"""studio.py instruments: the configured banks' presets found by words of their name, their General MIDI family or
their bank, each with the keys its samples cover and its velocity ranges, both read from the bank itself, and what the
skill's preset list (references/soundbank-presets.md) gives for it (0.8 step 2.6: notes outside an instrument's range
were the 0.7 agents' most frequent failure, 7 of 43).  The bank and program it reports are what a part's `soundfont`
and `patch` take (schema.md), so a part need not guess them."""
import difflib
import functools
import os
import re
from pathlib import Path

from . import audio, files, sf2

# The General MIDI Level 1 sound set's families, eight programs each (MIDI Manufacturers Association, General MIDI
# System Level 1, 1991): the banks built here put each instrument at its General MIDI program (soundbank-presets.md).
FAMILIES = ('piano', 'chromatic percussion', 'organ', 'guitar', 'bass', 'strings', 'ensemble', 'brass', 'reed', 'pipe',
            'synth lead', 'synth pad', 'synth effects', 'ethnic', 'percussive', 'sound effects')
PRESET_LIST = Path(__file__).resolve().parents[2] / 'references' / 'soundbank-presets.md'
NAMES = ('C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B')
note = lambda k: f'{NAMES[k % 12]}{k // 12 - 1}'


def documented():
    """(bank, bank number, program) -> what the preset list's table gives: the preset's name, keys and velocity layers."""
    rows = {}
    for line in PRESET_LIST.read_text(encoding='utf-8').splitlines():
        m = re.match(r'\| `([a-z0-9_]+)` \| (\d+):(\d+) \| ([^|]+)\| ([^|]+)\| ([^|]+)\|', line)
        if m:
            rows[(m.group(1), int(m.group(2)), int(m.group(3)))] = {'name': m.group(4).strip(), 'keys': m.group(5).strip(),
                                                                    'velocity_layers': m.group(6).strip()}
    return rows


MAX_PAIRS = 1_000_000   # preset zone and instrument zone pairs looked at in one bank; the largest bank installed holds 9,400 zones in all (our count)


def pairs(bank, preset, spent=None):
    """The preset's zone pairs that sound: (preset zone, instrument zone, the instrument's global gens, keys,
    velocities), keys and velocities the ranges the two share.  A preset zone and an instrument zone sound together
    where their key ranges and their velocity ranges both overlap; each zone without its own range takes its global
    zone's, the first zone when it names no instrument or sample (SoundFont 2.04, 7.3 and 7.7).  instruments and
    review read a preset through this one walk (review's own read no global zone and no velocity: the third outside
    review; over the 679 presets installed the two gave the same keys and shifts).  At most MAX_PAIRS pairs are looked
    at for all the presets that share `spent` (one bank's: many presets on one large instrument each stayed under a
    bound a preset)."""
    glob = lambda zones: zones[0]['gens'] if zones and zones[0]['target'] is None else {}
    spent, ptop = spent if spent is not None else [0], glob(preset['zones'])
    for pz in preset['zones']:
        if pz['target'] is None:
            continue
        plo, phi = pz['gens'].get(43, ptop.get(43, (0, 127)))
        pvlo, pvhi = pz['gens'].get(44, ptop.get(44, (0, 127)))
        inst = bank['instruments'][pz['target']]
        top = glob(inst['zones'])
        spent[0] += len(inst['zones'])
        if spent[0] > MAX_PAIRS:
            raise ValueError(f'preset {files.one_line(preset["name"])}: over {MAX_PAIRS:,} zone pairs to look at in its bank, more than a real bank holds')
        for z in inst['zones']:
            if z['target'] is None:
                continue
            lo, hi = z['gens'].get(43, top.get(43, (0, 127)))
            vlo, vhi = z['gens'].get(44, top.get(44, (0, 127)))
            k, v = (max(lo, plo), min(hi, phi)), (max(vlo, pvlo), min(vhi, pvhi))
            if k[0] <= k[1] and v[0] <= v[1]:
                yield pz, z, top, k, v


def measured(bank, preset, spent=None):
    """The keys the preset's zones give a sample, and the velocity ranges they split at: the dynamic layers, and, in
    banks that alternate round robins by velocity (the ones built here), those too (pairs: the zones that sound)."""
    keys, ranges = set(), set()
    for _, _, _, k, v in pairs(bank, preset, spent):
        keys.update(range(k[0], k[1] + 1))
        ranges.add(v)
    return keys, sorted(ranges)


def key_ranges(keys):
    """Keys as runs, [[first, last], ...]: what a preset covers, and where it has no sample between."""
    out = []
    for k in sorted(keys):
        if out and k == out[-1][1] + 1:
            out[-1][1] = k
        else:
            out.append([k, k])
    return out


@functools.lru_cache(maxsize=64)
def _read(path, stamp):
    return sf2.read(path)


def read(path):
    """A bank's tables, read once a process while the file is unchanged (a script's parts look up one bank each)."""
    s = os.stat(path)
    return _read(os.path.abspath(path), (s.st_mtime_ns, s.st_size))


def banks(config_file):
    """The configured banks, name -> path: `default` and the named ones (soundfonts), their paths read as the
    configuration gives them (not hashed: nothing is played)."""
    config = files.read_json(os.path.abspath(config_file))
    if not isinstance(config, dict):
        raise ValueError(f'{config_file}: a configuration is a JSON object')
    config = audio.absolute_paths(config, Path(config_file).resolve().parent, config_file)
    out = {'default': config['soundfont']['path']} if isinstance(config.get('soundfont'), dict) else {}
    out.update({name: e['path'] for name, e in (config.get('soundfonts') or {}).items() if isinstance(e, dict) and 'path' in e})
    return out


def search(config_file, words, bank=None):
    """The presets every word matches (in the preset's name, its family or its bank's name, without regard to case),
    by bank, bank number and program, in every configured bank or in `bank` alone (then words may be none); a word
    that matches no preset is refused with the nearest one that would."""
    words = [w.lower() for w in words if w.strip()]
    if not words and bank is None:
        raise ValueError('instruments takes one or more words: a part of a preset\'s name (violin), a family (strings) or a bank (vsco)')
    configured = banks(config_file)
    if bank is not None and bank not in configured:
        raise ValueError(f'No configured bank is named {files.one_line(bank)!r}; the configuration names {", ".join(sorted(configured))}')
    listed, rows, vocabulary = documented(), [], set()
    for name, path in sorted(configured.items()):
        if bank is not None and name != bank:
            continue
        sounds, spent = read(path), [0]   # one bound for the bank's presets together (pairs)
        for p in sounds['presets']:
            family = 'drum kit' if p['bank'] >= 128 else FAMILIES[p['program'] // 8] if p['program'] < 128 else 'no General MIDI family'
            text = f'{p["name"]} {family} {name}'.lower()
            vocabulary.update(re.findall(r'[a-z0-9_]+', text))   # a bank's name whole (iowa_strings), as a word may give it
            if not all(w in text for w in words):
                continue
            keys, ranges = measured(sounds, p, spent)
            row = {'bank': name, 'patch': {'bank': p['bank'], 'program': p['program']}, 'preset': p['name'], 'family': family,
                   'keys': f'{note(min(keys))}-{note(max(keys))}' if keys else None, 'keys_midi': [min(keys), max(keys)] if keys else None,
                   'keys_without_a_sample': (max(keys) - min(keys) + 1 - len(keys)) if keys else None, 'key_ranges': key_ranges(keys),
                   'velocity_ranges': len(ranges)}
            if len(keys) >= 120:   # a General MIDI bank stretches its samples over the keyboard: the keys say nothing of the instrument
                row['every_key'] = 'the bank stretches its samples over all keys: take the instrument\'s range from orchestration.md'
            if (name, p['bank'], p['program']) in listed:
                row['preset_list'] = listed[(name, p['bank'], p['program'])]
            rows.append(row)
    if not rows:
        near = [w for w in words if not any(w in v for v in vocabulary)]
        hint = difflib.get_close_matches(near[0], sorted(vocabulary), n=1) if near else []
        raise ValueError(f'No configured preset matches {" ".join(words)!r}' + (f'; did you mean {hint[0]!r}?' if hint else '')
                         + ' Words match a preset\'s name, its family (' + ', '.join(FAMILIES) + ') or its bank.')
    rows.sort(key=lambda r: (r['bank'], r['patch']['bank'], r['patch']['program']))
    return {'count': len(rows), 'presets': rows,
            'note': ('A part plays one with "soundfont": <bank> and "patch": {"bank": ..., "program": ...} (schema.md). keys: the '
                     'notes its samples cover (MIDI 60 is C4), read from the bank; write inside them, and nearer the middle for an '
                     'even tone. velocity_ranges counts its dynamic layers, and in the banks built here its round robins too; '
                     'preset_list gives the recorded layers as references/soundbank-presets.md lists them.')}


def summary(found):
    """One line a preset."""
    lines = [f'{found["count"]} preset{"s" if found["count"] != 1 else ""}:']
    for r in found['presets'][:60]:
        listed = r.get('preset_list')
        lines.append(f'  {r["bank"]} {r["patch"]["bank"]}:{r["patch"]["program"]} {r["preset"]} ({r["family"]}): keys {r["keys"]}'
                     + (f', {r["keys_without_a_sample"]} without a sample' if r['keys_without_a_sample'] else '')
                     + (' (stretched over all keys: the instrument\'s range is in orchestration.md)' if r.get('every_key') else '')
                     + f', {r["velocity_ranges"]} velocity range{"s" if r["velocity_ranges"] != 1 else ""}'
                     + (f'; the preset list: keys {listed["keys"]}, velocity layers {listed["velocity_layers"]}' if listed else ''))
    if found['count'] > 60:
        lines.append(f'  and {found["count"] - 60} more (--json lists all)')
    lines.append(found['note'])
    return files.joined(lines)
