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
import contextlib
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
import numpy as np
from musiclib import files, sf2, wavfile
from musiclib.model import RESERVED, file_hash, save_json

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
    try:
        return mantissa * 2.0 ** (exponent - 16383 - 63) if exponent else 0.0
    except OverflowError:  # an exponent no double holds (the format's infinity among them): no rate a recording has
        return float('inf')

def read_aiff(path):
    """Uncompressed AIFF or AIFC (big-endian PCM, or 'sowt' little-endian) as float frames, with read_audio's info.

    0.8 step 1.5 (AIFF 1.3; the AIFF-C draft of 1991 for AIFC): the chunk headers are walked by seeking, the samples
    read once and only where they are.  Until COMM and SSND are both found an ID is printable ASCII (a zero-filled file
    fails at once); once both are, bytes that make no chunk are left unread (a writer that left out the pad byte after
    an odd SSND shifts the next header by one, as in one of the Iowa recordings).  A second complete COMM is refused
    wherever it lies; chunks come in any order, the last SSND is used, the FORM's length is not trusted and no FVER is
    asked for.  COMM holds 18 bytes in AIFF, and in AIFC 22 and its compression name (a count and that many
    characters, padded to an even length).  The samples COMM's frames need must lie in SSND, after its offset, and in
    the file (surplus bytes are left), and a recording over MAX_SOURCE_SECONDS is refused, as a FLAC is, before any
    sample is read."""
    path = Path(path)
    name, size = path.name, path.stat().st_size
    with open(path, 'rb') as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] != b'FORM' or head[8:12] not in (b'AIFF', b'AIFC'):
            raise ValueError(f'{name}: not an AIFF file')
        aifc = head[8:12] == b'AIFC'
        pos, comm, ssnd = 12, None, None              # ssnd: where its payload starts, and how many bytes of it the file holds
        while pos + 8 <= size:
            f.seek(pos)
            cid, csize = (lambda h: (h[:4], int.from_bytes(h[4:8], 'big')))(f.read(8))
            printable = all(32 <= b < 127 for b in cid)
            if comm is not None and ssnd is not None and (not printable or pos + 8 + csize > size):
                break                                 # bytes after both that make no chunk: left unread
            if not printable:
                raise ValueError(f'{name}: not an AIFF file (a chunk ID of unprintable bytes at byte {pos})')
            if cid == b'COMM':
                if comm is not None:
                    raise ValueError(f'{name}: two COMM chunks (the second at byte {pos}); which one is meant is not known')
                comm = f.read(min(csize, 280))        # 22 and a name of at most 255 characters, padded
                if len(comm) != csize:
                    raise ValueError(f'{name}: a COMM chunk of {csize} bytes, where AIFF has 18 and AIFC 22 and its compression name')
            elif cid == b'SSND':
                ssnd = (pos + 8, min(csize, size - pos - 8))
            pos += 8 + csize + (csize & 1)
        if comm is None or ssnd is None:
            raise ValueError(f'{name}: AIFF without COMM or SSND')
        # AIFC's compression name: its count, that many characters, and a pad byte where those two make an odd length
        right = (len(comm) > 22 and len(comm) == 23 + comm[22] + (1 - comm[22] % 2)) if aifc else len(comm) == 18
        if not right:
            raise ValueError(f'{name}: a COMM chunk of {len(comm)} bytes, where {"AIFC has 22 and its compression name" if aifc else "AIFF has 18"}')
        channels, frames, bits = int.from_bytes(comm[:2], 'big'), int.from_bytes(comm[2:6], 'big'), int.from_bytes(comm[6:8], 'big')
        rate = _ext80(comm[8:18])
        kind = comm[18:22] if aifc else b'NONE'
        # The rate within the range a WAV's is held to (wavfile.info: 8 to 192 kHz).  The header's number sized working
        # arrays whatever it claimed: a build's ring measure makes one of a twentieth of a second, and a rate of a million
        # million asked for 400 GB (GPT's security audit of 0.5, S06).
        if (kind not in (b'NONE', b'twos', b'sowt') or bits not in (8, 16, 24, 32) or not 1 <= channels <= 8
                or not 8000 <= rate <= 192000):
            raise ValueError(f'{name}: unsupported AIFF ({kind!r}, {bits} bits, {rate:g} Hz)')
        if frames > MAX_SOURCE_SECONDS * rate:
            raise ValueError(f'{name}: longer than {MAX_SOURCE_SECONDS // 60} minutes, more than a sample recording; cut it first')
        width = bits // 8
        start, held = ssnd
        if held < 8:
            raise ValueError(f'{name}: an SSND chunk without its offset and block size')
        f.seek(start)
        offset = int.from_bytes(f.read(4), 'big')
        need = frames * channels * width
        if held - 8 - offset < need:
            raise ValueError(f'{name}: COMM says {frames} frames, and the sound data after its offset holds fewer')
        f.seek(start + 8 + offset)
        raw = f.read(need)
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
    with files.staged(path) as f:  # whole or not at all (musiclib.files)
        f.write(b'RIFF' + len(body).to_bytes(4, 'little') + body)

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
    """`root`/`rel` for a relative path that stays inside `root` (no absolute path, "..", drive or backslash), and on
    which no folder or file below the root is a link or a junction (CWE-59; 0.8 step 1.5: one inside the root was
    followed): a manifest or spec from elsewhere cannot reach other files.  The root itself may be one: each entry
    resolves it once."""
    parts = PurePosixPath(rel).parts if isinstance(rel, str) else ()
    if not parts or rel.startswith('/') or '..' in parts or ':' in rel or '\\' in rel:
        raise ValueError(f'{what} {rel!r}: expected a relative path inside its folder')
    path = Path(root)
    for part in parts:
        path = path / part
        unlinked(path, root, what)
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError(f'{what} {rel!r} leads out of its folder')
    return path


def unlinked(path, root, what):
    """`path`, below `root`, refused where it is a link or a junction, naming it (CWE-59)."""
    if files.linked(path):
        raise ValueError(f'{what}: {Path(path).relative_to(root).as_posix()} is a link or a junction; the build opens none below its root')
    return path

# The characters a label that becomes part of a file's name may hold: POSIX's portable filename character set, which
# leaves out every character a system reads as a folder, a drive or a stream, and no hyphen first (IEEE Std 1003.1,
# Base Definitions 3.282 "Portable Filename Character Set" and 4.8 "File Portability").
LABEL = re.compile(r'[A-Za-z0-9._][A-Za-z0-9._-]{0,63}')

def label(text, what):
    """`text` as a label a note file is named by (a split group's name, a dynamic, an `out` name): one name of
    portable characters, not "." or "..", nor a name Windows keeps for a device.  A label holding a path separator
    or ".." named the note's file outside the output folder, over a file that was there (GPT's security audit of
    0.5, S02)."""
    if (not isinstance(text, str) or not LABEL.fullmatch(text) or text.strip('.') == '' or text.endswith('.')
            or text.split('.')[0].lower() in RESERVED):
        raise ValueError(f'{what} {text!r}: a name of letters, digits, "_", "." and "-" (at most 64, no path)')
    return text

# 0.8 step 1.5 (CWE-1333, Inefficient Regular Expression Complexity: no regular expression from outside runs here).  A
# spec names a layer's files with a `template`; the skill's own recipes keep the regular expressions (`pattern`) they
# were built with, told by the canonical digest of the parsed spec, which soundbank-lock.json records for each locked
# build (`spec_digest`): a copy under another name or with other line endings is still one of them, a copy with one
# value changed is not.
LOCK = Path(__file__).resolve().parents[1] / 'references' / 'soundbank-lock.json'
TEMPLATE_FIELDS = ('note', 'dyn', 'id', 'rr')
NOTE_FIELD = re.compile(r'[A-Ga-g][#b]?(?:-1|[0-9])')  # a note name as note_number reads it, octave -1 to 9


def bundled_digests():
    """The digests of the skill's own recipes, from the lock."""
    lock = files.read_object(LOCK, 'the sound bank lock', needs=(('builds', list, 'the locked builds'),))
    return {b['spec_digest'] for b in lock['builds'] if isinstance(b, dict) and isinstance(b.get('spec_digest'), str)}


def template_parts(text, where):
    """A file-name template as its parts, in order: literal text, and up to four fields, {note}, {dyn}, {id} and {rr},
    each at most once, with literal text between any two (('', field) for a field).  A brace outside a field is
    refused: there is no escape."""
    if not isinstance(text, str) or not text:
        raise ValueError(f'{where}: `template` is the form of the file names, e.g. "p_{{note}}_vl{{dyn}}_rr{{rr}}.wav"')
    parts, literal, i = [], '', 0
    while i < len(text):
        c = text[i]
        if c == '}':
            raise ValueError(f'{where}: template {text!r} has a "}}" outside a field (a brace only encloses one)')
        if c != '{':
            literal += c
            i += 1
            continue
        j = text.find('}', i)
        name = text[i + 1:j] if j > i else None
        if name not in TEMPLATE_FIELDS:
            raise ValueError(f'{where}: template {text!r}: a field is one of {{note}}, {{dyn}}, {{id}} and {{rr}}, in braces')
        if any(f == name for _, f in parts):
            raise ValueError(f'{where}: template {text!r} names {{{name}}} twice')
        if parts and parts[-1][1] and not literal:
            raise ValueError(f'{where}: template {text!r} has two fields with no text between them; nothing would tell where one ends')
        if literal:
            parts.append((literal, None))
            literal = ''
        parts.append(('', name))
        i = j + 1
    if literal:
        parts.append((literal, None))
    return parts


def template_match(parts, name):
    """The fields of file name `name` by a template's parts, or None.  One pass, left to right, no backtracking: a
    literal must stand there exactly; a field runs to the first place the next literal follows, or to the end of the
    name when it is last, and a last literal is matched at the end; what a field took must be one or more of its
    characters (a note name; ASCII letters or digits for {dyn} and {id}; ASCII digits for {rr}, kept as written)."""
    got, pos = {}, 0
    for k, (literal, field) in enumerate(parts):
        if field is None:
            if not name.startswith(literal, pos):
                return None
            pos += len(literal)
            continue
        if k == len(parts) - 1:
            end = len(name)
        elif k + 1 == len(parts) - 1:
            end = len(name) - len(parts[k + 1][0])
        else:
            end = name.find(parts[k + 1][0], pos)
        value = name[pos:end] if end >= pos else ''  # none of the tests below takes an empty value
        if not (NOTE_FIELD.fullmatch(value) if field == 'note' else value.isascii() and (value.isdigit() if field == 'rr' else value.isalnum())):
            return None
        got[field] = value
        pos = end
    return got if pos == len(name) else None


def _as_template(pattern):
    """A regex of the usual form, written as the nearest template, or None: each named group of the four fields as
    the field, an escaped character as itself, and nothing else of a regex left.  Nearest, not the same: a field takes
    any value of its kind, where the group may have taken fewer (`(?P<note>C4|D4)` becomes {note}, which takes E4 too)."""
    if not isinstance(pattern, str):
        return None
    marked = re.sub(r'\(\?P<(note|dyn|id|rr)>[^()]*\)', lambda m: '\0' + m.group(1) + '\0', pattern)
    out, i = '', 0
    while i < len(marked):
        c = marked[i]
        if c == '\\' and i + 1 < len(marked) and not marked[i + 1].isalnum():
            out, i = out + marked[i + 1], i + 2
        elif c in '\\.^$*+?()[]{}|':
            return None
        else:
            out, i = out + c, i + 1
    return out.replace('\0note\0', '{note}').replace('\0dyn\0', '{dyn}').replace('\0id\0', '{id}').replace('\0rr\0', '{rr}')


def step3_fields(layer, where):
    """The layer fields 0.8 step 3 added, checked before any recording is read: a span of [0.5, 5] stopped the build
    with TypeError and [0] with IndexError, a tune of "20" with TypeError (the third outside review of 0.8)."""
    whole = lambda v: isinstance(v, int) and not isinstance(v, bool)
    # a whole number is compared as it is (math.isfinite of a JSON integer of 401 digits raised OverflowError: the
    # fourth review)
    real = lambda v: whole(v) or (isinstance(v, float) and math.isfinite(v))
    for name in ('span', 'loop_points'):
        v = layer.get(name, [0, 1])
        ok = isinstance(v, list) and len(v) == 2 and whole(v[0]) and v[0] >= 0
        if ok and name == 'loop_points' and v[1] is None:
            continue   # a loop to the end of what is kept (an SFZ loop with no loop_end, on a sample with no loop of its own)
        if not (ok and whole(v[1]) and v[0] < v[1]):
            raise ValueError(f'{where}: `{name}` is [the first frame, the frame after the last] in whole numbers, the first below the other'
                             + (' (or null: to the end of what is kept)' if name == 'loop_points' else ''))
    if (layer.get('loop') == 'points') != ('loop_points' in layer):
        raise ValueError(f'{where}: `"loop": "points"` and `loop_points` come together')
    if 'tune_cents' in layer and not (real(layer['tune_cents']) and -100 <= layer['tune_cents'] <= 100):
        raise ValueError(f'{where}: `tune_cents` is a number of cents from -100 to 100 (whole semitones go into `root`)')
    if layer.get('onset_db') is not None and not (real(layer['onset_db']) and layer['onset_db'] < 0):
        raise ValueError(f'{where}: `onset_db` is a level below 0 dB, or null to keep each take from its first frame')
    if layer.get('loop_mode', 'sustain') != 'sustain':
        raise ValueError(f'{where}: `loop_mode` is "sustain" (the loop plays while the key is held), or absent')
    env = layer.get('envelope')
    if isinstance(env, dict) and 'delay' in env and not (real(env['delay']) and 0 <= env['delay'] <= 100):
        raise ValueError(f'{where}: the envelope\'s `delay` is seconds from 0 to 100')


def naming(spec):
    """Each layer's way of naming its files, checked before any recording is read: its template's parts, or None for
    the regular expression of one of the skill's own recipes.  A `pattern` in any other spec, or beside a template,
    is refused, naming the preset and layer, with the nearest template where it has the usual form.  The layer fields
    of step 3 are checked here too (step3_fields)."""
    from musiclib.model import digest
    ours, out = None, []
    whole = lambda v: isinstance(v, int) and not isinstance(v, bool)
    span = lambda v: isinstance(v, list) and len(v) == 2 and all(map(whole, v)) and 0 <= v[0] <= v[1] <= 127
    for p in spec['presets']:
        if not p['layers']:   # a bank of no zone was built and published (GPT Pro's second review of 0.8.0)
            raise ValueError(f'preset {p.get("name")!r}: no layers; a preset plays the takes of its layers')
        for k, layer in enumerate(p['layers']):
            where = f'preset {p.get("name")!r}, layer {k + 1}'
            if not isinstance(layer, dict):
                raise ValueError(f'{where}: a layer is an object')
            step3_fields(layer, where)
            mics = layer.get('mics')
            if mics:   # each microphone's folder, which the build reads (a mic of no dir was a KeyError: the Astra review of the fixes)
                if not isinstance(mics, list) or not all(isinstance(m, dict) and isinstance(m.get('dir'), str) for m in mics):
                    raise ValueError(f'{where}: `mics` lists objects, each with its `dir`, the folder of its takes below the root')
            elif not isinstance(layer.get('dir'), str):   # a KeyError past the command's handler (the review of 0.8.0)
                raise ValueError(f'{where}: no `dir`, the folder of its takes below the root ("." for the root itself)')
            if 'template' in layer:
                if 'pattern' in layer:
                    raise ValueError(f'{where}: a `pattern` beside its `template`; the template alone names the files')
                parts = template_parts(layer['template'], where)
                if 'note' not in [f for _, f in parts] and 'root' not in layer and 'pitches' not in layer:
                    raise ValueError(f'{where}: template {layer["template"]!r} has no {{note}}: give the layer a `root` key, or '
                                     '`pitches` by {id}')
                out.append(parts)
            elif 'pattern' in layer:
                ours = digest(spec) in bundled_digests() if ours is None else ours
                if not ours:
                    shown = _as_template(layer['pattern'])
                    try:
                        template_parts(shown, where) if shown else None   # a hint the grammar refuses (n_{note}{dyn}.wav) is not shown
                    except ValueError:
                        shown = None
                    raise ValueError(f'{where}: names its files with a regular expression (`pattern`), which only the skill\'s own '
                                     'recipes keep (0.8). Name them with a `template` instead: '
                                     + (f'"template": "{shown}" (the nearest one: each field takes any value of its kind, which the regex may have narrowed)' if shown else
                                        '"template": "p_{note}_vl{dyn}_rr{rr}.wav", literal text and the fields {note}, {dyn}, {id} and {rr}'))
                out.append(None)
            else:
                raise ValueError(f'{where}: no `template` naming its files, e.g. "template": "p_{{note}}_vl{{dyn}}.wav"')
            for field, what in (('dynamics', 'the dynamics its takes are recorded at, softest first (["default"] for one)'),
                                ('keys', 'the keys it plays: [low, high], or "auto"'),
                                ('velocity', 'the velocities each dynamic takes, e.g. {"default": [1, 127]}')):
                if field not in layer:   # each read by the build: a KeyError past the command's handler, as `dir` was
                    raise ValueError(f'{where}: no `{field}`, {what}')
            # the ranges its zones are made of, as the build reads them: keys or a velocity range given high first left the
            # preset no key or no velocity that plays, and the bank was published (GPT Pro's second review of 0.8.0)
            dyns = layer['dynamics']
            if not (isinstance(dyns, list) and dyns and all(isinstance(d, str) for d in dyns) and len(set(dyns)) == len(dyns)):
                raise ValueError(f'{where}: `dynamics` is a list of names, each once, softest first (["default"] for one); it is {dyns!r}')
            if layer['keys'] != 'auto' and not span(layer['keys']):
                raise ValueError(f'{where}: `keys` is [low, high] as MIDI numbers, 0 <= low <= high <= 127, or "auto"; it is {layer["keys"]!r}')
            margin = layer.get('key_margin', 2)
            if layer['keys'] == 'auto' and not (whole(margin) and margin >= 0):   # below 0, one note's span ran high first (Astra's fifth round)
                raise ValueError(f'{where}: `key_margin` is a whole number of semitones, 0 or more; it is {margin!r}')
            vel = layer['velocity']
            if not (isinstance(vel, dict) and all(d in vel and span(vel[d]) for d in dyns)):
                raise ValueError(f'{where}: `velocity` gives each dynamic [low, high], 0 <= low <= high <= 127, e.g. '
                                 f'{{"default": [1, 127]}}; it is {vel!r}')
    return out


def _span(note, frames):
    """A manifest note's start, end and fade, checked against its decoded source before anything is sliced or ramped
    (CWE-770; 0.8 step 1.5: a fade longer than its note, a float or a negative start failed late or not at all): whole
    numbers, not booleans, with 0 <= start <= end <= the source's frames and 0 <= fade <= end - start."""
    s, e, f = (note.get(k) for k in ('start', 'end', 'fade'))
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (s, e, f)):
        raise ValueError(f'{note.get("file")!r}: its start, end and fade are whole numbers of samples')
    if not (0 <= s <= e <= frames and 0 <= f <= e - s):
        raise ValueError(f'{note.get("file")!r}: samples {s} to {e} with a fade of {f} do not fit a source of {frames} samples')
    return s, e, f


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
    with files.staged(path) as f:  # whole or not at all; bytes, so the lines end in LF on every system as before
        f.write(('\n'.join(lines) + '\n').encode('utf-8'))

def cut_sources(manifest, src_root, out_root):
    """Cut the notes a `split` manifest records (source, sample span, fade) from the same source files, each checked
    against its recorded SHA-256: an installer reproduces the intake's notes exactly without re-running the note finder,
    whose floating-point decisions could differ by a frame on another platform.  Each note is written under a name of
    its own and takes its file's name only once it is checked; if any note fails, the notes this run cut are removed
    again (they are its own: every one was a new file), so no note that does not match, nor half a set, is left."""
    src_root, out_root = Path(src_root).resolve(), Path(out_root).resolve()  # each once: a link below either is refused (contained)
    by_source, targets = {}, {}
    for n in manifest['notes']:
        contained(src_root, n['source'], 'source')
        path = targets[n['file']] = contained(out_root, n['file'], 'note file')
        if files.occupied(path):
            raise ValueError(f'{n["file"]} exists; cut writes into a new folder')
        by_source.setdefault(n['source'], []).append(n)
    if len(targets) != len(manifest['notes']):
        raise ValueError('Two notes of the manifest write one file')
    made = []
    try:
        for source, notes in by_source.items():
            x, info = read_audio(src_root / source)
            x = np.asarray(x, dtype=np.float32)
            for n in notes:
                path = targets[n['file']]
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = files.stage_name(path, '.wav')
                try:
                    if _cut_note(x, *_span(n, len(x)), info['rate'], temp) != n['sha256']:
                        raise ValueError(f'{n["file"]}: the cut does not reproduce the recorded note (is {source} the '
                                         'recording the manifest was made from?); no note was kept')
                    files.fresh(path, 'cut writes into a new folder')
                    files.replace(temp, path)
                    made.append(path)
                finally:
                    with contextlib.suppress(OSError):
                        os.unlink(temp)
    except BaseException:
        for path in made:
            with contextlib.suppress(OSError):
                os.unlink(path)
        files.prune(out_root)
        raise
    return len(manifest['notes'])

SOFT_CLEAR_DB, SOFT_PARTIALS = 12.0, 4
CLOSE_GUARD_DB = 0.5
CLOSE_NARROW_OVER_DB, CLOSE_NARROW_TO_HISS_DB, CLOSE_NARROW_SHARE = 12.0, -10.0, 0.03   # all ours: close_settled_bands

def _onset(x):
    env = np.abs(np.asarray(x, dtype=np.float64)).max(axis=1)
    return int(np.argmax(env > 0.1 * env.max())) if len(env) and env.max() > 0 else 0

def soft_curve(soft, loud, rate, f0):
    """How a soft blow on a key differs from a loud one, partial by partial: {'hz', 'db', 'slope', 'clear'}, or None
    where the takes are too short to read.

    Once the hammer has left the string, string and soundboard ring as a linear system: how each partial decays does
    not depend on how hard the key was struck.  What the blow's strength changes is how much each partial gets at the
    start, the upper ones more from a harder blow, whose felt is stiffer (Hall and Askenfelt 1988; Askenfelt and
    Jansson 1993).  So both takes' partials are read over their first 0.3 s (twelve periods of a low note, which a
    partial needs to stand apart from its neighbours), before two blows' decays have drifted apart, following the
    loud take's own spacing, since a piano's partials lie wider than whole multiples.  `db` is the soft partial's
    level over the loud one's wherever the soft partial stands SOFT_CLEAR_DB over the noise between partials in its
    own take; a median of three takes out one misread partial, the first and the last keeping their own value.
    `slope` is the fall of those ratios per octave, never a rise: above the last clear partial the soft take shows
    its noise and not its partials, and the trend is all there is to go on.  `clear` counts the partials used."""
    def early(x):
        m = np.asarray(x, dtype=np.float64).mean(axis=1)
        on = _onset(x)
        part = m[on + int(0.03 * rate):on + int((0.03 + max(0.3, 12 / f0)) * rate)]
        if len(part) < 512:
            return None
        w = np.hanning(len(part))
        n = 4 * len(part)
        return np.fft.rfftfreq(n, 1 / rate), 20 * np.log10(np.abs(np.fft.rfft(part * w, n)) / w.sum() * 2 + 1e-12)
    a, b = early(loud), early(soft)
    if a is None or b is None or len(a[0]) != len(b[0]):
        if a is None or b is None:
            return None
        b = (a[0], np.interp(a[0], b[0], b[1]))
    f, loud_db = a
    soft_db = b[1]
    top = min(16000.0, 0.45 * rate)
    rows, last, step = [], 0.0, f0
    while last + step <= top:
        guess = last + step
        # The window widens with frequency, as the partials stray further from whole multiples, and never reaches
        # back to the partial before: on the lowest keys, 29 Hz apart, a window of 0.4 per cent of 8 kHz did, the
        # search found the same peak again and never ended.
        half = min(0.06 * f0 + 0.004 * guess, 0.45 * f0)
        sel = (f > guess - half) & (f < guess + half)
        if not sel.any():
            break
        k = int(np.argmax(loud_db[sel]))
        peak = float(f[sel][k])
        if peak <= last:
            break
        near = (f > peak * 0.995) & (f < peak * 1.005)
        between = ((f > peak - 0.6 * f0) & (f < peak - 0.3 * f0)) | ((f > peak + 0.3 * f0) & (f < peak + 0.6 * f0))
        if not near.any() or not between.any():
            break
        # A peak of noise lies about 9 dB over the noise's median.
        rows.append((peak, float(loud_db[sel][k]), float(soft_db[near].max()), float(np.median(soft_db[between])) + 9.0))
        step = min(max(peak - last if len(rows) > 1 else f0, 0.9 * f0), 1.25 * f0)
        last = peak
    clear = [(hz, s - l) for hz, l, s, noise in rows if s > noise + SOFT_CLEAR_DB]
    while len(clear) > 2 and clear[-1][1] > clear[-2][1] + 6:      # a last partial that jumps up is noise read as one
        clear.pop()
    if len(clear) < 2:
        return {'hz': [], 'db': [], 'slope': 0.0, 'clear': len(clear)}
    hz = np.array([c[0] for c in clear])
    db = np.array([c[1] for c in clear])
    smooth = np.array([db[i] if i in (0, len(db) - 1) else float(np.median(db[i - 1:i + 2])) for i in range(len(db))])
    slope = min(float(np.polyfit(np.log2(hz), smooth, 1)[0]), 0.0)
    return {'hz': [float(v) for v in hz], 'db': [float(v) for v in smooth], 'slope': slope, 'clear': len(clear)}

def soft_from_loud(soft, loud, rate, curve):
    """The loud take with each partial brought to the level `curve` gives it, at the soft take's level: a soft note
    that carries the loud take's noise, lowered with it, in place of its own.  One zero-phase gain, the same for both
    channels and for the whole take, so nothing moves in time; below the first partial read the gain is that
    partial's, above the last it follows the curve's slope.  The level is the soft take's over its first 0.3 s."""
    y = np.asarray(loud, dtype=np.float64)
    pad = int(0.2 * rate)
    n = len(y) + 2 * pad
    f = np.fft.rfftfreq(n, 1 / rate)
    lf = np.log2(np.maximum(f, 1.0))
    hz, db = np.array(curve['hz']), np.array(curve['db'])
    gain = np.interp(lf, np.log2(hz), db)
    above = f > hz[-1]
    gain[above] = db[-1] + curve['slope'] * (lf[above] - np.log2(hz[-1]))
    out = np.fft.irfft(np.fft.rfft(np.pad(y, ((pad, pad), (0, 0))), axis=0) * (10 ** (gain / 20))[:, None], n=n, axis=0)[pad:pad + len(y)]
    def early(z):
        on = _onset(z)
        return float(np.sqrt(np.mean(np.asarray(z, dtype=np.float64)[on:on + int(0.3 * rate)] ** 2)))
    return (out * (early(soft) / max(early(out), 1e-12))).astype(np.float32)

def close_settled_bands(x, rate, from_hz=1000.0, settled_db=6.0, not_before_s=0.06):
    """A take with each half-octave band from `from_hz` up taken out from the moment it has come down to the
    recording's hiss, and what was done: [{'band': [lo, hi], 'closed_s': seconds after the onset} or {'band', 'left'}].

    A struck string's upper partials die first, so a take's bands reach the recording's hiss from the top down, and a
    softly struck one never sounds above a few kHz at all; what those bands hold from then on is hiss, which a held
    pedal adds up over every note that rings.  A band's gain moves once, from all to nothing, and never back, so
    nothing rises and falls with the playing (a gain that follows the signal did: soundbank-building.md, denoise).

    Whether a band is down at the hiss is read against the top band, which holds hiss alone once the blow has passed:
    a publisher's slow fade lowers every band alike, so the level itself keeps falling, and the difference to the top
    band does not.  Over the later part of the take (from half of it to 85 per cent) that difference may not move by
    more than 1.5 dB from its first half to its second, nor span more than 4 dB: then the band is at the hiss there,
    and it is closed from the first moment the difference stays within `settled_db` of that for 0.2 s.  A band that
    does not hold still against the top band holds partials and is left as recorded, as is a take under 2 s.  The top
    band itself closes when it first comes within `settled_db` of its own level between 0.5 and 1.5 s.  The fade of a
    band is half its settling time, between 0.03 and 0.3 s: a band only the blow reaches closes as fast as the blow
    went.  No band closes sooner than `not_before_s` after the onset: a pluck's or a blow's own top lasts
    a few hundredths of a second, less than the 0.1 s the levels are read over, and a band read as settled from
    the first frame would be closed through it.  A take whose peak or level the closing would lower by more than
    CLOSE_GUARD_DB stays as recorded: its bands held more than hiss.  So does every band that would take more
    than CLOSE_NARROW_SHARE of the amplitude of a narrow component heard in the hiss into the take's last part (a
    partial that dies slowly holds as still as hiss does), and a band that would take as much of one heard only
    earlier closes after it ('after_a_partial').  Zero-phase band filters that add up exactly to the take
    above `from_hz`; a filter's skirt reaches a little under it (0.3 of the amplitude at 0.9 of `from_hz`), which
    is why the narrow components are read from an octave under it."""
    y = np.asarray(x, dtype=np.float64)
    pad = int(0.2 * rate)
    n = len(y) + 2 * pad
    f = np.fft.rfftfreq(n, 1 / rate)
    def hp(hz, order=12):
        h = np.zeros(len(f))
        h[1:] = 1 / np.sqrt(1 + (hz / f[1:]) ** (2 * order))
        return h
    edges = [from_hz * 2 ** (k / 2) for k in range(24) if from_hz * 2 ** (k / 2) < 0.4 * rate]
    hop = int(0.02 * rate)
    on = _onset(x)
    frames = (len(y) - on) // hop
    if len(edges) < 2 or frames < int(2.0 / 0.02):
        return np.asarray(x), [{'band': [round(from_hz), round(rate / 2)], 'left': 'the take is under 2 s'}]
    X = np.fft.rfft(np.pad(y, ((pad, pad), (0, 0))), axis=0)
    parts, envs = [], []
    for k, e in enumerate(edges):
        mask = hp(e) - (hp(edges[k + 1]) if k + 1 < len(edges) else 0.0)
        part = np.fft.irfft(X * mask[:, None], n=n, axis=0)[pad:pad + len(y)]
        p = (part ** 2).mean(axis=1)[on:on + frames * hop].reshape(frames, hop).mean(axis=1)
        parts.append(part)
        envs.append(np.convolve(10 * np.log10(np.maximum(p, 1e-20)), np.ones(5) / 5, mode='same'))
    top = envs[-1]
    a, b = frames // 2, int(frames * 0.85)
    hold = int(0.2 / 0.02)
    out, report = y.copy(), []
    # Hiss is broad and a partial is narrow.  Two things passed for hiss that were partials (the review of 0.7's code,
    # F01, and the banks built after it).  A partial that dies slowly, under a decibel a second, holds as still
    # against the top band as hiss does, and it was removed from 0.06 s on.  And where the top band holds partials of
    # its own that fall as the others do (an FM voice), a band read against it is settled from the first frame
    # while its partial still sounds far over the hiss.  So the whole take is also read for narrow components, in
    # frames of about 85 ms averaged over windows of a quarter second.  A bin that stands CLOSE_NARROW_OVER_DB over
    # the floor of the half octave it lies in, and whose power (its lobe less the floor) is within
    # CLOSE_NARROW_TO_HISS_DB of all that half octave's hiss, is a tone heard in that hiss.  The floor is the
    # window's own, the lower of its median bin and its tenth percentile over 0.55, so that a half octave crowded
    # with a bass note's partials still shows its hiss between them: a floor taken from the later part of the take
    # made the earlier hiss of a faded recording stand over it, and its chance peaks pass for tones (the second
    # review, R2).  Every window is read, to the end of the take: read as one average, the later part hid a tone
    # that lasts a quarter second in it (R1).  A band's filter reaches into its neighbours (at a band's upper edge
    # the band above passes 0.7 of the amplitude), so a band is held by every tone it would take more than
    # CLOSE_NARROW_SHARE of, and it closes after the last window that holds one.  Where that is in the take's last
    # 15 per cent the band stays as recorded, the tone with its hiss: a tone left alone where the hiss around it
    # was taken out is heard more than before.
    # Each channel is read on its own, and a tone in either holds the band: with the channels' powers averaged, a
    # tone in one channel lay under the other's noise and was removed from both (the third review, N1).  The frames
    # run to the end of the take, the last one anchored there, and a window ends where its last frame ends: the
    # frames had stopped up to 85 ms short of the end, and a window was taken to end one step early (N2).
    nfft = 1 << int(round(math.log2(0.085 * rate)))
    step = nfft // 2
    span = max(4, int(round(0.25 * rate / step)))
    length = len(y) - on
    starts = list(range(0, length - nfft + 1, step))
    if starts and starts[-1] + nfft < length:
        starts.append(length - nfft)
    holds_until = None                    # per band: the sample, from the onset, at which the last window that holds a tone of it ends
    if len(starts) >= span:
        taper = np.hanning(nfft)[:, None]
        power = np.stack([np.abs(np.fft.rfft(y[on + i:on + i + nfft] * taper, axis=0)) ** 2 for i in starts])   # frame, bin, channel
        bins = np.fft.rfftfreq(nfft, 1 / rate)
        limits = [from_hz / 2, from_hz / 2 ** 0.5] + edges + [rate / 2]
        halves = [sel for sel in (np.flatnonzero((bins >= lo) & (bins < hi) & (bins > 0)) for lo, hi in zip(limits, limits[1:])) if len(sel) >= 8]
        # Each frame is first set against its own level in each half octave (its median bin there), and the frames of
        # a window are averaged after that.  Averaged as they stood, a window that lies over a fade inside the take
        # (a recording's own fade-out at its end) was ruled by its loudest frame or two, whose chance peaks then
        # stood over the window's floor as a tone does: on the Osiris piano seven takes in ten kept their bands
        # over 8 kHz for such a peak in their last quarter second.  It is the second review's R2 within one window.
        # And against no less than the floor a stored sample carries: 16 bits under the take's peak, since a take
        # is stored at full scale at most, with its dither and its rounding (a quarter of a step squared).  The end
        # of a take that fades to nothing holds 'components' 140 to 200 dB under its peak, which are what
        # arithmetic leaves and not sound; set against the frame's own level they were tones, in the last window
        # of the take, and held the band.
        stored = (float(np.abs(y).max()) / 32767.0) ** 2 / 4 * float((taper ** 2).sum())
        level = np.zeros_like(power)
        for sel in halves:
            level[:, sel] = np.maximum(np.median(power[:, sel], axis=1)[:, None], stored)
        power = np.divide(power, level, out=np.zeros_like(power), where=level > 0)
        run = np.concatenate([np.zeros((1,) + power.shape[1:]), np.cumsum(power, axis=0)])
        windows = (run[span:] - run[:-span]) / span                                # window i: frames i to i + span - 1
        # The stored sample's floor in each window's own units: the mean over its frames of that floor over the
        # frame's level.  It is 1 where a take has faded to nothing and next to nothing where it sounds.
        share = np.divide(stored, level, out=np.zeros_like(level), where=level > 0)
        run = np.concatenate([np.zeros((1,) + share.shape[1:]), np.cumsum(share, axis=0)])
        least = (run[span:] - run[:-span]) / span
        ends = np.array([starts[i + span - 1] + nfft for i in range(len(windows))])
        floor, width = np.zeros_like(windows), np.ones(len(bins))
        for sel in halves:
            if True:
                part = windows[:, sel]
                # No lower than the stored sample's floor in the window's units (`least`): where a frame lay far
                # under that floor, the window's own floor would be as far under it again.  Held at 1, the level
                # the frames were set against, it hid the partials of a low note, whose median bin in a crowded
                # half octave is itself partials and whose hiss lies far under it (the final review, FR01).
                floor[:, sel] = np.maximum(np.minimum(np.median(part, axis=1), np.percentile(part, 10, axis=1) / 0.55)[:, None], least[:, sel])
                width[sel] = len(sel)
        edge = np.pad(windows, ((0, 0), (1, 1), (0, 0)), mode='edge')
        over = np.pad(np.where(floor > 0, windows - floor, 0.0), ((0, 0), (2, 2), (0, 0)))
        lobe = over[:, :-4] + over[:, 1:-3] + over[:, 2:-2] + over[:, 3:-1] + over[:, 4:]
        heard = ((floor > 0) & (windows >= floor * 10 ** (CLOSE_NARROW_OVER_DB / 10)) & (windows >= edge[:, :-2])
                 & (windows >= edge[:, 2:]) & (lobe >= floor * width[None, :, None] * 10 ** (CLOSE_NARROW_TO_HISS_DB / 10))).any(axis=2)
        through = lambda edge_hz: 1 / np.sqrt(1 + (edge_hz / np.maximum(bins, 1.0)) ** 24)   # the filters of hp(), order 12
        holds_until = []
        for k in range(len(edges)):
            share = through(edges[k]) - (through(edges[k + 1]) if k + 1 < len(edges) else 0.0)
            rows = np.flatnonzero((heard & (share > CLOSE_NARROW_SHARE)).any(axis=1))
            holds_until.append(int(ends[rows[-1]]) if len(rows) else 0)
    def closing(settle):
        start = on + settle * hop if settle else 0
        fade = int(min(0.3, max(0.03, 0.5 * settle * 0.02)) * rate)
        gain = np.ones(len(y))
        gain[:start] = 0.0
        if settle:
            m = min(fade, len(y) - start)
            gain[start:start + m] = 0.5 - 0.5 * np.cos(np.pi * np.arange(m) / fade)
        return gain
    def first_held(under):
        run = 0
        for i, ok in enumerate(under):
            run = run + 1 if ok else 0
            if run >= hold:
                return i - hold + 1
        return None
    for k in range(len(edges)):
        band = [round(edges[k]), round(edges[k + 1] if k + 1 < len(edges) else rate / 2)]
        if k == len(edges) - 1:
            early = float(np.median(top[int(0.5 / 0.02):int(1.5 / 0.02)]))
            settle = first_held(top[:b] <= early + settled_db)
        else:
            d = envs[k] - top
            window = d[a:b]
            drift = float(np.median(window[:len(window) // 2]) - np.median(window[len(window) // 2:]))
            if abs(drift) > 1.5 or float(np.percentile(window, 95) - np.percentile(window, 5)) > 4.0:
                report.append({'band': band, 'left': 'it does not hold still against the top band: partials'})
                continue
            settle = first_held(d[:b] <= float(np.median(window)) + settled_db)
        if settle is None:
            report.append({'band': band, 'left': 'it never settles before the later part of the take'})
            continue
        settle = max(settle, int(math.ceil(not_before_s / 0.02 - 1e-9)))
        waited = False
        if holds_until and holds_until[k]:
            # A tone the band would take from is heard up to this sample: the band closes after it, or not at all
            # where that reaches the take's last 15 per cent.
            after = -(-holds_until[k] // hop)
            if after >= b:
                report.append({'band': band, 'left': 'a narrow component is heard in it into the last part of the take: a partial'})
                continue
            waited, settle = after > settle, max(settle, after)
        out -= closing(settle)[:, None] * parts[k]
        report.append({'band': band, 'closed_s': round(settle * 0.02, 2), **({'after_a_partial': True} if waited else {})})
    # Hiss holds no part of a take's peak or of its level.  Where taking the bands out lowers either by more than
    # CLOSE_GUARD_DB, a band read as settled held the note after all: a take that begins with a knock or a touch of
    # the string and sounds its note 0.3 s later reads as settled in between.  Such a take stays as recorded.
    rms = lambda v: float(np.sqrt(np.mean(v ** 2))) + 1e-30
    lost = max(20 * math.log10((float(np.abs(y).max()) + 1e-30) / (float(np.abs(out).max()) + 1e-30)), 20 * math.log10(rms(y) / rms(out)))
    if lost > CLOSE_GUARD_DB:
        return np.asarray(x), [{'band': [round(from_hz), round(rate / 2)],
                                'left': f'closing its bands would take {lost:.1f} dB from the take: they hold more than hiss'}]
    return out.astype(np.asarray(x).dtype), report

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
    src_root, out_root = Path(src_root).resolve(), Path(out_root).resolve()  # each once: a link below either is refused (contained)
    manifest = {'groups': [], 'notes': [], 'sources': []}
    for group in split['groups']:
        label(group.get('name'), 'group name')
        opts = {k: group[k] for k in ('quiet_db', 'edge_db', 'min_note', 'partial') if k in group}
        fmin, fmax = group.get('fmin', 25.0), group.get('fmax', 4200.0)
        tolerance = group.get('tolerance_cents', 80)
        candidates = {}
        for entry in group['files']:
            path = contained(src_root, entry['file'], 'source')
            label(entry.get('dyn'), f'{entry["file"]}: dyn')
            if entry.get('out'):
                label(entry['out'], f'{entry["file"]}: out')
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
            # The whole path is checked, as cut_sources checks a manifest's, and a name another note took is refused:
            # the output is new, so a file there is this run's own (two groups of one name, or of names that differ
            # by case on a drive that does not tell them apart), never written over.
            dest = contained(out_root, f'{group["name"]}/{name}', 'note file')
            if files.occupied(dest):
                raise ValueError(f'{group["name"]}/{name}: two notes would take this name')
            digest = _cut_note(pick['x'], pick['start'], pick['end'], fade, pick['rate'], dest)
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
        try:   # a file FFmpeg cannot decode, or not in time, is named (its errors went past the command's handler: the whole review)
            subprocess.run([str(ffmpeg), '-hide_banner', '-nostdin', '-v', 'error', '-y', '-protocol_whitelist', 'file',
                            '-f', 'flac', '-i', str(path), '-t', str(MAX_SOURCE_SECONDS + 1), '-c:a', 'pcm_f32le', tmp],
                           check=True, stdin=subprocess.DEVNULL, timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.CalledProcessError as e:
            raise ValueError(f'{path.name}: FFmpeg could not decode this FLAC (exit code {e.returncode}; its message is above)') from None
        except subprocess.TimeoutExpired:
            raise ValueError(f'{path.name}: FFmpeg did not decode this FLAC within 600 seconds') from None
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
                        ids, _, lift_cb = stored[(e['take'], round(e['gain'], 6), e['named'], bool(layer.get('full_scale')))]
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
                                if quieter or lift_cb:
                                    z[48] = c['gens'].get(48, 0) + quieter + lift_cb
                                if offset:
                                    z[0], z[4] = offset % 32768, offset // 32768
                                if e.get('loop'):
                                    z[54] = 3 if layer.get('loop_mode') == 'sustain' else 1   # as the main preset's zones
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
    manifest = files.read_object(unlinked(Path(root) / 'split.json', root, 'the split manifest'), 'a split manifest', needs=(('notes', list, 'the notes split cut'),))
    return {n['file'].replace('\\', '/'): n['cents'] for n in manifest['notes'] if n.get('cents') is not None}

def _load_layer(layer, root, ffmpeg, loaded, receipt, parts=None):
    """Match, load, trim and measure one layer's takes; returns its entries (octave-checked) and per-dynamic medians.
    `parts`: the layer's template (naming); None for the regular expression of one of the skill's own recipes."""
    rx = re.compile(layer['pattern']) if parts is None else None
    # `pitch_source: "split"`: notes cut by `split` keep the pitch measured over their whole steady part, so a low
    # pedal note that defeats a short YIN excerpt is still tuned.
    split_cents = _split_pitches(root) if layer.get('pitch_source') == 'split' else None
    mics = layer.get('mics')
    # A layer's folders are under the root ("." is the root itself): a spec from elsewhere named recordings anywhere,
    # which the build then put in the bank (GPT's security audit of 0.5, L01).
    under = lambda rel, what: Path(root) if rel == '.' else contained(root, rel, what)
    folder = under(mics[0]['dir'] if mics else layer['dir'], 'layer dir')
    entries = []
    # A folder listed once a build (an SFZ's regions share one), and a template of no field, which names one file,
    # says nothing of the folder's others: Meta Piano's 352 regions in one folder wrote 123,552 of them in its receipt.
    listing = loaded.get(('folder', str(folder)))
    if listing is None:
        listing = loaded[('folder', str(folder))] = audio_files(folder)
    literal = parts is not None and all(f is None for _, f in parts)
    if literal:   # its one file by its name, not each of the folder's matched against it (a region a file: R x F)
        names = loaded.get(('names', str(folder)))
        if names is None:
            names = loaded[('names', str(folder))] = {f.name: f for f in listing}
        listing = [names[parts[0][0]]] if parts[0][0] in names else []
    for f in listing:
        m = rx.fullmatch(f.name) if rx else template_match(parts, f.name)
        if m is None:   # a template of no field matches with no fields: {}
            if not literal:
                receipt['files'].append({'file': str(f.relative_to(root)), 'skipped': f'name does not match {"pattern" if rx else "template"}'})
            continue
        g = m.groupdict() if rx else m
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
        if not 0 <= named <= 127:   # Cb-1 is -1, B9 131: one stopped the bank's writer, the other left the preset no sample (the review of 0.8.0)
            raise ValueError(f'{f.relative_to(root).as_posix()}: its key is MIDI {named}' + (f' (note {g["note"]})' if g.get('note') else '')
                             + ', outside 0-127; rename the take or leave it out')
        if split_cents is not None:
            rel = f.relative_to(root).as_posix()
            if rel not in split_cents:
                raise ValueError(f'{rel}: not in split.json')
            measured = named + split_cents[rel] / 100
        if 'tune_cents' in layer:   # an SFZ region's tune (0.8 step 3.2): played that many cents sharp, as a take that much flat is
            measured = named - layer['tune_cents'] / 100
        # Every microphone recorded the same take in its own folder, under the same file name or one that differs by the
        # microphone's own tag (`name`: [text in the first microphone's file name, text in this one's]).
        # (Named takes, not files: a local `files` hid the module, and the denoise of notes cut by split, which reads
        # their manifest with files.read_json, stopped every such build; found by GPT Pro's fourth review of 0.4.0.)
        def take_of(mic):
            name = f.name.replace(*mic['name']) if mic.get('name') else f.name
            there = under(mic['dir'], 'microphone dir')
            # One name in that folder: a separator, "..", or on Windows a drive ("D:take.wav", which a path joined to
            # it starts from) names another place (the re-review of GPT's security audit, N4).
            if '/' in name or '\\' in name or name in ('.', '..') or (there / name).parent != there or (there / name).name != name:
                raise ValueError(f'{name!r}: a microphone\'s `name` changes a take\'s file name, not its folder')
            return there / name
        takes = [f] + [take_of(mic) for mic in (mics or [])[1:]]
        for take in takes:
            unlinked(take, root, 'a take')
        for other in takes[1:]:
            if not other.is_file():
                raise ValueError(f'{other.relative_to(root)}: no take for this microphone')
        entries.append({'file': f, 'files': takes, 'named': named, 'dyn': dyn, 'rr': g.get('rr') or '1', 'measured': measured})
    if not entries:
        raise ValueError(f'No samples matched {folder.relative_to(root)}')
    # Load, trim, measure pitch and level.
    looped = layer.get('loop') in ('recorded', 'found', 'points')
    dn = layer.get('denoise')
    dc = layer.get('declick')
    # `highpass`: {"ratio", "max_hz"}, a zero-phase high-pass at that fraction of each take's fundamental, at most
    # max_hz, before anything else: a room's rumble under soft plucked notes, which a stationary denoiser cannot follow.
    hpf = layer.get('highpass')
    close = layer.get('close_hiss')
    noise, per_take, profile_from = {}, {}, {}
    if dn and (root / 'split.json').is_file():
        # Notes cut from longer recordings: each take uses its recording's own noise, measured between its notes when
        # it was split (the manifest stores it, rounded, so every build gets the same numbers).  A recording played
        # without pauses borrows the median, band by band, of the recordings of the same layer and dynamic that have
        # one (one session, one setup), or of all the layer's.
        manifest = files.read_object(unlinked(root / 'split.json', root, 'the split manifest'), 'a split manifest',
                                     needs=(('notes', list, 'the notes split cut'), ('sources', list, 'the recordings it cut them from')))
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
        # A take is loaded once per build and shared by the layers that use it alike: its key holds everything that
        # changes what is kept of it (the files and microphones, the onset threshold, the ring and length cut, the
        # level statistic, the loop, the noise profile it is cleaned with, the declick and the high-pass, the named
        # note where the high-pass or the loop's pitch follows it, and the measured pitch where the partials the
        # denoiser keeps follow it), so a layer that trims or measures it otherwise loads its own.
        rel = e['file'].relative_to(root).as_posix()
        cleaned_with = (per_take[rel] if dn and rel in per_take else
                        hashlib.sha256(np.ascontiguousarray(noise[e['dyn']]).tobytes()).hexdigest() if dn and e['dyn'] in noise else None)
        # (onset_db as written: absent apart from -45 written out, as 0.7 kept them apart, and from null, step 3's "keep
        # the take from its first frame")
        key = json.dumps([[str(f) for f in e['files']], mics, layer.get('onset_db', 'unset'), layer.get('max_seconds'), layer.get('ring_db'),
                          layer.get('level'), layer.get('loop'), layer.get('loop_window'), layer.get('loop_repair'), dn, cleaned_with, dc, hpf,
                          e['named'] if looped or hpf else None,
                          e['measured'] if dn and dn.get('keep_partials_below') else None] + ([['close_hiss', close]] if close is not None else [])
                         + ([['span', layer.get('span'), layer.get('loop_points')]] if 'span' in layer or 'loop_points' in layer else []))
        if key not in loaded:
            x, info = mic_mix(e['files'], mics, ffmpeg) if mics else read_audio(e['file'], ffmpeg)
            cut = 0
            if 'span' in layer:   # an SFZ region's offset and end (0.8 step 3.2), in the file's own frames
                cut, end = layer['span'][0], min(layer['span'][1], len(x))
                if not 0 <= cut < end:
                    raise ValueError(f'{e["file"].name}: offset {cut} and end {layer["span"][1]} leave nothing of its {len(x)} frames')
                x = x[cut:end]
            if hpf:
                f0 = 440.0 * 2 ** ((e['named'] - 69) / 12)
                x = highpass(x, info['rate'], min(hpf.get('max_hz', 120.0), hpf.get('ratio', 0.73) * f0))
            closed = None
            if close is not None:           # `{}` asks for it with its defaults
                x, closed = close_settled_bands(x, info['rate'], float(close.get('from_hz', 1000.0)), float(close.get('settled_db', 6.0)),
                                                float(close.get('not_before_s', 0.06)))
            noise_db = noise_from = None
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
            threshold = layer.get('onset_db', -45.0)
            start = onset(x, info['rate'], threshold) if threshold is not None else 0   # None: kept as cut (an SFZ region's offset)
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
                if ls < cut + start:
                    raise ValueError(f'{e["file"].name}: the silence trim reaches into the recorded loop')
                if le > cut + start + len(x):   # an SFZ region's end short of the file's loop (0.8 step 3.2)
                    raise ValueError(f'{e["file"].name}: the end kept, frame {cut + start + len(x)}, cuts into the recorded loop {ls}-{le}')
                loop = (ls - cut - start, le - cut - start)
            elif layer.get('loop') == 'points':   # an SFZ region's loop_start and loop_end, in the file's frames
                ls, le = layer['loop_points']
                le = cut + start + len(x) if le is None else le   # null: to the end of what is kept (ARIA's loop with no loop_end)
                if not cut + start <= ls < le <= cut + start + len(x):
                    raise ValueError(f'{e["file"].name}: loop {ls}-{le} lies outside the {len(x)} frames kept from {cut + start}')
                loop = (ls - cut - start, le - cut - start)
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
                if n < 1:
                    raise ValueError(f'{e["file"].name}: max_seconds {layer["max_seconds"]} keeps no sample at '
                                     f'{info["rate"]} Hz; give it a positive length')
                if len(x) > n:
                    if loop and loop[1] > n:
                        raise ValueError(f'{e["file"].name}: max_seconds would cut the recorded loop')
                    # A cut shorter than the 50 ms fade fades over its whole length: a layer cut to 20 ms stopped on
                    # NumPy's broadcasting (GPT Pro's eighth review of 0.4.0, Y02).  Longer cuts are as before.
                    fade = min(int(0.05 * info['rate']), n)
                    x = x[:n].copy()
                    x[-fade:] *= np.linspace(1, 0, fade)[:, None]
            match = None
            if loop and (layer.get('loop_repair') or layer.get('loop') == 'found'):
                x, loop, match = steady_loop(x, info['rate'], loop, **layer.get('loop_repair', {}),
                                             found=layer.get('loop') == 'found', f0=440 * 2 ** ((e['named'] - 69) / 12))
            elif loop and len(x) - loop[1] < 8:
                # Interpolation reads a few frames past the loop end: there they repeat the loop's first frames.
                x = np.concatenate([x[:loop[1]], x[loop[0]:loop[0] + 16]])
            # A take kept from its first frame (onset_db null: an SFZ's sample) is measured from where it sounds: a second
            # of silence before a tone measured 0, and the preset was refused as silent (the review of 0.8.0).
            lead = 0
            if layer.get('onset_db', -45.0) is None and len(x):
                peaks = np.abs(x).max(axis=1)
                loud = np.flatnonzero(peaks > 1e-4)
                if not len(loud):   # quieter than -80 dBFS throughout: from its first sound (it measured 0, then divided
                    loud = np.flatnonzero(peaks > 0)   # the level match by 0: the Astra review of the fixes for 0.8.0)
                lead = int(loud[0]) if len(loud) else len(x)
            body = x[lead:lead + int(1.0 * info['rate'])]
            # Sustained layers are matched by early RMS; percussive layers by peak (a take silent throughout: 0).
            level = (float(np.abs(x).max()) * 0.115 if layer.get('level') == 'peak'
                     else float(np.sqrt(np.mean(body ** 2))) if len(body) else 0.0)
            hashes = [file_hash(f) for f in e['files']]
            loaded[key] = {'x': x, 'rate': info['rate'], 'loop': loop, 'loop_match': match, 'noise_db': noise_db, 'noise_from': noise_from,
                           'closed_bands': closed,
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
            # the names were checked against 0-127 before this fix, which also moves a take whose pitch was not read (a
            # short one): +12 wrote a root of 139 into the bank, -12 stopped its writer (GPT Pro's second review of 0.8.0)
            for e in entries:
                if not 0 <= e['named'] <= 127:
                    raise ValueError(f"{e['file'].relative_to(root).as_posix()}: its key is MIDI {e['named'] - octave_fix} by its name and "
                                     f"{e['named']} with the octave ({octave_fix:+d}) its layer's measured takes agree on, outside 0-127; "
                                     "rename the take or leave it out")
    if layer.get('fold_octaves'):
        # The pitch tracker can lock onto the second harmonic or an octave below the note: a reading an octave or two
        # away from the named note, give or take a few cents, is taken as the named note that many cents out.
        for e in entries:
            if e['cents'] is not None and abs(e['cents']) > 600:
                e['cents'] -= 1200 * round(e['cents'] / 1200)
    made = layer.get('soft_from')
    if made:
        # `soft_from`: {"<soft dynamic>": "<louder dynamic>"}.  Each take of the soft dynamic is replaced by the take
        # of the louder one on the same key (the same round robin where there is one), filtered to the soft blow's
        # partial levels and brought to the soft take's level (soft_curve, soft_from_loud): a soft layer whose
        # recording stands only a little over the room and the microphones then carries the loud take's noise,
        # lowered, in place of its own.  A key whose soft take shows fewer than SOFT_PARTIALS clear partials borrows
        # the curve of the nearest key that showed them; with none to borrow, or no louder take, it stays as recorded.
        if layer.get('loop'):
            raise ValueError('soft_from is for takes that ring out, not for looped layers')
        if not isinstance(made, dict) or any(k not in layer['dynamics'] or v not in layer['dynamics'] or k == v for k, v in made.items()):
            raise ValueError('soft_from maps a recorded dynamic to another recorded dynamic of the layer')
        if any(v in made for v in made.values()):
            raise ValueError('soft_from: a dynamic that is itself made cannot be the one another is made from; name a recorded one')
        by = {}
        for e in entries:
            by.setdefault((e['dyn'], e['named']), []).append(e)
        todo = sorted((e for e in entries if e['dyn'] in made), key=lambda e: (e['named'], str(e['rr'])))
        pairs, good = {}, {}
        for e in todo:
            louds = by.get((made[e['dyn']], e['named']))
            if not louds:
                e['soft_from'] = {'kept': 'recorded', 'why': 'no take of the louder dynamic on this key'}
                continue
            loud = next((l for l in louds if l['rr'] == e['rr']), louds[0])
            if loud['rate'] != e['rate']:
                raise ValueError(f'{e["file"].name}: its louder take has another sample rate')
            curve = soft_curve(e['x'], loud['x'], e['rate'], 440 * 2 ** ((e['named'] - 69) / 12))
            pairs[id(e)] = (loud, curve)
            if curve and curve['clear'] >= SOFT_PARTIALS:
                good.setdefault((e['dyn'], e['named']), curve)
        for e in todo:
            if id(e) not in pairs:
                continue
            loud, curve = pairs[id(e)]
            borrowed = None
            if not curve or curve['clear'] < SOFT_PARTIALS:
                near = [n for d, n in good if d == e['dyn']]
                if not near:
                    e['soft_from'] = {'kept': 'recorded', 'why': 'too few clear partials, and no key to borrow a curve from'}
                    continue
                borrowed = min(near, key=lambda n: (abs(n - e['named']), n))
                own = curve['clear'] if curve else 0
                curve = good[(e['dyn'], borrowed)]
            else:
                own = curve['clear']
            e['x'] = soft_from_loud(e['x'], loud['x'], e['rate'], curve)
            body = e['x'][:int(1.0 * e['rate'])]
            e['rms'] = (float(np.abs(e['x']).max()) * 0.115 if layer.get('level') == 'peak'
                        else float(np.sqrt(np.mean(body.astype(np.float64) ** 2))))
            e['f0'], e['cents'], e['trim_ms'] = loud['f0'], loud['cents'], loud['trim_ms']
            # Named by what it was made from: two layers that make the same soft take from different loud ones, or
            # with another key's curve, store two samples.
            # The curve itself is part of the name: another layer may borrow that key's curve from another round
            # robin, which is another curve (the review of 0.7's code, F03: both layers stored the first one's take).
            shape = hashlib.sha256(json.dumps([curve['hz'], curve['db'], curve['slope']]).encode()).hexdigest()[:16]
            e['take'] = json.dumps([e['take'], 'soft_from', loud['take'], borrowed, shape])
            for field in ('noise_db', 'noise_from', 'clicks_ms', 'closed_bands'):   # the repairs its samples carry
                e[field] = loud.get(field)
            e['soft_from'] = {'made_from': str(loud['file'].relative_to(root)), 'made_from_sha256': loud['sha256'],
                              'clear_partials': own, **({'curve_of_key': borrowed} if borrowed is not None else {}),
                              'last_clear_hz': round(curve['hz'][-1]), 'gain_db_first_partial': round(curve['db'][0], 1),
                              'gain_db_last_clear': round(curve['db'][-1], 1), 'db_per_octave_above': round(curve['slope'], 1)}
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

# `stored_patch` (0.9.1): numbers added to named takes as they are stored, a correction made once to a recording of one
# of the skill's banks.  They are in a file beside the recipes, which the recipe names with the digest of what it holds,
# so the lock's `spec_digest` covers them; each channel's numbers hold the hash of the words they were made for.
PATCH_FOLDER = LOCK.parent / 'soundbanks'
PATCH_BYTES = 4_000_000


class StoredPatchMismatch(ValueError):
    """A channel as stored is not the words its `stored_patch` was made for (the installer adds what to do about it)."""


def read_stored_patch(field, folder=None):
    """A layer's `stored_patch`, {"file": "<name>.json", "digest": "<64 hex digits>"}, read and checked whole before any
    recording is read.  The file's `takes`: {a take's path under the source root: [for each channel, {"before_sha256":
    the hash of its 16-bit words as stored without the patch, "start": the frame the numbers start at, "add": [whole
    numbers of 16 bits]}]}.  The digest is of the parsed document (model.digest), whatever the file's line endings."""
    from musiclib.model import digest
    if not (isinstance(field, dict) and set(field) == {'file', 'digest'} and isinstance(field['file'], str)
            and field['file'].endswith('.json') and isinstance(field['digest'], str)
            and re.fullmatch(r'[0-9a-f]{64}', field['digest'])):
        raise ValueError('`stored_patch` is {"file": "<name>.json", "digest": "<64 hex digits>"}, a file in the skill\'s '
                         'references/soundbanks')
    label(field['file'], '`stored_patch` file')
    try:
        document = files.read_object(Path(folder or PATCH_FOLDER) / field['file'], 'a stored patch', PATCH_BYTES,
                                     needs=(('takes', dict, 'the numbers to add, by take'),))
    except FileNotFoundError:
        raise ValueError(f'{field["file"]}, which this recipe names, is missing from the skill\'s references/soundbanks: '
                         'its files are incomplete; install the skill again') from None
    if digest(document) != field['digest']:
        raise ValueError(f'{field["file"]} is not the file its recipe names: its digest differs; the skill\'s files are '
                         'damaged or from two versions; install the skill again')
    for take, channels in document['takes'].items():
        if not (isinstance(channels, list) and channels and all(
                isinstance(c, dict) and set(c) == {'before_sha256', 'start', 'add'} and isinstance(c['before_sha256'], str)
                and re.fullmatch(r'[0-9a-f]{64}', c['before_sha256']) and type(c['start']) is int and c['start'] >= 0
                and isinstance(c['add'], list) and c['add'] and all(type(v) is int and -32768 <= v <= 32767 for v in c['add'])
                for c in channels)):
            raise ValueError(f'{field["file"]}: {take}: a take holds a list of channels, each with "before_sha256", a '
                             'whole-number "start" and "add", a list of whole numbers of 16 bits')
    return document['takes']


def _bind_stored_patch(takes, field, entries, root):
    """The takes a patch names, found in their layer once every gain is set.  Each is stored under a key of its own, with
    its exact gain (`store`'s key rounds it, and two gains that round alike store different words): a preset sharing the
    recording without the field keeps it as it was, and one at another gain does not pass on the first's hash.  A take
    the layer lacks is refused, not passed by."""
    here = {e['file'].relative_to(root).as_posix(): e for e in entries}
    absent = sorted(set(takes) - set(here))
    if absent:
        raise ValueError(f'{field["file"]} names {", ".join(absent)}, which this layer does not have')
    for name, channels in takes.items():
        e = here[name]
        if len(channels) != e['x'].shape[1]:
            raise ValueError(f'{field["file"]}: {name} has {e["x"].shape[1]} channels, the patch {len(channels)}')
        e['stored_patch'] = channels
        e['take'] = json.dumps([e['take'], 'stored_patch', field['digest'], float(e['gain'])])


def _patched_words(q, channels, name):
    """A take's 16-bit words as stored, with its `stored_patch` added.  Each channel must be the words its numbers were
    made for, and the sums must stay within 16 bits."""
    out = q.copy()
    for ch, c in enumerate(channels):
        found = hashlib.sha256(q[:, ch].astype('<i2').tobytes()).hexdigest()
        if found != c['before_sha256']:
            raise StoredPatchMismatch(f'{name}: channel {ch + 1} as stored here (SHA-256 {found[:12]}...) is not what its `stored_patch` '
                                      f'was made for ({c["before_sha256"][:12]}...): the recording, the layer\'s levels or the '
                                      'rounding of another NumPy differ')
        a, b = c['start'], c['start'] + len(c['add'])
        if b > len(q):
            raise ValueError(f'{name}: channel {ch + 1}: the `stored_patch` runs to frame {b} of a take of {len(q)}')
        y = q[a:b, ch].astype(np.int32) + np.asarray(c['add'], dtype=np.int32)
        if y.min() < -32768 or y.max() > 32767:
            raise ValueError(f'{name}: channel {ch + 1}: the `stored_patch` takes a word outside 16 bits')
        out[a:b, ch] = y
    return out


def build(spec, root, output, ffmpeg=None, new=False, patch_folder=None):
    root = Path(root).resolve()  # once: a link below it is refused where the build opens it (contained, unlinked)
    named = iter(naming(spec))  # every layer's naming checked before any recording is read (0.8 step 1.5)
    patches = {id(layer): read_stored_patch(layer['stored_patch'], patch_folder)   # so are the corrections
               for p in spec['presets'] for layer in p['layers'] if layer.get('stored_patch') is not None}
    samples, instruments, presets, receipt = [], [], [], {'spec': spec.get('name'), 'files': [], 'layers': []}
    loaded, stored = {}, {}
    for pspec in spec['presets']:
        layer_targets = []
        first_instrument = len(instruments)
        prepared = [_load_layer(layer, root, ffmpeg, loaded, receipt, next(named)) for layer in pspec['layers']]
        # Level matching: each dynamic layer's median level is kept relative to the loudest layer; notes within a
        # layer are pulled toward the layer median (bounded so noise is not raised much), or with `match_notes:
        # "local"` toward the median of their nearest neighbours, or with "across" every dynamic of a note to one
        # level on a register slope the dynamics share.  A kit (`level_reference: "preset"`) keeps the
        # recorded balance between its pieces instead: one reference for all.
        shared = pspec.get('level_reference') == 'preset'
        common = max(max(med.values()) for _, _, med in prepared) if shared else None
        for layer, (entries, octave_fix, layer_med) in zip(pspec['layers'], prepared):
            ref = common if shared else max(layer_med.values())
            if not ref > 0:   # silent takes alone (an SFZ's onset_db null lets them by): nothing to set the others' level by
                raise ValueError(f'preset {pspec.get("name")!r}: its samples are silent (a level of 0); leave the silent ones out')
            # Optional `layer_levels_db` sets each recorded dynamic's level relative to the loudest one (a soft
            # layer keeps its timbre but stops being 15-25 dB down, and sections in one patch match).
            shape = layer.get('layer_levels_db')
            # A take of no sound beside sounding ones is named before anything divides by its level or by its dynamic's
            # median of 0: the match by each take's level ("across" by each dynamic's median too), layer_levels_db by
            # the median of each dynamic it names (each a division by 0: the Astra reviews of the fixes for 0.8.0).
            # Where nothing divides by it (no match, and no shape of a dynamic whose median is 0), it is kept as before.
            zero = {d for d in (shape or {}) if d in layer_med and not layer_med[d] > 0}
            silent = sorted({Path(e['files'][0]).name for e in entries
                             if not e['rms'] > 0 and (layer.get('match_notes', True) or e['dyn'] in zero)})
            if silent:
                raise ValueError(f'preset {pspec.get("name")!r}: {", ".join(silent)} ' + ('is silent (a level of 0); leave it out' if len(silent) == 1
                                                                                          else 'are silent (a level of 0); leave them out'))
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
            if id(layer) in patches:
                _bind_stored_patch(patches[id(layer)], layer['stored_patch'], entries, root)
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
            for name, gen in (('delay', 33), ('attack', 34), ('hold', 35), ('decay', 36), ('release', 38)):
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
                # How the layer stores is part of the key: a take a `full_scale` layer and a plain one share was
                # stored once, as whichever layer came first in the spec (the review of 0.7's code, F08).
                skey = (e['take'], round(e['gain'], 6), e['named'], bool(layer.get('full_scale')))
                if skey in stored:
                    e['effective_gain_db'], e['stored_lift_cb'] = stored[skey][1], stored[skey][2]
                    return stored[skey][0]
                x = e['x'] * e['gain']
                peak = float(np.abs(x).max())
                if peak > 0.98:
                    x = x * (0.98 / peak)
                e['effective_gain_db'] = round(20 * math.log10(e['gain'] * min(1.0, 0.98 / max(peak, 1e-12))), 2)
                # `full_scale`: a sample is 16 bits, and its dither lies a fixed 93 dB under full scale whatever the
                # take's level.  A take stored 20 dB under full scale carries that floor 20 dB nearer its note, and a
                # soft piece raised 30 dB in the mix brings it up with the music.  So the take is stored as loud as
                # 16 bits hold and its zone attenuates it by the same amount: the level heard is the same and the
                # floor lies that much lower.  The lift is a whole number of the file's attenuation steps (0.04 dB
                # heard, sf2.EMU_ATTENUATION), at most 36 dB.
                lift_cb = 0.0
                if layer.get('full_scale') and 0 < peak < 0.98:
                    steps = int(min(36.0, 20 * math.log10(0.98 / peak)) * 10 / sf2.EMU_ATTENUATION)
                    lift_cb = steps * sf2.EMU_ATTENUATION
                    x = x * 10 ** (lift_cb / 200)
                e['stored_lift_cb'] = lift_cb
                rng = np.random.default_rng(int(e['sha256'][:8], 16))  # TPDF dither to 16-bit
                q = np.clip(np.round(x * 32767 + rng.random(x.shape) - rng.random(x.shape)), -32768, 32767).astype(np.int16)
                if e.get('stored_patch'):
                    q = _patched_words(q, e['stored_patch'], e['file'].name)
                ids = []
                for ch in range(q.shape[1]):
                    ids.append(len(samples))
                    samples.append({'name': f'{e["file"].stem[:15]}{"LR"[ch] if q.shape[1] == 2 else ""}', 'data': q[:, ch],
                                    'rate': e['rate'], 'root': e['named'], 'correction': 0, 'loop': e.get('loop'),
                                    'type': (4 if ch == 0 else 2) if q.shape[1] == 2 else 1})
                if len(ids) == 2:
                    samples[ids[0]]['link'], samples[ids[1]]['link'] = ids[1], ids[0]
                stored[skey] = (ids, e['effective_gain_db'], lift_cb)
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
                                if quieter or e.get('stored_lift_cb'):
                                    z[48] = gens.get(48, 0) + quieter + e.get('stored_lift_cb', 0.0)
                                if e.get('loop'):
                                    # loop continuously, the release envelope ending the note; an SFZ loop_sustain
                                    # (loop_mode "sustain") plays on past the loop after the key is let go (SF2 mode 3)
                                    z[54] = 3 if layer.get('loop_mode') == 'sustain' else 1
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
                        if e.get('soft_from'):
                            row['soft_from'] = e['soft_from']
                        if e.get('closed_bands'):
                            row['closed_bands'] = e['closed_bands']
                        if e.get('stored_lift_cb'):
                            row['stored_lift_db'] = round(e['stored_lift_cb'] / 10, 2)   # stored this much louder, attenuated as much in the zone
                        if e.get('stored_patch'):
                            row['stored_patch'] = {'digest': layer['stored_patch']['digest'], 'channels': [
                                {'sample': sid, 'from_frame': c['start'], 'frames': len(c['add']), 'words_changed': sum(map(bool, c['add'])),
                                 'largest_change': max(map(abs, c['add']))} for sid, c in zip(ids, e['stored_patch'])]}
                        receipt['files'].append(row)
            if id(layer) in patches:   # a take outside the layer's keys is loaded and never stored: the bank would lack the correction
                unused = sorted(e['file'].name for e in entries if e.get('stored_patch') and 'effective_gain_db' not in e)
                if unused:
                    raise ValueError(f'{layer["stored_patch"]["file"]} names {", ".join(unused)}, which no key of this layer plays')
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
                field = int(round(gens[48] / sf2.EMU_ATTENUATION))
                if field > 1440:
                    # The file holds 144 dB in this field and FluidSynth plays 0.4 of it: 57.6 dB heard.  Cut to
                    # the limit, a take stored louder (`full_scale`) under a large `attenuation_db` played louder
                    # than the spec asks, by up to 18 dB (the review of 0.7's code, F02).
                    raise ValueError(f'{item.get("name", "a zone")}: an attenuation of {gens[48] / 10:.1f} dB cannot be written '
                                     '(the file holds 57.6 dB as heard). Lower attenuation_db or the velocity attenuation, '
                                     'or build the layer without full_scale.')
                gens[48] = field
            seen.add(id(gens))
    sf2.write(output, spec['name'], samples, instruments, presets, comment=spec.get('comment', ''),
              copyright_notice=spec.get('copyright', ''), new=new)
    receipt['output'] = {'path': str(output), 'sha256': file_hash(output), 'bytes': output.stat().st_size,
                         'presets': sf2.inventory(sf2.read(output))}
    return receipt

def latin1(text):
    """Text as a SoundFont's INFO fields hold it, Latin-1: a character beyond it as its escape (U+9304 as \\u9304), so
    nothing is lost (they became ? and the printout said the bank kept the licence: the review of 0.8.0)."""
    return text.encode('latin-1', 'backslashreplace').decode('latin-1')


def preset_name(name):
    """A preset's name as the folder and sfz commands take it: what a SoundFont's preset header holds, 19 Latin-1
    characters (a longer or other one was cut or turned into ? without a word)."""
    if not isinstance(name, str) or not name.strip() or len(name) > 19 or latin1(name) != name:
        raise ValueError(f'--name {name!r}: a SoundFont preset name holds at most 19 Latin-1 characters (letters, digits, spaces), e.g. "My Piano"')
    return name


def licence_lines(license, receipt):
    """The printout's line for the licence: as kept in the receipt and the bank, and how the bank holds it."""
    if latin1(license) == license:
        return f'Licence, kept in the bank and in {receipt}: {license}'
    return (f'Licence, kept in {receipt} as given: {license}; the bank\'s copyright field holds Latin-1 text, so it keeps it '
            f'as {latin1(license)}')


def folder_spec(folder, template, name, program, license, dynamics=None, keys='auto', loop=None, bank=0):
    """The spec `soundbank.py folder` builds (0.8 step 3.1): one preset of one layer over the user's folder, its files
    named by `template`, each take's pitch read from its {note} and checked by the builder, the takes trimmed and their
    levels matched as any spec's are, the velocity range shared evenly by the dynamics, loudest last (MIDI 1.0 gives
    velocity no curve, so even shares are a start a spec of one's own then shapes).  With more than one {dyn} value
    in the folder `dynamics` must name them all, softest first: their names do not say their order."""
    parts = template_parts(template, 'the template')
    fields = {f for _, f in parts if f}
    if 'note' not in fields:
        raise ValueError(f'--template {template!r}: a take\'s pitch comes from {{note}} in its name here; takes named by position '
                         '({id}) or one take for every key need a spec of their own (soundbank-building.md: pitches, root)')
    found = sorted({m.get('dyn', 'default') for f in audio_files(folder) if (m := template_match(parts, f.name)) is not None})
    if not found:
        raise ValueError(f'No file in {folder} is named as {template!r}')
    if dynamics is None:
        if len(found) > 1:
            raise ValueError(f'The folder holds the dynamics {", ".join(found)}, and their names do not say which is softer: give '
                             'them all, softest first, as --dynamics <softest>,...,<loudest>')
        dynamics = found
    elif sorted(dynamics) != found or len(set(dynamics)) != len(dynamics):
        raise ValueError(f'--dynamics {",".join(dynamics)}: the folder holds {", ".join(found)}; name each once, softest first')
    n = len(dynamics)
    if n > 127:   # 127 velocities to share: 128 dynamics gave one an empty range
        raise ValueError(f'{n} dynamics: MIDI has 127 velocities to share among them')
    edges = [round(127 * k / n) for k in range(n + 1)]
    layer = {'dir': '.', 'template': template, 'dynamics': list(dynamics),
             'velocity': {d: [edges[k] + 1, edges[k + 1]] for k, d in enumerate(dynamics)}, 'keys': keys, **({'loop': loop} if loop else {})}
    return {'name': name, 'comment': latin1(f'Built by soundbank.py folder from the user\'s own samples ({folder.name})'), 'copyright': latin1(license),
            'presets': [{'name': name, 'program': program, **({'bank': bank} if bank else {}), 'layers': [layer]}]}


def sfz_spec(sfz_path, root, name, program, license):
    """The spec `soundbank.py sfz` builds (0.8 step 3.2) and what it could not carry: one preset, one layer a region,
    its sample by the path below `root` the SFZ names (sfz.read: through no link), its root key (the pitch centre less
    the transpose and the whole semitones of the tune, the rest as fine tune), keys and velocities (each crossfade a
    split at its middle), volume as a gain, offset and end as the span kept, the loop (each point the SFZ's, else the
    file's own), the amplitude envelope, and group and off_by as an exclusive class (SF2's is mutual: a group cut by
    another cuts it too).  The levels are the SFZ's (none matched, one reference for the preset) and the pitch is the
    SFZ's (none checked); nothing is trimmed but by the offset.  Each value is read as SFZ writes numbers and held to
    the range its page of the SFZ documentation gives (the third outside review: a volume of 100000 overflowed)."""
    from collections import Counter
    from musiclib import sfz
    parsed = sfz.read(sfz_path, root)   # the root as given: resolved there, once (one resolved here hid a link: the whole review)
    root = Path(root).resolve()
    file = Path(sfz_path).name

    def num(r, op, default, where, cast, lo, hi):
        value = str(r.get(op, default)).strip()
        if not re.fullmatch(r'[+-]?\d+' if cast is int else r'[+-]?(\d+\.?\d*|\.\d+)', value):
            raise ValueError(f'{where}: {op}={r.get(op)!r} is no {"whole " if cast is int else ""}number')
        if not lo <= cast(value) <= hi:
            raise ValueError(f'{where}: {op}={r.get(op)!r} is outside {lo:g} to {hi:g}')
        return cast(value)
    FRAMES = 2 ** 32 - 1   # offset, end and the loop points: the documentation's 0 to 4294967296 sample units
    # group and off_by are numbers (0, the default, is no group and no off_by); a region of no group that another cuts
    # gets a group of its own, so the other regions of group 0 do not cut each other in SF2's mutual classes.
    parent, groups, silent = {}, [], set()

    def find(g):   # iterative (a chain of 1,100 groups overflowed the recursion), each walk made one step for the next
        top = g
        while parent[top] != top:
            top = parent[top]
        while parent[g] != top:
            parent[g], g = top, parent[g]
        return top
    offs = []
    for k, r in enumerate(parsed['regions']):
        where = f'{file}, region {k + 1}'
        if 'end' in r and num(r, 'end', 0, where, int, -1, FRAMES) == -1:
            silent.add(k)   # end=-1: a region that does not play (SFZ uses one to cut others)
            groups.append(None)
            continue
        g = num(r, 'group', 0, where, int, -2 ** 31, 2 ** 31 - 1)
        off = num(r, 'off_by', 0, where, int, -2 ** 31, 2 ** 31 - 1)
        groups.append(('region', k) if off and not g else g)
        offs.append((k, off))
    # A class only between groups a playing region belongs to: an off_by naming a group no region plays in cuts nothing
    # in SFZ, but made a class of its own region, whose notes then cut each other (a chord of one region lost its notes:
    # the review of 0.8.0); a group whose only regions are silent (end=-1) is said in the notes below.
    playing = {g for g in groups if g is not None and g != 0}
    for k, off in offs:
        if off and off in playing:
            for x in (groups[k], off):
                parent.setdefault(x, x)
            a, b = find(groups[k]), find(off)
            if a != b:
                parent[a] = b
    classes = {r_: n + 1 for n, r_ in enumerate(sorted({find(x) for x in parent}, key=str))}
    if len(classes) > 127:
        raise ValueError(f'{file}: {len(classes)} groups cut by others; an SF2 instrument holds 127 exclusive classes')

    def split(low, high, r, kind, read, where):
        """A range less the halves of its crossfades: silent up to xfin_lo, full from xfin_hi; full up to xfout_lo,
        silent from xfout_hi (the documentation's pages).  Where both ends are equal the next value takes the side."""
        for edge, lo_d, hi_d in (('in', '0', '0'), ('out', '127', '127')):
            ends = f'xf{edge}_lo{kind}', f'xf{edge}_hi{kind}'
            if ends[0] in r or ends[1] in r:
                a, b = read(r, ends[0], lo_d), read(r, ends[1], hi_d)
                if b < a:
                    raise ValueError(f'{where}: {ends[1]} below {ends[0]}')
                low, high = (max(low, (a + b) // 2 + 1), high) if edge == 'in' else (low, min(high, (a + b) // 2))
        return low, high
    layers, notes, splits = [], [], Counter()
    for k, r in enumerate(parsed['regions']):
        if k in silent:
            continue
        where = f'{file}, region {k + 1}'
        sample = r['sample']
        rel = sample.relative_to(root)
        if '{' in rel.name or '}' in rel.name:
            raise ValueError(f'{where}: a sample whose name holds a brace is not taken ({rel.name})')
        key = lambda op, d: sfz.key(str(r.get(op, d)), where)
        lo, hi, centre = key('lokey', '0'), key('hikey', '127'), key('pitch_keycenter', '60')
        vel = lambda r_, op, d: num(r_, op, d, where, int, 0, 127)
        lovel, hivel = max(1, vel(r, 'lovel', 1)), vel(r, 'hivel', 127)   # velocity 0 is no note-on
        # A crossfade (xfin_ rising from silence, xfout_ falling to it) becomes a split at its middle: SF2 has none, and
        # layers left overlapping both sound there at full level (Meta Piano's four velocity groups overlapped by 16).
        was = (lo, hi, lovel, hivel)
        lo, hi = split(lo, hi, r, 'key', lambda r_, op, d: sfz.key(str(r_.get(op, d)), where), where)
        lovel, hivel = split(lovel, hivel, r, 'vel', vel, where)
        if not (lo <= hi and lovel <= hivel):
            raise ValueError(f'{where}: keys {lo}-{hi} and velocities {lovel}-{hivel} are no ranges' + (' once its crossfades are splits' if (lo, hi, lovel, hivel) != was else ''))
        for kind, before, after in (('keys', was[:2], (lo, hi)), ('velocities', was[2:], (lovel, hivel))):
            if before != after:
                splits[(kind, *before, *after)] += 1
        shift = 100 * num(r, 'transpose', 0, where, int, -127, 127) + num(r, 'tune', 0, where, float, -9600, 9600)
        whole = round(shift / 100)
        if not 0 <= centre - whole <= 127:
            raise ValueError(f'{where}: pitch_keycenter {centre} with transpose and tune lands outside the keys')
        layer = {'dir': rel.parent.as_posix() or '.', 'template': rel.name, 'root': centre - whole, 'keys': [lo, hi],
                 'dynamics': ['default'], 'velocity': {'default': [lovel, hivel]}, 'pitch_check': False, 'match_notes': False,
                 'onset_db': None, 'max_correction_cents': 50}
        if shift - 100 * whole:
            layer['tune_cents'] = shift - 100 * whole
        if 'volume' in r:   # the documentation's -144.6 to 6, and up to the +24 some players take
            layer['gain'] = 10 ** (num(r, 'volume', 0, where, float, -144.6, 24) / 20)
        if 'offset' in r or 'end' in r:
            start, end = num(r, 'offset', 0, where, int, 0, FRAMES), num(r, 'end', FRAMES - 1, where, int, -1, FRAMES)
            if not start <= end:
                raise ValueError(f'{where}: offset {start} and end {end} are no span')
            layer['span'] = [start, end + 1]   # SFZ's end is the last frame played
        mode = r.get('loop_mode', '')
        if mode not in ('', 'no_loop', 'one_shot', 'loop_continuous', 'loop_sustain'):
            raise ValueError(f'{where}: loop_mode={mode!r} is none of no_loop, one_shot, loop_continuous, loop_sustain')
        held = (wavfile.info(sample).get('loops') or [None])[0] if sample.suffix.lower() == '.wav' and sample.is_file() else None
        points = [num(r, 'loop_start', 0, where, int, 0, FRAMES) if 'loop_start' in r else None,
                  num(r, 'loop_end', 0, where, int, 0, FRAMES) + 1 if 'loop_end' in r else None]
        # Without loop_mode a sample plays as its file says: looped on its own loop where it holds one, else not; each
        # loop point the SFZ gives replaces the file's (the loop_start and loop_end pages).
        if mode in ('loop_continuous', 'loop_sustain') or (not mode and held):
            if points == [None, None] and held:
                layer['loop'] = 'recorded'   # the file's own loop (its smpl chunk), moved with the offset
            else:
                points = [p if p is not None else (held[n] if held else (0 if n == 0 else None)) for n, p in enumerate(points)]
                if points[1] is not None and not points[0] < points[1]:   # null: to the sample's end, as ARIA has it
                    raise ValueError(f'{where}: loop_start {points[0]} is not before loop_end {points[1] - 1}')
                layer.update(loop='points', loop_points=points)
            if mode == 'loop_sustain':
                layer['loop_mode'] = 'sustain'
        elif not mode and points != [None, None]:
            notes.append(f'{where}: loop_start or loop_end with no loop_mode, and no loop in {rel.name}: played unlooped, as SFZ has it')
        env = {n: num(r, f'ampeg_{n}', 0, where, float, 0, 100) for n in ('delay', 'attack', 'hold', 'decay', 'release') if f'ampeg_{n}' in r}
        if 'ampeg_sustain' in r:   # a percentage of the level, as its level in dB (-144, SF2's least, for 0)
            s = num(r, 'ampeg_sustain', 100, where, float, 0, 100)
            env['sustain_db'] = -144.0 if s <= 0 else max(-144.0, 20 * math.log10(s / 100))
        if env:
            layer['envelope'] = env
        if groups[k] in parent:
            layer['exclusive_class'] = classes[find(groups[k])]
        if mode == 'one_shot':
            notes.append(f'{where}: one_shot plays as the note is held (SF2 has no one-shot mode)')
        layers.append(layer)
    if not layers:
        raise ValueError(f'{file} holds no region that plays')
    for (kind, a, b, c, d), n in sorted(splits.items()):
        notes.append(f'{n} region{"s" * (n > 1)} of {kind} {a}-{b} play {kind} {c}-{d}: each crossfade is a split at its middle (SF2 has no crossfade)')
    if silent:
        notes.append(f'{len(silent)} region{"s" * (len(silent) > 1)} with end=-1, which do not play, left out (one that cuts others by group and off_by no longer does)')
    spec = {'name': name, 'comment': latin1(f'Built by soundbank.py sfz from {file}'), 'copyright': latin1(license),
            'presets': [{'name': name, 'program': program, 'level_reference': 'preset', 'layers': layers}]}
    return spec, {'not_used': parsed['not_used'], 'approximated': notes}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    sz = sub.add_parser('sfz', help='build a bank from an SFZ instrument (a documented subset; what it does not use is listed in the receipt)')
    sz.add_argument('sfz', type=Path, help='the .sfz file')
    sz.add_argument('--root', type=Path, help='the folder the .sfz file, its includes and its samples lie in or below (default: the .sfz file\'s folder)')
    sz.add_argument('--name', required=True, help="the bank's and the preset's name")
    sz.add_argument('--program', type=int, required=True, help='the General MIDI program the preset takes, 0-127')
    sz.add_argument('--license', required=True, help="the instrument's licence, as you state it: written into the bank and its receipt")
    sz.add_argument('--output', type=Path, required=True, help='the new bank (.sf2)')
    sz.add_argument('--receipt', type=Path, required=True, help='the new receipt: every file, every decision, what the SFZ held that is not used')
    sz.add_argument('--ffmpeg', type=Path, help='FFmpeg executable, needed for FLAC samples')
    fo = sub.add_parser('folder', help="build a bank from a folder of one's own samples in one step: one preset, named by a template")
    fo.add_argument('folder', type=Path, help='the folder of samples (WAV, AIFF; FLAC through --ffmpeg)')
    fo.add_argument('--template', required=True, help='the form of their names, e.g. "piano_{note}_{dyn}.wav" ({note} needed; {dyn} and {rr} as they come)')
    fo.add_argument('--name', required=True, help="the bank's and the preset's name")
    fo.add_argument('--program', type=int, required=True, help='the General MIDI program the preset takes, 0-127 (0 is a piano)')
    fo.add_argument('--license', required=True, help="the samples' licence, as you state it: written into the bank and its receipt")
    fo.add_argument('--dynamics', help='with more than one {dyn} value: all of them, softest first, comma-separated, e.g. p,mf,f')
    fo.add_argument('--keys', default='auto', help='the playable keys LOW-HIGH as MIDI numbers, or auto (the notes found and 2 keys each side)')
    fo.add_argument('--loop', choices=('recorded', 'found'), help="hold notes on each take's own loop (recorded) or on one the builder finds")
    fo.add_argument('--output', type=Path, required=True, help='the new bank (.sf2)')
    fo.add_argument('--receipt', type=Path, required=True, help='the new receipt: every file, every decision, the spec written and the licence')
    fo.add_argument('--ffmpeg', type=Path, help='FFmpeg executable, needed for FLAC samples')
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
    if args.command == 'sfz':
        if files.occupied(args.output) or files.occupied(args.receipt):
            raise ValueError('Choose new output and receipt paths')
        if os.path.normcase(str(args.output.resolve())) == os.path.normcase(str(args.receipt.resolve())):
            raise ValueError('--output and --receipt name one file: the receipt would replace the bank; give each its own')
        if not args.sfz.is_file():
            raise ValueError(f'{args.sfz} is no SFZ file')
        if not 0 <= args.program <= 127:
            raise ValueError(f'--program {args.program}: a General MIDI program is 0-127')
        if not args.license.strip():
            raise ValueError("--license: state the instrument's licence (as its author gives it)")
        root = args.root or args.sfz.parent   # as given: sfz.read resolves it once, after it has looked for links below it
        spec, left = sfz_spec(args.sfz, root, preset_name(args.name), args.program, args.license)
        receipt = build(spec, root, args.output, args.ffmpeg, new=True)
        receipt.update(license=args.license, sfz_spec=spec, sfz_not_used=left['not_used'], sfz_approximated=left['approximated'])
        save_json(args.receipt, receipt, new=True)
        unused = {**left['not_used']['headers'], **left['not_used']['opcodes']}
        print(files.joined([f'Built {args.output}: preset {args.name!r} at program {args.program}, {len(spec["presets"][0]["layers"])} regions.',
                            ('Not used (the receipt lists them): ' + ', '.join(f'{k} ({n})' for k, n in sorted(unused.items()))) if unused else 'Every header and opcode was used.',
                            *left['approximated'],
                            licence_lines(args.license, args.receipt)]))
        return
    if args.command == 'folder':
        if files.occupied(args.output) or files.occupied(args.receipt):
            raise ValueError('Choose new output and receipt paths')
        if os.path.normcase(str(args.output.resolve())) == os.path.normcase(str(args.receipt.resolve())):
            raise ValueError('--output and --receipt name one file: the receipt would replace the bank; give each its own')
        if not args.folder.is_dir():
            raise ValueError(f'{args.folder} is not a folder of samples')
        if not 0 <= args.program <= 127:
            raise ValueError(f'--program {args.program}: a General MIDI program is 0-127')
        if not args.license.strip():
            raise ValueError("--license: state the samples' licence (your own recordings, CC0, a library's terms)")
        keys = args.keys
        if keys != 'auto':
            m = re.fullmatch(r'(\d{1,3})-(\d{1,3})', keys)
            if not m or not int(m[1]) <= int(m[2]) <= 127:
                raise ValueError(f'--keys {keys!r}: LOW-HIGH as MIDI numbers 0-127, low first (60-72), or auto')
            keys = [int(m[1]), int(m[2])]
        dynamics = [d.strip() for d in args.dynamics.split(',') if d.strip()] if args.dynamics else None
        folder = args.folder.resolve()
        spec = folder_spec(folder, args.template, preset_name(args.name), args.program, args.license, dynamics, keys, args.loop)
        receipt = build(spec, folder, args.output, args.ffmpeg, new=True)
        receipt.update(license=args.license, folder_spec=spec)   # the licence as stated, and the spec to build on
        save_json(args.receipt, receipt, new=True)
        from musiclib.instruments import key_ranges, measured, note
        bank = sf2.read(args.output)
        held, ranges = measured(bank, bank['presets'][0])
        used = [r for r in receipt['files'] if 'skipped' not in r and 'file' in r]
        skipped = [r for r in receipt['files'] if 'skipped' in r and 'file' in r]
        print(files.joined([f'Built {args.output}: preset {args.name!r} at program {args.program}, from {len({r["file"] for r in used})} takes'
                            + (f' ({len(skipped)} files left out; the receipt says why)' if skipped else '') + '.',
                            'Keys with a sample: ' + ', '.join(note(a) if a == b else f'{note(a)}-{note(b)}' for a, b in key_ranges(held)) + '.',
                            'Velocity layers: ' + ', '.join(f'{d} {v[0]}-{v[1]}' for d, v in spec['presets'][0]['layers'][0]['velocity'].items())
                            + f' ({len(ranges)} velocity ranges in the bank, round robins counted).',
                            licence_lines(args.license, args.receipt),
                            'To play it: studio.py add-soundfont --config <config.json> --name <a name> --path <the bank> --license <its licence> '
                            '--source <where the samples come from> --version <a version> --output <a new config.json>']))
        return
    if args.command == 'inspect':
        # An output never replaces anything, the bank it reads least of all (musiclib.files.fresh).
        if args.output:
            files.fresh(args.output)
        result = inspect(args.bank)
        if args.output:
            save_json(args.output, result, new=True)
        print(json.dumps(result['presets'], ensure_ascii=True, indent=1))
        return
    if args.command == 'cut':
        # The notes and their manifest are made in a private folder that becomes the output only when all of them
        # are: a failure at any point, the manifest's write included, leaves no output folder.
        files.fresh(args.output, 'choose a new output folder')
        manifest = files.read_object(args.manifest, 'a cut manifest', needs=(('notes', list, 'the notes split cut, each with its source and span'),))
        staging = files.staging_folder(args.output)
        try:
            count = cut_sources(manifest, args.root, staging)
            save_manifest(staging / 'split.json', manifest)
            files.replace(staging, args.output)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        print(count, 'notes cut and verified')
        return
    if args.command == 'split':
        # As cut: made in a private folder that becomes the output only when every note and the manifest are written.
        files.fresh(args.output, 'choose a new output folder')
        spec = files.read_object(args.spec, 'a split spec', needs=(('split', dict, 'the recordings to split, as {"groups": [...]}'),))
        if not isinstance(spec['split'].get('groups'), list):
            raise ValueError(f'{args.spec}: a split spec needs "split": {{"groups": [...]}}, the groups of recordings to split')
        staging = files.staging_folder(args.output)
        try:
            manifest = split_sources(spec['split'], args.root, staging)
            save_manifest(staging / 'split.json', manifest)
            files.replace(staging, args.output)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        print(json.dumps(manifest['groups'], ensure_ascii=True, indent=1))
        return
    if files.occupied(args.output) or files.occupied(args.receipt):
        raise ValueError('Choose new output and receipt paths')
    if os.path.normcase(str(args.output.resolve())) == os.path.normcase(str(args.receipt.resolve())):
        raise ValueError('--output and --receipt name one file: the receipt would replace the bank; give each its own')
    # The bank and its receipt are published only where nothing has taken their names since they were found free:
    # a build takes minutes (GPT Pro's fourth review of 0.4.0).
    spec = files.read_object(args.spec, 'a bank spec', needs=(('name', str, "the bank's name"), ('presets', list, 'the presets the bank holds')))
    # Each preset's own fields, as build reads them (a spec without them stopped it with a traceback; found by GPT Pro's
    # sixth review of 0.4.0).  A layer's own fields are read as each layer is loaded, unchecked there (a known limit).
    for k, p in enumerate(spec['presets']):
        if not (isinstance(p, dict) and isinstance(p.get('name'), str) and isinstance(p.get('layers'), list)
                and isinstance(p.get('program'), int) and not isinstance(p.get('program'), bool) and 0 <= p['program'] <= 127):
            raise ValueError(f'{args.spec}: presets[{k}] is an object with a text "name", a "program" 0-127 and a list of "layers"')
    receipt = build(spec, args.root, args.output, args.ffmpeg, new=True)
    # Two names for one file that the paths do not show (a case-insensitive volume, a link not yet resolvable): the
    # receipt's path now holds the bank just built, which stays.
    if files.occupied(args.receipt):
        raise ValueError(f'--receipt {args.receipt} now names the bank just built (another name for --output); the bank is kept, '
                         'its receipt is not written: give the receipt a path of its own')
    save_json(args.receipt, receipt, new=True)
    print(json.dumps(receipt['output'], ensure_ascii=True, indent=1))

if __name__ == '__main__':
    import sys
    files.escape_unprintable()
    try:
        main()
    except (ValueError, OSError) as e:
        print('ERROR:', files.one_line(str(e)), file=sys.stderr)  # one line, whatever text it carries (0.8 step 1.6)
        sys.exit(2)
