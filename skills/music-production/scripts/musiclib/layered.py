"""Expressive rendering of sustained sampled parts: crossfades between recorded dynamics, and crossfaded legato.

Dynamics.  An instrument played louder also sounds brighter, so a sampled crescendo should move from one recorded
dynamic to the next rather than only turn the level up.  Samplers crossfade between recorded dynamics along a
controller (the mod wheel, CC1; SFZ's xfin/xfout, equal-power by default).  A bank built with `dynamic_layers`
(soundbank.py) has each recorded dynamic of a sustained preset as its own preset that ignores velocity, at bank 16 + k
(k = 0 the softest) on the preset's program.  A part with `performance.dynamics`, a [beat, 0-127] curve, is rendered
once per dynamic and the renders are crossfaded along the curve (`dynamics_mode` "crossfade"), or each note plays one
take (`dynamics_mode` "take", the default; below).  The values read like velocities: the level follows
the curve a plain preset gives velocity (amplitude in proportion to (value / 127)^2, so 64 sounds about 12 dB under
127; SF2's default velocity-to-attenuation), while the recordings crossfade, evenly spaced from 0 to 127.  Without a
curve, a part with crossfade legato takes one from its notes' velocities.  Two neighbouring dynamics cross over in the
middle half of the span between them, and near each recorded dynamic its take sounds alone: two takes of one note carry
their own vibrato and phase, and held together they comb-filter and sound like two players.  The gains follow
equal-power curves, then a factor from the measured correlation of the two renders keeps the power of the mix at what
two unrelated renders would give.  So the mix neither dips nor swells whether the takes are unrelated (two dynamics of
a section) or the same take (a dynamic the bank borrowed for a note): equal-power fading is exact only for
uncorrelated signals (Fink, Holters and Zoelzer 2016).

Takes.  With `performance.dynamics_mode` "take" (the default), each note plays one recorded take, the dynamic nearest the curve's
mean over the note, so no note is ever two takes at once and nothing comb-filters.  The curve still moves within the
note: the level follows it continuously (the layers' own offsets interpolated, so a note on the next take up does not
jump), and the tone follows it through a morph toward the neighbouring dynamic's spectrum.  Fabiani (2009) and Fabiani
and Friberg (2011) model how the spectrum of an instrument changes with dynamics; here the change is learned from the
bank itself: for every note sampled on two neighbouring dynamics with different takes, the 1/3-octave spectral envelope
of each take at equal RMS, and the median difference per band is a linear-phase filter.  A take is then blended with
its own filtered copy (in phase, so the blend is a filter between the two), toward the louder dynamic as the curve
rises past its nominal value and toward the softer as it falls.

Legato.  A sustained sample begins with its bow or breath attack, so a slurred line of samples re-attacks every note.
With `performance.legato` {"mode": "crossfade"}, a note that follows its neighbour within `gap_ms` (one line, not a
chord) starts from the bank's legato preset (bank 32 + k): the same take entered past its attack, as SFZ legato
regions do with `offset`.  The earlier note keeps sounding for `crossfade_ms` and the two cross over with equal-power
curves (two pitches, so uncorrelated).  Successive notes of a slur alternate between two renders so each can be faded
on its own.  A legato note speaks at once, so it leaves out the part's `offset_ms`.  A part that keeps the slur mode
(a glide on one sample, for solo lines in small steps) keeps it here too, on every dynamic.  A crossfade also ends before the next note on
the outgoing note's render starts: after a long note, fast notes would otherwise enter while that render is still
fading out.  Where a chord starts during a crossfade, both renders are busy, so the note it would slur into is struck
with the chord instead.

Bow changes.  A looped sample holds a note for ever on one bow; a string player changes bow every few seconds, a
small break in the tone.  With `performance.bow_change_s`, a note longer than one and a half times that is cut into
even stretches of about that length, each entering from the legato preset over `bow_ms` (60): the same recording,
re-entered past its attack.

Portamento.  With `legato.portamento_ms`, a legato note at least three semitones from the one before slides into its
pitch: the wheel starts `portamento_from` (0.6) of the way back toward the previous note and eases in over that many
milliseconds, an expressive shift of position rather than a glissando.  A part with pitch bends of its own keeps them
instead.

Round robins.  With `performance.round_robin`, a note repeating a pitch within 1.2 s plays a neighbouring key's
recording, the wheel bringing it back to pitch (musiclib/variation.py).
"""
import bisect
import math
from pathlib import Path
import threading

import numpy as np

from . import audio, files, sf2, variation
from .midi import chunk, meta
from .model import TPQ, bend_curve, bend_events, cc_events, curve_at, effective_tempo, legato_notes, performed, save_json, wheel_events

LAYER_BANK, LEGATO_BANK = 16, 32
FRAME = 480    # 10 ms: the step of the gain curves
ZONE = (.25, .75)  # where between two recorded dynamics they cross over
WINDOW = 19200  # samples (0.4 s) over which the two renders' powers and correlation are measured: long enough
# that the phase drift between two takes' vibratos averages out, short enough to follow a crossfade


BANDS = 1000 * 2 ** (np.arange(-13, 13) / 3)  # 1/3-octave centres, 50 Hz to 16 kHz
EXCERPT = (0.15, 0.75)  # seconds after a take's start over which its tone and level are measured
FIR = 2047  # taps of the brightness filters (48 kHz: 23 Hz resolution; the 21 ms delay is compensated)
_profiles, _profile_lock = {}, threading.Lock()
_names, _names_lock = {}, threading.Lock()


def preset_names(font_path):
    """{(bank, program): name} of a bank's presets, read once for the file as it is (its size and modification time):
    every SoundFont part of a render asks."""
    st = Path(font_path).stat()
    key = (str(font_path), st.st_size, st.st_mtime_ns)
    with _names_lock:
        if key not in _names:
            _names[key] = {(x['bank'], x['program']): x['name'] for x in sf2.read(font_path)['presets']}
        return _names[key]


def wanted(track):
    perf = track['performance']
    return 'dynamics' in perf or (perf.get('legato') or {}).get('mode') == 'crossfade'


def banks(font_path, program):
    """Banks of the dynamic layers (soft to loud) and of their legato versions on `program`."""
    have = set(preset_names(font_path))
    layers, legato = [], []
    while (LAYER_BANK + len(layers), program) in have:
        layers.append(LAYER_BANK + len(layers))
    while (LEGATO_BANK + len(legato), program) in have:
        legato.append(LEGATO_BANK + len(legato))
    return layers, legato


def unsupported(track, font_path):
    """Why the bank cannot play a part (None when it can), with what it can play instead: `review --config` reports it
    and a render stops on it before any part is synthesized.  First, that the bank holds the preset the part plays: a
    drum part on the drum channel plays bank 128 (the MIDI writer), and FluidSynth puts another preset in the place of
    a missing one, which the render found only after synthesis (found by the stress test of 0.4.0); then the part's
    dynamics or crossfade legato."""
    patch = track.get('patch') or {'bank': track.get('bank', 0), 'program': track.get('program', 0)}
    program = patch.get('program', 0)
    names = preset_names(font_path)
    drum = bool(track.get('drums')) and (track.get('patch') is None or patch.get('bank', 0) == 128)
    plays = (128 if drum else patch.get('bank', 0), program)
    if plays not in names:
        there = sorted(p for b, p in names if b == plays[0])
        listed = ', '.join(f'{p} ({names[(plays[0], p)]})' for p in there[:24]) + (' and more' if len(there) > 24 else '')
        zero = sorted(p for b, p in names if b == 0)
        also = ('' if plays[0] in (0, 128) else '; at bank 0: ' + (', '.join(f'{p} ({names[(0, p)]})' for p in zero[:24]) or 'none')
                + (' and more' if len(zero) > 24 else ''))
        return (f'{track["id"]}: the bank has no preset at bank {plays[0]} program {plays[1]}, which this part plays'
                f'{" (its drum kits are at bank 128)" if drum else ""}; FluidSynth would play another in its place. '
                f'At bank {plays[0]} it has: {listed or "none"}{also}.')
    if not wanted(track):
        return None
    able = ', '.join(f'{p} ({names.get((0, p), "?")})' for p in sorted({p for b, p in names if b == LAYER_BANK}))
    what = 'performance.dynamics' if 'dynamics' in track['performance'] else 'crossfade legato'
    hint = f' In this bank, these programs have them, at bank 0: {able or "none"}.'
    if patch.get('bank', 0) != 0:
        return (f'{track["id"]}: {what} plays a program\'s recorded dynamics, which belong to its sustained preset at bank 0; '
                f'bank {patch["bank"]} program {program} ({names.get((patch["bank"], program), "?")}) has none.' + hint)
    layers, legato = banks(font_path, program)
    if not layers:
        return f'{track["id"]}: {what} needs the bank\'s dynamic layers for program {program}, and it has none.' + hint
    if (track['performance'].get('legato') or {}).get('mode') == 'crossfade' and len(legato) != len(layers):
        return f'{track["id"]}: crossfade legato needs the bank\'s legato presets for program {program}, and it has none.'
    return None


def plan(track, clock):
    """Performed notes, each with its render (`parity`), whether it enters legato, and its crossfades in seconds."""
    notes = [dict(n, parity=0, legato=False, fade_in=None, fade_out=None, glide=None) for n in performed(track, clock)]
    leg = track['performance'].get('legato') or {}
    if leg.get('mode') != 'crossfade':
        return notes
    bow = track['performance'].get('bow_change_s')
    if bow:
        cut = []
        for n in notes:
            length = n['end_seconds'] - n['start_seconds']
            pieces = int(length // bow) if length > 1.5 * bow else 1
            for i in range(pieces):
                a = n['start_seconds'] + i * length / pieces
                b = n['start_seconds'] + (i + 1) * length / pieces if i < pieces - 1 else n['end_seconds']
                cut.append(dict(n, start_seconds=a, end_seconds=b, bow_change=i > 0,
                                tick=max(0, round(clock.beat(a) * TPQ))))
        notes = cut
    fade, gap, span = leg.get('crossfade_ms', 100) / 1000, leg.get('gap_ms', 40) / 1000, leg.get('max_interval', 12)
    glide_s, glide_from = leg.get('portamento_ms', 0) / 1000, leg.get('portamento_from', .6)
    if track['performance'].get('bend'):
        glide_s = 0  # the part's own bends own the wheel
    early = track['performance'].get('offset_ms', 0) / 1000
    onsets = {}
    for n in notes:
        onsets[n['tick']] = onsets.get(n['tick'], 0) + 1
    # Where a chord starts during a crossfade, both renders are busy (one fading out, one in), so the note it would
    # slur into is struck instead, with the chord.
    chords = sorted(n['start_seconds'] for n in notes if onsets[n['tick']] > 1)
    crowded = lambda a, b: bisect.bisect_left(chords, b) > bisect.bisect_right(chords, a)
    prev, slur, others = None, [], -1.0  # `others`: the latest end among the notes outside the current slur
    for n in notes:
        if n.get('bow_change') and prev is not None:
            # A bow change: the same note re-entered from the legato preset, crossing over in `bow_ms`.
            start = n['start_seconds']
            length = min(track['performance'].get('bow_ms', 60) / 1000, .8 * (start - prev['start_seconds']))
            prev.setdefault('own_end', prev['end_seconds'])
            prev['end_seconds'] = max(prev['end_seconds'], start + length)
            prev['fade_out'] = (start, length)
            n.update(legato=True, fade_in=(start, length), parity=1 - prev['parity'])
            slur.append(n)
            prev = n
            continue
        if (prev is not None and onsets[n['tick']] == 1 and onsets[prev['tick']] == 1 and n['pitch'] != prev['pitch']
                and abs(n['pitch'] - prev['pitch']) <= span and n['start_seconds'] - prev['end_seconds'] <= gap
                and others <= n['start_seconds'] and not crowded(prev['start_seconds'], n['start_seconds'] - early + fade)):
            shift = -early  # back to the written time: the legato preset has no attack to anticipate
            start = max(prev['start_seconds'] + .02, n['start_seconds'] + shift)
            length = min(fade, .8 * (start - prev['start_seconds']))
            if glide_s and abs(n['pitch'] - prev['pitch']) >= 3:
                n['glide'] = (glide_from * (prev['pitch'] - n['pitch']), glide_s)
            prev.setdefault('own_end', prev['end_seconds'])
            prev['end_seconds'] = max(prev['end_seconds'], start + length)
            prev['fade_out'] = (start, length)
            n.update(start_seconds=start, end_seconds=max(start + .02, n['end_seconds'] + shift), legato=True,
                     fade_in=(start, length), parity=1 - prev['parity'])
            slur.append(n)
        else:
            others = max([others] + [x['end_seconds'] for x in slur])
            slur = [n]
        prev = n
    # Each crossfade also ends before the next note on the outgoing note's render: the slur alternates between two
    # renders, so after a long note a fast one would otherwise enter while that render is still fading out.  Each
    # render's notes by start, found by bisection (the starts no longer move here), so a line of any length is planned
    # in N log N.
    starts = {}
    for x in sorted(notes, key=lambda x: x['start_seconds']):
        starts.setdefault(x['parity'], ([], []))
        starts[x['parity']][0].append(x['start_seconds'])
        starts[x['parity']][1].append(x)
    for i, b in enumerate(notes):
        a = notes[i - 1] if i and b['fade_in'] else None
        if a is None or a['fade_out'] != b['fade_in']:
            continue
        start, length = b['fade_in']
        times, order = starts.get(a['parity'], ([], []))
        k = bisect.bisect_right(times, start)
        c = order[k] if k < len(order) else None
        if c is not None and c['start_seconds'] < start + length:
            length = .8 * (c['start_seconds'] - start)
            a['fade_out'] = b['fade_in'] = (start, length)
            a['end_seconds'] = max(a['own_end'], start + length)
    for n in notes:
        n['tick'] = max(0, round(clock.beat(n['start_seconds']) * TPQ))
        n['end_tick'] = max(n['tick'] + 1, min(round(clock.total_beats * TPQ), round(clock.beat(n['end_seconds']) * TPQ)))
    # A fast slur can bring two notes of one render onto one key: the earlier ends just before the later.
    keys = {}
    for n in notes:
        keys.setdefault((n['parity'], n['pitch']), []).append(n)
    for same in keys.values():
        same.sort(key=lambda n: n['tick'])
        for a, b in zip(same, same[1:]):
            if a['end_tick'] >= b['tick']:
                a['end_tick'] = max(a['tick'] + 1, b['tick'] - 1)
    return notes


def write_midi(path, project, track, notes, program, layer_bank, legato_bank, end, bends=None, clock=None):
    """One render's MIDI: attacks on channel 0 (the dynamic layer), legato entries on channel 1 (its legato preset),
    each with the part's controllers and pitch bends; round-robin attacks on channels 2-5 with the wheel holding them
    at pitch; a portamento as wheel moves on channel 1 (range 12)."""
    conductor = [(round(beat * TPQ), 0, meta(81, round(60_000_000 / bpm).to_bytes(3, 'big'))) for beat, bpm in effective_tempo(project)]
    events = [(0, 0, meta(3, track['id'].encode()))]
    bends = bend_events(track) if bends is None else bends
    for channel, bank in ((0, layer_bank), (1, legato_bank)):
        if bank is None:
            continue
        events += [(0, 1, bytes([176 + channel, 0, bank // 128])), (0, 1, bytes([176 + channel, 32, bank % 128])),
                   (0, 2, bytes([192 + channel, program]))]
        events += [(0, 3, bytes([176 + channel, cc, value])) for cc, value in ((7, 100), (10, 64), (11, 100), (64, 0))]
        events += [(round(beat * TPQ), 4, bytes([176 + channel, cc, value])) for beat, cc, value in cc_events(track)]
        if bends:
            events += [(0, 3, bytes([176 + channel, cc, value])) for cc, value in
                       ((101, 0), (100, 0), (6, track['performance'].get('bend_range', 2)), (38, 0), (101, 127), (100, 127))]
            events += [(round(beat * TPQ), 4, bytes([224 + channel, value & 127, value >> 7])) for beat, value in bends]
        events += [(end, 7, bytes([176 + channel, 64, 0])), (end, 8, bytes([176 + channel, 123, 0]))]
    shifted = sorted({n.get('rr_shift', 0) for n in notes if not n['legato']} - {0})
    for s in shifted:
        channel = variation.channel_for(s, 1)
        events += [(0, 1, bytes([176 + channel, 0, layer_bank // 128])), (0, 1, bytes([176 + channel, 32, layer_bank % 128])),
                   (0, 2, bytes([192 + channel, program]))]
        events += [(0, 3, bytes([176 + channel, cc, value])) for cc, value in ((7, 100), (10, 64), (11, 100), (64, 0))]
        events += [(round(beat * TPQ), 4, bytes([176 + channel, cc, value])) for beat, cc, value in cc_events(track)]
        events += [(0, 3, bytes([176 + channel, cc, value])) for cc, value in ((101, 0), (100, 0), (6, 2), (38, 0), (101, 127), (100, 127))]
        wheel = variation.wheel_value(s)
        events += [(0, 4, bytes([224 + channel, wheel & 127, wheel >> 7])),
                   (end, 7, bytes([176 + channel, 64, 0])), (end, 8, bytes([176 + channel, 123, 0]))]
    glides = [n for n in notes if n['legato'] and n.get('glide')] if legato_bank is not None and not bends else []
    if glides:
        events += [(0, 3, bytes([177, cc, value])) for cc, value in ((101, 0), (100, 0), (6, 12), (38, 0), (101, 127), (100, 127))]
        for n in glides:
            semis, seconds = n['glide']
            t0 = n['tick'] / TPQ
            for i in range(9):
                # An eased slide: the wheel leaves the offset slowly and settles slowly (a half cosine).
                at = clock.beat(clock.seconds(t0) + seconds * i / 8) if clock else t0 + i / 32
                value = 8192 + round(semis * (1 + math.cos(math.pi * i / 8)) / 2 / 12 * 8191)
                events.append((round(at * TPQ), 5, bytes([225, value & 127, value >> 7])))
    for n in notes:
        channel = 1 if n['legato'] else (variation.channel_for(n['rr_shift'], 1) if n.get('rr_shift') else 0)
        key = n['pitch'] + (0 if n['legato'] else n.get('rr_shift', 0))
        events += [(n['tick'], 6, bytes([144 + channel, key, n['velocity']])), (n['end_tick'], 5, bytes([128 + channel, key, 0]))]
    body = chunk(conductor) + chunk(events)
    with files.staged(path) as f:  # whole or not at all (musiclib.files)
        f.write(b'MThd' + (6).to_bytes(4, 'big') + (1).to_bytes(2, 'big') + (2).to_bytes(2, 'big') + TPQ.to_bytes(2, 'big') + body)


def curve(track, notes):
    """The dynamics curve: `performance.dynamics`, or else each onset's velocity (a chord's loudest), linear between."""
    if track['performance'].get('dynamics'):
        return [[float(b), float(v)] for b, v in track['performance']['dynamics']]
    loudest = {}
    for n in notes:
        b = n['tick'] / TPQ
        loudest[b] = max(loudest.get(b, 0), n['velocity'])
    return [[b, float(v)] for b, v in sorted(loudest.items())]


def layer_weights(points, clock, frames, count):
    """Equal-power weights of each dynamic at every 10 ms frame, the pair each frame crossfades, and the dynamics value
    (0 to 1) there."""
    x = np.clip([curve_at(points, clock.beat(i * FRAME / audio.RATE)) / 127 for i in range(frames)], 0, 1)
    w = np.zeros((count, frames))
    if count == 1:
        w[0] = 1
        return w, np.zeros(frames, dtype=int), x
    u = x * (count - 1)
    pair = np.minimum(u.astype(int), count - 2)
    tau = np.clip((u - pair - ZONE[0]) / (ZONE[1] - ZONE[0]), 0, 1)  # one take alone near each recorded dynamic
    idx = np.arange(frames)
    w[pair, idx] = np.cos(np.pi * tau / 2)
    w[pair + 1, idx] += np.sin(np.pi * tau / 2)
    return w, pair, x


def windowed(values, frames, n):
    """Sum of `values` (one per sample) over WINDOW samples centred on each frame."""
    c = np.concatenate([[0.0], np.cumsum(values, dtype=np.float64)])
    centres = np.arange(frames) * FRAME
    return c[np.clip(centres + WINDOW // 2, 0, n)] - c[np.clip(centres - WINDOW // 2, 0, n)]


def matched(ys, w, pair):
    """Fink, Holters and Zoelzer (2016), for renders of unequal power: scale the equal-power gains a, b of neighbouring
    dynamics so that a^2 P1 + b^2 P2 + 2ab C, the power of the mix with C the renders' covariance, equals
    a^2 P1 + b^2 P2, the power two uncorrelated renders would give.  Returns the factor per frame (1 where silent)."""
    frames, n = w.shape[1], len(ys[0])
    scale = np.ones(frames)
    if len(ys) < 2:
        return scale
    power = [windowed((y.astype(np.float64) ** 2).sum(axis=1), frames, n) for y in ys]
    for j in range(len(ys) - 1):
        sel = pair == j
        if not sel.any():
            continue
        cov = windowed((ys[j].astype(np.float64) * ys[j + 1]).sum(axis=1), frames, n)[sel]
        a, b, p1, p2 = w[j, sel], w[j + 1, sel], power[j][sel], power[j + 1][sel]
        base = a * a * p1 + b * b * p2
        full = base + 2 * a * b * cov
        # Frames 60 dB under the part's loudest (release tails, silence) give unreliable estimates: they keep 1.
        ok = (base > 1e-6 * max(float(base.max()), 1e-30)) & (full > 1e-3 * base)
        s = np.ones(len(base))
        s[ok] = np.sqrt(base[ok] / full[ok])
        # One take into itself needs 0.71 at the midpoint, a steady half-antiphase pair 1.41; beyond that the estimate
        # is chasing something other than a steady correlation.
        scale[sel] = np.clip(s, .6, 1.5)
    return np.convolve(np.pad(scale, 2, mode='edge'), np.ones(5) / 5, mode='valid')


def legato_gains(notes, n):
    """Per-sample gain of each of the two renders: equal-power crossfades where a legato note enters, the faded note
    silent until its render's next note; a render that comes back for an attack does so over 5 ms."""
    gains, muted = {0: np.ones(n, dtype=np.float32), 1: np.ones(n, dtype=np.float32)}, {0: None, 1: None}
    at = lambda s: min(n, max(0, int(round(s * audio.RATE))))
    for note in sorted(notes, key=lambda x: x['start_seconds']):
        g, p = gains[note['parity']], note['parity']
        i0 = at(note['start_seconds'])
        if muted[p] is not None:
            g[muted[p]:i0] = 0
            if note['fade_in']:
                start, length = note['fade_in']
                i1 = max(i0 + 1, at(start + length))
                g[i0:i1] = np.sin(np.pi / 2 * np.linspace(0, 1, i1 - i0, endpoint=False))
            else:
                i1 = max(i0 + 1, at(note['start_seconds'] + .005))
                g[i0:i1] = np.linspace(0, 1, i1 - i0, endpoint=False)
            muted[p] = None
        elif note['fade_in']:
            # The render still carries an earlier phrase's release: it steps aside over 5 ms first.
            start, length = note['fade_in']
            i1, h = max(i0 + 1, at(start + length)), min(i0, at(.005))
            g[i0 - h:i0] *= np.linspace(1, 0, h, endpoint=False)
            g[i0:i1] = np.sin(np.pi / 2 * np.linspace(0, 1, i1 - i0, endpoint=False))
        if note['fade_out']:
            start, length = note['fade_out']
            j0, j1 = at(start), max(at(start) + 1, at(start + length))
            g[j0:j1] = np.cos(np.pi / 2 * np.linspace(0, 1, j1 - j0, endpoint=False))
            muted[p] = j1
    for p in (0, 1):
        if muted[p] is not None:
            gains[p][muted[p]:] = 0
    return gains


def _envelope(x, rate):
    """1/3-octave spectral envelope (dB, at equal RMS) and RMS level (dB) of a take's steady excerpt."""
    seg = np.asarray(x[int(EXCERPT[0] * rate):int(EXCERPT[1] * rate)], dtype=np.float64)
    if len(seg) < rate // 10:
        return None, None
    rms = float(np.sqrt(np.mean(seg ** 2)))
    if rms <= 1e-6:
        return None, None
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    freqs = np.fft.rfftfreq(len(seg), 1 / rate)
    edges = np.concatenate([[BANDS[0] / 2 ** (1 / 6)], BANDS * 2 ** (1 / 6)])
    band = np.array([spec[(freqs >= lo) & (freqs < hi)].sum() for lo, hi in zip(edges, edges[1:])])
    total = spec.sum()
    return 10 * np.log10(np.maximum(band / max(total, 1e-30), 1e-12)), 20 * np.log10(rms)


def layer_profile(font_path, program, layers):
    """What each recorded dynamic of `program` sounds like next to its neighbours, learned from the bank: for every root
    key sampled on two neighbouring layers with different takes, the difference of their 1/3-octave envelopes (at equal
    RMS), median over keys and smoothed across bands, clipped to +/-12 dB (`shape[k]`, from layer k to k + 1); and each
    layer's median level against the loudest (`level_db`).  Cached per bank and program."""
    key = (str(font_path), program, tuple(layers))
    with _profile_lock:
        if key in _profiles:
            return _profiles[key]
    bank = sf2.read(font_path)
    takes = []
    for b in layers:
        preset = next(x for x in bank['presets'] if x['bank'] == b and x['program'] == program)
        roots = {}
        for pz in preset['zones']:
            if pz['target'] is None:
                continue
            for z in bank['instruments'][pz['target']]['zones']:
                sid = z['target']
                if sid is None or bank['samples'][sid]['type'] == 2:  # a stereo pair is measured on its left channel
                    continue
                root = z['gens'].get(58, bank['samples'][sid]['root'])
                roots.setdefault(root, (sid, z['gens'].get(48, 0) * sf2.EMU_ATTENUATION / 10))  # dB as FluidSynth plays it
        takes.append(roots)
    measured = {}
    def measure(sid):
        if sid not in measured:
            s = bank['samples'][sid]
            measured[sid] = _envelope(sf2.load_sample(bank, sid), s['rate'])
        return measured[sid]
    shape, counts = [], []
    for k in range(len(layers) - 1):
        diffs = []
        for root, (sid, _) in takes[k].items():
            other = takes[k + 1].get(root)
            if other is None or other[0] == sid:
                continue
            (a, _), (b, _) = measure(sid), measure(other[0])
            if a is not None and b is not None:
                diffs.append(b - a)
        d = np.median(diffs, axis=0) if diffs else np.zeros(len(BANDS))
        d = np.convolve(np.pad(d, 1, mode='edge'), np.ones(3) / 3, mode='valid')
        shape.append(np.clip(d, -12, 12))
        counts.append(len(diffs))
    top = takes[-1]
    level = []
    for k in range(len(layers)):
        offs = []
        for root, (sid, att) in takes[k].items():
            if root in top and top[root][0] != sid:
                (_, la), (_, lb) = measure(sid), measure(top[root][0])
                if la is not None and lb is not None:
                    offs.append((la - att) - (lb - top[root][1]))
        level.append(float(np.median(offs)) if offs else 0.0)
    level[-1] = 0.0
    profile = {'shape': shape, 'level_db': level, 'pairs': counts}
    with _profile_lock:
        _profiles[key] = profile
    return profile


def brightness_fir(shape_db, rate=audio.RATE, taps=FIR):
    """A linear-phase FIR whose magnitude follows `shape_db` on the 1/3-octave bands (log-frequency interpolation,
    flat beyond the ends), windowed by Hann."""
    n = 8192
    freqs = np.fft.rfftfreq(n, 1 / rate)
    gain_db = np.interp(np.log2(np.maximum(freqs, 1.0)), np.log2(BANDS), shape_db)
    h = np.fft.irfft(10 ** (gain_db / 20), n)
    h = np.roll(h, taps // 2)[:taps] * np.hanning(taps)
    return h


def fir_filter(y, h):
    """Linear-phase FIR over a (samples, channels) signal by FFT overlap-add, delay removed."""
    n, taps = len(y), len(h)
    block = 1 << 16
    size = 1 << int(math.ceil(math.log2(block + taps - 1)))
    H = np.fft.rfft(h, size)
    out = np.zeros((n + taps - 1, y.shape[1]), dtype=np.float64)
    for start in range(0, n, block):
        seg = y[start:start + block].astype(np.float64)
        conv = np.fft.irfft(np.fft.rfft(seg, size, axis=0) * H[:, None], size, axis=0)[:len(seg) + taps - 1]
        out[start:start + len(conv)] += conv
    return out[taps // 2:taps // 2 + n].astype(np.float32)


def take_of(notes, points, clock, count):
    """Each note's take: the recorded dynamic nearest the curve's mean over the note (dynamics evenly spaced 0-127)."""
    for n in notes:
        a, b = clock.beat(n['start_seconds']), clock.beat(max(n['start_seconds'] + .01, n['end_seconds']))
        xs = [curve_at(points, a + (b - a) * i / 8) / 127 for i in range(9)]
        n['take'] = int(min(count - 1, max(0, round(float(np.mean(xs)) * (count - 1))))) if count > 1 else 0
    return notes


def render_takes(project, track, clock, cfg, font, folder, raw, layers, legato, crossfade, notes, bends, program):
    """The "take" dynamics mode (see the module notes)."""
    count = len(layers)
    points = curve(track, notes)
    take_of(notes, points, clock, count)
    renders = {}
    for k, bank in enumerate(layers):
        for parity in (0, 1):
            subset = [n for n in notes if n['parity'] == parity and n['take'] == k]
            if not subset:
                continue
            mid, wav = Path(folder) / f'take_{k}_{parity}.mid', Path(folder) / f'take_{k}_{parity}.wav'
            write_midi(mid, project, track, subset, program, bank, legato[k] if crossfade else None, round(clock.total_beats * TPQ), bends, clock)
            audio.fluidsynth(cfg, font['path'], mid, wav, folder, f'fluidsynth_take_{k}_{parity}')
            renders[(k, parity)] = audio.read_wav(wav)[0]
    n = max(len(x) for x in renders.values())
    pad = lambda x: np.pad(x, ((0, n - len(x)), (0, 0))) if len(x) < n else x
    gains = legato_gains(notes, n) if crossfade else {0: np.ones(n, dtype=np.float32), 1: np.ones(n, dtype=np.float32)}
    profile = layer_profile(font['path'], program, layers)
    frames = n // FRAME + 1
    x = np.clip([curve_at(points, clock.beat(i * FRAME / audio.RATE)) / 127 for i in range(frames)], 0, 1)
    nominal = np.linspace(0, 1, count) if count > 1 else np.array([1.0])
    level = np.interp(x, nominal, profile['level_db']) if count > 1 else np.zeros(frames)
    t_frames, t_samples = np.arange(frames) * FRAME, np.arange(n)
    out = np.zeros((n, 2), dtype=np.float32)
    morph_peak = 0.0
    for k in range(count):
        y = np.zeros((n, 2), dtype=np.float32)
        for parity in (0, 1):
            if (k, parity) in renders:
                y += pad(renders[(k, parity)]) * gains[parity][:, None]
        if not y.any():
            continue
        # How far the curve sits from this take's dynamic, in steps between neighbours: + toward the louder one.
        step = 1 / (count - 1) if count > 1 else 1.0
        a = np.clip((x - nominal[k]) / step, -1, 1)
        if k == count - 1:
            a = np.minimum(a, 0)
        if k == 0:
            a = np.maximum(a, 0)
        morph_peak = max(morph_peak, float(np.abs(a).max()))
        mixed = y.copy()
        for sign, shape in ((1, profile['shape'][k] if k < count - 1 else None), (-1, -profile['shape'][k - 1] if k > 0 else None)):
            amount = np.clip(sign * a, 0, 1)
            if shape is None or not amount.any() or not np.any(np.abs(shape) > .05):
                continue
            z = fir_filter(y, brightness_fir(shape))
            p_y, p_z = float(np.mean(y.astype(np.float64) ** 2)), float(np.mean(z.astype(np.float64) ** 2))
            z *= np.float32(math.sqrt(p_y / p_z)) if p_z > 0 else np.float32(1)
            g = np.interp(t_samples, t_frames, amount).astype(np.float32)[:, None]
            mixed += (z - y) * g
        # Level: the velocity law, with the layers' own offsets interpolated so the level depends on the curve alone.
        gain = x ** 2 * 10 ** ((level - profile['level_db'][k]) / 20)
        out += mixed * np.interp(t_samples, t_frames, gain).astype(np.float32)[:, None]
    audio.write_wav(raw, out)
    used = sorted({n['take'] for n in notes})
    summary = {'mode': 'take', 'dynamic_layers': layers, 'legato_presets': legato if crossfade else [], 'renders': len(renders),
               'takes_used': used, 'notes_per_take': {str(k): sum(n['take'] == k for n in notes) for k in used},
               'legato_entries': sum(n['legato'] for n in notes), 'notes': len(notes),
               'bow_changes': sum(bool(n.get('bow_change')) for n in notes), 'portamenti': sum(bool(n.get('glide')) for n in notes),
               'round_robin_shifts': sum(bool(n.get('rr_shift')) for n in notes),
               'brightness_pairs': profile['pairs'], 'layer_level_db': [round(v, 2) for v in profile['level_db']],
               'morph_peak': round(morph_peak, 3), 'correction_out_of_range_pct': 0.0}
    save_json(Path(folder) / 'layered.json', summary)
    return summary


def render(project, track, clock, cfg, font, folder, raw):
    """Render a part with dynamics crossfades and crossfaded legato into `raw`; returns a summary."""
    patch = track.get('patch') or {'bank': track.get('bank', 0), 'program': track.get('program', 0)}
    program = patch.get('program', 0)
    if patch.get('bank', 0) != 0:
        raise ValueError(f'{track["id"]}: dynamic layers belong to the sustained preset (bank 0) of a program')
    layers, legato = banks(font['path'], program)
    crossfade = (track['performance'].get('legato') or {}).get('mode') == 'crossfade'
    if not layers:
        raise ValueError(f'{track["id"]}: the bank has no dynamic layers for program {program} '
                         '(build it with dynamic_layers; see references/soundbank-building.md)')
    if crossfade and len(legato) != len(layers):
        raise ValueError(f'{track["id"]}: crossfade legato needs the bank\'s legato presets for program {program}')
    notes = plan(track, clock)
    bends = None
    leg = track['performance'].get('legato')
    if leg and leg.get('mode', 'slur') == 'slur':
        # Slurred notes sound as one sample with the pitch carried by the wheel, as on a plain preset (midi.write).
        notes, slurs = legato_notes(track, notes, clock)
        bends = wheel_events([bend_curve(track['performance'].get('bend', [])), slurs], track['performance'].get('bend_range', 2), clock.total_beats)
    if track['performance'].get('round_robin') and not bends and not bend_events(track):
        attacks = [n for n in notes if not n['legato']]
        for n, s in zip(attacks, variation.round_robin_shifts(attacks, variation.key_samples(font['path'], layers[0], program))):
            n['rr_shift'] = s
    if track['performance'].get('dynamics_mode', 'take') == 'take':
        return render_takes(project, track, clock, cfg, font, folder, raw, layers, legato, crossfade, notes, bends, program)
    renders = {}
    for k, bank in enumerate(layers):
        for parity in sorted({n['parity'] for n in notes}):
            subset = [n for n in notes if n['parity'] == parity]
            mid, wav = Path(folder) / f'pass_{k}_{parity}.mid', Path(folder) / f'pass_{k}_{parity}.wav'
            write_midi(mid, project, track, subset, program, bank, legato[k] if crossfade else None, round(clock.total_beats * TPQ), bends, clock)
            audio.fluidsynth(cfg, font['path'], mid, wav, folder, f'fluidsynth_{k}_{parity}')
            renders[(k, parity)] = audio.read_wav(wav)[0]
    n = max(len(x) for x in renders.values())
    pad = lambda x: np.pad(x, ((0, n - len(x)), (0, 0))) if len(x) < n else x
    gains = legato_gains(notes, n) if crossfade else {0: np.ones(n, dtype=np.float32), 1: np.ones(n, dtype=np.float32)}
    ys = []
    for k in range(len(layers)):
        y = np.zeros((n, 2), dtype=np.float32)
        for parity in (0, 1):
            if (k, parity) in renders:
                y += pad(renders[(k, parity)]) * gains[parity][:, None]
        ys.append(y)
    frames = n // FRAME + 1
    points = curve(track, notes)
    w, pair, x = layer_weights(points, clock, frames, len(layers))
    factor = matched(ys, w, pair)
    scale = factor * x ** 2  # the level follows the velocity curve
    t_frames, t_samples = np.arange(frames) * FRAME, np.arange(n)
    out = np.zeros((n, 2), dtype=np.float32)
    for k, y in enumerate(ys):
        g = np.interp(t_samples, t_frames, w[k] * scale).astype(np.float32)
        out += y * g[:, None]
    audio.write_wav(raw, out)
    # How much of the part's playing (frames within 20 dB of its loudest) the correction pushed past 1.25 or under 0.8:
    # two takes that disagree in phase there; a solo should stay near one recorded dynamic.
    energy = np.array([float(np.mean(out[i * FRAME:(i + 1) * FRAME].astype(np.float64) ** 2)) if i * FRAME < n else 0.0
                       for i in range(frames)])
    playing = energy > max(float(energy.max()), 1e-30) * 1e-2
    off = playing & ((factor > 1.25) | (factor < .8))
    summary = {'correction_out_of_range_pct': round(float(off.sum()) / max(1, int(playing.sum())) * 100, 2),
               'dynamic_layers': layers, 'legato_presets': legato if crossfade else [], 'renders': len(renders),
               'legato_entries': sum(n['legato'] for n in notes), 'notes': len(notes),
               'bow_changes': sum(bool(n.get('bow_change')) for n in notes), 'portamenti': sum(bool(n.get('glide')) for n in notes),
               'round_robin_shifts': sum(bool(n.get('rr_shift')) for n in notes),
               'correlation_factor': {'min': round(float(factor.min()), 3), 'max': round(float(factor.max()), 3)}}
    save_json(Path(folder) / 'layered.json', summary)
    return summary
