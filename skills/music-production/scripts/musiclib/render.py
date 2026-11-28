"""Deterministic per-track synthesis/cache, processed stems, FX returns and master.

The parts are synthesized and processed in parallel (`jobs` threads; the heavy work runs in FluidSynth and FFmpeg
processes and in NumPy, which release the interpreter). Every part writes only its own files, so the stems and the
master are the same for any `jobs`.  The renders of a piece share its cache, so a part holds its cache entry while it
is synthesized, processed and kept (entry_lock): a render that needs the same entry at the same time waits, then
finds the part in the cache, and no render reads a file another is replacing.

A part's cache entry also keeps its last processed stem.  When nothing the processing reads has changed, the render
copies that stem instead of processing the part again, as a frozen track in a DAW plays its rendered file instead of
computing its devices again (Ableton Live Reference Manual, Computer Audio Resources and Strategies).  The copy is
what is checked against the receipt.  Every render still mixes and masters all the parts.  Where a part's Surge XT Effects
chain does not render the same to the sample each time it runs (surgefx.repeat), the entry keeps that chain's output too,
under the part's audio into it and the chain, so that the speaker stem, the headphone version and a later render that
processes the part again for another reason (a pan) play one take (surgefx.apply).

A draft (`draft=True`) is the same audio, stems, buses and returns as a full render, for revising: it leaves out what
only delivery needs, master.flac, the MP3's decoded-loudness check and a game loop's Ogg copies and layers, as REAPER's
dry-run render processes everything but writes no output files (REAPER 6.30)."""
import ast
import contextlib
import errno
import json
import math
import os
import re
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from pathlib import Path
import shutil
import threading
import time
import numpy as np
from . import bankcheck, audio, drums, files, layered, midi, production, stage, surge, surgefx, synth, variation
from .model import Clock, load_project, validate, save_json, sounded, digest, file_hash

def retrigger_trims(t,clock):
    """How many of a part's notes a second strike of their key cuts short in its audio (the stem's receipt): of a part
    played by string, string by string (model.sounded), not on the exported MIDI's one channel."""
    return sum(n.get('retrigger_trimmed',False) for n in sounded(t,clock))

def engine_hash():
    """The renderer's code: every musiclib module and the two Surge hosts the renderer starts."""
    scripts=Path(__file__).resolve().parents[1]
    return digest({**{p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')},
                   **{name:file_hash(scripts/name) for name in ('surge_host.py','surgefx_host.py')}})

def _memory(free):
    """Bytes of memory free for new work (`free`), or installed; None where it cannot be read (macOS: half its installed
    memory counts as free)."""
    try:
        if os.name=='nt':
            import ctypes
            class Status(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('total','avail','page_total','page_avail','virtual_total','virtual_avail','extended')]
            s=Status();s.length=ctypes.sizeof(Status)
            return (s.avail if free else s.total) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)) else None
        if os.path.exists('/proc/meminfo'):
            with open('/proc/meminfo',encoding='ascii') as f:
                for line in f:
                    if line.startswith('MemAvailable:' if free else 'MemTotal:'):return int(line.split()[1])*1024
        return os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')//(2 if free else 1)
    except (OSError,ValueError,AttributeError):
        return None

def free_memory():
    return _memory(True)

def total_memory():
    return _memory(False)

def too_large(p,clock,frames,fonts,machine,surge_deps=None):
    """Refuse, before anything is synthesized, a part that would need more memory at once than the machine has
    (part_memory): run, it would only swap or be stopped.  The built-in synth makes each note whole, about 30 MB a
    second of the note, so a note held for minutes is the usual cause."""
    if not machine:return
    for t in p['tracks']:
        need=part_memory(t,clock,frames,fonts.get(t['id']),(surge_deps or {}).get(t['id'],{}).get('plays')=='Surge XT')
        if need<=machine:continue
        why=''
        if t['engine'] in ('synth','surge','additive'):
            held=max((clock.seconds(n['on']+n['duration'])-clock.seconds(n['on']) for n in t['notes']),default=0)
            why=(f'; its longest note lasts {held:.0f} s, and the {"additive" if t["engine"]=="additive" else "built-in"} synth '
                 'makes a note whole: split the note, or play the part on a SoundFont or Surge XT sound')
        raise ValueError(f'{t["id"]}: making this part takes about {need/1e9:.1f} GB at once, more than this machine has '
                         f'({machine/1e9:.1f} GB){why}')

def default_jobs():
    """Parallel parts: one per processor, at most 8; the memory they need is held by MemoryBudget."""
    return max(1,min(8,os.cpu_count() or 1))

# What a part holds at its peak, measured on two-minute parts (research/implementation-0.4.0.md): Python's with
# tracemalloc, in float64 stereo copies of the song (frames x 16 bytes) where it grows with the song, and FluidSynth's
# peak working set, which is its bank's size and some 50 MB (an SF3 bank's compressed samples decoded, about ten times).
TOOL_COPIES={'wow_flutter':1.5,'filter_sweep':17.5,'saturate':9.0,'gate':4.5,'delay':10.6,'duck':2.5}
SURGE_FX_COPIES,SURGE_FX_BYTES=3.0,5e8  # a mix.surge_fx chain: the stem twice here, once in the host; the host's plugin (ours)
STAGE_COPIES,CHORUS_COPIES,AUTOMATION_COPIES,WRITE_COPIES=6.0,4.8,0.5,1.0
AMP_COPIES,AMP_BLOCK_BYTES=1.5,3.0e8  # our arithmetic, not measured: the dry part read, one channel in float64 and the result; a block at eight times the rate with its transforms
STRUNG_COPIES=3.0  # our arithmetic, not measured: a pass and the sum of the passes in float64, and a pass as it is read
MOVE_COPIES=1.0  # our arithmetic, not measured: the stem a movement reads (which automation may have made) and the one it writes, both float32
ENGINE_COPIES={'drum_synth':3.5,'noise':4.9,'layered':5.2}  # layered: two layers and five alike
ADDITIVE_COPIES,ADDITIVE_HELD_COPIES=1.5,5.1  # eighths; a note held through the whole song adds the second
SYNTH_COPIES,SYNTH_PER_HELD_SECOND=2.5,3.0e7  # eighths; each second of its longest voice adds 30 MB (trance_pad)
PART_OVERHEAD=2.5e8  # our allowance for the rest: the interpreter's own work, the MIDI, an FFmpeg pass

REVERSE_FADE_S=.02  # the reversed ring starts from its level at the note's end: a 20 ms fade-in keeps it from clicking

def reversed_notes(p,t,clock,cfg,font,folder,out):
    """A sampled part whose notes play backwards (`reverse: true`): each note rendered alone at its written time, held
    for its written length, on the beat (no timing deviation) and at full gate, and the first `duration` of its sound,
    attack and ring, reversed into the span the note sat in, so it swells and stops on the note's end: a crash cymbal
    reversed into a downbeat, as tape reversal made it.  A note held longer takes more of the ring.  Swing, the part's
    offset, bends and controllers are left out: the reversed sound fills the written span exactly."""
    frames=round((clock.end+clock.tail)*audio.RATE);mix=np.zeros((frames,2),dtype=np.float64)
    fade=max(1,round(REVERSE_FADE_S*audio.RATE))
    for k,n in enumerate(sorted(t['notes'],key=lambda n:(n['on'],n['id']))):
        played={**t['performance']['notes'][n['id']],'timing_ms':0,'gate':1.0}
        perf={k2:v for k2,v in t['performance'].items() if k2 not in ('swing','offset_ms','bend','cc')}
        one={**t,'notes':[n],'performance':{**perf,'notes':{n['id']:played},'cc':[]}}
        mid,wav=folder/f'reverse_{k}.mid',folder/f'reverse_{k}.wav'
        midi.write(p,mid,[one],single_stem=True,render=True)
        audio.fluidsynth(cfg,font['path'],mid,wav,folder,label=f'fluidsynth_reverse_{k}')
        x,_=audio.read_wav(wav);a=round(clock.seconds(n['on'])*audio.RATE);b=min(frames,round(clock.seconds(n['on']+n['duration'])*audio.RATE))
        seg=np.array(x[a:b],dtype=np.float64)[::-1];del x
        ramp=np.linspace(0,1,min(fade,len(seg)))[:,None];seg[:len(ramp)]*=ramp
        mix[a:a+len(seg)]+=seg
        for f in (mid,wav):f.unlink()
    audio.write_wav(out,mix.astype(np.float32))


def part_memory(t,clock,frames,font,surge_plays=False):
    """Bytes a part is expected to hold at its peak, its synthesis or its processing, whichever is more.  A Surge part
    (`surge_plays`: Surge XT is there to play it) renders in a process of its own; otherwise its fallback on the
    built-in synth is counted."""
    copy=frames*16;song=max(1e-9,frames/audio.RATE)
    held=max((clock.seconds(n['on']+n['duration'])-clock.seconds(n['on']) for n in t['notes']),default=0.0)
    engine=t['engine']
    if engine=='soundfont':
        bank=Path(font['path']).stat().st_size*(10 if Path(font['path']).suffix.lower()=='.sf3' else 1)+5e7
        made=max(bank,ENGINE_COPIES['layered']*copy if layered.wanted(t) else 0,STRUNG_COPIES*copy if t.get('strings') else 0)
    elif engine=='additive':made=(ADDITIVE_COPIES+ADDITIVE_HELD_COPIES*min(1.0,held/song))*copy
    elif engine=='surge' and surge_plays:
        made=5e8+copy  # our allowance: the plugin's process, and the part it hands back as float32 stereo
    elif engine in ('synth','surge'):
        # A mono patch's legato line is one voice for up to MONO_LINE_S; a Surge part with no Surge here plays its
        # fallback on the built-in synth.
        line=synth.MONO_LINE_S if engine=='synth' and synth.patch_of(t).get('mono') else 0
        made=SYNTH_COPIES*copy+SYNTH_PER_HELD_SECOND*min(song,held+line)
    else:made=ENGINE_COPIES.get(engine,ENGINE_COPIES['noise'])*copy
    mix=t['mix']
    tools=[TOOL_COPIES[k] for k in TOOL_COPIES if (production.saturating(mix) if k=='saturate' else production.wobbling(mix) if k=='wow_flutter' else mix.get(k))]+[STAGE_COPIES]*(mix.get('depth_m') is not None)
    tools+=[CHORUS_COPIES]*any(e.get('type')=='chorus' for e in mix.get('effects',[]))
    tools+=[AUTOMATION_COPIES]*any(v for _,v in mix.get('automation',[]))
    tools+=[MOVE_COPIES]*bool(mix.get('move'))
    # A Surge XT Effects chain (0.11): the adapter's copy of the stem and the chain's result in this process, and the host,
    # a process of its own, with the stem in and out as float32 and the plugin, counted here as Surge XT's own parts are
    # (our allowance: 5e8 bytes beside the audio)
    if mix.get('surge_fx'):made=max(made,SURGE_FX_BYTES+SURGE_FX_COPIES*copy)
    if mix.get('amp'):return PART_OVERHEAD+max(made,(WRITE_COPIES+max(tools,default=0))*copy,AMP_COPIES*copy+AMP_BLOCK_BYTES)
    return PART_OVERHEAD+max(made,(WRITE_COPIES+max(tools,default=0))*copy)

class MemoryBudget:
    """The memory free when the parts start, shared among those made at once: each holds its estimate (part_memory)
    from before its synthesis to its processed stem, a part waits while the others hold too much of it, and one that
    needs it all runs alone.  Where the free memory cannot be read, parts run `jobs` at a time as before."""
    def __init__(self,free):
        # A fifth of it is kept back for everything else (our choice: the system, the other programs, estimates' error).
        # Whole bytes: float sums of the estimates could leave a residue once every part has let go, and a part that
        # needs it all would wait for ever.
        self.total=None if free is None else int(free*.8);self.used=0;self.ready=threading.Condition()
    @contextlib.contextmanager
    def hold(self,amount):
        if self.total is None:
            yield;return
        amount=min(math.ceil(amount),self.total)
        with self.ready:
            # Looking every 0.2 s whether the render stopped (audio.check_cancel): a part waiting for memory waited on
            # after another failed, then synthesized (found by GPT Pro's fourth review of 0.4.0).
            while not self.ready.wait_for(lambda:self.used+amount<=self.total,timeout=.2):
                audio.check_cancel('a part waiting for memory')
            self.used+=amount
        try:yield
        finally:
            with self.ready:
                self.used-=amount;self.ready.notify_all()

def synthesis_identity(p,clock,t,deps,renderer):
    """What a part's raw synthesis depends on, hashed into its cache key: the clock and the tempo as played (phrase
    rubato slows into section boundaries, so moving a section changes it), the part without its mix, the configured
    dependencies and the synthesis code and preset files.  A mix edit leaves it unchanged and reuses the part."""
    identity={'cache':2,'clock':p['clock'],'played_tempo':clock.tempo,'track':{k:v for k,v in t.items() if k!='mix'},'dependencies':deps,'renderer':renderer,'sample_rate':audio.RATE}
    # a part played by string is synthesized for the loop it is in: a string's last note is ended by the loop's first
    if t.get('strings') and 'loop' in p:identity['loop_start_bar']=p['loop'].get('start_bar',0)
    return identity

def process_seconds(logs):
    """Seconds spent in the FFmpeg processes a render logged, by kind: each run's own `seconds` from its
    *.process.json (a part's synthesis logs into its cache folder, not here)."""
    kinds={}
    for f in sorted(Path(logs).glob('*.process.json')):
        label=f.name[:-len('.process.json')]
        kind=('part processing' if label.startswith('process_') else 'loudness measurement' if label.startswith('measure_')
              else 'delivery limiter' if label.startswith('deliver') else label.split('.')[0])
        kinds[kind]=kinds.get(kind,0)+json.loads(f.read_text(encoding='utf-8')).get('seconds',0)
    return {k:round(v,3) for k,v in sorted(kinds.items(),key=lambda kv:-kv[1])}

# Float64 stereo copies of the song the mix's checks and the master hold at their peaks together (9.5 and 5.0, measured
# with tracemalloc on two bus-chain songs, research/implementation-0.4.0.md).
BOTH_AT_ONCE=15

# The mix fields only the mixer reads (the sends, the delay's time, the bus and the reverb space); the processing of a
# stem (process_stem, stage, production) never reads them, so editing one keeps the part's stem.
MIXER_ONLY=('reverb_db','delay_db','delay_quarters','bus','space')

# A cache entry's folder is named by the first ENTRY_KEY characters of its key, the SHA-256 of what the take depends
# on; the whole key is in the entry's receipt and a take is used only where it is the same (0.9 step 1).  The folder's
# name is the longest part of every path below a piece (65 of up to 115 characters with the whole key, our measurement),
# and where the system opens no path of 260 characters a piece in a deep folder could not be rendered.  20 characters
# are 80 bits: two of a million entries share them once in about 10^12 caches, and then one take is made again in the
# other's place; neither is ever played for the other.
ENTRY_KEY=20

def stem_identity(p,t,key,raw_sha256,frames,code_hash,cfg):
    """What a part's processed stem depends on, hashed into the key of the stem its cache entry keeps: its raw
    synthesis (whose key holds the clock and the tempo as played), its mix but the fields only the mixer reads, the
    song's length, the part a duck follows (its notes as played), the renderer's code, FFmpeg and NumPy."""
    by=(t['mix'].get('duck') or {}).get('by')
    source=next((x for x in p['tracks'] if x['id']==by),None) if by else None
    return {'stem':2,'synthesis':key,'raw_sha256':raw_sha256,'mix':{k:v for k,v in t['mix'].items() if k not in MIXER_ONLY},
            'frames':frames,'ducked_by':{k:v for k,v in source.items() if k!='mix'} if source else None,
            'renderer':code_hash,'ffmpeg':cfg['ffmpeg']['sha256'],'numpy':np.__version__,
            **({'surge_fx':surgefx.identity(t,cfg)} if t['mix'].get('surge_fx') else {})}

def read_json(path):
    """A receipt's JSON object, or {} where there is none or it cannot be read."""
    try:value=files.read_json(path)  # bounded: a cache entry's receipt
    except (OSError,ValueError):return {}
    return value if isinstance(value,dict) else {}

@contextlib.contextmanager
def _holding(lock,what):
    """Hold a threading lock, waiting for it 0.2 s at a time so a stopped render stops waiting (audio.check_cancel)."""
    while not lock.acquire(timeout=.2):
        audio.check_cancel(what)
    try:yield
    finally:lock.release()

@contextlib.contextmanager
def entry_lock(folder,wait=True,create=True):
    """Hold one cache entry against other renders and against clean: an exclusive lock on its file `entry.lock`
    (fcntl.flock on POSIX, msvcrt.locking on Windows), which the system releases when the process ends.  Yields whether
    it is held; without `wait`, False at once when another holds it.  With `create` the entry's folder is made where it
    is missing, and a lock taken on a file that clean removed meanwhile is let go and taken afresh.  Where the drive
    cannot lock, or the entry's folder or lock file cannot be made for want of permission (a cache this user may not
    write, a read-only drive), yields False: the render goes on, making the part in a folder of its own
    (unlocked_cache/ in the render's folder), and the shared cache's files are neither read nor written; taking the
    lock may have made the entry's folder and its entry.lock there.  Any other failure to make the folder (a file
    where it should be) is raised: it is no cache to work beside."""
    folder=Path(folder);lock=folder/'entry.lock'
    for _ in range(10):
        if create:
            # Refused for want of permission, the folder is as unusable as one that cannot be locked: the same way out,
            # where the failure had stopped the render (GPT's re-review of 0.5, RR03).  EROFS is a read-only file
            # system (POSIX, errno.h), which Python raises as a plain OSError, not a PermissionError.
            try:folder.mkdir(parents=True,exist_ok=True)
            except OSError as e:
                if not (isinstance(e,PermissionError) or e.errno==errno.EROFS):raise
                yield False;return
        # A link under the lock's name is refused before it is opened: opening it made a file wherever the link led,
        # and only then did check_entry refuse the entry (GPT's security audit of 0.5, S04).  O_NOFOLLOW (POSIX)
        # refuses one put there since the look, which then counts as an entry that cannot be locked.
        if files.linked(lock):
            raise ValueError(f'Cache entry {folder} holds entry.lock, a link; remove the entry and render again')
        try:fd=os.open(lock,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o644)
        except FileNotFoundError:
            if create:continue  # clean removed the folder between the two calls: make it again
            yield False;return
        except OSError:
            yield False;return
        # Waited for by trying again every 0.2 s, not in the lock call: a render stopped meanwhile (another part
        # failed) stops waiting (audio.check_cancel; found by GPT Pro's fourth review of 0.4.0).
        got=files.lock(fd,False)
        while got is False and wait:
            try:audio.check_cancel('a part waiting for its cache entry')
            except BaseException:
                os.close(fd);raise
            time.sleep(.2);got=files.lock(fd,False)
        held=got is True  # None (a drive that cannot lock) counts as not held
        if held and not files.same_file(fd,lock):
            files.unlock(fd);os.close(fd);continue
        try:yield held
        finally:
            if held:files.unlock(fd)
            os.close(fd)
        return
    yield False

def keep_stem(folder,stem,receipt):
    """Keep a processed stem in its cache entry for the next render: copied to a new file of its own (musiclib.files)
    and swapped in whole, then its receipt likewise.  Keeping is only a saving: where it fails (Windows refuses to
    replace a file another program holds open) the render goes on, and the next one processes the part again."""
    spare=None
    try:
        spare=files.stage_name(Path(folder)/'stem.wav','.wav');shutil.copyfile(stem,spare);files.replace(spare,Path(folder)/'stem.wav');spare=None
        files.write_json(Path(folder)/'stem.json',receipt)
        return True
    except OSError:
        return False
    finally:
        if spare is not None:  # stopped by anything (an error, Ctrl+C) before its copy took the stem's name
            with contextlib.suppress(OSError):spare.unlink()

def check_entry(folder):
    """A cache entry holds only files of its own: a link, or a file with another name (a hard link), would carry a
    write out of it, so such an entry is refused rather than written through."""
    odd=files.foreign(folder)
    if odd:
        raise ValueError(f'Cache entry {folder} holds {odd[0].name}, a link or a file with another name; remove the entry '
                         'and render again')

SYNTHESIS=('played.py','midi.py','audio.py','layered.py','strung.py','sf2.py','synth.py','drums.py','variation.py','surge.py','wavfile.py')

def module_closure(names):
    """The musiclib modules `names` import, directly or through one another, with themselves: the code a cached
    synthesis depends on (a noise part's vinyl reaches vinyl.py and measure.py this way; 0.11 moved it out of
    production.py, the mix's processing, which the closure no longer holds)."""
    here=Path(__file__).parent;seen=set();todo=list(names)
    while todo:
        name=todo.pop()
        if name in seen or not (here/name).is_file():continue
        seen.add(name)
        for node in ast.walk(ast.parse((here/name).read_text(encoding='utf-8'))):
            if isinstance(node,ast.ImportFrom) and node.level==1:
                todo+=[node.module.split('.')[0]+'.py'] if node.module else [a.name+'.py' for a in node.names]
    return sorted(seen)

def stopped(folder):
    """Why the render in `folder` stopped before it finished (the error its report.json gives), or None."""
    report=Path(folder)/'report.json'
    if not files.regular_file(report) or files.lstat(report).st_size>files.MAX_RECORD:return None
    try:r=files.loads(report.read_bytes())   # as bytes, as files.read_json reads a record: a mark or UTF-16 hid the failure (the review of 0.8.0)
    except (OSError,ValueError):return None
    failed=r.get('failed') if isinstance(r,dict) else None
    return (failed.get('error') or 'stopped') if isinstance(failed,dict) else None

def delivered(checks,draft,tail_fails=None):
    """(passed, needs) of a render's delivery checks.  That a piece ends in silence (`tail_quiet`) is a property of the
    delivered file: a draft whose master still sounds at its end passes, and `needs` names the check for the report
    and the summary to say so at every draft until the tail is long enough (three of nine real sessions of 0.8.0 lost
    a round to it: the render stopped, with no analysis and no comparison).  A full render fails on it, and so does a
    draft told to (`tail_fails`: an audition's render, which is made again with a longer tail).  Any other failed
    check fails either."""
    strict=(not draft) if tail_fails is None else tail_fails
    needs=[] if strict or checks.get('tail_quiet',True) else ['tail_quiet']
    return all(ok for k,ok in checks.items() if k not in needs),needs

def earlier_delivery(report):
    """The files, by their names in the render's folder, that an earlier full render made for delivery and a draft
    leaves out: what a draft taken up in that folder removes.  From that render's own report, and only what it
    lists: a full render that got as far as its checks (passed, or failed one: its files were made before it was
    checked) made master.flac, the loop's Ogg copy where its report has one, and of each layer the files its report
    names; a full render stopped before its report, a draft, or no report at all made nothing that is known.  (By the
    mode alone, a draft after a full render that had stopped removed a file a tool had written under a layer's name;
    by the project's layers, an Ogg copy the render never made: the reviews of 0.9.)"""
    if not isinstance(report,dict) or report.get('draft') is not False or 'failed' in report or not isinstance(report.get('checks'),dict):return []
    loop=report.get('loop') if isinstance(report.get('loop'),dict) else {}
    listed=lambda files,kind:isinstance(files,dict) and kind in files
    names=['master.flac']+(['loop.ogg'] if listed(loop.get('files'),'ogg') else [])
    parts=loop['layers'].get('parts') if isinstance(loop.get('layers'),dict) else None
    for lid,layer in (parts.items() if isinstance(parts,dict) else ()):
        if not (isinstance(lid,str) and re.fullmatch(r'[a-z][a-z0-9_]{0,47}',lid) and isinstance(layer,dict)):continue   # (a layer's id, as validate takes it)
        names+=[f'layers/{lid}.{kind}' for kind in ('wav','ogg') if listed(layer.get('files'),kind)]+[f'layers/{lid}_premix.filtergraph.txt']
    return names

def tail_state(data):
    """How a master (frames, 2) ends: the peak of its last 50 ms in dBFS (`tail_quiet` asks for less than -60), how
    fast its level falls (dB a second: a straight line through the peaks of its last second, 50 ms by 50 ms), and from
    the two an estimate of how many more seconds would bring it under -60 dBFS, to the next half second.  An
    estimate: a cymbal's ring falls nearly so, a reverb's last second need not.  No figure where the end is quiet
    already, where the level is not falling by 3 dB a second, or where it rises again by as much in its last fifth of a second
    (`rises_at_the_end`: another note or an echo begins there, and the second's fall says nothing of it)."""
    peaks=np.max(np.abs(np.asarray(data,dtype=np.float64)).reshape(len(data),-1),axis=1) if len(data) else np.zeros(0)
    step=2400;n=min(20,len(peaks)//step)
    level=lambda x:20*math.log10(max(float(x),1e-9))
    last=level(np.max(peaks[-step:])) if len(peaks) else level(0)
    falling=0.0;rises=False
    if n>=4:
        levels=[level(np.max(peaks[len(peaks)-(k+1)*step:len(peaks)-k*step])) for k in range(n)][::-1]
        falling=-float(np.polyfit(np.arange(n)*step/audio.RATE,levels,1)[0])
        rises=last>-60 and float(np.polyfit(np.arange(4)*step/audio.RATE,levels[-4:],1)[0])>=3   # its last four 50 ms peaks, by their own line: 3 dB a second or more, as for the fall
    more=math.ceil((last+60)/falling*2)/2 if last>-60 and falling>=3 and not rises else None
    return {'last_50ms_dbfs':round(last,1),'falling_db_per_second':round(falling,1),'rises_at_the_end':bool(rises),'more_seconds_estimated':more}

def highest_sample(frame,clock):
    """Where a master's highest sample lies: its second, with the bar of the score, or `in_tail` past the last bar."""
    at=frame/audio.RATE
    return {'seconds':round(at,3),**({'bar':int(clock.beat(at)//clock.beats_per_bar)+1} if at<clock.end else {'in_tail':True})}

def peak_frames(data,quiet=.001):
    """The frame of a master's highest sample, and of its last sample at `quiet` (-60 dBFS, as tail_quiet reads it) or over,
    -1 where none: read a second at a time, so that a long master is not held in memory a second time."""
    top,last,highest=0,-1,-1.0
    for at in range(0,len(data),audio.RATE):
        block=np.max(np.abs(np.asarray(data[at:at+audio.RATE],dtype=np.float32)),axis=1);k=int(np.argmax(block))
        if float(block[k])>highest:top,highest=at+k,float(block[k])
        over=np.flatnonzero(block>=quiet)
        if len(over):last=at+int(over[-1])
    return top,last

def tail_advice(state):
    """What to do about a tail that still sounds, with the estimate where there is one."""
    more=state.get('more_seconds_estimated');falling=state.get('falling_db_per_second') or 0
    if state.get('rises_at_the_end'):return 'its level rises in its last moments (a note or an echo that begins there, or a level that is raised): let it end, or give clock.tail_seconds the time it needs'
    if more is None and falling>=.05:return f'its level falls only {falling:g} dB a second at the end, too slowly for an estimate: look for a note or an effect that rings on (a long release, a held pedal, a delay\'s feedback), then give clock.tail_seconds the time it needs'
    if more is None:return 'its level is not falling at the end: look for a note or an effect that does not stop, then give clock.tail_seconds the time it needs'
    return (f'by the fall of its last second, about {more:g} more second{"s" if more!=1 else ""} of clock.tail_seconds would bring it under (an estimate: leave a second more, as a ring slows while it fades; alone it fell short on 15 of 93 tails cut from finished pieces, with the second on 5)')

def render(project_file,output,config_file,cache=None,resume=False,jobs=None,draft=False,quiet=(),tail_fails=None):
    """Render a project into the new folder `output` (or take up an unfinished render of the same project there with
    `resume`, stopped at any moment, killed even).  Whatever happens, what it wrote is recorded in the folder's
    files.json, and while it works its journal proves each file it is writing (musiclib.files): all clean ever removes of
    it, and all a resume writes over.  `quiet`: parts that may barely sound (the other parts of an audition's passage, where
    a held note's last moment is all a part plays): they keep their own level instead of stopping the render."""
    if files.linked(Path(output)):
        # Resolving it first would follow the link (a dangling one included) and write wherever it leads.
        raise ValueError(f'{output} is a link; give a new folder (a render never writes through a link)')
    if cache is not None and files.linked(Path(cache)):
        # Likewise the cache: it was resolved first, and the check after it then saw the folder the link led to, where
        # the render made its entries (GPT's security audit of 0.5, S03).
        raise ValueError(f'The cache {cache} is a link; give the folder itself')
    output=Path(output).resolve();claim={};started=time.monotonic()
    with contextlib.ExitStack() as held:  # the folder's work lock (files.working), let go after its record is written
        claim['hold']=held.enter_context
        try:
            return _render(project_file,output,config_file,cache,resume,jobs,draft,claim,set(quiet),tail_fails)
        except BaseException as e:
            # A render stopped before its report: report.json says so, after which stage, in which part and why, as a
            # round's record does for its steps.  (A failed delivery check has written its full report already.)
            if claim.get('folder') and not claim.get('reported'):
                stages=dict(claim.get('stages') or {})
                with contextlib.suppress(OSError,ValueError):
                    save_json(output/'report.json',{'status':'FAIL','title':claim.get('title'),'draft':draft,
                              'failed':{'after_stage':next(reversed(stages),None),'part':getattr(e,'render_part',None),'error':str(e) or type(e).__name__},
                              'stage_seconds':stages,'runtime_seconds':round(time.monotonic()-started,2)})
            raise
        finally:
            if claim.get('folder'):
                with contextlib.suppress(OSError):
                    files.register_tree(output,keep=claim.get('kept'))
                    files.drop_journal(output)  # the record lists everything the journal proved

def _render(project_file,output,config_file,cache,resume,jobs,draft,claim,quiet,tail_fails=None):
    started=time.monotonic();p=load_project(project_file);clock=Clock(p);cfg=audio.load_config(config_file)
    # Seconds per stage, each from the end of the one before, so they add up to the runtime (profiling the stages
    # before any is optimized: what a change saves shows here).
    stages={};mark=[started];claim.update(stages=stages,title=p['title'])
    def lap(name):
        now=time.monotonic();stages[name]=round(now-mark[0],3);mark[0]=now
        if claim.get('folder'):
            # What the render wrote so far is recorded at the end of each stage, not only when it ends, and the journal
            # proves what the stage at work writes (found by GPT Pro's third review of 0.4.0: a killed render's last stage
            # was named by clean and refused by --resume).
            files.register_tree(output,keep=claim.get('kept'))
    output=Path(output).resolve();cache=Path(cache).resolve() if cache else output.parent/'cache'
    # Before anything is synthesized: every part's bank is configured and can play what the part asks of it.
    fonts={t['id']:audio.soundfont_for(cfg,t)[1] for t in p['tracks'] if t['engine']=='soundfont'}
    for path in {font['path'] for font in fonts.values()}:bankcheck.refuse_unsafe(path)   # every FluidSynth launch of a render plays one of these
    problems=[m for t in p['tracks'] if t['id'] in fonts for m in [layered.unsupported(t,fonts[t['id']]['path'])] if m]
    if problems:raise ValueError('Parts the banks cannot play as written (review --config lists them too): '+' '.join(problems))
    # And no part needs more memory at once than the machine has.  (Whether Surge XT plays each Surge part is read
    # once here, and is part of that part's cache key.)
    surge_deps={t['id']:surge.dependencies(cfg,t) for t in p['tracks'] if t['engine']=='surge'}
    too_large(p,clock,round((clock.end+clock.tail)*audio.RATE),fonts,total_memory(),surge_deps)
    project_key=digest(p);marker=output/'render_input.json'
    code_hash=engine_hash()
    # A cached part depends on the code its synthesis runs and on the preset files the built-in synth and Surge parts read.
    synthesis_hash=digest({**{n:file_hash(Path(__file__).with_name(n)) for n in module_closure(SYNTHESIS)},
                           'synth-presets':file_hash(synth.PRESETS_FILE),'surge-presets':file_hash(surge.PRESETS_FILE)})
    resumed=files.occupied(output)
    if resumed:
        if not resume:raise ValueError('Output exists; choose a fresh directory or resume the same project')
        # A folder a render takes up again holds only what renders write: a link or a hard link in it would carry a
        # write out of the folder, so it is refused rather than written through.
        files.no_links(output)
        claim['hold'](files.working(output))  # before reading what is there: clean may be removing it
        odd=files.foreign(output)
        if odd:raise ValueError(f'{output} holds links or files with other names ({", ".join(str(x.relative_to(output)) for x in odd[:5])}); '
                                'render into a new folder')
        # A resumed render writes over its own files only: what is there must be the earlier render's, as its record
        # lists it unchanged or its journal proves it, the files of the stage a kill stopped included.  A file it did
        # not write, or one changed since, stops it before anything is written or removed.
        found,listed=files.proofs(output),files.recorded(output)
        own=lambda x:files.unchanged(x,listed.get(files.relative(output,x),(-1,-1))) or files.proven(output,x,found)
        strays=[x for x in files.tree(output) if x.name not in (files.RECORD,files.JOURNAL) and not (x.parent==output and files.is_lock_file(x)) and not own(x)]
        # A file under a name the journal gave a new file, which the journal cannot prove the render's.  Either it was
        # named and never noted made: the render stopped in the instant between making it and noting it (8 of 212
        # hard kills on Windows, measured), or the making failed on a file already there.  Or it is not the file
        # noted made: a program the stopped render had started wrote it anew, or someone put it there since.  Said
        # as such, without claiming the render made it, so the user can tell it from a file of their own (GPT's
        # review of 0.5, C01, and its re-review, RR01).
        unmade=[x for x in strays if files.relative(output,x) in found[0]]
        if strays and len(unmade)==len(strays):
            raise ValueError(f'{output} holds files under names the earlier render gave new files, which it cannot prove it made '
                             f'({", ".join(x.relative_to(output).as_posix() for x in strays[:5])}): its journal has no note that the file was made, '
                             'or the file there now is not the one it noted.  They may be the stopped render\'s, or have been there before, '
                             'or been put there since, so they are kept; check where they came from, then remove them and resume, '
                             'or render into a new folder')
        if strays:raise ValueError(f'{output} holds files the earlier render did not write, or that changed since '
                                   f'({", ".join(x.relative_to(output).as_posix() for x in strays[:5])}); move them away or render into a new folder')
        if files.regular_file(marker):
            if read_json(marker).get('project_sha256')!=project_key:
                raise ValueError('Output exists; choose a fresh directory or resume the same project')
        elif [x for x in files.tree(output) if x.name not in (files.RECORD,files.JOURNAL) and not (x.parent==output and files.is_lock_file(x))
              and files.relative(output,x) not in found[0]]:
            # Killed before it wrote its marker, a render leaves only new files its journal names: anything else here
            # cannot be told for the same project's.
            raise ValueError('Output exists; choose a fresh directory or resume the same project')
    if files.linked(cache):raise ValueError(f'The cache {cache} is a link; give the folder itself')
    # The half-written files of a stopped stage go; what had taken its name stays the run's (files.adopt).
    claim['kept']=files.adopt(output) if resumed else {}
    earlier=read_json(output/'report.json') if resumed and draft and files.regular_file(output/'report.json') else None
    if earlier_delivery(earlier):
        # A draft taken up in a full render's folder (its report says it was one: over an earlier draft, or a render
        # stopped before its report, nothing is taken for a delivery).  What only delivery makes (master.flac, a loop's Ogg copy and
        # its layers) would lie there as files of an earlier master, in a folder whose report says a draft leaves
        # them out: they go first, by the names the delivery gives them and nothing else in those folders (an
        # analysis saved beside the layers is the folder's own too, by its record, and stays), before the draft does
        # any work, so that one that cannot be removed (read-only: left so, it may be meant) stops it with the folder as it was.
        named=[output/name for name in earlier_delivery(earlier)]
        there=[x for x in named if files.regular_file(x) and files.relative(output,x) in claim['kept']]
        gone=[]
        for x in there:
            try:x.unlink()
            except OSError as e:
                raise ValueError(f'{output} holds a full render\'s {files.relative(output,x)}, which a draft leaves out and which could not be removed '
                                 f'({e.strerror or e}); remove it, or render the draft into a new folder'
                                 +(f' (already removed: {", ".join(gone)}; a full render makes them again)' if gone else '')) from None
            gone.append(files.relative(output,x))
        with contextlib.suppress(OSError):(output/'layers').rmdir()
        claim['earlier_delivery']=gone
    output.mkdir(parents=True,exist_ok=True)
    if not resumed:claim['hold'](files.working(output))  # a render started into the same new folder meanwhile is refused
    claim['hold'](files.journaled(output))  # from the first file it writes, the marker
    for d in (cache,output/'logs',output/'stems',output/'midi',output/'returns'):d.mkdir(parents=True,exist_ok=True)
    from . import ears
    if ears.wanted(p):
        # the headphone version (musiclib/ears.py): each part is also processed without its place, where its take is held
        for d in (output/'headphones'/'centre'/'stems',output/'headphones'/'centre'/'logs'):d.mkdir(parents=True,exist_ok=True)
    # The render's first file, which names the piece too: clean tells a render killed before its project.json for the piece's.
    save_json(marker,{'project_sha256':project_key,'renderer_sha256':code_hash,'title':p['title']})
    claim.update(folder=True,resumed=resumed)
    save_json(output/'project.json',p)
    lap('prepare')
    route=midi.write(p,output/'composition.mid')
    midi.write(p,output/'score.mid',expressive=False)
    save_json(output/'midi_routing.json',route)
    parsed=midi.read_own(output/'composition.mid')
    if any(t['unclosed'] or t['stray_offs'] for t in parsed['tracks']):raise ValueError('Exported MIDI lifecycle failed')
    note_count=sum(len(t['notes']) for t in parsed['tracks'])
    expected=sum(len(t['notes']) for t in p['tracks'])
    if note_count!=expected:raise ValueError('MIDI note count mismatch')
    lap('midi')
    duration=clock.end+clock.tail;frames=round(duration*audio.RATE)
    jobs=max(1,min(jobs or default_jobs(),len(p['tracks'])));locks={};guard=threading.Lock();budget=MemoryBudget(free_memory())
    def make_stem(t):
        began=time.monotonic()
        font_name,font=audio.soundfont_for(cfg,t) if t['engine']=='soundfont' else (None,None)
        deps={'fluidsynth':cfg['fluidsynth']['sha256'],'soundfont':font['sha256'] if font else None}
        if t['engine']=='surge':deps['surge']=surge_deps[t['id']]
        identity=synthesis_identity(p,clock,t,deps,synthesis_hash)
        whole=digest(identity);key=whole[:ENTRY_KEY];folder=cache/key
        if files.linked(folder):raise ValueError(f'Cache entry {folder} is a link; remove it and render again')
        raw=folder/'raw.wav';receipt=folder/'receipt.json'
        track_midi=output/'midi'/(t['id']+'.mid')
        midi.write(p,track_midi,[t],single_stem=True)
        with guard:lock=locks.setdefault(key,threading.Lock())
        # The entry is held from the cache lookup to the kept stem: a render of the piece running at the same time waits
        # here for this part, then finds it in the cache.  The part's memory is taken first, before any lock, so a part
        # never waits for memory while it holds an entry another part waits on.
        asked=time.monotonic()
        with budget.hold(part_memory(t,clock,frames,font,deps.get('surge',{}).get('plays')=='Surge XT')),_holding(lock,t['id']),entry_lock(folder) as held,contextlib.ExitStack() as entry:
          waited=time.monotonic()-asked
          audio.check_cancel(t['id'])  # stopped while it waited: nothing is synthesized
          if held:entry.enter_context(files.journaled(folder))
          else:
              # Where the entry cannot be locked (a drive without locks, a cache this user may not write, or clean took
              # it from under the lock ten times), the part is made in a folder of this render's own, which its journal
              # and record cover, and the shared cache's files are neither read nor written: unlocked, another render
              # could drop the journal this one writes there, and each would record the other's files (GPT's review of
              # 0.5, C04).  Trying for the lock may have made the entry's folder and its entry.lock there, nothing
              # else.  Nothing is cached for later renders.
              folder=output/files.UNLOCKED_CACHE/key;folder.mkdir(parents=True,exist_ok=True)
              raw,receipt=folder/'raw.wav',folder/'receipt.json'
          check_entry(folder)
          # The entry keeps a record of its own (files.json), of what renders wrote in it, and a journal while one works
          # in it, so clean removes an entry by the files a render proves it wrote, not by their names (left for 0.5 by
          # GPT Pro's third review of 0.4.0).  A render stopped in the entry leaves only files the journal proves: the
          # next one to hold the entry removes those half written and keeps the rest as renders' (files.adopt).
          entry_keep=files.adopt(folder) if held else None
          try:
            cached=False;raw_sha=None;old=read_json(receipt) if files.regular_file(raw) else {};rejected={}
            if old:
                # 0.8 step 1.4: the take's header and length checked from the file before it is hashed: exactly the
                # render's frames from an empty part, a reversed one, the built-in engines and Surge's fallback where
                # Surge XT is not configured; from FluidSynth, layered takes and Surge XT, whose tails vary, no longer
                # than the ceiling.  A take that fails is made again, the reason in this render's receipt only.
                exact=(not t['notes'] or (t['engine']=='soundfont' and bool(t.get('reverse'))) or t['engine'] in ('additive','synth','drum_synth','noise')
                       or (t['engine']=='surge' and deps['surge'].get('plays')!='Surge XT'))
                fault=audio.take_fault(raw,frames if exact else None)
                if fault:rejected['raw']=fault
                else:
                    raw_sha=audio.audio_hash(raw);cached=old.get('key')==key and old.get('identity')==whole and raw_sha==old.get('sha256')
                    # a part played by string is its take and the record of how it was played: without the record it is made again
                    if cached and t.get('strings') and not read_json(folder/'strung.json'):cached=False;rejected['raw']='its record of the strings is missing'
            if not cached:
                # Synthesized into a new file of its own (musiclib.files), which then takes raw.wav's place whole.
                fresh=files.stage_name(raw,'.wav')
                try:
                    if not t['notes']:
                        audio.write_wav(fresh,np.zeros((frames,2),dtype=np.float32))
                        if t.get('strings'):
                            from . import strung
                            save_json(folder/'strung.json',strung.empty())
                    elif t['engine']=='soundfont' and t.get('reverse'):reversed_notes(p,t,clock,cfg,font,folder,fresh)
                    elif t['engine']=='soundfont' and t.get('strings'):
                        # Played by string (musiclib/strung.py): passes of the ordinary synthesis, summed.
                        from . import strung
                        save_json(folder/'strung.json',strung.render(p,t,clock,cfg,font,folder,fresh))
                    elif t['engine']=='soundfont' and layered.wanted(t):layered.render(p,t,clock,cfg,font,folder,fresh)
                    elif t['engine']=='soundfont':
                        # The synthesis MIDI applies the track's render patch/key map; the exported part MIDI does not.
                        patch=t.get('patch') or {'bank':t.get('bank',0),'program':t.get('program',0)}
                        keys=variation.key_samples(font['path'],patch.get('bank',0),patch.get('program',0)) if t['performance'].get('round_robin') else None
                        # Each hit of a drum part takes one of the bank's recorded takes unless round_robin is set false.
                        cycles=variation.velocity_cycles(font['path'],patch.get('bank',0),patch.get('program',0)) if t.get('drums') and t['performance'].get('round_robin',True) is not False else None
                        synth_midi=folder/'synth.mid';midi.write(p,synth_midi,[t],single_stem=True,render=True,keys=keys,cycles=cycles)
                        audio.fluidsynth(cfg,font['path'],synth_midi,fresh,folder)
                    elif t['engine']=='additive':audio.synthesize(p,t,fresh)
                    elif t['engine']=='synth':synth.render(p,t,fresh,clock)
                    elif t['engine']=='surge':
                        # Surge XT when it is installed; otherwise the part's fallback preset on the built-in synth.
                        played={'preset':t['surge']['preset']}
                        try:played.update(surge.render(p,t,fresh,folder,cfg) or {});played['rendered_with']='Surge XT'
                        except surge.Unavailable as e:
                            fallback=surge.fallback_track(t);synth.render(p,fallback,fresh,clock)
                            played.update(rendered_with='built-in synth',fallback=fallback['synth']['preset'],reason=str(e))
                        save_json(folder/'surge.json',played)
                    elif t['engine']=='drum_synth':drums.render(p,t,fresh,clock)
                    else:audio.noise_fx(p,t,fresh)
                    files.replace(fresh,raw)
                except BaseException:
                    with contextlib.suppress(OSError):fresh.unlink()
                    raise
                raw_sha=audio.audio_hash(raw)
                save_json(receipt,{'key':key,'identity':whole,'sha256':raw_sha,'track':t['id']})
            synthesized=time.monotonic()
            audio.check_cancel(t['id'])  # between synthesis and processing, which runs no program to stop
            stem=output/'stems'/(t['id']+'.wav')
            # The processed stem the cache entry keeps, used when nothing it depends on has changed: the copy this
            # render mixes is what is checked against the receipt read before it.
            frozen,frozen_receipt=folder/'stem.wav',folder/'stem.json'
            identity=stem_identity(p,t,whole,raw_sha,frames,code_hash,cfg)
            stem_key=digest({**identity,'quiet':t['id'] in quiet});expected_fx=(identity.get('surge_fx') or {}).get('state')
            kept=read_json(frozen_receipt);reused=False
            usable=kept.get('key')==stem_key and isinstance(kept.get('processing'),dict) and {'reference_level_dbfs','gain_db','filter_chain'}<=set(kept['processing']) and frozen.is_file()
            if usable and (fault:=audio.take_fault(frozen,frames)):rejected['stem'],usable=fault,False  # exactly the render's frames (1.4)
            fx_was=kept.get('processing',{}).get('surge_fx') if usable else None
            if isinstance(fx_was,dict) and fx_was.get('repeat') not in (None,'exact'):
                # A stem whose chain is not exact is used only beside the take it was made from, so that the headphone version
                # plays that take too: a failed edit had replaced the take and kept the stem (Astra's review b011d)
                # (checked as the chain's own run would take it again: key, length, samples and report; a damaged take had
                # left the headphone version on a new one: Astra's review b011e)
                if not fx_was.get('take_key') or not surgefx.take_is_kept(folder,fx_was['take_key'],frames,t):
                    rejected['stem'],usable='its chain is not exact, and the take it was made from is not kept beside it',False
            if usable:
                # Copied under a name of its own and checked before it takes the stem's name: a copy that fails or
                # does not match leaves no stem, half or otherwise, and the part is processed again.
                copy=None
                try:
                    copy=files.stage_copy(frozen,stem)
                    if file_hash(copy)==kept.get('sha256'):files.replace(copy,stem);reused=True
                except OSError:reused=False
                finally:
                    if copy is not None:
                        with contextlib.suppress(OSError):os.unlink(copy)
            if reused:done,stem_sha=kept['processing'],kept['sha256']
            else:
                done=process_stem(p,t,clock,cfg,output,raw,stem,frames,quiet=t['id'] in quiet,expected_fx=expected_fx,fx_take=folder);stem_sha=file_hash(stem)
                if (done.get('surge_fx') or {}).get('cached',True):keep_stem(folder,stem,{'key':stem_key,'sha256':stem_sha,'track':t['id'],'processing':done})
            phones=None
            if ears.wanted(p):
                unplaced=output/'headphones'/'centre'
                # (a chain that is not exact plays the take the speaker stem's kept in the entry: one take of the part)
                phones=process_stem(p,ears.unplaced(t),clock,cfg,unplaced,raw,unplaced/'stems'/(t['id']+'.wav'),frames,quiet=t['id'] in quiet,expected_fx=expected_fx,fx_take=folder)
            expressive=read_json(folder/'layered.json') if (folder/'layered.json').is_file() else None
            heard=read_json(folder/'surge.json') if t['engine']=='surge' and (folder/'surge.json').is_file() else None
            by_string=read_json(folder/'strung.json') if t.get('strings') and (folder/'strung.json').is_file() else None
          finally:
            if held:
                with contextlib.suppress(OSError):
                    files.register_tree(folder,keep=entry_keep)
                    files.drop_journal(folder)
        receipt_data={'track':t['id'],'soundfont':font_name,'cache_key':key,'cache_hit':cached,'stem_key':stem_key,'stem_reused':reused,'raw_sha256':raw_sha,'stem_sha256':stem_sha,'reference_level_dbfs':done['reference_level_dbfs'],'gain_db':done['gain_db'],'processed_stem':str(stem.relative_to(output)),'filter_chain':done['filter_chain'],'same_pitch_retrigger_trims':retrigger_trims(t,clock)}
        if not held:receipt_data['unlocked_cache']=True  # made in the render's own folder: nothing cached (C04)
        if rejected:receipt_data['cache_rejected']=rejected  # a cached take or stem found unfit and made again (1.4)
        if expressive:receipt_data['expressive']=expressive
        if heard:receipt_data['surge']=heard
        if by_string:receipt_data['strung']=by_string
        if done.get('nearly_silent'):receipt_data['nearly_silent']=True
        if done.get('automation_points'):receipt_data['automation_points']=done['automation_points']
        if done.get('stage'):receipt_data['stage']=done['stage']
        if done.get('move'):receipt_data['move']=done['move']
        if done.get('amp'):receipt_data['amp']=done['amp']
        if done.get('production'):receipt_data['production']=done['production']
        if done.get('surge_fx'):receipt_data['surge_fx']=done['surge_fx']
        # The headphone version processes the part again; where its chain did not do what the speaker stem's did (a run
        # that failed there alone), the receipt and the report say so (Astra's review b011a).
        if phones and (phones.get('surge_fx') or {}).get('state')!=(done.get('surge_fx') or {}).get('state'):
            receipt_data['surge_fx_headphones']=phones['surge_fx']
        elif phones and (phones.get('surge_fx') or {}).get('take_reused') is False:
            # a chain that is not exact, run again for the headphone version (the speaker stem's take could not be kept or read)
            receipt_data['surge_fx_headphones_own_take']=True
        # Each part's own seconds (they overlap: parts run `jobs` at a time); synthesis includes the cache lookup.
        receipt_data['seconds']={'waiting':round(waited,3),'synthesis':round(synthesized-began-waited,3),'processing':round(time.monotonic()-synthesized,3)}
        return receipt_data,font_name,font
    cancel=threading.Event();first_failure=[];failure_lock=threading.Lock()
    def stem_of(t):
        if cancel.is_set():raise audio.Cancelled(f'{t["id"]}: not started, another part failed')
        try:
            with audio.cancel_scope(cancel):return make_stem(t)
        except BaseException as e:
            # The part travels with its own error, so the report names the part whose error the render stops on.
            with contextlib.suppress(Exception):
                if getattr(e,'render_part',None) is None:e.render_part=t['id']
            # The first failure is kept before the others are stopped: a part it stopped fails too (Cancelled), and
            # one submitted earlier was reported in its place (found by GPT Pro's fourth review of 0.4.0).
            with failure_lock:
                if not first_failure and not isinstance(e,audio.Cancelled):first_failure.append(e)
            # Set here, before this thread takes the next waiting part: set by the main thread, a part could start
            # in the moment between (found by the selfcheck of the fix).
            cancel.set()
            raise
    # The first part to fail stops the render at once: the parts waiting do not start, and those at work stop the
    # program they run (audio.run), so the render ends on that part's error without the others' time (they ran on to
    # their end; found by GPT Pro's third review of 0.4.0).  Ctrl+C stops them the same way.
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures=[pool.submit(stem_of,t) for t in p['tracks']]
        try:
            done,_=wait(futures,return_when=FIRST_EXCEPTION)
        except BaseException:
            cancel.set()
            for f in futures:f.cancel()
            raise
        first=[f for f in futures if f in done and f.exception() is not None]
        if first:
            cancel.set()
            for f in futures:f.cancel()
    if first_failure:raise first_failure[0]
    if first:raise first[0].exception()
    results=[f.result() for f in futures]
    receipts=[r for r,_,_ in results];used_fonts={name:font for _,name,font in results if font}
    save_json(output/'stem_receipts.json',receipts)
    lap('parts')
    chain_name=p['mix'].get('chain','room');buses=None;mp3=None
    if chain_name=='bus':
        from . import mixbus
        buses=mixbus.mix(p,clock,cfg,output,frames)
        lap('mix')
        # The mix's checks read only what it wrote, so they run while the master is made (its loudness passes wait on
        # FFmpeg) where the memory holds both (BOTH_AT_ONCE); with less free, or where the free memory cannot be read,
        # after it.  The last delivery pass measured master.wav as it is kept: that measurement is the master's.
        if (free_memory() or 0)>=BOTH_AT_ONCE*frames*16:
            with ThreadPoolExecutor(max_workers=1) as side:
                verified=side.submit(mixbus.verify,p,output,buses)
                before,mastering,after=mixbus.master(p,cfg,output)
                lap('master')
                buses.update(verified.result())
        else:
            before,mastering,after=mixbus.master(p,cfg,output)
            lap('master')
            buses.update(mixbus.verify(p,output,buses))
        lap('mix_checks')
    else:
        before,mastering=room_mix(p,clock,cfg,output,frames,duration)
        lap('mix_and_master')
    master=output/'master.wav'
    if chain_name!='bus':after=audio.measure(cfg,master,output/'logs','measure_master')
    from .mixbus import true_peak_ceiling  # both chains: the room chain never imports mixbus otherwise
    tp_max=true_peak_ceiling(p['mix'].get('target_lufs',-16))
    if after['true_peak_dbtp']>tp_max or after['clipped_samples'] or after['frames']!=frames:
        raise ValueError(f'Master delivery check failed: true peak {after["true_peak_dbtp"]:g} dBTP (at most {tp_max:g}), '
                         f'{after["clipped_samples"]} clipped samples, {after["frames"]} of {frames} frames')
    lap('master_check')
    heard=None
    if ears.wanted(p):
        heard=ears.deliver(p,clock,cfg,output,frames)
        audio.ffmpeg(cfg,['-i',output/'headphones.wav','-c:a','libmp3lame','-b:a','256k',output/'headphones.mp3'],output/'logs','mp3_headphones')
        lap('headphones')
    # The files made from the master do not depend on each other and are made at once: the MP3 (and in a full bus
    # render the check that it decodes to the master's loudness), master.flac and a game loop.
    def preview():
        audio.ffmpeg(cfg,['-i',master,'-c:a','libmp3lame','-b:a','256k',output/'preview.mp3'],output/'logs','mp3')
        return mixbus.mp3_check(cfg,output,after['integrated_lufs']) if chain_name=='bus' and not draft else None
    def lossless():
        audio.ffmpeg(cfg,['-i',master,'-c:a','flac',output/'master.flac'],output/'logs','flac')
    def looping():
        from . import loop
        return loop.deliver(p,clock,cfg,output,mastering,draft)
    # They share a stop (audio.cancel_scope), as the parts do: Ctrl+C, or one of them failing, stops the programs the
    # others run, and the render ends on the first failure without waiting for them (they ran to their end, and a
    # failure was seen only once the outputs before it had ended; found by GPT Pro's fifth review and its selfcheck).
    stop_outputs=threading.Event();output_failure=[];output_lock=threading.Lock()
    def scoped(make):
        def run():
            try:
                with audio.cancel_scope(stop_outputs):return make()
            except BaseException as e:
                with output_lock:
                    if not output_failure and not isinstance(e,audio.Cancelled):output_failure.append(e)
                stop_outputs.set()
                raise
        return run
    with ThreadPoolExecutor(max_workers=3) as pool:
        made=[pool.submit(scoped(preview))]+([] if draft else [pool.submit(scoped(lossless))])+([pool.submit(scoped(looping))] if 'loop' in p else [])
        try:wait(made,return_when=FIRST_EXCEPTION)
        except BaseException:
            stop_outputs.set()
            for f in made:f.cancel()
            raise
    if output_failure:raise output_failure[0]
    results=[f.result() for f in made]
    mp3,looped=results[0],(results[-1] if 'loop' in p else None)
    from .measure import release
    release()  # the measuring is done: the K-weighting responses kept for it are let go
    lap('outputs')
    data,_=audio.read_wav(master);sections=[]
    for s in p['sections']:
        start=clock.seconds(s['start_bar']*clock.beats_per_bar);end=clock.seconds((s['start_bar']+s['bars'])*clock.beats_per_bar)
        a=data[round(start*audio.RATE):round(end*audio.RATE)]
        mid=(a[:,0]+a[:,1])/2;side=(a[:,0]-a[:,1])/2
        active=[t['id'] for t in p['tracks'] if any(s['start_bar']*clock.beats_per_bar<=n['on']<(s['start_bar']+s['bars'])*clock.beats_per_bar for n in t['notes'])]
        sections.append({**s,'start_seconds':round(start,3),'end_seconds':round(end,3),'rms_dbfs':round(20*math.log10(max(1e-12,audio.rms(a))),3),'side_mid_db':round(20*math.log10(max(1e-12,audio.rms(side)/max(audio.rms(mid),1e-12))),3),'active_tracks':active})
    checks={'finite':bool(np.isfinite(data).all()),'no_clipping':after['clipped_samples']==0,'true_peak_ceiling':after['true_peak_dbtp']<=tp_max,'duration_exact':after['frames']==frames,'stereo_48k_24bit':after['channels']==2 and after['sample_rate']==48000 and after['bits']==24,'tail_quiet':float(np.max(np.abs(data[-2400:])))<.001,'midi_note_count':note_count==expected,'midi_no_stuck_notes':True,'dependency_hashes_verified':True}
    if mp3:checks['mp3_loudness_matches_master']=mp3['matches']
    if buses:checks['buses_and_returns_add_up_to_premix']=buses['adds_up_to_premix']
    if looped:checks.update(looped.pop('checks'))
    lap('sections_and_checks')
    passed,needs=delivered(checks,draft,tail_fails)
    report={'status':('DRAFT_PASS' if draft else 'TECHNICAL_PASS_AUDITION_PENDING') if passed else 'FAIL','title':p['title'],'version':p.get('version'),'draft':draft,'runtime_seconds':round(time.monotonic()-started,2),'stage_seconds':stages,'process_seconds':process_seconds(output/'logs'),'jobs':jobs,'project_sha256':project_key,'renderer_sha256':code_hash,'validation':validate(p),'checks':checks,'chain':chain_name,'premaster':before,'master':after,'sections':sections,'mastering':mastering,'buses':buses,'mp3':mp3,'cache_hits':sum(r['cache_hit'] for r in receipts),'stems_reused':sum(r['stem_reused'] for r in receipts),'stem_count':len(receipts),'direct_audio_listening_performed':False,'perceptual_quality':'Not certified by numeric checks; user audition pending','dependencies':{**{k:{x:v for x,v in cfg[k].items() if x!='path'} for k in ('fluidsynth','ffmpeg')},'soundfonts':{n:{x:v for x,v in f.items() if x!='path'} for n,f in used_fonts.items()}}}
    if draft:
        # The same audio as a full render; what only delivery needs is left out. Deliver a full render.
        report['left_out']=['master.flac']+(['the check that preview.mp3 decodes to the master\'s loudness'] if chain_name=='bus' else [])+(['loop.ogg and the loop layers'] if 'loop' in p else [])
        # A draft taken up in a full render's folder: that render's files of this kind are of an earlier master, in a
        # folder whose report now says they are left out.  They are the folder's own (the resume was let in on that),
        # so they go, and the report says which; a full render makes them again.
        if claim.get('earlier_delivery'):report['earlier_delivery_removed']=claim['earlier_delivery']
    if looped:report['loop']=looped
    chains={r['track']:r['surge_fx'] for r in receipts if r.get('surge_fx')}
    if chains:
        # Each part's Surge XT Effects chain, applied or not (also when its stem came from the cache): a part that plays
        # without its chain is said here and in the printed summary, never only in its receipt.
        report['surge_fx']={'applied':{k:v.get('level_change_db') for k,v in chains.items() if v['state']=='applied'},
                            'bypassed':{k:v['reason'] for k,v in chains.items() if v['state']!='applied'}}
        for r in receipts:
            # a headphone version whose chain did otherwise than its speaker stem's, either way (Astra's reviews b011a, b011c)
            hp=r.get('surge_fx_headphones')
            if hp and hp.get('state')=='applied':report['surge_fx']['applied'][r['track']+' (headphone version)']=hp.get('level_change_db')
            elif hp:report['surge_fx']['bypassed'][r['track']+' (headphone version)']=hp.get('reason')
        # the chains set to vary, each played once and kept with its part (0.11; Astra's review d011b)
        varying={k:v['varies'] for k,v in chains.items() if v.get('varies')}
        if varying:report['surge_fx']['varies']=varying
        own=[r['track'] for r in receipts if r.get('surge_fx_headphones_own_take')]
        if own:report['surge_fx']['headphones_own_take']=own
    top,last=peak_frames(data)
    # What holds a wide master's gain, named: one held chord set it for a whole piece and only a search of the master showed it (0.9.1).
    report['master']={**report['master'],'highest_sample':highest_sample(top,clock)}
    if not looped:report['silent_end_seconds'],report['clock_tail_seconds']=round((len(data)-1-last)/audio.RATE,2),clock.tail
    if not checks['tail_quiet']:
        # the master still sounds at its end: how loud, how fast it falls, and how much longer the tail would have to be
        report['tail']=tail_state(data)
        if needs:report['delivery_needs']=needs
    if heard:
        report['headphones']=heard
        # the headphone version's own FFmpeg runs (its parts before their places, its mix and master), in one figure
        report['process_seconds']['headphone version']=round(report['process_seconds'].pop('mp3_headphones',0)+sum(v for d in (output/'headphones'/'logs',output/'headphones'/'centre'/'logs') for v in process_seconds(d).values()),3)
    save_json(output/'report.json',report);claim['reported']=True
    if not passed:
        failed=[k for k,ok in checks.items() if not ok]
        advice={'tail_quiet':'the master still sounds in its last 50 ms (above -60 dBFS): give the note releases and the reverb more time with clock.tail_seconds'+(('; '+tail_advice(report['tail'])) if 'tail' in report else '')}
        raise ValueError('Delivery checks failed ('+', '.join(failed)+'); '+''.join(advice[k]+'; ' for k in failed if k in advice)+f'see {output/"report.json"}')
    return report

def process_stem(p,t,clock,cfg,output,raw,stem,frames,quiet=False,expected_fx=None,fx_take=None):
    """The part's raw synthesis to its processed stem: the gain to its level, filters, EQ, effects, compressor, width,
    pan or stage position and automation, then the production tools.  Returns what the receipt records of it.  With
    `quiet`, a part that barely sounds, or not at all, keeps its own level rather than stopping the render.
    `expected_fx`: what the stem's key said of its Surge XT Effects chain (`applied`, `bypassed`); a chain that does
    otherwise here is recorded with `cached` false, so the stem is not kept under that key.  `fx_take`: the part's cache
    entry, where a chain that is not exact keeps its output for the headphone version and later renders (surgefx.apply)."""
    amped=None
    if t['mix'].get('amp'):
        # The part's amplifier (musiclib/amp.py), on its dry synthesis before anything else: what leaves it is levelled
        # and mixed as a synthesis is.
        from . import amp
        x,_=audio.read_wav(raw);y,amp_facts=amp.apply(x,t,audio.soundfont_for(cfg,t)[1] if t['engine']=='soundfont' else None);del x
        amped=output/'stems'/f'.{t["id"]}.amp.wav';audio.write_wav(amped,y);del y;raw=amped
    try:return _process_stem(p,t,clock,cfg,output,raw,stem,frames,quiet,amp_facts if amped else None,expected_fx,fx_take)
    except BaseException as e:
        # What failed may still hold the amplifier's file open in a frame of its traceback (a memory map of it, read
        # for its level): Windows then refuses to remove the file.  The frames' variables are let go first.
        import traceback
        seen=e
        while seen is not None:
            if seen.__traceback__ is not None:traceback.clear_frames(seen.__traceback__)
            seen=seen.__context__
        raise
    finally:
        # the passes' own intermediate files (round a chorus: ".<part>.pass<k>.wav"), which a pass that fails leaves
        for left in (output/'stems').glob(f'.{t["id"]}.pass*.wav'):
            with contextlib.suppress(OSError):left.unlink()
        if amped is not None:
            with contextlib.suppress(OSError):amped.unlink()

def _process_stem(p,t,clock,cfg,output,raw,stem,frames,quiet,amp_facts,expected_fx=None,fx_take=None):
    try:
        ref=audio.reference_level(raw,t['mix'].get('level_mode','active_rms')) if t['notes'] else 0
    except ValueError as e:
        if str(e)!='Silent stem':raise
        if not quiet:
            raise ValueError(f'{t["id"]}: its synthesis is silent: check that its notes lie in its bank\'s keys (review '
                             '--config names any outside them), that its patch is in the bank, and that its notes are '
                             'long and loud enough to sound') from None
        ref=None
    gain=t['mix']['level_dbfs']-ref if t['notes'] and ref is not None else 0
    nearly_silent=ref is None
    if not -60<=gain<=45:
        if quiet and gain>45:
            gain,nearly_silent=0.0,True
        elif gain>45:
            raise ValueError(f'{t["id"]}: its synthesis is nearly silent ({ref:.1f} dBFS; reaching its level_dbfs would take '
                             f'{gain:+.1f} dB): check its bank and patch, and notes too short or soft for the sample to sound')
        else:
            raise ValueError(f'{t["id"]}: its synthesis is {ref:.1f} dBFS, {-gain:.1f} dB over its level_dbfs: check its bank, '
                             'patch and velocities')
    fx=t['mix'];co=fx.get('compressor')
    filters=[f'apad,atrim=end_sample={frames}',f'volume={gain:.9f}dB',f'highpass=f={fx.get("highpass",30)}',f'lowpass=f={fx.get("lowpass",18000)}']
    ng=fx.get('noise_gate')
    if ng is not None:
        # A gate by level (0.11), first among the processors, at the part's level; `{}` is the gate with its defaults.
        # Gates go before compressors and before delay and reverb (White, Sound On Sound, September 1997 and February
        # 2002): compression narrows the gap between the notes and the noise the gate tells apart.  FFmpeg's agate is a
        # downward expander: at its default ratio of 2 a held tone 8 dB under the threshold lost only 10.6 dB and one 20 dB
        # under it 34 dB, short of a -40 dB floor; at 10 they reach the floor (-39.8 and -41.3 dB), and a tone 2 dB under
        # the threshold loses 4.8 dB in its knee (measured, research/effects-0.11): a gate, as the field is named.
        filters.append(f'agate=threshold={10**(ng.get("threshold_db",-50)/20):.9f}:range={10**(ng.get("range_db",-40)/20):.9f}'
                       f':attack={ng.get("attack_ms",2)}:release={ng.get("release_ms",120)}:ratio=10')
    for band in fx.get('eq',[]):
        # A [Hz, dB] pair is a peak of width Q 1, as before; an object a peak, a shelf or a notch (0.11).
        if not isinstance(band,dict):f,g=band;filters.append(f'equalizer=f={f}:t=q:w=1:g={g}');continue
        q=band.get('q',1)
        if band['type']=='notch':filters.append(f'bandreject=f={band["hz"]}:t=q:w={q}')
        else:filters.append(f'{ {"peak":"equalizer","low_shelf":"lowshelf","high_shelf":"highshelf"}[band["type"]]}=f={band["hz"]}:t=q:w={q}:g={band["db"]}')
    for e in fx.get('effects',[]):
        # Modulation and lo-fi effects after the EQ: the chorus in NumPy (production.chorus; FFmpeg's chorus steps
        # its moving delay in whole samples, a buzz on sustained parts), FFmpeg's aphaser and acrusher.
        if e['type']=='chorus':filters.append(('chorus',e.get('depth',.5)))
        elif e['type']=='phaser':filters.append(f'aphaser=in_gain=0.8:out_gain=0.9:delay=3:decay={.2+.5*e.get("depth",.5):.3f}:speed={e.get("rate_hz",.5)}:type=t')
        elif e['type']=='bitcrush':filters.append(f'acrusher=bits={e.get("bits",8)}:samples={e.get("downsample",4)}:mix={e.get("mix",1)}:mode=lin')
        elif e['type']=='tremolo':filters.append(f'tremolo=f={e.get("rate_hz",5)}:d={e.get("depth",.5)}')
        # FFmpeg's flanger: its width is the share of the delayed signal mixed in (at 100 the dry half stays), regen its
        # feedback in percent; quadratic interpolation (0.11, measured smooth on a held tone).
        elif e['type']=='flanger':filters.append(f'flanger=delay={e.get("delay_ms",0)}:depth={e.get("depth_ms",2)}:regen={round(100*e.get("feedback",0),3)}'
                                                 f':width={round(100*e.get("mix",.71),3)}:speed={e.get("rate_hz",.5)}:interp=quadratic')
    if co:
        # 0.11's options, each only where written, so a compressor without them is the filter it was.
        extra=''.join([f':knee={10**(co["knee_db"]/20):.9f}' if 'knee_db' in co else '',f':mix={co["mix"]}' if 'mix' in co else '',
                       f':detection={co["detection"]}' if 'detection' in co else ''])
        filters.append(f'acompressor=threshold={10**(co["threshold_db"]/20):.9f}:ratio={co["ratio"]}:attack={co["attack_ms"]}:release={co["release_ms"]}'
                       f':makeup={10**(co.get("makeup_db",0)/20):.9f}{extra}' if ('makeup_db' in co or extra) else
                       f'acompressor=threshold={10**(co["threshold_db"]/20):.9f}:ratio={co["ratio"]}:attack={co["attack_ms"]}:release={co["release_ms"]}:makeup=1')
    bypass=None
    if fx.get('surge_fx'):
        # Surge XT Effects, before width and the static pan (musiclib.surgefx).  Where the plugin cannot run here the
        # chain is left out of the chain of filters altogether, so the part renders as it would without the field (a split
        # pass round a chain that does nothing changed a master by one 24-bit count: Astra's review b011a).
        try:surgefx.locate(cfg);filters.append(('surge_fx',))
        except surgefx.Unavailable as e:bypass={'state':'bypassed','reason':str(e)}
    pan=fx.get('pan',0);width=fx.get('width',1)
    if width<1:
        # Mid/side width before the pan: spaced-microphone samples (some piano and room recordings) are nearly
        # uncorrelated left/right, which leaves a lead diffuse and off-centre and partly cancels in mono.
        a,b=(1+width)/2,(1-width)/2
        filters.append(f'pan=stereo|c0={a:.9f}*c0+{b:.9f}*c1|c1={b:.9f}*c0+{a:.9f}*c1')
    depth=fx.get('depth_m');moving=fx.get('move')
    # A part placed on the stage gets its pan with its early reflections (musiclib/stage.py), after the chain; a part
    # that moves gets its place sample by sample (musiclib/move.py), there too.
    if depth is None and not moving:filters.append(f'pan=stereo|c0={math.sqrt(1-pan):.9f}*c0|c1={math.sqrt(1+pan):.9f}*c1')
    filters.append(f'apad,atrim=end_sample={frames}')  # a chorus or phaser delays the signal and would lengthen the stem
    # One FFmpeg pass, or, around each chorus, a pass up to it, the chorus in NumPy on that file, and on. A later
    # pass's log takes ".pass{k}": a part id cannot hold a dot, so the label never names another part's log.
    surge_fx=bypass
    def through(fs):
        """The filters `fs` from the raw take to the stem: FFmpeg's passes, the chorus and the Surge XT Effects chain;
        returns those that ran.  A chain that cannot run after all (its host failed, or the plugin went after it was found)
        is taken out and the part made again from its raw take, so that it is to the sample what it would be without the
        field, as where the plugin was missing from the start (a split pass moved a master by a 24-bit count: Astra's review
        b011c).  A run that failed with the plugin in place is not kept (`cached` false): the next render tries again."""
        nonlocal surge_fx
        src,run,k=raw,[],0
        for f in fs+[None]:
            if isinstance(f,str):run.append(f);continue
            if run:
                out=stem if f is None else output/'stems'/f'.{t["id"]}.pass{k}.wav'
                audio.ffmpeg(cfg,['-i',src,'-af',','.join(run),'-ar',str(audio.RATE),'-c:a','pcm_f32le',out],output/'logs','process_'+t['id']+(f'.pass{k}' if k else ''))
                if src!=raw:src.unlink()
                src,run,k=out,[],k+1
            if f is None:break
            if f[0]=='surge_fx':
                try:surge_fx={'state':'applied',**surgefx.apply(src,src,t,cfg,output/'stems',output/'logs',keep=fx_take)}
                except surgefx.Unavailable as e:   # (Failed is one: it found the plugin, and the run failed)
                    surge_fx={'state':'bypassed','reason':str(e),**({'cached':False} if isinstance(e,surgefx.Failed) else {})}
                    if src!=raw:src.unlink()
                    return through([g for g in fs if g is not f])
                continue
            x,_=audio.read_wav(src);x,_=production.chorus(x,f[1]);audio.write_wav(src,x)
        return fs
    ran=through(filters)
    done={'reference_level_dbfs':ref,'gain_db':gain,'filter_chain':','.join(f if isinstance(f,str) else 'surge_fx' if f[0]=='surge_fx' else f'chorus(depth={f[1]}, production.chorus)' for f in ran)}
    if surge_fx:
        if expected_fx and surge_fx['state']!=expected_fx:surge_fx['cached']=False   # the plugin came or went during the render
        done['surge_fx']=surge_fx
    if nearly_silent:done['nearly_silent']=True
    if amp_facts:done['amp']=amp_facts
    points=fx.get('automation',[])
    ride=any(v for _,v in points)
    if ride or depth is not None or moving or production.wanted(t):
        # In NumPy on the stem read once: the automation (where the FFmpeg chain had it, after the pan), the movement
        # or the stage position, then the sweeps, saturation, gates, tempo-synced delays and ducking
        # (musiclib/production.py).
        x,_=audio.read_wav(stem)
        if ride:
            x=audio.automated(x,points,clock);done['automation_points']=len(points)
        if moving:
            from . import move
            x,done['move']=move.apply(x,moving,pan,clock)
        if depth is not None:
            x,placed=stage.place(x,pan,depth,fx.get('facing','front'))
            if placed:done['stage']={'depth_m':depth,'facing':fx.get('facing','front'),**placed}
        if production.wanted(t):
            x,produced=production.process(x,p,t,clock)
            if produced:done['production']=produced
        audio.write_wav(stem,x)
    return done

def room_mix(p,clock,cfg,output,frames,duration):
    """The original chain (mix.chain "room"): every stem dry, one shared noise room, a delay send and a limiter."""
    from .mixbus import DELAY_BAND,delay_times
    ir=output/'returns'/'room_ir.wav';audio.room_ir(ir,p['mix'].get('room_seconds',1.1))
    args=[];graph=[];dry=[];room=[];delay=[]
    for i,t in enumerate(p['tracks']):
        fx=t['mix'];args.extend(['-i',output/'stems'/(t['id']+'.wav')]);branches=[f'[d{i}]'];dry.append(branches[0])
        if fx.get('reverb_db') is not None:branches.append(f'[ri{i}]')
        if fx.get('delay_db') is not None:branches.append(f'[di{i}]')
        graph.append(f'[{i}:a]asplit={len(branches)}'+''.join(branches))
        if fx.get('reverb_db') is not None:
            graph.append(f'[ri{i}]volume={fx["reverb_db"]}dB[r{i}]');room.append(f'[r{i}]')
        if fx.get('delay_db') is not None:
            graph.append(f'[di{i}]highpass=f={DELAY_BAND[0]},lowpass=f={DELAY_BAND[1]},adelay={delay_times(clock,fx)},volume={fx["delay_db"]}dB[e{i}]');delay.append(f'[e{i}]')
    buses=dry[:];exports=[]
    if room:
        args.extend(['-i',ir])
        graph.append(''.join(room)+f'amix=inputs={len(room)}:normalize=0[room_send]')
        graph.append(f'[room_send][{len(p["tracks"])}:a]afir={audio.afir_options(cfg)},apad,atrim=end_sample={frames},asplit=2[room][room_export]')
        buses.append('[room]');exports.append(('room_export','room_return.wav'))
    if delay:
        graph.append(''.join(delay)+f'amix=inputs={len(delay)}:normalize=0,apad,atrim=end_sample={frames},asplit=2[delay][delay_export]')
        buses.append('[delay]');exports.append(('delay_export','delay_return.wav'))
    from .loop import starts_at_zero
    fade='' if starts_at_zero(p) else ',afade=t=in:st=0:d=0.005'
    # Every input of the last mix is padded by a second before it is added, and the sum cut to the piece's length.
    # A return comes out of its convolution a block late; where the parts end with it, FFmpeg 6's amix lets go of the
    # parts' last block when they end first (measured on Ubuntu 24.04's FFmpeg 6.1: the mix's last 50 ms held the
    # return alone, 13 dB lower than with FFmpeg 7 and newer; stem, return and every quarter second before it the
    # same).  Padded, what it lets go of is silence past the cut.
    padded=[f'[last{i}]' for i in range(len(buses))]
    graph+=[f'{b}apad=pad_dur=1{q}' for b,q in zip(buses,padded)]
    graph.append(''.join(padded)+f'amix=inputs={len(buses)}:normalize=0:duration=longest,atrim=end_sample={frames}{fade},afade=t=out:st={duration-1.7:.8f}:d=1.7[mix]')
    graph_options=audio.graph_file(cfg,output/'mix.filtergraph.txt',';\n'.join(graph))
    premaster=output/'premaster.wav'
    outs=['-map','[mix]','-ar',str(audio.RATE),'-c:a','pcm_f32le',premaster]
    for label,name in exports:outs+=['-map',f'[{label}]','-ar',str(audio.RATE),'-c:a','pcm_f32le',output/'returns'/name]
    audio.ffmpeg(cfg,[*args,*graph_options,*outs],output/'logs','mix')
    before=audio.measure(cfg,premaster,output/'logs','measure_premaster')
    # The limiter's default ceiling sits 0.6 dB under the true-peak ceiling (mixbus.true_peak_ceiling): -1.6 dBFS, or
    # -2.6 for a master louder than -14 LUFS.
    from .mixbus import true_peak_ceiling
    target=p['mix'].get('target_lufs',-16);tp_max=true_peak_ceiling(target)
    ceiling=p['mix'].get('peak_ceiling_db',tp_max-.6);allowance=p['mix'].get('max_limit_db',1.5)
    gain=min(target-before['integrated_lufs'],ceiling-before['true_peak_dbtp']+allowance)
    chain=f'volume={gain:.9f}dB,aresample=192000,alimiter=limit={10**(ceiling/20):.9f}:attack=5:release=110:level=false:latency=true,aresample=48000,apad,atrim=end_sample={frames}'
    audio.ffmpeg(cfg,['-i',premaster,'-af',chain,'-c:a','pcm_s24le',output/'master.wav'],output/'logs','master')
    return before,{'chain':'room','gain_db':gain,'ceiling_db':ceiling,'true_peak_ceiling_dbtp':tp_max,'max_input_peak_above_ceiling_db':max(0,before['true_peak_dbtp']+gain-ceiling),'limiter_chain':chain}
