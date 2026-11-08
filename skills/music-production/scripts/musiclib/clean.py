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
  is left alone.  The records go last, when nothing else stays (a sub-folder's, such as a round's review/, when
  nothing else stays in it), and a file is a record by what it holds: a file of the user's named files.json stays.
- Only the kept renders' piece: a render, round or audition of another piece (another title, and for a round another
  project file) is left alone and listed, also inside a folder that goes; so is one whose piece cannot be read.
- A cache entry goes only from a cache folder the kept renders use, only if it holds nothing but what renders write
  there, and under its lock (render.entry_lock), so a render never loses an entry it is using.
- A render, round or audition at work holds its folder's lock (files.working), and clean takes the same lock on each
  folder it would remove from before it looks inside, keeping it until that folder is done: a folder in use, or inside
  one in use, is left alone and named, and no run starts in a folder while clean removes from it.  Each file is looked
  at again just before it goes, and one changed since stays.
- A finished audition keeps its audition.mp3 and audition.json; its version renders and own cache go.
- Links are never followed or removed; a folder or a --keep given as a link is refused."""
import json
import os
import re
from contextlib import suppress
from pathlib import Path

from . import files
from .files import linked, real_folder as _folder, regular_file as _file

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
                         r'[A-Za-z0-9_.-]+\.json(\.\d+\.\d+)?\.tmp|'
                         # a file a stopped render was writing under a name of its own (files.stage_name: mkstemp's
                         # eight characters), kept stems' copies among them (found by GPT Pro's third review)
                         r'\.[A-Za-z0-9_.-]+\.[a-z0-9_]{8}\.(wav|mid|copy))')


def _record(path, limit=None):
    """The JSON object in a regular file, or None."""
    if not _file(path) or files.lstat(path).st_size > (limit or files.MAX_RECORD):
        return None
    try:
        value = files.loads(Path(path).read_text(encoding='utf-8'))
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
    r = _record(project_file, files.MAX_PROJECT)  # a render's copy of its project, as large as a project may be
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


def _folders(root):
    """Every folder under `root`, however deep, without following links: what clean finds is what its plans may walk,
    so a tool's folder deeper than it looked (it looked four levels down) is never taken as plain files of the folder
    holding it, and keeps its own piece, record and lock (found by GPT Pro's third review of 0.4.0)."""
    return [f for f in files.real_folders(root) if f != root]


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
    seen = lambda p: [files.lstat(p).st_size, files.lstat(p).st_mtime_ns]  # a record as the plan found it
    skip = set(inner) | ({folder / 'cache'} if kind == 'audition' else set())
    records = {folder: files.recorded(folder)}
    take, stay, size, holders, last = [], [], 0, [], []
    for p in files.tree(folder, skip):
        if p.parent == folder and files.is_lock_file(p):
            continue  # the folder's work lock, which clean holds: it goes with the folder (files.release)
        # The records go last, when nothing else stays: the tools' files.json, and at the top what names the folder's
        # tool and piece as its record lists it, unchanged.  A file is no record by its name: a file of the user's so
        # named, or one changed since, stays.
        if files.is_record(p):
            if p.parent != folder:
                holders.append(p.parent)  # a sub-folder's own record (a round's review/): it goes once nothing else is there
            last.append((p, seen(p)))
            continue
        own = records[folder].get(p.name) if p.parent == folder and p.name in TOP_RECORDS else None
        if own is not None and files.unchanged(p, own):
            last.append((p, seen(p)))
            continue
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
            take.append((p, entry))
            size += files.lstat(p).st_size
        else:
            stay.append(p)
    # A link inside it (a symbolic link, a junction) is nothing the tools wrote: it stays, never followed, and the
    # folder with it.  (files.tree does not list links.)
    stay += [p for p in files.links_in(folder) if not any(s == p or s in p.parents for s in skip)]
    # What an audition's own cache holds besides its entries (a file of the user's put there) stays, and is named:
    # the cache is left out of the walk above.  (Found by GPT Pro's third review.)
    if kind == 'audition' and _folder(folder / 'cache'):
        stay += [c for c in sorted((folder / 'cache').iterdir()) if not (_folder(c) and entry_record(c))]
    return {'kind': kind, 'take': take, 'stay': stay, 'bytes': size, 'inner': inner, 'holders': holders, 'last': last}


def _empty_folders(folder, skip, holders=()):
    """Remove the folders under `folder` (deepest first, not following links, not entering `skip`) left empty, and
    those of `holders` (sub-folders with a record of their own) left holding nothing but that record."""
    for base in sorted(files.real_folders(folder, skip), key=lambda b: -len(b.parts)):
        if base == folder:
            continue
        with suppress(OSError):
            if base in holders and [p.name for p in base.iterdir()] == [files.RECORD] and files.is_record(base / files.RECORD):
                (base / files.RECORD).unlink()
            os.rmdir(base)


def _remove_entry(entry, report, rel):
    """A cache entry, under its lock: its files but the lock, then the lock file and the folder.  A render waiting for
    the lock finds the entry gone and takes it afresh (render.entry_lock).  The lock file is removed only where no
    render can hold another by that name: on POSIX by its holder, under the lock (an open file can be unlinked, and a
    render that then opens the name makes a new file, its own lock); on Windows, which cannot remove a file a process
    holds open, once it is released, so a render that has opened it since keeps it.  Removing the name on POSIX after
    the release could take away a new lock a render had just made there."""
    from .render import entry_lock
    with entry_lock(entry, wait=False, create=False) as free:
        if not free:
            report['not_removed'].append({'kind': 'cache entry', 'path': rel(entry), 'error': 'a render is using it'})
            return False
        # The receipt last and the raw synthesis before it: stopped part way by a file another program holds open,
        # the entry keeps what a render can still use, or what it makes again, and is named; the clean goes on.
        try:
            for p in sorted(entry.iterdir(), key=lambda p: (p.name == 'raw.wav') + 2 * (p.name == 'receipt.json')):
                if p.name != 'entry.lock':
                    p.unlink()
            if os.name != 'nt':
                (entry / 'entry.lock').unlink()
        except OSError as e:
            report['not_removed'].append({'kind': 'cache entry', 'path': rel(entry), 'error': str(e)})
            return False
    if os.name == 'nt':
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
            used |= {r['cache_key'] for r in files.loads(receipts.read_text(encoding='utf-8')) if isinstance(r, dict) and 'cache_key' in r}
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
                         'why': 'no record of the files the tools wrote in it (made before 0.4.0, or by a run killed before it '
                                'wrote one); remove it by hand if you want'})
        else:
            listed[f] = (kind, record)
    held, busy = _hold(units, listed, remove)
    try:
        for f, why in busy.items():
            kind, record = listed.pop(f)
            left.append({'kind': kind, 'path': rel(f), 'title': piece(f, kind, record)[0], 'why': why})
        return _remove(root, kept, used, folders, units, caches, listed, left, held, remove, rel)
    finally:
        for f, fd in held.items():  # the folders holding listed ones, and any a failure left held
            files.release(f, fd)


def _hold(units, listed, remove):
    """Take the work lock (files.take) of each listed folder and of the tool folders holding one, and keep them while
    clean removes: returns ({folder: its lock, held}, {listed folder: why it stays}).  A folder holding a listed one
    stays held to the end, so no run starts in it while clean removes inside it (it was looked at and let go; found by
    GPT Pro's third review of 0.4.0).  A dry run only looks, and lets go at once."""
    held, busy = {}, {}
    for f in sorted(units, key=lambda f: len(f.parts)):  # a folder before those inside it
        if f not in listed and not any(f in u.parents for u in listed):
            continue
        above = next((why for u, why in busy.items() if u in f.parents), None)
        if above is not None:
            busy[f] = above
            continue
        state, fd = files.take(f, create=remove)
        if state == 'held' and remove:
            held[f] = fd
        elif state == 'held':
            files.let_go(fd)
        elif state == 'busy':
            busy[f] = 'a render, round or audition is working in it; run clean again once it has finished'
        elif state == 'unlockable':
            busy[f] = ('its work lock cannot be taken (the drive cannot lock files, or its work.lock is no lock file), '
                       'so clean cannot tell whether a run is using it; remove it by hand when none is')
    return held, {f: why for f, why in busy.items() if f in listed}


def _remove(root, kept, used, folders, units, caches, listed, left, held, remove, rel):
    """The listed folders' plans, and with `remove` their removal, each folder under its lock (`held`), which is let
    go as soon as that folder is done."""
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
        if not remove and files.take(e, create=False, name='entry.lock')[0] == 'busy':
            # The dry run looks at the entry's lock as --remove takes it, creating nothing: one a render holds stays.
            report['not_removed'].append({'kind': 'cache entry', 'path': rel(e), 'error': 'a render is using it'})
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
                for p, entry in plan['take']:
                    if files.unchanged(p, entry):  # still as the plan found it
                        p.unlink()
                    else:
                        plan['stay'].append(p)  # changed since: it stays, and the folder with it
                        plan['bytes'] -= entry[0]
                if plan['kind'] == 'audition':
                    with suppress(OSError):
                        (f / 'cache').rmdir()  # an audition's own cache, once its entries are gone
                _empty_folders(f, skip, plan['holders'])
                goes_whole = whole(f) and not files.occupied(f / 'cache') if plan['kind'] == 'audition' else whole(f)
                if goes_whole:
                    # The records the plan named, and nothing found anew: a file that appeared since keeps the folder,
                    # which is then named as not removed.  Each must still be as the plan found it (a command writing
                    # into the folder meanwhile records its file there): one changed keeps them all, and the folder.
                    for p, was in plan['last']:
                        if files.occupied(p) and not files.unchanged(p, was):
                            raise OSError(f'{p.relative_to(f).as_posix()} changed while clean ran; the folder stays with its records')
                    for p, _ in plan['last']:
                        if files.regular_file(p):
                            p.unlink()
                    _empty_folders(f, set())
                    files.release(f, held.pop(f))  # its lock file goes last, then the folder
                    f.rmdir()
            except OSError as e:
                # A file another program holds open: the rest stays, its records with it, and the folder is named.
                failed.add(f)
                report['not_removed'].append({'kind': plan['kind'], 'path': rel(f), 'error': str(e)})
                continue
            finally:
                if f in held:
                    files.release(f, held.pop(f))
        else:
            goes_whole = whole(f)
        # What stays: its own files no tool recorded (or changed since), and the folders inside it that stay.
        stays = [p.relative_to(root).as_posix() for p in plan['stay']] + [rel(u) + '/' for u in plan['inner'] if not whole(u)]
        report['listed'].append({'kind': plan['kind'], 'path': rel(f), 'bytes': plan['bytes'], 'whole': goes_whole,
                                 'kept_inside': stays[:20]})
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
        part = '' if r['whole'] else ' (in part: ' + ', '.join(r['kept_inside'][:5]) + (' and more' if len(r['kept_inside']) > 5 else '') + ' stay)'
        lines.append(f'- {r["kind"]}: {r["path"]} ({r["bytes"] / 1e6:.0f} MB){part}')
    if len(report['listed']) > 20:
        lines.append(f'- and {len(report["listed"]) - 20} more')
    if report['left_alone']:
        lines.append(f'Left alone ({len(report["left_alone"])}): ' + '; '.join(
            f'{x["kind"]} {x["path"]} ({x["why"]}{": " + repr(x["title"]) if x.get("title") else ""})' for x in report['left_alone'][:10])
            + (f'; and {len(report["left_alone"]) - 10} more' if len(report['left_alone']) > 10 else ''))
    for r in report['not_removed']:
        lines.append(f'Not removed, {r["kind"]} {r["path"]}: {r["error"]} (close what holds it open and run clean again)')
    if any(not r['whole'] for r in report['listed']):
        lines.append('A folder listed "in part" keeps what the tools did not write there, or that changed since, and the '
                     'folders inside it that stay; its records stay with them.')
    if report['dry_run'] and report['listed']:
        lines.append('Nothing was removed: check the list, then run the same command with --remove.')
    return '\n'.join(lines)
