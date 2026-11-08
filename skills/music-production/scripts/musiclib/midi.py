"""Small bounded SMF reader and deterministic encoder; never executes metadata."""
from collections import Counter, defaultdict, deque
from pathlib import Path
import struct
from . import variation
from .model import Clock, TPQ, performed, cc_events, bend_curve, bend_events, legato_notes, wheel_events

def vlq(n):
    if not 0<=n<=0x0fffffff:raise ValueError('VLQ range')
    b=[n&127]
    while n>>7:
        n>>=7;b.insert(0,(n&127)|128)
    return bytes(b)

def meta(kind,data):return bytes([255,kind])+vlq(len(data))+data

def chunk(events):
    previous=0;out=bytearray()
    for tick,rank,data in sorted(events,key=lambda e:(e[0],e[1])):
        out+=vlq(tick-previous)+data;previous=tick
    out+=b'\x00\xff\x2f\x00'
    return b'MTrk'+struct.pack('>I',len(out))+out

def remap(notes,key_map):
    """Apply a render-time key map; notes landing on one key keep the louder attack and trim overlaps."""
    out=[]
    for n in notes:out.append({**n,'pitch':int(key_map.get(str(n['pitch']),n['pitch']))})
    kept=[]
    for pitch in {n['pitch'] for n in out}:
        group=sorted((n for n in out if n['pitch']==pitch),key=lambda n:(n['tick'],-n['velocity']))
        prev=None
        for n in group:
            if prev is not None and n['tick']==prev['tick']:continue
            if prev is not None and prev['end_tick']>=n['tick']:prev['end_tick']=max(prev['tick']+1,n['tick']-1)
            kept.append(n);prev=n
    return sorted(kept,key=lambda n:(n['tick'],n['pitch']))

def write(project,path,tracks=None,expressive=True,single_stem=False,render=False,keys=None,cycles=None):
    """Standard MIDI file. With render=True (synthesis input only) a track's `patch` replaces its
    program/bank and `key_map` remaps pitches; a drum part whose patch is not bank 128 plays on a
    melodic channel; with `keys` (a preset's recordings per key, musiclib/variation.py) a part with
    `performance.round_robin` plays repeated notes on neighbouring keys, on channels 1-4 with the wheel
    holding them at pitch; with `cycles` (variation.velocity_cycles) repeated hits step through the
    bank's recorded round robins.  Exports for people keep the authored identity."""
    clock=Clock(project)
    tracks=project['tracks'] if tracks is None else tracks
    conductor=[]
    for beat,bpm in clock.tempo:
        conductor.append((round(beat*TPQ),0,meta(81,round(60_000_000/bpm).to_bytes(3,'big'))))
    num,den=project['clock']['meter']
    conductor.append((0,1,meta(88,bytes([num,den.bit_length()-1,36 if den==8 and num%3==0 else 24,8]))))
    for s in project['sections']:
        conductor.append((round(s['start_bar']*clock.beats_per_bar*TPQ),2,meta(6,s['id'].encode('ascii','replace'))))
    chunks=[chunk(conductor)];routing=[];melodic=0;kits=0
    for t in tracks:
        patch=t.get('patch') if render else None
        bank=(patch or t).get('bank',0);program=(patch or t).get('program',0)
        drum_channel=bool(t.get('drums')) and (patch is None or bank==128)
        if drum_channel:
            # Each drum part gets channel 10 of its own port, so two kits keep their own program and controllers.
            channel=9;port=0 if single_stem else kits;kits+=1
        elif single_stem:
            channel=0;port=0
        else:
            port=melodic//15;index=melodic%15;channel=index+(index>=9);melodic+=1
        routing.append({'track':t['id'],'port':port,'channel':channel,'program':program,'bank':bank})
        e=[(0,0,meta(3,t['id'].encode())),(0,0,meta(33,bytes([port])))]
        if not drum_channel:
            e.extend([(0,1,bytes([176+channel,0,bank//128])),(0,1,bytes([176+channel,32,bank%128]))])
        e.append((0,2,bytes([192+channel,program])))
        for cc,value in [(7,100),(10,64),(11,100),(64,0)]:
            e.append((0,3,bytes([176+channel,cc,value])))
        notes=performed(t,clock,expressive)
        if render and t.get('key_map'):notes=remap(notes,t['key_map'])
        if render and cycles:
            notes=sorted(notes,key=lambda n:(n['tick'],n['pitch']))
            notes=[{**n,'velocity':v} for n,v in zip(notes,variation.cycle_velocities(notes,cycles))]
        if render and expressive and t['performance'].get('legato'):
            # Synthesis only: slurred notes sound as one sample with the pitch carried by the wheel.
            notes,slurs=legato_notes(t,notes,clock)
            bends=wheel_events([bend_curve(t['performance'].get('bend',[])),slurs],t['performance'].get('bend_range',2),clock.total_beats)
        else:
            bends=bend_events(t) if expressive else []
        if expressive:
            for beat,cc,value in cc_events(t):
                e.append((round(beat*TPQ),4,bytes([176+channel,cc,value])))
            if t['performance'].get('dynamics') and not render:
                # The dynamics curve goes out as CC1, the controller orchestral sample libraries read as dynamics.
                ramp={'engine':'soundfont','performance':{'cc_mode':'linear','cc':[[b,1,int(round(v))] for b,v in t['performance']['dynamics']]}}
                for beat,cc,value in cc_events(ramp):
                    e.append((round(beat*TPQ),4,bytes([176+channel,cc,value])))
        if bends:
            # RPN 0 sets the wheel range in semitones, then the null RPN closes data entry.
            for cc,value in [(101,0),(100,0),(6,t['performance'].get('bend_range',2)),(38,0),(101,127),(100,127)]:
                e.append((0,3,bytes([176+channel,cc,value])))
            for beat,value in bends:
                e.append((round(beat*TPQ),4,bytes([224+channel,value&127,value>>7])))
        shifts=[0]*len(notes)
        if render and keys and t['performance'].get('round_robin') and not bends and not drum_channel and single_stem:
            shifts=variation.round_robin_shifts(notes,keys)
            for s in sorted(set(shifts)-{0}):
                ch=variation.channel_for(s,channel)
                e.extend([(0,1,bytes([176+ch,0,bank//128])),(0,1,bytes([176+ch,32,bank%128])),(0,2,bytes([192+ch,program]))])
                e.extend((0,3,bytes([176+ch,cc,value])) for cc,value in [(7,100),(10,64),(11,100),(64,0),(101,0),(100,0),(6,2),(38,0),(101,127),(100,127)])
                if expressive:
                    e.extend((round(beat*TPQ),4,bytes([176+ch,cc,value])) for beat,cc,value in cc_events(t))
                wheel=variation.wheel_value(s);end=round(clock.total_beats*TPQ)
                e.extend([(0,4,bytes([224+ch,wheel&127,wheel>>7])),(end,7,bytes([176+ch,64,0])),(end,8,bytes([176+ch,123,0]))])
        for n,s in zip(notes,shifts):
            ch=variation.channel_for(s,channel) if s else channel
            e.append((n['tick'],6,bytes([144+ch,n['pitch']+s,n['velocity']])))
            e.append((n['end_tick'],5,bytes([128+ch,n['pitch']+s,0])))
        end=round(clock.total_beats*TPQ)
        e.extend([(end,7,bytes([176+channel,64,0])),(end,8,bytes([176+channel,123,0]))])
        if bends:e.append((end,7,bytes([224+channel,0,64])))
        chunks.append(chunk(e))
    Path(path).write_bytes(b'MThd'+struct.pack('>IHHH',6,1,len(chunks),TPQ)+b''.join(chunks))
    return routing

def read_own(path):
    """A MIDI file the skill wrote, read back to check it: bounded by its own size (an event takes at least two bytes,
    a delta time and a data byte), not by the limits for a file from elsewhere, which a long project's own export
    (validate allows 500,000 notes, a million note events before the controllers and the wheel) can pass."""
    size=Path(path).stat().st_size
    return read(path,max_bytes=size,max_events=size//2+1)

def read(path,max_bytes=8_000_000,max_events=1_000_000):
    if Path(path).stat().st_size>max_bytes:raise ValueError('MIDI byte bound exceeded')
    with Path(path).open('rb') as stream:data=stream.read(max_bytes+1)
    if not 14<=len(data)<=max_bytes or data[:4]!=b'MThd' or data[4:8]!=b'\x00\x00\x00\x06':raise ValueError('Invalid/big MIDI')
    kind,ntracks,division=struct.unpack_from('>HHH',data,8)
    if kind not in (0,1) or not 1<=ntracks<=128 or not 1<=division<=32767 or (kind==0 and ntracks!=1):raise ValueError('Unsupported SMF header')
    pos=14;tracks=[];tempos=[];total_events=0
    def read_vlq(pos,end):
        n=0
        for _ in range(4):
            if pos>=end:raise ValueError('Truncated VLQ')
            b=data[pos];pos+=1;n=(n<<7)|(b&127)
            if b<128:return n,pos
        raise ValueError('Overlong VLQ')
    for ti in range(ntracks):
        if data[pos:pos+4]!=b'MTrk' or pos+8>len(data):raise ValueError('Missing MIDI track')
        size=struct.unpack_from('>I',data,pos+4)[0];pos+=8;end=pos+size
        if end>len(data):raise ValueError('Truncated MIDI track')
        tick=0;running=None;events=[];active=defaultdict(deque);notes=[];counts=Counter();name='';stray=0;ended=False;meters=[];port=0
        while pos<end:
            delta,pos=read_vlq(pos,end);tick+=delta;total_events+=1
            if total_events>max_events or tick>division*30000:raise ValueError('MIDI bounds exceeded')
            if pos>=end:raise ValueError('Missing MIDI status after delta time')
            status=data[pos]
            if status&128:pos+=1
            elif running is not None:status=running
            else:raise ValueError('Invalid running status')
            if 128<=status<=239:
                running=status;op=status>>4;ch=status&15;length=1 if op in (12,13) else 2
                if pos+length>end:raise ValueError('Truncated MIDI message')
                args=data[pos:pos+length];pos+=length
                if any(v>127 for v in args):raise ValueError('Invalid data byte')
                counts[str(op)]+=1;events.append([tick,status,*args])
                if op==9 and args[1]>0:active[(ch,args[0])].append((tick,args[1]))
                elif op==8 or (op==9 and args[1]==0):
                    queue=active[(ch,args[0])]
                    if queue:
                        on,vel=queue.popleft();notes.append({'tick':on,'end_tick':tick,'pitch':args[0],'velocity':vel,'channel':ch,'port':port})
                    else:stray+=1
            elif status in (240,247,255):
                if status==255:
                    if pos>=end:raise ValueError('Truncated meta')
                    mt=data[pos];pos+=1
                else:mt=None;running=None
                length,pos=read_vlq(pos,end)
                if length>65536 or pos+length>end:raise ValueError('Oversized MIDI metadata')
                payload=data[pos:pos+length];pos+=length
                if status!=255:counts['sysex']+=1
                elif mt==47:
                    if length or pos!=end:raise ValueError('Invalid track ending')
                    ended=True
                elif mt==81:
                    if length!=3:raise ValueError('Invalid tempo')
                    tempo=int.from_bytes(payload,'big')
                    # Any slower tempo a project's rubato can reach (a 30-minute bound limits the length anyway).
                    if tempo<100000:raise ValueError('Tempo outside bound')
                    tempos.append([tick,tempo])
                elif mt==88:
                    if length!=4 or payload[0]==0 or payload[1]>7:raise ValueError('Invalid meter')
                    meters.append([tick,payload[0],2**payload[1]])
                elif mt==3:name=payload.decode('utf-8','replace')[:300]
                elif mt==33 and length==1:port=payload[0]
            else:raise ValueError('Unsupported system message')
        if not ended:raise ValueError('No end-of-track')
        tracks.append({'name':name,'notes':sorted(notes,key=lambda n:n['tick']),'events':events,'meters':meters,'end_tick':tick,'unclosed':sum(len(x) for x in active.values()),'stray_offs':stray,'counts':dict(counts)})
    if pos!=len(data):raise ValueError('Unexpected trailing data')
    return {'format':kind,'division':division,'tracks':tracks,'tempos':sorted(set(tuple(x) for x in tempos)),'events':total_events}
