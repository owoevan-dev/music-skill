#!/usr/bin/env python
"""Cairnfire - a concert overture for full orchestra.

This script writes every note of the piece into song.json (schema music-production/v1).
Run:  python compose.py            (writes song.json beside this file)

Layout of the file
  1. helpers: pitch names, the note writer, a small line notation, strokes, rolls
  2. the orchestra: one track per orchestral part and articulation
  3. the music, section by section (bars are 1-based in the code)
  4. performance: player-like deviation, dynamics curves, legato
  5. mix and project file
"""
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# line named the folder where the skill was installed on the machine it ran on).
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import expression  # noqa: E402
from musiclib.phrasing import ramp  # noqa: E402

HERE = Path(__file__).resolve().parent
TITLE = 'Cairnfire'
REVISION = 'final'

# ------------------------------------------------------------------ 1. helpers
STEP = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def P(name):
    """'F#3' -> 54 (C4 = 60)."""
    m = re.fullmatch(r'([A-G])([#b]*)(-?\d)', name)
    if not m:
        raise ValueError(f'bad pitch {name!r}')
    return 12 * (int(m[3]) + 1) + STEP[m[1]] + m[2].count('#') - m[2].count('b')


def bar(b):
    """Beat at which 1-based bar b starts (4/4)."""
    return (b - 1) * 4.0


TR = {}       # track id -> track
ORDER = []    # track ids in score order
GATE = {}     # default gate per track
COUNT = {}    # (track, bar) -> notes written, for stable ids
DYN = {}      # track -> explicit dynamics segments [(beat, value), ...] written over the automatic curve
HARMONY = []  # chord symbols for review


def add(tid, on, dur, pitch, vel, gate=None):
    t = TR[tid]
    b = int(on // 4) + 1
    k = COUNT.get((tid, b), 0)
    COUNT[(tid, b)] = k + 1
    nid = f'{tid}_b{b:03d}_n{k:02d}'
    if callable(vel):
        vel = vel(on)
    t['notes'].append({'id': nid, 'on': round(on, 4), 'duration': round(dur, 4), 'pitch': int(pitch)})
    t['performance']['notes'][nid] = {'velocity': int(max(1, min(127, round(vel)))),
                                      'gate': GATE[tid] if gate is None else gate}


def at(tid, on, text, vel, tr=0, gate=None, dv=0):
    """Write a line from beat `on`.  Tokens: 'E4:1.5' (pitch:beats), 'r:1' (rest), 'E4+B4:2' (notes together),
    '|' (a bar line, checked).  `vel` is a number or a function of the beat.  Returns the beat after the line."""
    pos = 0.0
    for tok in text.split():
        if tok == '|':
            if abs((on + pos) % 4) > 1e-6 and abs((on + pos) % 4 - 4) > 1e-6:
                raise ValueError(f'{tid}: bar line off the bar at beat {on + pos} in {text!r}')
            continue
        name, d = tok.rsplit(':', 1)
        d = float(Fraction(d))
        if name != 'r':
            v = (vel(on + pos) if callable(vel) else vel) + dv
            for nm in name.split('+'):
                add(tid, on + pos, d, P(nm) + tr, v, gate)
        pos += d
    return on + pos


def L(tid, b, text, vel, tr=0, gate=None, dv=0):
    """A line from the start of bar b."""
    return at(tid, bar(b), text, vel, tr, gate, dv)


def ML(parts, b, text, vel, gate=None):
    """One line in several parts: 'tp:0 tb:-12 fl:12/-4' = track:transposition[/velocity change]."""
    for spec in parts.split():
        tid, rest = spec.split(':')
        tr, _, dv = rest.partition('/')
        L(tid, b, text, vel, int(tr), gate, int(dv or 0))


def hit(on, spec, vel, dur=.5, gate=None):
    """A stroke: {track: 'E4+E5'} all struck at beat `on`."""
    for tid, names in spec.items():
        for nm in names.split('+'):
            add(tid, on, dur, P(nm), vel + STROKE.get(tid, 0), gate)


def eighths(tid, b, names, vel, tr=0, accent=(0, 3)):
    """Eight eighth notes in bar b; the first is accented, and the others named in `accent` a little."""
    for i, nm in enumerate(names):
        on = bar(b) + i * .5
        v = vel(on) if callable(vel) else vel
        add(tid, on, .5, P(nm) + tr, v + (8 if i == 0 else 4 if i in accent else -3))


def roll(tid, on, dur, name, v0, v1, step=.25):
    """A roll written as single strokes, `step` beats apart, from velocity v0 to v1."""
    n = int(round(dur / step))
    for i in range(n):
        add(tid, on + i * step, step, P(name), v0 + (v1 - v0) * i / max(n - 1, 1))


def dyn(tid, *points):
    """Explicit dynamics for a sustained part: (beat, 0-127) points replacing the automatic curve between them."""
    DYN.setdefault(tid, []).append(sorted(points))


def H(b, symbol, beat=0):
    HARMONY.append({'bar': b, 'beat': beat, 'symbol': symbol})


# ------------------------------------------------------------------ 2. the orchestra
def track(tid, name, role, bank_name, bank, program, gm, lo, hi, level, pan, depth, offset=0, gate=1.0,
          bus='ensemble', drums=False, mode='active_rms', facing=None, highpass=None):
    t = {'id': tid, 'name': name, 'role': role, 'engine': 'soundfont', 'program': gm, 'bank': 0,
         'soundfont': bank_name, 'patch': {'bank': bank, 'program': program},
         'range': [P(lo), P(hi)] if isinstance(lo, str) else [lo, hi],
         'notes': [], 'performance': {'notes': {}},
         'mix': {'level_dbfs': level, 'level_mode': mode, 'pan': pan, 'depth_m': depth, 'space': 'hall',
                 'reverb_db': -14, 'bus': bus}}
    if drums:
        t['drums'] = True
    if offset:
        t['performance']['offset_ms'] = offset
    if facing:
        t['mix']['facing'] = facing
    if highpass:
        t['mix']['highpass'] = highpass
    TR[tid] = t
    ORDER.append(tid)
    GATE[tid] = gate


# woodwinds (centre, 5-6.5 m back)
# (flutes, oboes, clarinets, piccolo and trombones mostly double the tune: as 'countermelody' review reads their top line)
track('picc', 'Piccolo', 'countermelody', 'vsco_extra', 0, 72, 72, 'D5', 'C8', -27.0, -.12, 5.5)
track('fl', 'Flutes 1-2', 'countermelody', 'vsco', 0, 73, 73, 'B3', 'D7', -25.0, -.15, 5.0, offset=-35)
track('fls', 'Flutes 1-2 staccato', 'rhythm', 'vsco', 1, 73, 73, 'F4', 'D7', -26.0, -.15, 5.0, gate=.9)
track('ob', 'Oboes 1-2', 'countermelody', 'vsco', 0, 68, 68, 'Bb3', 'A6', -25.0, .1, 5.0)
track('obs', 'Oboes 1-2 staccato', 'rhythm', 'vsco', 1, 68, 68, 'Bb3', 'A6', -26.0, .1, 5.0, gate=.9)
track('cl', 'Clarinets 1-2', 'countermelody', 'vsco', 0, 71, 71, 'D3', 'E6', -25.5, -.08, 6.0, offset=-60)
track('cls', 'Clarinets 1-2 staccato', 'rhythm', 'vsco', 1, 71, 71, 'D3', 'F6', -26.5, -.08, 6.0, gate=.9)
track('bn', 'Bassoons 1-2', 'harmony', 'vsco', 0, 70, 70, 'Bb1', 'Eb5', -25.0, .15, 6.0)
track('bns', 'Bassoons 1-2 staccato', 'rhythm', 'vsco', 1, 70, 70, 'Bb1', 'D5', -26.0, .15, 6.0, gate=.9)
# brass (behind the woodwinds; the horns' bells face the back wall)
# (the horns play the Iowa recordings, sampled on every semitone: on the VSCO horn 133 notes of this score
#  would have been stretched more than four semitones)
track('hn_t', 'Horns 1-2 (theme)', 'melody', 'iowa_brass', 0, 60, 60, 'A#1', 'F5', -21.5, -.35, 7.5, gate=.95, bus='lead',
      facing='back')
track('hn12', 'Horns 1-2', 'harmony', 'iowa_brass', 0, 60, 60, 'A#1', 'F5', -23.0, -.35, 7.5, gate=.92, facing='back')
track('hn34', 'Horns 3-4', 'harmony', 'iowa_brass', 0, 60, 60, 'A#1', 'F5', -23.0, -.42, 7.5, gate=.92, facing='back')
track('tp', 'Trumpets 1-2', 'melody', 'vsco', 0, 56, 56, 'F#3', 'C6', -20.0, .25, 8.5, gate=.95, bus='lead')
track('tps', 'Trumpets 1-2 staccato', 'accent', 'vsco', 1, 56, 56, 'F#3', 'C6', -21.0, .25, 8.5, gate=.9)
track('tb', 'Trombones 1-2', 'countermelody', 'vsco_extra', 0, 57, 57, 'E2', 'Bb4', -20.0, .4, 8.5, gate=.95)
track('tbs', 'Trombones short', 'accent', 'vsco_extra', 1, 57, 57, 'E2', 'Bb4', -21.0, .4, 8.5, gate=.9)
track('tb3', 'Trombone 3', 'harmony', 'vsco_extra', 0, 57, 57, 'E2', 'Bb4', -21.0, .46, 8.5, gate=.95)
track('tuba', 'Tuba', 'bass', 'vsco_extra', 0, 58, 58, 'F1', 'C4', -21.0, .5, 9.0, gate=.95, highpass=20)
track('tubas', 'Tuba staccato', 'bass', 'vsco_extra', 1, 58, 58, 'E1', 'F4', -21.5, .5, 9.0, gate=.9, highpass=20)
# timpani, percussion, harp
track('timp', 'Timpani', 'rhythm', 'vcsl', 0, 47, 47, 'D2', 'B3', -11.0, .05, 9.5, gate=1.0, mode='peak', highpass=20)
track('bd', 'Bass drum', 'drums', 'vcsl', 128, 48, 48, 27, 86, -12.0, -.1, 10.0, gate=1.0, bus='drums', drums=True,
      mode='peak', highpass=20)
track('cym', 'Cymbals and tam-tam', 'drums', 'vcsl', 128, 48, 48, 27, 86, -13.0, .1, 10.0, gate=1.0, bus='drums',
      drums=True, mode='peak')
track('harp', 'Harp', 'texture', 'vcsl', 0, 46, 46, 'C1', 'G7', -27.5, -.55, 4.0)
# strings (first violins left, seconds left of centre, violas right of centre, cellos and basses right)
track('vn1', 'Violins I', 'melody', 'vsco_strings', 0, 40, 48, 'G3', 'F#6', -20.5, -.5, 1.5, offset=-90, bus='lead')
track('vn1s', 'Violins I spiccato', 'rhythm', 'vsco_strings', 1, 40, 48, 'G3', 'F#6', -22.5, -.5, 1.5, offset=-35, gate=.9)
track('vn2', 'Violins II', 'harmony', 'vsco_strings', 0, 40, 48, 'G3', 'F#6', -22.5, -.22, 2.0, offset=-90)
track('vn2s', 'Violins II spiccato', 'rhythm', 'vsco_strings', 1, 40, 48, 'G3', 'F#6', -23.0, -.22, 2.0, offset=-35, gate=.9)
track('vnt', 'Violins I-II tremolo', 'texture', 'vsco_strings', 0, 44, 44, 'G3', 'F#6', -25.0, -.36, 1.8, offset=-60)
track('va', 'Violas', 'harmony', 'vsco_strings', 0, 41, 48, 'C3', 'F#6', -23.0, .2, 2.5, offset=-90)
track('vas', 'Violas spiccato', 'rhythm', 'vsco_strings', 1, 41, 48, 'C3', 'F#6', -23.0, .2, 2.5, offset=-35, gate=.9)
track('vat', 'Violas tremolo', 'texture', 'vsco_strings', 0, 45, 44, 'C3', 'F#6', -26.0, .2, 2.5, offset=-60)
track('vc', 'Cellos', 'harmony', 'vsco_strings', 0, 42, 48, 'C2', 'A5', -22.0, .45, 2.5, offset=-90)
track('vcs', 'Cellos spiccato', 'rhythm', 'vsco_strings', 1, 42, 48, 'C2', 'A5', -22.0, .45, 2.5, offset=-35, gate=.9)
track('cb', 'Double basses', 'bass', 'vsco_extra', 0, 43, 43, 'E1', 'D4', -22.5, .6, 3.5, highpass=20)
track('cbs', 'Double basses spiccato', 'bass', 'vsco_extra', 2, 43, 43, 'E1', 'D4', -22.5, .6, 3.5, gate=.9, highpass=20)
track('cbp', 'Double basses pizzicato', 'bass', 'vsco_extra', 3, 43, 43, 'E1', 'D4', -27.0, .6, 3.5, highpass=20)

# Levels (round 2).  Round 1 levelled each part from its louder half-seconds (active_rms), which lifted the parts
# that mostly play softly: violas, cellos, basses, third trombone and tuba came out level with the tune, and the low
# brass set the master's peak.  From round 2 every part is levelled by its peak, its loudest moment, so a change
# of dynamics in a soft passage no longer moves the part's tutti level.  The figures are round 1's measured stem
# peaks, 8 dB down, with these changes: timpani +6, bass drum +5, cymbals +4, horns' theme +1.5, piccolo and
# tremolo violins +1; violas -6, third trombone -5, cellos, basses and tuba -4, second violins -3.5, short
# trombones -2.5, first violins, bassoons and harp -2, flutes, short trumpets, staccato bassoons, spiccato violas
# and cellos, staccato tuba -1, spiccato basses -1.5.
PEAK = {'picc': -20.8, 'fl': -16.7, 'fls': -16.9, 'ob': -16.6, 'obs': -15.4, 'cl': -16.7, 'cls': -14.8, 'bn': -16.0,
        'bns': -18.7, 'hn_t': -12.5, 'hn12': -13.4, 'hn34': -14.3, 'tp': -11.3, 'tps': -11.7, 'tb': -8.3, 'tbs': -8.4,
        'tb3': -10.0, 'tuba': -11.4, 'tubas': -11.5, 'timp': -14.3, 'bd': -15.0, 'cym': -18.7, 'harp': -19.7,
        'vn1': -13.3, 'vn1s': -12.3, 'vn2': -10.7, 'vn2s': -15.2, 'vnt': -13.3, 'va': -13.6, 'vas': -14.7,
        'vat': -11.6, 'vc': -10.9, 'vcs': -13.1, 'cb': -13.9, 'cbs': -12.8, 'cbp': -19.0}
# Round 3, from round 2's stem levels per section (a peak level moves a part by exactly its change):
# - the brass theme over everything in the tuttis: trumpets +1.5, horns' theme +2, trombones +1, horns +1;
#   third trombone +3 and tuba +1 (round 2 took them further down than meant);
# - flutes -4 and clarinets -3 (in the coda and the development the two flutes measured over the two trumpets),
#   oboes -1; the staccato woodwinds that answer the strings in the fugato up: clarinets +8, flutes +6, oboes
#   and bassoons +3;
# - the figure under the brass: spiccato cellos and basses -3, violas and first violins -1;
# - violins under the brass in the return: firsts -1, seconds -2; violas (accompaniment only) -3;
# - percussion: cymbals +4, bass drum +1.5, timpani +1; harp +3.
ROUND3 = {'fl': -4, 'fls': 6, 'ob': -1, 'obs': 3, 'cl': -3, 'cls': 8, 'bns': 3, 'hn_t': 2, 'hn12': 1, 'hn34': 1,
          'tp': 1.5, 'tb': 1, 'tb3': 3, 'tuba': 1, 'timp': 1, 'bd': 1.5, 'cym': 4, 'harp': 3, 'vn1': -1, 'vn1s': -1,
          'vn2': -2, 'va': -3, 'vas': -1, 'vcs': -3, 'cbs': -3}
for _tid, _change in ROUND3.items():
    PEAK[_tid] = round(PEAK[_tid] + _change, 1)
# Round 4, from round 3's figures: the staccato flutes, clarinets and oboes, raised for the fugato, came out at the
# trumpets' level in the tutti strokes, so their strokes are written softer (STROKE below) and the parts lowered
# with them; staccato bassoons -2 (level with the cellos they double); third trombone -1.5 (it set the peak).
ROUND4 = {'fls': -4, 'cls': -3, 'obs': -2, 'bns': -2, 'tb3': -1.5}
for _tid, _change in ROUND4.items():
    PEAK[_tid] = round(PEAK[_tid] + _change, 1)
# Round 5: spiccato first violins -1.5 (their figure measured 2 dB under the trumpets in the coda).
PEAK['vn1s'] = round(PEAK['vn1s'] - 1.5, 1)
STROKE = {'fls': -20, 'cls': -14, 'obs': -10}   # velocity change of these parts in a tutti stroke
for _tid, _level in PEAK.items():
    TR[_tid]['mix']['level_dbfs'] = _level
    TR[_tid]['mix']['level_mode'] = 'peak'

# Round 4: a little presence and air on the violins.  In round 3 the dry ensemble bus held 2.8% of its power above
# 2.5 kHz and 0.03% above 6 kHz in the return (the hall's return the same: the hall is not what darkens the mix),
# and the master's top end sat 4 dB under the skill's orchestral reference.
for _tid in ('vn1', 'vn1s', 'vn2', 'vn2s', 'vnt'):
    TR[_tid]['mix']['eq'] = [[5000, 1.5], [9000, 2.5]]

BD, CLASH, GONG, SWELL_3S7 = 36, 49, 52, 29   # keys of the orchestra kit

PP, P_, MP, MF, F, FF, FFF = 40, 54, 66, 80, 98, 112, 123

# ------------------------------------------------------------------ 3. the music
# The low strings' driving figure: the open pedal on the beats, an upper line on the off-beats that
# rocks from the fifth to the sixth above it (in E minor: B, C, B - the opening gesture's turn).
FIG = {'E': ('E2', 'B2', 'C3'), 'A': ('A2', 'E3', 'F3'), 'C': ('C3', 'G3', 'A3'), 'B': ('B2', 'F#3', 'G3'),
       'F#': ('F#2', 'C3', 'E3'), 'Em/B': ('B2', 'E3', 'G3'), 'F/A': ('A2', 'F3', 'C3'), 'Am/E': ('E2', 'A2', 'C3'),
       'B7': ('B2', 'F#3', 'A3')}
THIRD = {'E': 'G2', 'A': 'C3', 'C': 'E3', 'B': 'D#3', 'F#': 'A2', 'Em/B': 'G3', 'F/A': 'C3', 'Am/E': 'C3', 'B7': 'D#3'}
VN1 = {'E': ('G4', 'E5'), 'A': ('C5', 'A5'), 'C': ('E5', 'C6'), 'B': ('D#5', 'B5'), 'F#': ('A4', 'E5'),
       'Em/B': ('E5', 'B5'), 'F/A': ('C5', 'A5'), 'Am/E': ('C5', 'A5'), 'B7': ('D#5', 'B5')}
PEDAL = {'E': 'E1', 'A': 'A1', 'C': 'C2', 'B': 'B1', 'F#': 'F#1', 'Em/B': 'B1', 'Em/B>B7': 'B1', 'F/A': 'A1',
         'Am/E': 'E1', 'B7': 'B1'}


def figure(key, last=None, upper=False):
    if key == 'Em/B>B7':   # the cadential six-four for two beats, then the dominant seventh
        pat = 'B2 E3 B2 G3 B2 F#3 B2'.split() + ['D#3' if upper else 'F#3']
        if last:
            pat[7] = last
        return pat
    r, f, s = FIG[key]
    x = THIRD[key] if upper else s
    pat = [r, f, r, x, r, f, r, f]
    if last:
        pat[7] = last
    return pat


def pedal(b, name, vel):
    """The basses under the figure: its pedal note alone, short, on the four beats (where the cellos have it too)."""
    for i in range(4):
        on = bar(b) + i
        add('cbs', on, .5, P(name), (vel(on) if callable(vel) else vel) + (8 if i == 0 else 2 if i == 2 else -2))


def drive(b, key, vel, last=None, parts=('vcs', 'cbs', 'bns'), vn1_last=None):
    """One bar of the driving figure.  Cellos (and bassoons) play it as written; the basses strike its pedal note on
    the beats an octave below (the whole figure there put fourths, thirds and tenths under the cellos, timpani and
    tuba); violas and second violins play it above with the chord's third in place of the sixth; first violins in
    thirds and fourths over the seconds."""
    for tid in parts:
        if tid in ('vcs', 'bns'):
            eighths(tid, b, figure(key, last), vel)
        elif tid == 'cbs':
            pedal(b, PEDAL[key], vel)
        elif tid == 'vas':
            eighths('vas', b, figure(key, last, upper=True), vel, tr=12)
        elif tid == 'vn2s':
            eighths('vn2s', b, figure(key, last, upper=True), vel, tr=24)
        elif tid == 'vn1s':
            x, y = VN1['Em/B' if key == 'Em/B>B7' else key]
            pat = [x, y] * 4
            if key == 'Em/B>B7':
                pat[4], pat[6] = 'D#5', 'D#5'
            if vn1_last:
                pat[6], pat[7] = vn1_last
            eighths('vn1s', b, pat, vel, accent=(0, 4))


def tpat(b, hits, vel):
    """Timpani strokes in bar b: (beat in the bar, pitch, velocity change)."""
    for pos, name, dv in hits:
        add('timp', bar(b) + pos, .5, P(name), (vel(bar(b) + pos) if callable(vel) else vel) + dv)


TIMP_A = lambda p: [(0, p, 8), (2, p, -2), (2.5, p, -6), (3, p, 2)]            # long, short-short-long
TIMP_B = lambda p, q: [(0, p, 8), (2, q, 0), (2.5, q, -5), (3, q, 3)]          # ... turning to the dominant
TIMP_C = lambda p: [(0, p, 8), (2, p, -2), (3, p, 2)]                          # without the off-beat stroke
# (the timpani have E, A and B, and G, D, F and B flat for the middle of the piece; where the bass is on another
#  note they rest: under a C or an F sharp their E or A made a low third)


def horn_rhythm(b, hn12, hn34, vel, hn12b=None, hn34b=None):
    """Horns on the timpani's rhythm: a chord on 1, then on 3, 3-and, 4 (the second half may change chord)."""
    for pos, d in ((0, 1), (2, .5), (2.5, .5), (3, .5)):
        a, c = (hn12b or hn12, hn34b or hn34) if pos >= 2 else (hn12, hn34)
        v = (vel(bar(b) + pos) if callable(vel) else vel) + (4 if pos == 0 else -2)
        for tid, names in (('hn12', a), ('hn34', c)):
            if names:
                for nm in names.split('+'):
                    add(tid, bar(b) + pos, d, P(nm), v, gate=.8)


def low_brass(b, tbs, tuba, vel, beats=(0, 2)):
    """Trombones and tuba, short, on the strong beats."""
    for pos in beats:
        v = (vel(bar(b) + pos) if callable(vel) else vel) + (4 if pos == 0 else 0)
        for nm in tbs.split('+'):
            add('tbs', bar(b) + pos, .5, P(nm), v)
        add('tubas', bar(b) + pos, .5, P(tuba), v)


def gesture(b0, vel, full=False):
    """The opening gesture, three bars: a bare E struck by everyone; B rising to C in octaves; the C held in the
    bass while the top falls to A sharp (an augmented sixth, C-E-G-A#), swelling; and its resolution, a bare B."""
    s = bar(b0)
    H(b0, 'Em')
    hit(s, {'vn1s': 'E5', 'vn2s': 'E4', 'vas': 'E3', 'vcs': 'E2', 'cbs': 'E1', 'fls': 'E5+E6', 'obs': 'E4+E5',
            'cls': 'E4+E5', 'bns': 'E2+E3', 'tps': 'E4+E5', 'hn12': 'E4', 'hn34': 'E3', 'tbs': 'E2+E3', 'tubas': 'E2',
            'timp': 'E2'}, vel)
    add('bd', s, 1, BD, vel)
    if full:
        add('cym', s, 1, CLASH, vel - 4)
        add('cym', s, 1, GONG, vel - 14)
        add('picc', s, .5, P('E7'), vel - 6, gate=.6)
    # B (dotted quarter) to C (eighth): brass and woodwinds sustained, strings struck
    for spec in ('tp:0', 'hn_t:-12', 'hn34:-24', 'tb:-12', 'tb3:-24', 'tuba:-36', 'cl:-12', 'ob:0', 'fl:12'):
        tid, tr = spec.split(':')
        at(tid, s + 2, 'B4:1.5 C5:.5', vel - 4, int(tr), gate=.95)
    at('bn', s + 2, 'B1+B2:1.5 C2+C3:.5', vel - 4, gate=.95)
    for tid, tr in (('vn1s', 12), ('vn2s', 0), ('vas', -12), ('vcs', -24), ('cbs', -36)):
        at(tid, s + 2, 'B4:1.5 C5:.5', vel, tr)
    add('timp', s + 2, .5, P('B2'), vel - 8)
    if full:
        at('picc', s + 2, 'B6:1.5 C7:.5', vel - 10)
    # the augmented sixth, held a bar: fp, then a crescendo into the stroke
    H(b0 + 1, 'C7')
    chord = {'tp': 'E4+A#4', 'hn_t': 'A#3+E4', 'hn34': 'G3+C4', 'tb': 'E3+G3', 'tb3': 'C3', 'tuba': 'C2',
             'bn': 'C2+C3', 'cl': 'E4+G4', 'ob': 'G4+A#4', 'fl': 'G5+A#5', 'vnt': 'A#4+A#5', 'vat': 'E4+G4',
             'vc': 'C3', 'cb': 'C2'}
    if full:
        chord['picc'] = 'A#6'
    for tid, names in chord.items():
        for nm in names.split('+'):
            add(tid, s + 4, 4, P(nm), vel - 2, gate=1.0)
        dyn(tid, (s + 4, vel - 2), (s + 4.45, vel - 40), (s + 6, vel - 24), (s + 7.9, min(127, vel + 8)))
    roll('timp', s + 4, 4, 'E2', vel - 50, vel + 4)
    # the resolution: B in bare octaves, then silence
    H(b0 + 2, 'B5')
    hit(s + 8, {'vn1s': 'B5', 'vn2s': 'B4', 'vas': 'B3', 'vcs': 'B2', 'cbs': 'B1', 'fls': 'B5+B6', 'obs': 'B4+B5',
                'cls': 'B3+B4', 'bns': 'B1+B2', 'tps': 'B3+B4', 'hn12': 'B3', 'hn34': 'B2', 'tbs': 'B2+B3',
                'tubas': 'B1', 'timp': 'B2'}, min(127, vel + 4))
    add('bd', s + 8, 1, BD, min(127, vel + 4))
    if full:
        add('picc', s + 8, .5, P('B6'), vel - 4, gate=.6)


T1 = ('E4:2 B4:1.5 C5:.5 | B4:3 r:1 | A4:2 E5:1.5 F5:.5 | E5:3 r:1 | '
      'E5:1.5 D5:.5 C5:1 G4:1 | C5:1.5 B4:.5 A4:1 E4:1 | B4:1.5 G4:.5 E4:1 F#4:1 | B4:3 r:1')
T1_HEAD = 'E4:2 B4:1.5 C5:.5 | B4:3 r:1 | A4:2 E5:1.5 F5:.5 | E5:3 r:1 |'
T1_CADENCE = 'E5:1.5 D5:.5 C5:1 E5:1 | F#5:2 A5:1.5 G5:.5 | E5:2 F#5:1.5 D#5:.5 |'


def sec_gesture():
    gesture(1, FF + 6)


def sec_drive():
    # bars 4-5: the figure alone, cellos and basses with the timpani
    v = ramp([(bar(4), MF), (bar(6), F)])
    drive(4, 'E', v, parts=('vcs', 'cbs'))
    drive(5, 'E', v, last='A#2', parts=('vcs', 'cbs', 'bns'))
    tpat(4, TIMP_A('E2'), MF)
    tpat(5, TIMP_B('E2', 'B2'), MF + 8)
    for b, sym in ((4, 'Em'), (8, 'Am'), (10, 'C'), (11, 'Am'), (12, 'Em/B'), (13, 'B'), (14, 'Em'), (16, 'Am'),
                   (18, 'C'), (19, 'F#m7b5'), (20, 'Em/B'), (21, 'Em')):
        H(b, sym)
    H(12, 'B7', 3)
    H(20, 'B7', 2)
    # bars 6-13: the first theme in the four horns (octaves) over the figure
    v = ramp([(bar(6), F + 6), (bar(10), FF - 2), (bar(13), FF + 4)])
    vf = lambda x: v(x) - 12   # the figure a dynamic under the brass (round 1: the cellos measured level with the horns)
    L('hn_t', 6, T1, v)
    L('hn34', 6, T1, v, tr=-12, dv=-4)
    L('tp', 10, 'E5:1.5 D5:.5 C5:1 G4:1 | C5:1.5 B4:.5 A4:1 E4:1 | B4:1.5 G4:.5 E4:1 F#4:1 | B4:3 r:1', v, dv=-6)
    keys = [(6, 'E', None), (7, 'E', 'G#2'), (8, 'A', None), (9, 'A', 'B2'), (10, 'C', 'B2'), (11, 'A', 'A#2'),
            (12, 'B', None), (13, 'B', 'D#3')]
    for b, key, last in keys:
        drive(b, key, vf, last=last, parts=('vcs', 'cbs', 'bns') + (('vas',) if b >= 10 else ()))
    tpat(6, TIMP_A('E2'), F)
    tpat(7, TIMP_B('E2', 'B2'), F)
    tpat(8, TIMP_A('A2'), F)
    tpat(9, TIMP_A('A2'), F)
    tpat(11, [(0, 'A2', 4), (2, 'A2', -4)], F)
    tpat(12, TIMP_A('B2'), F + 4)
    roll('timp', bar(13), 4, 'B2', F - 16, FF + 6)
    low_brass(10, 'C3+G3', 'C2', F)
    low_brass(11, 'A2+E3', 'A1', F)
    low_brass(12, 'B2+E3', 'B1', F + 4, beats=(0,))
    low_brass(12, 'B2+F#3', 'B1', F + 4, beats=(3,))
    low_brass(13, 'B2+F#3', 'B1', FF)
    L('vnt', 12, 'B4+B5:4 | B4+B5:4', MF)
    dyn('vnt', (bar(12), P_), (bar(13), MF + 4), (bar(14) - .1, FF))
    add('bd', bar(10), 1, BD, F - 8)
    # bars 14-21: the theme again, trumpets and trombones in octaves with the woodwinds, the whole string
    # section on the figure, the horns on the timpani's rhythm; a full cadence in E minor
    v = lambda _: FF + 4
    m2 = T1_HEAD + ' ' + T1_CADENCE + ' E5:3 r:1'
    ML('tp:0 tb:-12/-2 fl:12/-6 ob:0/-6 cl:0/-8', 14, m2, v)
    keys = [(14, 'E', None), (15, 'E', 'G#2'), (16, 'A', None), (17, 'A', 'B2'), (18, 'C', None), (19, 'F#', 'A2'),
            (20, 'B', None), (21, 'E', None)]
    for b, key, last in keys:
        vl = ('C5', 'G5') if (b, key) == (17, 'A') else None
        drive(b, 'Em/B>B7' if b == 20 else key, FF - 10, last=last, parts=('vcs', 'cbs', 'bns', 'vas', 'vn2s', 'vn1s'),
              vn1_last=vl)
    chords = {14: ('G4+B4', 'B3+E4'), 15: ('G4+B4', 'B3+E4'), 16: ('A4+C5', 'A3+E4'), 17: ('A4+C5', 'A3+E4'),
              18: ('G4+C5', 'C4+E4'), 19: ('A4+C5', 'C4+E4'), 21: ('G4+B4', 'B3+E4')}
    for b, (a, c) in chords.items():
        horn_rhythm(b, a, c, FF - 10)
    horn_rhythm(20, 'G4+B4', 'B3+E4', FF - 8, 'F#4+A4', 'B3+D#4')
    for b, (tbs, tu) in {14: ('E3', 'E2'), 15: ('E3', 'E2'), 16: ('A2', 'A1'), 17: ('A2', 'A1'), 18: ('C3', 'C2'),
                         19: ('F#2', 'F#1'), 20: ('B2', 'B1'), 21: ('E3', 'E2')}.items():
        low_brass(b, tbs, tu, FF - 8)
    tpat(14, TIMP_A('E2'), FF)
    tpat(15, TIMP_B('E2', 'B2'), FF)
    tpat(16, TIMP_A('A2'), FF)
    tpat(17, TIMP_A('A2'), FF)
    roll('timp', bar(20), 4, 'B2', F, FFF)
    tpat(21, TIMP_A('E2'), FF + 6)
    for b, dv in ((14, 0), (16, -8), (18, -4), (21, 6)):
        add('bd', bar(b), 1, BD, FF - 6 + dv)


def sec_bridge():
    """Bars 22-31: the figure thins out over the tonic, the woodwinds turn the gesture's B-C-B into B-C-D,
    and the harmony settles on D, the dominant of G major, as the tempo broadens."""
    for b, sym in ((22, 'Em'), (25, 'G/D'), (26, 'D7'), (27, 'G/D'), (28, 'D7'), (29, 'D9sus4'), (30, 'D7')):
        H(b, sym)
    v = ramp([(bar(22), F - 2), (bar(25), MP + 6)])   # (round 4: the figure fades less far; the bridge measured 16 LU under the return)
    drive(22, 'E', v, parts=('vcs', 'vas'))
    drive(23, 'E', v, parts=('vcs', 'vas'))
    drive(24, 'E', v, parts=('vcs',))
    for b in (22, 23, 24):
        add('cbs', bar(b), .5, P('E1'), v(bar(b)) + 4)
        add('cbs', bar(b) + 2, .5, P('E1'), v(bar(b)) - 4)
    tpat(22, [(0, 'E2', 0)], MF)
    tpat(23, [(0, 'E2', 0)], P_ + 4)
    # the gesture's turn, echoed: clarinets and bassoons, then oboes and flutes opening it upward
    # (round 3: the woodwind lines a dynamic up and the held strings one down; round 2 measured the lines 6-8 dB
    #  under the strings that only hold the chord, and the harp 15 dB under them)
    ML('cl:0 bn:0/-2', 22, 'r:2 B3:1.5 C4:.5 | B3:3 r:1', F + 6)
    ML('ob:0 fl:12/-4', 24, 'r:2 B4:1.5 C5:.5 | D5:3 r:1', F)
    # the pedal on D: strings sustained, horns, a soft timpani stroke every other bar
    pp = ramp([(bar(25), PP + 6), (bar(28), PP + 2), (bar(32), PP - 6)])
    L('vc', 25, 'D3:4 | D3:8 | D3:8 | D3:8', pp)
    L('cb', 25, 'D2:4 | D2:8 | D2:8 | D2:8', pp)
    L('va', 25, 'B3:4 | C4:4 | B3:4 | C4:4 | C4:4 | C4:8', pp)
    L('vn2', 25, 'G4:4 | F#4:4 | G4:4 | F#4:4 | G4:4 | F#4:8', pp)
    L('hn12', 26, 'A3+D4:8 | A3+D4:8 | A3+D4:8', PP)
    for b in (26, 28, 30):
        tpat(b, [(0, 'D3', 0)], PP + 4)
    ML('cl:0 bn:0/-2', 26, 'r:2 D4:1.5 E4:.5 | D4:3 r:1', MF + 10)
    ML('fl:12 ob:0/-2', 28, 'r:2 A4:1.5 B4:.5 | C5:3 r:1', MF + 8)
    # the harp rises through the dominant seventh to D, the note the theme begins on
    L('harp', 30, 'D3:1 A3:1 C4:1 F#4:1 | A4:1 C5:1 D5:2', ramp([(bar(30), F - 6), (bar(32), F + 6)]))


# ---- the singing theme (G major, then B flat major): bars 32-59, t1 = bar 32
TB = 31
THEME_A = ('D5:3 B4:1 | G4:2 E5:2 | E5:1 D5:1 C5:1.5 B4:.5 | A4:3 r:1 | '
           'D5:3 B4:1 | G4:2 F#5:2 | G5:1.5 F#5:.5 E5:1 C#5:1 | D5:3 r:1')
THEME_C = ('D5:3 B4:1 | G4:2 E5:2 | E5:1 F#5:1 G5:1.5 A5:.5 | C6:1 B5:2 G5:1 | '
           'A5:1.5 G5:.5 E5:1 C5:1 | B4:1 D5:1 A5:1.5 F#5:.5 | G5:3 r:1')
THEME_BB = ('F5:3 D5:1 | Bb4:2 G5:2 | G5:1 A5:1 Bb5:1.5 C6:.5 | Eb6:1 D6:2 Bb5:1 | '
            'C6:1.5 Bb5:.5 G5:1 Eb5:1 | D5:1 F5:1 C6:1.5 A5:.5 |')
ARP = {'G': 'G2 D3 G3 B3 D4 B3 G3 D3', 'G/B': 'B2 G3 B3 D4', 'C': 'C3 G3 C4 E4', 'Am': 'A2 E3 A3 C4',
       'C#dim7': 'C#3 G3 Bb3 E4', 'G/D': 'D3 G3 B3 D4 G4 D4 B3 G3', 'Em': 'E3 B3 E4 G4', 'D7': 'D3 A3 C4 F#4',
       'F7': 'F2 C3 Eb3 A3', 'G5': 'G2 D3 G3 D4', 'Bb': 'Bb2 F3 Bb3 D4 F4 D4 Bb3 F3', 'Bb/D': 'D3 Bb3 D4 F4', 'Eb': 'Eb3 Bb3 Eb4 G4',
       'Edim7': 'E3 Bb3 Db4 G4', 'Bb/F': 'F3 Bb3 D4 F4 Bb4 F4 D4 Bb3', 'Gm': 'G2 D3 G3 Bb3', 'Cm': 'C3 G3 C4 Eb4',
       'G/Dh': 'D3 G3 B3 D4'}


def harp_bar(t, chords, vel):
    """Harp arpeggios in eighths for theme bar t: one chord for the bar, or two for its halves."""
    on = bar(TB + t)
    for k, sym in enumerate(chords):
        names = ARP[sym].split()
        if len(chords) == 2:
            names = names[:4]
        for i, nm in enumerate(names):
            o = on + 2 * k + i * .5
            add('harp', o, .5 if i < len(names) - 1 else .5, P(nm), (vel(o) if callable(vel) else vel) + (5 if i == 0 else 0))


def sec_theme():
    t = lambda k: TB + k
    for k, syms in enumerate(['G', 'G/B C', 'C Am', 'D', 'G/B', 'C B7', 'Em A7', 'D',
                              'G', 'G/B C', 'C C#dim7', 'G/D', 'Em Am', 'G/D D7', 'G', 'G F7',
                              'Bb', 'Bb/D Eb', 'Eb Edim7', 'Bb/F', 'Gm Cm', 'Bb/F F7',
                              'Gm', 'Gm', 'Gm Eb', 'Eb7', 'D', 'D'], start=1):
        for j, sym in enumerate(syms.split()):
            H(t(k), sym, 2 * j)
    # --- t1-t8: the first violins alone on the tune, the other strings under them, basses plucked
    v = ramp([(bar(t(1)), MF + 4), (bar(t(5)), MF + 8), (bar(t(7)), F), (bar(t(8)), MF + 6), (bar(t(9)), MF + 8)])
    L('vn1', t(1), THEME_A, v)
    # the tune well over what carries it (round 1: second violins and violas within 2 dB of it; round 2: 3.5 dB)
    acc = lambda x: v(x) - 50
    L('vn2', t(1), 'G4:4 | D4:2 E4:2 | E4:4 | F#4:4 | G4:4 | E4:2 D#4:2 | E4:4 | D4:4', acc)
    L('va', t(1), 'B3:4 | G3:4 | G3:2 A3:2 | A3:4 | G3:4 | G3:2 A3:2 | G3:4 | F#3:4', acc)
    L('vc', t(1), 'G2:4 | B2:2 C3:2 | C3:2 A2:2 | D3:2 D2:2 | B2:4 | C3:2 B2:2 | E3:2 A2:2 | D3:2 D2:2', acc, dv=18)
    for k, hits in enumerate(['G1', 'B1 C2', 'C2 A1', 'D2', 'B1', 'C2 B1', 'E2 A1', 'D2'], start=1):
        for j, nm in enumerate(hits.split()):
            add('cbp', bar(t(k)) + 2 * j, 1, P(nm), MP + 4)
    L('cl', t(4), 'F#4+A4:3 r:1', P_)
    L('cl', t(8), 'D4+F#4:3 r:1', P_)
    L('bn', t(8), 'D3:3 r:1', P_)
    # --- t9-t16: the tune again and on to its peak: first violins, with second violins and cellos an octave
    #     under them (round 3: the seconds leave the harmony for the tune), flute and oboe joining at the climb;
    #     violas, clarinets and horns hold the harmony, harp, the bass line bowed
    v = ramp([(bar(t(9)), MF + 8), (bar(t(11)), F - 2), (bar(t(12)), F + 8), (bar(t(13)), F + 4), (bar(t(15)), MF + 8),
              (bar(t(17)), MF + 8)])
    L('vn1', t(9), THEME_C, v)
    L('vn2', t(9), THEME_C, v, tr=-12, dv=-8)
    L('vc', t(9), THEME_C, v, tr=-12, dv=-8)
    acc = lambda x: v(x) - 46
    upper = 'G4:4 | D4:2 E4:2 | E4:4 | G4:4 | G4:2 E4:2 | G4:2 F#4:2 | G4:4 | G4:2 A4:2'
    va = 'B3:4 | G3:4 | G3:2 Bb3:2 | D4:4 | B3:2 C4:2 | B3:2 C4:2 | B3:4 | G3:2 C4:2'
    L('vn2', t(16), 'G4:2 A4:2', acc)
    L('va', t(9), va, acc, dv=4)
    L('cl', t(9), upper, acc, dv=8)
    L('cl', t(9), va, acc, dv=4)
    bass = 'G2:4 | B2:2 C3:2 | C3:2 C#3:2 | D3:4 | E3:2 A2:2 | D3:4 | G2:4 | G2:2 F2:2'
    L('cb', t(9), bass, acc, tr=-12, dv=22)
    L('bn', t(9), bass, acc, dv=14)
    L('hn12', t(9), 'G3+D4:4 | G3+D4:2 G3+E4:2 | G3+E4:4 | G3+D4:4 | G3+E4:2 A3+E4:2 | G3+D4:2 A3+D4:2 | '
                    'G3+D4:4 | G3+D4:2 A3+C4:2', lambda x: acc(x) + 12)
    ML('fl:0/-8 ob:-12/-10', t(11), 'E5:1 F#5:1 G5:1.5 A5:.5 | C6:1 B5:2 G5:1 | A5:1.5 G5:.5 E5:1 C5:1', v)
    for k, ch in enumerate(['G', 'G/B C', 'C C#dim7', 'G/D', 'Em Am', 'G/Dh D7', 'G', 'G5 F7'], start=9):
        harp_bar(k, ch.split(), lambda x: acc(x) + 28)
    ML('fl:0 ob:-12/-3', t(16), 'B4:1 C5:1 D5:1 Eb5:1', MF)
    tpat(t(15), [(0, 'G2', 0)], MP)
    # --- t17-t22: the tune a minor third higher, in B flat, by the whole orchestra: violins in octaves with
    #     flutes and oboes, cellos on a line of their own, horns and trombones in chords, timpani at the peak
    v = ramp([(bar(t(17)), F - 2), (bar(t(19)), F + 4), (bar(t(20)), FF), (bar(t(21)), F + 2), (bar(t(22)), F - 4),
              (bar(t(23)), MF)])
    ML('vn1:0 vn2:-12 fl:0/-8 ob:-12/-10', t(17), THEME_BB, v)
    acc = lambda x: v(x) - 28   # round 1: violas and cellos measured over the tune here, the horns 2 dB under it
    L('vc', t(17), 'Bb3:1 C4:1 D4:1 F4:1 | F4:2 G4:1 Eb4:1 | Bb3:2 Db4:2 | Bb3:1 D4:1 F4:1 D4:1 | '
                   'D4:1 Bb3:1 C4:1 Eb4:1 | D4:2 Eb4:1 C4:1', lambda x: v(x) - 22)
    L('va', t(17), 'D4:1 F4:1 D4:1 F4:1 | D4:1 F4:1 Eb4:1 G4:1 | Eb4:1 G4:1 Db4:1 G4:1 | Bb3:1 F4:1 D4:1 F4:1 | '
                   'D4:1 G4:1 Eb4:1 G4:1 | D4:1 F4:1 Eb4:1 F4:1', acc)
    bass = 'Bb2:4 | D3:2 Eb3:2 | Eb3:2 E3:2 | F3:4 | G3:2 C3:2 | F3:2 F2:2'
    L('cb', t(17), bass, acc, tr=-12, dv=14)
    L('bn', t(17), bass, acc, dv=8)
    L('tuba', t(17), 'Bb1:4 | D2:2 Eb2:2 | Eb2:2 E2:2 | F2:4 | G2:2 C2:2 | F2:4', acc, dv=-2)
    L('hn12', t(17), 'D4+F4:4 | D4+F4:2 Eb4+G4:2 | Eb4+G4:2 Db4+G4:2 | F4+Bb4:4 | D4+G4:2 Eb4+G4:2 | D4+F4:2 Eb4+F4:2',
      lambda x: acc(x) + 4)
    L('hn34', t(17), 'F3+Bb3:4 | F3+Bb3:2 G3+Bb3:2 | G3+Bb3:4 | F3+Bb3:4 | G3+Bb3:2 G3+C4:2 | F3+Bb3:2 F3+A3:2',
      lambda x: acc(x) + 4)
    L('cl', t(17), 'D4+F4:4 | D4+F4:2 Eb4+G4:2 | Eb4+G4:2 Db4+G4:2 | F4+Bb4:4 | D4+G4:2 Eb4+G4:2 | D4+F4:2 Eb4+F4:2', acc)
    L('tb', t(20), 'F3+Bb3:4 | G3+Bb3:2 G3+C4:2 | F3+D4:2 A3+Eb4:2', acc)
    L('tb3', t(20), 'F2:4 | G2:2 C3:2 | F2:4', acc)
    for k, ch in enumerate(['Bb', 'Bb/D Eb', 'Eb Edim7', 'Bb/F', 'Gm Cm', 'Bb/F F7'], start=17):
        harp_bar(k, ch.split(), lambda x: v(x) - 26)   # (round 3's harp measured 1 dB under the violins, round 4's 14.5)
    roll('timp', bar(t(19)), 4, 'Bb2', PP + 6, MF + 8, step=1 / 6)   # B flat is in both chords of the bar
    tpat(t(20), [(0, 'F2', 0)], F)   # with the bass
    roll('timp', bar(t(22)) + 2, 2, 'F2', MP, MF, step=1 / 6)
    # --- t23-t28: the cadence turns aside to G minor; violas, clarinets and bassoons give the tune's first notes
    #     in the minor (D, B flat, G, E flat), and E flat falls through C sharp to D: the gesture's turn again
    v = ramp([(bar(t(23)), MF + 4), (bar(t(24)), MP + 8), (bar(t(27)), MP - 4), (bar(t(29)), PP)])
    L('vn1', t(23), 'Bb5:4', v)
    # (round 3: the held strings under the tune in violas, clarinets and bassoons; round 2 measured them level)
    # (round 5: again; in round 4 the three parts on the tune together measured level with these two)
    L('vn2', t(23), 'Bb4:4 | G4:4 | G4:4 | G4:4 | F#4:8', lambda x: v(x) - 34)
    L('va', t(23), 'D4:4', lambda x: v(x) - 8)
    L('vc', t(23), 'G3:4 | G2:4 | G2:2 Eb2:2 | Eb2:4 | D2:8', lambda x: v(x) - 28)
    L('cb', t(23), 'G1:4', lambda x: v(x) - 6)
    L('cb', t(27), 'D2:8', lambda x: v(x) - 6)
    L('hn12', t(23), 'D4+G4:4', lambda x: v(x) - 12)
    L('hn34', t(23), 'G3+Bb3:4 | r:4 | r:4 | G3+Bb3:4 | F#3+A3:8', lambda x: v(x) - 12)
    tpat(t(23), [(0, 'G2', 0)], MP)
    ML('va:0 cl:0 bn:0/-2', t(24), 'D4:3 Bb3:1 | G3:2 Eb4:2 | Eb4:2 C#4:2 | D4:8', lambda x: v(x) + 16)
    for k, nm in ((24, 'G1'), (25, 'G1'), (26, 'Eb2')):
        add('cbp', bar(t(k)), 1, P(nm), MP - 6)
    add('cbp', bar(t(25)) + 2, 1, P('Eb2'), MP - 8)
    roll('timp', bar(t(27)), 6, 'D2', PP + 6, PP - 14, step=1 / 6)


# ---- the fugato (G minor): bars 60-77
SUBJ = 'G3:1 D4:1.5 Eb4:.5 C#4:1 | D4:.5 Bb3:.5 A3:.5 G3:.5 C4:.5 A3:.5 G3:.5 F#3:.5 | G3:.5 A3:.5 Bb3:.5 C4:.5 D4:1 r:1'
CSUB = 'r:1 F3:.5 G3:.5 A3:.5 D3:.5 E3:1 | A3:1.5 A3:.5 A3:1 G3:1 | F3:.5 E3:.5 D3:.5 C#3:.5 D3:1 r:1'   # in D minor


def sec_fugato():
    for b, sym, beat in ((60, 'Gm', 0), (60, 'A7/C#', 3), (61, 'Gm/D', 0), (61, 'D7', 2), (62, 'Gm', 0), (62, 'D', 2),
                         (63, 'Dm', 0), (63, 'E7', 3), (64, 'Dm/A', 0), (64, 'A7', 2), (65, 'Dm', 0), (66, 'D7', 0),
                         (67, 'Gm', 0), (67, 'Bb/D', 1), (67, 'Eb', 2.5), (67, 'A7/C#', 3), (68, 'Gm/D', 0),
                         (68, 'D7', 2), (69, 'Gm', 0), (69, 'D', 2), (70, 'Dm', 0), (70, 'E7', 3), (71, 'Dm/A', 0),
                         (71, 'A7', 2), (72, 'Dm', 0), (73, 'Gm', 0), (73, 'C7', 2), (74, 'F', 0), (74, 'Bbmaj7', 2),
                         (75, 'Eb', 0), (75, 'Abmaj7', 2), (76, 'Dm7b5', 0), (76, 'G7', 2), (77, 'G7', 0)):
        H(b, sym, beat)
    # entry 1, violas alone: the subject (the gesture's rising fifth and its turn, then a running tail)
    # (round 2: a dynamic louder throughout - mezzo forte, marcato, from the first entry; round 1's fugato measured
    #  12 LU under the return)
    L('vas', 60, SUBJ, MF + 6)
    # entry 2, second violins: the answer a fifth higher (a real answer); the violas go on with the countersubject
    L('vn2s', 63, SUBJ, MF + 12, tr=7)
    L('vas', 63, CSUB, MF + 4)
    # a bar's link back to G minor
    L('vn2s', 66, 'Bb4:.5 A4:.5 G4:.5 F#4:.5 E4:.5 F#4:.5 G4:.5 A4:.5', MF + 12)
    L('vas', 66, 'D3:1 D4:1 C4:1 A3:1', MF + 6)
    # entry 3, cellos, basses and bassoons: the subject in the bass; countersubject above in the second violins
    v = F + 2
    ML('vcs:-12 cbs:-24/-8 bns:-12/-6', 67, SUBJ, v)   # (round 5: the basses under the cellos; they measured 4 dB over)
    L('vn2s', 67, 'r:1 Bb4:.5 C5:.5 D5:.5 G4:.5 A4:1 | D5:1.5 D5:.5 D5:1 C5:1 | Bb4:.5 A4:.5 G4:.5 A4:.5 F#4:1 r:1', v - 6)
    L('vas', 67, 'Bb3:1 F3:1.5 Bb3:.5 G3:1 | Bb3:1 G3:1 F#3:1 A3:1 | D4:1 D4:.5 Eb4:.5 D4:1 r:1', v - 8)
    tpat(67, [(0, 'G2', 0)], MF)
    # entry 4, first violins with oboes and flutes: the answer on top; countersubject in the bass
    v = F + 10
    ML('vn1s:19 obs:19/-8 fls:19/-10', 70, SUBJ, v)
    L('vcs', 70, CSUB, v - 4, tr=-12)
    L('cbs', 70, 'D2:1 F1:.5 G1:.5 A1:.5 D2:.5 E1:1 | A1:1.5 A1:.5 A1:1 G1:1 | F1:.5 E1:.5 D2:.5 C#2:.5 D2:1 r:1', v - 12)
    L('vn2s', 70, 'A4:.5 F4:.5 D4:1 F4:1 E4:1 | F4:1 D4:1 E4:1 E4:1 | F4:.5 G4:.5 F4:.5 E4:.5 F4:1 r:1', v - 8)
    L('vas', 70, 'D4:1 A3:1 D4:1 B3:1 | D4:1 A3:1 C#4:1 A3:1 | D4:1 A3:1 A3:1 r:1', v - 10)
    tpat(70, [(0, 'D3', 0)], F - 6)
    # the episode, bars 73-76: the subject's falling cell in sequence through the circle of fifths, violins
    # answered by the woodwinds; the basses walk; the horns hold a line that sinks by step
    v = ramp([(bar(73), F + 8), (bar(77), FF), (bar(78), FF + 4)])
    cells = {73: ('D5:.5 Bb4:.5 A4:.5 G4:.5', 'Bb4:.5 G4:.5 F4:.5 E4:.5'),
             74: ('C5:.5 A4:.5 G4:.5 F4:.5', 'A4:.5 F4:.5 Eb4:.5 D4:.5'),
             75: ('Bb4:.5 G4:.5 F4:.5 Eb4:.5', 'G4:.5 Eb4:.5 Db4:.5 C4:.5'),
             76: ('Ab4:.5 F4:.5 Eb4:.5 D4:.5', 'F4:.5 D4:.5 C4:.5 B3:.5')}
    for b, (first, second) in cells.items():
        for tid, tr, dv in (('vn1s', 12, 0), ('vn2s', 0, -4)):
            at(tid, bar(b), first, v, tr, dv=dv)
        for tid, tr, dv in (('obs', 12, -6), ('cls', 0, -8), ('fls', 12, -8)):
            at(tid, bar(b) + 2, second, v, tr, dv=dv)
    L('vas', 73, 'r:.5 D4:.5 r:.5 Bb3:.5 r:.5 E4:.5 r:.5 Bb3:.5 | r:.5 C4:.5 r:.5 A3:.5 r:.5 D4:.5 r:.5 Bb3:.5 | '
               'r:.5 Bb3:.5 r:.5 G3:.5 r:.5 C4:.5 r:.5 Ab3:.5 | r:.5 C4:.5 r:.5 Ab3:.5 r:.5 B3:.5 r:.5 G3:.5',
      lambda x: v(x) - 12)
    # the bass walks root and fifth (its thirds sat a ninth under the cells' passing notes)
    walk = 'G2:1 D3:1 C3:1 G2:1 | F2:1 C3:1 Bb2:1 F2:1 | Eb3:1 Bb2:1 Ab2:1 Eb3:1 | D3:1 Ab2:1 G2:1 D3:1'
    ML('vcs:0 cbs:-12/-8 bns:0/-8', 73, walk, lambda x: v(x) - 4)
    L('hn12', 73, 'G4:4 | F4:4 | Eb4:4 | F4:2 D4:2', MF)
    # bar 77: everyone on the dominant of C minor, rising
    ML('vn1s:12 vn2s:0 vas:0/-4', 77, 'G3:.5 A3:.5 B3:.5 C4:.5 D4:.5 Eb4:.5 F4:.5 G4:.5', v)
    ML('vcs:-12 cbs:-12 bns:-12/-6', 77, 'G3:1 G3:1 G3:.5 G3:.5 G3:.5 B3:.5', v)
    L('hn12', 77, 'G4:4', MF + 6)   # the horns hold the bare G: the third and seventh are in the scale
    L('hn34', 77, 'G3:4', MF + 6)
    dyn('hn12', (bar(77), MF + 4), (bar(78) - .1, FF))
    dyn('hn34', (bar(77), MF + 4), (bar(78) - .1, FF))
    roll('timp', bar(77), 4, 'G2', MF - 6, FF)


def sec_development():
    """Bars 78-87: the subject's head in close imitation between low and high brass, climbing from C minor through
    D minor; the singing theme's opening in F major, in the fast tempo; and C7, which is also the augmented sixth
    of E minor."""
    for b, sym, beat in ((78, 'Cm', 0), (78, 'D7', 3), (79, 'Gm', 0), (79, 'A7', 1), (79, 'D', 2),
                         (80, 'Dm', 0), (80, 'E7', 3), (81, 'Am', 0), (81, 'B7', 1), (81, 'E', 2),
                         (82, 'F', 0), (83, 'F', 0), (83, 'Bb', 2), (84, 'Bb', 0), (84, 'Bdim7', 2), (85, 'F/C', 0),
                         (86, 'C7', 0), (87, 'C7', 0)):
        H(b, sym, beat)
    v = lambda _: FF - 4
    for b, tr in ((78, 0), (80, 2)):
        ML('tb:0 tuba:-12/-2 bn:0/-10 vcs:0/-4 cbs:-12/-2', b, 'C3:1 G3:1.5 Ab3:.5 F#3:1 | G3:2 r:2', v, gate=.95)
        ML('tp:0 hn_t:0/-2 ob:0/-10 cl:0/-12 fl:12/-10', b, 'r:2 G4:1 D5:1.5 Eb5:.5 C#5:1 D5:2', v, gate=.95)
    # (the second pair a whole step higher)
    for tid in ('tb', 'tuba', 'bn', 'cl', 'vcs', 'cbs', 'tp', 'hn_t', 'ob', 'fl'):
        for n in TR[tid]['notes']:
            if bar(80) <= n['on'] < bar(82):
                n['pitch'] += 2
    run = {78: 'Eb5:.5 D5:.5 C5:.5 D5:.5 Eb5:.5 G5:.5 F#5:.5 A5:.5', 79: 'G5:.5 Bb5:.5 A5:.5 G5:.5 F#5:.5 A5:.5 D5:.5 F#5:.5',
           80: 'F5:.5 E5:.5 D5:.5 E5:.5 F5:.5 A5:.5 G#5:.5 B5:.5', 81: 'A5:.5 C6:.5 B5:.5 A5:.5 G#5:.5 B5:.5 E5:.5 G#5:.5',
           82: 'A5:.5 G5:.5 F5:.5 G5:.5 A5:.5 C6:.5 A5:.5 F5:.5', 83: 'C6:.5 A5:.5 F5:.5 A5:.5 Bb5:.5 D6:.5 Bb5:.5 F5:.5',
           84: 'D6:.5 Bb5:.5 D6:.5 Bb5:.5 D6:.5 B5:.5 Ab5:.5 F5:.5', 85: 'C6:.5 F5:.5 C6:.5 F5:.5 A5:.5 C6:.5 F5:.5 A5:.5'}
    for b, text in run.items():   # (round 5: a dynamic lower; in round 4 the run measured 1.6 dB under the brass)
        ML('vn1s:0 vn2s:-12/-4', b, text, F - 4)
    rock = {78: 'G4 Eb4 G4 Eb4 G4 Eb4 A4 F#4', 79: 'G4 D4 G4 E4 F#4 D4 F#4 D4', 80: 'A4 F4 A4 F4 A4 F4 B4 G#4',
            81: 'E4 A4 F#4 D#4 B4 E4 B4 E4', 82: 'C4 F4 C4 F4 C4 F4 C4 F4', 83: 'C4 F4 C4 F4 F4 D4 F4 D4',
            84: 'Bb3 D4 Bb3 D4 F4 Ab4 F4 Ab4', 85: 'F4 C4 F4 C4 F4 A3 F4 A3'}
    for b, names in rock.items():   # the violas rock between two notes of the chord, against the violins' direction
        eighths('vas', b, names.split(), FF - 14, accent=(0, 4))
    tpat(79, [(0, 'G2', 0)], F)
    tpat(81, [(0, 'A2', 0)], F)
    # bars 82-85: the singing theme's first notes, in F major, horns and trumpets with the trombones an octave under
    theme = 'C5:3 A4:1 | F4:2 D5:2 | D5:1 E5:1 F5:1.5 G5:.5 | Bb5:1 A5:2 F5:1'
    v = ramp([(bar(82), FF - 2), (bar(85), FF + 4)])
    ML('tp:0 tb:-12/-2 ob:0/-10 cl:0/-12 fl:12/-10', 82, theme, v)
    L('hn_t', 82, 'C5:3 A4:1 | F4:2 D5:2', v)
    L('hn_t', 84, 'D4:1 E4:1 F4:1.5 G4:.5 | Bb4:1 A4:2 F4:1', v)
    L('hn34', 82, 'F3+C4:4 | F3+C4:2 F3+D4:2 | F3+D4:4 | F3+C4:4', FF - 12)
    low = {82: 'F2 C3 F2 C3 F2 C3 F2 C3', 83: 'F2 C3 F2 C3 Bb2 F3 Bb2 F3', 84: 'Bb2 F3 Bb2 F3 B2 F3 B2 F3',
           85: 'C3 F3 C3 A3 C3 F3 C3 F3'}
    for b, names in low.items():
        for tid in ('vcs', 'cbs', 'bns'):
            eighths(tid, b, names.split(), FF - 8, accent=(0, 4))
    L('tuba', 82, 'F2:4 | F2:2 Bb1:2 | Bb1:2 B1:2 | C2:4', F)
    L('tb3', 82, 'F3:4 | F3:2 Bb2:2 | Bb2:2 B2:2 | C3:4', F)
    tpat(82, [(0, 'F2', 0)], F + 4)
    add('bd', bar(82), 1, BD, F)
    # bars 86-87: C7 - the augmented sixth of the home key - swelling; the trumpets climb it to B flat (A sharp)
    v = ramp([(bar(86), FF - 2), (bar(88), FFF - 2)])
    ML('tp:0 hn_t:-12 ob:0/-8 fl:12/-8', 86, 'E5:2 G5:2 | Bb5:3 r:1', v)
    L('tb', 86, 'E3+Bb3:4 | E3+Bb3:4', v, dv=-6)
    L('tb3', 86, 'C3:4 | C3:4', v, dv=-6)
    L('tuba', 86, 'C2:4 | C2:4', v, dv=-6)
    L('hn34', 86, 'G3+C4:4 | G3+C4:4', v, dv=-8)
    L('cl', 86, 'G4+Bb4:4 | G4+Bb4:4', v, dv=-12)
    L('bn', 86, 'C3+G3:4 | C3+G3:4', v, dv=-10)
    L('vnt', 86, 'E5+Bb5:4 | E5+Bb5:4', v)
    L('vat', 86, 'E4+G4:4 | E4+G4:4', v)
    for tid in ('tb', 'tb3', 'tuba', 'hn34', 'cl', 'bn', 'vnt', 'vat'):
        dyn(tid, (bar(86), FF - 14), (bar(87), FF - 4), (bar(88) - .1, FFF))
    for b in (86, 87):
        eighths('vcs', b, 'C3 G3 C3 E3 C3 G3 C3 G3'.split(), v)
        eighths('cbs', b, 'C3 G3 C3 E3 C3 G3 C3 G3'.split(), v)
    roll('timp', bar(86), 8, 'E2', F - 10, FF + 6)


def sec_pedal():
    """Bars 88-97: the dominant pedal.  The figure returns on B in the low strings; the gesture's turn climbs
    through the chord, horn to clarinets to oboes to flutes; the ninth C beats against B; everything swells."""
    for b, sym in ((88, 'Em/B'), (89, 'B7'), (90, 'Em/B'), (91, 'B7'), (92, 'Em/B'), (93, 'B7'), (94, 'B7b9'),
                   (96, 'B7')):
        H(b, sym)
    v = ramp([(bar(88), FF - 6), (bar(90), F), (bar(94), FF - 2), (bar(98), FFF)])
    for b in range(88, 98):
        key = 'Em/B' if b in (88, 90, 92) else 'B'
        drive(b, key, v, last='D#3' if b == 97 else None, parts=('vcs', 'bns', 'cbs') + (('vas',) if b < 94 else ()))
        add('tuba', bar(b), 4, P('B1'), v(bar(b)) - 20)   # (round 1: the held pedal measured over everything else)
        add('tb3', bar(b), 4, P('B2'), v(bar(b)) - 20)
    for b in range(88, 94):
        tpat(b, TIMP_A('B2'), lambda x: v(x) - 2)
    roll('timp', bar(94), 16, 'B2', F - 8, FFF + 2)
    add('bd', bar(88), 1, BD, FF - 4)
    add('bd', bar(94), 1, BD, F)
    add('bd', bar(96), 1, BD, FF)
    # violins tremolo above
    L('vnt', 88, 'G5+B5:4 | F#5+B5:4 | E5+G5:4 | F#5+A5:4 | E5+B5:4 | F#5+A5:4 | F#5+A5:4 | F#5+A5:4 | F#5+B5:4 | F#5+B5:4', v)
    # (round 5: the tremolo a dynamic lower until the last bars; in round 4 it measured level with the trumpets)
    dyn('vnt', (bar(88), FF - 22), (bar(90), F - 18), (bar(94), FF - 18), (bar(96), FF - 8), (bar(98) - .1, FFF))
    # bars 88-89: the arrival; brass on the timpani's rhythm
    for b, (a, c, t2, tb) in {88: ('G4+B4', 'B3+E4', 'B4+E5', 'E3+G3'), 89: ('F#4+A4', 'B3+D#4', 'B4+D#5', 'F#3+A3')}.items():
        horn_rhythm(b, a, c, FF - 8)
        for pos in (0, 2, 2.5, 3):
            for nm in t2.split('+'):
                add('tps', bar(b) + pos, .5, P(nm), FF - 6)
            for nm in tb.split('+'):
                add('tbs', bar(b) + pos, .5, P(nm), FF - 8)
    L('fl', 88, 'G5+B5:4 | F#5+B5:4', FF - 14)
    L('ob', 88, 'E5+G5:4 | D#5+F#5:4', FF - 14)
    L('cl', 88, 'B4+E5:4 | A4+D#5:4', FF - 16)
    # bars 90-93: the turn (x, the note above, the note below, x) rising through B, D sharp, G, B
    cell = lambda p: f'{p[0]}:1.5 {p[1]}:.5 {p[2]}:1 {p[0]}:1'
    ML('hn_t:0 cl:0/-8', 90, cell(('B4', 'C5', 'A#4')), F + 4)
    ML('ob:0 cl:0/-4 tp:0/-8', 91, cell(('D#5', 'E5', 'D5')), F + 6)
    ML('fl:0 ob:0/-2 tp:0/-6', 92, cell(('G5', 'A5', 'F#5')), FF - 4)
    ML('fl:0 picc:12/-8 ob:0/-2 tp:-12', 93, cell(('B5', 'C6', 'A#5')), FF)
    for b, (c, tb) in {90: ('B3+E4', 'E3+G3'), 91: ('B3+D#4', 'F#3+A3'), 92: ('B3+E4', 'E3+G3'), 93: ('B3+D#4', 'F#3+A3')}.items():
        horn_rhythm(b, None, c, lambda x: v(x) - 10)
        for pos in (0, 2):
            for nm in tb.split('+'):
                add('tbs', bar(b) + pos, .5, P(nm), v(bar(b)) - 8)
    # bars 94-95: C against B, in quarters then eighths
    ML('fl:0 picc:12/-8 ob:-12 tp:-12 hn_t:-24/-2', 94,
       'C6:1 B5:1 C6:1 B5:1 | C6:.5 B5:.5 C6:.5 B5:.5 C6:.5 B5:.5 C6:.5 B5:.5', lambda x: v(x) + 2, gate=.9)
    L('cl', 94, 'D#5+F#5:4 | D#5+F#5:4', lambda x: v(x) - 8)
    # the violas leave the figure for a tremolo on the chord's third and seventh
    L('vat', 94, 'D#4+A4:4 | D#4+A4:4 | D#4+A4:4 | D#4+A4:4', v)
    dyn('vat', (bar(94), FF - 14), (bar(96), FF - 4), (bar(98) - .1, FFF))
    L('hn34', 94, 'D#4+F#4:4 | D#4+F#4:4', lambda x: v(x) - 8)
    L('tb', 94, 'F#3+A3:4 | F#3+A3:4', lambda x: v(x) - 6)
    # bars 96-97: the dominant seventh held by everyone, swelling; three eighths of upbeat in trumpets and trombones
    hold = {'tp': 'F#5+B5', 'hn_t': 'F#4+A4', 'hn34': 'B3+D#4', 'tb': 'A3+D#4', 'fl': 'B5+D#6', 'picc': 'B6',
            'ob': 'F#5+A5', 'cl': 'D#5+F#5'}
    for tid, names in hold.items():
        d = 6.5 if tid in ('tp', 'tb') else 8
        for nm in names.split('+'):
            add(tid, bar(96), d, P(nm), FF)
        dyn(tid, (bar(96), FF - 8), (bar(97), FF), (bar(98) - .1, FFF + 2))
    for i in range(3):
        on = bar(97) + 2.5 + i * .5
        for nm in ('B4', 'D#5'):
            add('tps', on, .5, P(nm), FF + 2 + 3 * i)
        for nm in ('B2', 'B3'):
            add('tbs', on, .5, P(nm), FF + 2 + 3 * i)
    # a suspended-cymbal swell that peaks on the return's first stroke (the sample peaks 3.7 s after it starts)
    add('cym', bar(98) - 8.6, 8.6, SWELL_3S7, FF)


def sec_return():
    """Bars 98-113: the opening at full force, then the first theme by the whole orchestra, extended through a
    deceptive cadence and the Neapolitan (F major) to the dominant."""
    gesture(98, FFF, full=True)
    for i in range(4):  # timpani leads back into the figure
        add('timp', bar(100) + 2 + i * .5, .5, P('B2'), F + 6 * i)
    for b, sym, beat in ((101, 'Em', 0), (104, 'Am', 0), (106, 'C', 0), (107, 'F#m7b5', 0), (108, 'Em/B', 0),
                         (108, 'B7', 2), (109, 'C', 0), (110, 'F/A', 0), (112, 'Em/B', 0), (113, 'B7', 0)):
        H(b, sym, beat)
    v = lambda _: FFF - 4
    strings = ('vcs', 'cbs', 'bns', 'vas')
    drive(101, 'E', v, parts=strings + ('vn2s', 'vn1s'))
    tpat(101, TIMP_A('E2'), FFF - 6)
    add('bd', bar(101), 1, BD, FF)
    keys = [(102, 'E', None), (103, 'E', 'G#2'), (104, 'A', None), (105, 'A', 'B2'), (106, 'C', None),
            (107, 'F#', 'A2'), (108, 'Em/B>B7', None), (109, 'C', 'B2'), (110, 'F/A', None), (111, 'F/A', 'A#2'),
            (112, 'Em/B', None), (113, 'B7', 'D#3')]
    for b, key, last in keys:
        drive(b, key, v, last=last, parts=strings)
    # the theme: trumpets, horns 1-2 and trombones in three octaves, violins in octaves above, woodwinds with them
    ext = 'E5:2 G5:1.5 A5:.5 | C6:3 A5:1 | A5:1.5 G5:.5 F5:2 | E5:2 G5:1.5 F#5:.5 | F#5:3 D#5:1'
    L('tp', 102, T1_HEAD + ' ' + T1_CADENCE + ' ' + ext, v)
    L('hn_t', 102, T1_HEAD + ' E5:1.5 D5:.5 C5:1 E5:1', v)
    L('hn_t', 107, 'F#5:2 A5:1.5 G5:.5 | E5:2 F#5:1.5 D#5:.5 | ' + ext, v, tr=-12)
    L('tb', 102, T1_HEAD + ' ' + T1_CADENCE + ' E5:2 G5:1.5 A5:.5', v, tr=-12)
    L('tb', 110, 'C6:3 A5:1 | A5:1.5 G5:.5 F5:2 | E5:2 G5:1.5 F#5:.5 | F#5:3 D#5:1', v, tr=-24)
    L('vn1', 102, T1_HEAD + ' E5:1.5 D5:.5 C5:1 E5:1', v, tr=12)
    L('vn1', 107, 'F#5:2 A5:1.5 G5:.5 | E5:2 F#5:1.5 D#5:.5 | ' + ext, v)
    L('vn2', 102, T1_HEAD + ' E5:1.5 D5:.5 C5:1 E5:1', v, dv=-4)
    L('vn2', 107, 'F#5:2 A5:1.5 G5:.5 | E5:2 F#5:1.5 D#5:.5 | ' + ext, v, tr=-12, dv=-4)
    ML('fl:12/-8 ob:0/-8 cl:0/-10', 102, T1_HEAD + ' ' + T1_CADENCE + ' ' + ext, v)
    L('picc', 106, T1_CADENCE + ' ' + ext, v, tr=12, dv=-12)
    hn = {102: 'B3+E4', 103: 'B3+E4', 104: 'A3+E4', 105: 'A3+E4', 106: 'C4+E4', 107: 'C4+E4', 109: 'C4+E4',
          110: 'C4+F4', 111: 'C4+F4', 112: 'B3+E4', 113: 'B3+D#4'}
    for b, c in hn.items():
        horn_rhythm(b, None, c, FFF - 12)
    horn_rhythm(108, None, 'B3+E4', FFF - 12, None, 'B3+D#4')
    for b, (tbs, tu) in {102: ('E3', 'E2'), 103: ('E3', 'E2'), 104: ('A2', 'A1'), 105: ('A2', 'A1'), 106: ('C3', 'C2'),
                         107: ('F#2', 'F#1'), 108: ('B2', 'B1'), 109: ('C3', 'C2'), 110: ('A2', 'A1'), 111: ('A2', 'A1'),
                         112: ('B2', 'B1'), 113: ('B2', 'B1')}.items():
        add('tubas', bar(b), .5, P(tu), FFF - 8)
        add('tubas', bar(b) + 2, .5, P(tu), FFF - 12)
    tpat(102, TIMP_A('E2'), FFF - 6)
    tpat(103, TIMP_B('E2', 'B2'), FFF - 6)
    tpat(104, TIMP_A('A2'), FFF - 6)
    tpat(105, TIMP_A('A2'), FFF - 6)
    roll('timp', bar(108), 4, 'B2', F, FFF)
    tpat(110, TIMP_A('A2'), FFF - 4)
    tpat(111, TIMP_A('A2'), FFF - 4)
    roll('timp', bar(112), 8, 'B2', F, FFF + 2)
    for b, dv in ((102, 0), (104, -10), (106, -6), (109, 4), (110, 0), (112, -6)):
        add('bd', bar(b), 1, BD, FF + dv)
    add('cym', bar(109), 1, CLASH, FF)


def sec_coda():
    """Bars 114-133, faster: the tonic pedal with the figure; the singing theme's first notes in the minor, in
    trombones and horns, answered a fourth higher by the trumpets; Neapolitan-dominant-tonic twice; the gesture's
    rising fifth piled up from the bass; the augmented sixth, the dominant, and the bare E the piece began with."""
    for b, sym, beat in ((114, 'Em', 0), (115, 'C/E', 2), (116, 'Em', 2), (118, 'Am/E', 0), (119, 'F/E', 2),
                         (120, 'Am/E', 2), (121, 'B7', 0), (122, 'F/A', 0), (122, 'B7', 2), (123, 'Em', 0),
                         (124, 'F/A', 0), (124, 'B7', 2), (125, 'Em', 0), (129, 'C7', 0), (130, 'B', 0),
                         (131, 'Em', 0), (131, 'B7', 2), (132, 'Em', 0)):
        H(b, sym, beat)
    v = lambda _: FFF - 6
    allstr = ('vcs', 'cbs', 'bns', 'vas', 'vn2s', 'vn1s')

    def fig_bar(b, low, up=None, vn1=('G4', 'E5'), bassoons=True):
        """A bar of the figure over the E pedal with notes of its own: cellos (and bassoons) play `low`, violas and
        second violins `up` one and two octaves higher, first violins rock between two notes, basses keep E."""
        low = low.split()
        up = up.split() if up else low
        eighths('vcs', b, low, v)
        if bassoons:
            eighths('bns', b, low, v)
        pedal(b, 'E1', v)
        eighths('vas', b, up, v, tr=12)
        eighths('vn2s', b, up, v, tr=24)
        eighths('vn1s', b, list(vn1) * 4, v, accent=(0, 4))

    # bars 114-117: E minor; trombones and horns
    hit(bar(114), {'tps': 'E5+B4', 'fls': 'E6+B6', 'obs': 'G5+B5', 'cls': 'E5+G5'}, FFF - 6)
    add('picc', bar(114), .5, P('E7'), FFF - 10, gate=.6)
    add('cym', bar(114), 1, CLASH, FF + 4)
    add('bd', bar(114), 1, BD, FF + 6)
    drive(114, 'E', v, parts=allstr)
    fig_bar(115, 'E2 B2 E2 G2 E2 G2 E2 C3')
    fig_bar(116, 'E2 C3 E2 G2 E2 G2 E2 B2')
    drive(117, 'E', v, parts=allstr)
    ML('tb:-12 hn_t:0/-2', 114, 'B4:3 G4:1 | E4:2 C5:2 | C5:1.5 B4:.5 A#4:1 B4:1 | E4:3 r:1', v)
    for b in (114, 115, 116, 117):
        tpat(b, TIMP_A('E2') if b in (114, 117) else TIMP_C('E2'), FFF - 6)
        add('tubas', bar(b), .5, P('E2'), FFF - 10)
        add('tubas', bar(b) + 2, .5, P('E2'), FFF - 14)
    # bars 118-121: the answer over the same pedal (A minor, then F major over E: the Neapolitan against the
    # tonic, kept out of every part but the bass), then the dominant
    am = 'E2 A2 E2 C3 E2 A2 E2 C3'
    fig_bar(118, am, vn1=('C5', 'A5'), bassoons=False)
    fig_bar(119, am, 'E2 A2 E2 C3 A2 C3 A2 F3', vn1=('C5', 'A5'), bassoons=False)
    fig_bar(120, am, 'A2 C3 A2 F3 E2 A2 E2 C3', vn1=('C5', 'A5'), bassoons=False)
    drive(121, 'B', v, last='D#3', parts=('vcs', 'cbs', 'bns', 'vas', 'vn2s'))
    eighths('vn1s', 121, ['D#5', 'B5'] * 4, v, accent=(0, 4))
    ML('tp:0 ob:0/-8 fl:12/-8', 118, 'E5:3 C5:1 | A4:2 F5:2 | F5:1.5 E5:.5 D#5:1 E5:1 | D#5:3 r:1', v)
    horn_rhythm(118, None, 'A3+E4', FFF - 12)
    horn_rhythm(119, None, 'A3+E4', FFF - 12, None, 'A3+F4')
    horn_rhythm(120, None, 'A3+F4', FFF - 12, None, 'A3+E4')
    horn_rhythm(121, 'F#4+A4', 'B3+D#4', FFF - 10)
    for b in (118, 119, 120):
        tpat(b, TIMP_C('E2'), FFF - 6)
        add('tubas', bar(b), .5, P('E2'), FFF - 10)
        add('tubas', bar(b) + 2, .5, P('E2'), FFF - 14)
    roll('timp', bar(121), 4, 'B2', F, FFF)
    low_brass(121, 'B2+F#3', 'B1', FFF - 8)
    add('bd', bar(118), 1, BD, FF)
    # bars 122-125: Neapolitan (two strokes), dominant (held), tonic with a bar of the figure - twice
    n6 = {'tps': 'C5+F5', 'fls': 'C6+F6', 'obs': 'A5+C6', 'cls': 'F5+A5', 'hn12': 'A4+C5', 'hn34': 'A3+F4',
          'tbs': 'A2+F3', 'tubas': 'A1', 'vn1s': 'C6', 'vn2s': 'F5', 'vas': 'A4', 'vcs': 'A2', 'cbs': 'A1',
          'bns': 'A2', 'timp': 'A2'}
    v7 = {'tp': 'B4+D#5', 'hn12': 'F#4+A4', 'hn34': 'B3+D#4', 'tb': 'F#3+A3', 'tb3': 'B2', 'tuba': 'B1', 'fl': 'B5+D#6',
          'ob': 'F#5+A5', 'cl': 'D#5+F#5', 'bn': 'B2', 'vnt': 'F#5+B5', 'vat': 'F#4+A4', 'vc': 'B2', 'cb': 'B1'}
    for b in (122, 124):
        hit(bar(b), n6, FFF - 6)
        hit(bar(b) + 1, n6, FFF - 8)
        add('bd', bar(b), 1, BD, FF)
        for tid, names in v7.items():
            for nm in names.split('+'):
                add(tid, bar(b) + 2, 2, P(nm), FFF - 6)
            dyn(tid, (bar(b) + 2, FF), (bar(b) + 4 - .05, FFF + 2))
        roll('timp', bar(b) + 2, 2, 'B2', FF - 6, FFF + 2)
        hit(bar(b + 1), {'tps': 'E5+B4', 'fls': 'E6+B6', 'obs': 'G5+B5', 'cls': 'E5+G5', 'hn12': 'G4+B4', 'hn34': 'B3+E4',
                         'tbs': 'E3+B3', 'tubas': 'E2'}, FFF - 4)
        drive(b + 1, 'E', v, parts=allstr)
        tpat(b + 1, TIMP_A('E2'), FFF - 4)
        add('bd', bar(b + 1), 1, BD, FF + 4)
    add('cym', bar(125), 1, CLASH, FF)
    # bars 126-128: the gesture's rising fifth and turn, a bar each, from the bass up through three octaves
    for b in (126, 127, 128):
        drive(b, 'E', v, parts=allstr)
        tpat(b, TIMP_A('E2'), FFF - 4)
    head = 'E4:1 B4:1.5 C5:.5 B4:1'
    ML('tb:-12 hn34:-12/-4', 126, head, v, gate=.95)
    ML('tp:0 hn_t:0/-2 ob:0/-8 cl:0/-10 tb:-12/-4', 127, head, v, gate=.95)
    ML('tp:12 hn_t:0/-2 fl:24/-6 picc:24/-12 ob:12/-8 cl:12/-10 tb:-12/-4', 128, head, v, gate=.95)
    for b in (126, 127, 128):
        add('tubas', bar(b), .5, P('E2'), FFF - 8)
        add('tubas', bar(b) + 2, .5, P('E2'), FFF - 12)
    # bar 129: the augmented sixth, broad; bar 130: the dominant, bare, with the timpani
    g6 = {'tp': 'E5+A#5', 'hn_t': 'A#3+E4', 'hn34': 'G3+C4', 'tb': 'E3+G3', 'tb3': 'C3', 'tuba': 'C2', 'bn': 'C2+C3',
          'cl': 'E5+G5', 'ob': 'G5+A#5', 'fl': 'G6+A#6', 'picc': 'A#6', 'vnt': 'A#4+A#5', 'vat': 'E4+G4', 'vc': 'C3',
          'cb': 'C2'}
    for tid, names in g6.items():
        for nm in names.split('+'):
            add(tid, bar(129), 4, P(nm), FFF)
        dyn(tid, (bar(129), FFF - 4), (bar(130) - .05, 127))
    roll('timp', bar(129), 4, 'E2', FF - 6, FFF + 2)
    add('bd', bar(129), 1, BD, FF + 6)
    add('cym', bar(129), 1, CLASH, FF + 2)
    dom = {'tp': 'B4+B5', 'hn_t': 'B3+B4', 'hn34': 'B2', 'tb': 'B2+B3', 'tuba': 'B1', 'bn': 'B1+B2',
           'cl': 'B4+B5', 'ob': 'B4+B5', 'fl': 'B5+B6', 'picc': 'B6', 'vnt': 'B4+B5', 'vat': 'B3', 'vc': 'B2', 'cb': 'B1'}
    for tid, names in dom.items():
        for nm in names.split('+'):
            add(tid, bar(130), 4, P(nm), FFF)
        dyn(tid, (bar(130), FFF - 6), (bar(131) - .05, 127))
    roll('timp', bar(130), 4, 'B2', FF, 127)
    # bars 131-132: tonic, dominant, tonic - three strokes - and silence
    em = {'tps': 'E5+B4', 'fls': 'E6+B6', 'obs': 'G5+B5', 'cls': 'E5+G5', 'hn12': 'G4+B4', 'hn34': 'B3+E4',
          'tbs': 'E3+B3', 'tubas': 'E2', 'vn1s': 'E6', 'vn2s': 'G5', 'vas': 'B4', 'vcs': 'E2', 'cbs': 'E1',
          'bns': 'E2+B2', 'timp': 'E2'}
    b7 = {'tps': 'D#5+B4', 'fls': 'D#6+B6', 'obs': 'F#5+A5', 'cls': 'D#5+F#5', 'hn12': 'F#4+A4', 'hn34': 'B3+D#4',
          'tbs': 'F#3+B3', 'tubas': 'B1', 'vn1s': 'D#6', 'vn2s': 'F#5', 'vas': 'A4', 'vcs': 'B2', 'cbs': 'B1',
          'bns': 'B2', 'timp': 'B2'}
    hit(bar(131), em, 126)
    hit(bar(131) + 2, b7, 124)
    hit(bar(132), em, 127)
    for on in (bar(131), bar(131) + 2, bar(132)):
        add('bd', on, 1, BD, FFF)
    # bar 133: the bare E, everyone, as at the opening - but held
    last = {'tp': 'E4+E5', 'hn_t': 'E4', 'hn34': 'E3', 'tb': 'E3', 'tb3': 'E2', 'tuba': 'E2', 'bn': 'E2+E3',
            'cl': 'E4+E5', 'ob': 'E4+E5', 'fl': 'E5+E6', 'picc': 'E7', 'vn1': 'E5', 'vn2': 'E4', 'va': 'E3+E4',
            'vc': 'E2+E3', 'cb': 'E1'}
    for tid, names in last.items():
        for nm in names.split('+'):
            add(tid, bar(133), 3, P(nm), 127)
        dyn(tid, (bar(133), 124), (bar(133) + 2.9, 127))
    hit(bar(133), {'vn1s': 'E5', 'vn2s': 'E4', 'vas': 'E3', 'vcs': 'E2', 'cbs': 'E1'}, 127)   # the bows' attack
    roll('timp', bar(133), 3, 'E2', FFF, 127)
    add('bd', bar(133), 1, BD, 127)
    add('cym', bar(133), 1, CLASH, FFF)
    add('cym', bar(133), 1, GONG, FF)


SECTIONS = [
    ('gesture', 1, 3, 'The opening gesture: a bare E, B rising to C, the augmented sixth, a bare B, silence'),
    ('drive', 4, 18, 'The driving figure in cellos and basses with timpani; the first theme in the horns, then the full orchestra'),
    ('bridge', 22, 10, 'The figure thins; woodwinds turn the gesture toward G major; the tempo broadens'),
    ('theme', 32, 16, 'The singing theme in G major: first violins, then violins and cellos in octaves to its peak'),
    ('theme_full', 48, 6, 'The singing theme in B flat major by the whole orchestra, to its highest note'),
    ('codetta', 54, 6, 'A deceptive cadence into G minor; the theme in the minor falls into the gesture\'s turn'),
    ('fugato', 60, 18, 'Fugato on the gesture: violas, second violins, cellos and basses, first violins; an episode'),
    ('development', 78, 10, 'The subject\'s head in imitation in the brass, the singing theme in F, the augmented sixth'),
    ('pedal', 88, 10, 'The dominant pedal: the figure returns, the turn climbs, everything swells'),
    ('return', 98, 16, 'The opening at full force; the first theme by the whole orchestra, extended to the dominant'),
    ('coda', 114, 20, 'Faster: tonic pedal, the themes compressed, Neapolitan cadences, and the bare E to end'),
]
BARS = 133


def compose():
    sec_gesture()
    sec_drive()
    sec_bridge()
    sec_theme()
    sec_fugato()
    sec_development()
    sec_pedal()
    sec_return()
    sec_coda()


# ------------------------------------------------------------------ 4. performance
# Players who cannot be in two places: parts that share players may not sound together.
SHARED = [('hn_t', 'hn12'), ('tp', 'tps'), ('tuba', 'tubas'), ('vn1', 'vn1s', 'vnt'),
          ('vn2', 'vn2s', 'vnt'), ('va', 'vas', 'vat'), ('vc', 'vcs'), ('cb', 'cbs', 'cbp'), ('fl', 'fls'),
          ('ob', 'obs'), ('cl', 'cls'), ('bn', 'bns')]
PLAYERS = {'fl': 2, 'fls': 2, 'ob': 2, 'obs': 2, 'cl': 2, 'cls': 2, 'bn': 2, 'bns': 2, 'hn_t': 2, 'hn12': 2,
           'hn34': 2, 'tp': 2, 'tps': 2, 'tb': 2, 'tbs': 3, 'tb3': 1, 'tuba': 1, 'tubas': 1, 'picc': 1}


def check_players():
    problems = []
    spans = {tid: sorted((n['on'], n['on'] + n['duration']) for n in TR[tid]['notes']) for tid in TR}
    for group in SHARED:
        for i, a in enumerate(group):
            for c in group[i + 1:]:
                if {a, c} == {'vn1', 'vn1s'} or {a, c} == {'vn2', 'vn2s'} or {a, c} == {'va', 'vas'} or {a, c} == {'vc', 'vcs'} or {a, c} == {'cb', 'cbs'}:
                    ok_at = bar(133)   # the last chord: an accent on the held note's attack
                else:
                    ok_at = None
                for s0, e0 in spans[a]:
                    for s1, e1 in spans[c]:
                        if s1 >= e0:
                            break
                        if min(e0, e1) - max(s0, s1) > .01 and max(s0, s1) != ok_at:
                            problems.append(f'{a} and {c} both play at beat {max(s0, s1):g} (bar {int(max(s0, s1) // 4) + 1})')
                            break
    groups = [((tid,), most) for tid, most in PLAYERS.items()] + [(('tb', 'tbs', 'tb3'), 3), (('hn_t', 'hn12'), 2)]
    for tids, most in groups:
        tid = '+'.join(tids)
        notes = [n for x in tids for n in TR[x]['notes']]
        ev = sorted([(n['on'], 1) for n in notes] + [(n['on'] + n['duration'] - .01, -1) for n in notes])
        cur = 0
        for when, d in ev:
            cur += d
            if cur > most:
                problems.append(f'{tid}: {cur} notes at beat {when:g} (bar {int(when // 4) + 1}) for {most} players')
                break
    return sorted(set(problems))


LAYERED = ['vn1', 'vn2', 'va', 'vc', 'cb', 'vnt', 'vat', 'fl', 'ob', 'cl', 'bn', 'picc', 'hn_t', 'hn12', 'hn34', 'tp',
           'tb', 'tb3', 'tuba']
LEGATO = {'vn1': 110, 'vn2': 110, 'va': 110, 'vc': 110, 'fl': 70, 'ob': 70, 'cl': 80, 'bn': 80}
SWELL = {'vn1': 6, 'vn2': 4, 'va': 4, 'vc': 5, 'cb': 3, 'fl': 4, 'ob': 4, 'cl': 4, 'bn': 4, 'hn_t': 5, 'hn12': 4,
         'hn34': 4, 'tp': 4, 'tb': 4, 'tb3': 3, 'tuba': 3, 'picc': 2, 'vnt': 3, 'vat': 3}


def dynamics_curve(t, swell):
    """[beat, 0-127] points for a part played on its recorded dynamics: every onset at its loudest note's velocity,
    a small swell inside notes of two beats or more, and the level held to the end of a note that a rest follows."""
    perf = t['performance']['notes']
    loud, ends = {}, {}
    for n in t['notes']:
        b = round(n['on'], 4)
        loud[b] = max(loud.get(b, 0), perf[n['id']]['velocity'])
        ends[b] = max(ends.get(b, 0), n['on'] + n['duration'])
    onsets = sorted(loud)
    pts = {}
    for k, b in enumerate(onsets):
        v = loud[b]
        pts[b] = v
        nxt = onsets[k + 1] if k + 1 < len(onsets) else None
        span = min(nxt, ends[b]) - b if nxt is not None else ends[b] - b
        tail = v
        if span >= 2:
            pts.setdefault(round(b + .45 * span, 4), v + swell)
            tail = v - swell / 2
            pts.setdefault(round(b + .9 * span, 4), tail)
        if nxt is None or nxt > ends[b] + .25:
            pts.setdefault(round(ends[b], 4), tail)
    for seg in DYN.get(t['id'], []):
        lo, hi = seg[0][0], seg[-1][0]
        pts = {b: v for b, v in pts.items() if not lo - 1e-6 <= b <= hi + 1e-6}
        for b, v in seg:
            pts[round(b, 4)] = v
    return [[b, int(max(1, min(127, round(v))))] for b, v in sorted(pts.items())]


def perform(project):
    report = expression.apply(project, {
        'timp': {'timing_sd': 3, 'vel_pct': 2, 'arch': 0},
        'bd': {'timing_sd': 3}, 'cym': {'timing_sd': 3},
        'harp': {'spread': 0, 'lead': 0},
    }, seed=1106, drift='time')
    for tid in LAYERED:
        t = TR.get(tid)
        if t is None or not t['notes']:
            continue
        t['performance']['dynamics'] = dynamics_curve(t, SWELL.get(tid, 4))
        if tid in LEGATO:
            t['performance']['legato'] = {'mode': 'crossfade', 'crossfade_ms': LEGATO[tid], 'gap_ms': 60}
            if tid in ('vn1', 'vn2', 'va', 'vc'):
                t['performance']['legato']['portamento_ms'] = 70
                t['performance']['bow_change_s'] = 4
    for tid in ('hn12', 'hn34'):
        TR[tid]['performance']['round_robin'] = True
    return report


# ------------------------------------------------------------------ 5. the project
DECISIONS = [
    'Key E minor; 4/4; Allegro con fuoco at 140, the singing theme at 90, the coda at 150. 133 bars.',
    'One cell runs through the piece: the fifth above the tonic, the note above it, the note below it, and back '
    '(B, C, A sharp, B). It is the opening gesture, the upper line of the low strings\' figure, the head of the fugato '
    'subject, the climbing turn over the dominant pedal and the close of the coda; harmonised, it is the augmented '
    'sixth C-E-G-A sharp resolving to B.',
    'The opening is bare octaves and silence, no chord until the augmented sixth: stark by having no third.',
    'The singing theme is given to the string sections (first violins; then violins and cellos in octaves; then '
    'violins in octaves with flutes and oboes), never to a solo string instrument. Its second statement is a minor '
    'third higher, in B flat, so its peak (E flat 6 to D6) is the highest the violins go.',
    'Fugato: a three-bar subject, real answers at the fifth, a countersubject, four entries (violas, second '
    'violins, cellos with basses and bassoons, first violins with oboes and flutes) and an episode on the '
    'subject\'s falling cell. A real, not tonal, answer: this is a development, and it should modulate.',
    'The return is prepared by C7 heard as the augmented sixth of E minor and ten bars of dominant pedal.',
    'Parts that share players never sound together (the script checks it): sustained and spiccato strings are '
    'separate tracks of the same desks, horns 1-2 are either hn_t or hn12, and so on.',
    'Mix: the bus chain under the rules of version 2 with wide dynamics (no compression), every part in the hall '
    'at its stage depth with one send. mix.c80_db is 2: the brief asks that the singing theme sound as from a good '
    'seat in the hall, so the clarity is set inside the range Barron (2013) recommends for concert halls (-2 to +2 '
    'dB), at its clear end because of the fugato and the fast low-string figure.',
    'Style: orchestral/romantic. Tempo and rhythm are the piece\'s own choices where the map gives no source.',
    'Review, minor seconds and ninths (about 150 pairs): kept, all three are written tensions. (1) Bars 90-95: C over '
    'the dominant pedal B - the turn\'s upper note, then the ninth of B7b9 beating against its root before the '
    'return. (2) Bars 119-120: F in the trumpets over the tonic pedal E, the Neapolitan against the tonic; E is kept '
    'out of every part but the bass register there. (3) The figure\'s C against a held B is the neighbour note the '
    'whole piece is built on. Each counts once for every pair of doubling parts. The accidental ones the first '
    'reviews found (woodwind lines a semitone from held chord notes at bars 47, 50, 73-77, 84-85, 113) were rewritten.',
    'Review, parallel octaves (about 160 pairs): kept, they are doublings. 118 of the pairs are the gesture\'s B-C in '
    'bars 1 and 98, one line played in octaves by twelve parts; the rest are the figure, the themes and the turn '
    'doubled between sections, in passages too short for review to read as doublings. The real parallels the first '
    'reviews found were rewritten: fifths between violas and second violins at bar 72, octaves between the violas\' '
    'rocking figure and the violins\' run in bars 78-85.',
    'Levels: every part is levelled by its peak (its loudest moment), set from the measured stems of rounds 1-5, so '
    'the tutti balance follows the orchestration guide (brass over strings over woodwinds) and soft passages follow '
    'their written dynamics.',
    'mix.range_lu 13: the piece will be heard on ordinary speakers more than in a hall; the natural range measured '
    '17 LU, with the bridge and the codetta 15-16 LU under the return. The loudest passages keep their level.',
    'Violins: +1.5 dB at 5 kHz and +2.5 dB at 9 kHz, the only equalisation in the mix; the sampled sections and '
    'horns leave the dry mix with almost nothing above 6 kHz.',
]


def build():
    compose()
    for tid in list(ORDER):
        if not TR[tid]['notes']:
            ORDER.remove(tid)
            del TR[tid]
    for t in TR.values():
        t['notes'].sort(key=lambda n: (n['on'], n['pitch']))
    problems = check_players()
    project = {
        'schema': 'music-production/v1',
        'title': TITLE,
        'version': '1.0.' + REVISION,
        'brief': ('A dramatic concert overture for full orchestra, four to five minutes: a stark opening gesture, a '
                  'driving figure in the low strings with timpani and brass over it, a broad singing theme in the '
                  'middle heard as from a good seat in the hall, a development with a fugato, and the opening '
                  'returning at full force to land. Written for the sections, not for soloists.'),
        'style': 'orchestral/romantic',
        'clock': {
            'bars': BARS, 'meter': [4, 4],
            'tempo': [[0, 140], [bar(28), 132], [bar(29), 122], [bar(30), 110], [bar(31), 98], [bar(32), 90],
                      [bar(60), 140], [bar(98), 124], [bar(101), 140], [bar(114), 150]],
            'rubato': {'phrase_ratio': .96, 'phrase_beats': 1, 'final_ratio': .8, 'final_beats': 3, 'q': 2,
                       'spans': [[bar(39) + 2, bar(40), .9], [bar(46), bar(47), .9], [bar(53) + 2, bar(54), .86],
                                 [bar(58), bar(60), .72], [bar(97) + 1, bar(98), .84], [bar(129), bar(131), .7]]},
            'tail_seconds': 12,
        },
        'sections': [{'id': sid, 'start_bar': b - 1, 'bars': n, 'intent': intent} for sid, b, n, intent in SECTIONS],
        'harmony': sorted(HARMONY, key=lambda h: (h['bar'], h['beat'])),
        'decisions': DECISIONS,
        'tracks': [TR[tid] for tid in ORDER],
        'mix': {'chain': 'bus', 'rules': 2, 'dynamics': 'wide', 'target_lufs': -16, 'c80_db': 2, 'range_lu': 13},
    }
    report = perform(project)
    return project, problems, report


if __name__ == '__main__':
    project, problems, report = build()
    out = HERE / 'song.json'
    out.write_text(json.dumps(project, indent=1), encoding='utf-8')
    notes = sum(len(t['notes']) for t in project['tracks'])
    print(f'wrote {out.name}: {len(project["tracks"])} tracks, {notes} notes, {BARS} bars')
    for p in problems:
        print('PLAYERS:', p)
