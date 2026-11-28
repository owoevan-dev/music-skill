"""MIT. `studio.py effects` (0.11): the processing catalog (references/processing-catalog.json) searched for a part, a short
list to choose from rather than the whole table, and one tool described in full.

The catalog holds every tool a part's processing can use: the skill's own mix fields and effects, Surge XT Effects' types and
the 75 Airwindows algorithms inside it, each with its kinds (correction, dynamics, colour, modulation, space, delay, lo-fi,
noise, sound design, utility), words for its character, the roles it serves, where it goes in a project, what it needs, a
fragment to start from, what to watch, a tool of the skill's own to fall back on, its measures and its sources.

A search filters by fit first: the part's role, a kind, character words (each must be among the entry's words, its own or
those its measures give), and the style.  Where the style's map documents treatments for the role (`treatments` in
style-maps.json), the tools they name come first, then the tools of the kinds they name, each row saying which source; the
rest follow.  Among the tools that fit, the piece's seed picks, kind by kind, so that two pieces asking the same question see
different tools, the first rows too: every agent shown the same first few is the shared start that makes work alike (Doshi
and Hauser 2024, as `studio.py sounds` cites).  The last row is always `nothing`: leaving a part as it is, with the reason in
the project's `decisions`, is a choice like any other (processing.md).  Here and not in sounds.py or measure.py, which cached
syntheses depend on: nothing here touches a render.
"""
import difflib
import json
from functools import lru_cache
from pathlib import Path

CATALOG_FILE = Path(__file__).resolve().parents[2] / 'references' / 'processing-catalog.json'
# roles the catalog's entries do not list by name, read as the nearest that they do
ROLE_AS = {'countermelody': 'melody', 'accent': 'melody', 'effect': 'texture'}
LIMIT = 10
NOTHING = {'id': 'nothing', 'kinds': [], 'where': None, 'needs': None,
           'summary': "Leave the part as it is: the mix's level, pan and sends only.",
           'why': 'always offered: a part left dry is a choice; write why in decisions'}


@lru_cache(maxsize=1)
def catalog():
    return json.loads(CATALOG_FILE.read_text(encoding='utf-8'))


def tools():
    return {e['id']: e for e in catalog()['tools']}


def _unknown(flag, value, known, listed=True):
    """A word the catalog does not hold, refused with the nearest it does (and, where `listed`, all of them)."""
    near = difflib.get_close_matches(str(value).lower(), known, n=1)
    return ValueError(f'{flag} {value!r} is not a word of the processing catalog' + (f'; did you mean {near[0]!r}?' if near else '.')
                      + (f' It knows: {", ".join(known)}.' if listed else ''))


def words(e):
    """An entry's words for its character: its own and those its measures give, each phrase whole and word by word."""
    phrases = list(e.get('character', ())) + list(e.get('measured_words', ()))
    return set(phrases) | {w for p in phrases for w in p.split()}


def all_words():
    return sorted({w for e in catalog()['tools'] for w in words(e)})


def phrases():
    """The catalog's character phrases as entries hold them (an error lists these; a word inside one matches too)."""
    return sorted({p for e in catalog()['tools'] for p in list(e.get('character', ())) + list(e.get('measured_words', ()))})


def treatments(style, role):
    """What the style's map documents for a role: [{'kind', 'tools', 'how', 'context', 'source'}], the family's entries that
    hold for the style, and the entry or family read; [] where the map documents none (or no style is given)."""
    from . import styles
    if not style:
        return [], None
    reg = styles.registry()
    if style in reg['families']:
        family, entry = style, None
    elif style in reg['styles']:
        entry = style
        family = reg['styles'][style].get('family') or style.split('/', 1)[0]
    else:
        raise _unknown('--style', style, sorted(reg['families']) + sorted(reg['styles']))
    table = (reg['families'].get(family) or {}).get('treatments') or {}
    rows = (table.get(role) or table.get(ROLE_AS.get(role)) or []) if role else []   # the role's own, else the one it is read as
    found = []
    for t in rows:
        if entry is None or not t.get('styles') or entry in t['styles']:
            found.append(t)
    return found, entry or family


def _fits(e, role, kind, wanted):
    if role and role not in e['roles'] and ROLE_AS.get(role) not in e['roles']:
        return False
    if kind and kind not in e['kinds']:
        return False
    return all(w in words(e) for w in wanted)


def _row(e, why):
    return {'id': e['id'], 'kinds': e['kinds'], 'where': e['where'], 'needs': e.get('needs'), 'summary': e['summary'], 'why': why}


def search(role=None, style=None, character=(), kind=None, seed=None, limit=LIMIT, everything=False):
    """The tools for a part: {'count', 'rows', 'treatments', 'style', 'note'}.  Rows the style's map names come first (each
    row's `why` says from which source), then a spread over the kinds of the rest, the seed choosing within each kind; the
    last row `nothing`.  With `everything`, every tool that fits, by kind, and no spread."""
    import numpy as np
    cat = catalog()
    if role is not None and role not in cat['roles']:
        raise _unknown('--role', role, cat['roles'])
    if kind is not None and kind not in cat['kinds']:
        raise _unknown('--kind', kind, cat['kinds'])
    known = all_words()
    wanted = [w.strip().lower() for w in character if w.strip()]
    for w in wanted:
        if w not in known:
            near = difflib.get_close_matches(w, known, n=1)
            raise ValueError(f'--character {w!r} is not a word of the processing catalog' + (f'; did you mean {near[0]!r}?' if near else '.')
                             + f' Its phrases (a word inside one matches too): {", ".join(phrases())}.')
    if limit < 1:
        raise ValueError('--limit is at least 1')
    found, read = treatments(style, role)
    # a tool the style's map names for the role is kept though its own roles leave the role out (jazz's piano compressor
    # was left out: Astra's review b011d); the other filters hold for it
    named_ids = {i for t in found if not t.get('none') for i in t.get('tools', ())}
    fitting = [e for e in cat['tools'] if _fits(e, role, kind, wanted) or (e['id'] in named_ids and _fits(e, None, kind, wanted))]
    order = {k: i for i, k in enumerate(cat['kinds'])}
    fitting.sort(key=lambda e: (order[e['kinds'][0]], e['id']))
    rng = np.random.default_rng(seed) if seed is not None else None
    named, of_kind = {}, {}
    parts = lambda r: f'{"drum" if r == "drums" else r} parts'
    for t in found:
        if t.get('none'):
            continue   # a source that says the role takes little or none of a kind ranks nothing up: it is said on `nothing`
        said = f'{t["how"]}{", " + t["context"] if t.get("context") else ""}; {", ".join([t["source"]] + list(t.get("also", ())))}'
        for tid in t.get('tools', ()):
            named.setdefault(tid, f'the map of {read} documents it for {parts(role)} ({said})')
        of_kind.setdefault(t['kind'], f'the map of {read} documents {t["kind"]} for {parts(role)} ({said})')
    first = [e for e in fitting if e['id'] in named]
    second = [e for e in fitting if e['id'] not in named and e['kinds'][0] in of_kind]
    rest = [e for e in fitting if e['id'] not in named and e['kinds'][0] not in of_kind]

    def why(e):
        if e['id'] in named:
            return named[e['id']]
        if e['kinds'][0] in of_kind:
            return of_kind[e['kinds'][0]]
        bits = [f'{e["kinds"][0]}']
        if role:
            bits.append(f'for {parts(role)}' if role in e['roles'] else f'for {parts(ROLE_AS.get(role, role))}, as {role} is read')
        if wanted:
            bits.append(', '.join(wanted))
        return ', '.join(bits)

    if everything:
        rows = [_row(e, why(e)) for e in first + second + rest]
    else:
        rows = []
        for group in (first, second, rest):
            room = limit - len(rows)
            if room <= 0:
                break
            rows += [_row(e, why(e)) for e in spread(group, room, rng, kind)]
    unranked = ('' if found or not style else "; give --role to rank them by the style's map" if not role
                else f'; the map of {read} documents no treatment for {role} parts, so none is ranked by it')
    note = (f'{len(fitting)} of {len(cat["tools"])} tools fit' + (f'; {len(rows)} shown' if not everything else '') + unranked
            + ". --describe <id> gives one in full: its fragment, its controls (a Surge XT effect's; the skill's own tools "
              'name where schema.md gives their fields), fallback and sources.')
    nothing = dict(NOTHING)
    little = [t for t in found if t.get('none')]
    if little:
        nothing['why'] += (f'; the map of {read} documents little or none of ' + '; '.join(
            f'{t["kind"]} for {parts(role)} ({t["how"]}, {t["context"]}; {", ".join([t["source"]] + list(t.get("also", ())))})' for t in little))
    return {'count': len(fitting), 'rows': rows + [nothing], 'treatments': found, 'style': read, 'note': note}


FAMILIES = ('own', 'surge_fx', 'airwindows')


def family(e):
    """Whose tool it is: the skill's own (no plugin), a Surge XT Effects type, or an Airwindows algorithm."""
    return 'own' if not e.get('needs') else 'surge_fx' if e['id'].startswith('surge_fx.') else 'airwindows'


def spread(group, room, rng, kind=None):
    """`room` entries of `group`, taken kind by kind in turn (each tool by its first kind), so that every kind that fits is
    shown before any is shown twice; within a kind the families (the skill's own, Surge's types, Airwindows) take turns
    in turn, whatever their numbers (75 of the 115 tools are Airwindows algorithms), a family with nothing left passed over.
    The seed orders the kinds, the families' turn in each kind and the tool; without one, the kinds go in the catalog's
    order, the skill's own tools first, the middle tool of each list.  The picks are shown in a seeded order, so the first
    rows differ from piece to piece too."""
    if len(group) <= room:
        picks = list(group)
    else:
        kinds = []
        pools = {}
        for e in group:
            k = kind or e['kinds'][0]   # the kind asked, which every tool here has; else each tool's first
            if k not in pools:
                kinds.append(k)
                pools[k] = {f: [] for f in FAMILIES}
            pools[k][family(e)].append(e)
        if rng is not None:
            kinds = [kinds[i] for i in rng.permutation(len(kinds))]
        turns = {k: ([FAMILIES[i] for i in rng.permutation(len(FAMILIES))] if rng is not None else list(FAMILIES)) for k in kinds}
        picks, at = [], {k: 0 for k in kinds}
        while len(picks) < room:
            for k in kinds:
                if len(picks) >= room:
                    break
                for step in range(len(FAMILIES)):   # the next family in this kind's turn that has a tool left
                    f = turns[k][(at[k] + step) % len(FAMILIES)]
                    if pools[k][f]:
                        break
                else:
                    continue
                at[k] = (at[k] + step + 1) % len(FAMILIES)
                pool = pools[k][f]
                picks.append(pool.pop(int(rng.integers(len(pool))) if rng is not None else len(pool) // 2))
    if rng is not None:
        picks = [picks[i] for i in rng.permutation(len(picks))]
    return picks


def describe(tid):
    """One tool in full: the catalog's entry, its controls (a Surge XT effect's or algorithm's from references/surge-fx.json;
    null for the skill's own tools, whose `fields` names where schema.md gives them), and its sources cited.  `airwindows`
    alone lists the 75 algorithms by group."""
    from . import surgefx
    table = surgefx.table()['types']
    if tid == 'airwindows':
        groups = {}
        for e in catalog()['tools']:
            if e['id'].startswith('airwindows.'):
                groups.setdefault(e['group'], []).append({'id': e['id'], 'name': e['name'], 'kinds': e['kinds'], 'summary': e['summary']})
        return {'id': 'airwindows', 'algorithms': sum(len(v) for v in groups.values()), 'groups': groups,
                'note': 'Each is {"type": "airwindows", "algorithm": "<the part after airwindows.>", "params": {...}} in mix.surge_fx; '
                        '--describe airwindows.<Name> gives its controls.'}
    if tid == 'nothing':
        return {**NOTHING, 'why': 'a part left as it is: its level, pan and sends only; write why in decisions', 'sources': []}
    by_id = tools()
    if tid not in by_id and f'surge_fx.{tid}' in by_id:
        tid = f'surge_fx.{tid}'
    if tid not in by_id and f'airwindows.{tid}' in by_id:
        tid = f'airwindows.{tid}'
    if tid not in by_id:
        ends = [i for i in by_id if i.split('.', 1)[-1] == tid]   # a name only one tool has: compressor, auto_pan
        tid = ends[0] if len(ends) == 1 else tid
    if tid not in by_id:
        # the nearest by the whole id or by its name alone (ToTape6 for Tape6), the list itself left to --all
        short = {i.split('.', 1)[-1].lower(): i for i in by_id}
        near = difflib.get_close_matches(str(tid).lower(), list(short), n=3, cutoff=.5)
        raise ValueError(f'--describe {tid!r} is not a tool of the processing catalog'
                         + (f'; did you mean {", ".join(short[n] for n in near)}?' if near else '.')
                         + ' studio.py effects --all lists every tool, --describe airwindows the 75 algorithms.')
    e = dict(by_id[tid])
    if tid.startswith('surge_fx.'):
        spec = table[tid.split('.', 1)[1]]
        e['controls'] = _controls(spec['params'])
    elif tid.startswith('airwindows.'):
        spec = table['airwindows']['algorithms'][tid.split('.', 1)[1]]
        e['controls'] = _controls(spec['params'])
    else:   # every description has the key (Astra's review b011e: reading it as the guide says raised KeyError)
        e['controls'] = None
        e['fields'] = "references/schema.md (a track's " + ('kit' if tid.startswith('kit.') else 'mix') + ')'
    sources = catalog()['sources']
    e['sources'] = [{'key': k, **sources[k]} for k in e['sources']]
    return e


def part_tools(track):
    """The catalog's tools a part's processing uses, by id, read from its mix and its kit as written: a field present (the
    high- and low-pass where the project sets them, a send that is not null, a saturation above 0, an auto-pan where the
    part moves as a swing), each of its effects and its Surge XT Effects chain.  A Surge XT part's preset carries effects
    of its own, which are not read here (`preset_effects`)."""
    mix, out = track.get('mix') or {}, []
    for field in ('eq', 'compressor', 'noise_gate', 'amp', 'delay', 'duck', 'filter_sweep', 'gate'):
        if mix.get(field) is not None and mix.get(field) != []:
            out.append(f'mix.{field}')
    if isinstance(mix.get('wow_flutter'), dict):   # an object plays, {} included (production.wobbling)
        out.append('mix.wow_flutter')
    for field in ('highpass', 'lowpass'):
        if field in mix:
            out.append(f'mix.{field}')
    sat = mix.get('saturate')
    if sat is not None and (sat.get('drive', .5) > 0 if isinstance(sat, dict) else sat > 0):
        out.append('mix.saturate')
    if mix.get('reverb_db') is not None:
        out.append('mix.reverb_send')
    if mix.get('delay_db') is not None:
        out.append('mix.delay_send')
    if isinstance(mix.get('move'), dict) and mix['move'].get('type') == 'swing':
        out.append('mix.auto_pan')
    out += [f'effects.{e["type"]}' for e in mix.get('effects') or () if isinstance(e, dict) and e.get('type')]
    for fx in mix.get('surge_fx') or ():
        if isinstance(fx, dict) and fx.get('type') == 'airwindows':
            out.append(f'airwindows.{fx.get("algorithm")}')
        elif isinstance(fx, dict):
            out.append(f'surge_fx.{fx.get("type")}')
    if isinstance(track.get('kit'), dict) and track['kit'].get('gated_ms'):
        out.append('kit.gated_reverb')
    known = tools()
    return [i for i in out if i in known]


def kinds_of(ids):
    """The kinds the tools `ids` give, each tool every kind it has, in the catalog's order."""
    known, have = tools(), set()
    for i in ids:
        have.update(known[i]['kinds'])
    return [k for k in catalog()['kinds'] if k in have]


CHARACTER = ('colour', 'modulation', 'lo-fi', 'noise', 'sound design')   # the kinds that change a part's character


def _controls(params):
    out = {}
    for name, p in params.items():
        if 'values' in p:
            out[name] = {'values': p['values'], 'default': p['default']}
        else:
            out[name] = {'unit': p['unit'], 'min': p['min'], 'max': p['max'], 'default': p['default']}
    return out


def summary(found):
    """A search or a description as lines (the JSON, --json, holds the rest)."""
    if 'rows' not in found:
        return describe_lines(found)
    lines = [found['note']]
    for r in found['rows']:
        place = f' -> {r["where"]}' if r['where'] else ''
        needs = f' [needs {r["needs"]}]' if r['needs'] else ''
        lines.append(f'  {r["id"]} ({", ".join(r["kinds"]) or "dry"}){place}{needs}: {r["summary"]} Why: {r["why"]}.')
    return '\n'.join(lines)


def describe_lines(e):
    if e['id'] == 'nothing':
        return f'nothing: {e["summary"]} Why: {e["why"]}.'
    if e['id'] == 'airwindows':
        lines = [f'{e["algorithms"]} Airwindows algorithms in Surge XT Effects, by group:']
        for g, rows in e['groups'].items():
            lines.append(f'  {g}: ' + '; '.join(f'{r["id"].split(".", 1)[1]} ({", ".join(r["kinds"])})' for r in rows))
        lines.append(e['note'])
        return '\n'.join(lines)
    lines = [f'{e["id"]}' + (f' ({e["name"]})' if e.get('name') else '') + f': {e["summary"]}',
             f'Kinds: {", ".join(e["kinds"])}. Character: {", ".join(e["character"])}'
             + (f'; measured at its defaults: {", ".join(e["measured_words"])}' if e.get('measured_words') else '') + '.',
             f'Roles: {", ".join(e["roles"])}. Goes in {e["where"]}' + (f', needs {e["needs"]}' if e.get('needs') else '')
             + (f' (without it: {e["fallback"]})' if e.get('fallback') else '') + '.',
             'Start from: ' + json.dumps(e['fragment'], ensure_ascii=False)]
    if e.get('controls'):
        lines.append('Controls: ' + '; '.join(
            f'{n} {c["min"]:g} to {c["max"]:g} {c["unit"]} (default {c["default"]:g})' if 'unit' in c else f'{n} {"|".join(map(str, c["values"]))} (default {c["default"]})'
            for n, c in e['controls'].items()))
    if e.get('repeat') and e['repeat'] != 'exact' or e.get('varies_when'):
        lines.append('Renders: ' + ('the same each time to within -120 dBFS (float rounding)' if e['repeat'] == 'rounding' else 'the same samples each time')
                     + (f', and otherwise each time the part is processed anew where {" or ".join(e["varies_when"])} (the cache keeps one take)'
                        if e.get('varies_when') else '') + '.')
    if not e.get('needs'):
        lines.append("Its fields and their limits: references/schema.md (a track's mix" + (', kit' if e['id'].startswith('kit.') else '') + ').')
    if e.get('measured'):
        m = e['measured']
        lines.append(f'Measured at its defaults: level {m["level_db"]:+g} dB, brightness x{m["brightness_ratio"]:g}, width {m["width_db"]:g} dB, '
                     f'harmonics {m["harmonics_db"]:g} dB, other partials {m["inharmonic_db"]:g} dB, noise {m["noise_dbfs"]:g} dBFS, tail {m["tail_s"]:g} s '
                     '(the catalog\'s note says on what).')
    lines.append(f'Watch: {e["watch"]}')
    if e.get('prefer'):
        lines.append(f'Rather: {e["prefer"]}')
    lines.append('Sources: ' + '; '.join(s['cite'].rstrip('.') for s in e['sources']) + '.')
    return '\n'.join(lines)
