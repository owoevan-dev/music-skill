"""Surge XT Effects on a part (`mix.surge_fx`, 0.11): the table of the types offered, the checks of a part's chain, what its
processed stem depends on, and the run of the GPL host (scripts/surgefx_host.py) that applies it.

The types, their parameters, units, limits and defaults are references/surge-fx.json, read off Surge XT Effects 1.3.4 with
pedalboard (research/effects-0.11/surgefx-params.md).  Every parameter is set on each render, the project's value or the
table's default, so that nothing depends on the plugin's state before it.  The Airwindows type holds Airwindows' algorithms
(`algorithm`, by its Airwindows name), each knob set by its position (two of an algorithm's knobs can share a Python name in
pedalboard's dictionary).  A setting that renders otherwise each time the part is processed anew (the table's `varies_when`:
Tape's degrade, the spring reverb's chaos and knock, the noise waveforms, the combulator's noise) is offered and said in the
stem's receipt (`varies`).  A chain that does not render the same to the sample each time it runs (the table's `repeat`:
`varies`, or `rounding` where Tape's start differs below -120 dBFS) runs once for the part's audio into it: its output is
kept in the part's cache entry, where the headphone version and later renders take it again until that audio or the chain
changes (Astra's review d011b), so that a varying part is one take.  Every chain processes 4 s of silence before the part, so that what the plugin smooths or settles has settled (Tape's start differs
per process until it has: research/effects-0.11/surgefx-params.md), part one's thirteen types 4 blocks, as before, so
that their modulation stands where it did at the first note.  The host's report is checked against the chain asked (the type,
the algorithm, every control and the value it shows): a report that does otherwise is a failed run, never a receipt.  A chain
runs after the part's noise gate, EQ,
effects and compressor, before its width and static pan (render.process_stem); after it the host removes any DC offset
(a first-order high-pass at 5 Hz), and the part is brought back to the level it entered the chain at, so that the chain
itself leaves the part's level as it found it (the receipt says by how much the chain had changed it).  Where Surge XT Effects is not installed
or its files do not match their hashes, the part plays without its chain, and the stem's receipt, the render's report and its
printed summary say so; this is apart from a Surge instrument part's own fallback preset.  Nothing here runs GPL code: the
host is a separate program that exchanges files.
"""
import json
import os
import sys
from pathlib import Path

TABLE_FILE = Path(__file__).resolve().parents[2] / 'references' / 'surge-fx.json'
HOST = Path(__file__).resolve().parents[1] / 'surgefx_host.py'
MAX_CHAIN = 4
TAKE = 'surge_fx_take'   # a chain's kept output in the part's cache entry: TAKE.f32 (the host's samples) and TAKE.json
_table = None


class Unavailable(Exception):
    """Surge XT Effects cannot run here; the reason names files, not their paths."""


class Failed(Unavailable):
    """Surge XT Effects was found but its run failed: the part plays without its chain on this render, and the stem so made
    is not kept for the next one, which tries the chain again."""


def table():
    global _table
    if _table is None:
        _table = json.loads(TABLE_FILE.read_text(encoding='utf-8'))
    return _table


def validate(track, warnings=None):
    """`mix.surge_fx` of one part, or ValueError saying what to write instead."""
    from .model import number, unknown_fields
    tid, chain = track['id'], track['mix'].get('surge_fx')
    types = table()['types']
    if not isinstance(chain, list) or not chain:
        raise ValueError(f'{tid}: mix.surge_fx is a list of one to {MAX_CHAIN} effects, each {{"type": ..., "params": {{...}}}}')
    if len(chain) > MAX_CHAIN:
        raise ValueError(f'{tid}: {len(chain)} effects in mix.surge_fx; a part takes at most {MAX_CHAIN}, applied in the order listed')
    for k, fx in enumerate(chain):
        where = f'{tid}.mix.surge_fx[{k}]'
        if not isinstance(fx, dict) or fx.get('type') not in types:
            raise ValueError(f'{where}: type is one of {", ".join(sorted(types))} (references/surge-fx.json)')
        if warnings is not None:
            unknown_fields(fx, 'surge fx', where, warnings)
        spec, params = types[fx['type']], fx.get('params', {})
        if fx['type'] == 'airwindows':
            algorithms = spec['algorithms']
            if fx.get('algorithm') not in algorithms:
                raise ValueError(f'{where}: algorithm is the Airwindows name of one of the {len(algorithms)} algorithms in '
                                 'references/surge-fx.json (studio.py effects --describe airwindows lists them)')
            spec = algorithms[fx['algorithm']]
        elif 'algorithm' in fx:
            raise ValueError(f'{where}: only the airwindows type takes an algorithm')
        if not isinstance(params, dict):
            raise ValueError(f'{where}: params is an object of a parameter name and its value')
        for name, value in params.items():
            if name not in spec['params']:
                raise ValueError(f'{where}: {fx.get("algorithm") or fx["type"]} has no parameter {name!r}; it has {", ".join(spec["params"])}')
            p = spec['params'][name]
            if 'values' in p:
                if value not in p['values']:
                    raise ValueError(f'{where}: {name} is one of {", ".join(map(str, p["values"]))}')
            else:
                number(value, p['min'], p['max'], f'{where} {name} ({p["unit"]})')


def host_chain(track):
    """The host's chain for a part: each effect's type and the raw value selecting it, and every parameter of the type as
    the plugin names it, the project's value or the table's default, with its unit (or the value it shows); the table's
    fixed parameters added."""
    out = []
    for fx in track['mix']['surge_fx']:
        spec, given = table()['types'][fx['type']], fx.get('params', {})
        if fx['type'] == 'airwindows':
            # every knob by its position and the plugin's own label, which the host checks before it sets it
            alg = spec['algorithms'][fx['algorithm']]
            knobs = [{'index': p['index'], 'plugin': p['plugin'],
                      'want': given.get(name, p['default']) if 'values' in p else {'unit': p['unit'], 'value': float(given.get(name, p['default']))}}
                     for name, p in alg['params'].items()]
            out.append({'type': spec['surge'], 'type_raw': spec['raw'], 'algorithm': alg['surge_name'], 'algorithm_raw': alg['raw'],
                        'knobs': knobs, 'preroll_s': spec.get('preroll_s', 0)})
            continue
        params = {}
        for name, p in spec['params'].items():
            value = given.get(name, p['default'])
            params[p['plugin']] = value if 'values' in p else {'unit': p['unit'], 'value': float(value)}
        for plugin_name, fixed in spec.get('fixed', {}).items():
            params[plugin_name] = fixed
        out.append({'type': spec['surge'], 'type_raw': spec['raw'], 'params': params, **({'preroll_s': spec['preroll_s']} if spec.get('preroll_s') else {})})
    return out


def _shown_value(text, unit):
    """The number a text the plugin shows holds, in `unit`, or None (a name, or another unit)."""
    import re
    text = str(text).strip()
    m = re.match(r'^1\s*:\s*(-?\d+(?:\.\d+)?)$', text) or re.match(r'^(-?\d+(?:\.\d+)?)\s*:\s*1$', text)
    if m:
        return float(m.group(1)) if unit == 'ratio' else None
    m = re.match(r'^(-?\d+(?:\.\d+)?)\s*([^\d\s(][^(]*)?', text)
    if not m:
        return None
    shown = (m.group(2) or '').strip() or 'number'
    value = float(m.group(1))
    factor = {('s', 'ms'): 1000.0, ('ms', 's'): 0.001, ('kHz', 'Hz'): 1000.0, ('Hz', 'kHz'): 0.001}
    return value if shown == unit else value * factor[(shown, unit)] if (shown, unit) in factor else None


def check_report(track, report):
    """Raise Failed unless the host's report is the chain asked: each effect its type (and algorithm), every control the
    table names, each numeric value within its tolerance of the value asked and each named value the one asked.  A host that
    took another type, or read every control back as zero, fails here (Astra's review d011b)."""
    chain = track['mix']['surge_fx']
    if not isinstance(report, list) or len(report) != len(chain):
        raise Failed('Surge XT Effects reported another chain than the one asked')
    for k, (fx, got) in enumerate(zip(chain, report)):
        spec = table()['types'][fx['type']]
        want_type = spec['surge']
        params = spec['params'] if fx['type'] != 'airwindows' else spec['algorithms'][fx['algorithm']]['params']
        if not isinstance(got, dict) or got.get('type') != want_type or (
                fx['type'] == 'airwindows' and got.get('algorithm') != spec['algorithms'][fx['algorithm']]['surge_name']):
            raise Failed(f'Surge XT Effects ran another effect than {fx.get("algorithm") or fx["type"]} at place {k + 1} of the chain')
        shown = got.get('shown') or {}
        for name, p in params.items():
            key = str(p['index']) if fx['type'] == 'airwindows' else p['plugin']
            if key not in shown:
                raise Failed(f'Surge XT Effects did not report {name} of {fx.get("algorithm") or fx["type"]}')
            asked = fx.get('params', {}).get(name, p['default'])
            if 'values' in p:
                if str(shown[key]) != str(asked):
                    raise Failed(f'Surge XT Effects shows {name} of {fx.get("algorithm") or fx["type"]} as {shown[key]!r}, not {asked!r}')
                continue
            value = _shown_value(shown[key], p['unit'])
            span = p['max'] - p['min']
            step = span / max(p.get('steps', 1001) - 1, 1) + .006   # one step of the control, and the display's rounding
            target = float(asked)
            if isinstance(p.get('shown_by_mode'), dict):
                # a control the plugin shows centred in some modes and not in others, the setting the same (Nimbus's density
                # and texture): what the chain's mode shows for the setting asked; the table gives the control as the type's
                # default mode shows it, and for each mode whether it is shown centred (Astra's review b011d)
                mode = next((str(shown.get(q['plugin'])) for q in params.values()
                             if 'values' in q and str(shown.get(q['plugin'])) in p['shown_by_mode']), None)
                if mode is not None and p['shown_by_mode'][mode] != (p['min'] < 0):
                    target = (target + 100) / 2 if p['min'] < 0 else 2 * target - 100
            if value is None:
                ok = False
            elif p['min'] > 0 and target > 0 and p['unit'] in ('Hz', 'kHz', 'ms', 's', 'ips', 'μm', 'x', 'samples'):
                ok = abs(value / target - 1) <= .03 or abs(value - target) <= step   # a scale of ratios: within 3 %
            else:
                ok = abs(value - target) <= max(.02 * span, step)
            if not ok:
                raise Failed(f'Surge XT Effects shows {name} of {fx.get("algorithm") or fx["type"]} as {shown[key]!r}, not {asked} {p["unit"]}')


def varies(track):
    """The effects of a part's chain set to render otherwise each time the part is processed anew (the table's
    `varies_when`), each named with the controls that make it: e.g. 'tape (degrade_depth)'; and an effect whose runs agree
    only to rounding (Tape) with another effect after it, which can enlarge that difference ('tape (before another effect)':
    Tape then DustBunny came out 15 dB under the signal apart, Astra's review b011d)."""
    out = []
    chain = list(track['mix'].get('surge_fx') or ())
    for place, fx in enumerate(chain):
        spec = table()['types'][fx['type']]
        if fx['type'] == 'airwindows':
            spec, label = spec['algorithms'][fx['algorithm']], f"airwindows {fx['algorithm']}"
        else:
            label = fx['type']
        given, hits = fx.get('params', {}), []
        for rule in spec.get('varies_when', ()):
            value = given.get(rule['param'], spec['params'][rule['param']]['default'])
            if (('above' in rule and isinstance(value, (int, float)) and not isinstance(value, bool) and value > rule['above'])
                    or ('is' in rule and value == rule['is']) or ('in' in rule and value in rule['in'])):
                hits.append(rule['param'])
        if not hits and spec.get('repeat') == 'rounding' and place < len(chain) - 1:
            hits.append('before another effect')
        if hits:
            out.append(f"{label} ({', '.join(hits)})")
    return out


def locate(cfg):
    """The effects plugin to load and pedalboard, the plugin's binary checked by hash, or Unavailable with the reason.  The
    plugin loads from the path the configuration gives (the binary itself on Windows, the bundle on Linux and macOS), as
    Surge XT's own parts load (surge.locate)."""
    from .played import file_hash
    from .surge import board_intact
    fx, board = (cfg or {}).get('surge_fx'), (cfg or {}).get('pedalboard')
    if not fx:
        raise Unavailable('Surge XT Effects is not installed; bootstrap.py installs it with Surge XT')
    if not board:
        raise Unavailable('pedalboard is not installed; bootstrap.py installs it with Surge XT')
    plugin, binary, pylib = Path(fx['path']), Path(fx.get('binary', fx['path'])), Path(board['path'])
    same = lambda a, b: os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    if not (same(binary, plugin) or any(same(plugin, up) for up in binary.parents)):
        raise Unavailable(f'the Surge XT Effects binary checked ({binary.name}) is not the plugin that would load ({plugin.name}); run bootstrap.py again')
    if not binary.is_file() or file_hash(binary) != fx['sha256']:
        raise Unavailable(f'Surge XT Effects missing or changed: {binary.name}')
    if not (pylib / 'pedalboard').is_dir() or not board_intact(pylib, board.get('record_sha256')):
        raise Unavailable('pedalboard is not the package bootstrap.py installed; run bootstrap.py again')
    return plugin, pylib


def identity(track, cfg):
    """What a part's processed stem owes its chain (render.stem_identity): whether it is applied, or why not, and what it
    is applied with: the plugin's and pedalboard's identities, the host's and the table's hashes, the chain itself."""
    from .played import file_hash
    if not track['mix'].get('surge_fx'):
        return None
    try:
        locate(cfg)
        state, reason = 'applied', None
    except Unavailable as e:
        state, reason = 'bypassed', str(e)
    board = (cfg or {}).get('pedalboard') or {}
    return {'state': state, 'reason': reason, 'plugin': ((cfg or {}).get('surge_fx') or {}).get('sha256'),
            'pedalboard': board.get('record_sha256') or board.get('sha256'), 'host': file_hash(HOST),
            'table': file_hash(TABLE_FILE), 'chain': host_chain(track)}


def repeat(track):
    """How two runs of a part's chain on the same audio compare: 'varies' where an effect is set to vary (varies), else
    'rounding' where an effect's runs differ only below -120 dBFS (the table's repeat: Tape) and nothing follows it, else
    'exact'."""
    if varies(track):
        return 'varies'
    kinds = {table()['types'][fx['type']].get('repeat', 'exact') for fx in track['mix'].get('surge_fx') or ()}
    return 'rounding' if 'rounding' in kinds else 'exact'


def _take_key(x, track, cfg):
    """What a chain's output depends on: the part's audio into it, the chain as the host is given it, and the plugin's,
    pedalboard's, the host's and the table's identities."""
    import hashlib
    import numpy as np
    from .played import file_hash
    board = (cfg or {}).get('pedalboard') or {}
    ident = {'chain': host_chain(track), 'plugin': ((cfg or {}).get('surge_fx') or {}).get('sha256'),
             'pedalboard': board.get('record_sha256') or board.get('sha256'), 'host': file_hash(HOST), 'table': file_hash(TABLE_FILE)}
    h = hashlib.sha256(json.dumps(ident, sort_keys=True, ensure_ascii=False).encode('utf-8'))
    h.update(np.ascontiguousarray(x, dtype='<f4').tobytes())
    return h.hexdigest()


def _kept_take(folder, key, frames, track):
    """The host's output and report kept under `key` in the cache entry `folder`, or None: none kept, another key, samples
    that are not those its receipt hashed, or a report that is not the chain asked."""
    import hashlib
    import numpy as np
    from . import files
    sound, receipt = Path(folder) / f'{TAKE}.f32', Path(folder) / f'{TAKE}.json'
    if not (files.regular_file(sound) and files.regular_file(receipt)) or files.lstat(sound).st_size != frames * 8:
        return None
    try:
        got = files.read_json(receipt)   # bounded, never through a link
        if not isinstance(got, dict) or got.get('key') != key:
            return None
        data = sound.read_bytes()
        if hashlib.sha256(data).hexdigest() != got.get('sha256'):
            return None
        check_report(track, got.get('report'))
    except (OSError, ValueError, Failed):
        return None
    return np.frombuffer(data, dtype='<f4').reshape(-1, 2).copy(), got['report']


def take_is_kept(folder, key, frames, track):
    """Whether the take kept under `key` in the cache entry `folder` is one this chain's run would use again: a cached stem
    whose chain is not exact is used only beside it (render.make_stem)."""
    return _kept_take(folder, key, frames, track) is not None


def _keep_take(folder, key, y, shown, tid):
    """Keep the host's output and report under `key` in the cache entry `folder` (each written whole, the samples first):
    a failure costs only the reuse."""
    import hashlib
    import numpy as np
    from . import files
    data = np.asarray(y, dtype='<f4').tobytes()
    try:
        with files.staged(Path(folder) / f'{TAKE}.f32') as f:
            f.write(data)
        files.write_json(Path(folder) / f'{TAKE}.json', {'key': key, 'sha256': hashlib.sha256(data).hexdigest(), 'track': tid, 'report': shown})
    except OSError:
        pass


def apply(src, dst, track, cfg, stems, logs, keep=None):
    """Run the part's chain on the WAV `src` into the WAV `dst` (both 48 kHz stereo) through the host, its files in the
    folder `stems` and its log in `logs`.  Returns what the receipt keeps: each effect with the text the plugin showed for
    each parameter (an Airwindows algorithm's knobs by the table's names), by how much the chain changed the part's level
    before it was restored, how two runs of it compare (`repeat`: exact, rounding or varies), and the effects set to vary
    (`varies`) where any is.  Where the chain is not exact and `keep` names the part's cache entry, its output is kept there
    under the part's audio into it and the chain (_take_key) and taken again while both are the same (`take_reused`;
    `take_key`, which the render checks before it uses the part's stem from the cache again).
    Raises Unavailable when the plugin cannot run here (Failed when it was found and its run failed), ValueError when the
    chain leaves the part silent."""
    import numpy as np
    from . import audio, files
    plugin, pylib = locate(cfg)
    stems, tid = Path(stems), track['id']
    # A copy, so that nothing holds `src` open when the result takes its place (Windows refuses to replace a file still
    # mapped: the chorus's pass, which reads and writes the same file, drops its reading the same way).
    x = np.array(audio.read_wav(src)[0], dtype=np.float32)
    how = repeat(track)
    key = _take_key(x, track, cfg) if keep is not None and how != 'exact' else None
    if key is not None:
        found = _kept_take(keep, key, len(x), track)
        if found is not None:
            return {**_finish(x, *found, track, dst, how, reused=True), 'take_key': key}
    raw_in, raw_out = stems / f'.{tid}.surge_fx_in.f32', stems / f'.{tid}.surge_fx_out.f32'
    job, report = stems / f'.{tid}.surge_fx_job.json', stems / f'.{tid}.surge_fx_report.json'
    try:
        with files.staged(raw_in) as f:
            f.write(np.asarray(x, dtype='<f4').tobytes())
        with files.staged(job, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'plugin': str(plugin), 'pylib': str(pylib), 'input': str(raw_in), 'output': str(raw_out),
                                'report': str(report), 'rate': audio.RATE, 'chain': host_chain(track)}))
        try:
            audio.run([sys.executable, str(HOST), str(job)], logs, 'surge_fx_' + tid, timeout=1800, cwd=HOST.parent)
            y = np.fromfile(raw_out, dtype='<f4').reshape(-1, 2)
            shown = json.loads(Path(report).read_text(encoding='utf-8'))
        except (RuntimeError, OSError, ValueError) as e:
            raise Failed(f'Surge XT Effects failed ({files.one_line(str(e))[:160]}; see logs/surge_fx_{tid}.log)') from None
        if len(y) != len(x) or not np.isfinite(y).all() or len(shown) != len(track['mix']['surge_fx']):
            raise Failed('Surge XT Effects returned audio of another length, non-finite samples or another chain')
        check_report(track, shown)
    finally:
        for p in (raw_in, raw_out, job, report):
            try:
                p.unlink()
            except OSError:
                pass
    result = _finish(x, y, shown, track, dst, how, reused=None if key is None else False)
    if key is not None:
        # kept only now that the part is made: a chain that left it silent replaced the take a stem in the cache was made
        # from, and the headphone version then played another (Astra's review b011d)
        _keep_take(keep, key, y, shown, tid)
        result['take_key'] = key
    return result


def _finish(x, y, shown, track, dst, how, reused):
    """The host's output `y` for the part's audio `x` brought back to the level the part entered at and written to `dst`;
    returns what the receipt keeps (apply)."""
    import numpy as np
    from . import audio
    tid = track['id']
    mode, change = track['mix'].get('level_mode', 'active_rms'), None
    try:
        before = audio.level_of(x, mode)
    except ValueError:
        before = None   # what enters the chain is silent (a part let through quiet): there is no level to keep
    if before is not None:
        try:
            change = audio.level_of(y, mode) - before
        except ValueError:
            raise ValueError(f'{tid}: its mix.surge_fx chain leaves it silent: check the chain\'s settings (an output_mix of 0 %, '
                             'an output gain at its lowest, a pre-delay or delay longer than the piece)') from None
        y = y * np.float32(10 ** (-change / 20))
    audio.write_wav(dst, y)
    chain = []
    for fx, got in zip(track['mix']['surge_fx'], shown):
        spec = table()['types'][fx['type']]
        if fx['type'] == 'airwindows':
            alg = spec['algorithms'][fx['algorithm']]
            by_index = {str(p['index']): name for name, p in alg['params'].items()}
            chain.append({'type': 'airwindows', 'algorithm': fx['algorithm'],
                          'shown': {by_index[k]: v for k, v in got['shown'].items() if k in by_index}})
            continue
        named = {p['plugin']: name for name, p in spec['params'].items()}
        named.update({k: k for k in spec.get('fixed', {})})   # the controls held at one value, shown too
        chain.append({'type': fx['type'], 'shown': {named[k]: v for k, v in got['shown'].items() if k in named}})
    result = {'chain': chain, 'level_change_db': None if change is None else round(change, 2), 'repeat': how}
    if how == 'varies':
        result['varies'] = varies(track)
    if reused is not None:
        result['take_reused'] = reused
    return result
