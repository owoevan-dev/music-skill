"""Writing and removing files without touching what the tools did not make.

- An output never replaces what is there: a path that exists in any form, a dangling link included, is taken.
- A file is written whole under a name of its own beside its destination, created exclusively (so nothing already
  there, a link least of all, is written through), and swapped in at the end; it is removed if anything fails.  Two
  runs at once never share it.
- A folder a tool makes keeps a record of the files the tools wrote in it, `files.json`: each file's size and
  modification time when it was written.  Only what a record lists, and what is unchanged since, is ever removed, as a
  build tool's clean removes only the outputs its build log lists (Ninja manual, the clean tool).
- While a run writes a folder (journaled), the folder keeps a journal of the run's writes, `files.journal`, appended
  line by line, each line written whole: each new file's name before the file is made and again, with the file's
  number, once it is made, and each finished file's size, modification time and file number before it takes its name.
  A run stopped at any moment, killed even, then leaves only files the record or the journal proves the run's own, so
  a render takes the folder up again (--resume) and clean removes it, as a database logs a change before it makes it
  and recovers from the log after a crash (PostgreSQL documentation, Write-Ahead Logging).  A proof is of a file, never
  of a name: a file under a name the journal holds that is not the file the run made there (another number) is not
  the run's (GPT's re-review of 0.5, RR01).  Two cases are left unproven on purpose, for --resume to name and stop on
  and for clean to leave: a file the run made and was stopped before noting (a name noted before the file is made
  proves nothing: GPT's review of 0.5, C01), and a file a program the stopped run had started wrote under one of its
  names after the run's own was removed.  The journal goes once the record lists everything.
- Links are never followed: a symbolic link, or a reparse point whose tag has the name-surrogate bit, which Microsoft
  defines for tags that stand for another named entity, as a junction's (mount point's) and a symbolic link's do
  (Reparse Point Tags, IsReparseTagNameSurrogate).  Tested with os.lstat, on every Python the skill runs on
  (Path.is_junction exists only from 3.12)."""
import contextlib
import errno
import json
import os
import secrets
import shutil
import stat
import sys
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

NAME_SURROGATE = 0x20000000
RECORD = 'files.json'
KIND = 'music-production files'
JOURNAL = 'files.journal'  # a folder's journal of the writes of the run at work in it (journaled)
JOURNAL_KIND = 'music-production journal'
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
# In a render's folder, the parts it made itself where the shared cache could not be locked (render.entry_lock): the
# render's own files, under its work lock, record and journal, and no cache to clean (clean.clean).
UNLOCKED_CACHE = 'unlocked_cache'


def one_line(text):
    """`text` with each control character written as its escape (a line break as \\n, ESC as \\x1b; the Unicode
    line and paragraph separators too): text a summary takes from a project, a record or a file's name stays on the line
    that prints it, where it cannot pass for a line of the tool's own or drive a terminal (CWE-150, Improper
    Neutralization of Escape, Meta, or Control Sequences; a title's line break began a line of review's summary: GPT's
    security audit of 0.5, L05).  A tab stays a tab: it ends no line, and text copied from a table holds them (the
    audit's re-review, N3)."""
    return ''.join(c.encode('unicode_escape').decode('ascii') if c != '\t' and unicodedata.category(c) in ('Cc', 'Zl', 'Zp') else c
                   for c in text)


def joined(rows):
    """The rows of a summary, one line each (one_line)."""
    return '\n'.join(one_line(row) for row in rows)


def escape_unprintable():
    """Make a script print a character its output cannot encode as an escape (喆 as \\u5586), not stop on it.  On
    Windows, Python writes to a pipe or a file, as an agent reads a script's output, in the ANSI code page (Python
    documentation, sys.stdout), and a folder or piece name can hold a character that page lacks: 喆 and 堃 are not in
    code page 950, Traditional Chinese Windows' (Python's cp950 codec).  stderr already escapes so (Python gives it the
    backslashreplace handler); this does the same for stdout."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors='backslashreplace')


# The files this process put in place (replace, publish_new) or wrote itself (wrote), each as it was then (its device,
# inode, size and modification time): all that register_tree may record as a run's own.  A file someone else put in a
# folder while a run worked in it, a note saved there during a render, was recorded with the run's files, and clean
# removed it (found by a probe of 0.4.0); a file put under a name the run had written, or one changed since, was still
# taken for the run's, as only names were kept (found by GPT Pro's fifth review of 0.4.0).
_WROTE, _WROTE_LOCK = {}, threading.Lock()


def _key(path):
    return os.path.normcase(os.path.abspath(path))


def _stamp(path):
    s = lstat(path)
    return None if s is None or not stat.S_ISREG(s.st_mode) else (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def wrote(path):
    """Note the file now at `path` as one this process wrote: replace and publish_new note theirs; a program's own output
    (a log, a file a check decodes) is noted by the code that runs it, once the program has finished writing."""
    stamp = _stamp(path)
    with _WROTE_LOCK:
        if stamp is None:
            _WROTE.pop(_key(path), None)
        else:
            _WROTE[_key(path)] = stamp


def written_here(path):
    """Whether the file at `path` is the one this process noted there, unchanged since."""
    with _WROTE_LOCK:
        want = _WROTE.get(_key(path))
    return want is not None and _stamp(path) == want


# The folders this process journals, {_key(folder): _Journal}, while a run writes them (journaled).
_JOURNALS, _JOURNALS_LOCK = {}, threading.Lock()


class _Journal:
    """The journal of one folder: opened at the first write, each line appended whole, from every thread of the run."""

    def __init__(self, root):
        self.root, self.fd, self.lock = Path(root), None, threading.Lock()

    def append(self, entry):
        line = (json.dumps(entry, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        with self.lock:
            if self.fd is None:
                self.fd = _open_journal(self.root / JOURNAL)
            try:
                _write_all(self.fd, line)
            except BaseException:
                # A write that failed part way leaves a cut line.  The journal is closed, so the next line opens it
                # anew and starts on a line of its own (_open_journal): written on after the cut one, it ran into it,
                # and neither was read, the proof of the file the next one announced lost with them (GPT's second
                # re-review of 0.5, R03: a render's report and its record are written after a failure, the journal
                # still open).
                fd, self.fd = self.fd, None
                with contextlib.suppress(OSError):
                    os.close(fd)
                raise

    def close(self):
        with self.lock:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None


def _write_all(fd, data):
    """Write all of `data`: os.write may take fewer bytes than it is given (POSIX write(2)), and the rest would be lost
    with the proof the line carries.  A write that takes nothing, or fails, raises, so the file a line announces never
    takes its name without it (GPT's review of 0.5, C02)."""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if not n:
            raise OSError(errno.EIO, 'a write to the journal took nothing')
        view = view[n:]


def _open_journal(path):
    """The journal at `path`, opened to append: a new one starts with its kind, and one there already is taken up only
    when the tools wrote it (a file of that name that is not one is set aside first, kept).  One whose last line a stop
    cut off gets a line break first, so the next line is read on its own rather than lost with the cut one (GPT's review
    of 0.5, C02)."""
    if occupied(path) and not is_journal(path):
        aside(path)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0),
                 0o666)
    try:
        size = os.fstat(fd).st_size
        if size == 0:
            _write_all(fd, (json.dumps({'kind': JOURNAL_KIND}) + '\n').encode('utf-8'))
        else:
            with open(path, 'rb') as f:
                f.seek(size - 1)
                if f.read(1) != b'\n':
                    _write_all(fd, b'\n')
    except BaseException:
        os.close(fd)
        raise
    return fd


def is_journal(path):
    """Whether `path` is a journal the tools wrote: a regular file named files.journal whose first line names its kind."""
    if Path(path).name != JOURNAL or not regular_file(path) or lstat(path).st_size > MAX_RECORD:
        return False
    try:
        with open(path, 'rb') as f:
            first = f.readline(200)
        return json.loads(first.decode('utf-8')) == {'kind': JOURNAL_KIND}
    except (OSError, ValueError):
        return False


@contextlib.contextmanager
def journaled(folder):
    """Journal what this process writes in `folder`, and in the folders under it, while the block runs: each new file
    (staged, stage_name, a program's log) is named in the journal before it is made and noted once it is made, and
    each takes its name only after the journal holds its size, time and number (replace, publish_new).  Yields
    the journal.  A block inside another on the same folder shares the outer one's journal and leaves it to the outer
    to close: it had closed it, and the outer's later files went unjournaled (GPT's review of 0.5, C05)."""
    folder = Path(os.path.abspath(folder))
    candidate = _Journal(folder)  # opens nothing until its first line
    with _JOURNALS_LOCK:
        journal = _JOURNALS.setdefault(_key(folder), candidate)
        mine = journal is candidate
    try:
        yield journal
    finally:
        if mine:
            with _JOURNALS_LOCK:
                if _JOURNALS.get(_key(folder)) is journal:
                    del _JOURNALS[_key(folder)]
            journal.close()


def _journal_for(path):
    """The journal of the deepest journaled folder holding `path`, or None."""
    key = _key(path)
    with _JOURNALS_LOCK:
        held = [(k, j) for k, j in _JOURNALS.items() if key.startswith(k.rstrip(os.sep) + os.sep)]
    return max(held, key=lambda kj: len(kj[0]))[1] if held else None


def _rel(folder, path):
    return os.path.relpath(os.path.abspath(path), os.path.abspath(folder)).replace(os.sep, '/')


relative = _rel  # the posix path of `path` relative to `folder`, as the record and the journal name a file


def _coming(src, dst):
    """Before `src` takes the name `dst` in a journaled folder: the journal notes the size, time and number `dst` is
    about to hold (a rename keeps all three), so a run stopped between the rename and its record still proves it."""
    journal = _journal_for(dst)
    if journal is not None:
        s = stamp(src)
        if s is not None:
            journal.append({'f': _rel(journal.root, dst), 's': s})


def proofs(folder):
    """What the journal in `folder` proves: ({name: numbers} of the new files it named before they were made, with the
    file numbers it noted for the files made under each name (none: named and never noted made), {name: [stamps]} of
    the files it noted as they took their names), by posix path relative to the folder; nothing without a journal of
    the tools.  A cut last line (the run stopped as it wrote it), or one nested too deeply to read, is passed over, and
    so is a made line without a file number (0.5 before its release wrote those: its files stay, named by --resume)."""
    path = Path(folder) / JOURNAL
    named, made, gone, stamps = set(), {}, set(), {}
    if not is_journal(path):
        return {}, stamps
    with open(path, 'rb') as f:
        lines = f.read(MAX_RECORD).split(b'\n')[1:]
    number = lambda x: isinstance(x, int) and not isinstance(x, bool)
    good = lambda v: isinstance(v, list) and len(v) == 3 and all(number(x) for x in v)
    for line in lines:
        try:
            entry = loads(line.decode('utf-8'))  # the depth limit every record has (GPT's review of 0.5, C06)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get('t'), str):
            named.add(entry['t'])
        elif isinstance(entry.get('c'), str):
            if number(entry.get('i')):
                made.setdefault(entry['c'], set()).add(entry['i'])  # made: the file of that number is the run's
        elif isinstance(entry.get('x'), str):
            gone.add(entry['x'])  # a name found taken when it was to be made: someone else's, never the run's
        elif isinstance(entry.get('f'), str) and good(entry.get('s')):
            stamps.setdefault(entry['f'], []).append(entry['s'])
    return {n: frozenset(made.get(n, ())) for n in named - gone}, stamps


def proven(folder, path, found=None):
    """Whether the file at `path`, in `folder`, is one the folder's journal proves a run's own: the new file it made
    exclusively under a name it held first, the same file still (its number, noted once it was made), or a file it
    noted as it took its name, unchanged since.  A name noted before the file is made proves nothing alone: making it
    may then fail on a file someone else has there (GPT's review of 0.5, C01).  Nor does a name noted made prove the
    file there now: one put in its place since, a copy even, is another file with another number (GPT's re-review of
    0.5, RR01; the name alone had proved it, on the belief that FluidSynth makes its output anew).  A made file's size
    and time are not held to, as the run or a program it starts is still writing it.  Every writer of the tools keeps
    the number of a file made first: FluidSynth -F, FFmpeg -y, Python's open('wb') and shutil.copyfile, measured on
    NTFS with Python 3.10 and 3.13; what replaces a made file by a rename goes through replace, which notes its stamp.
    The number is as good as the file system makes it: POSIX has the device and number identify a file among those
    that exist (IEEE Std 1003.1, <sys/stat.h>), not that a deleted file's number is never given again; NTFS gave 2,000
    different numbers to 2,000 files made and deleted under one name (our measurement).  `found` is proofs(folder),
    read once by a caller looking at many files."""
    named, stamps = found if found is not None else proofs(folder)
    rel = _rel(folder, path)
    now = stamp(path)
    return now is not None and (now[2] in named.get(rel, ()) or now in stamps.get(rel, []))


def adopt(folder):
    """Take up a folder an earlier run of the tools wrote, before writing in it again: the new files its journal names
    that a stopped run left (half written, or never swapped in) are removed, and what the record lists unchanged or the
    journal proves is returned, {posix path: stamp}, for register_tree's `keep`.  Anything else is the caller's to
    refuse (strays)."""
    folder = Path(folder)
    found = proofs(folder)
    named, _ = found
    keep = {k: v for k, v in recorded(folder).items()}
    for p in tree(folder):
        rel = _rel(folder, p)
        if rel in named:
            # Removed only where it is the file the journal noted made (or has the stamp noted as it took the name);
            # a run stopped in the instant between making it and noting it leaves one it cannot prove, and so does a
            # file of another number under the name: both stay for strays to name.
            if proven(folder, p, found):
                with contextlib.suppress(OSError):
                    p.unlink()
        elif not unchanged(p, keep.get(rel, (-1, -1))) and proven(folder, p, found):
            # The run's, written since the record (a recorded file the run replaced counts too, by what it is now).
            keep[rel] = stamp(p)
    return keep


def strays(folder, keep):
    """The files under `folder` that are not in `keep` (what adopt found to keep) unchanged, the record, the journal
    and the folder's lock aside.  The journal is not read again here: a file adopt proved the run's and could not
    remove (one a program holds open) is listed with those nothing accounts for."""
    folder = Path(folder)
    return [p for p in tree(folder) if p.name not in (RECORD, JOURNAL) and not (p.parent == folder and is_lock_file(p))
            and not unchanged(p, keep.get(_rel(folder, p), (-1, -1)))]


def drop_journal(folder):
    """Remove the journal of `folder` once the record lists what it proved: closed first where this process has it
    open, and only while no new file it names is left (a stopped write's)."""
    folder = Path(folder)
    journal = _JOURNALS.get(_key(os.path.abspath(folder)))
    if journal is not None:
        journal.close()
    path = folder / JOURNAL
    if not is_journal(path):
        return False
    named, _ = proofs(folder)
    if any(regular_file(folder / n) for n in named):
        return False
    with contextlib.suppress(OSError):
        path.unlink()
        return True
    return False


def replace(src, dst):
    """os.replace, tried again for up to a second where Windows refuses it with PermissionError: a virus scanner or the
    search indexer may hold a file just written for a moment.  pip replaces its own files so (its utils.filesystem
    replace: for up to a second, every quarter), and graceful-fs, npm's file layer, retries a rename on Windows for up
    to a second for the same reason.  `dst` is noted as a file this process wrote (wrote), and in a journaled folder
    the journal holds what it is about to be first (_coming)."""
    _coming(src, dst)
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
    noted as a file this process wrote (wrote) the moment it holds the new file, before the temporary name goes: a
    failure to remove that name left a published output unnoted (found by GPT Pro's fifth review of 0.4.0)."""
    _publish(src, dst)


def _publish(src, dst):
    _coming(src, dst)
    if os.name == 'nt':
        for attempt in range(5):
            try:
                os.rename(src, dst)
                wrote(dst)
                return None
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
        wrote(dst)
        return None
    wrote(dst)
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


def cache_file(cache, *parts):
    """The path of a file a setup keeps under its download cache (`cache`, as the setup resolved it), its folder made:
    refused when a folder on the way down from `cache` is a link.  The patches' folders were made, and the downloads
    written, wherever a link inside a cache from elsewhere led, before any check of the install's own (the re-review
    of GPT's security audit of 0.5, N1).  Folders above the cache are the user's own path and may be links."""
    cache = Path(cache)
    dest = cache.joinpath(*parts)
    no_links(dest.parent, below=cache)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def real_runtime(runtime):
    """Refuse a runtime folder (given resolved) that holds a link directly in it: a setup makes its folders there by
    name (the downloads, the tools, pylib, the sources and builds), and one that was a link took the downloads and the
    installed files wherever it led; resolving a folder before the check hid the link from it (GPT's security audit
    of 0.5, S03).  Deeper, an install places each file only through real folders (place)."""
    runtime = Path(runtime)
    odd = sorted(p for p in runtime.iterdir() if linked(p)) if real_folder(runtime) else []
    if odd:
        raise ValueError(f'{odd[0]} is a link; a setup installs only into real folders of its runtime (--archive-cache '
                         'names another place for the downloads)')


@contextlib.contextmanager
def installing(folder):
    """Hold a runtime folder while a setup installs into it (bootstrap.py, fetch_soundbanks.py), by the lock a render
    holds on its folder (take): a second setup started meanwhile is refused at once.  Two at once each read the folder's
    record before the other wrote it, and each set aside what it found at a name (GPT's security audit of 0.5, S05).
    Where the drive cannot lock files the setup goes on without the lock."""
    state, fd = take(folder)
    if state == 'busy':
        raise ValueError(f'{folder} is in use: another setup (bootstrap.py or fetch_soundbanks.py) is installing into '
                         'it; run this one when that has finished')
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


def new_file(dest, suffix='.part'):
    """A new, empty file beside `dest`, opened for writing: (descriptor, path).  It is created exclusively under a name
    no other run uses, as tempfile.mkstemp makes one (a random part, O_EXCL, retried when taken), and in a journaled
    folder the journal holds its name before it is made and again, with the file's number, once it is made: a run
    stopped at any moment leaves no file of its own that the journal cannot name, and only the file it noted made
    counts as the run's (proven).  Stopped in the instant between making the file and noting it, the run leaves that
    one file unproven.  A name found taken is noted as not the run's."""
    dest = Path(dest)
    journal = _journal_for(dest)
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    for _ in range(100):
        name = dest.parent / f'.{dest.name}.{secrets.token_hex(6)}{suffix}'
        if journal is not None:
            journal.append({'t': _rel(journal.root, name)})
        try:
            fd = os.open(name, flags, 0o600)
        except FileExistsError:
            if journal is not None:
                journal.append({'x': _rel(journal.root, name)})
            continue
        try:
            if journal is not None:
                journal.append({'c': _rel(journal.root, name), 'i': os.fstat(fd).st_ino})
        except BaseException:
            os.close(fd)
            with contextlib.suppress(OSError):
                os.unlink(name)  # made here and not yet noted: this run's to remove
            raise
        return _opened(fd), name
    raise FileExistsError(f'No free name for a new file beside {dest}')


def stage_name(dest, suffix='.part'):
    """A new, empty file beside `dest` (new_file), for a program that writes a path itself (FFmpeg, a bank build); the
    caller swaps it in with replace or removes it."""
    fd, name = new_file(dest, suffix)
    os.close(fd)
    return name


@contextlib.contextmanager
def staged(dest, mode='wb', encoding=None, newline=None, new=False):
    """Write `dest` whole: yields a file opened on a new name of its own beside it; on success that file takes the
    destination's place (os.replace swaps the name, so a hard link at the destination is never written through), on
    any failure it is removed.  With `new`, the destination must still be free when the file is done (publish_new): an
    output a command found free is never put in the place of one that took its name meanwhile."""
    fd, name = new_file(dest, '.part')
    try:
        with os.fdopen(fd, mode, encoding=encoding, newline=newline) as f:
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



def read_object(path, what, limit=None, needs=()):
    """read_json for a document that must be a JSON object (a spec, a manifest, a configuration) holding the fields
    `needs` names, as (key, type, what it holds): anything else is refused with what it should be (a list there, or an
    object without the field the command reads first, stopped it with a traceback; found by GPT Pro's fifth review of
    0.4.0)."""
    value = read_json(path, limit)
    if not isinstance(value, dict):
        raise ValueError(f'{path}: {what} is a JSON object, not {type(value).__name__}')
    for key, kind, holds in needs:
        if not isinstance(value.get(key), kind):
            raise ValueError(f'{path}: {what} needs "{key}", {holds}')
    return value


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


def stamp(path):
    """What a record keeps of a file the tools wrote: its size, modification time and file number (st_ino), or None for
    anything but a regular file.  The number tells the file from a copy put in its place since, which can keep the size
    and time (a backup restored, shutil.copy2): size and time alone took such a copy for the tools' file (found by GPT
    Pro's sixth review of 0.4.0)."""
    s = lstat(path)
    return [s.st_size, s.st_mtime_ns, s.st_ino] if s is not None and stat.S_ISREG(s.st_mode) and not linked(path) else None


def recorded(folder):
    """The files a folder's record lists, {posix relative path: [size, mtime_ns, file number]}; {} without a readable
    record.  An entry of two numbers, from a record written before the file number was kept, is listed too, and taken as
    no proof (unchanged)."""
    value = _record_value(Path(folder) / RECORD)
    listed = value.get('files') if value else None
    good = lambda v: isinstance(v, list) and len(v) in (2, 3) and all(isinstance(x, int) and not isinstance(x, bool) for x in v)
    return {k: v for k, v in listed.items() if good(v)} if isinstance(listed, dict) else {}


def is_record(path):
    """Whether `path` is a record the tools wrote: a file named files.json alone is not one."""
    return Path(path).name == RECORD and _record_value(path) is not None


def has_record(folder):
    return regular_file(Path(folder) / RECORD)


def register(folder, paths):
    """Add files a tool wrote in `folder` (paths inside it) to its record, as stamp() gives them.  A
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
            listed[rel.as_posix()] = [s.st_size, s.st_mtime_ns, s.st_ino]
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
        if p.name == RECORD or (p.parent == folder and (is_lock_file(p) or is_journal(p))):
            continue  # the record itself, the journal, and the run's lock, which goes with the run
        if not written_here(p):
            entry = (keep or {}).get(p.relative_to(folder).as_posix())
            if entry is None or not unchanged(p, entry):
                continue
        paths.append(p)
    register(folder, paths)


def remove_own(folder):
    """Remove what a run's folder holds of the run's own, under the folder's work lock: the files its record lists
    unchanged, then the record and the folders left empty, the folder itself last.  Anything else (a file someone put
    there, one changed since, a link) stays, with the record, and False is returned, as it is while another run holds
    the folder; True once the folder is gone.  For a run that takes its own failed output away, as an audition does to
    render again with a longer tail: it removed the whole folder, whatever was in it (found by GPT Pro's fifth review of
    0.4.0)."""
    folder = Path(folder)
    if not real_folder(folder):
        return not occupied(folder)
    state, fd = take(folder)
    if state == 'busy':
        return False
    try:  # 'unlockable': a drive that cannot lock files, or a work.lock that is no lock file (it stays, as others do)
        # The records and the journal as found: one written since stays, with the folder.
        records = {p: stamp(p) for p in tree(folder) if is_record(p) or is_journal(p)}
        listed, found = recorded(folder), proofs(folder)
        for p in tree(folder):
            if p.name in (RECORD, JOURNAL) or (p.parent == folder and is_lock_file(p)):
                continue
            entry = listed.get(p.relative_to(folder).as_posix())
            if (entry is not None and unchanged(p, entry)) or proven(folder, p, found):
                with contextlib.suppress(FileNotFoundError):
                    p.unlink()
        if [p for p in tree(folder) if not (is_record(p) or is_journal(p)) and not (p.parent == folder and is_lock_file(p))] + links_in(folder):
            return False
        for p in tree(folder):  # the records as found; and the lock's file where none is held (the lock held goes on release)
            if ((is_record(p) or is_journal(p)) and stamp(p) == records.get(p)) or (fd is None and p.parent == folder and is_lock_file(p)):
                with contextlib.suppress(OSError):
                    p.unlink()
    finally:
        if fd is not None:
            release(folder, fd)
    for base in sorted(real_folders(folder), key=lambda b: -len(b.parts)):
        with contextlib.suppress(OSError):
            os.rmdir(base)
    return not occupied(folder)


def unchanged(path, entry):
    """Whether the file at `path` is still the one a record (or a plan, from stamp()) noted: the same size, modification
    time and file number.  An entry of two numbers, from a record written before the number was kept, cannot tell a copy
    from the file it names, so nothing is taken on it: its files stay, and --resume refuses them."""
    entry = list(entry)
    return len(entry) == 3 and stamp(path) == entry


def aside(path):
    """Rename what is at `path` aside, to a name beside it that nothing has: kept, never removed."""
    path = Path(path)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    for k in range(1000):
        other = path.with_name(f'{path.name}.replaced-{stamp}' + (f'-{k}' if k else ''))
        if not occupied(other):
            try:
                _move_new(path, other)  # not noted as the tools': it is what they set aside
            except FileExistsError:
                continue  # another setup took the name since the look: the next name
            return other
    raise ValueError(f'No free name to set {path} aside')


def _move_new(src, dst):
    """Rename `src` (a file, a folder or a link) to `dst`, which nothing may hold: FileExistsError where something has
    taken the name since it was seen free.  os.replace put `src` in its place: of two setups setting a file aside in the
    same second, the second moved the first's new file over the user's, the only copy (GPT's security audit of 0.5,
    S05).  Windows' rename refuses an existing name.  POSIX's replaces one, so the name is reserved first, made
    exclusively (a folder for a folder, mkdir(2); an empty file otherwise, open(2) with O_EXCL), and rename(2) then
    puts `src` in the reservation's place; should that fail, the reservation goes while it is still this one, empty."""
    if os.name == 'nt':
        for attempt in range(5):
            try:
                return os.rename(src, dst)
            except PermissionError:  # a virus scanner holding the file (replace()); FileExistsError is not one
                if attempt == 4:
                    raise
                time.sleep(.25)
    folder = stat.S_ISDIR(os.lstat(src).st_mode)
    if folder:
        os.mkdir(dst, 0o700)
    else:
        os.close(os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    mine = os.lstat(dst)
    try:
        os.rename(src, dst)
    except BaseException:
        with contextlib.suppress(OSError):
            now = os.lstat(dst)
            if (now.st_dev, now.st_ino) == (mine.st_dev, mine.st_ino):
                (os.rmdir if folder else os.unlink)(dst)
        raise


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
