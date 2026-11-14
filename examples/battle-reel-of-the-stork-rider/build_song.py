#!/usr/bin/env python3
"""Battle Reel of the Stork-Rider: the composition script.

Writes every note, the performance, the mix, the plan and the piece's words into song.json.
Run:  python build_song.py            (writes song.json next to this file)

A folk band (fiddle, clarinet, strumstick, archtop guitar, folk harp, upright bass, cello, frame drums and hand
percussion) plays a battle that changes sides: the stork-rider's reel (E Dorian, running eighths) against the
hedge-goblins' stamp (E Freygish, 3+3+2), a held breath of melting chords between, a final reel a step higher
(F# Dorian) and one blow at the end.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# line named the folder of a copy of the skill on the machine it ran on).
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import expression  # noqa: E402

TITLE = "Battle Reel of the Stork-Rider"
TEMPO = 168
SEED = 529893823          # the seed studio.py words drew for this piece; also the performance seed
VERSION = "1.0.r3"

# ----------------------------------------------------------------------------------------------------------------
# Form
# ----------------------------------------------------------------------------------------------------------------
SECTIONS = [
    ("intro", 0, 4, "The band strikes in on E minor; the fiddle hovers on B over drum, bass and guitar chops."),
    ("reel_a", 4, 16, "The stork-rider's reel: the fiddle states the A-strain twice (E Dorian), running eighths."),
    ("reel_b", 20, 16, "The tune passes to the clarinet for the B-strain (warm borrowed G, C, D); the fiddle joins a third below."),
    ("stamp_1", 36, 16, "The goblins take the field: E Freygish, 3+3+2 stamps, cello and bass riff; clarinet then fiddle carry the prickly tune."),
    ("reel_a2", 52, 16, "The stork fights back: the strumstick takes the A-strain over harp and fiddle chops, then fiddle and clarinet in thirds."),
    ("breath", 68, 10, "Held breath: drips on the harp, melting chords sliding down by semitones, the clarinet's snail spiral, a heartbeat drum, then a roll."),
    ("stamp_2", 78, 16, "The goblins surge: fiddle and clarinet in octaves on the prickly tune, then the cello takes it low; C#7 swings the key."),
    ("reel_f1", 94, 8, "The final reel a whole step up (F# Dorian): fiddle and clarinet in unison on the A-strain, the stamp's accents in the drums."),
    ("reel_f2", 102, 8, "High point: the clarinet's B-strain peaks on C#6 under the fiddle's E6, the cello sings a counter-line, every part plays."),
    ("reel_f3", 110, 8, "The A-strain one last time with the 3+3+2 stamps taken into the reel."),
    ("coda", 118, 4, "Stop-time stabs, a run up with one beat of silence, and the blow on F#."),
]
TOTAL_BARS = sum(s[2] for s in SECTIONS)
assert TOTAL_BARS == 122
SEC = {s[0]: (s[1], s[2]) for s in SECTIONS}


def bar_beat(bar, beat=0.0):
    return bar * 4.0 + beat


# ----------------------------------------------------------------------------------------------------------------
# Pitch helpers
# ----------------------------------------------------------------------------------------------------------------
PC = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
      'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
MODES = {'dorian': [0, 2, 3, 5, 7, 9, 10], 'aeolian': [0, 2, 3, 5, 7, 8, 10], 'freygish': [0, 1, 4, 5, 7, 8, 10]}


def scale(tonic, mode):
    t = PC[tonic]
    return {(t + i) % 12 for i in MODES[mode]}


def dia(p, steps, pcs):
    """Move p by `steps` scale degrees inside the pitch-class set pcs (p snapped to the nearest scale tone)."""
    cand = [q for q in range(p - 30, p + 31) if q % 12 in pcs]
    i = min(range(len(cand)), key=lambda j: abs(cand[j] - p))
    return cand[i + steps]


def parse_chord(sym):
    root = sym[:2] if len(sym) > 1 and sym[1] in '#b' else sym[:1]
    rest = sym[len(root):]
    r = PC[root]
    if rest.startswith('maj7'):
        tones = [0, 4, 7, 11]
    elif rest.startswith('m7'):
        tones = [0, 3, 7, 10]
    elif rest.startswith('m'):
        tones = [0, 3, 7]
    elif rest.startswith('7'):
        tones = [0, 4, 7, 10]
    elif rest.startswith('5'):
        tones = [0, 7]
    else:
        tones = [0, 4, 7]
    return r, tones


def low_root(sym):
    """The bass's low root: E1 (28) up to D#2 (39)."""
    r, _ = parse_chord(sym)
    return 28 + (r - 4) % 12


GUITAR_VOICING = {
    # r2: the low voicings (G, A, Am, F, B) moved up so the guitar chops sit above the bass and the frame drum
    'Em': [52, 59, 64, 67], 'D': [50, 57, 62, 66], 'A': [52, 57, 61, 64], 'G': [50, 55, 59, 62],
    'C': [48, 55, 60, 64], 'E': [52, 59, 64, 68], 'Dm': [50, 57, 62, 65], 'Am': [52, 57, 60, 64],
    'F': [48, 53, 57, 60], 'C#7': [49, 56, 59, 65], 'F#m': [54, 61, 66, 69], 'B': [54, 59, 63, 66],
}

# ----------------------------------------------------------------------------------------------------------------
# The chord timeline (one entry per bar: a symbol, or a list of (beat, symbol))
# ----------------------------------------------------------------------------------------------------------------
A_CH1 = ['Em7', 'Em', 'D', 'D', 'Em7', 'A', [(0, 'G'), (2, 'A')], 'D']
A_CH2 = ['Em7', 'Em', 'D', 'D', 'Em7', 'A', [(0, 'G'), (2, 'A')], 'Em']
B_CH = ['G', 'D', 'C', 'D', 'G', 'D', [(0, 'C'), (2, 'D')], 'Em']
S_CH = ['E', 'E', 'Dm', 'E', 'Am', 'Dm', [(0, 'F'), (2, 'E')], 'E']
S_CH6 = ['E', 'E', 'Dm', 'E', [(0, 'F'), (2, 'E')], 'E']
UP2 = {'Em': 'F#m', 'Em7': 'F#m7', 'D': 'E', 'A': 'B', 'G': 'A', 'C': 'D', 'Bm': 'C#m'}


def up2(chs):
    return [[(b, UP2[s]) for b, s in c] if isinstance(c, list) else UP2[c] for c in chs]


CHORDS = (['Em'] * 4 + A_CH1 + A_CH2 + B_CH + B_CH + ['E', 'E'] + S_CH + S_CH6 + A_CH1 + A_CH2
          + ['Cmaj7', 'Cmaj7', 'Bm7', 'Bm7', 'Bbmaj7', 'Bbmaj7', 'Am7', 'Am7', 'F', 'F']
          + S_CH + S_CH6 + ['C#7', 'C#7'] + up2(A_CH1) + up2(B_CH) + up2(A_CH2)
          + ['F#m', 'E', [(0, 'D'), (2, 'E')], 'F#m'])
assert len(CHORDS) == TOTAL_BARS, len(CHORDS)
GUITAR_VOICING.update({'Bm7': [47, 54, 57, 62], 'Cmaj7': [48, 55, 59, 64], 'Em7': [52, 59, 62, 67],
                       'F#m7': [54, 61, 64, 69]})


def chords_in_bar(bar):
    c = CHORDS[bar]
    return c if isinstance(c, list) else [(0, c)]


def chord_at(beat):
    bar = int(beat // 4)
    sym = None
    for b, s in chords_in_bar(bar):
        if beat - bar * 4 >= b - 1e-9:
            sym = s
    return sym


def scale_for_bar(bar, beat=0.0):
    """The scale the melody uses in a bar: E Dorian, with C natural where the chord is C (the borrowed 'papaya'
    chord), E Freygish in the stamps, F# Dorian (D natural over D) in the final reel."""
    sym = chord_at(bar_beat(bar, beat))
    st1, n1 = SEC['stamp_1']
    st2, n2 = SEC['stamp_2']
    if st1 <= bar < st1 + n1 or st2 <= bar < st2 + n2 - 2:
        return scale('E', 'freygish')
    if bar >= SEC['reel_f1'][0]:
        return scale('F#', 'aeolian') if sym == 'D' else scale('F#', 'dorian')
    return scale('E', 'aeolian') if sym == 'C' else scale('E', 'dorian')


# ----------------------------------------------------------------------------------------------------------------
# Tracks
# ----------------------------------------------------------------------------------------------------------------
T = {}
ORDER = []


def track(tid, name, role, soundfont, patch, program, rng, mix, perf=None, drums=False):
    t = {"id": tid, "name": name, "role": role, "engine": "soundfont", "program": program, "bank": 0,
         "drums": drums, "range": rng, "soundfont": soundfont, "patch": patch, "notes": [],
         "performance": {"notes": {}}, "mix": mix}
    if perf:
        t["performance"].update(perf)
    T[tid] = t
    ORDER.append(tid)
    return t


LEGATO_FAST = {"mode": "crossfade", "crossfade_ms": 30, "gap_ms": 20, "max_interval": 9}

track("fiddle", "Fiddle (solo violin)", "melody", "vsco", {"bank": 0, "program": 40}, 40, [55, 100],
      {"level_dbfs": -17.5, "level_mode": "active_rms", "pan": -0.12, "width": 0.6, "highpass": 95,
       "reverb_db": -13},
      {"legato": dict(LEGATO_FAST), "bow_change_s": 4})
track("clarinet", "Clarinet (the licorice stick)", "melody", "vsco", {"bank": 0, "program": 71}, 71, [50, 88],
      {"level_dbfs": -18.5, "level_mode": "active_rms", "pan": 0.16, "width": 0.6, "highpass": 90,
       "reverb_db": -13},
      {"legato": dict(LEGATO_FAST), "offset_ms": -20})   # r3: -50 chained every gap after a slur into a slur
track("fiddle_sp", "Fiddle chops (spiccato double stops)", "rhythm", "vsco", {"bank": 1, "program": 40}, 40,
      [55, 96], {"level_dbfs": -27, "level_mode": "active_rms", "pan": -0.32, "width": 0.6, "highpass": 120,
                 "reverb_db": -15},
      {"offset_ms": -30})
track("strumstick", "Strumstick (plucked folk strings)", "countermelody", "vcsl_world", {"bank": 0, "program": 25},
      25, [48, 83],
      {"level_dbfs": -23, "level_mode": "active_rms", "pan": 0.36, "width": 0.7, "highpass": 70, "reverb_db": -15,
       "automation": [[0, 0], [206, 0], [208, 4], [238, 4], [240, 0]]})
track("guitar", "Archtop guitar chops", "rhythm", "guitar_shiny", {"bank": 0, "program": 25}, 25, [35, 86],
      {"level_dbfs": -25, "level_mode": "active_rms", "pan": -0.42, "highpass": 90, "eq": [[260, -1.5]],
       "reverb_db": -18})
track("harp", "Folk harp", "harmony", "vcsl_world", {"bank": 0, "program": 46}, 46, [34, 94],
      {"level_dbfs": -25, "level_mode": "active_rms", "pan": 0.46, "highpass": 28, "reverb_db": -13})
track("bass", "Upright bass (pizzicato)", "bass", "bass_sneaky", {"bank": 0, "program": 32}, 32, [22, 50],
      {"level_dbfs": -20, "level_mode": "active_rms", "pan": 0.0, "highpass": 20, "reverb_db": -28})
track("cello", "Cello (sustained)", "countermelody", "cello_bigcat", {"bank": 0, "program": 42}, 42, [36, 84],
      {"level_dbfs": -22, "level_mode": "active_rms", "pan": -0.24, "highpass": 38, "reverb_db": -14,
       "automation": [[0, 0], [342, 0], [344, 3], [367, 3], [369, 0]]},
      {"legato": {"mode": "crossfade", "crossfade_ms": 60, "gap_ms": 30, "max_interval": 9}})
track("cello_st", "Cello staccato (the stamp riff)", "bass", "cello_bigcat", {"bank": 1, "program": 42}, 42,
      [36, 84], {"level_dbfs": -23, "level_mode": "active_rms", "pan": -0.18, "highpass": 32, "reverb_db": -20})
track("bodhran", "Frame drums (bodhran's place)", "drums", "vcsl_world", {"bank": 128, "program": 25}, 0,
      [35, 38], {"level_dbfs": -21, "level_mode": "active_rms", "pan": 0.04, "reverb_db": -18}, drums=True)
track("hand", "Hand percussion (darbuka, claps, shaker, finger cymbals)", "drums", "vcsl_world",
      {"bank": 128, "program": 25}, 0, [39, 81],
      {"level_dbfs": -23, "level_mode": "active_rms", "pan": 0.3, "reverb_db": -16}, drums=True)

_count = {}


def add(tid, on, dur, pitch, vel, gate=1.0, timing=0.0):
    t = T[tid]
    lo, hi = t['range']
    if not lo <= pitch <= hi:
        raise ValueError(f'{tid}: pitch {pitch} at beat {on} outside {lo}-{hi}')
    bar = int(math.floor(on / 4 + 1e-9))
    k = _count.get((tid, bar), 0)
    _count[(tid, bar)] = k + 1
    nid = f"{tid}_b{bar:03d}_n{k:02d}"
    t['notes'].append({"id": nid, "on": round(on, 4), "duration": round(dur, 4), "pitch": int(pitch)})
    t['performance']['notes'][nid] = {"velocity": int(max(1, min(127, round(vel)))), "timing_ms": timing,
                                      "gate": round(max(0.05, min(1.6, gate)), 3)}
    return nid


def hit(tid, on, key, vel, dur=0.25):
    return add(tid, on, dur, key, vel, 1.0)


# ----------------------------------------------------------------------------------------------------------------
# Tunes (each bar a list of (pitch or None, eighths); every bar sums to 8 eighths)
# ----------------------------------------------------------------------------------------------------------------
A = {  # the stork's A-strain, E Dorian: a striding leap, then hovering round B
    1: [(64, 1), (71, 1), (76, 1), (71, 1), (74, 1), (71, 1), (69, 1), (71, 1)],
    2: [(67, 1), (64, 1), (59, 1), (64, 1), (67, 1), (69, 1), (71, 1), (74, 1)],
    3: [(76, 1), (74, 1), (69, 1), (66, 1), (62, 1), (66, 1), (69, 1), (74, 1)],
    4: [(66, 1), (69, 1), (71, 1), (73, 1), (74, 2), (69, 1), (66, 1)],
    5: [(64, 1), (71, 1), (76, 1), (71, 1), (74, 1), (71, 1), (69, 1), (71, 1)],
    6: [(73, 1), (76, 1), (81, 1), (79, 1), (78, 1), (76, 1), (73, 1), (69, 1)],
    7: [(71, 1), (67, 1), (74, 1), (71, 1), (73, 1), (69, 1), (76, 1), (73, 1)],
    '8a': [(74, 1), (76, 1), (78, 1), (74, 1), (69, 1), (66, 1), (62, 1), (66, 1)],
    '8b': [(76, 2), (71, 1), (67, 1), (64, 2), (None, 2)],
}
# second time through: the same strain with turns in it (bars 1, 3, 5) and the fiddle's triplet "treble" in bar 4
A_VAR = dict(A)
A_VAR[1] = [(64, 1), (71, 1), (76, 1), (78, 1), (76, 1), (74, 1), (71, 1), (69, 1)]
A_VAR[5] = [(64, 1), (71, 1), (76, 1), (71, 1), (74, 1), (76, 1), (78, 1), (76, 1)]

B = {  # the B-strain: long notes falling in a sequence of thirds, then the stork's leap back up
    1: [(83, 3), (81, 1), (79, 1), (78, 1), (79, 1), (74, 1)],
    2: [(78, 3), (76, 1), (74, 1), (73, 1), (74, 1), (69, 1)],
    3: [(76, 3), (74, 1), (72, 1), (71, 1), (72, 1), (67, 1)],
    4: [(66, 1), (69, 1), (74, 1), (78, 1), (81, 2), (78, 1), (74, 1)],
    5: [(83, 3), (81, 1), (79, 1), (78, 1), (79, 1), (74, 1)],
    6: [(78, 1), (76, 1), (74, 1), (76, 1), (78, 1), (81, 1), (79, 1), (78, 1)],
    7: [(76, 1), (72, 1), (67, 1), (72, 1), (74, 1), (69, 1), (66, 1), (69, 1)],
    '8a': [(71, 1), (76, 1), (79, 1), (76, 1), (74, 1), (76, 1), (78, 1), (79, 1)],
    '8b': [(71, 1), (74, 1), (76, 1), (71, 1), (76, 2), (64, 2)],
}
S = {  # the goblins' prickly tune, E Freygish (F natural, the augmented second F-G#)
    1: [(76, 2), (77, 1), (80, 3), (77, 1), (76, 1)],
    2: [(77, 1), (76, 1), (74, 1), (72, 1), (71, 2), (68, 2)],
    3: [(69, 1), (74, 1), (77, 1), (81, 3), (77, 1), (74, 1)],
    4: [(76, 1), (77, 1), (76, 1), (74, 1), (76, 4)],
    5: [(81, 2), (80, 1), (81, 1), (83, 1), (84, 1), (83, 1), (81, 1)],
    6: [(77, 2), (76, 1), (77, 1), (80, 1), (81, 1), (80, 1), (77, 1)],
    7: [(84, 2), (81, 1), (77, 1), (80, 2), (77, 1), (76, 1)],
    8: [(76, 6), (None, 2)],
}
S_ANSWER = [  # the clarinet's answers under the fiddle's statement of the tune (stamp_1 bars 11-16)
    [(None, 6), (68, 1), (69, 1)],
    [(71, 3), (69, 1), (68, 1), (65, 1), (64, 2)],
    [(None, 6), (65, 1), (64, 1)],
    [(65, 3), (64, 1), (62, 1), (60, 1), (59, 2)],
    [(69, 2), (72, 2), (71, 2), (68, 2)],
    [(64, 6), (None, 2)],
]
INTRO_FIDDLE = [
    [(71, 8)],
    [(71, 4), (69, 1), (71, 1), (73, 1), (71, 1)],
    [(71, 6), (74, 1), (73, 1)],
    [(71, 2), (69, 1), (71, 1), (73, 1), (71, 1), (67, 1), (66, 1)],
]
T15 = [(68, 1), (73, 1), (77, 1), (80, 1), (83, 2), (80, 1), (77, 1)]
T16 = [(83, 1), (80, 1), (77, 1), (73, 1), (71, 1), (68, 1), (65, 1), (61, 1)]


def strain(d, keys):
    return [d[k] for k in keys]


A_FIRST = strain(A, [1, 2, 3, 4, 5, 6, 7, '8a'])
A_SECOND = strain(A_VAR, [1, 2, 3, 4, 5, 6, 7, '8b'])
B_FIRST = strain(B, [1, 2, 3, 4, 5, 6, 7, '8a'])
B_SECOND = strain(B, [1, 2, 3, 4, 5, 6, 7, '8b'])
S_FULL = strain(S, [1, 2, 3, 4, 5, 6, 7, 8])
S_SIX = strain(S, [1, 2, 3, 4, 7, 8])


def cells_to_events(cells, start_bar, transpose=0):
    ev = []
    for b, cell in enumerate(cells):
        pos = 0
        for p, n8 in cell:
            if p is not None:
                ev.append([bar_beat(start_bar + b, pos * 0.5), n8 * 0.5, p + transpose])
            pos += n8
        if pos != 8:
            raise ValueError(f'bar {start_bar + b}: {pos} eighths')
    return ev


def shift_events(ev, steps=0, octave=0):
    """A diatonic shift (thirds above or below) in the scale of each note's bar, and/or octaves."""
    out = []
    for on, d, p in ev:
        bar = int(on // 4)
        q = dia(p, steps, scale_for_bar(bar, on - bar * 4)) if steps else p
        out.append([on, d, q + 12 * octave])
    return out


def chord_tones_at(on):
    r, tones = parse_chord(chord_at(on))
    return {(r + t) % 12 for t in tones}


def harmony_line(ev, direction):
    """A second voice a third away (direction -1 below, +1 above): on the beats the nearest chord tone 3-9
    semitones away, between them the diatonic third, so the harmony keeps to the chord where it is heard most."""
    out = []
    for on, d, p in ev:
        bar = int(on // 4)
        if abs(on - round(on)) < 1e-6:
            pcs = chord_tones_at(on)
            cands = [p + direction * k for k in range(3, 10) if (p + direction * k) % 12 in pcs]
            q = cands[0] if cands else dia(p, 2 * direction, scale_for_bar(bar, on - bar * 4))
        else:
            q = dia(p, 2 * direction, scale_for_bar(bar, on - bar * 4))
        out.append([on, d, q])
    return out


def breathe(cells, bars):
    """A wind player takes a breath: the last eighth of each listed bar (0-based in the strain) becomes a rest."""
    out = [list(c) for c in cells]
    for b in bars:
        cell = out[b]
        p, n8 = cell[-1]
        if p is None:
            continue
        cell[-1:] = [(None, 1)] if n8 == 1 else [(p, n8 - 1), (None, 1)]
    return out


def metric_accent(on):
    x = on % 4
    if abs(x) < 1e-6:
        return 7
    if abs(x - 2) < 1e-6:
        return 4
    if abs(x - round(x)) < 1e-6:
        return 1
    return -4


def play(tid, ev, vel, style='bow', bar_dyn=None, slur_max=5):
    """Write a melodic line with its articulation: 'bow' slurs an off-beat note into the next across the beat (a
    fiddler's bowing), 'tongue' slurs steps in groups and tongues leaps and beats 1 and 3 (a wind player), 'pluck'
    plucks every note."""
    ids = []
    for i, (on, d, p) in enumerate(ev):
        nxt = ev[i + 1] if i + 1 < len(ev) else None
        touching = nxt is not None and abs(nxt[0] - (on + d)) < 1e-6
        interval = abs(nxt[2] - p) if nxt else 99
        offbeat = abs((on * 2) % 2 - 1) < 1e-6
        if style == 'bow':
            slur = touching and interval <= slur_max and interval > 0 and offbeat and d <= 0.5
        elif style == 'tongue':
            nxt_on_strong = nxt is not None and abs(nxt[0] % 2) < 1e-6
            slur = touching and 0 < interval <= slur_max and not nxt_on_strong
        else:
            slur = False
        if slur:
            gate = 1.04
        elif not touching:
            gate = 0.86
        elif d <= 0.5:
            gate = 0.72 if style == 'tongue' else 0.78    # a tongued eighth leaves a gap the legato will not bridge
        else:
            gate = 0.88
        v = vel + metric_accent(on) + (3 if d >= 1.5 else 0)
        if i > 0 and ids and style != 'pluck':
            prev = ev[i - 1]
            if abs(prev[0] + prev[1] - on) < 1e-6 and T[tid]['performance']['notes'][ids[-1]]['gate'] > 1:
                v -= 4   # the slurred-into note is lighter
        if bar_dyn:
            v += bar_dyn(on)
        ids.append(add(tid, on, d, p, v, gate))
    return ids


# ----------------------------------------------------------------------------------------------------------------
# Accompaniment writers
# ----------------------------------------------------------------------------------------------------------------
GTR_R1 = [(0, 1.0, .45), (1, .78, .4), (1.5, .7, .3), (2, .95, .45), (3, .8, .4), (3.5, .72, .3)]
GTR_R2 = [(0, 1.0, .45), (1, .8, .35), (2, .95, .45), (2.5, .74, .3), (3.5, .8, .35)]
GTR_STAMP = [(0, 1.0, .3), (1.5, .92, .3), (3, .96, .3), (3.5, .7, .2)]


def guitar_bar(bar, vel, pattern, push=False, skip_down=False):
    for pos, f, d in pattern:
        if skip_down and pos == 0:
            continue
        if push and pos == 3.5:
            continue
        sym = chord_at(bar_beat(bar, pos))
        for p in GUITAR_VOICING[sym]:
            add('guitar', bar_beat(bar, pos), d, p, vel * f, 0.9)
    if push:   # the push is a power chord (root, fifth, octave): no third to rub against the tune's pickup
        sym = chord_at(bar_beat(bar + 1, 0))
        r, _ = parse_chord(sym)
        low = min(GUITAR_VOICING[sym])
        root = low - ((low - r) % 12)
        if root < 48:     # r3: kept above the guitar's 90 Hz high-pass
            root += 12
        for p in (root, root + 7, root + 12):
            add('guitar', bar_beat(bar, 3.5), 1.0, p, vel * 0.95, 0.85)


def bass_reel_bar(bar, vel, push=False, skip_down=False, drive=False):
    cs = chords_in_bar(bar)
    nxt = chords_in_bar(bar + 1)[0][1] if bar + 1 < TOTAL_BARS else cs[0][1]
    N = low_root(nxt)
    if len(cs) == 1:
        R = low_root(cs[0][1])
        seq = [(0, R, vel + 6), (1, R + 7, vel - 6), (2, R + 12, vel + 2), (3, R + 7, vel - 4)]
        last = cs[0][1]
    else:
        R1, R2 = low_root(cs[0][1]), low_root(cs[1][1])
        seq = [(0, R1, vel + 6), (1, R1 + 7, vel - 6), (2, R2, vel + 2), (3, R2 + 7, vel - 4)]
        last = cs[1][1]
    sc = scale_for_bar(bar, 3.5)
    steps = [q for q in (N - 2, N + 2, N - 1, N + 1) if 23 <= q <= 50 and q % 12 in sc]
    approach = steps[0] if steps else N + 7
    walk = nxt != last and bar % 2 == 1 and not push      # a step into the next root on the "and" of 4
    for pos, p, v in seq:
        if skip_down and pos == 0:
            continue
        if push and pos == 3:
            add('bass', bar_beat(bar, 3), 0.5, approach, v, 0.9)
            continue
        if walk and pos == 3:
            add('bass', bar_beat(bar, 3), 0.5, p, v, 0.85)
            add('bass', bar_beat(bar, 3.5), 0.5, approach, v - 6, 0.85)
            continue
        if drive and pos in (1, 3):
            add('bass', bar_beat(bar, pos), 0.5, p, v, 0.85)
            add('bass', bar_beat(bar, pos + 0.5), 0.5, p + 12 if p + 12 <= 50 else p, v - 10, 0.8)
            continue
        add('bass', bar_beat(bar, pos), 1.0, p, v, 0.92)
    if push:
        add('bass', bar_beat(bar, 3.5), 1.5, N, vel + 6, 0.95)


def riff_bar(tid, bar, vel, octave):
    """The stamp riff: 3+3+2, the root twice and a turn on the flat second (E-F) or a step."""
    cs = chords_in_bar(bar)
    base = 28 if tid == 'bass' else 40
    dur = 1.0 if tid == 'bass' else 0.45

    def R(sym):
        r, _ = parse_chord(sym)
        p = base + (r - 4) % 12
        if tid == 'cello_st' and p < 36:
            p += 12
        return p + 12 * octave
    if len(cs) == 1:
        sym = cs[0][1]
        r = R(sym)
        turn = r + 1 if sym in ('E',) else (r - 2 if sym == 'C#7' else r + 2)
        # the turn comes last, on the "and" of 4, leaning into the next stamp (and moving against the tune's own
        # turns on beat 4, which a turn on beat 4 doubled in octaves)
        seq = [(0, r, vel + 8, dur * 1.3), (1.5, r, vel, dur * 1.3), (3, r, vel - 4, 0.45), (3.5, turn, vel - 2, 0.45)]
    else:
        f, e = R(cs[0][1]), R(cs[1][1])
        seq = [(0, f, vel + 8, dur * 1.3), (1.5, f, vel - 2, 0.45), (2, e, vel + 4, dur), (3, e, vel - 4, 0.45),
               (3.5, f, vel - 2, 0.45)]
    for pos, p, v, d in seq:
        add(tid, bar_beat(bar, pos), d, p, v, 0.9)


def bracelet(start_bar, nbars, vel, top=76, mid=71, offset=0):
    """The strumstick's ring: a three-eighth cycle (drone, drone, chord tone) running across the bar lines, so it
    comes round to the downbeat only every three bars, like beads on a bracelet."""
    for k in range(nbars * 8):
        on = bar_beat(start_bar, k * 0.5)
        sym = chord_at(on)
        r, tones = parse_chord(sym)
        i = (k + offset) % 3
        if i == 0:
            p = top
        elif i == 1:
            p = mid + 1 if (r + 11) % 12 == mid % 12 else mid     # over C the drone B gives way to C
        else:
            pcs = [(r + t) % 12 for t in tones]
            third = pcs[1]
            p = min((q for q in range(mid - 9, mid) if q % 12 in pcs and q % 12 != r), key=lambda q: abs(q - (mid - 4)),
                    default=mid - 5)
            del third
        v = vel + (8 if i == 0 else 0) + (4 if abs(on % 4) < 1e-6 else 0)
        add('strumstick', on, 0.5, p, v, 0.9)


def harp_broken(bar, vel, up=0):
    cs = chords_in_bar(bar)
    for ci, (b0, sym) in enumerate(cs):
        r, tones = parse_chord(sym)
        root = 52 + (r - 4) % 12 + up
        third = tones[1]
        arp = [root, root + 7, root + 12, root + 12 + third, root + 19, root + 24]
        idx = [0, 1, 2, 3, 4, 3, 2, 1] if len(cs) == 1 else [0, 1, 2, 3]
        for k, j in enumerate(idx):
            on = bar_beat(bar, b0 + k * 0.5)
            add('harp', on, 0.5, arp[j], vel + (6 if k == 0 else 0) - (2 * (k % 2)), 1.0)


def harp_rising(bar, vel):
    cs = chords_in_bar(bar)
    for ci, (b0, sym) in enumerate(cs):
        r, tones = parse_chord(sym)
        root = 52 + (r - 4) % 12
        third = tones[1]
        arp = [root, root + 7, root + 12, root + 12 + third, root + 19, root + 24, root + 24 + third, root + 31]
        n = 8 if len(cs) == 1 else 4
        for k in range(n):
            add('harp', bar_beat(bar, b0 + k * 0.5), 0.5, arp[k], vel + 2 * k, 1.0)


# ----------------------------------------------------------------------------------------------------------------
# Percussion
# ----------------------------------------------------------------------------------------------------------------
LO, LO_M, HI, HI_M = 35, 36, 37, 38     # frame drum large, large muted, small, small muted
DOUM, TEK, KA, KA2 = 44, 45, 46, 47
CLAP, SHAKE, SHAKE_ROLL, FINGER = 39, 70, 72, 80

REEL_A = [(0, LO, 104), (0.5, HI_M, 52), (1, LO_M, 78), (1.5, HI_M, 56), (2, LO, 94), (2.5, HI_M, 54),
          (3, LO_M, 80), (3.5, HI, 66)]
REEL_B = [(0, LO, 106), (0.5, HI_M, 55), (1, LO_M, 74), (1.5, HI, 70), (2, LO, 92), (2.5, HI_M, 56),
          (3, LO_M, 78), (3.5, HI, 72), (3.75, HI_M, 46)]
REEL_C = [(0, LO, 112), (0.5, HI_M, 56), (1, LO_M, 70), (1.5, LO, 100), (2, LO_M, 66), (2.5, HI_M, 58),
          (3, LO, 104), (3.5, HI, 80)]                       # the reel with the stamp's 3+3+2 in its low drum
STAMP = [(0, LO, 120), (0.5, LO_M, 46), (1, LO_M, 54), (1.5, LO, 110), (2, LO_M, 56), (2.5, LO_M, 48),
         (3, LO, 114), (3.5, HI_M, 72)]
FILL4 = [(2, LO, 96), (2.5, HI_M, 62), (2.75, HI_M, 58), (3, HI, 84), (3.25, HI_M, 64), (3.5, HI, 88),
         (3.75, HI_M, 72)]
FILL8 = [(2, LO, 100), (2 + 1 / 3, HI_M, 70), (2 + 2 / 3, HI_M, 76), (3, HI, 86), (3 + 1 / 3, HI_M, 84),
         (3 + 2 / 3, HI, 98)]
STAMP_FILL = [(3, LO, 116), (3.25, HI, 80), (3.5, HI, 92), (3.75, HI, 104)]


def drum_bars(tid, start_bar, nbars, pattern, scale_v=1.0, fills=True, fill_pattern4=FILL4, fill_pattern8=FILL8,
              last_fill=True):
    for b in range(nbars):
        bar = start_bar + b
        pat = pattern
        if fills and b % 8 == 7 and (last_fill or b != nbars - 1):
            pat = [x for x in pattern if x[0] < 2] + fill_pattern8
        elif fills and b % 4 == 3:
            pat = [x for x in pattern if x[0] < 2] + fill_pattern4
        for pos, key, v in pat:
            hit(tid, bar_beat(bar, pos), key, v * scale_v, 0.25)


def shaker_bars(start_bar, nbars, on_v=48, off_v=68):
    for b in range(nbars):
        for k in range(8):
            hit('hand', bar_beat(start_bar + b, k * 0.5), SHAKE, off_v if k % 2 else on_v, 0.25)


def darbuka_reel(start_bar, nbars, v=1.0):
    pat = [(0, DOUM, 92), (1, TEK, 78), (1.5, KA, 54), (2.5, DOUM, 72), (3, TEK, 82), (3.5, KA, 58)]
    for b in range(nbars):
        for pos, key, vel in pat:
            hit('hand', bar_beat(start_bar + b, pos), key, vel * v, 0.25)


def stamp_hand(start_bar, nbars, v=1.0, cymbal=True):
    pat = [(0, DOUM, 112), (1, CLAP, 92), (1.5, DOUM, 100), (2, TEK, 70), (3, DOUM, 106), (3, CLAP, 100),
           (3.5, TEK, 72)]
    for b in range(nbars):
        bar = start_bar + b
        for pos, key, vel in pat:
            hit('hand', bar_beat(bar, pos), key, vel * v, 0.25)
        for k in range(8):
            hit('hand', bar_beat(bar, k * 0.5), SHAKE, (64 if k % 2 else 46) * v, 0.25)
        if cymbal and b % 2 == 1:
            hit('hand', bar_beat(bar, 2.5), FINGER, 96 * v, 1.0)


def roll(tid, start_beat, n16, v0, v1, keys=(HI, HI_M)):
    for k in range(n16):
        v = v0 + (v1 - v0) * k / max(1, n16 - 1)
        hit(tid, start_beat + k * 0.25, keys[k % 2], v, 0.25)


# ================================================================================================================
# The score
# ================================================================================================================
# ---- intro (bars 0-3) -------------------------------------------------------------------------------------------
s0 = SEC['intro'][0]
play('fiddle', cells_to_events(INTRO_FIDDLE, s0), 80, 'bow', bar_dyn=lambda on: (on - s0 * 4) * 0.6)
for b in range(4):
    guitar_bar(s0 + b, 84 + 2 * b, GTR_R1 if b % 2 == 0 else GTR_R2)
    bass_reel_bar(s0 + b, 84 + 2 * b)
drum_bars('bodhran', s0, 4, REEL_A, 0.95, fills=True)

# ---- reel_a (bars 4-19): fiddle A-strain twice ------------------------------------------------------------------
s = SEC['reel_a'][0]
play('fiddle', cells_to_events(breathe(A_FIRST, [3]), s), 86, 'bow')      # a phrase break after bar 4
play('fiddle', cells_to_events(breathe(A_SECOND, [3]), s + 8), 90, 'bow')
for b in range(16):
    bar = s + b
    guitar_bar(bar, 86 if b < 8 else 90, GTR_R1 if b % 2 == 0 else GTR_R2, push=(b in (7, 15)), skip_down=(b == 8))
    bass_reel_bar(bar, 86 if b < 8 else 90, push=(b == 7 or b == 15), skip_down=(b == 8))
drum_bars('bodhran', s, 16, REEL_A, 1.0)
bracelet(s + 8, 8, 62)
shaker_bars(s + 8, 8, 40, 60)

# ---- reel_b (bars 20-35): clarinet B-strain twice; the fiddle joins a third below the second time --------------
s = SEC['reel_b'][0]
evb1 = cells_to_events(breathe(B_FIRST, [3, 6]), s)
evb2 = cells_to_events(B_SECOND, s + 8)
play('clarinet', evb1, 88, 'tongue')
play('clarinet', cells_to_events(breathe(B_SECOND, [3]), s + 8), 92, 'tongue')
play('fiddle', harmony_line(evb2, -1), 80, 'bow')
for b in range(16):
    bar = s + b
    guitar_bar(bar, 88 if b < 8 else 92, GTR_R2 if b % 2 == 0 else GTR_R1, push=(b == 7), skip_down=(b in (0, 8)))
    bass_reel_bar(bar, 88 if b < 8 else 92, push=(b == 7), skip_down=(b == 0 or b == 8))
drum_bars('bodhran', s, 16, REEL_B, 1.0)
bracelet(s, 16, 64, offset=1)
shaker_bars(s, 16, 44, 64)
darbuka_reel(s + 8, 8)

# ---- stamp_1 (bars 36-51): E Freygish, 3+3+2 ----------------------------------------------------------------------
s = SEC['stamp_1'][0]
for b in range(16):
    bar = s + b
    v = 96 if b < 10 else 100
    riff_bar('cello_st', bar, v, 0)
    riff_bar('bass', bar, v + 4, 0)
    if b >= 2:
        guitar_bar(bar, 92, GTR_STAMP)
drum_bars('bodhran', s, 16, STAMP, 1.0, fill_pattern4=STAMP_FILL, fill_pattern8=STAMP_FILL)
stamp_hand(s, 16, 1.0)
play('clarinet', cells_to_events(S_FULL, s + 2), 96, 'tongue')
play('fiddle', cells_to_events(S_SIX, s + 10), 98, 'bow')
play('clarinet', cells_to_events(S_ANSWER, s + 10), 88, 'tongue')
SEKUND = {'E': [68, 76], 'Dm': [65, 74], 'Am': [64, 72], 'F': [65, 72], 'C#7': [65, 71]}
for b in range(2, 10):          # the second fiddle's chops (klezmer's partial chords) while the clarinet leads
    bar = s + b
    for pos, v in ((1, 84), (2.5, 66), (3.5, 74)):
        for p in SEKUND[chord_at(bar_beat(bar, pos))]:
            add('fiddle_sp', bar_beat(bar, pos), 0.4, p, v, 0.8)

# ---- reel_a2 (bars 52-67): strumstick takes the A-strain; then fiddle with clarinet a third below ---------------
s = SEC['reel_a2'][0]
play('strumstick', cells_to_events(A_FIRST, s), 92, 'pluck')
for b in range(8):
    bar = s + b
    harp_broken(bar, 70)
    bass_reel_bar(bar, 82, push=(b == 7))
    CHOP = {'Em': [67, 71], 'Em7': [67, 71], 'D': [66, 69], 'A': [69, 73], 'G': [67, 71]}
    for pos in (0.5, 1.5, 2.5, 3.5):
        for p in CHOP[chord_at(bar_beat(bar, pos))]:
            add('fiddle_sp', bar_beat(bar, pos), 0.4, p, 62 + (6 if pos in (1.5, 3.5) else 0), 0.8)
drum_bars('bodhran', s, 8, REEL_A, 0.84)
shaker_bars(s, 8, 38, 56)
eva = cells_to_events(A_SECOND, s + 8)
play('fiddle', cells_to_events(breathe(A_SECOND, [3]), s + 8), 92, 'bow')
play('clarinet', harmony_line(eva, -1), 86, 'tongue')
for b in range(8, 16):
    bar = s + b
    guitar_bar(bar, 88, GTR_R1 if b % 2 == 0 else GTR_R2)
    bass_reel_bar(bar, 88, skip_down=(b == 8))
drum_bars('bodhran', s + 8, 8, REEL_B, 1.0)
bracelet(s + 8, 8, 60, top=76, mid=71, offset=2)
darbuka_reel(s + 8, 8, 0.95)
shaker_bars(s + 8, 8, 42, 62)

# ---- breath (bars 68-77): drips, melting chords, the snail spiral, a heartbeat, then the roll -----------------------
s = SEC['breath'][0]
B0 = bar_beat(s)
# the clarinet's snail: intervals shrinking 9, 7, 5, 3, 2, 1, 2 toward A3
for k, (p, d) in enumerate([(64, 4), (55, 4), (62, 4), (57, 4), (60, 4), (58, 4), (59, 4), (57, 12)]):
    on = B0 + sum(x[1] for x in [(64, 4), (55, 4), (62, 4), (57, 4), (60, 4), (58, 4), (59, 4), (57, 12)][:k])
    add('clarinet', on, d, p, [66, 62, 66, 62, 67, 64, 68, 70][k], 1.03 if k < 7 else 0.92)   # r2: +12, in front
# the fiddle melts: B5 held (hovering over Cmaj7 and Bm7), Bb5, A5 (r2: softer, behind the clarinet)
for on, d, p, v in ((0, 16, 83, 40), (16, 8, 82, 42), (24, 16, 81, 48)):
    add('fiddle', B0 + on, d, p, v, 1.02 if on < 24 else 0.92)
# the cello's chromatic melt, G3 F#3 F3 E3 F3 (above the low roots of bass and harp)
for on, d, p, v in ((0, 8, 55, 44), (8, 8, 54, 44), (16, 8, 53, 46), (24, 8, 52, 46), (32, 8, 53, 56)):
    add('cello', B0 + on, d, p, v, 1.02 if on < 32 else 0.9)
# bass roots on the changes
for on, p, v in ((0, 36, 66), (8, 35, 64), (16, 34, 64), (24, 33, 66), (32, 29, 72)):
    add('bass', B0 + on, 7.5 if on < 32 else 3.5, p, v, 1.0)
for k in range(8):
    add('bass', B0 + 36 + k * 0.5, 0.5, 29 if k % 2 == 0 else 41, 58 + k * 6, 0.85)
# harp: the cot's low notes on each change, and the drips from the thatch at uneven places
for on, ps, v in ((0, (36, 43), 56), (8, (35, 42), 54), (16, (34, 41), 56), (24, (45, 52), 56)):
    for p in ps:
        add('harp', B0 + on, 4, p, v, 1.0)
DRIPS = [(0.5, 79, 52), (2.75, 88, 44), (4.0, 83, 50), (6.5, 79, 46), (7.25, 76, 42),
         (8.75, 78, 50), (10.5, 86, 44), (13.0, 81, 48), (14.25, 83, 42),
         (16.5, 77, 50), (18.0, 86, 46), (19.75, 89, 44), (22.5, 82, 48), (23.25, 77, 40),
         (24.75, 76, 50), (26.5, 88, 46), (28.0, 79, 48), (30.25, 81, 44)]
for on, p, v in DRIPS:
    add('harp', B0 + on, 1.0, p, v, 1.0)
for k, p in enumerate([53, 57, 60, 65, 69, 72, 77, 81]):     # bar 76: the harp rises through F
    add('harp', B0 + 32 + k * 0.5, 0.5, p, 50 + 4 * k, 1.0)
# heartbeat, then the roll
for b in range(8):
    hit('bodhran', B0 + b * 4, LO_M, 58, 0.25)
    hit('bodhran', B0 + b * 4 + 0.5, LO_M, 42, 0.25)
roll('bodhran', B0 + 32, 32, 30, 112)
hit('hand', B0 + 32, SHAKE_ROLL, 60, 2.0)
hit('hand', B0 + 36, SHAKE_ROLL, 84, 2.0)
# guitar and strumstick wake on F
for p in GUITAR_VOICING['F']:
    add('guitar', B0 + 32, 3.5, p, 62, 1.0)
for k in range(8):
    for p in GUITAR_VOICING['F']:
        add('guitar', B0 + 36 + k * 0.5, 0.3, p, 50 + 7 * k, 0.8)
    add('strumstick', B0 + 36 + k * 0.5, 0.5, 77 if k % 2 == 0 else 72, 46 + 7 * k, 0.9)
# the swell of the held parts over the two F bars (CC11, linear)
for tid in ('fiddle', 'clarinet', 'cello'):
    T[tid]['performance']['cc'] = [[0, 11, 127], [B0 - 0.1, 11, 127], [B0, 11, 104], [B0 + 31.9, 11, 100],
                                   [B0 + 39.9, 11, 127]]
    T[tid]['performance']['cc_mode'] = 'linear'

# ---- stamp_2 (bars 78-93) -----------------------------------------------------------------------------------------
s = SEC['stamp_2'][0]
evs = cells_to_events(S_FULL, s)
play('fiddle', evs, 104, 'bow')
play('clarinet', shift_events(evs, 0, -1), 98, 'tongue')
evc = cells_to_events(S_SIX, s + 8, -12)
play('cello', evc, 100, 'tongue', slur_max=4)
play('clarinet', cells_to_events(S_ANSWER, s + 8, 12), 92, 'tongue')
for b in range(14):
    bar = s + b
    riff_bar('bass', bar, 106, 0)
    if b < 8:
        riff_bar('cello_st', bar, 102, 0)
    guitar_bar(bar, 96, GTR_STAMP)
for b in range(8, 14):
    bar = s + b
    for pos, v in ((1, 86), (2.5, 70), (3, 80), (3.5, 74)):
        for p in SEKUND[chord_at(bar_beat(bar, pos))]:
            add('fiddle_sp', bar_beat(bar, pos), 0.4, p, v, 0.8)
drum_bars('bodhran', s, 14, STAMP, 1.04, fill_pattern4=STAMP_FILL, fill_pattern8=STAMP_FILL)
stamp_hand(s, 14, 1.05)
# the swing to the new key: C#7 for two bars, a climb and a dive
tr = cells_to_events([T15, T16], s + 14)
play('fiddle', tr, 104, 'bow')
play('clarinet', tr, 98, 'tongue')
for b in (14, 15):
    bar = s + b
    riff_bar('bass', bar, 104, 0) if b == 14 else None
    riff_bar('cello_st', bar, 100, 0)
    guitar_bar(bar, 98, GTR_STAMP, push=(b == 15))
add('bass', bar_beat(s + 15, 0), 1.0, 37, 104, 0.9)
add('bass', bar_beat(s + 15, 1), 1.0, 32, 96, 0.9)
add('bass', bar_beat(s + 15, 2), 1.0, 37, 100, 0.9)
add('bass', bar_beat(s + 15, 3), 0.5, 44, 96, 0.9)
add('bass', bar_beat(s + 15, 3.5), 1.5, 30, 110, 0.95)       # the push into F#
drum_bars('bodhran', s + 14, 1, STAMP, 1.06, fills=False)
roll('bodhran', bar_beat(s + 15), 14, 70, 118)
hit('bodhran', bar_beat(s + 15, 3.5), LO, 120)
stamp_hand(s + 14, 1, 1.05, cymbal=False)
hit('hand', bar_beat(s + 15), SHAKE_ROLL, 90, 2.0)
for k, p in enumerate([89, 85, 83, 80, 77, 73, 71, 68, 65, 61, 59, 56]):   # harp glissando down into the new key
    add('harp', bar_beat(s + 15, 1 + k / 4), 0.25, p, 60 + 2 * k, 1.0)

# ---- reel_f1 (bars 94-101): F# Dorian, fiddle and clarinet in unison ---------------------------------------------
s = SEC['reel_f1'][0]
ev1 = cells_to_events(A_FIRST, s, 2)
play('fiddle', cells_to_events(breathe(A_FIRST, [3]), s, 2), 102, 'bow')
play('clarinet', cells_to_events(breathe(A_FIRST, [7])[4:], s + 4, 2), 96, 'tongue')   # joins for the second phrase
play('strumstick', shift_events(ev1, 0, -1), 80, 'pluck')
for b in range(8):
    bar = s + b
    guitar_bar(bar, 96, GTR_R1 if b % 2 == 0 else GTR_R2, skip_down=(b == 0))
    bass_reel_bar(bar, 96, skip_down=(b == 0), drive=(b % 2 == 1))
drum_bars('bodhran', s, 8, REEL_C, 1.0)
darbuka_reel(s, 8, 1.0)
shaker_bars(s, 8, 46, 66)

# ---- reel_f2 (bars 102-109): the high point ----------------------------------------------------------------------
s = SEC['reel_f2'][0]
ev2 = cells_to_events(B_SECOND, s, 2)
play('clarinet', cells_to_events(breathe(B_SECOND, [3]), s, 2), 110, 'tongue')
play('fiddle', harmony_line(ev2, +1), 106, 'bow')
play('strumstick', shift_events(ev2, 0, -1), 84, 'pluck')
CELLO_F2 = [(0, 4, 61), (4, 4, 59), (8, 4, 57), (12, 4, 56), (16, 4, 57), (20, 4, 59), (24, 2, 54), (26, 2, 56),
            (28, 4, 57)]
for on, d, p in CELLO_F2:
    add('cello', bar_beat(s) + on, d, p, 96 + (6 if on in (0, 16) else 0), 1.02 if on < 28 else 0.9)
for b in range(8):
    bar = s + b
    guitar_bar(bar, 100, GTR_R1 if b % 2 == 0 else GTR_R2, push=(b == 7))
    bass_reel_bar(bar, 100, push=(b == 7), drive=True)
    harp_rising(bar, 74)
drum_bars('bodhran', s, 8, REEL_C, 1.06)
darbuka_reel(s, 8, 1.05)
for b in range(8):
    for pos in (1, 3):
        hit('hand', bar_beat(s + b, pos), CLAP, 96)
shaker_bars(s, 8, 50, 72)

# ---- reel_f3 (bars 110-117): the A-strain with the stamps taken in ----------------------------------------------
s = SEC['reel_f3'][0]
ev3 = cells_to_events(A_SECOND, s, 2)
play('fiddle', cells_to_events(breathe(A_SECOND, [3]), s, 2), 106, 'bow')
play('clarinet', cells_to_events(breathe(A_SECOND, [3]), s, 2), 98, 'tongue')
play('strumstick', shift_events(ev3, 0, -1), 82, 'pluck')
for b in range(8):
    bar = s + b
    guitar_bar(bar, 100, GTR_STAMP if b % 2 == 0 else GTR_R1, skip_down=(b == 0))
    bass_reel_bar(bar, 100, skip_down=(b == 0), drive=(b % 2 == 0))
    for pos, v in ((0, 104), (1.5, 96), (3, 100)):
        sym = chord_at(bar_beat(bar, pos))
        r, _ = parse_chord(sym)
        add('cello_st', bar_beat(bar, pos), 0.45, 40 + (r - 4) % 12, v, 0.9)
drum_bars('bodhran', s, 8, REEL_C, 1.08, last_fill=True)
stamp_hand(s, 8, 1.0)

# ---- coda (bars 118-121): stabs, the run, one beat of silence, the blow -------------------------------------------
s = SEC['coda'][0]
STABS = [(0, [78], 'F#m'), (1.5, [81], 'F#m'), (3, [85], 'F#m'), (4, [76], 'E'), (5.5, [80], 'E'), (7, [83], 'E')]
for on, ps, sym in STABS:
    o = bar_beat(s) + on
    for p in ps:
        add('fiddle', o, 0.5, p, 112, 0.7)
        add('clarinet', o, 0.5, p, 106, 0.7)
        add('strumstick', o, 0.5, p - 12, 96, 0.9)
    for p in GUITAR_VOICING[sym]:
        add('guitar', o, 0.4, p, 96, 0.8)     # r3: -12, the guitar stood level with the tune's stabs
    r, _ = parse_chord(sym)
    add('bass', o, 0.9, 28 + (r - 4) % 12, 112, 0.9)
    add('cello_st', o, 0.45, 40 + (r - 4) % 12, 108, 0.9)
    hit('bodhran', o, LO, 120)
    hit('hand', o, DOUM, 116)
    hit('hand', o, CLAP, 104)
RUN = cells_to_events([[(66, 1), (69, 1), (74, 1), (78, 1), (80, 1), (83, 1), (None, 2)]], s + 2)
play('fiddle', RUN, 108, 'bow')
play('clarinet', RUN, 102, 'tongue')
play('strumstick', shift_events(RUN, 0, -1), 92, 'pluck')
for pos, sym in ((0, 'D'), (2, 'E')):
    for p in GUITAR_VOICING[sym]:
        add('guitar', bar_beat(s + 2, pos), 1.4, p, 92, 0.85)
    r, _ = parse_chord(sym)
    add('bass', bar_beat(s + 2, pos), 1.5, {'D': 38, 'E': 40}[sym], 108, 0.9)
roll('bodhran', bar_beat(s + 2), 12, 64, 122)
# the blow: bar 121, beat 0, then nothing
BLOW = bar_beat(s + 3)
for p in (78, 85):
    add('fiddle', BLOW, 1.0, p, 124, 0.8)
add('clarinet', BLOW, 1.0, 78, 120, 0.8)
for p in (66, 73):
    add('strumstick', BLOW, 2.0, p, 116, 1.0)
for p in (54, 61, 66, 73):      # r3: the low F#2 left to bass, cello and harp
    add('guitar', BLOW, 2.0, p, 110, 1.0)
for p in (42, 49, 54, 66):
    add('harp', BLOW, 3.0, p, 110, 1.0)
add('bass', BLOW, 2.0, 30, 124, 1.0)
add('cello_st', BLOW, 1.0, 42, 120, 1.0)
add('cello', BLOW, 1.5, 49, 118, 0.8)
hit('bodhran', BLOW, LO, 127, 1.0)
hit('bodhran', BLOW, HI, 110, 1.0)
hit('hand', BLOW, DOUM, 127, 1.0)
hit('hand', BLOW, CLAP, 118, 0.5)
hit('hand', BLOW, 41, 116, 0.5)

# ---- the bass keeps out of parallel octaves and fifths with the tune in the reels --------------------------------
TUNE_PARTS = ('fiddle', 'clarinet', 'strumstick', 'cello')


def attacks(tid):
    out = {}
    for n in T[tid]['notes']:
        out.setdefault(round(n['on'], 4), []).append(n['pitch'])
    return out


def parallel(a_low, b_low, a_ups, b_ups):
    if a_low == b_low:
        return False
    for x in a_ups:
        for y in b_ups:
            if x == y:
                continue
            ia, ib = (x - a_low) % 12, (y - b_low) % 12
            if ia == ib and ia in (0, 7) and (y - x > 0) == (b_low - a_low > 0):
                return True
    return False


def fix_bass_parallels(spans):
    tune = {tid: attacks(tid) for tid in TUNE_PARTS}
    bass = sorted((n for n in T['bass']['notes'] if any(a * 4 <= n['on'] < b * 4 for a, b in spans)),
                  key=lambda n: n['on'])
    changed = 0

    def clash(prev, cur_pitch, cur_on):
        for tid in TUNE_PARTS:
            ua, ub = tune[tid].get(round(prev['on'], 4)), tune[tid].get(round(cur_on, 4))
            if ua and ub and parallel(prev['pitch'], cur_pitch, ua, ub):
                return True
        return False
    for i in range(1, len(bass)):
        a, b = bass[i - 1], bass[i]
        if b['on'] - a['on'] > 2.01 or not clash(a, b['pitch'], b['on']):
            continue
        pcs = chord_tones_at(b['on'])
        nxt = bass[i + 1] if i + 1 < len(bass) else None
        options = sorted((q for q in range(23, 51) if q % 12 in pcs and q != b['pitch']),
                         key=lambda q: (abs(q - b['pitch']), q))
        for q in options:
            if clash(a, q, b['on']):
                continue
            if nxt is not None and clash({'on': b['on'], 'pitch': q}, nxt['pitch'], nxt['on']):
                continue
            b['pitch'] = q
            changed += 1
            break
    return changed


BASS_FIXED = fix_bass_parallels([(0, 36), (52, 68), (94, 118)])

# ================================================================================================================
# Project
# ================================================================================================================
harmony = []
for bar in range(TOTAL_BARS):
    for b, sym in chords_in_bar(bar):
        harmony.append({"bar": bar + 1, "beat": b, "symbol": sym})

assoc = json.loads((HERE / 'association.json').read_text(encoding='utf-8'))

project = {
    "schema": "music-production/v1",
    "title": TITLE,
    "version": VERSION,
    "brief": ("Battle music for a fantasy story played by a folk band, not an orchestra: fiddle, a wind instrument "
              "(clarinet), plucked strings (strumstick, archtop guitar, folk harp), upright bass and hand drums. "
              "Fast and driving, about three minutes. The fight changes sides more than once: a running reel, a "
              "heavier stamping section and a moment of held breath, the tune passing from instrument to "
              "instrument, ending on a blow. One-shot cue, not a loop; delivered as master, MP3, MIDI and stems."),
    "clock": {"bars": TOTAL_BARS, "meter": [4, 4], "tempo": [[0, TEMPO]], "tail_seconds": 4},
    "style": {"primary": "folk/celtic", "borrow": {"timbre": "folk/klezmer", "harmony": "folk/klezmer"}},
    "sections": [{"id": sid, "start_bar": st, "bars": n, "intent": intent} for sid, st, n, intent in SECTIONS],
    "harmony": harmony,
    "association": {
        "source": assoc["source"], "seed": assoc["seed"], "words": assoc["words"],
        "whole": ("At the edge of a papaya grove, where the marsh meets the village, a stork-rider guards a child "
                  "asleep in a reed cot. Hedge-goblins with prickly backs waddle up out of the mud in stamping "
                  "ranks, bracelets of snail shells rattling on their wrists. The stork hovers and strikes and the "
                  "reel runs; the goblins stamp back in their crooked mode; the fight swings twice. In the hush "
                  "between, rain drips from the thatch, the goblin shaman's licorice-black charm melts in the fire "
                  "and a snail-slow spell coils round the cot, until the village carver steps out and ends it with "
                  "one blow of a chisel."),
        "gives": [
            {"level": "form", "what": "the fight swings: the stork's reel against the goblins' stamp twice, the hush "
             "of the spell between, and one chisel blow as the ending", "where": "all sections; the blow in bar 122"},
            {"level": "harmony", "what": "the stork's bittersweet E Dorian (licorice) with the papaya's warm "
             "borrowed major chords G, C and D in the B-strain; the goblins' prickly E Freygish on the same tonic "
             "(F natural and the augmented second F-G#); the melting chords Cmaj7, Bm7, Bbmaj7, Am7 sliding down "
             "by semitones in the hush", "where": "reel_b bars 21-36 and 103-110; stamp_1, stamp_2; breath bars 69-76"},
            {"level": "melody", "what": "the stork's stride (the A-strain opens with leaps E4-B4-E5) and its "
             "hovering round B4; the snail's spiral, the clarinet's intervals shrinking 9, 7, 5, 3, 2, 1 toward A3",
             "where": "fiddle intro and reel_a; clarinet in breath"},
            {"level": "rhythm", "what": "the goblins' waddle as 3+3+2 stamps (beats 1, 2.5, 4), taken over by the "
             "reel at the end; the drips falling at uneven places; the chisel as the guitar's chopped chords and "
             "the final stroke", "where": "stamp_1, stamp_2, reel_f1-reel_f3, coda; harp in breath"},
            {"level": "sounds", "what": "the clarinet, the 'licorice stick', as the band's wind; the folk harp as "
             "the cot's lullaby in the hush; shaker and finger cymbals as the snail-shell bracelets",
             "where": "clarinet throughout; harp in breath; hand percussion in the stamps"},
        ],
    },
    "plan": {
        "identity": ("A reel that is fought over: the stork's running E Dorian tune and the goblins' 3+3+2 Freygish "
                     "stamp trade the field, the tune handed from fiddle to clarinet to strumstick to cello, until "
                     "the reel, a step higher, swallows the stamp and a single blow ends it."),
        "high_point": {"section": "reel_f2", "means": ("key lifted a whole step to F# Dorian the section before; "
                       "every part sounds; the clarinet's B-strain peaks on C#6 under the fiddle's E6, the highest "
                       "note of the piece; the cello's counter-line enters; claps and darbuka on top of the reel drum")},
        "sections": [
            {"section": "intro", "sounds": ["fiddle", "guitar", "bass", "bodhran"], "leads": "fiddle"},
            {"section": "reel_a", "sounds": ["fiddle", "guitar", "bass", "bodhran", "strumstick", "hand"],
             "leads": "fiddle", "differs": "the running eighths of the A-strain begin"},
            {"section": "reel_b", "leads": "clarinet", "answers": ["fiddle"],
             "differs": "the clarinet enters with the B-strain; the fiddle drops to a harmony a third below"},
            {"section": "stamp_1", "sounds": ["clarinet", "fiddle", "fiddle_sp", "cello_st", "bass", "guitar",
                                              "bodhran", "hand"], "leads": "clarinet",
             "dynamics": "louder",
             "differs": "E Freygish instead of E Dorian; 3+3+2 stamps instead of running eighths; the cello and bass riff in octaves"},
            {"section": "reel_a2", "leads": "strumstick", "dynamics": "softer",
             "differs": "the tune passes to the plucked strumstick over harp and fiddle chops; the reel returns"},
            {"section": "breath", "sounds": ["clarinet", "fiddle", "cello", "harp", "bass", "bodhran",
                                             "guitar", "strumstick", "hand"],
             "leads": "clarinet", "harmony": "slower", "dynamics": "softer",
             "differs": "no running notes: drips, held melting chords, a heartbeat, then a roll"},
            {"section": "stamp_2", "leads": "fiddle", "answers": ["clarinet", "cello"], "dynamics": "louder",
             "harmony": "faster", "differs": "the stamp returns heavier: fiddle and clarinet in octaves, then the cello takes the tune"},
            {"section": "reel_f1", "leads": "fiddle", "differs": "a whole step higher, F# Dorian; the stamp's accents in the reel drum"},
            {"section": "reel_f2", "leads": "clarinet", "register": {"fiddle": "higher"}, "dynamics": "louder",
             "sounds": ["clarinet", "fiddle", "strumstick", "cello", "harp", "guitar", "bass", "bodhran", "hand"],
             "differs": "the high point: every part plays, the peak notes, the cello's counter-line"},
            {"section": "reel_f3", "leads": "fiddle", "differs": "the A-strain one last time with the 3+3+2 stamps in drums and cello"},
            {"section": "coda", "differs": "stop-time stabs, a run, one silent beat and the blow"},
        ],
    },
    "decisions": [
        "style: primary folk/celtic for what the piece runs on, the reel (rhythm), the fiddle tune in AABB strains "
        "(melody) and the frame drum in the bodhran's place. Timbre is borrowed from folk/klezmer because the "
        "brief's wind instrument is a clarinet here (the 'licorice stick' of the piece's words) beside a cello and a "
        "plucked bass, the klezmer band of the map. Harmony is borrowed from folk/klezmer because the Celtic entry "
        "has no source for harmony, and klezmer's accompaniment from bare octaves (the stamp riff of cello and bass) "
        "to a second violin's partial chords (the fiddle_sp chops) is what this band plays.",
        "tempo: the Celtic entry has no source for tempo; 168 BPM is the piece's choice from the brief (fast and "
        "driving): running eighths at 5.6 notes a second, within what the VSCO solo violin (attack about 20 ms) "
        "articulates.",
        "form: the Celtic entry has no source for form; the piece's own, from the brief and the story: reel, stamp, "
        "reel, held breath, stamp, final reel a step up, blow.",
        "rhythm of the stamps: the 3+3+2 grouping is the piece's own choice for the goblins' waddle, written as this "
        "piece's rhythm rather than as a klezmer bulgar (the rhythm axis is governed by the Celtic entry).",
        "mix: no source read for the Celtic mix; bus chain with the rules of version 2, -14 LUFS.",
        "stand-ins: the vcsl_world strumstick for the bouzouki, banjo or mandolin the banks lack; the vcsl_world "
        "frame drums for the bodhran; the vcsl_world folk harp for the Celtic harp (and the klezmer cimbalom's "
        "place); the guitar_shiny archtop (microphone) as the band's rhythm guitar; the bass_sneaky upright for the "
        "contrabass.",
        "key: E Dorian for the reels (the fiddle's open E and B strings ring in the bracelet figure), E Freygish on "
        "the same tonic for the stamps, F# Dorian for the final reel (a whole-step lift into the high point).",
        "vertical: the minor seconds and ninths left are all the stamp's prickle: the tune's F (the Freygish flat "
        "second, each time a neighbour or passing note between E and G# or E and D) over the stamped E of bass and "
        "cello. That rub is what the goblins' mode is made of here. The accidental ones in the reels and the hush "
        "were removed: guitar pushes are power chords, harp drips moved off the held notes, the bracelet plays C "
        "instead of B over the C chord.",
        "outside_chord.melody: two kinds remain, both meant. The strumstick's bracelet rings its drone strings E5 and "
        "B4 over every chord of the reel, as a dulcimer's open drones ring (the ring of the bracelet), and the "
        "goblins' tune leaps the augmented second F-G# (F5 up to G#5, G#5 down to F5), the step that names the "
        "Freygish mode. Where a fiddle or clarinet note outside the chord was an accident it was rewritten: A-strain "
        "bar 4, the B-strain endings, harmony lines taken from chord tones on the beats, Em7 written where the tune "
        "outlines it.",
        "parallels: what remains is meant: doublings (fiddle and clarinet in octaves in stamp_2, the strumstick an "
        "octave under the tune and the clarinet in unison in the final reel, bass and cello in octaves on the C#7 "
        "riff), the bracelet's drone strings crossing the tune's own E and B, and the hush's melt, where cello and "
        "fiddle slide down by semitones in fifths and octaves over the bass (C-G, B-F#, Bb-F, A-E) as one melting "
        "block. 24 bass notes in the reels were moved to other chord tones to leave the tune's octaves.",
    ],
    "authorship": {"composer": "Claude (Opus 5.5), with the music-production skill 0.7.0",
                   "script": "build_song.py"},
    "revision_history": [
        {"version": "1.0.r1", "what": "first full score"},
        {"version": "1.0.r2", "what": "r1 measured the frame drum as the loudest stem and the leads 3-4 dB under the "
         "band in the reels, a very dry mix (C80 +25.7 dB) and half the power in 60-250 Hz: frame drum -3 dB, fiddle "
         "and clarinet +1.5 dB, hand percussion +2 dB, reverb sends +2 to +5 dB, the guitar's low voicings moved up "
         "with a 90 Hz high-pass; in the hush the clarinet's spiral raised and the held fiddle and cello lowered"},
        {"version": "1.0.r3", "what": "r2's stem receipt showed the clarinet slurring 422 of 465 notes: its -50 ms "
         "offset is left out of legato notes, so each gap after a slur fell under the 20 ms legato threshold and the "
         "slurs chained. Offset -20 ms and tongued eighths at gate 0.72 bring back its tonguing. The review asked "
         "about the guitar's 90 Hz high-pass on the blow's F#2, and analyze put the coda guitar level with the tune: "
         "the blow's guitar chord starts on F#3, push chords stay above C3, the coda guitar plays 12 velocity lower"},
    ],
    "tracks": [T[t] for t in ORDER],
    "mix": {"chain": "bus", "rules": 2, "target_lufs": -14},
}

overrides = {
    'guitar': {'strum': 5},
    'harp': {'lead': 0, 'spread': 4},
    'fiddle_sp': {'spread': 3},
}
report = expression.apply(project, overrides, seed=SEED, drift='time')

out = HERE / 'song.json'
out.write_text(json.dumps(project, indent=1, ensure_ascii=False), encoding='utf-8')
n = sum(len(t['notes']) for t in project['tracks'])
print("bass notes moved off parallels:", BASS_FIXED)
print(f'wrote {out} : {TOTAL_BARS} bars, {len(project["tracks"])} tracks, {n} notes')
for tid in ORDER:
    print(f'  {tid:11s} {len(T[tid]["notes"]):5d} notes')
