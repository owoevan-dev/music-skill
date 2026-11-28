"""What a raw take is made from: the clock, the notes as played, their controllers, bends and slurs, and the few helpers
the synthesis code shares (save_json, digest, file_hash, number, kit_patch).  Split from model.py in 0.11 so that the
synthesis hash (render.SYNTHESIS) covers these and not the project's validation: changing what a project may say about its
mix no longer remakes every take (research/design-0.11.md, after Astra's review d011a).  The code is model.py's as it was;
model.py re-exports every name."""
import bisect
import hashlib
import json
import math
from pathlib import Path

TPQ = 960


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


def number(value, lo, hi, name, integer=False):
    """`value` must be a number in lo..hi; with `integer`, a JSON integer (100, not 100.0, which MIDI cannot carry)."""
    # An integer is compared as it is: math.isfinite turns it into a float, and one past 10**308 (bars of 10**400 in
    # a small file) raised OverflowError instead of this message (found by GPT Pro's fifth review of 0.4.0).
    if (isinstance(value, bool) or not isinstance(value, int if integer else (int, float))
            or (isinstance(value, float) and not math.isfinite(value)) or not lo <= value <= hi):
        show = lambda x: f'{x:g}' if isinstance(x, float) else repr(x) if not isinstance(x, int) or abs(x) < 10 ** 30 else f'an integer of {len(str(abs(x)))} digits'
        hint = f' (write {int(value)}, not {value!r})' if integer and isinstance(value, float) and math.isfinite(value) and value.is_integer() else ''
        raise ValueError(f'{name}: expected {"an integer " if integer else ""}{show(lo)}..{show(hi)}, got {show(value)}{hint}')


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


def kit_patch(t):
    """A sampled part on a kit's bank (128), with or without the `drums` flag; the bank is the patch's where the
    patch names one, the part's own otherwise, as the renderer reads it.  (A synthesizer's `bank` is its exported
    MIDI's and says nothing of its sound.)"""
    return t.get('engine') == 'soundfont' and ((t.get('patch') if isinstance(t.get('patch'), dict) and t['patch'] else None) or t).get('bank', 0) == 128


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
    q = r.get('q', 2.0)
    eps = 1e-9
    # Two events under a 200th of a MIDI tick apart are at one beat (a passage's spans are written to six decimals,
    # and two steps that began together in the piece lay a millionth of a beat apart in it; which came first then
    # chose the tempo of the whole step: the reviews of 0.9).
    together = 5e-6
    # The map is laid by walking its events in order, each at its exact beat: a written tempo point (0), the start of
    # a step of a ritardando (1) and a ritardando's end (2).  (It was laid through places rounded to six decimals: a
    # point on a triplet's beat was read against the tempo before it, and a span's end there was missed: the reviews
    # of 0.9.)  A span may begin before beat 0 or end after the last beat (a passage's, cut from a piece): the step
    # sounding at beat 0 starts there; a span that has ended by then lays nothing.
    events = [(beat, 0, 0, value) for beat, value in tempo]
    for order, (a, b, w) in enumerate(rubato_spans(project)):
        k = 0
        while a + k / 8 < b - together:   # (no step so near its span's own end that the two would be one event)
            beat = a + k / 8
            if min(beat + 1 / 8, b) > eps and beat < total + eps:
                # the step's middle, but never past the span's end: a span shorter than a step was read beyond its
                # own ratio, down to no tempo at all
                events.append((max(beat, 0.0), 1, order, (w, min(1.0, (beat + 1 / 16 - a) / (b - a))), beat))
            k += 1
        events.append((b, 2, order, None))  # back to the written tempo at the boundary
    events.sort(key=lambda e: e[:3])
    out, base, curve, k = {}, tempo[0][1], None, 0
    while k < len(events):
        beat, here = events[k][0], []
        # (a group holds one written point at most: two written points are two tempi, however near; taken for one
        # event, the later was lost and the piece played on at the earlier one's tempo)
        while k < len(events) and events[k][0] <= beat + together and not (events[k][1] == 0 and any(e[1] == 0 for e in here)):
            here.append(events[k])
            k += 1
        point = next((e[3] for e in here if e[1] == 0), None)
        # Of the steps that begin at this beat, the one that sounds: the one that began last (at beat 0 of a
        # passage, steps cut off before it lie here together), and of those begun together the later written span's,
        # as it always was.
        steps = [e for e in here if e[1] == 1]
        last = max((e[4] for e in steps), default=0.0)
        steps = sorted((e for e in steps if e[4] >= last - together), key=lambda e: e[2])
        tail = beat > total - eps        # the last beat: the tail's tempo, which only a written point there sets
        if beat > total + eps or (tail and point is None):
            continue
        if point is not None:
            base = point
        # A written point inside a ritardando changes what the curve multiplies, not the curve: it takes the curve
        # of the step sounding there (off a step, it put the written tempo back until the next one).
        if steps:
            curve = steps[-1][3]
        elif any(e[1] == 2 for e in here):
            curve = None
        out[round(beat, 6)] = base if curve is None else base * (1 + (curve[0] ** q - 1) * curve[1]) ** (1 / q)
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


def performed(track,clock,expressive=True,ends=None):
    """Return actual MIDI-grid onset/release. Trim only overlapping same-key retriggers.
    `performance.offset_ms` shifts a whole part (e.g. sounding earlier to offset slow sample attacks).
    On a part played by string (`strings`, musiclib/strung.py) a note also ends where its string's next note begins,
    as played (such a note is marked `string_ended`).  The whole part's events are the exported MIDI's: one channel,
    on which a second strike of a key ends the first, whatever string it is on.  The audio plays each string by
    itself; what reads how long a note sounds reads `sounded` below.  `ends` (id -> tick) ends a note no later than its tick: a synthesis pass of
    a part played by string holds some of a string's notes, and each must end where the whole part has it end; it is
    an argument and not a field of the project, so that no project can set it."""
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
        if ends is not None and n['id'] in ends:stop=max(tick+1,min(stop,ends[n['id']]))
        notes.append({'id':n['id'],'pitch':n['pitch'],'tick':tick,'end_tick':stop,'velocity':e['velocity'] if expressive else 80})
    def clash(a,b,what,fix):
        beat=b['tick']/TPQ;bar=int(beat//clock.beats_per_bar)+1
        name='C C# D Eb E F F# G Ab A Bb B'.split()[a['pitch']%12]+str(a['pitch']//12-1)  # spelt as review spells them
        return ValueError(f'{track["id"]}: notes {a["id"]} and {b["id"]} {what} {name} near bar {bar} beat {round(beat%clock.beats_per_bar+1,2):g}'
                          f' {"as played" if expressive else "as written"}; {fix}')
    if track.get('strings'):
        on_string={n['id']:n.get('string') for n in track['notes']}
        for s in sorted({v for v in on_string.values() if isinstance(v,int) and not isinstance(v,bool)}):
            group=sorted((n for n in notes if on_string[n['id']]==s),key=lambda n:n['tick'])
            for a,b in zip(group,group[1:]):
                if a['tick']==b['tick']:
                    beat=b['tick']/TPQ;bar=int(beat//clock.beats_per_bar)+1
                    raise ValueError(f'{track["id"]}: notes {a["id"]} and {b["id"]} both strike string {s} near bar {bar} beat {round(beat%clock.beats_per_bar+1,2):g}'
                                     f' {"as played" if expressive else "as written"}; a string sounds one note at a time: move one of them, or put it on another string')
                if a['end_tick']>b['tick']:a['end_tick']=b['tick'];a['string_ended']=True
    unison=' (on a part played by string two strings can hold one pitch when the two notes are written two ticks or more apart)' if track.get('strings') else ''
    for pitch in {n['pitch'] for n in notes}:
        group=sorted((n for n in notes if n['pitch']==pitch),key=lambda n:n['tick'])
        for a,b in zip(group,group[1:]):
            if a['tick']==b['tick']:raise clash(a,b,'both strike','one key cannot be struck twice at once: remove one, or change its pitch or onset'+unison)
            if a['end_tick']>=b['tick']:
                a['end_tick']=b['tick']-1
                if a['end_tick']<=a['tick']:raise clash(a,b,'strike one tick apart on','the first cannot end before the second starts: move them apart or remove one')
                a['retrigger_trimmed']=True
    for n in notes:
        n['start_seconds']=clock.seconds(n['tick']/TPQ)
        n['end_seconds']=clock.seconds(n['end_tick']/TPQ)
    return sorted(notes,key=lambda n:(n['tick'],n['pitch']))


def sounded(track,clock,expressive=True):
    """The part's notes as its audio has them.  For a part played by string each string is a voice of its own
    (strung.passes plays a string's notes alone): its notes are performed string by string, so one pitch held on two
    strings is held on both.  performed() of the whole part is the exported MIDI's one channel, on which the second
    strike of a key ends the first; what reads how long a note sounds reads this instead (an excerpt, the loop's
    guard on a movement, the mix's held spans, the roll, the seam's count, notes.csv: the reviews of 0.9).  Any other
    part: performed().  A sampled part played backwards (`reverse`) sounds over each note's written span, whatever
    its gate, its timing, swing or a later note of its key: render.reversed_notes plays every note by itself.  (An
    excerpt reads such a part by performed(), as it always did: excerpt.py says why.)"""
    if track.get('engine')=='soundfont' and track.get('reverse'):
        played=[{'id':n['id'],'pitch':n['pitch'],'tick':tick_of(n['on']),'end_tick':max(tick_of(n['on'])+1,tick_of(n['on']+n['duration'])),
                 'velocity':track['performance']['notes'][n['id']]['velocity'] if expressive else 80} for n in track['notes']]
        for n in played:n['start_seconds']=clock.seconds(n['tick']/TPQ);n['end_seconds']=clock.seconds(n['end_tick']/TPQ)
        return sorted(played,key=lambda n:(n['tick'],n['pitch']))
    if not track.get('strings'):return performed(track,clock,expressive)
    per={}
    for n in track['notes']:per.setdefault(n.get('string'),[]).append(n)
    out=[]
    for own in per.values():
        ids={n['id'] for n in own}
        out+=performed({**track,'notes':own,'performance':{**track['performance'],'notes':{k:v for k,v in track['performance']['notes'].items() if k in ids}}},clock,expressive)
    return sorted(out,key=lambda n:(n['tick'],n['pitch']))


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
