# SPDX-License-Identifier: GPL-3.0-or-later
"""Surge XT Effects host: runs one part's audio through a chain of Surge XT Effects with pedalboard.

Unlike the rest of the skill (MIT), this program is GPL-3.0-or-later, the licence of the two programs it loads, as
surge_host.py is.  The skill runs it as a separate program and exchanges only files with it: a job file and the part's
audio in (32-bit float, interleaved stereo, raw), the processed audio and a report out.  No GPL code runs in the skill's
own processes.

How a type is chosen.  Surge XT Effects runs one effect per instance; pedalboard reads a plugin's parameter names once,
when it loads it or when its state is set.  So for each effect an instance is loaded, its type set by raw value
(index / (count - 1): set by name, some types land on their neighbour), a few silent blocks processed (a plugin takes
parameter changes while it processes audio), and its state given to a fresh instance, which then names the type's own
parameters.

How a parameter is set.  The text the plugin shows is read at each of 1,001 raw values by setting the value and reading
it back (`live_ranges`, pedalboard's own slower way): the table pedalboard builds by asking the plugin for a value's text
formats some parameters as another type's (the chorus's, flanger's and phaser's depth in cents where the plugin shows
percent, the flanger's mix and the ensemble's width as 0-100 where they run from -100 to 100 %), and the plugin processes
by the text it shows (research/effects-0.11/surgefx-params.md).  Each parameter is set from those texts (`raw_for`): a
name or a stepped value at the middle of its steps, a continuous value on the straight line between the two steps whose
texts lie either side of it, read in the job's unit; the text then shown is read back into the report.  The job names
every parameter of the type (the skill fills in its table's defaults), so nothing depends on the instance's state before.
No parameter is tempo-synced (pedalboard gives a plugin no tempo), and every time is absolute.  After the chain, a
first-order high-pass at 5 Hz (pedalboard's own, -3 dB at 5 Hz, -0.12 dB at 30 Hz) removes the DC offset an asymmetric
shaper leaves.

Airwindows.  Surge XT Effects names an Airwindows algorithm's knobs, and shows them in the algorithm's own units, only on an
instance that is running when the algorithm is chosen; through pedalboard it does not apply the algorithm's defaults.  So an
Airwindows effect is chosen on a running instance (its type, then its algorithm, each by raw value with silent blocks
processed), and that instance processes the part.  Its knobs are taken by position from pedalboard's ordered list of the
plugin's parameters, not its dictionary, where two knobs whose labels differ only in punctuation share one Python name; each
knob's label is checked against the job's before it is set, and the job sets every knob (the skill's table gives Airwindows'
own defaults).

Before the part, an effect whose job asks for a pre-roll (`preroll_s`: the types 0.11's second part adds and Airwindows)
processes that much silence after its controls are set: Surge smooths a knob's change over time, and Tape's start differs per
process until it has processed about two seconds of audio (research/effects-0.11/surgefx-params.md); part one's types keep
4 blocks, so that their modulation stands where it did at the first note.

The licence text is in ../LICENSES/GPL-3.0-or-later.txt.

Usage: python surgefx_host.py <job.json>
"""
import json
import re
import sys
from pathlib import Path

CONVERT = {('s', 'ms'): 1000.0, ('ms', 's'): 0.001, ('kHz', 'Hz'): 1000.0, ('Hz', 'kHz'): 0.001}
NUM = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*([^\d\s(][^(]*)?(?:\(.*\))?\s*$')
RATIO = re.compile(r'^\s*1\s*:\s*(\d+(?:\.\d+)?)\s*$')
WARM_BLOCKS, BLOCK = 4, 512
WARM_SECONDS = 4.0
UNIT_NAMES = {'': 'number', ': 1': 'ratio'}   # a value shown without a unit, and Airwindows' ratios ("4.75 : 1"), as the table names them
STEPS = 1000
DC_HZ = 5.0


def reading(text, label, unit):
    """The value a text shows, in `unit`, or None where it shows another unit or a name."""
    text = str(text)
    m = RATIO.match(text)
    if m:
        return float(m.group(1)) if unit == 'ratio' else None
    m = NUM.match(text)
    if not m:
        return None
    shown = (m.group(2) or '').strip() or (label or '').strip()
    value = float(m.group(1))
    if shown == unit or UNIT_NAMES.get(shown) == unit:
        return value
    if (shown, unit) in CONVERT:
        return value * CONVERT[(shown, unit)]
    return None


def live_ranges(param, steps=STEPS):
    """{(first raw, first raw of the next text): text} for a parameter, each text read from the plugin after setting the
    raw value (the parameter is left at the value it had)."""
    keep, ranges, start, text = param.raw_value, {}, 0.0, None
    try:
        for x in range(steps + 1):
            raw = x / steps
            param.raw_value = raw
            shown = str(param.string_value)
            if text is None:
                text = shown
            elif shown != text:
                ranges[(start, raw)] = text
                text, start = shown, raw
        ranges[(start, 1.0)] = text
    finally:
        param.raw_value = keep
    return ranges


def raw_for(name, ranges, label, want):
    """The raw value for `want`: a name, at the middle of the range showing it; a number in a unit, at the range whose text
    is nearest.  A text that holds over several steps (a stepped parameter) is set at the middle of its range, off the
    edges where the plugin may round to the neighbour; one read at a single step (a continuous parameter) where it was
    read, or, where the value asked lies between it and its neighbour, on the straight line between the two, so that the
    plugin shows the value asked (0.6 Hz, not the 0.597 Hz read at the nearest step)."""
    one = 1.5 / STEPS
    items = sorted(ranges.items())
    if not isinstance(want, dict):
        for (start, end), text in items:
            if str(text) == str(want):
                return start if end - start <= one else (start + end) / 2
        raise ValueError(f'{name}: no value of the plugin reads as {want!r}')
    points = [(start, end, got) for (start, end), text in items for got in [reading(text, label, want['unit'])] if got is not None]
    if not points:
        raise ValueError(f'{name}: no value of the plugin reads in {want["unit"]}')
    value = want['value']
    k = min(range(len(points)), key=lambda i: abs(points[i][2] - value))
    start, end, got = points[k]
    if end - start > one:
        return (start + end) / 2
    for j in (k - 1, k + 1):
        if 0 <= j < len(points) and points[j][1] - points[j][0] <= one and (got - value) * (points[j][2] - value) < 0:
            return start + (value - got) * (points[j][0] - start) / (points[j][2] - got)
    return start


def warm(unit, rate, silence, seconds):
    """Silence through `unit` for `seconds` (at least WARM_BLOCKS blocks), so that what it smooths or settles has settled."""
    for _ in range(max(WARM_BLOCKS, int(seconds * rate / BLOCK))):
        unit.process(silence, rate, reset=False)


def knob_list(unit):
    """The plugin's parameters in their order, but its type, its Airwindows algorithm and its bypass: knob i of an
    Airwindows algorithm is the i-th."""
    return [c for c in unit._parameters if c.name not in ('Type FX', 'FX Type', 'Bypass')]


def airwindows(job, fx, rate, silence, x, pedalboard, np):
    """One Airwindows algorithm on the part: chosen on a running instance, every knob set by position, warmed, applied."""
    unit = pedalboard.load_plugin(job['plugin'])
    unit.parameters['fx_type'].raw_value = float(fx['type_raw'])
    for _ in range(WARM_BLOCKS):
        unit.process(silence, rate, reset=False)
    unit.parameters['type_fx'].raw_value = float(fx['algorithm_raw'])
    for _ in range(WARM_BLOCKS):
        unit.process(silence, rate, reset=False)
    got = str(unit.parameters['type_fx'].string_value)
    if got != fx['algorithm']:
        raise SystemExit(f'Surge XT Effects took the Airwindows algorithm {got!r} for {fx["algorithm"]!r}')
    listed = knob_list(unit)
    active = [c for c in listed if c.name.strip() not in ('-', '- -', '')]
    if len(active) != len(fx['knobs']):
        raise SystemExit(f'{fx["algorithm"]}: the plugin shows {len(active)} knobs, the job {len(fx["knobs"])}')
    chosen = []
    for knob in fx['knobs']:
        i = knob['index']
        if not 0 <= i < len(listed) or listed[i].name != knob['plugin']:
            found = listed[i].name if 0 <= i < len(listed) else None
            raise SystemExit(f'{fx["algorithm"]}: knob {i} is {found!r}, not {knob["plugin"]!r}')
        chosen.append((knob, listed[i], raw_for(knob['plugin'], live_ranges(listed[i]), listed[i].label, knob['want'])))
    for knob, c, raw in chosen:
        c.raw_value = raw
    warm(unit, rate, silence, float(fx.get('preroll_s', WARM_SECONDS)))
    shown = {str(knob['index']): str(c.string_value) for knob, c, _ in chosen}
    return unit.process(x.astype(np.float32), rate, reset=False), {'type': fx['type'], 'algorithm': fx['algorithm'], 'shown': shown}


def main(job_file):
    job = json.loads(Path(job_file).read_text(encoding='utf-8'))
    sys.path.insert(0, job['pylib'])
    import numpy as np
    import pedalboard
    rate = float(job['rate'])
    x = np.fromfile(job['input'], dtype='<f4').reshape(-1, 2).T.copy()
    silence = np.zeros((2, BLOCK), np.float32)
    report = []
    for fx in job['chain']:
        if fx['type'] == 'Airwindows':
            x, done = airwindows(job, fx, rate, silence, x, pedalboard, np)
            report.append(done)
            continue
        first = pedalboard.load_plugin(job['plugin'])
        first.parameters['fx_type'].raw_value = float(fx['type_raw'])
        for _ in range(WARM_BLOCKS):
            first.process(silence, rate, reset=False)
        unit = pedalboard.load_plugin(job['plugin'])
        unit.raw_state = first.raw_state
        if str(getattr(unit, 'fx_type')) != fx['type']:
            raise SystemExit(f'Surge XT Effects took {getattr(unit, "fx_type")!r} for {fx["type"]!r}')
        params = unit.parameters
        for name in fx['params']:
            if name not in params:
                raise SystemExit(f'{fx["type"]} has no parameter {name!r} (it has {", ".join(sorted(params))})')
        # every text table first, from the type's own state, then every value set
        chosen = {name: raw_for(name, live_ranges(params[name]), params[name].label, want) for name, want in fx['params'].items()}
        for name, raw in chosen.items():
            params[name].raw_value = raw
        warm(unit, rate, silence, float(fx.get('preroll_s', 0)))
        shown = {name: str(params[name].string_value) for name in fx['params']}
        x = unit.process(x.astype(np.float32), rate, reset=False)
        report.append({'type': fx['type'], 'shown': shown})
    x = pedalboard.HighpassFilter(cutoff_frequency_hz=DC_HZ).process(x.astype(np.float32), rate)
    x.T.astype('<f4').tofile(job['output'])
    Path(job['report']).write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
