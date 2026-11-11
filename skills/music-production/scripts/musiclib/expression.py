"""Performance shaping for composers: timing and dynamics that behave like players rather than a grid.

Timing.  A player keeping to a beat is never at a fixed distance from it.  In the model the synchronisation
literature uses most (linear phase correction: Vorberg and Wing 1996 and Vorberg and Schulze 2002, as Repp 2005
reviews them), the player takes back a share of the distance by the next beat and a new error comes on top, so
successive distances from the beat are alike and the likeness dies away over a few beats.  Estimates of that share
lie between 0.2 and 0.8, and the distances vary least when it is between 0.3 and 0.5 (van der Steen and Keller
2013, after Repp and Keller 2008): PHASE_CORRECTION is 0.4, this module's choice inside that.  Each onset then has
its own motor delay, independent of the other onsets' (notes struck together share one), which is what makes
successive intervals between notes pull against each other (Wing and Kristofferson 1973).  Each part keeps to the score's beat by itself: nothing in one part's
timing is taken from another part.

Loudness.  In the recorded drum part analysed for it, the loudness of the hi-hat wandered with long-range
correlations and carried a two-bar pattern (Raesaenen et al. 2015, PLoS ONE 10: e0127902): the slow line of the
velocities is 1/f^beta noise, and cymbals carry a two-bar accent cycle.

Size.  Listeners rated a simple rock pattern best quantized (Fruehauf et al. 2013), and swing and funk performances
as grooving equally quantized or with the players' own timing, worse exaggerated (Senn et al. 2016), so deviations
stay small.  Sizes and weights below are this module's starting values:

- the distance from the beat as above (`timing_sd`, ms) and the motor delays (`short_sd`, ms).  With `drift='time'`
  the distance runs in time over the piece, on the sixteenth-note grid, and each onset's delay is drawn from the
  part, the seed and the onset's place, so a note added or removed changes no other note's draws (a chord it joins
  is shaped again: which note leads, the strum, the spread) (with the default
  `drift='notes'` every value steps note by note, and a part's whole performance moves when it gains a note: the
  0.4.0 Haiku pieces).  Either way a piece made longer draws its lines again.  A script written for 0.5 or before
  writes another performance under 0.6, of the same size: the distance and the gates are drawn another way, and
  the loudness line, drawn after them, takes other values with them;
- a fixed feel per part (laid-back bass, the two rhythm guitars apart);
- phrase arches and high-loud on melodic parts (KTH rules, Friberg et al. 2006);
- chords that are not perfectly together: the top note leads in keyboards, section players spread;
- strummed guitar chords (opt-in `strum`, ms per string): the pick reaches the strings in order, low to high on a
  downstroke and high to low on an upstroke, and the hand alternates on the `strum_grid` steps, down on the even
  steps and up on the odd ones (with the default 0.5, down on the beat and up on the "and"), the usual rhythm-guitar
  motion; a chord off the grid is a downstroke.  Upstrokes are a little faster and lighter.  No measurement of
  string-to-string timing was read, so the step sizes are choices;
- a two-bar periodic accent pattern on hi-hat/ride (Raesaenen et al. 2015, above);
- a bow-like expression arc (CC11) inside held chords of sustained parts.

apply(project, overrides, seed) changes performance.notes (timing_ms, velocity, gate) of the authored
values rather than replacing them, and densifies CC11 on parts whose profile asks for swells.  Results are
deterministic for a given seed.  Profiles come from the track role; `overrides` maps track ids to changes
(or None to leave a track alone).
"""
import hashlib
import math

import numpy as np

ROLE_DEFAULTS = {
    'melody': {'timing_sd': 6, 'short_sd': 2, 'vel_pct': 3, 'high_loud': .3, 'arch': 6, 'spread': 0, 'lead': 0,
               'gate_sd': .02, 'contrast': .04},
    'countermelody': {'timing_sd': 6, 'short_sd': 2, 'vel_pct': 3, 'high_loud': .2, 'arch': 4, 'spread': 8},
    'harmony': {'timing_sd': 5, 'short_sd': 2, 'vel_pct': 3, 'arch': 4, 'spread': 10, 'lead': 10, 'contrast': .03},
    'texture': {'timing_sd': 5, 'short_sd': 2, 'vel_pct': 4, 'arch': 3, 'spread': 6, 'lead': 6, 'gate_sd': .03},
    'rhythm': {'timing_sd': 4, 'short_sd': 1.5, 'vel_pct': 3, 'arch': 3, 'gate_sd': .03, 'contrast': .03},
    'bass': {'timing_sd': 3.5, 'short_sd': 1.5, 'feel': 4, 'vel_pct': 3, 'arch': 3, 'gate_sd': .02},
    'drums': {'timing_sd': 2.5, 'short_sd': 1.5, 'vel_pct': 3, 'cymbal_cycle': 4},
    'accent': {'timing_sd': 4, 'short_sd': 1.5, 'vel_pct': 3, 'spread': 6},
    'effect': None,
}
BASE = {'timing_sd': 0, 'short_sd': 0, 'feel': 0, 'vel_pct': 0, 'high_loud': 0, 'arch': 0, 'spread': 0, 'lead': 0,
        'gate_sd': 0, 'contrast': 0, 'cymbal_cycle': 0, 'swell': 0, 'strum': 0, 'strum_grid': .5, 'beta': .8,
        'correction': .4}
PHASE_CORRECTION = BASE['correction']  # the share of its distance from the beat a player takes back by the next beat
UPSTROKE_SPEED, UPSTROKE_VELOCITY = .8, .92
GRID = 4  # slots per quarter note: the sixteenth-note grid the slow components wander on


def strum_offsets(onset, group, prof, rng):
    """Per-note delays (ms) and velocity factors of one strummed chord: a downstroke on the even `strum_grid` steps and
    off the grid, an upstroke on the odd steps."""
    step = onset / prof['strum_grid']
    up = round(step) % 2 == 1 and abs(step - round(step)) < .25
    order = sorted(group, key=lambda n: n['pitch'], reverse=up)
    gap = prof['strum'] * (UPSTROKE_SPEED if up else 1)
    out, t = {}, 0.0
    for k, n in enumerate(order):
        if k:
            t += gap * (1 + .15 * rng.uniform(-1, 1))
        out[n['id']] = (t, UPSTROKE_VELOCITY if up else 1.0)
    return out, up
CYMBALS = {42, 44, 46, 51, 53, 59}


def rng_for(seed, name):
    return np.random.default_rng(int(hashlib.sha256(f'{seed}:{name}'.encode()).hexdigest()[:12], 16))


def kept_to_the_beat(n, rng, share=PHASE_CORRECTION, per_beat=1, gaps=None):
    """n successive distances of a player from the beat, `per_beat` of them to a beat: by the next beat the player
    has taken back `share` of the distance and a new error has come on top (linear phase correction, the module's
    text).  Two distances a beat apart correlate by 1 - share, two beats apart by its square, and so on down: the
    likeness is short, where the loudness line keeps its own over the whole piece.  The n values are brought to zero
    mean and unit standard deviation, as the loudness line is, so that `timing_sd` is the deviation a part gets
    whatever its length and a lasting lead or lag is left to `feel`.  With `gaps` (the n - 1 distances between
    successive values, in beats) the values are those of onsets that far apart: what is kept from one to the next
    is 1 - share to the power of the gap."""
    if not 0 < share <= 1:
        raise ValueError(f'correction is the share of its distance from the beat a player takes back each beat, over 0 and at most 1, not {share!r}')
    if n < 1:
        return np.zeros(0)
    e = rng.standard_normal(n)
    x = np.empty(n)
    x[0] = e[0]
    for i in range(1, n):
        kept = (1 - share) ** (1 / per_beat if gaps is None else max(0.0, float(gaps[i - 1])))
        x[i] = kept * x[i - 1] + math.sqrt(1 - kept * kept) * e[i]
    if n < 2:
        return np.zeros(n)
    x -= x.mean()
    return x / x.std() if x.std() > 0 else x


def lrc(n, rng, beta=.8):
    """n samples of 1/f^beta noise (long-range correlated), zero mean, unit standard deviation: the slow line of a
    part's loudness."""
    if n < 2:
        return np.zeros(n)
    m = 1 << (n - 1).bit_length()
    f = np.arange(m // 2 + 1, dtype=float)
    spectrum = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) / np.maximum(f, 1) ** (beta / 2)
    spectrum[0] = 0
    x = np.fft.irfft(spectrum, n=m)[:n]
    x -= x.mean()
    return x / x.std() if x.std() > 0 else x


def arch_shape(x):
    """KTH-style phrase arch: rises to a peak at 60% of the phrase and falls back, centred on zero."""
    return math.sin(math.pi * min(1, max(0, x)) ** 1.357) - .5


def phrase_positions(track, sections, melodic, beats_per_bar=4.0):
    """Position 0..1 of each note inside its phrase: rests of a beat or more for melodic parts, four-bar
    blocks from each section start otherwise (`beats_per_bar` quarter notes to a bar)."""
    notes = sorted(track['notes'], key=lambda n: n['on'])
    pos = {}
    if melodic:
        groups, cur = [], []
        for n in notes:
            if cur and n['on'] - max(c['on'] + c['duration'] for c in cur) >= 1 - 1e-9:
                groups.append(cur)
                cur = []
            cur.append(n)
        if cur:
            groups.append(cur)
        for g in groups:
            a, b = g[0]['on'], max(n['on'] + n['duration'] for n in g)
            for n in g:
                pos[n['id']] = (n['on'] - a) / max(b - a, 1e-9)
        return pos
    starts = sorted(s['start_bar'] * beats_per_bar for s in sections)
    span = 4 * beats_per_bar
    for n in notes:
        s = max([x for x in starts if x <= n['on'] + 1e-9], default=0)
        block = math.floor((n['on'] - s) / span) * span + s
        pos[n['id']] = (n['on'] - block) / span
    return pos


def profile_for(track, overrides):
    if track['id'] in overrides and overrides[track['id']] is None:
        return None
    role = ROLE_DEFAULTS.get(track.get('role'), ROLE_DEFAULTS['texture'])
    if role is None and track['id'] not in overrides:
        return None
    return {**BASE, **(role or {}), **(overrides.get(track['id']) or {})}


def apply(project, overrides=None, seed=1, drift='notes'):
    if drift not in ('notes', 'time'):
        raise ValueError("drift is 'time' (the player's distance from the beat runs in time: an added note changes no "
                         "other note's draws) or 'notes' (note by note)")
    overrides = overrides or {}
    report = {}
    for t in project['tracks']:
        prof = profile_for(t, overrides)
        if prof is None or not t['notes']:
            continue
        perf = t['performance']['notes']
        notes = sorted(t['notes'], key=lambda n: (n['on'], n['pitch']))
        onsets = sorted({round(n['on'], 6) for n in notes})
        rng = rng_for(seed, t['id'])
        meter = project['clock']['meter']
        if drift == 'time':
            # The slow lines span the piece on the sixteenth-note grid, so their values depend on the piece's length,
            # not on how many notes it has: the distance from the beat and the gates as a player keeping to the beat
            # (kept_to_the_beat, four values to the quarter note), the loudness as 1/f noise (lrc).  A
            # note in the last half of the score's last sixteenth rounds into the slot past it, which had grown the
            # grid by one and redrawn every note (GPT's review of 0.5, E04): the grid takes the slot a note starts in,
            # and the note the nearest slot inside the grid.
            span = max(1, int(round(project['clock']['bars'] * meter[0] * 4 / meter[1] * GRID)),
                       int(math.floor(onsets[-1] * GRID + 1e-9)) + 1)
            slow_t = kept_to_the_beat(span, rng, prof['correction'], GRID)
            slow_v = lrc(span, rng, prof['beta'])
            gates = kept_to_the_beat(span, rng, prof['correction'], GRID)
            cycle = rng.uniform(-1, 1, 16)
            slot = {o: min(span - 1, max(0, int(round(o * GRID)))) for o in onsets}
            # Each onset's motor delay, independent of the others, keyed by the onset itself (not by its slot of the
            # grid, which onsets nearer than a sixteenth share): a note added or removed changes no other onset's.  The
            # key is the onset in whole millionths of a beat, so that one beat written 1 or 1.0, or reached by another
            # sum, is one key (the third review of 0.6.0 found 1 and 1.0 drawing apart).
            fast_t = {o: float(rng_for(seed, f'{t["id"]}:short:{int(round(o * 1_000_000))}').standard_normal()) for o in onsets}
        else:
            # One value per onset in order, drawn in this order, each as far from the last as the onsets are in beats.
            slot = {o: k for k, o in enumerate(onsets)}
            apart = [b - a for a, b in zip(onsets, onsets[1:])]
            slow_t = kept_to_the_beat(len(onsets), rng, prof['correction'], gaps=apart)
            fast = rng.standard_normal(len(onsets))
            fast_t = {o: fast[k] for k, o in enumerate(onsets)}
            slow_v = lrc(len(onsets), rng, prof['beta'])
            gates = kept_to_the_beat(len(onsets), rng, prof['correction'], gaps=apart)
            cycle = rng.uniform(-1, 1, 16)
        melodic = t.get('role') in ('melody', 'countermelody')
        pos = phrase_positions(t, project['sections'], melodic, meter[0] * 4 / meter[1]) if prof['arch'] else {}
        mean_pitch = sum(n['pitch'] for n in notes) / len(notes)
        by_onset = {}
        for n in notes:
            by_onset.setdefault(round(n['on'], 6), []).append(n)
        widest = max(len(g) for g in by_onset.values())
        limit = (3 * (prof['timing_sd'] + prof['short_sd']) + abs(prof['feel']) + prof['lead'] + prof['spread']
                 + 1.15 * prof['strum'] * (widest - 1))
        moved, strokes = [], {'down': 0, 'up': 0}
        for o, group in by_onset.items():
            k = slot[o]
            shared = prof['feel'] + prof['timing_sd'] * slow_t[k] + prof['short_sd'] * fast_t[o]
            group = sorted(group, key=lambda n: n['pitch'])
            strummed = {}
            if prof['strum'] and len(group) > 1:
                # Keyed by the onset as a float, so that a beat written 1 strums as the same beat written 1.0.
                strummed, up = strum_offsets(o, group, prof, rng_for(seed, f'{t["id"]}:{float(o) + 0.0}'))
                strokes['up' if up else 'down'] += 1
            for j, n in enumerate(group):
                e = perf[n['id']]
                dt = shared
                if n['id'] in strummed:
                    dt += strummed[n['id']][0]
                elif len(group) > 1:
                    if prof['lead'] and j == len(group) - 1:
                        dt -= prof['lead']
                    elif prof['spread']:
                        dt += rng_for(seed, n['id']).uniform(-prof['spread'], prof['spread'])
                dt = max(-limit, min(limit, dt)) if limit else 0
                e['timing_ms'] = round(max(-100, min(100, e.get('timing_ms', 0) + dt)), 2)
                v = e['velocity'] * (1 + prof['vel_pct'] / 100 * slow_v[k]) * (strummed[n['id']][1] if n['id'] in strummed else 1)
                if prof['arch'] and n['id'] in pos:
                    v += prof['arch'] * arch_shape(pos[n['id']])
                if prof['high_loud']:
                    v += max(-6, min(6, prof['high_loud'] * (n['pitch'] - mean_pitch)))
                if prof['cymbal_cycle'] and n['pitch'] in CYMBALS:
                    v += prof['cymbal_cycle'] * cycle[int(round(n['on'] * 2)) % 16]
                e['velocity'] = int(max(1, min(127, round(v))))
                g = e.get('gate', 1)
                if prof['contrast']:
                    g *= (1 - prof['contrast']) if n['duration'] <= .5 else (1 + prof['contrast'] / 2) if n['duration'] >= 1.5 else 1
                if prof['gate_sd']:
                    g *= 1 + prof['gate_sd'] * gates[k]
                e['gate'] = round(max(.05, min(1.6, g)), 4)
                moved.append(dt)
        if prof['swell']:
            swell(t, prof['swell'])
        report[t['id']] = {'notes': len(notes), 'timing_sd_ms': round(float(np.std(moved)), 2),
                           'profile': {k: v for k, v in prof.items() if v and k not in ('beta', 'strum_grid', 'correction')}}
        if prof['strum']:
            report[t['id']]['strokes'] = strokes
    return report


def value_at(points, beat):
    before = [(b, v) for b, v in points if b <= beat + 1e-9]
    after = [(b, v) for b, v in points if b > beat + 1e-9]
    if not before:
        return after[0][1] if after else 100
    if after and after[0][0] > before[-1][0]:
        (b0, v0), (b1, v1) = before[-1], after[0]
        return v0 + (v1 - v0) * (beat - b0) / (b1 - b0)
    return before[-1][1]


def swell(track, depth):
    """Bow-like CC11 arc inside every held chord (1.5 beats or longer) on top of the part's existing CC11
    curve: in a little below it, up past it at 40%, easing back near the end.  Linear CC mode is required."""
    if track['performance'].get('cc_mode') != 'linear':
        raise ValueError(f'{track["id"]}: swells need cc_mode linear')
    base = sorted((b, v) for b, c, v in track['performance']['cc'] if c == 11)
    spans = sorted({(round(n['on'], 6), round(n['on'] + n['duration'], 6)) for n in track['notes'] if n['duration'] >= 1.5})
    arcs = []
    for a, b in spans:
        d = b - a
        arcs += [(a, -depth), (a + .4 * d, depth / 2), (a + .9 * d, -depth / 3)]
    if not arcs:
        return
    offset = dict(arcs)
    beats = sorted({b for b, _ in base} | set(offset))
    curve = []
    for beat in beats:
        v = value_at(base, beat) + offset.get(beat, 0)
        curve.append([round(beat, 4), 11, int(max(0, min(127, round(v))))])
    track['performance']['cc'] = sorted([x for x in track['performance']['cc'] if x[1] != 11] + curve,
                                        key=lambda x: (x[0], x[1]))
