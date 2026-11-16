"""selfcheck.py's checks of one area (0.8 step 1.8). Mixing and mastering: buses, the room and the stage, loudness, the limiter, the production tools, automation, range control, the master, analysis.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import copy
import json
import numpy as np
import shutil
from make_example import example
from musiclib import audio
from musiclib.model import Clock, file_hash, save_json, validate
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    config, rejects, work = S['config'], S['rejects'], S['work']
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
    def loudness_measures():
        # The measures analyze and the mix's rules of version 2 read (0.6): momentary and gated loudness by BS.1770,
        # the clarity of a response, and what a project writes of how much each part sounds.
        from musiclib import measure,mixbus
        R=audio.RATE;t=np.arange(10*R)/R;rng=np.random.default_rng(11)
        sine=np.zeros((len(t),2));sine[:,0]=np.sin(2*np.pi*997*t)
        m=measure.momentary(sine)  # a 0 dBFS 997 Hz sine in one channel reads -3.01 in every window, and over the whole
        assert len(m)==97 and float(np.abs(m+3.01).max())<.02 and abs(measure.integrated(sine)+3.01)<.02,(len(m),m[:3])
        # The block-wise filter against the two biquads run sample by sample, an oracle of another construction, over
        # more than one block; and against the whole-signal filter once that one's start is past (its transform lets
        # the end of a signal with no silence after it run round into the first milliseconds).
        x=rng.standard_normal((R+70000,2))*.1;blocks=measure.k_power(x)
        def biquad(signal,b,a):
            out=[0.0]*len(signal);x1=x2=y1=y2=0.0
            for i,v in enumerate(signal):
                y=b[0]*v+b[1]*x1+b[2]*x2-a[1]*y1-a[2]*y2;x2,x1,y2,y1=x1,v,y1,y;out[i]=y
            return out
        in_time=sum(np.square(biquad(biquad(x[:,c].tolist(),*measure.SHELF),*measure.RLB)) for c in range(2))
        whole=(measure.k_filter(x)**2).sum(axis=1)
        assert float(np.abs(blocks-in_time).max())<1e-5*float(in_time.max()),float(np.abs(blocks-in_time).max()/in_time.max())
        assert float(np.abs(blocks-whole)[4096:].max())<1e-5*float(whole.max()),float(np.abs(blocks-whole)[4096:].max()/whole.max())
        assert measure.k_power(x[:,0]).shape==(len(x),) and measure.integrated(np.zeros((R,2))) is None
        # Gating: 2 s of noise and 8 s of the same noise 30 dB lower.  The ungated mean falls with the quiet part; BS.1770's
        # relative gate (10 LU under the mean) leaves the quiet blocks out.  What passes is the 17 blocks inside the
        # loud part and the three that straddle its end, three quarters, a half and a quarter loud: 18.5 blocks' worth
        # of the loud power over 20 blocks, 0.34 LU under the loud part measured alone.
        loud=rng.standard_normal((2*R,2))*.2;quiet=rng.standard_normal((8*R,2))*.2*10**(-30/20)
        both=np.concatenate([loud,quiet]);alone=measure.integrated(loud);gated=measure.integrated(both);ungated=measure.k_level(both)
        assert abs(gated-alone-10*np.log10(18.5/20))<.05 and gated-ungated>6,(alone,gated,ungated)
        # How near a mix is heard, as one room (0.6): C80 from the response the mix gives its parts, in the octaves of
        # 500, 1000 and 2000 Hz.  A direct sound with reflections of half its amplitude at 20 ms and at 100 ms: each
        # reflection has a quarter of the energy sent, in every octave, so early is 1 + 0.25 and late 0.25, and the
        # clarity 10 log10(5) = 6.9897 dB.  It is the room's: the notes played through it do not enter.
        room=np.zeros((int(.2*R),2));room[int(.02*R)]=.5;room[int(.1*R)]=.5
        taps=measure.early_late(room)
        assert len(taps)==3 and all(abs(a-.25)<1e-9 and abs(b-.25)<1e-9 for a,b in taps),taps
        assert all(abs(a-.25)<1e-9 and abs(b-.25)<1e-9 for a,b in measure.early_late(room[:,0]))  # one channel alike
        c80=measure.clarity_c80(1.0,[(1.0,taps)])
        assert abs(c80-10*np.log10(5))<1e-9,c80
        # Half the energy sent (a send 3 dB down): early 1 + 0.125, late 0.125; the returns 6 dB up: 1 + 1, over 1.
        assert abs(measure.clarity_c80(1.0,[(.5,taps)])-10*np.log10(1.125/.125))<1e-9
        assert abs(measure.clarity_c80(1.0,[(1.0,taps)],10*np.log10(4))-10*np.log10(2/1))<1e-9
        # Two spaces add their early and their late energy; no space, or a response with nothing after 80 ms: none.
        short=np.zeros((int(.2*R),2));short[int(.01*R)]=1.0
        both=[(1.0,taps),(1.0,measure.early_late(short))]
        assert abs(measure.clarity_c80(1.0,both)-10*np.log10((1+.25+1)/.25))<1e-9
        assert measure.clarity_c80(1.0,[]) is None and measure.clarity_c80(1.0,[(1.0,measure.early_late(short))]) is None
        assert measure.clarity_c80(1.0,[(0.0,taps)]) is None
        # The octaves differ where the response does: the same room with the reflection at 100 ms low-passed at 700 Hz
        # (FFmpeg's own filter's response) keeps its late energy in the 500 Hz octave and loses most of it above, so
        # the three octaves' clarities part and their mean is what is given.
        freqs=np.fft.rfftfreq(len(room),1/R);late=np.zeros(len(room));late[int(.1*R)]=.5
        dark=room.copy();dark[:,:]=0;dark[int(.02*R)]=.5
        dark+=np.fft.irfft(np.fft.rfft(late)*measure.biquad('lowpass',700,freqs),n=len(room))[:,None]
        bands=measure.early_late(dark)
        assert all(abs(a-.25)<1e-6 for a,_ in bands) and bands[0][1]>2*bands[1][1]>8*bands[2][1]>0,bands
        each=[10*np.log10((1+a)/b) for a,b in bands]
        assert abs(measure.clarity_c80(1.0,[(1.0,bands)])-sum(each)/3)<1e-9 and each[0]<each[1]<each[2]
        # The filters on a space's return are counted: FFmpeg's highpass and lowpass at their defaults, two poles with
        # Q 0.707, whose response is 3.01 dB down at the corner and 12 dB an octave beyond it.
        for kind,corner,beyond in (('highpass',1000.0,500.0),('lowpass',1000.0,2000.0)):
            h=np.abs(measure.biquad(kind,corner,np.array([corner,beyond,corner*(8 if kind=='highpass' else 1/8)])))
            assert abs(20*np.log10(h[0])+3.0103)<.01 and abs(20*np.log10(h[1])+12.3)<.3 and abs(20*np.log10(h[2]))<.01,(kind,h)
        filtered=measure.early_late(room,highpass_hz=1000.0)
        assert filtered[0][0]<.5*taps[0][0] and abs(filtered[2][0]-taps[2][0])<.15*taps[2][0],filtered
        # The gain that gives a clarity gives it back, within the span allowed; past either end the nearer end is
        # taken (the clarity then misses, which the mix records); with nothing sent there is none to find.
        for target in (15,8,4,2):
            g=measure.returns_gain_for_c80(1.0,[(1.0,taps),(.5,bands)],target,30)
            assert abs(g)<30 and abs(measure.clarity_c80(1.0,[(1.0,taps),(.5,bands)],g)-target)<1e-9,(target,g)
        # These two spaces alone have a clarity over 1 dB (their own early energy over their late), so no gain brings
        # the mix to 0: the loudest allowed is given, and the clarity there is still above what was asked.
        assert measure.returns_gain_for_c80(1.0,[(1.0,taps),(.5,bands)],0,30)==30 and measure.clarity_c80(1.0,[(1.0,taps),(.5,bands)],30)>1
        assert measure.returns_gain_for_c80(1.0,[(1.0,taps)],15,30)<0<measure.returns_gain_for_c80(1.0,[(1.0,taps)],2,30)
        assert abs(measure.returns_gain_for_c80(1.0,[(1.0,taps)],10*np.log10(2),30)-10*np.log10(4))<1e-9  # worked above
        assert measure.returns_gain_for_c80(1.0,[(1.0,taps)],60,30)==-30 and measure.returns_gain_for_c80(1.0,[(1.0,taps)],-5,6)==6
        assert measure.returns_gain_for_c80(1.0,[(0.0,taps)],2,30) is None and measure.returns_gain_for_c80(1.0,[],2,30) is None
        assert measure.HALL_C80_DB==(-2.0,2.0) and measure.MID_OCTAVES_HZ==(500.0,1000.0,2000.0)
        # A signal shorter than one 400 ms block: one block with silence after it, 6.02 dB under the tone for 100 ms
        # (this skill's reading, said so in the text; BS.1770 counts whole blocks only).
        brief=measure.integrated(sine[:int(.1*R)]);whole=measure.integrated(sine)
        assert abs((whole-brief)-10*np.log10(4))<.35,(whole,brief)
        # What the project writes of how much each part sounds: the clarity is taken from this, never from the audio.
        # At 120 to the minute a note of four quarter notes is held 2 s; a second note that starts while the first is
        # held adds only what it adds (beats 2 to 6: one second more).  A part counts 10^(level / 10) for each second,
        # and sends that into its space at its send's level; a part that sends nothing names no space.
        w=example();w['clock']={'bars':4,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':1};w['mix']['chain']='bus'
        one_,two_=copy.deepcopy(w['tracks'][0]),copy.deepcopy(w['tracks'][0]);two_['id']=two_['name']='other'
        def held(part,spans):
            part['notes']=[{**part['notes'][0],'id':f'{part["id"]}_{k}','on':on,'duration':d,'pitch':60+k} for k,(on,d) in enumerate(spans)]
            part['performance']={**part['performance'],'notes':{n['id']:{'velocity':80,'gate':1.0,'timing_ms':0} for n in part['notes']}}
        held(one_,[(0,4)]);held(two_,[(0,4),(2,4)])
        one_['mix'].update(level_dbfs=-20,reverb_db=None);two_['mix'].update(level_dbfs=-30,reverb_db=-10)
        w['tracks']=[one_,two_];validate(w)
        written,sent=mixbus.written_energies(w,Clock(w))
        assert abs(written-(10**-2*2+10**-3*3))<2e-3*written and set(sent)=={'hall'} and abs(sent['hall']-10**-3*3*10**-1)<2e-3*sent['hall'],(written,sent)
        # The clarity such a project asks: the hall's response here is the two reflections above, read after the
        # return's own filters, and each octave's clarity is (written + sent * early) / (sent * late) by hand.
        response={'hall':room}
        filtered_=measure.early_late(room,mixbus.SPACES['hall'][5],mixbus.RETURN_LOWPASS)
        by_hand=sum(10*np.log10((written+sent['hall']*a)/(sent['hall']*b)) for a,b in filtered_)/3
        assert mixbus.clarity_setting(w,Clock(w),response) is None  # no clarity asked: nothing is set
        w['mix'].update(rules=2,c80_db=20);validate(w);set_=mixbus.clarity_setting(w,Clock(w),response)
        assert abs(set_['c80_written_db']-by_hand)<.01 and set_['c80_reached'] and abs(set_['c80_db']-20)<.05 and set_['c80_asked_db']==20,(set_,by_hand)
        assert abs(set_['gain_db']-(by_hand-20))<.5 and (set_['gain_db']>0)==(by_hand>20),(set_,by_hand)  # a dB on the returns is about a dB of clarity while the direct sound leads
        # The same notes written half as long, or a part's level raised, change it as the arithmetic says; the audio
        # is never read (no render exists here).
        held(two_,[(0,2)]);quieter=mixbus.written_energies(w,Clock(w))
        assert abs(quieter[1]['hall']-10**-3*1*10**-1)<2e-3*quieter[1]['hall']
        # A part played backwards fills its written span whatever its notes' gates say (render.reversed_notes), so
        # it counts for the written span: the same for a gate of 0.1 as for 1.0 (it had followed the gate, and the
        # clarity of a piece moved by 7 dB with a field the renderer does not read: a review of 0.6.0).
        backwards=[]
        for gate in (.1,1.0):
            held(two_,[(0,4)]);two_['reverse']=True;two_['performance']['notes'][two_['notes'][0]['id']]['gate']=gate
            backwards.append(mixbus.written_energies(w,Clock(w))[1]['hall'])
        assert backwards[0]==backwards[1] and abs(backwards[0]-10**-3*2*10**-1)<2e-3*backwards[0],backwards
        two_.pop('reverse')
        # The time a part counts for is the time its renderer holds its notes, each worked out here by hand at 120 to
        # the minute (the third review of 0.6.0 found the performed notes counted where the renderer plays others):
        # - a drum hit of four beats on key 35 that the part's key map moves onto key 36, where a louder hit of half a
        #   beat starts with it: the renderer keeps the louder and drops the other, so 0.25 s, as without the long hit;
        # - a slur, notes of 0.45 beat at beats 0 and 0.5: one note from 0 to 0.475 s, the gap filled; and with notes
        #   of 0.2 beat and a slur across 200 ms, 0 to 0.35 s;
        # - the same two notes with crossfade legato of 100 ms: the first held to the crossfade's end at 0.35 s, the
        #   second from 0.25 to 0.475 s, 0.475 s together, with the part moved 80 ms early as without;
        # - a mono synth line, a note at beat 1 of half a beat over a first note of four beats or of one: the later
        #   note owns the voice and its release, so 0 to 0.75 s both times.
        def span_part(notes,**more):
            return {'id':'send','role':'harmony','engine':'soundfont','program':0,'notes':[{'id':f'n{i}','on':on,'duration':d,'pitch':key} for i,(on,d,key) in enumerate(notes)],
                    'performance':{'notes':{f'n{i}':{'velocity':80,'gate':1.0,'timing_ms':0} for i in range(len(notes))},'cc':[]},'mix':{'level_dbfs':-20,'reverb_db':-10,'space':'hall'},**more}
        def counted(part):
            q={'schema':'music-production/v1','title':'Spans','clock':{'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':1},'sections':[{'id':'all','start_bar':0,'bars':2}],
               'tracks':[part],'mix':{'chain':'bus'}}
            validate(q);return mixbus.written_energies(q,Clock(q))[1]['hall']/(10**-2*10**-1)
        mapped=span_part([(0,4,35),(0,.5,36)],drums=True,key_map={'35':36});mapped['performance']['notes']['n0']['velocity']=60;mapped['performance']['notes']['n1']['velocity']=100
        alone_=span_part([(0,.5,36)],drums=True,key_map={'35':36});alone_['performance']['notes']['n0']['velocity']=100
        spans_={'mapped':counted(mapped),'alone':counted(alone_)}
        for name_,notes_,gap_ in (('slur',[(0,.45,60),(.5,.45,62)],40),('wide_slur',[(0,.2,60),(.5,.2,62)],200)):
            slurred=span_part(notes_);slurred['performance'].update(legato={'mode':'slur','gap_ms':gap_,'max_interval':5},bend_range=12);spans_[name_]=counted(slurred)
        for early_ in (0,-80):
            crossed=span_part([(0,.45,60),(.5,.45,62)]);crossed['performance'].update(legato={'mode':'crossfade','gap_ms':40,'crossfade_ms':100},offset_ms=early_);spans_[f'crossfade{early_}']=counted(crossed)
        for first_ in (4,1):
            line_=span_part([(0,first_,60),(1,.5,62)],engine='synth',synth={'mono':True});line_['performance'].pop('cc');spans_[f'mono{first_}']=counted(line_)
        # - a Surge patch built an octave down is played an octave up, and a key past 127 at 127: notes of four beats
        #   and of half a beat written on 116 and 117 both play key 127, so the first is cut one tick before the second
        #   strikes at beat 1 (959 of the beat's 960 ticks) and the second holds 0.25 s; written on 48 and 49 they play
        #   60 and 61 and the first holds its 2 s (a last review of 0.6.0 found the written keys counted).
        for name_,keys_ in (('surge_top',(116,117)),('surge_mid',(48,49))):
            bass_=span_part([(0,4,keys_[0]),(1,.5,keys_[1])],engine='surge',surge={'preset':'sub_bass_3'});bass_.pop('program');spans_[name_]=counted(bass_)
        by_hand_={'mapped':.25,'alone':.25,'slur':.475,'wide_slur':.35,'crossfade0':.475,'crossfade-80':.475,'mono4':.75,'mono1':.75,'surge_top':959/960*.5+.25,'surge_mid':2.0}
        assert all(abs(spans_[k]-v)<1e-6 for k,v in by_hand_.items()),spans_
        # A part whose notes are gone sends nothing: no clarity can be set, and the record says not reached.
        two_['notes']=[];two_['performance']['notes']={};none_=mixbus.clarity_setting(w,Clock(w),response)
        assert none_['gain_db']==0 and none_['c80_db'] is None and not none_['c80_reached'] and none_['c80_asked_db']==20,none_
        # The project's keys: rules 1 or 2, version 2 only on the bus chain, a clarity only with version 2.
        q=example();q['mix'].update(chain='bus',rules=2,c80_db=6);validate(q)
        # A clarity is set on the reverbs' returns: a project that sends nothing to a reverb is refused, not rendered
        # with the clarity passed over (a review of 0.6.0); one part sending is enough.
        q=example();q['mix'].update(chain='bus',rules=2,c80_db=6);[t['mix'].pop('reverb_db',None) for t in q['tracks']]
        try:validate(q);raise AssertionError('a clarity with no reverb send was accepted')
        except ValueError as e:assert 'mix.c80_db' in str(e) and 'reverb' in str(e),e
        q['tracks'][0]['mix']['reverb_db']=-12;validate(q)
        for mix in ({'chain':'bus','c80_db':6},{'chain':'bus','rules':2,'c80_db':26},
                    {'chain':'bus','rules':2,'c80_db':-6},{'chain':'bus','rules':2,'c80_db':'6'},{'chain':'bus','rules':2,'c80_db':None}):
            q=example();q['mix'].update(mix);rejects(lambda:validate(q))
        for mix in ({'rules':3},{'rules':'2'},{'chain':'room','rules':2},{'chain':'bus','rules':True}):
            q=example();q['mix'].update(mix);rejects(lambda:validate(q))
        return {'sine_integrated_lufs':round(measure.integrated(sine),3),'gated_minus_ungated_lu':round(gated-ungated,2),
                'clarity_written_db':set_['c80_written_db']}
    def true_peak_limiter():
        # musiclib/limiter.py, the master's limiter under the mix's rules of version 2.
        from musiclib import limiter
        R=audio.RATE;rng=np.random.default_rng(12);t=np.arange(2*R)/R
        # The running minimum against the plain loop, at widths under, at and over the signal's length.
        a=rng.standard_normal(700)
        for w in (1,2,7,64,145,699,700,1100):
            assert np.array_equal(limiter.running_min(a,w),np.array([a[i:i+w].min() for i in range(len(a))])),w
        # The true peak between samples: a sine at a quarter of the rate, sampled 45 degrees from its crests, has sample
        # peaks of 0.707 and a true peak of 1; one faded in reads 1 too, and silence reads 0.
        fade=np.minimum(1,np.minimum(np.arange(len(t)),len(t)-1-np.arange(len(t)))/(R/20))
        quarter=np.sin(2*np.pi*(R/4)*t+np.pi/4)*fade;q2=np.stack([quarter,quarter],axis=1)
        tp=limiter.true_peak(q2)
        assert abs(float(np.abs(q2).max())-.7071)<1e-3 and abs(float(tp.max())-1)<1e-3 and float(limiter.true_peak(np.zeros((1000,2))).max())==0,float(tp.max())
        # The interpolation is the curve through the samples.  Worked out here term by term, not by the transform it
        # uses: for N samples (N even) with spectrum X, x(t) = (1/N) [sum over |k| < N/2 of X_k e^(2 pi i k t / N)
        # + X_(N/2) cos(pi t)], the term at half the rate being a cosine through its samples.  Every fourth value is a
        # sample again.  (Until a review of 0.6.0 the term at half the rate went up doubled, and this check compared
        # the function with the same mistake.)
        s=rng.standard_normal((64,2));N=len(s);X=np.fft.fft(s,axis=0);tt=np.arange(4*N)/4;k=np.arange(-N//2+1,N//2)
        curve=((X[k%N][None,:,:]*np.exp(2j*np.pi*k[None,:,None]*tt[:,None,None]/N)).sum(axis=1).real+X[N//2].real[None,:]*np.cos(np.pi*tt)[:,None])/N
        fine=limiter.interpolate(s,4)
        assert float(np.abs(fine-curve).max())<1e-9 and float(np.abs(fine[::4]-s).max())<1e-9,float(np.abs(fine-curve).max())
        odd=rng.standard_normal((63,2));assert float(np.abs(limiter.interpolate(odd,4)[::4]-odd).max())<1e-9  # an odd length has no such bin
        # A part at half the rate: 0.1 + 0.4 (-1)^n is the curve 0.1 + 0.4 cos(pi t), whose peak is 0.5 (the doubled
        # term read 0.9).  A limiter with its ceiling at 0.6 leaves it alone.
        # Read where the blocks hold nothing but the steady signal (the second of three).  In a block where such a part
        # starts or stops, its curve between samples is not settled by the samples near it, and the reading there
        # runs up to a third high: over the need, never under it, since the samples themselves are always read.
        n4=np.arange(3*61440);ends=np.minimum(1,np.minimum(n4,len(n4)-1-n4)/(R/20))
        half=np.stack([(0.1+0.4*(-1.0)**n4)*ends]*2,axis=1);whole_tp=limiter.true_peak(half);tph=whole_tp[61440:2*61440]
        assert abs(float(tph.max())-.5)<1e-3 and abs(float(tph.min())-(0.1+0.4*np.cos(np.pi/4)))<1e-3,(float(tph.max()),float(tph.min()))
        assert float((whole_tp-np.abs(half).max(axis=1)).min())>-1e-6 and float(whole_tp.max())<.5*4/3
        assert float(limiter.limit(half,.7,.05)[1].min())>-1e-6
        # Against one interpolation of the whole signal with silence round it: block edges change nothing.
        x=rng.standard_normal((70000,2))*.3;z=np.concatenate([np.zeros((4096,2)),x,np.zeros((4096,2))])
        up=np.abs(limiter.interpolate(z,4)).max(axis=1)
        whole=np.array([up[4*i-3:4*i+4].max() for i in range(4096,4096+len(x))])
        assert float(np.abs(limiter.true_peak(x)-whole).max())<.02*float(whole.max()),float(np.abs(limiter.true_peak(x)-whole).max())
        # The guarantee: whatever the signal, the gain is at most what each sample needs, so no true peak this module
        # reads is over the ceiling before the gain is applied; after it, bursts of noise 20 dB over stay within 0.1 dB.
        bursts=rng.standard_normal((2*R,2))*np.repeat(rng.random(40)*3,R//20)[:,None];peak=limiter.true_peak(bursts)
        for release,lookahead,hold in ((.05,.003,None),(.2,.0015,None),(.1,.005,0)):
            g=limiter.gain_db(peak,.5,release,lookahead,hold);need=np.minimum(0,20*np.log10(.5/np.maximum(peak.astype(np.float64),1e-12)))
            assert float((g-need).max())<=1e-9 and float(g.max())<=0,(release,lookahead,float((g-need).max()))
            after=float(limiter.true_peak(bursts*(10**(g/20))[:,None]).max())
            assert after<.5*10**(.1/20),(release,lookahead,after)
        # The release against the plain recursion rel(n) = min(held(n), rel(n-1) * r), with no look-ahead and no hold.
        need=-np.abs(rng.standard_normal(4000))*(rng.random(4000)>.97);r=np.exp(-1/(.01*R));want=np.empty(4000);prev=0.0
        for i,h in enumerate(need):
            prev=min(min(h,-1e-9),prev*r);want[i]=prev
        got=limiter.gain_db(10**(-need/20),1.0,.01,0,0)
        assert float(np.abs(got-want).max())<1e-9,float(np.abs(got-want).max())
        # A low note meets one steady gain: 30 Hz, 6 dB over, moves the gain by under a thousandth of a decibel once it
        # has settled (its crests are 16.7 ms apart, inside the hold); without the hold the gain rides the waveform.
        low=np.stack([np.sin(2*np.pi*30*t)]*2,axis=1);_,g=limiter.limit(low,.5,.1);_,bare=limiter.limit(low,.5,.1,hold=0)
        steady=float(np.ptp(g[R//2:-R//10]));riding=float(np.ptp(bare[R//2:-R//10]))
        assert steady<1e-3 and riding>.5 and abs(float(g[R])+6.02)<.01,(steady,riding,float(g[R]))
        # No delay: a burst comes out where it went in, held to the ceiling, and the tone round it is untouched before
        # the look-ahead and back within 1 dB half a second later.
        tone=.05*np.sin(2*np.pi*1000*t);burst=tone.copy();burst[R:R+960]*=40;y,g=limiter.limit(np.stack([burst,burst],axis=1),.5,.1)
        assert abs(float(np.abs(y[R:R+960]).max())-.5)<.005 and float(g[:R-200].min())>-1e-6 and float(g[R+R//2])>-1 and float(g[R+100])<-11,(float(g[R+100]),float(g[R+R//2]))
        return {'steady_gain_ripple_db_30hz':round(steady,6),'riding_without_hold_db':round(riding,3),'quarter_rate_true_peak':round(float(tp.max()),4)}
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
        # Pestana et al. (2013)'s slope of log magnitude on log frequency: pink noise -0.5, the darker -0.8, white 0.
        ll=[x['tonal_balance']['slope_log_log_100hz_10khz'] for x in (pink,dark,white)]
        assert abs(ll[0]+.5)<.05 and abs(ll[1]+.8)<.05 and abs(ll[2])<.05,ll
        same,quiet=analysis.compare(pink,pink,'pink')
        assert not quiet and same['slope_difference_db_per_octave']==0 and not any(same['octaves_minus_reference_db'].values()),same
        darker,told=analysis.compare(dark,pink,'pink')
        assert len(told)==1 and 'darker' in told[0] and dark['side_minus_mid_db']['20-120']==-60 and abs(pink['side_minus_mid_db']['2000-16000'])<.5,(told,dark['side_minus_mid_db'],pink['side_minus_mid_db'])
        table=json.loads(analysis.REFERENCES.read_text(encoding='utf-8'))['references']
        assert all(-8<=r['tonal_balance']['slope_db_per_octave_100hz_4khz']<=-1.5 and r['loudness']['plr_db']>0 for r in table.values()),sorted(table)
        return {'slopes':slopes,'log_log_slopes':ll,'darker_by':darker['slope_difference_db_per_octave'],'references':sorted(table)}
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
    def part_saturation():
        # musiclib/production.py: `mix.saturate` drives the stem through tanh at four times the sample rate and keeps its
        # loudness (no check ran it before 0.8: the selfcheck's coverage).
        from musiclib import production
        t=np.arange(audio.RATE)/audio.RATE;out={}
        for f0,drive in ((1000,.8),(7000,1.)):
            x=np.stack([.5*np.sin(2*np.pi*f0*t)]*2,axis=1)
            y,receipt=production.saturate(x,{'mix':{'saturate':drive}});y=np.asarray(y,dtype=np.float64)
            spec=np.abs(np.fft.rfft(y[:,0]*np.hanning(len(y))));f=np.fft.rfftfreq(len(y),1/audio.RATE)
            rel=lambda hz:float(20*np.log10(spec[np.argmin(np.abs(f-hz))]/spec[np.argmin(np.abs(f-f0))]+1e-20))
            kept=float(10*np.log10(np.mean(y**2)/np.mean(x**2)))
            assert abs(kept)<.01 and rel(3*f0)>-30 and receipt=={'drive':drive},(f0,kept,rel(3*f0),receipt)  # measured: 0.000 dB, -11 dB
            out[f0]={'loudness_change_db':round(kept,4),'third_harmonic_db':round(rel(3*f0),1)}
        # The 5th harmonic of 7 kHz (35 kHz) folds to 13 kHz unless it is made at four times the rate and filtered away.
        folded=rel(audio.RATE-5*7000)
        assert folded<-80,folded  # measured: -146.6 dB
        out[7000]['folded_fifth_db']=round(folded,1)
        return out
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
        # Analysis regions by names of their own: a --span named as a section is, or one label given twice, is refused
        # before anything is read (they shared their figures, and a section's came out 19.6 dB wrong with a cut
        # suggested on it; GPT Pro's seventh review of 0.4.0); a round asks before its render.
        from musiclib.revision import revision_round
        analysis.region_names(['intro','verse'],[('focus',1,2),('other',3,4)])
        assert rejects(lambda:analysis.region_names(['span:focus','tail'],[('focus',3,4)]))
        assert rejects(lambda:analysis.region_names(['a'],[('take',1,4),('take',3,4)]))
        save_json(work/'names.json',example())
        assert rejects(lambda:revision_round(work/'names.json',work/'names_round',None,spans=[('take',1,2),('take',2,2)],show=lambda *a:None))
        assert not (work/'names_round').exists()
        return {'group':group,'suggestion':cut[0],'silent_lead_has_no_figures':True,'region_names_refused':3}
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
    found = {'bus_assignment_and_validation': bus_settings, 'church_space_decays_as_specified_and_dynamics_validate': spaces_and_dynamics, 'k_weighting_matches_bs1770': k_weighting, 'loudness_measures_gate_and_compare': loudness_measures, 'true_peak_limiter_holds_the_ceiling': true_peak_limiter, 'tonal_balance_reads_noise_and_compares_with_a_reference': tonal_reference, 'a_bell_facing_back_sounds_darker_and_further': facing, 'production_delay_duck_gate_and_mono_low_end': production_tools, 'part_saturation_keeps_loudness_and_adds_harmonics': part_saturation, 'tape_wow_flutter_and_vinyl_noise': worn_media, 'chorus_reads_its_moving_delay_between_samples': chorus_effect, 'stage_depth_moves_reflections_and_hall': stage_depth, 'range_control_lifts_soft_passages_only': range_master, 'analysis_groups_octave_doublings_and_suggests_cuts': melody_group_and_balance, 'automation_applies_per_sample_with_held_ends': automation_applies_per_sample_with_held_ends}
    if config:
        p, cache, render = S['p'], S['cache'], S['render']
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
            # A loud master, louder than -14 LUFS, keeps its true peak under -2 dBTP, as Spotify asks of loud masters, and
            # the summary gives the ceiling; its MP3's true peak is measured (a -9 LUFS master at -1.13 dBTP decoded at
            # +0.06 from its MP3 in a 0.4.0 piece).
            hot=copy.deepcopy(q);hot['mix'].update(loudness='loud',target_lufs=-10);save_json(work/'bus_loud.json',hot)
            h=render(work/'bus_loud.json',work/'render_bus_loud',config,cache)
            assert all(h['checks'].values()) and h['mastering']['true_peak_ceiling_dbtp']==-2 and h['master']['true_peak_dbtp']<=-2,(h['checks'],h['mastering']['passes'])
            from musiclib import summary as said
            assert h['master']['integrated_lufs']>-14 and 'over_full_scale' in h['mp3'] and '(ceiling -2)' in said.render(h,work/'render_bus_loud'),h['master']
            return {'buses':r['buses']['assignment'],'returns':r['buses']['returns'],'sum_minus_premix_peak_dbfs':r['buses']['sum_minus_premix_peak_dbfs'],'tape_premix_rebuilt_within':worst,'level_change_db':change,'master_lufs':r['master']['integrated_lufs'],'true_peak_dbtp':r['master']['true_peak_dbtp']}
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
        def effects_in_listed_order():
            # A part's effects apply in the order listed (0.8 step 1.3 counts them and must neither sort nor merge
            # them): a bitcrush before a phaser and the reverse give two filter chains in those orders and two stems,
            # each stem the very chain its receipt records run by FFmpeg on the part's raw take (so the audio follows the
            # order shown, not only differs between the two).
            q=copy.deepcopy(p);q['tracks']=[q['tracks'][0]];out={};cfg=audio.load_config(config);(work/'fx_logs').mkdir()
            for name,fx in (('crush_first',[{'type':'bitcrush','bits':4,'downsample':8},{'type':'phaser','rate_hz':2,'depth':.9}]),
                            ('phaser_first',[{'type':'phaser','rate_hz':2,'depth':.9},{'type':'bitcrush','bits':4,'downsample':8}])):
                q['tracks'][0]['mix']['effects']=fx;save_json(work/f'fx_{name}.json',q);render(work/f'fx_{name}.json',work/f'render_fx_{name}',config,cache)
                rec=json.loads((work/f'render_fx_{name}'/'stem_receipts.json').read_text(encoding='utf-8'))[0];chain=rec['filter_chain']
                ran=work/f'fx_{name}_chain.wav'
                audio.ffmpeg(cfg,['-i',str(cache/rec['cache_key']/'raw.wav'),'-af',chain,'-ar',str(audio.RATE),'-c:a','pcm_f32le',str(ran)],work/'fx_logs',f'chain_{name}')
                same=np.array_equal(audio.read_wav(ran)[0],audio.read_wav(work/f'render_fx_{name}'/rec['processed_stem'])[0])
                out[name]=(chain.index('acrusher')<chain.index('aphaser'),rec['stem_sha256'],same)
                crush,phase='acrusher=bits=4:samples=8:mix=1:mode=lin','aphaser=in_gain=0.8:out_gain=0.9:delay=3:decay=0.650:speed=2:type=t'
                assert (f'{crush},{phase}' if name=='crush_first' else f'{phase},{crush}') in chain,chain   # each effect's own filter, written out here
            assert out['crush_first'][0] and not out['phaser_first'][0] and out['crush_first'][1]!=out['phaser_first'][1] and out['crush_first'][2] and out['phaser_first'][2],out
            return {k:v[0] for k,v in out.items()}
        def analysis():
            from musiclib.analysis import analyze
            from musiclib import analysis as analysis_mod
            a=analyze(work/'render_bus')
            assert [s['section'] for s in a['sections']]==[s['id'] for s in p['sections']] and a['lead_tracks']==['lead']
            assert all(np.isfinite(s['level_lufs_ungated']) and abs(sum(s['band_share_pct'].values())-100)<1.5 for s in a['sections'])
            assert any('lead_minus_accompaniment_db_median' in s and np.isfinite(s['lead_minus_accompaniment_level_db']) for s in a['lead_presence']),a['lead_presence']
            assert a['published_genre'] is None or p.get('style'),a['published_genre']
            # A report from elsewhere may say anything: a bus that is none of the mix's six is refused before its name
            # becomes a file's (returns/bus_<name>.wav was read from wherever a path in the name led; GPT's security
            # audit of 0.5, L01).
            odd=work/'render_bus_odd';shutil.rmtree(odd,ignore_errors=True);shutil.copytree(work/'render_bus',odd)
            told=json.loads((odd/'report.json').read_text(encoding='utf-8'))
            for assigned in ({t['id']:'../../../../beside' for t in p['tracks']},{'no_such_part':'lead'},{p['tracks'][0]['id']:['lead']},['lead']):
                told['chain']='bus';told['buses']={**(told.get('buses') or {}),'assignment':assigned};save_json(odd/'report.json',told)
                try:analyze(odd);raise AssertionError(('a report that names no bus of the mix was read',assigned))
                except ValueError as e:assert 'buses' in str(e),e
            styled=work/'render_bus_styled';shutil.rmtree(styled,ignore_errors=True);shutil.copytree(work/'render_bus',styled)
            proj=json.loads((styled/'project.json').read_text(encoding='utf-8'));proj['style']='pop/ballad';save_json(styled/'project.json',proj)
            b=analyze(styled);pg=b['published_genre']
            assert (pg['genre'],pg['slope'],pg['master_slope'])==('pop',-0.943,b['tonal_balance']['slope_log_log_100hz_10khz']) and pg['difference']==round(pg['master_slope']+0.943,3),pg
            assert any('number ones they tag pop' in w for w in b['warnings'])==(pg['difference']<-analysis_mod.STEEPER_THAN_GENRE),(pg,b['warnings'])
            return {'sections':len(a['sections']),'lead_presence':a['lead_presence'],'published_genre':pg}
        def rules_2_render():
            # The mix's rules of version 2 (0.6): the buses' chains of version 1 with the saturation between two
            # resamplers, a master with one true-peak limiter and no delay, and a clarity where a project asks one,
            # set from the project file.  None of these is set from a measurement of the audio.  The same project under
            # version 1 stays as it was (render_bus above: checked there).
            from musiclib import loop,mixbus,measure
            from musiclib import summary as said
            q=copy.deepcopy(p);q['mix'].update(chain='bus',rules=2);save_json(work/'rules2.json',q)
            r=render(work/'rules2.json',work/'render_rules2',config,cache);out=work/'render_rules2';ms=r['mastering'];st=r['buses']['rules']
            one=json.loads((work/'render_bus'/'report.json').read_text(encoding='utf-8'))
            assert all(r['checks'].values()) and ms['rules']==2 and st['rules']==2,r['checks']
            assert abs(r['master']['integrated_lufs']-q['mix']['target_lufs'])<=.3 and r['master']['true_peak_dbtp']<=ms['true_peak_ceiling_dbtp'],r['master']
            # One limiter, and it is not FFmpeg's: neither chain names alimiter, and the record says what limited.
            assert 'alimiter' not in ms['master_chain']+ms['delivery_chain'] and 'true-peak limiter' in ms['delivery_chain'],ms['delivery_chain']
            assert ms['limiter']['lookahead_ms']==3 and ms['limiter']['release_ms']==60 and len(ms['passes'])>=1 and not (out/'limited.wav').exists(),ms['limiter']
            # The ensemble's compressor is version 1's, settings and all: the bus moves against its stems as it did
            # under version 1, and its filter in the graph is the same text.
            change=r['buses']['level_change_db'];old=one['buses']['level_change_db']
            graph=(out/'mix.filtergraph.txt').read_text(encoding='utf-8')
            assert set(change)==set(old) and all(abs(change[b]-old[b])<=.05 for b in change if b not in mixbus.SATURATING+('lead',)),(change,old)
            assert all(mixbus.BUS_FILTER[b] in graph for b in ('ensemble',) if b in change) and 'lead' not in mixbus.BUS_FILTER_2
            # The lead's compressor stands 6 dB over the loudest lead part's written level, with 0.4 dB of make-up:
            # the threshold is in the graph as the project gives it, and the lead ends nearer where it was written
            # than under version 1's one threshold for every piece.
            top=max(t['mix']['level_dbfs'] for t in q['tracks'] if mixbus.bus_of(t)=='lead' and t['notes'])
            assert st['lead_threshold_dbfs']==min(0.0,top+6)==mixbus.lead_threshold_2(q) and f'acompressor=threshold={10**(st["lead_threshold_dbfs"]/20):.6f}:ratio=3:attack=6:release=120:makeup={10**(.4/20):.6f}' in graph,st
            assert abs(change['lead'])<=1 and abs(change['lead'])<abs(old['lead']),(change,old)
            bare=copy.deepcopy(q)
            for t in bare['tracks']:
                if mixbus.bus_of(t)=='lead':t['notes']=[]
            assert mixbus.lead_threshold_2(bare) is None and mixbus.lead_filter_2(bare)==mixbus.BUS_FILTER['lead']
            loud_lead=copy.deepcopy(q)
            for t in loud_lead['tracks']:
                if mixbus.bus_of(t)=='lead':t['mix']['level_dbfs']=-6
            assert mixbus.lead_threshold_2(loud_lead)==0.0 and 'threshold=1.000000' in mixbus.lead_filter_2(loud_lead)
            # The saturating buses pass the curve at four times the rate, between two resamplers, and come out as long
            # as the mix (the checks above read every bus beside its stems); version 1's graph has no resampler.
            assert graph.count('aresample=192000')==len([b for b in mixbus.SATURATING if b in change])>0 and 'aresample' not in (work/'render_bus'/'mix.filtergraph.txt').read_text(encoding='utf-8'),graph.count('aresample=192000')
            assert all(audio.read_wav(out/'returns'/f'bus_{b}.wav')[1]['frames']==r['master']['frames'] for b in change),r['master']['frames']
            # The reverb stays as the sends write it: the record holds no gain, and the returns on disk are version 1's.
            wet_energy=lambda folder:sum(float((np.asarray(audio.read_wav(folder/'returns'/n)[0],dtype=np.float64)**2).sum()) for n in r['buses']['returns'] if n!='delay_return.wav')  # noqa: E731
            assert st['rules']==2 and st['reverb'] is None and set(st)=={'rules','lead_threshold_dbfs','reverb'} and r['buses']['returns'] and abs(10*np.log10(wet_energy(out)/wet_energy(work/'render_bus')))<.01,st
            assert r['checks']['buses_and_returns_add_up_to_premix'] and json.loads((out/'returns'/mixbus.RULES_FILE).read_text(encoding='utf-8'))==st and 'Mix rules 2' in said.render(r,out)
            # A piece that names how near it is heard (mix.c80_db): the returns move by the one gain that gives the mix
            # that clarity, worked out from the project file and the spaces' responses, and analyze, from the same,
            # reports the clarity asked.
            from musiclib.analysis import analyze as analysed
            near=copy.deepcopy(q);near['mix']['c80_db']=6;save_json(work/'rules2_c80.json',near)
            rn=render(work/'rules2_c80.json',work/'render_rules2_c80',config,cache,draft=True);hn=rn['buses']['rules']['reverb']
            an=analysed(work/'render_rules2_c80')
            # The returns on disk rose by the gain recorded, against the same piece with its sends as written.
            assert abs(10*np.log10(wet_energy(work/'render_rules2_c80')/wet_energy(out))-hn['gain_db'])<.01,hn
            assert all(rn['checks'].values()) and hn['c80_asked_db']==6 and hn['c80_reached'] and abs(hn['c80_db']-6)<.05 and hn['gain_db']>0 and hn['c80_written_db']>6,hn
            # The clarity as written is the project's: the same figure from the file alone, before anything is rendered.
            from musiclib.model import Clock as Clock_
            alone=mixbus.clarity_setting(near,Clock_(near),{n:mixbus.space_ir(n) for n in mixbus.SPACES})
            assert alone==hn,(alone,hn)
            assert abs(an['reverb']['clarity_c80_db']-6)<=.1 and an['reverb']['c80_asked_db']==6 and an['reverb']['hall_c80_db']==[-2.0,2.0] and not any('reverb returns' in w for w in an['warnings']),(an['reverb'],an['warnings'])
            plain=analysed(out)
            assert plain['reverb']['clarity_c80_db']>an['reverb']['clarity_c80_db']+5 and 'c80_asked_db' not in plain['reverb'] and 'clarity C80' in said.analysis(plain,out/'analysis.json'),plain['reverb']
            # The same render twice: the same master.
            again2=render(work/'rules2.json',work/'render_rules2_again',config,cache,draft=True)
            assert file_hash(work/'render_rules2_again'/'master.wav')==file_hash(out/'master.wav') and again2['buses']['rules']==st
            # A loud master under version 2: the soft clipper, then the limiter, under -2 dBTP.
            hot=copy.deepcopy(q);hot['mix'].update(loudness='loud',target_lufs=-10);save_json(work/'rules2_loud.json',hot)
            h=render(work/'rules2_loud.json',work/'render_rules2_loud',config,cache)
            assert all(h['checks'].values()) and h['master']['true_peak_dbtp']<=-2 and 'soft clip' in h['mastering']['delivery_chain'] and abs(h['master']['integrated_lufs']+10)<=.3,(h['master'],h['mastering']['passes'])
            # A wide master under version 2: one gain, no guard limiter, nothing set on the buses.
            wide=copy.deepcopy(q);wide['mix'].update(dynamics='wide',target_lufs=-18);save_json(work/'rules2_wide.json',wide)
            w=render(work/'rules2_wide.json',work/'render_rules2_wide',config,cache,draft=True)
            assert all(w['checks'].values()) and 'alimiter' not in w['mastering']['delivery_chain'] and w['mastering']['rules']==2 and w['buses']['rules']['reverb'] is None,w['mastering']
            # A wide mix compresses no bus: its record names no lead threshold and its summary says none (it named the
            # threshold of a compressor that was not there: a review of 0.6.0).
            assert w['buses']['rules']['lead_threshold_dbfs'] is None and 'lead compressor' not in said.render(w,work/'render_rules2_wide') and '[sum_lead]anull[bus_lead]' in (work/'render_rules2_wide'/'mix.filtergraph.txt').read_text(encoding='utf-8')
            # Layers of a loop under version 2 read what the full mix set, add up to the loop, and need no delay: the
            # master has no look-ahead to trail by (under version 1 the master trails its layers by some 10 ms).
            ids=[t['id'] for t in q['tracks']];lq=copy.deepcopy(q);lq['loop']={'start_bar':0,'layers':{'base':ids[:2]+ids[4:],'top':ids[2:4]}}
            save_json(work/'rules2_layers.json',lq);lr=render(work/'rules2_layers.json',work/'render_rules2_layers',config,cache);lo_=work/'render_rules2_layers';lp=lr['loop']
            parts=[np.asarray(audio.read_wav(lo_/'layers'/f'{lid}.wav')[0],dtype=np.float64) for lid in ('base','top')]
            mix=np.asarray(audio.read_wav(lo_/'loop.wav')[0],dtype=np.float64);both=parts[0]+parts[1]
            corr=float(np.sum(both*mix)/np.sqrt(np.sum(both**2)*np.sum(mix**2)))
            assert all(lr['checks'].values()) and corr>.98 and abs(lp['layers']['sum_minus_loop_db'])<3 and lp['layers']['aligned_frames']==0,(corr,lp['layers'])
            # What a review of 0.6.0 found, on the mix alone (stems written here, no notes rendered).
            from musiclib import limiter
            from musiclib.model import Clock
            R=audio.RATE;cfg_=audio.load_config(config);click=np.zeros((2*R,2),dtype=np.float32);click[R]=1.0
            def stems_mix(name,mixed,stem,change=None):
                o=work/name;c=copy.deepcopy(p);c['mix']=mixed
                if change:change(c)
                for sub in ('stems','returns','logs'):(o/sub).mkdir(parents=True)
                for t in c['tracks']:audio.write_wav(o/'stems'/f'{t["id"]}.wav',stem(t))
                return o,mixbus.mix(c,Clock(c),cfg_,o,2*R)
            # A bus that is a single click mixes under both versions (under the first version 2 its measured crest
            # factor asked the compressor for a time under what FFmpeg takes, and the mix stopped).
            for version in (1,2):
                o,made=stems_mix(f'click_rules{version}',{'chain':'bus','rules':version},lambda t:click)
                assert audio.read_wav(o/'premix.wav')[1]['frames']==2*R,version
            assert made['rules']['rules']==2 and made['rules']['reverb'] is None,made['rules']
            # A clarity asked of a project whose sending parts have no notes cannot be set: the returns stay, the
            # record says not reached, and the render's summary says so.  What the stems hold does not enter: the
            # same project with its notes is given its clarity whatever audio stands in the stems.
            sending={t['id'] for t in p['tracks'] if t['mix'].get('reverb_db') is not None}
            def emptied(c):
                for t in c['tracks']:
                    if t['id'] in sending:t['notes']=[];t['performance']['notes']={}
            o,made=stems_mix('silent_sends',{'chain':'bus','rules':2,'c80_db':6},lambda t:click,emptied)
            sr=made['rules']['reverb']
            assert sending and sr['c80_asked_db']==6 and sr['c80_db'] is None and not sr['c80_reached'] and sr['gain_db']==0,sr
            assert 'clarity C80 asked +6 dB: not reached' in said.render({**r,'buses':{**r['buses'],'rules':made['rules']}},out)
            o,made=stems_mix('any_audio',{'chain':'bus','rules':2,'c80_db':6},lambda t:np.zeros_like(click))
            assert made['rules']['reverb']==hn,(made['rules']['reverb'],hn)
            # The delivery records the gain it applied.  A quiet tone with short loud bursts, asked for a loudness
            # the limiter cannot give it: four tries each of four passes do not settle, and the gain recorded is the
            # gain of the last signal the limiter was given (it was the next try's, 5 dB on, which a loop's layers
            # and the limiting by section then read).
            tt=np.arange(20*R)/R;x=10**(-40/20)*np.sin(2*np.pi*440*tt)
            for k in range(20):
                a=int((k+.5)*R);x[a:a+R//20]+=10**(-3/20)*np.sin(2*np.pi*1000*tt[:R//20])
            o=work/'deliver_bursts';(o/'logs').mkdir(parents=True);audio.write_wav(o/'mixed.wav',np.stack([x,x],axis=1).astype(np.float32))
            src=audio.measure(cfg_,o/'mixed.wav',o/'logs','measure_mixed');base=float(limiter.true_peak(audio.read_wav(o/'mixed.wav')[0]).max())
            seen=[];real=limiter.gain_db
            def watched(peak,*a,**k):
                seen.append(float(np.max(peak)));return real(peak,*a,**k)
            limiter.gain_db=watched
            try:rec,_=mixbus.deliver_2({**q,'mix':{**q['mix'],'target_lufs':-10}},cfg_,o,o/'mixed.wav',src,-10)
            finally:limiter.gain_db=real
            applied=20*np.log10(seen[-1]/base);last=rec['passes'][-1]['gain_db']
            assert len(rec['passes'])==4 and len(seen)==16 and abs(applied-last)<=.002 and f'volume={last:.6f}dB' in rec['delivery_chain'] and not (o/'limited.wav').exists(),(applied,rec['passes'])
            return {'level_change_db':change,'level_change_db_rules_1':old,'limiter':ms['limiter'],
                    'passes':len(ms['passes']),'layers_correlation_with_loop':round(corr,4),'clarity_asked_6':hn,
                    'bursts_gain_applied_db':round(float(applied),3),'bursts_gain_recorded_db':last}
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
            # A target louder than -14 LUFS holds the true peak under -2 dBTP, as Spotify asks of loud masters.
            assert held>0 and hot['mastering']['true_peak_ceiling_dbtp']==-2 and hot['master']['true_peak_dbtp']<=-2 and abs(hot['master']['integrated_lufs']-(-10-held))<.5,hot['mastering']
            return {'contrast_mix_db':round(mixed,2),'contrast_wide_db':round(wide,2),'contrast_glue_db':round(glue,2),
                    'hot_peak_held_db':held,'hot_true_peak_dbtp':hot['master']['true_peak_dbtp']}
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
        found.update({'bus_chain_render_and_delivery_checks': bus_render, 'a_chorus_pass_never_shares_another_parts_log': chorus_pass_logs, 'effects_apply_in_the_order_listed': effects_in_listed_order, 'analysis_reports_sections_stems_and_lead': analysis, 'mix_rules_2_render_limiter_saturation_and_clarity': rules_2_render, 'wide_dynamics_master_keeps_the_mix_range': wide_render, 'stage_depth_and_range_control_render': stage_and_range, 'long_automation_renders': long_automation_renders})
    return found
