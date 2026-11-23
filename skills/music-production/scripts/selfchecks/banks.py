"""selfcheck.py's checks of one area (0.8 step 1.8). SoundFont banks and their sources: the SoundFont reader and writer, soundbank.py's build, split, cut and cleaning, the WAV, AIFF and FLAC readers, and the lookups of presets and sounds.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import json
import numpy as np
import os
import struct
from musiclib import audio
from musiclib.model import file_hash, save_json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    config, rejects, work, xf_bank = S['config'], S['rejects'], S['work'], S['xf_bank']
    def sf2_roundtrip():
        from musiclib import sf2
        tone=(0.4*np.sin(2*np.pi*440*np.arange(4800)/48000)).astype(np.float32)
        sf2.write(work/'tiny.sf2','tiny',[{'name':'A4','data':tone,'rate':48000,'root':69}],
                  [{'name':'inst','global':{38:sf2.timecents(.2)},'zones':[{'gens':{43:(60,80),44:(1,127)},'sample':0}]}],
                  [{'name':'tiny','bank':0,'program':0,'global':{},'zones':[{'gens':{},'instrument':0}]}])
        bank=sf2.read(work/'tiny.sf2');inv=sf2.inventory(bank)[0];back=sf2.load_sample(bank,0)
        assert inv['keys']==[60,80] and inv['samples']==1 and inv['sample_rates']==[48000]
        assert np.max(np.abs(back-np.round(tone*32767)/32767))<1e-4
        # A bank past SoundFont 2's 16-bit indices is refused as ValueError before anything is written: struct.error went
        # past the commands' handlers (the whole review of 0.8; an SFZ of 14,000 regions reaches it): 22,000 zones of four
        # generators, and 65,537 samples whose last stereo pair links past 65,535
        many=[{'gens':{43:(k%128,k%128),58:60,51:0},'sample':0} for k in range(22000)]
        mono={'name':'s','data':tone[:2],'rate':48000,'root':69}
        pair=[{**mono,'name':'L','link':65536,'type':4},{**mono,'name':'R','link':65535,'type':2}]
        for samples,zones in (([mono],many),([mono]*65535+pair,[{'gens':{},'sample':0}])):
            try:sf2.write(work/'too_many.sf2','too many',samples,[{'name':'inst','zones':zones}],[{'name':'p','bank':0,'program':0,'zones':[{'gens':{},'instrument':0}]}]);raise AssertionError('a bank past its indices written')
            except ValueError as e:assert 'index limit' in str(e),e
        assert not (work/'too_many.sf2').exists()
        return inv
    def sf2_inventory():
        # sf2.inventory, which `soundbank.py inspect` prints and 0.8's instrument lookup reads, on a bank whose contents
        # are known: keys over every zone (a zone with no key range spans 0-127), velocity layers, samples, their rates
        # and seconds, looped zones. Two one-line faults in it passed every check before (0.8's mutation run).
        from musiclib import sf2
        a=(.3*np.sin(2*np.pi*220*np.arange(4800)/48000)).astype(np.float32);b=(.3*np.sin(2*np.pi*110*np.arange(9600)/24000)).astype(np.float32)
        sf2.write(work/'inventory.sf2','inventory',[{'name':'a','data':a,'rate':48000,'root':57,'loop':(100,4000)},{'name':'b','data':b,'rate':24000,'root':45}],
                  [{'name':'inst','global':{},'zones':[{'gens':{43:(40,50),44:(1,63),54:1},'sample':0},{'gens':{44:(64,127)},'sample':1}]}],
                  [{'name':'inventory','bank':0,'program':5,'global':{},'zones':[{'gens':{},'instrument':0}]}])
        inv=sf2.inventory(sf2.read(work/'inventory.sf2'))
        assert inv==[{'preset':'inventory','bank':0,'program':5,'keys':[0,127],'velocity_layers':2,'samples':2,'sample_rates':[24000,48000],
                      'sample_seconds':.5,'looped_zones':1}],inv
        return inv[0]
    def kit_build():
        import wave
        from musiclib import sf2
        from soundbank import build
        root=work/'kit_source';t=np.arange(14400)/48000;s=np.sin(2*np.pi*200*t)*np.exp(-t/.05)
        def wav(path,x):
            path.parent.mkdir(parents=True,exist_ok=True);q=np.clip(np.round(x*32767),-32768,32767).astype('<i2')
            with wave.open(str(path),'wb') as w:w.setnchannels(q.shape[1]);w.setsampwidth(2);w.setframerate(48000);w.writeframes(q.tobytes())
        for dyn,a in (('1',.25),('2',.5)):
            for rr in '12':
                wav(root/'kick'/'close'/f'k_vl{dyn}_rr{rr}.wav',(a*s)[:,None]);wav(root/'kick'/'oh'/f'k_vl{dyn}_rr{rr}.wav',np.repeat((.8*a*s)[:,None],2,1))
        wav(root/'hat'/'close'/'h_vl1_rr1.wav',(.125*s)[:,None])
        kick={'mics':[{'dir':'kick/close','gain':1.0,'pan':.5},{'dir':'kick/oh','gain':.5}],'template':'k_vl{dyn}_rr{rr}.wav',
              'root':36,'keys':[36,36],'dynamics':['1','2'],'velocity':{'1':[1,64],'2':[65,127]},'level':'peak','match_notes':False,
              'pitch_check':False,'rr_block':1,'velocity_attenuation_cb':60,'velocity_filter_cents':0}
        hat={'mics':[{'dir':'hat/close'}],'template':'h_vl{dyn}_rr{rr}.wav','root':42,'keys':[42,42],'dynamics':['1'],
             'velocity':{'1':[1,127]},'level':'peak','match_notes':False,'pitch_check':False,'exclusive_class':1}
        spec={'name':'kit','presets':[{'name':'kit','program':0,'level_reference':'preset','layers':[kick,hat]}]}
        kit_receipt=build(spec,root,work/'kit.sf2');bank=sf2.read(work/'kit.sf2')
        # A kit's takes are not pitch-measured: pitch_check is false (a mutant that read the switch from another field
        # measured them: 0.8's second mutation sample, 2026-11-15).
        assert kit_receipt['files'] and all(r['f0_hz'] is None for r in kit_receipt['files']),[(r['file'],r['f0_hz']) for r in kit_receipt['files']]
        # A microphone's `name` changes a take's file name, never its folder: a separator, "..", or on Windows a drive
        # names another place (the re-review of GPT's security audit, N4).  One that keeps the folder is used.
        for swap in (['k_','../close/k_'],['k_','sub/k_'],['k_vl1_rr1.wav','..']):
            odd={**kick,'mics':[kick['mics'][0],{**kick['mics'][1],'name':swap}]}
            try:build({'name':'kit','presets':[{'name':'kit','program':0,'layers':[odd]}]},root,work/'kit_odd.sf2');raise AssertionError(swap)
            except ValueError as e:assert 'file name, not its folder' in str(e),e
        if os.name=='nt':
            odd={**kick,'mics':[kick['mics'][0],{**kick['mics'][1],'name':['k_','D:k_']}]}
            try:build({'name':'kit','presets':[{'name':'kit','program':0,'layers':[odd]}]},root,work/'kit_odd.sf2');raise AssertionError('a drive in a take name')
            except ValueError as e:assert 'file name, not its folder' in str(e),e
        assert not (work/'kit_odd.sf2').exists()
        assert sf2.inventory(bank)[0]['keys']==[36,42]
        names={x['name']:i for i,x in enumerate(bank['samples'])};peak=lambda n:float(np.max(np.abs(sf2.load_sample(bank,names[n]))))
        # The close microphone panned right of a centred overhead pair; the hat keeps its recorded level against the kick.
        pan_ratio=peak('k_vl2_rr1R')/peak('k_vl2_rr1L');balance=peak('h_vl1_rr1')/peak('k_vl2_rr1R')
        assert abs(pan_ratio-(.5*.75**.5+.2)/(.5*.25**.5+.2))<.01 and abs(balance-.125/(.5*.75**.5+.2))<.005,(pan_ratio,balance)
        kz,hz=bank['instruments'][0]['zones'],bank['instruments'][1]['zones']
        assert set(kz[0]['mods'])=={(0x0502,48,60,0,0),(0x0102,8,0,0,0),(0x0102,8,0,0x0C02,0)} and not hz[0]['mods']
        assert all(z['gens'].get(57)==1 for z in hz if z['target'] is not None) and not any(57 in z['gens'] for z in kz)
        rr={bank['samples'][z['target']]['name'][:9]:z['gens'][44] for z in kz if z['target'] is not None and z['gens'][44][0] in (65,66)}
        assert rr=={'k_vl2_rr1':(65,65),'k_vl2_rr2':(66,66)},rr
        (root/'kick'/'oh'/'k_vl1_rr2.wav').unlink();rejects(lambda:build(spec,root,work/'kit_missing.sf2'))
        return {'pan_ratio':round(pan_ratio,3),'hat_vs_kick':round(balance,4),'velocity_mods':len(kz[0]['mods'])}
    def loop_build():
        from musiclib import sf2
        from musiclib.loop import write_wav
        from soundbank import build
        root=work/'loop_source';root.mkdir(parents=True,exist_ok=True);rate=48000;t=np.arange(3*rate)/rate
        # Three sustained takes, each looped from 1 s to its end; the middle one was recorded 6 dB hot and every take
        # sags 6 dB over the last 0.4 s of its loop, as a bow easing off.
        for name,f0,amp in (('A3',220.0,.1),('C4',261.63,.2),('D#4',311.13,.1)):
            x=amp*np.where(t<2.6,1,.5)*np.sin(2*np.pi*f0*t);write_wav(root/f'c_{name}.wav',np.repeat(x[:,None],2,1),rate,len(x))
        layer={'dir':'.','template':'c_{note}.wav','dynamics':['default'],'velocity':{'default':[1,127]},'keys':[55,66],
               'loop':'recorded','loop_repair':{'sag_db':1.5,'crossfade':.12},'match_notes':'local',
               'vibrato':{'rate_hz':5.5,'depth_cents':12,'delay_seconds':.35},'velocity_attenuation_cb':300,'velocity_curve':'linear'}
        build({'name':'loops','presets':[{'name':'held','program':42,'layers':[layer]}]},root,work/'loops.sf2');bank=sf2.read(work/'loops.sf2')
        inv=sf2.inventory(bank)[0];zones=bank['instruments'][0]['zones'];glob=zones[0]
        assert inv['looped_zones']==inv['samples']==6 and all(z['gens'].get(54)==1 for z in zones[1:]),inv
        assert {k:glob['gens'][k] for k in (6,23,24)}=={6:12,23:sf2.timecents(.35),24:-686}
        assert set(glob['mods'])=={(0x0502,48,0,0,0),(0x0102,48,300,0,0)},glob['mods']
        # Each loop now ends before the sag, the frames after its end repeat its first ones, and the hot take was evened.
        peaks={}
        for i,s in enumerate(bank['samples']):
            x=sf2.load_sample(bank,i);ls,le=s['loop'][0]-s['start'],s['loop'][1]-s['start'];peaks[s['name']]=float(np.max(np.abs(x[:rate])))
            assert ls==rate and 1.9*rate<le<=2.6*rate and np.allclose(x[le:le+8],x[ls:ls+8],atol=2e-4),(s['name'],ls,le)
        hot=20*np.log10(peaks['c_C4R']/peaks['c_A3R'])
        assert abs(hot)<.2,peaks
        recorded=[round((s['loop'][0]-s['start'])/rate,3),round((s['loop'][1]-s['start'])/rate,3)]
        # A take with no loop of its own and a key noise at 1.9 s: the loop found in it, crossfade included, keeps clear.
        import wave
        y=.1*np.where(t<2.6,1,.5)*np.sin(2*np.pi*329.63*t);y[int(1.9*rate):int(1.905*rate)]+=.5
        (root/'found').mkdir(exist_ok=True);q=np.round(np.repeat(y[:,None],2,1)*32767).astype('<i2')
        with wave.open(str(root/'found'/'f_E4.wav'),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(q.tobytes())
        found={**layer,'dir':'found','template':'f_{note}.wav','keys':[60,70],'loop':'found','loop_window':[.5,600.0],
               'loop_repair':{'sag_db':1.5,'crossfade':.1}}
        build({'name':'found','presets':[{'name':'held','program':42,'layers':[found]}]},root,work/'found.sf2');fb=sf2.read(work/'found.sf2')
        f=fb['samples'][0];ls,le=(f['loop'][0]-f['start'])/rate,(f['loop'][1]-f['start'])/rate
        assert le-ls>=.8 and (ls-.1>1.905 or le<1.9) and all(z['gens'].get(54)==1 for z in fb['instruments'][0]['zones'][1:]),(ls,le)
        return {'loop_seconds':recorded,'hot_take_after_db':round(hot,2),'found_loop_seconds':[round(ls,3),round(le,3)]}
    def across_levels():
        from musiclib import sf2
        from musiclib.loop import write_wav
        from soundbank import build
        root=work/'across_source';root.mkdir(parents=True,exist_ok=True);rate=48000;t=np.arange(int(1.5*rate))/rate
        # Two recorded dynamics on six notes: the loud one even, the soft one 2 dB quieter each note up (a soft layer
        # recorded quieter in the treble).  Local levels keep each layer's own slope, so the velocity split jumps more
        # and more up the keyboard; "across" puts both dynamics of every note at one level.
        notes=('C3','E3','G3','C4','E4','G4')
        for k,(name,f0) in enumerate(zip(notes,(130.81,164.81,196.0,261.63,329.63,392.0))):
            tone=np.exp(-t/.8)*(np.sin(2*np.pi*f0*t)+.3*np.sin(4*np.pi*f0*t))
            for dyn,amp in (('p',.08*10**(-2*k/20)),('f',.3)):write_wav(root/f'a_{name}_{dyn}.wav',(amp*tone)[:,None],rate,len(t))
        steps={}
        for mode in ('local','across'):
            layer={'dir':'.','template':'a_{note}_{dyn}.wav','dynamics':['p','f'],'velocity':{'p':[1,64],'f':[65,127]},
                   'keys':[48,67],'match_notes':mode,'layer_levels_db':{'p':0,'f':0},'match_limit_db':12,'pitch_check':False}
            build({'name':'across','presets':[{'name':'keys','program':0,'layers':[layer]}]},root,work/f'across_{mode}.sf2')
            bank=sf2.read(work/f'across_{mode}.sf2')
            rms={s['name']:20*np.log10(np.sqrt(np.mean(sf2.load_sample(bank,i)[:rate].astype(float)**2))) for i,s in enumerate(bank['samples'])}
            lvl=lambda n,d:next(v for k,v in rms.items() if k.startswith(f'a_{n}_{d}'))
            steps[mode]=[round(lvl(n,'f')-lvl(n,'p'),2) for n in notes]
        assert max(map(abs,steps['across']))<.2 and steps['local'][-1]-steps['local'][0]>4,steps
        return {'split_step_db_local':steps['local'],'split_step_db_across':steps['across']}
    def expressive_bank():
        from musiclib import layered,sf2
        bank,plain=sf2.read(xf_bank()),sf2.read(work/'xf_plain.sf2')
        # Dynamics play a program's recorded layers, which only its bank-0 preset has: review --config and the render
        # name another bank's preset, or a bank without layers, with the programs that have them.
        part=lambda patch:{'id':'v','performance':{'notes':{},'dynamics':[[0,64]]},'patch':patch}
        off=layered.unsupported(part({'bank':1,'program':48}),xf_bank());bare=layered.unsupported(part({'bank':0,'program':48}),work/'xf_plain.sf2')
        assert layered.unsupported(part({'bank':0,'program':48}),xf_bank()) is None
        # A preset the bank lacks is refused before synthesis, with what the bank has: FluidSynth put another in its
        # place, which the render found only after synthesis (found by the stress test of 0.4.0).
        assert 'no preset at bank 1 program 48' in layered.unsupported({**part({'bank':1,'program':48}),'performance':{'notes':{}}},xf_bank())
        assert 'bank 1 program 48' in off and '48 (held)' in off and 'has none' in bare and 'at bank 0: none' in bare,(off,bare)
        assert sorted((x['bank'],x['program']) for x in bank['presets'])==[(0,48),(16,48),(17,48),(32,48),(33,48)]
        # The derived presets reuse the stored takes: the samples are the plain build's, byte for byte.
        assert len(bank['samples'])==len(plain['samples']) and all(sf2.load_sample(bank,i).tobytes()==sf2.load_sample(plain,i).tobytes() for i in range(len(plain['samples'])))
        derived=[i for i in bank['instruments'] if ' d' in i['name'] or ' L' in i['name']]
        assert len(derived)==4 and all(set(i['zones'][0]['mods'])=={(0x0502,48,0,0,0),(0x0102,8,0,0,0),(0x0102,8,0,0x0C02,0)} for i in derived)
        legato=[i for i in derived if ' L' in i['name']];rate=48000
        offsets=[(z['gens'].get(0,0)+32768*z['gens'].get(4,0))/rate for i in legato for z in i['zones'] if z['target'] is not None]
        # The takes reach 2 dB under their steady level at about 0.24 s: legato entries start there (+20 ms).
        assert all(.2<o<.32 for o in offsets) and all(i['zones'][0]['gens'][34]==sf2.timecents(.01) for i in legato),offsets
        return {'presets':len(bank['presets']),'legato_offset_s':[round(min(offsets),3),round(max(offsets),3)]}
    def ring_cut():
        import wave
        from soundbank import build
        from musiclib import sf2
        # Two struck tones that fall 60 dB in 2 s and in 5 s, recorded 8 s long: each is kept to its own ring.
        root=work/'ring_source';root.mkdir(parents=True,exist_ok=True);rate=48000;t=np.arange(8*rate)/rate
        for name,f0,fall in (('C4',261.63,2.0),('G4',392.0,5.0)):
            x=.5*np.sin(2*np.pi*f0*t)*10**(-3*t/fall)
            q=np.clip(np.round(np.repeat(x[:,None],2,1)*32767),-32768,32767).astype('<i2')
            with wave.open(str(root/f'r_{name}_f.wav'),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(q.tobytes())
        layer={'dir':'.','template':'r_{note}_{dyn}.wav','dynamics':['f'],'velocity':{'f':[1,127]},'keys':[55,72],
               'level':'peak','ring_db':-60,'max_seconds':7}
        lengths=lambda bank:sorted(round((x['end']-x['start'])/rate,2) for x in bank['samples'][::2])
        build({'name':'ring','presets':[{'name':'struck','program':0,'layers':[layer]}]},root,work/'ring.sf2')
        free=lengths(sf2.read(work/'ring.sf2'))
        build({'name':'ring','presets':[{'name':'struck','program':0,'layers':[{**layer,'max_seconds':3}]}]},root,work/'ring_capped.sf2')
        capped=lengths(sf2.read(work/'ring_capped.sf2'))
        assert abs(free[0]-2.05)<.15 and abs(free[1]-5.05)<.15 and abs(capped[1]-3)<.05,(free,capped)
        # Two layers of one build that cut the same take otherwise each keep their own cut: the G4 take stays 5 s long
        # in one preset and 3 s in the other (a take loaded once was shared by its file name alone, so the second
        # preset got the first's).  (Found by a review of 0.4.0.)
        both={'name':'ring','presets':[{'name':'struck','program':0,'layers':[layer]},{'name':'capped','program':1,'layers':[{**layer,'max_seconds':3}]}]}
        build(both,root,work/'ring_both.sf2');shared=lengths(sf2.read(work/'ring_both.sf2'))
        assert any(abs(x-3)<.05 for x in shared) and any(abs(x-5.05)<.15 for x in shared),shared
        return {'kept_seconds':free,'capped_at_3s':capped,'one_build_two_cuts':shared}
    def denoise_keeps_each_layers_partials():
        # Two layers that denoise one take but give it different measured pitches keep each its own partials as
        # recorded: the take loaded once was shared by everything but that pitch, so the second layer got the first's
        # cleaning.  (Found by the second review of 0.4.0.)
        import wave
        from soundbank import build
        from musiclib import sf2
        root=work/'partials_source';root.mkdir();rate=48000;t=np.arange(6*rate)/rate;rng=np.random.default_rng(5)
        x=.3*np.exp(-t)*(np.sin(2*np.pi*110*t)+np.sin(2*np.pi*165*t))+.0005*rng.standard_normal(len(t))  # quiet frames over 35 dB under the loud ones, as soundbank.quiet_power needs
        q=np.clip(np.round(np.repeat(x[:,None],2,1)*32767),-32768,32767).astype('<i2')
        with wave.open(str(root/'p_a_f.wav'),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(q.tobytes())
        layer={'dir':'.','template':'p_{id}_{dyn}.wav','dynamics':['f'],'velocity':{'f':[1,127]},'keys':[40,64],'level':'peak',
               'denoise':{'reduce_db':12,'keep_partials_below':300}}
        spec={'name':'partials','presets':[{'name':'on_a','program':0,'layers':[{**layer,'pitches':{'a':45.0}}]},
                                           {'name':'on_e','program':1,'layers':[{**layer,'pitches':{'a':52.0}}]}]}
        build(spec,root,work/'partials.sf2');bank=sf2.read(work/'partials.sf2')
        data=[sf2.load_sample(bank,i).tobytes() for i in range(len(bank['samples']))]
        assert len(data)==4 and set(data[:2]).isdisjoint(data[2:]),len(set(data))  # each layer's two channels, its own cleaning
        return {'samples':len(data),'shared_between_layers':0}
    def aiff(path,x,rate,bits=16):
        """A big-endian PCM AIFF, as the University of Iowa recordings are published."""
        x=np.asarray(x,dtype=np.float64);x=x[:,None] if x.ndim==1 else x;e=int(np.floor(np.log2(rate)))
        q=np.clip(np.round(x*(2**(bits-1)-1)),-2**(bits-1),2**(bits-1)-1).astype(np.int64).ravel()
        data=b''.join(int(v).to_bytes(bits//8,'big',signed=True) for v in q) if bits==24 else q.astype('>i2').tobytes()
        comm=struct.pack('>hIh',x.shape[1],len(x),bits)+struct.pack('>HQ',16383+e,int(rate)<<(63-e))
        body=b'AIFF'+b'COMM'+struct.pack('>I',18)+comm+b'SSND'+struct.pack('>I',8+len(data))+b'\0'*8+data
        Path(path).write_bytes(b'FORM'+struct.pack('>I',len(body))+body)
    def chromatic_run():
        """Six notes C4-F4 played one at a time as a sample library records them: D4 twice (first 45 cents flat), a
        breath between C#4 and D4, E4 slurred into F4 with no gap."""
        rate=44100;rng=np.random.default_rng(7);parts=[];truth=[]
        def tone(midi,cents,sec):
            t=np.arange(int(sec*rate))/rate;f=440*2**((midi+cents/100-69)/12)
            y=sum(np.sin(2*np.pi*k*f*t)/k for k in range(1,9))*.15
            env=np.minimum(1,t/.02)*np.minimum(1,(t[-1]-t)/.05);return y*env
        gap=lambda sec:np.zeros(int(sec*rate))
        for midi,cents,lead in ((60,8,.3),(61,-12,.15),(62,-45,.6),(62,4,.15),(63,0,.15)):
            parts.append(gap(lead))
            if midi==62 and cents==-45:  # the breath sits in the middle of the gap before the flat take
                parts[-1][int(.2*rate):int(.4*rate)]=rng.normal(0,.01,int(.2*rate))
            truth.append((midi,cents,sum(map(len,parts))/rate));parts.append(tone(midi,cents,1.2))
        parts.append(gap(.15));truth.append((64,-5,sum(map(len,parts))/rate))
        t=np.arange(int(2.4*rate))/rate;f=np.where(t<1.2,440*2**((64-.05-69)/12),440*2**((65+.1-69)/12))
        ph=2*np.pi*np.cumsum(f)/rate;y=sum(np.sin(k*ph)/k for k in range(1,9))*.15*np.minimum(1,t/.02)*np.minimum(1,(t[-1]-t)/.05)
        parts.append(y);truth.append((65,10,truth[-1][2]+1.2));parts.append(gap(.3))
        return np.concatenate(parts),rate,[x for x in truth if not (x[0]==62 and x[1]==-45)]
    def split_run():
        from soundbank import split_sources,read_audio
        root=work/'split_source';root.mkdir(parents=True,exist_ok=True);x,rate,truth=chromatic_run()
        aiff(root/'T.mf.C4F4.aiff',x,rate);aiff(root/'T24.aiff',np.stack([x,-x],1),rate,24)
        a,ia=read_audio(root/'T.mf.C4F4.aiff');b,ib=read_audio(root/'T24.aiff')
        assert ia['rate']==ib['rate']==rate and ib['channels']==2 and np.abs(a[:,0]-b[:,0]).max()<1e-4 and np.abs(b[:,0]+b[:,1]).max()<1e-6
        group={'name':'T','files':[{'file':'T.mf.C4F4.aiff','dyn':'mf','notes':['C4','F4']}]}
        m=split_sources({'groups':[group]},root,work/'split_notes');save_json(work/'split_notes'/'split.json',m)
        got=[(n['file'],n['cents'],n['start']/rate) for n in m['notes']]
        names=[f'T/T_mf_{k}.wav' for k in ('C4','C#4','D4','D#4','E4','F4')]
        assert [g[0] for g in got]==names,got
        by={g[0]:g for g in got}
        for midi,cents,start in truth:
            g=by[f'T/T_mf_{["C","C#","D","D#","E","F"][midi-60]}4.wav']
            assert abs(g[1]-cents)<4 and -.03<start-g[2]<.03,(midi,g,cents,start)
        # The retake replaced the flat D4, and no cut reaches into the breath (0.2-0.4 s into the gap before it).
        breath=(truth[1][2]+1.2+.2,truth[1][2]+1.2+.4)
        assert all(n['end']/rate<=breath[0] or n['start']/rate>=breath[1] for n in m['notes'])
        lacking={'name':'T','files':[{'file':'T.mf.C4F4.aiff','dyn':'mf','notes':['C4','F#4']}]}
        rejects(lambda:split_sources({'groups':[lacking]},root,work/'split_lacking'))
        partial=split_sources({'groups':[{**lacking,'partial':True}]},root,work/'split_partial')
        assert partial['sources'][0]['missing']==['F#4'] and len(partial['notes'])==6
        # A label that becomes part of a note file's name (a group's name, a dynamic, an `out` name) is one name of
        # portable characters: a path in one wrote the note outside the output, over a file that was there.  Two notes
        # never take one name.  (GPT's security audit of 0.5, S02.)
        victim=work/'split_victim_x.wav';victim.write_bytes(b'not the splitter');whole={'file':'T.mf.C4F4.aiff','whole':True,'pitch':False}
        for k,(name,dyn,out) in enumerate((('T','/../../split_victim','x'),('T','mf','/../split_victim_x'),('../T','mf','x'),('T/U','mf','x'),('T','m:f','x'),
                                           ('CON','mf','x'),('T','..','x'),('T','mf','x.'),('T',5,'x'),('T','-mf','x'),('T','mf','x'*65))):
            try:split_sources({'groups':[{'name':name,'files':[{**whole,'dyn':dyn,'out':out}]}]},root,work/f'split_label_{k}');raise AssertionError((name,dyn,out))
            except ValueError as e:assert 'a name of letters' in str(e),e
        assert victim.read_bytes()==b'not the splitter'
        try:split_sources({'groups':[{'name':'T','files':[{**whole,'dyn':'mf','out':'x'}]}]*2},root,work/'split_twice');raise AssertionError('one note written over another')
        except ValueError as e:assert 'two notes' in str(e),e
        plain=split_sources({'groups':[{'name':'T.1_a-b','files':[{**whole,'dyn':'mf','out':'Tam-Tam_40.x'}]}]},root,work/'split_labels_kept')
        assert plain['notes'][0]['file']=='T.1_a-b/T.1_a-b_mf_Tam-Tam_40.x.wav' and (work/'split_labels_kept'/plain['notes'][0]['file']).is_file()
        # An AIFF's sample rate is held to the range a WAV's is (wavfile.info): the header's number sized working
        # arrays whatever it claimed, and the format's infinity stopped the reader with OverflowError (S06).
        def odd_rate(exponent,mantissa):
            comm=struct.pack('>hIh',1,10,16)+struct.pack('>HQ',exponent,mantissa);body=b'AIFF'+b'COMM'+struct.pack('>I',18)+comm+b'SSND'+struct.pack('>I',28)+bytes(28)
            (work/'odd_rate.aiff').write_bytes(b'FORM'+struct.pack('>I',len(body))+body);return work/'odd_rate.aiff'
        for exponent,mantissa in ((16383+39,1<<63),(0x7FFF,1<<63),(16383+12,1<<63),(0,0)):  # 2**39 Hz, infinity, 4096 Hz, 0
            try:read_audio(odd_rate(exponent,mantissa));raise AssertionError((exponent,mantissa))
            except ValueError as e:assert 'unsupported AIFF' in str(e),e
        return {'notes':len(m['notes']),'cents':{g[0][7:-4]:g[1] for g in got}}
    def split_highpass():
        from soundbank import split_sources,highpass,spectral_pitch,read_audio
        rate=44100;t=np.arange(rate)/rate;mid=slice(rate//4,-rate//4)
        # The zero-phase high-pass: -3 dB at its cutoff, about -36 dB an octave under it (order 6), flat at four times
        # it, and a click left where it was.
        gain=lambda f:20*np.log10(np.std(highpass(np.sin(2*np.pi*f*t),rate,100)[mid])/np.std(np.sin(2*np.pi*f*t)[mid]))
        g=[round(gain(f),2) for f in (50,100,400)]
        assert abs(g[0]+36.1)<1 and abs(g[1]+3.01)<.3 and abs(g[2])<.05,g
        click=np.zeros(rate);click[rate//2]=1
        assert int(np.argmax(np.abs(highpass(click,rate,100))))==rate//2
        # The chromatic run under a 60 Hz hum about 5 dB under its notes, so the gaps are never quiet: the split reads a
        # copy high-passed at 120 Hz (the hum 41 dB under the notes there), cuts the notes from the recording as it is
        # (the hum still in them), and drops the take named in leave_out.
        root=work/'split_source';x,_,truth=chromatic_run()
        aiff(root/'H.mf.C4F4.aiff',x+.1*np.sin(2*np.pi*60*np.arange(len(x))/rate),rate)
        group={'name':'H','files':[{'file':'H.mf.C4F4.aiff','dyn':'mf','notes':['C4','F4'],'analysis_highpass_hz':120}],
               'leave_out':[{'dyn':'mf','note':'D#4','why':'a take judged unusable'}]}
        m=split_sources({'groups':[group]},root,work/'split_hum')
        got={n['file'].split('_')[-1][:-4]:n for n in m['notes']}
        assert sorted(got)==sorted(['C4','C#4','D4','E4','F4']) and m['sources'][0]['analysis_highpass_hz']==120,(sorted(got),m['sources'])
        for midi,cents,start in truth:
            name=['C','C#','D','D#','E','F'][midi-60]+'4'
            if name in got:
                assert abs(got[name]['cents']-cents)<4 and -.03<start-got[name]['start']/rate<.03,(name,got[name],cents,start)
        y,_=read_audio(work/'split_hum'/got['C4']['file']);y=np.asarray(y,dtype=np.float64).reshape(len(y),-1)[:,0]
        n=np.arange(len(y))/rate;hum=float(2*abs(np.mean(y*np.exp(-2j*np.pi*60*n))))   # the 60 Hz amplitude in the cut
        assert .07<hum<.13,hum
        # Tuning from the spectrum: an A4 played 20 cents flat reads -20 cents.
        f=spectral_pitch(np.sin(2*np.pi*440*2**(-20/1200)*t)*.3,rate,69,(.2,.9))
        cents=1200*np.log2(f/440);assert abs(cents+20)<1,cents
        return {'gain_db_at_50_100_400_hz':g,'notes':len(got),'hum_in_cut':round(hum,3),'spectral_cents':round(float(cents),2)}
    def soft_take_from_the_loud_one():
        # `soft_from` (0.7): a soft dynamic whose recording stands little over its own noise is made from the louder
        # take of the same key.  Known answers on a made-up key: twenty partials that decay as a string's do, a loud
        # take, and a soft take whose partials are 3 dB lower for each one up, under hiss 30 dB louder than the loud
        # take's.  The curve read from the two must be that fall; the take made from it must hold the soft take's
        # partials, its level, and the loud take's hiss lowered, not the soft take's.  The lowest keys once never
        # ended: at 29 Hz between partials the search window reached back to the partial before.
        from soundbank import soft_curve,soft_from_loud,SOFT_PARTIALS
        rate,f0,n=44100,220.0,3*44100
        t=np.arange(n)/rate
        rng=np.random.default_rng(7)
        def take(fall_db,noise_db):
            x=sum(10**((-2.0*k-fall_db*k)/20)*np.exp(-t*(1.0+0.5*k))*np.sin(2*np.pi*f0*(k+1)*np.sqrt(1+0.0004*(k+1)**2)*t) for k in range(20))
            x=np.concatenate([np.zeros(200),x])[:n]*0.25+10**(noise_db/20)*rng.standard_normal(n)
            return np.stack([x,x],axis=1).astype(np.float32)
        loud,soft=take(0.0,-90.0),take(3.0,-60.0)
        c=soft_curve(soft,loud,rate,f0)
        assert c['clear']>=SOFT_PARTIALS,c['clear']
        fall=[c['db'][k]-c['db'][0] for k in range(min(5,c['clear']))]
        assert all(abs(got+3.0*k)<1.0 for k,got in enumerate(fall)),fall          # 3 dB a partial, within 1 dB
        assert c['slope']<0 and abs(c['hz'][0]-f0)<3,(c['slope'],c['hz'][0])
        made=soft_from_loud(soft,loud,rate,c)
        assert made.shape==loud.shape and made.dtype==np.float32
        early=lambda z:float(np.sqrt(np.mean(z[200:200+int(0.3*rate)].astype(np.float64)**2)))
        assert abs(20*np.log10(early(made)/early(soft)))<0.1                        # the soft take's level
        def band(z,lo,hi):
            w=np.hanning(n);p=np.abs(np.fft.rfft(z[:,0]*w))**2;f=np.fft.rfftfreq(n,1/rate)
            return 10*np.log10(p[(f>=lo)&(f<hi)].sum()+1e-30)
        hiss=lambda z:band(z,12000,18000)                                           # no partial of this key lies there
        assert hiss(made)<hiss(soft)-20,(hiss(made),hiss(soft))                     # the loud take's hiss, lowered
        for k in (0,2,4):                                                           # each partial where the soft blow put it
            lo,hi=f0*(k+1)*0.97,f0*(k+1)*1.04
            assert abs(band(made,lo,hi)-band(soft,lo,hi))<1.5,(k,band(made,lo,hi),band(soft,lo,hi))
        low=soft_curve(take(3.0,-60.0),take(0.0,-90.0),rate,29.14)                 # ends, whatever it reads
        assert low is None or isinstance(low['clear'],int)
        quiet=soft_curve((soft*0+1e-4*rng.standard_normal(soft.shape)).astype(np.float32),loud,rate,f0)
        assert quiet['clear']<SOFT_PARTIALS,quiet                                    # noise alone shows no partials
        return {'clear':c['clear'],'fall_db':[round(v,2) for v in fall],'slope':round(c['slope'],1)}
    def settled_bands_are_closed_once():
        # `close_hiss` (0.7): a band of a take that has come down to the recording's hiss is taken out from then on,
        # once.  Known answers on a made-up take: two low partials that ring for seconds, one at 5 kHz gone within half
        # a second, steady hiss, and a publisher's fade over the second half, which lowers every band alike.  The bands
        # of the ringing partials stay as recorded, the 5 kHz band closes after its partial and not before, the bands
        # above close at once, nothing under 1 kHz moves, and the hiss is gone from the later part.
        from soundbank import close_settled_bands
        rate,n=48000,6*48000
        t=np.arange(n)/rate
        rng=np.random.default_rng(11)
        tone=0.3*np.exp(-t*0.6)*np.sin(2*np.pi*440*t)+0.1*np.exp(-t*0.9)*np.sin(2*np.pi*1500*t)+0.05*np.exp(-t*12)*np.sin(2*np.pi*5000*t)
        fade=np.where(t<3,1.0,10**(-(t-3)*4/20))                      # 4 dB a second from the third second
        x=((tone+10**(-70/20)*rng.standard_normal(n))*fade)
        x=np.concatenate([np.zeros(300),x])[:n]
        x=np.stack([x,x],axis=1).astype(np.float32)
        y,report=close_settled_bands(x,rate)
        got={r['band'][0]:r for r in report}
        assert y.shape==x.shape and y.dtype==x.dtype
        assert 'left' in got[1000] and 'left' in got[1414],report      # the 1.5 kHz partial still rings there
        five=got[4000]                                                 # 4000-5657 Hz holds the 5 kHz partial
        assert 'closed_s' in five and 0.15<five['closed_s']<1.2,five    # after the partial has gone (it is 6 dB over the hiss at about 0.3 s)
        assert all('closed_s' in got[b] and got[b]['closed_s']<0.3 for b in got if b>=8000),report
        # No band closes through the blow: nothing is touched in the first 0.05 s after the onset, though the bands
        # over 8 kHz read as settled from the first frame (their levels are read over 0.1 s, the blow's top lasts
        # less; the first Osiris and guitar builds lost up to 9 dB above 8 kHz in a note's first 30 ms).
        assert all(got[b]['closed_s']>=0.06 for b in got if 'closed_s' in got[b]),report
        assert np.array_equal(y[:300+int(0.05*rate)],x[:300+int(0.05*rate)])
        z,_=close_settled_bands(x,rate,not_before_s=0.0);assert not np.array_equal(z[:300+int(0.05*rate)],x[:300+int(0.05*rate)])
        def band(z,lo,hi,a,b):
            seg=z[int(a*rate):int(b*rate),0].astype(np.float64);w=np.hanning(len(seg))
            p=np.abs(np.fft.rfft(seg*w))**2;f=np.fft.rfftfreq(len(seg),1/rate)
            return 10*np.log10(p[(f>=lo)&(f<hi)].sum()+1e-30)
        assert band(y,8000,20000,1.5,2.5)<band(x,8000,20000,1.5,2.5)-30                 # the hiss, gone
        assert abs(band(y,4800,5200,0.01,0.12)-band(x,4800,5200,0.01,0.12))<1.0           # the blow's own 5 kHz, kept
        assert abs(band(y,300,900,0.0,5.0)-band(x,300,900,0.0,5.0))<0.01                  # nothing under 1 kHz moves
        assert abs(band(y,1400,1600,0.0,5.0)-band(x,1400,1600,0.0,5.0))<0.05              # nor a band that was left
        short,rep=close_settled_bands(x[:rate],rate);assert np.array_equal(short,x[:rate]) and 'left' in rep[0]
        # A take that begins with a knock and sounds its note 0.4 s later reads as settled in between; closing its
        # bands there would take the note's own top, so the take stays as recorded and says why (the nylon guitar's
        # soft D sharp 3 lost 1.6 dB of its peak that way in a trial build).
        late=np.concatenate([np.zeros(300),0.12*np.exp(-np.arange(960)/96)*np.sin(2*np.pi*3000*np.arange(960)/rate),np.zeros(int(0.4*rate)),
                             0.3*(np.exp(-t*0.6)*np.sin(2*np.pi*440*t)+np.exp(-t*12)*np.sin(2*np.pi*2500*t))])[:n]+10**(-70/20)*rng.standard_normal(n)
        late=np.stack([late,late],axis=1).astype(np.float32)
        # Since the take is read for partials (the review of 0.7's code, F01), the bands the late note's 2.5 kHz
        # reaches wait for it and close after it: the note keeps its top and the take loses its hiss.  The guard is
        # what is left where that reading finds nothing, shown here with the reading switched off.
        import soundbank
        kept,rep=close_settled_bands(late,rate);waited={r['band'][0]:r for r in rep}
        assert waited[2000].get('after_a_partial') and waited[2000]['closed_s']>0.7,rep
        assert abs(band(kept,2300,2700,0.42,0.7)-band(late,2300,2700,0.42,0.7))<0.2 and band(kept,8000,20000,2,4)<band(late,8000,20000,2,4)-30
        share,soundbank.CLOSE_NARROW_SHARE=soundbank.CLOSE_NARROW_SHARE,9.0
        try:kept,rep=close_settled_bands(late,rate)
        finally:soundbank.CLOSE_NARROW_SHARE=share
        assert np.array_equal(kept,late) and 'more than hiss' in rep[0].get('left',''),rep
        return {'closed':{b:got[b].get('closed_s') for b in sorted(got)}}
    def full_scale_keeps_the_level():
        # `full_scale` (0.7): a take is stored as loud as 16 bits hold and its zone attenuates it by as much, so the
        # level heard is the one it had and the dither lies that much lower under the note.  Two small banks from the
        # same two takes, one built with it: every stored sample then peaks at full scale, give or take one step of
        # attenuation, and its peak less its zone's attenuation is the peak the plain build stored; a bank without the
        # option is bit for bit what it was (the Osiris, rebuilt with this code, kept its file hash).
        from musiclib import sf2
        from musiclib.loop import write_wav
        from soundbank import build
        root=work/'full_scale_source';root.mkdir(parents=True,exist_ok=True);rate=48000;t=np.arange(2*rate)/rate
        for name,f0,amp in (('A3',220.0,.5),('C4',261.63,.03)):
            x=amp*np.exp(-t*2)*np.sin(2*np.pi*f0*t);write_wav(root/f'p_{name}.wav',np.repeat(x[:,None],2,1),rate,len(x))
        layer={'dir':'.','template':'p_{note}.wav','dynamics':['default'],'velocity':{'default':[1,127]},'keys':[55,62],
               'pitch_check':False}
        def made(name,extra):
            build({'name':name,'target_rms':0.05,'presets':[{'name':'p','program':0,'layers':[{**layer,**extra}]}]},root,work/f'{name}.sf2')   # under the 36 dB the lift stops at
            bank=sf2.read(work/f'{name}.sf2');out={}
            for z in bank['instruments'][0]['zones'][1:]:
                i=z['gens'][53];out[bank['samples'][i]['name']]=(float(np.max(np.abs(sf2.load_sample(bank,i)))),z['gens'].get(48,0)*sf2.EMU_ATTENUATION/10)
            return out
        plain,full=made('plain',{}),made('full',{'full_scale':True})
        assert set(plain)==set(full) and len(plain)==4,(sorted(plain),sorted(full))
        lifts={}
        for name in plain:
            (p0,a0),(p1,a1)=plain[name],full[name]
            assert a0==0 and p0<0.5,(name,p0,a0)                                   # stored under full scale, no attenuation
            assert 0.98*10**(-0.05/20)<=p1<=0.981,(name,p1)                        # as loud as 16 bits hold
            assert abs(20*np.log10(p1/p0)-a1)<0.02,(name,p0,p1,a1)                 # and attenuated by as much
            lifts[name]=round(a1,2)
        assert all(v>3 for v in lifts.values()),lifts                               # each take had room to be raised
        return {'stored_lift_db':lifts}
    def split_bank():
        from soundbank import build
        from musiclib import sf2
        root=work/'split_notes';manifest=json.loads((root/'split.json').read_text(encoding='utf-8'))
        layer={'dir':'T','template':'T_{dyn}_{note}.wav','dynamics':['pp','mf'],'velocity':{'pp':[1,63],'mf':[64,127]},
               'keys':[60,65],'pitch_source':'split','max_correction_cents':100,'layer_levels_db':{'pp':-10,'mf':0},'borrowed_level':'served'}
        build({'name':'split','presets':[{'name':'t','program':0,'layers':[layer]}]},root,work/'split.sf2');bank=sf2.read(work/'split.sf2')
        # With denoise too, as the Iowa banks build from their sources: the manifest's noise is read (a local name hid
        # the files module, and every such build stopped; found by GPT Pro's fourth review of 0.4.0).
        denoised=build({'name':'split','presets':[{'name':'t','program':0,'layers':[{**layer,'denoise':{'reduce_db':12}}]}]},root,work/'split_denoised.sf2')
        assert sf2.read(work/'split_denoised.sf2')['presets']
        # Each take records the noise it was cleaned of, measured in its own recording (one here, so one measure for
        # all), and the round robin it was given (1: the pattern names none).  A mutant that left the measure out lived
        # through every check (0.8's mutation analysis, 2026-11-15).
        rows=denoised['files'];noise={r.get('denoised_noise_dbfs') for r in rows}
        assert rows and all(r.get('noise_measured_from')=='recording' and r['round_robin']=='1' for r in rows),[(r['file'],r.get('noise_measured_from'),r['round_robin']) for r in rows]
        assert len(noise)==1 and isinstance(min(noise,key=str),float) and -140<min(noise,key=str)<0,noise
        zones=[z for z in bank['instruments'][0]['zones'] if z['target'] is not None]
        cents={n['file'].split('_')[-1][:-4]:n['cents'] for n in manifest['notes']}
        names=['C4','C#4','D4','D#4','E4','F4']
        for z in zones:
            note=names[z['gens'][58]-60]
            assert z['gens'].get(52,0)==-round(cents[note]),(note,z['gens'])
            # 10 dB quieter as heard: FluidSynth applies the generator at 0.4 of its centibels, so 250 is written.
            assert z['gens'].get(48,0)==(250 if z['gens'][44][1]<=63 else 0),z['gens']
        # Tuning from the spectrum, through the build: one take of an A4 played 30 cents flat for a second and 30 cents
        # sharp the next, read by two presets over their own windows, keeps each preset's tuning in either order (the
        # takes are shared between layers, a pitch is not); and a 150 ms A4 ends before the default window, so it is
        # left as it is rather than pulled toward the band's edge.
        rate=44100;tt=np.arange(2*rate)/rate
        for d in ('S','Q'):(work/'spec_notes'/d).mkdir(parents=True,exist_ok=True)
        aiff(work/'spec_notes'/'S'/'S_mf_A4.aiff',.3*np.sin(2*np.pi*np.cumsum(np.where(tt<1,440*2**(-30/1200),440*2**(30/1200)))/rate),rate)
        aiff(work/'spec_notes'/'Q'/'Q_mf_A4.aiff',.3*np.sin(2*np.pi*440*np.arange(int(.15*rate))/rate),rate)
        def spec_layer(folder,window=None):
            return {'dir':folder,'template':folder+'_{dyn}_{note}.aiff','dynamics':['mf'],'velocity':{'mf':[1,127]},
                    'keys':[69,69],'pitch_source':'spectrum','max_correction_cents':100,**({'spectrum_window':window} if window else {})}
        def tunes(path):
            bank=sf2.read(path);return {p['name']:[z['gens'].get(52,0) for z in bank['instruments'][p['zones'][0]['gens'][41]]['zones'] if z['target'] is not None] for p in bank['presets']}
        early={'name':'early','program':0,'layers':[spec_layer('S',[.2,.8])]};late={'name':'late','program':1,'layers':[spec_layer('S',[1.2,1.8])]}
        for order,name in (([early,late],'early_first'),([late,early],'late_first')):
            build({'name':name,'presets':order},work/'spec_notes',work/f'{name}.sf2')
            assert tunes(work/f'{name}.sf2')=={'early':[30],'late':[-30]},(name,tunes(work/f'{name}.sf2'))
        build({'name':'short','presets':[{'name':'short','program':0,'layers':[spec_layer('Q')]}]},work/'spec_notes',work/'short.sf2')
        assert tunes(work/'short.sf2')=={'short':[0]},tunes(work/'short.sf2')
        return {'zones':len(zones),'borrowed_attenuation_heard_cb':100,'written_cb':250,'spectrum_fine_tunes':{'early':30,'late':-30,'short':0}}
    def noise_reduction():
        import soundbank as sbk
        rate=44100;rng=np.random.default_rng(7);t=np.arange(rate*4)/rate
        note=sum(.3/k*np.sin(2*np.pi*220*k*t) for k in range(1,15))*((t>1)&(t<3))*np.clip((t-1)/.02,0,1)
        x=(note+rng.standard_normal(len(t))*10**(-50/20))[:,None].astype(np.float32)
        y=sbk.denoise(x,sbk.quiet_power(x).mean(axis=0),12)[:,0].astype(float);x=x[:,0].astype(float)
        db=lambda v:20*np.log10(np.sqrt(np.mean(v**2))+1e-30);sil=slice(int(.2*rate),int(.9*rate));mid=slice(int(1.5*rate),int(2.5*rate))
        flick=lambda v:float((10*np.log10((np.lib.stride_tricks.sliding_window_view(v,1024)[::512]**2).mean(axis=1))).std())
        # The hiss between notes falls by the 12 dB asked for, the note keeps its level, and what is left of the
        # noise stays steady instead of flickering into 'musical noise'.
        assert 10.5<db(x[sil])-db(y[sil])<13.5 and abs(db(y[mid])-db(x[mid]))<.1 and flick(y[sil])<flick(x[sil])+.3,(db(x[sil])-db(y[sil]),db(y[mid])-db(x[mid]))
        same=sbk.denoise(x[:,None].astype(np.float32),np.full(sbk.DENOISE_FRAME//2+1,1e-20),12)[:,0]
        assert np.abs(same-x).max()<1e-6
        return {'hiss_reduction_db':round(db(x[sil])-db(y[sil]),1),'note_change_db':round(db(y[mid])-db(x[mid]),3)}
    def click_repair():
        import soundbank as sbk
        rate=48000;rng=np.random.default_rng(11);n=int(rate*2.5);t=np.arange(n)/rate
        # A ringing G3 with a little hiss and a 4 ms knock 0.9 s in: the knock is found and taken out, the partials
        # keep their level through it, and nothing outside the repaired frames moves.  A low string whose sound
        # pulses once a period (A0, every 36 ms) is left alone.
        tone=sum(.2/k*np.sin(2*np.pi*196*k*t)*np.exp(-t*(.6+.15*k)) for k in range(1,13))+rng.standard_normal(n)*1e-4
        clean=np.stack([tone,.9*tone],axis=1).astype(np.float32);x=clean.copy();at=int(.9*rate)
        x[at:at+192]+=(rng.standard_normal((192,2))*.02).astype(np.float32)
        spans=sbk.find_clicks(x,rate);y=sbk.declick(x,rate,spans)
        fs=np.fft.rfftfreq(2048,1/rate)
        band=lambda v,lo,hi:10*np.log10((np.abs(np.fft.rfft(v[at-480:at+1568].astype(float).mean(axis=1)*np.hanning(2048)))**2)[(fs>=lo)&(fs<hi)].sum())
        knock,left,partials=band(x,3000,12000)-band(clean,3000,12000),band(y,3000,12000)-band(clean,3000,12000),band(y,150,2500)-band(clean,150,2500)
        a,b=spans[0][0]-sbk.CLICK_FRAME,spans[0][1]+sbk.CLICK_FRAME
        assert len(spans)==1 and spans[0][0]<=at<=spans[0][1] and knock>20 and left<2 and abs(partials)<.2,(spans,knock,left,partials)
        assert np.array_equal(y[:a],x[:a]) and np.array_equal(y[b:],x[b:])
        pulses=np.zeros(n);burst=rng.standard_normal(48)*np.hanning(48)
        for k in range(0,n-48,int(rate/27.5)):pulses[k:k+48]+=burst*np.exp(-k/rate*1.5)
        low=sum(.1/k*np.sin(2*np.pi*27.5*k*t) for k in range(1,30))*np.exp(-t*.5)+.05*pulses
        assert sbk.find_clicks(np.stack([low,low],axis=1).astype(np.float32),rate)==[]
        return {'knock_db':round(knock,1),'after_repair_db':round(left,1),'partials_change_db':round(partials,3)}
    def denoise_keeps_low_partials():
        import soundbank as sbk
        rate=44100;rng=np.random.default_rng(5);n=rate*4;t=np.arange(n)/rate;f=np.fft.rfftfreq(n,1/rate)
        # Rumble falling 6 dB an octave from 20 Hz, as loud at 82 Hz as the fundamental of a soft E2 played over it
        # from the second second: the gain alone takes the fundamental for rumble; told the note's pitch, it keeps the
        # partials under 300 Hz as recorded while the rumble under the note still falls.
        rumble=np.fft.irfft(np.fft.rfft(rng.standard_normal(n))*20/np.maximum(f,20),n)*.02
        noise=sbk.bands_to_bins(sbk.noise_bands(rumble[:rate,None].astype(np.float32),rate,[]),rate)
        f0=440*2**((40-69)/12);fb=np.fft.rfftfreq(sbk.DENOISE_FRAME,1/rate)
        a=np.sqrt(noise[np.argmin(np.abs(fb-f0))])/(np.sqrt(np.hanning(sbk.DENOISE_FRAME+1)[:-1]).sum()/2)
        x=(rumble+(t>=1)*sum(a/k*np.sin(2*np.pi*f0*k*t) for k in range(1,13)))[:,None].astype(np.float32)
        kept=sbk.denoise(x,noise,12,keep=sbk.partial_bins(40,300,rate))[:,0];plain=sbk.denoise(x,noise,12)[:,0]
        seg=slice(int(1.5*rate),int(3.5*rate));fs=np.fft.rfftfreq(seg.stop-seg.start,1/rate)
        band=lambda v,lo,hi:10*np.log10((np.abs(np.fft.rfft(v[seg]*np.hanning(seg.stop-seg.start)))**2)[(fs>=lo)&(fs<hi)].sum())
        raw=x[:,0].astype(float);fund=lambda v:band(v,f0-3,f0+3)
        keep_db,plain_db,low_db=fund(kept)-fund(raw),fund(plain)-fund(raw),band(raw,25,55)-band(kept,25,55)
        assert abs(keep_db)<.5 and plain_db<-2 and low_db>6,(keep_db,plain_db,low_db)
        return {'fundamental_change_db':round(keep_db,2),'without_its_pitch_db':round(plain_db,1),'rumble_under_note_reduction_db':round(low_db,1)}
    def noise_profile():
        import soundbank as sbk
        rate=44100;rng=np.random.default_rng(11)
        starts=[.2+k*2.5 for k in range(10)];n=int((starts[-1]+1.8)*rate);t=np.arange(n)/rate
        hiss=rng.standard_normal((n,2))*10**(-60/20);x=hiss.copy();notes=[]
        for k,a in enumerate(starts):
            b=a+1.5;notes.append({'start':int(a*rate),'end':int(b*rate)})
            x+=((t>=a)&(t<b))[:,None]*.2*np.sin(2*np.pi*220*2**(k/12)*t)[:,None]
            if k<9:
                # A publisher's gate leaves digital silence in the middle of each pause, and three notes have a breath
                # before them: only short open stretches next to the notes hold the noise.
                g=int(b*rate);x[g+int(.25*rate):g+int(.75*rate)]=0
                if k%3==0:x[g+int(.8*rate):g+int(.95*rate)]+=rng.standard_normal((int(.95*rate)-int(.8*rate),2))*10**(-35/20)
        truth=sbk.noise_bands(hiss.astype(np.float32),rate,[]);got=sbk.noise_bands(x.astype(np.float32),rate,notes)
        level=lambda b:10*np.log10(sbk.bands_to_bins(b,rate).sum())
        assert got is not None,'no profile'
        err=abs(level(got)-level(truth));band=float(np.median(np.abs(np.subtract(got,truth))))
        assert err<.5 and band<.75,(err,band)
        return {'level_error_db':round(err,2),'median_band_error_db':round(band,2)}
    def split_ignores_faint_rings():
        import soundbank as sbk
        rate=44100;t=np.arange(int(13*rate))/rate;rng=np.random.default_rng(3)
        def tone(midi,a,b,db):
            env=((t>=a)&(t<b))*np.clip((t-a)/.03,0,1)*np.clip((b-t)/.05,0,1)
            return 10**(db/20)*env*sum(np.sin(2*np.pi*440*2**((midi-69)/12)*k*t)/k for k in range(1,6))
        # A bowed A#3 played 35 cents sharp, then, seconds later, its faint ring 40 dB down and in tune: the run keeps
        # the bowed note, where the better-tuned ring used to win.
        x=tone(57,.5,1.6,-12)+tone(58.35,3.5,4.7,-12)+tone(58,6.5,9.5,-52)+tone(59,11,12.2,-12)+rng.standard_normal(len(t))*10**(-70/20)
        found,_=sbk.align_run(x[:,None],rate,[57,58,59])
        starts=[round(n['start']/rate,1) for n in found]
        assert starts==[.5,3.5,11.0],starts
        return {'starts_s':starts}
    def files_stay_inside():
        from soundbank import cut_sources
        root=work/'cut_check';src=root/'src';src.mkdir(parents=True,exist_ok=True);victim=root/'victim.txt';victim.write_text('keep',encoding='utf-8')
        audio.write_wav(src/'s.wav',np.zeros((16,2),dtype=np.float32))
        bad={'groups':[],'sources':[],'notes':[{'source':'s.wav','file':'../victim.txt','start':0,'end':8,'fade':0,'sha256':'0'*64}]}
        rejects(lambda:cut_sources(bad,src,root/'out'))
        bad['notes'][0]['file']=str(victim.resolve());rejects(lambda:cut_sources(bad,src,root/'out'))
        assert victim.read_text(encoding='utf-8')=='keep'
        # A note cut from a changed recording does not match its hash: no note of the run is kept (the one that matched
        # is taken out again), the command says why with no traceback, and its folder is gone; a bank build whose
        # receipt would replace the bank is refused before it starts.  (Found by a review of 0.4.0.)
        import subprocess,sys
        from soundbank import _cut_note,read_audio
        from musiclib import files as owned
        rate=audio.RATE;audio.write_wav(src/'take.wav',(np.sin(2*np.pi*220*np.arange(rate)/rate)*.5).astype(np.float32)[:,None].repeat(2,axis=1))
        x,info=read_audio(src/'take.wav');x=np.asarray(x,dtype=np.float32);good={'groups':[],'sources':[{'file':'take.wav'}],'notes':[]}
        for k,(a,b) in enumerate(((0,rate//4),(rate//4,rate//2))):
            good['notes'].append({'source':'take.wav','file':f'n{k}.wav','start':a,'end':b,'fade':0,'sha256':_cut_note(x,a,b,0,info['rate'],root/f'probe{k}.wav')})
        assert cut_sources(good,src,root/'ok')==2 and sorted(p.name for p in (root/'ok').iterdir())==['n0.wav','n1.wav']
        y=x.copy();y[rate//4:]*=.5;audio.write_wav(src/'take.wav',y)
        rejects(lambda:cut_sources(good,src,root/'changed'));assert not owned.occupied(root/'changed')
        save_json(root/'manifest.json',good);script=str(SCRIPTS.joinpath('soundbank.py'))
        r=subprocess.run([sys.executable,script,'cut',str(root/'manifest.json'),'--root',str(src),'--output',str(root/'cli')],capture_output=True,text=True,timeout=120)
        assert r.returncode==2 and 'does not reproduce' in r.stderr and 'Traceback' not in r.stderr and not owned.occupied(root/'cli'),(r.returncode,r.stderr[-400:])
        r=subprocess.run([sys.executable,script,'build',str(root/'manifest.json'),'--root',str(src),'--output',str(root/'same.sf2'),'--receipt',str(root/'.'/'same.sf2')],capture_output=True,text=True,timeout=120)
        assert r.returncode==2 and 'one file' in r.stderr and not owned.occupied(root/'same.sf2'),(r.returncode,r.stderr[-400:])
        # So is one that names the bank through another folder name for the same folder (a junction, a link).
        (root/'banks').mkdir();aliased=False
        if os.name=='nt':aliased=subprocess.run(['cmd','/c','mklink','/J',str(root/'alias'),str(root/'banks')],capture_output=True).returncode==0
        else:os.symlink(root/'banks',root/'alias',target_is_directory=True);aliased=True
        if aliased:
            r=subprocess.run([sys.executable,script,'build',str(root/'manifest.json'),'--root',str(src),'--output',str(root/'banks'/'kit.sf2'),'--receipt',str(root/'alias'/'kit.sf2')],capture_output=True,text=True,timeout=120)
            assert r.returncode==2 and 'one file' in r.stderr and not owned.occupied(root/'banks'/'kit.sf2'),(r.returncode,r.stderr[-400:])
        return {'refused':['..','absolute'],'changed_source_kept_nothing':True,'receipt_on_the_bank_refused':True,'receipt_through_an_alias_refused':aliased}
    def wav_readers():
        # The two WAV readers' samples and header rules: audio.read_wav for the skill's own files (48 kHz, 16- and
        # 24-bit PCM, 32-bit float) and wavfile for third-party samples (any rate from 8 to 192 kHz, PCM of 8 to 32
        # bits, float).  Mutants that lived through every check (0.8's mutation analysis, 2026-11-15): either reader's
        # RIFF/WAVE test joined by `and` (a RIFF file of another form, or a big-endian RIFX one, read on as WAV),
        # wavfile's bound on a chunk loosened by 16 bytes (a data chunk cut short read as whole), and read_wav's 16-bit
        # scale multiplied.  Every encoding below holds the same five values exactly.
        from musiclib import wavfile
        E=np.array([-1,-.5,0,.25,.5],dtype=np.float32);S=np.stack([E,E[::-1]],1)   # stereo: the right channel reversed
        enc={8:lambda x:(x*128+128).astype('u1').tobytes(),16:lambda x:(x*32768).astype('<i2').tobytes(),
             24:lambda x:b''.join(int(v).to_bytes(3,'little',signed=True) for v in (x*8388608).astype(np.int64)),
             32:lambda x:(x.astype(np.float64)*2147483648).astype('<i4').tobytes(),'f':lambda x:x.astype('<f4').tobytes()}
        def chunk(cid,data):
            return cid+struct.pack('<I',len(data))+data+(b'\0' if len(data)%2 else b'')
        def riff(*chunks,form=b'WAVE',magic=b'RIFF'):
            body=form+b''.join(chunks);return magic+struct.pack('<I',len(body))+body
        def fmt(tag,channels,rate,bits,sub=None):           # sub: WAVE_FORMAT_EXTENSIBLE with that subformat
            align=channels*bits//8;f=struct.pack('<HHIIHH',tag,channels,rate,rate*align,align,bits)
            if sub is not None:f+=struct.pack('<HHIH',22,bits,(1<<channels)-1,sub)+bytes.fromhex('000000001000800000aa00389b71')
            return chunk(b'fmt ',f)
        def write(name,data):
            (work/f'wav08_{name}.wav').write_bytes(data);return work/f'wav08_{name}.wav'
        refusals=[]
        def refused(read,data,words):
            try:read(write('refused',data))
            except ValueError as e:
                assert words in str(e),(words,str(e));refusals.append(words);return
            raise AssertionError(f'read: {words}')
        R=audio.RATE
        # The skill's own reader, with an odd-sized chunk of another kind (and its pad byte) before the format.
        own=[('own16s',riff(chunk(b'LIST',b'abc'),fmt(1,2,R,16),chunk(b'data',enc[16](S.ravel()))),S,16,1),
             ('own24m',riff(fmt(1,1,R,24),chunk(b'data',enc[24](E))),E[:,None],24,1),
             ('ownfs',riff(fmt(3,2,R,32),chunk(b'data',enc['f'](S.ravel()))),S,32,3),
             ('own16x',riff(fmt(0xFFFE,2,R,16,sub=1),chunk(b'data',enc[16](S.ravel()))),S,16,1)]
        for name,data,want,bits,tag in own:
            x,info=audio.read_wav(write(name,data));got=np.array(x);del x   # a copy: the reader maps the file
            assert got.dtype==np.float32 and np.array_equal(got,want),(name,got)
            assert (info['bits'],info['format'],info['frames'],info['channels'],info['sample_rate'])==(bits,tag,5,want.shape[1],R),(name,info)
        good=(fmt(1,1,R,16),chunk(b'data',enc[16](E)))
        refused(audio.read_wav,riff(*good,form=b'AVI '),'Only RIFF WAV supported')
        refused(audio.read_wav,riff(*good,magic=b'RIFX'),'Only RIFF WAV supported')
        refused(audio.read_wav,riff(fmt(1,1,44100,16),good[1]),'Unsupported WAV dimensions')
        # A WAV without its format or its data chunk is refused as such, by both readers.  A mutant that dropped
        # read_wav's starting value for the data turned the refusal into UnboundLocalError, and one that joined the
        # test by `and` read on into a TypeError (0.8's second mutation sample, 2026-11-15).
        for missing in (riff(good[0]),riff(good[1])):
            refused(audio.read_wav,missing,'Missing WAV format/data');refused(wavfile.info,missing,'Missing fmt/data')
        # The third-party reader: 8-bit PCM is unsigned (5 bytes here, so the data chunk has its pad byte).
        third=[('tp8m',riff(fmt(1,1,22050,8),chunk(b'data',enc[8](E))),E[:,None],22050,8,1),
               ('tp16s',riff(fmt(1,2,44100,16),chunk(b'data',enc[16](S.ravel()))),S,44100,16,1),
               ('tp24m',riff(fmt(1,1,96000,24),chunk(b'data',enc[24](E))),E[:,None],96000,24,1),
               ('tp32m',riff(fmt(1,1,8000,32),chunk(b'data',enc[32](E))),E[:,None],8000,32,1),
               ('tpfs',riff(fmt(3,2,192000,32),chunk(b'data',enc['f'](S.ravel()))),S,192000,32,3),
               ('tpfx',riff(fmt(0xFFFE,1,48000,32,sub=3),chunk(b'data',enc['f'](E))),E[:,None],48000,32,3)]
        for name,data,want,rate,bits,tag in third:
            x,info=wavfile.read(write(name,data))
            assert np.array_equal(x,want) and (info['rate'],info['bits'],info['tag'],info['frames'],info['channels'])==(rate,bits,tag,5,want.shape[1]),(name,x,info)
        refused(wavfile.info,riff(*good,form=b'AVI '),'Not RIFF/WAVE')
        refused(wavfile.info,riff(*good,magic=b'RIFX'),'Not RIFF/WAVE')
        for rate in (7999,192001):refused(wavfile.info,riff(fmt(1,1,rate,16),good[1]),'Unsupported WAV layout')
        # A data chunk that says it holds more than the file has: one byte more is read as the bytes there are, two are
        # refused as cut short; a chunk after the audio that runs past the end is left unread.
        body=enc[16](E)
        refused(wavfile.info,riff(fmt(1,1,44100,16),b'data'+struct.pack('<I',len(body)+2)+body),'Truncated chunk')
        x,info=wavfile.read(write('tp_one_over',riff(fmt(1,1,44100,16),b'data'+struct.pack('<I',len(body)+1)+body)))
        assert np.array_equal(x,E[:,None]) and info['frames']==5,info
        x,info=wavfile.read(write('tp_tail',riff(fmt(1,1,44100,16),chunk(b'data',body),b'LIST'+struct.pack('<I',100)+b'INFO')))
        assert np.array_equal(x,E[:,None]) and info['frames']==5,info
        # 1 to 7 bytes after the last chunk, too few for a chunk's header: the skill's reader refuses the file and the
        # third-party one reads its audio, each by its own policy through step 1.7's shared walker (the outside review
        # of 2026-11-15).
        for extra in range(1,8):
            short_tail=riff(fmt(1,1,R,16),good[1])+bytes(extra)
            refused(audio.read_wav,short_tail,'Truncated WAV chunk')
            x,info=wavfile.read(write(f'tp_short_tail_{extra}',short_tail));assert np.array_equal(x,E[:,None]) and info['frames']==5,(extra,info)
        return {'own_encodings':len(own),'third_party_encodings':len(third),'refusals':len(refusals)}
    def wav_policies_side_by_side():
        # 0.8 step 1.7 (design-0.8.md, Part C): the skill's reader (audio.read_wav, for its own files) and the third-party
        # reader (wavfile.info, for the samples a bank is built from) keep their own policies, pinned on the same bytes:
        # an extensible format chunk of 26-39 bytes is refused by the first and read by the second (the subformat's code
        # is there from byte 24), 40 by both, 25 by neither, and 40 whose sub-format GUID is not KSDATAFORMAT's (which
        # FFmpeg does not read either) by the second alone; a format chunk under 16 bytes is refused by both, the second
        # now naming the file, also through the builder's command (it stopped with struct.error); a smpl chunk after the
        # data still gives its loop.  The two chunk walks stay apart: they differ in a truncated tail, a chunk past the
        # end, the format chunk's size and the data's end, and each difference is held by a check here or above.
        import struct,subprocess,sys
        from musiclib import audio,loop,wavfile
        R=48000;pcm=struct.pack('<4h',1000,-1000,2000,-2000)   # two stereo frames
        chunk=lambda cid,p:cid+struct.pack('<I',len(p))+p+(b'\0' if len(p)&1 else b'')
        wav=lambda *cs:(lambda body:b'RIFF'+struct.pack('<I',len(body))+body)(b'WAVE'+b''.join(cs))
        GUID=bytes.fromhex('000000001000800000aa00389b71')   # KSDATAFORMAT's sub-format GUID after its first two bytes, the code
        ext=lambda n:(struct.pack('<HHIIHHHHI',0xFFFE,2,R,R*4,4,16,22,16,3)+struct.pack('<H',1)+GUID)[:n]
        def write(name,data):path=work/name;path.write_bytes(data);return path
        own,third={},{}
        for n in (25,26,39,40):
            path=write(f'ext{n}.wav',wav(chunk(b'fmt ',ext(n)),chunk(b'data',pcm)))
            try:audio.read_wav(path);own[n]='read'
            except ValueError as e:own[n]=str(e)
            try:i=wavfile.info(path);third[n]=(i['tag'],i['frames'])
            except ValueError as e:third[n]=str(e)
        assert own[40]=='read' and all('Short extensible WAV' in own[n] for n in (25,26,39)),own
        assert third[26]==third[39]==third[40]==(1,2) and 'Unsupported WAV encoding' in third[25],third
        other=write('ext40_other.wav',wav(chunk(b'fmt ',ext(26)+bytes(14)),chunk(b'data',pcm)))   # the GUID's last 14 bytes 0
        try:audio.read_wav(other);own['40, another GUID']='read'
        except ValueError as e:own['40, another GUID']=str(e)
        i=wavfile.info(other);third['40, another GUID']=(i['tag'],i['frames'])
        assert 'unknown sub-format' in own['40, another GUID'] and third['40, another GUID']==(1,2),(own,third)
        for k in range(14):   # one bit off in each byte of the GUID after its code (one byte alone checked would pass the rest)
            flipped=write(f'ext40_bit{k}.wav',wav(chunk(b'fmt ',ext(26)+GUID[:k]+bytes([GUID[k]^1])+GUID[k+1:]),chunk(b'data',pcm)))
            try:audio.read_wav(flipped);raise AssertionError(f'a GUID one bit off in byte {k} read')
            except ValueError as e:assert 'unknown sub-format' in str(e),str(e)
        # a 40-byte extensible format naming float32 is float32 to both: the samples exactly (one taking every extensible
        # format as PCM passed the PCM cases above)
        F32=np.array([[.5,-.25],[.125,-1]],dtype='<f4')
        fext=write('ext_float.wav',wav(chunk(b'fmt ',struct.pack('<HHIIHHHHI',0xFFFE,2,R,R*8,8,32,22,32,3)+struct.pack('<H',3)+GUID),chunk(b'data',F32.tobytes())))
        assert np.array_equal(audio.read_wav(fext)[0],F32) and wavfile.info(fext)['tag']==3 and np.array_equal(wavfile.read(fext)[0],F32)
        for n in (15,14):   # one byte short of the 16 read, and two (a check of < 15 took 15 bytes into struct.error)
            short=write(f'fmt{n}.wav',wav(chunk(b'fmt ',(struct.pack('<HHIIH',1,2,R,R*4,4)+b'\x10')[:n]),chunk(b'data',pcm)))
            for read,words in ((audio.read_wav,'Short WAV format chunk'),(wavfile.info,f'Short WAV format chunk in fmt{n}.wav')):
                try:read(short);raise AssertionError(f'{read.__module__} read a {n}-byte format chunk')
                except ValueError as e:assert words in str(e),str(e)
        root=work/'fmt14_source';root.mkdir();(root/'n_C4.wav').write_bytes(short.read_bytes())
        spec={'name':'short','presets':[{'name':'p','program':0,'layers':[{'dir':'.','template':'n_{note}.wav','dynamics':['default'],
                                                                           'velocity':{'default':[1,127]},'keys':[60,60],'pitch_check':False}]}]}
        save_json(work/'fmt14_spec.json',spec)
        run=subprocess.run([sys.executable,str(SCRIPTS.joinpath('soundbank.py')),'build',str(work/'fmt14_spec.json'),'--root',str(root),
                            '--output',str(work/'fmt14.sf2'),'--receipt',str(work/'fmt14_receipt.json')],capture_output=True,text=True,encoding='utf-8',errors='replace')
        assert run.returncode==2 and 'Short WAV format chunk in n_C4.wav' in run.stderr and 'Traceback' not in run.stderr,(run.returncode,run.stderr[-600:])
        after=write('smpl_after.wav',wav(chunk(b'fmt ',struct.pack('<HHIIHH',1,2,R,R*4,4,16)),chunk(b'data',pcm),
                                         chunk(b'smpl',struct.pack('<9I',0,0,20833,60,0,0,0,1,0)+struct.pack('<6I',0,0,0,1,0,0))))
        assert wavfile.info(after)['loops']==[(0,2)] and audio.read_wav(after)[1]['frames']==2
        # The loop file's writer: a cue label of odd length is padded, and the next label's header lies at its even place.
        loop.write_wav(work/'cues.wav',np.zeros((480,2),dtype=np.float32),0,480,cues=[(0,'ab'),(240,'cdef')])
        b=(work/'cues.wav').read_bytes();i=b.find(b'adtl')+4
        assert struct.unpack_from('<4sI',b,i)==(b'labl',7) and b[i+15]==0 and b[i+16:i+20]==b'labl',b[i:i+40]
        assert struct.unpack_from('<I',b,4)[0]==len(b)-8 and audio.read_wav(work/'cues.wav')[1]['frames']==480
        # A cached take of no frames is no take, whatever length the render asks of it: one passed for a sampled part,
        # whose length varies, and stopped the level's measure (the review of 0.8.0)
        audio.write_wav(work/'take_no_frames.wav',np.zeros((0,2),dtype=np.float32))
        assert audio.take_fault(work/'take_no_frames.wav')=='no frames' and audio.take_fault(work/'take_no_frames.wav',0)=='no frames'
        return {'extensible':{'own':{n:('read' if v=='read' else 'refused') for n,v in own.items()},'third_party':{n:('read' if isinstance(v,tuple) else 'refused') for n,v in third.items()}},'short_format':'refused by both, named'}
    def bank_files_named_by_template():
        # 0.8 step 1.5 (design-0.8.md, Part C; CWE-1333): a spec names a layer's files with a template, matched in one
        # pass without backtracking; only the skill's own recipes keep their regular expressions, told by the canonical
        # digest of the parsed spec that the lock records.  Through `soundbank.py build` on a synthetic source tree for
        # the bundled vocal_ah recipe: a renamed copy with CRLF line endings builds (its regex kept), the same with one
        # value changed is refused with the template it would be, the recipe with that template builds the same bank,
        # and a 0.7 user's regex spec is refused before any recording is read.
        import subprocess,sys
        import soundbank as sb
        P=lambda t:sb.template_parts(t,'t');m=lambda t,n:sb.template_match(P(t),n)
        assert m('p_{note}','p_C4')=={'note':'C4'} and m('p_{note}','p_C4x') is None and m('take.wav','take.wav')=={} and m('take.wav','take.wav.wav') is None
        assert m('{id}x{rr}.wav','abx02.wav')=={'id':'ab','rr':'02'} and m('{id}x{rr}.wav','axbx2.wav') is None   # no later x tried
        assert m('r{rr}5','r255')=={'rr':'25'}   # a last literal is matched at the end, not where it first appears
        try:sb.naming({'presets':[{'name':'p','layers':[{'template':'p_{note}.wav'}]}]});raise AssertionError('a layer without dir taken')
        except ValueError as e:assert 'no `dir`' in str(e),str(e)   # a KeyError past the command's handler (the review of 0.8.0)
        for mics in ([{}],[{'dir':'k'},{'gain':.5}],'k',[3]):   # and each microphone's folder (a KeyError: the Astra review of the fixes)
            try:sb.naming({'presets':[{'name':'p','layers':[{'template':'x.wav','root':60,'mics':mics,'dynamics':['default']}]}]});raise AssertionError(f'mics {mics!r} taken')
            except ValueError as e:assert '`mics` lists objects, each with its `dir`' in str(e),str(e)
        whole={'dir':'.','template':'p_{note}.wav','dynamics':['default'],'keys':'auto','velocity':{'default':[1,127]}}
        sb.naming({'presets':[{'name':'p','layers':[whole]}]})   # and the fields the build reads of every layer, each named
        for field in ('dynamics','keys','velocity'):
            try:sb.naming({'presets':[{'name':'p','layers':[{k:v for k,v in whole.items() if k!=field}]}]});raise AssertionError(f'a layer without {field} taken')
            except ValueError as e:assert f'no `{field}`' in str(e),str(e)
        assert m('p_{note}.wav','P_C4.wav') is None and m('p_{note}.wav','p_c#4.wav')=={'note':'c#4'} and m('p_{note}.wav','p_Bb-1.wav')=={'note':'Bb-1'}
        assert m('p_{note}.wav','p_C10.wav') is None and m('p_{note}.wav','p_C4.wav.wav') is None and m('p_{note}_{dyn}.wav','p_C4_.wav') is None
        assert m('p_{note}_{dyn}.wav','p_C4_ff.wav')=={'note':'C4','dyn':'ff'} and m('p_{dyn}.wav','p_fé.wav') is None and m('r{rr}.wav','r٢.wav') is None
        for bad in ('','{note}{dyn}.wav','{tone}.wav','{note}_{note}.wav','a}b.wav','{note.wav','p_{Note}.wav'):
            rejects(lambda:P(bad))
        one=lambda **layer:{'name':'t','presets':[{'name':'p','program':0,'layers':[{'dir':'.','dynamics':['default'],'velocity':{'default':[1,127]},'keys':[60,60],**layer}]}]}
        assert sb.naming(one(template='hit.wav',root=60))==[[('hit.wav',None)]] and sb.naming(one(template='t_{id}.wav',pitches={'a':60.0}))==[[('t_',None),('','id'),('.wav',None)]]
        for bad in (one(template='hit.wav'),one(template='p_{note}.wav',pattern='p_(?P<note>C4).wav'),one(pattern=r'p_(?P<note>[A-G]\d)\.wav'),one()):
            rejects(lambda:sb.naming(bad))
        recipe_path=sb.LOCK.parent/'soundbanks'/'vocal_ah.json';text=recipe_path.read_text(encoding='utf-8');recipe=json.loads(text)
        src=work/'tpl_src';folder=src/recipe['presets'][0]['layers'][0]['dir'];folder.mkdir(parents=True)
        for name,midi in (('C4',60),('E4',64),('G4',67)):   # 3 s of a steady vowel-like tone at each note
            f0=440*2**((midi-69)/12);t=np.arange(3*48000)/48000
            x=sum(np.sin(2*np.pi*f0*k*t)/k for k in range(1,7))*np.minimum(1,t/0.05)*np.minimum(1,(3-t)/0.2)*0.2
            pcm=(np.clip(x,-1,1)*32767).astype('<i2').tobytes()
            (folder/f'vowel_a_{name}.wav').write_bytes(b'RIFF'+struct.pack('<I',36+len(pcm))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,48000,96000,2,16)+b'data'+struct.pack('<I',len(pcm))+pcm)
        def build(spec_text,tag,root=src):
            (work/f'tpl_{tag}.json').write_bytes(spec_text.encode('utf-8'))
            return subprocess.run([sys.executable,str(SCRIPTS.joinpath('soundbank.py')),'build',str(work/f'tpl_{tag}.json'),'--root',str(root),'--output',
                                   str(work/f'tpl_{tag}.sf2'),'--receipt',str(work/f'tpl_{tag}_receipt.json')],capture_output=True,text=True,encoding='utf-8',errors='replace')
        crlf=build(text.replace('\r\n','\n').replace('\n','\r\n'),'crlf')
        assert crlf.returncode==0,crlf.stderr[-600:]
        changed=json.loads(text);changed['presets'][0]['layers'][0]['fmax']=1201
        refused=build(json.dumps(changed),'changed')
        assert refused.returncode==2 and "preset 'Vocal Ah', layer 1" in refused.stderr and '"template": "vowel_a_{note}.wav"' in refused.stderr and 'Traceback' not in refused.stderr,refused.stderr
        templated=json.loads(text);layer=templated['presets'][0]['layers'][0];del layer['pattern'];layer['template']='vowel_a_{note}.wav'
        same=build(json.dumps(templated),'template')
        assert same.returncode==0 and (work/'tpl_template.sf2').read_bytes()==(work/'tpl_crlf.sf2').read_bytes(),same.stderr[-600:]
        (work/'tpl_old').mkdir();(work/'tpl_old'/'n_C4.wav').write_bytes(b'not a wav')   # read, it would fail as no WAV
        old=build(json.dumps(one(pattern=r'n_(?P<note>[A-G]#?\d)\.wav',pitch_check=False)),'old',work/'tpl_old')
        assert old.returncode==2 and '"template": "n_{note}.wav" (the nearest one' in old.stderr and 'RIFF' not in old.stderr and 'Traceback' not in old.stderr,old.stderr
        # a template of no field: its one file, the folder's others neither read (miss.wav is no WAV) nor listed (an
        # SFZ's 352 regions in one folder listed 123,552 of them in its receipt: the third outside review)
        (work/'tpl_hit').mkdir();(work/'tpl_hit'/'hit.wav').write_bytes((folder/'vowel_a_C4.wav').read_bytes());(work/'tpl_hit'/'miss.wav').write_bytes(b'not a wav')
        hit=build(json.dumps(one(template='hit.wav',root=60,pitch_check=False)),'hit',work/'tpl_hit')
        rows=json.loads((work/'tpl_hit_receipt.json').read_text(encoding='utf-8'))['files'] if hit.returncode==0 else hit.stderr[-300:]
        assert [(r['file'],r['root_key'],r['keys']) for r in rows if 'skipped' not in r]==[('hit.wav',60,[60,60])] and not [r for r in rows if 'skipped' in r],rows
        # a regex whose nearest template the grammar refuses (two fields side by side) is shown the general form instead
        try:sb.naming(one(pattern=r'n_(?P<note>C4)(?P<dyn>p)\.wav'));raise AssertionError('a regex spec taken')
        except ValueError as e:assert '{note}{dyn}' not in str(e) and 'literal text and the fields' in str(e),str(e)
        return {'bundled_copy':'built','one_value_changed':'refused','template':'same bank','regex_spec':'refused before reading','one_file':'built'}
    def bank_build_opens_no_link_below_its_root():
        # 0.8 step 1.5 (design-0.8.md, Part C; CWE-59): a link or a junction on a path the builder opens below its root
        # is refused, named (0.7 followed one that stayed inside the root); the root itself may be one, resolved once;
        # links the build does not open do not matter.  Through `soundbank.py build` and `cut`; junctions on Windows,
        # where a file link needs a privilege the runner may lack (then those cases are reported as skipped).
        import subprocess,sys
        from musiclib import files as fl
        def tone(path,midi):
            f0=440*2**((midi-69)/12);t=np.arange(48000)/48000
            pcm=(np.sin(2*np.pi*f0*t)*np.minimum(1,t/.01)*np.minimum(1,(1-t)/.1)*.3*32767).astype('<i2').tobytes()
            path.write_bytes(b'RIFF'+struct.pack('<I',36+len(pcm))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,48000,96000,2,16)+b'data'+struct.pack('<I',len(pcm))+pcm)
        def dir_link(link,target):
            try:os.symlink(target,link,target_is_directory=True)
            except OSError:
                if os.name!='nt':raise
                subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True)
            return fl.linked(link)
        def file_link(link,target):
            try:os.symlink(target,link)
            except OSError:return False
            return fl.linked(link)
        root=work/'lk_root';(root/'L').mkdir(parents=True);(root/'M').mkdir();(root/'P'/'inner'/'L').mkdir(parents=True)
        for folder in (root/'L',root/'M',root/'P'/'inner'/'L'):tone(folder/'n_C4.wav',60)
        made={'alias':dir_link(work/'lk_alias',root),'J':dir_link(root/'J',root/'L'),'Q':dir_link(root/'Q',root/'P'),'other':dir_link(root/'other',root/'M')}
        assert all(made.values()),made
        spec=lambda **layer:{'name':'links','presets':[{'name':'p','program':0,'layers':[{'template':'n_{note}.wav','dynamics':['default'],
                             'velocity':{'default':[1,127]},'keys':[60,62],'pitch_check':False,**layer}]}]}
        runs=[0]
        def build(s,at=root):
            runs[0]+=1;tag=f'lk_{runs[0]}';save_json(work/f'{tag}.json',s)
            return subprocess.run([sys.executable,str(SCRIPTS.joinpath('soundbank.py')),'build',str(work/f'{tag}.json'),'--root',str(at),'--output',
                                   str(work/f'{tag}.sf2'),'--receipt',str(work/f'{tag}_receipt.json')],capture_output=True,text=True,encoding='utf-8',errors='replace')
        ok=build(spec(dir='L'));alias=build(spec(dir='L'),work/'lk_alias')   # a link elsewhere in the root, and the root as an alias
        assert ok.returncode==0 and alias.returncode==0 and (work/'lk_1.sf2').read_bytes()==(work/'lk_2.sf2').read_bytes(),(ok.stderr[-300:],alias.stderr[-300:])
        for layer,named in (({'dir':'J'},'J is a link'),({'dir':'Q/inner/L'},'Q is a link'),({'mics':[{'dir':'L'},{'dir':'other'}]},'other is a link')):
            r=build(spec(**layer))
            assert r.returncode==2 and named in r.stderr and 'Traceback' not in r.stderr,(layer,r.returncode,r.stderr[-400:])
        skipped=[]
        if file_link(root/'L'/'n_D4.wav',root/'L'/'n_C4.wav'):
            r=build(spec(dir='L'));assert r.returncode==2 and 'L/n_D4.wav is a link' in r.stderr,r.stderr[-400:]
            (root/'L'/'n_D4.wav').unlink()
        else:skipped.append('a file link in a layer (no privilege to make one)')
        # cut: a manifest's source through a junction below the root is refused before anything is cut
        manifest={'groups':[],'sources':[],'notes':[{'source':'J/n_C4.wav','file':'x/n_C4.wav','start':0,'end':100,'fade':0,'sha256':'0'*64}]}
        save_json(work/'lk_manifest.json',manifest)
        r=subprocess.run([sys.executable,str(SCRIPTS.joinpath('soundbank.py')),'cut',str(work/'lk_manifest.json'),'--root',str(root),'--output',str(work/'lk_cut')],
                         capture_output=True,text=True,encoding='utf-8',errors='replace')
        assert r.returncode==2 and 'J is a link' in r.stderr and not (work/'lk_cut').exists(),r.stderr[-400:]
        # split.json, read where the pitches come from it and where the noise does: each read refused as a link.  A file
        # link needs a privilege, so the link is the reader's view here (files.linked answering for split.json alone);
        # built without that view, both read the manifest and build.
        import soundbank as sb
        sroot=work/'lk_split';(sroot/'S').mkdir(parents=True);tone(sroot/'S'/'n_C4.wav',60)
        save_json(sroot/'split.json',{'groups':[],'sources':[{'file':'rec.wav','noise_bands':None}],'notes':[{'file':'S/n_C4.wav','source':'rec.wav','cents':0.0}]})
        reads=({'pitch_source':'split'},{'denoise':{'reduce_db':12}})
        for k,layer in enumerate(reads):sb.build(spec(dir='S',**layer),sroot,work/f'lk_split_{k}.sf2')
        real,real_read,opened=fl.linked,fl.read_object,[]   # and the manifest never read before its link is refused
        fl.linked=lambda p:Path(p).name=='split.json' or real(p)
        fl.read_object=lambda p,*a,**k:(opened.append(Path(p).name),real_read(p,*a,**k))[1]
        try:
            for k,layer in enumerate(reads):
                try:sb.build(spec(dir='S',**layer),sroot,work/f'lk_split_linked_{k}.sf2');raise AssertionError(f'split.json read through a link: {layer}')
                except ValueError as e:assert 'the split manifest: split.json is a link' in str(e),(layer,str(e))
        finally:fl.linked,fl.read_object=real,real_read
        assert 'split.json' not in opened,opened
        return {'refused':['a layer folder','a parent folder','a second microphone','a cut source','split.json for pitches','split.json for noise'],'taken':['the root as an alias','a link not opened'],'skipped':skipped}
    def bank_cut_checks_each_span_first():
        # 0.8 step 1.5 (design-0.8.md, Part C; CWE-770): a split manifest's start, end and fade are whole numbers, not
        # booleans, with 0 <= start <= end <= the source's frames and 0 <= fade <= end - start, checked once the source
        # is decoded and before the slice and the ramp (0.7 took a boolean fade as 1, stopped on a float with a
        # TypeError and on a long fade with NumPy's broadcast error); a refused note after a good one leaves no file.
        import subprocess,sys
        import soundbank as sb
        src=work/'span_src';src.mkdir()
        sb.write_float_wav(src/'take.wav',(np.sin(np.arange(4800)/7)*.3).astype(np.float32)[:,None],48000)
        x,info=sb.read_audio(src/'take.wav')
        def note(i,start,end,fade):   # its recorded hash is the cut's where the cut can be made
            n={'source':'take.wav','file':f'n{i}.wav','start':start,'end':end,'fade':fade,'sha256':'0'*64}
            if all(isinstance(v,int) and not isinstance(v,bool) for v in (start,end,fade)) and 0<=start<=end<=4800 and 0<=fade<=end-start:
                n['sha256']=sb._cut_note(x,start,end,fade,info['rate'],work/f'span_ref_{i}.wav')
            return n
        good=[note(0,0,4800,0),note(1,100,1100,1000)]   # no fade, and a fade over the whole note
        assert sb._span({'file':'z','start':100,'end':100,'fade':0},4800)==(100,100,0) and sb._span({'file':'z','start':4800,'end':4800,'fade':0},4800)==(4800,4800,0)   # empty spans at the edges are whole numbers in bounds
        assert sb.cut_sources({'notes':good},src,work/'span_good')==2 and sorted(p.name for p in (work/'span_good').iterdir())==['n0.wav','n1.wav']
        bad=[(100,1100,1001),(100,1100,-1),(100,1100,1.5),(100,1100,True),(-1,1100,0),(100,4801,0),(4000,4801,10),(1100,100,0),(0,True,0)]
        cuts,real_cut=[],sb._cut_note   # each cut's span: a bad note must not reach the cut (its wrong hash would refuse it later)
        sb._cut_note=lambda x,s,e,f,rate,path:(cuts.append((s,e,f)),real_cut(x,s,e,f,rate,path))[1]
        try:
            for k,(s,e,f) in enumerate(bad):
                out=work/f'span_bad_{k}';cuts.clear()
                try:sb.cut_sources({'notes':[good[0],note(2,s,e,f)]},src,out);raise AssertionError(f'cut {s}-{e} fade {f}')
                except ValueError as err:assert "'n2.wav'" in str(err),str(err)
                assert cuts==[(0,4800,0)],((s,e,f),cuts)
                assert not out.exists() or not [p for p in out.rglob('*') if p.is_file()],(s,e,f,list(out.rglob('*')))
        finally:sb._cut_note=real_cut
        save_json(work/'span_manifest.json',{'groups':[],'sources':[],'notes':[good[0],note(2,100,1100,1.5)]})
        r=subprocess.run([sys.executable,str(SCRIPTS.joinpath('soundbank.py')),'cut',str(work/'span_manifest.json'),'--root',str(src),'--output',str(work/'span_cli')],
                         capture_output=True,text=True,encoding='utf-8',errors='replace')
        assert r.returncode==2 and 'whole numbers' in r.stderr and 'Traceback' not in r.stderr and not (work/'span_cli').exists(),r.stderr[-400:]
        return {'cut':len(good),'refused':len(bad)+1}
    def aiff_reader_walks_headers_and_refuses_what_it_cannot_hold():
        # 0.8 step 1.5 (design-0.8.md, Part C; AIFF 1.3, the AIFF-C draft of 1991): soundbank.read_aiff walks the chunk
        # headers by seeking.  Kept from 0.7: either chunk order, a wrong FORM length, no FVER, surplus sample bytes, the
        # last SSND, bytes after COMM and SSND that make no chunk (an odd SSND whose writer left out the pad byte shifts
        # the next header, as in one Iowa recording), an .aifc read by its path while folders list .aif and .aiff.
        # Refused now (0.7 read a shorter take, or took the second COMM): a second COMM after SSND or after another
        # chunk, unprintable bytes before both chunks are found (a zero-filled file), a sample payload cut short, an
        # offset that leaves too few bytes, a wrong compression-name count, an AIFF COMM of another size, and a
        # recording over MAX_SOURCE_SECONDS, refused before any sample byte is read (here with the limit lowered).
        import builtins
        import soundbank as sb
        ext80=lambda rate:(lambda e:struct.pack('>HQ',16383+e,int(rate)<<(63-e)))(int(np.floor(np.log2(rate))))
        S=np.array([[.5,-.5],[.25,-.25],[0,0]]);pcm=b''.join(int(v*32768).to_bytes(2,'big',signed=True) for v in S.ravel())
        chunk=lambda cid,payload:cid+struct.pack('>I',len(payload))+payload+(b'\0' if len(payload)%2 else b'')
        comm=lambda frames=3,ch=2,bits=16,extra=b'':chunk(b'COMM',struct.pack('>hIh',ch,frames,bits)+ext80(48000)+extra)
        ssnd=lambda data=pcm,offset=0:chunk(b'SSND',struct.pack('>II',offset,0)+bytes(offset)+data)
        aiff=lambda *cs,kind=b'AIFF',form=None:(lambda body:b'FORM'+struct.pack('>I',len(body) if form is None else form)+body)(kind+b''.join(cs))
        def read(name,data,suffix='.aif'):
            p=work/f'aiffs_{name}{suffix}';p.write_bytes(data);return sb.read_audio(p)
        want=S.astype(np.float32)
        odd=b'FORM'+struct.pack('>I',4)+b'AIFF'+chunk(b'COMM',struct.pack('>hIh',1,3,8)+ext80(48000))+b'SSND'+struct.pack('>I',11)+struct.pack('>II',0,0)+bytes([64,192,0])+chunk(b'APPL',b'stoc')
        kept=[('comm_first',aiff(comm(),ssnd())),('ssnd_first',aiff(ssnd(),comm())),('form_length',aiff(comm(),ssnd(),form=7)),('surplus',aiff(comm(),ssnd(pcm+b'\1\2\3\4'))),
              ('last_ssnd',aiff(comm(),ssnd(bytes(len(pcm))),ssnd())),('tail_after',aiff(comm(),ssnd())+b'\0\0\0\0junk!'),('offset',aiff(comm(),ssnd(offset=6)))]
        for name,data in kept:
            x,info=read(name,data);assert np.array_equal(x,want) and info['frames']==3,(name,x)
        x,info=read('odd_no_pad',odd);assert x[:,0].tolist()==[.5,-.5,0.0] and info['frames']==3,x
        x,_=read('named',aiff(comm(extra=b'NONE'+bytes([4])+b'none'+b'\0'),ssnd(),kind=b'AIFC'),'.aifc');assert np.array_equal(x,want)   # an .aifc by its path
        (work/'aiffs_folder').mkdir();(work/'aiffs_folder'/'a.aifc').write_bytes(b'');(work/'aiffs_folder'/'b.aif').write_bytes(b'')
        assert [p.name for p in sb.audio_files(work/'aiffs_folder')]==['b.aif']
        refused=[('comm_after_ssnd',aiff(comm(),ssnd(),comm()),'two COMM'),('comm_after_other',aiff(comm(),chunk(b'NAME',b'x'),comm(),ssnd()),'two COMM'),
                 ('comm_after_both_and_other',aiff(comm(),ssnd(),chunk(b'NAME',b'x'),comm()),'two COMM'),   # the walk goes on past a chunk it skips
                 ('comm_after_an_even_chunk',aiff(comm(),ssnd(),chunk(b'NAME',b'ab'),comm()),'two COMM'),  # no pad byte after an even one
                 ('bad_before',aiff(comm())+b'\0'*8+ssnd(),'unprintable'),('zero_filled',b'FORM'+struct.pack('>I',4+64)+b'AIFF'+bytes(64),'unprintable'),
                 ('cut_short',aiff(comm(),ssnd())[:-2],'holds fewer'),('offset_short',aiff(comm(),chunk(b'SSND',struct.pack('>II',4,0)+pcm)),'holds fewer'),
                 ('pascal_count',aiff(comm(extra=b'NONE'+bytes([9])+b'none'+b'\0'),ssnd(),kind=b'AIFC'),'compression name'),('comm_20',aiff(comm(extra=b'\0\0'),ssnd()),'AIFF has 18')]
        for name,data,words in refused:
            try:read(name,data);raise AssertionError(f'{name} read')
            except ValueError as e:assert words in str(e),(name,str(e))
        class Counting:   # how far into the file any read reached (a count of bytes let one sample byte by: the third review)
            def __init__(self,f):self.f,self.reach=f,0
            def read(self,k=-1):at=self.f.tell();b=self.f.read(k);self.reach=max(self.reach,at+len(b));return b
            def seek(self,*a):return self.f.seek(*a)
            def __enter__(self):return self
            def __exit__(self,*a):self.f.close()
        opened=[];sb.open=lambda p,mode='rb':opened.append(Counting(builtins.open(p,mode))) or opened[-1];limit=sb.MAX_SOURCE_SECONDS
        try:
            sb.MAX_SOURCE_SECONDS=3/48000
            assert read('at_cap',aiff(comm(),ssnd()))[1]['frames']==3   # at the limit: read
            before=len(opened)
            try:read('over_cap',aiff(comm(frames=4),ssnd(pcm+b'\0'*4)));raise AssertionError('over the limit read')
            except ValueError as e:assert 'longer than' in str(e),str(e)
            # the headers only: no read through any file the refused attempt opened reached the first sample byte, at 54
            assert len(opened)>before and all(h.reach<=12+26+16 for h in opened[before:]),[h.reach for h in opened[before:]]
        finally:
            del sb.open;sb.MAX_SOURCE_SECONDS=limit
        return {'kept':len(kept)+2,'refused':len(refused)+1}
    def sounds_search_names_what_it_does_not_know():
        # 0.8 step 2.3 (design-0.8.md; the Command Line Interface Guidelines: suggest, never correct silently): `sounds`
        # matches a role without regard to case, refuses a role or a character word the catalog does not hold with the
        # nearest one and all of them (0.7 matched nothing and said nothing), takes the catalog's phrases ("fast attack"),
        # and gives each range's own examples (--attack showed the centroid's Hz).
        import subprocess,sys
        def sounds(*a):
            r=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'sounds',*a,'--json'],capture_output=True,text=True,encoding='utf-8',errors='replace')
            return r.returncode,(json.loads(r.stdout) if r.returncode==0 else r.stderr)
        code,lower=sounds('--role','lead','--limit','3');code2,upper=sounds('--role','Lead','--limit','3')
        assert code==code2==0 and lower['count']==upper['count']>0 and lower['shown']==upper['shown'],(code,code2)
        for args,words in ((('--role','leads'),"did you mean 'lead'?"),(('--character','brite'),"did you mean 'bright'?"),(('--role','zzz'),'It knows: bass, brass,')):
            code,err=sounds(*args);assert code==2 and words in err and err.count('\n')==1,(args,err)
        code,phrase=sounds('--character','fast attack,warm','--limit','2')   # every word asked, the second too
        assert code==0 and phrase['count']>0 and all('fast attack' in r['character'] and 'warm' in r['character'] for r in phrase['shown']),phrase
        code,loud=sounds('--character','FAST ATTACK,Warm','--limit','2');assert code==0 and loud==phrase,(code,loud)   # character words without regard to case too
        code,err=sounds('--attack','fast');assert code==2 and 'seconds: 0.1-0.3' in err,err
        code,err=sounds('--centroid','bright');assert code==2 and 'Hz: 600-900' in err,err
        # 0.9.2: by default one line a patch, with what tells them apart (the JSON of 25 patches was about 12 KB a call); --json keeps it all.
        short=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'sounds','--role','lead','--limit','3'],capture_output=True,text=True,encoding='utf-8',errors='replace')
        lines=short.stdout.strip().splitlines();assert short.returncode==0 and len(lines)==5 and lines[0].endswith('3 shown:'),short.stdout[:300]
        assert all(r['id'] in short.stdout for r in lower['shown']) and all(' Hz, attack ' in x for x in lines[1:4]) and '--json' in lines[-1],short.stdout[:600]
        return {'case':'Lead = lead','refused':['leads','brite','zzz'],'phrase':'fast attack'}
    def instruments_reads_keys_and_layers_from_the_bank():
        # 0.8 step 2.6 (design-0.8.md): `studio.py instruments` finds a configured bank's presets by words of their
        # name, General MIDI family or bank, and reports the bank and program a part takes, the keys the samples cover
        # and the velocity ranges, read from the bank (here one the builder makes: a viola over G3-G4 in two layers).
        import subprocess,sys
        import soundbank as sb
        src=work/'ins_src';src.mkdir()
        for dyn,level in (('p',.1),('f',.5)):
            t=np.arange(48000)/48000;x=(np.sin(2*np.pi*261.63*t)*np.minimum(1,(1-t)/.1)*level).astype(np.float32)
            sb.write_float_wav(src/f'v_C4_{dyn}.wav',np.stack([x,x],1),48000)
        spec={'name':'ins','presets':[{'name':'Test Viola','program':41,'layers':[{'dir':'.','template':'v_{note}_{dyn}.wav','dynamics':['p','f'],
              'velocity':{'p':[1,64],'f':[65,127]},'keys':[55,67],'pitch_check':False}]}]}
        sb.build(spec,src,work/'ins.sf2')
        save_json(work/'ins_config.json',{'soundfont':{'path':str(work/'ins.sf2'),'sha256':file_hash(work/'ins.sf2')}})
        def ins(*words):
            r=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'instruments',*words,'--config',str(work/'ins_config.json'),'--json'],
                             capture_output=True,text=True,encoding='utf-8',errors='replace')
            return r.returncode,(json.loads(r.stdout) if r.returncode==0 else r.stderr)
        for words in (('viola',),('Strings',),('default','viola')):
            code,found=ins(*words);row=found['presets'][0] if code==0 else None
            assert code==0 and found['count']==1 and row['patch']=={'bank':0,'program':41} and row['family']=='strings' and row['keys']=='G3-G4' and row['velocity_ranges']==2,(words,found)
            assert row['velocities']==[[1,64],[65,127]],row   # the ranges themselves (a preset of 90-127 alone read as one of 1-127: the review of 0.8.0)
        code,err=ins('viloa');assert code==2 and "did you mean 'viola'?" in err and err.count('\n')==1,err
        # 0.9 step 5, from real sessions.  A bank number and program, as a part's instrument is written, find the preset
        # ("vsco_strings 1:41" was refused with a did-you-mean); where no preset has every word, those that have the
        # most are listed with the words each has ("electric bass slap" found nothing: the preset is "Slap Bass");
        # a word that is a built-in synth preset's name, or no match at all, points to the synthesizers.
        for words in (('default','0:41'),('0:41',),('viola','0:41')):
            code,found=ins(*words);assert code==0 and found['count']==1 and found['presets'][0]['preset']=='Test Viola' and found['every_word'],(words,found)
        code,err=ins('default','0:40');assert code==2 and '0:40' in err and err.count('\n')==1,err
        code,err=ins('0:41','1:41');assert code==2 and 'one bank number and program' in err,err
        spec2={'name':'ins2','presets':[{**spec['presets'][0]},{**spec['presets'][0],'name':'Slap Bass','program':36}]};sb.build(spec2,src,work/'ins2.sf2')
        save_json(work/'ins2_config.json',{'soundfont':{'path':str(work/'ins2.sf2'),'sha256':file_hash(work/'ins2.sf2')}})
        import musiclib.instruments as mi2
        part=mi2.search(work/'ins2_config.json',['viola','slap','bass'])   # no preset has all three: the one that has two
        assert part['count']==1 and part['every_word'] is False and part['words']==3 and part['presets'][0]['preset']=='Slap Bass' and part['presets'][0]['has']==['slap','bass'],part
        shown=mi2.summary(part);assert shown.startswith('No preset has every word; 1 has 2 of the 3:') and 'has: slap, bass' in shown,shown
        both=mi2.search(work/'ins2_config.json',['viola','slap']);assert both['count']==2 and not both['every_word'] and [r['has'] for r in both['presets']]==[['slap'],['viola']],both
        whole=mi2.search(work/'ins2_config.json',['slap','bass']);assert whole['count']==1 and whole['every_word'] and 'has' not in whole['presets'][0] and mi2.summary(whole).startswith('1 preset:')
        code,err=ins('electric','viola');assert code==2 and 'No configured preset matches' in err and err.count('\n')==1,err   # a word no preset has at all is still refused
        # 0.9.2 (T4): one quoted argument is its words; a miss on a kit's sound says where the kits' keys are; the preset list's dash prints as a hyphen.
        code,found=ins('default 0:41');assert code==0 and found['count']==1 and found['presets'][0]['preset']=='Test Viola',found
        code,err=ins('tambourine');assert code==2 and 'key maps' in err,err
        row={'bank':'b','patch':{'bank':0,'program':0},'preset':'p','family':'piano','keys':'A0-C8','keys_midi':[21,108],'keys_without_a_sample':0,'velocity_ranges':1,'preset_list':{'keys':'A0–C8','velocity_layers':'3'}}
        shown=mi2.summary({'count':1,'every_word':True,'words':1,'note':'n','presets':[row]});assert 'the preset list: keys A0-C8,' in shown and chr(0x2013) not in shown,shown
        rejects(lambda:mi2.search(work/'ins2_config.json',['viola','viloa']))
        # The review of step 5.  (1) A word with a hyphen is in a preset's name as written ("Honky-tonk Piano"), not
        # among the name's separate words: it was called a word no preset has, and the search refused.  (2) The
        # builder, and start through it, took the one nearest preset for the instrument asked: "viola slap bass"
        # gave a part the Slap Bass.  A part plays a preset that has every word, or the script is told which have some.
        spec3={'name':'ins3','presets':[{**spec['presets'][0]},{**spec['presets'][0],'name':'Honky-tonk Piano','program':3}]};sb.build(spec3,src,work/'ins3.sf2')
        save_json(work/'ins3_config.json',{'soundfont':{'path':str(work/'ins3.sf2'),'sha256':file_hash(work/'ins3.sf2')}})
        hy=mi2.search(work/'ins3_config.json',['honky-tonk','viola']);assert hy['count']==2 and not hy['every_word'] and [r['has'] for r in hy['presets']]==[['honky-tonk'],['viola']],hy
        assert mi2.search(work/'ins3_config.json',['honky-tonk'])['presets'][0]['preset']=='Honky-tonk Piano'
        try:mi2.search(work/'ins3_config.json',['honky-tonk','viloa']);raise AssertionError('a word no preset has, taken')
        except ValueError as e:assert "did you mean 'viola'" in str(e),str(e)
        from musiclib.builder import Song
        try:Song('near',bars=1,config=work/'ins2_config.json').part('p','bass','viola slap bass');raise AssertionError('the nearest preset taken for the one asked')
        except ValueError as e:assert 'no preset has every word' in str(e) and 'Slap Bass' in str(e) and 'has: slap, bass' in str(e),str(e)
        assert Song('whole',bars=1,config=work/'ins2_config.json').part('p','bass','slap bass').track['patch']=={'bank':0,'program':36}
        # The walkthrough of 0.9: the summary printed a guitar bank's preset on program 0 as "(piano)".  The family
        # is General MIDI's name for the program number, which a bank of one instrument need not follow: said as
        # that, and the note says what velocity_ranges counts where a bank chooses among takes by the velocity.
        line=mi2.summary(whole).splitlines()[1];assert '(GM family of program 36: bass)' in line and '(bass)' not in line,line
        assert 'General MIDI' in whole['note'] and 'takes by the velocity' in whole['note'],whole['note']
        code,err=ins('fm_epiano');assert code==2 and "'fm_epiano' is a built-in synth preset" in err and 'studio.py sounds' in err and err.count('\n')==1,err
        code,err=ins('qqqq');assert code==2 and 'studio.py sounds' in err and 'built-in synth preset' not in err,err
        # The Astra review of step 2: a preset zone and an instrument zone sound together only where their keys and their
        # velocities both overlap, each zone taking its global zone's ranges; the keys come as runs (holes kept); a
        # preset of no General MIDI program and a bank named with an underscore are read; the pairs measured are bounded.
        import musiclib.instruments as mi
        zone=lambda gens,target=0:{'gens':gens,'target':target}
        inst={'zones':[zone({},None),zone({43:(48,84),44:(1,127)})]};bank={'instruments':[inst]}
        cases=[([zone({43:(60,64),44:(50,60)},None),zone({})],({*range(60,65)},[(50,60)])),   # the preset's global zone bounds its zone
               ([zone({43:(60,64),44:(1,10)})],({*range(60,65)},[(1,10)])),
               ([zone({43:(90,100),44:(1,127)})],(set(),[]))]                                 # keys apart: neither keys nor velocities
        apart={'instruments':[{'zones':[zone({43:(60,64),44:(100,127)})]}]}
        for zones,want in cases:assert mi.measured(bank,{'name':'p','zones':zones})==want,(zones,mi.measured(bank,{'name':'p','zones':zones}))
        assert mi.measured(apart,{'name':'p','zones':[zone({43:(60,64),44:(1,50)})]})==(set(),[])   # velocities apart: neither
        narrow={'instruments':[{'zones':[zone({43:(60,64)},None),zone({}),zone({43:(70,72)})]}]}   # an instrument's global zone bounds its zones, a zone's own range over it
        assert mi.measured(narrow,{'name':'p','zones':[zone({})]})==({*range(60,65),*range(70,73)},[(0,127)]),mi.measured(narrow,{'name':'p','zones':[zone({})]})
        assert mi.key_ranges({60,72,61,62})==[[60,62],[72,72]] and mi.key_ranges(set())==[]
        # review's map of keys to samples reads a preset through the same walk (the third review: it read no global zone
        # and no velocity, so a key outside the preset's own range counted as covered)
        from musiclib.review import transposition
        tb={'instruments':[inst],'samples':[{'root':60}],'presets':[{'name':'p','bank':0,'program':0,'zones':cases[0][0]}]}
        tv={'instruments':apart['instruments'],'samples':[{'root':60}],'presets':[{'name':'p','bank':0,'program':0,'zones':[zone({43:(60,64),44:(1,50)})]}]}
        assert transposition(tb,0,0)=={k:k-60 for k in range(60,65)} and transposition(tv,0,0)=={},(transposition(tb,0,0),transposition(tv,0,0))
        limit=mi.MAX_PAIRS;mi.MAX_PAIRS=3
        try:
            rejects(lambda:mi.measured(bank,{'name':'p','zones':[zone({})]*2}))   # 4 pairs over a bound of 3
            spent=[0];mi.measured(bank,{'name':'p','zones':[zone({})]},spent)   # 2, and 2 more of the same bank: over 3 (a bound a bank, not a preset)
            rejects(lambda:mi.measured(bank,{'name':'q','zones':[zone({})]},spent))
        finally:mi.MAX_PAIRS=limit
        from musiclib import sf2
        tone=(np.sin(np.arange(4800)/5)*.3).astype(np.float32)
        sf2.write(work/'ins_odd.sf2','odd',[{'name':'t','data':tone,'rate':48000,'root':60}],[{'name':'i','zones':[{'gens':{43:(60,60)},'sample':0},{'gens':{43:(72,72)},'sample':0}]}],
                  [{'name':'Odd Viola','bank':0,'program':128,'zones':[{'gens':{},'instrument':0}]}])
        save_json(work/'ins_odd_config.json',{'soundfont':{'path':str(work/'ins.sf2'),'sha256':file_hash(work/'ins.sf2')},
                                              'soundfonts':{'iowa_strings':{'path':str(work/'ins_odd.sf2'),'sha256':file_hash(work/'ins_odd.sf2')}}})
        odd=mi.search(work/'ins_odd_config.json',['odd'])['presets'][0]
        assert odd['family']=='no General MIDI family' and odd['key_ranges']==[[60,60],[72,72]] and odd['keys_without_a_sample']==11,odd
        # a preset over 120 keys is said to stretch its samples over 120 of the 128 (it was "all keys"); a configuration
        # naming a bank "default" among the others is refused, as doctor refuses it (it was listed: the review of 0.8.0)
        sf2.write(work/'ins_wide.sf2','wide',[{'name':'t','data':tone,'rate':48000,'root':60}],[{'name':'i','zones':[{'gens':{43:(0,119)},'sample':0}]}],
                  [{'name':'Wide Pad','bank':0,'program':88,'zones':[{'gens':{},'instrument':0}]}])
        save_json(work/'ins_wide_config.json',{'soundfont':{'path':str(work/'ins_wide.sf2'),'sha256':file_hash(work/'ins_wide.sf2')}})
        wide=mi.search(work/'ins_wide_config.json',['wide'])
        assert '120 of the 128 keys' in wide['presets'][0]['every_key'] and '(stretched over 120 keys' in mi.summary(wide),wide['presets'][0]
        save_json(work/'ins_named_default.json',{'soundfont':{'path':str(work/'ins.sf2'),'sha256':file_hash(work/'ins.sf2')},
                                                 'soundfonts':{'default':{'path':str(work/'ins_wide.sf2'),'sha256':file_hash(work/'ins_wide.sf2')}}})
        try:mi.search(work/'ins_named_default.json',['wide']);raise AssertionError('a bank named default among the others listed')
        except ValueError as e:assert '(not "default")' in str(e),str(e)
        try:mi.search(work/'ins_odd_config.json',['iowa_strings','viloa']);raise AssertionError('a misspelt word matched')
        except ValueError as e:assert "did you mean 'viola'?" in str(e),str(e)   # not 'strings', a piece of the bank's name
        try:mi.search(work/'ins_odd_config.json',[],bank='nowhere');raise AssertionError('an unknown bank searched')
        except ValueError as e:assert "No configured bank is named 'nowhere'; the configuration names default, iowa_strings" in str(e),str(e)
        assert [r['preset'] for r in mi.search(work/'ins_odd_config.json',[],bank='iowa_strings')['presets']]==['Odd Viola']
        sf2.write(work/'ins_two.sf2','two',[{'name':'t','data':tone,'rate':48000,'root':60}],[{'name':'i','zones':[{'gens':{43:(60,60)},'sample':0},{'gens':{43:(72,72)},'sample':0}]}],
                  [{'name':f'Two {k}','bank':0,'program':k,'zones':[{'gens':{},'instrument':0}]} for k in range(2)])
        save_json(work/'ins_two_config.json',{'soundfont':{'path':str(work/'ins.sf2'),'sha256':file_hash(work/'ins.sf2')},'soundfonts':{'two':{'path':str(work/'ins_two.sf2'),'sha256':file_hash(work/'ins_two.sf2')}}})
        limit=mi.MAX_PAIRS;mi.MAX_PAIRS=3
        try:rejects(lambda:mi.search(work/'ins_two_config.json',[],bank='two'))   # 2 pairs a preset, 4 in its bank: search bounds the bank
        finally:mi.MAX_PAIRS=limit
        return {'found':'default 0:41 Test Viola, keys G3-G4, 2 velocity ranges','misspelt':'viloa -> viola','measured':'keys and velocities overlapping together, global zones',
                'review':'the same walk','bound':'a bank\'s pairs together'}
    def own_folder_and_sfz_build_banks():
        # 0.8 step 3 (design-0.8.md): `soundbank.py folder` builds one preset from a folder of one's own samples named by
        # a template (each pitch from {note}, checked; levels matched; the velocity range shared evenly by the dynamics,
        # given softest first), and `soundbank.py sfz` one from an SFZ instrument in the documented subset (a zone a
        # region, its levels and pitch as written; what lies outside the subset named in the receipt); each keeps the
        # licence stated in the bank and its receipt.
        import subprocess,sys
        import soundbank as sb
        from musiclib import loop,sf2
        src=work/'own_src';(src/'samples').mkdir(parents=True);t=np.arange(int(1.2*48000))/48000
        tone=lambda midi,a:(sum(np.sin(2*np.pi*440*2**((midi-69)/12)*h*t)/h for h in range(1,6))*np.exp(-t*2)*np.minimum(1,t/.005)*a).astype(np.float32)
        for name,midi in (('C4',60),('G4',67)):
            for dyn,a in (('p',.08),('f',.4)):sb.write_float_wav(src/'samples'/f'pno_{name}_{dyn}.wav',np.stack([tone(midi,a)]*2,1),48000)
        loop.write_wav(src/'samples'/'held note.wav',np.stack([tone(64,.2)]*2,1),24000,48000)   # a sample holding its own loop (smpl)
        def run(*a):
            return subprocess.run([sys.executable,str(SCRIPTS.joinpath('soundbank.py')),*map(str,a)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        lic="CC0 (the check's own tones)"
        folder=lambda tag,*a:run('folder',src/'samples','--template','pno_{note}_{dyn}.wav','--name','Own Piano','--program',0,'--license',lic,'--output',work/f'own_{tag}.sf2','--receipt',work/f'own_{tag}.json',*a)
        r=folder('one','--dynamics','p,f')
        assert r.returncode==0 and 'Keys with a sample: Bb3-A4.' in r.stdout and 'p 1-64, f 65-127' in r.stdout,r.stderr[-400:]
        receipt=json.loads((work/'own_one.json').read_text(encoding='utf-8'));bank=sf2.read(work/'own_one.sf2')
        assert receipt['license']==lic and receipt['folder_spec']['presets'][0]['layers'][0]['velocity']=={'p':[1,64],'f':[65,127]} and lic.encode() in (work/'own_one.sf2').read_bytes()
        assert [(p['name'],p['bank'],p['program']) for p in bank['presets']]==[('Own Piano',0,0)] and len({x['file'] for x in receipt['files'] if 'skipped' not in x and 'file' in x})==4
        for tag,args,words in (('two',(),'softest first'),('three',('--dynamics','f'),'the folder holds f, p'),('four',('--dynamics','p,f','--keys','70-60'),'LOW-HIGH'),
                               ('one',('--dynamics','p,f'),'Choose new output')):
            r=folder(tag,*args);assert r.returncode==2 and words in r.stderr and 'Traceback' not in r.stderr,(tag,r.stderr[-300:])
        r=run('folder',src/'samples','--template','pno_{id}.wav','--name','X','--program',0,'--license',lic,'--output',work/'own_id.sf2','--receipt',work/'own_id.json')
        assert r.returncode==2 and '{note}' in r.stderr,r.stderr[-300:]
        r=folder('keys','--dynamics','p,f','--keys','55-72');assert r.returncode==0 and 'Keys with a sample: G3-C5.' in r.stdout,(r.stdout,r.stderr[-300:])
        # An SFZ: comments (each holding what would be an opcode), #define, #include, default_path, <global> and <group>
        # defaults (a later level wins), crossfades over keys and velocities (made splits: SF2 has no crossfade, and
        # layers left overlapping both sound), note names with sharps and flats, a sample's name with a space, SFZ 1's
        # spellings, tune, transpose, volume, offset and end (one file in two regions, each its own span), loop points
        # and modes (the file's own loop under an offset), the envelope, group and off_by; a <curve> and a cutoff,
        # outside the subset, named as not used.
        (src/'more.sfz').write_text('<group> lovel=49 hivel=127 xfin_lovel=49 xfin_hivel=80 group=1 off_by=2\n'
                                    '<region> sample=pno_C4_f.wav lokey=57 hikey=eb4 pitch_keycenter=60 offset=100 end=40000\n'
                                    '<region> sample=pno_G4_f.wav lokey=59 hikey=70 xfin_lokey=59 xfin_hikey=g#4 pitch_keycenter=55 transpose=12 cutoff=2000 group=2\n',encoding='utf-8')
        (src/'own.sfz').write_text('// a test instrument: sample=nothing.wav\n/* two velocity groups,\n   lokey=0 for none */\n#define $SOFT 49\n<control> default_path=samples/\n'
                                   '<global> ampeg_release=0.3\n<group> lovel=1 hivel=80 xfout_lovel=$SOFT xfout_hivel=80\n'
                                   '<region> sample=pno_C4_p.wav lokey=a3 hikey=d#4 pitch_keycenter=c4 // hikey=99\n'
                                   '<region> sample=pno_G4_p.wav lokey=64 hikey=70 pitch_keycenter=67 tune=20 volume=-3 loopmode=loop_sustain loop_start=24000 loopend=47999 ampeg_release=0.5\n'
                                   '#include "more.sfz"\n<group> lovel=1 hivel=127 ampeg_release=0.2\n<region> sample=held note.wav key=e4 ampeg_sustain=50 ampeg_delay=0.05 offset=1000\n'
                                   '<region> sample=pno_C4_f.wav key=50 pitch_keycenter=60 end=20000\n<curve> curve_index=1\n',encoding='utf-8')
        r=run('sfz',src/'own.sfz','--name','Own SFZ','--program',0,'--license',lic,'--output',work/'own_sfz.sf2','--receipt',work/'own_sfz.json')
        assert r.returncode==0 and 'cutoff (1)' in r.stdout and 'curve (1)' in r.stdout,(r.stdout,r.stderr[-400:])
        # the crossfades over velocities 49-80 and keys 59-68 as splits at their middles (64 | 65, 63 | 64), named
        assert all(f'{words}: each crossfade is a split at its middle' in r.stdout for words in
                   ('1 region of keys 59-70 play keys 64-70','2 regions of velocities 1-80 play velocities 1-64','2 regions of velocities 49-127 play velocities 65-127')),r.stdout
        receipt=json.loads((work/'own_sfz.json').read_text(encoding='utf-8'));bank=sf2.read(work/'own_sfz.sf2')
        assert receipt['license']==lic and receipt['sfz_not_used']=={'headers':{'curve':1},'opcodes':{'curve_index':1,'cutoff':1}},receipt['sfz_not_used']
        zones=[]
        for pz in bank['presets'][0]['zones']:
            inst=bank['instruments'][pz['target']];top=inst['zones'][0]['gens'] if inst['zones'][0]['target'] is None else {}
            zones+=[{**top,**z['gens'],'sample':bank['samples'][z['target']]} for z in inst['zones'] if z['target'] is not None]
        assert len(zones)==12 and all(zones[k][17]==-zones[k+1][17]==-500 for k in range(0,12,2)),len(zones)   # a stereo take: its left and right zones
        zones=zones[::2];got=[(z[43],z[44],z[58],z.get(52,0),z.get(54,0),z.get(57,0)) for z in zones]
        assert got==[((57,63),(1,64),60,0,0,0),((64,70),(1,64),67,20,3,0),((57,63),(65,127),60,0,0,1),((64,70),(65,127),43,0,0,1),((64,64),(1,127),64,0,1,0),
                     ((50,50),(1,127),60,0,0,0)],got
        assert [z[38] for z in zones]==[sf2.timecents(s) for s in (.3,.5,.3,.3,.2,.2)],[z[38] for z in zones]   # the global's release; a region's, a group's over it
        assert zones[4][37]==round(10*20*np.log10(2)) and zones[4][33]==sf2.timecents(.05) and all(33 not in z for z in zones[:4]),zones[4]   # a sustain of 50 %; a delay
        g=[x['requested_gain_db'] for x in receipt['files'] if x.get('file','').endswith(('pno_C4_p.wav','pno_G4_p.wav')) and 'skipped' not in x]
        assert len(g)==2 and abs(g[1]-g[0]+3)<.01,g   # volume=-3 as written, the levels not matched
        s=zones[2]['sample'];assert s['end']-s['start']==39901,(s['start'],s['end'])   # offset 100 to end 40000, both kept
        s=zones[5]['sample'];assert s['end']-s['start']==20001,(s['start'],s['end'])   # the same file to end 20000: a take of its own
        s=zones[1]['sample'];assert s['loop'][1]-s['loop'][0]==24000   # points
        s=zones[4]['sample'];assert s['loop'][1]-s['loop'][0]==24000 and s['loop'][0]-s['start']==23000,(s['start'],s['loop'])   # the file's own, less the offset
        (src/'bad.sfz').write_text('<region> sample=../outside.wav\n',encoding='utf-8');(work/'outside.wav').write_bytes((src/'samples'/'held note.wav').read_bytes())
        (src/'mode.sfz').write_text('<region> sample=samples/held note.wav loop_mode=loop_backward\n',encoding='utf-8')
        (src/'short.sfz').write_text('<region> sample=samples/held note.wav end=30000\n',encoding='utf-8')   # the file's loop runs to 48000
        (src/'self.sfz').write_text('#include "self.sfz"\n',encoding='utf-8')
        for name,words in (('bad.sfz','leads out of --root'),('mode.sfz','loop_mode'),('short.sfz','cuts into the recorded loop'),('self.sfz','through #include')):
            r=run('sfz',src/name,'--name','X','--program',0,'--license',lic,'--output',work/f'own_{name}.sf2','--receipt',work/f'own_{name}.json')
            assert r.returncode==2 and words in r.stderr and 'Traceback' not in r.stderr,(name,r.stderr[-300:])
        # The rules of reading the third outside review found missing, each an SFZ the code before read otherwise
        # (sfz_spec in this process; nothing is built).
        cases=work/'own_cases'
        for d in ('s','A','B','inc','dyn'):(cases/d).mkdir(parents=True)
        for d in ('s','A','B'):(cases/d/'x.wav').write_bytes((src/'samples'/'pno_C4_p.wav').read_bytes())
        (cases/'held.wav').write_bytes((src/'samples'/'held note.wav').read_bytes())   # its own loop, 24000-48000
        def spec(text):
            (cases/'case.sfz').write_text(text,encoding='utf-8');return sb.sfz_spec(cases/'case.sfz',cases,'X',0,lic)
        layers=lambda text:spec(text)[0]['presets'][0]['layers']
        L=layers('<region>key=64 sample=s/x.wav\n<region>sample=s/x.wav key=65')   # a header and an opcode with no space between
        assert [(l['keys'],l['root']) for l in L]==[([64,64],64),([65,65],65)],L
        assert len(layers('// /*\n<region> sample=s/x.wav key=60\n// */\n'))==1   # a /* inside a line comment starts nothing
        L=layers('<group> lokey=50 hikey=70 pitch_keycenter=60\n<region> sample=s/x.wav key=64\n<region> sample=s/x.wav pitch_keycenter=62 key=64')
        assert [(l['keys'],l['root']) for l in L]==[([64,64],64),([64,64],62)],L   # key over what is inherited; its own header's pitch_keycenter over key
        L=layers('<control> default_path=A/\n<region> sample=x.wav\n<control> default_path=B/\n<region> sample=x.wav\n<control>\n<region> sample=s/x.wav')
        assert [l['dir'] for l in L]==['A','B','s'],L   # each default_path for the regions after it; a new <control> resets it
        (cases/'inc'/'a.sfz').write_text('#include "inc/b.sfz"\n',encoding='utf-8');(cases/'inc'/'b.sfz').write_text('<region> sample=s/x.wav key=61\n',encoding='utf-8')
        assert [l['keys'] for l in layers('#include "inc/a.sfz"\n')]==[[61,61]]   # an include in an include, named from the main file's folder
        L=layers('<region> sample=held.wav key=64 loop_start=200\n<region> sample=held.wav key=64 loop_end=39999')
        assert [l.get('loop_points') for l in L]==[[200,48000],[24000,40000]],L   # each loop point the SFZ gives, over the file's own
        L=layers('<region> sample=s/x.wav group=0 off_by=0\n<region> sample=s/x.wav group=01 off_by=1\n<region> sample=s/x.wav group=1\n'
                 '<region> sample=s/x.wav off_by=7\n<region> sample=s/x.wav group=7\n<region> sample=s/x.wav')
        assert [l.get('exclusive_class') for l in L]==[None,1,1,2,2,None],L   # numbers, 0 none; a region of no group cut by 7 apart from group 0
        L=layers(''.join(f'<region> sample=s/x.wav group={k} off_by={k+1}\n' for k in range(1,1101)))   # a chain of 1,100 groups: one class
        assert {l['exclusive_class'] for l in L}=={1},{l['exclusive_class'] for l in L}
        L=layers('<region> sample=s/x.wav xfin_lovel=64 xfin_hivel=64\n<region> sample=s/x.wav tune=.5 transpose=+1 volume=+3')
        assert L[0]['velocity']=={'default':[65,127]} and (L[1]['tune_cents'],L[1]['root'],round(20*np.log10(L[1]['gain']),6))==(.5,59,3.0),L
        sp,left=spec('<region> sample=s/x.wav end=-1 group=3\n<region> sample=s/x.wav off_by=3')
        assert len(sp['presets'][0]['layers'])==1 and any('end=-1' in n for n in left['approximated']),left   # a region that does not play, left out and said
        # and the region it cut gets no exclusive class, nor one whose off_by names a group no region plays in: a class
        # of its own made its notes cut each other, a chord lost its first notes (the review of 0.8.0)
        assert 'exclusive_class' not in sp['presets'][0]['layers'][0],sp['presets'][0]['layers'][0]
        assert 'exclusive_class' not in layers('<region> sample=s/x.wav lokey=60 hikey=72 off_by=99')[0]
        import os
        outside=work/'own_outside';outside.mkdir();(outside/'x.wav').write_bytes(b'');(outside/'y.sfz').write_text('<region> sample=s/x.wav\n',encoding='utf-8')
        junction=(subprocess.run(['cmd','/c','mklink','/J',str(cases/'j'),str(outside)],capture_output=True).returncode==0 if os.name=='nt'
                  else (os.symlink(outside,cases/'j',target_is_directory=True) or True))
        assert junction
        doubling='#define $A x\n'+''.join(f'#define ${"A"*k} ${"A"*(k-1)}${"A"*(k-1)}\n' for k in range(2,24))+'<region> sample=$'+'A'*23   # 391 bytes to 4 MB
        for text,words in (('<region> sample=s/x.wav volume=100000','outside -144.6 to 24'),('<region> sample=s/x.wav tune='+'9'*400,'is outside'),
                           ('<region> sample=s/x.wav xfin_lovel=80 xfin_hivel=40','xfin_hivel below xfin_lovel'),('<region> sample=s/x.wav xfin_lovel=200','outside 0 to 127'),
                           ('#include "../case.sfz"\n','leads out of --root'),('<region> sample=../x.wav','leads out of --root'),
                           ('#include "j/y.sfz"\n','is a link or a junction'),('<region> sample=j/x.wav','is a link or a junction'),
                           (doubling,'once its #define names are replaced')):
            try:spec(text);raise AssertionError(f'taken: {text[:80]!r}')
            except ValueError as e:assert words in str(e),(words,str(e)[:300])
        for k in range(128):(cases/'dyn'/f'n_C4_d{k}.wav').write_bytes(b'')   # names only: folder_spec reads none
        try:sb.folder_spec(cases/'dyn','n_{note}_{dyn}.wav','X',0,lic,[f'd{k}' for k in range(128)]);raise AssertionError('128 dynamics taken')
        except ValueError as e:assert '127 velocities' in str(e),str(e)
        for field,value in (('span',[.5,5]),('span',[0]),('span',[True,5]),('tune_cents','20'),('tune_cents',10**400),('onset_db',10**400),
                            ('loop','points'),('loop_points',['a',5])):   # the builder's step 3 fields, checked before any reading (no OverflowError)
            try:sb.naming({'presets':[{'name':'p','layers':[{'template':'x.wav','root':60,field:value}]}]});raise AssertionError(f'{field}={value!r} taken')
            except ValueError as e:assert f'`{field}`' in str(e) or 'loop_points' in str(e),str(e)
        sb.naming({'presets':[{'name':'p','layers':[{'dir':'.','template':'x.wav','root':60,'loop':'points','loop_points':[0,None],
                                                     'dynamics':['default'],'keys':'auto','velocity':{'default':[1,127]}}]}]})   # null: to the end kept
        # The fourth outside review's cases: a main file below the root, and one reached through a junction; key after
        # bounds in its own header; a loop with no loop_end on a sample with none of its own (to the sample's end), and
        # points with no loop_mode on such a sample (unlooped, said); text grown past the bound by the lines after a
        # replaced one; silent samples alone; 127 dynamics taken where 128 are not.
        (cases/'prog').mkdir();(cases/'prog'/'main.sfz').write_text('<region> sample=../s/x.wav key=60\n',encoding='utf-8')
        assert [l['dir'] for l in sb.sfz_spec(cases/'prog'/'main.sfz',cases,'X',0,lic)[0]['presets'][0]['layers']]==['s']
        (outside/'main.sfz').write_text('<region> sample=x.wav\n',encoding='utf-8')
        try:sb.sfz_spec(cases/'j'/'main.sfz',cases,'X',0,lic);raise AssertionError('a main file through a junction taken')
        except ValueError as e:assert 'is a link or a junction' in str(e),str(e)
        # The whole review of 0.8: a root named through a junction (an alias) is the root, resolved once; a junction between
        # it and the main file is refused through the command as through sfz_spec (both resolved the root first, and a main
        # file named through the alias passed unchecked); one named through the alias with none on the way is taken, and
        # one named from neither spelling of the root is refused
        def dir_link(at,to):
            return (subprocess.run(['cmd','/c','mklink','/J',str(at),str(to)],capture_output=True).returncode==0 if os.name=='nt'
                    else (os.symlink(to,at,target_is_directory=True) or True))
        aka,aka2=work/'own_alias',work/'own_alias2';assert dir_link(aka,cases) and dir_link(aka2,cases) and dir_link(cases/'jp',cases/'prog')
        try:sb.sfz_spec(aka/'jp'/'main.sfz',aka,'X',0,lic);raise AssertionError('a main file through a junction behind an aliased root taken')
        except ValueError as e:assert 'jp is a link or a junction' in str(e),str(e)
        r=run('sfz',aka/'jp'/'main.sfz','--root',aka,'--name','X','--program',0,'--license',lic,'--output',work/'own_alias_jp.sf2','--receipt',work/'own_alias_jp.json')
        assert r.returncode==2 and 'jp is a link or a junction' in r.stderr and not (work/'own_alias_jp.sf2').exists(),r.stderr[-300:]
        for named in (aka/'prog'/'main.sfz',cases/'prog'/'main.sfz'):   # through the alias, or by the root's own path, none on the way
            assert [l['dir'] for l in sb.sfz_spec(named,aka,'X',0,lic)[0]['presets'][0]['layers']]==['s'],named
        try:sb.sfz_spec(aka2/'prog'/'main.sfz',aka,'X',0,lic);raise AssertionError('a main file named from neither spelling of the root taken')
        except ValueError as e:assert 'name the .sfz file by a path inside the root' in str(e),str(e)
        # a sample and an include named in another case than their files (SFZ files made where case does not count) are
        # taken by the names their folders list, on every system (Windows and macOS found the file, and the build then
        # matched none: the whole review)
        L=layers('<region> sample=S/X.WAV key=60\n#include "INC/B.SFZ"\n')
        assert [(l['dir'],l['template']) for l in L]==[('s','x.wav'),('s','x.wav')],L
        sb.build(spec('<region> sample=S/X.WAV key=60')[0],cases,work/'own_case.sf2')
        L=layers('<region> sample=s/x.wav lokey=50 hikey=70 key=64');assert (L[0]['keys'],L[0]['root'])==([64,64],64),L
        # <master>, ARIA's level between <global> and <group> (the legato tutorial's programs set their mono there): over
        # the global, under the group, a new one starting afresh
        L=layers('<global> ampeg_release=0.3\n<master> group=1 off_by=1 ampeg_attack=0.1\n<group> ampeg_attack=0.2\n<region> sample=s/x.wav key=60\n'
                 '<region> sample=s/x.wav key=61\n<master>\n<region> sample=s/x.wav key=62')
        assert [(l.get('exclusive_class'),l['envelope']) for l in L]==[(1,{'attack':.2,'release':.3}),(1,{'attack':.2,'release':.3}),(None,{'release':.3})],L
        sp,left=spec('<region> sample=s/x.wav loop_mode=loop_continuous\n<region> sample=s/x.wav loop_start=10 loop_end=99')
        L=sp['presets'][0]['layers']
        assert L[0].get('loop_points')==[0,None] and 'loop' not in L[1] and any('played unlooped' in n for n in left['approximated']),(L,left)
        sb.build(spec('<region> sample=s/x.wav key=60 loop_mode=loop_continuous loop_start=4800')[0],cases,work/'own_to_end.sf2')
        from musiclib import wavfile
        s=sf2.read(work/'own_to_end.sf2')['samples'][0];frames=wavfile.info(cases/'s'/'x.wav')['frames']
        assert s['loop'][0]-s['start']==4800 and s['loop'][1]-s['start']==frames,(s,frames)   # built: the loop runs to the take's last frame
        grow='#define $W '+'w'*1_500_000+'\n<region> sample=s/$W.wav\n<region> sample=s/$W.wav\n<region> sample=s/'+'y'*1_100_000+'.wav\n'
        try:spec(grow);raise AssertionError('text grown past the bound by the line after taken')
        except ValueError as e:assert 'once its #define names are replaced' in str(e),str(e)
        sb.write_float_wav(cases/'s'/'silent.wav',np.zeros((4800,2),np.float32),48000)
        try:sb.build(spec('<region> sample=s/silent.wav key=60')[0],cases,work/'own_silent.sf2');raise AssertionError('silent samples alone built')
        except ValueError as e:assert 'samples are silent' in str(e),str(e)
        (cases/'dyn127').mkdir()
        for k in range(127):(cases/'dyn127'/f'n_C4_d{k}.wav').write_bytes(b'')
        wide=sb.folder_spec(cases/'dyn127','n_{note}_{dyn}.wav','X',0,lic,[f'd{k}' for k in range(127)])['presets'][0]['layers'][0]['velocity']
        assert len(wide)==127 and wide['d0']==[1,1] and wide['d126']==[127,127],wide
        # The review of 0.8.0. A byte order mark before a first-line #include (an editor's UTF-8) and an #include named by
        # a #define are read: the included regions were left out, or looked for under "$part"
        (cases/'case.sfz').write_bytes(b'\xef\xbb\xbf#include "inc/b.sfz"\n<region> sample=s/x.wav key=62\n')
        assert [l['keys'] for l in sb.sfz_spec(cases/'case.sfz',cases,'X',0,lic)[0]['presets'][0]['layers']]==[[61,61],[62,62]]
        assert [l['keys'] for l in layers('#define $part inc/b.sfz\n#include "$part"\n')]==[[61,61]]
        # an #include's name grown by #define names that double at each step is refused before it grows (1 KB made a
        # name of 4 MB, and more steps grew it without end: the Astra review of the fixes for 0.8.0)
        chain='#define $A x\n'+''.join(f'#define ${"A"*(k+1)} ${"A"*k}${"A"*k}\n' for k in range(1,23))+'#include "$'+'A'*23+'"\n'
        try:layers(chain);raise AssertionError('an #include name grown past any path taken')
        except ValueError as e:assert 'grows past' in str(e),str(e)
        # a sample kept from its first frame with a second of silence before its tone builds: it was measured over that
        # second and refused as silent
        late=np.concatenate([np.zeros((48000,2),np.float32),np.stack([(np.sin(2*np.pi*261.63*np.arange(24000)/48000)*.3).astype(np.float32)]*2,1)])
        sb.write_float_wav(cases/'s'/'late.wav',late,48000);sb.build(spec('<region> sample=s/late.wav key=60')[0],cases,work/'own_late.sf2')
        # a take quieter than -80 dBFS throughout is measured from its first sound: it measured 0, so an SFZ of it alone
        # was refused as silent and, beside a louder take in a layer that matches its notes, the match divided by 0; a
        # take of no sound beside sounding ones is refused by its name (the Astra review of the fixes for 0.8.0)
        tone=lambda amp:np.stack([(np.sin(2*np.pi*261.63*np.arange(48000)/48000)*amp).astype(np.float32)]*2,1)
        sb.write_float_wav(cases/'s'/'quiet.wav',tone(.00005),48000);sb.build(spec('<region> sample=s/quiet.wav key=60')[0],cases,work/'own_quiet.sf2')
        pair=work/'own_pair';pair.mkdir()
        sb.write_float_wav(pair/'n_C4.wav',tone(.00005),48000);sb.write_float_wav(pair/'n_D4.wav',tone(.3),48000)
        two={'name':'Pair','presets':[{'name':'Pair','program':0,'layers':[{'dir':'.','template':'n_{note}.wav','dynamics':['default'],'keys':'auto',
                                                                              'velocity':{'default':[1,127]},'onset_db':None,'pitch_check':False}]}]}
        sb.build(two,pair,work/'own_pair.sf2')
        sb.write_float_wav(pair/'n_C4.wav',np.zeros((48000,2),np.float32),48000)
        try:sb.build(two,pair,work/'own_pair_silent.sf2');raise AssertionError('a silent take beside a sounding one built')
        except ValueError as e:assert 'n_C4.wav is silent' in str(e),str(e)
        # and in a layer of two dynamics whose soft take is silent, before "across" or layer_levels_db divides by that
        # dynamic's median (each a division by 0 before the first fix's check: the second Astra review of the fixes)
        dyn=work/'own_dyn';dyn.mkdir()
        sb.write_float_wav(dyn/'n_C4_pp.wav',np.zeros((48000,2),np.float32),48000);sb.write_float_wav(dyn/'n_C4_ff.wav',tone(.3),48000)
        two_dyn={'dir':'.','template':'n_{note}_{dyn}.wav','dynamics':['pp','ff'],'keys':'auto','velocity':{'pp':[1,63],'ff':[64,127]},'onset_db':None,'pitch_check':False}
        for extra in ({'match_notes':'across'},{'layer_levels_db':{'pp':-6}},{'match_notes':False,'layer_levels_db':{'pp':-6}}):
            try:sb.build({'name':'Dyn','presets':[{'name':'Dyn','program':0,'layers':[{**two_dyn,**extra}]}]},dyn,work/'own_dyn.sf2');raise AssertionError(f'a silent dynamic built with {extra}')
            except ValueError as e:assert 'n_C4_pp.wav is silent' in str(e),(extra,str(e))
        # where nothing divides by it, a silent take is kept as before: no match, and a shape of the sounding dynamic
        # only (the guard refused it too: the third Astra review of the fixes)
        sb.build({'name':'Dyn','presets':[{'name':'Dyn','program':0,'layers':[{**two_dyn,'match_notes':False,'layer_levels_db':{'ff':0}}]}]},dyn,work/'own_dyn_kept.sf2')
        # a take whose name gives a key outside MIDI 0-127 is refused by name (Cb-1 stopped the writer with a traceback,
        # B9 built a bank of no sample); a preset name the bank cannot hold is refused; a licence beyond Latin-1 is kept
        # in the receipt as given and in the bank's copyright field as its escapes, and the printout says which
        odd=work/'own_odd';odd.mkdir()
        for note_name in ('Cb-1','B9'):
            (odd/f'p_{note_name}.wav').write_bytes((src/'samples'/'pno_C4_p.wav').read_bytes())
            r=run('folder',odd,'--template','p_{note}.wav','--name','Odd','--program',0,'--license',lic,'--output',work/f'own_odd_{note_name}.sf2','--receipt',work/f'own_odd_{note_name}.json')
            assert r.returncode==2 and 'outside 0-127' in r.stderr and 'Traceback' not in r.stderr and not (work/f'own_odd_{note_name}.sf2').exists(),(note_name,r.stderr[-300:])
            (odd/f'p_{note_name}.wav').rename(odd/f'p_{note_name}.wav.off')
        for bad_name in ('A preset name too long','鋼琴'):
            r=folder('badname','--dynamics','p,f','--name',bad_name)
            assert r.returncode==2 and '19 Latin-1' in r.stderr and not (work/'own_badname.sf2').exists(),(bad_name,r.stderr[-300:])
        wide_lic='錄音授權, CC0'
        r=run('sfz',src/'own.sfz','--name','Own SFZ','--program',0,'--license',wide_lic,'--output',work/'own_wide.sf2','--receipt',work/'own_wide.json')
        assert r.returncode==0 and json.loads((work/'own_wide.json').read_text(encoding='utf-8'))['license']==wide_lic,r.stderr[-300:]
        assert b'\\u9304\\u97f3\\u6388\\u6b0a, CC0\0' in (work/'own_wide.sf2').read_bytes() and 'keeps it as \\u9304' in r.stdout,r.stdout[-400:]
        # a take too short to read its pitch is moved by the octave its layer's measured takes agree on, and a key that
        # leaves MIDI 0-127 that way is refused by its name: +12 wrote a root of 139 into the bank and built, -12 stopped
        # the writer with struct.error (GPT Pro's second review of 0.8.0)
        sine=lambda hz,n:np.stack([(np.sin(2*np.pi*hz*np.arange(n)/48000)*.3).astype(np.float32)]*2,1)
        for tag,takes,short in (('up',(('C4',523.25),('E4',659.26)),'G9'),('down',(('C5',261.63),('E5',329.63)),'C-1')):
            oct_dir=work/f'own_oct_{tag}';oct_dir.mkdir()
            for note_name,hz in takes:sb.write_float_wav(oct_dir/f'n_{note_name}.wav',sine(hz,48000),48000)
            sb.write_float_wav(oct_dir/f'n_{short}.wav',sine(1000,4800),48000)
            octave={'name':'Oct','presets':[{'name':'Oct','program':0,'layers':[{'dir':'.','template':'n_{note}.wav','dynamics':['default'],'keys':'auto',
                                                                                    'velocity':{'default':[1,127]},'onset_db':None}]}]}
            try:sb.build(octave,oct_dir,work/f'own_oct_{tag}.sf2');raise AssertionError(f'a key moved past MIDI 0-127 by the octave fix built ({tag})')
            except ValueError as e:assert f'n_{short}.wav' in str(e) and 'outside 0-127' in str(e),(tag,str(e))
            assert not (work/f'own_oct_{tag}.sf2').exists(),tag
        # a layer's keys, dynamics and velocities, and a preset's layers, are checked before any recording is read: keys or
        # a velocity range given high first left the preset no key or no velocity that plays, and no layers no zone at all,
        # and each built and was published (GPT Pro's second review of 0.8.0)
        base={'dir':'.','template':'x.wav','root':60,'dynamics':['default'],'keys':[60,72],'velocity':{'default':[1,127]}}
        sb.naming({'presets':[{'name':'p','layers':[base]}]})
        for field,value in (('keys',[72,60]),('keys',[0,128]),('keys',[60]),('keys',[60.0,72]),('keys',[True,72]),('keys','all'),
                            ('velocity',{'default':[127,1]}),('velocity',{'pp':[1,127]}),('velocity',{'default':[0,128]}),('velocity',[1,127]),
                            ('dynamics',[]),('dynamics','default'),('dynamics',['p','p'])):
            try:sb.naming({'presets':[{'name':'p','layers':[{**base,field:value}]}]});raise AssertionError(f'{field}={value!r} taken')
            except ValueError as e:assert f'`{field}`' in str(e),(field,value,str(e))
        # keys "auto" with a key_margin below 0 made [62, 58] of one note, and the bank no key that plays (Astra's fifth
        # round); a margin of 0 is taken, and one beside fixed keys, which the build does not read, is left alone
        for margin in (-2,1.5,True,'2'):
            try:sb.naming({'presets':[{'name':'p','layers':[{**base,'keys':'auto','key_margin':margin}]}]});raise AssertionError(f'key_margin={margin!r} taken')
            except ValueError as e:assert '`key_margin`' in str(e),(margin,str(e))
        for keys in ('auto',[60,72]):
            sb.naming({'presets':[{'name':'p','layers':[{**base,'keys':keys,'key_margin':0 if keys=='auto' else -2}]}]})
        (work/'own_revkeys.json').write_text(json.dumps({'name':'K','presets':[{'name':'K','program':0,'layers':[{**two['presets'][0]['layers'][0],'keys':[72,60]}]}]}),encoding='utf-8')
        (work/'own_nolayers.json').write_text(json.dumps({'name':'N','presets':[{'name':'N','program':0,'layers':[]}]}),encoding='utf-8')
        for spec_name,words in (('revkeys','`keys`'),('nolayers','no layers')):
            r=run('build',work/f'own_{spec_name}.json','--root',pair,'--output',work/f'own_{spec_name}.sf2','--receipt',work/f'own_{spec_name}_receipt.json')
            assert r.returncode==2 and words in r.stderr and not (work/f'own_{spec_name}.sf2').exists() and not (work/f'own_{spec_name}_receipt.json').exists(),(spec_name,r.stderr[-300:])
        return {'folder':'2 notes x 2 dynamics, keys Bb3-A4, or G3-C5 as asked; 128 dynamics refused','sfz':'6 regions; a header and 2 opcodes named as not used; 4 refusals',
                'reading':'9 rules and 9 refusals in this process','fields':'4 refused before reading'}
    def aiff_reader():
        # The bank builder's AIFF reader (soundbank.read_aiff) on well-formed files of each kind it takes: AIFF of 8 to
        # 32 bits, AIFC uncompressed ('NONE', 'twos') and little-endian ('sowt'), 1 to 8 channels, 8 to 192 kHz.  AIFF's
        # 8-bit samples are signed, unlike WAV's.  A mutant that refused 8-bit AIFF lived through every check (0.8's
        # mutation analysis, 2026-11-15).  The AIFC files carry the FVER chunk and the compression name AIFC asks for.
        from soundbank import read_aiff
        E=np.array([-1,-.5,0,.25,.5]);S=np.stack([E,E[::-1]],1)
        def ext80(rate):                                     # the sample rate as an 80-bit extended float
            e=int(np.floor(np.log2(rate)));return struct.pack('>HQ',16383+e,int(rate)<<(63-e))
        def aiff_bytes(x,bits,rate,kind=None,order='big',store=None,magic=b'FORM',form=None,sound=True,name=b'',offset=0):
            x=np.asarray(x,dtype=np.float64);x=x[:,None] if x.ndim==1 else x;store=store or bits
            data=b''.join(int(v).to_bytes(store//8,order,signed=True) for v in (x.ravel()*2.0**(store-1)).astype(np.int64))
            comm=struct.pack('>hIh',x.shape[1],len(x),bits)+ext80(rate)
            pstring=bytes([len(name)])+name;pstring+=b'\0'*(len(pstring)%2)   # the compression name: count, text, a pad to even
            if kind is None:head=(form or b'AIFF')+b'COMM'+struct.pack('>I',18)+comm
            else:head=(form or b'AIFC')+b'FVER'+struct.pack('>II',4,0xA2805140)+b'COMM'+struct.pack('>I',22+len(pstring))+comm+kind+pstring
            sound_data=struct.pack('>II',offset,0)+bytes(offset)+data   # SSND: offset and block size, `offset` bytes, the samples
            body=head+(b'SSND'+struct.pack('>I',len(sound_data))+sound_data+(b'\0' if len(sound_data)%2 else b'') if sound else b'')
            return magic+struct.pack('>I',len(body))+body
        E8=np.stack([np.roll(E,k) for k in range(8)],1)        # eight channels, each the five values turned by one more
        cases=[('8m',aiff_bytes(E,8,44100),E[:,None],44100,8),                  # 5 bytes: the sound chunk has its pad byte
               ('16s',aiff_bytes(S,16,44100),S,44100,16),
               ('24m',aiff_bytes(E,24,96000),E[:,None],96000,24),
               ('32s',aiff_bytes(S,32,22050),S,22050,32),
               ('8ch',aiff_bytes(E8,16,48000),E8,48000,16),
               ('sowt',aiff_bytes(S,16,48000,kind=b'sowt',order='little'),S,48000,16),
               ('twos',aiff_bytes(E,16,8000,kind=b'twos'),E[:,None],8000,16),
               ('none24',aiff_bytes(S,24,192000,kind=b'NONE'),S,192000,24),
               # a compression name, as AIFF-C writers give it: 15 bytes with its count (one pad byte) and 6 (none), and
               # sound data after an offset the SSND chunk names (the outside review of 2026-11-15: step 1.5 must keep both)
               ('named',aiff_bytes(S,16,44100,kind=b'NONE',name=b'not compressed'),S,44100,16),
               ('named_even',aiff_bytes(E,24,48000,kind=b'NONE',name=b'none!'),E[:,None],48000,24),
               ('offset',aiff_bytes(S,16,44100,offset=4),S,44100,16)]
        for name,data,want,rate,bits in cases:
            (work/f'aiff08_{name}.aif').write_bytes(data);x,info=read_aiff(work/f'aiff08_{name}.aif')
            assert x.dtype==np.float32 and np.array_equal(x,want.astype(np.float32)),(name,x)
            assert (info['rate'],info['bits'],info['channels'],info['frames'])==(rate,bits,want.shape[1],5),(name,info)
        refusals=[]
        def refused(data,words):
            (work/'aiff08_refused.aif').write_bytes(data)
            try:read_aiff(work/'aiff08_refused.aif')
            except ValueError as e:
                assert words in str(e),(words,str(e));refusals.append(words);return
            raise AssertionError(f'read: {words}')
        refused(aiff_bytes(E,32,44100,kind=b'fl32'),'unsupported AIFF')       # a float AIFC
        refused(aiff_bytes(E,12,44100,store=16),'unsupported AIFF')           # 12 bits, stored in 16
        refused(aiff_bytes(np.repeat(E[:,None],9,1),16,44100),'unsupported AIFF')
        for rate in (7999,192001):refused(aiff_bytes(E,16,rate),'unsupported AIFF')
        refused(aiff_bytes(E,16,44100,magic=b'RIFF'),'not an AIFF file');refused(aiff_bytes(E,16,44100,form=b'AIFX'),'not an AIFF file')
        refused(aiff_bytes(E,16,44100,sound=False),'AIFF without COMM or SSND')
        return {'decoded':len(cases),'refusals':len(refusals)}
    def flac_source_must_be_flac():
        # A file named .flac that is not FLAC (a playlist, another container) is refused before FFmpeg opens it.
        from soundbank import read_audio
        fake=work/'not_flac.flac';fake.write_bytes(b'#EXTM3U\nfile:///etc/passwd\n')
        try:read_audio(fake,ffmpeg='ffmpeg-is-not-started');raise AssertionError('a non-FLAC .flac was read')
        except ValueError as e:assert 'fLaC' in str(e),e
        # one FFmpeg cannot decode, or not in time, is refused by its name: its errors went past the command's handler as
        # a traceback (the whole review of 0.8; FFmpeg's run stood in for here)
        import subprocess as sp
        import soundbank
        real=soundbank.subprocess.run;bad=work/'undecodable.flac';bad.write_bytes(b'fLaC'+bytes(64))
        for fault,words in ((sp.CalledProcessError(1,['ffmpeg']),'could not decode'),(sp.TimeoutExpired(['ffmpeg'],600),'within 600 seconds')):
            def stopped(*a,**k):raise fault
            soundbank.subprocess.run=stopped
            try:
                try:read_audio(bad,ffmpeg='ffmpeg');raise AssertionError('an undecodable FLAC taken')
                except ValueError as e:assert words in str(e) and 'undecodable.flac' in str(e),e
            finally:soundbank.subprocess.run=real
        return {'refused_before_ffmpeg':True}
    def soundfont_tables_must_hold_together():
        # A bank whose header or bag indices run backwards, end short of their table, or name an instrument that is not
        # there is refused, as the SoundFont 2.04 specification (7.2-7.7) and FluidSynth refuse it: indices running back
        # and forth made a 4 KB file expand into thousands of zones.
        import struct
        from musiclib import sf2
        tone=(np.sin(2*np.pi*440*np.arange(4800)/48000)*.5).astype(np.float32)
        sf2.write(work/'three.sf2','three',[{'name':'A4','data':tone,'rate':48000,'root':69}],
                  [{'name':'inst','zones':[{'gens':{43:(0,127)},'sample':0}]}],
                  [{'name':f'p{k}','bank':0,'program':k,'zones':[{'gens':{},'instrument':0}]} for k in range(3)])
        good=(work/'three.sf2').read_bytes();assert len(sf2.read(work/'three.sf2')['presets'])==3
        def broken(edit):
            data=bytearray(good);i=data.find(b'phdr');off=i+8;n=struct.unpack_from('<I',data,i+4)[0]//38
            edit(data,off,n);path=work/'broken.sf2';path.write_bytes(bytes(data));return path
        cases=[lambda d,off,n:struct.pack_into('<H',d,off+1*38+24,0) or struct.pack_into('<H',d,off+0*38+24,1),  # 1, 0, ...
               lambda d,off,n:struct.pack_into('<H',d,off+(n-1)*38+24,2)]  # the terminal record names bag 2, not the last (3)
        for edit in cases:
            try:sf2.read(broken(edit));raise AssertionError('a defective bank was read')
            except ValueError as e:assert 'structurally defective' in str(e),e
        data=bytearray(good);i=data.find(b'pgen');off=i+8;n=struct.unpack_from('<I',data,i+4)[0]//4
        for k in range(n):
            if struct.unpack_from('<H',data,off+4*k)[0]==41:struct.pack_into('<HH',data,off+4*k,41,9)
        (work/'broken.sf2').write_bytes(bytes(data))
        try:sf2.read(work/'broken.sf2');raise AssertionError('a bank naming a missing instrument was read')
        except ValueError as e:assert 'structurally defective' in str(e),e
        return {'refused':3}
    def sf2_tables_by_their_size():
        # A pdta table whose size is no whole number of its records, or that holds more records than the reader takes
        # (sf2.MAX_RECORDS), is refused by its size before it is read.  A mutant that let either through (the test joined
        # by `and`) lived through every check (0.8's second mutation sample, 2026-11-15); 0.8's step 1.1 rewrites this.
        import struct
        from musiclib import sf2
        tone=(np.sin(2*np.pi*440*np.arange(4800)/48000)*.5).astype(np.float32)
        sf2.write(work/'sized.sf2','sized',[{'name':'A4','data':tone,'rate':48000,'root':69}],
                  [{'name':'inst','zones':[{'gens':{43:(0,127)},'sample':0}]}],
                  [{'name':f'p{k}','bank':0,'program':k,'zones':[{'gens':{},'instrument':0}]} for k in range(3)])
        good=(work/'sized.sf2').read_bytes();assert len(sf2.read(work/'sized.sf2')['presets'])==3
        # Two bytes more in the preset headers (38 a record), the LIST and the RIFF sizes grown to match: every other
        # chunk stays where its size says.
        data=bytearray(good);i=data.find(b'phdr');size=struct.unpack_from('<I',data,i+4)[0];at=data.rfind(b'LIST',0,i)
        data[i+8+size:i+8+size]=bytes(2);struct.pack_into('<I',data,i+4,size+2)
        for where in (at+4,4):struct.pack_into('<I',data,where,struct.unpack_from('<I',data,where)[0]+2)
        (work/'sized_odd.sf2').write_bytes(bytes(data))
        try:sf2.read(work/'sized_odd.sf2');raise AssertionError('a table of 38n+2 bytes was read')
        except ValueError as e:assert 'table size' in str(e),e
        real=sf2.MAX_RECORDS;sf2.MAX_RECORDS=3                # the preset headers hold 4 records: three and the end
        try:
            try:sf2.read(work/'sized.sf2');raise AssertionError('a table over MAX_RECORDS was read')
            except ValueError as e:assert 'table size' in str(e),e
        finally:sf2.MAX_RECORDS=real
        assert len(sf2.read(work/'sized.sf2')['presets'])==3
        return {'refused':2}
    def sf2_tables_without_terminal_records():
        # A bank whose generator or modulator table ends without its terminal record (the bag's terminal record then
        # names the table's end) is read as the same bank with it: SoundFont 2.04 asks for the record and FluidSynth
        # accepts its absence (sf2.structure).  The skill's writer always writes it, so no check had read a bank without
        # one; step 1.1's reader must keep taking them (the outside review of 2026-11-15).  Without its terminal record a
        # modulator table of this bank is empty.
        import struct
        from musiclib import sf2
        tone=(np.sin(2*np.pi*440*np.arange(4800)/48000)*.5).astype(np.float32)
        sf2.write(work/'terminal.sf2','terminal',[{'name':'A4','data':tone,'rate':48000,'root':69}],
                  [{'name':'inst','zones':[{'gens':{43:(0,127)},'sample':0}]}],
                  [{'name':'p0','bank':0,'program':0,'zones':[{'gens':{},'instrument':0}]}])
        good=(work/'terminal.sf2').read_bytes();whole=sf2.read(work/'terminal.sf2')
        same=lambda b:{k:b[k] for k in ('presets','instruments','samples')}
        for table,size in ((b'pgen',4),(b'pmod',10),(b'igen',4),(b'imod',10)):
            data=bytearray(good);i=data.find(table);n=struct.unpack_from('<I',data,i+4)[0];at=data.rfind(b'LIST',0,i)
            del data[i+8+n-size:i+8+n];struct.pack_into('<I',data,i+4,n-size)   # the table's last record goes, and the sizes with it
            for where in (at+4,4):struct.pack_into('<I',data,where,struct.unpack_from('<I',data,where)[0]-size)
            path=work/f'terminal_without_{table.decode()}.sf2';path.write_bytes(bytes(data))
            assert same(sf2.read(path))==same(whole),table
        return {'tables':4}
    def sf2_reader_refuses_early_and_keeps_its_forms():
        # 0.8 step 1.1 (design-0.8.md, Part C): the reader locates the pdta tables by name and checks what their counts
        # say (each header table's terminal record against its bag table, each bag table's terminal record against its
        # generator and modulator tables) before it reads a table whose size depends on another, so a bag table of two
        # million records that its header does not name is refused after a few records are read.  What 0.7.0 took stays
        # taken: the tables in any order, two tables at once without their terminal records, a preset of no zones
        # (equal neighbouring indices), a real modulator with a negative amount, negative generator amounts, key ranges
        # as pairs, and the parse's own types; the expected parse is written out here, not read back by the reader.
        import struct,time,tracemalloc
        from musiclib import sf2
        tone=(np.sin(2*np.pi*440*np.arange(4800)/48000)*.5).astype(np.float32)
        sf2.write(work/'kept.sf2','kept',[{'name':'A4','data':tone,'rate':48000,'root':69,'loop':(100,4000)}],
                  [{'name':'inst','mods':[(0x0102,48,-120,0,0)],'zones':[{'gens':{43:(36,72),52:-50,54:1},'sample':0}]}],
                  [{'name':'p0','bank':0,'program':5,'zones':[{'gens':{},'instrument':0}]},{'name':'empty','bank':0,'program':6,'zones':[]}])
        good=(work/'kept.sf2').read_bytes()
        presets=[{'name':'p0','program':5,'bank':0,'zones':[{'gens':{41:0},'mods':[],'target':0}]},
                 {'name':'empty','program':6,'bank':0,'zones':[]}]
        instruments=[{'name':'inst','zones':[{'gens':{},'mods':[(0x0102,48,-120,0,0)],'target':None},
                                             {'gens':{43:(36,72),52:-50,54:1,53:0},'mods':[],'target':0}]}]
        samples=[{'name':'A4','start':0,'end':4800,'loop':(100,4000),'rate':48000,'root':69,'correction':0,'link':0,'type':1}]
        def parse_is_the_written_bank(path):
            b=sf2.read(path)
            assert (b['presets'],b['instruments'],b['samples'])==(presets,instruments,samples),(b['presets'],b['instruments'],b['samples'])
            z=b['instruments'][0]['zones'][1]
            assert all(type(k) is int for p in b['presets']+b['instruments'] for zz in p['zones'] for k in zz['gens']),'generator keys are ints'
            assert type(z['gens'][43]) is tuple and type(b['instruments'][0]['zones'][0]['mods']) is list and type(b['instruments'][0]['zones'][0]['mods'][0]) is tuple
            assert type(b['samples'][0]['loop']) is tuple and json.dumps(sf2.inventory(b))  # the inventory stays JSON
            return b
        parse_is_the_written_bank(work/'kept.sf2')
        def pdta(data,change):
            # The bank with its pdta sub-chunks given to `change` as [(id, payload)], the sizes of the LIST and the RIFF
            # made to match what comes back.
            data=bytearray(data);at=data.find(b'LIST',12)
            while data[at+8:at+12]!=b'pdta':at=data.find(b'LIST',at+8)
            size=struct.unpack_from('<I',data,at+4)[0];subs,pos=[],at+12
            while pos<at+8+size:
                cid,n=struct.unpack_from('<4sI',data,pos);subs.append((cid,bytes(data[pos+8:pos+8+n])));pos+=8+n+(n&1)
            body=b'pdta'+b''.join(cid+struct.pack('<I',len(p))+p+(b'\0' if len(p)&1 else b'') for cid,p in change(subs))
            out=data[:at]+b'LIST'+struct.pack('<I',len(body))+body+data[at+8+size:]
            struct.pack_into('<I',out,4,len(out)-8);return bytes(out)
        (work/'kept_reordered.sf2').write_bytes(pdta(good,lambda s:s[::-1]))   # shdr first, phdr last
        parse_is_the_written_bank(work/'kept_reordered.sf2')
        size={b'pgen':4,b'igen':4,b'pmod':10,b'imod':10}
        for gone in ((b'pgen',b'igen'),(b'pmod',b'imod'),(b'igen',b'imod')):   # two terminal records missing at once
            (work/'kept_short.sf2').write_bytes(pdta(good,lambda s:[(c,p[:-size[c]] if c in gone else p) for c,p in s]))
            parse_is_the_written_bank(work/'kept_short.sf2')
        def refused(data,words,label):
            (work/'kept_bad.sf2').write_bytes(data)
            try:sf2.read(work/'kept_bad.sf2')
            except ValueError as e:
                assert words in str(e),(label,str(e));return str(e)
            raise AssertionError(f'read: {label}')
        # A bag index that runs back inside its table, both ends right: refused (unsigned differences would hide it).
        def back(s):
            out=[]
            for c,p in s:
                if c==b'ibag':
                    recs=[list(struct.unpack_from('<HH',p,4*k)) for k in range(len(p)//4)];recs[1][0]=recs[2][0]+1
                    p=b''.join(struct.pack('<HH',*r) for r in recs)
                out.append((c,p))
            return out
        refused(pdta(good,back),'structurally defective','an instrument bag index running back')
        # Several faults: the error is the first the specification's order reaches (the preset tables before the
        # instrument tables), as in 0.7.0.
        both=pdta(good,lambda s:[(c,p+bytes(4) if c in (b'pbag',b'ibag') else p) for c,p in s])
        assert 'preset' in refused(both,'structurally defective','both bag tables a record long')
        def faults(phdr=None,inst_end=None,pbag_gen_end=None,pbag_mod_end=None):   # the preset headers' bag indices; the last instrument's; the last preset bag's generator and modulator indices
            def change(s):
                out=[]
                for c,p in s:
                    if c==b'phdr' and phdr:p=b''.join(p[38*k:38*k+24]+struct.pack('<H',x)+p[38*k+26:38*k+38] for k,x in enumerate(phdr))
                    if c==b'inst' and inst_end is not None:p=p[:-2]+struct.pack('<H',inst_end)
                    if c==b'pbag' and pbag_gen_end is not None:p=p[:-4]+struct.pack('<H',pbag_gen_end)+p[-2:]
                    if c==b'pbag' and pbag_mod_end is not None:p=p[:-2]+struct.pack('<H',pbag_mod_end)
                    out.append((c,p))
                return out
            return pdta(good,change)
        # a preset header running back beside an instrument header's wrong end, and beside a preset bag's wrong end
        assert 'preset header' in refused(faults(phdr=(1,0,1),inst_end=1),'structurally defective','a preset header back, an instrument end wrong')
        assert 'preset header' in refused(faults(phdr=(1,0,1),pbag_gen_end=7),'structurally defective','a preset header back, a preset bag end wrong')
        assert 'instrument header' in refused(faults(inst_end=1),'structurally defective','an instrument end wrong')
        assert 'generator table' in refused(faults(pbag_gen_end=7,pbag_mod_end=9),'structurally defective','both of a bag\'s ends wrong')   # generators before modulators, as 0.7
        # The early refusal: a preset bag table of two million records (8 MB) that the header's terminal record does not
        # name, and a generator table likewise.  Each is refused having read the headers and a few records.
        class Counting:
            def __init__(self,f):self.f,self.bytes,self.spans=f,0,[]
            def read(self,k=-1):at=self.f.tell();b=self.f.read(k);self.bytes+=len(b);self.spans.append((at,at+len(b)));return b
            def seek(self,*a):return self.f.seek(*a)
            def __enter__(self):return self
            def __exit__(self,*a):self.f.close()
        out={}
        for table,label in ((b'pbag','preset bags'),(b'pgen','preset generators')):
            data=pdta(good,lambda s:[(c,bytes(4*2_000_000) if c==table else p) for c,p in s])
            begin=data.find(table,data.find(b'pdta'))+8;forbidden=(begin,begin+8_000_000)   # not a byte of the table read
            (work/'kept_huge.sf2').write_bytes(data);opened=[]
            sf2.open=lambda p,mode='rb':opened.append(Counting(open(p,mode))) or opened[-1]   # the reader opens with open()
            tracemalloc.start();began=time.perf_counter()
            try:
                try:sf2.read(work/'kept_huge.sf2');raise AssertionError(f'read: {label}')
                except ValueError as e:assert 'structurally defective' in str(e),(label,str(e))
                seconds=time.perf_counter()-began;peak=tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop();del sf2.open
            read=sum(c.bytes for c in opened)
            # within 1 s and 50 MB of traced allocations (tracemalloc: Python's, not the process's); the bytes read are
            # the RIFF and LIST headers, INFO and a few records, against 8 MB in the table
            assert opened and read<65536 and seconds<1 and peak<50e6,(label,read,round(seconds,3),peak)
            assert not [s for c in opened for s in c.spans if s[0]<forbidden[1] and s[1]>forbidden[0]],(label,[c.spans for c in opened])
            out[label]={'bytes_read':read,'peak_kb':round(peak/1024)}
        return {'forms_kept':6,'refused':3,'early':out}
    def stored_patch_changes_the_named_take_alone():
        # `stored_patch` (0.9.1): numbers added to named takes as stored.  The take is the plain build's plus the numbers,
        # word for word; every other sample is the plain build's; a preset sharing the recording without the field keeps it
        # as it was, whichever comes first, also where the two gains only round alike and the plain build stores one set of
        # words for both; a dynamic layer made from the preset plays the patched take; the receipt's ids are the samples that
        # hold it; and whatever the numbers were not made for is refused, for its own reason, with no bank written and, where
        # the field itself is wrong, no recording read: among them a take no key or velocity plays (it would be left out in
        # silence) and a first layer whose words are others than those the numbers were made for.
        import hashlib
        import fetch_soundbanks as fb
        import soundbank as sb
        from musiclib import sf2
        from musiclib.model import digest
        from soundbank import StoredPatchMismatch,build
        root=work/'stored_patch_source';folder=work/'stored_patch_files';root.mkdir(parents=True,exist_ok=True);folder.mkdir(exist_ok=True)
        (root/'rr').mkdir(exist_ok=True)
        rate=44100;t=np.arange(rate)/rate
        tone=lambda f0,amp:np.stack([amp*np.exp(-t*3)*np.sin(2*np.pi*f0*t),.8*amp*np.exp(-t*3)*np.sin(2*np.pi*1.002*f0*t)],1)
        for name,f0,amp in (('p_A3',220.0,.4),('p_C4',261.63,.3),('rr/A3_ff_1',222.0,.3),('rr/A3_ff_2',224.0,.3)):
            audio.write_wav(root/f'{name}.wav',tone(f0,amp),rate)
        layer={'dir':'.','template':'p_{note}.wav','dynamics':['default'],'velocity':{'default':[1,127]},'keys':[55,62],'pitch_check':False}
        word=lambda bank,i:np.round(sf2.load_sample(bank,i).astype(np.float64)*32768).astype(np.int64)
        def stored(path):   # {(bank, program): {sample name: its 16-bit words}}
            bank=sf2.read(path);out={}
            for p in bank['presets']:
                one=out.setdefault((p['bank'],p['program']),{})
                for pz in p['zones']:
                    for z in (bank['instruments'][pz['target']]['zones'] if pz['target'] is not None else ()):
                        if z['target'] is not None:
                            one[bank['samples'][z['target']]['name']]=word(bank,z['target'])
            return out
        receipts={}
        def made(name,layers,rms=.05,**preset):
            receipts[name]=build({'name':name,'target_rms':rms,'presets':[{'name':f'p{i}','program':i,'layers':[l],**preset} for i,l in enumerate(layers)]},
                                 root,work/f'{name}.sf2',patch_folder=folder)
            return stored(work/f'{name}.sf2')
        def patch(name,takes):
            doc={'comment':'a test','takes':takes}
            (folder/f'{name}.json').write_text(json.dumps(doc),encoding='utf-8')
            return {'file':f'{name}.json','digest':digest(doc)}
        same=lambda got,ref:set(got)==set(ref) and all(np.array_equal(got[k],ref[k]) for k in ref)
        plain=made('patch_plain',[layer])[(0,0)]
        assert set(plain)=={'p_A3L','p_A3R','p_C4L','p_C4R'},sorted(plain)
        adds={'L':(100,[5,-13,3,0,11]),'R':(400,[-2,9])}
        channels=[{'before_sha256':hashlib.sha256(plain['p_A3'+c].astype('<i2').tobytes()).hexdigest(),'start':a,'add':d} for c,(a,d) in adds.items()]
        good=patch('good',{'p_A3.wav':channels})
        want={k:v.copy() for k,v in plain.items()}
        for c,(a,d) in adds.items():
            want['p_A3'+c][a:a+len(d)]+=np.asarray(d)
        def receipt_is_true(name,stem='p_A3',words=None):   # each id the receipt gives is the sample that holds that channel of the
            words=words or want                             # patched take, and a zone plays it at a velocity of that row
            bank=sf2.read(work/f'{name}.sf2');rows=[r for r in receipts[name]['files'] if r.get('stored_patch')];assert rows,name
            for r in rows:
                lo,hi=r['velocities']
                for side,c in zip('LR',r['stored_patch']['channels']):
                    assert bank['samples'][c['sample']]['name']==stem+side and np.array_equal(word(bank,c['sample']),words[stem+side]),(name,side,c)
                    assert any(z['target']==c['sample'] and z['gens'][44][0]<=hi and z['gens'][44][1]>=max(lo,1)
                               for i in bank['instruments'] for z in i['zones']),(name,r['serves_dynamic'],c)
        assert same(made('patch_on',[{**layer,'stored_patch':good}])[(0,0)],want)
        receipt_is_true('patch_on')
        rows=[r for r in receipts['patch_on']['files'] if r.get('stored_patch')]
        assert len(rows)==1 and rows[0]['file']=='p_A3.wav' and rows[0]['stored_patch']['digest']==good['digest'],rows
        assert [{k:v for k,v in c.items() if k!='sample'} for c in rows[0]['stored_patch']['channels']]==[
            {'from_frame':100,'frames':5,'words_changed':4,'largest_change':13},{'from_frame':400,'frames':2,'words_changed':2,'largest_change':9}],rows
        on={**layer,'stored_patch':good}
        for order,pair in enumerate(((on,dict(layer)),(dict(layer),on))):
            got=made(f'patch_two_{order}',list(pair));receipt_is_true(f'patch_two_{order}')
            assert same(got[(0,0)],want if order==0 else plain) and same(got[(0,1)],plain if order==0 else want),order
        # Two gains that round alike: a plain build stores the first's words for both, and the numbers go on those words.
        near=1+4e-7
        assert not same(made('patch_near_alone',[{**layer,'gain':near}])[(0,0)],plain)      # alone, the second gain stores other words
        for name,pair,ref in (('patched_first',(on,{**layer,'gain':near}),(want,plain)),('plain_first',(dict(layer),{**on,'gain':near}),(plain,want)),
                              ('both',(on,{**on,'gain':near}),(want,want))):
            got=made(f'patch_near_{name}',list(pair));receipt_is_true(f'patch_near_{name}')
            assert same(got[(0,0)],ref[0]) and same(got[(0,1)],ref[1]),name
        # Two patches on one take: each preset holds its own numbers.
        other=patch('other',{'p_A3.wav':[{**channels[0],'add':[29,-13,3,0,11]},channels[1]]})
        other_want={**want,'p_A3L':want['p_A3L'].copy()};other_want['p_A3L'][100]+=24
        got=made('patch_two_kinds',[on,{**layer,'stored_patch':other}])
        assert same(got[(0,0)],want) and same(got[(0,1)],other_want)
        assert [r['stored_patch']['channels'][0]['largest_change'] for r in receipts['patch_two_kinds']['files'] if r.get('stored_patch')]==[13,29]
        # Gains that round alike in the key and not in what is stored (the lift; the gain the receipt gives): a plain preset
        # beside a patched one keeps the first's figures and attenuation, as in a plain build.
        one={**layer,'template':'p_A3.wav','root':57,'match_notes':False}
        loaded,_,medians=sb._load_layer(one,root.resolve(),None,{},{'files':[]},sb.template_parts(one['template'],'a test'))
        peak=float(np.abs(loaded[0]['x']).max())
        shown=lambda g,full:int(min(36.0,20*np.log10(.98/(peak*g)))*10/sf2.EMU_ATTENUATION) if full else round(20*np.log10(g),2)
        def straddle(full):
            for n in range(100,650):
                g=.98/(peak*10**(n*sf2.EMU_ATTENUATION/200)) if full else 10**((-n*.01-.005)/20)
                if round(g-1.2e-7,6)==round(g+1.2e-7,6) and shown(g-1.2e-7,full)!=shown(g+1.2e-7,full):return g-1.2e-7,g+1.2e-7
            raise AssertionError('no two such gains')
        def figures(name,program):
            bank=sf2.read(work/f'{name}.sf2');p=next(x for x in bank['presets'] if (x['bank'],x['program'])==(0,program))
            return ([(r['applied_gain_db'],r.get('stored_lift_db')) for r in receipts[name]['files'] if r.get('preset')==f'p{program}'],
                    [z['gens'].get(48) for pz in p['zones'] for z in bank['instruments'][pz['target']]['zones'] if z['target'] is not None])
        for full in (False,True):
            pair=[{**one,'gain':g,'full_scale':full} for g in straddle(full)]
            words=made(f'patch_step_plain_{full}',pair,rms=medians['default'])[(0,0)]
            step=patch(f'step_{full}',{'p_A3.wav':[{'before_sha256':hashlib.sha256(words['p_A3'+c].astype('<i2').tobytes()).hexdigest(),'start':10,'add':[3]} for c in 'LR']})
            made(f'patch_step_{full}',[{**pair[0],'stored_patch':step},pair[1]],rms=medians['default'])
            assert figures(f'patch_step_{full}',1)==figures(f'patch_step_plain_{full}',1),(full,figures(f'patch_step_{full}',1)[0])
            made(f'patch_step_second_{full}',[pair[0],{**pair[1],'stored_patch':step}],rms=medians['default'])   # the patched one second: the first's figures too
            assert figures(f'patch_step_second_{full}',1)==figures(f'patch_step_plain_{full}',1),(full,figures(f'patch_step_second_{full}',1)[0])
        derived=made('patch_derived',[on],dynamic_layers={'bank':16})
        assert len(derived)==2 and all(same(v,want) for v in derived.values()),sorted(derived)
        refusals=[]
        def refused(why,field,rms=.05,kind=ValueError,**extra):
            try:made('patch_refused',[{**layer,'stored_patch':field,**extra}],rms=rms)
            except kind as e:assert why in str(e),(why,str(e))
            else:raise AssertionError(f'not refused: {why}')
            refusals.append(why)
        second=lambda **c:[channels[0],{**channels[1],**c}]
        refused('its digest differs',{**good,'digest':'0'*64})
        for field in ({},None,'good.json',{'file':'good.json'},{**good,'extra':1},{**good,'file':'good.txt'},{**good,'digest':'ABC'}):
            refused('`stored_patch` is {',field)
        for name in ('../good.json','a/good.json','CON.json'):
            refused('a name of letters',{**good,'file':name})
        refused('is missing from',{**good,'file':'absent.json'})
        refused('does not have',patch('lacks',{'p_B3.wav':channels}))
        refused('channels, the patch',patch('one_channel',{'p_A3.wav':channels[:1]}))
        refused('no key or velocity',good,keys=[60,62])                               # A3 is loaded and outside the keys
        rr={'dir':'rr','template':'{note}_{dyn}_{rr}.wav','dynamics':['ff'],'velocity':{'ff':[121,127]},'rr_block':8}    # one block of velocities, two takes
        wide=made('patch_rr_wide',[{**layer,**rr,'velocity':{'ff':[1,127]}}])[(0,0)]  # where the second take is played, to read its words
        rr_patch=lambda name,take:patch(name,{f'rr/A3_ff_{take}.wav':[{'before_sha256':hashlib.sha256(wide[f'A3_ff_{take}{c}'].astype('<i2').tobytes()).hexdigest(),
                                                                       'start':10,'add':[3]} for c in 'LR']})
        far=rr_patch('rr',2)
        refused('no key or velocity',far,**rr)
        refused('no key or velocity',rr_patch('rr_zero',1),**{**rr,'velocity':{'ff':[0,1]},'rr_block':1})   # its one velocity is 0, a note's end in MIDI
        try:made('patch_refused',[{**layer,**rr,'velocity':{'ff':[1,127]},'stored_patch':far},{**layer,**rr,'stored_patch':far}])     # the first preset plays it, the second cannot
        except ValueError as e:assert 'no key or velocity' in str(e),str(e)
        else:raise AssertionError('a layer that cannot play the take let by on an earlier preset\'s zones')
        refusals.append('each layer its own zones')
        try:build({'name':'x','target_rms':.05,'presets':[{'name':'p','program':0,'layers':[{**layer,**rr,'velocity':{'ff':[1,127]},'stored_patch':far},
                                                                                          {**layer,**rr,'stored_patch':far}]}]},root,work/'patch_refused.sf2',patch_folder=folder)
        except ValueError as e:assert 'no key or velocity' in str(e),str(e)                # the same, between two layers of one preset
        else:raise AssertionError('a layer that cannot play the take let by on another layer of its preset')
        refusals.append('each layer its own zones')
        rr_first={k:v.copy() for k,v in wide.items()}
        for c in 'LR':rr_first['A3_ff_1'+c][10]+=3
        made('patch_zero_row',[{**layer,**rr,'dynamics':['soft','ff'],'velocity':{'soft':[0,0],'ff':[1,127]},'stored_patch':rr_patch('rr_first',1)}])   # heard in ff, at 0 alone in soft
        assert [r['serves_dynamic'] for r in receipts['patch_zero_row']['files'] if r.get('stored_patch')]==['ff']
        receipt_is_true('patch_zero_row','A3_ff_1',rr_first)
        rr_want={k:v.copy() for k,v in wide.items()}
        for c in 'LR':rr_want['A3_ff_2'+c][10]+=3
        made('patch_borrowed',[{**layer,**rr,'dynamics':['soft','ff'],'velocity':{'soft':[1,60],'ff':[121,127]},'stored_patch':far}])  # played only where it is borrowed
        assert [r['serves_dynamic'] for r in receipts['patch_borrowed']['files'] if r.get('stored_patch')]==['soft']
        receipt_is_true('patch_borrowed','A3_ff_2',rr_want)
        # A preset made from the layer (`dynamic_layers`, `legato`) gives each round robin blocks of 16 velocities of its own, so it
        # can play a take the main preset leaves out: that take is used, and is taken with its numbers, the receipt naming the
        # banks that play it.  One that none of them plays, or that only another layer's presets play, is still refused.
        for sub,here in (('gen',(('A3_soft_1',221.0,.12),('A3_ff_1',222.0,.3),('A3_ff_2',224.0,.3))),('nine',tuple((f'A3_ff_{n}',222.0+n,.3) for n in range(1,10)))):
            (root/sub).mkdir(exist_ok=True)
            for name,f0,amp in here:audio.write_wav(root/sub/f'{name}.wav',tone(f0,amp),rate)
        versions={'dynamic_layers':{'bank':16},'legato':{'bank':32,'attack':.01}}
        one_word=lambda name,words,take,stem:patch(name,{take:[{'before_sha256':hashlib.sha256(words[stem+c].astype('<i2').tobytes()).hexdigest(),'start':10,'add':[3]} for c in 'LR']})
        gen={**layer,'dir':'gen','template':'{note}_{dyn}_{rr}.wav','dynamics':['soft','ff'],'velocity':{'soft':[1,120],'ff':[121,127]},'rr_block':8}
        gen_plain=made('patch_gen_plain',[gen],**versions)
        assert 'A3_ff_2L' not in gen_plain[(0,0)] and 'A3_ff_2L' not in gen_plain[(16,0)] and 'A3_ff_2L' in gen_plain[(17,0)],sorted(gen_plain)
        assert 'stored_patch' not in receipts['patch_gen_plain']['derived'][0]
        gen_patch=one_word('gen',gen_plain[(17,0)],'gen/A3_ff_2.wav','A3_ff_2')
        gen_got=made('patch_gen',[{**gen,'stored_patch':gen_patch}],**versions)
        gen_want={k:{n:w.copy() for n,w in v.items()} for k,v in gen_plain.items()}
        for b in (17,33):
            for c in 'LR':gen_want[(b,0)]['A3_ff_2'+c][10]+=3
        assert set(gen_got)==set(gen_want) and all(same(gen_got[k],gen_want[k]) for k in gen_want),sorted(gen_got)
        assert not any(r.get('stored_patch') for r in receipts['patch_gen']['files'])                     # no row of the main preset plays it
        gen_rows=receipts['patch_gen']['derived'][0]['stored_patch']
        assert [(r['file'].replace('\\','/'),r['banks'],r['digest']) for r in gen_rows]==[('gen/A3_ff_2.wav',[17,33],gen_patch['digest'])],gen_rows
        gen_bank=sf2.read(work/'patch_gen.sf2')
        for side,c in zip('LR',gen_rows[0]['channels']):
            assert {k:v for k,v in c.items() if k!='sample'}=={'from_frame':10,'frames':1,'words_changed':1,'largest_change':3},c
            assert gen_bank['samples'][c['sample']]['name']=='A3_ff_2'+side and np.array_equal(word(gen_bank,c['sample']),gen_want[(17,0)]['A3_ff_2'+side]),c
            for p in gen_bank['presets']:                                                                 # the banks it names are those that play it
                plays=any(z['target']==c['sample'] and z['gens'][44][1]>=1 for pz in p['zones'] for z in gen_bank['instruments'][pz['target']]['zones'])
                assert plays==(p['bank'] in (17,33)),(p['bank'],c)
        assert [r['banks'] for r in receipts['patch_derived']['derived'][0]['stored_patch']]==[[16]],receipts['patch_derived']['derived']   # played by both: named in both
        assert [r for r in receipts['patch_derived']['files'] if r.get('stored_patch')]
        nine={**layer,'dir':'nine','template':'{note}_{dyn}_{rr}.wav','dynamics':['ff'],'velocity':{'ff':[121,127]},'rr_block':8}
        nine_words=made('patch_nine_wide',[{**nine,'velocity':{'ff':[1,127]},'rr_block':1}])[(0,0)]
        made('patch_nine_eighth',[{**nine,'stored_patch':one_word('nine8',nine_words,'nine/A3_ff_8.wav','A3_ff_8')}],**versions)     # the eighth has the last block
        try:made('patch_refused',[{**nine,'stored_patch':one_word('nine9',nine_words,'nine/A3_ff_9.wav','A3_ff_9')}],**versions)
        except ValueError as e:assert 'no key or velocity' in str(e),str(e)
        else:raise AssertionError('a ninth round robin, which no preset gives a block, taken in silence')
        refusals.append('no preset made from the layer')
        try:build({'name':'x','target_rms':.05,'presets':[{'name':'p','program':0,**versions,'layers':[{**layer,'keys':[60,62],'stored_patch':good},{**layer,'stored_patch':good}]}]},
                  root,work/'patch_refused.sf2',patch_folder=folder)
        except ValueError as e:assert 'no key or velocity' in str(e),str(e)
        else:raise AssertionError("a layer that cannot play the take let by on another layer's presets")
        refusals.append('each layer its own presets')
        twice=build({'name':'x','target_rms':.05,'presets':[{'name':'p','program':0,**versions,'layers':[{**layer,'stored_patch':good},{**layer,'stored_patch':good}]}]},
                    root,work/'patch_two_layers.sf2',patch_folder=folder)
        assert [r['banks'] for r in twice['derived'][0]['stored_patch']]==[[16,32]],twice['derived']   # one take in two layers: one row, each bank once
        def misplaced(where):
            p={'name':'p','program':0,'layers':[dict(layer)]};s={'name':'x','target_rms':.05,'presets':[p]}
            if where=='recipe':s['stored_patch']=good
            elif where=='preset':p['stored_patch']=good
            elif where=='inside a layer':p['layers'][0]['envelope']={'stored_patch':good}
            else:p['dynamic_layers']={'bank':16,'stored_patch':good}
            return s
        for where in ('recipe','preset','deeper','inside a layer'):                   # anywhere but a layer it would do nothing
            try:build(misplaced(where),root,work/'patch_refused.sf2',patch_folder=folder)
            except ValueError as e:assert 'belongs on a layer' in str(e),str(e)
            else:raise AssertionError(f'a field on the {where}: a plain bank, in silence')
            refusals.append('placement')
        refused('names no take',patch('empty',{}))
        refused('was made for',good,rms=.06,kind=StoredPatchMismatch)                 # the recording stored at another level
        refused('was made for',good,gain=near,kind=StoredPatchMismatch)               # the first layer's words are the second gain's
        flipped=plain['p_A3R'].copy();flipped[1000]+=1                                # a channel one word away from its words
        refused('was made for',patch('one_word',{'p_A3.wav':second(before_sha256=hashlib.sha256(flipped.astype('<i2').tobytes()).hexdigest())}),
                kind=StoredPatchMismatch)
        # A wrong field on a later preset stops the build before the first preset's recordings are read.
        reader=sb.read_audio;opened=[]
        sb.read_audio=lambda *a,**k:(opened.append(a[0]),reader(*a,**k))[1]
        try:
            for bad in ({},None,{**good,'digest':'0'*64},{**good,'file':'absent.json'},patch('late_number',{'p_A3.wav':second(start=-1)})):
                try:made('patch_refused',[dict(layer),{**layer,'stored_patch':bad}])
                except ValueError as e:assert 'stored_patch' in str(e) or '.json' in str(e),str(e)
                else:raise AssertionError(f'not refused: {bad}')
                refusals.append('before any recording')
        finally:sb.read_audio=reader
        assert not opened,(len(opened),'recordings read before a wrong field was refused')
        last=len(plain['p_A3R'])-1
        ends=made('patch_end',[{**layer,'stored_patch':patch('to_the_end',{'p_A3.wav':second(start=last,add=[1])})}])[(0,0)]['p_A3R']
        assert ends[last]==plain['p_A3R'][last]+1 and np.array_equal(ends[:last],plain['p_A3R'][:last])   # a span may end on the last frame
        refused('runs to frame',patch('past',{'p_A3.wav':second(start=last,add=[1,1])}))
        refused('outside 16 bits',patch('over',{'p_A3.wav':second(start=int(np.argmax(plain['p_A3R'])),add=[32767])}))
        refused('outside 16 bits',patch('under',{'p_A3.wav':second(start=int(np.argmin(plain['p_A3R'])),add=[-32768])}))
        for bad in ({'add':[1.5]},{'add':[True]},{'add':[]},{'add':[32768]},{'add':[-32769]},{'start':-1},{'start':1.0},{'before_sha256':'x'}):
            refused('a list of whole numbers',patch('bad',{'p_A3.wav':second(**bad)}))
        assert not (work/'patch_refused.sf2').exists()
        # Through the installer the same refusal names the take and says what to do about it, as a bank that misses its hash does.
        kept=sb.PATCH_FOLDER
        try:
            sb.PATCH_FOLDER=folder
            try:fb.build_bank({'name':'x','output_sha256':'0'*64},{'name':'x','target_rms':.06,'presets':[{'name':'p','program':0,'layers':[{**layer,'stored_patch':good}]}]},
                              root,work/'patch_installer.sf2',None)
            except ValueError as e:assert all(s in str(e) for s in ('p_A3.wav','was made for','NumPy','Install the prebuilt bank')),str(e)
            else:raise AssertionError('the installer built on words the patch was not made for')
        finally:sb.PATCH_FOLDER=kept
        assert not (work/'patch_installer.sf2').exists()
        return {'channels_patched':len(channels),'numbers':sum(len(d) for _,d in adds.values()),'refused':len(refusals)}
    def the_steinway_patch_is_as_described():
        # The correction the vcsl recipe names, read as the build reads it: on the Steinway's layer alone, for its take at G#5
        # in three dynamics and two channels; nothing in the first 3 ms or from 0.35 s (at 44.1 kHz, frames 133 to 15,434);
        # each span starts and ends on a word it changes, and the numbers are as many as the notes on it count.
        from soundbank import PATCH_FOLDER,read_stored_patch
        spec=json.loads((PATCH_FOLDER/'vcsl.json').read_text(encoding='utf-8'))
        fields=[(p['name'],l) for p in spec['presets'] for l in p['layers'] if 'stored_patch' in l]
        assert [name for name,_ in fields]==['Grand Steinway B'],[name for name,_ in fields]
        layer=fields[0][1];takes=read_stored_patch(layer['stored_patch'])
        assert sorted(takes)==[f"{layer['dir']}/JHPiano_NoSus_Close_G#5_vl{v}_rr1.wav" for v in (2,3,4)],sorted(takes)
        assert all(len(c)==2 for c in takes.values())
        channels=[c for v in takes.values() for c in v]
        assert all(c['start']>=133 and c['start']+len(c['add'])<=15435 and c['add'][0]!=0 and c['add'][-1]!=0 for c in channels)
        numbers,changed=sum(len(c['add']) for c in channels),sum(v!=0 for c in channels for v in c['add'])
        assert (numbers,changed)==(72529,60694),(numbers,changed)
        first,last=min(c['start'] for c in channels),max(c['start']+len(c['add'])-1 for c in channels)   # both of them words it changes
        assert (first,last)==(137,12671),(first,last)
        return {'takes':len(takes),'numbers':numbers,'words_changed':changed,'first_frame':first,'last_frame':last}
    found = {'sf2_writer_reader_roundtrip': sf2_roundtrip, 'sf2_inventory_reports_keys_layers_seconds_and_loops': sf2_inventory, 'soundbank_builds_a_kit_with_microphones_and_choke': kit_build, 'soundbank_keeps_recorded_loops_and_evens_takes': loop_build, 'soundbank_levels_every_dynamic_of_a_note_together': across_levels, 'soundbank_builds_dynamic_layers_and_legato_presets': expressive_bank, 'soundbank_ring_db_keeps_each_take_to_its_own_decay': ring_cut, 'soundbank_denoise_keeps_each_layers_partials': denoise_keeps_each_layers_partials, 'split_finds_each_note_of_a_chromatic_run': split_run, 'split_reads_a_high_passed_copy_and_leaves_out_takes': split_highpass, 'a_soft_take_made_from_the_loud_one': soft_take_from_the_loud_one, 'settled_bands_are_closed_once': settled_bands_are_closed_once, 'full_scale_storage_keeps_the_level_heard': full_scale_keeps_the_level, 'stored_patch_changes_the_named_take_alone': stored_patch_changes_the_named_take_alone, 'the_steinway_patch_is_as_described': the_steinway_patch_is_as_described,'soundbank_tunes_split_notes_and_quiets_borrowed_dynamics': split_bank, 'noise_reduction_lowers_hiss_and_keeps_the_note': noise_reduction, 'click_repair_takes_out_a_knock_and_keeps_the_ring': click_repair, 'denoise_keeps_a_soft_low_note_out_of_the_rumble': denoise_keeps_low_partials, 'noise_profile_reads_gated_and_breathy_recordings': noise_profile, 'split_keeps_the_note_not_its_faint_ring': split_ignores_faint_rings, 'a_cut_manifest_writes_only_inside_its_folder': files_stay_inside, 'wav_readers_decode_each_encoding_and_keep_their_header_rules': wav_readers, 'wav_readers_keep_their_policies_on_the_same_bytes': wav_policies_side_by_side, 'bank_files_named_by_template': bank_files_named_by_template, 'bank_build_opens_no_link_below_its_root': bank_build_opens_no_link_below_its_root, 'bank_cut_checks_each_span_first': bank_cut_checks_each_span_first, 'aiff_reader_walks_headers_and_refuses_what_it_cannot_hold': aiff_reader_walks_headers_and_refuses_what_it_cannot_hold, 'sounds_search_names_what_it_does_not_know': sounds_search_names_what_it_does_not_know, 'instruments_reads_keys_and_layers_from_the_bank': instruments_reads_keys_and_layers_from_the_bank, 'own_folder_and_sfz_build_banks': own_folder_and_sfz_build_banks,'aiff_reader_decodes_each_kind_it_takes': aiff_reader, 'flac_source_must_be_flac': flac_source_must_be_flac, 'soundfont_tables_must_hold_together': soundfont_tables_must_hold_together, 'sf2_tables_are_refused_by_their_size': sf2_tables_by_their_size, 'sf2_tables_may_end_without_their_terminal_records': sf2_tables_without_terminal_records, 'sf2_reader_refuses_early_and_keeps_its_forms': sf2_reader_refuses_early_and_keeps_its_forms}
    if config:
        def preset_list_matches_the_banks():
            # 0.8 step 2.6: what `instruments` reads from each configured bank against references/soundbank-presets.md, row
            # by row: the same keys (a sharp and its flat alike; drum kits by MIDI number) for every preset the list gives.
            from musiclib import instruments as ins,sf2
            norm=lambda s:s.replace('–','-').replace('♯','#').replace('♭','b')
            flat=lambda k:ins.note(k);sharp=lambda k:f'{["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"][k%12]}{k//12-1}'
            banks=ins.banks(config);checked=0;rows=ins.documented()
            assert len(rows)>=60,len(rows)   # the list itself is read: a table it no longer parsed would check nothing
            # Each row of a bank this setup has: one with the default bank alone (bootstrap.py --system, as CI's Ubuntu and
            # macOS jobs) has none of the listed banks, and the check asked for 60 rows and the strings there (the whole review)
            for (name,b,pr),row in rows.items():
                if name not in banks:continue
                bank=sf2.read(banks[name]);preset=next(x for x in bank['presets'] if x['bank']==b and x['program']==pr)
                keys,_=ins.measured(bank,preset);lo,hi=min(keys),max(keys)
                assert norm(row['keys']) in (f'{flat(lo)}-{flat(hi)}',f'{sharp(lo)}-{sharp(hi)}',f'{lo}-{hi}'),(name,b,pr,row,lo,hi);checked+=1
            if 'iowa_strings' in banks:
                found=ins.search(config,['violin'])
                assert any(r['bank']=='iowa_strings' and r['patch']=={'bank':0,'program':40} and r['keys']=='G3-B7' for r in found['presets'])
            return {'rows_checked':checked}
        def flac_sources_decode_within_a_limit():
            # A FLAC source is decoded to at most a second past soundbank.MAX_SOURCE_SECONDS and refused when longer,
            # so the temporary WAV stays bounded whatever the file holds (here with the limit set to 2 s).
            import soundbank
            cfg=audio.load_config(config);wav=work/'three_seconds.wav';audio.write_wav(wav,np.zeros((3*audio.RATE,2),dtype=np.float32))
            audio.ffmpeg(cfg,['-i',wav,'-c:a','flac',work/'three_seconds.flac'],work/'logs_flac','to_flac')
            x,_=soundbank.read_audio(work/'three_seconds.flac',cfg['ffmpeg']['path']);assert len(x)==3*audio.RATE,len(x)
            limit=soundbank.MAX_SOURCE_SECONDS
            try:
                soundbank.MAX_SOURCE_SECONDS=2
                try:soundbank.read_audio(work/'three_seconds.flac',cfg['ffmpeg']['path']);raise AssertionError('a FLAC over the limit was read')
                except ValueError as e:assert 'cut it first' in str(e),e
            finally:soundbank.MAX_SOURCE_SECONDS=limit
            return {'limit_s':limit}
        found.update({'preset_list_keys_match_the_banks': preset_list_matches_the_banks, 'flac_sources_decode_within_a_limit': flac_sources_decode_within_a_limit})
    return found
