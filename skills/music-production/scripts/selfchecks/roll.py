"""selfcheck.py's checks of one area (0.8 step 4). The piano roll: studio.py still and studio.py video.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS)."""
import copy
import json
import os
import subprocess
import sys
import numpy as np
from make_example import example
from musiclib.model import save_json, validate
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    config, rejects, work = S['config'], S['rejects'], S['work']
    def piano_roll_draws_the_notes_as_played():
        # 0.8 step 4 (design-0.8.md, 4.3-4.7): a frame is a function of its time alone (the same twice, from two rolls,
        # so pieces of a video join without a seam); a note is its class's colour, brighter while it sounds, its part
        # named and lit in the legend; the colours keep WCAG 2.2's contrasts (text 4.5:1, bars 3:1) on every ground they
        # lie on; the legend fits however many parts there are; no frame flashes; without Pillow the command says how to
        # install it; `studio.py still` writes the picture.
        from musiclib import roll as rl
        try:
            import PIL  # noqa: F401
        except ImportError:   # Pillow is the user's to install (the public tests keep NumPy alone): the command says how
            try:rl.pillow();raise AssertionError('drew without Pillow')
            except ValueError as e:assert 'pip install pillow' in str(e),str(e)
            return {'pillow':'not installed here: the message that says how to install it checked'}
        folder=work/'roll_render';folder.mkdir()
        p=example();validate(p);save_json(folder/'project.json',p)
        r=rl.Roll(folder,640,360,30)
        a,b=r.frame(1.0),r.frame(1.0);c=rl.Roll(folder,640,360,30).frame(1.0)
        assert a.shape==(360,640,3) and np.array_equal(a,b) and np.array_equal(a,c)
        r.frame(7.3);assert np.array_equal(r.frame(1.0),c)   # and after another time: nothing a frame draws stays for the next
        from musiclib.model import Clock,performed
        clock=Clock(p);track=next(t for t in p['tracks'] if not t.get('drums') and t['engine'] not in ('noise','drum_synth'))
        notes=performed(track,clock);n=notes[1];cls=next(q['class'] for q in r.parts if q['name']==(track.get('name') or track['id']))
        # a point inside the note, a fifth of the way in (the playhead stands at its middle while it sounds)
        mid=lambda note,t:(int(round(r.y_of(note['pitch'])+r.semitone/2)),int(round(r.x_of(note['start_seconds']+.2*(note['end_seconds']-note['start_seconds']),t))))
        during=(n['start_seconds']+n['end_seconds'])/2;y,x=mid(n,during)
        assert r.playhead-x>=3,(x,r.playhead)
        assert tuple(r.frame(during)[y,x])==rl.brighter(rl.COLOUR[cls]),(tuple(r.frame(during)[y,x]),cls)   # sounding: brighter
        before=n['start_seconds']-.5;y,x=mid(n,before)
        assert tuple(r.frame(before)[y,x])==rl.COLOUR[cls]   # to come: its own colour
        # noise in the lane is drawn and lit for as long as it sounds (a kit's hits are short marks; a riser was one too)
        fx=next(t for t in p['tracks'] if t['engine']=='noise');nz=max(performed(fx,clock),key=lambda n:n['end_seconds']-n['start_seconds'])
        now,row=nz['start_seconds']+.25,(r.lane_h-8)/max(1,len(r.lane_keys));y0=r.lane_top+2+r.lane_row[nz['pitch']]*row
        y,x=int(round(y0+max(3,row-2)/2)),int(round(r.x_of(nz['start_seconds']+.2,now)))
        assert nz['end_seconds']-nz['start_seconds']>.3 and tuple(r.frame(now)[y,x])==rl.brighter(rl.COLOUR['kit']),(nz,tuple(r.frame(now)[y,x]))
        # a noise shorter than the lane's mark is drawn the mark's width, and lit only while it sounds
        tiny=copy.deepcopy(p);fx2=next(t for t in tiny['tracks'] if t['engine']=='noise');first=fx2['notes'][0]
        first['duration']=round(.02/Clock(tiny).seconds(1),6);validate(tiny);(work/'roll_tiny').mkdir();save_json(work/'roll_tiny'/'project.json',tiny)
        rt=rl.Roll(work/'roll_tiny',640,360,30);tn=next(n for n in performed(fx2,Clock(tiny)) if n['id']==first['id'])
        y0=rt.lane_top+2+rt.lane_row[tn['pitch']]*((rt.lane_h-8)/max(1,len(rt.lane_keys)));after=tn['start_seconds']+.05   # past its 20 ms
        y,x=int(round(y0+max(3,(rt.lane_h-8)/max(1,len(rt.lane_keys))-2)/2)),int(round(rt.x_of(tn['start_seconds']+.01,after)))
        assert tuple(rt.frame(after)[y,x])==rl.COLOUR['kit'],tuple(rt.frame(after)[y,x])   # drawn, its own colour: not sounding
        # every rectangle in order where a note or a section is under two pixels: a full register at 320x240, and a first
        # section of one bar in 512 at 640 pixels (Pillow refuses a rectangle whose end comes before its start)
        wide=copy.deepcopy(p);t0=next(t for t in wide['tracks'] if t['engine']=='soundfont' and not t.get('drums'));t0.pop('range',None)
        t0['notes'][0]['pitch'],t0['notes'][1]['pitch']=0,127;validate(wide);(work/'roll_wide').mkdir();save_json(work/'roll_wide'/'project.json',wide)
        rl.Roll(work/'roll_wide',320,240,30).frame(1.0)
        long=copy.deepcopy(p);long['clock']['bars']=512;long['sections']=[{'id':'a','start_bar':0,'bars':1},{'id':'b','start_bar':1,'bars':511}]
        long.pop('plan',None);validate(long);(work/'roll_long').mkdir();save_json(work/'roll_long'/'project.json',long)
        rl.Roll(work/'roll_long',640,360,30).frame(.5)
        # a title beyond Latin is drawn with the first system font found (never bundled): which one, on each system the
        # check runs on (CI's macOS and Ubuntu say theirs), or the built-in font as far as it goes where there is none
        cjk=copy.deepcopy(p);cjk['title']='賦格 第一號';(work/'roll_cjk').mkdir();save_json(work/'roll_cjk'/'project.json',cjk)
        rc=rl.Roll(work/'roll_cjk',640,360,30);rc.frame(.5);font=next((f for f in rl.SYSTEM_FONTS if os.path.isfile(f)),None)
        assert font is None or getattr(rc.font['title'],'path',None)==font,(font,getattr(rc.font['title'],'path',None))
        named=copy.deepcopy(p);named['tracks'][0]['name']=['piano']   # a part's name is text: the legend draws it
        try:validate(named);raise AssertionError('a name of a list taken')
        except ValueError as e:assert 'name is text' in str(e),str(e)
        for colour in rl.COLOUR.values():
            for ground in (rl.SURFACE,rl.PANEL,rl.BLACK_ROW):assert rl.contrast(colour,ground)>=3,(colour,ground)
            assert rl.contrast(rl.brighter(colour),rl.PANEL)>=3
        for ground,inks in rl.INKS.items():   # each text colour on each ground it is drawn on
            for ink in inks:assert rl.contrast(ink,ground)>=4.5,(ink,ground)
        # an orchestra of 48 parts with long names, in the example's four classes (four columns, each narrower than a
        # name): the legend under 30 % of the height, each row inside its column, a name cut short with an ellipsis
        big=copy.deepcopy(p)
        big['tracks']=[{**copy.deepcopy(p['tracks'][k%len(p['tracks'])]),'id':f'part_{k:02d}','name':f'Section {k} with a long descriptive name, divisi a{k % 4}'} for k in range(48)]
        twins=('Violins I, a section of twenty players seated at the front, left desk','Violins I, a section of twenty players seated at the front, right desk')
        big['tracks'][0]['name'],big['tracks'][5]['name']=twins   # one class, one text once cut: still two parts, each lit alone
        (work/'roll_big').mkdir();save_json(work/'roll_big'/'project.json',big)
        rb=rl.Roll(work/'roll_big',1280,720,30);measure=rb.ImageDraw.Draw(rb.Image.new('RGB',(8,8))).textlength
        assert len(rb.groups)==4 and rb.H-rb.legend_top<=rb.H*.3+rb.line*1.6 and rb.bottom-rb.top>rb.H*.4,(len(rb.groups),rb.legend_top,rb.bottom-rb.top)
        for rows in rb.legend_rows:
            for row in rows:
                assert sum(measure(text,font=rb.font['small'])+rb.line*.5 for text,_ in row)-rb.line*.5<=rb.col,row
        assert all(any(text.startswith('+') and text.endswith(' more') and name is None for text,name in rows[-1]) for rows in rb.legend_rows)
        assert any(text.endswith('…') for rows in rb.legend_rows for row in rows for text,_ in row)
        cut={name:text for rows in rb.legend_rows for row in rows for text,name in row if name in twins};klass=rb.parts[0]['class']
        lit=[np.asarray(rb._legend(frozenset(on))) for on in ((),((klass,twins[0]),),((klass,twins[1]),))]
        assert cut[twins[0]]==cut[twins[1]] and not any(np.array_equal(lit[i],lit[j]) for i,j in ((0,1),(0,2),(1,2))),cut
        # one name in two classes: two entries, each lit alone (a name lit both columns: the fourth review)
        same=copy.deepcopy(p);same['tracks'][0]['name']=same['tracks'][2]['name']='Violin';(work/'roll_same').mkdir();save_json(work/'roll_same'/'project.json',same)
        rs=rl.Roll(work/'roll_same',1280,720,30);both=[q['class'] for q in rs.parts if q['name']=='Violin']
        lit=[np.asarray(rs._legend(frozenset(on))) for on in ((),((both[0],'Violin'),),((both[1],'Violin'),))]
        assert len(set(both))==2 and not any(np.array_equal(lit[i],lit[j]) for i,j in ((0,1),(0,2),(1,2))),both
        # a part's key_map as the render plays it (midi.remap): a note the map puts on the key another strikes at once
        # sounds as one with it and is drawn so, the louder kept at its written pitch (two were drawn: the whole review)
        km=copy.deepcopy(p);t=next(t for t in km['tracks'] if t['engine']=='soundfont' and not t.get('drums') and 'dynamics' not in t['performance']
                                   and (t['performance'].get('legato') or {}).get('mode')!='crossfade')
        n0=t['notes'][0];up=next(k for k in range(1,24) if n0['pitch']+k not in {n['pitch'] for n in t['notes']})   # a pitch the part has nowhere else
        twin={**n0,'id':n0['id']+'_twin','pitch':n0['pitch']+up};t['notes'].append(twin);t.pop('range',None);played=t['performance']['notes'][n0['id']]
        t['performance']['notes'][twin['id']]={**played,'velocity':max(1,played['velocity']-20)};t['key_map']={str(twin['pitch']):n0['pitch']}   # at its tick, softer
        validate(km);(work/'roll_keymap').mkdir();save_json(work/'roll_keymap'/'project.json',km)
        rk=rl.Roll(work/'roll_keymap',640,360,30);drawn=next(q for q in rk.parts if q['name']==(t.get('name') or t['id']))['notes']
        assert len(drawn)==len(t['notes'])-1 and twin['pitch'] not in {pitch for _,_,pitch in drawn},(len(drawn),len(t['notes']))
        # The review of 0.8.0: a part played backwards sounds over each note's written span, and one with crossfade
        # legato as layered.plan has it (a note entered legato later, the one before held into the crossfade): drawn so,
        # at their written pitches (both were drawn from the performed notes); a name or a title holding a line break is
        # drawn on one line (it stopped Pillow's measure)
        from musiclib import layered
        from musiclib.model import TPQ
        plain=lambda t:t['engine']=='soundfont' and not t.get('drums') and 'dynamics' not in t['performance'] and not t['performance'].get('legato')
        rv=copy.deepcopy(p);tr=next(t for t in rv['tracks'] if plain(t));tr['notes']=tr['notes'][:12];tr['reverse']=True
        tr['performance']['notes']={n['id']:{**tr['performance']['notes'][n['id']],'gate':.5} for n in tr['notes']}
        validate(rv);(work/'roll_reverse').mkdir();save_json(work/'roll_reverse'/'project.json',rv);c=Clock(rv)
        drawn=next(q for q in rl.Roll(work/'roll_reverse',640,360,30).parts if q['name']==' '.join((tr.get('name') or tr['id']).split()))['notes']
        assert drawn==sorted((c.seconds(n['on']),c.seconds(n['on']+n['duration']),n['pitch']) for n in tr['notes']),drawn[:3]
        # a kit played backwards sounds each note as a swell over its written span: drawn so in the lane, and lit while it
        # swells (a reversed crash was drawn and lit as a 90 ms hit: the Astra review of the fixes for 0.8.0)
        kr=copy.deepcopy(p);kt=next(t for t in kr['tracks'] if t.get('drums') and t['engine']=='soundfont');kt['reverse']=True
        validate(kr);(work/'roll_kit_reverse').mkdir();save_json(work/'roll_kit_reverse'/'project.json',kr);ck=Clock(kr)
        q=next(q for q in rl.Roll(work/'roll_kit_reverse',640,360,30).parts if q['name']==' '.join((kt.get('name') or kt['id']).split()))
        assert q['lane'] and not q['hits'] and q['notes']==sorted((ck.seconds(n['on']),ck.seconds(n['on']+n['duration']),n['pitch']) for n in kt['notes']),q['notes'][:3]
        xf=copy.deepcopy(p);tx=next(t for t in xf['tracks'] if plain(t));tx.pop('range',None)
        tx['notes']=[{'id':f'x{k}','on':k,'duration':1,'pitch':60+2*k} for k in range(4)];tx['performance']['notes']={f'x{k}':{'velocity':80} for k in range(4)}
        tx['performance']['legato']={'mode':'crossfade'};validate(xf);(work/'roll_crossfade').mkdir();save_json(work/'roll_crossfade'/'project.json',xf);c=Clock(xf)
        drawn=next(q for q in rl.Roll(work/'roll_crossfade',640,360,30).parts if q['name']==' '.join((tx.get('name') or tx['id']).split()))['notes']
        planned=sorted((c.seconds(n['tick']/TPQ),c.seconds(n['end_tick']/TPQ),n['pitch']) for n in layered.plan(tx,c))
        assert drawn==planned and drawn!=sorted((n['start_seconds'],n['end_seconds'],n['pitch']) for n in performed(tx,c)),(drawn,planned)
        lines=copy.deepcopy(p);lines['title']='Two\nlines';lines['tracks'][0]['name']='Piano\nleft hand';validate(lines)
        (work/'roll_lines').mkdir();save_json(work/'roll_lines'/'project.json',lines);rn=rl.Roll(work/'roll_lines',640,360,30);rn.frame(1.0)
        assert rn.title=='Two lines' and any(q['name']=='Piano left hand' for q in rn.parts),(rn.title,[q['name'] for q in rn.parts])
        # no flash: the mean luminance of the frame moves less than a tenth between frames (WCAG 2.3.1's threshold)
        lum=[float(np.mean(r.frame(k/30)@np.array([.2126,.7152,.0722])))/255 for k in range(0,150)]
        assert max(abs(x-y) for x,y in zip(lum,lum[1:]))<.1,max(abs(x-y) for x,y in zip(lum,lum[1:]))
        import builtins
        real=builtins.__import__
        builtins.__import__=lambda name,*a,**k:(_ for _ in ()).throw(ImportError(name)) if name.startswith('PIL') else real(name,*a,**k)
        try:
            try:rl.pillow();raise AssertionError('drew without Pillow')
            except ValueError as e:assert 'pip install pillow' in str(e),str(e)
        finally:builtins.__import__=real
        rejects(lambda:rl.Roll(folder,641,360))
        run=lambda *a:subprocess.run([sys.executable,str(SCRIPTS/'studio.py'),*map(str,a)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        done=run('still',folder,'--at',1,'--output',work/'roll.png','--size','640x360')
        from PIL import Image
        assert done.returncode==0 and Image.open(work/'roll.png').size==(640,360),done.stderr[-300:]
        for args,words in ((('--at',99),'the piece runs 0 to'),(('--at',1,'--size','big'),'WIDTHxHEIGHT')):
            done=run('still',folder,*args,'--output',work/'roll_bad.png');assert done.returncode==2 and words in done.stderr and not (work/'roll_bad.png').exists(),done.stderr[-300:]
        return {'frame':'a function of its time','contrast':'bars 3:1, text 4.5:1','legend':'48 parts under 30 %','flash':'none',
                'title_font':os.path.basename(font) if font else 'none here: the built-in font, as far as it goes'}
    def video_fits_its_size_by_encoding_again():
        # 0.9 step 5: an encoder's two passes aim at a rate and can end a little over the size asked (a real session:
        # 10.12 MB for 10, then 9.44 for the 9.38 the message suggested, then 8.88 for 8.85: three refused encodes of
        # about a minute each).  The command lowers the rate by the overshoot it measured and encodes again itself,
        # the first pass's statistics kept; where three encodes all come out over, it says so and writes nothing.
        from musiclib import roll as rl
        calls=[]
        def over_by(share):   # an encoder that makes share times the bytes its rate asks for (10 seconds, no sound)
            def encode(vbr,again):
                calls.append((vbr,again));return int(vbr*10/8*share)
            return encode
        limit=1_000_000;vbr=int(limit*8/10)
        calls.clear();got=rl.fit_size(over_by(.98),vbr,limit);assert got==(vbr,980_000,[(vbr,980_000)]) and calls==[(vbr,False)],got
        calls.clear();rate,size,made=rl.fit_size(over_by(1.012),vbr,limit)
        assert len(made)==2 and size<=limit and rate==int(vbr*limit*.97/1_012_000) and calls==[(vbr,False),(rate,True)],(rate,size,made)
        assert .955*limit<size<=.975*limit,size     # the second lands 3 % under: the overshoot taken off, and 3 % more
        calls.clear()
        def stubborn(v,again):
            calls.append((v,again));return 1_200_000-40_000*(len(calls)-1)
        try:rl.fit_size(stubborn,vbr,limit);raise AssertionError('a video over its size put out')
        except ValueError as e:assert '1.20, 1.16 and 1.12 MB in three encodes, each over' in str(e) and 'is not written' in str(e),str(e)   # every encode's size (it said the last "in each": the review of step 5)
        assert len(calls)==3 and [a for _,a in calls]==[False,True,True] and calls[0][0]>calls[1][0]>calls[2][0],calls
        return {'second_try_bytes':size}
    found = {'piano_roll_draws_the_notes_as_played': piano_roll_draws_the_notes_as_played, 'a_video_over_its_size_is_encoded_again_lower': video_fits_its_size_by_encoding_again}
    if config:
        p, cache, render = S['p'], S['cache'], S['render']
        def piano_roll_video_carries_the_master():
            # 0.8 step 4 (design-0.8.md, 4.5): `studio.py video` makes the roll into a WebM (VP9, Opus) by default and an
            # MP4 (H.264, AAC) with --mp4, each with the render's master as its sound and as long as it, under the size
            # asked; a name of the other kind is refused.
            from musiclib import audio,roll as rl
            try:
                import PIL  # noqa: F401
            except ImportError:
                return {'pillow':'not installed here: the video is not made'}
            cfg=audio.load_config(config);have=rl.encoders(cfg['ffmpeg']['path']);out={}
            render(work/'example.json',work/'render_roll',config,cache)
            total=rl.Roll(work/'render_roll',640,360).total
            # The review of 0.8.0: the video's sound is checked as sound, decoded and set against the master (codec names
            # and a length passed a silent or an earlier master): their correlation at the best lag within 50 ms
            master=audio.read_wav(work/'render_roll'/'master.wav')[0].mean(axis=1).astype(np.float64)
            def heard(video):
                # FFmpeg itself, as the probe below: audio.ffmpeg takes only the skill's own WAVs as inputs
                wav=work/f'{video.stem}_{video.suffix[1:]}_sound.wav'
                got=subprocess.run([cfg['ffmpeg']['path'],'-hide_banner','-nostdin','-i',str(video),'-vn','-ac','2','-ar',str(audio.RATE),
                                    '-c:a','pcm_f32le','-map_metadata','-1',str(wav)],capture_output=True,text=True,errors='replace')
                assert got.returncode==0,(video.name,got.stderr[-400:])
                return audio.read_wav(wav)[0].mean(axis=1).astype(np.float64)
            def alike(a,b,span=2400):
                n=min(len(a),len(b));a,b=a[:n],b[:n];size=1<<(2*n-1).bit_length()
                c=np.fft.irfft(np.fft.rfft(a,size)*np.conj(np.fft.rfft(b,size)),size)
                return float(np.r_[c[:span+1],c[-span:]].max()/np.sqrt((a*a).sum()*(b*b).sum()))
            for name,flag,codecs in (('roll.webm',(),('libvpx-vp9','libopus')),('roll.mp4',('--mp4',),('libx264','aac'))):
                if not set(codecs)<=have:
                    out[name]='this FFmpeg lacks '+', '.join(sorted(set(codecs)-have));continue
                # named from the working folder: FFmpeg runs in a staging folder, where a relative master named nothing
                done=subprocess.run([sys.executable,str(SCRIPTS/'studio.py'),'video','render_roll','--output',name,'--config',str(Path(config).absolute()),
                                     *flag,'--size-mb','1','--fps','10','--size','640x360'],cwd=work,capture_output=True,text=True,encoding='utf-8',errors='replace')
                assert done.returncode==0 and (work/name).stat().st_size<=1_000_000,(name,done.stderr[-400:])
                probe=subprocess.run([cfg['ffmpeg']['path'],'-hide_banner','-i',str(work/name)],capture_output=True,text=True,errors='replace').stderr
                import re
                h,m,s=re.search(r'Duration: (\d+):(\d+):([\d.]+)',probe).groups();seconds=int(h)*3600+int(m)*60+float(s)
                assert abs(seconds-total)<.25 and ('vp9' if not flag else 'h264') in probe and ('opus' if not flag else 'aac') in probe,(name,seconds,total,probe[-400:])
                r=alike(heard(work/name),master);assert r>.8,(name,r)
                out[name]=f'{seconds:.2f} s, {(work/name).stat().st_size} bytes, its sound the master\'s (r {r:.2f})'
            # a draft resumed over a full render leaves the full render's FLAC beside the new master.wav: the video takes
            # the WAV, which every render writes and checks (it took the FLAC, the earlier master)
            if {'libvpx-vp9','libopus'}<=have:
                stale=work/'render_stale';stale.mkdir()
                for f in ('project.json','master.wav'):(stale/f).write_bytes((work/'render_roll'/f).read_bytes())
                tone=np.sin(2*np.pi*440*np.arange(len(master))/audio.RATE).astype(np.float32)*.3;audio.write_wav(work/'stale_tone.wav',np.stack([tone,tone],1))
                audio.ffmpeg(cfg,['-i',str(work/'stale_tone.wav'),'-c:a','flac',str(stale/'master.flac')],work/'roll_logs','stale_flac')
                rl.video(stale,work/'roll_stale.webm',config,size_mb=1,fps=10,width=640,height=360)
                sound=heard(work/'roll_stale.webm');assert alike(sound,master)>.8 and alike(sound,tone.astype(np.float64))<.3,'the video took the earlier master'
            done=subprocess.run([sys.executable,str(SCRIPTS/'studio.py'),'video',str(work/'render_roll'),'--output',str(work/'roll_wrong.mp4'),'--config',str(config)],
                                capture_output=True,text=True,encoding='utf-8',errors='replace')
            assert done.returncode==2 and 'name it .mp4 with --mp4' in done.stderr,done.stderr[-300:]
            # The size is met by the bit rates asked, not by luck: a piece this short stays far under any size it may
            # ask (0.5 MB at least), so FFmpeg's two passes are watched here (both at one video rate that, with the
            # sound's, fits the size; the master an input ahead of the output's options, which FFmpeg refused behind them).
            if {'libvpx-vp9','libopus'}<=have:
                # (and while pass 2 runs, another writer takes the output's name: the video is not put in its place)
                asked,real=[],subprocess.Popen
                def spy(argv,*a,**k):
                    if '-pass' in argv:
                        asked.append(list(argv))
                        if argv[argv.index('-pass')+1]=='2':(work/'roll_asked.webm').write_bytes(b'another writer')
                    return real(argv,*a,**k)
                subprocess.Popen=spy
                try:rl.video(work/'render_roll',work/'roll_asked.webm',config,size_mb=.5,fps=10,width=640,height=360);raise AssertionError('put over a file made meanwhile')
                except ValueError as e:assert 'made by something else' in str(e),str(e)
                finally:subprocess.Popen=real
                assert (work/'roll_asked.webm').read_bytes()==b'another writer'
                assert [a[a.index('-pass')+1] for a in asked]==['1','2'] and len({a[a.index('-b:v')+1] for a in asked})==1,asked
                video_bps,sound_bps=int(asked[1][asked[1].index('-b:v')+1]),int(asked[1][asked[1].index('-b:a')+1])
                assert (video_bps+sound_bps)*total/8<=.5e6 and asked[1].index(str(rl.master_of((work/'render_roll').absolute())))<asked[1].index('-c:v'),(video_bps,sound_bps,total)
                out['asked']=f'{video_bps // 1000} + {sound_bps // 1000} kbps for 0.5 MB'
                # FFmpeg stopping before it reads the frames (an option it refuses) is reported with its own words, and
                # nothing is written (the frames' broken pipe hid them)
                subprocess.Popen=lambda argv,*a,**k:real([argv[0],'-no_such_option','1',*argv[1:]] if '-pass' in argv else argv,*a,**k)
                try:rl.video(work/'render_roll',work/'roll_refused.webm',config,size_mb=.5,fps=10,width=640,height=360);raise AssertionError('made with an option FFmpeg refuses')
                except ValueError as e:assert 'FFmpeg stopped in pass 1' in str(e) and 'no_such_option' in str(e),str(e)
                finally:subprocess.Popen=real
                assert not (work/'roll_refused.webm').exists()
                # a size the least rates cannot meet is refused before a frame is drawn (100 s at 0.5 MB was made at
                # three times the size and reported done)
                real_roll=rl.Roll;rl.Roll=lambda *a,**k:type('Long',(),{'total':100.0})()
                try:rl.video(work/'render_roll',work/'roll_small.webm',config,size_mb=.5,fps=10,width=640,height=360);raise AssertionError('a size it cannot meet taken')
                except ValueError as e:assert 'MB at least' in str(e),str(e)
                finally:rl.Roll=real_roll
                assert not (work/'roll_small.webm').exists()
            if {'libvpx-vp9','libopus'}<=have:
                class Big:
                    def __init__(self,argv,*a,**k):
                        self.stdin=type('In',(),{'write':lambda s,b:None,'close':lambda s:None})()
                        if argv[argv.index('-pass')+1]=='2':Path(argv[-1]).write_bytes(bytes(1_500_000))
                    def wait(self):return 0
                    def kill(self):pass
                real=subprocess.Popen;subprocess.Popen=lambda argv,*a,**k:Big(argv) if '-pass' in argv else real(argv,*a,**k)
                try:rl.video(work/'render_roll',work/'roll_big.webm',config,size_mb=1,fps=10,width=640,height=360);raise AssertionError('a video over its size put out')
                except ValueError as e:assert 'over the 1 MB asked' in str(e),str(e)
                finally:subprocess.Popen=real
                assert not (work/'roll_big.webm').exists()
            real_run=subprocess.run;subprocess.run=lambda *a,**k:(_ for _ in ()).throw(subprocess.TimeoutExpired('ffmpeg',30))
            try:rl.encoders('ffmpeg');raise AssertionError('a listing that timed out passed')   # not past the command's handler as a traceback
            except ValueError as e:assert 'within 30 seconds' in str(e),str(e)
            finally:subprocess.run=real_run
            return out
        def deep_folder_video():
            # 0.9 step 1 (design-0.9.md): the video of a render in a deep folder is made.  x264 opens its first pass's
            # statistics by Windows' plain calls, and FFmpeg was started in the staging folder beside the output: past
            # the limits the encoder could not be opened (a real session of 0.8.0 wrote its video to another drive and
            # copied it back).  The staging folder and the video in it have short names of their own, and where even
            # those lie too deep the statistics go to the temporary folder.  Each expectation below is asked of the
            # command's own rules first, so the check holds wherever the work and temporary folders lie.
            from musiclib import audio,files as fs,roll as rl
            from selfchecks.render import deep_folder
            import re,tempfile
            try:
                import PIL  # noqa: F401
            except ImportError:
                return {'pillow':'not installed here: the video is not made'}
            deep=deep_folder(work)
            if deep is None:
                return {'long_paths':'off on this system: its Python opens no path of 260 characters, so nothing is made that deep'}
            cfg=audio.load_config(config);have=rl.encoders(cfg['ffmpeg']['path']);out={}
            source=deep/'r1'/'render'
            if not (source/'master.wav').is_file():   # the render check's, when it ran first
                save_json(deep/'example.json',p);render(deep/'example.json',source,config,deep/'cache')
            total=rl.Roll(source,640,360).total
            vdir=deep/('d'*40);vdir.mkdir(exist_ok=True)   # deeper still: on Windows even the short staging folder is past what a program starts in
            staging_left=lambda folder:[f.name for f in folder.iterdir() if f.name.startswith('.roll.')]
            make=lambda to:rl.video(source,to,config,mp4=mp4,size_mb=1,fps=10,width=640,height=360)
            for suffix,mp4,codecs in (('.webm',False,{'libvpx-vp9','libopus'}),('.mp4',True,{'libx264','aac'})):
                if not codecs<=have:
                    out[suffix]='this FFmpeg lacks '+', '.join(sorted(codecs-have));continue
                video=vdir/('a-piece-with-a-name-as-long-as-a-title_roll_640x360'+suffix)
                too_deep=(lambda folder:fs.past_path_limit(folder/'passlog-0.log.mbtree.temp')) if mp4 else fs.past_folder_limit   # the command's rule for this kind
                moved=too_deep(vdir/'.roll.12345678.extract')   # whether the statistics leave the staging folder (on Windows; nowhere else)
                own=Path(tempfile.mkdtemp(prefix='sc-'));before=tempfile.tempdir   # a temporary folder of the check's, to see what is left in it
                watched=not too_deep(own/'roll-12345678')
                if moved and not watched and too_deep(Path(tempfile.gettempdir())/'roll-12345678'):   # nor from the system's own: the command refuses here, rightly
                    own.rmdir();out[suffix]='the temporary folder here lies too deep for the statistics: not made';continue
                real=subprocess.Popen
                try:
                    if moved:
                        # a temporary folder as deep: the command says so and makes nothing
                        far=deep/('t'*60);far.mkdir(exist_ok=True);tempfile.tempdir=str(far)
                        try:make(video);raise AssertionError('made with its statistics past the limit')
                        except ValueError as e:assert 'set TEMP and TMP to a folder with a shorter path' in str(e),e
                        assert not video.exists() and not list(far.iterdir()) and not staging_left(vdir)
                        if not mp4 and not too_deep(deep/'.roll.12345678.extract'):
                            # a WebM whose staging folder a program can start in is made beside its output even then:
                            # FFmpeg writes VP9's statistics itself, at any length, and x264's longer names do not count
                            near=deep/('near'+suffix);make(near)
                            assert near.stat().st_size>0 and not list(far.iterdir()) and not staging_left(deep)
                    tempfile.tempdir=str(own) if watched else before
                    # stopped while FFmpeg finishes a pass (Ctrl+C in the last wait): FFmpeg is stopped and waited for
                    # before the folders go, and nothing is put out
                    seen=[]
                    class Stopped:
                        def __init__(self,argv,*a,**k):
                            self.proc=real(argv,*a,**k);self.stdin=self.proc.stdin;self.calls=[];seen.append(self)
                        def wait(self,*a,**k):
                            self.calls.append('wait')
                            if self.calls==['wait']:raise KeyboardInterrupt
                            return self.proc.wait(*a,**k)
                        def kill(self):self.calls.append('kill');self.proc.kill()
                    subprocess.Popen=lambda argv,*a,**k:Stopped(argv,*a,**k) if '-pass' in argv else real(argv,*a,**k)
                    try:make(video);raise AssertionError('made though stopped')
                    except KeyboardInterrupt:pass
                    finally:subprocess.Popen=real
                    assert seen and seen[0].calls==['wait','kill','wait'] and seen[0].proc.poll() is not None,seen and seen[0].calls
                    assert not video.exists() and not list(own.iterdir()) and not staging_left(vdir)
                    # made: the file FFmpeg writes has a short name in a staging folder with a short name, beside the output
                    asked=[]
                    subprocess.Popen=lambda argv,*a,**k:(asked.append([str(x) for x in argv]) if '-pass' in argv else None) or real(argv,*a,**k)
                    try:make(video)
                    finally:subprocess.Popen=real
                    staged=Path(asked[-1][-1])
                    assert staged.name=='roll'+suffix and re.fullmatch(r'\.roll\.[a-z0-9_]{8}\.extract',staged.parent.name) and staged.parent.parent.resolve()==vdir.resolve(),asked[-1][-1]
                finally:subprocess.Popen=real;tempfile.tempdir=before
                assert not list(own.iterdir()),[f.name for f in own.iterdir()]   # nothing of the run's is left there
                own.rmdir()
                probe=subprocess.run([cfg['ffmpeg']['path'],'-hide_banner','-i',str(video)],capture_output=True,text=True,errors='replace').stderr
                h,m,sec=re.search(r'Duration: (\d+):(\d+):([\d.]+)',probe).groups();seconds=int(h)*3600+int(m)*60+float(sec)
                assert 0<video.stat().st_size<=1_000_000 and abs(seconds-total)<.25 and 'Audio:' in probe,(suffix,seconds,total,probe[-300:])
                assert not staging_left(vdir)   # the staging folder beside the output is gone
                out[suffix]=f'{seconds:.2f} s, as long as the master'
            return out
        found.update({'piano_roll_video_carries_the_master': piano_roll_video_carries_the_master, 'a_video_in_a_deep_folder_is_made': deep_folder_video})
    return found
