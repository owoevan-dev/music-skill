"""studio.py start: a new piece's folder with a compose.py that writes its song.json through musiclib.builder, and
that song.json, validated (0.8 steps 2.5 and 2.9: an important operation in one action, SWE-agent's second principle;
a valid, renderable skeleton for the agent to fill in, on the bus chain with rules 2, in place of make_example.py's
older room chain).  It writes the sections and parts it is given, one placeholder note a part (so the project renders
as it stands), and comments that say how notes are written; it composes nothing.  The same skeleton is built and
validated in memory first, so a preset it cannot name, an id compose.py cannot use or a note outside a part's keys is
refused before anything is written."""
import keyword
import subprocess
import sys
from pathlib import Path

from . import files

SCRIPTS = Path(__file__).resolve().parents[1]


def parse(sections, parts):
    """[(id, bars)] and [(id, role, instrument words or None)] from the command's --section ID:BARS and
    --part "ID ROLE [INSTRUMENT ...]"."""
    out_s, out_p = [], []
    for s in sections:
        ident, sep, bars = s.partition(':')
        if not sep or not ident.strip() or not bars.strip().isdigit() or int(bars) < 1:
            raise ValueError(f'--section {s!r}: a section is ID:BARS, e.g. verse:8')
        out_s.append((ident.strip(), int(bars)))
    for p in parts:
        words = p.split()
        if len(words) < 2:
            raise ValueError(f'--part {p!r}: a part is "ID ROLE [INSTRUMENT]", e.g. "piano harmony vcsl 0:0" or "lead melody flute"')
        if keyword.iskeyword(words[0]) or words[0] == 'song':
            raise ValueError(f'--part {p!r}: the id names the part\'s variable in compose.py, so it is neither a Python keyword nor "song"')
        out_p.append((words[0], words[1], ' '.join(words[2:]) or None))
    return out_s, out_p


def placeholder(part):
    """A drum part's kick (General MIDI 36), else the middle of the part's keys, else middle C: the key its preset has
    a sample for nearest that (a preset's keys may have holes), else the nearest inside the part's range."""
    track = part.track
    lo, hi = track.get('range', (0, 127))
    want = 36 if track.get('drums') else (lo + hi) // 2 if 'range' in track else 60
    keys = part.keys if part.keys is not None else range(lo, hi + 1)
    return min(keys, key=lambda k: (abs(k - want), k))


def script(title, sections, parts, tempo, meter, config):
    """The text of compose.py; `parts` are (id, role, instrument, placeholder pitch, its length in beats)."""
    q = lambda s: repr(str(s))
    lines = ['"""The composition script of this piece.  It writes song.json beside it: python compose.py',
             '',
             'studio.py start wrote this skeleton.  musiclib.builder does the bookkeeping (note ids, a performance entry for',
             'each note, each note checked against its part\'s keys as it is written, a save that validates); every note is',
             'yours.  Bars and beats count from 1; a beat is a quarter note; a pitch is a MIDI number or a name (C4 is 60)."""',
             'import sys',
             'from pathlib import Path',
             '',
             f'sys.path.insert(0, {q(SCRIPTS)})  # the skill\'s scripts on this machine',
             'from musiclib.builder import Song  # noqa: E402',
             '',
             f'song = Song({q(title)}, bars={sum(b for _, b in sections)}, tempo={tempo!r}, meter=({meter[0]}, {meter[1]}), tail_seconds=4'
             + (f', config={q(Path(config).resolve())})' if config else ')'),
             '']
    lines += [f'song.section({q(s)}, {b}, intent={q("what this section does")})' for s, b in sections]
    lines.append('')
    for ident, role, instrument, _, _ in parts:
        lines.append(f'{ident} = song.part({q(ident)}, {q(role)}' + (f', {q(instrument)})' if instrument else
                                                                       ")  # the default bank's program 0; name a preset: song.part(id, role, '<bank> <bank number>:<program>') or words (studio.py instruments)"))
    lines += ['',
              '# The notes: part.note(bar, beat, pitch, beats, velocity=80) and part.chord(bar, beat, [pitches], beats, velocity=80).',
              '# One placeholder note a part (a drum part\'s kick, 36, else the middle of its keys), so that the project renders as it',
              '# stands: replace them.  What else a part and a note take: the docstrings of musiclib/builder.py.']
    lines += [f'{ident}.note(1, 1, {pitch}, {length!r}, velocity=64)' for ident, _, _, pitch, length in parts]
    lines += ['',
              "song.save(Path(__file__).resolve().parent / 'song.json')",
              '']
    return '\n'.join(lines)


def start(folder, title, sections, parts, tempo=100.0, meter='4/4', config=None):
    """Write folder/compose.py and run it once, so that folder/song.json is there, validated."""
    folder = Path(folder)
    files.fresh(folder, 'start writes a new folder for the piece')
    try:
        beats, unit = (int(x) for x in meter.split('/'))
    except ValueError:
        raise ValueError(f'--meter {meter!r}: beats/beat unit, e.g. 4/4 or 6/8') from None
    sections, parts = parse(sections, parts)
    if config is None and any(instrument for _, _, instrument in parts):
        raise ValueError('a part\'s instrument is found in the configured banks: give --config <the configuration bootstrap.py wrote>')
    from .builder import Song
    from .model import validate
    probe = Song(title, bars=sum(b for _, b in sections), tempo=tempo, meter=(beats, unit), tail_seconds=4, config=config)
    for ident, bars in sections:
        probe.section(ident, bars, 'what this section does')
    placed, length = [], min(1, probe.beats_per_bar)   # a quarter note, or a bar of 1/8 or 3/16 whole
    for ident, role, instrument in parts:
        part = probe.part(ident, role, instrument)
        pitch = placeholder(part)
        part.note(1, 1, pitch, length, velocity=64)
        placed.append((ident, role, instrument, pitch, length))
    validate(probe.project)   # the skeleton compose.py writes, checked before anything is written
    try:
        folder.mkdir(parents=True)
    except FileExistsError:
        raise ValueError(f'{folder} was made by something else meanwhile; start writes a new folder for the piece') from None
    script_path = folder.absolute() / 'compose.py'
    # Written on a new name of its own and given its name only while nothing holds it: a file, or a link, put there after
    # the folder was made was written over or through (the whole review of 0.8)
    try:
        with files.staged(script_path, 'w', encoding='utf-8', newline='\n', new=True) as f:
            f.write(script(title, sections, placed, tempo, (beats, unit), config))
    except FileExistsError:
        raise ValueError(f'{script_path} was made by something else while start wrote it; it is left as it is') from None
    # The script by its absolute path, which no option begins like: a folder named "-cprint(1)" was read as Python's
    # -c option, and a relative one was looked for again inside itself (the Astra review of step 2)
    run = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=folder)
    if run.returncode:
        last = (run.stderr.strip().splitlines() or ['(no message)'])[-1]
        raise ValueError(f'{folder / "compose.py"} was written, but it stopped: {last}. Fix that line of the script, then run it: python compose.py')
    return files.joined([f'Wrote {folder / "compose.py"} and the song.json it writes ({len(parts)} parts, {len(sections)} sections, validated).',
                         'Write the notes in compose.py, run python compose.py, then studio.py validate and studio.py review.'])
