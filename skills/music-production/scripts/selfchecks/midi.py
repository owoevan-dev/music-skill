"""selfcheck.py's checks of one area (0.8 step 1.8). MIDI: the performed and the notated file, ports, controllers, bends, ticks, the bounded reader and inspect-midi.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import copy
import numpy as np
import struct
from make_example import example
from musiclib import audio, midi
from musiclib.model import Clock, TPQ, cc_events, performed, validate
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    rejects, work = S['rejects'], S['work']
    def midi_roundtrip():
        p=example();path=work/'roundtrip.mid';routing=midi.write(p,path);m=midi.read(path);clock=Clock(p)
        for t,parsed in zip(p['tracks'],m['tracks'][1:]):
            expected=sorted([(n['tick'],n['end_tick'],n['pitch'],n['velocity']) for n in performed(t,clock)])
            actual=sorted([(n['tick'],n['end_tick'],n['pitch'],n['velocity']) for n in parsed['notes']])
            assert expected==actual and not parsed['unclosed'] and not parsed['stray_offs']
            assert any(e[1]>>4==11 and e[2:]==[64,0] for e in parsed['events'])
        return {'tracks':len(routing),'notes':sum(len(t['notes']) for t in m['tracks'])}
    def ports():
        p=example();base=copy.deepcopy(p['tracks'][0]);p['tracks']=[]
        for i in range(20):t=copy.deepcopy(base);t['id']='part_'+str(i);t['program']=i;p['tracks'].append(t)
        midi.write(p,work/'ports.mid');m=midi.read(work/'ports.mid');addresses=[(t['notes'][0]['port'],t['notes'][0]['channel']) for t in m['tracks'][1:]]
        assert len(set(addresses))==20 and all(ch!=9 for port,ch in addresses) and any(port==1 for port,ch in addresses)
        return {'distinct_melodic_addresses':20}
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
    def render_patch_and_key_map():
        p=example();d=p['tracks'][3];d['patch']={'bank':0,'program':0};d['key_map']={'36':48,'38':50};validate(p)
        midi.write(p,work/'export.mid');midi.write(p,work/'synth.mid',[d],single_stem=True,render=True)
        export=[t for t in midi.read(work/'export.mid')['tracks'] if t['name']=='drums'][0];synth=midi.read(work/'synth.mid')['tracks'][1]
        assert {n['channel'] for n in export['notes']}=={9} and {n['pitch'] for n in export['notes']}=={36,38}
        assert {n['channel'] for n in synth['notes']}=={0} and {n['pitch'] for n in synth['notes']}=={48,50}
        assert len(synth['notes'])==len(export['notes'])
        return {'export_channel':9,'render_channel':0,'mapped':{'36':48,'38':50}}
    def cc_modes():
        p=example();t=p['tracks'][0];t['performance']['cc']=[[0,11,20],[2,11,100],[2,64,127],[3.9,64,0]]
        step=cc_events(t);t['performance']['cc_mode']='linear';ramp=cc_events(t)
        assert step==[(0,11,20),(2,11,100),(2,64,127),(3.9,64,0)]
        values=[v for b,c,v in ramp if c==11];pedal=[(b,v) for b,c,v in ramp if c==64]
        assert len(values)>30 and values==sorted(values) and values[0]==20 and values[-1]==100 and pedal==[(2,127),(3.9,0)]
        return {'linear_cc11_events':len(values),'pedal_stays_switched':True}
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
    def drum_ports():
        p=example();kit=copy.deepcopy(next(t for t in p['tracks'] if t.get('drums')) if any(t.get('drums') for t in p['tracks']) else p['tracks'][0])
        kit.update(drums=True,program=0);a=copy.deepcopy(kit);a['id']='kit_a';b=copy.deepcopy(kit);b['id']='kit_b';b['program']=16
        p['tracks']=[x for x in p['tracks'] if not x.get('drums')]+[a,b];route=midi.write(p,work/'two_kits.mid')
        kits=[(r['port'],r['channel']) for r in route if r['track'] in ('kit_a','kit_b')]
        assert kits==[(0,9),(1,9)],kits
        return {'kits':kits}
    def no_overwrite():
        import subprocess,sys
        here=SCRIPTS;mid=work/'own.mid';midi.write(example(),mid);before=mid.read_bytes()
        done=subprocess.run([sys.executable,str(here/'studio.py'),'inspect-midi',str(mid),'--output',str(mid)],capture_output=True,text=True)
        assert done.returncode==2 and mid.read_bytes()==before,done.stderr
        return {'exit':done.returncode}
    def tick_rounding_is_stable():
        # A position within float error of a half tick takes the even tick, from either side, as round() does at an
        # exact half: one position computed along two paths lands on one tick.
        from musiclib.model import tick_of
        for v,want in ((7102.5,7102),(7103.5,7104),(7102.5+1e-9,7102),(7102.5-1e-9,7102),(1342.5000000000005,1342),(10.4,10),(10.6,11)):
            assert tick_of(v/TPQ)==want,(v,tick_of(v/TPQ))
        return {'values':7}
    found = {'performed_midi_roundtrip_and_pedal_release': midi_roundtrip, 'more_than_15_melodic_parts_have_distinct_ports': ports, 'bounded_untrusted_midi_reader': malformed_midi, 'render_patch_and_key_map_leave_export_authored': render_patch_and_key_map, 'cc_mode_linear_ramps_continuous_controllers_only': cc_modes, 'pitch_bend_exports_rpn_and_wheel': bend_export, 'slow_rubato_reads_back_from_its_midi': slow_rubato_midi, 'drum_parts_get_their_own_ports': drum_ports, 'inspect_midi_keeps_its_input': no_overwrite, 'tick_rounding_is_stable': tick_rounding_is_stable}
    return found
