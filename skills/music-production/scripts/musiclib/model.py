"""Validated score/performance/mix project model; all time units are quarter notes."""
import bisect
import difflib
import hashlib
import json
import math
from pathlib import Path
import re

TPQ = 960
# The bus mix (mix.chain "bus", musiclib.mixbus): buses a track can join and spaces its reverb send can feed.
BUSES = ('drums', 'bass', 'rhythm', 'ensemble', 'lead', 'fx')
SPACES = ('room', 'plate', 'hall', 'church')

def save_json(path, value, new=False):
    """Write JSON whole (musiclib.files.staged): a reader never sees half a file, two writers never share a temporary
    file, and nothing already at a temporary name is written through.  With `new`, an output found free beforehand is
    never put in the place of one that took the name meanwhile (files.publish_new)."""
    from .files import write_json
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, value, new=new)

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def text(value, name):
    """`value` must be text (a JSON string): the brief, decisions, intents, roles and note labels review reads."""
    if not isinstance(value, str):
        raise ValueError(f'{name} is text (a string), got {type(value).__name__}')


def shape(value, kind, name):
    """`value` must be a JSON object (`kind` dict) or a list: the project's frame, checked before its fields are read."""
    if not isinstance(value, kind):
        raise ValueError(f'{name} is {"an object" if kind is dict else "a list"}, got {type(value).__name__}')
    return value


def number(value, lo, hi, name, integer=False):
    """`value` must be a number in lo..hi; with `integer`, a JSON integer (100, not 100.0, which MIDI cannot carry)."""
    # An integer is compared as it is: math.isfinite turns it into a float, and one past 10**308 (bars of 10**400 in
    # a small file) raised OverflowError instead of this message (found by GPT Pro's fifth review of 0.4.0).
    if (isinstance(value, bool) or not isinstance(value, int if integer else (int, float))
            or (isinstance(value, float) and not math.isfinite(value)) or not lo <= value <= hi):
        show = lambda x: f'{x:g}' if isinstance(x, float) else repr(x) if not isinstance(x, int) or abs(x) < 10 ** 30 else f'an integer of {len(str(abs(x)))} digits'
        hint = f' (write {int(value)}, not {value!r})' if integer and isinstance(value, float) and math.isfinite(value) and value.is_integer() else ''
        raise ValueError(f'{name}: expected {"an integer " if integer else ""}{show(lo)}..{show(hi)}, got {show(value)}{hint}')

# Fields each object may carry.  Validation lists any other field as a warning with the nearest known name, since a
# misspelt optional field would otherwise do nothing; free-text fields (a section's `intent`, a note's `phrase`)
# can go on sections and notes, which are not checked.
KNOWN = {
    'project': {'schema', 'title', 'version', 'clock', 'sections', 'tracks', 'mix', 'harmony', 'loop', 'brief', 'decisions',
                'authorship', 'revision_history', 'description', 'comment', 'style'},
    'clock': {'bars', 'meter', 'tempo', 'tail_seconds', 'rubato'},
    'mix': {'chain', 'dynamics', 'loudness', 'target_lufs', 'peak_ceiling_db', 'max_limit_db', 'room_seconds', 'range_lu',
            'mono_below_hz', 'wow_flutter', 'rules', 'c80_db'},
    'track': {'id', 'engine', 'notes', 'performance', 'mix', 'program', 'bank', 'drums', 'range', 'soundfont', 'patch', 'key_map',
              'instrument', 'synth', 'surge', 'kit', 'role', 'name', 'description', 'comment', 'reverse'},
    'performance': {'notes', 'cc', 'cc_mode', 'offset_ms', 'bend', 'bend_range', 'legato', 'bow_change_s', 'bow_ms', 'round_robin',
                    'swing', 'dynamics', 'dynamics_mode'},
    'played note': {'velocity', 'timing_ms', 'gate'},
    'note': {'id', 'on', 'duration', 'pitch', 'phrase', 'articulation', 'comment'},
    'track mix': {'level_dbfs', 'level_mode', 'pan', 'width', 'depth_m', 'facing', 'bus', 'space', 'highpass', 'lowpass', 'eq',
                  'reverb_db', 'delay_db', 'delay_quarters', 'compressor', 'effects', 'automation', 'delay', 'duck', 'filter_sweep',
                  'saturate', 'gate', 'wow_flutter'},
    'legato': {'mode', 'gap_ms', 'max_interval', 'glide_ms', 'max_notes', 'crossfade_ms', 'portamento_ms', 'portamento_from'},
    'synth': {'preset', 'oscillators', 'amp', 'filter', 'filter_env', 'lfo', 'pitch_env', 'arpeggio', 'glide_ms', 'mono', 'drive',
              'velocity_curve', 'gain_db'},
}

# Track and layer ids name files (stems, part MIDIs, layer loops): Windows reserves these names, with any extension.
RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}

def unknown_fields(obj, kind, where, warnings, count=1):
    """Warn about each field of `obj` not in KNOWN[kind], with the nearest known name (`count`: how many objects of a
    part carry it, for notes)."""
    if not isinstance(obj, dict):
        return
    for key in sorted(set(obj) - KNOWN[kind]):
        played = KNOWN['played note'] if kind == 'note' else set()  # velocity, timing and gate written on the score
        near = difflib.get_close_matches(key, sorted(KNOWN[kind] | played), n=1, cutoff=.6)
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

def rubato_spans(project):
    """The ritardandi `clock.rubato` lays over the written tempo, as (from_beat, to_beat, ratio): the last
    `phrase_beats` before each section boundary, the last `final_beats` of the piece, and any written `spans` (an
    excerpt's: the piece's ritardandi that reach into the passage, which may begin before its first beat or end after
    its last)."""
    c = project['clock']
    r = c.get('rubato') or {}
    bpb = c['meter'][0] * 4 / c['meter'][1]
    total = bpb * c['bars']
    spans = []
    if r.get('phrase_beats', 0) > 0:
        for sec in project.get('sections', [])[1:]:
            end = sec['start_bar'] * bpb
            if 0 < end < total:
                spans.append((max(0.0, end - r['phrase_beats']), end, r.get('phrase_ratio', 0.94)))
    if r.get('final_beats', 0) > 0:
        spans.append((max(0.0, total - r['final_beats']), total, r.get('final_ratio', 0.6)))
    return spans + [(float(a), float(b), w) for a, b, w in r.get('spans', [])]

def effective_tempo(project):
    """The tempo map as played: the authored one, with `clock.rubato` applied.  Friberg and Sundberg (1999) model a
    final ritardando on runners stopping: tempo v(x) = (1 + (w^q - 1) x)^(1/q) over the last `final_beats`, x running
    from 0 to 1 and w the tempo reached at the end (`final_ratio`; q = 2 is a constant braking force, 3 a softer one).
    The same curve, shallower, ends each section (`phrase_ratio` over `phrase_beats`): the slight lengthening at a
    phrase boundary the KTH rule system adds (Friberg, Bresin and Sundberg 2006), released at the next downbeat.  The
    curve is laid out in steps of an eighth of a beat."""
    c = project['clock']
    tempo = [[float(b), float(v)] for b, v in c['tempo']]
    r = c.get('rubato')
    if not r:
        return tempo
    total = c['meter'][0] * 4 / c['meter'][1] * c['bars']
    base = lambda b: next(v for beat, v in reversed(tempo) if beat <= b + 1e-9)
    q = r.get('q', 2.0)
    steps = {}
    for a, b, w in rubato_spans(project):
        k = 0
        while a + k / 8 < b - 1e-9:
            beat = a + k / 8
            # A span may begin before beat 0 or end after the last beat (an excerpt's, cut from a piece): the step
            # sounding at beat 0 starts there, and steps after the end are not played.
            if beat + 1 / 8 > 1e-9 and beat < total - 1e-9:
                x = (beat + 1 / 16 - a) / (b - a)
                steps[round(max(beat, 0.0), 6)] = (w, x)
            k += 1
        steps.setdefault(round(b, 6), None)  # back to the written tempo at the boundary
    out = {round(b, 6): v for b, v in tempo}
    for beat, item in sorted(steps.items()):
        if item is None:
            if beat < total:
                out[beat] = base(beat)
            continue
        w, x = item
        out[beat] = base(beat) * (1 + (w ** q - 1) * x) ** (1 / q)
    return [[b, round(v, 4)] for b, v in sorted(out.items())]

class Clock:
    def __init__(self, project):
        c = project['clock']
        self.beats_per_bar = c['meter'][0] * 4 / c['meter'][1]
        self.total_beats = self.beats_per_bar * c['bars']
        tempo = effective_tempo(project)
        self.tempo = tempo
        self.beats = [float(x[0]) for x in tempo]
        # MIDI tempo is integral microseconds; share this exact clock with audio.
        self.spb = [round(60_000_000/x[1])/1_000_000 for x in tempo]
        self.times = [0.0]
        for i in range(1,len(self.beats)):
            self.times.append(self.times[-1] + (self.beats[i]-self.beats[i-1])*self.spb[i-1])
        self.end = self.seconds(self.total_beats)
        self.tail = c.get('tail_seconds', 5)

    def seconds(self, beat):
        i = max(0,bisect.bisect_right(self.beats,beat)-1)
        return self.times[i] + (beat-self.beats[i])*self.spb[i]

    def beat(self, seconds):
        i = max(0,bisect.bisect_right(self.times,seconds)-1)
        return self.beats[i] + (seconds-self.times[i])/self.spb[i]

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
        raise ValueError('Unsupported project schema')
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
    # revise adds to it: as another type it passed here and stopped revise (found by GPT Pro's fifth review of 0.4.0).
    if 'revision_history' in p and not isinstance(p['revision_history'],list):raise ValueError('revision_history is a list of the revisions made')
    c=p['clock'];unknown_fields(c,'clock','clock',warnings);unknown_fields(p['mix'],'mix','mix',warnings)
    number(c['bars'],1,512,'bars',True)
    if not isinstance(c['meter'],list) or len(c['meter'])!=2:raise ValueError('clock.meter is [beats, beat unit], e.g. [3, 4]')
    number(c['meter'][1],2,16,'meter beat unit',True)
    if c['meter'][1] not in (2,4,8,16):
        raise ValueError('Unsupported meter')
    number(c['meter'][0],1,16,'meter numerator',True)
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
        number(s['start_bar'],0,c['bars']-1,f'section {s["id"]} start bar',True)
        if s['id'] in section_ids or s['start_bar']!=cursor:
            raise ValueError('Sections must uniquely cover all bars')
        number(s['bars'],1,c['bars'],'section bars',True)
        if 'intent' in s:text(s['intent'],f'section {s["id"]} intent')
        section_ids.add(s['id'])
        cursor+=s['bars']
    if cursor!=c['bars']:
        raise ValueError('Sections do not cover form')
    if 'loop' in p:
        # The loop runs from the start of `start_bar` (0-based, like sections) to the end of the last bar.
        if not isinstance(p['loop'],dict) or set(p['loop'])-{'start_bar','layers'}:raise ValueError('loop takes start_bar and layers')
        number(p['loop'].get('start_bar',0),0,c['bars']-1,'loop start bar',True)
    if not 1<=len(p['tracks'])<=64:
        raise ValueError('Track count outside bound')
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
    if events>500000:raise ValueError('Too many notes')
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
    for x in shape(t['performance']['notes'],dict,f'{tid}.performance.notes').values():shape(x,dict,f'each entry of {tid}.performance.notes')
    if t['engine'] not in ('soundfont','additive','noise','synth','drum_synth','surge'):
        raise ValueError('Unsupported instrument engine')
    if t['engine']=='synth':
        from . import synth;synth.validate(t)
    if t['engine']=='drum_synth':
        from . import drums;drums.validate(t)
    if t['engine']=='surge':
        from . import surge;surge.validate(t)
    if 'kit' in t and t['engine']!='drum_synth':raise ValueError(f'{t["id"]}: "kit" belongs to engine "drum_synth"')
    if 'synth' in t and t['engine']!='synth':raise ValueError(f'{t["id"]}: "synth" belongs to engine "synth"')
    if 'surge' in t and t['engine']!='surge':raise ValueError(f'{t["id"]}: "surge" belongs to engine "surge"')
    if not isinstance(t.get('drums',False),bool):raise ValueError('drums must be boolean')
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
        number(t['patch'].get('bank',0),0,16383,'patch bank',True);number(t['patch'].get('program',0),0,127,'patch program',True)
    if 'key_map' in t:
        if t['engine']!='soundfont' or not isinstance(t['key_map'],dict) or len(t['key_map'])>128:raise ValueError(f'{t["id"]}: key_map maps MIDI pitches')
        for k,v in t['key_map'].items():
            if not re.fullmatch(r'\d{1,3}',k) or int(k)>127:raise ValueError(f'{t["id"]}: key_map keys are MIDI pitches')
            number(v,0,127,'key_map target',True)
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
    number(t.get('program',0),0,127,'program',True)
    number(t.get('bank',0),0,16383,'bank',True)
    lo,hi=t.get('range',[0,127])
    number(lo,0,127,'range low',True);number(hi,lo,127,'range high',True)
    local_ids=set();events=0;tid=t['id']
    unknown_fields(t,'track',tid,warnings);unknown_fields(t['performance'],'performance',f'{tid}.performance',warnings)
    unknown_fields(t['mix'],'track mix',f'{tid}.mix',warnings);unknown_fields(t['performance'].get('legato'),'legato',f'{tid}.performance.legato',warnings)
    if t['engine']=='synth':unknown_fields(t.get('synth'),'synth',f'{tid}.synth',warnings)
    unknown_note_fields(t['notes'],'note',f'{tid} notes',warnings)
    unknown_note_fields(list(t['performance']['notes'].values()),'played note',f'{tid} performance.notes',warnings)
    if 'role' in t:text(t['role'],f'{tid} role')
    for n in t['notes']:
        if not isinstance(n.get('id'),str) or not 1<=len(n['id'])<=120 or n['id'] in local_ids:
            raise ValueError(f'{tid}: duplicate or invalid note id {n.get("id")!r}')
        for k in ('phrase','articulation','comment'):
            if k in n:text(n[k],f'{tid}/{n["id"]} {k}')
        local_ids.add(n['id']);events+=1;at=f'{tid}/{n["id"]}'
        number(n['on'],0,total-1/TPQ,f'{at} onset (beats)')
        number(n['duration'],1/TPQ,total,f'{at} duration (beats)')
        if n['on']+n['duration']>total+1e-6:
            raise ValueError(f'Note beyond score: {t["id"]}/{n["id"]}')
        number(n['pitch'],lo,hi,f'pitch {t["id"]}/{n["id"]}',True)
        if n['id'] not in t['performance']['notes']:
            raise ValueError(f'Missing performance for {t["id"]}/{n["id"]}')
        perf=t['performance']['notes'][n['id']]
        if 'velocity' not in perf:raise ValueError(f'{at}: performance.notes needs a velocity')
        number(perf['velocity'],1,127,f'{at} velocity',True)
        number(perf.get('timing_ms',0),-100,100,f'{at} timing_ms')
        number(perf.get('gate',1),.05,1.6,f'{at} gate')
    if local_ids!=set(t['performance']['notes']):
        raise ValueError('Performance keys must exactly match score ids')
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
    if mix.get('level_mode','active_rms') not in ('active_rms','peak'):raise ValueError('Unknown reference level mode')
    number(mix.get('delay_quarters',.75),.0625,8,'delay quarter notes')
    number(mix['level_dbfs'],-60,-6,f'{tid} mix.level_dbfs')
    number(mix.get('pan',0),-1,1,'pan');number(mix.get('width',1),0,1,'stereo width')
    if mix.get('depth_m') is not None:number(mix['depth_m'],0,10,'stage depth m')
    from . import production;production.validate(p,t)
    for e in mix.get('effects',[]):
        if not isinstance(e,dict) or e.get('type') not in ('chorus','phaser','bitcrush'):raise ValueError(f'{t["id"]}: effects are chorus, phaser or bitcrush')
        # The phaser is FFmpeg's aphaser, whose speed runs from 0.1 to 2 Hz (ffmpeg -h filter=aphaser): a rate outside
        # it passed here and stopped the render.
        number(e.get('depth',.5),0,1,'effect depth');number(e.get('rate_hz',.5),.1,2,'phaser rate_hz (FFmpeg aphaser: 0.1 to 2 Hz)')
        number(e.get('bits',8),2,16,'bitcrush bits',True);number(e.get('downsample',4),1,32,'bitcrush downsample',True);number(e.get('mix',1),0,1,'bitcrush mix')
    if mix.get('facing','front') not in ('front','back'):raise ValueError(f'{t["id"]}: mix.facing must be "front" or "back"')
    if mix.get('facing','front')=='back' and mix.get('depth_m') is None:raise ValueError(f'{t["id"]}: mix.facing needs mix.depth_m')
    if mix.get('bus') is not None and mix['bus'] not in BUSES:raise ValueError(f'{t["id"]}: mix.bus must be one of '+', '.join(BUSES))
    if mix.get('space') is not None and mix['space'] not in SPACES:raise ValueError(f'{t["id"]}: mix.space must be one of '+', '.join(SPACES))
    number(mix.get('highpass',30),15,3000,'HPF')
    number(mix.get('lowpass',18000),100,22000,'LPF')
    for hz,gain in mix.get('eq',[]):
        number(hz,20,20000,'EQ frequency');number(gain,-12,12,'EQ gain')
    for key in ('reverb_db','delay_db'):
        if mix.get(key) is not None: number(mix[key],-80,0,key)
    if mix.get('compressor'):
        co=mix['compressor'];number(co['threshold_db'],-50,-3,'compressor threshold');number(co['ratio'],1,12,'compressor ratio');number(co['attack_ms'],.1,200,'attack');number(co['release_ms'],5,3000,'release')
    prev=-1
    for beat,db in mix.get('automation',[]):
        number(beat,0,total,f'{tid} automation beat');number(db,-60,12,f'{tid} automation dB')
        if beat<=prev:raise ValueError(f'{tid}: automation points must be ordered')
        prev=beat
    # The notes as played and as written, on the MIDI grid the render and the exports use: a key struck twice at once
    # stops the render, so it is found here, before anything is rendered (an error caught at once costs least).
    for expressive in (True,False):performed(t,clock,expressive)
    return events

def tick_of(beat):
    """The tick a position in beats plays on: the nearest, a half tick to the even one (Python's round()).  A position
    within float error of a tick or a half tick is taken as exactly there first, so one position computed along two
    paths, a piece and its excerpt, lands on one tick: an excerpt starts on a bar line, a whole and even number of
    ticks into the piece (bars are multiples of 120 ticks), and rounding a half to even does not change under such a
    shift."""
    v=beat*TPQ;h=round(v*2)
    if abs(v*2-h)<2e-6:v=h/2
    return round(v)

def swung(b,sw,bar):
    """Where a part's `swing` ({"ratio", "unit"}) plays the written position `b` (beats; `bar` beats to a bar).  Swing
    warps time inside each pair of `unit` notes (0.5 beat swings eighths, 0.25 sixteenths): the first of the pair
    stretches to `ratio` of it, so the off-beat lands late and anything between moves in proportion.  The pairs are
    counted from each bar line, as a drum machine delays the even-numbered steps of the beat (Linn 2013), so every bar
    swings alike; a bar with an odd number of units (eighths in 5/8, quarters in 3/4) plays its last one straight."""
    if not sw:return b
    u,r=2*sw.get('unit',.5),sw['ratio']
    start=math.floor(b/bar+1e-9)*bar;k=math.floor((b-start)/u+1e-9)
    if (k+1)*u>bar+1e-9:return b
    x=(b-start)/u-k
    return start+u*(k+(x*2*r if x<=.5 else r+(x-.5)*2*(1-r)))

def performed(track,clock,expressive=True):
    """Return actual MIDI-grid onset/release. Trim only overlapping same-key retriggers.
    `performance.offset_ms` shifts a whole part (e.g. sounding earlier to offset slow sample attacks)."""
    notes=[];offset=track['performance'].get('offset_ms',0)/1000 if expressive else 0
    sw=track['performance'].get('swing') if expressive else None
    bar=clock.beats_per_bar
    for n in track['notes']:
        e=track['performance']['notes'][n['id']]
        on,off=swung(n['on'],sw,bar),swung(n['on']+n['duration'],sw,bar)
        start=clock.seconds(on) + (e.get('timing_ms',0)/1000 if expressive else 0)+offset
        duration=(clock.seconds(off)-clock.seconds(on))*(e.get('gate',1) if expressive else 1)
        tick=max(0,tick_of(clock.beat(start)))
        stop=max(tick+1,min(round(clock.total_beats*TPQ),tick_of(clock.beat(start+duration))))
        notes.append({'id':n['id'],'pitch':n['pitch'],'tick':tick,'end_tick':stop,'velocity':e['velocity'] if expressive else 80})
    def clash(a,b,what,fix):
        beat=b['tick']/TPQ;bar=int(beat//clock.beats_per_bar)+1
        name='C C# D Eb E F F# G Ab A Bb B'.split()[a['pitch']%12]+str(a['pitch']//12-1)  # spelt as review spells them
        return ValueError(f'{track["id"]}: notes {a["id"]} and {b["id"]} {what} {name} near bar {bar} beat {round(beat%clock.beats_per_bar+1,2):g}'
                          f' {"as played" if expressive else "as written"}; {fix}')
    for pitch in {n['pitch'] for n in notes}:
        group=sorted((n for n in notes if n['pitch']==pitch),key=lambda n:n['tick'])
        for a,b in zip(group,group[1:]):
            if a['tick']==b['tick']:raise clash(a,b,'both strike','one key cannot be struck twice at once: remove one, or change its pitch or onset')
            if a['end_tick']>=b['tick']:
                a['end_tick']=b['tick']-1
                if a['end_tick']<=a['tick']:raise clash(a,b,'strike one tick apart on','the first cannot end before the second starts: move them apart or remove one')
                a['retrigger_trimmed']=True
    for n in notes:
        n['start_seconds']=clock.seconds(n['tick']/TPQ)
        n['end_seconds']=clock.seconds(n['end_tick']/TPQ)
    return sorted(notes,key=lambda n:(n['tick'],n['pitch']))

def cc_events(track):
    """Controller events as performed. `step` holds each value until the next point; `linear`
    ramps continuous controllers between points (1/32-beat resolution, changed values only).
    Switch controllers 64-69 always step.  Default: linear for additive, step otherwise."""
    cc=sorted(track['performance'].get('cc',[]))
    if track['performance'].get('cc_mode','linear' if track['engine']=='additive' else 'step')=='step':return [tuple(x) for x in cc]
    out=[];by={}
    for beat,control,value in cc:by.setdefault(control,[]).append((beat,value))
    for control,pts in by.items():
        if 64<=control<=69 or len(pts)==1:out+=[(b,control,v) for b,v in pts];continue
        last=None
        for (b0,v0),(b1,v1) in zip(pts,pts[1:]):
            steps=max(1,int(round((b1-b0)*32)))
            for k in range(steps):
                v=int(round(v0+(v1-v0)*k/steps))
                if v!=last:out.append((b0+(b1-b0)*k/steps,control,v));last=v
        if pts[-1][1]!=last:out.append((pts[-1][0],control,pts[-1][1]))
    return sorted(out)

def bend_events(track):
    """Pitch bend as performed: [beat, semitones] points ramp linearly (1/64-beat steps, changed values only)
    and become 14-bit wheel values for the part's `bend_range` (semitones at full deflection, default 2)."""
    pts=track['performance'].get('bend',[])
    if not pts:return []
    span=track['performance'].get('bend_range',2)
    wheel=lambda s:max(0,min(16383,8192+round(s/span*8191)))
    out=[];last=None
    for (b0,v0),(b1,v1) in zip(pts,pts[1:]):
        steps=max(1,int(round((b1-b0)*64)))
        for k in range(steps):
            v=wheel(v0+(v1-v0)*k/steps)
            if v!=last:out.append((b0+(b1-b0)*k/steps,v));last=v
    if wheel(pts[-1][1])!=last:out.append((pts[-1][0],wheel(pts[-1][1])))
    return out

def bend_curve(points):
    """A part's `performance.bend` as a curve for curve_at: the wheel rests at 0 until the first point and may jump
    there, as the exported MIDI plays it (curve_at alone would hold the first value from the start)."""
    return [[points[0][0],0.0]]+[list(x) for x in points] if points and points[0][1] else points

def curve_at(points,beat):
    """Value of a [beat, value] curve at `beat`: linear between points, the later of two points on one beat wins."""
    i=bisect.bisect_right([b for b,_ in points],beat)
    if i==0:return points[0][1]
    if i==len(points):return points[-1][1]
    (b0,v0),(b1,v1)=points[i-1],points[i]
    return v0 if b1==b0 else v0+(v1-v0)*(beat-b0)/(b1-b0)

def wheel_events(curves,span,end_beat):
    """Pitch-wheel values for the sum of [beat, semitones] curves, sampled every 1/64 beat and at every point
    (so jumps land on their beat), changed values only."""
    grid=sorted({k/64 for k in range(int(end_beat*64)+1)}|{b for c in curves for b,_ in c})
    wheel=lambda s:max(0,min(16383,8192+round(s/span*8191)))
    out=[];last=None
    for b in grid:
        v=wheel(sum(curve_at(c,b) for c in curves if c))
        if v!=last:out.append((b,v));last=v
    return out

def legato_notes(track,notes,clock):
    """Render-time slurs for a monophonic sampled part.  Notes that follow within `gap_ms`, change pitch, stay within
    `max_interval` of the group's first note and number at most `max_notes` sound as one note at the first pitch;
    returns those notes and a [beat, semitones] curve gliding (`glide_ms`) to each later pitch, as a guitarist's
    hammer-ons and pull-offs or a wind player's slur.  Exported MIDI keeps the written notes."""
    cfg=track['performance']['legato'];gap=cfg.get('gap_ms',40)/1000;glide=cfg.get('glide_ms',25)/1000
    out=[];pts=[];group=[];cur=0.0
    def close():
        nonlocal cur
        if not group:return
        first,last=group[0],group[-1];b0=first['tick']/TPQ
        out.append({**first,'end_tick':last['end_tick'],'end_seconds':last['end_seconds'],'slurred':len(group)})
        pts.extend([[b0,cur],[b0,0.0]] if cur else [[b0,0.0]]);cur=0.0
        for n in group[1:]:
            b=n['tick']/TPQ;a=max(pts[-1][0],clock.beat(max(0,n['start_seconds']-glide)))
            pts.extend([[a,cur],[b,float(n['pitch']-first['pitch'])]]);cur=float(n['pitch']-first['pitch'])
    for n in sorted(notes,key=lambda n:n['tick']):
        if (group and n['start_seconds']-group[-1]['end_seconds']<=gap and n['pitch']!=group[-1]['pitch']
                and abs(n['pitch']-group[0]['pitch'])<=cfg.get('max_interval',5) and len(group)<cfg.get('max_notes',4)):
            group.append(n)
        else:
            close();group=[n]
    close()
    # A slurred note sounds at its group's first pitch, so two groups can meet on one key: the earlier one's note-off
    # would then silence the later one (a synthesizer releases every voice on that key).  Trim as performed() does.
    for pitch in {n['pitch'] for n in out}:
        same=sorted((n for n in out if n['pitch']==pitch),key=lambda n:n['tick'])
        for a,b in zip(same,same[1:]):
            if a['end_tick']>=b['tick']:
                a['end_tick']=b['tick']-1;a['end_seconds']=clock.seconds(a['end_tick']/TPQ);a['retrigger_trimmed']=True
    return out,pts

def load_project(path):
    path=Path(path)
    from .files import MAX_PROJECT, loads
    if path.stat().st_size>MAX_PROJECT:raise ValueError(f'Project exceeds size limit ({MAX_PROJECT // 1_000_000} MB)')
    p=loads(path.read_text(encoding='utf-8'))
    validate(p)
    return p
