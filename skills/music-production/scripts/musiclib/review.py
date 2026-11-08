"""Score diagnostics are questions for a musical review, never aesthetic scores."""
import bisect
from collections import Counter, defaultdict
import csv
import heapq
import json
import math
from pathlib import Path
import statistics
from . import files, harmony
from .model import Clock, performed, save_json, validate

FOREGROUND = ('melody', 'countermelody')
NAMES = ('C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B')


def highpass_floor(f0):
    """Where a high-pass keeps a note of fundamental `f0` whole: an octave under it, but not under 15 Hz, the lowest
    `validate` accepts (A0 is 27.5 Hz); with the dB that cutoff still takes from the fundamental."""
    low = max(15.0, f0 / 2)
    return low, 10 * math.log10(1 + (low / f0) ** 4)

def highpass_cut(t):
    """dB a part's high-pass takes from the fundamental of its lowest note, with that note and its frequency.  FFmpeg's
    two-pole Butterworth passes r^4/(1+r^4) of the power at r times its cutoff: 3 dB is lost at the cutoff, 1.5 dB a
    major third above it, 0.3 dB an octave above it; review asks about more than 1.5 dB.  None for parts that do not sound at their written pitch (drums, synthesizers with
    octave oscillators, Surge)."""
    if not t['notes'] or t['engine'] not in ('soundfont','additive') or t.get('drums') or (t.get('patch') or t).get('bank',0)==128:return None
    low=min(n['pitch'] for n in t['notes']);f0=440*2**((low-69)/12)
    return 10*math.log10(1+(t['mix'].get('highpass',30)/f0)**4),low,f0

def where(clock,beat):
    return f'bar {int(beat//clock.beats_per_bar)+1} beat {beat%clock.beats_per_bar+1:g}'

def unpitched(t):
    """Drum and noise parts, and synth parts whose oscillators are all noise (a riser, a reverse cymbal, a fall): their
    notes set a sweep or a hit, not a pitch heard against chords."""
    if t.get('drums') or t['engine'] in ('noise','drum_synth'):return True
    if t['engine']=='synth':
        from .synth import patch_of
        try:oscillators=patch_of(t).get('oscillators') or []
        except (KeyError,ValueError):return False
        return bool(oscillators) and all(o.get('wave')=='noise' for o in oscillators)
    return False

def vertical(p,clock,limit=40):
    """Minor seconds/ninths between a sustained note (>=0.75 beat) and any note of another pitched
    part (or inside one part's chord) overlapping >=0.5 beat.  Major sevenths are not flagged.  Unpitched parts
    (unpitched()) are left out.  The notes are indexed by pitch and onset, so only notes 1, 13, 25... semitones away
    that overlap in time are looked at: the work follows the collisions there are, not the square of the notes, and the
    first `limit` examples by beat are kept while the rest are counted."""
    items=[]
    for t in p['tracks']:
        if unpitched(t):continue
        for n in t['notes']:items.append((n['on'],n['on']+n['duration'],n['pitch'],t['id'],t.get('role') in FOREGROUND))
    by_pitch=defaultdict(list)
    for it in items:by_pitch[it[2]].append(it)
    starts,longest={},{}
    for q,lst in by_pitch.items():
        lst.sort();starts[q]=[x[0] for x in lst];longest[q]=max(x[1]-x[0] for x in lst)
    count=fg=seq=0;pairs=Counter();kept=[]
    for a in items:
        if a[1]-a[0]<.75:continue
        for q in [a[2]+d*s for d in range(1,128,12) for s in (1,-1)]:
            lst=by_pitch.get(q)
            if not lst:continue
            # Notes of that pitch starting before a ends and late enough to still sound when it starts.
            for b in lst[bisect.bisect_left(starts[q],a[0]-longest[q]):bisect.bisect_left(starts[q],a[1])]:
                ov=min(a[1],b[1])-max(a[0],b[0])
                # A pair of two sustained notes is found from both; it counts once, from the earlier one.
                if ov<.5 or (b[1]-b[0]>=.75 and b<a):continue
                count+=1;fg+=a[4] or b[4];pairs[' / '.join(sorted({a[3],b[3]}))]+=1;seq+=1
                beat=max(a[0],b[0])
                heapq.heappush(kept,(-beat,-seq,(a,b,ov)))
                if len(kept)>limit:heapq.heappop(kept)
    found=[]
    for beat,_,(a,b,ov) in sorted(kept,key=lambda k:(-k[0],-k[1])):
        found.append({'at':where(clock,-beat),'beat':round(-beat,4),'parts':sorted({a[3],b[3]}),'pitches':sorted([a[2],b[2]]),'overlap_beats':round(ov,3),'involves_foreground':a[4] or b[4],'same_part':a[3]==b[3]})
    return {'count':count,'foreground_count':fg,'by_parts':dict(pairs.most_common()),'examples':found}

def note_name(pitch):
    return f'{NAMES[pitch%12]}{pitch//12-1}'

STEP=2  # semitones: a half or a whole step; anything wider is a leap
MOTION={None:'a rest',0:'held or repeated',1:'step up',-1:'step down',2:'leap up',-2:'leap down'}

def _outer(notes,top):
    """The highest (top) or lowest note at each onset: the line a listener follows through a melody part, or the line
    a bass part gives the harmony."""
    best={}
    for n in notes:
        k=round(n['on'],4)
        if k not in best or (n['pitch']>best[k]['pitch'] if top else n['pitch']<best[k]['pitch']):best[k]=n
    return [best[k] for k in sorted(best)]

def line_of(t):
    """A part as one line: the top line of a melody or countermelody, the bottom line of a bass part, a part written
    one note at a time (overlapping the next by a quarter beat at most) as it stands; None for a chordal part."""
    if t.get('role') in FOREGROUND:return _outer(t['notes'],True)
    if t.get('role')=='bass':return _outer(t['notes'],False)
    s=sorted(t['notes'],key=lambda n:(n['on'],n['pitch']))
    if all(b['on']-a['on']>1e-6 and a['on']+a['duration']-b['on']<=.25+1e-9 for a,b in zip(s,s[1:])):return s
    return None

def _merge(notes):
    """[pitch, start, end, sounding] events from notes in onset order: a pitch repeated or held on across rests of a beat
    or less is one event, one gesture; `sounding` is the time the pitch sounds in it, its notes' (start, end) joined
    where they overlap, so a rest inside it is not taken for sound and a note struck again over the held pitch is not
    counted twice.  Notes that only meet stay apart: a pitch struck again as the last one ends keeps its attack."""
    out=[]
    for n in notes:
        e=n['on']+n['duration']
        if out and out[-1][0]==n['pitch'] and n['on']-out[-1][2]<=1+1e-9:
            x=out[-1];x[2]=max(x[2],e)
            if n['on']<x[3][-1][1]-1e-9:x[3][-1]=(x[3][-1][0],max(x[3][-1][1],e))
            else:x[3].append((n['on'],e))
        else:out.append([n['pitch'],n['on'],e,[(n['on'],e)]])
    return out

def voices(t):
    """A part's events (_merge), each with the event before and after it in its voice, None across a rest of more than
    a beat: in a line (line_of) its neighbours; in a chordal part the nearest pitch that ends as it starts and the
    nearest that starts as it ends, since successive tones close in pitch are heard as one stream and a separation in
    frequency splits them (Wikipedia, Auditory scene analysis; Huron 2001)."""
    line=line_of(t)
    if line is not None:
        ev=_merge(line)
        return [(x,ev[k-1] if k and x[1]-ev[k-1][2]<=1+1e-9 else None,ev[k+1] if k+1<len(ev) and ev[k+1][1]-x[2]<=1+1e-9 else None) for k,x in enumerate(ev)]
    by=defaultdict(list)
    for n in sorted(t['notes'],key=lambda n:n['on']):by[n['pitch']].append(n)
    ev=sorted((x for v in by.values() for x in _merge(v)),key=lambda x:(x[1],x[0]))
    ends=sorted(ev,key=lambda x:x[2]);end_at=[x[2] for x in ends];start_at=[x[1] for x in ev];out=[]
    for x in ev:
        before=[y for y in ends[bisect.bisect_left(end_at,x[1]-1-1e-9):bisect.bisect_right(end_at,x[1]+.125+1e-9)] if y[1]<x[1]-1e-9]
        after=[y for y in ev[bisect.bisect_left(start_at,x[2]-.125-1e-9):bisect.bisect_right(start_at,x[2]+1+1e-9)] if y[1]>x[1]+1e-9]
        out.append((x,min(before,key=lambda y:(abs(y[0]-x[0]),-y[2]),default=None),min(after,key=lambda y:(abs(y[0]-x[0]),y[1]),default=None)))
    return out

def _motion(a,b):
    """0 held or repeated, +-1 a step up or down, +-2 a leap, None across a rest (no note)."""
    if a is None or b is None:return None
    d=b-a
    return 0 if d==0 else (1 if d>0 else -1)*(1 if abs(d)<=STEP else 2)

def embellishment(approach,departure,continues=False,anticipates=False):
    """The embellishing tone a note outside the chord makes, from its approach and departure (_motion), after Open
    Music Theory's table (Peterson, Embellishing Tones): passing (a step in, a step on), neighbour (a step in, a step
    back), appoggiatura (a leap in, a step back), escape tone (a step in, a leap back), suspension or retardation
    (held in, a step down or up), pedal (held in and held on into the next chord), anticipation (struck at most a beat
    before the chord it belongs to and held into it); 'left by step' for the other notes that move on by step; None
    for a note not resolved by step."""
    if approach==0:
        return 'pedal' if continues else {-1:'suspension',1:'retardation'}.get(departure)
    if continues:return 'anticipation' if anticipates else None
    if departure in (1,-1):
        if approach in (1,-1):return 'passing' if approach==departure else 'neighbour'
        return 'appoggiatura' if approach in (2,-2) and approach*departure<0 else 'left by step'
    return 'escape tone' if departure in (2,-2) and approach in (1,-1) and approach*departure<0 else None

def outside_chord(p,clock,limit=40):
    """Notes outside the written chord in every pitched part, named as embellishing tones (embellishment()).  A note
    is checked where it is struck on a beat or sounds a beat or more in the chord, or is held a beat or more into a
    chord (all of a shorter chord, if that is half a beat or more); a pitch repeated or held on across rests of a beat
    or less is one gesture, approached by itself in a later chord, and a longer rest ends it.  Only the time a pitch
    sounds counts, once where its notes overlap: a chord that falls in a rest is not sounded against.  Lines and voices are found as in voices().  Notes not
    resolved by step are listed: in common practice nearly every embellishing tone lies between notes consonant with
    the bass (Open Music Theory), while rock melodies leave such notes unresolved, mostly in pentatonic verses
    (Temperley 2007)."""
    line=harmony.timeline(p,clock.beats_per_bar)
    if not line:return None
    end=p['clock']['bars']*clock.beats_per_bar
    spans=[]
    for k,(s,c) in enumerate(line):  # a chord restated (the same pitch classes) continues its span
        e=line[k+1][0] if k+1<len(line) else max(end,s)
        if e<=s+1e-9:continue
        if spans and c is not None and spans[-1][2] is not None and spans[-1][2]['pcs']==c['pcs'] and abs(spans[-1][1]-s)<1e-9:spans[-1]=(spans[-1][0],e,spans[-1][2])
        else:spans.append((s,e,c))
    starts=[x[0] for x in spans];unknown=sorted({h['symbol'] for h in p['harmony'] if harmony.parse(h['symbol']) is None})
    tracks={};found=[]
    for t in p['tracks']:
        if not t['notes'] or unpitched(t):continue
        kinds=Counter()
        for (pitch,s0,e0,sounding),before,after in voices(t):
            k=max(bisect.bisect_right(starts,s0+1e-9)-1,0)
            while k<len(spans) and spans[k][0]<e0-1e-9:
                cs,ce,ch=spans[k];k+=1
                if ch is None or ce<=s0+1e-9 or pitch%12 in ch['pcs']:continue
                over=sum(max(0,min(b,ce)-max(a,cs)) for a,b in sounding)
                if over<=1e-9:continue
                held=any(a<cs-1e-9 and b>cs+1e-9 for a,b in sounding)
                first=cs if held else min(a for a,b in sounding if b>cs+1e-9 and a<ce-1e-9)
                if not (over>=min(1,ce-cs)-1e-9 and over>=.5-1e-9 if held else abs(first-round(first))<1e-6 or over>=1-1e-9):continue
                nk=k if k<len(spans) and abs(spans[k][0]-ce)<1e-9 else None
                nxt=spans[nk][2] if nk is not None else None
                later=sum(max(0,min(b,spans[nk][1])-max(a,ce)) for a,b in sounding) if nk is not None else 0
                continues=nxt is not None and later>=min(.5,spans[nk][1]-ce)-1e-9
                approach=0 if s0<cs-1e-9 else _motion(before[0] if before else None,pitch)
                departure=None if continues else _motion(pitch,after[0] if after else None)
                kind=embellishment(approach,departure,continues,continues and pitch%12 in nxt['pcs'] and ce-first<=1+1e-9)
                kinds[kind or 'not resolved by step']+=1
                if kind is None:
                    found.append({'track':t['id'],'role':t.get('role'),'at':where(clock,first),'beat':round(first,4),'pitch':pitch,'note':note_name(pitch),'chord':ch['symbol'],'held_into_chord':held,'approach':MOTION[approach],'departure':'held on' if continues else MOTION[departure]})
        if kinds:tracks[t['id']]={'role':t.get('role'),'outside_chord':dict(kinds)}
    found.sort(key=lambda x:x['beat']);groups={}
    for g,test in (('melody',lambda r:r in FOREGROUND),('bass',lambda r:r=='bass'),('accompaniment',lambda r:r not in FOREGROUND and r!='bass')):
        xs=[x for x in found if test(x['role'])]
        if xs:groups[g]={'count':len(xs),'most_in':Counter(x['track'] for x in xs).most_common(1)[0][0],'first':xs[0]}
    return {'count':len(found),'not_resolved_by_step':groups,'tracks':tracks,'examples':found[:limit],'unparsed_symbols':unknown}

def parallels(p,clock,window=8,doubled_share=.75,limit=40):
    """Two perfect consonances of the same size in a row, fifths or octaves (with unisons), between two lines
    (line_of) moving the same way: both voices go from one note to their next at the same moment, with no rest of
    more than half a beat.  Open Music Theory forbids them in counterpoint, as they fuse the two voices
    (First-Species Counterpoint).  Octaves where the two lines meet at the octave or unison in at least
    `doubled_share` of the `window` attacks they share around them are one line doubled to blend, not two voices
    (climax-and-melody.md, Blend), and are counted apart; a window and share of our choosing."""
    lines={t['id']:ln for t in p['tracks'] if t['notes'] and not unpitched(t) for ln in [line_of(t)] if ln and len(ln)>1}
    ids=sorted(lines);found=[];doubled=Counter()
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            A,B=lines[a],lines[b];at={round(n['on'],3):j for j,n in enumerate(B)}
            shared=[(k,at[round(n['on'],3)]) for k,n in enumerate(A) if round(n['on'],3) in at]
            size=[{7:'fifths',0:'octaves'}.get(abs(A[k]['pitch']-B[j]['pitch'])%12) for k,j in shared]
            joined=lambda L,u:L[u]['on']+L[u]['duration']>=L[u+1]['on']-.5-1e-9
            for m in range(1,len(shared)):
                (k1,j1),(k2,j2)=shared[m-1],shared[m]
                if size[m] is None or size[m]!=size[m-1] or (k2,j2)!=(k1+1,j1+1) or not (joined(A,k1) and joined(B,j1)):continue
                if (A[k2]['pitch']-A[k1]['pitch'])*(B[j2]['pitch']-B[j1]['pitch'])<=0:continue
                around=size[max(0,m-window//2):m+window//2]
                if size[m]=='octaves' and len(around)>=4 and around.count('octaves')>=doubled_share*len(around):
                    doubled[' / '.join((a,b))]+=1;continue
                found.append({'parts':[a,b],'at':where(clock,A[k2]['on']),'beat':round(A[k2]['on'],4),'interval':size[m],'pitches':[[A[k1]['pitch'],B[j1]['pitch']],[A[k2]['pitch'],B[j2]['pitch']]]})
    found.sort(key=lambda x:x['beat'])
    return {'count':len(found),'by_pair':dict(Counter(' / '.join(x['parts']) for x in found).most_common()),'examples':found[:limit],'octaves_in_doublings':dict(doubled.most_common())}

INTERVAL_NAMES={1:'minor second',2:'major second',3:'minor third',4:'major third',5:'perfect fourth',6:'tritone',7:'perfect fifth',8:'minor sixth',9:'major sixth',10:'minor seventh',11:'major seventh',13:'minor ninth',14:'major ninth',15:'minor tenth',16:'major tenth'}

def low_intervals(p,clock,limit=40):
    """Two notes sounding together for half a beat or more, up to a major tenth apart (octaves are not charted), whose
    lower note lies under that interval's low interval limit, where voicings turn muddy (Hoffmann's chart,
    voicing.LOW_INTERVAL_LIMITS); one finding per interval sounding at a moment, whichever parts play it.  The fourth
    or fifth of a power chord (a part's root and fifth, with octaves) is left out, also where another part doubles
    it: rock and metal voice it low (rock-and-metal.md).  As in vertical(), the notes are indexed by pitch and onset: only
    the pitches an interval puts above a note low enough for its limit, and only their notes overlapping it, are looked
    at, not every note of the bars it spans."""
    from .voicing import LOW_INTERVAL_LIMITS
    notes=[];top=max(LOW_INTERVAL_LIMITS.values())
    for t in p['tracks']:
        if unpitched(t):continue
        pcs=defaultdict(set)
        for n in t['notes']:pcs[round(n['on'],4)].add(n['pitch']%12)
        for n in t['notes']:
            c=frozenset(pcs[round(n['on'],4)])
            notes.append((n['on'],n['on']+n['duration'],n['pitch'],t['id'],c if len(c)==2 and max(c)-min(c) in (5,7) else None))
    by_pitch=defaultdict(list)
    for it in notes:by_pitch[it[2]].append(it)
    starts,longest={},{}
    for q,lst in by_pitch.items():
        lst.sort();starts[q]=[x[0] for x in lst];longest[q]=max(x[1]-x[0] for x in lst)
    found={}
    for a in notes:
        if a[2]>=top:continue
        for d,low in LOW_INTERVAL_LIMITS.items():
            q=a[2]+d
            if a[2]>=low or q not in by_pitch:continue
            for b in by_pitch[q][bisect.bisect_left(starts[q],a[0]-longest[q]):bisect.bisect_left(starts[q],a[1])]:
                if min(a[1],b[1])-max(a[0],b[0])<.5-1e-9:continue
                if d in (5,7) and any(x[4] and {a[2]%12,b[2]%12}<=x[4] for x in (a,b)):continue
                at=round(max(a[0],b[0]),4)
                f=found.setdefault((at,a[2],b[2]),{'parts':set(),'at':where(clock,at),'beat':at,'interval':INTERVAL_NAMES[d],'notes':[note_name(a[2]),note_name(b[2])],'limit':note_name(LOW_INTERVAL_LIMITS[d]),'below_limit':LOW_INTERVAL_LIMITS[d]-a[2]})
                f['parts']|={a[3],b[3]}
    found=[{**f,'parts':sorted(f['parts'])} for _,f in sorted(found.items())]
    worst=max(found,key=lambda x:(x['below_limit'],-x['beat']),default=None)
    return {'count':len(found),'by_parts':dict(Counter(' / '.join(x['parts']) for x in found).most_common()),'furthest_below':worst,'examples':found[:limit]}

ARRIVALS=('chorus','hook','drop','climax','peak','summit','final','refrain')

def _arrival(name):
    """A section named as an arrival (ARRIVALS) and not as the lead-in to one: prechorus, pre-chorus, pre_hook and the
    like start with "pre"."""
    n=name.lower()
    return not n.startswith('pre') and any(w in n for w in ARRIVALS)

def _bar_contents(t,bpb):
    """{bar: the part's written notes in it as (position, pitch, length)}; performance (velocity, timing) left out, so
    a bar changes only when its notes do."""
    out=defaultdict(list)
    for n in t['notes']:
        b=int(n['on']//bpb+1e-9);out[b].append((round(n['on']-b*bpb,3),n['pitch'],round(n['duration'],3)))
    return {b:tuple(sorted(v)) for b,v in out.items()}

def _energy(p,clock):
    """Per section: written notes per bar, the parts that play, the mean performed velocity."""
    rows=[]
    for s in p['sections']:
        lo,hi=s['start_bar']*clock.beats_per_bar,(s['start_bar']+s['bars'])*clock.beats_per_bar;parts=[];count=0;vel=[]
        for t in p['tracks']:
            notes=[n for n in t['notes'] if lo<=n['on']<hi]
            if notes:
                parts.append(t['id']);count+=len(notes);vel+=[t['performance']['notes'][n['id']]['velocity'] for n in notes]
        rows.append({'section':s['id'],'bars':s['bars'],'notes_per_bar':round(count/max(s['bars'],1),2),'parts':parts,'mean_velocity':round(statistics.mean(vel),1) if vel else 0})
    return rows

def repetition(p,clock,static_bars=16,pitched_loop_bars=24,percussion_loop_bars=33):
    """Where nothing changes: (1) spans of at least `static_bars` bars in which every part repeats the same block of
    1, 2, 4 or 8 bars note for note; (2) parts that repeat a 1-, 2- or 4-bar cycle unchanged for at least
    `pitched_loop_bars` bars (a pitched part) or `percussion_loop_bars` (a percussion part): dance music is phrased in
    multiples of two bars at several levels, new sounds entering at the downbeats of those phrases (Smith 2021, after
    Snoman 2019), so a loop held past one or two 16-bar phrases is a question; (3) sections that return note for note in every part; (4) arrival sections (named chorus,
    hook, drop, climax, peak, summit, final or refrain, a pre-chorus not counted) thinner than the section before them in at least two of notes
    per bar, parts and velocity; (5) neighbouring sections with the same parts, notes per bar within 10% and velocity
    within 3.  Moderate novelty is liked best (Chmiel and Schubert 2017): questions, not faults."""
    bpb=clock.beats_per_bar;bars=p['clock']['bars']
    contents={t['id']:_bar_contents(t,bpb) for t in p['tracks'] if t['notes']}
    found=[]
    for t in p['tracks']:
        if not t['notes']:continue
        bc=contents[t['id']];best=(0,0,0)
        for b in range(bars):
            if b not in bc:continue
            for period in (1,2,4):
                e=b+period
                while e<bars and e in bc and bc[e]==bc.get(e-period):e+=1
                if e-b>best[0]:best=(e-b,b,period)
        perc=unpitched(t)
        if best[0]>=(percussion_loop_bars if perc else pitched_loop_bars):
            found.append({'track':t['id'],'start':best[1],'end':best[1]+best[0],'cycle_bars':best[2],'percussion':perc})
    part_loops=[]  # parts whose loops cover mostly the same bars are asked about together
    for f in sorted(found,key=lambda x:(x['start'],x['end'])):
        g=next((g for g in part_loops if min(g['end'],f['end'])-max(g['start'],f['start'])>=.75*min(g['end']-g['start'],f['end']-f['start'])),None)
        if g is None:
            part_loops.append({'start':f['start'],'end':f['end'],'tracks':[f['track']],'cycle_bars':{f['cycle_bars']},'percussion':f['percussion']})
        else:
            g['start'],g['end']=min(g['start'],f['start']),max(g['end'],f['end']);g['tracks'].append(f['track']);g['cycle_bars'].add(f['cycle_bars']);g['percussion']=g['percussion'] and f['percussion']
    part_loops=[{'from_bar':g['start']+1,'to_bar':g['end'],'bars':g['end']-g['start'],'tracks':g['tracks'],'cycle_bars':sorted(g['cycle_bars']),'percussion':g['percussion']} for g in part_loops]
    sig=[tuple(contents[k].get(b,()) for k in sorted(contents)) for b in range(bars)]
    static=[];b=0
    while b<bars:
        best=None
        for period in (1,2,4,8):
            if b+period>=bars or not any(sig[b]):continue
            e=b+period
            while e<bars and sig[e]==sig[e-period]:e+=1
            if e-b>=static_bars and (best is None or e-b>best[1]-best[0]):best=(b,e,period)
        if best:
            static.append({'from_bar':best[0]+1,'to_bar':best[1],'bars':best[1]-best[0],'block_bars':best[2]});b=best[1]
        else:b+=1
    returns=[]
    secs=p['sections']
    def section_notes(s):
        lo=s['start_bar'];return {k:tuple((b-lo,c) for b,c in sorted(v.items()) if lo<=b<lo+s['bars']) for k,v in contents.items()}
    for i,s in enumerate(secs):
        for e in secs[:i]:
            if e['bars']==s['bars'] and any(section_notes(s).values()) and section_notes(s)==section_notes(e):
                returns.append({'section':s['id'],'repeats':e['id']});break
    energy=_energy(p,clock);flat=[];weak=[]
    for a,b in zip(energy,energy[1:]):
        lower=(b['notes_per_bar']<a['notes_per_bar'])+(len(b['parts'])<len(a['parts']))+(b['mean_velocity']<a['mean_velocity'])
        if _arrival(b['section']) and not _arrival(a['section']) and lower>=2:
            weak.append({'section':b['section'],'after':a['section'],'notes_per_bar':[a['notes_per_bar'],b['notes_per_bar']],'parts':[len(a['parts']),len(b['parts'])],'mean_velocity':[a['mean_velocity'],b['mean_velocity']]})
        if a['notes_per_bar'] and set(a['parts'])==set(b['parts']) and abs(b['notes_per_bar']/a['notes_per_bar']-1)<.1 and abs(b['mean_velocity']-a['mean_velocity'])<3:
            flat.append({'sections':[a['section'],b['section']],'notes_per_bar':[a['notes_per_bar'],b['notes_per_bar']],'mean_velocity':[a['mean_velocity'],b['mean_velocity']]})
    return {'static_spans':static,'part_loops':part_loops,'literal_returns':returns,'arrivals_thinner_than_before':weak,'sections_alike':flat,'energy':energy}

def _meter(p):
    """The bar's length in quarter notes, its half-bar where the beats divide the bar in two (4/4, 6/8, 12/8; none in
    3/4 or 9/8), and its metric levels: the beat and two levels below it.  A compound meter (6/8, 9/8, 12/8: a numerator
    above 3 divisible by 3, over 8 or 16) beats in dotted notes of three units, each divided in three."""
    num,den=p['clock']['meter'];unit=4/den;bar=num*unit
    compound=num>3 and num%3==0 and den>=8
    beat=3*unit if compound else unit
    return bar,(bar/2 if round(bar/beat)%2==0 else None),((beat,beat/3,beat/6) if compound else (beat,beat/2,beat/4))

def _metric_weight(pos,meter):
    """Metric strength of a position in quarter notes within the bar (_meter): the downbeat 5, the half-bar 4, a beat 3,
    the two levels below the beat 2 and 1, finer 0 (after Longuet-Higgins and Lee 1984)."""
    bar,half,levels=meter
    if abs(pos)<1e-6:return 5
    if half is not None and abs(pos-half)<1e-6:return 4
    for w,step in zip((3,2,1),levels):
        if abs(pos/step-round(pos/step))<1e-6:return w
    return 0

def stiffness(p,clock,block_share=.9,min_chords=8):
    """Where the parts move as blocks: chord parts (three or more pitch classes, power chords left out) that strike and
    release at least `block_share` of their chords together, the voices never moving apart, when the chords are held
    (a median of two beats or more) or keep one length (at least three in four alike); syncopated stabs and comping of
    varied lengths are a rhythm, not stiffness.  Also, per pitched part, the
    share of its attacks that are syncopated (the last attack before a stronger position that is itself left without an
    attack, held over or rested: Longuet-Higgins and Lee 1984; in 6/8, 9/8 and 12/8 the beats are dotted, _meter) and of those that anticipate a downbeat or half-bar by
    an eighth or less, the push of pop, rock and J-pop (Tan, Lustig and Temperley 2019).  Medium syncopation is the most
    groove-inducing (Witek et al. 2014); none at all in melody and accompaniment is asked about, as a question of style."""
    bpb=clock.beats_per_bar;blocks=[];parts={};end=p['clock']['bars']*bpb;meter=_meter(p);_,half,levels=meter
    grids=tuple(sorted({*levels,*(() if half is None else (half,)),bpb}))
    for t in p['tracks']:
        if not t['notes'] or unpitched(t):continue
        by_on=defaultdict(list)
        for n in t['notes']:by_on[round(n['on'],4)].append(n)
        chords=[g for _,g in sorted(by_on.items()) if len({n['pitch']%12 for n in g})>=3]
        if len(chords)>=min_chords:
            share=sum(len({round(n['duration'],3) for n in g})==1 for g in chords)/len(chords)
            lengths=[max(n['duration'] for n in g) for g in chords];median=statistics.median(lengths)
            alike=Counter(round(x,3) for x in lengths).most_common(1)[0][1]/len(lengths)
            if share>=block_share and (median>=2 or alike>=.75):
                blocks.append({'track':t['id'],'role':t.get('role'),'chords':len(chords),'block_share':round(share,3),'median_beats':round(median,3),'one_length_share':round(alike,3)})
        onsets=sorted(by_on);sync=push=0
        for k,on in enumerate(onsets):
            w=_metric_weight(on%bpb,meter);nxt=onsets[k+1] if k+1<len(onsets) else end
            stronger=next((q for q in (math.floor(on/s+1e-9)*s+s for s in grids) if _metric_weight(q%bpb,meter)>w),None)
            if stronger is not None and stronger<end and nxt>stronger+1e-6:
                sync+=1
                if _metric_weight(stronger%bpb,meter)>=4 and stronger-on<=.5+1e-9:push+=1
        parts[t['id']]={'role':t.get('role'),'attacks':len(onsets),'syncopated_pct':round(100*sync/len(onsets),1),'downbeat_pushes_pct':round(100*push/len(onsets),1)}
    lines=[v for v in parts.values() if v['role'] in ('melody','countermelody','harmony','rhythm','bass','texture')]
    no_push=bool(lines) and all(v['downbeat_pushes_pct']==0 for v in lines)
    return {'block_chord_parts':blocks,'parts':parts,'no_pushes_anywhere':no_push}

def transposition(bank,bank_no,program):
    """Key -> semitones between the key and the recorded pitch of the sample that plays it in a preset (the smallest
    among the zones covering the key; coarse tune counts). None when the bank has no such preset."""
    pre=next((x for x in bank['presets'] if x['bank']==bank_no and x['program']==program),None)
    if pre is None:return None
    shift={}
    for pz in pre['zones']:
        if pz['target'] is None:continue
        plo,phi=pz['gens'].get(43,(0,127));inst=bank['instruments'][pz['target']]
        top=next((z['gens'] for z in inst['zones'] if z['target'] is None),{})
        for z in inst['zones']:
            g,smp=z['gens'],z['target']
            if smp is None:continue
            lo,hi=g.get(43,top.get(43,(0,127)))
            root=g.get(58,top.get(58,bank['samples'][smp]['root']));coarse=g.get(51,top.get(51,0))
            for k in range(max(lo,plo),min(hi,phi)+1):
                d=k-root+coarse
                if k not in shift or abs(d)<abs(shift[k]):shift[k]=d
    return shift
def sample_maps(p,config):
    """transposition() for every pitched SoundFont part, reading each configured bank once."""
    from . import audio,sf2
    banks,maps={},{}
    for t in p['tracks']:
        if t['engine']!='soundfont' or t.get('drums') or t.get('key_map'):continue
        _,font=audio.soundfont_for(config,t)
        if font['path'] not in banks:banks[font['path']]=sf2.read(font['path'])
        patch=t.get('patch') or {'bank':t.get('bank',0),'program':t.get('program',0)}
        maps[t['id']]=transposition(banks[font['path']],patch.get('bank',0),patch.get('program',0))
    return maps
def stretched(p,clock,maps,limit=4,examples=40):
    """Notes whose sample is transposed more than `limit` semitones (timbre and vibrato rate change with it), and notes
    no zone covers (silent)."""
    far,silent,by=[],[],defaultdict(lambda:{'notes':0,'worst':None})
    for t in p['tracks']:
        shift=maps.get(t['id'],{})
        if t['id'] in maps and shift is None:silent.append({'track':t['id'],'problem':'preset not in bank'});continue
        for n in t['notes'] if t['id'] in maps else []:
            d=shift.get(n['pitch'])
            if d is None:silent.append({'track':t['id'],'at':where(clock,n['on']),'pitch':n['pitch']})
            elif abs(d)>limit:
                far.append({'track':t['id'],'at':where(clock,n['on']),'pitch':n['pitch'],'semitones':d})
                b=by[t['id']];b['notes']+=1
                if b['worst'] is None or abs(d)>abs(b['worst']['semitones']):b['worst']={'pitch':n['pitch'],'semitones':d,'at':where(clock,n['on'])}
    return {'limit_semitones':limit,'count':len(far),'by_track':dict(sorted(by.items(),key=lambda kv:-kv[1]['notes'])),'examples':far[:examples],'outside_preset':silent[:examples],'outside_count':len(silent)}
def review(p,out,config=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);clock=Clock(p)
    summary={'validation':validate(p),'title':p['title'],'tracks':[],'sections':[],'prompts':[],'not_a_perceptual_quality_score':True}
    csv_rows=[]
    for t in p['tracks']:
        notes=sorted(t['notes'],key=lambda n:n['on']);actual=performed(t,clock)
        a_by_id={n['id']:n for n in actual};vel=[t['performance']['notes'][n['id']]['velocity'] for n in notes]
        hist=Counter(round(n['duration'],3) for n in notes);interval=[];gaps=[]
        for a,b in zip(actual,actual[1:]):
            if a['tick']!=b['tick']:
                interval.append(abs(b['pitch']-a['pitch']));gaps.append((b['start_seconds']-a['end_seconds'])*1000)
        phrases=Counter(n.get('phrase','unassigned') for n in notes)
        info={'id':t['id'],'role':t.get('role'),'engine':t['engine'],'notes':len(notes),'pitch_range':[min((n['pitch'] for n in notes),default=None),max((n['pitch'] for n in notes),default=None)],'duration_values':dict(hist),'velocity_range':[min(vel,default=None),max(vel,default=None)],'median_performed_key_gap_ms':round(statistics.median(gaps),2) if gaps else None,'step_or_repeat_fraction':round(sum(x<=2 for x in interval)/len(interval),3) if interval else None,'phrase_labels':dict(phrases),'same_key_retrigger_trims':sum(n.get('retrigger_trimmed',False) for n in actual)}
        summary['tracks'].append(info)
        if t.get('role') in ('melody','countermelody') and notes:
            if len(hist)<3:summary['prompts'].append(f'{t["id"]}: few duration categories; inspect whether the intended line has phrase direction and space.')
            if len(set(vel))<4:summary['prompts'].append(f'{t["id"]}: nearly flat MIDI velocity; inspect instrument response before adding expression.')
        bank=(t.get('patch') or t).get('bank',0)
        if t['engine']=='soundfont' and t.get('soundfont','default')=='default' and bank in (17,18) and not any(c==2 for _,c,_ in t['performance'].get('cc',[])):
            summary['prompts'].append(f'{t["id"]}: MuseScore "Expr." presets (bank 17/18) are near-silent until CC2 is written.')
        cut=highpass_cut(t)
        if cut and cut[0]>1.5:
            low,keeps=highpass_floor(cut[2]);where='an octave under that note' if low>15 else 'the lowest a part may have'
            summary['prompts'].append(f'{t["id"]}: its high-pass at {t["mix"].get("highpass",30):g} Hz takes {cut[0]:.1f} dB from the fundamental of its lowest note ({NAMES[cut[1]%12]}{cut[1]//12-1}, {cut[2]:.0f} Hz); at {low:.0f} Hz, {where}, it takes {keeps:.1f} dB.')
        for n in notes:
            e=t['performance']['notes'][n['id']];a=a_by_id[n['id']]
            csv_rows.append({'track':t['id'],'role':t.get('role'),'note_id':n['id'],'bar_1_based':int(n['on']//clock.beats_per_bar)+1,'beat_in_bar':round(n['on']%clock.beats_per_bar,4),'pitch':n['pitch'],'duration_q':n['duration'],'phrase':n.get('phrase',''),'articulation':n.get('articulation',''),'velocity':e['velocity'],'timing_ms':e.get('timing_ms',0),'gate':e.get('gate',1),'start_seconds':round(a['start_seconds'],6),'end_seconds':round(a['end_seconds'],6)})
    for s in p['sections']:
        lo=s['start_bar']*clock.beats_per_bar;hi=(s['start_bar']+s['bars'])*clock.beats_per_bar
        tracks=[];roles=Counter()
        for t in p['tracks']:
            notes=[n for n in t['notes'] if lo<=n['on']<hi]
            if notes:tracks.append(t['id']);roles[t.get('role')]+=len(notes)
        summary['sections'].append({**s,'start_seconds':round(clock.seconds(lo),3),'end_seconds':round(clock.seconds(hi),3),'active_tracks':tracks,'onsets_by_role':dict(roles)})
    summary['vertical_minor_seconds_ninths']=v=vertical(p,clock)
    if v['count']:
        summary['prompts'].append(f'{v["count"]} sustained minor-second/ninth collisions ({v["foreground_count"]} touch the foreground); most between {next(iter(v["by_parts"]))}. Check whether each is a prepared tension or an accidental voicing.')
    oc=outside_chord(p,clock)
    if oc is not None:
        summary['outside_chord']=oc;g=oc['not_resolved_by_step']
        def first(x):
            f=x['first'];return f'most in {x["most_in"]}; first {f["note"]} {"held into" if f["held_into_chord"] else "on"} {f["chord"]} at {f["at"]}'
        def notes(x,who):
            n=x['count'];return f'{n} {who} {"note" if n==1 else "notes"} on strong positions {"sits" if n==1 else "sit"} outside the written chord and {"is" if n==1 else "are"}'
        if 'melody' in g:summary['prompts'].append(f'{notes(g["melody"],"melody")} not resolved by step ({first(g["melody"])}). The others outside it are named in outside_chord as passing, neighbour, appoggiatura, escape, suspension, retardation, pedal or anticipation notes (Open Music Theory, Embellishing Tones). In rock, melodies leave such notes unresolved, mostly in pentatonic verses (Temperley 2007; rock-and-metal.md); elsewhere resolve each by step, change the chord under it, or write a colour tone that is meant to stay into the symbol (Cadd9, C6, Csus4).')
        if 'bass' in g:summary['prompts'].append(f'{notes(g["bass"],"bass")} neither resolved by step nor held as a pedal ({first(g["bass"])}). Where the bass is meant there, write a slash chord (C/D); otherwise move it to a chord tone.')
        if 'accompaniment' in g:summary['prompts'].append(f'{notes(g["accompaniment"],"accompaniment")} neither resolved by step nor held as a pedal ({first(g["accompaniment"])}). Write a tension that is meant into the symbol (Cmaj7, Csus4, Cadd9); many together can mean the part and the chord symbols are out of step.')
        if oc['unparsed_symbols']:summary['prompts'].append('Chord symbols not checked: '+', '.join(oc['unparsed_symbols']))
    par=summary['parallel_fifths_octaves']=parallels(p,clock)
    if par['count']:
        f=par['examples'][0]
        summary['prompts'].append(f'{par["count"]} {"time" if par["count"]==1 else "times"} two parts move in parallel fifths or octaves (most between {next(iter(par["by_pair"]))}; first {f["interval"]} at {f["at"]}). Where the parts are independent voices (baroque, classical, chorale and chamber writing), two perfect consonances of the same size in a row fuse the voices and are avoided (Open Music Theory, First-Species Counterpoint): move one voice the other way or to a third or sixth. Power chords and lines doubled on purpose move in parallel; octaves inside a line doubled at the octave are left out (baroque.md).')
    low=summary['low_intervals']=low_intervals(p,clock)
    if low['count']:
        w=low['furthest_below']
        summary['prompts'].append(f'{low["count"]} close {"interval sounds under its" if low["count"]==1 else "intervals sound under their"} low interval limit, where voicings turn muddy (most between {next(iter(low["by_parts"]))}; furthest under, a {w["interval"]} {w["notes"][0]}-{w["notes"][1]} at {w["at"]}, whose limit is {w["limit"]}). Spread the voicing or move the upper note an octave up, leaving the low register to the bass. The limits are guides: soft, dark sounds bear more than loud, bright ones, and a low rumble can be meant (Hoffmann; arrangement.md, Spacing).')
    rep=summary['repetition']=repetition(p,clock)
    for s in rep['static_spans']:
        summary['prompts'].append(f'Bars {s["from_bar"]}-{s["to_bar"]}: every part repeats the same {s["block_bars"]}-bar block note for note ({s["bars"]} bars). Change a layer, add a fill or a break, or vary the block (development-and-groove.md).')
    for l in rep['part_loops']:
        who=', '.join(l['tracks']);cyc='/'.join(map(str,l['cycle_bars']))
        summary['prompts'].append(f'Bars {l["from_bar"]}-{l["to_bar"]}: {who} {"repeat" if len(l["tracks"])>1 else "repeats"} a {cyc}-bar pattern unchanged for {l["bars"]} bars. Dance music brings new sounds in at the downbeats of its phrases (Smith 2021): at an 8- or 16-bar edge try a fill, a dropout and return, or a variation of the pattern (development-and-groove.md).')
    for r in rep['literal_returns']:
        summary['prompts'].append(f'{r["section"]} repeats {r["repeats"]} note for note in every part; if the return should develop, change one thing: the melody, the harmony under it, the texture or the register (development-and-groove.md).')
    for w in rep['arrivals_thinner_than_before']:
        summary['prompts'].append(f'{w["section"]} arrives thinner than {w["after"]} (notes per bar {w["notes_per_bar"][0]:g} -> {w["notes_per_bar"][1]:g}, parts {w["parts"][0]} -> {w["parts"][1]}, velocity {w["mean_velocity"][0]:g} -> {w["mean_velocity"][1]:g}); confirm the drop in energy is meant.')
    for f in rep['sections_alike']:
        summary['prompts'].append(f'{f["sections"][0]} and {f["sections"][1]} have the same parts and nearly the same density and dynamics; decide what changes between them.')
    stiff=summary['stiffness']=stiffness(p,clock)
    for b in stiff['block_chord_parts']:
        summary['prompts'].append(f'{b["track"]}: {b["block_share"]:.0%} of its {b["chords"]} chords are struck and released as one block. Hold a common tone over the change, move an inner voice, break the chord or vary its rhythm (development-and-groove.md; musiclib.voicing voices chords to move smoothly).')
    from .profile import melody_in, top_line
    line=top_line([n for t in p['tracks'] if t.get('role')=='melody' for n in t['notes']])
    summary['melody_sections']=[]
    for s in p['sections']:
        m=melody_in(line,s['start_bar']*clock.beats_per_bar,(s['start_bar']+s['bars'])*clock.beats_per_bar,clock)
        summary['melody_sections'].append({'section':s['id'],**(m or {})})
        if m and m['bars_compared']>=8 and m['bars_restated']==0:
            summary['prompts'].append(f'{s["id"]}: none of its {m["bars_compared"]} melody bars restates the rhythm and shape of an earlier one. Pop sections often state an idea and restate it before departing (Summach 2011), as a classical sentence repeats its basic idea (Caplin 1998); if this section should have such an idea, state it and restate it, varied or sequenced (climax-and-melody.md).')
    if stiff['no_pushes_anywhere']:
        summary['prompts'].append('No melody or accompaniment attack anticipates a downbeat or half-bar. Rock and pop melodies anticipate strong beats (Tan, Lustig and Temperley 2019), and moderate syncopation goes with the most groove (Witek et al. 2014; development-and-groove.md); if the style calls for drive, try a few pushes.')
    if config is not None:
        from . import surge
        if surge.installed(config):
            # Surge XT is the default synth where it is installed: a built-in preset it covers is asked about.
            full=bool((config.get('surge') or {}).get('catalog'))
            for t in p['tracks']:
                preset=(t.get('synth') or {}).get('preset') if t['engine']=='synth' else None
                options=surge.counterparts(preset) if preset else []
                named=surge.catalog_counterparts(preset) if preset and full and not options else []
                if (options or named) and t['notes']:
                    which=f'its patches for this role include {", ".join(options[:4])}' if options else f'its full patch set has patches named for this sound: {", ".join(named[:4])}'
                    summary['prompts'].append(f'{t["id"]}: plays the built-in {preset}; Surge XT is installed, and {which}. Hear them on the part: studio.py audition --track {t["id"]} --sounds {",".join("surge:"+x for x in (options or named)[:3])} --bars FIRST-LAST (electronic-sounds.md). Keep the built-in preset where a render must repeat exactly or the sound needs fields of its own.')
        st=summary['transposed_samples']=stretched(p,clock,sample_maps(p,config))
        if st['count']:
            worst=next(iter(st['by_track']))
            summary['prompts'].append(f'{st["count"]} notes play a sample transposed more than {st["limit_semitones"]} semitones, most in {worst}; the tone and the vibrato rate change with it. Move them, give them to another instrument, or accept the change.')
        if st['outside_count']:summary['prompts'].append(f'{st["outside_count"]} notes fall outside their preset\'s keys and will not sound.')
        from . import audio,layered
        cannot=summary['cannot_render']=[m for t in p['tracks'] if t['engine']=='soundfont' for m in [layered.unsupported(t,audio.soundfont_for(config,t)[1]['path'])] if m]
        summary['prompts']+=['Cannot render: '+m for m in cannot]
    if 'loop' in p:
        from . import loop
        s=summary['loop_seam']=loop.seam(p,clock)
        m,pc,tb=s['meter'],s['pitch'],s['timbre']
        if not m['same_tempo']:summary['prompts'].append(f'Loop seam: {m["bpm_at_end"]:g} BPM at the loop end, {m["bpm_at_start"]:g} at the loop start. A tempo change across the seam is heard on every repeat; confirm it is meant.')
        if pc['not_before']:summary['prompts'].append(f'Loop seam: {", ".join(pc["not_before"])} sound in the first second after the loop point but not in the five seconds before it. Check that the last bar leads into the first.')
        moves=[x for x in (f'entering: {", ".join(tb["entering"])}' if tb['entering'] else '',f'leaving: {", ".join(tb["leaving"])}' if tb['leaving'] else '') if x]
        if moves:summary['prompts'].append('Loop seam: parts '+'; '.join(moves)+'. Confirm the change of instruments at the loop point is meant.')
    # Everything is composed before the first file is written, and what was written is recorded whatever stops the
    # review, so clean can take it (a failure part way left two files and no record; found by GPT Pro's third review).
    lines=[f'# {p["title"]}', '',p.get('brief',''),'', '| Section | Bars (1-based) | Time | Function |','|---|---:|---:|---|']
    for s in summary['sections']:
        lines.append(f'| {s["id"]} | {s["start_bar"]+1}–{s["start_bar"]+s["bars"]} | {s["start_seconds"]:.1f}–{s["end_seconds"]:.1f}s | {s.get("intent","")} |')
    lines+=['','## Authored musical decisions','']+[f'- {x}' for x in p.get('decisions',[])]+['','## Review questions','']+['- '+x for x in summary['prompts']]
    lines+=['','Metrics do not establish whether a piece sounds good. Key gaps exclude pedal/release tails. Different durations and more tracks are not quality scores.']
    arrangement='\n'.join(lines)+'\n'
    try:
        save_json(out/'score_review.json',summary)
        if csv_rows:
            # A text cell a spreadsheet would read as a formula (one starting with =, +, -, @, a tab or a carriage
            # return) gets a leading apostrophe, as OWASP's CSV injection guidance advises: a project's names stay text.
            safe=lambda v:"'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@','\t','\r') else v
            with files.staged(out/'notes.csv','w',encoding='utf-8',newline='') as f:  # whole or not at all
                w=csv.DictWriter(f,fieldnames=csv_rows[0].keys());w.writeheader();w.writerows({k:safe(v) for k,v in r.items()} for r in csv_rows)
        with files.staged(out/'arrangement.md','w',encoding='utf-8') as f:
            f.write(arrangement)
    finally:
        files.register(out,[out/n for n in ('score_review.json','notes.csv','arrangement.md') if (out/n).is_file()])
    return summary
