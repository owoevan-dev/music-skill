"""A guitar or bass amplifier and loudspeaker for a part recorded from a pickup (`mix.amp`).

A direct recording of an electric guitar is the signal that leaves the instrument: it is meant to go through an
amplifier.  This chain is that amplifier: `{"voice": "crunch", "drive": 0.5}` on the part.  It runs first in the
part's processing, on the part's whole dry synthesis, so all the notes sounding together pass one set of curves: a
chord's notes then make sum and difference tones with one another, as they do in an amplifier, which separately
distorted notes added afterwards cannot.  The amplifier's output is then brought to the part's `level_dbfs` and goes
through the rest of the part's mix as any synthesis does.

The structure is the one the literature gives for a guitar amplifier (Pakarinen and Yeh 2009, a review): a
conditioning filter, gain stages in cascade (each a low-pass, a memoryless curve, a high-pass and a sign inversion),
a tone filter, a power stage and a linear filter for the loudspeaker; "filter, memoryless nonlinearity, filter" is
also how distortion pedals are modelled (Yeh, Abel and Smith 2007).  The curves are tanh; a fixed offset makes a
stage's two half-waves unequal (even harmonics), and the power stage has none (a push-pull stage is odd).

How it is computed.  The part is folded to one channel (a pickup is one signal).  It is taken in blocks with a
pre-roll and a post-roll; each block is transformed once, the linear filters are multiplied in as the frequency
responses of their analog prototypes (nothing is warped by a bilinear transform), the block is brought to OVERSAMPLE
times the sample rate by zero-padding its spectrum, the curves are applied there with their filters between, and the
block comes back down through the same transform.  The pedal paper reports that digital distortions usually run at
eight or ten times the rate; here the residue against 32 times is measured by the selfcheck.  The band's upper edge,
on the way up and on the way down, is a raised-cosine slope from GUARD_HZ to half the sample rate and not a cut: a
cut rings for thousands of samples (as 1/t), and a block's edges then reached its kept part (the first build: a
block of another size, or silence appended to the part, changed the output by -85 dB of its peak; with the slope,
by less than -200 dB).  A curve has no memory, the filters' responses die away inside the pre-roll and the slope's
ringing within a few dozen samples (the slope is ahead of the curves too: what a part holds above GUARD_HZ, which a
pickup's signal hardly does, is lowered before it is distorted), so a block's kept part depends on nothing outside
its rolls: the result does
not depend on the block size or on the part's length, memory is bounded by the block, and a note changed in one
place changes the amplifier's output only there and for the filters' settling time after it.

The input level is fixed, not measured from the piece: `BANKS` holds, for each bank whose level was measured, the gain
that brings its dry synthesis to the chain's working level (a hard full chord peaking near 1).  So playing harder
drives the curves harder, as on an amplifier.  A bank is known by its file (`BANK_FILES`: the SoundFont's SHA-256)
wherever a renderer configuration says which file a part plays: the same file under another name has its gain, and
another file under its name has none.  Without a configuration (`review` alone) it is known by its name in the
lock.  A part on another bank gets no such gain (its `input_db`, 0 unless written, is all it has); its receipt's
`input_peak` shows how hard it drove the chain.

The voice `bass` is the same chain for a bass guitar: its filters let the instrument's lowest notes through (the
guitar voices lower them: through the whole `crunch` chain a soft 41 Hz tone comes out 30 dB under one at 165
Hz); what is under 250 Hz is lowered ahead of its
stage's curve and raised again after it by the same filter's reciprocal, ahead of the power stage, so that the
stage's curve works on a note's harmonics more than on its fundamental and the two filters cancel where the signal
is not bent; its loudspeaker filter has the range a maker states for bass guitar loudspeakers.  The bass banks' levels in `BANKS` bring their hardest single note to the working level (a
bass line is single notes; the guitar bank's reference is a hard chord).  Their makers do not say whether the
recordings are a pickup's signal or a loudspeaker's, and the takes' spectra did not tell (research/guitar-0.9/
bass_probe.py: the direct and the amplified guitar banks, which are known, read alike on that measure).

Every number of a voice below is marked: the source it comes from, or "provisional": chosen here, with no published
figure beside it.
"""
import math

import numpy as np

RATE = 48000
OVERSAMPLE = 8
BLOCK, PRE, POST, PAD = 32768, 16384, 2048, 4096   # samples at RATE: the kept part, its rolls, room for filter tails
TAPER = 256
DRIVE_SPAN_DB = 24.0      # provisional: `drive` from 0 to 1 moves the first stage's gain over this range
OUTPUT_DB = -12.0         # the chain's output near its input's level; the part is levelled after it
GUARD_HZ = 18000.0        # the band's upper edge slopes from here to RATE / 2 (the loudspeaker filter is far below)
FOLD_FLOOR_DB = -120.0    # what `fold_loss_db` says of a part whose two channels cancel entirely

# Voices, named by character.  [YAS]: the overdrive pedal's RC corner, 720 Hz (Yeh, Abel and Smith 2007).  [CEL]: a
# maker's nominal range for a 12-inch guitar loudspeaker, 75 Hz to 5 kHz (Celestion's specifications).  [PY]: the
# structure (Pakarinen and Yeh 2009).  [CELB]: the same maker's ranges for two bass guitar loudspeakers, 45 Hz and
# 40 Hz to 3.5 kHz (Celestion's specifications).  Everything not marked is provisional.
_CAB = {'highpass': (80.0, 1.1), 'peaks': [(2700.0, 3.5, 1.3), (420.0, -2.0, 0.9)], 'lowpass': [(5000.0, 0.54), (5000.0, 1.31)]}   # edges [CEL]
VOICES = {
    'clean': {'input_highpass_hz': 60.0, 'drive_shelf': (720.0, -3.0),
              'stages': [{'gain_db': 6.0, 'bias': 0.10, 'lowpass_hz': 12000.0, 'highpass_hz': 80.0}],
              'tone': [('peak', 550.0, -5.0, 0.7), ('high_shelf', 2500.0, 3.0)], 'power_db': 0.0,
              'cabinet': {'highpass': (90.0, 0.9), 'peaks': [(3000.0, 3.0, 1.2)], 'lowpass': [(5000.0, 0.54), (5000.0, 1.31)]}},
    'edge': {'input_highpass_hz': 60.0, 'drive_shelf': (720.0, -6.0),
             'stages': [{'gain_db': 16.0, 'bias': 0.25, 'lowpass_hz': 10000.0, 'highpass_hz': 100.0}],
             'tone': [('peak', 600.0, -4.0, 0.7), ('high_shelf', 2400.0, 2.0)], 'power_db': 4.0, 'cabinet': _CAB},
    'crunch': {'input_highpass_hz': 60.0, 'drive_shelf': (720.0, -9.0),
               'stages': [{'gain_db': 26.0, 'bias': 0.30, 'lowpass_hz': 9000.0, 'highpass_hz': 110.0},
                          {'gain_db': 12.0, 'bias': 0.15, 'lowpass_hz': 7000.0, 'highpass_hz': 90.0}],
               'tone': [('peak', 650.0, -4.0, 0.7), ('high_shelf', 2400.0, 2.0)], 'power_db': 4.0, 'cabinet': _CAB},
    'lead': {'input_highpass_hz': 60.0, 'drive_shelf': (720.0, -10.0),
             'stages': [{'gain_db': 28.0, 'bias': 0.30, 'lowpass_hz': 8000.0, 'highpass_hz': 120.0},
                        {'gain_db': 16.0, 'bias': 0.15, 'lowpass_hz': 6500.0, 'highpass_hz': 100.0}],
             'tone': [('peak', 800.0, 2.0, 0.8), ('high_shelf', 2400.0, 1.0)], 'power_db': 6.0, 'cabinet': _CAB},
    'high_gain': {'input_highpass_hz': 70.0, 'drive_shelf': (720.0, -14.0),
                  'stages': [{'gain_db': 30.0, 'bias': 0.20, 'lowpass_hz': 9000.0, 'highpass_hz': 140.0},
                             {'gain_db': 16.0, 'bias': 0.15, 'lowpass_hz': 7000.0, 'highpass_hz': 120.0},
                             {'gain_db': 10.0, 'bias': 0.10, 'lowpass_hz': 6000.0, 'highpass_hz': 100.0}],
                  'tone': [('peak', 600.0, -6.0, 0.7), ('high_shelf', 2400.0, 3.0)], 'power_db': 3.0,
                  'cabinet': {'highpass': (95.0, 1.3), 'peaks': [(2600.0, 4.0, 1.3), (450.0, -3.0, 1.0)], 'lowpass': [(5000.0, 0.54), (5000.0, 1.31)]}},
    # A bass guitar's: the low strings pass (E1 is 41 Hz, a five-string's B0 31 Hz).  What lies under 250 Hz is lowered
    # by 6 dB ahead of the stage's curve (`drive_shelf`) and raised again after it by that shelf's reciprocal (the
    # tone's `unshelf`), ahead of the power stage: the stage's curve works on the harmonics more than on the
    # fundamental, and for a signal too soft to be bent the two cancel at every frequency.
    'bass': {'input_highpass_hz': 15.0, 'drive_shelf': (250.0, -6.0),
             'stages': [{'gain_db': 8.0, 'bias': 0.15, 'lowpass_hz': 6000.0, 'highpass_hz': 15.0}],
             'tone': [('unshelf', 250.0, -6.0)], 'power_db': 2.0,
             'cabinet': {'highpass': (42.0, 0.8), 'peaks': [], 'lowpass': [(3500.0, 0.54), (3500.0, 1.31)]}},   # edges [CELB]
}

# Banks whose level was measured: (soundfont, "bank:program") -> the gain in dB that brings the skill's dry synthesis of
# the bank to the working level.  Our measurement (2026-11-19, FluidSynth 2.6.1 at the skill's gain of 0.55, the MIDI
# writer's controllers: volume 100, expression 100): a six-string E major chord at velocity 127 peaks at -6.27 dBFS.
# The bass banks (the same day and settings): their loudest single note at velocity 127 peaks at -15.00 dBFS on the
# two FreePats basses (every note of them does) and at -18.07 dBFS on the fingered five-string (its A1; its other
# notes lie up to 11 dB under that, and its staccato preset was not measured; at velocity 64 its loudest note peaks
# at -42.83 dBFS, 24.8 dB lower: research/guitar-0.9/bass_level.py).
BANKS = {('fsbs_direct', '0:0'): 6.27, ('bass_pick', '0:0'): 15.0, ('bass_finger', '0:0'): 15.0, ('bass_darkblack', '0:33'): 18.07}
# The banks' files: name in the lock -> the SoundFont's SHA-256 (references/soundbank-lock.json: an archive's
# member_sha256, a built bank's output_sha256).
BANK_FILES = {'fsbs_direct': 'cd0b9d1e239148c3ad29acc43090b463c6d887f7d3cecb05b4b292be84a86fd8',
              'bass_pick': 'b16f6666486f42c6c4bde19a62462f0cda8b0f1d0ce72ad8ec51a557118d03ae',
              'bass_finger': 'bd1332696f61c0cb254ce7f202fb6b945ff46ccb1dcdd62e345a50bde3afb165',
              'bass_darkblack': 'b01cf1f928e000168d49fbda507692e5431057b5c35450fe8e20e39cae62eb63'}


def fast_length(n):
    """The next length at or above n whose only prime factors are 2, 3 and 5."""
    while True:
        m = n
        for p in (2, 3, 5):
            while m % p == 0:
                m //= p
        if m == 1:
            return n
        n += 1


# Analog prototypes, evaluated at s = j f / fc.
def hp1(f, fc):
    s = 1j * f / fc
    return s / (1 + s)


def lp1(f, fc):
    return 1 / (1 + 1j * f / fc)


def hp2(f, fc, q):
    s = 1j * f / fc
    return s * s / (s * s + s / q + 1)


def lp2(f, fc, q):
    s = 1j * f / fc
    return 1 / (s * s + s / q + 1)


def low_shelf1(f, fc, gain_db):
    """First order: `gain_db` far below fc, 0 dB far above."""
    g = 10 ** (gain_db / 20)
    s = 1j * f / fc
    return (s + g) / (s + 1)


def high_shelf1(f, fc, gain_db):
    """First order: 0 dB far below fc, `gain_db` far above."""
    g = 10 ** (gain_db / 20)
    s = 1j * f / fc
    return (g * s + 1) / (s + 1)


def peak(f, fc, gain_db, q):
    a = 10 ** (gain_db / 40)
    s = 1j * f / fc
    return (s * s + s * a / q + 1) / (s * s + s / (a * q) + 1)


def curve(x, gain, bias):
    """A memoryless stage: tanh around a fixed offset, the offset's own output taken off so that silence stays zero."""
    return np.tanh(gain * x + bias) - math.tanh(bias)


def guard(f):
    """The band's upper edge: 1 up to GUARD_HZ, a raised-cosine slope to 0 at RATE / 2 and above."""
    w = np.clip((RATE / 2 - np.abs(f)) / (RATE / 2 - GUARD_HZ), 0.0, 1.0)
    return np.sin(np.pi / 2 * w) ** 2


def _pre(f, voice):
    lo, depth = voice['drive_shelf']
    return hp1(f, voice['input_highpass_hz']) * low_shelf1(f, lo, depth)


def _tone(f, voice):
    h = np.ones(len(f), dtype=complex)
    for kind, fc, gain, *rest in voice['tone']:
        # ('unshelf', fc, gain): the reciprocal of a `drive_shelf` of the same corner and gain, to the last decimal
        h *= peak(f, fc, gain, rest[0]) if kind == 'peak' else 1 / low_shelf1(f, fc, gain) if kind == 'unshelf' else high_shelf1(f, fc, gain)
    return h


def cabinet_response(f, voice):
    cab = voice['cabinet']
    h = hp2(f, *cab['highpass'])
    for fc, gain, q in cab['peaks']:
        h = h * peak(f, fc, gain, q)
    for fc, q in cab['lowpass']:
        h = h * lp2(f, fc, q)
    return h


def _block(seg, voice, input_gain, drive, oversample):
    n = len(seg)
    m = fast_length(n + PAD)
    f = np.fft.rfftfreq(m, 1 / RATE)
    edge = guard(f)                      # nothing is left at the base rate's Nyquist frequency, up or down
    spec = np.fft.rfft(seg, n=m) * _pre(f, voice) * input_gain * edge
    big = m * oversample
    fb = np.fft.rfftfreq(big, 1 / (RATE * oversample))
    up = np.zeros(big // 2 + 1, dtype=complex)
    up[:len(spec)] = spec
    y = np.fft.irfft(up, n=big) * oversample
    stages = voice['stages']
    for k, st in enumerate(stages):
        gain = 10 ** ((st['gain_db'] + (DRIVE_SPAN_DB * (drive - .5) if k == 0 else 0)) / 20)
        y = -curve(y, gain, st['bias'])  # the sign inversion of a tube stage
        h = lp1(fb, st['lowpass_hz']) * hp1(fb, st['highpass_hz'])
        if k == len(stages) - 1:
            h = h * _tone(fb, voice)
        y = np.fft.irfft(np.fft.rfft(y) * h, n=big)
    y = np.tanh(10 ** (voice['power_db'] / 20) * y)
    down = np.fft.rfft(y)[:m // 2 + 1] * cabinet_response(f, voice) * edge
    return np.fft.irfft(down, n=m)[:n] / oversample * 10 ** (OUTPUT_DB / 20)


def process(x, voice, input_gain=1.0, drive=.5, oversample=OVERSAMPLE, block=BLOCK):
    """The chain on one channel `x` (float, RATE), as float64."""
    x = np.asarray(x)
    if x.ndim != 1:
        raise ValueError('one channel: fold a stereo signal first')
    out = np.zeros(len(x))
    ramp = .5 - .5 * np.cos(np.pi * np.arange(TAPER) / TAPER)
    for a in range(0, len(x), block):
        b = min(len(x), a + block)
        lo, hi = a - PRE, b + POST
        seg = np.zeros(hi - lo)
        s0, s1 = max(lo, 0), min(hi, len(x))
        seg[s0 - lo:s1 - lo] = x[s0:s1]
        if not seg.any():
            continue                     # silence in, silence out
        seg[:TAPER] *= ramp              # the rolls' outer edges fade, so the block's transform sees no step
        seg[-TAPER:] *= ramp[::-1]
        out[a:b] = _block(seg, voice, input_gain, drive, oversample)[PRE:PRE + (b - a)]
    return out


def bank_gain_db(track, font=None):
    """The measured gain of the part's bank into the chain, or None where the bank's level was not measured (BANKS).
    `font`: the configuration's entry for the part's SoundFont (its `sha256`), where there is a configuration; the
    bank is then known by its file.  The preset is the one the synthesis plays: the part's `patch` where it has one
    (a field the patch leaves out is 0, as the MIDI writer takes it), its `bank` and `program` otherwise."""
    if track.get('engine', 'soundfont') != 'soundfont':
        return None
    preset = preset_of(track)
    if font is not None:
        name = next((n for n, digest in BANK_FILES.items() if digest == font.get('sha256')), None)
        return BANKS.get((name, preset))
    return BANKS.get((track.get('soundfont', 'default'), preset))


def preset_of(track):
    """"bank:program" of the preset a sampled part's synthesis plays (the MIDI writer's rule)."""
    source = track.get('patch') or track
    # (a drum part without a patch, or with one on bank 128, plays the drum bank)
    drum = bool(track.get('drums')) and (track.get('patch') is None or source.get('bank', 0) == 128)
    return f'{128 if drum else source.get("bank", 0)}:{source.get("program", 0)}'


def described(track, font=None):
    """How review names a part's preset where its level into the chain was not measured: the bank's name and
    "bank:program", or the engine of a part that is not sampled.  Where a configuration gives a measured bank's name
    another file (`font`: its entry), the name and preset stand in the list of measured ones too: it says so."""
    if track.get('engine', 'soundfont') != 'soundfont':
        return track['engine']
    name, preset = track.get('soundfont', 'default'), preset_of(track)
    other = font is not None and (name, preset) in BANKS and BANK_FILES.get(name) != font.get('sha256')
    return f'{name} {preset}' + (', which the configuration gives another file than the bank measured under this name' if other else '')


def validate(track):
    """`mix.amp` of one part, or ValueError saying what to write instead."""
    from .model import number
    spec, tid = track['mix'].get('amp'), track['id']
    if spec is None:
        return
    names = ', '.join(VOICES)
    if not isinstance(spec, dict) or set(spec) - {'voice', 'drive', 'input_db'}:
        raise ValueError(f'{tid}: mix.amp is {{"voice": one of {names}, "drive": 0 to 1}}, with input_db where the part\'s bank '
                         'has no measured level')
    if not isinstance(spec.get('voice'), str) or spec['voice'] not in VOICES:
        raise ValueError(f'{tid}: mix.amp voice {spec.get("voice")!r} is not one of {names}')
    number(spec.get('drive', .5), 0, 1, f'{tid} mix.amp drive')
    number(spec.get('input_db', 0), -40, 40, f'{tid} mix.amp input_db')


def apply(x, track, font=None):
    """The part's dry synthesis `x` (frames, 2) through its amplifier: float32 (frames, 2), the one signal on both
    channels, and what the receipt records.  `font` as for bank_gain_db."""
    spec = track['mix']['amp']
    x = np.asarray(x)
    mono = np.asarray(x, dtype=np.float64).mean(axis=1)
    e_in, e_fold = float(np.sum(np.asarray(x, dtype=np.float64) ** 2)), 2 * float(np.sum(mono ** 2))
    bank = bank_gain_db(track, font)
    gain_db = (bank or 0.0) + spec.get('input_db', 0)
    gain = 10 ** (gain_db / 20)
    drive = spec.get('drive', .5)
    y = process(mono, VOICES[spec['voice']], gain, drive).astype(np.float32)
    facts = {'voice': spec['voice'], 'drive': drive, 'input_gain_db': round(gain_db, 2), 'bank_measured': bank is not None,
             'input_peak': round(float(np.max(np.abs(mono))) * gain, 3) if len(mono) else 0.0,
             'fold_loss_db': max(FOLD_FLOOR_DB, round(10 * math.log10(max(e_fold, 1e-30) / max(e_in, 1e-30)), 2)) if e_in > 0 else 0.0}
    return np.stack([y, y], axis=1), facts
