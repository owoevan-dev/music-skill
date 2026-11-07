"""Deterministic per-track synthesis/cache, processed stems, FX returns and master.

The parts are synthesized and processed in parallel (`jobs` threads; the heavy work runs in FluidSynth and FFmpeg
processes and in NumPy, which release the interpreter). Every part writes only its own files, so the stems and the
master are the same for any `jobs`.  The renders of a piece share its cache, so a part holds its cache entry while it
is synthesized, processed and kept (entry_lock): a render that needs the same entry at the same time waits, then
finds the part in the cache, and no render reads a file another is replacing.

A part's cache entry also keeps its last processed stem.  When nothing the processing reads has changed, the render
copies that stem instead of processing the part again, as a frozen track in a DAW plays its rendered file instead of
computing its devices again (Ableton Live Reference Manual, Computer Audio Resources and Strategies).  The copy is
what is checked against the receipt.  Every render still mixes and masters all the parts.

A draft (`draft=True`) is the same audio, stems, buses and returns as a full render, for revising: it leaves out what
only delivery needs, master.flac, the MP3's decoded-loudness check and a game loop's Ogg copies and layers, as REAPER's
dry-run render processes everything but writes no output files (REAPER 6.30)."""
import contextlib
import errno
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import threading
import time
import numpy as np
from . import audio, drums, layered, midi, production, stage, surge, synth, variation
from .model import Clock, load_project, validate, performed, save_json, digest, file_hash, TPQ

def engine_hash():
    """The renderer's code: every musiclib module and the Surge host the renderer starts."""
    host=Path(__file__).resolve().parents[1]/'surge_host.py'
    return digest({**{p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')},'surge_host.py':file_hash(host)})

def free_memory():
    """Bytes of memory free for new work, or None where it cannot be read (macOS gives half its installed memory)."""
    try:
        if os.name=='nt':
            import ctypes
            class Status(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('total','avail','page_total','page_avail','virtual_total','virtual_avail','extended')]
            s=Status();s.length=ctypes.sizeof(Status)
            return s.avail if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)) else None
        if os.path.exists('/proc/meminfo'):
            with open('/proc/meminfo',encoding='ascii') as f:
                for line in f:
                    if line.startswith('MemAvailable:'):return int(line.split()[1])*1024
        return os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')//2
    except (OSError,ValueError,AttributeError):
        return None

def default_jobs():
    """Parallel parts: one per processor, at most 8, and one per 2 GB of free memory (a long part with a mono synth line
    or effects can hold that much while it works)."""
    jobs=max(1,min(8,os.cpu_count() or 1));free=free_memory()
    return max(1,min(jobs,int(free//2e9))) if free else jobs

def synthesis_identity(p,clock,t,deps,renderer):
    """What a part's raw synthesis depends on, hashed into its cache key: the clock and the tempo as played (phrase
    rubato slows into section boundaries, so moving a section changes it), the part without its mix, the configured
    dependencies and the synthesis code and preset files.  A mix edit leaves it unchanged and reuses the part."""
    return {'cache':2,'clock':p['clock'],'played_tempo':clock.tempo,'track':{k:v for k,v in t.items() if k!='mix'},'dependencies':deps,'renderer':renderer,'sample_rate':audio.RATE}

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

def stem_identity(p,t,key,raw_sha256,frames,code_hash,cfg):
    """What a part's processed stem depends on, hashed into the key of the stem its cache entry keeps: its raw
    synthesis (whose key holds the clock and the tempo as played), its mix but the fields only the mixer reads, the
    song's length, the part a duck follows (its notes as played), the renderer's code, FFmpeg and NumPy."""
    by=(t['mix'].get('duck') or {}).get('by')
    source=next((x for x in p['tracks'] if x['id']==by),None) if by else None
    return {'stem':2,'synthesis':key,'raw_sha256':raw_sha256,'mix':{k:v for k,v in t['mix'].items() if k not in MIXER_ONLY},
            'frames':frames,'ducked_by':{k:v for k,v in source.items() if k!='mix'} if source else None,
            'renderer':code_hash,'ffmpeg':cfg['ffmpeg']['sha256'],'numpy':np.__version__}

def read_json(path):
    """A receipt's JSON object, or {} where there is none or it cannot be read."""
    try:value=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}
    return value if isinstance(value,dict) else {}

@contextlib.contextmanager
def entry_lock(folder,wait=True):
    """Hold one cache entry against other renders: an exclusive lock on its file `entry.lock` (fcntl.flock on POSIX,
    msvcrt.locking on Windows), which the system releases when the process ends.  Yields whether it is held; without
    `wait`, False at once when another render holds it.  Where the drive cannot lock, yields False and the render goes
    on: the stem it copies is still checked against its receipt."""
    try:fd=os.open(Path(folder)/'entry.lock',os.O_RDWR|os.O_CREAT,0o644)
    except OSError:
        yield False;return
    held=False
    try:
        if os.name=='nt':
            import msvcrt
            while True:
                try:
                    os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK,1);held=True;break
                except OSError as e:
                    # LK_LOCK gives up after ten tries a second apart while another render holds the entry: wait on.
                    if not wait or e.errno not in (errno.EDEADLK,errno.EACCES):break
        else:
            import fcntl
            try:fcntl.flock(fd,fcntl.LOCK_EX|(0 if wait else fcntl.LOCK_NB));held=True
            except OSError:pass
        yield held
    finally:
        if held:
            with contextlib.suppress(OSError):
                if os.name=='nt':os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
                else:fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

def keep_stem(folder,stem,receipt):
    """Keep a processed stem in its cache entry for the next render: copied under a name of this process and thread,
    swapped in whole, then its receipt likewise.  Keeping is only a saving: where it fails (Windows refuses to replace a
    file another program holds open) the render goes on, and the next one processes the part again."""
    tag=f'{os.getpid()}.{threading.get_ident()}'
    spare,note=Path(folder)/f'stem.{tag}.wav',Path(folder)/f'stem.{tag}.json'
    try:
        shutil.copyfile(stem,spare);os.replace(spare,Path(folder)/'stem.wav')
        note.write_text(json.dumps(receipt,ensure_ascii=False,allow_nan=False),encoding='utf-8');os.replace(note,Path(folder)/'stem.json')
        return True
    except OSError:
        for f in (spare,note):
            with contextlib.suppress(OSError):f.unlink()
        return False

def render(project_file,output,config_file,cache=None,resume=False,jobs=None,draft=False):
    started=time.monotonic();p=load_project(project_file);clock=Clock(p);cfg=audio.load_config(config_file)
    # Seconds per stage, each from the end of the one before, so they add up to the runtime (profiling the stages
    # before any is optimized: what a change saves shows here).
    stages={};mark=[started]
    def lap(name):
        now=time.monotonic();stages[name]=round(now-mark[0],3);mark[0]=now
    output=Path(output).resolve();cache=Path(cache).resolve() if cache else output.parent/'cache'
    # Before anything is synthesized: every part's bank is configured and can play what the part asks of it.
    fonts={t['id']:audio.soundfont_for(cfg,t)[1] for t in p['tracks'] if t['engine']=='soundfont'}
    problems=[m for t in p['tracks'] if t['id'] in fonts for m in [layered.unsupported(t,fonts[t['id']]['path'])] if m]
    if problems:raise ValueError('Parts the banks cannot play as written (review --config lists them too):\n'+'\n'.join(problems))
    project_key=digest(p);marker=output/'render_input.json'
    code_hash=engine_hash()
    # A cached part depends on this code and on the preset files the built-in synth and Surge parts read.
    synthesis_hash=digest({**{n:file_hash(Path(__file__).with_name(n)) for n in ('model.py','midi.py','audio.py','layered.py','sf2.py','synth.py','drums.py','variation.py','surge.py','wavfile.py')},
                           'synth-presets':file_hash(synth.PRESETS_FILE),'surge-presets':file_hash(surge.PRESETS_FILE)})
    if output.exists():
        if not resume or not marker.is_file() or json.loads(marker.read_text(encoding='utf-8'))['project_sha256']!=project_key:
            raise ValueError('Output exists; choose a fresh directory or resume the same project')
    for d in (output,cache,output/'logs',output/'stems',output/'midi',output/'returns'):d.mkdir(parents=True,exist_ok=True)
    save_json(marker,{'project_sha256':project_key,'renderer_sha256':code_hash})
    save_json(output/'project.json',p)
    lap('prepare')
    route=midi.write(p,output/'composition.mid')
    midi.write(p,output/'score.mid',expressive=False)
    save_json(output/'midi_routing.json',route)
    parsed=midi.read(output/'composition.mid')
    if any(t['unclosed'] or t['stray_offs'] for t in parsed['tracks']):raise ValueError('Exported MIDI lifecycle failed')
    note_count=sum(len(t['notes']) for t in parsed['tracks'])
    expected=sum(len(t['notes']) for t in p['tracks'])
    if note_count!=expected:raise ValueError('MIDI note count mismatch')
    lap('midi')
    duration=clock.end+clock.tail;frames=round(duration*audio.RATE)
    jobs=max(1,min(jobs or default_jobs(),len(p['tracks'])));locks={};guard=threading.Lock()
    def make_stem(t):
        began=time.monotonic()
        font_name,font=audio.soundfont_for(cfg,t) if t['engine']=='soundfont' else (None,None)
        deps={'fluidsynth':cfg['fluidsynth']['sha256'],'soundfont':font['sha256'] if font else None}
        if t['engine']=='surge':deps['surge']=surge.dependencies(cfg,t)
        identity=synthesis_identity(p,clock,t,deps,synthesis_hash)
        key=digest(identity);folder=cache/key;folder.mkdir(exist_ok=True)
        raw=folder/'raw.wav';receipt=folder/'receipt.json'
        track_midi=output/'midi'/(t['id']+'.mid')
        midi.write(p,track_midi,[t],single_stem=True)
        with guard:lock=locks.setdefault(key,threading.Lock())
        # The entry is held from the cache lookup to the kept stem: a render of the piece running at the same time waits
        # here for this part, then finds it in the cache.
        with lock,entry_lock(folder):
            cached=False;raw_sha=None;old=read_json(receipt) if raw.is_file() else {}
            if old:
                raw_sha=audio.audio_hash(raw);cached=old.get('key')==key and raw_sha==old.get('sha256')
            if not cached:
                if not t['notes']:audio.write_wav(raw,np.zeros((frames,2),dtype=np.float32))
                elif t['engine']=='soundfont' and layered.wanted(t):layered.render(p,t,clock,cfg,font,folder,raw)
                elif t['engine']=='soundfont':
                    # The synthesis MIDI applies the track's render patch/key map; the exported part MIDI does not.
                    patch=t.get('patch') or {'bank':t.get('bank',0),'program':t.get('program',0)}
                    keys=variation.key_samples(font['path'],patch.get('bank',0),patch.get('program',0)) if t['performance'].get('round_robin') else None
                    # A drum part steps through the bank's recorded round robins unless round_robin is set false.
                    cycles=variation.velocity_cycles(font['path'],patch.get('bank',0),patch.get('program',0)) if t.get('drums') and t['performance'].get('round_robin',True) is not False else None
                    synth_midi=folder/'synth.mid';midi.write(p,synth_midi,[t],single_stem=True,render=True,keys=keys,cycles=cycles)
                    audio.fluidsynth(cfg,font['path'],synth_midi,raw,folder)
                elif t['engine']=='additive':audio.synthesize(p,t,raw)
                elif t['engine']=='synth':synth.render(p,t,raw,clock)
                elif t['engine']=='surge':
                    # Surge XT when it is installed; otherwise the part's fallback preset on the built-in synth.
                    played={'preset':t['surge']['preset']}
                    try:played.update(surge.render(p,t,raw,folder,cfg) or {});played['rendered_with']='Surge XT'
                    except surge.Unavailable as e:
                        fallback=surge.fallback_track(t);synth.render(p,fallback,raw,clock)
                        played.update(rendered_with='built-in synth',fallback=fallback['synth']['preset'],reason=str(e))
                    save_json(folder/'surge.json',played)
                elif t['engine']=='drum_synth':drums.render(p,t,raw,clock)
                else:audio.noise_fx(p,t,raw)
                raw_sha=audio.audio_hash(raw)
                save_json(receipt,{'key':key,'sha256':raw_sha,'track':t['id']})
            synthesized=time.monotonic()
            stem=output/'stems'/(t['id']+'.wav')
            # The processed stem the cache entry keeps, used when nothing it depends on has changed: the copy this
            # render mixes is what is checked against the receipt read before it.
            frozen,frozen_receipt=folder/'stem.wav',folder/'stem.json'
            stem_key=digest(stem_identity(p,t,key,raw_sha,frames,code_hash,cfg))
            kept=read_json(frozen_receipt);reused=False
            if kept.get('key')==stem_key and isinstance(kept.get('processing'),dict) and {'reference_level_dbfs','gain_db','filter_chain'}<=set(kept['processing']) and frozen.is_file():
                try:shutil.copyfile(frozen,stem);reused=file_hash(stem)==kept.get('sha256')
                except OSError:reused=False
            if reused:done,stem_sha=kept['processing'],kept['sha256']
            else:
                done=process_stem(p,t,clock,cfg,output,raw,stem,frames);stem_sha=file_hash(stem)
                keep_stem(folder,stem,{'key':stem_key,'sha256':stem_sha,'track':t['id'],'processing':done})
            expressive=read_json(folder/'layered.json') if (folder/'layered.json').is_file() else None
            heard=read_json(folder/'surge.json') if t['engine']=='surge' and (folder/'surge.json').is_file() else None
        receipt_data={'track':t['id'],'soundfont':font_name,'cache_key':key,'cache_hit':cached,'stem_reused':reused,'raw_sha256':raw_sha,'stem_sha256':stem_sha,'reference_level_dbfs':done['reference_level_dbfs'],'gain_db':done['gain_db'],'processed_stem':str(stem.relative_to(output)),'filter_chain':done['filter_chain'],'same_pitch_retrigger_trims':sum(n.get('retrigger_trimmed',False) for n in performed(t,clock))}
        if expressive:receipt_data['expressive']=expressive
        if heard:receipt_data['surge']=heard
        if done.get('stage'):receipt_data['stage']=done['stage']
        if done.get('production'):receipt_data['production']=done['production']
        # Each part's own seconds (they overlap: parts run `jobs` at a time); synthesis includes the cache lookup.
        receipt_data['seconds']={'synthesis':round(synthesized-began,3),'processing':round(time.monotonic()-synthesized,3)}
        return receipt_data,font_name,font
    with ThreadPoolExecutor(max_workers=jobs) as pool:results=list(pool.map(make_stem,p['tracks']))
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
    if after['true_peak_dbtp']>-1 or after['clipped_samples'] or after['frames']!=frames:
        raise ValueError(f'Master delivery check failed: true peak {after["true_peak_dbtp"]:g} dBTP (at most -1), '
                         f'{after["clipped_samples"]} clipped samples, {after["frames"]} of {frames} frames')
    lap('master_check')
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
    with ThreadPoolExecutor(max_workers=3) as pool:
        made=[pool.submit(preview)]+([] if draft else [pool.submit(lossless)])+([pool.submit(looping)] if 'loop' in p else [])
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
    checks={'finite':bool(np.isfinite(data).all()),'no_clipping':after['clipped_samples']==0,'true_peak_ceiling':after['true_peak_dbtp']<=-1,'duration_exact':after['frames']==frames,'stereo_48k_24bit':after['channels']==2 and after['sample_rate']==48000 and after['bits']==24,'tail_quiet':float(np.max(np.abs(data[-2400:])))<.001,'midi_note_count':note_count==expected,'midi_no_stuck_notes':True,'dependency_hashes_verified':True}
    if mp3:checks['mp3_loudness_matches_master']=mp3['matches']
    if buses:checks['buses_and_returns_add_up_to_premix']=buses['adds_up_to_premix']
    if looped:checks.update(looped.pop('checks'))
    lap('sections_and_checks')
    passed=all(checks.values())
    report={'status':('DRAFT_PASS' if draft else 'TECHNICAL_PASS_AUDITION_PENDING') if passed else 'FAIL','title':p['title'],'version':p.get('version'),'draft':draft,'runtime_seconds':round(time.monotonic()-started,2),'stage_seconds':stages,'process_seconds':process_seconds(output/'logs'),'jobs':jobs,'project_sha256':project_key,'renderer_sha256':code_hash,'validation':validate(p),'checks':checks,'chain':chain_name,'premaster':before,'master':after,'sections':sections,'mastering':mastering,'buses':buses,'mp3':mp3,'cache_hits':sum(r['cache_hit'] for r in receipts),'stems_reused':sum(r['stem_reused'] for r in receipts),'stem_count':len(receipts),'direct_audio_listening_performed':False,'perceptual_quality':'Not certified by numeric checks; user audition pending','dependencies':{**{k:{x:v for x,v in cfg[k].items() if x!='path'} for k in ('fluidsynth','ffmpeg')},'soundfonts':{n:{x:v for x,v in f.items() if x!='path'} for n,f in used_fonts.items()}}}
    if draft:
        # The same audio as a full render; what only delivery needs is left out. Deliver a full render.
        report['left_out']=['master.flac']+(['the check that preview.mp3 decodes to the master\'s loudness'] if chain_name=='bus' else [])+(['loop.ogg and the loop layers'] if 'loop' in p else [])
    if looped:report['loop']=looped
    save_json(output/'report.json',report)
    if not passed:
        failed=[k for k,ok in checks.items() if not ok]
        advice={'tail_quiet':'the master still sounds in its last 50 ms (above -60 dBFS): give the note releases and the reverb more time with clock.tail_seconds'}
        raise ValueError('Delivery checks failed ('+', '.join(failed)+'); '+''.join(advice[k]+'; ' for k in failed if k in advice)+f'see {output/"report.json"}')
    return report

def process_stem(p,t,clock,cfg,output,raw,stem,frames):
    """The part's raw synthesis to its processed stem: the gain to its level, filters, EQ, effects, compressor, width,
    pan or stage position and automation, then the production tools.  Returns what the receipt records of it."""
    ref=audio.reference_level(raw,t['mix'].get('level_mode','active_rms')) if t['notes'] else 0
    gain=t['mix']['level_dbfs']-ref if t['notes'] else 0
    if not -60<=gain<=45:raise ValueError(f'Unexpected instrument gain: {t["id"]}: {gain}')
    fx=t['mix'];co=fx.get('compressor')
    filters=[f'apad,atrim=end_sample={frames}',f'volume={gain:.9f}dB',f'highpass=f={fx.get("highpass",30)}',f'lowpass=f={fx.get("lowpass",18000)}']
    filters += [f'equalizer=f={f}:t=q:w=1:g={g}' for f,g in fx.get('eq',[])]
    for e in fx.get('effects',[]):
        # Modulation and lo-fi effects after the EQ: the chorus in NumPy (production.chorus; FFmpeg's chorus steps
        # its moving delay in whole samples, a buzz on sustained parts), FFmpeg's aphaser and acrusher.
        if e['type']=='chorus':filters.append(('chorus',e.get('depth',.5)))
        elif e['type']=='phaser':filters.append(f'aphaser=in_gain=0.8:out_gain=0.9:delay=3:decay={.2+.5*e.get("depth",.5):.3f}:speed={e.get("rate_hz",.5)}:type=t')
        elif e['type']=='bitcrush':filters.append(f'acrusher=bits={e.get("bits",8)}:samples={e.get("downsample",4)}:mix={e.get("mix",1)}:mode=lin')
    if co:filters.append(f'acompressor=threshold={10**(co["threshold_db"]/20):.9f}:ratio={co["ratio"]}:attack={co["attack_ms"]}:release={co["release_ms"]}:makeup=1')
    pan=fx.get('pan',0);width=fx.get('width',1)
    if width<1:
        # Mid/side width before the pan: spaced-microphone samples (some piano and room recordings) are nearly
        # uncorrelated left/right, which leaves a lead diffuse and off-centre and partly cancels in mono.
        a,b=(1+width)/2,(1-width)/2
        filters.append(f'pan=stereo|c0={a:.9f}*c0+{b:.9f}*c1|c1={b:.9f}*c0+{a:.9f}*c1')
    depth=fx.get('depth_m')
    # A part placed on the stage gets its pan with its early reflections (musiclib/stage.py), after the chain.
    filters.extend(([] if depth is not None else [f'pan=stereo|c0={math.sqrt(1-pan):.9f}*c0|c1={math.sqrt(1+pan):.9f}*c1'])+[audio.automation(fx.get('automation',[]),clock)])
    filters.append(f'apad,atrim=end_sample={frames}')  # a chorus or phaser delays the signal and would lengthen the stem
    # One FFmpeg pass, or, around each chorus, a pass up to it, the chorus in NumPy on that file, and on. A later
    # pass's log takes ".pass{k}": a part id cannot hold a dot, so the label never names another part's log.
    src,run,k=raw,[],0
    for f in filters+[None]:
        if isinstance(f,str):run.append(f);continue
        if run:
            out=stem if f is None else output/'stems'/f'.{t["id"]}.pass{k}.wav'
            audio.ffmpeg(cfg,['-i',src,'-af',','.join(run),'-ar',str(audio.RATE),'-c:a','pcm_f32le',out],output/'logs','process_'+t['id']+(f'.pass{k}' if k else ''))
            if src!=raw:src.unlink()
            src,run,k=out,[],k+1
        if f is None:break
        x,_=audio.read_wav(src);x,_=production.chorus(x,f[1]);audio.write_wav(src,x)
    done={'reference_level_dbfs':ref,'gain_db':gain,'filter_chain':','.join(f if isinstance(f,str) else f'chorus(depth={f[1]}, production.chorus)' for f in filters)}
    if depth is not None:
        x,_=audio.read_wav(stem);x,placed=stage.place(x,pan,depth,fx.get('facing','front'));audio.write_wav(stem,x)
        if placed:done['stage']={'depth_m':depth,'facing':fx.get('facing','front'),**placed}
    if production.wanted(t):
        # Sweeps, saturation, gates, tempo-synced delays and ducking (musiclib/production.py), on the placed stem.
        x,_=audio.read_wav(stem);x,produced=production.process(x,p,t,clock);audio.write_wav(stem,x)
        if produced:done['production']=produced
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
    graph.append(''.join(buses)+f'amix=inputs={len(buses)}:normalize=0:duration=longest,atrim=end_sample={frames}{fade},afade=t=out:st={duration-1.7:.8f}:d=1.7[mix]')
    graph_text=';\n'.join(graph);(output/'mix.filtergraph.txt').write_text(graph_text,encoding='utf-8')
    premaster=output/'premaster.wav'
    outs=['-map','[mix]','-ar',str(audio.RATE),'-c:a','pcm_f32le',premaster]
    for label,name in exports:outs+=['-map',f'[{label}]','-ar',str(audio.RATE),'-c:a','pcm_f32le',output/'returns'/name]
    audio.ffmpeg(cfg,[*args,'-filter_complex',graph_text,*outs],output/'logs','mix')
    before=audio.measure(cfg,premaster,output/'logs','measure_premaster')
    ceiling=p['mix'].get('peak_ceiling_db',-1.6);allowance=p['mix'].get('max_limit_db',1.5)
    gain=min(p['mix'].get('target_lufs',-16)-before['integrated_lufs'],ceiling-before['true_peak_dbtp']+allowance)
    chain=f'volume={gain:.9f}dB,aresample=192000,alimiter=limit={10**(ceiling/20):.9f}:attack=5:release=110:level=false:latency=true,aresample=48000,apad,atrim=end_sample={frames}'
    audio.ffmpeg(cfg,['-i',premaster,'-af',chain,'-c:a','pcm_s24le',output/'master.wav'],output/'logs','master')
    return before,{'chain':'room','gain_db':gain,'ceiling_db':ceiling,'max_input_peak_above_ceiling_db':max(0,before['true_peak_dbtp']+gain-ceiling),'limiter_chain':chain}
