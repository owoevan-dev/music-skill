"""The Stone Vault Turns to Light -- every note authored here.

Run: python compose.py --revision 4  (1-3 reproduce the earlier rounds)
The --probe option writes only registration_probe.json for the preliminary test.
No scores, MIDI files, melodies or progressions are imported.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# lines named the folder where the skill was installed on the machine it ran on, and a temporary folder there).
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import expression
from musiclib.model import Clock, validate
from musiclib.harmony import parse as parse_chord

ROOT = Path(__file__).resolve().parent
TITLE = 'The Stone Vault Turns to Light'
SEED = 2611111957

def track(tid, name, bank, role, level, pan=0.0, low=48, high=88):
    return dict(id=tid, name=name, role=role, engine='soundfont',
                soundfont='organ_vcsl', patch={'bank': bank, 'program': 19},
                program=19, bank=bank, range=[low, high], notes=[],
                performance={'notes': {}, 'offset_ms': -25 if bank != 2 else -30,
                             'cc': [[0, 11, 127]], 'round_robin': False},
                mix={'level_dbfs': level, 'level_mode': 'active_rms', 'pan': pan,
                     'highpass': 18 if bank == 2 else 55, 'lowpass': 18000,
                     'reverb_db': -5.5 if bank != 2 else -8,
                     'delay_db': None, 'space': 'church', 'width': 0.65,
                     'bus': 'lead' if role == 'melody' else 'ensemble'})

def note(t, bar, beat, pitch, duration, tag, gate=.92, velocity=96, phrase=None):
    nid = f"{t['id']}_b{bar+1:03d}_{tag}"
    assert nid not in t['performance']['notes'], nid
    t['notes'].append({'id': nid, 'on': bar*4+beat, 'duration': duration,
                       'pitch': pitch, 'phrase': phrase or f'p{bar//4:02d}'})
    t['performance']['notes'][nid] = {'velocity': velocity, 'timing_ms': 0, 'gate': gate}

def save(project, filename):
    validation = validate(project)
    (ROOT / filename).write_text(json.dumps(project, indent=2) + '\n', encoding='utf-8')
    print(filename, validation)
    return project

def probe():
    ts = [track('full_probe', 'Full manual range and velocity', 0, 'harmony', -24, low=36, high=96),
          track('soft_probe', 'Stopped flute range and velocity', 1, 'harmony', -24, low=43, high=96),
          track('pedal_probe', 'Pedal range and velocity', 2, 'bass', -24, low=24, high=55)]
    for i, (t, pitches) in enumerate(zip(ts, ([50,62,74,86], [50,62,74,86], [26,33,38,45]))):
        for j, p in enumerate(pitches):
            note(t, i*3, j, p, .8, f'range{j}', gate=.9)
        for j, vel in enumerate([48,96]):
            note(t, i*3+1, j*2, pitches[1], 1.6, f'velocity{vel}', gate=1, velocity=vel)
        note(t, i*3+2, 0, pitches[1], 3.5, 'expression', gate=1)
        t['performance']['cc'] += [[(i*3+2)*4+1.5,11,75], [(i*3+2)*4+3.5,11,127]]
        t['mix']['highpass'] = 18
    return save({'schema':'music-production/v1','title':TITLE+' registration probe','version':'probe',
                 'clock':{'bars':9,'meter':[4,4],'tempo':[[0,120]],'tail_seconds':3},
                 'sections':[{'id':'probe','start_bar':0,'bars':9,'intent':'Verify registration range, fixed velocity and CC11 response'}],
                 'tracks':ts,'mix':{'chain':'bus','rules':2,'dynamics':'wide','target_lufs':-20}}, 'registration_probe.json')

def compose(revision):
    # Bar-by-bar harmonic route, written for this piece rather than a stock loop.
    intro = 'Dm Dm Gm/D A7'.split()
    theme = ('Dm Dm/F Em7b5 A7 Bb Gm/Bb Dm/A A7 '
             'Dm F/A C/E F Bb/D Gm A7sus4 A7 '
             'Dm/F Bb Eb/G Gm/Bb Edim7 A7 Dm Dm').split()
    development = ('F#m F#m/A Bm D/F# G G/B E/G# A '
                   'C C/E Fm/Ab Db/F Ebm/Gb Ab7/C A7sus4 A7').split()
    middle = ('Bb Bb/D Eb Eb/G Gm D7/F# Gm Gm7/F '
              'Eb Cm/Eb F7 F7/A Bb Bb7/Ab Eb/G Ebm/Gb '
              'Bb/F F7 Dm/A A7').split()
    gathering = 'Dm Dm/C Bbmaj7 Gm/Bb Em7b5/G A7 Dm/A A7'.split()
    returning = ('D D/F# Em7 G A7sus4 A7 Bm G/B '
                 'D/A A7 D D/F# G Gm/Bb D/A E7/G# '
                 'A A/C# D/F# Bb G/B A7sus4 A7 D').split()
    coda = 'G/D Gm/D D/A A7 D D D D'.split()
    chords = intro + theme + development + middle + gathering + returning + coda
    assert len(chords) == 104
    full_r = track('full_r', 'Right hand - full manual figuration', 0, 'rhythm', -26, .10, 60, 90)
    full_l = track('full_l', 'Left hand - full manual', 0, 'harmony', -28, -.10, 48, 74)
    soft_r = track('soft_r', 'Right hand - stopped flute cantilena', 1, 'melody', -31, .06, 60, 88)
    soft_l = track('soft_l', 'Left hand - stopped flute support', 1, 'harmony', -35, -.06, 48, 72)
    pedal = track('pedal_theme', 'Pedal - striding theme at sounding pitch', 2, 'melody', -21.5, 0, 24, 55)
    tracks = [full_r, full_l, soft_r, soft_l, pedal]
    sections = [
      ('threshold',0,4,'Manual figure opens above a tonic pedal; dominant intake',2),
      ('stone_stride',4,24,'Pedal theme in three eight-bar paragraphs; D minor, half cadence then tonic',3),
      ('turning_stair',28,16,'Fragment and transpose the stride through chromatic mediants; dominant return',4),
      ('inner_chapel',44,20,'Stopped-flute cantilena in B-flat; two hands, restrained pedal; quiet centre',1),
      ('rekindling',64,8,'Recover the figure, then full left manual; prepare the major-mode return',2),
      ('open_vault',72,24,'D-major transformation, wider register and faster left hand, full-organ accumulation',5),
      ('last_light',96,8,'Minor-subdominant recollection, final dominant, fourteen-beat major chord and release',5)]
    p = {'schema':'music-production/v1', 'title':TITLE, 'version':f'1.0.r{revision}',
         'brief':'Original Romantic pipe-organ toccata for one organist in a large church; running hands above a striding pedal theme, quiet flute middle, D-major full-organ return.',
         'style':{'primary':'orchestral/romantic','borrow':{'rhythm':'orchestral/baroque','timbre':'orchestral/baroque'}},
         'clock':{'bars':104,'meter':[4,4],
                  'tempo':[[0,120],[108,112],[112,124],[172,108],[176,92],[252,84],
                           [256,104],[272,112],[284,106],[288,120],[320,124],[352,128],
                           [380,116],[384,108],[392,96],[396,84],[400,70]],
                  'tail_seconds':8,
                  'rubato':{'phrase_ratio':.97,'phrase_beats':1,'final_ratio':1,'final_beats':1}},
         'sections':[{'id':s,'start_bar':b,'bars':n,'intent':intent} for s,b,n,intent,e in sections],
         'tracks':tracks,
         'harmony':[{'bar':b+1,'symbol':c} for b,c in enumerate(chords)],
         'mix':{'chain':'bus','rules':2,'dynamics':'wide','target_lufs':-18,'c80_db':3},
         'decisions':[
             'Romantic primary: chromatic-mediant development, modal mixture, rubato, transformed return and broad dynamic contrast.',
             'Borrow Baroque rhythm only for continuous motor figuration, and timbre only for pipe organ; this is a ternary toccata, without fugal exposition, imitative entries or a borrowed model.',
             'Theme first: D2 dotted half, F2 quarter | F2 half, D2 half | E2 dotted half, G2 quarter | A1 dotted half, C#2 quarter. Each is checked against its authored harmony.',
             'Organ dynamics come from fixed registrations, texture and declared expression-level automation; key velocity is fixed and does not control the organ.',
             'One player, two manual hands and monophonic pedal. The low thematic line is foreground; manual figuration deliberately lies above it.',
             'The church response and C80 target are a design choice, not a claim about an actual building or a listening judgement.',
             'The final chord holds fourteen quarter beats at 70 BPM, followed by two beats of written rest and eight seconds of tail.'
         ],
         'authorship':{'method':'Every note written by compose.py, with explicit harmony and manually designed theme, figure cells and form.',
                       'external_scores_or_midi':False,'reference_recording':None,'audio_generation_model':False,
                       'seed':SEED,'sample_bank':'Installed VCSL organ build b2; CC0 samples'},
         'revision_history':[{'revision':1,'change':'First complete authored score and registration-aware bus mix.'}]}

    def pcs(symbol):
        result = parse_chord(symbol)
        return sorted(result['pcs'])

    def pool(symbol, low, count=4):
        found = [x for x in range(low,97) if x % 12 in pcs(symbol)]
        return found[:count]

    def bass(symbol):
        name = symbol.split('/')[-1] if '/' in symbol else symbol
        pc = {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[name[0]]
        if len(name)>1 and name[1] in '#b': pc += 1 if name[1]=='#' else -1
        return 24+(pc%12) if pc%12 >= 7 else 36+(pc%12)

    # The figure has its own changing contour; alternating cells retain identity.
    cells = [[0,2,1,3,2,1,0,1, 2,3,1,2,3,2,1,0],
             [2,1,0,1,3,2,1,2, 0,1,2,3,2,0,1,2],
             [0,1,3,2,1,2,0,1, 3,2,1,0,1,2,3,1],
             [3,2,1,2,0,1,2,3, 1,2,0,1,2,1,3,2]]
    for b,symbol in enumerate(chords[:100]):
        if 44 <= b < 64:
            continue
        r = soft_r if 64 <= b < 72 else full_r
        l = soft_l if 64 <= b < 68 else full_l
        low = 62 if b<28 else (65 if b<44 else 62)
        if 72<=b<88: low=65
        if 88<=b<96: low=70
        if b>=96: low=69
        rp = pool(symbol,low)
        lp = pool(symbol,50,4)
        cell=cells[(b//2)%4]
        step=.5 if 64<=b<68 else .25
        count=8 if step==.5 else 16
        # A one-beat breath at the two major boundaries clears the church tail.
        if b in (43,63,71): count-=int(1/step)
        if b>=96: count=12 if b<98 else 8
        for j in range(count):
            pitch=rp[cell[j]]
            gate=.91 if j%4 else .98
            if j==count-1 and b%4==3: gate=.78
            note(r,b,j*step,pitch,step,f'f{j:02d}',gate)
        if b>=96:
            # Cadential blocks occupy one hand each; spans stay within an octave.
            for k,pitch in enumerate(lp[:3]):
                note(l,b,0,pitch,3.55,f'cad{k}',.98)
        else:
            step_l=.25 if 88<=b<96 else .5
            count_l=16 if step_l==.25 else 8
            if b<4: count_l=4
            if b in (27,43,71): count_l-=2
            pat=[1,0,2,1,3,2,1,2] if b%2 else [0,2,1,3,1,2,0,1]
            for j in range(count_l):
                note(l,b,j*step_l,lp[pat[j%8]],step_l,f'a{j:02d}',.90)

    # Pedal exposition: three related sentences, separately specified pitches.
    pedal_pairs = [
      [38,41],[41,38],[40,43],[33,37],[34,38],[31,34],[33,38],[33],
      [38,41],[33,36],[40,36],[41],[38,41],[31,34],[33,38],[33],
      [41,38],[34,38],[43,39],[34,31],[40,43],[33,37],[38,33],[38]]
    for b in range(100):
        symbol=chords[b]
        if b<4:
            pairs=[26] if b<3 else [33]
        elif b<28:
            pairs=pedal_pairs[b-4]
        elif 44<=b<64:
            if b in (44,45,52,53,60,61): continue
            pairs=[bass(symbol)]
        elif 64<=b<66:
            continue
        elif 72<=b<96:
            idx=b-72
            root=bass(symbol)
            # Preserve the dotted/half-note stride in major; alternate root and a chordal third.
            options=[x for x in range(root+2,min(root+8,55)) if x%12 in pcs(symbol)]
            pairs=[root,options[0]] if options and idx%8!=7 else [root]
        else:
            root=bass(symbol)
            options=[x for x in range(root+2,min(root+8,55)) if x%12 in pcs(symbol)]
            pairs=[root,options[0]] if options and b%4 in (0,2) and b<96 else [root]
        starts=[0,3] if (b-4)%4 in (0,2,3) else [0,2]
        if len(pairs)==1:
            dur=3.55 if b%4==3 else 3.88
            note(pedal,b,0,pairs[0],dur,'theme0',.98)
        else:
            for j,pitch in enumerate(pairs):
                length=(starts[1] if j==0 else 4-starts[1])
                note(pedal,b,starts[j],pitch,length,'theme'+str(j),.96)

    # Quiet cantilena: a transformed version of the pedal's dotted/half-note cell.
    quiet = [[74,77],[77,74],[75,79],[79,75], [74,70],[72,69],[70,69,67],[65,70],
             [67,70],[72,67],[69,72],[72,69], [74,77],[74,72],[70,67],[69,66],
             [65,70],[69,67,65],[65,62],[64,61]]
    for i,pitches in enumerate(quiet):
        b=44+i
        starts=[0,3] if i%2==0 else [0,2]
        lengths=[3,1] if i%2==0 else [2,2]
        if len(pitches)==3: starts,lengths=[0,2,3],[2,1,1]
        for j,(pitch,on,dur) in enumerate(zip(pitches,starts,lengths)):
            note(soft_r,b,on,pitch,dur,'cant'+str(j),.96 if i%4!=3 else .89)
        voicing=pool(chords[b],50,3)
        for j,pitch in enumerate(voicing):
            note(soft_l,b,.25 if i%2 else 0,pitch,3.45,'chord'+str(j),.97)
    # Last chord: a single held event per voice; no invented reed/coupler patches.
    for t,ps in [(full_r,[74,78,81,86]),(full_l,[50,57,62]),(pedal,[26])]:
        for j,pitch in enumerate(ps): note(t,100,0,pitch,14,'final'+str(j),1)

    if revision >= 2:
        # r1 review, question 3: keep the pedal theme and open the manual's spacing.
        raised = {7:50,19:52,31:50,32:50,33:50,34:50,43:52,
                  73:50,74:50,75:50,77:52,79:50,80:50,83:50,84:50,85:50}
        for n in full_l['notes']:
            bar=int(n['on']//4)+1
            if bar in raised and n['pitch']==raised[bar]: n['pitch']+=12
        for n in soft_l['notes']:
            if int(n['on']//4)+1==50 and n['pitch']==50: n['pitch']+=12
        # r1 question 5: each four-bar flute phrase now has a different accompaniment
        # gesture. Stable ids remain attached to the musical event they began with.
        for n in soft_l['notes']:
            b=int(n['on']//4)
            if 44<=b<64:
                voice=int(n['id'][-1])
                pos=(b-44)%4
                if pos==0:
                    n['on']=b*4+[0,.5,1][voice]
                    n['duration']=[3.7,3.15,2.55][voice]
                elif pos==1:
                    n['on']=b*4+[0,.25,1.5][voice]
                    n['duration']=[3.7,3.2,2.1][voice]
                elif pos==2:
                    n['on']=b*4+[0,1,2][voice]
                    n['duration']=[3.7,2.6,1.55][voice]
                else:
                    n['on']=b*4
                    n['duration']=[3.75,3.5,3.25][voice]
        p['revision_history'].append({'revision':2,'change':'Manual-support clarity: lift the 17 questioned low-interval locations; stagger and vary the stopped-flute left-hand chord entries/releases. Keep velocity and exposition/development density with documented reasons.'})
        p['decisions'] += [
            'r1 Q1/Q2 kept: velocity is intentionally fixed at 96 because all three registrations ignore velocity. Timing, articulation, registration and expression-level automation carry phrasing.',
            'r1 Q3 changed: selected low D3/E3 manual tones move up an octave at each of the 17 flagged locations, leaving the pedal theme intact.',
            'r1 Q4 kept: exposition and development intentionally retain motor density; development changes harmonic region to F-sharp minor, C major and F minor/flat-side harmony, raises the right-hand register, fragments pedal statements and changes tempo.',
            'r1 Q5 changed: middle-section left-hand chords now enter as four distinct phrase gestures, with different note releases; the fourth bar retains a chordal cadence.'
        ]

    if revision >= 3:
        # A single organ cannot make one key louder by having both hands press it.
        # Reassign only the ten left-hand events found in the two-hand audit.
        reassigned=[]
        for n in full_l['notes']:
            overlaps=[r for r in full_r['notes'] if r['pitch']==n['pitch'] and
                      min(n['on']+n['duration'],r['on']+r['duration'])>max(n['on'],r['on'])+.03]
            if overlaps:
                b=int(n['on']//4)
                candidates=[x for x in range(max(53,n['pitch']-7),n['pitch']) if x%12 in pcs(chords[b])]
                old=n['pitch']; n['pitch']=max(candidates)
                reassigned.append({'note':n['id'],'from':old,'to':n['pitch']})
        p['revision_history'].append({'revision':3,'change':'Remove ten duplicate full-manual key presses between the two hands; retain right-hand figures and pedal pitches.', 'events':reassigned})
        p['decisions'].append('r3: same-key events shared by both full-manual tracks are reassigned to the nearest lower chord tone in the left hand. This avoids treating one pipe rank as two independent instruments on those keys.')

    # Organ expression is written as level changes: no fictitious velocity dynamics.
    full_r['mix']['automation']=[[0,-3],[16,-1.5],[108,-1.5],[112,-.5],[172,-1],
                                 [288,-2],[320,-.5],[352,1],[384,1.5],[400,2]]
    full_l['mix']['automation']=[[0,-5],[16,-1.5],[112,-.5],[172,-1],
                                 [272,-4],[288,-2],[320,-.5],[352,1],[400,2]]
    soft_r['mix']['automation']=[[0,0],[176,0],[240,-1],[256,-1],[284,1]]
    soft_l['mix']['automation']=[[0,0],[176,0],[240,-1],[256,-1],[272,0]]
    pedal['mix']['automation']=[[0,-7],[16,0],[172,-1],[176,-12],[252,-12],
                               [256,-7],[284,-4],[288,-1],[320,0],[352,1],[400,2]]
    if revision >= 4:
        # One audit follow-up: the first replacement at b19 met another RH note.
        next(n for n in full_l['notes'] if n['id']=='full_l_b019_a04')['pitch']=57
        # A gradual return, with
        # less of the whole-piece headroom consumed by the large closing chord.
        for t in (full_r, full_l):
            t['mix']['automation']=[point for point in t['mix']['automation'] if point[0]<352]+[
                [352,2],[368,4],[380,4.5],[384,4.5],[392,4],[396,3],[399.75,.5],[400,-1]]
        pedal['mix']['automation']=[point for point in pedal['mix']['automation'] if point[0]<352]+[
                [352,2],[368,4],[380,4.5],[384,4.5],[392,4],[396,3],[399.75,1.5],[400,1]]
        p['revision_history'].append({'revision':4,'change':'Broaden the return crescendo after bar 81, reaching the increased levels at bars 89-97, then compensate the much denser final manual chord by 3 dB and its pedal by 1 dB relative to r3. Also complete the two-hand audit at b19: move the replacement D4 to A3, since D4 met the preceding RH sixteenth. All other score events and the quiet centre are unchanged.'})
        p['decisions'].append('r4: r1/r2 measurements put the coda about 7.4 LU above the returning section and held master gain 2.8 dB below target. Shape the written late-section automation to spread the arrival across the return and coda, leaving wide dynamics and the long final chord intact.')
    overrides={}
    for t in tracks:
        overrides[t['id']]={'timing_sd':2.0,'short_sd':.7,'feel':0,'vel_pct':0,
                            'high_loud':0,'arch':0,'spread':1.5,'lead':1,
                            'gate_sd':.006,'contrast':0,'swell':0}
    expression.apply(p,overrides,seed=SEED,drift='time')
    # Fixed release of the fermata, and no negative pre-roll at the first attack.
    for t in tracks:
        for n in t['notes']:
            if n['on']==400: t['performance']['notes'][n['id']]['gate']=1
    save(p,'song.json')
    save(p,f'song_r{revision}.json')
    clock=Clock(p)
    summary={'title':TITLE,'revision':revision,'duration_seconds':clock.end+clock.tail,
             'last_chord_seconds':clock.seconds(414)-clock.seconds(400),
             'sections':[{'id':s,'bars':[b+1,b+n],'start_s':clock.seconds(b*4),
                          'end_s':clock.seconds((b+n)*4),'energy_plan':e} for s,b,n,intent,e in sections]}
    (ROOT/f'form_r{revision}.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return p

if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--probe', action='store_true')
    ap.add_argument('--revision', type=int, default=4, choices=[1,2,3,4])
    args=ap.parse_args()
    probe() if args.probe else compose(args.revision)
