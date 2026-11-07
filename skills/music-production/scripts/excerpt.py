"""Extract a score passage for revision. Held notes at the cut re-attack."""
import argparse
import copy
from pathlib import Path
import sys
from musiclib.model import TPQ,Clock,curve_at,load_project,performed,save_json,validate

REATTACK_GAP_S=.1  # the most a note's own timing may move it (validate: timing_ms within ±100)

def collides(track,first,clock,struck,gap=0.0):
    """Whether the note `first`, struck before the cut in the piece and so at the excerpt's start, meets a later strike
    of its key (later in the piece as played, `struck`): on its tick or one tick off, as played or as written, which the
    render's own rule (performed()) stops on, or within `gap` seconds as played.  As played counts the notes' timing,
    the part's offset and swing."""
    h=next(n for n in track['notes'] if n['id']==first)
    for n in track['notes']:
        if n is h or n['pitch']!=h['pitch'] or struck[n['id']]<=struck[h['id']]:continue
        pair={**track,'notes':[h,n],'performance':{**track['performance'],'notes':{k:track['performance']['notes'][k] for k in (h['id'],n['id'])}}}
        try:
            played={x['id']:x['start_seconds'] for x in performed(pair,clock,True)};performed(pair,clock,False)
        except ValueError:return True
        if abs(played[n['id']]-played[h['id']])<gap:return True
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
    held={};struck={};cut=round(start*TPQ)
    for t,source in zip(q['tracks'],p['tracks']):
        # A note struck before the cut sounds there only while it lasts as written: a later attack of its key ends it
        # (performed() trims a retrigger), so a long note struck again before the cut has stopped.  The notes still
        # sounding at the cut are re-attacked there.
        ends={n['id']:n['end_tick'] for n in performed(source,clock,False)}
        struck[t['id']]={n['id']:n['tick'] for n in performed(source,clock,True)}
        notes=[];again=set()
        for n in t['notes']:
            a=max(start,n['on']);b=min(end,n['on']+n['duration'])
            if a<b and (n['on']>=start or ends[n['id']]>cut):
                if n['on']<start:again.add(n['id'])
                n['on']=a-start;n['duration']=b-a;notes.append(n)
        held[t['id']]=again
        t['notes']=notes;ids={n['id'] for n in notes}
        t['performance']['notes']={k:v for k,v in t['performance']['notes'].items() if k in ids}
        cc=t['performance'].get('cc',[]);initial={}
        for beat,control,value in sorted(cc):
            if beat<=start:initial[control]=value
        t['performance']['cc']=[[0,c,v] for c,v in sorted(initial.items())]+[[beat-start,c,v] for beat,c,v in cc if start<beat<=end]
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
    rubato=q['clock'].get('rubato')
    if rubato and first_bar-1+bars<p['clock']['bars']:
        # The final ritardando belongs to the piece's last bars; an excerpt that stops earlier keeps only the phrase rubato.
        rubato={k:v for k,v in rubato.items() if k not in ('final_beats','final_ratio')}
        if rubato.get('phrase_beats'):q['clock']['rubato']=rubato
        else:q['clock'].pop('rubato')
    if 'loop' in q:
        q.pop('loop')
        q.setdefault('decisions',[]).append('The excerpt plays as a passage, not a loop; the source keeps its loop.')
    if 'harmony' in q:q['harmony']=[{**h,'bar':h['bar']-first_bar+1} for h in q['harmony'] if first_bar<=h['bar']<first_bar+bars]
    # What the piece struck before the cut starts the excerpt: the re-attacks, and the passage's own notes that their
    # timing or the part's earlier offset plays before the cut (the excerpt cannot start before its first beat, so they
    # all sound at its start).  Of these, a note is left out where it would meet a later strike of its key: on one tick,
    # which the render stops on (the piece's later strike had stopped it there), and for a re-attack also within 100 ms
    # as played, where it would only double the strike that follows.  A note written in the passage stays otherwise.
    excerpt_clock=Clock(q)
    for t in q['tracks']:
        order=struck[t['id']];early={n['id'] for n in t['notes'] if n['id'] not in held[t['id']] and order[n['id']]<cut}
        drop=({h for h in held[t['id']] if collides(t,h,excerpt_clock,order,REATTACK_GAP_S)}
              |{e for e in early if collides(t,e,excerpt_clock,order)})
        if drop:
            t['notes']=[n for n in t['notes'] if n['id'] not in drop]
            t['performance']['notes']={k:v for k,v in t['performance']['notes'].items() if k not in drop}
    q.setdefault('decisions',[]).append(f'Excerpt from source bars {first_bar}–{first_bar+bars-1}; notes already held at the cut are re-attacked for independent rendering.')
    validate(q);return q

def main():
    p=argparse.ArgumentParser();p.add_argument('project',type=Path);p.add_argument('--first-bar',type=int,required=True);p.add_argument('--bars',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior output; use new path')
    save_json(a.output,extract(load_project(a.project),a.first_bar,a.bars));print(a.output)

if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):stream.reconfigure(errors='backslashreplace')
    try:main()
    except (ValueError,KeyError,OSError) as e:
        print('ERROR:',str(e),file=sys.stderr);sys.exit(2)
