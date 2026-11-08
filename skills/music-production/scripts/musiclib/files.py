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
import json
import os
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path

NAME_SURROGATE = 0x20000000
RECORD = 'files.json'
KIND = 'music-production files'
MAX_RECORD = 64_000_000  # the largest record read, as a project file's limit (model.load_project)


def escape_unprintable():
    """Make a script print a character its output cannot encode as an escape (喆 as \\u5586), not stop on it.  On
    Windows, Python writes to a pipe or a file, as an agent reads a script's output, in the ANSI code page (Python
    documentation, sys.stdout), and a folder or piece name can hold a character that page lacks: 喆 and 堃 are not in
    code page 950, Traditional Chinese Windows' (Python's cp950 codec).  stderr already escapes so (Python gives it the
    backslashreplace handler); this does the same for stdout."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors='backslashreplace')


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
def staged(dest, mode='wb', encoding=None):
    """Write `dest` whole: yields a file opened on a new name of its own beside it; on success that file takes the
    destination's place (os.replace swaps the name, so a hard link at the destination is never written through), on
    any failure it is removed."""
    dest = Path(dest)
    fd, name = tempfile.mkstemp(dir=dest.parent, prefix=f'.{dest.name}.', suffix='.part')
    try:
        with os.fdopen(_opened(fd), mode, encoding=encoding) as f:
            yield f
        os.replace(name, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(name)
        raise


@contextlib.contextmanager
def staged_path(dest, suffix='.part'):
    """As staged, for code that writes a path itself: yields the new file's path; on success it takes the destination's
    place, on any failure it is removed."""
    temp = stage_name(dest, suffix)
    try:
        yield temp
        os.replace(temp, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise


def write_json(path, value):
    with staged(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def _record_value(record):
    """What a record the tools wrote holds (a regular files.json of this kind), or None."""
    if not regular_file(record) or lstat(record).st_size > MAX_RECORD:
        return None
    try:
        value = json.loads(Path(record).read_text(encoding='utf-8'))
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
    folder = Path(folder)
    moved = aside(folder / RECORD) if occupied(folder / RECORD) and not is_record(folder / RECORD) else None
    listed = recorded(folder)
    for p in paths:
        p = Path(p)
        p = p if p.is_absolute() else folder / p
        s = lstat(p)
        if s is not None and stat.S_ISREG(s.st_mode) and not linked(p) and p.name != RECORD:
            listed[p.relative_to(folder).as_posix()] = [s.st_size, s.st_mtime_ns]
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


def register_tree(folder, skip=(), since_ns=None, keep=None):
    """Record every file under `folder` (but the folders in `skip`, which keep their own records).  With `since_ns`, a
    file is recorded only if it was written from then on or `keep` (an earlier record) listed it: a folder a run
    resumes may hold files that run did not write."""
    folder = Path(folder)
    paths = []
    for p in tree(folder, skip):
        if p.name == RECORD:
            continue
        if since_ns is not None and lstat(p).st_mtime_ns < since_ns:
            entry = (keep or {}).get(p.relative_to(folder).as_posix())
            if entry is None or not unchanged(p, entry):
                continue  # not written by this run, nor listed unchanged before it: changed since, it is not the tools'
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
            os.replace(path, other)
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
    os.replace(src, dest)
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
