"""Fughetta in D minor for harpsichord and strings -- composition script.

Writes every note of song.json.  Run:  python compose.py
Each voice is written by hand as a token stream "Pitch:beats" (r = rest); '|' checks that a bar line falls there.
"""
import json
import os
import re
import sys

# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# line named the folder where the skill was installed on the machine it ran on).
from pathlib import Path  # noqa: E402
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import expression  # noqa: E402
from musiclib.voicing import voice_lead  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BAR = 4.0
TEMPO = 76
BARS = 36

NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def midi(name):
    m = re.fullmatch(r'([A-G])(#|b)?(-?\d)', name)
    if not m:
        raise ValueError(name)
    pc = NAMES[m.group(1)] + {'#': 1, 'b': -1, None: 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + pc


def parse(start_bar, text):
    """Token stream -> list of (on_beat, dur, pitch). start_bar is 1-based."""
    pos = (start_bar - 1) * BAR
    out = []
    for tok in text.split():
        if tok == '|':
            if abs(pos / BAR - round(pos / BAR)) > 1e-9:
                raise ValueError(f'bar check failed at beat {pos} (bar {pos / BAR + 1:.2f}) in segment from bar {start_bar}')
            continue
        name, dur = tok.split(':')
        dur = float(dur)
        if name != 'r':
            out.append((pos, dur, midi(name)))
        pos += dur
    return out, pos


def voice(segments):
    notes = []
    for bar, text in segments:
        n, _ = parse(bar, text)
        notes += n
    return notes


# ---------------------------------------------------------------- the voices
VLN1 = voice([(1, """
r:.5 D5:.5 F5:.5 E5:.5 Bb5:1 A5:.5 G5:.5 |
F5:.5 E5:.5 F5:.5 D5:.5 C#5:.5 D5:.5 E5:.5 A4:.5 |
D5:.5 C5:.5 E5:1 A5:1 G5:.5 F5:.5 |
E5:1.5 D5:.5 B4:1 D5:1 |
C5:1 D5:1 G5:2 |
A5:1.5 Bb5:.5 A5:2 |
F5:1 E5:1 F5:1 G5:1 |
A5:2 B5:1 G#5:1 |
A5:2 G5:1 F5:.25 E5:.25 F5:.25 E5:.25 |
D5:1 F5:2 E5:4 D5:1 |
D5:2 F5:2 |
F5:1 E5:1 G5:1 A5:.25 G5:.25 A5:.25 G5:.25 |
F5:.5 A4:.5 C5:1 F5:1 E5:.5 D5:.5 |
C5:1.5 Bb4:.5 G4:1 Bb4:1 |
A4:1 A5:1 Bb5:1 C6:1 |
A5:1.5 G5:.5 E5:1 G5:1 |
F5:1 r:3 |
r:4 |
F5:3 Eb5:4 D5:1 |
D5:2 G5:1 F5:.5 Eb5:.5 |
D5:1.5 C5:.5 A4:1 C5:1 |
Bb4:1 D5:1 E5:1 G5:1 |
F5:1 A5:1 G5:1 Bb5:1 |
A5:.5 D5:.5 F5:.5 E5:.5 Bb5:1 A5:.5 G5:.5 |
F5:.5 E5:.5 F5:.5 D5:.5 C#5:.5 D5:.5 E5:.5 A4:.5 |
D5:1 A5:1 G5:1 Bb5:1 |
A5:.5 C#6:.5 E6:.5 D6:.5 C#6:.5 Bb5:.5 A5:.5 G5:.5 |
D5:1 A5:1 D6:1 C6:.5 Bb5:.5 |
A5:1.5 G5:.5 E5:1 G5:1 |
F5:1 E5:.5 F5:.5 G5:1 Bb5:1 |
A5:1 G5:.5 F5:.75 E5:.25 F5:.25 E5:.25 F5:.25 E5:.25 D5:.25 E5:.25 |
D5:4 |
F5:2 E5:2 |
D5:4 |
""")])

VLN2 = voice([(3, """
r:.5 A4:.5 C5:.5 B4:.5 F5:1 E5:.5 D5:.5 |
C5:.5 B4:.5 C5:.5 A4:.5 G#4:.5 A4:.5 B4:.5 E4:.5 |
A4:2 D5:1 C5:.5 Bb4:.5 |
A4:1.5 G4:.5 E4:1 G4:1 |
F4:1 A4:1 D5:1 C5:3 E5:2 |
E5:1 D5:1 Bb4:1 A4:1 |
A4:2 Bb4:3 A4:4 G4:1 A4:2 |
G4:2 Bb4:2 |
r:4 | r:4 |
F4:1 C5:1 F5:1 E5:.5 D5:.5 |
C5:1.5 Bb4:.5 G4:1 Bb4:1 |
A4:1 r:3 |
r:4 |
A4:2 Bb4:3 A4:3 |
Bb4:1 G4:1 C5:2 |
Bb4:1 G4:1 D4:2 |
D4:1 G4:1 C#5:1 Bb4:1 |
A4:1 D5:3 |
C#5:.5 A4:1.5 G4:2 |
r:.5 D4:.5 F4:.5 E4:.5 Bb4:1 A4:.5 G4:.5 |
F4:.5 E4:.5 F4:.5 D4:.5 C#4:.5 D4:.5 E4:.5 A3:.5 |
D4:1 C#4:1 E4:2 |
F4:1 D5:3 |
F5:2 A4:2 |
A4:2 D5:1 E5:1 |
D5:2 C#5:2 |
A4:2.5 G4:.5 Bb4:.5 A4:.5 |
A4:2 G4:2 |
F#4:4 |
""")])

VIOLA = voice([(5, """
r:.5 D4:.5 F4:.5 E4:.5 Bb4:1 A4:.5 G4:.5 |
F4:.5 E4:.5 F4:.5 D4:.5 C#4:.5 D4:.5 E4:.5 A3:.5 |
D4:.5 C4:.5 E4:1 A4:1 G4:.5 F4:.5 |
E4:1.5 D4:.5 B3:1 D4:1 |
C#4:1 D4:2.5 C#4:.5 |
D4:.5 F4:.5 D4:.5 A3:.5 G3:.5 Bb3:.5 G3:.5 D4:.5 |
C4:.5 E4:.5 C4:.5 G3:.5 F3:.5 A3:.5 F3:.5 C4:.5 |
Bb3:.5 D4:.5 Bb3:.5 F3:.5 F4:.5 D4:.5 A3:.5 D4:.5 |
C4:1 G3:1 E4:.5 C4:.5 E4:.5 G4:.5 |
F4:1 r:3 |
r:4 | r:4 | r:4 | r:4 | r:4 |
D4:3 Bb3:1 |
C4:4 |
Bb3:.5 G3:.5 Bb3:.5 A3:.5 Eb4:1 D4:.5 C4:.5 |
Bb3:.5 A3:.5 Bb3:.5 G3:.5 F#3:.5 G3:.5 A3:.5 D3:.5 |
G3:.5 Bb3:.5 D4:.5 C4:.5 Bb3:.5 G3:.5 Bb3:.5 A3:.5 |
A3:.5 D4:.5 F4:.5 E4:.5 D4:.5 Bb3:.5 D4:.5 F4:.5 |
E4:.5 F4:1.5 D4:2 |
A3:2 E3:2 |
F3:2 E3:2 |
A3:2 G3:2 |
F3:1.5 G3:.5 D4:2 |
D4:1 A3:1 E4:2 |
F4:2 D4:1 G3:1 |
A3:2 G3:2 |
F3:.5 D4:.5 F4:.5 E4:.5 D4:1 Bb3:1 |
D4:2 C#4:2 |
D4:4 |
""")])

PEDAL = ' '.join(['A2:.5'] * 32)
CELLO = voice([(7, f"""
r:.5 A2:.5 C3:.5 B2:.5 F3:1 E3:.5 D3:.5 |
C3:.5 B2:.5 C3:.5 A2:.5 G#2:.5 A2:.5 B2:.5 E2:.5 |
A2:1 F2:1 G2:1 A2:1 |
D3:1 D2:1 G2:2 |
C3:1 C2:1 F2:2 |
Bb2:2 D3:1 D2:1 |
C3:1 C2:1 C3:1 G2:1 |
F2:1 A2:1 Bb2:1 G2:1 |
A2:1 F2:1 C3:1 C2:1 |
F2:1 A2:.5 G2:.5 D3:1 C3:.5 Bb2:.5 |
A2:.5 G2:.5 A2:.5 F2:.5 E2:.5 F2:.5 G2:.5 C2:.5 |
F2:1 A2:1 Bb2:1 D3:1 |
G2:1 E2:1 A2:1 C#3:1 |
D3:1 D2:1 G2:2 |
C3:1 A2:1 D3:1 F#2:1 |
G2:1 Bb2:1 C3:2 |
G2:2 D3:2 |
G2:2 E2:2 |
F2:2 Bb2:2 |
{PEDAL} |
D3:1 F3:.5 E3:.5 Bb3:1 A3:.5 G3:.5 |
F3:.5 E3:.5 F3:.5 D3:.5 C#3:.5 D3:.5 E3:.5 A2:.5 |
D3:1 C3:1 Bb2:1 E2:1 |
A2:4 |
D3:4 |
D3:2 A2:2 |
D2:4 |
""")])

# Harpsichord obbligato (8'+4'): the subject in F major, then the solo episode's figuration.
HPSI_SUBJECT = voice([(14, """
r:.5 F5:.5 A5:.5 G5:.5 D6:1 C6:.5 Bb5:.5 |
A5:.5 G5:.5 A5:.5 F5:.5 E5:.5 F5:.5 G5:.5 C5:.5 |
F5:1
""")])

# ---------------------------------------------------------------- harmony (bar 1-based, beat, symbol)
HARMONY = [
    (1, 0, 'Dm'), (1, 2, 'Gm'), (2, 0, 'Dm'), (2, 2, 'A'),
    (3, 0, 'Dm'), (3, 1, 'Am'), (3, 2, 'Dm'), (4, 0, 'Am'), (4, 2, 'E7'),
    (5, 0, 'Dm'), (5, 2, 'Gm'), (6, 0, 'Dm'), (6, 2, 'A7'),
    (7, 0, 'Dm'), (7, 1, 'Am'), (7, 2, 'Dm'), (8, 0, 'Am'), (8, 2, 'E7'),
    (9, 0, 'A'), (9, 1, 'Dm/F'), (9, 2, 'Gm'), (9, 3, 'Asus4'), (9, 3.5, 'A'),
    (10, 0, 'Dm'), (10, 2, 'Gm'), (11, 0, 'C7'), (11, 2, 'F'), (12, 0, 'Bb'), (12, 2, 'Dm'),
    (13, 0, 'Csus4'), (13, 1, 'C'), (13, 2, 'C7'),
    (14, 0, 'F'), (14, 2, 'Bb'), (15, 0, 'F'), (15, 2, 'C'), (16, 0, 'F'), (16, 2, 'Bb'), (17, 0, 'F'), (17, 2, 'C7'),
    (18, 0, 'F'), (18, 2, 'Bb'), (19, 0, 'Edim/G'), (19, 2, 'A7'), (20, 0, 'Dm'), (20, 2, 'Gm'),
    (21, 0, 'Am7b5/C'), (21, 2, 'D7'),
    (22, 0, 'Gm'), (22, 2, 'Cm'), (23, 0, 'Gm'), (23, 2, 'D7'),
    (24, 0, 'Gm'), (24, 2, 'C#dim7/E'), (25, 0, 'Dm/F'), (25, 2, 'Gm/Bb'),
    (26, 0, 'A'), (26, 0.5, 'Dm/A'), (26, 2, 'Gm/A'), (27, 0, 'Dm/A'), (27, 2, 'C#dim7/A'),
    (28, 0, 'Dm/A'), (28, 2, 'A7'), (29, 0, 'Asus4'), (29, 1, 'A7'),
    (30, 0, 'Dm'), (30, 2, 'Gm'), (31, 0, 'Dm'), (31, 2, 'A7'),
    (32, 0, 'Dm'), (32, 1, 'Dm7/C'), (32, 2, 'Gm/Bb'), (32, 3, 'Edim'),
    (33, 0, 'Dm/A'), (33, 2, 'A7'), (34, 0, 'Dm'), (34, 2, 'Gm/D'), (35, 0, 'Dm'), (35, 2, 'A7'), (36, 0, 'D'),
]


def hbeat(bar, beat):
    return (bar - 1) * BAR + beat


EVENTS = [(hbeat(b, t), s) for b, t, s in HARMONY]


def event_end(i):
    return EVENTS[i + 1][0] if i + 1 < len(EVENTS) else BARS * BAR


def sounding(parts, t):
    return sorted({p for part in parts for (on, d, p) in part if on <= t + 1e-6 < on + d})


# ---------------------------------------------------------------- harpsichord solo figuration (bars 18-21)
def figuration():
    syms = ['F', 'Bb', 'Edim', 'A7', 'Dm', 'Gm', 'Am7b5', 'D7']
    voicings = voice_lead(syms, voices=3, low=62, high=74, avoid_parallels=True)
    notes = []
    t = hbeat(18, 0)
    for k, v in enumerate(voicings):
        v0, v1, v2 = v
        fig = [v0, v1, v2, v0 + 12, v2, v1, v2, v1] if k % 2 == 0 else [v2, v1, v0, v1, v2, v0 + 12, v2, v1]
        for j, p in enumerate(fig):
            notes.append((t + j * .25, .25, int(p)))
        t += 2
    notes.append((hbeat(22, 0), 1.0, midi('G4')))
    return notes


HPSI_SOLO = HPSI_SUBJECT + figuration()

# ---------------------------------------------------------------- continuo: left hand doubles the bass line
def continuo_lh():
    out = []
    for on, d, p in CELLO:
        if hbeat(26, 0) <= on < hbeat(30, 0):
            continue
        q = p - 12 if p - 12 >= midi('E1') else p
        out.append((on, d, q))
    for k in range(16):  # dominant pedal: quarter-note A1 under the cello's repeated eighths
        out.append((hbeat(26, 0) + k, 1.0, midi('A1')))
    return sorted(out)


HPSI_LH = continuo_lh()

VIOLONE_SPANS = [(hbeat(7, 0), hbeat(14, 0)), (hbeat(20, 0), hbeat(37, 0))]


def violone():
    out = []
    for on, d, p in CELLO:
        if not any(a <= on < b for a, b in VIOLONE_SPANS) or hbeat(26, 0) <= on < hbeat(30, 0):
            continue
        q = p - 12 if p - 12 >= midi('E1') else p
        out.append((on, d, q))
    for k in range(16):
        out.append((hbeat(26, 0) + k, 1.0, midi('A1')))
    return sorted(out)


VIOLONE = violone()

# Continuo right hand: chords where it accompanies (not under its own subject or solo episode).
RH_SPANS = [(hbeat(7, 0), hbeat(14, 0)), (hbeat(16, 1), hbeat(18, 0)), (hbeat(22, 0), hbeat(37, 0))]


SPREAD = 0.0625  # beats between the notes of a spread chord (about 50 ms at 76 bpm)


def continuo_rh():
    """One strike per beat inside the accompanying spans.  Strong beats (1, 3) strike the full three-note chord,
    detached; weak beats strike its upper two notes, shorter; in the pedal and the final entry the weak beats break
    the chord in eighths.  Each strike is voiced against every string pitch sounding during it."""
    strings = [VLN1, VLN2, VIOLA, CELLO]
    strikes = []
    for i, (t0, sym) in enumerate(EVENTS):
        t1 = event_end(i)
        for a, b in RH_SPANS:
            lo, hi = max(t0, a), min(t1, b)
            t = lo
            while t < hi - 1e-9:
                d = min(1.0 - (t % 1.0), hi - t)
                strikes.append((t, d, sym))
                t += d
    strikes.sort()
    syms = [s for _, _, s in strikes]
    against = []
    for t, d, _ in strikes:
        span = sorted({p for part in strings for (on, dd, p) in part if on < t + d - 1e-6 and on + dd > t + 1e-6})
        against.append(span)
    voicings = voice_lead(syms, voices=3, low=53, high=69, against=against, avoid_parallels=True)
    out = []
    for (t, d, sym), v in zip(strikes, voicings):
        v = [int(p) for p in v]
        if t >= hbeat(36, 0):  # the final chord, struck once and held
            if t == hbeat(36, 0):
                out += [(t, 4.0, p) for p in v]
            continue
        beat = round(t % BAR, 6)
        strong = beat in (0.0, 2.0)
        broken = hbeat(26, 0) <= t < hbeat(32, 0)
        if strong and d >= 1.0:  # spread low to high, as harpsichordists play a continuo chord
            out += [(t + k * SPREAD, .75 - k * SPREAD, p) for k, p in enumerate(v)]
        elif strong or d < 1.0:
            out += [(t, min(d, .75), p) for p in v]
        elif broken:
            out += [(t, .5, v[1]), (t + .5, .5, v[2])]
        else:
            out += [(t, .5, p) for p in v[1:]]
    return out


HPSI_RH = continuo_rh()

# ---------------------------------------------------------------- dynamics plan (per bar, written velocity)
DYN = {}
for b in range(1, BARS + 1):
    DYN[b] = 78
for b in range(10, 14): DYN[b] = 74
for b in range(14, 18): DYN[b] = 70
for b in range(18, 22): DYN[b] = 68 + (b - 18) * 3
for b in range(22, 26): DYN[b] = 80
for b in range(26, 30): DYN[b] = 84 + (b - 26) * 4
for b in range(30, 34): DYN[b] = 92
DYN[34], DYN[35], DYN[36] = 74, 76, 82


def make_track(tid, name, role, notes, soundfont, bank, program, rng, mixd, perf_extra=None, gate_short=.82):
    tnotes, perf = [], {}
    counts = {}
    for on, d, p in sorted(notes, key=lambda x: (x[0], x[2])):
        bar = int(on // BAR) + 1
        k = counts.get(bar, 0)
        counts[bar] = k + 1
        nid = f'{tid}_b{bar:03d}_n{k:03d}'
        tnotes.append({'id': nid, 'on': round(on, 4), 'duration': round(d, 4), 'pitch': int(p)})
        beat_in_bar = on % BAR
        v = DYN[bar]
        if abs(beat_in_bar) < 1e-6:
            v += 5
        elif abs(beat_in_bar - 2) < 1e-6:
            v += 2
        elif abs(beat_in_bar % 1) > 1e-6:
            v -= 4
        if d >= 2:
            v += 2
        gate = gate_short if d <= .5 else (.9 if d <= 1 else .98)
        perf[nid] = {'velocity': max(30, min(118, int(v))), 'timing_ms': 0, 'gate': gate}
    tr = {'id': tid, 'name': name, 'role': role, 'engine': 'soundfont', 'program': program, 'bank': 0,
          'soundfont': soundfont, 'patch': {'bank': bank, 'program': program}, 'range': list(rng),
          'notes': tnotes, 'performance': {'notes': perf}, 'mix': mixd}
    if perf_extra:
        tr['performance'].update(perf_extra)
    return tr


def mix(level, pan, depth, hp=30, width=None, extra=None):
    m = {'level_dbfs': level, 'level_mode': 'active_rms', 'pan': pan, 'highpass': hp, 'reverb_db': -14,
         'space': 'hall', 'depth_m': depth}
    if width is not None:
        m['width'] = width
    if extra:
        m.update(extra)
    return m


def harmony_list():
    return [{'bar': b, 'beat': t, 'symbol': s} for b, t, s in HARMONY]


def build():
    tracks = [
        make_track('vln1', 'Violin I (solo)', 'melody', VLN1, 'vsco', 0, 40, (55, 91),
                   mix(-20, -.45, 1.5, hp=100, width=.55)),
        make_track('vln2', 'Violin II (solo)', 'countermelody', VLN2, 'iowa_strings', 0, 40, (55, 91),
                   mix(-22, -.18, 1.8, hp=100)),
        make_track('viola', 'Viola (solo)', 'countermelody', VIOLA, 'iowa_strings', 0, 41, (48, 79),
                   mix(-22, .2, 1.8, hp=65)),
        make_track('cello', 'Cello (continuo and subject)', 'bass', CELLO, 'cello_bigcat', 0, 42, (36, 72),
                   mix(-21, .38, 2.0, hp=36)),
        make_track('violone', 'Double bass (violone, 16-foot continuo)', 'bass', VIOLONE, 'iowa_strings', 0, 43,
                   (28, 60), mix(-28, .45, 3.5, hp=25)),
        make_track('hpsi_lh', 'Harpsichord continuo, left hand (Flemish 8\')', 'bass', HPSI_LH, 'vcsl_keys', 1, 6,
                   (28, 86), mix(-26, .05, 2.5, extra={'bus': 'ensemble'}), gate_short=.9),
        make_track('hpsi_rh', 'Harpsichord continuo, right hand (Flemish 8\')', 'harmony', HPSI_RH, 'vcsl_keys', 1,
                   6, (28, 86), mix(-27, -.05, 2.5), gate_short=.9),
        make_track('hpsi_solo', 'Harpsichord obbligato (Flemish 8\'+4\')', 'melody', HPSI_SOLO, 'vcsl_keys',
                   2, 6, (40, 98), mix(-21, 0.0, 2.2), gate_short=.9),
    ]
    project = {
        'schema': 'music-production/v1',
        'title': 'Fughetta in D minor',
        'version': '1.0.r5',
        'brief': ('Baroque-style miniature for harpsichord and strings, about two minutes: a fughetta whose subject '
                  'each voice takes up in turn, an episode travelling to F major, a harpsichord solo episode to '
                  'G minor, a dominant pedal with stretto, and a firm cadence with a Picardy third.'),
        'style': 'orchestral/baroque',
        'clock': {'bars': BARS, 'meter': [4, 4], 'tempo': [[0, TEMPO]], 'tail_seconds': 5,
                  'rubato': {'final_ratio': .6, 'final_beats': 6, 'phrase_ratio': .97, 'phrase_beats': 1, 'q': 2}},
        'sections': [
            {'id': 'exposition', 'start_bar': 0, 'bars': 9,
             'intent': 'Subject in Violin I, answer in Violin II, subject in viola, answer in cello; continuo joins with the bass; cadence in D minor'},
            {'id': 'episode1', 'start_bar': 9, 'bars': 4,
             'intent': 'Descending-fifths sequence with interlocking 7-6 suspensions in the violins; travels to F major'},
            {'id': 'middle_F', 'start_bar': 13, 'bars': 4,
             'intent': 'Harpsichord takes the subject in F major, then the cello; lighter texture'},
            {'id': 'episode2', 'start_bar': 17, 'bars': 4,
             'intent': 'Harpsichord solo figuration on a fifths sequence, strings rejoin with suspensions; to G minor'},
            {'id': 'entry_gm', 'start_bar': 21, 'bars': 4,
             'intent': 'Viola subject in G minor, then a short episode back toward D minor'},
            {'id': 'pedal', 'start_bar': 25, 'bars': 4,
             'intent': 'Dominant pedal; stretto of the subject in the violins; the high point at bar 29'},
            {'id': 'final_entry', 'start_bar': 29, 'bars': 4,
             'intent': 'Subject in the bass (cello with harpsichord), full texture, cadential trill, perfect cadence'},
            {'id': 'coda', 'start_bar': 33, 'bars': 3,
             'intent': 'Tonic pedal with the subject head in viola and Violin II; V7-I to D major'},
        ],
        'harmony': harmony_list(),
        'tracks': tracks,
        'mix': {'chain': 'bus', 'rules': 2, 'dynamics': 'wide', 'target_lufs': -16, 'c80_db': 6},
        'decisions': [
            'Chamber forces: one player per string part (solo violin VSCO, Iowa violin and viola, Big Cat cello) and harpsichord continuo, as in a trio-sonata or chamber-concerto fugue.',
            'Harpsichord registration changes for contrast: Flemish 8\' for continuo, 8\'+4\' for its subject entry and solo episode.',
            'c80_db +6: counterpoint for a small ensemble whose lines must be followed (orchestration.md), between the guide\'s starting sends and a concert hall.',
            'Wide dynamics: no bus compression; the shape comes from texture and the written dynamic plan.',
        ],
    }
    expression.apply(project, {'hpsi_lh': {'feel': 0}}, seed=606, drift='time')
    return project


if __name__ == '__main__':
    p = build()
    out = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else 'song.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(p, f, indent=1)
    print('wrote', out, sum(len(t['notes']) for t in p['tracks']), 'notes')
