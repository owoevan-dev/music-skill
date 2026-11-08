"""Extract a score passage for revision. Held notes at the cut re-attack."""
import argparse
import copy
from pathlib import Path
import sys
from musiclib.model import TPQ,Clock,curve_at,load_project,performed,rubato_spans,save_json,swung,tick_of,validate

REATTACK_GAP_S=.1  # the most a note's own timing may move it (validate: timing_ms within ±100)

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
        notes=[];again=set();shifted=set();length=end-start;perf=t['performance']
        sw=perf.get('swing');offset=perf.get('offset_ms',0)/1000;bar=excerpt_clock.beats_per_bar
        at=lambda b:excerpt_clock.seconds(swung(b,sw,bar))  # where the excerpt plays a written position, before timing
        for n in t['notes']:
            a0,a1=played[n['id']]['tick'],played[n['id']]['end_tick'];w=written[n['id']]
            on=w['tick'];off=max(on+1,tick_of(clock.beat(clock.seconds(n['on']+n['duration']))))
            if on>=stop or min(stop,a1)-max(cut,a0)<1:continue
            if on<cut and w['end_tick']<=cut and a0<cut:continue
            # (A note a later strike of its key cut short in the piece takes the boundary's way too, so it ends where it
            # ended even where that strike is not in the passage.)
            if start<=n['on'] and n['on']+n['duration']<=end and cut<=a0 and a1<=stop and not played[n['id']].get('retrigger_trimmed'):
                a=n['on']-start;d=n['duration']
                if not (a<=length-1/TPQ and 1/TPQ<=d and a+d<=length+1e-9):
                    a=(max(cut,on)-cut)/TPQ;d=(min(stop,off)-max(cut,on))/TPQ
                n['on']=a;n['duration']=d;notes.append(n);continue
            x0,x1=max(a0,cut)-cut,min(a1,stop)-cut
            s0,s1=excerpt_clock.seconds(x0/TPQ),excerpt_clock.seconds(x1/TPQ)
            # Its written onset: its own where it is written in the passage (its timing then stays its own), the cut
            # where it is written before it; the tick it plays on where a float hair would leave less than a tick to the
            # end.  Its written length runs to its written end or the passage's, at least a tick.
            o=max(0.0,n['on']-start)
            if o>length-1/TPQ-1e-9:o=(max(on,cut)-cut)/TPQ
            room=length-o;d=min(room,n['on']+n['duration']-start-o)
            if d<1/TPQ:d=min(room,max(1,x1-x0)/TPQ)  # written to end before the cut, struck after it as played
            timing=min(.1,max(-.1,s0-at(o)-offset))  # validate: timing_ms within ±100
            begin=at(o)+timing+offset  # before the tick rounding: a start before the excerpt's plays at its start
            if s1-begin<excerpt_clock.seconds(1/TPQ):continue  # a part offset no timing can undo leaves no tick of it
            gate=(s1-begin)/(at(o+d)-at(o))
            if not .05<=gate<=1.6:
                # The written length, in whole ticks, that plays as long at the nearest gate validate allows (bisection:
                # the length a written span plays grows with it, swing and tempo changes included).
                want=(s1-begin)/min(1.6,max(.05,gate));lo,hi=1,max(1,int(room*TPQ+1e-9))
                while lo<hi:
                    mid=(lo+hi)//2
                    if at(o+mid/TPQ)-at(o)<want:lo=mid+1
                    else:hi=mid
                d=min(room,lo/TPQ);gate=min(1.6,max(.05,(s1-begin)/(at(o+d)-at(o))))
            n['on']=o;n['duration']=d;perf['notes'][n['id']].update(timing_ms=timing*1000,gate=gate);notes.append(n)
            if on<cut and a0<cut:again.add(n['id'])  # struck before the cut and sounding there: re-attacked at it
            elif on<cut:shifted.add(n['id'])  # written before the cut, struck after it: its written onset moved onto it
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
    if 'loop' in q:
        q.pop('loop')
        q.setdefault('decisions',[]).append('The excerpt plays as a passage, not a loop; the source keeps its loop.')
    if 'harmony' in q:q['harmony']=[{**h,'bar':h['bar']-first_bar+1} for h in q['harmony'] if first_bar<=h['bar']<first_bar+bars]
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
    save_json(a.output,extract(load_project(a.project),a.first_bar,a.bars));print(a.output)

if __name__=='__main__':
    from musiclib import files
    files.escape_unprintable()
    try:main()
    except (ValueError,KeyError,OSError) as e:
        print('ERROR:',str(e),file=sys.stderr);sys.exit(2)
