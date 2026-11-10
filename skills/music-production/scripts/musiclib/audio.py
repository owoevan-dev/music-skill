"""Local headless processes, narrow WAV I/O, instruments and audio measurements."""
import contextlib
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import threading
import time
import numpy as np
from . import files
from .model import Clock, performed, save_json, file_hash
from .model import bend_curve as wheel_curve

RATE=48000
# The longest WAV read: a project's 30 minutes (validate) and its tail of up to 15 s, with room to spare.
MAX_WAV_SECONDS=1860

TOOLS = ('fluidsynth', 'ffmpeg', 'soundfont')  # what every configuration names, as bootstrap.py writes it


def config_shape(config, where, needs=TOOLS):
    """A configuration's shape, checked before any of it is read: a JSON object; the entries `needs` names present;
    each of fluidsynth, ffmpeg, soundfont, surge and pedalboard it holds an object with a text `path`; `soundfonts`, if
    there, an object of named banks, each an object with a text `path`.  Anything else is refused naming the field: a
    null path, a list of banks or a missing tool stopped the command with a traceback (found by GPT Pro's sixth review
    of 0.4.0)."""
    if not isinstance(config, dict):
        raise ValueError(f'{where}: a configuration is a JSON object, not {type(config).__name__}')
    for key in needs:
        if key not in config:
            raise ValueError(f'{where}: the configuration needs "{key}"; bootstrap.py writes one')
    for key in ('fluidsynth', 'ffmpeg', 'soundfont', 'surge', 'pedalboard'):
        if key in config and not (isinstance(config[key], dict) and isinstance(config[key].get('path'), str) and config[key]['path']):
            raise ValueError(f'{where}: "{key}" in the configuration is an object with a text "path"')
    banks = config.get('soundfonts', {})
    if not isinstance(banks, dict):
        raise ValueError(f'{where}: "soundfonts" in the configuration maps names to banks (an object), not {type(banks).__name__}')
    for name, entry in banks.items():
        if not (isinstance(entry, dict) and isinstance(entry.get('path'), str) and entry['path']):
            raise ValueError(f'{where}: soundfonts.{name} in the configuration is an object with a text "path"')
    return config


def absolute_paths(config, base, where=None):
    """The configuration with every relative path made absolute against `base` (the folder of the file it was read
    from), so it can be written anywhere; its shape is checked first (config_shape, with no tool required)."""
    config_shape(config, where or base, needs=())
    entries = [config[k] for k in ('fluidsynth', 'ffmpeg', 'soundfont', 'surge', 'pedalboard') if isinstance(config.get(k), dict)]
    entries += [v for v in config.get('soundfonts', {}).values() if isinstance(v, dict)]
    for entry in entries:
        for key in ('path', 'binary', 'patches'):
            if isinstance(entry.get(key), str) and not Path(entry[key]).is_absolute():
                entry[key] = str((Path(base) / entry[key]).resolve())
    return config

VERIFIED={}  # path -> (sha256, size, modification time) of each named bank this process has hashed

def _stamp(p):
    """A file's size and modification time: both change when the file is rewritten, so a bank hashed once is hashed
    again once either has changed."""
    s=os.stat(p);return (s.st_size,s.st_mtime_ns)

def _verified(path,sha):
    try:return VERIFIED.get(str(path))==(sha,_stamp(path))
    except OSError:return False

def _verify(key,entry,p):
    # A system package update replaces the executable: the configuration then names a file that is gone or changed.
    again=' Run bootstrap.py again (and fetch_soundbanks.py for the banks) to write a new configuration.'
    if not p.is_file():raise ValueError(f'Missing dependency: {key}: {p}.'+again)
    if not entry.get('sha256') or file_hash(p)!=entry['sha256']:raise ValueError(f'Dependency hash mismatch: {key}: {p} changed since the configuration was written.'+again)

def verify_tool(config,key):
    """The executable a configuration names under `key` is the file its hash names, as load_config holds every one a
    render runs: for a command that runs one tool only and reads the configuration itself (fetch_soundbanks.py, whose
    builds ran the configured FFmpeg unverified; GPT's security audit of 0.5, S01)."""
    _verify(key,config[key],Path(config[key]['path']))

def load_config(path,all_banks=False):
    """Verify the configured executables and the default SoundFont by path and SHA-256. `soundfont` is the default
    bank; optional `soundfonts` adds named banks that tracks select with `soundfont`.  A named bank is found at load and
    hashed the first time a part uses it (soundfont_for), or at once with `all_banks` (doctor): a full set is about 8 GB,
    and hashing it all took a render's first five seconds for the few banks one piece plays."""
    # Read by the name given, bounded and never through a link (found by GPT Pro's fourth review), and only then
    # resolved, for the folder its relative entries start from: resolved first, a link had become its target and
    # passed the reader's check (found by GPT Pro's fifth review of 0.4.0).
    data=files.read_json(os.path.abspath(path))
    path=Path(path).resolve()
    config_shape(data,path)
    extra=data.get('soundfonts',{})
    if 'default' in extra or not all(re.fullmatch(r'[a-z][a-z0-9_]{0,47}',k) for k in extra):
        raise ValueError('soundfonts must map lower-case names (not "default") to entries')
    for key,entry in [(k,data[k]) for k in ('fluidsynth','ffmpeg','soundfont')]+[('soundfonts.'+k,v) for k,v in extra.items()]:
        p=Path(entry['path'])
        if not p.is_absolute():p=path.parent/p
        p=p.resolve()
        if key.startswith('soundfonts.') and not all_banks:
            if not p.is_file():_verify(key,entry,p)
        else:
            _verify(key,entry,p)
            if key.startswith('soundfonts.'):VERIFIED[str(p)]=(entry['sha256'],_stamp(p))
        entry['path']=str(p)
    return data

def soundfont_for(config,track):
    name=track.get('soundfont','default')
    if name=='default':return name,config['soundfont']
    if name not in config.get('soundfonts',{}):
        lock=Path(__file__).resolve().parents[2]/'references'/'soundbank-lock.json'
        known={i['name'] for k in ('archives','builds') for i in json.loads(lock.read_text(encoding='utf-8'))[k]} if lock.is_file() else set()
        hint=(f' It is one of the optional banks: install it with fetch_soundbanks.py --only {name} (references/setup.md), then pass the configuration it writes.'
              if name in known else ' Configure it with studio.py add-soundfont, or choose a configured bank (studio.py doctor lists them).')
        raise ValueError(f'{track["id"]}: SoundFont "{name}" is not configured.'+hint)
    entry=config['soundfonts'][name]
    if not _verified(entry['path'],entry.get('sha256')):
        p=Path(entry['path']);_verify('soundfonts.'+name,entry,p);VERIFIED[str(p)]=(entry['sha256'],_stamp(p))
    return name,entry

class Cancelled(Exception):
    """The run a program belonged to stopped (another part of the render failed), and the program was stopped too."""

_scope=threading.local()

@contextlib.contextmanager
def cancel_scope(event):
    """Programs this thread starts with run() stop once `event` is set: a render's other parts, when one has failed
    (they ran on, and the parts still waiting started, until each finished; found by GPT Pro's third review)."""
    before=getattr(_scope,'event',None);_scope.event=event
    try:yield
    finally:_scope.event=before

def check_cancel(what):
    """Stop here (Cancelled) if this thread's run was stopped (cancel_scope): before a program starts, after a wait for
    memory or a cache entry, between a part's stages.  A part that waited went on to synthesize once let in, and a
    program started after the stop ran to its end (found by GPT Pro's fourth review of 0.4.0)."""
    event=getattr(_scope,'event',None)
    if event is not None and event.is_set():raise Cancelled(f'{what} stopped: another part failed')

def run(argv,folder,label,timeout=600,cwd=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    log=folder/(label+'.log');started=time.monotonic()
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    cancel=getattr(_scope,'event',None)
    check_cancel(label)  # a run already stopped starts no program (one that ended within 0.2 s ran to its end)
    temp=None;ran=False
    # A file already at the log's name that cannot be written stays, as when the log was opened there: the run stops
    # before its program starts (a read-only file of someone else's would otherwise be swapped out on POSIX).
    if files.occupied(log) and (not files.regular_file(log) or not os.access(log,os.W_OK)):
        raise PermissionError(errno.EACCES,'the log cannot be written there',str(log))
    try:
        # The program writes its log under a new name of its own (files.new_file, named in a journaled folder's journal
        # before it is made), which takes the log's name once the program has ended, however it ended: a run killed
        # while the program wrote leaves a file the journal proves the run's, never a log half written under its name.
        fd,temp=files.new_file(log,'.log')
        with os.fdopen(fd,'wb') as out:
            proc=subprocess.Popen([str(x) for x in argv],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,creationflags=flags,cwd=cwd)
            try:
                deadline=started+timeout
                while True:
                    try:code=proc.wait(timeout=.2 if cancel is not None else max(.01,deadline-time.monotonic()));break
                    except subprocess.TimeoutExpired:
                        if time.monotonic()>=deadline:raise TimeoutError(f'{label} exceeded {timeout}s; log: {log}') from None
                        if cancel is not None and cancel.is_set():raise Cancelled(f'{label} stopped: another part failed') from None
            except BaseException:
                # Stopped from outside (Ctrl+C, a failure elsewhere): the program it started stops too, and is waited for,
                # so nothing it writes outlives the run.
                proc.kill()
                with contextlib.suppress(Exception):proc.wait(timeout=10)
                raise
        ran=True
    finally:
        # The log takes its name, noted as the run's (files.replace), whatever stopped the program: a failed program's
        # log is read to report it.  Only this run's own new file ever takes it, so a file at that name the run did not
        # write is never taken for the run's (GPT Pro's sixth review of 0.4.0, from the code).
        if temp is not None:
            try:files.replace(temp,log)
            except OSError:
                with contextlib.suppress(OSError):os.unlink(temp)
                if ran:raise
    receipt={'argv':[str(x) for x in argv],'returncode':code,'seconds':round(time.monotonic()-started,3),'pid':proc.pid,'launch_mode':'CREATE_NO_WINDOW' if flags else 'no stdin; no GUI arguments','log':str(log)}
    save_json(folder/(label+'.process.json'),receipt)
    content=log.read_text(encoding='utf-8',errors='replace')
    if code:raise RuntimeError(f'{label} failed ({code}): {content[-3000:]}')
    return content

def written_whole(run_it,outputs):
    """Run `run_it(names)` with each output file of `outputs` given as a new file of its own beside it, with the same
    extension (a program picks the format from it); each takes its output's place only when the run succeeds, and all
    are removed when it fails, so a stopped or failed program never leaves half a file under the output's name.  A
    null sink (os.devnull, -) is passed through."""
    named=[]
    try:
        for o in outputs:named.append(o if str(o) in (os.devnull,'-') else files.stage_name(o,Path(o).suffix))
        result=run_it(named)
        for o,n in zip(outputs,named):
            if n is not o:files.replace(n,o)
        return result
    finally:
        for o,n in zip(outputs,named):
            if n is not o:
                with contextlib.suppress(OSError):os.unlink(n)

def fluidsynth(config,font_path,midi_path,wav_path,folder,label='fluidsynth'):
    """Render a MIDI file on one SoundFont: dry (no chorus or reverb), 48 kHz float, sample-accurate timing.  A run
    whose log reports a problem publishes nothing (written_whole)."""
    def run_it(names):
        log=run([config['fluidsynth']['path'],'-n','-i','-C','0','-R','0','-g','.55','-r',str(RATE),'-T','wav','-O','float','-o','synth.cpu-cores=1','-o','synth.polyphony=256','-o','synth.midi-bank-select=mma','-o','player.timing-source=sample','-F',names[0],font_path,midi_path],folder,label)
        # Only FluidSynth's own messages ("fluidsynth: error: ...", a preset "not found"), not paths it echoes.
        problems=[line for line in log.splitlines() if line.lower().startswith('fluidsynth:') and any(w in line.lower() for w in ('error','panic','failed','not found'))]
        if problems:raise ValueError('Instrument rendering diagnostic: '+'\n'.join(problems)[-2000:])
        return log
    return written_whole(run_it,[wav_path])

def ffmpeg(config,args,folder,label):
    """Run FFmpeg on the skill's own WAVs.  Every option the scripts pass takes one value, so any other argument is an
    output file; each output gets no metadata or chapters from its inputs (-map_metadata -1, -map_chapters -1), only
    the tags a script sets itself: FFmpeg copies an input's global metadata by default (FFmpeg documentation,
    -map_metadata), and a tag written into a cached WAV would otherwise reach every master, MP3 and FLAC made from it.
    Each output is written whole (written_whole)."""
    guarded=[];i=0;outputs=[];slots=[]
    while i<len(args):
        if args[i]=='-i':
            p=Path(args[i+1]).resolve()
            if not p.is_file() or p.suffix.lower()!='.wav':raise ValueError('Audio inputs must be local generated WAVs')
            with p.open('rb') as f:header=f.read(12)
            if header[:4]!=b'RIFF' or header[8:12]!=b'WAVE':raise ValueError('Not RIFF/WAVE')
            guarded.extend(['-protocol_whitelist','file,pipe','-f','wav','-i',p]);i+=2
        elif str(args[i]).startswith('-') and str(args[i])!='-':
            if i+1>=len(args):raise ValueError(f'FFmpeg option {args[i]} has no value')
            guarded.extend(args[i:i+2]);i+=2
        else:
            guarded.extend(['-map_metadata','-1','-map_chapters','-1',args[i]]);slots.append(len(guarded)-1);outputs.append(args[i]);i+=1
    def run_it(names):
        argv=list(guarded)
        for slot,name in zip(slots,names):argv[slot]=name
        return run([config['ffmpeg']['path'],'-hide_banner','-nostdin','-y','-threads','1','-filter_threads','1','-filter_complex_threads','1',*argv],folder,label)
    return written_whole(run_it,outputs)

_GRAPH={}
def graph_file(config,path,text):
    """Write the filtergraph `text` to `path` and return the FFmpeg options that read it from there: a mix's graph
    grows with its parts, and on the command line it would take the 32,767 characters a Windows command line holds.
    FFmpeg 7 and newer read an option's value from a file as -/filter_complex; FFmpeg 6 has only -filter_complex_script,
    which FFmpeg 9.0.2 no longer accepts (we tried).  The version is asked once per executable."""
    exe=config['ffmpeg']['path']
    if exe not in _GRAPH:
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        out=subprocess.run([exe,'-hide_banner','-version'],capture_output=True,text=True,errors='replace',stdin=subprocess.DEVNULL,creationflags=flags,timeout=30)
        m=re.search(r'version\s+n?(\d+)\.',out.stdout)
        _GRAPH[exe]='-filter_complex_script' if m and int(m.group(1))<7 else '-/filter_complex'
    with files.staged(path) as f:f.write(text.encode('utf-8'))
    return [_GRAPH[exe],str(Path(path).resolve())]

_AFIR={}
def afir_options(config):
    """Options for convolving with an impulse response used as it is.  FFmpeg 7 and newer spell "no normalization"
    irnorm=-1; FFmpeg 6 spells it gtype=none.  Asked once per executable from its own filter help."""
    path=config['ffmpeg']['path']
    if path not in _AFIR:
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        out=subprocess.run([path,'-hide_banner','-h','filter=afir'],capture_output=True,text=True,errors='replace',stdin=subprocess.DEVNULL,creationflags=flags,timeout=30)
        text=out.stdout+out.stderr
        _AFIR[path]=':'.join(['dry=1','wet=1','irnorm=-1' if 'irnorm' in text else 'gtype=none']+(['precision=double'] if 'precision' in text else []))
    return _AFIR[path]

def write_wav(path,data,rate=RATE):
    data=np.asarray(data,dtype='<f4')
    if data.ndim==1:data=data[:,None]
    if not np.isfinite(data).all():raise ValueError('Nonfinite audio')
    channels=data.shape[1];raw=data.tobytes()
    fmt=struct.pack('<HHIIHH',3,channels,rate,rate*channels*4,channels*4,32)
    with files.staged(path) as f:  # whole or not at all: a failed write leaves the file that was there
        f.write(b'RIFF'+struct.pack('<I',36+len(raw))+b'WAVEfmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',len(raw))+raw)

def read_wav(path):
    path=Path(path)
    with path.open('rb') as f:
        h=f.read(12)
        if h[:4]!=b'RIFF' or h[8:12]!=b'WAVE':raise ValueError('Only RIFF WAV supported')
        fmt=None;payload=None
        while True:
            header=f.read(8)
            if not header:break
            if len(header)!=8:raise ValueError('Truncated WAV chunk')
            name,size=struct.unpack('<4sI',header)
            if size>path.stat().st_size:raise ValueError('Invalid WAV chunk size')
            if name==b'fmt ':
                if size>1024:raise ValueError('Invalid WAV format chunk')  # 16 to 40 bytes in practice
                fmt=f.read(size)
            elif name==b'data':payload=(f.tell(),size);f.seek(size,1)
            else:f.seek(size,1)
            if size%2:f.seek(1,1)
    if fmt is None or payload is None:raise ValueError('Missing WAV format/data')
    # A format chunk holds 16 bytes at least, and a frame is its channels times its sample's bytes (the WAVE format's
    # nBlockAlign, as wavfile.info holds it): a shorter chunk stopped the reader with struct.error, a frame size of 0
    # with ZeroDivisionError, and another frame size than the samples have made the length limit below count other
    # frames than the ones then read (GPT's security audit of 0.5, L04).
    if len(fmt)<16:raise ValueError('Short WAV format chunk')
    tag,channels,rate,_,align,bits=struct.unpack_from('<HHIIHH',fmt)
    if tag==65534:
        if len(fmt)<40:raise ValueError('Short extensible WAV')
        tag=struct.unpack_from('<H',fmt,24)[0]
    if channels not in (1,2) or rate!=RATE or not align or align!=channels*bits//8 or payload[1]%align:raise ValueError('Unsupported WAV dimensions')
    offset,size=payload
    if size//align>MAX_WAV_SECONDS*RATE:
        # Nothing the tools write is longer than a render, so a longer file (a reference, a render folder from
        # elsewhere) is refused before it is read: analysis and comparison hold several float64 copies of what they read.
        raise ValueError(f'{path.name}: {size//align/RATE/60:.1f} minutes, longer than a render can be ({MAX_WAV_SECONDS//60} minutes)')
    if tag==3 and bits==32:
        data=np.memmap(path,dtype='<f4',mode='r',offset=offset,shape=(size//4//channels,channels))
    elif tag==1 and bits==24:
        b=np.memmap(path,dtype='u1',mode='r',offset=offset,shape=(size//3,3))
        ints=b[:,0].astype(np.int32)|(b[:,1].astype(np.int32)<<8)|(b[:,2].astype(np.int32)<<16)
        ints=(ints^0x800000)-0x800000
        data=(ints.astype(np.float32)/8388608).reshape(-1,channels)
    elif tag==1 and bits==16:
        data=np.memmap(path,dtype='<i2',mode='r',offset=offset,shape=(size//2//channels,channels)).astype(np.float32)/32768
    else:raise ValueError(f'Unsupported WAV encoding {tag}/{bits}')
    return data,{'frames':len(data),'sample_rate':rate,'channels':channels,'bits':bits,'format':tag,'seconds':len(data)/rate}

def audio_hash(path):
    """SHA-256 of a WAV's format and data chunks only: the same audio gives the same hash whatever else the writer
    stored (FluidSynth's PEAK chunk records the time it wrote the file)."""
    h=hashlib.sha256();found=set()
    with Path(path).open('rb') as f:
        head=f.read(12)
        if head[:4]!=b'RIFF' or head[8:12]!=b'WAVE':raise ValueError('Only RIFF WAV supported')
        while True:
            header=f.read(8)
            if len(header)<8:break
            name,size=struct.unpack('<4sI',header)
            if name in (b'fmt ',b'data'):
                h.update(name+header[4:]);left=size;found.add(name)
                while left:
                    block=f.read(min(left,1<<20))
                    if not block:raise ValueError('Truncated WAV chunk')
                    h.update(block);left-=len(block)
            else:f.seek(size,1)
            if size%2:f.seek(1,1)
    if found!={b'fmt ',b'data'}:raise ValueError('Missing WAV format/data')
    return h.hexdigest()

def rms(data):return float(np.sqrt(np.mean(np.asarray(data,dtype=np.float64)**2)))

def reference_level(path,mode='active_rms'):
    a,_=read_wav(path)
    if not np.isfinite(a).all():raise ValueError('Nonfinite stem')
    peak=float(np.max(np.abs(a)))
    if peak<1e-9:raise ValueError('Silent stem')
    if mode=='peak':return 20*math.log10(peak)
    blocks=[rms(a[i:i+RATE//2]) for i in range(0,len(a),RATE//2)]
    active=[x for x in blocks if x>max(1e-6,peak*.01)]
    return 20*math.log10(float(np.percentile(active,70)))

def measure(config,path,logs,label):
    log=ffmpeg(config,['-i',path,'-af','loudnorm=I=-16:TP=-1.6:LRA=20:print_format=json','-f','null',os.devnull],logs,label)
    matches=re.findall(r'\{\s*"input_i"[\s\S]*?\}',log)
    if not matches:raise ValueError('No loudness measurement')
    values=json.loads(matches[-1]);a,info=read_wav(path)
    if not np.isfinite(a).all():raise ValueError('Nonfinite master')
    info.update(integrated_lufs=float(values['input_i']),true_peak_dbtp=float(values['input_tp']),lra_lu=float(values['input_lra']),sample_peak_dbfs=20*math.log10(max(1e-15,float(np.max(np.abs(a))))),clipped_samples=int(np.count_nonzero(np.abs(a)>=1)),rms=rms(a),sha256=file_hash(path),meter='FFmpeg loudnorm input analysis; BS.1770/EBU R128')
    if not all(math.isfinite(info[x]) for x in ('integrated_lufs','true_peak_dbtp','lra_lu')):raise ValueError('Silent/invalid loudness input')
    return info

AUTOMATION_BLOCK=1<<16  # samples whose gain is computed at once: the song's whole gain curve is never held in memory

def automated(x,points,clock):
    """The stem `x` (frames × channels) under its part's `automation`, as a new array, or None where the automation
    leaves it as it is (no points, or 0 dB at every point).  The level runs linearly in dB and in time from point to
    point; before the first point it is the first point's, after the last the last one's (as excerpt.py reads it).
    Sample by sample in NumPy: an FFmpeg expression nests one condition per point, which fails past about 96 points
    and puts every point on the command line."""
    db=np.array([v for _,v in points],dtype=np.float64)
    if not db.any():return None
    at=np.array([clock.seconds(b)*RATE for b,_ in points],dtype=np.float64)
    out=np.empty(x.shape,dtype=np.float32)
    for i in range(0,len(x),AUTOMATION_BLOCK):
        n=np.arange(i,min(i+AUTOMATION_BLOCK,len(x)),dtype=np.float64)
        out[i:i+len(n)]=x[i:i+len(n)]*np.power(10.0,np.interp(n,at,db)/20).astype(np.float32)[:,None]
    return out

def beats_at(clock,times):
    """clock.beat for an array of seconds: the position in beats each time falls on."""
    ts=np.asarray(clock.times);i=np.clip(np.searchsorted(ts,times,side='right')-1,0,None)
    return np.asarray(clock.beats)[i]+(np.asarray(times,dtype=np.float64)-ts[i])/np.asarray(clock.spb)[i]

def control(track,cc,times,clock,default):
    """A controller's value at `times` (seconds) as the exported MIDI plays the part's [beat, controller, value] points
    (model.cc_events): linear in beats from point to point, or held in step mode; `default` before the first point.
    In beats, not seconds, so a ramp under a tempo change reaches the value the MIDI file gives that beat."""
    points=sorted((b,v) for b,c,v in track['performance'].get('cc',[]) if c==cc)
    if not points:return np.full(len(times),default,dtype=np.float32)
    xs=np.array([x[0] for x in points],dtype=np.float64);ys=np.array([x[1] for x in points],dtype=np.float64);beats=beats_at(clock,times)
    if track['performance'].get('cc_mode','linear')=='step':
        idx=np.searchsorted(xs,beats,side='right')-1
        return np.where(idx>=0,ys[np.clip(idx,0,None)],default)
    return np.interp(beats,xs,ys,left=default)

def bend_curve(track,times,clock):
    """Pitch bend in semitones at `times` (seconds), as the exported MIDI plays the part's [beat, semitones] points
    (model.bend_curve, curve_at): zero until the first point, which it may jump to, then linear in beats between
    points; zero without any."""
    pts=wheel_curve(track['performance'].get('bend',[]))
    if not pts:return np.zeros(len(times))
    return np.interp(beats_at(clock,times),[b for b,_ in pts],[v for _,v in pts])

def synthesize(project,track,path):
    clock=Clock(project);frames=round((clock.end+clock.tail)*RATE)
    out=np.zeros((frames,2),dtype=np.float32)
    cfg=track.get('instrument',{})
    notes=performed(track,clock);prior_end=-1;prior_pitch=69;phase_end=0.0
    for ni,n in enumerate(notes):
        start=round(n['start_seconds']*RATE);stop=round(n['end_seconds']*RATE)
        release=round(cfg.get('release_ms',120)/1000*RATE)
        end=min(frames,stop+release);count=end-start
        if count<1:continue
        t=np.arange(count,dtype=np.float64)/RATE
        connected=n['start_seconds']<=prior_end+.012
        pitch=np.full(count,float(n['pitch']))
        glide=min(count,round(cfg.get('glide_ms',28)/1000*RATE)) if connected else 0
        if glide:pitch[:glide]=np.linspace(prior_pitch,n['pitch'],glide)
        pitch+=bend_curve(track,t+n['start_seconds'],clock)
        expr=control(track,11,t+n['start_seconds'],clock,100)/127
        brightness=control(track,74,t+n['start_seconds'],clock,66)
        vib=control(track,1,t+n['start_seconds'],clock,32)
        # Default depth .015+CC1*.001 semitones, unless the instrument sets a CC1=127 depth in cents.
        depth=cfg['vibrato_depth_cents']/100*vib/127 if 'vibrato_depth_cents' in cfg else .015+vib*.001
        pitch+=depth*np.clip((t-cfg.get('vibrato_delay_ms',180)/1000)/.25,0,1)*np.sin(2*math.pi*cfg.get('vibrato_rate_hz',5.1)*t)
        f=440*np.exp2((pitch-69)/12)
        phase=phase_end+2*math.pi*np.cumsum(f)/RATE
        gate=max(1,min(count,stop-start))
        env=np.ones(count,dtype=np.float64)
        attack=min(gate,round((.008 if connected else cfg.get('attack_ms',22)/1000)*RATE))
        if attack:env[:attack]=np.sin(np.linspace(0,math.pi/2,attack))**2
        if count>gate:env[gate:]=np.cos(np.linspace(0,math.pi/2,count-gate))**2
        env*=1-.1*np.minimum(t/.3,1)
        level=(n['velocity']/110)**1.4*.23
        detunes=cfg.get('detune_cents',[-5,0,5]);harmonics=cfg.get('harmonics',12)
        for vi,cents in enumerate(detunes):
            ratio=2**(cents/1200);wave=np.zeros(count)
            cutoff=cfg.get('cutoff_hz',1900)+brightness*18
            for h in range(1,harmonics+1):
                weight=1/(h**cfg.get('spectral_tilt',1.25)*(1+(f*h/cutoff)**4))
                if cfg.get('odd_only') and h%2==0:weight*=.12
                weight=np.where(f*h*ratio<RATE*.45,weight,0)
                wave+=np.sin(h*(phase*ratio+vi*.43))*weight
            pan=.5 if len(detunes)==1 else .35+.3*vi/(len(detunes)-1)
            signal=wave*env*expr*level/len(detunes)
            out[start:end,0]+=signal*np.sqrt(1-pan)
            out[start:end,1]+=signal*np.sqrt(pan)
        prior_end=n['end_seconds'];prior_pitch=n['pitch'];phase_end=float(phase[gate-1]%(2*math.pi))
    write_wav(path,out)

def noise_fx(project,track,path):
    clock=Clock(project);out=np.zeros((round((clock.end+clock.tail)*RATE),2),dtype=np.float32)
    by_id={n['id']:n for n in track['notes']}
    for event in performed(track,clock):
        n=by_id[event['id']]
        start=round(event['start_seconds']*RATE);end=round(event['end_seconds']*RATE);count=end-start
        if count<1:continue
        rng=np.random.default_rng(int(hashlib.sha256(n['id'].encode()).hexdigest()[:8],16))
        t=np.arange(count)/RATE;progress=np.linspace(0,1,count)
        kind=n.get('articulation','rise');velocity=event['velocity']/127
        if kind=='impact':
            freq=45+70*np.exp(-t*16);sig=np.sin(2*math.pi*np.cumsum(freq)/RATE)*np.exp(-t*6)*np.minimum(t/.008,1)
            wave=np.column_stack([sig,sig])*.2
        elif kind=='vinyl':
            from .production import vinyl
            wave=vinyl(count,rng)*.13;fade=min(count//2,round(.05*RATE))
            wave[:fade]*=np.linspace(0,1,fade)[:,None];wave[count-fade:]*=np.linspace(1,0,fade)[:,None]
        else:
            white=rng.standard_normal((count,2));freq=np.fft.rfftfreq(count,1/RATE)
            band=(freq/1200)**2/(1+(freq/1200)**2)/(1+(freq/7500)**4)
            wave=np.fft.irfft(np.fft.rfft(white,axis=0)*band[:,None],n=count,axis=0)
            wave*=((progress**1.8 if kind=='rise' else np.exp(-t*4))*.13)[:,None]
            fade=min(count,round(.04*RATE));wave[-fade:]*=np.linspace(1,0,fade)[:,None]
        out[start:end]+=wave.astype(np.float32)*velocity
    write_wav(path,out)

def room_ir(path,seconds):
    frames=round((seconds*1.3+.08)*RATE);rng=np.random.default_rng(64019)
    noise=rng.standard_normal((frames,2));frequency=np.fft.rfftfreq(frames,1/RATE)
    noise=np.fft.irfft(np.fft.rfft(noise,axis=0)/(1+(frequency[:,None]/3600)**2),n=frames,axis=0)
    t=np.arange(frames)/RATE;envelope=np.exp(-math.log(1000)*np.maximum(0,t-.024)/seconds);envelope[t<.024]=0
    noise*=envelope[:,None];noise/=np.sqrt(np.sum(noise**2,axis=0))[None,:]
    noise*=.40
    for delay,level in [(.029,.30),(.047,.24),(.071,.18),(.101,.12)]:
        noise[round(delay*RATE),0]+=level;noise[round((delay+.009)*RATE),1]+=level
    write_wav(path,noise)
