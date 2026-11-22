"""selfcheck.py's checks of one area (0.8 step 1.8). The tools' files: clean, cache entries and their records and locks, journals, whole writes, links, bounded reads, stopped programs, the work folder.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import json
import numpy as np
import os
import shutil
import struct
import time
from make_example import example
from musiclib import audio, midi
from musiclib.model import save_json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    rejects, rejects_with, work = S['rejects'], S['rejects_with'], S['work']
    def entry_lock_across_renders():
        # Renders sharing a cache: while one process holds a cache entry, another cannot take it, and can once it ends.
        import subprocess,sys
        from musiclib.render import entry_lock,keep_stem
        folder=work/'lock_entry';folder.mkdir()
        code=('import sys,time;sys.path.insert(0,sys.argv[1]);from musiclib.render import entry_lock\n'
              'with entry_lock(sys.argv[2]) as held:\n    print(held,flush=True);time.sleep(4)')
        holder=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(folder)],stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='True'
            with entry_lock(folder,wait=False) as busy:assert busy is False
        finally:
            holder.wait(timeout=60);holder.stdout.close()
        with entry_lock(folder,wait=False) as free:assert free is True
        with entry_lock(folder) as again:assert again is True
        # A link under the lock's name is refused before it is opened, so nothing is made behind it: opening it made
        # an empty file wherever it led, and only then was the entry refused (GPT's security audit of 0.5, S04).
        # Symbolic links to files need a privilege on Windows; the CI's Linux and macOS runs make one.
        linked_lock=work/'lock_linked';linked_lock.mkdir();beyond=work/'lock_beyond.txt';lock_is_link=False
        try:os.symlink(beyond,linked_lock/'entry.lock');lock_is_link=True
        except (OSError,NotImplementedError):pass
        if lock_is_link:
            try:
                with entry_lock(linked_lock):raise AssertionError('an entry whose lock is a link was taken')
            except ValueError as e:assert 'a link' in str(e),e
            assert not os.path.lexists(beyond)
        # Keeping a stem is only a saving: one that cannot be written is skipped, not raised.
        assert keep_stem(work/'no_such_entry',work/'lock_entry'/'entry.lock',{}) is False
        # A keep stopped part way by anything (Ctrl+C in a part's thread) leaves no copy behind, and clean knows the
        # names a render's own files take while written, so an entry holding one is still one it may remove.  (Found
        # by GPT Pro's third review of 0.4.0: the copy stayed, and the entry was left alone for ever.)
        import shutil as sh
        from musiclib.clean import ENTRY_FILES
        (work/'lock_entry'/'stem_source.wav').write_bytes(bytes(8192));real_copy=sh.copyfile
        def stopped(src,dst,*a,**k):
            Path(dst).write_bytes(bytes(4096));raise KeyboardInterrupt
        sh.copyfile=stopped
        try:
            try:
                keep_stem(work/'lock_entry',work/'lock_entry'/'stem_source.wav',{});raise AssertionError('the stop went unnoticed')
            except KeyboardInterrupt:pass
        finally:sh.copyfile=real_copy
        assert not [x.name for x in (work/'lock_entry').iterdir() if x.name.startswith('.stem.wav')],sorted(x.name for x in (work/'lock_entry').iterdir())
        assert ENTRY_FILES.fullmatch('.stem.wav.fwn3nxr2.wav') and ENTRY_FILES.fullmatch('.raw.wav.a1_b2c3d.wav') and not ENTRY_FILES.fullmatch('my_take.wav')
        return {'held_by_another_process_refused':True,'free_after_it_ends':True,'failed_keep_skipped':True,'stopped_keep_left_nothing':True,'linked_lock_refused':lock_is_link}
    def clean_only_what_the_tools_made():
        # clean deletes only folders whose tool-written records say a tool made them, of the kept piece, never through
        # a link, and only when asked to: these are the cases two reviews of 0.4.0 found it deleting what it should not.
        import subprocess,sys
        from musiclib.clean import clean,describe
        base=work/'clean_cases';H=lambda c:c*64
        from musiclib import files as record
        # Folders as the tools leave them: each records what it wrote in its files.json (musiclib.files), and a
        # round names its project relative to itself.
        def made(folder,title,keys=(),recorded=True):
            folder.mkdir(parents=True);save_json(folder/'render_input.json',{'project_sha256':H('a'),'renderer_sha256':H('b')})
            save_json(folder/'project.json',{'title':title,'tracks':[]});save_json(folder/'stem_receipts.json',[{'track':'t','cache_key':k} for k in keys])
            (folder/'master.wav').write_bytes(bytes(1000))
            if recorded:record.register(folder,[folder/n for n in ('render_input.json','project.json','stem_receipts.json','master.wav')])
            return folder
        def round_of(folder,title,project,keys=()):
            folder.mkdir(parents=True)
            save_json(folder/'round.json',{'kind':'music-production round','title':title,'project':os.path.relpath(project,folder).replace(os.sep,'/'),'status':'DRAFT_PASS','review':'review/score_review.json','render':'render/report.json','seconds':{}})
            record.register(folder,[folder/'round.json']);made(folder/'render',title,keys);return folder
        def entry(cache,key):
            (cache/key).mkdir(parents=True);save_json(cache/key/'receipt.json',{'key':key,'sha256':H('c'),'track':'t'});(cache/key/'raw.wav').write_bytes(bytes(2000))
        def link(at,target):
            # A junction on Windows (no privilege needed), a symbolic link elsewhere.
            if os.name=='nt':return subprocess.run(['cmd','/c','mklink','/J',str(at),str(target)],capture_output=True).returncode==0
            os.symlink(target,at,target_is_directory=True);return True
        listed=lambda r:sorted((x['kind'],Path(x['path']).as_posix()) for x in r['listed'])
        proj=base/'piece';final=made(proj/'final','Song')
        # A source folder with a project saved as round.json, or an ordinary render_input.json, is not a tool's folder.
        (proj/'compositions').mkdir();save_json(proj/'compositions'/'round.json',{'title':'Song','clock':{},'tracks':[]});(proj/'compositions'/'compose.py').write_text('x',encoding='utf-8')
        (proj/'notes').mkdir();save_json(proj/'notes'/'render_input.json',{'project_sha256':'x','renderer_sha256':'y'})
        # A link to a folder outside holding a render is not entered; a linked record does not make a render folder.
        outside=made(base/'outside'/'old','Song');linked=link(proj/'link_out',base/'outside')
        symlinked=False
        try:
            (proj/'source').mkdir();(proj/'source'/'render_input.json').symlink_to(final/'render_input.json');save_json(proj/'source'/'project.json',{'title':'Song'});symlinked=True
        except OSError:pass  # symbolic links need a privilege on Windows; the CI's Linux and macOS runs make one
        first=clean(proj,[final])
        assert listed(first)==[] and first['dry_run'],first
        clean(proj,[final],remove=True)
        assert (proj/'compositions'/'compose.py').is_file() and (proj/'notes'/'render_input.json').is_file() and (outside/'master.wav').is_file()
        assert not symlinked or (proj/'source'/'project.json').is_file()
        # A parent folder of two pieces: the kept piece's old round and unused cache entry go, the other piece stays.
        work2=base/'pieces';a,b=work2/'song_a',work2/'song_b'
        for c,k in ((a,H('1')),(a,H('2')),(b,H('3'))):entry(c/'cache',k)
        made(a/'final','Song A',[H('1')]);round_of(a/'r1','Song A',str(a/'song.json'),[H('2')])
        made(b/'final','Song B',[H('3')]);round_of(b/'r3','Song B',str(b/'song.json'),[H('3')])
        dry=clean(work2,[a/'final'])
        want=[('cache entry','song_a/cache/'+H('2')),('render','song_a/r1/render'),('round','song_a/r1')]
        assert listed(dry)==want and (a/'r1').is_dir() and sorted(Path(x['path']).as_posix() for x in dry['left_alone'])==['song_b/final','song_b/r3','song_b/r3/render'],dry
        assert all(x['whole'] for x in dry['listed']) and describe(dry).splitlines()[-1].startswith('Nothing was removed')
        done=clean(work2,[a/'final'],remove=True)
        assert listed(done)==want and not (a/'r1').exists() and (b/'final'/'master.wav').is_file() and (b/'r3').is_dir() and (b/'cache'/H('3')).is_dir()
        # A piece renamed between rounds: its earlier round names the same project file.
        c=work2/'song_c';round_of(c/'r1','Old name',c/'song.json');round_of(c/'r2','New name',c/'song.json')
        kept_round=clean(work2,[c/'r2'])
        assert listed(kept_round)==[('render','song_c/r1/render'),('round','song_c/r1')]
        # a kept round is named by its own folder, which stays whole (it printed the render inside it: the walkthrough
        # of 0.8.0), and so is the round of a render kept from inside it
        assert kept_round['kept']==[str((c/'r2').resolve())] and clean(work2,[c/'r2'/'render'])['kept']==[str((c/'r2').resolve())],kept_round['kept']
        assert 'Kept: '+str((c/'r2').resolve())+';' in describe(kept_round),describe(kept_round)
        # Only what a tool wrote and recorded goes, unchanged: a listed render keeps the files added to it and another
        # piece's render inside it, so it stays, in part, with its records; a file changed since stays; and a folder
        # from before 0.4.0, with no files.json, is left alone.  (The cases the second review of 0.4.0 found.)
        e=work2/'song_e';made(e/'final','Song E');old=made(e/'r_old','Song E')
        (old/'listen').mkdir();(old/'listen'/'for_the_user.mp3').write_bytes(b'mp3');(old/'my_notes.txt').write_text('mine',encoding='utf-8')
        nested=made(old/'alt','Other song');changed=made(e/'r_changed','Song E');(changed/'master.wav').write_bytes(bytes(1001))
        legacy=made(e/'r_legacy','Song E',recorded=False)
        r=clean(e,[e/'final'],remove=True)
        assert (old/'listen'/'for_the_user.mp3').is_file() and (old/'my_notes.txt').is_file() and (nested/'master.wav').is_file(),r
        assert not (old/'master.wav').exists() and (old/'project.json').is_file() and (old/record.RECORD).is_file(),r
        assert (changed/'master.wav').is_file() and not (changed/'stem_receipts.json').exists() and (legacy/'master.wav').is_file(),r
        parts={Path(x['path']).as_posix():x for x in r['listed']}
        assert not parts['r_old']['whole'] and {'r_old/listen/for_the_user.mp3','r_old/my_notes.txt'}<=set(parts['r_old']['kept_inside']),parts
        left={Path(x['path']).as_posix():x['why'] for x in r['left_alone']}
        assert left.get('r_old/alt')=='another piece' and 'no record' in left.get('r_legacy',''),left
        again=clean(e,[e/'final'])  # what the first left is found again; nothing of it can go, so it is named as left and not as removed
        still={Path(x['path']).as_posix():x['why'] for x in again['left_alone']}
        assert not again['listed'] and 'r_old/my_notes.txt' in still.get('r_old','') and 'r_changed/master.wav' in still.get('r_changed',''),again
        # A round left in part (a file of the user's in its render) loses its review/ whole, the record with it; a file
        # named as a record but not one (files.json in a folder of the user's, a project.json no record lists at a
        # round's top) stays, so the round goes in part even when all else goes.  (Found by a clean-room run.)
        kept_round=round_of(e/'r_kept','Song E',e/'song.json');(kept_round/'review').mkdir()
        save_json(kept_round/'review'/'score_review.json',{});record.register(kept_round/'review',[kept_round/'review'/'score_review.json'])
        (kept_round/'render'/'mine.txt').write_text('mine',encoding='utf-8')
        named=round_of(e/'r_named','Song E',e/'song.json');(named/'mine').mkdir();(named/'mine'/record.RECORD).write_text('{}',encoding='utf-8')
        save_json(named/'project.json',{'title':'Song E'})
        r=clean(e,[e/'final'],remove=True);parts={Path(x['path']).as_posix():x for x in r['listed']}
        assert not (kept_round/'review').exists() and (kept_round/'round.json').is_file() and (kept_round/'render'/'mine.txt').is_file(),r
        assert (named/'mine'/record.RECORD).is_file() and (named/'project.json').is_file() and not (named/'render').exists(),r
        why=next(x['why'] for x in r['left_alone'] if x['path']=='r_named');assert 'r_named/mine/files.json' in why and 'r_named/project.json' in why,why   # its render went; of itself nothing more can
        # A folder or a --keep given as a link is refused.
        assert not linked or (link(base/'root_link',proj) and rejects(lambda:clean(base/'root_link',[base/'root_link'/'final'])))
        assert not linked or (link(proj/'final_link',final) and rejects(lambda:clean(proj,[proj/'final_link'])))
        # A cache entry a render holds stays.
        d=work2/'song_d';entry(d/'cache',H('4'));entry(d/'cache',H('5'));made(d/'final','Song D',[H('5')])
        code=('import sys,time;sys.path.insert(0,sys.argv[1]);from musiclib.render import entry_lock\n'
              'with entry_lock(sys.argv[2]) as held:\n    print(held,flush=True);time.sleep(5)')
        holder=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(d/'cache'/H('4'))],stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='True'
            looked=clean(d,[d/'final'])  # the dry run looks at the entry's lock too, creating nothing
            held=clean(d,[d/'final'],remove=True)
        finally:
            holder.wait(timeout=60);holder.stdout.close()
        assert [x['error'] for x in held['not_removed']]==['a render is using it'] and (d/'cache'/H('4')).is_dir(),held
        # The dry run says so too: it listed the entry as one that goes (found by GPT Pro's third review of 0.4.0).
        assert [x['error'] for x in looked['not_removed']]==['a render is using it'] and not any(H('4') in x['path'] for x in looked['listed']),looked
        # A render's unlocked_cache/ is its own, not a cache to clean: where the shared cache could not be locked the
        # render made its parts there, under its work lock, and its record covers them.  A kept render using one of its
        # keys made it a cache: its other parts were listed and removed by their names under an entry lock no render
        # holds there, while the render worked, or from a render of another piece, and a part changed since went too
        # (GPT's second re-review of 0.5, R01).  It goes with the render's folder, by the render's record.
        def private(folder,title,keys):
            made(folder,title,keys,recorded=False);own=[folder/n for n in ('render_input.json','project.json','stem_receipts.json','master.wav')]
            for k in keys:entry(folder/'unlocked_cache',k);own+=[folder/'unlocked_cache'/k/'receipt.json',folder/'unlocked_cache'/k/'raw.wav']
            record.register(folder,own);return folder
        v_=work2/'song_v';made(v_/'final','Song V',[H('1'),H('2')])
        for k in '126':entry(v_/'cache',H(k))
        working=private(v_/'working','Song V',[H('1'),H('3')]);other=private(v_/'other','Another song',[H('1'),H('4')])
        changed=private(v_/'changed','Song V',[H('1'),H('5')]);(changed/'unlocked_cache'/H('5')/'raw.wav').write_bytes(bytes(2001))
        older=private(v_/'older','Song V',[H('1'),H('3')])
        for k in '17':entry(v_/'loose'/'unlocked_cache',H(k))  # in a folder clean cannot read as a render: it stays too
        code=('import sys;sys.path.insert(0,sys.argv[1]);from musiclib import files\n'
              'with files.working(sys.argv[2]) as held:\n    print(held,flush=True);sys.stdin.readline()')
        holder=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(working)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='True'
            looked=clean(v_,[v_/'final']);r=clean(v_,[v_/'final'],remove=True)
        finally:
            holder.stdin.write('\n');holder.stdin.close();holder.wait(timeout=60);holder.stdout.close()
        for x in (looked,r):
            assert [Path(e['path']).as_posix() for e in x['listed'] if e['kind']=='cache entry']==['cache/'+H('6')],x['listed']
            assert {Path(e['path']).as_posix() for e in x['left_alone']}=={'working','other'},x['left_alone']
        parts=lambda f,keys:all(sorted(p.name for p in (f/'unlocked_cache'/k).iterdir())==['raw.wav','receipt.json'] for k in keys)
        assert parts(working,[H('1'),H('3')]) and parts(other,[H('1'),H('4')]) and (changed/'unlocked_cache'/H('5')/'raw.wav').stat().st_size==2001
        assert not older.exists() and not (v_/'cache'/H('6')).exists() and (v_/'cache'/H('1')/'raw.wav').is_file() and (v_/'cache'/H('2')/'raw.wav').is_file()
        assert parts(v_/'loose',[H('1'),H('7')])
        # An entry's lock file goes only where no render can hold another by its name: a render that makes and holds
        # a new lock there the moment clean lets the entry go keeps it (on POSIX clean removed the name under the lock,
        # then again after letting go, which took the render's new lock away).  (Found by a review of 0.4.0.)
        import contextlib
        import musiclib.render as rd
        f2=work2/'song_f';entry(f2/'cache',H('6'));entry(f2/'cache',H('7'));made(f2/'final','Song F',[H('7')]);real_lock=rd.entry_lock;newer=[]
        @contextlib.contextmanager
        def then_a_render(folder,wait=True,create=True):
            with real_lock(folder,wait,create) as free:
                yield free
            newer.append(os.open(Path(folder)/'entry.lock',os.O_RDWR|os.O_CREAT,0o644))  # a render, there at once
        rd.entry_lock=then_a_render
        try:
            clean(f2,[f2/'final'],remove=True)
            assert newer and (f2/'cache'/H('6')/'entry.lock').is_file(),sorted(p.name for p in (f2/'cache'/H('6')).iterdir()) if (f2/'cache'/H('6')).is_dir() else 'entry gone'
        finally:
            rd.entry_lock=real_lock
            for fd in newer:os.close(fd)
        # A link inside a listed folder (a junction on Windows, which os.walk enters) is never walked into: the empty
        # folders where it leads stay, and the folder holding it stays in part with its records, the link named.
        # (Found by a review of 0.4.0: the empty folders behind a junction were removed.)
        g=work2/'song_g';made(g/'final','Song G');old_g=made(g/'r_link','Song G');(base/'beyond'/'empty'/'deeper').mkdir(parents=True)
        junction=link(old_g/'listen',base/'beyond')
        if junction:
            r=clean(g,[g/'final'],remove=True);parts={Path(x['path']).as_posix():x for x in r['listed']}
            assert (base/'beyond'/'empty'/'deeper').is_dir() and (old_g/'render_input.json').is_file() and (old_g/record.RECORD).is_file(),r
            assert not parts['r_link']['whole'] and 'r_link/listen' in parts['r_link']['kept_inside'],parts
            from musiclib import files as owned
            owned.prune(old_g);assert (base/'beyond'/'empty'/'deeper').is_dir()
        # A cache entry's file another program holds open (Windows refuses to remove it) leaves that entry, named, and
        # the clean goes on to the rest.  (Found by a review of 0.4.0: one open file stopped the whole clean.)
        h2=work2/'song_h';entry(h2/'cache',H('8'));entry(h2/'cache',H('9'));made(h2/'final','Song H',[H('9')]);old_h=made(h2/'r_old','Song H')
        real_unlink=Path.unlink
        def held_open(self,*a,**k):
            if self.name=='raw.wav' and self.parent.name==H('8'):raise PermissionError(13,'held open by another program',str(self))
            return real_unlink(self,*a,**k)
        Path.unlink=held_open
        try:r=clean(h2,[h2/'final'],remove=True)
        finally:Path.unlink=real_unlink
        assert [x['path'] for x in r['not_removed']]==[f'cache/{H("8")}'] and (h2/'cache'/H('8')/'receipt.json').is_file() and not old_h.exists(),r
        # A record another program holds open stays, and is not counted among what went.
        h3=work2/'song_h3';made(h3/'final','Song H3');r3=round_of(h3/'r3','Song H3',h3/'song.json');(r3/'review').mkdir();save_json(r3/'review'/'score_review.json',{})
        record.register(r3/'review',[r3/'review'/'score_review.json']);(r3/'note.txt').write_text('mine',encoding='utf-8')
        sizes=lambda:sum(x.stat().st_size for x in r3.rglob('*') if x.is_file());before=sizes()
        def record_open(self,*a,**k):
            if self==r3/'review'/record.RECORD:raise PermissionError(13,'held open by another program',str(self))
            return real_unlink(self,*a,**k)
        Path.unlink=record_open
        try:r=clean(h3,[h3/'final'],remove=True)
        finally:Path.unlink=real_unlink
        assert (r3/'review'/record.RECORD).is_file() and r['bytes']==before-sizes(),(r['bytes'],before-sizes())
        # From GPT Pro's third review of 0.4.0: a tool's folder deeper than clean looked (four levels), inside a listed
        # one, keeps its own piece and record: another piece's stays whole and is named; a file of the user's in an
        # audition's own cache is named among what stays; a record changed while clean runs keeps the folder with its
        # records; and a tool's folder holding a listed one stays held while clean removes inside it.
        k=work2/'song_k';made(k/'final','Song K');old_k=made(k/'r_old','Song K');deep=made(old_k/'a'/'b'/'c'/'d'/'e','Another song')
        r=clean(k,[k/'final'],remove=True);left={Path(x['path']).as_posix():x['why'] for x in r['left_alone']}
        assert (deep/'master.wav').is_file() and left.get('r_old/a/b/c/d/e')=='another piece' and old_k.is_dir(),(left,r['listed'])
        aud=k/'aud';(aud/'00_v'/'render').parent.mkdir(parents=True);save_json(aud/'00_v'/'song.json',{'title':'Song K','tracks':[]})
        made(aud/'00_v'/'render','Song K');entry(aud/'cache',H('d'));(aud/'cache'/'my_notes.txt').write_text('mine',encoding='utf-8')
        save_json(aud/'audition.json',{'kind':'music-production audition','title':'Song K','track':'lead','bars':[1,1],'versions':[],'each_seconds':2,'status':'FAIL'})
        record.register_tree(aud,skip={aud/'00_v'/'render',aud/'cache'})
        r=clean(k,[k/'final'],remove=True);parts={Path(x['path']).as_posix():x for x in r['listed']}
        assert (aud/'cache'/'my_notes.txt').is_file() and 'aud/cache/my_notes.txt' in parts['aud']['kept_inside'],parts.get('aud')
        import musiclib.clean as cl
        changed=made(k/'r_changed_meanwhile','Song K');real_empty=cl._empty_folders;fired=[]
        def meanwhile(folder,skip,holders=(),stamps=None,only=None):
            if folder==changed and not fired:  # once, after the folder's files went and before its records do
                fired.append(1);(changed/'late.json').write_text('{}',encoding='utf-8');record.register(changed,[changed/'late.json'])
            return real_empty(folder,skip,holders,stamps,only)
        cl._empty_folders=meanwhile
        try:r=clean(k,[k/'final'],remove=True)
        finally:cl._empty_folders=real_empty
        assert record.is_record(changed/record.RECORD) and (changed/'late.json').is_file() and any(x['path']=='r_changed_meanwhile' for x in r['not_removed']),r['not_removed']
        host=k/'other_aud';(host/'00_v').mkdir(parents=True);save_json(host/'audition.json',{'kind':'music-production audition','title':'Other song','track':'x','bars':[1,1],'versions':[],'each_seconds':2})
        record.register(host,[host/'audition.json']);inner=made(host/'inner','Song K');real_remove=cl._remove;seen=[]
        def watched(*a,**kw):
            seen.append(record.take(host,create=False)[0])  # another open of the lock, as a run starting there would make
            return real_remove(*a,**kw)
        cl._remove=watched
        try:clean(k,[k/'final'],remove=True)
        finally:cl._remove=real_remove
        assert seen==['busy'] and not inner.exists() and not record.occupied(host/record.WORK_LOCK),seen
        # From GPT Pro's fourth review of 0.4.0: a round's review/ record written again after the plan keeps the round
        # with its records (it went unseen); a file of the user's that appears after the plan keeps the folder with the
        # records that name it (they went first, and the folder's removal then failed on it); a dry run lets go of the
        # entry locks it takes; tool folders inside each other are worked out once each (it took twice as long for
        # every level); a kept render's stem receipts are read within the record limit.
        def after_plan(change):
            real_plan=cl._plan
            def planned(folder,kind,rec,inner,entries=()):
                plan=real_plan(folder,kind,rec,inner,entries);change(Path(folder));return plan
            cl._plan=planned;return real_plan
        m=work2/'song_m';made(m/'final','Song M')
        rnd=m/'r_round';rnd.mkdir();save_json(rnd/'round.json',{'kind':'music-production round','title':'Song M','project':'../song.json','status':'DRAFT_PASS',
                                                                 'review':'review/score_review.json','render':'render/report.json','seconds':{}})
        record.register(rnd,[rnd/'round.json']);(rnd/'review').mkdir();save_json(rnd/'review'/'score_review.json',{})
        record.register(rnd/'review',[rnd/'review'/'score_review.json']);made(rnd/'render','Song M')
        real_plan=after_plan(lambda f:(time.sleep(.02),record.register(rnd/'review',[])) if f==rnd else None)
        try:r=clean(m,[m/'final'],remove=True)
        finally:cl._plan=real_plan
        assert record.is_record(rnd/'review'/record.RECORD) and any(x['path']=='r_round' for x in r['not_removed']),r['not_removed']
        late=made(m/'r_late','Song M')
        real_plan=after_plan(lambda f:(late/'my_notes.txt').write_text('mine',encoding='utf-8') if f==late else None)
        try:r=clean(m,[m/'final'],remove=True)
        finally:cl._plan=real_plan
        assert (late/'my_notes.txt').is_file() and all((late/n).is_file() for n in ('files.json','render_input.json','project.json')),sorted(x.name for x in late.iterdir())
        assert any(x['path']=='r_late' and 'appeared' in x['error'] for x in r['not_removed']),r['not_removed']
        n_=work2/'song_n';made(n_/'final','Song N',keys=[H('e')]);entry(n_/'cache',H('e'));entry(n_/'cache',H('f'));(n_/'cache'/H('f')/'entry.lock').write_bytes(b'')
        for _ in range(2):  # the second sees the entry as free as the first did
            r=clean(n_,[n_/'final'],remove=False)
            assert [x['path'] for x in r['listed'] if x['kind']=='cache entry']==[f'cache/{H("f")}'] and not r['not_removed'],(r['listed'],r['not_removed'])
        q_=work2/'song_q';made(q_/'final','Song Q');f=q_/'a';made(f,'Song Q')
        for k in range(1,26):f=f/chr(97+k);made(f,'Song Q')
        began=time.monotonic();r=clean(q_,[q_/'final'],remove=False);nested_s=time.monotonic()-began
        assert len(r['listed'])==26 and nested_s<30,(len(r['listed']),nested_s)
        big=made(work2/'song_r'/'final','Song R');save_json(big/'stem_receipts.json',[{'track':'t','cache_key':H('a'),'pad':'x'*5000}],new=False)
        real_max=record.MAX_RECORD;record.MAX_RECORD=2000
        try:assert rejects(lambda:clean(work2/'song_r',[big],remove=False))
        finally:record.MAX_RECORD=real_max
        # A render stopped before its first record is proved by its journal alone: what names it goes last, so a file
        # that cannot be removed leaves it with its marker, recognised by the next clean (GPT's review of 0.5, C03: the
        # marker went with the other files, and the folder was then neither cleaned nor resumed).
        s_=work2/'song_s';made(s_/'final','Song S');stopped=s_/'stopped';stopped.mkdir(parents=True)
        with record.journaled(stopped):
            save_json(stopped/'render_input.json',{'project_sha256':H('a'),'renderer_sha256':H('b'),'title':'Song S'})
            save_json(stopped/'project.json',{'title':'Song S','tracks':[]});save_json(stopped/'stem_receipts.json',[])
        assert not record.is_record(stopped/record.RECORD)
        real_unlink=Path.unlink
        def held(self,*a,**k):
            if self.name=='stem_receipts.json':raise PermissionError(13,'held open by another program',str(self))
            return real_unlink(self,*a,**k)
        Path.unlink=held
        try:r=clean(s_,[s_/'final'],remove=True)
        finally:Path.unlink=real_unlink
        assert all((stopped/n).is_file() for n in ('render_input.json','project.json')) and any(x['path']=='stopped' for x in r['not_removed']),(sorted(x.name for x in stopped.iterdir()),r['not_removed'])
        r=clean(s_,[s_/'final'],remove=True);assert not stopped.exists() and (s_/'final'/'master.wav').is_file(),r
        # The marker itself may be the file that cannot be removed, the record and the journal gone before it: a new
        # record of it alone is written, so the next clean knows it for the tools' and takes the folder.  Nothing had
        # proved it, and every later clean left the folder, naming the marker as a file of the user's (GPT's re-review
        # of 0.5, RR02).  A files.json someone puts there meanwhile is never written over: the folder then stays.
        def marker_held(folder,meanwhile=None):
            def held(self,*a,**k):
                if self==folder/'render_input.json':
                    if meanwhile:meanwhile()
                    raise PermissionError(13,'held open by another program',str(self))
                return real_unlink(self,*a,**k)
            Path.unlink=held
            try:return clean(folder.parent,[folder.parent/'final'],remove=True)
            finally:Path.unlink=real_unlink
        for proof in ('journal','record'):
            t_=work2/f'song_t_{proof}';made(t_/'final','Song T');stopped=t_/'stopped'
            if proof=='record':  # as a render of 0.5 leaves it: the marker names the piece
                made(stopped,'Song T');save_json(stopped/'render_input.json',{'project_sha256':H('a'),'renderer_sha256':H('b'),'title':'Song T'})
                record.register(stopped,[stopped/'render_input.json'])
            else:
                stopped.mkdir(parents=True)
                with record.journaled(stopped):
                    save_json(stopped/'render_input.json',{'project_sha256':H('a'),'renderer_sha256':H('b'),'title':'Song T'})
                    save_json(stopped/'project.json',{'title':'Song T','tracks':[]})
            was=record.stamp(stopped/'render_input.json');r=marker_held(stopped)
            assert any(x['path']=='stopped' for x in r['not_removed']) and sorted(x.name for x in stopped.iterdir())==['files.json','render_input.json'],(proof,sorted(x.name for x in stopped.iterdir()),r['not_removed'])
            assert record.recorded(stopped)=={'render_input.json':was},(proof,record.recorded(stopped))
            r=clean(t_,[t_/'final'],remove=True);assert not stopped.exists() and (t_/'final'/'master.wav').is_file(),(proof,r)
        u_=work2/'song_u';made(u_/'final','Song U');theirs=made(u_/'stopped','Song U')
        r=marker_held(theirs,lambda:(theirs/'files.json').write_text('mine',encoding='utf-8'))
        assert (theirs/'files.json').read_text(encoding='utf-8')=='mine' and (theirs/'render_input.json').is_file() and any(x['path']=='stopped' for x in r['not_removed']),r['not_removed']
        r=clean(u_,[u_/'final'],remove=True);assert (theirs/'files.json').read_text(encoding='utf-8')=='mine' and (theirs/'render_input.json').is_file(),r
        # A cache entry whose entry.lock is a link stays whole, the link and what it names with it (GPT's security
        # audit of 0.5, S04).
        w_=work2/'song_w_lock';entry(w_/'cache',H('2'));entry(w_/'cache',H('3'));made(w_/'final','Song W',[H('2')]);named=work2/'lock_named.txt';named.write_bytes(b'kept');entry_lock_linked=False
        try:os.symlink(named,w_/'cache'/H('3')/'entry.lock');entry_lock_linked=True
        except (OSError,NotImplementedError):pass
        if entry_lock_linked:
            for remove in (False,True):
                r=clean(w_,[w_/'final'],remove=remove)
                assert os.path.islink(w_/'cache'/H('3')/'entry.lock') and named.read_bytes()==b'kept' and (w_/'cache'/H('3')/'raw.wav').is_file(),r
                assert not [x for x in r['listed'] if x['kind']=='cache entry'],r['listed']
        return {'records_by_name_alone_kept':True,'journal_proved_marker_last':True,'held_marker_recorded_anew':True,'link_not_followed':linked,'linked_record_kept':symlinked,'other_piece_left_alone':True,'renamed_piece_cleaned':True,'unrecorded_files_kept':True,'held_entry_kept':True,'emptied_review_removed':True,'files_named_as_records_kept':True,
                'deep_folder_kept_its_piece':True,'audition_cache_file_named':True,'record_changed_meanwhile_kept':True,'holding_folder_held':True,
                'junction_not_walked':junction,'open_entry_named':True,'nested_record_changed_kept':True,'late_file_kept_with_records':True,
                'dry_run_lets_entry_locks_go':True,'nested_26_units_s':round(nested_s,2),'kept_receipts_bounded':True,'unlocked_cache_is_the_renders':True,
                'entry_with_a_linked_lock_kept':entry_lock_linked}
    def cache_entries_by_their_record():
        # A cache entry renders of 0.5 write keeps its own record (files.json) and, while one works in it, a journal:
        # clean removes such an entry by the files they prove, whole when nothing else is there; a file of the user's
        # in it, or a copy put in a file's place, keeps it, named; one a render was writing when it stopped (a new file
        # the journal names, no receipt yet) goes too.  (Left for 0.5 by GPT Pro's third review of 0.4.0, which found
        # clean going by the entry's key, receipt, the renderers' file names and lock.)
        from musiclib.clean import clean
        from musiclib import files as fs
        base=work/'entry_records';piece=base/'piece';H=lambda c:c*64;cache=piece/'cache'
        kept=piece/'final';kept.mkdir(parents=True)
        save_json(kept/'render_input.json',{'project_sha256':H('a'),'renderer_sha256':H('b')});save_json(kept/'project.json',{'title':'Song','tracks':[]})
        save_json(kept/'stem_receipts.json',[{'track':'t','cache_key':H('1')}]);fs.register_tree(kept)
        def entry(key,partial=False):
            e=cache/key;e.mkdir(parents=True)
            with fs.journaled(e):
                if partial:
                    fd,_=fs.new_file(e/'raw.wav','.wav');os.write(fd,bytes(500));os.close(fd);return e
                x=fs.stage_name(e/'raw.wav','.wav');x.write_bytes(bytes(2000));fs.replace(x,e/'raw.wav')
                save_json(e/'receipt.json',{'key':key,'sha256':H('c'),'track':'t'})
                fs.register_tree(e);fs.drop_journal(e)
            return e
        used,whole,mine,partial,copied=entry(H('1')),entry(H('2')),entry(H('3')),entry(H('4'),True),entry(H('5'))
        (mine/'notes.txt').write_text('mine',encoding='utf-8')
        shutil.copy2(copied/'raw.wav',copied/'raw.copy');os.replace(copied/'raw.copy',copied/'raw.wav')
        assert (whole/'files.json').is_file() and not (whole/fs.JOURNAL).exists() and (partial/fs.JOURNAL).is_file()
        dry=clean(piece,[kept]);done=clean(piece,[kept],remove=True)
        went=sorted(Path(x['path']).name[:1] for x in done['listed'] if x['kind']=='cache entry')
        stayed=sorted(Path(x['path']).name[:1] for x in done['left_alone'] if x['kind']=='cache entry')
        assert went==['2','4'] and stayed==['3','5'],(done['listed'],done['left_alone'])
        assert not whole.exists() and not partial.exists() and (mine/'notes.txt').is_file() and (copied/'raw.wav').is_file() and used.is_dir()
        assert sorted(x['path'] for x in dry['listed'])==sorted(x['path'] for x in done['listed'])
        return {'whole_entry_removed':True,'stopped_entry_removed':True,'user_file_and_copy_kept':True}
    def files_never_overwrite_or_write_through():
        # Outputs never take an occupied path, a dangling link included; a write swaps a new file in, so a hard link at
        # the path keeps its bytes; an install sets aside what it did not record, never removing it (musiclib.files).
        from musiclib import files as fs
        d=work/'files_cases';d.mkdir()
        (d/'taken.txt').write_text('x',encoding='utf-8');(d/'folder').mkdir()
        for p in (d/'taken.txt',d/'folder'):rejects(lambda p=p:fs.fresh(p))
        fs.fresh(d/'new.txt')
        dangling=False
        try:os.symlink(d/'missing_target',d/'dangling');dangling=True
        except OSError:pass  # symbolic links need a privilege on Windows; the CI's Linux and macOS runs make one
        if dangling:
            rejects(lambda:fs.fresh(d/'dangling'))
            assert fs.occupied(d/'dangling') and not (d/'missing_target').exists()
            assert [x.name for x in fs.foreign(d)]==['dangling']  # a link is something a write could leave through
            os.unlink(d/'dangling')
        outside=d/'outside.json';outside.write_text('{"keep": 1}',encoding='utf-8');os.link(outside,d/'linked.json')
        assert {x.name for x in fs.foreign(d)}=={'outside.json','linked.json'}
        fs.write_json(d/'linked.json',{'new':2})
        assert json.loads(outside.read_text(encoding='utf-8'))=={'keep':1} and json.loads((d/'linked.json').read_text(encoding='utf-8'))=={'new':2}
        assert not fs.foreign(d) and not [x for x in d.iterdir() if x.name.startswith('.')]
        target=d/'install';target.mkdir();(target/'mine.txt').write_text('user',encoding='utf-8')
        stage=fs.staging_folder(target);(stage/'mine.txt').write_text('new',encoding='utf-8');(stage/'bank.sf2').write_bytes(b'v1')
        moved=fs.install_tree(stage,target)
        assert len(moved)==1 and moved[0].read_text(encoding='utf-8')=='user' and (target/'mine.txt').read_text(encoding='utf-8')=='new',moved
        stage=fs.staging_folder(target);(stage/'bank.sf2').write_bytes(b'v2')
        assert fs.install_tree(stage,target)==[] and (target/'bank.sf2').read_bytes()==b'v2' and not stage.exists()
        # A files.json of someone else's where an install records its files (another program's list, the user's own)
        # is set aside and named, not written over by the record.  (Found by a review of 0.4.0.)
        other=d/'theirs';other.mkdir();(other/'files.json').write_text('{"personal_note": "mine"}',encoding='utf-8')
        stage=fs.staging_folder(other);(stage/'tool.txt').write_text('t',encoding='utf-8')
        moved=fs.install_tree(stage,other)
        assert len(moved)==1 and json.loads(moved[0].read_text(encoding='utf-8'))=={'personal_note':'mine'} and fs.is_record(other/'files.json'),moved
        # A program that stops or fails after it began its output leaves nothing under the output's name: FFmpeg and
        # FluidSynth write a new file of their own, which takes the name only when they succeed.  (Found by a review.)
        from musiclib import audio
        real_run=audio.run
        def failing(argv,folder,label,timeout=600):
            out=Path(argv[-1]) if label=='ffmpeg_case' else Path(argv[argv.index('-F')+1])
            out.write_bytes(b'RIFF'+bytes(4092));raise RuntimeError(f'{label} failed (1): write failed')
        audio.run=failing;stopped=0
        try:
            src=d/'in.wav';audio.write_wav(src,np.zeros((480,2),dtype=np.float32))
            for call in (lambda:audio.ffmpeg({'ffmpeg':{'path':'ffmpeg'}},['-i',src,'-c:a','pcm_s16le',d/'out.wav'],d,'ffmpeg_case'),
                         lambda:audio.fluidsynth({'fluidsynth':{'path':'fluidsynth'}},d/'bank.sf2',d/'in.mid',d/'synth.wav',d,'fluidsynth_case')):
                try:call()
                except RuntimeError:stopped+=1
        finally:
            audio.run=real_run
        assert stopped==2,stopped
        assert not fs.occupied(d/'out.wav') and not fs.occupied(d/'synth.wav') and not [x for x in d.iterdir() if x.name.startswith('.out') or x.name.startswith('.synth')],sorted(x.name for x in d.iterdir())
        # An output is recorded only in a folder whose files.json is the tools' record: another program's files.json a
        # few folders up is neither set aside nor written over.  (Found by a review of 0.4.0.)
        mine=d/'project_of_theirs';(mine/'reports'/'music').mkdir(parents=True);(mine/'files.json').write_text('{"their": "list"}',encoding='utf-8')
        (mine/'reports'/'music'/'compare.json').write_text('{}',encoding='utf-8')
        assert fs.register_output(mine/'reports'/'music'/'compare.json') is None and json.loads((mine/'files.json').read_text(encoding='utf-8'))=={'their':'list'}
        assert sorted(x.name for x in mine.iterdir())==['files.json','reports']
        # A resumed run records a file it did not write only while it is unchanged since the earlier record: one the
        # user edited between the runs is not adopted (clean would take it for the tools').  (Found by a review.)
        resumed=d/'resumed';resumed.mkdir();(resumed/'analysis.json').write_text('{"a": 1}',encoding='utf-8');fs.register(resumed,[resumed/'analysis.json'])
        before=fs.recorded(resumed);(resumed/'analysis.json').write_text('{"a": 1, "mine": true}',encoding='utf-8')
        fs.register_tree(resumed,keep=before)
        assert not fs.unchanged(resumed/'analysis.json',fs.recorded(resumed)['analysis.json'])
        # Nor is a file put into a run's folder while the run works there, a note saved into a render folder during the
        # render: a run records only what it wrote itself, and clean keeps the rest.  (It was recorded with the run's
        # files and clean removed it; found by a probe of 0.4.0.)
        busy=d/'busy_run';busy.mkdir();save_json(busy/'report.json',{'a':1});(busy/'my_notes.txt').write_text('mine',encoding='utf-8')
        fs.register_tree(busy);assert list(fs.recorded(busy))==['report.json'],fs.recorded(busy)
        # Nor a file put under a name the run wrote: what the run noted is the file as it was then (its device, inode,
        # size and time), not the name (found by GPT Pro's fifth review of 0.4.0).
        swapped=d/'swapped_run';swapped.mkdir();save_json(swapped/'report.json',{'tools':True});(swapped/'report.json').unlink()
        (swapped/'report.json').write_text('{"the user": "wrote this"}',encoding='utf-8');fs.register_tree(swapped)
        assert 'report.json' not in fs.recorded(swapped),fs.recorded(swapped)
        # Nor, by its saved record, a copy put back under the name that keeps the size and time (shutil.copy2): the record
        # keeps the file's number too, and an entry of two numbers proves nothing (found by GPT Pro's sixth review).
        kept=d/'kept_copy';kept.mkdir();save_json(kept/'report.json',{'tools':True});fs.register_tree(kept)
        (kept/'report.json').rename(kept/'report.orig');shutil.copy2(kept/'report.orig',kept/'report.json');(kept/'report.orig').unlink()
        entry=fs.recorded(kept)['report.json'];assert len(entry)==3 and not fs.unchanged(kept/'report.json',entry)
        assert not fs.unchanged(kept/'report.json',entry[:2]) and not fs.remove_own(kept) and (kept/'report.json').is_file()
        # From the same review's reading of the code: a program's log that the run could not open, and a check's decoded
        # file the program never wrote, are not noted as the run's; remove_own takes away only the records it found.
        import stat as stat_mod,sys
        from musiclib import mixbus
        logs=d/'ro_logs';logs.mkdir();(logs/'ro.log').write_text('theirs',encoding='utf-8');os.chmod(logs/'ro.log',stat_mod.S_IREAD)
        try:
            try:audio.run([sys.executable,'-c','pass'],logs,'ro')
            except OSError:pass
            if (logs/'ro.log').read_text(encoding='utf-8')=='theirs':assert not fs.written_here(logs/'ro.log')  # (an administrator writes it)
        finally:os.chmod(logs/'ro.log',stat_mod.S_IWRITE|stat_mod.S_IREAD)
        dec=d/'dec';(dec/'logs').mkdir(parents=True);(dec/'logs'/'preview_decoded.wav').write_bytes(b'theirs');real_run=audio.run
        def no_program(*a,**k):raise RuntimeError('decode_mp3 failed (1)')
        audio.run=no_program
        try:assert rejects_with(RuntimeError,lambda:mixbus.mp3_check({'ffmpeg':{'path':'ffmpeg'}},dec,-14))
        finally:audio.run=real_run
        assert not fs.written_here(dec/'logs'/'preview_decoded.wav')
        late=d/'late_record';late.mkdir();save_json(late/'a.json',{'a':1});fs.register_tree(late);real_links=fs.links_in
        def rewrite(folder):
            fs.register(late,[]);return real_links(folder)  # another run writes the record again meanwhile
        fs.links_in=rewrite
        try:assert not fs.remove_own(late) and fs.is_record(late/fs.RECORD)
        finally:fs.links_in=real_links
        # A run taking its own failed output away (an audition rendering again with a longer tail) removes what its
        # record lists, and a file put there keeps the folder and the record (the whole folder went; same review).
        own=d/'own_run';(own/'stems').mkdir(parents=True);save_json(own/'report.json',{'a':1});save_json(own/'stems'/'a.json',{'b':2})
        fs.register_tree(own);(own/'stems'/'my_notes.txt').write_text('mine',encoding='utf-8')
        assert not fs.remove_own(own) and (own/'stems'/'my_notes.txt').is_file() and fs.is_record(own/fs.RECORD) and not (own/'report.json').exists()
        (own/'stems'/'my_notes.txt').unlink();(own/'stems'/fs.RECORD).write_text('{"mine": true}',encoding='utf-8')  # no record
        assert not fs.remove_own(own) and (own/'stems'/fs.RECORD).is_file() and fs.is_record(own/fs.RECORD)
        (own/'stems'/fs.RECORD).unlink()
        with fs.working(own):assert not fs.remove_own(own) and fs.is_record(own/fs.RECORD)  # another run holds it
        assert fs.remove_own(own) and not fs.occupied(own)
        # A record made with a relative folder, as a round or a review given a relative --output makes it, lists the
        # files: each was taken from the folder a second time and nothing was recorded.  (Found by the stress test.)
        here=os.getcwd();os.chdir(d)
        try:
            Path('rel_round').mkdir();Path('rel_round/round.json').write_text('{}',encoding='utf-8');(Path('rel_round')/'review').mkdir()
            Path('rel_round/review/notes.csv').write_text('x',encoding='utf-8');fs.wrote(Path('rel_round/review/notes.csv'))  # as review writes it
            fs.register(Path('rel_round'),[Path('rel_round')/'round.json']);fs.register_tree(Path('rel_round')/'review')
        finally:os.chdir(here)
        assert list(fs.recorded(d/'rel_round'))==['round.json'] and list(fs.recorded(d/'rel_round'/'review'))==['notes.csv']
        # A file written whole keeps the mode a new file has under the user's umask (mkstemp makes them 0600).
        import stat
        made_whole=fs.stage_name(d/'mode.wav','.wav')
        assert fs.FILE_MODE is None or stat.S_IMODE(os.stat(made_whole).st_mode)==fs.FILE_MODE,oct(os.stat(made_whole).st_mode)
        return {'dangling_link_refused':dangling,'hard_link_kept':True,'unrecorded_set_aside':True,'foreign_record_set_aside':True,'failed_output_left_nothing':True,
                'foreign_record_above_an_output_untouched':True,'changed_file_not_adopted_on_resume':True,'staged_mode':oct(fs.FILE_MODE) if fs.FILE_MODE is not None else 'not POSIX'}
    def journal_proves_a_stopped_run():
        # A run stopped at any moment leaves only files its record or its journal proves its own: a run writing into a
        # journaled folder is killed after each of its journal lines in turn (the line written, what it announces not
        # yet done), and after each of its renames (the file in place, not yet noted).  Every time, every file left is
        # the run's, adopt removes those half written, and remove_own takes the folder whole.  A file put there after
        # the stop, or in a file's place, is never the run's.  (Left for 0.5 by GPT Pro's third review of 0.4.0: a
        # killed run's last stage was named by clean and refused by --resume.)
        import subprocess,sys
        from musiclib import files as fs
        base=work/'journal_cases';base.mkdir()
        child=('import os,sys;sys.path.insert(0,sys.argv[1]);from pathlib import Path;from musiclib import files\n'
               'mode,k=sys.argv[3],int(sys.argv[4]);n={"line":0,"swap":0};append,swap=files._Journal.append,files._swap\n'
               'def a(self,e):\n    append(self,e);n["line"]+=1\n    if mode=="line" and n["line"]==k:os._exit(9)\n'
               'def s(x,y):\n    swap(x,y);n["swap"]+=1\n    if mode=="swap" and n["swap"]==k:os._exit(9)\n'
               'files._Journal.append,files._swap=a,s;d=Path(sys.argv[2])\n'
               'with files.working(d),files.journaled(d):\n'
               '    (d/"logs").mkdir()\n'
               '    with files.staged(d/"a.json","w",encoding="utf-8") as f:f.write("{}")\n'
               '    x=files.stage_name(d/"logs"/"b.wav",".wav");x.write_bytes(bytes(100));files.replace(x,d/"logs"/"b.wav")\n'
               '    files.register_tree(d)\n'
               '    with files.staged(d/"a.json","w",encoding="utf-8",new=False) as f:f.write("[]")\n'
               '    with files.staged(d/"c.json","w",encoding="utf-8",new=True) as f:f.write("1")\n'
               '    fd,x=files.new_file(d/"logs"/"d.log",".log");os.write(fd,b"half");os.close(fd)\n'
               '    files.register_tree(d);files.drop_journal(d)\n'
               'print(n["line"],n["swap"])')
        def run(mode,k,d):
            d.mkdir(parents=True)
            return subprocess.run([sys.executable,'-c',child,str(SCRIPTS),str(d),mode,str(k)],capture_output=True,text=True)
        whole=run('line',0,base/'whole');lines,swaps=map(int,whole.stdout.split()[-2:])
        assert lines>=12 and swaps>=5,whole.stdout+whole.stderr
        stops=[('line',k) for k in range(1,lines+1)]+[('swap',k) for k in range(1,swaps+1)]
        for mode,k in stops:
            d=base/f'{mode}_{k}';r=run(mode,k,d);assert r.returncode==9,(mode,k,r.stdout,r.stderr[-800:])
            keep=fs.adopt(d);left=fs.strays(d,keep)
            assert not left,(mode,k,[fs.relative(d,x) for x in left])
            assert not [x for x in fs.tree(d) if fs.relative(d,x) in fs.proofs(d)[0]],(mode,k)  # the half-written are gone
            assert fs.remove_own(d) and not fs.occupied(d),(mode,k,sorted(fs.relative(d,x) for x in fs.tree(d)))
        # A file put in a stopped run's folder, and a copy put in the place of one of its files, are not the run's:
        # they stay, and so does the folder.
        d=base/'with_mine';run('line',lines-3,d);shutil.copy2(d/'a.json',d/'a.json.copy');os.replace(d/'a.json.copy',d/'a.json')
        (d/'logs'/'mine.txt').write_text('mine',encoding='utf-8')
        keep=fs.adopt(d);assert sorted(fs.relative(d,x) for x in fs.strays(d,keep))==['a.json','logs/mine.txt'],fs.strays(d,keep)
        assert not fs.remove_own(d) and (d/'logs'/'mine.txt').is_file() and (d/'a.json').is_file()
        # A name the journal holds but found taken when it was to be made is someone else's, never the run's.
        d=base/'taken';d.mkdir()
        with fs.journaled(d) as j:
            j.append({'t':'.e.json.000000000000.part'});j.append({'x':'.e.json.000000000000.part'})
        (d/'.e.json.000000000000.part').write_text('theirs',encoding='utf-8')
        assert not fs.proven(d,d/'.e.json.000000000000.part') and fs.strays(d,fs.adopt(d))
        # A name alone proves nothing: the line goes before the file is made, which may then fail on a file someone else
        # has there, and a run stopped before noting the file made leaves the name alone.  Such a file stays, and is
        # named (GPT's review of 0.5, C01).
        d=base/'named_only';d.mkdir()
        with fs.journaled(d) as j:j.append({'t':'notes.txt'})
        (d/'notes.txt').write_text('mine',encoding='utf-8')
        keep=fs.adopt(d);assert not fs.proven(d,d/'notes.txt') and (d/'notes.txt').is_file() and fs.strays(d,keep)==[d/'notes.txt']
        # Nor does a name noted made prove the file there now: the proof is of the file the run made, by its number.
        # Written into, as a program writes its output or Python's open does, it is the same file and the run's.  A file
        # put under the name since (a copy of it even, or the file moved away and another made there) is not: it stays,
        # named, through adopt and remove_own, and so does a file under a made line that carries no number.  (GPT's
        # re-review of 0.5, RR01: the name alone had proved whatever file was there.)
        d=base/'made_then_written';d.mkdir()
        with fs.journaled(d):x=fs.stage_name(d/'f.wav','.wav')
        assert fs.proven(d,x)
        with open(x,'wb') as f:f.write(bytes(1000))
        assert fs.proven(d,x) and not fs.strays(d,fs.adopt(d)) and not x.exists()
        d=base/'made_then_replaced';d.mkdir()
        with fs.journaled(d):x=fs.stage_name(d/'f.wav','.wav')
        shutil.copy2(x,d/'f.copy');os.replace(d/'f.copy',x)
        keep=fs.adopt(d);assert not fs.proven(d,x) and x.is_file() and fs.strays(d,keep)==[x]
        assert not fs.remove_own(d) and x.is_file() and (d/fs.JOURNAL).is_file()
        d=base/'made_then_moved';d.mkdir()
        with fs.journaled(d):x=fs.stage_name(d/'f.wav','.wav')
        os.replace(x,base/'moved_away.wav');x.write_text('mine',encoding='utf-8')
        keep=fs.adopt(d);assert not fs.proven(d,x) and x.read_text(encoding='utf-8')=='mine' and fs.strays(d,keep)==[x]
        assert not fs.remove_own(d) and x.read_text(encoding='utf-8')=='mine' and (base/'moved_away.wav').is_file()
        d=base/'made_without_number';d.mkdir();x=d/'.k.wav.000000000000.wav'
        with fs.journaled(d) as j:j.append({'t':x.name});j.append({'c':x.name});j.append({'c':x.name,'i':True})
        x.write_bytes(b'x')
        assert fs.proofs(d)[0]=={x.name:frozenset()} and not fs.proven(d,x) and fs.strays(d,fs.adopt(d))==[x] and x.is_file()
        # A made file the run then replaces whole under its own name (write_wav swaps a finished file into a stage_name
        # file) is the run's by the stamp the journal noted as it took the name (a first fix took only the number).
        d=base/'made_then_rewritten';d.mkdir()
        with fs.journaled(d):
            x=fs.stage_name(d/'g.wav','.wav')
            with fs.staged(x) as f:f.write(b'whole')
        assert fs.proven(d,x) and not fs.strays(d,fs.adopt(d)) and not x.exists()
        # A write the system takes only part of is finished (os.write may return less than it is given), and a journal
        # whose last line a stop cut is taken up on a line of its own (GPT's review of 0.5, C02).
        d=base/'short_writes';d.mkdir();real=fs.os.write
        fs.os.write=lambda fd,data:real(fd,bytes(data)[:max(1,len(data)//2)])
        try:
            with fs.journaled(d):
                with fs.staged(d/'g.json') as f:f.write(b'{}')
        finally:fs.os.write=real
        assert fs.proven(d,d/'g.json') and all(json.loads(x) for x in (d/fs.JOURNAL).read_text(encoding='utf-8').splitlines())
        (d/fs.JOURNAL).write_bytes((d/fs.JOURNAL).read_bytes()+b'{"f":"cut')
        with fs.journaled(d):y=fs.stage_name(d/'h.wav','.wav')
        assert fs.proven(d,y) and fs.proven(d,d/'g.json')
        # A write that fails part way closes the journal, so the next line opens it anew, on a line of its own: written
        # on after the cut one it ran into it, and the file it announced went unproven (GPT's second re-review of 0.5,
        # R03: a render writes its report and its record after a failure, the journal still open).
        d=base/'failed_write';d.mkdir();fail=[False]
        def failing(fd,data):
            if fail[0]:fail[0]=False;real(fd,bytes(data)[:max(1,len(data)//2)]);raise OSError(5,'Input/output error')
            return real(fd,data)
        with fs.journaled(d):
            x=fs.stage_name(d/'k.wav','.wav');fs.os.write=failing;fail[0]=True
            try:rejects_with(OSError,lambda:fs.stage_name(d/'l.wav','.wav'))
            finally:fs.os.write=real
            y=fs.stage_name(d/'m.wav','.wav')
        cut=[z for z in (d/fs.JOURNAL).read_text(encoding='utf-8').splitlines() if not z.endswith('}')]
        assert len(cut)==1 and '.l.wav.' in cut[0] and fs.proven(d,x) and fs.proven(d,y) and sorted(p.name for p in d.iterdir())==sorted([fs.JOURNAL,x.name,y.name]),cut
        # A block journaling a folder inside another on the same folder leaves the outer journaling (GPT's review of
        # 0.5, C05), and a line nested too deeply to read is passed over, not a crash (C06).
        d=base/'nested';d.mkdir()
        with fs.journaled(d):
            with fs.journaled(d):
                with fs.staged(d/'i.json') as f:f.write(b'1')
            with fs.staged(d/'j.json') as f:f.write(b'2')
        assert fs.proven(d,d/'i.json') and fs.proven(d,d/'j.json')
        (d/fs.JOURNAL).write_bytes((d/fs.JOURNAL).read_bytes()+b'['*100000+b'\n')
        assert fs.proven(d,d/'j.json')
        # So is a whole line, its brackets closed, nested past MAX_DEPTH: the limit is this skill's, not the parser's
        # (the open brackets above stop any parser).  The lines after it are read.
        deep=b'{"f":"j.json","s":'+b'['*(fs.MAX_DEPTH+1)+b']'*(fs.MAX_DEPTH+1)+b'}\n'
        (d/fs.JOURNAL).write_bytes((d/fs.JOURNAL).read_bytes()+deep)
        with fs.journaled(d):y=fs.stage_name(d/'n.wav','.wav')
        assert json.loads(deep) and rejects(lambda:fs.loads(deep.decode())) and fs.proven(d,d/'j.json') and fs.proven(d,y)
        return {'stops':len(stops),'every_stop_left_only_its_own':True,'half_written_removed':True,'copy_and_note_not_taken':True,
                'a_name_alone_proves_nothing':True,'a_made_name_proves_only_the_file_made':True,'short_writes_finished':True,
                'nested_journal_kept':True}
    def writers_leave_whole_files_when_a_write_fails():
        # A write that fails part way, as on a full disk, leaves the file that was there whole and no temporary file:
        # every writer of a final file writes a new file of its own and swaps it in (musiclib.files.staged).  (Found by
        # the second review of 0.4.0: the WAV, bank, manifest and note writers wrote under the final name.)
        import errno
        from musiclib import files as fs,sf2,loop as lp
        from musiclib.review import review
        import soundbank as sb
        d=work/'full_disk';d.mkdir()
        class Full:
            # A file that takes 64 bytes, then reports the disk full.
            def __init__(self,f):self.f,self.n=f,0
            def write(self,b):
                if self.n+len(b)>64:self.f.write(b[:max(0,64-self.n)]);raise OSError(errno.ENOSPC,'No space left on device')
                self.n+=len(b);return self.f.write(b)
            def __getattr__(self,k):return getattr(self.f,k)
            def __enter__(self):return self
            def __exit__(self,*a):return self.f.__exit__(*a)
        tone=(.4*np.sin(2*np.pi*440*np.arange(4800)/48000)).astype(np.float32);both=np.stack([tone,tone],1)
        bank=lambda path:sf2.write(path,'tiny',[{'name':'A4','data':tone,'rate':48000,'root':69}],
                                   [{'name':'inst','global':{},'zones':[{'gens':{43:(60,80)},'sample':0}]}],
                                   [{'name':'tiny','bank':0,'program':0,'global':{},'zones':[{'gens':{},'instrument':0}]}])
        rows={'groups':[{'name':'g'}],'sources':[{'file':'s.wav'}],'notes':[{'file':f'g/n{k}.wav','sha256':'0'*64} for k in range(4)]}
        p=example()
        writers={'wav':lambda path:audio.write_wav(path,both),'float_wav':lambda path:sb.write_float_wav(path,both,44100),
                 'json':lambda path:fs.write_json(path,{'a':list(range(50))}),'bank':bank,'manifest':lambda path:sb.save_manifest(path,rows),
                 'midi':lambda path:midi.write(p,path),'loop':lambda path:lp.write_wav(path,both,0,len(both)),
                 'review':lambda path:review(p,path.parent)}
        real=os.fdopen
        for name,write in writers.items():
            folder=d/name;folder.mkdir();path=folder/('score_review.json' if name=='review' else f'out.{name}')
            path.write_bytes(b'the file that was there')
            os.fdopen=lambda *a,**k:Full(real(*a,**k))
            try:
                write(path);raise AssertionError(f'{name}: the full disk went unnoticed')
            except OSError as e:assert e.errno==errno.ENOSPC,(name,e)
            finally:os.fdopen=real
            assert path.read_bytes()==b'the file that was there' and [x.name for x in folder.iterdir()]==[path.name],(name,sorted(x.name for x in folder.iterdir()))
        # Windows refuses a rename while a virus scanner holds a file just written: the swap is tried again for up to a
        # second (files.replace), as pip and graceful-fs do; elsewhere a refusal is final.  (A selfcheck run on Windows
        # failed so, replacing a note's temporary file a moment after it was made.)
        real_replace=os.replace;refused=[]
        def scanner(src,dst):
            if len(refused)<2:
                refused.append(dst);raise PermissionError(13,'held by another program',str(dst))
            return real_replace(src,dst)
        os.replace=scanner
        try:
            if os.name=='nt':
                fs.write_json(d/'scanned.json',{'a':1});assert json.loads((d/'scanned.json').read_text(encoding='utf-8'))=={'a':1} and len(refused)==2
            else:
                try:
                    fs.write_json(d/'scanned.json',{'a':1});raise AssertionError('a refused rename went unnoticed')
                except PermissionError:pass
        finally:os.replace=real_replace
        assert not [x.name for x in d.iterdir() if x.name.startswith('.scanned')]
        # publish_new where a drive has no hard links (FAT on POSIX, some network drives): the empty reservation under
        # the output's name goes when the new file cannot take its place (it stayed, and the name looked taken; found
        # by GPT Pro's fourth review of 0.4.0).  Run here as on POSIX, with files' own os standing in.
        import types
        out=d/'reserved.json';src=d/'reserved.src';src.write_text('{}',encoding='utf-8')
        def no_link(*a,**k):raise OSError(errno.EOPNOTSUPP,'no hard links')
        def storage_fails(a,b,*x,**k):
            if Path(b)==out:raise OSError(errno.EIO,'storage failure')
            return os.replace(a,b,*x,**k)
        shim=types.SimpleNamespace(**{k:getattr(os,k) for k in dir(os) if not k.startswith('__')});shim.name,shim.link,shim.replace='posix',no_link,storage_fails
        real_os=fs.os;fs.os=shim
        try:assert rejects_with(OSError,lambda:fs.publish_new(src,out))
        finally:fs.os=real_os
        assert not fs.occupied(out) and src.is_file()
        # A bank the soundbank command found free is published only while it still is (sf2.write new).
        taken=d/'taken.sf2';taken.write_bytes(b'theirs');tone=(.3*np.sin(2*np.pi*440*np.arange(480)/48000)).astype(np.float32)
        assert rejects_with(FileExistsError,lambda:sf2.write(taken,'x',[{'name':'A4','data':tone,'rate':48000,'root':69}],[{'name':'i','global':{},'zones':[{'gens':{},'sample':0}]}],
                                                            [{'name':'x','bank':0,'program':0,'global':{},'zones':[{'gens':{},'instrument':0}]}],new=True))
        assert taken.read_bytes()==b'theirs'
        # On POSIX, a published output whose temporary name cannot then be removed is still noted as the run's (it
        # was not, and went unrecorded; found by GPT Pro's fifth review of 0.4.0).
        out=d/'linked_out.json';src=d/'linked_out.src';src.write_text('{}',encoding='utf-8');real_unlink=os.unlink
        def stuck(path,*a,**k):
            if Path(path)==src:raise OSError(errno.EIO,'storage failure')
            return real_unlink(path,*a,**k)
        shim=types.SimpleNamespace(**{k:getattr(os,k) for k in dir(os) if not k.startswith('__')});shim.name,shim.unlink='posix',stuck
        real_os=fs.os;fs.os=shim
        try:assert rejects_with(OSError,lambda:fs.publish_new(src,out))
        finally:fs.os=real_os
        assert out.is_file() and fs.written_here(out)
        return {'writers':sorted(writers),'refused_rename_retried':os.name=='nt','reservation_removed':True,'bank_not_over_a_taken_name':True}
    def run_stops_its_program_when_stopped():
        # A run stopped from outside (Ctrl+C, a failure in another part) stops the program it started and waits for it,
        # so nothing that program writes outlives the run.  (Found by the second review of 0.4.0.)
        import subprocess,sys
        started=[];real=subprocess.Popen
        class Interrupted(real):
            def __init__(self,*a,**k):super().__init__(*a,**k);started.append(self);self.asked=False
            def wait(self,timeout=None):
                if not self.asked:
                    self.asked=True;raise KeyboardInterrupt  # as Ctrl+C arrives while the run waits
                return super().wait(timeout)
        subprocess.Popen=Interrupted
        try:
            try:
                audio.run([sys.executable,'-c','import time;time.sleep(60)'],work/'stopped_run','sleeper');raise AssertionError('the stop went unnoticed')
            except KeyboardInterrupt:pass
        finally:subprocess.Popen=real
        assert len(started)==1 and started[0].poll() is not None,started
        # A part's program stops once another part of its render has failed (audio.cancel_scope): it ran to its end.
        import threading
        event=threading.Event();threading.Timer(.3,event.set).start();began=time.monotonic()
        try:
            with audio.cancel_scope(event):
                audio.run([sys.executable,'-c','import time;time.sleep(30)'],work/'cancelled_run','sleeper');raise AssertionError('not stopped')
        except audio.Cancelled:pass
        assert time.monotonic()-began<10,time.monotonic()-began
        # A part stopped before its program starts starts none; one waiting for memory or for a cache entry another
        # process holds stops waiting.  (A program started after the stop ran to its end, and a waiting part waited on,
        # then synthesized; found by GPT Pro's fourth review of 0.4.0.)
        import musiclib.render as rd
        stopped=threading.Event();stopped.set();ran=work/'ran_after_the_stop.txt'
        with audio.cancel_scope(stopped):
            assert rejects_with(audio.Cancelled,lambda:audio.run([sys.executable,'-c',f'open({str(ran)!r},"w").write("ran")'],work/'late_run','late'))
        assert not ran.exists()
        budget=rd.MemoryBudget(10_000);event=threading.Event();threading.Timer(.3,event.set).start();began=time.monotonic()
        with budget.hold(10_000):
            with audio.cancel_scope(event):
                assert rejects_with(audio.Cancelled,lambda:budget.hold(5_000).__enter__())
        waited_memory=time.monotonic()-began
        entry=work/'held_entry';entry.mkdir()
        code=('import sys,time;sys.path.insert(0,sys.argv[1]);from musiclib.render import entry_lock\n'
              'with entry_lock(sys.argv[2]) as held:\n    print(held,flush=True);time.sleep(20)')
        holder=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(entry)],stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='True'
            event=threading.Event();threading.Timer(.3,event.set).start();began=time.monotonic()
            def wait_for_entry():
                with rd.entry_lock(entry):raise AssertionError('took an entry another process holds')
            with audio.cancel_scope(event):
                assert rejects_with(audio.Cancelled,wait_for_entry)
            waited_entry=time.monotonic()-began
        finally:
            holder.kill();holder.wait(timeout=30);holder.stdout.close()
        assert waited_memory<5 and waited_entry<5,(waited_memory,waited_entry)
        return {'program_stopped':True,'returncode':started[0].returncode,'stopped_with_its_render':True,
                'no_program_after_the_stop':True,'memory_wait_stopped_s':round(waited_memory,2),'entry_wait_stopped_s':round(waited_entry,2)}
    def clean_and_runs_never_share_a_folder():
        # A render, round or audition holds its folder's work lock while it runs (musiclib.files.working); clean takes
        # the same lock before it looks inside a folder.  A folder in use, or inside one in use, is left alone and named,
        # a second run there is refused, and once the run ends its lock file is gone.  (Found by the second review of
        # 0.4.0: clean could remove the files of a round or a resumed render at work.)
        import subprocess,sys
        from musiclib import files as fs
        from musiclib.clean import clean
        H=lambda c:c*64
        def made(folder,title):
            folder.mkdir(parents=True);save_json(folder/'render_input.json',{'project_sha256':H('a'),'renderer_sha256':H('b')})
            save_json(folder/'project.json',{'title':title,'tracks':[]});save_json(folder/'stem_receipts.json',[]);(folder/'master.wav').write_bytes(bytes(1000))
            fs.register(folder,[folder/n for n in ('render_input.json','project.json','stem_receipts.json','master.wav')]);return folder
        piece=work/'lock_cases';final=made(piece/'final','Song');busy=made(piece/'r_busy','Song');idle=made(piece/'r_idle','Song')
        rnd=piece/'r_round';rnd.mkdir()
        save_json(rnd/'round.json',{'kind':'music-production round','title':'Song','project':'../song.json','status':'FAIL','review':'review/score_review.json','render':'render/report.json','seconds':{}})
        fs.register(rnd,[rnd/'round.json']);made(rnd/'render','Song')
        code=('import sys,time;sys.path.insert(0,sys.argv[1]);from musiclib import files\n'
              'with files.working(sys.argv[2]) as one,files.working(sys.argv[3]) as two:\n    print(one and two,flush=True);time.sleep(6)')
        holder=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(busy),str(rnd)],stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='True'
            assert fs.take(busy)[0]=='busy' and rejects(lambda:fs.working(busy).__enter__())
            # A reference render is held while it is read too, so one a run is still writing is refused (it was read
            # unheld, and a clean could take its master mid-read; found by GPT Pro's fourth review of 0.4.0).
            from musiclib.analysis import load_reference
            try:load_reference(str(busy));raise AssertionError('a reference in use was read')
            except ValueError as e:assert 'in use' in str(e),e
            dry=clean(piece,[final]);done=clean(piece,[final],remove=True)
        finally:
            holder.wait(timeout=60);holder.stdout.close()
        for r in (dry,done):
            left={Path(x['path']).as_posix():x['why'] for x in r['left_alone']}
            assert [Path(x['path']).as_posix() for x in r['listed']]==['r_idle'] and set(left)=={'r_busy','r_round','r_round/render'},r
            assert all('working in it' in why for why in left.values()),left
        assert (busy/'master.wav').is_file() and (rnd/'render'/'master.wav').is_file() and not idle.exists()
        assert not fs.occupied(busy/fs.WORK_LOCK) and not fs.occupied(rnd/fs.WORK_LOCK)  # each went with its run
        again=clean(piece,[final],remove=True)
        assert sorted(Path(x['path']).as_posix() for x in again['listed'])==['r_busy','r_round','r_round/render'] and not busy.exists() and not rnd.exists(),again
        return {'busy_left_alone':True,'inside_busy_left_alone':True,'second_run_refused':True,'lock_file_gone_after_the_run':True}
    def render_refuses_a_linked_output():
        # A render's output given as a link is refused before it is resolved, which would follow the link and write
        # wherever it leads.  (Found by the second review of 0.4.0.)
        import subprocess
        from musiclib.render import render
        target=work/'link_target';target.mkdir();at=work/'render_through_link'
        if os.name=='nt':made=subprocess.run(['cmd','/c','mklink','/J',str(at),str(target)],capture_output=True).returncode==0
        else:
            os.symlink(target,at,target_is_directory=True);made=True
        if made:
            try:
                render(work/'no_such_project.json',at,None);raise AssertionError('a linked output was taken')
            except ValueError as e:assert 'is a link' in str(e),e  # refused for being a link, not for what it leads to
            assert not list(target.iterdir())
            # Likewise a cache given as a link: it was resolved first, and the check after saw the folder it led to
            # (GPT's security audit of 0.5, S03).
            try:
                render(work/'no_such_project.json',work/'render_cache_through_link',None,cache=at);raise AssertionError('a linked cache was taken')
            except ValueError as e:assert 'cache' in str(e) and 'is a link' in str(e),e
            assert not list(target.iterdir()) and not (work/'render_cache_through_link').exists()
        return {'link_refused':made}
    def bounded_reads_of_records_and_wav_headers():
        # A WAV format chunk larger than any format needs, and a stopped render's report.json larger than a record may
        # be, are refused before they are read whole.  (Found by the second review of 0.4.0.)
        from musiclib import files as fs
        from musiclib.render import stopped
        wav=work/'huge_fmt.wav';wav.write_bytes(b'RIFF'+struct.pack('<I',4020)+b'WAVE'+b'fmt '+struct.pack('<I',4000)+bytes(4000)+b'data'+struct.pack('<I',0))
        try:
            audio.read_wav(wav);raise AssertionError('a 4000-byte format chunk was read')
        except ValueError as e:assert 'format chunk' in str(e),e
        # A format chunk shorter than a format, a frame size of 0, and one that is not the channels times the sample's
        # bytes are refused as WAVs: they stopped the reader with struct.error and ZeroDivisionError, or made its
        # length limit count other frames than it then read (GPT's security audit of 0.5, L04).  16-bit PCM is read.
        def odd_wav(fmt,data=bytes(16)):
            (work/'odd_fmt.wav').write_bytes(b'RIFF'+struct.pack('<I',20+len(fmt)+len(data))+b'WAVEfmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(data))+data)
            return work/'odd_fmt.wav'
        for fmt in (struct.pack('<HHI',1,2,audio.RATE),struct.pack('<HHIIHH',1,2,audio.RATE,audio.RATE*4,0,16),struct.pack('<HHIIHH',1,2,audio.RATE,audio.RATE*4,2,16),
                    struct.pack('<HHIIHH',3,2,audio.RATE,audio.RATE*8,4,32)):
            assert rejects(lambda:audio.read_wav(odd_wav(fmt)))
        assert len(audio.read_wav(odd_wav(struct.pack('<HHIIHH',1,2,audio.RATE,audio.RATE*4,4,16)))[0])==4
        folder=work/'stopped_big';folder.mkdir();save_json(folder/'report.json',{'failed':{'error':'x'*200}})
        assert stopped(folder)=='x'*200
        real=fs.MAX_RECORD;fs.MAX_RECORD=100
        try:assert stopped(folder) is None
        finally:fs.MAX_RECORD=real
        # JSON nested deeper than Python parses, a SoundFont cut short inside a chunk and a loop's chunks shorter than
        # what they count are refused with a reason, and a record so nested is no record (it raised RecursionError and
        # struct.error, and stopped clean).  (Found by the stress test of 0.4.0.)
        from musiclib import loop as lp,sf2
        from musiclib.model import load_project
        deep=work/'deep.json';deep.write_text('['*100000+']'*100000,encoding='utf-8')
        assert rejects(lambda:load_project(deep))
        # Python 3.14 parses those 100,000 levels, and a free-form harmony 600 levels deep, which every Python parses,
        # passed validate and stopped excerpt's copy of the project with RecursionError: JSON is read to MAX_DEPTH
        # levels, no deeper (found by CI on Python 3.14).
        assert fs.loads('['*fs.MAX_DEPTH+']'*fs.MAX_DEPTH) and rejects(lambda:fs.loads('['*(fs.MAX_DEPTH+1)+']'*(fs.MAX_DEPTH+1)))
        nested=[]
        for _ in range(600):nested=[nested]
        q=example();q['harmony']={'chart':nested};(work/'deep_harmony.json').write_text(json.dumps(q),encoding='utf-8')
        assert rejects(lambda:load_project(work/'deep_harmony.json'))
        q['harmony']={'chart':[[['C','G']]]};(work/'deep_harmony.json').write_text(json.dumps(q),encoding='utf-8');load_project(work/'deep_harmony.json')
        (work/'deep_record').mkdir();(work/'deep_record'/fs.RECORD).write_text('{"kind": '+'['*100000+']'*100000+'}',encoding='utf-8')
        assert fs.recorded(work/'deep_record')=={} and not fs.is_record(work/'deep_record'/fs.RECORD)
        tone=(.4*np.sin(2*np.pi*440*np.arange(480)/48000)).astype(np.float32)
        sf2.write(work/'cut_short.sf2','x',[{'name':'A4','data':tone,'rate':48000,'root':69}],[{'name':'i','global':{},'zones':[{'gens':{},'sample':0}]}],
                  [{'name':'x','bank':0,'program':0,'global':{},'zones':[{'gens':{},'instrument':0}]}])
        data=bytearray((work/'cut_short.sf2').read_bytes());at=data.find(b'ifil');data[at+4:at+8]=struct.pack('<I',2)
        (work/'cut_short.sf2').write_bytes(bytes(data));assert rejects(lambda:sf2.read(work/'cut_short.sf2'))
        body=b'WAVE'+b'smpl'+struct.pack('<I',40)+struct.pack('<9I',0,0,20833,60,0,0,0,5,0)+bytes(4)
        (work/'short_smpl.wav').write_bytes(b'RIFF'+struct.pack('<I',len(body))+body);assert rejects(lambda:lp.read_smpl(work/'short_smpl.wav'))
        body=b'WAVE'+b'cue '+struct.pack('<I',4)+struct.pack('<I',3)
        (work/'short_cue.wav').write_bytes(b'RIFF'+struct.pack('<I',len(body))+body);assert rejects(lambda:lp.read_cues(work/'short_cue.wav'))
        # From GPT Pro's third review: a report read through the shared reader is refused as a link or over its limit
        # before it is read; an output found free is never put in the place of one that took its name meanwhile; and a
        # drum part whose kit the bank lacks is refused before synthesis (FluidSynth put kit 0 in its place).
        big=work/'big_report.json';big.write_text('{"a": "'+'x'*500+'"}',encoding='utf-8')
        assert rejects(lambda:fs.read_json(big,limit=100)) and fs.read_json(big)['a']=='x'*500
        taken=work/'taken.json';taken.write_text('{"theirs": true}',encoding='utf-8')
        try:
            save_json(taken,{'mine':True},new=True);raise AssertionError('written over a file that took the name')
        except FileExistsError:pass
        assert json.loads(taken.read_text(encoding='utf-8'))=={'theirs':True} and not [x for x in work.iterdir() if x.name.startswith('.taken.json')]
        from musiclib import layered
        kit={'id':'kit','drums':True,'program':80,'performance':{'notes':{}}}
        assert 'no preset at bank 128 program 80' in layered.unsupported(kit,work/'tiny.sf2')  # sf2_writer_reader_roundtrip's bank
        kit['drums']=False;kit['program']=0;assert layered.unsupported(kit,work/'tiny.sf2') is None
        return {'format_chunk_refused':True,'oversized_report_not_read':True,'deep_json_refused':True,'short_chunks_refused':True,
                'bounded_reader':True,'new_output_never_over_another':True,'missing_kit_refused':True}
    def shared_reports_name_folders_relatively():
        # A comparison is saved with the renders and the clip relative to its folder: no local folders or user name.
        from musiclib.compare import portable
        base=work/'portable';(base/'r1'/'render').mkdir(parents=True);(base/'r2'/'render').mkdir(parents=True)
        r=portable({'before':base/'r1'/'render','after':base/'r2'/'render','clip':{'file':base/'r2'/'clip.mp3'}},base/'r2'/'render')
        assert r['before']=='../../r1/render' and r['after']=='.' and r['clip']['file']=='../clip.mp3',r
        return {'relative':True}
    def selfcheck_work_must_be_new_or_empty():
        import subprocess,sys
        busy=work/'busy_work';busy.mkdir();(busy/'roundtrip.mid').write_bytes(b'mine')
        r=subprocess.run([sys.executable,str((SCRIPTS/'selfcheck.py')),'--work',str(busy)],capture_output=True,text=True,timeout=120)
        assert r.returncode==2 and 'not empty' in r.stderr and (busy/'roundtrip.mid').read_bytes()==b'mine',(r.returncode,r.stderr)
        return {'refused':True}
    def render_folders_are_read_without_links():
        # analyze and compare read a render folder's own files only: one holding a link (here its stems folder, a
        # junction on Windows) is refused before any audio is read; and no WAV longer than a render is read at all.
        import subprocess
        from musiclib.compare import load
        from musiclib.analysis import analyze
        r=work/'linked_render';(r/'stems').mkdir(parents=True);outside=work/'outside_stems';outside.mkdir()
        save_json(r/'project.json',example());save_json(r/'report.json',{});save_json(r/'stem_receipts.json',[])
        load(r)  # a folder of its own files is read
        (r/'master.wav').write_bytes(b'no audio: read before the links are refused, it would fail as no WAV')   # analyze names a folder without one (2.1)
        shutil.rmtree(r/'stems')
        made=subprocess.run(['cmd','/c','mklink','/J',str(r/'stems'),str(outside)],capture_output=True).returncode==0 if os.name=='nt' else (os.symlink(outside,r/'stems',target_is_directory=True) or True)
        assert made
        for read in (lambda:load(r),lambda:analyze(r)):
            try:read();raise AssertionError('a render folder holding a link was read')
            except ValueError as e:assert 'links' in str(e),e
        # the piano roll reads a render folder so too: its still and its video took a project or a master through a link
        # (the whole review of 0.8); refused before Pillow is asked for, so this holds where it is not installed
        from musiclib import roll as rl
        for read in (lambda:rl.still(r,1,work/'roll_links.png'),lambda:rl.Roll(r)):
            try:read();raise AssertionError('a render folder holding a link drawn')
            except ValueError as e:assert 'links' in str(e),e
        # a linked file too (project.json leading outside), where this machine lets a file link be made (the Astra
        # review of step 2); the details stay those of 0.7.0's check
        # (its other records there, so the link is what refuses it: without them compare stopped at "report.json is
        # missing" where links can be made, the third review)
        f=work/'linked_file_render';f.mkdir();save_json(work/'outside_project.json',example());(f/'master.wav').write_bytes(b'no audio')
        save_json(f/'report.json',{});save_json(f/'stem_receipts.json',[])
        try:os.symlink(work/'outside_project.json',f/'project.json');filelink=True
        except OSError:filelink=False
        if filelink:
            for read in (lambda:load(f),lambda:analyze(f),lambda:rl.still(f,1,work/'roll_filelink.png')):
                try:read();raise AssertionError('a render folder holding a file link was read')
                except ValueError as e:assert 'links' in str(e),e
        # The render folder inside a round, or the folder given, that is itself a link is refused before its lock is
        # taken or a report written behind it: analyze of a round from elsewhere wrote its report into the folder the
        # round's render/ led to (GPT's security audit of 0.5, S03).
        import sys
        from musiclib.revision import render_folder
        link=lambda at,to:subprocess.run(['cmd','/c','mklink','/J',str(at),str(to)],capture_output=True).returncode==0 if os.name=='nt' else (os.symlink(to,at,target_is_directory=True) or True)
        rnd=work/'linked_round';rnd.mkdir();save_json(rnd/'round.json',{'kind':'music-production round','title':'Song'});behind=work/'round_behind';behind.mkdir()
        assert link(rnd/'render',behind) and link(work/'linked_given',behind)
        for given in (rnd,work/'linked_given'):
            try:render_folder(given);raise AssertionError('a linked render folder was taken')
            except ValueError as e:assert 'is a link' in str(e),e
            for argv in (['analyze',str(given)],['compare',str(given),str(r)],['compare',str(r),str(given)]):
                done=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),*argv],capture_output=True,text=True)
                assert done.returncode==2 and 'is a link' in done.stderr,(argv,done.stderr[-300:])
        # still and video refuse a linked render folder before they take its lock, which would be made behind the link
        # (a spy on files.take: no folder asked for); video before its configuration is read
        from musiclib import files as fs
        taken,real_take=[],fs.take
        fs.take=lambda folder,*a,**k:(taken.append(folder),real_take(folder,*a,**k))[1]
        try:
            for given in (rnd/'render',work/'linked_given'):
                for draw in (lambda:rl.still(given,1,work/'roll_linked.png'),lambda:rl.video(given,work/'roll_linked.webm',work/'no_config.json')):
                    try:draw();raise AssertionError('a linked render folder drawn')
                    except ValueError as e:assert 'is a link' in str(e),e
        finally:fs.take=real_take
        assert not taken,taken
        assert not list(behind.iterdir())
        # and they hold a render while they read it, as analyze does: one another run holds is refused (a render still
        # writing its master was taken whole)
        held_r=work/'held_render';held_r.mkdir();save_json(held_r/'project.json',example())
        code=('import sys;sys.path.insert(0,sys.argv[1]);from musiclib import files\n'
              'with files.working(sys.argv[2]) as held:\n    print(held,flush=True);sys.stdin.readline()')
        holder=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(held_r)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            if holder.stdout.readline().strip()=='True':   # a drive that cannot lock files lets every run through (files.working)
                for draw in (lambda:rl.still(held_r,1,work/'roll_held.png'),lambda:rl.video(held_r,work/'roll_held.webm',work/'no_config.json')):
                    try:draw();raise AssertionError('a render another run holds drawn')
                    except ValueError as e:assert 'is in use' in str(e),e
        finally:
            holder.stdin.write('\n');holder.stdin.flush();holder.wait()
        plain=work/'plain_round';(plain/'render').mkdir(parents=True);save_json(plain/'round.json',{'kind':'music-production round'})
        assert render_folder(plain)==plain/'render' and render_folder(plain/'render')==plain/'render'
        long=work/'long.wav';audio.write_wav(long,np.zeros((3*audio.RATE,2),dtype=np.float32));limit=audio.MAX_WAV_SECONDS
        # At the limit's edge: a WAV exactly as long is read, one frame more is refused (a mutant of `>` into `>=`
        # refused a reference of exactly 1860 s, which analyze --reference passes on: the outside review of 2026-11-15).
        edge,over=work/'edge.wav',work/'edge_over.wav'
        audio.write_wav(edge,np.zeros((2*audio.RATE,2),dtype=np.float32));audio.write_wav(over,np.zeros((2*audio.RATE+1,2),dtype=np.float32))
        try:
            audio.MAX_WAV_SECONDS=2;rejects(lambda:audio.read_wav(long));rejects(lambda:audio.read_wav(over))
            assert len(audio.read_wav(edge)[0])==2*audio.RATE
        finally:audio.MAX_WAV_SECONDS=limit
        audio.read_wav(long)
        return {'refused':2}
    def long_paths_for_programs():
        # 0.9 step 1 (design-0.9.md): Windows' plain file calls stop at 260 characters, the terminating null included
        # (Microsoft Learn, Maximum Path Length Limitation).  FluidSynth opens its files through them, so a path at the
        # limit or past it goes to it in the extended-length form, which those calls take at any length; a shorter one
        # goes as it is, so the receipts of a render in an ordinary folder read as they did.  No program is started in a
        # working folder Windows refuses to start one in (measured: design-0.9.md), and an error on a long path where the
        # system's long paths are off says so.  The forms are tested with Windows' rules on every system.
        from musiclib import files as fs
        B=chr(92);X=B*2+'?'+B;L=fs.WINDOWS_PATH_LIMIT;F=fs.WINDOWS_FOLDER_LIMIT
        (work/'room').mkdir(exist_ok=True)   # where this check writes, on every system (made on Windows alone, the new-file names failed everywhere else)
        def of_length(n,head='C:'+B+'work',tail='take.wav'):
            parts=[head];left=n-len(head)-1-len(tail)
            while left>40:parts.append('d'*30);left-=31
            if left>0:parts.append('e'*(left-1))
            path=B.join(parts+[tail]);assert len(path)==n,(len(path),n);return path
        short=of_length(fs.PROGRAM_PATH_MAX);assert fs.for_program(short,windows=True)==short   # the longest that goes as it is
        edge=of_length(fs.PROGRAM_PATH_MAX+1);assert fs.for_program(edge,windows=True)==X+edge
        far=of_length(400);assert fs.for_program(far,windows=True)==X+far and fs.for_program(far,windows=False)==far
        assert fs.PROGRAM_PATH_MAX<L-1   # the form changes before the calls stop, never after
        assert fs.for_program(X+far,windows=True)==X+far   # already extended: left alone
        assert fs.for_program(far.replace(B,'/'),windows=True)==X+far   # the extended form takes backslashes only
        assert fs.for_program(of_length(400,tail='x'+B+'..'+B+'take.wav'),windows=True)==X+of_length(400-5)   # and no . or .. (they are not resolved in it)
        unc=of_length(400,head=B*2+'server'+B+'share');assert fs.for_program(unc,windows=True)==X+'UNC'+B+unc[2:]
        assert fs.for_program(Path('take.wav'),windows=False)=='take.wav'
        assert not fs.past_path_limit(of_length(L-1),windows=True) and fs.past_path_limit(of_length(L),windows=True) and not fs.past_path_limit(far,windows=False)
        # counted in UTF-16 units, as Windows counts: a character outside the Basic Multilingual Plane is two
        note=chr(0x1F3B5);wide=short[:-9]+note+short[-8:];assert len(wide)==len(short) and fs.for_program(wide,windows=True)==X+wide
        assert fs.past_path_limit(of_length(L-1)[:-9]+note+'take.wav',windows=True)
        try:fs.program_folder(of_length(F-1,tail='f')[:-1]+note,windows=True);raise AssertionError('a working folder of 259 units taken')
        except ValueError as e:assert f'is {F} characters long' in str(e),e
        if os.name=='nt':   # a relative path is measured as Windows resolves it, against the working folder
            here=os.getcwd()
            try:
                room=work/'room';room.mkdir(exist_ok=True);os.chdir(room);base=os.getcwd()
                name='n'*(fs.PROGRAM_PATH_MAX+1-len(base.encode('utf-16-le','surrogatepass'))//2-1)   # in the units Windows counts
                if len(name)>=2:   # (a work folder that leaves no room for a name has no such case)
                    full=(X+'UNC'+base[1:] if base.startswith(B*2) else X+base)+B+name   # a work folder on a share takes the UNC form
                    assert fs.for_program(name)==full and fs.for_program(name[:-1])==name[:-1]
            finally:os.chdir(here)
        # a working folder: one a program can be started in is given back as it came, a longer one is refused by name
        ok=of_length(F-1,tail='f');assert fs.program_folder(ok,windows=True)==ok and fs.program_folder(None,windows=True) is None
        assert fs.program_folder(far,windows=False)==far
        assert not fs.past_folder_limit(ok,windows=True) and fs.past_folder_limit(of_length(F,tail='f'),windows=True) and not fs.past_folder_limit(far,windows=False)
        try:fs.program_folder(of_length(F,tail='f'),windows=True);raise AssertionError('a working folder at the limit taken')
        except ValueError as e:assert f'is {F} characters long' in str(e),e
        # the hint: only on Windows, only for a path at the limit or past it, only where long paths are off
        gone=FileNotFoundError(2,'No such file or directory',far)
        hint=fs.path_limit_hint(gone,windows=True,long_paths=False);assert '400 characters' in hint and '260' in hint and 'shorter' in hint,hint
        assert fs.path_limit_hint(gone,windows=True,long_paths=True)=='' and fs.path_limit_hint(gone,windows=False,long_paths=False)==''
        assert fs.path_limit_hint(FileNotFoundError(2,'No such file or directory',short),windows=True,long_paths=False)==''
        assert fs.path_limit_hint(OSError(22,'Invalid argument'),windows=True,long_paths=False)==''
        assert fs.path_limit_hint(ValueError('x'),windows=True,long_paths=False)==''
        assert fs.path_limit_hint(FileNotFoundError(2,'No such file or directory',X+far),windows=True,long_paths=False)==''   # the extended form opens at any length
        both=OSError(2,'No such file or directory',short,None,far);assert '400 characters' in fs.path_limit_hint(both,windows=True,long_paths=False)
        assert '400 characters' in fs.path_limit_hint(far,windows=True,long_paths=False) and fs.path_limit_hint(short,windows=True,long_paths=False)==''   # a path itself, for a message that it was not found
        # a new file's own name is short whatever its destination is called (the journal, not the name, proves it the run's)
        for suffix in ('.part','.wav','.log','.mid','.copy'):
            fd,temp=fs.new_file(work/'room'/('fluidsynth_take_12_1.process'+'x'*40+'.json'),suffix);os.close(fd)
            assert temp.is_file() and temp.parent==work/'room' and temp.name.startswith('.fluidsynth_take_.') and len(temp.name)==1+fs.TEMP_STEM+1+12+len(suffix)==30+len(suffix),temp.name
        fd,temp=fs.new_file(work/'room'/'a.json');os.close(fd);assert temp.name.startswith('.a.json.') and len(temp.name)==8+12+5   # a short name is whole
        # a record or a configuration that is not there: the error names the file, so the hint reads it, in the words it had
        try:fs.read_json(far);raise AssertionError('read')
        except FileNotFoundError as e:assert str(e)==far+' is not there' and '400 characters' in fs.path_limit_hint(e,windows=True,long_paths=False),e
        used='on Windows only'
        if os.name=='nt':
            # where the rules are used: a program is not started in a folder past the limit (the run, the starter's
            # script), and the commands' error line carries the hint (long paths taken as off for the two commands)
            import subprocess,sys
            from musiclib import starter
            there=work/'room'/B.join(['w'*40]*7)   # not made: each stops before it touches the folder
            for start in (lambda:audio.run([sys.executable,'-c','pass'],work/'room'/'logs','deep_cwd',cwd=there),lambda:starter.start(there,'A piece','a:4','piano')):
                try:start();raise AssertionError('started in a folder past the limit')
                except ValueError as e:assert 'characters long, and Windows starts no program' in str(e),e
            assert not there.exists() and not (work/'room'/'logs'/'deep_cwd.log').exists()
            off=('import sys,runpy;from musiclib import files;files.long_paths_enabled=lambda:False;'
                 'sys.argv=["studio.py"]+sys.argv[1:];runpy.run_path("studio.py",run_name="__main__")')
            cases=[('validate',there/'song.json'),('inspect-midi',there/'song.mid')]   # a message of the tools' own; the system's error
            # a render folder of 247 units, the longest Windows makes with long paths off (a folder's limit is 248), whose
            # project.json lies at 260; made only where the work folder leaves a name of that length
            render=work/'room'/('r'*max(1,247-fs._full_length(work/'room')[0]-1))
            if fs._full_length(render)[0]==247 and fs._full_length(render/'project.json')[0]==L:
                render.mkdir(exist_ok=True);cases.append(('still',render,'--at','0','--output',work/'room'/'hint.png'))
            for args in cases:
                done=subprocess.run([sys.executable,'-c',off,*map(str,args)],cwd=SCRIPTS,capture_output=True,text=True,encoding='utf-8',errors='replace')
                assert done.returncode==2 and 'characters long: this Windows opens no path of 260' in done.stderr and done.stderr.count('\n')==1,(args[0],done.stderr[-400:])
            used='the run, the starter, the commands\' error line'
        return {'used':used,'extended_from':fs.PROGRAM_PATH_MAX+1,'folder_limit':F,'counted_in':'UTF-16 units','forms':['as it is','extended','UNC','slashes','dot segments','relative: on Windows, where the work folder leaves room']}
    def clean_takes_reviews_and_lists_only_what_goes():
        # 0.9.2 (design-0.9.2.md, T1): the review folders six runs were left with, by the same proof as every other tool's
        # folder; a folder of which nothing goes is no longer listed; the list is cut after the folders, and says how to see it all.
        from make_example import example
        from musiclib import files as record
        from musiclib.clean import clean,describe
        from musiclib.review import review
        base=work/'clean_reviews';base.mkdir();song=example()
        final=base/'final';final.mkdir();save_json(final/'render_input.json',{'project_sha256':'a'*64,'renderer_sha256':'b'*64})
        save_json(final/'project.json',{'title':song['title'],'tracks':[]});save_json(final/'stem_receipts.json',[])
        record.register(final,[final/n for n in ('render_input.json','project.json','stem_receipts.json')])
        mine=base/'review_a';review(song,mine)
        other=example();other['title']='Another piece';theirs=base/'review_other';review(other,theirs)
        noted=base/'review_noted';review(song,noted);(noted/'my_note.txt').write_text('keep',encoding='utf-8')
        changed=base/'review_changed';review(song,changed);(changed/'notes.csv').write_text('edited by hand',encoding='utf-8')
        plain=base/'not_a_review';plain.mkdir();save_json(plain/'score_review.json',{'title':song['title']})
        unrecorded=base/'review_without_record';review(song,unrecorded);(unrecorded/record.RECORD).unlink()
        looked=clean(base,[final]);got={x['path']:x['whole'] for x in looked['listed']}
        assert got=={'review_a':True,'review_noted':False,'review_changed':False},got
        assert all((mine/n).is_file() for n in ('score_review.json','notes.csv','arrangement.md')),'a listing removes nothing'
        left={x['path']:x['why'] for x in looked['left_alone']};assert 'another piece' in left.get('review_other','') and 'no record' in left.get('review_without_record',''),left
        size=sum(x.stat().st_size for x in mine.iterdir() if x.is_file() and not record.is_lock_file(x))   # every file it takes, its records too
        assert next(x['bytes'] for x in looked['listed'] if x['path']=='review_a')==size,(looked['listed'],size)
        done=clean(base,[final],remove=True);assert next(x['bytes'] for x in done['listed'] if x['path']=='review_a')==size,done['listed']
        assert not mine.exists() and (theirs/'score_review.json').is_file() and (plain/'score_review.json').is_file() and (unrecorded/'notes.csv').is_file()
        assert (noted/'my_note.txt').read_text(encoding='utf-8')=='keep' and not (noted/'notes.csv').exists() and (noted/'score_review.json').is_file()
        assert (changed/'notes.csv').read_text(encoding='utf-8')=='edited by hand' and (final/'render_input.json').is_file()
        again=clean(base,[final]);still={x['path']:x['why'] for x in again['left_alone']}   # nothing more of these can go: named as left, not as removed
        assert not again['listed'] and 'review_noted/my_note.txt' in still.get('review_noted','') and 'review_changed/notes.csv' in still.get('review_changed',''),again
        # A finished audition down to what it keeps (its MP3 and report) is no longer listed; with anything more of the tools' it is.
        aud=base/'aud';aud.mkdir();save_json(aud/'audition.json',{'kind':'music-production audition','title':song['title'],'versions':[],'bars':[1,2],'track':'t','each_seconds':1,'status':'PASS'})
        (aud/'audition.mp3').write_bytes(bytes(100));record.register(aud,[aud/'audition.json',aud/'audition.mp3'])
        now=clean(base,[final]);assert not any(x['path']=='aud' for x in now['listed']+now['left_alone']),now
        (aud/'stale.log').write_bytes(bytes(10));record.register(aud,[aud/'stale.log'])
        assert any(x['path']=='aud' and x['bytes']==10 for x in clean(base,[final])['listed'])
        (aud/'stale.log').unlink();(aud/'my_note.txt').write_text('hear it again',encoding='utf-8')   # a note of the user's beside them: nothing goes, so nothing is counted
        now=clean(base,[final]);assert not any(x['path']=='aud' for x in now['listed']) and any(x['path']=='aud' and 'aud/my_note.txt' in x['why'] for x in now['left_alone']),now
        (aud/'alternate-takes').mkdir()   # an empty folder clean takes nothing from is not touched
        # An audition's own cache that a kept render plays (`--cache` on it): the take it uses stays, since it cannot be made again, and each other entry goes once.
        keyed='ab'*10;other_key='cd'*10;shared=base/'aud2';(shared/'cache'/keyed).mkdir(parents=True);(shared/'cache'/other_key).mkdir()
        for k in (keyed,other_key):save_json(shared/'cache'/k/'receipt.json',{'key':k,'sha256':'c'*64,'track':'t'});(shared/'cache'/k/'raw.wav').write_bytes(bytes(50))
        save_json(shared/'audition.json',{'kind':'music-production audition','title':song['title'],'versions':[],'bars':[1,2],'track':'t','each_seconds':1,'status':'PASS'})
        (shared/'audition.mp3').write_bytes(bytes(10));record.register(shared,[shared/'audition.json',shared/'audition.mp3'])
        save_json(final/'stem_receipts.json',[{'track':'t','cache_key':keyed}]);record.register(final,[final/'stem_receipts.json'])
        listed=[x['path'] for x in clean(base,[final])['listed']]
        assert len(listed)==len(set(listed)) and f'aud2/cache/{other_key}' in listed and f'aud2/cache/{keyed}' not in listed,listed
        gone=clean(base,[final],remove=True);assert gone['not_removed']==[] and (shared/'cache'/keyed/'raw.wav').is_file() and not (shared/'cache'/other_key).exists() and (shared/'audition.mp3').is_file(),gone
        assert any(x['path']=='aud2' and f'aud2/cache/{keyed}/' in x['why'] for x in gone['left_alone']),gone['left_alone']
        assert (aud/'alternate-takes').is_dir() and (aud/'my_note.txt').is_file(),'a removal takes what the list named and no more'
        # A cache inside a render that goes (`--cache older/cache`): the take a kept render plays stays with the render's record, the other goes.
        inner='ef'*10;spare='0a'*10;older=base/'older';older.mkdir()
        save_json(older/'render_input.json',{'project_sha256':'a'*64,'renderer_sha256':'b'*64});save_json(older/'project.json',{'title':song['title'],'tracks':[]});save_json(older/'stem_receipts.json',[])
        record.register(older,[older/n for n in ('render_input.json','project.json','stem_receipts.json')])
        for k in (inner,spare):
            (older/'cache'/k).mkdir(parents=True);save_json(older/'cache'/k/'receipt.json',{'key':k,'sha256':'c'*64,'track':'t'});(older/'cache'/k/'raw.wav').write_bytes(bytes(50))
            record.register(older/'cache'/k,[older/'cache'/k/'receipt.json',older/'cache'/k/'raw.wav'])
        save_json(final/'stem_receipts.json',[{'track':'t','cache_key':keyed},{'track':'u','cache_key':inner}]);record.register(final,[final/'stem_receipts.json'])
        gone=clean(base,[final],remove=True);assert (older/'cache'/inner/'raw.wav').is_file() and (older/'cache'/inner/'receipt.json').is_file() and not (older/'cache'/spare).exists(),gone
        row=next(x for x in gone['listed']+gone['left_alone'] if x['path']=='older');assert f'older/cache/{inner}/' in (row.get('why') or ' '.join(row['kept_inside'])),row
        # A receipt saved again by another program (a one-row list turned into an object) names no key: clean stops, and the kept take stays.
        save_json(final/'stem_receipts.json',{'track':'u','cache_key':inner});record.register(final,[final/'stem_receipts.json'])
        assert rejects(lambda:clean(base,[final],remove=True)) and (older/'cache'/inner/'raw.wav').is_file(),'a kept key it cannot read'
        save_json(final/'stem_receipts.json',[{'track':'t','cache_key':keyed},{'track':'u','cache_key':inner}]);record.register(final,[final/'stem_receipts.json'])
        # A file held open stops its folder: what did go is counted, and the row says how much.
        opened=base/'review_open';review(song,opened);before={x:x.stat().st_size for x in opened.iterdir() if x.is_file()};real_unlink=Path.unlink
        def open_file(self,*a,**k):
            if self==opened/'notes.csv':raise PermissionError(13,'held open by another program',str(self))
            return real_unlink(self,*a,**k)
        Path.unlink=open_file
        try:got=clean(base,[final],remove=True)
        finally:Path.unlink=real_unlink
        went=sum(n for x,n in before.items() if not x.exists());row=next(x for x in got['not_removed'] if x['path']=='review_open')
        assert row['bytes_removed']==went and got['bytes']>=went and (opened/'notes.csv').is_file(),(row,went)
        row=lambda k,p:{'kind':k,'path':p,'bytes':1,'whole':True,'kept_inside':[]}
        text=describe({'folder':'piece','kept':['final'],'cache_entries_kept':0,'dry_run':True,'bytes':26,'left_alone':[],'not_removed':[],
                       'listed':[row('cache entry',f'cache/{k}') for k in range(25)]+[row('review','review_a')]})
        assert '- review: review_a' in text and text.index('- review: review_a')<text.index('- cache entry:') and '- and 6 more (--json lists every one)' in text,text
        # What a kept render plays is read whole, a cache is cleaned only if it is the kept piece's, and what stays keeps its takes.
        whose=work/'clean_whose';K=lambda c:c*20
        def entry_of(cache,key):
            (cache/key).mkdir(parents=True);save_json(cache/key/'receipt.json',{'key':key,'sha256':'c'*64,'track':'t'});(cache/key/'raw.wav').write_bytes(bytes(50))
            record.register(cache/key,[cache/key/'receipt.json',cache/key/'raw.wav'])
        def render_of(folder,title,parts):
            folder.mkdir(parents=True);save_json(folder/'render_input.json',{'project_sha256':'a'*64,'renderer_sha256':'b'*64})
            save_json(folder/'project.json',{'title':title,'tracks':[{'id':t} for t in parts]});save_json(folder/'stem_receipts.json',[{'track':t,'cache_key':k} for t,k in parts.items()])
            record.register(folder,[folder/n for n in ('render_input.json','project.json','stem_receipts.json')]);return folder
        lost=whose/'lost';kept=render_of(lost/'final','Lost',{'lead':K('1'),'bass':K('2')});all_rows=[{'track':'lead','cache_key':K('1')},{'track':'bass','cache_key':K('2')}]
        for k in '123':entry_of(lost/'cache',K(k))
        for rows in (all_rows[:1],[],[all_rows[0],{'track':'bass','cache_key':'not a key'}],None):   # a row lost, all of them, a key that is none, no file
            if rows is None:(kept/'stem_receipts.json').unlink()
            else:save_json(kept/'stem_receipts.json',rows)
            assert rejects(lambda:clean(lost,[kept],remove=True)) and all((lost/'cache'/K(k)/'raw.wav').is_file() for k in '123'),rows
        save_json(kept/'stem_receipts.json',all_rows);record.register(kept,[kept/'stem_receipts.json'])
        clean(lost,[kept],remove=True);assert not (lost/'cache'/K('3')).exists() and all((lost/'cache'/K(k)/'raw.wav').is_file() for k in '12'),'every part named: only the unused entry goes'
        # Two pieces that share a part, each with its own cache: the other piece's cache stays whole, and is named.
        two=whose/'two';a_final=render_of(two/'a'/'final','A',{'lead':K('4'),'bass':K('5')});render_of(two/'b'/'final','B',{'lead':K('4'),'bass':K('6')})
        for name,k in (('a','4'),('a','5'),('a','7'),('b','4'),('b','6'),('b','8')):entry_of(two/name/'cache',K(k))
        r=clean(two,[a_final],remove=True)
        assert all((two/'b'/'cache'/K(k)/'raw.wav').is_file() for k in '468') and not (two/'a'/'cache'/K('7')).exists(),r
        assert any(x['kind']=='cache' and x['path']=='b/cache' for x in r['left_alone']) and 'cache b/cache' in describe(r),r
        # One cache beside the renders of two pieces: what the other plays stays, what none plays goes; if a render that stays cannot say what it plays, nothing goes.
        same=whose/'same';c_final=render_of(same/'c_final','C',{'lead':K('9')});d_final=render_of(same/'d_final','D',{'lead':K('a')})
        for k in '9ab':entry_of(same/'cache',K(k))
        clean(same,[c_final],remove=True);assert (same/'cache'/K('a')/'raw.wav').is_file() and not (same/'cache'/K('b')).exists(),'what another piece plays stays'
        (d_final/'stem_receipts.json').unlink();entry_of(same/'cache',K('c'))
        r=clean(same,[c_final],remove=True);assert (same/'cache'/K('c')/'raw.wav').is_file() and any(x['path']=='cache' and 'no entry goes' in x['why'] for x in r['left_alone']),r
        # The cache beside a kept round is its own, as it is beside a kept render.
        rnd=whose/'round'/'r2';rnd.mkdir(parents=True);save_json(rnd/'round.json',{'kind':'music-production round','title':'R','project':'../song.json','status':'DRAFT_PASS','review':'review/score_review.json','render':'render/report.json','seconds':{}})
        record.register(rnd,[rnd/'round.json']);render_of(rnd/'render','R',{'lead':K('d')})
        for k in 'de':entry_of(rnd.parent/'cache',K(k))
        clean(rnd.parent,[rnd],remove=True);assert (rnd.parent/'cache'/K('d')/'raw.wav').is_file() and not (rnd.parent/'cache'/K('e')).exists(),'the cache beside a kept round'
        # A cache inside an older render of the piece (`--cache past/cache`) goes by the same rules, never with the folder: what another piece plays from it stays.
        nest=whose/'nest';n_final=render_of(nest/'final','N',{'lead':K('1')});entry_of(nest/'cache',K('1'))
        past=render_of(nest/'past','N',{'lead':K('2'),'bass':K('3')});plays=render_of(nest/'plays','P',{'lead':K('2')})
        for k in '234':entry_of(past/'cache',K(k))
        r=clean(nest,[n_final],remove=True);row=next(x for x in r['listed']+r['left_alone'] if x['path']=='past')
        assert (past/'cache'/K('2')/'raw.wav').is_file() and not (past/'cache'/K('3')).exists() and not (past/'cache'/K('4')).exists(),r
        assert f'past/cache/{K("2")}/' in (row.get('why') or ' '.join(row['kept_inside'])),row
        # Where a render that stays does not show what it plays, no entry of that cache goes, by itself or with the folder.
        (plays/'stem_receipts.json').unlink();entry_of(past/'cache',K('5'))
        r=clean(nest,[n_final],remove=True);assert all((past/'cache'/K(k)/'raw.wav').is_file() for k in '25'),r
        assert any(x['path']=='past/cache' and 'no entry goes' in x['why'] for x in r['left_alone']),r['left_alone']
        # What none plays goes, and the folder with it; a folder named by a key that cannot be read as an entry stays, and keeps its folder, though the render's record
        # lists its file; an empty one holds nothing back; and the cache of another piece's render inside a folder that goes stays whole.
        lone=whose/'lone';l_final=render_of(lone/'final','L',{'lead':K('6')});entry_of(lone/'cache',K('6'))
        whole_past=render_of(lone/'past','L',{'lead':K('7')})
        for k in '78':entry_of(whole_past/'cache',K(k))
        unread=render_of(lone/'unread','L',{});(unread/'cache'/K('9')).mkdir(parents=True);(unread/'cache'/K('9')/'raw.wav').write_bytes(bytes(50));record.register(unread,[unread/'cache'/K('9')/'raw.wav'])
        hollow=render_of(lone/'hollow','L',{});(hollow/'cache'/K('a')).mkdir(parents=True)
        host=render_of(lone/'host','L',{});guest=render_of(host/'guest','G',{'lead':K('b')})
        for k in 'bc':entry_of(guest/'cache',K(k))
        hexed=render_of(lone/'hexed','L',{});render_of(hexed/K('3'),'L',{})   # a render's folder that happens to be named like a key is a render
        r=clean(lone,[l_final],remove=True);assert not whole_past.exists() and not hollow.exists() and not hexed.exists(),r
        assert (unread/'cache'/K('9')/'raw.wav').is_file() and (unread/'render_input.json').is_file(),r
        assert all((guest/'cache'/K(k)/'raw.wav').is_file() for k in 'bc'),r
        # A track's id of another type (a record saved again by another program) stops clean with a message on a kept render, and on one that stays lets no entry go.
        typed=whose/'typed';t_final=render_of(typed/'final','T',{'lead':K('d')});t_other=render_of(typed/'other','U',{'lead':K('e')})
        for k in 'def':entry_of(typed/'cache',K(k))
        for wrong in (['lead'],{'name':'lead'}):
            for folder,title in ((t_final,'T'),(t_other,'U')):
                save_json(folder/'project.json',{'title':title,'tracks':[{'id':wrong}]})
                if folder==t_final:assert rejects(lambda:clean(typed,[t_final],remove=True)),wrong
                else:
                    r=clean(typed,[t_final],remove=True);assert any('no entry goes' in x['why'] for x in r['left_alone']),r
                assert all((typed/'cache'/K(k)/'raw.wav').is_file() for k in 'def'),wrong
                save_json(folder/'project.json',{'title':title,'tracks':[{'id':'lead'}]})
        # An audition that did not finish goes whole, the takes of its own cache with it.
        heard=whose/'heard';h_final=render_of(heard/'final','H',{'lead':K('1')});entry_of(heard/'cache',K('1'));aud3=heard/'aud';aud3.mkdir()
        save_json(aud3/'audition.json',{'kind':'music-production audition','title':'H','versions':[],'bars':[1,2],'track':'t','each_seconds':1,'status':'FAIL'})
        record.register(aud3,[aud3/'audition.json']);entry_of(aud3/'cache',K('2'))
        clean(heard,[h_final],remove=True);assert not aud3.exists(),'an audition goes whole with its own cache'
        return {'cases':37}
    found = {'clean_takes_reviews_and_lists_only_what_goes': clean_takes_reviews_and_lists_only_what_goes, 'long_paths_reach_programs_in_a_form_they_open': long_paths_for_programs, 'cache_entry_locked_across_renders': entry_lock_across_renders, 'clean_removes_only_what_the_tools_made': clean_only_what_the_tools_made, 'cache_entries_go_by_their_own_record': cache_entries_by_their_record, 'files_never_overwrite_or_write_through': files_never_overwrite_or_write_through, 'journal_proves_a_stopped_run': journal_proves_a_stopped_run, 'writers_leave_whole_files_when_a_write_fails': writers_leave_whole_files_when_a_write_fails, 'run_stops_its_program_when_stopped': run_stops_its_program_when_stopped, 'clean_and_runs_never_share_a_folder': clean_and_runs_never_share_a_folder, 'render_refuses_a_linked_output': render_refuses_a_linked_output, 'bounded_reads_of_records_and_wav_headers': bounded_reads_of_records_and_wav_headers, 'shared_reports_name_folders_relatively': shared_reports_name_folders_relatively, 'selfcheck_work_must_be_new_or_empty': selfcheck_work_must_be_new_or_empty, 'render_folders_are_read_without_links': render_folders_are_read_without_links}
    return found
