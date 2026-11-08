"""Writing and removing files without touching what the tools did not make.

- An output never replaces what is there: a path that exists in any form, a dangling link included, is taken.
- A file is written whole under a name of its own beside its destination, created exclusively (so nothing already
  there, a link least of all, is written through), and swapped in at the end; it is removed if anything fails.  Two
  runs at once never share it.
- A folder a tool makes keeps a record of the files the tools wrote in it, `files.json`: each file's size and
  modification time when it was written.  Only what a record lists, and what is unchanged since, is ever removed, as a
  build tool's clean removes only the outputs its build log lists (Ninja manual, the clean tool).
- Links are never followed: a symbolic link, or a reparse point whose tag has the name-surrogate bit, which Microsoft
  defines for tags that stand for another named entity, as a junction's (mount point's) and a symbolic link's do
  (Reparse Point Tags, IsReparseTagNameSurrogate).  Tested with os.lstat, on every Python the skill runs on
  (Path.is_junction exists only from 3.12)."""
import contextlib
import errno
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path

NAME_SURROGATE = 0x20000000
RECORD = 'files.json'
KIND = 'music-production files'
MAX_RECORD = 64_000_000  # the largest record, report or receipt read
# The largest project read: one of validate's 500,000 notes as save_json writes it, 205 bytes a note measured (102 MB
# for 499,200 notes in the stress test of 0.4.0, which 64 MB had refused), with room for its CC and automation.
MAX_PROJECT = 160_000_000
# The deepest nesting of lists and objects a JSON document read may have: our own limit, the same on every Python
# (3.14 parsed the stress test's 100,000 levels that 3.13 refuses; a free-form harmony 600 levels deep passed validate
# and stopped excerpt's copy of the project with RecursionError).  It is eight times the deepest of the tools' own
# documents: 8 levels, measured over 183,131 JSON files of the project, its renders and the agents' examples.
MAX_DEPTH = 64
WORK_LOCK = 'work.lock'  # held in a render, round or audition folder by the run writing it, and by clean
LOCKS = (WORK_LOCK, 'entry.lock')  # a work lock's file, and a cache entry's (render.entry_lock)


def escape_unprintable():
    """Make a script print a character its output cannot encode as an escape (喆 as \\u5586), not stop on it.  On
    Windows, Python writes to a pipe or a file, as an agent reads a script's output, in the ANSI code page (Python
    documentation, sys.stdout), and a folder or piece name can hold a character that page lacks: 喆 and 堃 are not in
    code page 950, Traditional Chinese Windows' (Python's cp950 codec).  stderr already escapes so (Python gives it the
    backslashreplace handler); this does the same for stdout."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors='backslashreplace')


# The files this process put in place (replace, publish_new) or wrote itself (wrote): all that register_tree may record
# as a run's own.  A file someone else put in a folder while a run worked in it, a note saved there during a render,
# was recorded with the run's files, and clean removed it (found by a probe of 0.4.0).
_WROTE, _WROTE_LOCK = set(), threading.Lock()


def _key(path):
    return os.path.normcase(os.path.abspath(path))


def wrote(path):
    """Note `path` as a file this process wrote: replace and publish_new note theirs; a program's own output (a log, a
    file a check decodes) is noted by the code that names it."""
    with _WROTE_LOCK:
        _WROTE.add(_key(path))


def written_here(path):
    with _WROTE_LOCK:
        return _key(path) in _WROTE


def replace(src, dst):
    """os.replace, tried again for up to a second where Windows refuses it with PermissionError: a virus scanner or the
    search indexer may hold a file just written for a moment.  pip replaces its own files so (its utils.filesystem
    replace: for up to a second, every quarter), and graceful-fs, npm's file layer, retries a rename on Windows for up
    to a second for the same reason.  `dst` is noted as a file this process wrote (wrote)."""
    _swap(src, dst)
    wrote(dst)


def _swap(src, dst):
    for attempt in range(5):
        try:
            return os.replace(src, dst)
        except PermissionError:
            if os.name != 'nt' or attempt == 4:
                raise
            time.sleep(.25)


def publish_new(src, dst):
    """Give the new file `src` the name `dst`, which nothing may hold: where something has taken it since the output
    was found free (another run, the user), FileExistsError, and `src` stays for the caller to remove.  os.replace
    would put it in the other's place.  Windows' rename refuses an existing name; on POSIX, where rename replaces, a
    hard link refuses it, then the temporary name goes; a file system without hard links gets the name reserved first
    (created exclusively), which the new file then replaces (found by GPT Pro's third review of 0.4.0).  `dst` is
    noted as a file this process wrote (wrote)."""
    _publish(src, dst)
    wrote(dst)


def _publish(src, dst):
    if os.name == 'nt':
        for attempt in range(5):
            try:
                return os.rename(src, dst)
            except PermissionError:  # a virus scanner holding the new file (replace())
                if attempt == 4:
                    raise
                time.sleep(.25)
    try:
        os.link(src, dst)
    except FileExistsError:
        raise
    except OSError:
        # The name reserved (an empty file, created exclusively), then the new file put in its place.  Should that
        # fail, the reservation goes while it is still this one, empty: it was left under the output's name, which
        # then looked taken (found by GPT Pro's fourth review of 0.4.0).  A process killed between the two leaves it,
        # and a later run then finds the name taken and refuses it rather than write over what may be another's.
        fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            mine = os.fstat(fd)
        finally:
            os.close(fd)
        try:
            os.replace(src, dst)
        except BaseException:
            with contextlib.suppress(OSError):
                now = os.lstat(dst)
                if (now.st_dev, now.st_ino) == (mine.st_dev, mine.st_ino) and now.st_size == 0:
                    os.unlink(dst)
            raise
        return None
    os.unlink(src)
    return None


def lstat(path):
    try:
        return os.lstat(path)
    except OSError:
        return None


def linked(path):
    """A symbolic link, a junction or another reparse point that names a different place, read without following it."""
    s = lstat(path)
    if s is None:
        return False
    if stat.S_ISLNK(s.st_mode):
        return True
    return bool(getattr(s, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                and getattr(s, 'st_reparse_tag', 0) & NAME_SURROGATE)


def real_folder(path):
    """A folder, not a link to one."""
    s = lstat(path)
    return s is not None and stat.S_ISDIR(s.st_mode) and not linked(path)


def regular_file(path):
    """A regular file, not a link to one."""
    s = lstat(path)
    return s is not None and stat.S_ISREG(s.st_mode) and not linked(path)


def occupied(path):
    """Whether anything is at `path`: a file, a folder or a link, a dangling one included."""
    return os.path.lexists(path)


def lock(fd, wait):
    """Take an exclusive lock on an open file: fcntl.flock on POSIX, msvcrt.locking on Windows.  The system releases
    it when the process ends, however it ends (flock(2): when every descriptor of the open file is closed; LockFileEx:
    when the process terminates, after a delay that depends on the system's resources), so a stopped run leaves no
    stale lock, as a lock file made to exist would.  A second descriptor of the same file is refused even in the same
    process (flock(2); LockFileEx), and child processes do not hold it: Python's descriptors are not inherited (PEP 446).
    True when held; False while another process holds it; None where the drive cannot lock files."""
    if os.name == 'nt':
        import msvcrt
        while True:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK, 1)
                return True
            except OSError as e:
                # The C runtime's _locking: EACCES while another holds the bytes, EDEADLOCK once LK_LOCK has tried ten
                # times a second apart (wait on); anything else is a drive or file that cannot lock.  The byte locked
                # lies past the end of the empty file, which both _locking and LockFileEx allow; an exclusive lock
                # bars other processes from reading it, and the file is never read.
                if e.errno not in (errno.EDEADLK, errno.EACCES):
                    return None
                if not wait:
                    return False
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        return True
    except BlockingIOError:  # EWOULDBLOCK: another holds it (flock(2))
        return False
    except OSError:  # ENOLCK, or a file system without locks
        return None


def unlock(fd):
    with contextlib.suppress(OSError):
        if os.name == 'nt':
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)


def same_file(fd, path):
    """Whether `path` is still the file open as `fd` (its last holder may have removed it meanwhile)."""
    try:
        a, b = os.fstat(fd), os.stat(path)
    except OSError:
        return False
    return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


def is_lock_file(path):
    """A work lock's file as the tools make it: named work.lock, a regular file, empty (nothing is written to it)."""
    s = lstat(path)
    return Path(path).name in LOCKS and s is not None and stat.S_ISREG(s.st_mode) and not linked(path) and s.st_size == 0


def take(folder, create=True, name=WORK_LOCK):
    """Try the work lock of a render, round or audition folder without waiting.  Returns (state, fd): 'held' with the
    open file holding it; 'busy' while another process holds it; 'unlockable' where it cannot be taken (the drive
    cannot lock files, or work.lock there is no lock file: a link, a folder, a file with contents); with create=False,
    'free' where no lock file is there, as no run holds one then.  A lock taken on a file its holder removed meanwhile
    is let go and taken afresh."""
    path = Path(folder) / name
    for _ in range(10):
        if occupied(path) and not is_lock_file(path):
            return 'unlockable', None
        if not create and not occupied(path):
            return 'free', None
        try:
            fd = os.open(path, os.O_RDWR | (os.O_CREAT if create else 0) | getattr(os, 'O_NOFOLLOW', 0), 0o666)
        except FileNotFoundError:
            if create:
                return 'unlockable', None  # the folder itself is gone
            continue
        except OSError:
            return 'unlockable', None
        held = lock(fd, False)
        if held and not same_file(fd, path):
            unlock(fd)
            os.close(fd)
            continue
        if held:
            return 'held', fd
        os.close(fd)
        return ('busy' if held is False else 'unlockable'), None
    return 'unlockable', None


def let_go(fd):
    """Release a lock `take` gave, keeping its file (a look that changes nothing, as a dry run's)."""
    unlock(fd)
    os.close(fd)


def release(folder, fd):
    """Release a work lock `take` gave and remove its file, only where no other process can hold another by that
    name: on POSIX under the lock (a process that opens the name after makes a new file, its own lock); on Windows,
    which cannot remove a file a process holds open, once released, so a process that has opened it since keeps it."""
    path = Path(folder) / WORK_LOCK
    if os.name != 'nt' and same_file(fd, path):
        with contextlib.suppress(OSError):
            os.unlink(path)
    let_go(fd)
    if os.name == 'nt':
        with contextlib.suppress(OSError):
            os.unlink(path)


@contextlib.contextmanager
def working(folder):
    """Hold a render, round or audition folder while a run writes it: clean takes the same lock before it reads or
    removes anything there, so neither works in a folder the other is using, and two runs never write one folder at
    once.  A folder another holds is refused at once, as Bazel serves one command at a time per output folder and
    makes another wait or fail at once (Bazel documentation, Client/server implementation).  The file is opened for
    writing, which an NFS client needs for an exclusive lock (flock(2)).  Where the drive cannot lock files the run goes
    on without the lock, and clean leaves the folder alone."""
    state, fd = take(folder)
    if state == 'busy':
        raise ValueError(f'{folder} is in use: a render, round, audition or clean is working in it; wait for it to '
                         'finish, or write into a new folder')
    try:
        yield state == 'held'
    finally:
        if fd is not None:
            release(folder, fd)


def fresh(path, what='outputs never overwrite, so choose a new path'):
    """Refuse a path that is taken (Path.exists follows links, so a dangling link would pass it)."""
    if occupied(path):
        raise ValueError(f'{path} exists; {what}')


def no_links(path, below=None):
    """Refuse `path` when it, or a folder on the way to it from `below`, is a link: a write would leave the folder."""
    path = Path(path)
    stop = Path(below) if below is not None else None
    for p in [path, *path.parents]:
        if stop is not None and p == stop:
            break
        if linked(p):
            raise ValueError(f'{p} is a link; the tools write only into real folders (give the folder itself)')


# The mode a new file takes from the process's umask, read once at import, before any thread starts: tempfile.mkstemp
# makes its files 0600 and a file swapped in keeps its mode, so without this every output would be private to its
# owner where the user's umask shares it (POSIX; Windows has no such bits).
if os.name != 'nt':
    _UMASK = os.umask(0)
    os.umask(_UMASK)
    FILE_MODE = 0o666 & ~_UMASK
else:
    FILE_MODE = None


def _opened(fd):
    """Give a file mkstemp made the mode a new file would have had."""
    if FILE_MODE is not None:
        os.fchmod(fd, FILE_MODE)
    return fd


def stage_name(dest, suffix='.part'):
    """A new, empty file beside `dest`, created exclusively under a name no other run uses, for a program that writes
    a path itself (FFmpeg, a bank build); the caller swaps it in with os.replace or removes it."""
    dest = Path(dest)
    fd, name = tempfile.mkstemp(dir=dest.parent, prefix=f'.{dest.name}.', suffix=suffix)
    os.close(_opened(fd))
    return Path(name)


@contextlib.contextmanager
def staged(dest, mode='wb', encoding=None, newline=None, new=False):
    """Write `dest` whole: yields a file opened on a new name of its own beside it; on success that file takes the
    destination's place (os.replace swaps the name, so a hard link at the destination is never written through), on
    any failure it is removed.  With `new`, the destination must still be free when the file is done (publish_new): an
    output a command found free is never put in the place of one that took its name meanwhile."""
    dest = Path(dest)
    fd, name = tempfile.mkstemp(dir=dest.parent, prefix=f'.{dest.name}.', suffix='.part')
    try:
        with os.fdopen(_opened(fd), mode, encoding=encoding, newline=newline) as f:
            yield f
        (publish_new if new else replace)(name, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(name)
        raise


@contextlib.contextmanager
def staged_path(dest, suffix='.part', new=False):
    """As staged, for code that writes a path itself: yields the new file's path; on success it takes the destination's
    place (with `new`, only while nothing holds that name: publish_new), on any failure it is removed."""
    temp = stage_name(dest, suffix)
    try:
        yield temp
        (publish_new if new else replace)(temp, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise


def loads(text):
    """json.loads, refusing as ValueError a document nested more than MAX_DEPTH levels deep, or deeper than Python
    parses (json raises RecursionError): a record, a project or a report someone else made is refused with a reason,
    not a crash (found by the stress test of 0.4.0; the depth limit by CI on Python 3.14).  The depth is measured a
    level at a time, without recursion: about a quarter of a second for a project of 500,000 notes."""
    try:
        value = json.loads(text)
    except RecursionError:
        raise ValueError('a JSON document nested too deeply to read') from None
    level, depth = ([value] if isinstance(value, (dict, list)) else []), 0
    while level:
        depth += 1
        if depth > MAX_DEPTH:
            raise ValueError(f'a JSON document nested more than {MAX_DEPTH} levels deep')
        level = [x for c in level for x in (c.values() if isinstance(c, dict) else c) if isinstance(x, (dict, list))]
    return value


def read_json(path, limit=None):
    """The JSON in a regular file someone else may have made (a report, a receipt, a record), refused as ValueError
    where it is a link or larger than `limit` (MAX_RECORD by default) before any of it is read, or nested too deeply
    (found by GPT Pro's third review of 0.4.0: the limits did not reach every reader)."""
    path = Path(path)
    s = lstat(path)
    if s is None:
        raise FileNotFoundError(f'{path} is not there')
    if not stat.S_ISREG(s.st_mode) or linked(path):
        raise ValueError(f'{path} is no regular file (a link or a folder): it is not read')
    if s.st_size > (MAX_RECORD if limit is None else limit):
        raise ValueError(f'{path} is {s.st_size} bytes, more than a record of the tools is: it is not read')
    return loads(path.read_text(encoding='utf-8'))


def check_config_path(path, flag):
    """An installer's configuration path, before it installs: free, and not named as the records the tools keep."""
    if occupied(path):
        raise ValueError(f'{flag} {path} exists; choose a new path for the configuration')
    if Path(path).name == RECORD:
        raise ValueError(f'{flag} names {RECORD}, the records the tools keep; choose another name for the configuration')


def save_config(path, config, flag):
    """An installer's configuration, written last: only where nothing has taken the path since the install began (a
    bank or a record the install put there, which a configuration written over left broken), and never over what
    takes it meanwhile (publish_new).  Found by GPT Pro's third review of 0.4.0."""
    if occupied(path):
        raise ValueError(f'{flag} {path} now holds a file the install put there; everything else is installed: run it '
                         f'again with a {flag} of its own')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_json(Path(path).resolve(), config, new=True)


def write_json(path, value, new=False):
    with staged(path, 'w', encoding='utf-8', new=new) as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def _record_value(record):
    """What a record the tools wrote holds (a regular files.json of this kind), or None."""
    if not regular_file(record) or lstat(record).st_size > MAX_RECORD:
        return None
    try:
        value = loads(Path(record).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) and value.get('kind') == KIND else None


def recorded(folder):
    """The files a folder's record lists, {posix relative path: [size, mtime_ns]}; {} without a readable record."""
    value = _record_value(Path(folder) / RECORD)
    listed = value.get('files') if value else None
    return {k: v for k, v in listed.items() if isinstance(v, list) and len(v) == 2} if isinstance(listed, dict) else {}


def is_record(path):
    """Whether `path` is a record the tools wrote: a file named files.json alone is not one."""
    return Path(path).name == RECORD and _record_value(path) is not None


def has_record(folder):
    return regular_file(Path(folder) / RECORD)


def register(folder, paths):
    """Add files a tool wrote in `folder` (paths inside it) to its record, with their size and modification time.  A
    files.json there that is no record of the tools (another program's, the user's, a link) is renamed aside first, kept
    and never written over; returns that name, or None."""
    # A relative path is the caller's, from the working folder, as every caller builds it (folder / name): a round or a
    # review given a relative --output recorded nothing when it was taken from `folder` instead (found by the stress
    # test of 0.4.0).
    folder = Path(os.path.abspath(folder))
    moved = aside(folder / RECORD) if occupied(folder / RECORD) and not is_record(folder / RECORD) else None
    listed = recorded(folder)
    for p in paths:
        p = Path(os.path.abspath(p))
        s = lstat(p)
        if s is not None and stat.S_ISREG(s.st_mode) and not linked(p) and p.name != RECORD:
            try:
                rel = p.relative_to(folder)
            except ValueError:  # one of the two given resolved, the other not (a junction on the way)
                rel = Path(os.path.realpath(p)).relative_to(os.path.realpath(folder))
            listed[rel.as_posix()] = [s.st_size, s.st_mtime_ns]
    write_json(folder / RECORD, {'kind': KIND, 'files': listed})
    return moved


def links_in(folder):
    """The links under `folder` (symbolic links, junctions), found without following any.  A command that reads a
    folder someone else may have made refuses one holding links: a stem that is a link would be read, and compared, from
    wherever it points."""
    found = []
    for base, dirs, names in os.walk(folder, followlinks=False):
        found += [Path(base) / n for n in dirs + names if linked(Path(base) / n)]
        dirs[:] = [d for d in dirs if real_folder(Path(base) / d)]
    return found


def foreign(folder):
    """What under `folder` a write could leave it through, found without following anything: links, and files that
    have another name too (hard links)."""
    found = []
    for base, dirs, names in os.walk(folder, followlinks=False):
        base = Path(base)
        for n in dirs + names:
            p, s = base / n, lstat(base / n)
            if linked(p) or (s is not None and stat.S_ISREG(s.st_mode) and s.st_nlink > 1):
                found.append(p)
        dirs[:] = [d for d in dirs if real_folder(base / d)]
    return found


def tree(folder, skip=()):
    """Every regular file under `folder`, without following links and without entering the folders in `skip`."""
    found = []
    for base, dirs, names in os.walk(folder, followlinks=False):
        base = Path(base)
        dirs[:] = [d for d in dirs if real_folder(base / d) and base / d not in skip]
        found += [base / n for n in names if regular_file(base / n)]
    return found


def register_tree(folder, skip=(), keep=None):
    """Record the files under `folder` (but the folders in `skip`, which keep their own records) that this process
    wrote (wrote), and those `keep` (the record of a run resumed) listed and that are unchanged since.  Anything else
    there is not the tools': a file saved into the folder while the run worked in it was recorded, and clean removed
    it (found by a probe of 0.4.0); one the user changed between a run and its resume stays the user's."""
    folder = Path(folder)
    paths = []
    for p in tree(folder, skip):
        if p.name == RECORD or (p.parent == folder and is_lock_file(p)):
            continue  # the record itself, and the run's lock, which goes with the run
        if not written_here(p):
            entry = (keep or {}).get(p.relative_to(folder).as_posix())
            if entry is None or not unchanged(p, entry):
                continue
        paths.append(p)
    register(folder, paths)


def unchanged(path, entry):
    """Whether a file still has the size and modification time its record gave it."""
    s = lstat(path)
    return s is not None and stat.S_ISREG(s.st_mode) and not linked(path) and [s.st_size, s.st_mtime_ns] == list(entry)


def aside(path):
    """Rename what is at `path` aside, to a name beside it that nothing has: kept, never removed."""
    path = Path(path)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    for k in range(1000):
        other = path.with_name(f'{path.name}.replaced-{stamp}' + (f'-{k}' if k else ''))
        if not occupied(other):
            _swap(path, other)  # not noted as the tools': it is what they set aside
            return other
    raise ValueError(f'No free name to set {path} aside')


def same_bytes(a, b):
    sa, sb = lstat(a), lstat(b)
    if sa is None or sb is None or sa.st_size != sb.st_size:
        return False
    with open(a, 'rb') as fa, open(b, 'rb') as fb:
        while True:
            x, y = fa.read(1 << 20), fb.read(1 << 20)
            if x != y:
                return False
            if not x:
                return True


def place(src, dest, root, listed=None):
    """Move the new file `src` to `dest`, under `root` (a folder whose record lists what was installed in it; `listed`
    is that record, read once by a caller placing many files).  What is already at `dest` is replaced only if the
    record lists it unchanged; with the same bytes it simply stays; anything else (a file the installer did not put
    there, a link, a folder) is renamed aside and reported, never removed or written through: os.replace swaps names, so
    a hard link at `dest` keeps its old bytes.  Returns the name set aside, or None."""
    src, dest, root = Path(src), Path(dest), Path(root)
    no_links(dest.parent, below=root.parent)
    dest.parent.mkdir(parents=True, exist_ok=True)
    moved = None
    if occupied(dest):
        entry = (listed if listed is not None else recorded(root)).get(dest.relative_to(root).as_posix())
        if regular_file(dest) and entry is not None and unchanged(dest, entry):
            pass
        elif regular_file(dest) and same_bytes(dest, src):
            os.unlink(src)
            return None
        else:
            moved = aside(dest)
    replace(src, dest)
    return moved


def prune(folder):
    """Remove the folders under `folder`, and `folder` itself, that are left empty: deepest first, without following
    or removing links.  A folder that still holds anything stays."""
    folder = Path(folder)
    if not real_folder(folder):
        return
    for base in sorted(real_folders(folder), key=lambda b: -len(b.parts)):
        with contextlib.suppress(OSError):
            os.rmdir(base)


def real_folders(folder, skip=()):
    """`folder` and every folder under it, never entering a link or a junction (os.walk with followlinks=False still
    enters a junction on Windows, which is not a symbolic link to it) nor the folders in `skip`."""
    found = []
    for base, dirs, names in os.walk(folder, followlinks=False):
        base = Path(base)
        dirs[:] = [d for d in dirs if real_folder(base / d) and base / d not in skip]
        found.append(base)
    return found


def stage_copy(src, dest):
    """Copy `src` to a new file of its own beside `dest` (stage_name) and return that file, ready to be placed."""
    temp = stage_name(dest, '.copy')
    try:
        shutil.copyfile(src, temp)
        shutil.copystat(src, temp)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise
    return temp


def install_tree(staging, target):
    """Move every file extracted into the private folder `staging` to the same place under `target` (place), record
    them as installed there, and remove `staging`, which this run made.  Returns the files set aside."""
    staging, target = Path(staging), Path(target)
    target.mkdir(parents=True, exist_ok=True)
    no_links(target)
    placed, moved, listed = [], [], recorded(target)
    try:
        for p in tree(staging):
            dest = target.joinpath(*p.relative_to(staging).parts)
            m = place(p, dest, target, listed)
            if m is not None:
                moved.append(m)
            placed.append(dest)
        m = register(target, placed)
        if m is not None:
            moved.append(m)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return moved


def staging_folder(target):
    """A new private folder beside `target` to extract into (tempfile.mkdtemp: a name no other run has)."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=target.parent, prefix=f'.{target.name}.', suffix='.extract'))


def register_output(path, levels=4):
    """Record a file a command wrote inside a folder a tool made (its nearest folder up to `levels` above with a record),
    so that clean may later remove it with that folder; outside such a folder, nothing."""
    path = Path(path).resolve()
    for folder in list(path.parents)[:levels]:
        if is_record(folder / RECORD):  # a files.json of another program's is no folder of the tools'
            register(folder, [path])
            return folder
    return None
