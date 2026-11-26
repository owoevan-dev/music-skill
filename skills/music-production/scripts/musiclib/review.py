"""Score diagnostics are questions for a musical review, never aesthetic scores."""
import bisect
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from . import files, harmony
from .instruments import key_ranges, pairs
from .model import Clock, TPQ, bend_curve, curve_at, kit_patch, performed, save_json, sounded, tick_of, validate

FOREGROUND = ('melody', 'countermelody')
NAMES = ('C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B')


def highpass_floor(f0):
    """Where a high-pass keeps a note of fundamental `f0` whole: an octave under it, but not under 15 Hz, the lowest
    `validate` accepts (A0 is 27.5 Hz); with the dB that cutoff still takes from the fundamental."""
    low = max(15.0, f0 / 2)
    return low, 10 * math.log10(1 + (low / f0) ** 4)

def low_passes(p,below_hz=12000,share=.5,min_parts=3):
    """Parts other than the bass whose `mix.lowpass` sits at or under `below_hz`, and whether they are most of the mix.
    Widespread low-pass filtering seldom helps a mix, because most instruments' harmonics and noise reach up the
    spectrum, and it easily dulls one; a low-pass suits a part case by case, such as an amplified guitar's noise in the
    top two octaves (Senior 2012).  Most mixing books put "air" at 10-20 or 12-20 kHz (Moffat, De Man and Reiss 2022):
    a two-pole low-pass at 12 kHz takes 8 dB at 15 kHz and 15 dB at 18 kHz.  Bass parts are left out: their top is
    seldom what a mix lacks.  The 12 kHz, the half and the three parts are this project's choice."""
    parts=[t for t in p['tracks'] if t.get('role')!='bass']
    under={t['id']:(t.get('mix') or {}).get('lowpass') for t in parts if (t.get('mix') or {}).get('lowpass',18000)<=below_hz}
    return {'below_hz':below_hz,'parts':len(parts),'under':under,'most':len(under)>=min_parts and len(under)>=share*len(parts)}

def tempo_range(p,entry,spec):
    """The piece's main tempo against the range its style entry's source gives (`tempo_bpm` in style-maps.json): the
    written tempo most notes start under, as a synced part follows it (surge.part_tempo).  In a closed range a half- or
    double-time reading inside it counts as inside (this project's reading: trap is programmed in half time, WP Trap
    music); a range open at one end is read as written, as doubling would always reach it."""
    from .surge import part_tempo
    bpm=part_tempo(p,{'notes':[n for t in p['tracks'] for n in t['notes']]})
    lo,hi=spec['range'];inside=lambda x:(lo is None or x>=lo) and (hi is None or x<=hi)
    readings=(bpm,bpm*2,bpm/2) if lo is not None and hi is not None else (bpm,)
    return {'entry':entry,'bpm':bpm,'range':[lo,hi],'source':spec['source'],'inside':any(inside(x) for x in readings)}

def highpass_cut(t):
    """dB a part's high-pass takes from the fundamental of its lowest note, with that note and its frequency.  FFmpeg's
    two-pole Butterworth passes r^4/(1+r^4) of the power at r times its cutoff: 3 dB is lost at the cutoff, 1.5 dB a
    major third above it, 0.3 dB an octave above it; review asks about more than 1.5 dB.  None for parts that do not sound at their written pitch (drums, synthesizers with
    octave oscillators, Surge)."""
    if not t['notes'] or t['engine'] not in ('soundfont','additive') or t.get('drums') or (t.get('patch') or t).get('bank',0)==128:return None
    low=min(n['pitch'] for n in t['notes']);f0=440*2**((low-69)/12)
    return 10*math.log10(1+(t['mix'].get('highpass',30)/f0)**4),low,f0

def most_of(counts):
    """The key counted most, or those tied for it, as words: two parts with one note each were said to be "most in" the
    first (the walkthrough of 0.9.1)."""
    counts=dict(counts);top=max(counts.values());tied=[k for k,v in counts.items() if v==top]
    return ' and '.join(tied[:3])+(' and others' if len(tied)>3 else '')

def place_digest(rows,*more):
    """A short digest of where a question's findings lie: every finding's place, parts and pitches, before any list of
    examples is cut, so that a round can tell one that moved under its decision at the same count (a parallel from bar 2
    to bar 3: the text, which names the first, stayed the same)."""
    keys=sorted(json.dumps([x.get('at'),x.get('parts') or x.get('track'),x.get('pitches') or x.get('notes') or x.get('pitch') or x.get('note')],default=str) for x in rows)
    return hashlib.sha256(json.dumps([keys,more],default=str).encode()).hexdigest()[:16]

def where(clock,beat):
    return f'bar {int(beat//clock.beats_per_bar)+1} beat {beat%clock.beats_per_bar+1:g}'

NOTE_COLUMNS=('track','role','note_id','bar_1_based','beat_in_bar','pitch','duration_q','phrase','articulation','velocity','timing_ms','gate','start_seconds','end_seconds')   # notes.csv

def kit(t):
    """A drum part by what it is: the `drums` flag, a drum machine, the role, or a kit's patch (bank 128) written
    without the flag."""
    return bool(t.get('drums') or t['engine']=='drum_synth' or t.get('role')=='drums' or kit_patch(t))

def unpitched(t):
    """Drum and noise parts, synth parts whose oscillators are all noise (a riser, a reverse cymbal, a fall), and
    Surge patches that the catalog measured as having no clear pitch (its flag; 245 of the 3,008): their notes set a
    sweep or a hit, not a pitch heard against chords.  A Surge part is read as the patch it names: on a machine
    without Surge XT it plays its fallback, a built-in preset that may have a pitch, and the render's receipt and
    analyze say that it did (the review of 0.9's step 5; a fallback without a pitch for such patches is not built)."""
    if t.get('drums') or t['engine'] in ('noise','drum_synth'):return True
    if kit_patch(t):return True   # a kit's patch without the flag
    if t['engine']=='surge':
        from . import surge
        return 'no clear pitch' in ((surge.catalog().get(str((t.get('surge') or {}).get('preset',''))) or {}).get('flags') or ())
    if t['engine']=='synth':
        from .synth import patch_of
        try:oscillators=patch_of(t).get('oscillators') or []
        except (KeyError,ValueError):return False
        return bool(oscillators) and all(o.get('wave')=='noise' for o in oscillators)
    return False

def vertical(p,clock,limit=40,sustain_beats=.75,overlap_beats=.5,widest=127,digest=False):
    """Minor seconds/ninths between a sustained note (>=0.75 beat) and any note of another pitched
    part (or inside one part's chord) overlapping >=0.5 beat (both numbers ours: style-maps.json).  Major sevenths are
    not flagged.  Unpitched parts
    (unpitched()) are left out.  The first `limit` examples by beat are kept while the rest are counted.

    `widest` is the widest distance counted, in semitones: 13 takes the minor second and the minor ninth, 25 the
    semitone two octaves wide as well, 127 every octave (what 0.8 counted, and still the default of this function).
    review counts up to 13 (style-maps.json) and gives the wider ones apart: see review().  `digest` adds `places`, a digest
    of where every counted pair lies, those past the examples too (revision.answered_moved).

    0.8 step 1.2: the pairs are counted, not looked at one by one where they are many (0.7 looked at every pair, and
    two parts of 250,000 notes hold 62,500,000,000).  The results are 0.7's to the last example.  A pair is two notes
    1, 13, 25... semitones apart, each lasting overlap_beats or more, overlapping by overlap_beats as 0.7 computed it
    (the earlier end less the later onset, in floats), one of them sustained (its end less its onset at least
    sustain_beats).  Of two long notes e and f with f starting no earlier, they overlap when e's end passes f's onset
    by the overlap: f's own length passes it already, and a rounded difference never shrinks when its first term
    grows or its second falls.  So a note's partners starting after it are a run of the other pitch's long notes in
    onset order, up to the first whose onset its end does not pass by the overlap; with it, they are those starting
    with it.  Each run's ends are found exactly among the long notes' distinct onsets (a binary search of the
    rounded differences themselves), and every pair is counted once, from its earlier note (of one onset, from
    the lower pitch): looked at where its run is short beside the parts at that pitch, counted part by part where it
    is long.  The parts' order (most pairs first, ties in the order 0.7 found their first pair: its outer note in the
    order of the parts and their notes, the pitches by 1, 13, 25... above and below, the partner in the pitch's order)
    and the examples (the earliest beats, ties in that order) are drawn from counts that say which notes hold them."""
    items=[]
    for t in p['tracks']:
        if unpitched(t):continue
        for n in t['notes']:items.append((n['on'],n['on']+n['duration'],n['pitch'],t['id'],t.get('role') in FOREGROUND,n.get('id') or ''))
    if not items:
        return {'count':0,'foreground_count':0,'by_parts':{},'examples':[]}
    import numpy as np
    ob=overlap_beats;N=len(items)
    index={};fg=[]                                    # the parts in order, each with its role (0.7: the note's part's)
    for x in items:
        if x[3] not in index:index[x[3]]=len(fg);fg.append(x[4])
    tids,k=list(index),len(fg)
    on=np.array([x[0] for x in items],dtype=np.float64);end=np.array([x[1] for x in items],dtype=np.float64)
    length=end-on                                     # 0.7's a[1]-a[0]
    long=length>=ob                                   # a pair overlaps by no more than either note lasts
    sust=long&(length>=sustain_beats)
    code=np.array([index[x[3]] for x in items])
    offsets=lambda q:[q+d*s for d in range(1,widest+1,12) for s in (1,-1)]
    # Each pitch's notes in 0.7's order (onset, end, pitch, part, foreground, id), and each note's place there.
    by_pitch=defaultdict(list)
    for i,x in enumerate(items):by_pitch[x[2]].append(i)
    place=np.zeros(N,dtype=np.int64);P={}
    for q,ix in by_pitch.items():
        ix.sort(key=items.__getitem__);P[q]=np.array(ix);place[P[q]]=np.arange(len(ix))
    pitches=sorted(P);rank={q:j for j,q in enumerate(pitches)};pid=np.array([rank[x[2]] for x in items])

    # The long notes: their ends and onsets as ranks among the distinct ones, and keyed by pitch or by group (one
    # pitch and part) with each rank: all of them, and the sustained ones.
    L=np.flatnonzero(long);pL=pid[L];sl=sust[L];cL=code[L]
    V,U=np.unique(end[L]),np.unique(on[L]);W=max(len(V),len(U))+1
    rV,rU=np.searchsorted(V,end[L]),np.searchsorted(U,on[L])
    groups,gid=np.unique(pL*k+cL,return_inverse=True);G=len(groups)
    gpart=groups%k;gstart=np.searchsorted(groups//k,np.arange(len(pitches)+1))  # a pitch's groups lie together

    def keyed(of,n,idx):
        # the ends' keys sorted; the onsets' keys sorted, with the long notes in that order; where each key begins
        KE=np.sort(of[idx]*W+rV[idx]);ko=of[idx]*W+rU[idx];o=np.argsort(ko,kind='stable')
        return KE,ko[o],idx[o],np.searchsorted(KE,np.arange(n+1)*W)
    every,held=np.arange(len(L)),np.flatnonzero(sl)
    pitch_keys=(keyed(pL,len(pitches),every),keyed(pL,len(pitches),held))   # [0]: all long notes, [1]: sustained
    group_keys=(keyed(gid,G,every),keyed(gid,G,held))

    def first(vals,holds):
        # the first index of the sorted distinct vals at which holds(value) is true, holds turning true once along them:
        # a binary search of the rounded comparison itself, since one rounding plateau can hold any number of distinct
        # values (onsets 1e-19 apart all lie 0.5 before an end of 0.5)
        m=len(vals);lo=np.zeros(len(L),dtype=np.int64);hi=np.full(len(L),m,dtype=np.int64)
        while (live:=lo<hi).any():
            mid=(lo+hi)//2;h=holds(vals[np.minimum(mid,m-1)])
            hi=np.where(live&h,mid,hi);lo=np.where(live&~h,mid+1,lo)
        return lo
    z0,z1=on[L],end[L]
    rE=first(V,lambda v:v-z0>=ob)   # ends from here on reach z's onset by ob
    rS=first(U,lambda u:z1-u<ob)    # onsets before here z's end passes by ob

    def tally(zz,ss,keys):
        # long notes zz against sets ss: the members whose end reaches z's onset by the overlap, whose onset z's end
        # passes by it, starting no later than z, starting before z; the set's size and first place
        KE,KS,_,seg=keys;base=ss*W;lo,hi=seg[ss],seg[ss+1]
        return (hi-np.searchsorted(KE,base+rE[zz]),np.searchsorted(KS,base+rS[zz])-lo,np.searchsorted(KS,base+rU[zz],'right')-lo,
                np.searchsorted(KS,base+rU[zz])-lo,hi-lo,lo)

    CAP=1<<20  # elements worked on at once

    def spread(lens):
        # runs of the given lengths in chunks of about CAP elements: each element's run, and its place in the run
        ends=np.cumsum(lens);a=0
        while a<len(lens):
            b=max(a+1,int(np.searchsorted(ends,ends[a]-lens[a]+CAP,'right')));n=lens[a:b]
            yield np.repeat(np.arange(a,b),n),np.arange(ends[a]-lens[a],ends[b-1])-np.repeat(ends[a:b]-n,n)
            a=b

    def add_up(acc,keys,values):
        u,inv=np.unique(keys,return_inverse=True)
        for key,val in zip(u.tolist(),np.bincount(inv,weights=values,minlength=len(u)).tolist()):acc[key]=acc.get(key,0)+val

    near=[np.array([rank[o] for o in offsets(q) if o in rank and pitch_keys[0][3][rank[o]+1]>pitch_keys[0][3][rank[o]]],dtype=np.int64)
          for q in pitches]                           # the offset pitches that hold long notes
    zorder=np.argsort(pL,kind='stable');zstart=np.searchsorted(pL[zorder],np.arange(len(pitches)+1))

    def note_pitch_pairs():
        zs,qs,n=[],[],0
        for j in range(len(pitches)):
            Z,R=zorder[zstart[j]:zstart[j+1]],near[j]
            if not (len(Z) and len(R)):continue
            step=max(1,CAP//len(R))
            for a in range(0,len(Z),step):
                zs.append(np.repeat(Z[a:a+step],len(R)));qs.append(np.tile(R,len(Z[a:a+step])));n+=len(zs[-1])
                if n>=CAP:
                    yield np.concatenate(zs),np.concatenate(qs);zs,qs,n=[],[],0
        if n:yield np.concatenate(zs),np.concatenate(qs)

    # Each long note z against each offset pitch, with any long partner if z is sustained, sustained ones if not: for
    # the examples, its partners starting no later than it (twice those before it, once those with it); and the run of
    # the pairs it starts, counted by pair of parts: looked at where it is no longer than eight times its pitch's
    # groups, else counted group by group (the group's long or sustained notes from z's onset, or after it, to the
    # run's end).
    twice=np.zeros(len(L));pairs_of={};meets=np.zeros(len(L))   # meets: how many pairs each long note is in
    for zz,qq in note_pitch_pairs():
        for s,mine in ((0,sl[zz]),(1,~sl[zz])):  # the partners' set: all long notes, or the sustained ones
            z,q=zz[mine],qq[mine]
            if not len(z):continue
            cE,cS,upto,before,size,lo=tally(z,q,pitch_keys[s])
            twice+=np.bincount(z,weights=2*(cE-size+upto)-(upto-before),minlength=len(L))
            if digest:meets+=np.bincount(z,weights=cE+cS-size,minlength=len(L))
            a,b=lo+np.where(q>pL[z],before,upto),lo+cS
            m=b>a;z,q,a,b=z[m],q[m],a[m],b[m];kq=gstart[q+1]-gstart[q];look=b-a<=8*kq
            for rep,off in spread((b-a)[look]):
                zl,fl=z[look][rep],pitch_keys[s][2][a[look][rep]+off]
                add_up(pairs_of,np.minimum(cL[zl],cL[fl])*k+np.maximum(cL[zl],cL[fl]),np.ones(len(zl)))
            z,q=z[~look],q[~look];KS=group_keys[s][1]
            lo_rank=rU[z]+(q<=pL[z])                  # with z only from the lower pitch
            for rep,off in spread(kq[~look]):
                g=gstart[q[rep]]+off;zr=z[rep];base=g*W
                n=np.searchsorted(KS,base+rS[zr])-np.searchsorted(KS,base+lo_rank[rep]);m=n>0
                add_up(pairs_of,np.minimum(cL[zr[m]],gpart[g[m]])*k+np.maximum(cL[zr[m]],gpart[g[m]]),n[m])
    counted={divmod(key,k):int(n) for key,n in pairs_of.items()}
    count=sum(counted.values());fg_count=sum(n for (a,b),n in counted.items() if fg[a] or fg[b])

    def found_with(i,q,ix):
        # 0.7's partners of outer note i among notes ix of pitch q, in the pitch's order: overlapping long notes, less a
        # sustained one that sorts before i (that pair is found from it)
        a=items[i];b0,b1=on[ix],end[ix]
        before=(b0<a[0])|((b0==a[0])&((b1<a[1])|((b1==a[1])&(q<a[2]))))
        return ix[long[ix]&(np.minimum(a[1],b1)-np.maximum(a[0],b0)>=ob)&~(sust[ix]&before)]

    # The parts' order: most pairs first; where counts tie, the first pair 0.7 found of each.  All of a part's notes
    # come before a later part's, so that pair's outer note is the first of the earlier part that is the outer note
    # of a pair with the other part, or else the first such of the other; its partner, the first in the order of the
    # pitches and of the pitch's notes.  The sustained notes with partners at a pitch where the other part has notes
    # are tried in growing batches, all ties at once.
    ties=Counter(counted.values());first={}
    tied=[key for key,n in counted.items() if ties[n]>1]
    if tied:
        both=rU*W+rV;UB=np.unique(both);NB=len(UB)+1
        rB,nextB=np.searchsorted(UB,both),np.searchsorted(UB,(rU+1)*W)
        KB=np.sort(gid[held]*NB+rB[held])             # the sustained notes by group, onset and end
        partnered=[]                                  # each sustained note with partners at a pitch, by part, then note
        for zz,qq in note_pitch_pairs():
            z,q=zz[sl[zz]],qq[sl[zz]];cE,cS,_,_,size,_=tally(z,q,pitch_keys[0]);partnered.append((z[cE+cS>size],q[cE+cS>size]))
        pz,pq=(np.concatenate(c) for c in zip(*partnered));o=np.lexsort((pq,pz,cL[pz]));pz,pq=pz[o],pq[o]
        pcut=np.searchsorted(cL[pz],np.arange(k+1))

        def outers(asks):
            # for each (a, b) asked: the first sustained note of part a that is the outer note of a pair with part b
            # (a partner of b there not sustained, or sustained and after it in 0.7's order: starting later, or with it
            # and ending later, or ending with it at a higher pitch), or None
            best=[None]*len(asks);live=np.arange(len(asks));at,step=0,64
            start,stop=pcut[[a for a,_ in asks]],pcut[[a+1 for a,_ in asks]];bs=np.array([b for _,b in asks])
            while len(live):
                step=max(1,min(step,CAP//len(live)))  # the batch doubles, at most CAP notes in all
                lo,hi=start[live]+at,np.minimum(stop[live],start[live]+at+step);live,lo,hi=live[hi>lo],lo[hi>lo],hi[hi>lo]
                at+=step;step*=2
                if not len(live):break
                n=hi-lo;owner=np.repeat(live,n);e=np.repeat(lo,n)+np.arange(n.sum())-np.repeat(np.cumsum(n)-n,n)
                key=pq[e]*k+bs[owner];g=np.minimum(np.searchsorted(groups,key),G-1);m=groups[g]==key
                if not m.any():continue
                z,g,w=pz[e[m]],g[m],owner[m]
                cE,cS,upto,_,size1,_=tally(z,g,group_keys[0]);cE2,cS2,upto2,_,size2,_=tally(z,g,group_keys[1])
                k0,k1=g*NB+rB[z],g*NB+nextB[z];e0,e1=np.searchsorted(KB,k0),np.searchsorted(KB,k0,'right')
                outer=(cE+cS-size1)-(cE2+cS2-size2)+(cS2-upto2)+np.searchsorted(KB,k1)-e1+np.where(groups[g]//k>pL[z],e1-e0,0)>0
                if not outer.any():continue
                least=np.full(len(asks),len(L));np.minimum.at(least,w[outer],z[outer])
                for t in np.flatnonzero(least<len(L)):best[t]=int(L[least[t]])
                live=live[least[live]==len(L)]
            return best
        firsts=outers(tied)
        again=[t for t,i in enumerate(firsts) if i is None]
        for t,i in zip(again,outers([tied[t][::-1] for t in again]) if again else ()):firsts[t]=i
        srt=np.lexsort((place,code,pid));ps,cs=pid[srt],code[srt]   # each part's notes of a pitch, in the pitch's order
        cut=np.flatnonzero(np.r_[True,(ps[1:]!=ps[:-1])|(cs[1:]!=cs[:-1]),True])
        part_at={(pitches[ps[s]],int(cs[s])):srt[s:e] for s,e in zip(cut[:-1].tolist(),cut[1:].tolist())}
        for (a,b),i in zip(tied,firsts):
            other=b if code[i]==a else a
            for qi,q in enumerate(offsets(items[i][2])):
                hit=found_with(i,q,part_at[(q,other)]) if (q,other) in part_at else ()
                if len(hit):first[(a,b)]=(i,qi,int(place[hit[0]]));break
    by_parts={' / '.join(sorted({tids[a],tids[b]})):counted[(a,b)] for a,b in sorted(counted,key=lambda key:(-counted[key],first.get(key,())))}

    # The examples: the `limit` pairs of the earliest beats, ties in 0.7's order of finding them.  A pair's beat is its
    # later onset.  The count for each note of its pairs with partners starting no later than it (a pair of one onset
    # half from each side) gives the beat B by which `limit` pairs have begun: every pair before B is drawn, from its
    # later note; then the first pairs at B in 0.7's order, from the outer notes counted to hold some.
    found=[]
    if limit>0 and count:
        tw=np.zeros(N);tw[L]=twice
        by_onset=np.argsort(on,kind='stable');cum=np.cumsum(tw[by_onset]);o=on[by_onset]
        reach=np.flatnonzero(np.r_[o[1:]!=o[:-1],True]&(cum>=2*limit))  # at the last note of an onset
        B=o[reach[0]] if len(reach) else np.inf
        chosen={}

        def add(i,j):
            a,b=(i,j) if sust[i] and (not sust[j] or items[i]<items[j]) else (j,i)
            chosen.setdefault((a,b),(max(items[a][0],items[b][0]),a,offsets(items[a][2]).index(items[b][2]),int(place[b])))
        for z in np.flatnonzero((on<B)&(tw>0)):  # every pair before B, found from its later note
            z=int(z)
            for q in set(offsets(items[z][2]))&P.keys():
                ix=P[q];m=long[ix]&(on[ix]<=on[z])&(end[ix]-on[z]>=ob)
                if not sust[z]:m&=sust[ix]
                for j in ix[m]:add(z,int(j))
        need=limit-len(chosen)
        if need>0 and B<np.inf:
            # The outer notes of pairs at B are sustained notes sounding at B.  One starting before B pairs with every
            # long note at an offset pitch starting at B; one starting at B, with the long notes not sustained that
            # reach past B by the overlap, and with the sustained ones starting at B after it in 0.7's order.
            span=np.flatnonzero(sust&(on<=B)&(end-B>=ob))
            starting=np.bincount(pid[long&(on==B)],minlength=len(pitches))
            reaching=np.bincount(pid[long&~sust&(on<=B)&(end-B>=ob)],minlength=len(pitches))
            pairs_at=np.where(on[span]<B,np.array([starting[r].sum() for r in near])[pid[span]],
                              np.array([reaching[r].sum() for r in near])[pid[span]])
            with_b=on[span]==B
            if with_b.any():
                sb=np.flatnonzero(sust&(on==B));sb=sb[np.lexsort((end[sb],pid[sb]))]  # by pitch, then end
                cut=np.searchsorted(pid[sb],np.arange(len(pitches)+1))
                for j in np.unique(pid[span[with_b]]):
                    here=np.flatnonzero(with_b&(pid[span]==j))
                    for r in near[j]:
                        e=end[sb[cut[r]:cut[r+1]]]  # after it: a later end, or the same end at a higher pitch
                        if len(e):pairs_at[here]+=len(e)-np.searchsorted(e,end[span[here]],'left' if r>j else 'right')
            for i in span[pairs_at>0]:
                i=int(i)
                for q in offsets(items[i][2]):
                    if q not in P:continue
                    hit=found_with(i,q,P[q]);hit=hit[on[hit]<=B] if on[i]==B else hit[on[hit]==B]
                    for j in hit[:need]:add(i,int(j))
                    need=limit-len(chosen)
                    if need<=0:break
                if need<=0:break
        for (ai,bi),_ in sorted(chosen.items(),key=lambda kv:kv[1])[:limit]:
            a,b=items[ai],items[bi];ov=min(a[1],b[1])-max(a[0],b[0]);beat=max(a[0],b[0])
            pair=sorted([(a[2],a[5]),(b[2],b[5])])  # the lower pitch first, each with its note's id
            found.append({'at':where(clock,beat),'beat':round(beat,4),'parts':sorted({a[3],b[3]}),'pitches':[x[0] for x in pair],'ids':[x[1] for x in pair],'overlap_beats':round(ov,3),'involves_foreground':a[4] or b[4],'same_part':a[3]==b[3]})
    out={'count':count,'foreground_count':fg_count,'by_parts':by_parts,'examples':found}
    if digest:
        # Each note in a pair by onset, end, pitch, part and how many it is in, and how many pairs hold a foreground part; a part by
        # its name, among those in a pair, so that neither the parts' order nor a part that meets nothing changes it.
        hit=meets>0;names=sorted({tids[c] for c in np.unique(cL[hit]).tolist()});place={x:k for k,x in enumerate(names)}
        rows=np.column_stack((z0[hit],z1[hit],np.array(pitches,dtype=np.float64)[pL[hit]],np.array([place.get(x,-1) for x in tids])[cL[hit]],meets[hit]))
        out['places']=hashlib.sha256(rows[np.lexsort(rows.T[::-1])].tobytes()+json.dumps([names,fg_count]).encode()).hexdigest()[:16]
    return out

def exposed(p,clock,widest=13,beats=1.0,limit=40):
    """The clashes vertical() counts up to `widest` semitones that begin on a downbeat or a half-bar and sound
    together `beats` or more: (how many, the `limit` longest together, longest first).  Each row is as one of
    vertical()'s examples, with `semitones`, `place` ("downbeat", "half-bar") and `tracks` (the lower note's part,
    the higher's).  A clash begins where the later of its two notes does.  The places are the two strongest of the
    bar's metric levels (_metric_weight, after Longuet-Higgins and Lee 1984; a bar of three beats has no half-bar);
    the length is ours (style-maps.json, the check `clash`).

    Places and lengths are read as written, on the grid the piece is played on (TPQ ticks a quarter), one way for the
    place, its name and the length: a note a rounding error before the bar line is on it and is named by its bar,
    and a length that a tick does not tell from a beat is a beat (the review of 0.9's step 4: read as floats, a
    place and its name disagreed).  The performance's timing and gates are not read.

    Counted from how many notes sound at each strong beat, not pair by pair: at a strong beat B the clashes are a
    note struck at B with a note a semitone or a ninth from it that sounds at B, both lasting to B and `beats` more
    (two struck together are taken once, from the lower).  Only the `limit` longest are made into rows, from each
    strong beat's `limit` longest partners."""
    import heapq
    import numpy as np
    meter=_meter(p);bar=round(meter[0]*TPQ);half=None if meter[1] is None else round(meter[1]*TPQ);need=round(beats*TPQ)
    meta=[];raw=defaultdict(list)
    for t in p['tracks']:
        if unpitched(t):continue
        fg=t.get('role') in FOREGROUND
        for n in t['notes']:
            on,end=tick_of(n['on']),tick_of(n['on']+n['duration'])   # as the exported MIDI has them (model.tick_of)
            if end-on>=need:raw[n['pitch']].append((on,end,len(meta)));meta.append((t['id'],fg,n.get('id') or ''))
    by={q:np.array(sorted(v),dtype=np.int64).reshape(-1,3) for q,v in raw.items()}
    struck=defaultdict(list)                          # strong beat -> [(pitch, rows of that pitch's notes struck there)]
    for q,arr in by.items():
        on=arr[:,0];strong=(on%bar==0)|((on%bar==half) if half is not None else False)
        for B in np.unique(on[strong]):struck[int(B)].append((q,np.flatnonzero(on==B)))
    count=0;best=[]                                   # a heap of the `limit` longest: (overlap, -beat, -low pitch, -high pitch, sequence)
    def keep(key,row):
        if len(best)<limit:heapq.heappush(best,(key,row))
        elif key>best[0][0]:heapq.heapreplace(best,(key,row))
    for B in sorted(struck):
        sounding={}
        def partners(r):
            if r not in sounding:
                arr=by[r];idx=np.flatnonzero((arr[:,0]<=B)&(arr[:,1]>=B+need));sounding[r]=idx
            return sounding[r]
        for q,mine in struck[B]:
            for d in range(1,widest+1,12):
                for r in (q+d,q-d):
                    if r not in by:continue
                    theirs=partners(r)
                    if r<q:theirs=theirs[by[r][theirs,0]<B]      # struck together: taken from the lower note's side
                    if not len(theirs):continue
                    count+=len(mine)*len(theirs)
                    ends=by[r][theirs,1]
                    top=theirs[np.argsort(-ends,kind='stable')[:limit]] if len(theirs)>limit else theirs
                    for i in mine:
                        a=by[q][i]
                        for j in top:
                            b=by[r][j];together=int(min(a[1],b[1]))-B
                            lo,hi=((q,a),(r,b)) if q<r else ((r,b),(q,a))
                            keep((together,-B,-lo[0],-hi[0],-int(lo[1][2]),-int(hi[1][2])),(B,together,lo,hi,d))
    rows=[]
    for _,(B,together,(ql,nl),(qh,nh),d) in sorted(best,key=lambda x:x[0],reverse=True):
        ml,mh=meta[int(nl[2])],meta[int(nh[2])];beat=B/TPQ
        rows.append({'at':where(clock,beat),'beat':round(beat,4),'parts':sorted({ml[0],mh[0]}),'pitches':[ql,qh],'ids':[ml[2],mh[2]],
                     'overlap_beats':round(together/TPQ,3),'involves_foreground':ml[1] or mh[1],'same_part':ml[0]==mh[0],
                     'semitones':d,'place':'downbeat' if B%bar==0 else 'half-bar','tracks':[ml[0],mh[0]]})
    return count,rows

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
        kinds=Counter();ids={(n['pitch'],round(n['on'],4)):n.get('id') for n in t['notes']}
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
                    found.append({'track':t['id'],'role':t.get('role'),'at':where(clock,first),'beat':round(first,4),'id':ids.get((pitch,round(s0,4))),'struck':where(clock,s0),'pitch':pitch,'note':note_name(pitch),'chord':ch['sounding'],'held_into_chord':held,'approach':MOTION[approach],'departure':'held on' if continues else MOTION[departure]})
        if kinds:tracks[t['id']]={'role':t.get('role'),'outside_chord':dict(kinds)}
    found.sort(key=lambda x:x['beat']);groups={}
    for g,test in (('melody',lambda r:r in FOREGROUND),('bass',lambda r:r=='bass'),('accompaniment',lambda r:r not in FOREGROUND and r!='bass')):
        xs=[x for x in found if test(x['role'])]
        if xs:groups[g]={'count':len(xs),'most_in':most_of(Counter(x['track'] for x in xs)),'first':xs[0],'places':place_digest(xs)}
    # A long list keeps the foreground's first, then the bass's: cut by time alone, it held accompaniment only (a run of 0.9.1).
    kept=found if len(found)<=limit else sorted(sorted(found,key=lambda x:(x['role'] not in FOREGROUND,x['role']!='bass',x['beat']))[:limit],key=lambda x:x['beat'])
    return {'count':len(found),'not_resolved_by_step':groups,'tracks':tracks,'examples':kept,'unparsed_symbols':unknown}

def parallels(p,clock,window=8,doubled_share=.75,limit=40,run=4):
    """Two perfect consonances of the same size in a row, fifths or octaves (with unisons), between two lines
    (line_of) moving the same way: both voices go from one note to their next at the same moment, with no rest of
    more than half a beat.  Open Music Theory forbids them in counterpoint, as they fuse the two voices
    (First-Species Counterpoint).  Octaves where the two lines meet at the octave or unison in at least
    `doubled_share` of the `window` attacks they share around them are one line doubled to blend, not two voices
    (climax-and-melody.md, Blend), and are counted apart; a window and share of our choosing.  So are octaves inside a
    run of `run` attacks or more that the two parts share one after another, all at the octave or unison: where a doubled passage ends and the
    parts move apart, the window round its last notes holds what follows, and they were counted as parallels (most of
    the octaves three real pieces of 0.8.0 answered as "doubled on purpose": 33 of 50, 63 of 71, 11 of 11)."""
    lines={t['id']:ln for t in p['tracks'] if t['notes'] and not unpitched(t) for ln in [line_of(t)] if ln and len(ln)>1}
    ids=sorted(lines);found=[];doubled=Counter()
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            A,B=lines[a],lines[b];at={round(n['on'],3):j for j,n in enumerate(B)}
            shared=[(k,at[round(n['on'],3)]) for k,n in enumerate(A) if round(n['on'],3) in at]
            size=[{7:'fifths',0:'octaves'}.get(abs(A[k]['pitch']-B[j]['pitch'])%12) for k,j in shared]
            joined=lambda L,u:L[u]['on']+L[u]['duration']>=L[u+1]['on']-.5-1e-9
            # the length of the run of octaves each shared attack lies in (0 outside one): attacks the two parts
            # share one after another, neither with a note of its own between (two pairs of octaves with such notes
            # between them were read as one run of four: the review of 0.9's step 5)
            runs=[0]*len(size);m=0
            while m<len(size):
                e=m
                while e<len(size) and size[e]=='octaves' and (e==m or shared[e]==(shared[e-1][0]+1,shared[e-1][1]+1)):e+=1
                runs[m:e]=[e-m]*(e-m);m=max(e,m+1)
            for m in range(1,len(shared)):
                (k1,j1),(k2,j2)=shared[m-1],shared[m]
                if size[m] is None or size[m]!=size[m-1] or (k2,j2)!=(k1+1,j1+1) or not (joined(A,k1) and joined(B,j1)):continue
                if (A[k2]['pitch']-A[k1]['pitch'])*(B[j2]['pitch']-B[j1]['pitch'])<=0:continue
                around=size[max(0,m-window//2):m+window//2]
                if size[m]=='octaves' and (runs[m]>=run or len(around)>=4 and around.count('octaves')>=doubled_share*len(around)):
                    doubled[' / '.join((a,b))]+=1;continue
                found.append({'parts':[a,b],'at':where(clock,A[k2]['on']),'beat':round(A[k2]['on'],4),'interval':size[m],'pitches':[[A[k1]['pitch'],B[j1]['pitch']],[A[k2]['pitch'],B[j2]['pitch']]]})
    found.sort(key=lambda x:x['beat'])
    return {'count':len(found),'by_pair':dict(Counter(' / '.join(x['parts']) for x in found).most_common()),'examples':found[:limit],'places':place_digest(found),'octaves_in_doublings':dict(doubled.most_common())}

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
    return {'count':len(found),'by_parts':dict(Counter(' / '.join(x['parts']) for x in found).most_common()),'furthest_below':worst,'examples':found[:limit],'places':place_digest(found)}

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

def _curve_value(points,beat,step):
    """A [beat, value] curve at `beat`, as the render plays it: linear between points, the later of two points on one
    beat winning (model.curve_at), or, in step mode, each value held until the next point; the first value before the
    first point, the last after the last."""
    i=bisect.bisect_right([b for b,_ in points],beat)
    if i==0:return points[0][1]
    if step or i==len(points):return points[i-1][1]
    (b0,v0),(b1,v1)=points[i-1],points[i]
    return v0 if b1==b0 else v0+(v1-v0)*(beat-b0)/(b1-b0)

def _curve_moves(points,lo,hi,step=False):
    """Whether a [beat, value] curve changes in the span [lo, hi) of beats: at its start, or anywhere inside it.  The
    curve is read just before the span, just after its start, either side of every point inside it and just before
    its end: piecewise linear (or held), it is constant over the span exactly when all those agree."""
    if len(points)<2:return False
    pts=sorted(points,key=lambda x:x[0]);e=1e-6
    probes=[lo-e,lo+e,hi-e]+[b+d for b,_ in pts if lo<b<hi for d in (-e,e)]
    return len({round(_curve_value(pts,x,step),6) for x in probes})>1

def processes(p,lo,hi):
    """What moves a part's sound in the span [lo, hi) of beats while its notes may repeat: a filter sweep, the gain
    automation, a continuous controller's curve (the mod wheel opening a Surge patch's filter, expression, brightness;
    the switch controllers 64-69, the pedals, and the bank and mode controllers left out).  The continuous processes of
    dance music are pitch slides, crescendos, fades, filter sweeps and timbre changes (Smith 2021)."""
    out=[]
    for t in p['tracks']:
        mix=t.get('mix') or {};perf=t.get('performance') or {}
        if _curve_moves((mix.get('filter_sweep') or {}).get('points') or [],lo,hi):out.append(f'{t["id"]}: filter sweep')
        if _curve_moves(mix.get('automation') or [],lo,hi):out.append(f'{t["id"]}: automation')
        if mix.get('move'):
            from . import move
            if move.moves(mix['move'],mix.get('pan',0),Clock(p),lo,hi):out.append(f'{t["id"]}: movement across the image')
        step=perf.get('cc_mode','linear' if t['engine']=='additive' else 'step')=='step';by=defaultdict(list)
        for b,c,v in perf.get('cc',[]):
            if not (64<=c<=69 or c in (0,32) or c>=120):by[c].append((b,v))
        out+=[f'{t["id"]}: CC{c}' for c in sorted(by) if _curve_moves(by[c],lo,hi,step)]
    return out

def repetition(p,clock,static_bars=16,pitched_loop_bars=24,percussion_loop_bars=33,lower_measures=2,density_share=.1,velocity=3,processes_vary=False):
    """Where nothing changes: (1) spans of at least `static_bars` bars in which every part repeats the same block of
    1, 2, 4 or 8 bars note for note; with `processes_vary` (the dance styles' map entries: loops change by process,
    Smith 2021, Garcia 2005), each span also records what moves its sound (`processes`) and the runs of at least
    `static_bars` bars inside it in which nothing does (`still`); (2) parts that repeat a 1-, 2- or 4-bar cycle unchanged for at least
    `pitched_loop_bars` bars (a pitched part) or `percussion_loop_bars` (a percussion part): dance music is phrased in
    multiples of two bars at several levels, new sounds entering at the downbeats of those phrases (Smith 2021, after
    Snoman 2019), so a loop held past one or two 16-bar phrases is a question; (3) sections that return note for note in every part; (4) arrival sections (named chorus,
    hook, drop, climax, peak, summit, final or refrain, a pre-chorus not counted) thinner than the section before them in at least two of notes
    per bar, parts and velocity; (5) neighbouring sections with the same parts, notes per bar within 10% and velocity
    within 3.  Moderate novelty is liked best (Chmiel and Schubert 2017): questions, not faults.  The numbers are ours,
    set on the project's early pieces (style-maps.json); a style's map entry may give its own."""
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
    if processes_vary:
        for s in static:
            moving=[processes(p,k*bpb,(k+1)*bpb) for k in range(s['from_bar']-1,s['to_bar'])];runs=[];start=None
            for k,m in enumerate(moving+[['end']]):
                if not m and start is None:start=k
                elif m and start is not None:
                    if k-start>=static_bars:runs.append({'from_bar':s['from_bar']+start,'to_bar':s['from_bar']+k-1,'bars':k-start})
                    start=None
            s['processes']=sorted({x for m in moving for x in m});s['still']=runs
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
        if _arrival(b['section']) and not _arrival(a['section']) and lower>=lower_measures:
            weak.append({'section':b['section'],'after':a['section'],'notes_per_bar':[a['notes_per_bar'],b['notes_per_bar']],'parts':[len(a['parts']),len(b['parts'])],'mean_velocity':[a['mean_velocity'],b['mean_velocity']]})
        if a['notes_per_bar'] and set(a['parts'])==set(b['parts']) and abs(b['notes_per_bar']/a['notes_per_bar']-1)<density_share and abs(b['mean_velocity']-a['mean_velocity'])<velocity:
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

def attack_kinds(onsets,bpb,meter,end):
    """For each attack of a part (`onsets`, its distinct attack times in beats, sorted): (onset, syncopated, push).  An
    attack is syncopated when the next stronger position of the bar comes before the part's next attack, the note held
    over that position or stopped before it: a weak-beat note with a rest or a continuation on the following strong
    beat (Longuet-Higgins and Lee 1984; Huron and Ommen 2006, as Tan, Lustig and Temperley 2019 give it).  A push is a
    syncopated attack at most half a beat before a downbeat or half-bar.  `end` is the piece's last beat: the last
    attack has no next one, and a stronger position at or past the end is none.  (stiffness counts by this; so does
    views.melody_rhythm, so the two give one figure.)"""
    _,half,levels=meter;grids=tuple(sorted({*levels,*(() if half is None else (half,)),bpb}));out=[]
    for k,on in enumerate(onsets):
        w=_metric_weight(on%bpb,meter);nxt=onsets[k+1] if k+1<len(onsets) else end
        stronger=next((q for q in (math.floor(on/s+1e-9)*s+s for s in grids) if _metric_weight(q%bpb,meter)>w),None)
        sync=stronger is not None and stronger<end and nxt>stronger+1e-6
        out.append((on,sync,bool(sync and _metric_weight(stronger%bpb,meter)>=4 and stronger-on<=.5+1e-9)))
    return out

def stiffness(p,clock,block_share=.9,min_chords=8):
    """Where the parts move as blocks: chord parts (three or more pitch classes, power chords left out) that strike and
    release at least `block_share` of their chords together, the voices never moving apart, when the chords are held
    (a median of two beats or more) or keep one length (at least three in four alike); syncopated stabs and comping of
    varied lengths are a rhythm, not stiffness.  Also, per pitched part, the
    share of its attacks that are syncopated (the last attack before a stronger position that is itself left without an
    attack, held over or rested: Longuet-Higgins and Lee 1984; in 6/8, 9/8 and 12/8 the beats are dotted, _meter) and of those that anticipate a downbeat or half-bar by
    an eighth or less, the push of pop, rock and J-pop (Tan, Lustig and Temperley 2019).  Medium syncopation is the most
    groove-inducing (Witek et al. 2014); none at all in melody and accompaniment is asked about, as a question of style."""
    bpb=clock.beats_per_bar;blocks=[];parts={};end=p['clock']['bars']*bpb;meter=_meter(p)
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
        onsets=sorted(by_on);kinds=attack_kinds(onsets,bpb,meter,end)
        sync=sum(1 for _,s,_ in kinds if s);push=sum(1 for _,_,q in kinds if q)
        parts[t['id']]={'role':t.get('role'),'attacks':len(onsets),'syncopated_pct':round(100*sync/len(onsets),1),'downbeat_pushes_pct':round(100*push/len(onsets),1)}
    lines=[v for v in parts.values() if v['role'] in ('melody','countermelody','harmony','rhythm','bass','texture')]
    no_push=bool(lines) and all(v['downbeat_pushes_pct']==0 for v in lines)
    return {'block_chord_parts':blocks,'parts':parts,'no_pushes_anywhere':no_push}

def transposition(bank,bank_no,program,spent=None):
    """Key -> semitones between the key and the recorded pitch of the sample that plays it in a preset (the smallest
    among the zones covering the key; coarse tune counts), over the zone pairs that sound (instruments.pairs: global
    zones, keys and velocities together). None when the bank has no such preset."""
    pre=next((x for x in bank['presets'] if x['bank']==bank_no and x['program']==program),None)
    if pre is None:return None
    shift={}
    for _,z,top,(lo,hi),_ in pairs(bank,pre,spent):
        g=z['gens'];root=g.get(58,top.get(58,bank['samples'][z['target']]['root']));coarse=g.get(51,top.get(51,0))
        for k in range(lo,hi+1):
            d=k-root+coarse
            if k not in shift or abs(d)<abs(shift[k]):shift[k]=d
    return shift
def sample_maps(p,config):
    """transposition() for every pitched SoundFont part, reading each configured bank once."""
    from . import audio,sf2
    banks,maps,made={},{},{}   # each preset's map made once, the pairs it looks at bounded a bank (the fourth review)
    for t in p['tracks']:
        if t['engine']!='soundfont' or t.get('drums') or t.get('key_map'):continue
        _,font=audio.soundfont_for(config,t)
        if font['path'] not in banks:banks[font['path']]=(sf2.read(font['path']),[0])
        patch=t.get('patch') or {'bank':t.get('bank',0),'program':t.get('program',0)}
        k=(font['path'],patch.get('bank',0),patch.get('program',0))
        if k not in made:made[k]=transposition(banks[font['path']][0],k[1],k[2],banks[font['path']][1])
        maps[t['id']]=made[k]
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
            if d is None:silent.append({'track':t['id'],'at':where(clock,n['on']),'pitch':n['pitch'],'key_ranges':key_ranges(shift)})   # the runs: a hole inside them too
            elif abs(d)>limit:
                far.append({'track':t['id'],'at':where(clock,n['on']),'pitch':n['pitch'],'semitones':d})
                b=by[t['id']];b['notes']+=1
                if b['worst'] is None or abs(d)>abs(b['worst']['semitones']):b['worst']={'pitch':n['pitch'],'semitones':d,'at':where(clock,n['on'])}
    return {'limit_semitones':limit,'count':len(far),'by_track':dict(sorted(by.items(),key=lambda kv:-kv[1]['notes'])),'examples':far[:examples],'places':place_digest(far),'outside_preset':silent[:examples],'outside_count':len(silent)}
def outside_keys(st):
    """review's question on notes no zone of their preset covers (stretched()): the count, the first three by part, place
    and name with the keys their preset has, and the fix (0.8 step 2.1: it gave the count alone)."""
    runs=lambda r:', '.join(note_name(a) if a==b else f'{note_name(a)} to {note_name(b)}' for a,b in r)
    named=[f'{x["track"]} at {x["at"]}, {note_name(x["pitch"])}'+(f' (its preset has samples for {runs(x["key_ranges"])})' if x.get('key_ranges') else '')
           for x in st['outside_preset'] if 'pitch' in x][:3]
    return (f'{st["outside_count"]} notes fall on keys their preset has no sample for and will not sound'
            +(': '+'; '.join(named)+('; ...' if st['outside_count']>len(named) else '') if named else '')+'. Move them onto those keys, or give them to an instrument that has them.')
# The acoustic pianos of the banks other than the Steinway grand (vcsl 0:0), by bank, bank number and program; 'default'
# is a SoundFont part that names no bank, on the General MIDI bank every installation has.
OTHER_PIANOS={('piano_osiris',0,0):'the Osiris piano',('piano_osiris',1,0):'the Osiris piano recorded with the pedal held',
              ('vcsl_keys',0,1):'the Kawai grand',('vcsl_keys',0,3):'the Yamaha upright',('vcsl_keys',1,3):'the Knight upright',
              ('vsco_colors',0,0):'the VSCO upright',('default',0,0):"the default bank's Acoustic Grand",
              ('default',0,1):"the default bank's Bright Acoustic"}
def identifier(kind,*names):
    """A question's identifier: its kind and, after a colon, the names it is about (a part, a section, two sections),
    joined by plus signs.  In a name a per cent sign is written %25 and a plus sign %2B, and in the whole a space
    after a colon is written %20, so that no two questions about different names share an identifier and none holds
    a colon followed by a space: the text before a decision's first colon and space is one identifier.  The section
    "answer: reprise" gives "plan:answer:%20reprise" and "answer:reprise" gives "plan:answer:reprise" (with the space
    taken out the two were one: the third review, N3); the pairs ("a+b", "c") and ("a", "b+c") give
    "sections_alike:a%2Bb+c" and "sections_alike:a+b%2Bc" (escaped after joining, both were a+b+c: the fourth, T1)."""
    qid=kind+(':'+'+'.join(str(n).replace('%','%25').replace('+','%2B') for n in names) if names else '')
    while ': ' in qid:qid=qid.replace(': ',':%20')
    return qid
def own_banks(config):
    """The names of a configuration's banks that are the project's own, whose presets are known: a named bank that is
    one of the project's builds (its `version` says `build b...`, as fetch_soundbanks.py and soundbank.py write it),
    and 'default' where the default bank is the one the setup installs (runtime-lock.json), a General MIDI bank.  A
    bank someone configured themselves may hold anything at any program."""
    names={name for name,e in (config.get('soundfonts') or {}).items() if isinstance(e,dict) and str(e.get('version','')).startswith('build b')}
    lock=Path(__file__).resolve().parents[2]/'references'/'runtime-lock.json'
    try:pinned={d.get('sha256') for d in json.loads(lock.read_text(encoding='utf-8'))['downloads'] if d.get('id')=='soundfont'}
    except (OSError,ValueError,KeyError,TypeError,AttributeError):pinned=set()
    default=config.get('soundfont')
    if isinstance(default,dict) and default.get('sha256') in pinned:names.add('default')
    return names
def piano_choice(p,installed):
    """A question for each piano part played on another piano than the Steinway grand, where `installed` (the names of
    the configured banks) has the Steinway's bank: [(identifier, text)].  The Steinway is the piano for every piano
    part (piano-and-chamber.md); another is kept on the user's word or for a sound the piece is built on, and a
    decision beginning with the identifier says which.  Parts without notes, drum parts and parts with a key map are
    left out, and so is everything where the bank is not installed: there is nothing to move the part to.  `installed`
    is own_banks(config): program 0 of a default bank that someone configured themselves may be an organ, and was
    asked about as the Acoustic Grand (the second review, R5)."""
    if 'vcsl' not in installed:return []
    asked=[]
    for t in p['tracks']:
        if t['engine']!='soundfont' or t.get('drums') or t.get('key_map') or not t['notes']:continue
        patch=t.get('patch') or {'bank':t.get('bank',0),'program':t.get('program',0)}
        bank,b,pr=t.get('soundfont','default'),patch.get('bank',0),patch.get('program',0)
        name=OTHER_PIANOS.get((bank,b,pr)) if bank in installed else None   # a bank that is not the project's own may hold anything there
        if name:asked.append((identifier('piano',t['id']),f'{t["id"]}: plays {name} ({bank} {b}:{pr}). The piano for every piano part is the Steinway grand ("soundfont": "vcsl", bank 0, program 0; piano-and-chamber.md): move the part to it, and make it brighter or closer in the mix, not by changing the piano. Keep this one only where the user asked for it or the piece is built on its own sound (a worn upright for lo-fi or a bar room, the closeness of the Osiris in slow, sparse music), and say which in a decision that begins "{identifier("piano",t["id"])}: ".'))
    return asked
OFF_PITCH=.5   # semitones a note may stay from its written pitch through a bend before it is asked about: a quarter-tone
BENT=('soundfont','additive','synth','surge')   # the engines that play `performance.bend` (a drum machine or a noise part has no pitch to bend)
def beyond(v0,v1,limit):
    """How much of a straight stretch from v0 to v1 lies at or beyond +-limit, from 0 to 1."""
    if v0==v1:return float(abs(v0)>=limit)
    lo,hi=min(v0,v1),max(v0,v1)
    return (max(0,hi-max(lo,limit))+max(0,min(hi,-limit)-lo))/(hi-lo)
def bends_across(t,clock,actual=None):
    """The notes that `performance.bend` keeps a quarter-tone or more off their written pitch for most of the time they
    sound, as (beat, the furthest it goes in semitones).  The wheel runs straight from each point to the next and holds
    the last, so a scoop written as one point before its note ramps from the last point across every note between (two
    runs of 0.9.1, one with 51 of 299 notes, the median 118 cents off; no check saw it), and a bend never brought back
    leaves every later note off.  The time is measured and not sampled, stretch by stretch of the curve and the tempo: a
    regular vibrato of 60 cents is past 50 for under a fifth of a note, and sixteen samples could all land on its peaks.
    A note's own short scoop is not counted.  A reversed part is played without the wheel (render.reversed_notes)."""
    if t['engine'] not in BENT or t.get('reverse'):return []
    curve=bend_curve(t['performance'].get('bend') or [])
    if not curve:return []
    out=[];marks=sorted({b for b,_ in curve}|set(clock.beats))
    for a in (sounded(t,clock) if actual is None else actual):
        s0,s1=a['start_seconds'],a['end_seconds']
        if s1<=s0:continue
        b0,b1=clock.beat(s0),clock.beat(s1);cuts=[b0,*marks[bisect.bisect_right(marks,b0):bisect.bisect_left(marks,b1)],b1];off=furthest=0.0
        for x,y in zip(cuts,cuts[1:]):
            v0=curve_at(curve,x);v1=2*curve_at(curve,(x+y)/2)-v0   # straight from x to y, y as it is reached and before any jump there
            off+=(clock.seconds(y)-clock.seconds(x))*beyond(v0,v1,OFF_PITCH);furthest=max(furthest,v0,v1,key=abs)
        if off>(s1-s0)/2+1e-6:out.append((round(b0,4),furthest))   # (exactly half is not most, whatever the rounding of the seconds)
    return sorted(out)
def bend_question(t,clock,actual=None):
    """The review's question on bends_across, as (identifier, text), or None."""
    across=bends_across(t,clock,actual)
    if not across:return None
    off=max((v for _,v in across),key=abs)*100
    return (identifier('bend',t['id']),f'{t["id"]}: {len(across)} note{"s stay" if len(across)!=1 else " stays"} a quarter-tone or more off the written pitch through most of {"their" if len(across)!=1 else "its"} length because of `performance.bend` (first at {where(clock,across[0][0])}; up to {abs(off):.0f} cents {"flat" if off<0 else "sharp"}). The wheel runs straight from each point to the next and holds the last: a scoop written as one point before its note ramps across the notes before it, and a bend not brought back leaves the notes after it off. Put a point at 0 just before each scoop and where a bend ends. If this is meant (a held bend, a long glide), say so in decisions.')
SUSTAINED=('harmony','texture','pad')   # the roles whose notes are held for the sound to fill the time (0.10, sound_decay)
PROBE_HOLD=1.2   # seconds the catalog's probe note is held (scripts/surge_catalog.py): how far `decays` was measured
def sound_of(t,config=None):
    """What a Surge or built-in synth part sounds like as it plays (0.10 step 3d): {'what': its name, 'attack_s': seconds
    to half its level, 'decays': whether it dies 12 dB away within the probe's 1.2 s hold, 'from': where the figures come
    from, 'track': the part as its engine plays it}, a figure None where nothing gives it; None for another engine.  With
    a configuration under which Surge XT does not play the part (surge_plays: surge.locate's checks short of its hashes) a
    Surge part plays its fallback preset on the built-in synth, and that is what is read; without a configuration Surge XT
    is taken to play it.  A Surge patch: the catalog's figures (a curated one its own attack and no decay, as the catalog's
    copy of its file may be played at another octave); with `swell`, macros, `velocity_to_cutoff`, or a mod wheel (CC1)
    moved on a patch whose wheel moves anything, neither, as each plays the patch otherwise than at the saved settings and
    the wheel at rest it was measured at (the Astra reviews of step 3 and of the whole of 0.10, GPT Pro's reviews of 0.10).  A built-in preset: the amplitude envelope of the patch as the synth builds it
    (synth.patch_of: a part's own `amp` replaces the preset's whole), half its attack time, as it rises in a straight line
    to full level, and its level at the end of the hold against the most it reached by then, so a slow attack still
    rising is not taken for dying away (the Astra review of step 3)."""
    from . import surge,synth
    if t['engine']=='surge':
        spec=t.get('surge') or {};name=spec.get('preset');found=surge.entry(name)
        if config is not None and found is not None and not surge_plays(config,found):
            s=sound_of(surge.fallback_track(t))
            return {**s,'what':f'{s["what"]} (the fallback of the Surge patch {name}, which this configuration does not play)'}
        curated=surge.presets()['presets'].get(name)
        if curated is not None:   # its own figures (its transpose may differ from the catalog's copy of its file): no decay measured
            attack,decays=(curated.get('measured') or {}).get('attack_s'),None
        else:
            e=surge.catalog().get(name) or {};m=e.get('measured') or {}
            attack=m.get('attack_s');decays=None if m.get('hold_end_db') is None else 'decays' in (e.get('character') or '').split(', ')
        # The figures are the patch at its saved settings.  `swell` sets the envelopes' attacks to the notes' length; a macro
        # may move an envelope (bright_pad's Attack macro shortens its 0.32 s rise to about 0.03 s), and velocity_to_cutoff
        # moves filter 1 by the notes' velocity: with any of them the saved patch's figures do not describe the part, and
        # neither question reads them (GPT Pro's review of 0.10, after the Astra reviews of step 3 and of the whole).  The
        # figures are also of the mod wheel at rest: a part that moves CC1 on a patch whose wheel moves anything (the catalog
        # lists what it moves; a curated patch's is not listed) plays it otherwise (verb_pad's wheel takes its amplitude
        # attack from about 0.9 s to 0.52 s: GPT Pro's second full review of 0.10).
        wheel=any(c==1 and v>0 for _,c,v in ((t.get('performance') or {}).get('cc') or []))
        moves=(surge.catalog().get(name) or {}).get('wheel') if curated is None else None
        if spec.get('swell') or spec.get('macros') or 'velocity_to_cutoff' in spec or (wheel and moves!=[]):attack=decays=None
        return {'what':f'the Surge patch {name}','attack_s':attack,'decays':decays,'from':"measured on the catalog's held probe note",'track':t}
    if t['engine']=='synth':
        what=f'the built-in preset {(t.get("synth") or {})["preset"]}' if (t.get('synth') or {}).get('preset') else 'its synth patch'
        try:amp=synth.patch_of(t).get('amp') or {}
        except ValueError:return {'what':what,'attack_s':None,'decays':None,'from':'its envelope','track':t}
        if not isinstance(amp,dict):return {'what':what,'attack_s':None,'decays':None,'from':'its envelope','track':t}
        # the synth's own envelope (synth.adsr, as synth.voice plays it), key held, read at 1 kHz up to the end of the hold
        rate=1000;n=int(round(PROBE_HOLD*rate));env=synth.adsr(n+10,n+5,amp,rate)[:n]
        decays=bool(env[-1]<=10**(-12/20)*env.max())
        attack=max(1e-4,amp.get('attack',.005))   # adsr's own floor and default
        return {'what':what,'attack_s':attack/2,'decays':decays,'from':'its envelope','track':t}
    return None
def surge_plays(config,found):
    """Whether Surge XT plays a part of the patch `found` (surge.entry) with this configuration, by the checks surge.locate
    makes short of its hashes: the binary is the plugin that loads (or inside its bundle), the plugin's file, the
    pedalboard package inside its folder, the full patch set for a catalog patch, the patch's file.  surge.installed alone
    took a folder without pedalboard in it for Surge XT, where the renderer played the fallback (the Astra review of the
    whole of 0.10); a configuration without a field the check reads plays the fallback, as in the renderer."""
    import os
    from pathlib import Path as _Path
    s,board=config.get('surge'),config.get('pedalboard')
    if not isinstance(s,dict) or not isinstance(board,dict) or not s.get('path') or not board.get('path'):return False
    plugin,binary=_Path(s['path']),_Path(s.get('binary',s['path']))
    # the binary checked must be the plugin that loads, or inside its bundle, as locate asks (the Astra review of the fixes)
    same=lambda a,b:os.path.normcase(os.path.realpath(a))==os.path.normcase(os.path.realpath(b))
    if not (same(binary,plugin) or any(same(plugin,up) for up in binary.parents)):return False
    if not binary.is_file() or not (_Path(board['path'])/'pedalboard').is_dir():return False
    folder=s.get('catalog') if found['folder']=='catalog' else s.get('patches')   # a field left out: the fallback, not an error
    return bool(folder) and (_Path(folder)/found['patch']).is_file()
def held_time(spans):
    """The seconds the spans cover, each moment once: a chord's notes held together are one stretch of time."""
    total,end=0.0,None
    for a,b in sorted(spans):
        if end is None or a>end:total+=b-a;end=b
        elif b>end:total+=b-end;end=b
    return total
def pedal_down(track,clock):
    """The stretches in seconds in which the part's sustain pedal is down (CC64 at 64 or more, as MIDI reads it), from its
    performance's controller events, the last running on past the end; [] for a part with no pedal, None for one with a
    pedal and no clock to time it."""
    events=sorted((b,v) for b,c,v in (track.get('performance') or {}).get('cc',[]) if c==64)
    if not events:return []
    if clock is None:return None
    out,start=[],None
    for b,v in events:
        if v>=64 and start is None:start=clock.seconds(b)
        elif v<64 and start is not None:out.append((start,clock.seconds(b)));start=None
    if start is not None:out.append((start,float('inf')))
    return out
def started(track,actual,clock):
    """The spans (start, end in seconds) in which the part's sound is started, as its engine plays the notes, and what
    one of them is called: a built-in synth part's voices as synth.render makes them (synth.line_voices: a mono patch's
    notes that run on into each other are one voice, an arpeggio's chord is one), a Surge part with `glide_ms` its notes
    merged where one overlaps the one before (Surge's single-trigger mono mode, surge.played_as, does not start the
    envelope again there; a note that only touches the one before is struck afresh), else one span a note (the Astra
    review of step 3: review's own grouping of touching notes missed what the synth did).  A Surge part's span let go
    while its sustain pedal is down is left out, as Surge holds it on to an end review does not know (pedal_down)."""
    from . import synth
    if track['engine']=='synth' and clock is not None:
        groups,patch=synth.line_voices(track,clock)
        spans=[(a,a+h) for a,h in (synth.voice_held(g,patch) for g in groups)]
        kind='chords (an arpeggio plays each as one voice)' if patch.get('arpeggio') else 'voices (its notes run on one voice where they meet)' if patch.get('mono') else 'notes'
        return spans,kind
    spans=sorted((a['start_seconds'],a['end_seconds']) for a in actual)
    down=[]
    if track['engine']=='surge':
        # Surge XT gets the part's sustain pedal (CC64, surge.render) and holds a key let go while the pedal is down until
        # it comes up, so where such a span ends review does not know: a span let go under the pedal, or within 20 ms of
        # its going down or up, counts for neither question (GPT Pro's review of 0.10: a pad's 0.25 s note under a pedal
        # held to 4 s was asked about as ending at 0.25 s).  The built-in synth, which plays a fallback, takes no pedal.
        down=pedal_down(track,clock)
        if down is None:return [],'notes'
    def pedalled(b):
        """Where a key let go at b sounds to, if it is let go under the pedal: the latest coming up of every stretch it falls
        in, as a pedal let up and pressed again within 20 ms falls in both (the first alone ended a C4 let go at 2.015 s, under
        a pedal pressed again at 2.01 s and held to 3 s, at 2.015 s: GPT Pro's second check of the fixes); else None."""
        ups=[max(hi,b) for lo,hi in down if lo-.02<=b<hi+.02]
        return max(ups) if ups else None
    if track['engine']=='surge' and 'glide_ms' in (track.get('surge') or {}):
        # The phrases first, each note held on to where it sounds (a note let go under the pedal to the pedal's coming up),
        # then a phrase with such a note left out whole: leaving the note out first made the phrase's later notes a fresh
        # start (GPT Pro's check of the fixes: a C4 held 2 s under the pedal and a D4 gliding on from 1.9 s were asked about
        # as a 0.3 s phrase).
        merged=[]
        for a,b in spans:
            p=pedalled(b);end=b if p is None else p
            if merged and a<merged[-1][1]-1e-6:merged[-1][1]=max(merged[-1][1],end);merged[-1][2]=merged[-1][2] or p is not None
            else:merged.append([a,end,p is not None])
        return [(a,b) for a,b,p in merged if not p],'phrases (notes that overlap glide on one voice)'
    return [(a,b) for a,b in spans if pedalled(b) is None],'notes'
def sound_questions(t,actual,info,clock=None,config=None):
    """The questions of a part's sound against its notes (0.10 step 3d, research/design-0.10.md), as [(identifier, text)]:
    a quarter or more of the spans its sound is started in (started()) ending before it reaches half its level
    (`sound_attack`), and a part in a sustained role, half or more of whose sounding time lies in spans held past the
    probe's 1.2 s, on a sound that dies away within it (`sound_decay`).  A length within 10 ms of the attack or of the
    hold is neither shorter nor longer: lengths read off the clock differ from it by a rounding, and a note of a key
    struck again is cut a tick short (eight quarter notes of 0.6 s were three "shorter" than 0.6 s: the Astra review of
    step 3).  Neither is a fault in itself (a plucked chord left to
    ring is a choice): each puts the choice in front of the composer, and a decision answers it.  The figures go into the
    part's entry as `sound`."""
    s=sound_of(t,config)
    if not s or not actual:return []
    track=s.pop('track');info['sound']=s
    spans,kind=started(track,actual,clock)
    eps=.01;asked=[]
    if s['attack_s'] and spans:
        short=sum(b-a<s['attack_s']-eps for a,b in spans)
        if short*4>=len(spans):
            asked.append((identifier('sound_attack',t['id']),f'{t["id"]}: {short} of its {len(spans)} {kind} end before {s["what"]} reaches half its level (its attack, {s["attack_s"]:.2f} s, {s["from"]}), so they end while it is still rising. A sound with a faster attack (studio.py sounds --attack), longer notes, or say in decisions that it is meant.'))
    if s['decays'] and t.get('role') in SUSTAINED:
        # by time, not by count: one long drone among many short notes is most of what the part plays (the Astra review of
        # the design); time as it passes, each moment once, not each voice of a chord apart (a two-second chord of four
        # notes and four seconds of short notes was "67%": the Astra review of the whole of 0.10)
        held=held_time([(a,b) for a,b in spans if b-a>PROBE_HOLD+eps]);total=held_time(spans)
        if total>0 and held*2>=total:
            asked.append((identifier('sound_decay',t['id']),f'{t["id"]}: a {t["role"]} part on {s["what"]}, which dies away while a note is held (12 dB down or more within {PROBE_HOLD:g} s, {s["from"]}); {held/total:.0%} of the time its sound plays lies in {kind} held longer than that. A sound that holds its level (studio.py sounds --without decays), shorter notes, or say in decisions that it is meant.'))
    return asked
def places(summary,qid):
    """The digest of where what an answered question counts lies now (place_digest), or None for a question that names
    its place in its own words."""
    kind=qid.split(':',1)[0]
    if kind.startswith('outside_chord.'):
        return (((summary.get('outside_chord') or {}).get('not_resolved_by_step') or {}).get(kind.split('.',1)[1]) or {}).get('places')
    key={'vertical':'vertical_minor_seconds_ninths','parallels':'parallel_fifths_octaves','low_intervals':'low_intervals','transposed_samples':'transposed_samples'}.get(kind)
    return (summary.get(key) or {}).get('places') if key else None
def review(p,out,config=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);clock=Clock(p)
    from . import ears;headphones=ears.wanted(p)
    summary={'validation':validate(p),'title':p['title'],'tracks':[],'sections':[],'prompts':[],'not_a_perceptual_quality_score':True}
    questions=summary['questions']=[];answered=summary['answered']=[]
    reasons=[d for d in p.get('decisions',[]) if isinstance(d,str)]
    def put(qid,text):
        """A question: its text in `prompts`, as every release has had it, and in `questions` beside an identifier that
        stays the same from round to round and from version to version whatever the wording: the kind of question and,
        after a colon, the part, the parts or the section it is about.  Two rounds, or two versions of this file, are
        compared by these and never by the text (the review of the design of 0.7, E1).

        A decision that begins with the identifier and a colon ("stiffness:lead: a sequenced arpeggio, meant") answers
        that question: it is listed under `answered` with its reason and is not asked again, for as long as it keeps
        its identifier.  Its text is kept there with its current figures, so a change in what it counts is still seen.

        An identifier holds no colon followed by a space: a section named "answer: reprise" gives
        "plan:answer:%20reprise" (identifier(), which every question about a named part or section is given by).  So the identifier a decision answers is the text before its first colon and space, that
        one and no other, in this round and in every later one.  Matched by how a decision begins, one for the
        section "answer: reprise" also answered the question of the section "answer" (the review of 0.7's code, F04);
        matched by the longest identifier the review asks, it moved to "answer" in the round where the longer
        question had gone (the second review, R3)."""
        if qid in reason_of:answered.append({'id':qid,'text':text,'reason':reason_of[qid]})
        else:summary['prompts'].append(text);questions.append({'id':qid,'text':text})
    reason_of={}
    for d in reasons:
        head,colon,reason=d.partition(': ')
        if colon and reason.strip():reason_of.setdefault(head,reason.strip())   # the first decision for an identifier is the one kept
    # Each check's limits come from the style maps: the entry governing the check's axis, else the default, which is
    # marked 'ours' where the project set the number itself (styles.py; style-maps.json).
    from . import styles
    lims=styles.limits(p);L=lambda c:lims[c]['params'];ask=lambda c:lims[c]['ask']
    summary['style']=styles.parse(p.get('style'));summary['limits']=styles.summary(lims)
    csv_rows=[]
    for t in p['tracks']:
        notes=sorted(t['notes'],key=lambda n:n['on']);actual=sounded(t,clock)   # as the audio has them (notes.csv gives where each note ends)
        a_by_id={n['id']:n for n in actual};vel=[t['performance']['notes'][n['id']]['velocity'] for n in notes]
        hist=Counter(round(n['duration'],3) for n in notes);interval=[];gaps=[]
        for a,b in zip(actual,actual[1:]):
            if a['tick']!=b['tick']:
                interval.append(abs(b['pitch']-a['pitch']));gaps.append((b['start_seconds']-a['end_seconds'])*1000)
        phrases=Counter(n.get('phrase','unassigned') for n in notes)
        info={'id':t['id'],'role':t.get('role'),'engine':t['engine'],'notes':len(notes),'pitch_range':[min((n['pitch'] for n in notes),default=None),max((n['pitch'] for n in notes),default=None)],'duration_values':dict(hist),'velocity_range':[min(vel,default=None),max(vel,default=None)],'median_performed_key_gap_ms':round(statistics.median(gaps),2) if gaps else None,'step_or_repeat_fraction':round(sum(x<=2 for x in interval)/len(interval),3) if interval else None,'phrase_labels':dict(phrases),'same_key_retrigger_trims':sum(n.get('retrigger_trimmed',False) for n in actual)}
        summary['tracks'].append(info)
        bent=bend_question(t,clock,actual)
        if bent:put(*bent)
        if t.get('role') in ('melody','countermelody') and notes:
            if ask('melody_durations') and len(hist)<L('melody_durations')['min_categories']:put(identifier('melody_durations',t["id"]),f'{t["id"]}: few duration categories; inspect whether the intended line has phrase direction and space.')
            if ask('melody_velocities') and len(set(vel))<L('melody_velocities')['min_values']:put(identifier('melody_velocities',t["id"]),f'{t["id"]}: nearly flat MIDI velocity; inspect instrument response before adding expression.')
        bank=(t.get('patch') or t).get('bank',0)
        if t['engine']=='soundfont' and t.get('soundfont','default')=='default' and bank in (17,18) and not any(c==2 for _,c,_ in t['performance'].get('cc',[])):
            put(identifier('expression_preset',t["id"]),f'{t["id"]}: MuseScore "Expr." presets (bank 17/18) are near-silent until CC2 is written.')
        cut=highpass_cut(t)
        if cut and cut[0]>L('highpass')['loss_db'] and ask('highpass'):
            low,keeps=highpass_floor(cut[2]);where='an octave under that note' if low>15 else 'the lowest a part may have'
            put(identifier('highpass',t["id"]),f'{t["id"]}: its high-pass at {t["mix"].get("highpass",30):g} Hz takes {cut[0]:.1f} dB from the fundamental of its lowest note ({NAMES[cut[1]%12]}{cut[1]//12-1}, {cut[2]:.0f} Hz); at {low:.0f} Hz, {where}, it takes {keeps:.1f} dB.')
        if t['mix'].get('amp'):
            # An amplifier's input level is measured for some banks (amp.BANKS: the direct guitar, three basses); on another bank
            # the drive is whatever that bank's level makes it, which the part's receipt shows after a render.
            from . import amp
            spec=t['mix']['amp']
            # by the bank's file where a configuration says which file the part plays, by its name otherwise
            font=None
            if config is not None and t['engine']=='soundfont':
                from . import audio
                try:font=audio.soundfont_for(config,t)[1]
                except ValueError:font=None   # a bank that is not configured: said where the configuration is read
            known=amp.bank_gain_db(t,font) is not None
            info['amp']={'voice':spec['voice'],'drive':spec.get('drive',.5),'bank_measured':known}
            if not known and 'input_db' not in spec:
                put(identifier('amp_level',t["id"]),f'{t["id"]}: mix.amp on a preset whose level into the amplifier was not measured ({amp.described(t,font)}); the presets whose level was measured are {", ".join(sorted(f"{b} {k}" for b,k in amp.BANKS))}. After a render the part\'s receipt gives input_peak (near 1 for the hardest stroke, a guitar\'s full chord or a bass\'s single note, is the working level): set mix.amp.input_db by it, or say in decisions that the level is meant.')
        if t.get('key_map'):   # the hits as played: those the key map moves onto one key at one moment are one
            from .midi import remap
            hits=len(remap(actual,t['key_map']))
        else:hits=len(notes)
        if t['mix'].get('level_mode')=='peak' and kit(t) and hits>p['clock']['bars']:
            # A kit, hats or a shaker levelled by its peak: the loudest hit takes the level and the rest lies far
            # under it.  Eight of the nine real pieces of 0.8.0 had drums, and three revision logs name this as the
            # round they lost (design-0.9/real-use-2026-11-18.md): asked before the first render, once, and a
            # decision answers it.  Asked of a pattern: a part that plays more than once a bar on average, whose
            # loudness is not its hardest hit's (a kit, hats, a shaker).  A part of rare hits (a crash, a tam-tam, a
            # triangle, on however many keys) is what `peak` is for and is not asked; the line of once a bar is this
            # skill's, with no published figure behind it.
            what=f'{hits} hits in {p["clock"]["bars"]} bars, more than once a bar'
            put(identifier('peak_level',t["id"]),f'{t["id"]}: a drum part ({what}) levelled by its peak (mix.level_mode "peak"): level_dbfs is then the level of its loudest sample, so one crash or one hard hit sets it, and the part as a whole can come out much lower than its level says (kits and hats written so came out 15 to 30 dB too low in the pieces read for this check). "active_rms" levels the part by how loud it plays; "peak" suits a part of single hits alike, such as crashes on a part of their own: say in decisions that it is meant.')
        if t.get('strings'):
            # a part played by string (musiclib/strung.py), from the score alone: the notes on each string, the frets,
            # the muted notes and the widest stretch between stopped notes that sound together.  Nothing is asked:
            # no limit of a hand's reach has been read, and no fingering is chosen.
            from . import strung
            info['strung']=strung.summary(t,clock)
        if headphones:
            # the part's place in the headphone version (mix.headphones, musiclib/ears.py), from the score alone
            info['around']=ears.summary(t,clock)
        if t['mix'].get('move'):
            # A movement, from the score alone: its range and its fastest rate (pan units a second, under the tempo as
            # written).  No rate is called too fast: the detection studies read give no limit for music.  Low parts are
            # usually kept in the centre (electronic.md: Flint 2007, Senior 2010), so a moving bass or kick is asked about.
            from . import move
            info['move']={'type':t['mix']['move']['type'],**move.summary(t['mix']['move'],t['mix'].get('pan',0),clock)}
            kick=(t.get('drums') or t['engine']=='drum_synth' or kit_patch(t)) and any(n['pitch'] in (35,36) for n in notes)
            if (t.get('role')=='bass' or kick) and info['move']['highest']>info['move']['lowest']:   # its place changes (figures to three decimals)
                put(identifier('moving_low',t["id"]),f'{t["id"]}: a bass part or a kick moves across the image (mix.move, from {info["move"]["lowest"]:+.2f} to {info["move"]["highest"]:+.2f}); low parts are usually kept in the centre, where both loudspeakers carry them: move another part instead, or say in decisions that it is meant.')
        for asked in sound_questions(t,actual,info,clock,config):put(*asked)
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
    # The clashes between sounding notes (0.9 step 4).  Counted: the minor second and the minor ninth, the rule the
    # guides state (arrangement.md).  0.8 counted the semitone at every octave; in 272 projects of 50 real pieces a
    # third of its count lay two octaves or more apart, and the agents answered those as meant.  They are given
    # apart and not asked about: by Sethares's (1993) model of roughness between the partials of two harmonic tones,
    # a semitone two octaves wide has a tenth to a quarter of a close one's roughness and three octaves wide under a
    # tenth (a minor ninth about half; computed for two spectra at three registers).
    summary['vertical_minor_seconds_ninths']=v=vertical(p,clock,**L('vertical'),digest=True)
    upto=lambda widest:vertical(p,clock,**{**L('vertical'),'widest':widest})['count']
    two=upto(25);v['wider']={'two_octaves':two-v['count'],'three_octaves_or_more':upto(127)-two};wider=sum(v['wider'].values())
    # The exposed ones: begun on a downbeat or a half-bar and sounding together a beat or more.  Few, each is asked
    # by itself and answered by its own decision, so that a decision about the count hides none that comes later;
    # more than `one_by_one` are a matter of the style or of the voicing, and the count's question names them.
    clash=L('clash');exposed_count,found=exposed(p,clock,L('vertical').get('widest',13),clash['beats']) if v['count'] else (0,[])
    v['exposed_count']=exposed_count;v['exposed']=[{k:x[k] for k in x if k!='tracks'} for x in found]
    # a question of its own for each, by the two notes: a note's id is its part's own, so each is named with its part,
    # and the two names stand in one order whichever note is the lower (the review of 0.9's step 4)
    named=lambda x:sorted(f'{part}.{i}' if i else f'{part}@{x["beat"]:g}@{pitch}' for i,part,pitch in zip(x['ids'],x['tracks'],x['pitches']))
    few=0<exposed_count<=clash['one_by_one'] and ask('clash')
    singly=found if ask('vertical') and few else []
    if v['count'] and ask('vertical'):
        n=exposed_count;count=v['count'];fg=v['foreground_count']
        put('vertical',f'{count} sustained minor-second/ninth collision{"" if count==1 else "s"} ({fg} touch{"es" if fg==1 else ""} the foreground); most between {most_of(v["by_parts"])}.'
            +(f' {n} of them {"begins" if n==1 else "begin"} on a downbeat or a half-bar and {"sounds" if n==1 else "sound"} a beat or more, as written'
              +(f' ({"it has" if n==1 else "each has"} a question of its own (clash:<part>.<note>+<part>.<note>), asked below unless a decision answers it).' if few
                else f' (the longest at {found[0]["at"]}; more than {clash["one_by_one"]}, so none is asked by itself).' if n>clash['one_by_one'] else '.') if n else '')
            +' Check whether each is a prepared tension or an accidental voicing.'
            +(f' Not counted: {wider} more whose notes lie two octaves or more apart (a model of the roughness between two tones\' partials gives a semitone two octaves wide a quarter of a close one\'s or less, and three octaves wide under a tenth: Sethares 1993).' if wider else ''))
    for x in singly:
        lasts=x['overlap_beats']
        put(identifier('clash',*named(x)),f'{x["at"]}: {x["tracks"][0]} {note_name(x["pitches"][0])} and {x["tracks"][1]} {note_name(x["pitches"][1])} sound a minor {"second" if x["semitones"]==1 else "ninth"} together for {lasts:g} beat{"" if lasts==1 else "s"} from a {x["place"]}, as written. If it is a prepared tension (a suspension, a voicing with its flat ninth), say so in decisions; otherwise move or shorten one of the two notes.')
    oc=outside_chord(p,clock)
    if oc is not None:
        summary['outside_chord']=oc;g=oc['not_resolved_by_step']
        def first(x):
            f=x['first'];note=f' (note {f["id"]}'+(f', struck at {f["struck"]}' if f['struck']!=f['at'] else '')+')' if f.get('id') else ''
            return f'most in {x["most_in"]}; first {f["note"]} {"held into" if f["held_into_chord"] else "on"} {f["chord"]} at {f["at"]}{note}'
        def notes(x,who):
            n=x['count'];return f'{n} {who} {"note" if n==1 else "notes"} on strong positions {"sits" if n==1 else "sit"} outside the written chord and {"is" if n==1 else "are"}'
        if not ask('outside_chord'):g={}
        if 'melody' in g:put('outside_chord.melody',f'{notes(g["melody"],"melody")} not resolved by step ({first(g["melody"])}). The others outside it are named in outside_chord as passing, neighbour, appoggiatura, escape, suspension, retardation, pedal or anticipation notes (Open Music Theory, Embellishing Tones). In rock, melodies leave such notes unresolved, mostly in pentatonic verses (Temperley 2007; rock-and-metal.md); elsewhere resolve each by step, change the chord under it, or write a colour tone that is meant to stay into the symbol (Cadd9, C6, Csus4).')
        if 'bass' in g:put('outside_chord.bass',f'{notes(g["bass"],"bass")} neither resolved by step nor held as a pedal ({first(g["bass"])}). Where the bass is meant there, write a slash chord (C/D); otherwise move it to a chord tone.')
        if 'accompaniment' in g:put('outside_chord.accompaniment',f'{notes(g["accompaniment"],"accompaniment")} neither resolved by step nor held as a pedal ({first(g["accompaniment"])}). Write a tension that is meant into the symbol (Cmaj7, Csus4, Cadd9); many together can mean the part and the chord symbols are out of step.')
        if oc['unparsed_symbols']:put('chord_symbols_unread','Chord symbols not checked: '+', '.join(oc['unparsed_symbols']))
    par=summary['parallel_fifths_octaves']=parallels(p,clock,**L('parallels'))
    if par['count'] and ask('parallels'):
        f=par['examples'][0]
        put('parallels',f'{par["count"]} {"time" if par["count"]==1 else "times"} two parts move in parallel fifths or octaves (most between {most_of(par["by_pair"])}; first {f["interval"]} at {f["at"]}). Where the parts are independent voices (baroque, classical, chorale and chamber writing), two perfect consonances of the same size in a row fuse the voices and are avoided (Open Music Theory, First-Species Counterpoint): move one voice the other way or to a third or sixth. Power chords and lines doubled on purpose move in parallel; octaves inside a line doubled at the octave are left out (baroque.md).')
    low=summary['low_intervals']=low_intervals(p,clock)
    if low['count'] and ask('low_intervals'):
        w=low['furthest_below']
        put('low_intervals',f'{low["count"]} close {"interval sounds under its" if low["count"]==1 else "intervals sound under their"} low interval limit, where voicings turn muddy (most between {most_of(low["by_parts"])}; furthest under, a {w["interval"]} {w["notes"][0]}-{w["notes"][1]} at {w["at"]}, whose limit is {w["limit"]}). Spread the voicing or move the upper note an octave up, leaving the low register to the bass. The limits are guides: soft, dark sounds bear more than loud, bright ones, and a low rumble can be meant (Hoffmann; arrangement.md, Spacing).')
    rep=summary['repetition']=repetition(p,clock,**L('static_texture'),**L('repetition'),**L('arrivals_thinner'),**L('sections_alike'))
    for s in rep['static_spans'] if ask('static_texture') else ():
        if 'still' not in s:
            put('static_texture',f'Bars {s["from_bar"]}-{s["to_bar"]}: every part repeats the same {s["block_bars"]}-bar block note for note ({s["bars"]} bars). Change a layer, add a fill or a break, or vary the block (development-and-groove.md).')
        for w in s.get('still',()):
            put('static_texture.still',f'Bars {w["from_bar"]}-{w["to_bar"]}: every part repeats the same {s["block_bars"]}-bar block note for note ({w["bars"]} bars) and nothing moves its sound, no filter sweep, automation or controller curve. Dance music changes its loops by adding and taking away layers at phrase downbeats and by continuous processes, filter sweeps, crescendos, fades (Garcia 2005; Smith 2021): add one, or change a layer (electronic.md, Techno).')
    for l in rep['part_loops'] if ask('repetition') else ():
        who=', '.join(l['tracks']);cyc='/'.join(map(str,l['cycle_bars']))
        put(identifier('repetition',*l['tracks']),f'Bars {l["from_bar"]}-{l["to_bar"]}: {who} {"repeat" if len(l["tracks"])>1 else "repeats"} a {cyc}-bar pattern unchanged for {l["bars"]} bars. Dance music brings new sounds in at the downbeats of its phrases (Smith 2021): at an 8- or 16-bar edge try a fill, a dropout and return, or a variation of the pattern (development-and-groove.md).')
    for r in rep['literal_returns'] if ask('literal_returns') else ():
        put(identifier('literal_returns',r["section"]),f'{r["section"]} repeats {r["repeats"]} note for note in every part; if the return should develop, change one thing: the melody, the harmony under it, the texture or the register (development-and-groove.md).')
    for w in rep['arrivals_thinner_than_before'] if ask('arrivals_thinner') else ():
        put(identifier('arrivals_thinner',w["section"]),f'{w["section"]} arrives thinner than {w["after"]} (notes per bar {w["notes_per_bar"][0]:g} -> {w["notes_per_bar"][1]:g}, parts {w["parts"][0]} -> {w["parts"][1]}, velocity {w["mean_velocity"][0]:g} -> {w["mean_velocity"][1]:g}); confirm the drop in energy is meant.')
    for f in rep['sections_alike'] if ask('sections_alike') else ():
        put(identifier('sections_alike',*f['sections'][:2]),f'{f["sections"][0]} and {f["sections"][1]} have the same parts and nearly the same density and dynamics; decide what changes between them.')
    entry=styles.governing(summary['style'],'tempo');spec=(styles.registry()['styles'].get(entry) or {}).get('tempo_bpm') if entry else None
    if spec:
        tr=summary['tempo_range']=tempo_range(p,entry,spec);lo,hi=tr['range']
        span=f'{lo:g}-{hi:g} BPM' if hi is not None else f'{lo:g} BPM or more'
        if not tr['inside'] and ask('tempo_range'):put('tempo_range',f'The piece runs at {tr["bpm"]:g} BPM, outside the {span} the source of {entry} gives ({tr["source"]}){", and so does its half or double time" if hi is not None else ""}. If the tempo is meant, record why in decisions; a tempo outside the range can make the music read as another style (style-maps.md).')
    lp=summary['low_passes']=low_passes(p,**L('widespread_lowpass'))
    if lp['most'] and ask('widespread_lowpass'):
        named=', '.join(f'{k} {v/1000:g} kHz' for k,v in sorted(lp['under'].items(),key=lambda kv:kv[1])[:6])+(', ...' if len(lp['under'])>6 else '')
        put('widespread_lowpass',f'{len(lp["under"])} of the {lp["parts"]} parts other than the bass are low-passed at or under {lp["below_hz"]/1000:g} kHz ({named}): together they take the top octave out of the mix, where most mixing books put air (10-20 kHz; Moffat, De Man and Reiss 2022). Widespread low-pass filtering seldom helps, because the harmonics and noise of most instruments reach up the spectrum, and it easily dulls a mix (Senior 2012). Keep a low-pass where the highs of a part must go for the balance, such as the noise of an amplified guitar; for the others remove `mix.lowpass` (18 kHz by default) unless the style wants a muffled top (performance-and-mix.md, Brightness and air).')
    stiff=summary['stiffness']=stiffness(p,clock,**L('stiffness'))
    for b in stiff['block_chord_parts'] if ask('stiffness') else ():
        put(identifier('stiffness',b["track"]),f'{b["track"]}: {b["block_share"]:.0%} of its {b["chords"]} chords are struck and released as one block. Hold a common tone over the change, move an inner voice or vary its rhythm; a chord broken into separate attacks is not counted among them, so breaking some leaves this share of the rest (development-and-groove.md; musiclib.voicing voices chords to move smoothly).')
    from .profile import melody_in, top_line
    line=top_line([n for t in p['tracks'] if t.get('role')=='melody' for n in t['notes']])
    summary['melody_sections']=[]
    for s in p['sections']:
        m=melody_in(line,s['start_bar']*clock.beats_per_bar,(s['start_bar']+s['bars'])*clock.beats_per_bar,clock)
        summary['melody_sections'].append({'section':s['id'],**(m or {})})
        if m and ask('restatement') and m['bars_compared']>=L('restatement')['min_bars'] and m['bars_restated']==0:
            put(identifier('restatement',s["id"]),f'{s["id"]}: none of its {m["bars_compared"]} melody bars restates the rhythm and shape of an earlier one. Pop sections often state an idea and restate it before departing (Summach 2011), as a classical sentence repeats its basic idea (Caplin 1998); if this section should have such an idea, state it and restate it, varied or sequenced (climax-and-melody.md).')
    if stiff['no_pushes_anywhere'] and ask('pushes'):
        put('pushes','No melody or accompaniment attack anticipates a downbeat or half-bar. Rock and pop melodies anticipate strong beats (Tan, Lustig and Temperley 2019), and moderate syncopation goes with the most groove (Witek et al. 2014; development-and-groove.md); if the style calls for drive, try a few pushes.')
    # Surge XT's mono single-trigger legato keeps the velocity of the note a slide starts from: SurgeVoice::legato (Surge
    # XT 1.3.4) does not take the new note's, so velocity_to_cutoff does not reach a note that glides in, as played (GPT's
    # review of 0.5, SA01: an accented note's cutoff stayed where the note before it had set it).
    for t in p['tracks']:
        sp=t.get('surge') if t['engine']=='surge' else None
        if sp and 'glide_ms' in sp and 'velocity_to_cutoff' in sp:
            # A note glides in when any note begun before it still sounds, not only the one just before it: a long
            # note held under a short one is still down when the next begins (GPT's second re-review of 0.5, R06).
            ns=sorted(performed(t,clock),key=lambda n:(n['start_seconds'],n['pitch']))
            slid,down,began=[],float('-inf'),[]  # the latest end of the notes begun before; those begun with this one
            for n in ns:
                while began and began[0][0]+1e-6<n['start_seconds']:down=max(down,began.pop(0)[1])
                if n['start_seconds']<down-1e-6:slid.append(n['id'])
                began.append((n['start_seconds'],n['end_seconds']))
            if slid:put(identifier('glide_accent',t["id"]),f'{t["id"]}: {len(slid)} note{"s" if len(slid)>1 else ""} glide{"" if len(slid)>1 else "s"} in from a note still sounding ({", ".join(slid[:3])}{", ..." if len(slid)>3 else ""}); Surge XT keeps the velocity of the note a slide starts from, so velocity_to_cutoff does not accent them. End every note still sounding before one that must be accented (it then attacks), or let it slide unaccented.')
    if config is not None:
        from . import surge
        if surge.installed(config):
            # Surge XT is the default synth where it is installed: a built-in preset it covers is asked about.
            full=bool((config.get('surge') or {}).get('catalog'))
            for t in p['tracks']:
                preset=(t.get('synth') or {}).get('preset') if t['engine']=='synth' else None
                role=surge.BUILTIN_ROLES.get(preset) if preset else None
                options=surge.counterparts(preset) if preset else []
                named=surge.catalog_counterparts(preset) if preset and full and not options else []
                if full and role and t['notes']:
                    # With the full patch set: three of the role spread over the range and picked by the piece's seed
                    # (sounds.spread), so two pieces are not pointed to the same patches, as the curated four were
                    # every time: the 0.4.0 agent pieces took 71% of their Surge parts from the curated fifty.
                    from .blocks import seed as piece_seed
                    from .sounds import search
                    s=piece_seed(p['title']);picks=[r['id'] for r in search(role,limit=3,seed=s)['shown']]
                    put(identifier('builtin_preset',t["id"]),f'{t["id"]}: plays the built-in {preset}; Surge XT is installed with its full patch set: studio.py sounds --role {role} --seed {s} lists patches for this role spread over the range (three for this piece: {", ".join(picks)}). Hear two to four on the part: studio.py audition <song.json> --track {t["id"]} --sounds {",".join("surge:"+x for x in picks)} --bars FIRST-LAST --output <folder> --config <config.json> (sound-selection.md). Keep the built-in preset where a render must repeat exactly or the sound needs fields of its own.')
                elif full and surge.measured_counterparts(preset) and t['notes']:
                    # The 808's slide and the acid line's accents and slides: the patches measured to play them as the
                    # score asks, with the settings that do it (surge-roles.json), not every patch so named.
                    measured=surge.measured_counterparts(preset)
                    listed='; '.join(pid+(' with '+', '.join(k if v is True else f'{k} {v:g}' for k,v in s.items()) if s else '') for pid,s in measured)
                    put(identifier('builtin_preset',t["id"]),f'{t["id"]}: plays the built-in {preset}; Surge XT is installed with its full patch set, and these patches were measured to play this part as the score asks (surge-roles.json): {listed}. Hear them on the part with those settings: studio.py audition <song.json> --track {t["id"]} --sounds {",".join("surge:"+pid+"".join("+"+k if v is True else f"+{k}={v:g}" for k,v in s.items()) for pid,s in measured[:3])} --bars FIRST-LAST --output <folder> --config <config.json> (electronic-sounds.md). Keep the built-in preset where none suits, where a render must repeat exactly, or where Surge XT is missing.')
                elif (options or named) and t['notes']:
                    which=f'its patches for this role include {", ".join(options[:4])}' if options else f'its full patch set has patches named for this sound: {", ".join(named[:4])}'
                    put(identifier('builtin_preset',t["id"]),f'{t["id"]}: plays the built-in {preset}; Surge XT is installed, and {which}. Hear them on the part: studio.py audition <song.json> --track {t["id"]} --sounds {",".join("surge:"+x for x in (options or named)[:3])} --bars FIRST-LAST --output <folder> --config <config.json> (electronic-sounds.md). Keep the built-in preset where a render must repeat exactly or the sound needs fields of its own.')
        st=summary['transposed_samples']=stretched(p,clock,sample_maps(p,config),limit=L('transposed_samples')['limit_semitones'])
        if st['count'] and ask('transposed_samples'):
            worst=most_of({k:v['notes'] for k,v in st['by_track'].items()})
            put('transposed_samples',f'{st["count"]} notes play a sample transposed more than {st["limit_semitones"]} semitones, most in {worst}; the tone and the vibrato rate change with it. Move them, give them to another instrument, or accept the change.')
        if st['outside_count']:put('outside_keys',outside_keys(st))
        from . import audio,layered
        cannot=summary['cannot_render']=[m for t in p['tracks'] if t['engine']=='soundfont' for m in [layered.unsupported(t,audio.soundfont_for(config,t)[1]['path'])] if m]
        for m in cannot:put('cannot_render','Cannot render: '+m)
        for qid,text in piano_choice(p,own_banks(config)):put(qid,text)
    if 'loop' in p:
        from . import loop
        s=summary['loop_seam']=loop.seam(p,clock)
        m,pc,tb=s['meter'],s['pitch'],s['timbre']
        if not m['same_tempo']:put('loop_seam.tempo',f'Loop seam: {m["bpm_at_end"]:g} BPM at the loop end, {m["bpm_at_start"]:g} at the loop start. A tempo change across the seam is heard on every repeat; confirm it is meant.')
        if pc['not_before']:put('loop_seam.pitch',f'Loop seam: {", ".join(pc["not_before"])} sound in the first second after the loop point but not in the five seconds before it. Check that the last bar leads into the first.')
        moves=[x for x in (f'entering: {", ".join(tb["entering"])}' if tb['entering'] else '',f'leaving: {", ".join(tb["leaving"])}' if tb['leaving'] else '') if x]
        if moves:put('loop_seam.timbre','Loop seam: parts '+'; '.join(moves)+'. Confirm the change of instruments at the loop point is meant.')
    # The score at a glance: the parts by section, the harmony's pace, the melody's rhythm (views.py), each counted
    # by a rule its text states.  They describe; none of them is a question.
    from . import views as score_views
    summary['views']=score_views.views(p)
    # The plan read against the score (plan.py): what it states and the score holds, what differs, what cannot be
    # read.  A project without a plan is asked for one; nothing refuses it.
    from . import plan as score_plan
    compared=summary['plan']=score_plan.compare(p,clock)
    for qid,asked in score_plan.questions(compared):put(qid,asked)
    from . import association
    for qid,asked in association.questions(p):put(qid,asked)
    # Everything is composed before the first file is written, and what was written is recorded whatever stops the
    # review, so clean can take it (a failure part way left two files and no record; found by GPT Pro's third review).
    lines=[f'# {p["title"]}', '',p.get('brief',''),'', '| Section | Bars (1-based) | Time | Function |','|---|---:|---:|---|']
    for s in summary['sections']:
        lines.append(f'| {s["id"]} | {s["start_bar"]+1}–{s["start_bar"]+s["bars"]} | {s["start_seconds"]:.1f}–{s["end_seconds"]:.1f}s | {s.get("intent","")} |')
    lines+=['','## Authored musical decisions','']+[f'- {x}' for x in p.get('decisions',[])]+['','## Review questions','']+['- '+x for x in summary['prompts']]
    lines+=['','Metrics do not establish whether a piece sounds good. Key gaps exclude pedal/release tails. Different durations and more tracks are not quality scores.']
    arrangement='\n'.join(lines)+'\n'
    try:
        for a in answered:
            where_now=places(summary,a['id'])
            if where_now:a['places']=where_now
        save_json(out/'score_review.json',summary)
        # A text cell a spreadsheet would read as a formula (one starting with =, +, -, @, a tab or a carriage
        # return) gets a leading apostrophe, as OWASP's CSV injection guidance advises: a project's names stay text.
        # A score without a note has the file too, its header alone: the summary names it, and one an earlier review
        # left in the folder would list notes that are gone (the reviews of 0.9).
        safe=lambda v:"'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@','\t','\r') else v
        with files.staged(out/'notes.csv','w',encoding='utf-8',newline='') as f:  # whole or not at all
            w=csv.DictWriter(f,fieldnames=NOTE_COLUMNS);w.writeheader();w.writerows({k:safe(v) for k,v in r.items()} for r in csv_rows)
        with files.staged(out/'arrangement.md','w',encoding='utf-8') as f:
            f.write(arrangement)
    finally:
        files.register(out,[out/n for n in ('score_review.json','notes.csv','arrangement.md') if (out/n).is_file()])
    return summary
