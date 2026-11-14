#!/usr/bin/env python3
"""Fughetta of the Paper Paddock: the one script that writes every note into song.json.

Layout of this file
  1. notation helpers (note names, a small line DSL) and a counterpoint checker
  2. the material: subject, answer, countersubject, free counterpoints, episodes
  3. the voices, bar by bar
  4. performance, mix, plan, association, and the project file

Run:  python compose.py            -> writes song.json and prints the counterpoint report
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------------------------
# 1. notation helpers
# ----------------------------------------------------------------------------------------------
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def P(name):
    """'Bb3' -> 58, 'C#5' -> 73 (C4 = 60)."""
    m = re.fullmatch(r"([A-G])([#b]*)(-?\d)", name)
    if not m:
        raise ValueError("bad note name %r" % name)
    pc = _PC[m.group(1)] + m.group(2).count("#") - m.group(2).count("b")
    return pc + 12 * (int(m.group(3)) + 1)


def NAME(p):
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    return "%s%d" % (names[p % 12], p // 12 - 1)


def line(text, t0=0.0):
    """Parse 'D4:1.5 A4:.5 r:1 ...' into [(start, dur, pitch)], starting at beat t0.
    A pitch may be followed by '~' to tie it to the next token of the same pitch."""
    out = []
    t = float(t0)
    for tok in text.split():
        pit, dur = tok.split(":")
        d = float(dur)
        if pit != "r":
            out.append((t, d, P(pit)))
        t += d
    return out


def shift(notes, semis=0, beats=0.0):
    return [(t + beats, d, p + semis) for (t, d, p) in notes]


def length(notes):
    return max(t + d for (t, d, p) in notes) - min(t for (t, d, p) in notes)


def at(notes, t, eps=1e-6):
    """pitch sounding at beat t (or None)."""
    for (s, d, p) in notes:
        if s - eps <= t < s + d - eps:
            return p
    return None


def onsets(notes):
    return [s for (s, d, p) in notes]


# ----------------------------------------------------------------------------------------------
# scale-step notation: material written once, rendered in any key
#   a token is  step:duration   (step 0 = tonic in the reference octave, 7 = the octave above,
#   -1 = the note below the tonic); an 'L' before the step marks the leading tone, raised in the
#   minor (C# in D minor) and the plain seventh degree in the major.
# ----------------------------------------------------------------------------------------------
MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]


class Key:
    def __init__(self, tonic_midi, mode):
        self.tonic = tonic_midi
        self.mode = mode
        self.scale = MINOR if mode == "minor" else MAJOR

    def midi(self, step, lt=False):
        octv, idx = divmod(step, 7)
        if lt:
            assert idx == 6, "leading tone must be the 7th degree"
            return self.tonic + 12 * octv + (11 if self.mode == "minor" else self.scale[6])
        return self.tonic + 12 * octv + self.scale[idx]


def steps(text, t0=0.0):
    """'0:1.5 L-1:.5 r:1' -> [(start, dur, step, lt)]"""
    out = []
    t = float(t0)
    for tok in text.split():
        a, d = tok.split(":")
        d = float(d)
        if a != "r":
            lt = a.startswith("L")
            s = int(a[1:] if lt else a)
            out.append((t, d, s, lt))
        t += d
    return out


def render(mat, key, octave_shift=0, t0=0.0, beats=None):
    """step material -> [(start, dur, midi)] in `key`, moved `octave_shift` octaves, starting at t0."""
    base = mat[0][0] if mat else 0.0
    return [(t - base + t0, d, key.midi(s, lt) + 12 * octave_shift) for (t, d, s, lt) in mat]


def tr(mat, ds):
    """transpose step material by ds scale steps (a sequence)."""
    return [(t, d, s + ds, lt) for (t, d, s, lt) in mat]


# ----------------------------------------------------------------------------------------------
# counterpoint checker
# ----------------------------------------------------------------------------------------------
CONSONANT = {0, 3, 4, 7, 8, 9}


def _sounding(notes, t, eps=1e-6):
    for (s, d, p) in notes:
        if s - eps <= t < s + d - eps:
            return (s, d, p)
    return None


def check(voices, order, beat_grid=1.0, label="", verbose=True, exempt=()):
    """voices: name -> [(t,d,p)];  order: names from highest to lowest.
    Reports dissonance on beats, parallel perfect intervals, crossing, wide spacing."""
    problems = []
    tmin = min(min(t for (t, d, p) in v) for v in voices.values() if v)
    tmax = max(max(t + d for (t, d, p) in v) for v in voices.values() if v)
    # simultaneities at every onset of any voice and on the grid
    times = set()
    for v in voices.values():
        for (t, d, p) in v:
            times.add(round(t, 4))
    g = tmin
    while g < tmax:
        times.add(round(g, 4))
        g += beat_grid
    times = sorted(times)
    prev = None
    for T in times:
        snd = {n: _sounding(voices[n], T) for n in order if n in voices}
        now = {n: s[2] for n, s in snd.items() if s}
        names = [n for n in order if n in now]
        # crossing / spacing
        for a, b in zip(names, names[1:]):
            if now[a] < now[b]:
                problems.append((T, "crossing %s below %s" % (a, b)))
            elif now[a] - now[b] > 19 and a not in ("LH",) and b not in ("B", "LH"):
                problems.append((T, "wide %s-%s %d" % (a, b, now[a] - now[b])))
        # dissonance on integer beats (strong)
        if abs(T - round(T)) < 1e-6:
            low = names[-1] if names else None
            for i, a in enumerate(names):
                for b in names[i + 1:]:
                    if a in exempt or b in exempt:
                        continue
                    iv = (now[a] - now[b]) % 12
                    ok = iv in CONSONANT or (iv == 5 and b != low)
                    if not ok:
                        # allowed: suspension  (upper or lower note was struck before T and resolves down by step)
                        sus = False
                        for who in (a, b):
                            s0, d0, p0 = snd[who]
                            if s0 < T - 1e-6:
                                nxt = _sounding(voices[who], s0 + d0 + 1e-6)
                                if nxt and 0 < p0 - nxt[2] <= 2 and nxt[0] - (s0 + d0) < 1e-6:
                                    sus = True
                        if not sus:
                            problems.append((T, "dissonance %s/%s %s-%s (%d)" % (a, b, NAME(now[a]), NAME(now[b]), iv)))
        # parallels
        if prev is not None:
            pt, pnow = prev
            for i, a in enumerate(names):
                for b in names[i + 1:]:
                    if a in pnow and b in pnow:
                        i0 = (pnow[a] - pnow[b]) % 12
                        i1 = (now[a] - now[b]) % 12
                        da = now[a] - pnow[a]
                        db = now[b] - pnow[b]
                        if i0 == i1 and i0 in (0, 7) and da != 0 and db != 0 and da * db > 0:
                            problems.append((T, "parallel %s %s/%s %s-%s" % ("5ths" if i0 == 7 else "8ves", a, b, NAME(now[a]), NAME(now[b]))))
        prev = (T, now)
    # melodic checks
    for n, v in voices.items():
        v = sorted(v)
        for (t1, d1, p1), (t2, d2, p2) in zip(v, v[1:]):
            iv = abs(p2 - p1)
            if iv > 12 and t2 - (t1 + d1) < 0.5:
                problems.append((t2, "melodic leap %s %s->%s" % (n, NAME(p1), NAME(p2))))
            if iv == 6:
                problems.append((t2, "melodic tritone %s %s->%s" % (n, NAME(p1), NAME(p2))))
    # also catch exact same-voice overlaps
    for n, v in voices.items():
        v = sorted(v)
        for (t1, d1, p1), (t2, d2, p2) in zip(v, v[1:]):
            if t2 < t1 + d1 - 1e-6:
                problems.append((t2, "overlap in voice %s" % n))
    if verbose:
        print("check %s: %d problem(s)" % (label, len(problems)))
        for T, m in sorted(problems)[:60]:
            print("   beat %7.2f (bar %d.%.2f): %s" % (T, int(T // 4), T % 4 + 1, m))
    return problems


# ----------------------------------------------------------------------------------------------
# design aid: a seeded search for a free counterpoint against fixed voices (used while composing;
# the lines it found are written out below as notes, they are not generated at build time)
# ----------------------------------------------------------------------------------------------
def search_line(fixed, order, new, rhythm, t0, lo, hi, pcs, prev=None, end_pcs=None, start_pcs=None,
                seed=1, tries=40000, maxleap=7, top=8, noteps=None, avoid_unison=True, wavy=True, strong_pcs=None):
    import random
    rng = random.Random(seed)
    ts = []
    t = t0
    for d in rhythm:
        ts.append(t)
        t += d
    above = [n for n in order[:order.index(new)]]
    below = [n for n in order[order.index(new) + 1:]]
    allv = {n: v for n, v in fixed.items()}
    ev = sorted(set(round(x, 4) for v in fixed.values() for (x, _, _) in v) | set(round(x, 4) for x in ts))
    found = {}
    for _ in range(tries):
        ps = []
        ok = True
        for i, (T, d) in enumerate(zip(ts, rhythm)):
            opts = []
            for p in range(lo, hi + 1):
                if p % 12 not in pcs:
                    continue
                if i == 0 and prev is not None and abs(p - prev) > 5:
                    continue
                if i == 0 and start_pcs and p % 12 not in start_pcs:
                    continue
                if i == len(ts) - 1 and end_pcs and p % 12 not in end_pcs:
                    continue
                if i > 0:
                    q = ps[-1]
                    if abs(p - q) > maxleap or abs(p - q) == 6 or (p == q and not (noteps and "rep" in noteps)):
                        continue
                good = True
                if strong_pcs is not None and abs(T - round(T)) < 1e-6:
                    sp_ = strong_pcs(T)
                    if sp_ is not None and p % 12 not in sp_:
                        continue
                # ordering and consonance at every beat the note covers, plus its onset
                chk = [T] + [b for b in range(int(T) + 1, int(T + d - 1e-6) + 1) if b > T + 1e-6]
                for X in chk:
                    sn = {n: _sounding(allv[n], X) for n in fixed}
                    sn = {n: s[2] for n, s in sn.items() if s}
                    for n in above:
                        if n in sn and not sn[n] > p:
                            good = False
                    for n in below:
                        if n in sn and not sn[n] < p:
                            good = False
                    if not good:
                        break
                    allp = list(sn.values()) + [p]
                    lowest = min(allp)
                    strong = abs(X - round(X)) < 1e-6
                    for n, q in sn.items():
                        iv = abs(p - q) % 12
                        if strong or X == T and abs(T - round(T)) < 1e-6:
                            cons = iv in CONSONANT or (iv == 5 and min(p, q) != lowest)
                            if not cons:
                                good = False
                                break
                        if avoid_unison and strong and iv == 0 and abs(p - q) < 1:
                            good = False
                    if not good:
                        break
                if good:
                    opts.append(p)
            if not opts:
                ok = False
                break
            q = ps[-1] if ps else prev
            w = []
            for p in opts:
                if q is None:
                    w.append(1)
                else:
                    iv = abs(p - q)
                    w.append(8 if iv <= 2 else (3 if iv <= 4 else 1))
            ps.append(rng.choices(opts, w)[0])
        if not ok:
            continue
        line_ = [(T, d, p) for T, d, p in zip(ts, rhythm, ps)]
        # off-beat dissonances must be passing/neighbour
        bad = False
        for i, (T, d, p) in enumerate(line_):
            if abs(T - round(T)) < 1e-6:
                continue
            for n, v in fixed.items():
                s = _sounding(v, T)
                if s and (abs(p - s[2]) % 12) not in CONSONANT | {5}:
                    a = ps[i - 1] if i > 0 else prev
                    c = ps[i + 1] if i + 1 < len(ps) else None
                    if a is None or c is None or abs(a - p) > 2 or abs(c - p) > 2:
                        bad = True
                        break
            if bad:
                break
        if bad:
            continue
        # parallels with every fixed voice
        for n, v in fixed.items():
            pv = None
            for E in ev:
                a = _sounding(line_, E)
                b = _sounding(v, E)
                if a and b:
                    cur = (a[2], b[2])
                    if pv and pv[0] != cur[0] and pv[1] != cur[1]:
                        i0 = abs(pv[0] - pv[1]) % 12
                        i1 = abs(cur[0] - cur[1]) % 12
                        if i0 == i1 and i0 in (0, 7) and (cur[0] - pv[0]) * (cur[1] - pv[1]) > 0:
                            bad = True
                    pv = cur
            if bad:
                break
        if bad:
            continue
        cost = 0.0
        seq = ([prev] if prev is not None else []) + ps
        for x, y in zip(seq, seq[1:]):
            iv = abs(x - y)
            cost += 0 if iv <= 2 else (1.0 if iv <= 4 else 2.5)
        mx = max(ps)
        cost += 2.5 * (ps.count(mx) - 1)
        dirs = [(y > x) - (y < x) for x, y in zip(ps, ps[1:])]
        ch = sum(1 for a, b in zip(dirs, dirs[1:]) if a != b)
        cost += 0.7 * abs(ch - len(ps) // 3)
        cost += 0.5 * max(0, (max(ps) - min(ps)) - 10)
        found[tuple(ps)] = cost
    res = sorted(found.items(), key=lambda kv: kv[1])[:top]
    return [(c, [(T, d, p) for T, d, p in zip(ts, rhythm, ps)]) for ps, c in res]


def show(l):
    return " ".join("%s:%s" % (NAME(p), ("%g" % d)) for (t, d, p) in l)


# ==============================================================================================
# 2. THE MATERIAL
#    D minor, 4/4, written for harpsichord (two hands), violin, viola and cello.
# ==============================================================================================
# Subject (two bars): a head that climbs the tonic triad to the octave (D-A-D), and a tail that
# turns back on itself - a falling scale, then two sixteenth-note cells, each the neighbour-note
# figure "3 2 1 2" a step lower, closing on the leading tone.  The tail is the head folded over.
SUBJECT = steps("0:1.5 4:.5 7:1 6:.5 5:.5 4:1 3:.25 2:.25 1:.25 2:.25 1:.25 0:.25 L-1:.25 0:.25 0:1")
# Countersubject (two bars): rice-grain eighths wobbling around the third and the sixth below,
# a climb to the peak, then a fold of an octave down.  Only thirds and sixths against the subject
# on every beat, so it can stand above or below it and moves to any key with it.
COUNTER = steps("-2:.5 -3:.5 -2:.5 -3:.5 -2:.5 0:.5 1:1 2:1 1:1 L-1:.5 -3:.5 -5:1")
HEAD = steps("0:1.5 4:.5 7:1 6:.5 5:.5")                               # bar one of the subject
CS_BAR1 = steps("-2:.5 -3:.5 -2:.5 -3:.5 -2:.5 0:.5 1:1")              # bar one of the countersubject
HEAD_LAST = steps("0:1.5 4:.5 7:1 6:1")                                # the head ending on a held seventh (last bar of a sequence)

DM = Key(62, "minor")      # D minor, tonic D4
AM = Key(69, "minor")      # A minor (the real answer), tonic A4
FM = Key(65, "major")      # F major, tonic F4
CM = Key(72, "major")      # C major, tonic C5 (answer in the dominant of F)
FM2 = Key(41, "major")     # F major, tonic F2
GM_VLA = Key(55, "minor")  # G minor, tonic G3
GM_VC = Key(43, "minor")   # G minor, tonic G2
GM_VLN = Key(67, "minor")  # G minor, tonic G4

TRACKS = ["hpd", "hpd44", "lh", "vln", "vla", "vc"]


class Score:
    def __init__(self):
        self.v = {k: [] for k in TRACKS}

    def put(self, voice, notes, tag):
        for (t, d, p) in notes:
            self.v[voice].append((round(t, 6), d, p, tag))

    def plain(self):
        return {k: [(t, d, p) for (t, d, p, g) in sorted(v)] for k, v in self.v.items()}


def build_score():
    sc = Score()
    put = sc.put

    # ---------------- exposition, bars 0-9 (beats 0-40) -------------------------------------
    # hpd: subject (alto)  ->  countersubject under the violin's answer  ->  free line  ->  countersubject
    put("hpd", render(SUBJECT, DM, 0, t0=0), "subject")
    put("vln", render(SUBJECT, AM, 0, t0=8), "answer")
    put("hpd", render(COUNTER, AM, 0, t0=8), "countersubject")
    put("vla", render(SUBJECT, DM, -1, t0=16), "subject")
    put("vln", render(COUNTER, DM, 1, t0=16), "countersubject")
    put("hpd", line("F4:.5 E4:.5 D4:1 F4:1 G4:1 A4:.5 F4:.5 G4:1 E4:1 A3:1", 16), "free")
    put("vc", render(SUBJECT, AM, -2, t0=24), "answer")
    put("hpd", render(COUNTER, AM, 0, t0=24), "countersubject")
    put("vla", line("F3:1.5 C4:1.5 E4:1 C4:1 D4:1 B3:1 A3:1", 24), "free")
    put("vln", line("A4:1 C5:.5 D5:.5 C5:.5 D5:.5 E5:1 G#5:.5 A5:.5 B5:.5 A5:.5 G#5:1 A5:1", 24), "free")
    # codetta: i - VI - iv - V over a cello that walks, then the deceptive turn into the episode
    put("vc", line("A2:2 D3:2 Bb2:1 G2:1 A2:2", 32), "codetta")
    put("vla", line("A3:2 Bb3:1 A3:1 Bb3:1 D4:1 C#4:2", 32), "codetta")
    put("hpd", line("C#4:1 E4:1 D4:.5 E4:.5 F4:1 G4:.5 A4:.5 G4:1 F4:1 E4:.5 r:.5", 32), "codetta")
    put("vln", line("F5:1 A5:.5 G5:.5 F5:.5 G5:.5 F5:1 D5:.5 C#5:.5 D5:.5 C5:.5 C#5:1 E5:.5 r:.5", 32), "codetta")

    # ---------------- episode 1, bars 10-12 (beats 40-52): IV - V - I of F, sequence rising by fourths
    for i, k in enumerate((0, 3, 6)):
        put("vln", render(tr(HEAD, k), DM, 0, t0=40 + 4 * i), "episode")
        put("hpd", render(tr(CS_BAR1, k), DM, 0, t0=40 + 4 * i), "episode")
    put("vc", line("Bb2:1 G2:1 Bb2:1 C3:1 C3:1 E3:1 C3:1 A2:1 A2:1 C3:1 F2:1 Bb2:1", 40), "episode")

    # ---------------- entries in the relative major, bars 13-18 (beats 52-76) ------------------
    put("hpd", render(SUBJECT, FM, 0, t0=52), "subject")                       # subject in F
    put("vc", line("F2:2 A2:1 G2:1 A2:1 Bb2:.5 C3:.5 Bb2:1 A2:1", 52), "support")
    put("vln", render(SUBJECT, CM, 0, t0=60), "answer")                         # answer in C
    put("hpd", render(COUNTER, CM, 0, t0=60), "countersubject")
    put("vc", line("C3:2 A2:1 B2:1 C3:1 D3:.5 C3:.5 B2:1 C3:1", 60), "support")
    put("vc", render(SUBJECT, FM2, 0, t0=68), "subject")                        # subject in F, in the bass
    put("vln", render(COUNTER, FM, 0, t0=68), "countersubject")
    put("hpd", line("D5:.5 E5:.5 F5:1 A5:1 G5:1 E5:.5 C5:.5 D5:1 E5:1 F5:1", 68), "free")

    # ---------------- episode 2, bars 19-22 (beats 76-92): descending thirds F-Dm-Bb, then D (V of G minor)
    for i, k in enumerate((0, -2, -4)):
        put("hpd", render(tr(HEAD, k), FM, 0, t0=76 + 4 * i), "episode")
        put("vla", render(tr(CS_BAR1, k), FM, 0, t0=76 + 4 * i), "episode")
    put("vc", line("F3:1 Bb2:1 D3:1 C3:1 D3:1 G2:1 Bb2:1 C3:1 Bb2:1 G2:1 Bb2:1 F3:1", 76), "episode")
    put("vc", line("D3:1 F#3:1 D3:1 A2:1", 88), "cadence")
    put("hpd", line("F#4:1 A4:.5 Bb4:.5 A4:.5 G4:.5 A4:1", 88), "cadence")

    # ---------------- entries in G minor (the subdominant), bars 23-28 (beats 92-116) ---------
    put("vla", render(SUBJECT, GM_VLA, 0, t0=92), "subject")
    put("vc", line("Bb2:1 C3:1 Bb2:1 A2:1 Bb2:1 C3:1 D3:1 E3:1", 92), "support")
    put("vln", render(SUBJECT, DM, 0, t0=100), "answer")                         # answer in D minor
    put("vla", render(COUNTER, DM, 0, t0=100), "countersubject")
    put("vc", line("G2:2 Bb2:1 C3:1 A2:1 C3:1 C#3:1 D3:1", 100), "support")
    put("vc", render(SUBJECT, GM_VC, 0, t0=108), "subject")
    put("vln", render(COUNTER, GM_VLN, 0, t0=108), "countersubject")
    put("hpd", line("Bb5:1 G5:.5 F5:.5 Eb5:1 F5:1 F#5:1 A5:.5 G5:.5 A5:1", 108), "free")

    # ---------------- episode 3, bars 29-34 (beats 116-140): Gm-F-Dm-Bb, then E diminished and A -
    for i, k in enumerate((5, 4, 2, 0)):
        put("vln", render(tr(HEAD_LAST if i == 3 else HEAD, k), DM, 0, t0=116 + 4 * i), "episode")
        put("hpd", render(tr(CS_BAR1, k), DM, 0, t0=116 + 4 * i), "episode")
    put("vc", line("G2:1 Bb2:1 G2:1 F2:1 F2:1 A2:1 F2:1 G2:1 D3:1 F3:1 D3:1 C3:1 Bb2:1 D3:1 Bb2:1 A2:1", 116), "episode")
    put("hpd", line("E4:.5 F4:.5 G4:.5 A4:.5 Bb4:1 G4:1 A4:.5 Bb4:.5 A4:1 C#5:1", 132), "ascent")
    put("vc", line("G2:1 E2:1 G2:1 Bb2:1 A2:2 E3:1 A2:1", 132), "ascent")

    # ---------------- stretto over the dominant pedal, bars 35-42 (beats 140-172) --------------
    # the entries alternate answer (A minor) and subject (D minor), one every six beats
    put("vln", render(SUBJECT, AM, 0, t0=140), "stretto")
    put("hpd44", render(SUBJECT, DM, 0, t0=146), "stretto")
    put("vla", render(SUBJECT, AM, -1, t0=152), "stretto")
    put("vln", render(SUBJECT, DM, 1, t0=158), "stretto")
    put("hpd44", render(SUBJECT, AM, 0, t0=164), "stretto")
    for b in range(8):
        put("vc", line("A2:1 A3:1 A2:1 A3:1" if b < 7 else "A2:1 A3:1 A2:1 A2:1", 140 + 4 * b), "pedal")

    # ---------------- return, bars 43-44 (beats 172-180): the subject in the bass, tonic -------
    put("vc", render(SUBJECT, DM, -2, t0=172), "subject")
    put("vln", render(COUNTER, DM, 1, t0=172), "countersubject")
    put("vla", line("D4:2 Bb3:1 C4:1 F4:1 G4:1 E4:1 D4:1", 172), "free")

    # ---------------- coda, bars 45-52 (beats 180-212) -----------------------------------------
    # the third episode again with violin and viola, then the ascent to the dominant
    for i, k in enumerate((5, 4, 2, 0)):
        put("vln", render(tr(HEAD_LAST if i == 3 else HEAD, k), DM, 0, t0=180 + 4 * i), "episode")
        put("vla", render(tr(CS_BAR1, k), DM, 0, t0=180 + 4 * i), "episode")
    put("vc", line("Bb2:1 G2:1 Bb2:1 F2:1 F2:1 A2:1 F2:1 G2:1 D3:1 F3:1 D3:1 C3:1 Bb2:1 D3:1 Bb2:1 A2:1", 180), "episode")
    put("hpd", line("E4:.5 F4:.5 G4:.5 A4:.5 Bb4:1 G4:1 A4:.5 Bb4:.5 A4:1 C#5:1", 196), "ascent")
    put("vc", line("G2:1 E2:1 G2:1 Bb2:1 A2:2 E3:1 A2:1", 196), "ascent")
    # cadence: i - iv6 - V7 - I with the third raised (tierce de Picardie)
    # the trill on the penultimate note starts on the upper note (D5) and is written out
    put("vln", line("D5:3 D5:.25 C#5:.25 D5:.25 C#5:.25 D5:4", 204), "cadence")
    put("hpd44", line("F4:2 D4:1 E4:1 A4:4", 204), "cadence")
    put("vla", line("A3:2 G3:1 G3:1 F#3:4", 204), "cadence")
    put("vc", line("D3:2 Bb2:1 A2:1 D2:4", 204), "cadence")

    # harpsichord left hand: doubles the cello line (continuo), from the cello's first entry
    for (t, d, p, g) in sorted(sc.v["vc"]):
        if t >= 24 - 1e-6 and not (140 - 1e-6 <= t < 172 - 1e-6) and t < 204 - 1e-6:
            sc.v["lh"].append((t, d, p, "continuo"))
    # in the stretto the left hand keeps the dominant pedal in its own octave strokes
    for b in range(8):
        for (t, d, p) in line("A2:1 A3:1 A2:1 A3:1" if b < 7 else "A2:1 A3:1 A2:1 A2:1", 140 + 4 * b):
            sc.v["lh"].append((t, d, p, "pedal"))
    # the last chord: the left hand spreads D-A under the others
    sc.v["lh"].append((204.0, 2, 50, "cadence"))
    sc.v["lh"].append((206.0, 1, 46, "cadence"))
    sc.v["lh"].append((207.0, 1, 45, "cadence"))
    sc.v["lh"].append((208.0, 4, 38, "cadence"))
    return sc


# ==============================================================================================
# 3. SECTIONS, PERFORMANCE, MIX, PLAN
# ==============================================================================================
SECTIONS = [
    ("exposition", 0, 10, "Subject in the harpsichord, answer in the violin, subject in the viola, answer in the cello, "
                          "the countersubject kept in its own voice each time; a codetta closes it"),
    ("episode1", 10, 3, "Head and countersubject in a sequence rising by fourths: IV - V - I of F major"),
    ("entry_F", 13, 6, "Subject in F major (harpsichord), answer in C (violin), subject in the bass"),
    ("episode2", 19, 4, "Head and countersubject falling by thirds, F - Dm - Bb, then D, the dominant of G minor"),
    ("entry_G", 23, 6, "Subject in G minor (viola), answer in D minor (violin), subject in the bass (cello)"),
    ("episode3", 29, 6, "Gm - F - Dm - Bb in the sequence, then E diminished and the dominant A"),
    ("stretto", 35, 8, "Stretto: five entries, answer and subject alternating one bar and a half apart, over a dominant pedal"),
    ("return", 43, 2, "The subject in the bass in the tonic, the countersubject above it"),
    ("coda", 45, 8, "The third episode with violin and viola, the ascent to the dominant, a firm cadence with the third raised"),
]

# written dynamic (velocity of the strings) by section: terraced, as the style asks
SECTION_VEL = {"exposition": 78, "episode1": 82, "entry_F": 72, "episode2": 80, "entry_G": 76, "episode3": 84,
               "stretto": 96, "return": 80, "coda": 76}
VOICE_VEL = {"vln": 0, "vla": 2, "vc": 0}
TAG_VEL = {"subject": 7, "answer": 7, "stretto": 4, "countersubject": -2, "free": -5, "episode": 0, "support": -10,
           "pedal": -8, "continuo": -8, "codetta": -2, "cadence": 2, "ascent": 0}


def section_of_beat(t):
    bar = int(t // 4)
    for (sid, start, n, _) in SECTIONS:
        if start <= bar < start + n:
            return sid
    return SECTIONS[-1][0]


TRACK_DEFS = {
    "hpd": dict(name="Harpsichord, right hand", role="melody", soundfont="vcsl_keys", patch={"bank": 1, "program": 6},
                program=6, bank=0, range=[55, 88]),
    "hpd44": dict(name="Harpsichord, right hand, full manual (8' + 4')", role="melody", soundfont="vcsl_keys",
                  patch={"bank": 2, "program": 6}, program=6, bank=0, range=[55, 92]),
    "lh": dict(name="Harpsichord, left hand (continuo)", role="harmony", soundfont="vcsl_keys",
               patch={"bank": 1, "program": 6}, program=6, bank=0, range=[30, 60]),
    "vln": dict(name="Violin", role="melody", soundfont="vsco", patch={"bank": 0, "program": 40},
                program=40, bank=0, range=[55, 90]),
    "vla": dict(name="Viola", role="melody", soundfont="iowa_strings", patch={"bank": 0, "program": 41},
                program=41, bank=0, range=[48, 84]),
    "vc": dict(name="Cello", role="bass", soundfont="cello_bigcat", patch={"bank": 0, "program": 42},
               program=42, bank=0, range=[36, 76]),
}

MIX = {
    "hpd": dict(level_dbfs=-25, pan=-0.05, highpass=60, lowpass=16000, depth_m=2.5, offset_ms=0),
    "hpd44": dict(level_dbfs=-26, pan=-0.05, highpass=60, lowpass=16000, depth_m=2.5, offset_ms=0),
    "lh": dict(level_dbfs=-31, pan=0.05, highpass=35, lowpass=9000, depth_m=3.0, offset_ms=0),
    "vln": dict(level_dbfs=-25, pan=-0.45, highpass=130, lowpass=15000, depth_m=2.0, offset_ms=-20),
    "vla": dict(level_dbfs=-25, pan=0.2, highpass=90, lowpass=14000, depth_m=2.5, offset_ms=-40),
    "vc": dict(level_dbfs=-26, pan=0.45, highpass=35, lowpass=12000, depth_m=3.0, offset_ms=-15),
}


STRETTO_LIFT = {"hpd44": 1.5, "vln": 1, "vla": 1, "vc": 1, "lh": 1}


def gate_for(voice, d, prev_same):
    if voice in ("hpd", "hpd44", "lh"):
        g = 0.75 if d <= 0.25 else 0.8 if d <= 0.5 else 0.88 if d <= 1 else 0.93
        return min(g, 0.78) if prev_same else g
    g = 0.84 if d <= 0.25 else 0.9 if d <= 0.5 else 0.95 if d <= 1 else 0.98
    return g


def build_tracks(sc):
    tracks = []
    for tid in TRACKS:
        d = TRACK_DEFS[tid]
        notes, perf = [], {}
        seq = sorted(sc.v[tid])
        per_bar = {}
        prev_pitch = None
        for (t, dur, p, tag) in seq:
            bar = int(t // 4) + 1
            k = per_bar.get(bar, 0)
            per_bar[bar] = k + 1
            nid = "%s_b%03d_n%02d" % (tid, bar, k)
            notes.append({"id": nid, "on": round(t, 6), "duration": dur, "pitch": p, "phrase": tag})
            if tid in ("hpd", "hpd44", "lh"):
                vel = 100
            else:
                vel = (SECTION_VEL[section_of_beat(t)] + TAG_VEL.get(tag, 0) + VOICE_VEL.get(tid, 0)
                       + (-4 if (tid == "vc" and tag == "episode") else 0))
                if abs(t - round(t)) < 1e-6 and int(round(t)) % 4 == 0:
                    vel += 3
                vel = max(40, min(120, vel))
            gate = gate_for(tid, dur, prev_pitch == p)
            if bar == 53 and dur >= 4:
                gate = 1.0
            perf[nid] = {"velocity": int(vel), "timing_ms": 0, "gate": gate}
            prev_pitch = p
        tr_ = {
            "id": tid, "name": d["name"], "role": d["role"], "engine": "soundfont", "program": d["program"],
            "bank": d["bank"], "drums": False, "range": d["range"], "soundfont": d["soundfont"], "patch": d["patch"],
            "notes": notes,
            "performance": {"notes": perf, "offset_ms": MIX[tid]["offset_ms"]},
            "mix": {"level_dbfs": MIX[tid]["level_dbfs"], "level_mode": "active_rms", "pan": MIX[tid]["pan"],
                    "highpass": MIX[tid]["highpass"], "lowpass": MIX[tid]["lowpass"], "reverb_db": -14,
                    "space": "hall", "depth_m": MIX[tid]["depth_m"]},
        }
        if tid in STRETTO_LIFT:                     # the stretto stands a little above the rest (terraced, not a swell)
            tr_["mix"]["automation"] = [[0, 0], [139.5, 0], [140, STRETTO_LIFT[tid]], [171.5, STRETTO_LIFT[tid]], [172, 0]]
        tracks.append(tr_)
    return tracks


WORDS = ["savanna", "origami", "rice", "heel", "paddock", "huddle", "spider", "lattice", "shutter", "magpie", "rowboat", "fry"]
WHOLE = ("On a wet afternoon someone folds a savanna out of rice paper on a table by a window with a wooden lattice "
         "and a shutter: a paddock of paper animals, a paper rowboat on a bowl of water with a shoal of paper fry "
         "under it. A spider lets one thread down across the lattice, then a second and a third along the same "
         "path, and a fourth, so that four threads hang there answering one another. A magpie hops along the sill, "
         "takes a bright scrap of the web at a time and carries it from pane to pane, from room to room of the "
         "paddock. Grains of rice scatter and settle. At the end every animal huddles into one corner of the "
         "paddock, the heel of a foot is planted on one note, the shutter is pulled to, and the last light "
         "through the lattice goes out in one firm chord.")
GIVES = [
    {"level": "form", "what": "the fugue follows the scene: the exposition lays the four threads one by one; three "
     "episodes are the magpie carrying scraps; the stretto is the huddle; the cadence is the shutter", "where": "all sections"},
    {"level": "melody", "what": "subject = the thread: a head that leaps D-A-D across the lattice and a tail that folds the "
     "paper back (a falling scale, then the neighbour-note cell 3-2-1-2 twice, a step lower each time); "
     "countersubject = the rice: even eighth notes in thirds and sixths that keep their shape", "where": "bars 1-44"},
    {"level": "harmony", "what": "the paddock is a fence of related keys: F major (the relative) and G minor (the subdominant) "
     "as its two rooms; the huddle is a dominant pedal the voices crowd over; the last chord lets the light in with a raised third",
     "where": "bars 14-19, 24-29, 36-43, 52-53"},
    {"level": "rhythm", "what": "the rowboat is the cello's paired oar strokes (root-third-root, then A low-high-low-high) "
     "under the episodes and the pedal; the fry are the sixteenth-note flicks in the tail", "where": "bars 11-13, 30-33, 36-43"},
    {"level": "sounds", "what": "rice paper and plucked wire: the harpsichord on its single Flemish 8-foot stop, "
     "with a solo violin, viola and cello, each a single player, as in a room for four", "where": "whole piece"},
    {"level": "mix", "what": "the shutter: the room is a near one (clarity C80 +8 dB), the lines easy to follow, "
     "little hall around them", "where": "whole piece"},
]

PLAN = {
    "identity": "A fughetta in D minor made from two bars of subject (a rising D-A-D head folded back by a "
                "neighbour-note tail) and two bars of countersubject (rice-grain eighths), passed between harpsichord, "
                "violin, viola and cello, sequenced in the episodes and crowded together in a stretto over a dominant pedal.",
    "high_point": {"section": "stretto", "means": "entries one bar and a half apart over a held dominant, the violin's "
                   "subject an octave higher (D5-D6) in bar 40, the cello's pedal in octave strokes, ending in the "
                   "dominant that the return resolves"},
    "sections": [
        {"section": "exposition", "sounds": ["hpd", "vln", "vla", "vc", "lh"], "leads": "hpd",
         "differs": "four entries, each in a new voice; the countersubject stays beside each"},
        {"section": "episode1", "sounds": ["vln", "hpd", "vc", "lh"], "leads": "vln",
         "differs": "the head and the countersubject in sequence, the viola resting"},
        {"section": "entry_F", "sounds": ["hpd", "vln", "vc", "lh"], "leads": "hpd",
         "differs": "the subject in the relative major, three voices only"},
        {"section": "episode2", "sounds": ["hpd", "vla", "vc", "lh"], "leads": "hpd",
         "differs": "harpsichord and viola as the pair; the violin rests"},
        {"section": "entry_G", "sounds": ["vla", "vln", "vc", "hpd", "lh"], "leads": "vla",
         "differs": "the viola begins the entries; the subdominant colour (Eb, F#)"},
        {"section": "episode3", "sounds": ["vln", "hpd", "vc", "lh"], "leads": "vln",
         "differs": "falling sequence, then the climb to the dominant"},
        {"section": "stretto", "sounds": ["vln", "hpd44", "vla", "vc", "lh"], "leads": "vln",
         "differs": "entries overlap; the cello holds the pedal"},
        {"section": "return", "sounds": ["vc", "vln", "vla", "lh"], "leads": "vc",
         "differs": "the subject in the bass, in the tonic, after the pedal"},
        {"section": "coda", "sounds": ["vln", "vla", "vc", "hpd", "hpd44", "lh"], "leads": "vln",
         "differs": "the third episode with other voices, then the cadence"},
    ],
}


DECISIONS = [
    "vertical: seven places, each sounding twice because the harpsichord's left hand doubles the cello. Three were changed: "
    "bar 7, where the viola's held F3 rubbed the cello's E3 for an eighth, now moves to C4 half a beat earlier; bars 33 and 49, "
    "where the last eighth pair of the falling head put Bb4 over the bass A2, now end the head on a held C5. The other four "
    "(bars 35, 38, 41, 51) are a Bb eighth, entered and left by step on a weak half beat, over the dominant A: the flat ninth "
    "of the dominant, a colour that D minor takes in the style, and it is part of the subject's own falling head in bars 38 and 41; kept.",
]
REVISIONS = [
    {"version": "1.0.r1", "note": "first draft: four-voice fughetta, 53 bars, harpsichord on one 8-foot register"},
    {"version": "1.0.r2", "note": "answered the review's collisions (bars 7, 33, 49); the stretto made the high point by "
                                  "registration (the harpsichord's 8' + 4' on its entries and the last chord), by 102 against "
                                  "76-84 in velocity and by +2 dB; the coda and the cadence lowered (r1 measured the coda "
                                  "2.8 dB above the stretto and the cadence at -1.2 dBFS, holding the whole master 1.6 dB under "
                                  "its target); the violin and viola labelled melody parts, the viola raised 2 dB and the cello "
                                  "lowered 1 dB; target loudness -18 LUFS"},
    {"version": "1.0.r3", "note": "r2 measured the stretto 5.5 dB above the episodes (-14.6 against -19.5 to -21.8 LUFS, the "
                                  "violin and viola stems near -16): lowered to 96 in velocity and +1 to +1.5 dB; the cello's "
                                  "bass lines in the episodes 4 velocity steps and its support lines under entries 4 more "
                                  "(r2: the cello 0.9 dB under the melody group in the G minor entries, the left hand 1.9 dB), "
                                  "the left hand 2 dB lower"},
    {"version": "1.0.r4", "note": "attack times measured on the r3 stems at the first entries (10% of the note's early peak: "
                                  "violin 23 ms, cello 19 ms, viola 39 ms before its -40 ms offset): offsets of -20 ms "
                                  "(violin) and -15 ms (cello) so that the entries sit on the beat with the harpsichord; the "
                                  "penultimate note of the final cadence trilled, written out from the upper note (baroque.md)"},
]


def build_project():
    sc = build_score()
    tracks = build_tracks(sc)
    project = {
        "schema": "music-production/v1",
        "title": "Fughetta of the Paper Paddock",
        "version": "1.0.r4",
        "brief": ("A baroque-style fughetta for harpsichord and strings, about two and a half minutes: a subject with a "
                  "clear head and tail answered by each voice in turn, a countersubject that keeps its shape, episodes "
                  "in sequence to related keys, a stretto over a dominant pedal near the end, and a firm cadence."),
        "style": "orchestral/baroque",
        "clock": {"bars": 53, "meter": [4, 4], "tempo": [[0, 90]], "tail_seconds": 6,
                  "rubato": {"final_ratio": 0.7, "final_beats": 6, "phrase_ratio": 0.96, "phrase_beats": 1, "q": 2}},
        "sections": [{"id": sid, "start_bar": start, "bars": n, "intent": intent} for (sid, start, n, intent) in SECTIONS],
        "tracks": tracks,
        "mix": {"chain": "bus", "rules": 2, "dynamics": "wide", "c80_db": 8, "target_lufs": -18},
        "association": {"source": "draw", "seed": 1625065070, "words": WORDS, "whole": WHOLE, "gives": GIVES},
        "plan": PLAN,
        "decisions": DECISIONS,
        "revision_history": REVISIONS,
    }
    return project


def main():
    # Edited for this repository: the skill's scripts are found from this file's place, or on PYTHONPATH (the agent's own
    # line named the folder of a copy of the skill on the machine it ran on).
    from pathlib import Path
    SKILL = next((p for d in Path(__file__).resolve().parents for p in (d / 'skills' / 'music-production' / 'scripts', d / 'music-production' / 'scripts') if p.is_dir()), None)
    if SKILL:
        sys.path.insert(0, str(SKILL))
    from musiclib import expression
    project = build_project()
    expression.apply(project, {"lh": {"timing_sd": 4}}, seed=1625065070, drift="time")
    out = os.path.join(HERE, "song.json")
    with open(out, "w", encoding="utf8") as f:
        json.dump(project, f, indent=1)
    n = sum(len(t["notes"]) for t in project["tracks"])
    print("wrote", out, n, "notes")


if __name__ == "__main__":
    if "--check" in sys.argv:
        sc = build_score()
        plain = sc.plain()
        plain["hpd"] = sorted(plain["hpd"] + plain["hpd44"])     # one right hand for the counterpoint check
        for n, v in plain.items():
            print(n, len(v), "notes", NAME(min(p for *_, p in v)), NAME(max(p for *_, p in v)), "ends", max(t + d for t, d, p in v))
        check({k: plain[k] for k in ("vln", "hpd", "vla", "vc")}, ["vln", "hpd", "vla", "vc"], label="whole piece")
    else:
        main()
