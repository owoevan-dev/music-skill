"""MIT. Single-agent music production: validate, inspect, export, render, revise."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
from musiclib.model import load_project, validate, save_json, file_hash
from musiclib import files,midi,summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('validate','review','export-midi','render','revise'):
        cmd=sub.add_parser(name);cmd.add_argument('project',type=Path)
        if name in ('review','export-midi','render'):cmd.add_argument('--output',type=Path,required=True)
        if name=='review':cmd.add_argument('--config',type=Path,help='also check each note against the samples of its bank')
        if name in ('review','render'):cmd.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
        if name=='render':
            cmd.add_argument('--config',type=Path,required=True);cmd.add_argument('--cache',type=Path);cmd.add_argument('--resume',action='store_true')
            cmd.add_argument('--jobs',type=int,help='parts rendered at once (default: one per processor, at most 8, each waiting for its share of the free memory; the result is the same)')
            cmd.add_argument('--draft',action='store_true',help='for revising: the same audio, stems, buses and returns, without master.flac, the MP3 loudness check and a loop\'s Ogg copies and layers; deliver a full render')
        if name=='revise':
            cmd.add_argument('--track',required=True);cmd.add_argument('--note',required=True)
            cmd.add_argument('--pitch',type=int);cmd.add_argument('--velocity',type=int);cmd.add_argument('--duration',type=float)
            cmd.add_argument('--output',type=Path,required=True)
    doctor=sub.add_parser('doctor');doctor.add_argument('--config',type=Path,required=True)
    addsf=sub.add_parser('add-soundfont',help='Write a new config that adds a named SoundFont to an existing one')
    for arg in ('config','path','output'):addsf.add_argument('--'+arg,type=Path,required=True)
    for arg in ('name','license','source','version'):addsf.add_argument('--'+arg,required=True)
    inspect=sub.add_parser('inspect-midi');inspect.add_argument('file',type=Path);inspect.add_argument('--output',type=Path)
    analyze=sub.add_parser('analyze',help='Measure a finished render: section levels and spectrum, stereo, stem levels, lead presence')
    analyze.add_argument('render',type=Path);analyze.add_argument('--output',type=Path,help='JSON report (default: <render>/analysis.json)')
    analyze.add_argument('--span',action='append',default=[],metavar='NAME:FIRST-LAST',help='also measure bars FIRST to LAST (1-based) under NAME; repeatable')
    analyze.add_argument('--reference',help='compare the whole master with a reference: a name in references/tonal-references.json, a render folder or a WAV file')
    analyze.add_argument('--config',type=Path,help='needed with a WAV reference: FFmpeg converts and meters it')
    analyze.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    cmp=sub.add_parser('compare',help='Compare two renders: what the project changed, which parts were synthesized again, and where each stem, bus, return, the premix and the master changed')
    cmp.add_argument('before',type=Path);cmp.add_argument('after',type=Path)
    cmp.add_argument('--output',type=Path,help='JSON report (default: <after>/compare_<before folder>.json)')
    cmp.add_argument('--differences',type=Path,metavar='FOLDER',help='a new folder for every changed file as after minus before, level-matched: the change alone')
    cmp.add_argument('--clip',type=Path,metavar='MP3',help='an old-then-new MP3 of 8 seconds around the first change in the master, both at the same loudness (needs --config)')
    cmp.add_argument('--config',type=Path,help='needed with --clip: FFmpeg measures and encodes it')
    cmp.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    aud=sub.add_parser('audition',help="Play one part's passage on several sounds in turn: the same notes in the same mix, at one loudness, with each sound's measured brightness")
    aud.add_argument('project',type=Path);aud.add_argument('--track',required=True)
    aud.add_argument('--sounds',required=True,help='comma-separated: surge:<preset>, synth:<preset>, soundfont:<bank>:<bank number>:<program>; the part as written plays first')
    aud.add_argument('--bars',required=True,metavar='FIRST-LAST',help='the passage, 1-based, at most 16 bars')
    aud.add_argument('--output',type=Path,required=True);aud.add_argument('--config',type=Path,required=True);aud.add_argument('--cache',type=Path)
    aud.add_argument('--solo',action='store_true',help='the part alone instead of in its passage with the others')
    aud.add_argument('--jobs',type=int,help='parts rendered at once in each version (as render --jobs)')
    aud.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    snd=sub.add_parser('sounds',help='Search the Surge XT catalog: every factory and third-party patch, by role, measured character, name and source, for a shortlist to audition')
    snd.add_argument('--role',help='lead, brass, pad, chords, keys, pluck, bass, sequence, fx or percussion')
    snd.add_argument('--character',default='',help='comma-separated words the measured character must contain: dark, warm, mid, bright; fast, soft, slow; dry, short, long; mono, narrow, wide')
    snd.add_argument('--name',help='text in the patch name or category');snd.add_argument('--source',help='"factory" or a designer')
    snd.add_argument('--limit',type=int,default=25);snd.add_argument('--all',action='store_true',help='also patches flagged silent, MPE, microtonal or off pitch')
    snd.add_argument('--id',help='one catalog patch in full: its measurement and what its mod wheel and macros move')
    snd.add_argument('--seed',type=int,help="the piece's seed (musiclib.blocks.seed(title)): which patch each band of the spread shows, so two pieces see different ones")
    prof=sub.add_parser('profile',help='Describe the written score per part and section: density, register, intervals, rhythm, repetition')
    prof.add_argument('project',type=Path);prof.add_argument('--output',type=Path,help='full JSON (without it, the full profile is printed)')
    rnd=sub.add_parser('round',help='One revision round: validate, review, a draft render, analyze it and compare it with the previous round, each with a short summary')
    rnd.add_argument('project',type=Path);rnd.add_argument('--output',type=Path,required=True,help='a new folder for the round: review/, render/ and round.json')
    rnd.add_argument('--config',type=Path,required=True);rnd.add_argument('--previous',type=Path,help="the previous round's folder (or a render folder) to compare with")
    rnd.add_argument('--cache',type=Path,help='default: the folder cache next to the round, which every round shares')
    rnd.add_argument('--jobs',type=int,help='parts rendered at once (as render --jobs)')
    rnd.add_argument('--span',action='append',default=[],metavar='NAME:FIRST-LAST',help='also analyze bars FIRST to LAST (1-based) under NAME; repeatable')
    rnd.add_argument('--reference',help='analyze against a reference: a name in references/tonal-references.json, a render or round folder, or a WAV file')
    rnd.add_argument('--clip',type=Path,metavar='MP3',help='with --previous: an old-then-new MP3 of 8 seconds around the first change in the master, both at the same loudness')
    rnd.add_argument('--json',action='store_true',help="print round.json instead of the steps' summaries")
    cln=sub.add_parser('clean',help="List, or with --remove remove, the piece's render and round folders other than those kept, its auditions' renders and caches, and the cache entries the kept renders do not use")
    cln.add_argument('folder',type=Path,help="the piece's folder")
    cln.add_argument('--keep',type=Path,action='append',required=True,help='a render or round folder that stays (repeatable): the final render and the previous round')
    cln.add_argument('--remove',action='store_true',help='remove what the list names (without it, nothing is removed)')
    cln.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    configure=sub.add_parser('configure')
    for arg in ('fluidsynth','ffmpeg','soundfont','output'):configure.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args()
    def fresh(path,source=None):
        # Taken in any form, a dangling link included (Path.exists follows links): outputs never overwrite.
        files.fresh(path)
        if source is not None and path.resolve()==Path(source).resolve():raise ValueError('The output would replace its own input')
    if args.command=='configure':
        if files.occupied(args.output):raise ValueError('Choose a new configuration path')
        from musiclib import sf2
        sf2.read(args.soundfont)  # as add-soundfont: a bank whose tables do not hold together is refused before it is configured
        cfg={key:{'path':str(getattr(args,key).resolve()),'sha256':file_hash(getattr(args,key)),'license':'User-supplied; retain upstream notices','source':'User-configured local file; hash is integrity, not provenance or antivirus certification'} for key in ('fluidsynth','ffmpeg','soundfont')}
        save_json(args.output,cfg,new=True);print('Saved configuration; inspect source/license before redistribution');return
    if args.command=='add-soundfont':
        import re
        if files.occupied(args.output):raise ValueError('Choose a new configuration path')
        if args.name=='default' or not re.fullmatch(r'[a-z][a-z0-9_]{0,47}',args.name):raise ValueError('Name must be lower-case letters/digits/underscores and not "default"')
        from musiclib.audio import absolute_paths
        base=files.read_json(os.path.abspath(args.config))  # by the name given, never through a link (GPT Pro's fifth review)
        if not isinstance(base,dict):raise ValueError(f'{args.config}: a configuration is a JSON object')
        base=absolute_paths(base,args.config.resolve().parent,args.config);fonts=base.setdefault('soundfonts',{})
        if args.name in fonts:raise ValueError('SoundFont name already configured')
        from musiclib import sf2
        bank=sf2.read(args.path)
        fonts[args.name]={'path':str(args.path.resolve()),'sha256':file_hash(args.path),'license':args.license,'source':args.source,'version':args.version,'presets':[[p['bank'],p['program'],p['name']] for p in bank['presets']]}
        save_json(args.output,base,new=True);print('Saved',args.output,'with',len(bank['presets']),'presets in',args.name);return
    if args.command=='doctor':
        from musiclib.audio import load_config,run
        import numpy,tempfile
        c=load_config(args.config,all_banks=True)
        print('Python',sys.version.split()[0],'NumPy',numpy.__version__)
        # The version checks log into a temporary folder of their own: doctor writes nothing beside the configuration.
        with tempfile.TemporaryDirectory(prefix='doctor-') as logs:
            for key in ('fluidsynth','ffmpeg'):
                output=run([c[key]['path'],'--version' if key=='fluidsynth' else '-version'],logs,key,30)
                print(output.splitlines()[0])
        from musiclib.loop import has_vorbis
        print('Ogg Vorbis for game loops:','yes' if has_vorbis(c) else 'no, this FFmpeg has no libvorbis encoder (references/setup.md)')
        for name,entry in [('default',c['soundfont'])]+sorted(c.get('soundfonts',{}).items()):
            print('SoundFont',name,'|',entry.get('version',''),'|',entry.get('license',''))
        print('PASS: paths and pinned checksums verified; no malware scan implied');return
    if args.command=='clean':
        from musiclib.clean import clean,describe
        r=clean(args.folder,args.keep,remove=args.remove)
        print(json.dumps(r,ensure_ascii=True) if args.json else describe(r));return
    if args.command=='inspect-midi':
        if args.output:fresh(args.output,args.file)
        m=midi.read(args.file);result={'division':m['division'],'tracks':len(m['tracks']),'notes':sum(len(t['notes']) for t in m['tracks']),'unclosed':sum(t['unclosed'] for t in m['tracks']),'stray_offs':sum(t['stray_offs'] for t in m['tracks']),'sha256':file_hash(args.file)}
        if args.output:save_json(args.output,result,new=True)
        print(json.dumps(result));return
    def parse_spans(given):
        import re
        spans=[]
        for x in given:
            m=re.fullmatch(r'([A-Za-z0-9_-]{1,40}):(\d+)-(\d+)',x)
            if not m or int(m.group(2))<1 or int(m.group(3))<int(m.group(2)):raise ValueError(f'--span {x}: write NAME:FIRST-LAST with 1 <= FIRST <= LAST')
            spans.append((m.group(1),int(m.group(2)),int(m.group(3))))
        return spans
    from musiclib.revision import render_folder
    def reference_of(spec):
        # A round's folder stands for its render.
        return str(render_folder(spec)) if spec and Path(spec).is_dir() else spec
    if args.command=='round':
        from musiclib.revision import revision_round
        if args.jobs is not None and args.jobs<1:raise ValueError('--jobs is 1 or more')
        show=(lambda text:None) if args.json else (lambda text:print(text,end='\n\n',flush=True))
        r=revision_round(args.project,args.output,args.config,args.previous,args.cache,parse_spans(args.span),reference_of(args.reference),args.jobs,show,args.clip)
        if args.json:print(json.dumps(r,ensure_ascii=True))
        return
    if args.command=='analyze':
        from musiclib.analysis import analyze,load_reference
        from musiclib.audio import load_config
        given=args.render;args.render=render_folder(args.render);spans=parse_spans(args.span);out=args.output or args.render/'analysis.json'
        if files.occupied(out) and not args.output:
            raise ValueError(f'{out} exists'+(' (the round measured its render already)' if args.render!=given else '')+'; outputs never overwrite, so to measure again (other --span or --reference) choose a path with --output')
        fresh(out)
        reference=load_reference(reference_of(args.reference),load_config(args.config) if args.config else None) if args.reference else None
        # The render is held while it is read and the report written into it: clean leaves it alone meanwhile, and
        # a render still at work there is refused (found by GPT Pro's third review of 0.4.0).
        with files.working(args.render):
            r=analyze(args.render,spans,reference);save_json(out,r,new=True)
            files.register_output(out)  # inside a render or round folder, it goes with that folder in clean
        print(json.dumps(r,ensure_ascii=True) if args.json else summary.analysis(r,out,args.render));return
    if args.command=='compare':
        from musiclib.compare import compare,clip
        from musiclib.audio import load_config
        if args.clip and not args.config:raise ValueError('--clip needs --config: FFmpeg measures and encodes the clip')
        # A round's folder stands for its render, and names the default report: compare_<round>.json. A round wrote
        # that file for its previous round already, so a second comparison of the two needs --output.
        named=args.before.resolve().name if (args.before/'round.json').is_file() else None
        args.before,args.after=render_folder(args.before),render_folder(args.after)
        out=args.output or args.after/f'compare_{named or args.before.resolve().name}.json'
        if files.occupied(out) and not args.output:raise ValueError(f'{out} exists (a round compares with its previous round); choose a path with --output')
        fresh(out)
        if args.clip:fresh(args.clip)
        if args.differences:fresh(args.differences)
        # Both renders are held while they are read and the report written into one: clean leaves them alone
        # meanwhile, and a render still at work is refused (files.working; found by GPT Pro's third review of 0.4.0).
        import contextlib
        with contextlib.ExitStack() as held:
            held.enter_context(files.working(args.before))
            if args.after.resolve()!=args.before.resolve():held.enter_context(files.working(args.after))
            r=compare(args.before,args.after,args.differences)
            if args.clip:
                # The clip is optional: if it cannot be made, the report still is, and says why.
                try:r['clip']=clip(load_config(args.config),r,args.clip)
                except (ValueError,OSError,RuntimeError) as e:r['clip']={'error':str(e)}
            from musiclib.compare import portable
            # The report as saved, its folders relative to it, is also what --json prints: shared or redirected, it
            # carries no local folders either.
            shared=portable(r,out.parent);save_json(out,shared,new=True)
            # Written inside a render or round folder, each goes with that folder in clean.
            for written in [out]+([Path(r['clip']['file'])] if isinstance(r.get('clip'),dict) and r['clip'].get('file') else []):
                files.register_output(written)
            if args.differences:
                for f in files.tree(args.differences):files.register_output(f)
        print(json.dumps(shared,ensure_ascii=True) if args.json else summary.compare(r,out));return
    if args.command=='sounds':
        from musiclib.sounds import describe,search
        print(json.dumps(describe(args.id) if args.id else search(args.role,[w for w in args.character.split(',') if w.strip()],args.name,args.source,args.limit,args.all,args.seed),ensure_ascii=True,indent=1));return
    p=load_project(args.project)
    if args.command=='validate':print(json.dumps(validate(p)));return
    if args.command=='profile':
        from musiclib.profile import profile
        r=profile(p)
        if not args.output:print(json.dumps(r,ensure_ascii=True,indent=1));return
        fresh(args.output);save_json(args.output,r,new=True)
        brief={k:{f:v.get(f) for f in ('notes_per_bar','register','rhythm_repeat_pct','offbeat_onsets_pct') if f in v}|({'top_line':{f:v['top_line'][f] for f in ('mean_abs_interval','leaps_pct','recurring_cells_pct')}} if v.get('top_line') else {}) for k,v in r['parts'].items()}
        print(json.dumps({'output':str(args.output),'seconds':r['seconds'],'notes_per_bar':r['notes_per_bar'],'parts':brief},ensure_ascii=True));return
    if args.command=='review':
        from musiclib.review import review
        from musiclib.audio import load_config
        fresh(args.output);r=review(p,args.output,load_config(args.config) if args.config else None)
        print(json.dumps(r,ensure_ascii=True) if args.json else summary.review(r,args.output));return
    if args.command=='export-midi':
        if files.occupied(args.output):raise ValueError('Output already exists')
        args.output.parent.mkdir(parents=True,exist_ok=True);midi.write(p,args.output,new=True);print(str(args.output));return
    if args.command=='audition':
        from musiclib.audition import audition,parse_sound
        bars=args.bars.split('-')
        if len(bars)!=2 or not all(b.isdigit() for b in bars):raise ValueError('--bars is FIRST-LAST, for example 21-24')
        if args.jobs is not None and args.jobs<1:raise ValueError('--jobs is 1 or more')
        r=audition(args.project,args.track,[parse_sound(x) for x in args.sounds.split(',') if x.strip()],int(bars[0]),int(bars[1]),args.output,args.config,args.cache,args.solo,args.jobs)
        print(json.dumps(r,ensure_ascii=True) if args.json else summary.audition(r,args.output));return
    if args.command=='render':
        from musiclib.render import render
        if args.jobs is not None and args.jobs<1:raise ValueError('--jobs is 1 or more')
        r=render(args.project,args.output,args.config,args.cache,args.resume,args.jobs,args.draft)
        print(json.dumps(r,ensure_ascii=True) if args.json else summary.render(r,args.output));return
    if args.command=='revise':
        if files.occupied(args.output) or args.output.resolve()==args.project.resolve():raise ValueError('Revision must use a fresh output path')
        if args.pitch is None and args.velocity is None and args.duration is None:raise ValueError('Specify a change')
        revised=copy.deepcopy(p);t=next((t for t in revised['tracks'] if t['id']==args.track),None)
        if t is None:raise ValueError(f'No track {args.track!r}; the tracks are '+', '.join(x['id'] for x in revised['tracks']))
        n=next((n for n in t['notes'] if n['id']==args.note),None)
        if n is None:raise ValueError(f'No note {args.note!r} in {args.track}; its first notes are '+', '.join(x['id'] for x in t['notes'][:8]))
        if args.pitch is not None:n['pitch']=args.pitch
        if args.duration is not None:n['duration']=args.duration
        if args.velocity is not None:t['performance']['notes'][n['id']]['velocity']=args.velocity
        revised.setdefault('revision_history',[]).append({'parent_sha256':file_hash(args.project),'track':args.track,'note':args.note,'pitch':args.pitch,'velocity':args.velocity,'duration':args.duration})
        validate(revised);save_json(args.output,revised,new=True);print(str(args.output));return

if __name__=='__main__':
    files.escape_unprintable()
    try:main()
    except KeyError as e:
        print('ERROR: missing field',e,file=sys.stderr);sys.exit(2)
    except (ValueError,OSError,RuntimeError,TimeoutError) as e:
        print('ERROR:',str(e),file=sys.stderr);sys.exit(2)
