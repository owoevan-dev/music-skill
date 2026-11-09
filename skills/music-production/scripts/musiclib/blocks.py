"""Arrangement building blocks: a drum groove, a bass line and an accompaniment written as plain notes from the piece's
own settings, for a composition script to put in its parts and edit (references/building-blocks.md;
research/blocks-0.5.md).

Where the numbers come from:
- Drums: what professional drummers played, feel by feel, in the Groove MIDI Dataset (Gillick, Roberts, Engel, Eck and
  Bamman 2019; Google LLC, CC BY 4.0): where each drum falls in the bar, how loud, how many notes a bar holds, how
  much the bars vary, and the fills (references/drum-statistics.json, made by research/gmd-drums/gmd_drum_stats.py;
  aggregate numbers only).  The layers are Open Music Theory's ("Drumbeats", Hanenberg): the backbeat, the kick that
  enters on the downbeat however syncopated, the cymbals' regular pulse, and the cymbals stopping for a fill.  A fill
  closes each section, as a fill at the end of an eight-bar section leads into the next, and no step takes more hand
  drums than two hands play (Dow 2010, Sound On Sound).
- Bass and accompaniment: the figures the guides give (development-and-groove.md, arrangement.md, jazz-and-funk.md,
  with their sources); a rhythm of one's own as Logic Pro's Session Players take one, a bar of sixteenths with main
  hits and probable hits that complexity brings in (Apple, "Edit a Session Player performance"); fills, octave jumps
  and a maximum note length as those players offer them; pushes, a note an eighth early held over the change
  (development-and-groove.md; jazz-and-funk.md: push the root with the guitar); the walking line's scale tones from
  Open Music Theory's chord-scale table; velocities on MuseScore's table of dynamics (pp 32 to ff 112).  The comping
  answers the melody and the bass rather than doubling their rhythms (Israels; Owsinski's fills).
- The settings complexity, intensity, fills and variation run from 0 to 1 and are defined by what they do: a quantile
  of the drummers' distribution, a share of phrase ends or of free slots.  No constant stands in for what players do.
  Where a choice has no source, the seed picks uniformly among the options.

Against sameness:
- Writers given a GPT-4 idea wrote stories more alike, anchored on it; with five ideas to choose from they still wrote
  more alike than writers alone (Doshi and Hauser 2024).
- One tool answers different users' similar requests with similar output (Anderson, Shah and Kreminski 2024, who
  propose, without testing them, randomness from a large pool, quality-diversity methods and intent elicitation).
So:
- no musical setting has a default, and neither has the seed: a call carries the piece's own decisions;
- the seed comes from the piece (`seed(title)`), so one call in two pieces gives two parts;
- the parts are drawn from distributions (the drummers', the seed's), not picked from a short list, and the comping
  follows the piece's own melody and bass;
- `candidates` returns several parts for one setting, spread over density and syncopation, to choose between: the
  spread of quality-diversity search without its measure of quality (Mouret and Clune 2015 keep the best of each
  kind; here the agent judges);
- the record names a choice that is the style's most common form, as Anderson et al. (2024) suggest that users told
  what a tool tends to suggest might resist it.

Nothing here has been heard: whether a block suits a piece is a listening question.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from .harmony import QUALITIES, parse
from .review import _meter, _metric_weight

STEPS = 4  # grid steps per quarter note: sixteenths
STATISTICS = Path(__file__).resolve().parents[2] / 'references' / 'drum-statistics.json'
DRUM_KEYS = {'kick': 36, 'snare': 38, 'clap': 39, 'rim': 37, 'closed_hat': 42, 'pedal_hat': 44, 'open_hat': 46,
             'ride': 51, 'crash': 49, 'tom_high': 50, 'tom_mid': 47, 'tom_low': 45, 'shaker': 70}
BACKBEATS = ('normal', 'half', 'double', 'dembow', 'blast', 'eighths', 'none')
KICKS = ('one_three', 'four_floor', 'syncopated', 'tresillo', 'euclidean', 'eighths', 'double', 'none')
PULSES = ('quarter', 'eighth', 'sixteenth', 'offbeat', 'feel', 'none')
CYMBALS = ('closed_hat', 'open_hat', 'ride', 'shaker')
BASS_FIGURES = ('root', 'root_fifth', 'eighths', 'octaves', 'kick', 'funk', 'bossa', 'walking', 'pattern')
ACCOMPANIMENTS = ('held', 'broken', 'alternating', 'syncopated', 'strum', 'offbeat', 'pompe', 'batida', 'pattern')
# The drum voices a drums pattern may name, with the class whose velocities the drummers' statistics give them.
PATTERN_VOICES = {'kick': 'kick', 'snare': 'snare', 'clap': 'clap', 'rim': 'rim', 'closed_hat': 'hat_closed',
                  'pedal_hat': 'hat_pedal', 'open_hat': 'hat_open', 'ride': 'ride', 'crash': 'crash',
                  'tom_high': 'tom_high', 'tom_mid': 'tom_mid', 'tom_low': 'tom_low'}
PUSHES = ('none', 'phrase', 'changes')
# MuseScore 3's MIDI velocities for the dynamic markings (MuseScore handbook, "Soundfont, MIDI velocity and
# instruments.xml").  Bass and accompaniment play at intensity's place between pp and ff; a probable hit one marking
# softer; a ghost note at ppp.
DYNAMICS = {'ppp': 16, 'pp': 32, 'p': 48, 'mp': 64, 'mf': 80, 'f': 96, 'ff': 112, 'fff': 126}
SOFTER = DYNAMICS['mf'] - DYNAMICS['mp']
# Open Music Theory's chord-scale table: ionian (or lydian) for major sevenths, dorian for minor sevenths, mixolydian
# for dominant sevenths, locrian for half-diminished sevenths.  Triads, sixths and added tones of each family follow it;
# chords the table does not name (suspended, diminished, augmented, altered dominants, minor-major) walk on chord tones.
SCALES = {'ionian': (0, 2, 4, 5, 7, 9, 11), 'lydian': (0, 2, 4, 6, 7, 9, 11), 'dorian': (0, 2, 3, 5, 7, 9, 10),
          'mixolydian': (0, 2, 4, 5, 7, 9, 10), 'locrian': (0, 1, 3, 5, 6, 8, 10)}
CYMBAL_CLASS = {'closed_hat': 'hat_closed', 'open_hat': 'hat_open', 'ride': 'ride', 'shaker': 'hat_closed'}
FALLBACK = {'clap': 'snare', 'rim': 'snare', 'hat_open': 'hat_closed', 'ride': 'hat_closed', 'crash': 'ride',
            'tom_high': 'snare', 'tom_mid': 'snare', 'tom_low': 'snare'}
FILL_DRUMS = ('snare', 'tom_high', 'tom_mid', 'tom_low', 'kick')
HANDS = {'snare', 'tom_high', 'tom_mid', 'tom_low'}
PCT_POINTS = (.1, .25, .5, .75, .9)


@lru_cache(maxsize=1)
def statistics():
    """The drummers' statistics (references/drum-statistics.json; research/gmd-drums/gmd_drum_stats.py)."""
    return json.loads(STATISTICS.read_text(encoding='utf-8'))


FEELS = tuple(sorted(statistics()['feels']))


def seed(title):
    """A seed from the piece's title: running the script again gives the same notes, another piece other notes."""
    return int(hashlib.sha256(str(title).encode('utf-8')).hexdigest()[:12], 16)


def _rng(base, *keys):
    text = ':'.join(str(k) for k in (base, *keys))
    return np.random.default_rng(int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:12], 16))


def _need(block, **settings):
    missing = [k for k, v in settings.items() if v is None]
    if missing:
        raise ValueError(f'{block}: decide {", ".join(missing)} for this piece; the blocks have no defaults, so that '
                         'two pieces do not start from the same part (references/building-blocks.md)')


def _unit(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f'{name} must be a number from 0 to 1, not {value!r}')
    return float(value)


def _per_bar(name, value, bars, sections, allowed=None):
    """One value per bar, from one value or one per section id (every bar covered)."""
    if isinstance(value, dict):
        if not sections:
            raise ValueError(f'{name} given per section needs the sections')
        out = [None] * bars
        for s in sections:
            if s['id'] not in value:
                raise ValueError(f'{name}: no value for section {s["id"]!r}')
            for b in range(s['start_bar'], min(bars, s['start_bar'] + s['bars'])):
                out[b] = value[s['id']]
        if any(v is None for v in out):
            raise ValueError(f'{name}: the sections leave bars without a value')
    else:
        out = [value] * bars
    for v in out:
        if allowed is not None:
            if v not in allowed:
                raise ValueError(f'{name} must be one of {", ".join(allowed)}, not {v!r}')
        else:
            _unit(name, v)
    return out


def _section_of(bars, sections):
    if not sections:
        return [None] * bars
    out = [None] * bars
    for s in sections:
        for b in range(s['start_bar'], min(bars, s['start_bar'] + s['bars'])):
            out[b] = s['id']
    return out


def _grid(meter):
    """The bar in steps, each step's metric weight (review's, after Longuet-Higgins and Lee 1984), the beat in steps."""
    m = _meter({'clock': {'meter': list(meter)}})
    steps = round(m[0] * STEPS)
    if abs(m[0] * STEPS - steps) > 1e-9:
        raise ValueError(f'meter {meter}: the blocks need a bar of whole sixteenths')
    return m, steps, [_metric_weight(i / STEPS, m) for i in range(steps)], round(m[2][0] * STEPS)


def _q(deciles, u):
    """The u-quantile (0 to 1) of a distribution given by its deciles (0, 10, ..., 100 percent)."""
    if not deciles:
        return 0.0
    x = min(1.0, max(0.0, float(u))) * 10
    i = min(9, int(x))
    return deciles[i] + (deciles[i + 1] - deciles[i]) * (x - i)


def _level(pcts, intensity):
    """A velocity from the 10th, 25th, 50th, 75th and 90th percentiles: intensity 0 gives the 10th, 0.5 the median,
    1 the 90th, linearly between."""
    q = .1 + .8 * intensity
    for a, b, va, vb in zip(PCT_POINTS, PCT_POINTS[1:], pcts, pcts[1:]):
        if q <= b + 1e-12:
            return va + (vb - va) * (q - a) / (b - a)
    return pcts[-1]


def _dynamic(intensity):
    """A velocity on MuseScore's table: intensity 0 is pp (32), 1 is ff (112), mp (64) and mf (80) between."""
    return int(round(DYNAMICS['pp'] + (DYNAMICS['ff'] - DYNAMICS['pp']) * intensity))


def syncopation(onsets, weights):
    """Longuet-Higgins and Lee's (1984) syncopation of a cyclic pattern of onsets (steps): for each onset, the strongest
    position before the next onset that is stronger than its own, minus its own weight; per onset."""
    on = sorted(set(onsets))
    if not on:
        return 0.0
    n, total = len(weights), 0
    for k, a in enumerate(on):
        b = on[(k + 1) % len(on)] + (n if k + 1 == len(on) else 0)
        between = [weights[i % n] for i in range(a + 1, b)]
        if between and max(between) > weights[a]:
            total += max(between) - weights[a]
    return total / len(on)


def euclid(k, n, rotation=0):
    """k onsets spread as evenly as possible over n steps (Toussaint 2005), rotated by `rotation` steps."""
    if not 0 <= k <= n:
        raise ValueError('euclid needs 0 <= k <= n')
    hits = [i for i in range(n) if (i * k) % n < k]
    return sorted((i + rotation) % n for i in hits)


def _draw(r, cands, weights, k):
    """k steps drawn without replacement, each in proportion to its weight; steps of weight 0 never."""
    pairs = [(c, w) for c, w in zip(cands, weights) if w > 0]
    k = min(int(k), len(pairs))
    if k <= 0:
        return []
    c = np.array([p[0] for p in pairs])
    w = np.array([p[1] for p in pairs], dtype=float)
    return sorted(int(x) for x in r.choice(c, size=k, replace=False, p=w / w.sum()))


def _within(notes, end):
    """Each note's written length cut to the block's end: an open hat or a crash on the last sixteenth, written half a
    beat long, ran past it, and validate refused the piece (GPT's review of 0.5, E01).  The sound's own release still
    rings in the render."""
    for n in notes:
        if n['on'] + n['duration'] > end + 1e-9:
            n['duration'] = round(end - n['on'], 6)
    return notes


def _unique(notes):
    """One note per key and onset (validate refuses a key struck twice at once): the louder stays."""
    best = {}
    for n in notes:
        k = (round(n['on'] * 960), n['pitch'])
        if k not in best or n['velocity'] > best[k]['velocity']:
            best[k] = n
    return sorted(best.values(), key=lambda n: (n['on'], n['pitch']))


# --- drums -----------------------------------------------------------------------------------------------------------

def _backbeat(kind, steps, beat):
    beats = steps // beat
    if kind == 'none':
        return []
    if kind == 'normal':
        return [beat * 2] if beats == 3 else [beat * i for i in range(1, beats, 2)]
    if kind == 'half':
        if beats % 2 or beats < 4:
            raise ValueError('a half-time backbeat needs a bar of four beats (or eight)')
        return [steps // 2]
    if kind == 'double':
        if beat != STEPS:
            raise ValueError('a double-time backbeat needs a simple meter (quarter-note beats)')
        return [beat * i + beat // 2 for i in range(beats)]
    if kind == 'dembow':
        if steps % 8:
            raise ValueError('dembow needs bars of whole half-notes (2/4, 4/4)')
        return [g + o for g in range(0, steps, 8) for o in (3, 6)]
    if kind in ('blast', 'eighths'):
        # The traditional blast beat alternates single strokes between the kick and the snare on sixteenths, the
        # snare on the second of each pair; the hammer and bomb blasts put the snare on every eighth (Wikipedia,
        # Blast beat).
        if beat != STEPS:
            raise ValueError(f'a {kind} snare needs a simple meter (quarter-note beats)')
        return list(range(1, steps, 2)) if kind == 'blast' else list(range(0, steps, 2))
    raise ValueError(kind)


def _table_map(steps, beat, beats_n, grid):
    """Each step of the block's bar -> a step of the drummers' bar (4/4 in sixteenths for a straight feel, grid 16; in
    triplet eighths for a shuffle, grid 12), or None between triplet eighths.  A bar of four beats maps beat for beat.
    Other meters borrow beat by beat: the first beat from the first, a backbeat (beats 2 and 4, beat 3 in triple meter:
    Open Music Theory) from beats 2 and 4 in turn, any other beat from beat 3."""
    if grid == 16 and beat != STEPS:
        raise ValueError('a straight feel is read on sixteenths: give a meter that beats in quarter notes (2/4, 3/4, '
                         '4/4, 5/4), or a shuffle feel (rock_shuffle, jazz_shuffle, latin_shuffle) for 6/8, 9/8 or 12/8')
    if grid == 12 and beat != 3 * STEPS // 2:
        raise ValueError('a shuffle feel is read on triplet eighths: give 6/8, 9/8 or 12/8 (a 4/4 shuffle is written '
                         'in 12/8), or a straight feel')
    if beats_n == 4:
        classes = [0, 1, 2, 3]
    else:
        backs = {s // beat for s in _backbeat('normal', steps, beat)}
        classes, turn = [], 0
        for i in range(beats_n):
            if i == 0:
                classes.append(0)
            elif i in backs:
                classes.append((1, 3)[turn % 2])
                turn += 1
            else:
                classes.append(2)
    out = []
    for s in range(steps):
        i, ph = divmod(s, beat)
        if grid == 16:
            out.append(classes[i] * 4 + ph)
        else:
            out.append(classes[i] * 3 + ph // 2 if ph % 2 == 0 else None)
    return out


def _onset(T, cls, tmap, steps, exclude=()):
    on = T['onset'].get(cls)
    cands = [s for s in range(steps) if s not in exclude and tmap[s] is not None]
    return cands, [on[tmap[s]] if on else 0.0 for s in cands]


def _velocity(T, cls, t, intensity, programmed):
    """The drummers' velocity on this drum at this step, at intensity's place between their 10th and 90th percentiles;
    with `programmed`, the drum's one velocity over all steps."""
    v = T['velocity'].get(cls) or T['velocity'].get(FALLBACK.get(cls, 'snare')) or T['velocity']['snare']
    p = v['all'] if programmed or t is None else v['by_step'].get(str(t), v['all'])
    return int(np.clip(round(_level(p, intensity)), 1, 127))


def _kick(kind, steps, beat, T, tmap, r, cx):
    """(the layer's own kicks, the kicks the feel adds): as many in all as the drummers played in a bar at
    complexity's quantile, each placed in proportion to how often they played a kick there."""
    beats = steps // beat
    if kind == 'none':
        return [], []
    target = int(round(_q(T['per_bar']['kick'], cx)))
    if kind == 'four_floor':
        base = [beat * i for i in range(beats)]
    elif kind == 'one_three':
        base = sorted({0, steps // 2} if beats % 2 == 0 else {0})
    elif kind == 'tresillo':
        if steps != 16:
            raise ValueError('a tresillo kick (3+3+2 eighths) needs a bar of 4/4')
        base = [0, 6, 12]
    elif kind == 'euclidean':
        n = steps // 2  # eighths in a simple meter, triplet eighths in a compound one
        k = max(1, min(n, target))
        rotations = [x for x in range(n) if 0 in euclid(k, n, x)]
        base = sorted({2 * i for i in euclid(k, n, int(r.choice(rotations)))})
    elif kind in ('eighths', 'double'):
        # The kick on every eighth (with the snare between, the traditional blast; with it, the hammer blast), or a
        # constant stream of sixteenths on the double kick (Wikipedia, Blast beat; rock-and-metal.md).
        if beat != STEPS:
            raise ValueError(f'an {kind} kick needs a simple meter (quarter-note beats)')
        base = list(range(0, steps, 2)) if kind == 'eighths' else list(range(steps))
    else:  # syncopated: the downbeat, the rest where the feel puts its kicks
        base = [0]
    cands, w = _onset(T, 'kick', tmap, steps, exclude=set(base))
    return base, _draw(r, cands, w, max(0, target - len(base)))


def _cymbal_steps(kind, steps, beat):
    if kind == 'none':
        return []
    if kind == 'quarter':
        return list(range(0, steps, beat))
    if kind == 'eighth':
        return list(range(0, steps, beat // 2 if beat == STEPS else STEPS // 2))
    if kind == 'sixteenth':
        return list(range(steps))
    if kind == 'offbeat':
        if beat != STEPS:
            raise ValueError('off-beat cymbals need a simple meter')
        return [i + beat // 2 for i in range(0, steps, beat)]
    raise ValueError(kind)


def _groove(T, tmap, steps, beat, key, base_seed):
    feel, backbeat, kick, pulse, cymbal, cx, _ = key
    r = _rng(base_seed, 'drums', *key)
    snare = _backbeat(backbeat, steps, beat)
    kicks = _kick(kick, steps, beat, T, tmap, r, cx)
    if pulse == 'feel':
        # Each step where the drummers in this feel played this cymbal, in proportion to how often they did.
        cands, w = _onset(T, CYMBAL_CLASS[cymbal], tmap, steps)
        cym = [s for s, p in zip(cands, w) if r.random() < p]
    else:
        cym = _cymbal_steps(pulse, steps, beat)
    return {'snare': snare, 'kicks': kicks, 'cymbal': cym, 'sub': int(r.integers(0, 2**31))}


def _fill(T, r, steps, beat, beats_n, intensity, programmed):
    """A fill over the bar's last beats, from the drummers' fills in this feel: its length drawn from theirs, each step's
    drums drawn with the probability they played them there, at most two hand drums a step (Dow 2010: four limbs)."""
    ft = T['fills']
    lengths = {int(k): v for k, v in ft['length_beats'].items() if v > 0}
    keys = sorted(lengths)
    length = min(int(r.choice(keys, p=np.array([lengths[k] for k in keys]) / sum(lengths.values()))), beats_n)
    start = steps - length * beat
    grid = T['grid']
    out = []
    for s in range(start, steps):
        j, ph = divmod(s - start, beat)
        tb = 4 - length + j  # the drummers' beat that this beat of the fill stands for
        if grid == 16:
            t = tb * 4 + ph
        elif ph % 2 == 0:
            t = tb * 3 + ph // 2
        else:
            continue
        share = sum(v for k, v in lengths.items() if k >= 4 - tb)  # the fills long enough to reach this beat
        hits = []
        for c in FILL_DRUMS:
            on = ft['onset'].get(c)
            p = min(1.0, on[t] / share) if on and share else 0.0
            if r.random() < p:
                hits.append((p, c))
        hands = sorted((h for h in hits if h[1] in HANDS), reverse=True)
        hits = [h for h in hits if h[1] not in HANDS] + hands[:2]
        for _, c in hits:
            groove = (T['velocity'].get(c) or T['velocity']['snare'])['all']
            pcts = groove if programmed else ft['velocity'].get(c) or groove
            out.append((s, c, int(np.clip(round(_level(pcts, intensity)), 1, 127))))
    return start, out


def drums(bars, meter, *, seed=None, feel=None, backbeat=None, kick=None, pulse=None, cymbal=None, complexity=None,
          intensity=None, fills=None, sections=None, backbeat_sound='snare', rolls=0.0, phrase_bars=4, variation=None,
          programmed=False, pattern=None):
    """Notes for a drum part: {'notes': [{'on', 'duration', 'pitch', 'velocity'}], 'record': what was chosen}.

    `feel` is one of FEELS, the drummers' styles in the Groove MIDI Dataset (straight feels for meters in quarter-note
    beats, the *_shuffle feels for 6/8, 9/8 and 12/8).  `backbeat` is one of BACKBEATS, `kick` of KICKS, `pulse` of
    PULSES ('feel': the cymbal where the feel's drummers played it) and `cymbal` of CYMBALS.  From 0 to 1:
    - `complexity`: how many kicks, off-backbeat snares and open hats a bar holds, as the quantile of what the drummers
      played in a bar of this feel (0.5, their median bar);
    - `intensity`: velocities from the drummers' 10th to their 90th percentile, drum by drum and step by step;
    - `fills`: 0 none; otherwise a fill ends each section, and within a section one every so many bars, the quantile
      of the drummers' spacing (fills 0.5, their median spacing; 1, their closest);
    - `variation` (complexity if not given): how often a bar of the phrase departs from the groove and by how many
      kicks, the quantile of the drummers' (0, the most repetitive; 1, the most varied).
    Each may be one value or one per section id, as Drummer's settings belong to a region.  `seed` comes from
    `seed(title)`.  `rolls` (0 to 1) adds trap's hi-hat rate changes on sixteenth pulses (beats.md); `phrase_bars` is
    the cycle the bars vary over; `programmed` gives each drum one velocity, as a step sequencer does.

    `pattern` writes the groove on a step sequencer's grid instead of the layers: {voice: one bar}, a voice of
    PATTERN_VOICES and a bar of `steps` characters (sixteenths; twelve in 6/8), x a hit, o a probable hit taken with
    complexity's probability (drawn per bar of the phrase), . a rest.  backbeat, kick, pulse and cymbal are then left
    out; fills, intensity, the drummers' velocities and `programmed` apply as before."""
    if pattern is not None:
        if backbeat is not None or kick is not None or pulse is not None or cymbal is not None:
            raise ValueError('drums: a pattern replaces backbeat, kick, pulse and cymbal; leave them out')
        backbeat = kick = pulse = 'none'
        cymbal = 'closed_hat'
    _need('drums', seed=seed, feel=feel, backbeat=backbeat, kick=kick, pulse=pulse, cymbal=cymbal,
          complexity=complexity, intensity=intensity, fills=fills)
    m, steps, weights, beat = _grid(meter)
    if pattern is not None:
        if (not isinstance(pattern, dict) or not pattern or set(pattern) - set(PATTERN_VOICES)
                or any(not isinstance(v, str) or len(v) != steps or set(v) - set('xo.') for v in pattern.values())
                or not any(set(v) & set('xo') for v in pattern.values())):
            raise ValueError(f'drums: pattern maps voices ({", ".join(PATTERN_VOICES)}) to one bar of {steps} steps, '
                             'each x (a hit), o (a probable hit) or . (a rest)')
    bar_q = m[0]
    beats_n = steps // beat
    per = {name: _per_bar(name, value, bars, sections, allowed)
           for name, value, allowed in (('feel', feel, FEELS), ('backbeat', backbeat, BACKBEATS), ('kick', kick, KICKS),
                                        ('pulse', pulse, PULSES), ('cymbal', cymbal, CYMBALS),
                                        ('complexity', complexity, None), ('intensity', intensity, None),
                                        ('fills', fills, None))}
    per['variation'] = per['complexity'] if variation is None else _per_bar('variation', variation, bars, sections)
    rolls = _per_bar('rolls', rolls, bars, sections)
    if backbeat_sound not in ('snare', 'clap', 'rim'):
        raise ValueError('backbeat_sound must be snare, clap or rim')
    if phrase_bars not in (1, 2, 4, 8):
        raise ValueError('phrase_bars must be 1, 2, 4 or 8')
    if not isinstance(programmed, bool):
        raise ValueError('programmed must be True or False')
    names = _section_of(bars, sections)
    starts = []
    for b in range(bars):
        starts.append(b if b == 0 or names[b] != names[b - 1] else starts[b - 1])
    maps, notes, grooves, typical = {}, [], {}, set()
    for b in range(bars):
        f = per['feel'][b]
        T = statistics()['feels'][f]
        if f not in maps:
            maps[f] = _table_map(steps, beat, beats_n, T['grid'])
        tmap = maps[f]
        cx, it, fl, va = per['complexity'][b], per['intensity'][b], per['fills'][b], per['variation'][b]
        # Sections with the same settings share a groove, as a verse returns with its groove.
        key = (f, per['backbeat'][b], per['kick'][b], per['pulse'][b], per['cymbal'][b], round(cx, 2), round(va, 2))
        if key not in grooves:
            grooves[key] = _groove(T, tmap, steps, beat, key, seed)
            if key[1] == 'normal' and key[2] == 'one_three' and key[3] == 'eighth':
                typical.add('the basic rock beat: the kick on 1 and 3, the backbeat on 2 and 4, eighths on the cymbal '
                            '(Open Music Theory, Drumbeats), the most common pop drumbeat')
            if key[2] == 'four_floor' and key[3] == 'offbeat':
                typical.add('four on the floor with off-beat hats, house\'s most common pattern (electronic.md)')
            if key[1] == 'blast' and key[2] == 'eighths':
                typical.add('the traditional blast beat: kick and snare alternating on sixteenths, the cymbal with the kick, '
                            'usually from about 180 BPM (Wikipedia, Blast beat)')
            if key[1] == 'eighths' and key[2] in ('eighths', 'double'):
                typical.add('the hammer blast, kick and snare together on eighths' if key[2] == 'eighths' else
                            'the bomb blast, the snare on eighths over sixteenths on the double kick')
            if key[1] == 'double' and key[2] == 'four_floor' and key[3] == 'eighth':
                typical.add('the thrash or skank beat: kick and snare alternating on eighths, the cymbal on every eighth '
                            '(rock-and-metal.md)')
        g = grooves[key]
        r = _rng(seed, 'bar', g['sub'], b % phrase_bars)
        base, extras = g['kicks'][0], list(g['kicks'][1])
        vt = T['variation']
        if b % phrase_bars and vt['mode_share'] and r.random() < 1 - _q(vt['mode_share'], 1 - va):
            # A bar that departs from the groove by as many kicks as the drummers changed at variation's quantile:
            # up to half of them moved away, the rest placed anew where the feel puts its kicks.
            changed = max(1, int(round(_q(vt['changed_steps'], va)))) if vt['changed_steps'] else 1
            removed = min(len(extras), changed // 2)
            for _ in range(removed):
                extras.pop(int(r.integers(0, len(extras))))
            cands, w = _onset(T, 'kick', tmap, steps, exclude=set(base) | set(extras))
            extras = sorted(extras + _draw(r, cands, w, changed - removed))
        kicks = sorted(set(base) | set(extras))
        snare = g['snare']
        ghosts = []
        if backbeat_sound == 'snare' and pattern is None:
            cands, w = _onset(T, 'snare', tmap, steps, exclude=set(snare))
            ghosts = _draw(r, cands, w, int(round(_q(T['per_bar']['snare_off_backbeat'], cx))))
        pulse_steps, opens = g['cymbal'], []
        if key[4] == 'closed_hat' and pulse_steps and T['onset'].get('hat_open') and pattern is None:
            on = T['onset']['hat_open']
            opens = _draw(r, pulse_steps, [on[tmap[s]] if tmap[s] is not None else 0 for s in pulse_steps],
                          int(round(_q(T['per_bar']['hat_open'], cx))))
        section_end = b == bars - 1 or names[b + 1] != names[b]
        fill_from, fill = steps, []
        if fl > 0:
            spacing = T['fills']['interval_bars']
            every = max(1, int(round(_q(spacing, 1 - fl)))) if spacing else None
            if section_end or (every and (b - starts[b] + 1) % every == 0):
                fill_from, fill = _fill(T, r, steps, beat, beats_n, it, programmed)
        roll_here = bool(rolls[b]) and key[3] == 'sixteenth' and fill_from == steps and r.random() < rolls[b]
        at = b * bar_q

        def hit(step, cls, sound, duration=.25):
            notes.append({'on': at + step / STEPS, 'duration': duration, 'pitch': DRUM_KEYS[sound],
                          'velocity': _velocity(T, cls, tmap[step], it, programmed)})

        for s in kicks:
            if s < fill_from:
                hit(s, 'kick', 'kick')
        for s in snare:
            if s < fill_from:
                hit(s, backbeat_sound, backbeat_sound)
        for s in ghosts:
            if s < fill_from:
                hit(s, 'snare', 'snare')
        cym_class = CYMBAL_CLASS[key[4]]
        for s in pulse_steps:
            if s >= fill_from or (roll_here and s >= steps - beat):
                continue
            if s in opens:
                hit(s, 'hat_open', 'open_hat', .5)
            else:
                hit(s, cym_class, key[4], .5 if key[4] == 'open_hat' else .25)
        if roll_here:
            # A rate change on the last beat: thirty-seconds or sixteenth triplets (Computer Music 2016, in beats.md).
            start, n_sub = (steps - beat) / STEPS, int(r.choice([6, 8]))
            v = _velocity(T, cym_class, tmap[steps - beat], it, programmed)
            for j in range(n_sub):
                notes.append({'on': at + start + j * (beat / STEPS) / n_sub, 'duration': (beat / STEPS) / n_sub,
                              'pitch': DRUM_KEYS[key[4]], 'velocity': v})
        if pattern is not None:
            draws = _rng(seed, 'drum-pattern', b % phrase_bars).random((len(pattern), steps))
            for i, (voice, line) in enumerate(sorted(pattern.items())):
                for s, ch in enumerate(line):
                    if s < fill_from and (ch == 'x' or (ch == 'o' and draws[i][s] < cx)):
                        hit(s, PATTERN_VOICES[voice], voice, .5 if voice in ('open_hat', 'crash') else .25)
        for s, drum, v in fill:
            notes.append({'on': at + s / STEPS, 'duration': .25, 'pitch': DRUM_KEYS[drum], 'velocity': v})
        if fill and b + 1 < bars and r.random() < T['fills']['crash_after']:
            notes.append({'on': (b + 1) * bar_q, 'duration': 1.0, 'pitch': DRUM_KEYS['crash'],
                          'velocity': _velocity(T, 'crash', tmap[0], it, programmed)})
    notes = _within(_unique(notes), bars * bar_q)
    first = grooves[next(iter(grooves))]
    kick_steps = sorted(set(first['kicks'][0]) | set(first['kicks'][1]))
    return {'notes': notes, 'record': {
        'block': 'drums', 'seed': seed, 'meter': list(meter), 'bars': bars, 'feel': sorted(set(per['feel'])),
        'pattern': pattern,
        'grooves': len(grooves), 'typical': sorted(typical), 'kick_steps': kick_steps,
        'backbeat_steps': first['snare'], 'kick_syncopation': round(syncopation(kick_steps, weights), 3),
        'source': 'Groove MIDI Dataset (Gillick et al. 2019), Google LLC, CC BY 4.0: aggregate statistics',
        'note': 'A starting point: change what the brief asks for. Nothing here has been heard.'}}


# --- candidates ------------------------------------------------------------------------------------------------------

def _features(result, block, meter):
    """(onset density per step, syncopation): the first groove's kick for drums, every bar's onsets for the others."""
    m, steps, weights, _ = _grid(meter)
    if block == 'drums':
        k = result['record']['kick_steps']
        return len(k) / steps, syncopation(k, weights)
    bars = {}
    for n in result['notes']:
        b = int(np.floor(n['on'] / m[0] + 1e-9))
        bars.setdefault(b, set()).add(int(round((n['on'] - b * m[0]) * STEPS)) % steps)
    if not bars:
        return 0.0, 0.0
    return (float(np.mean([len(v) for v in bars.values()])) / steps,
            float(np.mean([syncopation(v, weights) for v in bars.values()])))


def candidates(n=4, pool=24, block='drums', **settings):
    """`n` parts for the same settings, spread over onset density and syncopation: made from `pool` seeds derived from
    the piece's seed, then picked one by one as far as possible from those already picked (the spread of
    quality-diversity search without its measure of quality, Mouret and Clune 2015).  `block` is 'drums', 'bass' or
    'accompaniment', with that block's settings.  Choose one for the brief; its 'seed' gives it again."""
    makers = {'drums': drums, 'bass': bass, 'accompaniment': accompaniment}
    if block not in makers:
        raise ValueError('block must be drums, bass or accompaniment')
    if settings.get('seed') is None:
        raise ValueError('candidates: give the piece\'s seed')
    made = []
    for k in range(pool):
        s = int(_rng(settings['seed'], 'candidate', block, k).integers(0, 2**40))
        res = makers[block](**{**settings, 'seed': s})
        made.append((s, res, _features(res, block, settings['meter'])))
    if not made:
        return []
    d = np.array([x[2] for x in made])
    span = np.where(d.max(axis=0) - d.min(axis=0) > 1e-9, d.max(axis=0) - d.min(axis=0), 1.0)
    z = (d - d.mean(axis=0)) / span
    picked = [int(np.argmin(np.abs(z).sum(axis=1)))]
    while len(picked) < min(n, len(made)):
        dist = np.min([np.abs(z - z[p]).sum(axis=1) for p in picked], axis=0)
        dist[picked] = -1
        picked.append(int(np.argmax(dist)))
    out = []
    for i in picked:
        row = {'seed': made[i][0], 'density': round(made[i][2][0], 3), 'syncopation': round(made[i][2][1], 3),
               'result': made[i][1]}
        if block == 'drums':
            row.update({'kick_density': row['density'], 'kick_syncopation': row['syncopation'],
                        'kick_steps': made[i][1]['record']['kick_steps']})
        out.append(row)
    return out


# --- bass and accompaniment: shared pieces ----------------------------------------------------------------------------

def _changes(chords, bar_q):
    """[(beat, symbol)] from one symbol per bar, or per bar a list of (beat in the bar, symbol)."""
    out = []
    for b, c in enumerate(chords):
        items = [(0, c)] if isinstance(c, str) else c
        for beat, symbol in items:
            if parse(symbol) is None:
                raise ValueError(f'bar {b + 1}: unknown chord symbol {symbol!r}')
            out.append((b * bar_q + beat, symbol))
    return out


def _bars_in(start, stop, length):
    """(start, end) of each stretch of `length` beats between start and stop, cut at multiples of `length`."""
    t = start
    while t < stop - 1e-9:
        nxt = (np.floor(t / length + 1e-9) + 1) * length
        yield t, min(nxt, stop)
        t = nxt


def _place(pc, low, high, near):
    """The pitch of class `pc` in [low, high] nearest `near`."""
    options = [p for p in range(low, high + 1) if p % 12 == pc]
    if not options:
        raise ValueError(f'no pitch of class {pc} between {low} and {high}')
    return min(options, key=lambda p: (abs(p - near), p))


def _scale(chord):
    """The chord's scale on Open Music Theory's chord-scale table as a set of pitch classes, or None."""
    iv = set(QUALITIES[chord['quality']])
    if 4 in iv and 10 in iv and not iv & {1, 3, 6, 8}:
        name = 'mixolydian'
    elif 4 in iv and 11 in iv and 6 in iv and not iv & {1, 3, 8, 10}:
        name = 'lydian'
    elif 4 in iv and not iv & {1, 3, 6, 8, 10}:
        name = 'ionian'
    elif 3 in iv and 7 in iv and not iv & {1, 4, 6, 8, 11}:
        name = 'dorian'
    elif {3, 6, 10} <= iv and not iv & {4, 7}:
        name = 'locrian'
    else:
        return None
    return {(chord['root'] + i) % 12 for i in SCALES[name]}


def _pattern(pattern, steps, block):
    if not isinstance(pattern, str) or len(pattern) != steps or set(pattern) - set('xo.') or not set(pattern) & set('xo'):
        raise ValueError(f'{block}: pattern is one bar of {steps} sixteenths, each x (a hit), o (a probable hit, taken '
                         'more often with more complexity) or . (a rest), as Logic Pro\'s Session Player patterns mark '
                         'main and probable accents')
    return pattern


def _phrase_ends(bars, phrase_bars, share, r):
    """The bars that end a phrase (not the last bar), each taken with probability `share`, drawn by the seed."""
    return {b for b in range(bars - 1) if (b + 1) % phrase_bars == 0 and r.random() < share}


def _pushed(changes, push, bar_q, phrase_bars):
    """The indices of the changes struck an eighth early: every change but the first, or those on a phrase's first
    downbeat."""
    if push == 'none':
        return set()
    out = set()
    for k, (start, _) in enumerate(changes):
        if k == 0:
            continue
        if push == 'changes' or abs(start / (bar_q * phrase_bars) - round(start / (bar_q * phrase_bars))) < 1e-9:
            out.add(k)
    return out


def _check_common(block, figure, figures, complexity, intensity, push, phrasing, pattern, phrase_bars):
    if figure not in figures:
        raise ValueError(f'{block}: figure must be one of {", ".join(figures)}')
    _unit('complexity', complexity)
    _unit('intensity', intensity)
    if push not in PUSHES:
        raise ValueError(f'{block}: push must be one of {", ".join(PUSHES)}')
    if phrasing is not None and (isinstance(phrasing, bool) or not isinstance(phrasing, (int, float)) or phrasing <= 0):
        raise ValueError(f'{block}: phrasing is the longest a note may last, in beats')
    if pattern is not None and figure != 'pattern':
        raise ValueError(f'{block}: a pattern is read with figure="pattern"')
    if figure == 'pattern' and pattern is None:
        raise ValueError(f'{block}: figure "pattern" needs pattern=')
    if phrase_bars not in (1, 2, 4, 8):
        raise ValueError('phrase_bars must be 1, 2, 4 or 8')


# --- bass ------------------------------------------------------------------------------------------------------------

def bass(chords, meter, *, seed=None, figure=None, complexity=None, intensity=None, low=None, high=None, push=None,
         fills=None, kick=None, pattern=None, octaves=None, phrasing=None, phrase_bars=4):
    """Notes for a bass line under `chords` (one symbol per bar, or a list of (beat in the bar, symbol) per bar).

    `figure` is one of BASS_FIGURES:
    - 'root' and 'root_fifth' (the two-feel): the root on the downbeat, the fifth on the half-bar;
    - 'eighths' and 'octaves': the root in driving eighths, or root and octave;
    - 'kick': the kick's rhythm from a `drums` result passed as `kick`, a rhythmic cell shared with it;
    - 'funk': the root on the One, then sixteenths off the beat, each with complexity's probability, an octave, the
      root or a ghost note, the last half beat before the next One left open;
    - 'bossa': the root on 1, the fifth on the "and" of 2 and on 3, the root on the "and" of 4;
    - 'walking': quarter notes, the root on beat 1, chord and scale tones by step on 2 and 3, and before a change a
      half step above or below the next root or its fifth (jazz-and-funk.md);
    - 'pattern': the rhythm of `pattern`, a bar of sixteenths: x a hit, o a probable hit (complexity is its
      probability, drawn again in each bar of the phrase), . a rest; the chord's root on each hit.
    `push` ('none', 'phrase', 'changes'): the note of a change struck an eighth early and held over it, at every change
    or at the first of each phrase.  `fills` (0 to 1): the probability that a phrase end's last beat (two beats above
    complexity 0.5) runs to a half step from the next root in eighths (sixteenths above 0.5).  Complexity is also the
    probability that any other change is approached by a whole step from a tone of the chord (arrangement.md).
    `octaves` (0 to 1) the probability
    that a later note of a chord leaps an octave; `phrasing` the longest a note lasts, in beats (otherwise each note
    lasts until the next).  Velocities: intensity's place between pp and ff on MuseScore's table."""
    _need('bass', seed=seed, figure=figure, complexity=complexity, intensity=intensity, low=low, high=high, push=push,
          fills=fills)
    _check_common('bass', figure, BASS_FIGURES, complexity, intensity, push, phrasing, pattern, phrase_bars)
    _unit('fills', fills)
    if octaves is not None:
        _unit('octaves', octaves)
    if high - low < 12:
        raise ValueError('bass: the range needs an octave or more')
    if figure == 'kick' and not kick:
        raise ValueError('bass: figure "kick" needs the drums result as kick=')
    m, steps, weights, beat = _grid(meter)
    bar_q = m[0]
    pat = _pattern(pattern, steps, 'bass') if figure == 'pattern' else None
    changes = _changes(chords, bar_q)
    end = len(chords) * bar_q
    r = _rng(seed, 'bass', figure)
    kick_on = sorted({round(n['on'] * STEPS) / STEPS for n in (kick or {}).get('notes', []) if n['pitch'] == 36})
    level, ghost = _dynamic(intensity), DYNAMICS['ppp']
    soft = max(1, level - SOFTER)
    approached = {k for k in range(1, len(changes)) if r.random() < complexity}
    pushed = _pushed(changes, push, bar_q, phrase_bars)
    seq, prev, short = [], (low + high) // 2, figure == 'funk'
    for k, (start, symbol) in enumerate(changes):
        stop = changes[k + 1][0] if k + 1 < len(changes) else end
        c = parse(symbol)
        root = _place(c['bass'], low, high, prev)
        fifth = _place((c['root'] + 7) % 12, low, high, root + 7) if 7 in [(p - c['root']) % 12 for p in c['pcs']] else root
        octave = root + 12 if root + 12 <= high else root
        nxt = parse(changes[k + 1][1]) if k + 1 < len(changes) else None
        local = []  # (on, pitch, velocity)
        if figure in ('root', 'root_fifth'):
            for a, z in _bars_in(start, stop, bar_q):
                local.append((a, root, level))
                if figure == 'root_fifth' and z - a > bar_q / 2 + 1e-9:
                    local.append((a + bar_q / 2, fifth, level))
        elif figure in ('eighths', 'octaves'):
            t, i = start, 0
            while t < stop - 1e-9:
                local.append((t, octave if figure == 'octaves' and i % 2 else root, level))
                t, i = t + .5, i + 1
        elif figure == 'kick':
            for x in [x for x in kick_on if start - 1e-9 <= x < stop - 1e-9] or [start]:
                local.append((x, root, level))
        elif figure == 'funk':
            local.append((start, root, level))
            t, limit = start + .25, min(stop, start + bar_q) - .5
            while t < limit - 1e-9:
                if weights[round((t - start) * STEPS) % steps] < 3 and r.random() < complexity:
                    kind = int(r.integers(0, 3))  # the guide's three, uniformly: an octave, the root, a ghost note
                    local.append((t, (octave, root, root)[kind], (level, level, ghost)[kind]))
                t += .25
        elif figure == 'bossa':
            for a, z in _bars_in(start, stop, 2.0):
                first = round(a / 2) % 2 == 0 if bar_q % 4 == 0 else True
                for off, which in ((0, 'r' if first else 'f'), (1.5, 'f' if first else 'r')):
                    if a + off < z - 1e-9:
                        local.append((a + off, root if which == 'r' else fifth, level))
        elif figure == 'walking':
            scale = _scale(c) or set()
            tones = [p for p in range(low, high + 1) if p % 12 in c['pcs'] | scale]
            chord_tones = [p for p in tones if p % 12 in c['pcs']]
            t, last = start, None
            while t < stop - 1e-9:
                if last is None:
                    p = root
                else:
                    near = [q for q in tones if q != last and abs(q - last) <= 2]  # by step: a half or whole tone
                    p = int(r.choice(near)) if near else min(chord_tones, key=lambda q: (abs(q - last), q))
                local.append((t, p, level))
                last, t = p, t + 1.0
        elif figure == 'pattern':
            for a, z in _bars_in(start, stop, bar_q):
                bar_index = int(np.floor(a / bar_q + 1e-9))
                draws = _rng(seed, 'bass-pattern', bar_index % phrase_bars).random(steps)
                for s, ch in enumerate(pat):
                    on = bar_index * bar_q + s / STEPS
                    if a - 1e-9 <= on < z - 1e-9 and (ch == 'x' or (ch == 'o' and draws[s] < complexity)):
                        local.append((on, root, level if ch == 'x' else soft))
        if octaves:
            local = [(t, p + 12 if j and v != ghost and p + 12 <= high and r.random() < octaves else p, v)
                     for j, (t, p, v) in enumerate(local)]
        # Into the next chord: in a walking line a half step above or below its root, or its fifth (jazz-and-funk.md);
        # otherwise, at the changes complexity picks, a whole step from a tone of this chord (arrangement.md).
        if nxt is not None and local and figure != 'funk' and (figure == 'walking' or k + 1 in approached):
            target = _place(nxt['bass'], low, high, local[-1][1])
            if figure == 'walking':
                options = [target - 1, target + 1, _place((nxt['root'] + 7) % 12, low, high, local[-1][1])]
            else:
                options = [p for p in (target - 2, target + 2) if p % 12 in c['pcs']]
            options = [p for p in options if low <= p <= high and p != target]
            if options and local[-1][0] > start + 1e-9:
                t, _, v = local[-1]
                local[-1] = (t, int(r.choice(options)), v)
        if k in pushed and local and abs(local[0][0] - start) < 1e-9 and start - .5 >= 0:
            seq = [e for e in seq if e[0] < start - .5 - 1e-9]
            local[0] = (start - .5, local[0][1], local[0][2])
        seq += local
        prev = root
    # Fills at the phrase ends the seed picks: a run by step through the chord's tones and scale to a half step from
    # the next root, on slots the seed keeps (the first always); a pushed change keeps its early note.
    bars = len(chords)
    pushed_at = {changes[k][0] for k in pushed}
    for b in sorted(_phrase_ends(bars, phrase_bars, fills, r)):
        length = 2 if complexity > .5 else 1
        rate = .25 if complexity > .5 else .5
        z = (b + 1) * bar_q
        if any(abs(z - t) < 1e-9 for t in pushed_at):
            z -= .5  # the fill leads to the pushed note
        # No earlier than the phrase's start: in 2/4 a pushed two-beat fill began half a beat before the piece and found
        # no chord there (GPT's review of 0.5, E02).
        a = max(z - length * beat / STEPS, (b + 1 - phrase_bars) * bar_q)
        slots = [a + i * rate for i in range(int(round((z - a) / rate)))]
        if not slots:
            continue
        keep = [slots[0]] + [t for t in slots[1:] if r.random() < .5]
        if len(keep) < 2:
            keep = slots[:2]
        here = max((ch for ch in changes if ch[0] <= a + 1e-9), key=lambda ch: ch[0], default=None)
        after = min((ch for ch in changes if ch[0] >= (b + 1) * bar_q - 1e-9), key=lambda ch: ch[0], default=None)
        if here is None or after is None:
            continue
        c, nc = parse(here[1]), parse(after[1])
        before = [e for e in seq if e[0] < a - 1e-9]
        from_p = before[-1][1] if before else _place(c['bass'], low, high, (low + high) // 2)
        target = _place(nc['bass'], low, high, from_p)
        approach = target - 1 if from_p < target else target + 1
        tones = sorted(p for p in range(low, high + 1) if p % 12 in c['pcs'] | (_scale(c) or set()))
        path = [p for p in tones if (from_p < p < approach) or (approach < p < from_p)]
        path = path if from_p < approach else path[::-1]
        need = len(keep) - 1
        if path and need:
            idx = np.linspace(0, len(path) - 1, need).round().astype(int)
            run = [path[i] for i in idx] + [approach]
        else:
            run = [from_p] * need + [approach]
        if not low <= approach <= high:
            continue
        seq = [e for e in seq if not a - 1e-9 <= e[0] < z - 1e-9] + [(t, p, level) for t, p in zip(keep, run)]
    seq.sort(key=lambda e: e[0])
    notes = []
    for j, (t, p, v) in enumerate(seq):
        nxt_on = seq[j + 1][0] if j + 1 < len(seq) else end
        d = .25 if short else nxt_on - t
        if phrasing is not None:
            d = min(d, phrasing)
        if d > 1e-9:
            notes.append({'on': round(t, 6), 'duration': round(max(.125, d), 6), 'pitch': int(p),
                          'velocity': int(np.clip(v, 1, 127))})
    return {'notes': _unique(notes), 'record': {
        'block': 'bass', 'seed': seed, 'figure': figure, 'chords': len(changes), 'push': push, 'fills': fills,
        'note': 'A starting point: change what the brief asks for. Nothing here has been heard.'}}


# --- accompaniment ---------------------------------------------------------------------------------------------------

def accompaniment(chords, meter, *, seed=None, figure=None, complexity=None, intensity=None, low=None, high=None,
                  voices=None, push=None, melody=None, bass=None, answer=None, keep_root=False, pattern=None,
                  phrasing=None, phrase_bars=4):
    """Notes for a keyboard, guitar or pad part under `chords` (as for `bass`), its pitches from `voice_lead`.

    `figure` is one of ACCOMPANIMENTS (development-and-groove.md, after Owsinski and Israels):
    - 'held': each voicing held; a chord that can take it has its third delayed by the fourth for a beat, a 4-3
      suspension resolving, with complexity's probability;
    - 'broken': the chord broken into eighths (sixteenths above complexity 0.5), up, down or up and down, the seed
      choosing per chord;
    - 'alternating': the lowest tone on the beat, the rest of the chord on the "and" with complexity's probability, as a
      Session Player pattern's probable hit, a sixteenth or an eighth long (uniformly: the touch varied);
    - 'syncopated': comping, short chords (a sixteenth or an eighth, uniformly) on the eighths, the change struck and
      each other free eighth taken with complexity's probability;
    - 'strum': the chord down on the beats and up on the "and"s, each upstroke taken with complexity's probability, for
      a guitar with `strum` in musiclib.expression;
    - 'offbeat': the skank, a short damped chord on each off-beat (Wikipedia, Reggae; Ska), and with complexity's
      probability the double skank, a second stroke a sixteenth later, which reggae's slower tempos allowed (Wikipedia,
      Reggae); reggae's chord on 2 and 4 alone is a 'pattern';
    - 'pompe': gypsy jazz's la pompe, four staccato downstrokes a bar with a slight emphasis on 2 and 4, a quick
      upstroke before 1 and 3 (Persinger 2014; the emphasis also Wikipedia, Gypsy jazz); the softer 1 and 3 and the
      upstroke's length are this skill's;
    - 'batida': the bossa nova guitar's beat, in 4/4 the chord on beats 1 and 2 and the "and" of 3 (in 2/4 both eighths
      of beat 1 and the second sixteenth of beat 2: Wikipedia, Bossa nova), an eighth long; a pushed chord rings over
      the bar line; the thumb's bass is the bass block's ('bossa') or keep_root's;
    - 'pattern': the rhythm of `pattern` (as for `bass`), the whole voicing on each hit.
    `push` as for `bass`.  `melody` and `bass` give those parts' notes ({'on', 'duration', 'pitch'}): the voicing stays
    a minor third under the melody's lowest pitch in each chord and clear of its pitches (`voice_lead` ceilings and
    against), and with `answer` (on whenever either is given, unless answer=False) the comping's optional hits leave
    the eighths where the melody or the bass strikes, commentary on the melody rather than its rhythm, chords in answer
    to the bass's rhythm (Israels).  `phrasing` the longest a chord lasts, in beats.  Velocities as for `bass`."""
    _need('accompaniment', seed=seed, figure=figure, complexity=complexity, intensity=intensity, low=low, high=high,
          voices=voices, push=push)
    _check_common('accompaniment', figure, ACCOMPANIMENTS, complexity, intensity, push, phrasing, pattern, phrase_bars)
    from .voicing import voice_lead
    m, steps, weights, beat = _grid(meter)
    bar_q = m[0]
    pat = _pattern(pattern, steps, 'accompaniment') if figure == 'pattern' else None
    changes = _changes(chords, bar_q)
    end = len(chords) * bar_q
    spans = [(s, changes[k + 1][0] if k + 1 < len(changes) else end) for k, (s, _) in enumerate(changes)]
    ceilings, against = None, None
    if melody:
        sounding = [[int(n['pitch']) for n in melody if n['on'] < b and n['on'] + n['duration'] > a] for a, b in spans]
        ceilings = [min(x) - 3 if x else None for x in sounding]
        against = [x for x in sounding]
    voicings = voice_lead([s for _, s in changes], voices=voices, low=low, high=high, ceilings=ceilings,
                          against=against, keep_root=keep_root)
    answer = bool(melody or bass) if answer is None else bool(answer)
    struck = set()
    if answer:
        for part in (melody or [], bass or []):
            struck |= {int(np.floor(n['on'] * 2 + 1e-9)) for n in part}  # the eighths where another part strikes
    r = _rng(seed, 'accompaniment', figure)
    level = _dynamic(intensity)
    soft = max(1, level - SOFTER)
    pushed = _pushed(changes, push, bar_q, phrase_bars)
    held = []  # (on, duration, pitch, velocity): the held figure's own lengths
    attacks = []  # (on, [pitches], velocity, fixed length or None)
    suspend = set()
    if figure == 'held':
        eligible = []
        for k, ((start, stop), (_, symbol), chord) in enumerate(zip(spans, changes, voicings)):
            c = parse(symbol)
            third = [p for p in chord if (p - c['root']) % 12 in (3, 4)]
            if third and c['quality'] in ('', 'maj', 'M', 'm', 'min', '-', '7', 'm7') and stop - start >= 2:
                q = third[0]
                fourth = q + (2 if (q - c['root']) % 12 == 3 else 1)
                if fourth not in chord and fourth <= high and (not melody or all(abs(fourth - n['pitch']) % 12 not in (1, 11)
                                                              for n in melody if n['on'] < start + 1
                                                              and n['on'] + n['duration'] > start)):
                    eligible.append(k)
        suspend = {k for k in eligible if r.random() < complexity}
    for k, ((start, stop), (_, symbol), chord) in enumerate(zip(spans, changes, voicings)):
        c = parse(symbol)
        begin = start - .5 if k in pushed and start - .5 >= 0 else start
        if begin < start:
            held = [(t, min(d, begin - t), p, v) for t, d, p, v in held]
            attacks = [a for a in attacks if a[0] < begin - 1e-9]
        if figure == 'held':
            if k in suspend:
                q = [p for p in chord if (p - c['root']) % 12 in (3, 4)][0]
                fourth = q + (2 if (q - c['root']) % 12 == 3 else 1)
                held += [(begin, stop - begin, p, level) for p in chord if p != q]
                held += [(begin, start + 1.0 - begin, fourth, level), (start + 1.0, stop - start - 1.0, q, level)]
            else:
                held += [(begin, stop - begin, p, level) for p in chord]
        elif figure == 'broken':
            rate = .25 if complexity > .5 else .5
            order = sorted(chord)
            shape = ['up', 'down', 'updown'][int(r.integers(0, 3))]
            seq = order if shape == 'up' else order[::-1] if shape == 'down' else order + order[-2:0:-1]
            t, i = begin, 0
            while t < stop - 1e-9:
                attacks.append((t, [seq[i % len(seq)]], level, rate))
                t, i = t + rate, i + 1
        elif figure == 'alternating':
            low_tone, rest = min(chord), sorted(chord)[1:]
            t = begin
            if begin < start:  # the pushed chord whole, held through the first beat
                attacks.append((begin, chord, level, None))
                t = start + 1.0
            while t < stop - 1e-9:
                attacks.append((t, [low_tone], level, None))
                off = t + .5
                if off < stop - 1e-9 and int(np.floor(off * 2 + 1e-9)) not in struck and r.random() < complexity:
                    # The touch varied: a sixteenth or an eighth, the seed choosing uniformly.
                    attacks.append((off, rest, level, (.25, .5)[int(r.integers(0, 2))]))
                t += 1.0
        elif figure == 'syncopated':
            slots = [begin] + [start + x / 2 for x in range(1, int(round((stop - start) * 2)))]
            for j, t in enumerate(slots):
                if j == 0 or (int(np.floor(t * 2 + 1e-9)) not in struck and r.random() < complexity):
                    # Short chords with rests: each a sixteenth or an eighth long, the seed choosing uniformly.
                    attacks.append((t, chord, level, (.25, .5)[int(r.integers(0, 2))]))
        elif figure == 'strum':
            t = begin
            while t < stop - 1e-9:
                on_beat = abs(t - round(t)) < 1e-9
                tied = begin < start and abs(t - start) < 1e-9  # a pushed chord rings over the downbeat
                if not tied and (t == begin or on_beat or r.random() < complexity):
                    attacks.append((t, chord, level, None))
                t += .5
        elif figure == 'offbeat':
            if beat != STEPS:
                raise ValueError('accompaniment: offbeat needs a simple meter (quarter-note beats)')
            t = np.floor(begin + 1e-9) + .5
            t = t if t >= begin - 1e-9 else t + 1.0
            while t < stop - 1e-9:
                attacks.append((t, chord, level, .25))
                if t + .25 < stop - 1e-9 and r.random() < complexity:
                    attacks.append((t + .25, chord, soft, .25))
                t += 1.0
        elif figure == 'pompe':
            if beat != STEPS or bar_q % 2:
                raise ValueError('accompaniment: pompe needs a simple meter of two or four beats')
            t = float(np.ceil(begin - 1e-9))
            while t < stop - 1e-9:
                if int(round(t)) % 2:  # beats 2 and 4: the slight emphasis
                    attacks.append((t, chord, level, .25))
                else:
                    # Beats 1 and 3, each led by a quick upstroke of the chord it leads into, across a change too, but
                    # not before the first beat (Persinger 2014; it was on 2 and 4: GPT's review of 0.5, E03).
                    if t - .125 >= -1e-9:
                        attacks.append((t - .125, chord, soft, .125))
                    attacks.append((t, chord, soft, .25))
                t += 1.0
        elif figure == 'batida':
            offsets = {4: (0, 1, 2.5), 2: (0, .5, 1.25)}.get(bar_q) if beat == STEPS else None
            if offsets is None:
                raise ValueError('accompaniment: batida needs a bar of 2/4 or 4/4')
            if begin < start:  # the pushed chord rings over the bar line
                attacks.append((begin, chord, level, None))
            for a, z in _bars_in(start, stop, bar_q):
                bar_index = int(np.floor(a / bar_q + 1e-9))
                for o in offsets:
                    on = bar_index * bar_q + o
                    if a - 1e-9 <= on < z - 1e-9 and not (begin < start and abs(on - start) < 1e-9):
                        attacks.append((on, chord, level, .5))
        elif figure == 'pattern':
            if begin < start:
                attacks.append((begin, chord, level, None))
            for a, z in _bars_in(start, stop, bar_q):
                bar_index = int(np.floor(a / bar_q + 1e-9))
                draws = _rng(seed, 'comp-pattern', bar_index % phrase_bars).random(steps)
                for s, ch in enumerate(pat):
                    on = bar_index * bar_q + s / STEPS
                    if not a - 1e-9 <= on < z - 1e-9 or (begin < start and abs(on - start) < 1e-9):
                        continue
                    if ch == 'x' or (ch == 'o' and int(np.floor(on * 2 + 1e-9)) not in struck
                                     and draws[s] < complexity):
                        attacks.append((on, chord, level if ch == 'x' else soft, None))
    attacks.sort(key=lambda a: a[0])
    out = [{'on': t, 'duration': d, 'pitch': p, 'velocity': v} for t, d, p, v in held]
    for j, (t, pitches, v, fixed) in enumerate(attacks):
        nxt_on = attacks[j + 1][0] if j + 1 < len(attacks) else end
        d = fixed if fixed is not None else nxt_on - t
        if fixed is not None and figure != 'broken':
            d = min(d, max(nxt_on - t, 1e-9))
        if figure == 'pompe' and fixed == .125:  # the grace stroke keeps its own length, however short
            d = .125
        out += [{'on': t, 'duration': d, 'pitch': p, 'velocity': v} for p in pitches]
    notes = []
    for n in out:
        d = n['duration'] if phrasing is None else min(n['duration'], phrasing)
        if d > 1e-9:
            notes.append({'on': round(float(n['on']), 6), 'duration': round(max(.125, float(d)), 6),
                          'pitch': int(n['pitch']), 'velocity': int(np.clip(n['velocity'], 1, 127))})
    return {'notes': _unique(notes), 'record': {
        'block': 'accompaniment', 'seed': seed, 'figure': figure, 'chords': len(changes), 'voicings': voicings,
        'push': push, 'answer': answer,
        'note': 'A starting point: change what the brief asks for. Nothing here has been heard.'}}


def slides(notes, share, seed, overlap=.125):
    """A bass line's slides: with `share`'s probability, a note followed by one of another pitch is held `overlap` beats
    into it, so that on a patch that glides between overlapping notes (Surge with `surge.glide_ms`, or a `mono` built-in
    patch) the second slides from the first.  UK drill slides its 808 (Wikipedia, UK drill), acid house programs a
    slide per step (Wikipedia, Acid house); which notes slide is the seed's choice.  Notes struck together are left as
    they are.  Returns new notes."""
    from .model import number
    number(share, 0, 1, 'slides share')
    number(overlap, .03125, 1, 'slides overlap')
    r = _rng(seed, 'slides')
    out = sorted(({**n} for n in notes), key=lambda n: (n['on'], n['pitch']))
    # By onset: a note slides only from a note struck alone to a note struck alone (the last note of a chord was held
    # into the next: GPT's review of 0.5, E05).
    groups = {}
    for n in out:
        groups.setdefault(round(n['on'], 6), []).append(n)
    lone = [g[0] if len(g) == 1 else None for _, g in sorted(groups.items())]
    for a, b in zip(lone, lone[1:]):
        if a is None or b is None:
            continue
        if b['pitch'] != a['pitch'] and b['on'] - (a['on'] + a['duration']) < 1 + 1e-9:
            if r.random() < share:
                a['duration'] = round(b['on'] - a['on'] + overlap, 6)
    return out


def articulate(notes, ratio):
    """Each note's length set to `ratio` times the time to the next onset (notes struck together share it).  Eerola,
    Friberg and Bresin (2013) varied articulation at 1 (legato), 0.75, 0.5 and 0.25 (staccatissimo): shorter notes
    moved listeners' ratings toward happy, legato toward sad and peaceful.  The last onset's notes take `ratio` of their
    own length.  `ratio` from 0.05 to 1; returns new notes."""
    from .model import TPQ, number
    number(ratio, .05, 1, 'articulation ratio')
    onsets = sorted({round(float(n['on']), 6) for n in notes})
    following = dict(zip(onsets, onsets[1:]))
    out = []
    for n in notes:
        nxt = following.get(round(float(n['on']), 6))
        span = nxt - n['on'] if nxt is not None else n['duration']
        # A tick at least, the shortest note validate takes (1e-3 beat was under it: GPT's review of 0.5, E06).
        out.append({**n, 'duration': max(round(ratio * span, 6), round(1 / TPQ + 5e-7, 6))})
    return out


def add(track, result, prefix, gate=None):
    """Put a block's notes into a project track: ids `prefix`0, 1, ..., each note's velocity (and `gate`, if given)
    under performance.notes."""
    taken = {n['id'] for n in track.setdefault('notes', [])}
    perf = track.setdefault('performance', {}).setdefault('notes', {})
    for k, n in enumerate(result['notes']):
        nid = f'{prefix}{k}'
        if nid in taken:
            raise ValueError(f'note id {nid} is taken in track {track.get("id")}; choose another prefix')
        track['notes'].append({'id': nid, 'on': n['on'], 'duration': n['duration'], 'pitch': n['pitch']})
        perf[nid] = {'velocity': n['velocity'], **({'gate': gate} if gate is not None else {})}
    return track
