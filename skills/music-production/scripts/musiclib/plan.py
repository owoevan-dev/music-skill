"""The plan of a piece, as data in the project, read against the score written from it.

A plan (schema.md) says, before the notes: what identifies the piece, where its high point is and by what means, and
for each section the commitments that can be read off a score: which parts sound, which part leads and which answer
it, a part's register against where it last played, the harmony's pace and the dynamics against the section before.
`compare` reads each commitment in the score and names the difference (research/design-0.7.md, 5.1).

It compares what the plan states and nothing else.  A plan that says nothing of a section is not held to anything
there; a high point is not more notes or more parts by definition, so its means are shown and not judged; and what
differs is put as a question, since the score or the plan may be the one to change.  The margins are this project's
own and are named with every difference they decide."""
import statistics

from . import views
from .model import PLAN_WORDS as WORDS, Clock

REGISTER_STEP = 2   # semitones the middle pitch of a part must move for `higher` or `lower` (ours)
VELOCITY_STEP = 3   # mean performed velocity a section must move for `louder` or `softer` (the margin of sections_alike)
PACE_STEP = 0.05    # chord changes a bar a section must move for `faster` or `slower` (ours)
EPS = 1e-6

def _moved(word, difference, step, up, down):
    """Whether a difference meets the plan's word: `up` when it rose by the step, `down` when it fell by it, `same`
    when it did neither."""
    if word == up:
        return difference >= step - EPS
    if word == down:
        return difference <= -step + EPS
    return abs(difference) < step - EPS


def _middle(track, lo, hi):
    """The median pitch of the notes a part begins between two beats, or None."""
    pitches = [n['pitch'] for n in track['notes'] if lo - EPS <= n['on'] < hi - EPS]
    return statistics.median(pitches) if pitches else None


def _velocity(p, lo, hi):
    """The mean performed velocity of every note begun between two beats, or None."""
    out = []
    for t in p['tracks']:
        played = (t.get('performance') or {}).get('notes') or {}
        out += [played[n['id']]['velocity'] for n in t['notes']
                if lo - EPS <= n['on'] < hi - EPS and n.get('id') in played and 'velocity' in played[n['id']]]
    return sum(out) / len(out) if out else None


def compare(p, clock=None):
    """The plan read against the score, or None for a project without one:

    {'identity', 'high_point': {'section', 'means', 'in_piece'} or None, 'commitments', 'kept', 'differences',
     'sections': [{'section', 'in_piece', 'what_differs', 'kept': [...], 'differs': [...], 'unread': [...]}]}

    A commitment is one statement that can be read: the set of parts that sound, the part that leads, each part that
    answers, each part's register, the harmony's pace, the dynamics.  `kept` names those the score holds; `differs`
    lists the others as {'what', 'planned', 'found', 'text'}; `unread` those that cannot be read, with the reason (a
    first section has no section before it; a project without `harmony` has no pace).  `what_differs` is the plan's
    own sentence on the section, carried along and not compared."""
    plan = p.get('plan')
    if not isinstance(plan, dict):
        return None
    clock = clock or Clock(p)
    spans = views.spans(p, clock)
    order = [s[0] for s in spans]
    span = {s[0]: s for s in spans}
    rows = {r['section']: r['parts'] for r in views.parts_by_section(p, clock)}
    pace = views.harmony_pace(p, clock)
    # As counted: rounded to two places, 1/3 and 3/8 of a change a bar stood 0.05 apart, the step that counts as
    # faster, where they are 0.042 apart (the review of 0.7's code, F11).
    pace_of = {s['section']: s['changes'] / max(s['bars'], 1) for s in pace['sections']} if pace else None
    tracks = {t['id']: t for t in p['tracks']}
    out = {'identity': plan.get('identity'), 'high_point': None, 'sections': [], 'commitments': 0, 'kept': 0, 'differences': 0}
    outside = plan.get('outside_passage')
    if isinstance(outside, dict):          # a passage cut from a piece (excerpt.py): what its plan leaves to the piece
        out['outside_passage'] = outside
    hp = plan.get('high_point')
    if isinstance(hp, dict):
        out['high_point'] = {'section': hp.get('section'), 'means': hp.get('means'), 'in_piece': hp.get('section') in span}
    for entry in plan.get('sections') or []:
        name = entry.get('section')
        row = {'section': name, 'in_piece': name in span, 'what_differs': entry.get('differs'), 'kept': [], 'differs': [], 'unread': []}
        out['sections'].append(row)
        if name not in span:
            continue
        _, lo, hi, _ = span[name]
        before = order[order.index(name) - 1] if order.index(name) else None
        sounding = rows.get(name, {})

        def settle(what, met, planned, found, text):
            out['commitments'] += 1
            if met:
                row['kept'].append(what)
                out['kept'] += 1
            else:
                row['differs'].append({'what': what, 'planned': planned, 'found': found, 'text': text})
                out['differences'] += 1

        def absent(part):
            return f'{part} is not a part of the project' if part not in tracks else None

        if 'sounds' in entry:
            planned, found = list(entry['sounds']), sorted(sounding)
            silent = [x for x in planned if x not in sounding]
            extra = [x for x in found if x not in planned]
            said = []
            if silent:
                said.append('planned to sound and silent: ' + ', '.join(x + (' (not a part of the project)' if x not in tracks else '') for x in silent))
            if extra:
                said.append('sounding and not in the plan: ' + ', '.join(extra))
            settle('sounds', not silent and not extra, planned, found, '; '.join(said))
        for what, parts in (('leads', [entry['leads']] if 'leads' in entry else []), ('answers', list(entry.get('answers') or []))):
            for part in parts:
                attacks = sounding.get(part, {}).get('attacks', 0)
                verb = 'lead' if what == 'leads' else 'answer'
                why = absent(part) or (f'{part} only holds notes begun earlier' if part in sounding else f'{part} is silent')
                settle(f'{what} {part}', attacks > 0, part, attacks, f'{part} is planned to {verb} and has no attack in the section ({why})')
        for part, word in (entry.get('register') or {}).items():
            what = f'register {part} {word}'
            if absent(part):
                settle(what, False, word, None, absent(part))
                continue
            here = _middle(tracks[part], lo, hi)
            earlier = None
            for other in reversed(order[:order.index(name)]):
                earlier = _middle(tracks[part], span[other][1], span[other][2])
                if earlier is not None:
                    last = other
                    break
            if here is None:
                settle(what, False, word, None, f'{part} has no attack in the section, so it has no register there')
            elif earlier is None:
                row['unread'].append({'what': what, 'why': f'{part} plays in no section before this one'})
            else:
                moved = here - earlier
                settle(what, _moved(word, moved, REGISTER_STEP, 'higher', 'lower'), word, round(moved, 1),
                       f'{part} is planned {word} than in {last}; its middle pitch is {earlier:g} there and {here:g} here '
                       f'(a move of {REGISTER_STEP} semitones counts)')
        if 'harmony' in entry:
            word, what = entry['harmony'], f'harmony {entry["harmony"]}'
            if pace_of is None:
                row['unread'].append({'what': what, 'why': 'the project writes no harmony'})
            elif before is None:
                row['unread'].append({'what': what, 'why': 'the first section has none before it'})
            else:
                moved = pace_of[name] - pace_of[before]
                settle(what, _moved(word, moved, PACE_STEP, 'faster', 'slower'), word, round(moved, 2),
                       f'the harmony is planned {word} than in {before}; the chord changes {round(pace_of[before], 2):g} times a bar there '
                       f'and {round(pace_of[name], 2):g} here')
        if 'dynamics' in entry:
            word, what = entry['dynamics'], f'dynamics {entry["dynamics"]}'
            if before is None:
                row['unread'].append({'what': what, 'why': 'the first section has none before it'})
            else:
                here, earlier = _velocity(p, lo, hi), _velocity(p, span[before][1], span[before][2])
                if here is None or earlier is None:
                    row['unread'].append({'what': what, 'why': 'a section without notes has no written dynamics'})
                else:
                    moved = here - earlier
                    settle(what, _moved(word, moved, VELOCITY_STEP, 'louder', 'softer'), word, round(moved, 1),
                           f'the section is planned {word} than {before}; the mean velocity written is {earlier:.0f} there and '
                           f'{here:.0f} here (a move of {VELOCITY_STEP} counts; levels and automation of the mix are not read)')
    return out


def questions(compared):
    """The questions a comparison raises, as (identifier, text): one for a project without a plan, one for a high
    point without its means or outside the piece, one for each section where plan and score differ."""
    from .review import identifier
    if compared is None:
        return [('plan.missing',
                 'The project has no plan. A plan says, before the notes, what identifies the piece, where its high point is and '
                 'by what means, and for each section which parts sound, which leads and what differs from the section before '
                 '(schema.md, plan); review then reads the score against it. Write one, or say in decisions why this piece '
                 'needs none.')]
    out = []
    hp = compared['high_point']
    if hp is None and isinstance((compared.get('outside_passage') or {}).get('high_point'), dict):
        pass                                   # the piece's high point lies in bars the passage leaves out: nothing to ask of the passage
    elif hp is None or not hp.get('section'):
        out.append(('plan.high_point', 'The plan names no high point. Say where it is and by what means it is one, or say in '
                                       'decisions that the piece has none (a loop that holds one level has none to name).'))
    elif not hp['in_piece']:
        out.append(('plan.high_point', f'The plan puts the high point in {hp["section"]}, which is not a section of the piece.'))
    elif not hp.get('means'):
        out.append(('plan.high_point',
                    f'The plan names {hp["section"]} as the high point and not by what means it is one. More parts or more notes '
                    'are one means among several (register, harmony, rhythm, dynamics, a part held back until then, a texture '
                    'that thins while the line climbs); say which this piece uses, so that the score can be read against it.'))
    for s in compared['sections']:
        if not s['in_piece']:
            out.append((identifier('plan', s['section']), f'The plan has a section {s["section"]}, which the piece does not have.'))
        elif s['differs']:
            out.append((identifier('plan', s['section']),
                        f'Plan and score differ in {s["section"]}: ' + '; '.join(d['text'] for d in s['differs'])
                        + '. Change the score, or change the plan and say why in decisions (the plan as first written stays in '
                          'the rounds\' records).'))
    return out


def describe(compared):
    """One line for the head of a review's summary: how much of the plan the score holds."""
    if compared is None:
        return ''
    n, kept = compared['commitments'], compared['kept']
    unread = sum(len(s['unread']) for s in compared['sections'])
    hp = compared['high_point']
    line = (f'Plan: the score holds {kept} of the {n} commitment{"s" if n != 1 else ""} the plan states'
            if n else 'Plan: it states no commitment that can be read off the score')
    if unread:
        line += f'; {unread} cannot be read'
    if hp and hp.get('section') and hp.get('means'):
        line += f'. High point: {hp["section"]}, by {hp["means"]} (shown, not judged)'
    return line + '.'


def changed(first, now):
    """What a plan no longer says as it first did: [{'where', 'first', 'now'}], comparing the identity, the high point
    and each section's commitments.  A plan changed after the score, to fit it, is not a plan carried out, so the
    first plan is kept by the rounds and the change is shown."""
    if not isinstance(first, dict) or not isinstance(now, dict):
        return []
    out = []
    for key in ('identity', 'high_point'):
        if first.get(key) != now.get(key):
            out.append({'where': key, 'first': first.get(key), 'now': now.get(key)})
    was = {s.get('section'): s for s in first.get('sections') or [] if isinstance(s, dict)}
    for s in now.get('sections') or []:
        old = was.pop(s.get('section'), None)
        if old != s:
            out.append({'where': f'section {s.get("section")}', 'first': old, 'now': s})
    out += [{'where': f'section {name}', 'first': old, 'now': None} for name, old in was.items()]
    return out
