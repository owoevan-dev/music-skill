"""Loop delivery for game music.

A project with `loop` gets, next to the master, `loop.wav` and `loop.ogg`: frames from the start of the file to the end
of the last bar, with everything the render produced after that (note releases and reverb tails) added back from the
loop start, so the loop point carries the decay a listener would hear if the music really went round again.  The WAV
holds the loop in a `smpl` chunk (Microsoft RIFF; Godot's importer reads it in "Detect From WAV" mode), the Ogg Vorbis
copy in LOOPSTART/LOOPLENGTH comments in samples (the RPG Maker convention).

`seam` describes the loop point after Medina-Gray (2019), who judges a seam between game-music modules by meter,
timbre, pitch, volume and abruptness, comparing the 1 s after it with the 5 s before it, and keeps the aspects apart
instead of adding them into one score.  The score-side aspects come from the project; volume and the folded tail
come from the audio.

The WAV files also carry one cue point per section start, labelled with the section id (a `cue ` chunk and a LIST
`adtl` chunk of `labl` entries), so a middleware segment or an engine script can jump between sections on a bar line.
loop.json repeats them in samples, with the tempo, beats per bar and beat count where the tempo is constant.

With `loop.layers`, every layer also goes through the same buses and spaces alone, with the master's gains and EQ but
not its compressor and limiters, is delayed by the look-ahead of those limiters (measured on each render, about 10 ms)
so it lines up with loop.wav, and is folded the same way (layers/<id>.wav and .ogg).  One gain, shared by all
layers, keeps them under -1 dBTP, so their balance stays the composer's.  Played together they add up to the mix before
the master's dynamics: the game's music bus needs its own limiter.
"""
import math
import re
import struct
import subprocess
from pathlib import Path

import numpy as np

from . import audio, files, measure
from .model import TPQ, performed, save_json

BEFORE, AFTER = 5.0, 1.0
NAMES = ('C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B')


def bounds(p, clock):
    """Loop start and end in seconds and in frames: from `loop.start_bar` to the end of the last bar."""
    start = clock.seconds(p['loop'].get('start_bar', 0) * clock.beats_per_bar)
    return start, clock.end, round(start * audio.RATE), round(clock.end * audio.RATE)


def starts_at_zero(p):
    """A loop from bar 1 replays the file's first frames on every repeat, so they must not be faded in."""
    return 'loop' in p and p['loop'].get('start_bar', 0) == 0


def fold(master, start, end):
    """Frames [0, end) of the master with the frames after `end` added back from `start`, wrapping round the loop when
    the tail is longer than the loop: on every repeat the loop then holds the decay of all earlier passes."""
    out = np.array(master[:end], dtype=np.float64)
    tail = np.asarray(master[end:], dtype=np.float64)
    length, pos = end - start, 0
    while pos < len(tail):
        n = min(length, len(tail) - pos)
        out[start:start + n] += tail[pos:pos + n]
        pos += n
    return out


def chunk(cid, payload):
    return cid + struct.pack('<I', len(payload)) + payload + (b'\0' if len(payload) % 2 else b'')


def write_wav(path, data, loop_start, loop_end, cues=()):
    """24-bit PCM WAV with one forward loop [loop_start, loop_end) in a `smpl` chunk.  The chunk names the last frame
    that is played, loop_end - 1; a play count of 0 loops for ever.  `cues` are (frame, label) pairs, written as cue
    points with `labl` entries."""
    # The scale audio.read_wav divides by, so the master's own frames come back unchanged.
    x = np.clip(np.round(np.asarray(data, dtype=np.float64) * 8388608), -8388608, 8388607).astype('<i4')
    channels = x.shape[1]
    raw = x.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    fmt = struct.pack('<HHIIHH', 1, channels, audio.RATE, audio.RATE * channels * 3, channels * 3, 24)
    smpl = struct.pack('<9I', 0, 0, round(1e9 / audio.RATE), 60, 0, 0, 0, 1, 0) + struct.pack('<6I', 0, 0, loop_start, loop_end - 1, 0, 0)
    body = b'WAVE' + chunk(b'fmt ', fmt) + chunk(b'data', raw) + chunk(b'smpl', smpl)
    if cues:
        points = b''.join(struct.pack('<II4sIII', k + 1, frame, b'data', 0, 0, frame) for k, (frame, _) in enumerate(cues))
        labels = b''.join(chunk(b'labl', struct.pack('<I', k + 1) + label.encode('utf-8') + b'\0')
                          for k, (_, label) in enumerate(cues))
        body += chunk(b'cue ', struct.pack('<I', len(cues)) + points) + chunk(b'LIST', b'adtl' + labels)
    with files.staged(path) as f:  # whole or not at all (musiclib.files)
        f.write(b'RIFF' + struct.pack('<I', len(body)) + body)


def chunks(path):
    data = Path(path).read_bytes()
    pos = 12
    while pos + 8 <= len(data):
        cid, size = struct.unpack_from('<4sI', data, pos)
        yield cid, data[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)


def read_smpl(path):
    """The loops of a WAV's `smpl` chunk as [(type, start, end)], end being the last frame played; a chunk shorter
    than the loops it counts is refused (ValueError)."""
    for cid, body in chunks(path):
        if cid == b'smpl':
            count = struct.unpack_from('<I', body, 28)[0] if len(body) >= 32 else -1
            if count < 0 or len(body) < 36 + 24 * count:
                raise ValueError(f'{path}: its smpl chunk is shorter than the loops it counts')
            return [struct.unpack_from('<6I', body, 36 + 24 * i)[1:4] for i in range(count)]
    return []


def read_cues(path):
    """Cue points of a WAV as [(frame, label)], in cue order."""
    frames, labels = {}, {}
    for cid, body in chunks(path):
        if cid == b'cue ':
            count = struct.unpack_from('<I', body, 0)[0] if len(body) >= 4 else -1
            if count < 0 or len(body) < 4 + 24 * count:
                raise ValueError(f'{path}: its cue chunk is shorter than the points it counts')
            for k in range(count):
                name, _, _, _, _, offset = struct.unpack_from('<II4sIII', body, 4 + 24 * k)
                frames[name] = offset
        elif cid == b'LIST' and body[:4] == b'adtl':
            pos = 4
            while pos + 8 <= len(body):
                sub, size = struct.unpack_from('<4sI', body, pos)
                if sub == b'labl' and pos + 12 <= len(body):
                    labels[struct.unpack_from('<I', body, pos + 8)[0]] = body[pos + 12:pos + 8 + size].split(b'\0')[0].decode('utf-8', 'replace')
                pos += 8 + size + (size & 1)
    return [(frames[k], labels.get(k, '')) for k in sorted(frames)]


def markers(p, clock, end_f):
    """Section starts inside the file, as (frame, section id)."""
    out = []
    for s in p['sections']:
        frame = round(clock.seconds(s['start_bar'] * clock.beats_per_bar) * audio.RATE)
        if frame < end_f:
            out.append((frame, s['id']))
    return out


def tempo(clock):
    """BPM, beats per bar and beat count for engines that sync music by beat; None where the tempo changes."""
    constant = len(clock.spb) == 1 or len(set(round(x, 9) for x in clock.spb)) == 1
    per_bar = clock.beats_per_bar
    return {'bpm': round(60 / clock.spb[0], 6) if constant else None,
            'bar_beats': int(per_bar) if constant and float(per_bar).is_integer() else None,
            'beat_count': round(clock.total_beats, 6) if constant else None}


def has_vorbis(cfg):
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    out = subprocess.run([cfg['ffmpeg']['path'], '-hide_banner', '-encoders'], capture_output=True, text=True, errors='replace',
                         stdin=subprocess.DEVNULL, creationflags=flags, timeout=30)
    return ' libvorbis ' in out.stdout


def ogg_check(cfg, ogg, logs):
    """Decoded length and loop comments of the Ogg file just written (its own output, never an outside file)."""
    decoded, meta = ogg.with_name('loop_ogg_decoded.wav'), ogg.with_name('loop_ogg_tags.txt')
    base = [cfg['ffmpeg']['path'], '-hide_banner', '-nostdin', '-y', '-protocol_whitelist', 'file', '-f', 'ogg', '-i', ogg]
    before = {p: files.stamp(p) for p in (decoded, meta)}
    try:
        audio.run(base + ['-c:a', 'pcm_f32le', '-f', 'wav', decoded], logs, 'loop_ogg_decode')
        audio.run(base + ['-map_metadata', '0:s:a:0', '-f', 'ffmetadata', meta], logs, 'loop_ogg_tags')
    finally:
        for p, was in before.items():  # FFmpeg writes both there itself: files of the run once it has changed them
            if files.stamp(p) != was:
                files.wrote(p)
    frames = audio.read_wav(decoded)[1]['frames']
    tags = dict(re.findall(r'^(LOOPSTART|LOOPLENGTH)=(\d+)$', meta.read_text(encoding='utf-8', errors='replace'), re.M | re.I))
    decoded.unlink()
    meta.unlink()
    return frames, {k.upper(): int(v) for k, v in tags.items()}


def bpm_at(clock, beat):
    i = max(0, np.searchsorted(clock.beats, beat, side='right') - 1)
    return 60 / clock.spb[i]


def names(pcs):
    return [NAMES[x] for x in sorted(pcs)]


def seam(p, clock, folded=None, master=None):
    """The loop point by Medina-Gray's five aspects.  Score: tempo either side, parts and pitch classes sounding in the
    5 s before the loop end and the 1 s after the loop start, parts still sounding at the end.  With audio: K-weighted
    levels either side, the folded tail against the first second's own music, and the sample step at the jump."""
    start_s, end_s, start_f, end_f = bounds(p, clock)
    before, after = (max(start_s, end_s - BEFORE), end_s), (start_s, min(end_s, start_s + AFTER))
    end_tick = round(clock.total_beats * TPQ)
    parts = {'before': set(), 'after': set()}
    pcs = {'before': set(), 'after': set()}
    held = {}
    for t in p['tracks']:
        notes = performed(t, clock)
        pitched = not t.get('drums') and t['engine'] != 'noise'
        for side, (lo, hi) in (('before', before), ('after', after)):
            hit = [n for n in notes if n['start_seconds'] < hi and n['end_seconds'] > lo]
            if hit:
                parts[side].add(t['id'])
                if pitched:
                    pcs[side] |= {n['pitch'] % 12 for n in hit}
        count = sum(n['end_tick'] >= end_tick for n in notes)
        if count:
            held[t['id']] = count
    shared = pcs['after'] & pcs['before']
    bpm = (round(bpm_at(clock, clock.total_beats - 1 / TPQ), 3), round(bpm_at(clock, p['loop'].get('start_bar', 0) * clock.beats_per_bar), 3))
    report = {
        'windows_seconds': {'before': [round(x, 3) for x in before], 'after': [round(x, 3) for x in after]},
        'meter': {'bpm_at_end': bpm[0], 'bpm_at_start': bpm[1], 'same_tempo': abs(bpm[0] - bpm[1]) < 1e-6, 'on_bar_line': True},
        'timbre': {'before': sorted(parts['before']), 'after': sorted(parts['after']),
                   'continuing': sorted(parts['before'] & parts['after']), 'entering': sorted(parts['after'] - parts['before']),
                   'leaving': sorted(parts['before'] - parts['after'])},
        'pitch': {'after': names(pcs['after']), 'before': names(pcs['before']), 'not_before': names(pcs['after'] - pcs['before']),
                  'share_after_in_before': round(len(shared) / len(pcs['after']), 3) if pcs['after'] else None},
        'abruptness': {'sounding_at_end': held},
    }
    if folded is not None and master is not None:
        win = lambda x: measure.k_level(x) if len(x) > 1 else None
        b5, a1 = folded[max(start_f, end_f - round(BEFORE * audio.RATE)):end_f], folded[start_f:start_f + round(AFTER * audio.RATE)]
        short = round(.4 * audio.RATE)
        own = np.asarray(master[start_f:start_f + round(AFTER * audio.RATE)], dtype=np.float64)
        tail = np.asarray(master[end_f:end_f + round(AFTER * audio.RATE)], dtype=np.float64)
        report['volume'] = {'before_lufs': round(win(b5), 2), 'after_lufs': round(win(a1), 2), 'change_db': round(win(a1) - win(b5), 2),
                            'last_400ms_lufs': round(win(folded[end_f - short:end_f]), 2), 'first_400ms_lufs': round(win(folded[start_f:start_f + short]), 2)}
        local = np.abs(np.diff(folded[end_f - 4800:end_f], axis=0))
        step = float(np.max(np.abs(folded[start_f] - folded[end_f - 1])))
        tail_db, own_db = (win(tail) if np.any(tail) else -120.0), (win(own) if np.any(own) else -120.0)
        report['abruptness'].update({
            'folded_tail_lufs': round(tail_db, 2), 'first_second_own_lufs': round(own_db, 2), 'tail_below_own_db': round(own_db - tail_db, 2),
            'seam_step': round(step, 6), 'seam_step_vs_local_p999': round(step / max(float(np.percentile(local, 99.9)), 1e-9), 2),
            'first_frame_dbfs': round(20 * math.log10(max(float(np.max(np.abs(folded[0]))), 1e-6)), 1)})
    return report


def encode_ogg(cfg, wav, ogg, start_f, end_f, logs, name):
    """Vorbis copy of a loop WAV with LOOPSTART/LOOPLENGTH, and whether its length and tags came out right."""
    # Vorbis comments live in the stream's header, so the tags go on the audio stream, not the container.
    audio.ffmpeg(cfg, ['-i', wav, '-c:a', 'libvorbis', '-q:a', '6', '-metadata:s:a:0', f'LOOPSTART={start_f}',
                       '-metadata:s:a:0', f'LOOPLENGTH={end_f - start_f}', '-fflags', '+bitexact', ogg], logs, name)
    frames, tags = ogg_check(cfg, ogg, logs)
    return frames == end_f, tags == {'LOOPSTART': start_f, 'LOOPLENGTH': end_f - start_f}


def deliver(p, clock, cfg, output, mastering=None, draft=False):
    """loop.wav, loop.ogg and loop.json from master.wav, and the layer loops; returns the report entry and its checks.
    A draft render makes loop.wav, its checks and the seam description, not the Ogg copies or the layers."""
    output = Path(output)
    logs = output / 'logs'
    start_s, end_s, start_f, end_f = bounds(p, clock)
    master, _ = audio.read_wav(output / 'master.wav')
    folded = fold(master, start_f, end_f)
    cues = markers(p, clock, end_f)
    wav, ogg = output / 'loop.wav', output / 'loop.ogg'
    # The tail can add to a peak near the loop start, even past full scale: the peak is measured on a float copy,
    # before the 24-bit file would clip it, and the whole loop comes down rather than clip.
    probe = logs / 'loop_float.wav'
    audio.write_wav(probe, folded)
    peak = audio.measure(cfg, probe, logs, 'measure_loop_float')['true_peak_dbtp']
    probe.unlink()
    gain = -1.05 - peak if peak > -1 else 0.0
    if gain:
        folded = folded * 10 ** (gain / 20)
    write_wav(wav, folded, start_f, end_f, cues)
    measured = audio.measure(cfg, wav, logs, 'measure_loop')
    loops = read_smpl(wav)
    checks = {'loop_length_exact': measured['frames'] == end_f, 'loop_points_in_wav': loops == [(0, start_f, end_f - 1)],
              'loop_true_peak_ceiling': measured['true_peak_dbtp'] <= -1, 'loop_cues_in_wav': read_cues(wav) == cues}
    vorbis = not draft and has_vorbis(cfg)
    entry = {'start_bar': p['loop'].get('start_bar', 0), 'end_bar': p['clock']['bars'], 'sample_rate': audio.RATE,
             'start_sample': start_f, 'end_sample': end_f, 'length_samples': end_f - start_f,
             'start_seconds': round(start_s, 6), 'end_seconds': round(end_s, 6), **tempo(clock),
             'sections': [{'id': label, 'start_sample': frame, 'start_seconds': round(frame / audio.RATE, 6)} for frame, label in cues],
             'files': {'wav': wav.name}, 'gain_db': round(gain, 3), 'integrated_lufs': measured['integrated_lufs'],
             'true_peak_dbtp': measured['true_peak_dbtp'], 'seam': seam(p, clock, folded, master)}
    if draft:
        entry['left_out'] = 'A draft render: the Ogg copies and the layers come with the full render'
    elif vorbis:
        checks['loop_ogg_length_exact'], checks['loop_ogg_tags'] = encode_ogg(cfg, wav, ogg, start_f, end_f, logs, 'loop_ogg')
        entry['files']['ogg'] = ogg.name
    else:
        entry['ogg_skipped'] = 'This FFmpeg has no libvorbis encoder'
    if p['loop'].get('layers') and not draft:
        entry['layers'], layer_checks = layers(p, clock, cfg, output, mastering, start_f, end_f, cues, master, folded, vorbis)
        checks.update(layer_checks)
    keep = ('start_bar', 'end_bar', 'sample_rate', 'start_sample', 'end_sample', 'length_samples', 'start_seconds', 'end_seconds',
            'bpm', 'bar_beats', 'beat_count', 'sections', 'files')
    summary = {k: entry[k] for k in keep}
    if 'layers' in entry:
        summary['layers'] = {lid: {'tracks': v['tracks'], 'files': v['files']} for lid, v in entry['layers']['parts'].items()}
        summary['layers_gain_db'] = entry['layers']['gain_db']
    save_json(output / 'loop.json', summary)
    entry['checks'] = checks
    return entry


def latency(layered, master, start, max_lag=4800):
    """Frames by which the master trails the layers (its limiters look ahead), from the cross-correlation of 30 s."""
    x = np.asarray(layered[start:start + 30 * audio.RATE], dtype=np.float64).mean(axis=1)
    y = np.asarray(master[start:start + 30 * audio.RATE], dtype=np.float64).mean(axis=1)
    n = 1 << (len(x) + max_lag).bit_length()
    corr = np.fft.irfft(np.conj(np.fft.rfft(x, n)) * np.fft.rfft(y, n), n)
    return int(np.argmax(corr[:max_lag + 1]))


def layers(p, clock, cfg, output, mastering, start_f, end_f, cues, master, mix_folded, vorbis):
    """layers/<id>.wav (and .ogg): each layer mixed alone through the buses and spaces, with the master's gains and EQ but
    not its dynamics, delayed by the master's limiter latency and folded like the loop.  One gain for every layer keeps
    them all under -1 dBTP."""
    from . import mixbus
    folder, logs = output / 'layers', output / 'logs'
    folder.mkdir(exist_ok=True)
    frames = round((clock.end + clock.tail) * audio.RATE)
    linear = mixbus.linear_master(mastering)
    raw = {}
    for lid, members in p['loop']['layers'].items():
        premix, processed = folder / f'{lid}_premix.wav', folder / f'{lid}_processed.wav'
        mixbus.mix(p, clock, cfg, output, frames, [t for t in p['tracks'] if t['id'] in members], premix)
        audio.ffmpeg(cfg, ['-i', premix, '-af', linear, '-ar', str(audio.RATE), '-c:a', 'pcm_f32le', processed], logs, f'layer_{lid}')
        raw[lid] = np.asarray(audio.read_wav(processed)[0], dtype=np.float64)
        premix.unlink()
        processed.unlink()
    lag = latency(sum(raw.values()), master, start_f)
    folded = {lid: fold(np.concatenate([np.zeros((lag, x.shape[1])), x[:len(x) - lag]]), start_f, end_f) for lid, x in raw.items()}
    # The layers carry no limiter: scale them together so the loudest sample peak sits below -1 dBFS, then by true peak.
    peak = max(float(np.max(np.abs(x))) for x in folded.values())
    gain = min(0.0, 20 * math.log10(0.85 / max(peak, 1e-9)))
    measured = {}
    for attempt in range(2):
        for lid, x in folded.items():
            write_wav(folder / f'{lid}.wav', x * 10 ** (gain / 20), start_f, end_f, cues)
            measured[lid] = audio.measure(cfg, folder / f'{lid}.wav', logs, f'measure_layer_{lid}')
        loudest = max(m['true_peak_dbtp'] for m in measured.values())
        if loudest <= -1:
            break
        gain += -1.05 - loudest
    total = sum(folded.values()) * 10 ** (gain / 20)
    parts, checks = {}, {'layer_lengths_exact': True, 'layer_points_in_wav': True, 'layer_true_peak_ceiling': True,
                         'layer_cues_in_wav': True}
    for lid, m in measured.items():
        wav = folder / f'{lid}.wav'
        parts[lid] = {'tracks': p['loop']['layers'][lid], 'files': {'wav': f'layers/{wav.name}'},
                      'integrated_lufs': m['integrated_lufs'], 'true_peak_dbtp': m['true_peak_dbtp']}
        checks['layer_lengths_exact'] &= m['frames'] == end_f
        checks['layer_points_in_wav'] &= read_smpl(wav) == [(0, start_f, end_f - 1)]
        checks['layer_true_peak_ceiling'] &= m['true_peak_dbtp'] <= -1
        checks['layer_cues_in_wav'] &= read_cues(wav) == cues
        if vorbis:
            length_ok, tags_ok = encode_ogg(cfg, wav, folder / f'{lid}.ogg', start_f, end_f, logs, f'layer_{lid}_ogg')
            checks['layer_ogg_lengths_exact'] = checks.get('layer_ogg_lengths_exact', True) and length_ok
            checks['layer_ogg_tags'] = checks.get('layer_ogg_tags', True) and tags_ok
            parts[lid]['files']['ogg'] = f'layers/{lid}.ogg'
    # How far the layers played together sit from the delivered loop: the master's compressor and limiter are missing.
    sum_minus_mix = round(measure.k_level(total) - measure.k_level(mix_folded), 2)
    return {'gain_db': round(gain, 3), 'aligned_frames': lag, 'sum_minus_loop_db': sum_minus_mix, 'parts': parts}, checks
