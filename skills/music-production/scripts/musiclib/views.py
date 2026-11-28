"""Views of a written score: figures an agent that cannot hear can read its piece by.

Four tables, each counted from the project file alone and each named for its rule (research/design-0.7.md, 4.1;
the fourth from 0.11):

- `parts_by_section`: which parts sound in each section, with their attacks, register and loudness there.  A part
  sounds in a section when a note of it does, attacked in the section or held into it.
- `harmony_pace`: how often the chord changes, by section.  A change is an entry of `harmony` whose chord differs
  from the chord before it; an entry that writes the same chord again is none.
- `melody_rhythm`: for each part with the role `melody`, its syncopated attacks and pushes by the rule `review`
  uses, the longest run it sounds without a rest, its phrases as `profile` guesses them, and its bar rhythms.
- `accompaniment`: for each other pitched part, how many bar rhythms and chord shapes it plays and how much of it the
  commonest of each takes, over the piece and by section (a part that keeps one rhythm and one shape through sections
  that should differ is a question of `review`'s, where the style or the plan says they should).

They describe.  None of them says a piece is good, and a figure is compared only with one counted the same way.
Times are written beats (quarter notes); performance timing is left out, velocities come from the performance.
"""
from collections import Counter

from . import harmony
from .files import one_line
from .model import Clock
from .profile import STEPS, phrases, tick, top_line
from .review import _meter, attack_kinds, unpitched

REST = 0.5  # a gap between a part's written notes of half a beat or more is a rest; a shorter one is articulation
EPS = 1e-6

# The kind of a chord by what its symbol writes above the root (harmony.QUALITIES).  `triad`: three notes or fewer;
# `added`: a sixth or ninth added to a triad, no seventh; `seventh`: a seventh and nothing above it; `extended`: a
# seventh with a ninth, eleventh or thirteenth of the scale; `altered`: a seventh chord with a raised or lowered
# fifth, ninth, eleventh or thirteenth.  The division is this skill's, for counting; it is no judgement of a chord.
KINDS = {
    'triad': ('', 'maj', 'M', 'm', 'min', '-', '5', 'sus2', 'sus4', 'sus', 'dim', 'o', 'aug', '+'),
    'added': ('6', 'm6', 'add9', 'madd9', '6/9', '69', '6/9#11', '69#11'),
    'seventh': ('7', 'maj7', 'M7', 'm7', 'min7', '-7', 'mMaj7', 'mmaj7', '7sus4', '7sus', 'dim7', 'o7', 'm7b5', 'ø', 'ø7'),
    'extended': ('9', 'maj9', 'M9', 'm9', '11', 'm11', '13', 'maj13', 'm13', '9sus4', '13sus', '13sus4'),
    'altered': ('7#5', '+7', '7b5', '7b9', '7#9', '7#11', 'maj7#11', '7b13', '9#11', 'maj9#11', 'maj13#11'),
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


# Chord kinds by their pitch classes in any inversion (a division for counting, no judgement of a chord): a fifth (or a fourth,
# its inversion) is `power`, octaves alone `octave`, the four triads `triad`, a suspended fourth or second `sus`, the
# seventh chords on those triads and their shells (root, third and seventh) `seventh`, anything else `added` (sixths, added
# ninths, clusters).
TRIADS = {(0, 4, 7), (0, 3, 7), (0, 3, 6), (0, 4, 8)}
SUSPENDED = {(0, 5, 7), (0, 2, 7)}
SEVENTHS = {(0, 4, 7, 10), (0, 4, 7, 11), (0, 3, 7, 10), (0, 3, 7, 11), (0, 3, 6, 10), (0, 3, 6, 9), (0, 4, 8, 10), (0, 4, 8, 11),
            (0, 4, 10), (0, 3, 10), (0, 4, 11), (0, 3, 11)}   # (the last four: shells, root, third and seventh)


def chord_kind(shape):
    """A chord's kind (power, octave, triad, sus, seventh or added) from its notes or their distances above the lowest,
    whatever its inversion: E-G-C is a triad as C-E-G is."""
    pcs = sorted({int(x) % 12 for x in shape})
    if len(pcs) == 1:
        return 'octave'
    for kind, sets in (('power', {(0, 7)}), ('triad', TRIADS), ('sus', SUSPENDED), ('seventh', SEVENTHS)):
        if any(tuple(sorted((q - root) % 12 for q in pcs)) in sets for root in pcs):
            return kind
    return 'added'


def _beats(ticks):
    """Attack positions in a bar as beats from 1: '1 1.5 2 3.5'."""
    return ' '.join(f'{1 + t / STEPS:.3f}'.rstrip('0').rstrip('.') for t in sorted(ticks))


def _median(values):
    values = sorted(values)
    if not values:
        return None
    k = len(values) // 2
    return float(values[k]) if len(values) % 2 else (values[k - 1] + values[k]) / 2


def accompaniment(p, clock=None, min_bars=4, presence=.75):
    """For each pitched part with notes that is not a melody (0.11): how many bar rhythms and chords it plays and how much
    of it the commonest of each takes, over the piece and section by section: {'part', 'role', 'bars', 'rhythms', 'rhythm',
    'rhythm_share', 'attacks', 'chords', 'shapes', 'shape', 'shape_share', 'kind', 'kind_share', 'kinds', 'register',
    'length', 'sections', 'short', 'absent'}.

    A bar's rhythm is the set of its attack positions, to the grid of `profile` (as `melody_rhythm` counts the melody's
    bar rhythms); `rhythm` is the commonest, as beats from 1, and `rhythm_share` the share of the bars that play it: over
    the piece, of the bars the part plays in; in a section, of the section's bars, so a bar the part rests in counts
    against it.  A chord is two or more notes attacked at one written position (`attacks` counts the positions); its shape
    is their distances in semitones above the lowest note (a power chord with its octave is 0-7-12 wherever it lies), its
    kind `chord_kind`'s (in any inversion); `shape` and `kind` are the commonest, their shares of the chords, `kinds` the
    count by kind.  `register` is the median pitch of the notes attacked, `length` their median written length in beats.
    A section is described for a part where it is `min_bars` bars or longer and the part attacks in at least `presence`
    of its bars; such a section where it does not is listed in `absent`.  A shorter section is described in `short` where
    the part attacks in it and listed in `absent` where it does not: no comparison reads it, but a part does not keep one
    rhythm through a stretch whose short section it rests in or plays otherwise (review.unchanging; a two-bar
    turnaround and a two-bar rest went unseen: Astra's review b011c).  `kinds` is in every row, empty where the part
    plays no chords there.  A description: one rhythm and one chord throughout is no fault in itself."""
    clock = clock or Clock(p)
    bpb = clock.beats_per_bar
    sections = spans(p, clock)
    out = []
    for t in p['tracks']:
        if t.get('role') == 'melody' or not t['notes'] or unpitched(t):
            continue
        at = {}
        for n in t['notes']:
            at.setdefault(round(n['on'], 4), []).append((n['pitch'], n['duration']))
        bars, chords = {}, {}
        for on, played in at.items():
            b = int(on // bpb + 1e-9)
            bars.setdefault(b, set()).add(tick(on - b * bpb))
            pitches = [q for q, _ in played]
            if len(pitches) >= 2:
                low = min(pitches)
                chords[on] = tuple(sorted({q - low for q in pitches}))

        def described(bar_ids, onsets, out_of=None):
            rhythms = Counter(frozenset(bars[b]) for b in bar_ids)
            shapes = Counter(chords[o] for o in onsets if o in chords)
            row = {'bars': len(bar_ids), 'rhythms': len(rhythms)}
            if rhythms:
                top, n = max(rhythms.items(), key=lambda kv: (kv[1], sorted(kv[0])))
                row.update(rhythm=_beats(top), rhythm_share=round(n / (out_of or len(bar_ids)), 3))
            row.update(attacks=len(onsets), chords=sum(shapes.values()), shapes=len(shapes))
            if shapes:
                top, n = max(shapes.items(), key=lambda kv: (kv[1], kv[0]))
                row.update(shape='-'.join(map(str, top)), shape_share=round(n / sum(shapes.values()), 3))
                kinds = Counter(chord_kind(x) for x in shapes.elements())
                top, n = max(kinds.items(), key=lambda kv: (kv[1], kv[0]))
                row.update(kind=top, kind_share=round(n / sum(kinds.values()), 3), kinds=dict(kinds))
            else:
                row['kinds'] = {}   # a section of single notes has its count too, as the piece has (Astra's review b011c)
            notes = [x for o in onsets for x in at[o]]
            row.update(register=_median(q for q, _ in notes), length=_median(d for _, d in notes))
            return row
        row = {'part': t['id'], 'role': t.get('role'), **described(sorted(bars), list(at)), 'sections': [], 'short': [],
               'absent': []}
        for name, lo, hi, n in sections:
            first, last = int(lo // bpb + 1e-9), int((hi - EPS) // bpb)
            inside = [b for b in sorted(bars) if first <= b <= last]
            if n < min_bars:
                if inside:
                    row['short'].append({'section': name, 'section_bars': n,
                                         **described(inside, [o for o in at if lo - EPS <= o < hi - EPS], out_of=n)})
                else:
                    row['absent'].append(name)
                continue
            if len(inside) >= presence * n:
                row['sections'].append({'section': name, 'section_bars': n,
                                        **described(inside, [o for o in at if lo - EPS <= o < hi - EPS], out_of=n)})
            else:
                row['absent'].append(name)
        out.append(row)
    return out


def treatment(p):
    """Each part's processing (0.11, the second part): the catalog's tools its mix and kit use and their kinds
    (effectscatalog.part_tools), beside what the map of the style governing the mix documents for its role (style-maps.json
    `treatments`: each entry's kind, how usual its source says it is, its context and source, `none` where the source says
    the role takes little or none of it, and whether the part has a tool of that kind).  A Surge XT part's preset may carry
    effects of its own (`preset_effects`), which are not read.  A description: what a style documents is no rule for every
    part (an entry may concern one instrument of the role, as an electric piano's tremolo does), and nothing here asks."""
    from . import effectscatalog, styles
    try:
        entry = styles.governing(styles.parse(p.get('style')), 'mix')
    except ValueError:
        entry = None   # (validation refuses a style that is not an entry; a view never stops a review)
    rows = []
    for t in p['tracks']:
        ids = effectscatalog.part_tools(t)
        kinds = effectscatalog.kinds_of(ids)
        documented = effectscatalog.treatments(entry, t.get('role'))[0] if entry and t.get('role') else []
        rows.append({'part': t['id'], 'role': t.get('role'), 'tools': ids, 'kinds': kinds,
                     'character_tools': sum(1 for i in ids if effectscatalog.tools()[i]['kinds'][0] in effectscatalog.CHARACTER),
                     **({'preset_effects': True} if t.get('engine') == 'surge' else {}),
                     'documented': [{'kind': d['kind'], 'how': d['how'], 'context': d.get('context'), 'source': d['source'],
                                     **({'none': True} if d.get('none') else {}), 'has': d['kind'] in kinds} for d in documented]})
    return {'style': entry, 'parts': rows}


def views(p):
    """The five views of a project."""
    clock = Clock(p)
    rows = parts_by_section(p, clock)
    return {'parts_by_section': rows, 'part_sets': len(set(part_sets(rows))),
            'harmony_pace': harmony_pace(p, clock), 'melody_rhythm': melody_rhythm(p, clock),
            'accompaniment': accompaniment(p, clock), 'treatment': treatment(p)}


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
    # A role is the project's own text: escaped before the table is composed, so that it adds no line (0.8 step 1.6)
    parts = {n: one_line(str(r)) for n, r in parts.items()}
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
                     f'Kinds of chord: {kinds}.' + (f' Not read: {", ".join(one_line(u) for u in h["unknown"])}.' if h['unknown'] else ''))
    acc = [a for a in v.get('accompaniment') or () if a.get('role') in ('rhythm', 'harmony')]
    if acc:
        lines.append("Rhythm and harmony parts (a bar rhythm is the set of its attack positions; a chord's shape its semitones "
                     'above its lowest note; every pitched part in score_review.json, views.accompaniment):')
    for a in acc:
        chords = (f'; {a["chords"]} chords, {a["shapes"]} shape{"s" if a["shapes"] != 1 else ""}, the commonest {a["shape"]} in '
                  f'{a["shape_share"]:.0%} of them ({", ".join(f"{k} {n}" for k, n in sorted(a["kinds"].items(), key=lambda kv: -kv[1]))})'
                  if a.get('chords') else '; no chords')
        by = '; '.join(f'{s["section"]} {s["rhythms"]} rhythm{"s" if s["rhythms"] != 1 else ""}'
                       + (f', {s["shapes"]} shape{"s" if s["shapes"] != 1 else ""}' if s.get('chords') else '') for s in a['sections'])
        lines.append(f'  {one_line(a["part"])} ({one_line(str(a["role"]))}): {a["bars"]} bars, {a["rhythms"]} bar rhythm{"s" if a["rhythms"] != 1 else ""}, '
                     f'the commonest ({a["rhythm"]}) in {a["rhythm_share"]:.0%} of them{chords}' + (f'. By section: {by}' if by else '') + '.')
    for m in v['melody_rhythm']:
        run = m['longest_run']
        rests = ', '.join(f'{s["section"]} {s["rests"]}' for s in m['sections'] if s['attacks'])
        lines.append(f'Melody ({m["part"]}): of {m["attacks"]} attacks {m["syncopated_pct"]:g}% are syncopated (the next stronger '
                     f'position of the bar passes before the next attack) and {m["pushes_pct"]:g}% push a downbeat or half-bar. '
                     f'Longest stretch without a rest of half a beat: {run["seconds"]:g} s, bars {run["from_bar"]}-{run["to_bar"]}. '
                     f'Rests by section: {rests}. {m["bar_rhythms"]} different bar rhythms.')
    lines += treatment_lines(v.get('treatment'))
    return '\n'.join(lines)


def treatment_lines(t):
    """The treatment view as short lines: each part's tools by kind, and what its style's map documents for its role."""
    if not t or not t['parts']:
        return []
    style = one_line(str(t['style'])) if t['style'] else None
    lines = ["Processing by part (the processing catalog's tools, and their kinds):"]
    for r in t['parts']:
        used = ', '.join(i.split('.', 1)[1] for i in r['tools']) or 'nothing beyond its level and pan'
        lines.append(f'  {one_line(r["part"])} ({one_line(str(r["role"]))}): {used}' + (f' [{", ".join(r["kinds"])}]' if r['kinds'] else '')
                     + (" and its Surge preset's own effects" if r.get('preset_effects') else '') + '.')
    # what the style's map documents, once for each role the piece has: an entry may concern one instrument of the role
    # (its context says which), so it is set beside the parts, not on each of them
    said, roles = {}, []
    for r in t['parts']:
        if r['documented'] and r['role'] not in said:
            roles.append(r['role'])
            said[r['role']] = '; '.join(f'{"little or no " if d.get("none") else ""}{d["kind"]}: {one_line(str(d.get("context") or ""))} ({d["how"]}, {d["source"]})'
                                        for d in r['documented'])
    if said:
        lines.append(f'What the map of {style} documents, by role (a kind, on what, how usual its source says it is; studio.py effects '
                     f'--role ROLE --style {style} lists the tools, these first):')
        lines += [f'  {one_line(str(role))}: {said[role]}.' for role in roles]
    heavy = [r['part'] for r in t['parts'] if r['character_tools'] >= 3]
    if heavy:
        lines.append(f'Parts with three tools or more that change their character (colour, modulation, lo-fi, noise, sound design): '
                     f'{", ".join(one_line(x) for x in heavy)}. Each such tool on a part is heard against the others; check that '
                     'each still earns its place.')
    return lines
