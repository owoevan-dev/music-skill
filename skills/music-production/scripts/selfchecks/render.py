"""selfcheck.py's checks of one area (0.8 step 1.8). Making each part's audio: the engines (SoundFont, synth, drum machine, additive, noise, Surge XT), layered and reversed parts, the synthesis cache and its takes, memory, and whole renders.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import copy
import json
import numpy as np
import os
import shutil
import struct
import time
from make_example import example
from musiclib import audio, midi
from musiclib.model import Clock, file_hash, performed, save_json, validate
from pathlib import Path
from soundbank import yin_f0

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    config, rejects, work, xf_bank = S['config'], S['rejects'], S['work'], S['xf_bank']
    def wav_roundtrip():
        a=np.column_stack([np.linspace(-.25,.25,4096),np.linspace(.2,-.2,4096)]).astype(np.float32)
        audio.write_wav(work/'wav_roundtrip.wav',a);b,info=audio.read_wav(work/'wav_roundtrip.wav');assert np.array_equal(a,b)
        return info
    def noise_timing():
        p=example();t=p['tracks'][-1];n=t['notes'][0];t['performance']['notes'][n['id']].update(timing_ms=50,gate=.5)
        audio.noise_fx(p,t,work/'noise.wav');a,_=audio.read_wav(work/'noise.wav');actual=performed(t,Clock(p))[0]
        begin=round(actual['start_seconds']*audio.RATE);end=round(actual['end_seconds']*audio.RATE)
        assert np.max(np.abs(a[:begin]))==0 and np.max(np.abs(a[end:]))==0 and np.max(np.abs(a[begin:end]))>0
        return {'actual_start_frame':begin,'actual_end_frame':end}
    def single_voice_center():
        p=example();t=p['tracks'][2];t['instrument']={'detune_cents':[0]};audio.synthesize(p,t,work/'mono_voice.wav')
        a,_=audio.read_wav(work/'mono_voice.wav');l,r=audio.rms(a[:,0]),audio.rms(a[:,1])
        assert abs(20*np.log10(l/r))<0.01
        return {'left_minus_right_db':round(20*float(np.log10(l/r)),4)}
    def crossfade_gains():
        from musiclib import layered
        rng=np.random.default_rng(7);n=48000*2;frames=n//layered.FRAME+1
        tau=np.clip(np.arange(frames)/(frames-1),0,1);w=np.stack([np.cos(np.pi*tau/2),np.sin(np.pi*tau/2)]);pair=np.zeros(frames,dtype=int)
        def swept(y0,y1):
            s=layered.matched([y0,y1],w,pair);g=lambda k:np.interp(np.arange(n),np.arange(frames)*layered.FRAME,w[k]*s)[:,None]
            out=y0*g(0)+y1*g(1);seg=lambda a:10*np.log10(np.mean(a[int(.1*n):int(.9*n)].reshape(-1,4800,2)**2,axis=(1,2)))
            return seg(out)-10*np.log10(np.mean(y0**2))
        a=rng.standard_normal((n,2)).astype(np.float32);b=rng.standard_normal((n,2)).astype(np.float32)
        same,free,anti=swept(a,a.copy()),swept(a,b),swept(a,(.866*b-.5*a).astype(np.float32))
        # One take faded into itself (r = 1) keeps its level with no 3 dB bump; unrelated ones keep their power; so does
        # a pair half in antiphase, where plain equal-power fading would dip.
        assert np.ptp(same)<.3 and np.ptp(free)<.6 and np.ptp(anti)<.8,(np.ptp(same),np.ptp(free),np.ptp(anti))
        notes=[{'parity':0,'start_seconds':0.,'fade_in':None,'fade_out':(.5,.1)},{'parity':1,'start_seconds':.5,'fade_in':(.5,.1),'fade_out':(1.,.1)},
               {'parity':0,'start_seconds':1.,'fade_in':(1.,.1),'fade_out':None}]
        g=layered.legato_gains(notes,48000*2);i=np.arange(int(.5*48000),int(.6*48000))
        assert np.allclose(g[0][i]**2+g[1][i]**2,1,atol=1e-3) and g[0][int(.7*48000)]==0 and g[1][int(1.2*48000)]==0 and g[0][int(1.5*48000)]==1
        # A long note, then sixteenths at 160 BPM (94 ms apart) with a 100 ms crossfade: each fade ends before the next
        # note on the same render starts, so no fade is cut short and no released note comes back.
        from musiclib.model import Clock
        p=example();p['clock']={'bars':2,'meter':[4,4],'tempo':[[0,160]]};p['sections']=[{'id':'a','start_bar':0,'bars':2}]
        t=copy.deepcopy(p['tracks'][0]);t['notes']=[{'id':'n0','on':0,'duration':1,'pitch':60}]+[{'id':f'n{k}','on':1+.25*(k-1),'duration':.25,'pitch':60+k%5+1} for k in range(1,8)]
        t['performance']={'notes':{n['id']:{'velocity':80} for n in t['notes']},'legato':{'mode':'crossfade'}}
        planned=layered.plan(t,Clock(p))
        for k,a in enumerate(planned):
            nxt=[c for c in planned[k+1:] if c['parity']==a['parity']]
            if a['fade_out'] and nxt:assert a['fade_out'][0]+a['fade_out'][1]<=nxt[0]['start_seconds']+1e-9,(a,nxt[0])
        assert sum(n['legato'] for n in planned)==7
        # A long line is planned in N log N: 20,000 alternating notes in a few seconds at most (each crossfade scanned
        # every note for the next on its render, 20 s here, and hours for the 500,000 notes a project may hold).
        p['clock']={'bars':2500,'meter':[4,4],'tempo':[[0,160]]};p['sections']=[{'id':'a','start_bar':0,'bars':2500}]
        t['notes']=[{'id':f'm{k}','on':.5*k,'duration':.5,'pitch':60+2*(k%2)} for k in range(20000)]
        t['performance']['notes']={n['id']:{'velocity':80} for n in t['notes']}
        began=time.monotonic();long_line=layered.plan(t,Clock(p));took=time.monotonic()-began
        assert len(long_line)==20000 and took<5,took
        return {'level_spread_db':{'same_take':round(float(np.ptp(same)),2),'unrelated':round(float(np.ptp(free)),2),'half_antiphase':round(float(np.ptp(anti)),2)},
                'plan_20000_notes_seconds':round(took,2)}
    def take_mode():
        from musiclib import layered
        from musiclib.model import Clock
        # The bank's soft layer is a sine, its loud one eight harmonics, 9 dB apart: stepping up must brighten above the
        # fundamental and the layers' level offset must come out at -9 dB.
        prof=layered.layer_profile(xf_bank(),48,[16,17]);shape=prof['shape'][0]
        hi=shape[layered.BANDS>1000];low=shape[np.argmin(np.abs(layered.BANDS-250))]
        assert prof['pairs']==[2] and abs(prof['level_db'][0]+9)<1 and hi.max()>=6 and low<0,(prof['level_db'],shape.round(1))
        # The filter follows the band gains it is built from, and filtering keeps time: an impulse stays where it was.
        h=layered.brightness_fir(np.clip(shape,-6,6));H=np.abs(np.fft.rfft(h,1<<15));f=np.fft.rfftfreq(1<<15,1/48000)
        err=[abs(20*np.log10(H[np.argmin(np.abs(f-b))])-g) for b,g in zip(layered.BANDS,np.clip(shape,-6,6)) if 100<b<12000]
        imp=np.zeros((48000,2),dtype=np.float32);imp[1000]=1;y=layered.fir_filter(imp,h)
        assert max(err)<1 and int(np.argmax(np.abs(y[:,0])))==1000,(max(err),int(np.argmax(np.abs(y[:,0]))))
        # Each note takes the dynamic nearest the curve's mean over it.
        clock=Clock({'clock':{'bars':4,'meter':[4,4],'tempo':[[0,60]]}})
        notes=[{'start_seconds':0.,'end_seconds':2.},{'start_seconds':6.,'end_seconds':8.},{'start_seconds':2.,'end_seconds':6.}]
        layered.take_of(notes,[[0,10],[8,120]],clock,2)
        assert [n['take'] for n in notes]==[0,1,1],[n['take'] for n in notes]
        return {'level_db':[round(v,2) for v in prof['level_db']],'brightening_db':round(float(hi.max()),1),'filter_error_db':round(max(err),2)}
    def drum_round_robins():
        from musiclib import variation
        # A hit recorded at two dynamics with four takes each, interleaved on neighbouring velocities as the builder
        # lays them out (velocities 1-20 and 21-40), and a key with one take per velocity (velocity layers only).
        row=[set()]+[{('soft',(v-1)%4)} if v<=20 else {('loud',(v-21)%4)} if v<=40 else set() for v in range(1,128)]
        cells=variation.cycle_layers(row);flat=variation.cycle_layers([set()]+[{v} for v in range(1,128)])
        assert cells[5][:3]==(1,20,4) and cells[30][:3]==(21,40,4) and cells[50] is None and flat[64][2]==1,(cells[5],cells[30],flat[64])
        cycles={38:cells,40:flat}
        # A groove at one velocity per role: each hit takes one of its layer's four takes by a draw of its own, a step
        # or two away inside its layer; a velocity-layered key keeps its velocities.
        notes=[{'id':f'h{i}','tick':i*240,'pitch':38,'velocity':10 if i%2==0 else 35} for i in range(400)]+[{'id':f'k{i}','tick':i*240,'pitch':40,'velocity':64} for i in range(4)]
        out=variation.take_velocities(notes,cycles)
        takes=[next(iter(row[v]))[1] for v in out[:400]]
        assert all(abs(v-n['velocity'])<=3 and cells[v][0]==cells[n['velocity']][0] for v,n in zip(out[:400],notes)) and out[400:]==[64]*4,out[:12]
        # The take is the hit's own: the same on a second run, the same when another hit is taken away, and the draw
        # worked out here by hand from the hit's id, pitch and tick.
        import hashlib
        by_hand=[int(hashlib.sha256(f"{n['id']}:{n['pitch']}:{n['tick']}".encode()).hexdigest()[:8],16)%4 for n in notes[:400]]
        assert takes==by_hand and variation.take_velocities(notes,cycles)==out and variation.take_velocities(notes[1:],cycles)==out[1:]
        # All four takes are used about equally, and a hit has the take of the hit before it about one time in four:
        # no take is stepped to in order (0, 1, 2, 3 after one another would never repeat and would always be next).
        share=[takes.count(k)/400 for k in range(4)];again=sum(a==b for a,b in zip(takes,takes[1:]))/399;nexts=sum((a+1)%4==b for a,b in zip(takes,takes[1:]))/399
        assert all(.17<s<.33 for s in share) and .15<again<.35 and .15<nexts<.35,(share,again,nexts)
        # The draw is from the hit's id, key and tick together, as the texts say: one id on another tick or another
        # key is another draw (over many hits about three in four differ; an id alone would give none), and a hit
        # without an id draws from its key and tick.
        moved=[variation.take_of({'id':f'h{i}','pitch':38,'tick':240},4)!=variation.take_of({'id':f'h{i}','pitch':38,'tick':0},4) for i in range(400)]
        other_key=[variation.take_of({'id':f'h{i}','pitch':40,'tick':0},4)!=variation.take_of({'id':f'h{i}','pitch':38,'tick':0},4) for i in range(400)]
        assert .65<sum(moved)/400<.85 and .65<sum(other_key)/400<.85,(sum(moved),sum(other_key))
        assert variation.take_of({'pitch':38,'tick':0},4)==int(hashlib.sha256(b'None:38:0').hexdigest()[:8],16)%4
        # A layer of eight takes on velocities 1 to 16: every hit stays in the layer on the nearest velocity that holds
        # its take, found here by looking at every velocity of the layer, and at the layer's edge that is up to seven
        # steps away (one fewer than the takes), not the three of a layer with four.
        wide_row=[set()]+[{('only',(v-1)%8)} if v<=16 else set() for v in range(1,128)];wide_cells=variation.cycle_layers(wide_row)
        edge=[{'id':f'e{i}','tick':i*240,'pitch':38,'velocity':1+i%16} for i in range(800)];edge_out=variation.take_velocities(edge,{38:wide_cells})
        for n,v in zip(edge,edge_out):
            want=int(hashlib.sha256(f"{n['id']}:38:{n['tick']}".encode()).hexdigest()[:8],16)%8
            assert 1<=v<=16 and (v-1)%8==want and abs(v-n['velocity'])==min(abs(u-n['velocity']) for u in range(1,17) if (u-1)%8==want),(n,v)
        assert max(abs(v-n['velocity']) for n,v in zip(edge,edge_out))==7
        return {'take_shares':[round(s,3) for s in share],'same_as_the_hit_before':round(again,3),'largest_step':max(abs(v-n['velocity']) for v,n in zip(out,notes))}
    def surge_state():
        import re
        from musiclib import surge
        # A Surge XT state as JUCE writes it (VC2!, a size, XML holding the plugin's state in JUCE's text encoding: the
        # patch, then JUCE's own data) and a .fxp file: the file's patch replaces the state's, JUCE's data stays.
        def patch(xml):
            body=xml.encode();return b'sub3'+struct.pack('<I',len(body))+struct.pack('<6I',3,0,0,0,0,0)+body+b'\x01\x02\x03'
        old,new,tail=patch('<patch name="init"/>'),patch('<patch name="lead" category="Leads"/>'),b'\x00'*16+b'JUCEPrivateData\x07'
        inner=surge._encode(old+tail)
        xml=f'<?xml version="1.0"?> <VST3PluginState><IComponent>{inner}</IComponent></VST3PluginState>'.encode()
        state=b'VC2!'+struct.pack('<I',len(xml))+xml+b'\x00'
        fxp=b'CcnK'+struct.pack('>I',56+len(new))+b'FPCh'+bytes(44)+struct.pack('>I',len(new))+new
        out=surge.with_patch(state,fxp);size=struct.unpack('<I',out[4:8])[0]
        got=surge._decode(re.search(r'<IComponent>(.*?)</IComponent>',out[8:8+size].decode()).group(1))
        assert surge._decode(inner)==old+tail and got==new+tail and out[8+size:]==b'\x00',got[:48]
        rejects(lambda:surge.with_patch(state,b'RIFF'+fxp[4:]))
        # Surge gets no tempo here and would play synced parameters at 120 BPM: at 90 BPM a synced Delay time (log2 s)
        # grows by log2(120/90) and an LFO rate (log2 Hz) shrinks by as much, both freed; an unsynced one stays.
        import math
        synced=patch('<patch><fx5_type type="0" value="1" /><fx5_p0 type="2" value="-1.000000" temposync="1" />'
                     '<a_lfo6_rate type="2" value="0.000000" temposync="1" /><a_lfo2_rate type="2" value="2.000000" temposync="0" /></patch>')
        sfxp=b'CcnK'+bytes(4)+b'FPCh'+bytes(44)+struct.pack('>I',len(synced))+synced
        moved,names=surge.at_tempo(sfxp,90);body=moved[60:].decode('latin-1')
        value=lambda n:float(re.search(r'<%s [^>]*value="([-\d.]+)"'%n,body).group(1))
        assert names==['fx5_p0','a_lfo6_rate'] and 'temposync="1"' not in body and value('a_lfo2_rate')==2
        assert abs(value('fx5_p0')-(-1+math.log2(120/90)))<1e-5 and abs(value('a_lfo6_rate')-math.log2(90/120))<1e-5
        assert struct.unpack('>I',moved[56:60])[0]==len(moved)-60 and surge._patch_size(moved[60:])==len(moved)-60
        # The tempo a part syncs to is the written one most of its notes start under: a pickup into the faster section
        # or the final ritardando (rubato) does not set it; of equals, the earlier.
        proj={'clock':{'tempo':[[0,100],[8,140]],'rubato':{'final_ratio':.6,'final_beats':4}}};part=lambda ons:{'notes':[{'on':o} for o in ons]}
        assert [surge.part_tempo(proj,part(o)) for o in ([7.5,8,9,10],[0,1,9],[7,8],[])]==[140,100,100,100]
        return {'state_bytes':len(out),'patch_bytes':len(new),'synced_at_90_bpm':names}
    def surge_controls():
        # What the score sets on a Surge patch (surge.played_as): glide_ms makes both scenes one voice that glides only
        # between overlapping notes (Surge's play mode 4) for that time, free of the tempo; velocity_to_cutoff routes
        # velocity (source 1) to filter 1's cutoff in semitones, replacing a velocity routing it had and keeping the
        # others; a part without either sends the patch byte for byte.  Out-of-range values are refused, the fallback
        # keeps the slide, and the measured patches are offered for the 808 and the acid line only.
        from musiclib import surge
        import math
        xml=('<?xml version="1.0" encoding="UTF-8" ?><patch revision="21"><parameters>'
             '<a_polymode type="0" value="0" /><a_portamento type="2" value="-8.000000" temposync="1" porta_const_rate="0" porta_gliss="0" porta_retrigger="0" porta_curve="0" />'
             '<a_filter1_cutoff type="2" value="3.000000" />'
             '<b_polymode type="0" value="0" /><b_portamento type="2" value="-8.000000" porta_const_rate="0" porta_gliss="0" porta_retrigger="0" porta_curve="0" />'
             '<b_filter1_cutoff type="2" value="0.000000"><modrouting source="1" depth="5" muted="0" source_index="0" /><modrouting source="16" depth="12" muted="0" source_index="0" /></b_filter1_cutoff>'
             +''.join(f'<{s}_env{e}_attack type="2" value="-8.000000" temposync="1" />' for s in 'ab' for e in (1,2))+
             '</parameters></patch>').encode('latin-1')
        chunk=b'sub3'+struct.pack('<I',len(xml))+bytes(24)+xml+b'WT'
        fxp=b'CcnK'+bytes(4)+b'FPCh'+bytes(44)+struct.pack('>I',len(chunk))+chunk
        same,none=surge.played_as(fxp,{'preset':'juno_60_strings','macros':{'1':.5}})
        assert same is fxp and none=={}
        out,done=surge.played_as(fxp,{'glide_ms':80,'velocity_to_cutoff':24})
        new=out[60:];size=struct.unpack('<I',new[4:8])[0];body=new[32:32+size].decode('latin-1')
        assert done=={'glide_ms':80,'velocity_to_cutoff':24} and struct.unpack('>I',out[56:60])[0]==len(out)-60 and new[32+size:]==b'WT',done
        assert '<a_polymode type="0" value="4" />' in body and '<b_polymode type="0" value="4" />' in body,body
        porta=f'value="{math.log2(.08):.6f}" temposync="0"'
        assert porta in body and body.count('temposync="1"')==4,body  # only the untouched envelope attacks stay synced
        assert '<a_filter1_cutoff type="2" value="3.000000"><modrouting source="1" depth="24.000000" muted="0" source_index="0" /></a_filter1_cutoff>' in body,body
        b=body[body.index('<b_filter1_cutoff'):body.index('</b_filter1_cutoff>')]
        assert b.count('source="1"')==1 and 'depth="24.000000"' in b and 'source="16" depth="12"' in b,b
        rejects(lambda:surge.played_as(fxp.replace(b'a_portamento',b'a_portamentx'),{'glide_ms':80}))
        part=lambda **s:{'id':'s','surge':{'preset':'juno_60_strings',**s}}
        surge.validate(part(glide_ms=4,velocity_to_cutoff=-60));surge.validate(part(glide_ms=4000,velocity_to_cutoff=60))
        for bad in ({'glide_ms':3},{'glide_ms':4001},{'velocity_to_cutoff':61},{'slide':1}):rejects(lambda:surge.validate(part(**bad)))
        fb=surge.fallback_track({'id':'s','engine':'surge','surge':{'preset':'juno_60_strings','glide_ms':2500},'notes':[]})
        assert fb['synth']=={'preset':surge.presets()['presets']['juno_60_strings']['fallback'],'mono':True,'glide_ms':2000},fb['synth']
        b808,acid=surge.measured_counterparts('bass_808'),surge.measured_counterparts('acid_bass')
        assert len(b808)>=2 and all(s=={'glide_ms':80} for _,s in b808) and acid and not surge.measured_counterparts('supersaw_lead'),(b808,acid)
        assert all(set(s)<={'glide_ms','velocity_to_cutoff'} and surge.entry(pid) for pid,s in b808+acid)
        # swell: the attacks of both envelopes of both scenes take the notes' one length, free of the tempo; a part
        # whose notes differ in length is refused; the riser and the reverse cymbal each get the measured patch of
        # their own catalog role.
        out,done=surge.played_as(fxp,{'swell':True},2.0);new=out[60:];size=struct.unpack('<I',new[4:8])[0];body=new[32:32+size].decode('latin-1')
        assert done=={'swell_seconds':2.0} and all(f'<{s}_env{e}_attack type="2" value="1.000000" temposync="0" />' in body for s in 'ab' for e in (1,2)),body
        rejects(lambda:surge.played_as(fxp,{'swell':True}));rejects(lambda:surge.validate(part(swell=1)))
        q=example();t=q['tracks'][0];q['clock']['tempo']=[[0,120]]
        t['notes']=[{'id':'a','on':0,'duration':4,'pitch':60},{'id':'b','on':8,'duration':4,'pitch':60}]
        assert abs(surge.swell_length(q,t)-2.0)<1e-9
        t['notes'][1]['duration']=2;rejects(lambda:surge.swell_length(q,t))
        rev,rise=surge.measured_counterparts('reverse_cymbal'),surge.measured_counterparts('noise_riser')
        assert rev and all(s=={'swell':True} and surge.catalog()[pid]['role']=='percussion' for pid,s in rev) and all(surge.catalog()[pid]['role']=='fx' for pid,_ in rise),(rev,rise)
        # Past Surge's 32 s attack, the record gives what the patch got and what was asked (GPT's review of 0.5, SA03).
        assert surge.played_as(fxp,{'swell':True},40.0)[1]=={'swell_seconds':32.0,'swell_asked_seconds':40.0}
        # audition hears a patch with the settings review names for it (+glide_ms=80, ...; they were dropped: SA02), and
        # takes a SoundFont part's reverse away with its engine (SA04).
        from musiclib.audition import parse_sound,label,with_sound
        pid,settings=b808[0];sound=parse_sound('surge:'+pid+''.join('+'+k if v is True else f'+{k}={v:g}' for k,v in settings.items()))
        swapped={'id':'b','engine':'soundfont','soundfont':'x','patch':{'bank':0,'program':0},'reverse':True,'performance':{'notes':{}}}
        left=with_sound(swapped,sound)
        assert {k:swapped['surge'][k] for k in settings}==settings and left==['reverse'] and 'reverse' not in swapped and 'glide_ms' in label(sound),(swapped,left,label(sound))
        for bad in ('+glide=80','+glide_ms=x','+swell=1'):rejects(lambda:parse_sound('surge:'+pid+bad))
        # review names the notes that glide in, which velocity_to_cutoff cannot accent as Surge plays them (SA01).
        from musiclib.review import review
        a=example();t=a['tracks'][0];[t.pop(k,None) for k in ('soundfont','patch','key_map','synth')]
        t.update(engine='surge',surge={'preset':pid,'glide_ms':80,'velocity_to_cutoff':24})
        t['notes']=[{'id':'n1','on':0,'duration':1.25,'pitch':36},{'id':'n2','on':1,'duration':1,'pitch':41},{'id':'n3','on':3,'duration':1,'pitch':36}]
        t['performance']={'notes':{'n1':{'velocity':40,'gate':1},'n2':{'velocity':127,'gate':1},'n3':{'velocity':127,'gate':1}}}
        a['tracks']=[t];a.pop('harmony',None);r=review(a,work/'review_slid_accents')
        said=[x for x in r['prompts'] if 'in from a note still sounding' in x]
        assert len(said)==1 and '1 note glides in' in said[0] and '(n2)' in said[0] and 'n3' not in said[0],said
        # A note begun while a long note from before still sounds glides in too, though the note just before it has
        # ended: only that neighbour was looked at (GPT's second re-review of 0.5, R06).
        t['notes']=[{'id':'long','on':0,'duration':4,'pitch':36},{'id':'short','on':1,'duration':.5,'pitch':40},{'id':'later','on':2,'duration':1,'pitch':43}]
        t['performance']={'notes':{'long':{'velocity':40,'gate':1},'short':{'velocity':127,'gate':1},'later':{'velocity':127,'gate':1}}}
        said=[x for x in review(a,work/'review_slid_under_a_long_note')['prompts'] if 'in from a note still sounding' in x]
        assert len(said)==1 and '2 notes glide in' in said[0] and '(short, later)' in said[0],said
        return {'808':[p for p,_ in b808],'acid_with_slides':[p for p,s in acid if 'glide_ms' in s],'reverse':[p for p,_ in rev],'riser':[p for p,_ in rise]}
    def reverse_validation():
        # reverse is true on a sampled part only, not with the layered dynamics or crossfade legato that render a part
        # another way, and on at most 64 notes, each rendered on its own.
        q=example();t=q['tracks'][0];t['reverse']=True;validate(q)
        for bad in (lambda t:t.update(reverse=1),lambda t:t.update(engine='additive'),lambda t:t['performance'].update(dynamics=[[0,64]]),
                    lambda t:t['performance'].update(legato={'mode':'crossfade'}),
                    lambda t:t.update(notes=[{'id':f'r{i}','on':i*.25,'duration':.25,'pitch':60} for i in range(65)],performance={**t['performance'],'notes':{f'r{i}':{'velocity':80} for i in range(65)}})):
            r=example();u=r['tracks'][0];u['reverse']=True;bad(u);rejects(lambda:validate(r))
        return {'reverse':'soundfont parts, 64 notes at most'}
    def synth_engine():
        from musiclib import synth
        rate=synth.RATE*synth.OVER;n=rate//2
        patch=dict(synth.DEFAULT);patch['amp']={'attack':.001,'decay':.1,'sustain':1.0,'release':.1}
        def alias_db(midi,wave):
            patch['oscillators']=[{'wave':wave}]
            y=synth.resample_down(synth.voice(patch,np.full(n,float(midi)),n,n,1.0,'t',rate,np.arange(n)/rate*2),synth.OVER)[:,0]
            seg=y[2400:2400+16384]*np.hanning(16384);spec=20*np.log10(np.abs(np.fft.rfft(seg))+1e-12);f=np.fft.rfftfreq(16384,1/48000)
            f0=440*2**((midi-69)/12);harm=np.zeros_like(f,dtype=bool)
            for k in range(1,30):harm|=np.abs(f-k*f0)<40
            return float(spec[np.abs(f-f0)<40].max()-spec[(~harm)&(f>20)&(f<20000)].max())
        # A sawtooth and a square at C7 keep their aliases 60 dB under the fundamental.
        saw,sq=alias_db(96,'saw'),alias_db(96,'square');assert saw>60 and sq>60,(saw,sq)
        # The filter at full resonance, its cutoff swept over five octaves twice a second, stays finite and bounded.
        x=np.random.default_rng(1).standard_normal(48000);cut=200*2**(5*(.5+.5*np.sin(2*np.pi*2*np.arange(48000)/48000)))
        y=synth.biquad(x,'lowpass',cut,np.full(48000,.707+24),48000);assert np.isfinite(y).all() and np.abs(y).max()<200,np.abs(y).max()
        # Glide reaches its note; every preset validates and sounds; a render repeats exactly.
        g={**synth.DEFAULT,'mono':True,'glide_ms':50,'oscillators':[{'wave':'sine'}]}
        pc=np.full(rate,60.0);pc[rate//2:]=67;tau=.05/3
        seg=np.arange(rate-rate//2)/rate;pc[rate//2:]=67+(60-67)*np.exp(-seg/tau)
        assert abs(pc[-1]-67)<.01
        for name,item in synth.presets().items():
            t={'id':'s','synth':{'preset':name},'notes':[]};synth.validate(t);pat=synth.patch_of(t)
            v=synth.voice(pat,np.full(rate//4,57.0),rate//8,rate//4,.8,'n',rate,np.arange(rate//4)/rate*2);assert np.isfinite(v).all() and np.abs(v).max()>1e-4,name
        a=synth.voice(synth.patch_of({'synth':{'preset':'supersaw_lead'}}),np.full(rate//4,64.0),rate//8,rate//4,.8,'n',rate,np.arange(rate//4)/rate*2)
        b=synth.voice(synth.patch_of({'synth':{'preset':'supersaw_lead'}}),np.full(rate//4,64.0),rate//8,rate//4,.8,'n',rate,np.arange(rate//4)/rate*2)
        assert np.array_equal(a,b)
        rejects(lambda:synth.validate({'id':'s','synth':{'oscillators':[{'wave':'kazoo'}]}}))
        # The objects inside an oscillator are checked before the render, as the patch's own are: a PWM LFO's shape,
        # fields and depth, an FM index envelope's fields and bounds.  (A "sawtooth" PWM passed and stopped the render.)
        for bad in ({'wave':'pulse','pwm':{'rate_hz':1,'depth':.2,'shape':'sawtooth'}},{'wave':'pulse','pwm':{'rate':1}},
                    {'wave':'pulse','pwm':{'depth':.9}},{'wave':'pulse','pwm':'fast'},{'wave':'fm','index_env':{'sustain':2}},
                    {'wave':'fm','index_env':{'attack':.01,'hold':1}}):
            rejects(lambda bad=bad:synth.validate({'id':'s','synth':{'oscillators':[bad]}}))
        synth.validate({'id':'s','synth':{'oscillators':[{'wave':'pulse','pwm':{'rate_hz':1,'depth':.2,'shape':'saw'}}]}})
        return {'alias_db_c7':{'saw':round(saw,1),'square':round(sq,1)},'presets':len(synth.presets()),'nested_objects_checked':6}
    def drum_machine():
        from musiclib import drums
        k=drums.hit('kick',36,1,'k','808');f=np.abs(np.fft.rfft(k[:2400]*np.hanning(2400)));ff=np.fft.rfftfreq(2400,1/48000)
        early=ff[np.argmax(f)];late_seg=k[24000:26400];fl=np.fft.rfftfreq(2400,1/48000)[np.argmax(np.abs(np.fft.rfft(late_seg*np.hanning(2400))))]
        assert early>late_seg.shape[0]*0 and early>fl>30,(early,fl)
        for kind,key in (('snare',38),('clap',39),('hat_closed',42),('hat_open',46),('tom',45),('rim',37),('cowbell',56),('crash',49),('ride',51),('shaker',70)):
            h=drums.hit(kind,key,.9,kind,'909');assert np.isfinite(h).all() and np.abs(h).max()>.01,kind
        rejects(lambda:drums.validate({'id':'d','kit':{'style':'707'},'notes':[]}))
        # A gated room holds behind the snare, wide, and is cut once the gate closes.
        tail=drums.gated_tail(.9,'s',300,-4);lvl=lambda a,b:20*np.log10(np.sqrt(np.mean(tail[int(a*48000):int(b*48000)]**2))+1e-12)
        corr=float(np.corrcoef(tail[2400:12000,0],tail[2400:12000,1])[0,1])
        assert lvl(.2,.28)-lvl(.05,.13)>-6 and np.abs(tail[int(.316*48000):]).max()==0 and abs(corr)<.3,(lvl(.05,.13),lvl(.2,.28),corr)
        rejects(lambda:drums.validate({'id':'d','kit':{'gated_ms':50},'notes':[]}))
        return {'kick_pitch_hz':[round(float(early)),round(float(fl))],'gated_tail_corr':round(corr,2)}
    def drum_machine_render():
        # The part as drums.render assembles it (no check ran it before 0.8: the selfcheck's coverage): each hit at its
        # onset and nothing before it, the noise drawn from the note's id so a render repeats exactly, a closed hat
        # choking an open one, the gated tail added in stereo behind a snare, kit.tune moving the kit by semitones.
        from musiclib import drums
        def play(notes,kit,name):
            t={'id':'kit','name':'kit','role':'drums','engine':'drum_synth','drums':True,'range':[35,81],'kit':kit,
               'notes':[{'id':f'k{i}','on':on,'duration':.25,'pitch':key} for i,(on,key) in enumerate(notes)],
               'performance':{'notes':{f'k{i}':{'velocity':100} for i in range(len(notes))}},'mix':{'level_dbfs':-20,'level_mode':'peak','pan':0}}
            q={'schema':'music-production/v1','title':'Drum machine','version':'1','clock':{'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':1},
               'sections':[{'id':'a','start_bar':0,'bars':2}],'tracks':[t],'mix':{'chain':'bus','rules':2,'target_lufs':-14}}
            validate(q);receipt=drums.render(q,t,work/f'drums_{name}.wav',Clock(q))
            return np.asarray(audio.read_wav(work/f'drums_{name}.wav')[0],dtype=np.float64),receipt
        level=lambda x,a,b:10*np.log10(float(np.mean(x[int(a*audio.RATE):int(b*audio.RATE)]**2))+1e-20)
        once,receipt=play([(0,36),(1,38),(2,42)],{'style':'808'},'once');again,_=play([(0,36),(1,38),(2,42)],{'style':'808'},'again')
        assert np.array_equal(once,again) and receipt=={'hits':3,'style':'808'},receipt
        late,_=play([(1,36)],{'style':'808'},'late')
        assert not np.any(late[:int(.49*audio.RATE)]) and np.abs(late[int(.5*audio.RATE):int(.52*audio.RATE)]).max()>.05,'a hit before its onset, or none at it'
        alone,_=play([(0,46)],{'style':'808'},'open');choked,_=play([(0,46),(1,42)],{'style':'808'},'choked')  # the closed hat at 0.5 s
        before=(level(alone[:,0],0,.45),level(choked[:,0],0,.45));after=(level(alone[:,0],.65,.85),level(choked[:,0],.65,.85))
        assert abs(before[0]-before[1])<.1 and after[0]-after[1]>10,(before,after)  # measured: the same before, 17.7 dB lower after
        gated,receipt=play([(0,38)],{'style':'808','gated_ms':300,'gated_db':-6},'gated');plain,_=play([(0,38)],{'style':'808'},'plain')
        side=gated[:,0]-gated[:,1]  # the tail is decorrelated between the channels; the hit is the same in both
        assert level(side,.20,.28)>-40 and level(side,.32,.40)<-120 and not np.any(plain[:,0]-plain[:,1]) and receipt['gated_ms']==300,(level(side,.20,.28),level(side,.32,.40))
        def body(x):
            seg=x[int(.15*audio.RATE):int(.35*audio.RATE),0];seg=seg*np.hanning(len(seg))
            s=np.abs(np.fft.rfft(seg,n=1<<17));f=np.fft.rfftfreq(1<<17,1/audio.RATE);m=(f>20)&(f<400);return float(f[m][np.argmax(s[m])])
        low,_=play([(0,36)],{'style':'808'},'kick');high,_=play([(0,36)],{'style':'808','tune':12},'kick12');ratio=body(high)/body(low)
        assert 40<body(low)<56 and abs(ratio-2)<.05,(body(low),ratio)  # measured: 48.3 Hz, and 2.008 an octave up
        return {'choke_drop_db':round(after[0]-after[1],1),'kick_body_hz':round(body(low),1),'octave_up_ratio':round(ratio,3)}
    def chip_sounds():
        from musiclib import synth
        rate=synth.RATE*synth.OVER
        # A chord of three notes, the top one shorter, arpeggiated at 50 Hz: the voice steps up through the held notes
        # once per step and drops the top note when it ends; "updown" turns back without repeating the ends.
        chord=[{'pitch':60,'start_seconds':0.,'end_seconds':1.},{'pitch':64,'start_seconds':0.,'end_seconds':1.},{'pitch':67,'start_seconds':0.,'end_seconds':.5}]
        up=synth.arpeggio_curve(chord,{'rate_hz':50},0.,48000,48000,None,None)[::960]
        assert up[:6].tolist()==[60,64,67,60,64,67] and set(up[26:50].tolist())=={60,64},up[:30]
        ud=synth.arpeggio_curve(chord,{'rate_hz':50,'order':'updown'},0.,48000,48000,None,None)[::960]
        assert ud[:8].tolist()==[60,64,67,64,60,64,67,64],ud[:8]
        # The NES-style triangle holds 16 levels, and at C7 its aliases stay far below its harmonics.
        f=440*2**((96-69)/12);n=rate;dt=np.full(n,f/rate);y=synth.resample_down(synth.stepped_triangle(np.cumsum(dt),dt,16),synth.OVER)
        Y=np.abs(np.fft.rfft(y*np.hanning(len(y))));fr=np.fft.rfftfreq(len(y),1/synth.RATE)
        harm=np.zeros(len(Y),bool)
        for k in range(1,12):harm|=np.abs(fr-k*f)<15
        alias=20*np.log10(Y[harm].max()/Y[~harm&(fr>50)].max())
        low=np.full(rate//10,55./rate);z=synth.stepped_triangle(np.cumsum(low),low,16);flat=np.unique(np.round(z[1:][np.diff(z)==0],6))
        assert alias>80 and len(flat)==16,(alias,len(flat))
        # Clocked noise gets brighter with the note.
        cents=[]
        for pitch in (48,72,96):
            fq=440*2**((pitch-69)/12);ph=np.cumsum(np.full(rate//4,fq/rate))
            x=synth.resample_down(synth.clocked_noise(ph*16,np.random.default_rng(1)),synth.OVER)
            S=np.abs(np.fft.rfft(x))**2;fr=np.fft.rfftfreq(len(x),1/synth.RATE);cents.append(float((S*fr).sum()/S.sum()))
        assert cents[0]<cents[1]<cents[2],cents
        return {'triangle_alias_db':round(float(alias),1),'noise_centroid_hz':[round(c) for c in cents]}
    def pitch_envelope():
        from musiclib import synth
        q={'clock':{'bars':1,'meter':[4,4],'tempo':[[0,120]]}}
        t={'id':'b808','synth':{'preset':'bass_808'},'notes':[{'id':'a','pitch':36,'on':0,'duration':2}],'performance':{'notes':{'a':{'velocity':110}}}}
        synth.validate(t);synth.render(q,t,work/'b808.wav',Clock(q));x=audio.read_wav(work/'b808.wav')[0][:,0].astype(float)
        def hz(a,b):
            seg=x[int(a*48000):int(b*48000)];z=np.flatnonzero((seg[:-1]<0)&(seg[1:]>=0));return 48000/np.median(np.diff(z))
        # The 808 bass starts an octave up and falls to C2 within a tenth of a second.
        early,late=hz(0,.03),hz(.15,.5)
        assert early>late*1.15 and abs(1200*np.log2(late/65.41))<10,(early,late)
        bad=copy.deepcopy(t);bad['synth']['pitch_env']={'semitones':60};rejects(lambda:synth.validate(bad))
        return {'start_hz':round(float(early),1),'settled_hz':round(float(late),2)}
    def cache_identity():
        from musiclib.render import synthesis_identity
        from musiclib.model import digest
        p=example();p['clock']['rubato']={'phrase_beats':2,'phrase_ratio':.8};p['clock']['bars']=8
        p['sections']=[{'id':'a','start_bar':0,'bars':4},{'id':'b','start_bar':4,'bars':4}]
        q=copy.deepcopy(p);q['sections']=[{'id':'a','start_bar':0,'bars':2},{'id':'b','start_bar':2,'bars':6}]
        r=copy.deepcopy(p);r['tracks'][0]['mix']['level_dbfs']-=3
        key=lambda x:digest(synthesis_identity(x,Clock(x),x['tracks'][0],{},'code'))
        assert key(p)!=key(q) and key(p)==key(r)
        # A Surge part's key also holds the host program that plays it.
        from musiclib import surge
        st=copy.deepcopy(p['tracks'][0]);st.update(engine='surge',surge={'preset':'juno_60_strings'})
        assert surge.dependencies({},st)['host']==file_hash(SCRIPTS/'surge_host.py')
        return {'sections_moved':'new key','mix_changed':'same key'}
    def mono_lines():
        from musiclib import synth
        notes=[{'start_seconds':k*.5,'end_seconds':k*.5+.5,'pitch':40} for k in range(100)]
        lines=synth.voices(notes,{'mono':True})
        assert len(lines)==2 and lines[1][0]['start_seconds']==synth.MONO_LINE_S,[len(x) for x in lines]
        return {'unbroken_legato_seconds':synth.MONO_LINE_S}
    def fluidsynth_log():
        from musiclib import audio as au
        real=au.run
        try:
            # The output inside the work folder: given as 'out.wav', the mocked run published an empty file into the
            # folder the selfcheck was started from.
            au.run=lambda *a,**k:"Rendering audio to file 'work/terror-game/failed takes/raw.wav'..\n"
            au.fluidsynth({'fluidsynth':{'path':'x'}},'f.sf2','in.mid',work/'fluidsynth_log_out.wav',work)
            au.run=lambda *a,**k:'fluidsynth: warning: Instrument not found on channel 0 [bank=0 prog=5], substituted [bank=0 prog=0]\n'
            rejects(lambda:au.fluidsynth({'fluidsynth':{'path':'x'}},'f.sf2','in.mid',work/'fluidsynth_log_rejected.wav',work))
            assert not (work/'fluidsynth_log_rejected.wav').exists()
        finally:au.run=real
        return {'paths_with_error_words':'accepted'}
    def slur_legato_plays_one_line():
        # A slur glides the part's pitch wheel, which bends every note the part holds: notes that overlap as written (a
        # chord, a held note under a run) are refused before the render, which would bend them together; crossfade
        # legato plays them as written.  (Found by the second review of 0.4.0.)
        p=example();q=copy.deepcopy(p);q['clock']={'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':1}
        q['sections']=[{'id':'line','start_bar':0,'bars':2,'intent':'One line'}]
        t=copy.deepcopy(p['tracks'][0]);t.update(id='flute',program=73,bank=0,role='melody',range=[60,90])
        t['notes']=[{'id':f'flute_n{k}','on':on,'duration':1,'pitch':m} for k,(on,m) in enumerate([(0,72),(1,74),(2,76),(3,79)])]
        t['performance']={'notes':{f'flute_n{k}':{'velocity':96,'gate':1.0} for k in range(4)},'bend_range':12,'legato':{'max_interval':5}}
        q['tracks']=[t];validate(q)
        t['notes'][1]['on']=.5  # the second note now starts under the first: two voices
        try:
            validate(q);raise AssertionError('two written voices passed as one slurred line')
        except ValueError as e:assert 'one line' in str(e) and 'flute_n0' in str(e) and 'flute_n1' in str(e),e
        t['performance']['legato']['mode']='crossfade';validate(q)
        return {'overlap_refused':True,'crossfade_accepted':True}
    def synth_modulation_in_beats_follows_the_tempo():
        # An LFO or an arpeggio timed in beats follows the beats the voice plays: when the tempo doubles under a held
        # note, its cycle halves in seconds.  A rate in both Hz and beats is refused, a PWM's too.  (Found by the second
        # review of 0.4.0: a beat-based rate kept the tempo its note started at, and two rate fields passed the check.)
        from musiclib import synth
        q={'clock':{'bars':2,'meter':[4,4],'tempo':[[0,60],[2,120]]}};c=Clock(q);rate=48000;n=3*rate
        beats=audio.beats_at(c,np.arange(n)/rate)-c.beat(0.)
        saw=synth.lfo(n,{'rate_beats':1,'shape':'saw'},rate,beats);wraps=(np.flatnonzero(np.diff(saw)<-1)+1)/rate
        assert np.allclose(wraps,[1.,2.,2.5],atol=1e-3),wraps
        chord=[{'pitch':m,'start_seconds':0.,'end_seconds':3.} for m in (60,64,67)]
        steps=(np.flatnonzero(np.diff(synth.arpeggio_curve(chord,{'rate_beats':.5},0.,n,rate,beats,c)))+1)/rate
        assert np.allclose(steps[:7],[.5,1.,1.5,2.,2.25,2.5,2.75],atol=1e-3),steps[:7]
        # synth.render gives a held note's LFO the beats it plays through, the tempo change included.
        seen=[];real=synth.lfo
        def spy(m,spec,r,b=None):
            if spec and spec.get('rate_beats'):seen.append((r,b))
            return real(m,spec,r,b)
        t={'id':'pad','synth':{'oscillators':[{'wave':'sine'}],'lfo':{'rate_beats':1,'to_amp':.3}},'notes':[{'id':'a','pitch':60,'on':0,'duration':3}],
           'performance':{'notes':{'a':{'velocity':100}}}}
        synth.validate(t);synth.lfo=spy
        try:synth.render(q,t,work/'lfo_tempo.wav',c)
        finally:synth.lfo=real
        r,b=seen[0];assert abs(b[int(2.5*r)]-3.)<1e-3,b[int(2.5*r)]
        for bad in ({'lfo':{'rate_hz':2,'rate_beats':1,'to_amp':.3}},{'oscillators':[{'wave':'pulse','pwm':{'rate_hz':1,'rate_beats':1,'depth':.2}}]},
                    {'arpeggio':{'rate_hz':30,'rate_beats':.25}}):
            rejects(lambda bad=bad:synth.validate({'id':'s','synth':{'oscillators':[{'wave':'saw'}],**bad}}))
        return {'lfo_wraps_s':wraps.round(3).tolist(),'arpeggio_steps_s':steps[:7].round(3).tolist(),'both_rates_refused':3}
    def parts_wait_for_memory():
        # Parts made at once share the memory free at the start (MemoryBudget): one that needs more than is left waits
        # for the others, one needing all of it runs alone, and a part's estimate grows with the song and its tools.
        import threading
        from musiclib.render import MemoryBudget,part_memory
        budget=MemoryBudget(1000/.8);order=[];started=threading.Event()
        def big():
            with budget.hold(800):started.set();time.sleep(.3);order.append('big')
        def small():
            started.wait()
            with budget.hold(400):order.append('small')
        a,b=threading.Thread(target=big),threading.Thread(target=small);a.start();b.start();a.join();b.join()
        assert order==['big','small'],order
        alone=MemoryBudget(100/.8)
        with alone.hold(10**9):pass  # more than all of it: runs, alone
        with MemoryBudget(None).hold(10**12):pass
        p=example();c=Clock(p);frames=round((c.end+c.tail)*audio.RATE);t=copy.deepcopy(p['tracks'][2])
        plain=part_memory(t,c,frames,None);t['mix']['filter_sweep']={'points':[[0,200],[8,4000]]}
        swept=part_memory(t,c,frames,None);assert swept>plain and part_memory(t,c,2*frames,None)>swept
        # In whole bytes: four estimates with fractions, let go in the order they were taken, leave the budget empty,
        # so a part that needs all of it starts at once (summed as floats they left 3e-8 bytes held, and it waited for
        # ever).  (Found by a review of 0.4.0.)
        whole=MemoryBudget(2e9);held=[whole.hold(x) for x in (1e9/3,1e9/7,1e9/11,1e9/13)]
        for h in held:h.__enter__()
        for h in held:h.__exit__(None,None,None)
        done=threading.Event()
        def everything():
            with whole.hold(1.75e9):done.set()
        w=threading.Thread(target=everything,daemon=True);w.start();w.join(10)
        assert whole.used==0 and done.is_set(),whole.used
        return {'waited':True,'empty_after_all_let_go':True}
    def a_part_larger_than_the_machine_is_refused():
        # A part that would need more memory at once than the machine has (render.part_memory) is refused before
        # anything is synthesized, and the error says why: a synth pad note held through a long song is the usual cause.
        from musiclib.render import too_large
        p=example();p['clock']={'bars':400,'meter':[4,4],'tempo':[[0,100]],'tail_seconds':2};p['sections']=[{'id':'a','start_bar':0,'bars':400}]
        p.pop('harmony',None);t=copy.deepcopy(p['tracks'][2]);t.update(id='pad',engine='synth',synth={'preset':'trance_pad'})
        t['notes']=[{'id':'held','on':0,'duration':1600,'pitch':57}];t['performance']={'notes':{'held':{'velocity':70}}};p['tracks']=[t];validate(p)
        c=Clock(p);frames=round((c.end+c.tail)*audio.RATE)
        try:too_large(p,c,frames,{},8e9);raise AssertionError('a 16-minute synth note passed on an 8 GB machine')
        except ValueError as e:assert 'split the note' in str(e) and 'pad' in str(e),e
        too_large(p,c,frames,{},None);too_large(p,c,frames,{},1e12)
        # A Surge part plays in Surge's own process where Surge XT is there; only its fallback on the built-in synth
        # makes the note whole.
        s=copy.deepcopy(t);s.update(engine='surge',surge={'preset':'juno_60_strings'});s.pop('synth',None);q=copy.deepcopy(p);q['tracks']=[s]
        too_large(q,c,frames,{},8e9,{'pad':{'plays':'Surge XT'}})
        rejects(lambda:too_large(q,c,frames,{},8e9,{'pad':{'plays':'fallback: Surge XT is not installed'}}))
        return {'refused_on_8_gb':True}
    found = {'float_wav_roundtrip': wav_roundtrip, 'noise_engine_obeys_performance_timing_and_gate': noise_timing, 'additive_single_voice_is_centred': single_voice_center, 'dynamics_crossfade_keeps_power_and_legato_fades_cross': crossfade_gains, 'take_mode_learns_brightness_from_the_layers': take_mode, 'drum_hits_take_their_recorded_takes_by_their_own_draw': drum_round_robins, 'surge_patch_goes_into_the_plugin_state': surge_state, 'surge_patch_takes_the_slide_and_accent_the_score_sets': surge_controls, 'reverse_is_a_sampled_part_rendered_note_by_note': reverse_validation, 'synth_is_band_limited_stable_and_repeatable': synth_engine, 'drum_machine_voices_kick_pitch_drop_and_gated_snare': drum_machine, 'drum_machine_render_places_chokes_and_tunes_the_kit': drum_machine_render, 'chip_arpeggio_stepped_triangle_and_clocked_noise': chip_sounds, 'synth_pitch_envelope_punches_and_settles': pitch_envelope, 'synthesis_cache_follows_the_played_tempo': cache_identity, 'a_long_mono_line_starts_afresh_after_thirty_seconds': mono_lines, 'fluidsynth_diagnostics_ignore_its_paths': fluidsynth_log, 'slur_legato_plays_one_line': slur_legato_plays_one_line, 'synth_modulation_in_beats_follows_the_tempo': synth_modulation_in_beats_follows_the_tempo, 'parts_wait_for_memory': parts_wait_for_memory, 'a_part_larger_than_the_machine_is_refused': a_part_larger_than_the_machine_is_refused}
    if config:
        p, cache, render = S['p'], S['cache'], S['render']
        def cache_takes_checked():
            # 0.8 step 1.4 (design-0.8.md, Part C; CWE-345): before a cached raw take or a kept stem is hashed or decoded,
            # its header and length are read from the file: float32 stereo at 48 kHz, whole frames, its data inside the
            # file; exactly the render's frames F from the built-in engines (lead: additive, fx: noise) and for every
            # stem; FluidSynth's takes (piano, bass) up to the ceiling.  0.7 used whatever matched its receipt.  Each
            # take here is replaced and its receipt matched to it, so only that check can tell; a refused one is made
            # again (the reason in that render's receipt alone), the master is the same, and the next render hits.
            from musiclib import audio as au
            C=work/'cache_checked';F=round((Clock(p).end+Clock(p).tail)*au.RATE)
            rec=lambda name:{x['track']:x for x in json.loads((work/name/'stem_receipts.json').read_text(encoding='utf-8'))}
            base=render(work/'example.json',work/'take_base',config,C);keys={k:v['cache_key'] for k,v in rec('take_base').items()}
            def put(path,x,pcm16=False,how=None):   # how: float32 stereo with one header fault read_wav refuses
                if not pcm16 and how is None:au.write_wav(path,x);return
                data=(np.clip(x,-1,1)*32767).astype('<i2').tobytes() if pcm16 else np.asarray(x,'<f4').tobytes();tail=b''
                fmt=struct.pack('<HHIIHH',1,2,au.RATE,au.RATE*4,4,16) if pcm16 else struct.pack('<HHIIHH',3,2,au.RATE,au.RATE*8,0 if how=='align0' else 8,32)
                if how=='ext26':fmt=struct.pack('<HHIIHHHHIH',65534,2,au.RATE,au.RATE*8,8,32,8,32,3,3)   # float32 named at 24, 14 bytes short
                if how in ('ext40','guid0'):   # whole, its sub-format KSDATAFORMAT's float GUID: fit; with the GUID's last 14 bytes 0, not
                    fmt=struct.pack('<HHIIHHHHI',65534,2,au.RATE,au.RATE*8,8,32,22,32,3)+struct.pack('<H',3)+(bytes.fromhex('000000001000800000aa00389b71') if how=='ext40' else bytes(14))
                if how=='fmt1026':fmt+=bytes(1010)
                if how=='trailing':tail=b'\0'
                body=b'WAVEfmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(data))+data+tail
                path.write_bytes(b'RIFF'+struct.pack('<I',len(body))+body)
            def retake(part,x,pcm16=False,how=None):   # the raw take replaced and its receipt matched to it
                e=C/keys[part];put(e/'raw.wav',x,pcm16,how);r=json.loads((e/'receipt.json').read_text(encoding='utf-8'));r['sha256']=au.audio_hash(e/'raw.wav');save_json(e/'receipt.json',r)
            def restem(part,x,how=None):               # the kept stem replaced and its record matched to it
                e=C/keys[part];put(e/'stem.wav',x,how=how);s=json.loads((e/'stem.json').read_text(encoding='utf-8'));s['sha256']=file_hash(e/'stem.wav');save_json(e/'stem.json',s)
            take=lambda part,name='raw.wav':np.array(au.read_wav(C/keys[part]/name)[0])
            lead,fx,piano=take('lead'),take('fx'),take('piano');assert len(lead)==len(fx)==F   # FluidSynth's ends where its notes do
            def rendered(name,refused,restemmed=()):   # refused: {part: (which, words)}; restemmed: a hit whose stem is made
                out=render(work/'example.json',work/name,config,C);r=rec(name)   # again (its take changed); others reused
                assert out['master']['sha256']==base['master']['sha256'],name
                for part,x in r.items():
                    if part in refused:
                        which,words=refused[part]
                        assert words in x.get('cache_rejected',{}).get(which,''),(name,part,x.get('cache_rejected'))
                        assert (x['cache_hit'] and not x['stem_reused']) if which=='stem' else not x['cache_hit'],(name,part,x)
                    else:assert x['cache_hit'] and x['stem_reused']!=(part in restemmed) and 'cache_rejected' not in x,(name,part,x)
            retake('lead',lead,pcm16=True);retake('fx',fx[:-1]);restem('bass',take('bass','stem.wav')[:-1])
            rendered('take_one',{'lead':('raw','format 1, 16 bits'),'fx':('raw',f'{F-1} frames'),'bass':('stem',f'{F-1} frames')})
            rendered('take_one_again',{})
            retake('lead',np.vstack([lead,np.zeros((1,2),np.float32)]))
            au.write_wav(C/keys['fx']/'raw.wav',fx);b=bytearray((C/keys['fx']/'raw.wav').read_bytes());i=b.find(b'data')+4
            b[i:i+4]=struct.pack('<I',struct.unpack_from('<I',b,i)[0]+8);(C/keys['fx']/'raw.wav').write_bytes(bytes(b))   # 8 bytes more than it holds
            rendered('take_two',{'lead':('raw',f'{F+1} frames'),'fx':('raw','more than the file holds')})
            rendered('take_two_again',{})
            # headers the hash reads and read_wav refuses, each with its receipt matched (the first check let them by)
            retake('lead',lead,how='align0');retake('fx',fx,how='ext26');retake('piano',piano,how='trailing');retake('bass',take('bass'),how='fmt1026')
            restem('drums',take('drums','stem.wav'),how='align0')
            rendered('take_headers',{'lead':('raw','Unsupported WAV dimensions'),'fx':('raw','Short extensible WAV'),'piano':('raw','Truncated WAV chunk'),
                                     'bass':('raw','Invalid WAV format chunk'),'drums':('stem','Unsupported WAV dimensions')})
            rendered('take_headers_again',{})
            # float32 named by a whole extensible format is what read_wav reads: a take and a stem so written stay hits
            # (one refusing every extensible take passed the cases above); one whose GUID is not KSDATAFORMAT's, which
            # FFmpeg does not read, is made again (it passed the check and stopped the render in FFmpeg)
            retake('lead',lead,how='ext40');restem('bass',take('bass','stem.wav'),how='ext40');retake('fx',fx,how='guid0')
            rendered('take_extensible',{'fx':('raw','unknown sub-format')},('lead',))
            longest=max([len(take(part)) for part in ('piano','bass','drums')]+[F])
            limit=au.MAX_WAV_SECONDS;au.MAX_WAV_SECONDS=(longest+100)/au.RATE   # the ceiling lowered to just past the longest take
            try:
                ceiling=round(au.MAX_WAV_SECONDS*au.RATE)
                retake('piano',np.vstack([piano,np.zeros((ceiling-len(piano),2),np.float32)]));rendered('take_ceiling',{},('piano',))   # at it: taken
                retake('piano',np.vstack([piano,np.zeros((ceiling+1-len(piano),2),np.float32)]))
                rendered('take_past',{'piano':('raw','longer than a render can be')})
            finally:au.MAX_WAV_SECONDS=limit
            rendered('take_past_again',{})
            return {'F':F,'refused':['PCM16','F-1','F+1','a data chunk past the end','a frame of 0 bytes','a short extensible format','a byte after the data',
                                     'a format chunk of 1,026 bytes','an extensible format of another GUID','one frame past the ceiling','a stem F-1','a stem with a frame of 0 bytes'],
                    'taken':['F','the ceiling','a whole extensible format']}
        def integration():
            # Part by part, again from the cache, and afresh with the parts in parallel: one master.
            first=render(work/'example.json',work/'render_first',config,cache,jobs=1)
            repeat=render(work/'example.json',work/'render_repeat',config,cache)
            parallel=render(work/'example.json',work/'render_parallel',config,work/'cache_parallel',jobs=4)
            assert first['master']['sha256']==repeat['master']['sha256']==parallel['master']['sha256']
            assert repeat['cache_hits']==len(p['tracks']) and parallel['cache_hits']==0 and parallel['jobs']>1
            # Fresh syntheses of the same parts hash alike: the raw hash covers the audio, not the writer's timestamp.
            raws=lambda name:[x['raw_sha256'] for x in json.loads((work/name/'stem_receipts.json').read_text(encoding='utf-8'))]
            assert raws('render_first')==raws('render_parallel')
            # The repeat plays every part's processed stem from the cache (a frozen track), the same file to the bit.
            stems=lambda name:[x['stem_sha256'] for x in json.loads((work/name/'stem_receipts.json').read_text(encoding='utf-8'))]
            assert first['stems_reused']==parallel['stems_reused']==0 and repeat['stems_reused']==len(p['tracks'])
            assert stems('render_first')==stems('render_repeat')==stems('render_parallel')
            # Where the drive cannot lock a cache entry, each part is made in the render's own folder and the shared
            # cache's files are neither read nor written (trying for the lock makes the entry's folder and entry.lock,
            # nothing else): unlocked, a render had dropped the journal another wrote there (GPT's review of 0.5, C04).
            # The master is the same.
            from musiclib import files as fs
            real_lock=fs.lock;fs.lock=lambda fd,wait:None
            try:unlocked=render(work/'example.json',work/'render_unlocked',config,work/'cache_unlocked')
            finally:fs.lock=real_lock
            shared=[x for x in fs.tree(work/'cache_unlocked') if x.name!='entry.lock']
            receipts=json.loads((work/'render_unlocked'/'stem_receipts.json').read_text(encoding='utf-8'))
            assert unlocked['master']['sha256']==first['master']['sha256'] and not shared and all(x.get('unlocked_cache') for x in receipts),(shared[:3],receipts[0])
            assert all((work/'render_unlocked'/'unlocked_cache'/x['cache_key']/'raw.wav').is_file() for x in receipts)
            assert not [x for x in fs.tree(work/'render_unlocked') if x.name==fs.JOURNAL],'every journal dropped once recorded'
            assert all(fs.unchanged(x,fs.recorded(work/'render_unlocked').get(fs.relative(work/'render_unlocked',x),(-1,-1)))
                       for x in fs.tree(work/'render_unlocked') if x.name!=fs.RECORD and not fs.is_lock_file(x))
            # Those parts look like cache entries (a key's folder, raw.wav, a receipt naming the key), and clean takes
            # none of them for one, though a kept render uses one of their keys: it listed the others to remove (GPT's
            # second re-review of 0.5, R01; a dry run here, the cases that remove are with clean's).
            from musiclib.clean import clean,entry_record
            assert len(receipts)>1 and all(entry_record(work/'render_unlocked'/'unlocked_cache'/x['cache_key']) for x in receipts)
            kept=work/'kept_one_part';kept.mkdir();save_json(kept/'render_input.json',{'project_sha256':'a'*64,'renderer_sha256':'b'*64})
            save_json(kept/'project.json',{'title':'Kept one part','tracks':[]});save_json(kept/'stem_receipts.json',[{'track':'t','cache_key':receipts[0]['cache_key']}])
            looked=clean(work,[kept])
            assert not [x for x in looked['listed']+looked['not_removed'] if 'unlocked_cache' in Path(x['path']).parts],looked['listed']
            # The same where an entry's folder cannot be made for want of permission (a cache this user may not write,
            # a read-only drive): that failure had stopped the render (GPT's re-review of 0.5, RR03).  Nothing is made
            # in the cache.  Any other failure to make the folder is raised as it was: a file where the entry should
            # be, a full drive.
            import errno
            from musiclib.render import entry_lock
            real_mkdir=Path.mkdir;denied_root=(work/'cache_denied').resolve();refusal=[PermissionError(errno.EACCES,'Permission denied')]
            def refused(self,*a,**k):
                if self.resolve().parent==denied_root:raise refusal[0]
                return real_mkdir(self,*a,**k)
            Path.mkdir=refused
            try:
                private=render(work/'example.json',work/'render_denied',config,work/'cache_denied')
                refusal[0]=OSError(errno.EROFS,'Read-only file system')
                with entry_lock(work/'cache_denied'/'read_only') as held:assert held is False
                refusal[0]=OSError(errno.ENOSPC,'No space left on device')
                try:
                    with entry_lock(work/'cache_denied'/'full'):raise AssertionError('a full drive taken for a cache that cannot be locked')
                except OSError as e:assert e.errno==errno.ENOSPC,e
            finally:Path.mkdir=real_mkdir
            receipts=json.loads((work/'render_denied'/'stem_receipts.json').read_text(encoding='utf-8'))
            assert private['master']['sha256']==first['master']['sha256'] and all(x.get('unlocked_cache') for x in receipts),receipts[0]
            assert (work/'cache_denied').is_dir() and not list((work/'cache_denied').iterdir()),'something was made in the cache'
            in_the_way=work/'entry_is_a_file';in_the_way.write_text('mine',encoding='utf-8')
            try:
                with entry_lock(in_the_way):raise AssertionError('a file taken for a cache entry')
            except FileExistsError:pass
            assert in_the_way.read_text(encoding='utf-8')=='mine'
            # A draft is the same audio without what only delivery needs.
            draft=render(work/'example.json',work/'render_draft',config,cache,draft=True)
            assert draft['status']=='DRAFT_PASS' and draft['draft'] and draft['master']['sha256']==first['master']['sha256'],draft['status']
            assert not (work/'render_draft'/'master.flac').exists() and (work/'render_first'/'master.flac').is_file() and draft['left_out'][0]=='master.flac'
            return {'master_sha256':first['master']['sha256'],'cache_hits':repeat['cache_hits'],'stems_reused':repeat['stems_reused'],'parallel_jobs':parallel['jobs'],'draft_same_master':True,'checks':repeat['checks']}
        def render_folder_is_its_own_run():
            # A finished render leaves no lock file.  A resume refuses a folder holding a file the earlier render did not
            # write or one changed since (the user's own MIDI under its name), and one another run holds, leaving it as it
            # was; parts rendered at once report the part whose error the render stops on, with that error.  (Found by
            # the second review of 0.4.0.)
            import subprocess,sys,threading
            from musiclib import files as fs
            import musiclib.render as rd
            first=work/'render_first';assert not fs.occupied(first/fs.WORK_LOCK)
            # A render of its own: a copy of one (shutil.copytree) is not the run's, its record keeping each file's number.
            again=work/'render_resume_cases';render(work/'example.json',again,config,cache)
            names=lambda:sorted(x.relative_to(again).as_posix() for x in again.rglob('*'))
            before=names();own=b'MThd'+bytes(10);(again/'composition.mid').write_bytes(own)
            assert rejects(lambda:render(work/'example.json',again,config,cache,resume=True))
            assert (again/'composition.mid').read_bytes()==own and names()==before
            (again/'composition.mid').unlink();shutil.copy2(first/'composition.mid',again/'composition.mid')
            code=('import sys,time;sys.path.insert(0,sys.argv[1]);from musiclib import files\n'
                  'with files.working(sys.argv[2]) as held:\n    print(held,flush=True);time.sleep(5)')
            holder=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(again)],stdout=subprocess.PIPE,text=True)
            try:
                assert holder.stdout.readline().strip()=='True'
                try:
                    render(work/'example.json',again,config,cache,resume=True);raise AssertionError('a folder another run holds was resumed')
                except ValueError as e:assert 'in use' in str(e),e
            finally:
                holder.wait(timeout=60);holder.stdout.close()
            assert names()==before
            # Two parts that fail, the second in part order first: the render stops at once on the first to fail and
            # names it with its error (it named one part with another's); the parts still waiting never start and those
            # at work stop (every part ran to its end).  (Found by GPT Pro's second and third reviews of 0.4.0.)
            ids=[t['id'] for t in p['tracks']][:2];second_failed=threading.Event();real=rd.process_stem;reached=[]
            def failing(q,t,*a,**k):
                reached.append(t['id'])
                if t['id']==ids[1]:
                    second_failed.set();raise RuntimeError(f'{ids[1]} failed first')
                if t['id']==ids[0]:
                    second_failed.wait(60);time.sleep(.1);raise RuntimeError(f'{ids[0]} failed last')
                return real(q,t,*a,**k)
            rd.process_stem=failing
            try:
                try:
                    render(work/'example.json',work/'render_two_failures',config,work/'cache_two_failures',jobs=2);raise AssertionError('the failures went unnoticed')
                except RuntimeError as e:assert str(e)==f'{ids[1]} failed first',e
            finally:rd.process_stem=real
            failed=json.loads((work/'render_two_failures'/'report.json').read_text(encoding='utf-8'))['failed']
            assert failed['part']==ids[1] and failed['error']==f'{ids[1]} failed first',failed
            assert set(reached)<=set(ids),reached  # the parts waiting behind the two never started
            assert not fs.occupied(work/'render_two_failures'/fs.WORK_LOCK)
            # Every file a render writes is recorded as its own, a failed one's too: removing its own output (as an
            # audition does before it renders again) leaves nothing (GPT Pro's fifth review of 0.4.0).
            assert fs.remove_own(work/'render_two_failures') and not fs.occupied(work/'render_two_failures')
            # A part the first failure stopped (Cancelled), submitted before it, does not take its place in the report,
            # however late the render looks: it did once both had ended by then (found by GPT Pro's fourth review).
            second_failed.clear();real_wait=rd.wait
            def stopped_first(q,t,*a,**k):
                if t['id']==ids[1]:
                    second_failed.set();raise RuntimeError(f'{ids[1]} failed first')
                if t['id']==ids[0]:
                    second_failed.wait(60);raise audio.Cancelled(f'{ids[0]} stopped: another part failed')
                return real(q,t,*a,**k)
            def late_look(*a,**k):
                done=real_wait(*a,**k);time.sleep(.3);return done
            rd.process_stem,rd.wait=stopped_first,late_look
            try:
                try:
                    render(work/'example.json',work/'render_stopped_first',config,work/'cache_stopped_first',jobs=2);raise AssertionError('the failure went unnoticed')
                except RuntimeError as e:assert str(e)==f'{ids[1]} failed first',e
            finally:rd.process_stem,rd.wait=real,real_wait
            failed=json.loads((work/'render_stopped_first'/'report.json').read_text(encoding='utf-8'))['failed']
            assert failed['part']==ids[1] and failed['error']==f'{ids[1]} failed first',failed
            # The files made from the master stop together: the first to fail (the FLAC here, beside a slow MP3) stops
            # the program the other runs, and the render ends on its error at once (they ran to their end, and the
            # failure waited for the MP3 before it; GPT Pro's fifth review of 0.4.0 and the test of its fix).
            real_ffmpeg=audio.ffmpeg;slow=threading.Event();ended={}
            def outputs(cfg_,args,folder,label):
                if label=='mp3':
                    slow.set()
                    try:return audio.run([sys.executable,'-c','import time;time.sleep(120)'],folder,'mp3_slow')
                    finally:ended['mp3']=time.monotonic()
                if label=='flac':
                    slow.wait(60);time.sleep(.5);ended['flac']=time.monotonic();raise RuntimeError('flac failed')
                return real_ffmpeg(cfg_,args,folder,label)
            audio.ffmpeg=outputs
            try:
                try:
                    render(work/'example.json',work/'render_outputs_stop',config,cache);raise AssertionError('the failure went unnoticed')
                except RuntimeError as e:assert str(e)=='flac failed',e
            finally:audio.ffmpeg=real_ffmpeg
            assert ended['mp3']-ended['flac']<10 and not (work/'render_outputs_stop'/'logs'/'mp3_slow.process.json').exists(),ended
            assert fs.remove_own(work/'render_outputs_stop')  # the stopped program's log is the run's too
            return {'no_lock_left':True,'changed_file_refused':True,'held_folder_refused':True,'failed_part':failed['part'],
                    'outputs_stopped_after_s':round(ended['mp3']-ended['flac'],2)}
        def killed_render_resumes():
            # A render killed between two of its writes or just after a file took its name is taken up by --resume and
            # makes the master an unbroken render makes, its files all recorded and its journal gone; every cache entry
            # it wrote ends with a record of all its files.  Another killed the same way and cleaned beside a kept render
            # goes whole.  (Left for 0.5 by GPT Pro's third review of 0.4.0.)  The killed renders run their parts one at a
            # time: with two, the other part could be making a file at the moment of the kill, the one instant a render
            # leaves a file unproven (C01), and the check would hang on chance; the random-kill stress test covers
            # parallel parts (research/checks-0.5/stress_kill.py).  The files made from the master are made one at a time
            # too (one_at_a_time): a render makes the MP3, the FLAC and a loop together, so a kill placed in the MP3's
            # work could find the loop in that instant, and the resume then stops on the loop's file as it is meant to
            # (a run on main failed so on 2026-11-12: killed after decode_mp3.log, .loop.wav.*.part unproven).
            import subprocess,sys
            from musiclib import files as fs
            from musiclib.clean import clean
            one_at_a_time=('import musiclib.render as R\nfrom concurrent.futures import ThreadPoolExecutor as T\n'
                           'R.ThreadPoolExecutor=lambda max_workers=None,**k:T(max_workers=1,**k)\n')
            child=('import os,sys;sys.path.insert(0,sys.argv[1]);from musiclib import files;from musiclib.render import render\n'+one_at_a_time+
                   'mode,k=sys.argv[6],int(sys.argv[7]);n={"line":0,"swap":0};append,swap=files._Journal.append,files._swap\n'
                   'def a(self,e):\n    append(self,e);n["line"]+=1\n    if mode=="line" and n["line"]==k:os._exit(9)\n'
                   'def s(x,y):\n    swap(x,y);n["swap"]+=1\n    if mode=="swap" and n["swap"]==k:os._exit(9)\n'
                   'files._Journal.append,files._swap=a,s;render(*sys.argv[2:6],jobs=1)')
            def kill(mode,k,out,cache):
                return subprocess.run([sys.executable,'-c',child,str(SCRIPTS),str(work/'example.json'),str(out),str(config),str(cache),mode,str(k)],capture_output=True,text=True)
            reference=json.loads((work/'render_first'/'report.json').read_text(encoding='utf-8'))['master']['sha256']
            resumed=[]
            for mode,k in (('line',2),('line',60),('swap',30),('line',150)):
                out,cache=work/f'killed_{mode}_{k}',work/f'killed_cache_{mode}_{k}'
                r=kill(mode,k,out,cache);assert r.returncode==9,(mode,k,r.stderr[-800:])
                again=render(work/'example.json',out,config,cache,resume=True)
                assert again['master']['sha256']==reference,(mode,k,again['status'])
                # Everything there is the render's by its record, or by its journal: a program the killed render had
                # started (FluidSynth, FFmpeg) runs on to its end, holding its new file, which Windows will not let go
                # meanwhile; that file stays with the journal naming it, for the next render or clean to remove.
                for folder in [out,*cache.iterdir()]:
                    found,listed=fs.proofs(folder),fs.recorded(folder)
                    odd=[fs.relative(folder,x) for x in fs.tree(folder) if x.name not in (fs.RECORD,fs.JOURNAL) and not (x.parent==folder and fs.is_lock_file(x))
                         and not fs.unchanged(x,listed.get(fs.relative(folder,x),(-1,-1))) and not fs.proven(folder,x,found)]
                    assert not odd and (not (folder/fs.JOURNAL).exists() or any((folder/n).is_file() for n in found[0])),(mode,k,folder.name,odd)
                resumed.append(f'{mode} {k}')
            # The decodes the MP3 and Ogg checks make (a bus chain, a loop) are scratch files the journal names: a render
            # killed while one exists, just after FFmpeg's log for it took its name, is taken up too.  (Found by the
            # random-kill stress test of 0.5: preview_decoded.wav was written under its own name outside the journal, so
            # a render killed while it existed could not be resumed.)  The Ogg copy needs FFmpeg's libvorbis encoder, which
            # Homebrew's FFmpeg lacks: there the render makes no Ogg decode to be stopped at, only the MP3's (macOS in CI).
            from musiclib import loop as loop_files
            q=copy.deepcopy(p);q['mix']['chain']='bus';q['loop']={'start_bar':0};save_json(work/'killed_bus_loop.json',q)
            named=('import os,sys;sys.path.insert(0,sys.argv[1]);from musiclib import files;from musiclib.render import render\n'+one_at_a_time+
                   'swap=files._swap\n'
                   'def s(x,y):\n    swap(x,y)\n    if os.path.basename(y)==sys.argv[6]:os._exit(9)\n'
                   'files._swap=s;render(*sys.argv[2:6],jobs=1)')
            unbroken=render(work/'killed_bus_loop.json',work/'killed_bus_loop_unbroken',config,work/'cache_killed_bus_loop')
            for label in ('decode_mp3.log',)+(('loop_ogg_decode.log',) if loop_files.has_vorbis(audio.load_config(config)) else ()):
                out=work/f'killed_after_{label}'
                r=subprocess.run([sys.executable,'-c',named,str(SCRIPTS),str(work/'killed_bus_loop.json'),str(out),str(config),str(work/'cache_killed_bus_loop'),label],capture_output=True,text=True)
                assert r.returncode==9,(label,r.stderr[-800:])
                again=render(work/'killed_bus_loop.json',out,config,work/'cache_killed_bus_loop',resume=True)
                assert again['master']['sha256']==unbroken['master']['sha256'] and not list((out/'logs').glob('*decoded*')),label
                resumed.append(label)
            piece=work/'killed_piece';shutil.copytree(work/'render_first',piece/'kept')
            fs.register_tree(piece/'kept',keep={x:fs.stamp(piece/'kept'/x) for x in fs.recorded(work/'render_first') if (piece/'kept'/x).is_file()})
            r=kill('line',60,piece/'stopped',work/'killed_cache_line_60');assert r.returncode==9
            for _ in range(60):  # a program it had started may still hold its new file (above): clean again once it ends
                done=clean(piece,[piece/'kept'],remove=True)
                if not fs.occupied(piece/'stopped'):break
                time.sleep(1)
            assert not fs.occupied(piece/'stopped') and (piece/'kept'/'master.wav').is_file(),done
            # Killed in the instant between making a new file and noting it made (8 of 212 hard kills on Windows,
            # measured), a render leaves that file unproven: --resume stops, naming it as a file under a name the
            # render gave a new file, which it cannot prove it made; removed by the user, the resume goes on (GPT's
            # review of 0.5, C01).  The same for a file put in the place of one the render had noted made: it is
            # another file, kept as it is, and clean leaves it with the folder's records (the re-review, RR01).
            w=work/'resume_unmade';r=kill('line',60,w,work/'cache_resume_unmade');assert r.returncode==9
            with fs.journaled(w) as j:j.append({'t':'logs/.mix.process.json.0123456789ab.part'})
            unmade=w/'logs'/'.mix.process.json.0123456789ab.part';unmade.write_text('{}',encoding='utf-8')
            try:render(work/'example.json',w,config,work/'cache_resume_unmade',resume=True);raise AssertionError('the unproven file went unnoticed')
            except ValueError as e:assert 'cannot prove it made' in str(e) and 'logs/.mix.process.json.0123456789ab.part' in str(e),str(e)
            assert unmade.is_file();unmade.unlink()
            with fs.journaled(w):replaced=fs.stage_name(w/'logs'/'mix.process.json','.part')
            (w/'theirs.tmp').write_text('theirs',encoding='utf-8');os.replace(w/'theirs.tmp',replaced)
            try:render(work/'example.json',w,config,work/'cache_resume_unmade',resume=True);raise AssertionError('the replaced file went unnoticed')
            except ValueError as e:assert 'cannot prove it made' in str(e) and fs.relative(w,replaced) in str(e),str(e)
            assert replaced.read_text(encoding='utf-8')=='theirs'
            twin=work/'clean_replaced';shutil.copytree(work/'render_first',twin/'kept')
            fs.register_tree(twin/'kept',keep={x:fs.stamp(twin/'kept'/x) for x in fs.recorded(work/'render_first') if (twin/'kept'/x).is_file()})
            r=kill('line',60,twin/'stopped',work/'cache_resume_unmade');assert r.returncode==9
            with fs.journaled(twin/'stopped'):theirs=fs.stage_name(twin/'stopped'/'logs'/'mix.process.json','.part')
            (twin/'theirs.tmp').write_text('theirs',encoding='utf-8');os.replace(twin/'theirs.tmp',theirs)
            def left():return {fs.relative(twin/'stopped',x) for x in fs.tree(twin/'stopped')}-{fs.RECORD,fs.JOURNAL,fs.WORK_LOCK}
            # The file left, and the files naming the folder a render's and its piece, which stay with a folder that stays.
            only={fs.relative(twin/'stopped',theirs)}|{n for n in ('render_input.json','project.json') if (twin/'stopped'/n).is_file()}
            assert 'render_input.json' in only,only
            for _ in range(60):  # a program the killed render had started may hold its new file a while (above)
                clean(twin,[twin/'kept'],remove=True)
                if left()==only:break
                time.sleep(1)
            assert theirs.read_text(encoding='utf-8')=='theirs' and left()==only,left()
            assert (twin/'stopped'/fs.JOURNAL).is_file() and (twin/'kept'/'master.wav').is_file(),'the journal naming the file left went'
            replaced.unlink()
            again=render(work/'example.json',w,config,work/'cache_resume_unmade',resume=True)
            assert again['master']['sha256']==reference,again['master']['sha256']
            return {'resumed_after':resumed,'same_master':True,'stopped_render_cleaned_whole':True,'unmade_file_named':True,
                    'replaced_file_named_and_kept':True}
        def kept_stem_dependencies():
            # What a kept stem depends on.  Send levels and the delay's time are read only by the mixer, so editing them
            # keeps every stem, to the bit; a kick note moved processes the kick and the part it ducks again, nothing
            # else; a kept stem swapped for another file under its receipt is processed again (the copy is checked).
            q=copy.deepcopy(p);q['tracks'][1]['mix']['duck']={'by':'drums','depth_db':6};save_json(work/'duck.json',q)
            kc=work/'cache_kept';first=render(work/'duck.json',work/'render_duck',config,kc)
            stems=lambda name:{x['track']:(x['stem_reused'],x['stem_sha256']) for x in json.loads((work/name/'stem_receipts.json').read_text(encoding='utf-8'))}
            s=copy.deepcopy(q)
            for t in s['tracks']:
                if t['mix'].get('reverb_db') is not None:t['mix']['reverb_db']-=3
                if t['mix'].get('delay_db') is not None:t['mix'].update(delay_db=t['mix']['delay_db']-3,delay_quarters=.5)
            save_json(work/'duck_sends.json',s);sends=render(work/'duck_sends.json',work/'render_duck_sends',config,kc)
            a,b=stems('render_duck'),stems('render_duck_sends')
            assert sends['stems_reused']==len(q['tracks']) and all(a[k][1]==b[k][1] for k in a) and sends['master']['sha256']!=first['master']['sha256'],b
            m=copy.deepcopy(q);m['tracks'][3]['notes'][0]['on']=.5;save_json(work/'duck_moved.json',m)
            render(work/'duck_moved.json',work/'render_duck_moved',config,kc)
            redone=sorted(k for k,(reused,_) in stems('render_duck_moved').items() if not reused)
            assert redone==['bass','drums'],redone
            entry=lambda track:kc/next(x['cache_key'] for x in json.loads((work/'render_duck'/'stem_receipts.json').read_text(encoding='utf-8')) if x['track']==track)
            shutil.copyfile(entry('lead')/'stem.wav',entry('piano')/'stem.wav')
            again=render(work/'duck.json',work/'render_duck_swapped',config,kc);d=stems('render_duck_swapped')
            assert not d['piano'][0] and d['piano'][1]==a['piano'][1] and again['master']['sha256']==first['master']['sha256'],d
            return {'send_edit_stems_reused':sends['stems_reused'],'moved_kick_processed_again':redone,'swapped_stem_processed_again':True}
        def bank_select():
            q=copy.deepcopy(p);q['tracks']=[]
            for ident,bank in (('strings_b0',0),('strings_b17',17)):
                t=copy.deepcopy(p['tracks'][0]);t.update(id=ident,program=49,bank=bank,role='harmony')
                t['notes']=[{'id':ident+'_n0','on':0,'duration':6,'pitch':62}];t['performance']={'notes':{ident+'_n0':{'velocity':90}},'cc':[[0,2,100]]}
                q['tracks'].append(t)
            save_json(work/'bank.json',q);r=render(work/'bank.json',work/'render_bank',config,cache)
            raws=[x['raw_sha256'] for x in json.loads((work/'render_bank'/'stem_receipts.json').read_text(encoding='utf-8'))]
            levels=[x['reference_level_dbfs'] for x in json.loads((work/'render_bank'/'stem_receipts.json').read_text(encoding='utf-8'))]
            assert raws[0]!=raws[1] and min(levels)>-80
            return {'bank0_vs_bank17_raw_differs':True,'reference_levels':[round(x,2) for x in levels]}
        def named_soundfont():
            cfg=json.loads(Path(config).read_text(encoding='utf-8'));base=Path(cfg['soundfont']['path'])
            if not base.is_absolute():base=Path(config).resolve().parent/base
            cfg['soundfonts']={'alt':{**cfg['soundfont'],'path':str(base)}}
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            save_json(work/'two_fonts.json',cfg)
            q=copy.deepcopy(p);q['tracks'][0]['soundfont']='alt';save_json(work/'alt.json',q)
            r=render(work/'alt.json',work/'render_alt',work/'two_fonts.json',cache)
            fonts=[x['soundfont'] for x in json.loads((work/'render_alt'/'stem_receipts.json').read_text(encoding='utf-8'))]
            assert fonts[0]=='alt' and set(r['dependencies']['soundfonts'])=={'alt','default'}
            q['tracks'][0]['soundfont']='missing';save_json(work/'missing.json',q)
            rejects(lambda:render(work/'missing.json',work/'render_missing',work/'two_fonts.json',cache))
            return {'track_soundfont':fonts[0],'unknown_name_rejected':True}
        def named_bank_first_use():
            # A named bank is hashed when a part first uses it, not at load: a wrong hash passes load_config and stops
            # review and the render at first use, before anything is synthesized, and a round stopped so keeps its
            # record, naming the step.  A bank changed on disk after its first use in a process is hashed again.
            from musiclib.revision import revision_round
            cfg=json.loads(Path(config).read_text(encoding='utf-8'));base=Path(cfg['soundfont']['path'])
            if not base.is_absolute():base=Path(config).resolve().parent/base
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            copied=work/'named_bank.sf2';shutil.copyfile(base,copied)
            cfg['soundfonts']={'alt':{**cfg['soundfont'],'path':str(copied)},'wrong':{**cfg['soundfont'],'path':str(base),'sha256':'0'*64}}
            save_json(work/'lazy_banks.json',cfg);loaded=audio.load_config(work/'lazy_banks.json')
            q=copy.deepcopy(p);q['tracks'][0]['soundfont']='wrong';save_json(work/'wrong_bank.json',q)
            assert rejects(lambda:audio.soundfont_for(loaded,q['tracks'][0]))
            assert rejects(lambda:render(work/'wrong_bank.json',work/'render_wrong_bank',work/'lazy_banks.json',cache)) and not (work/'render_wrong_bank').exists()
            try:
                revision_round(work/'wrong_bank.json',work/'round_wrong_bank',work/'lazy_banks.json',show=lambda _:None);raise AssertionError('the round went on')
            except ValueError as e:assert 'hash mismatch' in str(e),e
            record=json.loads((work/'round_wrong_bank'/'round.json').read_text(encoding='utf-8'))
            assert record['status']=='FAIL' and record['failed']['step']=='review' and 'hash mismatch' in record['failed']['error'],record
            t=copy.deepcopy(p['tracks'][0]);t['soundfont']='alt';audio.soundfont_for(loaded,t)
            with copied.open('ab') as f:f.write(b'\0')
            assert rejects(lambda:audio.soundfont_for(audio.load_config(work/'lazy_banks.json'),t))
            return {'wrong_hash_passes_load':True,'stops_at_first_use':True,'round_record_names_review':True,'changed_bank_hashed_again':True}
        def bend_render():
            q=copy.deepcopy(p);q['clock']={'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':1}
            q['sections']=[{'id':'bend','start_bar':0,'bars':2,'intent':'Pitch bend check'}]
            t=copy.deepcopy(p['tracks'][0]);t.update(id='flute_bend',program=73,bank=0,role='melody',range=[60,80])
            t['notes']=[{'id':'flute_bend_n0','on':0,'duration':4,'pitch':69}]
            t['performance']={'notes':{'flute_bend_n0':{'velocity':96}},'bend_range':12,'bend':[[0,0],[2,0],[2.25,2],[4,2]]}
            q['tracks']=[t];save_json(work/'bend.json',q);render(work/'bend.json',work/'render_bend',config,cache)
            a,_=audio.read_wav(work/'render_bend'/'stems'/'flute_bend.wav');m=a.mean(axis=1)
            f1=yin_f0(m[int(.4*audio.RATE):int(.9*audio.RATE)],audio.RATE,fmin=200,fmax=2000)
            f2=yin_f0(m[int(1.4*audio.RATE):int(1.9*audio.RATE)],audio.RATE,fmin=200,fmax=2000)
            moved=float(12*np.log2(f2/f1))
            assert abs(moved-2)<.12,moved
            return {'before_hz':round(f1,2),'after_hz':round(f2,2),'semitones':round(moved,3)}
        def width_and_legato_render():
            q=copy.deepcopy(p);q['clock']={'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':1}
            q['sections']=[{'id':'slur','start_bar':0,'bars':2,'intent':'Legato and width check'}]
            t=copy.deepcopy(p['tracks'][0]);t.update(id='flute_slur',program=73,bank=0,role='melody',range=[60,90])
            t['mix']={**t['mix'],'width':0}
            line=[(0,72),(1,74),(2,76),(3,83)]
            t['notes']=[{'id':f'flute_slur_n{k}','on':on,'duration':1,'pitch':m} for k,(on,m) in enumerate(line)]
            t['performance']={'notes':{f'flute_slur_n{k}':{'velocity':96,'gate':1.0} for k in range(4)},'bend_range':12,
                              'legato':{'max_interval':5,'glide_ms':20,'gap_ms':40,'max_notes':4}}
            q['tracks']=[t];save_json(work/'slur.json',q);render(work/'slur.json',work/'render_slur',config,cache)
            exported=next(x for x in midi.read(work/'render_slur'/'composition.mid')['tracks'] if x['name']=='flute_slur')
            export_ons=sum(1 for e in exported['events'] if e[1]>>4==9 and e[3]>0)
            midi.write(q,work/'slur_synth.mid',render=True)
            synthesis=next(x for x in midi.read(work/'slur_synth.mid')['tracks'] if x['name']=='flute_slur')
            synth_ons=sum(1 for e in synthesis['events'] if e[1]>>4==9 and e[3]>0)
            assert export_ons==4 and synth_ons==2,(export_ons,synth_ons)
            a,_=audio.read_wav(work/'render_slur'/'stems'/'flute_slur.wav')
            assert np.allclose(a[:,0],a[:,1]),'width 0 must be mono'
            m=a.mean(axis=1);f=yin_f0(m[int(1.1*audio.RATE):int(1.45*audio.RATE)],audio.RATE,fmin=200,fmax=2000)
            assert abs(12*np.log2(f/440)-(76-69))<.15,f
            q2=copy.deepcopy(q);q2['tracks'][0]['performance']['bend_range']=4;rejects(lambda:validate(q2))
            from musiclib.model import legato_notes
            ns,pts=legato_notes(t,performed(t,Clock(q)),Clock(q))
            assert [n['slurred'] for n in ns]==[3,1] and max(v for _,v in pts)==4
            # Two groups that start on one key and touch: the first must let go before the second sounds, or its
            # note-off silences the second (a guitar riff lost 0.85 s this way).
            t2=copy.deepcopy(t);line2=[(0,77,.75),(.75,79,.5),(1.25,77,.5),(1.75,74,.5),(2.25,76,.5),(2.75,72,.5)]
            t2['notes']=[{'id':f'r{k}','on':on,'duration':d,'pitch':m} for k,(on,m,d) in enumerate(line2)]
            t2['performance']={'notes':{f'r{k}':{'velocity':100,'gate':1.02} for k in range(6)},'bend_range':12,
                               'legato':{'max_interval':5,'glide_ms':25,'gap_ms':40,'max_notes':2}}
            groups,_=legato_notes(t2,performed(t2,Clock(q)),Clock(q))
            same=[g for g in groups if g['pitch']==77]
            assert len(same)==2 and same[0]['end_tick']<same[1]['tick'] and same[0].get('retrigger_trimmed'),same
            return {'export_note_ons':export_ons,'synthesis_notes':len(ns),'third_note_hz':round(f,2),'mono_with_width_0':True}
        def reversed_crash():
            # A sampled crash played backwards (reverse: true): silent before its note, rising through it, loudest at its
            # end and silent after, whatever swing, timing and gate the part was given, so it stops on the downbeat.
            import math
            q=copy.deepcopy(p);q.pop('harmony',None);q['clock']={'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':2}
            q['sections']=[{'id':'a','start_bar':0,'bars':2}]
            t=copy.deepcopy(p['tracks'][0]);[t.pop(k,None) for k in ('soundfont','patch','key_map')]
            t.update(id='revcym',engine='soundfont',drums=True,role='effect',patch={'bank':128,'program':0},reverse=True,range=[35,60])
            t['notes']=[{'id':'c','on':2,'duration':2,'pitch':49}]
            t['performance']={'notes':{'c':{'velocity':110,'gate':.5,'timing_ms':12}},'swing':{'ratio':.6,'unit':.5}}
            q['tracks']=[t];save_json(work/'reverse.json',q)
            r=render(work/'reverse.json',work/'render_reverse',config,work/'cache_reverse')
            rec=json.loads((work/'render_reverse'/'stem_receipts.json').read_text(encoding='utf-8'))[0]
            x,_=audio.read_wav(work/'cache_reverse'/rec['cache_key']/'raw.wav');x=np.asarray(x,dtype=float).mean(axis=1);hop=int(.05*audio.RATE)
            db=[20*math.log10(np.sqrt(np.mean(x[i:i+hop]**2))+1e-9) for i in range(0,len(x)-hop,hop)]
            peak=(int(np.argmax(db))+.5)*.05;rise=float(np.mean(db[36:40])-np.mean(db[20:24]))
            assert all(r['checks'].values()) and max(db[:19])<-100 and max(db[41:])<-100 and 1.85<=peak<=2.0 and rise>6,(peak,rise,max(db[:19]),max(db[41:]))
            assert not list((work/'cache_reverse'/rec['cache_key']).glob('reverse_*')),'per-note files left behind'
            return {'peak_s':peak,'rise_db':round(rise,1)}
        def layered_render():
            bank=xf_bank();cfg=json.loads(Path(config).read_text(encoding='utf-8'))
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            cfg['soundfonts']={'xf':{'path':str(bank),'sha256':file_hash(bank)}};save_json(work/'xf_config.json',cfg)
            q=copy.deepcopy(p);q['clock']={'bars':4,'meter':[4,4],'tempo':[[0,90]],'tail_seconds':2}
            q['sections']=[{'id':'line','start_bar':0,'bars':4,'intent':'A slurred line'}]
            line=[60,64,67,64,60,62,64,67,69,67,64,62,60,64,67,72];q['tracks']=[]
            for ident,extra in (('leg',{'legato':{'mode':'crossfade','crossfade_ms':100},'dynamics':[[0,40],[16,127]],'dynamics_mode':'crossfade'}),('plain',{})):
                t=copy.deepcopy(p['tracks'][0]);t.update(id=ident,soundfont='xf',patch={'bank':0,'program':48},program=48,bank=0,role='harmony',range=[55,75])
                t['notes']=[{'id':f'{ident}_{i}','on':i,'duration':1,'pitch':x} for i,x in enumerate(line)]
                t['performance']={'notes':{f'{ident}_{i}':{'velocity':80} for i in range(len(line))},'offset_ms':-90,**extra}
                t['mix']={**t['mix'],'reverb_db':None,'delay_db':None,'level_dbfs':-20,'pan':0};q['tracks'].append(t)
            q['mix']={'chain':'bus','dynamics':'wide','target_lufs':-20};save_json(work/'xf.json',q)
            render(work/'xf.json',work/'render_xf',work/'xf_config.json',cache)
            rec={x['track']:x for x in json.loads((work/'render_xf'/'stem_receipts.json').read_text(encoding='utf-8'))};spb=60/90;out={}
            for ident in ('leg','plain'):
                m=audio.read_wav(work/'render_xf'/'stems'/f'{ident}.wav')[0].mean(axis=1)
                env=20*np.log10(np.sqrt(np.mean(m[:len(m)//480*480].reshape(-1,480)**2,axis=1))+1e-9);at=lambda k:int(k*spb*100)
                dips=[float(np.median(env[at(k)-40:at(k)-10])-env[at(k)-6:at(k)+30].min()) for k in range(1,16)]
                def centroid(a,b):
                    seg=m[int(a*spb*48000):int(b*spb*48000)];s=np.abs(np.fft.rfft(seg*np.hanning(len(seg))));return float((s*np.fft.rfftfreq(len(seg),1/48000)).sum()/s.sum())
                out[ident]=(max(dips),centroid(.3,1.),centroid(15.3,16.))
            # Slurred notes no longer swell in again (each take ramps in over 300 ms); the crescendo moves from the soft
            # take to the bright one.
            assert out['leg'][0]<4<9<out['plain'][0] and out['leg'][2]>2*out['leg'][1],out
            assert rec['leg']['expressive']['renders']==4 and rec['leg']['expressive']['legato_entries']==15 and 'expressive' not in rec['plain']
            cc1=[e for e in midi.read(work/'render_xf'/'midi'/'leg.mid')['tracks'][1]['events'] if e[1]>>4==11 and e[2]==1]
            assert len(cc1)>50 and cc1[-1][3]==127,len(cc1)
            return {'largest_transition_dip_db':{'legato':round(out['leg'][0],1),'re_attacked':round(out['plain'][0],1)},
                    'centroid_hz':{'start':round(out['leg'][1]),'end':round(out['leg'][2])},'exported_cc1_events':len(cc1)}
        def take_dynamics():
            # The default "take" dynamics mode (musiclib/layered.py, schema.md; no check ran it before 0.8: the selfcheck's
            # coverage): each note plays the one recorded dynamic nearest the curve's mean over the note, the dynamics
            # evenly spaced over 0-127, so two takes of a note never sound together; the level follows the curve.
            bank=xf_bank();cfg=json.loads(Path(config).read_text(encoding='utf-8'))
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            cfg['soundfonts']={'xf':{'path':str(bank),'sha256':file_hash(bank)}};save_json(work/'take_config.json',cfg)
            q=copy.deepcopy(p);q['clock']={'bars':4,'meter':[4,4],'tempo':[[0,90]],'tail_seconds':2}
            q['sections']=[{'id':'line','start_bar':0,'bars':4,'intent':'A crescendo on detached notes'}]
            t=copy.deepcopy(p['tracks'][0]);t.update(id='take',soundfont='xf',patch={'bank':0,'program':48},program=48,bank=0,role='harmony',range=[55,75])
            t['notes']=[{'id':f'take_{i}','on':i,'duration':.9,'pitch':60+(i%5)} for i in range(16)]
            t['performance']={'notes':{f'take_{i}':{'velocity':80} for i in range(16)},'dynamics':[[0,20],[16,127]]}
            t['mix']={**t['mix'],'reverb_db':None,'delay_db':None,'level_dbfs':-20,'pan':0};q['tracks']=[t]
            q['mix']={'chain':'bus','dynamics':'wide','target_lufs':-20};save_json(work/'take.json',q)
            render(work/'take.json',work/'render_take',work/'take_config.json',cache)
            ex=next(x for x in json.loads((work/'render_take'/'stem_receipts.json').read_text(encoding='utf-8')) if x['track']=='take')['expressive']
            # Two layers, as xf_bank records them: the count is the fixture's, not read back from the render (the outside
            # review of 2026-11-15 found it taken from the receipt under test).
            layers=len(ex['dynamic_layers']);assert layers==2,ex['dynamic_layers'];expected={}
            for i in range(16):  # the curve's mean over a note of a straight line is its value at the note's middle
                k=min(layers-1,max(0,round((20+107*(i+.45)/16)/127*(layers-1))));expected[str(k)]=expected.get(str(k),0)+1
            assert ex['mode']=='take' and ex['notes_per_take']==expected and sorted(ex['takes_used'])==sorted(int(k) for k in expected),(ex,expected)
            m=audio.read_wav(work/'render_take'/'stems'/'take.wav')[0].mean(axis=1);spb=60/90
            seg=lambda b:m[int(b*spb*audio.RATE):int((b+.8)*spb*audio.RATE)]
            rise=float(10*np.log10(np.mean(seg(15)**2)/np.mean(seg(0)**2)))
            assert rise>10,rise
            return {'dynamic_layers':layers,'notes_per_take':ex['notes_per_take'],'rise_db':round(rise,1)}
        def surge_part():
            from musiclib import surge
            # A Surge part: on a configuration without Surge XT it plays its preset's fallback on the built-in synth and
            # the receipt says why; with Surge XT installed it plays the patch, and a second render keeps that take.
            q=copy.deepcopy(p);q['clock']={'bars':2,'meter':[4,4],'tempo':[[0,100]],'tail_seconds':4}
            q['sections']=[{'id':'pad','start_bar':0,'bars':2,'intent':'chords'}]
            t=copy.deepcopy(p['tracks'][0]);[t.pop(k,None) for k in ('soundfont','patch','key_map')]
            t.update(id='pad',engine='surge',role='harmony',range=[48,72],surge={'preset':'juno_60_strings'})
            t['notes']=[{'id':f'pad_{k}','on':4*k,'duration':4,'pitch':x} for k,chord in enumerate(((57,60,64),(53,57,60))) for x in chord]
            t['notes']=[{**n,'id':f'{n["id"]}_{i}'} for i,n in enumerate(t['notes'])]
            t['performance']={'notes':{n['id']:{'velocity':80,'gate':1.0} for n in t['notes']}}
            q['tracks']=[t];save_json(work/'surge.json',q)
            cfg=json.loads(Path(config).read_text(encoding='utf-8'));has=bool(cfg.get('surge') and cfg.get('pedalboard'))
            # Surge XT is optional for users, and a setup without it passed here on the fallback alone.  With
            # MUSIC_SKILL_REQUIRE_SURGE set (CI sets it where the setup installs Surge XT) it is required, so a setup
            # that failed to install it fails here, as a missing Ogg encoder does.
            assert has or not os.environ.get('MUSIC_SKILL_REQUIRE_SURGE'),'the configuration names no Surge XT (surge and pedalboard), and MUSIC_SKILL_REQUIRE_SURGE asks for it'
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            cfg.pop('surge',None);cfg.pop('pedalboard',None);save_json(work/'no_surge_config.json',cfg)
            render(work/'surge.json',work/'render_surge_fallback',work/'no_surge_config.json',work/'cache_surge')
            fell=json.loads((work/'render_surge_fallback'/'stem_receipts.json').read_text(encoding='utf-8'))[0]['surge']
            assert fell['rendered_with']=='built-in synth' and fell['fallback']==surge.presets()['presets']['juno_60_strings']['fallback'] and 'not installed' in fell['reason'],fell
            # A render that finds the part in the cache reports it as the render that made it: the record of how it was
            # played comes from the cache entry (0.8's second outside review, 2026-11-16: no check read a second
            # render's record, so a cache hit that lost it passed).
            render(work/'surge.json',work/'render_surge_fallback_again',work/'no_surge_config.json',work/'cache_surge')
            kept=json.loads((work/'render_surge_fallback_again'/'stem_receipts.json').read_text(encoding='utf-8'))[0]
            assert kept['cache_hit'] and kept.get('surge')==fell,(fell,kept.get('surge'))
            # Where Surge XT is not configured the take is the built-in synth's, exactly the render's frames (0.8 step
            # 1.4; Surge XT's own takes vary in length): one frame more, its receipt matched, is refused and made again.
            e=work/'cache_surge'/kept['cache_key'];x=np.array(audio.read_wav(e/'raw.wav')[0]);F=len(x)
            audio.write_wav(e/'raw.wav',np.vstack([x,np.zeros((1,2),np.float32)]))
            r=json.loads((e/'receipt.json').read_text(encoding='utf-8'));r['sha256']=audio.audio_hash(e/'raw.wav');save_json(e/'receipt.json',r)
            render(work/'surge.json',work/'render_surge_fallback_long',work/'no_surge_config.json',work/'cache_surge')
            longer=json.loads((work/'render_surge_fallback_long'/'stem_receipts.json').read_text(encoding='utf-8'))[0]
            assert not longer['cache_hit'] and f'{F+1} frames' in longer.get('cache_rejected',{}).get('raw',''),longer
            out={'without_surge':fell['fallback']}
            if has:
                first=render(work/'surge.json',work/'render_surge',config,work/'cache_surge')
                again=render(work/'surge.json',work/'render_surge_again',config,work/'cache_surge')
                a,b=(json.loads((work/n/'stem_receipts.json').read_text(encoding='utf-8'))[0] for n in ('render_surge','render_surge_again'))
                x,_=audio.read_wav(work/'render_surge'/'stems'/'pad.wav')
                assert a['surge']['rendered_with']=='Surge XT' and b['cache_hit'] and a['raw_sha256']==b['raw_sha256'],(a.get('surge'),b['cache_hit'])
                assert b.get('surge')==a['surge'],(a['surge'],b.get('surge'))  # the kept take keeps its record, as above
                assert first['master']['sha256']==again['master']['sha256'] and float(np.sqrt(np.mean(np.asarray(x,dtype=float)**2)))>1e-4
                out['with_surge']='Surge XT, take kept by the cache'
                # Surge XT configured but its host failing at render time: the part plays its fallback under the same key,
                # its take bounded by the ceiling as Surge XT's would be (one frame longer, its receipt matched: a hit), and
                # the next render keeps the record of how it was played (the Astra review of step 2)
                real_render=surge.render
                surge.render=lambda *a,**k:(_ for _ in ()).throw(surge.Unavailable("the host stopped (the check's)"))
                try:render(work/'surge.json',work/'render_surge_down',config,work/'cache_surge_down')
                finally:surge.render=real_render
                down=json.loads((work/'render_surge_down'/'stem_receipts.json').read_text(encoding='utf-8'))[0]
                assert down['surge']['rendered_with']=='built-in synth' and "the check's" in down['surge']['reason'],down['surge']
                e=work/'cache_surge_down'/down['cache_key'];y=np.array(audio.read_wav(e/'raw.wav')[0])
                audio.write_wav(e/'raw.wav',np.vstack([y,np.zeros((1,2),np.float32)]))
                r=json.loads((e/'receipt.json').read_text(encoding='utf-8'));r['sha256']=audio.audio_hash(e/'raw.wav');save_json(e/'receipt.json',r)
                render(work/'surge.json',work/'render_surge_down_again',config,work/'cache_surge_down')
                again=json.loads((work/'render_surge_down_again'/'stem_receipts.json').read_text(encoding='utf-8'))[0]
                assert again['cache_hit'] and 'cache_rejected' not in again and again.get('surge')==down['surge'],again
                # A release longer than four seconds rings into the piece's tail (tail_seconds), as far as it asks: the
                # host stopped four seconds after the last note, and the rest was silence, which passed the quiet-tail
                # check (GPT Pro's seventh review of 0.4.0).
                r=copy.deepcopy(q);r['clock']={'bars':1,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':10};r['sections']=[{'id':'one','start_bar':0,'bars':1}]
                pad=r['tracks'][0];pad.update(surge={'preset':'ghost_pad'},notes=[{'id':'n','on':0,'duration':2,'pitch':60}])
                pad['performance']={'notes':{'n':{'velocity':90,'gate':1.0}}};save_json(work/'surge_tail.json',r)
                render(work/'surge_tail.json',work/'render_surge_tail',config,work/'cache_surge')
                key=json.loads((work/'render_surge_tail'/'stem_receipts.json').read_text(encoding='utf-8'))[0]['cache_key']
                raw,info=audio.read_wav(work/'cache_surge'/key/'raw.wav');late=np.asarray(raw[6*audio.RATE:7*audio.RATE],dtype=float)
                assert info['seconds']>=11.9 and late.size and float(np.sqrt(np.mean(late**2)))>1e-6,(info['seconds'],late.size)
                out['release_past_four_seconds']=True
                # The slide the score sets: a bass held into an overlapping note a fourth up glides there over about
                # glide_ms (Surge's portamento curve settles a little later), and a note that does not overlap starts at
                # its own pitch; the receipt says what was set.
                from soundbank import pitch_track
                s=copy.deepcopy(r);s['clock']={'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':2};s['sections']=[{'id':'two','start_bar':0,'bars':2}]
                bass=s['tracks'][0];bass.update(id='slide',role='bass',range=[24,60],surge={'preset':'bass_1','glide_ms':80})
                bass['notes']=[{'id':'a','on':0,'duration':2.1,'pitch':36},{'id':'b','on':2,'duration':2,'pitch':41},{'id':'c','on':6,'duration':1,'pitch':36}]
                bass['performance']={'notes':{k:{'velocity':100,'gate':1.0} for k in 'abc'}};save_json(work/'surge_slide.json',s)
                render(work/'surge_slide.json',work/'render_surge_slide',config,work/'cache_surge')
                rec=json.loads((work/'render_surge_slide'/'stem_receipts.json').read_text(encoding='utf-8'))[0]
                raw,_=audio.read_wav(work/'cache_surge'/rec['cache_key']/'raw.wav');x=np.asarray(raw,dtype=float).mean(axis=1)
                f0,win=pitch_track(x,audio.RATE,30,400,120);tt=(np.arange(len(f0))*120+win/2)/audio.RATE
                c=np.array([np.nan if np.isnan(v) else 1200*np.log2(v/65.406) for v in f0])
                voiced=[i for i in range(len(c)) if tt[i]>.95 and tt[i]<1.6 and not np.isnan(c[i])]
                leave=next(i for i in voiced if c[i]>30);arrive=next(i for k,i in enumerate(voiced) if i>leave and all(abs(c[j]-500)<20 for j in voiced[k:k+5]))
                lone=np.nanmedian(c[(tt>3.15)&(tt<3.45)])
                assert rec['surge'].get('played_as')=={'glide_ms':80} and 50<=1000*(tt[arrive]-tt[leave])<=130 and abs(lone)<30,(rec['surge'],tt[arrive]-tt[leave],lone)
                out['slide_ms']=round(1000*(tt[arrive]-tt[leave]),1)
            return out
        def outputs_carry_no_input_metadata():
            # Tags in a cached WAV (an artist, a comment that could hold a path) do not reach what FFmpeg writes from it: every
            # output is written with -map_metadata -1 and -map_chapters -1 (audio.ffmpeg).
            cfg=audio.load_config(config);src=work/'tagged.wav';audio.write_wav(src,np.zeros((4800,2),dtype=np.float32))
            chunk=lambda tag,b:tag+struct.pack('<I',len(b))+b+(b'\0' if len(b)%2 else b'')
            data=src.read_bytes()+chunk(b'LIST',b'INFO'+chunk(b'IART',b'tagged-artist-7151\0')+chunk(b'ICMT',b'tagged-comment-2938\0'))
            src.write_bytes(data[:4]+struct.pack('<I',len(data)-8)+data[8:])
            for name,codec in (('out.wav',['-c:a','pcm_s24le']),('out.mp3',['-c:a','libmp3lame','-b:a','128k']),('out.flac',['-c:a','flac'])):
                audio.ffmpeg(cfg,['-i',src,*codec,work/name],work/'logs_meta','meta_'+name.replace('.','_'))
                raw=(work/name).read_bytes();assert b'tagged-artist-7151' not in raw and b'tagged-comment-2938' not in raw,name
            return {'outputs':3}
        def a_silent_part_is_named():
            # A part whose synthesis is silent (here drum notes on a key the kit has no sample for) stops the render
            # with its name and what to check; as an audition's context part (`quiet`) it keeps its own level instead.
            q=copy.deepcopy(p);q['clock']={'bars':1,'meter':[4,4],'tempo':[[0,100]],'tail_seconds':1};q['sections']=[{'id':'a','start_bar':0,'bars':1}]
            q.pop('harmony',None);piano=copy.deepcopy(next(t for t in p['tracks'] if t['id']=='piano'));drums=copy.deepcopy(next(t for t in p['tracks'] if t['drums']))
            piano['notes']=[{'id':'pn','on':0,'duration':3,'pitch':60}];piano['performance']={'notes':{'pn':{'velocity':80}},'cc':[]}
            drums['notes']=[{'id':'dn','on':0,'duration':.25,'pitch':2}];drums['performance']={'notes':{'dn':{'velocity':100}},'cc':[]};drums['range']=[0,127]
            q['tracks']=[piano,drums];save_json(work/'silent.json',q)
            try:render(work/'silent.json',work/'render_silent',config,work/'cache_silent',draft=True);raise AssertionError('a silent part rendered')
            except ValueError as e:assert f'{drums["id"]}: its synthesis is silent' in str(e) and 'keys' in str(e),e
            # The render that stopped says so in its folder: report.json names the stage it had finished, the part and
            # why, and a round or a comparison will not take it for a finished render.  (Found by a review of 0.4.0.)
            from musiclib.render import stopped
            failed=json.loads((work/'render_silent'/'report.json').read_text(encoding='utf-8'))
            assert failed['status']=='FAIL' and failed['failed']['part']==drums['id'] and failed['failed']['after_stage']=='midi' and 'silent' in failed['failed']['error'],failed
            assert stopped(work/'render_silent') and stopped(work/'render_silent_never') is None
            r=render(work/'silent.json',work/'render_silent_quiet',config,work/'cache_silent',draft=True,quiet={drums['id']})
            receipt=next(x for x in json.loads((work/'render_silent_quiet'/'stem_receipts.json').read_text(encoding='utf-8')) if x['track']==drums['id'])
            assert r['status']=='DRAFT_PASS' and receipt.get('nearly_silent') is True,(r['status'],receipt)
            return {'named':drums['id']}
        found.update({'render_cache_checks_each_take_before_using_it': cache_takes_checked, 'actual_render_repeat_is_sample_identical': integration, 'render_folder_is_its_own_run': render_folder_is_its_own_run, 'a_killed_render_resumes': killed_render_resumes, 'kept_stems_follow_what_they_read': kept_stem_dependencies, 'bank_lsb_selects_bank_on_default_soundfont': bank_select, 'named_soundfont_selected_per_track': named_soundfont, 'named_bank_verified_at_first_use': named_bank_first_use, 'pitch_bend_moves_soundfont_pitch': bend_render, 'legato_slurs_and_width_render': width_and_legato_render, 'a_reversed_note_swells_into_its_end': reversed_crash, 'layered_render_slurs_and_crossfades_dynamics': layered_render, 'take_dynamics_play_one_recorded_dynamic_per_note': take_dynamics, 'surge_part_plays_the_patch_or_its_fallback': surge_part, 'outputs_carry_no_input_metadata': outputs_carry_no_input_metadata, 'a_silent_part_is_named': a_silent_part_is_named})
    return found
