"""selfcheck.py's checks of one area (0.8 step 1.8). Game loops: the fold, the seam, cue points, layers and their renders.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import copy
import json
import numpy as np
import os
from bootstrap import has_vorbis as setup_has_vorbis
from make_example import example
from musiclib import audio
from musiclib.model import Clock, save_json, validate
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    config, rejects, work = S['config'], S['rejects'], S['work']
    def loop_parts():
        from musiclib import loop
        # A 4-frame loop [4, 8) under a 6-frame tail: the tail wraps round it once and a half.
        m=np.arange(14,dtype=np.float64)[:,None].repeat(2,1)/100;f=loop.fold(m,4,8)
        want=m[:8].copy();want[4:8]+=m[8:12];want[4:6]+=m[12:14]
        assert np.allclose(f,want),f[:,0]
        x=np.random.default_rng(3).integers(-8388608,8388607,(500,2))/8388608
        loop.write_wav(work/'loop_points.wav',x,100,500);y,info=audio.read_wav(work/'loop_points.wav')
        assert info['bits']==24 and np.array_equal(np.asarray(y,dtype=np.float64),x) and loop.read_smpl(work/'loop_points.wav')==[(0,100,499)]
        # 4 bars at 120 BPM looping from bar 2: the 5 s before the end are 3-8 s, the 1 s after the loop start 2-3 s.
        def part(tid,notes,drums=False):
            ns=[{'id':f'n{k}','on':on,'duration':d,'pitch':m} for k,(on,d,m) in enumerate(notes)]
            return {'id':tid,'name':tid,'role':'melody','engine':'soundfont','program':0,'bank':128 if drums else 0,'drums':drums,'notes':ns,
                    'performance':{'notes':{n['id']:{'velocity':80} for n in ns},'cc':[]},'mix':{'level_dbfs':-20}}
        q={'schema':'music-production/v1','title':'seam','clock':{'bars':4,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':2},
           'sections':[{'id':'a','start_bar':0,'bars':4}],'mix':{},'loop':{'start_bar':1},
           'tracks':[part('lead',[(4,1,66),(5,1,64),(8,2,60),(10,2,64),(12,4,67)]),part('pad',[(14,2,69)]),part('kit',[(13,.5,38)],True)]}
        validate(q);s=loop.seam(q,Clock(q))
        # the review of 0.9's step 5: a tempo point on the piece's last beat is the tail's alone (a passage cut on a
        # tempo change has one), and the loop still has one tempo for an engine that syncs by the beat
        ended=copy.deepcopy(q);ended['clock']['tempo']=[[0,120],[16,60]];validate(ended)
        assert loop.tempo(Clock(ended))==loop.tempo(Clock(q))=={'bpm':120.0,'bar_beats':4,'beat_count':16.0},loop.tempo(Clock(ended))
        changed=copy.deepcopy(q);changed['clock']['tempo']=[[0,120],[8,60]];assert loop.tempo(Clock(changed))['bpm'] is None
        both=copy.deepcopy(q);both['clock']['tempo']=[[0,120],[8,90],[16,60]];assert loop.tempo(Clock(both))['bpm'] is None   # a change inside the loop is a change
        # two hits struck together on keys that the part's key_map moves onto one key are one hit as played (the
        # louder): the report counted two notes sounding at the end
        mapped=copy.deepcopy(q);kit=next(t for t in mapped['tracks'] if t['id']=='kit')
        kit['notes']=[{'id':'h0','on':15,'duration':1,'pitch':42},{'id':'h1','on':15,'duration':1,'pitch':44}];kit['performance']['notes']={'h0':{'velocity':80},'h1':{'velocity':100}}
        validate(mapped);assert loop.seam(mapped,Clock(mapped))['abruptness']['sounding_at_end']=={'lead':1,'pad':1,'kit':2}
        kit['key_map']={'44':42};validate(mapped);after=loop.seam(mapped,Clock(mapped));assert after['abruptness']['sounding_at_end']=={'lead':1,'pad':1,'kit':1}
        # (the second review: only that count reads the notes after the key map; the windows either side of the loop
        # point read the notes as before: a mapped note kept the end it had before the map shortened it, and was
        # listed as sounding in the last five seconds, on the key it was moved to)
        held=copy.deepcopy(q);pad=next(t for t in held['tracks'] if t['id']=='pad');pad['notes']=[{'id':'p0','on':0,'duration':16,'pitch':60},{'id':'p1','on':2,'duration':1,'pitch':62}]
        pad['performance']['notes']={'p0':{'velocity':80},'p1':{'velocity':80}};validate(held);plain=loop.seam(held,Clock(held))
        pad['key_map']={'60':67,'62':67};validate(held);moved=loop.seam(held,Clock(held))
        assert {k:v for k,v in moved.items() if k!='abruptness'}=={k:v for k,v in plain.items() if k!='abruptness'},(moved['pitch'],plain['pitch'])
        assert 'pad' in plain['abruptness']['sounding_at_end'] and 'pad' not in moved['abruptness']['sounding_at_end'],(plain['abruptness'],moved['abruptness'])
        assert s['timbre']['continuing']==['lead'] and s['timbre']['leaving']==['kit','pad'] and s['meter']['same_tempo']
        assert s['pitch']['after']==['E','F#'] and s['pitch']['not_before']==['F#'] and s['pitch']['share_after_in_before']==.5
        assert s['abruptness']['sounding_at_end']=={'lead':1,'pad':1}
        # (the confirmation review) a kit written by its patch (bank 128) without the `drums` flag: its keys are no pitches
        bare=copy.deepcopy(q);next(t for t in bare['tracks'] if t['id']=='kit')['drums']=False;validate(bare)
        assert loop.seam(bare,Clock(bare))['pitch']==s['pitch'],loop.seam(bare,Clock(bare))['pitch']
        # 0.9 step 5 (left by the second review of playing by string): a stroke that its timing puts after the loop's
        # end has not begun there, so it is not a note sounding at the end (it was counted: its key's end is held
        # to the end's tick or later); one that begins a tick before the end and is held to it still is
        late=copy.deepcopy(q);late['tracks'].append(part('late',[(15.99,.01,72)]));late['tracks'][-1]['performance']['notes']['n0']['timing_ms']=100
        late['tracks'].append(part('edge',[(15.99,.01,74)]));validate(late)
        assert loop.seam(late,Clock(late))['abruptness']['sounding_at_end']=={'lead':1,'pad':1,'edge':1}
        for bad in ({'start_bar':4},{'start_bar':1.5},{'start':0}):rejects(lambda:validate({**q,'loop':bad}))
        return {'pitch':s['pitch'],'timbre':s['timbre']}
    def loop_markers_and_layers():
        from musiclib import loop
        x=np.random.default_rng(5).integers(-8388608,8388607,(600,2))/8388608;cues=[(0,'intro'),(240,'a'),(480,'b')]
        loop.write_wav(work/'loop_cues.wav',x,240,600,cues);y,_=audio.read_wav(work/'loop_cues.wav')
        assert np.array_equal(np.asarray(y,dtype=np.float64),x) and loop.read_smpl(work/'loop_cues.wav')==[(0,240,599)]
        assert loop.read_cues(work/'loop_cues.wav')==cues and loop.read_cues(work/'loop_points.wav')==[]
        p=example();c=Clock(p);ends=round(c.end*audio.RATE)
        marks=loop.markers(p,c,ends);assert [m[1] for m in marks]==['question','answer'] and marks[0][0]==0
        assert loop.tempo(c)['bpm'] is None,'a tempo change leaves no single BPM'
        p['clock']['tempo']=[[0,96]];t=loop.tempo(Clock(p));assert t=={'bpm':96.0,'bar_beats':4,'beat_count':16.0},t
        q=example();q['mix']['chain']='bus';ids=[t['id'] for t in q['tracks']]
        q['loop']={'start_bar':0,'layers':{'base':ids[:3],'top':ids[3:]}};validate(q)
        for layers in ({'base':ids},{'base':ids[:3],'top':ids[2:]},{'base':ids[:3],'top':ids[3:4]},{'Base':ids[:3],'top':ids[3:]}):
            rejects(lambda:validate({**q,'loop':{'start_bar':0,'layers':layers}}))
        rejects(lambda:validate({**q,'mix':{**q['mix'],'chain':'room'}}))
        # A bus that compresses or saturates its parts together, split across layers, would not let the layers add up
        # to the mix: refused, unless the mix's dynamics are wide; the fx bus, which does neither, may be split (GPT
        # Pro's seventh review of 0.4.0).
        split=copy.deepcopy(q);next(x for x in split['tracks'] if x['id']=='drums')['mix']['bus']='ensemble'
        assert rejects(lambda:validate(split));split['mix']['dynamics']='wide';validate(split)
        fxs=copy.deepcopy(q);next(x for x in fxs['tracks'] if x['id']=='piano')['mix']['bus']='fx';validate(fxs)
        return {'cues':cues,'tempo':t,'layer_cases_rejected':6}
    found = {'loop_fold_points_and_seam': loop_parts, 'loop_cue_points_tempo_and_layer_rules': loop_markers_and_layers}
    if config:
        p, cache, render = S['p'], S['cache'], S['render']
        def loop_render():
            from musiclib import loop
            q=copy.deepcopy(p);q['mix']['chain']='bus';q['loop']={'start_bar':0};save_json(work/'loop.json',q)
            r=render(work/'loop.json',work/'render_loop',config,cache);out=work/'render_loop';lp=r['loop']
            assert all(r['checks'].values()) and {'loop_length_exact','loop_points_in_wav','loop_true_peak_ceiling'}<=set(r['checks']),r['checks']
            assert 'afade=t=in' not in (out/'mix.filtergraph.txt').read_text(encoding='utf-8'),'a loop from bar 1 must not fade in'
            m,_=audio.read_wav(out/'master.wav');a,_=audio.read_wav(out/'loop.wav');end=lp['end_sample']
            tail=np.asarray(m[end:],dtype=np.float64);d=np.asarray(a,dtype=np.float64)-np.asarray(m[:end],dtype=np.float64)
            assert len(a)==end and loop.read_smpl(out/'loop.wav')==[(0,0,end-1)] and lp['gain_db']==0
            assert np.allclose(d[:len(tail)],tail,atol=2e-7) and not np.any(d[len(tail):]),'the loop is the master plus its folded tail'
            # The Ogg Vorbis copy needs FFmpeg's libvorbis encoder and is noted as skipped without it.  With
            # MUSIC_SKILL_REQUIRE_OGG set (CI sets it) it is required, so an FFmpeg without the encoder fails here.
            ogg=('ogg' in lp['files'] and r['checks']['loop_ogg_tags'] and r['checks']['loop_ogg_length_exact'])
            assert setup_has_vorbis(audio.load_config(config)['ffmpeg']['path'])==loop.has_vorbis(audio.load_config(config)),'the setup and the render ask FFmpeg alike'
            assert ogg or ('ogg_skipped' in lp and not os.environ.get('MUSIC_SKILL_REQUIRE_OGG')),lp.get('ogg_skipped',lp['files'])
            return {'loop_samples':end,'files':lp['files'],'abruptness':lp['seam']['abruptness']}
        def layer_render():
            from musiclib import loop
            q=copy.deepcopy(p);q['mix']['chain']='bus';ids=[t['id'] for t in q['tracks']]
            q['loop']={'start_bar':0,'layers':{'base':ids[:2]+ids[4:],'top':ids[2:4]}};save_json(work/'layers.json',q)
            r=render(work/'layers.json',work/'render_layers',config,cache);out=work/'render_layers';lp=r['loop'];end=lp['end_sample']
            assert all(r['checks'].values()) and {'layer_lengths_exact','layer_points_in_wav','layer_cues_in_wav'}<=set(r['checks']),r['checks']
            parts=[np.asarray(audio.read_wav(out/'layers'/f'{lid}.wav')[0],dtype=np.float64) for lid in ('base','top')]
            mix=np.asarray(audio.read_wav(out/'loop.wav')[0],dtype=np.float64);both=parts[0]+parts[1]
            corr=float(np.sum(both*mix)/np.sqrt(np.sum(both**2)*np.sum(mix**2)))
            assert all(len(x)==end for x in parts) and loop.read_cues(out/'layers'/'top.wav')==[(s['start_sample'],s['id']) for s in lp['sections']]
            assert corr>.98 and abs(lp['layers']['sum_minus_loop_db'])<3 and 0<lp['layers']['aligned_frames']<1000,(corr,lp['layers'])
            saved=json.loads((out/'loop.json').read_text(encoding='utf-8'));assert set(saved['layers'])=={'base','top'}
            # The layers get the mix's own production before the master as the mix does: with mix.mono_below_hz, two low
            # parts panned apart add up to a mono low end in the layers too (they kept the stereo lows, the side 0 dB
            # from the mid; GPT Pro's seventh review of 0.4.0).
            m=copy.deepcopy(q);m['mix'].update(dynamics='wide',mono_below_hz=250);m['loop']['layers']={'base':['bass'],'top':[x['id'] for x in m['tracks'] if x['id']!='bass']}
            low=next(x for x in m['tracks'] if x['id']=='bass');low['mix']['pan']=-1
            m['tracks'].append({**copy.deepcopy(low),'id':'bass_r','mix':{**low['mix'],'pan':1}});m['loop']['layers']['top'].append('bass_r')
            save_json(work/'layers_mono.json',m);render(work/'layers_mono.json',work/'render_layers_mono',config,cache)
            both=sum(np.asarray(audio.read_wav(work/'render_layers_mono'/'layers'/f'{lid}.wav')[0],dtype=np.float64) for lid in ('base','top'))
            spec=lambda x:np.abs(np.fft.rfft(x))[(np.fft.rfftfreq(len(x),1/audio.RATE)>30)&(np.fft.rfftfreq(len(x),1/audio.RATE)<150)]
            side_db=20*np.log10(np.linalg.norm(spec(both[:,0]-both[:,1]))/max(np.linalg.norm(spec(both[:,0]+both[:,1])),1e-12))
            assert side_db<-30,side_db
            # 0.9 step 5 (a note of the review of 0.8).  A draft taken up over a full render left that render's
            # master.flac, loop.ogg and layers beside its own master.wav, in a folder whose report says a draft leaves
            # them out: files of an earlier master that a delivery could take.  They go with the draft, which says
            # so, and a full render taken up after it makes them again.
            delivery=lambda:sorted(x.relative_to(out).as_posix() for x in out.rglob('*') if x.is_file() and (x.name in ('master.flac','loop.ogg') or x.parent.name=='layers'))
            before=delivery();assert {'master.flac','layers/base.wav','layers/top.wav'}<=set(before),before
            # The review of step 5.  (1) An analysis saved into the render's layers folder is the render's own by its
            # record (analyze registers its output there), and went with the layers: only the files the delivery
            # itself wrote go, by their names.  (2) A file that cannot be removed (read-only, on Windows) was passed
            # over in silence, and the draft said it had left out what still lay there: the draft stops before it
            # does any work, with the file's name.
            from musiclib import files as fs
            kept=out/'layers'/'levels.json';save_json(kept,{'mine':True});fs.register_output(kept)
            flac=out/'master.flac';real_unlink=Path.unlink
            def refuses(self,*a,**k):
                if self==flac:raise PermissionError(13,'read-only',str(self))
                return real_unlink(self,*a,**k)
            Path.unlink=refuses
            try:
                try:render(work/'layers.json',out,config,cache,resume=True,draft=True);raise AssertionError('a draft made beside a master.flac it could not remove')
                except ValueError as e:assert 'master.flac' in str(e) and 'could not be removed' in str(e),str(e)
            finally:Path.unlink=real_unlink
            assert flac.is_file() and (out/'layers'/'base.wav').is_file(),'stopped before anything was removed or written'
            before=[x for x in delivery() if x!='layers/levels.json'];assert before and 'layers/levels.json' in delivery()
            d=render(work/'layers.json',out,config,cache,resume=True,draft=True)
            assert d['status']=='DRAFT_PASS' and delivery()==['layers/levels.json'] and json.loads(kept.read_text(encoding='utf-8'))=={'mine':True},delivery()
            real_unlink(kept);(out/'layers').rmdir()
            assert sorted(d['earlier_delivery_removed'])==before and 'layers' not in json.loads((out/'loop.json').read_text(encoding='utf-8')),d.get('earlier_delivery_removed')
            from musiclib import summary
            assert 'Removed, as an earlier full render\'s: ' in summary.render(d,out),summary.render(d,out)
            again=render(work/'layers.json',out,config,cache,resume=True)
            assert again['status']=='TECHNICAL_PASS_AUDITION_PENDING' and delivery()==before and 'earlier_delivery_removed' not in again,delivery()
            # with nothing else in it, the layers' folder goes with them
            d2=render(work/'layers.json',out,config,cache,resume=True,draft=True);assert d2['status']=='DRAFT_PASS' and delivery()==[] and not (out/'layers').exists(),delivery()
            # the second review: the files that go are a full render's.  Over an earlier draft nothing was delivered,
            # so a file a tool wrote into layers/ under a layer's name (compare's differences, say) is none of them.
            (out/'layers').mkdir();theirs=out/'layers'/'base.wav';theirs.write_bytes(b'RIFFdifferences');fs.register_output(theirs)
            d3=render(work/'layers.json',out,config,cache,resume=True,draft=True)
            assert d3['status']=='DRAFT_PASS' and theirs.read_bytes()==b'RIFFdifferences' and 'earlier_delivery_removed' not in d3,d3.get('earlier_delivery_removed')
            real_unlink(theirs);(out/'layers').rmdir()
            return {'gain_db':lp['layers']['gain_db'],'sum_minus_loop_db':lp['layers']['sum_minus_loop_db'],'correlation_with_loop':round(corr,4),
                    'mono_low_side_db':round(float(side_db),1)}
        found.update({'loop_render_folds_the_tail_into_wav_and_ogg': loop_render, 'loop_layers_render_and_add_up_to_the_mix': layer_render})
    return found
