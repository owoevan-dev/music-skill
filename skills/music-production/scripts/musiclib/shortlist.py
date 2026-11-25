"""MIT. `studio.py sounds` since 0.10 (step 3b, research/design-0.10.md): the catalog search of musiclib.sounds, its words
matched as 0.9.3 matched them, the words of what a held note does (musiclib.motion) matched whole, and `--without`, which
leaves out the patches whose character holds any word given; then spread over the range as sounds.search spreads it.
Here and not in sounds.py, which a cached synthesis depends on (render.SYNTHESIS, through surge.py): a change there would
make every Surge take be synthesized again, and a Surge take is not repeatable."""
from . import sounds, surge


def motion_terms():
    """The words of what a held note does (musiclib.motion), as phrases and their words ("pitch blip", "blip", "pitch"...);
    none is a word of the catalog's older vocabulary."""
    from .motion import WORDS
    return set(WORDS) | {t for w in WORDS for t in w.split()}


def older(character):
    """A patch's character as 0.9.3's catalog held it: the words of a held note, which 0.10 appended, taken off.  A word
    asked for with --character that is not one of those is matched here, inside the text, as sounds.search matches it, so
    it finds what it found in 0.9.3: matched in the whole text, "bright" also found "brightens" and "brightness swings",
    and 526 patches in place of 336 (the Astra review of step 3)."""
    from .motion import WORDS
    return ', '.join(p for p in character.split(', ') if p and p not in WORDS)


def whole(phrases):
    """Phrases and their words, each matched whole: "pitch blip" holds "pitch blip", "pitch" and "blip"."""
    phrases = list(phrases)
    return set(phrases) | {t for p in phrases for t in p.split()}


def held(character):
    """The words of a held note in a patch's character, as whole phrases and their words."""
    from .motion import WORDS
    return whole(p for p in character.split(', ') if p in WORDS)


def unread(entry, word):
    """Whether a patch is not known to lack the held note's `word` (a phrase, or a word of phrases): it has none of the
    phrases the word covers, and for one of them the figure was not read (None, or no measurement: a silent playing gives
    a measurement of Nones, which the Astra review of step 3 found listed by --without decays), or a swing reaches the
    word's line with no rate read, so whether it repeats is not known (a gated vibrato of 86 cents passed --without "pitch
    swings": the Astra review of the whole of 0.10)."""
    from .motion import FIGURES, LINES, RATES
    phrases = [p for p in FIGURES if word == p or word in p.split()]
    have = held(entry.get('character', ''))
    measured = entry.get('measured') or {}
    if have & set(phrases):
        return False
    return any(measured.get(FIGURES[p]) is None or (p in RATES and measured[FIGURES[p]] >= LINES[p] and measured.get(RATES[p]) is None)
               for p in phrases)


def search(role=None, character=(), name=None, source=None, limit=25, everything=False, seed=None, centroid=None, attack=None,
           without=()):
    """sounds.search with the catalog's older words matched as 0.9.3 matched them and the words of a held note matched whole,
    leaving out the patches whose character holds any word of `without`, and those not known to lack a held note's word of
    it (its figure could not be read).  A word, asked for or left out, is checked against the catalog's words as
    sounds.search checks one: an unknown word is refused with the nearest one."""
    asked = [w.strip().lower() for w in character if w.strip()]
    without = [w.strip().lower() for w in without if w.strip()]
    terms = sorted({t for e in surge.catalog().values() for phrase in e.get('character', '').split(', ') if phrase
                    for t in [phrase] + phrase.split()})
    for w in without:
        if w not in terms:
            raise sounds.unknown('--without', w, terms)
    # every match of the other filters and the words (sounds.search checks each word; it matches inside the whole text, which
    # finds every patch 0.9.3 found and more), dark to bright, then the words matched again as said
    every = sounds.search(role, character, name, source, 10 ** 9, everything, None, centroid, attack)
    timed = motion_terms()
    rows = [r for r in every['shown']
            if all(w in held(r['character']) if w in timed else w in older(r['character']) for w in asked)]
    note = every['note']
    if without:
        catalog = surge.catalog()
        lacking = [r for r in rows if not set(without) & whole(p for p in r['character'].split(', ') if p)]   # whole, as 0.10 matched them
        known = [r for r in lacking if not any(unread(catalog.get(r['id'], {}), w) for w in without if w in timed)]
        note += f' {len(rows) - len(known)} left out by --without {", ".join(without)}'
        note += f' ({len(lacking) - len(known)} of them because the figure could not be read).' if len(lacking) > len(known) else '.'
        rows = known
    shown = sounds.spread(rows, limit, seed)
    if len(rows) > len(shown):
        note += (f' {len(shown)} of {len(rows)} matches, spread over the range and the designers'
                 + (" and picked by this piece's seed" if seed is not None else '; pass the piece\'s --seed for its '
                    'own picks') + '; --limit shows more.')
    return {'count': len(rows), 'shown': shown, 'note': note}
