"""The bus mix, used when a project sets mix.chain to "bus": buses, four generated spaces, a master chain and a
delivery master with checks.

Buses.  Every track goes to one of six buses, by its role unless it sets mix.bus:
- drums: the kit, compressed in parallel (a hard-compressed copy 20 dB under the dry one) and saturated;
- bass: light saturation;
- rhythm: driven band parts such as rhythm guitars (2:1 compression, light saturation);
- ensemble: keys, strings, brass, pads, bells, countermelodies (gentle 1.5:1 compression);
- lead: the melody (3:1 compression with makeup);
- fx: noise effects, untouched.
Bus filters are fixed strings in this file and are never read from a project.  Saturation is FFmpeg's asoftclip as
tanh without oversampling: tanh has unity gain on small signals, while FFmpeg 9.0.2's oversampled asoftclip loses a
flat 5.8 dB and atan is 2/pi (about -3.9 dB), measured on sine tones.  bus_level_change_db.json checks each render:
bus processing should not move a group far from the sum of its stems.

Spaces.  A track's reverb send (mix.reverb_db) goes to the space that suits its bus, or to mix.space: a short room
for the band, a plate for the lead, a hall for the ensemble, and a church for an organ or a choir.  Each is a stereo
noise impulse response decaying per octave band with its own T60 (faster at high frequencies, as rooms do), building
up its density over a few to 40 ms, with discrete early reflections in the room, hall and church.  The delay send
works as in the room chain.  A part with mix.depth_m gets its early reflections from that stage position before the
mix (musiclib/stage.py) and sends more to its space, half the distance loss.

Files.  returns/ keeps each bus (bus_<bus>.wav), each space's return (<space>_return.wav), the delay return
(delay_return.wav) and the impulse responses.  The buses and the returns are the premix in parts: summed they give it
back to float32 rounding, which the render checks, so a mix can be rebuilt from them in another program.  The stems in
stems/ are each part before its bus and without the shared spaces.  A project's mix.wow_flutter and mix.mono_below_hz
act on a copy the master reads (master_input.wav), so premix.wav stays the sum.

Master.  The premix is brought to -18 LUFS for glue compression (about 2 dB on the loudest passages), an air shelf, a
little presence and a -1 dBFS limiter.  One gain toward mix.target_lufs then feeds a -1.5 dBFS sample-peak limiter;
if limiting costs loudness the gain is corrected (at most three passes).  With mix.loudness "loud" the gained mix first
passes a soft clipper computed in NumPy at four times the sample rate (FFmpeg's oversampled asoftclip would cost the
flat 5.8 dB above): linear up to three quarters of the limiter's ceiling and rounding toward the ceiling above, so the
limiter only catches what is left.  mastering.limiting_db reports, per section, how much level clipper and limiter
together took.  With mix.dynamics "wide" (orchestral and
organ music), no bus compresses or saturates and the master keeps only its EQ: one gain brings the mix to the target
unless its true peak would pass -1.2 dBTP, in which case the music stays quieter instead of being limited; with
mix.range_lu it first lifts the quieter passages until the loudness range is that many LU.  The
render checks the true peak (at most -1 dBTP) and that the MP3 decodes to the same loudness.
"""
import math

import numpy as np

from . import audio, files, stage
from .loop import starts_at_zero
from .measure import k_filter, k_level
from .model import BUSES, save_json

RATE = audio.RATE
ROLE_BUS = {'drums': 'drums', 'bass': 'bass', 'rhythm': 'rhythm', 'melody': 'lead', 'effect': 'fx'}
SEND_TO = {'drums': 'room', 'bass': 'room', 'rhythm': 'room', 'ensemble': 'hall', 'lead': 'plate', 'fx': 'hall'}
# T60 at 125 Hz / 1 kHz / 8 kHz, predelay, early reflections (s), density build-up time constant (s), width,
# return high-pass (Hz).
SPACES = {
    'room': ((.55, .45, .28), .004, (.007, .013, .019, .027, .036), .003, .7, 220),
    'plate': ((1.5, 1.7, 1.2), .022, (), .001, .9, 320),
    'hall': ((2.6, 2.2, 1.2), .030, (.017, .029, .041, .053, .067), .025, .85, 260),
    # A large stone church: about twice the hall's decay, later and sparser first reflections, a slow build-up.
    'church': ((5.5, 4.2, 2.2), .045, (.031, .048, .066, .087, .112), .040, .9, 100),
}
BUS_FILTER = {
    'bass': 'volume=2dB,asoftclip=type=tanh:threshold=1,volume=-2dB',
    'rhythm': 'acompressor=threshold=0.1:ratio=2:attack=20:release=150:makeup=1,'
              'volume=1.5dB,asoftclip=type=tanh:threshold=1,volume=-1.5dB',
    'ensemble': 'acompressor=threshold=0.12:ratio=1.5:attack=30:release=250:makeup=1',
    'lead': 'acompressor=threshold=0.08:ratio=3:attack=6:release=120:makeup=1.6',
    'fx': 'anull',
}
DRUM_BUS = ['[sum_drums]asplit=2[dr_dry][dr_par]',
            '[dr_par]acompressor=threshold=0.04:ratio=6:attack=2:release=80:makeup=4,volume=-20dB[dr_comp]',
            '[dr_dry][dr_comp]amix=inputs=2:normalize=0,volume=2dB,asoftclip=type=tanh:threshold=1,volume=-2dB[bus_drums]']
MASTER_EQ = 'highshelf=f=10000:g=2.5:t=q:w=0.7,equalizer=f=3200:t=q:w=1.2:g=0.8'
MASTER = ('acompressor=threshold={thr:.6f}:ratio=2:attack=30:release=200:knee=4:makeup=1,'
          + MASTER_EQ + ',alimiter=limit=0.891:attack=5:release=60:level=disabled')
MIX_LUFS = -18
LIMIT_DBFS = -1.5
DELAY_BAND = (500, 4000)  # a delay send's high- and low-pass (Hz), on both chains
RETURN_LOWPASS = 13000    # each space's return low-pass (Hz); its high-pass is SPACES[name][5]


def delay_times(clock, fx):
    """A part's delay as FFmpeg's adelay takes it: left|right in ms, the right 1.5 times the left, from its
    delay_quarters (0.75 by default) at the first tempo."""
    ms = clock.spb[0] * fx.get('delay_quarters', .75) * 1000
    return f'{ms:.6f}|{ms * 1.5:.6f}'


def bus_of(track):
    if track['mix'].get('bus'):
        return track['mix']['bus']
    if track.get('drums'):
        return 'drums'
    if track['engine'] == 'noise':
        return 'fx'
    return ROLE_BUS.get(track.get('role'), 'ensemble')


def space_of(track):
    return track['mix'].get('space') or SEND_TO[bus_of(track)]


def space_ir(name, seed=20261101):
    """Stereo noise impulse response, decaying per octave band with its own T60."""
    (t_lo, t_mid, t_hi), pre, ers, tau, width, _ = SPACES[name]
    n = int((pre + 1.15 * max(t_lo, t_mid, t_hi)) * RATE)
    rng = np.random.default_rng(seed + sum(map(ord, name)))
    noise = width * rng.standard_normal((n, 2)) + (1 - width) * rng.standard_normal(n)[:, None]
    t = np.arange(n) / RATE
    spec = np.fft.rfft(noise, axis=0)
    lf = np.log2(np.maximum(np.fft.rfftfreq(n, 1 / RATE), 1))
    out = np.zeros_like(noise)
    centres = [62.5 * 2 ** k for k in range(9)]
    for k, c in enumerate(centres):
        x = lf - math.log2(c)
        mask = np.where(np.abs(x) < 1, .5 + .5 * np.cos(np.pi * x), 0.0)
        if k == 0:
            mask = np.where(x < 0, 1.0, mask)
        if k == len(centres) - 1:
            mask = np.where(x > 0, 1.0, mask)
        band = np.fft.irfft(spec * mask[:, None], n=n, axis=0)
        t60 = float(np.interp(math.log2(c), [math.log2(125), math.log2(1000), math.log2(8000)], [t_lo, t_mid, t_hi]))
        out += band * (np.exp(-6.91 * np.maximum(t - pre, 0) / t60) * (t >= pre))[:, None]
    out *= (1 - np.exp(-np.maximum(t - pre, 0) / tau))[:, None]
    tail = math.sqrt(np.sum(out ** 2) / 2)
    for k, d in enumerate(ers):
        # Discrete early reflections carry about 15% of the tail's energy, panned and slightly delayed per ear.
        side, amp = rng.uniform(-.7, .7), .25 * .8 ** k * tail
        i = int(d * RATE)
        out[i, 0] += amp * math.sqrt(1 - side)
        out[i + int(.0007 * RATE * (1 + side)), 1] += amp * math.sqrt(1 + side)
    out *= math.sqrt(.35 / (np.sum(out ** 2) / 2))  # about the energy of the room chain's impulse response
    return out.astype(np.float32)


def mix(p, clock, cfg, output, frames, tracks=None, premix=None):
    """Mix the render's processed stems through the buses and spaces into premix.wav.  Each bus, reverb and delay
    return and impulse response is kept in returns/; `verify` then checks that the buses and returns add up to the
    premix and compares every bus with its stems' sum.

    With `tracks` (a layer of a game loop) only those parts go through the same buses and spaces into `premix`; the
    impulse responses of the full mix are reused and nothing else is written."""
    full = tracks is None
    tracks = p['tracks'] if full else tracks
    premix = output / 'premix.wav' if premix is None else premix
    returns = output / 'returns'
    stems = [output / 'stems' / f'{t["id"]}.wav' for t in tracks]
    irs = {name: returns / f'{name}_ir.wav' for name in SPACES}
    for name, path in irs.items():
        if full or not path.is_file():
            audio.write_wav(path, space_ir(name))
    args = []
    for path in stems + list(irs.values()):
        args += ['-i', path]
    ir_input = {name: len(tracks) + j for j, name in enumerate(SPACES)}

    graph, dry, sends, delays = [], {b: [] for b in BUSES}, {s: [] for s in SPACES}, []
    for k, t in enumerate(tracks):
        fx = t['mix']
        outs = [f'[d{k}]'] + ([f'[r{k}]'] if fx.get('reverb_db') is not None else []) + (
            [f'[e{k}]'] if fx.get('delay_db') is not None else [])
        graph.append(f'[{k}:a]asplit={len(outs)}' + ''.join(outs))
        dry[bus_of(t)].append(f'[d{k}]')
        if fx.get('reverb_db') is not None:
            # A part placed deeper on the stage sends more to its space (musiclib/stage.py).
            send = fx['reverb_db'] + (stage.send_boost_db(fx.get('pan', 0), fx['depth_m']) if fx.get('depth_m') is not None else 0)
            graph.append(f'[r{k}]volume={send:.6f}dB[rs{k}]')
            sends[space_of(t)].append(f'[rs{k}]')
        if fx.get('delay_db') is not None:
            graph.append(f'[e{k}]highpass=f={DELAY_BAND[0]},lowpass=f={DELAY_BAND[1]},adelay={delay_times(clock, fx)},volume={fx["delay_db"]}dB[es{k}]')
            delays.append(f'[es{k}]')
    sums = []
    wide = p['mix'].get('dynamics') == 'wide'
    for b, members in dry.items():
        if not members:
            continue
        graph.append(''.join(members) + (f'amix=inputs={len(members)}:normalize=0' if len(members) > 1 else 'anull') + f'[sum_{b}]')
        if wide:
            graph.append(f'[sum_{b}]anull[bus_{b}]')  # no bus compression or saturation: the written dynamics stay
        else:
            graph += DRUM_BUS if b == 'drums' else [f'[sum_{b}]{BUS_FILTER[b]}[bus_{b}]']
        graph.append(f'[bus_{b}]asplit=2[busmix_{b}][busexp_{b}]' if full else f'[bus_{b}]anull[busmix_{b}]')
        sums.append(f'[busmix_{b}]')
    returned = []  # each return the full mix writes to returns/: (graph label, file)
    for name, items in sends.items():
        if not items:
            graph.append(f'[{ir_input[name]}:a]anullsink')
            continue
        graph.append(''.join(items) + (f'amix=inputs={len(items)}:normalize=0' if len(items) > 1 else 'anull') + f'[send_{name}]')
        graph.append(f'[send_{name}][{ir_input[name]}:a]afir={audio.afir_options(cfg)},'
                     f'highpass=f={SPACES[name][5]},lowpass=f={RETURN_LOWPASS},apad,atrim=end_sample={frames}'
                     + (f',asplit=2[ret_{name}][retexp_{name}]' if full else f'[ret_{name}]'))
        sums.append(f'[ret_{name}]')
        returned.append((f'retexp_{name}', returns / f'{name}_return.wav'))
    if delays:
        graph.append(''.join(delays) + (f'amix=inputs={len(delays)}:normalize=0' if len(delays) > 1 else 'anull')
                     + f',apad,atrim=end_sample={frames}' + (',asplit=2[ret_delay][retexp_delay]' if full else '[ret_delay]'))
        sums.append('[ret_delay]')
        returned.append(('retexp_delay', returns / 'delay_return.wav'))
    # A loop from bar 1 replays the first frames on every repeat, where a fade-in would dent each downbeat.
    fade = '' if starts_at_zero(p) else ',afade=t=in:st=0:d=0.005'
    graph.append(''.join(sums) + f'amix=inputs={len(sums)}:normalize=0:duration=longest,'
                 f'atrim=end_sample={frames}{fade}[mix]')
    text = ';\n'.join(graph)
    graph_options = audio.graph_file(cfg, output / 'mix.filtergraph.txt' if full else premix.with_suffix('.filtergraph.txt'), text)
    exports = []
    for b in BUSES:
        if dry[b] and full:
            exports += ['-map', f'[busexp_{b}]', '-ar', str(RATE), '-c:a', 'pcm_f32le', returns / f'bus_{b}.wav']
    for label, path in returned if full else ():
        exports += ['-map', f'[{label}]', '-ar', str(RATE), '-c:a', 'pcm_f32le', path]
    audio.ffmpeg(cfg, [*args, *graph_options, '-map', '[mix]', '-ar', str(RATE), '-c:a', 'pcm_f32le',
                       premix, *exports], output / 'logs', 'mix' if full else 'mix_' + premix.stem)
    if not full:
        return None
    return {'assignment': {t['id']: bus_of(t) for t in tracks}, 'spaces': {t['id']: space_of(t) for t in tracks
                                                                         if t['mix'].get('reverb_db') is not None},
            'returns': [path.name for _, path in returned]}


def verify(p, output, buses):
    """What a full mix (`buses`, from `mix`) is checked against, written to bus_level_change_db.json and returned:
    each bus's K-weighted level against the sum of its stems, and the buses and returns added up against the premix.
    It reads only the files the mix wrote, so a render runs it while the master is made."""
    returns = output / 'returns'
    change, total, mag = {}, 0.0, 0.0
    for b in BUSES:
        members = [output / 'stems' / f'{t["id"]}.wav' for t in p['tracks'] if bus_of(t) == b]
        if members:
            summed = sum(audio.read_wav(s)[0].astype(np.float64) for s in members)
            bus = np.asarray(audio.read_wav(returns / f'bus_{b}.wav')[0], dtype=np.float64)
            change[b] = round(k_level(bus) - k_level(summed), 2)
            total, mag = total + bus, mag + np.abs(bus)
    for name in buses['returns']:
        x = np.asarray(audio.read_wav(returns / name)[0], dtype=np.float64)
        total, mag = total + x, mag + np.abs(x)
    save_json(output / 'bus_level_change_db.json', change)
    # Summed, the buses and returns give the premix back up to float rounding (the premix fades in over its first 5 ms).
    mixed = np.asarray(audio.read_wav(output / 'premix.wav')[0], dtype=np.float64)
    ok, worst, share = adds_up(total, mag, mixed, int(.01 * RATE))
    return {'level_change_db': change, 'sum_minus_premix_peak_dbfs': round(20 * math.log10(max(worst, 1e-12)), 1),
            'sum_error_share_of_allowance': round(share, 4), 'adds_up_to_premix': ok}


def adds_up(total, mag, mixed, skip=0):
    """Whether the sum of a mix's parts (`total`, with `mag` the sum of their magnitudes) gives `mixed` back to float32
    rounding: per sample within 1e-6 plus 16 float32 steps of the parts' magnitudes, since a premix before mastering
    can run far above full scale.  Returns (ok, the worst absolute difference, the worst share of that allowance)."""
    d = np.abs(total[skip:] - mixed[skip:])
    if not d.size:
        return True, 0.0, 0.0
    share = float(np.max(d / (1e-6 + 16 * 2.0 ** -23 * mag[skip:])))
    return share <= 1, float(d.max()), share


def soft_clip(x, ceiling, knee=.75, factor=4, block=1 << 16, margin=2048):
    """Peaks rounded toward `ceiling` (linear amplitude): unchanged below `knee` times it, a tanh curve above that
    meets the line with the same slope and approaches the ceiling.  Computed at `factor` times the rate, in blocks
    whose margins are discarded, and brought back through an FFT low-pass, so the harmonics the curve adds above the
    band do not fold back."""
    n, t = len(x), knee * ceiling
    out = np.empty((n, x.shape[1]), dtype=np.float32)
    for s in range(0, n, block):
        a, b = max(0, s - margin), min(n, s + block + margin)
        seg = np.asarray(x[a:b], dtype=np.float64)
        m = len(seg)
        up = np.fft.irfft(np.fft.rfft(seg, axis=0), n=m * factor, axis=0) * factor
        mag = np.abs(up)
        over = mag > t
        up[over] = np.sign(up[over]) * (t + (ceiling - t) * np.tanh((mag[over] - t) / (ceiling - t)))
        down = np.fft.irfft(np.fft.rfft(up, axis=0)[:m // 2 + 1], n=m, axis=0) / factor
        keep = min(block, n - s)
        out[s:s + keep] = down[s - a:s - a + keep]
    return out


def master(p, cfg, output):
    """premix.wav (or master_input.wav) -> master chain -> mixed.wav -> delivery gain and limiter -> master.wav (24-bit).
    Returns the premix measurement, the mastering record and the measurement of master.wav as delivered (the last
    delivery pass measured the file the render keeps, so it is not measured again)."""
    logs = output / 'logs'
    source_in = output / 'premix.wav'
    if p['mix'].get('wow_flutter') or p['mix'].get('mono_below_hz'):
        # Tape wobble over the whole mix, then low frequencies mono (musiclib/production.py), before the master
        # measures and compresses it: written to master_input.wav, so premix.wav stays the buses and returns summed.
        from . import production
        x, _ = audio.read_wav(source_in)
        x = x.astype('float64')  # releases the mapped file
        if p['mix'].get('wow_flutter'):
            x, _ = production.wow_flutter(x, p['mix']['wow_flutter'], 'premix')
        if p['mix'].get('mono_below_hz'):
            x = production.mono_below(x, p['mix']['mono_below_hz'])
        source_in = output / 'master_input.wav'
        audio.write_wav(source_in, x.astype('float32'))
    before = audio.measure(cfg, source_in, logs, 'measure_premix')
    gain = MIX_LUFS - before['integrated_lufs']
    wide = p['mix'].get('dynamics') == 'wide'
    chain = f'volume={gain:.6f}dB,' + (MASTER_EQ if wide else MASTER.format(thr=10 ** (-16 / 20)))
    mixed = output / 'mixed.wav'
    audio.ffmpeg(cfg, ['-i', source_in, '-af', chain, '-ar', str(RATE), '-c:a', 'pcm_f32le', mixed], logs, 'master_chain')
    source = audio.measure(cfg, mixed, logs, 'measure_mixed')
    target = p['mix'].get('target_lufs', -16)
    if wide:
        ranged = None
        if p['mix'].get('range_lu') is not None:
            ranged = range_control(mixed, output / 'ranged.wav', p['mix']['range_lu'])
            mixed = output / 'ranged.wav'
            source = audio.measure(cfg, mixed, logs, 'measure_ranged')
        delivered, measured = wide_delivery(cfg, output, mixed, source, target, gain, chain)
        if ranged:
            delivered['range'] = ranged
        return before, delivered, measured
    delivery, passes, ceiling = target - source['integrated_lufs'], [], LIMIT_DBFS
    loud = p['mix'].get('loudness') == 'loud'
    clipped = output / 'clipped.wav'
    for k in range(4):
        # A loud master (dense electronic genres) rounds the peaks with an oversampled soft clipper before the limiter,
        # so the limiter works less and pumps less at -8 to -10 LUFS.
        if loud:
            x, _ = audio.read_wav(mixed)
            audio.write_wav(clipped, soft_clip(np.asarray(x, dtype=np.float64) * 10 ** (delivery / 20), 10 ** (ceiling / 20)))
            del x
            source_file, limiter = clipped, f'alimiter=limit={10 ** (ceiling / 20):.6f}:attack=5:release=60:level=disabled'
        else:
            source_file = mixed
            limiter = f'volume={delivery:.6f}dB,alimiter=limit={10 ** (ceiling / 20):.6f}:attack=5:release=60:level=disabled'
        audio.ffmpeg(cfg, ['-i', source_file, '-af', limiter, '-ar', str(RATE), '-c:a', 'pcm_s24le', output / 'master.wav'], logs, f'deliver_{k}')
        m = audio.measure(cfg, output / 'master.wav', logs, f'measure_delivery_{k}')
        passes.append({'gain_db': round(delivery, 3), 'limit_dbfs': round(ceiling, 3), 'lufs': m['integrated_lufs'],
                       'true_peak_dbtp': m['true_peak_dbtp']})
        close, peak = abs(m['integrated_lufs'] - target) <= .3, m['true_peak_dbtp'] <= -1
        if close and peak:
            break
        if not peak:
            # The limiter holds sample peaks; bright transients (cymbals, mallets) can still overshoot between samples.
            # Lower its ceiling by the overshoot and a margin, and let the gain restore the loudness.
            ceiling -= m['true_peak_dbtp'] + 1 + .2
        delivery += target - m['integrated_lufs']
    applied = passes[-1]['gain_db']
    if loud:
        clipped.unlink()
        limiter = f'volume={applied:.6f}dB, soft clip to {10 ** (ceiling / 20):.4f} above {.75 * 10 ** (ceiling / 20):.4f} at 4x (NumPy), ' + limiter
    return before, {'chain': 'bus', 'mix_gain_db': round(gain, 6), 'master_chain': chain,
                    'mixed': {k: source[k] for k in ('integrated_lufs', 'true_peak_dbtp', 'lra_lu')},
                    'target_lufs': target, 'limiter_dbfs': round(ceiling, 3), 'delivery_chain': limiter, 'passes': passes,
                    'limiting_db': section_limiting(p, mixed, output / 'master.wav', applied)}, m


def section_limiting(p, mixed, master, gain_db):
    """How much level the delivery clipper and limiter took from each section: its RMS after the delivery gain minus
    its RMS in the master, in dB.  A dense section loses more than a sparse one, which turns a drop or a chorus quieter
    than the intro around it once the loss passes a few dB."""
    from .model import Clock
    clock = Clock(p)
    x, _ = audio.read_wav(mixed)
    y, _ = audio.read_wav(master)
    out = {}
    for s in p['sections']:
        a, b = (int(round(clock.seconds(bar * clock.beats_per_bar) * RATE)) for bar in (s['start_bar'], s['start_bar'] + s['bars']))
        rx = float(np.sqrt(np.mean(np.asarray(x[a:b], dtype=np.float64) ** 2)))
        ry = float(np.sqrt(np.mean(np.asarray(y[a:b], dtype=np.float64) ** 2)))
        if rx > 1e-6 and ry > 1e-6:
            out[s['id']] = round(20 * np.log10(rx) + gain_db - 20 * np.log10(ry), 2)
    return out


def wide_delivery(cfg, output, mixed, source, target, gain, chain):
    """One gain to the target loudness, held down when the true peak would pass -1.2 dBTP, so the music comes out
    quieter rather than limited; a -1 dBFS limiter stays only as a guard and is reported if it acted."""
    logs = output / 'logs'
    wanted = target - source['integrated_lufs']
    delivery = min(wanted, -1.2 - source['true_peak_dbtp'])
    guard = f'volume={delivery:.6f}dB,alimiter=limit={10 ** (-1 / 20):.6f}:attack=5:release=60:level=disabled'
    audio.ffmpeg(cfg, ['-i', mixed, '-af', guard, '-ar', str(RATE), '-c:a', 'pcm_s24le', output / 'master.wav'], logs, 'deliver_wide')
    m = audio.measure(cfg, output / 'master.wav', logs, 'measure_delivery_wide')
    passes = [{'gain_db': round(delivery, 3), 'limit_dbfs': -1.0, 'lufs': m['integrated_lufs'], 'true_peak_dbtp': m['true_peak_dbtp']}]
    return {'chain': 'bus', 'dynamics': 'wide', 'mix_gain_db': round(gain, 6), 'master_chain': chain,
            'mixed': {k: source[k] for k in ('integrated_lufs', 'true_peak_dbtp', 'lra_lu')}, 'target_lufs': target,
            'peak_held_db': round(max(0.0, wanted - delivery), 2), 'lra_lu': m['lra_lu'],
            'limiter_dbfs': -1.0, 'delivery_chain': guard, 'passes': passes}, m


def short_term(x):
    """EBU short-term loudness (3 s windows, BS.1770 K-weighting) every 100 ms: window centres in samples, LUFS."""
    power = (k_filter(x) ** 2).sum(axis=1)
    c = np.concatenate([[0.0], np.cumsum(power)])
    win, hop = 3 * RATE, RATE // 10
    starts = np.arange(0, max(1, len(power) - win + 1), hop)
    level = -0.691 + 10 * np.log10(np.maximum((c[np.minimum(starts + win, len(power))] - c[starts]) / win, 1e-20))
    return starts + win // 2, level


def loudness_range(level):
    """EBU Tech 3342: the spread between the 10th and 95th percentiles of the short-term loudness, gated at -70 LUFS
    and at 20 LU under the mean of what passes; also returns those two percentiles."""
    a = level[level > -70]
    if not len(a):
        return 0.0, (-70.0, -70.0)
    g = a[a > 10 * np.log10(np.mean(10 ** (a / 10))) - 20]
    lo, hi = float(np.percentile(g, 10)), float(np.percentile(g, 95))
    return hi - lo, (lo, hi)


def range_control(src, dst, target):
    """Bring a wide master's loudness range (Tech 3342) down to `target` LU by lifting its quieter passages.

    A short-term loudness at or above the 95th percentile keeps its level; below it the passage rises by a share of its
    distance from there, the same share everywhere (a passage under the 10th percentile rises as much as one at it), so
    the order of soft and loud and every accent inside a passage stay.  The lift follows the 3 s loudness smoothed over
    1.5 s, so it moves with phrases, not notes.  EBU R 128 sets no ceiling on loudness range and leaves it to the
    programme and where it will be heard; this is for music that must also carry on small speakers."""
    x, _ = audio.read_wav(src)
    centres, level = short_term(x)
    before, (lo, hi) = loudness_range(level)
    info = {'target_lu': target, 'lra_before_lu': round(before, 2)}
    share, out, after, lift = 1 - target / before if before > target else 0.0, x, before, np.zeros(len(level))
    for _ in range(5):
        if share <= 0:
            break
        lift = np.convolve(np.pad(share * (hi - np.clip(level, lo, hi)), 7, mode='edge'), np.ones(15) / 15, mode='valid')
        out = (x * (10 ** (np.interp(np.arange(len(x)), centres, lift) / 20))[:, None]).astype(np.float32)
        after, _ = loudness_range(short_term(out)[1])
        if after <= target + .3:
            break
        share = min(.95, share + (after - target) / before)
    audio.write_wav(dst, out)
    info.update(lra_after_lu=round(after, 2), share=round(share, 3), max_lift_db=round(float(lift.max()), 2))
    return info


def linear_master(mastering):
    """The master's gains and EQ without its compressor and limiters: what a layer of a game loop gets, so the layers
    played together add up to the mix before the master's dynamics."""
    return (f'volume={mastering["mix_gain_db"]:.6f}dB,{MASTER_EQ},'
            f'volume={mastering["passes"][-1]["gain_db"]:.6f}dB')


def mp3_check(cfg, output, master_lufs):
    """Decode preview.mp3 again and compare its loudness with the master's (the MP3 must not change it)."""
    decoded = output / 'logs' / 'preview_decoded.wav'
    before = files.stamp(decoded)
    try:
        audio.run([cfg['ffmpeg']['path'], '-hide_banner', '-nostdin', '-y', '-i', output / 'preview.mp3', '-ar', str(RATE),
                   '-c:a', 'pcm_f32le', decoded], output / 'logs', 'decode_mp3')
    finally:
        # FFmpeg writes it there itself: a file of the run, should a failure leave it, once FFmpeg has changed what was
        # at that name (a file there that it never wrote is not the run's; GPT Pro's sixth review, from the code).
        if files.stamp(decoded) != before:
            files.wrote(decoded)
    d = audio.measure(cfg, decoded, output / 'logs', 'measure_mp3')
    decoded.unlink()
    return {'mp3_lufs': d['integrated_lufs'], 'mp3_true_peak_dbtp': d['true_peak_dbtp'],
            'matches': abs(d['integrated_lufs'] - master_lufs) <= .2}
