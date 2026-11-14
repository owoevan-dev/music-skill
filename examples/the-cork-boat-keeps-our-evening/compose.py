"""All notes, both the technical probe and the piece, are authored here.
Run with --probe first, then --revision 1 or 2. No external musical input.
"""
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys, json, argparse, copy, math
from pathlib import Path
ROOT = Path(__file__).resolve().parent
# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# lines named the folder of a copy of the skill and a temporary folder on the machine it ran on).
sys.dont_write_bytecode = True
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import expression
TITLE = 'The Cork Boat Keeps Our Evening'
SEED = 1052141233
SPECS = [
    # Edited for this repository: the two piano parts play the Steinway (vcsl 0:0), as the recording does; the agent
    # put them on the Kawai grand ('vcsl_keys', 1).
    ('piano', 'Steinway grand: tune and upper accompaniment', 'melody', 'vcsl', 0, 0, 0, -23, -0.08, [48,88]),
    ('piano_left', 'Steinway grand: rocking left hand', 'rhythm', 'vcsl', 0, 0, 0, -30, -0.12, [39,67]),
    ('cello', 'Solo cello: the unsung vocal line', 'melody', 'cello_bigcat', 42, 0, 42, -21, 0.02, [60,79]),
    ('violas', 'Sustained inner string voices', 'harmony', 'vsco_strings', 41, 0, 41, -32, 0.24, [48,67]),
    ('violins', 'Upper sustained string halo', 'harmony', 'vsco_strings', 40, 0, 40, -32, -0.30, [55,84]),
    ('guitar', 'Archtop microphone: long open voicings', 'rhythm', 'guitar_shiny', 25, 0, 25, -34, 0.32, [55,75]),
    ('bass', 'Fingered electric bass', 'bass', 'bass_darkblack', 33, 0, 33, -29, 0.0, [27,55]),
    ('kit', 'Restrained brush-kit pulse', 'drums', 'default', 40, 128, 0, -34, 0.0, [35,51]),
]

def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

def tracks():
    result=[]
    for ident,name,role,bank,program,patchbank,gm,level,pan,ran in SPECS:
        t={'id':ident,'name':name,'role':role,'engine':'soundfont','program':gm,'bank':0,
           'soundfont':bank,'patch':{'bank':patchbank,'program':program},'drums':ident=='kit',
           'range':ran,'notes':[],'performance':{'notes':{},'cc':[]},
           'mix':{'level_dbfs':level,'level_mode':'active_rms','pan':pan,'width':0.5 if ident=='cello' else 0.8,
                  'highpass':25 if ident in ('bass','kit') else 45 if ident=='piano_left' else 90,
                  'reverb_db':-19 if ident in ('piano','piano_left','cello') else -17 if ident in ('violas','violins') else -25,
                  'space':'hall' if ident in ('violas','violins') else 'room'}}
        if ident=='kit': t['mix']['level_mode']='peak'
        if ident in ('violas','violins'):
            t['performance']['offset_ms']=-65
            t['performance']['cc_mode']='linear'
        result.append(t)
    return result

def add(t,on,pitch,dur,vel,phrase='figure',ident=None,gate=1.0):
    nid=ident or f"{t['id']}_b{int(on//4)+1:03d}_n{sum(int(n['on']//4)==int(on//4) for n in t['notes']):03d}"
    t['notes'].append({'id':nid,'on':on,'pitch':int(pitch),'duration':dur,'phrase':phrase})
    t['performance']['notes'][nid]={'velocity':int(vel),'timing_ms':0,'gate':gate}

SECTIONS=[('window',0,8,'The whole melody introduced on one piano'),
          ('verse',8,16,'Cello takes the line; bass and inner strings gradually join'),
          ('chorus',24,16,'The same pulse carries the upper strings and soft band'),
          ('last_chorus',40,16,'Fullest orchestration and the highest long melodic arc'),
          ('home',56,8,'Gradual withdrawal into the piano alone')]
PLAN={'identity':'A rising third answered by stepwise retreat, long vocal-length phrases, and an unbroken rocking piano pulse.',
      'high_point':{'section':'last_chorus','means':'All eight parts, two-voice strings, higher sustained cello and long open guitar chords; no faster pulse.'},
      'sections':[
          {'section':'window','sounds':['piano','piano_left'],'leads':'piano'},
          {'section':'verse','sounds':['piano','piano_left','cello','violas','bass'],'leads':'cello','differs':'Cello takes over at bar 9; inner strings at 13; bass at 17.'},
          {'section':'chorus','sounds':['piano','piano_left','cello','violas','violins','bass','kit'],'leads':'cello','differs':'Upper strings and restrained drums join, with the same quarter pulse.'},
          {'section':'last_chorus','sounds':[x[0] for x in SPECS],'leads':'cello','differs':'Guitar arrives and strings broaden to two voices; the theme gains a higher conclusion.'},
          {'section':'home','sounds':['piano','piano_left','violas','violins','bass','kit'],'leads':'piano','differs':'Band and strings taper over four bars; the last four bars are piano alone.'}]}

def base(bars=64):
    a=json.loads((ROOT/'association.json').read_text(encoding='utf-8'))
    return {'schema':'music-production/v1','title':TITLE,'version':'1.0.r1',
            'brief':'Original slow instrumental Japanese film/anime ending-theme ballad; steady throughout, long phrases, gradual strings and soft band, fullest final chorus, piano opening and ending alone.',
            'style':'pop/ballad','clock':{'bars':bars,'meter':[4,4],'tempo':[[0,74]],'tail_seconds':5},
            'sections':[{'id':i,'start_bar':s,'bars':n,'intent':why} for i,s,n,why in SECTIONS],
            'plan':copy.deepcopy(PLAN),'tracks':tracks(),
            'mix':{'chain':'bus','rules':2,'target_lufs':-16,'mono_below_hz':100},
            'association':{'source':a['source'],'seed':a['seed'],'words':a['words'],
              'whole':'After a seaside birthday, a child with frizzy hair folds a blanket on a sofa beside a toy walrus and a gecko ornament; a pyramid of gifts still smells of clove cake. Outside, a parked steamroller stands on new cement while a cork boat drifts above a minnow. The boat travels away and returns below the lit window.',
              'gives':[{'level':'form','what':'Departure, broad return, then the window alone; five long sections','where':'entire piece'},
                       {'level':'melody','what':'Rising third and a long stepwise return, like the drifting boat','where':'piano opening and cello themes'},
                       {'level':'rhythm','what':'Even rocking quarters without a tempo change','where':'piano left hand throughout'},
                       {'level':'harmony','what':'Common-tone inversions join the journey to the home tonic','where':'two-bar harmonic spans'}]},
            'decisions':['The request takes precedence over a generic ballad pre-chorus or key-change lift: five long sections and one unchanging tempo.',
                         'The ending-theme character is a broad genre brief, not imitation of any named artist or existing work.',
                         'The delivery target is -16 LUFS to leave room for the piano opening and gentle band; this is a piece-specific choice.'],
            'authorship':{'method':'Every note authored in compose.py; existing sample recordings are instruments, not the composition.'}}

def probe():
    p=base(4); p['title']=TITLE+' - technical instrument probe'
    p['sections']=[{'id':'probe','start_bar':0,'bars':4,'intent':'Range, velocity and sustained-note render check; no auditory judgment'}]
    p.pop('plan')
    for t in p['tracks']:
        pitches={'piano':[48,63,74,82],'piano_left':[39,46,55,63],'cello':[60,67,74,79],
                 'violas':[48,55,62,67],'violins':[55,62,70,79],'guitar':[55,60,67,74],
                 'bass':[27,34,39,46],'kit':[36,37,44,51]}[t['id']]
        for j,pitch in enumerate(pitches): add(t,4*j,pitch,3.7,52+j*11,'probe')
    dump(ROOT/'probe.json',p)

# Each two-bar harmony has a bass and an explicitly chosen inner voicing.
# The sequence was composed for these phrases, not copied from a reference.
CHORDS={
 'Ebmaj9': (39,[55,58,62,65]), 'Abmaj7/Eb':(39,[56,60,63,67]),
 'Gm7':(43,[53,58,62,67]), 'Bb7sus4':(34,[56,63,65,70]),
 'Ebmaj7/G':(43,[55,58,62,63]), 'Cm9':(36,[55,58,62,63]),
 'Fm9':(41,[56,60,63,67]), 'Gm7/Bb':(34,[55,58,62,65]),
 'Fm7/Ab':(32,[53,56,60,63]), 'Bb7':(34,[56,62,65,70]),
 'Abmaj7':(32,[55,56,60,63]), 'Cm7/Eb':(39,[55,58,60,63]),
 'Gm7/D':(38,[55,58,62,65]), 'Abmaj7/C':(36,[55,56,60,63]),
 'Bb9sus4':(34,[56,60,63,65]), 'Fm7':(41,[56,60,63,65]),
 'Eb6/9':(39,[55,58,60,65]),
}
PROGRESSION=[
 'Ebmaj9','Abmaj7/Eb','Gm7','Bb7sus4',
 'Ebmaj7/G','Cm9','Fm9','Abmaj7/Eb','Ebmaj9','Gm7/Bb','Fm7/Ab','Bb7',
 'Ebmaj9','Abmaj7','Cm7/Eb','Fm9','Gm7','Abmaj7','Bb9sus4','Bb7',
 'Ebmaj9','Gm7/D','Abmaj7/C','Fm9','Cm9','Abmaj7','Bb9sus4','Ebmaj9',
 'Abmaj7/Eb','Gm7','Fm7','Eb6/9',
]
# Tuples are (pitch, beats); every phrase is authored, including rests (None).
INTRO=[
 [(67,2),(70,1),(68,1),(67,3),(65,1)],
 [(63,2),(65,1),(67,1),(72,2),(70,1),(67,.75),(None,.25)],
 [(70,3),(69,1),(70,2),(74,2)],
 [(72,2),(70,2),(68,2),(65,1.75),(None,.25)],
]
VERSE=[
 [(67,2),(70,1),(68,1),(67,2),(65,1),(63,.75),(None,.25)],
 [(67,3),(65,1),(63,2),(62,1),(60,.75),(None,.25)],
 [(60,2),(63,2),(65,3),(67,1)],
 [(68,3),(67,1),(63,2),(60,1.75),(None,.25)],
 [(65,1),(67,3),(70,2),(68,1),(67,.75),(None,.25)],
 [(65,2),(67,2),(70,3),(74,1)],
 [(72,3),(70,1),(68,2),(67,1),(65,1)],
 [(65,2),(68,2),(74,2),(72,1),(70,.75),(None,.25)],
]
CHORUS=[
 [(67,2),(70,1),(68,1),(70,4)],
 [(72,3),(70,1),(68,2),(67,1),(68,.75),(None,.25)],
 [(75,3),(74,1),(72,2),(70,2)],
 [(68,2),(67,2),(65,3.75),(None,.25)],
 [(67,2),(70,2),(74,3),(72,1)],
 [(72,2),(75,2),(72,2),(70,1),(68,.75),(None,.25)],
 [(67,2),(68,2),(72,2),(70,2)],
 [(68,2),(65,2),(62,2),(65,1),(70,.75),(None,.25)],
]
FINAL=[
 [(67,2),(70,1),(68,1),(70,2),(74,2)],
 [(74,3),(72,1),(70,2),(67,1),(70,.75),(None,.25)],
 [(72,2),(75,2),(79,3),(77,1)],
 [(75,2),(72,2),(68,3.75),(None,.25)],
 [(67,2),(70,2),(75,3),(74,1)],
 [(72,2),(75,2),(79,2),(77,1),(75,.75),(None,.25)],
 [(72,2),(70,2),(68,2),(65,2)],
 [(67,3),(65,1),(63,3.75),(None,.25)],
]
OUTRO=[
 [(67,2),(70,1),(68,1),(67,3),(65,1)],
 [(62,2),(65,2),(67,2),(65,1),(62,.75),(None,.25)],
 [(63,2),(65,2),(68,2),(67,1),(65,1)],
 [(67,2),(65,2),(63,4)],
]

def compose(revision):
    p=base(); p['version']=f'1.0.r{revision}'
    tt={t['id']:t for t in p['tracks']}
    p['harmony']=[{'bar':2*k+1,'symbol':c} for k,c in enumerate(PROGRESSION)]
    # Establish the entire tune before arranging it.
    for start, phrases, part, vbase, label in [
        (0,INTRO,'piano',78,'opening'), (8,VERSE,'cello',74,'verse'),
        (24,CHORUS,'cello',83,'chorus'), (40,FINAL,'cello',90,'last'),
        (56,OUTRO,'piano',78,'return')]:
        for k,phrase in enumerate(phrases):
            assert abs(sum(d for _,d in phrase)-8)<1e-6
            on=(start+2*k)*4
            for j,(pitch,dur) in enumerate(phrase):
                if pitch is not None:
                    add(tt[part],on,pitch,dur,vbase + (2 if k%2==0 else 0),f'{label}_{k//2+1}',
                        f'{part}_{label}_{k:02d}_{j:02d}',gate=1.0 if part=='cello' else .99)
                on+=dur
    # Consistent rocking quarters, with the pedal changing every bar.
    for bar in range(64):
        root,voice=CHORDS[PROGRESSION[bar//2]]
        section=0 if bar<8 else 1 if bar<24 else 2 if bar<40 else 3 if bar<56 else 4
        lv=[57,56,62,66,54][section]
        # The lower piano is open, avoiding clustered low chord tones.
        anchor=root+12
        while anchor<46: anchor+=12
        tones=sorted(set(voice))
        upper=[x for x in tones if x>=anchor and x<=65]
        if not upper: upper=tones[:2]
        pattern=[anchor,upper[0],upper[min(1,len(upper)-1)],upper[0]]
        if bar%2: pattern=[anchor,upper[min(1,len(upper)-1)],upper[0],upper[-1]]
        for beat,pitch in enumerate(pattern):
            vel=lv+(3 if beat==0 else -2 if beat==3 else 0)
            add(tt['piano_left'],bar*4+beat,pitch,min(1.18,256-(bar*4+beat)),vel,f'rock_{bar//4}',gate=.98)
        if 8<=bar<56:
            # An unhurried two-note response below the solo line, not doubling it.
            vals=[x for x in voice if 55<=x<=65]
            for beat,pitch in [(1.5,vals[-1]),(3,vals[0])]:
                add(tt['piano'],bar*4+beat,pitch,1.35,lv-2,f'response_{bar//4}',gate=1.0)
        for ident in ('piano','piano_left'):
            tt[ident]['performance']['cc'] += [[bar*4,64,0],[bar*4+.08,64,100]]
    for ident in ('piano','piano_left'):
        tt[ident]['performance']['cc'].append([255.9,64,0])
    # A gradual bass entrance. Whole/half-note foundation, no fills.
    for bar in range(16,60):
        root,voice=CHORDS[PROGRESSION[bar//2]]
        v=65 if bar<24 else 72 if bar<40 else 77 if bar<56 else 58
        add(tt['bass'],bar*4,root,3.92 if bar%2==0 else 1.98,v,f'bass_{bar//4}',gate=.99)
        if bar%2:
            add(tt['bass'],bar*4+2,root,1.94,v-6,f'bass_{bar//4}',gate=.99)
    # String entries are offset and common tones tied; no clipped stabs.
    string_lines={'violas':[], 'violins':[]}
    for k,c in enumerate(PROGRESSION):
        bar=k*2; root,voice=CHORDS[c]
        if 12<=bar<60:
            # a single inner line until the fullest chorus
            pitch={'Ebmaj9':55,'Abmaj7/Eb':56,'Gm7':58,'Bb7sus4':56,
                   'Ebmaj7/G':55,'Cm9':55,'Fm9':56,'Gm7/Bb':58,'Fm7/Ab':56,
                   'Bb7':56,'Abmaj7':55,'Cm7/Eb':55,'Gm7/D':55,'Abmaj7/C':56,
                   'Bb9sus4':56,'Fm7':56,'Eb6/9':55}[c]
            string_lines['violas'].append((bar*4+.5,pitch,7.5,60 if bar<24 else 67 if bar<40 else 75 if bar<56 else 52))
        if 24<=bar<60:
            pitch={'Ebmaj9':62,'Abmaj7':63,'Cm7/Eb':63,'Fm9':63,'Gm7':62,
                   'Bb9sus4':63,'Bb7':62,'Gm7/D':62,'Abmaj7/C':63,
                   'Cm9':62,'Abmaj7/Eb':63}[c]
            string_lines['violins'].append((bar*4+1,pitch,7,65 if bar<40 else 77 if bar<56 else 50))
            if 40<=bar<56:
                # The second desk arrives only for the last chorus.
                second={'Ebmaj9':70,'Gm7/D':70,'Abmaj7/C':72,'Fm9':72,
                        'Cm9':70,'Abmaj7':72,'Bb9sus4':70}[c]
                string_lines['violins'].append((bar*4+2,second,6,68))
    for ident,items in string_lines.items():
        for j,(on,pitch,dur,vel) in enumerate(items):
            add(tt[ident],on,pitch,dur,vel,f'string_{int(on//16)}',f'{ident}_line_{j:03d}',gate=1.0)
    # The archtop joins only in the final chorus. Each voicing lasts a bar.
    for bar in range(40,56):
        root,voice=CHORDS[PROGRESSION[bar//2]]
        voicing=sorted(set([voice[0]+12,voice[1]+12,voice[2]]))
        voicing=[x-12 if x>75 else x for x in voicing]
        for j,pitch in enumerate(sorted(set(voicing))):
            add(tt['guitar'],bar*4+.5,pitch,3.35,60 if bar<48 else 64,f'guitar_{bar//4}',gate=1.0)
    # A soft backbeat with pedal hats; never a crash or transitional fill.
    for bar in range(24,60):
        v=52 if bar<40 else 60 if bar<56 else 42
        for beat,key,delta in [(0,36,6),(1,37,-3),(2,36,0),(3,37,-1)]:
            add(tt['kit'],bar*4+beat,key,.8,v+delta,f'pulse_{bar//4}')
        for beat in (0,1,2,3):
            add(tt['kit'],bar*4+beat,44,.8,v-12+(2 if beat%2==0 else 0),f'pulse_{bar//4}')
    # Phrase curves give the cello longer arcs, connected without fake bends.
    tt['cello']['performance'].update({'legato':{'mode':'crossfade','crossfade_ms':95,'gap_ms':70,'max_interval':7},
        'dynamics_mode':'take','bow_change_s':4.0,'bow_ms':70,'dynamics':[]})
    for bar in range(8,56,4):
        value=74 if bar<24 else 84 if bar<40 else 92
        tt['cello']['performance']['dynamics'] += [[bar*4,value-8],[bar*4+9,value+3],[bar*4+15.5,value-8]]
    # Continuous level ramps soften ensemble arrival and withdrawal.
    tt['piano']['mix']['automation']=[[0,0],[31,0],[32,-3],[95,-3],[96,-4],[223,-4],[224,0],[240,-1],[256,-4]]
    tt['piano_left']['mix']['automation']=[[0,0],[64,0],[96,-1],[160,-1],[220,-1],[240,-2],[256,-4]]
    for ident,start in [('cello',32),('violas',48.5),('bass',64),('violins',97),('kit',96),('guitar',160.5)]:
        m=tt[ident]['mix']
        ending=224 if ident in ('cello','guitar') else 240
        m['automation']=[[0,-6],[start,-6],[start+8,0],[ending-8,0],[ending,-14]]
    p['decisions'] += [
      'Fixed 74 BPM is deliberate: all growth comes from sustained layers, register and dynamics, as the brief requires.',
      'The cello is the sole vocal substitute. Piano carries the opening and closing; accompanying piano notes occupy the lower middle register.',
      'The two piano tracks represent one pianist: left-hand quarters and a right-hand tune or light commentary, with barwise pedal changes.',
      'The kit uses quiet kick, cross-stick and pedal hat; no crashes, fills or syncopated accents interrupt the steady feel.',
      'Common-practice chord vocabulary is used freely; the complete harmonic path and all melodic phrases were authored for this piece without a musical reference.'
    ]
    expression.apply(p,overrides={
       'piano':{'timing_sd':3,'short_sd':1,'high_loud':0,'arch':3,'gate_sd':0},
       'piano_left':{'timing_sd':2,'short_sd':.7,'arch':2,'gate_sd':0},
       'cello':{'timing_sd':3,'short_sd':1,'arch':3,'high_loud':0,'gate_sd':0,'contrast':0},
       'violas':{'swell':7,'gate_sd':0},'violins':{'swell':9,'gate_sd':0},
       'guitar':{'strum':12,'arch':2,'gate_sd':0},'kit':{'timing_sd':1.2,'short_sd':.5},
       'bass':{'timing_sd':2,'feel':4,'gate_sd':0}},seed=SEED,drift='time')
    for t in p['tracks']:
        t['notes'].sort(key=lambda n:(n['on'],n['pitch'],n['id']))
    p['revision_history']=[{'round':1,'change':'Initial full score and bus-rules-2 mix, following successful instrument probe.'}]
    if revision>=2:
        decisions_path=ROOT/'review_decisions.json'
        if decisions_path.exists():
            p['decisions']+=json.loads(decisions_path.read_text(encoding='utf-8'))
        # Concrete revision instructions are added after the first measured round.
        revise_second_round(p)
    dump(ROOT/f'song_r{revision}.json',p)
    dump(ROOT/'song.json',p)
    print(f'{TITLE}: revision {revision}, {sum(len(t["notes"]) for t in p["tracks"])} authored notes')

def revise_second_round(p):
    tt={t['id']:t for t in p['tracks']}
    # Review: move the low major seventh away from Ab3 in the inner parts.
    ab_bars={26,27,34,35,44,45,50,51}
    for ident in ('piano','piano_left','violas'):
        for n in tt[ident]['notes']:
            if int(n['on']//4) in ab_bars and n['pitch']==55:
                n['pitch']=60
    # The written ninth in the opening now resolves by step; the return's
    # final F becomes the common-tone Eb leading down to D in the next phrase.
    for n in tt['piano']['notes']:
        if n['id']=='piano_opening_01_05': n['pitch']=68
        if n['id']=='piano_return_00_04': n['pitch']=63
        if n['id']=='piano_b012_n000': n['pitch']=58
    # Give the sung substitute a half-beat breath at each four-bar ending.
    for n in tt['cello']['notes']:
        end=n['on']+n['duration']
        if abs((end+.25)%16)<1e-6:
            n['duration']-=.25
        elif abs(end%16)<1e-6:
            n['duration']-=.5
    # Unclutter the two long Eb arrivals, keeping the principal line intact.
    for n in tt['violins']['notes']:
        if int(n['on']//4) in (48,54) and n['pitch']==62:
            n['pitch']=67 if int(n['on']//4)==48 else 58
    # Deliberately chosen open archtop voicings, gently spread over one beat.
    guitar_voicings={40:[58,65,70],42:[58,62,67],44:[60,63,68],46:[60,63,68],
                    48:[58,63,67],50:[60,63,68],52:[60,63,68],54:[58,65,70]}
    remove=[]
    for bar in range(40,56):
        group=[n for n in tt['guitar']['notes'] if int(n['on']//4)==bar]
        group.sort(key=lambda n:n['pitch'])
        for j,n in enumerate(group):
            n['pitch']=guitar_voicings[bar-bar%2][j]
            n['on']=bar*4+.5+j*.5
            n['duration']=3.4-j*.5
            if j==2:
                if bar%2==0: n['duration']+=4
                else: remove.append(n['id'])
    tt['guitar']['notes']=[n for n in tt['guitar']['notes'] if n['id'] not in remove]
    for nid in remove: tt['guitar']['performance']['notes'].pop(nid)
    # Measurements: the piano's opening correlation was 0.347, and the
    # response-based C80 was +29.5 dB. Narrow its sample and give the room
    # a defined, moderate presence. No timbral boost to chase the pop mean.
    for ident in ('piano','piano_left'): tt[ident]['mix']['width']=.5
    p['mix']['c80_db']=14
    p['decisions'] += [
      'analysis: R1 piano opening correlation 0.347 and mono change -1.72 dB prompted piano width 0.8 to 0.5, retaining the original mild left placement.',
      'analysis: R1 response-based C80 +29.5 dB prompted c80_db 14, a close song space with a more present late return; this is a written acoustic target, not a listening verdict.',
      'analysis: Keep the measured steep pop-relative spectrum. This is a soft cello-and-piano instrumental with pedal hats, no singer or bright crashes; broad treble boost would not serve the brief.',
      'analysis: R1 section levels rose -18.20, -16.37, -15.70, -14.74 LUFS before the -18.94 return; retain that long-form rise. The final chorus lead-bus margin was +5.2 dB, so no extra lead gain was warranted.',
      'phrasing: Half-beat breaths now end four-bar cello sentences. The piano continues through each breath, preserving the pulse.'
    ]
    p['revision_history'].append({'round':2,'change':'Revoice Ab harmony and guitar; resolve two piano phrase ends; add four-bar cello breaths; move two violin ninths; narrow piano stereo and set C80 to 14 dB. Retain the steady drum pattern and unchanged form, tempo, bass and kit notes.'})

def audit():
    import hashlib
    def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    p=json.loads((ROOT/'song.json').read_text(encoding='utf-8'))
    snap=json.loads((ROOT/'final/project.json').read_text(encoding='utf-8'))
    report=json.loads((ROOT/'final/report.json').read_text(encoding='utf-8'))
    review=json.loads((ROOT/'r2/review/score_review.json').read_text(encoding='utf-8'))
    midi=json.loads((ROOT/'midi_inspection.json').read_text(encoding='utf-8'))
    canonical=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    collisions=[]
    for t in p['tracks']:
        seen=set()
        for n in t['notes']:
            key=(n['on'],n['pitch'])
            if key in seen: collisions.append([t['id'],n['id']])
            seen.add(key)
    checks={
      'render_snapshot_equals_song':p==snap,
      'canonical_project_hash_matches_report':canonical==report['project_sha256'],
      'master_file_hash_matches_report':sha(ROOT/'final/master.wav')==report['master']['sha256'],
      'same_audio_as_second_round':sha(ROOT/'final/master.wav')==sha(ROOT/'r2/render/master.wav'),
      'all_eleven_delivery_checks_pass':len(report['checks'])==11 and all(report['checks'].values()),
      'no_unanswered_review_questions':not review['questions'],
      'one_unchanging_tempo':p['clock']['tempo']==[[0,74]],
      'five_long_sections':len(p['sections'])==5 and all(s['bars']>=8 for s in p['sections']),
      'opening_eight_bars_only_piano':all(n['on']>=32 for t in p['tracks'] if t['id'] not in ('piano','piano_left') for n in t['notes']),
      'last_four_bars_only_piano_notes':all(n['on']+n['duration']<=240 for t in p['tracks'] if t['id'] not in ('piano','piano_left') for n in t['notes']),
      'all_eight_parts_in_last_chorus':all(any(160<=n['on']<224 for n in t['notes']) for t in p['tracks']),
      'no_duplicate_same_onset_pitch_within_parts':not collisions,
      'midi_count_and_note_lifecycle':midi['notes']==938 and midi['unclosed']==0 and midi['stray_offs']==0,
    }
    manifest={'title':TITLE,'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,
      'file_hashes':{str(x.relative_to(ROOT)):sha(x) for x in [ROOT/'compose.py',ROOT/'song.json',ROOT/'song_r1.json',ROOT/'song_r2.json',ROOT/'final/master.wav',ROOT/'final/master.flac',ROOT/'final/preview.mp3',ROOT/'final/composition.mid']},
      'project_canonical_sha256':canonical,'direct_audio_listening_performed':False,
      'quality_claim':'Technical and score checks only; no perceptual sign-off.'}
    dump(ROOT/'verification.json',manifest)
    print(json.dumps({'status':manifest['status'],'checks':checks},indent=2))
    if not all(checks.values()): raise SystemExit(2)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--probe',action='store_true'); ap.add_argument('--revision',type=int,default=1); ap.add_argument('--audit',action='store_true')
    args=ap.parse_args()
    if args.audit: audit()
    else:
        dump(ROOT/'plan.json', {'title':TITLE,'clock':base()['clock'],'sections':base()['sections'],'plan':PLAN})
        if args.probe: probe()
        else: compose(args.revision)
