"""Views of a written score: figures an agent that cannot hear can read its piece by.

Three tables, each counted from the project file alone and each named for its rule (research/design-0.7.md, 4.1):

- `parts_by_section`: which parts sound in each section, with their attacks, register and loudness there.  A part
  sounds in a section when a note of it does, attacked in the section or held into it.
- `harmony_pace`: how often the chord changes, by section.  A change is an entry of `harmony` whose chord differs
  from the chord before it; an entry that writes the same chord again is none.
- `melody_rhythm`: for each part with the role `melody`, its syncopated attacks and pushes by the rule `review`
  uses, the longest run it sounds without a rest, its phrases as `profile` guesses them, and its bar rhythms.

They describe.  None of them says a piece is good, and a figure is compared only with one counted the same way.
Times are written beats (quarter notes); performance timing is left out, velocities come from the performance.
"""
from collections import Counter

from . import harmony
from .model import Clock
from .profile import phrases, tick, top_line
from .review import _meter, attack_kinds, unpitched

REST = 0.5  # a gap between a part's written notes of half a beat or more is a rest; a shorter one is articulation
EPS = 1e-6

# The kind of a chord by what its symbol writes above the root (harmony.QUALITIES).  `triad`: three notes or fewer;
# `added`: a sixth or ninth added to a triad, no seventh; `seventh`: a seventh and nothing above it; `extended`: a
# seventh with a ninth, eleventh or thirteenth of the scale; `altered`: a seventh chord with a raised or lowered
# fifth, ninth, eleventh or thirteenth.  The division is this skill's, for counting; it is no judgement of a chord.
KINDS = {
    'triad': ('', 'maj', 'M', 'm', 'min', '-', '5', 'sus2', 'sus4', 'sus', 'dim', 'o', 'aug', '+'),
    'added': ('6', 'm6', 'add9', 'madd9', '6/9', '69'),
    'seventh': ('7', 'maj7', 'M7', 'm7', 'min7', '-7', 'mMaj7', 'mmaj7', '7sus4', '7sus', 'dim7', 'o7', 'm7b5', 'ø', 'ø7'),
    'extended': ('9', 'maj9', 'M9', 'm9', '11', 'm11', '13', 'maj13', 'm13', '9sus4'),
    'altered': ('7#5', '+7', '7b5', '7b9', '7#9', '7#11', 'maj7#11', '7b13'),
}
KIND_OF = {quality: kind for kind, qualities in KINDS.items() for quality in qualities}


def spans(p, clock):
    """[(section id, first beat, beat after the last, bars)] of the project's sections."""
    bpb = clock.beats_per_bar
    return [(s['id'], s['start_bar'] * bpb, (s['start_bar'] + s['bars']) * bpb, s['bars']) for s in p.get('sections', [])]


def parts_by_section(p, clock=None):
    """Per section, the parts that sound in it: {'section', 'bars', 'parts': {part: {...}}}.  For a part: `attacks`
    (notes that begin in the section), `held_in` (notes begun before it that still sound in it), `notes_per_bar` (of
    the attacks), `low` and `high` (the pitches sounding, for a pitched part) and `velocity` (the mean performed
    velocity of the attacks).  A part with neither an attack nor a held note in the section is left out."""
    clock = clock or Clock(p)
    rows = []
    for name, lo, hi, bars in spans(p, clock):
        parts = {}
        for t in p['tracks']:
            inside = [n for n in t['notes'] if n['on'] < hi - EPS and n['on'] + n['duration'] > lo + EPS]
            if not inside:
                continue
            attacks = [n for n in inside if n['on'] >= lo - EPS]
            row = {'role': t.get('role'), 'attacks': len(attacks), 'held_in': len(inside) - len(attacks),
                   'notes_per_bar': round(len(attacks) / max(bars, 1), 2)}
            if not unpitched(t):
                row['low'], row['high'] = min(n['pitch'] for n in inside), max(n['pitch'] for n in inside)
            perf = (t.get('performance') or {}).get('notes') or {}
            vel = [perf[n['id']]['velocity'] for n in attacks if n.get('id') in perf and 'velocity' in perf[n['id']]]
            if vel:
                row['velocity'] = round(sum(vel) / len(vel), 1)
            parts[t['id']] = row
        rows.append({'section': name, 'bars': bars, 'parts': parts})
    return rows


def part_sets(rows):
    """The set of parts sounding in each section, in the sections' order."""
    return [tuple(sorted(r['parts'])) for r in rows]


def _identity(chord, symbol):
    """What makes two written chords the same chord: root, the notes above it and the bass, however the symbol is
    spelled (Db and C#, maj and M).  A symbol the parser does not know is itself."""
    if chord is None:
        return ('?', symbol)
    return (chord['root'], tuple(sorted(harmony.QUALITIES[chord['quality']])), chord['bass'])


def harmony_pace(p, clock=None):
    """How often the chord changes: {'entries', 'changes', 'changes_per_bar', 'entries_per_bar', 'kinds', 'unknown',
    'sections': [...]}.  A change is an entry whose chord (`_identity`) differs from the chord before it, so a new bass
    under the same chord is a change and the same chord written again is none.  The first chord of the piece is no
    change.  `kinds` counts the entries that are changes, by KINDS; `unknown` lists symbols the parser does not read.
    None for a project without `harmony`."""
    clock = clock or Clock(p)
    entries = p.get('harmony')
    if not isinstance(entries, list) or not entries:
        return None
    bpb = clock.beats_per_bar
    # Sorted by beat and symbol and no further: two entries at one beat with one symbol and different transpositions
    # pass validate, and sorting the parsed chords themselves compared two dicts (the review of 0.7's code, F06).
    line = sorted((((h['bar'] - 1) * bpb + h.get('beat', 0), h['symbol'],
                    harmony.parse(h['symbol'], h.get('transpose_semitones', 0))) for h in entries), key=lambda e: e[:2])
    events, before = [], None
    for beat, symbol, chord in line:
        ident = _identity(chord, symbol)
        events.append((beat, ident != before and before is not None, KIND_OF.get(chord['quality'], 'unknown') if chord else 'unknown',
                       before is None))
        before = ident
    bars = p['clock']['bars']
    out = {'entries': len(events), 'changes': sum(1 for e in events if e[1]),
           'entries_per_bar': round(len(events) / bars, 2), 'changes_per_bar': round(sum(1 for e in events if e[1]) / bars, 2),
           'kinds': dict(Counter(e[2] for e in events if e[1] or e[3])),
           'unknown': sorted({s for _, s, c in line if c is None}), 'sections': []}
    for name, lo, hi, n in spans(p, clock):
        inside = [e for e in events if lo - EPS <= e[0] < hi - EPS]
        changes = sum(1 for e in inside if e[1])
        out['sections'].append({'section': name, 'bars': n, 'entries': len(inside), 'changes': changes,
                                'changes_per_bar': round(changes / max(n, 1), 2),
                                'kinds': dict(Counter(e[2] for e in inside if e[1] or e[3]))})
    return out


def runs(notes, rest=REST):
    """The stretches a part sounds without a rest: [(first beat, last beat)], a new one after a gap of `rest` beats or
    more between the end of everything sounding and the next attack.  Notes' lengths do not end a run: four notes of
    two beats each, one after the other, are one run of eight beats."""
    out = []
    start = end = None
    for n in sorted(notes, key=lambda n: n['on']):
        if end is None or n['on'] - end >= rest - EPS:
            if end is not None:
                out.append((start, end))
            start, end = n['on'], n['on'] + n['duration']
        else:
            end = max(end, n['on'] + n['duration'])
    if end is not None:
        out.append((start, end))
    return out


def melody_rhythm(p, clock=None):
    """For each part with the role `melody` that has notes: {'part', 'attacks', 'syncopated_pct', 'pushes_pct',
    'longest_run', 'bar_rhythms', 'sections': [...]}.

    `syncopated_pct` and `pushes_pct` are `review`'s (review.attack_kinds): an attack is syncopated when the next
    stronger position of the bar passes before the part's next attack, the note held over that position or stopped
    before it; a push is such an attack at most half a beat before a downbeat or half-bar.  `longest_run` is the
    longest stretch the part sounds without a rest of half a beat (`runs`), in beats and seconds with the bars it
    spans.  `bar_rhythms` is how many different sets of attack positions its bars have, to the grid of `profile`.
    Per section: its attacks there, how many are syncopated and pushes, the rests that begin in it, and the phrases
    `profile` guesses (a phrase ends at a rest of half a beat or at a note held a beat and a half)."""
    clock = clock or Clock(p)
    bpb, meter, end = clock.beats_per_bar, _meter(p), p['clock']['bars'] * clock.beats_per_bar
    out = []
    for t in p['tracks']:
        if t.get('role') != 'melody' or not t['notes'] or unpitched(t):
            continue
        onsets = sorted({round(n['on'], 4) for n in t['notes']})
        kinds = attack_kinds(onsets, bpb, meter, end)
        stretches = runs(t['notes'])
        # The longest in time: with a change of tempo the run of most beats is not the one that lasts longest, and
        # its seconds were shown as the longest (the review of 0.7's code, F12).
        a, b = max(stretches, key=lambda r: (clock.seconds(r[1]) - clock.seconds(r[0]), r[1] - r[0]))
        patterns = {}
        for on in onsets:
            patterns.setdefault(int(on // bpb + 1e-9), set()).add(tick(on % bpb))
        line = top_line(t['notes'])
        row = {'part': t['id'], 'attacks': len(onsets),
               'syncopated_pct': round(100 * sum(1 for _, s, _ in kinds if s) / len(onsets), 1),
               'pushes_pct': round(100 * sum(1 for _, _, q in kinds if q) / len(onsets), 1),
               'longest_run': {'beats': round(b - a, 3), 'seconds': round(clock.seconds(b) - clock.seconds(a), 2),
                               'from_bar': int(a // bpb + 1e-9) + 1, 'to_bar': int((b - EPS) // bpb) + 1},
               'bar_rhythms': len({frozenset(v) for v in patterns.values()}), 'sections': []}
        for name, lo, hi, n in spans(p, clock):
            inside = [k for k in kinds if lo - EPS <= k[0] < hi - EPS]
            gaps = sum(1 for (_, e), (s, _) in zip(stretches, stretches[1:]) if lo - EPS <= e < hi - EPS)
            row['sections'].append({'section': name, 'attacks': len(inside),
                                    'syncopated': sum(1 for _, s, _ in inside if s), 'pushes': sum(1 for _, _, q in inside if q),
                                    'rests': gaps, 'phrases': len(phrases([x for x in line if lo - EPS <= x['on'] < hi - EPS]))})
        out.append(row)
    return out


def views(p):
    """The three views of a project."""
    clock = Clock(p)
    rows = parts_by_section(p, clock)
    return {'parts_by_section': rows, 'part_sets': len(set(part_sets(rows))),
            'harmony_pace': harmony_pace(p, clock), 'melody_rhythm': melody_rhythm(p, clock)}


ROLE_ORDER = ('melody', 'countermelody', 'accent', 'harmony', 'rhythm', 'texture', 'bass', 'drums')
WIDE = 14  # sections a table shows side by side; a piece with more is shown in blocks of this many


def _cell(row):
    """A part's cell for a section: its notes per bar there, `held` where it only holds notes begun earlier, `.` where
    it is silent."""
    if row is None:
        return '.'
    if not row['attacks']:
        return 'held'
    n = row['notes_per_bar']
    return f'{n:.0f}' if n >= 9.5 else f'{n:.1f}'.rstrip('0').rstrip('.')


def describe(v):
    """The views as short text, for the head of a review's summary.  Every figure is given with its rule, so that it
    is read for what it counts."""
    rows = v['parts_by_section']
    if not rows:
        return ''
    lines = ['The score at a glance (counted from the project; a description, not a judgement).',
             'Parts by section: notes a bar; `held`: only notes begun earlier still sound; `.`: silent.']
    parts = {}
    for r in rows:
        for name, row in r['parts'].items():
            parts.setdefault(name, row.get('role'))
    order = sorted(parts, key=lambda n: (ROLE_ORDER.index(parts[n]) if parts[n] in ROLE_ORDER else len(ROLE_ORDER), n))
    label = max([len(f'{n} ({parts[n]})') for n in order] + [8])
    width = max([len(r['section']) for r in rows] + [4]) + 2
    for start in range(0, len(rows), WIDE):
        block = rows[start:start + WIDE]
        lines.append(f'  {"":{label}}' + ''.join(f'{r["section"]:>{width}}' for r in block))
        lines.append(f'  {"bars":{label}}' + ''.join(f'{r["bars"]:>{width}}' for r in block))
        for n in order:
            lines.append(f'  {f"{n} ({parts[n]})":{label}}' + ''.join(f'{_cell(r["parts"].get(n)):>{width}}' for r in block))
        lines.append(f'  {"sounding":{label}}' + ''.join(f'{len(r["parts"]):>{width}}' for r in block))
    sets = part_sets(rows)
    lines.append(f'  {len(set(sets))} different set{"s" if len(set(sets)) != 1 else ""} of parts over {len(rows)} sections.')
    h = v['harmony_pace']
    if h:
        by = ', '.join(f'{s["section"]} {s["changes_per_bar"]:g}' for s in h['sections'])
        kinds = ', '.join(f'{k} {n}' for k, n in sorted(h['kinds'].items(), key=lambda kv: -kv[1]))
        lines.append(f'Harmony: {h["changes"]} chord changes in {h["entries"]} entries (a change is a chord that differs from the '
                     f'one before it; the same chord written again is none), {h["changes_per_bar"]:g} a bar. By section: {by}. '
                     f'Kinds of chord: {kinds}.' + (f' Not read: {", ".join(h["unknown"])}.' if h['unknown'] else ''))
    for m in v['melody_rhythm']:
        run = m['longest_run']
        rests = ', '.join(f'{s["section"]} {s["rests"]}' for s in m['sections'] if s['attacks'])
        lines.append(f'Melody ({m["part"]}): of {m["attacks"]} attacks {m["syncopated_pct"]:g}% are syncopated (the next stronger '
                     f'position of the bar passes before the next attack) and {m["pushes_pct"]:g}% push a downbeat or half-bar. '
                     f'Longest stretch without a rest of half a beat: {run["seconds"]:g} s, bars {run["from_bar"]}-{run["to_bar"]}. '
                     f'Rests by section: {rests}. {m["bar_rhythms"]} different bar rhythms.')
    return '\n'.join(lines)
