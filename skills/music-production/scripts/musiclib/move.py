"""A part that moves across the stereo image (`mix.move`).

Two forms.  A place is a pan value, -1 (left) to 1 (right).

- `{"type": "path", "points": [[beat, pan], ...]}`: absolute places.  Between two points the place runs straight in
  time, as `mix.automation` runs; before the first point it is the first point's, after the last the last one's.
  The part's `pan` is not also written.
- `{"type": "swing", "beats": 4, "width": 0.5, "shape": "sine", "phase_beats": 0}`: to and fro around the part's
  `pan`.  `width` is the farthest it goes to each side; `beats` is the period, counted under the piece's tempo from
  beat 0; with `phase_beats` 0 the part stands at `pan` at beat 0 and moves right.  `shape` is "sine" or "triangle".

How it is rendered.  The part is a point: its two channels are folded to one (their mean), and at every sample the two
gains of the place it has then are applied, by the law the static pan uses (left sqrt(1 - place), right
sqrt(1 + place)).  Level only: there is no time difference between the channels, so the sum of the two is free of
combing, and the part keeps its time (a moving instrument is not detuned).  The place is computed once per sample and
applied to that sample; nothing is rendered for two places and crossfaded.

What it costs, both reported in the part's receipt (`move`):
- the fold: a part whose two channels differ loses its width, and what they carry in opposite polarity cancels
  (`fold_loss_db`; 0 for a part that is one signal);
- in mono a part that is one signal is 3 dB lower at a hard side than in the centre, the pan law's known cost
  (`mono_dip_db`: the lowest the mono sum falls against the centre, where the part sounds).
The figures of where the part sounds are taken as the part reaches the movement, before its production tools (a gate or
a duck after it may silence what is counted); a part that never sounds has only `type`, `fold_loss_db` and, for a
swing, its period.

Not with a stage position (`depth_m`) and not with `width`: a moving part is one point.
"""
import math

import numpy as np

RATE = 48000
SHAPES = ('sine', 'triangle')
WINDOW = 480             # 10 ms: the stretch over which a part is found to sound or not
BLOCK = 128 * WINDOW     # samples placed at once
SOUNDING = 1e-4          # a window above this level (-80 dBFS) counts as the part sounding
SEAM = .05               # how far a held part's place may differ across a loop's seam
FOLD_FLOOR_DB = -120.0   # the least fold_loss_db reported: at it, all of the part was lost in the fold


def validate(project, track, total_beats):
    """`mix.move` of one part, or ValueError saying what to write instead."""
    from .model import number
    mix, tid = track['mix'], track['id']
    spec = mix.get('move')
    forms = '{"type": "path", "points": [[beat, pan], ...]} or {"type": "swing", "beats": ..., "width": ...}'
    if not isinstance(spec, dict) or spec.get('type') not in ('path', 'swing'):
        raise ValueError(f'{tid}: mix.move is {forms}')
    if mix.get('depth_m') is not None:
        raise ValueError(f'{tid}: mix.move cannot be used with mix.depth_m: a part on the stage stays in its place; '
                         'remove one of the two')
    if mix.get('width') is not None:
        raise ValueError(f'{tid}: mix.move cannot be used with mix.width: a moving part is one point (its two channels '
                         'are folded to one); remove mix.width')
    if spec['type'] == 'path':
        if set(spec) - {'type', 'points'}:
            raise ValueError(f'{tid}: a path takes type and points; got also {", ".join(sorted(set(spec) - {"type", "points"}))}')
        points = spec.get('points')
        if not isinstance(points, list) or len(points) < 2 or any(not isinstance(q, list) or len(q) != 2 for q in points):
            raise ValueError(f'{tid}: a path\'s points are two or more [beat, pan] pairs')
        last = -1.0
        for beat, pan in points:
            number(beat, 0, total_beats, f'{tid} mix.move beat')
            number(pan, -1, 1, f'{tid} mix.move pan')
            if beat <= last:
                raise ValueError(f'{tid}: a path\'s points must be in time order, each on a later beat than the one before '
                                 '(a jump is two points close together)')
            last = beat
        if mix.get('pan', 0) != 0:
            raise ValueError(f'{tid}: a path gives the part\'s places itself, so mix.pan is not also written; remove mix.pan '
                             '(or use a swing, which moves around mix.pan)')
    else:
        extra = set(spec) - {'type', 'beats', 'width', 'shape', 'phase_beats'}
        if extra:
            raise ValueError(f'{tid}: a swing takes type, beats, width, shape and phase_beats; got also {", ".join(sorted(extra))}')
        if 'beats' not in spec or 'width' not in spec:
            raise ValueError(f'{tid}: a swing needs beats (its period) and width (how far it goes to each side)')
        number(spec['beats'], .25, 1024, f'{tid} mix.move beats')
        number(spec['width'], .01, 1, f'{tid} mix.move width')
        if spec.get('shape', 'sine') not in SHAPES:
            raise ValueError(f'{tid}: mix.move shape is "sine" or "triangle"')
        number(spec.get('phase_beats', 0), 0, spec['beats'], f'{tid} mix.move phase_beats')
        pan = mix.get('pan', 0)
        if abs(pan) + spec['width'] > 1 + 1e-9:
            room = round(1 - abs(pan), 4)
            raise ValueError(f'{tid}: a swing of width {spec["width"]:g} around pan {pan:g} leaves the image (-1 to 1); '
                             f'around this pan the width can be at most {room:g}')
    if 'loop' in project:
        from .model import Clock, TPQ, tick_of
        clock = Clock(project)
        start = project['loop'].get('start_bar', 0) * clock.beats_per_bar
        end = clock.total_beats
        # by the ticks the notes are played on (their timing, gate, swing and the part's offset: model.performed): a
        # note reaching the loop's last tick, a note starting on its first
        from .model import performed
        first, last = tick_of(start), tick_of(end)
        if track.get('reverse'):
            # a reversed part sounds over each note's written span, whatever its gate, its timing or a later note
            # of its key (render.reversed_notes plays every note by itself)
            spans = [(tick_of(n['on']), tick_of(n['on'] + n['duration'])) for n in track['notes']]
        else:
            spans = [(e['tick'], e['end_tick']) for e in performed(track, clock)]
        held = any(a < last <= b for a, b in spans)
        struck = any(a <= first < b for a, b in spans)   # sounding at the loop's first tick: struck there, or held into it from the intro
        a, b = (float(v) for v in at_beats(spec, mix.get('pan', 0), np.array([start, end]), clock))
        if held and struck and abs(a - b) > SEAM + 1e-9:
            raise ValueError(f'{tid}: the part sounds up to the loop\'s end and again at its start, but its place is {b:+.2f} at '
                             f'the end and {a:+.2f} at the start, so it would jump at the seam: let the movement come back '
                             '(a swing whose period divides the loop, a path that ends where the loop starts) or leave a rest '
                             'at the seam')


def _wave(arg, shape):
    """The swing's value, -1 to 1, at `arg` cycles: 0 at whole cycles, rising."""
    s = np.sin(2 * np.pi * arg)
    return s if shape == 'sine' else np.arcsin(np.clip(s, -1, 1)) * (2 / np.pi)


def at_beats(spec, pan, beats, clock):
    """The part's place at each of `beats`."""
    beats = np.asarray(beats, dtype=np.float64)
    if spec['type'] == 'path':
        at = np.array([clock.seconds(b) for b, _ in spec['points']])
        return np.interp(np.array([clock.seconds(float(b)) for b in beats]), at, [v for _, v in spec['points']])
    return pan + spec['width'] * _wave((beats + spec.get('phase_beats', 0)) / spec['beats'], spec.get('shape', 'sine'))


def places(spec, pan, clock, first, count, times=None):
    """The place at each of `count` samples from sample `first`, or at each of `times` (seconds)."""
    n = np.arange(first, first + count, dtype=np.float64) if times is None else np.asarray(times, dtype=np.float64) * RATE
    if spec['type'] == 'path':
        at = np.array([clock.seconds(b) * RATE for b, _ in spec['points']], dtype=np.float64)
        return np.interp(n, at, np.array([v for _, v in spec['points']], dtype=np.float64))
    from .audio import beats_at
    beats = beats_at(clock, n / RATE)
    return pan + spec['width'] * _wave((beats + spec.get('phase_beats', 0)) / spec['beats'], spec.get('shape', 'sine'))


def apply(x, spec, pan, clock):
    """The stem `x` (frames, 2) moved: a new float32 array and what the receipt records.  The figures are taken where
    the part sounds as it reaches the movement (windows of 10 ms above SOUNDING, the stem's last window as long as
    what is left): before its production tools, so a gate or a duck after this may silence what is counted here."""
    x = np.asarray(x)
    frames = len(x)
    out = np.empty((frames, 2), dtype=np.float32)
    e_in = e_fold = 0.0
    lowest, highest, fastest, dip = math.inf, -math.inf, 0.0, 0.0
    sounding = 0
    before = None                                          # the place of the sample before this block
    for i in range(0, frames, BLOCK):
        seg = np.asarray(x[i:i + BLOCK], dtype=np.float64)
        mono = seg.mean(axis=1)
        e_in += float(np.sum(seg ** 2))
        e_fold += 2 * float(np.sum(mono ** 2))        # the point on two channels, before its place
        p = np.clip(places(spec, pan, clock, i, len(seg)), -1.0, 1.0)
        out[i:i + len(seg), 0] = mono * np.sqrt(1 - p)
        out[i:i + len(seg), 1] = mono * np.sqrt(1 + p)
        edges = np.arange(0, len(seg), WINDOW)           # BLOCK is a whole number of windows, so they line up
        size = np.diff(np.append(edges, len(seg)))
        live = np.repeat(np.sqrt(np.add.reduceat(mono ** 2, edges) / size) > SOUNDING, size)
        if live.any():
            q = p[live]
            sounding += int(live.sum())
            lowest, highest = min(lowest, float(q.min())), max(highest, float(q.max()))
            # the rate from each sample to the next, counted where the later one sounds; across two blocks as well
            rate = np.abs(np.diff(np.concatenate([[p[0] if before is None else before], p]))) * RATE
            fastest = max(fastest, float(rate[live].max()))
            dip = min(dip, float(20 * np.log10(np.maximum(((np.sqrt(1 - q) + np.sqrt(1 + q)) / 2).min(), 1e-9))))
        before = float(p[-1]) if len(p) else before
    facts = {'type': spec['type'],
             'fold_loss_db': max(FOLD_FLOOR_DB, round(10 * math.log10(max(e_fold, 1e-30) / max(e_in, 1e-30)), 2)) if e_in > 0 else 0.0}
    if sounding:
        facts.update(lowest=round(lowest, 3), highest=round(highest, 3), fastest_pan_per_second=round(fastest, 3),
                     mono_dip_db=round(dip, 2))
    if spec['type'] == 'swing':
        facts['period_beats'] = spec['beats']
        facts['period_seconds'] = period_seconds(spec, clock)
    return out, facts


def period_seconds(spec, clock):
    """A swing's period in seconds under the tempo as played: of its first period (from beat 0) and of its last (ending
    with the piece's last bar); one that is longer than the piece runs on at the last tempo, and the two are the same."""
    beats, total = spec['beats'], clock.total_beats
    first = clock.seconds(beats) - clock.seconds(0)
    last = clock.seconds(total) - clock.seconds(total - beats) if beats <= total else first
    return [round(first, 3), round(last, 3)]


def summary(spec, pan, clock, exact=False):
    """What `review` says of a movement from the score alone: its range and its fastest rate in pan units a second,
    over the piece from its first beat to the end of its last bar.  Read every millisecond and at every point of a
    path, so a move between two close points is seen whole."""
    end = clock.seconds(clock.total_beats)
    times = np.arange(0.0, end, .001)
    if spec['type'] == 'path':
        times = np.concatenate([times, [clock.seconds(b) for b, _ in spec['points'] if clock.seconds(b) <= end]])
    else:
        # a swing's two ends, a quarter and three quarters of each period: a quick swing reaches them between two
        # milliseconds (a quarter-beat triangle of width 1 read every millisecond gave 0.992)
        half = spec['beats'] / 2
        first = (spec['beats'] / 4 - spec.get('phase_beats', 0)) % half
        turns = first + half * np.arange(int(max(0.0, clock.total_beats - first) // half) + 1)
        times = np.concatenate([times, [clock.seconds(float(b)) for b in turns if b <= clock.total_beats]])
    times = np.unique(np.append(times, end))
    p = np.clip(places(spec, pan, clock, 0, 0, times=times), -1.0, 1.0)
    rate = np.abs(np.diff(p)) / np.maximum(np.diff(times), 1e-12)
    if exact:                                  # for a reader that works on from the figures (the headphone version's directions)
        return {'lowest': float(p.min()), 'highest': float(p.max())}
    return {'lowest': round(float(p.min()), 3), 'highest': round(float(p.max()), 3),
            'fastest_pan_per_second': round(float(rate.max()), 3) if len(rate) else 0.0}


def moves(spec, pan, clock, lo=None, hi=None):
    """Whether the part's place changes between beats `lo` and `hi` (the whole piece without them)."""
    lo = 0 if lo is None else lo
    hi = clock.total_beats if hi is None else hi
    if spec['type'] == 'swing':
        return hi > lo
    beats = sorted({lo, hi, *(b for b, _ in spec['points'] if lo < b < hi)})
    values = at_beats(spec, pan, beats, clock)
    return bool(np.ptp(values) > 1e-9)


def excerpt(spec, pan, start, end, clock):
    """`mix.move` for the passage from beat `start` to `end`, whose own beats count from 0: a path cut at both ends
    with the places it has there, a swing with its phase moved so that it stands where the piece's swing stands."""
    if spec['type'] == 'path':
        a, b = (min(1.0, max(-1.0, float(v))) for v in at_beats(spec, pan, [start, end], clock))   # as they are: not rounded
        inner = [[beat - start, v] for beat, v in spec['points'] if start < beat < end]
        return {'type': 'path', 'points': [[0, a]] + inner + [[end - start, b]]}
    out = dict(spec)
    out['phase_beats'] = round((start + spec.get('phase_beats', 0)) % spec['beats'], 9) % spec['beats']
    return out
