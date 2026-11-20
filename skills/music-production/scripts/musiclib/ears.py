"""A headphone version of the mix (`mix.headphones`): every part heard from a direction around the head.

The ordinary master places a part between two loudspeakers by the levels of its two channels.  On headphones a part
can also be given the cues a head gives a sound from some direction: each ear's own delay, level and colour for that
direction (measured on a dummy head), and a room's first reflections arriving from other directions.  The render
then writes `headphones.wav` beside `master.wav`: the same parts, levels, buses, sends and master, with every part
at a direction around the listener.  It is for headphones only: on loudspeakers those cues are heard as a change of
tone.  What it gives is the cues; what a listener makes of them differs from one listener and one pair of headphones
to the next: left and right are plain, front and back can be heard reversed, and a sound can stay inside the head.
The head does not turn with the listener's.

A part's direction is in degrees clockwise seen from above, as on a compass: 0 ahead, 90 to the right, 180 behind,
-90 (or 270) to the left.  Without `mix.around` a part stands where its pan puts it, PAN_DEGREES to the side at a
pan of 1, and follows its `mix.move` there.  `mix.around` is a number (a part that stands), a path
(`{"type": "path", "points": [[beat, degrees], ...]}`, straight in time from point to point; 0 to 360 is once round)
or a turn (`{"type": "turn", "beats": 16}`: once round every 16 beats, from where the part stands, to the right
unless `"direction": "left"`).

How a part is placed.  It is processed as in the ordinary mix but for its pan, its stage position and its movement
(render.process_stem, the part "unplaced"), and then:
- what a part's two channels share (their mean) stands at its place, one point; what differs between them (half
  their difference, however small) is spread SPREAD degrees either side, to the left as it is and to the right
  inverted, at SIDE_GAIN.  A part whose channels are one signal is so the one point, a drum kit or a piano keeps the width its
  stem has, and nothing changes by a step between the two.  (The first build made two points of the two channels
  where they differed by more than a threshold: measured on a drum kit, that came out 5.7 dB over the kit's stem
  and 2.6 to 3.4 dB down around 1 kHz and above 8 kHz, the two points' sum combing what the channels share, and a
  part crossing the threshold jumped by 6 dB.  As it is now the kit is 0.2 dB under its stem, within 1.3 dB of its
  spectrum in every band, and as wide between the ears as between its stem's channels.)
- a point's signal is given to the two measured directions next to its place by two gains that sum to one and follow
  the place sample by sample; each direction's signal then goes through that direction's own pair of responses,
  which never change.  All that moves is a gain ahead of a fixed filter: no response is interpolated, nothing is
  filtered twice and mixed, and no delay moves, so a moving part's pitch stays where it is;
- the room's first reflections (unless `"reflections": false`): one fixed pair of filters for every part, made of
  eight reflections with fixed delays, levels and directions, the first and second images (Allen and Berkley 1979)
  in the horizontal plane of a point at the listener's own place in a room of ROOM metres, each through its
  direction's responses, high-passed at EARLY_HIGHPASS_HZ as the stage's reflections are (musiclib/stage.py).  They
  are the room's answer to a sound near the head, the same wherever the part stands or moves.
The placed parts then go through the mix as the stems do (mixbus.mix with `ears`): the buses' compressors, which
give both channels one gain, without the buses' saturation, which would bend each ear's signal by itself; the
reverb and delay sends are taken from the parts before their places, so the spaces' returns are the room's own
field in both ears (they are the sends the project writes, as in the ordinary mix: a part without `reverb_db` has
the first reflections and no more); and the master, without `mono_below_hz`, with the same EQ on both ears, the limiter's one gain
for both, and a loud master's soft clip giving both the one gain it reads from the louder ear (without that clip the
limiter alone took 8 dB from a master at -9 LUFS and stayed half a dB under its target).

The responses are the SADIE II database's (The Audio Lab, University of York, version 2-2, Apache License 2.0),
subject D1, a Neumann KU100 dummy head, at 48 kHz: the 72 directions of the horizontal plane, every 5 degrees, as
published but for their number format (assets/sadie2-d1, with the licence and a note of the source and the change).
Here they are scaled by one factor, so that their mean power over the ring is 1 and a part keeps about its level.
Above and below the horizontal plane nothing is placed.

Every number of the room, PAN_DEGREES and SPREAD are this skill's choices (on clips, 2026-11-19, the reflections
were preferred to none: a preference, not a calibration).
"""
import json
import math
from pathlib import Path

import numpy as np

from . import audio

RATE = audio.RATE
ASSET = Path(__file__).resolve().parents[2] / 'assets' / 'sadie2-d1'
PAN_DEGREES = 70.0            # where a pan of 1 stands, to the right
SPREAD = 30.0                 # where the difference of a part's two channels stands, either side of its place
SIDE_GAIN = math.sqrt(.5)     # its gain: each side's power then adds up to the difference's own, as the place's does
ROOM, HEAD, WALL, NEAR = (7.2, 9.6), (3.2, 4.2), .8, 2.0   # metres; the pressure a wall returns; the source's distance
EARLY_HIGHPASS_HZ = 250.0
EARLY_TAPS = 8192             # the reflections' filter: 41 ms of reflections, a response's 256 samples, the high-pass's tail
SOUND = 343.0
BLOCK = 16384
SOURCE_KEYS = ('title', 'version', 'publisher', 'doi', 'subject', 'licence')
_cache = {}


def fast_length(n):
    from .measure import fast_length as fast
    return fast(n)


def ring():
    """(responses, step): the ring's pairs as float64 (directions, 2, taps), anticlockwise from straight ahead as the
    data has them, left ear first, scaled to a mean power of 1; and the degrees between two directions."""
    if 'ring' not in _cache:
        import hashlib
        try:
            note = json.loads((ASSET / 'ring72_48k.json').read_text(encoding='utf-8'))
            # text: the source's 24-bit integer samples, one line a direction and ear (the published repository
            # holds nothing binary but images); divided by 2**23, exactly, they are 32-bit floats
            held = np.array((ASSET / note['data']).read_text(encoding='ascii').split(), dtype=np.int64)
            raw = (held.reshape(note['shape']) / 2 ** 23).astype('<f4')
            # the shape is the set's own (72 directions, two ears, 256 samples): the hash is of the samples in any shape
            whole = (raw.shape == (72, 2, 256) and note['shape'] == [72, 2, 256] and note['sample_rate'] == RATE
                     and hashlib.sha256(np.ascontiguousarray(raw, dtype='<f4').tobytes()).hexdigest() == note['array_sha256']
                     and all(isinstance(note['source'][k], str) for k in SOURCE_KEYS))
        except Exception as e:                 # whatever a damaged file raises (a word that is no number, a short file), it is one message
            raise ValueError(f'The head responses of the headphone version cannot be read ({type(e).__name__} in {ASSET.name}): '
                             'they are part of the skill, so install the skill again') from None
        if not whole:
            raise ValueError(f'The head responses of the headphone version are not the files the skill came with ({ASSET.name}): '
                             'install the skill again')
        h = raw.astype(np.float64)
        h *= 1 / math.sqrt(float(np.mean(np.sum(h ** 2, axis=2))))
        _cache['ring'] = (h, 360.0 / h.shape[0])
        _cache['source'] = {k: note['source'][k] for k in SOURCE_KEYS}
    return _cache['ring']


def source():
    """What the render's report says of the responses (read and checked with them, in `ring`)."""
    ring()
    return dict(_cache['source'])


def reflections():
    """The room's eight first reflections: (seconds after the direct sound's start, gain against it, degrees
    clockwise).  The listener looks along +y; first images in the four walls, second images in the four corners."""
    (w, l), (x, y) = ROOM, HEAD
    out = []
    for sx in (-1, 0, 1):
        for sy in (-1, 0, 1):
            if sx == 0 and sy == 0:
                continue
            dx = (0 if sx == 0 else (-x if sx < 0 else 2 * w - x) - x)
            dy = (0 if sy == 0 else (-y if sy < 0 else 2 * l - y) - y)
            path = math.hypot(dx, dy)
            out.append((path / SOUND, WALL ** (abs(sx) + abs(sy)) * NEAR / (NEAR + path), math.degrees(math.atan2(dx, dy)) % 360.0))
    return sorted(out)


def early():
    """The reflections as one fixed pair of filters, (2, EARLY_TAPS): each reflection a delay, a gain and its
    direction's pair of responses, the whole high-passed (second order, Butterworth)."""
    if 'early' not in _cache:
        h, step = ring()
        f = np.fft.rfftfreq(EARLY_TAPS, 1 / RATE)
        s = 1j * f / EARLY_HIGHPASS_HZ
        total = np.zeros((2, len(f)), dtype=complex)
        for delay, gain, degrees in reflections():
            j = int(round((-degrees % 360.0) / step)) % h.shape[0]          # the measured direction nearest to it
            total += gain * np.exp(-2j * np.pi * f * delay)[None, :] * np.fft.rfft(h[j], n=EARLY_TAPS, axis=1)
        _cache['early'] = np.fft.irfft(total * (s * s / (s * s + s * math.sqrt(2) + 1))[None, :], n=EARLY_TAPS, axis=1)
    return _cache['early']


def gains(degrees):
    """For each sample's place (degrees clockwise): the two measured directions next to it and their gains, which sum
    to one."""
    h, step = ring()
    pos = -np.asarray(degrees, dtype=np.float64) / step            # the data counts anticlockwise
    low = np.floor(pos)
    frac = pos - low
    low = low.astype(np.int64) % h.shape[0]
    return low, (low + 1) % h.shape[0], 1.0 - frac, frac


def point(x, degrees, out):
    """One signal `x` heard from `degrees` (for each sample, or one number), added into `out` (frames, 2): in blocks,
    one transform a block and direction, each block's tail laid over the next."""
    h, _ = ring()
    taps = h.shape[2]
    degrees = np.broadcast_to(np.asarray(degrees, dtype=np.float64), x.shape)
    for a in range(0, len(x), BLOCK):
        seg = x[a:a + BLOCK]
        if not seg.any():
            continue
        low, high, g0, g1 = gains(degrees[a:a + BLOCK])
        n = len(seg) + taps - 1
        m = fast_length(n)
        acc = np.zeros((2, m // 2 + 1), dtype=complex)
        for j in np.union1d(low, high):
            bus = seg * (np.where(low == j, g0, 0.0) + np.where(high == j, g1, 0.0))
            acc += np.fft.rfft(bus, n=m)[None, :] * np.fft.rfft(h[j], n=m, axis=1)
        y = np.fft.irfft(acc, n=m, axis=1)[:, :n].T
        end = min(len(out), a + n)
        out[a:end] += y[:end - a]


def convolved(x, pair, out):
    """`x` through the fixed pair of filters `pair` (2, taps), added into `out` (frames, 2), in blocks."""
    taps = pair.shape[1]
    step = 4 * taps
    m = fast_length(step + taps - 1)
    spec = np.fft.rfft(pair, n=m, axis=1)
    for a in range(0, len(x), step):
        seg = x[a:a + step]
        if not seg.any():
            continue
        y = np.fft.irfft(np.fft.rfft(seg, n=m)[None, :] * spec, n=m, axis=1)[:, :len(seg) + taps - 1].T
        end = min(len(out), a + len(y))
        out[a:end] += y[:end - a]


def wanted(p):
    spec = p['mix'].get('headphones')
    return spec is True or isinstance(spec, dict)


def with_reflections(p):
    spec = p['mix'].get('headphones')
    return not isinstance(spec, dict) or spec.get('reflections', True) is not False


def validate_project(p):
    """`mix.headphones`, or ValueError saying what to write instead."""
    if 'headphones' not in p['mix']:
        return
    spec = p['mix']['headphones']
    if not (isinstance(spec, bool) or (isinstance(spec, dict) and not set(spec) - {'reflections'} and isinstance(spec.get('reflections', True), bool))):
        raise ValueError('mix.headphones is true, or {"reflections": false} for the parts\' directions without the room\'s first reflections')
    if spec is False:
        return
    if p['mix'].get('chain') != 'bus':
        raise ValueError('mix.headphones needs mix.chain "bus"')
    if 'loop' in p:
        raise ValueError('mix.headphones is not made for a looped piece: remove one of the two (a loop\'s tail is folded onto its '
                         'start, which the headphone version does not do)')


def validate_track(p, track, total):
    """A part's `mix.around`, or ValueError saying what to write instead."""
    from .model import number
    mix, tid = track['mix'], track['id']
    if 'around' not in mix:
        return
    spec = mix['around']
    if not wanted(p):
        raise ValueError(f'{tid}: mix.around places the part in the headphone version: add "headphones": true to the project\'s mix, '
                         'or remove it')
    forms = (f'{tid}: mix.around is a direction in degrees clockwise (0 ahead, 90 to the right, 180 behind, -90 to the left), '
             '{"type": "path", "points": [[beat, degrees], ...]} or {"type": "turn", "beats": the beats of one turn}')
    if isinstance(spec, bool) or spec is None or (not isinstance(spec, (int, float, dict))):
        raise ValueError(forms)
    if isinstance(spec, (int, float)):
        number(spec, -360, 360, f'{tid} mix.around')
        return
    if spec.get('type') == 'path':
        if set(spec) - {'type', 'points'} or not isinstance(spec.get('points'), list) or len(spec['points']) < 2:
            raise ValueError(f'{tid}: a path around the head is {{"type": "path", "points": [[beat, degrees], ...]}} with two or more points')
        last = -1.0
        for item in spec['points']:
            if not isinstance(item, list) or len(item) != 2:
                raise ValueError(f'{tid}: a point of a path around the head is [beat, degrees]')
            number(item[0], 0, total, f'{tid} mix.around beat')
            number(item[1], -3600, 3600, f'{tid} mix.around degrees')
            if item[0] <= last:
                raise ValueError(f'{tid}: the points of a path around the head are in time order, one for a beat')
            last = item[0]
        return
    if spec.get('type') == 'turn':
        if set(spec) - {'type', 'beats', 'from', 'direction', 'phase_beats'} or 'beats' not in spec:
            raise ValueError(f'{tid}: a turn is {{"type": "turn", "beats": the beats of one turn}}, with "from" (degrees), '
                             '"direction" ("right" or "left") and "phase_beats" where wanted')
        number(spec['beats'], .25, 100000, f'{tid} mix.around beats')
        number(spec.get('from', 0), -360, 360, f'{tid} mix.around from')
        number(spec.get('phase_beats', 0), 0, spec['beats'], f'{tid} mix.around phase_beats')
        if spec.get('direction', 'right') not in ('right', 'left'):
            raise ValueError(f'{tid}: a turn\'s direction is "right" (clockwise seen from above) or "left"')
        return
    raise ValueError(forms)


def degrees_at(track, clock, times):
    """The part's place in degrees clockwise at each of `times` (seconds)."""
    from . import move
    times = np.asarray(times, dtype=np.float64)
    mix = track['mix']
    spec, pan = mix.get('around'), mix.get('pan', 0)
    if spec is None:
        if mix.get('move'):
            return PAN_DEGREES * np.clip(move.places(mix['move'], pan, clock, 0, 0, times=times), -1.0, 1.0)
        return np.full(len(times), PAN_DEGREES * pan)
    if isinstance(spec, (int, float)):
        return np.full(len(times), float(spec))
    if spec['type'] == 'path':
        return move.places({'type': 'path', 'points': spec['points']}, 0, clock, 0, 0, times=times)
    sign = -1.0 if spec.get('direction', 'right') == 'left' else 1.0
    return spec.get('from', PAN_DEGREES * pan) + sign * 360.0 * (audio.beats_at(clock, times) + spec.get('phase_beats', 0)) / spec['beats']


def degrees(track, clock, first, count):
    """The part's place in degrees clockwise at each of `count` samples from sample `first`."""
    return degrees_at(track, clock, np.arange(first, first + count, dtype=np.float64) / RATE)


def summary(track, clock):
    """What `review` says of a part's place in the headphone version, from the score: how it is given and the range
    of its directions over the piece (read every hundredth of a second and at a path's points)."""
    end = clock.seconds(clock.total_beats)
    times = np.arange(0.0, end, .01)
    spec = track['mix'].get('around')
    if isinstance(spec, dict) and spec['type'] == 'path':
        times = np.concatenate([times, [clock.seconds(b) for b, _ in spec['points'] if clock.seconds(b) <= end]])
    if spec is None and track['mix'].get('move'):
        # a part that follows its movement: the movement's own range (its points and a swing's ends, move.summary)
        from . import move
        seen = move.summary(track['mix']['move'], track['mix'].get('pan', 0), clock, exact=True)
        return {'by': kind(track), 'lowest_degrees': round(PAN_DEGREES * seen['lowest'], 1), 'highest_degrees': round(PAN_DEGREES * seen['highest'], 1)}
    where = degrees_at(track, clock, np.unique(np.append(times, end)))
    return {'by': kind(track), 'lowest_degrees': round(float(where.min()), 1), 'highest_degrees': round(float(where.max()), 1)}


def without(p):
    """The project without its headphone version: for a passage that is rendered only to compare sounds."""
    if 'headphones' not in p['mix'] and not any('around' in t['mix'] for t in p['tracks']):
        return p
    return {**p, 'mix': {k: v for k, v in p['mix'].items() if k != 'headphones'},
            'tracks': [{**t, 'mix': {k: v for k, v in t['mix'].items() if k != 'around'}} for t in p['tracks']]}


def kind(track):
    spec = track['mix'].get('around')
    if spec is None:
        return 'pan and move' if track['mix'].get('move') else 'pan'
    return 'still' if isinstance(spec, (int, float)) else spec['type']


def unplaced(track):
    """The part as it is processed for the headphone version: all of its mix but its pan, its stage position and its
    movement, which its direction replaces."""
    return {**track, 'mix': {k: v for k, v in track['mix'].items() if k not in ('pan', 'depth_m', 'facing', 'move', 'around')}}


def place(x, track, clock, room=True):
    """The unplaced stem `x` (frames, 2) placed: float32 (frames, 2), left ear and right ear, and what the report
    says of it."""
    x = np.asarray(x, dtype=np.float64)
    frames = len(x)
    mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2
    e_mid, e_side = float(np.sum(mid ** 2)), float(np.sum(side ** 2))
    one = e_side == 0.0                    # nothing differs between the channels: one point (no threshold: any difference is spread)
    points = [(mid, 0.0)] if one else [(mid, 0.0), (SIDE_GAIN * side, -SPREAD), (-SIDE_GAIN * side, SPREAD)]
    out = np.zeros((frames, 2))
    lowest, highest = math.inf, -math.inf
    where = np.concatenate([degrees(track, clock, a, min(BLOCK, frames - a)) for a in range(0, frames, BLOCK)]) if frames else np.zeros(0)
    if frames:
        lowest, highest = float(where.min()), float(where.max())
    for signal, offset in points:
        point(signal, where + offset, out)
    if room:
        convolved(mid, early(), out)           # the room answers what stands at the part's place
    facts = {'points': 1 if one else 3, 'by': kind(track)}
    if not one:
        facts['side_db'] = round(10 * math.log10(e_side / e_mid), 1) if e_mid > 0 else None
    if frames:
        facts.update(lowest_degrees=round(lowest, 1), highest_degrees=round(highest, 1))
    return out.astype(np.float32), facts


def mix_project(p):
    """The project as the headphone version is mixed and mastered: without what treats the two channels apart."""
    return {**p, 'mix': {k: v for k, v in p['mix'].items() if k not in ('mono_below_hz', 'headphones')},
            'tracks': [unplaced(t) for t in p['tracks']]}      # (a stage depth raises a part's send: not here)


def deliver(p, clock, cfg, output, frames):
    """headphones/: the unplaced stems (headphones/centre/stems, made with the parts) placed, mixed and mastered;
    `headphones.wav` beside the master.  Returns what the report says."""
    from . import files, mixbus
    folder = output / 'headphones'
    for d in (folder / 'stems', folder / 'logs', folder / 'returns', folder / 'mixin'):
        d.mkdir(parents=True, exist_ok=True)
    room, parts = with_reflections(p), {}
    for t in p['tracks']:
        x, _ = audio.read_wav(folder / 'centre' / 'stems' / f'{t["id"]}.wav')
        x = np.asarray(x, dtype=np.float32)
        y, parts[t['id']] = place(x, t, clock, room)
        audio.write_wav(folder / 'stems' / f'{t["id"]}.wav', y)
        # what the mix reads: the placed part and, for its sends, the part before its place, in one file of four
        # channels (a second file a part would double the mix's command line, which Windows bounds)
        audio.write_wav(folder / 'mixin' / f'{t["id"]}.wav', np.concatenate([y, x], axis=1))
        del x, y
    q = mix_project(p)
    buses = mixbus.mix(q, clock, cfg, folder, frames, ears=True)
    _, mastering, after = mixbus.master(q, cfg, folder, ears=True)
    buses.update(mixbus.verify(q, folder, buses))
    tp_max = mixbus.true_peak_ceiling(q['mix'].get('target_lufs', -16))
    if after['true_peak_dbtp'] > tp_max or after['clipped_samples'] or after['frames'] != frames or not buses['adds_up_to_premix']:
        raise ValueError(f'Headphone delivery check failed: true peak {after["true_peak_dbtp"]:g} dBTP (at most {tp_max:g}), '
                         f'{after["clipped_samples"]} clipped samples, {after["frames"]} of {frames} frames, buses and returns '
                         f'{"add" if buses["adds_up_to_premix"] else "do not add"} up to the premix')
    copy = files.stage_copy(folder / 'master.wav', output / 'headphones.wav')
    try:
        files.replace(copy, output / 'headphones.wav')
    except BaseException:
        import contextlib
        import os
        with contextlib.suppress(OSError):
            os.unlink(copy)                    # the copy is not left beside a file that could not be replaced
        raise
    return {'file': 'headphones.wav', 'integrated_lufs': after['integrated_lufs'], 'true_peak_dbtp': after['true_peak_dbtp'],
            'reflections': room, 'responses': source(), 'parts': parts,
            'left_out': [k for k in ('mono_below_hz',) if k in p['mix']] + ['the buses\' saturation'],
            'limiting_db': mastering.get('limiting_db')}


def excerpt(spec, pan, start, end, clock):
    """`mix.around` for an excerpt of the beats `start` to `end`: a path's points inside it with its places at the two
    cuts, a turn with its phase where the excerpt starts and the place it began from."""
    if isinstance(spec, (int, float)):
        return spec
    if spec['type'] == 'turn':
        return {**spec, 'from': spec.get('from', PAN_DEGREES * pan), 'phase_beats': round((start + spec.get('phase_beats', 0)) % spec['beats'], 9) % spec['beats']}
    from . import move
    path = {'type': 'path', 'points': spec['points']}
    a, b = (float(v) for v in move.at_beats(path, 0, [start, end], clock))
    inside = [[beat - start, v] for beat, v in spec['points'] if start < beat < end]
    return {'type': 'path', 'points': [[0, a], *inside, [end - start, b]]}
