"""The piece's style on the style maps (references/style-maps.md, style-maps.json): one primary entry, and entries
borrowed for some axes, and the limits `review` takes for each of its checks, with where each limit comes from.

A project's `style` is a map entry ("family/sub-style") or {"primary": entry, "borrow": {axis: entry}}.  Each axis is
governed by the entry borrowed for it, otherwise by the primary one: a piece primarily of one style keeps that
style's form and harmony while it takes, say, its rhythm from another.  Averaging the styles would give neither.
Each of review's checks belongs to one axis, so the entry governing that axis supplies its limits; an entry gives no
limit of its own for a check, and the family it belongs to none either, the check keeps the default, marked 'ours'
where this project set the number itself rather than taking it from a source.
"""
import json
from functools import lru_cache
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[2] / 'references' / 'style-maps.json'


@lru_cache(maxsize=1)
def registry():
    """style-maps.json: the axes, review's checks with their default limits and origins, the families and entries."""
    return json.loads(REGISTRY.read_text(encoding='utf-8'))


def _entries(reg):
    names = sorted(reg['styles'])
    return ', '.join(names) if names else 'none yet'


def parse(style, reg=None):
    """{'primary': entry, 'borrow': {axis: entry}} from a project's `style`; None where the project has none."""
    if style is None:
        return None
    reg = reg or registry()
    if isinstance(style, str):
        style = {'primary': style}
    form = ('style is a style map entry ("family/sub-style") or {"primary": entry, "borrow": {axis: entry}} '
            '(references/style-maps.md)')
    if not isinstance(style, dict) or set(style) - {'primary', 'borrow'} or not isinstance(style.get('primary'), str):
        raise ValueError(form)
    borrow = style.get('borrow', {})
    if not isinstance(borrow, dict) or not all(isinstance(v, str) for v in borrow.values()):
        raise ValueError(form)
    for axis in borrow:
        if axis not in reg['axes']:
            raise ValueError(f'style.borrow: {axis!r} is not an axis; the axes are {", ".join(reg["axes"])}')
    for entry in [style['primary'], *borrow.values()]:
        if entry not in reg['styles']:
            raise ValueError(f'style: {entry!r} is not an entry of the style maps (entries: {_entries(reg)}; '
                             'references/style-maps.md)')
    return {'primary': style['primary'], 'borrow': dict(borrow)}


def governing(style, axis):
    """The entry that governs an axis: the one borrowed for it, otherwise the primary; None without a style."""
    if style is None or axis is None:
        return None
    return style['borrow'].get(axis, style['primary'])


def limits(project, reg=None):
    """Each check's limits for this project: {check: {'axis', 'params', 'ask', 'origin', 'source', 'set_by'}}, where
    `set_by` names the entry (or family) whose limit replaced the default, or is None."""
    reg = reg or registry()
    style = parse(project.get('style'), reg)
    out = {}
    for check, spec in reg['checks'].items():
        row = {'axis': spec.get('axis'), 'params': dict(spec.get('params', {})), 'ask': spec.get('ask', True),
               'origin': spec['origin'], 'source': spec.get('source'), 'set_by': None}
        entry = governing(style, spec.get('axis'))
        if entry is not None:
            family = reg['styles'][entry].get('family') or entry.split('/')[0]
            for owner, checks in ((entry, reg['styles'][entry].get('checks', {})),
                                  (family, reg['families'].get(family, {}).get('checks', {}))):
                over = checks.get(check)
                if over:
                    row['params'].update(over.get('params', {}))
                    if 'ask' in over:
                        row['ask'] = over['ask']
                    row.update(origin=over['origin'], source=over.get('source'), set_by=owner)
                    break
        out[check] = row
    return out


def summary(lims):
    """The limits as review records them, and how many are the project's own."""
    ours = sorted(c for c, r in lims.items() if r['origin'] == 'ours')
    return {'checks': lims, 'ours': ours}
