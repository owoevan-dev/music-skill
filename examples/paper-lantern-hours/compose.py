"""Writes song.json: 'Paper Lantern Hours', a lo-fi study beat, F major, 76 BPM, 40 bars, loops from bar 0."""
import sys, json, random, argparse
# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# lines named the folder where the skill was installed on the machine it ran on, and the piece's folder there as the default --out).
from pathlib import Path
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import expression, blocks

ap = argparse.ArgumentParser()
ap.add_argument('--round', type=int, default=2)
ap.add_argument('--out', default='song.json')
A = ap.parse_args()
R = A.round  # round 1 = first draft values; 2 = revised values

TITLE = 'Paper Lantern Hours'
BARS = 40
SEED = blocks.seed(TITLE)
rnd = random.Random(SEED)

sections = [
    {'id': 'intro', 'start_bar': 0, 'bars': 4, 'intent': 'Worn electric piano and vinyl alone; the loop seam lives here'},
    {'id': 'groove', 'start_bar': 4, 'bars': 8, 'intent': 'Drums and bass enter; the motif arrives in the last four bars'},
    {'id': 'theme', 'start_bar': 12, 'bars': 8, 'intent': 'Motif stated twice, answered and varied'},
    {'id': 'bridge', 'start_bar': 20, 'bars': 8, 'intent': 'Brighter IV-centred chords, half-time drums, motif in fragments'},
    {'id': 'return', 'start_bar': 28, 'bars': 8, 'intent': 'Motif returns with a high echo, fullest point'},
    {'id': 'outro', 'start_bar': 36, 'bars': 4, 'intent': 'Drums and bass fall away so the end meets the intro'},
]

# chords: (bar offset in 4-bar cycle, beat, symbol, voicing)
V = {
    'Fmaj9': [57, 60, 64, 67], 'Em7': [55, 59, 62, 64], 'A7b13': [55, 59, 61, 65] if R >= 2 else [55, 61, 64, 65], 'Dm9': [53, 57, 60, 64],
    'Gm9': [55, 58, 62, 65], 'C13': [58, 62, 64, 69],
    'Bbmaj9': [57, 60, 62, 65], 'Am7': [55, 60, 64, 67], 'D7b9': [54, 57, 60, 63],
}
ROOT = {'Fmaj9': 41, 'Em7': 40, 'A7b13': 33, 'Dm9': 38, 'Gm9': 43, 'C13': 36, 'Bbmaj9': 34 + 12, 'Am7': 45, 'D7b9': 38}
ROOT['Bbmaj9'] = 34
ROOT['Am7'] = 33
CYC_A = [(0, 0, 'Fmaj9'), (1, 0, 'Em7'), (1, 2, 'A7b13'), (2, 0, 'Dm9'), (3, 0, 'Gm9'), (3, 2, 'C13')]
CYC_B = [(0, 0, 'Bbmaj9'), (1, 0, 'Am7'), (1, 2, 'D7b9'), (2, 0, 'Gm9'), (3, 0, 'Gm9'), (3, 2, 'C13')]


def chords_for_bar(bar):
    cyc = CYC_B if 20 <= bar < 28 else CYC_A
    k = bar % 4
    return [(b, s) for (kk, b, s) in cyc if kk == k]


harmony = []
for bar in range(BARS):
    for b, s in chords_for_bar(bar):
        sym = {'Fmaj9': 'Fmaj9', 'Em7': 'Em7', 'A7b13': 'A7b13', 'Dm9': 'Dm9', 'Gm9': 'Gm9', 'C13': 'C13',
               'Bbmaj9': 'Bbmaj9', 'Am7': 'Am7', 'D7b9': 'D7b9'}[s]
        harmony.append({'bar': bar + 1, 'beat': b, 'symbol': sym})


class Part:
    def __init__(self, ident, name, role, **kw):
        self.t = {'id': ident, 'name': name, 'role': role, 'notes': [],
                  'performance': {'notes': {}}, 'mix': {}}
        self.t.update(kw)
        self.n = 0

    def add(self, bar, beat, dur, pitch, vel, tag=''):
        nid = f'{self.t["id"]}_b{bar+1:03d}_n{self.n:03d}'
        self.n += 1
        self.t['notes'].append({'id': nid, 'on': round(bar * 4 + beat, 4), 'duration': dur, 'pitch': pitch})
        self.t['performance']['notes'][nid] = {'velocity': int(vel), 'timing_ms': 0, 'gate': 1.0}
        return nid


# ---- keys: Surge electric piano, comping --------------------------------------------------------------------
keys = Part('keys', 'Worn electric piano', 'harmony', engine='surge',
            surge={'preset': 'bluelight/keys/treated_rhodes'}, range=[48, 72])
for bar in range(BARS):
    ch = chords_for_bar(bar)
    spans = []
    for i, (b, s) in enumerate(ch):
        end = ch[i + 1][0] if i + 1 < len(ch) else 4
        spans.append((b, end, s))
    for (b, end, s) in spans:
        v = V[s]
        quiet = bar < 4 or bar >= 38
        base = 54 if quiet else (56 if (R >= 2 and bar < 12) else 64 if (R >= 2 and 12 <= bar < 20) else 62)
        base += rnd.randint(-3, 3)
        if end - b == 4:
            # whole-bar chord: hit on 1, re-hit on the 'and' of 2 (anticipation of the lazy beat)
            for p in v:
                keys.add(bar, b, 1.75, p, base)
            if not quiet or bar % 2 == 1:
                for p in v[1:]:
                    keys.add(bar, b + 2.5, 1.2, p, base - 12)
        else:
            # half-bar chords: sustain through half the bar
            for p in v:
                keys.add(bar, b, (end - b) - 0.1, p, base)
            if b == 0 and not quiet:
                pass

# ---- melody on a worn upright piano ----------------------------------------------------------------------
mel = Part('piano', 'Worn upright piano (motif)', 'melody', engine='soundfont', soundfont='vcsl_keys',
           program=0, bank=0, patch={'bank': 0, 'program': 3}, range=[60, 88])
MOTIF = {  # per bar of the 4-bar cycle: (beat, pitch, dur, vel)
    'A': [
        [(0.5, 72, 1.0, 66), (1.5, 74, 0.5, 58), (2.0, 72, 0.5, 60), (2.5, 69, 1.5, 62)],
        [(0.5, 67, 1.0, 58), (1.5, 69, 0.5, 52), (2.5, 73, 1.5, 62)],
        [(0.5, 69, 1.0, 64), (1.5, 72, 0.5, 58), (2.0, 74, 0.5, 60), (2.5, 72, 1.5, 62)],
        [(0.5, 70, 1.0, 60), (1.5, 69, 0.5, 54), (2.5, 67, 0.5, 54)],
    ],
    # answer phrase: same cell, the end lifted so the second pass does not just repeat
    'A2': [
        [(0.5, 72, 1.0, 68), (1.5, 74, 0.5, 60), (2.0, 72, 0.5, 62), (2.5, 69, 1.5, 62)],
        [(0.5, 67, 1.0, 60), (1.5, 69, 0.5, 54), (2.5, 73, 0.5, 64), (3.0, 76, 1.0, 66)],
        [(0.5, 69, 1.0, 66), (1.5, 72, 0.5, 60), (2.0, 74, 0.5, 62), (2.5, 76, 1.0, 66)],
        [(0.5, 76, 1.0, 62), (1.5, 74, 0.5, 58), (2.5, 72, 1.5, 58)],
    ],
    'B': [  # bridge: cell moved down and thinned out
        [(0.5, 74, 1.0, 58), (1.5, 72, 0.5, 52)],
        [(0.5, 72, 1.0, 54), (1.5, 69, 0.5, 50), (2.5, 66, 1.5, 56)],
        [(0.5, 70, 1.0, 56), (1.5, 69, 0.5, 50), (2.5, 67, 1.5, 54)],
        [],
    ],
}
plan = {}
for bar in range(8, 12):
    plan[bar] = MOTIF['A'][bar % 4]
for bar in range(12, 16):
    plan[bar] = MOTIF['A'][bar % 4]
for bar in range(16, 20):
    plan[bar] = MOTIF['A2'][bar % 4]
for bar in range(20, 24):
    plan[bar] = MOTIF['B'][bar % 4]
for bar in range(24, 28):
    plan[bar] = MOTIF['B'][bar % 4] if bar < 26 else []
for bar in range(28, 32):
    plan[bar] = MOTIF['A'][bar % 4]
for bar in range(32, 36):
    plan[bar] = MOTIF['A2'][bar % 4]
for bar, evs in sorted(plan.items()):
    for (b, p, d, v) in evs:
        mel.add(bar, b, d, p, v + (4 if bar >= 28 else 0) + (6 if (R >= 2 and 20 <= bar < 28) else 0))
# high echo in the return section: the cell's first two notes an octave up, in bars 31 and 35, answering the melody
for bar, evs in [(29, [(3.0, 85, .5, 40)]), (31, [(2.5, 79, .5, 40), (3.0, 81, .75, 38)]),
                 (33, [(3.0, 88, .5, 38)]), (35, [(2.5, 81, .5, 38), (3.0, 84, 0.75, 36)])]:
    if R >= 2:
        for (b, p, d, v) in evs:
            mel.add(bar, b, d, p, v)

# ---- bass: upright, round ---------------------------------------------------------------------------------
bass = Part('bass', 'Upright bass', 'bass', engine='soundfont', soundfont='bass_sneaky', program=32, bank=0,
            range=[31, 52])
for bar in range(4, 38):
    if 36 <= bar:
        continue
    ch = chords_for_bar(bar)
    bridge = 20 <= bar < 28
    for i, (b, s) in enumerate(ch):
        end = ch[i + 1][0] if i + 1 < len(ch) else 4
        r = ROOT[s]
        if r > 45:
            r -= 12
        fifth = r + 7
        if end - b == 4:
            bass.add(bar, b, 1.4, r, 76)
            if bar % 2 == 0:
                bass.add(bar, b + 2.5, 0.9, fifth if fifth <= 50 else r - 5, 62)
            else:
                bass.add(bar, b + 2.0, 0.4, r, 54)
                bass.add(bar, b + 2.5, 0.8, fifth if fifth <= 50 else r - 5, 60)
            nxt = chords_for_bar((bar + 1) % BARS)[0][1]
            ar = ROOT[nxt]
            ar = ar - 12 if ar > 45 else ar
            if bar % 4 == 3 or rnd.random() < .5:
                bass.add(bar, 3.5, 0.5, ar + (1 if ar < r else -1), 50)
        else:
            bass.add(bar, b, (end - b) - 0.25, r, 74)
    if bar == 35:
        pass

# ---- drums: Big Rusty kit ---------------------------------------------------------------------------------
dr = Part('drums', 'Rusty kit', 'drums', engine='soundfont', soundfont='rusty', program=0, bank=0, drums=True,
          patch={'bank': 0, 'program': 0}, range=[35, 59])


def step(bar, s, key, vel):
    dr.add(bar, s * 0.25, 0.2, key, vel)


KICK_A = [0, 7, 10]
KICK_B = [0, 6, 10, 15]
for bar in range(4, 38):
    if bar >= 36:
        # outro: hat only in 36-37, silence 38-39 (seam meets the intro)
        if bar < 38:
            for s in range(0, 16, 2):
                step(bar, s, 42, 40 + (8 if s % 4 == 0 else 0))
        continue
    half = 20 <= bar < 28
    last = bar in (11, 19, 27, 35)
    pre = bar < 8
    # hats: swung eighths with ghost sixteenths
    for s in range(0, 16, 2):
        v = 62 if s % 4 == 0 else 46
        if R >= 2 and 12 <= bar < 20:
            v += 6
        if pre:
            v -= 8
        step(bar, s, 42, v + rnd.randint(-4, 4))
    for s in (3, 11, 15):
        if rnd.random() < (.55 if R >= 2 else .3):
            step(bar, s, 42, 28 + rnd.randint(0, 8))
    if bar % 4 == 3:
        step(bar, 14, 46, 44)
    # kick
    ks = KICK_A if bar % 2 == 0 else KICK_B
    if half:
        ks = [0, 10] if bar % 2 == 0 else [0, 7]
    for s in ks:
        step(bar, s, 36, 92 if s == 0 else 70 + rnd.randint(-4, 4))
    # snare / side stick
    if half:
        step(bar, 8, 38, 78)
        step(bar, 8, 37, 40)
    else:
        step(bar, 4, 38, 82)
        step(bar, 12, 38, 86)
        if R >= 2:
            step(bar, 4, 37, 36)
        if rnd.random() < .6 and not last and not (R >= 2 and bar < 12):
            step(bar, 15 if bar % 2 else 9, 38, 30 + rnd.randint(0, 6))
    if last and not half:
        step(bar, 13, 38, 46); step(bar, 14, 38, 52); step(bar, 15, 38, 60)

# ---- vinyl --------------------------------------------------------------------------------------------------
vinyl = Part('vinyl', 'Vinyl surface noise', 'effect', engine='noise', range=[24, 96])
vid = vinyl.add(0, 0, BARS * 4, 60, 70)
vinyl.t['notes'][0]['articulation'] = 'vinyl'

# ---- assemble --------------------------------------------------------------------------------------------
tracks = [keys.t, mel.t, bass.t, dr.t, vinyl.t]

keys.t['performance'].update({'swing': {'ratio': 0.56, 'unit': 0.5}, 'offset_ms': 8})
mel.t['performance'].update({'swing': {'ratio': 0.58, 'unit': 0.5}, 'offset_ms': 14})
bass.t['performance'].update({'swing': {'ratio': 0.56, 'unit': 0.5}, 'offset_ms': 12})
dr.t['performance'].update({'swing': {'ratio': 0.60, 'unit': 0.25}})

keys.t['mix'] = {'level_dbfs': (-27 if R >= 2 else -23), 'level_mode': 'active_rms', 'pan': -0.15, 'highpass': 110, 'lowpass': 3600,
                 'reverb_db': -14, 'wow_flutter': {'wow_cents': 9, 'wow_hz': 0.6, 'flutter_cents': 2.5},
                 'duck': {'by': 'drums', 'keys': [36], 'depth_db': 3.5, 'attack_ms': 5, 'hold_ms': 40, 'release_ms': 220},
                 'eq': [[300, -1.0]]}
mel.t['mix'] = {'level_dbfs': (-19 if R >= 2 else -21), 'level_mode': 'active_rms', 'pan': 0.12, 'highpass': 180, 'lowpass': 4800,
                'reverb_db': -12, 'width': 0.5,
                'wow_flutter': {'wow_cents': 11, 'wow_hz': 0.45, 'flutter_cents': 2},
                'effects': [{'type': 'chorus', 'depth': 0.25}]}
bass.t['mix'] = {'level_dbfs': (-24 if R >= 2 else -22), 'level_mode': 'active_rms', 'pan': 0, 'highpass': 38, 'lowpass': 900,
                 'reverb_db': None, 'saturate': 0.15,
                 'compressor': {'threshold_db': -26, 'ratio': 2.5, 'attack_ms': 20, 'release_ms': 120}}
dr.t['mix'] = {'level_dbfs': -23, 'level_mode': 'active_rms', 'pan': 0, 'highpass': 40, 'lowpass': 7000,
               'reverb_db': -20, 'saturate': 0.25,
               'effects': [{'type': 'bitcrush', 'bits': 12, 'downsample': 2, 'mix': 0.6}]}
vinyl.t['mix'] = {'level_dbfs': -28, 'level_mode': 'peak', 'pan': 0, 'highpass': 80, 'lowpass': 9000,
                  'reverb_db': None}

project = {
    'schema': 'music-production/v1', 'title': TITLE, 'version': f'1.0.r{R}',
    'brief': 'Lo-fi hip-hop study beat, ~2 min, seamless loop: worn electric piano on seventh chords, round upright bass, '
             'swung dusty drums, vinyl; a short motif (up a step, back, down to the sixth) keeps returning.',
    'style': {'primary': 'beats/lo-fi'},
    'clock': {'bars': BARS, 'meter': [4, 4], 'tempo': [[0, 76]], 'tail_seconds': 4},
    'sections': sections, 'harmony': harmony, 'tracks': tracks,
    'loop': {'start_bar': 0},
    'mix': {'chain': 'bus', 'rules': 2, 'target_lufs': -14, 'dynamics': 'glue',
            'wow_flutter': {'wow_cents': 4, 'wow_hz': 0.35}},
}
project['decisions'] = ['Motif (C D C A) heard in the cycle A bars, moved down in the bridge, lifted at its end in the answer phrase.']
for t in tracks:
    t['performance'].setdefault('notes', {})

expression.apply(project, {'drums': None, 'vinyl': None} if False else {'vinyl': None}, SEED, drift='time')
# drums: keep authored velocities but add the small human drift
json.dump(project, open(A.out, 'w'), indent=1)
print('wrote', A.out, 'notes:', {t['id']: len(t['notes']) for t in tracks})
