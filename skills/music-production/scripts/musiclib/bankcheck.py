"""Whether FluidSynth may be given a SoundFont, checked before it ever is.

FluidSynth up to 2.6.2 keeps a modulator's 16-bit destination in 8 bits and uses it as an index into a voice's 63
generators, so a destination of 63 or more can write outside them (CVE-2026-111123).  Its fix (commit d0431d3f, released
in 2.6.3, the build the setup pins since 0.10) drops a modulator with `dest >= GEN_LAST`.  The check stays, since a
configuration may name an older FluidSynth (a system's: Ubuntu 24.04 ships 2.3.4), and the same bound refuses the bank here: every record of the
preset and instrument modulator tables and of the default modulators (INFO/DMOD, which FluidSynth imports the same way),
whether or not a part plays that preset, since the file is loaded whole.

The module is kept apart from sf2.py and audio.py so that adding it changes nothing a cached synthesis depends on
(render.SYNTHESIS): a Surge take is not repeatable, so an upgrade that invalidated the cache would change a piece's sound."""
import struct
from itertools import islice
from pathlib import Path

from .sf2 import MAX_RECORDS, MOD, _chunks

GEN_LAST = 63   # FluidSynth's count of generators (include/fluidsynth/gen.h): 0 to 62 exist
TABLES = {b'pdta': (b'pmod', b'imod'), b'INFO': (b'DMOD',)}   # the modulator tables of each list, all read by one importer
ORDER = (b'phdr', b'pbag', b'pmod', b'pgen', b'inst', b'ibag', b'imod', b'igen', b'shdr')   # what FluidSynth's process_pdta takes, in turn


def refuse_unsafe(path):
    """Raise ValueError for a SoundFont FluidSynth is not safe with.  Only the bank's chunk headers and its modulator tables
    are read.  A top-level chunk of odd size is refused too: RIFF pads it and FluidSynth's reader does not, so the two would
    find different tables after it (one inside INFO FluidSynth refuses itself).  So is a file that does not hold exactly
    what its RIFF header says: FluidSynth compares the two in 32 bits, so a file 4 GiB longer passes there, and its reader
    can then take tables this walk never reaches.  Under 4 GiB FluidSynth refuses such a file itself.  The first pdta list
    must begin with the nine tables in the order FluidSynth takes them: it counts the bytes left in 32 bits, so a table of
    over 2 GiB could otherwise stand past the list's end, where it reads on and this walk does not."""
    path = Path(path)
    with open(path, 'rb') as f:
        head = f.read(12)
        if head[:4] != b'RIFF' or head[8:12] != b'sfbk':
            raise ValueError(f'{path}: not a SoundFont 2 file')
        end, holds = 8 + struct.unpack('<I', head[4:8])[0], path.stat().st_size
        if end != holds:
            raise ValueError(f'{path}: its RIFF header says {end} bytes and the file holds {holds}, so it is not played; '
                             'it was cut short or has something after its end. Get a whole copy from its maker.')
        first_pdta = True
        for cid, off, size in _chunks(f, 12, end):
            if size & 1:
                raise ValueError(f'{path}: its {cid.decode("latin-1")!r} chunk has an odd size, which SoundFont 2 does not allow, so it is not played')
            if cid != b'LIST':
                continue
            f.seek(off)
            kind = f.read(4)
            tables = TABLES.get(kind)
            if tables is None:
                continue
            if kind == b'pdta' and first_pdta:
                first_pdta = False
                if tuple(sub for sub, _, _ in islice(_chunks(f, off + 4, off + size), len(ORDER))) != ORDER:
                    raise ValueError(f'{path}: its pdta list does not begin with the nine SoundFont 2 tables in their order, so FluidSynth could read '
                                     'other tables than this check does and it is not played. Choose another, or ask its maker for a corrected one.')
            for sub, table, length in _chunks(f, off + 4, off + size):
                if sub not in tables:
                    continue
                if length % MOD.size or length // MOD.size > MAX_RECORDS:
                    raise ValueError(f'{path}: bad {sub!r} table size')
                f.seek(table)
                for _, dest, *_rest in MOD.iter_unpack(f.read(length)):
                    if dest >= GEN_LAST:
                        raise ValueError(f'{path}: a modulator in its {sub.decode()} table has the destination {dest}, past the '
                                         f'{GEN_LAST} generators FluidSynth has. FluidSynth is not safe with such a bank '
                                         '(CVE-2026-111123), so it is not played; choose another, or ask its maker for a corrected one.')
