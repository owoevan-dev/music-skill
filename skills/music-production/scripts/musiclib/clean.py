"""List, or remove, what a piece's finished work no longer uses: its render and round folders other than those kept,
its auditions' renders and own caches, and the cache entries the kept renders do not use.

Ableton Live keeps decoded and analysed audio in a cache whose older files are deleted to make room, and its Cleanup
deletes the cache files the open Set does not use (Live Reference Manual, Managing Files and Sets).  Here the kept
renders play that Set's part: usually the final render and the round before it.

It is the one command that deletes, so it errs toward keeping:

- Nothing is removed without `remove` (studio.py clean --remove): by default it lists what it would remove, as git
  clean refuses to delete without -f and lists with --dry-run (git-clean(1)).
- A folder goes only when the record one of the tools writes there shows that tool made it: a regular file, not a
  link, holding that record, never a file's name alone.
  - a render folder: render_input.json, the SHA-256 of the project and of the renderer;
  - a round's folder: round.json, the record studio.py round writes (its review and render go with it);
  - an audition's own cache: the cache folder beside audition.json, the record studio.py audition writes;
  - a cache entry: a folder named by its key, with receipt.json naming that key and raw.wav.
- Only the kept renders' piece: a render, round or audition of another piece (another title, and for a round another
  project file) is left alone and listed, and so is one whose piece cannot be read.  Cache entries go only from a cache
  folder the kept renders use, and not one a running render holds (its entry lock).
- Links are never followed or removed: a symbolic link, a junction or another reparse point that names a different
  place, tested without following it on every Python the skill runs on (Path.is_junction exists only from 3.12); a
  folder or a --keep given as a link is refused."""
import json
import os
import re
import shutil
import stat
from pathlib import Path

DEPTH = 4  # piece/round/render; piece/audition/version/render; piece/cache/entry
# Microsoft, Reparse Point Tags: a tag with this bit set (IsReparseTagNameSurrogate) names another place in the file
# system, as a symbolic link's and a junction's (mount point's) do.
NAME_SURROGATE = 0x20000000
HEX64 = re.compile(r'[0-9a-f]{64}')
ROUND, AUDITION = 'music-production round', 'music-production audition'  # the `kind` round.json and audition.json hold
MAX_RECORD = 64_000_000  # the largest record read, as a project file's limit (load_project)


def _lstat(path):
    try:
        return os.lstat(path)
    except OSError:
        return None


def linked(path):
    """A symbolic link, a junction or another reparse point that names a different place, read without following it."""
    s = _lstat(path)
    if s is None:
        return False
    if stat.S_ISLNK(s.st_mode):
        return True
    return bool(getattr(s, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                and getattr(s, 'st_reparse_tag', 0) & NAME_SURROGATE)


def _folder(path):
    """A real folder, not a link to one."""
    s = _lstat(path)
    return s is not None and stat.S_ISDIR(s.st_mode) and not linked(path)


def _file(path):
    """A regular file, not a link to one."""
    s = _lstat(path)
    return s is not None and stat.S_ISREG(s.st_mode) and not linked(path)


def _record(path):
    """The JSON object in a regular file, or None."""
    if not _file(path) or _lstat(path).st_size > MAX_RECORD:
        return None
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def render_record(folder):
    """render_input.json as render writes it, or None."""
    r = _record(Path(folder) / 'render_input.json')
    ok = r and all(isinstance(r.get(k), str) and HEX64.fullmatch(r[k]) for k in ('project_sha256', 'renderer_sha256'))
    return r if ok else None


def round_record(folder):
    """round.json as studio.py round writes it, or None (rounds made before `kind` was written hold the same keys)."""
    r = _record(Path(folder) / 'round.json')
    if not r:
        return None
    same_keys = (r.get('review') == 'review/score_review.json' and r.get('render') == 'render/report.json'
                 and isinstance(r.get('status'), str) and isinstance(r.get('seconds'), dict))
    return r if r.get('kind') == ROUND or same_keys else None


def audition_record(folder):
    """audition.json as studio.py audition writes it, or None (earlier ones have no `kind`, the same keys)."""
    r = _record(Path(folder) / 'audition.json')
    if not r:
        return None
    same_keys = isinstance(r.get('versions'), list) and isinstance(r.get('bars'), list) and 'track' in r and 'each_seconds' in r
    return r if r.get('kind') == AUDITION or same_keys else None


def entry_record(folder):
    """A cache entry's receipt: its folder is named by its key, receipt.json names that key, raw.wav is there."""
    folder = Path(folder)
    if not HEX64.fullmatch(folder.name) or not _file(folder / 'raw.wav'):
        return None
    r = _record(folder / 'receipt.json')
    return r if r and r.get('key') == folder.name else None


def _title(project_file):
    r = _record(project_file)
    return r['title'] if r and isinstance(r.get('title'), str) else None


def piece(folder, kind, record):
    """(title, project file) of the piece a render, round or audition folder was made of; None for what is not known."""
    folder = Path(folder)
    own = record.get('title') if isinstance(record.get('title'), str) else None
    if kind == 'render':
        return _title(folder / 'project.json'), None
    if kind == 'round':
        project = record.get('project') if isinstance(record.get('project'), str) else None
        return own or _title(folder / 'render' / 'project.json'), project
    versions = sorted(v for v in folder.glob('[0-9][0-9]_*') if _folder(v))
    return own or next((t for t in (_title(v / 'song.json') for v in versions) if t), None), None


def _folders(root, depth=DEPTH):
    """Every folder under `root` to `depth` levels, without following links."""
    found, level = [], [root]
    for _ in range(depth):
        nxt = []
        for folder in level:
            try:
                children = [c for c in folder.iterdir() if _folder(c)]
            except OSError:
                continue
            found += children
            nxt += children
        level = nxt
    return found


def _size(path):
    total = 0
    for base, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if _folder(Path(base) / d)]
        total += sum(s.st_size for s in (_lstat(Path(base) / f) for f in files) if s is not None and stat.S_ISREG(s.st_mode))
    return total


def _kept(path):
    """(render folder, its round's folder or None, title, project file) of a --keep: a render folder or a round's."""
    given = Path(path)
    if linked(given):
        raise ValueError(f'--keep {path} is a link; give the folder itself (clean never follows links)')
    folder = given.resolve()
    rnd = round_record(folder)
    render_dir, round_dir = (folder / 'render', folder) if rnd else (folder, None)
    if not _folder(render_dir) or render_record(render_dir) is None:
        raise ValueError(f'--keep {path}: not a render or round folder (no render_input.json written by render)')
    if rnd is None and round_record(folder.parent):
        round_dir, rnd = folder.parent, round_record(folder.parent)  # the render inside a round's folder
    title, project = piece(round_dir, 'round', rnd) if rnd else (None, None)
    return render_dir, round_dir, title or _title(render_dir / 'project.json'), project


def clean(folder, keep, remove=False):
    given = Path(folder)
    if linked(given):
        raise ValueError(f'{folder} is a link; give the folder itself (clean never follows links)')
    root = given.resolve()
    if not _folder(root):
        raise ValueError(f'{folder} is not a folder')
    if not keep:
        raise ValueError('Name what stays with --keep: the final render and the previous round (render or round folders)')
    kept = [_kept(k) for k in keep]
    for render_dir, round_dir, _, _ in kept:
        if root not in render_dir.parents:
            raise ValueError(f'--keep {render_dir} is not inside {root}')
    titles = {t for _, _, t, _ in kept if t}
    projects = {pr for _, _, _, pr in kept if pr}
    used = set()
    for render_dir, _, _, _ in kept:
        receipts = render_dir / 'stem_receipts.json'
        if _file(receipts):
            used |= {r['cache_key'] for r in json.loads(receipts.read_text(encoding='utf-8')) if isinstance(r, dict) and 'cache_key' in r}
    protected = {k[0] for k in kept} | {k[1] for k in kept if k[1]}
    folders = _folders(root)
    # The piece's caches: the folders holding an entry a kept render uses.
    caches = {f.parent for f in folders if f.name in used and entry_record(f)}
    rel = lambda f: str(f.relative_to(root))
    listed, left = [], []
    for f in folders:
        if any(f == p or p in f.parents or f in p.parents for p in protected):
            continue  # a kept render, its round, what they hold, and the folders holding them
        rnd = round_record(f)
        made = rnd or render_record(f)
        if made is not None:
            kind = 'round' if rnd is not None else 'render'
            title, project = piece(f, kind, made)
            if (title is not None and title in titles) or (project is not None and project in projects):
                listed.append((kind, f))
            else:
                left.append({'kind': kind, 'path': rel(f), 'title': title,
                             'why': 'its piece cannot be read' if title is None and project is None else 'another piece'})
            continue
        heard = audition_record(f)
        if heard is not None and _folder(f / 'cache'):
            title, _ = piece(f, 'audition', heard)
            if title is not None and title in titles:
                listed.append(('audition cache', f / 'cache'))
            else:
                left.append({'kind': 'audition cache', 'path': rel(f / 'cache'), 'title': title,
                             'why': 'its piece cannot be read' if title is None else 'another piece'})
        elif f.parent in caches and f.name not in used and entry_record(f):
            listed.append(('cache entry', f))
    # A folder inside one already listed goes with it; one inside a folder left alone stays with it.
    outer = [f for _, f in listed]
    spared = [root / x['path'] for x in left]
    listed = [(kind, f) for kind, f in listed if not any(o in f.parents for o in outer) and not any(s in f.parents for s in spared)]
    left = [x for x in left if not any(o in (root / x['path']).parents for o in outer + spared)]
    report = {'folder': str(root), 'kept': [str(k[0]) for k in kept], 'cache_entries_kept': len(used), 'dry_run': not remove,
              'listed': [], 'bytes': 0, 'left_alone': left, 'not_removed': []}
    for kind, f in listed:
        size = _size(f)
        if remove:
            if kind == 'cache entry':
                from .render import entry_lock
                with entry_lock(f, wait=False) as free:
                    pass
                if not free:
                    report['not_removed'].append({'kind': kind, 'path': rel(f), 'error': 'a render is using it'})
                    continue
            try:
                shutil.rmtree(f)  # Python 3.8+ removes a junction inside without entering it, as it does a link
            except OSError as e:
                # A file another program holds open: the folder stays (in part), is named, and the rest goes on.
                report['not_removed'].append({'kind': kind, 'path': rel(f), 'error': str(e)})
                continue
        report['listed'].append({'kind': kind, 'path': rel(f), 'bytes': size})
        report['bytes'] += size
    return report


def describe(report):
    kinds = {}
    for r in report['listed']:
        n, b = kinds.get(r['kind'], (0, 0))
        kinds[r['kind']] = (n + 1, b + r['bytes'])
    plural = {'render': 'renders', 'round': 'rounds', 'audition cache': 'audition caches', 'cache entry': 'cache entries'}
    what = ', '.join(f'{n} {k if n == 1 else plural[k]} ({b / 1e9:.2f} GB)' for k, (n, b) in kinds.items()) or 'nothing'
    verb = 'Would remove' if report['dry_run'] else 'Removed'
    lines = [f'{verb} {what} from {report["folder"]}: {report["bytes"] / 1e9:.2f} GB in all.',
             'Kept: ' + '; '.join(report['kept']) + f'; the {report["cache_entries_kept"]} cache entries they use.']
    lines += [f'- {r["kind"]}: {r["path"]} ({r["bytes"] / 1e6:.0f} MB)' for r in report['listed'][:20]]
    if len(report['listed']) > 20:
        lines.append(f'- and {len(report["listed"]) - 20} more')
    if report['left_alone']:
        lines.append(f'Left alone, not of the kept piece ({len(report["left_alone"])}): ' + '; '.join(
            f'{x["kind"]} {x["path"]} ({x["why"]}{": " + repr(x["title"]) if x.get("title") else ""})' for x in report['left_alone'][:10])
            + (f'; and {len(report["left_alone"]) - 10} more' if len(report['left_alone']) > 10 else ''))
    for r in report['not_removed']:
        lines.append(f'Not removed, {r["kind"]} {r["path"]}: {r["error"]} (close what holds it open and run clean again)')
    if report['dry_run'] and report['listed']:
        lines.append('Nothing was removed: check the list, then run the same command with --remove.')
    return '\n'.join(lines)
