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


# Relative reverb loudness (LU), from De Man, McNally and Reiss (2017, J. Audio Eng. Soc. 65(1/2)): 80 mixes of 10
# recordings by trained engineers, rated by skilled listeners.  Every mix at -9 LU or more was judged too reverberant,
# and -14 LU "appears to be a more desirable loudness as it is in between 95% confidence intervals of the medians of
# either labelled group".  The paper gives the just-noticeable difference of the direct-to-reverberant ratio as 5 to
# 6 dB; the range here is that much around -14 (3 LU either side), which is this skill's reading of those two numbers.
REVERB_TOO_MUCH_LU = -9.0
REVERB_RANGE_LU = (-17.0, -11.0)
# How near the players are heard.  The early-to-late sound index C80 (ISO 3382-1's clarity) is the energy that
# arrives within 80 ms of the direct sound over the energy after it, in dB.  Barron (2013, Applied Acoustics 74,
# 936-944, Table 1) gives -2 to +2 dB as the recommended range at mid frequencies for a seat in a concert hall,
# beside a reverberation time of 1.8 to 2.2 s.  Those songs' mixes above sit far on the clear side of it: at -16 LU of
# reverb the generated hall gives +17.6 dB.  Listeners divide between those who prefer an intimate sound in which
# single instruments are easy to hear and those who prefer a louder, more reverberant, enveloping one (Lokki,
# Patynen, Kuusinen and Tervo 2012, J. Acoust. Soc. Am. 132, 3148-3161; Barron names three groups), and the seat and
# the music change the judgement (the same authors 2016, 140, 551): no one value is right, so a project names its own
# (mix.c80_db) and the range here is what analyze sets a piece beside.
HALL_C80_DB = (-2.0, 2.0)
EARLY_S = .08


def early_share(response):
    """The share of an impulse response's energy in its first 80 ms, counted from its first frame, where the dry sound
    it answers is: the part of a space's return that C80 counts as early."""
    e = np.asarray(response, dtype=np.float64) ** 2
    if e.ndim > 1:
        e = e.sum(axis=1)
    total = float(np.sum(e))
    return float(np.sum(e[:int(EARLY_S * RATE)])) / total if total > 0 else 0.0


def clarity_c80(dry_energy, returns):
    """C80 (dB) of a mix heard as one room: the dry signal is the direct sound, and each space's return is its
    response's energy spread as that response is.  `returns` holds (the return's energy, its response's early share)
    for every space.  None without any late energy.  An estimate from energies: early reflections already in the dry
    signal (a part's stage depth) count as direct sound, which they follow within 80 ms."""
    early = dry_energy + sum(e * f for e, f in returns)
    late = sum(e * (1 - f) for e, f in returns)
    return 10 * math.log10(early / late) if late > 0 and early > 0 else None


def returns_gain_for_c80(dry_energy, returns, target_db):
    """The one gain (dB) on every space's return that brings clarity_c80 to `target_db`: with A the returns' early
    energy and B their late energy, (dry + g^2 A) / (g^2 B) = k gives g^2 = dry / (k B - A).  None where no gain does:
    spaces so short that their own early energy keeps the mix clearer than the target however loud they are."""
    early = sum(e * f for e, f in returns)
    late = sum(e * (1 - f) for e, f in returns)
    rest = 10 ** (target_db / 10) * late - early
    return 10 * math.log10(dry_energy / rest) if rest > 0 and dry_energy > 0 else None


K_SIZE, K_MARGIN = 1 << 16, 4096


@functools.lru_cache(maxsize=1)
def _k_block_response():
    return k_response.__wrapped__(K_SIZE).astype(np.complex64)


def k_power(x):
    """The K-weighted power of `x` at each sample, summed over its channels: k_filter(x) squared, to about 1e-6 of
    it.  The filter runs in single precision over blocks of 2**16 samples whose margins
    (4096 samples, some twenty time constants of the high-pass, its slowest part) are discarded; the mix's rules of
    version 2 measure every bus, its stems and the returns with it, where k_filter's one transform of the whole
    signal took 2 to 4 s for a mix of four minutes and this takes 0.8 s.  `x` is read block by block and never copied
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
    75% overlap its gated measure uses)."""
    power = k_power(x)
    c = np.concatenate([[0.0], np.cumsum(power)])
    window, hop = int(.4 * RATE), int(.1 * RATE)
    starts = np.arange(0, max(1, len(power) - window + 1), hop)
    return -0.691 + 10 * np.log10(np.maximum((c[np.minimum(starts + window, len(power))] - c[starts]) / window, 1e-20))


def integrated(x):
    """Integrated loudness (LUFS) of `x` by ITU-R BS.1770-4: the mean power of its 400 ms blocks (75% overlap) that
    pass the absolute gate at -70 LUFS and then the relative gate 10 LU under the mean of those.  None for silence.
    Computed here, so that two signals in memory are measured alike; a file's loudness for delivery is FFmpeg's."""
    blocks = momentary(x)
    power = 10 ** ((blocks + 0.691) / 10)
    kept = power[blocks > -70]
    if not len(kept):
        return None
    kept = kept[kept > kept.mean() * 10 ** (-10 / 10)]
    return -0.691 + 10 * math.log10(float(kept.mean()))


def relative_loudness(wet, dry, floor=-50.0):
    """The mean, over the measurement windows, of the momentary loudness of `wet` minus that of `dry` (LU): De Man,
    McNally and Reiss's relative reverb loudness (2017, eq. 4) when they are a mix's reverb and its dry signal.  A
    window counts while `dry` is above `floor` LUFS, so the silence around a piece does not enter (the paper's
    passages read do not say which windows it keeps: this choice is the skill's).  None where no window counts."""
    n = min(len(wet), len(dry))
    return windows_difference(momentary(wet[:n]), momentary(dry[:n]), floor)


def windows_difference(w, d, floor=-50.0):
    """relative_loudness from the two signals' momentary loudness, where a caller has measured them already."""
    n = min(len(w), len(d))
    use = d[:n] > floor
    return float((w[:n][use] - d[:n][use]).mean()) if use.any() else None


def crest_squared(x, window=.4):
    """The squared crest factor typical of `x` while it sounds: in each 400 ms window, the largest squared sample over
    the mean square, and of those the median over the windows within 40 dB of the loudest.  2 for a sine, more the
    more percussive.  Ma et al. (2015) take it sample by sample from a peak and an RMS detector with one smoothing
    constant, which the paper takes from another not read here: the window and the median are this skill's.  (OpenAL
    Soft's compressor, written after Giannoulis, Massberg and Reiss 2013, the paper Ma et al. cite for it, smooths
    both detectors over 200 ms: core/mastering.cpp.  The same order of time as the window here.)"""
    x = np.asarray(x)
    if x.dtype != np.float32:
        x = x.astype(np.float64)
    if x.ndim == 1:
        x = x[:, None]
    w = int(window * RATE)
    n = len(x) // w
    if n < 1:
        return None
    sq = (x[:n * w] ** 2).reshape(n, w, x.shape[1])
    mean, peak = sq.mean(axis=(1, 2), dtype=np.float64), sq.max(axis=(1, 2)).astype(np.float64)
    active = mean > mean.max() * 1e-4
    if mean.max() <= 0 or not active.any():
        return None
    return float(np.median(peak[active] / mean[active]))
