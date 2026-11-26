"""MIT. What a sound does while one note is held (0.10 step 3a, research/design-0.10.md): whether it holds its level or
dies away, whether it darkens or brightens on the way, whether its pitch blips at the onset or moves in steps, whether its
level, pitch or brightness swing while the note is held, and how much of its power lies away from the harmonics of its
pitch.  scripts/surge_motion.py measures every Surge XT patch with it on the catalog's probe note; the figures and words
go into references/surge-catalog.json.

The catalog's other figures describe the held part as a whole, and "steady" and "moving" there say whether the centroid
differed between three playings.  These describe the course of one playing, and say what the sound does, not why: a level
swing may be an LFO, a gate or the beating of detuned voices.  So a patch can be steady between playings and swing within
each.  The timbre literature the skill reads names two of them among the acoustic correlates of its semantic dimensions:
centroid fluctuation and inharmonicity, with luminance and mass (Zacharakis, Pastiadis and Reiss 2014;
references/character-words.md).  The lines that give a word are this skill's own, set where each figure separates the
patches that clearly do the thing (the counts are in research/design-0.10.md), as the 10% between playings is; they are not
from listening.  A figure the probe cannot establish is None, and gives no word.

Read in frames of 10 ms.  The level is the two channels' mean power over two periods of the note played (30 ms at least),
so that neither a low note's own ripple nor a channel cancelling the other moves it; the centroid is read on the channels'
summed spectra, and the pitch on the louder channel.  The held part runs from the attack's half-peak to the note-off.
Whether it dies away compares the loudest tenth of its last 300 ms (a gate's whole cycle where it is longer: a level that
swings at a rate, or two or more like silences the level came back from) with the loudest tenth of its first 150 ms, so a
gate's phase does not decide it; a silence at the end longer than any the level came back from is the sound stopped.
Whether it darkens or brightens compares the centroid's median over the last 200 ms with that
over the first 150 ms of the swings' span.  The swings leave out the held part's first 150 ms (the attack settling); a
frame more than 40 dB under the peak counts at that floor for the level, and the centroid is drawn straight across such
frames, so that every frame keeps its place in time; a swing is the spread of a series once a parabola is taken out of it (a decay, a
swell, the bend of a slow sweep), between its 5th and 95th percentiles, with the rate at which it repeats between 1.5 and
20 Hz, and it gets a word only where it repeats: a one-way change of brightness is "darkens" or "brightens", not a swing.
A pitch is a periodicity near the patch's measured pitch; a frame without a clear one has none.  Frames read more than
600 cents from the median (an octave or a fifth: the track's own error) are left out (so a figure whose other notes lie a
fifth or an octave from the pitch it holds most can read no steps); where the clear pitch lies more than
a semitone from its median in a fifth or more of the rest, the patch steps between pitches by itself (an arpeggio or a
sequence in it), and its pitch swing, onset and inharmonic share, which assume one pitch, are not given.  The pitch blip
is the farthest the pitch lies from where it settles over the 80 ms from the first frame within 30 dB of the peak, so a
slow attack does not hide it; it says where the pitch starts, not how soon it arrives.  The pitch swing is read where the
pitch was heard: across a gap of more than 40 ms (a gate's) its course is not known, so it has no rate there.  A rate is
given only where its swing reaches a floor (FLOORS: under it the series' own noise sets a "rate").  The inharmonic share
is read on the channels' summed spectra against two references, the patch's measured pitch and the track's median, on
the same peaks (the owner's question on the marks, 2026-11-25, and Astra's reviews of its fixes; research/design-0.10.md):
where both readings fall on the same side of the line the lesser is the share; where they fall either side, or one
reads no peak, it is not known (None), as neither reference can be shown right.  With a vibrato (a pitch swing that gives
`pitch swings`) where the track's median lies within AGREE cents of the measured pitch, each reference moves from frame
to frame as the track moves, as a vibrato moves every partial with it, and a frame over which the pitch moves more than
twice NEAR, which holds another note (a reading more than SEMITONE off) or which has no reading to move them by, is left
out; otherwise each is held fixed, and a frame whose pitch lies more than NEAR from the track's median is left out (a
glide after the attack, a vibrato with no rate, another note, the track erring).  Where the pitch swings at a rate, both
tests narrow as the track narrows a sine of that rate: a fast vibrato that dwells near its middle and darts to its ends
is narrowed more, and its frames can be judged though its pitch moves further.  Where no vibrato moves the references, a
reading within ASTRAY of an octave or two off is the track's own error and leaves no frame out: so a note the track reads
there counts against the share (one an octave under the pitch held, or a major seventh away), while one an octave over
lies on its harmonics; as the track can read a note an octave from where it is, a note a little over an octave away
counts or is left out by how it is read.  Where a vibrato moves the references, every reading is tested, and a frame
holding one an octave off, another note to them, is left out.  The track reads the louder channel, so a note the other channel alone carries is not heard: it gives no steps, and
its partials count against the share as a partial on one side does (the two cannot be told apart there: a second note
panned to the other channel read 44% inharmonic).  Each reference fails somewhere: the track wavers from frame to frame
(a harmonic mallet read 71% inharmonic frame by frame, 0.4% against the median), sits a little off the partials, which with NEAR allowed can put every partial off (a lead with a vibrato read
85% against its track, 0% against its measured pitch), settles an octave down on a bass or 88 cents off on a patch
sounding an octave under its note, or is pulled toward a strong partial a quarter tone off a harmonic; the measured pitch
can lie off where the sound is (a sine 51 cents over it read 100%).  Where either reference lies under LOWEST Hz there is
no share: an 85 ms frame cannot place harmonics that close within NEAR, and longer frames resolve a tremolo's sidebands
into peaks of their own (11.4% of the read patches under 50 Hz were marked, 2 to 4% elsewhere).  A partial within NEAR of
a harmonic counts as harmonic, and the share counts the peaks up to NEAR over the 16th harmonic of the lower reference
only.

What one held note of 1.2 s cannot tell: a level or brightness that swings slower than about one and a half times a
second (the rates read start there) reads as a lasting change, `decays`, `darkens` or `brightens`, or as none, by where
the note caught it; a gate of about two times a second or slower whose silence holds the end of the hold can read as
`decays`, as one gap and a silence at the end are also a shot, an echo and the end; a level swing faster than about 15 Hz
reads shallower than it is (the level is read over 30 ms); a pitch that swings more than a semitone either way counts as
steps, and a figure whose other notes lie a fifth or an octave from the pitch it holds most can read none.  (The Astra
reviews of step 3, of the whole and of its fixes found these with tones of known course.)"""
import math

import numpy as np

HOP = .01                 # frame step, seconds
SETTLE = .15              # seconds after the half-peak before the swings are read
QUIET_DB = 40.0           # frames this far under the held part's peak are left out of the swings
ONSET = .08               # seconds read for a pitch blip, from the first frame within READABLE_DB of the peak
READABLE_DB = 30.0
STEPS_PCT = 20.0          # share of clear frames over a semitone from the median pitch that makes a patch step
LINES = {'decays': -12.0, 'darkens': -1.0, 'brightens': 1.0, 'pitch blip': 100.0, 'level swings': 6.0, 'pitch swings': 20.0,
         'brightness swings': 1.0, 'inharmonic': 30.0}
WORDS = ('decays', 'darkens', 'brightens', 'pitch blip', 'pitch steps', 'level swings', 'pitch swings', 'brightness swings',
         'inharmonic')
FIGURES = {'decays': 'hold_end_db', 'darkens': 'centroid_drift_oct', 'brightens': 'centroid_drift_oct',
           'pitch blip': 'onset_pitch_cents', 'pitch steps': 'pitch_steps_pct', 'level swings': 'level_swing_db',
           'pitch swings': 'pitch_swing_cents', 'brightness swings': 'centroid_swing_oct', 'inharmonic': 'inharmonic_pct'}
RATES = {'level swings': 'level_swing_hz', 'pitch swings': 'pitch_swing_hz', 'brightness swings': 'centroid_swing_hz'}
FLOORS = {'level': 1.0, 'pitch': 5.0, 'centroid': .1}   # dB, cents, octaves: the least swing a rate is given for
GAP = 4                   # frames a pitch may go unheard and the swing still be followed across (40 ms)
AGREE = 50.0              # cents within which the pitch track's median and the measured pitch are taken to agree
LOWEST = 50.0             # Hz: no inharmonic share where either reference lies under it
NEAR = 40.0               # cents from a harmonic within which a peak counts as on it
ASTRAY = 150.0            # cents from an octave or two off within which a track reading is the track's own error
SEMITONE = 100.0          # cents off the median over which a track reading under a vibrato is another note
BAND = (45.0, 8000.0)     # Hz: where a peak must be placed to count in the inharmonic share
FRAME = 4096 / 48000      # seconds: the inharmonic share's frames, 85 ms at any rate
NO_PITCH = dict(pitch_steps_pct=None, pitch_swing_cents=None, pitch_swing_hz=None, onset_pitch_cents=None, inharmonic_pct=None)


def channels_of(y):
    """The samples as (frames, channels) floats."""
    y = np.asarray(y, dtype=np.float64)
    return y[:, None] if y.ndim == 1 else y


def envelope_db(y, rate, window=HOP):
    """The channels' mean power every 10 ms over `window` seconds from each frame's start, in dB (-120 for silence).  A
    window shorter than two periods of the note ripples at its pitch: a bass's C2 read in 10 ms frames swung by several
    dB that no LFO made."""
    power = np.mean(channels_of(y) ** 2, axis=1)
    hop, w = int(round(HOP * rate)), max(1, int(round(window * rate)))
    n = len(power) // hop
    sq = np.concatenate(([0.0], np.cumsum(power)))
    starts = np.arange(n) * hop
    ends = np.minimum(starts + w, len(power))
    return 10 * np.log10(np.maximum((sq[ends] - sq[starts]) / np.maximum(ends - starts, 1), 1e-12))


def swing(series, floor=0.0, lo=1.5, hi=20.0):
    """(spread between the 5th and 95th percentiles once a parabola is taken out, rate in Hz or None) of a series in
    10 ms frames; (None, None) for fewer than 30 frames.  The rate is the first of the series' autocorrelation peaks over
    0.3, between 1/20 and 1/1.5 s, that reaches nine tenths of the strongest of them: a swing that repeats; None where
    the spread is under `floor`."""
    s = np.asarray(series, dtype=np.float64)
    if len(s) < 30:
        return None, None
    t = np.arange(len(s))
    r = s - np.polyval(np.polyfit(t, s, 2), t)   # a curve taken out: a decay, a swell, the bend of a slow sweep
    spread = float(np.percentile(r, 95) - np.percentile(r, 5))
    ac = np.correlate(r, r, 'full')[len(r) - 1:]
    if ac[0] <= 0 or spread < floor:
        return spread, None
    ac = ac / ac[0]
    first, last = max(1, int(math.ceil(1 / hi / HOP))), min(len(ac) - 1, int(1 / lo / HOP))
    peaks = [k for k in range(first, last) if ac[k] > .3 and ac[k] >= ac[k - 1] and ac[k] >= ac[k + 1]]
    if not peaks:
        return spread, None
    best = max(ac[k] for k in peaks)
    k = next(k for k in peaks if ac[k] >= .9 * best)   # the period, not a ripple before it nor a multiple of it
    return spread, round(1 / (k * HOP), 1)


def pitch_track(mono, rate, f0, start, stop, window=.04, span=2.0):
    """Cents against f0 for each 10 ms frame from `start` to `stop` (frame indices), None where no periodicity stands
    out: the normalized cross-correlation of a window (`window` seconds, at least one and a half periods) with the signal
    after it, over lags from 1/span to span times the period, its first peak nearly as strong as the best taken where it
    reaches 0.6, refined between samples."""
    hop = int(round(HOP * rate))
    lo, hi = max(2, int(rate / (f0 * span))), int(math.ceil(rate * span / f0))
    w = max(int(window * rate), int(1.5 * rate / f0))
    size = 1 << int(math.ceil(math.log2(w + hi + 1)))
    out = []
    for i in range(start, stop):
        seg = mono[i * hop:i * hop + w + hi + 1]
        if len(seg) < w + hi + 1:
            out.append(None)
            continue
        seg = seg - seg[:w].mean()
        a = seg[:w]
        ea = float(np.dot(a, a))
        if ea <= 1e-12:
            out.append(None)
            continue
        r = np.fft.irfft(np.conj(np.fft.rfft(a, size)) * np.fft.rfft(seg, size), size)[:hi + 1]
        sq = np.concatenate(([0.0], np.cumsum(seg ** 2)))
        eb = sq[np.arange(hi + 1) + w] - sq[np.arange(hi + 1)]
        nsdf = 2 * r / np.maximum(ea + eb, 1e-30)
        part = nsdf[lo:hi + 1]
        best = int(np.argmax(part))
        if part[best] < .6:
            out.append(None)
            continue
        k = lo + best
        for j in range(1, best):
            if part[j] >= .9 * part[best] and part[j] >= part[j - 1] and part[j] >= part[j + 1]:
                k = lo + j
                break
        y0, y1, y2 = nsdf[k - 1], nsdf[k], nsdf[min(k + 1, hi)]
        d = (y0 - y2) / (2 * (y0 - 2 * y1 + y2)) if (y0 - 2 * y1 + y2) else 0.0
        out.append(1200 * math.log2(rate / (k + max(-.5, min(.5, d))) / f0))
    return out


def centroid_track(y, rate, start, stop):
    """Spectral centroid (50 Hz-16 kHz) of the channels' summed spectra in each 10 ms frame from `start` to `stop`, in
    octaves against the series' median; None where the frame holds nothing in that band."""
    ch = channels_of(y)
    hop = int(round(HOP * rate))
    n = 2048
    win = np.hanning(n)
    f = np.fft.rfftfreq(n, 1 / rate)
    band = (f >= 50) & (f <= 16000)
    cs = []
    for i in range(start, stop):
        seg = ch[i * hop:i * hop + n]
        if len(seg) < n:
            cs.append(None)
            continue
        p = (np.abs(np.fft.rfft(seg * win[:, None], axis=0)) ** 2).sum(axis=1)
        tot = p[band].sum()
        cs.append(float((f[band] * p[band]).sum() / tot) if tot > 1e-20 else None)
    clear = [c for c in cs if c]
    if not clear:
        return [None] * len(cs)
    mid = float(np.median(clear))
    return [None if not c else math.log2(c / mid) for c in cs]


def inharmonic_share(y, rate, f0, a, b, course=None, first=0, moving=False, low=None, narrow=1.0):
    """Percent of the power of the held part's spectral peaks that lies more than NEAR (40) cents from every harmonic of
    the pitch, on the channels' summed spectra (a partial on one side counts), over frames of FRAME (85 ms at any rate),
    in which a swing's sidebands mostly stay inside the partial's own peak (a full tremolo on a harmonic C4 read under 3%
    up to 18 Hz and 10% at 26 Hz; a 40-cent vibrato at 18 Hz, 1%; frames of 4,096 samples at 96 kHz resolved an 18 Hz
    tremolo on C2 into peaks of its own, 99%).  Each frame in three steps: whether it is read, and against what pitch
    (`frame_shift`); its peaks and their powers (`peaks`); each peak on a harmonic or off it.  The peaks counted reach NEAR
    over the 16th harmonic of `low` (f0 where not given), over which the harmonics lie too close in cents for NEAR to
    tell on from off.  None where no peak stands out or no frame is left.  Detuned voices within NEAR of each other count
    as one partial.

    `course`: the pitch heard, in cents, one value per 10 ms frame from frame `first`, each timed at the middle of the
    signal it was read over (timed by its window's start, an 8 Hz vibrato of 90 cents was judged 20 ms late and read
    35%), None where none was heard.  `moving`: the course moves f0, `low` and the top of the peaks counted with it, as a
    vibrato moves every partial with it (the Astra review of step 3 read a harmonic tone with a vibrato of 75 cents as 75%
    inharmonic against a fixed pitch).  `narrow`: how far the track narrows the patch's pitch swing, by which the cents a
    frame's readings may stray shrink too."""
    ch = channels_of(y)
    n = int(round(FRAME * rate))
    hop = int(round(HOP * rate))
    f = np.fft.rfftfreq(n, 1 / rate)
    win = np.hanning(n)
    low = low or f0
    on = off = 0.0
    for at in range(a, b - n + 1, n // 2):
        heard = None if course is None else [c for c in course[max(0, at // hop - first):max(0, (at + n) // hop - first)] if c is not None]
        moved = frame_shift(heard, moving, narrow, low)
        if moved is None:
            continue
        ref = f0 * moved
        p = (np.abs(np.fft.rfft(ch[at:at + n] * win[:, None], axis=0)) ** 2).sum(axis=1)
        for freq, power in peaks(p, f, min(BAND[1], 16 * 2 ** (NEAR / 1200) * low * moved)):
            if abs(1200 * math.log2(freq / (max(1, round(freq / ref)) * ref))) > NEAR:
                off += power
            else:
                on += power
    return round(float(100 * off / (on + off)), 1) if on + off > 0 else None


def frame_shift(heard, moving, narrow, low):
    """The factor by which a frame's reference moves, or None where the frame is left out; `heard`: the frame's track
    readings against the pitch held most (None: no track to go by).  Under a vibrato (`moving`) the reference moves to the
    readings' median, and the frame is left out where it has no reading to move by (judged unmoved, a harmonic tone whose
    track read an octave off in three frames read 43% from those frames alone), where a reading lies more than SEMITONE
    off (another note: an 800-cent second note under a vibrato read 38%), where `low` moves under LOWEST, or where its
    readings span more than twice NEAR, narrowed as the track narrows the swing (its partials smeared wider than one pitch
    can judge: a 10 Hz vibrato of 75 cents read 47%; one of 150 cents at 14 Hz, tracked as 65 to 83 within each frame,
    66%).  Otherwise the reference stays put, and a frame with a reading more than NEAR off, narrowed likewise, is left
    out, as a fixed pitch cannot judge its partials: a glide (a synth tom still falling after its attack read 46%
    inharmonic, its loudest frame alone), a vibrato with no rate, another note, the track erring, or a fast vibrato that
    the measured pitch does not agree with (180 cents at 18 Hz, the measured pitch 75 cents off, had read 100%)."""
    if heard is None:
        return 1.0
    if not moving:
        return None if heard and max(abs(c) for c in heard) > NEAR * narrow else 1.0
    if not heard:
        return None
    moved = 2 ** (float(np.median(heard)) / 1200)
    if max(abs(c) for c in heard) > SEMITONE or max(heard) - min(heard) > 2 * NEAR * narrow or low * moved < LOWEST:
        return None
    return moved


def peaks(p, f, top):
    """(frequency, power) of each peak of a frame's power spectrum `p` (its bins at `f`) that counts: one standing 10 dB
    over the median of its third of an octave, and of six bins either side at least (at C2 the third of an octave is the
    peak's own bin, which never stands 10 dB over itself: a bass's fundamental was left out and a faint partial read as
    100% inharmonic), so a noise floor gives none; placed in BAND and under `top` (a C2's fundamental at 51.9 Hz lies in a
    bin centred under 50 Hz: tested by the bin, it was left out and a partial of 1% read 100%).  A peak alone is placed
    between bins by a parabola through its bin and the two beside it, which a swing's sidebands, falling on both sides,
    leave in place (a Hann window's two-bin ratio, which reads one side, put a bass under a 16 Hz tremolo 80 cents off
    and read it 60% inharmonic for 15% of its power in the sidebands); a peak with another within four bins, by that ratio
    read on the side away from the other, whose leakage it leaves alone (by the parabola, which leans toward a neighbour, a
    partial 62 cents off a harmonic was taken for 39).  The same place serves its power and the test of it.  Its power is its whole peak, the bins falling away from it within NEAR or two bins, a
    bin two peaks fall to shared by what the window would put there from each (one bin alone read a partial midway
    between bins 1.4 dB low: modes at 1 and 2.75 times, 25.8% off, read 32.1% or 20.1% by where the fundamental fell;
    three bins missed most of a partial a vibrato spread; a shared bin counted by both read 33% for 26%)."""
    step = f[1] - f[0]
    db = 10 * np.log10(np.maximum(p, 1e-30))
    found = []
    for k in range(2, len(p) - 1):
        if f[k] < BAND[0] - step or f[k] > top + step or not (db[k] > db[k - 1] and db[k] >= db[k + 1]):
            continue
        lo_k = min(int(np.searchsorted(f, f[k] / 2 ** (1 / 6))), k - 6)
        hi_k = max(int(np.searchsorted(f, f[k] * 2 ** (1 / 6))), k + 7)
        if db[k] >= np.median(db[max(0, lo_k):hi_k]) + 10:
            found.append(k)
    kept, claims = [], {}
    for k in found:
        beside = [j - k for j in found if j != k and abs(j - k) <= 4]
        if beside:
            away = -1 if min(beside, key=abs) > 0 else 1
            r = math.sqrt(float(p[k + away] / p[k])) if p[k] > 0 else 0.0
            place = k + away * max(-.5, min(.5, (2 * r - 1) / (1 + r)))
        else:
            y0, y1, y2 = db[k - 1], db[k], db[k + 1]
            place = k + max(-.5, min(.5, (y0 - y2) / (2 * (y0 - 2 * y1 + y2)) if (y0 - 2 * y1 + y2) else 0.0))
        freq = place * step
        if freq < BAND[0] or freq > top:
            continue
        width = max(2, int(freq * (2 ** (NEAR / 1200) - 1) / step))
        falls = [k]
        for way in (-1, 1):
            j = k + way
            while abs(j - k) <= width and 0 < j < len(p) and p[j] < p[j - way]:
                falls.append(j)
                j += way
        for j in falls:
            claims.setdefault(j, []).append((len(kept), float(p[k]) * max(lobe(j - place), 1e-9) / max(lobe(k - place), 1e-9)))
        kept.append(freq)
    power = [0.0] * len(kept)
    for j, who in claims.items():
        total = sum(w for _, w in who)
        for i, w in who:
            power[i] += float(p[j]) * w / total
    return list(zip(kept, power))


def lobe(d):
    """A Hann window's power `d` bins from a sinusoid's frequency, 1 at it and 0 from two bins on."""
    d = abs(d)
    if d >= 2:
        return 0.0
    if d < 1e-9:
        return 1.0
    if abs(d - 1) < 1e-9:
        return .25
    return (math.sin(math.pi * d) / (math.pi * d * (1 - d * d))) ** 2


def measure(y, rate, pitch, ratio=None, lead=.05, hold=1.2):
    """The figures of one playing of a probe note: `pitch` the MIDI note played at `lead` seconds and released `hold`
    seconds later; `ratio` the catalog's measured pitch against it (None: no clear pitch, so no pitch figures)."""
    ch = channels_of(y)
    env = envelope_db(ch, rate, max(.03, 2 / (440 * 2 ** ((pitch - 69) / 12))))   # two periods of the note played, 30 ms at least
    on, off = int(round(lead / HOP)), min(len(env), int(round((lead + hold) / HOP)))
    held = env[on:off]
    if len(held) == 0 or held.max() <= -100:
        return {'silent': True}
    peak = float(held.max())
    half = next((i for i in range(on, off) if env[i] >= peak - 6.02), on)
    start = half + int(round(SETTLE / HOP))
    loud = [i for i in range(start, off) if env[i] >= peak - QUIET_DB]
    # every frame in its place, so a rate is a rate: a quieter one is held at the floor 40 dB under the peak (a gate's gaps
    # dip that far), and where the centroid has no meaning there it is drawn straight between the frames around
    ld, lhz = swing(np.maximum(env[start:off], peak - QUIET_DB), FLOORS['level']) if len(loud) >= 30 else (None, None)
    # the end over one period of a level that swings, and over the longest silence the level comes back from (and 100 ms
    # more), 300 ms at least: a gate of 2 Hz open a quarter of the time can be shut for the whole last 300 ms, and read as
    # dying away (the Astra review of the whole of 0.10); a sound that dies to silence does not come back
    gaps, run = [0], 0
    for i in range(half, off):
        if env[i] < peak - QUIET_DB:
            run += 1
        else:
            gaps.append(run)
            run = 0
    # only a gate's silences widen it: two or more the level came back from, within 30% of one another's length, or a level
    # that swings at a rate; and a silence at the end longer than every one the level came back from (by 50 ms) is the sound
    # stopped, read over the last 300 ms.  A shot, one echo and then 410 ms of silence had read as holding its level (the
    # Astra review of the fixes for the whole of 0.10)
    back = sorted(g for g in gaps if g > 3)
    gated = len(back) >= 2 and back[-2] >= .7 * back[-1]
    tail = 30 if run > max(gaps) + 5 else max(30, back[-1] + 10 if gated else 0, int(math.ceil(1 / lhz / HOP)) if lhz else 0)
    first, last = env[half:min(off, half + 15)], env[max(half, off - tail):off]
    out = {'hold_end_db': round(float(np.percentile(last, 90) - np.percentile(first, 90)), 1)}
    out['level_swing_db'], out['level_swing_hz'] = (None if ld is None else round(ld, 1)), lhz
    cent = centroid_track(ch, rate, start, off)
    known = [(i - start, cent[i - start]) for i in loud if cent[i - start] is not None]
    if len(known) >= 30:
        cs = np.interp(np.arange(off - start), [k for k, _ in known], [c for _, c in known])
        oc, chz = swing(cs, FLOORS['centroid'])
        out['centroid_swing_oct'], out['centroid_swing_hz'] = round(oc, 3), chz
        out['centroid_drift_oct'] = round(float(np.median(cs[-20:]) - np.median(cs[:15])), 3)
    else:
        out['centroid_swing_oct'] = out['centroid_swing_hz'] = out['centroid_drift_oct'] = None
    out.update(NO_PITCH)
    if not ratio:
        return out
    mono = ch[:, int(np.argmax((ch[int(lead * rate):int((lead + hold) * rate)] ** 2).sum(axis=0)))]   # the louder channel
    f0 = 440 * 2 ** ((pitch - 69) / 12) * ratio
    track = pitch_track(mono, rate, f0, start, off)
    heard = [(i, c) for i, c in zip(range(start, off), track) if c is not None and env[i] >= peak - QUIET_DB]
    if len(heard) < 30:
        return out
    mid = float(np.median([c for _, c in heard]))
    # a frame read an octave or a fifth off is the track's own error, and is left out; so a figure that steps by fifths or
    # octaves alone reads no steps (the Astra review of the whole of 0.10).  Keeping such frames where four or more in a row
    # held one pitch gave 199 more patches steps, most of them leads, pads, keys and chords rather than sequences: the
    # track wandering among a chord's voices or to a sub-oscillator, so it was taken back (research/design-0.10.md)
    voiced, heard = heard, [(i, c) for i, c in heard if abs(c - mid) <= 600]
    if len(heard) < 30:
        return out
    steps = 100 * sum(abs(c - mid) > 100 for _, c in heard) / len(heard)
    out['pitch_steps_pct'] = round(steps, 1)
    if steps >= STEPS_PCT:
        return out
    near = [(i, c) for i, c in heard if abs(c - mid) <= 100]
    if len(near) >= 30:
        # every frame in its place: the pitch is drawn straight across the frames where it was not heard, and a gap over
        # GAP frames (a gate's) leaves the swing without a rate (a gated 5 Hz vibrato read 8.3 Hz with the gaps closed up)
        at = np.array([i for i, _ in near])
        pc, phz = swing(np.interp(np.arange(at[0], at[-1] + 1), at, [c for _, c in near]), FLOORS['pitch'])
        if int(np.max(np.diff(at))) > GAP + 1:
            phz = None
        out['pitch_swing_cents'], out['pitch_swing_hz'] = (None if pc is None else round(pc, 1)), phz
    centre = f0 * 2 ** (mid / 1200)
    readable = next((i for i in range(on, off) if env[i] >= peak - READABLE_DB), half)
    early = [c for c in pitch_track(mono, rate, centre, readable, readable + int(round(ONSET / HOP)), window=.01, span=1.5) if c is not None]
    out['onset_pitch_cents'] = round(max(abs(c) for c in early), 1) if early else None
    # two references, the measured pitch and the track's median (the module's docstring), read on the same peaks (up to
    # the lower one's 16th harmonic): each moved frame by frame with a vibrato heard where the track agrees, else held
    # fixed; the lesser where both readings fall on the same side of the line, else not known, as is a reading of one
    # alone; nothing where either lies under LOWEST Hz
    if min(f0, centre) < LOWEST:
        return out
    a_s, b_s = int(start * HOP * rate), int(off * HOP * rate)
    reach = max(.04, 1.5 / f0) + 1 / centre   # seconds a track value is read over: its window and a period
    vibrato = (out['pitch_swing_cents'] or 0) >= LINES['pitch swings'] and out['pitch_swing_hz'] is not None
    # reading over `reach` narrows a swing of rate R by sinc(R x reach): R the swing's own or the one its crossings of its
    # middle give (each a move from a quarter of its half-swing, five cents at least, under its middle to as far over it,
    # so the track's jitter crosses nothing), whichever is faster, as an 18 Hz vibrato's swing read 9.1 Hz; no share at
    # all for a swing the track cannot follow.  Only where the track follows the pitch, within 600 cents of the measured
    # one: a membrane's track, wandering among sub-harmonics 1,100 cents down, had narrowed the test by its own wander
    # and left out the frames that made it inharmonic.  A swing past the line for `pitch swings` with no rate of its own
    # (a gap of over 40 ms takes it) goes by its crossings alone (an 18 Hz vibrato with one 120 ms gap read 100%)
    narrow = 1.0
    swung = out['pitch_swing_hz'] or (out['pitch_swing_cents'] or 0) >= LINES['pitch swings']
    if swung and abs(mid) <= 600:
        at = np.array([i for i, _ in near])
        s = np.interp(np.arange(at[0], at[-1] + 1), at, [c for _, c in near])
        s = s - np.polyval(np.polyfit(np.arange(len(s)), s, 2), np.arange(len(s)))
        rim, side, crossings = max(FLOORS['pitch'], (out['pitch_swing_cents'] or 0) / 8), 0, 0
        for v in s:
            if abs(v) >= rim and np.sign(v) != side:
                crossings += side != 0
                side = np.sign(v)
        narrow = float(np.sinc(max(out['pitch_swing_hz'] or 0, crossings / 2 / (len(s) * HOP)) * reach))
        if narrow <= 0:
            return out
    # the readings more than 600 cents off, which the steps leave out, are tested too (a second note 800 cents up had
    # passed and read 37%); with the references fixed, but for those an octave or two off within ASTRAY, the track's own
    # error: on a clangorous patch it lands there loosely (1,100 to 1,310 cents off), and testing them left most of its
    # frames out.  Moving references test them all: to a reference that follows the track, a reading an octave off is
    # another note (a frame holding the end of an accented note 1,100 cents up had kept one reading and read 52%)
    moving = vibrato and abs(mid) <= AGREE
    kept = voiced if moving else [(i, c) for i, c in voiced
                                  if abs(c - mid) <= 600 or min(abs(abs(c - mid) - 1200), abs(abs(c - mid) - 2400)) > ASTRAY]
    course = dict((i, c - mid) for i, c in kept)
    both = [inharmonic_share(ch, rate, ref, a_s, b_s, [course.get(i) for i in range(start, off)], start + int(round(reach / 2 / HOP)),
                             moving, min(f0, centre), narrow) for ref in (f0, centre)]
    if None not in both and (both[0] >= LINES['inharmonic']) == (both[1] >= LINES['inharmonic']):
        out['inharmonic_pct'] = min(both)
    return out


def words(m):
    """The words the figures give, at this skill's lines (LINES), in the order of WORDS.  A swing is named only where it
    repeats (a rate was found): a level that only wanders, as many detuned voices make it, gives figures but no word."""
    if m.get('silent'):
        return []
    drift = m.get('centroid_drift_oct')
    have = {
        'decays': m.get('hold_end_db') is not None and m['hold_end_db'] <= LINES['decays'],
        'darkens': drift is not None and drift <= LINES['darkens'],
        'brightens': drift is not None and drift >= LINES['brightens'],
        'pitch blip': (m.get('onset_pitch_cents') or 0) >= LINES['pitch blip'],
        'pitch steps': (m.get('pitch_steps_pct') or 0) >= STEPS_PCT,
        'level swings': (m.get('level_swing_db') or 0) >= LINES['level swings'] and m.get('level_swing_hz') is not None,
        'pitch swings': (m.get('pitch_swing_cents') or 0) >= LINES['pitch swings'] and m.get('pitch_swing_hz') is not None,
        'brightness swings': (m.get('centroid_swing_oct') or 0) >= LINES['brightness swings'] and m.get('centroid_swing_hz') is not None,
        'inharmonic': (m.get('inharmonic_pct') or 0) >= LINES['inharmonic'],
    }
    return [w for w in WORDS if have[w]]
