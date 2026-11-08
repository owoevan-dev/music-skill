"""Observable invariants and optional real render/revision tests. Not a taste test."""
import argparse
import copy
import io
import json
import os
from pathlib import Path
import shutil
import struct
import tarfile
import tempfile
import time
import zipfile
import numpy as np
from make_example import example
from excerpt import extract
from bootstrap import safe_extract,safe_extract_tar,surge_platform,has_vorbis as setup_has_vorbis
from soundbank import yin_f0
from musiclib import midi,audio
from musiclib.model import Clock,TPQ,validate,performed,save_json,file_hash,cc_events

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

def checks(work,config=None):
    work=Path(work).resolve();work.mkdir(parents=True,exist_ok=True);results=[]
    def check(name,fn):
        began=time.monotonic()
        try:
            details=fn();results.append({'name':name,'passed':True,'details':details,'seconds':round(time.monotonic()-began,3)})
            print('PASS',name,flush=True)
        except Exception as e:
            results.append({'name':name,'passed':False,'error':repr(e)});save_json(work/'selfcheck_report.json',{'status':'FAIL','checks':results});raise
    def rejects(fn):
        try:fn()
        except ValueError:return True
        raise AssertionError('Expected rejection')
    def clock_roundtrip():
        p=example();p['clock']={'bars':8,'meter':[6,8],'tempo':[[0,99],[5.5,76],[12,112],[22,68]],'tail_seconds':3};c=Clock(p)
        for beat in [0,.125,5.49,5.5,5.501,11.9,12,22,24]:assert abs(c.beat(c.seconds(beat))-beat)<1e-9
        assert c.beats_per_bar==3
        return {'quarter_beats_per_6_8_bar':3,'tested_breakpoints':9}
    check('shared_tempo_clock_and_compound_meter',clock_roundtrip)
    def invalid():
        p=example();p['tracks'][0]['performance']['notes'].pop(next(iter(p['tracks'][0]['performance']['notes'])));rejects(lambda:validate(p))
        p=example();p['clock']['tempo']=[[0,108],[0,120]];rejects(lambda:validate(p))
        p=example();p['tracks'][2]['instrument']={'harmonics':100000};rejects(lambda:validate(p))
        p=example();p['tracks'][0]['notes'][0]['pitch']=128;rejects(lambda:validate(p))
        # A key struck twice at once is found by validate, before any render, with both notes and where they are.
        p=example();t=p['tracks'][0];n=copy.deepcopy(t['notes'][0]);n['id']+='_again';t['notes'].append(n)
        t['performance']['notes'][n['id']]=dict(t['performance']['notes'][t['notes'][0]['id']])
        try:
            validate(p);raise AssertionError('a key struck twice at once passed validation')
        except ValueError as e:
            assert t['notes'][0]['id'] in str(e) and n['id'] in str(e) and ' bar ' in str(e),str(e)
        # A phaser's rate is FFmpeg aphaser's speed, 0.1 to 2 Hz: outside it a project passed and its render failed.
        for rate,ok in ((.05,False),(.1,True),(2,True),(2.5,False)):
            p=example();p['tracks'][0]['mix']['effects']=[{'type':'phaser','rate_hz':rate,'depth':.5}]
            if ok:validate(p)
            else:rejects(lambda:validate(p))
        # The text review reads, of another type, is refused before review stops on it (found by GPT Pro's third review).
        for change in (lambda p:p.__setitem__('brief',{'mood':'warm'}),lambda p:p.__setitem__('decisions',None),
                       lambda p:p['tracks'][0]['notes'][0].__setitem__('phrase',['A']),lambda p:p['tracks'][0].__setitem__('role',['melody'])):
            p=example();change(p);rejects(lambda p=p:validate(p))
        # A project, or its clock, mix, tracks, sections, tempo, harmony, notes or performance, of another JSON type is
        # refused with its place, and any other field of the wrong type as that: they raised AttributeError or TypeError
        # and stopped the command (found by CI on Python 3.14, which parsed a deeply nested list).
        for q in ([],'x',1,None):rejects(lambda q=q:validate(q))
        first=lambda p:p['tracks'][0]['notes'][0]['id']
        for change,place in ((lambda p:p.__setitem__('clock',[]),'clock'),(lambda p:p.__setitem__('mix','x'),'mix'),
                             (lambda p:p.__setitem__('tracks','x'),'tracks'),(lambda p:p.__setitem__('tracks',[1]),'track'),
                             (lambda p:p.__setitem__('sections',[1]),'section'),(lambda p:p['clock'].__setitem__('tempo',[1]),'tempo'),
                             (lambda p:p.__setitem__('harmony',[1]),'harmony'),(lambda p:p['tracks'][0].__setitem__('notes',[1]),'note'),
                             (lambda p:p['tracks'][0].__setitem__('performance',[]),'performance'),
                             (lambda p:p['tracks'][0]['performance'].__setitem__('notes',[]),'performance.notes'),
                             (lambda p:p['tracks'][0].__setitem__('mix',[]),'mix'),
                             (lambda p:p['tracks'][0]['performance']['notes'].__setitem__(first(p),1),'performance.notes'),
                             (lambda p:p['tracks'][0]['performance'].__setitem__('cc',[1]),'wrong type'),
                             (lambda p:p['tracks'][0].__setitem__('range',5),'wrong type')):
            p=example();change(p)
            try:validate(p);raise AssertionError(f'{place} of the wrong type passed validation')
            except ValueError as e:assert place in str(e),str(e)
        return {'invalid_cases_rejected':29}
    check('malformed_projects_rejected',invalid)
    def midi_roundtrip():
        p=example();path=work/'roundtrip.mid';routing=midi.write(p,path);m=midi.read(path);clock=Clock(p)
        for t,parsed in zip(p['tracks'],m['tracks'][1:]):
            expected=sorted([(n['tick'],n['end_tick'],n['pitch'],n['velocity']) for n in performed(t,clock)])
            actual=sorted([(n['tick'],n['end_tick'],n['pitch'],n['velocity']) for n in parsed['notes']])
            assert expected==actual and not parsed['unclosed'] and not parsed['stray_offs']
            assert any(e[1]>>4==11 and e[2:]==[64,0] for e in parsed['events'])
        return {'tracks':len(routing),'notes':sum(len(t['notes']) for t in m['tracks'])}
    check('performed_midi_roundtrip_and_pedal_release',midi_roundtrip)
    def ports():
        p=example();base=copy.deepcopy(p['tracks'][0]);p['tracks']=[]
        for i in range(20):t=copy.deepcopy(base);t['id']='part_'+str(i);t['program']=i;p['tracks'].append(t)
        midi.write(p,work/'ports.mid');m=midi.read(work/'ports.mid');addresses=[(t['notes'][0]['port'],t['notes'][0]['channel']) for t in m['tracks'][1:]]
        assert len(set(addresses))==20 and all(ch!=9 for port,ch in addresses) and any(port==1 for port,ch in addresses)
        return {'distinct_melodic_addresses':20}
    check('more_than_15_melodic_parts_have_distinct_ports',ports)
    def malformed_midi():
        path=work/'bad.mid';path.write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,960)+b'MTrk'+struct.pack('>I',1)+b'\x00')
        rejects(lambda:midi.read(path));path.write_bytes(b'not midi');rejects(lambda:midi.read(path))
        good=work/'roundtrip.mid';rejects(lambda:midi.read(good,max_bytes=10))
        # The skill reads its own exports back bounded by their size, not by the limits for MIDI from elsewhere: a
        # project may hold 500,000 notes, a million note events before its controllers, which is the million a file
        # from elsewhere may hold.  (Found by a review of 0.4.0.)
        p=example();p.pop('harmony',None);p['clock']['bars']=64;p['sections']=[{'id':'a','start_bar':0,'bars':64}];t=p['tracks'][0];p['tracks']=[t]
        t['notes']=[{'id':f'x{k}','on':round(k*.08,2),'duration':.05,'pitch':48+k%12} for k in range(3000)]
        t['performance']={'notes':{n['id']:{'velocity':80} for n in t['notes']},'cc':[]};validate(p);midi.write(p,work/'many.mid')
        rejects(lambda:midi.read(work/'many.mid',max_events=6000))
        assert sum(len(x['notes']) for x in midi.read_own(work/'many.mid')['tracks'])==3000
        return {'bad_cases_rejected':3,'own_export_read_by_its_size':True}
    check('bounded_untrusted_midi_reader',malformed_midi)
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
        # Every pinned Surge build names its archive, hashes and the binary to check; this machine maps to one or none.
        pinned=json.loads((Path(__file__).resolve().parents[1]/'references'/'runtime-lock.json').read_text(encoding='utf-8'))['optional']['surge_xt']
        for key in ('windows-x86_64','linux-x86_64','macos-universal'):
            item=pinned[key]
            assert item['url'].endswith('/'+item['filename']) and len(item['sha256'])==64 and len(item['executable_sha256'])==64
            assert item['executable'].startswith(item['extract']) and item['bytes']>1e7
        assert surge_platform() in (None,'windows-x86_64','linux-x86_64','macos-universal')
        return True
    check('archive_cannot_escape_destination',zip_traversal)
    def wav_roundtrip():
        a=np.column_stack([np.linspace(-.25,.25,4096),np.linspace(.2,-.2,4096)]).astype(np.float32)
        audio.write_wav(work/'wav_roundtrip.wav',a);b,info=audio.read_wav(work/'wav_roundtrip.wav');assert np.array_equal(a,b)
        return info
    check('float_wav_roundtrip',wav_roundtrip)
    def noise_timing():
        p=example();t=p['tracks'][-1];n=t['notes'][0];t['performance']['notes'][n['id']].update(timing_ms=50,gate=.5)
        audio.noise_fx(p,t,work/'noise.wav');a,_=audio.read_wav(work/'noise.wav');actual=performed(t,Clock(p))[0]
        begin=round(actual['start_seconds']*audio.RATE);end=round(actual['end_seconds']*audio.RATE)
        assert np.max(np.abs(a[:begin]))==0 and np.max(np.abs(a[end:]))==0 and np.max(np.abs(a[begin:end]))>0
        return {'actual_start_frame':begin,'actual_end_frame':end}
    check('noise_engine_obeys_performance_timing_and_gate',noise_timing)
    def excerpt_clock():
        p=example();q=extract(p,3,2);validate(q);a=Clock(p);b=Clock(q)
        assert q['clock']['tempo'][0]==[0,112] and abs(b.end-(a.seconds(16)-a.seconds(8)))<1e-8
        assert q['sections'][0]['start_bar']==0 and q['clock']['bars']==2
        return {'bars':2,'notes':sum(len(t['notes']) for t in q['tracks'])}
    check('excerpt_preserves_tempo_and_score_bounds',excerpt_clock)
    def render_patch_and_key_map():
        p=example();d=p['tracks'][3];d['patch']={'bank':0,'program':0};d['key_map']={'36':48,'38':50};validate(p)
        midi.write(p,work/'export.mid');midi.write(p,work/'synth.mid',[d],single_stem=True,render=True)
        export=[t for t in midi.read(work/'export.mid')['tracks'] if t['name']=='drums'][0];synth=midi.read(work/'synth.mid')['tracks'][1]
        assert {n['channel'] for n in export['notes']}=={9} and {n['pitch'] for n in export['notes']}=={36,38}
        assert {n['channel'] for n in synth['notes']}=={0} and {n['pitch'] for n in synth['notes']}=={48,50}
        assert len(synth['notes'])==len(export['notes'])
        return {'export_channel':9,'render_channel':0,'mapped':{'36':48,'38':50}}
    check('render_patch_and_key_map_leave_export_authored',render_patch_and_key_map)
    def cc_modes():
        p=example();t=p['tracks'][0];t['performance']['cc']=[[0,11,20],[2,11,100],[2,64,127],[3.9,64,0]]
        step=cc_events(t);t['performance']['cc_mode']='linear';ramp=cc_events(t)
        assert step==[(0,11,20),(2,11,100),(2,64,127),(3.9,64,0)]
        values=[v for b,c,v in ramp if c==11];pedal=[(b,v) for b,c,v in ramp if c==64]
        assert len(values)>30 and values==sorted(values) and values[0]==20 and values[-1]==100 and pedal==[(2,127),(3.9,0)]
        return {'linear_cc11_events':len(values),'pedal_stays_switched':True}
    check('cc_mode_linear_ramps_continuous_controllers_only',cc_modes)
    def offset_shift():
        p=example();t=p['tracks'][0];clock=Clock(p);base=performed(t,clock)
        t['performance']['offset_ms']=-80;moved=performed(t,clock)
        deltas={round(a['start_seconds']-b['start_seconds'],3) for a,b in zip(base,moved) if a['tick']>0}
        assert deltas=={0.08};validate(p)
        return {'shift_seconds':0.08}
    check('performance_offset_moves_whole_part',offset_shift)
    def bend_export():
        p=example();t=p['tracks'][0];t['performance']['bend_range']=12
        t['performance']['bend']=[[0,0],[1,0],[1.25,2],[2,2],[2,-1]]
        validate(p);midi.write(p,work/'bend.mid')
        track=next(x for x in midi.read(work/'bend.mid')['tracks'] if x['name']==t['id'])
        wheel=[(e[0],e[2]+128*e[3]) for e in track['events'] if e[1]>>4==14]
        rpn=[(e[2],e[3]) for e in track['events'] if e[1]>>4==11 and e[2] in (101,100,6)]
        assert rpn[:3]==[(101,0),(100,0),(6,12)],rpn
        assert wheel[0]==(0,8192) and max(v for _,v in wheel)==8192+round(2/12*8191) and min(v for _,v in wheel)<8192
        assert wheel[-1][1]==8192
        for bad in ([[0,0],[1,13]],[[1,0],[0,0]],[[0,0,1]]):
            q=copy.deepcopy(p);q['tracks'][0]['performance']['bend']=bad;rejects(lambda:validate(q))
        q=copy.deepcopy(p);q['tracks'][0]['performance']['bend_range']=30;rejects(lambda:validate(q))
        midi.write(p,work/'bend_score.mid',expressive=False)
        assert not any(e[1]>>4==14 for x in midi.read(work/'bend_score.mid')['tracks'] for e in x['events'])
        # The additive synth plays the curve the MIDI holds: no bend before its first point (a note on beats 0-2 under a
        # first point on beat 4 sounds its own pitch, as the wheel rests until then), and a ramp under a tempo change
        # reaches at a beat the value the MIDI gives that beat; controllers alike.  (Found by a review of 0.4.0.)
        from musiclib.model import bend_events,cc_events
        c=Clock({'clock':{'bars':2,'meter':[4,4],'tempo':[[0,60],[2,120]]},'sections':[]})
        a={'engine':'additive','performance':{'bend':[[4,2],[6,2]],'cc':[]}}
        assert np.all(audio.bend_curve(a,np.array([0.0,1.0,1.9]),c)==0) and audio.bend_curve(a,np.array([c.seconds(4)]),c)[0]==2
        a['performance'].update(bend=[[0,0],[4,2]],cc=[[0,11,0],[4,11,120]],bend_range=2);mid=np.array([c.seconds(2)])
        wheel_at=next(v for b,v in reversed(bend_events(a)) if b<=2);cc_at=next(v for b,ctl,v in reversed(cc_events(a)) if ctl==11 and b<=2)
        assert abs(audio.bend_curve(a,mid,c)[0]-(wheel_at-8192)/8191*2)<.01 and abs(audio.control(a,11,mid,c,100)[0]-cc_at)<1,(audio.bend_curve(a,mid,c),wheel_at,cc_at)
        return {'wheel_events':len(wheel),'rpn_range_semitones':12,'score_export_has_no_bend':True,'additive_follows_the_midi_curve':True}
    check('pitch_bend_exports_rpn_and_wheel',bend_export)
    def single_voice_center():
        p=example();t=p['tracks'][2];t['instrument']={'detune_cents':[0]};audio.synthesize(p,t,work/'mono_voice.wav')
        a,_=audio.read_wav(work/'mono_voice.wav');l,r=audio.rms(a[:,0]),audio.rms(a[:,1])
        assert abs(20*np.log10(l/r))<0.01
        return {'left_minus_right_db':round(20*float(np.log10(l/r)),4)}
    check('additive_single_voice_is_centred',single_voice_center)
    def review_vertical():
        p=example();p['tracks']=p['tracks'][:3];p['tracks'][2]['role']='melody'
        p['tracks'][0]['notes']=p['tracks'][0]['notes'][:1];p['tracks'][0]['notes'][0].update(on=0,duration=4,pitch=54)
        p['tracks'][0]['performance']['notes']={p['tracks'][0]['notes'][0]['id']:{'velocity':70}}
        p['tracks'][2]['notes'][0].update(on=0,duration=2,pitch=67)
        from musiclib.review import vertical
        found=vertical(p,Clock(p))
        assert found['count']>=1 and any(x['pitches']==[54,67] and x['involves_foreground'] for x in found['examples'])
        p['tracks'][0]['notes'][0]['pitch']=55
        assert not any(x['pitches'] in ([55,67],[54,67]) for x in vertical(p,Clock(p))['examples'])
        return {'minor_ninth_flagged':True,'octave_not_flagged':True}
    check('review_flags_sustained_minor_ninth',review_vertical)
    def review_smoothness():
        # Notes outside the chord named as Open Music Theory's embellishing tones, the ones not resolved by step asked
        # about; parallel fifths and octaves between independent lines, a doubled line left out; close intervals under
        # their low interval limits, a power chord left out.
        from musiclib.review import outside_chord,parallels,low_intervals,embellishment,review as run_review
        base=example()
        def part(tid,role,notes):
            t=copy.deepcopy(base['tracks'][2]);t.update(id=tid,role=role,engine='additive');t.pop('drums',None)
            t['notes']=[{'id':f'{tid}_{i}','pitch':pc,'on':on,'duration':d} for i,(on,pc,d) in enumerate(notes)]
            t['performance']={'notes':{n['id']:{'velocity':80} for n in t['notes']}}
            return t
        def song(tracks,chords=(),bars=8):
            q=copy.deepcopy(base);q['clock']={'bars':bars,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':2};q['tracks']=tracks
            q['sections']=[{'id':'a','start_bar':0,'bars':bars}];q['harmony']=[c if isinstance(c,dict) else {'bar':i+1,'symbol':c} for i,c in enumerate(chords)]
            return q
        cases=((1,1),(1,-1),(2,-1),(-1,2),(0,-1),(0,1),(0,None,True),(1,None,True,True),(1,None,True),(2,-2),(2,1),(None,1),(1,None))
        assert [embellishment(*x) for x in cases]==['passing','neighbour','appoggiatura','escape tone','suspension','retardation','pedal','anticipation',None,None,'left by step','left by step',None]
        melody=[(0,64,1),(1,65,1),(2,67,1),(3,72,1),(4,72,1),(5,71,1),(6,69,1),(7,74,1),(8,77,1),(9,76,1),(10,81,1),(11,72,1),
                (12,72,2),(14,70,1),(15,69,1),(16,67,3),(19,74,5),(24,72,4),(28,72,4)]
        bass=[(0,48,4),(4,48,4),(8,48,4),(12,41,4),(16,36,4),(20,41,4),(24,36,4),(28,36,4)]
        pad=[(0,60,4),(0,64,4),(0,67,4),(4,59,4),(4,62,4),(4,67,4),(8,60,4),(8,64,6),(8,67,4),(12,60,4),(12,69,4),(14,65,2),
             (16,60,6),(16,64,4),(16,67,4),(20,62,4),(20,67,4),(22,55,2),(24,60,4),(24,64,4),(24,67,4),(28,60,4),(28,64,4),(28,67,4)]
        q=song([part('lead','melody',melody),part('bass','bass',bass),part('pad','harmony',pad)],['C','G','C','F','C','G','C','C'])
        q['tracks'][2].update(engine='synth',synth={'preset':'warm_pad'});r=outside_chord(q,Clock(q))
        # Melody: F and B-flat passing, C held into G and falling to B, A between B and D, F leapt to and falling to E,
        # D struck a beat before G and held into it; A5 leapt to and from over C.  Bass: C held under G into C, F2 leapt
        # to and from under G.  Pad: E held into F and rising to F, C held into G and leaving by a leap.
        assert r['tracks']['lead']['outside_chord']=={'passing':2,'suspension':1,'escape tone':1,'appoggiatura':1,'anticipation':1,'not resolved by step':1},r['tracks']
        assert r['tracks']['bass']['outside_chord']=={'pedal':1,'not resolved by step':1} and r['tracks']['pad']['outside_chord']=={'retardation':1,'not resolved by step':1},r['tracks']
        assert [(x['track'],x['note'],x['chord'],x['approach'],x['departure']) for x in r['examples']]==[('lead','A5','C','leap up','leap down'),('bass','F2','G','leap up','leap down'),('pad','C4','G','held or repeated','leap down')],r['examples']
        prompts=run_review(q,work/'review_smoothness')['prompts']
        assert sum('melody note on strong positions sits outside the written chord and is not resolved by step' in x for x in prompts)==1,prompts
        assert sum('neither resolved by step nor held as a pedal' in x for x in prompts)==2,prompts
        # A chord restated is not a change: F between G and E stays a passing note under C, C.
        q=song([part('lead','melody',[(0,67,2),(2,65,2),(4,64,4)])],['C',{'bar':1,'beat':3,'symbol':'C'},{'bar':2,'symbol':'Am'}],bars=2)
        assert outside_chord(q,Clock(q))['tracks']=={'lead':{'role':'melody','outside_chord':{'passing':1}}}
        # A chord that falls in the rest between two repeated notes is not sounded against.
        q=song([part('lead','melody',[(0,60,1),(2,60,.25)])],['C',{'bar':1,'beat':1,'symbol':'D'},{'bar':1,'beat':2,'symbol':'C'}],bars=1)
        assert outside_chord(q,Clock(q))['count']==0
        # A note struck again over the same held pitch adds no time: C4 sounds 0.6 beat into D (not enough to ask about)
        # or a whole beat in D and 0.3 into the next C (not held on, so unresolved), with or without the second note.
        # One struck again just as the last ends keeps its attack: C4 struck where D starts is asked about, C4 held a
        # quarter beat into D is not.
        for role in ('melody','harmony'):
            for notes,kinds in (([(0,60,1.6)],None),([(0,60,1.6),(.75,60,.85)],None),
                                ([(0,60,2.3)],{'not resolved by step':1}),([(0,60,2.3),(1.9,60,.4)],{'not resolved by step':1}),
                                ([(0,60,1.25)],None),([(0,60,1),(1,60,.25)],{'not resolved by step':1})):
                q=song([part('x',role,notes)],['C',{'bar':1,'beat':1,'symbol':'D'},{'bar':1,'beat':2,'symbol':'C'}],bars=1)
                assert outside_chord(q,Clock(q))['tracks'].get('x',{}).get('outside_chord')==kinds,(role,notes)
        # 6/8 beats in dotted quarters: attacks on them are not syncopated, one an eighth before the second beat pushes it.
        from musiclib.review import stiffness,repetition
        def compound(onsets):
            q=song([part('lead','melody',[(o,64,.5) for o in onsets])],bars=4);q['clock']['meter']=[6,8];return stiffness(q,Clock(q))
        on,early=compound([0,1.5,3,4.5,6,7.5,9,10.5]),compound([0,1.25,3,4.25,6,7.25,9,10.25])
        assert on['parts']['lead']['syncopated_pct']==0 and early['parts']['lead']['downbeat_pushes_pct']==50 and not early['no_pushes_anywhere'],(on,early)
        # A pre-chorus leads in to its chorus: a chorus thinner than it is asked about, whatever the pre-chorus is called.
        for name in ('prechorus','pre_chorus','pre-chorus'):
            q=song([part('lead','melody',[(x*.5,60+x%3,.5) for x in range(16)]+[(8,60,4)]),part('pad','harmony',[(0,48,8)])],bars=4)
            q['sections']=[{'id':name,'start_bar':0,'bars':2},{'id':'chorus','start_bar':2,'bars':2}]
            assert [w['section'] for w in repetition(q,Clock(q))['arrivals_thinner_than_before']]==['chorus'],name
        sop=[72,74,76,77,79,77,76,74];alto=[65,67,69,69,72,72,69,65];bass=[48,50,45,41,40,41,43,43]
        s=song([part('sop','melody',[(i,x,1) for i,x in enumerate(sop)]),part('alto','harmony',[(i,x,1) for i,x in enumerate(alto)]),
                part('ten','harmony',[(i,x-12,1) for i,x in enumerate(sop)]),part('bass','bass',[(i,x,1) for i,x in enumerate(bass)])],bars=2)
        par=parallels(s,Clock(s))
        assert par['by_pair']=={'alto / sop':2,'bass / sop':1,'bass / ten':1} and par['octaves_in_doublings']=={'sop / ten':7},par
        l=song([part('pad','harmony',[(0,45,4),(0,49,4),(0,52,4),(8,40,4)]),part('gtr','rhythm',[(4,38,4),(4,45,4),(4,50,4)]),
                part('gtr2','rhythm',[(4,45,4)]),part('bass','bass',[(8,36,4)])],bars=3)
        low=low_intervals(l,Clock(l))
        assert [(x['parts'],x['interval'],x['notes']) for x in low['examples']]==[(['pad'],'major third',['A2','C#3']),(['bass','pad'],'major third',['C2','E2'])],low
        return {'melody_kinds':r['tracks']['lead']['outside_chord'],'parallels':par['by_pair'],'low_intervals':low['count']}
    check('review_names_embellishing_tones_parallels_and_low_intervals',review_smoothness)
    def review_development():
        # Two hand-made 40-bar songs. A: every part loops, the second chorus repeats the first, the chorus is thinner
        # than its pre-chorus, the pad strikes block chords and nothing pushes: each is asked about. B: the same music
        # with the pad holding a tone over the change, an inner voice moving, drum fills every 8 bars, the melody and
        # bass varied, a fuller chorus and pushes: nothing is asked about.
        from musiclib.review import repetition,stiffness
        base=example()
        def part(tid,role,notes,drums=False):
            t=copy.deepcopy(base['tracks'][2]);t.update(id=tid,role=role,engine='additive');t.pop('drums',None)
            if drums:t['drums']=True
            t['notes']=[{'id':f'{tid}_{i}','pitch':pc,'on':on,'duration':d} for i,(on,pc,d) in enumerate(notes)]
            t['performance']={'notes':{n['id']:{'velocity':80} for n in t['notes']}}
            return t
        def song(tracks):
            q=copy.deepcopy(base);q['clock']={'bars':40,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':2};q['tracks']=tracks
            q['sections']=[{'id':i,'start_bar':s,'bars':8} for i,s in (('intro',0),('verse',8),('pre',16),('chorus',24),('chorus2',32))]
            return q
        bars=range(40);chorus=lambda b:24<=b<40
        mel_a=[(b*4+x,72+((b+x)%2)*2,1) for b in bars if 8<=b for x in (0,1,2,3) if not chorus(b) or x in (0,2)]
        flat=song([part('pad','harmony',[(b*4,p,4) for b in bars for p in (60,64,67)]),part('bass','bass',[(b*4+x,36,1) for b in bars for x in (0,2)]),
                   part('kit','drums',[(b*4+x,36,.5) for b in bars for x in (0,1,2,3)],True),part('lead','melody',mel_a),
                   part('strings','harmony',[(b*4,55,4) for b in range(16,24)])])
        c=Clock(flat);r,s=repetition(flat,c),stiffness(flat,c)
        assert r['static_spans'] and r['static_spans'][-1]['to_bar']==40,r['static_spans']
        assert any({'pad','bass','kit'}<=set(l['tracks']) for l in r['part_loops']),r['part_loops']
        assert {'section':'chorus2','repeats':'chorus'} in r['literal_returns'],r['literal_returns']
        assert [w['section'] for w in r['arrivals_thinner_than_before']]==['chorus'],r['arrivals_thinner_than_before']
        assert [b['track'] for b in s['block_chord_parts']]==['pad'] and s['no_pushes_anywhere'],s
        pad=[]
        for b in bars:
            top=64 if b%2 else 67
            pad+=[(b*4,60,4),(b*4,top,2),(b*4+2,top-(1 if b%4<2 else 3),2)] if b%2==0 else [(b*4,60,2),(b*4,top,4),(b*4+2,62+b%3,2)]
        mel_b=[(b*4+x,72+(b*3+x*5)%7,1 if x<3 else 1.5) for b in bars if 8<=b for x in (0,1,2,3.5)
               if (x<3.5 or b%4==3) and not (x==0 and b%4==0 and b>8)]  # every fourth bar pushes its last note over the bar line
        varied=song([part('pad','harmony',pad),part('bass','bass',[(b*4+x,36+(b//8)*2+(x==2.5),1) for b in bars for x in (0,2.5)]),
                     part('kit','drums',[(b*4+x,36 if (b+1)%8 else 38,.5) for b in bars for x in ((0,1,2,3) if (b+1)%8 else (0,1,2,2.5,3,3.5))],True),
                     part('lead','melody',mel_b),part('strings','harmony',[(b*4,55+b%3,4) for b in range(16,40)]),
                     part('counter','countermelody',[(b*4+x,79-(b+x*2)%5,.5 if b>=32 else 2) for b in range(24,40) for x in ((0,.5,1,1.5,2,2.5,3,3.5) if b>=32 else (0,2))])])
        c=Clock(varied);r,s=repetition(varied,c),stiffness(varied,c)
        assert not (r['static_spans'] or r['part_loops'] or r['literal_returns'] or r['arrivals_thinner_than_before'] or r['sections_alike']),r
        assert not s['block_chord_parts'] and not s['no_pushes_anywhere'] and s['parts']['lead']['downbeat_pushes_pct']>0,s['parts']
        # Stabs struck and released together but short and of varied lengths are a rhythm; one length throughout is asked about.
        stabs=[(b*4+on,p,d) for b in bars for on,d in ((0,.5),(1.5,.75),(2.5,1.5)) for p in (60,64,67)]
        even=[(b*4+on,p,.5) for b in bars for on in (0,1.5,2.5) for p in (60,64,67)]
        for notes,asked in ((stabs,False),(even,True)):
            q=song([part('stab','harmony',notes)]);assert bool(stiffness(q,Clock(q))['block_chord_parts'])==asked,notes[:6]
        # A synth part whose oscillators are all noise sets a sweep, not a pitch, like a drum part.
        from musiclib.review import unpitched
        fx=part('riser','effect',[(0,60,4)]);fx.update(engine='synth',synth={'preset':'noise_riser'})
        saw=part('lead','melody',[(0,60,4)]);saw.update(engine='synth',synth={'preset':'supersaw_lead'})
        assert unpitched(fx) and not unpitched(saw) and unpitched(part('kit','drums',[(0,36,1)],True))
        # A melody new in every bar, in running eighths, is asked about and never breathes; a motif stated, restated with
        # a new ending, sequenced and fragmented, with rests, is not asked about.
        from musiclib.profile import melody_in,top_line
        from musiclib.review import review as run_review
        # Eight bars of running eighths whose shapes (the Hamming(7,4) codewords of weight 0 and 3, as steps up and down)
        # differ pairwise in three directions or more: nothing comes back.
        codes=['0000000']+[('1101000'*2)[i:i+7] for i in range(7)]
        wander=[(b*4+k*.5,64+sum(2 if c=='1' else -2 for c in codes[b-8][:k]),.5) for b in range(8,16) for k in range(8)]
        motif=[(0,67,.5),(.5,69,.5),(1,72,1.5),(3,71,.5)]
        theme=[(b*4+on,p+(0,0,2,2,5,5,7,0)[b-8],d) for b in range(8,16) for on,p,d in (motif if b<15 else [(0,72,3)])]
        for notes,asked in ((wander,True),(theme,False)):
            q=song([part('lead','melody',notes)]);m=melody_in(top_line(q['tracks'][0]['notes']),32,64,Clock(q))
            prompts=run_review(q,work/f'review_melody_{asked}')['prompts']
            assert any('restates the rhythm and shape' in x for x in prompts)==asked,(m,prompts)
            assert (m['longest_without_breath_beats']==32)==asked and (m['bars_restated']>=5)!=asked,m
        # With Surge XT installed, a built-in preset that a curated patch covers is asked about; the 808 is not.
        from musiclib import surge
        assert surge.counterparts('warm_pad')[0]=='bell_pad' and 'moody_pad' in surge.counterparts('warm_pad') and not surge.counterparts('bass_808')
        fake=work/'fake_surge';(fake/'pylib').mkdir(parents=True,exist_ok=True);(fake/'Surge XT.vst3').write_bytes(b'')
        cfg={'surge':{'path':str(fake/'Surge XT.vst3')},'pedalboard':{'path':str(fake/'pylib')}}
        assert surge.installed(cfg) and not surge.installed({}) and not surge.installed(None)
        for preset,asked in (('warm_pad',True),('bass_808',False)):
            pad=part('pad','harmony',[(b*4,x,4) for b in range(8) for x in (48,55,60)]);pad.update(engine='synth',synth={'preset':preset})
            prompts=run_review(song([pad]),work/f'review_surge_{preset}',cfg)['prompts']
            assert any(f'plays the built-in {preset}; Surge XT is installed' in x for x in prompts)==asked,prompts
            assert not any('Surge XT is installed' in x for x in run_review(song([pad]),work/f'review_nosurge_{preset}')['prompts'])
        # With the full patch set installed, a built-in preset no curated patch covers is asked about with the catalog
        # patches named for its sound; one that no patch is named for is not.
        assert surge.catalog_counterparts('bass_808')==['a_liv/basses/bonsai_808','vospi/basses/808_builder_a'] and not surge.catalog_counterparts('chip_triangle')
        full={**cfg,'surge':{**cfg['surge'],'catalog':str(fake/'catalog')}}
        for preset,asked in (('bass_808',True),('chip_triangle',False)):
            low=part('bass','bass',[(b*4,36,2) for b in range(8)]);low.update(engine='synth',synth={'preset':preset})
            prompts=run_review(song([low]),work/f'review_catalog_{preset}',full)['prompts']
            assert any(f'plays the built-in {preset}; Surge XT is installed, and its full patch set has patches named for this sound' in x for x in prompts)==asked,prompts
        return {'flat':{k:len(v) for k,v in repetition(flat,Clock(flat)).items() if k!='energy'},'pushes_pct':s['parts']['lead']['downbeat_pushes_pct']}
    check('review_asks_about_loops_returns_arrivals_and_blocks',review_development)
    def review_summary():
        # The printed summary keeps every question word for word, shows where each counted finding is, and ends with
        # the file and the keys of the full figures; --json prints the whole report instead.
        from musiclib import summary
        from musiclib.review import review
        # The example with its first piano note a minor ninth under the lead's (B3 under C5), held as long.
        p=example();lead=min(p['tracks'][2]['notes'],key=lambda n:n['on'])
        p['tracks'][0]['notes'][0].update(on=lead['on'],duration=max(2,lead['duration']),pitch=lead['pitch']-13)
        r=review(p,work/'review_summary');text=summary.review(r,work/'review_summary')
        assert r['prompts'] and all(q in text for q in r['prompts']),text
        assert 'vertical_minor_seconds_ninths (' in text and 'B3/C5 (foreground)' in text and text.splitlines()[-1].startswith('Full figures: ') and 'score_review.json' in text.splitlines()[-1],text
        save_json(work/'summary_project.json',p);import subprocess,sys
        out=subprocess.run([sys.executable,str(Path(__file__).with_name('studio.py')),'review',str(work/'summary_project.json'),'--output',str(work/'review_summary_json'),'--json'],capture_output=True,text=True,encoding='utf-8')
        assert out.returncode==0 and json.loads(out.stdout)['prompts']==r['prompts'],out.stderr[-600:]
        return {'questions':len(r['prompts']),'summary_characters':len(text),'full_json_characters':len(out.stdout)}
    check('review_summary_keeps_every_question',review_summary)
    def surge_catalog():
        # Any patch of the measured catalog is a Surge preset by its id: found by role and measured character (flagged
        # patches left out, dark to bright), falling back by its role, and played only from the full patch set, which
        # bootstrap installs (offline with nothing cached it reports the skip and leaves the configuration without it).
        import contextlib,io,types
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
    check('surge_catalog_patch_by_id_search_and_install',surge_catalog)
    def sf2_roundtrip():
        from musiclib import sf2
        tone=(0.4*np.sin(2*np.pi*440*np.arange(4800)/48000)).astype(np.float32)
        sf2.write(work/'tiny.sf2','tiny',[{'name':'A4','data':tone,'rate':48000,'root':69}],
                  [{'name':'inst','global':{38:sf2.timecents(.2)},'zones':[{'gens':{43:(60,80),44:(1,127)},'sample':0}]}],
                  [{'name':'tiny','bank':0,'program':0,'global':{},'zones':[{'gens':{},'instrument':0}]}])
        bank=sf2.read(work/'tiny.sf2');inv=sf2.inventory(bank)[0];back=sf2.load_sample(bank,0)
        assert inv['keys']==[60,80] and inv['samples']==1 and inv['sample_rates']==[48000]
        assert np.max(np.abs(back-np.round(tone*32767)/32767))<1e-4
        return inv
    check('sf2_writer_reader_roundtrip',sf2_roundtrip)
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
        kick={'mics':[{'dir':'kick/close','gain':1.0,'pan':.5},{'dir':'kick/oh','gain':.5}],'pattern':r'k_vl(?P<dyn>\d)_rr(?P<rr>\d)\.wav',
              'root':36,'keys':[36,36],'dynamics':['1','2'],'velocity':{'1':[1,64],'2':[65,127]},'level':'peak','match_notes':False,
              'pitch_check':False,'rr_block':1,'velocity_attenuation_cb':60,'velocity_filter_cents':0}
        hat={'mics':[{'dir':'hat/close'}],'pattern':r'h_vl(?P<dyn>\d)_rr(?P<rr>\d)\.wav','root':42,'keys':[42,42],'dynamics':['1'],
             'velocity':{'1':[1,127]},'level':'peak','match_notes':False,'pitch_check':False,'exclusive_class':1}
        spec={'name':'kit','presets':[{'name':'kit','program':0,'level_reference':'preset','layers':[kick,hat]}]}
        build(spec,root,work/'kit.sf2');bank=sf2.read(work/'kit.sf2')
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
    check('soundbank_builds_a_kit_with_microphones_and_choke',kit_build)
    def loop_build():
        from musiclib import sf2
        from musiclib.loop import write_wav
        from soundbank import build
        root=work/'loop_source';root.mkdir(parents=True,exist_ok=True);rate=48000;t=np.arange(3*rate)/rate
        # Three sustained takes, each looped from 1 s to its end; the middle one was recorded 6 dB hot and every take
        # sags 6 dB over the last 0.4 s of its loop, as a bow easing off.
        for name,f0,amp in (('A3',220.0,.1),('C4',261.63,.2),('D#4',311.13,.1)):
            x=amp*np.where(t<2.6,1,.5)*np.sin(2*np.pi*f0*t);write_wav(root/f'c_{name}.wav',np.repeat(x[:,None],2,1),rate,len(x))
        layer={'dir':'.','pattern':r'c_(?P<note>[A-G]#?\d)\.wav','dynamics':['default'],'velocity':{'default':[1,127]},'keys':[55,66],
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
        found={**layer,'dir':'found','pattern':r'f_(?P<note>[A-G]#?\d)\.wav','keys':[60,70],'loop':'found','loop_window':[.5,600.0],
               'loop_repair':{'sag_db':1.5,'crossfade':.1}}
        build({'name':'found','presets':[{'name':'held','program':42,'layers':[found]}]},root,work/'found.sf2');fb=sf2.read(work/'found.sf2')
        f=fb['samples'][0];ls,le=(f['loop'][0]-f['start'])/rate,(f['loop'][1]-f['start'])/rate
        assert le-ls>=.8 and (ls-.1>1.905 or le<1.9) and all(z['gens'].get(54)==1 for z in fb['instruments'][0]['zones'][1:]),(ls,le)
        return {'loop_seconds':recorded,'hot_take_after_db':round(hot,2),'found_loop_seconds':[round(ls,3),round(le,3)]}
    check('soundbank_keeps_recorded_loops_and_evens_takes',loop_build)
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
            layer={'dir':'.','pattern':r'a_(?P<note>[A-G]#?\d)_(?P<dyn>[pf])\.wav','dynamics':['p','f'],'velocity':{'p':[1,64],'f':[65,127]},
                   'keys':[48,67],'match_notes':mode,'layer_levels_db':{'p':0,'f':0},'match_limit_db':12,'pitch_check':False}
            build({'name':'across','presets':[{'name':'keys','program':0,'layers':[layer]}]},root,work/f'across_{mode}.sf2')
            bank=sf2.read(work/f'across_{mode}.sf2')
            rms={s['name']:20*np.log10(np.sqrt(np.mean(sf2.load_sample(bank,i)[:rate].astype(float)**2))) for i,s in enumerate(bank['samples'])}
            lvl=lambda n,d:next(v for k,v in rms.items() if k.startswith(f'a_{n}_{d}'))
            steps[mode]=[round(lvl(n,'f')-lvl(n,'p'),2) for n in notes]
        assert max(map(abs,steps['across']))<.2 and steps['local'][-1]-steps['local'][0]>4,steps
        return {'split_step_db_local':steps['local'],'split_step_db_across':steps['across']}
    check('soundbank_levels_every_dynamic_of_a_note_together',across_levels)
    def score_profile():
        from musiclib.profile import profile
        p=example();lead=next(t for t in p['tracks'] if t['id']=='lead');line=[60,62,64,65,67,65,64,62]
        lead['notes']=[{'id':f'lead_t{b}_{i}','on':b*4+i*.5,'duration':.5,'pitch':x,'phrase':'test','articulation':'normal'} for b in (0,1) for i,x in enumerate(line)]
        lead['performance']['notes']={n['id']:{'velocity':80+10*(i%2),'gate':1.0,'timing_ms':0} for i,n in enumerate(lead['notes'])}
        r=profile(p);row=r['parts']['lead'];tl=row['top_line']
        # A one-bar scale in eighths played twice: worked out by hand, so any change to a descriptor shows here.
        assert (row['notes'],row['notes_per_bar'],row['offbeat_onsets_pct'],row['downbeat_onsets_pct'],row['rhythm_repeat_pct'])==(16,4.0,50.0,12.5,50.0),row
        assert row['register']=={'low':'C4','high':'G4','median':'E4','span':7} and row['pitch_classes_used']==5 and row['pitch_class_entropy_bits']==2.25
        assert (tl['mean_abs_interval'],tl['steps_pct'],tl['leaps_pct'],tl['largest_leap'],tl['direction_changes_pct'],tl['recurring_cells_pct'])==(1.73,100.0,0.0,2,21.4,33.3),tl
        assert row['ioi_beats']=={'1/2':100.0} and row['velocity']=={'mean':85.0,'sd':5.0,'range':[80,90]}
        sec={s['section']:s for s in r['sections']}
        assert sec['question']['notes_per_bar']['lead']==8.0 and sec['question']['melody_median']=='E4' and sec['answer']['melody_median'] is None
        # Sixteen eighths in two bars at 108 BPM, the other pitched parts silent and the drums not counted: 16 / 4.44 s.
        q=copy.deepcopy(p)
        for t in q['tracks']:
            if t['id'] not in ('lead','drums'):t['notes']=[]
        assert profile(q)['sections'][0]['onsets_per_second']==3.6,profile(q)['sections'][0]
        return {'lead':{k:row[k] for k in ('notes_per_bar','offbeat_onsets_pct','rhythm_repeat_pct')},'top_line':tl}
    check('score_profile_matches_a_hand_counted_line',score_profile)
    def soundbank_lock():
        import fetch_soundbanks as fs
        lock=json.loads((Path(__file__).resolve().parents[1]/'references'/'soundbank-lock.json').read_text(encoding='utf-8'))
        for item in lock['archives']:
            import urllib.parse
            assert urllib.parse.urlsplit(item['url']).hostname in fs.HOSTS and len(item['sha256'])==64 and len(item['member_sha256'])==64
            assert fs.safe_member(item['member']) and all(fs.safe_member(n) for n in item.get('notices',[]))
        for item in lock['builds']:
            spec=Path(__file__).resolve().parents[1]/'references'/item['spec']
            assert len(item['output_sha256'])==64 and int(item['output_sha256'],16)>=0 and spec.is_file(),item['name']
        assert not fs.safe_member('../x.sf2') and not fs.safe_member('/abs.sf2') and not fs.safe_member('C:/x.sf2')
        (work/'crlf.txt').write_bytes(b'line\r\nnext\r\n');(work/'bin.dat').write_bytes(b'\0\r\n')
        lf=__import__('hashlib').sha1(b'blob 10\0line\nnext\n').hexdigest()
        assert lf in fs.git_blob_sha1s(work/'crlf.txt') and len(fs.git_blob_sha1s(work/'bin.dat'))==1
        return {'archives':len(lock['archives']),'builds':len(lock['builds'])}
    check('soundbank_lock_hosts_hashes_and_member_paths',soundbank_lock)
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
        lock=json.loads((Path(__file__).resolve().parents[1]/'references'/'soundbank-lock.json').read_text(encoding='utf-8'))
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
    check('prebuilt_banks_unpack_only_when_they_match_the_lock',prebuilt_bank)
    def bus_settings():
        from musiclib import mixbus
        from musiclib.model import BUSES,SPACES
        assert set(mixbus.SPACES)==set(SPACES) and set(mixbus.BUS_FILTER)|{'drums'}==set(BUSES)
        p=example();buses={t['id']:mixbus.bus_of(t) for t in p['tracks']}
        assert buses=={'piano':'ensemble','bass':'bass','lead':'lead','drums':'drums','fx':'fx'},buses
        q=example();q['tracks'][0]['mix'].update(bus='rhythm',space='plate');validate(q)
        assert mixbus.bus_of(q['tracks'][0])=='rhythm' and mixbus.space_of(q['tracks'][0])=='plate'
        for key,value in (('bus','vocals'),('space','cathedral')):
            q=example();q['tracks'][0]['mix'][key]=value;rejects(lambda:validate(q))
        q=example();q['mix']['chain']='tape';rejects(lambda:validate(q))
        # The render's premix check allows float32 rounding at the parts' size: eleven loud parts summed in float32, as
        # FFmpeg sums them, miss their exact sum by more than a fixed 1e-5 (a premix runs far above full scale before
        # mastering) and still pass; with one part left out the sum fails.
        rng=np.random.default_rng(3);parts=[(rng.standard_normal((48000,2))*10).astype(np.float32) for _ in range(11)]
        mixed=parts[0].copy()
        for x in parts[1:]:mixed=(mixed+x).astype(np.float32)
        total=sum(x.astype(np.float64) for x in parts);mag=sum(np.abs(x.astype(np.float64)) for x in parts)
        ok,worst,share=mixbus.adds_up(total,mag,mixed.astype(np.float64))
        assert ok and worst>1e-5,(worst,share)
        assert not mixbus.adds_up(total-parts[3],mag-np.abs(parts[3]),mixed.astype(np.float64))[0]
        return {'default_buses':buses,'invalid_settings_rejected':3,'loud_float32_sum_error':worst,'share_of_allowance':round(share,3)}
    check('bus_assignment_and_validation',bus_settings)
    def spaces_and_dynamics():
        from musiclib import mixbus
        def t60(ir,centre):
            # Schroeder backward integration of a half-octave band (zero-padded, so the filter cannot wrap the start
            # onto the tail), T30 from -5 to -35 dB, scaled to 60 dB.
            m=ir.mean(axis=1).astype(np.float64);n=len(m);f=np.fft.rfftfreq(2*n,1/audio.RATE)
            band=np.fft.irfft(np.fft.rfft(m,2*n)*(np.abs(np.log2(np.maximum(f,1)/centre))<.5),n=2*n)[:n]
            edc=np.cumsum(band[::-1]**2)[::-1];edc=10*np.log10(edc/edc[0]+1e-30)
            a,b=np.argmax(edc<-5),np.argmax(edc<-35);return 2*(b-a)/audio.RATE
        hall,church=t60(mixbus.space_ir('hall'),1000),t60(mixbus.space_ir('church'),1000)
        assert abs(hall-2.2)<.33 and abs(church-4.2)<.63 and church>1.6*hall,(hall,church)
        q=example();q['tracks'][0]['mix']['space']='church';validate(q)
        q=example();q['mix'].update(chain='bus',dynamics='wide');validate(q)
        for mix in ({'dynamics':'loud'},{'chain':'room','dynamics':'wide'}):
            q=example();q['mix'].update(mix);rejects(lambda:validate(q))
        return {'t60_1k_hall':round(hall,2),'t60_1k_church':round(church,2)}
    check('church_space_decays_as_specified_and_dynamics_validate',spaces_and_dynamics)
    def k_weighting():
        from musiclib.measure import SHELF,RLB,k_level
        t=np.arange(audio.RATE)/audio.RATE
        sine=np.zeros((len(t),2));sine[:,0]=np.sin(2*np.pi*997*t)
        calibrated=k_level(sine)  # BS.1770: a 0 dBFS 997 Hz sine in one channel reads -3.01
        def biquad(signal,b,a):
            out=[0.0]*len(signal);x1=x2=y1=y2=0.0
            for i,v in enumerate(signal):
                y=b[0]*v+b[1]*x1+b[2]*x2-a[1]*y1-a[2]*y2;x2,x1,y2,y1=x1,v,y1,y;out[i]=y
            return out
        x=np.column_stack([np.random.default_rng(7).standard_normal(len(t))*.1,.2*np.sin(2*np.pi*3000*t)])
        power=sum(np.mean(np.square(biquad(biquad(x[:,c].tolist(),*SHELF),*RLB))) for c in range(2))
        in_time=-0.691+10*np.log10(power)
        assert abs(calibrated+3.01)<.05 and abs(k_level(x)-in_time)<.05,(calibrated,k_level(x),in_time)
        return {'sine_997hz_0dbfs_lufs':round(calibrated,3),'frequency_vs_time_domain_db':round(float(k_level(x)-in_time),4)}
    check('k_weighting_matches_bs1770',k_weighting)
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
    check('loop_fold_points_and_seam',loop_parts)
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
        return {'cues':cues,'tempo':t,'layer_cases_rejected':5}
    check('loop_cue_points_tempo_and_layer_rules',loop_markers_and_layers)
    def strum():
        from musiclib import expression
        p=example();g=copy.deepcopy(p['tracks'][0]);g['id']='gtr';g['role']='rhythm'
        chord=[40,47,52,56,59,64];g['notes']=[{'id':f'g{k}_{j}','on':k*.5,'duration':.4,'pitch':m} for k in range(4) for j,m in enumerate(chord)]
        g['performance']={'notes':{n['id']:{'velocity':90,'timing_ms':0,'gate':1} for n in g['notes']},'cc':[]};p['tracks']=[g]
        flat={'timing_sd':0,'short_sd':0,'vel_pct':0,'arch':0,'gate_sd':0,'contrast':0}
        report=expression.apply(p,{'gtr':{**flat,'strum':8}},seed=4);perf=g['performance']['notes']
        down=[perf[f'g0_{j}']['timing_ms'] for j in range(6)];up=[perf[f'g1_{j}']['timing_ms'] for j in range(6)]
        assert down==sorted(down) and down[0]==0 and 30<down[-1]<50,down
        assert up==sorted(up,reverse=True) and up[-1]==0 and up[0]<down[-1],up
        assert perf['g1_0']['velocity']<perf['g0_0']['velocity'] and report['gtr']['strokes']=={'down':2,'up':2}
        return {'downstroke_ms':down,'upstroke_ms':up}
    check('strummed_chords_follow_the_stroke',strum)
    def xf_bank():
        """A two-dynamic sustained instrument (a soft sine and a bright tone, both swelling in over 300 ms, as a bowed
        attack does) with dynamic-layer and legato presets; built once per selfcheck."""
        import wave
        from soundbank import build
        path=work/'xf.sf2'
        if path.is_file():return path
        root=work/'xf_source';root.mkdir(parents=True,exist_ok=True);rate=48000;t=np.arange(3*rate)/rate;ramp=np.minimum(1,t/.3)
        for name,f0 in (('C4',261.63),('G4',392.0)):
            for dyn,x in (('p',.1*ramp*np.sin(2*np.pi*f0*t)),('f',.3*ramp*sum(np.sin(2*np.pi*f0*h*t)/h for h in range(1,9)))):
                q=np.clip(np.round(np.repeat(x[:,None],2,1)*32767),-32768,32767).astype('<i2')
                with wave.open(str(root/f'x_{name}_{dyn}.wav'),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(q.tobytes())
        layer={'dir':'.','pattern':r'x_(?P<note>[A-G]#?\d)_(?P<dyn>[pf])\.wav','dynamics':['p','f'],'velocity':{'p':[1,64],'f':[65,127]},
               'keys':[55,72],'layer_levels_db':{'p':-9,'f':0},'envelope':{'attack':.005,'release':.3}}
        preset={'name':'held','program':48,'layers':[layer],'dynamic_layers':{'bank':16},'legato':{'bank':32,'attack':.01}}
        build({'name':'xf','presets':[preset]},root,path)
        plain={k:v for k,v in preset.items() if k not in ('dynamic_layers','legato')}
        build({'name':'xf','presets':[plain]},root,work/'xf_plain.sf2')
        return path
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
    check('soundbank_builds_dynamic_layers_and_legato_presets',expressive_bank)
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
        layer={'dir':'.','pattern':r'r_(?P<note>[A-G]#?\d)_(?P<dyn>f)\.wav','dynamics':['f'],'velocity':{'f':[1,127]},'keys':[55,72],
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
    check('soundbank_ring_db_keeps_each_take_to_its_own_decay',ring_cut)
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
        layer={'dir':'.','pattern':r'p_(?P<id>a)_(?P<dyn>f)\.wav','dynamics':['f'],'velocity':{'f':[1,127]},'keys':[40,64],'level':'peak',
               'denoise':{'reduce_db':12,'keep_partials_below':300}}
        spec={'name':'partials','presets':[{'name':'on_a','program':0,'layers':[{**layer,'pitches':{'a':45.0}}]},
                                           {'name':'on_e','program':1,'layers':[{**layer,'pitches':{'a':52.0}}]}]}
        build(spec,root,work/'partials.sf2');bank=sf2.read(work/'partials.sf2')
        data=[sf2.load_sample(bank,i).tobytes() for i in range(len(bank['samples']))]
        assert len(data)==4 and set(data[:2]).isdisjoint(data[2:]),len(set(data))  # each layer's two channels, its own cleaning
        return {'samples':len(data),'shared_between_layers':0}
    check('soundbank_denoise_keeps_each_layers_partials',denoise_keeps_each_layers_partials)
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
        return {'notes':len(m['notes']),'cents':{g[0][7:-4]:g[1] for g in got}}
    check('split_finds_each_note_of_a_chromatic_run',split_run)
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
    check('split_reads_a_high_passed_copy_and_leaves_out_takes',split_highpass)
    def split_bank():
        from soundbank import build
        from musiclib import sf2
        root=work/'split_notes';manifest=json.loads((root/'split.json').read_text(encoding='utf-8'))
        layer={'dir':'T','pattern':r'T_(?P<dyn>pp|mf)_(?P<note>[A-G]#?-?\d)\.wav','dynamics':['pp','mf'],'velocity':{'pp':[1,63],'mf':[64,127]},
               'keys':[60,65],'pitch_source':'split','max_correction_cents':100,'layer_levels_db':{'pp':-10,'mf':0},'borrowed_level':'served'}
        build({'name':'split','presets':[{'name':'t','program':0,'layers':[layer]}]},root,work/'split.sf2');bank=sf2.read(work/'split.sf2')
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
            return {'dir':folder,'pattern':folder+r'_(?P<dyn>mf)_(?P<note>[A-G]#?-?\d)\.aiff','dynamics':['mf'],'velocity':{'mf':[1,127]},
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
    check('soundbank_tunes_split_notes_and_quiets_borrowed_dynamics',split_bank)
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
    check('dynamics_crossfade_keeps_power_and_legato_fades_cross',crossfade_gains)
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
    check('take_mode_learns_brightness_from_the_layers',take_mode)
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
    check('noise_reduction_lowers_hiss_and_keeps_the_note',noise_reduction)
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
    check('click_repair_takes_out_a_knock_and_keeps_the_ring',click_repair)
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
    check('denoise_keeps_a_soft_low_note_out_of_the_rumble',denoise_keeps_low_partials)
    def drum_round_robins():
        from musiclib import variation
        # A hit recorded at two dynamics with four takes each, interleaved on neighbouring velocities as the builder
        # lays them out (velocities 1-20 and 21-40), and a key with one take per velocity (velocity layers only).
        row=[set()]+[{('soft',(v-1)%4)} if v<=20 else {('loud',(v-21)%4)} if v<=40 else set() for v in range(1,128)]
        cells=variation.cycle_layers(row);flat=variation.cycle_layers([set()]+[{v} for v in range(1,128)])
        assert cells[5][:3]==(1,20,4) and cells[30][:3]==(21,40,4) and cells[50] is None and flat[64][2]==1,(cells[5],cells[30],flat[64])
        cycles={38:cells,40:flat}
        # A groove at one velocity per role: each later hit on a key takes the layer's next take, a step or two away,
        # inside its layer; the two dynamics rotate apart; a velocity-layered key keeps its velocities.
        notes=[{'pitch':38,'velocity':10 if i%2==0 else 35} for i in range(12)]+[{'pitch':40,'velocity':64} for _ in range(4)]
        out=variation.cycle_velocities(notes,cycles)
        takes=[row[v] for v in out[:12]]
        soft=[next(iter(t))[1] for t,n in zip(takes,notes) if n['velocity']==10];loud=[next(iter(t))[1] for t,n in zip(takes,notes) if n['velocity']==35]
        assert soft==[1,2,3,0,1,2] and loud==[2,3,0,1,2,3],(soft,loud)
        assert all(abs(v-n['velocity'])<=2 and cells[v][0]==cells[n['velocity']][0] for v,n in zip(out[:12],notes)) and out[12:]==[64]*4,out
        return {'soft_takes':soft,'loud_takes':loud,'largest_step':max(abs(v-n['velocity']) for v,n in zip(out,notes))}
    check('drum_hits_cycle_their_recorded_round_robins',drum_round_robins)
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
    check('surge_patch_goes_into_the_plugin_state',surge_state)
    def tonal_reference():
        from musiclib import analysis
        # Pink noise falls 3 dB per octave in power per hertz and white noise not at all; a master matches itself; a
        # darker one is told so against the pink reference; a mono low end and unrelated channels read narrow and wide.
        rng=np.random.default_rng(5);n=audio.RATE*12;f=np.fft.rfftfreq(n,1/audio.RATE)
        def coloured(alpha,mono=False):
            x=np.fft.irfft(np.fft.rfft(rng.standard_normal((n,2)),axis=0)/np.maximum(f,20)[:,None]**(alpha/2),n,axis=0)
            if mono:x[:,1]=x[:,0]
            return (x/np.abs(x).max()*.3).astype(np.float32)
        meter={'integrated_lufs':-16.0,'true_peak_dbtp':-1.0,'lra_lu':5.0}
        pink,dark,white=(analysis.long_term(coloured(a,m),meter) for a,m in ((1,False),(1.6,True),(0,False)))
        slopes=[x['tonal_balance']['slope_db_per_octave_100hz_4khz'] for x in (pink,dark,white)]
        assert abs(slopes[0]+3)<.3 and abs(slopes[1]+4.8)<.3 and abs(slopes[2])<.3,slopes
        same,quiet=analysis.compare(pink,pink,'pink')
        assert not quiet and same['slope_difference_db_per_octave']==0 and not any(same['octaves_minus_reference_db'].values()),same
        darker,told=analysis.compare(dark,pink,'pink')
        assert len(told)==1 and 'darker' in told[0] and dark['side_minus_mid_db']['20-120']==-60 and abs(pink['side_minus_mid_db']['2000-16000'])<.5,(told,dark['side_minus_mid_db'],pink['side_minus_mid_db'])
        table=json.loads(analysis.REFERENCES.read_text(encoding='utf-8'))['references']
        assert all(-8<=r['tonal_balance']['slope_db_per_octave_100hz_4khz']<=-1.5 and r['loudness']['plr_db']>0 for r in table.values()),sorted(table)
        return {'slopes':slopes,'darker_by':darker['slope_difference_db_per_octave'],'references':sorted(table)}
    check('tonal_balance_reads_noise_and_compares_with_a_reference',tonal_reference)
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
    check('noise_profile_reads_gated_and_breathy_recordings',noise_profile)
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
    check('split_keeps_the_note_not_its_faint_ring',split_ignores_faint_rings)
    def rubato():
        from musiclib.model import effective_tempo
        p=example();p['clock']['tempo']=[[0,100]];bpb=Clock(p).beats_per_bar;total=Clock(p).total_beats
        plain=Clock(p);p['clock']['rubato']={'final_ratio':.5,'final_beats':4,'phrase_ratio':.9,'phrase_beats':2};validate(p);played=Clock(p)
        # The close slows to half speed by the last eighth (Friberg and Sundberg's curve, q = 2: tempo falls fastest at
        # the end), each section's last two beats ease by up to 10%, and the next downbeat is back in time.
        tempo=effective_tempo(p);last=tempo[-1][1];bounds=[s['start_bar']*bpb for s in p['sections'][1:]]
        mid=[v for b,v in tempo if total-4<=b<total-2];late=[v for b,v in tempo if b>=total-1]
        assert 50<=last<=55 and min(mid)>75 and max(late)<70,(last,min(mid),max(late))
        for b in bounds:
            before=[v for x,v in tempo if b-2<=x<b];assert 90<=min(before)<100 and dict((x,v) for x,v in tempo)[b]==100,(b,before)
        stretch=played.end-plain.end;expected=sum((plain.seconds(x+1/8)-plain.seconds(x))*(100/v-1) for x,v in tempo if v!=100)
        assert abs(stretch-expected)<1e-3 and stretch>.5,(stretch,expected)
        bad=copy.deepcopy(p);bad['clock']['rubato']={'final_ratio':.1};rejects(lambda:validate(bad))
        return {'final_tempo':last,'seconds_added':round(stretch,3),'tempo_points':len(tempo)}
    check('rubato_slows_phrase_ends_and_the_close',rubato)
    def swing():
        from musiclib.model import performed
        p=example();p['clock']['tempo']=[[0,120]];clock=Clock(p);part=p['tracks'][0]
        part['notes']=[{'id':f's{k}','pitch':60+k,'on':k*.5,'duration':.5} for k in range(4)]+[{'id':'s4','pitch':64,'on':2.25,'duration':.25}]
        part['performance']={'notes':{n['id']:{'velocity':80} for n in part['notes']},'swing':{'ratio':.6,'unit':.5}}
        # Swung eighths at 0.6: each off-beat lands a tenth of a beat late, notes on the beat stay put, the first of a
        # pair lengthens to 0.6 beat and a sixteenth inside the pair moves in proportion; unswung, nothing moves.
        on=[round(clock.beat(e['start_seconds']),4) for e in performed(part,clock)];length=[round(clock.beat(e['end_seconds'])-clock.beat(e['start_seconds']),4) for e in performed(part,clock)]
        assert on==[0,.6,1,1.6,2.3] and length[:2]==[.6,.4],(on,length)
        assert [round(clock.beat(e['start_seconds']),4) for e in performed(part,clock,expressive=False)]==[0,.5,1,1.5,2.25]
        part['performance']['swing']={'ratio':.6,'unit':.25}
        assert [round(clock.beat(e['start_seconds']),4) for e in performed(part,clock)]==[0,.5,1,1.5,2.3]
        for bad in ({'ratio':.9},{'unit':.5},{'ratio':.6,'unit':.3},{'ratio':.6,'feel':1}):
            q=copy.deepcopy(p);q['tracks'][0]['performance']['swing']=bad;rejects(lambda:validate(q))
        return {'eighths_at_0.6':on}
    check('swing_delays_off_beats_and_keeps_the_beat',swing)
    def variation_tools():
        from musiclib import variation,layered,midi as mid
        dense={k:frozenset([k]) for k in range(48,80)};zoned={k:frozenset([k//5]) for k in range(48,80)};single={k:frozenset([0]) for k in range(48,80)}
        notes=[{'pitch':60,'start_seconds':x} for x in (0,.2,.4,.6,3.0)]
        # Keys 60-64 share a recording in `zoned`: the repeat goes down to 59, the first key with another one.
        assert variation.round_robin_shifts(notes,dense)==[0,1,0,1,0] and variation.round_robin_shifts(notes,zoned)==[0,-1,0,-1,0]
        assert variation.round_robin_shifts(notes,single)==[0]*5
        # A repeated note leaves for a key whose zone holds another recording and the wheel brings it back.
        p=example();t=p['tracks'][0];t['engine']='soundfont';t['drums']=False;t['performance']['round_robin']=True
        t['performance'].pop('bend',None);t['performance'].pop('legato',None)
        t['notes']=[{'id':f'r{k}','on':k*.5,'duration':.4,'pitch':62} for k in range(4)];t['performance']['notes']={f'r{k}':{'velocity':90} for k in range(4)}
        validate(p);mid.write(p,work/'rr.mid',[t],single_stem=True,render=True,keys=dense);parsed=mid.read(work/'rr.mid')
        on=[(e['channel'],e['pitch']) for tr in parsed['tracks'] for e in tr['notes']]
        assert sorted(on)==[(0,62),(0,62),(1,63),(1,63)],on
        # Bow changes cut a long held note into even stretches entering from the legato preset; a leap of a fifth in a
        # slur gets a slide into its pitch.
        clock=Clock(p);t['performance'].update(legato={'mode':'crossfade','crossfade_ms':100,'portamento_ms':120},bow_change_s=3)
        t['notes']=[{'id':'a','on':0,'duration':12,'pitch':60},{'id':'b','on':12,'duration':2,'pitch':67}]
        t['performance']['notes']={'a':{'velocity':80},'b':{'velocity':80}};t['performance'].pop('offset_ms',None);validate(p)
        planned=layered.plan(t,clock);bows=[n for n in planned if n.get('bow_change')]
        assert len(planned)==len(bows)+2 and all(n['legato'] and n['fade_in'] for n in bows) and planned[-1]['glide'] and planned[-1]['glide'][0]<0,[(n['pitch'],n.get('bow_change'),n['legato'],n.get('glide')) for n in planned]
        layered.write_midi(work/'glide.mid',p,t,planned,48,16,32,round(clock.total_beats*TPQ),None,clock)
        raw=(work/'glide.mid').read_bytes();assert raw.count(bytes([0xE1]))>=9  # the slide's wheel moves on channel 1
        return {'shifts':variation.round_robin_shifts(notes,dense),'bow_changes':len(bows),'glide_semitones':round(planned[-1]['glide'][0],2)}
    check('round_robins_bow_changes_and_portamento',variation_tools)
    def facing():
        from musiclib import stage
        x=np.random.default_rng(3).standard_normal((48000*2,2)).astype(np.float32)*.1;f=np.fft.rfftfreq(48000*2,1/48000)
        def shape(y):
            spec=np.abs(np.fft.rfft(y.astype(np.float64).mean(axis=1)))**2
            return 10*np.log10(spec[(f>3000)&(f<8000)].sum()/spec[(f>200)&(f<1000)].sum()),float(np.sum(y.astype(np.float64)**2))
        (front,ef),(back,eb)=shape(stage.place(x,-.3,7)[0]),shape(stage.place(x,-.3,7,'back')[0])
        # A bell facing away: darker, more of it from the walls, the same energy.
        assert front-back>1.5 and abs(eb/ef-1)<.02 and stage.place(x,-.3,7,'back')[1]['reflection_share_db']>stage.place(x,-.3,7)[1]['reflection_share_db']+3
        return {'darker_db':round(front-back,2)}
    check('a_bell_facing_back_sounds_darker_and_further',facing)
    def phrasing_helpers():
        from musiclib import phrasing
        line=[(k,1) for k in range(8)]
        v=phrasing.sing(line,70,peak=10,apex=.6)
        # The arch tops out on the note nearest 60% of the phrase; the first note stays at the base, the last falls back.
        assert v[0]==70 and max(v)==v[5]>=79 and v[-1]<v[5],v
        hair=phrasing.ramp([[0,40],[8,100]]);assert hair(-1)==40 and hair(4)==70 and hair(9)==100
        t={'notes':[{'id':'a','on':0,'duration':4,'pitch':60},{'id':'b','on':4,'duration':1,'pitch':62}],
           'performance':{'notes':{'a':{'velocity':60},'b':{'velocity':80}}}}
        d=phrasing.dynamics(t,swell=8)
        assert d==[[0,60],[1.8,68],[3.6,56],[4,80]],d
        assert phrasing.near([[0,20],[4,110]],64,12)==[[0,52],[4,76]]
        return {'arch':v,'curve':d}
    check('phrasing_helpers_arch_swell_and_hold',phrasing_helpers)
    def voicing_helper():
        # ii-V-I moves by the textbook steps (common tones held), a pop loop moves far less than root-position blocks,
        # parallels go when asked, a melody ceiling holds, tones drop and double in order, and the spacing keeps to the
        # octave and the low interval limits, the same each run.
        from musiclib.voicing import voice_lead,chord_tones,LOW_INTERVAL_LIMITS
        motion=lambda vs:[sum(abs(b-a) for a,b in zip(x,y)) for x,y in zip(vs,vs[1:])]
        jazz=voice_lead(['Dm7','G7','Cmaj7'],voices=4,low=52,high=76)
        assert motion(jazz)==[3,3],jazz
        assert all(any((p-r)%12 in (3,4) for p in v) and any((p-r)%12 in (10,11) for p in v) for v,r in zip(jazz,[2,7,0])),jazz
        pop=['C','G','Am','F']*2;smooth=voice_lead(pop,voices=4)
        naive=[[48+r,48+r+(3 if 'm' in s else 4),48+r+7,60+r] for s,r in zip(pop,[0,7,9,5]*2)]
        assert sum(motion(smooth))*2<sum(motion(naive)) and smooth==voice_lead(pop,voices=4),(motion(smooth),motion(naive))
        def parallels(vs):
            n=0
            for a,b in zip(vs,vs[1:]):
                for i in range(len(a)):
                    for j in range(i+1,len(a)):
                        di,dj=b[i]-a[i],b[j]-a[j]
                        n+=(a[j]-a[i])%12==(b[j]-b[i])%12 and (a[j]-a[i])%12 in (0,7) and di and dj and (di>0)==(dj>0)
            return n
        free,strict=voice_lead(['C','D','G','C'],voices=4),voice_lead(['C','D','G','C'],voices=4,avoid_parallels=True)
        assert parallels(free)>0 and parallels(strict)==0,(free,strict)
        # Where the range leaves one voicing per chord (three voices for D then E between C4 and C5) the parallel stays;
        # with room, none does.
        assert voice_lead(['D','E'],voices=3,low=60,high=72,avoid_parallels=True)==[[62,66,69],[64,68,71]]
        assert parallels(voice_lead(['D','E'],voices=3,low=55,high=79,avoid_parallels=True))==0
        # Here the smoothest voicing keeps a parallel that one moving further avoids: a parallel must outweigh any motion.
        assert parallels(voice_lead(['C','B','Fm','G'],voices=4,low=48,high=66,avoid_parallels=True))==0
        caps=[64,62,64,60];capped=voice_lead(['F','G','Em','Am'],voices=3,ceilings=caps)
        assert all(v[-1]<=c for v,c in zip(capped,caps)),capped
        assert sorted(chord_tones('Cmaj13',3))==[4,9,11] and sorted(chord_tones('G7',5))==[2,5,7,7,11] and sorted(chord_tones('C/E',3))==[0,4,7]
        # Under a major seventh the root goes first and is not doubled against it; with one G-flat in range the fifth is
        # doubled instead of the root.
        assert sorted(chord_tones('Cmaj7',3))==[4,7,11] and sorted(chord_tones('Cmaj7',5))==[0,4,7,7,11]
        gb=voice_lead(['Gb'],voices=4,low=55,high=76)
        assert sorted(p%12 for p in gb[0])==[1,1,6,10],gb
        # Against a left hand, the right hand leaves its keys and their minor seconds and ninths alone.
        rub=lambda a,b:abs(a-b) in (1,13)
        lh=[[48,55],[57,64],[53,60],[55,62]];alone=voice_lead(['C','Am','F','G'],voices=4,low=55,high=79)
        apart=voice_lead(['C','Am','F','G'],voices=4,low=55,high=79,against=lh)
        clash=lambda vs:[p for v,l in zip(vs,lh) for p in v if p in l or any(rub(p,q) for q in l)]
        assert clash(alone) and not clash(apart),(alone,apart)
        # A melody on the root of a major-seventh chord: the seventh would rub against it wherever it went in the range,
        # so the chord becomes a triad; the third stays.
        tri=voice_lead(['Abmaj7'],voices=3,low=48,high=72,against=[[68,80]])
        assert sorted({p%12 for p in tri[0]})==[0,3,8] and not any(rub(p,q) for p in tri[0] for q in (68,80)),tri
        # With no bass part the root stays: a rootless A-flat major seventh in three voices would be C minor.
        alone=voice_lead(['Abmaj7','Bb7','Gm7','Cm7'],voices=3,low=48,high=67,keep_root=True)
        assert all(r in {p%12 for p in v} for v,r in zip(alone,(8,10,7,0))) and 8 not in chord_tones('Abmaj7',3),alone
        low=voice_lead(['C','F','G','C'],voices=4,low=36,high=60)
        for v in jazz+smooth+strict+low+gb+apart:
            assert v==sorted(v) and all(0<b-a<=12 for a,b in zip(v,v[1:])) and all(a>=LOW_INTERVAL_LIMITS.get(b-a,0) for a,b in zip(v,v[1:])),v
            assert not any(rub(a,b) for i,a in enumerate(v) for b in v[i+1:]),v
        return {'ii_V_I':jazz,'pop_motion':motion(smooth),'root_position_motion':motion(naive),'parallels':[parallels(free),parallels(strict)]}
    check('voicing_moves_smoothly_and_spaces_chords',voicing_helper)
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
    check('synth_is_band_limited_stable_and_repeatable',synth_engine)
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
    check('drum_machine_voices_kick_pitch_drop_and_gated_snare',drum_machine)
    def production_tools():
        from musiclib import production
        p=example();p['clock']['tempo']=[[0,120],[8,90]];clock=Clock(p)
        n=int(clock.seconds(16)*48000)+48000;stem=np.zeros((n,2));i=int(clock.seconds(7.5)*48000);stem[i]=1.0
        t={'id':'pad','mix':{'delay':{'beats':1,'feedback':.5,'send_db':0,'highpass':20,'lowpass':20000}}}
        y,_=production.delay(stem,t,clock)
        # The first echo of a click at beat 7.5 lands at beat 8.5, across the tempo change, within a sample.
        want=clock.seconds(8.5)*48000;got=i+1+int(np.argmax(np.abs(y[i+1:,0])))
        assert abs(got-want)<=1.5,(got,want)
        kick={'id':'kick','notes':[{'id':f'k{b}','on':b,'duration':.25,'pitch':36} for b in range(4)],'performance':{'notes':{f'k{b}':{'velocity':100} for b in range(4)}}}
        q={'tracks':[kick],'clock':p['clock']};pad={'id':'pad','mix':{'duck':{'by':'kick','depth_db':9,'attack_ms':4,'hold_ms':20,'release_ms':200}}}
        g,_=production.duck(np.ones((n,2)),q,pad,clock);hit=int(clock.seconds(1)*48000)
        assert abs(20*np.log10(g[hit+int(.01*48000),0])+9)<.1 and g[hit+int(.45*48000),0]>.97,(g[hit+480,0],g[hit+21600,0])
        side=np.zeros((48000,2));tone=np.sin(2*np.pi*60*np.arange(48000)/48000);side[:,0]=tone;side[:,1]=-tone
        m=production.mono_below(side,120);assert np.abs(m[4800:-4800,0]-m[4800:-4800,1]).max()<.05
        gated,_=production.gate(np.ones((48000*2,2)),{'id':'x','mix':{'gate':{'pattern':'x.','step_beats':.5}}},Clock({'clock':{'bars':4,'meter':[4,4],'tempo':[[0,120]]}}))
        assert gated[int(.1*48000),0]>.99 and gated[int(.35*48000),0]<.01
        # A sweep that jumps back (a high-pass reset on a drop) stays as loud as its input: the filter's state is the
        # signal itself, so the jump leaves no burst.
        x=np.random.default_rng(4).standard_normal((48000*8,2))*.1;c4=Clock({'clock':{'bars':4,'meter':[4,4],'tempo':[[0,120]]}})
        y,_=production.filter_sweep(x,{'id':'p','mix':{'filter_sweep':{'type':'highpass','points':[[0,20],[7.99,1600],[8,20]],'resonance':.35}}},c4)
        jump=float(np.abs(y[4*48000-2400:4*48000+4800]).max()/np.abs(x).max())
        assert jump<1.5,jump
        return {'echo_sample_error':round(float(got-want),2),'sweep_jump_peak_ratio':round(jump,2)}
    check('production_delay_duck_gate_and_mono_low_end',production_tools)
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
    check('chip_arpeggio_stepped_triangle_and_clocked_noise',chip_sounds)
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
    check('synth_pitch_envelope_punches_and_settles',pitch_envelope)
    def worn_media():
        from musiclib import production
        rate=48000;n=rate*6;t=np.arange(n)/rate;x=np.stack([np.sin(2*np.pi*1000*t)]*2,axis=1)
        y,info=production.wow_flutter(x,{'wow_cents':10,'wow_hz':.5,'flutter_cents':0},'keys')
        # The pitch of a 1 kHz tone swings by the cents asked for, and no click lands more than 2 ms from its place.
        S=np.fft.fft(y[:,0]);h=np.zeros(n);h[0]=1;h[1:n//2]=2;ph=np.unwrap(np.angle(np.fft.ifft(S*h)))
        f=np.convolve(np.diff(ph)*rate/(2*np.pi),np.ones(480)/480,mode='valid')[rate:-rate];c=1200*np.log2(f/1000)
        assert 8.5<c.max()<10.5 and -10.5<c.min()<-7.5,(c.max(),c.min())
        clicks=np.zeros((n,2));clicks[::rate//2]=1;z,_=production.wow_flutter(clicks,{'wow_cents':10,'wow_hz':.5},'keys')
        offs=[int(np.argmax(np.abs(z[k-2000:k+2000,0])))-2000 for k in range(rate//2,n-rate,rate//2)]
        assert max(map(abs,offs))<96 and abs(np.mean(offs))<20,offs
        again,_=production.wow_flutter(x,{'wow_cents':10,'wow_hz':.5,'flutter_cents':0},'keys');assert np.array_equal(y,again)
        v=production.vinyl(rate*10,np.random.default_rng(2))
        # Surface noise: a crackle far above the hiss, partly different in the two channels, and repeatable.
        crest=20*np.log10(np.abs(v).max()/np.sqrt(np.mean(v**2)));corr=float(np.corrcoef(v[:,0],v[:,1])[0,1])
        assert crest>20 and .1<corr<.9 and np.array_equal(v,production.vinyl(rate*10,np.random.default_rng(2))),(crest,corr)
        bad=example();bad['tracks'][0]['mix']['wow_flutter']={'wow_cents':80};rejects(lambda:validate(bad))
        return {'wow_cents':[round(float(c.min()),2),round(float(c.max()),2)],'peak_shift_ms':info['peak_shift_ms'],'vinyl_crest_db':round(float(crest),1)}
    check('tape_wow_flutter_and_vinyl_noise',worn_media)
    def chorus_effect():
        from musiclib import production
        rate=48000;n=rate*8;t=np.arange(n)/rate
        # A 1 kHz tone gains nothing far above it: the moving delay is read between samples. FFmpeg's chorus stepped it
        # (energy above 4 kHz 52 dB under the tone) and read a voice 61.5 ms late whenever its delay reached zero.
        y,info=production.chorus(np.stack([.5*np.sin(2*np.pi*1000*t)]*2,axis=1),.6)
        S=np.abs(np.fft.rfft(y[rate:7*rate,0]*np.hanning(6*rate)))**2;f=np.fft.rfftfreq(6*rate,1/rate)
        above=10*np.log10(S[f>4000].sum()/S.sum())
        assert above<-75,above
        # Every impulse comes back within 80 samples (dry 0.63, the voices within 1.2 and 1.5 ms; the cubic reading
        # starts a sample early; a moving delay changes a voice's sum by its Doppler factor, under 0.2%) and never later.
        x=np.zeros((n,2));x[rate//4::rate//4]=1;z,_=production.chorus(x,.6)
        for k in range(rate//4,n-rate,rate//4):
            assert abs(z[k-2:k+80,0].sum()-.9*1.24)<2e-3 and np.abs(z[k+80:k+6000,0]).max()<1e-12,(k,z[k-2:k+80,0].sum())
        return {'above_4khz_db':round(float(above),1),'sweeps_ms':info['sweeps_ms']}
    check('chorus_reads_its_moving_delay_between_samples',chorus_effect)
    def stage_depth():
        from musiclib import stage
        x=np.random.default_rng(3).standard_normal((48000*3,2)).astype(np.float32)*.1;rows=[]
        for depth in (0,4,8):
            y,info=stage.place(x,0.,depth);er=stage.reflections(0.,depth)
            rows.append((10*np.log10(np.mean(y.astype(float)**2)/np.mean(x.astype(float)**2)),info['reflection_share_db'],info['hall_send_boost_db'],float(np.corrcoef(er[:,0],er[:,1])[0,1]),info['first_reflection_ms']))
        # The part keeps its loudness; deeper, its reflections and its hall send grow; the two capsules differ.
        assert all(abs(r[0])<.05 for r in rows) and rows[0][1]<rows[1][1]<rows[2][1] and rows[0][2]==0<rows[1][2]<rows[2][2],rows
        assert all(r[3]<.5 and r[4]>=1 for r in rows),rows
        return {'reflection_share_db':[r[1] for r in rows],'hall_send_boost_db':[r[2] for r in rows]}
    check('stage_depth_moves_reflections_and_hall',stage_depth)
    def expressive_fields():
        p=example();t=p['tracks'][1];validate(p)
        t['performance']['dynamics']=[[0,20],[8,110]];t['performance']['legato']={'mode':'crossfade','crossfade_ms':120};validate(p)
        t['mix']['depth_m']=6;p['mix'].update(chain='bus',dynamics='wide',range_lu=12);validate(p)
        for bad in (lambda q:q['tracks'][1]['performance'].update(dynamics=[[4,20],[2,110]]),lambda q:q['tracks'][1]['performance']['legato'].update(crossfade_ms=900),
                    lambda q:q['tracks'][1]['performance'].update(cc=[[0,1,64]]),lambda q:q['tracks'][1]['mix'].update(depth_m=12),
                    lambda q:q['mix'].update(dynamics='glue'),lambda q:q.update(loop={'start_bar':0}),lambda q:q['mix'].update(chain='room')):
            q=copy.deepcopy(p);bad(q);rejects(lambda:validate(q))
        return True
    check('expressive_fields_validate',expressive_fields)
    def range_master():
        from musiclib import mixbus
        rng=np.random.default_rng(5);t=np.arange(48000*60)/48000
        env=np.where(t<20,10**(-28/20),np.where(t<40,10**(-14/20),10**(-22/20)))
        x=(rng.standard_normal((len(t),2))*.3*env[:,None]).astype(np.float32);audio.write_wav(work/'range_in.wav',x)
        info=mixbus.range_control(work/'range_in.wav',work/'range_out.wav',8);y,_=audio.read_wav(work/'range_out.wav')
        lev=lambda a,s,e:10*np.log10(np.mean(a[int(s*48000):int(e*48000)].astype(float)**2))
        # The loudest passage keeps its level; the soft ones rise, the softest most, and their order stays.
        loud,soft,mid=lev(y,22,38)-lev(x,22,38),lev(y,2,18)-lev(x,2,18),lev(y,42,58)-lev(x,42,58)
        assert info['lra_before_lu']>12 and info['lra_after_lu']<=8.3 and abs(loud)<.2 and soft>mid>1 and lev(y,2,18)<lev(y,42,58)<lev(y,22,38),(info,loud,soft,mid)
        return {**info,'lift_db':{'softest':round(soft,2),'middle':round(mid,2),'loudest':round(loud,2)}}
    check('range_control_lifts_soft_passages_only',range_master)
    def transposed_samples():
        from musiclib import review as rv
        from musiclib.model import Clock
        # One preset over keys 60-90: a zone recorded at 60 serves 60-72, a zone recorded at 67 with coarse tune +12
        # serves 73-84; nothing serves 85 and up.
        bank={'presets':[{'bank':0,'program':1,'zones':[{'gens':{43:(60,90)},'mods':[],'target':0}]}],
              'instruments':[{'zones':[{'gens':{43:(60,72),58:60},'mods':[],'target':0},{'gens':{43:(73,84),51:12},'mods':[],'target':1}]}],
              'samples':[{'root':60},{'root':67}]}
        m=rv.transposition(bank,0,1)
        assert m[60]==0 and m[64]==4 and m[72]==12 and m[73]==18 and 85 not in m and rv.transposition(bank,0,2) is None
        q=example();t=q['tracks'][0]
        t['notes']=[{'id':f'x{k}','on':k,'duration':1,'pitch':x} for k,x in enumerate((60,64,65,73,86))]
        st=rv.stretched(q,Clock(q),{t['id']:m})
        assert st['count']==2 and st['outside_count']==1 and st['by_track'][t['id']]['worst']['semitones']==18,st
        # A high-pass close under a part's lowest note thins it: 45 Hz takes 2.8 dB from F#1 and 5.1 dB from D1, under
        # 1 dB from D2, and an octave under the note takes 0.26 dB; parts that do not sound at their written pitch are
        # left out (review asks past 1.5 dB).
        part=lambda hp,low,**k:{'engine':'soundfont','notes':[{'pitch':low},{'pitch':low+12}],'mix':{'highpass':hp},**k}
        cuts=[rv.highpass_cut(part(45,low))[0] for low in (30,26,38)]
        assert abs(cuts[0]-2.78)<.02 and abs(cuts[1]-5.13)<.02 and cuts[2]<1 and abs(rv.highpass_cut(part(440*2**((30-69)/12)/2,30))[0]-.26)<.01,cuts
        assert rv.highpass_cut(part(45,30,drums=True)) is None and rv.highpass_cut(part(45,30,engine='surge')) is None
        # The cutoff review suggests is one validate accepts: an octave under D1, but 15 Hz under A0 (0.4 dB).
        (d1,d1_db),(a0,a0_db)=rv.highpass_floor(440*2**((26-69)/12)),rv.highpass_floor(27.5)
        assert abs(d1-18.35)<.01 and abs(d1_db-.26)<.01 and a0==15 and abs(a0_db-.37)<.01,(d1,d1_db,a0,a0_db)
        fresh=example();fresh['tracks'][0]['mix']['highpass']=a0;validate(fresh)
        return {'flagged':st['count'],'outside':st['outside_count'],'highpass_cut_db':[round(c,2) for c in cuts]}
    check('review_flags_far_transposed_samples_and_missing_keys',transposed_samples)
    def melody_group_and_balance():
        from musiclib import analysis
        q=example();q['tracks']=q['tracks'][:3]
        a,b,c=q['tracks'];a['role']='melody';b['role']='harmony';c['role']='harmony'
        a['notes']=[{'id':f'a{k}','on':k,'duration':1,'pitch':60+k} for k in range(6)]
        b['notes']=[{'id':f'b{k}','on':k,'duration':1,'pitch':72+k} for k in range(6)]  # the tune an octave up
        c['notes']=[{'id':f'c{k}','on':k,'duration':1,'pitch':48} for k in range(6)]
        group=analysis.doublings(q,0,8)
        assert group==sorted([a['id'],b['id']]),group
        levels={a['id']:-20.0,b['id']:-22.0,c['id']:-23.0}
        cut=analysis.balance(q,levels,group)
        assert len(cut)==1 and cut[0]['track']==c['id'] and cut[0]['suggested_cut_db']==3.0,cut
        c['role']='bass';assert analysis.balance(q,levels,group)==[]  # a bass may sit 3 dB under the tune
        # A lead that rests through a section has no active frames there and no figures, not a masked share of 0/0
        # (NaN, which a report cannot hold); one that plays gets them.  (Found by a review of 0.4.0.)
        rate=audio.RATE;n=4*rate;tone=(np.sin(2*np.pi*440*np.arange(n)/rate)*.1)[:,None].repeat(2,axis=1)
        rows=analysis.lead_presence(np.zeros((n,2)),tone,[('a',0,n)])
        assert rows==[{'section':'a','lead_active_frames':0}] and json.dumps(rows,allow_nan=False),rows
        rows=analysis.lead_presence(tone,tone*.5,[('a',0,n)])
        assert rows[0]['lead_active_frames']>5 and all(np.isfinite(v) for k,v in rows[0].items() if k!='section'),rows
        return {'group':group,'suggestion':cut[0],'silent_lead_has_no_figures':True}
    check('analysis_groups_octave_doublings_and_suggests_cuts',melody_group_and_balance)
    def strict_projects():
        # A JSON float where MIDI needs an integer (100.0) and a section id that is not text stop in validation, with
        # the place and the value; a misspelt optional field is reported with the name it was probably meant to be.
        p=example();t=p['tracks'][0];n=t['notes'][0]
        t['performance']['notes'][n['id']]['velocity']=100.0
        try:validate(p);raise AssertionError('accepted a float velocity')
        except ValueError as e:assert f'{t["id"]}/{n["id"]} velocity' in str(e) and 'write 100, not 100.0' in str(e),e
        p=example();p['sections'][0]['id']=1;rejects(lambda:validate(p))
        p=example();p['clock']['meter']=[4,4.0];rejects(lambda:validate(p))
        p=example();p['tracks'][0]['mix']['revrb_db']=-12;p['tracks'][0]['performance']['timming_ms']=3;p['mixx']={}
        warnings=validate(p)['warnings']
        assert any("'revrb_db' (did you mean 'reverb_db'?)" in w for w in warnings) and any("'timming_ms'" in w for w in warnings) and any("'mixx'" in w for w in warnings),warnings
        assert validate(example())['warnings']==[]
        p=example();del p['tracks'][0]['performance']['notes'][p['tracks'][0]['notes'][0]['id']]['velocity']
        try:validate(p);raise AssertionError('accepted a note without velocity')
        except ValueError as e:assert 'velocity' in str(e) and p['tracks'][0]['id'] in str(e),e
        return {'warnings':len(warnings)}
    check('integer_fields_and_unknown_fields_are_reported',strict_projects)
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
        assert surge.dependencies({},st)['host']==file_hash(Path(__file__).resolve().parent/'surge_host.py')
        return {'sections_moved':'new key','mix_changed':'same key'}
    check('synthesis_cache_follows_the_played_tempo',cache_identity)
    def slow_rubato_midi():
        p=example();p['clock']={'bars':2,'meter':[4,4],'tempo':[[0,30]],'rubato':{'final_beats':8,'final_ratio':.3}}
        p['sections']=[{'id':'a','start_bar':0,'bars':2}]
        for t in p['tracks']:
            keep=[n for n in t['notes'] if n['on']+n['duration']<=8][:2];t['notes']=keep
            t['performance']['notes']={n['id']:t['performance']['notes'][n['id']] for n in keep}
            t['performance'].pop('cc',None);t['mix'].pop('automation',None)
        p['tracks']=[t for t in p['tracks'] if t['notes']]
        validate(p);out=work/'slow.mid';midi.write(p,out);m=midi.read(out)
        slowest=60_000_000/max(v for _,v in m['tempos'])
        assert slowest<15 and sum(len(t['notes']) for t in m['tracks'])==sum(len(t['notes']) for t in p['tracks'])
        return {'slowest_bpm':round(slowest,2)}
    check('slow_rubato_reads_back_from_its_midi',slow_rubato_midi)
    def drum_ports():
        p=example();kit=copy.deepcopy(next(t for t in p['tracks'] if t.get('drums')) if any(t.get('drums') for t in p['tracks']) else p['tracks'][0])
        kit.update(drums=True,program=0);a=copy.deepcopy(kit);a['id']='kit_a';b=copy.deepcopy(kit);b['id']='kit_b';b['program']=16
        p['tracks']=[x for x in p['tracks'] if not x.get('drums')]+[a,b];route=midi.write(p,work/'two_kits.mid')
        kits=[(r['port'],r['channel']) for r in route if r['track'] in ('kit_a','kit_b')]
        assert kits==[(0,9),(1,9)],kits
        return {'kits':kits}
    check('drum_parts_get_their_own_ports',drum_ports)
    def meter_arches():
        from musiclib.expression import phrase_positions
        t={'notes':[{'id':str(b),'on':b,'duration':1} for b in (0,3,6,9,12,15,16)]}
        pos=phrase_positions(t,[{'start_bar':0},{'start_bar':4}],False,3.0)
        assert pos['12']==0 and pos['0']==0 and abs(pos['9']-.75)<1e-9,pos
        return {'three_four_section_starts_at_beat':12}
    check('phrase_arches_follow_the_meter',meter_arches)
    def excerpt_curves():
        from musiclib.model import curve_at
        p=example();t=p['tracks'][0];total=p['clock']['bars']*Clock(p).beats_per_bar
        t['performance']['bend_range']=2;t['performance']['bend']=[[2,0],[6,1.5],[9,-1]]
        t['mix']['filter_sweep']={'type':'lowpass','points':[[0,300],[total,8000]]}
        validate(p);q=extract(p,2,2);u=q['tracks'][0];start=Clock(p).beats_per_bar
        for b in (0,1.5,3.9):
            assert abs(curve_at(u['performance']['bend'],b)-curve_at(t['performance']['bend'],b+start))<1e-9
            assert abs(curve_at(u['mix']['filter_sweep']['points'],b)-curve_at(t['mix']['filter_sweep']['points'],b+start))<1e-6
        # The wheel an excerpt plays is the source's at every eighth of a beat: a bend rests at 0 before its first point
        # and a jump (two points on one beat) on either cut stays a jump.
        from excerpt import crop
        from musiclib.model import bend_events
        def wheel(curve,b):
            v=8192
            for beat,value in bend_events({'performance':{'bend':curve,'bend_range':2}}):
                if beat<=b+1e-9:v=value
            return v
        for pts,a,b in (([[8,2],[12,2]],0,16),([[0,0],[4,0],[4,2],[8,2]],0,4),([[4,0],[4,2],[6,2]],4,8),([[2,0],[6,1.5],[9,-1]],4,12)):
            cut=crop(pts,a,b,bend=True)
            assert all(wheel(pts,a+k/8)==(wheel(cut,k/8) if cut else 8192) for k in range(int((b-a)*8))),(pts,a,b,cut)
        # A key held across the cut and struck again right at it is not re-attacked as well (that would strike it twice
        # at once); one held across the cut and struck again later is; of two held at once, only the later attack.
        p=example();t=p['tracks'][0];bpb=Clock(p).beats_per_bar
        t['notes']=[{'id':'held','on':bpb-1,'duration':2,'pitch':50},{'id':'again','on':bpb,'duration':1,'pitch':50},
                    {'id':'long','on':bpb-2,'duration':4,'pitch':55},{'id':'later','on':bpb-1,'duration':4,'pitch':55},
                    {'id':'ring','on':bpb-1,'duration':3,'pitch':60},{'id':'next','on':bpb+1,'duration':1,'pitch':60}]
        t['performance']['notes']={n['id']:{'velocity':80} for n in t['notes']};validate(p)
        kept=sorted(n['id'] for n in extract(p,2,2)['tracks'][0]['notes'])
        assert kept==['again','later','next','ring'],kept
        # A long note struck again, shorter, before the cut has stopped by the cut: it is not re-attacked there.
        p=example();t=p['tracks'][0]
        t['notes']=[{'id':'old','on':0,'duration':8,'pitch':60},{'id':'last','on':3,'duration':.5,'pitch':60},
                    {'id':'pedal','on':0,'duration':8,'pitch':62},{'id':'short','on':2,'duration':1,'pitch':62},
                    {'id':'active','on':4,'duration':1,'pitch':67}]
        t['performance']['notes']={n['id']:{'velocity':80} for n in t['notes']};validate(p)
        stopped=sorted(n['id'] for n in extract(p,2,1)['tracks'][0]['notes'])
        assert stopped==['active'],stopped
        # A re-attack that the notes' own timings put on the tick of the next strike of its key (the held note 100 ms
        # late, the next 20 ms early) is left out, where it would stop the render.
        p=example();p['clock']['tempo']=[[0,120]];t=p['tracks'][0]
        t['notes']=[{'id':'held','on':3,'duration':2,'pitch':60},{'id':'next','on':4.24,'duration':.5,'pitch':60}]
        t['performance']['notes']={'held':{'velocity':80,'timing_ms':100},'next':{'velocity':80,'timing_ms':-20}};validate(p)
        timed=[n['id'] for n in extract(p,2,1)['tracks'][0]['notes']]
        assert timed==['next'],timed
        # So is one that the next strike of its key follows within 100 ms as played; a strike later than that keeps it.
        for on,timing,want in ((4.02,0,['next']),(4.3,-20,['held','next']),(4.24,-60,['next'])):
            t['notes'][1]['on']=on;t['performance']['notes']={'held':{'velocity':80},'next':{'velocity':80,'timing_ms':timing}};validate(p)
            got=[n['id'] for n in extract(p,2,1)['tracks'][0]['notes']]
            assert got==want,(on,timing,got)
        # The passage's own notes that the part's earlier offset plays before the cut all sound at the excerpt's start;
        # of a key struck so more than once, only its last strike stays (the piece's later strikes had stopped the rest).
        p=example();p['clock']['tempo']=[[0,120]];t=p['tracks'][0];t['performance']['offset_ms']=-300
        t['notes']=[{'id':k,'on':on,'duration':1,'pitch':57} for k,on in (('a',4),('b',4.05),('c',4.5),('d',4.75))]
        t['performance']['notes']={n['id']:{'velocity':80} for n in t['notes']};validate(p)
        early=[n['id'] for n in extract(p,2,1)['tracks'][0]['notes']]
        assert early==['c','d'],early
        return {'bend_points':len(u['performance']['bend']),'held_notes_kept_at_the_cut':kept,'stopped_before_the_cut':stopped,'retimed_onto_the_next':timed,'played_before_the_cut':early}
    check('excerpt_moves_bends_sweeps_and_dynamics',excerpt_curves)
    def mono_lines():
        from musiclib import synth
        notes=[{'start_seconds':k*.5,'end_seconds':k*.5+.5,'pitch':40} for k in range(100)]
        lines=synth.voices(notes,{'mono':True})
        assert len(lines)==2 and lines[1][0]['start_seconds']==synth.MONO_LINE_S,[len(x) for x in lines]
        return {'unbroken_legato_seconds':synth.MONO_LINE_S}
    check('a_long_mono_line_starts_afresh_after_thirty_seconds',mono_lines)
    def fluidsynth_log():
        from musiclib import audio as au
        real=au.run
        try:
            au.run=lambda *a,**k:"Rendering audio to file 'work/terror-game/failed takes/raw.wav'..\n"
            au.fluidsynth({'fluidsynth':{'path':'x'}},'f.sf2','in.mid','out.wav',work)
            au.run=lambda *a,**k:'fluidsynth: warning: Instrument not found on channel 0 [bank=0 prog=5], substituted [bank=0 prog=0]\n'
            rejects(lambda:au.fluidsynth({'fluidsynth':{'path':'x'}},'f.sf2','in.mid','out.wav',work))
        finally:au.run=real
        return {'paths_with_error_words':'accepted'}
    check('fluidsynth_diagnostics_ignore_its_paths',fluidsynth_log)
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
        save_json(root/'manifest.json',good);script=str(Path(__file__).with_name('soundbank.py'))
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
    check('a_cut_manifest_writes_only_inside_its_folder',files_stay_inside)
    def no_overwrite():
        import subprocess,sys
        here=Path(__file__).resolve().parent;mid=work/'own.mid';midi.write(example(),mid);before=mid.read_bytes()
        done=subprocess.run([sys.executable,str(here/'studio.py'),'inspect-midi',str(mid),'--output',str(mid)],capture_output=True,text=True)
        assert done.returncode==2 and mid.read_bytes()==before,done.stderr
        return {'exit':done.returncode}
    check('inspect_midi_keeps_its_input',no_overwrite)
    def relative_banks():
        import subprocess,sys
        here=Path(__file__).resolve().parent;old=work/'cfg_old';new=work/'cfg_new';old.mkdir(exist_ok=True);new.mkdir(exist_ok=True)
        for name in ('fs.exe','ff.exe'):(old/name).write_bytes(name.encode())
        bank=xf_bank();shutil.copy2(bank,old/'own.sf2')
        cfg={k:{'path':n,'sha256':file_hash(old/n)} for k,n in (('fluidsynth','fs.exe'),('ffmpeg','ff.exe'),('soundfont','own.sf2'))}
        cfg['soundfonts']={'named':{'path':'own.sf2','sha256':file_hash(old/'own.sf2')}};save_json(old/'config.json',cfg)
        done=subprocess.run([sys.executable,str(here/'studio.py'),'add-soundfont','--config',str(old/'config.json'),'--name','added','--path',str(bank),
                             '--license','test','--source','test','--version','1','--output',str(new/'config.json')],capture_output=True,text=True)
        assert done.returncode==0,done.stderr
        loaded=audio.load_config(new/'config.json');assert Path(loaded['soundfonts']['named']['path'])==(old/'own.sf2').resolve()
        # configure checks its bank's tables as add-soundfont does: a file that is no SoundFont is refused, a bank is
        # configured.  (Found by a review of 0.4.0.)
        (old/'not-a-bank.sf2').write_text('plain text',encoding='utf-8')
        for font,want in ((old/'not-a-bank.sf2',2),(bank,0)):
            out=new/f'configured_{want}.json'
            done=subprocess.run([sys.executable,str(here/'studio.py'),'configure','--fluidsynth',str(old/'fs.exe'),'--ffmpeg',str(old/'ff.exe'),
                                 '--soundfont',str(font),'--output',str(out)],capture_output=True,text=True)
            assert done.returncode==want and out.is_file()==(want==0),(font,done.returncode,done.stderr[-300:])
        return {'named_bank':'still found','configure_refuses_a_file_that_is_no_bank':True}
    check('a_config_written_elsewhere_keeps_relative_banks',relative_banks)
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
        return {'short_read':'tried again, never cached','damaged_cache':'downloaded again','damaged_wheel':'replaced'}
    check('a_short_or_damaged_download_is_never_kept',short_downloads)
    def compare_unit():
        # Hand-made renders of the setup study (no buses: the premix is the stems summed), the bass a quiet part:
        # - note: the piano's note in bar 3 changes and its whole part moves 0.2 dB, as a part whose level is set from
        #   its loudness can (one note moved a piano 0.01 dB here and 0.11 dB on Ubuntu's FluidSynth), under a master
        #   0.3 dB quieter;
        # - louder: only the lead is 1 dB louder;
        # - quiet_bass: the same note change while the bass is 6 dB louder.
        # Every passage stays in the report.  The parts' level moves account only for their own share of a mix, so the
        # note is a change in the premix and the master however far another part moved, and from the note on only.
        from musiclib.compare import compare,first_change
        p=example();clock=Clock(p);rate=audio.RATE;frames=round((clock.end+clock.tail)*rate);t=np.arange(frames)/rate
        def tone(k,amp=.1):
            x=amp*np.sin(2*np.pi*110*2**(k/5)*t)*(1+.5*np.sin(2*np.pi*.3*t+k));return np.stack([x,.9*x],axis=1)
        stems={tr['id']:tone(k,.01 if tr['id']=='bass' else .1) for k,tr in enumerate(p['tracks'])}
        on,off=clock.seconds(8.5),clock.seconds(10);a,b=int(on*rate),int(off*rate)
        note=copy.deepcopy(p);next(n for n in note['tracks'][0]['notes'] if n['id']=='piano_n7')['pitch']+=1
        note_stems={k:v.copy() for k,v in stems.items()};note_stems['piano'][a:b]=tone(9)[a:b];note_stems['piano']*=10**(.2/20)
        louder=copy.deepcopy(p);next(tr for tr in louder['tracks'] if tr['id']=='lead')['mix']['level_dbfs']+=1
        louder_stems={k:v*(10**(1/20) if k=='lead' else 1) for k,v in stems.items()}
        quiet=copy.deepcopy(note);next(tr for tr in quiet['tracks'] if tr['id']=='bass')['mix']['level_dbfs']+=6
        quiet_stems={k:v.copy() for k,v in stems.items()};quiet_stems['piano'][a:b]=tone(9)[a:b];quiet_stems['bass']*=2
        for name,proj,parts,master_db in (('before',p,stems,0),('note',note,note_stems,-.3),('louder',louder,louder_stems,0),('quiet_bass',quiet,quiet_stems,0)):
            out=work/'compare_unit'/name;(out/'stems').mkdir(parents=True,exist_ok=True)
            save_json(out/'project.json',proj);save_json(out/'report.json',{'renderer_sha256':'one','master':{'integrated_lufs':-18}})
            again=lambda k:k+('2' if name in ('note','quiet_bass') and k=='piano' else '')
            save_json(out/'stem_receipts.json',[{'track':k,'cache_key':again(k),'raw_sha256':again(k)} for k in parts])
            for k,x in parts.items():audio.write_wav(out/'stems'/f'{k}.wav',x.astype(np.float32))
            mix=sum(parts.values());audio.write_wav(out/'premix.wav',mix.astype(np.float32));audio.write_wav(out/'master.wav',(mix*10**(master_db/20)).astype(np.float32))
        real=lambda e:[q for q in e.get('passages',[]) if not q.get('follows_part_levels')]
        r=compare(work/'compare_unit'/'before',work/'compare_unit'/'note',work/'compare_unit'/'difference');f=r['files']
        assert r['summary']['project']==['piano note piano_n7 at 3:1.5: pitch 64 -> 65'] and r['synthesis']['synthesized_again']==['piano'],r['summary']
        assert [k for k,e in f['stems'].items() if not e['identical']]==['piano'] and f['stems']['piano']['level_db']==.2,f['stems']['piano']
        assert abs(f['premix']['premix']['level_db'])<.1 and abs(f['master']['master']['level_db']+.3)<.1,(f['premix'],f['master'])
        for e in (f['stems']['piano'],f['premix']['premix'],f['master']['master']):
            assert len(real(e))==1 and abs(real(e)[0]['start_s']-on)<.02 and abs(real(e)[0]['end_s']-off)<.02,e
        assert 'note' not in r['summary'] or 'piano +0.20 dB' in r['summary']['note'],r['summary']
        d,_=audio.read_wav(work/'compare_unit'/'difference'/'stems_piano.wav');d=np.abs(np.asarray(d))
        assert d[:a-480].max()<1e-5 and d[b+480:].max()<1e-5 and d[a:b].max()>.05,'the difference is the changed note alone'
        m=compare(work/'compare_unit'/'before',work/'compare_unit'/'louder');g=m['files']
        assert m['summary']['project']==['lead mix: level_dbfs -25 -> -24'] and m['synthesis']['synthesized_again']==[]
        assert g['stems']['lead']['level_db']==1 and not g['stems']['lead']['passages'] and m['summary']['changed']['stems']=={'lead':'level only, +1.00 dB'}
        assert not real(g['premix']['premix']) and not real(g['master']['master']),(g['premix'],g['master'])
        q=compare(work/'compare_unit'/'before',work/'compare_unit'/'quiet_bass');h=q['files']
        assert h['stems']['bass']['level_db']==6.02 and not h['stems']['bass']['passages'],h['stems']['bass']
        for e in (h['premix']['premix'],h['master']['master']):
            assert real(e) and abs(real(e)[0]['start_s']-on)<.02 and all(x['start_s']>on-.02 for x in real(e)),e
        # A change and the level passages around it never overlap, even a change shorter than the joining gap with the
        # piano's level move on both sides of it.
        blip=copy.deepcopy(note);bl={k:v.copy() for k,v in stems.items()};z=a+int(.1*rate)
        bl['piano'][a:z]=tone(9)[a:z];bl['piano']*=10**(.2/20)
        out=work/'compare_unit'/'blip';(out/'stems').mkdir(parents=True,exist_ok=True)
        save_json(out/'project.json',blip);save_json(out/'report.json',{'renderer_sha256':'one'})
        save_json(out/'stem_receipts.json',[{'track':k,'cache_key':k+('2' if k=='piano' else ''),'raw_sha256':k+('2' if k=='piano' else '')} for k in bl])
        for k,x in bl.items():audio.write_wav(out/'stems'/f'{k}.wav',x.astype(np.float32))
        mix=sum(bl.values());audio.write_wav(out/'premix.wav',mix.astype(np.float32));audio.write_wav(out/'master.wav',mix.astype(np.float32))
        def apart(res):
            for g in ('buses','returns','premix','master'):
                for e in res['files'][g].values():
                    ch,fo=real(e),[x for x in e.get('passages',[]) if x.get('follows_part_levels')]
                    assert not any(x['start_s']<y['end_s'] and y['start_s']<x['end_s'] for x in ch for y in fo),(g,e['passages'])
        bp=compare(work/'compare_unit'/'before',out)
        for e in (bp['files']['premix']['premix'],bp['files']['master']['master']):
            assert len(real(e))==1 and abs(real(e)[0]['start_s']-on)<.02 and abs(real(e)[0]['end_s']-z/rate)<.03,e
        # A chain with buses and a shared delay (the files as the bus mix writes them, the delay an echo):
        # - chain_echo: the bass, 40 dB under the lead, gets 6 dB louder while the lead changes 0.1 s of its tone; the
        #   lead's new echo in the shared delay is a change, not the bass's level move;
        # - chain_squash and chain_dynamics: the stems are identical and only the lead bus acts differently, with the
        #   project mix the same or changed: nothing there is put down to a part's level;
        # - band_after: the lead is loud lows with a high line 46 dB under them, through a fixed saturation, and the
        #   echo keeps 500-4000 Hz as the delay's filters do.  The high line changes for 0.1 s, the whole lead moves
        #   0.11 dB through the saturation and the bass gets 6 dB louder.  The lead's stem shows only its level, but
        #   the filtered echo brings the change out: a change in the return.  The saturation's small difference
        #   everywhere is still only the lead's level, there as in its stem;
        # - chain_tempo: as chain_echo with the tempo halved, so the delay's time doubles: the delay return, the premix
        #   and the master are changes from the start, and the clip starts there, not at the lead's change.
        cq=copy.deepcopy(p)
        for tr in cq['tracks']:
            if tr['id'] in ('bass','lead'):tr['mix']['delay_db']=-6
        tone2=lambda f,amp:np.stack([amp*np.sin(2*np.pi*f*t),.9*amp*np.sin(2*np.pi*f*t)],axis=1)
        lead0,bass0=tone2(1700,.1),tone2(1000,.001);e0,e1=int(6*rate),int(6.1*rate);lead1=lead0.copy();lead1[e0:e1]=tone2(2300,.1)[e0:e1]
        squash=lambda x:x*(1-.3*np.abs(x)/np.abs(x).max())
        def chain(name,proj,bass,lead,bus_lead=None,lag=.375,filt=None):
            out=work/'compare_unit'/name;(out/'stems').mkdir(parents=True,exist_ok=True);(out/'returns').mkdir(exist_ok=True)
            save_json(out/'project.json',proj);save_json(out/'report.json',{'renderer_sha256':'one'})
            save_json(out/'stem_receipts.json',[{'track':k,'cache_key':k,'raw_sha256':k} for k in ('bass','lead')])
            d=int(lag*rate);bus=lead if bus_lead is None else bus_lead;echo=np.zeros_like(lead);echo[d:]=.5*(bass+lead)[:-d]
            if filt:echo=filt(echo)
            for f,x in (('stems/bass',bass),('stems/lead',lead),('returns/bus_bass',bass),('returns/bus_lead',bus),('returns/delay_return',echo),('premix',bass+bus+echo),('master',bass+bus+echo)):
                audio.write_wav(out/f'{f}.wav',x.astype(np.float32))
            return out
        louder_bass=copy.deepcopy(cq);next(tr for tr in louder_bass['tracks'] if tr['id']=='bass')['mix']['level_dbfs']+=6
        wide=copy.deepcopy(cq);wide['mix'].update(dynamics='wide',chain='bus')  # validate: "wide" is the bus chain's
        c0=chain('chain_before',cq,bass0,lead0)
        ec=compare(c0,chain('chain_echo',louder_bass,2*bass0,lead1));g2=ec['files']
        assert g2['stems']['bass']['level_db']==6.02 and abs(real(g2['stems']['lead'])[0]['start_s']-6)<.02,g2['stems']
        dl=real(g2['returns']['delay']);assert dl and abs(dl[0]['start_s']-6.375)<.02 and dl[0]['end_s']>6.47,g2['returns']['delay']
        assert any(abs(x['start_s']-6)<.02 for x in real(g2['premix']['premix'])) and max(x['end_s'] for x in real(g2['premix']['premix']))>6.47,g2['premix']
        sq=compare(c0,chain('chain_squash',cq,bass0,lead0,squash(lead0)));dy=compare(c0,chain('chain_dynamics',wide,bass0,lead0,squash(lead0)))
        for res in (sq,dy):
            assert all(e['identical'] for e in res['files']['stems'].values()),res['summary']
            for g,n in (('buses','lead'),('premix','premix'),('master','master')):
                e=res['files'][g][n];assert e['passages'] and not any(x.get('follows_part_levels') for x in e['passages']),(g,e)
        fr=np.fft.rfftfreq(len(t),1/rate);band=lambda x:np.fft.irfft(np.fft.rfft(x,axis=0)*((fr>=500)&(fr<=4000))[:,None],n=len(x),axis=0)
        sat=lambda x:np.stack([np.tanh(4*x)/4,.9*np.tanh(4*x)/4],axis=1)
        low,hi0=.1*np.sin(2*np.pi*100*t),.0004*np.sin(2*np.pi*1700*t);hi1=hi0.copy();hi1[e0:e1]=.0004*np.sin(2*np.pi*2300*t[e0:e1])
        bd=compare(chain('band_before',cq,bass0,sat(low+hi0),filt=band),chain('band_after',louder_bass,2*bass0,sat(10**(.11/20)*(low+hi1)),filt=band))
        g3=bd['files'];assert g3['stems']['lead']['level_db'] and not g3['stems']['lead']['passages'],g3['stems']['lead']
        assert any(x['start_s']<6.38 and x['end_s']>6.47 for x in real(g3['returns']['delay'])),g3['returns']['delay']
        for g,n in (('returns','delay'),('premix','premix'),('master','master')):
            assert all(x['start_s']>6-.02 for x in real(g3[g][n])),(g,g3[g][n])
        slow=copy.deepcopy(louder_bass);slow['clock']['tempo']=[[b,bpm/2] for b,bpm in slow['clock']['tempo']]
        tp=compare(c0,chain('chain_tempo',slow,2*bass0,lead1,lag=.75));g4=tp['files']
        for g,n in (('returns','delay'),('premix','premix'),('master','master')):
            assert g4[g][n]['passages'] and not any(x.get('follows_part_levels') for x in g4[g][n]['passages']),(g,g4[g][n])
        assert first_change(tp)<1,first_change(tp)
        # The same delay at another tempo and length in quarter notes (0.75 at 100 BPM, 1.125 at 150: 0.45 s, though the
        # two products differ in the last digit) is the same route: a louder bass's move still follows the levels.
        eq0=copy.deepcopy(cq);eq0['clock']['tempo']=[[0,100]];eq1=copy.deepcopy(eq0);eq1['clock']['tempo']=[[0,150]]
        for tr in eq1['tracks']:
            if tr['id'] in ('bass','lead'):tr['mix']['delay_quarters']=1.125
        next(tr for tr in eq1['tracks'] if tr['id']=='bass')['mix']['level_dbfs']+=6
        bass2=tone2(1000,.01);eqr=compare(chain('equal_delay_before',eq0,bass2,lead0,lag=.45),chain('equal_delay_after',eq1,2*bass2,lead0,lag=.45))
        for g,n in (('returns','delay'),('premix','premix'),('master','master')):
            e=eqr['files'][g][n];assert e['passages'] and not real(e),(g,e)
        for res in (r,m,q,bp,ec,sq,dy,bd,tp,eqr):apart(res)
        return {'note':r['summary']['changed'],'louder':m['summary']['changed'],'quiet_bass':q['summary']['changed'],'echo':ec['summary']['changed'],
                'band':bd['summary']['changed'],'tempo':tp['summary']['changed']}
    check('compare_finds_level_and_local_changes',compare_unit)
    def compare_rewritten_level():
        # A file rewritten throughout has no overall level (more of it changed than one gain matches: its windows' gains
        # scatter, and their median once gave -332 dB); a level move keeps its level.
        from musiclib.compare import compare_audio,describe
        n=48000*4
        def line(seed):
            g=np.random.default_rng(seed);x=np.zeros(n);seg=np.arange(n//16)/48000
            for k in range(16):x[k*n//16:(k+1)*n//16]=.2*np.sin(2*np.pi*220*2**(g.integers(0,24)/12)*seg)*np.exp(-3*seg)
            return np.stack([x,.9*x],axis=1).astype(np.float32)
        a=line(1);audio.write_wav(work/'cmp_a.wav',a);clock=Clock(example());out={}
        for name,b in (('level',.5*a),('rewritten',line(2)),('quieter_rewrite',.05*line(3))):
            audio.write_wav(work/f'cmp_{name}.wav',b.astype(np.float32));e,_,_=compare_audio(work/'cmp_a.wav',work/f'cmp_{name}.wav',clock);out[name]=e['level_db']
        assert out['level']==-6.02 and out['rewritten'] is None and out['quieter_rewrite'] is None,out
        assert describe(e).startswith('no overall level'),describe(e)
        return out
    check('compare_reports_no_level_for_a_rewritten_file',compare_rewritten_level)
    def entry_lock_across_renders():
        # Renders sharing a cache: while one process holds a cache entry, another cannot take it, and can once it ends.
        import subprocess,sys
        from musiclib.render import entry_lock,keep_stem
        folder=work/'lock_entry';folder.mkdir()
        code=('import sys,time;sys.path.insert(0,sys.argv[1]);from musiclib.render import entry_lock\n'
              'with entry_lock(sys.argv[2]) as held:\n    print(held,flush=True);time.sleep(4)')
        holder=subprocess.Popen([sys.executable,'-c',code,str(Path(__file__).resolve().parent),str(folder)],stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='True'
            with entry_lock(folder,wait=False) as busy:assert busy is False
        finally:
            holder.wait(timeout=60);holder.stdout.close()
        with entry_lock(folder,wait=False) as free:assert free is True
        with entry_lock(folder) as again:assert again is True
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
        return {'held_by_another_process_refused':True,'free_after_it_ends':True,'failed_keep_skipped':True,'stopped_keep_left_nothing':True}
    check('cache_entry_locked_across_renders',entry_lock_across_renders)
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
        assert listed(clean(work2,[c/'r2']))==[('render','song_c/r1/render'),('round','song_c/r1')]
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
        again=clean(e,[e/'final'])  # what the first left is found again, and still not removed
        assert {Path(x['path']).as_posix() for x in again['listed']}=={'r_old','r_changed'} and not any(x['whole'] for x in again['listed']),again
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
        assert not parts['r_named']['whole'] and {'r_named/mine/files.json','r_named/project.json'}<=set(parts['r_named']['kept_inside']),parts
        # A folder or a --keep given as a link is refused.
        assert not linked or (link(base/'root_link',proj) and rejects(lambda:clean(base/'root_link',[base/'root_link'/'final'])))
        assert not linked or (link(proj/'final_link',final) and rejects(lambda:clean(proj,[proj/'final_link'])))
        # A cache entry a render holds stays.
        d=work2/'song_d';entry(d/'cache',H('4'));entry(d/'cache',H('5'));made(d/'final','Song D',[H('5')])
        code=('import sys,time;sys.path.insert(0,sys.argv[1]);from musiclib.render import entry_lock\n'
              'with entry_lock(sys.argv[2]) as held:\n    print(held,flush=True);time.sleep(5)')
        holder=subprocess.Popen([sys.executable,'-c',code,str(Path(__file__).resolve().parent),str(d/'cache'/H('4'))],stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='True'
            looked=clean(d,[d/'final'])  # the dry run looks at the entry's lock too, creating nothing
            held=clean(d,[d/'final'],remove=True)
        finally:
            holder.wait(timeout=60);holder.stdout.close()
        assert [x['error'] for x in held['not_removed']]==['a render is using it'] and (d/'cache'/H('4')).is_dir(),held
        # The dry run says so too: it listed the entry as one that goes (found by GPT Pro's third review of 0.4.0).
        assert [x['error'] for x in looked['not_removed']]==['a render is using it'] and not any(H('4') in x['path'] for x in looked['listed']),looked
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
        def meanwhile(folder,skip,holders=()):
            if folder==changed and not fired:  # once, after the folder's files went and before its records do
                fired.append(1);(changed/'late.json').write_text('{}',encoding='utf-8');record.register(changed,[changed/'late.json'])
            return real_empty(folder,skip,holders)
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
        return {'records_by_name_alone_kept':True,'link_not_followed':linked,'linked_record_kept':symlinked,'other_piece_left_alone':True,'renamed_piece_cleaned':True,'unrecorded_files_kept':True,'held_entry_kept':True,'emptied_review_removed':True,'files_named_as_records_kept':True,
                'deep_folder_kept_its_piece':True,'audition_cache_file_named':True,'record_changed_meanwhile_kept':True,'holding_folder_held':True,
                'junction_not_walked':junction,'open_entry_named':True}
    check('clean_removes_only_what_the_tools_made',clean_only_what_the_tools_made)
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
        before=fs.recorded(resumed);(resumed/'analysis.json').write_text('{"a": 1, "mine": true}',encoding='utf-8');since=time.time_ns()+1
        fs.register_tree(resumed,since_ns=since,keep=before)
        assert not fs.unchanged(resumed/'analysis.json',fs.recorded(resumed)['analysis.json'])
        # A record made with a relative folder, as a round or a review given a relative --output makes it, lists the
        # files: each was taken from the folder a second time and nothing was recorded.  (Found by the stress test.)
        here=os.getcwd();os.chdir(d)
        try:
            Path('rel_round').mkdir();Path('rel_round/round.json').write_text('{}',encoding='utf-8');(Path('rel_round')/'review').mkdir()
            Path('rel_round/review/notes.csv').write_text('x',encoding='utf-8')
            fs.register(Path('rel_round'),[Path('rel_round')/'round.json']);fs.register_tree(Path('rel_round')/'review')
        finally:os.chdir(here)
        assert list(fs.recorded(d/'rel_round'))==['round.json'] and list(fs.recorded(d/'rel_round'/'review'))==['notes.csv']
        # A file written whole keeps the mode a new file has under the user's umask (mkstemp makes them 0600).
        import stat
        made_whole=fs.stage_name(d/'mode.wav','.wav')
        assert fs.FILE_MODE is None or stat.S_IMODE(os.stat(made_whole).st_mode)==fs.FILE_MODE,oct(os.stat(made_whole).st_mode)
        return {'dangling_link_refused':dangling,'hard_link_kept':True,'unrecorded_set_aside':True,'foreign_record_set_aside':True,'failed_output_left_nothing':True,
                'foreign_record_above_an_output_untouched':True,'changed_file_not_adopted_on_resume':True,'staged_mode':oct(fs.FILE_MODE) if fs.FILE_MODE is not None else 'not POSIX'}
    check('files_never_overwrite_or_write_through',files_never_overwrite_or_write_through)
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
        return {'writers':sorted(writers),'refused_rename_retried':os.name=='nt'}
    check('writers_leave_whole_files_when_a_write_fails',writers_leave_whole_files_when_a_write_fails)
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
        return {'program_stopped':True,'returncode':started[0].returncode,'stopped_with_its_render':True}
    check('run_stops_its_program_when_stopped',run_stops_its_program_when_stopped)
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
        # The configuration's path is checked before the install and again when it is written: files.json is refused,
        # and a path the install put a bank at meanwhile keeps the bank (it was written over with the configuration;
        # found by GPT Pro's third review of 0.4.0).
        from musiclib import files as fs
        assert rejects(lambda:fs.check_config_path(rt/'files.json','--config'))
        bank=rt/'demo.sf2';fs.check_config_path(bank,'--config');bank.write_bytes(b'RIFF a bank')
        assert rejects(lambda:fs.save_config(bank,{'a':1},'--config')) and bank.read_bytes()==b'RIFF a bank'
        fs.save_config(rt/'config.json',{'a':1},'--config');assert json.loads((rt/'config.json').read_text(encoding='utf-8'))=={'a':1}
        return {'set_aside':len(aside()),'own_replaced':True,'config_never_over_an_installed_file':True}
    check('bootstrap_receipts_set_aside_what_it_did_not_write',bootstrap_receipts_set_aside_what_it_did_not_write)
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
        holder=subprocess.Popen([sys.executable,'-c',code,str(Path(__file__).resolve().parent),str(busy),str(rnd)],stdout=subprocess.PIPE,text=True)
        try:
            assert holder.stdout.readline().strip()=='True'
            assert fs.take(busy)[0]=='busy' and rejects(lambda:fs.working(busy).__enter__())
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
    check('clean_and_runs_never_share_a_folder',clean_and_runs_never_share_a_folder)
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
        return {'link_refused':made}
    check('render_refuses_a_linked_output',render_refuses_a_linked_output)
    def bounded_reads_of_records_and_wav_headers():
        # A WAV format chunk larger than any format needs, and a stopped render's report.json larger than a record may
        # be, are refused before they are read whole.  (Found by the second review of 0.4.0.)
        from musiclib import files as fs
        from musiclib.render import stopped
        wav=work/'huge_fmt.wav';wav.write_bytes(b'RIFF'+struct.pack('<I',4020)+b'WAVE'+b'fmt '+struct.pack('<I',4000)+bytes(4000)+b'data'+struct.pack('<I',0))
        try:
            audio.read_wav(wav);raise AssertionError('a 4000-byte format chunk was read')
        except ValueError as e:assert 'format chunk' in str(e),e
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
    check('bounded_reads_of_records_and_wav_headers',bounded_reads_of_records_and_wav_headers)
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
    check('slur_legato_plays_one_line',slur_legato_plays_one_line)
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
    check('synth_modulation_in_beats_follows_the_tempo',synth_modulation_in_beats_follows_the_tempo)
    def json_output_survives_an_ascii_console():
        # --json output escapes what the console's code page lacks as JSON does (\u00e9, a surrogate pair beyond the
        # BMP), so it stays JSON; the console's own escape (\xe9) is not JSON.  (Found by the second review of 0.4.0.)
        import subprocess,sys
        here=Path(__file__).resolve().parent
        p=example();p['title']='Café 𝄞 喆';save_json(work/'console_json.json',p)
        run=subprocess.run([sys.executable,str(here/'studio.py'),'review',str(work/'console_json.json'),'--output',str(work/'console_json_review'),'--json'],
                           capture_output=True,timeout=300,env={**os.environ,'PYTHONIOENCODING':'ascii'},creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        assert run.returncode==0,(run.returncode,run.stderr[-500:])
        assert json.loads(run.stdout.decode('ascii'))['title']=='Café 𝄞 喆'
        return {'parsed':True}
    check('json_output_survives_an_ascii_console',json_output_survives_an_ascii_console)
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
    check('delete_sources_takes_only_the_installers_files',delete_sources_takes_only_the_installers_files)
    def flac_source_must_be_flac():
        # A file named .flac that is not FLAC (a playlist, another container) is refused before FFmpeg opens it.
        from soundbank import read_audio
        fake=work/'not_flac.flac';fake.write_bytes(b'#EXTM3U\nfile:///etc/passwd\n')
        try:read_audio(fake,ffmpeg='ffmpeg-is-not-started');raise AssertionError('a non-FLAC .flac was read')
        except ValueError as e:assert 'fLaC' in str(e),e
        return {'refused_before_ffmpeg':True}
    check('flac_source_must_be_flac',flac_source_must_be_flac)
    def notes_csv_escapes_formulas():
        # A cell a spreadsheet would run as a formula (=, +, -, @, tab, CR first) starts with an apostrophe (OWASP, CSV
        # Injection), so a project from someone else cannot put a formula into notes.csv.
        import csv
        from musiclib.review import review
        p=example();n=p['tracks'][0]['notes'][0];n['phrase']='=HYPERLINK("http://example.org")';n['articulation']='@SUM(1)'
        review(p,work/'csv_review')
        rows=list(csv.DictReader((work/'csv_review'/'notes.csv').open(encoding='utf-8',newline='')))
        row=next(r for r in rows if r['note_id']==n['id'])
        cells=[v for v in row.values() if 'HYPERLINK' in v or 'SUM(1)' in v]
        assert len(cells)==2 and all(v.startswith("'") for v in cells),row
        return {'escaped_cells':len(cells)}
    check('notes_csv_escapes_formulas',notes_csv_escapes_formulas)
    def shared_reports_name_folders_relatively():
        # A comparison is saved with the renders and the clip relative to its folder: no local folders or user name.
        from musiclib.compare import portable
        base=work/'portable';(base/'r1'/'render').mkdir(parents=True);(base/'r2'/'render').mkdir(parents=True)
        r=portable({'before':base/'r1'/'render','after':base/'r2'/'render','clip':{'file':base/'r2'/'clip.mp3'}},base/'r2'/'render')
        assert r['before']=='../../r1/render' and r['after']=='.' and r['clip']['file']=='../clip.mp3',r
        return {'relative':True}
    check('shared_reports_name_folders_relatively',shared_reports_name_folders_relatively)
    def scripts_escape_what_their_output_cannot_show():
        # On Windows a script's output read through a pipe, as an agent reads it, is written in the ANSI code page
        # (Python documentation, sys.stdout), which lacks characters some folder names hold (喆 is not in code page 950):
        # every script that prints escapes them instead of stopping.  PYTHONIOENCODING=ascii makes any system's pipe
        # such a page.  (Found by setting the skill up in a folder named with 喆.)
        import subprocess,sys
        here=Path(__file__).resolve().parent
        printing=[s.name for s in sorted(here.glob('*.py')) for t in [s.read_text(encoding='utf-8')] if "__name__=='__main__'" in t.replace(' ','') and 'print(' in t]
        missing=[n for n in printing if 'escape_unprintable()' not in (here/n).read_text(encoding='utf-8')]
        assert len(printing)>=7 and not missing,(printing,missing)
        out=work/'console_喆'/'song.json';out.parent.mkdir()
        run=subprocess.run([sys.executable,str(here/'make_example.py'),'--output',str(out)],capture_output=True,timeout=120,
                           env={**os.environ,'PYTHONIOENCODING':'ascii'},creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        assert run.returncode==0 and b'console_\\u5586' in run.stdout and out.is_file(),(run.returncode,run.stdout[-300:],run.stderr[-500:])
        return {'printing_scripts':len(printing),'escaped':True}
    check('scripts_escape_what_their_output_cannot_show',scripts_escape_what_their_output_cannot_show)
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
    check('pedalboard_checked_against_its_record',pedalboard_checked_against_its_record)
    def automation_applies_per_sample_with_held_ends():
        # Automation in NumPy, sample by sample, linear in dB and in time between points: any number of points (an FFmpeg
        # expression failed past 95), the first point's level before it and the last one's after it.
        p=example();clock=Clock(p);frames=round((clock.end+clock.tail)*audio.RATE);x=np.ones((frames,2),dtype=np.float32)
        level=lambda y,beat:20*np.log10(float(y[min(frames-1,round(clock.seconds(beat)*audio.RATE)),0]))
        y=audio.automated(x,[[4,-12],[8,0]],clock)
        assert abs(level(y,0)+12)<1e-3 and abs(level(y,4)+12)<1e-3 and abs(level(y,8))<1e-3 and abs(level(y,15.9))<1e-3
        mid=(clock.seconds(4)+clock.seconds(8))/2;assert abs(20*np.log10(float(y[round(mid*audio.RATE),0]))+6)<.01
        many=[[i*.1,-6.0*(i%2)] for i in range(160)];y=audio.automated(x,many,clock)
        assert abs(level(y,.1)+6)<1e-3 and abs(level(y,.2))<1e-3 and abs(level(y,.15)+3)<.05
        assert audio.automated(x,[[0,0],[16,0]],clock) is None
        return {'points':len(many)}
    check('automation_applies_per_sample_with_held_ends',automation_applies_per_sample_with_held_ends)
    def swing_pairs_counted_from_each_bar_line():
        # Swing pairs are counted from each bar line (a drum machine delays the even steps of the beat: Linn 2013): in
        # 5/8 eighth swing every downbeat stays on time and the bar's fifth eighth is straight; in 3/4 quarter swing beat
        # 3 is straight; in 4/4 nothing changes.
        def part(meter,unit,ons):
            p=example();p['clock']={'bars':3,'meter':meter,'tempo':[[0,120]],'tail_seconds':1}
            p['sections']=[{'id':'a','start_bar':0,'bars':3}];p.pop('harmony',None);t=p['tracks'][0]
            t['notes']=[{'id':f'n{k}','on':on,'duration':.2,'pitch':60+k%5} for k,on in enumerate(ons)]
            t['performance']={'notes':{f'n{k}':{'velocity':80} for k in range(len(ons))},'swing':{'ratio':2/3,'unit':unit}}
            p['tracks']=[t];validate(p);c=Clock(p);return {n['id']:n['tick']/TPQ for n in performed(t,c)}
        five=part([5,8],.5,[b*2.5+k*.5 for b in range(3) for k in range(5)])
        assert all(abs(five[f'n{b*5}']-b*2.5)<1e-9 for b in range(3)),five
        assert all(abs(five[f'n{b*5+4}']-(b*2.5+2))<1e-9 and abs(five[f'n{b*5+1}']-(b*2.5+2/3))<2/TPQ for b in range(3)),five
        three=part([3,4],1,[b*3+k for b in range(3) for k in range(3)])
        assert all(abs(three[f'n{b*3}']-b*3)<1e-9 and abs(three[f'n{b*3+2}']-(b*3+2))<1e-9 and abs(three[f'n{b*3+1}']-(b*3+4/3))<2/TPQ for b in range(3)),three
        four=part([4,4],.5,[k*.5 for k in range(24)])
        assert all(abs(four[f'n{k}']-(k*.5 if k%2==0 else k*.5-.5+2/3))<2/TPQ for k in range(24)),four
        return {'meters':['5/8','3/4','4/4']}
    check('swing_pairs_counted_from_each_bar_line',swing_pairs_counted_from_each_bar_line)
    def excerpt_keeps_the_piece_at_its_edges():
        # An excerpt plays its passage as the piece does at both cuts (the cases the second review of 0.4.0 found): a
        # linear CC ramp takes its value at the cut, a note held over the cut but stopped before it as played is not
        # re-attacked, a note a float hair under the end is not in the passage, a half-tick note lands on the piece's
        # tick, and the piece's ritardando into a boundary at the passage's end is kept (clock.rubato.spans).
        p=example();p.pop('harmony',None);p['clock']={'bars':4,'meter':[4,4],'tempo':[[0,100]],'tail_seconds':1}
        p['sections']=[{'id':'a','start_bar':0,'bars':2},{'id':'b','start_bar':2,'bars':2}]
        t=p['tracks'][2];t['performance']['cc']=[[0,11,20],[16,11,120]]  # the additive lead: linear CC by default
        p['tracks']=[t];validate(p);q=extract(p,2,1)
        assert q['tracks'][0]['performance']['cc'][0]==[0,11,45] and q['tracks'][0]['performance']['cc'][-1]==[4.0,11,70],q['tracks'][0]['performance']['cc']
        p=example();p.pop('harmony',None);t=p['tracks'][0]
        t['notes']=[{'id':'push','on':3.5,'duration':1.0,'pitch':60},{'id':'held','on':3.5,'duration':1.0,'pitch':64},{'id':'hair','on':float(np.nextafter(8.0,0.0)),'duration':.5,'pitch':67}]
        t['performance']['notes']={'push':{'velocity':80,'gate':.4},'held':{'velocity':80},'hair':{'velocity':80}};t['performance']['cc']=[]
        p['tracks']=[t];validate(p);q=extract(p,2,1)
        assert [n['id'] for n in q['tracks'][0]['notes']]==['held'],q['tracks'][0]['notes']
        q=extract(p,1,2);assert 'hair' not in [n['id'] for n in q['tracks'][0]['notes']]
        p=example();p.pop('harmony',None);p['clock']['bars']=8;p['sections']=[{'id':'a','start_bar':0,'bars':8}];t=p['tracks'][0]
        t['notes']=[{'id':'half','on':(7102.5)/TPQ,'duration':1/TPQ,'pitch':60},{'id':'next','on':7104/TPQ,'duration':.5,'pitch':60}]
        t['performance']={'notes':{'half':{'velocity':80},'next':{'velocity':80}}};p['tracks']=[t];validate(p)
        whole={n['id']:n['tick'] for n in performed(t,Clock(p))};q=extract(p,2,6);part={n['id']:n['tick'] for n in performed(q['tracks'][0],Clock(q))}
        cut=round(4*TPQ);assert all(part[k]==whole[k]-cut for k in part) and len(part)==2,(whole,part)
        p=example();p.pop('harmony',None);p['clock']={'bars':8,'meter':[4,4],'tempo':[[0,100]],'tail_seconds':1,'rubato':{'phrase_beats':8,'phrase_ratio':.7}}
        p['sections']=[{'id':'a','start_bar':0,'bars':4},{'id':'b','start_bar':4,'bars':4}];t=p['tracks'][0]
        t['notes']=[{'id':f'n{i}','on':i,'duration':1,'pitch':60+i%7} for i in range(32)];t['performance']={'notes':{f'n{i}':{'velocity':80} for i in range(32)}}
        p['tracks']=[t];validate(p);a=Clock(p);q=extract(p,3,2);b=Clock(q)
        assert q['clock']['rubato']['spans'] and abs((a.seconds(16)-a.seconds(8))-b.seconds(8))<1e-6,(q['clock'],a.seconds(16)-a.seconds(8),b.seconds(8))
        bad=copy.deepcopy(q);bad['clock']['rubato']['spans']=[[4,2,.8]];rejects(lambda:validate(bad))
        # A note the piece plays across a cut plays the part of it inside the passage, as played: a long note with a
        # short gate re-attacked at the cut ends where it ended (not where its gate would end the cut note), a note
        # written before the cut but played after it starts where it started, and one held past the end sounds to the
        # end.  A legato overlap, written to end before the cut, is not re-attacked: it belongs to the next note's
        # attack.  (Cases two reviews of 0.4.0 found.)
        p=example();p.pop('harmony',None);p['clock']={'bars':3,'meter':[4,4],'tempo':[[0,120],[6,90]],'tail_seconds':1}
        p['sections']=[{'id':'a','start_bar':0,'bars':3}];t=copy.deepcopy(p['tracks'][0])
        t['notes']=[{'id':'long','on':0,'duration':8,'pitch':60},{'id':'legato','on':2,'duration':1.5,'pitch':64},
                    {'id':'late','on':3.9,'duration':.4,'pitch':67},{'id':'over','on':6.5,'duration':3,'pitch':72}]
        t['performance']={'notes':{'long':{'velocity':80,'gate':.75},'legato':{'velocity':80,'gate':1.6},'late':{'velocity':80,'timing_ms':100},
                                   'over':{'velocity':80,'gate':.9}},'cc':[],'offset_ms':-15}
        p['tracks']=[t];validate(p);a=Clock(p);q=extract(p,2,1);b=Clock(q);cut,stop=round(4*TPQ),round(8*TPQ)
        piece={n['id']:(max(n['tick'],cut)-cut,min(n['end_tick'],stop)-cut) for n in performed(t,a)}
        part={n['id']:(n['tick'],n['end_tick']) for n in performed(q['tracks'][0],b)}
        assert part=={k:v for k,v in piece.items() if k!='legato'} and sorted(part)==['late','long','over'],(piece,part)
        # A note of the next bar that the part's offset plays early is the next passage's, so a part that plays a few
        # milliseconds ahead (offset_ms for slow attacks) leaves every passage valid; so does a legato line over a bar
        # line on the additive lead, and a laid-back part whose held note a re-attack cannot reach.  (Found by a
        # review of 0.4.0: each stopped excerpt and audition.)
        for offset in (-5,-15,-150,-300,250):
            p=example();bass=next(t for t in p['tracks'] if t['id']=='bass');bass['performance']['offset_ms']=offset
            next(n for n in bass['notes'] if n['id']=='bass_n0')['duration']=3.885;validate(p)
            for first,count in ((1,1),(1,2),(2,1),(2,2),(1,3),(3,1)):extract(p,first,count)
        p=example();lead=next(t for t in p['tracks'] if t['engine']=='additive');next(n for n in lead['notes'] if n['id']=='lead_n2')['duration']=2.0
        validate(p);extract(p,2,2)
        # A part held to one written line (the additive lead) whose note crosses the cut, its gate carrying it into the
        # next note: the re-attack ends where the next note begins, at gate 1.6, rather than overlapping it as written,
        # which validate refuses.  (Found by the stress test of 0.4.0: 6 % of random projects with an additive lead.)
        p=example();p.pop('harmony',None);lead=next(t for t in p['tracks'] if t['engine']=='additive')
        lead['notes']=[{'id':'over','on':3.5,'duration':.75,'pitch':72},{'id':'next','on':4.25,'duration':1.0,'pitch':74}]
        lead['performance']={'notes':{'over':{'velocity':90,'gate':1.5},'next':{'velocity':90}},'cc':[]};validate(p)
        q=extract(p,2,1);ql=next(t for t in q['tracks'] if t['engine']=='additive');o={n['id']:n for n in ql['notes']}
        assert o['over']['on']==0 and abs(o['over']['duration']-.25)<1e-9 and o['next']['on']==.25,o
        assert ql['performance']['notes']['over']['gate']==1.6,ql['performance']['notes']
        # A note written just before the cut that its timing plays after it, where the piece struck a note of its key
        # on the cut first: it is written where it plays, not onto the cut (two strikes of one key there as written,
        # which validate refused); and a short note of the passage played wholly before it sounds at its start.
        # (Found by the stress test of 0.4.0.)
        p=example();p.pop('harmony',None);p['clock']['tempo']=[[0,120]];t=p['tracks'][0];bpb=Clock(p).beats_per_bar
        t['notes']=[{'id':'late','on':bpb-.05,'duration':.8,'pitch':67},{'id':'cut','on':float(bpb),'duration':1.0,'pitch':67},
                    {'id':'blip','on':bpb+2.02,'duration':.05,'pitch':72},{'id':'bar','on':bpb+3.0,'duration':.5,'pitch':74}]
        t['performance']={'notes':{'late':{'velocity':80,'timing_ms':60},'cut':{'velocity':80},'blip':{'velocity':80},'bar':{'velocity':80}},'cc':[]}
        validate(p);q=extract(p,2,1);o={n['id']:n for n in q['tracks'][0]['notes']}
        assert o['cut']['on']==0 and 0<o['late']['on']<.1 and abs(q['tracks'][0]['performance']['notes']['late']['timing_ms'])<1,o
        t['notes'][2]['on']=bpb+.02;t['performance']['notes']['blip']['timing_ms']=-80;validate(p)
        q=extract(p,2,1);played={x['id']:x for x in performed(q['tracks'][0],Clock(q),True)}
        assert 'blip' in played and played['blip']['tick']==0,played
        # An older free-form harmony object, which schema.md still accepts, stays as it is (it stopped extract).
        p=example();p['harmony']={'changes':'C major then G major'};validate(p)
        assert extract(p,2,1)['harmony']=={'changes':'C major then G major'}
        return {'cases':16}
    check('excerpt_keeps_the_piece_at_its_edges',excerpt_keeps_the_piece_at_its_edges)
    def tick_rounding_is_stable():
        # A position within float error of a half tick takes the even tick, from either side, as round() does at an
        # exact half: one position computed along two paths lands on one tick.
        from musiclib.model import tick_of
        for v,want in ((7102.5,7102),(7103.5,7104),(7102.5+1e-9,7102),(7102.5-1e-9,7102),(1342.5000000000005,1342),(10.4,10),(10.6,11)):
            assert tick_of(v/TPQ)==want,(v,tick_of(v/TPQ))
        return {'values':7}
    check('tick_rounding_is_stable',tick_rounding_is_stable)
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
    check('soundfont_tables_must_hold_together',soundfont_tables_must_hold_together)
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
    check('parts_wait_for_memory',parts_wait_for_memory)
    def selfcheck_work_must_be_new_or_empty():
        import subprocess,sys
        busy=work/'busy_work';busy.mkdir();(busy/'roundtrip.mid').write_bytes(b'mine')
        r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--work',str(busy)],capture_output=True,text=True,timeout=120)
        assert r.returncode==2 and 'not empty' in r.stderr and (busy/'roundtrip.mid').read_bytes()==b'mine',(r.returncode,r.stderr)
        return {'refused':True}
    check('selfcheck_work_must_be_new_or_empty',selfcheck_work_must_be_new_or_empty)
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
        lock=json.loads((Path(__file__).resolve().parents[1]/'references'/'soundbank-lock.json').read_text(encoding='utf-8'))
        assert all(len(b.get('samples_sha256',''))==64 and b['samples']>0 for b in lock['builds'] if b.get('kind')!='split')
        return {'refused':3}
    check('source_listing_must_name_the_pinned_samples',source_listing_must_name_the_pinned_samples)
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
    check('pedalboard_wheel_fetched_by_its_lock',pedalboard_wheel_fetched_by_its_lock)
    def render_folders_are_read_without_links():
        # analyze and compare read a render folder's own files only: one holding a link (here its stems folder, a
        # junction on Windows) is refused before any audio is read; and no WAV longer than a render is read at all.
        import subprocess
        from musiclib.compare import load
        from musiclib.analysis import analyze
        r=work/'linked_render';(r/'stems').mkdir(parents=True);outside=work/'outside_stems';outside.mkdir()
        save_json(r/'project.json',example());save_json(r/'report.json',{});save_json(r/'stem_receipts.json',[])
        load(r)  # a folder of its own files is read
        shutil.rmtree(r/'stems')
        made=subprocess.run(['cmd','/c','mklink','/J',str(r/'stems'),str(outside)],capture_output=True).returncode==0 if os.name=='nt' else (os.symlink(outside,r/'stems',target_is_directory=True) or True)
        assert made
        for read in (lambda:load(r),lambda:analyze(r)):
            try:read();raise AssertionError('a render folder holding a link was read')
            except ValueError as e:assert 'links' in str(e),e
        long=work/'long.wav';audio.write_wav(long,np.zeros((3*audio.RATE,2),dtype=np.float32));limit=audio.MAX_WAV_SECONDS
        try:
            audio.MAX_WAV_SECONDS=2;rejects(lambda:audio.read_wav(long))
        finally:audio.MAX_WAV_SECONDS=limit
        audio.read_wav(long)
        return {'refused':2}
    check('render_folders_are_read_without_links',render_folders_are_read_without_links)
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
    check('a_part_larger_than_the_machine_is_refused',a_part_larger_than_the_machine_is_refused)
    if config:
        from musiclib.render import render
        p=example();save_json(work/'example.json',p);cache=work/'cache'
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
            # A draft is the same audio without what only delivery needs.
            draft=render(work/'example.json',work/'render_draft',config,cache,draft=True)
            assert draft['status']=='DRAFT_PASS' and draft['draft'] and draft['master']['sha256']==first['master']['sha256'],draft['status']
            assert not (work/'render_draft'/'master.flac').exists() and (work/'render_first'/'master.flac').is_file() and draft['left_out'][0]=='master.flac'
            return {'master_sha256':first['master']['sha256'],'cache_hits':repeat['cache_hits'],'stems_reused':repeat['stems_reused'],'parallel_jobs':parallel['jobs'],'draft_same_master':True,'checks':repeat['checks']}
        check('actual_render_repeat_is_sample_identical',integration)
        def render_folder_is_its_own_run():
            # A finished render leaves no lock file.  A resume refuses a folder holding a file the earlier render did not
            # write or one changed since (the user's own MIDI under its name), and one another run holds, leaving it as it
            # was; parts rendered at once report the part whose error the render stops on, with that error.  (Found by
            # the second review of 0.4.0.)
            import subprocess,sys,threading
            from musiclib import files as fs
            import musiclib.render as rd
            first=work/'render_first';assert not fs.occupied(first/fs.WORK_LOCK)
            again=work/'render_resume_cases';shutil.copytree(first,again)  # each file keeps the time its record lists
            names=lambda:sorted(x.relative_to(again).as_posix() for x in again.rglob('*'))
            before=names();own=b'MThd'+bytes(10);(again/'composition.mid').write_bytes(own)
            assert rejects(lambda:render(work/'example.json',again,config,cache,resume=True))
            assert (again/'composition.mid').read_bytes()==own and names()==before
            (again/'composition.mid').unlink();shutil.copy2(first/'composition.mid',again/'composition.mid')
            code=('import sys,time;sys.path.insert(0,sys.argv[1]);from musiclib import files\n'
                  'with files.working(sys.argv[2]) as held:\n    print(held,flush=True);time.sleep(5)')
            holder=subprocess.Popen([sys.executable,'-c',code,str(Path(__file__).resolve().parent),str(again)],stdout=subprocess.PIPE,text=True)
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
            return {'no_lock_left':True,'changed_file_refused':True,'held_folder_refused':True,'failed_part':failed['part']}
        check('render_folder_is_its_own_run',render_folder_is_its_own_run)
        def local_edit():
            q=copy.deepcopy(p);q['tracks'][0]['notes'][0]['pitch']+=2;save_json(work/'edited.json',q)
            r=render(work/'edited.json',work/'render_edited',config,cache)
            assert r['cache_hits']==len(q['tracks'])-1
            before=json.loads((work/'render_first'/'stem_receipts.json').read_text(encoding='utf-8'));after=json.loads((work/'render_edited'/'stem_receipts.json').read_text(encoding='utf-8'))
            changed=[a['track'] for a,b in zip(before,after) if a['raw_sha256']!=b['raw_sha256']]
            assert changed==['piano']
            return {'raw_changed_tracks':changed,'cache_hits':r['cache_hits']}
        check('one_note_revision_regenerates_only_its_part',local_edit)
        def mix_edit():
            q=copy.deepcopy(p);q['tracks'][2]['mix']['level_dbfs']+=1;save_json(work/'mix_edit.json',q)
            r=render(work/'mix_edit.json',work/'render_mix_edit',config,cache)
            assert r['cache_hits']==len(q['tracks'])
            before=json.loads((work/'render_first'/'report.json').read_text(encoding='utf-8'));assert r['master']['sha256']!=before['master']['sha256']
            # Only the part whose mix changed is processed again; the others play their stems from the cache.
            processed=[x['track'] for x in json.loads((work/'render_mix_edit'/'stem_receipts.json').read_text(encoding='utf-8')) if not x['stem_reused']]
            assert processed==[q['tracks'][2]['id']],processed
            # A kept stem that no longer matches its hash is not used: the part is processed again, to the same file.
            # (A cache entry keeps its last stem, so the part whose mix was just edited is processed again too.)
            entry=cache/next(x['cache_key'] for x in json.loads((work/'render_first'/'stem_receipts.json').read_text(encoding='utf-8')) if x['track']==q['tracks'][0]['id'])
            data=bytearray((entry/'stem.wav').read_bytes());data[-8:]=bytes(8);(entry/'stem.wav').write_bytes(bytes(data))
            again=render(work/'example.json',work/'render_after_damage',config,cache)
            redone=[x['track'] for x in json.loads((work/'render_after_damage'/'stem_receipts.json').read_text(encoding='utf-8')) if not x['stem_reused']]
            assert redone==[q['tracks'][0]['id'],q['tracks'][2]['id']] and again['master']['sha256']==before['master']['sha256'],(redone,again['master']['sha256'])
            return {'cache_hits':r['cache_hits'],'master_changed':True,'processed_again':processed,'damaged_stem_processed_again':redone}
        check('mix_revision_reuses_all_synthesis',mix_edit)
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
        check('kept_stems_follow_what_they_read',kept_stem_dependencies)
        def bad_hash():
            cfg=json.loads(Path(config).read_text(encoding='utf-8'))
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            cfg['soundfont']['sha256']='0'*64;save_json(work/'bad_config.json',cfg);rejects(lambda:audio.load_config(work/'bad_config.json'))
            return True
        check('dependency_hash_mismatch_stops_before_render',bad_hash)
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
        check('bank_lsb_selects_bank_on_default_soundfont',bank_select)
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
        check('named_soundfont_selected_per_track',named_soundfont)
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
        check('named_bank_verified_at_first_use',named_bank_first_use)
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
        check('pitch_bend_moves_soundfont_pitch',bend_render)
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
        check('legato_slurs_and_width_render',width_and_legato_render)
        def bus_render():
            q=copy.deepcopy(p);q['mix']['chain']='bus';save_json(work/'bus.json',q)
            r=render(work/'bus.json',work/'render_bus',config,cache)
            assert r['chain']=='bus' and r['cache_hits']==len(q['tracks']) and all(r['checks'].values()),r['checks']
            assert r['checks']['mp3_loudness_matches_master'] and abs(r['master']['integrated_lufs']-q['mix']['target_lufs'])<=.3
            out=work/'render_bus';assert all((out/'returns'/f'{s}_ir.wav').is_file() for s in ('room','plate','hall'))
            change=json.loads((out/'bus_level_change_db.json').read_text(encoding='utf-8'))
            assert set(change)==set(r['buses']['assignment'].values()) and all(abs(v)<6 for v in change.values()),change
            # Each space a part sends to and the delay come back as files, and with the buses they add up to the premix.
            spaces=sorted(set(r['buses']['spaces'].values()));wanted=[f'{s}_return.wav' for s in spaces]+['delay_return.wav']
            assert sorted(r['buses']['returns'])==sorted(wanted) and all((out/'returns'/n).is_file() for n in wanted),r['buses']['returns']
            assert r['checks']['buses_and_returns_add_up_to_premix'] and r['buses']['sum_minus_premix_peak_dbfs']<-100,r['buses']
            # A draft of the bus mix: the same premix, buses, returns and master, without the MP3 check and master.flac.
            d=render(work/'bus.json',work/'render_bus_draft',config,cache,draft=True);od=work/'render_bus_draft'
            assert d['status']=='DRAFT_PASS' and d['mp3'] is None and 'mp3_loudness_matches_master' not in d['checks'] and not (od/'master.flac').exists()
            for f in ['premix.wav','master.wav']+[f'returns/{x.name}' for x in sorted((out/'returns').glob('*.wav'))]:
                assert file_hash(od/f)==file_hash(out/f),f
            # With too little free memory for the mix's checks beside the master they run after it: the same render.
            import musiclib.render as render_module
            free=render_module.free_memory;render_module.free_memory=lambda:0
            try:s=render(work/'bus.json',work/'render_bus_sequential',config,cache)
            finally:render_module.free_memory=free
            assert s['master']['sha256']==r['master']['sha256'] and s['buses']==r['buses'],(s['buses'],r['buses'])
            # The same with tape wobble and a mono low end on the mix: they act on master_input.wav, and the delivered
            # buses and returns, read back once the render is done, still add up to the delivered premix.wav.
            t=copy.deepcopy(q);t['mix'].update(mono_below_hz=150,wow_flutter={'wow_cents':8,'wow_hz':.5,'flutter_cents':2,'flutter_hz':8})
            save_json(work/'bus_tape.json',t);rt=render(work/'bus_tape.json',work/'render_bus_tape',config,cache);ot=work/'render_bus_tape'
            parts=[np.asarray(audio.read_wav(f)[0],dtype=np.float64) for f in sorted((ot/'returns').glob('bus_*.wav'))+sorted((ot/'returns').glob('*_return.wav'))]
            pm=np.asarray(audio.read_wav(ot/'premix.wav')[0],dtype=np.float64);mi=np.asarray(audio.read_wav(ot/'master_input.wav')[0],dtype=np.float64)
            from musiclib.mixbus import adds_up
            ok,worst,_=adds_up(sum(parts),sum(np.abs(x) for x in parts),pm,480)
            assert rt['checks']['buses_and_returns_add_up_to_premix'] and ok and float(np.max(np.abs(mi-pm)))>1e-3,(worst,rt['checks'])
            return {'buses':r['buses']['assignment'],'returns':r['buses']['returns'],'sum_minus_premix_peak_dbfs':r['buses']['sum_minus_premix_peak_dbfs'],'tape_premix_rebuilt_within':worst,'level_change_db':change,'master_lufs':r['master']['integrated_lufs'],'true_peak_dbtp':r['master']['true_peak_dbtp']}
        check('bus_chain_render_and_delivery_checks',bus_render)
        def chorus_pass_logs():
            # A part with a chorus logs its later FFmpeg pass as ".pass1"; a part named like that pass ("<id>_1")
            # keeps its own log and receipt (a "_1" suffix once shared them, and parallel writes could collide).
            q=copy.deepcopy(p);first=q['tracks'][0];first['mix']['effects']=[{'type':'chorus','depth':.5}]
            twin=copy.deepcopy(first);twin['id']=first['id']+'_1';twin['mix'].pop('effects');q['tracks'].append(twin)
            save_json(work/'chorus_logs.json',q);r=render(work/'chorus_logs.json',work/'render_chorus_logs',config,cache)
            names={f.name for f in (work/'render_chorus_logs'/'logs').glob('process_*.process.json')}
            want={f'process_{first["id"]}.process.json',f'process_{first["id"]}.pass1.process.json',f'process_{twin["id"]}.process.json'}
            assert want<=names and all(r['checks'].values()),(sorted(want-names),r['checks'])
            assert not list((work/'render_chorus_logs'/'stems').glob('.*.wav')),'a pass file was left behind'
            return sorted(want)
        check('a_chorus_pass_never_shares_another_parts_log',chorus_pass_logs)
        def analysis():
            from musiclib.analysis import analyze
            a=analyze(work/'render_bus')
            assert [s['section'] for s in a['sections']]==[s['id'] for s in p['sections']] and a['lead_tracks']==['lead']
            assert all(np.isfinite(s['level_lufs_ungated']) and abs(sum(s['band_share_pct'].values())-100)<1.5 for s in a['sections'])
            assert any('lead_minus_accompaniment_db_median' in s and np.isfinite(s['lead_minus_accompaniment_level_db']) for s in a['lead_presence']),a['lead_presence']
            return {'sections':len(a['sections']),'lead_presence':a['lead_presence']}
        check('analysis_reports_sections_stems_and_lead',analysis)
        def compare_render():
            # The bus mix again with one piano note a semitone higher (only the piano is synthesized again, and every
            # file that changes changes from that note on) and with the lead 1 dB louder (its stem and its plate and
            # delay returns only move in level, and nothing is synthesized again).  A render against itself is identical.
            from musiclib.compare import compare,clip
            q=json.loads((work/'bus.json').read_text(encoding='utf-8'))
            note=copy.deepcopy(q);next(n for n in note['tracks'][0]['notes'] if n['id']=='piano_n7')['pitch']+=1;save_json(work/'bus_note.json',note)
            louder=copy.deepcopy(q);next(t for t in louder['tracks'] if t['id']=='lead')['mix']['level_dbfs']+=1;save_json(work/'bus_louder.json',louder)
            for name in ('note','louder'):render(work/f'bus_{name}.json',work/f'render_bus_{name}',config,cache)
            same=compare(work/'render_bus',work/'render_bus')
            assert not same['project_changes'] and all(e['identical'] for g in same['files'].values() for e in g.values())
            r=compare(work/'render_bus',work/'render_bus_note');f=r['files'];on=Clock(note).seconds(8.5)
            assert r['synthesis']['synthesized_again']==['piano'] and r['summary']['project']==['piano note piano_n7 at 3:1.5: pitch 64 -> 65'],r['summary']
            assert [k for k,e in f['stems'].items() if not e['identical']]==['piano'] and [k for k,e in f['returns'].items() if not e['identical']]==['hall'],r['summary']
            # Every file that changed changes from the note on, on any system: how far the piano's level moves with the
            # note depends on the FluidSynth (0.01 dB here, 0.11 dB on Ubuntu), and that move is marked apart.
            real=lambda e:[x for x in e['passages'] if not x.get('follows_part_levels')]
            moved=[e for g in ('stems','buses','returns','premix','master') for e in f[g].values() if not e['identical']]
            assert all(real(e) and abs(real(e)[0]['start_s']-on)<.15 and all(x['start_s']>on-.15 for x in real(e)) for e in moved),r['summary']
            heard=clip(audio.load_config(config),r,work/'note_ab.mp3')
            assert heard and (work/'note_ab.mp3').stat().st_size>10000 and abs(heard['start_s']-(real(f['master']['master'])[0]['start_s']-1.5))<.02,heard
            m=compare(work/'render_bus',work/'render_bus_louder');g=m['files']
            assert m['synthesis']['synthesized_again']==[] and g['stems']['lead']['level_db']==1 and not g['stems']['lead']['passages'],m['summary']
            assert all(g['returns'][s]['level_db']==1 and not g['returns'][s]['passages'] for s in ('plate','delay')),m['summary']
            assert not real(g['premix']['premix']) and not real(g['master']['master']),m['summary']
            # Clips with a silent side, decoded and heard back by level: a part added in a rest (old side silent), the
            # same removed (new side silent), and an old master that ends before the change (padded with silence). Each
            # clip is 8 s old, 0.8 s apart, 8 s new; the silent side stays silent and the other carries the tone.
            rate=audio.RATE;ff=audio.load_config(config)['ffmpeg']['path']
            def master_case(name,seconds,tone_at):
                d=work/'clip_case'/name;d.mkdir(parents=True,exist_ok=True);save_json(d/'project.json',p)
                save_json(d/'report.json',{'renderer_sha256':'one'});save_json(d/'stem_receipts.json',[])
                x=np.zeros((int(seconds*rate),2));tt=np.arange(4*rate)/rate;x[:4*rate]=(.2*np.sin(2*np.pi*220*tt))[:,None]
                if tone_at:x[int(tone_at*rate):int((tone_at+2)*rate)]=(.2*np.sin(2*np.pi*330*tt[:2*rate]))[:,None]
                audio.write_wav(d/'master.wav',x.astype(np.float32));return d
            rest,added,short,late=master_case('rest',20,None),master_case('added',20,11),master_case('short',10,None),master_case('late',20,12)
            def heard_back(mp3):
                wav=mp3.with_suffix('.wav');audio.run([ff,'-hide_banner','-nostdin','-y','-i',mp3,'-ar',str(rate),'-c:a','pcm_f32le',wav],work/'clip_case','decode')
                y=np.asarray(audio.read_wav(wav)[0],dtype=np.float64);rms=lambda a,b:float(np.sqrt(np.mean(y[int(a*rate):int(b*rate)]**2)))
                return len(y)/rate,rms(.5,7.5),rms(9.3,16.3)
            cases={}
            for name,(before,after),silent in (('added',(rest,added),'old'),('removed',(added,rest),'new'),('short_old',(short,late),'old')):
                made=clip(audio.load_config(config),compare(before,after),work/f'clip_{name}.mp3');length,old_rms,new_rms=heard_back(work/f'clip_{name}.mp3')
                quiet,loud=(old_rms,new_rms) if silent=='old' else (new_rms,old_rms)
                assert made and abs(length-16.8)<.15 and quiet<1e-4 and loud>.02,(name,made,length,old_rms,new_rms)
                assert (made['levels_lufs'][0] is None)==(silent=='old') and (made['levels_lufs'][1] is None)==(silent=='new'),(name,made)
                cases[name]={'old_rms':round(old_rms,4),'new_rms':round(new_rms,4),'seconds':round(length,2)}
            # Through the command line: when the clip cannot be made (its folder cannot be created, or the
            # configuration cannot be read), the report is still written and says why.
            import subprocess,sys
            blocker=work/'clip_case'/'a_file';blocker.write_text('x',encoding='utf-8')
            for why,extra in (('folder',['--clip',str(blocker/'x.mp3'),'--config',str(config)]),('config',['--clip',str(work/'cli_ab.mp3'),'--config',str(work/'no_such_config.json')])):
                report=work/f'cli_{why}.json'
                run=subprocess.run([sys.executable,str(Path(__file__).with_name('studio.py')),'compare',str(rest),str(added),'--output',str(report),*extra],capture_output=True,text=True,encoding='utf-8',errors='replace')
                saved=json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {}
                assert run.returncode==0 and saved.get('clip',{}).get('error') and saved['files']['master']['master']['passages'],(why,run.stderr[-600:],saved.get('clip'))
            # --json prints the report as saved, its folders relative to it, not the one with local paths.  (Found by a
            # review of 0.4.0.)
            report=work/'cli_json.json'
            run=subprocess.run([sys.executable,str(Path(__file__).with_name('studio.py')),'compare',str(rest),str(added),'--output',str(report),'--json'],capture_output=True,text=True,encoding='utf-8',errors='replace')
            assert run.returncode==0 and json.loads(run.stdout)==json.loads(report.read_text(encoding='utf-8')),run.stderr[-600:]
            # compare judges a part's change as it is sent, through gains it models on FFmpeg's highpass and lowpass:
            # tones through the delay's and the hall's filters, FFmpeg against the model.  Then two cases through the
            # real mixer, two parts on the fx bus that share only a delay:
            # - a lead of a loud 18 kHz tone over a weak 1 kHz line that turns to 2.3 kHz for 0.1 s, the other part 6 dB
            #   louder: the delay's lowpass cuts 18 kHz 38 dB (an analog formula says 26), so the change counts in the
            #   return, and it stays a change there, though the lead's stem shows nothing;
            # - the lead 0.11 dB louder into FFmpeg's compressor, the other part 6 dB louder: the compressed lead differs
            #   a little everywhere, under the stem's 40 dB test, and the return only follows the levels.
            from musiclib import mixbus
            from musiclib.compare import _band
            cfgd=audio.load_config(config);mx=work/'mixer_case';mx.mkdir(exist_ok=True)
            freqs=[40,100,250,500,1000,2000,4000,8000,13000,16000,18000,21000];seg,gap=rate//2,rate//10
            tones=np.zeros(((seg+gap)*len(freqs),2))
            for k,fq in enumerate(freqs):tones[k*(seg+gap):k*(seg+gap)+seg]=(.5*np.sin(2*np.pi*fq*np.arange(seg)/rate))[:,None]
            audio.write_wav(mx/'tones.wav',tones.astype(np.float32))
            lvl=lambda y,k:10*np.log10(np.mean(np.asarray(y[k*(seg+gap)+seg//4:k*(seg+gap)+3*seg//4],dtype=np.float64)**2))
            filters={}
            for hp,lp in (mixbus.DELAY_BAND,(mixbus.SPACES['hall'][5],mixbus.RETURN_LOWPASS)):
                audio.ffmpeg(cfgd,['-i',mx/'tones.wav','-af',f'highpass=f={hp},lowpass=f={lp}','-c:a','pcm_f32le',mx/f'tones_{hp}.wav'],mx,f'tones_{hp}')
                y,z=audio.read_wav(mx/f'tones_{hp}.wav')[0],_band(tones,hp,lp)
                err=[abs(lvl(y,k)-lvl(z,k)) for k in range(len(freqs))];filters[f'{hp}-{lp}']=round(max(err),4)
                assert max(err)<.05,(hp,lp,[round(e,3) for e in err])
            pm=example();lead=next(t for t in pm['tracks'] if t['id']=='lead');other=copy.deepcopy(next(t for t in pm['tracks'] if t['id']=='bass'))
            other['id']='other';pm['tracks']=[lead,other];pm['mix']={'chain':'bus','dynamics':'wide','target_lufs':-18};pm['clock']['tempo']=[[0,120]]
            for tr in pm['tracks']:tr['mix'].update(bus='fx',reverb_db=None,delay_db=-6)
            cm=Clock(pm);n=round((cm.end+cm.tail)*rate);tt=np.arange(n)/rate
            st=lambda x:np.stack([x,.9*x],axis=1);sine=lambda f,a:a*np.sin(2*np.pi*f*tt)
            def mixed(name,parts):
                out=mx/name
                for d in ('stems','returns','logs'):(out/d).mkdir(parents=True,exist_ok=True)
                for k,x in parts.items():audio.write_wav(out/'stems'/f'{k}.wav',np.asarray(x,dtype=np.float32))
                mixbus.mix(pm,cm,cfgd,out,n);mixbus.master(pm,cfgd,out)
                save_json(out/'project.json',pm);save_json(out/'report.json',{'renderer_sha256':'one'})
                save_json(out/'stem_receipts.json',[{'track':k,'cache_key':k,'raw_sha256':k} for k in parts]);return out
            s0,s1=int(6*rate),int(6.1*rate);mid0=sine(1000,.00008);mid1=mid0.copy();mid1[s0:s1]=sine(2300,.00008)[s0:s1];o0=st(sine(700,.00004))
            hf=compare(mixed('high_before',{'lead':st(sine(18000,.4)+mid0),'other':o0}),mixed('high_after',{'lead':st(sine(18000,.4)+mid1),'other':2*o0}))['files']
            assert not hf['stems']['lead']['passages'] and any(x['start_s']<6.4 and x['end_s']>6.6 for x in real(hf['returns']['delay'])),(hf['stems']['lead'],hf['returns']['delay'])
            def compressed(x,name):
                audio.write_wav(mx/f'{name}_in.wav',x.astype(np.float32))
                audio.ffmpeg(cfgd,['-i',mx/f'{name}_in.wav','-af','acompressor=threshold=0.08:ratio=3:attack=6:release=120:makeup=1','-c:a','pcm_f32le',mx/f'{name}.wav'],mx,name)
                return audio.read_wav(mx/f'{name}.wav')[0]
            voice=st((.15*np.sin(2*np.pi*440*tt)+.05*np.sin(2*np.pi*1320*tt))*(1+.5*np.sin(2*np.pi*.3*tt)));o1=st(sine(700,.02))
            cl=compare(mixed('comp_before',{'lead':compressed(voice,'comp0'),'other':o1}),mixed('comp_after',{'lead':compressed(voice*10**(.11/20),'comp1'),'other':2*o1}))['files']
            assert not cl['stems']['lead']['passages'] and cl['returns']['delay']['passages'] and not real(cl['returns']['delay']),(cl['stems']['lead'],cl['returns']['delay'])
            return {'note':r['summary']['changed'],'louder':m['summary']['changed'],'clip':heard,'silent_side_clips':cases,
                    'filter_model_worst_db':filters,'hidden_high_change':real(hf['returns']['delay']),'compressed_level_only':cl['returns']['delay']['passages']}
        check('compare_reports_what_changed_and_where',compare_render)
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
        check('loop_render_folds_the_tail_into_wav_and_ogg',loop_render)
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
            return {'gain_db':lp['layers']['gain_db'],'sum_minus_loop_db':lp['layers']['sum_minus_loop_db'],'correlation_with_loop':round(corr,4)}
        check('loop_layers_render_and_add_up_to_the_mix',layer_render)
        def wide_render():
            # Four soft bars and four loud ones.  The wide master is one gain and an EQ, so it keeps the mix's contrast
            # between the sections, and it holds the gain down rather than limit when the target would push the true
            # peak past -1.2 dBTP.  The soft bars sit over 20 LU under the loud ones, so the loudness range, whose
            # relative gate leaves them out, cannot show that contrast; the section levels do.
            q=copy.deepcopy(p);q['mix'].update(chain='bus');q['clock']={'bars':8,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':2}
            q['sections']=[{'id':'soft','start_bar':0,'bars':4,'intent':'pp'},{'id':'loud','start_bar':4,'bars':4,'intent':'ff'}]
            t=copy.deepcopy(p['tracks'][0]);t.update(id='dyn',program=0,bank=0,role='harmony',range=[48,72]);t['mix']={**t['mix'],'reverb_db':None,'delay_db':None}
            t['notes']=[{'id':f'dyn_{b}_{k}','on':b*4+k,'duration':1,'pitch':x} for b in range(8) for k,x in enumerate((48,55,60,64))]
            t['performance']={'notes':{n['id']:{'velocity':24 if n['on']<16 else 124,'gate':1.0} for n in t['notes']}}
            q['tracks']=[t];out={}
            for name,mode,target in (('glue','glue',-18),('wide','wide',-18),('wide_hot','wide',-10)):
                q['mix'].update(dynamics=mode,target_lufs=target);save_json(work/f'dyn_{name}.json',q)
                r=render(work/f'dyn_{name}.json',work/f'render_dyn_{name}',config,cache);assert all(r['checks'].values()),r['checks']
                out[name]=r
            def contrast(r):
                s={x['id']:x['rms_dbfs'] for x in r['sections']};return s['loud']-s['soft']
            premix,_=audio.read_wav(work/'render_dyn_wide'/'premix.wav');sec={x['id']:x for x in out['wide']['sections']}
            level={k:20*np.log10(audio.rms(premix[int(v['start_seconds']*audio.RATE):int(v['end_seconds']*audio.RATE)])) for k,v in sec.items()}
            mixed=level['loud']-level['soft'];glue,wide=contrast(out['glue']),contrast(out['wide'])
            m,hot=out['wide']['mastering'],out['wide_hot']
            graph=(work/'render_dyn_wide'/'mix.filtergraph.txt').read_text(encoding='utf-8')
            assert m['dynamics']=='wide' and 'acompressor' not in m['master_chain']+graph and 'asoftclip' not in graph,m
            assert abs(wide-mixed)<.3 and glue<wide and abs(m['lra_lu']-m['mixed']['lra_lu'])<.5,(mixed,wide,glue,m)
            held=hot['mastering']['peak_held_db']
            assert held>0 and hot['master']['true_peak_dbtp']<=-1 and abs(hot['master']['integrated_lufs']-(-10-held))<.5,hot['mastering']
            return {'contrast_mix_db':round(mixed,2),'contrast_wide_db':round(wide,2),'contrast_glue_db':round(glue,2),
                    'hot_peak_held_db':held,'hot_true_peak_dbtp':hot['master']['true_peak_dbtp']}
        check('wide_dynamics_master_keeps_the_mix_range',wide_render)
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
        check('layered_render_slurs_and_crossfades_dynamics',layered_render)
        def stage_and_range():
            from musiclib import stage
            q=copy.deepcopy(p);q['mix'].update(chain='bus',dynamics='wide',target_lufs=-18,range_lu=6)
            q['clock']={'bars':8,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':2}
            q['sections']=[{'id':'soft','start_bar':0,'bars':4,'intent':'p'},{'id':'loud','start_bar':4,'bars':4,'intent':'f'}]
            t=copy.deepcopy(p['tracks'][0]);t.update(id='deep',program=0,bank=0,role='harmony',range=[48,72])
            t['mix']={**t['mix'],'reverb_db':-12,'delay_db':None,'depth_m':8}
            t['notes']=[{'id':f'deep_{b}_{k}','on':b*4+k,'duration':1,'pitch':x} for b in range(8) for k,x in enumerate((48,55,60,64))]
            t['performance']={'notes':{n['id']:{'velocity':50 if n['on']<16 else 124,'gate':1.0} for n in t['notes']}}
            q['tracks']=[t];save_json(work/'stage.json',q);r=render(work/'stage.json',work/'render_stage',config,cache);m=r['mastering']
            rec=json.loads((work/'render_stage'/'stem_receipts.json').read_text(encoding='utf-8'))[0]
            send=-12+stage.send_boost_db(t['mix'].get('pan',0),8)
            assert f'volume={send:.6f}dB' in (work/'render_stage'/'mix.filtergraph.txt').read_text(encoding='utf-8') and rec['stage']['reflection_share_db']>-8,rec
            assert m['range']['lra_before_lu']>6.5 and m['range']['lra_after_lu']<=6.3 and r['master']['true_peak_dbtp']<=-1,m
            return {'stage':rec['stage'],'range':m['range'],'master_lra_lu':r['master']['lra_lu']}
        check('stage_depth_and_range_control_render',stage_and_range)
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
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            cfg.pop('surge',None);cfg.pop('pedalboard',None);save_json(work/'no_surge_config.json',cfg)
            render(work/'surge.json',work/'render_surge_fallback',work/'no_surge_config.json',work/'cache_surge')
            fell=json.loads((work/'render_surge_fallback'/'stem_receipts.json').read_text(encoding='utf-8'))[0]['surge']
            assert fell['rendered_with']=='built-in synth' and fell['fallback']==surge.presets()['presets']['juno_60_strings']['fallback'] and 'not installed' in fell['reason'],fell
            out={'without_surge':fell['fallback']}
            if has:
                first=render(work/'surge.json',work/'render_surge',config,work/'cache_surge')
                again=render(work/'surge.json',work/'render_surge_again',config,work/'cache_surge')
                a,b=(json.loads((work/n/'stem_receipts.json').read_text(encoding='utf-8'))[0] for n in ('render_surge','render_surge_again'))
                x,_=audio.read_wav(work/'render_surge'/'stems'/'pad.wav')
                assert a['surge']['rendered_with']=='Surge XT' and b['cache_hit'] and a['raw_sha256']==b['raw_sha256'],(a.get('surge'),b['cache_hit'])
                assert first['master']['sha256']==again['master']['sha256'] and float(np.sqrt(np.mean(np.asarray(x,dtype=float)**2)))>1e-4
                out['with_surge']='Surge XT, take kept by the cache'
            return out
        check('surge_part_plays_the_patch_or_its_fallback',surge_part)
        def audition_part():
            # One part's passage played as written (a soft pluck) and on a bright FM bell, alone: two versions in the MP3
            # at one loudness, the bell measured brighter, the order kept.
            from musiclib.audition import audition,parse_sound
            q=copy.deepcopy(p);q['clock']={'bars':2,'meter':[4,4],'tempo':[[0,100]],'tail_seconds':2}
            q['sections']=[{'id':'a','start_bar':0,'bars':2,'intent':'a line'}]
            t=copy.deepcopy(p['tracks'][0]);[t.pop(k,None) for k in ('soundfont','patch','key_map')]
            t.update(id='line',engine='synth',role='melody',range=[60,84],synth={'preset':'pluck'})
            t['notes']=[{'id':f'line_{k}','on':k*.5,'duration':.5,'pitch':(67,69,71,72,74,72,71,69)[k%8]} for k in range(16)]
            t['performance']={'notes':{n['id']:{'velocity':90,'gate':.9} for n in t['notes']}}
            q['tracks']=[t];save_json(work/'audition.json',q)
            r=audition(work/'audition.json','line',[parse_sound('synth:fm_bell')],1,2,work/'audition_out',config,work/'cache_audition',solo=True)
            v=r['versions']
            assert [x['sound'] for x in v]==['as_written','synth_fm_bell'] and (work/'audition_out'/'audition.mp3').is_file()
            assert v[1]['part_brightness']['centroid_hz']>v[0]['part_brightness']['centroid_hz'],v
            assert rejects(lambda:parse_sound('surge:no_such_patch')) and rejects(lambda:parse_sound('synth'))
            # --solo of a part ducked to another, which the solo leaves out: the duck goes too, and each version says so
            # (every version stopped on validate before).
            kick={'id':'kick','engine':'drum_synth','drums':True,'role':'drums','notes':[{'id':f'k{i}','on':i,'duration':.25,'pitch':36} for i in range(8)],
                  'performance':{'notes':{f'k{i}':{'velocity':110} for i in range(8)}},'mix':{'level_dbfs':-14}}
            ducked=copy.deepcopy(q);ducked['tracks'][0]['mix']['duck']={'by':'kick','depth_db':6};ducked['tracks'].append(kick)
            save_json(work/'audition_duck.json',ducked)
            d=audition(work/'audition_duck.json','line',[parse_sound('synth:fm_bell')],1,2,work/'audition_duck',config,work/'cache_audition',solo=True)
            assert all('duck' in x.get('performance_left_out',[]) for x in d['versions']) and d['status']=='PASS',d['versions']
            # Settings only a SoundFont part takes are left out on another engine, and said so.
            from musiclib.audition import with_sound
            sf=copy.deepcopy(p);piano=next(x for x in sf['tracks'] if x['engine']=='soundfont' and not x.get('drums'))
            piano['performance'].update(round_robin=True,dynamics=[[0,64]],legato={'mode':'crossfade'})
            for sound in ('synth:fm_bell','surge:juno_60_strings'):
                q2=copy.deepcopy(sf);x=next(t for t in q2['tracks'] if t['id']==piano['id'])
                assert sorted(with_sound(x,parse_sound(sound)))==['dynamics','legato','round_robin'];validate(q2)
            # Without Surge XT a Surge candidate plays its fallback, and the report says so instead of describing the patch.
            cfg=json.loads(Path(config).read_text(encoding='utf-8'))
            for key in ('fluidsynth','ffmpeg','soundfont'):
                value=Path(cfg[key]['path']);cfg[key]['path']=str(value if value.is_absolute() else Path(config).resolve().parent/value)
            cfg.pop('surge',None);cfg.pop('pedalboard',None);save_json(work/'audition_no_surge.json',cfg)
            r=audition(work/'audition.json','line',[parse_sound('surge:bell_pad'),parse_sound('surge:ghost_pad')],1,2,work/'audition_fallback',work/'audition_no_surge.json',work/'cache_audition_fallback',solo=True)
            fell=r['versions'][1:]
            assert all(x['rendered_with']=='built-in synth' and x['fallback'] and 'surge_character' not in x for x in fell),fell
            assert r['fallbacks']==['surge_bell_pad','surge_ghost_pad'] and 'not an A/B' in r['note'],r
            return {x['sound']:x['part_brightness'] for x in v}
        check('audition_plays_one_part_on_several_sounds',audition_part)
        def revision_rounds_and_clean():
            # Two rounds through the command: the second, after one note moved, names it, synthesizes only its part
            # again and compares with the first. clean then keeps the second round and the cache entries it uses, and
            # removes the first round and its own entry; the next render still reuses everything.
            import subprocess,sys
            from musiclib.revision import revision_round
            from musiclib.clean import clean
            proj=work/'rounds';proj.mkdir();q=example();save_json(proj/'song.json',q)
            shown=[]
            first=revision_round(proj/'song.json',proj/'r1',config,show=shown.append)
            assert first['status']=='DRAFT_PASS' and first['compare'] is None and (proj/'r1'/'round.json').is_file() and (proj/'cache').is_dir(),first
            assert len(shown)==5 and shown[0].startswith('Review of ') and shown[1].startswith('Render (draft) of ') and shown[2].startswith('Analysis of r1'),shown
            q['tracks'][0]['notes'][0]['pitch']+=2;moved=q['tracks'][0]['notes'][0]['id'];save_json(proj/'song_r2.json',q)
            run=subprocess.run([sys.executable,str(Path(__file__).with_name('studio.py')),'round',str(proj/'song_r2.json'),'--output',str(proj/'r2'),'--config',str(config),'--previous',str(proj/'r1')],capture_output=True,text=True,encoding='utf-8',errors='replace')
            assert run.returncode==0 and 'Compare r1 -> r2' in run.stdout and f'note {moved}' in run.stdout and 'Synthesized again: '+q['tracks'][0]['id'] in run.stdout,run.stdout[-3000:]+run.stderr[-1500:]
            second=json.loads((proj/'r2'/'round.json').read_text(encoding='utf-8'))
            # The round names its project and the round before it relative to itself: no local folders in a shared record.
            assert second['project']=='../song_r2.json' and second['previous']=='../r1/render',(second['project'],second['previous'])
            report=json.loads((proj/'r2'/'render'/'report.json').read_text(encoding='utf-8'))
            assert second['compare']=='render/compare_r1.json' and report['cache_hits']==report['stems_reused']==len(q['tracks'])-1,(second,report['cache_hits'])
            # A round's folder stands for its render in analyze and compare; analyze says why it will not overwrite the
            # round's own measurement.
            studio=lambda *a:subprocess.run([sys.executable,str(Path(__file__).with_name('studio.py')),*map(str,a)],capture_output=True,text=True,encoding='utf-8',errors='replace')
            again=studio('compare',proj/'r1',proj/'r2','--output',proj/'r1_r2.json')
            assert again.returncode==0 and again.stdout.startswith('Compare r1 -> r2'),again.stderr[-800:]
            measured=studio('analyze',proj/'r2')
            assert measured.returncode==2 and 'the round measured its render already' in measured.stderr and '--output' in measured.stderr,measured.stderr
            # round --json prints the round's record instead of the summaries.
            third=studio('round',proj/'song_r2.json','--output',proj/'r3','--config',config,'--previous',proj/'r2','--json')
            assert third.returncode==0 and json.loads(third.stdout)==json.loads((proj/'r3'/'round.json').read_text(encoding='utf-8')),third.stdout[-800:]+third.stderr[-800:]
            entries=len([d for d in (proj/'cache').iterdir() if d.is_dir()])
            # clean lists by default and removes only with --remove.
            listing=studio('clean',proj,'--keep',proj/'r2','--keep',proj/'r3')
            assert listing.returncode==0 and listing.stdout.startswith('Would remove') and 'Nothing was removed' in listing.stdout and (proj/'r1').is_dir(),listing.stdout
            done=clean(proj,[proj/'r2',proj/'r3'],remove=True)
            assert not (proj/'r1').exists() and (proj/'r2'/'render'/'master.wav').is_file() and (proj/'song.json').is_file() and (proj/'r1_r2.json').is_file()
            kinds=sorted(x['kind'] for x in done['listed']);left=len([d for d in (proj/'cache').iterdir() if d.is_dir()])
            assert kinds==['cache entry','render','round'] and left==entries-1==len(q['tracks']) and not done['dry_run'],(kinds,entries,left)
            assert rejects(lambda:clean(proj,[])) and rejects(lambda:clean(proj,[work/'render_first']))
            after=render(proj/'song_r2.json',proj/'final',config)
            assert after['cache_hits']==after['stems_reused']==len(q['tracks']) and after['status']=='TECHNICAL_PASS_AUDITION_PENDING'
            return {'rounds':2,'removed':kinds,'cache_entries_kept':left,'final_reused_every_stem':True}
        check('revision_rounds_and_clean',revision_rounds_and_clean)
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
        check('outputs_carry_no_input_metadata',outputs_carry_no_input_metadata)
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
        check('flac_sources_decode_within_a_limit',flac_sources_decode_within_a_limit)
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
        check('a_silent_part_is_named',a_silent_part_is_named)
        def long_automation_renders():
            # A part ridden by 200 automation points renders (FFmpeg's expression failed past 95), and its stem follows them.
            q=copy.deepcopy(p);q['clock']={'bars':4,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':1}
            q['sections']=[{'id':'a','start_bar':0,'bars':4}];q.pop('harmony',None)
            lead=copy.deepcopy(next(t for t in p['tracks'] if t['engine']=='additive'))
            lead['notes']=[{'id':'held','on':0,'duration':16,'pitch':69}];lead['performance']={'notes':{'held':{'velocity':90}}}
            lead['mix'].update(automation=[[i*.08,-12.0 if i%2 else 0.0] for i in range(200)],delay_db=None,reverb_db=None)
            q['tracks']=[lead];save_json(work/'automation.json',q)
            r=render(work/'automation.json',work/'render_automation',config,work/'cache_automation',draft=True)
            y,_=audio.read_wav(work/'render_automation'/'stems'/'lead.wav');y=np.asarray(y,dtype=np.float64)
            c=Clock(q);at=lambda beat:round(c.seconds(beat)*audio.RATE);w=round(.004*audio.RATE)
            level=lambda beat:10*np.log10(np.mean(y[at(beat)-w:at(beat)+w]**2))
            ridden=[level(i*.08)-level((i+1)*.08) for i in range(100,110,2)]
            assert all(d>8 for d in ridden) and r['status']=='DRAFT_PASS',(ridden,r['status'])
            receipt=next(x for x in json.loads((work/'render_automation'/'stem_receipts.json').read_text(encoding='utf-8')) if x['track']=='lead')
            assert receipt.get('automation_points')==200 and 'pow(10' not in receipt['filter_chain'],receipt
            return {'points':200,'level_drop_db':round(float(np.mean(ridden)),1)}
        check('long_automation_renders',long_automation_renders)
    report={'status':'PASS','checks':results,'render_checks_included':bool(config),'direct_audio_audition':False,'musical_quality_certified':False}
    save_json(work/'selfcheck_report.json',report);return report

if __name__=='__main__':
    import sys
    from musiclib import files
    files.escape_unprintable()
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--config',type=Path);args=p.parse_args()
    # The checks write many files under fixed names, so the folder must be new or empty: a report there or not, what
    # it already holds is not theirs to overwrite.
    if files.linked(args.work) or (files.occupied(args.work) and (not args.work.is_dir() or any(args.work.iterdir()))):
        print(f'ERROR: --work {args.work} is not empty (or is a link); give a new or empty folder (the selfcheck writes many files there)',file=sys.stderr)
        sys.exit(2)
    result=checks(args.work,args.config);print(json.dumps({'status':result['status'],'checks':len(result['checks'])}),flush=True)
