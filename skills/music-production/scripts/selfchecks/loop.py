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
        assert s['timbre']['continuing']==['lead'] and s['timbre']['leaving']==['kit','pad'] and s['meter']['same_tempo']
        assert s['pitch']['after']==['E','F#'] and s['pitch']['not_before']==['F#'] and s['pitch']['share_after_in_before']==.5
        assert s['abruptness']['sounding_at_end']=={'lead':1,'pad':1}
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
            return {'gain_db':lp['layers']['gain_db'],'sum_minus_loop_db':lp['layers']['sum_minus_loop_db'],'correlation_with_loop':round(corr,4),
                    'mono_low_side_db':round(float(side_db),1)}
        found.update({'loop_render_folds_the_tail_into_wav_and_ogg': loop_render, 'loop_layers_render_and_add_up_to_the_mix': layer_render})
    return found
