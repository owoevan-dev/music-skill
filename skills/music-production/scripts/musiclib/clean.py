"""List, or remove, what a piece's finished work no longer uses: its render and round folders other than those kept,
its auditions' renders and own caches, and the cache entries the kept renders do not use.

Ableton Live keeps decoded and analysed audio in a cache whose older files are deleted to make room, and its Cleanup
deletes the cache files the open Set does not use (Live Reference Manual, Managing Files and Sets).  Here the kept
renders play that Set's part: usually the final render and the round before it.

It is the one command that deletes, so it errs toward keeping (musiclib.files):

- Nothing is removed without `remove` (studio.py clean --remove): by default it lists what it would remove, as git
  clean refuses to delete without -f and lists with --dry-run (git-clean(1)).
- A folder counts only when the record a tool writes there shows that tool made it: a regular file, not a link, with
  that tool's contents (render_input.json, round.json, audition.json; a cache entry named by its key, with its
  receipt).  A file's name alone proves nothing.
- Inside such a folder only the files its record `files.json` lists, unchanged since the tools wrote them, are removed,
  as a build tool's clean removes only the outputs its build log lists (Ninja manual, the clean tool): a listening copy
  or notes put there stay, and the folder with them, and are listed.  A folder made before the tools kept that record
  is left alone.  The records go last, when nothing else stays.
- Only the kept renders' piece: a render, round or audition of another piece (another title, and for a round another
  project file) is left alone and listed, also inside a folder that goes; so is one whose piece cannot be read.
- A cache entry goes only from a cache folder the kept renders use, only if it holds nothing but what renders write
  there, and under its lock (render.entry_lock), so a render never loses an entry it is using.
- A finished audition keeps its audition.mp3 and audition.json; its version renders and own cache go.
- Links are never followed or removed; a folder or a --keep given as a link is refused."""
import json
import os
import re
from contextlib import suppress
from pathlib import Path

from . import files
from .files import linked, real_folder as _folder, regular_file as _file

DEPTH = 4  # piece/round/render; piece/audition/version/render; piece/cache/entry
HEX64 = re.compile(r'[0-9a-f]{64}')
ROUND, AUDITION = 'music-production round', 'music-production audition'  # the `kind` round.json and audition.json hold
# What names a folder's tool and its piece: they go last, with files.json, once nothing else in the folder stays, so a
# folder a clean leaves in part (a file held open, a file of the user's) is still recognised by the next.
TOP_RECORDS = ('render_input.json', 'project.json', 'round.json', 'audition.json')
AUDITION_KEEPS = ('audition.mp3', 'audition.json')  # what a finished audition is for: the A/B and its report
# What renders write in a cache entry (render.make_stem, audio.fluidsynth, layered, surge), and temporary files a stopped
# run may leave there: an entry holding anything else is left alone.
ENTRY_FILES = re.compile(r'(raw\.wav|receipt\.json|stem\.wav|stem\.json|entry\.lock|synth\.mid|surge\.mid|surge_job\.json|'
                         r'surge\.log|surge\.json|patch_at_tempo\.fxp|layered\.json|(take|pass)_\d+_\d+\.(mid|wav)|'
                         r'[A-Za-z0-9_.-]+\.(log|process\.json)|\.[^/\\]+\.part|stem\.new\.wav|stem\.\d+\.\d+\.(wav|json)|'
                         r'[A-Za-z0-9_.-]+\.json(\.\d+\.\d+)?\.tmp)')


def _record(path):
    """The JSON object in a regular file, or None."""
    if not _file(path) or files.lstat(path).st_size > files.MAX_RECORD:
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


def unit(folder):
    """(kind, record) of a folder a tool made: a round, a render or an audition; None otherwise."""
    for kind, read in (('round', round_record), ('render', render_record), ('audition', audition_record)):
        r = read(folder)
        if r is not None:
            return kind, r
    return None


def _title(project_file):
    r = _record(project_file)
    return r['title'] if r and isinstance(r.get('title'), str) else None


def piece(folder, kind, record):
    """(title, project file) of the piece a render, round or audition folder was made of; None for what is not known.
    A project file a record names relative to its folder is read from there."""
    folder = Path(folder)
    own = record.get('title') if isinstance(record.get('title'), str) else None
    if kind == 'render':
        held = round_record(folder.parent) if folder.name == 'render' else None
        if held is not None:
            return piece(folder.parent, 'round', held)  # a round's render is of the round's piece
        return _title(folder / 'project.json'), None
    if kind == 'round':
        project = record.get('project') if isinstance(record.get('project'), str) else None
        if project is not None:
            project = os.path.normcase(os.path.normpath(folder / project))
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


def _plan(folder, kind, record, inner):
    """What removing a tool's folder takes: its own files that a record (its own, or a sub-folder's such as a round's
    review/) lists unchanged, and what stays.  `inner` are the tool folders inside it, which go or stay on their own."""
    folder = Path(folder)
    finished = kind == 'audition' and record.get('status', 'PASS') != 'FAIL' and _file(folder / 'audition.mp3')
    skip = set(inner) | ({folder / 'cache'} if kind == 'audition' else set())
    records = {}
    take, stay, size = [], [], 0
    for p in files.tree(folder, skip):
        if p.name == files.RECORD or (p.parent == folder and p.name in TOP_RECORDS):
            continue  # the records go last, when nothing else stays
        if finished and p.parent == folder and p.name in AUDITION_KEEPS:
            stay.append(p)
            continue
        holder = folder  # the nearest folder with a record: a sub-folder's (a round's review/) or the tool folder's own
        for h in p.parents:
            if h == folder:
                break
            if files.has_record(h):
                holder = h
                break
        listed = records.setdefault(holder, files.recorded(holder))
        entry = listed.get(p.relative_to(holder).as_posix())
        if entry is not None and files.unchanged(p, entry):
            take.append(p)
            size += files.lstat(p).st_size
        else:
            stay.append(p)
    return {'kind': kind, 'take': take, 'stay': stay, 'bytes': size, 'inner': inner}


def _empty_folders(folder, skip):
    """Remove the folders under `folder` (deepest first, not following links, not entering `skip`) left empty."""
    for base, dirs, names in sorted(os.walk(folder, followlinks=False), key=lambda w: -len(Path(w[0]).parts)):
        base = Path(base)
        if base == folder or base in skip or any(s in base.parents for s in skip) or not _folder(base):
            continue
        with suppress(OSError):
            os.rmdir(base)


def _remove_entry(entry, report, rel):
    """A cache entry, under its lock: its files but the lock, then (the lock released) the lock file and the folder.  A
    render waiting for the lock finds the entry gone and takes it afresh (render.entry_lock)."""
    from .render import entry_lock
    with entry_lock(entry, wait=False, create=False) as free:
        if not free:
            report['not_removed'].append({'kind': 'cache entry', 'path': rel(entry), 'error': 'a render is using it'})
            return False
        for p in entry.iterdir():
            if p.name != 'entry.lock':
                p.unlink()
        if os.name != 'nt':
            (entry / 'entry.lock').unlink()  # an open file can be unlinked on POSIX; a waiting render then starts afresh
    with suppress(OSError):
        (entry / 'entry.lock').unlink()
    with suppress(OSError):
        entry.rmdir()  # stays if a render has started on it meanwhile
    return True


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
    rel = lambda f: Path(f).relative_to(root).as_posix()
    units = {f: u for f in folders for u in [unit(f)] if u}
    caches = {f.parent for f in folders if f.name in used and entry_record(f)}
    listed, left = {}, []
    for f, (kind, record) in units.items():
        if any(f == p or p in f.parents or f in p.parents for p in protected):
            continue  # a kept render, its round, what they hold, and the folders holding them
        title, project = piece(f, kind, record)
        if not ((title is not None and title in titles) or (project is not None and project in projects)):
            why = 'its piece cannot be read' if title is None and project is None else 'another piece'
            left.append({'kind': kind, 'path': rel(f), 'title': title, 'why': why})
        elif not files.has_record(f):
            left.append({'kind': kind, 'path': rel(f), 'title': title,
                         'why': 'no record of the files the tools wrote in it (made before 0.4.0); remove it by hand if you want'})
        else:
            listed[f] = (kind, record)
    plans = {f: _plan(f, kind, record, [u for u in units if u != f and f in u.parents]) for f, (kind, record) in listed.items()}
    report = {'folder': str(root), 'kept': [str(k[0]) for k in kept], 'cache_entries_kept': len(used), 'dry_run': not remove,
              'listed': [], 'bytes': 0, 'left_alone': left, 'not_removed': []}
    # Cache entries first: an audition's own cache must be empty before its folder can go.
    entries = [f for f in folders if f.parent in caches and f.name not in used and entry_record(f)]
    entries += [e for f, (kind, _) in listed.items() if kind == 'audition' and _folder(f / 'cache')
                for e in sorted((f / 'cache').iterdir()) if _folder(e) and entry_record(e)]
    cleared = set()  # the cache entries that go (or would go, in a dry run)
    for e in entries:
        contents = list(e.iterdir())
        if any(linked(p) or not _file(p) or not ENTRY_FILES.fullmatch(p.name) for p in contents):
            report['left_alone'].append({'kind': 'cache entry', 'path': rel(e), 'title': None,
                                         'why': 'it holds files renders do not write there'})
            continue
        size = sum(files.lstat(p).st_size for p in contents)
        if remove and not _remove_entry(e, report, rel):
            continue
        cleared.add(e)
        report['listed'].append({'kind': 'cache entry', 'path': rel(e), 'bytes': size, 'whole': True, 'kept_inside': []})
        report['bytes'] += size
    failed = set()

    def own_cache_goes(f):
        """An audition's own cache is gone, or every folder in it is an entry that goes."""
        c = f / 'cache'
        return not files.occupied(c) or (_folder(c) and all(e in cleared for e in c.iterdir()))

    def whole(f):
        """A listed folder goes whole when nothing of its own stays and every tool folder inside it goes whole."""
        return (f in plans and f not in failed and not plans[f]['stay'] and all(whole(u) for u in plans[f]['inner'])
                and (plans[f]['kind'] != 'audition' or own_cache_goes(f)))
    # Deepest first, so that a round's render is gone before the round is looked at.
    for f in sorted(plans, key=lambda f: -len(f.parts)):
        plan = plans[f]
        skip = set(plan['inner']) | ({f / 'cache'} if plan['kind'] == 'audition' else set())
        if remove:
            try:
                for p in plan['take']:
                    p.unlink()
                if plan['kind'] == 'audition':
                    with suppress(OSError):
                        (f / 'cache').rmdir()  # an audition's own cache, once its entries are gone
                _empty_folders(f, skip)
                goes_whole = whole(f) and not files.occupied(f / 'cache') if plan['kind'] == 'audition' else whole(f)
                if goes_whole:
                    for p in files.tree(f, skip):
                        p.unlink()  # what is left is the records: every other file went above
                    _empty_folders(f, set())
                    f.rmdir()
            except OSError as e:
                # A file another program holds open: the rest stays, its records with it, and the folder is named.
                failed.add(f)
                report['not_removed'].append({'kind': plan['kind'], 'path': rel(f), 'error': str(e)})
                continue
        else:
            goes_whole = whole(f)
        report['listed'].append({'kind': plan['kind'], 'path': rel(f), 'bytes': plan['bytes'], 'whole': goes_whole,
                                 'kept_inside': [p.relative_to(root).as_posix() for p in plan['stay']][:20]})
        report['bytes'] += plan['bytes']
    return report


def describe(report):
    kinds = {}
    for r in report['listed']:
        n, b = kinds.get(r['kind'], (0, 0))
        kinds[r['kind']] = (n + 1, b + r['bytes'])
    plural = {'render': 'renders', 'round': 'rounds', 'audition': 'auditions', 'cache entry': 'cache entries'}
    what = ', '.join(f'{n} {k if n == 1 else plural[k]} ({b / 1e9:.2f} GB)' for k, (n, b) in kinds.items()) or 'nothing'
    verb = 'Would remove' if report['dry_run'] else 'Removed'
    lines = [f'{verb} {what} from {report["folder"]}: {report["bytes"] / 1e9:.2f} GB in all.',
             'Kept: ' + '; '.join(report['kept']) + f'; the {report["cache_entries_kept"]} cache entries they use.']
    for r in report['listed'][:20]:
        part = '' if r['whole'] else ' (in part: ' + ', '.join(r['kept_inside'][:5]) + (' and more' if len(r['kept_inside']) > 5 else '') + ' stay, not written by the tools)'
        lines.append(f'- {r["kind"]}: {r["path"]} ({r["bytes"] / 1e6:.0f} MB){part}')
    if len(report['listed']) > 20:
        lines.append(f'- and {len(report["listed"]) - 20} more')
    if report['left_alone']:
        lines.append(f'Left alone ({len(report["left_alone"])}): ' + '; '.join(
            f'{x["kind"]} {x["path"]} ({x["why"]}{": " + repr(x["title"]) if x.get("title") else ""})' for x in report['left_alone'][:10])
            + (f'; and {len(report["left_alone"]) - 10} more' if len(report['left_alone']) > 10 else ''))
    for r in report['not_removed']:
        lines.append(f'Not removed, {r["kind"]} {r["path"]}: {r["error"]} (close what holds it open and run clean again)')
    if report['dry_run'] and report['listed']:
        lines.append('Nothing was removed: check the list, then run the same command with --remove.')
    return '\n'.join(lines)
