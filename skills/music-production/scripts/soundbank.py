"""Inspect SoundFont banks and build SF2 instruments from licensed WAV sample sets.

inspect: preset inventory (keys, velocity layers, sample rates, loops) of any SF2/SF3-free bank.
build:   a JSON spec maps sample files (regex on file names) to presets.  Each file's pitch is
         measured and checked against its name (octave conventions differ between libraries),
         small intonation errors become fineTune, leading silence is trimmed, levels are matched
         within and across layers, and round robins alternate on neighbouring velocities.
         Unpitched layers (drums) give a fixed `root` key instead of a note in the name, may mix
         several microphones of one hit (`mics`, each with a gain and, for mono, a pan), and may
         share an `exclusive_class` (a closed hi-hat cutting an open one).  A sustained layer can keep
         each recording's own loop (`loop: "recorded"`, from the WAV `smpl` chunk), or have one cut from
         the steady part of a take that has none (`loop: "found"`), so a held note lasts as long as the
         key.  A sustained preset can add one velocity-deaf preset per recorded dynamic (`dynamic_layers`)
         and legato versions of them that enter each take past its attack (`legato`), for the renderer's
         dynamics crossfades and crossfade legato.  FLAC sources are decoded losslessly with FFmpeg (--ffmpeg).  A receipt records every
         source file hash and decision.
split:   recordings of notes played one at a time (a chromatic scale per file and dynamic, as in the University of
         Iowa Musical Instrument Samples) cut into one WAV per note, each checked against the run its file is named for;
         AIFF is read directly.  The manifest (split.json) records every cut and its hash.
cut:     the notes of a split manifest cut again from the same sources and checked against their hashes (installs).
Sample data is never executed.  The output inherits the sample set's license.
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
import numpy as np
from musiclib import files, sf2, wavfile
from musiclib.model import file_hash, save_json

PCS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

def note_number(name):
    m = re.fullmatch(r'([A-Ga-g])([#b]?)(-?\d)', name)
    if not m:
        raise ValueError(f'Unparsed note name {name!r}')
    pc = PCS[m.group(1).upper()] + {'#': 1, 'b': -1, '': 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + pc

def yin_f0(x, rate, fmin=25.0, fmax=4200.0, threshold=0.12):
    """YIN fundamental estimate over a steady excerpt; None when no clear period exists."""
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    tmin, tmax = int(rate / fmax), min(int(rate / fmin), len(x) // 2 - 1)
    if tmax <= tmin + 2:
        return None
    w = len(x) - tmax
    d = np.array([np.sum((x[:w] - x[t:t + w]) ** 2) for t in range(tmax + 1)])
    cmnd = np.ones_like(d)
    cmnd[1:] = d[1:] * np.arange(1, tmax + 1) / np.maximum(np.cumsum(d[1:]), 1e-12)
    cand = np.where(cmnd[tmin:] < threshold)[0]
    if not len(cand):
        return None
    t = tmin + cand[0]
    while t + 1 <= tmax and cmnd[t + 1] < cmnd[t]:
        t += 1
    if 1 <= t < tmax:
        a, b, c = cmnd[t - 1], cmnd[t], cmnd[t + 1]
        shift = 0.5 * (a - c) / max(a - 2 * b + c, 1e-12)
        t = t + max(-1.0, min(1.0, shift))
    return rate / t

def onset(x, rate, threshold_db=-45.0, preroll_ms=3.0):
    env = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    peak = float(env.max())
    if peak <= 0:
        raise ValueError('Silent sample')
    idx = int(np.argmax(env > peak * 10 ** (threshold_db / 20)))
    return max(0, idx - int(rate * preroll_ms / 1000))

def inspect(path):
    bank = sf2.read(path)
    return {'path': str(path), 'sha256': file_hash(path), 'info': {k: v for k, v in bank['info'].items()},
            'samples': len(bank['samples']), 'sm24': bool(bank['sm24']), 'presets': sf2.inventory(bank)}

def _zones_for(notes, keys):
    """Split the keyboard between sampled roots: each root owns keys up to the midpoint, clamped to
    the layer's playable range (roots outside it may still serve the nearest edge keys)."""
    roots = sorted(notes)
    out = {}
    for i, r in enumerate(roots):
        lo = 0 if i == 0 else (roots[i - 1] + r) // 2 + 1
        hi = 127 if i == len(roots) - 1 else (r + roots[i + 1]) // 2
        lo, hi = max(lo, keys[0]), min(hi, keys[1])
        if lo <= hi:
            out[r] = (lo, hi)
    return out

AUDIO = ('.wav', '.flac', '.aif', '.aiff')
MAX_SOURCE_SECONDS = 600  # the longest FLAC recording decoded; the sources the builds pin are 11 MB at most, a minute or two

def audio_files(folder):
    return [f for f in sorted(Path(folder).iterdir()) if f.is_file() and f.suffix.lower() in AUDIO]

def _ext80(b):
    """An IEEE 754 80-bit extended float (AIFF's sample rate)."""
    exponent = int.from_bytes(b[:2], 'big') & 0x7FFF
    mantissa = int.from_bytes(b[2:10], 'big')
    return mantissa * 2.0 ** (exponent - 16383 - 63) if exponent else 0.0

def read_aiff(path):
    """Uncompressed AIFF or AIFC (big-endian PCM, or 'sowt' little-endian) as float frames, with read_audio's info."""
    data = Path(path).read_bytes()
    if data[:4] != b'FORM' or data[8:12] not in (b'AIFF', b'AIFC'):
        raise ValueError(f'{Path(path).name}: not an AIFF file')
    pos, comm, ssnd = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], int.from_bytes(data[pos + 4:pos + 8], 'big')
        if cid == b'COMM':
            comm = data[pos + 8:pos + 8 + size]
        elif cid == b'SSND':
            ssnd = data[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)
    if comm is None or ssnd is None:
        raise ValueError(f'{Path(path).name}: AIFF without COMM or SSND')
    channels, frames, bits = int.from_bytes(comm[:2], 'big'), int.from_bytes(comm[2:6], 'big'), int.from_bytes(comm[6:8], 'big')
    rate = _ext80(comm[8:18])
    kind = comm[18:22] if data[8:12] == b'AIFC' else b'NONE'
    if kind not in (b'NONE', b'twos', b'sowt') or bits not in (8, 16, 24, 32) or not 1 <= channels <= 8 or rate <= 0:
        raise ValueError(f'{Path(path).name}: unsupported AIFF ({kind!r}, {bits} bits)')
    offset = int.from_bytes(ssnd[:4], 'big')
    width = bits // 8
    raw = ssnd[8 + offset:8 + offset + frames * channels * width]
    order = '<' if kind == b'sowt' else '>'
    if width == 3:
        b3 = np.frombuffer(raw, dtype='u1').reshape(-1, 3).astype(np.int32)
        v = (b3[:, 2] | (b3[:, 1] << 8) | (b3[:, 0] << 16)) if order == '>' else (b3[:, 0] | (b3[:, 1] << 8) | (b3[:, 2] << 16))
        x = ((v ^ 0x800000) - 0x800000).astype(np.float32) / 8388608
    else:
        x = np.frombuffer(raw, dtype=f'{order}i{width}').astype(np.float32) / float(1 << (bits - 1))
    x = x[:len(x) // channels * channels].reshape(-1, channels)
    return x, {'rate': int(round(rate)), 'channels': channels, 'bits': bits, 'frames': len(x), 'loops': []}

def write_float_wav(path, x, rate):
    """A 32-bit float WAV at any rate (the splitter's notes keep their source's rate)."""
    x = np.asarray(x, dtype='<f4')
    if x.ndim == 1:
        x = x[:, None]
    data = x.tobytes()
    ch = x.shape[1]
    fmt = (3).to_bytes(2, 'little') + ch.to_bytes(2, 'little') + int(rate).to_bytes(4, 'little') + (rate * ch * 4).to_bytes(4, 'little') + (ch * 4).to_bytes(2, 'little') + (32).to_bytes(2, 'little')
    body = b'WAVE' + b'fmt ' + len(fmt).to_bytes(4, 'little') + fmt + b'data' + len(data).to_bytes(4, 'little') + data
    Path(path).write_bytes(b'RIFF' + len(body).to_bytes(4, 'little') + body)

def pitch_track(mono, rate, fmin, fmax, hop, threshold=0.15, chunk=400, guide=None):
    """YIN (de Cheveigne and Kawahara 2002) on frames `hop` samples apart: f0 in Hz, nan where no period's
    cumulative-mean-normalized difference falls under `threshold`.  With `guide` (lowest, highest Hz) only lags in that
    range count, and the period is the shortest lag whose dip comes within 1.5 times (+0.02) of the range's deepest
    (an octave-up error needs a dip that deep; the first octave down is a longer lag); frames whose deepest dip stays
    over 0.4 are unpitched.  Frame i spans samples i*hop .. i*hop + W."""
    mono = np.asarray(mono, dtype=np.float64)
    tmin, tmax = max(2, int(rate / fmax)), int(rate / fmin) + 2
    w = tmax
    W = w + tmax + 2
    n = max(0, (len(mono) - W) // hop + 1)
    f0 = np.full(n, np.nan)
    if not n:
        return f0, W
    if guide:
        glo, ghi = max(tmin, int(rate / guide[1])), min(tmax - 1, int(rate / guide[0]) + 1)
    nfft = 1 << int(math.ceil(math.log2(W + w)))
    cs = np.concatenate([[0.0], np.cumsum(mono ** 2)])
    taus = np.arange(tmax + 1)
    for c0 in range(0, n, chunk):
        idx = np.arange(c0, min(n, c0 + chunk)) * hop
        frames = mono[idx[:, None] + np.arange(W)]
        r = np.fft.irfft(np.conj(np.fft.rfft(frames[:, :w], nfft)) * np.fft.rfft(frames, nfft), nfft)[:, :tmax + 1]
        e1 = cs[idx + w] - cs[idx]
        e2 = cs[idx[:, None] + taus + w] - cs[idx[:, None] + taus]
        d = np.maximum(e1[:, None] + e2 - 2 * r, 0.0)
        d[:, 0] = 0.0
        cm = np.ones_like(d)
        cm[:, 1:] = d[:, 1:] * taus[1:] / np.maximum(np.cumsum(d[:, 1:], axis=1), 1e-12)
        if guide:
            sub = cm[:, glo:ghi + 1]
            deepest = sub.min(axis=1)
            dip = np.zeros_like(sub, dtype=bool)
            dip[:, 1:-1] = (sub[:, 1:-1] <= sub[:, :-2]) & (sub[:, 1:-1] <= sub[:, 2:])
            ok = dip & (sub <= (1.5 * deepest + 0.02)[:, None])
            first = glo + np.argmax(ok, axis=1)
            rows = np.flatnonzero((deepest < 0.4) & ok.any(axis=1) & (e1 > w * 1e-12))  # digital silence has no pitch
        else:
            below = cm[:, tmin:] < threshold
            first = tmin + np.argmax(below, axis=1)
            rows = np.flatnonzero(below.any(axis=1))
        for k in rows:
            t, row = first[k], cm[k]
            if not guide:
                while t + 1 <= tmax and row[t + 1] < row[t]:
                    t += 1
            if 1 <= t < tmax:
                p, q, s = row[t - 1], row[t], row[t + 1]
                t = t + max(-1.0, min(1.0, 0.5 * (p - s) / max(p - 2 * q + s, 1e-12)))
            f0[c0 + k] = rate / t
    return f0, W

def align_run(x, rate, expected, quiet_db=25.0, edge_db=35.0, min_note=0.25, tolerance=0.8, skip=0.1, partial=False,
              level_db=24.0):
    """Where each note of `expected` (MIDI numbers, rising, in playing order) lies in a recording of them played one
    at a time, as a chromatic scale is recorded for a sample library.

    Candidates first: every 10 ms frame gets a YIN pitch searched only around the run's range, and a level; frames more
    than `quiet_db` under the loudest level within 1.5 s are quiet.  A candidate note runs until a quiet stretch over
    50 ms or until 25 pitched frames in a row (within 0.5 s) settle 0.6 to 3.5 semitones from the median of its last
    30 (their median that far, 80% of them over 0.45: the next note slurred in; vibrato and octave slips stay inside), and is kept if it lasts `min_note` seconds and
    is pitched for 30% of it, and if it rises within `level_db` of the recording's loud notes (the 95th percentile of
    its frame levels) and within `level_db` + 12 of its loudest moment: far from any note the local test stops working,
    and the room's hum or a string's faint ring, pitched by the guided search, would otherwise pass for a note.  Then
    the expected notes are matched to candidates in order by dynamic programming: a match costs its distance in
    semitones (at most `tolerance`; an octave off counts 0.3 more, a candidate shorter than the typical one up to 0.4
    more), each candidate left out costs `skip`, so a note played twice keeps its better-tuned
    take and a stray noise is passed over; with `partial`, a note the file lacks (a string player skipping a note on
    one string) is left out for 0.5.  Each matched note's edges move out while the level keeps falling away from
    it and stays within `edge_db` of its median (taking in attack and release but not a breath or a retake), never into
    another matched note; a plucked note whose candidate begins in its ring starts at the louder attack before it.
    Returns the notes found, [{'start', 'end', 'midi', 'cents', 'f0'}] in samples, and a summary (candidates,
    left out, missing notes); raises when a note cannot be matched and the run is not `partial`."""
    m = np.asarray(x, dtype=np.float64)
    m = m.mean(axis=1) if m.ndim == 2 else m
    hop = int(round(0.01 * rate))
    lo_hz, hi_hz = 440 * 2 ** ((min(expected) - 1.5 - 69) / 12), 440 * 2 ** ((max(expected) + 1.5 - 69) / 12)
    f0, W = pitch_track(m, rate, lo_hz * 0.9, hi_hz * 1.1, hop, guide=(lo_hz, hi_hz))
    n = len(f0)
    if n < 10:
        raise ValueError('recording too short')
    centre = np.arange(n) * hop + W // 2
    seg = np.clip(centre[:, None] + np.arange(-hop // 2, hop // 2)[None, :], 0, len(m) - 1)
    e = 10 * np.log10(np.maximum((m[seg] ** 2).mean(axis=1), 1e-20))
    span = int(1.5 / 0.01)
    pad = np.pad(e, span, mode='edge')
    local = np.lib.stride_tricks.sliding_window_view(pad, 2 * span + 1).max(axis=1)
    quiet = e < local - quiet_db
    semi = np.where(np.isfinite(f0) & ~quiet, 69 + 12 * np.log2(np.where(np.isfinite(f0), f0, 440.0) / 440.0), np.nan)
    # Candidates: stretches between quiet runs over 50 ms, cut where the pitch moves to a new steady value.
    cands, i = [], 0
    while i < n:
        if quiet[i]:
            i += 1
            continue
        j, hush = i, 0
        while j < n and hush <= 5:
            hush = hush + 1 if quiet[j] else 0
            j += 1
        a, b = i, j - hush
        i = j
        at = np.flatnonzero(np.isfinite(semi[a:b])) + a
        vals = semi[at]
        # The next note of a chromatic run lies 1-3 semitones on: a pitch that holds that far from the current note for
        # 25 pitched frames (within 0.5 s) starts a new candidate; a vibrato peak or an octave slip does not, and
        # frames an octave or more away are left out of the pitch.
        # The seed is the commonest semitone of the first 50 pitched frames: an octave slip at the attack cannot set it.
        head = vals[:50]
        mode = np.bincount(np.round(head).astype(int) - int(np.round(head).min())).argmax() + int(np.round(head).min()) if len(head) else 0
        cuts, cur, k, slips = [a], [float(np.median(head[np.round(head) == mode]))] if len(head) else [], 0, set()
        while k < len(at):
            ref = float(np.median(cur[-30:]))
            step = abs(vals[k] - ref)
            if step > 3.5:
                slips.add(int(at[k]))
                k += 1
                continue
            if step > 0.6:
                ahead = vals[k:k + 25]
                dev = np.abs(ahead - ref)
                if (len(ahead) == 25 and abs(np.median(ahead) - ref) > 0.6 and np.mean(dev > 0.45) >= 0.8
                        and np.all(dev < 3.5) and np.ptp(ahead) <= 1.2 and at[min(k + 24, len(at) - 1)] - at[k] <= 50):
                    cuts.append(int(at[k]))
                    cur, k = list(ahead), k + 25
                else:
                    k += 1
                continue
            cur.append(vals[k])
            k += 1
        cuts.append(b)
        for u, v in zip(cuts, cuts[1:]):
            inside = [t for t in at[(at >= u) & (at < v)] if int(t) not in slips]
            cands.append({'a': u, 'b': v, 'p': list(semi[inside])})
    keep = []
    loud = float(np.percentile(e, 95))
    # Plucked runs are mostly ringing, so their 95th percentile sits low; a stretch far under the loudest attack (a
    # previous note's last ring) is no note either.
    peak = float(np.convolve(e, np.ones(5) / 5, mode='same').max())
    for c in cands:
        if (c['b'] - c['a']) * 0.01 < min_note or len(c['p']) < 0.3 * (c['b'] - c['a']):
            continue
        top = float(e[c['a']:c['b']].max())
        if top < loud - level_db or top < peak - level_db - 12:
            continue
        q = np.array(c['p'])
        c['pitch'] = float(np.median(q[len(q) // 4:max(len(q) // 4 + 1, 3 * len(q) // 4)]))
        if keep and keep[-1]['b'] >= c['a'] - 1 and abs(keep[-1]['pitch'] - c['pitch']) < 0.4:
            keep[-1]['b'], keep[-1]['p'] = c['b'], keep[-1]['p'] + c['p']
            continue
        keep.append(c)
    cands = keep
    J, K = len(cands), len(expected)
    if J < K and not partial:
        raise ValueError(f'{K} notes named, {J} found: ' + ' '.join(f'{c["pitch"]:.2f}' for c in cands))
    # Matching in order (an edit-distance alignment): a candidate on a note costs their distance in semitones (at most
    # `tolerance`), a candidate left out costs `skip`, and with `partial` a note left out costs `miss`.
    INF = float('inf')
    # A candidate an octave off (a breathy flute note YIN heard an octave down) still matches, for 0.3 more.
    P, Wn = np.array([c['pitch'] for c in cands]).reshape(1, J), np.array(expected, dtype=float).reshape(K, 1)
    options = np.stack([np.abs(P - Wn), np.abs(P + 12 - Wn) + 0.3, np.abs(P - 12 - Wn) + 0.3])
    octave = np.array([0, 12, -12])[np.argmin(options, axis=0)]
    dist = options.min(axis=0)
    dist[dist > tolerance] = INF
    # A fragment (a stray stretch of bow noise, the tail of a note) loses to a whole take: up to 0.4 more the shorter
    # it is than the typical candidate.
    lengths = np.array([c['b'] - c['a'] for c in cands], dtype=float)
    dist = dist + 0.4 * np.clip(1 - lengths / max(1.0, float(np.median(lengths))), 0, 1)[None, :]
    miss = 0.5 if partial else INF
    D = np.full((K + 1, J + 1), INF)
    move = np.zeros((K + 1, J + 1), dtype=np.int8)
    D[0, :] = skip * np.arange(J + 1)
    move[0, 1:] = 2
    for k in range(1, K + 1):
        D[k, 0] = D[k - 1, 0] + miss
        move[k, 0] = 3
        for j in range(1, J + 1):
            options = (D[k - 1, j - 1] + dist[k - 1, j - 1], D[k, j - 1] + skip, D[k - 1, j] + miss)
            best = int(np.argmin(options))
            D[k, j], move[k, j] = options[best], best + 1
    if not np.isfinite(D[K, J]):
        near = [min(((abs(c['pitch'] - w), c['pitch']) for c in cands), default=(INF, float('nan')))[1] for w in expected]
        bad = [f'MIDI {w} (nearest {p:.2f})' for w, p in zip(expected, near) if not abs(p - w) <= tolerance]
        raise ValueError(f'{K} notes named, {J} found; no in-order match for '
                         + (', '.join(bad) or 'the run ' + ' '.join(f'{c["pitch"]:.2f}' for c in cands)))
    pairs, k, j = [], K, J
    while k or j:
        mv = move[k, j]
        if mv == 1:
            pairs.append((k - 1, j - 1))
            k, j = k - 1, j - 1
        elif mv == 2:
            j -= 1
        else:
            k -= 1
    pairs.reverse()
    matched = {kk: jj for kk, jj in pairs}
    used = sorted(matched.values())
    out = []
    for k, w in enumerate(expected):
        if k not in matched:
            continue
        j = matched[k]
        c = cands[j]
        a, b = c['a'], c['b']
        level = float(np.median(e[a:b]))
        before = [matched[q] for q in matched if matched[q] < j]
        after = [matched[q] for q in matched if matched[q] > j]
        lo = cands[max(before)]['b'] if before else 0
        hi = cands[min(after)]['a'] if after else n
        # A plucked or struck note: its loudest moment, the attack, is too brief and too rich for a steady pitch, so
        # the candidate starts in the ringing that follows.  When a louder burst precedes it within 2 s and the sound
        # does not fall silent in between, the note starts at that burst.
        back = max(lo, a - 200)
        if back < a:
            peak = back + int(np.argmax(e[back:a]))
            if e[peak] > e[a:b].max() + 3 and e[peak:a].min() >= e[a:b].min() - 6:
                a = peak
        while a - 1 >= lo and e[a - 1] > level - edge_db and e[a - 1] <= e[a] + 1.0:
            a -= 1
        while b < hi and e[b] > level - edge_db - 5 and e[b] <= e[b - 1] + 1.0:
            b += 1
        heard = c['pitch'] + octave[k, j]
        out.append({'start': int(max(0, centre[a] - hop // 2)), 'end': int(min(len(m), centre[b - 1] + hop // 2)),
                    'midi': w, 'cents': round((heard - w) * 100, 1), 'f0': round(440 * 2 ** ((heard - 69) / 12), 3)})
    return out, {'candidates': J, 'left_out': J - len(used), 'missing': [w for k, w in enumerate(expected) if k not in matched]}

def spectral_pitch(x, rate, midi, window=(0.05, 0.65), reach=1.0):
    """The frequency of the strongest spectral peak within `reach` semitones of `midi`, from a Hann-windowed spectrum
    of the stretch `window` seconds into `x` (bins of 1 Hz or finer), refined by a parabola through the log magnitudes;
    None when that peak is more than 30 dB under the stretch's strongest, and when the stretch is too short to tell a
    semitone (under 0.1 s or 20 periods of the named note: a short take ends before a default window) or silent.  For
    struck metal (crotales, gongs), whose partials are not harmonic, so that YIN's period is not the pitch heard."""
    seg = np.asarray(x, dtype=np.float64)[int(window[0] * rate):int(window[1] * rate)]
    f = 440 * 2 ** ((midi - 69) / 12)
    if len(seg) < max(0.1 * rate, 20 * rate / f) or not np.any(seg):
        return None
    n = 1 << int(math.ceil(math.log2(max(len(seg), rate))))
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
    freqs = np.arange(len(spec)) * rate / n
    band = np.flatnonzero((freqs >= f * 2 ** (-reach / 12)) & (freqs <= f * 2 ** (reach / 12)))
    k = int(band[np.argmax(spec[band])])
    if spec[k] < spec.max() * 10 ** (-30 / 20) or not 0 < k < len(spec) - 1:
        return None
    a, b, c = np.log(spec[k - 1:k + 2] + 1e-12)
    shift = 0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c else 0.0
    return (k + shift) * rate / n

NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')

def note_name(midi):
    return f'{NOTE_NAMES[midi % 12]}{midi // 12 - 1}'

def _note_run(names):
    """MIDI numbers of a chromatic run given by its first and last note (one name for a single note)."""
    lo, hi = note_number(names[0]), note_number(names[-1])
    if hi < lo:
        raise ValueError(f'Run {names} goes down')
    return list(range(lo, hi + 1))

def contained(root, rel, what):
    """`root`/`rel` for a relative path that stays inside `root` (no absolute path, "..", drive or backslash, and no
    link out of it); a manifest or spec from elsewhere cannot reach other files."""
    parts = PurePosixPath(rel).parts if isinstance(rel, str) else ()
    if not parts or rel.startswith('/') or '..' in parts or ':' in rel or '\\' in rel:
        raise ValueError(f'{what} {rel!r}: expected a relative path inside its folder')
    path = Path(root) / rel
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError(f'{what} {rel!r} leads out of its folder')
    return path

def _cut_note(x, start, end, fade, rate, path):
    """Write samples start..end of `x` as a float WAV, the last `fade` samples faded out; returns the file's SHA-256."""
    y = np.array(x[start:end], dtype=np.float32)
    if fade:
        y[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    write_float_wav(path, y, rate)
    return file_hash(path)

def save_manifest(path, manifest):
    """A split manifest with one record per line: compact enough to keep beside the spec, and line-diffable."""
    lines = ['{']
    for i, key in enumerate(('groups', 'sources', 'notes')):
        rows = ',\n'.join('  ' + json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in manifest[key])
        lines.append(f' "{key}": [\n{rows}\n ]' + (',' if i < 2 else ''))
    lines.append('}')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')

def cut_sources(manifest, src_root, out_root):
    """Cut the notes a `split` manifest records (source, sample span, fade) from the same source files, each checked
    against its recorded SHA-256: an installer reproduces the intake's notes exactly without re-running the note finder,
    whose floating-point decisions could differ by a frame on another platform."""
    src_root, out_root = Path(src_root), Path(out_root)
    by_source, targets = {}, {}
    for n in manifest['notes']:
        contained(src_root, n['source'], 'source')
        path = targets[n['file']] = contained(out_root, n['file'], 'note file')
        if path.exists():
            raise ValueError(f'{n["file"]} exists; cut writes into a new folder')
        by_source.setdefault(n['source'], []).append(n)
    if len(targets) != len(manifest['notes']):
        raise ValueError('Two notes of the manifest write one file')
    for source, notes in by_source.items():
        x, info = read_audio(src_root / source)
        x = np.asarray(x, dtype=np.float32)
        for n in notes:
            path = targets[n['file']]
            path.parent.mkdir(parents=True, exist_ok=True)
            if _cut_note(x, n['start'], n['end'], n['fade'], info['rate'], path) != n['sha256']:
                raise ValueError(f'{n["file"]}: the cut does not reproduce the recorded note')
    return len(manifest['notes'])

def highpass(x, rate, hz, order=6):
    """A zero-phase high-pass by FFT with a Butterworth magnitude, |H| = 1 / sqrt(1 + (hz / f) ** (2 * order)): no
    phase shift, so a note keeps its attack; 0.2 s of zero padding each side keeps the circular wrap out of the take.
    Order 6 takes 10 dB at 0.83 times the cutoff and leaves 1.37 times it within 0.1 dB."""
    x = np.asarray(x)
    dtype, two = x.dtype, x.ndim == 2
    y = np.asarray(x, dtype=np.float64)
    if not two:
        y = y[:, None]
    pad = int(0.2 * rate)
    n = len(y) + 2 * pad
    f = np.fft.rfftfreq(n, 1 / rate)
    H = np.zeros(len(f))
    H[1:] = 1 / np.sqrt(1 + (hz / f[1:]) ** (2 * order))
    out = np.fft.irfft(np.fft.rfft(np.pad(y, ((pad, pad), (0, 0))), axis=0) * H[:, None], n=n, axis=0)[pad:pad + len(y)]
    return (out if two else out[:, 0]).astype(dtype)

def split_sources(split, src_root, out_root):
    """Cut each source file of `split['groups']` into one float WAV per note, named <group>_<dyn>_<note>.wav.

    A file entry gives its dynamic and the chromatic run it holds (`notes`: first and last note, as the publisher named
    the file); align_run finds each of those notes in order (a retake keeps its better-tuned take, within
    `tolerance_cents`, default 80) or refuses the file; in a `partial` group or file a note the file lacks is recorded
    as missing instead.  An entry with `whole` keeps the file as one note (a
    single crotale, a gong), pitch-checked by YIN, or with `pitch: "spectrum"` by its strongest partial near the name
    (struck metal), or not at all with `pitch: false` and `out` naming it.  `quiet_db`,
    `edge_db` and `min_note` tune the note finder per group or file; `fmin` and `fmax` bound the pitch check of a
    `whole` note.  Where several files hold the same
    note at the same dynamic (a violin's notes on more than one string), `strings` gives each string's preferred notes
    and the nearest string that has the note is used.  Returns the manifest: every note's source, sample span, pitch,
    and each source's noise floor."""
    src_root, out_root = Path(src_root), Path(out_root)
    manifest = {'groups': [], 'notes': [], 'sources': []}
    for group in split['groups']:
        opts = {k: group[k] for k in ('quiet_db', 'edge_db', 'min_note', 'partial') if k in group}
        fmin, fmax = group.get('fmin', 25.0), group.get('fmax', 4200.0)
        tolerance = group.get('tolerance_cents', 80)
        candidates = {}
        for entry in group['files']:
            path = contained(src_root, entry['file'], 'source')
            x, info = read_audio(path)
            rate = info['rate']
            x = np.asarray(x, dtype=np.float32)
            source = {'file': entry['file'], 'sha256': file_hash(path), 'rate': rate, 'seconds': round(len(x) / rate, 3)}
            if entry.get('whole'):
                mono = x.mean(axis=1)
                start = max(0, onset(x, rate, entry.get('floor_db', group.get('floor_db', -45.0)), 10.0))
                end = int(np.flatnonzero(np.abs(mono) > 1e-6)[-1]) + 1
                midi = cents = f0 = None
                how = entry.get('pitch', group.get('pitch', True))
                if how:
                    want = _note_run(entry['notes'])[0]
                    seg = mono[start + int(.05 * rate):start + int(.65 * rate)].astype(np.float64)
                    f0 = spectral_pitch(mono[start:], rate, want) if how == 'spectrum' else None
                    for threshold in (0.12, 0.2) if how != 'spectrum' else ():
                        f0 = f0 or yin_f0(seg, rate, entry.get('fmin', fmin), entry.get('fmax', fmax), threshold)
                    exact = None if not f0 else 69 + 12 * math.log2(f0 / 440.0)
                    if exact is not None and entry.get('octave_free', group.get('octave_free')):
                        exact = want + (exact - want + 6) % 12 - 6
                    if exact is not None and abs(exact - want) * 100 > tolerance:
                        raise ValueError(f'{entry["file"]}: named {note_name(want)}, measured {exact:.2f}')
                    midi, cents = want, None if exact is None else round((exact - want) * 100, 1)
                    f0 = None if not f0 else round(f0, 3)
                spans = [{'start': start, 'end': end, 'midi': midi, 'cents': cents, 'f0': f0, 'cut': (start, end)}]
                source['noise_db'] = None
                source['noise_bands'] = noise_bands(x, rate, spans)
            else:
                fo = {**opts, **{k: entry[k] for k in ('quiet_db', 'edge_db', 'min_note', 'partial') if k in entry}}
                # A room's rumble under a soft plucked run can hide its notes from the finder: it then works on a copy
                # high-passed at `analysis_highpass_hz`, and the notes are still cut from the recording as it is.
                hp = entry.get('analysis_highpass_hz', group.get('analysis_highpass_hz'))
                if hp:
                    source['analysis_highpass_hz'] = hp
                try:
                    found, summary = align_run(highpass(x, rate, hp) if hp else x, rate, _note_run(entry['notes']),
                                               tolerance=tolerance / 100, **fo)
                except ValueError as exc:
                    raise ValueError(f'{entry["file"]}: {exc}') from None
                source.update(left_out=summary['left_out'], missing=[note_name(w) for w in summary['missing']])
                for k, n in enumerate(found):
                    # 10 ms before the note and 30 ms after its release, never into the next one.
                    nxt = found[k + 1]['start'] if k + 1 < len(found) else len(x)
                    n['cut'] = (max(0, n['start'] - int(.01 * rate)), min(nxt - int(.005 * rate), n['end'] + int(.03 * rate)))
                spans = found
                # The noise floor: the median level away from every note, under the loudest 5 ms.
                mono = x.mean(axis=1).astype(np.float64)
                hop = int(round(.005 * rate))
                frames = len(mono) // hop
                e = 10 * np.log10(np.maximum((mono[:frames * hop].reshape(frames, hop) ** 2).mean(axis=1), 1e-20))
                inside = np.zeros(frames, dtype=bool)
                for n in found:
                    inside[max(0, n['start'] // hop - 4):n['end'] // hop + 20] = True
                source['noise_db'] = round(float(np.median(e[~inside]) - e.max()), 1) if (~inside).sum() > 20 else None
                source['noise_bands'] = noise_bands(x, rate, found)
            manifest['sources'].append(source)
            for n in spans:
                a, b = n['cut']
                key = (entry['dyn'], entry.get('out') or n['midi'])
                candidates.setdefault(key, []).append({'entry': entry, 'x': x, 'rate': rate, 'start': a, 'end': b, 'note': n})
        prefer = group.get('strings')
        order = list(prefer) if prefer else []
        folder = contained(out_root, group['name'], 'group')
        folder.mkdir(parents=True, exist_ok=True)
        written = 0
        # `leave_out`: takes judged unusable after listening or measuring ({"dyn", "note", "why"}), as a player's
        # soft note in a loud run; the layer then serves that key from a neighbouring dynamic, as for a missing note.
        dropped = {(d['dyn'], d['note']) for d in group.get('leave_out', [])}
        for (dyn, which), cands in sorted(candidates.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
            if (dyn, which if isinstance(which, str) else note_name(which)) in dropped:
                continue
            if prefer and len(cands) > 1:
                def distance(c):
                    lo, hi = prefer[c['entry']['string']]
                    m = c['note']['midi']
                    return (0 if lo <= m <= hi else min(abs(m - lo), abs(m - hi)), order.index(c['entry']['string']))
                pick = min(cands, key=distance)
            elif len(cands) > 1:
                raise ValueError(f'{group["name"]}: {dyn} {which} comes from {len(cands)} files and the group has no `strings` choice')
            else:
                pick = cands[0]
            fade = 0 if pick['entry'].get('whole') else min((pick['end'] - pick['start']) // 4, int(.02 * pick['rate']))
            name = f'{group["name"]}_{dyn}_{which if isinstance(which, str) else note_name(which)}.wav'
            digest = _cut_note(pick['x'], pick['start'], pick['end'], fade, pick['rate'], folder / name)
            written += 1
            n = pick['note']
            manifest['notes'].append({'file': f'{group["name"]}/{name}', 'source': pick['entry']['file'],
                                      'string': pick['entry'].get('string'), 'start': pick['start'], 'end': pick['end'],
                                      'fade': fade, 'sha256': digest,
                                      'seconds': round((pick['end'] - pick['start']) / pick['rate'], 3),
                                      'f0_hz': n['f0'], 'cents': n['cents'],
                                      'alternatives': [c['entry']['file'] for c in cands if c is not pick]})
        manifest['groups'].append({'name': group['name'], 'files': len(group['files']), 'notes': written})
    return manifest

def read_audio(path, ffmpeg=None):
    """A WAV as it is; an AIFF read directly; a FLAC decoded losslessly by FFmpeg into a temporary float WAV first."""
    path = Path(path)
    if path.suffix.lower() in ('.aif', '.aiff', '.aifc'):
        return read_aiff(path)
    if path.suffix.lower() != '.flac':
        return wavfile.read(path)
    if not ffmpeg:
        raise ValueError(f'{path.name}: FLAC sources need --ffmpeg')
    # A FLAC stream starts with the marker "fLaC" (RFC 9639); FFmpeg is held to its FLAC demuxer and to local files, so a file
    # named .flac that is a playlist or another container cannot make it read anything else.
    with open(path, 'rb') as f:
        if f.read(4) != b'fLaC':
            raise ValueError(f'{path.name}: not a FLAC file (no fLaC signature)')
    fd, tmp = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        # Decoded to at most a second past MAX_SOURCE_SECONDS, so the temporary WAV stays bounded whatever the file
        # claims; a longer recording is refused rather than cut.
        subprocess.run([str(ffmpeg), '-hide_banner', '-nostdin', '-v', 'error', '-y', '-protocol_whitelist', 'file',
                        '-f', 'flac', '-i', str(path), '-t', str(MAX_SOURCE_SECONDS + 1), '-c:a', 'pcm_f32le', tmp],
                       check=True, stdin=subprocess.DEVNULL, timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        x, info = wavfile.read(tmp)
        if len(x) > MAX_SOURCE_SECONDS * info['rate']:
            raise ValueError(f'{path.name}: longer than {MAX_SOURCE_SECONDS // 60} minutes, more than a sample recording; cut it first')
        return x, info
    finally:
        os.unlink(tmp)

def mic_mix(paths, mics, ffmpeg):
    """One hit from several microphones of the same take, summed sample-aligned: each scaled by its gain, a mono one
    placed with a constant-power pan.  A single mono microphone without a pan stays mono."""
    out, rate = None, None
    for path, mic in zip(paths, mics):
        x, info = read_audio(path, ffmpeg)
        x = np.asarray(x, dtype=np.float64)
        if rate is not None and info['rate'] != rate:
            raise ValueError(f'{Path(path).name}: sample rate differs between microphones')
        rate = info['rate']
        if x.shape[1] == 1 and (len(mics) > 1 or 'pan' in mic):
            p = float(mic.get('pan', 0.0))
            x = x * np.array([[math.sqrt((1 - p) / 2), math.sqrt((1 + p) / 2)]])
        x = x * float(mic.get('gain', 1.0))
        if out is None:
            out = x
        else:
            if out.shape[1] != x.shape[1]:
                raise ValueError(f'{Path(path).name}: channel layout differs between microphones')
            n = max(len(out), len(x))
            out = np.pad(out, ((0, n - len(out)), (0, 0))) + np.pad(x, ((0, n - len(x)), (0, 0)))
    return out.astype(np.float32), {'rate': rate}

DENOISE_FRAME, DENOISE_HOP = 2048, 512


def _stft(x, frame=DENOISE_FRAME, hop=DENOISE_HOP):
    """Frames of `x` (n, channels) under a periodic square-root Hann window, padded by a frame on each side."""
    win = np.sqrt(np.hanning(frame + 1)[:-1])
    xp = np.pad(np.asarray(x, dtype=np.float64), ((frame, frame + hop), (0, 0)))
    count = (len(xp) - frame) // hop + 1
    idx = np.arange(frame)[None, :] + hop * np.arange(count)[:, None]
    return np.fft.rfft(xp[idx] * win[None, :, None], axis=1), win, len(xp)


def quiet_power(x, below_db=35.0, share=.2, margin=.05, rate=44100):
    """Power per bin (mean over channels) of a take's quietest frames: the lowest `share` of frames that are also
    `below_db` under its loud frames, skipping digital silence and every frame within `margin` seconds of either end
    (where the analysis pads with zeros and a cut fades), so a quiet frame is the noise a recording carries between
    and after notes, not a fade."""
    X, _, _ = _stft(x)
    P = (np.abs(X) ** 2).mean(axis=2)
    e = P.sum(axis=1)
    starts = np.arange(len(P)) * DENOISE_HOP - DENOISE_FRAME
    edge = int(margin * rate)
    live = (e > 1e-14) & (starts >= edge) & (starts + DENOISE_FRAME <= len(x) - edge)
    if live.sum() < 8:
        return None
    loud = np.percentile(e[live], 90)
    cut = min(np.percentile(e[live], 100 * share), loud * 10 ** (-below_db / 10))
    rows = P[live & (e <= cut)]
    return rows if len(rows) else None


NOISE_BANDS = 20 * 2 ** (np.arange(60) / 6)  # 1/6-octave centres from 20 Hz to about 18 kHz


def noise_bands(x, rate, notes, margins=((.3, .5), (.15, .3), (.05, .1)), least=40, spread_db=6.0):
    """The noise of a recording away from its notes, in dB per 1/6-octave band (the power per bin of the denoiser's
    frames, averaged over the channels), or None when fewer than `least` frames qualify.

    A frame qualifies when it lies wholly inside the recording and holds no run of 64 exact zeros (a publisher's gate
    leaves digital silence between notes, and a frame reaching into it reads as less noise), and lies at least
    `before` seconds ahead of every note and `after` behind it; the (before, after) `margins` narrow in turn until
    `least` frames remain, for recordings played with short pauses.  Of those frames only the ones within `spread_db`
    of their quietest tenth count, so a breath, a chair or a note's last ring is left out.  Each bin's power is its
    median over them per channel over ln 2 (the median of an exponentially spread power), and each band takes the
    median of its bins, so a hum line or a stray partial does not raise it."""
    x = np.asarray(x, dtype=np.float64)
    X, _, _ = _stft(x)
    P = np.abs(X) ** 2
    silent = np.all(x == 0, axis=1)
    edges = np.diff(np.concatenate([[0], silent.astype(np.int8), [0]]))
    runs = np.stack([np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)], axis=1)
    runs = runs[runs[:, 1] - runs[:, 0] >= 64]
    mark = np.zeros(len(x) + 1, dtype=np.int64)
    np.add.at(mark, runs[:, 0], 1)
    np.add.at(mark, runs[:, 1], -1)
    gated = np.concatenate([[0], np.cumsum(np.cumsum(mark)[:-1] > 0)])
    # Frame t covers samples [t * hop - frame, t * hop) of the recording (_stft pads a frame ahead).
    end = np.arange(len(P)) * DENOISE_HOP
    start, centre = end - DENOISE_FRAME, end - DENOISE_FRAME // 2
    whole = (start >= 0) & (end <= len(x))
    whole[whole] = gated[end[whole]] == gated[start[whole]]
    rows = None
    for before, after in margins:
        clear = whole.copy()
        for n in notes:
            clear &= (centre < n['start'] - before * rate) | (centre > n['end'] + after * rate)
        if clear.sum() < least:
            continue
        e = P[clear].mean(axis=2).sum(axis=1)
        keep = e <= np.percentile(e, 10) * 10 ** (spread_db / 10)
        if keep.sum() >= least:
            rows = P[clear][keep]
            break
    if rows is None:
        return None
    power = (np.median(rows, axis=0) / math.log(2)).mean(axis=1)
    f = np.fft.rfftfreq(DENOISE_FRAME, 1 / rate)
    out = []
    for c in NOISE_BANDS:
        band = (f >= c * 2 ** (-1 / 12)) & (f < c * 2 ** (1 / 12))
        value = np.median(power[band]) if band.any() else power[np.argmin(np.abs(f - c))]
        out.append(round(float(10 * np.log10(value + 1e-30)), 1))
    return out


def bands_to_bins(bands, rate):
    """Noise power per bin of the denoiser's frames from 1/6-octave band levels, interpolated over log frequency."""
    f = np.fft.rfftfreq(DENOISE_FRAME, 1 / rate)
    db = np.interp(np.log2(np.maximum(f, NOISE_BANDS[0])), np.log2(NOISE_BANDS), np.asarray(bands, dtype=np.float64))
    return 10 ** (db / 10)


def partial_bins(pitch, below, rate):
    """The bins of the denoiser's frames that hold a note's partials under `below` Hz (`pitch`: a MIDI number with
    cents): those within the window's main lobe (1.5 bins) or 3 % of each harmonic."""
    f0 = 440.0 * 2 ** ((pitch - 69) / 12)
    f = np.fft.rfftfreq(DENOISE_FRAME, 1 / rate)
    keep = np.zeros(len(f), dtype=bool)
    for h in range(1, int(below // f0) + 1):
        keep |= np.abs(f - h * f0) <= max(1.5 * rate / DENOISE_FRAME, .03 * h * f0)
    return keep


def denoise(x, noise, reduce_db=12.0, alpha=.98, keep=None):
    """Reduce stationary recording noise (`noise`: its power per bin in this frame size) by up to `reduce_db`.

    A short-time Wiener gain per bin from a decision-directed estimate of the a-priori SNR (Ephraim and Malah 1984;
    Scalart and Filho 1996): the estimate follows the signal with the smoothing `alpha` of the previous frame's
    gain, which keeps the residual noise from flickering into 'musical noise' (Cappe 1994).  The gain never falls
    under -reduce_db, is shared by both channels so the stereo image stays, and is smoothed over three bins.  With
    nothing above the noise the output equals the input to rounding.  The bins in `keep` (partial_bins of the note)
    stay as recorded: a soft low note can be no louder than the room's rumble, and the gain cannot tell the two
    apart there."""
    dtype = np.asarray(x).dtype
    x = np.asarray(x, dtype=np.float64)
    n, ch = x.shape
    X, win, size = _stft(x)
    gamma = (np.abs(X) ** 2).mean(axis=2) / np.maximum(noise, 1e-30)[None, :]
    floor = 10 ** (-reduce_db / 20)
    G = np.empty_like(gamma)
    prev_g, prev_gamma = np.ones(gamma.shape[1]), np.ones(gamma.shape[1])
    for t in range(len(gamma)):
        xi = alpha * prev_g ** 2 * prev_gamma + (1 - alpha) * np.maximum(gamma[t] - 1, 0)
        g = np.maximum(xi / (1 + xi), floor)
        G[t], prev_g, prev_gamma = g, g, gamma[t]
    G[:, 1:-1] = (G[:, :-2] + G[:, 1:-1] + G[:, 2:]) / 3
    if keep is not None:
        G[:, keep] = 1.0
    y = np.fft.irfft(X * G[:, :, None], n=DENOISE_FRAME, axis=1) * win[None, :, None]
    out = np.zeros((size, ch))
    count = len(y)
    for j in range(DENOISE_FRAME // DENOISE_HOP):
        seg = y[:, j * DENOISE_HOP:(j + 1) * DENOISE_HOP, :].reshape(-1, ch)
        out[j * DENOISE_HOP:j * DENOISE_HOP + len(seg)] += seg
    # A periodic Hann window (the product of the two square roots) sums to 2 at a quarter-frame hop.
    return (out[DENOISE_FRAME:DENOISE_FRAME + n] / 2).astype(dtype)


CLICK_FRAME, CLICK_HOP = 1024, 128


def _side_means(L, near, far):
    """Per frame and bin, the mean of L over the frames `near` to `far` before it and `near` to `far` after it (an
    edge borrows the other side)."""
    n = len(L)
    c = np.concatenate([np.zeros((1, L.shape[1])), np.cumsum(L, axis=0)])
    t = np.arange(n)

    def mean(lo, hi):
        lo, hi = np.clip(lo, 0, n), np.clip(hi, 0, n)
        return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)[:, None], hi > lo
    before, has_b = mean(t - far, t - near + 1)
    after, has_a = mean(t + near, t + far + 1)
    before[~has_b] = after[~has_b]
    after[~has_a] = before[~has_a]
    return before, after


def find_clicks(x, rate, after=.15, share=.4, rise_db=6.0, strength_db=6.0, alone=.25, alone_db=4.0, longest=.15):
    """Mechanical clicks in a ringing take (a key or the action knocking while the string rings on): spans of
    samples [start, end, strength_db], `after` seconds past the onset at the earliest.

    A click is broadband and stands alone.  Its frames (CLICK_FRAME samples every CLICK_HOP) lift at least `share`
    of the bins from 2 to 12 kHz more than `rise_db` over their mean level 50-120 ms before and after (the higher
    of the two); its 3-12 kHz band stands `strength_db` over the median of the frames 20-110 ms either side; and
    nothing else within `alone` seconds rises within `alone_db` of it.  A low string's own sound pulses once a
    period (every 36 ms on A0) and a soft take's hammer noise flickers, so those rise again and again and are left
    as they are.  A burst longer than `longest` seconds is not taken for a click."""
    X, _, _ = _stft(np.asarray(x, dtype=np.float64).mean(axis=1, keepdims=True), CLICK_FRAME, CLICK_HOP)
    L = 10 * np.log10(np.abs(X[:, :, 0]) ** 2 + 1e-30)
    f = np.fft.rfftfreq(CLICK_FRAME, 1 / rate)
    wide = (f >= 2000) & (f < 12000)
    before, behind = _side_means(L[:, wide], int(.05 * rate / CLICK_HOP), int(.12 * rate / CLICK_HOP))
    lifted = (L[:, wide] - np.maximum(before, behind) > rise_db).mean(axis=1)
    band = 10 * np.log10((10 ** (L[:, (f >= 3000) & (f < 12000)] / 10)).sum(axis=1) + 1e-30)
    band = np.maximum(band, band.max() - 100)                     # the zeros padded past either end
    near, far = int(.02 * rate / CLICK_HOP), int(.11 * rate / CLICK_HOP)
    window = np.lib.stride_tricks.sliding_window_view(np.pad(band, far, mode='edge'), 2 * far + 1)
    rise = band - np.median(np.concatenate([window[:, :far - near + 1], window[:, far + near:]], axis=1), axis=1)
    starts = np.arange(len(L)) * CLICK_HOP - CLICK_FRAME          # frame t holds x[starts[t]:starts[t] + CLICK_FRAME]
    events, t = [], int(np.searchsorted(starts, after * rate))
    while t < len(L):
        if lifted[t] <= share / 4 and rise[t] <= 2:
            t += 1
            continue
        first = t
        while t + 1 < len(L) and (lifted[t + 1] > share / 4 or rise[t + 1] > 2):
            t += 1
        events.append((first, t, float(lifted[first:t + 1].max()), float(rise[first:t + 1].max())))
        t += 1
    reach = int(alone * rate / CLICK_HOP)
    spans = []
    for first, last, wide_share, strength in events:
        if wide_share <= share or strength < strength_db:
            continue
        rivals = [s for a, b, _, s in events if (a, b) != (first, last) and a < last + reach and b > first - reach]
        s0, s1 = max(0, int(starts[first])), min(len(x), int(starts[last]) + CLICK_FRAME)
        # The repair needs clean frames after the span: a take cut off while it still sounds ends in a step, not a click.
        if s1 + 6 * CLICK_FRAME > len(x):
            continue
        if (not rivals or strength - max(rivals) >= alone_db) and s1 - s0 <= longest * rate + CLICK_FRAME:
            if spans and s0 <= spans[-1][1] + CLICK_FRAME:
                spans[-1] = [spans[-1][0], max(spans[-1][1], s1), max(spans[-1][2], round(strength, 1))]
            else:
                spans.append([s0, s1, round(strength, 1)])
    return spans


def declick(x, rate, spans, margin_db=1.5, reference=4):
    """Repair `spans` ([start, end, ...] in samples) of `x` (n, channels).  In the frames that reach into a span, each
    bin is held to its level interpolated, in log power, between the `reference` frames just before the span and
    just after it, plus `margin_db`, with its phase kept (the gain is shared by the channels, so the stereo image
    stays).  A ringing partial holds its level across the span and passes; the click's added noise does not.  The
    reference level is a median over frames, divided by ln 2 for a noise-like bin's mean power.  Samples the changed
    frames do not reach stay as they were, bit for bit."""
    y = np.array(x, copy=True)
    lift = math.log(10 ** (margin_db / 10) / math.log(2))
    for s0, s1, *_ in spans:
        a0 = max(0, s0 - (reference + 2) * CLICK_FRAME)
        a1 = min(len(x), s1 + (reference + 2) * CLICK_FRAME)
        seg = np.asarray(x[a0:a1], dtype=np.float64)
        X, win, size = _stft(seg, CLICK_FRAME, CLICK_HOP)
        st = np.arange(len(X)) * CLICK_HOP - CLICK_FRAME
        en = st + CLICK_FRAME
        inside = np.flatnonzero((en > s0 - a0) & (st < s1 - a0))
        before = np.flatnonzero((en <= s0 - a0) & (st >= 0))[-reference:]
        behind = np.flatnonzero((st >= s1 - a0) & (en <= len(seg)))[:reference]
        if len(before) < 2 or len(behind) < 2:
            continue
        P = (np.abs(X) ** 2).mean(axis=2)
        lb = np.median(np.log(P[before] + 1e-30), axis=0)
        la = np.median(np.log(P[behind] + 1e-30), axis=0)
        cb, ca = st[before].mean(), st[behind].mean()
        for t in inside:
            limit = np.exp(lb + (la - lb) * (st[t] - cb) / (ca - cb) + lift)
            X[t] *= np.sqrt(np.minimum(1.0, limit / np.maximum(P[t], 1e-30)))[:, None]
        frames = np.fft.irfft(X, n=CLICK_FRAME, axis=1) * win[None, :, None]
        out = np.zeros((size, seg.shape[1]))
        for t in range(len(frames)):
            out[t * CLICK_HOP:t * CLICK_HOP + CLICK_FRAME] += frames[t]
        # A periodic Hann window (the product of the two square roots) sums to frame / (2 hop) at that hop.
        out = out[CLICK_FRAME:CLICK_FRAME + len(seg)] / (CLICK_FRAME / (2 * CLICK_HOP))
        w0, w1 = max(0, st[inside[0]]), min(len(seg), en[inside[-1]])
        y[a0 + w0:a0 + w1] = out[w0:w1]
    return y


def steady_loop(x, rate, loop, sag_db=2.0, crossfade=0.15, found=False, noise_db=4.0, period_search=False, f0=None,
                min_loop=0.8, match_seconds=0.0):
    """A recorded loop whose end sags (the player easing off at the end of the take) pulses on every repeat.  This
    keeps the loop start, moves the end back to the last point where the 0.3 s before it stays within `sag_db` of the
    loop's median level, then within 25 ms to where the last 20 ms best match the 20 ms before the loop start, and
    crossfades the final `crossfade` seconds into the audio leading to the loop start (never into the first 0.25 s,
    the attack).  With `period_search` and the note's `f0`, the match compares at least one period (a low brass pedal
    note at 30-60 Hz has periods longer than 20 ms; `match_seconds` lengthens it, so a vibrato's phase is matched as
    well as the waveform) and the end is searched over the last 0.3 s of the steady part, keeping at least 0.5 s of
    loop.  A loop `found` in a take without one spans the take to its end, release included, so when less than
    `min_loop` seconds (0.8) stay steady the loop keeps that long rather than the release.  Returns the data, the new loop and the match (a
    correlation)."""
    ls, le = loop
    mono = x.mean(axis=1) if x.ndim == 2 else x
    hop, span = int(.05 * rate), 6
    level = np.array([20 * np.log10(np.sqrt(np.mean(mono[i:i + hop] ** 2)) + 1e-12) for i in range(ls, le - hop + 1, hop)])
    if found:
        # A take with no loop of its own may hold noises (a key, a valve, a breath) that a loop would repeat every
        # cycle: the loop takes the longest stretch between frames more than `noise_db` over the median of their own
        # half second (slow beating between organ ranks or a bow's swell moves that median along), 0.3 s clear of each.
        # A tremolo flickers by itself and needs a higher threshold.
        local = np.array([np.median(level[max(0, i - 5):i + 6]) for i in range(len(level))])
        noise = np.flatnonzero(level - local > noise_db)
        if len(noise):
            edges = [-1 - span] + list(noise) + [len(level) + span]
            a, b = max(zip(edges, edges[1:]), key=lambda ab: ab[1] - ab[0])
            a, b = max(0, a + 1 + span), min(len(level), b - span)
            if b - a >= 16:
                ls, le, level = ls + a * hop, ls + b * hop, level[a:b]
    floor = np.median(level) - sag_db
    end = next((ls + k * hop for k in range(len(level), span - 1, -1) if level[k - span:k].min() >= floor), le)
    if end - ls < int(min_loop * rate):
        end = ls + int(min_loop * rate) if found else le
    w = int(.02 * rate)
    ref = mono[ls - w:ls]
    def match(c):
        seg = mono[c - w:c]
        return float(np.dot(seg, ref) / (np.linalg.norm(seg) * np.linalg.norm(ref) + 1e-12))
    if period_search and f0:
        # The end is searched over the last 0.3 s of the steady part, keeping at least 0.5 s of loop, and always over
        # at least 1.2 periods (or 25 ms) even where the steady part is short.
        w = min(max(w, int(rate / f0), int(match_seconds * rate)), ls)
        ref = mono[ls - w:ls]
        least = max(int(.025 * rate), int(1.2 * rate / f0))
        lower = max(ls + w, min(max(end - int(.3 * rate), ls + int(min(.5, min_loop) * rate)), end - least))
        segs = np.lib.stride_tricks.sliding_window_view(mono[lower - w:end], w)
        scores = segs @ ref / (np.sqrt((segs ** 2).sum(axis=1)) * np.linalg.norm(ref) + 1e-12)
        end = lower + int(np.argmax(scores))
    else:
        end = max(range(end - int(.025 * rate), end + 1), key=match)
    score = match(end)
    n = min(int(crossfade * rate), ls - int(.25 * rate))
    if n > 0:
        t = ((np.arange(n) + .5) / n)[:, None]
        # Matched in phase the two stretches add like one signal (gains summing to 1); otherwise keep their power.
        a, b = (1 - t, t) if score > .5 else (np.cos(t * np.pi / 2), np.sin(t * np.pi / 2))
        x = x.copy()
        x[end - n:end] = x[end - n:end] * a + x[ls - n:ls] * b
    return np.concatenate([x[:end], x[ls:ls + 16]]), (ls, end), score

def attack_end(x, rate, loop=None, margin=0.02, cap=0.6):
    """Where a sustained take has finished its attack, in samples: the first 10 ms frame within 2 dB of the take's
    steady level (the median over its loop, or from 0.4 to 2.5 s), plus `margin`.  A legato note starts there, as SFZ
    legato regions skip a sustained sample's start with `offset`; it stays under `cap` seconds and before the loop."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    hop = int(.01 * rate)
    frames = len(mono) // hop
    if frames < 10:
        return 0
    level = 20 * np.log10(np.sqrt(np.mean(mono[:frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-12)
    a, b = (loop[0] // hop, loop[1] // hop) if loop else (int(.4 * rate) // hop, min(frames, int(2.5 * rate) // hop))
    if b - a < 5:
        return 0
    reached = np.flatnonzero(level[:b] >= np.median(level[a:b]) - 2.0)
    end = min(cap, (reached[0] + 1) * hop / rate + margin if len(reached) else 0.0)
    if loop:
        end = min(end, loop[0] / rate - .02)
    return max(0, int(end * rate))

def _borrowed_cb(layer, src, dyn):
    """With `borrowed_level: "served"`, a dynamic borrowed from a louder one plays that much quieter (centibels of
    zone attenuation, from `layer_levels_db`), so a register recorded only at mf still enters softly at pp.  0 when
    the take is the note's own dynamic, the layer keeps recorded levels, or the borrowed dynamic is the softer one
    (SF2 attenuation cannot raise a level)."""
    shape = layer.get('layer_levels_db')
    if src == dyn or layer.get('borrowed_level') != 'served' or not shape:
        return 0
    return max(0, int(round(10 * (shape[src] - shape[dyn]))))

def _derived_presets(pspec, contexts, stored, instruments, presets, receipt):
    """The `dynamic_layers` and `legato` presets of a sustained preset.

    A sampler crossfades between recorded dynamics along a controller (SFZ's xfin/xfout on CC1); an SF2 zone can only
    choose a recording by velocity.  So each recorded dynamic becomes a preset of its own at bank
    `dynamic_layers.bank` + k (k = 0 for the softest), which ignores velocity, and the renderer plays a part once per
    dynamic and crossfades the renders (musiclib/layered.py).  With `legato`, bank `legato.bank` + k holds the same takes
    started past their attack, as SFZ legato regions skip a sustained sample's start with `offset`, and faded in over
    `legato.attack` seconds.  A layer with fewer recorded dynamics than the preset's richest maps onto the same scale.
    Round robins alternate in blocks of 16 velocities, since velocity no longer sets the level."""
    dl, leg = pspec.get('dynamic_layers'), pspec.get('legato')
    if not dl:
        if leg:
            raise ValueError(f'{pspec["name"]}: legato presets need dynamic_layers')
        return
    count = max(len(c['layer']['dynamics']) for c in contexts)
    neutral = sf2.override(sf2.VELOCITY_TO_ATTENUATION, 0) + sf2.override(sf2.VELOCITY_TO_FILTER, 0)
    report = {'preset': pspec['name'], 'program': pspec['program'], 'layer_banks': [], 'legato_banks': [], 'legato_offsets_ms': []}
    for kind, base in (('layer', dl['bank']), ('legato', leg['bank'] if leg else None)):
        if base is None:
            continue
        for k in range(count):
            first = len(instruments)
            for c in contexts:
                layer, order = c['layer'], list(c['layer']['dynamics'])
                dyn = order[round(k * (len(order) - 1) / (count - 1))] if count > 1 else order[-1]
                by = {}
                for e in c['entries']:
                    by.setdefault((e['named'], e['dyn']), []).append(e)
                zones = []
                for note in c['notes']:
                    if note not in c['keymap']:
                        continue
                    lo_key, hi_key = c['keymap'][note]
                    have = [d for d in order if (note, d) in by]
                    src = dyn if (note, dyn) in by else min(have, key=lambda d: (abs(order.index(d) - order.index(dyn)), -order.index(d)))
                    group = sorted(by[(note, src)], key=lambda e: str(e['rr']))
                    quieter = _borrowed_cb(layer, src, dyn)
                    for pos, e in enumerate(group):
                        ids = stored[(e['take'], round(e['gain'], 6), e['named'])][0]
                        fine = 0 if e['cents'] is None or abs(e['cents']) > layer.get('max_correction_cents', 45) else -int(round(e['cents']))
                        spans = [(v, min(127, v + 15)) for v in range(1, 128, 16) if ((v - 1) // 16) % len(group) == pos] if len(group) > 1 else [(1, 127)]
                        offset = attack_end(e['x'], e['rate'], e.get('loop')) if kind == 'legato' else 0
                        if kind == 'legato':
                            report['legato_offsets_ms'].append(round(1000 * offset / e['rate'], 1))
                        for span in spans:
                            for ch, sid in enumerate(ids):
                                z = {43: (lo_key, hi_key), 44: span, 58: e['named']}
                                if fine:
                                    z[52] = fine
                                if quieter:
                                    z[48] = c['gens'].get(48, 0) + quieter
                                if offset:
                                    z[0], z[4] = offset % 32768, offset // 32768
                                if e.get('loop'):
                                    z[54] = 1
                                if layer.get('exclusive_class'):
                                    z[57] = int(layer['exclusive_class'])
                                if len(ids) == 2:
                                    z[17] = -500 if ch == 0 else 500
                                zones.append({'gens': z, 'sample': sid})
                gens = dict(c['gens'])
                if kind == 'legato':
                    gens[34] = sf2.timecents(leg.get('attack', 0.01))
                instruments.append({'name': f'{pspec["name"][:12]} {"dL"[kind == "legato"]}{k + 1}.{len(instruments) - first + 1}',
                                    'global': gens, 'zones': zones, 'mods': neutral})
            presets.append({'name': f'{pspec["name"][:15]} {"dL"[kind == "legato"]}{k + 1}', 'bank': base + k,
                            'program': pspec['program'], 'global': {},
                            'zones': [{'gens': {}, 'instrument': i} for i in range(first, len(instruments))]})
            report[f'{kind}_banks'].append(base + k)
    offsets = report.pop('legato_offsets_ms')
    if offsets:
        report['legato_offset_ms'] = {'min': min(offsets), 'median': float(np.median(offsets)), 'max': max(offsets)}
    receipt.setdefault('derived', []).append(report)

def _split_pitches(root):
    """Each note file's measured offset in cents from its name, from the manifest `split` wrote beside the notes."""
    manifest = json.loads((Path(root) / 'split.json').read_text(encoding='utf-8'))
    return {n['file'].replace('\\', '/'): n['cents'] for n in manifest['notes'] if n.get('cents') is not None}

def _load_layer(layer, root, ffmpeg, loaded, receipt):
    """Match, load, trim and measure one layer's takes; returns its entries (octave-checked) and per-dynamic medians."""
    rx = re.compile(layer['pattern'])
    # `pitch_source: "split"`: notes cut by `split` keep the pitch measured over their whole steady part, so a low
    # pedal note that defeats a short YIN excerpt is still tuned.
    split_cents = _split_pitches(root) if layer.get('pitch_source') == 'split' else None
    mics = layer.get('mics')
    folder = root / (mics[0]['dir'] if mics else layer['dir'])
    entries = []
    for f in audio_files(folder):
        m = rx.fullmatch(f.name)
        if not m:
            receipt['files'].append({'file': str(f.relative_to(root)), 'skipped': 'name does not match pattern'})
            continue
        g = m.groupdict()
        dyn = g.get('dyn') or 'default'
        if dyn not in layer['dynamics']:
            continue
        if g.get('rr') and str(g['rr']) not in [str(r) for r in layer.get('round_robins', [g['rr']])]:
            continue
        # Takes named by position rather than pitch (a timpani's tuning letter) get their pitch from `pitches`, a
        # MIDI number with cents measured beforehand; positions left out of it are not used.
        measured = layer['pitches'].get(g.get('id')) if 'pitches' in layer else None
        if 'pitches' in layer and measured is None:
            receipt['files'].append({'file': str(f.relative_to(root)), 'skipped': 'position not in the layer pitches'})
            continue
        named = (layer['root'] if 'root' in layer else round(measured) if measured is not None
                 else note_number(g['note']) + layer.get('octave_offset', 0))
        if split_cents is not None:
            rel = f.relative_to(root).as_posix()
            if rel not in split_cents:
                raise ValueError(f'{rel}: not in split.json')
            measured = named + split_cents[rel] / 100
        # Every microphone recorded the same take in its own folder, under the same file name or one that differs by the
        # microphone's own tag (`name`: [text in the first microphone's file name, text in this one's]).
        files = [f] + [root / mic['dir'] / (f.name.replace(*mic['name']) if mic.get('name') else f.name) for mic in (mics or [])[1:]]
        for other in files[1:]:
            if not other.is_file():
                raise ValueError(f'{other.relative_to(root)}: no take for this microphone')
        entries.append({'file': f, 'files': files, 'named': named, 'dyn': dyn, 'rr': g.get('rr') or '1', 'measured': measured})
    if not entries:
        raise ValueError(f'No samples matched {folder.relative_to(root)}')
    # Load, trim, measure pitch and level.
    looped = layer.get('loop') in ('recorded', 'found')
    dn = layer.get('denoise')
    dc = layer.get('declick')
    # `highpass`: {"ratio", "max_hz"}, a zero-phase high-pass at that fraction of each take's fundamental, at most
    # max_hz, before anything else: a room's rumble under soft plucked notes, which a stationary denoiser cannot follow.
    hpf = layer.get('highpass')
    noise, per_take, profile_from = {}, {}, {}
    if dn and (root / 'split.json').is_file():
        # Notes cut from longer recordings: each take uses its recording's own noise, measured between its notes when
        # it was split (the manifest stores it, rounded, so every build gets the same numbers).  A recording played
        # without pauses borrows the median, band by band, of the recordings of the same layer and dynamic that have
        # one (one session, one setup), or of all the layer's.
        manifest = json.loads((root / 'split.json').read_text(encoding='utf-8'))
        bands = {s['file']: s.get('noise_bands') for s in manifest['sources']}
        source_of = {n['file']: n['source'] for n in manifest['notes']}
        measured = {}
        for e in entries:
            rel = e['file'].relative_to(root).as_posix()
            if bands.get(source_of.get(rel)):
                per_take[rel], profile_from[rel] = bands[source_of[rel]], 'recording'
                measured.setdefault(e['dyn'], {})[source_of[rel]] = bands[source_of[rel]]
        everywhere = {s: b for found in measured.values() for s, b in found.items()}
        for e in entries:
            rel = e['file'].relative_to(root).as_posix()
            near = measured.get(e['dyn']) or everywhere
            if rel in source_of and rel not in per_take and near:
                per_take[rel] = [round(float(v), 1) for v in np.median(np.array([near[s] for s in sorted(near)]), axis=0)]
                profile_from[rel] = 'same dynamic' if measured.get(e['dyn']) else 'same layer'
    if dn:
        # Takes without a measured recording: the noise of each recorded dynamic, the quiet frames of its takes pooled
        # (one session, one setup).
        pooled = {}
        for e in entries:
            if e['file'].relative_to(root).as_posix() in per_take:
                continue
            x, _ = mic_mix(e['files'], mics, ffmpeg) if mics else read_audio(e['file'], ffmpeg)
            rows = quiet_power(x)
            if rows is not None:
                pooled.setdefault(e['dyn'], []).append(rows)
        everything = [r for rows in pooled.values() for r in rows]
        for dyn in {e['dyn'] for e in entries}:
            rows = pooled.get(dyn) or everything
            if rows and sum(len(r) for r in rows) >= 20:
                noise[dyn] = np.concatenate(rows).mean(axis=0)
    for e in entries:
        key = (str(e['file']) if not mics and not looped and not dn and dc is None and not hpf else
               json.dumps([[str(f) for f in e['files']], mics, layer.get('onset_db'), layer.get('max_seconds'), layer.get('ring_db'), looped,
                           layer.get('loop_repair'), dn] + ([layer['loop'], layer.get('loop_window')] if layer.get('loop') == 'found' else [])
                          + ([dc] if dc is not None else []) + ([hpf, e['named']] if hpf else [])))
        if key not in loaded:
            x, info = mic_mix(e['files'], mics, ffmpeg) if mics else read_audio(e['file'], ffmpeg)
            if hpf:
                f0 = 440.0 * 2 ** ((e['named'] - 69) / 12)
                x = highpass(x, info['rate'], min(hpf.get('max_hz', 120.0), hpf.get('ratio', 0.73) * f0))
            noise_db = noise_from = None
            rel = e['file'].relative_to(root).as_posix()
            keep = (partial_bins(e['measured'], dn['keep_partials_below'], info['rate'])
                    if dn and dn.get('keep_partials_below') and e['measured'] is not None else None)
            if dn and rel in per_take:
                profile = bands_to_bins(per_take[rel], info['rate'])
                x = denoise(x, profile, dn.get('reduce_db', 12.0), keep=keep)
                noise_db = round(10 * math.log10(4 * profile.sum() / DENOISE_FRAME ** 2 + 1e-30), 1)
                noise_from = profile_from[rel]
            elif dn and e['dyn'] in noise:
                x = denoise(x, noise[e['dyn']], dn.get('reduce_db', 12.0), keep=keep)
                noise_db = round(10 * math.log10(4 * noise[e['dyn']].sum() / DENOISE_FRAME ** 2 + 1e-30), 1)
                noise_from = 'quiet frames'
            # Short articulations use a higher threshold so pre-attack bow/breath noise is cut.
            start = onset(x, info['rate'], layer.get('onset_db', -45.0))
            x = x[start:]
            # `declick` (options of find_clicks, {} for its defaults): a take that rings on while the action knocks
            # (a key let go under the sustain pedal) has the knock repaired before the ring cut is measured.
            clicks = find_clicks(x, info['rate'], **dc) if dc is not None else []
            if clicks:
                x = declick(x, info['rate'], clicks)
            loop = None
            if layer.get('loop') == 'recorded':
                if not info.get('loops'):
                    raise ValueError(f'{e["file"].name}: no recorded loop (a WAV smpl chunk) to keep')
                ls, le = info['loops'][0]
                if ls < start:
                    raise ValueError(f'{e["file"].name}: the silence trim reaches into the recorded loop')
                loop = (ls - start, le - start)
            elif layer.get('loop') == 'found':
                # A take recorded without a loop: one is cut from `loop_window` (seconds after the onset), its end
                # moved back to the last steady point and matched to the start by steady_loop below.
                a, b = layer.get('loop_window', [.8, 600.0])
                shortest = layer.get('loop_repair', {}).get('min_loop', .8)
                # A take too short for the window's start loops from earlier, never inside its first 0.15 s.
                if len(x) - 8 - int(a * info['rate']) < int(shortest * info['rate']):
                    a = max(.15, (len(x) - 8) / info['rate'] - shortest - .02)
                loop = (int(a * info['rate']), min(len(x) - 8, int(b * info['rate'])))
                if loop[1] - loop[0] < int(shortest * info['rate']):
                    raise ValueError(f'{e["file"].name}: less than {shortest} s after {a} s to loop')
            # `ring_db`: each take ends where its ring last reaches that far under its own peak (smoothed over 50 ms),
            # so a low piano note keeps 30 s and a high one 4; `max_seconds` still caps it.
            ring_end = None
            if layer.get('ring_db') is not None and not loop:
                env = np.sqrt(np.convolve((x.astype(np.float64) ** 2).mean(axis=1), np.ones(int(.05 * info['rate'])) / int(.05 * info['rate']), mode='same'))
                above = np.flatnonzero(env > float(env.max()) * 10 ** (layer['ring_db'] / 20))
                ring_end = int(above[-1]) + int(0.05 * info['rate']) if len(above) else len(x)
            if layer.get('max_seconds') or ring_end is not None:
                n = min(int(layer['max_seconds'] * info['rate']) if layer.get('max_seconds') else len(x), ring_end if ring_end is not None else len(x))
                if len(x) > n:
                    if loop and loop[1] > n:
                        raise ValueError(f'{e["file"].name}: max_seconds would cut the recorded loop')
                    fade = int(0.05 * info['rate'])
                    x = x[:n].copy()
                    x[-fade:] *= np.linspace(1, 0, fade)[:, None]
            match = None
            if loop and (layer.get('loop_repair') or layer.get('loop') == 'found'):
                x, loop, match = steady_loop(x, info['rate'], loop, **layer.get('loop_repair', {}),
                                             found=layer.get('loop') == 'found', f0=440 * 2 ** ((e['named'] - 69) / 12))
            elif loop and len(x) - loop[1] < 8:
                # Interpolation reads a few frames past the loop end: there they repeat the loop's first frames.
                x = np.concatenate([x[:loop[1]], x[loop[0]:loop[0] + 16]])
            body = x[:int(1.0 * info['rate'])]
            # Sustained layers are matched by early RMS; percussive layers by peak.
            level = (float(np.abs(x).max()) * 0.115 if layer.get('level') == 'peak'
                     else float(np.sqrt(np.mean(body ** 2))))
            hashes = [file_hash(f) for f in e['files']]
            loaded[key] = {'x': x, 'rate': info['rate'], 'loop': loop, 'loop_match': match, 'noise_db': noise_db, 'noise_from': noise_from,
                           'trim_ms': round(1000 * start / info['rate'], 1),
                           'clicks_ms': [[round(1000 * a / info['rate'], 1), round(1000 * b / info['rate'], 1), s] for a, b, s in clicks],
                           'rms': level, 'sha256': hashes[0] if not mics else hashlib.sha256(''.join(hashes).encode()).hexdigest(),
                           'mic_files': ([{'file': str(f.relative_to(root)), 'sha256': h, 'gain': mic.get('gain', 1.0),
                                           'pan': mic.get('pan')} for f, h, mic in zip(e['files'], hashes, mics)]
                                         if mics else None)}
        e.update(loaded[key])
        e['take'] = key
        # The pitch follows this layer's own settings and named note, not the first layer that loaded the take: kept
        # apart in the shared cache under its own key (a tuple; the audio's keys are strings).
        rate = loaded[key]['rate']
        how = ('f0', key, e['named'], layer.get('pitch_source'), tuple(layer.get('spectrum_window', (0.2, 1.2))),
               layer.get('fmin', 25.0), layer.get('fmax', 4200.0), layer.get('yin_threshold', 0.12),
               bool(layer.get('pitch_check', True)), split_cents is None)
        if how not in loaded:
            x = loaded[key]['x']
            if layer.get('pitch_source') == 'spectrum':
                # The strongest peak within a semitone of the named fundamental over `spectrum_window` seconds: for
                # plucked strings recorded over a room's rumble, which can pull YIN or the split's tracker off pitch.
                loaded[how] = spectral_pitch(x.mean(axis=1), rate, e['named'], how[4])
            else:
                seg = x[int(0.25 * rate):int(0.85 * rate)].mean(axis=1)
                loaded[how] = (yin_f0(seg, rate, fmin=how[5], fmax=how[6], threshold=how[7])
                               if how[8] and how[9] and len(seg) > 2048 else None)
        e['f0'] = loaded[how]
        e['cents'] = (100 * (e['measured'] - e['named']) if e['measured'] is not None else
                      None if e['f0'] is None else 1200 * math.log2(e['f0'] / (440 * 2 ** ((e['named'] - 69) / 12))))
    checked = [e['cents'] for e in entries if e['cents'] is not None]
    octave_fix = 0
    if checked:
        med = float(np.median(checked))
        octave_fix = int(round(med / 1200)) * 12
        if octave_fix:
            for e in entries:
                e['named'] += octave_fix
                e['cents'] = None if e['cents'] is None else e['cents'] - 100 * octave_fix
    if layer.get('fold_octaves'):
        # The pitch tracker can lock onto the second harmonic or an octave below the note: a reading an octave or two
        # away from the named note, give or take a few cents, is taken as the named note that many cents out.
        for e in entries:
            if e['cents'] is not None and abs(e['cents']) > 600:
                e['cents'] -= 1200 * round(e['cents'] / 1200)
    layer_med = {d: float(np.median([e['rms'] for e in entries if e['dyn'] == d])) for d in layer['dynamics']
                 if any(e['dyn'] == d for e in entries)}
    return entries, octave_fix, layer_med

def _local_levels(entries, width=2):
    """Each note's target level within its dynamic: the median over that note and its `width` nearest recorded
    neighbours on either side, so an uneven take is evened out while the register keeps its own slope."""
    out = {}
    for dyn in {e['dyn'] for e in entries}:
        level = {}
        for e in entries:
            if e['dyn'] == dyn:
                level.setdefault(e['named'], []).append(e['rms'])
        notes = sorted(level)
        for i, n in enumerate(notes):
            out[(n, dyn)] = float(np.median([np.median(level[m]) for m in notes[max(0, i - width):i + width + 1]]))
    return out

def _across_levels(local, layer_med):
    """`match_notes: "across"`: every recorded dynamic of a note at one level.  Local levels keep each dynamic's own
    register slope, and a soft layer recorded quieter in the treble than the loud one then jumps at a velocity split
    there; here the slope is the median, over the dynamics recorded at a note, of each one's local level against its
    own median, so a split changes the tone only and the velocity curve sets loudness."""
    common = {}
    for (n, dyn), v in local.items():
        common.setdefault(n, []).append(v / layer_med[dyn])
    return {(n, dyn): float(np.median(common[n])) * layer_med[dyn] for (n, dyn) in local}

def build(spec, root, output, ffmpeg=None):
    root = Path(root)
    samples, instruments, presets, receipt = [], [], [], {'spec': spec.get('name'), 'files': [], 'layers': []}
    loaded, stored = {}, {}
    for pspec in spec['presets']:
        layer_targets = []
        first_instrument = len(instruments)
        prepared = [_load_layer(layer, root, ffmpeg, loaded, receipt) for layer in pspec['layers']]
        # Level matching: each dynamic layer's median level is kept relative to the loudest layer; notes within a
        # layer are pulled toward the layer median (bounded so noise is not raised much), or with `match_notes:
        # "local"` toward the median of their nearest neighbours, or with "across" every dynamic of a note to one
        # level on a register slope the dynamics share.  A kit (`level_reference: "preset"`) keeps the
        # recorded balance between its pieces instead: one reference for all.
        shared = pspec.get('level_reference') == 'preset'
        common = max(max(med.values()) for _, _, med in prepared) if shared else None
        for layer, (entries, octave_fix, layer_med) in zip(pspec['layers'], prepared):
            ref = common if shared else max(layer_med.values())
            # Optional `layer_levels_db` sets each recorded dynamic's level relative to the loudest one (a soft
            # layer keeps its timbre but stops being 15-25 dB down, and sections in one patch match).
            shape = layer.get('layer_levels_db')
            layer_gain = {d: (ref * 10 ** (shape[d] / 20) / m if shape and d in shape else 1.0) for d, m in layer_med.items()}
            local = _local_levels(entries) if layer.get('match_notes') in ('local', 'across') else None
            if layer.get('match_notes') == 'across':
                local = _across_levels(local, layer_med)
            for e in entries:
                target = local[(e['named'], e['dyn'])] if local else layer_med[e['dyn']]
                pull = target / e['rms'] if layer.get('match_notes', True) else 1.0
                limit = layer.get('match_limit_db', 6)  # how far a take may be pulled; more raises its noise too
                e['gain'] = (float(np.clip(pull, 10 ** (-limit / 20), 10 ** (limit / 20))) * layer_gain[e['dyn']] * layer.get('gain', 1.0)
                             * spec.get('target_rms', 0.08) / ref)
            layer_targets.append({'dir': layer['mics'][0]['dir'] if layer.get('mics') else layer['dir'],
                                  'octave_fix': octave_fix, 'medians': layer_med})
        if shared:
            # If the kit's loudest hit would clip, the whole kit comes down together, never one sample.
            loudest = max(float(np.abs(e['x']).max()) * e['gain'] for entries, _, _ in prepared for e in entries)
            if loudest > 0.95:
                for entries, _, _ in prepared:
                    for e in entries:
                        e['gain'] *= 0.95 / loudest
        contexts = []
        for layer, (entries, octave_fix, layer_med) in zip(pspec['layers'], prepared):
            inst_zones = []
            notes = sorted({e['named'] for e in entries})
            # `keys: "auto"` spans the notes found, after any octave fix, plus `key_margin` (2) semitones each side: for a
            # library whose names may sit an octave off, where a fixed range would drop the corrected notes.
            keys = layer['keys'] if layer['keys'] != 'auto' else [max(0, notes[0] - layer.get('key_margin', 2)),
                                                                     min(127, notes[-1] + layer.get('key_margin', 2))]
            keymap = _zones_for(notes, keys)
            vel_ranges = layer['velocity']
            env = layer.get('envelope', {})
            gens = {54: 0}
            for name, gen in (('attack', 34), ('hold', 35), ('decay', 36), ('release', 38)):
                if name in env:
                    gens[gen] = sf2.timecents(env[name])
            if 'sustain_db' in env:
                gens[37] = int(round(-10 * env['sustain_db']))
            if 'filter_hz' in env:
                gens[8] = int(round(1200 * math.log2(env['filter_hz'] / 8.176)))
            if layer.get('attenuation_db'):
                gens[48] = int(round(10 * layer['attenuation_db']))
            # Takes recorded without vibrato get the synthesizer's vibrato LFO, starting after a delay so short notes
            # stay straight; the mod wheel (CC1) adds depth on top through the default modulator.
            vib = layer.get('vibrato')
            if vib:
                gens[6] = int(round(vib['depth_cents']))
                gens[23] = sf2.timecents(vib.get('delay_seconds', 0.001))
                gens[24] = int(round(1200 * math.log2(vib['rate_hz'] / 8.176)))
            # Recorded velocity layers already carry the dynamics: these replace the synthesizer's default velocity
            # curves (attenuation in cB; filter in cents, 0 turns the velocity darkening off).
            mods = []
            if 'velocity_attenuation_cb' in layer:
                amount = layer['velocity_attenuation_cb']
                mods += (sf2.linear_velocity_attenuation(amount) if layer.get('velocity_curve') == 'linear'
                         else sf2.override(sf2.VELOCITY_TO_ATTENUATION, amount))
            if 'velocity_filter_cents' in layer:
                mods += sf2.override(sf2.VELOCITY_TO_FILTER, layer['velocity_filter_cents'])
            def store(e):
                """Write one source file once (stereo as a linked pair) and return its sample ids."""
                skey = (e['take'], round(e['gain'], 6), e['named'])
                if skey in stored:
                    e['effective_gain_db'] = stored[skey][1]
                    return stored[skey][0]
                x = e['x'] * e['gain']
                peak = float(np.abs(x).max())
                if peak > 0.98:
                    x = x * (0.98 / peak)
                e['effective_gain_db'] = round(20 * math.log10(e['gain'] * min(1.0, 0.98 / max(peak, 1e-12))), 2)
                rng = np.random.default_rng(int(e['sha256'][:8], 16))  # TPDF dither to 16-bit
                q = np.clip(np.round(x * 32767 + rng.random(x.shape) - rng.random(x.shape)), -32768, 32767).astype(np.int16)
                ids = []
                for ch in range(q.shape[1]):
                    ids.append(len(samples))
                    samples.append({'name': f'{e["file"].stem[:15]}{"LR"[ch] if q.shape[1] == 2 else ""}', 'data': q[:, ch],
                                    'rate': e['rate'], 'root': e['named'], 'correction': 0, 'loop': e.get('loop'),
                                    'type': (4 if ch == 0 else 2) if q.shape[1] == 2 else 1})
                if len(ids) == 2:
                    samples[ids[0]]['link'], samples[ids[1]]['link'] = ids[1], ids[0]
                stored[skey] = (ids, e['effective_gain_db'])
                return ids

            order = list(layer['dynamics'])
            by = {}
            for e in entries:
                by.setdefault((e['named'], e['dyn']), []).append(e)
            for note in notes:
                if note not in keymap:
                    receipt['files'].append({'root_key': note, 'skipped': 'root outside layer key range'})
                    continue
                lo_key, hi_key = keymap[note]
                for dyn in order:
                    # A dynamic missing for this note borrows the nearest recorded dynamic of the same note.
                    have = [d for d in order if (note, d) in by]
                    src = dyn if (note, dyn) in by else min(have, key=lambda d: (abs(order.index(d) - order.index(dyn)), -order.index(d)))
                    group = sorted(by[(note, src)], key=lambda e: str(e['rr']))
                    vlo, vhi = vel_ranges[dyn]
                    quieter = _borrowed_cb(layer, src, dyn)
                    for pos, e in enumerate(group):
                        ids = store(e)
                        fine = 0 if e['cents'] is None or abs(e['cents']) > layer.get('max_correction_cents', 45) else -int(round(e['cents']))
                        # Round robins alternate in small blocks of neighbouring velocities, so performed
                        # velocity variation also varies the recording (SF2 has no round-robin opcode).
                        block = layer.get('rr_block', 4)
                        spans = ([(v, min(vhi, v + block - 1)) for v in range(vlo, vhi + 1, block)
                                  if ((v - vlo) // block) % len(group) == pos] if len(group) > 1 else [(vlo, vhi)])
                        for span in spans:
                            for ch, sid in enumerate(ids):
                                z = {43: (lo_key, hi_key), 44: span, 58: e['named']}
                                if fine:
                                    z[52] = fine
                                if quieter:
                                    z[48] = gens.get(48, 0) + quieter
                                if e.get('loop'):
                                    z[54] = 1  # loop continuously; the release envelope ends the note
                                if layer.get('exclusive_class'):
                                    z[57] = int(layer['exclusive_class'])
                                if len(ids) == 2:
                                    z[17] = -500 if ch == 0 else 500
                                inst_zones.append({'gens': z, 'sample': sid})
                        row = {'file': str(e['file'].relative_to(root)), 'sha256': e['sha256'], 'root_key': e['named'],
                               'dynamic': e['dyn'], 'serves_dynamic': dyn, 'round_robin': e['rr'],
                               **({'served_attenuation_db': quieter / 10} if quieter else {}),
                               'keys': [lo_key, hi_key], 'velocities': [vlo, vhi],
                               'f0_hz': None if e['f0'] is None else round(e['f0'], 2),
                               'deviation_cents': None if e['cents'] is None else round(e['cents'], 1),
                               'fine_tune_cents': fine, 'trimmed_ms': e['trim_ms'],
                               'requested_gain_db': round(20 * math.log10(e['gain']), 2),
                               'applied_gain_db': e.get('effective_gain_db'), 'preset': pspec['name']}
                        if e.get('mic_files'):
                            row['microphones'] = e['mic_files']
                        if e.get('loop'):
                            row['loop_seconds'] = [round(f / e['rate'], 3) for f in e['loop']]
                        if e.get('loop_match') is not None:
                            row['loop_match'] = round(e['loop_match'], 3)
                        if e.get('noise_db') is not None:
                            row['denoised_noise_dbfs'] = e['noise_db']
                            row['noise_measured_from'] = e['noise_from']
                        if e.get('clicks_ms'):
                            row['declicked_ms'] = e['clicks_ms']    # [start, end, 3-12 kHz rise in dB] after the onset
                        receipt['files'].append(row)
            contexts.append({'layer': layer, 'entries': entries, 'notes': notes, 'keymap': keymap, 'gens': dict(gens)})
            instrument = {'name': f'{pspec["name"][:16]} {len(instruments) - first_instrument + 1}', 'global': gens,
                          'zones': inst_zones}
            if mods:
                instrument['mods'] = mods
            instruments.append(instrument)
        presets.append({'name': pspec['name'][:19], 'bank': pspec.get('bank', 0), 'program': pspec['program'], 'global': {},
                        'zones': [{'gens': {}, 'instrument': i} for i in range(first_instrument, len(instruments))]})
        receipt['layers'].append({'preset': pspec['name'], 'layers': layer_targets})
        _derived_presets(pspec, contexts, stored, instruments, presets, receipt)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Attenuations are kept in the centibels meant to be heard and written for FluidSynth (sf2.EMU_ATTENUATION).
    seen = set()
    for item in instruments + presets:
        for gens in [item.get('global') or {}] + [z['gens'] for z in item.get('zones', [])]:
            if id(gens) not in seen and gens.get(48):
                gens[48] = min(1440, int(round(gens[48] / sf2.EMU_ATTENUATION)))
            seen.add(id(gens))
    sf2.write(output, spec['name'], samples, instruments, presets, comment=spec.get('comment', ''),
              copyright_notice=spec.get('copyright', ''))
    receipt['output'] = {'path': str(output), 'sha256': file_hash(output), 'bytes': output.stat().st_size,
                         'presets': sf2.inventory(sf2.read(output))}
    return receipt

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    i = sub.add_parser('inspect')
    i.add_argument('bank', type=Path)
    i.add_argument('--output', type=Path)
    b = sub.add_parser('build')
    b.add_argument('spec', type=Path)
    b.add_argument('--root', type=Path, required=True)
    b.add_argument('--output', type=Path, required=True)
    b.add_argument('--receipt', type=Path, required=True)
    b.add_argument('--ffmpeg', type=Path, help='FFmpeg executable, needed for FLAC sources')
    ct = sub.add_parser('cut', help='re-cut the notes a split manifest records, each checked against its hash')
    ct.add_argument('manifest', type=Path)
    ct.add_argument('--root', type=Path, required=True)
    ct.add_argument('--output', type=Path, required=True)
    sp = sub.add_parser('split', help="cut a spec's `split` sources into one WAV per note (manifest: split.json)")
    sp.add_argument('spec', type=Path)
    sp.add_argument('--root', type=Path, required=True)
    sp.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.command == 'inspect':
        # An output never replaces anything, the bank it reads least of all (musiclib.files.fresh).
        if args.output:
            files.fresh(args.output)
        result = inspect(args.bank)
        if args.output:
            save_json(args.output, result)
        print(json.dumps(result['presets'], ensure_ascii=False, indent=1))
        return
    if args.command == 'cut':
        files.fresh(args.output, 'choose a new output folder')
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        print(cut_sources(manifest, args.root, args.output), 'notes cut and verified')
        save_manifest(args.output / 'split.json', manifest)
        return
    if args.command == 'split':
        files.fresh(args.output, 'choose a new output folder')
        manifest = split_sources(json.loads(args.spec.read_text(encoding='utf-8'))['split'], args.root, args.output)
        save_manifest(args.output / 'split.json', manifest)
        print(json.dumps(manifest['groups'], ensure_ascii=False, indent=1))
        return
    if files.occupied(args.output) or files.occupied(args.receipt):
        raise ValueError('Choose new output and receipt paths')
    receipt = build(json.loads(args.spec.read_text(encoding='utf-8')), args.root, args.output, args.ffmpeg)
    save_json(args.receipt, receipt)
    print(json.dumps(receipt['output'], ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
