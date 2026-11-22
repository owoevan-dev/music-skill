"""selfcheck.py's checks of one area (0.8 step 1.8). What a composition script uses: performance (timing, swing, rubato, strums, phrasing), voicing, the building blocks, the builder and `studio.py start`.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import copy
import json
import numpy as np
from make_example import example
from musiclib.model import Clock, TPQ, file_hash, performed, save_json, validate
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    rejects, work = S['rejects'], S['work']
    def offset_shift():
        p=example();t=p['tracks'][0];clock=Clock(p);base=performed(t,clock)
        t['performance']['offset_ms']=-80;moved=performed(t,clock)
        deltas={round(a['start_seconds']-b['start_seconds'],3) for a,b in zip(base,moved) if a['tick']>0}
        assert deltas=={0.08};validate(p)
        return {'shift_seconds':0.08}
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
        # The player's distance from the beat runs in time, not by note count: a note added changes only itself (every
        # note of the part moved when it gained one: the 0.4.0 Haiku pieces).
        line=copy.deepcopy(example());m=copy.deepcopy(line['tracks'][0]);m.update(id='line',role='rhythm')
        m['notes']=[{'id':f'l{k}','on':k*.5,'duration':.4,'pitch':60+k%5} for k in range(48)]
        m['performance']={'notes':{n['id']:{'velocity':80,'timing_ms':0,'gate':1} for n in m['notes']},'cc':[]};line['tracks']=[m]
        more=copy.deepcopy(line);more['tracks'][0]['notes'].append({'id':'l_new','on':12.25,'duration':.2,'pitch':62})
        more['tracks'][0]['performance']['notes']['l_new']={'velocity':80,'timing_ms':0,'gate':1}
        old_line,old_more=copy.deepcopy(line),copy.deepcopy(more)
        expression.apply(line,seed=9,drift='time');expression.apply(more,seed=9,drift='time')
        a,b=line['tracks'][0]['performance']['notes'],more['tracks'][0]['performance']['notes']
        moved=[k for k in a if a[k]!=b[k]]
        assert moved==[] and set(b)-set(a)=={'l_new'} and len({v['timing_ms'] for v in a.values()})>40,moved
        # So too a note added in the last half of the score's last sixteenth: it had grown the grid by a slot and
        # redrawn every note (GPT's review of 0.5, E04).
        bar=copy.deepcopy(old_line);bar['clock']['bars']=1;bar['sections']=[{'id':'a','start_bar':0,'bars':1}]
        bar['tracks'][0]['notes']=[{'id':f'b{k}','on':k*.5,'duration':.125,'pitch':60+k%5} for k in range(8)]
        bar['tracks'][0]['performance']['notes']={n['id']:{'velocity':80,'timing_ms':0,'gate':1} for n in bar['tracks'][0]['notes']}
        added=copy.deepcopy(bar);added['tracks'][0]['notes'].append({'id':'b_tail','on':3.875,'duration':.125,'pitch':62})
        added['tracks'][0]['performance']['notes']['b_tail']={'velocity':80,'timing_ms':0,'gate':1}
        expression.apply(bar,seed=20261109,drift='time');expression.apply(added,seed=20261109,drift='time')
        u,v=bar['tracks'][0]['performance']['notes'],added['tracks'][0]['performance']['notes']
        assert [k for k in u if u[k]!=v[k]]==[] and len({x['timing_ms'] for x in u.values()})>4,[k for k in u if u[k]!=v[k]]
        # The default still steps note by note: a part that gains a note is drawn again.
        expression.apply(old_line,seed=9);expression.apply(old_more,seed=9)
        x,y=old_line['tracks'][0]['performance']['notes'],old_more['tracks'][0]['performance']['notes']
        assert len([k for k in x if x[k]!=y[k]])>40 and rejects(lambda:expression.apply(copy.deepcopy(line),drift='bars'))
        return {'downstroke_ms':down,'upstroke_ms':up,'notes_moved_by_an_added_note':moved}
    def keeps_to_the_beat():
        # The timing line of 0.6: a player keeping to the beat takes back a share of the distance from it by the next
        # beat and a new error comes on top (linear phase correction: Repp 2005, Table 1).  The oracle is that model
        # run on tap times, not the function: taps t(n+1) = t(n) + T - share * (t(n) - m(n)) + noise against a
        # metronome m(n) = n T.  Its distances from the beat correlate by 1 - share one beat apart, by the square two
        # apart, and the function's series does the same.
        from musiclib import expression
        rng=np.random.default_rng(31);ac=lambda x,k:float(np.corrcoef(x[:-k],x[k:])[0,1])  # noqa: E731
        for share in (.2,.4,.8):
            T,N=.5,60000;t=np.empty(N);t[0]=0.0;noise=rng.standard_normal(N)*.01
            for n in range(N-1):t[n+1]=t[n]+T-share*(t[n]-n*T)+noise[n]
            taps=t-np.arange(N)*T;line=expression.kept_to_the_beat(N,rng,share)
            for lag in (1,2,3):
                assert abs(ac(taps,lag)-(1-share)**lag)<.03 and abs(ac(line,lag)-(1-share)**lag)<.03,(share,lag,ac(taps,lag),ac(line,lag))
        # Four values to the beat (the sixteenth-note grid): a beat apart is four steps on.
        grid=expression.kept_to_the_beat(120000,rng,.4,4)
        assert abs(ac(grid,4)-.6)<.03 and abs(ac(grid,8)-.36)<.03 and abs(float(grid.mean()))<1e-9 and abs(float(grid.std())-1)<1e-9
        # The likeness is short: over the lowest decades of frequency the power stays level, where the 1/f line the
        # loudness keeps goes on rising toward zero frequency.
        def decades(x):
            p=np.abs(np.fft.rfft(x))**2;f=np.fft.rfftfreq(len(x));ref=float(p[(f>=1e-2)&(f<1e-1)].mean())
            return [float(p[(f>=a)&(f<10*a)].mean())/ref for a in (1e-4,1e-3)]
        level,rising=decades(expression.kept_to_the_beat(1<<17,rng,.4)),decades(expression.lrc(1<<17,rng,.8))
        assert max(level)<3 and rising[0]>10*level[0] and rising[0]>rising[1]>1,(level,rising)
        assert len(expression.kept_to_the_beat(0,rng))==0 and list(expression.kept_to_the_beat(1,rng))==[0.0]
        for wrong in (0,-.1,1.5):
            assert rejects(lambda:expression.kept_to_the_beat(8,rng,wrong)),wrong
        # In a piece: a long line of eighth notes with only the distance from the beat (no motor delay) keeps the
        # correlation a beat apart, two onsets on; with only the motor delays, successive onsets are unrelated.
        def line(profile,drift):
            p=copy.deepcopy(example());m=copy.deepcopy(p['tracks'][0]);m.update(id='line',role='rhythm')
            p['clock']['bars']=500;p['sections']=[{'id':'a','start_bar':0,'bars':500}]
            m['notes']=[{'id':f'l{k}','on':k*.5,'duration':.4,'pitch':60} for k in range(4000)]
            m['performance']={'notes':{n['id']:{'velocity':80,'timing_ms':0,'gate':1} for n in m['notes']},'cc':[]};p['tracks']=[m]
            expression.apply(p,{'line':{'timing_sd':0,'short_sd':0,'vel_pct':0,'arch':0,'gate_sd':0,'contrast':0,**profile}},seed=12,drift=drift)
            return np.array([m['performance']['notes'][f'l{k}']['timing_ms'] for k in range(4000)])
        slow=line({'timing_sd':6},'time');motor=line({'short_sd':6},'time');by_note=line({'timing_sd':6},'notes')
        assert abs(ac(slow,2)-.6)<.06 and abs(float(slow.std())-6)<.4 and abs(ac(motor,1))<.06 and abs(ac(by_note,2)-.6)<.06,(ac(slow,2),float(slow.std()),ac(motor,1),ac(by_note,2))
        assert abs(ac(line({'timing_sd':6,'correction':.2},'time'),2)-.8)<.06 and rejects(lambda:line({'timing_sd':6,'correction':0},'time'))
        # Each part keeps to the beat by itself: a part's timing is the same whatever other parts the piece has.
        alone=copy.deepcopy(example());both=copy.deepcopy(alone);extra=copy.deepcopy(both['tracks'][0]);extra['id']='extra_part'
        extra['notes']=[{**n,'id':'x_'+n['id']} for n in extra['notes']];extra['performance']={**extra['performance'],'notes':{'x_'+k:dict(v) for k,v in extra['performance']['notes'].items()}}
        both['tracks'].append(extra);expression.apply(alone,seed=3,drift='time');expression.apply(both,seed=3,drift='time')
        assert all(a['performance']['notes']==b['performance']['notes'] for a,b in zip(alone['tracks'],both['tracks']))
        # Onsets nearer than a sixteenth note share a slot of the grid, and each still has a motor delay of its own:
        # eight thirty-second notes with the slow line off move by eight different amounts (they had taken their
        # slot's, the same for two or three of them: a review of 0.6.0).  The delay is the onset's own, so the same
        # onsets in a longer line keep theirs.
        def thirty_seconds(count):
            q=example();part=copy.deepcopy(next(x for x in q['tracks'] if x.get('role')=='melody'))
            part['notes']=[{**part['notes'][0],'id':f'm{k}','on':k*.125,'duration':.1,'pitch':60+k%12} for k in range(count)]
            part['performance']={**part['performance'],'notes':{n['id']:{'velocity':80,'gate':1.0,'timing_ms':0} for n in part['notes']}}
            q['tracks']=[part]
            expression.apply(q,{part['id']:{'timing_sd':0,'short_sd':5,'feel':0,'spread':0,'lead':0,'vel_pct':0,'arch':0,'high_loud':0,'gate_sd':0,'contrast':0}},seed=7,drift='time')
            return [part['performance']['notes'][f'm{k}']['timing_ms'] for k in range(count)]
        eight,sixteen=thirty_seconds(8),thirty_seconds(16)
        assert len(set(eight))==8 and sixteen[:8]==eight,(eight,sixteen)
        # One beat is one onset however its number is written: a note at beat 1 draws the same delay written 1 or 1.0,
        # alone or with another note on that beat written the other way, under it or over it (the key had been the
        # number as Python prints it, and 1 and 1.0 drew 22 ms apart: the third review of 0.6.0).  A strummed chord
        # likewise strums the same written in whole numbers or not.
        def at_beat_one(own,other=None,pitch=60,strum=0):
            q=example();part=copy.deepcopy(next(x for x in q['tracks'] if x.get('role')=='melody'))
            part['notes']=[{**part['notes'][0],'id':'old','on':own,'duration':.125,'pitch':64}]+([{**part['notes'][0],'id':'new','on':other,'duration':.125,'pitch':pitch}] if other is not None else [])
            part['performance']={**part['performance'],'notes':{n['id']:{'velocity':80,'gate':1.0,'timing_ms':0} for n in part['notes']}}
            q['tracks']=[part]
            expression.apply(q,{part['id']:{'timing_sd':0,'short_sd':0 if strum else 6,'feel':0,'spread':0,'lead':0,'vel_pct':0,'arch':0,'high_loud':0,'gate_sd':0,'contrast':0,'strum':strum}},seed=7,drift='time')
            return [part['performance']['notes'][n['id']]['timing_ms'] for n in part['notes']]
        ones=[at_beat_one(1)[0],at_beat_one(1.0)[0],at_beat_one(1,1.0,60)[0],at_beat_one(1,1.0,67)[0],at_beat_one(1.0,1,60)[0],at_beat_one(.1+.9)[0]]
        assert len(set(ones))==1 and ones[0]!=0,ones
        strums=[at_beat_one(1,1,60,12),at_beat_one(1.0,1.0,60,12),at_beat_one(1,1.0,60,12)]
        assert strums[0]==strums[1]==strums[2] and strums[0][0]!=strums[0][1],strums
        return {'a_beat_apart':round(ac(slow,2),3),'motor_delays_lag_1':round(ac(motor,1),3),'level_power_by_decade':[round(v,2) for v in level],
                'loudness_power_by_decade':[round(v,2) for v in rising]}
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
        # A slash starts a bass only before a note name: 6/9 keeps its slash, as 69 does, with or without a bass (it was
        # read as a bass of 9 and refused: GPT Pro's eighth review of 0.4.0, Y03).
        from musiclib.harmony import parse
        assert parse('C6/9')['pcs']==parse('C69')['pcs']=={0,2,4,7,9} and parse('C6/9/E')['bass']==4 and parse('F#m7/A')['bass']==9
        assert parse('C/9') is None and len(voice_lead(['C6/9','F6/9/A'],voices=4,low=48,high=79))==2
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
        # A range too narrow for the rules gives a voicing that breaks them, and says so with the chord and the
        # range: four voices of a ninth chord in fourteen semitones are a cluster (a session of the 0.7 baseline
        # met that silently and dropped the function).  A range with room says nothing.
        import warnings
        from musiclib.voicing import GivenUp
        with warnings.catch_warnings(record=True) as said:
            warnings.simplefilter('always')
            narrow=voice_lead(['Dm9','G7'],voices=4,low=55,high=69);roomy=voice_lead(['Dm9','G7'],voices=4,low=48,high=72)
        told=[str(w.message) for w in said if issubclass(w.category,GivenUp)]
        assert len(told)==1 and 'Dm9 (chord 1)' in told[0] and 'between 55 and 69' in told[0],told
        assert any(rub(a,b) for a in narrow[0] for b in narrow[0]) and not any(rub(a,b) for v in roomy for a in v for b in v),(narrow,roomy)
        for v in jazz+smooth+strict+low+gb+apart:
            assert v==sorted(v) and all(0<b-a<=12 for a,b in zip(v,v[1:])) and all(a>=LOW_INTERVAL_LIMITS.get(b-a,0) for a,b in zip(v,v[1:])),v
            assert not any(rub(a,b) for i,a in enumerate(v) for b in v[i+1:]),v
        return {'ii_V_I':jazz,'pop_motion':motion(smooth),'root_position_motion':motion(naive),'parallels':[parallels(free),parallels(strict)]}
    def building_blocks():
        # The blocks refuse a call without the piece's decisions; one seed gives the same notes twice and the seeds of
        # other pieces give many grooves for one setting; the downbeat kick and the backbeat stay where they were asked;
        # the drums' velocities and kick counts are the drummers' (an oracle read from the statistics file); a fill
        # stops the cymbals; the candidates differ; the bass's push and walking line, the comping's answer to the
        # melody; every figure validates under one progression, and review reads the result
        # (references/building-blocks.md).
        from musiclib import blocks
        from musiclib.review import review as review_score
        stats=blocks.statistics()
        assert stats['source']['license']=='CC BY 4.0, Google LLC' and set(blocks.FEELS)==set(stats['feels'])
        base=dict(bars=16,meter=[4,4],feel='funk',backbeat='normal',kick='syncopated',pulse='sixteenth',cymbal='closed_hat',complexity=.6,intensity=.7,fills=.5)
        assert rejects(lambda:blocks.drums(**base)) and rejects(lambda:blocks.drums(**{**base,'seed':1,'kick':None}))
        assert rejects(lambda:blocks.drums(**{**base,'seed':1,'feel':None})) and rejects(lambda:blocks.drums(**{**base,'seed':1,'meter':[12,8]}))
        assert rejects(lambda:blocks.bass(['C'],[4,4],seed=1,figure='root',complexity=.5,intensity=.5,low=28,high=52,fills=0))
        assert rejects(lambda:blocks.bass(['C'],[4,4],seed=1,figure='pattern',complexity=.5,intensity=.5,low=28,high=52,push='none',fills=0,pattern='x..x'))
        assert rejects(lambda:blocks.accompaniment(['C'],[4,4],seed=1,figure='held',complexity=.5,intensity=.5,low=52,high=76,voices=4))
        a=blocks.drums(seed=blocks.seed('Song A'),**base)
        assert a==blocks.drums(seed=blocks.seed('Song A'),**base)
        grooves={tuple(blocks.drums(seed=blocks.seed(f'Song {k}'),**base)['record']['kick_steps']) for k in range(40)}
        assert len(grooves)>=20,len(grooves)
        plain=blocks.drums(seed=blocks.seed('Song A'),**{**base,'fills':0,'intensity':.5})
        kicks={round(n['on'],4) for n in plain['notes'] if n['pitch']==36};backbeat={round(n['on'],4):n['velocity'] for n in plain['notes'] if n['pitch']==38}
        assert all(b*4 in kicks for b in range(16)) and all(b*4+1 in backbeat and b*4+3 in backbeat for b in range(16)),(sorted(kicks),sorted(backbeat))
        funk=stats['feels']['funk']
        assert backbeat[1.0]==round(funk['velocity']['snare']['by_step']['4'][2])  # intensity 0.5: the drummers' median at that step
        hat0=[n['velocity'] for n in plain['notes'] if n['pitch']==42 and abs(n['on']%4)<1e-9]
        assert hat0 and all(v==round(funk['velocity']['hat_closed']['by_step']['0'][2]) for v in hat0),hat0
        assert len(plain['record']['kick_steps'])==round(blocks._q(funk['per_bar']['kick'],.6)),plain['record']['kick_steps']
        # Bar 8 ends the drummers' median spacing of fills (four bars in funk): the cymbals stop where the fill starts
        # and the same groove plays until then.
        cym=lambda part:[round(n['on'],4) for n in part['notes'] if 28<=n['on']<32 and n['pitch'] in (42,46)]
        ca,cp=cym(a),cym(plain)
        assert len(ca)<len(cp) and ca==cp[:len(ca)],(ca,cp)
        assert any(n['pitch'] in (38,45,47,50) and cp[len(ca)]-1e-9<=n['on']<32 for n in a['notes']),cp[len(ca)]
        rock=blocks.drums(seed=1,**{**base,'feel':'rock','kick':'one_three','pulse':'eighth'})
        assert rock['record']['typical'] and 'basic rock beat' in rock['record']['typical'][0]
        shuffle=blocks.drums(seed=1,**{**base,'meter':[12,8],'feel':'jazz_shuffle','cymbal':'ride','pulse':'feel'})
        rides=[n for n in shuffle['notes'] if n['pitch']==51]   # (all() of none passed with every ride gone: the review of 0.8.0)
        assert rides and all(abs(n['on']*2-round(n['on']*2))<1e-9 for n in rides)  # on the triplet eighths
        options=blocks.candidates(n=4,seed=blocks.seed('Song A'),**base)
        assert len({tuple(o['kick_steps']) for o in options})==4,options
        chords=['C','Am7','Fmaj7','G7']*4;sections=[{'id':'a','start_bar':0,'bars':8},{'id':'b','start_bar':8,'bars':8}]
        q={'schema':'music-production/v1','title':'Blocks','clock':{'bars':16,'meter':[4,4],'tempo':[[0,110]],'tail_seconds':2},'sections':sections,
           'mix':{'chain':'bus'},'harmony':[{'bar':i+1,'symbol':c} for i,c in enumerate(chords)],'tracks':[]}
        for fig in blocks.BASS_FIGURES:
            for push in blocks.PUSHES:
                line=blocks.bass(chords,[4,4],seed=2,figure=fig,complexity=.5,intensity=.7,low=28,high=52,kick=a,push=push,fills=.5,
                                 pattern='x..x..x...x.o.o.' if fig=='pattern' else None)
                assert line['notes'] and all(28<=n['pitch']<=52 for n in line['notes']),fig
        level=blocks._dynamic(.7);assert level==88  # pp 32 to ff 112 on MuseScore's table
        pushed=blocks.bass(chords,[4,4],seed=2,figure='root',complexity=0,intensity=.7,low=28,high=52,push='changes',fills=0)
        on={round(n['on'],4):n for n in pushed['notes']}
        assert all(on[b*4-.5]['pitch']%12==blocks.parse(chords[b])['root'] and b*4 not in on for b in range(1,16)),sorted(on)
        assert all(n['velocity']==level for n in pushed['notes'])
        walk=blocks.bass(['Dm7','G7','Cmaj7','Cmaj7']*2,[4,4],seed=3,figure='walking',complexity=.5,intensity=.6,low=28,high=55,push='none',fills=0)['notes']
        assert all(n['pitch']%12==blocks.parse(c)['root'] for n,c in zip(walk[::4],['Dm7','G7','Cmaj7','Cmaj7']*2))
        assert any(n['pitch']%12 not in blocks.parse(c)['pcs'] for k,c in enumerate(['Dm7','G7','Cmaj7','Cmaj7']*2) for n in walk[k*4+1:k*4+3]),walk
        melody=[{'on':t,'duration':.5,'pitch':79} for t in (.5,2.5,5,6.5,9.5,11,12.5,14.5)]
        comp=blocks.accompaniment(chords[:4],[4,4],seed=4,figure='syncopated',complexity=1,intensity=.6,low=52,high=72,voices=4,push='none',melody=melody)
        attacks={round(n['on'],4) for n in comp['notes']}
        assert not attacks&({t for t in (n['on'] for n in melody)}-{0,4,8,12}) and attacks>={0,4,8,12},sorted(attacks)
        for fig in blocks.ACCOMPANIMENTS:
            for push in blocks.PUSHES:
                comp=blocks.accompaniment(chords,[4,4],seed=2,figure=fig,complexity=.5,intensity=.6,low=52,high=76,voices=4,push=push,
                                          pattern='x...o.x...o.x.o.' if fig=='pattern' else None)
                assert comp['notes'] and all(52<=n['pitch']<=76 for n in comp['notes']),fig
        for tid,engine,role,result in (('drums','drum_synth','drums',a),('bass','synth','bass',blocks.bass(chords,[4,4],seed=2,figure='root_fifth',complexity=.5,intensity=.7,low=28,high=52,push='phrase',fills=.5)),
                                       ('keys','synth','harmony',blocks.accompaniment(chords,[4,4],seed=2,figure='syncopated',complexity=.5,intensity=.6,low=52,high=76,voices=4,push='phrase'))):
            t={'id':tid,'engine':engine,'role':role,'notes':[],'mix':{'level_dbfs':-20}}
            t.update({'drums':True,'kit':{'style':'909'}} if engine=='drum_synth' else {'synth':{'preset':'warm_pad' if role=='harmony' else 'sub_bass'}})
            q['tracks'].append(blocks.add(t,result,tid[0]))
        validate(q);r=review_score(q,work/'review_blocks')
        assert not r['stiffness']['block_chord_parts'],r['stiffness']['block_chord_parts']
        return {'grooves_from_40_pieces':len(grooves),'candidates':[(o['kick_density'],o['kick_syncopation']) for o in options]}
    def blocks_more():
        # The blocks added in 0.5-2, each against its source: the blast beats (Wikipedia, Blast beat), the double kick,
        # a groove written on the step grid, the skank (Wikipedia, Reggae), la pompe (Wikipedia, Gypsy jazz), the batida
        # (Wikipedia, Bossa nova), slides between overlapping notes, and Eerola et al.'s articulation ratio.
        from musiclib import blocks
        steps=lambda res,key:sorted({round((n['on']%4)*4) for n in res['notes'] if n['pitch']==key})
        base=dict(seed=7,feel='rock',complexity=0,intensity=.6,fills=0)
        blast=blocks.drums(2,[4,4],backbeat='blast',kick='eighths',pulse='eighth',cymbal='ride',**base)
        assert steps(blast,36)==list(range(0,16,2)) and steps(blast,38)==list(range(1,16,2)) and steps(blast,51)==list(range(0,16,2)),blast['record']
        assert any('traditional blast' in x for x in blast['record']['typical'])
        hammer=blocks.drums(1,[4,4],backbeat='eighths',kick='eighths',pulse='none',cymbal='ride',**base)
        bomb=blocks.drums(1,[4,4],backbeat='eighths',kick='double',pulse='none',cymbal='ride',**base)
        assert steps(hammer,36)==steps(hammer,38)==list(range(0,16,2)) and steps(bomb,36)==list(range(16)) and steps(bomb,38)==list(range(0,16,2))
        thrash=blocks.drums(1,[4,4],backbeat='double',kick='four_floor',pulse='eighth',cymbal='ride',**base)
        assert steps(thrash,36)==[0,4,8,12] and steps(thrash,38)==[2,6,10,14] and any('thrash' in x for x in thrash['record']['typical'])
        rejects(lambda:blocks.drums(1,[6,8],backbeat='blast',kick='eighths',pulse='eighth',cymbal='ride',**base))
        grid={'kick':'x...x...x...x...','snare':'....x.......x...','closed_hat':'xoxoxoxoxoxoxoxo'}
        sparse,full=(blocks.drums(2,[4,4],pattern=grid,**{**base,'complexity':c}) for c in (0,1))
        assert steps(sparse,36)==[0,4,8,12] and steps(sparse,38)==[4,12] and steps(sparse,42)==list(range(0,16,2)) and steps(full,42)==list(range(16))
        assert sparse['record']['pattern']==grid and not [n for n in sparse['notes'] if n['pitch'] not in (36,38,42)]
        rejects(lambda:blocks.drums(1,[4,4],pattern=grid,backbeat='normal',**base))
        for voice in ('open_hat','crash'):  # written half a beat long on the last sixteenth, past the block (E01)
            last=blocks.drums(1,[4,4],pattern={voice:'...............x'},**{**base,'seed':20261109})['notes'][-1]
            assert last['on']+last['duration']<=4+1e-9,last
        short=blocks.bass(['C','G'],[2,4],seed=1,figure='root',complexity=.75,intensity=.5,low=28,high=52,push='changes',fills=1,phrase_bars=1)
        assert short['notes'] and min(n['on'] for n in short['notes'])>=0  # its fill had begun before the piece (E02)
        for bad in ({'kick':'x...'},{'cowbell':'x...............'},{'kick':'x..y............'},{'kick':'................'}):
            rejects(lambda:blocks.drums(1,[4,4],pattern=bad,**base))
        chords=['C','Am','F','G']
        acc=lambda fig,**k:blocks.accompaniment(chords,[4,4],seed=3,figure=fig,complexity=k.pop('complexity',0),intensity=.6,low=48,high=72,voices=3,push='none',**k)
        on=lambda res:sorted({round(n['on'],3) for n in res['notes']})
        skank=acc('offbeat');double=acc('offbeat',complexity=1)
        assert on(skank)==[b+.5 for b in range(16)] and all(n['duration']==.25 for n in skank['notes']) and on(double)==sorted([b+.5 for b in range(16)]+[b+.75 for b in range(16)])
        pompe=acc('pompe');beats=[b for b in range(16)];graces=[b-.125 for b in range(2,16,2)]
        assert on(pompe)==sorted(beats+graces),on(pompe)  # before 1 and 3, across each change, not before the first beat
        vel={round(n['on'],3):n['velocity'] for n in pompe['notes']}
        assert all(vel[b]>vel[b-1] for b in range(1,16,2)) and all(vel[b-.125]<=vel[b] for b in range(2,16,2))
        # Across a change the upstroke is of the chord it leads into, as the downstroke after it: in two bars, C6 then
        # G6, the one before bar 2 (at 3.875) is G6's while C6 still sounds.  The times alone were checked (GPT's
        # re-review of 0.5).
        two=blocks.accompaniment(['C6','G6'],[4,4],seed=3,figure='pompe',complexity=0,intensity=.6,low=48,high=72,voices=4,push='none')
        at=lambda t:sorted(n['pitch'] for n in two['notes'] if round(n['on'],3)==t);pcs=lambda t:{p%12 for p in at(t)}
        c6,g6=(set(blocks.parse(c)['pcs']) for c in ('C6','G6'))
        assert sorted({round(n['on'],3) for n in two['notes']}-set(range(8)))==[1.875,3.875,5.875],on(two)
        assert all(len(at(g))==4 and at(g)==at(g+.125) for g in (1.875,3.875,5.875)),[at(g) for g in (1.875,3.875,5.875)]
        assert pcs(1.875)==c6 and pcs(3.875)==pcs(5.875)==g6!=c6 and pcs(3.0)==c6,(pcs(1.875),pcs(3.875),pcs(5.875))
        batida=acc('batida')
        assert on(batida)==sorted(4*k+o for k in range(4) for o in (0,1,2.5)) and all(n['duration']==.5 for n in batida['notes'])
        rejects(lambda:blocks.accompaniment(chords,[6,8],seed=3,figure='batida',complexity=0,intensity=.6,low=48,high=72,voices=3,push='none'))
        line=[{'on':float(i),'duration':.5,'pitch':(36,38,36,41)[i%4],'velocity':100} for i in range(8)]
        none,all_=blocks.slides(line,0,1),blocks.slides(line,1,1)
        assert [n['duration'] for n in none]==[.5]*8 and all(a['on']+a['duration']>b['on'] for a,b in zip(all_,all_[1:]) if a['pitch']!=b['pitch'])
        assert blocks.slides(line,.5,9)==blocks.slides(line,.5,9)
        struck=[{'on':0,'duration':.5,'pitch':36,'velocity':90},{'on':0,'duration':.5,'pitch':43,'velocity':90},{'on':1,'duration':.5,'pitch':40,'velocity':90}]
        assert [n['duration'] for n in blocks.slides(struck,1,20261109)]==[.5,.5,.5]  # a chord's last note was held on (E05)
        assert blocks.articulate([{'on':0,'duration':1/960,'pitch':60,'velocity':80}],.25)[0]['duration']>=1/960  # E06
        chord=[{'on':0,'duration':1,'pitch':60,'velocity':80},{'on':0,'duration':1,'pitch':64,'velocity':80},{'on':1,'duration':2,'pitch':62,'velocity':80}]
        art=blocks.articulate(chord,.5)
        assert [n['duration'] for n in art]==[.5,.5,1.0] and blocks.articulate(chord,1)[0]['duration']==1
        rejects(lambda:blocks.articulate(chord,0));rejects(lambda:blocks.slides(line,2,1))
        return {'blast':steps(blast,38),'pompe_notes':len(pompe['notes']),'batida':on(batida)[:3]}
    def meter_arches():
        from musiclib.expression import phrase_positions
        t={'notes':[{'id':str(b),'on':b,'duration':1} for b in (0,3,6,9,12,15,16)]}
        pos=phrase_positions(t,[{'start_bar':0},{'start_bar':4}],False,3.0)
        assert pos['12']==0 and pos['0']==0 and abs(pos['9']-.75)<1e-9,pos
        return {'three_four_section_starts_at_beat':12}
    def builder_keeps_the_books_and_start_writes_a_valid_piece():
        # 0.8 steps 2.9 and 2.5 (design-0.8.md): musiclib.builder places notes by bar and beat (from 1, quarter-note
        # beats) with stable ids and their performance entries, checks each against its part's keys as it is written,
        # takes a part's bank, program and keys from the configured banks, and saves only a valid project; `studio.py
        # start` writes a compose.py using it and the song.json it writes, refusing a preset it cannot name before
        # anything is written.  It composes nothing: the notes here are the check's.
        import subprocess,sys
        from musiclib.builder import Song,pitch_of
        # 0.9 step 5 (real use, 2026-11-18): an agent's script printed the chord qualities' names, one of which a
        # Traditional Chinese Windows console cannot encode, and stopped on it.  A script that writes a song with the
        # builder prints such a character as an escape, as the skill's own commands do.
        import os
        script=work/'console.py';scripts=Path(__file__).resolve().parents[1]
        script.write_text(f"import sys\nsys.path.insert(0, {str(scripts)!r})\nfrom musiclib.builder import Song\nSong('console', bars=1)\nprint('C\u00f87 and \u5586')\n",encoding='utf-8')
        env={k:v for k,v in os.environ.items() if k not in ('PYTHONUTF8','PYTHONIOENCODING')};env['PYTHONIOENCODING']='cp950'
        said=subprocess.run([sys.executable,'-X','utf8=0',str(script)],capture_output=True,env=env)
        assert said.returncode==0 and b'C\\xf87 and \\u5586' in said.stdout,(said.returncode,said.stdout,said.stderr[-300:])
        # and a script whose output is not a console's stream is left as it is: one replaced by an object that cannot
        # be set (a notebook's, a test's capture), a closed one, none at all (a program without a console)
        import io
        closed=io.TextIOWrapper(io.BytesIO(),encoding='ascii');closed.close();kept=sys.stdout,sys.stderr
        for stream in (io.StringIO(),closed,None):
            sys.stdout=stream
            try:Song('console',bars=1)
            finally:sys.stdout,sys.stderr=kept
        assert [pitch_of(x,'t') for x in ('C4','Bb2','F#3','c-1','G9',60)]==[60,46,54,0,127,60]
        for bad in ('H2','C10','G#9','Cb-1',128,True,4.5):rejects(lambda:pitch_of(bad,'t'))
        def song():
            s=Song('Books',bars=4,tempo=90,meter=(6,8));s.section('a',2,'first').section('b',2)
            lead=s.part('lead','melody',engine='additive',keys=('C4','C6'),mix={'level_dbfs':-20})
            kit=s.part('kit','drums',keys=(35,59))
            return s,lead,kit
        s,lead,kit=song()
        ids=[lead.note(1,1,'E4',1,velocity=70,phrase='hook'),lead.note(1,2.5,64,0.5),lead.note(2,1,'G4',1.5)]+kit.chord(1,1,[36,42],0.5)
        assert ids==['lead_b001_t000_p64','lead_b001_t072_p64','lead_b002_t000_p67','kit_b001_t000_p36','kit_b001_t000_p42'],ids
        t=s.project['tracks'][0];assert [n['on'] for n in t['notes']]==[0,1.5,3] and t['notes'][0]['phrase']=='hook' and t['performance']['notes'][ids[0]]=={'velocity':70}
        assert s.project['tracks'][1]['drums'] is True and s.project['sections'][1]['start_bar']==2 and s.beats_per_bar==3
        s2,lead2,_=song();assert lead2.note(1,1,'E4',1)==ids[0] and lead2.note(1,1,'E4',.5)==ids[0]+'_2'   # the same id run after run; a second at its place gets _2
        for args,words in (((1,1,'B3',1),'B3 (MIDI 59) is outside C4-C6'),((5,1,60,1),'bars 1 to 4'),((1,4,60,1),'beats 1 to under 4'),((0,1,60,1),'bars 1 to 4')):
            try:lead.note(*args);raise AssertionError(f'taken: {args}')
            except ValueError as e:assert words in str(e) and 'lead bar' in str(e),(args,str(e))
        rejects(lambda:s.part('lead','melody'))   # one id a part
        summary=s.save(work/'books.json');assert summary['notes']==5 and json.loads((work/'books.json').read_text(encoding='utf-8'))['tracks'][0]['id']=='lead'
        bad,_,_=song();bad.project['clock']['bars']=3;rejects(lambda:bad.save(work/'books_bad.json'));assert not (work/'books_bad.json').exists()
        # a part's preset found in the configured banks (a bank the builder makes: one viola over G3-G4)
        import soundbank as sb
        src=work/'books_src';src.mkdir();tt=np.arange(48000)/48000;x=(np.sin(2*np.pi*261.63*tt)*np.minimum(1,(1-tt)/.1)*.3).astype(np.float32)
        sb.write_float_wav(src/'v_C4.wav',np.stack([x,x],1),48000)
        sb.build({'name':'books','presets':[{'name':'Books Viola','program':41,'layers':[{'dir':'.','template':'v_{note}.wav','dynamics':['default'],
                  'velocity':{'default':[1,127]},'keys':[55,67],'pitch_check':False}]}]},src,work/'books.sf2')
        save_json(work/'books_config.json',{'soundfont':{'path':str(work/'books.sf2'),'sha256':file_hash(work/'books.sf2')}})
        c=Song('Books',bars=2,config=work/'books_config.json');c.section('a',2)
        for found in (c.part('viola','harmony','default 0:41'),c.part('viola2','harmony','viola')):
            assert found.track['patch']=={'bank':0,'program':41} and 'soundfont' not in found.track and found.track['range']==[55,67],found.track
        rejects(lambda:c.part('x','harmony','default 0:42'));rejects(lambda:Song('n',bars=1).part('y','bass','viola'))
        try:c.part('viola3','harmony','viola').note(1,1,'C5',1);raise AssertionError('C5 taken on G3-G4')
        except ValueError as e:assert 'C5 (MIDI 72) has no sample in default 0:41, whose samples cover G3-G4' in str(e),str(e)
        # The Astra review of step 2: the export carries the preset's program (patch is the render's alone); a preset's
        # keys are the ones it has samples for, holes too; a kit at bank 128 plays on the drum channel whatever its role;
        # the meter is checked before it divides; an id may be given, and a note's place is not a field.
        from musiclib import midi,sf2
        e=Song('E',bars=1,config=work/'books_config.json');e.section('a',1);e.part('viola','harmony','default 0:41').note(1,1,'G3',1)
        e.save(work/'books_export.json');assert [r['program'] for r in midi.write(e.project,work/'books_export.mid')]==[41]
        g=Song('G',bars=1,config=work/'books_config.json');g.section('a',1);given=g.part('viola','harmony','default 0:41',program=71)   # a program the script gives stays
        zero=g.part('violb','harmony','default 0:41',program=0);given.note(1,1,'G3',1);zero.note(1,1,'G3',1);g.save(work/'books_given.json')
        assert given.track['program']==71 and zero.track['program']==0 and given.track['patch']=={'bank':0,'program':41},given.track
        assert [r['program'] for r in midi.write(g.project,work/'books_given.mid')]==[71,0]   # the export's: the authored ones
        tone=(np.sin(2*np.pi*440*np.arange(4800)/48000)*.4).astype(np.float32)
        # (a program 0 over 48-72, and one that sounds C4 only at velocities 90-127, for start's defaults below)
        sf2.write(work/'holes.sf2','holes',[{'name':'a','data':tone,'rate':48000,'root':60},{'name':'b','data':tone,'rate':48000,'root':72},{'name':'k','data':tone,'rate':48000,'root':36}],
                  [{'name':'gaps','zones':[{'gens':{43:(60,60)},'sample':0},{'gens':{43:(72,72)},'sample':1}]},{'name':'kit','zones':[{'gens':{43:(36,36)},'sample':2}]},
                   {'name':'zero','zones':[{'gens':{43:(48,72)},'sample':0}]},{'name':'loud','zones':[{'gens':{43:(60,60),44:(90,127)},'sample':0}]}],
                  [{'name':'Holes','bank':0,'program':11,'zones':[{'gens':{},'instrument':0}]},{'name':'Kit','bank':128,'program':0,'zones':[{'gens':{},'instrument':1}]},
                   {'name':'Zero','bank':0,'program':0,'zones':[{'gens':{},'instrument':2}]},{'name':'Loud','bank':0,'program':12,'zones':[{'gens':{},'instrument':3}]}])
        entry=lambda f:{'path':str(work/f),'sha256':file_hash(work/f)}
        save_json(work/'holes_config.json',{'soundfont':entry('books.sf2'),'soundfonts':{'holes':entry('holes.sf2')}})
        save_json(work/'start_config.json',{'soundfont':entry('holes.sf2'),'soundfonts':{'books':entry('books.sf2'),'holes':entry('holes.sf2')}})
        h=Song('H',bars=1,config=work/'holes_config.json');h.section('a',1);gaps=h.part('gaps','harmony','holes 0:11')
        assert gaps.keys==[60,72] and gaps.track['range']==[60,72] and gaps.track['soundfont']=='holes' and gaps.track['program']==11,(gaps.keys,gaps.track)
        try:gaps.note(1,1,66,1);raise AssertionError('a key with no sample taken')
        except ValueError as e:assert 'F#4 (MIDI 66) has no sample in holes 0:11, whose samples cover C4, C5' in str(e),str(e)
        gaps.note(1,1,72,1);perc=h.part('perc','percussion','holes 128:0');assert perc.track.get('drums') is True and perc.keys==[36],perc.track
        # The whole review of 0.8: a part's key_map moves a written key to the key that plays (a kit not on GM keys), so
        # a note is checked on the key it reaches: a key mapped onto a sample is taken, one mapped off them refused, and
        # a key_map of the wrong kind refused before it is used (a number for a key stopped validate with a TypeError)
        moved=h.part('moved','harmony','holes 0:11',keys=(48,48),key_map={'48':60});moved.note(1,1,48,1)
        off=h.part('off','harmony','holes 0:11',key_map={'60':66})
        try:off.note(1,1,60,1);raise AssertionError('a key mapped onto no sample taken')
        except ValueError as e:assert 'plays key 66 through the part\'s key_map, which has no sample in holes 0:11; the keys that reach one are C5' in str(e),str(e)
        for bad in ({35:36},{'35':36.0},{'35':128},['35'],{'035':36}):   # each onto the kit's one sample, or past the keys: only its kind refuses it
            try:h.part('bad','percussion','holes 128:0',key_map=bad);raise AssertionError(f'key_map {bad!r} taken')
            except ValueError as e:assert 'key_map' in str(e),(bad,str(e))
        # a key with a leading zero ("048") is refused by validate and the builder alike: the render looks a note up as
        # "48" and left it unmapped, so the builder took a key no sample played (the review of 0.8.0)
        for key,words in ((36,'key_map key 36: a MIDI pitch written as text without leading zeros'),('048',"key_map key '048': a MIDI pitch")):
            numbered=copy.deepcopy(h.project);validate(copy.deepcopy(numbered));numbered['tracks'][-1]['key_map']={key:60}
            try:validate(numbered);raise AssertionError(f'a key_map key {key!r} taken')
            except ValueError as e:assert words in str(e),str(e)
        try:h.part('padded','harmony','holes 0:11',keys=(48,48),key_map={'048':60});raise AssertionError('a key with a leading zero taken by the builder')
        except ValueError as e:assert "key_map key '048'" in str(e),str(e)
        # malformed arguments are refused, not a raw error or a value left out (the review of 0.8.0)
        rejects(lambda:Song('k',bars=1).part('k1','melody',keys=(60,)));rejects(lambda:Song('k',bars=1).part('k2','melody',keys=(60,72,84)))
        _,lead4,_=song()
        for bad in (None,True,'2'):rejects(lambda:lead4.note(1,bad,'E4',1))
        # 0.9 step 4: the chords are written once, by bar and beat as notes are (from 1), and every part reads the
        # same list: song.harmony writes project['harmony'] (whose beat is an offset from 0: a trap for a script that
        # wrote it by hand), song.changes() gives each chord with how long it lasts, song.chord_at the chord
        # sounding at a place.  A symbol review cannot read is refused where it is written, not listed after a review.
        h=Song('chords',bars=4,meter=(3,4));h.harmony(1,1,'Dm7').harmony(3,1,'Cmaj7').harmony(2,2.5,'G7/B')
        assert h.project['harmony']==[{'bar':1,'symbol':'Dm7'},{'bar':2,'beat':1.5,'symbol':'G7/B'},{'bar':3,'symbol':'Cmaj7'}],h.project['harmony']
        assert h.changes()==[(1,1,'Dm7',4.5),(2,2.5,'G7/B',1.5),(3,1,'Cmaj7',6)],h.changes()
        assert [h.chord_at(b,x) for b,x in ((1,1),(2,2),(2,2.5),(2,3.5),(4,3))]==['Dm7','Dm7','G7/B','G7/B','Cmaj7']
        e=Song('none yet',bars=2);e.harmony(2,1,'C');assert e.chord_at(1,4) is None and e.changes()==[(2,1,'C',4)] and Song('x',bars=1).changes()==[]
        for bad,words in ((lambda:h.harmony(1,1,'F'),'a chord is written at bar 1 beat 1 already'),(lambda:h.harmony(1,1,'Hm'),'is no chord symbol'),
                          (lambda:h.harmony(1,1,'Cmaj13#11b9'),'is no chord symbol'),(lambda:h.harmony(5,1,'C'),'bars 1 to 4'),(lambda:h.harmony(1,4,'C'),'beats 1 up to'),
                          (lambda:h.harmony(1,0,'C'),'beats 1 up to'),(lambda:h.harmony(1,1,7),'is no chord symbol'),(lambda:h.chord_at(5,1),'bars 1 to 4')):
            try:bad();raise AssertionError(f'taken: {words}')
            except ValueError as err:assert words in str(err),(words,str(err))
        from musiclib import harmony as hm
        assert [c['symbol'] for _,c in hm.timeline(h.project,3)]==['Dm7','G7/B','Cmaj7'] and [b for b,_ in hm.timeline(h.project,3)]==[0,4.5,6]
        # The review of step 4: a list written by hand beside the builder's.  Out of order, it is read in order, as
        # review reads it (a chord came back lasting -4 beats); an entry review reads otherwise than its symbol says
        # (transpose_semitones) is refused, not given back as the symbol that does not sound; an entry that is no
        # chord entry is named, not a KeyError; and what song.harmony writes is what validate takes (a beat within a
        # tick of the next bar, a symbol padded to 41 characters, passed the builder and stopped the save).
        m=Song('by hand',bars=2);m.project['harmony']=[{'bar':2,'symbol':'G'},{'bar':1,'symbol':'C'}]
        assert m.changes()==[(1,1,'C',4),(2,1,'G',4)] and m.chord_at(2,1)=='G' and m.chord_at(1,4)=='C',m.changes()
        m.harmony(1,3,'F');assert [x[2] for x in m.changes()]==['C','F','G'] and m.project['harmony'][0]['symbol']=='C'
        w=Song('odd',bars=2);w.project['harmony']=[{'bar':1,'symbol':'C7alt'}];assert w.changes()==[(1,1,'C7alt',8)],'a symbol written by hand comes back as written'
        for entries,words in (([{'bar':1,'symbol':'C/E','transpose_semitones':2}],'transpose_semitones'),([{'symbol':'C'}],'no chord entry'),(['C'],'no chord entry'),([{'bar':1,'beat':'2','symbol':'C'}],'no chord entry')):
            for call in (lambda s:s.changes(),lambda s:s.chord_at(1,1),lambda s:s.harmony(2,1,'G')):
                s=Song('bad',bars=2);s.project['harmony']=copy.deepcopy(entries)
                try:call(s);raise AssertionError(f'read: {entries}')
                except ValueError as err:assert words in str(err),(entries,str(err))
        edge=Song('edge',bars=1)
        try:edge.harmony(1,4.9995,'C');raise AssertionError('a beat past the last tick of the bar taken')
        except ValueError as err:assert 'beats 1 up to' in str(err),str(err)
        edge.harmony(1,4.5,' Am ').harmony(1,5-1/960,'C'+' '*40);assert [x['symbol'] for x in edge.project['harmony']]==['Am','C'] and edge.chord_at(1,4.75)=='Am'   # stored without the spaces round it
        edge.section('a',1);edge.part('p','harmony').note(1,1,'C4',1);validate(edge.project)
        # the second review: `harmony: null` is a project validate takes, and the first chord written into it was an
        # AttributeError; an entry outside the piece came back lasting -4 beats; and a place a note may be written
        # on (within a tick of the next bar) could not be asked for
        nul=Song('null',bars=1);nul.project['harmony']=None;nul.harmony(1,2,'C');assert nul.project['harmony']==[{'bar':1,'beat':1,'symbol':'C'}] and nul.chord_at(1,4.999)=='C'
        far=Song('far',bars=2);far.project['harmony']=[{'bar':1,'symbol':'C'},{'bar':4,'symbol':'G'}]
        for call in (lambda:far.changes(),lambda:far.chord_at(1,1),lambda:far.harmony(2,1,'F')):
            try:call();raise AssertionError('a chord outside the piece read')
            except ValueError as err:assert 'outside the piece' in str(err),str(err)
        # the first save of a song.json makes it only while the name stays free: one put there meanwhile is left as it
        # is (start's first run replaced it: the review of 0.8.0); a save over the script's own earlier one replaces it
        import musiclib.builder as builder_mod
        s5,_,_=song();s5.save(work/'books_twice.json');s5.save(work/'books_twice.json')
        real_occupied=builder_mod.files.occupied
        def appears(p):
            if Path(p).name!='books_race.json':return real_occupied(p)
            Path(p).write_text('theirs',encoding='utf-8');return False
        builder_mod.files.occupied=appears
        try:
            try:s5.save(work/'books_race.json');raise AssertionError('a song.json made meanwhile replaced')
            except ValueError as e:assert 'made by something else while the song was saved' in str(e),str(e)
        finally:builder_mod.files.occupied=real_occupied
        assert (work/'books_race.json').read_text(encoding='utf-8')=='theirs'
        rejects(lambda:Song('m',bars=1,meter=(4,0)));rejects(lambda:Song('m',bars=1,meter=(4,6)))
        s3,lead3,_=song();assert lead3.note(1,1,'E4',1,id='hook')=='hook' and 'hook' in s3.project['tracks'][0]['performance']['notes'] and s3.project['tracks'][0]['notes'][-1]['id']=='hook'
        for given,words in (('hook','is taken by another note of this part'),(7,'is no text'),('','is no text')):   # an id this part has, or none: each named
            try:lead3.note(1,2,'E4',1,id=given);raise AssertionError(f'id {given!r} taken')
            except ValueError as e:assert words in str(e),(given,str(e))
        for field in ('on','duration'):rejects(lambda:lead3.note(1,2,'E4',1,**{field:0}))
        def start(*a):
            return subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'start',*map(str,a)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        title='Books """1""" \\N'   # quotes and a backslash written into compose.py as they are
        r=start(work/'books_piece','--title',title,'--section','a:2','--section','b:2','--part','lead melody','--part','kit drums','--part','viola harmony viola','--config',work/'start_config.json')
        assert r.returncode==0 and (work/'books_piece'/'compose.py').is_file(),r.stderr[-400:]
        made=json.loads((work/'books_piece'/'song.json').read_text(encoding='utf-8'));validate(made)
        notes={t['id']:[n['pitch'] for n in t['notes']] for t in made['tracks']}
        assert made['title']==title and made['mix']=={'chain':'bus','rules':2,'target_lufs':-14} and notes=={'lead':[60],'kit':[36],'viola':[61]} and made['clock']['bars']==4,(made['mix'],notes)
        # The review of 0.8.0: with a configuration, a part that names no instrument plays the default bank's program 0
        # (a drum part its kit), written out and checked; compose.py names the skill and the configuration from the
        # user's home where they lie there (it named the whole path, the account with it)
        text=(work/'books_piece'/'compose.py').read_text(encoding='utf-8')
        # the skeleton shows where the chords go, written out as a comment: the piece start saves has none yet
        assert "# song.harmony(1, 1, 'Cmaj7')" in text and 'song.changes()' in text and 'harmony' not in json.loads((work/'books_piece'/'song.json').read_text(encoding='utf-8'))
        # the third review: a beat reached by adding thirds (4.999999999999999) is a place a note takes, and the
        # chord there can be asked for; the last tick of a bar of 1/4 can be written
        beat=1.0
        for _ in range(12):beat+=1/3
        assert nul.chord_at(1,beat)=='C' and Song('tick',bars=1,meter=(1,4)).harmony(1,1+959/960,'C').project['harmony'][0]['beat']<=1-1/960
        for past in (5,5.5,0.999):   # and the next bar's first beat, or one before the bar, is no place in this bar to ask about
            try:nul.chord_at(1,past);raise AssertionError(past)
            except ValueError as e:assert 'beat' in str(e),e
        assert "the pitched parts' notes" in text and "every part's notes" not in text,'the skeleton says what review reads (the second review)'
        assert "song.part('lead', 'melody', 'default 0:0')" in text and "song.part('kit', 'drums', 'default 128:0')" in text,text
        home=Path.home().resolve()
        assert str(home) not in text and home.as_posix() not in text,'compose.py names the home folder'
        if SCRIPTS.resolve().is_relative_to(home):assert 'SKILL = Path.home() / ' in text,text[:900]
        from musiclib.starter import spelled   # wherever this skill lies: a path under the home is named from it, another as it is
        assert spelled(home/'skills'/'x')=="Path.home() / 'skills/x'" and spelled(home.parent.parent/'x').startswith("Path('"),spelled(home/'skills'/'x')
        # compose.py says where the project's other fields go and the mix a new song starts with, as the builder makes
        # it (the walkthrough of 0.8.0 found both only in the builder's docstrings)
        assert 'written into song.project before the save' in text and f"song.project['mix'] starts as {made['mix']!r}." in text,text[-700:]
        # a preset that sounds its key only at velocities 90-127 gets its placeholder at 90, not a silent 64; a part that
        # names no instrument where the default bank has no program 0 is refused before anything is written
        r=start(work/'books_loud','--title','L','--section','a:1','--part','lead melody default 0:12','--config',work/'start_config.json')
        loud=json.loads((work/'books_loud'/'song.json').read_text(encoding='utf-8')) if r.returncode==0 else r.stderr[-300:]
        assert isinstance(loud,dict) and [e['velocity'] for e in loud['tracks'][0]['performance']['notes'].values()]==[90],loud
        r=start(work/'books_nodefault','--title','N','--section','a:1','--part','lead melody','--config',work/'books_config.json')
        assert r.returncode==2 and 'names no instrument' in r.stderr and not (work/'books_nodefault').exists(),r.stderr[-300:]
        # a folder holding the piece's brief and words (SKILL.md's steps 1 and 2 come first) is written into, keeping them;
        # one holding a compose.py or a song.json is refused (a folder that was there was refused: the review of 0.8.0)
        kept=work/'books_kept';kept.mkdir();(kept/'brief.md').write_text('the brief',encoding='utf-8');save_json(kept/'association.json',{'words':['a']})
        r=start(kept,'--title','K','--section','a:1','--part','lead melody','--config',work/'start_config.json')
        assert r.returncode==0 and (kept/'song.json').is_file() and (kept/'brief.md').read_text(encoding='utf-8')=='the brief',r.stderr[-300:]
        for name in ('compose.py','song.json'):
            other=work/f'books_has_{name[:-3]}';other.mkdir();(other/name).write_text('mine',encoding='utf-8')
            r=start(other,'--title','K','--section','a:1','--part','lead melody','--config',work/'start_config.json')
            assert r.returncode==2 and 'exists' in r.stderr and (other/name).read_text(encoding='utf-8')=='mine',(name,r.stderr[-300:])
        import musiclib.starter as starter
        real=starter.script;starter.script=lambda *a:real(*a)+'raise SystemExit("stopped here")\n'   # a compose.py that stops is reported
        try:starter.start(work/'books_stops','B',['a:2'],['lead melody']);raise AssertionError('a stopped compose.py reported as written')
        except ValueError as e:assert 'compose.py was written, but it stopped: stopped here' in str(e) and 'running compose.py would replace it' in str(e),str(e)
        finally:starter.script=real
        # that one stopped after its save, so its song.json is there and running it again replaces that file, as the message
        # says; one that stops before its save leaves none, and is told to fix the line and run it (GPT Pro's second review)
        starter.script=lambda *a:real(*a).replace('song.save(','raise SystemExit("stopped here"); song.save(')
        try:starter.start(work/'books_stops_early','B',['a:2'],['lead melody']);raise AssertionError('a compose.py stopped before its save reported as written')
        except ValueError as e:assert 'stopped here. Fix that line of the script, then run it: python compose.py' in str(e),str(e)
        finally:starter.script=real
        assert not (work/'books_stops_early'/'song.json').exists()
        # a compose.py put in the new folder while start writes its own is left as it is (it was written over: the whole review)
        def theirs(*a):
            (work/'books_race'/'compose.py').write_text('# theirs\n',encoding='utf-8');return real(*a)
        starter.script=theirs
        try:starter.start(work/'books_race','B',['a:2'],['lead melody']);raise AssertionError('a compose.py made meanwhile written over')
        except ValueError as e:assert 'made by something else while start wrote it' in str(e),str(e)
        finally:starter.script=real
        assert (work/'books_race'/'compose.py').read_text(encoding='utf-8')=='# theirs\n' and not (work/'books_race'/'song.json').exists()
        # a song.json put there after start looked, before compose.py saves, is left as it is: start's first run replaces
        # nothing (it was taken for the script's own and replaced: the Astra review of the fixes for 0.8.0)
        import contextlib
        real_staged=starter.files.staged
        @contextlib.contextmanager
        def then_theirs(path,*a,**k):
            with real_staged(path,*a,**k) as f:yield f
            (Path(path).parent/'song.json').write_text('theirs',encoding='utf-8')
        starter.files.staged=then_theirs
        try:starter.start(work/'books_late','B',['a:2'],['lead melody']);raise AssertionError('a song.json made after start looked replaced')
        except ValueError as e:
            # and start does not tell the user to run compose.py, whose save would replace it (following that instruction
            # replaced it: GPT Pro's second review of 0.8.0)
            told=str(e);assert 'made by something else while the song was saved' in told and 'running compose.py would replace it' in told and 'then run it' not in told,told
        finally:starter.files.staged=real_staged
        assert (work/'books_late'/'song.json').read_text(encoding='utf-8')=='theirs'
        r=start(work/'books_piece','--title','B','--section','a:2','--part','lead melody');assert r.returncode==2 and 'exists' in r.stderr,r.stderr[-300:]
        # from the working folder: a relative folder, and one named as Python's -c option (both ran another script, or
        # code, before compose.py was given by its absolute path after "--"); a meter of 3/16 (its placeholder a bar
        # long), a tempo kept to the digit, the placeholder of a preset with holes on a key it has
        def start_in(*a):
            return subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'start',*map(str,a)],cwd=work,capture_output=True,text=True,encoding='utf-8',errors='replace')
        for folder,args in (('books_rel',()),('-cprint(123)#',('--meter','3/16','--tempo','100.123456789'))):
            r=start_in('--title','R','--section','a:1','--part','lead melody','--part','gaps harmony holes 0:11','--config',work/'start_config.json',*args,'--',folder)
            made=json.loads((work/folder/'song.json').read_text(encoding='utf-8')) if r.returncode==0 else r.stderr[-300:]
            assert isinstance(made,dict) and [n['pitch'] for t in made['tracks'] for n in t['notes']]==[60,60],(folder,made)
        assert made['clock']['tempo']==[[0,100.123456789]] and [n['duration'] for t in made['tracks'] for n in t['notes']]==[.75,.75],made['clock']
        r=start_in('--title','M','--section','a:1','--part','lead melody','--meter','4/0','--','books_meter');assert r.returncode==2 and 'meter beat unit' in r.stderr and not (work/'books_meter').exists(),r.stderr[-300:]
        refused=(('a:x',['lead melody'],'ID:BARS'),('a:2',['lead melody viola'],'give --config'),('a:2',['class melody'],'Python keyword'),
                 ('a:2',['Lead melody'],'Invalid or duplicate track id'),('a:2',['lead melody','lead bass'],'exists already'),
                 ('a:2',['lead melody default 0:42'],'finds no preset'))
        for i,(section,parts,words) in enumerate(refused):   # each refused before its folder is made
            r=start(work/f'books_r{i}','--title','B','--section',section,*[x for p in parts for x in ('--part',p)],*(('--config',work/'start_config.json') if i>2 else ()))
            assert r.returncode==2 and words in r.stderr and not (work/f'books_r{i}').exists(),(i,r.stderr[-300:])
        return {'ids':ids[:2],'start':'compose.py and a valid song.json','refused':['a used folder']+[w for _,_,w in refused]}
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
    def chords_few_voices_and_parts_not_written_yet():
        # 0.9.2 (design-0.9.2.md, T2, T6, T8, M2): what the real pieces of 0.9.1 stumbled on in writing a score.
        from musiclib.analysis import doublings,leads_over
        from musiclib.harmony import parse
        from musiclib.review import review
        from musiclib.voicing import chord_tones,voice_lead
        from musiclib import views
        for s,iv in (('Cmaj9#11',{0,4,7,11,2,6}),('C13sus',{0,5,7,10,2,9}),('C13sus4',{0,5,7,10,2,9}),('Cmaj13#11',{0,4,7,11,2,6,9}),
                     ('C6/9#11',{0,4,7,9,2,6}),('C69#11',{0,4,7,9,2,6}),('C9#11',{0,4,7,10,2,6})):
            assert parse(s)['pcs']==iv and parse(s+'/E')['bass']==4,s
        # Too few voices keep what names the chord: the third, then the seventh; the root first where it is to be kept.
        for s,voices,want in (('Fm7',1,{8}),('Ddim7',2,{5,11}),('Bm7b5',2,{2,9}),('C7sus4',2,{5,10}),('C7#9',2,{4,10}),('C13',2,{4,10})):
            got=voice_lead([s],voices=voices,thin=True);assert len(got[0])==voices and {x%12 for x in got[0]}==want,(s,got)
            if s!='C7sus4':rejects(lambda:voice_lead([s],voices=voices))   # by default still refused: a script may rest on that
        assert voice_lead(['Cm7'],voices=2)==voice_lead(['Cm7'],voices=2,thin=True) and {x%12 for x in voice_lead(['Cm7'],voices=2)[0]}=={3,10}   # what worked stays as it was
        assert {0,3}=={x%12 for x in chord_tones('Cm7',2,keep_root=True,thin=True)},chord_tones('Cm7',2,keep_root=True,thin=True)
        assert len(voice_lead(['Cmaj13#11','Fm7','Ddim7'],voices=3,thin=True))==3   # a progression through them, each with its three voices
        from musiclib.views import KIND_OF
        assert all(q in KIND_OF for q in ('9#11','maj9#11','maj13#11','6/9#11','69#11','13sus','13sus4')),'each chord quality has its kind in the score views'
        rejects(lambda:chord_tones('C',0))
        # A span is read by the lead of the sections it lies in, across a change of lead too.
        led=example();melody={t['id'] for t in led['tracks'] if t.get('role')=='melody'};assert melody
        led['plan']={'identity':'x','sections':[{'section':'question','leads':'piano'},{'section':'answer','leads':'bass'}]}
        assert leads_over(led,0,8)=={'piano'} and leads_over(led,8,16)=={'bass'} and leads_over(led,4,12)=={'piano','bass'},leads_over(led,4,12)
        led['plan']['sections'].pop();assert leads_over(led,4,12)=={'piano'}|melody and leads_over(example(),4,12)==melody
        # A lead that holds a note across a span sounds there though it starts nothing; a part's name is a whole name; no lead is no lead.
        line_of=lambda name,role,*notes:{'id':name,'role':role,'notes':[{'on':a,'duration':d,'pitch':60} for a,d in notes]}
        tiny={'tracks':[line_of('sax','melody',(0,1),(1,1)),line_of('alto_sax','harmony',(0,4))]}
        assert doublings(tiny,1.5,3,leads='alto_sax')==['alto_sax'] and doublings(tiny,0,1,leads='alto_sax')==['alto_sax'] and doublings(tiny,0,1,leads=None)==['sax'],doublings(tiny,0,1,leads='alto_sax')
        gated=example();kept=next(t for t in gated['tracks'] if t.get('role')!='melody' and not t.get('drums'));ticks=Clock(gated)
        kept['notes']=[{'id':'h0','on':0.0,'duration':4,'pitch':48}];kept['performance']['notes']={'h0':{'velocity':80,'gate':1.5}}
        assert kept['id'] in doublings(gated,4.5,5.5,leads=kept['id'],clock=ticks) and kept['id'] not in doublings(gated,6.5,7,leads=kept['id'],clock=ticks),'by the note as played'
        # A part the plan names and the project does not have yet is one question, whatever it was planned to do.
        p=example();clock=Clock(p);first,second=p['sections'][0]['id'],p['sections'][1]['id']
        real=sorted({r['section']:r['parts'] for r in views.parts_by_section(p,clock)}[second])
        p['plan']={'identity':'x','high_point':{'section':second,'means':'register'},
                   'sections':[{'section':second,'sounds':real+['ghost'],'leads':'ghost2','answers':['ghost4'],'register':{'ghost3':'higher'}}]}
        asked=lambda name:review(p,work/name)
        r=asked('review_unwritten');plans=[q for q in r['questions'] if q['id'].startswith('plan')]
        missing='plan.unwritten:ghost+ghost2+ghost3+ghost4'
        assert [q['id'] for q in plans]==[missing],plans
        assert all(f'{g} ({second})' in plans[0]['text'] for g in ('ghost','ghost2','ghost3','ghost4')),plans[0]['text']
        assert r['plan']['differences']==4 and r['plan']['kept']==0,r['plan']   # still counted as not held
        # A real difference beside them keeps its own question, and the parts not written stay together in theirs.
        p['plan']['sections'][0]['sounds']=real[1:]+['ghost']
        r=asked('review_unwritten2');ids=[q['id'] for q in r['questions'] if q['id'].startswith('plan')]
        assert ids==[f'plan:{second}',missing],ids
        text=next(q['text'] for q in r['questions'] if q['id']==f'plan:{second}')
        assert f'sounding and not in the plan: {real[0]}' in text and 'ghost' not in text,text
        p['plan']['sections'][0]['sounds']=real+['ghost'];p['decisions']=list(p.get('decisions') or [])+[f'{missing}: written next round']
        r=asked('review_unwritten3');assert not any(q['id'].startswith('plan') for q in r['questions']) and any(a['id']==missing for a in r['answered'])
        p['plan']['sections'][0]['answers']=['ghost4','ghost5'];r=asked('review_unwritten4')   # a decision on one set does not cover a part named later
        assert [q['id'] for q in r['questions'] if q['id'].startswith('plan')]==['plan.unwritten:ghost+ghost2+ghost3+ghost4+ghost5'],[q['id'] for q in r['questions']]
        # A long list of notes outside the chord keeps the foreground's: forty accompaniment notes came first by time, and hid the melody's.
        from musiclib.review import outside_chord
        o=example();o['clock']['bars']=max(o['clock']['bars'],40);o['sections'][-1]['bars']+=o['clock']['bars']-sum(x['bars'] for x in o['sections'])
        o['harmony']=[{'bar':1,'symbol':'C'}];ontop=next(t for t in o['tracks'] if t.get('role')=='melody');under=next(t for t in o['tracks'] if t.get('role') not in ('melody','countermelody','bass') and not t.get('drums') and t['engine']=='soundfont')
        def lay(t,beats,pitch):
            t['notes']=[{'id':f'{t["id"]}_{k}','on':float(b),'duration':1,'pitch':pitch+5*(k%2)} for k,b in enumerate(beats)];t['performance']['notes']={n['id']:{'velocity':80} for n in t['notes']}
        lay(under,range(0,60,2),61);lay(ontop,[100.0,102.0],61)
        for t in o['tracks']:
            if t not in (ontop,under):lay(t,[],60)
        found=outside_chord(o,Clock(o),limit=10);assert found['count']==32 and sum(x['track']==ontop['id'] for x in found['examples'])==2 and len(found['examples'])==10,found['count']
        assert [x['beat'] for x in found['examples']]==sorted(x['beat'] for x in found['examples'])
        # The additive engine's field `instrument` goes through song.part; on another engine an instrument is still refused.
        from musiclib.builder import Song
        made=Song('x',bars=1);voice=made.part('voice','melody',{'harmonics':4},engine='additive',keys=(48,72))
        assert voice.track['instrument']=={'harmonics':4} and voice.track['engine']=='additive',voice.track
        rejects(lambda:made.part('other','melody','violin',engine='additive'))
        # The two synthesizer parts as the script `start` writes shows them, written out and saved.
        from musiclib import starter
        shown=starter.script('x',[('a',1)],[('p','harmony',None,60,1,80)],100.0,(4,4),None)
        assert "engine='surge', surge={'preset': 'juno_60_strings'}" in shown and "synth={'preset': 'warm_pad'}" in shown,shown[:300]
        both=Song('y',bars=1);both.section('a',1);both.part('pad','harmony',engine='surge',surge={'preset':'juno_60_strings'}).note(1,1,60,1);both.part('syn','harmony',engine='synth',synth={'preset':'warm_pad'}).note(1,1,64,1)
        both.save(work/'two_synths.json');saved=json.loads((work/'two_synths.json').read_text(encoding='utf-8'))
        assert {t['id']:(t['engine'],(t.get('surge') or t.get('synth'))['preset']) for t in saved['tracks']}=={'pad':('surge','juno_60_strings'),'syn':('synth','warm_pad')},saved['tracks']
        # The melody group of a section starts from the part the plan says leads it.
        q=example();melody=next(t for t in q['tracks'] if t.get('role')=='melody' and t['notes']);other=next(t for t in q['tracks'] if t.get('role')!='melody' and t['notes'] and not t.get('drums'))
        span=(0,q['clock']['bars']*Clock(q).beats_per_bar)
        assert melody['id'] in doublings(q,*span) and other['id'] in doublings(q,*span,leads=other['id'])
        assert doublings(q,*span,leads='no_such_part')==doublings(q,*span)   # a plan's lead that does not play there leaves the melody parts
        return {'cases':18}
    found = {'chords_few_voices_and_parts_not_written_yet': chords_few_voices_and_parts_not_written_yet, 'performance_offset_moves_whole_part': offset_shift, 'strummed_chords_follow_the_stroke': strum, 'timing_keeps_to_the_beat_by_phase_correction': keeps_to_the_beat, 'rubato_slows_phrase_ends_and_the_close': rubato, 'swing_delays_off_beats_and_keeps_the_beat': swing, 'round_robins_bow_changes_and_portamento': variation_tools, 'phrasing_helpers_arch_swell_and_hold': phrasing_helpers, 'voicing_moves_smoothly_and_spaces_chords': voicing_helper, 'building_blocks_write_parts_from_the_pieces_settings': building_blocks, 'building_blocks_add_blasts_grids_skank_pompe_batida_slides': blocks_more, 'phrase_arches_follow_the_meter': meter_arches, 'builder_keeps_the_books_and_start_writes_a_valid_piece': builder_keeps_the_books_and_start_writes_a_valid_piece, 'swing_pairs_counted_from_each_bar_line': swing_pairs_counted_from_each_bar_line}
    return found
