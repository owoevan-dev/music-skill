"""Bounded SoundFont 2 reader and writer.

The reader parses RIFF structure and the preset/instrument/sample tables only; sample data is
located but not loaded, so multi-gigabyte banks can be inventoried.  Sizes and record counts are
checked against the file.  The writer builds banks from PCM arrays (used for CC0 sample sets that
are published as WAV files).  Nothing in a bank is executed.
"""
import struct
from pathlib import Path
import numpy as np
from . import files

GEN = {'startAddrsOffset': 0, 'endAddrsOffset': 1, 'startloopAddrsOffset': 2, 'endloopAddrsOffset': 3,
       'startAddrsCoarseOffset': 4, 'modLfoToPitch': 5, 'vibLfoToPitch': 6, 'modEnvToPitch': 7,
       'initialFilterFc': 8, 'initialFilterQ': 9, 'modLfoToFilterFc': 10, 'modEnvToFilterFc': 11,
       'endAddrsCoarseOffset': 12, 'modLfoToVolume': 13, 'chorusEffectsSend': 15, 'reverbEffectsSend': 16,
       'pan': 17, 'delayModLFO': 21, 'freqModLFO': 22, 'delayVibLFO': 23, 'freqVibLFO': 24, 'delayModEnv': 25,
       'attackModEnv': 26, 'holdModEnv': 27, 'decayModEnv': 28, 'sustainModEnv': 29, 'releaseModEnv': 30,
       'keynumToModEnvHold': 31, 'keynumToModEnvDecay': 32, 'delayVolEnv': 33, 'attackVolEnv': 34,
       'holdVolEnv': 35, 'decayVolEnv': 36, 'sustainVolEnv': 37, 'releaseVolEnv': 38, 'keynumToVolEnvHold': 39,
       'keynumToVolEnvDecay': 40, 'instrument': 41, 'keyRange': 43, 'velRange': 44,
       'startloopAddrsCoarseOffset': 45, 'keynum': 46, 'velocity': 47, 'initialAttenuation': 48,
       'endloopAddrsCoarseOffset': 50, 'coarseTune': 51, 'fineTune': 52, 'sampleID': 53, 'sampleModes': 54,
       'scaleTuning': 56, 'exclusiveClass': 57, 'overridingRootKey': 58}
GEN_NAME = {v: k for k, v in GEN.items()}
RANGE_GENS = {43, 44}
UNSIGNED_GENS = {41, 53, 54}
PHDR = struct.Struct('<20sHHHIII')
BAG = struct.Struct('<HH')
MOD = struct.Struct('<HHhHH')
GENREC = struct.Struct('<HH')
INST = struct.Struct('<20sH')
SHDR = struct.Struct('<20sIIIIIBbHH')
PDTA = {b'phdr': PHDR, b'pbag': BAG, b'pmod': MOD, b'pgen': GENREC, b'inst': INST, b'ibag': BAG,
        b'imod': MOD, b'igen': GENREC, b'shdr': SHDR}
MAX_RECORDS = 2_000_000
# Modulators that replace a synthesizer default (a zone modulator with the same sources and destination overrides
# it).  SF2 default 1: velocity to attenuation, concave, 960 cB.  Default 2: velocity to filter cutoff, -2400 cents;
# FluidSynth applies it only from velocity 64 (a switch as second source), so both forms are listed.
VELOCITY_TO_ATTENUATION = ((0x0502, 48, 0),)
# FluidSynth applies a zone's initialAttenuation (generator 48) at 0.4 of its centibels, as the EMU8000 did, so a bank
# that wants N cB heard writes N / 0.4 (measured with FluidSynth 2.6.1: 120 written, 4.8 dB heard).
EMU_ATTENUATION = 0.4
VELOCITY_TO_FILTER = ((0x0102, 8, 0), (0x0102, 8, 0x0C02))

def override(identities, amount):
    return [(src, dest, int(amount), amount_src, 0) for src, dest, amount_src in identities]

def linear_velocity_attenuation(amount):
    """Velocity to attenuation on a straight line, `amount` cB at velocity 0 and none at 127, in place of the concave
    default: every velocity step changes the level by the same number of decibels."""
    return override(VELOCITY_TO_ATTENUATION, 0) + [(0x0102, 48, int(amount), 0, 0)]

def timecents(seconds):
    return int(round(1200 * np.log2(max(seconds, 0.001))))

def _name(raw):
    return raw.split(b'\0', 1)[0].decode('latin-1', 'replace')

def _gen_value(oper, amount):
    if oper in RANGE_GENS:
        return (amount & 0xFF, amount >> 8)
    if oper in UNSIGNED_GENS:
        return amount
    return amount - 0x10000 if amount >= 0x8000 else amount

def _chunks(f, start, end):
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        cid, size = struct.unpack('<4sI', f.read(8))
        if pos + 8 + size > end:
            raise ValueError(f'Chunk {cid!r} overruns its container')
        yield cid, pos + 8, size
        pos += 8 + size + (size & 1)

MAX_ZONES = 262_144  # preset and instrument zones together; the largest bank the skill installs has 9,400 (our count)

def structure(tables):
    """Refuse a bank whose tables do not hold together, as the SoundFont 2.04 specification (7.2-7.3, 7.6-7.7) and
    FluidSynth's loader do: the bag indices of the preset and instrument headers, and the generator and modulator
    indices of the bags, never decrease; each header table's terminal record names the bag table's terminal record;
    and each bag table's terminal record names the generator or modulator table's terminal record, or the end of a
    table that has none (FluidSynth accepts a missing terminal generator or modulator).  "Structurally defective ...
    rejected at load time" is the specification's word for any other bank.  With the indices in order, every zone and
    generator is read once, so the zones built stay in proportion to the file (non-monotonic indices repeat a range
    of zones as often as a header names it)."""
    for head, index, bag, gen, mod, what in ((b'phdr', 3, b'pbag', b'pgen', b'pmod', 'preset'),
                                             (b'inst', 1, b'ibag', b'igen', b'imod', 'instrument')):
        heads, bags = [h[index] for h in tables[head]], tables[bag]
        if not heads or not bags or not tables[b'shdr']:
            raise ValueError(f'SoundFont {what} tables without their terminal records: a structurally defective bank')
        if any(a > b for a, b in zip(heads, heads[1:])) or heads[-1] != len(bags) - 1:
            raise ValueError(f'SoundFont {what} header indices are not monotonic or do not end at the bag table\'s end: '
                             'a structurally defective bank')
        for k, table in ((0, gen), (1, mod)):
            xs = [b[k] for b in bags]
            if any(a > b for a, b in zip(xs, xs[1:])) or xs[-1] not in (len(tables[table]) - 1, len(tables[table])):
                raise ValueError(f'SoundFont {what} bag indices are not monotonic or do not end at the '
                                 f'{"generator" if k == 0 else "modulator"} table\'s end: a structurally defective bank')
    zones = len(tables[b'pbag']) + len(tables[b'ibag']) - 2
    if zones > MAX_ZONES:
        raise ValueError(f'SoundFont with {zones} zones: more than the {MAX_ZONES} this reader takes')

def read(path):
    """A SoundFont's tables and where its sample data lies, refusing a damaged file with ValueError: a chunk shorter
    than its fields says what is wrong rather than raising struct.error (found by the stress test of 0.4.0)."""
    try:
        return _read(path)
    except struct.error as e:
        raise ValueError(f'{path}: not a whole SoundFont 2 file (a chunk is shorter than its fields: {e})') from None


def _read(path):
    path = Path(path)
    total = path.stat().st_size
    with path.open('rb') as f:
        head = f.read(12)
        if head[:4] != b'RIFF' or head[8:12] != b'sfbk':
            raise ValueError('Not a SoundFont 2 file')
        riff_end = min(total, 8 + struct.unpack('<I', head[4:8])[0])
        info, sdta, tables = {}, {}, {}
        for cid, off, size in _chunks(f, 12, riff_end):
            if cid != b'LIST':
                continue
            f.seek(off)
            kind = f.read(4)
            for sub, soff, ssize in _chunks(f, off + 4, off + size):
                if kind == b'INFO' and ssize <= 65536:
                    f.seek(soff)
                    raw = f.read(ssize)
                    info[sub.decode('latin-1')] = struct.unpack('<HH', raw[:4]) if sub in (b'ifil', b'iver') else _name(raw)
                elif kind == b'sdta':
                    sdta[sub] = (soff, ssize)
                elif kind == b'pdta' and sub in PDTA:
                    rec = PDTA[sub]
                    if ssize % rec.size or ssize // rec.size > MAX_RECORDS:
                        raise ValueError(f'Bad {sub!r} table size')
                    f.seek(soff)
                    tables[sub] = [rec.unpack_from(buf, i * rec.size) for buf in [f.read(ssize)] for i in range(ssize // rec.size)]
    missing = [k for k in PDTA if k not in tables]
    if missing or b'smpl' not in sdta:
        raise ValueError(f'Incomplete SoundFont tables: {missing}')
    structure(tables)

    def zones(headers, bag, gen, mod, terminal):
        out = []
        for i, h in enumerate(headers[:-1]):
            first, last = h[-1], headers[i + 1][-1]
            zl = []
            for b in range(first, last):
                g0, m0 = bag[b]
                g1, m1 = bag[b + 1]
                gens = {o: _gen_value(o, a) for o, a in gen[g0:g1]}
                zl.append({'gens': gens, 'mods': mod[m0:m1], 'target': gens.get(terminal)})
            out.append(zl)
        return out

    phdr = [(h[0], h[1], h[2], h[3]) for h in tables[b'phdr']]
    pz = zones([(h[3],) for h in tables[b'phdr']], tables[b'pbag'], tables[b'pgen'], tables[b'pmod'], 41)
    iz = zones([(h[1],) for h in tables[b'inst']], tables[b'ibag'], tables[b'igen'], tables[b'imod'], 53)
    presets = [{'name': _name(n), 'program': p, 'bank': b, 'zones': z} for (n, p, b, _), z in zip(phdr[:-1], pz)]
    instruments = [{'name': _name(h[0]), 'zones': z} for h, z in zip(tables[b'inst'][:-1], iz)]
    samples = [{'name': _name(s[0]), 'start': s[1], 'end': s[2], 'loop': (s[3], s[4]), 'rate': s[5], 'root': s[6],
                'correction': s[7], 'link': s[8], 'type': s[9]} for s in tables[b'shdr'][:-1]]
    # A zone names an instrument or a sample by its index: one past the table is a defective bank, refused like the
    # others above rather than failing later wherever the zone is read.
    for what, owners, count in (('preset', presets, len(instruments)), ('instrument', instruments, len(samples))):
        for owner in owners:
            if any(z['target'] is not None and z['target'] >= count for z in owner['zones']):
                raise ValueError(f'{what} {owner["name"]!r} names an {"instrument" if what == "preset" else "sample"} '
                                 'the bank does not have: a structurally defective SoundFont')
    return {'path': str(path), 'info': info, 'presets': presets, 'instruments': instruments, 'samples': samples,
            'smpl': sdta[b'smpl'], 'sm24': sdta.get(b'sm24')}

def inventory(bank):
    """Per-preset summary: key coverage, velocity layers, sample rates/lengths and loops."""
    rows = []
    samples, instruments = bank['samples'], bank['instruments']
    for p in bank['presets']:
        keys, vels, used, rates, loops, seconds = set(), set(), set(), set(), 0, 0.0
        for pz in p['zones']:
            if pz['target'] is None or pz['target'] >= len(instruments):
                continue
            for iz in instruments[pz['target']]['zones']:
                sid = iz['target']
                if sid is None or sid >= len(samples):
                    continue
                lo, hi = iz['gens'].get(43, pz['gens'].get(43, (0, 127)))
                keys.update(range(lo, hi + 1))
                vels.add(iz['gens'].get(44, pz['gens'].get(44, (0, 127))))
                if sid not in used:
                    s = samples[sid]
                    used.add(sid)
                    rates.add(s['rate'])
                    seconds += (s['end'] - s['start']) / max(1, s['rate'])
                    loops += iz['gens'].get(54, 0) in (1, 3)
        rows.append({'preset': p['name'], 'bank': p['bank'], 'program': p['program'],
                     'keys': [min(keys), max(keys)] if keys else None, 'velocity_layers': len(vels),
                     'samples': len(used), 'sample_rates': sorted(rates), 'sample_seconds': round(seconds, 1),
                     'looped_zones': loops})
    return rows

def load_sample(bank, index):
    """Return one sample as float32 in [-1, 1] (16-bit plus optional sm24 low byte)."""
    s = bank['samples'][index]
    off, size = bank['smpl']
    if not 0 <= s['start'] <= s['end'] <= size // 2:
        raise ValueError('Sample outside smpl chunk')
    with open(bank['path'], 'rb') as f:
        f.seek(off + 2 * s['start'])
        data = np.frombuffer(f.read(2 * (s['end'] - s['start'])), dtype='<i2').astype(np.int32) << 8
        if bank['sm24']:
            f.seek(bank['sm24'][0] + s['start'])
            data |= np.frombuffer(f.read(s['end'] - s['start']), dtype='u1').astype(np.int32)
    return data.astype(np.float32) / 8388608.0

def _genbytes(gens):
    order = sorted(gens, key=lambda o: (0 if o == 43 else 1 if o == 44 else 3 if o in (41, 53) else 2, o))
    out = b''
    for o in order:
        v = gens[o]
        amount = (v[0] | (v[1] << 8)) if o in RANGE_GENS else (v & 0xFFFF)
        out += GENREC.pack(o, amount)
    return out

def write(path, name, samples, instruments, presets, comment='', copyright_notice='', software='music-production', new=False):
    """samples: [{'name','data' (float in [-1,1] or int16),'rate','root','correction','loop':(s,e)|None,'type','link'}]
    instruments: [{'name','global':{gen:val},'mods':[(src,dest,amount,amount_src,transform)],'zones':[{'gens':{...},'sample':i}]}]
    presets: [{'name','bank','program','global':{...},'zones':[{'gens':{...},'instrument':i}]}]
    An item's 'mods' go to its global zone and apply to all of its zones."""
    smpl, shdr = bytearray(), bytearray()
    for s in samples:
        d = np.asarray(s['data'])
        if d.dtype != np.int16:
            d = np.clip(np.round(d * 32767.0), -32768, 32767).astype('<i2')
        start = len(smpl) // 2
        smpl += d.astype('<i2').tobytes() + b'\0' * 92
        end = start + len(d)
        ls, le = s.get('loop') or (0, 0)
        shdr += SHDR.pack(s['name'][:19].encode('latin-1', 'replace'), start, end, start + ls, start + le, int(s['rate']),
                          int(s['root']), int(s.get('correction', 0)), int(s.get('link', 0)), int(s.get('type', 1)))
    shdr += SHDR.pack(b'EOS', 0, 0, 0, 0, 0, 0, 0, 0, 0)

    def tables(items, target_gen, header):
        hdr, bag, gen, mod = bytearray(), bytearray(), bytearray(), bytearray()
        nbag = ngen = nmod = 0
        for it in items:
            hdr += header(it, nbag)
            zl = ([{'gens': it.get('global') or {}, 'mods': it.get('mods', [])}] if it.get('global') or it.get('mods')
                  else []) + it['zones']
            for z in zl:
                bag += BAG.pack(ngen, nmod)
                for m in z.get('mods', []):
                    mod += MOD.pack(*m)
                    nmod += 1
                gens = dict(z['gens'])
                if 'sample' in z:
                    gens[53] = z['sample']
                if 'instrument' in z:
                    gens[41] = z['instrument']
                g = _genbytes(gens)
                gen += g
                ngen += len(g) // 4
                nbag += 1
        if ngen >= 0xFFFF or nbag >= 0xFFFF or nmod >= 0xFFFF:
            raise ValueError(f'SoundFont 2 index limit exceeded ({ngen} generators, {nbag} zones); split the bank')
        bag += BAG.pack(ngen, nmod)
        gen += GENREC.pack(0, 0)
        mod += MOD.pack(0, 0, 0, 0, 0)
        return hdr, bag, mod, gen, nbag

    ihdr, ibag, imod, igen, nib = tables(instruments, 53, lambda it, n: INST.pack(it['name'][:19].encode('latin-1', 'replace'), n))
    ihdr += INST.pack(b'EOI', nib)
    phdr, pbag, pmod, pgen, npb = tables(presets, 41, lambda it, n: PHDR.pack(it['name'][:19].encode('latin-1', 'replace'),
                                                                               it['program'], it['bank'], n, 0, 0, 0))
    phdr += PHDR.pack(b'EOP', 0, 0, npb, 0, 0, 0)

    def chunk(cid, data):
        data = bytes(data)
        return cid + struct.pack('<I', len(data)) + data + (b'\0' if len(data) & 1 else b'')

    def zstr(text):
        raw = text.encode('latin-1', 'replace') + b'\0'
        return raw + (b'\0' if len(raw) & 1 else b'')

    info = (b'INFO' + chunk(b'ifil', struct.pack('<HH', 2, 1)) + chunk(b'isng', zstr('EMU8000')) + chunk(b'INAM', zstr(name)) +
            chunk(b'ICOP', zstr(copyright_notice)) + chunk(b'ICMT', zstr(comment)) + chunk(b'ISFT', zstr(software)))
    sdta = b'sdta' + chunk(b'smpl', smpl)
    pdta = (b'pdta' + chunk(b'phdr', phdr) + chunk(b'pbag', pbag) + chunk(b'pmod', pmod) + chunk(b'pgen', pgen) +
            chunk(b'inst', ihdr) + chunk(b'ibag', ibag) + chunk(b'imod', imod) + chunk(b'igen', igen) + chunk(b'shdr', shdr))
    body = b'sfbk' + chunk(b'LIST', info) + chunk(b'LIST', sdta) + chunk(b'LIST', pdta)
    # Whole or not at all: a failed write leaves the file that was there; with `new`, only where nothing has taken the
    # name meanwhile (files.publish_new), as a bank the soundbank command found free (GPT Pro's fourth review of 0.4.0).
    with files.staged(path, new=new) as f:
        f.write(b'RIFF' + struct.pack('<I', len(body)) + body)
