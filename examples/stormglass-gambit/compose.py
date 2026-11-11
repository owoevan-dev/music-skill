#!/usr/bin/env python3
"""Stormglass Gambit: a looping battle theme for a game, led by Surge XT synthesizers.

This one script writes every note, velocity, gate and mix setting of the piece into song.json
(music-production/v1).  Run:  python compose.py          (writes song.json next to it)

Bars are 1-based here; a position is in quarter-note beats from the bar line.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# line named the folder where the skill was installed on the machine it ran on).
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import blocks, expression, harmony  # noqa: E402
from musiclib.model import validate  # noqa: E402
from musiclib.voicing import voice_lead  # noqa: E402

TITLE = 'Stormglass Gambit'
BPM = 148
BARS = 112
SEED = blocks.seed(TITLE)
REVISION = 'r4'

# --------------------------------------------------------------------------------------------- sounds
# Chosen from the Surge XT catalog with `studio.py sounds --seed <SEED>` and `studio.py audition` (NOTES.md).
SOUNDS = {
    'lead': 'john_valentine/leads/synced_synth_solo_lead',  # a sync lead: 53% of its power above 2 kHz on the hook
    'counter': 'bluelight/brass/horns_2',                   # synth brass, darker than the lead (1.2 kHz centroid)
    'softlead': 'rozzer/leads/delicious_square',            # a square lead: 1.4 kHz centroid on the theme, steady
    'bass': 'factory/basses/stable',                        # mono, dark, steady
    'riff': 'giana_brotherz/leads/mechanic_unison',         # dry mono unison, 0.7 kHz centroid on the riff
    'arp': 'damon_armani/plucks/drunk_pluck',               # between the pad and the lead in brightness
    'stab': 'factory/polysynths/megasynth_2',
    'pad': 'databroth/pads/tape_magic',                     # warm, soft attack, short tail, steady; darker than both leads
    'revcrash': 'damon_armani/drums/reverse_crash',
    'riser': 'damon_armani/drums/reverse_crash',
}

# --------------------------------------------------------------------------------------------- helpers
NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def P(name):
    """'G5' -> 79, 'Bb4' -> 70, 'F#5' -> 78 (C4 = 60)."""
    pc, rest = NOTE[name[0]], name[1:]
    while rest[0] in '#b':
        pc += 1 if rest[0] == '#' else -1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + pc


def beat_of(bar, pos=0.0):
    return (bar - 1) * 4.0 + pos


project = {
    'schema': 'music-production/v1',
    'title': TITLE,
    'version': '1.0.' + REVISION,
    'brief': ('A battle theme for a game, led by synthesizers on Surge XT: high energy, about three minutes, '
              'a seamless loop. The lead is a synthesizer. Heard on repeat: a hook that holds up, a section that '
              'contrasts, and a build back into the top.'),
    'style': {'primary': 'electronic/trance', 'borrow': {'form': 'game/battle'}},
    'clock': {'bars': BARS, 'meter': [4, 4], 'tempo': [[0, BPM]], 'tail_seconds': 5},
    'loop': {'start_bar': 0},
    'sections': [],
    'harmony': [],
    'tracks': [],
    'mix': {'chain': 'bus', 'rules': 2, 'target_lufs': -14, 'mono_below_hz': 120},
}

SECTIONS = [
    ('hook_a', 1, 16, 'The top of the loop: the hook on the lead synth over four-on-the-floor, rolling bass and '
                      'tresillo arpeggio; a 16-bar period, each half a sentence ending on V.'),
    ('riff', 17, 16, 'A drop in register and density: a syncopated G-pedal riff in bass and riff synth with a flat '
                     'second, broken kick; the lead answers from bar 25 with a repeated-note motif and climbs.'),
    ('hook_b', 33, 16, 'The hook returns fuller: a counter-line answers it, then the lead plays it a third higher '
                       'over the counter synth playing the original; the melody reaches Eb6.'),
    ('chase', 49, 8, 'Development, leaner than hook_b (no pad, two stabs a bar): a one-bar idea in rising sequence '
                     'over a stepwise rising bass, the counter synth echoing it, a broad answer and the Neapolitan.'),
    ('climax', 57, 8, 'The high point: the repeated-note motif in rising sequence to F6 (bar 60) in thirds, pad and '
                      'riff synth added, ride and open hats, the Neapolitan for two bars, then a full stop on V.'),
    ('contrast', 65, 24, 'The contrasting section: half-time, no four-on-the-floor, a slow sung theme on a square '
                         'lead over pads in E-flat; its last eight bars state the hook at half speed.'),
    ('build_pulse', 89, 8, 'The build back into the top, first stage: four-on-the-floor returns softly under an '
                           'off-beat bass, the arpeggio plays only the hook\'s 3+3+2 accents, the lead hints the call.'),
    ('build_climb', 97, 8, 'Second stage: the repeated-note motif climbs two bars at a time through iv-VI-VII-bII; '
                           'rolling bass, clap, the riff synth and the arpeggio open their filters.'),
    ('build_pedal', 105, 8, 'Third stage: eight bars of dominant pedal with a cadential six-four, the call\'s head '
                            'once then twice a bar, a snare roll doubling in rate, a rising swell; no kick or bass '
                            'in the last bar, and the pickup D-E-F# into bar 1.'),
]
for sid, first, length, intent in SECTIONS:
    project['sections'].append({'id': sid, 'start_bar': first - 1, 'bars': length, 'intent': intent})

# --------------------------------------------------------------------------------------------- harmony
# One entry per bar (or [(beat, symbol), ...] for a bar with two chords).  G minor; D major as V; Ab as bII.
CHORDS = {}


def set_chords(first_bar, symbols):
    for k, s in enumerate(symbols):
        CHORDS[first_bar + k] = [(0, s)] if isinstance(s, str) else s


set_chords(1, ['Gm', 'Gm', 'Eb', 'F', 'Gm', 'Bb', 'Cm', 'D',
               'Gm', 'Gm', 'Eb', 'F', 'Bb', 'Cm7', 'Ab', 'D7'])
set_chords(17, ['Gm', 'Gm7', 'Ab/G', 'Gm7', 'Gm', 'Gm7', 'Eb', 'D7',
                'Gm', 'Gm7', 'Ab/G', 'Gm7', 'Cm', 'Cm7', [(0, 'Eb'), (2, 'F')], 'D7'])
set_chords(33, ['Gm', 'Gm', 'Eb', 'F', 'Gm', 'Bb', 'Cm', 'D',
                'Gm', 'Gm/F', 'Eb', 'F', 'Bb', 'Cm7', 'Ab', 'D7'])
set_chords(49, ['Cm', 'Dm', 'Eb', 'F', 'Gm', 'Gm', 'Ab', 'D',
                'Cm', 'Dm', 'Eb', 'F', 'Ab', 'Ab', 'D7', 'D7'])
set_chords(65, ['Ebmaj7', 'Ebmaj7', 'Bb/D', 'Bb/D', 'Cm7', 'Cm7', 'F', 'F',
                'Ebmaj7', 'Ebmaj7', 'Bb/D', 'Bb/D', 'Cm7', 'Cm7', 'Dsus4', 'D',
                'Gm', 'Gm', 'Ebmaj7', 'Ebmaj7', 'Cm7', 'Cm7', 'Dsus4', 'D'])
set_chords(89, ['Gm', 'Gm', 'Eb', 'F', 'Gm', 'Gm', 'Eb', 'F',
                'Cm', 'Cm', 'Eb', 'Eb', 'F', 'F', 'Ab', 'Ab',
                'Dsus4', 'D', 'Gm/D', 'D', 'Dsus4', 'Gm/D', 'Dsus4', 'D7'])
assert sorted(CHORDS) == list(range(1, BARS + 1))
for bar in range(1, BARS + 1):
    for beat, sym in CHORDS[bar]:
        project['harmony'].append({'bar': bar, 'beat': beat, 'symbol': sym})


def chord_at(bar, pos=0.0):
    sym = CHORDS[bar][0][1]
    for beat, s in CHORDS[bar]:
        if beat <= pos + 1e-9:
            sym = s
    return sym


def triad(sym):
    """The chord's root, third (or suspended tone) and fifth as pitch classes, in that order."""
    c = harmony.parse(sym)
    return [(c['root'] + i) % 12 for i in harmony.QUALITIES[c['quality']][:3]]


def ladder(sym, low, count=4, tones=None):
    """`count` consecutive chord tones upward from the first one at or above `low`."""
    pcs = set(tones or triad(sym))
    out, p = [], low
    while len(out) < count:
        if p % 12 in pcs:
            out.append(p)
        p += 1
    return out


BASS_ROOT = {7: 31, 8: 32, 9: 33, 10: 34, 0: 36, 2: 38, 3: 39, 5: 41, 6: 30}  # G1 ... F2: 49-87 Hz


def bass_root(sym):
    return BASS_ROOT[harmony.parse(sym)['bass']]


G_MINOR = {7, 9, 10, 0, 2, 3, 5}


def scale_neighbour(pitch, above):
    """The G natural minor scale tone next to `pitch`, above or below it."""
    p = pitch + (1 if above else -1)
    while p % 12 not in G_MINOR:
        p += 1 if above else -1
    return p


# --------------------------------------------------------------------------------------------- tracks
def track(tid, name, role, engine, level, program=80, **kw):
    t = {'id': tid, 'name': name, 'role': role, 'engine': engine, 'program': program, 'bank': 0,
         'drums': engine == 'drum_synth', 'range': [0, 127], 'notes': [],
         'performance': {'notes': {}, 'cc': []},
         'mix': {'level_dbfs': level, 'level_mode': 'active_rms', 'pan': 0, 'reverb_db': None, 'delay_db': None}}
    if engine == 'surge':
        t['surge'] = {'preset': SOUNDS[tid]}
    t.update({k: v for k, v in kw.items() if k != 'mix'})
    t['mix'].update(kw.get('mix', {}))
    project['tracks'].append(t)
    return t


def add(t, bar, pos, dur, pitch, vel, gate=0.95, phrase='', art='normal'):
    step = int(round(pos * 48))
    nid = f"{t['id']}_b{bar:03d}_s{step:03d}_p{pitch}"
    assert nid not in t['performance']['notes'], nid
    t['notes'].append({'id': nid, 'on': round(beat_of(bar, pos), 6), 'duration': dur, 'pitch': int(pitch),
                       'phrase': phrase, 'articulation': art})
    t['performance']['notes'][nid] = {'velocity': int(max(1, min(127, round(vel)))), 'timing_ms': 0,
                                      'gate': round(gate, 3)}


def line(t, bar, text, vel, phrase, gate=0.94):
    """One bar of a single line.  Tokens 'G5:0.75', rests 'r:0.5'; a name may end in ! (accent), ' (short), _ (full
    length) or , (soft)."""
    pos = 0.0
    for tok in text.split():
        name, dur = tok.split(':')
        dur = float(dur)
        flags = ''
        while name[-1] in "!'_,":
            flags, name = flags + name[-1], name[:-1]
        if name != 'r':
            v = vel + (9 if '!' in flags else 0) - (10 if ',' in flags else 0)
            g = 0.5 if "'" in flags else 1.0 if '_' in flags else gate
            add(t, bar, pos, dur, P(name), v, g, phrase)
        pos += dur
    assert abs(pos - 4) < 1e-9, (t['id'], bar, text, pos)


DUCK = {'by': 'drums', 'keys': [36], 'attack_ms': 4, 'hold_ms': 25, 'release_ms': 170}


def duck(depth):
    return dict(DUCK, depth_db=depth)


lead = track('lead', 'Lead synth (the hook)', 'melody', 'surge', -19.0, program=81, mix={
    'pan': 0, 'width': 0.55, 'highpass': 200, 'reverb_db': -14,
    'delay': {'beats': 0.75, 'feedback': 0.28, 'send_db': -19, 'ping_pong': True, 'highpass': 500, 'lowpass': 6500}})
counter = track('counter', 'Counter synth (answers and harmony)', 'countermelody', 'surge', -25.5, program=62, mix={
    'pan': -0.24, 'highpass': 160, 'reverb_db': -15})
softlead = track('softlead', 'Square lead (contrast theme)', 'melody', 'surge', -20.5, program=80, mix={
    'pan': 0, 'width': 0.6, 'highpass': 180, 'reverb_db': -12,
    'delay': {'beats': 1.5, 'feedback': 0.3, 'send_db': -20, 'ping_pong': True, 'highpass': 400, 'lowpass': 5000}})
stab = track('stab', 'Chord stabs', 'harmony', 'surge', -25.0, program=90, mix={
    'pan': -0.2, 'highpass': 230, 'reverb_db': -18, 'duck': duck(4)})
pad = track('pad', 'Warm pad', 'texture', 'surge', -28.5, program=89, mix={
    'pan': 0.05, 'highpass': 170, 'reverb_db': -12, 'duck': duck(7)})
arp = track('arp', 'Pluck arpeggio', 'rhythm', 'surge', -27.5, program=84, mix={
    'pan': 0.27, 'highpass': 220, 'reverb_db': -20, 'duck': duck(3),
    'delay': {'beats': 0.75, 'feedback': 0.32, 'send_db': -17, 'ping_pong': True, 'highpass': 500, 'lowpass': 7000}})
riff = track('riff', 'Riff synth', 'rhythm', 'surge', -23.5, program=87, mix={
    'pan': 0.1, 'highpass': 70, 'saturate': 0.2, 'duck': duck(4)})
bass = track('bass', 'Synth bass', 'bass', 'surge', -21.5, program=38, mix={
    'pan': 0, 'highpass': 30, 'saturate': 0.2, 'duck': duck(6)})
drums = track('drums', 'Drum machine (909)', 'drums', 'drum_synth', -7.5, program=0, kit={'style': '909'}, mix={
    'level_mode': 'peak', 'pan': 0, 'highpass': 30, 'reverb_db': -23})
revcrash = track('revcrash', 'Reverse crash (two bars)', 'effect', 'surge', -30.0, program=119, mix={
    'pan': 0, 'highpass': 250, 'reverb_db': -12})
riser = track('riser', 'Reverse crash riser (eight bars)', 'effect', 'surge', -36.0, program=119, mix={
    'pan': 0, 'highpass': 300, 'reverb_db': -12})
impact = track('impact', 'Noise impact', 'effect', 'noise', -17.0, program=122, mix={
    'level_mode': 'peak', 'pan': 0, 'highpass': 35, 'lowpass': 9000, 'reverb_db': -14})
revcrash['surge']['swell'] = True
riser['surge']['swell'] = True
# The riff patch is saved as a mono voice that slides 50 ms into every note; glide_ms makes it slide between
# overlapping notes only, and the riff's notes are detached, so each speaks at its pitch.
riff['surge']['glide_ms'] = 20

# ============================================================================================= LEAD
# The hook: a zigzag call (down a fourth, up a sixth, an appoggiatura falling by step) in a 3+3+2 rhythm, and a
# stepwise tail.  Bars 1-2 state it, 3-4 restate it higher over VI-VII, 5-8 fragment it down to V.
HOOK = {
    1: "G5!:0.75 D5:0.75 Bb5!:0.5 A5:1 G5:1",
    2: "F5:0.5 Eb5:0.25 D5:0.75 Bb4:0.5 C5:0.5 D5:1 r:0.5",
    3: "G5!:0.75 Eb5:0.75 Bb5!:0.5 C6:1 Bb5:1",
    4: "A5:0.5 G5:0.25 F5:0.75 C5:0.5 F5:0.5 A5:1 r:0.5",
    5: "D5:0.25 G5:0.25 Bb5!:0.5 A5:0.5 G5:0.5 D5:0.25 G5:0.25 Bb5!:0.5 A5:0.5 G5:0.5",
    6: "F5:0.25 Bb5:0.25 C6!:0.5 Bb5:0.5 F5:0.5 D5:0.25 F5:0.25 Bb5!:0.5 A5:0.5 Bb5:0.5",
    7: "G5!:0.75 Eb5:0.25 D5:0.5 C5:0.5 Eb5:0.75 D5:0.25 C5:0.5 Bb4:0.5",
    8: "A4:0.5 D5:0.5 F#5:0.5 A5!:0.5 F#5_:1.5 r:0.5",
}
for b, text in HOOK.items():
    line(lead, b, text, 98, 'hook_a_antecedent')
# Consequent: the hook again, its tails turned upward, then three bars on the 3+3+2 head down to the Neapolitan.
CONSEQUENT = {
    9: HOOK[1],
    10: "F5:0.5 Eb5:0.25 D5:0.75 G5:0.5 A5:0.5 Bb5:1 r:0.5",
    11: HOOK[3],
    12: "A5:0.5 G5:0.25 F5:0.75 A5:0.5 Bb5:0.5 C6:1 r:0.5",
    13: "Bb5!:0.75 F5:0.75 Bb5:0.5 C6:0.5 Bb5:0.5 A5:0.5 Bb5:0.5",
    14: "C6!:0.75 G5:0.75 Eb5:0.5 G5:0.5 Bb5:0.5 G5:0.5 Bb5:0.5",
    15: "C6!:0.75 Ab5:0.75 Eb5:0.5 Ab5!:0.75 Eb5:0.75 C5:0.5",
    16: "D5:0.5 F#5:0.5 A5:0.5 C6!:0.5 A5:0.5 F#5_:1.5",
}
for b, text in CONSEQUENT.items():
    line(lead, b, text, 100, 'hook_a_consequent')
line(lead, 17, "G5!':0.5 r:3.5", 100, 'hook_a_consequent')  # the leading tone resolves on the riff's downbeat

# Riff section: the lead rests eight bars, then a repeated-note motif (three stabs and a leap), bars 25-28,
# and the hook's call a third lower climbing to the pickup, bars 29-32.
RIFF_LEAD = {
    25: "r:1 D5':0.5 D5':0.25 D5:0.25 G5!:0.75 D5:0.75 r:0.5",
    26: "r:1 D5':0.5 D5':0.25 D5:0.25 Bb5!:0.75 G5:0.75 r:0.5",
    27: "r:1 Eb5':0.5 Eb5':0.25 Eb5:0.25 Ab5!:0.75 Eb5:0.75 r:0.5",
    28: "r:1 D5':0.5 D5':0.25 D5:0.25 G5!:0.75 Bb5:0.75 G5:0.5",
    29: "Eb5!:0.75 C5:0.75 G5!:0.5 F5:1 Eb5:1",
    30: "D5:0.5 C5:0.25 Bb4:0.75 G4:0.5 A4:0.5 Bb4:1 r:0.5",
    31: "Bb4:0.5 Eb5:0.5 G5!:1 C5:0.5 F5:0.5 A5!:1",
    32: "D5:0.5 F#5:0.5 A5:0.5 C6!:0.5 A5:1 r:0.25 D5:0.25 E5:0.25 F#5:0.25",
}
for b, text in RIFF_LEAD.items():
    line(lead, b, text, 99 if b < 29 else 100, 'riff_answer' if b < 29 else 'riff_climb')

# hook_b: bars 33-40 are the hook as first heard (the arrangement changes); 41-44 the hook a third higher;
# 45-48 a broad two-bar sequence, the Neapolitan, and the cadence.
HOOK_B = dict((32 + b, HOOK[b]) for b in range(1, 8))
HOOK_B.update({
    40: "A4:0.5 D5:0.5 F#5:0.5 A5!:0.5 F#5_:1 r:0.25 F#5:0.25 G5:0.25 A5:0.25",
    41: "Bb5!:0.75 G5:0.75 D6!:0.5 C6:1 Bb5:1",
    42: "A5:0.5 G5:0.25 F5:0.75 G5:0.5 A5:0.5 Bb5:1 r:0.5",
    43: "Bb5!:0.75 G5:0.75 D6!:0.5 Eb6:1 D6:1",
    44: "C6:0.5 Bb5:0.25 A5:0.75 F5:0.5 A5:0.5 C6:1 r:0.5",
    45: "D6!_:2 C6:0.5 Bb5:0.5 C6:0.5 D6:0.5",
    46: "Eb6!_:1.5 D6:0.5 C6:1 G5:0.5 r:0.5",
    47: "Ab5:0.75 C6:0.75 Eb6!:0.5 C6:0.75 Ab5:0.75 Eb5:0.5",
    48: "D5:0.5 F#5:0.5 A5:0.5 C6!:0.5 A5_:1.5 r:0.5",
})
for b, text in HOOK_B.items():
    line(lead, b, text, 102 if b < 41 else 106, 'hook_b_first' if b < 41 else 'hook_b_lifted')

# chase: a one-bar idea rising by step with the bass (49-51), broken at 52; a broad answer (53-56); then the
# repeated-note motif of the riff section in rising sequence to F6 (57-60), the Neapolitan (61-62), V and a stop.
CHASE = {
    49: "C5:0.25 Eb5:0.25 G5!:0.5 F5:0.5 Eb5:0.5 G5_:1.5 r:0.5",
    50: "D5:0.25 F5:0.25 A5!:0.5 G5:0.5 F5:0.5 A5_:1.5 r:0.5",
    51: "Eb5:0.25 G5:0.25 Bb5!:0.5 A5:0.5 G5:0.5 Bb5_:1.5 r:0.5",
    52: "A5!:0.75 C6:0.75 A5:0.5 Bb5:0.5 C6:0.5 Bb5:0.5 C6:0.5",
    53: "D6!_:1.5 C6:0.5 Bb5:0.5 A5:0.5 G5:0.5 r:0.5",
    54: "G5:0.25 A5:0.25 Bb5:0.25 C6:0.25 D6!:0.5 Bb5:0.5 G5:0.25 A5:0.25 Bb5:0.25 C6:0.25 D6!_:1",
    55: "C6!:0.75 Ab5:0.75 Eb5:0.5 Ab5:0.75 C6!:0.75 Ab5:0.5",
    56: "A5_:1 F#5:0.5 D5:0.5 F#5:0.5 A5:0.5 D6!:0.5 A5:0.5",
    57: "G5':0.5 G5':0.25 G5:0.25 C6!:0.75 G5:0.75 Eb5:0.5 G5:0.5 r:0.5",
    58: "A5':0.5 A5':0.25 A5:0.25 D6!:0.75 A5:0.75 F5:0.5 A5:0.5 r:0.5",
    59: "Bb5':0.5 Bb5':0.25 Bb5:0.25 Eb6!:0.75 Bb5:0.75 G5:0.5 Bb5:0.5 r:0.5",
    60: "C6':0.5 C6':0.25 C6:0.25 F6!:0.75 C6:0.75 A5:0.5 C6:0.5 r:0.5",
    61: "Eb6!_:2 C6:0.5 Ab5:0.5 C6:0.5 Eb6:0.5",
    62: "Eb6!:0.75 C6:0.75 Ab5:0.5 C6:0.75 Ab5:0.75 Eb5:0.5",
    63: "D5:0.25 F#5:0.25 A5:0.5 D6!_:1 C6:0.5 A5:0.5 F#5:0.5 A5:0.5",
    64: "D6!':0.5 r:1 D6!':0.5 r:2",
}
for b, text in CHASE.items():
    line(lead, b, text, 104 if b < 57 else 110, 'chase_sequence' if b < 57 else 'chase_peak')

# build: the hook's call an octave down and quiet (93, 95); the repeated-note motif climbing two bars at a time
# (97-104); the call's 3+3+2 head over the dominant pedal, once a bar then twice (105-110); a trill of the
# suspension, the seventh, and the pickup D-E-F# into bar 1's G.
BUILD = {
    93: "G4:0.75 D4:0.75 Bb4:0.5 A4:1 G4:1",
    95: "G4:0.75 Eb4:0.75 Bb4:0.5 C5:1 Bb4:1",
    97: "r:1 G4':0.5 G4':0.25 G4:0.25 C5!:0.75 G4:0.75 r:0.5",
    98: "r:1 G4':0.5 G4':0.25 G4:0.25 Eb5!:0.75 C5:0.75 r:0.5",
    99: "r:1 Bb4':0.5 Bb4':0.25 Bb4:0.25 Eb5!:0.75 Bb4:0.75 r:0.5",
    100: "r:1 Bb4':0.5 Bb4':0.25 Bb4:0.25 G5!:0.75 Eb5:0.75 r:0.5",
    101: "C5':0.5 C5':0.25 C5:0.25 F5!:0.75 C5:0.75 A5:0.5 F5:0.5 r:0.5",
    102: "C5':0.5 C5':0.25 C5:0.25 A5!:0.75 F5:0.75 C6:0.5 A5:0.5 r:0.5",
    103: "Eb5':0.5 Eb5':0.25 Eb5:0.25 Ab5!:0.75 Eb5:0.75 C6:0.5 Ab5:0.5 r:0.5",
    104: "Eb5':0.5 Eb5':0.25 Eb5:0.25 Ab5!:0.75 C6:0.75 Ab5:0.5 C6:0.5 r:0.5",
    105: "A5!:0.75 D5:0.75 G5:0.5 r:2",
    106: "A5!:0.75 D5:0.75 F#5:0.5 r:2",
    107: "Bb5!:0.75 D5:0.75 G5:0.5 r:2",
    108: "A5!:0.75 D5:0.75 F#5:0.5 A5!:0.75 D5:0.75 F#5:0.5",
    109: "A5!:0.75 D5:0.75 G5:0.5 A5!:0.75 D5:0.75 G5:0.5",
    110: "Bb5!:0.75 D5:0.75 G5:0.5 Bb5!:0.75 D5:0.75 G5:0.5",
    111: "A5!:0.5 G5:0.5 A5:0.5 G5:0.5 A5!:0.5 G5:0.5 A5:0.5 G5:0.5",
    112: "A5:0.25 F#5:0.25 A5:0.25 F#5:0.25 C6!:0.25 A5:0.25 C6:0.25 A5:0.25 C6!_:1 r:0.25 D5:0.25 E5:0.25 F#5!:0.25",
}
BUILD_VEL = {93: 78, 95: 80, 97: 84, 98: 86, 99: 88, 100: 90, 101: 92, 102: 94, 103: 96, 104: 98, 105: 98, 106: 99,
             107: 100, 108: 101, 109: 102, 110: 104, 111: 105, 112: 108}
for b, text in BUILD.items():
    line(lead, b, text, BUILD_VEL[b], 'build_tease' if b < 97 else 'build_climb' if b < 105 else 'build_pedal')

# ============================================================================================= COUNTER
# hook_b 33-40: a tenor answer in the lead's long notes.  41-44: the original hook, under the lead's lifted one.
# 45-48 and the chase: thirds and fourths under the lead, and echoes of its one-bar idea.
COUNTER = {
    33: "r:1 G4:1.5 A4:0.5 Bb4:1",
    34: "A4:0.5 G4:1 r:0.5 D4:0.5 G4:0.5 Bb4:1",
    35: "r:1 Bb4:1.5 C5:0.5 D5:1",
    36: "C5:0.5 A4:1 r:0.5 A4:0.5 C5:1.5",
    37: "Bb4_:2 D5_:2",
    38: "D5_:1.5 C5:0.5 Bb4_:2",
    39: "G4_:2 Eb4_:2",
    40: "D4:1 F#4:1 A4_:2",
    41: HOOK[1], 42: HOOK[2], 43: HOOK[3], 44: HOOK[4],
    45: "Bb5_:2 A5:0.5 G5:0.5 A5:0.5 Bb5:0.5",
    46: "C6_:1.5 Bb5:0.5 G5:1 Eb5:1",
    47: "Eb5:0.75 Ab5:0.75 C6:0.5 Ab5:0.75 Eb5:0.75 C5:0.5",
    48: "A4:0.5 D5:0.5 F#5:0.5 A5:0.5 F#5_:1.5 r:0.5",
    49: "r:2 G4:0.25 C5:0.25 Eb5!:0.5 C5:1",
    50: "r:2 A4:0.25 D5:0.25 F5!:0.5 D5:1",
    51: "r:2 Bb4:0.25 Eb5:0.25 G5!:0.5 Eb5:1",
    52: "F5:0.75 A5:0.75 F5:0.5 G5:0.5 A5:0.5 G5:0.5 A5:0.5",
    53: "Bb5_:1.5 A5:0.5 G5_:1 D5:1",
    54: "G4_:2 Bb4:1 D5:1",
    55: "Ab5:0.75 Eb5:0.75 C5:0.5 Eb5:0.75 Ab5:0.75 Eb5:0.5",
    56: "F#5_:1 D5:0.5 A4:0.5 D5:0.5 F#5:0.5 A5:0.5 F#5:0.5",
    57: "Eb5':0.5 Eb5':0.25 Eb5:0.25 G5!:0.75 Eb5:0.75 C5:0.5 Eb5:0.5 r:0.5",
    58: "F5':0.5 F5':0.25 F5:0.25 A5!:0.75 F5:0.75 D5:0.5 F5:0.5 r:0.5",
    59: "G5':0.5 G5':0.25 G5:0.25 Bb5!:0.75 G5:0.75 Eb5:0.5 G5:0.5 r:0.5",
    60: "A5':0.5 A5':0.25 A5:0.25 C6!:0.75 A5:0.75 F5:0.5 A5:0.5 r:0.5",
    61: "C6_:2 Ab5:0.5 Eb5:0.5 Ab5:0.5 C6:0.5",
    62: "C6:0.75 Ab5:0.75 Eb5:0.5 Ab5:0.75 Eb5:0.75 C5:0.5",
    63: "r:1 F#5_:1 A5:0.5 F#5:0.5 D5:0.5 F#5:0.5",
    64: "A5!':0.5 r:1 A5!':0.5 r:2",
    # build: an echo of the lead's fragment an octave down in the bar's second half, then doubling it
    105: "r:2 A4:0.75 D4:0.75 G4:0.5",
    106: "r:2 A4:0.75 D4:0.75 F#4:0.5",
    107: "r:2 Bb4:0.75 D4:0.75 G4:0.5",
    108: "A4:0.75 D4:0.75 F#4:0.5 A4:0.75 D4:0.75 F#4:0.5",
    109: "A4:0.75 D4:0.75 G4:0.5 A4:0.75 D4:0.75 G4:0.5",
    110: "Bb4:0.75 D4:0.75 G4:0.5 Bb4:0.75 D4:0.75 G4:0.5",
    111: "A4:0.5 G4:0.5 A4:0.5 G4:0.5 A4:0.5 G4:0.5 A4:0.5 G4:0.5",
    112: "F#4:0.5 A4:0.5 C5:0.5 A4:0.5 C5_:1 r:1",
}
for b, text in COUNTER.items():
    vel = 88 if b < 41 else 92 if b < 49 else 96 if b < 65 else BUILD_VEL[b] - 6
    line(counter, b, text, vel, 'counter_answer' if b < 41 else 'counter_harmony' if b < 65 else 'counter_build')

# ============================================================================================= SOFT LEAD
# The contrast theme: a rising three-note pickup into an appoggiatura that falls by step, stated in E-flat (65-68),
# sequenced on Cm7 (69-72), restated a third higher (73-76) and brought to a 4-3 suspension over V (79-80).
# Bars 81-84 are the hook's call at half speed; 85-88 fold back to the suspension.
SOFT = {
    65: "r:1 G4:1 Bb4:1 D5:1",
    66: "F5!_:2 Eb5:1 D5:1",
    67: "D5_:1.5 C5:0.5 Bb4:1 F5:1",
    68: "D5_:3 r:1",
    69: "r:1 G4:1 Bb4:1 Eb5:1",
    70: "G5!_:2 F5:1 Eb5:1",
    71: "F5_:1.5 G5:0.5 F5:1 C5:1",
    72: "C5_:3 r:1",
    73: "r:1 Bb4:1 D5:1 G5:1",
    74: "Bb5!_:2 G5_:1.5 F5:0.5",
    75: "F5_:1.5 Eb5:0.5 D5:1 Bb4:1",
    76: "D5_:2 r:0.5 D5:0.5 Eb5:0.5 F5:0.5",
    77: "G5!_:1.5 Bb5:0.5 G5:1 Eb5:1",
    78: "F5:1 Eb5:1 D5:1 C5:1",
    79: "A4:1 D5:1 G5!_:2",
    80: "F#5_:3 r:1",
    81: "G5!_:1.5 D5_:1.5 Bb5:1",
    82: "A5_:2 G5_:2",
    83: "G5!_:1.5 Eb5_:1.5 Bb5:1",
    84: "C6_:2 Bb5_:2",
    85: "G5_:1.5 Eb5_:1.5 C5:1",
    86: "D5_:2 Eb5:1 C5:1",
    87: "D5:1 G5!_:3",
    88: "F#5_:3 r:1",
}
for b, text in SOFT.items():
    line(softlead, b, text, 80 if b < 73 else 86 if b < 81 else 84, 'contrast_theme' if b < 81 else 'hook_at_half_speed',
         gate=0.97)

# ============================================================================================= RIFF SYNTH + BASS RIFF
# A two-bar ostinato on the tonic pedal: 3+3+2 hits with an octave pop and the flat third, answered by a falling
# F-D-Bb-A turn.  Bars 19 and 27 raise the pop and the answer to A-flat (the flat second over the G pedal).
def riff_bar(form, root):
    if form == 'A':
        return [(0, 0.5, 0, 1), (0.75, 0.5, 0, 0), (1.5, 0.5, 12, 1), (2.0, 0.5, 0, 0), (2.75, 0.5, 3, 1), (3.5, 0.5, 0, 0)]
    if form == 'Amaj':
        return [(0, 0.5, 0, 1), (0.75, 0.5, 0, 0), (1.5, 0.5, 12, 1), (2.0, 0.5, 0, 0), (2.75, 0.5, 4, 1), (3.5, 0.5, 0, 0)]
    if form == 'Ab2':
        return [(0, 0.5, 0, 1), (0.75, 0.5, 0, 0), (1.5, 0.5, 13, 1), (2.0, 0.5, 0, 0), (2.75, 0.5, 1, 1), (3.5, 0.5, 0, 0)]
    if form == 'B':
        return [(0, 0.5, 0, 1), (0.75, 0.5, 0, 0), (1.5, 0.5, 12, 1), (2.0, 0.5, 10, 0), (2.5, 0.5, 7, 0), (3.0, 0.5, 3, 0),
                (3.5, 0.5, 2, 0)]
    if form == 'Bdom':
        return [(0, 0.5, 0, 1), (0.75, 0.5, 0, 0), (1.5, 0.5, 12, 1), (2.0, 0.5, 10, 0), (2.5, 0.5, 7, 0), (3.0, 0.5, 4, 0),
                (3.5, 0.5, 0, 0)]
    if form == 'EbF':
        return [(0, 0.5, 0, 1), (0.75, 0.5, 0, 0), (1.5, 0.5, 4, 0), (2.0, 0.5, 2, 1), (2.75, 0.5, 2, 0), (3.5, 0.5, 6, 0)]
    if form == 'eighths':
        return [(k * 0.5, 0.5, 0, 1 if k % 2 == 0 else 0) for k in range(8)]
    raise ValueError(form)


RIFF_FORMS = {17: 'A', 18: 'B', 19: 'Ab2', 20: 'B', 21: 'A', 22: 'B', 23: 'Amaj', 24: 'Bdom',
              25: 'A', 26: 'B', 27: 'Ab2', 28: 'B', 29: 'A', 30: 'B', 31: 'EbF', 32: 'eighths'}
for b, form in RIFF_FORMS.items():
    root = bass_root(chord_at(b)) + 12  # riff synth: G2, C3, Eb3, D3; the bass an octave lower
    cresc = (b - 17) * 0.4
    for k, (pos, dur, off, accent) in enumerate(riff_bar(form, root)):
        v = 92 + cresc + (10 if accent else 0) + (k * 2.2 if form == 'eighths' else 0)
        add(riff, b, pos, dur, root + off, v, 0.62, 'riff')
        add(bass, b, pos, dur, root - 12 + off, v + 2, 0.66, 'riff')
# From bar 57 the riff synth doubles the bass an octave up in eighths: the chase's second half is the fullest.
for b in range(57, 64):
    root = bass_root(chord_at(b)) + 12
    for k in range(8):
        add(riff, b, k * 0.5, 0.5, root + (12 if k in (3, 7) else 0), 92 + (8 if k % 2 == 0 else 0), 0.6, 'climax_double')
for pos in (0.0, 1.5):
    add(riff, 64, pos, 0.5, 50, 112, 0.8, 'chase_stop')
# The riff synth returns under the build's second and third stages with the A form on each root, staccato.
for b in range(97, 111):
    sym = chord_at(b)
    root = bass_root(sym) + 12
    form = 'Amaj' if harmony.parse(sym)['quality'] in ('', 'sus4', '7') and sym[0] != 'G' else 'A'
    for pos, dur, off, accent in riff_bar(form, root):
        if sym in ('Dsus4', 'Gm/D') and off in (3, 4):
            off = 5 if sym == 'Dsus4' else 8  # the suspended fourth G, or the six-four's B-flat, over the D pedal
        add(riff, b, pos, dur, root + off, 70 + (b - 97) * 2.2 + (9 if accent else 0), 0.55, 'riff_build')

# ============================================================================================= BASS
def bass_bar(b, style, vel, phrase):
    for beat in range(4):
        sym = chord_at(b, beat)
        r = bass_root(sym)
        if style == 'roll':  # the three sixteenths after each kick; an octave pop closes beats 2 and 4
            cells = [(0.25, r, 0), (0.5, r, -6), (0.75, r + 12 if beat in (1, 3) else r, 4)]
        elif style == 'roll8':  # the same with the octave in the middle of every beat
            cells = [(0.25, r, 0), (0.5, r + 12, 2), (0.75, r, -4)]
        elif style == 'drive':  # unbroken sixteenths
            cells = [(0.0, r, 6), (0.25, r, -8), (0.5, r + 12, 2), (0.75, r, -6)]
        elif style == 'off':  # the off-beat eighth
            cells = [(0.5, r, 0)]
        elif style == 'pedal':
            cells = [(0.0, r, 4), (0.25, r, -8), (0.5, r, 0), (0.75, r, -6)]
        else:
            raise ValueError(style)
        for off, pitch, dv in cells:
            add(bass, b, beat + off, 0.5 if style == 'off' else 0.25, pitch, vel + dv,
                0.8 if style == 'off' else 0.72, phrase)


for b in range(1, 17):
    bass_bar(b, 'roll', 100, 'hook_a')
for b in range(33, 49):
    bass_bar(b, 'roll8', 104, 'hook_b')
for b in range(49, 64):
    bass_bar(b, 'drive', 104 + (4 if b >= 57 else 0), 'chase')
for pos in (0.0, 1.5):  # bar 64: two hits with the band, then nothing
    add(bass, 64, pos, 0.5, 38, 112, 0.8, 'chase_stop')
# contrast: long roots; from bar 73 an octave on the "and" of 3 and a pickup that is a tone of its own chord
CONTRAST_PICKUP = {73: 'Bb1', 74: 'Eb2', 75: 'F2', 76: 'D2', 77: 'G1', 78: 'C2', 79: 'A1', 80: 'A1',
                   81: 'D2', 82: 'D2', 83: 'Bb1', 84: 'Bb1', 85: 'G1', 86: 'C2', 87: 'A1', 88: 'A1'}
for b in range(65, 89):
    r = bass_root(chord_at(b))
    if b < 73:
        add(bass, b, 0, 4, r, 62, 0.98, 'contrast')
    else:
        add(bass, b, 0, 2.5, r, 70, 0.96, 'contrast')
        add(bass, b, 2.5, 1.0, r + 12, 60, 0.9, 'contrast')
        add(bass, b, 3.5, 0.5, P(CONTRAST_PICKUP[b]), 66, 0.9, 'contrast')
for b in range(89, 97):
    bass_bar(b, 'off', 82 + (b - 89) * 2, 'build_offbeat')
for b in range(97, 105):
    bass_bar(b, 'roll', 92 + (b - 97) * 1.5, 'build_roll')
for b in range(105, 112):  # bar 112: no bass
    bass_bar(b, 'pedal', 98 + (b - 105) * 2, 'build_pedal')

# ============================================================================================= ARP
def arp_bar(b, pattern, low, vel, phrase, steps=None):
    for half in (0, 1):
        sym = chord_at(b, half * 2)
        t = ladder(sym, low)
        if pattern == 'down':  # 3+3+2, each group falling
            seq = [t[2], t[1], t[0], t[2], t[1], t[0], t[2], t[1]] if half == 0 else \
                  [t[3], t[2], t[1], t[3], t[2], t[1], t[3], t[2]]
        elif pattern == 'up':  # 3+3+2, each group rising
            seq = [t[0], t[1], t[2], t[0], t[1], t[2], t[1], t[2]] if half == 0 else \
                  [t[1], t[2], t[3], t[1], t[2], t[3], t[2], t[3]]
        elif pattern == 'zigzag':
            seq = [t[0], t[2], t[1], t[3]] * 2
        elif pattern == 'broken':  # eighths, for the contrast
            seq = ([t[0], None, t[2], None, t[1], None, t[2], None] if half == 0 else
                   [t[3], None, t[2], None, t[1], None, t[2], None])
        elif pattern == 'head':  # only the hook's 3+3+2 accents
            seq = [t[3], None, None, t[2], None, None, t[3], None] if half == 0 else \
                  [t[1], None, None, t[2], None, None, t[3], None]
        else:
            raise ValueError(pattern)
        for k, pitch in enumerate(seq):
            if pitch is None or (steps is not None and half * 8 + k not in steps):
                continue
            accent = k in (0, 3, 6)
            dur = 0.5 if pattern == 'broken' or (pattern == 'head' and k == 6) else 0.75 if pattern == 'head' else 0.25
            add(arp, b, half * 2 + k * 0.25, dur, pitch, vel + (14 if accent else 0) - (4 if k % 2 else 0),
                0.9 if pattern in ('broken', 'head') else 0.8, phrase)


for b in range(1, 17):
    arp_bar(b, 'down', 55, 78, 'hook_a')
for b in range(25, 33):
    arp_bar(b, 'down', 55, 70 + (b - 25) * 1.5, 'riff')
for b in range(33, 49):
    arp_bar(b, 'up', 58, 82, 'hook_b')
for b in range(49, 64):
    arp_bar(b, 'zigzag', 58, 84, 'chase')
arp_bar(64, 'zigzag', 58, 88, 'chase', steps=set(range(8)))
for b in range(65, 89):
    arp_bar(b, 'broken', 55 if b < 81 else 58, 62 + (4 if b >= 73 else 0), 'contrast')
for b in range(89, 93):
    arp_bar(b, 'head', 55, 74, 'build_tease')
for b in range(93, 105):
    arp_bar(b, 'down', 55, 68 + (b - 93) * 1.3, 'build')
for b in range(105, 113):
    arp_bar(b, 'zigzag', 58 if b < 111 else 62, 78 + (b - 105), 'build_pedal')

# ============================================================================================= STABS and PAD
def lead_floor(b):
    """The lowest lead (or soft lead, or counter harmony) pitch sounding in a bar, for the chords' ceiling."""
    lo = [n['pitch'] for t in (lead, softlead) for n in t['notes'] if beat_of(b) <= n['on'] < beat_of(b + 1)]
    return min(lo) if lo else 84


def slots(first, last):
    """(bar, beat, symbol) for every chord of the bars first..last."""
    return [(b, beat, sym) for b in range(first, last + 1) for beat, sym in CHORDS[b]]


def sounding(first_beat, last_beat, parts, min_dur=0.0):
    """Pitches the given parts start in [first_beat, last_beat), of notes at least `min_dur` long."""
    return sorted({n['pitch'] for t in parts for n in t['notes']
                   if first_beat <= n['on'] < last_beat and n['duration'] >= min_dur})


def voicings(first, last, voices, low, high, ceiling=True, keep_root=False, against=False):
    sl = slots(first, last)
    ceilings = [max(low + 12, min(high, lead_floor(b) - 2)) for b, _, _ in sl] if ceiling else None
    ag = None
    if against:  # the arpeggio's notes and the sustained notes of the lines, chord by chord
        ends = [beat_of(b, beat) for b, beat, _ in sl[1:]] + [beat_of(last + 1)]
        ag = [sounding(beat_of(b, beat), e, [arp]) + sounding(beat_of(b, beat), e, [lead, softlead, counter], 0.75)
              for (b, beat, _), e in zip(sl, ends)]
    v = voice_lead([s for _, _, s in sl], voices=voices, low=low, high=high, ceilings=ceilings, keep_root=keep_root,
                   against=ag)
    return {(b, beat): chord for (b, beat, _), chord in zip(sl, v)}


def voicing_at(table, b, pos):
    keys = sorted(k for k in table if k[0] == b and k[1] <= pos + 1e-9)
    return table[keys[-1]]


STAB_RHYTHM = {
    'hook_odd': [(0.5, 0.25, 0), (1.5, 0.5, 1), (2.5, 0.25, 0), (3.5, 0.5, 1)],
    'hook_even': [(0.5, 0.25, 0), (1.5, 0.5, 1), (2.25, 0.25, 0), (3.0, 0.25, 0), (3.5, 0.5, 1)],
    'hookb_odd': [(0.5, 0.25, 0), (1.25, 0.25, 0), (1.5, 0.5, 1), (2.5, 0.25, 0), (3.5, 0.5, 1)],
    'hookb_even': [(0.5, 0.25, 0), (1.5, 0.5, 1), (2.25, 0.25, 0), (3.0, 0.25, 0), (3.5, 0.25, 0), (3.75, 0.25, 1)],
    'riff_a': [(1.0, 0.5, 1), (3.0, 0.25, 0)],
    'riff_b': [(1.0, 0.5, 1)],
    'riff_turn': [(1.0, 0.5, 1), (3.0, 0.5, 1)],
    'chase': [(0.0, 0.5, 1), (1.5, 0.25, 0), (2.5, 0.25, 0), (3.0, 0.25, 0), (3.5, 0.5, 1)],
    'chase_lean': [(0.0, 0.5, 1), (3.5, 0.5, 1)],
    'stop': [(0.0, 0.5, 1), (1.5, 0.5, 1)],
    'offbeat': [(0.5, 0.25, 0), (1.5, 0.5, 1), (2.5, 0.25, 0), (3.5, 0.5, 1)],
    'eighths': [(k * 0.5, 0.25 if k % 2 == 0 else 0.5, k % 2) for k in range(8)],
}


def stab_bars(first, last, rhythm_of, vel_of, phrase, low=57, high=74):
    table = voicings(first, last, 3, low, high)
    for b in range(first, last + 1):
        for pos, dur, accent in STAB_RHYTHM[rhythm_of(b)]:
            for pitch in voicing_at(table, b, pos):
                add(stab, b, pos, dur, pitch, vel_of(b) + (10 if accent else 0), 0.7 if dur <= 0.25 else 0.85, phrase)


stab_bars(1, 16, lambda b: 'hook_odd' if b % 2 else 'hook_even', lambda b: 84, 'hook_a')
stab_bars(17, 32, lambda b: 'riff_turn' if b in (23, 24, 31, 32) else 'riff_a' if b % 2 else 'riff_b',
          lambda b: 98, 'riff')
stab_bars(33, 48, lambda b: 'hookb_odd' if b % 2 else 'hookb_even', lambda b: 88, 'hook_b', low=58, high=75)
stab_bars(49, 64, lambda b: 'stop' if b == 64 else 'chase_lean' if b < 57 else 'chase',
          lambda b: 88 if b < 57 else 94, 'chase', low=58, high=75)
stab_bars(97, 112, lambda b: 'eighths' if b >= 111 else 'offbeat',
          lambda b: 72 if b >= 111 else 60 + (b - 97) * 1.6, 'build')


def pad_bars(first, last, vel, phrase, low=53, high=67, voices=3, keep_root=False, stop_at=None):
    """Held chords, voiced to move as little as possible.  A pitch two chords share is held across the change;
    of the voices that do move, the upper ones enter a beat after the lowest, so a change is not one block."""
    sl = slots(first, last)
    table = voicings(first, last, voices, low, high, ceiling=False, keep_root=keep_root, against=True)
    end = beat_of(last + 1) if stop_at is None else stop_at
    starts = [beat_of(b, beat) for b, beat, _ in sl] + [end]
    open_notes = {}  # pitch -> (bar, pos, start beat)
    for i, (b, beat, _) in enumerate(sl):
        chord, start, stop = table[(b, beat)], starts[i], starts[i + 1]
        nxt = table[(sl[i + 1][0], sl[i + 1][1])] if i + 1 < len(sl) else []
        moving = [p for p in chord if p not in open_notes]
        for k, pitch in enumerate(sorted(moving)):
            delay = 0.0 if k == 0 or stop - start < 2 else 1.0 if k % 2 else 0.5
            open_notes[pitch] = (b, beat + delay, start + delay)
        for pitch in list(open_notes):
            held_long = stop - open_notes[pitch][2] >= 16
            if pitch not in nxt or held_long or pitch not in chord:
                bb, pp, s0 = open_notes.pop(pitch)
                add(pad, bb, pp, round(stop - s0, 6), pitch, vel, 1.0, phrase)


pad_bars(1, 16, 70, 'hook_a')
pad_bars(25, 32, 66, 'riff')
pad_bars(33, 48, 74, 'hook_b', high=65)  # under the counter synth's answers (G4-D5)
pad_bars(57, 64, 78, 'chase', stop_at=beat_of(64, 2.0))  # held back until the chase's second half
pad_bars(65, 88, 76, 'contrast', low=48, high=74, voices=4, keep_root=True)
pad_bars(89, 112, 72, 'build')

# ============================================================================================= DRUMS
K, RIM, S, CLAP, HC, HO, RIDE, CRASH, T1, T2, T3, SHAKER = 36, 37, 38, 39, 42, 46, 51, 49, 50, 47, 43, 70
DRUM_VEL = {K: 112, S: 104, CLAP: 96, HC: 70, HO: 82, RIDE: 72, CRASH: 106, T1: 100, T2: 102, T3: 104, RIM: 84,
            SHAKER: 52}


def hits(b, voice, pattern, vel=None, ramp=None, step=0.25):
    """A bar of one drum on a grid: x a hit, X an accent, o a ghost, . a rest.  `ramp` (from, to) runs the
    velocities across the bar's hits instead."""
    base = DRUM_VEL[voice] if vel is None else vel
    on = [i for i, ch in enumerate(pattern) if ch != '.']
    for n, i in enumerate(on):
        ch = pattern[i]
        v = base + (12 if ch == 'X' else -30 if ch == 'o' else 0)
        if ramp:
            v = ramp[0] + (ramp[1] - ramp[0]) * n / max(1, len(on) - 1) + (6 if ch == 'X' else 0)
        add(drums, b, i * step, 0.12, voice, v, 0.8, 'drums')


FOUR = "x...x...x...x..."
BACK = "....x.......x..."
HAT16 = "xo.xxo.xxo.xxo.x"
OPEN8 = "..x...x...x...x."


def groove_hook(b, fuller=False, crash=False, pickup=False, crash_vel=None):
    hits(b, K, "x...x...x...x.o." if pickup else FOUR)
    hits(b, CLAP, BACK)
    if fuller:
        hits(b, S, BACK, 98)
        hits(b, RIDE, FOUR)
    hits(b, HC, HAT16)
    hits(b, HO, OPEN8)
    if crash:
        hits(b, CRASH, "x...............", crash_vel)


def fill_short(b, fuller=False):
    """Half a bar of groove, then snare and toms down the kit; the cymbals stop."""
    hits(b, K, "x...x...x.....x.")
    hits(b, CLAP, "....x...........")
    if fuller:
        hits(b, S, "....x...........", 98)
    hits(b, HC, "xo.xxo.x........")
    hits(b, HO, "..x...x.........")
    hits(b, S, "........x.xx....", ramp=(88, 104))
    hits(b, T1, "............xx..", ramp=(96, 102))
    hits(b, T2, "..............x.")
    hits(b, T3, "...............x", 110)


def fill_roll(b):
    """A bar of four-on-the-floor under a sixteenth-note snare crescendo."""
    hits(b, K, FOUR)
    hits(b, CLAP, "....x...........")
    hits(b, HC, "xo.xxo.x........")
    hits(b, S, "........xxxxxxxx", ramp=(72, 112))


# hook_a
for b in range(1, 17):
    if b == 8:
        fill_short(b)
    elif b == 16:
        fill_roll(b)
    else:
        groove_hook(b, crash=b in (1, 9), pickup=b in (4, 12), crash_vel=116 if b == 1 else None)
# riff: a broken kick under the ostinato, backbeat on the snare, eighth-note hats
for b in range(17, 33):
    if b == 24:
        hits(b, K, "x..x..x...x.....")
        hits(b, S, "....x.......x.xx", ramp=(100, 110))
        hits(b, HC, "x.x.x.x.x.x.....")
        hits(b, T2, "..........o.....")
    elif b == 32:
        hits(b, K, FOUR)
        hits(b, S, "x.x.x.x.xxxxxxxx", ramp=(70, 114))
    else:
        odd = b % 2 == 1
        hits(b, K, "x..x..x...x....." if odd else "x..x..x.x..x....")
        hits(b, S, "....X.......X..." if odd else "....X.......X..o", 96)
        hits(b, HC, "X.x.X.x.X.x.X.x." if odd else "X.x.X.x.X.x.X...", 64)
        if not odd:
            hits(b, HO, "..............x.")
        if b in (17, 25):
            hits(b, CRASH, "x...............")
# hook_b
for b in range(33, 49):
    if b == 40:
        fill_short(b, fuller=True)
    elif b == 48:
        fill_roll(b)
    else:
        groove_hook(b, fuller=True, crash=b in (33, 41, 45), pickup=b % 2 == 0)
# chase: sixteenth hats with an accent on each beat, tom answers every fourth bar, a stop
for b in range(49, 64):
    hits(b, K, "x...x...x...x.x." if b % 2 else FOUR)
    if b in (52, 56, 60):
        hits(b, S, "....x.......x...")
        hits(b, HC, "XoxoXoxoXo......", 66)
        hits(b, T1, "..........xx....", ramp=(98, 104))
        hits(b, T2, ".............x..")
        hits(b, T3, "..............xx", ramp=(104, 112))
    elif b == 63:
        hits(b, S, "x.x.x.x.x.x.xxxx", ramp=(84, 114))
        hits(b, HC, "XoxoXoxoXoxo....", 66)
    else:
        hits(b, S, "....x..o....x..." if b % 2 else "....x.......x.o.")
        hits(b, CLAP, BACK, 90)
        if b < 57:
            hits(b, HC, "XoxoXoxoXoxoXoxo", 66)
        else:  # the high point: open hats on the off-beats and the ride on the beat
            hits(b, HC, HAT16, 72)
            hits(b, HO, OPEN8, 86)
            hits(b, RIDE, FOUR, 78)
    if b in (49, 57, 59, 61):
        hits(b, CRASH, "x...............")
hits(64, K, "x.....x.........", 118)
hits(64, S, "x.....x.........", 112)
hits(64, CRASH, "x.....x.........")
# contrast: nothing for four bars, quiet hats, then half time with the backbeat on beat 3
for b in range(69, 73):
    hits(b, HC, "x.x.x.x.x.x.x.x.", ramp=(34 + (b - 69) * 3, 40 + (b - 69) * 3))
for b in range(73, 89):
    even = b % 2 == 0
    if b == 88:
        hits(b, K, "x.........x.....", 100)
        hits(b, HC, "X.x.X.x.........", 54)
        hits(b, RIM, "........x.......")
        hits(b, T1, "..........x.x...", ramp=(70, 80))
        hits(b, T2, "..............x.", 86)
        hits(b, T3, "...............x", 94)
        continue
    hits(b, K, "x.....x...x....." if even else "x.........x.....", 100)
    hits(b, RIM if b < 81 else S, "........x.......", 88 if b < 81 else 92)
    hits(b, CLAP, "........x.......", 80)
    hits(b, HC, "X.x.X.x.X.x.X.x." if not even else "X.x.X.x.X.x.X...", 66)
    hits(b, SHAKER, "..x...x...x...x." if b < 81 else "xxXxxxXxxxXxxxXx", 56 if b < 81 else 48 + (b - 81))
    if even:
        hits(b, HO, "..............x.", 76)
# build
for b in range(89, 97):
    hits(b, K, FOUR, 84 + (b - 89) * 3)
    hits(b, HC, "..x...x...x...x." if b < 93 else "x.x.x.x.x.x.x.x.", 60 + (b - 89) * 1.5)
for b in range(97, 105):
    hits(b, K, FOUR, 108 + (b - 97) * 0.5)
    hits(b, CLAP, BACK, 84 + (b - 97) * 1.5)
    hits(b, HC, HAT16, 64 + (b - 97))
    hits(b, HO, OPEN8, 70 + (b - 97) * 1.5)
    if b == 97:
        hits(b, CRASH, "x...............", 96)
ROLL = {105: ("x...x...x...x...", (62, 68)), 106: ("x...x...x...x...", (68, 74)),
        107: ("x.x.x.x.x.x.x.x.", (68, 74)), 108: ("x.x.x.x.x.x.x.x.", (72, 78)),
        109: ("xxxxxxxxxxxxxxxx", (68, 78)), 110: ("XxxxXxxxXxxxXxxx", (74, 84)),
        111: ("XxxXxxXxXxxXxxXx", (80, 90))}
for b, (pattern, ramp) in ROLL.items():
    hits(b, K, FOUR, 112)
    hits(b, S, pattern, ramp=ramp)
    hits(b, HC, HAT16, 72)
    if b == 105:
        hits(b, CRASH, "x...............", 98)
# bar 112: no kick; snare sixteenths, a beat of thirty-seconds, then the toms under the lead's pickup
hits(112, S, "XxxxXxxx", ramp=(84, 92))
hits(112, S, "." * 16 + "xxxxxxxx", ramp=(72, 92), step=0.125)
hits(112, T1, "............xx..", ramp=(84, 88))
hits(112, T2, "..............x.", 90)
hits(112, T3, "...............x", 94)

# ============================================================================================= EFFECTS
for end_bar in (17, 33, 41, 49, 57, 65, 89, 97, 105, 113):  # reverse crashes ending on these downbeats
    add(revcrash, end_bar - 2, 0, 8, 60, 82 if end_bar == 113 else 100, 1.0, 'swell')
add(riser, 105, 0, 32, 60, 104, 1.0, 'swell')  # eight bars into the top
for b, v in ((1, 112), (33, 108), (49, 110), (65, 84), (89, 90)):
    add(impact, b, 0, 2, 36, v, 1.0, 'impact', art='impact')

# ============================================================================================= MIX MOVES
B = beat_of
lead['mix']['automation'] = [[0, 0], [B(57) - 0.05, 0], [B(57), 1.8], [B(64), 1.8], [B(65), 0], [B(89) - 0.05, 0],
                             [B(89), -3], [B(97), -2], [B(105), -1], [B(109), 0], [B(113) - 0.05, 0]]
counter['mix']['automation'] = [[0, 0], [B(57) - 0.05, 0], [B(57), 1], [B(65) - 0.05, 1], [B(65), 0],
                                [B(105) - 0.05, 0], [B(105), -3], [B(111), 0]]
pad['mix']['automation'] = [[0, 0], [B(57) - 0.05, 0], [B(57), 1.5], [B(97) - 0.05, 1.5], [B(97), 0], [B(105), 0],
                            [B(112), 1]]
arp['mix']['automation'] = [[0, 0], [B(65) - 0.05, 0], [B(65), 2], [B(89) - 0.05, 2], [B(89), -2], [B(105), -2.5],
                            [B(112), -3]]
stab['mix']['automation'] = [[0, 0], [B(17) - 0.05, 0], [B(17), 2], [B(33) - 0.05, 2], [B(33), 0]]
riff['mix']['automation'] = [[0, 0], [B(25) - 0.05, 0], [B(25), -3], [B(57) - 0.05, -3], [B(57), -5],
                             [B(97) - 0.05, -5], [B(97), 0], [B(105) - 0.05, 0], [B(105), -2], [B(113) - 0.05, -2]]
arp['mix']['filter_sweep'] = {'type': 'lowpass', 'resonance': 0.3, 'points': [
    [0, 15000], [B(25) - 0.05, 15000], [B(25), 1500], [B(32), 8000], [B(33), 15000], [B(65) - 0.05, 15000],
    [B(65), 10000], [B(89) - 0.05, 10000], [B(89), 1300], [B(97), 3200], [B(105), 6000], [B(111), 15000],
    [B(113) - 0.05, 15000]]}
riff['mix']['filter_sweep'] = {'type': 'lowpass', 'resonance': 0.25, 'points': [
    [0, 14000], [B(97) - 0.05, 14000], [B(97), 500], [B(105), 2400], [B(110), 12000], [B(113) - 0.05, 14000]]}
pad['mix']['filter_sweep'] = {'type': 'highpass', 'resonance': 0.2, 'points': [
    [0, 170], [B(105) - 0.05, 170], [B(105), 170], [B(112), 900], [B(113) - 0.05, 900]]}
riser['mix']['automation'] = [[0, 0], [B(105), -4], [B(113) - 0.05, -6]]
revcrash['mix']['automation'] = [[0, 0], [B(111) - 0.05, 0], [B(111), -4], [B(113) - 0.05, -4]]

# The lead's mod wheel is the depth of a 6.4 Hz vibrato with no delay of its own (read from the patch file), so it
# is written per note: only notes of a beat and a half or more, from half a beat in, to about a third of the wheel.
lead['performance']['cc_mode'] = 'linear'
points = {}
for n in sorted(lead['notes'], key=lambda n: n['on']):
    if n['duration'] >= 1.5:
        on, end = n['on'], n['on'] + n['duration']
        for beat, value in ((on, 0), (on + 0.5, 0), (on + 1.0, 40), (end - 0.125, 40), (end, 0)):
            points[round(beat, 4)] = value
lead['performance']['cc'] = [[beat, 1, value] for beat, value in sorted(points.items())]

# ============================================================================================= RANGES, EXPRESSION
for t in project['tracks']:
    pitches = [n['pitch'] for n in t['notes']]
    t['range'] = [max(0, min(pitches) - 2), min(127, max(pitches) + 2)]
    t['notes'].sort(key=lambda n: (n['on'], n['pitch']))

# Player-like deviation, kept small: these are sequenced synthesizers and a drum machine, and listeners rate a
# tight groove no worse quantized.  The lines run in time (drift='time'), so a revised note moves no other.
report = expression.apply(project, {
    'drums': {'timing_sd': 0.8, 'short_sd': 0.4, 'vel_pct': 3, 'cymbal_cycle': 5},
    'bass': {'timing_sd': 1.2, 'short_sd': 0.6, 'feel': 0, 'vel_pct': 3, 'arch': 2, 'gate_sd': 0.02},
    'riff': {'timing_sd': 1.5, 'short_sd': 0.8, 'vel_pct': 3, 'arch': 2, 'gate_sd': 0.03, 'contrast': 0},
    'arp': {'timing_sd': 1.5, 'short_sd': 0.8, 'vel_pct': 4, 'arch': 4, 'gate_sd': 0.03, 'contrast': 0},
    'stab': {'timing_sd': 2.5, 'short_sd': 1.0, 'vel_pct': 3, 'arch': 3, 'spread': 3, 'lead': 3, 'contrast': 0},
    'pad': {'timing_sd': 4, 'short_sd': 2, 'vel_pct': 3, 'arch': 2, 'spread': 6, 'lead': 0, 'gate_sd': 0},
    'lead': {'timing_sd': 3.5, 'short_sd': 1.5, 'vel_pct': 3, 'high_loud': 0.25, 'arch': 5, 'gate_sd': 0.015,
             'contrast': 0.03},
    'counter': {'timing_sd': 4, 'short_sd': 1.5, 'vel_pct': 3, 'high_loud': 0.2, 'arch': 4, 'spread': 0},
    'softlead': {'timing_sd': 6, 'short_sd': 2, 'vel_pct': 3, 'high_loud': 0.3, 'arch': 7, 'gate_sd': 0.01,
                 'contrast': 0},
    'revcrash': None, 'riser': None, 'impact': None,
}, seed=SEED, drift='time')

# The swell parts take their attack from the note length and the pad holds through changes: keep their gates whole.
for t in (revcrash, riser, impact, pad):
    for e in t['performance']['notes'].values():
        e['gate'] = 1.0
        e['timing_ms'] = 0 if t is not pad else e['timing_ms']

project['decisions'] = [
    'Style: electronic/trance as the primary entry (148 BPM inside its sourced 120-150, minor key, a lead motif, rapid '
    'arpeggios, a break and a build with a snare roll). The form axis is borrowed from game/battle because the brief '
    'asks for a game loop that goes round again with no ending, not a DJ track with a sparse intro and outro.',
    'Tempo 148 BPM, 4/4, G minor, 112 bars = 181.6 s. The piece loops from bar 1: no intro, so one pass of the loop is '
    'the preview and the top of the loop is the hook itself.',
    'The hook (bars 1-2): a 3+3+2 call G5-D5-Bb5 with an appoggiatura A5 falling to G5, and a stepwise tail. It is the '
    'only material of hook_a and hook_b; the riff section and the build use a second, repeated-note motif.',
    'High point planned at bars 57-62 (the climax section): the melody\'s highest note F6 in bar 60, the fullest '
    'texture (pad and riff synth added, ride and open hats), then the Neapolitan A-flat and a stop on the dominant in '
    'bar 64. The contrast section is where it settles.',
    'Contrast (bars 65-88): half time, relative-major side (Ebmaj7, Bb/D, Cm7, F), a square lead, no kick on every '
    'beat; reached by a deceptive move D to E-flat. Its last eight bars play the hook at half speed.',
    'Seam: the last bar is D7 after a cadential six-four, so G, B-flat, D and A (the pitch classes of bar 1\'s first '
    'second) all sound in the last three bars. Kick and bass leave for the last bar only and return on bar 1; the '
    'snare roll, the riser, the arpeggio and the lead\'s pickup D-E-F# carry across. No tempo change.',
    'Levels are written from the lead down; kick ducking on pad, bass, stabs, riff and arpeggio (release about an '
    'eighth note at 148 BPM). Delivered at -14 LUFS: the in-game level is set in the engine.',
    'Player-like deviation is applied small (drums 0.8 ms, bass 1.2 ms, lead 3.5 ms): sequenced synthesizers.',
    'Drums are written by hand on a step grid (not from musiclib.blocks): four-on-the-floor for the hook sections, a '
    'broken kick for the riff, half time for the contrast, a snare roll doubling in rate through the last eight bars.',
]
project['authorship'] = 'Composed note by note by Claude with the music-production skill 0.6.0; no outside material.'
project['revision_history'] = [
    'r1: first full render. Before it, two score reviews: chord symbols corrected to what sounds (Eb for the hook\'s '
    'bar 3, Gm7 for the riff\'s answer bar), the pad voiced against the arpeggio and the held melody notes and kept '
    'under the counter synth, contrast bass pickups made chord tones, breaths added to the lead, the chase thinned in '
    'its first half and filled in its second. Sounds chosen by audition figures.',
    'r2: from r1\'s measurements. The build\'s last 400 ms measured 6.1 dB louder than the first 400 ms of the top: '
    'riser 7 dB down, snare roll and toms softer, arpeggio, pad and stabs held back in the last eight bars. The '
    'contrast theme measured 1.7 dB under its accompaniment and the section had 0.7% of its power above 2.5 kHz: '
    'the sine lead (0.5% above 2 kHz, unchanged by saturation) replaced by a square lead (28% above 2 kHz on the '
    'theme), bass and pad down there, hats up, a shaker added, the arpeggio\'s low-pass opened. The '
    'chase was not louder than hook_b: its second half is now a section of its own (climax) with ride, open hats, '
    'another crash, lead and counter up 1 dB and the riff synth\'s doubling down. More reverb on every send (the mix '
    'measured a clarity of +29 dB). Counter bar 36 rewritten on chord tones. Drums up 1 dB. Sections split for '
    'measuring and for cue points.',
    'r3: from r2\'s measurements. The seam still fell 2.9 dB from the last 400 ms to the first: toms, snare roll, the '
    'last reverse crash and the riser softer again, the riff synth 2 dB down over the pedal, the top\'s crash and '
    'impact harder. The climax\'s lead measured 0.7 dB under its accompaniment: lead +1.8 dB there, stabs softer, '
    'riff doubling 1.5 dB further down. The lead\'s answers in the riff section (1.9 dB under) written as loud as the '
    'hook, riff synth 3 dB down under them. The first build stage measured 3.3 dB under the contrast before it: '
    'arpeggio filter opened further, lead hint and pad up. Bass 1 dB down, stabs and pad 1 dB up (250-800 Hz held '
    '9% of the hook\'s power). Counter bar 36 moved to sixths under the lead (r2\'s rewrite doubled it at the octave).',
    'r4 (the full render): r3\'s seam still fell 2.4 dB. Measured stem by stem over the last 400 ms, the two swells '
    'together stood as loud as the lead bus (-19.5 against -19.3 dBFS RMS) and the stabs 4 dB over their level in '
    'the first 400 ms: reverse crashes 3 dB down and the last one 4 dB more, the riser 4 dB down, the last two '
    'bars\' stabs softer.',
]

if __name__ == '__main__':
    warnings = validate(project)
    out = HERE / 'song.json'
    out.write_text(json.dumps(project, indent=1), encoding='utf-8')
    counts = {t['id']: len(t['notes']) for t in project['tracks']}
    print('wrote', out, 'notes', sum(counts.values()), counts)
    if warnings:
        print('validate:', warnings)
    print('expression:', {k: v['timing_sd_ms'] for k, v in report.items()})
