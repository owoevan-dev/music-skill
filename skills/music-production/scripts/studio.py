"""MIT. Single-agent music production: validate, inspect, export, render, revise."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import sys
try:
    import numpy  # noqa: F401
except ImportError:
    sys.exit(f'NumPy is missing from this Python ({sys.executable}). Install it for this interpreter (python -m pip install numpy) '
             'or run the scripts with the Python the setup used (references/setup.md).')
from musiclib.model import load_project, validate, save_json, file_hash
from musiclib import files,midi,summary

EXAMPLES = """The usual order of a piece (SKILL.md gives it in full):
  python studio.py validate song.json
  python studio.py review song.json --output review_1
  python studio.py round song.json --output round_1 --config ~/.music-skill/local-config.json
  python studio.py round song.json --output round_2 --config ~/.music-skill/local-config.json --previous round_1
  python studio.py render song.json --output render_final --config ~/.music-skill/local-config.json
  python studio.py analyze render_final
Each command's own help and example: python studio.py COMMAND --help"""

# 0.10: a command that needs the configuration takes it from MUSIC_SKILL_CONFIG when --config is left out, so a later
# session finds the one the user recorded without searching the disk; start too, which finds its parts' presets in it.
# review, analyze and compare use a configuration only when it is named, as before.
CONFIG_FROM_ENVIRONMENT = ('round', 'render', 'audition', 'instruments', 'video', 'doctor', 'start')
CONFIG_HELP = 'the renderer configuration bootstrap.py wrote (default: the file MUSIC_SKILL_CONFIG names)'


class Parser(argparse.ArgumentParser):
    """argparse's parser, its errors in the form every other error takes (SKILL.md: Errors go to stderr as `ERROR: ...`
    with exit code 2): the usage, then one line `ERROR: ...`.  The commands' parsers are of this class too
    (add_subparsers makes them of the parser's own class)."""
    def error(self,message):
        self.print_usage(sys.stderr)
        print(f'ERROR: {self.prog}: {files.one_line(message)}',file=sys.stderr);sys.exit(2)

def build_parser():
    """The command line: the commands an agent runs most first, each with a one-line description, an example, and help
    for every option (0.8 step 2.4, after the Command Line Interface Guidelines: examples first, every flag described)."""
    parser=Parser(description=__doc__+'\n\n'+EXAMPLES,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=parser.add_subparsers(dest='command',required=True,metavar='COMMAND')
    def command(name,help,example,**kw):
        return sub.add_parser(name,help=help,description=f'{help}.\n\nExample:\n  {example}',formatter_class=argparse.RawDescriptionHelpFormatter,**kw)
    project=lambda cmd:cmd.add_argument('project',type=Path,help='the project file (JSON)')
    as_json=lambda cmd:cmd.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    st=command('start','Start a piece: in its folder (made if missing; its brief and words may be there), a compose.py that writes song.json through musiclib.builder (sections and parts named, a performance entry for every note), and that song.json, validated',
               'python studio.py start harbour --title "Harbour Lights" --tempo 96 --section verse:8 --section chorus:8 --part "piano harmony vcsl 0:0" --part "lead melody iowa_winds 0:73" --config ~/.music-skill/local-config.json')
    st.add_argument('folder',type=Path,help="the piece's folder: a new one, or one with its brief and words but no compose.py or song.json");st.add_argument('--title',required=True,help="the piece's title")
    st.add_argument('--section',action='append',required=True,metavar='ID:BARS',help='a section and its bars, in order (repeatable)')
    st.add_argument('--part',action='append',required=True,metavar='"ID ROLE [INSTRUMENT]"',help='a part: its id, its role (melody, harmony, bass, drums, ...) and words that find its preset in the configured banks, as studio.py instruments takes them, or a sound as audition --sounds names one: surge:<id> (studio.py sounds), synth:<preset>, soundfont:<bank>:<bank number>:<program> (repeatable)')
    st.add_argument('--tempo',type=float,default=100,help='quarter-note BPM (default 100)');st.add_argument('--meter',default='4/4',help='beats/beat unit (default 4/4)')
    st.add_argument('--config',type=Path,help="the renderer configuration bootstrap.py wrote: needed to find the parts' presets (default: the file MUSIC_SKILL_CONFIG names)")
    cmd=command('validate','Check a project against the schema; print its size and any unknown field with the nearest known name','python studio.py validate song.json');project(cmd)
    cmd=command('review','Ask the questions a score raises (range, collisions, form, the plan), each with where it is; write score_review.json','python studio.py review song.json --output review_1')
    project(cmd);cmd.add_argument('--output',type=Path,required=True,help='a new folder for the review')
    cmd.add_argument('--config',type=Path,help='also check each note against the samples of its bank');as_json(cmd)
    rnd=command('round','One revision round: validate, review, a draft render, analyze it and compare it with the previous round, each with a short summary',
                'python studio.py round song.json --output round_2 --config ~/.music-skill/local-config.json --previous round_1')
    rnd.add_argument('project',type=Path,help='the project file (JSON)');rnd.add_argument('--output',type=Path,required=True,help='a new folder for the round: review/, render/ and round.json')
    rnd.add_argument('--config',type=Path,help=CONFIG_HELP);rnd.add_argument('--previous',type=Path,help="the previous round's folder (or a render folder) to compare with")
    rnd.add_argument('--cache',type=Path,help='default: the folder cache next to the round, which every round shares')
    rnd.add_argument('--jobs',type=int,help='parts rendered at once (as render --jobs)')
    rnd.add_argument('--span',action='append',default=[],metavar='NAME:FIRST-LAST',help='also analyze bars FIRST to LAST (1-based) under NAME; repeatable')
    rnd.add_argument('--reference',help='analyze against a reference: a name in references/tonal-references.json, a render or round folder, or a WAV file')
    rnd.add_argument('--clip',type=Path,metavar='MP3',help='with --previous: an old-then-new MP3 of 8 seconds around the first change in the master, both at the same loudness')
    rnd.add_argument('--json',action='store_true',help="print round.json instead of the steps' summaries")
    cmd=command('render','Render, mix and master a project into a new folder: stems, buses, the master as WAV, FLAC and MP3, MIDI, and a game loop where asked',
                'python studio.py render song.json --output render_final --config ~/.music-skill/local-config.json')
    project(cmd);cmd.add_argument('--output',type=Path,required=True,help='a new folder for the render');as_json(cmd)
    cmd.add_argument('--config',type=Path,help=CONFIG_HELP)
    cmd.add_argument('--cache',type=Path,help="the parts' synthesis cache (default: the folder cache next to the output), shared by renders of the piece")
    cmd.add_argument('--resume',action='store_true',help='take up a render of the same project that stopped, in its own folder')
    cmd.add_argument('--jobs',type=int,help='parts rendered at once (default: one per processor, at most 8, each waiting for its share of the free memory; the result is the same)')
    cmd.add_argument('--draft',action='store_true',help='for revising: the same audio, stems, buses and returns, without master.flac, the MP3 loudness check and a loop\'s Ogg copies and layers; deliver a full render')
    analyze=command('analyze','Measure a finished render: section levels and spectrum, stereo, stem levels, lead presence','python studio.py analyze render_final --span chorus:17-24')
    analyze.add_argument('render',type=Path,help='a render folder');analyze.add_argument('--output',type=Path,help='JSON report (default: <render>/analysis.json)')
    analyze.add_argument('--span',action='append',default=[],metavar='NAME:FIRST-LAST',help='also measure bars FIRST to LAST (1-based) under NAME; repeatable')
    analyze.add_argument('--reference',help='compare the whole master with a reference: a name in references/tonal-references.json, a render folder or a WAV file')
    analyze.add_argument('--config',type=Path,help='needed with a WAV reference: FFmpeg converts and meters it')
    analyze.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    cmp=command('compare','Compare two renders: what the project changed, which parts were synthesized again, and where each stem, bus, return, the premix and the master changed',
                'python studio.py compare render_1 render_2')
    cmp.add_argument('before',type=Path,help='the earlier render folder');cmp.add_argument('after',type=Path,help='the later render folder')
    cmp.add_argument('--output',type=Path,help='JSON report (default: <after>/compare_<before folder>.json)')
    cmp.add_argument('--differences',type=Path,metavar='FOLDER',help='a new folder for every changed file as after minus before, level-matched: the change alone')
    cmp.add_argument('--clip',type=Path,metavar='MP3',help='an old-then-new MP3 of 8 seconds around the first change in the master, both at the same loudness (needs --config)')
    cmp.add_argument('--config',type=Path,help='needed with --clip: FFmpeg measures and encodes it')
    cmp.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    cmd=command('revise','Change one note (pitch, velocity or length) into a new project file, recorded in its revision history',
                'python studio.py revise song.json --track lead --note lead_12 --pitch 67 --output song_r2.json')
    project(cmd);cmd.add_argument('--track',required=True,help='the part, by its id');cmd.add_argument('--note',required=True,help='the note, by its id')
    cmd.add_argument('--pitch',type=int,help='the new MIDI pitch');cmd.add_argument('--velocity',type=int,help='the new MIDI velocity');cmd.add_argument('--duration',type=float,help='the new length in beats')
    cmd.add_argument('--output',type=Path,required=True,help='a new project file')
    aud=command('audition',"Play one part's passage on several sounds in turn: the same notes in the same mix, at one loudness, with each sound's measured brightness",
                'python studio.py audition song.json --track lead --sounds surge:juno_60_strings,synth:warm_pad --bars 9-12 --output aud_lead --config ~/.music-skill/local-config.json')
    aud.add_argument('project',type=Path,help='the project file (JSON)');aud.add_argument('--track',required=True,help='the part to audition, by its id')
    aud.add_argument('--sounds',required=True,help='comma-separated: surge:<preset>, synth:<preset>, soundfont:<bank>:<bank number>:<program>; the part as written plays first')
    aud.add_argument('--bars',required=True,metavar='FIRST-LAST',help='the passage, 1-based, at most 16 bars')
    aud.add_argument('--output',type=Path,required=True,help='a new folder for the audition');aud.add_argument('--config',type=Path,help=CONFIG_HELP)
    aud.add_argument('--cache',type=Path,help="the parts' synthesis cache (as render --cache)")
    aud.add_argument('--solo',action='store_true',help='the part alone instead of in its passage with the others')
    aud.add_argument('--jobs',type=int,help='parts rendered at once in each version (as render --jobs)')
    aud.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    snd=command('sounds','Search the Surge XT catalog: every factory and third-party patch, by role, measured character, name and source, for a shortlist to audition',
                'python studio.py sounds --role pad --character dark,slow --seed 412')
    snd.add_argument('--role',help='lead, brass, pad, chords, keys, pluck, bass, sequence, fx, percussion or other')
    snd.add_argument('--character',default='',help='comma-separated words the measured character must contain: dark, warm, mid, bright; fast, soft, slow; dry, short, long; mono, narrow, wide; steady, moving (between playings); what a held note does: decays, darkens, brightens, pitch blip, pitch steps, level swings, pitch swings, brightness swings, inharmonic (quote a list that holds a space)')
    snd.add_argument('--centroid',help='a range of the probe note\'s spectral centroid in Hz, LOW-HIGH with either end open: 600-900, 1500-, -400')
    snd.add_argument('--attack',help='a range of its attack in seconds (the time to half its peak level), LOW-HIGH with either end open: 0.1-0.3, -0.03')
    snd.add_argument('--without',default='',help='comma-separated words of the measured character to leave out: a patch with any of them is not listed, nor one whose figure for a word of a held note could not be read ("decays,level swings" for a held pad, quoted)')
    snd.add_argument('--name',help='text in the patch name or category');snd.add_argument('--source',help='"factory" or a designer')
    snd.add_argument('--limit',type=int,default=25,help='the most patches shown (default 25)');snd.add_argument('--all',action='store_true',help='also patches flagged silent, MPE, microtonal or off pitch')
    snd.add_argument('--id',help='one catalog patch in full: its measurement and what its mod wheel and macros move')
    snd.add_argument('--seed',type=int,help="the piece's seed (musiclib.blocks.seed(title)): which patch each band of the spread shows, so two pieces see different ones")
    snd.add_argument('--json',action='store_true',help='print the full JSON instead of one line a patch (--id always prints it)')
    ins=command('instruments','Find presets in the configured banks by words of their name, family or bank: the bank and program a part takes, the keys their samples cover, their velocity layers',
                'python studio.py instruments violin --config ~/.music-skill/local-config.json')
    ins.add_argument('words',nargs='+',help='words of the preset name (violin), a General MIDI family (strings, brass, reed) or a bank (vsco), or a bank number and program (0:41); where no preset has them all, those that have the most are listed; a word that no preset has is refused, with the nearest word where one is near')
    ins.add_argument('--config',type=Path,help=CONFIG_HELP);ins.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    stl=command('still',"Draw a render's piano roll at one moment as a PNG: the notes as played, coloured by what the part does, every part named in the legend (needs Pillow)",
                'python studio.py still render_final --at 42 --output roll_42.png')
    stl.add_argument('render',type=Path,help='a render folder (the --output of studio.py render)');stl.add_argument('--at',type=float,required=True,help='the moment, in seconds from the start')
    stl.add_argument('--output',type=Path,required=True,help='a new PNG file');stl.add_argument('--size',default='1280x720',help='WIDTHxHEIGHT in pixels, even numbers (default 1280x720)')
    vid=command('video',"Make a render's piano roll into a video with its master as the sound: WebM (VP9, Opus) by default, MP4 (H.264, AAC) with --mp4, kept under a size (needs Pillow)",
                'python studio.py video render_final --output roll.webm --config ~/.music-skill/local-config.json')
    vid.add_argument('render',type=Path,help='a render folder (the --output of studio.py render)');vid.add_argument('--output',type=Path,required=True,help='a new .webm file, or .mp4 with --mp4')
    vid.add_argument('--config',type=Path,help='the configuration bootstrap.py wrote: its FFmpeg encodes the video (default: the file MUSIC_SKILL_CONFIG names)')
    vid.add_argument('--mp4',action='store_true',help='MP4 with H.264 and AAC, for the widest playback, where the FFmpeg has those encoders')
    vid.add_argument('--size-mb',type=float,default=10,help="the size to stay under, in MB (default 10: GitHub's limit for a video on its free plans)")
    vid.add_argument('--fps',type=int,default=30,help='frames a second (default 30)');vid.add_argument('--size',default='1280x720',help='WIDTHxHEIGHT in pixels, even numbers (default 1280x720)')
    prof=command('profile','Describe the written score per part and section: density, register, intervals, rhythm, repetition','python studio.py profile song.json --output profile.json')
    prof.add_argument('project',type=Path,help='the project file (JSON)');prof.add_argument('--output',type=Path,help='full JSON (without it, the full profile is printed)')
    wrd=command('words',"Draw the twelve words a piece associates from, once, and keep them beside the project (association.json); with --own, the user's words in their place",
                'python studio.py words my_piece')
    wrd.add_argument('folder',type=Path,help='the project folder')
    wrd.add_argument('--seed',type=int,help='make a given draw again')
    wrd.add_argument('--own',help="the user's own words or short phrases, separated by commas, in place of a draw")
    wrd.add_argument('--none',metavar='REASON',help='record that this piece associates from no words, and why (the user asked for none)')
    wrd.add_argument('--json',action='store_true',help='print the record instead of the summary')
    cmd=command('export-midi','Write the score as a standard MIDI file (type 1), a track for each part','python studio.py export-midi song.json --output song.mid')
    project(cmd);cmd.add_argument('--output',type=Path,required=True,help='a new MIDI file')
    inspect=command('inspect-midi','Count what a MIDI file holds: its tracks and notes, notes left open, note-offs without a note, and its SHA-256','python studio.py inspect-midi song.mid')
    inspect.add_argument('file',type=Path,help='a MIDI file');inspect.add_argument('--output',type=Path,help='also write the listing as JSON here')
    cln=command('clean',"List, or with --remove remove, the piece's render, round and review folders other than those kept, its auditions' renders and caches, and the cache entries the kept renders do not use",
                'python studio.py clean my_piece --keep my_piece/render_final --keep my_piece/round_3')
    cln.add_argument('folder',type=Path,help="the piece's folder")
    cln.add_argument('--keep',type=Path,action='append',required=True,help='a render or round folder that stays (repeatable): the final render and the previous round')
    cln.add_argument('--remove',action='store_true',help='remove what the list names (without it, nothing is removed)')
    cln.add_argument('--json',action='store_true',help='print the full JSON instead of the summary')
    doctor=command('doctor','Check a renderer configuration: each program and bank there, by path and SHA-256','python studio.py doctor --config ~/.music-skill/local-config.json')
    doctor.add_argument('--config',type=Path,help='the configuration to check (default: the file MUSIC_SKILL_CONFIG names)')
    configure=command('configure','Write a configuration from a FluidSynth, an FFmpeg and a SoundFont of your own (bootstrap.py writes the usual one)',
                      'python studio.py configure --fluidsynth fluidsynth.exe --ffmpeg ffmpeg.exe --soundfont bank.sf2 --output config.json')
    for arg,what in (('fluidsynth','the FluidSynth program'),('ffmpeg','the FFmpeg program'),('soundfont','the default SoundFont'),('output','a new configuration file')):
        configure.add_argument('--'+arg,type=Path,required=True,help=what)
    addsf=command('add-soundfont','Write a new config that adds a named SoundFont to an existing one',
                  'python studio.py add-soundfont --config ~/.music-skill/local-config.json --path harp.sf2 --name harp --license CC0-1.0 --source "the publisher\'s page" --version 1 --output with-harp.json')
    for arg,what in (('config','the configuration to add to'),('path','the SoundFont file'),('output','a new configuration file')):addsf.add_argument('--'+arg,type=Path,required=True,help=what)
    for arg,what in (('name','the name a part chooses it by (lower-case letters, digits and underscores; not "default")'),('license','its licence, as its publisher states it'),
                     ('source','where it came from'),('version','its version')):addsf.add_argument('--'+arg,required=True,help=what)
    return parser


def config_from_environment(args):
    """--config left out of a command that takes it from the environment: the file MUSIC_SKILL_CONFIG names (an absolute
    path; a relative one is refused), said in a NOTE line on stderr.  A command that cannot run without a configuration and has neither stops as a missing option
    stops (an ERROR line, exit 2); start without one goes on as before: a Surge patch or a built-in preset needs none, and a
    part that names a SoundFont preset is refused."""
    from musiclib.homepath import at_home
    if getattr(args,'config',None) is not None:args.config=at_home(args.config)  # ~/ as the user's home, as a shell would (~/.music-skill/)
    if args.command not in CONFIG_FROM_ENVIRONMENT or args.config is not None:return
    named=os.environ.get('MUSIC_SKILL_CONFIG','')   # as it is: a file name may begin with a space
    if named:
        path=at_home(named)
        if not path.is_absolute():
            # A relative name would be read from each command's working folder, so a project's folder could choose the
            # configuration, and so the programs that run (the Astra review of 0.10's step 2)
            print(f'ERROR: studio.py {args.command}: MUSIC_SKILL_CONFIG names a relative path ({files.one_line(named)}): give the '
                  "configuration's absolute path, so that a command finds the same file in every folder",file=sys.stderr);sys.exit(2)
        args.config=path
        print(f'NOTE: --config {files.one_line(str(path))} (from MUSIC_SKILL_CONFIG)',file=sys.stderr,flush=True)
    elif args.command!='start':
        print(f'ERROR: studio.py {args.command}: the following arguments are required: --config (the configuration bootstrap.py wrote, '
              'or MUSIC_SKILL_CONFIG naming it)',file=sys.stderr);sys.exit(2)


def config_beside(args):
    """A configuration inside the folder of the project, render or piece a command works on may have come with it, and a
    configuration names the programs that run (its tools are checked only against its own hashes): said in a WARNING line
    on stderr, not refused, as a user may keep their own there (the security check of 0.10.0)."""
    cfg=getattr(args,'config',None)
    if cfg is None:return
    try:cfg=Path(cfg).resolve()
    except (OSError,RuntimeError):return
    for name in ('project','render','folder'):
        given=getattr(args,name,None)
        if given is None:continue
        try:place=Path(given).resolve()
        except (OSError,RuntimeError):continue
        if (place if place.is_dir() else place.parent) in cfg.parents:
            print(f'WARNING: studio.py {args.command}: the configuration {files.one_line(str(cfg))} lies in the folder of {files.one_line(str(given))}. '
                  'A configuration names the programs that run: use the one the setup wrote on this machine or one the user names, '
                  'not one that came with a piece or a download (SKILL.md).',file=sys.stderr,flush=True)
            return


def main(args):
    def fresh(path,source=None):
        # Taken in any form, a dangling link included (Path.exists follows links): outputs never overwrite.
        files.fresh(path)
        if source is not None and path.resolve()==Path(source).resolve():raise ValueError('The output would replace its own input')
    if args.command=='configure':
        if files.occupied(args.output):raise ValueError('Choose a new configuration path')
        from musiclib import sf2
        from musiclib.bankcheck import refuse_unsafe
        sf2.read(args.soundfont);refuse_unsafe(args.soundfont)  # as add-soundfont: a bank whose tables do not hold together, or that FluidSynth is not safe with, is refused before it is configured
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
        from musiclib.bankcheck import refuse_unsafe
        bank=sf2.read(args.path);refuse_unsafe(args.path)
        fonts[args.name]={'path':str(args.path.resolve()),'sha256':file_hash(args.path),'license':args.license,'source':args.source,'version':args.version,'presets':[[p['bank'],p['program'],p['name']] for p in bank['presets']]}
        save_json(args.output,base,new=True);print('Saved',args.output,'with',len(bank['presets']),'presets in',args.name);return
    if args.command=='doctor':
        from musiclib.audio import load_config,run
        import numpy,tempfile
        c=load_config(args.config,all_banks=True)
        from musiclib.bankcheck import refuse_unsafe
        for entry in [c['soundfont'],*c.get('soundfonts',{}).values()]:refuse_unsafe(entry['path'])
        print('Python',sys.version.split()[0],'NumPy',numpy.__version__)
        # The version checks log into a temporary folder of their own: doctor writes nothing beside the configuration.
        with tempfile.TemporaryDirectory(prefix='doctor-') as logs:
            for key in ('fluidsynth','ffmpeg'):
                output=run([c[key]['path'],'--version' if key=='fluidsynth' else '-version'],logs,key,30)
                print(files.one_line(output.splitlines()[0]))
        from musiclib.loop import has_vorbis
        print('Ogg Vorbis for game loops:','yes' if has_vorbis(c) else 'no, this FFmpeg has no libvorbis encoder (references/setup.md)')
        for name,entry in [('default',c['soundfont'])]+sorted(c.get('soundfonts',{}).items()):
            print('SoundFont',*(files.one_line(str(x)) for x in (name,'|',entry.get('version',''),'|',entry.get('license',''))))   # text a configuration holds
        # Surge XT is optional: without it a synth part plays its patch's built-in fallback, and nothing said so here.
        surge,host=c.get('surge'),c.get('pedalboard')
        from musiclib.surge import installed as surge_installed
        if surge and host and not surge_installed(c):
            # Configured, and the plugin or pedalboard is not where the configuration says: a render plays the
            # fallbacks, and this line gave the version and PASS (the review of 0.7's code, F09).
            print('Surge XT: configured, but its plugin or pedalboard is not at the configured path; synth parts written for it play their built-in fallbacks. Run bootstrap.py again (references/setup.md)')
        elif surge and host:
            catalog=surge.get('catalog') or surge.get('patches')
            count=sum(1 for _,_,names in os.walk(catalog) for n in names if n.lower().endswith('.fxp')) if catalog and os.path.isdir(catalog) else 0
            print('Surge XT',*(files.one_line(str(x)) for x in (surge.get('version',''),'|',surge.get('license',''),'|',f'{count} patches' if count else 'no patch folder found','| host: pedalboard',host.get('version',''))))   # text a configuration holds
        else:
            print('Surge XT: not set up; synth parts written for it play their built-in fallbacks (references/setup.md)')
        try:
            from PIL import __version__ as pillow
            import re
            major=re.match(r'(\d+)\.(\d+)',pillow)   # a sized default font (roll.py) came in 10.1
            print('Pillow',pillow,'(still and video)' if major and (int(major[1]),int(major[2]))>=(10,1) else '(still and video need 10.1 or newer: python -m pip install --upgrade pillow)')
        except ImportError:
            print('Pillow: not installed; only still and video need it (python -m pip install pillow)')
        print('PASS: paths and pinned checksums verified; no malware scan implied');return
    if args.command=='words':
        from musiclib import association
        if not args.folder.is_dir():raise ValueError(f'{args.folder}: the project folder (it holds the draw; make it first)')
        record,made=association.keep(str(args.folder),seed=args.seed,own=args.own,none=args.none)
        print(json.dumps(record,ensure_ascii=True) if args.json else association.describe(record,made,str(args.folder/'association.json')));return
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
    if args.command=='start':
        from musiclib.starter import start
        print(start(args.folder,args.title,args.section,args.part,args.tempo,args.meter,args.config));return
    if args.command=='instruments':
        from musiclib import instruments
        found=instruments.search(args.config,args.words)
        print(json.dumps(found,ensure_ascii=True,indent=1) if args.json else instruments.summary(found));return
    if args.command in ('still','video'):
        from musiclib import roll
        w,x,h=args.size.partition('x')
        if not (x and w.isdigit() and h.isdigit()):raise ValueError(f'--size {args.size!r}: WIDTHxHEIGHT in pixels, e.g. 1280x720')
        if args.command=='still':print(roll.still(args.render,args.at,args.output,int(w),int(h)));return
        print(roll.video(args.render,args.output,args.config,args.mp4,args.size_mb,args.fps,int(w),int(h)));return
    if args.command=='sounds':
        from musiclib.sounds import describe
        from musiclib.shortlist import search   # sounds.search with --without (0.10), outside the synthesis closure
        def span(text,what,examples):
            if text is None:return None
            lo,sep,hi=text.partition('-')
            try:
                if not sep or (not lo and not hi):raise ValueError
                got=(float(lo) if lo else None,float(hi) if hi else None)
                # An end is a plain number of Hz or seconds: finite and not under zero (nan-900, 0-inf and --1 were taken).
                if any(v is not None and not (math.isfinite(v) and v>=0) for v in got):raise ValueError
            except ValueError:
                raise ValueError(f'{what} is a range LOW-HIGH with either end open ({examples}), not {text!r}') from None
            if got[0] is not None and got[1] is not None and got[0]>got[1]:raise ValueError(f'{what}: the lowest is over the highest in {text!r}')
            return got
        found=describe(args.id) if args.id else search(args.role,[w for w in args.character.split(',') if w.strip()],args.name,args.source,args.limit,args.all,args.seed,
                                                       span(args.centroid,'--centroid','Hz: 600-900, 1500-, -400'),span(args.attack,'--attack','seconds: 0.1-0.3, 0.05-, -0.03'),
                                                       [w for w in args.without.split(',') if w.strip()])
        print(json.dumps(found,ensure_ascii=True,indent=1) if args.json or args.id else summary.sounds(found));return
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
    args=build_parser().parse_args();code=0
    config_from_environment(args)
    config_beside(args)
    try:main(args)
    except KeyError as e:
        print('ERROR: missing field',files.one_line(str(e)),file=sys.stderr);code=2
    except (ValueError,OSError,RuntimeError,TimeoutError) as e:
        # (0.9 step 1: an error on a path past Windows' limit, where the system's long paths are off, says so)
        print('ERROR:',files.one_line(str(e)+files.path_limit_hint(e)),file=sys.stderr);code=2  # one line, whatever text it carries (0.8 step 1.6)
    if getattr(args,'project',None):
        # Last of all, after what stdout holds, so that a `| tail` keeps it (0.9.2: one run's tail hid a failed script).
        from musiclib.starter import behind_script
        note=behind_script(args.project)
        if note:
            # On stdout after a summary, as the last line a `| tail` keeps, in PowerShell and Git Bash alike; on stderr where stdout holds JSON.
            summarised=args.command in ('review','round','render','audition') and not args.json
            try:
                sys.stdout.flush();print(note,file=sys.stdout if summarised else sys.stderr,flush=True)
            except OSError:pass
    sys.exit(code)
