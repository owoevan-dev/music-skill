"""Whether FluidSynth may be given a SoundFont, checked before it ever is.

FluidSynth 2.6.1, the build pinned here, keeps a modulator's 16-bit destination in 8 bits and uses it as an index into a
voice's 63 generators, so a destination of 63 or more can write outside them (CVE-2026-111123).  Its fix (commit d0431d3f,
in no release yet) drops a modulator with `dest >= GEN_LAST`, and the same test refuses the bank here: every record of the
preset and instrument modulator tables, whether or not a part plays that preset, since the file is loaded whole.

The module is kept apart from sf2.py and audio.py so that adding it changes nothing a cached synthesis depends on
(render.SYNTHESIS): a Surge take is not repeatable, so an upgrade that invalidated the cache would change a piece's sound."""
import struct
from pathlib import Path

from .sf2 import MAX_RECORDS, MOD, _chunks

GEN_LAST = 63   # FluidSynth's count of generators (include/fluidsynth/gen.h): 0 to 62 exist


def refuse_unsafe(path):
    """Raise ValueError for a SoundFont FluidSynth is not safe with.  Only the bank's chunk headers and its two modulator
    tables are read.  A chunk of odd size is refused too: RIFF pads it and FluidSynth's reader does not, so the two would
    find different tables after it."""
    path = Path(path)
    with open(path, 'rb') as f:
        head = f.read(12)
        if head[:4] != b'RIFF' or head[8:12] != b'sfbk':
            raise ValueError(f'{path}: not a SoundFont 2 file')
        for cid, off, size in _chunks(f, 12, min(path.stat().st_size, 8 + struct.unpack('<I', head[4:8])[0])):
            if size & 1:
                raise ValueError(f'{path}: its {cid.decode("latin-1")!r} chunk has an odd size, which SoundFont 2 does not allow, so it is not played')
            if cid != b'LIST':
                continue
            f.seek(off)
            if f.read(4) != b'pdta':
                continue
            for sub, table, length in _chunks(f, off + 4, off + size):
                if sub not in (b'pmod', b'imod'):
                    continue
                if length % MOD.size or length // MOD.size > MAX_RECORDS:
                    raise ValueError(f'{path}: bad {sub!r} table size')
                f.seek(table)
                for _, dest, *_rest in MOD.iter_unpack(f.read(length)):
                    if dest >= GEN_LAST:
                        raise ValueError(f'{path}: a modulator in its {sub.decode()} table has the destination {dest}, past the '
                                         f'{GEN_LAST} generators FluidSynth has. FluidSynth is not safe with such a bank '
                                         '(CVE-2026-111123), so it is not played; choose another, or ask its maker for a corrected one.')
