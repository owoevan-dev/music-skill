"""Surge XT Effects on a part (`mix.surge_fx`, 0.11): the table of the types offered, the checks of a part's chain, what its
processed stem depends on, and the run of the GPL host (scripts/surgefx_host.py) that applies it.

The types, their parameters, units, limits and defaults are references/surge-fx.json, read off Surge XT Effects 1.3.4 with
pedalboard (research/effects-0.11/surgefx-params.md).  Every parameter is set on each render, the project's value or the
table's default, so that nothing depends on the plugin's state before it.  Tape, the random modulation waveforms and the
spring reverb's chaos and knock are left out: they did not render the same twice.  A chain runs after the part's noise gate, EQ,
effects and compressor, before its width and static pan (render.process_stem); after it the host removes any DC offset
(a first-order high-pass at 5 Hz), and the part is brought back to the level it entered the chain at, so that its
`level_dbfs` stays its level (the receipt says by how much the chain had changed it).  Where Surge XT Effects is not installed
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
        if not isinstance(params, dict):
            raise ValueError(f'{where}: params is an object of a parameter name and its value')
        for name, value in params.items():
            if name not in spec['params']:
                raise ValueError(f'{where}: {fx["type"]} has no parameter {name!r}; it has {", ".join(spec["params"])}')
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
        params = {}
        for name, p in spec['params'].items():
            value = given.get(name, p['default'])
            params[p['plugin']] = value if 'values' in p else {'unit': p['unit'], 'value': float(value)}
        for plugin_name, fixed in spec.get('fixed', {}).items():
            params[plugin_name] = fixed
        out.append({'type': spec['surge'], 'type_raw': spec['raw'], 'params': params})
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


def apply(src, dst, track, cfg, stems, logs):
    """Run the part's chain on the WAV `src` into the WAV `dst` (both 48 kHz stereo) through the host, its files in the
    folder `stems` and its log in `logs`.  Returns what the receipt keeps: each effect with the text the plugin showed for
    each parameter, and by how much the chain changed the part's level before it was restored.  Raises Unavailable when the
    plugin cannot run here (Failed when it was found and its run failed), ValueError when the chain leaves the part silent."""
    import numpy as np
    from . import audio, files
    plugin, pylib = locate(cfg)
    stems, tid = Path(stems), track['id']
    # A copy, so that nothing holds `src` open when the result takes its place (Windows refuses to replace a file still
    # mapped: the chorus's pass, which reads and writes the same file, drops its reading the same way).
    x = np.array(audio.read_wav(src)[0], dtype=np.float32)
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
    finally:
        for p in (raw_in, raw_out, job, report):
            try:
                p.unlink()
            except OSError:
                pass
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
        named = {p['plugin']: name for name, p in spec['params'].items()}
        named.update({k: k for k in spec.get('fixed', {})})   # the controls held at one value, shown too
        chain.append({'type': fx['type'], 'shown': {named[k]: v for k, v in got['shown'].items() if k in named}})
    return {'chain': chain, 'level_change_db': None if change is None else round(change, 2)}
