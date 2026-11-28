"""Drum-machine voices for parts with `engine: "drum_synth"`, on General MIDI drum keys.

The classic analog machines build each drum from a few circuits (Roland TR-808 service notes; Werner, Abel and Smith
2014 on the 808's cymbal and bass drum): a bass drum is a sine whose pitch falls quickly from a click to its body; a
snare a pair of damped tones under a burst of filtered noise; a clap several noise bursts a few milliseconds apart
before a tail; hi-hats six square waves at inharmonic frequencies through a high-pass, cut short when closed (a closed
or pedal hat chokes an open one); toms falling sines; a cowbell two squares through a band-pass.  `kit.style` "808"
gives long, round drums; "909" shorter, punchier ones with more noise.  `kit.tune` (semitones) and `kit.decay` (a
factor) adjust the whole kit.  Every hit is computed directly, and the noise comes from the note's id, so a render
repeats exactly.

Gated reverb, the snare sound of much 1980s pop, puts a loud, dense room behind the snare and cuts it off with a noise
gate while it is still loud.  `kit.gated_ms` (100-600) gives snares and claps that tail: decorrelated noise in each
channel, shaped like a snare's spectrum, held for that long and closed in 15 ms; `kit.gated_db` (-18 to 0, default -6)
sets its level against the hit.
"""
import math

import numpy as np

from .synth import RATE, biquad, seed

METAL = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)  # the 808's six cymbal oscillators (Hz)
STYLES = {
    '808': {'kick': (150, 48, .045, .55), 'snare_tone': (180, 330, .09), 'snare_noise': (.5, .16), 'hat': (.045, .3, 1.0),
            'tom': .3, 'clap_tail': .15, 'click': .2},
    '909': {'kick': (230, 55, .03, .28), 'snare_tone': (200, 360, .07), 'snare_noise': (.85, .18), 'hat': (.03, .22, 1.4),
            'tom': .22, 'clap_tail': .12, 'click': .6},
}
TOMS = {41: 82, 43: 98, 45: 116, 47: 138, 48: 164, 50: 196}
KEYS = {35: 'kick', 36: 'kick', 37: 'rim', 38: 'snare', 40: 'snare', 39: 'clap', 42: 'hat_closed', 44: 'hat_pedal',
        46: 'hat_open', 49: 'crash', 51: 'ride', 56: 'cowbell', 70: 'shaker', **{k: 'tom' for k in TOMS}}


def _noise(n, note_id):
    return np.random.default_rng(seed(note_id)).standard_normal(n)


def _filter(x, kind, hz, q=.707):
    return biquad(x, kind, np.full(len(x), float(hz)), np.full(len(x), float(q)), RATE)


def _metal(t, scale):
    return sum(np.sign(np.sin(2 * np.pi * f * scale * t)) for f in METAL) / len(METAL)


def hit(kind, key, velocity, note_id, style, tune=0.0, decay=1.0):
    """One drum hit (mono) of `kind` at velocity 0-1."""
    st = STYLES[style]
    ratio = 2 ** (tune / 12)
    length = {'kick': 1.2, 'snare': .5, 'clap': .5, 'hat_closed': .2, 'hat_pedal': .2, 'hat_open': 1.2, 'crash': 3.0,
              'ride': 2.5, 'tom': 1.0, 'rim': .1, 'cowbell': .5, 'shaker': .25}[kind] * max(1.0, decay)
    n = int(length * RATE)
    t = np.arange(n) / RATE
    if kind == 'kick':
        f0, f1, tau_p, tau_a = st['kick']
        f = (f1 + (f0 - f1) * np.exp(-t / tau_p)) * ratio
        body = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t / (tau_a * decay))
        click = _filter(_noise(n, note_id), 'highpass', 2500) * np.exp(-t / .002) * st['click']
        y = np.tanh(1.6 * (body + click)) / math.tanh(1.6)
    elif kind == 'snare':
        a, b, tau = st['snare_tone']
        tone = (np.sin(2 * np.pi * a * ratio * t) + .6 * np.sin(2 * np.pi * b * ratio * t)) * np.exp(-t / (tau * decay))
        level, tau_n = st['snare_noise']
        noise = _filter(_filter(_noise(n, note_id), 'highpass', 1200), 'lowpass', 9000) * np.exp(-t / (tau_n * decay))
        y = .55 * tone + level * noise
    elif kind == 'clap':
        x = _filter(_noise(n, note_id), 'bandpass', 1200, 1.2)
        env = sum(np.where(t >= d, np.exp(-(t - d) / .005), 0) for d in (0, .011, .022)) + np.where(t >= .033, np.exp(-(t - .033) / (st['clap_tail'] * decay)), 0)
        y = x * env * 1.4
    elif kind in ('hat_closed', 'hat_pedal', 'hat_open'):
        closed, opened, scale = st['hat']
        tau = {'hat_closed': closed, 'hat_pedal': closed * 1.4, 'hat_open': opened}[kind] * decay
        x = _filter(_filter(_metal(t, scale * ratio), 'bandpass', 8500, 1.0), 'highpass', 6500)
        y = x * np.exp(-t / tau) * 1.6
    elif kind in ('crash', 'ride'):
        x = _filter(_metal(t, 1.6 * ratio) + .5 * _noise(n, note_id), 'highpass', 4000 if kind == 'crash' else 6000)
        y = x * np.exp(-t / ((1.0 if kind == 'crash' else .7) * decay)) * (.9 if kind == 'crash' else .5)
        if kind == 'ride':
            y = y + .25 * np.sin(2 * np.pi * 3100 * ratio * t) * np.exp(-t / (.5 * decay))
    elif kind == 'tom':
        f = TOMS[key] * ratio * (1 + .25 * np.exp(-t / .05))
        y = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t / (st['tom'] * decay))
    elif kind == 'rim':
        y = (np.sin(2 * np.pi * 1700 * ratio * t) * np.exp(-t / .012) + .4 * _filter(_noise(n, note_id), 'highpass', 3000) * np.exp(-t / .004))
    elif kind == 'cowbell':
        x = (np.sign(np.sin(2 * np.pi * 540 * ratio * t)) + np.sign(np.sin(2 * np.pi * 800 * ratio * t))) / 2
        x = _filter(x, 'bandpass', 900, 2.0)
        y = x * (.6 * np.exp(-t / .03) + .4 * np.exp(-t / (.2 * decay))) * 1.5
    else:  # shaker
        y = _filter(_noise(n, note_id), 'highpass', 5000) * np.exp(-((t - .02) / .03) ** 2) * .8
    fade = min(n, int(.005 * RATE))
    y[-fade:] *= np.linspace(1, 0, fade)
    return y * velocity ** 1.2


def gated_tail(velocity, note_id, ms, db):
    """A gated room behind a snare or clap: stereo, held `ms` milliseconds, then cut."""
    n = int((ms + 20) / 1000 * RATE)
    t = np.arange(n) / RATE
    hold = ms / 1000
    env = np.minimum(t / .004, 1) * np.exp(-t / (2.5 * hold)) * np.clip((hold + .015 - t) / .015, 0, 1)
    out = np.empty((n, 2))
    for c in range(2):
        x = _noise(n, f'{note_id}:gate{c}')
        out[:, c] = _filter(_filter(x, 'highpass', 250), 'lowpass', 7000) * env
    return out * .5 * 10 ** (db / 20) * velocity ** 1.2


def validate(track):
    from .played import number
    kit = track.get('kit', {})
    if (not isinstance(kit, dict) or set(kit) - {'style', 'tune', 'decay', 'gated_ms', 'gated_db'}
            or kit.get('style', '808') not in STYLES):
        raise ValueError(f'{track["id"]}: kit takes style ("808" or "909"), tune, decay, gated_ms and gated_db')
    number(kit.get('tune', 0), -12, 12, 'kit tune semitones')
    number(kit.get('decay', 1), .25, 4, 'kit decay factor')
    number(kit.get('gated_ms', 300), 100, 600, 'kit gated ms');number(kit.get('gated_db', -6), -18, 0, 'kit gated dB')
    bad = sorted({n['pitch'] for n in track['notes']} - set(KEYS))
    if bad:
        raise ValueError(f'{track["id"]}: drum_synth plays keys ' + ', '.join(map(str, sorted(KEYS))) + f'; not {bad}')


def render(project, track, path, clock=None):
    from .played import Clock, performed
    from . import audio
    clock = clock or Clock(project)
    kit = track.get('kit', {})
    style, tune, decay = kit.get('style', '808'), kit.get('tune', 0.0), kit.get('decay', 1.0)
    total = round((clock.end + clock.tail) * RATE)
    out, opened = np.zeros(total), np.zeros(total)
    gated = np.zeros((total, 2)) if kit.get('gated_ms') else None
    open_hats = []  # (start, end) of open-hat hits, which the next closed or pedal hat cuts
    hits = sorted(performed(track, clock), key=lambda e: e['start_seconds'])
    for e in hits:
        kind = KEYS[e['pitch']]
        y = hit(kind, e['pitch'], e['velocity'] / 127, e['id'], style, tune, decay)
        i0 = int(round(e['start_seconds'] * RATE))
        if kind in ('hat_closed', 'hat_pedal'):
            for k, (a, b) in enumerate(open_hats):
                if a < i0 < b:
                    fade = min(b - i0, int(.004 * RATE))
                    opened[i0:i0 + fade] *= np.linspace(1, 0, fade)
                    opened[i0 + fade:b] = 0
                    open_hats[k] = (a, i0)
        m = min(len(y), total - i0)
        if m > 0:
            (opened if kind == 'hat_open' else out)[i0:i0 + m] += y[:m]
            if kind == 'hat_open':
                open_hats.append((i0, i0 + m))
        if gated is not None and kind in ('snare', 'clap'):
            tail = gated_tail(e['velocity'] / 127, e['id'], kit['gated_ms'], kit.get('gated_db', -6))
            m = min(len(tail), total - i0)
            if m > 0:
                gated[i0:i0 + m] += tail[:m]
    out += opened
    stereo = np.repeat(out[:, None], 2, axis=1) + (gated if gated is not None else 0)
    audio.write_wav(path, (stereo * .5).astype(np.float32))
    return {'hits': len(hits), 'style': style, **({'gated_ms': kit['gated_ms']} if gated is not None else {})}
