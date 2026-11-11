"""Varying the recording: each hit of a drum part takes one of the takes its bank holds, and where a bank has none a
repeated note borrows the neighbouring key's recording.

A bank built here keeps a hit's recorded takes on neighbouring velocities inside its dynamic layer (take 1 at one
velocity, take 2 at the next, and so on), so a part written at one velocity would play one take every time.  Each
hit of a drum part instead takes one of the layer's takes by a draw of its own, made from the hit's id, its key and
its tick together, at the nearest velocity inside that layer that holds it (with N takes at most N - 1 steps away,
at a layer's edge), as a sampler's random mode does.  The velocity moves only in the MIDI given to the synthesizer;
the project and the exported MIDI keep the written one.  No hit's take depends on another hit, so with N takes one hit in N has the take of
the hit before it.  (Until 0.6 a drum stepped through its takes in order.)

A sampler plays the same recording every time a key repeats, and a fast repeated figure then sounds mechanical (the
"machine-gun" effect); libraries record several takes of each note (round robins) and alternate them.  A bank without
them can still vary the recording: a repeated note is played on a neighbouring key, one or two semitones away, whose
zone holds a different recording, and the pitch wheel brings it back to the written pitch, as samplers that borrow a
neighbour's sample do.  The note keeps its pitch and loudness; its tone is that of the next recording, transposed a
semitone or two further than it would be on its own key.  Only keys whose zones hold different recordings are used,
so a bank sampled every few semitones varies only where its zones change, and a part with pitch bends of its own keeps
its keys.
"""
import hashlib
import threading

from . import sf2

SHIFTS = (1, -1, 2, -2)
MAX_TAKES = 8
_maps, _lock = {}, threading.Lock()


def key_samples(font_path, bank, program):
    """For each key, the set of recordings the preset's zones put on it (any velocity).  Cached per bank and preset."""
    cache_key = (str(font_path), bank, program)
    with _lock:
        if cache_key in _maps:
            return _maps[cache_key]
    font = sf2.read(font_path)
    preset = next((p for p in font['presets'] if p['bank'] == bank and p['program'] == program), None)
    keys = {}
    if preset:
        for pz in preset['zones']:
            if pz['target'] is None:
                continue
            plo, phi = pz['gens'].get(43, (0, 127))
            for z in font['instruments'][pz['target']]['zones']:
                if z['target'] is None:
                    continue
                lo, hi = z['gens'].get(43, (0, 127))
                for k in range(max(lo, plo), min(hi, phi) + 1):
                    keys.setdefault(k, set()).add(z['target'])
    result = {k: frozenset(v) for k, v in keys.items()}
    with _lock:
        _maps[cache_key] = result
    return result


def velocity_cycles(font_path, bank, program):
    """For each key, the layer every velocity falls in, as (first velocity, last velocity, period, index): a layer is
    a run of velocities whose recordings repeat with a period (its round robins; 1 for a single take), and the index
    is the velocity's place in that cycle.  None where no zone plays.  Cached per bank and preset."""
    cache_key = ('cycles', str(font_path), bank, program)
    with _lock:
        if cache_key in _maps:
            return _maps[cache_key]
    font = sf2.read(font_path)
    preset = next((p for p in font['presets'] if p['bank'] == bank and p['program'] == program), None)
    played = {}
    if preset:
        for pz in preset['zones']:
            if pz['target'] is None:
                continue
            plo, phi = pz['gens'].get(43, (0, 127))
            pvlo, pvhi = pz['gens'].get(44, (0, 127))
            for z in font['instruments'][pz['target']]['zones']:
                if z['target'] is None:
                    continue
                lo, hi = z['gens'].get(43, (0, 127))
                vlo, vhi = z['gens'].get(44, (0, 127))
                for k in range(max(lo, plo), min(hi, phi) + 1):
                    row = played.setdefault(k, [set() for _ in range(128)])
                    for v in range(max(vlo, pvlo, 1), min(vhi, pvhi) + 1):
                        row[v].add(z['target'])
    result = {k: cycle_layers(row) for k, row in played.items()}
    with _lock:
        _maps[cache_key] = result
    return result


def cycle_layers(row):
    """velocity_cycles for one key: `row[v]` is the set of recordings a zone plays at velocity v (index 0 unused)."""
    cells = [None] * 128
    layers, start, cycle, period = [], None, [], None
    for v in range(1, 129):
        cur = frozenset(row[v]) if v < len(row) and v < 128 else frozenset()
        if start is not None:
            if period is None and cur and cur not in cycle:
                cycle.append(cur)
                continue
            if period is None and cur and cur == cycle[0]:
                period = len(cycle)
            if period is not None and cur == cycle[(v - start) % period]:
                continue
            # A run that never repeated holds one take per velocity (velocity layers, not round robins).
            layers.append((start, v - 1, period if period is not None and period <= MAX_TAKES else 1))
            start, cycle, period = None, [], None
        if cur:
            start, cycle = v, [cur]
    for first, last, p in layers:
        for v in range(first, last + 1):
            cells[v] = (first, last, p, (v - first) % p)
    return cells


def take_of(note, period):
    """Which of `period` recorded takes a hit plays: a draw from the hit itself, its id (where it has one), the key it
    plays and its tick together, the same on every render and independent of every other hit.  A hit that keeps its
    id and is moved or played on another key draws again."""
    key = f"{note.get('id')}:{note['pitch']}:{note.get('tick')}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % period


def take_velocities(notes, cycles):
    """A velocity for each performed note that gives the hit one of its layer's recorded takes: the take is take_of's
    draw, played at the nearest velocity inside the layer that holds it.  A key with one take per velocity keeps its
    velocities.  `cycles` is velocity_cycles' map."""
    out = []
    for n in notes:
        v = n['velocity']
        info = cycles.get(n['pitch'], [None] * 128)[v] if 0 < v < 128 else None
        if not info or info[2] < 2:
            out.append(v)
            continue
        first, final, period, index = info
        up = (take_of(n, period) - index) % period
        options = [v + d for d in (up, up - period) if first <= v + d <= final]
        out.append(min(options, key=lambda x: abs(x - v)) if options else v)
    return out


def round_robin_shifts(notes, keys, window=1.2):
    """A key shift for each performed note (0 for most): a note that repeats the pitch of one started less than `window`
    seconds before moves to the nearest key, up to two semitones away, whose recordings differ from those the previous
    note of that pitch used; the next repeat may come back.  `notes` are performed notes in time order."""
    last = {}
    shifts = []
    for n in notes:
        pitch, start = n['pitch'], n['start_seconds']
        prev = last.get(pitch)
        shift = 0
        if prev is not None and start - prev[0] < window and pitch in keys:
            used = keys.get(pitch + prev[1])
            for s in (0,) + SHIFTS:
                if s != prev[1] and keys.get(pitch + s) and keys.get(pitch + s) != used:
                    shift = s
                    break
        last[pitch] = (start, shift)
        shifts.append(shift)
    return shifts


def channel_for(shift, base):
    """The MIDI channel a shifted note plays on: `base` + 1 to 4 for shifts +1, -1, +2, -2 (the wheel set to undo it)."""
    return base + 1 + SHIFTS.index(shift)


def wheel_value(shift, bend_range=2):
    """The 14-bit pitch-wheel value that brings a note played `shift` keys away back to its written pitch."""
    return max(0, min(16383, 8192 - round(shift / bend_range * 8192)))
