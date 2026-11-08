"""Production tools for electronic and pop mixes, applied to a part's processed stem (and one to the premix):
ducking keyed by another part's notes, a tempo-synced delay that follows the tempo map, a filter sweep, oversampled
saturation, a rhythmic gate, and low frequencies made mono.

Ducking.  A sidechain compressor keyed by the kick pulls a pad or bass down on each beat; in electronic production the
same shape is often drawn as a volume envelope from the kick's timing, which is exact and repeatable.  `mix.duck`
does that: from each note of the part named by `by` (optionally only some keys), the gain falls by `depth_db` within
`attack_ms`, holds `hold_ms` and recovers with a time constant of a fifth of `release_ms`.

Delay.  `mix.delay` repeats the part `beats` later (in beats, so on a tempo map each echo lands where that many
beats later falls), each repeat `feedback` quieter, optionally alternating sides, filtered between `highpass` and
`lowpass` Hz, and mixed in at `send_db`.  Echoes are read from the stem at fractional positions (linear
interpolation), so every repeat is sample-accurate on any tempo map.

The other tools: `mix.filter_sweep` moves a resonant low- or high-pass along [beat, Hz] points (the biquad of
musiclib/synth.py); `mix.saturate` drives the stem through tanh at four times the sample rate; `mix.gate` opens and
closes the part in a repeating pattern of steps ("x" open, "." closed) a given number of beats long, with 3 ms ramps;
`mix.mono_below_hz` (project mix) makes the premix mono below that frequency, as a cutting lathe and club systems want.

Worn media.  A tape machine whose speed wavers bends the pitch of everything on it: slow "wow" (below about 4 Hz,
from capstan or reel eccentricity) and faster "flutter" (IEC 60386 and AES6 measure both as speed deviation).
`mix.wow_flutter` reads the stem through a delay that moves so the pitch deviates by `wow_cents` at `wow_hz` and by
`flutter_cents` at `flutter_hz` (peak values), with cubic interpolation and no net shift in time; on the project mix
it wobbles the whole premix.  A noise part's `vinyl` note plays a worn record's surface noise: hiss, a crackle of
short clicks whose sizes fall off as a power law, an occasional deeper pop, and one scratch ticking once a revolution
(33 1/3 rpm, every 1.8 s).
"""
import math

import numpy as np

from .measure import fast_length
from .synth import RATE, biquad, resample_down, seed


def _times(n):
    return np.arange(n) / RATE


def duck(stem, project, track, clock):
    spec = track['mix']['duck']
    source = next((t for t in project['tracks'] if t['id'] == spec['by']), None)
    if source is None:
        raise ValueError(f'{track["id"]}: duck.by names no part')
    from .model import performed
    keys = set(spec.get('keys', []))
    hits = sorted({round(e['start_seconds'], 6) for e in performed(source, clock) if not keys or e['pitch'] in keys})
    n = len(stem)
    floor = 10 ** (-spec.get('depth_db', 6) / 20)
    attack, hold, release = spec.get('attack_ms', 4) / 1000, spec.get('hold_ms', 20) / 1000, spec.get('release_ms', 160) / 1000
    gain = np.ones(n)
    span = int((attack + hold + release * 1.5) * RATE)
    for h in hits:
        i0 = max(0, int(round((h - attack) * RATE)))
        t = np.arange(span) / RATE
        shape = np.where(t < attack, t / attack, np.where(t < attack + hold, 1.0, np.exp(-(t - attack - hold) / (release / 5))))
        g = 1 - (1 - floor) * shape
        m = min(span, n - i0)
        if m > 0:
            gain[i0:i0 + m] = np.minimum(gain[i0:i0 + m], g[:m])
    return stem * gain[:, None], {'hits': len(hits), 'depth_db': spec.get('depth_db', 6)}


def _band(x, lo, hi):
    """x between `lo` and `hi` Hz, a zero-phase filter applied in the frequency domain.  The stem is zero-padded to a
    fast FFT length (measure.fast_length): a stem's sample count often has a large prime factor, which made this
    transform the slowest step of a part, and the padding also keeps the filter's decay from wrapping round."""
    m = fast_length(len(x))
    spec = np.fft.rfft(x, n=m, axis=0)
    f = np.fft.rfftfreq(m, 1 / RATE)
    h = np.ones_like(f)
    if lo:
        h *= (f / lo) ** 2 / (1 + (f / lo) ** 2)
    if hi:
        h /= 1 + (f / hi) ** 2
    return np.fft.irfft(spec * h[:, None], n=m, axis=0)[:len(x)]


def delay(stem, track, clock):
    spec = track['mix']['delay']
    n = len(stem)
    beats, fb = spec.get('beats', .75), spec.get('feedback', .35)
    wet = np.zeros_like(stem)
    source = _band(stem, spec.get('highpass', 300), spec.get('lowpass', 6000))
    t_out = _times(n)
    beat_out = np.array([clock.beat(x) for x in t_out[::480]])
    beat_out = np.interp(np.arange(n), np.arange(0, n, 480)[:len(beat_out)], beat_out)
    echoes = 0
    for k in range(1, 17):
        g = fb ** (k - 1)
        if g < 1e-3:
            break
        src_beat = beat_out - k * beats
        ok = src_beat >= 0
        src_t = np.array([clock.seconds(b) for b in src_beat[::480]])
        src_t = np.interp(np.arange(n), np.arange(0, n, 480)[:len(src_t)], src_t)
        pos = src_t * RATE
        i = np.clip(pos.astype(int), 0, n - 2)
        frac = (pos - i)[:, None]
        echo = (source[i] * (1 - frac) + source[i + 1] * frac) * ok[:, None]
        if spec.get('ping_pong') and k % 2 == 1:
            echo = echo[:, ::-1]
        wet += echo * g
        echoes += 1
    return stem + wet * 10 ** (spec.get('send_db', -12) / 20), {'beats': beats, 'echoes': echoes}


def filter_sweep(stem, track, clock):
    from .model import curve_at
    spec = track['mix']['filter_sweep']
    n = len(stem)
    hz = np.array([curve_at(spec['points'], clock.beat(x)) for x in _times(n)[::240]])
    hz = np.interp(np.arange(n), np.arange(0, n, 240)[:len(hz)], hz)
    q = np.full(n, .707 + spec.get('resonance', 0.0) ** 2 * 12)
    out = np.stack([biquad(stem[:, c].astype(np.float64), spec.get('type', 'lowpass'), hz, q, RATE) for c in range(stem.shape[1])], axis=1)
    return out, {'from_hz': float(hz[0]), 'to_hz': float(hz[-1])}


def saturate(stem, track):
    drive = track['mix']['saturate']
    k = 1 + 9 * drive
    n = len(stem)
    m = fast_length(n)  # zero-padded to a fast FFT length, as in _band
    # One channel at a time: the four-times signal of a long stem is large (the result is the same either way).
    cols = []
    for c in range(stem.shape[1]):
        spec = np.fft.rfft(stem[:, c:c + 1], n=m, axis=0)
        up = np.fft.irfft(np.pad(spec, ((0, 2 * m + 1 - len(spec)), (0, 0))), n=m * 4, axis=0) * 4
        cols.append(resample_down(np.tanh(k * up) / math.tanh(k), 4)[:n])
        del up, spec
    out = np.concatenate(cols, axis=1)
    # Equal loudness in, equal loudness out: saturation adds density, not level.
    p_in, p_out = float(np.mean(stem ** 2)), float(np.mean(out ** 2))
    return out * (math.sqrt(p_in / p_out) if p_out > 0 else 1.0), {'drive': drive}


def gate(stem, track, clock):
    spec = track['mix']['gate']
    pattern, step = spec['pattern'], spec.get('step_beats', .25)
    n = len(stem)
    beats = np.array([clock.beat(x) for x in _times(n)[::48]])
    beats = np.interp(np.arange(n), np.arange(0, n, 48)[:len(beats)], beats)
    # `phase_beats`: where the pattern stands at beat 0, which an excerpt sets so its passage gates as it did in the
    # piece (it restarted the pattern there; found by GPT Pro's fourth review of 0.4.0).
    idx = (np.floor((beats + spec.get('phase_beats', 0)) / step).astype(int)) % len(pattern)
    open_ = np.array([c == 'x' for c in pattern])[idx].astype(float)
    ramp = int(.003 * RATE)
    kernel = np.ones(ramp) / ramp
    smooth = np.convolve(open_, kernel, mode='same')
    floor = 10 ** (-spec.get('depth_db', 60) / 20)
    return stem * (floor + (1 - floor) * smooth)[:, None], {'steps': len(pattern)}


def wow_flutter(x, spec, name):
    """Tape speed variation on stereo `x` (see the module notes); the wobble's phases come from `name`."""
    rng = np.random.default_rng(seed('wow:' + name))
    n = len(x)
    t = np.arange(n) / RATE
    a, b, c, d = rng.uniform(0, 2 * np.pi, 4)
    wow_hz, flutter_hz = spec.get('wow_hz', .5), spec.get('flutter_hz', 8.0)
    # A main wow with a weaker partial at an unrelated rate, and a flutter whose depth itself drifts; each peaks at 1.
    wow = .75 * np.sin(2 * np.pi * wow_hz * t + a) + .25 * np.sin(2 * np.pi * wow_hz * 1.618 * t + b)
    flutter = np.sin(2 * np.pi * flutter_hz * t + c) * (.6 + .4 * np.sin(2 * np.pi * .13 * t + d))
    cents = spec.get('wow_cents', 8) * wow + spec.get('flutter_cents', 2) * flutter
    shift = np.cumsum(2 ** (cents / 1200) - 1)
    pos = np.arange(n) + shift - shift.mean()
    out = np.empty_like(x, dtype=np.float64)
    for s in range(0, n, 1 << 20):
        p = pos[s:s + (1 << 20)]
        i = np.clip(np.floor(p).astype(np.int64), 1, n - 3)
        f = np.clip(p - i, 0, 1)[:, None]
        xm, x0, x1, x2 = x[i - 1], x[i], x[i + 1], x[i + 2]
        out[s:s + len(p)] = x0 + .5 * f * (x1 - xm + f * (2 * xm - 5 * x0 + 4 * x1 - x2 + f * (3 * (x0 - x1) + x2 - xm)))
    return out, {'wow_cents': spec.get('wow_cents', 8), 'flutter_cents': spec.get('flutter_cents', 2),
                 'peak_shift_ms': round(float(np.abs(shift - shift.mean()).max()) / RATE * 1000, 2)}


def chorus(x, depth):
    """The `chorus` effect on stereo `x`: the voices FFmpeg's chorus gave the skill's earlier renders (in 0.7, out 0.9;
    two voices mixed at 0.5 and 0.4 of `depth`, delayed by 0 to 2 and 0 to 2.5 times `depth` ms along sines of 0.25 and
    0.35 Hz), each read between samples (cubic, as `wow_flutter`).  FFmpeg's chorus reads its moving delay at whole
    samples, so the delay steps, about 77 times a second at depth 0.6: a buzz under a sustained part (a 1 kHz sine came
    out with energy above 4 kHz 52 dB under it).  Whenever a voice's delay came down to zero it read that voice from its
    buffer's far end, 61.5 ms late, for about 0.2 s: a catch every few seconds.  Its delays option only sized that
    buffer, so it never moved the voices."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    voices = ((.5 * depth, .25, 2 * depth), (.4 * depth, .35, 2.5 * depth))
    pad = 3 + max(int(ms * RATE / 1000) for _, _, ms in voices)
    xp = np.concatenate([np.zeros((pad, x.shape[1])), x, np.zeros((3, x.shape[1]))])
    out = .7 * x
    for gain, hz, ms in voices:
        span, period = int(ms * RATE / 1000), int(RATE / hz)  # whole samples, as FFmpeg sized its table
        for s in range(0, n, 1 << 20):
            i = np.arange(s, min(n, s + (1 << 20)))
            p = i + pad - (np.sin(2 * np.pi * (i % period) / period) + 1) / 2 * span
            k = np.floor(p).astype(np.int64)
            f = (p - k)[:, None]
            xm, x0, x1, x2 = xp[k - 1], xp[k], xp[k + 1], xp[k + 2]
            out[s:s + len(i)] += gain * (x0 + .5 * f * (x1 - xm + f * (2 * xm - 5 * x0 + 4 * x1 - x2 + f * (3 * (x0 - x1) + x2 - xm))))
    return out * .9, {'depth': depth, 'sweeps_ms': [round(ms, 3) for _, _, ms in voices]}


def vinyl(n, rng):
    """`n` samples of a worn record's surface noise, stereo, peaking near 1 on the largest clicks."""
    def convolve(x, kernel):
        size = 1 << int(np.ceil(np.log2(len(x) + len(kernel))))
        return np.fft.irfft(np.fft.rfft(x, size, axis=0) * np.fft.rfft(kernel, size)[:, None], size, axis=0)[:len(x)]

    def scatter(rate, sizes):
        count = rng.poisson(rate * n / RATE)
        where, pan = rng.integers(0, n, count), rng.uniform(.15, .85, count)
        size = sizes(count) * rng.choice((-1.0, 1.0), count)
        out = np.zeros((n, 2))
        np.add.at(out[:, 0], where, size * np.sqrt(1 - pan))
        np.add.at(out[:, 1], where, size * np.sqrt(pan))
        return out

    k = np.arange(int(.004 * RATE)) / RATE
    tick = np.sin(2 * np.pi * 3600 * k) * np.exp(-k / .00025)
    pop = np.sin(2 * np.pi * 850 * k) * np.exp(-k / .0012)
    crackle = scatter(14, lambda m: np.minimum(1.0, .03 + .05 * rng.pareto(1.5, m)))
    pops = scatter(.35, lambda m: rng.uniform(.25, .7, m))
    scratch = np.zeros((n, 2))
    first = int(rng.integers(0, int(1.8 * RATE)))
    scratch[first::int(1.8 * RATE)] = [.45, .35]
    hiss = _band(rng.standard_normal((n, 2)), 2500, 9000) * .012
    return convolve(crackle + scratch, tick) + convolve(pops, pop) + hiss


def mono_below(x, hz):
    """The side channel through a zero-phase high-pass falling 48 dB per octave under `hz`, so the low end is mono
    and nothing above it moves in time."""
    mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2
    m = fast_length(len(side))  # zero-padded to a fast FFT length, as in _band
    f = np.fft.rfftfreq(m, 1 / RATE)
    keep = 1 / (1 + (hz / np.maximum(f, 1e-6)) ** 8)
    side = np.fft.irfft(np.fft.rfft(side, n=m) * keep, n=m)[:len(side)]
    return np.stack([mid + side, mid - side], axis=1)


def process(stem, project, track, clock):
    """The track's production tools in a fixed order: tape wobble, sweep, saturation, gate, delay, ducking."""
    mix, report = track['mix'], {}
    y = stem.astype(np.float64)
    if mix.get('wow_flutter'):
        y, report['wow_flutter'] = wow_flutter(y, mix['wow_flutter'], track['id'])
    if mix.get('filter_sweep'):
        y, report['filter_sweep'] = filter_sweep(y, track, clock)
    if mix.get('saturate'):
        y, report['saturate'] = saturate(y, track)
    if mix.get('gate'):
        y, report['gate'] = gate(y, track, clock)
    if mix.get('delay'):
        y, report['delay'] = delay(y, track, clock)
    if mix.get('duck'):
        y, report['duck'] = duck(y, project, track, clock)
    return y.astype(np.float32), report


def wanted(track):
    return any(track['mix'].get(k) for k in ('wow_flutter', 'filter_sweep', 'saturate', 'gate', 'delay', 'duck'))


def validate_wow(spec, where):
    from .model import number
    if not isinstance(spec, dict) or set(spec) - {'wow_cents', 'wow_hz', 'flutter_cents', 'flutter_hz'}:
        raise ValueError(f'{where}: wow_flutter takes wow_cents, wow_hz, flutter_cents and flutter_hz')
    number(spec.get('wow_cents', 8), 0, 50, 'wow cents');number(spec.get('wow_hz', .5), .1, 4, 'wow Hz')
    number(spec.get('flutter_cents', 2), 0, 20, 'flutter cents');number(spec.get('flutter_hz', 8), 4, 25, 'flutter Hz')


def validate(project, track):
    from .model import number
    mix = track['mix']
    ids = {t['id'] for t in project['tracks']}
    if mix.get('wow_flutter'):
        validate_wow(mix['wow_flutter'], track['id'])
    if mix.get('duck'):
        d = mix['duck']
        if d.get('by') not in ids or d['by'] == track['id']:
            raise ValueError(f'{track["id"]}: duck.by names another part')
        number(d.get('depth_db', 6), 0, 30, 'duck depth dB')
        for k, hi in (('attack_ms', 50), ('hold_ms', 500), ('release_ms', 2000)):
            number(d.get(k, 1), 0, hi, 'duck ' + k)
    if mix.get('delay'):
        d = mix['delay']
        number(d.get('beats', .75), .0625, 8, 'delay beats');number(d.get('feedback', .35), 0, .9, 'delay feedback')
        number(d.get('send_db', -12), -40, 0, 'delay send dB')
        number(d.get('highpass', 300), 20, 5000, 'delay highpass');number(d.get('lowpass', 6000), 500, 20000, 'delay lowpass')
    if mix.get('filter_sweep'):
        f = mix['filter_sweep']
        if f.get('type', 'lowpass') not in ('lowpass', 'highpass') or not isinstance(f.get('points'), list) or not f['points']:
            raise ValueError(f'{track["id"]}: filter_sweep takes type and [beat, Hz] points')
        for b, hz in f['points']:
            number(b, 0, 1e6, 'sweep beat');number(hz, 20, 20000, 'sweep Hz')
        number(f.get('resonance', 0), 0, 1, 'sweep resonance')
    if mix.get('saturate') is not None:
        number(mix['saturate'], 0, 1, 'saturate drive')
    if mix.get('gate'):
        g = mix['gate']
        if not isinstance(g.get('pattern'), str) or not 1 <= len(g['pattern']) <= 64 or set(g['pattern']) - set('x.'):
            raise ValueError(f'{track["id"]}: gate.pattern is up to 64 steps of "x" and "."')
        number(g.get('step_beats', .25), .03125, 4, 'gate step beats');number(g.get('depth_db', 60), 3, 90, 'gate depth dB')
        number(g.get('phase_beats', 0), 0, 256, 'gate phase beats')  # the pattern's longest cycle: 64 steps of 4 beats
