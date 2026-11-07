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
