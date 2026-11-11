#!/usr/bin/env python3
"""Glass Towers, Low Gear -- an original city pop instrumental.

This one script writes every note, performance value and mix setting of song.json.  Run it from anywhere:

    python compose.py            (writes song.json beside this script)

Musical plan (details in NOTES.md and in the project's `decisions`):
- E-flat major, 110 BPM, 4/4, 80 bars; the last two choruses and the outro a whole step up in F.
- Form: intro (brass riff) | verse 1 | pre-chorus | chorus | interlude (riff) | verse 2 | pre-chorus | chorus |
  synth solo | break (key change) | chorus in F | chorus in F with a new peak | outro (riff in F).
- Lead: a Surge XT synth lead; the solo on a second, brighter Surge lead; electric piano chords; sampled
  five-string finger bass; sampled acoustic kit; Surge synth brass stabs; string-machine pad; clean
  electric guitar cutting sixteenths; shaker; a glassy pluck for a few ornaments.
"""
import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# line named the folder where the skill was installed on the machine it ran on).
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import blocks, expression  # noqa: E402
from musiclib.harmony import QUALITIES, parse  # noqa: E402
from musiclib.voicing import LOW_INTERVAL_LIMITS, voice_lead  # noqa: E402
import bisect  # noqa: E402
from musiclib.model import validate  # noqa: E402

TITLE = 'Glass Towers, Low Gear'
SEED = blocks.seed(TITLE)
VERSION = '1.0.r4'
BPM = 110
BARS = 80

# ----------------------------------------------------------------------------------------------- sounds
# Chosen in round 0 from `studio.py sounds ... --seed <piece seed>` shortlists and `studio.py audition`
# (see NOTES.md).  Edit here to change a part's sound.
SOUND = {
    'lead': 'slowboat/leads/turnout',
    'solo': 'luna/leads/tofu_delivery',
    'ep': 'factory/keys/dx_ep',
    'brass': 'factory/brass/plastic_brass',
    'pad': 'jacky_ligon/pads/string_machine_4',
    'glass': 'damon_armani/plucks/glassier',
}

# ----------------------------------------------------------------------------------------------- pitch helpers
NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']


def P(name):
    """'Eb5' -> 75, 'Cb5' -> 71, 'Fb5' -> 76."""
    i, acc = 1, 0
    while i < len(name) and name[i] in 'b#':
        acc += -1 if name[i] == 'b' else 1
        i += 1
    return 12 * (int(name[i:]) + 1) + NAMES[name[0]] + acc


def pcn(s):
    return (NAMES[s[0]] + sum(-1 if c == 'b' else 1 for c in s[1:])) % 12


def tr(symbol, n):
    """Transpose a chord symbol by n semitones, spelled with flats."""
    if n == 0:
        return symbol
    m = re.fullmatch(r'([A-G][b#]?)(.*?)(?:/([A-G][b#]?))?', symbol)
    root, qual, bass = m.groups()
    out = FLAT[(pcn(root) + n) % 12] + qual
    if bass:
        out += '/' + FLAT[(pcn(bass) + n) % 12]
    return out


# ----------------------------------------------------------------------------------------------- form
SECTIONS = [
    ('intro', 0, 4, 'Brass riff (the chorus departure line) previews the chorus cadence over EP, bass and a light groove'),
    ('verse1', 4, 8, 'A-melo: low conversational lead with breaths; EP and bass carry the groove; no brass yet'),
    ('pre1', 12, 4, 'B-melo: rising thirds in the hook rhythm tease the hook, held V bar thins, ii-V of IV pushes in'),
    ('chorus1', 16, 8, 'Sabi: hook stated, restated over new chords, departure up to B-flat 5, minor iv close'),
    ('interlude', 24, 4, 'Brass riff returns with the guitar; turnaround to the verse'),
    ('verse2', 28, 8, 'Verse restated with a higher departure and ending; brass answers; sixteenth hats'),
    ('pre2', 36, 4, 'Pre-chorus with the string pad entering and a fuller build'),
    ('chorus2', 40, 8, 'Chorus with pad, shaker and more brass hits'),
    ('solo', 48, 8, 'Short synth solo over a minor-leaning cycle, quoting the hook, ride cymbal'),
    ('break', 56, 4, 'Reduction: drums thin to rim and hats, D-flat maj9 surprise, ii-V into F'),
    ('chorus3', 60, 8, 'Chorus a whole step up in F: the arrival'),
    ('chorus4', 68, 8, 'Chorus again with a new top (D6, the peak) and a perfect close on the tonic'),
    ('outro', 76, 4, 'Brass riff in F, hook head on the last chord, final ritardando'),
]
SEC = {s[0]: (s[1], s[2]) for s in SECTIONS}


def S(name):
    return SEC[name][0] * 4


def section_at_bar(b):
    for sid, start, n, _ in SECTIONS:
        if start <= b < start + n:
            return sid
    raise ValueError(b)


def one(a):
    return [(0, a)]


def two(a, b):
    return [(0, a), (2, b)]


INTRO = [two('Abmaj9', 'Bb13'), two('Gm7', 'C7b9'), two('Fm9', 'Abm6'), one('Bb9sus4')]
VERSE = [one('Ebmaj9'), two('Gm7', 'Cm9'), one('Abmaj9'), two('Bb9sus4', 'Bb13'),
         two('Gm7', 'C7b9'), two('Fm9', 'Bb13'), one('Ebmaj9'), two('Cm9', 'C7b9')]
PRE = [two('Fm9', 'Gm7'), two('Abmaj9', 'Adim7'), one('Bb9sus4'), two('Bbm9', 'Eb7b9')]
CHORUS = [two('Abmaj9', 'Bb13'), two('Gm7', 'Cm9'), two('Fm9', 'Bb13'), two('Ebmaj9', 'Eb9'),
          two('Abmaj9', 'Bb13'), two('Gm7', 'C7b9'), two('Fm9', 'Abm6'), one('Eb6/9')]
SOLO = [one('Cm9'), two('Fm9', 'Bb13'), two('Ebmaj9', 'Abmaj9'), two('Dm7b5', 'G7b9'),
        two('Cm9', 'Bbm9'), two('Abmaj9', 'Gb13'), two('Fm9', 'Gm7'), two('Abmaj9', 'Bb9sus4')]
BREAK = [one('Ebmaj9'), one('Gm9'), one('Dbmaj9'), two('Cm9', 'F7b9')]
OUTRO = [two('Abmaj9', 'Bb13'), two('Gm7', 'C7b9'), two('Fm9', 'Abm6'), one('Eb6/9')]

PLAN = INTRO + VERSE + PRE + CHORUS + INTRO + VERSE + PRE + CHORUS + SOLO + BREAK + CHORUS + CHORUS + OUTRO
assert len(PLAN) == BARS
KEY_SHIFT = [2 if b >= 60 else 0 for b in range(BARS)]
HARM = [[(beat, tr(sym, KEY_SHIFT[b])) for beat, sym in bar] for b, bar in enumerate(PLAN)]
KEY_PCS = {0: {3, 5, 7, 8, 10, 0, 2}, 2: {5, 7, 9, 10, 0, 2, 4}}

SPANS = []  # (start beat, end beat, symbol)
for b, bar in enumerate(HARM):
    for k, (beat, sym) in enumerate(bar):
        start = b * 4 + beat
        end = b * 4 + (bar[k + 1][0] if k + 1 < len(bar) else 4)
        if SPANS and SPANS[-1][2] == sym and abs(SPANS[-1][1] - start) < 1e-9:
            SPANS[-1] = (SPANS[-1][0], end, sym)
        else:
            SPANS.append((start, end, sym))


def span_index(t):
    for i, (a, b, _) in enumerate(SPANS):
        if a - 1e-6 <= t < b - 1e-6:
            return i
    return len(SPANS) - 1


def chord_at(t):
    return SPANS[span_index(t)][2]


def chord_for(on, dur):
    """The chord a note belongs to: a note that starts at most half a beat before a change and is held over it is
    heard as an anticipation of the next chord."""
    i = span_index(on)
    a, b, sym = SPANS[i]
    if i + 1 < len(SPANS) and on + dur > b + 1e-6 and b - on <= 0.5 + 1e-6:
        return SPANS[i + 1][2]
    return sym


# ----------------------------------------------------------------------------------------------- project
def new_track(tid, name, role, engine, program=0, bank=0, drums=False, **kw):
    t = {'id': tid, 'name': name, 'role': role, 'engine': engine, 'program': program, 'bank': bank, 'drums': drums,
         'range': [0, 127], 'notes': [], 'performance': {'notes': {}}, 'mix': {}}
    t.update(kw)
    return t


def add(t, on, dur, pitch, vel, gate=None, timing=0, phrase=None):
    on = round(on, 4)
    dur = min(dur, BARS * 4 - on)  # nothing is written past the last bar; the tail lets it ring
    bar = int(on // 4 + 1e-9)
    slot = int(round((on - bar * 4) * 12))
    nid = f"{t['id']}_b{bar:03d}s{slot:02d}p{pitch}"
    if nid in t['performance']['notes']:
        return None
    note = {'id': nid, 'on': on, 'duration': round(dur, 4), 'pitch': int(pitch)}
    if phrase:
        note['phrase'] = phrase
    t['notes'].append(note)
    perf = {'velocity': int(max(1, min(127, round(vel))))}
    if gate is not None:
        perf['gate'] = round(gate, 3)
    if timing:
        perf['timing_ms'] = round(timing, 1)
    t['performance']['notes'][nid] = perf
    return nid


def surge(preset, **extra):
    d = {'preset': preset}
    d.update(extra)
    return d


tracks = {}
tracks['lead'] = new_track('lead', 'Synth lead (verse and chorus melody)', 'melody', 'surge', program=81,
                           surge=surge(SOUND['lead']))
tracks['solo'] = new_track('solo', 'Synth solo lead', 'melody', 'surge', program=81, surge=surge(SOUND['solo']))
tracks['ep'] = new_track('ep', 'Electric piano chords', 'harmony', 'surge', program=4, surge=surge(SOUND['ep']))
tracks['bass'] = new_track('bass', 'Electric bass (five-string, fingers)', 'bass', 'soundfont', program=33,
                           soundfont='bass_darkblack', patch={'bank': 0, 'program': 33})
tracks['drums'] = new_track('drums', 'Drum kit', 'drums', 'soundfont', program=0, bank=128, drums=True,
                            soundfont='rusty', patch={'bank': 0, 'program': 0})
tracks['brass'] = new_track('brass', 'Synth brass stabs', 'accent', 'surge', program=62,
                            surge=surge(SOUND['brass']))
tracks['riff'] = new_track('riff', 'Synth brass riff (intro, interlude, outro; doubles the last chorus)', 'melody',
                           'surge', program=62, surge=surge(SOUND['brass']))
tracks['pad'] = new_track('pad', 'String-machine pad', 'texture', 'surge', program=50, surge=surge(SOUND['pad']))
tracks['guitar'] = new_track('guitar', 'Clean electric guitar, cutting', 'rhythm', 'soundfont', program=27,
                             soundfont='fsbs_clean', patch={'bank': 0, 'program': 0})
tracks['shaker'] = new_track('shaker', 'Shaker', 'drums', 'soundfont', program=0, bank=128, drums=True,
                             soundfont='vcsl_world', patch={'bank': 128, 'program': 25})
tracks['glass'] = new_track('glass', 'Glassy pluck ornaments', 'texture', 'surge', program=98,
                            surge=surge(SOUND['glass']))

# ----------------------------------------------------------------------------------------------- melody
VERSE_MEL = [
    # statement (v0-v1): repeated notes, a falling third, an answer that rises to the Cm9 root
    (0.75, 0.25, 'Bb4'), (1.0, 0.5, 'Bb4'), (1.5, 0.5, 'G4'), (2.0, 0.5, 'F4'), (2.5, 1.25, 'G4'),
    (4.75, 0.25, 'F4'), (5.0, 0.5, 'G4'), (5.5, 0.5, 'Bb4'), (6.0, 1.0, 'C5'), (7.0, 0.75, 'Bb4'),
    # restatement (v2-v3): same rhythm a step higher, closing on the dominant
    (8.75, 0.25, 'C5'), (9.0, 0.5, 'C5'), (9.5, 0.5, 'Bb4'), (10.0, 0.5, 'G4'), (10.5, 1.25, 'Bb4'),
    (12.75, 0.25, 'Ab4'), (13.0, 0.5, 'Ab4'), (13.5, 0.5, 'G4'), (14.0, 1.75, 'F4'),
    # departure (v4-v5): a two-beat cell in sequence, D to D-flat over the secondary dominant
    (16.5, 0.25, 'D5'), (16.75, 0.25, 'D5'), (17.0, 0.75, 'Bb4'),
    (18.5, 0.25, 'Db5'), (18.75, 0.25, 'Db5'), (19.0, 0.75, 'Bb4'),
    (20.5, 0.25, 'C5'), (20.75, 0.25, 'C5'), (21.0, 0.75, 'Ab4'),
    (22.5, 0.25, 'C5'), (22.75, 0.25, 'D5'), (23.0, 1.0, 'F5'),
    # conclusion (v6-v7): falls to the third, then a short turn into the pre-chorus
    (24.0, 1.0, 'Eb5'), (25.0, 0.5, 'D5'), (25.5, 0.5, 'Bb4'), (26.0, 1.5, 'G4'),
    (28.5, 0.25, 'Bb4'), (28.75, 0.75, 'C5'), (29.5, 0.5, 'Bb4'), (30.0, 1.0, 'G4'),
]
VERSE2_MEL = [e for e in VERSE_MEL if not (16.0 <= e[0] < 28.0)] + [
    (-0.5, 0.25, 'F4'),
    (16.5, 0.25, 'F5'), (16.75, 0.25, 'F5'), (17.0, 0.75, 'D5'),
    (18.5, 0.25, 'E5'), (18.75, 0.25, 'E5'), (19.0, 0.75, 'Db5'),
    (20.5, 0.25, 'Eb5'), (20.75, 0.25, 'Eb5'), (21.0, 0.75, 'C5'),
    (22.5, 0.25, 'D5'), (22.75, 0.25, 'F5'), (23.0, 1.0, 'Ab5'),
    (24.0, 1.0, 'G5'), (25.0, 0.5, 'F5'), (25.5, 0.5, 'D5'), (26.0, 1.5, 'Bb4'),
]
PRE_MEL = [
    # rising thirds in the hook's 3+3+2 rhythm, a sequence up a third; the second time the hook's head
    # (C Eb G) is heard and turned aside to G-flat over the diminished chord
    (0.0, 0.75, 'Ab4'), (0.75, 0.75, 'C5'), (1.5, 0.5, 'Eb5'), (2.0, 1.0, 'D5'), (3.0, 0.5, 'Bb4'), (3.5, 0.5, 'D5'),
    (4.0, 0.75, 'C5'), (4.75, 0.75, 'Eb5'), (5.5, 0.5, 'G5'), (6.0, 1.0, 'Gb5'), (7.0, 0.5, 'Eb5'), (7.5, 0.5, 'C5'),
    (8.0, 2.0, 'F5'), (10.0, 0.5, 'Eb5'), (10.5, 0.5, 'F5'), (11.0, 1.0, 'Ab5'),
    (12.0, 0.75, 'F5'), (12.75, 0.75, 'Db5'), (13.5, 0.5, 'C5'), (14.0, 1.25, 'Bb4'),
]
CHORUS_MEL = [
    # statement: the hook, C-Eb-G rising to the major seventh of Ab, F F, D pushed over the bar line
    (0.0, 0.75, 'C5'), (0.75, 0.75, 'Eb5'), (1.5, 1.25, 'G5'), (3.0, 0.25, 'F5'), (3.25, 0.25, 'F5'), (3.5, 1.0, 'D5'),
    (4.75, 0.75, 'C5'), (5.5, 1.25, 'Bb4'), (7.5, 0.5, 'Bb4'),
    # restatement: the same head over Fm9, now turning up to G and resting on the tonic
    (8.0, 0.75, 'C5'), (8.75, 0.75, 'Eb5'), (9.5, 1.25, 'G5'), (11.0, 0.25, 'F5'), (11.25, 0.25, 'F5'), (11.5, 1.0, 'G5'),
    (12.75, 0.75, 'F5'), (13.5, 1.25, 'Eb5'), (15.5, 0.5, 'Bb4'),
    # departure: the head a third higher in eighths, up to B-flat 5
    (16.0, 0.5, 'Eb5'), (16.5, 0.5, 'G5'), (17.0, 1.0, 'Bb5'), (18.0, 0.5, 'Ab5'), (18.5, 0.5, 'G5'), (19.0, 0.5, 'F5'),
    (19.5, 1.0, 'G5'), (20.75, 0.25, 'F5'), (21.0, 0.5, 'D5'), (21.5, 0.5, 'Bb4'), (22.0, 0.75, 'E5'), (23.5, 0.5, 'G5'),
    # conclusion: down from A-flat, C-flat over the minor iv, an imperfect close on the third
    (24.0, 0.75, 'Ab5'), (24.75, 0.75, 'G5'), (25.5, 0.5, 'F5'), (26.0, 0.75, 'Eb5'), (26.75, 0.75, 'Cb5'),
    (27.5, 1.5, 'Bb4'), (29.0, 0.5, 'C5'), (29.5, 1.5, 'G4'),
]
CHORUS4_MEL = [e for e in CHORUS_MEL if not (16.0 <= e[0] < 20.0) and e[0] < 27.5] + [
    (16.0, 0.5, 'Eb5'), (16.5, 0.5, 'G5'), (17.0, 0.5, 'Bb5'), (17.5, 1.0, 'C6'), (18.5, 0.5, 'Ab5'), (19.0, 0.5, 'F5'),
    (19.5, 1.0, 'G5'),
    (27.5, 0.5, 'Bb4'), (28.0, 0.5, 'C5'), (28.5, 0.5, 'D5'), (29.0, 3.0, 'Eb5'),
]
BREAK_PICKUP = [(15.0, 0.5, 'A4'), (15.5, 0.5, 'C5')]  # literal pitches over F7b9, into chorus 3 in F
OUTRO_LEAD = [(12.0, 0.75, 'D5'), (12.75, 0.75, 'F5'), (13.5, 2.5, 'A5')]  # the hook's head over Fmaj9
SOLO_MEL = [
    # s0: the solo's own idea (a sixteenth pickup, a held note, a falling answer)
    (0.5, 0.25, 'G4'), (0.75, 0.25, 'Bb4'), (1.0, 0.75, 'C5'), (2.5, 0.25, 'Eb5'), (2.75, 0.25, 'D5'), (3.0, 0.5, 'C5'),
    (3.5, 0.5, 'Bb4'),
    # s1: restated a fourth higher over Fm9 | Bb13
    (4.5, 0.25, 'C5'), (4.75, 0.25, 'Eb5'), (5.0, 0.75, 'F5'), (6.5, 0.25, 'Ab5'), (6.75, 0.25, 'G5'), (7.0, 0.5, 'F5'),
    (7.5, 0.5, 'D5'),
    # s2: the hook's rhythm quoted (D F G, then the repeated note) over Ebmaj9 | Abmaj9
    (8.0, 0.75, 'D5'), (8.75, 0.75, 'F5'), (9.5, 1.25, 'G5'), (11.0, 0.25, 'F5'), (11.25, 0.25, 'F5'), (11.5, 0.5, 'Eb5'),
    (12.0, 0.5, 'F5'), (12.5, 0.5, 'Ab5'), (13.0, 0.25, 'G5'), (13.25, 0.25, 'F5'), (13.5, 0.5, 'D5'),
    (14.0, 0.5, 'B4'), (14.5, 0.25, 'D5'), (14.75, 0.25, 'F5'), (15.0, 0.5, 'Ab5'), (15.5, 0.25, 'F5'), (15.75, 0.25, 'D5'),
    # s4: the idea again, a sixth higher, over Cm9 | Bbm9
    (16.5, 0.25, 'Eb5'), (16.75, 0.25, 'G5'), (17.0, 0.75, 'Bb5'), (18.5, 0.25, 'Db5'), (18.75, 0.25, 'F5'),
    (19.0, 0.5, 'Ab5'), (19.5, 0.25, 'G5'), (19.75, 0.25, 'Ab5'),
    (20.0, 1.0, 'Bb5'), (21.0, 0.25, 'Ab5'), (21.25, 0.25, 'G5'), (21.5, 0.25, 'Eb5'), (21.75, 0.25, 'C5'),
    (22.0, 0.5, 'Db5'), (22.5, 0.25, 'Eb5'), (22.75, 0.25, 'Fb5'), (23.0, 0.5, 'Gb5'), (23.5, 0.5, 'Bb5'),
    (24.0, 0.75, 'Ab5'), (24.75, 0.25, 'G5'), (25.0, 0.5, 'F5'), (25.5, 0.5, 'C5'),
    (26.0, 0.25, 'D5'), (26.25, 0.25, 'F5'), (26.5, 0.25, 'G5'), (26.75, 0.75, 'Bb5'), (27.5, 0.25, 'G5'), (27.75, 0.25, 'F5'),
    (28.0, 1.25, 'G5'), (29.25, 0.25, 'Eb5'), (29.5, 0.25, 'F5'), (29.75, 0.25, 'G5'), (30.0, 1.75, 'F5'),
]
RIFF = [  # the brass riff: the chorus departure line over the intro chords
    (0.0, 0.5, 'Eb5'), (0.5, 0.5, 'G5'), (1.0, 1.0, 'Bb5'), (2.0, 0.5, 'Ab5'), (2.5, 0.5, 'G5'), (3.0, 0.5, 'F5'),
    (3.5, 1.0, 'G5'), (4.75, 0.25, 'F5'), (5.0, 0.5, 'D5'), (5.5, 0.5, 'Bb4'), (6.0, 1.25, 'E5'), (7.5, 0.5, 'G5'),
    (8.0, 0.75, 'Ab5'), (8.75, 0.75, 'G5'), (9.5, 0.5, 'F5'), (10.0, 0.75, 'Eb5'), (10.75, 0.75, 'Cb5'),
    (11.5, 2.5, 'Bb4'),
]


def placed(mel, start, shift=0):
    return [(start + on, dur, P(name) + shift) for on, dur, name in mel]


lead_line = []
lead_line += placed(VERSE_MEL, S('verse1'))
lead_line += placed(PRE_MEL, S('pre1'))
lead_line += placed(CHORUS_MEL, S('chorus1'))
lead_line += placed(VERSE2_MEL, S('verse2'))
lead_line += placed(PRE_MEL, S('pre2'))
lead_line += placed(CHORUS_MEL, S('chorus2'))
lead_line += placed(BREAK_PICKUP, S('break'))
lead_line += placed(CHORUS_MEL, S('chorus3'), 2)
lead_line += placed(CHORUS4_MEL, S('chorus4'), 2)
lead_line += placed(OUTRO_LEAD, S('outro'))
lead_line.sort()
solo_line = sorted(placed(SOLO_MEL, S('solo')))


def melodic_velocity(on, dur, sec):
    base = {'verse1': 84, 'verse2': 88, 'pre1': 84, 'pre2': 87, 'chorus1': 94, 'chorus2': 96, 'chorus3': 99,
            'chorus4': 101, 'break': 84, 'outro': 90, 'solo': 96, 'interlude': 84}[sec]
    pos = on % 1
    if dur >= 1.0:
        base += 4
    if pos in (0.25, 0.75) and dur <= 0.25:
        base -= 8
    elif pos == 0.0:
        base += 2
    return base


for on, dur, pitch in lead_line:
    sec = section_at_bar(int(on // 4))
    gate = 0.82 if dur <= 0.25 else (0.92 if dur <= 0.5 else 0.98)
    add(tracks['lead'], on, dur, pitch, melodic_velocity(on, dur, sec), gate=gate, phrase=sec)
for on, dur, pitch in solo_line:
    gate = 0.85 if dur <= 0.25 else 0.95
    add(tracks['solo'], on, dur, pitch, melodic_velocity(on, dur, 'solo'), gate=gate, phrase='solo')


def melody_notes_between(a, b):
    """Notes of the foreground (lead, solo, and the brass riff where it leads) sounding in [a, b)."""
    out = []
    for line in (lead_line, solo_line, riff_line):
        for on, dur, p in line:
            if on < b and on + dur > a:
                out.append((on, dur, p))
    return out


# brass riff in intro, interlude and outro (the outro a whole step up, ending on F major 9)
riff_line = []
riff_line += placed(RIFF, S('intro'))
riff_line += placed(RIFF, S('interlude'))
outro_riff = [e for e in RIFF if e[0] < 11.5] + [(11.5, 4.5, 'Bb4')]
riff_line += placed(outro_riff, S('outro'), 2)
riff_line += [e for e in placed(CHORUS4_MEL, S('chorus4'), 2) if e[0] >= S('chorus4') + 16]
riff_line.sort()

# ----------------------------------------------------------------------------------------------- bass


def chord_info(sym):
    c = parse(sym)
    iv = QUALITIES[c['quality']]
    third = next((i for i in (4, 3, 5, 2) if i in iv), 4)
    fifth = 6 if (6 in iv and 7 not in iv) else 7
    seventh = next((i for i in (10, 11, 9) if i in iv), 12)
    return c['root'], third, fifth, seventh


def place_pc(pc, near, lo=28, hi=44):
    cands = [p for p in range(lo, hi + 1) if p % 12 == pc]
    return min(cands, key=lambda p: (abs(p - near), p))


BASS_T = {
    'riff': [(0, .75, 'R', 104), (1.0, .25, 'G', 18), (1.5, .5, 'O', 90), (2.0, .75, 'R', 100), (2.75, .25, 'O', 86),
             (3.0, .25, 'G', 18), (3.5, .5, 'APP', 94)],
    'riff_end': [(0, 1.5, 'R', 104), (2.0, .25, 'O', 88), (2.5, .5, '5', 92), (3.0, .5, 'O', 88), (3.5, .5, 'APP', 94)],
    'verse_1': [(0, 1.0, 'R', 104), (1.5, .25, 'G', 18), (1.75, .5, '5', 90), (2.5, .5, 'O', 88), (3.0, .25, 'G', 18),
                (3.5, .5, 'APP', 92)],
    'verse_2': [(0, 1.0, 'R', 104), (1.5, .4, 'O', 88), (2.0, 1.0, 'R', 100), (3.0, .25, 'G', 18), (3.25, .25, '5', 86),
                (3.5, .5, 'APP', 92)],
    'pre': [(0, .4, 'R', 100), (.5, .4, 'R', 84), (1.0, .4, 'O', 90), (1.5, .4, 'R', 84), (2.0, .4, 'R', 98),
            (2.5, .4, 'R', 84), (3.0, .4, 'O', 90), (3.5, .4, 'APP', 90)],
    'chorus_1': [(0, .5, 'R', 108), (.75, .25, 'O', 90), (1.0, .25, 'G', 18), (1.5, .5, '5', 94), (2.0, .5, 'R', 102),
                 (2.75, .25, 'O', 88), (3.0, .25, 'G', 18), (3.25, .25, '5', 88), (3.5, .5, 'APP', 96)],
    'chorus_2': [(0, .5, 'R', 108), (.75, .25, 'O', 92), (1.0, .25, '7', 86), (1.5, .5, '5', 94), (2.0, .5, 'R', 104),
                 (2.5, .25, 'O', 90), (2.75, .25, 'G', 18), (3.0, .25, '5', 88), (3.5, .5, 'APP', 96)],
    'solo': [(0, .5, 'R', 106), (.75, .25, 'O', 90), (1.25, .25, 'G', 18), (1.5, .25, '5', 92), (1.75, .25, 'O', 86),
             (2.0, .5, 'R', 102), (2.75, .25, '3', 88), (3.0, .25, '5', 88), (3.5, .5, 'APP', 94)],
}


def bass_template(bar):
    sec = section_at_bar(bar)
    k = bar - SEC[sec][0]
    nchords = len(HARM[bar])
    if sec in ('intro', 'interlude', 'outro'):
        if sec == 'outro' and k == 3:
            return [(0, 4.0, 'R', 100)]
        return BASS_T['riff_end'] if k == 3 else BASS_T['riff']
    if sec.startswith('verse'):
        return BASS_T['verse_2'] if nchords == 2 else BASS_T['verse_1']
    if sec.startswith('pre'):
        return [(0, 3.0, 'R', 100), (3.0, .5, 'O', 88), (3.5, .5, 'APP', 90)] if k == 2 else BASS_T['pre']
    if sec.startswith('chorus'):
        return BASS_T['chorus_2'] if sec != 'chorus1' else BASS_T['chorus_1']
    if sec == 'solo':
        return BASS_T['solo']
    if sec == 'break':
        return [[(0, 3.5, 'R', 96), (3.5, .5, 'APP', 86)],
                [(0, 3.0, 'R', 94), (3.0, .5, '5', 84), (3.5, .5, 'APP', 86)],
                [(0, 2.0, 'R', 96), (2.0, 1.0, '5', 86), (3.0, .5, 'O', 84), (3.5, .5, 'APP', 88)],
                [(0, 1.0, 'R', 98), (1.0, .5, '5', 88), (1.5, .5, 'O', 86), (2.0, 1.0, 'R', 100), (3.0, .5, '3', 88),
                 (3.5, .5, 'APP', 94)]][k]
    raise ValueError(sec)


RUN_BARS = set()
for sid, start, n, _ in SECTIONS:
    if sid.startswith(('verse', 'chorus')) or sid == 'solo':
        RUN_BARS |= {start + 3, start + 7}
    if sid.startswith('pre'):
        RUN_BARS.add(start + 1)
RUN_BARS -= {75}            # the last chorus holds its tonic into the outro
PUSH_BARS = {15, 39, 59}    # the bass anticipates the chorus downbeat with the brass

def fg_at(t):
    """The foreground pitch sounding at beat t (lead or solo), or None."""
    for line in (lead_line, solo_line):
        for on, dur, p in line:
            if on - 1e-6 <= t < on + dur - 1e-6:
                return p
    return None


def approach_ok(c, target, t, t_next):
    """An approach note that neither rubs a semitone (or minor ninth) against the melody nor moves with it in
    parallel fifths or octaves into the next root."""
    m1, m2 = fg_at(t), fg_at(t_next)
    if m1 is not None and (abs(m1 - c) % 12 in (1, 11)) and (max(m1, c) - min(m1, c)) % 12 == 1:
        return False
    if m1 is not None and m2 is not None and m1 != m2 and c != target:
        i1, i2 = (m1 - c) % 12, (m2 - target) % 12
        if i1 == i2 and i1 in (0, 7):
            return False
    return True


bass = tracks['bass']
prev = 39
bass_events = []
for bar in range(BARS):
    tmpl = bass_template(bar)
    nxt_sym = HARM[bar + 1][0][1] if bar + 1 < BARS else HARM[bar][0][1]
    roots = {}
    for beat, sym in HARM[bar]:
        r, _, _, _ = chord_info(sym)
        roots[beat] = place_pc(r, prev)
        prev = roots[beat]
    nr = place_pc(parse(nxt_sym)['root'], prev)
    shift = KEY_SHIFT[bar + 1] if bar + 1 < BARS else KEY_SHIFT[bar]
    scale = sorted(KEY_PCS[shift])
    events = list(tmpl)
    if bar in RUN_BARS:
        events = [e for e in events if e[0] < 3.0] + [(3.0, .25, 'G', 18), (3.25, .25, 'RUN3', 90), (3.5, .25, 'RUN2', 92),
                                                      (3.75, .25, 'RUN1', 94)]
    if bar in PUSH_BARS:
        events = [e for e in events if e[0] < 3.5] + [(3.5, 1.0, 'PUSH', 106)]
    for on, dur, kind, vel in events:
        t = bar * 4 + on
        sym = chord_at(t)
        beat_key = max(b for b, _ in HARM[bar] if b <= on + 1e-9)
        root = roots[beat_key]
        r, third, fifth, seventh = chord_info(sym)
        if kind == 'R':
            p = root
        elif kind == 'G':
            p = root
        elif kind == 'O':
            p = root + 12
        elif kind == '5':
            p = root + fifth if root + fifth <= 50 else root + fifth - 12
        elif kind == '3':
            p = root + third
        elif kind == '7':
            p = root + seventh - 12 if root + seventh > 50 else root + seventh
        elif kind == 'APP':
            pcs = parse(sym)['pcs']
            cands = [nr + d for d in (-2, 2) if (nr + d) % 12 in pcs]
            cands += [nr + d for d in (-2, 2) if (nr + d) % 12 in KEY_PCS[shift] and nr + d not in cands]
            cands.append(nr - 1)
            p = next((c for c in cands if approach_ok(c, nr, t, (bar + 1) * 4)), cands[0])
        elif kind.startswith('RUN'):
            k = int(kind[3:])
            below = [q for q in range(nr - 1, nr - 12, -1) if q % 12 in KEY_PCS[shift]]
            p = below[k - 1]
        elif kind == 'PUSH':
            p = nr
        bass_events.append((t, dur, p, vel, kind))

# a note pushed over the bar line replaces the next bar's downbeat note
push_targets = {(bar + 1) * 4 for bar in PUSH_BARS}
bass_events = [e for e in bass_events if not (e[0] in push_targets and e[4] != 'PUSH')]
for t, dur, p, vel, kind in bass_events:
    gate = 0.5 if kind == 'G' else (0.9 if dur >= 1 else 0.82)
    add(bass, t, dur, p, vel, gate=gate)

bass_line = [(t, d, p) for t, d, p, v, k in bass_events]


def bass_between(a, b):
    return [p for t, d, p in bass_line if t < b and t + d > a]


# ----------------------------------------------------------------------------------------------- electric piano
EP_SET = {
    'intro': ('syncopated', .35, .55, 'phrase', 1.25), 'verse1': ('syncopated', .35, .5, 'phrase', 1.5),
    'pre1': ('held', .5, .6, 'changes', 4.0), 'chorus1': ('syncopated', .55, .7, 'changes', 1.0),
    'interlude': ('syncopated', .45, .65, 'phrase', 1.0), 'verse2': ('syncopated', .45, .55, 'phrase', 1.25),
    'pre2': ('held', .5, .65, 'changes', 4.0), 'chorus2': ('syncopated', .6, .75, 'changes', 1.0),
    'solo': ('syncopated', .3, .6, 'phrase', 1.0), 'break': ('held', .3, .45, 'none', 4.0),
    'chorus3': ('syncopated', .6, .8, 'changes', 1.0), 'chorus4': ('syncopated', .65, .85, 'changes', 1.0),
    'outro': ('held', .4, .6, 'none', 4.0),
}
ep = tracks['ep']
ep_records = {}
for k, (sid, start, n, _) in enumerate(SECTIONS):
    figure, cx, inten, push, maxlen = EP_SET[sid]
    a, b = start * 4, (start + n) * 4
    chords = [HARM[bar] for bar in range(start, start + n)]
    mel = [{'on': on - a, 'duration': dur, 'pitch': p} for on, dur, p in melody_notes_between(a, b)]
    bas = [{'on': t - a, 'duration': d, 'pitch': p} for t, d, p in bass_line if a <= t < b]
    res = None
    for voices, low in ((4, 52), (3, 52), (3, 50)):  # four rootless voices above E3; three where the melody dips
        try:
            res = blocks.accompaniment(chords, [4, 4], seed=SEED + 101 + k, figure=figure, complexity=cx,
                                       intensity=inten, low=low, high=74, voices=voices, push=push,
                                       melody=mel or None, bass=bas)
            break
        except ValueError:
            continue
    ep_records[sid] = {'voices': voices, 'low': low}
    ep_records[sid].update({kk: vv for kk, vv in res['record'].items() if kk in ('figure', 'push')})
    notes = sorted(res['notes'], key=lambda x: x['on'])
    onsets = sorted({round(x['on'], 4) for x in notes})
    for x in notes:
        later = [o for o in onsets if o > x['on'] + 1e-6]
        room = (later[0] - x['on']) if later else (b - a - x['on'])
        dur = min(max(x['duration'], min(room * .94, maxlen)), room * .98)
        if sid == 'outro' and x['on'] >= 12:
            dur = 4.0
        add(ep, a + x['on'], dur, x['pitch'], x['velocity'], gate=0.95)

# ----------------------------------------------------------------------------------------------- brass


def brass_voicing(top, sym, n=3):
    c = parse(sym)
    pcs = c['pcs']
    if top % 12 not in pcs:
        return [top - 12, top]
    voices = [top]
    p = top - 2
    while len(voices) < n and p > top - 15:
        gap = voices[-1] - p
        ok = p % 12 in pcs and gap >= 3 and all((v - p) % 12 not in (1, 11) or (v - p) == 11 for v in voices)
        ok = ok and all((v - p) not in (1, 13) for v in voices)
        if ok:
            voices.append(p)
        p -= 1
    return sorted(voices)


brass = tracks['brass']
riff = tracks['riff']
RIFF_TOPS = set()
for on, dur, top in riff_line:
    sym = chord_for(on, dur)
    sec = section_at_bar(int(on // 4))
    long_note = dur >= 1.0
    vel = 100 if long_note else 92
    if sec == 'outro':
        vel += 4
    if sec == 'chorus4':
        vel -= 6
    gate = 0.8 if long_note else 0.62
    for p in brass_voicing(top, sym, 3):
        nid = add(riff, on, dur, p, vel - (0 if p == top else 8), gate=gate)
        if p == top:
            RIFF_TOPS.add(nid)

# stabs: (beat within section, length, velocity)
CHORUS_STABS_A = [(0.0, .5, 104), (2.0, .25, 90), (3.5, .75, 98), (10.0, .25, 90), (11.5, .75, 96), (15.5, .75, 100),
                  (22.0, .25, 92), (26.0, .25, 92), (27.5, .75, 98), (31.0, .25, 94), (31.5, .75, 98)]
CHORUS_STABS_B = CHORUS_STABS_A + [(6.0, .25, 88), (14.0, .25, 90), (18.0, .25, 92), (30.0, .25, 90)]
VERSE2_STABS = [(3.75, .25, 86), (7.5, .75, 92), (12.0, .25, 86), (12.5, .25, 88), (15.5, .75, 94), (27.5, .25, 88),
                (28.0, .5, 92)]
PRE_STABS = [(14.0, .25, 94), (15.5, .75, 104)]
SOLO_STABS = [(0.0, .5, 100), (14.0, .25, 92), (15.5, .75, 96), (30.0, 1.5, 92)]
stab_plan = []
for sid, stabs in (('verse2', VERSE2_STABS), ('pre1', PRE_STABS), ('pre2', PRE_STABS), ('chorus1', CHORUS_STABS_A),
                   ('chorus2', CHORUS_STABS_B), ('solo', SOLO_STABS), ('chorus3', CHORUS_STABS_B),
                   ('chorus4', [x for x in CHORUS_STABS_B if x[0] < 16 or x[0] in (27.5, 31.0, 31.5)])):
    for on, dur, vel in stabs:
        stab_plan.append((S(sid) + on, dur, vel, sid))
# the held swell on the pre-chorus's dominant bar
for sid in ('pre1', 'pre2'):
    stab_plan.append((S(sid) + 8.0, 3.75, 72 if sid == 'pre1' else 80, sid))
stab_plan.sort()
syms = [chord_for(on, dur) for on, dur, _, _ in stab_plan]
against, ceilings = [], []
for (on, dur, vel, sid) in stab_plan:
    mel = melody_notes_between(on, on + dur)
    against.append([p for _, _, p in mel] + bass_between(on, on + dur))
    ceilings.append(max(65, min(p for _, _, p in mel) - 3) if mel else 79)
brass_v = voice_lead(syms, voices=4, low=55, high=79, against=against, ceilings=ceilings)
for (on, dur, vel, sid), voicing in zip(stab_plan, brass_v):
    gate = 0.6 if dur <= .75 else 0.9
    for p in voicing:
        add(brass, on, dur, p, vel, gate=gate)

# ----------------------------------------------------------------------------------------------- guitar
gtr = tracks['guitar']
GTR_SECTIONS = ('chorus1', 'verse2', 'chorus2', 'chorus3', 'chorus4')
GTR_PATTERN = [(0.5, .15, 84), (1.25, .1, 60), (1.5, .15, 88), (2.5, .15, 84), (3.25, .1, 60), (3.5, .15, 88)]
g_hits = []
for bar in range(BARS):
    sec = section_at_bar(bar)
    if sec not in GTR_SECTIONS or (sec == 'chorus3' and bar < SEC['chorus3'][0] + 4):
        continue
    pattern = GTR_PATTERN if sec != 'verse2' else [e for e in GTR_PATTERN if e[2] > 70]
    for on, dur, vel in pattern:
        g_hits.append((bar * 4 + on, dur, vel))
g_syms = [chord_at(t) for t, _, _ in g_hits]
g_against, g_ceil = [], []
for t, d, v in g_hits:
    mel = melody_notes_between(t, t + d)
    g_against.append([p for _, _, p in mel] + bass_between(t, t + d))
    g_ceil.append(max(67, min(p for _, _, p in mel) - 2) if mel else 76)
g_v = voice_lead(g_syms, voices=3, low=55, high=76, against=g_against, ceilings=g_ceil)
for (t, d, v), voicing in zip(g_hits, g_v):
    for p in voicing:
        add(gtr, t, d, p, v, gate=0.45)

# ----------------------------------------------------------------------------------------------- vertical hygiene
# Parts are voiced in dependency order (melody, bass, brass, electric piano, guitar, pad, ornaments).  A note of a
# later part that sounds a minor second or ninth (at any octave) against an earlier part for a quarter beat or more,
# or that sits closer above the bass than its low interval limit, moves an octave or is left out.  The one tension
# kept on purpose: the flat nine of a 7(b9) chord over its root in the bass.


def rubs(lo, hi):
    return hi > lo and (hi - lo) % 12 == 1


def b9_ok(lo, hi, t):
    c = parse(chord_at(t))
    return c['quality'] == '7b9' and lo % 12 == c['root'] and hi % 12 == (c['root'] + 1) % 12


class Sounding:
    def __init__(self, tids):
        self.items = sorted((n['on'], n['on'] + n['duration'], n['pitch'], tid)
                            for tid in tids for n in tracks[tid]['notes'])
        self.starts = [x[0] for x in self.items]
        self.maxdur = max((x[1] - x[0] for x in self.items), default=0)

    def overlapping(self, a, b, least=0.25):
        i = bisect.bisect_left(self.starts, a - self.maxdur - 1e-6)
        j = bisect.bisect_left(self.starts, b)
        for x in self.items[i:j]:
            if min(b, x[1]) - max(a, x[0]) >= least - 1e-9:
                yield x


def bad(p, a, b, idx):
    for oa, ob, q, tid in idx.overlapping(a, b):
        if q == p:
            continue
        lo, hi = min(p, q), max(p, q)
        if rubs(lo, hi) and not (tid == 'bass' and q == lo and b9_ok(lo, hi, max(a, oa))):
            return True
        if tid == 'bass' and q < p:
            lim = LOW_INTERVAL_LIMITS.get(p - q)
            if lim is not None and q < lim:
                return True
    return False


HYGIENE = {}


def clean_track(tid, higher, protect=frozenset(), lo_lim=50, hi_lim=79):
    t = tracks[tid]
    idx = Sounding(higher)
    moved, dropped = 0, 0
    groups = {}
    for n in t['notes']:
        groups.setdefault(round(n['on'], 4), []).append(n)
    for on, grp in groups.items():
        for n in list(grp):
            a, b = n['on'], n['on'] + n['duration']
            if n['id'] in protect or not bad(n['pitch'], a, b, idx):
                continue
            others = [m['pitch'] for m in grp if m is not n]
            alt = next((x for x in (n['pitch'] + 12, n['pitch'] - 12)
                        if lo_lim <= x <= hi_lim and x not in others and not bad(x, a, b, idx)
                        and not any(rubs(min(x, o), max(x, o)) for o in others)), None)
            perf = t['performance']['notes'].pop(n['id'])
            t['notes'].remove(n)
            grp.remove(n)
            if alt is not None:
                add(t, n['on'], n['duration'], alt, perf['velocity'], gate=perf.get('gate'))
                grp.append(t['notes'][-1])
                moved += 1
            else:
                dropped += 1
    HYGIENE[tid] = {'moved_an_octave': moved, 'left_out': dropped}


def untangle(tid, lo_lim=50):
    t = tracks[tid]
    groups = {}
    for n in t['notes']:
        groups.setdefault(round(n['on'], 4), []).append(n)
    count = 0
    for grp in groups.values():
        changed = True
        while changed:
            changed = False
            grp.sort(key=lambda n: n['pitch'])
            for i, lo in enumerate(grp):
                if any(rubs(lo['pitch'], hi['pitch']) for hi in grp[i + 1:]):
                    t['performance']['notes'].pop(lo['id'])
                    t['notes'].remove(lo)
                    grp.remove(lo)
                    count += 1
                    changed = True
                    break
    HYGIENE.setdefault(tid, {})['semitones_inside_chords'] = count


clean_track('riff', ['lead', 'solo', 'bass'], protect=RIFF_TOPS)
clean_track('brass', ['lead', 'solo', 'bass', 'riff'])
clean_track('ep', ['lead', 'solo', 'bass', 'riff', 'brass'], lo_lim=52, hi_lim=76)
clean_track('guitar', ['lead', 'solo', 'bass', 'riff', 'brass', 'ep'], lo_lim=55, hi_lim=79)
for tid in ('brass', 'ep', 'guitar'):
    untangle(tid)

# ----------------------------------------------------------------------------------------------- pad
# Voiced last of the chord parts, each span checked against everything already written; a tone common to two
# chords is held over the change rather than struck again.
pad = tracks['pad']
PAD_SECTIONS = ('pre2', 'chorus2', 'solo', 'break', 'chorus3', 'chorus4', 'outro')
pad_spans = [sp for sp in SPANS if section_at_bar(int(sp[0] // 4)) in PAD_SECTIONS]
p_syms = [sp[2] for sp in pad_spans]
p_against, p_ceil = [], []
for a, b, sym in pad_spans:
    mel = melody_notes_between(a, b)
    p_against.append([p for _, _, p in mel] + bass_between(a, b))
    p_ceil.append(max(64, min(p for _, _, p in mel) - 3) if mel else 74)
pad_v = voice_lead(p_syms, voices=4, low=53, high=74, against=p_against, ceilings=p_ceil)
pad_idx = Sounding(['lead', 'solo', 'bass', 'riff', 'brass', 'ep', 'guitar'])
PAD_VEL = {'pre2': 70, 'chorus2': 80, 'solo': 72, 'break': 76, 'chorus3': 86, 'chorus4': 90, 'outro': 82}
active, pad_notes, pad_left_out = {}, [], 0
for (a, b, sym), voicing in zip(pad_spans, pad_v):
    sec = section_at_bar(int(a // 4))
    keep = [p for p in voicing if not bad(p, a, b, pad_idx)]
    pad_left_out += len(voicing) - len(keep)
    new_active = {}
    for p in keep:
        if p in active and abs(active[p][1] - a) < 1e-6:
            note = active[p]
            note[1] = b
        else:
            note = [a, b, p, PAD_VEL[sec]]
            pad_notes.append(note)
        new_active[p] = note
    active = new_active
for a, b, p, vel in pad_notes:
    add(pad, a, b - a, p, vel, gate=1.0)
HYGIENE['pad'] = {'left_out': pad_left_out}

# ----------------------------------------------------------------------------------------------- shaker
shk = tracks['shaker']
SHK_SECTIONS = ('pre2', 'chorus2', 'chorus3', 'chorus4')
for bar in range(BARS):
    if section_at_bar(bar) not in SHK_SECTIONS or (section_at_bar(bar) == 'chorus3' and bar < SEC['chorus3'][0] + 4):
        continue
    for i in range(16):
        vel = [52, 30, 66, 36][i % 4]
        add(shk, bar * 4 + i * .25, .2, 71, vel, gate=0.6)

# ----------------------------------------------------------------------------------------------- glass pluck
glass = tracks['glass']
GLASS = [  # (section, beat, length, pitch name)
    ('intro', 13.0, .25, 'F6'), ('intro', 13.25, .25, 'Eb6'), ('intro', 13.5, .25, 'C6'), ('intro', 13.75, .25, 'Bb5'),
    ('intro', 14.0, .5, 'Ab5'), ('intro', 14.5, 1.0, 'F5'),
    ('break', 1.0, .5, 'Bb5'), ('break', 1.5, .5, 'D6'), ('break', 2.0, .5, 'F6'), ('break', 2.5, 1.0, 'G6'),
    ('break', 5.0, .5, 'A5'), ('break', 5.5, .5, 'D6'), ('break', 6.0, 1.5, 'F6'),
    ('break', 8.5, .5, 'C6'), ('break', 9.0, .5, 'Ab5'), ('break', 9.5, .5, 'F5'), ('break', 10.0, 1.5, 'Eb5'),
    ('outro', 14.0, .5, 'F5'), ('outro', 14.5, .5, 'A5'), ('outro', 15.0, .5, 'C6'), ('outro', 15.5, .5, 'D6'),
]
for sid, on, dur, name in GLASS:
    add(glass, S(sid) + on, dur, P(name), 80, gate=0.9)
clean_track('glass', ['lead', 'solo', 'bass', 'riff', 'brass', 'ep', 'guitar', 'pad'], lo_lim=60, hi_lim=96)

# ----------------------------------------------------------------------------------------------- drums
sections = [{'id': s[0], 'start_bar': s[1], 'bars': s[2], 'intent': s[3]} for s in SECTIONS]
ids = [s[0] for s in SECTIONS]


def per(default, **over):
    return {i: over.get(i, default) for i in ids}


groove = blocks.drums(
    bars=BARS, meter=[4, 4], seed=SEED, sections=sections,
    feel=per('soul', chorus1='funk', chorus2='funk', solo='funk', chorus3='funk', chorus4='funk'),
    backbeat=per('normal', **{'break': 'none'}),
    kick=per('syncopated', chorus4='four_floor', **{'break': 'none'}),
    pulse=per('sixteenth', intro='eighth', verse1='eighth', pre1='eighth', interlude='eighth', outro='eighth',
              chorus4='offbeat', **{'break': 'quarter'}),
    cymbal=per('closed_hat', solo='ride', chorus4='open_hat'),
    complexity=per(.45, intro=.3, verse1=.35, interlude=.3, chorus1=.55, chorus2=.6, solo=.6, chorus3=.6, chorus4=.65, outro=.3,
                   **{'break': .1}),
    intensity=per(.6, intro=.5, verse1=.5, pre1=.6, chorus1=.75, interlude=.55, verse2=.55, pre2=.65, chorus2=.8,
                  solo=.6, chorus3=.85, chorus4=.9, outro=.6, **{'break': .3}),
    fills=.45)
drum_record = {k: v for k, v in groove['record'].items() if k in ('seed', 'typical', 'feel')}
dr = tracks['drums']
brk_a, brk_b = S('break'), S('chorus3')
final_bar = (BARS - 1) * 4
dn = [n for n in groove['notes'] if not (brk_a <= n['on'] < brk_b) and n['on'] < final_bar]
# crashes on the arrivals
for sid in ('interlude', 'chorus1', 'chorus2', 'solo', 'chorus3', 'chorus4', 'outro', 'verse2'):
    t = S(sid)
    if not any(n['pitch'] in (49, 57) and abs(n['on'] - t) < .05 for n in dn):
        dn.append({'on': t, 'duration': .5, 'pitch': 49 if sid != 'verse2' else 57, 'velocity': 104})
    if not any(n['pitch'] in (35, 36) and abs(n['on'] - t) < .05 for n in dn):
        dn.append({'on': t, 'duration': .25, 'pitch': 36, 'velocity': 100})
# the break: hats and rim, then a snare build into the key change
B = brk_a
brk = []
for bar in range(4):
    base = B + bar * 4
    brk.append((base, 36, 74))
    hats = [0, 1, 2, 3] if bar < 2 else ([0, .5, 1, 1.5, 2, 2.5, 3, 3.5] if bar == 2 else [0, .5, 1, 1.5])
    for h in hats:
        brk.append((base + h, 42, 46 if h % 1 else 58))
    if bar in (1, 2):
        brk.append((base + 1, 37, 62))
    if bar < 3:
        brk.append((base + 3, 37, 66))
for i in range(8):
    brk.append((B + 14 + i * .25, 38, 40 + i * 8))
brk.append((B + 15.5, 36, 92))
for t, p, v in brk:
    dn.append({'on': t, 'duration': .25, 'pitch': p, 'velocity': v})
for sid in ('pre1', 'pre2'):
    a = S(sid) + 8
    dn = [n for n in dn if not (a <= n['on'] < a + 4) or n['pitch'] in (42, 44, 46)]
    dn.append({'on': a, 'duration': .25, 'pitch': 36, 'velocity': 88})
# the last bar: crash and kick, then the chord rings
dn.append({'on': final_bar, 'duration': 1.0, 'pitch': 49, 'velocity': 106})
dn.append({'on': final_bar, 'duration': .5, 'pitch': 36, 'velocity': 104})
dn.sort(key=lambda n: (n['on'], n['pitch']))
for n in dn:
    timing = 0
    pos = n['on'] % 4
    if n['pitch'] in (38, 40) and abs(pos - 1) < .01 or n['pitch'] in (38, 40) and abs(pos - 3) < .01:
        timing = 7  # a backbeat that sits back
    add(dr, n['on'], n['duration'], n['pitch'], n['velocity'], timing=timing)

# ----------------------------------------------------------------------------------------------- performance
swing16 = {'ratio': 0.54, 'unit': 0.25}
for tid in ('drums', 'bass', 'ep', 'guitar', 'shaker', 'brass', 'riff'):
    tracks[tid]['performance']['swing'] = dict(swing16)
for tid in ('lead', 'solo'):
    tracks[tid]['performance']['swing'] = {'ratio': 0.52, 'unit': 0.25}
    tracks[tid]['performance']['offset_ms'] = 6

# ----------------------------------------------------------------------------------------------- mix
MIX = {
    'lead': {'level_dbfs': -15.5, 'level_mode': 'active_rms', 'pan': 0, 'highpass': 150, 'reverb_db': -19,
             'delay_db': -24, 'delay_quarters': 0.75,
             'automation': [[0, 0], [S('pre1') - 0.25, 0], [S('pre1'), -2], [S('chorus1') - 0.25, -2],
                            [S('chorus1'), 0], [S('pre2') - 0.25, 0], [S('pre2'), -2], [S('chorus2') - 0.25, -2],
                            [S('chorus2'), 0]]},
    'solo': {'level_dbfs': -15, 'level_mode': 'active_rms', 'pan': 0, 'highpass': 150, 'reverb_db': -19,
             'delay_db': -21, 'delay_quarters': 0.75, 'width': 0.45},
    'ep': {'level_dbfs': -24, 'level_mode': 'active_rms', 'pan': -0.22, 'highpass': 90, 'reverb_db': -20,
           'bus': 'rhythm', 'eq': [[300, -1.5]]},
    'bass': {'level_dbfs': -18.5, 'level_mode': 'active_rms', 'pan': 0, 'highpass': 18, 'reverb_db': None,
             'eq': [[55, 2.0], [250, -1.5]]},
    'drums': {'level_dbfs': -19, 'level_mode': 'active_rms', 'pan': 0, 'highpass': 30, 'reverb_db': -24,
              'eq': [[60, 2.0]]},
    'brass': {'level_dbfs': -23, 'level_mode': 'active_rms', 'pan': 0.15, 'highpass': 160, 'reverb_db': -17},
    'riff': {'level_dbfs': -18, 'level_mode': 'active_rms', 'pan': 0.08, 'highpass': 160, 'reverb_db': -18},
    'pad': {'level_dbfs': -30, 'level_mode': 'active_rms', 'pan': 0, 'highpass': 220, 'reverb_db': -16,
            'automation': [[S('pre2'), -6], [S('chorus2'), 0], [S('solo'), -3], [S('chorus3'), 0]]},
    'guitar': {'level_dbfs': -28.5, 'level_mode': 'active_rms', 'pan': 0.42, 'highpass': 100, 'reverb_db': -22},
    'shaker': {'level_dbfs': -29.5, 'level_mode': 'active_rms', 'pan': 0.35, 'highpass': 400, 'reverb_db': -24},
    'glass': {'level_dbfs': -29, 'level_mode': 'active_rms', 'pan': -0.3, 'highpass': 300, 'reverb_db': -14,
              'delay': {'beats': 0.75, 'feedback': 0.35, 'send_db': -9}},
}
for tid, m in MIX.items():
    tracks[tid]['mix'] = m

# ----------------------------------------------------------------------------------------------- assemble
for t in tracks.values():
    pitches = [n['pitch'] for n in t['notes']]
    t['range'] = [min(pitches), max(pitches)]
    t['notes'].sort(key=lambda n: (n['on'], n['pitch']))

harmony = []
for a, b, sym in SPANS:
    bar = int(a // 4)
    harmony.append({'bar': bar + 1, 'beat': round(a - bar * 4, 4), 'symbol': sym})

project = {
    'schema': 'music-production/v1',
    'title': TITLE,
    'version': VERSION,
    'brief': ('City pop instrumental, about three minutes: a night drive through a lit city. A groove that sits '
              'back, an electric bass that moves, electric piano chords rich in sevenths and ninths, bright synth '
              'brass stabs, and a tune one remembers after one hearing. The lead is a synthesizer (never a sampled '
              'saxophone or guitar). A verse, a chorus and a short solo.'),
    'style': {'primary': 'jpop/city-pop', 'borrow': {'tempo': 'pop/disco'}},
    'clock': {'bars': BARS, 'meter': [4, 4], 'tempo': [[0, BPM]], 'tail_seconds': 8,
              'rubato': {'final_ratio': 0.82, 'final_beats': 6, 'phrase_ratio': 1.0, 'phrase_beats': 1, 'q': 2}},
    'sections': sections,
    'harmony': harmony,
    'tracks': list(tracks.values()),
    'mix': {'chain': 'bus', 'rules': 2, 'target_lufs': -14},
    'decisions': [
        'Style: jpop/city-pop for every axis but tempo. Its tempo cell has no source, so tempo is borrowed from '
        'pop/disco (Harmonix funk/disco songs: median 119 BPM, middle 80% 109-131): city pop\'s rhythm trait names '
        'funk and disco, and 110 BPM sits at the low end of that range for a groove that sits back.',
        'Melody and form have no source in the city pop entry: the brief gives verse, chorus and solo and about three '
        'minutes; climax-and-melody.md and arrangement.md give the srdc chorus, phrases with breaths, a peak saved '
        'for the last chorus, and the J-pop family\'s A-melo / B-melo / sabi turn.',
        'Key E-flat major; the last two choruses and the outro a whole step up in F, prepared by a break that thins '
        'the band, turns to D-flat maj9 and takes ii-V into the new IV.',
        'Chorus harmony starts from the royal road (IVM7-V7-iii7-vi) of the J-pop family, then goes its own way: '
        'ii9-V13-Imaj9-I9 and a minor iv (Abm6) before the tonic 6/9.',
        'Hook: C-Eb-G rising to the major seventh of A-flat on a 3+3+2 sixteenth rhythm, then a repeated F and a D '
        'pushed over the bar line; restated over Fm9 (same notes, new colour), sequenced a third higher for the '
        'departure; the pre-chorus teases its head and turns it aside.',
        'The intro, interlude and outro riff on synth brass is the chorus departure line, so the tune is heard '
        'before the chorus arrives.',
        'Groove: blocks.drums soul feel in verses, funk feel in choruses and the solo (more ghost notes), ride in the '
        'solo, eighth hats in verse 1 and sixteenths from verse 2; snare backbeats 7 ms late and a 0.54 sixteenth '
        'swing in the rhythm section, the leads swung less and 6 ms behind.',
        'Bass: written by template per section, root on the One, octaves, ghost notes (velocity 18 plays the '
        'bank\'s ghost samples), whole-step approaches from a chord tone into each change, diatonic sixteenth runs '
        'at phrase ends, and pushes with the brass into each chorus.',
        'Electric piano: blocks.accompaniment syncopated comping (held in pre-choruses and the break), answering the '
        'melody and the bass, voiced rootless under the melody, notes lengthened to the next hit.',
        'Layers held back: brass stabs from the pre-chorus and verse 2; guitar from chorus 1; pad and shaker from '
        'pre-chorus 2; the melody\'s D6 only in chorus 4.',
    ],
    'authorship': {'composer': 'Claude (AI), working alone with the music-production skill 0.6.0',
                   'script': 'compose.py'},
    'revision_history': [
        {'version': '1.0.r1', 'change': 'First complete draft; its render stopped on the quiet-tail check.'},
        {'version': '1.0.r2', 'change': 'Tail 8 s; voicing hygiene in dependency order; pad holds common tones; '
                                        'bass approaches chosen against the lead; solo states and restates an idea; '
                                        'interlude lighter, without guitar; final chord F6/9; high-passes lowered.'},
        {'version': '1.0.r3', 'change': 'Lead +1.5 dB and solo +2 dB over a lighter backing; bass lower and fuller; '
                                        'pre-chorus V bar thinned; chorus 3 opens lighter, chorus 4 disco kick with '
                                        'open hats and the brass doubling the melody; riff on its own melody part.'},
        {'version': '1.0.r4', 'change': 'Chorus phrases given breaths; lead 2 dB down through the pre-choruses; '
                                        'semitones inside EP, brass and guitar chords removed.'},
    ],
}

expression.apply(project, overrides={'bass': {'feel': 5}, 'brass': {'spread': 3}, 'guitar': {'strum': 3},
                                     'riff': {'spread': 3, 'arch': 3},
                                     'glass': None},
                 seed=SEED, drift='time')

if __name__ == '__main__':
    validate(project)
    out = HERE / 'song.json'
    out.write_text(json.dumps(project, indent=1), encoding='utf-8')
    counts = {t['id']: len(t['notes']) for t in project['tracks']}
    print(out, counts)
    print('EP blocks:', json.dumps(ep_records))
    print('drums:', json.dumps(drum_record)[:400])
    print('hygiene:', json.dumps(HYGIENE))
