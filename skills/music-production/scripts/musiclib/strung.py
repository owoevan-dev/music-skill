"""A sampled part played by string (`strings` on the part, `string` and `mute` on its notes).

A guitar or a bass is a few strings, each sounding one note at a time.  A part that names its strings (their open
pitches, low to high: `"strings": [40, 45, 50, 55, 59, 64]`) and gives each note its string (`"string": 6`, counted
as players count them: 1 is the highest) is played so:

- a string's note ends when that string's next note begins, by a short fade, whatever its written length (the finger
  moves, or the pick lands on the string again); until then it rings as long as it is written, and the other strings
  ring on meanwhile;
- a note marked `"mute": "palm"` is its recording damped, as by the picking hand's edge on the strings at the bridge:
  every band of its sound dies away by a time of its own, the high ones fastest, from the note's start;
- a note marked `"mute": "dead"` is the same with far shorter times: a string stopped by the fretting hand, which
  gives a click of little pitch.

How it is computed.  The part is synthesized in passes, each the skill's ordinary dry synthesis of some notes of one
string, chosen so that in a pass every note is silent before the next begins: a note's key is released no later than
its string's next stroke, a voice of the bank sounds on after that for no longer than the preset's release (read from
the SoundFont: `tail_seconds`), and a note goes into the first pass that is silent again by its start.  So a note's
stretch in its pass (from its start to the pass's next note) holds that note and nothing else: it is damped if the
note is muted and faded out where its string's next note starts, and the passes are summed.  "Its string's next
stroke" is read as played (model.performed, which ends the note there for every reader of the part: the exported
MIDI, the roll, review, an excerpt), string by string: one pitch held on two strings rings on both here, where the
part's MIDI file, which holds a key once at a time, ends the first at the second; where the piece loops, a note is also ended by the loop's strokes on its
string a loop later, so that a string's last note does not lie under the loop's first stroke when the tail is folded.
(A stroke that its timing plays past the loop's end is folded onto the loop's start as it is: it does not end what
sounds there, since in a single pass through the piece nothing would.)  Where nothing is muted
and no string is struck again while it sounds, the sum is the part's ordinary synthesis (but for the first
millisecond or two of a note, where FluidSynth's output depends a little on what it has played before in the same
run: measured on the direct guitar bank, under 0.002 of full scale).  The sum is the part's dry synthesis for
everything after it: its amplifier where it has one (`mix.amp`), its level and its mix.

A part of slow notes takes one pass a string; one of quick notes on one string takes as many as fit into the
release (at sixteenth notes of 87 ms and a release of 0.2 s, four).  A bank whose release cannot be read (a
modulator moves it) is taken at TAIL_UNKNOWN, one longer than TAIL_LIMIT at TAIL_LIMIT, and the receipt says
`tail_assumed`: what a voice of it still sounds after that stays in its pass.  A pedal would hold a voice past its
key, so a part played by string is refused one.

No fingering is chosen here: the string of each note is written.  It is checked that the note lies on its string
(from the open string to FRETS frets above it); that a string is not struck twice on one tick is checked where the
notes are read as played (model.performed).  A note may not be written longer than to its string's next note:
what the score says is then what sounds, for every reader of the written lengths; what remains for the synthesis
is the note that its gate or the next stroke's timing carries past that stroke, and the release.

The decay times below are provisional: chosen here, not measured from a muted guitar.  Set beside a published
measurement of palm-muted against open playing through distorted amplifiers (Herbst 2017a, Table 5), the damped
notes through the amplifier's `high_gain` voice agree with it within about 3 dB from 250 Hz up; through the cleaner
voices they lose more of the top than his average (research/guitar-0.9/herbst_compare.py).
"""
import contextlib
import copy
import math

import numpy as np

from . import audio, midi, sf2
from .played import TPQ, performed, tick_of

RATE = audio.RATE
FRETS = 24
FADE_MS = 8.0             # a string stopped by its next stroke: provisional
MUTES = ('palm', 'dead')
# Seconds for a band to fall 60 dB, by frequency; straight lines between the points on a log-frequency axis.
T60 = {'palm': [(60, .45), (200, .32), (800, .16), (3000, .07), (12000, .04)],
       'dead': [(60, .05), (800, .03), (12000, .02)]}
BANDS, LOWEST = 24, 50.0
DAMP_ROOM = 4096
TAIL_MARGIN = .05         # seconds over the preset's release before a pass counts as silent
TAIL_LIMIT = 3.0          # the longest tail kept apart: a longer release is taken as this (the receipt says `tail_assumed`)
TAIL_UNKNOWN = 1.0        # the tail where a modulator moves the release, so that no figure can be read (`tail_assumed`)
SOUNDING = 1e-4           # a note counts as ended by its string's next stroke where it is above this (-80 dBFS) there
HELD = (64, 66, 69)       # the controllers that hold a note after its key: sustain, sostenuto, hold 2


def wanted(track):
    return bool(track.get('strings'))


def open_pitch(track, string):
    """The open pitch of `string` (1 the highest) on the part."""
    return track['strings'][len(track['strings']) - string]


def validate(track):
    """The part's `strings` and its notes' `string` and `mute`, or ValueError saying what to write instead."""
    tid, strings = track['id'], track.get('strings')
    marked = [n for n in track['notes'] if 'string' in n or 'mute' in n]
    if strings is None:
        if marked:
            raise ValueError(f'{tid}: note {marked[0]["id"]} has a string or a mute, but the part names no strings: give the part '
                             '"strings", the open pitches of its strings from low to high (a guitar: [40, 45, 50, 55, 59, 64])')
        return
    if (not isinstance(strings, list) or not 4 <= len(strings) <= 8
            or any(isinstance(s, bool) or not isinstance(s, int) or not 0 <= s <= 127 for s in strings)
            or any(b < a for a, b in zip(strings, strings[1:]))):
        raise ValueError(f'{tid}: strings are the open pitches of four to eight strings as MIDI numbers, from low to high '
                         '(a guitar: [40, 45, 50, 55, 59, 64]; a bass: [28, 33, 38, 43])')
    if track.get('engine') != 'soundfont' or track.get('drums'):
        raise ValueError(f'{tid}: strings are for a pitched sampled part ("engine": "soundfont")')
    perf = track['performance']
    for key in ('legato', 'round_robin', 'dynamics'):
        if perf.get(key):
            raise ValueError(f'{tid}: a part played by string cannot also use performance.{key}; remove one of the two')
    if track.get('reverse'):
        raise ValueError(f'{tid}: a part played by string cannot also be reversed')
    held = sorted({c[1] for c in perf.get('cc', []) if isinstance(c, (list, tuple)) and len(c) == 3 and c[1] in HELD})
    if held:
        raise ValueError(f'{tid}: a part played by string cannot hold its notes with a pedal (controller {held[0]}): a string '
                         'rings for as long as its note is written; write the lengths and remove the controller')
    if track.get('key_map') is not None:
        raise ValueError(f'{tid}: a part played by string cannot also have a key_map (two strings could be moved onto one key); '
                         'write the pitches the strings play')
    count = len(strings)
    for n in track['notes']:
        s = n.get('string')
        if isinstance(s, bool) or not isinstance(s, int) or not 1 <= s <= count:
            fits = [k for k in range(1, count + 1) if 0 <= n['pitch'] - open_pitch(track, k) <= FRETS]
            where = (f'it lies on string {" or ".join(map(str, fits))}' if fits else 'no string of this part reaches it')
            raise ValueError(f'{tid}: note {n["id"]} (MIDI {n["pitch"]}) needs its string, 1 (the highest) to {count}: {where}')
        fret = n['pitch'] - open_pitch(track, s)
        if not 0 <= fret <= FRETS:
            fits = [k for k in range(1, count + 1) if 0 <= n['pitch'] - open_pitch(track, k) <= FRETS]
            raise ValueError(f'{tid}: note {n["id"]} (MIDI {n["pitch"]}) is not on string {s}, which runs from MIDI '
                             f'{open_pitch(track, s)} to {open_pitch(track, s) + FRETS}'
                             + (f'; it lies on string {" or ".join(map(str, fits))}' if fits else ''))
        if n.get('mute') is not None and n['mute'] not in MUTES:
            raise ValueError(f'{tid}: note {n["id"]}: mute is "palm" or "dead"')
    # A note is written no longer than its string lets it sound: to its string's next note.  The score's own readers
    # (the views by section, review's intervals, the loop's report) read written lengths, and they are then true.
    by_string = {}
    for n in track['notes']:
        by_string.setdefault(n['string'], []).append(n)
    for s, own in by_string.items():
        own = sorted(own, key=lambda n: n['on'])
        for a, b in zip(own, own[1:]):
            if tick_of(b['on']) > tick_of(a['on']) and tick_of(a['on'] + a['duration']) > tick_of(b['on']):
                # (the length to write in full: rounded to six figures it could end a tick late and be refused again)
                raise ValueError(f'{tid}: note {a["id"]} on string {s} is written to last until beat {a["on"] + a["duration"]:g}, but that '
                                 f'string\'s next note ({b["id"]}) begins at beat {b["on"]:g}: write it {max(b["on"] - a["on"], 1 / TPQ):.10g} beats long '
                                 '(a string sounds one note at a time; the builder\'s fret() and shape() shorten a ringing note where '
                                 'its string is struck again)')


def _t60(points, freqs):
    return np.interp(np.log(np.maximum(freqs, 1.0)), np.log([q[0] for q in points]), [q[1] for q in points])


def damp(seg, points):
    """`seg` (frames, channels) with every frequency band decaying by its own time from its first sample.  The bands
    are triangular in log frequency and sum to one, so decay times far above the stretch's length leave it as it is.
    The transform is DAMP_ROOM samples longer than the stretch: a band's ringing then dies in that room and does not
    come round onto the stretch's start (without it a stretch of 80 ms differed from the same stretch followed by
    silence by -48 dB of its peak; with it, by less than -95 dB)."""
    seg = np.asarray(seg, dtype=np.float64)
    n = len(seg)
    if n < 64:
        return seg
    m = audio_fast(n + DAMP_ROOM)
    spec = np.fft.rfft(seg, n=m, axis=0)
    f = np.fft.rfftfreq(m, 1 / RATE)
    centres = np.sqrt(np.geomspace(LOWEST, RATE / 2, BANDS + 1)[:-1] * np.geomspace(LOWEST, RATE / 2, BANDS + 1)[1:])
    pos = np.interp(np.log(np.maximum(f, LOWEST)), np.log(centres), np.arange(BANDS))
    t = np.arange(n) / RATE
    times = _t60(points, centres) / math.log(1000)
    out = np.zeros_like(seg)
    for k in range(BANDS):
        w = np.clip(1 - np.abs(pos - k), 0, 1)
        if k == 0:
            w[f <= centres[0]] = 1
        if k == BANDS - 1:
            w[f >= centres[-1]] = 1
        if w.any():
            out += np.fft.irfft(spec * w[:, None], n=m, axis=0)[:n] * np.exp(-t / times[k])[:, None]
    return out


def audio_fast(n):
    from .measure import fast_length
    return fast_length(n)


def cut(seg, at):
    """`seg` (frames, channels) silenced from frame `at` by a short raised-cosine fade."""
    if at >= len(seg):
        return seg
    at = max(0, at)
    n = min(len(seg) - at, max(1, int(FADE_MS / 1000 * RATE)))
    seg[at:at + n] *= (.5 + .5 * np.cos(np.pi * np.arange(n) / n))[:, None]
    seg[at + n:] = 0
    return seg


def tail_seconds(release):
    """(seconds, assumed): how long after a note's end its pass is taken as sounding, from the preset's release in
    seconds, and whether that is an assumption: the release could not be read (None: TAIL_UNKNOWN) or is longer than
    TAIL_LIMIT."""
    if release is None:
        return TAIL_UNKNOWN, True
    return round(min(TAIL_LIMIT, release + TAIL_MARGIN), 4), release + TAIL_MARGIN > TAIL_LIMIT


def _sub(track, notes):
    """The part with `notes` alone."""
    sub = copy.copy(track)
    ids = {n['id'] for n in notes}
    sub['notes'] = notes
    sub['performance'] = {**track['performance'], 'notes': {k: v for k, v in track['performance']['notes'].items() if k in ids}}
    return sub


def passes(track, clock, tail, wrap=None):
    """The part's notes arranged for synthesis: for each string, highest number first,
    (string, notes, starts, stops, ends, groups).  `notes` are the string's notes in the order played; `starts` their
    first samples; `stops` the sample where each is ended by its string's next stroke (None for the last, or, where
    the piece loops, the loop's first stroke on that string a loop later: `wrap` is the loop's first sample and its
    length in samples); `ends` id -> the tick its key is released on, its own or its string's next stroke
    (model.performed); `groups` lists of indices into `notes`, each a pass in which every note's key has been
    released, and `tail` seconds have passed, before the next begins."""
    per = {}
    for n in track['notes']:
        per.setdefault(n['string'], []).append(n)
    out = []
    for string, own in sorted(per.items(), reverse=True):
        played = {e['id']: e for e in performed(_sub(track, own), clock)}
        notes = sorted(own, key=lambda n: played[n['id']]['tick'])
        starts = [round(played[n['id']]['start_seconds'] * RATE) for n in notes]
        stops = starts[1:] + [None]
        if wrap is not None:
            # the strokes of the loop again, a loop later: a note is ended by the first stroke after its own start,
            # of this pass through the piece or of the next (a last note played past the loop's end by its timing is
            # ended by the first repeated stroke after it, not by one before it)
            later = sorted(s + wrap[1] for s in starts if s >= wrap[0])
            for k, s in enumerate(starts):
                again = next((c for c in later if c > s), None)
                if again is not None and (stops[k] is None or again < stops[k]):
                    stops[k] = again
        groups, silent_from = [], []
        for k, n in enumerate(notes):
            e = played[n['id']]
            j = next((j for j, at in enumerate(silent_from) if e['start_seconds'] >= at), len(groups))
            if j == len(groups):
                groups.append([])
                silent_from.append(0.0)
            groups[j].append(k)
            silent_from[j] = e['end_seconds'] + tail
        out.append((string, notes, starts, stops, {n['id']: played[n['id']]['end_tick'] for n in notes}, groups))
    return out


def summary(track, clock):
    """What review says of a part played by string, from the score alone: the notes on each string (1 the highest),
    the frets used, the muted notes, and the widest stretch of frets between stopped notes that sound together.

    "Sound together" is read as played, string by string, as the synthesis reads the part (`passes`): a note sounds
    from its stroke until its own end or its string's next stroke, so the notes of a shape left to ring are held
    together and those of a line are not, and one pitch held on two strings is held on both (the whole part's
    MIDI events would end the first where the second begins).  The stretch's place is where it is played (a
    stroke played early by its timing can meet a note of the bar before).  An open string and a dead note take
    no finger's place on the neck and are left out of the stretch.  A figure of the score, not a fingering: no
    fingering is chosen here, and nothing is called too wide."""
    count = len(track['strings'])
    written = {n['id']: n for n in track['notes']}
    fret = {i: n['pitch'] - open_pitch(track, n['string']) for i, n in written.items()}
    by = {str(s): 0 for s in range(1, count + 1)}
    muted = {m: 0 for m in MUTES}
    for n in track['notes']:
        by[str(n['string'])] += 1
        if n.get('mute'):
            muted[n['mute']] += 1
    facts = {'strings': list(track['strings']), 'notes_by_string': by, 'open_notes': sum(1 for f in fret.values() if f == 0),
             'lowest_fret': min(fret.values(), default=None), 'highest_fret': max(fret.values(), default=None),
             'muted': muted, 'widest_reach': None}
    held = {}                                  # string -> the note sounding on it (as played)
    per = {}
    for n in track['notes']:
        per.setdefault(n['string'], []).append(n)
    played = sorted((a for own in per.values() for a in performed(_sub(track, own), clock)), key=lambda a: a['tick'])
    k = 0
    while k < len(played):
        tick = played[k]['tick']
        for s in [s for s, a in held.items() if a['end_tick'] <= tick]:
            del held[s]
        while k < len(played) and played[k]['tick'] == tick:
            held[written[played[k]['id']]['string']] = played[k]
            k += 1
        stopped = [fret[a['id']] for a in held.values() if fret[a['id']] > 0 and written[a['id']].get('mute') != 'dead']
        if len(stopped) > 1 and (facts['widest_reach'] is None or max(stopped) - min(stopped) > facts['widest_reach']['frets']):
            facts['widest_reach'] = {'frets': max(stopped) - min(stopped), 'lowest_fret': min(stopped), 'highest_fret': max(stopped),
                                     'at': f'bar {int(tick / TPQ // clock.beats_per_bar) + 1} beat {math.floor((tick / TPQ % clock.beats_per_bar + 1) * 1000) / 1000:g}',   # cut, not rounded: a bar's last tick is not told as the next beat
                                     'beat': round(tick / TPQ, 4)}
    return facts


def empty():
    """What the receipt records of a part played by string that has no notes."""
    return {'passes': 0, 'strings': [], 'open': 0, 'palm': 0, 'dead': 0, 'ended_by_next_stroke': 0, 'tail_seconds': 0.0}


def render(p, t, clock, cfg, font, folder, out):
    """The part's dry synthesis played by string, written to `out`; returns what the receipt records."""
    patch = t.get('patch') or t
    tail, assumed = tail_seconds(sf2.longest_release(sf2.read(font['path']), patch.get('bank', 0), patch.get('program', 0)))
    wrap = None
    if 'loop' in p:
        first = round(clock.seconds(p['loop'].get('start_bar', 0) * clock.beats_per_bar) * RATE)
        wrap = (first, round(clock.seconds(clock.total_beats) * RATE) - first)
    arranged = passes(t, clock, tail, wrap)
    total = None
    facts = {'passes': 0, 'strings': [a[0] for a in arranged], 'open': 0, 'palm': 0, 'dead': 0, 'ended_by_next_stroke': 0,
             'tail_seconds': tail}
    if assumed:
        facts['tail_assumed'] = True
    for string, notes, starts, stops, ends, groups in arranged:
        for g, group in enumerate(groups):
            label = f's{string}_{g}'
            mid, wav = folder / f'strung_{label}.mid', folder / f'strung_{label}.wav'
            try:
                midi.write(p, mid, [_sub(t, [notes[k] for k in group])], single_stem=True, render=True, ends=ends)
                audio.fluidsynth(cfg, font['path'], mid, wav, folder, f'fluidsynth_{label}')
                x = np.array(audio.read_wav(wav)[0], dtype=np.float64)        # a copy: the file can go
            finally:
                for made in (mid, wav):
                    with contextlib.suppress(OSError):
                        made.unlink()
            facts['passes'] += 1
            for j, k in enumerate(group):
                a = min(starts[k], len(x))
                b = min(starts[group[j + 1]], len(x)) if j + 1 < len(group) else len(x)
                kind = notes[k].get('mute') or 'open'
                facts[kind] += 1
                if kind != 'open':
                    # damped over the time its slowest band takes to fall 240 dB; nothing is left after it
                    upto = min(b, a + int(4 * max(q[1] for q in T60[kind]) * RATE))
                    x[a:upto] = damp(x[a:upto], T60[kind])
                    x[upto:b] = 0
                seg = x[a:b]                                   # a view: changed in place
                if stops[k] is not None and stops[k] - a < len(seg):
                    at = max(0, stops[k] - a)
                    if float(np.max(np.abs(seg[at:at + 480]), initial=0.0)) > SOUNDING:
                        facts['ended_by_next_stroke'] += 1
                    cut(seg, at)
            if total is None:
                total = x
            elif len(x) > len(total):
                x[:len(total)] += total
                total = x
            else:
                total[:len(x)] += x
    audio.write_wav(out, (total if total is not None else np.zeros((1, 2))).astype(np.float32))
    return facts
