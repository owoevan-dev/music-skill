"""studio.py start: a new piece's folder with a compose.py that writes its song.json through musiclib.builder, and
that song.json, validated (0.8 steps 2.5 and 2.9: an important operation in one action, SWE-agent's second principle;
a valid, renderable skeleton for the agent to fill in, on the bus chain with rules 2, in place of make_example.py's
older room chain).  It writes the sections and parts it is given, one placeholder note a part (so the project renders
as it stands), and comments that say how notes are written; it composes nothing.  The same skeleton is built and
validated in memory first, so a preset it cannot name, an id compose.py cannot use or a note outside a part's keys is
refused before anything is written."""
import keyword
import os
from pathlib import Path

from . import files

SCRIPTS = Path(__file__).resolve().parents[1]


def behind_script(project):
    """A line for a command that read `project`, where the compose.py beside it was saved after it; else None.  The
    script writes song.json, and a run of it that fails leaves the old one, which review, round and render then read
    without a word (six of 23 runs of 0.9.1).  Said and not refused, since a project from elsewhere must not be pushed
    into running the script it came with."""
    project = Path(project)
    try:
        if os.path.normcase(project.name) != os.path.normcase('song.json') or project.with_name('compose.py').stat().st_mtime_ns <= project.stat().st_mtime_ns:
            return None
    except OSError:
        return None
    return ('Note: compose.py was saved after song.json, so this read the project as it was before that edit. If the script '
            'is yours, run it again and see it finish (a run that fails leaves the old song.json); one that came with a '
            'project from elsewhere is not run unasked.')


# A part's sound written as `studio.py audition --sounds` writes one (0.10): any sound a part can play, beside the words
# that find a SoundFont preset.  Three runs of 0.9.1's gallery wrote their Surge and synth parts into compose.py by hand.
FORMS = ('surge:', 'synth:', 'soundfont:')


def sound_form(ident, instrument):
    """A part's instrument written as audition --sounds writes a sound (surge:<id>[+setting], synth:<preset>,
    soundfont:<bank>:<bank number>:<program>), checked against the lists: ('surge' or 'synth', the part's fields for its
    engine), or ('soundfont', '<bank> <bank number>:<program>'); None for words that find a SoundFont preset; and
    ('unknown', the reason with the nearest names) for anything else that begins like one of those forms (a Surge patch
    or a built-in preset that is not there, a SoundFont sound without its bank or numbers, a space in it).  start looks
    an unknown one up as the words it was in 0.9.3, and a SoundFont sound whose bank or preset is not configured too, and
    refuses only where that finds nothing either: a configured preset may be named "synth:zed tone" or "soundfont:odd",
    and 0.9.3 found it (the Astra reviews of 0.10's design and of its step 3)."""
    if not instrument or not instrument.startswith(FORMS):
        return None
    kind = instrument.split(':', 1)[0]
    if len(instrument.split()) > 1:
        return 'unknown', f'part {ident}: {instrument!r}: a sound named as {kind}: is one word, with no space'
    from .audition import parse_sound
    try:
        sound = parse_sound(instrument)
    except ValueError as e:
        return 'unknown', f'part {ident}: {e}{nearest(kind, instrument)}'
    if sound[0] == 'surge':
        return 'surge', {'surge': {'preset': sound[1], **dict(sound[2] if len(sound) > 2 else ())}}
    if sound[0] == 'synth':
        return 'synth', {'synth': {'preset': sound[1]}}
    if not sound[1]:   # "soundfont::0:41" read as the words " 0:41" took whichever bank had that preset
        return 'unknown', f'part {ident}: {instrument!r}: a SoundFont sound names its bank, soundfont:<bank>:<bank number>:<program>'
    return 'soundfont', f'{sound[1]} {sound[2]}:{sound[3]}'


def nearest(kind, instrument):
    """'; the nearest: ...' for a Surge patch or built-in preset that is not there, else ''."""
    import difflib
    from . import surge, synth
    asked = instrument.split(':', 1)[1].split('+')[0]
    names = [*surge.presets()['presets'], *surge.catalog()] if kind == 'surge' else list(synth.presets()) if kind == 'synth' else []
    close = difflib.get_close_matches(asked, names, n=3, cutoff=.6)
    return f'; the nearest: {", ".join(close)}' if close else ''


def probe_pitch(engine, fields):
    """Where a Surge or synth part's placeholder note goes: the pitch the catalog's probe note is written at (C2 for basses,
    C5 for leads, plucks and brass, C4 otherwise, as scripts/surge_catalog.py plays its probe), else middle C.  Written
    there, a patch with a `transpose` plays it where the renderer moves its notes, as every note of the part."""
    if engine != 'surge':
        return 60
    from . import surge
    entry = surge.entry(fields['surge']['preset']) or {}
    measured = entry.get('measured', {}).get('probe_pitch')
    return measured if isinstance(measured, int) else {'bass': 36, 'lead': 72, 'pluck': 72, 'brass': 72}.get(entry.get('role'), 60)


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


def placeholder(part, config=None):
    """A drum part's kick (General MIDI 36), else the middle of the part's keys, else middle C: the key its preset has
    a sample for nearest that (a preset's keys may have holes), else the nearest inside the part's range; and a velocity
    its preset sounds that key at, 64 where it can (a preset may give a key a sample at some velocities only: a
    placeholder at 64 on one of 90-127 was silent, and the render refuses a silent part: the review of 0.8.0)."""
    track = part.track
    lo, hi = track.get('range', (0, 127))
    want = 36 if track.get('drums') else (lo + hi) // 2 if 'range' in track else 60
    keys = part.keys if part.keys is not None else range(lo, hi + 1)
    key = min(keys, key=lambda k: (abs(k - want), k))
    velocity = 64
    if part.preset is not None and config is not None:
        from .instruments import zones_of
        played = part._moved.get(key, key)   # the key it sounds on, through the part's key_map
        patch = part.preset['patch']
        ranges = [v for k, v in zones_of(config, part.preset['bank'], patch['bank'], patch['program']) if k[0] <= played <= k[1]]
        if ranges and not any(a <= velocity <= b for a, b in ranges):
            a, b = min(ranges, key=lambda r: min(abs(r[0] - velocity), abs(r[1] - velocity)))
            velocity = a if a > velocity else b
    return key, velocity


def spelled(path):
    """A path as compose.py names it: from the user's home where it lies there, so that a script shared with others
    names no account (it named the whole path: the review of 0.8.0), else as it is.  Either way it is this machine's."""
    path = Path(path).resolve()
    try:
        return f'Path.home() / {path.relative_to(Path.home().resolve()).as_posix()!r}'
    except ValueError:
        return f'Path({path.as_posix()!r})'


def script(title, sections, parts, tempo, meter, config):
    """The text of compose.py; `parts` are (id, role, instrument, placeholder pitch, its length in beats, its velocity)."""
    q = lambda s: repr(str(s))
    lines = ['"""The composition script of this piece.  It writes song.json beside it: python compose.py',
             '',
             'studio.py start wrote this skeleton.  musiclib.builder does the bookkeeping (note ids, a performance entry for',
             'each note, each note checked against its part\'s keys as it is written, a save that validates); every note is',
             'yours.  Bars and beats count from 1; a beat is a quarter note; a pitch is a MIDI number or a name (C4 is 60)."""',
             'import os',
             'import sys',
             '',
             "# Python looks first in a script's own folder, so a file there named as a library (json.py, pathlib.py) would run",
             '# in its place: this folder leaves the import path before anything else is imported, by where it really is (run',
             '# through a link, the script is found in the folder the link leads to).',
             'HERE = {os.path.normcase(os.path.realpath(d)) for d in (os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.realpath(__file__)))}',
             'sys.path[:] = [p for p in sys.path if os.path.normcase(os.path.realpath(p or os.curdir)) not in HERE]',
             'from pathlib import Path  # noqa: E402',
             '',
             '# The skill and its configuration on this machine: a copy of this script elsewhere names its own.',
             f'SKILL = {spelled(SCRIPTS)}',
             'sys.path.insert(0, str(SKILL))',
             'from musiclib.builder import Song  # noqa: E402',
             '',
             f'song = Song({q(title)}, bars={sum(b for _, b in sections)}, tempo={tempo!r}, meter=({meter[0]}, {meter[1]}), tail_seconds=4'
             + (f', config={spelled(config)})' if config else ')'),
             '']
    lines += [f'song.section({q(s)}, {b}, intent={q("what this section does")})' for s, b in sections]
    lines += ['',
              '# The harmony, written once and read by every part: song.harmony(bar, beat, symbol) writes a chord into the project,',
              '# where review reads the pitched parts\' notes against it.  song.changes() gives the chords in order as (bar, beat, symbol,',
              '# beats) for a part\'s own loop, and song.chord_at(bar, beat) the chord sounding at a place, so that no part is',
              '# written from a chord list of its own.',
              "# song.harmony(1, 1, 'Cmaj7')",
              '']
    for ident, role, instrument, _, _, _ in parts:
        if isinstance(instrument, tuple):   # a Surge or synth part: its engine and the fields that name its sound
            engine, fields = instrument
            lines.append(f'{ident} = song.part({q(ident)}, {q(role)}, engine={q(engine)}, {engine}={fields[engine]!r})')
            continue
        lines.append(f'{ident} = song.part({q(ident)}, {q(role)}' + (f', {q(instrument)})' if instrument else
                                                                       ")  # the default bank's program 0; name a preset: song.part(id, role, '<bank> <bank number>:<program>') or words (studio.py instruments)"))
    lines += ['',
              "# A synthesizer part: song.part('pad', 'harmony', engine='surge', surge={'preset': 'juno_60_strings'}), or engine='synth',",
              "# synth={'preset': 'warm_pad'} (studio.py sounds finds a Surge patch; references/synth-presets.json lists the built-in ones).",
              '# The notes: part.note(bar, beat, pitch, beats, velocity=80) and part.chord(bar, beat, [pitches], beats, velocity=80).',
              '# One placeholder note a part (a drum part\'s kick, 36, else the middle of its keys, at a velocity its preset sounds), so',
              '# that the project renders as it stands: replace them.  What else a part and a note take: the docstrings of musiclib/builder.py.']
    lines += [f'{ident}.note(1, 1, {pitch}, {length!r}, velocity={velocity})' for ident, _, _, pitch, length, velocity in parts]
    from .builder import Song
    lines += ['',
              "# The project's other fields (schema.md) are written into song.project before the save: plan, style, association",
              f"# (studio.py words), decisions, loop.  song.project['mix'] starts as {Song('', 1).project['mix']!r}.",
              "song.save(Path(__file__).resolve().parent / 'song.json')",
              '']
    return '\n'.join(lines)


def start(folder, title, sections, parts, tempo=100.0, meter='4/4', config=None):
    """Write folder/compose.py and the song.json it writes: the same skeleton, validated and saved by start, which does not
    run the script (nothing in the folder is imported or run).  The folder may hold the
    piece's brief and words already (SKILL.md's steps 1 and 2 come first: a folder that was there was refused, the review
    of 0.8.0), but no compose.py or song.json; it is made where it is missing.  With a configuration, a part that names no
    instrument plays the default bank's program 0 (its kit at 128:0 for a drum part), written out so that it is checked."""
    folder = Path(folder)
    files.program_folder(folder)   # the script runs in its folder: one Windows starts nothing in is refused before anything is written
    if files.occupied(folder) and not files.real_folder(folder):
        raise ValueError(f'{folder} is a file or a link; start writes into a folder of its own (give the folder itself)')
    for name in ('compose.py', 'song.json'):
        files.fresh(folder / name, f'start writes a piece\'s first {name} and changes none: edit the one there, or start in another folder')
    try:
        beats, unit = (int(x) for x in meter.split('/'))
    except ValueError:
        raise ValueError(f'--meter {meter!r}: beats/beat unit, e.g. 4/4 or 6/8') from None
    sections, parts = parse(sections, parts)
    forms = {ident: sound_form(ident, instrument) for ident, _, instrument in parts}   # malformed sounds refused here, before anything is made
    unknown = next((form[1] for form in forms.values() if form and form[0] == 'unknown'), None)
    if config is None and unknown:
        raise ValueError(unknown)
    if config is None and any(instrument and (forms[ident] is None or forms[ident][0] == 'soundfont') for ident, _, instrument in parts):
        raise ValueError('a part\'s instrument is found in the configured banks: give --config <the configuration bootstrap.py wrote> '
                         '(a Surge patch or a built-in synth preset needs none: surge:<id>, synth:<preset>)')
    from .builder import Song
    from .model import validate
    probe = Song(title, bars=sum(b for _, b in sections), tempo=tempo, meter=(beats, unit), tail_seconds=4, config=config)
    for ident, bars in sections:
        probe.section(ident, bars, 'what this section does')
    placed, length = [], min(1, probe.beats_per_bar)   # a quarter note, or a bar of 1/8 or 3/16 whole
    for ident, role, instrument in parts:
        form = forms[ident]
        if form is not None and form[0] in ('surge', 'synth'):
            engine, fields = form
            part = probe.part(ident, role, engine=engine, **fields)
            pitch = probe_pitch(engine, fields)
            part.note(1, 1, pitch, length, velocity=64)
            placed.append((ident, role, form, pitch, length, 64))
            continue
        if form is not None and form[0] in ('soundfont', 'unknown'):
            # soundfont:<bank>:<n>:<program> as the bank words a part takes; where that is not configured, or the form is
            # no sound at all, the words it was in 0.9.3, which found a configured preset so named (a part 0.9.3 took is
            # taken: the Astra review of step 3)
            why, named = form[1], instrument
            if form[0] == 'soundfont':
                try:
                    part = probe.part(ident, role, form[1])
                    why, named = None, form[1]
                except ValueError as e:
                    why = f'part {ident}: {e}'
            if why is not None:
                try:
                    part = probe.part(ident, role, instrument)
                except ValueError as e:
                    raise ValueError(f'{why}; as words for a configured preset: {e}') from None
            pitch, velocity = placeholder(part, config)
            part.note(1, 1, pitch, length, velocity=velocity)
            placed.append((ident, role, named, pitch, length, velocity))
            continue
        # with a configuration, the default bank's preset the part would play, found and checked as a named one (a part
        # that named none was given middle C whatever that preset had: the review of 0.8.0)
        named = instrument or (f'default {128 if role == "drums" else 0}:0' if config else None)
        try:
            part = probe.part(ident, role, named)
        except ValueError as e:
            if instrument or not config:
                raise
            raise ValueError(f'part {ident} names no instrument, so it plays the default bank\'s {"kit" if role == "drums" else "program 0"} '
                             f'({named!r}): {e}; name a preset for it') from None
        pitch, velocity = placeholder(part, config)
        part.note(1, 1, pitch, length, velocity=velocity)
        placed.append((ident, role, named, pitch, length, velocity))
    validate(probe.project)   # the skeleton compose.py writes, checked before anything is written
    if not files.real_folder(folder):
        try:
            folder.mkdir(parents=True)
        except FileExistsError:
            raise ValueError(f'{folder} was made by something else meanwhile; start writes into a folder of its own') from None
    script_path = folder.absolute() / 'compose.py'
    # Written on a new name of its own and given its name only while nothing holds it: a file, or a link, put there after
    # the folder was made was written over or through (the whole review of 0.8)
    try:
        with files.staged(script_path, 'w', encoding='utf-8', newline='\n', new=True) as f:
            f.write(script(title, sections, placed, tempo, (beats, unit), config))
    except FileExistsError:
        raise ValueError(f'{script_path} was made by something else while start wrote it; it is left as it is') from None
    # The first song.json is the skeleton compose.py writes, validated above, saved here rather than by running compose.py:
    # Python runs a script with its own folder first on the import path, so a module file in the piece's folder (a
    # pathlib.py) was imported before the skill's (GPT Pro's second full review of 0.10); the script writes the same
    # project.  The save makes song.json but replaces nothing: start found none, so one there now was made by something else
    # after start looked (it was taken for the script's own and replaced: the Astra review of the fixes for 0.8.0).
    from .model import save_json
    try:
        save_json(folder.absolute() / 'song.json', probe.project, new=True)
    except FileExistsError:
        raise ValueError(f"{folder / 'compose.py'} was written, but {folder / 'song.json'} was made by something else while the song was saved: "
                         "it is left as it is, and running compose.py would replace it, so move it aside first or start in another folder") from None
    return files.joined([f'Wrote {folder / "compose.py"} and the song.json it writes ({len(parts)} parts, {len(sections)} sections, validated).',
                         'Write the notes in compose.py, run python compose.py, then studio.py validate and studio.py review.'])
