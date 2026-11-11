"""Subtractive and FM synthesis for parts with `engine: "synth"`: band-limited oscillators, unison, a resonant filter
that moves with envelopes, LFOs and velocity, amplitude and filter envelopes, glide, and oversampled drive.

Oscillators.  A naive sawtooth or pulse aliases badly at high notes; the classic remedy corrects the samples next to
each discontinuity with a polynomial band-limited step, PolyBLEP (Valimaki and Huovilainen 2007; Valimaki, Nam, Smith
and Abel 2010).  The voice runs at four times the output rate and is brought down by an FFT low-pass, so what PolyBLEP leaves
folds back above the audible band.  A pulse is the difference of two sawtooths a pulse width apart; the triangle is
summed from its odd harmonics below the output's Nyquist frequency; "supersaw" stacks detuned sawtooths spread across
the stereo field; "fm" is two-operator phase modulation (Chowning 1973) with its own index envelope.

Chip sounds.  The NES's sound chip plays pulses of 12.5, 25, 50 and 75% duty, a triangle stepped through 32 levels
of a 4-bit counter (15 down to 0 and back), and noise from a shift register clocked at one of sixteen rates, the
"pitch" of the noise (NESdev wiki, APU).  `"steps": 16` on a triangle gives the stepped wave, each step band-limited
like a pulse edge; `"clock": true` on noise holds each random value for a sixteenth of the note's period, so the note
sets the colour, from a dull hiss around C3 to nearly white noise from C7 up.  With one channel per voice, chip music plays chords as fast arpeggios: `arpeggio`
(`{"rate_hz": 60}` or `{"rate_beats"}`, `"order"` up/down/updown) plays the notes that start together as one voice
cycling through their pitches at that rate, as a tracker does once per frame.

Pitch envelope.  `pitch_env` (`{"semitones", "decay"}`) starts each attack that many semitones away and falls back
exponentially (time constant `decay` seconds): the punch of an 808-style bass, a tom, a zap.

Filter.  The low-, high- and band-pass filters are the RBJ biquads (Bristow-Johnson, Audio EQ Cookbook) with the
cutoff recomputed every sample, so an envelope or LFO sweeps them as on an analog synthesizer.  They run in direct
form I: the feed-forward part on the input, then the recursion y[n] = v[n] - a1[n] y[n-1] - a2[n] y[n-2] on the
filter's own output, so its state is the signal itself, which takes a moving cutoff better than the transposed forms;
a large, sudden jump at high resonance can still ring up for a moment (a state-variable filter would take it better).  The
recursion is a linear one in the state [y[n], y[n-1]]: it is solved in blocks of 64 samples at once (products of the
2x2 state matrices and the block's own response), and the blocks are joined by the same method one level up, so no
Python loop runs per sample.  Poles inside the unit circle at every cutoff keep each setting stable at full resonance.  Two
sections in series give 24 dB per octave (Zavalishin 2018 discusses the analog models these approximate).

Everything is deterministic: noise and unison phases come from the note's id.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np

RATE = 48000
OVER = 4
PRESETS_FILE = Path(__file__).resolve().parents[2] / 'references' / 'synth-presets.json'

DEFAULT = {'oscillators': [{'wave': 'saw', 'level': 1.0}], 'amp': {'attack': 0.005, 'decay': 0.1, 'sustain': 0.8, 'release': 0.2},
           'filter': None, 'filter_env': {'attack': 0.002, 'decay': 0.3, 'sustain': 0.0, 'release': 0.3}, 'lfo': None,
           'glide_ms': 0, 'mono': False, 'drive': 0.0, 'velocity_curve': 1.5, 'gain_db': 0.0}


WAVES = ('saw', 'supersaw', 'square', 'pulse', 'triangle', 'sine', 'fm', 'noise')
MONO_LINE_S = 30.0


def validate(track):
    """Bounds of a synth part's patch (after its preset is applied)."""
    from .model import number
    spec = track.get('synth')
    if not isinstance(spec, dict):
        raise ValueError(f'{track["id"]}: a synth part needs a "synth" object (a preset name and/or a patch)')
    patch = patch_of(track)
    oscs = patch.get('oscillators')
    if not isinstance(oscs, list) or not 1 <= len(oscs) <= 8:
        raise ValueError(f'{track["id"]}: 1-8 oscillators')
    for o in oscs:
        if o.get('wave', 'saw') not in WAVES:
            raise ValueError(f'{track["id"]}: oscillator wave must be one of ' + ', '.join(WAVES))
        for key, lo, hi in (('level', 0, 2), ('octave', -3, 3), ('semitones', -24, 24), ('cents', -100, 100), ('voices', 1, 16),
                            ('detune_cents', 0, 100), ('spread', 0, 1), ('width', .05, .95), ('ratio', .25, 16), ('index', 0, 20),
                            ('steps', 2, 64)):
            if key in o:
                number(o[key], lo, hi, f'synth oscillator {key}', key in ('voices', 'steps'))
        if 'steps' in o and o.get('wave') != 'triangle' or 'clock' in o and o.get('wave') != 'noise':
            raise ValueError(f'{track["id"]}: "steps" is for a triangle, "clock" for noise')
        # The objects inside an oscillator are checked as the patch's own are: a pulse's `pwm` is an LFO on its width
        # (its depth at most .45, past which the width, held to .05-.95, only clips), an FM oscillator's `index_env`
        # an envelope.
        if 'pwm' in o:
            check_lfo(track, o['pwm'], 'pwm', {'depth': (0, .45)})
        if 'index_env' in o:
            check_envelope(track, o['index_env'], 'index_env')
    f = patch.get('filter')
    if f:
        if f.get('type', 'lowpass') not in ('lowpass', 'highpass', 'bandpass') or f.get('slope', 12) not in (12, 24):
            raise ValueError(f'{track["id"]}: filter type lowpass/highpass/bandpass, slope 12 or 24')
        for key, lo, hi in (('cutoff_hz', 20, 20000), ('resonance', 0, 1), ('env_amount', -8, 8), ('key_track', -1, 2), ('velocity', -4, 4)):
            number(f.get(key, 0 if key != 'cutoff_hz' else 2000), lo, hi, f'synth filter {key}')
    for name in ('amp', 'filter_env'):
        check_envelope(track, patch.get(name) or {}, name, closed=False)
    l = patch.get('lfo')
    if l:
        check_lfo(track, l, 'lfo', {'to_pitch_cents': (0, 200), 'to_cutoff_octaves': (0, 6), 'to_amp': (0, 1)}, closed=False)
    arp = patch.get('arpeggio')
    if arp:
        if (not isinstance(arp, dict) or set(arp) - {'rate_hz', 'rate_beats', 'order'} or arp.get('order', 'up') not in ('up', 'down', 'updown')
                or 'rate_hz' in arp and 'rate_beats' in arp):
            raise ValueError(f'{track["id"]}: arpeggio takes rate_hz or rate_beats, and order up/down/updown')
        if 'rate_beats' in arp:
            number(arp['rate_beats'], 1 / 64, 1, 'synth arpeggio rate beats')
        else:
            number(arp.get('rate_hz', 60), 4, 120, 'synth arpeggio rate hz')
    pe = patch.get('pitch_env')
    if pe:
        if not isinstance(pe, dict) or set(pe) - {'semitones', 'decay'}:
            raise ValueError(f'{track["id"]}: pitch_env takes semitones and decay')
        number(pe.get('semitones', 12), -48, 48, 'synth pitch_env semitones');number(pe.get('decay', .03), .001, 2, 'synth pitch_env decay')
    number(patch.get('glide_ms', 0), 0, 2000, 'synth glide ms')
    number(patch.get('drive', 0), 0, 1, 'synth drive')
    number(patch.get('velocity_curve', 1.5), .5, 3, 'synth velocity curve')
    number(patch.get('gain_db', 0), -24, 12, 'synth gain dB')


LFO_SHAPES = ('sine', 'triangle', 'square', 'saw')  # what lfo() draws


def check_lfo(track, spec, name, extra, closed=True):
    """An LFO object (the patch's `lfo`, a pulse's `pwm`): a shape lfo() draws, a rate in Hz or beats, a delay and fade
    in seconds and `extra` fields within their bounds.  `closed`: no other fields (a misspelt one would be ignored)."""
    from .model import number
    if not isinstance(spec, dict):
        raise ValueError(f'{track["id"]}: synth {name} must be an object')
    known = {'shape', 'rate_hz', 'rate_beats', 'phase', 'delay', 'fade', *extra}
    if closed and set(spec) - known:
        raise ValueError(f'{track["id"]}: synth {name} takes ' + ', '.join(sorted(known)) + f'; not {", ".join(sorted(set(spec) - known))}')
    if spec.get('shape', 'sine') not in LFO_SHAPES:
        raise ValueError(f'{track["id"]}: synth {name} shape ' + '/'.join(LFO_SHAPES))
    if 'rate_beats' in spec and 'rate_hz' in spec:
        raise ValueError(f'{track["id"]}: synth {name} takes rate_hz or rate_beats, not both')
    if 'rate_beats' in spec:
        number(spec['rate_beats'], .0625, 32, f'synth {name} rate beats')
    else:
        number(spec.get('rate_hz', 5), .01, 30, f'synth {name} rate hz')
    for key, (lo, hi) in {'phase': (0, 1), 'delay': (0, 10), 'fade': (0, 10), **extra}.items():
        number(spec.get(key, lo), lo, hi, f'synth {name} {key}')


def check_envelope(track, env, name, closed=True):
    """An envelope object (`amp`, `filter_env`, an FM oscillator's `index_env`): attack, decay and release 0-30 s,
    sustain 0-1.  `closed`: no other fields."""
    from .model import number
    if not isinstance(env, dict):
        raise ValueError(f'{track["id"]}: synth {name} must be an object')
    if closed and set(env) - {'attack', 'decay', 'sustain', 'release'}:
        raise ValueError(f'{track["id"]}: synth {name} takes attack, decay, sustain and release; not '
                         + ', '.join(sorted(set(env) - {'attack', 'decay', 'sustain', 'release'})))
    for key in ('attack', 'decay', 'release'):
        number(env.get(key, .01), 0, 30, f'synth {name} {key}')
    number(env.get('sustain', .5), 0, 1, f'synth {name} sustain')


def presets():
    return json.loads(PRESETS_FILE.read_text(encoding='utf-8'))['presets']


def patch_of(track):
    """The track's patch: a named preset (`synth.preset`) with the track's own fields over it, on top of the defaults."""
    spec = dict(track.get('synth') or {})
    base = dict(DEFAULT)
    name = spec.pop('preset', None)
    if name:
        lib = presets()
        if name not in lib:
            raise ValueError(f'{track["id"]}: unknown synth preset {name!r}')
        base.update(lib[name]['patch'])
    base.update(spec)
    return base


def voices(notes, patch):
    """The notes grouped as the patch plays them: one group per voice (see render)."""
    groups = []
    if patch.get('arpeggio'):
        # Notes that start within 30 ms of each other are one chord, played as one voice cycling through its pitches.
        for e in notes:
            if groups and e['start_seconds'] - groups[-1][0]['start_seconds'] < .03:
                groups[-1].append(e)
            else:
                groups.append([e])
    elif patch.get('mono'):
        for e in notes:
            if (groups and e['start_seconds'] <= groups[-1][-1]['end_seconds'] + .001
                    and e['start_seconds'] - groups[-1][0]['start_seconds'] < MONO_LINE_S):
                groups[-1].append(e)
            else:
                groups.append([e])
    else:
        groups = [[e] for e in notes]
    return groups


def voice_held(group, patch):
    """A voice's start and the seconds it is held before its release: to the end of its last note, which owns the
    voice on a mono patch whatever an earlier note's length, and to the latest end of its chord on an arpeggio.  The
    mix reads the same for the time a part sounds (mixbus.held_spans)."""
    start = group[0]['start_seconds']
    end = max(e['end_seconds'] for e in group) if patch.get('arpeggio') else group[-1]['end_seconds']
    return start, max(.005, end - start)


def line_voices(track, clock):
    """The part's voices as render plays them: its performed notes by start and pitch, grouped by voices()."""
    from .model import performed
    patch = patch_of(track)
    return voices(sorted(performed(track, clock), key=lambda e: (e['start_seconds'], e['pitch'])), patch), patch


def seed(text):
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def polyblep(t, dt):
    """The PolyBLEP correction for a unit step at phase 0 (t in [0, 1), dt the phase increment per sample)."""
    out = np.zeros_like(t)
    a = t < dt
    x = t[a] / dt[a]
    out[a] = x + x - x * x - 1
    b = t > 1 - dt
    x = (t[b] - 1) / dt[b]
    out[b] = x * x + x + x + 1
    return out


def saw(phase, dt):
    t = phase % 1.0
    return 2 * t - 1 - polyblep(t, dt)


def pulse(phase, dt, width):
    return saw(phase, dt) - saw(phase + width, dt)


def triangle(phase, freq, rate):
    out = np.zeros_like(phase)
    for k in range(1, 400, 2):
        live = k * freq < .45 * RATE
        if not live.any():
            break
        sign = 1 if (k // 2) % 2 == 0 else -1
        out += np.where(live, sign * np.sin(2 * np.pi * k * phase) / (k * k), 0.0)
    return out * 8 / np.pi ** 2


def stepped_triangle(phase, dt, steps):
    """A triangle through `steps` levels, each held for 1/(2 steps) of a period (16: the NES's 32-step sequence), every
    step a band-limited edge."""
    t = phase % 1.0
    k = np.floor(t * 2 * steps).astype(int)
    level = np.where(k < steps, steps - 1 - k, k - steps)
    out = level * (2.0 / (steps - 1)) - 1
    height = 2.0 / (steps - 1)
    for j in range(1, 2 * steps):
        if j == steps:
            continue  # the two lowest steps are both 0
        edge = (t - j / (2 * steps)) % 1.0
        out += (-1 if j < steps else 1) * height / 2 * polyblep(edge, dt)
    return out


def clocked_noise(phase, rng):
    """Random +-1 values held for one cycle of `phase` each, like a shift register clocked at that rate."""
    cycle = np.floor(phase).astype(np.int64)
    cycle -= cycle[0]
    values = rng.choice((-1.0, 1.0), size=int(cycle[-1]) + 1)
    return values[cycle]


def adsr(n, off, env, rate):
    """An envelope over n samples with the key released at sample `off`: a linear attack, an exponential decay to the
    sustain level (time constants a third of the times given), and an exponential release (a fifth)."""
    a, d, s, r = (max(1e-4, env.get('attack', .005)), max(1e-4, env.get('decay', .1)), env.get('sustain', .8),
                  max(1e-4, env.get('release', .2)))
    t = np.arange(n) / rate
    held = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / (d / 3)))
    at_off = float(held[min(off, n - 1)]) if off < n else float(held[-1])
    # The release from the key's release on; before it the held envelope is used, so its decay is not computed there
    # (where it would overflow on a long note).
    rel = at_off * np.exp(-np.maximum(t - off / rate, 0.0) / (r / 5))
    return np.where(np.arange(n) < off, held, rel)


def lfo(n, spec, rate, beats=None):
    """An LFO over n samples at `rate`.  One in beats (`rate_beats`) follows the beats the voice has played, `beats`
    (one value per sample, from its start: the played clock's, tempo changes and rubato included); one in Hz, time."""
    if not spec:
        return np.zeros(n)
    t = np.arange(n) / rate
    shape = spec.get('shape', 'sine')
    if spec.get('rate_beats') and beats is not None:
        ph = (beats / spec['rate_beats'] + spec.get('phase', 0.0)) % 1.0
    else:
        ph = (spec.get('rate_hz', 5.0) * t + spec.get('phase', 0.0)) % 1.0
    wave = {'sine': np.sin(2 * np.pi * ph), 'triangle': 1 - 4 * np.abs(ph - .5), 'square': np.where(ph < .5, 1.0, -1.0),
            'saw': 2 * ph - 1}[shape]
    delay, fade = spec.get('delay', 0.0), spec.get('fade', 0.0)
    ramp = np.clip((t - delay) / fade, 0, 1) if fade > 0 else (t >= delay).astype(float)
    return wave * ramp


def linear_recursion(A, z, block=64):
    """s[n] = A[n] s[n-1] + z[n] with s[-1] = 0, for 2x2 matrices A (n, 2, 2) and vectors z (n, 2).  Within each block
    of `block` steps the products P[j] = A[j]...A[0] and the response Z[j] from a zero state are built for all blocks at
    once; each block's state is then P[j] times the state entering it plus Z[j], and the states entering the blocks
    solve the same recursion over the blocks' end matrices."""
    n = len(z)
    if n <= block:
        out = np.empty_like(z)
        cur = np.zeros(2)
        for i in range(n):
            cur = A[i] @ cur + z[i]
            out[i] = cur
        return out
    nb = -(-n // block)
    pad = nb * block - n
    if pad:
        A = np.concatenate([A, np.broadcast_to(np.eye(2), (pad, 2, 2))])
        z = np.concatenate([z, np.zeros((pad, 2))])
    A = A.reshape(nb, block, 2, 2)
    z = z.reshape(nb, block, 2)
    P = np.empty_like(A)
    Z = np.empty_like(z)
    P[:, 0], Z[:, 0] = A[:, 0], z[:, 0]
    for j in range(1, block):
        P[:, j] = A[:, j] @ P[:, j - 1]
        Z[:, j] = np.einsum('bik,bk->bi', A[:, j], Z[:, j - 1]) + z[:, j]
    ends = linear_recursion(P[:, -1], Z[:, -1], block)
    entering = np.concatenate([np.zeros((1, 2)), ends[:-1]])
    out = np.einsum('bjik,bk->bji', P, entering) + Z
    return out.reshape(-1, 2)[:n]


ALL_POLE_CHUNK = 1 << 16  # samples whose recursion is solved at once (its matrices take 100 bytes a sample)


def _all_pole(v, a1, a2, state):
    """One chunk of all_pole from the state [y[-1], y[-2]] the chunk before ended in (folded into the first input,
    s[0] = A[0] s[-1] + z[0]); returns the chunk's output and the state it ends in."""
    A = np.empty((len(v), 2, 2))
    A[:, 0, 0], A[:, 0, 1], A[:, 1, 0], A[:, 1, 1] = -a1, -a2, 1.0, 0.0
    z = np.zeros((len(v), 2))
    z[:, 0] = v
    z[0] += A[0] @ state
    s = linear_recursion(A, z)
    return s[:, 0], s[-1]


def all_pole(v, a1, a2):
    """y[n] = v[n] - a1[n] y[n-1] - a2[n] y[n-2], coefficients per sample.  Solved a chunk at a time, each from the
    state the one before ended in, so a note held for minutes does not build its whole recursion at once."""
    n = len(v)
    y, state = np.empty(n), np.zeros(2)
    for i in range(0, n, ALL_POLE_CHUNK):
        j = min(n, i + ALL_POLE_CHUNK)
        y[i:j], state = _all_pole(v[i:j], a1[i:j], a2[i:j], state)
    return y


def biquad(x, kind, cutoff, q, rate):
    """RBJ low-, high- or band-pass with a cutoff (Hz, one per sample) and Q (at least 0.55), in direct form I: a chunk
    at a time, its coefficients with it, the inputs and the recursion carrying on from the chunk before."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=np.float64), (n,))
    q = np.broadcast_to(np.asarray(q, dtype=np.float64), (n,))
    y, state = np.empty(n), np.zeros(2)
    for i in range(0, n, ALL_POLE_CHUNK):
        j = min(n, i + ALL_POLE_CHUNK)
        w0 = 2 * np.pi * np.clip(cutoff[i:j], 15.0, .45 * rate) / rate
        qs = np.maximum(q[i:j], .55)
        cw, alpha = np.cos(w0), np.sin(w0) / (2 * qs)
        a0 = 1 + alpha
        a1, a2 = -2 * cw / a0, (1 - alpha) / a0
        if kind == 'lowpass':
            b0 = (1 - cw) / 2 / a0
            b1, b2 = 2 * b0, b0
        elif kind == 'highpass':
            b0 = (1 + cw) / 2 / a0
            b1, b2 = -2 * b0, b0
        else:
            b0, b1, b2 = alpha / a0, 0.0 * alpha, -alpha / a0
        head = x[max(0, i - 2):i]
        ext = np.concatenate([np.zeros(2 - len(head)), head, x[i:j]])
        y[i:j], state = _all_pole(b0 * ext[2:] + b1 * ext[1:-1] + b2 * ext[:-2], a1, a2, state)
    return y


def resample_down(x, factor):
    """From `factor` times the output rate down to it, through an FFT low-pass at the output's Nyquist frequency."""
    n = len(x)
    m = n // factor
    spec = np.fft.rfft(x[:m * factor], axis=0)
    return np.fft.irfft(spec[:m // 2 + 1], n=m, axis=0) * (m / (m * factor))


def voice(patch, pitch_curve, n_on, n, velocity, note_id, rate, beats):
    """One voice at `rate` (the oversampled rate): `pitch_curve` gives its MIDI pitch per sample; the key is held for
    n_on samples of n; `beats`, the beats played since its start, per sample (lfo).  Returns stereo samples."""
    freq = 440.0 * 2 ** ((pitch_curve - 69) / 12)
    lfo_spec = patch.get('lfo')
    mod = lfo(n, lfo_spec, rate, beats)
    if lfo_spec and lfo_spec.get('to_pitch_cents'):
        freq = freq * 2 ** (mod * lfo_spec['to_pitch_cents'] / 1200)
    rng = np.random.default_rng(seed(note_id))
    out = np.zeros((n, 2))
    for osc in patch['oscillators']:
        f = freq * 2 ** (osc.get('octave', 0) + osc.get('semitones', 0) / 12 + osc.get('cents', 0) / 1200)
        wave, level = osc.get('wave', 'saw'), osc.get('level', 1.0)
        voices = int(osc.get('voices', 7 if wave == 'supersaw' else 1))
        detune, spread = osc.get('detune_cents', 25 if wave == 'supersaw' else 0), osc.get('spread', .8 if wave == 'supersaw' else 0)
        for v in range(voices):
            pos = (v / (voices - 1) - .5) * 2 if voices > 1 else 0.0
            fv = f * 2 ** (pos * detune / 1200)
            dt = fv / rate
            phase = np.cumsum(dt) + (rng.random() if voices > 1 or osc.get('random_phase') else 0.0)
            if wave in ('saw', 'supersaw'):
                sig = saw(phase, dt)
            elif wave in ('square', 'pulse'):
                width = osc.get('width', .5)
                if osc.get('pwm'):
                    width = np.clip(width + osc['pwm'].get('depth', .2) * lfo(n, osc['pwm'], rate, beats), .05, .95)
                sig = pulse(phase, dt, width)
            elif wave == 'triangle':
                sig = stepped_triangle(phase, dt, int(osc['steps'])) if osc.get('steps') else triangle(phase, fv, rate)
            elif wave == 'sine':
                sig = np.sin(2 * np.pi * phase)
            elif wave == 'fm':
                ratio, index = osc.get('ratio', 2.0), osc.get('index', 2.0)
                ienv = adsr(n, n_on, osc.get('index_env', {'attack': .001, 'decay': .5, 'sustain': .3, 'release': .3}), rate)
                sig = np.sin(2 * np.pi * phase + index * ienv * np.sin(2 * np.pi * phase * ratio))
            elif wave == 'noise':
                sig = clocked_noise(phase * 16, rng) * .5 if osc.get('clock') else rng.standard_normal(n) * .5
            else:
                raise ValueError(f'unknown oscillator wave {wave!r}')
            sig = sig * level / math.sqrt(voices)
            pan = pos * spread
            out[:, 0] += sig * math.sqrt((1 - pan) / 2) * math.sqrt(2)
            out[:, 1] += sig * math.sqrt((1 + pan) / 2) * math.sqrt(2)
    filt = patch.get('filter')
    if filt:
        fenv = adsr(n, n_on, patch.get('filter_env') or {}, rate)
        octaves = (filt.get('env_amount', 0.0) * fenv + filt.get('key_track', 0.0) * (pitch_curve - 60) / 12
                   + filt.get('velocity', 0.0) * (velocity - .5) * 2)
        if lfo_spec and lfo_spec.get('to_cutoff_octaves'):
            octaves = octaves + mod * lfo_spec['to_cutoff_octaves']
        cutoff = filt.get('cutoff_hz', 2000.0) * 2 ** octaves
        q = .707 + filt.get('resonance', 0.0) ** 2 * 24
        kind = filt.get('type', 'lowpass')
        for ch in range(2):
            y = biquad(out[:, ch], kind, cutoff, q, rate)
            if filt.get('slope', 12) == 24:
                y = biquad(y, kind, cutoff, np.full(n, .707), rate)
            out[:, ch] = y
    amp = adsr(n, n_on, patch.get('amp') or {}, rate) * velocity ** patch.get('velocity_curve', 1.5)
    if lfo_spec and lfo_spec.get('to_amp'):
        amp = amp * (1 + lfo_spec['to_amp'] * mod)
    out *= amp[:, None]
    drive = patch.get('drive', 0.0)
    if drive > 0:
        k = 1 + 9 * drive
        out = np.tanh(k * out) / math.tanh(k)
    return out


def arpeggio_curve(chord, arp, start, n, rate, beats, clock):
    """The pitch per sample of an arpeggiated chord: one of the notes still held per step, in order; after the last
    note ends the voice keeps the pitch it had.  A step in beats (`rate_beats`) follows the played clock (`beats`, per
    sample since `start`), a step in Hz, time."""
    if arp.get('rate_beats'):
        index = (beats / arp['rate_beats'] + 1e-9).astype(int)
        first = clock.beat(start)
        at = lambda k: clock.seconds(first + k * arp['rate_beats'])
    else:
        step = 1.0 / arp.get('rate_hz', 60)
        index = (np.arange(n) / rate / step).astype(int)
        at = lambda k: start + k * step
    count = int(index[-1]) + 1 if n else 1
    order = arp.get('order', 'up')
    pitches, last = [], float(chord[0]['pitch'])
    for k in range(count):
        t = at(k)
        live = sorted(e['pitch'] for e in chord if e['start_seconds'] - 1e-9 <= t < e['end_seconds'])
        if live:
            if order == 'down':
                live = live[::-1]
            elif order == 'updown' and len(live) > 2:
                live = live + live[-2:0:-1]
            last = float(live[k % len(live)])
        pitches.append(last)
    return np.asarray(pitches)[np.minimum(index, count - 1)]


def render(project, track, path, clock=None):
    """Render a synth part to `path` (stereo float WAV at RATE)."""
    from .model import Clock
    from . import audio
    clock = clock or Clock(project)
    groups, patch = line_voices(track, clock)
    total = round((clock.end + clock.tail) * RATE)
    out = np.zeros((total, 2))
    release = (patch.get('amp') or {}).get('release', .2)
    rate = RATE * OVER
    glide = patch.get('glide_ms', 0) / 1000
    # A mono patch plays one line: a note that starts while the previous one still sounds, or as it ends, takes over
    # its voice, gliding from its pitch; the envelope restarts only after a gap.  A line is synthesized whole at four
    # times the rate, about 60 MB a second, so after MONO_LINE_S of unbroken legato the next note starts afresh.
    arp = patch.get('arpeggio')
    for group in groups:
        first, last = group[0], group[-1]
        start, held = voice_held(group, patch)
        length = held + release * 1.2 + .02
        n = int(round(length * rate))
        n_on = int(round(held * rate))
        t = np.arange(n) / rate + start
        # The beats the voice plays through, from its start: what an LFO or arpeggio in beats follows, so a tempo
        # change or rubato under a held note moves it as it moves the beat.
        beats = audio.beats_at(clock, t) - clock.beat(start)
        pitch = np.full(n, float(first['pitch']))
        if arp:
            pitch = arpeggio_curve(group, arp, start, n, rate, beats, clock)
            group = group[:1]
        for prev, cur in zip(group, group[1:]):
            i = int(round((cur['start_seconds'] - start) * rate))
            if glide > 0:
                tau = glide / 3
                seg = np.arange(n - i) / rate
                pitch[i:] = cur['pitch'] + (pitch[i - 1] - cur['pitch']) * np.exp(-seg / tau)
            else:
                pitch[i:] = cur['pitch']
        pe = patch.get('pitch_env')
        if pe:
            pitch = pitch + pe.get('semitones', 12) * np.exp(-np.arange(n) / rate / pe.get('decay', .03))
        bends = track['performance'].get('bend')
        if bends:
            from .model import bend_curve, curve_at
            bends = bend_curve(bends)
            pitch = pitch + np.array([curve_at(bends, clock.beat(x)) for x in t[::OVER * 48]]).repeat(OVER * 48)[:n]
        y = voice(patch, pitch, n_on, n, first['velocity'] / 127, first['id'], rate, beats)
        y = resample_down(np.pad(y, ((0, (-len(y)) % OVER + OVER * 64), (0, 0))), OVER)
        i0 = int(round(start * RATE))
        m = min(len(y), total - i0)
        if m > 0:
            out[i0:i0 + m] += y[:m]
    out *= 10 ** (patch.get('gain_db', 0.0) / 20) * .25
    audio.write_wav(path, out.astype(np.float32))
    return {'notes': sum(len(g) for g in groups), 'voices': len(groups), 'oversampling': OVER}
