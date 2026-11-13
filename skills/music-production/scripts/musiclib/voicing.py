"""Voicings that move smoothly through a chord progression, for a composition script to give its keyboard, pad, string
or brass parts their pitches.  It chooses pitches, not rhythm: the part's rhythm, register plan and articulation stay
the composer's.

Each chord's tones are placed in `voices` notes between `low` and `high`, and the voicings are chosen together across
the whole progression by dynamic programming, so the parts move as little as possible: common tones held, the others
to the nearest chord tone.  This is efficient voice leading in Tymoczko's sense (2011); pitch proximity is also what
keeps each voice heard as one line (Huron 2001).  The top voice, the most audible, counts one and a half times, a leap
past a fifth costs extra, and a drift of the whole voicing away from the middle of the range (or from `start`) is
resisted, so a long progression neither climbs nor sinks.

Spacing follows arranging practice: adjacent voices at most `max_gap` semitones apart (an octave by default), no
doubled pitch, no close interval under its low interval limit, where it turns muddy (LOW_INTERVAL_LIMITS), and no
minor second or minor ninth between any two voices: a major seventh is fine, the seventh a semitone under the root is
not (references/arrangement.md, vertical hygiene).  `against` gives, per chord, the pitches other parts already sound
there (the bass, the melody, a voicing made first), and the voicing keeps the same distance from them and, where it
can, leaves their pitches to them: a unison only doubles what already sounds, and the two hands of one piano cannot
strike one key at once.  Voice the parts in dependency order, each avoiding what sounds before it.  A chord that
cannot meet these rules in its range gives up the unisons first, then the distance from the other parts, then the
spacing rules.  Voices never cross, since each keeps its rank.  A chord whose spacing rules were given up is named in
a warning with its range (`GivenUp`), since the result can then hold a minor second or a close interval below its
limit: four voices of a ninth chord between G3 and A4 have no other voicing than a cluster.
With `avoid_parallels`, voicings without consecutive perfect fifths or octaves between any two voices are chosen
wherever the range allows one, at any cost in motion, as common-practice and choral writing ask; where it allows none
(three voices for D then E between C4 and C5 have one voicing each), the fewest remain.  `review` lists parallels
between parts that each play one line, as voices written a part each, but not inside one chord part.  Pop and rock
move in parallel on purpose (power chords), so it is off by default.

With fewer voices than chord tones, tones are left out in the order arrangers drop them: the perfect fifth, the root
(the bass part plays it), an eleventh, a ninth; under a major seventh the root goes before the fifth, as it would rub
against the seventh a semitone away.  Where no bass part plays the root (a piano or pad alone), `keep_root` keeps it:
a rootless A-flat major seventh in three voices, C E-flat G, is heard as C minor.  The third or the suspended tone, the seventh or sixth, a thirteenth and altered
tones stay.  With more voices than tones, the root is doubled, then the fifth, then the others, skipping a tone that
lies a semitone from another chord tone (a doubled root under a major seventh).  When the range or the rules leave no
room for a chord as it stands, the next doubling in that order is tried (the fifth when the range holds one root),
then one more tone left out (a major seventh without its root, which the bass plays, rather than the seventh a
semitone under the root), then any tone that would rub against `against` wherever the range puts it (the major seventh
under a melody that sings the root: the chord becomes a triad; the third stays), before any rule is given up.  A slash
chord's bass note belongs to the bass part; the voicing uses the chord's own tones.
"""
import itertools
import warnings

import numpy as np

from .harmony import QUALITIES, parse

# The lowest note (MIDI number) of each interval, in semitones up to a major tenth, that stays clear of mud: Robin
# Hoffmann's chart of low interval limits (https://www.robin-hoffmann.com/dfsb/low-interval-limits/).  Arrangers' guides,
# not laws; Sweetwater's glossary gives a close table (https://www.sweetwater.com/insync/low-interval-limit/).
LOW_INTERVAL_LIMITS = {1: 52, 2: 51, 3: 48, 4: 46, 5: 46, 6: 46, 7: 34, 8: 43, 9: 41, 10: 41, 11: 41,
                       13: 40, 14: 39, 15: 36, 16: 34}
TOP_WEIGHT, LEAP_COST, DRIFT_COST = 1.5, 1.0, .3
PARALLEL_COST = 1e6  # more than any motion can cost: parallels go first wherever the range allows


class GivenUp(UserWarning):
    """A chord's range left no voicing that keeps the spacing rules, and one that breaks them was taken."""


def chord_tones(symbol, voices, rotation=0, omit=0, exclude=(), keep_root=False):
    """The pitch classes one chord gives `voices` voices, with the omissions or doublings above; `rotation` starts the
    doublings further down their order (the fifth instead of the root, say), `omit` leaves out that many more tones in
    the same order, `exclude` leaves out the tones with these pitch classes first, and `keep_root` never leaves out the
    root (where no bass part plays it)."""
    c = parse(symbol)
    if c is None:
        raise ValueError(f'Unknown chord symbol: {symbol}')
    iv = [i for i in dict.fromkeys(QUALITIES[c['quality']]) if (c['root'] + i) % 12 not in exclude]
    third = any(i in iv for i in (3, 4))
    colour = any(i in iv for i in (9, 10, 11))
    major_seventh = 11 in iv

    def rank(i):
        """How readily a tone is left out: lower goes first; 9 never."""
        if i == 7:
            return .5 if major_seventh else 0
        if i == 0:
            return 9 if keep_root else 0 if major_seventh else 1
        if i == 5 and third:
            return 2
        if i == 2 and third and colour:
            return 3
        return 9
    keep = sorted(iv, key=rank)
    while len(keep) > voices and rank(keep[0]) < 9:
        keep.pop(0)
    if len(keep) > voices:
        raise ValueError(f'{symbol} needs at least {len(keep)} voices')
    for _ in range(omit):
        if len(keep) > 1 and rank(keep[0]) < 9:
            keep.pop(0)
    order = ([i for i in (0, 7) if i in keep] + [i for i in keep if i not in (0, 7, 3, 4)]
             + [i for i in keep if i in (3, 4)])
    clear = [i for i in order if not any((i - j) % 12 in (1, 11) for j in keep if j != i)]
    doubling = clear or order
    out, k = list(keep), rotation
    while len(out) < voices:
        out.append(doubling[k % len(doubling)])
        k += 1
    return [(c['root'] + i) % 12 for i in out]


def _rubs(a, b):
    """A minor second or minor ninth between two pitches."""
    return abs(a - b) in (1, 13)


def candidates(pcs, low, high, max_gap=12, limits=True, against=(), unisons=True):
    """Every voicing of the pitch classes (one per voice) between low and high, sorted upward and spaced as above;
    with `limits`, also clear of the low interval limits, of minor seconds and ninths, and of rubs against `against`,
    and without `unisons`, of the pitches in `against` too."""
    options = [[p for p in range(low, high + 1) if p % 12 == pc] for pc in pcs]
    found = set()
    for combo in itertools.product(*options):
        v = tuple(sorted(combo))
        if len(set(v)) < len(v) or any(b - a > max_gap for a, b in zip(v, v[1:])):
            continue
        if limits and (any(a < LOW_INTERVAL_LIMITS.get(b - a, 0) for a, b in zip(v, v[1:]))
                       or any(_rubs(a, b) for a, b in itertools.combinations(v, 2))
                       or any(_rubs(a, b) or (a == b and not unisons) for a in v for b in against)):
            continue
        found.add(v)
    return sorted(found)


def _parallels(a, b, d):
    """For every pair of candidate voicings (a before, b after, d their differences), how many voice pairs move in
    consecutive perfect fifths or octaves: the same perfect interval twice, both voices moving the same way."""
    count = np.zeros(d.shape[:2])
    n = a.shape[1]
    for i in range(n):
        for j in range(i + 1, n):
            ia, ib = (a[:, j] - a[:, i]) % 12, (b[:, j] - b[:, i]) % 12
            same = (ia[:, None] == ib[None, :]) & np.isin(ia, (0, 7))[:, None]
            si, sj = np.sign(d[..., i]), np.sign(d[..., j])
            count += same & (si == sj) & (si != 0)
    return count


def voice_lead(symbols, voices=4, low=48, high=79, start=None, ceilings=None, avoid_parallels=False, max_gap=12,
               against=None, keep_root=False):
    """One voicing per chord symbol (a list of MIDI pitches, low to high), chosen across the whole progression to move
    as little as possible.  `start` is a voicing to begin near; `ceilings` gives, per chord, a highest pitch the voices
    may reach (under a melody, say) or None; `against` gives, per chord, the pitches other parts sound with it;
    `keep_root` (True, or one value per chord) keeps the root where no bass part plays it.  See the module notes for the
    spacing, omissions and costs."""
    if not symbols:
        return []
    cands = []
    for k, symbol in enumerate(symbols):
        top = min(high, ceilings[k]) if ceilings is not None and ceilings[k] is not None else high
        sets = []
        root = keep_root[k] if isinstance(keep_root, (list, tuple)) else keep_root
        for omit, r in itertools.product((0, 1), range(voices)):  # the doublings in order, then one tone fewer
            pcs = chord_tones(symbol, voices, r, omit, keep_root=root)
            if sorted(pcs) not in [sorted(x) for x in sets]:
                sets.append(pcs)
        others = tuple(against[k]) if against is not None and against[k] else ()
        # A tone that rubs against the other parts wherever the range puts it (a major seventh under a melody on the
        # root) is left out, as long as the chord keeps its third and two tones.
        tones = {pc for pcs in sets for pc in pcs}
        places = {pc: [p for p in range(low, top + 1) if p % 12 == pc] for pc in tones}
        blocked = {pc for pc in tones if places[pc] and all(any(_rubs(p, a) for a in others) for p in places[pc])}
        c0 = parse(symbol)
        thirds = {(c0['root'] + i) % 12 for i in (3, 4, 5) if i in QUALITIES[c0['quality']]}
        if blocked and not blocked & thirds and len(tones - blocked) >= 2:
            for r in range(voices):
                pcs = chord_tones(symbol, voices, r, 0, exclude=blocked - ({c0['root']} if root else set()),
                                  keep_root=root)
                if sorted(pcs) not in [sorted(x) for x in sets]:
                    sets.append(pcs)
        c = None
        for rules in ({'against': others, 'unisons': False}, {'against': others}, {}, {'limits': False}):
            c = next((found for pcs in sets if (found := candidates(pcs, low, top, max_gap, **rules))), None)
            if c:
                break
        if not c:
            raise ValueError(f'No voicing of {symbol} in {voices} voices between {low} and {top}; widen the range')
        if rules.get('limits') is False:
            # Said, not silent: a session of the 0.7 baseline gave four voices fourteen semitones, got a cluster for
            # its ninth chord and dropped the function for voicings written by hand.
            warnings.warn(f'voice_lead: {symbol} (chord {k + 1}) has no voicing in {voices} voices between {low} and {top} that '
                          'keeps the spacing rules (no minor second or ninth between two voices, no close interval under '
                          'its low limit), so one that breaks them was taken. Widen the range, lower `low`, or give it '
                          'fewer voices.', GivenUp, stacklevel=2)
        cands.append(np.array(c, dtype=float))
    centre = (low + high) / 2 if start is None else float(np.mean(start))
    drift = lambda c: DRIFT_COST * np.abs(c.mean(axis=1) - centre)
    cost = drift(cands[0])
    if start is not None:
        if len(start) != voices:
            raise ValueError(f'start has {len(start)} pitches for {voices} voices')
        cost = cost + np.abs(cands[0] - np.array(sorted(start), dtype=float)).sum(axis=1)
    back = []
    for a, b in zip(cands, cands[1:]):
        d = b[None, :, :] - a[:, None, :]
        step = np.abs(d)
        motion = step.sum(-1) + (TOP_WEIGHT - 1) * step[..., -1] + LEAP_COST * np.maximum(step - 7, 0).sum(-1)
        if avoid_parallels:
            motion = motion + PARALLEL_COST * _parallels(a, b, d)
        total = cost[:, None] + motion
        back.append(total.argmin(axis=0))
        cost = total.min(axis=0) + drift(b)
    k = int(cost.argmin())
    path = [k]
    for pointers in reversed(back):
        k = int(pointers[k])
        path.append(k)
    path.reverse()
    return [[int(x) for x in cands[i][j]] for i, j in enumerate(path)]
