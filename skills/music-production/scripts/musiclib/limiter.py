"""A true-peak look-ahead limiter in NumPy, for the master of the mix's rules of version 2 (mixbus.deliver_2).

The principle is Hamalainen's (2002, "Smoothing of the Control Signal without Clipped Output in Digital Peak Limiters",
Proc. DAFx-02, pp. 195-198): a limiter that delays the signal by N samples can smooth its control signal and still
never let a peak through, if the control signal first passes a running maximum over those N samples and the smoothing
that follows is an average over no more than them.  The paper works on the envelope; its section 3.5 names the same
structure on the gain, with a running minimum, which is the form here:

  need(n)  = min(0, ceiling - peak(n))                   the gain each sample needs, in dB
  held(n)  = min(need(n - H) ... need(n + N))            running minimum over the look-ahead, and H samples back
  rel(n)   = min(held(n), rel(n - 1) * r)                the reduction decays toward 0 dB once the peak has passed
  gain(n)  = sum over j of w(j) * rel(n - j), j = 0..N   weights positive, summing to one

Every rel(k) with n - N <= k <= n is at most held(k), and held(k) covers sample n, so each is at most need(n) and so
is their weighted mean: gain(n) <= need(n) whatever the signal.  The weights are a raised cosine, which bends the
gain more gently than the paper's moving average and keeps the same guarantee.

peak(n) is a true peak: the largest magnitude, over both channels, of the band-limited signal within one sample
either side of n, from interpolation at four times the rate (ITU-R BS.1770-4, annex 2, measures true peak at four
times 48 kHz).  The gain itself is applied at the base rate: it moves slowly, so the product's own peaks between
samples follow it.  Meters interpolate differently, though, so the master aims a little under its ceiling and is
checked by the meter the render's checks use.

Measured beside FFmpeg's alimiter as the rules of version 1 set it (research/design-0.6/limiter_tests.py; attack 5 ms,
release 60 ms), both 6 dB into limiting: harmonic distortion of a 30 Hz sine -129 dB against -30 dB, of a 50 Hz sine
-115 against -37, of 100 Hz and 1 kHz below -140 for both; SMPTE intermodulation (60 Hz and 7 kHz, four to one) -93 dB
against -39; a sine at a quarter of the sample rate whose samples miss its crests, held to -6.02 dBTP, came out at
-6.02 against -3.01 dBTP.  This limiter adds no delay; alimiter's output is 243 samples late.

Nothing here runs sample by sample in Python: the running minimum is van Herk's two-pass one, and the release is a
running maximum of the reduction's logarithm against a ramp.
"""
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .measure import RATE

LOOKAHEAD = .003  # s.  Hamalainen writes that, as a personal opinion, 64 samples (1.3 ms at 48 kHz) "already gives
                  # good results"; FFmpeg's alimiter defaults to 5 ms.  Measured here at 1.5, 3 and 5 ms: the figures
                  # above moved by less than 5 dB, and at 5 ms a tone 12 dB under the ceiling dipped 0.9 dB before a
                  # burst.  3 ms is this skill's choice between them.
# The lowest note whose crests meet one steady gain: A0, the piano's lowest key (27.5 Hz).  Its crests are half a
# period apart, 18.2 ms, which the running minimum's window (hold and look-ahead together) has to span.
LOWEST_STEADY_HZ = 27.5


def true_peak(x, factor=4, block=61440, margin=2048):
    """For each sample of `x` (frames, channels), the largest magnitude of the band-limited signal within one sample
    either side, over the channels: FFT interpolation at `factor` times the rate, in blocks whose margins are
    discarded.  Before its first sample and after its last the signal is silence, as a file's is where it is played:
    a signal that starts or stops at once overshoots there between samples.  In single precision (a peak is read to
    about 1e-4 of full scale, a thousandth of a decibel at the ceiling), with transforms of 2**16 and 2**18 points,
    the blocks three at a time (the transforms release the interpreter's lock; each block is computed alone, so the
    result does not depend on how many run together): 4 s became 1 s for a mix of 238 s."""
    x = np.asarray(x)
    n = len(x)
    out = np.empty(n, dtype=np.float32)

    def one(s):
        a, b = max(0, s - margin), min(n, s + block + margin)
        seg = np.zeros((block + 2 * margin, x.shape[1]), dtype=np.float32)
        seg[a - (s - margin):b - (s - margin)] = x[a:b]
        m = len(seg)
        up = np.abs(np.fft.irfft(np.fft.rfft(seg, axis=0), n=m * factor, axis=0)).max(axis=1) * factor
        pad = np.pad(up, factor - 1, mode='edge')
        around = pad[0::factor][:m].copy()
        for j in range(1, 2 * factor - 1):
            np.maximum(around, pad[j::factor][:m], out=around)
        keep = min(block, n - s)
        out[s:s + keep] = around[margin:margin + keep]
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, range(0, n, block)))
    return out


def running_min(a, width):
    """min(a[i] ... a[i + width - 1]) for every i, the end of `a` counted as it stands (van Herk 1992, Gil and Werman
    1993: one pass forward and one back inside blocks of `width`)."""
    n = len(a)
    b = np.concatenate([a, np.full((-n) % width + width, np.inf)]).reshape(-1, width)
    forward = np.minimum.accumulate(b, axis=1).ravel()
    backward = np.minimum.accumulate(b[:, ::-1], axis=1)[:, ::-1].ravel()
    return np.minimum(backward[:n], forward[width - 1:n + width - 1])


def gain_db(peak, ceiling, release, lookahead=LOOKAHEAD, hold=None):
    """The gain (dB, at most 0) that holds `peak` (linear) under `ceiling` (linear): see the module's text.
    `release`, `lookahead` and `hold` in seconds.  The running minimum reaches `hold` back as well as `lookahead`
    forward, so a peak's reduction stays that long after it: a low note's crests, half a period apart, then meet one
    steady gain instead of a gain that rides the waveform.  Without `hold`, the two together span half a period of
    LOWEST_STEADY_HZ."""
    if hold is None:
        hold = max(0.0, .5 / LOWEST_STEADY_HZ - lookahead)
    need = np.minimum(0.0, 20 * np.log10(ceiling / np.maximum(np.asarray(peak, dtype=np.float64), 1e-12)))
    n, h = int(round(lookahead * RATE)), int(round(hold * RATE))
    held = running_min(np.concatenate([np.zeros(h), need]), n + h + 1)[:len(need)]
    # rel(n) = min(held(n), rel(n-1) * r): with d = -held >= 0, log D(n) = n log r + max over k <= n of (log d(k) - k log r)
    step = -1.0 / (release * RATE)
    ramp = np.arange(len(held)) * step
    rel = -np.exp(ramp + np.maximum.accumulate(np.log(np.maximum(-held, 1e-9)) - ramp))
    w = np.hanning(n + 3)[1:-1]
    w /= w.sum()
    return np.convolve(np.concatenate([np.full(n, rel[0]), rel]), w, mode='valid')


def limit(x, ceiling, release, lookahead=LOOKAHEAD, hold=None):
    """`x` (frames, channels) held under a true peak of `ceiling` (linear), and the gain applied (dB per sample)."""
    g = gain_db(true_peak(x), ceiling, release, lookahead, hold)
    return np.asarray(x, dtype=np.float64) * (10 ** (g / 20))[:, None], g
