"""SFZ files read as a documented subset (0.8 step 3.2; the SFZ format documentation, sfzformat.com): the regions of
SFZ 1 with their key and velocity ranges and crossfades, pitch centre, tune and transpose, volume, offset and end, loop
mode and points, amplitude envelope, and group and off_by, under the headers and directives that carry their defaults
(<control> default_path, <global>, <master>, <group>, #define, #include; <master> is ARIA's level between <global> and
<group>, found in the official legato tutorial's programs).  Every other header and opcode is counted and named as
not used: soundbank.py sfz writes them into its receipt, so nothing of a region's sound is dropped without a word.

Read as the documentation has it (each rule found missing by the third outside review of 0.8, or in its pages):
- a header or an opcode may follow another on a line with or without a space between;
- a comment is // to the line's end or /* ... */, whichever begins first (a /* inside a line comment starts nothing);
- `key` sets lokey, hikey and pitch_keycenter where it stands; a pitch_keycenter its own header sets wins (ARIA);
- default_path holds for the regions after its <control> until the next <control>, which resets it (ARIA);
- an #include and a sample are named from the main file's folder, not an included file's ("the SFZ is interpreted as
  if it was in the main SFZ file's path"); both must lie inside the root, reached through no link or junction.

The format's site states that SFZ files may be created, used and distributed free of charge for free or commercial
applications; this reads such text and hands the regions to the bank builder."""
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path, PurePosixPath

from . import files

HEADERS = ('control', 'global', 'master', 'group', 'region')
REGION = {'sample', 'lokey', 'hikey', 'key', 'pitch_keycenter', 'lovel', 'hivel', 'tune', 'transpose', 'volume', 'offset',
          'end', 'loop_mode', 'loop_start', 'loop_end', 'ampeg_delay', 'ampeg_attack', 'ampeg_hold', 'ampeg_decay',
          'ampeg_sustain', 'ampeg_release', 'group', 'off_by', 'xfin_lokey', 'xfin_hikey', 'xfout_lokey', 'xfout_hikey',
          'xfin_lovel', 'xfin_hivel', 'xfout_lovel', 'xfout_hivel'}
ALIASES = {'loopmode': 'loop_mode', 'loopstart': 'loop_start', 'loopend': 'loop_end'}   # SFZ 1's spellings of v2's names
CONTROL = {'default_path'}
MAX_INCLUDES = 32          # files an SFZ may pull in, and their depth: an #include of itself stops here
MAX_BYTES = 4_000_000      # the SFZ text with its includes, and again once its #define names are replaced
NAMES = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}


def key(value, where):
    """A MIDI key from a number or an SFZ note name (c4 is 60; c#4 and db4 are 61)."""
    v = value.strip().lower()
    if re.fullmatch(r'[+-]?\d+', v):
        k = int(v)
    else:
        m = re.fullmatch(r'([a-g])([#b]?)(-?\d)', v)
        if not m:
            raise ValueError(f'{where}: {value!r} is no key (a MIDI number or a note name such as c4, c#4 or eb3)')
        k = 12 * (int(m[3]) + 1) + NAMES[m[1]] + {'#': 1, 'b': -1, '': 0}[m[2]]
    if not 0 <= k <= 127:
        raise ValueError(f'{where}: key {value!r} is outside 0-127')
    return k


def below(root, start, name, what, listed=None):
    """root/start/name walked one name at a time from the root: '..' goes back up, never above the root, and no name
    on the way is a link or a junction (CWE-59), so nothing the file names is read from outside the root.  Each name is
    taken as its folder lists it (spelled)."""
    text = name.replace('\\', '/')
    if text.startswith('/') or ':' in text:   # a drive, or on Windows a file's stream (a:b.wav)
        raise ValueError(f'{what} {name!r}: a path from a drive\'s root, or with a colon, is not taken; name it from the .sfz file\'s folder')
    listed = {} if listed is None else listed
    path = Path(root)
    for part in (*start, *PurePosixPath(text).parts):
        if part == '..':
            if path == Path(root):
                raise ValueError(f'{what} {name!r} leads out of --root {root}')
            path = path.parent
        elif part not in ('', '.'):
            path = path / spelled(path, part, listed)
            if files.linked(path):
                raise ValueError(f'{what} {name!r}: {path.relative_to(root).as_posix()} is a link or a junction; the build opens none below its root')
    return path


def _fold(name):
    return unicodedata.normalize('NFC', name).casefold()


def spelled(folder, part, listed):
    """`part` as `folder` lists it: itself where it is listed, else the one name there that differs from it only in case
    or Unicode form, else itself (then no file is found by it).  SFZ files made where case does not count name PIANO.WAV
    for Piano.wav: Windows and macOS find it, and the build, which looks a sample up by its listed name, did not (the
    whole review of 0.8); taken so on every system, an instrument reads alike everywhere.  `listed` keeps each folder's
    names for the file being read."""
    names = listed.get(folder)
    if names is None:
        try:
            entries = os.listdir(folder)
        except OSError:   # no folder there: the name stays as written and is reported where it is used
            entries = []
        folded = {}
        for entry in entries:
            folded.setdefault(_fold(entry), []).append(entry)
        names = listed[folder] = (set(entries), folded)
    exact, folded = names
    if part in exact:
        return part
    alike = folded.get(_fold(part), [])
    return alike[0] if len(alike) == 1 else part


def _text(path, root, start, seen, size, listed):
    """The file's text with each #include pulled in (named from the main file's folder, `start` below the root) and
    comments left out; the size is counted before a file is read, so none is taken whole to learn it is too large."""
    if len(seen) >= MAX_INCLUDES:
        raise ValueError(f'{path.name}: more than {MAX_INCLUDES} SFZ files through #include (or one that includes itself)')
    size[0] += path.stat().st_size
    if size[0] > MAX_BYTES:
        raise ValueError(f'{path.name}: more than {MAX_BYTES:,} bytes of SFZ text with its includes')
    seen.append(path)
    # // to the line's end, or /* ... */, whichever begins first; a block comment keeps its line breaks
    text = re.sub(r'//[^\n]*|/\*.*?\*/', lambda m: '' if m[0].startswith('//') else ' ' + '\n' * m[0].count('\n'),
                  path.read_bytes().decode('utf-8', 'replace'), flags=re.S)
    out = []
    for line in text.split('\n'):
        m = re.match(r'\s*#include\s+"([^"]+)"', line)
        if not m:
            out.append(line)
            continue
        target = below(root, start, m[1], f'{path.name}: #include', listed)
        if not target.is_file():
            raise ValueError(f'{path.name}: #include "{m[1]}" names no file')
        out.append(_text(target, root, start, seen, size, listed))
    return '\n'.join(out)


def _tokens(text):
    """('h', header) and ('o', opcode, value) in order, each #define's $name replaced in the lines after it (the text
    then bounded again: a chain of names doubling at each step grew a 391-byte file a thousandfold); a value runs to
    the next opcode or header (a sample's path may hold spaces)."""
    defines, tokens, grown = {}, [], 0
    for line in text.split('\n'):
        m = re.match(r'\s*#define\s+(\$\w+)\s+(.*?)\s*$', line)
        if m:
            defines[m[1]] = m[2]
            continue
        for name in sorted(defines, key=len, reverse=True):   # the longest first ($PIANO before $PIAN)
            n = line.count(name)
            if n and len(line) + n * (len(defines[name]) - len(name)) > MAX_BYTES - grown:
                raise ValueError(f'more than {MAX_BYTES:,} characters of SFZ text once its #define names are replaced')
            line = line.replace(name, defines[name])
        grown += len(line)   # the text so far, replaced: lines after a grown one count too (3.9 MB made 7.8: the fourth review)
        if grown > MAX_BYTES:
            raise ValueError(f'more than {MAX_BYTES:,} characters of SFZ text once its #define names are replaced')
        marks = sorted([(mm.start(), mm.end(), 'h', mm[1]) for mm in re.finditer(r'<(\w+)>', line)]
                       + [(mm.start(), mm.end(), 'o', mm[1]) for mm in re.finditer(r'(?:(?<=[\s>])|^)(\w+)=', line)])
        for k, (at, after, kind, name) in enumerate(marks):
            if kind == 'h':
                tokens.append(('h', name.lower(), None))
            else:
                tokens.append(('o', name.lower(), line[after:marks[k + 1][0] if k + 1 < len(marks) else len(line)].strip()))
    return tokens


def read(path, root):
    """An SFZ file's regions, each with the opcodes of the <global>, <master> and <group> in force where it stands under
    its own (a later level wins; a <global> starts the masters and groups afresh, a <master> the groups), `sample` the
    path below `root` it names (from the
    main file's folder and the default_path in force); and what was not used:
    {'regions': [...], 'not_used': {'headers': {...}, 'opcodes': {...}}}.  The file itself lies inside `root`."""
    # the file named, and each folder between the root and it, no link (the root itself may be one, resolved once): a
    # link resolved first was never seen (the fourth review), nor one behind a root resolved before it came here (the
    # whole review: the command resolved it), so the file is named from the root as given or as resolved, or refused
    given, top = Path(path).absolute(), Path(root).absolute()
    if files.linked(given):
        raise ValueError(f'{given.name} is a link or a junction; give the .sfz file itself')
    real = top.resolve()
    base = next((b for b in (top, real) if given.is_relative_to(b)), None)
    if base is None:
        raise ValueError(f'{given.name} lies outside --root {top}: name the .sfz file by a path inside the root, which holds it and '
                         'everything it names')
    for p in list(given.relative_to(base).parents)[:-1]:
        if files.linked(base / p):
            raise ValueError(f'{given.name}: {p.as_posix()} is a link or a junction; the build opens none below its root')
    root, path = real, given.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'{path.name} lies outside --root {root}: the root holds the .sfz file and everything it names')
    start = path.parent.relative_to(root).parts
    listed = {}   # each folder's names, for the names the file gives in another case (spelled)
    control, glob, master, group, region, regions, current, own = {}, {}, {}, {}, None, [], None, set()
    not_headers, not_opcodes = Counter(), Counter()
    for kind, name, value in _tokens(_text(path, root, start, [], [0], listed)):
        if kind == 'h':
            if region is not None:
                regions.append(region)
                region = None
            current, own = (name if name in HEADERS else 'skip'), set()
            if current == 'skip':
                not_headers[name] += 1
            elif name == 'control':
                control = {}
            elif name == 'global':
                glob, master, group = {}, {}, {}
            elif name == 'master':
                master, group = {}, {}
            elif name == 'group':
                group = {}
            elif name == 'region':
                region = {**glob, **master, **group, 'default_path': control.get('default_path', '')}
            continue
        name = ALIASES.get(name, name)
        if current == 'control' and name in CONTROL:
            control[name] = value
        elif current in ('global', 'master', 'group', 'region') and name in REGION:
            level = {'global': glob, 'master': master, 'group': group, 'region': region}[current]
            if name == 'key':
                level.update(lokey=value, hikey=value, **({} if 'pitch_keycenter' in own else {'pitch_keycenter': value}))
            else:
                level[name] = value
            own.add(name)
        else:
            not_opcodes[name] += 1
    if region is not None:
        regions.append(region)
    for k, r in enumerate(regions):
        if not r.get('sample'):
            raise ValueError(f'{path.name}: region {k + 1} names no sample')
        r['sample'] = below(root, start, r.pop('default_path') + r['sample'], f'{path.name}, region {k + 1}: sample', listed)
    return {'regions': regions, 'not_used': {'headers': dict(not_headers), 'opcodes': dict(not_opcodes)}}
