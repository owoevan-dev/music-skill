"""Search the Surge XT catalog (references/surge-catalog.json): every factory and third-party patch of Surge XT 1.3.4,
measured on one probe note in its role's register, by role, measured character, name and source, for a shortlist to
hear on the part itself (studio.py audition).

The catalog is how a part's sound is designed.  The two measures found most often with the dimensions on which
listeners tell timbres apart are the spectral centroid, heard as brightness, and the logarithm of the attack time
(McAdams and Giordano 2015, reporting among others Caclin et al. 2005, who confirmed both with synthetic tones), and
the catalog holds both for every patch, so a sound of a wanted brightness and attack is chosen by range (`centroid`,
`attack`).  Moving a patch's own controls toward such a target was tried and is not offered (research/design-0.6.md,
section 19): over 120 patches, a low-pass filter moved an octave moved the centroid 0.19 octave at the median, and
an amplitude attack set to 200 ms measured as 100 to 300 ms in 42 of 92 fast patches.  Each figure is the median of
three playings of the probe; a patch whose centroid differed by over 10% between them is called moving and the
others steady (1,144 and 1,853 of those measured): a moving patch's brightness is not one number.

A patch the measurement flagged is left out unless asked for: silent on a plain note (it waits for aftertouch, MPE or
the wheel), did not render, built for MPE, microtonal, or off its written pitch; for a pitched role, also one with no
clear pitch.  The figures describe the probe note, not the music: the shortlist is where listening starts.

When more patches match than the shortlist holds, it is a spread rather than the first ones dark to bright: the
matches, ordered dark to bright, are cut into as many bands as the shortlist has places, and each band gives one
patch, a designer not yet shown first.  The piece's seed (`seed`) picks within each band, so two pieces asking the
same question see different patches.  Showing every agent the same first few is the shared starting point that
makes work alike (Doshi and Hauser 2024): the 0.4.0 agent pieces took 71% of their Surge parts from the fifty curated
patches, and five patches recurred across pieces."""
from collections import Counter

import numpy as np

from . import surge

HIDDEN = {'silent on a plain note', 'did not render', 'MPE', 'microtonal', 'off its written pitch'}
PITCHED = {'lead', 'brass', 'pad', 'chords', 'keys', 'pluck', 'bass'}


def describe(key):
    """One catalog patch in full: its measurement, flags, and what its mod wheel and each routed macro move."""
    e = surge.catalog().get(key)
    if e is None:
        raise ValueError(f'No catalog patch {key!r}: studio.py sounds lists the ids')
    return {'id': key, **{k: v for k, v in e.items() if k not in ('sha256', 'bytes')}}


def spread(rows, limit, seed=None):
    """`limit` of the rows (ordered dark to bright), one from each of `limit` bands of the order, a source not yet
    shown preferred; the seed picks within a band, else the band's middle."""
    if len(rows) <= limit:
        return rows
    rng = np.random.default_rng(seed) if seed is not None else None
    shown, used = [], Counter()
    for band in np.array_split(np.arange(len(rows)), limit):
        fewest = min(used[rows[i]['source']] for i in band)
        pool = [rows[i] for i in band if used[rows[i]['source']] == fewest]
        pick = pool[int(rng.integers(len(pool)))] if rng is not None else pool[len(pool) // 2]
        used[pick['source']] += 1
        shown.append(pick)
    return shown


def within(value, span):
    """Whether `value` lies in `span`, (lowest, highest) with None for an open end; a patch without the figure does
    not."""
    if span is None:
        return True
    lo, hi = span
    return value is not None and (lo is None or value >= lo) and (hi is None or value <= hi)


def search(role=None, character=(), name=None, source=None, limit=25, everything=False, seed=None, centroid=None, attack=None):
    """The catalog's patches that match, as a shortlist.  `centroid` (Hz) and `attack` (seconds) are (lowest, highest)
    ranges of the probe note's figures, either end None for open."""
    rows = []
    for key, e in surge.catalog().items():
        if role and e['role'] != role:
            continue
        if source and source.lower() not in e['source'].lower():
            continue
        if name and name.lower() not in (e['name'] + ' ' + e['category']).lower():
            continue
        flags = set(e.get('flags', []))
        if not everything and (flags & HIDDEN or ('no clear pitch' in flags and e['role'] in PITCHED)
                               or e['role'] == 'special' or 'measured' not in e):
            continue
        words = e.get('character', '')
        if any(w.strip() and w.strip().lower() not in words for w in character):
            continue
        m = e.get('measured', {})
        if not (within(m.get('centroid_hz'), centroid) and within(m.get('attack_s'), attack)):
            continue
        rows.append({'id': key, 'role': e['role'], 'character': words, 'centroid_hz': m.get('centroid_hz'),
                     'centroid_spread_pct': m.get('centroid_spread_pct'),
                     'above_2k_pct': m.get('above_2k_pct'), 'attack_s': m.get('attack_s'), 'tail_s': m.get('tail_s'),
                     'source': e['source'], 'category': e['category'], 'flags': e.get('flags', []),
                     'wheel': e.get('wheel', [])[:2],
                     'labelled_macros': {k: v['label'] for k, v in e.get('macros', {}).items() if v.get('label')}})
    rows.sort(key=lambda r: (r['centroid_hz'] is None, r['centroid_hz'] or 0, r['id']))
    shown = spread(rows, limit, seed)
    note = ('Ordered dark to bright by the probe note (the median of three playings; centroid_spread_pct is how far the '
            'centroid moved between them). Play two to four on the part with studio.py audition; the figures describe '
            'one note, not how a patch sits in the music.')
    if len(rows) > len(shown):
        note += (f' {len(shown)} of {len(rows)} matches, spread over the range and the designers'
                 + (" and picked by this piece's seed" if seed is not None else '; pass the piece\'s --seed for its '
                    'own picks') + '; --limit shows more.')
    return {'count': len(rows), 'shown': shown, 'note': note}
