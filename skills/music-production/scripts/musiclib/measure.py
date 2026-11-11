"""Loudness-style measurements in NumPy alone: BS.1770 K-weighting applied in the frequency domain.

The K-weighting filter (a high-frequency shelf, then the RLB high-pass) is applied by multiplying the spectrum
of a whole song or section by the filter's response.  Over a song this matches running the two biquads in time,
apart from the first few milliseconds.  Levels are ungated means, comparable between sections and stems, not an
integrated loudness; the master's integrated loudness comes from FFmpeg (audio.measure).
"""
import functools
import math

import numpy as np

RATE = 48000
# ITU-R BS.1770-4 K-weighting at 48 kHz: (b, a) of the shelf and of the RLB high-pass.
SHELF = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585])
RLB = ([1, -2, 1], [1, -1.99004745483398, 0.99007225036621])


@functools.lru_cache(maxsize=2)
def k_response(n):
    """Complex K-weighting response at the rfft bins of an n-sample signal, read-only.  Kept for the last two lengths
    while a stage measures (a render measures every bus and its stems at one length, and computing the response took
    as long as the FFT); release() lets them go when the stage is done: n/2 + 1 complex values are about 115 MB for a
    five-minute song."""
    z = np.exp(-2j * np.pi * np.fft.rfftfreq(n))
    h = np.ones(len(z), dtype=complex)
    for b, a in (SHELF, RLB):
        h *= (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)
    h.setflags(write=False)
    return h


def release():
    """Drop the kept K-weighting responses: called when a render or an analysis has done its measuring."""
    k_response.cache_clear()


def fast_length(n):
    """The smallest 2^a * 3^b * 5^c of at least n.  A song's sample count often has a large prime factor (4,285,090 =
    2 * 5 * 428,509), and an FFT of that length takes about four times as long."""
    best, p5 = 1 << (n - 1).bit_length(), 1
    while p5 < best:
        p35 = p5
        while p35 < best:
            q = p35
            while q < n:
                q *= 2
            best, p35 = min(best, q), p35 * 3
        p5 *= 5
    return best


def k_filter(x):
    """K-weighted copy of x (frames, or frames x channels) as float64.  The signal is zero-padded to a fast FFT
    length, which also keeps the filter's decay from wrapping round to the start."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 2:
        return np.zeros_like(x)
    m = fast_length(len(x))
    h = k_response(m)
    spectrum = np.fft.rfft(x, n=m, axis=0)
    return np.fft.irfft(spectrum * (h if x.ndim == 1 else h[:, None]), n=m, axis=0)[:len(x)]


def level(y):
    """Ungated mean level of an already K-weighted signal, summed over channels as BS.1770 does (LUFS-like)."""
    y = np.asarray(y, dtype=np.float64)
    if y.ndim == 1:
        y = y[:, None]
    power = float(np.mean(y ** 2, axis=0).sum()) if len(y) else 0.0
    return -0.691 + 10 * math.log10(max(power, 1e-20))


def k_level(x):
    return level(k_filter(x))


# How near the players are heard.  The early-to-late sound index C80 (ISO 3382-1's clarity) is the energy of a room's
# impulse response within 80 ms of the direct sound, the direct sound included, over the energy after, in dB.  Barron
# (2013, Applied Acoustics 74, 936-944) gives -2 to +2 dB in its Table 1, "Recommended ranges for objective measures
# at mid-frequencies for concert halls", beside a reverberation time of 1.8 to 2.2 s; the paper takes mid frequency
# as "mean values for the octaves 500, 1000 and 2000 Hz", and calls the table's ranges those "of acceptability for
# occupied concert hall use".  Listeners
# divide between those who prefer an intimate sound in which single instruments are easy to hear and those who prefer
# a louder, more reverberant, enveloping one (Lokki, Patynen, Kuusinen and Tervo 2012, J. Acoust. Soc. Am. 132,
# 3148-3161; Barron names three groups), and the seat and the music change the judgement (the same authors 2016, 140,
# 551): no one value is right, so a project names its own (mix.c80_db) and the range here is what analyze sets a
# piece beside.
#
# What is computed here is that index for the response a mix gives its parts: the direct sound, and each space's
# response at the level the parts send to it (clarity_c80).  It is taken from impulse responses in the same three
# octaves, as the index is defined.  It is not a hall's: a generated space has no stage, no seats and no audience,
# and the first reflections a part's stage depth adds to its dry sound count here as direct sound.  The two say the
# same thing of the balance of early and late sound and nothing of a hall's other measures.  The parts enter as the
# project writes them (mixbus.written_energies), never as their audio measures: what a part's sound does within
# its notes does not change it, and how long the notes are written does.
HALL_C80_DB = (-2.0, 2.0)
EARLY_S = .08
MID_OCTAVES_HZ = (500.0, 1000.0, 2000.0)


def biquad(kind, hz, freqs):
    """The response at `freqs` (Hz) of FFmpeg's `highpass` or `lowpass` filter as the mix's graph writes it (two
    poles, Q 0.707): the Audio EQ Cookbook's pair.  Checked against FFmpeg itself (research/design-0.6/biquad_check.py,
    FFmpeg 9.0): an impulse through each space's two filters came out within 5e-5 of the same impulse through this
    response, and the magnitudes agree within 0.09 dB from 20 Hz to 20 kHz."""
    w = 2 * math.pi * hz / RATE
    cs, alpha = math.cos(w), math.sin(w) / (2 * math.sqrt(.5))
    b = ((1 + cs) / 2, -(1 + cs), (1 + cs) / 2) if kind == 'highpass' else ((1 - cs) / 2, 1 - cs, (1 - cs) / 2)
    z = np.exp(-2j * np.pi * np.asarray(freqs) / RATE)
    return (b[0] + b[1] * z + b[2] * z * z) / (1 + alpha - 2 * cs * z + (1 - alpha) * z * z)


def early_late(response, highpass_hz=None, lowpass_hz=None):
    """For each of MID_OCTAVES_HZ: (early, late), the energy a space gives back within 80 ms and after them, for one
    unit of energy sent into it.  `response` is the space's impulse response (frames, or frames x channels), counted
    from its first frame, where the sound it answers is; `highpass_hz` and `lowpass_hz` are the filters on its return.
    The response is cut at 80 ms first and each piece's energy in the octave is then read from its spectrum, between
    the octave's edges (the centre over and times the square root of two): a band filter run first would ring across
    the cut.  That order and the edges are this skill's choice; of the standard only the definition was read, in
    Barron's paper."""
    h = np.asarray(response, dtype=np.float64)
    if h.ndim == 1:
        h = h[:, None]
    n = fast_length(len(h) + RATE)  # a second of room for the filters to ring out
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    path = np.zeros((n, h.shape[1]))
    path[:len(h)] = h
    if highpass_hz or lowpass_hz:
        spectrum = np.fft.rfft(path, axis=0)
        for kind, hz in (('highpass', highpass_hz), ('lowpass', lowpass_hz)):
            if hz:
                spectrum = spectrum * biquad(kind, hz, freqs)[:, None]
        path = np.fft.irfft(spectrum, n=n, axis=0)
    cut = int(EARLY_S * RATE)
    early = np.abs(np.fft.rfft(path[:cut], n=n, axis=0)) ** 2
    late = np.abs(np.fft.rfft(path[cut:], n=n, axis=0)) ** 2
    out = []
    for centre in MID_OCTAVES_HZ:
        band = (freqs >= centre / math.sqrt(2)) & (freqs < centre * math.sqrt(2))
        unit = int(band.sum()) * h.shape[1]  # an impulse of one in every channel has one in every bin
        out.append((float(early[band].sum()) / unit, float(late[band].sum()) / unit))
    return out


def clarity_c80(dry_energy, spaces, gain_db=0.0):
    """C80 (dB) of a mix heard as one room, at mid frequencies as Barron (2013) gives it: in each of the octaves of
    500, 1000 and 2000 Hz, the energy within 80 ms of the direct sound over the energy after, and the mean of the
    three in dB.  The direct sound is the mix's dry signal (`dry_energy`); each of `spaces` is (the energy the parts
    send into the space, its early_late), and its return stands `gain_db` from where it was written.

    For one part this is the index of its impulse response, the direct sound and the space's answer at the part's
    send: the notes played do not enter.  With several parts and sends they enter only as weights, each part counting
    by its written level and the time it sounds (mixbus.written_energies); that weighting is this skill's.  None
    without late energy."""
    g = 10 ** (gain_db / 10)
    values = []
    for k in range(len(MID_OCTAVES_HZ)):
        early = dry_energy + g * sum(sent * ratios[k][0] for sent, ratios in spaces)
        late = g * sum(sent * ratios[k][1] for sent, ratios in spaces)
        if early <= 0 or late <= 1e-12 * early:  # nothing after 80 ms but what the arithmetic leaves
            return None
        values.append(10 * math.log10(early / late))
    return sum(values) / len(values)


def returns_gain_for_c80(dry_energy, spaces, target_db, most_db):
    """The one gain (dB) on every space's return, no further than `most_db` either way, that brings clarity_c80
    nearest `target_db`.  The clarity falls as the returns rise, so the gain is found by halving the span.  None
    without late energy (no part sends anything that sounds)."""
    if clarity_c80(dry_energy, spaces) is None:
        return None
    lo, hi = -float(most_db), float(most_db)
    if clarity_c80(dry_energy, spaces, hi) >= target_db:
        return hi  # the returns at their loudest still leave the mix clearer than asked
    if clarity_c80(dry_energy, spaces, lo) <= target_db:
        return lo
    for _ in range(60):
        mid = (lo + hi) / 2
        if clarity_c80(dry_energy, spaces, mid) > target_db:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


K_SIZE, K_MARGIN = 1 << 16, 4096


@functools.lru_cache(maxsize=1)
def _k_block_response():
    return k_response.__wrapped__(K_SIZE).astype(np.complex64)


def k_power(x):
    """The K-weighted power of `x` at each sample, summed over its channels: k_filter(x) squared, to about 1e-6 of
    it.  The filter runs in single precision over blocks of 2**16 samples whose margins
    (4096 samples, some twenty time constants of the high-pass, its slowest part) are discarded; k_filter's one
    transform of the whole signal took 2 to 4 s for a mix of four minutes, where this takes 0.8 s.  `x` is read block by block and never copied
    whole, so a file's samples can be given as they are mapped."""
    x = np.asarray(x)
    if x.ndim == 1:
        x = x[:, None]
    n, step = len(x), K_SIZE - 2 * K_MARGIN
    h = _k_block_response()[:, None]
    out = np.empty(n)
    for s in range(0, n, step):
        a, b = max(0, s - K_MARGIN), min(n, s + step + K_MARGIN)
        seg = np.zeros((K_SIZE, x.shape[1]), dtype=np.float32)
        seg[a - (s - K_MARGIN):b - (s - K_MARGIN)] = x[a:b]
        y = np.fft.irfft(np.fft.rfft(seg, axis=0) * h, n=K_SIZE, axis=0)
        keep = min(step, n - s)
        out[s:s + keep] = (y[K_MARGIN:K_MARGIN + keep].astype(np.float64) ** 2).sum(axis=1)
    return out


def momentary(x):
    """Momentary loudness (LUFS) of `x` as BS.1770 defines it, K-weighted in 400 ms windows, here every 100 ms (the
    75% overlap its gated measure uses).  A signal shorter than one window gives one value, the window filled out
    with silence (this skill's reading, see integrated)."""
    power = k_power(x)
    c = np.concatenate([[0.0], np.cumsum(power)])
    window, hop = int(.4 * RATE), int(.1 * RATE)
    starts = np.arange(0, max(1, len(power) - window + 1), hop)
    return -0.691 + 10 * np.log10(np.maximum((c[np.minimum(starts + window, len(power))] - c[starts]) / window, 1e-20))


def integrated(x):
    """Integrated loudness (LUFS) of `x` by ITU-R BS.1770-4: the mean power of its 400 ms blocks (75% overlap) that
    pass the absolute gate at -70 LUFS and then the relative gate 10 LU under the mean of those.  None for silence.
    Computed here, so that two signals in memory are measured alike; a file's loudness for delivery is FFmpeg's.

    A signal shorter than one block (400 ms) has no integrated loudness in the standard, which counts whole blocks
    only.  Here it is read as one block, with silence after it, so that a bus of a few milliseconds still has a level
    to be matched by: that reading is this skill's and not BS.1770's (100 ms of a tone reads 6 dB under the tone)."""
    blocks = momentary(x)
    power = 10 ** ((blocks + 0.691) / 10)
    kept = power[blocks > -70]
    if not len(kept):
        return None
    kept = kept[kept > kept.mean() * 10 ** (-10 / 10)]
    return -0.691 + 10 * math.log10(float(kept.mean()))
