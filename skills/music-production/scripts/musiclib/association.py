"""MIT. The words a piece starts from: a draw, its record, and what review asks about it.

An agent given the same request twice writes much the same piece twice: the request is all it starts from.  So each
piece draws twelve words at random from a list of a thousand (references/association-words.tsv), and the agent links
the request and all twelve into one whole, a scene or a story or a chain of associations, which then decides what the
request left open.  What the request asks for is settled first and the words change none of it.  Single words read one
by one give one model the same associations each time; twelve linked into one whole do not (the trials are in
research/association-0.7 of the project's development records, which the published repository does not hold).

The draw is uniform, without replacement, from a seed taken from the operating system, and it is made once for a
piece: the seed, the list's hash and the words are kept beside the project, so the draw can be made again and a
revision does not draw new words.  A user who gives words of their own has those recorded in place of a draw, and a
user who wants none has that recorded too."""
import hashlib
import json
import os
import random
import secrets

from . import files

LIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'references', 'association-words.tsv')
COUNT, MOST_OWN, LEVELS = 12, 24, 3


def words_of(path=LIST):
    """The list's words, in its order: a tab-separated file whose first line is `word<TAB>category`."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    if lines[0] != 'word\tcategory':
        raise ValueError(f'{path}: not a word list (its first line is `word<TAB>category`)')
    words = [line.split('\t')[0] for line in lines[1:] if line.strip()]
    if len(set(words)) != len(words):
        raise ValueError(f'{path}: a word is listed twice')
    return words


def draw(seed, count=COUNT, path=LIST):
    """`count` of the list's words for this seed: uniform, none twice."""
    words = words_of(path)
    if not 1 <= count <= len(words):
        raise ValueError(f'a draw takes 1 to {len(words)} words')
    return random.Random(seed).sample(words, count)


def _own(text):
    words = [w.strip() for w in text.split(',') if w.strip()]
    if not 1 <= len(words) <= MOST_OWN:
        raise ValueError(f'--own takes 1 to {MOST_OWN} words or short phrases, separated by commas')
    for w in words:
        if len(w) > 60 or any(ord(c) < 32 for c in w):
            raise ValueError('--own: each word or phrase is at most 60 characters of plain text')
    return words


def keep(folder, seed=None, own=None, none=None, path=LIST):
    """Make this piece's record, <folder>/association.json, and return (record, made).  A piece that has one keeps
    it: the record is returned as it is and nothing is drawn (`made` False)."""
    target = os.path.join(folder, 'association.json')
    if os.path.lexists(target):
        if files.linked(target):
            raise ValueError(f'{target} is a link; the record is a file of the project folder itself')
        try:
            record = files.read_json(target)
        except ValueError as error:
            raise ValueError(f'{target} cannot be read as a record of the piece\'s words ({error}). It was changed or cut short '
                             'after it was made. Put it back as it was; or, where the piece has not used its words yet, '
                             'remove the file and run `words` again.') from None
        check(record, target)
        return record, False
    if sum(x is not None for x in (seed, own, none)) > 1:
        raise ValueError('give one of --seed, --own and --none')
    if none is not None:
        record = {'source': 'none', 'reason': str(none)[:400], 'words': []}
    elif own is not None:
        record = {'source': 'user', 'words': _own(own)}
    else:
        seed = secrets.randbits(32) if seed is None else int(seed)
        with open(path, 'rb') as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        record = {'source': 'draw', 'seed': seed, 'count': COUNT, 'list_words': len(words_of(path)), 'list_sha256': digest,
                  'words': draw(seed, COUNT, path)}
    # Written whole beside its place and then given its name, and only while nothing holds that name: a write that
    # failed part way left half a record, which every later run read and refused (the review of 0.7's code, F07).
    with files.staged(target, 'w', encoding='utf-8', newline='\n', new=True) as f:
        json.dump(record, f, indent=1, ensure_ascii=True)
        f.write('\n')
    return record, True


def check(record, target):
    """A record that is there holds what one of the three kinds holds, or ValueError says what it lacks: `{}` was taken
    for a record with words, and `words` that is no list of words stopped with a TypeError (the review, F10)."""
    if not isinstance(record, dict):
        raise ValueError(f'{target}: not a record of the piece\'s words')
    source, words = record.get('source'), record.get('words')
    if source not in ('draw', 'user', 'none'):
        raise ValueError(f'{target}: its "source" is {source!r}; a record says "draw", "user" or "none"')
    if not isinstance(words, list) or not all(isinstance(w, str) and w.strip() for w in words):
        raise ValueError(f'{target}: its "words" is not a list of words')
    if (source == 'none') != (not words):
        raise ValueError(f'{target}: a record of source "none" holds no words, and every other holds some')
    if source == 'draw':
        # A draw says how it was made, and is what its seed draws from the list it names (the second review, R6: a
        # record of one word, or of twelve times one word under a seed, passed for a draw).
        seed, count, digest = record.get('seed'), record.get('count'), record.get('list_sha256')
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise ValueError(f'{target}: a draw records its "seed", a whole number')
        if not isinstance(count, int) or isinstance(count, bool) or count != len(words):
            raise ValueError(f'{target}: a draw records its "count", the number of its words ({len(words)})')
        if len(set(words)) != len(words):
            raise ValueError(f'{target}: a draw holds no word twice')
        if not isinstance(digest, str) or len(digest) != 64 or set(digest) - set('0123456789abcdef'):
            raise ValueError(f'{target}: a draw records "list_sha256", the SHA-256 of the list it was drawn from')
        with open(LIST, 'rb') as f:
            current = hashlib.sha256(f.read()).hexdigest()
        if digest == current and words != draw(seed, count):
            raise ValueError(f'{target}: its words are not what seed {seed} draws from the list it names. The record was '
                             'changed after it was made; put it back as it was. (A piece whose words the user chose records '
                             '"source": "user".)')


def describe(record, made, target):
    if record.get('source') == 'none':
        return f'This piece associates from no words ({record.get("reason") or "no reason given"}). Kept in {target}.'
    head = ('The words of this piece' if made else 'This piece already has its words; they are not drawn again')
    origin = {'draw': f' (drawn, seed {record.get("seed")})', 'user': ' (given by the user)'}.get(record.get('source'), '')
    return (f'{head}{origin}:\n{", ".join(record.get("words", []))}\n'
            f'Kept in {target}. The request comes first; link it and all of these into one whole, and let that whole decide '
            'what the request leaves open (SKILL.md, step 2).')


def questions(p):
    """What review asks of the project's `association`, as (identifier, text)."""
    a = p.get('association')
    if a is None or not (a.get('none') or a.get('words')):
        return [('association.missing',
                 'The project records no words to associate from. Before what the request leaves open is decided, `studio.py words` '
                 'draws twelve words for the piece; the request and all twelve are linked into one whole, which decides what '
                 'is open, and the project keeps the words and the whole (schema.md, association). Record them, or record '
                 '`"association": {"none": "<why>"}` where the user asked for none.')]
    if a.get('none'):
        return []
    out = []
    if a.get('words') and not a.get('whole'):
        out.append(('association.whole',
                    'The project keeps its words and not the whole made of them. Write, in `association.whole`, the one scene, '
                    'story or chain that holds the request and every word; single words taken one by one are not it.'))
    gives = a.get('gives') or []
    levels = {g.get('level') for g in gives if isinstance(g, dict) and g.get('level')}
    if a.get('whole') and len(levels) < LEVELS:
        out.append(('association.gives',
                    f'The whole is written; what it gave the music is recorded on {len(levels)} level(s) of it. Say in '
                    f'`association.gives` what it decided on at least {LEVELS} different levels of the music (the form, the '
                    'harmony or key, the melody, the rhythm, the sounds, the mix), each with where it is heard.'))
    return out
