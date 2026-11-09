"""Chord-symbol parsing for review questions (not for generating notes)."""
import re

PCS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
QUALITIES = {
    '': (0, 4, 7), 'maj': (0, 4, 7), 'M': (0, 4, 7), 'm': (0, 3, 7), 'min': (0, 3, 7), '-': (0, 3, 7), '5': (0, 7),
    '6': (0, 4, 7, 9), 'm6': (0, 3, 7, 9), '7': (0, 4, 7, 10), 'maj7': (0, 4, 7, 11), 'M7': (0, 4, 7, 11),
    'm7': (0, 3, 7, 10), 'min7': (0, 3, 7, 10), '-7': (0, 3, 7, 10), 'mMaj7': (0, 3, 7, 11), 'mmaj7': (0, 3, 7, 11),
    '9': (0, 4, 7, 10, 2), 'maj9': (0, 4, 7, 11, 2), 'M9': (0, 4, 7, 11, 2), 'm9': (0, 3, 7, 10, 2),
    'add9': (0, 4, 7, 2), 'madd9': (0, 3, 7, 2), '6/9': (0, 4, 7, 9, 2), '69': (0, 4, 7, 9, 2),
    '11': (0, 4, 7, 10, 2, 5), 'm11': (0, 3, 7, 10, 2, 5), '13': (0, 4, 7, 10, 2, 9), 'maj13': (0, 4, 7, 11, 2, 9),
    'm13': (0, 3, 7, 10, 2, 9), 'sus2': (0, 2, 7), 'sus4': (0, 5, 7), 'sus': (0, 5, 7), '7sus4': (0, 5, 7, 10),
    '7sus': (0, 5, 7, 10), '9sus4': (0, 5, 7, 10, 2), 'dim': (0, 3, 6), 'o': (0, 3, 6), 'dim7': (0, 3, 6, 9),
    'o7': (0, 3, 6, 9), 'm7b5': (0, 3, 6, 10), 'ø': (0, 3, 6, 10), 'ø7': (0, 3, 6, 10), 'aug': (0, 4, 8),
    '+': (0, 4, 8), '7#5': (0, 4, 8, 10), '+7': (0, 4, 8, 10), '7b5': (0, 4, 6, 10), '7b9': (0, 4, 7, 10, 1),
    '7#9': (0, 4, 7, 10, 3), '7#11': (0, 4, 7, 10, 6), 'maj7#11': (0, 4, 7, 11, 6), '7b13': (0, 4, 7, 10, 8),
}

def _pc(name):
    v = PCS[name[0].upper()]
    for ch in name[1:]:
        v += 1 if ch in '#♯' else -1 if ch in 'b♭' else 0
    return v % 12

def parse(symbol, transpose=0):
    """'F#m7/A' -> {'root': 6, 'bass': 9, 'pcs': {...}, 'quality': 'm7'}; None when the quality is unknown.  `pcs`
    includes a slash bass; QUALITIES[quality] gives the chord's own intervals above the root.  A slash starts a bass
    only before a note name, so the quality 6/9 keeps its slash (C6/9, C6/9/E; it was read as a bass of 9 and refused:
    GPT Pro's eighth review of 0.4.0, Y03)."""
    m = re.fullmatch(r'([A-Ga-g][#b♯♭]?)(.*?)(?:/([A-Ga-g][#b♯♭]?))?', symbol.strip().replace('Δ', 'maj'))
    if not m or m.group(2) not in QUALITIES:
        return None
    root = (_pc(m.group(1)) + transpose) % 12
    bass = (_pc(m.group(3)) + transpose) % 12 if m.group(3) else root
    return {'symbol': symbol, 'root': root, 'bass': bass, 'quality': m.group(2),
            'pcs': {(root + i) % 12 for i in QUALITIES[m.group(2)]} | {bass}}

def timeline(project, beats_per_bar):
    """Sorted [(beat, chord or None)] from project['harmony'] entries {bar, beat?, symbol}."""
    entries = project.get('harmony')
    if not isinstance(entries, list):
        return []
    out = [((h['bar'] - 1) * beats_per_bar + h.get('beat', 0), parse(h['symbol'], h.get('transpose_semitones', 0)))
           for h in entries]
    return sorted(out, key=lambda x: x[0])

def chord_at(line, beat):
    current = None
    for start, chord in line:
        if start <= beat + 1e-9:
            current = chord
        else:
            break
    return current
