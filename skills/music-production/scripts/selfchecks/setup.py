"""selfcheck.py's checks of one area (0.8 step 1.8). The setup: archives, downloads, locks and hosts, prebuilt banks, the configuration and its hashes, pedalboard and Surge XT's catalog, the sources listing.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import argparse
import copy
import io
import json
import os
import shutil
import sys
import tarfile
import time
import zipfile
from bootstrap import safe_extract, safe_extract_tar, surge_platform
from musiclib import audio
from musiclib.model import file_hash, save_json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def fake_board(pylib,files_=None):
    """A pedalboard folder as pip leaves one: the package's files and a dist-info RECORD naming each with its SHA-256
    and size (the wheel format), so surge.board_intact passes it."""
    import base64,hashlib
    pylib=Path(pylib);(pylib/'pedalboard').mkdir(parents=True,exist_ok=True)
    rows=[]
    for name,data in (files_ or {'pedalboard/__init__.py':b'# fake\n'}).items():
        (pylib/name).write_bytes(data)
        digest=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        rows.append(f'{name},sha256={digest},{len(data)}')
    info=pylib/'pedalboard-0.0.0.dist-info';info.mkdir(exist_ok=True)
    (info/'RECORD').write_bytes(('\n'.join(rows+['pedalboard-0.0.0.dist-info/RECORD,,'])+'\n').encode())
    return info/'RECORD'


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    config, rejects, work, xf_bank = S['config'], S['rejects'], S['work'], S['xf_bank']
    def zip_traversal():
        z=work/'bad.zip'
        with zipfile.ZipFile(z,'w') as f:f.writestr('../escaped.txt','must not escape')
        rejects(lambda:safe_extract(z,work/'extract'))
        assert not (work/'escaped.txt').exists()
        # The Linux Surge build is a .tar.gz: a member outside the target or a link is refused; "./" is dropped from
        # the names, only the asked-for prefix is written, and its permission bits are kept off Windows.
        def tar(name,members):
            path=work/name
            with tarfile.open(path,'w:gz') as t:
                for m,data in members:
                    info=tarfile.TarInfo(m);info.mode=0o755
                    if data is None:
                        info.type=tarfile.SYMTYPE;info.linkname='/etc/passwd';t.addfile(info)
                    else:
                        info.size=len(data);t.addfile(info,io.BytesIO(data))
            return path
        rejects(lambda:safe_extract_tar(tar('bad.tar.gz',[('../escaped2.txt',b'x')]),work/'extract_tar'))
        rejects(lambda:safe_extract_tar(tar('link.tar.gz',[('./plugin.vst3/link',None)]),work/'extract_tar'))
        assert not (work/'escaped2.txt').exists()
        good=tar('good.tar.gz',[('./plugin.vst3/Contents/x86_64-linux/plugin.so',b'binary'),('./other.txt',b'left out')])
        safe_extract_tar(good,work/'extract_good','plugin.vst3/')
        out=work/'extract_good'/'plugin.vst3'/'Contents'/'x86_64-linux'/'plugin.so'
        assert out.read_bytes()==b'binary' and not (work/'extract_good'/'other.txt').exists()
        assert os.name=='nt' or out.stat().st_mode&0o777==0o755
        # An install folder that is a link is refused before it is resolved, nothing installed behind it, and a setup
        # refuses a runtime holding a link directly in it: resolved first, the link had become the folder it led to
        # and passed the check after (GPT's security audit of 0.5, S03).
        import subprocess as sp
        from musiclib import files as fz
        behind=work/'extract_behind';behind.mkdir();rtl=work/'extract_runtime';rtl.mkdir();fz.real_runtime(rtl)
        with zipfile.ZipFile(work/'tool.zip','w') as f:f.writestr('bin/tool.exe','the tool')
        linked_folder=sp.run(['cmd','/c','mklink','/J',str(rtl/'tool'),str(behind)],capture_output=True).returncode==0 if os.name=='nt' else (os.symlink(behind,rtl/'tool',target_is_directory=True) or True)
        assert linked_folder
        for through in (lambda:safe_extract(work/'tool.zip',rtl/'tool'),lambda:safe_extract_tar(good,rtl/'tool','plugin.vst3/'),lambda:fz.real_runtime(rtl)):
            try:through();raise AssertionError('a setup went through a link')
            except ValueError as e:assert 'is a link' in str(e),e
        assert not list(behind.iterdir())
        safe_extract(work/'tool.zip',rtl/'plain');assert (rtl/'plain'/'bin'/'tool.exe').read_bytes()==b'the tool'
        # The download cache (the re-review of the audit, N1): a folder inside it that is a link is refused before a
        # folder is made or a download written behind it, as the Surge patches' folders were made behind one; folders
        # above the cache are the user's own path; a cache given as a link is refused by both setups before anything
        # is made.
        import sys,contextlib
        import bootstrap as bs
        mk=lambda at,to:sp.run(['cmd','/c','mklink','/J',str(at),str(to)],capture_output=True).returncode==0 if os.name=='nt' else (os.symlink(to,at,target_is_directory=True) or True)
        dl=work/'dl_cache';dl.mkdir();dl_behind=work/'dl_behind';dl_behind.mkdir()
        assert fz.cache_file(dl,'plain','a','b.fxp')==dl/'plain'/'a'/'b.fxp' and (dl/'plain'/'a').is_dir()
        assert mk(dl/'surge_patches',dl_behind) and mk(dl/'surge_patches_all',dl_behind)
        try:fz.cache_file(dl,'surge_patches','Leads','x.fxp');raise AssertionError('a download went through a link in the cache')
        except ValueError as e:assert 'is a link' in str(e),e
        said=io.StringIO()
        with contextlib.redirect_stdout(said):bs.install_catalog(work/'dl_runtime',dl,argparse.Namespace(offline=True),{})
        assert 'SKIPPED surge_catalog' in said.getvalue() and 'is a link' in said.getvalue() and not list(dl_behind.iterdir()),said.getvalue()[-300:]
        (work/'dl_real'/'inner').mkdir(parents=True);assert mk(work/'dl_above',work/'dl_real')
        assert fz.cache_file(work/'dl_above'/'inner','x','y.bin').parent.is_dir() and (work/'dl_real'/'inner'/'x').is_dir()
        scripts=SCRIPTS
        for argv in (['bootstrap.py','--runtime',str(work/'dl_rt_b'),'--config',str(work/'dl_b.json'),'--archive-cache',str(dl/'surge_patches'),'--offline'],
                     ['fetch_soundbanks.py','--runtime',str(work/'dl_rt_f'),'--config',str(work/'no_config.json'),'--output',str(work/'dl_f.json'),'--archive-cache',str(dl/'surge_patches'),'--offline']):
            done=sp.run([sys.executable,str(scripts/argv[0]),*argv[1:]],capture_output=True,text=True)
            assert done.returncode==2 and 'is a link' in done.stderr and 'Traceback' not in done.stderr and not Path(argv[2]).exists(),(argv[0],done.stderr[-300:])
        assert not list(dl_behind.iterdir())
        # Every pinned Surge build names its archive, hashes and the binary to check; this machine maps to one or none.
        pinned=json.loads((SCRIPTS.parent/'references'/'runtime-lock.json').read_text(encoding='utf-8'))['optional']['surge_xt']
        for key in ('windows-x86_64','linux-x86_64','macos-universal'):
            item=pinned[key]
            assert item['url'].endswith('/'+item['filename']) and len(item['sha256'])==64 and len(item['executable_sha256'])==64
            assert item['executable'].startswith(item['extract']) and item['bytes']>1e7
        assert surge_platform() in (None,'windows-x86_64','linux-x86_64','macos-universal')
        # Both setups find a system program on PATH, never in the working folder unless PATH names it (the security check
        # of 0.10.0: Windows' shutil.which looked there first before Python 3.12), here with which made to answer so
        import shutil
        import fetch_soundbanks as fsb
        tools,here=work/'path_tools',work/'path_here';tools.mkdir();here.mkdir()
        exe='tool.exe' if os.name=='nt' else 'tool'
        for folder in (tools,here):(folder/exe).write_bytes(b'');os.chmod(folder/exe,0o755)
        real_which,old_path,old_cwd=shutil.which,os.environ.get('PATH',''),os.getcwd()
        same=lambda a,b:a is not None and os.path.normcase(os.path.abspath(a))==os.path.normcase(os.path.abspath(b))
        try:
            os.chdir(here);shutil.which=lambda name,*a,**k:str(here/exe)
            for find in (bs.on_path,fsb.on_path):
                os.environ['PATH']=str(tools);assert same(find('tool'),tools/exe),find('tool')
                os.environ['PATH']=str(here)+os.pathsep+str(tools);assert same(find('tool'),here/exe),find('tool')   # PATH names it: the user's own
                os.environ['PATH']=str(work/'path_none');assert find('tool') is None
        finally:
            shutil.which=real_which;os.environ['PATH']=old_path;os.chdir(old_cwd)
        return True
    def surge_catalog():
        # Any patch of the measured catalog is a Surge preset by its id: found by role and measured character (flagged
        # patches left out, dark to bright), falling back by its role, and played only from the full patch set, which
        # bootstrap installs (offline with nothing cached it reports the skip and leaves the configuration without it).
        import contextlib,io,subprocess,types
        import bootstrap
        from musiclib import surge
        from musiclib.audition import label
        from musiclib.sounds import describe,search
        cat=surge.catalog();assert len(cat)>=3000
        assert surge.entry('smooth_lead')['folder']=='patches' and surge.entry('no/such/patch') is None
        pads=search('pad',['warm','slow'],limit=1000);rows=pads['shown']
        assert pads['count']==len(rows)>10 and all(r['role']=='pad' and 'warm' in r['character'] and 'slow' in r['character'] for r in rows)
        assert [r['centroid_hz'] for r in rows]==sorted(r['centroid_hz'] for r in rows)
        assert not any(set(r['flags'])&{'silent on a plain note','did not render','MPE','microtonal','off its written pitch'} for r in rows)
        assert search('pad',limit=1,everything=True)['count']>search('pad',limit=1)['count']
        # A shortlist smaller than the matches spreads over the range and the designers rather than showing the
        # darkest few, and the piece's seed picks within each band (in 0.4.0 one query showed every agent the same
        # first patches).
        every=search('pad',limit=100000)['shown'];few=search('pad',limit=8)['shown']
        assert len(few)==8 and [r['centroid_hz'] for r in few]==sorted(r['centroid_hz'] for r in few)
        assert few[0]['centroid_hz']<=every[len(every)//8]['centroid_hz'] and few[-1]['centroid_hz']>=every[-len(every)//8]['centroid_hz'],few
        assert len({r['source'] for r in few})==8 and '8 of' in search('pad',limit=8)['note']
        one,two=search('pad',limit=8,seed=1)['shown'],search('pad',limit=8,seed=2)['shown']
        assert one==search('pad',limit=8,seed=1)['shown'] and {r['id'] for r in one}!={r['id'] for r in two}
        # A sound is designed by choosing it (0.6): a range of the probe's centroid and of its attack, either end
        # open, and whether its brightness held still over the three playings the catalog takes the median of.
        ranged=search('pad',limit=100000,centroid=(600,900),attack=(.1,.3))['shown']
        assert 0<len(ranged)<len(every) and all(600<=r['centroid_hz']<=900 and .1<=r['attack_s']<=.3 for r in ranged),len(ranged)
        low=search('bass',limit=100000,centroid=(None,120))['shown'];high=search('bass',limit=100000,centroid=(120.5,None))['shown']
        assert low and high and max(r['centroid_hz'] for r in low)<=120<min(r['centroid_hz'] for r in high) and len(low)+len(high)==search('bass',limit=100000)['count']
        # From the command line a range's ends are plain numbers, finite and not under zero, the lower first (a review
        # of 0.6.0: nan-900, 0-inf and --1 were taken as ranges).
        cli=lambda *a:subprocess.run([sys.executable,'-B',str(SCRIPTS.joinpath('studio.py')),'sounds','--role','pad','--json',*a],capture_output=True,text=True)  # noqa: E731
        for bad in ('--centroid=nan-900','--centroid=0-inf','--centroid=--1','--attack=-inf-1','--attack=x-1','--centroid=900-600','--centroid=-','--attack=0.1'):
            r=cli(bad);assert r.returncode==2 and 'Traceback' not in r.stderr and bad.split('=')[0] in r.stderr,(bad,r.returncode,r.stderr[-200:])
        r=cli('--centroid=600-900','--attack=-0.3','--limit','5');assert r.returncode==0 and json.loads(r.stdout)['shown'],r.stderr[-200:]
        steady=search('pad',['steady'],limit=100000)['shown'];moving=search('pad',['moving'],limit=100000)['shown']
        assert steady and moving and len(steady)+len(moving)==len(every) and all(r['centroid_spread_pct']<=10 for r in steady) and all(r['centroid_spread_pct']>10 for r in moving)
        # A patch whose probe gave no centroid (nothing sounded in the held part) has no spread: it is called neither
        # steady nor moving and no brightness, and no range of the centroid finds it (a review of 0.6.0: one such
        # patch carried a spread of -100% and was called steady and dark).
        spread=lambda v:v['measured']['centroid_spread_pct']  # noqa: E731
        assert all(spread(v) is None or spread(v)>=0 for v in cat.values() if 'measured' in v)
        assert all((spread(v) is None)==(not v['measured']['centroid_hz']) for v in cat.values() if 'measured' in v)
        assert all(('steady' in v['character'])==(spread(v) is not None and spread(v)<=10) and ('moving' in v['character'])==(spread(v) is not None and spread(v)>10)
                   for v in cat.values() if 'measured' in v)
        bare=[k for k,v in cat.items() if 'measured' in v and not v['measured']['centroid_hz']]
        assert bare and all(not any(w in cat[k]['character'] for w in ('dark','warm','mid','bright')) for k in bare),bare
        role=cat[bare[0]]['role'];ids=lambda **k:{r['id'] for r in search(role,limit=100000,everything=True,**k)['shown']}  # noqa: E731
        assert bare[0] in ids() and bare[0] not in ids(centroid=(None,400)) and bare[0] not in ids(centroid=(0,None))
        # The licence a patch states for itself stays with it, word for word, and the catalog's origin says so with
        # their number (a review of 0.6.0: the catalog measured again had lost all 78).
        own={k:v['license'] for k,v in cat.items() if 'license' in v}
        origin=json.loads((Path(surge.__file__).resolve().parents[2]/'references'/'surge-catalog.json').read_text(encoding='utf-8'))['origin']['license']
        assert len(own)==78 and all('CC0' in text for text in own.values()) and cat['factory/templates/init_square']['license']=='Licensed under the maximally permissive CC0 license'
        assert 'GPL-3.0-or-later' in origin and f'{len(own)} of the {len(cat):,}' in origin and 'each CC0' in origin,origin
        key=rows[0]['id'];found=surge.entry(key)
        assert found['folder']=='catalog' and found['fallback']=='warm_pad' and describe(key)['measured']['centroid_hz']==rows[0]['centroid_hz']
        dark=next(k for k,v in cat.items() if v['role']=='bass' and v.get('measured',{}).get('centroid_hz',999)<120)
        assert surge.entry(dark)['fallback']=='sub_bass' and rejects(lambda:describe('no/such/patch'))
        t={'id':'pad','surge':{'preset':key}};surge.validate(t)
        assert rejects(lambda:surge.validate({'id':'pad','surge':{'preset':'no/such/patch'}}))
        assert label(('surge',key))=='surge_'+key.replace('/','.') and '/' not in label(('surge',key))
        fake=work/'fake_surge_catalog';fake_board(fake/'pylib')
        binary=fake/'Surge XT.vst3';binary.write_bytes(b'surge')
        cfg={'surge':{'path':str(binary),'sha256':file_hash(binary),'patches':str(fake)},'pedalboard':{'path':str(fake/'pylib')}}
        for where,reason in ((None,'full Surge XT patch set'),(fake/'all','missing or changed')):
            if where:cfg['surge']['catalog']=str(where)
            try:surge.locate(cfg,t);raise AssertionError('located '+key)
            except surge.Unavailable as why:assert reason in str(why),why
        # Whether the patch plays here is part of a Surge part's cache key: a fallback rendered before the full set was
        # installed is not reused once it is.
        plays=[]
        for where in (None,fake/'all'):
            c=copy.deepcopy(cfg);c['surge'].pop('catalog',None)
            if where:c['surge']['catalog']=str(where)
            plays.append(surge.dependencies(c,t)['plays'])
        assert plays[0]!=plays[1] and all(x.startswith('fallback') for x in plays),plays
        real=json.loads(Path(config).read_text(encoding='utf-8')) if config else {}
        if (real.get('surge') or {}).get('catalog'):
            without=copy.deepcopy(real);without['surge'].pop('catalog')
            assert surge.dependencies(real,t)['plays']=='Surge XT' and surge.dependencies(without,t)['plays'].startswith('fallback')
        blank={'surge':{}};said=io.StringIO()
        with contextlib.redirect_stdout(said):
            bootstrap.install_catalog(work/'catalog_runtime',work/'catalog_cache',types.SimpleNamespace(offline=True),blank)
        assert 'catalog' not in blank['surge'] and 'SKIPPED surge_catalog' in said.getvalue(),said.getvalue()
        return {'patches':len(cat),'warm_slow_pads':pads['count']}
    def soundbank_lock():
        import fetch_soundbanks as fs
        lock=json.loads((SCRIPTS.parent/'references'/'soundbank-lock.json').read_text(encoding='utf-8'))
        for item in lock['archives']:
            import urllib.parse
            assert urllib.parse.urlsplit(item['url']).hostname in fs.HOSTS and len(item['sha256'])==64 and len(item['member_sha256'])==64
            assert fs.safe_member(item['member']) and all(fs.safe_member(n) for n in item.get('notices',[]))
        from musiclib.model import digest
        for item in lock['builds']:
            spec=SCRIPTS.parent/'references'/item['spec']
            assert len(item['output_sha256'])==64 and int(item['output_sha256'],16)>=0 and spec.is_file(),item['name']
            # 0.8 step 1.5: each recipe's canonical digest, by which the builder tells the skill's own recipes (their regexes)
            assert item['spec_digest']==digest(json.loads(spec.read_text(encoding='utf-8'))),item['name']
        assert not fs.safe_member('../x.sf2') and not fs.safe_member('/abs.sf2') and not fs.safe_member('C:/x.sf2')
        (work/'crlf.txt').write_bytes(b'line\r\nnext\r\n');(work/'bin.dat').write_bytes(b'\0\r\n')
        lf=__import__('hashlib').sha1(b'blob 10\0line\nnext\n').hexdigest()
        assert lf in fs.git_blob_sha1s(work/'crlf.txt') and len(fs.git_blob_sha1s(work/'bin.dat'))==1
        return {'archives':len(lock['archives']),'builds':len(lock['builds'])}
    def prebuilt_bank():
        import fetch_soundbanks as fs
        import lzma
        import urllib.parse
        # A bank as this project built it is unpacked only when the asset and the bank inside match their locked
        # hashes and size, and is never left half-written; every built bank has an asset and the groups name real banks.
        bank=bytes(range(256))*4096;packed=lzma.compress(bank);assets=work/'prebuilt_assets';assets.mkdir(exist_ok=True)
        (assets/'demo_bank-b3.sf2.xz').write_bytes(packed)
        item={'name':'demo_bank','version':'build b3','output_sha256':__import__('hashlib').sha256(bank).hexdigest()}
        asset={'file':'demo_bank-b3.sf2.xz','bytes':len(packed),'sha256':file_hash(assets/'demo_bank-b3.sf2.xz'),'sf2_bytes':len(bank)}
        runtime=work/'prebuilt_runtime'
        out=fs.install_prebuilt(item,asset,runtime,work,'',True,assets)
        assert out.read_bytes()==bank and fs.built(item,runtime)==out
        out.unlink()
        for wrong_asset,wrong_item in (({**asset,'sha256':'0'*64},item),({**asset,'sf2_bytes':len(bank)-1},item),(asset,{**item,'output_sha256':'0'*64})):
            rejects(lambda:fs.install_prebuilt(wrong_item,wrong_asset,runtime,work,'',True,assets))
        assert [p.name for p in (runtime/'build').iterdir()]==['files.json'],list((runtime/'build').iterdir())
        # A bank of the user's under the installed bank's name (one edited since, or another so named) is set aside and
        # named, not replaced; the bank put there is recorded as the installer's.  (Found by a review of 0.4.0.)
        import contextlib,io
        out.write_bytes(b'MINE');said=io.StringIO()
        with contextlib.redirect_stdout(said):fs.install_prebuilt(item,asset,runtime,work,'',True,assets)
        kept=[p for p in (runtime/'build').iterdir() if '.replaced-' in p.name]
        from musiclib import files as owned
        assert out.read_bytes()==bank and [p.read_bytes() for p in kept]==[b'MINE'] and 'SET ASIDE' in said.getvalue() and out.name in owned.recorded(runtime/'build'),(kept,said.getvalue())
        lock=json.loads((SCRIPTS.parent/'references'/'soundbank-lock.json').read_text(encoding='utf-8'))
        names={i['name'] for i in lock['archives']+lock['builds']};pre=lock['prebuilt']['assets']
        assert set(pre)=={i['name'] for i in lock['builds']} and all(a['file'].endswith('.sf2.xz') and len(a['sha256'])==64 for a in pre.values())
        assert all(set(g)<=names for g in lock['groups'].values()) and set().union(*(lock['groups'][g] for g in ('orchestra','band','world')))==names
        assert fs.requested(lock,'orchestra,rusty')>={'vsco','rusty'} and fs.requested(lock,None) is None
        rejects(lambda:fs.requested(lock,'nonesuch'))
        assert urllib.parse.urlsplit(lock['prebuilt']['release']).hostname in fs.HOSTS
        # A bank published as an archive comes from its unchanged tar.xz repack when that matches, else from the publisher.
        import io,tarfile
        member,notice='Demo SF2/demo.sf2','Demo SF2/LICENSE.txt';tx=assets/'Demo-SF2.tar.xz'
        with tarfile.open(tx,'w:xz') as tar:
            for name,data in ((member,bank),(notice,b'CC0')):
                info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
        arch={'name':'demo_archive','format':'7z','url':'https://github.com/x/y/releases/download/1/Demo-SF2.7z','bytes':1,'sha256':'0'*64,
              'member':member,'member_sha256':item['output_sha256'],'notices':[notice],'license':'CC0','version':'1'}
        mirror={'file':tx.name,'bytes':tx.stat().st_size,'sha256':file_hash(tx),'url':'https://github.com/x/y/releases/download/1/'+tx.name}
        got=fs.install_archive(arch,work/'archive_runtime',work/'archive_cache',True,mirror,assets)
        assert Path(got['path']).read_bytes()==bank and got['source']==mirror['url']
        rejects(lambda:fs.install_archive(arch,work/'archive_runtime2',work/'archive_cache',True,{**mirror,'sha256':'0'*64},assets))
        # A repacked archive with a member outside its folder, or a link, is refused before anything is unpacked.
        for bad in ('../evil.txt','link'):
            bx=assets/f'bad_{bad[-4:]}.tar.xz'
            with tarfile.open(bx,'w:xz') as tar:
                info=tarfile.TarInfo(member);info.size=len(bank);tar.addfile(info,io.BytesIO(bank))
                extra=tarfile.TarInfo(bad)
                if bad=='link':extra.type,extra.linkname=tarfile.SYMTYPE,'../outside'
                tar.addfile(extra,io.BytesIO(b''))
            rejects(lambda:fs._install_archive({**arch,'format':'tar.xz','bytes':bx.stat().st_size,'sha256':file_hash(bx)},work/'archive_runtime3',work/'archive_cache',True,bx))
        assert not (work/'archive_runtime3'/'demo_archive').exists() and not (work/'evil.txt').exists()
        # A link already in the destination, a folder or the bank itself pointing elsewhere, is refused, not written through.
        tx_item={**arch,'format':'tar.xz','bytes':tx.stat().st_size,'sha256':file_hash(tx)};links=0
        for mode in ('folder','file'):
            runtime=work/f'link_runtime_{mode}';target=runtime/'demo_archive';outside=work/f'outside_{mode}'
            target.mkdir(parents=True);outside.mkdir();(outside/'demo.sf2').write_bytes(b'KEEP')
            try:
                if mode=='folder':(target/'Demo SF2').symlink_to(outside,target_is_directory=True)
                else:(target/'Demo SF2').mkdir();(target/'Demo SF2'/'demo.sf2').symlink_to(outside/'demo.sf2')
            except OSError:continue   # no right to make links here (Windows without developer mode)
            rejects(lambda:fs._install_archive(tx_item,runtime,work/'archive_cache',True,tx))
            assert (outside/'demo.sf2').read_bytes()==b'KEEP';links+=1
        mirrors=lock['prebuilt']['archives']
        assert set(mirrors)=={i['name'] for i in lock['archives']} and all(a['file'].endswith('.tar.xz') and len(a['sha256'])==64 for a in mirrors.values())
        return {'groups':{k:len(v) for k,v in lock['groups'].items()},'prebuilt_assets':len(pre),'repacked_archives':len(mirrors),'destination_links_refused':links}
    def relative_banks():
        import subprocess,sys
        here=SCRIPTS;old=work/'cfg_old';new=work/'cfg_new';old.mkdir(exist_ok=True);new.mkdir(exist_ok=True)
        for name in ('fs.exe','ff.exe'):(old/name).write_bytes(name.encode())
        bank=xf_bank();shutil.copy2(bank,old/'own.sf2')
        cfg={k:{'path':n,'sha256':file_hash(old/n)} for k,n in (('fluidsynth','fs.exe'),('ffmpeg','ff.exe'),('soundfont','own.sf2'))}
        cfg['soundfonts']={'named':{'path':'own.sf2','sha256':file_hash(old/'own.sf2')}};save_json(old/'config.json',cfg)
        done=subprocess.run([sys.executable,str(here/'studio.py'),'add-soundfont','--config',str(old/'config.json'),'--name','added','--path',str(bank),
                             '--license','test','--source','test','--version','1','--output',str(new/'config.json')],capture_output=True,text=True)
        assert done.returncode==0,done.stderr
        # The name is lower-case letters, digits and underscores, and not "default" (the configuration's own bank): either
        # is refused before anything is written.  The test joined by `and` passed both (0.8's mutation analysis, 2026-11-15).
        for name in ('default','Bank'):
            done=subprocess.run([sys.executable,str(here/'studio.py'),'add-soundfont','--config',str(old/'config.json'),'--name',name,'--path',str(bank),
                                 '--license','test','--source','test','--version','1','--output',str(new/f'refused_{name}.json')],capture_output=True,text=True)
            assert done.returncode==2 and 'Name must be lower-case' in done.stderr and not (new/f'refused_{name}.json').exists(),(name,done.returncode,done.stderr[-300:])
        loaded=audio.load_config(new/'config.json');assert Path(loaded['soundfonts']['named']['path'])==(old/'own.sf2').resolve()
        # configure checks its bank's tables as add-soundfont does: a file that is no SoundFont is refused, a bank is
        # configured.  (Found by a review of 0.4.0.)
        (old/'not-a-bank.sf2').write_text('plain text',encoding='utf-8')
        for font,want in ((old/'not-a-bank.sf2',2),(bank,0)):
            out=new/f'configured_{want}.json'
            done=subprocess.run([sys.executable,str(here/'studio.py'),'configure','--fluidsynth',str(old/'fs.exe'),'--ffmpeg',str(old/'ff.exe'),
                                 '--soundfont',str(font),'--output',str(out)],capture_output=True,text=True)
            assert done.returncode==want and out.is_file()==(want==0),(font,done.returncode,done.stderr[-300:])
        # A spec, manifest or configuration that is no JSON object is refused with what it should be (a list stopped
        # the command with a traceback); a configuration given as a link is not read through it (it was resolved
        # first; both found by GPT Pro's fifth review of 0.4.0).
        # An object without the fields each reads first is refused the same way (it raised KeyError).
        (old/'list.json').write_text('[]',encoding='utf-8');(old/'empty.json').write_text('{}',encoding='utf-8');(old/'root').mkdir(exist_ok=True)
        for doc,says in (('list.json','JSON object'),('empty.json','needs')):
            for argv in (['soundbank.py','build',str(old/doc),'--root',str(old/'root'),'--output',str(new/'x.sf2'),'--receipt',str(new/'x.json')],
                         ['soundbank.py','split',str(old/doc),'--root',str(old/'root'),'--output',str(new/'x_split')],
                         ['soundbank.py','cut',str(old/doc),'--root',str(old/'root'),'--output',str(new/'x_cut')],
                         ['fetch_soundbanks.py','--config',str(old/doc),'--runtime',str(new/'rt'),'--output',str(new/'x_cfg.json'),'--offline']):
                done=subprocess.run([sys.executable,str(here/argv[0]),*argv[1:]],capture_output=True,text=True)
                assert done.returncode==2 and says in done.stderr and 'Traceback' not in done.stderr,(argv[1],doc,done.returncode,done.stderr[-300:])
        # A bank spec without its name, a configuration with a null path, banks given as a list: refused naming the
        # field, by one shape check for every reader of a configuration (they raised KeyError, TypeError and
        # AttributeError; found by GPT Pro's sixth review of 0.4.0).
        (old/'nameless.json').write_text('{"presets": []}',encoding='utf-8')
        (old/'null_path.json').write_text(json.dumps({'fluidsynth':{'path':None},'ffmpeg':{},'soundfont':{}}),encoding='utf-8')
        (old/'bank_list.json').write_text(json.dumps({'soundfonts':[]}),encoding='utf-8')
        for argv,says in ((['soundbank.py','build',str(old/'nameless.json'),'--root',str(old/'root'),'--output',str(new/'y.sf2'),'--receipt',str(new/'y.json')],'"name"'),
                          (['studio.py','doctor','--config',str(old/'null_path.json')],'"fluidsynth"'),
                          (['studio.py','add-soundfont','--config',str(old/'bank_list.json'),'--path',str(old/'own.sf2'),'--output',str(new/'z.json'),
                            '--name','extra','--license','test','--source','test','--version','1'],'"soundfonts"')):
            done=subprocess.run([sys.executable,str(here/argv[0]),*argv[1:]],capture_output=True,text=True)
            assert done.returncode==2 and says in done.stderr and 'Traceback' not in done.stderr,(argv[1],done.returncode,done.stderr[-300:])
        assert not [n for n in ('y.sf2','y.json','z.json') if (new/n).exists()]
        linked_cfg=False
        try:os.symlink(old/'config.json',old/'linked_config.json');linked_cfg=True
        except (OSError,NotImplementedError):pass  # symbolic links need a privilege on Windows
        if linked_cfg:assert rejects(lambda:audio.load_config(old/'linked_config.json'))
        # fetch_soundbanks runs the configured FFmpeg only if it is the file the configuration's hash names, as a render
        # does, and says so before it makes anything: it ran the file as found (GPT's security audit of 0.5, S01).
        (old/'some_program.exe').write_bytes(b'not ffmpeg');save_json(old/'unverified.json',{'ffmpeg':{'path':str(old/'some_program.exe'),'sha256':'0'*64}})
        done=subprocess.run([sys.executable,str(here/'fetch_soundbanks.py'),'--config',str(old/'unverified.json'),'--runtime',str(new/'rt_unverified'),'--output',str(new/'unverified_out.json'),'--offline'],capture_output=True,text=True)
        assert done.returncode==2 and 'hash mismatch' in done.stderr and 'Traceback' not in done.stderr and not (new/'rt_unverified').exists(),done.stderr[-300:]
        audio.verify_tool({'ffmpeg':{'path':str(old/'some_program.exe'),'sha256':file_hash(old/'some_program.exe')}},'ffmpeg')
        return {'named_bank':'still found','configure_refuses_a_file_that_is_no_bank':True,'linked_config_refused':linked_cfg}
    def short_downloads():
        import http.server,threading
        import fetch_soundbanks as fs
        body=b'x'*1000
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path=='/redirect':
                    self.send_response(302);self.send_header('Location','https://example.invalid/bank.sf2');self.end_headers();return
                self.send_response(200);self.send_header('Content-Length','1000');self.end_headers()
                self.wfile.write(body[:400] if self.path=='/short' else body)
            def log_message(self,*a):pass
        server=http.server.HTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}';hosts=fs.HOSTS
        try:
            fs.HOSTS=hosts|{'127.0.0.1'};dest=work/'dl.bin'
            # A redirect to a host off the list is refused before any request goes there.
            try:fs._fetch_once(base+'/redirect',dest,None,10**6,None);raise AssertionError('followed a redirect off the list')
            except ValueError as e:assert 'not allowed' in str(e),e
            try:fs._fetch_once(base+'/short',dest,None,10**6,None);raise AssertionError('kept a short download')
            except fs.Damaged:pass
            assert not dest.exists() and not dest.with_name('dl.bin.partial').exists()
            # The bootstrap's downloads too: one the server cuts short is a Short, tried again, and leaves nothing.
            import bootstrap;bh=bootstrap.HOSTS;bootstrap.HOSTS=bh+('127.0.0.1',)
            try:
                try:bootstrap._download_once({'url':base+'/short','bytes':1000,'sha256':'0'*64},dest);raise AssertionError('kept a short download')
                except bootstrap.Short:pass
            finally:bootstrap.HOSTS=bh
            assert not dest.exists() and not list(work.glob('.dl.bin.*'))
            dest.write_bytes(b'damaged')
            fs.fetch=lambda url,d,size=None,max_bytes=0,tries=4,check=None:fs._fetch_once(base+'/ok',d,size,10**6,check)
            fs.cached('https://example.invalid/ok',dest,False,1000,lambda f:f.read_bytes()==body)
            assert dest.read_bytes()==body
        finally:
            fs.HOSTS=hosts;server.shutdown()
            import importlib;importlib.reload(fs)
        # A damaged cached wheel is set aside and the wheel fetched again from its locked address (bootstrap.download,
        # stood in for here), and that is the file handed back.
        import bootstrap,hashlib
        good=b'pedalboard wheel';name=f'pedalboard-0.9.26-{bootstrap.wheel_tags()[0]}.whl';wc=work/'wheel_cache';wc.mkdir(exist_ok=True)
        (wc/name).write_bytes(b'damaged')
        lock={'optional':{'pedalboard':{'version':'0.9.26','wheels':{name:{'url':'https://files.pythonhosted.org/x/'+name,'bytes':len(good),'sha256':hashlib.sha256(good).hexdigest()}}}}}
        real=bootstrap.download
        def fake(item,dest,offline):
            assert item['url'].endswith(name) and not offline
            dest.write_bytes(good)
        try:
            bootstrap.download=fake
            path,meta=bootstrap.pedalboard_wheel(lock,wc,False)
        finally:bootstrap.download=real
        assert path==wc/name and path.read_bytes()==good and file_hash(path)==meta['sha256'] and len(list(wc.glob(name+'.replaced-*')))==1
        # bootstrap.download tries a server error, a download cut short and a timeout again, after 3, 6 and 12 s, as
        # fetch_soundbanks.fetch does, and nothing else: one HTTP 504 from GitHub's servers stopped a whole install,
        # without saying which download (found by CI).
        import types,urllib.error
        item={'url':'https://github.com/x/y.zip','bytes':len(good),'sha256':hashlib.sha256(good).hexdigest()}
        status=lambda code:urllib.error.HTTPError(item['url'],code,'x',{},None)
        def failing(errors):
            left=list(errors)
            def once(item,dest):
                if left:raise left.pop(0)
                dest.write_bytes(good)
            return once
        waits=[];real_once=bootstrap._download_once
        try:
            bootstrap.time=types.SimpleNamespace(sleep=waits.append)
            for errors,ok,paused in (((status(504),bootstrap.Short('cut'),TimeoutError('slow')),True,[3,6,12]),((status(404),),False,[]),
                                     ((ValueError('the download does not match the lock'),),False,[]),((status(503),)*4,False,[3,6,12]),
                                     ((FileExistsError(17,'taken meanwhile'),),False,[])):
                waits.clear();dest=work/'retried.bin';bootstrap._download_once=failing(errors)
                if dest.exists():dest.unlink()
                try:bootstrap.download(item,dest,False);assert ok and dest.read_bytes()==good,errors
                except (OSError,ValueError):assert not ok,errors
                assert waits==paused,(errors,waits)
        finally:bootstrap.time=time;bootstrap._download_once=real_once
        return {'short_read':'tried again, never cached','damaged_cache':'downloaded again','damaged_wheel':'replaced',
                'bootstrap_retries':'server errors, short reads and timeouts, after 3, 6 and 12 s'}
    def bootstrap_receipts_set_aside_what_it_did_not_write():
        # The dependency receipts take their place as an installed file does: a dependency_receipts.json bootstrap did
        # not write, or one edited since, is set aside under a new name and kept; bootstrap's own is replaced.  (Found by
        # the second review of 0.4.0: an unrelated file there was written over.)
        import bootstrap,contextlib,io
        rt=work/'receipts_runtime';rt.mkdir();(rt/'dependency_receipts.json').write_text('{"mine": true}',encoding='utf-8')
        said=io.StringIO();aside=lambda:sorted(x for x in rt.iterdir() if '.replaced-' in x.name)
        with contextlib.redirect_stdout(said):bootstrap.save_receipts(rt,[{'id':'a'}])
        assert len(aside())==1 and json.loads(aside()[0].read_text(encoding='utf-8'))=={'mine':True} and 'SET ASIDE' in said.getvalue(),said.getvalue()
        assert json.loads((rt/'dependency_receipts.json').read_text(encoding='utf-8'))==[{'id':'a'}]
        with contextlib.redirect_stdout(said):bootstrap.save_receipts(rt,[{'id':'b'}])
        assert len(aside())==1 and json.loads((rt/'dependency_receipts.json').read_text(encoding='utf-8'))==[{'id':'b'}]
        (rt/'dependency_receipts.json').write_text('[{"id": "b", "edited": true}]',encoding='utf-8')
        with contextlib.redirect_stdout(said):bootstrap.save_receipts(rt,[{'id':'c'}])
        assert len(aside())==2 and json.loads((rt/'dependency_receipts.json').read_text(encoding='utf-8'))==[{'id':'c'}]
        assert not [x for x in rt.iterdir() if x.name.startswith('.')],sorted(x.name for x in rt.iterdir())
        # A file, folder or link set aside never takes a name another setup took since the look (the look is made to see
        # the name free once): os.replace put it over the file set aside first, the only copy.  And a second setup
        # into a runtime another is installing in is refused, and may run once that has ended.  (GPT's security audit
        # of 0.5, S05.)
        import subprocess,sys
        from musiclib import files as fz
        set_aside={}
        for kind in ('file','folder','link'):
            base=work/f'aside_{kind}';base.mkdir();dest=base/'bank.sf2';first=base/'bank.sf2.replaced-STAMP';first.write_bytes(b'set aside first')
            if kind=='folder':dest.mkdir();(dest/'in.txt').write_bytes(b'second')
            elif kind=='file':dest.write_bytes(b'second')
            else:
                try:os.symlink(base/'nowhere',dest)
                except (OSError,NotImplementedError):continue
            look,stamp,lied=fz.occupied,fz.time.strftime,[]
            def once(path,first=first,lied=lied,look=look):
                if Path(path)==first and not lied:
                    lied.append(1);return False
                return look(path)
            fz.occupied,fz.time.strftime=once,(lambda *a:'STAMP')
            try:moved=fz.aside(dest)
            finally:fz.occupied,fz.time.strftime=look,stamp
            assert lied and first.read_bytes()==b'set aside first' and moved.name=='bank.sf2.replaced-STAMP-1' and not fz.occupied(dest),(kind,sorted(x.name for x in base.iterdir()))
            assert ((moved/'in.txt').read_bytes()==b'second' if kind=='folder' else os.path.islink(moved) if kind=='link' else moved.read_bytes()==b'second'),kind
            set_aside[kind]=True
        code=('import sys;sys.path.insert(0,sys.argv[1]);from musiclib import files\n'
              'try:\n with files.installing(sys.argv[2]):print("held")\nexcept ValueError as e:print("refused",e)')
        other=lambda:subprocess.run([sys.executable,'-c',code,str(SCRIPTS),str(rt)],capture_output=True,text=True).stdout
        with fz.installing(rt) as held_runtime:
            assert held_runtime and 'another setup' in other()
        assert other().startswith('held') and not (rt/'work.lock').exists()
        # Where the lock cannot be taken (here a file of the user's under its name) the setup is told so, to say it,
        # and the file stays as it is (the re-review of the audit, N2).
        (rt/'work.lock').write_text('mine',encoding='utf-8')
        with fz.installing(rt) as held_runtime:assert held_runtime is False
        assert (rt/'work.lock').read_text(encoding='utf-8')=='mine'
        # The configuration's path is checked before the install and again when it is written: files.json is refused,
        # and a path the install put a bank at meanwhile keeps the bank (it was written over with the configuration;
        # found by GPT Pro's third review of 0.4.0).
        from musiclib import files as fs
        assert rejects(lambda:fs.check_config_path(rt/'files.json','--config'))
        bank=rt/'demo.sf2';fs.check_config_path(bank,'--config');bank.write_bytes(b'RIFF a bank')
        assert rejects(lambda:fs.save_config(bank,{'a':1},'--config')) and bank.read_bytes()==b'RIFF a bank'
        fs.save_config(rt/'config.json',{'a':1},'--config');assert json.loads((rt/'config.json').read_text(encoding='utf-8'))=={'a':1}
        return {'set_aside':len(aside()),'own_replaced':True,'config_never_over_an_installed_file':True,'aside_never_over_another':sorted(set_aside),'second_setup_refused':True}
    def delete_sources_takes_only_the_installers_files():
        # --delete-sources removes a download or a sample only while it is the installer's own (its locked size and
        # hash, or the git blob hash of the tree listing); a changed archive and a file put among the samples stay.
        import contextlib,hashlib,io
        import fetch_soundbanks as fb
        rt=work/'delete_sources'/'runtime';cache=rt/'cache';sources=rt/'sources';cache.mkdir(parents=True);sources.mkdir()
        good,bad=cache/'good.zip',cache/'bad.zip';good.write_bytes(b'archive');bad.write_bytes(b'changed!')
        commit='c'*40;folder=sources/f'samples-{commit[:12]}';(folder/'wav').mkdir(parents=True)
        (folder/'wav'/'a.wav').write_bytes(b'note a');(folder/'wav'/'mine.wav').write_bytes(b'user')
        blob=lambda b:hashlib.sha1(b'blob %d\0'%len(b)+b).hexdigest()
        listed=[('wav/a.wav',blob(b'note a'),6),('wav/mine.wav',blob(b'theirs'),6)]
        save_json(sources/f'someone_samples_{commit}_tree.json',{'sha':commit,'tree':[{'path':q,'type':'blob','sha':h,'size':n} for q,h,n in listed]})
        lock={'archives':[{'name':'good','url':'https://example.org/good.zip','sha256':hashlib.sha256(b'archive').hexdigest(),'bytes':7},
                          {'name':'bad','url':'https://example.org/bad.zip','sha256':hashlib.sha256(b'original').hexdigest(),'bytes':8}],
              'builds':[{'name':'samples','kind':'git','repository':'someone/samples','commit':commit,'paths':['wav/'],
                         'samples':2,'samples_sha256':fb.sample_digest(listed)}]}
        said=io.StringIO()
        with contextlib.redirect_stdout(said):fb.delete_sources(lock,None,rt,cache)
        assert not good.exists() and bad.is_file() and not (folder/'wav'/'a.wav').exists() and (folder/'wav'/'mine.wav').is_file(),said.getvalue()
        assert said.getvalue().count('Kept ')==2,said.getvalue()
        return {'deleted':2,'kept':2}
    def pedalboard_checked_against_its_record():
        # pedalboard runs Surge in this process's Python, so it must be the files pip installed: each file the RECORD
        # lists with its SHA-256 and size, no code file it does not list, and the RECORD bootstrap saw.
        import hashlib
        from musiclib import surge
        lib=work/'board_cases'/'pylib';record=fake_board(lib,{'pedalboard/__init__.py':b'x = 1\n','pedalboard/core.py':b'y = 2\n'})
        assert surge.board_intact(lib,hashlib.sha256(record.read_bytes()).hexdigest())
        surge.VERIFIED_BOARD.clear();assert not surge.board_intact(lib,'0'*64)
        (lib/'pedalboard'/'core.py').write_bytes(b'y = 3\n');surge.VERIFIED_BOARD.clear();assert not surge.board_intact(lib)
        (lib/'pedalboard'/'core.py').write_bytes(b'y = 2\n');(lib/'pedalboard'/'extra.py').write_bytes(b'z = 1\n')
        surge.VERIFIED_BOARD.clear();assert not surge.board_intact(lib)
        (lib/'pedalboard'/'extra.py').unlink();surge.VERIFIED_BOARD.clear();assert surge.board_intact(lib)
        return {'changed_added_and_other_record_refused':True}
    def source_listing_must_name_the_pinned_samples():
        # A source build takes from its listing only the samples the lock pins (each path with its blob hash and size):
        # a listing that adds a path running out of the sample folder, or changes a size, is refused before anything is
        # fetched, and the files are fetched no larger than their pinned size.
        import fetch_soundbanks as fb
        listing={'sha':'c'*40,'tree':[{'path':'wav/a.wav','type':'blob','sha':'1'*40,'size':10},{'path':'wav/b.wav','type':'blob','sha':'2'*40,'size':20},
                                     {'path':'docs/readme.txt','type':'blob','sha':'3'*40,'size':5}]}
        item={'name':'demo','paths':['wav/'],'samples':2,'samples_sha256':fb.sample_digest([('wav/a.wav','1'*40,10),('wav/b.wav','2'*40,20)])}
        assert fb.pinned_samples(item,listing)==[('wav/a.wav','1'*40,10),('wav/b.wav','2'*40,20)]
        out=copy.deepcopy(listing);out['tree'].append({'path':'wav/../../../scripts/soundbank.py','type':'blob','sha':'4'*40,'size':9})
        grown=copy.deepcopy(listing);grown['tree'][0]['size']=10**9
        cut=copy.deepcopy(listing);cut['truncated']=True
        for bad in (out,grown,cut):rejects(lambda bad=bad:fb.pinned_samples(item,bad))
        assert not fb.safe_member('wav/../x') and not fb.safe_member('C:/x.sf2') and not fb.safe_member('wav/a\0.wav') and fb.safe_member('wav/a b.wav')
        lock=json.loads((SCRIPTS.parent/'references'/'soundbank-lock.json').read_text(encoding='utf-8'))
        assert all(len(b.get('samples_sha256',''))==64 and b['samples']>0 for b in lock['builds'] if b.get('kind')!='split')
        return {'refused':3}
    def pedalboard_wheel_fetched_by_its_lock():
        # The wheel is the lock's best one for this Python by pip's own tag ranking, taken from the cache while its
        # bytes match the lock, else fetched from its locked address (bootstrap.download: at most its locked size,
        # hashed as it arrives); offline with nothing cached there is none, and a damaged copy is set aside.
        import contextlib,hashlib,io
        import bootstrap
        tags=bootstrap.wheel_tags();assert tags,'pip ranks no wheel tags here'
        name=f'pedalboard-0.0.0-{tags[0]}.whl';data=b'not a real wheel'
        lock={'optional':{'pedalboard':{'version':'0.0.0','wheels':{name:{'url':'https://files.pythonhosted.org/x/'+name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)},
                                                                     'pedalboard-0.0.0-cp27-cp27m-win32.whl':{'url':'https://files.pythonhosted.org/x/old.whl','sha256':'0'*64,'bytes':1}}}}}
        cache=work/'wheel_cache_lock';cache.mkdir()
        assert bootstrap.pedalboard_wheel(lock,cache,offline=True)==(None,None)
        (cache/name).write_bytes(data);found,w=bootstrap.pedalboard_wheel(lock,cache,offline=True)
        assert found==cache/name and w['bytes']==len(data)
        (cache/name).write_bytes(b'damaged');said=io.StringIO()
        with contextlib.redirect_stdout(said):assert bootstrap.pedalboard_wheel(lock,cache,offline=True)==(None,None)
        assert 'set aside' in said.getvalue() and len(list(cache.glob(name+'.replaced-*')))==1
        return {'tag':tags[0]}
    def a_bank_fluidsynth_is_not_safe_with_is_refused():
        # 0.9.2 (design-0.9.2.md, A1): a modulator's destination past FluidSynth's 63 generators writes outside a voice in
        # FluidSynth up to 2.6.2 (CVE-2026-111123; 0.10 pins 2.6.3, and a system's may be older), so no route hands such a
        # bank to it: add-soundfont, configure, doctor, and a render or audition, whatever the configuration says.  61 and
        # 62 are FluidSynth's own and play.
        import struct,subprocess,sys
        from make_example import example
        from musiclib import bankcheck
        from musiclib.render import module_closure,SYNTHESIS
        assert 'bankcheck.py' not in module_closure(SYNTHESIS),'the check must not change what a cached synthesis depends on'
        here=SCRIPTS;w=work/'unsafe_bank';w.mkdir();bank=xf_bank();whole=bank.read_bytes()
        def table(name):
            """Where the bank's table `name` starts, walked as the file is laid out."""
            with open(bank,'rb') as f:
                from musiclib.sf2 import _chunks
                for cid,off,size in _chunks(f,12,len(whole)):
                    f.seek(off)
                    if cid==b'LIST' and f.read(4)==b'pdta':
                        return next(t for sub,t,_ in _chunks(f,off+4,off+size) if sub==name)
        def crafted(name,dest,label=None):
            raw=bytearray(whole);struct.pack_into('<H',raw,table(name)+2,dest)
            out=w/(label or f'{name.decode()}_{dest}.sf2');out.write_bytes(raw);return out
        bankcheck.refuse_unsafe(bank)
        for name in (b'pmod',b'imod'):
            for dest in (0,60,61,62):bankcheck.refuse_unsafe(crafted(name,dest))
            for dest in (63,64,255,256,319,0x8000,0xFFFF):
                rejects(lambda:bankcheck.refuse_unsafe(crafted(name,dest)))
        # A chunk of odd size, padded as RIFF pads it: a walk that pads reads the tables after it, and FluidSynth's, which does not, reads others.
        with open(bank,'rb') as f:
            from musiclib.sf2 import _chunks
            at=next(off-8 for cid,off,_ in _chunks(f,12,len(whole)) if cid==b'LIST' and (f.seek(off),f.read(4))[1]==b'pdta')
        odd=bytearray(whole[:at]+b'JUNK'+struct.pack('<I',1)+b'x'+b'\0'+whole[at:]);struct.pack_into('<I',odd,4,len(odd)-8);(w/'odd.sf2').write_bytes(odd)
        rejects(lambda:bankcheck.refuse_unsafe(w/'odd.sf2'))
        # A file that does not hold what its RIFF header says, the preset tables past the end it declares among them: FluidSynth compares the two in 32 bits.
        past=bytearray(whole);struct.pack_into('<I',past,4,at-8)
        for name,raw in (('longer',whole+bytes(2)),('shorter',whole[:-2]),('tables_past_its_end',past)):
            (w/f'{name}.sf2').write_bytes(raw);rejects(lambda:bankcheck.refuse_unsafe(w/f'{name}.sf2'))
        # Default modulators (INFO/DMOD): FluidSynth reads them through the same importer, so the same bound holds, and sound ones pass.
        with open(bank,'rb') as f:
            info,info_size=next((off,size) for cid,off,size in _chunks(f,12,len(whole)) if cid==b'LIST' and (f.seek(off),f.read(4))[1]==b'INFO')
        def with_dmod(dest):
            body=struct.pack('<HHhHH',2,dest,10,0,0)+bytes(10);sub=b'DMOD'+struct.pack('<I',len(body))+body
            raw=bytearray(whole[:info+info_size]+sub+whole[info+info_size:]);struct.pack_into('<I',raw,info-4,info_size+len(sub));struct.pack_into('<I',raw,4,len(raw)-8)
            out=w/f'dmod_{dest}.sf2';out.write_bytes(raw);return out
        for dest in (0,62):bankcheck.refuse_unsafe(with_dmod(dest))
        for dest in (63,255,256,0xFFFF):rejects(lambda:bankcheck.refuse_unsafe(with_dmod(dest)))
        # The first pdta list begins with the nine tables in FluidSynth's order: its count of the bytes left is 32 bits, so a table of over 2 GiB can stand past the
        # end of a list and FluidSynth reads on into it.  Here, at a small size, the same layout: the tables outside an empty list, a clean list after them.
        size=struct.unpack_from('<I',whole,at+4)[0];tail=at+8+size;inner=whole[at+12:tail]
        def rebuilt(name,data):
            raw=bytearray(whole[:at]+data+whole[tail:]);struct.pack_into('<I',raw,4,len(raw)-8);(w/name).write_bytes(raw);return w/name
        swapped=bytearray(whole);swapped[table(b'pbag')-8:table(b'pbag')-4]=b'pgen';swapped[table(b'pgen')-8:table(b'pgen')-4]=b'pbag';(w/'order.sf2').write_bytes(swapped)
        rejects(lambda:bankcheck.refuse_unsafe(w/'order.sf2'))
        outside=bytearray(inner);struct.pack_into('<H',outside,table(b'pmod')-(at+12)+2,200)
        rejects(lambda:bankcheck.refuse_unsafe(rebuilt('past_the_list.sf2',b'LIST'+struct.pack('<I',4)+b'pdta'+bytes(outside)+whole[at:tail])))
        extra=b'JUNK'+struct.pack('<I',2)+b'ab'   # what FluidSynth never reads plays: more after the nine tables, and a second list
        bankcheck.refuse_unsafe(rebuilt('more_in_the_list.sf2',b'LIST'+struct.pack('<I',size+len(extra))+whole[at+8:tail]+extra))
        bankcheck.refuse_unsafe(rebuilt('second_list.sf2',whole[at:tail]+b'LIST'+struct.pack('<I',4)+b'pdta'))
        for name in (b'pmod',b'imod'):   # a table's size that is no whole number of records, the nine tables still in their order
            t=table(name);n=struct.unpack_from('<I',whole,t-4)[0];body=bytearray(whole[at:t+n]+bytes(2)+whole[t+n:tail])
            struct.pack_into('<I',body,4,size+2);struct.pack_into('<I',body,t-4-at,n+2)
            try:bankcheck.refuse_unsafe(rebuilt('not_whole.sf2',bytes(body)));raise AssertionError('a table of no whole number of records passed')
            except ValueError as e:assert 'table size' in str(e),e
        unsafe=crafted(b'imod',63,'unsafe.sf2');tools=lambda:{k:{'path':str(w/n),'sha256':file_hash(w/n)} for k,n in (('fluidsynth','fs.exe'),('ffmpeg','ff.exe'))}
        for n in ('fs.exe','ff.exe'):(w/n).write_bytes(n.encode())
        run=lambda *a:subprocess.run([sys.executable,'-X','utf8',str(here/'studio.py'),*map(str,a)],capture_output=True,text=True,encoding='utf-8')
        clean_cfg=w/'clean.json';save_json(clean_cfg,{**tools(),'soundfont':{'path':str(bank),'sha256':file_hash(bank)}})
        said=run('add-soundfont','--config',clean_cfg,'--name','unsafe','--path',unsafe,'--license','x','--source','x','--version','1','--output',w/'added.json')
        assert said.returncode==2 and 'CVE-2026-111123' in said.stderr and not (w/'added.json').exists(),said.stderr[-300:]
        said=run('configure','--fluidsynth',w/'fs.exe','--ffmpeg',w/'ff.exe','--soundfont',unsafe,'--output',w/'configured.json')
        assert said.returncode==2 and 'CVE-2026-111123' in said.stderr and not (w/'configured.json').exists(),said.stderr[-300:]
        # A configuration written by hand: doctor names the bank; a render and an audition stop before any program runs (fs.exe is no program).
        entry={'path':str(unsafe),'sha256':file_hash(unsafe)}
        save_json(w/'as_default.json',{**tools(),'soundfont':entry})
        save_json(w/'as_named.json',{**tools(),'soundfont':{'path':str(bank),'sha256':file_hash(bank)},'soundfonts':{'unsafe':entry}})
        for cfg in ('as_default.json','as_named.json'):
            said=run('doctor','--config',w/cfg);assert said.returncode==2 and 'CVE-2026-111123' in said.stderr,said.stderr[-300:]
        q=example();sampled=next(t for t in q['tracks'] if t['engine']=='soundfont' and t['notes']);save_json(w/'plays_default.json',q)
        said=run('render',w/'plays_default.json','--output',w/'r_default','--config',w/'as_default.json');assert said.returncode==2 and 'CVE-2026-111123' in said.stderr,said.stderr[-300:]
        q=example();next(t for t in q['tracks'] if t['id']==sampled['id'])['soundfont']='unsafe';save_json(w/'plays_named.json',q)
        said=run('render',w/'plays_named.json','--output',w/'r_named','--config',w/'as_named.json');assert said.returncode==2 and 'CVE-2026-111123' in said.stderr,said.stderr[-300:]
        said=run('audition',w/'plays_default.json','--track',sampled['id'],'--sounds','soundfont:unsafe:0:0','--bars','1-2','--output',w/'aud','--config',w/'as_named.json')
        assert said.returncode==2 and 'CVE-2026-111123' in said.stderr and not list((w/'aud').glob('[0-9]*')),said.stderr[-300:]
        return {'destinations_refused':14,'routes':6}
    found = {'a_bank_fluidsynth_is_not_safe_with_is_refused': a_bank_fluidsynth_is_not_safe_with_is_refused, 'archive_cannot_escape_destination': zip_traversal, 'surge_catalog_patch_by_id_search_and_install': surge_catalog, 'soundbank_lock_hosts_hashes_and_member_paths': soundbank_lock, 'prebuilt_banks_unpack_only_when_they_match_the_lock': prebuilt_bank, 'a_config_written_elsewhere_keeps_relative_banks': relative_banks, 'a_short_or_damaged_download_is_never_kept': short_downloads, 'bootstrap_receipts_set_aside_what_it_did_not_write': bootstrap_receipts_set_aside_what_it_did_not_write, 'delete_sources_takes_only_the_installers_files': delete_sources_takes_only_the_installers_files, 'pedalboard_checked_against_its_record': pedalboard_checked_against_its_record, 'source_listing_must_name_the_pinned_samples': source_listing_must_name_the_pinned_samples, 'pedalboard_wheel_fetched_by_its_lock': pedalboard_wheel_fetched_by_its_lock}
    if config:
        def bad_hash():
            cfg=json.loads(Path(config).read_text(encoding='utf-8'))
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            cfg['soundfont']['sha256']='0'*64;save_json(work/'bad_config.json',cfg);rejects(lambda:audio.load_config(work/'bad_config.json'))
            return True
        def read_by_another_skill():
            # 0.9 step 5.  A sound-effects skill built beside this one uses it through two things only, the
            # configuration file and `studio.py doctor` (it imports nothing; its own contract lists the rest).  What it
            # reads is pinned here, so that a change on this side fails here first:
            # - the entries `ffmpeg`, `fluidsynth`, `soundfont` and every `soundfonts.<name>`, each with `path`,
            #   `sha256` and `license` as text;
            # - `scripts/studio.py` in the skill's folder, and `doctor --config` ending 0 where the setup passes and
            #   otherwise where a file is not the one the configuration names;
            # - FFmpeg's coders and filters it encodes, decodes and measures with;
            # - the first word of the licence of every bank the setup installs (it plays a bank only where that says
            #   the sounds made with it ask no credit).
            import subprocess,sys
            cfg=json.loads(Path(config).read_text(encoding='utf-8'))
            entries=[('ffmpeg',cfg['ffmpeg']),('fluidsynth',cfg['fluidsynth']),('soundfont',cfg['soundfont']),*((f'soundfonts.{k}',v) for k,v in (cfg.get('soundfonts') or {}).items())]
            for name,e in entries:
                assert all(isinstance(e.get(k),str) and e[k] for k in ('path','sha256','license')),(name,sorted(e))
            studio=SCRIPTS/'studio.py';assert studio.is_file()
            run=lambda c:subprocess.run([sys.executable,str(studio),'doctor','--config',str(c)],capture_output=True,text=True,encoding='utf-8',errors='replace')
            ok=run(config);assert ok.returncode==0,ok.stderr[-300:]
            # 0.9.2 (the walkthrough of 0.9.1, 12): doctor passed where still and video could not run, so it names Pillow's state.
            assert any(x.startswith('Pillow') for x in ok.stdout.splitlines()),ok.stdout[-300:]
            without=subprocess.run([sys.executable,'-X','utf8','-c',f"import sys,runpy;sys.modules['PIL']=None;sys.argv=['studio.py','doctor','--config',{str(config)!r}];sys.path.insert(0,{str(SCRIPTS)!r});runpy.run_path({str(studio)!r},run_name='__main__')"],capture_output=True,text=True,encoding='utf-8',errors='replace')
            assert without.returncode==0 and 'Pillow: not installed; only still and video need it' in without.stdout,without.stdout[-300:]+without.stderr[-300:]
            old=subprocess.run([sys.executable,'-X','utf8','-c',f"import sys,runpy,types;m=types.ModuleType('PIL');m.__version__='9.5.0';sys.modules['PIL']=m;sys.argv=['studio.py','doctor','--config',{str(config)!r}];sys.path.insert(0,{str(SCRIPTS)!r});runpy.run_path({str(studio)!r},run_name='__main__')"],capture_output=True,text=True,encoding='utf-8',errors='replace')
            assert old.returncode==0 and 'Pillow 9.5.0 (still and video need 10.1 or newer' in old.stdout,old.stdout[-300:]+old.stderr[-300:]
            wrong=dict(cfg)
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);wrong[key]={**cfg[key],'path':str(value if value.is_absolute() else Path(config).resolve().parent/value)}
            wrong['soundfonts']={};wrong.pop('surge',None);wrong.pop('pedalboard',None);wrong['soundfont']={**wrong['soundfont'],'sha256':'0'*64}
            save_json(work/'contract_wrong.json',wrong);assert run(work/'contract_wrong.json').returncode!=0
            ffmpeg=audio.load_config(config)['ffmpeg']['path']
            listed={kind:subprocess.run([ffmpeg,'-hide_banner',f'-{kind}'],capture_output=True,text=True,errors='replace').stdout for kind in ('encoders','decoders','filters')}
            has=lambda kind,name:any(name in line.split() for line in listed[kind].splitlines())
            # libvorbis only where this FFmpeg has it: a build without it is a setup the skill supports (doctor
            # passes, a loop is delivered as WAV), and the check failed there (the review of 0.9's step 5)
            from bootstrap import has_vorbis
            vorbis=('libvorbis',) if has_vorbis(ffmpeg) else ()
            missing=[(k,n) for k,names in (('encoders',('pcm_s16le','pcm_s24le','pcm_f32le',*vorbis,'libmp3lame','flac')),('decoders',('vorbis','mp3','flac')),('filters',('ebur128','aresample'))) for n in names if not has(k,n)]
            assert not missing,missing
            lock=json.loads((SCRIPTS.parent/'references'/'soundbank-lock.json').read_text(encoding='utf-8'))
            first={i['name']:str(i.get('license','')) for k in ('archives','builds') for i in lock[k]}
            other={k:v[:40] for k,v in first.items() if not v.startswith(('CC0','University of Iowa','Unlicense','MIT'))}
            assert first and not other,other
            return {'entries':len(entries),'locked_banks':len(first),'libvorbis':bool(vorbis)}
        found.update({'dependency_hash_mismatch_stops_before_render': bad_hash, 'another_skill_reads_the_configuration_and_doctor': read_by_another_skill})
    return found
