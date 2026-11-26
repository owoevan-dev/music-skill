"""The bookkeeping of a composition script: a song with its clock and sections; parts that take their
instrument from the configured banks (`studio.py instruments`), so that bank, program and keys are not guessed; notes
placed by bar and beat, each with a stable id and its performance entry made on the spot and checked against its
part's range as it is written; and a save that validates.  It composes nothing: every note, chord, line and groove is
the script's (musiclib.blocks stays the opt-in for grooves).  The project file stays the source of truth: anything the
builder does not cover is written into `song.project` (plan, style, association, decisions, loop, a changed mix:
schema.md), and old projects and scripts work as they did.  A new song's mix is the bus chain with rules 2 at -14 LUFS.

The six published examples each re-implemented this in 358 to 1,219 lines (track dictionaries, note ids, a
performance entry per note), and in our tests of 0.7 the fields agents guessed (about 10 failures) and their notes
outside a range (7) arose there (a guardrail at the moment of writing: SWE-agent, Yang et al. 2024).

    from musiclib.builder import Song
    song = Song('Harbour Lights', bars=16, tempo=96, config='config.json')
    song.section('verse', 8, 'the tune alone')
    song.section('chorus', 8, 'the tune with the band')
    piano = song.part('piano', 'harmony', 'vcsl 0:0')    # bank and patch, or words: 'steinway'
    piano.chord(1, 1, ['C3', 'E3', 'G3'], 4, velocity=64)
    lead = song.part('lead', 'melody', 'iowa_winds flute')
    lead.note(1, 2, 'E5', 1.5)                         # bar 1, beat 2, for a beat and a half
    song.save('song.json')

Bars and beats are counted from 1, as players count them; a beat is a quarter note, as everywhere in the project, so
a bar of 6/8 holds beats 1 to 3.5.  A pitch is a MIDI number or a name (C4 is 60, F#3, Bb2)."""
import math
import os
import re
from pathlib import Path

from . import files
from .model import TPQ, check_meter, key_map_pitches, save_json, validate

START_SAVE = 'MUSIC_SKILL_START_SAVE'   # a save that replaces nothing (studio.py start set it for its run of compose.py before 0.10)
NAMES =('C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B')
PCS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def name(pitch):
    return f'{NAMES[pitch % 12]}{pitch // 12 - 1}'


def pitch_of(value, where):
    """A MIDI pitch from a number or a name (A-G, an optional # or b, an octave: C-1 is 0, G9 is 127)."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f'{where}: a pitch is a MIDI number or a name such as C4, F#3 or Bb2, got {value!r}')
    if isinstance(value, int):
        if not 0 <= value <= 127:
            raise ValueError(f'{where}: MIDI pitch {value} is outside 0-127')
        return value
    m = re.fullmatch(r'([A-Ga-g])([#b]?)(-?[0-9]+)', value.strip())
    if not m:
        raise ValueError(f'{where}: {value!r} is no note name; write it as C4, F#3 or Bb2 (C4 is MIDI 60)')
    k = 12 * (int(m.group(3)) + 1) + PCS[m.group(1).upper()] + {'#': 1, 'b': -1, '': 0}[m.group(2)]
    if not 0 <= k <= 127:
        raise ValueError(f'{where}: {value} is outside the MIDI range C-1 to G9')
    return k


class Song:
    """A project being written: `song.project` is the dictionary saved."""

    def __init__(self, title, bars, tempo=120, meter=(4, 4), tail_seconds=4, config=None, **fields):
        self.config = config
        # a script that writes a song prints what it likes of it: a name its console cannot encode comes out as an
        # escape and does not stop the script (a chord quality's sign on a Traditional Chinese Windows console)
        files.escape_unprintable()
        check_meter(list(meter))   # before the beat unit divides anything (4/0)
        self.project = {'schema': 'music-production/v1', 'title': title, 'version': '1.0',
                        'clock': {'bars': bars, 'meter': list(meter), 'tail_seconds': tail_seconds,
                                  'tempo': [[0, tempo]] if isinstance(tempo, (int, float)) else [list(x) for x in tempo]},
                        'sections': [], 'tracks': [], 'mix': {'chain': 'bus', 'rules': 2, 'target_lufs': -14}, **fields}
        self.beats_per_bar = meter[0] * 4 / meter[1]

    def section(self, ident, bars, intent=None):
        """The next section, from where the one before it ends."""
        start = sum(s['bars'] for s in self.project['sections'])
        self.project['sections'].append({'id': ident, 'start_bar': start, 'bars': bars, **({'intent': intent} if intent else {})})
        return self

    def _place(self, bar, beat, writing=False):
        if not (isinstance(bar, int) and not isinstance(bar, bool) and 1 <= bar <= self.project['clock']['bars']):
            raise ValueError(f'bar {bar!r}: the piece has bars 1 to {self.project["clock"]["bars"]}')
        # a chord is written to within a tick of the next bar, as validate takes its place; a place asked for is any
        # a note may be written on
        if isinstance(beat, bool) or not isinstance(beat, (int, float)) or not 1 <= beat < 1 + self.beats_per_bar or (
                writing and beat - 1 > self.beats_per_bar - 1 / TPQ + 1e-9):   # (as a note's beat is taken; a chord's also by validate's bound, a rounding allowed)
            raise ValueError(f'beat {beat!r}: a bar has beats 1 up to, not including, {1 + self.beats_per_bar:g} '
                             '(a beat is a quarter note; 1.5 is its second eighth)')
        return (bar - 1) * self.beats_per_bar + beat - 1

    def _chords(self):
        """The project's chords in order, each (beat from the piece's start, entry): the list `song.harmony` writes,
        read as review reads it (sorted), whatever order a script left it in.  An entry that is no chord entry, or one
        that review reads otherwise than its symbol says (`transpose_semitones`), is refused: its symbol is not the
        chord that sounds.  A symbol written by hand that review cannot read comes back as written."""
        entries = self.project.get('harmony')
        if entries is None or isinstance(entries, dict):   # none yet, or an older free-form object, which nothing reads
            return None if entries is None else False
        if not isinstance(entries, list):
            raise ValueError("the project's harmony is no list of chords")
        out = []
        for h in entries:
            if not (isinstance(h, dict) and isinstance(h.get('bar'), int) and not isinstance(h.get('bar'), bool)
                    and isinstance(h.get('beat', 0), (int, float)) and not isinstance(h.get('beat', 0), bool) and isinstance(h.get('symbol'), str)):
                raise ValueError(f"the project's harmony holds {h!r}, which is no chord entry: each is "
                                 "{'bar': 1-based, 'beat': offset in quarters (optional), 'symbol': text}, as song.harmony writes them")
            if not (1 <= h['bar'] <= self.project['clock']['bars'] and 0 <= h.get('beat', 0) < self.beats_per_bar):
                raise ValueError(f"the project's harmony holds a chord at bar {h['bar']}, beat offset {h.get('beat', 0):g}, outside the piece "
                                 f"(bars 1 to {self.project['clock']['bars']}, offsets from 0 to under {self.beats_per_bar:g})")
            if h.get('transpose_semitones'):
                raise ValueError(f"the project's harmony holds {h['symbol']!r} with transpose_semitones, so the chord that sounds is not "
                                 'its symbol: write the sounding chord, and song.changes and song.chord_at can give it')
            out.append(((h['bar'] - 1) * self.beats_per_bar + h.get('beat', 0), h))
        return sorted(out, key=lambda x: x[0])

    def harmony(self, bar, beat, symbol):
        """A chord of the piece's harmony, from this bar and beat (counted from 1, as notes are) until the next one
        written.  It goes into the project's `harmony`, which review reads the pitched parts' notes against;
        `changes()` and `chord_at()` give it back, so that every part is written from this one list.  A symbol is a
        root, a quality review knows (C, Cm, C7, Cmaj7, Cm7b5, Csus4, C6/9 and the rest of musiclib/harmony.py) and,
        after a slash, a bass: one it cannot read is refused here.  It is stored without spaces round it."""
        from . import harmony as chords
        at = self._place(bar, beat, writing=True)
        symbol = symbol.strip() if isinstance(symbol, str) else symbol
        if not isinstance(symbol, str) or chords.parse(symbol) is None:
            raise ValueError(f'{symbol!r} is no chord symbol review can read: a root, a quality of musiclib/harmony.py '
                             '(C, Cm, C7, Cmaj7, Cm7b5, Cdim7, Csus4, C6/9 ...) and, after a slash, a bass (G7/B)')
        written = self._chords()
        if written is False:
            raise ValueError("the project's harmony is not a list of chords: song.harmony adds to a list")
        if any(abs(x - at) < 1e-9 for x, _ in written or []):
            raise ValueError(f'a chord is written at bar {bar} beat {beat:g} already')
        if self.project.get('harmony') is None:   # none yet, or written as null
            self.project['harmony'] = []
        entries = self.project['harmony']
        entries.append({'bar': bar, **({'beat': min(beat - 1, self.beats_per_bar - 1 / TPQ)} if beat != 1 else {}), 'symbol': symbol})
        entries.sort(key=lambda h: (h['bar'], h.get('beat', 0)))
        return self

    def changes(self):
        """The harmony in order, each chord as (bar, beat, symbol, beats): where it begins, counted from 1, and how many
        beats it lasts, to the next chord or to the piece's end.  What a part's own loop reads; the symbols alone
        ([s for _, _, s, _ in song.changes()]) are what musiclib.voicing.voice_lead takes."""
        written = self._chords() or []
        end = self.project['clock']['bars'] * self.beats_per_bar
        return [(h['bar'], h.get('beat', 0) + 1, h['symbol'], (written[k + 1][0] if k + 1 < len(written) else end) - at)
                for k, (at, h) in enumerate(written)]

    def chord_at(self, bar, beat):
        """The symbol of the chord sounding at this bar and beat, or None before the first chord."""
        at, found = self._place(bar, beat), None
        for x, h in self._chords() or []:
            if x <= at + 1e-9:
                found = h['symbol']
        return found

    def part(self, ident, role, instrument=None, engine=None, keys=None, mix=None, performance=None, **fields):
        """A part.  `instrument`, for a SoundFont part: "<bank> <bank number>:<program>" or words that find one preset in
        the configured banks (studio.py instruments): the part plays it (`soundfont`, `patch`), exports its program
        (`program`, the authored General MIDI one: an export leaves `patch` out, schema.md), and its notes must fall on
        keys it gives a sample (for a part with a `key_map`, a kit not on General MIDI's keys, the keys they are moved to).  Another engine is named with its own fields (engine='surge', surge={'preset': ...}), its
        keys given as (lowest, highest) where they matter.  `mix` adds to a level of -24 dBFS and a reverb send of
        -20 dB, so the project renders as it stands."""
        if any(t['id'] == ident for t in self.project['tracks']):
            raise ValueError(f'a part {ident!r} exists already: each part has an id of its own')
        t = {'id': ident, 'role': role, 'engine': engine or 'soundfont', 'notes': [],
             'performance': {'notes': {}, 'cc': [], **(performance or {})},
             'mix': {'level_dbfs': -24, 'reverb_db': -20, **(mix or {})}, **fields}
        if isinstance(t.get('strings'), (list, tuple)):
            # open strings by number or by name, as pitches are written everywhere else here (the project holds numbers)
            t['strings'] = [pitch_of(s, f'{ident} strings') for s in t['strings']]
        found = covered = None
        if engine == 'additive' and isinstance(instrument, dict):   # the additive engine's own field of that name (schema.md)
            t['instrument'], instrument = instrument, None
        if instrument is not None:
            if engine not in (None, 'soundfont'):
                raise ValueError(f'{ident}: an instrument names a SoundFont preset; engine {engine!r} takes its own fields')
            found = self._preset(ident, instrument)
            if not found['key_ranges']:
                raise ValueError(f'{ident}: {instrument!r} ({found["preset"]}) gives no key a sample; choose another preset (studio.py instruments)')
            if found['bank'] != 'default':
                t['soundfont'] = found['bank']
            t['patch'] = dict(found['patch'])
            t.setdefault('program', found['patch']['program'])   # the export's program; one the script gives stays (the third review)
            sampled = {k for lo, hi in found['key_ranges'] for k in range(lo, hi + 1)}
            # A written key plays the key the part's key_map moves it to (render time: a kit not on General MIDI's keys),
            # so the keys a note may be written on are those that reach a sample through it (the whole review of 0.8: a
            # GM kick for a kit whose kick lies elsewhere was refused, and a key mapped onto no sample taken).
            moved = key_map_pitches(ident, t['key_map']) if 'key_map' in t else {}
            covered = {k for k in range(128) if moved.get(k, k) in sampled}
            if not covered:
                raise ValueError(f'{ident}: no key reaches a sample of {instrument!r} through its key_map; map keys onto {spans(sampled)}')
            keys = keys or [min(covered), max(covered)]
        if keys is not None:
            if isinstance(keys, (str, bytes)) or not isinstance(keys, (list, tuple)) or len(keys) != 2:   # (60,) was an IndexError, a third left out
                raise ValueError(f'{ident}: keys are two pitches, the lowest and the highest, e.g. ("C4", "C6"); got {keys!r}')
            t['range'] = [pitch_of(keys[0], f'{ident} keys'), pitch_of(keys[1], f'{ident} keys')]
            if covered is not None:
                covered = {k for k in covered if t['range'][0] <= k <= t['range'][1]}
        if role == 'drums' or (found and found['patch']['bank'] >= 128):
            t.setdefault('drums', True)   # a kit's notes go to MIDI channel 10 (schema.md)
        self.project['tracks'].append(t)
        return Part(self, t, found, covered)

    def _preset(self, ident, instrument):
        if not self.config:
            raise ValueError(f'{ident}: an instrument is found in the configured banks: give Song(..., config=<config.json>)')
        from .instruments import search
        words = instrument.split()
        patch = re.fullmatch(r'(\d+):(\d+)', words[-1]) if len(words) == 2 else None
        found = search(self.config, [], bank=words[0]) if patch else search(self.config, words)   # a named bank alone is read
        rows = found['presets']
        if not found.get('every_word', True):
            # the search gives the nearest presets where none has every word: none of them is the one asked for
            listed = '; '.join(f'"{r["bank"]} {r["patch"]["bank"]}:{r["patch"]["program"]}" {r["preset"]} (has: {", ".join(r["has"])})' for r in rows[:8])
            raise ValueError(f'{ident}: {instrument!r}: no preset has every word; the nearest are {listed}{"; ..." if len(rows) > 8 else ""}: '
                             'name one of them, or give fewer words')
        if patch:
            rows = [r for r in rows if (r['patch']['bank'], r['patch']['program']) == (int(patch[1]), int(patch[2]))]
        if len(rows) != 1:
            listed = '; '.join(f'"{r["bank"]} {r["patch"]["bank"]}:{r["patch"]["program"]}" {r["preset"]}' for r in rows[:8])
            raise ValueError(f'{ident}: {instrument!r} ' + (f'finds {len(rows)} presets ({listed}{"; ..." if len(rows) > 8 else ""}): name one of them'
                                                           if rows else 'finds no preset in that bank: studio.py instruments lists them'))
        return rows[0]

    def save(self, path):
        """Validate the project and write it (over an earlier one of the same script); returns validate's summary.  Where
        no file is there yet, it is made only while the name stays free: a file put there meanwhile is never replaced
        (files.publish_new).  With START_SAVE set (start set it for its run of compose.py before 0.10, which saves its skeleton
        itself) nothing there is the script's own: a song.json there was made by something else.  The flag alone decides, not a
        comparison of resolved paths, which a link swapped for a file between the two resolutions defeated (the Astra
        reviews of the fixes for 0.8.0): start's skeleton saves one file."""
        summary = validate(self.project)
        path = Path(path)
        try:
            save_json(path, self.project, new=bool(os.environ.get(START_SAVE)) or not files.occupied(path))
        except FileExistsError:
            raise ValueError(f'{path} was made by something else while the song was saved; it is left as it is') from None
        if summary.get('warnings'):
            print(files.joined(f'warning: {w}' for w in summary['warnings']))   # a warning carries the project's text
        return summary


def spans(keys):
    """Keys as runs of names: C4-E4, G4-C5."""
    from .instruments import key_ranges
    return ', '.join(name(lo) if lo == hi else f'{name(lo)}-{name(hi)}' for lo, hi in key_ranges(keys))


class Part:
    """A part's notes, written by bar and beat.  `keys`: the keys its preset gives a sample, or None (no preset)."""

    def __init__(self, song, track, preset=None, covered=None):
        self.song, self.track, self.preset = song, track, preset
        self.keys = sorted(covered) if covered is not None else None
        self._covered = set(covered or ())
        self._moved = key_map_pitches(track['id'], track['key_map']) if preset is not None and 'key_map' in track else {}
        self._ids = set()

    def note(self, bar, beat, pitch, beats, velocity=80, gate=None, timing_ms=None, id=None, **fields):
        """One note at `bar` and `beat` (from 1), `beats` long; its id is returned: `id` where given (a revision keeps
        a moved note's id so), else one made from the part, bar, beat and pitch.  Its performance entry is made with it;
        `fields` are the note's own (phrase, articulation, comment), not its place."""
        t, song = self.track, self.song
        if isinstance(beat, bool) or not isinstance(beat, (int, float)) or not math.isfinite(beat):   # None stopped the message's format, True was beat 1
            raise ValueError(f'{t["id"]} bar {bar!r}: beat {beat!r} is no number; a beat counts quarter notes from 1 (1, 2.5)')
        where = f'{t["id"]} bar {bar} beat {beat:g}'
        if set(fields) & {'on', 'duration'}:   # (pitch and id are parameters)
            raise ValueError(f'{where}: a note\'s on and duration come from bar, beat and beats, not from its fields')
        bars, per = song.project['clock']['bars'], song.beats_per_bar
        if isinstance(bar, bool) or not isinstance(bar, int) or not 1 <= bar <= bars:
            raise ValueError(f'{where}: the song has bars 1 to {bars} (counted from 1)')
        if not 1 <= beat < 1 + per:
            raise ValueError(f'{where}: a bar of {song.project["clock"]["meter"][0]}/{song.project["clock"]["meter"][1]} holds beats 1 to under {1 + per:g} (quarter notes, from 1)')
        k = pitch_of(pitch, where)
        lo, hi = t.get('range', [0, 127])
        if self.keys is not None and k not in self._covered:
            cover = spans(self.keys) or "no key in the part's range"
            patch = f'{t.get("soundfont", "default")} {t["patch"]["bank"]}:{t["patch"]["program"]}'
            if self._moved:
                raise ValueError(f'{where}: {name(k)} (MIDI {k}) plays key {self._moved.get(k, k)} through the part\'s key_map, which has no '
                                 f'sample in {patch}; the keys that reach one are {cover}: write it on one of them, or map it onto a sample')
            raise ValueError(f'{where}: {name(k)} (MIDI {k}) has no sample in {patch}, whose samples cover {cover}; move it onto them, '
                             'or give it to a part that has it')
        if not lo <= k <= hi:
            raise ValueError(f'{where}: {name(k)} (MIDI {k}) is outside {name(lo)}-{name(hi)}, the part\'s keys; move it into them, '
                             'or give it to a part that has it')
        on = round((bar - 1) * per + beat - 1, 6)
        if id is not None:   # each cause in its own words (one message for both left a test piece guessing which)
            if not isinstance(id, str) or not id:
                raise ValueError(f'{where}: note id {id!r} is no text; an id is a word of its own, or leave it out for one made from the place')
            if id in self._ids:
                raise ValueError(f'{where}: note id {id!r} is taken by another note of this part; give each note its own')
            ident = id
        else:
            base = f'{t["id"]}_b{bar:03d}_t{round((beat - 1) * 48):03d}_p{k}'
            ident, n = base, 2
            while ident in self._ids:
                ident, n = f'{base}_{n}', n + 1
        self._ids.add(ident)
        t['notes'].append({'id': ident, 'on': on, 'duration': beats, 'pitch': k, **fields})
        t['performance']['notes'][ident] = {'velocity': velocity, **({'gate': gate} if gate is not None else {}),
                                            **({'timing_ms': timing_ms} if timing_ms is not None else {})}
        return ident

    def chord(self, bar, beat, pitches, beats, velocity=80, **kw):
        """Notes struck together; their ids are returned."""
        return [self.note(bar, beat, p, beats, velocity, **kw) for p in pitches]

    def fret(self, bar, beat, string, fret, beats, velocity=80, mute=None, **kw):
        """One note of a part played by string (the part made with `strings=[...]`, the open pitches from low to high):
        `string` as players count (1 the highest), `fret` 0 for the open string; `mute` "palm" or "dead".  Its id is
        returned."""
        strings = self.track.get('strings')
        where = f'{self.track["id"]} bar {bar} beat {beat}'
        if not strings:
            raise ValueError(f'{where}: fret() is for a part played by string: make the part with strings=[...], its open '
                             'pitches from low to high (a guitar: [40, 45, 50, 55, 59, 64])')
        if isinstance(string, bool) or not isinstance(string, int) or not 1 <= string <= len(strings):
            raise ValueError(f'{where}: string {string!r}: this part has strings 1 (the highest) to {len(strings)}')
        if isinstance(fret, bool) or not isinstance(fret, int) or not 0 <= fret <= 24:
            raise ValueError(f'{where}: fret {fret!r}: a fret is 0 (the open string) to 24')
        fields = {'string': string, **({'mute': mute} if mute else {}), **kw}
        ident = self.note(bar, beat, strings[len(strings) - string] + fret, beats, velocity, **fields)
        # a string sounds one note at a time: a note written to ring is written to its string's next note (the project
        # holds lengths as they sound), whichever of the two was written first
        own = sorted((n for n in self.track['notes'] if n.get('string') == string), key=lambda n: n['on'])
        for a, b in zip(own, own[1:]):
            # (lengths that are not numbers are left for the project's own check to name; a tick is the shortest note)
            if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (a['duration'], b['duration'])) and b['on'] > a['on'] and a['on'] + a['duration'] > b['on']:
                a['duration'] = max(round(b['on'] - a['on'], 6), round(1 / TPQ + 5e-7, 6))
        return ident

    def shape(self, bar, beat, frets, beats, velocity=80, mute=None, **kw):
        """Notes struck together on a part played by string: `frets` is (string, fret) pairs, as a chord box or a
        tablature column gives them; their ids are returned."""
        return [self.fret(bar, beat, s, f, beats, velocity, mute, **kw) for s, f in frets]
