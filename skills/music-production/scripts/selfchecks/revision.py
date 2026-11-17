"""selfcheck.py's checks of one area (0.8 step 1.8). Revising a piece: excerpts, compare, a one-note and a mix revision, auditions, rounds.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import copy
import json
import numpy as np
from excerpt import extract
from make_example import example
from musiclib import audio
from musiclib.model import Clock, TPQ, performed, save_json, validate
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    config, rejects, work = S['config'], S['rejects'], S['work']
    def excerpt_clock():
        p=example();q=extract(p,3,2);validate(q);a=Clock(p);b=Clock(q)
        assert q['clock']['tempo'][0]==[0,112] and abs(b.end-(a.seconds(16)-a.seconds(8)))<1e-8
        assert q['sections'][0]['start_bar']==0 and q['clock']['bars']==2
        return {'bars':2,'notes':sum(len(t['notes']) for t in q['tracks'])}
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
        # A clip not made says why: the masters identical, or only one gain apart (that was said to leave them alike:
        # GPT Pro's eighth review of 0.4.0, Y04).
        from musiclib import summary as said
        base={'before':'a','after':'b','summary':{},'master_lufs':[-24,-28],'clip':None}
        level_only=said.compare({**base,'files':{'master':{'master':{'identical':False,'level_db':-4.0,'passages':[]}}}},work/'c.json')
        alike=said.compare({**base,'files':{'master':{'master':{'identical':True}}}},work/'c.json')
        assert 'Clip: not made, no passage differs once the levels are matched (the master moved -4.00 dB as a whole)' in level_only,level_only
        assert 'Clip: not made, the masters are identical' in alike,alike
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
        # From GPT Pro's fourth review of 0.4.0: a one-line part whose note a same-key move puts inside the one before
        # it, or within a tick of another, extracts as one line; a note played early that leaves a hair under a tick to
        # the passage's end keeps a whole tick; the rhythmic gate goes on where the piece's pattern stands at the cut.
        def line(engine,bpm,notes,**perf):
            t={'id':'line','engine':engine,'role':'melody','program':0,'notes':[],'performance':{'notes':{},**perf},'mix':{'level_dbfs':-12,'pan':0}}
            for k,(pitch,on,dur,timing,gate) in enumerate(notes):
                t['notes'].append({'id':f'n{k}','on':on,'duration':dur,'pitch':pitch});t['performance']['notes'][f'n{k}']={'velocity':80,'timing_ms':timing,'gate':gate}
            return {'schema':'music-production/v1','title':'Line','clock':{'bars':2,'meter':[4,4],'tempo':[[0,bpm]],'tail_seconds':2},
                    'sections':[{'id':'a','start_bar':0,'bars':2}],'mix':{},'tracks':[t]}
        for source,first in ((line('additive',60,[(60,3.99,1/TPQ,50,.05),(60,4,1,0,.1)]),2),
                             (line('soundfont',120,[(66,3.95,1/TPQ,80,.05),(60,4,1,80,1)],legato={'mode':'slur'},bend_range=12),2),
                             (line('soundfont',120,[(60,3.9994,1,-50,1)]),1)):
            validate(source);validate(extract(copy.deepcopy(source),first,1))
        # A note that sounds one tick, cut short by a later strike of its key, stays in the passage (a float residue had
        # it a hair under the tick, and it went; found by the excerpt fuzzer once it drew one-line parts).
        one_tick=line('soundfont',90,[(64,1.2385,.0115,0,1),(64,1.25,.25,-6,1)],legato={'mode':'slur'},bend_range=12);validate(one_tick)
        sounding={n['id']:n['end_tick']-n['tick'] for n in performed(one_tick['tracks'][0],Clock(one_tick),True)}
        q=extract(copy.deepcopy(one_tick),1,1);validate(q)
        assert sounding['n0']==1 and 'n0' in {n['id'] for n in q['tracks'][0]['notes']},(sounding,q['tracks'][0]['notes'])
        from musiclib import production
        gated=line('soundfont',120,[(60,4,3,0,1)]);gated['tracks'][0]['mix']['gate']={'pattern':'x.....','step_beats':.25,'depth_db':60}
        q=extract(copy.deepcopy(gated),2,1);validate(q)
        def gain(project,beat,seconds):
            c=Clock(project);y,_=production.gate(np.ones((int(seconds*48000),2)),project['tracks'][0],c);return float(y[int(c.seconds(beat)*48000),0])
        for beat in (.1,.3,.6,1.6,3.1):
            assert abs(gain(gated,4+beat,4)-gain(q,beat,2))<1e-3,(beat,gain(gated,4+beat,4),gain(q,beat,2))
        # From GPT Pro's fifth review of 0.4.0: after a same-key move, a note of the passage keeps its length (the
        # one-line pass cut it by the written order, 500 to 25 ms); a note that sounds one tick after a change of tempo
        # stays (a tick at the excerpt's first tempo was the test).
        for engine,extra in (('additive',{}),('soundfont',{'legato':{'mode':'slur'},'bend_range':12})):
            src=line(engine,120,[(60,3.95,.04,50,.5),(60,4,1,100,1)],**extra);validate(src)
            q=extract(copy.deepcopy(src),2,1);validate(q)
            want=next((x['tick']-4*TPQ,x['end_tick']-4*TPQ) for x in performed(src['tracks'][0],Clock(src),True) if x['id']=='n1')
            got=next((x['tick'],x['end_tick']) for x in performed(q['tracks'][0],Clock(q),True) if x['id']=='n1')
            assert got==want,(engine,got,want)
        fast=line('soundfont',60,[(64,4.0,4/TPQ,0,1),(64,4+2/TPQ,.25,0,1)]);fast['clock']['tempo']=[[0,60],[4,120]];validate(fast)
        q=extract(copy.deepcopy(fast),1,2);assert {'n0','n1'}<={n['id'] for n in q['tracks'][0]['notes']},q['tracks'][0]['notes']
        for engine,extra in (('additive',{}),('soundfont',{'legato':{'mode':'slur'},'bend_range':12})):  # and held to one line
            fast=line(engine,60,[(64,4.0,2/TPQ,0,1),(64,4+2/TPQ,.25,0,1)],**extra);fast['clock']['tempo']=[[0,60],[4,120]];validate(fast)
            q=extract(copy.deepcopy(fast),1,2);assert {'n0','n1'}<={n['id'] for n in q['tracks'][0]['notes']},(engine,q['tracks'][0]['notes'])
        # A pickup written before the cut and played inside the passage's first note is written before it, as in the
        # piece, of another key or the same: both play their ticks (the pickup was left out, or cut to 2 of 9 ticks).
        for engine,extra in (('additive',{}),('soundfont',{'legato':{'mode':'slur'},'bend_range':12})):
            for pitch in (64,67):
                src=line(engine,120,[(pitch,3.99,.01,20,1),(67,4,1,0,1)],**extra);validate(src)
                q=extract(copy.deepcopy(src),2,1);validate(q)
                want={x['id']:(x['tick']-4*TPQ,x['end_tick']-4*TPQ) for x in performed(src['tracks'][0],Clock(src),True)}
                got={x['id']:(x['tick'],x['end_tick']) for x in performed(q['tracks'][0],Clock(q),True)}
                assert got==want,(engine,pitch,got,want)
        # From GPT Pro's sixth review of 0.4.0: a pickup at gate 1.6 and a note of the passage played early leave the
        # passage's notes their lengths, the pickup ending sooner (one of them ended 68 ms early); in a chordal part, a
        # pickup that the passage strikes again on the cut is written a few ticks later, its timing keeping where it
        # plays (it was left out).
        for engine,extra in (('additive',{}),('soundfont',{'legato':{'mode':'slur'},'bend_range':12})):
            src=line(engine,120,[(60,3.875,.125,100,1.6),(62,4,.25,100,1.6),(64,4.25,.25,-80,1)],**extra);validate(src)
            q=extract(copy.deepcopy(src),2,1);validate(q)
            want={x['id']:(x['tick']-4*TPQ,x['end_tick']-4*TPQ) for x in performed(src['tracks'][0],Clock(src),True)}
            got={x['id']:(x['tick'],x['end_tick']) for x in performed(q['tracks'][0],Clock(q),True)}
            assert got['n1']==want['n1'] and got['n2']==want['n2'] and got['n0'][0]==want['n0'][0],(engine,got,want)
        chord=line('soundfont',120,[(60,3.875,.0625,62.5,1),(60,4,.5,50,1)]);validate(chord)
        q=extract(copy.deepcopy(chord),2,1);validate(q)
        played=lambda p,shift=0:sorted((x['id'],x['tick']-shift,x['end_tick']-shift) for x in performed(p['tracks'][0],Clock(p),True))
        assert played(q)==played(chord,4*TPQ),(played(q),played(chord,4*TPQ))
        return {'cases':33}
    found = {'excerpt_preserves_tempo_and_score_bounds': excerpt_clock, 'excerpt_moves_bends_sweeps_and_dynamics': excerpt_curves, 'compare_finds_level_and_local_changes': compare_unit, 'compare_reports_no_level_for_a_rewritten_file': compare_rewritten_level, 'excerpt_keeps_the_piece_at_its_edges': excerpt_keeps_the_piece_at_its_edges}
    if config:
        p, cache, render = S['p'], S['cache'], S['render']
        def local_edit():
            q=copy.deepcopy(p);q['tracks'][0]['notes'][0]['pitch']+=2;save_json(work/'edited.json',q)
            r=render(work/'edited.json',work/'render_edited',config,cache)
            assert r['cache_hits']==len(q['tracks'])-1
            before=json.loads((work/'render_first'/'stem_receipts.json').read_text(encoding='utf-8'));after=json.loads((work/'render_edited'/'stem_receipts.json').read_text(encoding='utf-8'))
            changed=[a['track'] for a,b in zip(before,after) if a['raw_sha256']!=b['raw_sha256']]
            assert changed==['piano']
            return {'raw_changed_tracks':changed,'cache_hits':r['cache_hits']}
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
                run=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'compare',str(rest),str(added),'--output',str(report),*extra],capture_output=True,text=True,encoding='utf-8',errors='replace')
                saved=json.loads(report.read_text(encoding='utf-8')) if report.is_file() else {}
                assert run.returncode==0 and saved.get('clip',{}).get('error') and saved['files']['master']['master']['passages'],(why,run.stderr[-600:],saved.get('clip'))
            # --json prints the report as saved, its folders relative to it, not the one with local paths.  (Found by a
            # review of 0.4.0.)
            report=work/'cli_json.json'
            run=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'compare',str(rest),str(added),'--output',str(report),'--json'],capture_output=True,text=True,encoding='utf-8',errors='replace')
            assert run.returncode==0 and json.loads(run.stdout)==json.loads(report.read_text(encoding='utf-8')),run.stderr[-600:]
            # A render still at work in the second folder is refused as in the first (files.working).  A mutant that held
            # the second only when it was the first lived through every check (0.8's mutation analysis, 2026-11-15).
            from musiclib import files as fs
            with fs.working(added) as held:
                run=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'compare',str(rest),str(added),'--output',str(work/'cli_in_use.json')],
                                   capture_output=True,text=True,encoding='utf-8',errors='replace')
            if held:  # on a drive that cannot lock files, working() lets every run through and says so (files.working)
                assert run.returncode==2 and 'in use' in run.stderr and not (work/'cli_in_use.json').exists(),(run.returncode,run.stderr[-300:])
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
            # The command takes render's --jobs, as round does (each of the six agents of the 0.5 A/B asked for it on a
            # machine others were rendering on): 0 is refused before anything is made, and 1 renders each version's two
            # parts one at a time.
            import subprocess,sys
            two=copy.deepcopy(q);low=copy.deepcopy(two['tracks'][0]);low.update(id='low',role='countermelody',range=[48,72])
            low['notes']=[dict(n,id='low_'+n['id'],pitch=n['pitch']-12) for n in low['notes']]
            low['performance']={'notes':{'low_'+k:x for k,x in low['performance']['notes'].items()}};two['tracks'].append(low)
            save_json(work/'audition_two.json',two)
            def audition_command(folder,jobs):
                return subprocess.run([sys.executable,str(SCRIPTS/'studio.py'),'audition',str(work/'audition_two.json'),'--track','line',
                                       '--sounds','synth:fm_bell','--bars','1-2','--output',str(folder),'--config',str(config),'--cache',str(work/'cache_audition'),
                                       '--jobs',jobs],capture_output=True,text=True)
            done=audition_command(work/'audition_jobs_zero','0')
            assert done.returncode==2 and '--jobs is 1 or more' in done.stderr and not (work/'audition_jobs_zero').exists(),(done.returncode,done.stderr[-300:])
            done=audition_command(work/'audition_jobs_one','1');assert done.returncode==0,done.stderr[-600:]
            # The passage is the bars --bars names, the first to the last (a mutant that played the last bar alone lived
            # through every check: 0.8's mutation analysis, 2026-11-15).
            held=json.loads((work/'audition_jobs_one'/'audition.json').read_text(encoding='utf-8'));assert held['bars']==[1,2],held['bars']
            ran=[json.loads((f/'render'/'report.json').read_text(encoding='utf-8')) for f in sorted((work/'audition_jobs_one').iterdir()) if (f/'render').is_dir()]
            assert len(ran)==2 and all(x['jobs']==1 and x['stem_count']==2 for x in ran),[(x['jobs'],x['stem_count']) for x in ran]
            # The versions play at one loudness as cut, not as rendered: a long release whose note is on the passage's
            # last beat counted its ring-out past the cut and played 2 LU above the version matched to it (GPT Pro's
            # eighth review of 0.4.0, Y01).
            late=copy.deepcopy(q);late['clock']={'bars':1,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':10}
            late['sections']=[{'id':'a','start_bar':0,'bars':1,'intent':'a line'}]
            pad=late['tracks'][0];pad['synth']={'preset':'warm_pad','amp':{'attack':1.2,'decay':1.0,'sustain':.9,'release':4.0}}
            pad['notes']=[{'id':'n','on':3,'duration':1,'pitch':60}];pad['performance']={'notes':{'n':{'velocity':90,'gate':1}}}
            save_json(work/'audition_late.json',late)
            g=audition(work/'audition_late.json','line',[parse_sound('synth:fm_epiano')],1,1,work/'audition_late',config,work/'cache_audition',solo=True)
            x,_=audio.read_wav(work/'audition_late'/'audition.wav');n=round(g['each_seconds']*audio.RATE);gap=round(g['gap_seconds']*audio.RATE)
            levels=[]
            for i in range(2):
                seg=work/'audition_late'/f'played_{i}.wav';audio.write_wav(seg,np.asarray(x[i*(n+gap):i*(n+gap)+n],dtype=np.float32))
                levels.append(audio.measure(audio.load_config(config),seg,work/'audition_late',f'played_{i}')['integrated_lufs'])
            assert abs(levels[0]-levels[1])<=.1 and abs(levels[0]-g['loudness_lufs'])<=.1,(levels,g['loudness_lufs'],[(v['master_lufs'],v['cut_lufs']) for v in g['versions']])
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
            run=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'round',str(proj/'song_r2.json'),'--output',str(proj/'r2'),'--config',str(config),'--previous',str(proj/'r1')],capture_output=True,text=True,encoding='utf-8',errors='replace')
            assert run.returncode==0 and 'Compare r1 -> r2' in run.stdout and f'note {moved}' in run.stdout and 'Synthesized again: '+q['tracks'][0]['id'] in run.stdout,run.stdout[-3000:]+run.stderr[-1500:]
            second=json.loads((proj/'r2'/'round.json').read_text(encoding='utf-8'))
            # The round names its project and the round before it relative to itself: no local folders in a shared record.
            assert second['project']=='../song_r2.json' and second['previous']=='../r1/render',(second['project'],second['previous'])
            report=json.loads((proj/'r2'/'render'/'report.json').read_text(encoding='utf-8'))
            assert second['compare']=='render/compare_r1.json' and report['cache_hits']==report['stems_reused']==len(q['tracks'])-1,(second,report['cache_hits'])
            # A round's folder stands for its render in analyze and compare; analyze says why it will not overwrite the
            # round's own measurement.
            studio=lambda *a:subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),*map(str,a)],capture_output=True,text=True,encoding='utf-8',errors='replace')
            again=studio('compare',proj/'r1',proj/'r2','--output',proj/'r1_r2.json')
            assert again.returncode==0 and again.stdout.startswith('Compare r1 -> r2'),again.stderr[-800:]
            # Without --output a round's comparison is render/compare_<round>.json, which the round wrote: refused, and
            # nothing written (a mutant that named it after the render folder wrote compare_render.json: 0.8's second
            # mutation sample, 2026-11-15).
            twice=studio('compare',proj/'r1',proj/'r2')
            assert twice.returncode==2 and 'compare_r1.json exists' in twice.stderr and not (proj/'r2'/'render'/'compare_render.json').exists(),twice.stderr[-500:]
            # A WAV reference is converted and metered by FFmpeg, which --config names (a mutant without the option lived
            # through every check: the same sample).  The render's own master as the reference: every difference is 0,
            # so a command that left the reference out, or compared another file, is seen (the outside review).
            ref=studio('analyze',proj/'r2','--reference',proj/'r2'/'render'/'master.wav','--config',config,'--output',proj/'r2_against_itself.json')
            assert ref.returncode==0,ref.stderr[-800:]
            got=json.loads((proj/'r2_against_itself.json').read_text(encoding='utf-8'))['reference_comparison']
            flat=[got[k] for k in ('slope_difference_db_per_octave','low_end_difference_db','top_end_difference_db','integrated_lufs_difference')]
            assert got['reference'] and 'master' in str(got['reference']) and all(v is not None and abs(v)<=.1 for v in flat),got
            # And against another file: the master 6 dB down under a name of its own.  Every level falls by the same
            # 6.02 dB, so the master measures that much louder, and the spectra, each levelled at its own line, match.
            # A command that measured the render's own master whatever file it was given passed the comparison above
            # (0.8's second outside review, 2026-11-16); here it measures 0 dB and names master.wav.
            x,_=audio.read_wav(proj/'r2'/'render'/'master.wav');audio.write_wav(proj/'quieter_reference.wav',np.asarray(x,dtype=np.float32)*0.5);del x
            ref=studio('analyze',proj/'r2','--reference',proj/'quieter_reference.wav','--config',config,'--output',proj/'r2_against_quieter.json')
            assert ref.returncode==0,ref.stderr[-800:]
            got=json.loads((proj/'r2_against_quieter.json').read_text(encoding='utf-8'))['reference_comparison']
            spectra=[got[k] for k in ('slope_difference_db_per_octave','low_end_difference_db','top_end_difference_db')]
            assert 'quieter_reference' in str(got['reference']) and abs(got['integrated_lufs_difference']-6.02)<=.15 and all(v is not None and abs(v)<=.1 for v in spectra),got
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
        found.update({'one_note_revision_regenerates_only_its_part': local_edit, 'mix_revision_reuses_all_synthesis': mix_edit, 'compare_reports_what_changed_and_where': compare_render, 'audition_plays_one_part_on_several_sounds': audition_part, 'revision_rounds_and_clean': revision_rounds_and_clean})
    return found
