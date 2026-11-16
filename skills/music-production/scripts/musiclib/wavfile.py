"""Bounded RIFF/WAVE reader for third-party sample sets (any rate; PCM 8/16/24/32-bit or float32).
Returns float32 frames; unknown chunks are skipped.  Used for library building, not for mixing."""
import struct
from pathlib import Path
import numpy as np

def info(path, max_bytes=2_000_000_000):
    path = Path(path)
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError('WAV exceeds size bound')
    with path.open('rb') as f:
        head = f.read(12)
        if head[:4] != b'RIFF' or head[8:12] != b'WAVE':
            raise ValueError(f'Not RIFF/WAVE: {path.name}')
        fmt = data = smpl = None
        pos = 12
        while pos + 8 <= size:
            f.seek(pos)
            cid, csize = struct.unpack('<4sI', f.read(8))
            if pos + 8 + csize > size + 1:
                # Trailing metadata that runs past the end (a writer that left out the pad byte after an odd-sized
                # data chunk shifts the next header by one) is ignored once the audio has been found.
                if fmt is not None and data is not None:
                    break
                raise ValueError(f'Truncated chunk in {path.name}')
            if cid == b'fmt ':
                fmt = f.read(min(csize, 64))
            elif cid == b'data':
                data = (pos + 8, min(csize, size - pos - 8))
            elif cid == b'smpl':
                smpl = f.read(min(csize, 36 + 24 * 16))
            pos += 8 + csize + (csize & 1)
    if fmt is None or data is None:
        raise ValueError(f'Missing fmt/data in {path.name}')
    if len(fmt) < 16:  # the fields read below; a shorter chunk stopped the build with struct.error (0.8 step 1.7)
        raise ValueError(f'Short WAV format chunk in {path.name}')
    tag, channels, rate, _, align, bits = struct.unpack_from('<HHIIHH', fmt)
    if tag == 0xFFFE and len(fmt) >= 26:
        tag = struct.unpack_from('<H', fmt, 24)[0]
    if channels not in (1, 2) or not 8000 <= rate <= 192000 or align != channels * bits // 8:
        raise ValueError(f'Unsupported WAV layout in {path.name}')
    if (tag, bits) not in ((1, 8), (1, 16), (1, 24), (1, 32), (3, 32)):
        raise ValueError(f'Unsupported WAV encoding {tag}/{bits} in {path.name}')
    frames = data[1] // align
    # Forward loops of the `smpl` chunk as [start, end) frame pairs (the chunk names the last frame played).
    loops = []
    if smpl is not None and len(smpl) >= 36:
        count = min(struct.unpack_from('<I', smpl, 28)[0], (len(smpl) - 36) // 24)
        for i in range(count):
            _, kind, start, end, _, _ = struct.unpack_from('<6I', smpl, 36 + 24 * i)
            if kind == 0 and start < end < frames:
                loops.append((start, end + 1))
    return {'path': str(path), 'tag': tag, 'channels': channels, 'rate': rate, 'bits': bits,
            'offset': data[0], 'frames': frames, 'loops': loops}

def read(path):
    i = info(path)
    with open(i['path'], 'rb') as f:
        f.seek(i['offset'])
        raw = f.read(i['frames'] * i['channels'] * i['bits'] // 8)
    if i['tag'] == 3:
        x = np.frombuffer(raw, '<f4').astype(np.float32)
    elif i['bits'] == 8:
        x = (np.frombuffer(raw, 'u1').astype(np.float32) - 128) / 128
    elif i['bits'] == 16:
        x = np.frombuffer(raw, '<i2').astype(np.float32) / 32768
    elif i['bits'] == 24:
        b = np.frombuffer(raw, 'u1').reshape(-1, 3).astype(np.int32)
        x = (((b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)) ^ 0x800000) - 0x800000).astype(np.float32) / 8388608
    else:
        x = np.frombuffer(raw, '<i4').astype(np.float32) / 2147483648
    x = x.reshape(-1, i['channels'])
    if not np.isfinite(x).all():
        raise ValueError(f'Non-finite samples in {i["path"]}')
    return x, i
