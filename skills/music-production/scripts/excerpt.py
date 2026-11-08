"""Extract a score passage for revision. Held notes at the cut re-attack."""
import argparse
import copy
import math
from pathlib import Path
import sys
from musiclib.model import TPQ,Clock,curve_at,load_project,performed,rubato_spans,save_json,swung,tick_of,validate

REATTACK_GAP_S=.1  # the most a note's own timing may move it (validate: timing_ms within ±100)

def one_line(t):
    """A part validate holds to one written line: the additive lead, and a SoundFont part that slurs (legato mode slur)."""
    leg=t['performance'].get('legato')
    return t['engine']=='additive' or (t['engine']=='soundfont' and isinstance(leg,dict) and leg.get('mode','slur')=='slur')

def collides(track,first,clock,struck,gap=0.0):
    """Whether the note `first`, struck before the cut in the piece and so at the excerpt's start, meets a later strike
    of its key (later in the piece as played, `struck`): on its tick or one tick off, as played or as written, which the
    render's own rule (performed()) stops on, or within `gap` seconds as played.  As played counts the notes' timing,
    the part's offset and swing."""
    h=next((n for n in track['notes'] if n['id']==first),None)
    if h is None:return False
    for n in track['notes']:
        if n is h or n['pitch']!=h['pitch'] or struck[n['id']]<=struck[h['id']]:continue
        pair={**track,'notes':[h,n],'performance':{**track['performance'],'notes':{k:track['performance']['notes'][k] for k in (h['id'],n['id'])}}}
        try:
            played={x['id']:x['start_seconds'] for x in performed(pair,clock,True)};performed(pair,clock,False)
        except ValueError:return True
        if abs(played[n['id']]-played[h['id']])<=gap+1e-9:return True
    return False

def crop(points,start,end,bend=False):
    """A [beat, value] curve (linear between points, two points on one beat a jump) from `start` to `end`, moved to start
    at 0: the value just after the start, the points between and the value just before the end, so a jump on either
    cut stays where it was.  A bend rests at 0 until its first point and jumps there; other curves hold their first
    value before it."""
    if not points:return points
    first=points[0][0]
    if bend and end<=first:return []
    left=lambda b:0.0 if bend and b<=first else curve_at(points,b-1e-9)
    head=[] if bend and start<first else [[0,curve_at(points,start)]]
    return head+[[b-start,v] for b,v in points if start<b<end]+[[end-start,left(end)]]

def crop_cc(track,start,end):
    """A part's [beat, controller, value] points from `start` to `end`, moved to start at 0: each controller's value at
    the start, its points between and, where it ramps on past the end, its value at the end.  In linear mode
    (cc_events) a continuous controller ramps from point to point in beats, in the MIDI and in the additive synth alike
    (audio.control), so a cut inside a ramp takes the ramp's value there; in step mode, and for the switch controllers
    64-69, a controller holds its last point's value."""
    perf=track['performance']
    linear=perf.get('cc_mode','linear' if track['engine']=='additive' else 'step')=='linear'
    by={}
    for beat,control,value in sorted(perf.get('cc',[])):by.setdefault(control,[]).append((beat,value))
    out=[]
    for control,points in by.items():
        ramps=linear and not 64<=control<=69 and len(points)>1
        def at(b):
            before=[(x,v) for x,v in points if x<=b];later=next(((x,v) for x,v in points if x>b),None)
            if not before:return None
            (x0,v0)=before[-1]
            if not ramps or later is None:return v0
            (x1,v1)=later
            return int(round(v0+(v1-v0)*(b-x0)/(x1-x0)))
        if at(start) is not None:out.append([0,control,at(start)])
        out+=[[beat-start,control,value] for beat,value in points if start<beat<=end]
        if ramps and at(end) is not None and not any(beat==end for beat,_ in points) and any(beat>end for beat,_ in points):
            out.append([end-start,control,at(end)])
    return sorted(out)

def extract(p,first_bar,bars):
    if first_bar<1 or bars<1 or first_bar-1+bars>p['clock']['bars']:raise ValueError('Excerpt outside source bars')
    q=copy.deepcopy(p);clock=Clock(p);start=(first_bar-1)*clock.beats_per_bar;end=start+bars*clock.beats_per_bar
    q['clock']['bars']=bars
    bpm=next(bpm for beat,bpm in reversed(p['clock']['tempo']) if beat<=start)
    q['clock']['tempo']=[[0,bpm]]+[[beat-start,bpm] for beat,bpm in p['clock']['tempo'] if start<beat<end]
    q['sections']=[]
    for sec in p['sections']:
        a=max(first_bar-1,sec['start_bar']);b=min(first_bar-1+bars,sec['start_bar']+sec['bars'])
        if a<b:q['sections'].append({**sec,'start_bar':a-first_bar+1,'bars':b-a})
    rubato=q['clock'].pop('rubato',None)
    if rubato:
        # The piece's ritardandi that reach into the passage, as spans in its beats, so it keeps the piece's tempo as
        # played: one into a section boundary at or after its end, one begun before its first bar, the close where
        # the passage reaches it.  Its own sections would put a boundary at neither edge.
        spans=[[round(a-start,6),round(b-start,6),w] for a,b,w in rubato_spans(p) if a<end and b>start]
        if spans:q['clock']['rubato']={'spans':spans,**({'q':rubato['q']} if 'q' in rubato else {})}
    excerpt_clock=Clock(q)
    held={};moved={};struck={};cut=round(start*TPQ);stop=round(end*TPQ)
    for t,source in zip(q['tracks'],p['tracks']):
        # A note belongs to the passage when it is written before its end (a note of the next bar that the part's
        # offset or its timing plays early is the next passage's) and the piece plays it there, on the tick grid it
        # plays on (performed(): its timing, gate, swing, the part's offset, a later attack of its key ending it): one
        # whose onset rounds onto the passage's last tick, or with less than a tick left at the cut, is not.  A note
        # written before the cut belongs to it only if it is written across the cut, or struck after it as played: one
        # written to end by the cut that its gate carries past it is a legato overlap, part of the next note's attack,
        # which a re-attack would double (and on a monophonic part, overlap).  One inside the passage as written and as
        # played keeps its own position, moved by whole bars, so it plays where it played in the piece; only one that
        # would fall a float hair outside the passage's bounds takes its tick instead.  One the piece plays across a cut
        # plays the part of it the passage holds: from the cut (a note struck before it, still sounding, is re-attacked
        # there) or from where it starts as played, to where it ends as played or to the end of the passage.  Its
        # written onset and length stay inside the passage, on its tick grid, and its timing and gate are worked out
        # (within their bounds) so the excerpt plays it on those ticks.
        written={n['id']:n for n in performed(source,clock,False)};played={n['id']:n for n in performed(source,clock,True)}
        struck[t['id']]={k:n['tick'] for k,n in played.items()}
        notes=[];again=set();shifted=set();spans={};length=end-start;perf=t['performance']
        sw=perf.get('swing');offset=perf.get('offset_ms',0)/1000;bar=excerpt_clock.beats_per_bar
        at=lambda b:excerpt_clock.seconds(swung(b,sw,bar))  # where the excerpt plays a written position, before timing
        def fit(o,d,s1,begin,room):
            """The written length near `d` (whole ticks, within `room`) and the gate that play a note written at `o`
            from `begin` to `s1`: bisection where the gate would leave validate's bounds (the length a written span
            plays grows with it, swing and tempo changes included)."""
            gate=(s1-begin)/(at(o+d)-at(o))
            if not .05<=gate<=1.6:
                want=(s1-begin)/min(1.6,max(.05,gate));lo,hi=1,max(1,int(room*TPQ+1e-9))
                while lo<hi:
                    mid=(lo+hi)//2
                    if at(o+mid/TPQ)-at(o)<want:lo=mid+1
                    else:hi=mid
                d=min(room,lo/TPQ);gate=min(1.6,max(.05,(s1-begin)/(at(o+d)-at(o))))
            return d,gate
        inside={}  # a note of the passage's own: where it plays in the excerpt, (start, end) in seconds
        for n in t['notes']:
            a0,a1=played[n['id']]['tick'],played[n['id']]['end_tick'];w=written[n['id']]
            on=w['tick'];off=max(on+1,tick_of(clock.beat(clock.seconds(n['on']+n['duration']))))
            # Written in the passage and played wholly before its first beat (a note shorter than the timing or offset
            # that plays it early): it sounds at the excerpt's start, as the passage's other notes played before the
            # cut do, for as long as it sounded; no passage held it before.  (Found by the stress test of 0.4.0.)
            early_whole=cut<=on<stop and a1<=cut
            if early_whole:a0,a1=cut,cut+(a1-a0)
            if on>=stop or min(stop,a1)-max(cut,a0)<1:continue
            if on<cut and w['end_tick']<=cut and a0<cut:continue
            # (A note a later strike of its key cut short in the piece takes the boundary's way too, so it ends where it
            # ended even where that strike is not in the passage.)
            if (start<=n['on'] and n['on']+n['duration']<=end and cut<=a0 and a1<=stop and not played[n['id']].get('retrigger_trimmed')
                    and not early_whole):
                a=n['on']-start;d=n['duration']
                if not (a<=length-1/TPQ and 1/TPQ<=d and a+d<=length+1e-9):
                    a=(max(cut,on)-cut)/TPQ;d=(min(stop,off)-max(cut,on))/TPQ
                n['on']=a;n['duration']=d;notes.append(n)
                inside[n['id']]=(at(a)+perf['notes'][n['id']].get('timing_ms',0)/1000+offset,excerpt_clock.seconds((min(stop,a1)-cut)/TPQ))
                continue
            x0,x1=max(a0,cut)-cut,min(a1,stop)-cut
            s0,s1=excerpt_clock.seconds(x0/TPQ),excerpt_clock.seconds(x1/TPQ)
            # Its written onset: its own where it is written in the passage (its timing then stays its own), the cut
            # where it is written before it; the tick it plays on where a float hair would leave less than a tick to the
            # end.  Its written length runs to its written end or the passage's, at least a tick.
            o=max(0.0,n['on']-start)
            if o>length-1/TPQ-1e-9:o=(max(on,cut)-cut)/TPQ
            # What is left to the passage's end, on its tick grid where it lies within a hair of it: a float residue
            # under a tick (3.9989583 from 4) left a length a hair under validate's one tick (found by GPT Pro's fourth
            # review of 0.4.0).
            room=length-o
            if abs(room*TPQ-round(room*TPQ))<1e-6:room=round(room*TPQ)/TPQ
            d=min(room,n['on']+n['duration']-start-o)
            if d<1/TPQ:d=min(room,max(1,x1-x0)/TPQ)  # written to end before the cut, struck after it as played
            timing=min(.1,max(-.1,s0-at(o)-offset))  # validate: timing_ms within ±100
            begin=at(o)+timing+offset  # before the tick rounding: a start before the excerpt's plays at its start
            # A part offset no timing can undo leaves no tick of it; one that sounds a tick, cut short by a later strike of
            # its key, stays.  Judged on the tick grid the excerpt plays on, as performed() rounds a start to its tick:
            # a tick's length at the excerpt's first tempo let a float residue drop such a note, and after a change of
            # tempo dropped one that sounds a whole tick (found by the excerpt fuzzer once it drew one-line parts, and by
            # GPT Pro's fifth review of 0.4.0).
            if x1-(0 if begin<=0 else tick_of(excerpt_clock.beat(begin)))<1:continue
            d,gate=fit(o,d,s1,begin,room)
            n['on']=o;n['duration']=d;perf['notes'][n['id']].update(timing_ms=timing*1000,gate=gate);notes.append(n)
            spans[n['id']]=(o,s1,begin)
            if on<cut and a0<cut:again.add(n['id'])  # struck before the cut and sounding there: re-attacked at it
            elif on<cut:shifted.add(n['id'])  # written before the cut, struck after it: its written onset moved onto it
        # A note written before the cut and struck after it has its written onset moved onto the cut; where a note of
        # its key is written there too, on the tick or the next (one the piece struck first), it is written where it
        # plays instead, its timing then under a tick, so the two do not strike the key at once as written, which
        # validate refuses.  One that still meets it plays within a tick of it, which the render refuses: it goes, and
        # only it (both of two such notes went; found by the excerpt fuzzer's count of notes from before the cut).  (Found
        # by the stress test of 0.4.0.)  A part held to one line is written in the piece's order below, which keeps two
        # strikes of a key apart, so nothing of it goes here.
        gone=set()
        clash=lambda n:any(m is not n and m['id'] not in gone and m['pitch']==n['pitch'] and abs(tick_of(m['on'])-tick_of(n['on']))<=1 for m in notes)
        last=max(0,int((length-1/TPQ)*TPQ+1e-9))
        def bound(ok):  # the first tick k, 0 to last, for which ok(k) holds (ok is monotone); last+1 if none
            lo,hi=0,last+1
            while lo<hi:
                mid=(lo+hi)//2
                if ok(mid):hi=mid
                else:lo=mid+1
            return lo
        for n in notes:
            if n['id'] in shifted and not one_line(t) and clash(n):
                o,s1,begin=spans[n['id']];end_w=o+n['duration']
                # Every tick whose timing (within ±100 ms, the part's offset counted) plays the note where it plays is
                # tried, nearest first: the last at or before that point, then outward, later ticks too, with negative
                # timing.  Only ticks up to the played start were tried, so a pickup the passage strikes again on the
                # cut went, though a later tick kept both (found by GPT Pro's sixth review of 0.4.0).
                k0=max(tick_of(o),bound(lambda k:at(k/TPQ)+offset>begin+1e-9)-1)
                k_lo=max(tick_of(o),bound(lambda k:at(k/TPQ)+offset>=begin-.1-1e-9));k_hi=bound(lambda k:at(k/TPQ)+offset>begin+.1+1e-9)-1
                same=[tick_of(m['on']) for m in notes if m is not n and m['id'] not in gone and m['pitch']==n['pitch']]
                free=[k for k in sorted(range(k_lo,k_hi+1),key=lambda k:(abs(k-k0),k)) if all(abs(k-x)>1 for x in same)]
                if not free:
                    gone.add(n['id']);continue
                n['on']=free[0]/TPQ
                d,gate=fit(n['on'],max(1/TPQ,min(length-n['on'],end_w-n['on'])),s1,begin,length-n['on'])
                n['duration']=d;spans[n['id']]=(n['on'],s1,begin)
                perf['notes'][n['id']].update(timing_ms=min(100,max(-100,(begin-at(n['on'])-offset)*1000)),gate=gate)
        notes=[n for n in notes if n['id'] not in gone];shifted-=gone
        if one_line(t):
            # The written line keeps the piece's written order.  A note written before the cut that sounds in the
            # passage (re-attacked at the cut, moved onto it or to where it plays) comes before the passage's own notes,
            # as it does in the piece, whichever its timing plays first: written where it plays, inside a note of the
            # passage, it had the pass below cut that note to where it began (500 ms to 25 ms; found by GPT Pro's fifth
            # review of 0.4.0, and in its other forms by the excerpt fuzzer's check of played lengths).  Those notes are
            # written from the cut, each as early as its timing (within 100 ms) plays it where it plays and as long as
            # its played length needs at a gate of 1, or to where the next note begins; the passage's notes keep their
            # places, but one written so close after the cut that it leaves no room is written after them, its timing
            # making up the difference, and so on to the first note left where the piece writes it.  Where a note's
            # timing cannot make that up, the note before ends sooner, or goes when no tick is left for it.
            written_at={m['id']:m['on']-start for m in source['notes']}
            before_cut=lambda n:written_at[n['id']]<-1e-9
            if any(before_cut(n) for n in notes):
                last_tick=max(0,int((length-1/TPQ)*TPQ+1e-9))
                when=lambda k:at(k/TPQ)+offset  # where a note written at tick k plays, before its own timing
                def first(ok):
                    """The first tick k, 0 to last_tick, for which ok(k) holds (ok is monotone); last_tick+1 if none."""
                    lo,hi=0,last_tick+1
                    while lo<hi:
                        mid=(lo+hi)//2
                        if ok(mid):hi=mid
                        else:lo=mid+1
                    return lo
                def ticks_for(k,begin,s1,gate):
                    """The fewest whole ticks a note written at tick k needs to play from begin to s1 at `gate`."""
                    want=(s1-begin)/gate;lo,hi=1,max(1,last_tick+1-math.floor(k))
                    while lo<hi:
                        mid=(lo+hi)//2
                        if at((k+mid)/TPQ)-at(k/TPQ)>=want-1e-12:hi=mid
                        else:lo=mid+1
                    return lo
                span_of=lambda n:(spans[n['id']][2],spans[n['id']][1]) if n['id'] in spans else inside[n['id']]
                earliest=lambda n:first(lambda k:when(k)>=span_of(n)[0]-.1-1e-9)  # its timing at most +100 ms
                latest=lambda n:first(lambda k:when(k)>span_of(n)[0]+.1+1e-9)-1  # and at least -100 ms
                gap=lambda a,b:2 if a['pitch']==b['pitch'] else 1  # one key struck a tick apart is refused
                order=sorted(notes,key=lambda n:written_at[n['id']])
                heads=[n for n in order if before_cut(n)];rest=[n for n in order if not before_cut(n)]
                # How late each note may start and leave the notes after it their places, from the passage's end back.
                # A note of the passage keeps its played length (a gate of 1.6 at most) and never starts before the
                # piece writes it, as the piece's own layout fits; a note from before the cut needs a tick at least, and
                # one that cannot start by then goes.  Laid forward without this, a note from before the cut took its
                # full length and the passage's note after it ended sooner, 200 ms becoming 132 (found by GPT Pro's
                # sixth review of 0.4.0).
                latest_of={};limit=length*TPQ;after=None
                for n in reversed(rest):
                    begin,s1=span_of(n);nat=n['on']*TPQ
                    # The latest whole tick, within its timing and a tick or two before the next note's latest start,
                    # whose earliest end at a gate of 1.6 is not past that start: found where it would be written, as
                    # swing and tempo changes make a span's length depend on where it lies (computed where the piece
                    # writes it, a note moved under swing came out two ticks short).
                    ends=lambda w,b=begin,e=s1:w+ticks_for(w,b,e,1.6)
                    lo,hi=math.ceil(nat-1e-9),math.floor(min(latest(n),limit-(gap(n,after) if after is not None else 0))+1e-9)
                    if hi<lo or ends(lo)>limit+1e-9:
                        late=nat
                    else:
                        while lo<hi:
                            mid=(lo+hi+1)//2
                            if ends(mid)<=limit+1e-9:lo=mid
                            else:hi=mid-1
                        late=max(nat,lo)
                    latest_of[n['id']]=late;limit,after=late,n
                gone=set()
                for n in reversed(heads):
                    late=min(latest(n),limit-(gap(n,after) if after is not None else 1))
                    if late<earliest(n):
                        gone.add(n['id']);continue
                    latest_of[n['id']]=late;limit,after=late,n
                line=[n for n in heads if n['id'] not in gone]+rest;laid=[]  # laid: [note, tick, ticks]
                for i,n in enumerate(line):
                    begin,s1=span_of(n);nxt=line[i+1] if i+1<len(line) else None
                    after_last=laid[-1][1]+gap(laid[-1][0],n) if laid else 0
                    k=laid[-1][1]+laid[-1][2] if laid else 0
                    if before_cut(n):
                        w=max(k,earliest(n),after_last)
                    else:
                        nat=n['on']*TPQ
                        if nat>=k-1e-6 and nat>=after_last-1e-6:break  # from here on as the piece writes them
                        w=max(k,nat,after_last)
                    room=(latest_of[nxt['id']] if nxt is not None else length*TPQ)-w  # the next note's latest start
                    if before_cut(n):
                        # As long as its played length needs at a gate of 1, or to where the next note begins (at up to
                        # 1.6, so it may end sooner than in the piece, as before); a note of the passage written so close
                        # after the cut that this leaves it no room goes after it, as far as the length needs at 1.6.
                        reach=(nxt['on']*TPQ if not before_cut(nxt) else earliest(nxt)) if nxt is not None else length*TPQ
                        d=ticks_for(w,begin,s1,1)
                        if w+d>reach:d=reach-w if reach-w>=(gap(n,nxt) if nxt is not None else 1) else ticks_for(w,begin,s1,1.6)
                        d=max(1,min(d,room))
                    else:  # to its written end, within the gates validate allows (a note a retrigger trims plays short)
                        d=min(max((n['on']+n['duration'])*TPQ-w,ticks_for(w,begin,s1,1.6)),ticks_for(w,begin,s1,.05),max(1,room))
                    laid.append([n,w,min(d,max(1,length*TPQ-w))])
                for n,w,d in laid:
                    begin,s1=span_of(n);o=w/TPQ;n['on']=o;n['duration']=d/TPQ;spans[n['id']]=(o,s1,begin)
                    perf['notes'][n['id']].update(timing_ms=min(100,max(-100,(begin-at(o)-offset)*1000)),
                                                  gate=min(1.6,max(.05,(s1-begin)/(at(o+d/TPQ)-at(o)))))
                notes=[n for n in notes if n['id'] not in gone];again-=gone;shifted-=gone
            # A part validate holds to one written line refuses notes that overlap as written by more than a tick, or
            # that start within a tick of each other.  A note the passage re-attacks or moves, its written length
            # stretched to play as long as in the piece, ends where the next note begins, at the longest gate validate
            # allows: it may end a little earlier than in the piece (the rest of a legato overlap into the next note);
            # one left with less than a tick before the next is left out.  A note of the passage's own that a moved
            # note now follows within its written length ends where that note begins, as it ended in the piece when
            # that note struck.  This runs after the same-key moves above, which can put a note inside the one before
            # it, and holds to validate's own tests (a moved note within a tick of another, or put inside it, went
            # through, and the excerpt was refused; found by GPT Pro's fourth review of 0.4.0).
            dropped=set();line=sorted(notes,key=lambda n:(n['on'],n['id'] not in spans))
            for a,b in zip(line,line[1:]):
                if a['id'] in dropped or not (b['on']-a['on']<1/TPQ-1e-9 or a['on']+a['duration']>b['on']+1/TPQ):continue
                room=b['on']-a['on']
                if a['id'] in spans:
                    if room<1/TPQ-1e-9:
                        dropped.add(a['id']);continue
                    o,s1,begin=spans[a['id']];a['duration']=room
                    perf['notes'][a['id']]['gate']=min(1.6,max(.05,(s1-begin)/(at(o+room)-at(o))))
                else:
                    a['duration']=max(1/TPQ,room)
            notes=[n for n in notes if n['id'] not in dropped];again-=dropped;shifted-=dropped
        held[t['id']]=again;moved[t['id']]=shifted
        t['notes']=notes;ids={n['id'] for n in notes}
        t['performance']['notes']={k:v for k,v in t['performance']['notes'].items() if k in ids}
        t['performance']['cc']=crop_cc(source,start,end)
        points=t['mix'].get('automation',[])
        def value_at(beat):
            if beat<=points[0][0]:return points[0][1]
            for (a,x),(b,y) in zip(points,points[1:]):
                if a<=beat<=b:return x+(y-x)*(clock.seconds(beat)-clock.seconds(a))/(clock.seconds(b)-clock.seconds(a))
            return points[-1][1]
        if points:t['mix']['automation']=[[0,value_at(start)]]+[[beat-start,v] for beat,v in points if start<beat<end]+[[end-start,value_at(end)]]
        perf=t['performance']
        if perf.get('dynamics'):perf['dynamics']=crop(perf['dynamics'],start,end)
        if perf.get('bend'):
            perf['bend']=crop(perf['bend'],start,end,bend=True)
            if not perf['bend']:perf.pop('bend')
        if t['mix'].get('filter_sweep'):t['mix']['filter_sweep']['points']=crop(t['mix']['filter_sweep']['points'],start,end)
        g=t['mix'].get('gate')
        if g:
            # The rhythmic gate goes on where the piece's pattern stands at the cut (it began its pattern again at the
            # passage's first beat, so a cut not on a whole cycle gated other steps; found by GPT Pro's fourth review).
            cycle=len(g['pattern'])*g.get('step_beats',.25)
            g['phase_beats']=round((start+g.get('phase_beats',0))%cycle,9)%cycle
    if 'loop' in q:
        q.pop('loop')
        q.setdefault('decisions',[]).append('The excerpt plays as a passage, not a loop; the source keeps its loop.')
    # The chord list moves to the passage's bars; an older free-form harmony object, which schema.md still accepts and
    # does not check, stays as it is (it was read as a list and stopped extract; found by GPT Pro's third review).
    if isinstance(q.get('harmony'),list):q['harmony']=[{**h,'bar':h['bar']-first_bar+1} for h in q['harmony'] if first_bar<=h['bar']<first_bar+bars]
    # What the piece struck before the cut starts the excerpt: the re-attacks, and the passage's own notes that their
    # timing or the part's earlier offset plays before the cut (the excerpt cannot start before its first beat, so they
    # all sound at its start).  Of these, and of the notes written before the cut whose written onset moved onto it, a
    # note is left out where it would meet a later strike of its key: on one tick, as played or as written, which the
    # render stops on (the piece's later strike had stopped it there), and for a re-attack also within 100 ms as
    # played, where it would only double the strike that follows.  A note written in the passage stays otherwise.
    for t in q['tracks']:
        order=struck[t['id']]
        early={n['id'] for n in t['notes'] if n['id'] not in held[t['id']] and order[n['id']]<cut}|moved[t['id']]
        drop=({h for h in held[t['id']] if collides(t,h,excerpt_clock,order,REATTACK_GAP_S)}
              |{e for e in early if collides(t,e,excerpt_clock,order)})
        if drop:
            t['notes']=[n for n in t['notes'] if n['id'] not in drop]
            t['performance']['notes']={k:v for k,v in t['performance']['notes'].items() if k not in drop}
    q.setdefault('decisions',[]).append(f'Excerpt from source bars {first_bar}–{first_bar+bars-1}; notes already held at the cut are re-attacked for independent rendering.')
    validate(q);return q

def main():
    p=argparse.ArgumentParser();p.add_argument('project',type=Path);p.add_argument('--first-bar',type=int,required=True);p.add_argument('--bars',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    from musiclib import files
    files.fresh(a.output,'preserve prior output; use a new path')
    save_json(a.output,extract(load_project(a.project),a.first_bar,a.bars),new=True);print(a.output)

if __name__=='__main__':
    from musiclib import files
    files.escape_unprintable()
    try:main()
    except (ValueError,KeyError,OSError) as e:
        print('ERROR:',str(e),file=sys.stderr);sys.exit(2)
