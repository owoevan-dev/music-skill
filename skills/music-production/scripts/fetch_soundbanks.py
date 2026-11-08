"""Fetch, verify and configure the optional sound banks in references/soundbank-lock.json.

Archives come only from the locked official hosts and must match size and SHA-256; members are
listed before extraction and only the locked bank and notice files are written, then hashed.
The VSCO bank is rebuilt from individually verified sample files (git blob hashes of the pinned
commit) and must reproduce the locked output hash.  A split build (the University of Iowa recordings,
one chromatic run per file) fetches each locked file, checks its size and SHA-256 (recorded at
retrieval; the publisher lists none), cuts each note where the locked manifest records it, checks
every note's hash and must reproduce the locked output hash too.  A new configuration is written; nothing is
overwritten.

The banks built here are first sought as this project built them: an xz-compressed SF2 attached to the repository's
release (the lock's "prebuilt" section), checked by size and SHA-256 before it is opened and then by the build's
locked hash once unpacked, so it is byte for byte the bank a build from the sources gives.  If the release cannot be
reached or anything fails to match, the bank is built from its sources as above.  --from-source skips the prebuilt
banks; --prebuilt-from takes them from a local folder (a mirror or a copy) instead of the release.

Usage:
  python fetch_soundbanks.py --config local-config.json --runtime <dir> --output local-config.studio.json
         [--archive-cache <dir>] [--vsco-source <checkout or cache>] [--offline] [--only vcsl,rusty|orchestra,...]
         [--from-source] [--prebuilt-from <dir>] [--delete-sources]
--only takes bank names and the groups in the lock (orchestra, band, world, examples).  With --delete-sources, once
every requested bank is verified, what was downloaded to make them (archives, prebuilt assets, samples, recordings
and cut notes) is deleted; the banks stay, but installing one again downloads it again.
"""
import argparse
import contextlib
import fnmatch
import hashlib
import http.client
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from musiclib import files
from musiclib.model import file_hash, save_json

HOSTS = {'github.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com', 'raw.githubusercontent.com',
         'api.github.com', 'theremin.music.uiowa.edu'}
SKILL = Path(__file__).resolve().parents[1]
NUMPY_BUILD = '2.1.2'  # the NumPy the locked builds were made with

class Allowed(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to an allowed host over HTTPS, checked before the request is made."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        if parts.scheme != 'https' or parts.hostname not in HOSTS:
            fp.close()  # urllib closes the redirect's response only when it follows it
            raise ValueError('Redirect to a host that is not allowed: ' + newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

OPENER = urllib.request.build_opener(Allowed)

class Damaged(OSError):
    """A download that ended short or does not match what the lock expects: tried again like a dropped connection."""

def fetch(url, dest, size=None, max_bytes=2_000_000_000, tries=4, check=None):
    """Download `url` to `dest` through a .partial file, which becomes `dest` only when it is complete (its locked
    `size`, or the server's Content-Length) and passes `check` (a function of the file, e.g. its hash).  A dropped
    connection, a short or damaged file, a timeout or a server error is tried again after a pause (3, 6, 12 s); a
    refused host, a missing file or a size over the lock is not."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in HOSTS:
        raise ValueError('Host not allowed: ' + url)
    for attempt in range(tries):
        try:
            return _fetch_once(url, dest, size, max_bytes, check)
        except (OSError, http.client.HTTPException) as e:
            final = isinstance(e, urllib.error.HTTPError) and e.code < 500 and e.code != 429
            if final or attempt == tries - 1:
                raise
            print(f'retrying {url} after {type(e).__name__}', flush=True)
            time.sleep(3 * 2 ** attempt)

def _fetch_once(url, dest, size, max_bytes, check):
    """One download into a new file of its own beside `dest` (musiclib.files.staged_path), which takes `dest`'s place
    only when complete and checked, and is removed otherwise: two runs never share it."""
    req = urllib.request.Request(url, headers={'User-Agent': 'MusicProductionSkill/2.0'})
    with OPENER.open(req, timeout=120) as r:
        if urllib.parse.urlsplit(r.url).hostname not in HOSTS:
            raise ValueError('Unexpected redirect to ' + r.url)
        # A connection the server closes early ends the reads without an error: the length tells.
        announced = r.headers.get('Content-Length')
        expected = size if size is not None else int(announced) if announced and announced.isdigit() else None
        count = 0
        with files.staged_path(dest) as temp:
            with temp.open('wb') as out:
                while chunk := r.read(1 << 20):
                    count += len(chunk)
                    if count > (size or max_bytes):
                        raise ValueError('Download exceeds locked size')
                    out.write(chunk)
            if expected is not None and count != expected:
                raise Damaged(f'{url}: {count} of {expected} bytes arrived')
            if check and not check(temp):
                raise Damaged(f'{url}: the download does not match the lock')

def cached(url, dest, offline, size=None, check=None, max_bytes=2_000_000_000):
    """`dest` from an earlier run if it still passes `check`; otherwise (a file left damaged, or none) downloaded.  A
    file at `dest` that does not match is set aside, never removed (musiclib.files.aside): it may not be the
    installer's."""
    if files.occupied(dest):
        if files.regular_file(dest) and (size is None or dest.stat().st_size == size) and (check is None or check(dest)):
            return
        if offline:
            raise ValueError(f'Offline, and the cached {dest} does not match the lock')
        print(f'{dest.name}: the cached copy does not match the lock; set aside as {files.aside(dest).name}, downloading it again', flush=True)
    elif offline:
        raise ValueError('Offline cache missing ' + str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    fetch(url, dest, size, max_bytes, check=check)

def sha256_is(expected):
    return lambda path: file_hash(path) == expected

def safe_member(name):
    p = PurePosixPath(name)
    return not (p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name or '\0' in name)

def sample_digest(entries):
    """The SHA-256 the lock pins a source build's samples by: each file's path, git blob hash and size, one a line,
    sorted (`samples_sha256`)."""
    return hashlib.sha256(''.join(f'{p}\t{s}\t{n}\n' for p, s, n in sorted(entries)).encode('utf-8')).hexdigest()

def pinned_samples(item, tree):
    """The samples a build takes from its source listing, [(path, blob hash, size)], only when they are exactly the
    files the lock pins: the listing comes from the host, and a path in it decides where a download is written, so a
    listing that names other files, other paths (a folder's name followed by `..`), other hashes or sizes is refused
    before anything is fetched."""
    if not isinstance(tree.get('tree'), list) or tree.get('truncated'):
        raise ValueError(f'{item["name"]}: the source listing is incomplete')
    entries = [(e['path'], e.get('sha'), e.get('size')) for e in tree['tree']
               if isinstance(e, dict) and e.get('type') == 'blob' and isinstance(e.get('path'), str) and locked(e['path'], item['paths'])]
    if len(entries) != item['samples'] or sample_digest(entries) != item['samples_sha256']:
        raise ValueError(f'{item["name"]}: the source listing does not name the samples the lock pins; nothing was fetched')
    if not all(safe_member(p) for p, _, _ in entries):
        raise ValueError(f'{item["name"]}: the source listing names a path outside its folder')
    return entries

def archive_tool():
    """A reader for the .7z banks (LZMA-compressed): a libarchive tar built with liblzma (Windows 11's own tar.exe,
    macOS's tar, or bsdtar: on Linux, libarchive-tools), or else 7-Zip's 7z.  GNU tar cannot read 7z, and the
    tar.exe of Windows 10 lacks LZMA.  Returns (kind, path)."""
    candidates = ([str(Path(os.environ['SystemRoot']) / 'System32' / 'tar.exe')] if os.name == 'nt' and os.environ.get('SystemRoot') else []) + \
                 [t for t in (shutil.which('bsdtar'), shutil.which('tar')) if t]
    for tool in candidates:
        try:
            version = subprocess.run([tool, '--version'], capture_output=True, text=True, timeout=30,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
        except OSError:
            continue
        if 'bsdtar' in version and 'liblzma' in version:
            return 'tar', tool
    sevenzip = shutil.which('7z') or shutil.which('7za') or next(
        (str(p) for p in [Path(os.environ.get(v, '')) / '7-Zip' / '7z.exe' for v in ('ProgramFiles', 'ProgramFiles(x86)')] if p.is_file()), None)
    if sevenzip:
        return '7z', sevenzip
    raise ValueError('The .7z banks need a tar with LZMA (bsdtar/libarchive with liblzma; on Debian/Ubuntu '
                     '`sudo apt install libarchive-tools`) or 7-Zip (Windows 10\'s own tar.exe cannot read them)')

def _run(argv):
    done = subprocess.run(argv, capture_output=True, text=True, timeout=1800, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if done.returncode:
        raise ValueError(f'{Path(argv[0]).name} failed ({done.returncode}): ' + (done.stderr or done.stdout).strip()[-600:])
    return done.stdout

def list_members(archive, fmt):
    if fmt == 'tar.xz':
        with tarfile.open(archive, 'r:xz') as t:
            return [m.name for m in t.getmembers()], [m.name for m in t.getmembers() if m.issym() or m.islnk()]
    kind, tool = archive_tool()
    if kind == '7z':
        out = _run([tool, 'l', '-ba', '-slt', str(archive)])
        return [line[7:].replace('\\', '/') for line in out.splitlines() if line.startswith('Path = ')], []
    out = _run([tool, '-tf', str(archive)])
    return [line for line in out.splitlines() if line.strip()], []

def inside(target, name):
    """Where member `name` goes in `target`, refused when the way there runs through a link already in the folder (a
    subfolder or the file itself linked elsewhere would carry the write out of it, as tarfile's data filter refuses)."""
    root = Path(os.path.realpath(target))
    dest = root.joinpath(*PurePosixPath(name).parts)
    if os.path.normcase(os.path.realpath(dest)) != os.path.normcase(str(dest)):
        raise ValueError('A link in the destination folder: ' + name)
    return dest

def extract(archive, fmt, members, target):
    """The wanted members, written into a new private folder first (by tarfile, or by bsdtar or 7-Zip), then put in
    `target` (musiclib.files.install_tree): a file the installer did not put there is set aside, never written through.
    Returns the files set aside."""
    target.mkdir(parents=True, exist_ok=True)
    for name in members:
        inside(target, name)
    staging = files.staging_folder(target)
    try:
        if fmt == 'tar.xz':
            # Each wanted member must be a plain file with a safe name; it is copied through extractfile, which every
            # Python 3.10 has (extract's `filter` came only in 3.10.12 and 3.11.4).
            with tarfile.open(archive, 'r:xz') as t:
                for name in members:
                    m = t.getmember(name)
                    if not m.isfile() or not safe_member(name):
                        raise ValueError('Unsafe archive member: ' + name)
                    out = staging.joinpath(*PurePosixPath(name).parts)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with t.extractfile(m) as src, out.open('xb') as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
        else:
            kind, tool = archive_tool()
            if kind == '7z':
                _run([tool, 'x', '-y', f'-o{staging}', str(archive), *members])
            else:
                _run([tool, '-xf', str(archive), '-C', str(staging), *members])
            odd = files.foreign(staging)
            if odd:
                raise ValueError(f'The archive tool wrote links ({odd[0].name}); the archive is not used')
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return files.install_tree(staging, target)

def git_blob_sha1s(path):
    """Blob hashes a file may match: as stored, and for text files also with CRLF -> LF (a Windows
    checkout converts line endings; the repository hashes the LF form)."""
    data = Path(path).read_bytes()
    forms = [data] + ([data.replace(b'\r\n', b'\n')] if b'\0' not in data and b'\r\n' in data else [])
    return {hashlib.sha1(b'blob %d\0' % len(d) + d).hexdigest() for d in forms}

def install_archive(item, runtime, cache, offline, mirror=None, local=None):
    """A bank published as an archive: from `mirror` first (the same files repacked unchanged as a tar.xz on this
    project's release, or found in `local`), then from its publisher's own archive; the bank must have its locked hash
    either way."""
    if mirror:
        try:
            source = Path(local) / mirror['file'] if local else None
            return _install_archive({**item, 'format': 'tar.xz', 'url': mirror['url'], 'bytes': mirror['bytes'], 'sha256': mirror['sha256']},
                                    runtime, cache, offline, source)
        except (OSError, ValueError, EOFError, lzma.LZMAError, tarfile.TarError, http.client.HTTPException) as e:
            print(f'{item["name"]}: no repacked archive ({e}); downloading it from its publisher', flush=True)
    return _install_archive(item, runtime, cache, offline)

def _install_archive(item, runtime, cache, offline, local=None):
    archive = local if local else cache / Path(urllib.parse.urlsplit(item['url']).path).name
    if local and not archive.is_file():
        raise ValueError('Missing repacked archive ' + str(archive))
    if not local:
        cached(item['url'], archive, offline, item['bytes'], sha256_is(item['sha256']))
    if archive.stat().st_size != item['bytes'] or file_hash(archive) != item['sha256']:
        raise ValueError('Archive integrity failed: ' + item['name'])
    names, links = list_members(archive, item['format'])
    if links or not all(safe_member(n) for n in names) or len(names) > 50:
        raise ValueError('Unsafe archive layout: ' + item['name'])
    wanted = [item['member'], *item.get('notices', [])]
    missing = [w for w in wanted if w not in names]
    if missing:
        raise ValueError(f'Archive lacks {missing}')
    target = runtime / item['name']
    for moved in extract(archive, item['format'], wanted, target):
        print('SET ASIDE', moved, '| the installer did not put it there; it is kept under this name', flush=True)
    bank = target / item['member']
    if file_hash(bank) != item['member_sha256']:
        raise ValueError('Extracted bank hash mismatch: ' + item['name'])
    return {'path': str(bank), 'sha256': item['member_sha256'], 'license': item['license'], 'source': item['url'],
            'version': f"{item['version']} (archive sha256 {item['sha256']})"}

def locked(path, patterns):
    """A build's `paths` name files, folders (ending in "/") or globs ("Samples/*_looped_[pf].wav"), so only the
    samples its spec uses are fetched."""
    return any(path == q or (q.endswith('/') and path.startswith(q)) or (any(c in q for c in '*?[') and fnmatch.fnmatchcase(path, q))
               for q in patterns)

def built(item, runtime):
    """The bank already built in this runtime, if it still has its locked hash (its sources may have been deleted)."""
    output = runtime / 'build' / f'{item["name"]}-{item["version"].split()[-1]}.sf2'
    return output if output.exists() and file_hash(output) == item['output_sha256'] else None

def install_prebuilt(item, asset, runtime, cache, release, offline, local=None):
    """The bank as this project built it, from its release asset (or `local`, a folder holding the assets): the asset
    must match its locked size and SHA-256 before it is opened; it is unpacked through a .partial file that may not
    grow past the locked SF2 size, and must give the build's locked hash before it takes the built bank's place."""
    target = runtime / 'build' / f'{item["name"]}-{item["version"].split()[-1]}.sf2'
    packed = Path(local) / asset['file'] if local else cache / asset['file']
    if local:
        if not packed.exists():
            raise ValueError('Missing prebuilt asset ' + str(packed))
    else:
        cached(release + urllib.parse.quote(asset['file']), packed, offline, asset['bytes'], sha256_is(asset['sha256']))
    if packed.stat().st_size != asset['bytes'] or file_hash(packed) != asset['sha256']:
        raise ValueError('Prebuilt asset does not match the lock: ' + asset['file'])
    target.parent.mkdir(parents=True, exist_ok=True)
    digest, count = hashlib.sha256(), 0
    partial = files.stage_name(target, '.sf2')
    try:
        with lzma.open(packed, 'rb') as src, partial.open('wb') as out:
            while chunk := src.read(1 << 22):
                count += len(chunk)
                if count > asset['sf2_bytes']:
                    raise ValueError('Prebuilt asset unpacks past the locked bank size: ' + asset['file'])
                digest.update(chunk)
                out.write(chunk)
        if count != asset['sf2_bytes'] or digest.hexdigest() != item['output_sha256']:
            raise ValueError('Prebuilt bank does not have the locked hash: ' + item['name'])
        publish(partial, target)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(partial)  # gone once published; left only by a failure
    return target

def publish(new, target):
    """A checked new file takes `target`'s place in the build folder, recorded there as the installer's
    (musiclib.files.place): what is at `target` and is not the installer's own unchanged file (a bank or receipt of the
    user's, one edited since) is renamed aside and named, never written over."""
    for moved in (files.place(new, target, target.parent), files.register(target.parent, [target])):
        if moved is not None:
            print('SET ASIDE', moved, '| the installer did not put it there; it is kept under this name', flush=True)

def requested(lock, only):
    """The bank names that --only asks for: names and groups, comma-separated (None for every bank)."""
    if not only:
        return None
    groups, names = lock.get('groups', {}), set()
    for word in only.split(','):
        names |= set(groups.get(word, [word]))
    unknown = names - {i['name'] for i in lock['archives'] + lock['builds']}
    if unknown:
        raise ValueError(f'--only: unknown {", ".join(sorted(unknown))}; the groups are {", ".join(groups)}')
    return names

def install_build(item, runtime, source, offline, ffmpeg=None):
    commit, repo = item['commit'], item['repository']
    ready = built(item, runtime)
    if ready:
        return {'path': str(ready), 'sha256': item['output_sha256'], 'license': item['license'],
                'source': f'https://github.com/{repo} at {commit} with references/{item["spec"]}', 'version': item['version'],
                'verified_samples': None}
    tree_file = runtime / 'sources' / f'{repo.replace("/", "_")}_{commit}_tree.json'
    tree_file.parent.mkdir(parents=True, exist_ok=True)
    def listing(path):
        try:
            t = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            return False
        return t.get('sha') == commit or t.get('url', '').endswith(commit)
    cached(f'https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1', tree_file, offline, check=listing, max_bytes=20_000_000)
    tree = json.loads(tree_file.read_text(encoding='utf-8'))
    if tree.get('sha') != commit and not tree.get('url', '').endswith(commit):
        raise ValueError('Tree listing does not belong to the pinned commit')
    wanted = pinned_samples(item, tree)
    root = runtime / 'sources' / f'{repo.split("/")[1]}-{commit[:12]}'
    root.mkdir(parents=True, exist_ok=True)
    for path, sha, size in wanted:
        dest = inside(root, path)
        matches = lambda f, sha=sha: sha in git_blob_sha1s(f)
        local = Path(source) / path if source else None
        if not files.occupied(dest) and local and local.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            files.replace(files.stage_copy(local, dest), dest)
        # At most the locked size: a download is the blob as stored.
        cached(f'https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(path)}', dest, offline, check=matches, max_bytes=size)
    output = runtime / 'build' / f'{item["name"]}-{item["version"].split()[-1]}.sf2'
    build_bank(item, json.loads((SKILL / 'references' / item['spec']).read_text(encoding='utf-8')), root, output, ffmpeg)
    return {'path': str(output), 'sha256': item['output_sha256'], 'license': item['license'],
            'source': f'https://github.com/{repo} at {commit} with references/{item["spec"]}', 'version': item['version'],
            'verified_samples': len(wanted)}

def build_bank(item, spec, root, output, ffmpeg):
    """Build into a new file of its own that becomes the bank only with the locked hash, so a failed build is never
    kept; the bank and its receipt then take their places as publish() places a file."""
    from soundbank import build
    if files.regular_file(output) and file_hash(output) == item['output_sha256']:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = files.stage_name(output, '.sf2')
    try:
        receipt = build(spec, root, partial, ffmpeg)
        if file_hash(partial) != item['output_sha256']:
            import numpy
            raise ValueError(f'Rebuilt bank does not reproduce the locked hash: {item["name"]}.  The lock was built with '
                             f'NumPy {NUMPY_BUILD} (this is NumPy {numpy.__version__}); a different NumPy can round a few '
                             'samples differently.  Install the prebuilt bank instead (leave out --from-source).')
        publish(partial, output)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(partial)
    receipt['output']['path'] = str(output)  # it was built under a temporary name
    sidecar = output.with_suffix('.receipt.json')
    written = files.stage_name(sidecar, '.json')
    try:
        save_json(written, receipt)
        publish(written, sidecar)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(written)

def install_split(item, runtime, offline, ffmpeg=None):
    from soundbank import cut_sources, save_manifest
    ready = built(item, runtime)
    if ready:
        return {'path': str(ready), 'sha256': item['output_sha256'], 'license': item['license'],
                'source': f'{item["page"]} ({len(item["files"])} recordings) with references/{item["spec"]}',
                'version': item['version'], 'verified_samples': None}
    source = runtime / 'sources' / item['source_folder']
    for f in item['files']:
        dest = source / f['path']
        cached(item['base'] + urllib.parse.quote(f['path']), dest, offline, f['bytes'], sha256_is(f['sha256']))
    spec = json.loads((SKILL / 'references' / item['spec']).read_text(encoding='utf-8'))
    version = item['version'].split()[-1]
    notes = runtime / 'sources' / f'{item["name"]}-{version}-notes'
    if not files.regular_file(notes / 'split.json'):
        # The notes are cut where the locked manifest says (soundbank.py split recorded each cut and its hash), into a
        # new private folder that becomes the notes folder only when every cut is verified.
        manifest = json.loads((SKILL / 'references' / item['notes']).read_text(encoding='utf-8'))
        files.fresh(notes, 'a notes folder without its split.json is not this installer\'s; move it away and run again')
        partial = files.staging_folder(notes)
        try:
            cut_sources(manifest, source, partial)
            save_manifest(partial / 'split.json', manifest)
            files.replace(partial, notes)
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
    output = runtime / 'build' / f'{item["name"]}-{version}.sf2'
    build_bank(item, spec, notes, output, ffmpeg)
    return {'path': str(output), 'sha256': item['output_sha256'], 'license': item['license'],
            'source': f'{item["page"]} ({len(item["files"])} recordings) with references/{item["spec"]}',
            'version': item['version'], 'verified_samples': len(item['files'])}

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--runtime', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--archive-cache', type=Path)
    ap.add_argument('--vsco-source', type=Path)
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--only', help='bank names and groups, comma-separated (groups: orchestra, band, world, examples)')
    ap.add_argument('--from-source', action='store_true',
                    help="build every bank from its publishers' samples instead of downloading this project's build")
    ap.add_argument('--prebuilt-from', type=Path, help='take the prebuilt banks from this folder instead of the release')
    ap.add_argument('--delete-sources', action='store_true',
                    help='after every requested bank is verified, delete the downloads they were made from')
    args = ap.parse_args()
    if files.occupied(args.output):
        raise ValueError('Choose a new configuration path')
    lock = json.loads((SKILL / 'references' / 'soundbank-lock.json').read_text(encoding='utf-8'))
    only = requested(lock, args.only)
    prebuilt = {} if args.from_source else lock.get('prebuilt', {}).get('assets', {})
    runtime = args.runtime.resolve()
    cache = (args.archive_cache or runtime / 'archives').resolve()
    cache.mkdir(parents=True, exist_ok=True)
    from musiclib.audio import absolute_paths
    config = absolute_paths(json.loads(args.config.read_text(encoding='utf-8')), args.config.resolve().parent)
    fonts = config.setdefault('soundfonts', {})
    failed = {}
    mirrors = {} if args.from_source else lock.get('prebuilt', {}).get('archives', {})
    for item in lock['archives']:
        if only is None or item['name'] in only:
            try:
                mirror = mirrors.get(item['name'])
                mirror = {**mirror, 'url': lock['prebuilt']['release'] + urllib.parse.quote(mirror['file'])} if mirror else None
                fonts[item['name']] = install_archive(item, runtime, cache, args.offline, mirror, args.prebuilt_from)
                if mirror and fonts[item['name']]['source'] == mirror['url']:
                    print('PREBUILT', item['name'], flush=True)
                print('VERIFIED', item['name'], flush=True)
            except (OSError, ValueError, http.client.HTTPException) as e:
                failed[item['name']] = str(e)
                print('FAILED', item['name'], '|', e, flush=True)
    for item in lock['builds']:
        if only is None or item['name'] in only:
            try:
                used = None
                if item['name'] in prebuilt and not built(item, runtime):
                    try:
                        install_prebuilt(item, prebuilt[item['name']], runtime, cache, lock['prebuilt']['release'], args.offline,
                                         args.prebuilt_from)
                        name = prebuilt[item['name']]['file']
                        used = str(args.prebuilt_from.resolve() / name) if args.prebuilt_from else lock['prebuilt']['release'] + name
                        print('PREBUILT', item['name'], flush=True)
                    except (OSError, ValueError, EOFError, lzma.LZMAError, http.client.HTTPException) as e:
                        print(f'{item["name"]}: no prebuilt bank ({e}); building it from its sources', flush=True)
                if item.get('kind') == 'split':
                    fonts[item['name']] = install_split(item, runtime, args.offline, config['ffmpeg']['path'])
                else:
                    vsco = args.vsco_source if item['repository'].endswith('/VSCO-2-CE') else None
                    fonts[item['name']] = install_build(item, runtime, vsco, args.offline, config['ffmpeg']['path'])
                if used:
                    fonts[item['name']]['prebuilt'] = used
                count = fonts[item['name']]['verified_samples']
                print('VERIFIED', item['name'], f'{count} samples' if count is not None else '(the built bank matches its lock)', flush=True)
            except (OSError, ValueError, EOFError, lzma.LZMAError, http.client.HTTPException) as e:
                failed[item['name']] = str(e)
                print('FAILED', item['name'], '|', e, flush=True)
    # The banks that did install are written to the configuration either way; a failure is listed and ends in exit 2.
    save_json(args.output.resolve(), config)
    print('Saved', args.output.resolve())
    if failed:
        raise ValueError(f'{len(failed)} bank(s) failed: ' + '; '.join(f'{k}: {v}' for k, v in failed.items()) +
                         '.  The others are configured; run again with --only ' + ','.join(failed) + ' (and a new --output) to retry.')
    if args.delete_sources:
        delete_sources(lock, only, runtime, cache)


def source_files(lock, only, runtime, cache):
    """What the installer downloaded or cut for the requested banks, each with how to tell it is still the installer's
    own file: [(archive, check)] for the archives and prebuilt assets in the cache (their locked size and SHA-256), and
    [(folder, {relative path: check})] for the sample trees, recordings and cut notes in runtime/sources (each file's
    git blob hash, locked SHA-256 or recorded SHA-256).  A sample tree whose listing is gone has no checks: nothing in it
    can be shown to be the installer's."""
    def sha(expected, size=None):
        return lambda p: (size is None or p.stat().st_size == size) and file_hash(p) == expected
    archives, folders = [], []
    for item in lock['archives']:
        if only is None or item['name'] in only:
            archives.append((cache / Path(urllib.parse.urlsplit(item['url']).path).name, sha(item['sha256'], item['bytes'])))
            mirror = lock.get('prebuilt', {}).get('archives', {}).get(item['name'])
            if mirror:
                archives.append((cache / mirror['file'], sha(mirror['sha256'], mirror['bytes'])))
    for item in lock['builds']:
        if only is not None and item['name'] not in only:
            continue
        asset = lock.get('prebuilt', {}).get('assets', {}).get(item['name'])
        if asset:
            archives.append((cache / asset['file'], sha(asset['sha256'], asset['bytes'])))
        sources = runtime / 'sources'
        if item.get('kind') == 'split':
            folders.append((sources / item['source_folder'], {f['path']: sha(f['sha256'], f['bytes']) for f in item['files']}))
            manifest = json.loads((SKILL / 'references' / item['notes']).read_text(encoding='utf-8'))
            notes = {n['file']: sha(n['sha256']) for n in manifest['notes']}
            notes['split.json'] = lambda p, m=manifest: json.loads(p.read_text(encoding='utf-8')) == m
            folders.append((sources / f'{item["name"]}-{item["version"].split()[-1]}-notes', notes))
        else:
            repo, commit = item['repository'], item['commit']
            listing = sources / f'{repo.replace("/", "_")}_{commit}_tree.json'
            try:
                tree = json.loads(listing.read_text(encoding='utf-8')) if files.regular_file(listing) else {}
            except ValueError:
                tree = {}
            # Only a listing that names exactly the pinned samples says which files are the installer's.
            try:
                pinned = pinned_samples(item, tree) if tree.get('sha') == commit or tree.get('url', '').endswith(commit) else []
            except (ValueError, KeyError, TypeError):
                pinned = []
            folders.append((sources / f'{repo.split("/")[1]}-{commit[:12]}',
                            {p: (lambda f, s=s: s in git_blob_sha1s(f)) for p, s, _ in pinned}))
    return archives, folders


def delete_sources(lock, only, runtime, cache):
    """Delete what the installer downloaded or cut for the requested banks, and only that: a file goes when it is
    still the installer's (source_files: its locked or recorded hash), then the folders left empty.  Anything else in
    those folders (a file put there, a changed one) stays and is named; nothing is reached through a link."""
    files.no_links(runtime / 'sources', below=runtime.parent)
    archives, folders = source_files(lock, only, runtime, cache)
    freed, kept = 0, []
    for path, check in archives:
        if not files.occupied(path):
            continue
        if files.regular_file(path) and check(path):
            freed += path.stat().st_size
            path.unlink()
            print('Deleted', path)
        else:
            kept.append(path)
    for folder, checks in folders:
        if not files.occupied(folder):
            continue
        if not files.real_folder(folder):
            kept.append(folder)
            continue
        gone = 0
        for p in files.tree(folder):
            check = checks.get(p.relative_to(folder).as_posix())
            if check is not None and check(p):
                freed += p.stat().st_size
                p.unlink()
                gone += 1
            else:
                kept.append(p)
        files.prune(folder)
        print('Deleted', gone, 'files from', folder)
    print(f'Freed {freed / 1e6:.0f} MB of downloaded sources')
    for p in kept[:20]:
        print('Kept', p, "| not the installer's file (or changed since): delete it yourself if you want", flush=True)
    if len(kept) > 20:
        print(f'Kept {len(kept) - 20} more files of that kind', flush=True)

if __name__ == '__main__':
    files.escape_unprintable()
    try:
        main()
    except (ValueError, OSError) as e:
        print('ERROR:', e, file=sys.stderr)
        sys.exit(2)
