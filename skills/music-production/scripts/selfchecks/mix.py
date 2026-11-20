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
from musiclib import audio, midi, model
from musiclib.model import Clock, file_hash, performed, save_json, validate
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
        # (a review of 0.9) a duck's `keys` is a list of keys: one number passed validate and stopped the render with
        # a traceback ('int' object is not iterable)
        dq=example();dq['tracks'][0]['mix']['duck']={'by':dq['tracks'][3]['id'],'keys':36}
        try:validate(dq);raise AssertionError('duck keys as one number')
        except ValueError as e:assert 'duck keys' in str(e) and '[36]' in str(e),e
        dq['tracks'][0]['mix']['duck']['keys']=[36];validate(dq)
        for good in ([],None,[36,38],[0,127]):   # an empty list and null are every key, as no `keys` at all (a review: [] was refused here, which older projects write)
            dq['tracks'][0]['mix']['duck']['keys']=good;validate(dq)
        assert production.duck(np.ones((n,2)),q,{'id':'pad','mix':{'duck':{'by':'kick','keys':None}}},clock)[1]['hits']==production.duck(np.ones((n,2)),q,{'id':'pad','mix':{'duck':{'by':'kick','keys':[]}}},clock)[1]['hits']==4
        for bad in ([36.5],['36'],[True],[128],'36',[None],128,-1):
            dq['tracks'][0]['mix']['duck']['keys']=bad
            try:validate(dq);raise AssertionError(bad)
            except ValueError as e:assert 'duck keys' in str(e),(bad,e)
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
    def a_part_moves_by_one_gain_for_each_channel():
        # mix.move (0.9 step 3): a part's place along a path or a swing, the two gains of that one place applied to each
        # sample of the part folded to a point; what is refused; what an excerpt and a review make of it.
        from musiclib import move
        from musiclib.review import review
        import excerpt as cut
        def with_move(spec,**mix):
            q=example();m=q['tracks'][0]['mix'];m.pop('pan',None);m.update(mix);m['move']=spec;return q
        path={'type':'path','points':[[0,-1],[8,1],[12,0]]};swing={'type':'swing','beats':4,'width':.5}
        for q in (with_move(path),with_move(path,pan=0),with_move(swing,pan=.5),with_move({**swing,'shape':'triangle','phase_beats':1})):validate(q)
        refused=[with_move(path,pan=.3),with_move(swing,pan=.7),with_move(swing,width=.5),with_move({'type':'orbit','beats':8}),
                 with_move({**swing,'speed':2}),with_move({**swing,'shape':'square'}),with_move({'type':'path','points':[[4,0]]}),
                 with_move({'type':'path','points':[[4,0],[4,1]]}),with_move({'type':'path','points':[[0,0],[4,1.5]]}),
                 with_move({'type':'swing','beats':4}),with_move({'type':'swing','beats':0,'width':.5}),with_move('left')]
        for q in refused:rejects(lambda q=q:validate(q))
        q=with_move(swing);q['mix']['chain']='bus';q['tracks'][0]['mix']['depth_m']=0;rejects(lambda:validate(q))
        # places: a swing stands at its pan at beat 0 and moves right; a path runs straight in time and holds its ends
        p=example();clock=Clock(p)
        at=lambda spec,pan,beats:[round(float(v),6) for v in move.at_beats(spec,pan,beats,clock)]
        assert at(swing,.25,[0,1,2,3,4])==[.25,.75,.25,-.25,.25] and at({**swing,'shape':'triangle'},0,[0,.5,1,2,3])==[0,.25,.5,0,-.5]
        assert at({**swing,'phase_beats':1},0,[0,1])==[.5,0]
        ends=at(path,0,[0,8,12,16]);assert ends==[-1,1,0,0],ends
        across={'type':'path','points':[[4,-1],[12,1]]};mid=(clock.seconds(4)+clock.seconds(12))/2   # the tempo changes at beat 8
        assert abs(clock.beat(mid)-8)>.05 and abs(float(move.at_beats(across,0,[clock.beat(mid)],clock)[0]))<1e-6   # half-way in time, not in beats
        assert abs(float(move.places(across,0,clock,round(mid*audio.RATE),1)[0]))<1e-4
        # applied: one signal on two channels, left sqrt(1 - place) and right sqrt(1 + place) of it at every sample
        frames=round((clock.end+clock.tail)*audio.RATE);rng=np.random.default_rng(5)
        mono=(.1*rng.standard_normal(frames)).astype(np.float32);x=np.stack([mono,mono],axis=1)
        y,facts=move.apply(x,path,0,clock);y=y.astype(np.float64)
        place=np.clip(move.places(path,0,clock,0,frames),-1,1)
        assert np.max(np.abs(y[:,0]-mono*np.sqrt(1-place)))<1e-6 and np.max(np.abs(y[:,1]-mono*np.sqrt(1+place)))<1e-6
        assert np.max(np.abs(y[:,0]**2+y[:,1]**2-2*mono.astype(np.float64)**2))<1e-6   # the power of the two stays
        assert facts['lowest']==-1 and facts['highest']==1 and facts['fold_loss_db']==0 and abs(facts['mono_dip_db']+3.01)<.01,facts
        rate=max(2/clock.seconds(8),1/(clock.seconds(12)-clock.seconds(8)));assert abs(facts['fastest_pan_per_second']-rate)<.01*rate,(facts,rate)
        # a path that stays in one place is the static pan's law
        still,_=move.apply(x,{'type':'path','points':[[0,.4],[16,.4]]},0,clock)
        assert np.max(np.abs(still[:,0]-mono*np.sqrt(.6)))<1e-6 and np.max(np.abs(still[:,1]-mono*np.sqrt(1.4)))<1e-6
        # the fold: two channels in opposite polarity cancel, and the receipt says how much went
        wide=np.stack([mono,-mono],axis=1);gone,lost=move.apply(wide,swing,0,clock)
        assert float(np.max(np.abs(gone)))<1e-6 and lost['fold_loss_db']<-100 and 'lowest' not in lost,lost
        half=np.stack([mono,np.zeros_like(mono)],axis=1);_,part=move.apply(half,swing,0,clock);assert abs(part['fold_loss_db']+3.01)<.01,part
        sw,fs=move.apply(x,swing,.25,clock)
        assert fs['period_beats']==4 and fs['lowest']==-.25 and fs['highest']==.75 and abs(fs['period_seconds'][0]-clock.seconds(4))<1e-3,fs
        # an excerpt goes on where the piece stands: a path with its places at both cuts, a swing with its phase
        assert move.excerpt(swing,0,6,10,clock)=={**swing,'phase_beats':2}
        e=move.excerpt(path,0,4,10,clock);assert [q[0] for q in e['points']]==[0,4,6] and e['points'][1][1]==1,e
        assert abs(e['points'][0][1]-float(move.at_beats(path,0,[4],clock)[0]))<1e-6 and abs(e['points'][2][1]-.5)<1e-6,e
        got=cut.extract(with_move(path),2,3)['tracks'][0]['mix']['move']   # bars 2 to 4: beats 4 to 16
        assert got==move.excerpt(path,0,4,16,clock) and [q[0] for q in got['points']]==[0,4,8,12],got
        # a loop: a part sounding up to the seam and again from it may not stand elsewhere across it
        def looped(spec,**mix):
            q=with_move(spec,**mix);q['loop']={'start_bar':0};t=q['tracks'][0]
            t['notes']=[{'id':'a','on':0,'duration':8,'pitch':60},{'id':'b','on':8,'duration':8,'pitch':62}]
            t['performance']={'notes':{'a':{'velocity':80},'b':{'velocity':80}}};return q
        validate(looped(swing));validate(looped({'type':'path','points':[[0,-.5],[8,.5],[16,-.5]]}))
        rejects(lambda:validate(looped({**swing,'beats':6})));rejects(lambda:validate(looped({'type':'path','points':[[0,-1],[16,1]]})))
        q=looped({'type':'path','points':[[0,-1],[16,1]]});q['tracks'][0]['notes'][1]['duration']=4;validate(q)   # a rest at the seam
        # review: the movement's range and rate from the score; a moving bass is asked about, another part is not
        q=with_move(swing);q['tracks'][1]['mix']['move']={'type':'path','points':[[0,-1],[16,1]]};save_json(work/'move_review.json',q)
        s=review(q,work/'move_review')
        byid={t['id']:t for t in s['tracks']};bass=q['tracks'][1]['id']
        assert byid[q['tracks'][0]['id']]['move']=={'type':'swing','lowest':-.5,'highest':.5,'fastest_pan_per_second':byid[q['tracks'][0]['id']]['move']['fastest_pan_per_second']}
        asked=[x['id'] for x in s['questions'] if x['id'].startswith('moving_low')];assert asked==[f'moving_low:{bass}'],asked
        # (the review of this feature, each point with its case)
        # the figures cover every sample: a visit to the hard right late in a block of the rendering, and a step from one
        # block's last sample to the next block's first
        R=audio.RATE;q=example();q['clock']['tempo']=[[0,120]];c120=Clock(q);n=3*R;flat=np.full((n,2),.1,dtype=np.float32)
        _,spike=move.apply(flat,{'type':'path','points':[[2.72,0],[2.725,1],[2.73,0]]},0,c120)
        assert spike['highest']==1 and abs(spike['fastest_pan_per_second']-400)<4 and abs(spike['mono_dip_db']+3.01)<.01,spike
        edge=move.BLOCK/R*2;_,step=move.apply(flat,{'type':'path','points':[[edge-2/R,0],[edge,1]]},0,c120)
        assert move.BLOCK%move.WINDOW==0 and step['fastest_pan_per_second']>20000,step
        late=np.zeros((move.BLOCK+300,2),dtype=np.float32);late[-300:]=.1   # sounding only in the stem's last, short window
        _,tail=move.apply(late,{'type':'path','points':[[0,-1],[edge,1]]},0,c120);assert tail['highest']==1 and tail['lowest']>.9,tail
        quiet,none=move.apply(np.zeros((R,2),dtype=np.float32),swing,0,c120);assert set(none)=={'type','fold_loss_db','period_beats','period_seconds'} and not quiet.any(),none
        assert lost['fold_loss_db']==move.FOLD_FLOOR_DB==-120                              # all lost in the fold: the floor, not a number of its own
        # a swing's period in seconds, also where it is longer than the piece
        q1=example();q1['clock'].update(bars=1,tempo=[[0,120]]);q1['sections']=[{'id':'a','start_bar':0,'bars':1}];q1.pop('harmony',None)
        assert move.period_seconds({'type':'swing','beats':8,'width':.5},Clock(q1))==[4.0,4.0]
        assert move.period_seconds(swing,clock)==[round(clock.seconds(4),3),round(clock.seconds(16)-clock.seconds(12),3)]
        # a field an agent wrote as "mode" was meant as level_mode, not as the nearest name by spelling
        q=example();q['tracks'][2]['mix']['mode']='peak';assert validate(q)['warnings']==["lead.mix: unknown field 'mode' (did you mean 'level_mode'?); it has no effect"],validate(q)['warnings']
        # null, and a width written beside it, are not the two forms
        rejects(lambda:validate(with_move(None)));rejects(lambda:validate(with_move(swing,width=1)))
        # the seam: a difference of exactly the tolerance passes; a note's place is read by the tick it is played on
        validate(looped({'type':'path','points':[[0,.5],[8,.7],[16,.55]]}))
        q=with_move({'type':'path','points':[[4,-1],[8,1]]});q['clock'].update(bars=2,tempo=[[0,120]]);q['sections']=[{'id':'a','start_bar':0,'bars':2}];q.pop('harmony',None)
        q['loop']={'start_bar':1};t0=q['tracks'][0];t0['notes']=[{'id':'a','on':4.0004,'duration':3.9992,'pitch':60}];t0['performance']={'notes':{'a':{'velocity':80}},'cc':[]}
        for other in q['tracks'][1:]:other['notes']=[];other['performance']={'notes':{},'cc':[]}
        rejects(lambda:validate(q))
        # an excerpt keeps a path's places as they are
        near={'type':'path','points':[[0,.9999996],[16,.9999996]]};kept=move.excerpt(near,0,0,16,clock)['points'];assert kept[0][1]==kept[-1][1]==.9999996,kept
        # review's figures: a visit between two close points, a fast swing's rate and its ends
        visit=move.summary({'type':'path','points':[[1,0],[1.03125,1],[1.0625,0]]},0,c120);assert visit['highest']==1 and abs(visit['fastest_pan_per_second']-64)<.7,visit
        fast=move.summary({'type':'swing','beats':.25,'width':1,'phase_beats':.03125},0,c120)
        assert fast['lowest']<-.999 and fast['highest']>.999 and abs(fast['fastest_pan_per_second']-2*np.pi/.125)<.6,fast
        # (the second review) a swing's ends are read where they fall, not at the nearest millisecond: a quarter-beat
        # triangle of width 1 at 120 turns at 31.25 ms and 93.75 ms and read 0.992
        tri=move.summary({'type':'swing','beats':.25,'width':1,'shape':'triangle'},0,c120);assert tri['lowest']==-1 and tri['highest']==1,tri
        tri2=move.summary({'type':'swing','beats':.25,'width':.6,'shape':'triangle','phase_beats':.1},.2,c120);assert tri2['lowest']==-.4 and tri2['highest']==.8,tri2
        # (the confirmation review) a note struck in the intro and held through the loop to its end sounds at the
        # loop's start too, without an attack there: its place jumps at the seam every time round
        q=with_move({'type':'path','points':[[4,0],[8,.8]]});q['clock'].update(bars=2,tempo=[[0,120]]);q['sections']=[{'id':'a','start_bar':0,'bars':2}];q.pop('harmony',None)
        q['loop']={'start_bar':1};t0=q['tracks'][0];t0['notes']=[{'id':'a','on':3,'duration':5,'pitch':60}];t0['performance']={'notes':{'a':{'velocity':80}},'cc':[]}
        for other in q['tracks'][1:]:other['notes']=[];other['performance']={'notes':{},'cc':[]}
        rejects(lambda:validate(q))
        t0['notes']=[{'id':'a','on':3,'duration':.5,'pitch':60},{'id':'b','on':5,'duration':3,'pitch':62}];t0['performance']['notes']={'a':{'velocity':80},'b':{'velocity':80}};validate(q)   # silent at the loop's start
        # the seam by the ticks the notes are played on: a note written after the loop's start and played on it, a note
        # whose gate carries it to the loop's end
        q=with_move({'type':'path','points':[[4,-1],[8,1]]});q['clock'].update(bars=2,tempo=[[0,120]]);q['sections']=[{'id':'a','start_bar':0,'bars':2}];q.pop('harmony',None)
        q['loop']={'start_bar':1};t0=q['tracks'][0];t0['notes']=[{'id':'a','on':4.02,'duration':1,'pitch':60},{'id':'b','on':7,'duration':.9,'pitch':62}]
        t0['performance']={'notes':{'a':{'velocity':80,'timing_ms':-10},'b':{'velocity':80,'gate':1.3}},'cc':[]}
        for other in q['tracks'][1:]:other['notes']=[];other['performance']={'notes':{},'cc':[]}
        rejects(lambda:validate(q));t0['performance']['notes']['b']['gate']=1;validate(q)
        # a new short field is no guess for another word; the words an agent might write for it are
        q=example();q['tracks'][2]['mix']['ramp']=[[0,0]];assert validate(q)['warnings']==["lead.mix: unknown field 'ramp'; it has no effect"],validate(q)['warnings']
        q=example();q['tracks'][2]['mix']['amplifier']={'voice':'crunch'};assert "did you mean 'amp'?" in validate(q)['warnings'][0],validate(q)['warnings']
        w=[];model.unknown_fields({'ammp':1},'synth','pad.synth',w);assert "did you mean 'amp'?" in w[0],w   # a synthesizer's own `amp` is still offered
        # a reversed part sounds over its written spans, whatever its gate
        def reversed_loop(duration,gate):
            q=with_move({'type':'path','points':[[0,-1],[4,1]]});q['clock'].update(bars=1,tempo=[[0,120]]);q['sections']=[{'id':'a','start_bar':0,'bars':1}];q.pop('harmony',None)
            q['loop']={'start_bar':0};t0=q['tracks'][0];t0['reverse']=True;t0['notes']=[{'id':'a','on':0,'duration':duration,'pitch':60}]
            t0['performance']={'notes':{'a':{'velocity':80,'gate':gate}},'cc':[]}
            for other in q['tracks'][1:]:other['notes']=[];other['performance']={'notes':{},'cc':[]}
            return q
        validate(reversed_loop(3,1.6));rejects(lambda:validate(reversed_loop(4,.5)))
        # ... or a later note of its key (a reversed part plays every note by itself, over its written span)
        q=reversed_loop(4,1);q['tracks'][0]['notes'].append({'id':'b','on':2,'duration':.25,'pitch':60});q['tracks'][0]['performance']['notes']['b']={'velocity':80}
        rejects(lambda:validate(q))
        # a bass that stands still along its path is not asked about; a kick of the drum synthesizer that moves is
        q=with_move(swing);q['tracks'][1]['mix'].pop('pan',None);q['tracks'][1]['mix']['move']={'type':'path','points':[[0,0],[16,.01]]}
        asked_small=[x['id'] for x in review(q,work/'move_review3')['questions'] if x['id'].startswith('moving_low')];assert asked_small==[f'moving_low:{q["tracks"][1]["id"]}'],asked_small   # a small move is a move
        q=with_move(swing);q['tracks'][1]['mix'].pop('pan',None);q['tracks'][1]['mix']['move']={'type':'path','points':[[0,0],[16,0]]}
        kick={'id':'kick','role':'rhythm','engine':'drum_synth','notes':[{'id':'k','on':0,'duration':.25,'pitch':36}],'performance':{'notes':{'k':{'velocity':100}},'cc':[]},
              'mix':{'level_dbfs':-20,'move':{'type':'swing','beats':2,'width':.5}}}
        q['tracks'].append(kick);save_json(work/'move_review2.json',q);s2=review(q,work/'move_review2')
        asked2=[x['id'] for x in s2['questions'] if x['id'].startswith('moving_low')];assert asked2==['moving_low:kick'],asked2
        # (the confirmation review) and so is a sampled kick written by its patch (bank 128) without the `drums` flag
        q['tracks'].append({**copy.deepcopy(kick),'id':'kick2','engine':'soundfont','program':0,'bank':128})
        asked3=[x['id'] for x in review(q,work/'move_review4')['questions'] if x['id'].startswith('moving_low')];assert asked3==['moving_low:kick','moving_low:kick2'],asked3
        # what moves a part's sound in a span of beats names a movement, and not a path that stays
        from musiclib.review import processes
        said=processes(q,0,16);assert f'{q["tracks"][0]["id"]}: movement across the image' in said and 'kick: movement across the image' in said and not any(x.startswith(q['tracks'][1]['id']+': movement') for x in said),said
        return {'refused':len(refused)+4,'mono_dip_db':facts['mono_dip_db'],'fold_loss_db':part['fold_loss_db'],'fastest':facts['fastest_pan_per_second']}
    def an_amplifier_makes_one_signal_of_a_parts_notes():
        # mix.amp (0.9 step 3): a part's notes through one chain of filters and memoryless curves, at eight times the
        # rate.  What that must do, on made signals: tones together make products that the same tones through separate
        # chains do not; the alias residue is small; silence stays silence; the block size does not matter; a change in
        # one place leaves the rest; and what is refused.
        from musiclib import amp
        from musiclib.review import review
        R=audio.RATE;db=lambda v:20*np.log10(max(float(v),1e-300));tone=lambda f,n,a=.25:a*np.sin(2*np.pi*f*np.arange(n)/R)
        def with_amp(spec,k=0):
            q=example();q['tracks'][k]['mix']['amp']=spec;return q
        for spec in ({'voice':'crunch','drive':.6},{'voice':'clean'},{'voice':'lead','input_db':-6},{'voice':'high_gain','drive':1},{'voice':'edge','drive':0},{'voice':'bass','drive':.4}):validate(with_amp(spec))
        refused=[{'drive':.5},{'voice':'stack'},{'voice':'crunch','drive':2},{'voice':'crunch','drive':'high'},{'voice':'crunch','gain':3},'crunch',{'voice':'crunch','input_db':90},
                 {'voice':['crunch']},{'voice':{'name':'crunch'}}]
        for spec in refused:rejects(lambda spec=spec:validate(with_amp(spec)))
        for spec in refused[-2:]:   # a list or an object for the voice: the message, not a TypeError (which `rejects` would take for a refusal)
            try:validate(with_amp(spec));said=None
            except ValueError as e:said=str(e)
            assert said and 'mix.amp voice' in said,said
        crunch=amp.VOICES['crunch'];bin_db=lambda y,f:db(abs(np.fft.rfft(y)[int(round(f*len(y)/R))])/(len(y)/2))
        # two tones on exact bins, no low-order product of the two on a harmonic of either
        f1,f2,n=220.0,331.0,R;pad=np.zeros(R//2);a=np.concatenate([tone(f1,n+R//2),pad]);b=np.concatenate([tone(f2,n+R//2),pad])
        both=amp.process(a+b,crunch)[R//4:R//4+n];apart=(amp.process(a,crunch)+amp.process(b,crunch))[R//4:R//4+n]
        products={k:(round(bin_db(both,f),1),round(bin_db(apart,f),1)) for k,f in (('f2-f1',f2-f1),('f1+f2',f1+f2),('2f1-f2',2*f1-f2),('2f2-f1',2*f2-f1))}
        assert all(t>-60 and t-s>40 for t,s in products.values()),products
        # alias residue: a sweep at 8 times the rate against 32 times; at the plain rate it is far worse
        secs=2;t=np.arange(secs*R)/R;f0,fe=80.0,6000.0
        sweep=.5*np.sin(2*np.pi*f0*secs/np.log(fe/f0)*(np.exp(t/secs*np.log(fe/f0))-1))
        y8,y32,y1=(amp.process(sweep,crunch,oversample=o) for o in (8,32,1));ref=db(np.sqrt(np.mean(y32**2)))
        res8,res1=db(np.sqrt(np.mean((y8-y32)**2)))-ref,db(np.sqrt(np.mean((y1-y32)**2)))-ref
        assert res8<-60 and res1>res8+20 and amp.OVERSAMPLE==8,(res8,res1)
        # silence, no offset, a tail that ends
        assert not amp.process(np.zeros(R),crunch).any()
        held=amp.process(np.concatenate([tone(196.0,R,.5),np.zeros(R//2)]),crunch)
        assert abs(float(np.mean(held[R//4:R])))<1e-4 and float(np.max(np.abs(held[-R//8:])))<1e-4
        # the block size does not matter, and a change in one place leaves the rest (the band limit rings a few samples
        # ahead of a step in the input; the filters settle within a quarter of a second after it)
        rng=np.random.default_rng(7)
        burst=np.concatenate([tone(110.0,R,.4)+tone(165.0,R,.3),np.zeros(R//4),tone(147.0,R//2,.5),np.zeros(R//4)])+1e-4*rng.standard_normal(2*R)
        ya=amp.process(burst,crunch);peak=db(np.max(np.abs(ya)));yb=amp.process(burst,crunch,block=12000)
        blocks=db(np.max(np.abs(ya-yb)))-peak;assert blocks<-100,blocks
        # the same of a harder case (the review of this feature): bursts that begin and end abruptly, the direct bank's
        # gain, drive at 1; also the same part with a second of silence after it, and an odd block size.  With the
        # band cut off sharply at half the rate these three read -85, -88 and -84 dB.
        jj=np.arange(R)%6000;hard=(.4*np.sin(2*np.pi*147*jj/R)*np.exp(-jj/4200)).astype(np.float32).astype(np.float64);g0=10**(6.27/20)
        h0=amp.process(hard,crunch,g0,1.0);hp=db(np.max(np.abs(h0)))
        hard_db=[db(np.max(np.abs(y[:R]-h0)))-hp for y in (amp.process(hard,crunch,g0,1.0,block=12000),amp.process(np.concatenate([hard,np.zeros(R)]),crunch,g0,1.0),amp.process(hard,crunch,g0,1.0,block=7001))]
        assert max(hard_db)<-150,hard_db
        gf=np.array([0,17999,18000,21000,23999,24000,30000.]);gw=amp.guard(gf);assert gw[0]==1 and gw[1]==1 and gw[2]==1 and abs(gw[3]-.5)<1e-9 and 0<gw[4]<1e-6 and gw[5]==0 and gw[6]==0,gw
        changed=burst.copy();k0,k1=int(1.30*R),int(1.45*R);changed[k0:k1]*=.25;yc=amp.process(changed,crunch)
        before,after=db(np.max(np.abs(yc[:k0-256]-ya[:k0-256])))-peak,db(np.max(np.abs(yc[k1+R//4:]-ya[k1+R//4:])))-peak
        assert before<-90 and after<-80 and db(np.max(np.abs(yc[k0:k1]-ya[k0:k1])))-peak>-40,(before,after)
        # every voice runs; more drive, more of the products
        for name,voice in amp.VOICES.items():
            y=amp.process(a+b,voice);assert np.isfinite(y).all() and y.any(),name
        def made(d):   # the share of the output that is neither tone: what the curves made of the two
            s=np.abs(np.fft.rfft(amp.process(a+b,crunch,drive=d)[R//4:R//4+n]))**2;own=s[int(f1)]+s[int(f2)];return 10*np.log10((s.sum()-own)/s.sum())
        shares=[made(d) for d in (0,.5,1)];assert shares[0]<shares[1]<shares[2] and shares[2]-shares[0]>3,shares
        def driven(g):   # the same share by the input's gain: a louder input is driven harder
            s=np.abs(np.fft.rfft(amp.process(a+b,crunch,input_gain=g)[R//4:R//4+n]))**2;return 10*np.log10((s.sum()-s[int(f1)]-s[int(f2)])/s.sum())
        by_gain=[driven(g) for g in (.5,1,2)];assert by_gain[0]<by_gain[1]<by_gain[2],by_gain
        # the power stage is a curve of its own: with the stage before it kept straight (a low gain) and the power
        # stage driven, the two tones still make products
        straight={**crunch,'stages':[{'gain_db':-30.0,'bias':0.0,'lowpass_hz':20000.0,'highpass_hz':20.0}],'power_db':55.0}
        s=np.abs(np.fft.rfft(amp.process(a+b,straight)[R//4:R//4+n]))**2;power_made=10*np.log10((s.sum()-s[int(f1)]-s[int(f2)])/s.sum())
        assert power_made>-12,power_made
        # the loudspeaker: little is left above its range
        hiss=amp.process(.2*rng.standard_normal(R),crunch);sp=np.abs(np.fft.rfft(hiss))**2;fr=np.fft.rfftfreq(R,1/R)
        top=10*np.log10(sp[(fr>=10000)&(fr<16000)].mean()/sp[(fr>=1000)&(fr<4000)].mean());assert top<-30,top
        # a part: its two channels folded to one signal, the bank's measured level where it has one
        stereo=np.stack([a+b,a+b],axis=1).astype(np.float32);part={'id':'g','soundfont':'fsbs_direct','patch':{'bank':0,'program':0},'mix':{'amp':{'voice':'crunch','drive':.5}}}
        y,facts=amp.apply(stereo,part)
        assert y.dtype==np.float32 and np.array_equal(y[:,0],y[:,1]) and facts['bank_measured'] and facts['input_gain_db']==6.27 and facts['fold_loss_db']==0,facts
        assert abs(facts['input_peak']-float(np.max(np.abs(a+b)))*10**(6.27/20))<2e-3,facts
        other={**part,'soundfont':'default','mix':{'amp':{'voice':'crunch','input_db':-3}}};_,f2s=amp.apply(stereo,other)
        assert not f2s['bank_measured'] and f2s['input_gain_db']==-3,f2s
        _,lost=amp.apply(np.stack([a+b,-(a+b)],axis=1).astype(np.float32),part);assert lost['fold_loss_db']==-120 and lost['input_peak']<1e-6,lost
        _,lost2=amp.apply(np.stack([a+b,-(a+b)],axis=1).astype(np.float32)[:R//2],part);assert lost2['fold_loss_db']==-120,lost2   # one figure, whatever the length
        # the preset is the one the synthesis plays: a patch that leaves its program out plays program 0
        partial={**part,'program':27,'patch':{'bank':0}};assert amp.bank_gain_db(partial)==6.27 and amp.bank_gain_db({**part,'patch':None,'bank':0,'program':27}) is None
        # by the file where a configuration names it: the bank under another name has its gain, another file under its name has none
        lock=json.loads((Path(__file__).resolve().parents[2]/'references'/'soundbank-lock.json').read_text(encoding='utf-8'))
        locked={i['name']:i.get('member_sha256') for i in lock['archives']}|{i['name']:i.get('output_sha256') for i in lock['builds']}
        assert set(amp.BANK_FILES)=={b for b,_ in amp.BANKS} and all(locked[b]==digest for b,digest in amp.BANK_FILES.items()),amp.BANK_FILES   # every measured bank is a file of the lock
        sha=amp.BANK_FILES['fsbs_direct']
        # the bass voice: a bass's low notes pass (the guitar voices take them out), the chain is level where it is not
        # driven (what is lowered ahead of the curve is raised after it), its loudspeaker ends lower, more drive more
        # harmonics; the bass banks' measured levels
        tt=np.arange(2*R)/R
        def small(voice,f):   # the chain's gain for a tone far too soft to be bent, in dB
            y=amp.process(1e-4*np.sin(2*np.pi*f*tt),amp.VOICES[voice])[R//2:R//2+R];return 20*np.log10(abs(np.fft.rfft(y)[f])/(R/2)/1e-4)
        low_bass,low_guitar=small('bass',41)-small('bass',165),small('crunch',41)-small('crunch',165)
        assert -6<low_bass<0 and low_guitar<-25,(low_bass,low_guitar)
        flat=[small('bass',f) for f in (120,165,250,400,660)];assert max(flat)-min(flat)<1.0,flat   # level through the shelves' corner too (two shelves that only met at the extremes left 1.9 dB at 250 Hz)
        top_bass=small('bass',8000)-small('bass',660);assert top_bass<-30,top_bass
        def harmonics(d):
            s=np.abs(np.fft.rfft(amp.process(np.sin(2*np.pi*82*tt),amp.VOICES['bass'],drive=d)[R//2:R//2+R]))**2;return 10*np.log10(s[161:].sum()/s[80:85].sum())
        bent=[harmonics(d) for d in (0,.5,1)];assert bent[0]<-25 and bent[0]+8<bent[1]<bent[2]-3 and bent[2]>-15,bent
        low_part={'id':'b','soundfont':'bass_pick','patch':{'bank':0,'program':0},'mix':{'amp':{'voice':'bass'}}}
        assert amp.bank_gain_db(low_part)==15.0 and amp.bank_gain_db({**low_part,'soundfont':'bass_finger'})==15.0
        assert amp.bank_gain_db({**low_part,'soundfont':'bass_darkblack','patch':{'bank':0,'program':33}})==18.07 and amp.bank_gain_db({**low_part,'soundfont':'bass_darkblack','patch':{'bank':1,'program':33}}) is None   # its staccato preset was not measured
        assert amp.bank_gain_db({**low_part,'soundfont':'x'},{'sha256':amp.BANK_FILES['bass_darkblack']}) is None and amp.bank_gain_db({**low_part,'soundfont':'x','patch':{'bank':0,'program':33}},{'sha256':amp.BANK_FILES['bass_darkblack']})==18.07
        assert amp.bank_gain_db({**part,'soundfont':'my_guitar'},{'sha256':sha})==6.27 and amp.bank_gain_db(part,{'sha256':'0'*64}) is None and amp.bank_gain_db({**part,'soundfont':'my_guitar'}) is None
        assert amp.bank_gain_db({**part,'engine':'synth'},{'sha256':sha}) is None
        assert amp.bank_gain_db({**part,'patch':None,'drums':True}) is None and amp.bank_gain_db({**part,'drums':True})==6.27   # a drum part without a patch plays bank 128
        # review: the amplifier in the part's summary, and a question where the bank's level was not measured
        q=with_amp({'voice':'crunch'});q['tracks'][1]['mix']['amp']={'voice':'clean','input_db':3};s=review(q,work/'amp_review')
        byid={t['id']:t for t in s['tracks']};first,second=q['tracks'][0]['id'],q['tracks'][1]['id']
        assert byid[first]['amp']=={'voice':'crunch','drive':.5,'bank_measured':False} and byid[second]['amp']['voice']=='clean'
        asked=[x['id'] for x in s['questions'] if x['id'].startswith('amp_level')];assert asked==[f'amp_level:{first}'],asked
        # the question names the preset: a bank's other preset is not called measured in the same breath
        qs=with_amp({'voice':'bass'});qs['tracks'][0].update(soundfont='bass_darkblack',patch={'bank':1,'program':33})
        told=[x['text'] for x in review(qs,work/'amp_review_preset')['questions'] if x['id'].startswith('amp_level')]
        assert len(told)==1 and '(bass_darkblack 1:33)' in told[0] and 'bass_darkblack 0:33' in told[0] and "a bass's single note" in told[0],told
        # another file configured under a measured bank's name: the question says so, and does not call one preset both
        pm={'id':'b','engine':'soundfont','soundfont':'bass_pick','patch':{'bank':0,'program':0}}
        assert amp.described(pm,{'sha256':'0'*64})=='bass_pick 0:0, which the configuration gives another file than the bank measured under this name'
        assert amp.described(pm,{'sha256':amp.BANK_FILES['bass_pick']})=='bass_pick 0:0'==amp.described(pm) and amp.described({**pm,'patch':{'bank':1,'program':0}},{'sha256':'0'*64})=='bass_pick 1:0' and amp.described({'id':'s','engine':'synth'})=='synth'
        qm=with_amp({'voice':'bass'});qm['tracks'][0].update(soundfont='bass_darkblack',patch={'bank':0,'program':33})
        assert not [x for x in review(qm,work/'amp_review_measured')['questions'] if x['id'].startswith('amp_level')]
        return {'products_db':products,'alias_8x_db':round(res8,1),'alias_1x_db':round(res1,1),'block_sizes_db':round(blocks,1),'hard_case_db':[round(v,1) for v in hard_db],'elsewhere_db':[round(before,1),round(after,1)],'refused':len(refused)}
    def a_part_played_by_string_is_checked_and_strummed_by_string():
        # Playing by string (0.9 step 3): what a part's strings and its notes' string and mute must be, the damping of a
        # muted note band by band, the fade that ends a string's note, a strum's order by string, the builder's frets.
        from musiclib import strung, expression
        from musiclib.builder import Song
        R=audio.RATE;GUITAR=[40,45,50,55,59,64]
        def strung_part(notes,**fields):
            q=example();t=q['tracks'][0];t['strings']=GUITAR;t.update(fields)
            t['notes']=[{'id':f'n{i}','on':on,'duration':d,'pitch':pitch,**more} for i,(on,d,pitch,more) in enumerate(notes)]
            t['performance']={'notes':{f'n{i}':{'velocity':90} for i in range(len(notes))},'cc':[]};return q
        chord=[(0,2,40,{'string':6}),(0,2,47,{'string':5}),(0,2,52,{'string':4}),(2,1,40,{'string':6,'mute':'palm'}),(3,.5,45,{'string':5,'mute':'dead'})]
        validate(strung_part(chord))
        q=strung_part(chord);q['tracks'][0]['strings']=[28,33,38,43];q['tracks'][0]['notes']=[{'id':'n0','on':0,'duration':1,'pitch':33,'string':3}]
        q['tracks'][0]['performance']={'notes':{'n0':{'velocity':90}},'cc':[]};validate(q)   # a bass: four strings
        def message(q):
            try:validate(q)
            except ValueError as e:return str(e)
            raise AssertionError('Expected rejection')
        assert 'it lies on string 6' in message(strung_part([(0,1,41,{})]))                     # a note without its string: told where it lies
        assert 'not on string 1' in message(strung_part([(0,1,41,{'string':1})]))               # F2 is not on the top string
        assert 'string 5 or 6' in message(strung_part([(0,1,47,{'string':2})]))                 # B2: told the strings that have it
        refused=[strung_part([(0,1,40,{'string':6,'mute':'soft'})]),strung_part([(0,1,40,{'string':7})]),strung_part([(0,1,40,{'string':True})]),
                 strung_part([(0,1,40,{'string':6}),(0,2,43,{'string':6})]),                    # one string struck twice at once
                 strung_part(chord,strings=[40,45,50]),strung_part(chord,strings=[64,59,55,50,45,40]),strung_part(chord,strings=[40,45,50,55,59,'e']),
                 strung_part(chord,reverse=True)]
        for q in refused:rejects(lambda q=q:validate(q))
        for key,value in (('legato',{'mode':'slur'}),('round_robin',True),('dynamics',[[0,60],[4,100]])):
            q=strung_part([(0,2,40,{'string':6})]);q['tracks'][0]['performance'].update({key:value,'bend_range':12});assert 'played by string' in message(q),(key,message(q))
        q=example();q['tracks'][0]['notes'][0]['string']=6;assert 'names no strings' in message(q)
        q=strung_part(chord);q['tracks'][2]['strings']=GUITAR;assert 'sampled part' in message(q)   # the additive lead
        # two notes of one string on one tick, written a hair apart: one string struck twice at once
        rejects(lambda:validate(strung_part([(1,1,40,{'string':6}),(1.0004,1,43,{'string':6})])))
        # how long a bank's voice sounds after its note ends: the longest release of the preset's zones (an
        # instrument zone's own, or its instrument's global zone's, plus the preset's), the SoundFont default where
        # none is written, and no figure where a modulator moves it
        from musiclib import sf2
        def bank_of(inst_zones,preset_zones,mods=()):
            return {'presets':[{'bank':0,'program':24,'zones':preset_zones}],
                    'instruments':[{'zones':[{'gens':g,'mods':list(mods),'target':None if k==0 and 53 not in g else g.get(53)} for k,g in enumerate(inst_zones)]}]}
        tc=sf2.timecents
        b1=bank_of([{38:tc(.3)},{53:0},{53:0,38:tc(.8)}],[{'gens':{41:0},'mods':[],'target':0}])
        assert abs(sf2.longest_release(b1,0,24)-.8)<.01 and sf2.longest_release(b1,0,25) is None
        b2=bank_of([{38:tc(.3)},{53:0}],[{'gens':{41:0,38:1200},'mods':[],'target':0}]);assert abs(sf2.longest_release(b2,0,24)-.6)<.01   # the preset's octave of timecents doubles it
        b3=bank_of([{53:0}],[{'gens':{41:0},'mods':[],'target':0}]);assert sf2.longest_release(b3,0,24)<.002
        b4=bank_of([{53:0,38:tc(.3)}],[{'gens':{41:0},'mods':[],'target':0}],mods=[(0x0102,38,1200,0,0)]);assert sf2.longest_release(b4,0,24) is None
        assert strung.tail_seconds(.2)==(.25,False) and strung.tail_seconds(None)==(strung.TAIL_UNKNOWN,True) and strung.tail_seconds(9)==(strung.TAIL_LIMIT,True) and strung.tail_seconds(2)==(2.05,False)
        # the passes: in each, a note has ended and the tail has passed before the next begins; a note's key is
        # released no later than its string's next stroke, which is what lets a long note share a pass at all
        TPQ=model.TPQ
        def arranged(notes,tail,tempo=120,perf=None,wrap=None):
            q=strung_part(notes);q['clock']['tempo']=[[0,tempo]]
            for k,v in (perf or {}).items():q['tracks'][0]['performance']['notes'][k].update(v)
            validate(q);c=Clock(q);t=q['tracks'][0]
            out=strung.passes(t,c,tail,wrap)
            for string,ns,starts,stops,ends,groups in out:
                whole={e['id']:e for e in performed(t,c)}
                assert sorted(k for g in groups for k in g)==list(range(len(ns))) and starts==[round(whole[n['id']]['start_seconds']*R) for n in ns]
                assert all(s is not None and s<=nxt for s,nxt in zip(stops[:-1],starts[1:])) and (wrap is not None or stops[:-1]==starts[1:])
                assert all(ends[n['id']]<=whole[n['id']]['end_tick'] or whole[n['id']].get('retrigger_trimmed') for n in ns)
                for g in groups:
                    # as the pass's own MIDI file plays them: its notes alone, each with its end
                    ev={e['id']:e for e in midi.synthesis_notes(strung._sub(t,[ns[k] for k in g]),c,True,None,ends)[0]}
                    assert all(ev[ns[k]['id']]['end_tick']==ends[ns[k]['id']] for k in g),(g,ends)
                    for i,j in zip(g,g[1:]):assert ev[ns[j]['id']]['start_seconds']>=ev[ns[i]['id']]['end_seconds']+tail-1e-9,(g,i,j)
            return out
        # three notes on one string, the first two carried past the next stroke by their gate: each ends at that stroke
        long3=[(0,1,40,{'string':6}),(1,1,43,{'string':6}),(2,2,45,{'string':6})];carried={'n0':{'gate':1.6},'n1':{'gate':1.6}}
        (s6,ns,_,stops,ends,groups),=arranged(long3,.25,perf=carried)
        assert s6==6 and groups==[[0,2],[1]] and ends=={'n0':TPQ,'n1':2*TPQ,'n2':4*TPQ} and stops[-1] is None,(groups,ends)
        assert [len(a[5]) for a in arranged(long3,.6,perf=carried)]==[3]
        line=[(i*.25,.25,40+i%3,{'string':6}) for i in range(16)]+[(i*1.0,1,59,{'string':2}) for i in range(4)]
        quick=arranged(line,.25);assert [(a[0],len(a[5])) for a in quick]==[(6,3),(2,2)],[(a[0],a[5]) for a in quick]   # sixteenths of 125 ms: every third shares a pass
        assert [len(a[5]) for a in arranged(line,0)]==[1,1] and [len(a[5]) for a in arranged([(0,1,40,{'string':6}),(2,1,43,{'string':6})],.25)]==[1]
        # (the review of this feature) a note's key is released where it would be, or at its string's next stroke as
        # played, whichever is first: E2 for four beats at gate 0.5 would be held a second; G2, written at beat 1 and
        # played 100 ms late, comes at 0.6 s; E2 is held until then (its written length cut to a beat and then gated
        # released it at 0.25 s)
        (_,ns,_,_,ends,_),=arranged([(0,1,40,{'string':6}),(1,1,43,{'string':6})],.25,perf={'n0':{'gate':1.6},'n1':{'timing_ms':100}})
        assert ends['n0']==round(1.2*TPQ),ends   # held to the stroke as played (0.6 s), not to the written one (0.5 s) nor to its own end (0.8 s)
        # the same pitch again on the string trims the first one in the whole part; a pass that holds the first without
        # the second still ends it there (it came back under the pass's next note, the arranged() property above)
        back=[(0,1,40,{'string':6}),(1,.125,40,{'string':6}),(1.52,.125,43,{'string':6})]
        (_,ns,_,_,ends,groups),=arranged(back,.25,perf={'n0':{'gate':1.6}});assert ends['n0']==TPQ-1 and groups[0][:2]==[0,2],(ends,groups)
        # as played, everywhere the notes are read: the roll, review, an excerpt, the exported MIDI
        q=strung_part([(0,1,40,{'string':6}),(1,.25,43,{'string':6}),(0,8,45,{'string':5})]);q['clock']['tempo']=[[0,120]];q['tracks'][0]['performance']['notes']['n0']['gate']=1.6;validate(q)
        got={e['id']:(e['end_tick'],bool(e.get('string_ended'))) for e in performed(q['tracks'][0],Clock(q))};assert got=={'n0':(TPQ,True),'n1':(TPQ+TPQ//4,False),'n2':(8*TPQ,False)},got
        # (the second review) a note is written no longer than its string lets it sound, so the readers of written
        # lengths (the views by section, review's intervals) say what sounds; the builder shortens a ringing note
        said=message(strung_part([(0,6,40,{'string':6}),(1,1,41,{'string':6})]));assert 'begins at beat 1' in said and 'write it 1 beats long' in said,said
        validate(strung_part([(0,1,40,{'string':6}),(1,1,41,{'string':6}),(0,6,45,{'string':5})]))
        # (the third review) the length the message gives is one that is accepted: in full, and no shorter than a tick
        said=message(strung_part([(0,1,40,{'string':6}),(.1171875,1,41,{'string':6})]));assert 'write it 0.1171875 beats long' in said,said
        validate(strung_part([(0,.1171875,40,{'string':6}),(.1171875,1,41,{'string':6})]))
        third=1/3;said=message(strung_part([(third,3.9,40,{'string':6}),(4,1,43,{'string':6})]));told=float(said.split('write it ')[1].split(' beats')[0])
        validate(strung_part([(third,told,40,{'string':6}),(4,1,43,{'string':6})]));assert abs(told-(4-third))<1e-9,told
        said=message(strung_part([(0,1,40,{'string':6}),(.001,1,41,{'string':6})]));told=float(said.split('write it ')[1].split(' beats')[0])
        validate(strung_part([(0,told,40,{'string':6}),(.001,1,41,{'string':6})]))
        q=strung_part(chord);q['tracks'][0]['key_map']={};assert 'key_map' in message(q)
        # a key map could move two strings onto one key; nothing a project writes can end a note early in secret
        q=strung_part(chord);q['tracks'][0]['key_map']={'40':41};assert 'key_map' in message(q),message(q)
        q=example();first_id=q['tracks'][0]['notes'][0]['id'];before=[e['end_tick'] for e in performed(q['tracks'][0],Clock(q))]
        q['tracks'][0]['performance']['notes'][first_id]['_end_tick']=1;assert [e['end_tick'] for e in performed(q['tracks'][0],Clock(q))]==before
        # an excerpt: a note its string's next stroke ended early in the piece (that stroke written in the next bar and
        # played 100 ms before it) ends there in the excerpt too; two strokes of one string that both fall on the
        # excerpt's first tick leave one
        import excerpt as cut_tool
        q2=strung_part([(3,1,40,{'string':6}),(4,1,43,{'string':6})]);q2['clock']['tempo']=[[0,120]];q2['tracks'][0]['performance']['notes']['n1']['timing_ms']=-100
        validate(q2);one=cut_tool.extract(q2,1,1);e2=performed(one['tracks'][0],Clock(one))
        assert [(e['pitch'],e['end_tick']) for e in e2]==[(40,round(3.8*TPQ))],e2
        q3=strung_part([(4,.08,40,{'string':6}),(4.08,1,43,{'string':6})]);q3['clock']['tempo']=[[0,120]]
        for k in ('n0','n1'):q3['tracks'][0]['performance']['notes'][k]['timing_ms']=-100
        validate(q3);two=cut_tool.extract(q3,2,1);validate(two);assert len(two['tracks'][0]['notes'])==1,two['tracks'][0]['notes']
        # (the third review) the excerpt of a valid part is a valid part: a note carried over the cut by its gate, its
        # string's next note written a quarter beat into the bar and played 100 ms late, is written to that note and
        # still plays to the stroke; a note that sounds a sixteenth of a second into the bar before another pitch on
        # its string is kept; a pickup played after the bar's first stroke of its string leaves a valid excerpt
        q4=strung_part([(3,1.25,40,{'string':6}),(4.25,1,43,{'string':6})]);q4['clock']['tempo']=[[0,120]]
        q4['tracks'][0]['performance']['notes']['n0']['gate']=1.6;q4['tracks'][0]['performance']['notes']['n1']['timing_ms']=100
        validate(q4);src={e['id']:e for e in performed(q4['tracks'][0],Clock(q4))};x4=cut_tool.extract(q4,2,1);got4={e['pitch']:e for e in performed(x4['tracks'][0],Clock(x4))}
        # (written to the next note, a quarter beat, it can be carried 1.6 times that by its gate: 384 ticks of the 432 it
        # sounded in the piece; the excerpt is valid and the note is there, 25 ms short of the late stroke)
        assert src['n0']['end_tick']-4*TPQ==got4[43]['tick']==432 and got4[40]['tick']==0 and got4[40]['end_tick']==384,(got4,src)
        q5=strung_part([(3,1.125,40,{'string':6}),(4.125,1,43,{'string':6})]);q5['clock']['tempo']=[[0,120]];q5['tracks'][0]['performance']['notes']['n0']['gate']=1.6
        validate(q5);x5=cut_tool.extract(q5,2,1);got5={e['pitch']:e for e in performed(x5['tracks'][0],Clock(x5))}
        assert got5[40]['tick']==0 and got5[40]['end_tick']==got5[43]['tick']==TPQ//8,got5
        q6=strung_part([(3.9375,.0625,40,{'string':6}),(4,1,43,{'string':6})]);q6['clock']['tempo']=[[0,120]];q6['tracks'][0]['performance']['notes']['n0']['timing_ms']=100
        validate(q6);x6=cut_tool.extract(q6,2,1);validate(x6);assert len(x6['tracks'][0]['notes'])==1,x6['tracks'][0]['notes']   # valid, one of the two (which the piece played in the other order: for step 5's list)
        # two strings struck on one tick as played (the second written an eighth of a beat later and played 62.5 ms early)
        q=strung_part([(1,.125,40,{'string':6}),(1.125,1,43,{'string':6})]);q['clock']['tempo']=[[0,120]];q['tracks'][0]['performance']['notes']['n1']['timing_ms']=-62.5
        assert 'both strike string 6' in message(q),message(q)
        # one pitch on two strings: struck apart it plays; on one tick it is one key twice, said with what to do
        validate(strung_part([(0,2,45,{'string':6}),(.0625,2,45,{'string':5})]))
        assert 'two ticks or more apart' in message(strung_part([(0,2,45,{'string':6}),(0,2,45,{'string':5})]))
        rejects(lambda:validate(strung_part([(0,2,45,{'string':6}),(1/TPQ,2,45,{'string':5})])));validate(strung_part([(0,2,45,{'string':6}),(2/TPQ,2,45,{'string':5})]))
        # a pedal would hold a voice past its key; a dynamics field written as null is none, and the part stays one played by string
        q=strung_part(chord);q['tracks'][0]['performance']['cc']=[[0,64,127]];assert 'pedal' in message(q),message(q)
        q=strung_part(chord);q['tracks'][0]['performance']['cc']=[[0,11,90]];validate(q)
        from musiclib import layered
        q=strung_part(chord);q['tracks'][0]['performance']['dynamics']=None;validate(q);assert not layered.wanted(q['tracks'][0])
        # where the piece loops, a string's last note is ended by the loop's first stroke on that string, a loop later
        (_,ns,starts,stops,_,_),=arranged(long3,.25,wrap=(R,7*R));assert stops[-1]==starts[2]+7*R and starts[2]==R,(starts,stops)
        (_,_,starts,stops,_,_),=arranged(long3,.25,wrap=(5*R,3*R));assert stops[-1] is None   # no stroke on the string inside the loop
        (_,_,starts,stops,_,_),=arranged(long3,.25,wrap=(0,R));assert starts[-1]==R and stops[-1]==starts[1]+R   # a note is ended by the first repeated stroke after its own start, not by one on or before it
        # a last stroke played past the loop's end by its timing: the first repeated stroke after it ends it
        late=[(0,.125,40,{'string':6}),(.25,.125,41,{'string':6}),(3.875,.125,43,{'string':6})]
        (_,_,starts,stops,_,_),=arranged(late,.25,perf={'n2':{'timing_ms':100}},wrap=(0,2*R));assert starts==[0,R//8,round(2.0375*R)] and stops==[R//8,2*R,2*R+R//8],(starts,stops)
        # the synthesis's own steps, with stand-ins for the synthesizer and the files' audio: every pass's MIDI file is
        # asked for with the whole part's ends, the passes' files are gone afterwards, the notes are counted once
        qs=strung_part(back);qs['clock']['tempo']=[[0,120]];qs['tracks'][0]['performance']['notes']['n0']['gate']=1.6;validate(qs);cs=Clock(qs)
        ts={**qs['tracks'][0],'patch':{'bank':0,'program':24}};(_,_,_,_,whole_ends,whole_groups),=strung.passes(ts,cs,strung.tail_seconds(sf2.longest_release(b1,0,24))[0])
        asked=[];stub=work/'strung_stub';stub.mkdir(exist_ok=True)
        kept=(midi.write,audio.fluidsynth,audio.read_wav,audio.write_wav,sf2.read)
        try:
            midi.write=lambda p,path,tracks,**kw:(asked.append((sorted(n['id'] for n in tracks[0]['notes']),kw.get('ends'))),Path(path).write_bytes(b'x'))[1]
            audio.fluidsynth=lambda cfg,font,mid,wav,folder,label:Path(wav).write_bytes(b'x')
            audio.read_wav=lambda path:(np.zeros((2*R,2),dtype=np.float32),R)
            audio.write_wav=lambda path,x:None
            sf2.read=lambda path:b1
            stub_facts=strung.render(qs,ts,cs,{},{'path':'none.sf2'},stub,stub/'out.wav')
        finally:
            midi.write,audio.fluidsynth,audio.read_wav,audio.write_wav,sf2.read=kept
        stub_tail=stub_facts.pop('tail_seconds');assert abs(stub_tail-.85)<.001,stub_tail   # the stand-in preset's release of 0.8 s and its margin
        assert stub_facts=={'passes':len(whole_groups),'strings':[6],'open':3,'palm':0,'dead':0,'ended_by_next_stroke':0},stub_facts
        assert [a[1] for a in asked]==[whole_ends]*len(whole_groups) and sorted(i for a in asked for i in a[0])==['n0','n1','n2'] and not list(stub.glob('strung_*')),asked
        # the take of a part played by string is the take for the loop it is in
        from musiclib.render import synthesis_identity
        qa=strung_part(long3);ca=Clock(qa);ident=lambda q,t:json.dumps(synthesis_identity(q,ca,t,{},'code'),sort_keys=True)
        ql0,ql1={**qa,'loop':{'start_bar':0}},{**qa,'loop':{'start_bar':1}}
        assert len({ident(qa,qa['tracks'][0]),ident(ql0,qa['tracks'][0]),ident(ql1,qa['tracks'][0])})==3 and ident(qa,qa['tracks'][1])==ident(ql1,qa['tracks'][1])
        assert strung.empty()['passes']==0 and set(strung.empty())=={'passes','strings','open','palm','dead','ended_by_next_stroke','tail_seconds'}
        # an audition on another engine leaves the strings out, with the notes' strings and mutes
        from musiclib.audition import with_sound
        tr=copy.deepcopy(strung_part(chord)['tracks'][0]);left=with_sound(tr,('synth','warm_pad'))
        assert 'strings' in left and 'strings' not in tr and not any('string' in n or 'mute' in n for n in tr['notes']),left
        tr=copy.deepcopy(strung_part(chord)['tracks'][0]);assert with_sound(tr,('soundfont','default',0,25))==[] and tr['strings']==GUITAR
        # damping: bands that sum to the stretch, each dying by its own time
        rng=np.random.default_rng(9);x=rng.standard_normal((R//2,2))
        same=strung.damp(x,[(60,1e6),(12000,1e6)]);assert float(np.max(np.abs(same-x)))<1e-3
        def band(y,lo,hi,a,b):
            s=np.abs(np.fft.rfft(y[int(a*R):int(b*R),0]*np.hanning(int(b*R)-int(a*R))))**2;f=np.fft.rfftfreq(int(b*R)-int(a*R),1/R)
            return 10*np.log10(max(float(s[(f>=lo)&(f<hi)].sum()),1e-30))
        # a stretch is damped the same whatever silence follows it (its pass's next note may be near or far)
        tt=np.arange(4000)/R;pluck=sum(np.sin(2*np.pi*82.41*k*tt)*np.exp(-tt*(1+k*.6))/k for k in range(1,30))*np.minimum(1,(4000-np.arange(4000))/400.)
        pluck=np.stack([pluck,pluck],axis=1);near=np.concatenate([pluck,np.zeros((2400,2))]);far=np.concatenate([pluck,np.zeros((150000,2))])
        d_near,d_far=strung.damp(near,strung.T60['palm']),strung.damp(far,strung.T60['palm'])
        apart=float(np.max(np.abs(d_near-d_far[:len(d_near)])))/float(np.max(np.abs(d_far)));assert apart<1e-4,apart
        palm,dead=strung.damp(x,strung.T60['palm']),strung.damp(x,strung.T60['dead'])
        low=band(palm,80,250,0,.05)-band(palm,80,250,.1,.15);high=band(palm,3000,8000,0,.05)-band(palm,3000,8000,.1,.15)
        assert 5<low<30 and high>50,(low,high)
        assert band(dead,80,250,0,.05)-band(dead,80,250,.1,.15)>60 and float(np.max(np.abs(palm[:8]-x[:8])))<.05*float(np.max(np.abs(x[:8])))
        # the fade that ends a note: untouched before it, silent after it
        y=np.ones((R//10,2));strung.cut(y,1000);k=int(strung.FADE_MS/1000*R)
        assert np.all(y[:1000]==1) and not y[1000+k:].any() and 0<y[1000+k//2,0]<1 and np.all(np.diff(y[1000:1000+k,0])<=0)
        # a strum goes by string: here the lower string holds the higher pitch
        prof={**expression.BASE,'strum':6,'strum_grid':.5};rng2=np.random.default_rng(1)
        group=[{'id':'a','pitch':60,'string':5},{'id':'b','pitch':55,'string':4},{'id':'c','pitch':64,'string':1}]
        down,_=expression.strum_offsets(0,group,prof,rng2);up,was_up=expression.strum_offsets(.5,group,prof,rng2)
        assert down['a'][0]<down['b'][0]<down['c'][0] and was_up and up['c'][0]<up['b'][0]<up['a'][0],(down,up)
        plain,_=expression.strum_offsets(0,[{k:v for k,v in n.items() if k!='string'} for n in group],prof,rng2)
        assert plain['b'][0]<plain['a'][0]<plain['c'][0],plain                                    # without strings: by pitch, as before
        # the builder: frets on strings
        ring=Song('Ring',bars=2,tempo=120).part('g','rhythm',engine='soundfont',keys=(35,86),strings=GUITAR)
        ring.fret(1,3,6,3,2);ring.fret(1,1,6,0,4);ring.fret(1,1,5,0,8);ring.fret(1,2,6,2,4)   # written out of order, each to ring
        assert sorted((n['on'],n['duration'],n['string']) for n in ring.track['notes'])==[(0,1,6),(0,8,5),(1,1,6),(2,2,6)],ring.track['notes']
        # two strokes a tick apart: the first is a tick long, not less; a length that is no number is left to the project's check
        near=Song('Near',bars=1,tempo=120).part('g','rhythm',engine='soundfont',keys=(35,86),strings=GUITAR)
        near.fret(1,1+160/960,6,0,1);near.fret(1,1+161/960,6,1,1);a0,b0=sorted(near.track['notes'],key=lambda n:n['on'])
        assert a0['duration']>=1/TPQ and model.tick_of(a0['on']+a0['duration'])==model.tick_of(b0['on']),(a0,b0)
        odd=Song('Odd',bars=1,tempo=120).part('g','rhythm',engine='soundfont',keys=(35,86),strings=GUITAR)
        try:odd.fret(1,1,6,0,'0.5');odd.fret(1,2,6,1,1)
        except ValueError:pass     # (a message from the note's own check is as good; a TypeError is not)
        named=Song('Names',bars=1,tempo=120).part('g','rhythm',engine='soundfont',keys=(35,86),strings=['E2','A2','D3','G3','B3','E4'])
        assert named.track['strings']==GUITAR and named.track['notes']==[] and named.fret(1,1,6,3,1) and named.track['notes'][0]['pitch']==43
        rejects(lambda:Song('Names',bars=1,tempo=120).part('g','rhythm',engine='soundfont',keys=(35,86),strings=['E2','H2','D3','G3']))
        song=Song('Frets',bars=2,tempo=120);song.section('a',2);g=song.part('g','rhythm',engine='soundfont',keys=(35,86),strings=GUITAR)
        ids=g.shape(1,1,[(6,3),(5,2),(4,0)],2,velocity=100)+[g.fret(2,1,6,0,1,mute='palm')]
        got=[(n['pitch'],n['string'],n.get('mute')) for n in song.project['tracks'][0]['notes']]
        assert got==[(43,6,None),(47,5,None),(50,4,None),(40,6,'palm')] and len(ids)==4,got
        for bad in (lambda:g.fret(1,2,7,0,1),lambda:g.fret(1,2,6,30,1),lambda:song.part('h','rhythm',engine='soundfont',keys=(35,86)).fret(1,1,6,0,1)):rejects(bad)
        # review's figures for the part (strung.summary), from the score alone: the notes on each string, the frets, the
        # muted notes, and the widest stretch between stopped notes that sound together.  An open string and a dead note
        # are left out of the stretch; a note that has ended by a stroke is not held with it.
        from musiclib import summary as said
        from musiclib.review import review
        neck=[(0,2,40,{'string':6}),(0,2,47,{'string':5}),(0,2,52,{'string':4}),(2,1,43,{'string':6}),(2,2,62,{'string':3}),
              (3,1,41,{'string':6,'mute':'palm'}),(3,.5,57,{'string':5,'mute':'dead'}),(3.5,.5,64,{'string':1})]
        q=strung_part(neck);got=strung.summary(q['tracks'][0],Clock(q))
        assert got=={'strings':GUITAR,'notes_by_string':{'1':1,'2':0,'3':1,'4':1,'5':2,'6':3},'open_notes':2,'lowest_fret':0,'highest_fret':12,
                     'muted':{'palm':1,'dead':1},'widest_reach':{'frets':6,'lowest_fret':1,'highest_fret':7,'at':'bar 1 beat 4','beat':3}},got
        line=strung_part([(0,1,41,{'string':6}),(1,1,76,{'string':1})]);assert strung.summary(line['tracks'][0],Clock(line))['widest_reach'] is None   # one after the other: nothing held together
        ring=strung_part([(0,2,41,{'string':6}),(1,1,76,{'string':1})]);assert strung.summary(ring['tracks'][0],Clock(ring))['widest_reach']=={'frets':11,'lowest_fret':1,'highest_fret':12,'at':'bar 1 beat 2','beat':1}
        early=strung_part([(0,1,41,{'string':6}),(1,1,76,{'string':1})]);early['tracks'][0]['performance']['notes']['n1']['timing_ms']=-30   # as played: the second stroke comes while the first still sounds
        assert strung.summary(early['tracks'][0],Clock(early))['widest_reach']=={'frets':11,'lowest_fret':1,'highest_fret':12,'at':'bar 1 beat 1.945','beat':.9458}   # told where it is played: 30 ms before beat 2 (at 108 BPM)
        last=strung_part([(0,4,41,{'string':6}),(4,1,76,{'string':1})]);last['clock']['tempo']=[[0,120]];last['tracks'][0]['performance']['notes']['n1']['timing_ms']=-1
        assert strung.summary(last['tracks'][0],Clock(last))['widest_reach']['at']=='bar 1 beat 4.997'   # the bar's last ticks are not told as beat 5
        both=strung_part([(0,2,47,{'string':6}),(1,1,47,{'string':5})]);assert strung.summary(both['tracks'][0],Clock(both))['widest_reach']=={'frets':5,'lowest_fret':2,'highest_fret':7,'at':'bar 1 beat 2','beat':1}   # one pitch held on two strings: both sound, as the synthesis plays them
        short=strung_part([(0,2,41,{'string':6}),(1,1,76,{'string':1})]);short['tracks'][0]['performance']['notes']['n0']['gate']=.4;assert strung.summary(short['tracks'][0],Clock(short))['widest_reach'] is None
        r=review(q,work/'strung_review');assert r['tracks'][0]['strung']==got and all('strung' not in x for x in r['tracks'][1:]),r['tracks'][0]
        told=[x for x in said.review(r,work/'strung_review').splitlines() if x.startswith('By string')]
        assert told==[f"By string, {q['tracks'][0]['id']}: notes on string 1: 1, 3: 1, 4: 1, 5: 2, 6: 3 (1 the highest); frets 0 to 12, 2 on open strings; 1 palm-muted, 1 dead-muted; widest stretch between stopped notes sounding together: 6 frets (frets 1 and 7, bar 1 beat 4)."],told
        plain=review(example(),work/'strung_review_plain');assert not any(x.startswith('By string') for x in said.review(plain,work/'strung_review_plain').splitlines())
        # The owner's review of the pull request.  In the audio a string is a voice of its own (strung.passes plays
        # each string's notes alone), so one pitch held on two strings is held on both; the whole part's MIDI events
        # end the first where the second is struck (one channel, one key).  An excerpt, the loop's guard on a
        # movement, the mix's held spans, the roll, the seam's count and notes.csv read the MIDI's events: a note held
        # for two bars under a short one of its pitch on the next string was gone from the second bar's excerpt, a
        # jump at the seam was let through, and the clarity was set from spans a quarter as long.  They read
        # model.sounded, the notes as the audio has them.
        import csv
        from excerpt import extract
        from musiclib import loop as looping, mixbus, roll
        from musiclib.model import sounded
        from musiclib.review import review as reviewed
        def on_two_strings(notes,bars,**more):
            q=strung_part(notes);q['clock'].update(bars=bars,tempo=[[0,120]]);q['clock'].pop('rubato',None);q['sections']=[dict(q['sections'][0],start_bar=0,bars=bars)]
            for k in ('harmony','chords','plan','loop'):q.pop(k,None)
            for other in q['tracks'][1:]:other['notes']=[];other['performance']={'notes':{},'cc':[]}
            q.update(more);return q
        under=[(0,8,52,{'string':6}),(1,.25,52,{'string':5})]
        q=on_two_strings(under,2);validate(q);t0=q['tracks'][0];c=Clock(q)
        assert {n['id']:n['end_tick'] for n in sounded(t0,c)}=={'n0':7680,'n1':1200} and {n['id']:n['end_tick'] for n in performed(t0,c)}['n0']==959   # (the MIDI's events are as they were)
        assert [(a,b) for a,b in sorted(mixbus.held_spans(t0,c))]==[(0.0,4.0),(0.5,0.625)],mixbus.held_spans(t0,c)
        assert {n['id']:round(n['end_seconds'],3) for n in roll.as_played(t0,c)}=={'n0':4.0,'n1':0.625},roll.as_played(t0,c)
        second=extract(q,2,1);validate(second);kept=second['tracks'][0]['notes']
        assert [(n['id'],n['on'],n['duration'],n['string']) for n in kept]==[('n0',0,4,6)],kept
        reviewed(q,work/'strung_sounded');rows={r['note_id']:float(r['end_seconds']) for r in csv.DictReader(open(work/'strung_sounded'/'notes.csv',encoding='utf-8',newline=''))}
        assert rows=={'n0':4.0,'n1':0.625},rows
        # in a loop: the held string sounds up to the seam and is struck at it, so a path from one side to the other jumps there
        q=on_two_strings([(0,4,52,{'string':6}),(1,.25,52,{'string':5})],1,loop={'start_bar':0})
        assert looping.seam(q,Clock(q))['abruptness']['sounding_at_end']=={q['tracks'][0]['id']:1},looping.seam(q,Clock(q))['abruptness']
        q['tracks'][0]['mix']['move']={'type':'path','points':[[0,-1],[4,1]]}
        try:validate(q);raise AssertionError('a jump at the seam on a part played by string')
        except ValueError as e:assert 'jump at the seam' in str(e),e
        # two strings holding one pitch across a cut are both struck again there; one key is not struck twice at once
        # (validate, and the exported MIDI), so the one the piece struck later is written two ticks on
        q=on_two_strings([(0,8,52,{'string':6}),(.5,7.5,52,{'string':5})],2);validate(q)
        second=extract(q,2,1);validate(second);kept=sorted(second['tracks'][0]['notes'],key=lambda n:n['on'])
        assert [(n['id'],round(n['on']*960),n['string']) for n in kept]==[('n0',0,6),('n1',2,5)],kept
        assert {n['id']:n['end_tick'] for n in sounded(second['tracks'][0],Clock(second))}=={'n0':3840,'n1':3840}
        whole=extract(q,1,2);validate(whole);assert [(n['id'],n['on'],n['duration']) for n in whole['tracks'][0]['notes']]==[('n0',0,8),('n1',.5,7.5)],whole['tracks'][0]['notes']
        # (a review of these fixes, run with a place to run code) the part's offset: a note written two ticks on plays
        # two ticks on, whatever the offset (its timing was set to nothing, so an offset of -20 ms brought both onto
        # the cut and one went, and +35 ms played the second 53 ticks late); swung, the two ticks are three
        for offset in (0,-20,35):
            q=on_two_strings([(0,8,52,{'string':6}),(.5,7.5,52,{'string':5})],2);q['clock']['tempo']=[[0,120],[4,90]]
            q['tracks'][0]['performance'].update(offset_ms=offset,swing={'ratio':.67});validate(q);second=extract(q,2,1);validate(second)
            played={n['id']:(n['tick'],n['end_tick']) for n in sounded(second['tracks'][0],Clock(second))}
            end=min(n['end_tick'] for n in sounded(q['tracks'][0],Clock(q)))-3840   # where the piece ends them (an earlier offset ends them earlier)
            assert played=={'n0':(0,end),'n1':(3,end)} and 3800<end<=3840,(offset,played,end)
        # a string left to ring across the cut while another string strikes its pitch just after it (a palm-muted
        # answer 62.5 ms on): both are in the passage.  On a part played by string only a strike on the same string
        # stops a note; the rule that drops a re-attack doubled within 100 ms took the ringing string's whole bar.
        q=on_two_strings([(0,11,52,{'string':6}),(4.125,.25,52,{'string':5,'mute':'palm'})],3);validate(q);second=extract(q,2,1);validate(second)
        assert {n['id']:(n['tick'],n['end_tick']) for n in sounded(second['tracks'][0],Clock(second))}=={'n0':(0,3840),'n1':(120,360)},second['tracks'][0]['notes']
        # the stem's receipt counts the notes a second strike of their key cut short in the audio, string by string
        from musiclib.render import retrigger_trims
        q=on_two_strings(under,2);assert retrigger_trims(q['tracks'][0],Clock(q))==0 and sum(n.get('retrigger_trimmed',False) for n in performed(q['tracks'][0],Clock(q)))==1
        plain=example();assert retrigger_trims(plain['tracks'][0],Clock(plain))==sum(n.get('retrigger_trimmed',False) for n in performed(plain['tracks'][0],Clock(plain)))
        # (the second review with a place to run code) The same over many seeded cuts: two or three strings, some on
        # one pitch, held across the cut or struck within a few ticks of it, as written or by their timing, under a
        # part offset of up to 300 ms either way, swing and a tempo change at the cut.  A string that sounds across
        # the cut and a quarter beat on is in the passage, to where the piece ends it.  (Placed clear of the other
        # notes as written alone, a re-attack met one as played, and the ringing string went: 292 of 1,468 such
        # pieces lost one.)
        import random
        def cuts(seed):
            rng=random.Random(seed);notes=[];each={}
            def add(i,on,duration,pitch,string,timing=0.0):
                notes.append({'id':i,'on':on,'duration':duration,'pitch':pitch,'string':string});each[i]={'velocity':90,**({'timing_ms':timing} if timing else {})}
            unison=rng.random()<.25   # two strings struck on one pitch on the cut and a little after it, no string held from before
            if unison:add('down6',4,rng.choice([1,2]),52,6);add('brush5',4+rng.choice([1/32,1/16,2/960]),rng.choice([1,2]),52,5)
            else:add('held6',0,rng.choice([8,11,6.5]),52,6)
            if unison:pass
            elif rng.random()<.6:add('held5',rng.choice([.5,1,2.25]),rng.choice([7,9]),rng.choice([52,52,57]),5)
            else:add('stroke5',4+rng.choice([0,1/960,2/960,1/16,1/8,.5]),rng.choice([.25,1]),rng.choice([52,52,57]),5,rng.choice([0,0,1.1,2.1,-1.1,40,-40]))
            if not unison and rng.random()<.4:add('held4',rng.choice([.25,3]),6,rng.choice([52,55]),4)
            offset=rng.choice([0,-20,-35,-60,-100]) if unison else rng.choice([0,0,-20,35,-100,100,-101,-150,150,-300,300])
            q=on_two_strings([],3);t0=q['tracks'][0];t0['notes']=notes
            t0['performance']={'notes':each,'cc':[],**({'offset_ms':offset} if offset else {}),**({'swing':{'ratio':rng.choice([.6,.67])}} if rng.random()<.4 else {})}
            q['clock']['tempo']=rng.choice([[[0,120]],[[0,120],[4,90]],[[0,96],[4,132]]])
            try:validate(q)
            except ValueError:return None
            source={n['id']:n for n in sounded(t0,Clock(q))};second=extract(q,2,1);validate(second)
            passage={n['id']:n for n in sounded(second['tracks'][0],Clock(second))}
            late=max(0.0,abs(offset)-100)/1000*960*2.2+16+240   # a re-attack's timing reaches 100 ms: the rest of an offset is heard (and three notes of one pitch stand two ticks apart, more under swing)
            for i,n in source.items():
                if n['tick']<3840+240 and n['end_tick']>=3840+240:   # sounds a quarter beat after the cut, struck before that
                    m=passage.get(i);want=min(7680,n['end_tick'])-3840
                    assert m is not None and abs(m['end_tick']-want)<=2 and m['tick']<=late,(seed,offset,i,m and (m['tick'],m['end_tick']),want,notes)
            return True
        assert sum(1 for seed in range(240) if cuts(seed))>200
        # and a string that holds a pitch across the cut while another strikes it on the cut: the passage is valid, and its own strike is in it
        q=on_two_strings([(0,8,52,{'string':6}),(4,1,52,{'string':5})],2);validate(q);second=extract(q,2,1);validate(second)
        assert ('n1',0,5) in [(n['id'],n['on'],n['string']) for n in second['tracks'][0]['notes']],second['tracks'][0]['notes']
        return {'refused':len(refused)+8,'palm_low_db':round(low,1),'palm_high_db':round(high,1),'widest_reach':got['widest_reach']['frets']}
    def a_stem_too_faint_to_measure_is_silent():
        # A stem with a peak but no half second above a millionth has no level: it is silent, as a stem without a peak is,
        # and is named so (the percentile of no blocks raised IndexError, a traceback: found by the review of 0.9's
        # movement in the level meter of every release).
        x=np.zeros((audio.RATE,2),dtype=np.float32);x[100]=3.6e-5;audio.write_wav(work/'faint.wav',x)
        try:audio.reference_level(work/'faint.wav')
        except ValueError as e:assert str(e)=='Silent stem',e
        else:raise AssertionError('a level was measured')
        assert audio.reference_level(work/'faint.wav','peak')<-88
        return {'peak':3.6e-5}
    found = {'bus_assignment_and_validation': bus_settings, 'church_space_decays_as_specified_and_dynamics_validate': spaces_and_dynamics, 'k_weighting_matches_bs1770': k_weighting, 'loudness_measures_gate_and_compare': loudness_measures, 'true_peak_limiter_holds_the_ceiling': true_peak_limiter, 'tonal_balance_reads_noise_and_compares_with_a_reference': tonal_reference, 'a_bell_facing_back_sounds_darker_and_further': facing, 'production_delay_duck_gate_and_mono_low_end': production_tools, 'part_saturation_keeps_loudness_and_adds_harmonics': part_saturation, 'tape_wow_flutter_and_vinyl_noise': worn_media, 'chorus_reads_its_moving_delay_between_samples': chorus_effect, 'stage_depth_moves_reflections_and_hall': stage_depth, 'range_control_lifts_soft_passages_only': range_master, 'analysis_groups_octave_doublings_and_suggests_cuts': melody_group_and_balance, 'automation_applies_per_sample_with_held_ends': automation_applies_per_sample_with_held_ends}
    found['a_part_moves_by_one_gain_for_each_channel'] = a_part_moves_by_one_gain_for_each_channel
    found['a_stem_too_faint_to_measure_is_silent'] = a_stem_too_faint_to_measure_is_silent
    def top_end_parts():
        # 0.9 step 4.  analyze said how far the master's top lies from its line and, against a genre's published
        # slope, to "look there first": at the cymbals, the low-passes, the patches.  It now says which parts carry
        # the band from 6 to 16 kHz, from the stems (each part after its own processing, before the buses, the shared
        # reverbs and the master), and beside each what bounds its top: a low-pass inside the band, an amplifier's
        # loudspeaker.  A description; no share is asked for (more percussion, more top: Elowsson and Friberg 2017).
        from musiclib.analysis import top_end,TOP_BAND
        from musiclib import summary
        q=example();ids=[t['id'] for t in q['tracks']];kit=next(t['id'] for t in q['tracks'] if t.get('drums'))
        q['tracks'][0]['mix']['lowpass']=9000;q['tracks'][1]['mix']['amp']={'voice':'bass'};q['tracks'][2]['mix'].pop('lowpass',None);q['tracks'][2]['mix']['lowpass']=18000
        power={ids[0]:1.0,ids[1]:0.0,ids[2]:3.0,kit:15.0,ids[4]:1.0}
        t=top_end(q,power)
        assert t['band_hz']==list(TOP_BAND)==[6000,16000] and [(x['part'],x['share_pct']) for x in t['by_part']]==[(kit,75.0),(ids[2],15.0),(ids[0],5.0),(ids[4],5.0),(ids[1],0.0)],t['by_part']
        row={x['part']:x for x in t['by_part']}
        assert row[kit]['drums'] and not row[ids[0]]['drums'] and t['drums_share_pct']==75.0
        assert row[ids[0]]['lowpass_hz']==9000 and 'lowpass_hz' not in row[ids[2]] and row[ids[1]]['amp']=='bass' and 'amp' not in row[kit],row   # a low-pass above the band is not one that bounds it
        assert top_end(q,{i:0.0 for i in ids})['by_part']==[] and top_end(q,{})['drums_share_pct'] is None,'silence, or no stems: nothing to share out'
        line=summary.top_end_line({'top_end':t})
        assert line.startswith('Top end (6-16 kHz) by part, from the stems: ') and f'{kit} 75%' in line and 'drum parts 75%' in line and f'{ids[0]} 5% (low-pass 9000 Hz)' in line and f'{ids[1]} 0% (low-pass 14000 Hz, amp bass)' in line and f'{ids[2]} 15%,' in line,line
        assert summary.top_end_line({})=='' and summary.top_end_line({'top_end':top_end(q,{})})==''
        # The second review.  (1) A stem's power is its two channels' power: a part panned hard to one side at equal
        # power had half the share of the same part in the middle (the stem was folded to one channel first), and
        # a top out of phase between the sides had none.
        from musiclib.analysis import top_power
        R=audio.RATE;tt=np.arange(R)/R;tone=.1*np.sin(2*np.pi*8000*tt);zero=np.zeros_like(tone)
        mid,side,anti=np.stack([tone,tone],1),np.stack([tone*2**.5,zero],1),np.stack([tone,-tone],1)
        assert abs(top_power(side)/top_power(mid)-1)<.01 and abs(top_power(anti)/top_power(mid)-1)<.01 and top_power(np.stack([zero,zero],1))==0,(top_power(mid),top_power(side),top_power(anti))
        # (2) The shares are of the powers themselves and add up: sixty-four equal drum parts are 100% drums (their
        # rounded shares added up to 102.4), the fifty-six not shown 87.5%; the order is the powers', not the
        # rounded shares' (eight parts of power 1 came before one of 1.001).
        even=copy.deepcopy(q);even['tracks']=[{**copy.deepcopy(next(t for t in q['tracks'] if t.get('drums'))),'id':f'd{k}'} for k in range(64)]
        te=top_end(even,{f'd{k}':1.0 for k in range(64)});line=summary.top_end_line({'top_end':te})
        assert te['drums_share_pct']==100.0 and 'the other 56 parts 87.5%' in line and 'drum parts 100%' in line,(te['drums_share_pct'],line)
        nine=copy.deepcopy(q);nine['tracks']=[{**copy.deepcopy(q['tracks'][2]),'id':f'p{k}'} for k in range(9)]
        assert top_end(nine,{**{f'p{k}':1.0 for k in range(8)},'p8':1.001})['by_part'][0]['part']=='p8'
        # (3) A drum part is one the mix sends to the drum bus: written by hand with the role and a kit's patch and
        # no `drums` flag, it was not counted with the drums.
        by_role=copy.deepcopy(q);kit_part=next(t for t in by_role['tracks'] if t.get('drums'));kit_part.pop('drums');kit_part['role']='drums'
        assert top_end(by_role,power)['drums_share_pct']==75.0
        # the third review: a drum part is one by what it is (the flag, a drum machine, the role, a kit's patch),
        # wherever the mix sends it: a kit sent to another bus is still the drums' share.  And a share is given to
        # three decimals, so that the summary's "other parts" is right to its one: eight parts of 11.116% and a
        # ninth of 11.072% (it printed 11.0 for 11.1).
        sent=copy.deepcopy(q);next(t for t in sent['tracks'] if t.get('drums'))['mix']['bus']='fx';assert top_end(sent,power)['drums_share_pct']==75.0
        nine2=copy.deepcopy(q);nine2['tracks']=[{**copy.deepcopy(q['tracks'][2]),'id':f'p{k}'} for k in range(9)]
        assert 'the other 1 parts 11.1%' in summary.top_end_line({'top_end':top_end(nine2,{**{f'p{k}':11116.0 for k in range(8)},'p8':11072.0})})
        # the third review: the files a draft removes are those a finished full render's own report says it delivered
        from musiclib.render import earlier_delivery
        layer=lambda lid,*kinds:{lid:{'tracks':['a'],'files':{k:f'layers/{lid}.{k}' for k in kinds}}}
        done={'status':'TECHNICAL_PASS_AUDITION_PENDING','draft':False,'checks':{'tail_quiet':True},
              'loop':{'files':{'wav':'loop.wav','ogg':'loop.ogg'},'layers':{'parts':{**layer('base','wav','ogg'),**layer('top','wav','ogg')}}}}
        assert earlier_delivery(done)==['master.flac','loop.ogg','layers/base.wav','layers/base.ogg','layers/base_premix.filtergraph.txt','layers/top.wav','layers/top.ogg','layers/top_premix.filtergraph.txt']
        # (the confirmation review) by what that report lists: where the FFmpeg had no Vorbis encoder no Ogg copy was
        # made, of the loop or of a layer, and a file of that name in the folder is not the render's
        plain={**done,'loop':{'files':{'wav':'loop.wav'},'layers':{'parts':layer('base','wav')}}}
        assert earlier_delivery(plain)==['master.flac','layers/base.wav','layers/base_premix.filtergraph.txt']
        assert earlier_delivery({**done,'loop':{'files':{'wav':'loop.wav'}}})==['master.flac'] and earlier_delivery({k:v for k,v in done.items() if k!='loop'})==['master.flac']
        # a full render that failed a delivery check had made its files before it was checked (they would lie beside
        # the draft's newer master); one stopped before its report made none that is known
        assert earlier_delivery({**done,'status':'FAIL','checks':{'tail_quiet':False}})==earlier_delivery(done)
        for other in ({'status':'FAIL','draft':False,'failed':{'error':'stopped'}},{'status':'FAIL','draft':False,'failed':{'error':'stopped'},'checks':{}},
                      {'status':'DRAFT_PASS','draft':True,'checks':{}},{'status':'TECHNICAL_PASS_AUDITION_PENDING','draft':False},{},None,[]):
            assert earlier_delivery(other)==[],other
        # a layer's name in a report is taken only as a layer may be named
        assert earlier_delivery({**done,'loop':{'files':{},'layers':{'parts':layer('../x','wav')}}})==['master.flac']
        # the shares are kept as they are computed, so that a figure printed to one decimal is rounded once: a ninth
        # part of 16 beside eight of 29 has 6.4516% (6.4 was printed), and 13 beside 94 has 12.1495% (12.2)
        assert 'the other 1 parts 6.5%' in summary.top_end_line({'top_end':top_end(nine2,{**{f'p{k}':29.0 for k in range(8)},'p8':16.0})})
        assert 'p1 12.1%' in summary.top_end_line({'top_end':top_end({**nine2,'tracks':nine2['tracks'][:2]},{'p0':94.0,'p1':13.0})})
        # a kit by its patch is a sampled part on bank 128, wherever the patch is written; a synthesizer's `bank` is
        # its exported MIDI's and says nothing of its sound
        from musiclib.review import kit as is_kit,unpitched as no_pitch
        assert is_kit({'engine':'soundfont','bank':128,'patch':{}}) and no_pitch({'engine':'soundfont','bank':128,'patch':{},'notes':[]})
        assert not is_kit({'engine':'synth','bank':128}) and not is_kit({'engine':'additive','patch':{'bank':128}}) and not no_pitch({'engine':'synth','bank':128,'notes':[]})
        many=copy.deepcopy(q);many['tracks']=[{**copy.deepcopy(q['tracks'][2]),'id':f'p{k}'} for k in range(12)]
        line=summary.top_end_line({'top_end':top_end(many,{f'p{k}':float(12-k) for k in range(12)})})
        assert 'p7' in line and 'p8' not in line and 'the other 4 parts' in line,line
        return {'parts':len(t['by_part'])}
    found['analysis_names_the_parts_that_carry_the_top'] = top_end_parts
    found['an_amplifier_makes_one_signal_of_a_parts_notes'] = an_amplifier_makes_one_signal_of_a_parts_notes
    found['a_part_played_by_string_is_checked_and_strummed_by_string'] = a_part_played_by_string_is_checked_and_strummed_by_string
    def a_headphone_version_places_every_part():
        # mix.headphones (0.9 step 3, musiclib/ears.py): the responses as shipped, a point heard from a direction by two
        # gains ahead of fixed filters, the room's first reflections as one fixed pair, a part as one point or two, its
        # place from its pan, its movement or mix.around, what is refused, and what the mix leaves out for two ears.
        import hashlib
        from musiclib import ears, mixbus
        from musiclib.review import review
        import excerpt as cut_tool
        R=audio.RATE;h,step=ears.ring();note=json.loads((ears.ASSET/'ring72_48k.json').read_text(encoding='utf-8'))
        # 0.9, before its release: the responses are text, the source's 24-bit integer samples one line a direction and
        # ear, since the published repository holds nothing binary but images (its own test said so of the array
        # file).  Divided by 2**23 they are the 32-bit floats of before, to the bit: the array's hash is unchanged.
        data=ears.ASSET/note['data'];held=data.read_bytes();assert data.suffix=='.txt' and b'\0' not in held and held.isascii(),data.name
        lines=held.decode('ascii').splitlines();assert len(lines)==144 and all(len(x.split())==256 for x in lines),len(lines)
        raw=(np.array(held.split(),dtype=np.int64).reshape(72,2,256)/2**23).astype('<f4');assert int(np.abs(np.array(held.split(),dtype=np.int64)).max())<2**23
        assert h.shape==(72,2,256) and step==5 and hashlib.sha256(np.ascontiguousarray(raw,dtype='<f4').tobytes()).hexdigest()==note['array_sha256']=='0d2246078b30a25fd3347f673e601528f6904c54d4492841315ea12f60020a05'
        assert (ears.ASSET/'LICENSE.txt').read_text(encoding='utf-8').lstrip().startswith('Apache License') and 'Apache-2.0' in ears.source()['licence'] and note['changes']
        assert abs(float(np.mean(np.sum(h**2,axis=2)))-1)<1e-9      # one factor for the whole ring: its mean power is 1
        # degrees run clockwise: at 90 the right ear is the louder and the earlier one, at -90 the left; ahead neither
        def ear(deg):
            out=np.zeros((600,2));click=np.zeros(300);click[0]=1;ears.point(click,deg,out);e=(out**2).sum(axis=0)
            return 10*np.log10(e[1]/e[0]),int(np.argmax(np.abs(np.correlate(out[:,0],out[:,1],'full'))))-599
        (r90,l90),(rm,lm),(r0,l0)=ear(90),ear(-90),ear(0)
        assert r90>10 and l90>20 and rm<-10 and lm<-20 and abs(r0)<2 and abs(l0)<=2,(r90,l90,rm,lm,r0,l0)
        # a place on a measured direction is that direction's pair; halfway between two is half of each
        rng=np.random.default_rng(5);x=rng.standard_normal(40000)*np.hanning(40000)
        def at(deg):
            out=np.zeros((len(x),2));ears.point(x,deg,out);return out
        j=lambda deg:int(round(-deg/step))%72
        plain=lambda k:np.stack([np.convolve(x,h[k,0])[:len(x)],np.convolve(x,h[k,1])[:len(x)]],axis=1)
        close=lambda a,b,tol=1e-9:float(np.max(np.abs(a-b)))<=tol*max(1.0,float(np.max(np.abs(b))))
        assert close(at(45.0),plain(j(45))) and close(at(47.5),.5*plain(j(45))+.5*plain(j(50))) and close(at(-90.0),plain(18)) and close(at(270.0),at(-90.0))
        low,high,g0,g1=ears.gains(np.linspace(-400,800,5001));assert close(g0+g1,np.ones(5001)) and bool(np.all((g0>=0)&(g1>=0))) and bool(np.all(high==(low+1)%72))
        # a moving point is the definition (each direction's signal through its own pair), whatever the block size
        turn=720*np.arange(len(x))/len(x)-90
        def definition():
            low,high,g0,g1=ears.gains(turn);out=np.zeros((len(x),2))
            for k in range(72):
                bus=x*(np.where(low==k,g0,0.0)+np.where(high==k,g1,0.0))
                if bus.any():
                    for e in (0,1):out[:,e]+=np.convolve(bus,h[k,e])[:len(x)]
            return out
        ref=definition();assert close(at(turn),ref)
        kept=ears.BLOCK
        try:
            for size in (1000,7001):
                ears.BLOCK=size;assert close(at(turn),ref),size
        finally:ears.BLOCK=kept
        # the room's first reflections: eight, each after the direct sound and under it, the nearest wall's first (to
        # the left); one fixed pair of filters, silent before the first of them, ended well inside its length
        taps=ears.reflections();assert len(taps)==8 and all(.015<d<.045 and g<.25 for d,g,_ in taps) and taps[0][2]==270 and taps==sorted(taps)
        pair=ears.early();top=float(np.max(np.abs(pair)));e_early=np.sum(pair**2,axis=1)
        first=slice(int(.0185*R),int(.0225*R));assert float(np.sum(pair[0,first]**2))>2*float(np.sum(pair[1,first]**2))   # the nearest wall is to the left
        assert pair.shape==(2,ears.EARLY_TAPS) and float(np.max(np.abs(pair[:,:int(.012*R)])))<1e-3*top and float(np.max(np.abs(pair[:,3000:])))<1e-3*top and bool(np.all((e_early>.03)&(e_early<.3))),e_early
        # a part: one signal on both channels is one point; of two channels that differ, what they share stands at the
        # part's place and what differs is spread either side, at SIDE_GAIN, the right side inverted
        c=Clock(example());track={'id':'p','mix':{'pan':.5}};mono=np.stack([x,x],axis=1)
        y1,f1=ears.place(mono,track,c,room=False)
        assert f1=={'points':1,'by':'pan','lowest_degrees':35.0,'highest_degrees':35.0} and y1.dtype==np.float32 and float(np.max(np.abs(y1-at(35.0))))<1e-5
        other=rng.standard_normal(len(x))*np.hanning(len(x));st=np.stack([x,other],axis=1);y2,f2=ears.place(st,track,c,room=False)
        shared,differs=(x+other)/2,(x-other)/2;two=np.zeros((len(x),2));ears.point(shared,35.0,two)
        ears.point(ears.SIDE_GAIN*differs,35.0-ears.SPREAD,two);ears.point(-ears.SIDE_GAIN*differs,35.0+ears.SPREAD,two)
        assert f2['points']==3 and abs(f2['side_db'])<1 and float(np.max(np.abs(y2-two)))<1e-5 and abs(ears.SIDE_GAIN**2-.5)<1e-12,f2
        tiny=2.0**-18;_,f_tiny=ears.place(np.stack([.5*x*(1+tiny),.5*x*(1-tiny)],axis=1).astype(np.float32),track,c,room=False);assert f_tiny['points']==3 and f_tiny['side_db']<-100,f_tiny   # any difference, however small
        # ... so nothing changes by a step where two channels come to differ (the first build made two points of them
        # above a threshold: 6 dB more into the room and as much at the place), and a part keeps about its stem's power
        s0=x;near=[ears.place(np.stack([(1+d)*s0,(1-d)*s0],axis=1),track,c)[0].astype(np.float64) for d in (0.0,.0099,.0101)]
        assert float(np.max(np.abs(near[1]-near[0])))<.02*float(np.max(np.abs(near[0]))) and float(np.max(np.abs(near[2]-near[1])))<.001*float(np.max(np.abs(near[0])))
        kept_db=10*np.log10(float(np.sum(y2.astype(np.float64)**2))/float(np.sum(st**2)));assert abs(kept_db)<3,kept_db
        y3,_=ears.place(mono,track,c);wet=np.zeros((len(x),2));ears.convolved(x,pair,wet)
        assert wet.any() and float(np.max(np.abs(y3-(at(35.0)+wet))))<1e-5
        whole=np.zeros((len(x)+ears.EARLY_TAPS,2));ears.convolved(np.concatenate([x,np.zeros(ears.EARLY_TAPS)]),pair,whole)
        direct=np.stack([np.convolve(x,pair[0]),np.convolve(x,pair[1])],axis=1);assert close(whole[:len(direct)],direct,1e-8)   # the pair in blocks is the pair
        silent,f0=ears.place(np.zeros((R,2),dtype=np.float32),track,c);assert not silent.any() and f0['points']==1
        # the place: from the pan, with the part's movement, standing, along a path, in a turn (by beats, either way)
        q=example();q['clock']['tempo']=[[0,120]];c120=Clock(q);secs=np.array([0,1,2,4.0])
        deg=lambda mix:[round(float(v),3) for v in ears.degrees_at({'id':'p','mix':mix},c120,secs)]
        assert deg({'pan':-1})==[-70.0]*4 and deg({})==[0.0]*4 and deg({'pan':.2,'around':135})==[135.0]*4
        assert deg({'move':{'type':'path','points':[[0,-1],[8,1]]}})==[-70.0,-35.0,0.0,70.0]            # 8 beats are 4 s at 120
        assert deg({'around':{'type':'path','points':[[0,0],[8,360]]}})==[0.0,90.0,180.0,360.0]
        assert deg({'pan':.5,'around':{'type':'turn','beats':8}})==[35.0,125.0,215.0,395.0]
        assert deg({'around':{'type':'turn','beats':8,'direction':'left','from':10,'phase_beats':2}})==[-80.0,-170.0,-260.0,-440.0]
        assert [round(float(v),3) for v in ears.degrees({'id':'p','mix':{'around':{'type':'turn','beats':8}}},c120,R,2)]==[90.0,round(90+360/(4*R),3)]
        # what is accepted and what is refused
        def hp(spec=True,**mix):
            q=example();q['mix']['chain']='bus';q['mix']['headphones']=spec;q['tracks'][0]['mix'].update(mix);return q
        for q in (hp(),hp({}),hp({'reflections':False}),hp(False),hp(around=-90),hp(around={'type':'path','points':[[0,0],[8,720]]}),hp(around={'type':'turn','beats':16,'direction':'left'})):validate(q)
        refused=[hp('on'),hp(1),hp({'room':True}),hp({'reflections':'no'}),hp(around='left'),hp(around=True),hp(around=None),hp(around=400),hp(around={'type':'orbit','beats':8}),
                 hp(around={'type':'path','points':[[0,0]]}),hp(around={'type':'path','points':[[4,0],[4,90]]}),hp(around={'type':'path','points':[[0,0],[99,90]]}),
                 hp(around={'type':'turn'}),hp(around={'type':'turn','beats':0}),hp(around={'type':'turn','beats':8,'direction':'up'}),hp(around={'type':'turn','beats':8,'speed':2})]
        def message(q):
            try:validate(q)
            except ValueError as e:return str(e)
            raise AssertionError(('accepted',q['mix'],q['tracks'][0]['mix']))
        for q in refused:assert message(q)
        q=example();q['mix']['chain']='bus';q['tracks'][0]['mix']['around']=90;assert '"headphones": true' in message(q)
        q=hp();q['mix']['chain']='room';assert 'bus' in message(q)
        q=hp();q['loop']={'start_bar':0};assert 'looped' in message(q)
        assert ears.wanted(hp()) and ears.wanted(hp({})) and not ears.wanted(hp(False)) and not ears.wanted(example())
        assert ears.with_reflections(hp()) and ears.with_reflections(hp({})) and not ears.with_reflections(hp({'reflections':False}))
        # the part before its place; the project as the headphone version is mixed; a passage without one
        t0={'id':'p','mix':{'pan':.3,'depth_m':2,'facing':'back','move':1,'around':2,'level_dbfs':-20,'width':.5}}
        assert ears.unplaced(t0)['mix']=={'level_dbfs':-20,'width':.5} and t0['mix']['pan']==.3
        mp=ears.mix_project({'mix':{'chain':'bus','mono_below_hz':120,'loudness':'loud','headphones':True,'target_lufs':-9},'tracks':[t0]})
        assert mp['mix']=={'chain':'bus','loudness':'loud','target_lufs':-9} and mp['tracks'][0]['mix']=={'level_dbfs':-20,'width':.5}   # no stage depth to raise a send
        # a loud master's soft clip with one gain for both ears: the ears keep their level against each other where the
        # curve works, a signal that is the same in both is clipped as ever, and one under the knee is left alone
        tt=np.arange(R//4)/R;loudL=np.sin(2*np.pi*220*tt);two=np.stack([loudL,.25*loudL],axis=1)
        tied=np.asarray(mixbus.soft_clip(two,.5,split=True,linked=True),dtype=np.float64);apart=np.asarray(mixbus.soft_clip(two,.5,split=True),dtype=np.float64)
        mid=slice(2000,-2000);assert float(np.max(np.abs(tied[mid,1]-.25*tied[mid,0])))<1e-4 and float(np.max(np.abs(tied[mid,0])))<.5001
        assert float(np.max(np.abs(apart[mid,1]-.25*two[mid,0])))<1e-4 and float(np.max(np.abs(apart[mid,1]-.25*apart[mid,0])))>.05   # by itself the quieter ear is not touched
        same=np.stack([loudL,loudL],axis=1);assert float(np.max(np.abs(np.asarray(mixbus.soft_clip(same,.5,split=True,linked=True),dtype=np.float64)-np.asarray(mixbus.soft_clip(same,.5,split=True),dtype=np.float64))))<1e-5
        small=.3*two;assert float(np.max(np.abs(np.asarray(mixbus.soft_clip(small,.5,split=True,linked=True),dtype=np.float64)[mid]-small[mid])))<1e-5
        w=ears.without(hp(around=90));assert 'headphones' not in w['mix'] and 'around' not in w['tracks'][0]['mix'];validate(w)
        # the delivery's own steps, with stand-ins for the mix, the master and the files: every part placed and written,
        # the mix and the master asked for two ears, on the project without what treats the ears apart
        from musiclib import files as files_mod
        qd=hp(around=90);qd['mix'].update(mono_below_hz=120,loudness='loud',target_lufs=-9);seen={'wrote':[]};frames_d=R
        qd['tracks'][-1]['mix']['depth_m']=6;validate(qd)   # a stage position, which the headphone mix leaves out: its place is the direction
        kept_d=(mixbus.mix,mixbus.master,mixbus.verify,audio.read_wav,audio.write_wav,files_mod.stage_copy,files_mod.replace)
        try:
            mixbus.mix=lambda p,clock,cfg,out,frames,**kw:seen.update(mix=(sorted(p['mix']),kw),tracks=[dict(t['mix']) for t in p['tracks']]) or {'assignment':{}}
            mixbus.master=lambda p,cfg,out,**kw:seen.update(master=(sorted(p['mix']),kw)) or (None,{'limiting_db':None},{'true_peak_dbtp':-3.0,'clipped_samples':0,'frames':frames_d,'integrated_lufs':-9.0})
            mixbus.verify=lambda p,out,buses:{'adds_up_to_premix':True}
            audio.read_wav=lambda path:(np.zeros((frames_d,2),dtype=np.float32),R)
            audio.write_wav=lambda path,x:seen['wrote'].append((Path(path).parent.name,Path(path).name,np.asarray(x).shape[1]))
            files_mod.stage_copy=lambda src,dest:Path(dest);files_mod.replace=lambda src,dest:None
            delivered=ears.deliver(qd,Clock(qd),{},work/'ears_stub',frames_d)
            # the copy of the finished file is not left beside one that cannot be replaced
            stray=work/'ears_stub'/'.headphones.copy'
            def staged(src,dest):stray.write_bytes(b'x');return stray
            def no_replace(src,dest):raise PermissionError('in use')
            files_mod.stage_copy,files_mod.replace=staged,no_replace
            try:ears.deliver(qd,Clock(qd),{},work/'ears_stub',frames_d);raise AssertionError('replaced')
            except PermissionError:pass
            assert not stray.exists()
        finally:
            mixbus.mix,mixbus.master,mixbus.verify,audio.read_wav,audio.write_wav,files_mod.stage_copy,files_mod.replace=kept_d
        assert seen['mix'][1]=={'ears':True} and seen['master'][1]=={'ears':True} and 'mono_below_hz' not in seen['mix'][0] and 'headphones' not in seen['master'][0] and 'loudness' in seen['master'][0],seen
        every=sorted(f'{t["id"]}.wav' for t in qd['tracks'])
        assert sorted(n for d,n,ch in seen['wrote'][:2*len(every)] if (d,ch)==('stems',2))==every and sorted(n for d,n,ch in seen['wrote'][:2*len(every)] if (d,ch)==('mixin',4))==every,seen['wrote']
        assert delivered['left_out']==['mono_below_hz',"the buses' saturation"] and delivered['file']=='headphones.wav'
        # (the owner's review: this read a literal empty mix and could not fail) the parts as the mixer got them hold no stage position, and the project's own still does
        assert len(seen['tracks'])==len(qd['tracks']) and all('depth_m' not in m for m in seen['tracks']) and qd['tracks'][-1]['mix']['depth_m']==6,seen['tracks']
        # the mix's graph for two ears, with stand-ins for FFmpeg: one input a part (four channels: placed, and before its
        # place for the sends), the sends from channels 2 and 3, a stage depth raising no send; the ordinary graph as ever
        qg=hp();g_tracks=qg['tracks'][:4]
        for t,(rv,dl) in zip(g_tracks,((None,None),(-18,None),(None,-20),(-18,-20))):t['mix'].update(reverb_db=rv,delay_db=dl)
        g_tracks[1]['mix']['depth_m']=10;qg['tracks']=g_tracks;qg['mix']['rules']=1
        kept_g=(audio.ffmpeg,audio.graph_file,audio.write_wav,audio.afir_options);graphs={}
        try:
            audio.write_wav=lambda path,x:None;audio.afir_options=lambda cfg:'dry=10'
            audio.graph_file=lambda cfg,path,text:graphs.update(text=text) or ['-filter_complex_script','x']
            audio.ffmpeg=lambda cfg,args,logs,label:graphs.update(inputs=[str(a) for a in args[:args.index('-filter_complex_script')] if str(a)!='-i'])
            mixbus.mix(ears.mix_project(qg),Clock(qg),{},work/'ears_graph',R,ears=True);two_ears=dict(graphs)
            mixbus.mix(qg,Clock(qg),{},work/'ears_graph_plain',R);ordinary=dict(graphs)
        finally:
            audio.ffmpeg,audio.graph_file,audio.write_wav,audio.afir_options=kept_g
        assert len(two_ears['inputs'])==len(ordinary['inputs'])==4+len(mixbus.SPACES) and all('mixin' in i for i in two_ears['inputs'][:4]) and all('mixin' not in i for i in ordinary['inputs'])
        gt=two_ears['text'];assert gt.count('pan=stereo|c0=c0|c1=c1')==4 and gt.count('pan=stereo|c0=c2|c1=c3')==3 and '[r1]volume=-18.000000dB' in gt and '[r3]volume=-18.000000dB' in gt and 'asoftclip' not in gt,gt
        assert 'pan=stereo' not in ordinary['text'] and '[r1]volume=-18.000000dB' not in ordinary['text'] and 'asoftclip' in ordinary['text']   # (in the ordinary mix the depth raises the send)
        # a damaged or foreign set of responses is said, not thrown
        real,cached=ears.ASSET,dict(ears._cache);good=json.loads((real/'ring72_48k.json').read_text(encoding='utf-8'))
        def spoiled(name,note=None,array=None,drop=False):
            # (a copy written file by file: copied as a tree it would keep a read-only install's permissions)
            bad=work/f'ears_asset_{name}';bad.mkdir(exist_ok=True)
            for f in real.iterdir():(bad/f.name).write_bytes(f.read_bytes())
            if note is not None:(bad/'ring72_48k.json').write_text(note,encoding='utf-8')
            if array is not None:(bad/good['data']).write_bytes(array)
            return bad
        zeros=('\n'.join(' '.join('0' for _ in range(256)) for _ in range(144))+'\n').encode('ascii')
        whole_text=(real/good['data']).read_bytes()
        try:
            for name,kw in (('null',{'note':'null'}),('zeros',{'array':zeros}),('short',{'array':b''}),('words',{'array':whole_text.replace(b' ',b' x ',1)}),
                            ('reshaped',{'note':json.dumps({**good,'shape':[36,2,512]})}),   # the third review: the same samples in another shape pass the hash
                            ('cut',{'array':whole_text[:len(whole_text)//2]}),('large',{'array':whole_text.replace(whole_text.split()[0],b'99999999',1)}),
                            ('unsourced',{'note':json.dumps({**good,'source':None})}),('unhashed',{'note':json.dumps({k:v for k,v in good.items() if k!='array_sha256'})})):
                ears.ASSET=spoiled(name,**kw);ears._cache.clear()
                try:ears.ring();raise AssertionError(name)
                except ValueError as e:assert 'install the skill again' in str(e),(name,str(e))
        finally:
            ears.ASSET=real;ears._cache.clear();ears._cache.update(cached)
        assert ears.source()['doi']=='10.5281/zenodo.12092466'
        plain_q=example();assert ears.without(plain_q) is plain_q
        # an excerpt goes on where the piece stands
        assert ears.excerpt(135,0,4,8,c120)==135 and ears.excerpt({'type':'turn','beats':8},.5,6,10,c120)=={'type':'turn','beats':8,'from':35.0,'phase_beats':6}
        assert ears.excerpt({'type':'path','points':[[0,0],[8,360],[16,0]]},0,4,12,c120)=={'type':'path','points':[[0,180.0],[4,360],[8,180.0]]}
        got=cut_tool.extract(hp(around={'type':'turn','beats':8}),2,2);validate(got);assert got['tracks'][0]['mix']['around']['phase_beats']==4 and got['mix']['headphones'] is True
        # the buses without their saturation: every curve gone, every compressor kept, each line still a filter
        lines=(mixbus.DRUM_BUS+mixbus.DRUM_BUS_2+[f'[sum_{b}]{mixbus.BUS_FILTER[b]}[bus_{b}]' for b in ('bass','rhythm','lead','ensemble','fx')]
               +[f'[sum_{b}]{mixbus.BUS_FILTER_2[b]},apad,atrim=end_sample=9[bus_{b}]' for b in ('bass','rhythm')])
        dry=[mixbus.unsaturated(l) for l in lines]
        assert not any('asoftclip' in l or 'aresample' in l or ',,' in l or ',[' in l or '][' in l.split(']',1)[1] and 'amix' not in l and 'asplit' not in l for l in dry),dry
        assert sum('acompressor' in l for l in dry)==sum('acompressor' in l for l in lines)==6 and dry[0]==lines[0] and '[sum_bass]anull[bus_bass]' in dry
        # review: each part's place in the headphone version, from the score
        s=review(hp(around={'type':'turn','beats':8}),work/'ears_review');byid={t['id']:t for t in s['tracks']};ids=[t['id'] for t in example()['tracks']]
        assert byid[ids[0]]['around']['by']=='turn' and byid[ids[1]]['around']=={'by':'pan','lowest_degrees':0.0,'highest_degrees':0.0}
        assert 'around' not in review(example(),work/'ears_review_plain')['tracks'][0]
        # a part that follows its movement: review's range is the movement's own (a visit between two hundredths of a
        # second, a quick swing's ends), as the render's is
        qm=hp(move={'type':'path','points':[[0,0],[.01,1],[.02,0]]});qm['tracks'][0]['mix'].pop('pan',None);qm['clock']['tempo']=[[0,120]]
        assert review(qm,work/'ears_review_move')['tracks'][0]['around']=={'by':'pan and move','lowest_degrees':0.0,'highest_degrees':70.0}
        qr=hp(move={'type':'path','points':[[0,0],[1,.0625]]});qr['tracks'][0]['mix'].pop('pan',None)
        assert review(qr,work/'ears_review_small')['tracks'][0]['around']['highest_degrees']==4.4   # 70 times 0.0625, rounded once (the pan rounded first gave 4.3)
        qs=hp(move={'type':'swing','beats':.25,'width':1,'shape':'triangle'});qs['tracks'][0]['mix'].pop('pan',None);qs['clock']['tempo']=[[0,120]]
        assert review(qs,work/'ears_review_swing')['tracks'][0]['around']['highest_degrees']==70.0
        # a new short field is no guess for another word (an unknown `amount` was told "did you mean 'around'?")
        qa=example();qa['tracks'][0]['mix']['amount']=.5;assert validate(qa)['warnings']==[f"{qa['tracks'][0]['id']}.mix: unknown field 'amount'; it has no effect"],validate(qa)['warnings']
        qa=example();qa['tracks'][0]['mix']['azimuth']=90;assert "did you mean 'around'?" in validate(qa)['warnings'][0]
        return {'ring':list(h.shape),'reflections':len(taps),'early_energy':[round(float(v),4) for v in e_early],'ears_db_at_90':[round(r90,1),l90],'refused':len(refused)}
    found['a_headphone_version_places_every_part'] = a_headphone_version_places_every_part
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
            # the parts that carry the top, from the render's own stems: every part once, the shares adding up
            te=a['top_end'];assert sorted(x['part'] for x in te['by_part'])==sorted(t['id'] for t in p['tracks']) and abs(sum(x['share_pct'] for x in te['by_part'])-100)<.6,te
            assert [x['share_pct'] for x in te['by_part']]==sorted((x['share_pct'] for x in te['by_part']),reverse=True) and abs(te['drums_share_pct']-sum(x['share_pct'] for x in te['by_part'] if x['drums']))<.06   # (the drums' share is the powers' own, each row's is rounded)
            # the band is the top's: the noise sweep leads it and the bass, loud as it is, has next to none of it
            assert te['by_part'][0]['part']=='fx' and next(x['share_pct'] for x in te['by_part'] if x['part']=='bass')<1,te['by_part']
            from musiclib import summary as told
            assert 'Top end (6-16 kHz) by part, from the stems: ' in told.analysis(a,work/'render_bus'/'analysis.json')
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
            last_mix=graph.split('[mix]')[0].rsplit(';',1)[1]   # each input of the bus chain's last mix is padded before it (render.py, the room chain's mix)
            assert last_mix.strip().startswith('[last0]') and graph.count('apad=pad_dur=1[last')==last_mix.count('[last')>=2,graph[-500:]
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
        def a_moving_part_renders_and_the_others_stay():
            # mix.move in a render: the moving part's stem goes from one side to the other, its receipt says what the
            # movement cost, the other parts' stems are the files they were, and the delivery checks pass.
            q=copy.deepcopy(p);q['mix']['chain']='bus';save_json(work/'move_still.json',q)
            still=render(work/'move_still.json',work/'render_move_still',config,cache,draft=True)
            m=copy.deepcopy(q);lead=next(t for t in m['tracks'] if t['id']=='lead');lead['mix'].pop('pan',None)
            lead['mix']['move']={'type':'path','points':[[0,-1],[16,1]]};save_json(work/'move_path.json',m)
            r=render(work/'move_path.json',work/'render_move_path',config,cache,draft=True)
            assert r['status']=='DRAFT_PASS' and still['status']=='DRAFT_PASS',(r['status'],still['status'])
            a,b=work/'render_move_still'/'stems',work/'render_move_path'/'stems'
            same=[t['id'] for t in q['tracks'] if file_hash(a/f'{t["id"]}.wav')==file_hash(b/f'{t["id"]}.wav')]
            assert same==[t['id'] for t in q['tracks'] if t['id']!='lead'],same
            y,_=audio.read_wav(b/'lead.wav');y=np.asarray(y,dtype=np.float64);c=Clock(m);k=round(c.seconds(8)*audio.RATE)
            side=lambda s:10*np.log10(max(float(np.sum(s[:,1]**2)),1e-30)/max(float(np.sum(s[:,0]**2)),1e-30))
            early,late=side(y[:k]),side(y[k:2*k]);assert early<-3 and late>3,(early,late)
            receipt=next(x for x in json.loads((work/'render_move_path'/'stem_receipts.json').read_text(encoding='utf-8')) if x['track']=='lead')
            mv=receipt['move'];assert mv['type']=='path' and mv['lowest']<-.9 and mv['highest']>.9 and mv['fold_loss_db']>-.5 and -3.02<mv['mono_dip_db']<-2.5,mv
            assert 'pan=stereo|c0=1.000000000*c0|c1=1.000000000*c1' not in receipt['filter_chain'],receipt['filter_chain']
            # the stem in the cache is the movement's: another movement makes another stem, the first comes back as it was
            m2=copy.deepcopy(m);next(t for t in m2['tracks'] if t['id']=='lead')['mix']['move']={'type':'swing','beats':4,'width':.6}
            save_json(work/'move_swing.json',m2);r2=render(work/'move_swing.json',work/'render_move_swing',config,cache,draft=True)
            assert file_hash(work/'render_move_swing'/'stems'/'lead.wav')!=file_hash(b/'lead.wav')
            again=render(work/'move_path.json',work/'render_move_path2',config,cache,draft=True)
            assert file_hash(work/'render_move_path2'/'stems'/'lead.wav')==file_hash(b/'lead.wav') and again['status']=='DRAFT_PASS'
            return {'right_minus_left_db':[round(early,1),round(late,1)],'move':mv,'unchanged_parts':len(same)}
        def a_part_through_an_amplifier_renders_and_the_others_stay():
            # mix.amp in a render: the part's dry synthesis goes through the chain before its level, its receipt says how
            # hard it was driven, the other parts' stems are the files they were, nothing of the chain's own is left behind.
            q=copy.deepcopy(p);q['mix']['chain']='bus';save_json(work/'amp_plain.json',q)
            plain=render(work/'amp_plain.json',work/'render_amp_plain',config,cache,draft=True)
            m=copy.deepcopy(q);part=next(t for t in m['tracks'] if t['id']=='piano');part['mix']['amp']={'voice':'crunch','drive':.6}
            save_json(work/'amp_on.json',m);r=render(work/'amp_on.json',work/'render_amp_on',config,cache,draft=True)
            assert r['status']=='DRAFT_PASS' and plain['status']=='DRAFT_PASS',(r['status'],plain['status'])
            a,b=work/'render_amp_plain'/'stems',work/'render_amp_on'/'stems'
            same=[t['id'] for t in q['tracks'] if file_hash(a/f'{t["id"]}.wav')==file_hash(b/f'{t["id"]}.wav')]
            assert same==[t['id'] for t in q['tracks'] if t['id']!='piano'],same
            assert sorted(x.name for x in b.iterdir() if x.name.startswith('.'))==[],sorted(x.name for x in b.iterdir())
            receipts={x['track']:x for x in json.loads((work/'render_amp_on'/'stem_receipts.json').read_text(encoding='utf-8'))}
            amped=receipts['piano']['amp'];assert amped['voice']=='crunch' and amped['drive']==.6 and not amped['bank_measured'] and amped['input_peak']>0,amped
            assert receipts['piano']['cache_hit'] and 'amp' not in receipts['bass'],receipts['piano']
            y,_=audio.read_wav(b/'piano.wav');y=np.asarray(y,dtype=np.float64);x,_=audio.read_wav(a/'piano.wav');x=np.asarray(x,dtype=np.float64)
            assert float(np.max(np.abs(y[:,0]-y[:,1])))<1e-6   # one signal on both channels, whatever the recording was
            level=lambda s:10*np.log10(float(np.mean(s**2)));assert abs(level(y)-level(x))<3,(level(y),level(x))   # brought to the part's level
            m2=copy.deepcopy(m);next(t for t in m2['tracks'] if t['id']=='piano')['mix']['amp']['drive']=.2;save_json(work/'amp_low.json',m2)
            render(work/'amp_low.json',work/'render_amp_low',config,cache,draft=True)
            assert file_hash(work/'render_amp_low'/'stems'/'piano.wav')!=file_hash(b/'piano.wav')
            # an amplified part whose synthesis is silent stops the render with its message, and the chain's own file is
            # not left among the stems (on Windows the failure's traceback still held it open)
            m3=copy.deepcopy(m);next(t for t in m3['tracks'] if t['id']=='piano')['performance']['cc']=[[0,7,0],[0,11,0]];save_json(work/'amp_silent.json',m3)
            try:render(work/'amp_silent.json',work/'render_amp_silent',config,cache,draft=True);said=None
            except ValueError as e:said=str(e)
            assert said and 'silent' in said,said
            left=sorted(x.name for x in (work/'render_amp_silent'/'stems').iterdir() if x.name.startswith('.')) if (work/'render_amp_silent'/'stems').is_dir() else []
            assert left==[],left
            return {'amp':amped,'unchanged_parts':len(same)}
        def a_headphone_version_renders_beside_the_master():
            # mix.headphones in a render: headphones.wav beside the master, at the master's loudness and length, the
            # master and the stems the files they were without it; a part to the left is louder in the left ear; the
            # reflections can be left out; nothing of the making is left among the stems.
            from musiclib import ears
            q=copy.deepcopy(p);q['mix']['chain']='bus';save_json(work/'ears_plain.json',q)
            plain=render(work/'ears_plain.json',work/'render_ears_plain',config,cache,draft=True)
            centred=work/'render_ears_plain'/'stems'/'piano.wav'   # the piano as the example has it: at the centre
            q=copy.deepcopy(q);next(t for t in q['tracks'] if t['id']=='piano')['mix']['pan']=.6;save_json(work/'ears_panned.json',q)
            plain=render(work/'ears_panned.json',work/'render_ears_panned',config,cache,draft=True)
            m=copy.deepcopy(q);m['mix']['headphones']=True;next(t for t in m['tracks'] if t['id']=='bass')['mix']['around']={'type':'turn','beats':8}
            save_json(work/'ears_on.json',m);r=render(work/'ears_on.json',work/'render_ears_on',config,cache,draft=True)
            assert r['status']=='DRAFT_PASS' and plain['status']=='DRAFT_PASS' and 'headphones' not in plain and not (work/'render_ears_panned'/'headphones').exists()
            a,b=work/'render_ears_panned',work/'render_ears_on'
            assert file_hash(a/'master.wav')==file_hash(b/'master.wav') and all(file_hash(a/'stems'/f'{t["id"]}.wav')==file_hash(b/'stems'/f'{t["id"]}.wav') for t in q['tracks'])
            # the part before its place is the part without its pan: the piano's stem as it is at the centre
            assert file_hash(b/'headphones'/'centre'/'stems'/'piano.wav')==file_hash(centred)!=file_hash(b/'stems'/'piano.wav') and r['headphones']['parts']['piano']['lowest_degrees']==42
            heard=r['headphones'];loaded=audio.load_config(config);made=audio.measure(loaded,b/'headphones.wav',work/'logs','measure_ears');whole=audio.measure(loaded,b/'master.wav',work/'logs','measure_ears_master')
            assert heard['file']=='headphones.wav' and (b/'headphones.mp3').is_file() and heard['reflections'] and heard['responses']['doi']=='10.5281/zenodo.12092466'
            assert made['channels']==2 and made['sample_rate']==48000 and made['bits']==24 and made['frames']==whole['frames'],made
            assert abs(made['integrated_lufs']-q['mix']['target_lufs'])<=.3 and made['true_peak_dbtp']<=-1 and made['clipped_samples']==0,made
            assert set(heard['parts'])=={t['id'] for t in q['tracks']} and heard['parts']['bass']['by']=='turn' and heard['parts']['bass']['highest_degrees']>360,heard['parts']
            assert r['process_seconds']['headphone version']>0 and 'headphone version' not in plain['process_seconds'] and 'mp3_headphones' not in r['process_seconds'] and heard['parts']['piano']['points']==3,r['process_seconds']
            # compare reads the headphone version too: a part moved around the head changes that file alone
            from musiclib.compare import compare as compare_renders
            m4=copy.deepcopy(m);next(t for t in m4['tracks'] if t['id']=='bass')['mix']['around']=-90;save_json(work/'ears_moved.json',m4)
            assert render(work/'ears_moved.json',work/'render_ears_moved',config,cache,draft=True)['status']=='DRAFT_PASS'
            diff=compare_renders(b,work/'render_ears_moved');changed=diff['summary']['changed']
            assert list(changed.get('headphones',{}))==['headphones'] and not any(changed[g] for g in ('stems','buses','returns','premix','master')),changed
            assert 'headphones' not in compare_renders(a,a)['summary']['changed']   # (no group for it where no render has one)
            from musiclib import summary
            said=summary.render(r,b);said_plain=summary.render(plain,a)
            assert 'Headphone version: headphones.wav and headphones.mp3' in said and 'moving: bass' in said and 'headphones (parts)' in said and 'Headphone version' not in said_plain and 'headphones (parts)' not in said_plain,said   # (not "no word of headphones": the summary prints its folder, whose name may hold it)
            assert heard['left_out'][-1]=="the buses' saturation" and file_hash(b/'headphones.wav')!=file_hash(b/'master.wav')
            dots=sorted(str(x.relative_to(b)) for x in (b/'headphones').rglob('.*'));assert dots==[],dots
            assert 'asoftclip' not in (b/'headphones'/'mix.filtergraph.txt').read_text(encoding='utf-8') and 'asoftclip' in (b/'mix.filtergraph.txt').read_text(encoding='utf-8')
            m2=copy.deepcopy(m);m2['mix']['rules']=2;save_json(work/'ears_rules2.json',m2);r2=render(work/'ears_rules2.json',work/'render_ears_rules2',config,cache,draft=True)
            b2=work/'render_ears_rules2';assert r2['status']=='DRAFT_PASS' and 'asoftclip' not in (b2/'headphones'/'mix.filtergraph.txt').read_text(encoding='utf-8') and 'asoftclip' in (b2/'mix.filtergraph.txt').read_text(encoding='utf-8')
            # one part alone, to the left and to the right: the nearer ear is the louder one
            def alone(name,where,loud=False,**spec):
                one=copy.deepcopy(q);one['mix']['headphones']=spec or True
                if loud:one['mix'].update(loudness='loud',target_lufs=-9)
                one['sections']=[{'id':'a','start_bar':0,'bars':one['clock']['bars']}];one.pop('harmony',None)
                t=copy.deepcopy(next(t for t in q['tracks'] if t['id']=='piano'));t['mix'].update(pan=0,around=where,reverb_db=None,delay_db=None);one['tracks']=[t]
                save_json(work/f'{name}.json',one);rr=render(work/f'{name}.json',work/f'render_{name}',config,cache,draft=True);assert rr['status']=='DRAFT_PASS'
                y=np.asarray(audio.read_wav(work/f'render_{name}'/'headphones.wav')[0],dtype=np.float64);e=(y**2).sum(axis=0)
                return 10*np.log10(e[1]/e[0]),file_hash(work/f'render_{name}'/'headphones.wav'),rr
            left,_,_=alone('ears_left',-90);right,h_room,rr=alone('ears_right',90);_,h_dry,rd=alone('ears_right_dry',90,reflections=False)
            # (a piano: two points 30 degrees either side of its place, most of its power low, where a head shadows little,
            # and the reflections reach both ears: the two ears are a few dB apart, not the 15 of a click at the side)
            assert left<-2 and right>2 and right-left>6,(left,right)
            assert h_room!=h_dry and rr['headphones']['reflections'] and not rd['headphones']['reflections'] and rr['headphones']['parts']['piano']['lowest_degrees']==90
            # a loud master keeps its soft clip in the headphone version (with one gain for both ears: checked without a
            # renderer), so the limiter is left little to do and the loudness is reached (without the clip the limiter
            # took 8 dB from a master at -9 LUFS and ended half a dB under)
            right_loud,_,rl=alone('ears_right_loud',90,loud=True)
            assert 'loudness' not in rl['headphones']['left_out'] and abs(rl['headphones']['integrated_lufs']+9)<=.3 and max(rl['headphones']['limiting_db'].values())<3 and right_loud>2,(right_loud,rl['headphones'])
            return {'left_db':round(left,1),'right_db':round(right,1),'right_loud_db':round(right_loud,1),'lufs':made['integrated_lufs'],'true_peak_dbtp':made['true_peak_dbtp'],'points':{k:v['points'] for k,v in heard['parts'].items()}}
        def a_part_played_by_string_renders_string_by_string():
            # Playing by string in a render: with no string struck again and nothing muted the part is its ordinary
            # synthesis; a string's note ends at that string's next note while another string rings on; a palm-muted
            # note dies sooner; the receipt counts them.
            from musiclib import strung
            GUITAR=[40,45,50,55,59,64]
            def raw_of(r):
                # the part's synthesis as the cache keeps it (the shared cache, or the render's own where that one could not be used)
                at=Path(cache)/r['cache_key']/'raw.wav'
                if not at.is_file():at=next(work.rglob(f'{r["cache_key"]}/raw.wav'))
                return np.array(audio.read_wav(at)[0],dtype=np.float64)
            def piece(name,notes,strings=True):
                q=copy.deepcopy(p);q['mix']['chain']='bus';q['clock']={'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':3}
                q['sections']=[{'id':'a','start_bar':0,'bars':2}];q.pop('harmony',None)
                t=copy.deepcopy(next(t for t in p['tracks'] if t['id']=='piano'))
                t['notes']=[{'id':f'n{i}','on':on,'duration':d,'pitch':pitch,**(more if strings else {})} for i,(on,d,pitch,more,*_) in enumerate(notes)]
                t['performance']={'notes':{f'n{i}':{'velocity':96,**(n[4] if len(n)>4 else {})} for i,n in enumerate(notes)},'cc':[]}
                if strings:t['strings']=GUITAR
                t['mix'].update(reverb_db=None,delay_db=None,highpass=30,lowpass=18000);q['tracks']=[t];save_json(work/f'{name}.json',q)
                r=render(work/f'{name}.json',work/f'render_{name}',config,cache,draft=True);assert r['status']=='DRAFT_PASS',r['status']
                y,_=audio.read_wav(work/f'render_{name}'/'stems'/'piano.wav')
                receipt=next(x for x in json.loads((work/f'render_{name}'/'stem_receipts.json').read_text(encoding='utf-8')) if x['track']=='piano')
                return np.array(y,dtype=np.float64),receipt
            apart=[(0,3,40,{'string':6}),(1,3,45,{'string':5}),(2,2,50,{'string':4})]
            ys,rs=piece('strung_apart',apart);yp,rp=piece('strung_apart_plain',apart,strings=False)
            # compared as synthesized, in the cache: the stems after them pass FFmpeg's single-precision filters, whose
            # rounding alone leaves two renders of one signal some 74 dB apart
            raw=raw_of
            dry_s,dry_p=raw(rs),raw(rp);n=min(len(dry_s),len(dry_p));same=float(np.max(np.abs(dry_s[:n]-dry_p[:n])))/float(np.max(np.abs(dry_p)))
            tail=rs['strung'].pop('tail_seconds');rs['strung'].pop('tail_assumed',None)
            assert same<1e-6 and float(np.max(np.abs(ys-yp)))/float(np.max(np.abs(yp)))<1e-3 and rs['strung']=={'passes':3,'strings':[6,5,4],'open':3,'palm':0,'dead':0,'ended_by_next_stroke':0} and 'strung' not in rp and 0<tail<=strung.TAIL_LIMIT,(same,rs.get('strung'),tail)
            # E2 on string 6 for four beats, then G2 on the same string after one; A2 on string 5 rings throughout
            # E2 on string 6, carried past G2 on that string by its gate (two beats written, 1.6 s as played; G2 at
            # 1 s); A2 on string 5 rings throughout.  Read between G2's stroke and where E2 would have ended.
            again=[(0,2,40,{'string':6},{'gate':1.6}),(0,6,45,{'string':5}),(2,4,43,{'string':6})]
            yc,rc=piece('strung_again',again);yn,_=piece('strung_again_plain',again,strings=False)
            R=audio.RATE;c=Clock(json.loads((work/'strung_again.json').read_text(encoding='utf-8')));a,b=round(c.seconds(2.1)*R),round(c.seconds(3.1)*R)
            def tone(y,hz):
                s=np.abs(np.fft.rfft(y[a:b,0]*np.hanning(b-a)));f=np.fft.rfftfreq(b-a,1/R);return 20*np.log10(max(float(s[(f>hz-2)&(f<hz+2)].max()),1e-12))
            e2,a2,g2=tone(yc,82.41)-tone(yn,82.41),tone(yc,110.0)-tone(yn,110.0),tone(yc,98.0)-tone(yn,98.0)
            assert e2<-20 and abs(a2)<3 and abs(g2)<3 and rc['strung']['ended_by_next_stroke']==1,(e2,a2,g2,rc['strung'])   # the string's next note sounds as it would
            # E2 carried past G2 on its string by its gate, A2 a beat after G2: E2 does not come back under A2 (found
            # before the first review with E2 written for four beats, which is now refused: a string's notes were
            # synthesized alternately in two passes, and what a note still sounded when its pass's next note began
            # was left as it was: +92 dB there)
            longer=[(0,1,40,{'string':6},{'gate':1.6}),(1,1,43,{'string':6},{'gate':1.6}),(2,2,45,{'string':6})]   # each still held when its string's next comes
            yl,rl=piece('strung_long',longer);y2,_=piece('strung_long_rest',[(2,2,45,{'string':6})])
            # (the stems are levelled each to its own part, so E2 is read against the A2 beside it in each)
            back=(tone(yl,82.41)-tone(yl,110.0))-(tone(y2,82.41)-tone(y2,110.0))
            assert back<6 and rl['strung']['ended_by_next_stroke']==2 and rl['strung']['passes']>=2,(back,rl['strung'])
            # three quick notes on one string: under the third there is nothing of the first (two alternating passes
            # left the first one's release there), so from the end of the second one's fade the synthesis is the
            # third note's own
            quick=[(0,.125,40,{'string':6}),(.125,.125,41,{'string':6}),(.25,1,42,{'string':6})]
            _,rq=piece('strung_quick',quick);_,r3=piece('strung_quick_third',[(.25,1,42,{'string':6})])
            cq=Clock(json.loads((work/'strung_quick.json').read_text(encoding='utf-8')));third=round(cq.seconds(.25)*R)
            full,alone=raw(rq),raw(r3);w=slice(third+round(.012*R),third+round(.4*R))
            under=float(np.max(np.abs(full[w]-alone[w])))/float(np.max(np.abs(full[:third])))
            assert under<1e-4 and rq['strung']['passes']>=2 and r3['strung']['passes']==1,(under,rq['strung'])   # (how many passes follows the preset's release)
            # a note's key is held to its own end or to its string's next stroke as played, whichever is first: E2 a
            # beat long at gate 1.6 (0.8 s), G2 written at beat 1 and played 100 ms late (0.6 s): until then the
            # synthesis is E2's own
            _,rg=piece('strung_gate',[(0,1,40,{'string':6},{'gate':1.6}),(1,1,43,{'string':6},{'timing_ms':100})]);_,re2=piece('strung_gate_alone',[(0,1,40,{'string':6},{'gate':1.6})])
            gate_a,gate_b=raw(rg),raw(re2);w=slice(round(.3*R),round(.58*R));held=float(np.max(np.abs(gate_a[w]-gate_b[w])))/float(np.max(np.abs(gate_b[w])))
            assert held<1e-3,held
            # a part played by string without a note has its record too
            two=copy.deepcopy(json.loads((work/'strung_again.json').read_text(encoding='utf-8')));rest_part=copy.deepcopy(two['tracks'][0])
            rest_part.update(id='resting',notes=[]);rest_part['performance']={'notes':{},'cc':[]};two['tracks'].append(rest_part);save_json(work/'strung_rest.json',two)
            assert render(work/'strung_rest.json',work/'render_strung_rest',config,cache,draft=True)['status']=='DRAFT_PASS'
            rr={x['track']:x for x in json.loads((work/'render_strung_rest'/'stem_receipts.json').read_text(encoding='utf-8'))}
            assert rr['resting']['strung']==strung.empty() and rr['piano']['strung']['passes']>=2,rr['resting']
            # the same E2 palm-muted, alone
            ym,rm=piece('strung_palm',[(0,4,40,{'string':6,'mute':'palm'})]);yo,_=piece('strung_open',[(0,4,40,{'string':6})])
            level=lambda y,t0,t1:10*np.log10(max(float(np.mean(y[round(t0*R):round(t1*R)]**2)),1e-30))
            # (each stem is brought to the part's level, so the two are compared by their own decay)
            fall_m,fall_o=level(ym,0,.05)-level(ym,.3,.4),level(yo,0,.05)-level(yo,.3,.4)
            assert fall_m>fall_o+15 and rm['strung']['palm']==1 and rm['strung']['passes']==1,(fall_m,fall_o,rm['strung'])
            return {'apart_minus_plain':same,'tail_seconds':tail,'e2_back_under_the_note_after_next_db':round(back,1),'first_under_third':under,'e2_after_its_strings_next_db':round(e2,1),'a2_db':round(a2,1),'palm_falls_db':round(fall_m,1),'open_falls_db':round(fall_o,1)}
        found.update({'bus_chain_render_and_delivery_checks': bus_render, 'a_chorus_pass_never_shares_another_parts_log': chorus_pass_logs, 'effects_apply_in_the_order_listed': effects_in_listed_order, 'analysis_reports_sections_stems_and_lead': analysis, 'mix_rules_2_render_limiter_saturation_and_clarity': rules_2_render, 'wide_dynamics_master_keeps_the_mix_range': wide_render, 'stage_depth_and_range_control_render': stage_and_range, 'long_automation_renders': long_automation_renders})
        found['a_moving_part_renders_and_the_others_stay'] = a_moving_part_renders_and_the_others_stay
        found['a_part_through_an_amplifier_renders_and_the_others_stay'] = a_part_through_an_amplifier_renders_and_the_others_stay
        found['a_part_played_by_string_renders_string_by_string'] = a_part_played_by_string_renders_string_by_string
        found['a_headphone_version_renders_beside_the_master'] = a_headphone_version_renders_beside_the_master
        def a_failed_pass_leaves_no_scratch_file():
            # 0.9 step 5 (left by the reviews of 0.8 and 0.9): where an FFmpeg pass fails in the middle of a part's
            # chain or of a loud delivery, the files the pass before it wrote for it stayed in the render's folder (a
            # chorus's intermediate stem, clipped.wav, limited.wav).  FFmpeg is made to fail at a named pass.
            from musiclib.render import render
            real=audio.ffmpeg
            def failing(label_end):
                def ffmpeg(cfg,args,logs,label,*a,**k):
                    if label.endswith(label_end):raise RuntimeError(f'{label} failed (made to)')
                    return real(cfg,args,logs,label,*a,**k)
                return ffmpeg
            def stopped(name,q,label_end):
                folder=work/f'scratch_{name}';folder.mkdir();save_json(folder/'song.json',q);audio.ffmpeg=failing(label_end)
                try:render(folder/'song.json',folder/'render',config,work/'cache_scratch');raise AssertionError(f'{name}: rendered through a failing pass')
                except RuntimeError as e:assert 'made to' in str(e),e
                finally:audio.ffmpeg=real
                return sorted(x.relative_to(folder/'render').as_posix() for x in (folder/'render').rglob('*') if x.is_file())
            base=copy.deepcopy(p);base['clock']={'bars':2,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':3};base['sections']=[dict(base['sections'][0],start_bar=0,bars=2)]
            for k in ('harmony','chords','plan','loop'):base.pop(k,None)
            for t in base['tracks']:
                keep=[n for n in t['notes'] if n['on']+n['duration']<=8];t['notes']=keep;t['performance']['notes']={n['id']:t['performance']['notes'][n['id']] for n in keep};t['performance']['cc']=[]
            base['tracks']=[t for t in base['tracks'] if t['notes']];validate(base)
            chorus=copy.deepcopy(base);part=chorus['tracks'][0];part['mix']['effects']=[{'type':'chorus','depth':.4}]
            left=stopped('chorus',chorus,f'process_{part["id"]}.pass1')
            assert not [x for x in left if '.pass' in x],left
            loud2=copy.deepcopy(base);loud2['mix'].update(chain='bus',rules=2,loudness='loud',target_lufs=-9)
            left=stopped('loud2',loud2,'deliver_0');assert 'limited.wav' not in left and 'clipped.wav' not in left,left
            loud1=copy.deepcopy(base);loud1['mix'].update(chain='bus',loudness='loud',target_lufs=-9);loud1['mix'].pop('rules',None)
            left=stopped('loud1',loud1,'deliver_0');assert 'limited.wav' not in left and 'clipped.wav' not in left,left
            # the third review: a loop's float copy, written to measure its peak, when that measurement fails
            looped=copy.deepcopy(base);looped['loop']={'start_bar':0};validate(looped)
            left=stopped('looped',looped,'measure_loop_float');assert not [x for x in left if 'loop_float' in x],left
            # the confirmation review: a loop layer's premix, when the pass that masters it fails
            layered=copy.deepcopy(base);layered['mix'].update(chain='bus');ids=[t['id'] for t in layered['tracks']]
            layered['loop']={'start_bar':0,'layers':{'base':ids[:1],'top':ids[1:]}};validate(layered)
            left=stopped('layered',layered,'layer_base');assert not [x for x in left if x.endswith(('_premix.wav','_processed.wav'))],left
            return {'passes_failed':5}
        found['a_failed_pass_leaves_no_scratch_file'] = a_failed_pass_leaves_no_scratch_file
    return found
