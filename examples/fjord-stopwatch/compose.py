"""Fjord Stopwatch: a 48-bar lo-fi beat, 78 BPM, 4/4, home key F major.

Every note of song.json is written here (round 2 of the piece; round 1 is kept in song_v1.json).
Run:  python compose.py     (writes song.json next to this file)

The musiclib helpers used are the skill's own: harmony.parse for chord tones, expression.apply for player-like
timing and dynamics, model.validate and save_json for the file.
"""
import itertools
import sys
from pathlib import Path

# Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
# line named the folder of a copy of the skill on the machine it ran on).
SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
if SKILL:
    sys.path.insert(0, str(SKILL))
from musiclib import expression, harmony  # noqa: E402
from musiclib.model import save_json, validate  # noqa: E402

HERE = Path(__file__).resolve().parent
TITLE = 'Fjord Stopwatch (lo-fi beat for late reading)'
SEED = 2655898359
TEMPO = 78
BARS = 48
TOTAL = BARS * 4.0
WORDS = ['fjord', 'pulley', 'stopwatch', 'plywood', 'balloon', 'simmer', 'wagon', 'cheek', 'canvas', 'ooze',
         'nettle', 'patio']

# Scenes of eight bars, in the order of the night. A = kettle, stopwatch, patio; B = pulley, wagon; C = balloon.
FORM = [('kettle', 'A', 0), ('pulley', 'B', 8), ('stopwatch', 'A', 16), ('wagon', 'B', 24),
        ('balloon', 'C', 32), ('patio', 'A', 40)]

# Chords per bar of each scene: (beat offset in the bar, symbol). A ends on the tonic, so the loop closes F -> F.
CHORD_BARS = {
    'A': [[(0, 'Fmaj9')], [(0, 'Em7'), (2, 'A7')], [(0, 'Dm9'), (2, 'G7')], [(0, 'Cm7'), (2, 'F7')],
          [(0, 'Bbmaj7')], [(0, 'Am7'), (2, 'D7')], [(0, 'Gm7'), (2, 'C7')], [(0, 'Fmaj9')]],
    'B': [[(0, 'Dm9')], [(0, 'Dbmaj7')], [(0, 'Cm7'), (2, 'F7')], [(0, 'Bbm7'), (2, 'Eb7')], [(0, 'Abmaj7')],
          [(0, 'Dm7'), (2, 'G7')], [(0, 'Cm7'), (2, 'F7')], [(0, 'C7')]],
    'C': [[(0, 'Dm9')], [(0, 'Bm7b5'), (2, 'E7')], [(0, 'Am7'), (2, 'D7')], [(0, 'Gm7'), (2, 'C7')],
          [(0, 'Fmaj9')], [(0, 'Ebmaj7')], [(0, 'Ab7')], [(0, 'Dm7'), (2, 'G7')]],
}

CHANGES = []  # (beat, symbol), in time order
for _name, _letter, _start in FORM:
    for _i, _entries in enumerate(CHORD_BARS[_letter]):
        for _off, _sym in _entries:
            CHANGES.append(((_start + _i) * 4.0 + _off, _sym))

SEC_OF_BAR = {}
for _name, _letter, _start in FORM:
    for _i in range(8):
        SEC_OF_BAR[_start + _i] = (_name, _i)


def chord_index(beat):
    idx = 0
    for i, (b, _) in enumerate(CHANGES):
        if b <= beat + 1e-9:
            idx = i
    return idx


def next_change(beat):
    for b, sym in CHANGES:
        if b > beat + 1e-9:
            return b, sym
    return None


# ---- piano: rootless voicings that move little and clash with nothing sounding under them --------------------
def realize(sym, prev, others, lo=52, hi=72):
    """Rootless tones of `sym` in the piano's range. A tone may be left out (never more than one of four) when every
    placement of the full chord clashes with a flute or bass note sounding under it (round 2's clashes: the ninth of
    Dm9 against the flute's F)."""
    h = harmony.parse(sym)
    all_tones = sorted(pc for pc in h['pcs'] if pc != h['root'])
    drops = [None] + (list(range(len(all_tones))) if len(all_tones) == 4 else [])
    best, best_score = None, None
    for drop in drops:
        tones = [pc for k, pc in enumerate(all_tones) if k != drop]
        options = [[p for p in range(lo, hi + 1) if p % 12 == pc] for pc in tones]
        for combo in itertools.product(*options):
            notes = sorted(combo)
            spread = notes[-1] - notes[0]
            if spread > 19:
                continue
            # a minor second or minor ninth (1 or 13 semitones) with another note of the piano or the bass and flute
            clash = sum(1 for a, b in itertools.combinations(notes, 2) if abs(a - b) % 12 == 1)
            clash += sum(1 for n in notes for m in others if abs(n - m) % 12 == 1)
            move = 0 if prev is None else sum(min(abs(n - q) for q in prev) for n in notes)
            score = 100 * clash + move + 0.25 * spread + (8 if drop is not None else 0)
            if best_score is None or score < best_score:
                best, best_score = notes, score
    return best


KEYS_PATTERN = {  # a hit ends before the bass's chromatic approach (3.5), so the two never sound together
    'kettle': [(0.0, 2.0, 70), (2.5, 1.0, 62)],
    'pulley': [(1.5, 1.5, 66), (3.0, 0.5, 60)],
    'stopwatch': [(0.0, 2.0, 76), (2.5, 1.0, 66)],
    'wagon': [(1.0, 1.0, 58), (3.0, 0.5, 54)],       # sparser and softer: the wagon thins the piano too
    'balloon': [(0.0, 4.0, 58)],
    'patio': [(0.0, 2.0, 72), (2.5, 1.0, 62)],
}

# ---- bass: round upright, roots and fifths with a chromatic approach into the next chord -----------------------
BASS_PATTERN = {
    'kettle': [(0.0, 'R', 1.5, 76), (2.0, '5', 1.0, 66), (3.5, 'A', 0.5, 64)],
    'pulley': [(0.0, 'R', 1.0, 80), (1.5, 'O', 0.5, 62), (2.5, '5', 1.0, 70), (3.5, 'A', 0.5, 64)],
    'stopwatch': [(0.0, 'R', 1.5, 80), (2.0, '5', 1.0, 70), (3.0, 'R', 0.5, 64), (3.5, 'A', 0.5, 66)],
    'wagon': [(0.0, 'R', 1.0, 78), (1.0, 'O', 1.0, 62), (2.5, '5', 1.0, 70), (3.5, 'A', 0.5, 64)],
    'balloon': [(0.0, 'R', 3.0, 70)],
    'patio': [(0.0, 'R', 1.5, 80), (2.0, '5', 1.0, 70), (3.0, 'R', 0.5, 64), (3.5, 'A', 0.5, 66)],
}


def bass_pattern(name, i):
    if name == 'kettle' and i < 4:
        return [(0.0, 'R', 3.5, 70)]
    if name == 'patio' and 4 <= i < 7:
        return [(0.0, 'R', 3.5, 66)]
    if name == 'patio' and i == 7:   # the last bar: no approach note under the flute's F; the fifth instead
        return [(0.0, 'R', 2.0, 72), (2.5, '5', 1.5, 68)]
    return BASS_PATTERN[name]


def bass_place(pc, near, lo=36, hi=52):
    cands = [p for p in range(lo, hi + 1) if p % 12 == pc]
    return min(cands, key=lambda p: abs(p - near))


# ---- drums: a 16-step bar on the kit's GM keys (rusty: 36 kick, 37 side stick, 38 snare, 42 hat, 46 open hat) ----
def hat_steps(vs=1.0, open_at=False):
    out = []
    for s in range(0, 16, 2):
        if s == 14 and open_at:
            out.append((14, 46, 62))
            continue
        v = 64 if s % 4 == 0 else 50
        out.append((s, 42, round(v * vs)))
    out += [(7, 42, 26), (15, 42, 22)]     # ghost hats on the off-sixteenths: the swing has notes to move
    return out


def stopwatch_steps(i):
    s = [(0, 36, 98), (10, 36, 82), (4, 37, 86), (12, 37, 90)]
    if i % 2 == 1:
        s.append((14, 36, 44))
    if i % 2 == 0:
        s.append((7, 38, 22))
    return s + hat_steps(open_at=(i % 4 == 3))


def drum_steps(name, i):
    if name == 'kettle':
        if i < 4:   # the kettle scene: hats and a soft side stick, so the drums are on from the loop's first bar
            return [(0, 42, 40), (4, 42, 34), (8, 42, 40), (12, 42, 34), (4, 37, 40), (12, 37, 44)]
        return [(0, 36, 70), (4, 37, 58), (12, 37, 62)] + hat_steps(0.8)
    if name == 'pulley':
        s = [(0, 36, 96), (6, 36, 74), (12, 36, 84), (4, 37, 80), (12, 37, 84)]
        if i % 2 == 1:
            s.append((15, 38, 24))
        return s + hat_steps()
    if name == 'stopwatch':
        return stopwatch_steps(i)
    if name == 'wagon':
        if i < 4:   # half time: the wagon's wheels, a kick on 1 and a side stick on 3, quarter hats
            s = [(0, 36, 96), (8, 36, 84), (8, 37, 86), (0, 42, 60), (4, 42, 50), (8, 42, 58), (12, 42, 50)]
            if i % 2 == 1:
                s.append((14, 38, 30))
            return s
        if i < 7:
            return [(0, 36, 96), (10, 36, 80), (4, 37, 86), (12, 37, 90)] + hat_steps(open_at=(i == 6))
        return [(0, 36, 96), (4, 37, 86), (12, 37, 88), (13, 38, 40), (14, 38, 52), (15, 38, 66)]
    if name == 'balloon':
        if i < 2:
            return [(0, 42, 58), (4, 42, 54), (8, 42, 58), (12, 42, 54)]
        if i < 4:
            return []
        return [(0, 36, 96), (10, 36, 80), (4, 37, 86), (12, 37, 90)] + hat_steps(open_at=(i == 7))
    if name == 'patio':
        if i < 4:
            return stopwatch_steps(i)
        if i < 7:
            return [(0, 36, 92), (12, 37, 88)]
        return [(0, 36, 96), (4, 37, 86), (12, 37, 90), (9, 38, 30), (11, 38, 40), (13, 38, 52), (14, 38, 58),
                (15, 38, 66)]
    raise KeyError(name)


DRUM_DUR = {36: 0.5, 37: 0.25, 38: 0.2, 42: 0.2, 46: 0.6}
WAGON_START, WAGON_END, WAGON_GAIN = 24, 32, 0.92   # bars of the wagon scene and its velocity scale

# ---- flute: the hook (a fourth up, then down by step), its answer, and the phrases of the other scenes -------
# (offset in beats from the phrase start, duration, MIDI pitch, velocity). Quarter-beat attacks are chord tones of
# the chords under them; passing tones sit on the off-beats and step to the next note.
HOOK = [(0.0, 1.5, 72, 88), (1.5, 0.5, 76, 84), (2.0, 2.0, 77, 92), (4.0, 1.0, 74, 86), (5.0, 1.0, 71, 84),
        (6.0, 2.0, 69, 88)]
ANSWER = [(0.0, 1.5, 72, 86), (1.5, 0.5, 76, 82), (2.0, 1.5, 77, 92), (3.5, 0.5, 76, 84), (4.0, 1.0, 75, 86),
          (5.0, 1.0, 72, 82), (6.0, 2.0, 69, 84)]
COLD = [(0.0, 1.5, 65, 86), (1.5, 0.5, 67, 80), (2.0, 2.0, 69, 90), (4.0, 1.0, 65, 84), (5.0, 1.0, 68, 82),
        (6.0, 2.0, 72, 88)]
COLD_ANSWER = [(0.0, 2.0, 72, 84), (2.0, 2.0, 75, 88), (4.0, 1.0, 77, 88), (5.0, 1.0, 74, 84), (6.0, 2.0, 71, 86)]
BALLOON_HOOK = [(0.0, 1.5, 84, 88), (1.5, 0.5, 88, 82), (2.0, 2.0, 89, 92), (4.0, 1.0, 86, 86), (5.0, 1.0, 83, 86),
                (6.0, 2.0, 86, 88)]
BALLOON_ANSWER = [(0.0, 1.5, 84, 84), (1.5, 0.5, 88, 80), (2.0, 1.5, 89, 90), (3.5, 0.5, 88, 82), (4.0, 1.0, 86, 86),
                  (5.0, 1.0, 82, 82), (6.0, 2.0, 79, 84)]
FRAG = [(0.0, 1.5, 72, 86), (1.5, 0.5, 76, 82), (2.0, 2.0, 77, 90)]
LEAD_PLAN = [(16, HOOK), (18, ANSWER),                 # stopwatch: the hook, its answer, rest
             (24, COLD), (28, COLD_ANSWER),           # wagon: the same shape over the cold chords
             (32, BALLOON_HOOK), (36, BALLOON_ANSWER),  # balloon: an octave up, after two bars without drums
             (40, HOOK), (42, ANSWER),                # patio: the hook home
             (47, FRAG)]                              # the last bar: a question that the first bar answers


def lead_events():
    out = []
    for bar, phrase in LEAD_PLAN:
        for off, dur, pitch, vel in phrase:
            out.append((bar * 4.0 + off, dur, pitch, vel))
    return out


def bass_events():
    out = []
    prev = 43
    for gbar in range(BARS):
        name, i = SEC_OF_BAR[gbar]
        for off, kind, dur, vel in bass_pattern(name, i):
            t = gbar * 4.0 + off
            ci = chord_index(t)
            root = harmony.parse(CHANGES[ci][1])['root']
            if kind == 'A':
                nxt = next_change(t)
                target = harmony.parse(nxt[1] if nxt else CHANGES[0][1])['root']
                pitch = bass_place((target - 1) % 12, prev)
            else:
                pc = (root + 7) % 12 if kind == '5' else root
                pitch = bass_place(pc, prev)
                if kind == 'O' and pitch + 12 <= 55:
                    pitch += 12
            prev = pitch
            nxt = next_change(t)
            end = nxt[0] if nxt else TOTAL
            out.append((t, min(dur, end - t - 0.05), pitch, vel))
    return out


def drum_events():
    out = []
    for gbar in range(BARS):
        name, i = SEC_OF_BAR[gbar]
        for step, pitch, vel in drum_steps(name, i):
            out.append((gbar * 4.0 + step / 4.0, DRUM_DUR[pitch], pitch, vel, ))
    return out


def keys_events(others_events):
    """Comping on each hit, voiced against the bass and flute sounding under it."""
    out = []
    last = None
    cc = []
    for gbar in range(BARS):
        name, i = SEC_OF_BAR[gbar]
        pattern = KEYS_PATTERN[name]
        if name == 'patio' and i >= 4:
            pattern = [(0.0, 3.5, 62)]
        for off, dur, vel in pattern:
            t = gbar * 4.0 + off
            ci = chord_index(t)
            nxt = next_change(t)
            end = nxt[0] if nxt else TOTAL
            eff = min(dur, end - t - 0.05)
            under = [p for on, d, p, v in others_events if on < t + eff - 1e-9 and on + d > t + 1e-9]
            last = realize(CHANGES[ci][1], last, under)
            for p in last:
                out.append((t, eff, p, vel))
        cc += [[gbar * 4.0, 64, 0], [gbar * 4.0 + 0.1, 64, 100], [gbar * 4.0 + 3.85, 64, 0]]
    return out, cc


class Part:
    def __init__(self, ident, name, role, engine, rng, program=None, soundfont=None, drums=False, mix=None,
                 performance=None, patch=None):
        self.t = {'id': ident, 'name': name, 'role': role, 'engine': engine, 'drums': drums, 'range': list(rng),
                  'notes': [], 'performance': {'notes': {}, 'cc': []}, 'mix': mix or {}}
        if program is not None:
            self.t['program'] = program
            self.t['bank'] = 0
        if soundfont:
            self.t['soundfont'] = soundfont
        if patch:
            self.t['patch'] = patch
        if performance:
            self.t['performance'].update(performance)
        self._ids = set()

    def note(self, on, dur, pitch, vel, gate=1.0, phrase='', articulation='normal'):
        if WAGON_START * 4 <= on < WAGON_END * 4 and self.t['id'] != 'vinyl':
            vel = vel * WAGON_GAIN   # the wagon scene is written a little softer than the stopwatch before it
        base = f"{self.t['id']}_t{round(on * 48):05d}_p{pitch}"
        ident, k = base, 2
        while ident in self._ids:
            ident = f'{base}_{k}'
            k += 1
        self._ids.add(ident)
        self.t['notes'].append({'id': ident, 'on': round(on, 6), 'duration': round(dur, 6), 'pitch': int(pitch),
                                'phrase': phrase, 'articulation': articulation})
        self.t['performance']['notes'][ident] = {'velocity': int(max(1, min(127, vel))), 'timing_ms': 0,
                                                 'gate': gate}
        return ident


def build():
    harmony_list = [{'bar': int(b // 4) + 1, 'beat': round(b % 4, 3), 'symbol': sym} for b, sym in CHANGES]
    bass_ev = bass_events()
    lead_ev = lead_events()
    keys_ev, keys_cc = keys_events([(on, d, p, v) for on, d, p, v in bass_ev] +
                                   [(on, d, p, v) for on, d, p, v in lead_ev])

    keys = Part('keys', 'Upright piano, rootless comping', 'harmony', 'soundfont', (48, 84), program=3,
                soundfont='vcsl_keys',
                mix={'level_dbfs': -25, 'level_mode': 'active_rms', 'pan': -0.12, 'bus': 'rhythm',
                     'space': 'room', 'highpass': 110, 'lowpass': 5200, 'reverb_db': -20,
                     'eq': [[1000, -2.0]],
                     'wow_flutter': {'wow_cents': 8, 'wow_hz': 0.55, 'flutter_cents': 2, 'flutter_hz': 7},
                     'duck': {'by': 'drums', 'keys': [36], 'depth_db': 2.5, 'attack_ms': 8, 'hold_ms': 60,
                              'release_ms': 220}})
    bass = Part('bass', 'Upright bass, round and laid back', 'bass', 'soundfont', (34, 62), program=32,
                soundfont='bass_sneaky',
                mix={'level_dbfs': -20.5, 'level_mode': 'active_rms', 'pan': 0.0, 'highpass': 35,
                     'lowpass': 2600, 'reverb_db': None, 'saturate': 0.15})
    drums = Part('drums', 'Drum kit, side stick and closed hats, worn', 'drums', 'soundfont', (35, 59), program=0,
                 soundfont='rusty', drums=True, patch={'bank': 0, 'program': 0},
                 mix={'level_dbfs': -22, 'level_mode': 'active_rms', 'pan': 0.0, 'highpass': 40,
                      'lowpass': 9000, 'reverb_db': -28, 'saturate': 0.25,
                      'effects': [{'type': 'bitcrush', 'bits': 12, 'downsample': 2, 'mix': 0.6}]},
                 performance={'swing': {'ratio': 0.58, 'unit': 0.25}})
    lead = Part('lead', 'Flute, the hook', 'melody', 'soundfont', (59, 98), program=73, soundfont='vsco',
                mix={'level_dbfs': -19, 'level_mode': 'active_rms', 'pan': 0.15, 'highpass': 200,
                     'lowpass': 8000, 'reverb_db': -16,
                     'wow_flutter': {'wow_cents': 10, 'wow_hz': 0.5, 'flutter_cents': 3, 'flutter_hz': 8}},
                performance={'legato': {'max_interval': 5, 'glide_ms': 25, 'gap_ms': 40, 'max_notes': 4},
                             'bend_range': 7})
    vinyl = Part('vinyl', 'Vinyl surface noise, whole piece', 'effect', 'noise', (0, 127),
                 mix={'level_dbfs': -30, 'level_mode': 'peak', 'pan': 0.0, 'reverb_db': None})

    for on, d, p, v in keys_ev:
        keys.note(on, d, p, v, gate=1.0)
    keys.t['performance']['cc'] = keys_cc
    for on, d, p, v in bass_ev:
        bass.note(on, d, p, v, gate=0.95)
    for on, d, p, v in drum_events():
        drums.note(on, d, p, v, gate=0.9)
    for on, d, p, v in lead_ev:
        lead.note(on, d, p, v, gate=1.0, phrase='hook')
    vinyl.note(0.0, TOTAL, 60, 80, gate=1.0, articulation='vinyl')

    tracks = [keys.t, bass.t, drums.t, lead.t, vinyl.t]
    project = {
        'schema': 'music-production/v1',
        'title': TITLE,
        'version': '1.0.r2',
        'brief': ('A lo-fi hip-hop beat for reading late at night, about two and a half minutes, looping without '
                  'a seam: a worn upright piano over jazzy seventh chords, a round upright bass, a laid-back swung '
                  'drum kit and a little tape and vinyl character. Four or five parts; one simple melodic idea '
                  'that keeps coming back.'),
        'clock': {'bars': BARS, 'meter': [4, 4], 'tempo': [[0, TEMPO]], 'tail_seconds': 4},
        'sections': [{'id': name, 'start_bar': start, 'bars': 8, 'intent': INTENT[name]}
                     for name, _letter, start in FORM],
        'tracks': tracks,
        'mix': {'chain': 'bus', 'rules': 2, 'target_lufs': -14, 'dynamics': 'glue', 'mono_below_hz': 100,
                'wow_flutter': {'wow_cents': 4, 'wow_hz': 0.5, 'flutter_cents': 1, 'flutter_hz': 6}},
        'loop': {'start_bar': 0},
        'style': 'beats/lo-fi',
        'harmony': harmony_list,
        'association': {
            'source': 'draw', 'seed': SEED, 'words': WORDS,
            'whole': ('A late reader on a plywood floor over a fjord-side harbour. A pulley outside lifts a wagon of '
                      'nets; the stopwatch on the sill times a kettle that simmers. A red balloon, lost from the '
                      'harbour fair, drifts past the patio door and its string brushes the canvas awning; nettles '
                      'grow through the paving and ooze from an old paint tin in the gutter. The reader rests a cheek '
                      'on one hand while the balloon rises and comes down again and the night goes on.'),
            'gives': [
                {'level': 'form', 'what': 'six scenes of eight bars in the order of the night: kettle, pulley, '
                                          'stopwatch, wagon, balloon, patio', 'where': 'all sections'},
                {'level': 'rhythm', 'what': 'the pulley creaks in 3+3+2 eighths (kick on steps 0, 6, 12) in the '
                                            'pulley and wagon scenes; the stopwatch ticks evenly on the hats',
                 'where': 'bars 8-15, 24-31; bars 16-23 and 40-43'},
                {'level': 'melody', 'what': 'the balloon: a fourth up from C5 to F5, then down by step to A4, the '
                                            'hook; the wagon plays the same shape over the cold chords',
                 'where': 'bars 16-19, 24-29, 32-43, 47'},
                {'level': 'harmony', 'what': 'the cold fjord turn: D-flat major seventh and the B-flat minor and '
                                             'E-flat seventh colour in the pulley and wagon scenes; the balloon '
                                             'climbs down a circle of fifths', 'where': 'bars 8-15, 24-31, 32-39'},
                {'level': 'sounds', 'what': 'wood and canvas: a side stick, a worn upright piano, an upright bass and '
                                            'a flute for the balloon', 'where': 'all sections'},
                {'level': 'mix', 'what': 'the canvas muffles the top: piano low-passed at 5.2 kHz, tape wobble on '
                                         'the piano and flute, vinyl hiss under the whole piece',
                 'where': 'all sections'},
            ]},
        'plan': {
            'identity': 'a two-bar hook for the flute that floats up a fourth and falls back by step, over a piano '
                         'that answers with rootless sevenths; the B scenes turn cold by a half step.',
            'high_point': {'section': 'balloon', 'means': 'the hook an octave up on the flute, after two bars '
                                                          'with the drums out'},
            'sections': [
                {'section': 'kettle', 'sounds': ['keys', 'bass', 'drums', 'vinyl'], 'leads': 'keys',
                 'differs': 'no lead; soft hats and a side stick from the first bar, the full kit on bar 5'},
                {'section': 'pulley', 'sounds': ['keys', 'bass', 'drums', 'vinyl'], 'leads': 'drums',
                 'answers': ['bass'], 'dynamics': 'louder', 'harmony': 'same',
                 'differs': 'the 3+3+2 kick, the full kit and the cold harmony; still no lead'},
                {'section': 'stopwatch', 'sounds': ['keys', 'bass', 'drums', 'vinyl', 'lead'], 'leads': 'lead',
                 'answers': ['keys'], 'register': {'lead': 'higher'}, 'dynamics': 'louder',
                 'differs': 'the flute enters with the hook and the full hat groove'},
                {'section': 'wagon', 'sounds': ['keys', 'bass', 'drums', 'vinyl', 'lead'], 'leads': 'lead',
                 'register': {'lead': 'lower'}, 'dynamics': 'softer',
                 'differs': 'half-time drums and quarter hats, the cold hook, the piano thins to two hits a bar, a fill'},
                {'section': 'balloon', 'sounds': ['keys', 'bass', 'drums', 'vinyl', 'lead'], 'leads': 'lead',
                 'register': {'lead': 'higher'}, 'harmony': 'same', 'dynamics': 'same',
                 'differs': 'the flute an octave up; two bars with no drums before the answer'},
                {'section': 'patio', 'sounds': ['keys', 'bass', 'drums', 'vinyl', 'lead'], 'leads': 'lead',
                 'register': {'lead': 'lower'}, 'dynamics': 'same',
                 'differs': 'the hook back in its home register, then a question on bar 47 that leads back '
                            'to the first bar'},
            ]},
        'decisions': [
            'Tempo 78 BPM, 48 bars (2:28 at this tempo), home key F major; the B scenes borrow D-flat and '
            'B-flat minor colours from the words (fjord, the cold turn).',
            'Upright piano (vcsl_keys 0:3, Upright Yamaha) comps rootless voicings on each hit, voiced against the bass '
            'and flute so that no minor second or ninth sounds under them (round 2); pedal once a bar, low-passed at '
            '5.2 kHz, given tape wobble; the drum bus ducks it on the kick (2.5 dB).',
            'Upright bass (bass_sneaky 0:32): roots, fifths, an octave, and a chromatic approach into the next chord; '
            'it sits on the rhythm of the piece, not a copy of the kick.',
            'Drum kit rusty as one melodic bank (bank 0, program 0: a single kit), side stick on 2 and 4, closed hats '
            'with ghost hats on the off-sixteenths, swing 0.58 on sixteenths (the words stopwatch and kettle), a 12-bit '
            'bitcrush and saturation as the SP-1200 grit.',
            'Flute (vsco 0:73), legato with a 5-semitone window; each hook is one line of connected notes.',
            'Vinyl: one noise note across the piece, peak-leveled at -30 dBFS.',
            'Loop from bar 0: the drums are on from the first bar (soft); bar 47 is the F-major question that the first '
            'bar answers; no fade at either end.',
            'loop_seam.timbre: the flute ends its question on bar 47 and rests through the loop\'s first bar; it returns '
            'on bar 16 with the hook. The piano, bass, drums and vinyl carry the join, and the flute\'s silence over '
            'bars 0-15 is the kettle scene by design. Kept on purpose.',
            'plan:balloon: the balloon keeps the wagon\'s loudness (its mean written velocity is within three counts of '
            'the wagon\'s). Its height comes from the register, the octave up, and from the two bars without drums; '
            'the plan now says so, where it first said softer.',
        ],
    }
    expression.apply(project, overrides={'bass': {'feel': 6}}, seed=SEED, drift='time')
    return project


INTENT = {
    'kettle': 'Kettle: keys, bass and soft drums with the vinyl; the full kit on bar 5',
    'pulley': 'Pulley: cold B harmony, the 3+3+2 kick; no lead',
    'stopwatch': 'Stopwatch: the hook on the flute with the full hat groove',
    'wagon': 'Wagon: half-time wheels and the cold hook; the piano thins; a fill at the end',
    'balloon': 'Balloon: the hook an octave up; two bars without drums',
    'patio': 'Patio: the hook home and a question that leads back to bar 0',
}


if __name__ == '__main__':
    p = build()
    result = validate(p)
    warnings = result.get('warnings', []) if isinstance(result, dict) else []
    print('validate:', 'ok', '| warnings:', warnings if warnings else 'none')
    save_json(HERE / 'song.json', p)
    n = sum(len(t['notes']) for t in p['tracks'])
    print('wrote', HERE / 'song.json', '| tracks', len(p['tracks']), '| notes', n)
