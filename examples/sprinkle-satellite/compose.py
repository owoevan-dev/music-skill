#!/usr/bin/env python3
"""Sprinkle Satellite: an original kawaii future bass instrumental, written note by note.

160 BPM with half-time drums (snare on beat 3). A major, lifting a whole step to B major through a pivot chord
(E = V of A = IV of B) for the second build, the second drop and the outro. Bright Surge XT chords that pump under
the kick, a high pluck lead carrying the hook, a small chipmunk-like "vox" patch that sings the verse and answers the
lead in the drops, music box and glockenspiel sparkle, a sampled upright piano in the breakdown, an 808 under the
drops and drum-machine drums with hi-hat rolls.

Run:  python compose.py      (writes song_r<REVISION>.json and song.json next to this script)
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The skill's scripts in this repository (the agent ran a frozen copy of the same 0.3.0 skill).
SKILL_SCRIPTS = next(p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir())
sys.path.insert(0, str(SKILL_SCRIPTS))
from musiclib import expression  # noqa: E402
from musiclib.harmony import parse as parse_chord  # noqa: E402
from musiclib.voicing import voice_lead  # noqa: E402

REVISION = 3
BPM = 160
BPB = 4
SEED = 20261107

# ---------------------------------------------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------------------------------------------
SECTIONS = [
    ('intro', 8, 'Music box states the hook over a low-passed pad that opens; shaker enters at bar 5; no kick or bass'),
    ('verse', 16, 'The vox sings a calmer verse tune; pluck chords, soft sub, kick and rim; hats and glock answers join for the second eight'),
    ('build1', 8, 'Kick and bass out; pluck chords in eighths under a rising high-pass, the hook cell fragmented and accelerating, snare roll doubling in rate, riser; one beat and a half of silence before the drop'),
    ('drop1', 16, 'First high point: pumping supersaw chords, the full hook on the pluck lead, 808, half-time drums; phrase A ends on a half cadence, phrase B on the tonic'),
    ('breakdown', 16, 'Contrast: no drums, piano broken chords and pad from the relative minor, the hook in augmentation on music box; from bar 57 the lead hints at the hook through an opening filter, claps and sub return'),
    ('build2', 8, 'Pivot E (V of A = IV of B) into B major; the build routine again with a faster roll (sixteenth triplets, thirty-seconds)'),
    ('drop2', 16, 'Planned high point: the drop a whole step higher, the vox doubling the lead, pad and off-beat plucks added, sixteenth hats and a full-tempo clap; the melody peaks on F#6, the highest note of the piece'),
    ('outro', 8, 'The groove thins and stops; music box hook and piano close on B add9, which rings out'),
]
START = {}
_cursor = 0
for _name, _bars, _ in SECTIONS:
    START[_name] = _cursor
    _cursor += _bars
TOTAL_BARS = _cursor  # 96 bars = 144 s at 160 BPM

DECISIONS = []


def decide(text):
    DECISIONS.append(text)


# ---------------------------------------------------------------------------------------------------------------
# Pitch and chord helpers
# ---------------------------------------------------------------------------------------------------------------
LETTER = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SHARP_NAME = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def P(name):
    """'C#5' -> 73 (scientific pitch, C4 = 60)."""
    i, acc = 1, 0
    while name[i] in '#b':
        acc += 1 if name[i] == '#' else -1
        i += 1
    return 12 * (int(name[i:]) + 1) + LETTER[name[0]] + acc


def tr_sym(sym, n):
    """Transpose a chord symbol by n semitones, spelled with sharps (A major -> B major here)."""
    def root(s):
        r = s[0]
        if len(s) > 1 and s[1] in '#b':
            r = s[:2]
        return r
    main, _, bass = sym.partition('/')
    r = root(main)
    pc = (LETTER[r[0]] + (1 if r.endswith('#') else -1 if r.endswith('b') else 0) + n) % 12
    out = SHARP_NAME[pc] + main[len(r):]
    if bass:
        b = root(bass)
        bpc = (LETTER[b[0]] + (1 if b.endswith('#') else -1 if b.endswith('b') else 0) + n) % 12
        out += '/' + SHARP_NAME[bpc]
    return out


CHORDS = []  # (absolute beat, symbol)


def chart(bar0, entries, transpose=0):
    for i, entry in enumerate(entries):
        if isinstance(entry, str):
            entry = [(0, entry)]
        for beat, sym in entry:
            CHORDS.append(((bar0 + i) * BPB + beat, tr_sym(sym, transpose) if transpose else sym))


def chord_events():
    return sorted(CHORDS)


def chord_at(beat):
    cur = None
    for s, sym in chord_events():
        if s <= beat + 1e-9:
            cur = sym
        else:
            break
    return cur


def spans(b0, b1):
    """Chord spans (start, end, symbol) inside bars [b0, b1)."""
    evs = chord_events()
    lo, hi = b0 * BPB, b1 * BPB
    out = []
    for i, (s, sym) in enumerate(evs):
        e = evs[i + 1][0] if i + 1 < len(evs) else TOTAL_BARS * BPB
        if e <= lo or s >= hi:
            continue
        out.append((max(s, lo), min(e, hi), sym))
    return out


def root_pc(sym):
    return parse_chord(sym)['root']


def bass_pc(sym):
    return parse_chord(sym)['bass']


def chord_pcs(sym):
    return parse_chord(sym)['pcs']


def in_window(pc, lo, hi):
    """The pitch of pitch class pc inside [lo, hi] (the lowest one there)."""
    for p in range(lo, hi + 1):
        if p % 12 == pc:
            return p
    raise ValueError((pc, lo, hi))


# ---------------------------------------------------------------------------------------------------------------
# Tracks and notes
# ---------------------------------------------------------------------------------------------------------------
TRACKS = {}
ORDER = []
_COUNT = {}


def track(tid, name, role, engine, program=0, **kw):
    t = {'id': tid, 'name': name, 'role': role, 'engine': engine, 'program': program, 'bank': 0,
         'drums': False, 'range': [0, 127], 'notes': [], 'performance': {'notes': {}}, 'mix': {}}
    t.update(kw)
    TRACKS[tid] = t
    ORDER.append(tid)
    return t


def note(tid, on, pitch, dur, vel, gate=1.0, phrase=None, art=None):
    """A note at an absolute beat."""
    t = TRACKS[tid]
    on = round(on, 4)
    bar = int(math.floor(on / BPB + 1e-9))
    k = _COUNT.get((tid, bar), 0)
    _COUNT[(tid, bar)] = k + 1
    nid = f'{tid}_b{bar + 1:03d}_n{k:03d}'
    n = {'id': nid, 'on': on, 'duration': round(dur, 4), 'pitch': int(pitch)}
    if phrase:
        n['phrase'] = phrase
    if art:
        n['articulation'] = art
    t['notes'].append(n)
    t['performance']['notes'][nid] = {'velocity': int(max(1, min(127, round(vel)))), 'timing_ms': 0,
                                      'gate': round(gate, 3)}
    return nid


def nb(tid, bar, beat, pitch, dur, vel, **kw):
    return note(tid, bar * BPB + beat, pitch, dur, vel, **kw)


def sounding(tids, s, e):
    out = []
    for tid in tids:
        for n in TRACKS[tid]['notes']:
            if n['on'] < e - 1e-6 and n['on'] + n['duration'] > s + 1e-6:
                out.append(n['pitch'])
    return out


SIMPLE = {'maj9': 'maj7', 'm9': 'm7', 'add9': '', '6': '', '9': '7'}


def simple(sym):
    """The chord without its added colour tone (9th, 6th): support parts leave the colour to the chords and the tune."""
    q = parse_chord(sym)['quality']
    main, _, bass = sym.partition('/')
    root = main[:len(main) - len(q)] if q else main
    return root + SIMPLE.get(q, q) + ('/' + bass if bass else '')


def voice(b0, b1, voices, low, high, melody=(), others=(), gap=3, keep_root=False, start=None, simplify=False):
    """Voice-lead the chords of bars [b0, b1) under the melody parts, against the other parts already written."""
    sp = spans(b0, b1)
    syms = [simple(x[2]) if simplify else x[2] for x in sp]
    ceil, against = [], []
    for s, e, _ in sp:
        m = sounding(melody, s, e)
        ceil.append(max(low + 9, min(m) - gap) if m else None)
        against.append(m + sounding(others, s, e))
    vs = voice_lead(syms, voices=voices, low=low, high=high, ceilings=ceil, against=against,
                    keep_root=keep_root, start=start)
    return [(s, e, sym, [int(p) for p in v]) for (s, e, sym), v in zip(sp, vs)]


def voice_hits(hits, voices, low, high, melody=(), others=(), gap=2):
    """One voicing per chord hit (on, dur, symbol): the ceiling comes from the melody over the hit's whole chord span,
    the parts to keep minor seconds and ninths away from are those sounding during the hit itself."""
    syms, ceil, against = [], [], []
    all_spans = spans(0, TOTAL_BARS)
    for on, dur, sym in hits:
        s, e = next((a, b) for a, b, _ in all_spans if a - 1e-9 <= on < b - 1e-9)
        m_span = sounding(melody, s, e)
        ceil.append(max(low + 9, min(m_span) - gap) if m_span else None)
        against.append(sounding(melody, on, on + dur) + sounding(others, on, on + dur))
        syms.append(sym)
    vs = voice_lead(syms, voices=voices, low=low, high=high, ceilings=ceil, against=against)
    return [[int(p) for p in v] for v in vs]


def voicing_at(vlist, beat):
    for s, e, sym, v in vlist:
        if s - 1e-9 <= beat < e - 1e-9:
            return v, sym, s, e
    return None, None, None, None


# ---------------------------------------------------------------------------------------------------------------
# Harmony (written in A major; the last three sections are the same functions a whole step up)
# ---------------------------------------------------------------------------------------------------------------
INTRO_CH = ['Dmaj9', 'E6', 'C#m7', 'F#m9', 'Bm9', 'C#m7', 'Dmaj7', [(0, 'Esus4'), (2, 'E')]]
VERSE_CH = ['Aadd9', 'C#m7/G#', 'F#m9', 'Dmaj9', 'Aadd9/C#', 'Bm9', 'Dmaj7', [(0, 'Esus4'), (2, 'E')],
            'Aadd9', 'C#m7/G#', 'F#m9', 'Dmaj9', 'Bm9', 'C#m7', 'Dmaj9', [(0, 'Esus4'), (2, 'E')]]
BUILD_CH = ['Dmaj9', 'E6', 'C#m7', 'F#m9', 'Bm9', 'C#m7', 'Dmaj9', 'E']
DROP_CH = ['Dmaj9', 'E6', 'C#m7', 'F#m9', 'Bm9', 'C#7', [(0, 'F#m7'), (2, 'Fmaj7')], [(0, 'Esus4'), (2, 'E')],
           'Dmaj9', 'E6', 'C#m7', 'F#m7', 'Bm9', 'C#m7', [(0, 'Dmaj7'), (2, 'E')], 'Aadd9']
BREAK_CH = ['F#m9', 'Dmaj9', 'Aadd9/C#', 'E', 'F#m9', 'Dmaj9', 'Bm9', [(0, 'C#7sus4'), (2, 'C#7')],
            'Dmaj9', 'E6', 'C#m7', 'F#m9', 'Bm9', 'C#m7', 'Dmaj7', 'E']
OUTRO_CH = ['Dmaj9', 'E6', 'C#m7', 'F#m9', 'Dmaj9', [(0, 'Esus4'), (2, 'E')], 'Aadd9', 'Aadd9']

chart(START['intro'], INTRO_CH)
chart(START['verse'], VERSE_CH)
chart(START['build1'], BUILD_CH)
chart(START['drop1'], DROP_CH)
chart(START['breakdown'], BREAK_CH)
chart(START['build2'], BUILD_CH[:-1] + [[(0, 'Esus4'), (2, 'E')]], transpose=2)
chart(START['drop2'], DROP_CH, transpose=2)
chart(START['outro'], OUTRO_CH, transpose=2)
decide('Drops open on IV (D, then E in B major), not on the tonic, after a build that ends on V: a deceptive arrival. '
       'Phrase A of each drop closes on a 4-3 suspension over V (half cadence), phrase B on IV-V-I (perfect authentic '
       'cadence, 1 in the melody).')
decide('Colour chords: C#7 (V/vi) and the borrowed bVI (Fmaj7) between F#m7 and E give the drop a chromatic bass '
       'F#-F-E; the breakdown starts on the relative minor F#m9.')
decide('Key lift A -> B at bar 65 through a pivot: the breakdown ends on E (V of A), the build reads the same root as '
       'IV of B; F# major (with A#) confirms the new key.')

# ---------------------------------------------------------------------------------------------------------------
# Melodies: (beat in bar, pitch name, duration) per bar, in A major
# ---------------------------------------------------------------------------------------------------------------
HOOK = [
    # 1 Dmaj9: repeated-note pickup, a leap of a sixth to the major seventh, then a stepwise fall
    [(0.00, 'E5', .25), (0.25, 'E5', .25), (0.50, 'C#6', .75), (1.25, 'B5', .25), (1.50, 'A5', .50),
     (2.00, 'F#5', .50), (2.50, 'A5', .75), (3.25, 'B5', .25), (3.50, 'A5', .50)],
    # 2 E6
    [(0.00, 'G#5', .75), (0.75, 'E5', .75), (1.50, 'B5', 1.00), (3.00, 'C#6', .25), (3.25, 'B5', .25),
     (3.50, 'G#5', .50)],
    # 3 C#m7: the basic idea restated a step lower, its leap narrowed to a fifth
    [(0.00, 'E5', .25), (0.25, 'E5', .25), (0.50, 'B5', .75), (1.25, 'A5', .25), (1.50, 'G#5', .50),
     (2.00, 'E5', .50), (2.50, 'G#5', .75), (3.25, 'A5', .25), (3.50, 'G#5', .50)],
    # 4 F#m9: the answer comes down to the root and breathes
    [(0.00, 'F#5', .75), (0.75, 'C#5', .75), (1.50, 'E5', .50), (2.00, 'F#5', 1.25)],
    # 5 Bm9: continuation, a one-beat cell sequenced upward
    [(0.00, 'A5', .50), (0.50, 'F#5', .25), (0.75, 'A5', .25), (1.00, 'B5', .50), (1.50, 'F#5', .25),
     (1.75, 'B5', .25), (2.00, 'C#6', .50), (2.50, 'B5', .25), (2.75, 'C#6', .25), (3.00, 'D6', .75),
     (3.75, 'C#6', .25)],
    # 6 C#7: down the dominant of vi to its leading tone E#
    [(0.00, 'B5', .75), (0.75, 'G#5', .75), (1.50, 'E#5', .50), (2.00, 'G#5', .50), (2.50, 'B5', .50),
     (3.00, 'C#6', .50), (3.50, 'B5', .50)],
    # 7 F#m7 -> Fmaj7: C natural, the borrowed colour
    [(0.00, 'C#6', .75), (0.75, 'A5', .75), (1.50, 'F#5', .50), (2.00, 'A5', .50), (2.50, 'C6', 1.00),
     (3.50, 'B5', .50)],
    # 8 Esus4 -> E: 4-3 suspension, half cadence
    [(0.00, 'A5', 2.00), (2.00, 'G#5', 1.00)],
]
HOOK_B_TAIL = [
    # 12 F#m9: the answer now runs up instead of resting
    [(0.00, 'F#5', .75), (0.75, 'C#5', .75), (1.50, 'E5', .50), (2.00, 'F#5', .75), (2.75, 'G#5', .25),
     (3.00, 'A5', .50), (3.50, 'B5', .50)],
    # 13 Bm9
    [(0.00, 'C#6', .50), (0.50, 'B5', .25), (0.75, 'C#6', .25), (1.00, 'D6', .75), (1.75, 'C#6', .25),
     (2.00, 'B5', .50), (2.50, 'A5', .50), (3.50, 'F#5', .25), (3.75, 'A5', .25)],
    # 14 C#m7: the drop's peak, E6 on the chord's third
    [(0.00, 'B5', .50), (0.50, 'C#6', .50), (1.00, 'E6', 1.00), (2.00, 'C#6', .50), (2.50, 'B5', .50),
     (3.00, 'G#5', .50), (3.50, 'B5', .50)],
    # 15 Dmaj7 -> E
    [(0.00, 'A5', .75), (0.75, 'F#5', .75), (1.50, 'A5', .50), (2.00, 'G#5', .75), (2.75, 'B5', .25),
     (3.00, 'C#6', .25), (3.25, 'B5', .25), (3.50, 'G#5', .50)],
    # 16 Aadd9: the tonic, held
    [(0.00, 'A5', 2.50)],
]
DROP_MELODY = HOOK + HOOK[:3] + HOOK_B_TAIL
# drop 2 varies bar 13: neighbour figures around D6 instead of the plain run
DROP2_BAR13 = [(0.00, 'C#6', .50), (0.50, 'D6', .25), (0.75, 'C#6', .25), (1.00, 'D6', .75), (1.75, 'E6', .25),
               (2.00, 'D6', .50), (2.50, 'C#6', .50), (3.50, 'F#5', .25), (3.75, 'A5', .25)]

VERSE_MEL = [
    [(0.50, 'C#5', .25), (0.75, 'C#5', .25), (1.00, 'A5', 1.00), (2.00, 'B5', .50), (2.50, 'A5', .50),
     (3.00, 'E5', 1.00)],
    [(0.00, 'G#5', 1.50), (1.50, 'F#5', .50), (2.00, 'E5', 1.50)],
    [(0.50, 'C#5', .25), (0.75, 'C#5', .25), (1.00, 'A5', 1.00), (2.00, 'G#5', .50), (2.50, 'F#5', .50),
     (3.00, 'C#5', 1.00)],
    [(0.00, 'E5', 1.50), (1.50, 'F#5', .50), (2.00, 'A5', 1.50)],
    [(0.50, 'E5', .25), (0.75, 'E5', .25), (1.00, 'C#6', 1.00), (2.00, 'B5', .50), (2.50, 'A5', .50),
     (3.00, 'E5', 1.00)],
    [(0.00, 'F#5', .75), (0.75, 'D5', .75), (1.50, 'F#5', .50), (2.00, 'A5', 1.00), (3.00, 'C#6', .50),
     (3.50, 'B5', .50)],
    [(0.00, 'A5', 1.00), (1.00, 'F#5', .50), (1.50, 'E5', .50), (2.00, 'F#5', 1.50)],
    [(0.00, 'A5', 2.00), (2.00, 'G#5', 1.50)],
    [(0.50, 'C#5', .25), (0.75, 'C#5', .25), (1.00, 'A5', .75), (1.75, 'B5', .25), (2.00, 'C#6', .50),
     (2.50, 'B5', .50), (3.00, 'A5', 1.00)],
    [(0.00, 'G#5', 1.00), (1.00, 'E5', .50), (1.50, 'F#5', .50), (2.00, 'G#5', 1.50)],
    [(0.50, 'C#5', .25), (0.75, 'C#5', .25), (1.00, 'A5', 1.00), (2.00, 'C#6', .50), (2.50, 'B5', .50),
     (3.00, 'A5', 1.00)],
    [(0.00, 'F#5', 1.00), (1.00, 'E5', .50), (1.50, 'F#5', .50), (2.00, 'A5', 1.50)],  # a breath before the D6
    [(0.00, 'D6', 1.00), (1.00, 'C#6', .50), (1.50, 'B5', .50), (2.00, 'A5', .50), (2.50, 'F#5', .50),
     (3.00, 'A5', 1.00)],
    [(0.00, 'G#5', .75), (0.75, 'E5', .75), (1.50, 'G#5', .50), (2.00, 'B5', 1.00), (3.00, 'A5', .50),
     (3.50, 'G#5', .50)],
    [(0.00, 'F#5', 1.00), (1.00, 'E5', 1.00), (2.00, 'A5', 1.50)],
    [(0.00, 'B5', 1.00), (1.00, 'A5', 1.00), (2.00, 'G#5', 1.50)],
]

INTRO_TAIL = [  # music box, bars 5-8 of the intro
    [(0.00, 'D6', 1.00), (1.00, 'C#6', 1.00), (2.00, 'B5', 1.00), (3.00, 'A5', 1.00)],
    [(0.00, 'G#5', 1.50), (1.50, 'B5', .50), (2.00, 'E5', 2.00)],
    [(0.00, 'F#5', 1.00), (1.00, 'A5', 1.00), (2.00, 'C#6', 2.00)],
    [(0.00, 'B5', 2.00), (2.00, 'G#5', 2.00)],
]

BREAK_AUG = [  # music box, breakdown bars 1-8: the hook's first two bars at half speed, then a sequence
    [(0.00, 'E5', .50), (0.50, 'E5', .50), (1.00, 'C#6', 1.50), (2.50, 'B5', .50), (3.00, 'A5', 1.00)],
    [(0.00, 'F#5', 1.00), (1.00, 'A5', 1.50), (2.50, 'B5', .50), (3.00, 'A5', 1.00)],
    [(0.00, 'C#6', 1.50), (1.50, 'A5', 1.50), (3.00, 'E5', 1.00)],
    [(0.00, 'G#5', 1.50), (1.50, 'B5', 2.50)],
    [(0.00, 'E5', .50), (0.50, 'E5', .50), (1.00, 'C#6', 1.50), (2.50, 'B5', .50), (3.00, 'A5', 1.00)],
    [(0.00, 'F#5', 1.00), (1.00, 'A5', 1.50), (2.50, 'C#6', .50), (3.00, 'E6', 1.00)],
    [(0.00, 'D6', 1.00), (1.00, 'C#6', .50), (1.50, 'B5', .50), (2.00, 'D6', 1.00), (3.00, 'C#6', 1.00)],
    [(0.00, 'F#5', 2.00), (2.00, 'E#5', 2.00)],
]
BREAK_LEAD = HOOK[:5] + [
    [(0.00, 'B5', .75), (0.75, 'G#5', .75), (1.50, 'E5', .50), (2.00, 'G#5', .50), (2.50, 'B5', .50),
     (3.00, 'C#6', .50), (3.50, 'B5', .50)],
    [(0.00, 'A5', 1.00), (1.00, 'F#5', 1.00), (2.00, 'C#6', 2.00)],
    [(0.00, 'B5', 2.00), (2.00, 'G#5', 1.00)],
]

OUTRO_MB_TAIL = [  # music box, outro bars 5-8 (written in A, played in B)
    [(0.00, 'F#5', 1.00), (1.00, 'A5', 1.00), (2.00, 'C#6', 2.00)],
    [(0.00, 'A5', 2.00), (2.00, 'G#5', 2.00)],
    [(0.00, 'E5', .25), (0.25, 'E5', .25), (0.50, 'C#6', 1.00), (1.50, 'B5', .50), (2.00, 'A5', 2.00)],
    [],
]


def play(tid, bar0, bars, transpose=0, vel=90, vel_fn=None, gate=0.95, phrase=None):
    """Write per-bar (beat, name, dur) lists; velocity accents downbeats and long notes."""
    for i, bar_notes in enumerate(bars):
        for beat, name, dur in bar_notes:
            v = vel
            if beat == 0:
                v += 5
            elif beat % 1 == 0:
                v += 2
            elif (beat * 4) % 2 == 1:
                v -= 6  # sixteenth off-beats lighter
            if dur >= 1:
                v += 3
            if vel_fn:
                v = vel_fn(i, beat, v)
            nb(tid, bar0 + i, beat, P(name) + transpose, dur, v, gate=gate, phrase=phrase)


# ---------------------------------------------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------------------------------------------
DUCK_HARD = {'by': 'kick', 'keys': [36], 'depth_db': 10, 'attack_ms': 3, 'hold_ms': 20, 'release_ms': 180}

track('lead', 'Bright lead (hook)', 'melody', 'surge', program=80, surge={'preset': 'sharpish'},
      mix={'level_dbfs': -15, 'pan': 0.0, 'highpass': 220, 'reverb_db': -20,
           'delay': {'beats': 0.75, 'feedback': 0.3, 'send_db': -18, 'ping_pong': True, 'highpass': 500,
                     'lowpass': 8000}})
track('vox', 'Vox patch (pickups, drop answers and doubles)', 'countermelody', 'surge', program=85,
      surge={'preset': 'zoozither/vox/munchkin_2', 'fallback': 'supersaw_lead'},
      mix={'level_dbfs': -19, 'pan': 0.0, 'width': 0.5, 'bus': 'lead', 'highpass': 250, 'lowpass': 10000,
           'eq': [[3500, -3]], 'reverb_db': -15,
           'delay': {'beats': 0.75, 'feedback': 0.25, 'send_db': -18, 'ping_pong': True, 'highpass': 500,
                     'lowpass': 7000},
           'duck': {'by': 'kick', 'keys': [36], 'depth_db': 3, 'attack_ms': 3, 'hold_ms': 10, 'release_ms': 120}})
track('vox_lead', 'Vox patch singing the verse', 'melody', 'surge', program=85,
      surge={'preset': 'zoozither/vox/munchkin_2', 'fallback': 'supersaw_lead'},
      mix={'level_dbfs': -14, 'pan': 0.0, 'width': 0.5, 'highpass': 250, 'lowpass': 10000, 'eq': [[3500, -3]],
           'reverb_db': -16,
           'delay': {'beats': 0.75, 'feedback': 0.25, 'send_db': -18, 'ping_pong': True, 'highpass': 500,
                     'lowpass': 7000}})
track('musicbox', 'Music box (intro, breakdown, outro melody)', 'melody', 'surge', program=10,
      surge={'preset': 'music_box'},
      mix={'level_dbfs': -19, 'pan': 0.0, 'highpass': 300, 'reverb_db': -13,
           'delay': {'beats': 0.75, 'feedback': 0.3, 'send_db': -16, 'ping_pong': True, 'highpass': 600,
                     'lowpass': 9000}})
track('chords', 'Future bass chords', 'harmony', 'surge', program=90, surge={'preset': 'uni_saw', 'macros': {'1': 0.35}},
      mix={'level_dbfs': -20, 'pan': 0.0, 'highpass': 110, 'eq': [[450, 2.0], [2200, -2.5]], 'reverb_db': -20,
           'duck': DUCK_HARD})
track('plucks', 'Pluck chords (rhythm)', 'rhythm', 'surge', program=4,
      surge={'preset': 'factory/plucks/nice_pluck_3', 'fallback': 'pluck'},
      mix={'level_dbfs': -21, 'pan': 0.0, 'highpass': 180, 'reverb_db': -22,
           'duck': {'by': 'kick', 'keys': [36], 'depth_db': 6, 'attack_ms': 3, 'hold_ms': 15, 'release_ms': 150},
           'delay': {'beats': 0.5, 'feedback': 0.2, 'send_db': -22, 'ping_pong': True, 'highpass': 500,
                     'lowpass': 7000}})
track('pad', 'Bright pad', 'texture', 'surge', program=88, surge={'preset': 'bright_pad'},
      mix={'level_dbfs': -26, 'pan': 0.0, 'highpass': 200, 'reverb_db': -18,
           'duck': {'by': 'kick', 'keys': [36], 'depth_db': 8, 'attack_ms': 5, 'hold_ms': 20, 'release_ms': 200}})
track('piano', 'Upright piano (breakdown, outro)', 'harmony', 'soundfont', program=0, soundfont='vcsl_keys',
      patch={'bank': 0, 'program': 3},
      mix={'level_dbfs': -21, 'pan': -0.05, 'highpass': 30, 'reverb_db': -14, 'width': 0.7,
           'eq': [[300, -2], [1600, 1.5], [4000, 2]]})
track('glock', 'Glockenspiel sparkle', 'accent', 'soundfont', program=9, soundfont='vsco',
      patch={'bank': 0, 'program': 9},
      mix={'level_dbfs': -28, 'pan': 0.25, 'highpass': 400, 'reverb_db': -12,
           'delay': {'beats': 0.5, 'feedback': 0.25, 'send_db': -18, 'ping_pong': True, 'highpass': 800,
                     'lowpass': 10000}})
track('bass808', '808 bass (drops)', 'bass', 'synth', program=38, synth={'preset': 'bass_808'},
      mix={'level_dbfs': -16, 'pan': 0.0, 'highpass': 25, 'saturate': 0.3,
           'duck': {'by': 'kick', 'keys': [36], 'depth_db': 3, 'attack_ms': 2, 'hold_ms': 15, 'release_ms': 70}})
track('sub', 'Sub bass (verse, breakdown, outro)', 'bass', 'surge', program=38, surge={'preset': 'sub_bass_3'},
      mix={'level_dbfs': -22, 'pan': 0.0, 'highpass': 25,
           'duck': {'by': 'kick', 'keys': [36], 'depth_db': 6, 'attack_ms': 3, 'hold_ms': 15, 'release_ms': 140}})
track('kick', 'Kick', 'drums', 'drum_synth', drums=True, kit={'style': '909', 'decay': 0.8},
      mix={'level_dbfs': -18, 'pan': 0.0, 'highpass': 25, 'reverb_db': None, 'saturate': 0.15})
track('snare', 'Snare and clap (half-time backbeat, rolls)', 'drums', 'drum_synth', drums=True,
      kit={'style': '909', 'decay': 0.9},
      mix={'level_dbfs': -20, 'pan': 0.0, 'highpass': 140, 'reverb_db': -15})
track('hats', 'Hi-hats', 'drums', 'drum_synth', drums=True, kit={'style': '808'},
      mix={'level_dbfs': -30, 'pan': 0.12, 'highpass': 350, 'lowpass': 12000, 'reverb_db': -24})
track('perc', 'Shaker, rim and thin clap', 'drums', 'drum_synth', drums=True, kit={'style': '808'},
      mix={'level_dbfs': -29, 'pan': -0.18, 'highpass': 300, 'lowpass': 12000, 'reverb_db': -20})
track('crash', 'Crash', 'drums', 'drum_synth', drums=True, kit={'style': '909'},
      mix={'level_dbfs': -27, 'pan': 0.0, 'highpass': 300, 'reverb_db': -18})
track('fx_rise', 'Noise riser', 'effect', 'synth', program=122, synth={'preset': 'noise_riser'},
      mix={'level_dbfs': -33, 'pan': 0.0, 'highpass': 300, 'lowpass': 9000, 'reverb_db': -18})
track('fx_rev', 'Reverse cymbal', 'effect', 'synth', program=119, synth={'preset': 'reverse_cymbal'},
      mix={'level_dbfs': -28, 'pan': 0.0, 'highpass': 200, 'lowpass': 10000, 'reverb_db': -18})
track('fx_down', 'Downlifter', 'effect', 'synth', program=122, synth={'preset': 'downlifter'},
      mix={'level_dbfs': -30, 'pan': 0.0, 'highpass': 150, 'reverb_db': -16})
track('fx_hit', 'Impact', 'effect', 'noise', program=119,
      mix={'level_dbfs': -26, 'pan': 0.0, 'highpass': 60, 'reverb_db': -13})

decide('Sounds start from Surge XT patches (pluck lead, vox patch, music box, chords, plucks, pad, sub); the 808 and the '
       'noise transitions stay on built-in presets (glide and sweeps), the kit on drum_synth, piano and glockenspiel '
       'on sampled banks.')

# ---------------------------------------------------------------------------------------------------------------
# Melody parts
# ---------------------------------------------------------------------------------------------------------------
I, V, B1, D1, BR, B2, D2, O = (START[k] for k in
                                ('intro', 'verse', 'build1', 'drop1', 'breakdown', 'build2', 'drop2', 'outro'))

# Intro: the music box states the hook, then a falling answer into the verse
play('musicbox', I, HOOK[:4] + INTRO_TAIL, vel=78, gate=1.0, phrase='intro_hook')
# Breakdown: the hook in augmentation
play('musicbox', BR, BREAK_AUG, vel=80, gate=1.0, phrase='break_aug')
# Outro: the hook in B, then the close on B
play('musicbox', O, HOOK[:4] + OUTRO_MB_TAIL, transpose=2, vel=80, gate=1.0, phrase='outro_hook')
nb('musicbox', O + 7, 0, P('B5'), 4.0, 72, gate=1.0, phrase='outro_hook')  # the last note, rung over the end

# Verse: the vox sings
play('vox_lead', V, VERSE_MEL, vel=86, gate=0.97, phrase='verse')

# Build 1: the hook cell (two repeated notes and the leap) fragmented and accelerating
CELL = {'Dmaj9': ('E5', 'C#6'), 'E6': ('E5', 'B5'), 'C#m7': ('E5', 'B5'), 'F#m9': ('C#5', 'A5'),
        'Bm9': ('F#5', 'D6'), 'E': ('E5', 'B5'), 'Esus4': ('E5', 'B5')}


def build_lead(b0, transpose):
    for i in range(8):
        bar = b0 + i
        sym = BUILD_CH[i]
        low, high = CELL[sym]
        if i < 4:
            starts = [0.0]
        elif i < 6:
            starts = [0.0, 2.0]
        elif i == 6:
            starts = [0.0, 1.0, 2.0, 3.0]
        else:
            starts = [0.0, 1.0]
        for k, s in enumerate(starts):
            v = 70 + i * 3 + k
            nb('lead', bar, s, P(low) + transpose, .25, v - 4, gate=0.9, phrase='build_cells')
            nb('lead', bar, s + .25, P(low) + transpose, .25, v - 6, gate=0.9, phrase='build_cells')
            nb('lead', bar, s + .5, P(high) + transpose, .5 if len(starts) > 2 else .75, v, gate=0.9,
               phrase='build_cells')


build_lead(B1, 0)
build_lead(B2, 2)
# pickups into the drops (vox), after a silence of a beat and a half
for bar, tr in ((B1 + 7, 0), (B2 + 7, 2)):
    for k, (beat, name) in enumerate(((3.25, 'B4'), (3.5, 'C#5'), (3.75, 'D5'))):
        nb('vox', bar, beat, P(name) + tr, .25, 80 + 6 * k, gate=0.9, phrase='pickup')

# Drops
play('lead', D1, DROP_MELODY, vel=96, gate=0.95, phrase='drop1')
d2_mel = DROP_MELODY[:12] + [DROP2_BAR13] + DROP_MELODY[13:]
play('lead', D2, d2_mel, transpose=2, vel=99, gate=0.95, phrase='drop2')

# Breakdown, second half: the lead hints at the hook (through an opening low-pass, below)
play('lead', BR + 8, BREAK_LEAD, vel=74, gate=0.95, phrase='break_hint')

# Vox answers in the lead's gaps in drop 1
VOX_FILLS = {
    3: [(3.25, 'E5', .25), (3.50, 'F#5', .25), (3.75, 'G#5', .25)],
    7: [(3.00, 'E5', .25), (3.25, 'E5', .25), (3.50, 'B5', .50)],
    11: [],
    15: [(2.50, 'E5', .25), (2.75, 'E5', .25), (3.00, 'C#6', .50), (3.50, 'B5', .25), (3.75, 'A5', .25)],
}
for i, fill in VOX_FILLS.items():
    for beat, name, dur in fill:
        nb('vox', D1 + i, beat, P(name), dur, 84, gate=0.9, phrase='drop_answer')
# Drop 2: the vox doubles the lead's longer notes and phrase starts (a chopped double), and keeps the last answer
for i, bar_notes in enumerate(d2_mel):
    for j, (beat, name, dur) in enumerate(bar_notes):
        if dur >= .5 or j == 0:
            nb('vox', D2 + i, beat, P(name) + 2, min(dur, 1.5), 82 + (4 if beat == 0 else 0), gate=0.9,
               phrase='drop2_double')
for beat, name, dur in VOX_FILLS[15]:
    nb('vox', D2 + 15, beat, P(name) + 2, dur, 84, gate=0.9, phrase='drop_answer')
decide('Layers held back for drop 2: the vox doubling, the pad, the off-beat plucks, sixteenth hats and the thin '
       'full-tempo clap; drop 1 keeps the vox to short answers in the lead\'s gaps.')

# ---------------------------------------------------------------------------------------------------------------
# Bass
# ---------------------------------------------------------------------------------------------------------------
BASS_LO, BASS_HI = 29, 40  # F1..E2 for the 808 (tonic A1, then B1)

# drop kick patterns (half time); the 808 follows the kick and the chord changes
KICKS = {
    'a': [0.0, 1.5],
    'b': [0.0, 0.75, 3.0],
    'c': [0.0, 0.75, 2.75],
    'end_a': [0.0, 1.5],
    'end_b': [0.0],
}


def drop_kicks(i):
    if i == 15:
        return KICKS['end_b']
    if i == 7:
        return KICKS['end_a']
    if i % 2 == 0:
        return KICKS['a']
    return KICKS['b'] if i % 4 == 1 else KICKS['c']


def write_808(b0, nbars, kick_fn, vel=100, last_long=True):
    events = []
    for i in range(nbars):
        bar = b0 + i
        pos = set(kick_fn(i))
        for s, e, sym in spans(bar, bar + 1):
            pos.add(s - bar * BPB)
        for p in sorted(pos):
            events.append(bar * BPB + p)
    events.sort()
    for k, on in enumerate(events):
        nxt = events[k + 1] if k + 1 < len(events) else (b0 + nbars) * BPB
        sym = chord_at(on)
        pitch = in_window(root_pc(sym), BASS_LO, BASS_HI)
        dur = max(.25, min(nxt - on - .05, 3.5))
        if k + 1 == len(events) and last_long:
            dur = (b0 + nbars) * BPB - on
        accent = 6 if abs((on / BPB) % 1) < 1e-6 else 0
        note('bass808', on, pitch, dur, vel + accent - (8 if dur < .6 else 0), gate=1.0)


write_808(D1, 16, drop_kicks)
write_808(D2, 16, drop_kicks, vel=104)
SLIDES = []
for b0 in (D1, D2):
    for i in (5, 13):
        nxt = (b0 + i + 1) * BPB
        last = max((n for n in TRACKS['bass808']['notes'] if n['on'] < nxt), key=lambda n: n['on'])
        last['duration'] = round(nxt - last['on'] + .12, 4)
        SLIDES.append(last['id'])
decide('808 slides: the last 808 note of drop bars 6 and 14 overlaps the next downbeat, so the mono built-in 808 '
       'glides into the new root (the reason to keep the built-in preset after hearing it against two Surge 808s).')
# outro: the groove thins over four bars
write_808(O, 4, lambda i: [0.0, 1.5] if i < 3 else [0.0], vel=92)

# sub: verse, breakdown second half, end of the outro


def write_sub(b0, nbars, pattern, vel=90, lo=33, hi=44, use_bass=True):
    for i in range(nbars):
        bar = b0 + i
        for s, e, sym in spans(bar, bar + 1):
            pc = bass_pc(sym) if use_bass else root_pc(sym)
            pitch = in_window(pc, lo, hi)
            rel_s = s - bar * BPB
            for (ps, pd) in pattern(i, rel_s, e - s):
                note('sub', bar * BPB + ps, pitch, pd, vel + (5 if ps == 0 else 0), gate=1.0)


def verse_sub(i, rel_s, length):
    if length >= 4:
        return [(0.0, 2.25), (2.5, 1.25)] if i % 2 == 0 else [(0.0, 1.5), (1.75, .5), (2.5, 1.25)]
    return [(rel_s, length - .1)]


write_sub(V, 16, verse_sub, vel=88)
write_sub(BR + 8, 8, lambda i, rs, ln: [(rs, ln - .1)], vel=82, use_bass=False)
write_sub(O + 4, 4, lambda i, rs, ln: [(rs, ln - .05)] if i < 3 else [(0.0, 4.0)], vel=80, lo=35, hi=46,
          use_bass=False)

# ---------------------------------------------------------------------------------------------------------------
# Drums
# ---------------------------------------------------------------------------------------------------------------
KICK, SNARE, CLAP, RIM, CH, OH, CRASH, SHAKER = 36, 38, 39, 37, 42, 46, 49, 70


def hat_bar(bar, i, base='8', roll=None, vel=72, stop=None):
    step = .5 if base == '8' else .25
    t = 0.0
    end = 4.0 if roll is None else 3.0 if roll in ('16', 'trip') else 3.5
    if stop is not None:
        end = min(end, stop)
    while t < end - 1e-9:
        off = (t % 1) != 0
        v = vel + (8 if off and base == '8' else 0) + (6 if base == '16' and (t * 2) % 1 == 0 else 0)
        if base == '16' and (t * 4) % 2 == 1:
            v -= 10
        nb('hats', bar, t, CH, .1, v)
        t += step
    if roll and (stop is None or stop >= 4):
        if roll == '16':
            pts = [3.0 + .25 * k for k in range(4)]
        elif roll == 'trip':
            pts = [3.0 + k / 6 for k in range(6)]
        else:  # '32'
            pts = [3.5 + .125 * k for k in range(4)]
        for k, p in enumerate(pts):
            nb('hats', bar, p, CH, .08, vel - 10 + k * (24 // len(pts)))


def drop_drums(b0, second=False):
    rolls = ['16', 'trip', '32', 'trip', '16', '32', 'trip', None, '16', 'trip', '32', '16', 'trip', '32', '16', None]
    for i in range(16):
        bar = b0 + i
        for k in drop_kicks(i):
            nb('kick', bar, k, KICK, .5, 112 if k == 0 else 100)
        nb('snare', bar, 2.0, SNARE, .5, 112)
        nb('snare', bar, 2.0, CLAP, .5, 104)
        if i % 4 == 3 and i not in (7, 15):
            nb('snare', bar, 3.75, SNARE, .25, 48)
        if i == 7:
            for k, p in enumerate((3.0, 3.25, 3.5, 3.75)):
                nb('snare', bar, p, SNARE, .25, 70 + 10 * k)
        roll = rolls[i] if i % 2 == 1 else None
        if i == 15:
            hat_bar(bar, i, base='16' if second else '8', vel=70, stop=2.0)
        else:
            hat_bar(bar, i, base='16' if second else '8', roll=roll, vel=70 if second else 72)
            if roll is None and not second and i != 7:
                nb('hats', bar, 3.5, OH, .4, 80)
        if second:
            for p in (1.0, 3.0):
                nb('perc', bar, p, CLAP, .25, 72)
    for b in (b0, b0 + 8):
        nb('crash', b, 0, CRASH, 2.0, 112 if b == b0 else 100)


drop_drums(D1)
drop_drums(D2, second=True)


def build_roll(b0, second=False):
    """Snare roll doubling in rate; claps on beat 3 keep the half-time pulse; silence before the drop."""
    plan = [(1.0, 0, 4), (1.0, 0, 4), (.5, 0, 4), (.5, 0, 4), (.25, 0, 4), (.25, 0, 4), (.25, 0, 4), (.125, 0, 2.5)]
    if second:
        plan = [(1.0, 0, 4), (.5, 0, 4), (.5, 0, 4), (.25, 0, 4), (.25, 0, 4), (1 / 6, 0, 4), (.125, 0, 4),
                (.125, 0, 2.5)]
    total = sum(int(round((e - s) / st)) for st, s, e in plan)
    n = 0
    for i, (step, s, e) in enumerate(plan):
        bar = b0 + i
        t = s
        while t < e - 1e-9:
            v = 40 + 56 * n / max(1, total - 1)
            nb('snare', bar, t, SNARE, min(step, .25), v)
            n += 1
            t += step
        if i < 6:
            nb('snare', bar, 2.0, CLAP, .5, 70 + 3 * i)
    # hats: sixteenths rising, out for the last bar
    for i in range(7):
        bar = b0 + i
        for k in range(16):
            v = 36 + i * 4 + (8 if k % 2 == 1 else 0)
            nb('hats', bar, k * .25, CH, .08, v)


build_roll(B1)
build_roll(B2, second=True)

# Verse drums
for i in range(16):
    bar = V + i
    second = i >= 8
    ks = [0.0, 2.5] if i % 4 != 3 else [0.0, 1.75, 2.5]
    for k in ks:
        nb('kick', bar, k, KICK, .5, (96 if second else 88) + (6 if k == 0 else 0))
    nb('perc', bar, 2.0, RIM, .25, 96)
    if second:
        nb('snare', bar, 2.0, CLAP, .5, 74)
    step = .25 if second else .5
    t = 0.0
    while t < 4 - 1e-9:
        v = 58 + (10 if (t % 1) == .5 else 0) + (4 if second else 0)
        nb('perc', bar, t, SHAKER, .1, v)
        t += step
    if second:
        hat_bar(bar, i, base='8', vel=60, roll=('16' if i == 15 else None))
    if i == 7:
        for k, p in enumerate((3.0, 3.25, 3.5, 3.75)):
            nb('perc', bar, p, RIM, .2, 70 + 8 * k)
nb('crash', V, 0, CRASH, 2.0, 84)
nb('crash', V + 8, 0, CRASH, 2.0, 80)

# Intro shaker from bar 5
for i in range(4, 8):
    for k in range(8):
        nb('perc', I + i, k * .5, SHAKER, .1, 50 + 2 * i + (8 if k % 2 else 0))

# Breakdown second half: shaker, claps from bar 59, kick from bar 61
for i in range(8, 16):
    bar = BR + i
    for k in range(8):
        nb('perc', bar, k * .5, SHAKER, .1, 52 + i + (8 if k % 2 else 0))
    if i >= 10:
        nb('snare', bar, 2.0, CLAP, .5, 70 + 2 * i)
    if i >= 12:
        nb('kick', bar, 0.0, KICK, .5, 84 + 2 * i)
nb('crash', BR, 0, CRASH, 3.0, 96)

# Outro drums: four bars thinning
for i in range(4):
    bar = O + i
    for k in ([0.0, 1.5] if i < 3 else [0.0]):
        nb('kick', bar, k, KICK, .5, 100 - 6 * i)
    nb('snare', bar, 2.0, CLAP, .5, 92 - 6 * i)
    nb('snare', bar, 2.0, SNARE, .5, 96 - 8 * i)
    if i < 3:
        hat_bar(bar, i, base='8', vel=64 - 4 * i)
nb('crash', O, 0, CRASH, 2.0, 100)
nb('crash', O + 6, 0, CRASH, 3.0, 70)

# ---------------------------------------------------------------------------------------------------------------
# Chords: future bass chords in the drops
# ---------------------------------------------------------------------------------------------------------------
DROP_PAT = {
    'a': [(0.00, .50), (0.75, .50), (1.50, .75), (2.50, .50), (3.25, .25), (3.50, .50)],
    'b': [(0.00, .75), (1.00, .25), (1.50, .50), (2.25, .75), (3.00, 1.00)],
}


def drop_chords(b0, vel=96):
    hits = []  # (on, dur, symbol, velocity)
    for i in range(16):
        bar = b0 + i
        if i in (7, 15):
            # held chords that wobble (pitch bend below), restruck at the change
            for s, e, sym in spans(bar, bar + 1):
                hits.append((s, e - s - .05, sym, vel + 4))
            continue
        pat = DROP_PAT['a'] if i % 2 == 0 else DROP_PAT['b']
        for ps, pd in pat:
            on = bar * BPB + ps
            sym = chord_at(on)
            s, e = next((a, b) for a, b, _ in spans(bar, bar + 1) if a - 1e-9 <= on < b - 1e-9)
            hits.append((on, min(pd, e - on - .02), sym, vel + (6 if ps == 0 else 0) - (8 if pd <= .25 else 0)))
    vs = voice_hits([(h[0], h[1], h[2]) for h in hits], 5, 53, 79, melody=['lead'], others=['bass808', 'vox'],
                    gap=2)
    for (on, dur, sym, v), voicing in zip(hits, vs):
        low_root = in_window(root_pc(sym), 48, 59)  # the root doubled an octave or two above the 808, for body
        if low_root not in voicing and all(abs(low_root - q) > 2 for q in voicing):
            voicing = [low_root] + voicing
        for p in voicing:
            note('chords', on, p, dur, v - (6 if p == low_root else 0), gate=1.0 if dur > 1.5 else 0.95)


drop_chords(D1)
drop_chords(D2, vel=100)


def wobble(b_from, b_to, depth=.2, period=.5):
    pts = []
    t = b_from * BPB
    step = period / 4
    k = 0
    while t <= b_to * BPB + 1e-9:
        pts.append([round(t, 4), round([0, depth, 0, -depth][k % 4], 3)])
        t += step
        k += 1
    pts[-1][1] = 0.0
    return pts


BEND = []
for start_bar in (D1 + 7, D1 + 15, D2 + 7, D2 + 15):
    BEND += wobble(start_bar, start_bar + 1)
TRACKS['chords']['performance']['bend'] = BEND
decide('The future-bass wobble: the held chords at the end of each drop phrase bend 20 cents up and down in eighths '
       '(performance.bend on the chord part); the rest of the chords pump in a two-bar syncopated pattern under '
       '10 dB of kick ducking.')

# ---------------------------------------------------------------------------------------------------------------
# Pluck chords: verse rhythm, build eighths, drop-2 off-beats
# ---------------------------------------------------------------------------------------------------------------
VERSE_PAT = {
    'a': [(0.00, .50), (0.75, .25), (1.50, .50), (2.50, .25), (3.00, .50)],
    'b': [(0.00, .50), (1.00, .25), (1.50, .50), (2.25, .25), (2.75, .50), (3.50, .25)],
}


def pluck_section(b0, nbars, pattern_fn, melody, vel=84, low=55, high=79, voices=4):
    vl = voice(b0, b0 + nbars, voices, low, high, melody=melody, others=['sub', 'bass808', 'chords'], gap=3,
               simplify=True)
    for i in range(nbars):
        bar = b0 + i
        for ps, pd in pattern_fn(i):
            on = bar * BPB + ps
            v, sym, s, e = voicing_at(vl, on)
            if v is None:
                continue
            pd = min(pd, e - on - .02)
            for p in v:
                note('plucks', on, p, pd, vel + (5 if ps == 0 else 0) + (i % 8), gate=0.9)
    return vl


pluck_section(V, 16, lambda i: VERSE_PAT['a'] if i % 2 == 0 else VERSE_PAT['b'], ['vox_lead'], vel=72)


def build_pat(i):
    if i < 6:
        return [(k * .5, .4) for k in range(8)]
    if i == 6:
        return [(k * .25, .2) for k in range(16)]
    return [(k * .25, .2) for k in range(8)]  # last bar stops at beat 2


pluck_section(B1, 8, build_pat, ['lead'], vel=62)
pluck_section(B2, 8, build_pat, ['lead'], vel=66)
pluck_section(D2, 16, lambda i: [(p, .25) for p in (0.5, 1.5, 2.5, 3.5)] if i not in (7, 15) else [],
              ['lead'], vel=66, low=62, high=81, voices=3)

# ---------------------------------------------------------------------------------------------------------------
# Pad: sustained, common tones tied across the changes
# ---------------------------------------------------------------------------------------------------------------


def pad_section(b0, b1, vel=70, melody=('musicbox', 'vox_lead', 'vox', 'lead'), low=55, high=76):
    vl = voice(b0, b1, 4, low, high, melody=list(melody), others=['sub', 'bass808', 'piano', 'chords', 'plucks'],
               gap=3, simplify=True)
    held = {}
    for s, e, sym, v in vl:
        nxt = {}
        for p in v:
            if p in held and abs(held[p][0] + held[p][1] - s) < 1e-6:
                on, dur = held[p]
                nxt[p] = (on, dur + (e - s))
            else:
                nxt[p] = (s, e - s)
        for p, (on, dur) in held.items():
            if p not in nxt or nxt[p][0] != on:
                note('pad', on, p, dur, vel, gate=1.0)
        held = nxt
    for p, (on, dur) in held.items():
        note('pad', on, p, dur, vel, gate=1.0)


pad_section(I, B1 + 8, vel=66)
# piano and pad share the breakdown; piano is written first (below), so the pad for the breakdown comes after it

# ---------------------------------------------------------------------------------------------------------------
# Piano: breakdown and outro, broken chords over a left-hand root
# ---------------------------------------------------------------------------------------------------------------


def piano_section(b0, nbars, melody, vel=62, final_bar_hold=False):
    vl = voice(b0, b0 + nbars, 3, 57, 76, melody=melody, others=['sub', 'bass808'], gap=3, keep_root=False)
    cc = []
    for s, e, sym, v in vl:
        r = in_window(bass_pc(sym), 38, 49)
        dur = e - s
        if r - 12 >= 33:
            note('piano', s, r - 12, min(dur, 2.0) - .05, vel + 6, gate=1.0)
        note('piano', s, r, min(dur, 2.0) - .05, vel + 4, gate=1.0)
        if dur >= 4:
            fifth = in_window((root_pc(sym) + 7) % 12, r + 1, r + 12)
            note('piano', s + 2, fifth, 1.9, vel - 2, gate=1.0)
        cc += [[round(max(0, s - .05), 4), 64, 0], [round(s + .05, 4), 64, 100]]
        # right hand: eighth-note broken chord, up then down, with a rest on the downbeat
        order = [0, 1, 2, 1, 2, 1, 0][:]
        t = s + .5
        k = 0
        while t < e - .25:
            p = v[order[k % len(order)]]
            note('piano', t, p, .5, vel - 4 + (6 if (t % 1) == 0 else 0), gate=1.0)
            t += .5
            k += 1
    cc.append([round((b0 + nbars) * BPB - .1, 4), 64, 0])
    TRACKS['piano']['performance'].setdefault('cc', [])
    TRACKS['piano']['performance']['cc'] += cc


piano_section(BR, 16, ['musicbox', 'lead'], vel=60)
piano_section(O + 4, 4, ['musicbox'], vel=58)
TRACKS['piano']['performance']['cc'].sort(key=lambda x: (x[0], x[2]))

pad_section(BR, B2 + 8, vel=70)
pad_section(D2, O + 8, vel=64)

# ---------------------------------------------------------------------------------------------------------------
# Glockenspiel sparkle: answers in the gaps, an arpeggio of the chord's upper tones
# ---------------------------------------------------------------------------------------------------------------


def sparkle(bar, beat, n=4, step=.25, lo=85, hi=100, vel=78, up=True):
    sym = chord_at(bar * BPB + beat)
    pcs = chord_pcs(sym)
    pitches = [p for p in range(lo, hi + 1) if p % 12 in pcs]
    seq = pitches[:n] if up else pitches[::-1][:n]
    for k, p in enumerate(seq):
        nb('glock', bar, beat + k * step, p, step * 1.5, vel - 4 * k if not up else vel - 6 + 3 * k)


# verse, second half: answers in the vox's breaths
for i in (9, 11, 13, 15):
    sparkle(V + i, 3.5 if i != 15 else 3.0, n=2 if i != 15 else 4, lo=81, hi=96, vel=70)
# drop 1: in the lead's gaps
for i, beat in ((1, 2.5), (3, 3.25), (7, 3.0), (9, 2.5), (15, 3.0)):
    sparkle(D1 + i, beat, n=2 if beat == 2.5 else 3 if beat > 3 else 4)
# drop 2: the same gaps, plus a falling sparkle at every second bar's end
for i, beat in ((1, 2.5), (3, 3.25), (7, 3.0), (9, 2.5), (15, 3.0)):
    sparkle(D2 + i, beat, n=2 if beat == 2.5 else 3 if beat > 3 else 4, vel=82)
for i in (4, 10, 12):
    sparkle(D2 + i, 3.5, n=2, up=False, vel=74)
# intro: one sparkle into the verse; the very end
sparkle(I + 7, 3.0, n=4, lo=81, hi=96, vel=66)
nb('glock', O + 7, 0, P('B6'), 2.0, 70)

# ---------------------------------------------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------------------------------------------
REV_BEATS = 2.0 * BPM / 60  # the preset swells over 2 s


def rev_into(bar, vel=96):
    note('fx_rev', bar * BPB - REV_BEATS, 84, REV_BEATS, vel)


for b, v in ((V, 80), (D1, 104), (BR + 8, 76), (D2, 108)):
    rev_into(b, v)
note('fx_rise', (B1 + 2) * BPB, 72, 6 * BPB - .5, 96)   # six bars of riser into drop 1
note('fx_rise', (B2 + 2) * BPB, 72, 6 * BPB - .5, 100)  # and into drop 2
note('fx_rise', (I + 4) * BPB, 72, 4 * BPB - .25, 70)  # a short, soft one into the verse
for b, v in ((BR, 92), (O, 92)):
    note('fx_down', b * BPB, 60, 8.0, v)
for b, v in ((D1, 110), (BR, 80), (D2, 116), (O, 84)):
    note('fx_hit', b * BPB, 36, 4.0, v, art='impact')

# ---------------------------------------------------------------------------------------------------------------
# Mix processes: sweeps through the intro and builds
# ---------------------------------------------------------------------------------------------------------------
TB = TOTAL_BARS * BPB


def hold_levels(points):
    """[(beat, dB), ...] held between points: a step at each point (a point just before it ends the hold)."""
    out = []
    for k, (b, db) in enumerate(points):
        if k:
            out.append([round(b - .02, 4), points[k - 1][1]])
        out.append([b, db])
    out.append([TB, points[-1][1]])
    return out


TRACKS['plucks']['mix']['automation'] = hold_levels([(0, -3.0), (B1 * BPB, -5.0), (D1 * BPB, 0.0), (B2 * BPB, -5.0),
                                                     (D2 * BPB, 0.0)])
decide('Round 3: the plucks patch does not turn velocity into level and the part is levelled as a whole, so the '
       'velocity cuts of round 2 changed nothing; section levels now come from automation: -3 dB under the verse '
       'vox, -5 dB in the builds.')
TRACKS['pad']['mix']['filter_sweep'] = {'type': 'lowpass', 'resonance': .25, 'points': [
    [0, 500], [I * BPB + 28, 3500], [V * BPB - .25, 16000], [V * BPB, 18000], [TB, 18000]]}
TRACKS['plucks']['mix']['filter_sweep'] = {'type': 'highpass', 'resonance': .35, 'points': [
    [0, 30], [B1 * BPB, 30], [(B1 + 7) * BPB + 2, 1400], [(B1 + 8) * BPB, 30],
    [B2 * BPB, 30], [(B2 + 7) * BPB + 2, 1600], [(B2 + 8) * BPB, 30], [TB, 30]]}
TRACKS['lead']['mix']['filter_sweep'] = {'type': 'lowpass', 'resonance': .2, 'points': [
    [0, 18000], [(BR + 8) * BPB - .5, 18000], [(BR + 8) * BPB, 900], [(BR + 15) * BPB, 6000],
    [(BR + 16) * BPB - .25, 12000], [(BR + 16) * BPB, 18000], [TB, 18000]]}
decide('Round 2: the builds measured as loud as the drops (-8.9 vs -8.95 LUFS), carried by the plucks and the '
       'snare roll; the roll now rises from velocity 40 to 96, the build plucks and hats are softer, the riser 3 dB '
       'lower, so the drops arrive louder than what precedes them.')
decide('Build tension (Solberg 2014): kick and bass out, a high-pass on the plucks rising to 1.4-1.6 kHz, a snare roll '
       'doubling in rate, a six-bar noise riser and a reverse cymbal ending on the drop downbeat, one and a half beats '
       'of near silence with a three-note pickup; kick, 808, crash and impact return together on the downbeat.')

# ---------------------------------------------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------------------------------------------
for tid in ORDER:
    t = TRACKS[tid]
    t['notes'].sort(key=lambda n: (n['on'], n['pitch']))
    if t['notes']:
        lo = min(n['pitch'] for n in t['notes'])
        hi = max(n['pitch'] for n in t['notes'])
        t['range'] = [max(0, lo - 2), min(127, hi + 2)]
    if t['engine'] == 'surge' or tid == 'piano':
        t['performance'].setdefault('cc', [])
    t['mix'].setdefault('level_mode', 'active_rms')

harmony = [{'bar': int(b // BPB) + 1, 'beat': round(b % BPB, 4), 'symbol': s} for b, s in chord_events()]

project = {
    'schema': 'music-production/v1',
    'title': 'Sprinkle Satellite',
    'version': f'1.0.r{REVISION}',
    'brief': ('Original kawaii future bass instrumental: bright major-key chords that pump under the kick, a light, '
              'bouncy half-time drop with a high pluck hook, a small vox patch singing the verse, music box and '
              'glockenspiel sparkle. 160 BPM, A major lifting to B major for the last drop. About 2:25.'),
    'clock': {'bars': TOTAL_BARS, 'meter': [4, 4], 'tempo': [[0, BPM]], 'tail_seconds': 6},
    'sections': [{'id': n, 'start_bar': START[n], 'bars': b, 'intent': it} for n, b, it in SECTIONS],
    'tracks': [TRACKS[t] for t in ORDER],
    'harmony': harmony,
    'mix': {'chain': 'bus', 'target_lufs': -10, 'loudness': 'loud', 'mono_below_hz': 120},
    'decisions': DECISIONS,
    'authorship': 'Every note written by compose.py (this folder); performance deviation from musiclib.expression.',
}

overrides = {
    'chords': {'spread': 3, 'lead': 2},
    'plucks': {'spread': 3, 'lead': 2},
    'pad': {'spread': 8},
    'bass808': {'feel': 0, 'timing_sd': 1.5, 'short_sd': .8},
    'sub': {'feel': 2},
    'kick': {'timing_sd': 1.0, 'short_sd': .5},
    'snare': {'timing_sd': 1.5},
    'fx_rise': None, 'fx_rev': None, 'fx_down': None, 'fx_hit': None,
}
expression.apply(project, overrides, seed=SEED)
decide('musiclib.expression adds small timing deviation that keeps to the beat and a slow dynamics drift; the grid stays straight (no swing), kick '
       'and 808 kept tight, chord spread kept to a few ms as synth chords are struck by a sequencer.')
project['decisions'] = DECISIONS

out = HERE / f'song_r{REVISION}.json'
# Published: an output path may be given; without one the script writes beside itself, as the agent ran it.
for path in ((Path(sys.argv[1]),) if len(sys.argv) > 1 else (out, HERE / 'song.json')):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(project, fh, indent=1, ensure_ascii=False)
print('wrote', out, 'notes:', sum(len(t['notes']) for t in project['tracks']))
