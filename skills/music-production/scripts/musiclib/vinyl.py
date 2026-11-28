"""A worn record's surface noise for the noise engine's `vinyl` articulation (audio.noise_fx), and the zero-phase band
filter it uses.  Moved verbatim from production.py in 0.11: a noise part's raw take is made from this code, so it stays in
the synthesis closure (render.SYNTHESIS) while production.py, the mix's processing, leaves it (research/design-0.11.md).
production.py imports both back."""
import numpy as np

from .measure import fast_length
from .synth import RATE


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
