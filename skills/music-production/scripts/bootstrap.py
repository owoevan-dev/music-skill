"""Set up the renderer's dependencies in a chosen local directory and write a configuration for them.

Windows x64 (default there): downloads the pinned portable FluidSynth and FFmpeg builds and the default sound bank
from their official release pages, checks every size and SHA-256 against references/runtime-lock.json, and
extracts them.  No installer runs; the registry and the system PATH are not touched.

--system (Linux, macOS, or Windows with your own tools): uses the fluidsynth and ffmpeg found on PATH (or given
with --fluidsynth/--ffmpeg) and downloads only the default sound bank and its licence notice, checked the same way.
Install the tools from your package manager first, e.g. `sudo apt install fluidsynth ffmpeg` or
`brew install fluid-synth ffmpeg`.  FFmpeg 6.0 or newer is required; renders are tested with FFmpeg 6.1 (Ubuntu
24.04) and 9.0 (macOS and the pinned Windows build).  Homebrew's ffmpeg lacks the libvorbis encoder, so a game loop rendered
with it gets no Ogg copy; for one, `brew install ffmpeg-full` and pass --ffmpeg "$(brew --prefix ffmpeg-full)/bin/ffmpeg".

Surge XT (engine "surge") is installed too unless --no-surge: the pinned plugin-only release for Windows or Linux on
x86-64 or for macOS (its VST3 alone is kept), or the bundle given with --surge-vst3; elsewhere (Linux on ARM) a Surge
XT 1.3.4 you installed from https://surge-synthesizer.github.io/, found in the usual VST3 folders; then the pinned pedalboard wheel for this Python, checked against the
hashes PyPI publishes, installed into the runtime folder only, and the curated factory patches from Surge's pinned
repository commit, each checked by hash.  Then, unless --no-surge-catalog, every patch of the catalog
(references/surge-catalog.json: 3,008 factory and third-party patches, about 217 MB) from the same commit, each checked
by size and hash, for parts that name a catalog patch.  Both programs are GPL-3.0 and run as their own process; without
them, Surge parts play their fallback presets on the built-in synth.
External files keep their own licences.
"""
import argparse
import contextlib
import hashlib
import http.client
import json
import os
from pathlib import Path,PurePosixPath
import platform
import re
import shutil
import tarfile
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from musiclib import files
from musiclib.model import file_hash,save_json

HOSTS=('github.com','raw.githubusercontent.com','release-assets.githubusercontent.com','objects.githubusercontent.com',
       'files.pythonhosted.org')  # the last for the pedalboard wheel the lock pins
MIN_FFMPEG=6

def safe_extract(path,target,only=None):
    """Extract a zip after checking every member; with `only`, just the members under that prefix.  The members are
    written into a new private folder, then put in `target` (musiclib.files.install_tree): a file the installer did not
    put there is set aside, never written through or lost.  Returns the files set aside."""
    # A target that is a link is refused before it is resolved, which would follow it (GPT's security audit of 0.5, S03).
    if files.linked(target):raise ValueError(f'{target} is a link; a setup installs only into real folders')
    target=Path(target).resolve();staging=files.staging_folder(target)
    try:
        with zipfile.ZipFile(path) as z:
            infos=z.infolist()
            if len(infos)>10000 or sum(i.file_size for i in infos)>800_000_000:raise ValueError('Archive exceeds limits')
            for i in infos:
                p=PurePosixPath(i.filename)
                if p.is_absolute() or '..' in p.parts or ':' in i.filename or '\\' in i.filename or ((i.external_attr>>16)&0o170000)==0o120000:
                    raise ValueError('Unsafe archive member')
                if only and not i.filename.startswith(only):continue
                out=(staging/Path(*p.parts)).resolve();out.relative_to(staging)
                if i.is_dir():out.mkdir(parents=True,exist_ok=True);continue
                if i.file_size>350_000_000:raise ValueError('Archive member too large')
                out.parent.mkdir(parents=True,exist_ok=True)
                with z.open(i) as src,out.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
                mode=(i.external_attr>>16)&0o777  # Unix permission bits, kept so an extracted plugin stays loadable
                if os.name!='nt' and mode:os.chmod(out,mode)
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True);raise
    return files.install_tree(staging,target)

def safe_extract_tar(path,target,only=None):
    """Extract a .tar.gz after checking every member: regular files and folders only (no link), no absolute path and
    none outside the target.  A leading "./" is dropped from the names, `only` keeps the members under that prefix, and
    the permission bits are kept.  Put in `target` as safe_extract does.  Returns the files set aside."""
    # A target that is a link is refused before it is resolved, which would follow it (GPT's security audit of 0.5, S03).
    if files.linked(target):raise ValueError(f'{target} is a link; a setup installs only into real folders')
    target=Path(target).resolve();staging=files.staging_folder(target)
    try:
        with tarfile.open(path,'r:gz') as t:
            members=t.getmembers()
            if len(members)>10000 or sum(m.size for m in members)>800_000_000:raise ValueError('Archive exceeds limits')
            for m in members:
                name=m.name[2:] if m.name.startswith('./') else m.name;p=PurePosixPath(name)
                if not (m.isfile() or m.isdir()) or p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name:
                    raise ValueError('Unsafe archive member')
                if only and not name.startswith(only):continue
                out=(staging/Path(*p.parts)).resolve();out.relative_to(staging)
                if m.isdir():out.mkdir(parents=True,exist_ok=True);continue
                if m.size>350_000_000:raise ValueError('Archive member too large')
                out.parent.mkdir(parents=True,exist_ok=True)
                with t.extractfile(m) as src,out.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
                if os.name!='nt':os.chmod(out,m.mode&0o777)
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True);raise
    return files.install_tree(staging,target)

def note_aside(moved):
    """Name the files an install set aside (musiclib.files.place): they were not put there by bootstrap."""
    for m in moved or []:print('SET ASIDE',m,'| bootstrap did not install it there; it is kept under this name',flush=True)

class Allowed(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to an allowed host over HTTPS, checked before the request is made."""
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parts=urllib.parse.urlsplit(newurl)
        if parts.scheme!='https' or parts.hostname not in HOSTS:
            fp.close()  # urllib closes the redirect's response only when it follows it
            raise ValueError('Redirect to a host that is not allowed: '+newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class Short(OSError):
    """A download the server ended before its locked size: tried again like a dropped connection."""

def download(item,archive,offline,tries=4):
    """Download to `archive` through a new file of its own (musiclib.files.staged), hashed as it arrives: it takes the
    archive's place only with the locked size and SHA-256, and is removed otherwise.  Two runs never share it.  An
    archive already there is left for the caller, which checks it.  A dropped connection, a timeout, a download cut
    short or a server error (5xx, 429) is tried again after 3, 6 and 12 s, as fetch_soundbanks.fetch does; a refused
    host, another HTTP error, a size over the lock or a file that does not match it is not.  Before, one HTTP 504
    from GitHub's servers stopped a whole install, and the error did not say which download (found by CI)."""
    if files.occupied(archive):return
    if offline:raise ValueError('Offline cache missing '+str(archive))
    parts=urllib.parse.urlsplit(item['url'])
    if parts.scheme!='https' or parts.hostname not in HOSTS:raise ValueError('Host not allowed: '+item['url'])
    for attempt in range(tries):
        try:return _download_once(item,archive)
        except (OSError,http.client.HTTPException) as e:
            # A name another run or the user took meanwhile is not tried again: a download is published only where
            # nothing holds its name (files.staged new; GPT Pro's fourth review of 0.4.0).
            if isinstance(e,FileExistsError) or isinstance(e,urllib.error.HTTPError) and e.code<500 and e.code!=429 or attempt==tries-1:
                print(f'download failed: {item["url"]} ({e})',flush=True);raise
            print(f'retrying {item["url"]} after {e}',flush=True);time.sleep(3*2**attempt)

def _download_once(item,archive):
    request=urllib.request.Request(item['url'],headers={'User-Agent':'MusicProductionSkill/1.0'})
    with urllib.request.build_opener(Allowed).open(request,timeout=60) as r:
        if urllib.parse.urlsplit(r.url).hostname not in HOSTS:raise ValueError('Unexpected download redirect')
        count=0;digest=hashlib.sha256()
        with files.staged(archive,new=True) as out:
            while True:
                data=r.read(1024*1024)
                if not data:break
                count+=len(data)
                if count>item['bytes']:raise ValueError(f'{item["url"]}: the download exceeds its locked size')
                digest.update(data);out.write(data)
            # A connection the server closes early ends the reads without an error: the locked size tells.
            if count<item['bytes']:raise Short(f'{item["url"]}: {count} of {item["bytes"]} bytes arrived')
            if digest.hexdigest()!=item['sha256']:raise ValueError(f'{item["url"]}: the download does not match the lock')

def system_tool(name,given):
    """A fluidsynth/ffmpeg executable from the system: its path, hash and the first line of its version output."""
    if given:
        path=Path(given).resolve()
        if not path.is_file():raise ValueError(f'{name} not found at {path}')
    else:
        found=shutil.which(name)
        if not found:raise ValueError(f'{name} not found on PATH; install it from your package manager or pass --{name}')
        path=Path(found).resolve()
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    out=subprocess.run([str(path),'--version' if name=='fluidsynth' else '-version'],capture_output=True,text=True,timeout=30,stdin=subprocess.DEVNULL,creationflags=flags)
    first=(out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else ''
    if name=='ffmpeg':
        m=re.search(r'version\s+n?(\d+)\.',first)
        if m and int(m.group(1))<MIN_FFMPEG:raise ValueError(f'{first}: FFmpeg {MIN_FFMPEG}.0 or newer is required')
    return {'path':str(path),'sha256':file_hash(path),'version':first,'license':'System package; see its distribution','source':'User system installation; hash is integrity, not provenance'}

def has_vorbis(ffmpeg):
    """Whether this FFmpeg has the libvorbis encoder a game loop's Ogg copy needs (musiclib.loop.has_vorbis asks the same)."""
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    out=subprocess.run([str(ffmpeg),'-hide_banner','-encoders'],capture_output=True,text=True,errors='replace',timeout=30,stdin=subprocess.DEVNULL,creationflags=flags)
    return ' libvorbis ' in out.stdout

def surge_platform():
    """This machine's pinned Surge XT build in runtime-lock.json: Windows and Linux on x86-64, and macOS (a universal
    binary for Intel and Apple silicon); None elsewhere (Linux on ARM), where a system install is looked for."""
    if sys.platform=='darwin':return 'macos-universal'
    if platform.machine().lower() not in ('x86_64','amd64'):return None
    return 'windows-x86_64' if os.name=='nt' else 'linux-x86_64' if sys.platform.startswith('linux') else None

def surge_plugin(lock,runtime,cache,args,system):
    """The Surge XT VST3 to load and the binary inside it to hash: the bundle given with --surge-vst3, else the pinned
    plugin-only build for this machine (surge_platform), else a system install in the usual VST3 folders."""
    s=lock['optional']['surge_xt'];key=None if args.surge_vst3 else surge_platform()
    if key in s:
        item=s[key];archive=cache/item['filename'];download(item,archive,args.offline)
        if archive.stat().st_size!=item['bytes'] or file_hash(archive)!=item['sha256']:raise ValueError('Archive integrity failed: surge_xt')
        target=runtime/'surge_xt';note_aside((safe_extract_tar if item['filename'].endswith('.tar.gz') else safe_extract)(archive,target,item['extract']))
        binary=target/item['executable']
        if file_hash(binary)!=item['executable_sha256']:raise ValueError('Executable integrity failed: surge_xt')
        return (binary if key=='windows-x86_64' else target/item['extract'].rstrip('/')),binary,item['url']
    kind='darwin' if sys.platform=='darwin' else 'windows' if os.name=='nt' else 'linux'
    for bundle in ([args.surge_vst3] if args.surge_vst3 else [Path(os.path.expandvars(p)).expanduser() for p in s['system_bundles'].get(kind,[])]):
        for inner in s['bundle_binaries'].get(kind,[]):
            if (Path(bundle)/inner).is_file():return Path(bundle).resolve(),(Path(bundle)/inner).resolve(),'User system installation; hash is integrity, not provenance'
    return None,None,None

def wheel_tags():
    """The wheel tags this Python installs, best first, as pip ranks them when it picks a wheel (pip's own copy of the
    packaging library); none where pip cannot be imported, as then it could not install the wheel either."""
    try:
        from pip._vendor.packaging.tags import sys_tags
    except ImportError:
        return []
    return [str(t) for t in sys_tags()]

def pedalboard_wheel(lock,cache,offline):
    """The pinned pedalboard wheel for this Python and platform: of the wheels the lock lists, the one whose tags pip
    ranks first here, from the cache while its bytes match the lock (a cache shared by several Pythons or machines
    holds each one's wheel), else downloaded from its locked URL, no larger than its locked size and hashed as it
    arrives (download).  `pip download` would have fetched whatever the index served before anything could check it."""
    board=lock['optional']['pedalboard'];wheels=board['wheels']
    rank={t:i for i,t in enumerate(wheel_tags())}
    def best(name):
        py,abi,plat=name[:-len('.whl')].split('-')[-3:]
        return min((rank[t] for t in (f'{a}-{b}-{c}' for a in py.split('.') for b in abi.split('.') for c in plat.split('.')) if t in rank),default=None)
    fitting=sorted((r,n) for n in wheels for r in [best(n)] if r is not None)
    if not fitting:return None,None
    name=fitting[0][1];w=wheels[name];dest=cache/name
    if files.occupied(dest) and not (files.regular_file(dest) and dest.stat().st_size==w['bytes'] and file_hash(dest)==w['sha256']):
        print(f'{name}: the cached copy does not match the lock; set aside as {files.aside(dest).name}',flush=True)
    if not files.occupied(dest):
        if offline:return None,None
        download(w,dest,offline)
    return dest,w

def install_surge(lock,runtime,cache,args,system,config):
    """Surge XT, pedalboard and the curated patches; a missing piece is reported and leaves Surge parts on fallbacks."""
    try:return _install_surge(lock,runtime,cache,args,system,config)
    except (ValueError,OSError,subprocess.SubprocessError) as e:
        config.pop('surge',None);config.pop('pedalboard',None)
        print(f'SKIPPED surge_xt | {e}; Surge parts use their fallback presets',flush=True)

def _install_surge(lock,runtime,cache,args,system,config):
    plugin,binary,source=surge_plugin(lock,runtime,cache,args,system)
    if plugin is None:
        print('SKIPPED surge_xt | not found: install Surge XT 1.3.4 from https://surge-synthesizer.github.io/ or pass --surge-vst3; Surge parts use their fallback presets',flush=True);return
    wheel,meta=pedalboard_wheel(lock,cache,args.offline)
    if wheel is None:
        print('SKIPPED pedalboard | no pinned wheel for this Python and platform; Surge parts use their fallback presets',flush=True);return
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    pylib=runtime/'pylib'
    # pip writes where its target leads: no link in it (the runtime's own folders are checked in main).
    odd=files.links_in(pylib) if files.real_folder(pylib) else []
    if odd:raise ValueError(f'{odd[0]} is a link; pedalboard is installed only into real folders')
    done=subprocess.run([sys.executable,'-m','pip','install','--no-deps','--no-index','--no-cache-dir','--target',str(pylib),str(wheel),'-q'],
                        capture_output=True,text=True,timeout=600,stdin=subprocess.DEVNULL,creationflags=flags)
    if done.returncode or not (pylib/'pedalboard').is_dir():raise ValueError('pedalboard install failed: '+(done.stderr or '').strip()[-300:])
    # pip's RECORD lists every file it installed with its hash (PEP 376, the wheel format); its own hash goes in the
    # configuration, and a render checks the installed files against it (musiclib.surge.board_intact).
    records=sorted(pylib.glob('pedalboard-*.dist-info/RECORD'))
    from musiclib.surge import board_intact
    if len(records)!=1 or not board_intact(pylib):raise ValueError('pedalboard installed without a RECORD that matches its files')
    presets=json.loads((Path(__file__).resolve().parents[1]/'references'/'surge-presets.json').read_text(encoding='utf-8'))
    src=presets['source'];patches=runtime/'surge_patches';staging=files.staging_folder(patches)
    try:
        for name,p in presets['presets'].items():
            local=files.cache_file(cache,'surge_patches',*PurePosixPath(p['patch']).parts)
            url=f'https://raw.githubusercontent.com/surge-synthesizer/surge/{src["commit"]}/{src["path"]}/'+urllib.parse.quote(p['patch'])
            download({'url':url,'bytes':p['bytes'],'sha256':p['sha256']},local,args.offline)
            if local.stat().st_size!=p['bytes'] or file_hash(local)!=p['sha256']:raise ValueError('Patch integrity failed: '+name)
            out=staging/p['patch'];out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(local,out)
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True);raise
    note_aside(files.install_tree(staging,patches))
    s=lock['optional']['surge_xt'];board=lock['optional']['pedalboard']
    config['surge']={'path':str(plugin),'binary':str(binary),'sha256':file_hash(binary),'version':s['version'] if source.startswith('https://') else 'system install (version not checked)','license':s['license'],'source':source,'patches':str(patches)}
    config['pedalboard']={'path':str(pylib),'sha256':meta['sha256'],'record_sha256':file_hash(records[0]),'version':board['version'],'license':board['license'],'source':meta['url']}
    print('VERIFIED surge_xt |',len(presets['presets']),'curated patches',flush=True)

def install_catalog(runtime,cache,args,config):
    """Every patch of the Surge catalog, each checked by size and hash, into the runtime folder; a failure is reported and
    leaves parts that name a catalog patch on their fallback presets, while the curated patches keep working."""
    doc=json.loads((Path(__file__).resolve().parents[1]/'references'/'surge-catalog.json').read_text(encoding='utf-8'))
    origin=doc['origin'];target=runtime/'surge_patches_all';staging=files.staging_folder(target)
    def one(e):
        local=files.cache_file(cache,'surge_patches_all',*PurePosixPath(e['path']).parts)
        url=f'https://raw.githubusercontent.com/surge-synthesizer/surge/{origin["commit"]}/{origin["path"]}/'+urllib.parse.quote(e['path'])
        download({'url':url,'bytes':e['bytes'],'sha256':e['sha256']},local,args.offline)  # tried again there
        if local.stat().st_size!=e['bytes'] or file_hash(local)!=e['sha256']:raise ValueError('Patch integrity failed: '+e['path'])
        out=staging/e['path'];out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(local,out)
    try:
        with ThreadPoolExecutor(8) as pool:list(pool.map(one,doc['presets'].values()))
        note_aside(files.install_tree(staging,target))
    except (ValueError,OSError,http.client.HTTPException) as err:
        shutil.rmtree(staging,ignore_errors=True)
        print(f'SKIPPED surge_catalog | {err}; parts that name a catalog patch use their fallback presets',flush=True);return
    config['surge']['catalog']=str(target)
    print('VERIFIED surge_catalog |',len(doc['presets']),'patches',flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--config',type=Path,required=True);ap.add_argument('--archive-cache',type=Path);ap.add_argument('--offline',action='store_true')
    ap.add_argument('--system',action='store_true',help='use the system fluidsynth and ffmpeg; download only the default sound bank')
    ap.add_argument('--fluidsynth',type=Path,help='with --system: this executable instead of the one on PATH');ap.add_argument('--ffmpeg',type=Path,help='with --system: this executable instead of the one on PATH')
    ap.add_argument('--no-surge',action='store_true',help='skip Surge XT and pedalboard (Surge parts then play their fallback presets)')
    ap.add_argument('--surge-vst3',type=Path,help='this Surge XT.vst3 bundle instead of the pinned build (or, where none is pinned, the usual VST3 folders)')
    ap.add_argument('--no-surge-catalog',action='store_true',help='skip the full Surge patch set (about 217 MB): only the curated patches; parts that name a catalog patch play their fallback presets')
    args=ap.parse_args()
    system=args.system or os.name!='nt'
    files.check_config_path(args.config,'--config')
    # The downloads' folder given as a link is refused before it is resolved, as a render's cache is (N1).
    if args.archive_cache and files.linked(args.archive_cache):raise ValueError(f'--archive-cache {args.archive_cache} is a link; give the folder itself')
    if os.path.normcase(str(args.config.resolve()))==os.path.normcase(str((args.runtime/'dependency_receipts.json').resolve())):
        raise ValueError("--config names the runtime folder's dependency_receipts.json; choose another path for the configuration")
    runtime=args.runtime.resolve();runtime.mkdir(parents=True,exist_ok=True)
    # One setup at a time in a runtime, and none through a link in it (musiclib.files; GPT's security audit of 0.5,
    # S05 and S03).
    with files.installing(runtime) as held:
        # Without the lock the setup goes on, as a render does on a drive that cannot lock, and says so (N2).
        if not held:print('NOTE runtime | its lock cannot be taken (the drive cannot lock files, or work.lock there is no lock file): make sure no other setup is installing into it',flush=True)
        files.real_runtime(runtime);_install(args,system,runtime)

def _install(args,system,runtime):
    lock=json.loads((Path(__file__).resolve().parents[1]/'references'/'runtime-lock.json').read_text(encoding='utf-8'))
    cache=args.archive_cache.resolve() if args.archive_cache else runtime/'downloads';cache.mkdir(parents=True,exist_ok=True)
    config={};receipts=[]
    if system:
        for name in ('fluidsynth','ffmpeg'):
            config[name]=system_tool(name,getattr(args,name));print('FOUND',name,'|',config[name]['version'],flush=True)
    for item in lock['downloads']:
        executable=item['filename'].endswith('.zip')
        if system and executable:continue  # the portable executables are the Windows builds
        archive=cache/item['filename'];download(item,archive,args.offline)
        if archive.stat().st_size!=item['bytes'] or file_hash(archive)!=item['sha256']:raise ValueError('Archive integrity failed: '+item['id'])
        if executable:
            target=runtime/item['id'];note_aside(safe_extract(archive,target));exe=target/item['executable']
            if file_hash(exe)!=item['executable_sha256']:raise ValueError('Executable integrity failed')
            config[item['id']]={'path':str(exe),'sha256':item['executable_sha256'],'version':item['version'],'license':item['license'],'source':item['url']}
        else:
            target=runtime/item['filename']
            if target.resolve()!=archive.resolve():
                # A copy of its own first, then put in place (musiclib.files.place): nothing at the name is written through.
                temp=files.stage_name(target,'.copy')
                try:
                    shutil.copy2(archive,temp);moved=files.place(temp,target,runtime)
                except BaseException:
                    temp.unlink(missing_ok=True);raise
                note_aside([moved] if moved else [])
                files.register(runtime,[target])
            if item['id']=='soundfont':config['soundfont']={'path':str(target),'sha256':item['sha256'],'version':item['version'],'license':item['license'],'source':item['url']}
        receipts.append({**item,'local_archive':str(archive)})
        print('VERIFIED',item['id'],flush=True)
    if not has_vorbis(config['ffmpeg']['path']):
        print('NOTE ffmpeg | no libvorbis encoder: a game loop gets loop.wav but no loop.ogg. With Homebrew, brew install '
              'ffmpeg-full and set up again to a new --config with --ffmpeg "$(brew --prefix ffmpeg-full)/bin/ffmpeg"',flush=True)
    if not args.no_surge:
        install_surge(lock,runtime,cache,args,system,config)
        if config.get('surge') and not args.no_surge_catalog:install_catalog(runtime,cache,args,config)
    files.save_config(args.config,config,'--config')  # never over a bank or record the setup put at that path
    save_receipts(runtime,receipts)
    print('Saved',args.config.resolve())

def save_receipts(runtime,receipts):
    """The receipts take their place as an installed file does (files.place): a dependency_receipts.json the bootstrap
    did not write there, or one edited since, is set aside and named, never written over."""
    receipts_file=Path(runtime)/'dependency_receipts.json';written=files.stage_name(receipts_file,'.json')
    try:
        save_json(written,receipts)
        for moved in (files.place(written,receipts_file,runtime),files.register(runtime,[receipts_file])):
            if moved is not None:print('SET ASIDE',moved,'| bootstrap did not write it there; it is kept under this name',flush=True)
    finally:
        with contextlib.suppress(OSError):os.unlink(written)

if __name__=='__main__':
    files.escape_unprintable()
    try:main()
    except (ValueError,OSError) as e:
        print('ERROR:',e,file=sys.stderr);sys.exit(2)
