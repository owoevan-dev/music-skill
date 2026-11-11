"""Surge XT parts (`engine: "surge"`): a curated factory patch of the Surge XT synthesizer, played offline through
pedalboard.  Both are GPL-3.0 programs installed beside the skill.  They run only in scripts/surge_host.py, a
GPL-3.0-or-later program that the renderer starts as its own process and talks to through files (a job with the
part's timed MIDI events in, a WAV out): the renderer's own processes never load them, and the host imports one MIT
helper of the skill (with_patch below), which the GPL allows.  The music made with them is the user's.

A VST3's saved state, as JUCE writes it, is "VC2!", a little-endian size and XML whose <IComponent> holds the plugin's
own state in JUCE's text encoding ("<bytes>.<6-bit groups, least significant bit first>").  Surge's state starts with
its patch ("sub3", the sizes of its XML and of the six oscillators' wavetable blocks, then those blocks), the chunk a
.fxp patch file carries after its 60-byte header, so a patch loads by writing its chunk over the patch in the state.
Surge takes the patch on its first audio block and sets its parameters from it there, so the host plays a silent block
before it sets the part's macros and bend range; every event still moves by a short lead-in that is cut off again.  Its oscillators start at random phases, so one part renders a different waveform each time
(the same sound); the render cache, not the renderer, holds a take fixed.  Without Surge, pedalboard or the preset's
file, the part plays its fallback preset on the built-in synth and its stem receipt says why.

pedalboard gives a plugin no tempo, so Surge plays tempo-synced parameters at 120 BPM.  Before a patch loads, each
synced parameter it uses (the left and right times of a Delay effect, an LFO's rate) becomes the free-running value it
has at the part's tempo (part_tempo): Surge stores both as log2 of seconds or of Hz at 120 BPM, so a time moves by
log2(120/bpm) and a rate by log2(bpm/120).  A tempo change inside the part does not move them."""
import json
import math
import os
import re
import struct
import sys
from collections import Counter
from pathlib import Path

PRESETS_FILE = Path(__file__).resolve().parents[2] / 'references' / 'surge-presets.json'
CATALOG_FILE = Path(__file__).resolve().parents[2] / 'references' / 'surge-catalog.json'
# The built-in preset a catalog patch falls back to where Surge or the patch is missing, by the patch's role.
FALLBACK_BY_ROLE = {'lead': 'supersaw_lead', 'brass': 'brass_stab', 'pad': 'warm_pad', 'chords': 'future_bass_chord',
                    'keys': 'fm_epiano', 'pluck': 'pluck', 'bass': 'synthwave_bass', 'sequence': 'pluck',
                    'percussion': 'pluck'}
SCRIPTS = Path(__file__).resolve().parents[1]
TABLE = '.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+'
VALUE = {c: i for i, c in enumerate(TABLE)}
LEAD_S = .1
TAIL_S = 4.0
RATE = 48000
_presets = None
_catalog = None


class Unavailable(Exception):
    """Surge cannot play this part here; the reason goes to the stem receipt."""


def presets():
    global _presets
    if _presets is None:
        _presets = json.loads(PRESETS_FILE.read_text(encoding='utf-8'))
    return _presets


def catalog():
    """Every Surge XT 1.3.4 patch, measured (references/surge-catalog.json), by id; empty where the file is absent."""
    global _catalog
    if _catalog is None:
        _catalog = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))['presets'] if CATALOG_FILE.is_file() else {}
    return _catalog


def entry(name):
    """A patch by curated name or catalog id: its file (relative to the curated or the full patch folder), SHA-256,
    transposition and built-in fallback; None for neither."""
    curated = presets()['presets'].get(name)
    if curated:
        return {**curated, 'folder': 'patches'}
    found = catalog().get(name)
    if not found:
        return None
    measured = found.get('measured') or {}
    fallback = FALLBACK_BY_ROLE.get(found['role'], 'warm_pad')
    if found['role'] == 'bass' and measured.get('centroid_hz', 999) < 120:
        fallback = 'sub_bass'
    return {'patch': found['path'], 'sha256': found['sha256'], 'transpose': found.get('transpose', 0),
            'fallback': fallback, 'role': found['role'], 'folder': 'catalog'}


def validate(track):
    from .model import number
    from . import synth
    spec = track.get('surge')
    if not isinstance(spec, dict) or set(spec) - {'preset', 'macros', 'fallback', 'glide_ms', 'velocity_to_cutoff', 'swell'}:
        raise ValueError(f'{track["id"]}: a surge part needs a "surge" object: preset, and optionally macros, fallback, '
                         'glide_ms, velocity_to_cutoff and swell')
    if entry(spec.get('preset')) is None:
        raise ValueError(f'{track["id"]}: surge preset must be a curated patch (references/surge-presets.json) or a '
                         'catalog id (references/surge-catalog.json; studio.py sounds searches it)')
    macros = spec.get('macros', {})
    if not isinstance(macros, dict) or not all(re.fullmatch(r'[1-8]', str(k)) for k in macros):
        raise ValueError(f'{track["id"]}: surge macros map "1"-"8" to 0-1')
    for v in macros.values():
        number(v, 0, 1, 'surge macro')
    if 'fallback' in spec and spec['fallback'] not in synth.presets():
        raise ValueError(f'{track["id"]}: surge fallback must name a built-in synth preset')
    if 'glide_ms' in spec:
        number(spec['glide_ms'], 4, 4000, 'surge glide_ms')  # Surge's portamento runs from 2^-8 s (off) to 4 s
    if 'velocity_to_cutoff' in spec:
        number(spec['velocity_to_cutoff'], -60, 60, 'surge velocity_to_cutoff')
    if 'swell' in spec and spec['swell'] is not True:
        raise ValueError(f'{track["id"]}: surge swell is true or left out')


def installed(cfg):
    """Surge XT and pedalboard are configured and present (their hashes are checked when a part renders)."""
    surge, board = (cfg or {}).get('surge'), (cfg or {}).get('pedalboard')
    return bool(surge and board and Path(surge.get('binary', surge['path'])).is_file() and Path(board['path']).is_dir())


# The role a built-in preset plays, where a curated Surge patch plays the same role.  The 808's pitch punch and glide, the
# 303's resonant sweep, a reese, a wobble, the chip waves and the noise transitions have none: the built-in synth stays
# the instrument for them.
BUILTIN_ROLES = {'supersaw_lead': 'lead', 'trance_pad': 'pad', 'warm_pad': 'pad', 'pwm_strings': 'pad', 'pluck': 'pluck',
                 'fm_bell': 'pluck', 'future_bass_chord': 'chords', 'brass_stab': 'brass', 'fm_epiano': 'keys',
                 'lofi_keys': 'keys', 'sub_bass': 'bass', 'synthwave_bass': 'bass'}


# Built-in presets no curated patch covers, with the role and the words the catalog's designers put in the names of
# patches for the same sound (matched at the start of a word).  A name is the designer's label, not a measurement: the
# patches so named that the measurement leaves unflagged (sounds.search) are candidates to hear on the part.
CATALOG_NAMES = {'bass_808': ('bass', ('808',)), 'acid_bass': ('bass', ('acid', '303')), 'reese_bass': ('bass', ('reese',)),
                 'wobble_bass': ('bass', ('wobble', 'dubstep')), 'noise_riser': ('fx', ('uplift', 'riser')),
                 'reverse_cymbal': ('percussion', ('reverse',)),
                 **{name: ('lead', ('chip', 'gameboy')) for name in ('chip_square', 'chip_pulse12', 'chip_pulse25', 'chip_arp')}}


ROLES_FILE = Path(__file__).resolve().parents[2] / 'references' / 'surge-roles.json'
MEASURED_FOR = {'bass_808': '808', 'acid_bass': 'acid', 'noise_riser': 'swell', 'reverse_cymbal': 'swell'}
_roles = None


def roles():
    """The Surge patches measured to play a built-in preset's job as the score asks (references/surge-roles.json):
    the 808's slide, the acid line's accents and slides, and the electric pianos' response to velocity."""
    global _roles
    if _roles is None:
        _roles = json.loads(ROLES_FILE.read_text(encoding='utf-8')) if ROLES_FILE.is_file() else {}
    return _roles


def measured_counterparts(builtin):
    """[(catalog id, the surge settings that play the job)] for a built-in preset whose job the roles file measured;
    [] for any other preset."""
    group = MEASURED_FOR.get(builtin)
    if group is None:
        return []
    table = roles().get(group) or {}
    base = table.get('settings', {})
    rows = (table.get('patches') or {}).items()
    if group == 'swell':  # risers and reverse cymbals share the measure; each keeps the catalog role of its sound
        role = CATALOG_NAMES[builtin][0]
        rows = [(pid, row) for pid, row in rows if (catalog().get(pid) or {}).get('role') == role]
    return [(pid, {**base, **row.get('settings', {})}) for pid, row in rows]


def catalog_counterparts(builtin):
    """Catalog patches named for a built-in preset's sound (CATALOG_NAMES), dark to bright; none where it has no entry."""
    role, words = CATALOG_NAMES.get(builtin, (None, ()))
    if not words:
        return []
    from . import sounds
    named = re.compile(r'\b(?:' + '|'.join(map(re.escape, words)) + ')', re.I)
    return [row['id'] for row in sounds.search(role=role, limit=len(catalog()))['shown'] if named.search(catalog()[row['id']]['name'])]


def counterparts(builtin):
    """The curated Surge patches for a built-in preset's role: of that role, those that fall back to it first (the
    closest measured), in the list's order; none for a role no curated patch plays."""
    role = BUILTIN_ROLES.get(builtin)
    if role is None:
        return []
    same = [name for name, entry in presets()['presets'].items() if entry['role'] == role]
    return sorted(same, key=lambda name: presets()['presets'][name].get('fallback') != builtin)


def fallback_track(track):
    """The part as a built-in synth part on its fallback preset."""
    spec = track['surge']
    name = spec.get('fallback') or entry(spec['preset'])['fallback']
    t = {k: v for k, v in track.items() if k != 'surge'}
    patch = {'preset': name}
    if 'glide_ms' in spec:  # the slide survives on the built-in synth: one line, gliding between overlapping notes
        patch.update(mono=True, glide_ms=min(2000, spec['glide_ms']))
    return {**t, 'engine': 'synth', 'synth': patch}


def as_played(track):
    """The part as its MIDI is written for Surge.  A patch built to sound an octave below the key it is played on plays
    an octave up (the catalog's `transpose`), so that the written pitch sounds; a key past the MIDI range is played at
    its end, 0 or 127.  render writes this part's MIDI, and the mix counts the same part for the time it sounds
    (mixbus.held_spans): two written pitches that land on one key are one key's notes in both."""
    shift = entry(track['surge']['preset']).get('transpose', 0)
    return {**track, 'notes': [{**n, 'pitch': max(0, min(127, n['pitch'] + shift))} for n in track['notes']]} if shift else track


def dependencies(cfg, track):
    """What a Surge part's sound depends on, for the render cache: the plugin, pedalboard, patch and host, the fallback,
    and whether the patch plays here or why not, so that a fallback rendered before Surge XT or its full patch set was
    installed is not reused once it is."""
    found = entry(track['surge']['preset'])
    from .model import file_hash
    try:
        locate(cfg, track)
        plays = 'Surge XT'
    except Unavailable as why:
        plays = 'fallback: ' + str(why)
    return {'plays': plays, 'surge': (cfg.get('surge') or {}).get('sha256'), 'pedalboard': (cfg.get('pedalboard') or {}).get('sha256'),
            'patch': found['sha256'], 'fallback': fallback_track(track)['synth']['preset'], 'host': file_hash(SCRIPTS / 'surge_host.py')}


def _decode(text):
    size, data = text.split('.', 1)
    out, pos = bytearray(int(size)), 0
    for c in data:
        if c not in VALUE:
            continue
        v = VALUE[c]
        for b in range(6):
            if v >> b & 1 and (pos + b) // 8 < len(out):
                out[(pos + b) // 8] |= 1 << ((pos + b) % 8)
        pos += 6
    return bytes(out)


def _encode(blob):
    bits, chars = len(blob) * 8, []
    for pos in range(0, bits, 6):
        v = 0
        for b in range(6):
            p = pos + b
            if p < bits and blob[p // 8] >> (p % 8) & 1:
                v |= 1 << b
        chars.append(TABLE[v])
    return f'{len(blob)}.' + ''.join(chars)


def _patch_size(blob):
    if blob[:4] != b'sub3':
        raise ValueError('not a Surge patch')
    return 32 + struct.unpack('<I', blob[4:8])[0] + sum(struct.unpack('<6I', blob[8:32]))


def with_patch(state, fxp):
    """`state` (the plugin's raw VST3 state) with the patch chunk of a Surge .fxp file in place of its patch."""
    if state[:4] != b'VC2!' or fxp[:4] != b'CcnK' or fxp[8:12] != b'FPCh':
        raise ValueError('unexpected Surge state or patch file')
    size = struct.unpack('<I', state[4:8])[0]
    xml = state[8:8 + size].decode('utf-8')
    m = re.search(r'<IComponent>(.*?)</IComponent>', xml, re.S)
    blob = _decode(m.group(1).strip())
    chunk = fxp[60:60 + struct.unpack('>I', fxp[56:60])[0]]
    _patch_size(chunk)
    new = (xml[:m.start(1)] + _encode(chunk + blob[_patch_size(blob):]) + xml[m.end(1):]).encode('utf-8')
    return b'VC2!' + struct.pack('<I', len(new)) + new + state[8 + size:]


SYNCED_DELAY = re.compile(r'fx(\d+)_p[01]$')  # a Delay effect's (type 1) left and right times
SYNCED_RATE = re.compile(r'[ab]_lfo\d+_rate$')


def at_tempo(fxp, bpm):
    """The .fxp `fxp` with its tempo-synced Delay times and LFO rates turned into free-running values for `bpm`, and
    the names of the parameters changed."""
    size = struct.unpack('>I', fxp[56:60])[0]
    chunk = fxp[60:60 + size]
    if fxp[:4] != b'CcnK' or chunk[:4] != b'sub3':
        raise ValueError('not a Surge patch')
    xml_size = struct.unpack('<I', chunk[4:8])[0]
    xml = chunk[32:32 + xml_size].decode('latin-1')
    fx_types = {m.group(1): float(m.group(2)) for m in re.finditer(r'<fx(\d+)_type [^>]*?value="([-+\d.eE]+)"', xml)}
    changed = []

    def free(m):
        name, attrs = m.group(1), m.group(2)
        if 'temposync="1"' not in attrs:
            return m.group(0)
        delay = SYNCED_DELAY.match(name)
        if delay and fx_types.get(delay.group(1)) == 1:
            shift = math.log2(120 / bpm)
        elif SYNCED_RATE.match(name):
            shift = math.log2(bpm / 120)
        else:
            return m.group(0)
        value = float(re.search(r'value="([-+\d.eE]+)"', attrs).group(1))
        attrs = re.sub(r'value="[-+\d.eE]+"', f'value="{value + shift:.6f}"', attrs, count=1).replace('temposync="1"', 'temposync="0"')
        changed.append(name)
        return f'<{name} {attrs}/>'

    new = re.sub(r'<(\w+) ([^>]*?)/>', free, xml).encode('latin-1')
    chunk = chunk[:4] + struct.pack('<I', len(new)) + chunk[8:32] + new + chunk[32 + xml_size:]
    # Only the chunk size changes; Surge leaves the header's byteSize at 0, and so does this.
    return fxp[:56] + struct.pack('>I', len(chunk)) + chunk + fxp[60 + size:], changed


# What the score controls on a Surge patch, from Surge XT 1.3.4's sources (SurgeStorage.h, ModulationSource.h,
# Parameter.cpp, SurgeVoice.cpp): play mode 4 is pm_mono_st_fp, one voice whose envelopes do not retrigger on an
# overlapping note and whose portamento acts only between overlapping notes, as the TR-808's slides in trap and the
# TB-303's slides are played; portamento is stored as log2 of seconds and is off at its minimum, -8; modulation source
# 1 is velocity, whose output is velocity / 127, and a routing adds depth times that output to its parameter in the
# parameter's own units, semitones for a filter cutoff.
MONO_SINGLE_TRIGGER_FINGERED = 4
MS_VELOCITY = 1


def _element(xml, name):
    m = re.search(r'<%s\b([^>]*?)(/?)>' % re.escape(name), xml)
    return m


def played_as(fxp, spec, swell_seconds=None):
    """The .fxp with what the part's `surge` object asks the score to control, on both scenes, and what was set.

    `glide_ms`: each scene becomes one voice that glides only between overlapping notes, its envelopes not retriggered
    there, the glide taking that many milliseconds.  `velocity_to_cutoff`: velocity moves filter 1's cutoff by that many
    semitones at velocity 127 and in proportion below, in place of any velocity routing the patch had on it.  `swell`:
    the attacks of the amplitude and filter envelopes (Surge's envelopes 1 and 2) take `swell_seconds`, the length of the
    part's notes, so a riser rises over the whole note (Surge's attack runs from 2^-8 to 2^5 seconds).  A patch without
    any of these comes back unchanged, byte for byte."""
    glide, cutoff, swell = spec.get('glide_ms'), spec.get('velocity_to_cutoff'), spec.get('swell')
    if glide is None and cutoff is None and not swell:
        return fxp, {}
    size = struct.unpack('>I', fxp[56:60])[0]
    chunk = fxp[60:60 + size]
    if fxp[:4] != b'CcnK' or chunk[:4] != b'sub3':
        raise ValueError('not a Surge patch')
    xml_size = struct.unpack('<I', chunk[4:8])[0]
    xml = chunk[32:32 + xml_size].decode('latin-1')
    done = {}

    def set_value(xml, name, value):
        # A time set in milliseconds is free-running: a temposync flag the patch had is turned off, as at_tempo does,
        # or Surge would read the value against the tempo it is given (none here: 120 BPM).
        m = _element(xml, name)
        if m is None:
            raise ValueError(f'the patch has no {name}')
        attrs = re.sub(r'\bvalue="[^"]*"', f'value="{value}"', m.group(1), count=1).replace('temposync="1"', 'temposync="0"')
        return xml[:m.start()] + f'<{name}{attrs}{m.group(2)}>' + xml[m.end():]

    if glide is not None:
        for scene in 'ab':
            xml = set_value(xml, f'{scene}_polymode', MONO_SINGLE_TRIGGER_FINGERED)
            xml = set_value(xml, f'{scene}_portamento', f'{math.log2(glide / 1000):.6f}')
        done['glide_ms'] = glide
    if swell:
        if not swell_seconds:
            raise ValueError("swell needs the length of the part's notes")
        given = min(5.0, max(-8.0, math.log2(swell_seconds)))
        attack = f'{given:.6f}'
        for scene in 'ab':
            for env in (1, 2):
                xml = set_value(xml, f'{scene}_env{env}_attack', attack)
        # What the patch got: Surge's attack stops at 2^5 = 32 s, and a 40 s note's swell was recorded as 40 s (GPT's
        # review of 0.5, SA03); what was asked is kept beside it where the range cut it.
        done['swell_seconds'] = round(2 ** given, 6)
        if abs(2 ** given - swell_seconds) > 1e-6:
            done['swell_asked_seconds'] = round(swell_seconds, 6)
    if cutoff is not None:
        route = f'<modrouting source="{MS_VELOCITY}" depth="{cutoff:.6f}" muted="0" source_index="0" />'
        for scene in 'ab':
            name = f'{scene}_filter1_cutoff'
            m = _element(xml, name)
            if m is None:
                raise ValueError(f'the patch has no {name}')
            if m.group(2):
                xml = xml[:m.start()] + f'<{name}{m.group(1).rstrip()}>{route}</{name}>' + xml[m.end():]
            else:
                end = xml.index(f'</{name}>', m.end())
                inner = re.sub(r'<modrouting\b[^>]*\bsource="%d"[^>]*/>' % MS_VELOCITY, '', xml[m.end():end])
                xml = xml[:m.end()] + inner + route + xml[end:]
        done['velocity_to_cutoff'] = cutoff
    new = xml.encode('latin-1')
    chunk = chunk[:4] + struct.pack('<I', len(new)) + chunk[8:32] + new + chunk[32 + xml_size:]
    return fxp[:56] + struct.pack('>I', len(chunk)) + chunk + fxp[60 + size:], done


VERIFIED_BOARD = {}  # pedalboard folder -> (size, mtime) of its RECORD when its files last matched it in this process


def board_intact(pylib, record_sha256=None):
    """Whether the installed pedalboard is the files pip installed: every file its RECORD lists has the SHA-256 and
    size given there (PEP 376 and the wheel format: RECORD is the installer's list of the files it wrote, with their
    hashes), and no code file is in the package that RECORD does not list.  With `record_sha256` (bootstrap writes it),
    RECORD itself must be the one installed.  Checked once per process while RECORD is unchanged."""
    import base64
    import csv
    import hashlib
    pylib = Path(pylib)
    records = sorted(pylib.glob('pedalboard-*.dist-info/RECORD'))
    if len(records) != 1:
        return False
    record = records[0]
    stamp = (record.stat().st_size, record.stat().st_mtime_ns)
    if VERIFIED_BOARD.get(str(pylib)) == stamp:
        return True
    data = record.read_bytes()
    if record_sha256 and hashlib.sha256(data).hexdigest() != record_sha256:
        return False
    listed = set()
    for row in csv.reader(data.decode('utf-8').splitlines()):
        if len(row) < 3 or not row[1]:
            continue  # RECORD lists itself (and .pyc files) without a hash
        name, (algo, _, digest) = row[0], row[1].partition('=')
        f = (pylib / name).resolve()
        if pylib.resolve() not in f.parents or algo != 'sha256' or not f.is_file() or str(f.stat().st_size) != row[2]:
            return False
        h = hashlib.sha256(f.read_bytes()).digest()
        if base64.urlsafe_b64encode(h).rstrip(b'=').decode() != digest:
            return False
        listed.add(f)
    code = ('.py', '.pyd', '.so', '.dll', '.dylib')
    if any(f.suffix in code and f.resolve() not in listed for f in (pylib / 'pedalboard').rglob('*')):
        return False
    VERIFIED_BOARD[str(pylib)] = stamp
    return True


def locate(cfg, track):
    """The plugin, pedalboard and patch file for a part, checked by hash; Unavailable with the reason otherwise.  The
    hashed binary must be the plugin that loads (the file itself, or inside its bundle), and pedalboard the files pip
    installed.  Reasons name files, not their full paths, as they go into receipts a user may share."""
    from .model import file_hash
    found = entry(track['surge']['preset'])
    surge, board = cfg.get('surge'), cfg.get('pedalboard')
    if not surge or not board:
        raise Unavailable('Surge XT is not installed (bootstrap.py installs it unless --no-surge)')
    plugin, binary, pylib = Path(surge['path']), Path(surge.get('binary', surge['path'])), Path(board['path'])
    same = lambda a, b: os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    if not (same(binary, plugin) or any(same(plugin, up) for up in binary.parents)):
        raise Unavailable(f'the Surge XT binary checked ({binary.name}) is not the plugin that would load ({plugin.name}); '
                          'run bootstrap.py again')
    if not binary.is_file() or file_hash(binary) != surge['sha256']:
        raise Unavailable(f'Surge XT plugin missing or changed: {binary.name}')
    if not (pylib / 'pedalboard').is_dir():
        raise Unavailable('pedalboard missing from the runtime folder (bootstrap.py installs it)')
    if not board_intact(pylib, board.get('record_sha256')):
        raise Unavailable('pedalboard is not the package bootstrap.py installed (a file is changed, added or missing); '
                          'run bootstrap.py again')
    if found['folder'] == 'catalog' and not surge.get('catalog'):
        raise Unavailable('the full Surge XT patch set is not installed (bootstrap.py installs it unless --no-surge-catalog)')
    patch = Path(surge['catalog'] if found['folder'] == 'catalog' else surge['patches']) / found['patch']
    if not patch.is_file() or file_hash(patch) != found['sha256']:
        raise Unavailable(f'Surge patch missing or changed: {found["patch"]}')
    return plugin, pylib, patch


def part_tempo(project, track):
    """The one tempo a part's synced parameters follow: the written tempo (`clock.tempo`, before rubato) that most of
    its notes start under, the earliest of equals.  A pickup into a section, a phrase's ritardando or the final one
    does not set it."""
    written = sorted((float(b), float(v)) for b, v in project['clock']['tempo'])
    at = lambda beat: next((v for b, v in reversed(written) if b <= beat + 1e-9), written[0][1])
    tempos = [at(n['on']) for n in sorted(track['notes'], key=lambda n: n['on'])] or [written[0][1]]
    counts = Counter(tempos)
    return max(tempos, key=counts.__getitem__)


def swell_length(project, track):
    """The one length in seconds a swell part's notes share, at the written tempo (a riser rises over its note); a part
    whose notes differ by more than 5 ms is refused, as one patch takes one attack: split it into parts."""
    from .model import Clock
    clock = Clock(project)
    lengths = [clock.seconds(n['on'] + n['duration']) - clock.seconds(n['on']) for n in track['notes']]
    if not lengths:
        return None
    if max(lengths) - min(lengths) > .005:
        raise ValueError(f'{track["id"]}: a surge swell part plays one length of note (it sets the attack of the patch to it); '
                         f'these run from {min(lengths):.2f} to {max(lengths):.2f} s: put each length in a part of its own')
    return lengths[0]


def render(project, track, raw, folder, cfg):
    """Play a Surge part into `raw`: its MIDI is written by the renderer's writer, then a separate process loads the
    plugin, sets the patch and macros and renders.  Raises Unavailable when Surge cannot play here."""
    from . import files, midi
    plugin, pylib, patch = locate(cfg, track)
    bpm = part_tempo(project, track)
    fxp, synced = at_tempo(patch.read_bytes(), bpm)
    fxp, controls = played_as(fxp, track['surge'], swell_length(project, track) if track['surge'].get('swell') else None)
    if synced or controls:
        patch = Path(folder) / 'patch_at_tempo.fxp'
        with files.staged(patch) as f:  # written whole, noted as the render's (musiclib.files)
            f.write(fxp)
    part_midi, job = Path(folder) / 'surge.mid', Path(folder) / 'surge_job.json'
    midi.write(project, part_midi, [as_played(track)], single_stem=True, render=True)
    # Notes, pitch bend, mod wheel and sustain go to the plugin, timed in seconds; the bend range goes as a setting.
    song = midi.read_own(part_midi)
    events = [[bytes([s, *a]).hex(), _seconds(tick, song['tempos'], song['division']) + LEAD_S]
              for t in song['tracks'] for tick, s, *a in t['events']
              if (s >> 4) in (8, 9, 14) or ((s >> 4) == 11 and a[0] in (1, 64))]
    # The patch rings on after its last event: four seconds at least, and as long as the project's tail asks
    # (tail_seconds, which the guides raise for a long release), up to the piece's end and its tail.  Four seconds
    # alone cut a longer release to silence, and the quiet-tail check then passed (found by GPT Pro's seventh review).
    from .model import Clock
    clock, last = Clock(project), max((t for _, t in events), default=LEAD_S)
    duration = max(last + TAIL_S, min(LEAD_S + clock.end + clock.tail, last + clock.tail))
    with files.staged(job, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'plugin': str(plugin), 'pylib': str(pylib), 'patch': str(patch), 'out': str(raw), 'rate': RATE,
                            'events': events, 'duration': duration,
                            'trim': int(round(LEAD_S * RATE)), 'macros': track['surge'].get('macros', {}),
                            'bend_range': track['performance'].get('bend_range', 2)}))
    # The host runs as every program of a render does (audio.run): it stops when the render is stopped (another part
    # failed, Ctrl+C), which subprocess.run could not see (found by GPT Pro's fifth review of 0.4.0), and its output
    # goes to surge.log in the cache entry.  A stop is not a failed host: it is raised, never answered with the fallback.
    from . import audio
    try:
        audio.run([sys.executable, str(SCRIPTS / 'surge_host.py'), str(job)], folder, 'surge', timeout=1800, cwd=SCRIPTS)
    except RuntimeError as e:
        raise Unavailable(f'Surge XT failed to render ({str(e)[:160]}; see surge.log in the cache entry {Path(folder).name[:12]})') from None
    if not Path(raw).is_file() or Path(raw).stat().st_size <= 44:
        raise Unavailable(f'Surge XT wrote no audio (see surge.log in the cache entry {Path(folder).name[:12]})')
    out = {'tempo_synced': {'bpm': round(bpm, 3), 'parameters': synced}} if synced else {}
    return {**out, 'played_as': controls} if controls else out


def _seconds(tick, tempos, division):
    tempos = sorted(tempos) or [(0, 500000)]
    if tempos[0][0] != 0:
        tempos = [(0, 500000)] + tempos
    t, last_tick, last_tempo = 0.0, 0, tempos[0][1]
    for at, tempo in tempos[1:]:
        if at >= tick:
            break
        t += (at - last_tick) / division * last_tempo / 1e6
        last_tick, last_tempo = at, tempo
    return t + (tick - last_tick) / division * last_tempo / 1e6
