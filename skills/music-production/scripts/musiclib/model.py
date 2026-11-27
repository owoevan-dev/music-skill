"""Validated score/performance/mix project model; all time units are quarter notes."""
import bisect
import difflib
import hashlib
import json
import math
from pathlib import Path
import re
from .files import id_fault, one_line, path_limit_hint
# The raw takes' primitives live in played.py (0.11); they are re-exported here for every caller.
from .played import (TPQ, Clock, bend_curve, bend_events, cc_events, curve_at, digest, effective_tempo,  # noqa: F401
                     file_hash, kit_patch, legato_notes, number, performed, rubato_spans, save_json, sounded, swung,
                     tick_of, wheel_events)

# Effects a part takes in mix.effects (0.8 step 1.3: a stated limit, CWE-770; the most any project held was one).
MAX_EFFECTS = 8
# The types mix.effects takes: the first three since 0.7, tremolo and flanger since 0.11 (FFmpeg's, measured smooth on a held
# tone before they were offered: research/effects-0.11/ffmpeg-filter-check.md; FFmpeg's vibrato was not offered).
EFFECT_TYPES = ('chorus', 'phaser', 'bitcrush', 'tremolo', 'flanger')
# The shapes an eq band may take as an object (0.11); a [Hz, dB] pair keeps its meaning, a peak of width Q 1.
EQ_TYPES = ('peak', 'low_shelf', 'high_shelf', 'notch')
# The bus mix (mix.chain "bus", musiclib.mixbus): buses a track can join and spaces its reverb send can feed.
BUSES = ('drums', 'bass', 'rhythm', 'ensemble', 'lead', 'fx')
SPACES = ('room', 'plate', 'hall', 'church')


def key_map_pitches(tid, key_map):
    """A part's key_map as {written pitch: key played}, read one way by validate, the builder and the render: each key a
    MIDI pitch written as text without leading zeros ("36"), each value a MIDI key.  A key that was no text stopped re
    with a TypeError (the whole review of 0.8), and "048" passed validate and the builder while the render, which looks
    a note up as "48", left it unmapped (the review of 0.8.0)."""
    if not isinstance(key_map, dict) or len(key_map) > 128:
        raise ValueError(f'{tid}: key_map maps MIDI pitches written as text to MIDI keys, e.g. {{"36": 48}}')
    out = {}
    for k, v in key_map.items():
        if not isinstance(k, str) or not re.fullmatch(r'0|[1-9][0-9]{0,2}', k) or int(k) > 127:
            raise ValueError(f'{tid}: key_map key {k!r}: a MIDI pitch written as text without leading zeros, e.g. {{"36": 48}}')
        number(v, 0, 127, f'{tid} key_map value of {k!r}', True)
        out[int(k)] = v
    return out


def text(value, name):
    """`value` must be text (a JSON string): the brief, decisions, intents, roles and note labels review reads."""
    if not isinstance(value, str):
        raise ValueError(f'{name} is text (a string), got {type(value).__name__}')


def shape(value, kind, name):
    """`value` must be a JSON object (`kind` dict) or a list: the project's frame, checked before its fields are read."""
    if not isinstance(value, kind):
        raise ValueError(f'{name} is {"an object" if kind is dict else "a list"}, got {type(value).__name__}')
    return value


def check_meter(meter):
    """A meter is [beats, beat unit]: 1-16 beats of a half, quarter, eighth or sixteenth note (validate, and the
    builder before it divides by the unit)."""
    if len(meter)!=2:raise ValueError('clock.meter is [beats, beat unit], e.g. [3, 4]')
    number(meter[1],2,16,'meter beat unit',True)
    if meter[1] not in (2,4,8,16):
        raise ValueError(f'Unsupported meter {list(meter)}: the beat unit is 2, 4, 8 or 16, as in [3, 4] or [6, 8]')
    number(meter[0],1,16,'meter numerator',True)


# Fields each object may carry.  Validation lists any other field as a warning with the nearest known name, since a
# misspelt optional field would otherwise do nothing; free-text fields (a section's `intent`, a note's `phrase`)
# can go on sections and notes, which are not checked.
KNOWN = {
    'project': {'schema', 'title', 'version', 'clock', 'sections', 'tracks', 'mix', 'harmony', 'loop', 'brief', 'decisions',
                'authorship', 'revision_history', 'description', 'comment', 'style', 'plan', 'association'},
    'association': {'source', 'seed', 'count', 'list_words', 'list_sha256', 'words', 'whole', 'gives', 'none', 'reason', 'comment'},
    'association gives': {'level', 'what', 'where'},
    'plan': {'identity', 'high_point', 'sections', 'comment', 'passage'},
    'plan high point': {'section', 'means'},
    'plan section': {'section', 'sounds', 'leads', 'answers', 'register', 'harmony', 'dynamics', 'differs', 'comment'},
    'clock': {'bars', 'meter', 'tempo', 'tail_seconds', 'rubato'},
    'mix': {'chain', 'dynamics', 'loudness', 'target_lufs', 'peak_ceiling_db', 'max_limit_db', 'room_seconds', 'range_lu',
            'mono_below_hz', 'wow_flutter', 'rules', 'c80_db', 'headphones'},
    'track': {'id', 'engine', 'notes', 'performance', 'mix', 'program', 'bank', 'drums', 'range', 'soundfont', 'patch', 'key_map',
              'instrument', 'synth', 'surge', 'kit', 'role', 'name', 'description', 'comment', 'reverse', 'strings'},
    'performance': {'notes', 'cc', 'cc_mode', 'offset_ms', 'bend', 'bend_range', 'legato', 'bow_change_s', 'bow_ms', 'round_robin',
                    'swing', 'dynamics', 'dynamics_mode'},
    'played note': {'velocity', 'timing_ms', 'gate'},
    'note': {'id', 'on', 'duration', 'pitch', 'phrase', 'articulation', 'comment', 'string', 'mute'},
    'track mix': {'level_dbfs', 'level_mode', 'pan', 'width', 'depth_m', 'facing', 'bus', 'space', 'highpass', 'lowpass', 'eq',
                  'reverb_db', 'delay_db', 'delay_quarters', 'compressor', 'effects', 'automation', 'delay', 'duck', 'filter_sweep',
                  'saturate', 'gate', 'wow_flutter', 'move', 'amp', 'around', 'noise_gate', 'surge_fx'},
    'noise gate': {'threshold_db', 'range_db', 'attack_ms', 'release_ms', 'comment'},
    'eq band': {'type', 'hz', 'db', 'q', 'comment'},
    'surge fx': {'type', 'params', 'comment'},
    'legato': {'mode', 'gap_ms', 'max_interval', 'glide_ms', 'max_notes', 'crossfade_ms', 'portamento_ms', 'portamento_from'},
    'synth': {'preset', 'oscillators', 'amp', 'filter', 'filter_env', 'lfo', 'pitch_env', 'arpeggio', 'glide_ms', 'mono', 'drive',
              'velocity_curve', 'gain_db'},
}

# The words a plan compares a section by (schema.md, plan; musiclib/plan.py reads them against the score).
PLAN_WORDS = {'register': ('higher', 'lower', 'same'), 'harmony': ('faster', 'slower', 'same'),
              'dynamics': ('louder', 'softer', 'same')}


def association_shape(a, warnings):
    """The frame of a project's `association`: words as text, the whole as text, what it gave as a list of
    {level, what, where}.  Whether the whole holds every word is for a reader, not for a check."""
    shape(a, dict, 'association')
    unknown_fields(a, 'association', 'association', warnings)
    words = shape(a.get('words', []), list, 'association.words')
    if len(words) > 64:
        raise ValueError('association.words: at most 64')
    for w in words:
        text(w, 'each of association.words')
    for key in ('whole', 'none', 'reason', 'source'):
        if key in a:
            text(a[key], f'association.{key}')
    gives = shape(a.get('gives', []), list, 'association.gives')
    if len(gives) > 64:
        raise ValueError('association.gives: at most 64')
    for g in gives:
        shape(g, dict, 'each of association.gives')
        unknown_fields(g, 'association gives', 'association.gives', warnings)
        for key in ('level', 'what', 'where'):
            if key in g:
                text(g[key], f'association.gives.{key}')


def plan_shape(plan, warnings):
    """A plan's frame: text where text belongs, lists of part names, one of its three words for each comparison.
    That a section or a part it names exists is not checked here: a plan is written before the notes and may name
    what the score does not have yet, and review says so (musiclib/plan.py)."""
    shape(plan, dict, 'plan')
    unknown_fields(plan, 'plan', 'plan', warnings)
    if 'identity' in plan:
        text(plan['identity'], 'plan.identity')
    if 'high_point' in plan:
        hp = shape(plan['high_point'], dict, 'plan.high_point')
        unknown_fields(hp, 'plan high point', 'plan.high_point', warnings)
        for key in ('section', 'means'):
            if key in hp:
                text(hp[key], f'plan.high_point.{key}')
    if 'outside_passage' in plan:
        # A passage cut by a form of excerpt.py that no version shipped (one commit of 0.7's development): its plan
        # holds part of the piece's and no record of where it was cut, and read as a plan it is asked for what the
        # cut took away.  What it lacks is not in it, so it is refused, with what to do.
        raise ValueError('plan.outside_passage: this passage was cut by an unreleased form of excerpt.py, which kept part of the '
                         'piece\'s plan. Cut it again from the piece with this version (excerpt.py), or take `plan` out of this '
                         'project; the piece\'s own plan is in the piece.')
    if 'passage' in plan:                # written by excerpt.py: the project is these bars of the piece the plan is of
        cut = shape(plan['passage'], dict, 'plan.passage')
        for key in ('first_bar', 'bars'):
            if not isinstance(cut.get(key), int) or isinstance(cut.get(key), bool) or cut[key] < 1:
                raise ValueError(f'plan.passage.{key}: a whole number of bars, 1 or more (excerpt.py writes it)')
    seen = set()
    sections = shape(plan.get('sections', []), list, 'plan.sections')
    if len(sections) > 512:
        raise ValueError('plan.sections: at most 512')
    for s in sections:
        shape(s, dict, 'each section of the plan')
        if not isinstance(s.get('section'), str) or not s['section']:
            raise ValueError('each section of the plan names its `section` (the id of a section of the piece)')
        where = f'plan section {s["section"]}'
        if s['section'] in seen:
            raise ValueError(f'{where}: planned twice')
        seen.add(s['section'])
        unknown_fields(s, 'plan section', where, warnings)
        for key in ('sounds', 'answers'):
            if key in s:
                if len(shape(s[key], list, f'{where} {key}')) > 128:
                    raise ValueError(f'{where} {key}: at most 128 parts')
                for part in s[key]:
                    text(part, f'{where} {key}: each part')
        for key in ('leads', 'differs'):
            if key in s:
                text(s[key], f'{where} {key}')
        if 'register' in s:
            for part, word in shape(s['register'], dict, f'{where} register').items():
                if word not in PLAN_WORDS['register']:
                    raise ValueError(f'{where} register of {part}: one of {", ".join(PLAN_WORDS["register"])}, got {word!r}')
        for key in ('harmony', 'dynamics'):
            if key in s and s[key] not in PLAN_WORDS[key]:
                raise ValueError(f'{where} {key}: one of {", ".join(PLAN_WORDS[key])}, got {s[key]!r}')


# Track and layer ids name files (stems, part MIDIs, layer loops): Windows reserves these names, with any extension.
RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}

GUESSED = {('track mix', 'mode'): 'level_mode', ('track mix', 'amplifier'): 'amp', ('track mix', 'amps'): 'amp', ('track mix', 'movement'): 'move',
           ('track mix', 'motion'): 'move', ('track mix', 'moves'): 'move', ('track mix', 'mov'): 'move',
           ('track mix', 'azimuth'): 'around', ('track mix', 'angle'): 'around', ('track mix', 'direction'): 'around', ('track mix', 'arround'): 'around',
           ('track mix', 'orbit'): 'around'}
# Short names that are near many words (`ramp`, `map`, `mode`, `more`): in a part's mix they are offered only for the
# guesses above (a synthesizer's own `amp` is offered for a misspelling as before).
NOT_GUESSED = {('track mix', 'amp'), ('track mix', 'move'), ('track mix', 'around')}


def unknown_fields(obj, kind, where, warnings, count=1):
    """Warn about each field of `obj` not in KNOWN[kind], with the nearest known name (`count`: how many objects of a
    part carry it, for notes)."""
    if not isinstance(obj, dict):
        return
    for key in sorted(set(obj) - KNOWN[kind]):
        played = KNOWN['played note'] if kind == 'note' else set()  # velocity, timing and gate written on the score
        # A name an agent guessed for a field that has another (the nearest by spelling would mislead: `mode` in a
        # part's mix is nearer to `move` than to `level_mode`, which is what it was written for).
        near = [GUESSED[kind, key]] if (kind, key) in GUESSED else difflib.get_close_matches(key, sorted((KNOWN[kind] | played) - {name for where, name in NOT_GUESSED if where == kind}), n=1, cutoff=.6)
        hint = (' (it belongs in performance.notes)' if key in played
                else f' (did you mean {near[0]!r}? that belongs in performance.notes)' if near and near[0] in played
                else f' (did you mean {near[0]!r}?)' if near else '')
        warnings.append(f'{where}: unknown field {key!r}' + hint + (f' on {count} notes' if count > 1 else '') + '; it has no effect')

def unknown_note_fields(notes, kind, where, warnings):
    """One warning per unknown field of a part's notes, however many notes carry it."""
    seen = {}
    for n in notes:
        if isinstance(n, dict):
            for key in set(n) - KNOWN[kind]:
                seen[key] = seen.get(key, 0) + 1
    for key, count in sorted(seen.items()):
        unknown_fields({key: None}, kind, where, warnings, count)


def validate(p):
    """Check a project; returns its size and `warnings` (unknown fields).  A missing field is reported with its place,
    and so is a field of another JSON type where an object or a list belongs (shape); any other field of the wrong
    type is refused as that.  A project that was a list, or a list where the clock, the mix, a track or its notes
    belong, raised AttributeError or TypeError and stopped the command (found by CI on Python 3.14, which parsed a
    deeply nested list that older Pythons refused)."""
    shape(p, dict, 'A project')
    try:
        return _validate(p)
    except KeyError as e:
        raise ValueError(f'missing field {e}') from None
    except (TypeError, AttributeError) as e:
        raise ValueError(f'a field has the wrong type ({e})') from None

def _validate(p):
    warnings = []
    if p.get('schema') != 'music-production/v1':
        raise ValueError(f'Unsupported project schema {p.get("schema")!r}: a project says "schema": "music-production/v1"')
    for k, kind in (('clock', dict), ('mix', dict), ('sections', list), ('tracks', list)):
        if k in p:shape(p[k], kind, k)
    for s in p.get('sections', []):shape(s, dict, 'each section')
    for t in p.get('tracks', []):shape(t, dict, 'each track')
    if not isinstance(p.get('title'),str) or not 1<=len(p['title'])<=200:
        raise ValueError('Title required')
    unknown_fields(p,'project','project',warnings)
    # The text the review reads (schema.md): a brief, decisions as a list of text.  Another type passed and stopped
    # review (found by GPT Pro's third review of 0.4.0).
    if 'brief' in p:text(p['brief'],'brief')
    # The style on the style maps: an entry, or a primary entry with entries borrowed for some axes (styles.py).
    if 'style' in p:
        from .styles import parse
        parse(p['style'])
    if 'decisions' in p:
        if not isinstance(p['decisions'],list):raise ValueError('decisions is a list of text')
        for d in p['decisions']:text(d,'each decision')
    if 'plan' in p:plan_shape(p['plan'],warnings)
    if 'association' in p:association_shape(p['association'],warnings)
    # revise adds to it: as another type it passed here and stopped revise (found by GPT Pro's fifth review of 0.4.0).
    if 'revision_history' in p and not isinstance(p['revision_history'],list):raise ValueError('revision_history is a list of the revisions made')
    c=p['clock'];unknown_fields(c,'clock','clock',warnings);unknown_fields(p['mix'],'mix','mix',warnings)
    number(c['bars'],1,512,'bars',True)
    if not isinstance(c['meter'],list):raise ValueError('clock.meter is [beats, beat unit], e.g. [3, 4]')
    check_meter(c['meter'])
    number(c.get('tail_seconds',5),1,15,'tail')
    r=c.get('rubato')
    if r is not None:
        if not isinstance(r,dict) or set(r)-{'final_ratio','final_beats','phrase_ratio','phrase_beats','q','spans'}:raise ValueError('clock.rubato takes final_ratio, final_beats, phrase_ratio, phrase_beats, q and spans')
        number(r.get('final_ratio',.6),.3,1,'rubato final ratio');number(r.get('final_beats',0),0,32,'rubato final beats')
        number(r.get('phrase_ratio',.94),.7,1,'rubato phrase ratio');number(r.get('phrase_beats',0),0,8,'rubato phrase beats')
        number(r.get('q',2),1,4,'rubato q')
        spans=r.get('spans',[]);length=c['bars']*c['meter'][0]*4/c['meter'][1]
        if not isinstance(spans,list) or len(spans)>512:raise ValueError('rubato spans: a list of at most 512 [from_beat, to_beat, ratio]')
        for s in spans:
            if not isinstance(s,list) or len(s)!=3:raise ValueError('rubato spans: each is [from_beat, to_beat, ratio]')
            number(s[0],-32,length,'rubato span from beat');number(s[1],0,length+32,'rubato span to beat');number(s[2],.3,1,'rubato span ratio')
            if not 0<s[1]-s[0]<=32:raise ValueError(f'rubato span {s}: it runs forward, over at most 32 beats')
    if not all(isinstance(x,list) and len(x)==2 for x in shape(c['tempo'],list,'clock.tempo')):raise ValueError('clock.tempo is a list of [beat, quarter-note BPM]')
    if not 1<=len(c['tempo'])<=2048 or c['tempo'][0][0]!=0:
        raise ValueError('Tempo map must start at zero')
    total=c['bars']*c['meter'][0]*4/c['meter'][1]
    prev=-1
    for beat,bpm in c['tempo']:
        number(beat,0,total,'tempo beat')
        number(bpm,30,300,'quarter-note BPM')
        if beat<=prev:
            raise ValueError('Tempo map not strictly ordered')
        prev=beat
    clock=Clock(p)
    if clock.end>1800:
        raise ValueError('A project is limited to 30 minutes')
    cursor=0
    section_ids=set()
    for s in p['sections']:
        if not isinstance(s.get('id'),str) or not 1<=len(s['id'])<=64:raise ValueError(f'Section id must be a string of 1-64 characters, got {s.get("id")!r}')
        if (bad:=id_fault(s['id'])):  # 0.8 step 1.6
            raise ValueError(f'Section id {one_line(s["id"])} holds {bad}: a section id is printed in tables and messages, so it holds no control, line-separator or bidirectional formatting character')
        number(s['start_bar'],0,c['bars']-1,f'section {s["id"]} start bar',True)
        # 0.8 step 2.1: which section, and where the gap or the overlap lies
        if s['id'] in section_ids:
            raise ValueError(f'Section id {s["id"]} is used twice: each section has an id of its own')
        if s['start_bar']!=cursor:
            raise ValueError(f'Section {s["id"]} starts at bar {s["start_bar"]}, and the sections before it end at bar {cursor}: '
                             + ('bars are counted from 0, so the first section has "start_bar": 0' if cursor==0 and s['start_bar']==1 else
                                f'bars {cursor} to {s["start_bar"]-1} belong to no section' if s['start_bar']>cursor else
                                f'it overlaps the section before; each section starts where the one before it ends (bar {cursor})'))
        number(s['bars'],1,c['bars'],'section bars',True)
        if 'intent' in s:text(s['intent'],f'section {s["id"]} intent')
        section_ids.add(s['id'])
        cursor+=s['bars']
    if cursor!=c['bars']:
        raise ValueError(f'The sections cover {cursor} bars and clock.bars is {c["bars"]}: '
                         + (f'bars {cursor} to {c["bars"]-1} belong to no section' if cursor<c['bars'] else 'they run past the end'))
    if 'loop' in p:
        # The loop runs from the start of `start_bar` (0-based, like sections) to the end of the last bar.
        if not isinstance(p['loop'],dict) or set(p['loop'])-{'start_bar','layers'}:raise ValueError('loop takes start_bar and layers')
        number(p['loop'].get('start_bar',0),0,c['bars']-1,'loop start bar',True)
    if not 1<=len(p['tracks'])<=64:
        raise ValueError(f'A project has 1 to 64 tracks; this one has {len(p["tracks"])}')
    ids=set(); events=0
    for t in p['tracks']:
        if not isinstance(t.get('id'),str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,47}',t['id']) or t['id'] in ids:
            raise ValueError(f'Invalid or duplicate track id {t.get("id")!r}: lower-case letters, digits and underscores, starting with a letter')
        if t['id'] in RESERVED:raise ValueError(f'Track id {t["id"]!r} is a reserved file name on Windows; choose another')
        ids.add(t['id'])
        try:events+=_track(p,t,c,total,clock,warnings)
        except KeyError as e:
            raise ValueError(f'{t["id"]}: missing field {e}') from None
        except (TypeError,AttributeError) as e:
            raise ValueError(f'{t["id"]}: a field has the wrong type ({e})') from None
    if events>500000:raise ValueError(f'A project holds at most 500,000 notes; this one holds {events:,}')
    if isinstance(p.get('harmony'),list):
        for h in p['harmony']:
            shape(h,dict,'each harmony entry');number(h['bar'],1,c['bars'],'harmony bar',True);number(h.get('beat',0),0,clock.beats_per_bar-1/TPQ,'harmony beat')
            if not isinstance(h.get('symbol'),str) or not 1<=len(h['symbol'])<=40:raise ValueError('harmony entries need a chord symbol')
            number(h.get('transpose_semitones',0),-24,24,'harmony transpose',True)
    if p['mix'].get('chain','room') not in ('room','bus'):raise ValueError('mix.chain must be "room" or "bus"')
    if p['mix'].get('dynamics','glue') not in ('glue','wide'):raise ValueError('mix.dynamics must be "glue" or "wide"')
    # The mix's rules: 1 is the bus chain as 0.5 mixed it (the default, so a project made before is mixed as it was);
    # 2 runs the saturation between resamplers, ends the master in one true-peak limiter and takes a clarity (mixbus.py).
    if p['mix'].get('rules',1) not in (1,2) or isinstance(p['mix'].get('rules',1),bool):raise ValueError('mix.rules must be 1 or 2')
    if p['mix'].get('rules',1)==2 and p['mix'].get('chain')!='bus':raise ValueError('mix.rules 2 needs mix.chain "bus"')
    if 'c80_db' in p['mix']:
        # How near the piece is heard (measure.HALL_C80_DB): -2 to +2 dB is the range Barron (2013) recommends for
        # concert halls; a mix with the reverb of mixed songs sits far on the clear side of it.  The clarity is set
        # on the reverbs' returns, so a project that sends
        # nothing to a reverb cannot be given one: refused here (it was accepted, and the render said nothing of it).
        if p['mix'].get('rules',1)!=2:raise ValueError('mix.c80_db belongs to mix.rules 2')
        if not any(isinstance(t,dict) and isinstance(t.get('mix'),dict) and t['mix'].get('reverb_db') is not None for t in (p.get('tracks') or [])):
            raise ValueError('mix.c80_db sets the clarity of the mix by its reverb, and no part sends to a reverb: give the parts mix.reverb_db, or leave mix.c80_db out')
        number(p['mix']['c80_db'],-5,25,'mix.c80_db')
    if p['mix'].get('dynamics')=='wide' and p['mix'].get('chain')!='bus':raise ValueError('mix.dynamics "wide" needs mix.chain "bus"')
    if p['mix'].get('range_lu') is not None:
        number(p['mix']['range_lu'],3,30,'master loudness range')
        if p['mix'].get('dynamics')!='wide':raise ValueError('mix.range_lu belongs to mix.dynamics "wide"')
        if 'loop' in p:raise ValueError('mix.range_lu changes the level along the piece, so it cannot be used with loop')
    if any(t['mix'].get('depth_m') is not None for t in p['tracks']) and p['mix'].get('chain')!='bus':raise ValueError('mix.depth_m needs mix.chain "bus"')
    layers=p.get('loop',{}).get('layers')
    if layers is not None:
        # Vertical layers of one loop: every part belongs to exactly one layer, so the layers add up to the mix.
        if p['mix'].get('chain')!='bus':raise ValueError('loop.layers need mix.chain "bus"')
        if not isinstance(layers,dict) or not 2<=len(layers)<=8:raise ValueError('loop.layers maps 2-8 layer ids to track ids')
        owner={}
        for lid,members in layers.items():
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,47}',lid) or lid in RESERVED:raise ValueError(f'Invalid layer id {lid!r}')
            if not isinstance(members,list) or not members:raise ValueError(f'layer {lid} needs a list of track ids')
            for tid in members:
                if tid not in ids:raise ValueError(f'layer {lid}: unknown track {tid!r}')
                if tid in owner:raise ValueError(f'track {tid} is in layers {owner[tid]} and {lid}')
                owner[tid]=lid
        missing=sorted(ids-set(owner))
        if missing:raise ValueError('Every track needs a layer; missing: '+', '.join(missing))
        # A bus that compresses or saturates (every bus but fx, unless mix.dynamics is "wide") acts on the sum of its
        # parts: split across layers, each layer's bus acted on its own parts only, and the layers no longer added up
        # to the mix, by 4 dB in the review's case, every check passing (found by GPT Pro's seventh review of 0.4.0).
        if p['mix'].get('dynamics')!='wide':
            from .mixbus import bus_of
            split={}
            for t in p['tracks']:
                b=bus_of(t)
                if b!='fx':split.setdefault(b,set()).add(owner[t['id']])
            for b,where in sorted(split.items()):
                if len(where)>1:raise ValueError(f'loop.layers: the {b} bus compresses its parts together, and they are in layers {", ".join(sorted(where))}, '
                                                 f'which would then not add up to the mix; put them in one layer, give some another bus (mix.bus), or set mix.dynamics "wide"')
    if p['mix'].get('loudness','normal') not in ('normal','loud'):raise ValueError('mix.loudness must be "normal" or "loud"')
    if p['mix'].get('loudness')=='loud' and (p['mix'].get('chain')!='bus' or p['mix'].get('dynamics')=='wide'):raise ValueError('mix.loudness "loud" needs the bus chain without wide dynamics')
    number(p['mix'].get('target_lufs',-16),-30,-8 if p['mix'].get('loudness')=='loud' else -10,'master LUFS')
    from . import ears;ears.validate_project(p)
    if p['mix'].get('mono_below_hz') is not None:
        number(p['mix']['mono_below_hz'],40,250,'mono below Hz')
        if p['mix'].get('chain')!='bus':raise ValueError('mix.mono_below_hz needs the bus chain')
    if p['mix'].get('wow_flutter') is not None:
        from . import production;production.validate_wow(p['mix']['wow_flutter'],'mix')
        if p['mix'].get('chain')!='bus':raise ValueError('mix.wow_flutter needs the bus chain')
    number(p['mix'].get('peak_ceiling_db',-1.6),-8,-1,'master ceiling')
    number(p['mix'].get('max_limit_db',1.5),0,4,'limiter allowance')
    number(p['mix'].get('room_seconds',1.1),.2,4,'room decay')
    return {'tracks':len(ids),'notes':events,'bars':c['bars'],'seconds':round(clock.end+clock.tail,3),'sections':len(section_ids),'warnings':warnings}

def _track(p,t,c,total,clock,warnings):
    """One track's checks (validate); returns its note count."""
    tid=t['id'];shape(t['performance'],dict,f'{tid}.performance');shape(t['mix'],dict,f'{tid}.mix')
    for n in shape(t['notes'],list,f'{tid}.notes'):shape(n,dict,f'each note of {tid}')
    if 'notes' not in t['performance']:  # 0.8 step 2.1: it read as the part's own `notes` missing
        raise ValueError(f'{tid}: performance.notes is missing: a velocity for each note, by its id, e.g. "performance": {{"notes": {{"{tid}_1": {{"velocity": 80}}}}}}')
    for x in shape(t['performance']['notes'],dict,f'{tid}.performance.notes').values():shape(x,dict,f'each entry of {tid}.performance.notes')
    if t['engine'] not in ('soundfont','additive','noise','synth','drum_synth','surge'):
        raise ValueError(f'{tid}: engine {t["engine"]!r} is none of soundfont, additive, noise, synth, drum_synth and surge')
    if t['engine']=='synth':
        from . import synth;synth.validate(t)
    if t['engine']=='drum_synth':
        from . import drums;drums.validate(t)
    if t['engine']=='surge':
        from . import surge;surge.validate(t)
    if 'kit' in t and t['engine']!='drum_synth':raise ValueError(f'{t["id"]}: "kit" belongs to engine "drum_synth"')
    if 'synth' in t and t['engine']!='synth':raise ValueError(f'{t["id"]}: "synth" belongs to engine "synth"')
    if 'surge' in t and t['engine']!='surge':raise ValueError(f'{t["id"]}: "surge" belongs to engine "surge"')
    if not isinstance(t.get('drums',False),bool):raise ValueError(f'{tid}: drums is true or false, got {t.get("drums")!r}')
    if 'reverse' in t:
        # A sampled part whose notes play backwards (render.reversed_notes): one plain render per note, so not with the
        # layered dynamics or crossfade legato, which render the part another way.
        if t['reverse'] is not True or t['engine']!='soundfont':raise ValueError(f'{t["id"]}: reverse is true, on a soundfont part')
        if 'dynamics' in t['performance'] or (t['performance'].get('legato') or {}).get('mode')=='crossfade':
            raise ValueError(f'{t["id"]}: a reverse part takes neither performance.dynamics nor crossfade legato')
        if len(t['notes'])>64:raise ValueError(f'{t["id"]}: a reverse part renders each note on its own; at most 64 notes')
    # Render-side sound selection; the score/MIDI export keeps program, bank and authored pitches.
    if 'soundfont' in t and (t['engine']!='soundfont' or not isinstance(t['soundfont'],str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,47}',t['soundfont'])):
        raise ValueError(f'{t["id"]}: soundfont must name a configured SoundFont (soundfont engine only)')
    if 'patch' in t:
        if t['engine']!='soundfont' or not isinstance(t['patch'],dict) or set(t['patch'])-{'bank','program'}:raise ValueError(f'{t["id"]}: patch takes bank/program')
        number(t['patch'].get('bank',0),0,16383,f'{tid} patch bank',True);number(t['patch'].get('program',0),0,127,f'{tid} patch program',True)
    if 'key_map' in t:
        if t['engine']!='soundfont':raise ValueError(f'{t["id"]}: key_map maps MIDI pitches (soundfont engine only)')
        key_map_pitches(tid,t['key_map'])
    if t['performance'].get('cc_mode','linear' if t['engine']=='additive' else 'step') not in ('step','linear'):
        raise ValueError(f'{t["id"]}: cc_mode must be step or linear')
    number(t['performance'].get('offset_ms',0),-300,300,'track offset ms')
    if t['engine']=='additive':
        cfg=t.get('instrument',{})
        for name,default,lo,hi in [('harmonics',12,1,32),('spectral_tilt',1.25,.7,3),('attack_ms',22,1,500),('release_ms',120,5,2000),('glide_ms',28,0,200),('cutoff_hz',1900,100,12000),('vibrato_depth_cents',14,0,100),('vibrato_rate_hz',5.1,2,9),('vibrato_delay_ms',180,0,1000)]:
            number(cfg.get(name,default),lo,hi,'instrument '+name,integer=name=='harmonics')
        voices=cfg.get('detune_cents',[-5,0,5])
        if not isinstance(voices,list) or not 1<=len(voices)<=7:raise ValueError('Expected 1–7 synth voices')
        for cents in voices:number(cents,-40,40,'detune cents')
        if not isinstance(cfg.get('odd_only',False),bool):raise ValueError('odd_only must be boolean')
    number(t.get('program',0),0,127,f'{tid} program',True)
    number(t.get('bank',0),0,16383,'bank',True)
    lo,hi=t.get('range',[0,127])
    number(lo,0,127,'range low',True);number(hi,lo,127,'range high',True)
    local_ids=set();events=0;tid=t['id'];missing=[]
    unknown_fields(t,'track',tid,warnings);unknown_fields(t['performance'],'performance',f'{tid}.performance',warnings)
    unknown_fields(t['mix'],'track mix',f'{tid}.mix',warnings);unknown_fields(t['performance'].get('legato'),'legato',f'{tid}.performance.legato',warnings)
    if t['engine']=='synth':unknown_fields(t.get('synth'),'synth',f'{tid}.synth',warnings)
    unknown_note_fields(t['notes'],'note',f'{tid} notes',warnings)
    unknown_note_fields(list(t['performance']['notes'].values()),'played note',f'{tid} performance.notes',warnings)
    if 'role' in t:text(t['role'],f'{tid} role')
    if 'name' in t:text(t['name'],f'{tid} name')   # the piano roll's legend draws it (a list stopped it: the third outside review of 0.8)
    for n in t['notes']:
        if not isinstance(n.get('id'),str) or not 1<=len(n['id'])<=120 or n['id'] in local_ids:
            raise ValueError(f'{tid}: duplicate or invalid note id {n.get("id")!r}')
        if (bad:=id_fault(n['id'])):  # 0.8 step 1.6
            raise ValueError(f'{tid}: note id {one_line(n["id"])} holds {bad}: a note id is printed in messages and examples, so it holds no control, line-separator or bidirectional formatting character')
        for k in ('phrase','articulation','comment'):
            if k in n:text(n[k],f'{tid}/{n["id"]} {k}')
        local_ids.add(n['id']);events+=1;at=f'{tid}/{n["id"]}'
        number(n['on'],0,total-1/TPQ,f'{at} onset (beats)')
        number(n['duration'],1/TPQ,total,f'{at} duration (beats)')
        if n['on']+n['duration']>total+1e-6:
            raise ValueError(f'{at}: the note ends at beat {n["on"]+n["duration"]:g}, past the end of the score at beat {total:g} '
                             f'({c["bars"]} bars): shorten it, or add bars')
        number(n['pitch'],lo,hi,f'pitch {t["id"]}/{n["id"]}',True)
        if n['id'] not in t['performance']['notes']:
            missing.append(n['id']);continue  # all of them reported at once, below (0.8 step 2.1)
        perf=t['performance']['notes'][n['id']]
        if 'velocity' not in perf:raise ValueError(f'{at}: performance.notes needs a velocity')
        number(perf['velocity'],1,127,f'{at} velocity',True)
        number(perf.get('timing_ms',0),-100,100,f'{at} timing_ms')
        number(perf.get('gate',1),.05,1.6,f'{at} gate')
    if missing:
        raise ValueError(f'{tid}: {len(missing)} note{"s" if len(missing)!=1 else ""} without an entry in performance.notes '
                         f'({", ".join(missing[:5])}{", ..." if len(missing)>5 else ""}): add one for each, e.g. "{missing[0]}": {{"velocity": 80}}')
    if local_ids!=set(t['performance']['notes']):
        extra=sorted(set(t['performance']['notes'])-local_ids)
        raise ValueError(f'{tid}: performance.notes has {len(extra)} entr{"ies" if len(extra)!=1 else "y"} for notes the part does not hold '
                         f'({", ".join(map(str,extra[:5]))}{", ..." if len(extra)>5 else ""}): each entry belongs to a note of the same id')
    if t['engine']=='additive':
        ordered=sorted(t['notes'],key=lambda n:n['on'])
        if any(a['on']+a['duration']>b['on']+1/TPQ for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Additive lead requires a monophonic score; use another track for harmony')
    for beat,control,value in t['performance'].get('cc',[]):
        number(beat,0,total,f'{tid} CC beat');number(control,0,127,f'{tid} CC controller',True);number(value,0,127,f'{tid} CC value',True)
    span=t['performance'].get('bend_range',2);number(span,1,24,'bend range',True)
    bend=t['performance'].get('bend',[])
    if not isinstance(bend,list):raise ValueError(f'{t["id"]}: bend is a list of [beat, semitones]')
    last=0
    for item in bend:
        if not isinstance(item,list) or len(item)!=2:raise ValueError(f'{t["id"]}: bend points are [beat, semitones]')
        number(item[0],0,total,f'{tid} bend beat');number(item[1],-span,span,f'{tid} bend semitones (within bend_range)')
        if item[0]<last:raise ValueError(f'{t["id"]}: bend points must be in time order')
        last=item[0]
    leg=t['performance'].get('legato')
    if leg is not None:
        if t['engine']!='soundfont' or not isinstance(leg,dict):raise ValueError(f'{t["id"]}: legato is a SoundFont-track setting (an object)')
        if leg.get('mode','slur') not in ('slur','crossfade'):raise ValueError(f'{t["id"]}: legato mode is "slur" or "crossfade"')
        number(leg.get('gap_ms',40),0,200,'legato gap ms')
        if leg.get('mode','slur')=='slur':
            number(leg.get('max_interval',5),1,12,'legato max interval',True);number(leg.get('glide_ms',25),0,200,'legato glide ms')
            number(leg.get('max_notes',4),2,16,'legato max notes',True)
            if span<leg.get('max_interval',5)+max((abs(v) for _,v in bend),default=0):
                raise ValueError(f'{t["id"]}: bend_range must cover the legato interval plus the authored bends')
            # A slur plays one line: it glides the part's pitch wheel, which bends every note the part holds, so notes
            # that overlap as written (a chord, a held note under a run) would sound merged or bent together.
            reach,longest=-1.0,None
            for n in sorted(t['notes'],key=lambda n:(n['on'],n['pitch'])):
                if longest is not None and n['on']<reach-1/TPQ:
                    raise ValueError(f'{t["id"]}: slur legato plays one line, and notes {longest["id"]} and {n["id"]} overlap as written; '
                                     'use crossfade legato, or another part for the second voice')
                if n['on']+n['duration']>reach:reach,longest=n['on']+n['duration'],n
        else:
            number(leg.get('crossfade_ms',100),20,400,'legato crossfade ms');number(leg.get('max_interval',12),1,24,'legato max interval',True)
            number(leg.get('portamento_ms',0),0,300,'legato portamento ms');number(leg.get('portamento_from',.6),.2,1,'legato portamento from')
            if leg.get('max_interval',12)>12 and leg.get('portamento_ms',0):raise ValueError(f'{t["id"]}: portamento covers intervals up to 12 semitones')
    perf=t['performance']
    if perf.get('bow_change_s') is not None:
        number(perf['bow_change_s'],2,12,'bow change seconds');number(perf.get('bow_ms',60),20,200,'bow change ms')
        if (leg or {}).get('mode')!='crossfade':raise ValueError(f'{t["id"]}: bow changes need crossfade legato')
    if perf.get('round_robin') not in (None,True,False):raise ValueError(f'{t["id"]}: round_robin is true or false')
    if perf.get('swing') is not None:
        if not isinstance(perf['swing'],dict) or 'ratio' not in perf['swing'] or set(perf['swing'])-{'ratio','unit'}:raise ValueError(f'{t["id"]}: swing takes ratio and optional unit')
        number(perf['swing']['ratio'],.5,.8,'swing ratio')
        if perf['swing'].get('unit',.5) not in (.25,.5,1):raise ValueError(f'{t["id"]}: swing unit is 0.25, 0.5 or 1 beat')
    if perf.get('round_robin') and (t['engine']!='soundfont' or t.get('drums')):raise ValueError(f'{t["id"]}: round_robin is for pitched SoundFont parts')
    dyn=t['performance'].get('dynamics')
    if dyn is not None or (leg or {}).get('mode')=='crossfade':
        # Rendered from a bank's dynamic layers (musiclib/layered.py): a pitched SoundFont part on its own keys.
        if t['engine']!='soundfont' or t.get('drums') or t.get('key_map'):raise ValueError(f'{t["id"]}: dynamics and crossfade legato are for pitched SoundFont parts without a key map')
    if t['performance'].get('dynamics_mode','take') not in ('crossfade','take'):raise ValueError(f'{t["id"]}: dynamics_mode must be "crossfade" or "take"')
    if dyn is not None:
        if not isinstance(dyn,list) or not dyn:raise ValueError(f'{t["id"]}: dynamics is a list of [beat, 0-127] points')
        last=0
        for item in dyn:
            if not isinstance(item,list) or len(item)!=2:raise ValueError(f'{t["id"]}: dynamics points are [beat, value]')
            number(item[0],0,total,f'{tid} dynamics beat');number(item[1],0,127,f'{tid} dynamics value')
            if item[0]<last:raise ValueError(f'{t["id"]}: dynamics points must be in time order')
            last=item[0]
        if any(control==1 for _,control,_ in t['performance'].get('cc',[])):raise ValueError(f'{t["id"]}: dynamics is exported as CC1, so the part cannot also write CC1')
    mix=t['mix']
    if mix.get('level_mode','active_rms') not in ('active_rms','peak'):raise ValueError(f'{tid}: mix.level_mode {mix.get("level_mode")!r} is "active_rms" or "peak"')
    number(mix.get('delay_quarters',.75),.0625,8,f'{tid} mix.delay_quarters')
    number(mix['level_dbfs'],-60,-6,f'{tid} mix.level_dbfs')
    number(mix.get('pan',0),-1,1,f'{tid} mix.pan');number(mix.get('width',1),0,1,f'{tid} mix.width')
    if mix.get('depth_m') is not None:number(mix['depth_m'],0,10,f'{tid} mix.depth_m')
    from . import production;production.validate(p,t)
    if 'move' in mix:   # written at all, null included: one of the two forms
        from . import move;move.validate(p,t,total)
    if 'amp' in mix:
        from . import amp;amp.validate(t)
    from . import strung;strung.validate(t)
    from . import ears;ears.validate_track(p,t,total)
    fx=mix.get('effects',[])
    # Counted as listed, repeats too, before each is checked; a list only, so 0.7's other forms keep their outcomes
    # ("" and {} hold no effect; null, false or a number are a field of the wrong type, as before).
    if isinstance(fx,list) and len(fx)>MAX_EFFECTS:
        raise ValueError(f'{t["id"]}: {len(fx)} effects in mix.effects; a part takes at most {MAX_EFFECTS}, applied in the order listed')
    for e in fx:
        kind=e.get('type') if isinstance(e,dict) else None
        if kind not in EFFECT_TYPES:raise ValueError(f'{t["id"]}: effects are '+', '.join(EFFECT_TYPES))
        # Each type's own limits (0.11: until then every field was checked against every type, a chorus's rate against
        # the phaser's).  The phaser is FFmpeg's aphaser, whose speed runs from 0.1 to 2 Hz (ffmpeg -h filter=aphaser): a
        # rate outside it passed here and stopped the render.
        if kind in ('chorus','phaser'):number(e.get('depth',.5),0,1,f'{kind} depth')
        if kind=='phaser':number(e.get('rate_hz',.5),.1,2,'phaser rate_hz (FFmpeg aphaser: 0.1 to 2 Hz)')
        if kind=='bitcrush':
            number(e.get('bits',8),2,16,'bitcrush bits',True);number(e.get('downsample',4),1,32,'bitcrush downsample',True);number(e.get('mix',1),0,1,'bitcrush mix')
        if kind=='tremolo':number(e.get('rate_hz',5),.1,20,f'{tid} tremolo rate_hz');number(e.get('depth',.5),0,1,f'{tid} tremolo depth')
        if kind=='flanger':
            number(e.get('delay_ms',0),0,30,f'{tid} flanger delay_ms');number(e.get('depth_ms',2),0,10,f'{tid} flanger depth_ms')
            number(e.get('rate_hz',.5),.1,10,f'{tid} flanger rate_hz');number(e.get('feedback',0),-.95,.95,f'{tid} flanger feedback');number(e.get('mix',.71),0,1,f'{tid} flanger mix')
    if mix.get('facing','front') not in ('front','back'):raise ValueError(f'{t["id"]}: mix.facing must be "front" or "back"')
    if mix.get('facing','front')=='back' and mix.get('depth_m') is None:raise ValueError(f'{t["id"]}: mix.facing needs mix.depth_m')
    if mix.get('bus') is not None and mix['bus'] not in BUSES:raise ValueError(f'{t["id"]}: mix.bus must be one of '+', '.join(BUSES))
    if mix.get('space') is not None and mix['space'] not in SPACES:raise ValueError(f'{t["id"]}: mix.space must be one of '+', '.join(SPACES))
    number(mix.get('highpass',30),15,3000,'HPF')
    number(mix.get('lowpass',18000),100,22000,'LPF')
    for band in mix.get('eq',[]):
        if isinstance(band,dict):
            # An object (0.11): a peak or a shelf of a given Q, or a notch, which removes its band (FFmpeg's bandreject takes
            # no gain; a partial cut is a peak with a negative db).  Cuts may go deeper than boosts, as resonances are cut.
            unknown_fields(band,'eq band',f'{tid}.mix.eq',warnings)
            if band.get('type') not in EQ_TYPES:raise ValueError(f'{tid}: an eq band object is a '+', '.join(EQ_TYPES))
            number(band.get('hz'),20,20000,f'{tid} EQ {band["type"]} hz');number(band.get('q',1),.1,20,f'{tid} EQ {band["type"]} q')
            if band['type']=='notch':
                if 'db' in band:raise ValueError(f'{tid}: an eq notch removes its band and takes no db; for a partial cut, a peak with a negative db')
            else:number(band.get('db'),-24,12,f'{tid} EQ {band["type"]} db')
        else:
            hz,gain=band;number(hz,20,20000,'EQ frequency');number(gain,-12,12,'EQ gain')
    for key in ('reverb_db','delay_db'):
        if mix.get(key) is not None: number(mix[key],-80,0,key)
    if mix.get('compressor'):
        co=mix['compressor'];number(co['threshold_db'],-50,-3,'compressor threshold');number(co['ratio'],1,12,'compressor ratio');number(co['attack_ms'],.1,200,'attack');number(co['release_ms'],5,3000,'release')
        # 0.11: the knee as a width in dB (FFmpeg's knee is 10^(dB/20), 1 to 8), make-up gain, the share of the compressed
        # signal (parallel compression below 1) and the detector; omitted, FFmpeg's own defaults as before.
        if 'knee_db' in co:number(co['knee_db'],0,18,f'{tid} compressor knee_db')
        if 'makeup_db' in co:number(co['makeup_db'],0,36,f'{tid} compressor makeup_db')
        if 'mix' in co:number(co['mix'],0,1,f'{tid} compressor mix')
        if 'detection' in co and co['detection'] not in ('peak','rms'):raise ValueError(f'{tid}: compressor detection is peak or rms')
    if mix.get('noise_gate') is not None:
        ng=mix['noise_gate']
        if not isinstance(ng,dict):raise ValueError(f'{tid}: mix.noise_gate is an object (threshold_db, range_db, attack_ms, release_ms)')
        unknown_fields(ng,'noise gate',f'{tid}.mix.noise_gate',warnings)
        number(ng.get('threshold_db',-50),-80,0,f'{tid} noise_gate threshold_db');number(ng.get('range_db',-40),-80,0,f'{tid} noise_gate range_db')
        number(ng.get('attack_ms',2),.01,1000,f'{tid} noise_gate attack_ms');number(ng.get('release_ms',120),1,5000,f'{tid} noise_gate release_ms')
    if mix.get('surge_fx') is not None:
        from . import surgefx;surgefx.validate(t,warnings)
    prev=-1
    for beat,db in mix.get('automation',[]):
        number(beat,0,total,f'{tid} automation beat');number(db,-60,12,f'{tid} automation dB')
        if beat<=prev:raise ValueError(f'{tid}: automation points must be ordered')
        prev=beat
    # The notes as played and as written, on the MIDI grid the render and the exports use: a key struck twice at once
    # stops the render, so it is found here, before anything is rendered (an error caught at once costs least).
    for expressive in (True,False):performed(t,clock,expressive)
    return events


def load_project(path):
    path=Path(path)
    from .files import MAX_PROJECT, loads
    # 0.8 step 2.1: what was expected, not the system's message in its own language ("Permission denied" for a folder)
    if not path.exists():raise ValueError(f'No project file at {path}: give the path of a project JSON file'+path_limit_hint(path))
    if path.is_dir():raise ValueError(f'{path} is a folder: give the project JSON file itself (song.json in it, for example)')
    if path.stat().st_size>MAX_PROJECT:raise ValueError(f'Project exceeds size limit ({MAX_PROJECT // 1_000_000} MB)')
    try:data=path.read_bytes()
    except PermissionError:raise ValueError(f'{path} cannot be read: this account has no permission to read it') from None
    p=loads(data)  # UTF-8 with or without a byte order mark, UTF-16 or UTF-32, as files.read_json (0.8 step 2.2)
    validate(p)
    return p
