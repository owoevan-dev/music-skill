"""studio.py instruments: the configured banks' presets found by words of their name, their General MIDI family or
their bank, each with the keys its samples cover and its velocity ranges, both read from the bank itself, and what the
skill's preset list (references/soundbank-presets.md) gives for it (0.8 step 2.6: notes outside an instrument's range
were the 0.7 agents' most frequent failure, 7 of 43).  The bank and program it reports are what a part's `soundfont`
and `patch` take (schema.md), so a part need not guess them."""
import difflib
import functools
import json
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


def zones_of(config_file, bank, bank_no, program):
    """The (keys, velocities) of each zone pair that sounds in a configured preset (pairs), merged where equal: what a
    note may be written on and how hard it may be played to sound (a preset may give a key a sample at some velocities
    only: start's placeholder at velocity 64 was silent on one of 90-127, the review of 0.8.0)."""
    configured = banks(config_file)
    if bank not in configured:
        raise ValueError(f'No configured bank is named {files.one_line(bank)!r}; the configuration names {", ".join(sorted(configured))}')
    sounds = read(configured[bank])
    preset = next((p for p in sounds['presets'] if (p['bank'], p['program']) == (bank_no, program)), None)
    if preset is None:
        raise ValueError(f'{bank} has no preset at {bank_no}:{program}')
    return sorted({(k, v) for _, _, _, k, v in pairs(sounds, preset)})


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
    if 'default' in (config.get('soundfonts') or {}):   # the name doctor and the render refuse there (it listed that bank: the review of 0.8.0)
        raise ValueError(f'{config_file}: soundfonts must map lower-case names (not "default") to entries; "default" is the bank under "soundfont"')
    out = {'default': config['soundfont']['path']} if isinstance(config.get('soundfont'), dict) else {}
    out.update({name: e['path'] for name, e in (config.get('soundfonts') or {}).items() if isinstance(e, dict) and 'path' in e})
    return out


def search(config_file, words, bank=None):
    """The presets every word matches (in the preset's name, its family or its bank's name, without regard to case),
    by bank, bank number and program, in every configured bank or in `bank` alone (then words may be none).  A word
    of the form "0:41" is a bank number and program, as a part's instrument is written.  Where no preset has every
    word, those that have the most are given (`every_word` false, each with the words it `has`): a search for
    "electric bass slap" is answered with "Slap Bass".  Where no word matches, the refusal names the nearest word
    that would, and the synthesizers' own lists."""
    words = [w.lower() for w in words if w.strip()]
    numbers = [w for w in words if re.fullmatch(r'\d+:\d+', w)]
    if len(numbers) > 1:
        raise ValueError(f'instruments takes one bank number and program at a time, not {" and ".join(numbers)}')
    patch = tuple(int(x) for x in numbers[0].split(':')) if numbers else None
    words = [w for w in words if w not in numbers]
    if not words and patch is None and bank is None:
        raise ValueError('instruments takes one or more words: a part of a preset\'s name (violin), a family (strings) or a bank (vsco)')
    configured = banks(config_file)
    if bank is not None and bank not in configured:
        raise ValueError(f'No configured bank is named {files.one_line(bank)!r}; the configuration names {", ".join(sorted(configured))}')
    listed, rows, vocabulary, texts = documented(), [], set(), []
    # first what each preset has of the words, then the rows of those that have the most
    candidates, most = [], 0
    for name, path in sorted(configured.items()):
        if bank is not None and name != bank:
            continue
        sounds = read(path)
        for p in sounds['presets']:
            family = 'drum kit' if p['bank'] >= 128 else FAMILIES[p['program'] // 8] if p['program'] < 128 else 'no General MIDI family'
            text = f'{p["name"]} {family} {name}'.lower()
            vocabulary.update(re.findall(r'[a-z0-9_]+', text))   # a bank's name whole (iowa_strings), as a word may give it
            texts.append(text)
            if patch is not None and (p['bank'], p['program']) != patch:
                continue
            has = [w for w in words if w in text]
            if has or not words:
                candidates.append((name, sounds, p, family, has))
                most = max(most, len(has))
    every = most == len(words)
    # a word is some preset's where it is in that preset's text as written: "honky-tonk" is in no single word of it
    held = lambda w: any(w in x for x in texts)
    if not every and any(not held(w) for w in words):
        candidates = []   # a word that no preset has at all is a slip of the pen: refused with the nearest word (below)
    spent = {}
    for name, sounds, p, family, has in candidates:
        if len(has) == most:
            keys, ranges = measured(sounds, p, spent.setdefault(name, [0]))   # one bound for a bank's presets together (pairs)
            row = {'bank': name, 'patch': {'bank': p['bank'], 'program': p['program']}, 'preset': p['name'], 'family': family,
                   'keys': f'{note(min(keys))}-{note(max(keys))}' if keys else None, 'keys_midi': [min(keys), max(keys)] if keys else None,
                   'keys_without_a_sample': (max(keys) - min(keys) + 1 - len(keys)) if keys else None, 'key_ranges': key_ranges(keys),
                   'velocity_ranges': len(ranges), 'velocities': [list(v) for v in ranges]}   # the ranges too, not their count alone (the review of 0.8.0)
            if len(keys) >= 120:   # a General MIDI bank stretches its samples over the keyboard: the keys say nothing of the instrument
                row['every_key'] = (f'the bank stretches its samples over {len(keys)} of the 128 keys: take the instrument\'s range from '
                                    'orchestration.md')
            if (name, p['bank'], p['program']) in listed:
                row['preset_list'] = listed[(name, p['bank'], p['program'])]
            if not every:
                row['has'] = has
            rows.append(row)
    if not rows:
        asked = ' '.join(words + numbers)
        near = [w for w in words if not held(w)]
        hint = difflib.get_close_matches(near[0], sorted(vocabulary), n=1) if near else []
        # the built-in synthesizer's presets are not in any bank: a word that names one says so
        synth_file = Path(__file__).resolve().parents[2] / 'references' / 'synth-presets.json'
        builtin = sorted(json.loads(synth_file.read_text(encoding='utf-8')).get('presets', {})) if synth_file.is_file() else []
        named = [w for w in words if w in builtin]
        raise ValueError(f'No configured preset matches {asked!r}' + (f'; did you mean {hint[0]!r}?' if hint else '')
                         + (f' {named[0]!r} is a built-in synth preset: "engine": "synth", "synth": {{"preset": "{named[0]}"}}.' if named else '')
                         + ' Words match a preset\'s name, its family (' + ', '.join(FAMILIES) + ') or its bank; a bank number and '
                         'program are written 0:41. The synthesizers are not in the banks: references/synth-presets.json lists the '
                         'built-in presets, and studio.py sounds finds the Surge XT patches.')
    rows.sort(key=lambda r: (r['bank'], r['patch']['bank'], r['patch']['program']))
    return {'count': len(rows), 'every_word': every, 'words': len(words), 'presets': rows,
            'note': ('A part plays one with "soundfont": <bank> and "patch": {"bank": ..., "program": ...} (schema.md). keys: the '
                     'notes its samples cover (MIDI 60 is C4), read from the bank; write inside them, and nearer the middle for an '
                     'even tone. family is General MIDI\'s name for the program number, which a bank of one instrument need not '
                     'follow (a guitar on program 0 is listed under piano). velocity_ranges counts the ranges of velocity its '
                     'samples are split into: dynamic layers, and where a bank chooses among takes by the velocity\'s value '
                     '(the banks built here, fsbs_direct) those too; velocities lists them (a note below every range sounds '
                     'nothing); '
                     'preset_list gives the recorded layers as references/soundbank-presets.md lists them.')}


def summary(found):
    """One line a preset."""
    lines = [f'{found["count"]} preset{"s" if found["count"] != 1 else ""}:']
    if not found.get('every_word', True):   # the nearest, said as such
        most = max(len(r.get('has', ())) for r in found['presets'])
        lines = [f'No preset has every word; {found["count"]} ha{"s" if found["count"] == 1 else "ve"} {most} of the {found["words"]}:']
    for r in found['presets'][:60]:
        listed = r.get('preset_list')
        family = r['family'] if r['patch']['bank'] >= 128 or r['patch']['program'] >= 128 else f'GM family of program {r["patch"]["program"]}: {r["family"]}'
        lines.append(f'  {r["bank"]} {r["patch"]["bank"]}:{r["patch"]["program"]} {r["preset"]} ({family}): keys {r["keys"]}'
                     + (f', {r["keys_without_a_sample"]} without a sample' if r['keys_without_a_sample'] else '')
                     + (f' (stretched over {r["keys_midi"][1] - r["keys_midi"][0] + 1 - r["keys_without_a_sample"]} keys: the instrument\'s range is in orchestration.md)' if r.get('every_key') else '')
                     + f', {r["velocity_ranges"]} velocity range{"s" if r["velocity_ranges"] != 1 else ""}'
                     + (f'; the preset list: keys {listed["keys"]}, velocity layers {listed["velocity_layers"]}' if listed else '')
                     + (f'; has: {", ".join(r["has"])}' if 'has' in r else ''))
    if found['count'] > 60:
        lines.append(f'  and {found["count"] - 60} more (--json lists all)')
    lines.append(found['note'])
    return files.joined(lines)
