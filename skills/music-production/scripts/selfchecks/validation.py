"""selfcheck.py's checks of one area (0.8 step 1.8). The project model: the clock, validation and its limits, ids and text, messages, the JSON read and printed, the commands' help.

Each check is defined in define(S), closed over the names it shares with the others (S: selfcheck.checks'
work folder, configuration, judging helpers and bank fixture, and with a configuration the example render's
project, cache and render), and selfcheck runs it in its place in one order (ROSTER).  Paths are the scripts
folder's (SCRIPTS), as they were when these checks lived in selfcheck.py."""
import copy
import json
import os
from make_example import example
from musiclib.model import Clock, save_json, validate
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]   # the skill's scripts folder, selfcheck.py's own


def define(S):
    """The checks of this area, {name: function}; those of the configuration's block only with one."""
    config, rejects, work = S['config'], S['rejects'], S['work']
    def clock_roundtrip():
        p=example();p['clock']={'bars':8,'meter':[6,8],'tempo':[[0,99],[5.5,76],[12,112],[22,68]],'tail_seconds':3};c=Clock(p)
        for beat in [0,.125,5.49,5.5,5.501,11.9,12,22,24]:assert abs(c.beat(c.seconds(beat))-beat)<1e-9
        assert c.beats_per_bar==3
        return {'quarter_beats_per_6_8_bar':3,'tested_breakpoints':9}
    def invalid():
        p=example();p['tracks'][0]['performance']['notes'].pop(next(iter(p['tracks'][0]['performance']['notes'])));rejects(lambda:validate(p))
        p=example();p['clock']['tempo']=[[0,108],[0,120]];rejects(lambda:validate(p))
        p=example();p['tracks'][2]['instrument']={'harmonics':100000};rejects(lambda:validate(p))
        p=example();p['tracks'][0]['notes'][0]['pitch']=128;rejects(lambda:validate(p))
        # A key struck twice at once is found by validate, before any render, with both notes and where they are.
        p=example();t=p['tracks'][0];n=copy.deepcopy(t['notes'][0]);n['id']+='_again';t['notes'].append(n)
        t['performance']['notes'][n['id']]=dict(t['performance']['notes'][t['notes'][0]['id']])
        try:
            validate(p);raise AssertionError('a key struck twice at once passed validation')
        except ValueError as e:
            assert t['notes'][0]['id'] in str(e) and n['id'] in str(e) and ' bar ' in str(e),str(e)
        # A phaser's rate is FFmpeg aphaser's speed, 0.1 to 2 Hz: outside it a project passed and its render failed.
        for rate,ok in ((.05,False),(.1,True),(2,True),(2.5,False)):
            p=example();p['tracks'][0]['mix']['effects']=[{'type':'phaser','rate_hz':rate,'depth':.5}]
            if ok:validate(p)
            else:rejects(lambda:validate(p))
        # The text review reads, of another type, is refused before review stops on it (found by GPT Pro's third review).
        for change in (lambda p:p.__setitem__('brief',{'mood':'warm'}),lambda p:p.__setitem__('decisions',None),
                       lambda p:p['tracks'][0]['notes'][0].__setitem__('phrase',['A']),lambda p:p['tracks'][0].__setitem__('role',['melody'])):
            p=example();change(p);rejects(lambda p=p:validate(p))
        # A project, or its clock, mix, tracks, sections, tempo, harmony, notes or performance, of another JSON type is
        # refused with its place, and any other field of the wrong type as that: they raised AttributeError or TypeError
        # and stopped the command (found by CI on Python 3.14, which parsed a deeply nested list).
        for q in ([],'x',1,None):rejects(lambda q=q:validate(q))
        first=lambda p:p['tracks'][0]['notes'][0]['id']
        for change,place in ((lambda p:p.__setitem__('clock',[]),'clock'),(lambda p:p.__setitem__('mix','x'),'mix'),
                             (lambda p:p.__setitem__('tracks','x'),'tracks'),(lambda p:p.__setitem__('tracks',[1]),'track'),
                             (lambda p:p.__setitem__('sections',[1]),'section'),(lambda p:p['clock'].__setitem__('tempo',[1]),'tempo'),
                             (lambda p:p.__setitem__('harmony',[1]),'harmony'),(lambda p:p['tracks'][0].__setitem__('notes',[1]),'note'),
                             (lambda p:p['tracks'][0].__setitem__('performance',[]),'performance'),
                             (lambda p:p['tracks'][0]['performance'].__setitem__('notes',[]),'performance.notes'),
                             (lambda p:p['tracks'][0].__setitem__('mix',[]),'mix'),
                             (lambda p:p['tracks'][0]['performance']['notes'].__setitem__(first(p),1),'performance.notes'),
                             (lambda p:p['tracks'][0]['performance'].__setitem__('cc',[1]),'wrong type'),
                             (lambda p:p['tracks'][0].__setitem__('range',5),'wrong type')):
            p=example();change(p)
            try:validate(p);raise AssertionError(f'{place} of the wrong type passed validation')
            except ValueError as e:assert place in str(e),str(e)
        # A revision history of another type (revise stopped on it) and a huge integer in a small file (it raised
        # OverflowError) are refused with a reason.  (Found by GPT Pro's fifth review of 0.4.0.)
        p=example();p['revision_history']={};rejects(lambda:validate(p))
        p=example();p['clock']['bars']=10**400;rejects(lambda:validate(p))
        return {'invalid_cases_rejected':31}
    def expressive_fields():
        p=example();t=p['tracks'][1];validate(p)
        t['performance']['dynamics']=[[0,20],[8,110]];t['performance']['legato']={'mode':'crossfade','crossfade_ms':120};validate(p)
        t['mix']['depth_m']=6;p['mix'].update(chain='bus',dynamics='wide',range_lu=12);validate(p)
        for bad in (lambda q:q['tracks'][1]['performance'].update(dynamics=[[4,20],[2,110]]),lambda q:q['tracks'][1]['performance']['legato'].update(crossfade_ms=900),
                    lambda q:q['tracks'][1]['performance'].update(cc=[[0,1,64]]),lambda q:q['tracks'][1]['mix'].update(depth_m=12),
                    lambda q:q['mix'].update(dynamics='glue'),lambda q:q.update(loop={'start_bar':0}),lambda q:q['mix'].update(chain='room')):
            q=copy.deepcopy(p);bad(q);rejects(lambda:validate(q))
        return True
    def validation_edges():
        # Limits validate holds, at their edges, with the reason it gives.  Two mutants of model.py lived through every
        # check (0.8's mutation analysis, 2026-11-15): the SoundFont name test joined by `and` (a name on another engine,
        # or one with capitals, passed), and the loud mix's LUFS ceiling given to the normal one.  With them, the
        # additive instrument's limits, beside which 0.8's step 1 adds its own.  The 0.7.0 limits are written here as
        # data, apart from the code.
        refusals=[]
        def refused(q,words):
            try:validate(q)
            except ValueError as e:
                assert words in str(e),(words,str(e));refusals.append(words);return
            raise AssertionError(f'validated: {words}')
        base=example();validate(base)
        lead=next(i for i,t in enumerate(base['tracks']) if t['engine']=='additive')
        piano=next(i for i,t in enumerate(base['tracks']) if t['engine']=='soundfont' and not t.get('drums'))
        limits={'harmonics':(1,32),'spectral_tilt':(.7,3),'attack_ms':(1,500),'release_ms':(5,2000),'glide_ms':(0,200),'cutoff_hz':(100,12000),
                'vibrato_depth_cents':(0,100),'vibrato_rate_hz':(2,9),'vibrato_delay_ms':(0,1000)}
        def instrument(**cfg):
            q=copy.deepcopy(base);q['tracks'][lead]['instrument']=cfg;return q
        for name,(lo,hi) in limits.items():
            step=1 if name=='harmonics' else (hi-lo)*1e-6
            validate(instrument(**{name:lo}));validate(instrument(**{name:hi}))
            refused(instrument(**{name:lo-step}),'instrument '+name);refused(instrument(**{name:hi+step}),'instrument '+name)
        refused(instrument(harmonics=12.0),'write 12, not 12.0')
        validate(instrument(detune_cents=[-40,40]));validate(instrument(detune_cents=[0]*7))
        for voices in ([],[0]*8,'0'):refused(instrument(detune_cents=voices),'synth voices')
        refused(instrument(detune_cents=[40.5]),'detune cents');refused(instrument(odd_only=1),'odd_only must be boolean')
        # A SoundFont named for a part: lower-case letters, digits and underscores, a letter first, at most 48, and only
        # on the soundfont engine.
        def font(i,name):
            q=copy.deepcopy(base);q['tracks'][i]['soundfont']=name;return q
        for name in ('a','my_bank_2','a'+'0'*47):validate(font(piano,name))
        for name in ('A','1a','_a','a-b','','a'*49,'bank\x1b',5,None):refused(font(piano,name),'soundfont must name')
        refused(font(lead,'a'),'soundfont must name')
        # The master's LUFS: -30 to -10, and to -8 for a loud mix, which needs the bus chain without wide dynamics.
        def mix(**m):
            q=copy.deepcopy(base);q['mix'].update(m);return q
        for lufs in (-30,-10):validate(mix(target_lufs=lufs));validate(mix(loudness='normal',target_lufs=lufs))
        for lufs in (-30.01,-9.99):refused(mix(target_lufs=lufs),'master LUFS')
        for lufs in (-30,-8):validate(mix(loudness='loud',chain='bus',target_lufs=lufs))
        for lufs in (-30.01,-7.99):refused(mix(loudness='loud',chain='bus',target_lufs=lufs),'master LUFS')
        refused(mix(loudness='loud',target_lufs=-12),'needs the bus chain');refused(mix(loudness='loud',chain='bus',dynamics='wide'),'needs the bus chain')
        refused(mix(loudness='quiet'),'must be "normal" or "loud"')
        # Four more edges a second mutation sample found unpinned (2026-11-15): the room's decay, a rubato span that
        # starts past the piece's last beat, portamento over more than an octave, and a reverse part's 64 notes.
        for room in (.2,4):validate(mix(room_seconds=room))
        for room in (.19,4.01):refused(mix(room_seconds=room),'room decay')
        beats=base['clock']['bars']*base['clock']['meter'][0]*4/base['clock']['meter'][1]
        def rubato(spans):
            q=copy.deepcopy(base);q['clock']['rubato']={'spans':spans};return q
        validate(rubato([[beats-1,beats+1,.9]]));refused(rubato([[beats+.5,beats+1,.9]]),'rubato span from beat')
        def legato(**leg):
            q=copy.deepcopy(base);q['tracks'][piano]['performance']['legato']={'mode':'crossfade',**leg};return q
        validate(legato(max_interval=12,portamento_ms=50));validate(legato(max_interval=13))
        refused(legato(max_interval=13,portamento_ms=50),'portamento covers intervals up to 12')
        def reversed_part(count):
            q=copy.deepcopy(base);t=q['tracks'][piano];t['reverse']=True;t['performance'].pop('dynamics',None)
            if (t['performance'].get('legato') or {}).get('mode')=='crossfade':t['performance'].pop('legato')
            step=beats/65
            t['notes']=[{'id':f'rv{k}','on':round(k*step,4),'duration':round(step*.9,4),'pitch':60+k%12} for k in range(count)]
            t['performance']['notes']={f'rv{k}':{'velocity':80} for k in range(count)};return q
        validate(reversed_part(64));refused(reversed_part(65),'at most 64 notes')
        return {'instrument_limits':len(limits),'refusals':len(refusals)}
    def effects_capped_per_part():
        # 0.8 step 1.3 (design-0.8.md, Part C): a part takes at most 8 effects, counted as listed, repeats too, before
        # each is checked, and the ninth is refused naming the part and the cap; the cap is each part's, so two parts
        # of 8 pass.  0.7.0's forms keep their outcomes: no effects, [], "" and {} hold none; null and false are
        # refused as a field of the wrong type.
        from musiclib.model import MAX_EFFECTS
        assert MAX_EFFECTS==8
        chorus,phaser,crush={'type':'chorus','depth':.3},{'type':'phaser','rate_hz':.5,'depth':.5},{'type':'bitcrush','bits':8}
        def with_effects(fx,other=None):
            q=example();a=q['tracks'][0]
            if fx=='omitted':a['mix'].pop('effects',None)
            else:a['mix']['effects']=fx
            if other is not None:q['tracks'][2]['mix']['effects']=other
            before=json.dumps(q,sort_keys=True);validate(q)
            assert json.dumps(q,sort_keys=True)==before,fx   # validation changes nothing ("" and {} stay as written)
            return q
        for fx in ('omitted',[],'',{},[chorus],[chorus]*7,[chorus,phaser,crush,crush,chorus,phaser,chorus,crush],[crush]*8):
            with_effects(fx)
        with_effects([chorus]*8,[phaser]*8)
        for fx in ([chorus]*9,[chorus,phaser,crush]*3,[{'type':'flanger'}]*9):   # counted before each is checked
            q=example();q['tracks'][0]['mix']['effects']=fx;before=json.dumps(q,sort_keys=True)
            try:validate(q);raise AssertionError(f'{len(fx)} effects passed')
            except ValueError as e:assert str(e).startswith('piano: 9 effects') and 'at most 8' in str(e),str(e)
            assert json.dumps(q,sort_keys=True)==before,fx   # nor changed by the refusal
        q=example();q['tracks'][0]['mix']['effects']=[chorus]*8;q['tracks'][2]['mix']['effects']=[phaser]*9;before=json.dumps(q,sort_keys=True)   # a later part's too
        try:validate(q);raise AssertionError('9 effects on a later part passed')
        except ValueError as e:assert str(e).startswith(f"{q['tracks'][2]['id']}: 9 effects") and json.dumps(q,sort_keys=True)==before,str(e)
        for fx in (None,False):
            try:with_effects(fx);raise AssertionError(f'effects {fx!r} passed')
            except ValueError as e:assert 'wrong type' in str(e),str(e)
        return {'cap':MAX_EFFECTS,'accepted':9,'refused':5}
    def strict_projects():
        # A JSON float where MIDI needs an integer (100.0) and a section id that is not text stop in validation, with
        # the place and the value; a misspelt optional field is reported with the name it was probably meant to be.
        p=example();t=p['tracks'][0];n=t['notes'][0]
        t['performance']['notes'][n['id']]['velocity']=100.0
        try:validate(p);raise AssertionError('accepted a float velocity')
        except ValueError as e:assert f'{t["id"]}/{n["id"]} velocity' in str(e) and 'write 100, not 100.0' in str(e),e
        p=example();p['sections'][0]['id']=1;rejects(lambda:validate(p))
        p=example();p['clock']['meter']=[4,4.0];rejects(lambda:validate(p))
        p=example();p['tracks'][0]['mix']['revrb_db']=-12;p['tracks'][0]['performance']['timming_ms']=3;p['mixx']={}
        warnings=validate(p)['warnings']
        assert any("'revrb_db' (did you mean 'reverb_db'?)" in w for w in warnings) and any("'timming_ms'" in w for w in warnings) and any("'mixx'" in w for w in warnings),warnings
        assert validate(example())['warnings']==[]
        p=example();del p['tracks'][0]['performance']['notes'][p['tracks'][0]['notes'][0]['id']]['velocity']
        try:validate(p);raise AssertionError('accepted a note without velocity')
        except ValueError as e:assert 'velocity' in str(e) and p['tracks'][0]['id'] in str(e),e
        return {'warnings':len(warnings)}
    def project_text_stays_text():
        # 0.8 step 1.6 (design-0.8.md, Part C): text from a project can neither begin a line of the tool's own nor
        # reorder how one shows.  Section and note ids refuse a control character (a tab too), the line and paragraph
        # separators and the 12 bidirectional formatting characters (Unicode PropList, Bidi_Control), naming the
        # character by its escape.  Free text (a title, an intent, a role, a plan's section name) is kept as written and
        # printed escaped: one_line escapes the bidirectional characters too, review's table escapes a role before it
        # is composed (a line break there added a line), and every script prints an error as one escaped line.  A ZWJ
        # emoji, Chinese text, a tab, quotes and a backslash stay as they are; the command's JSON (ASCII escapes) and the
        # saved JSON (UTF-8) each give back the exact text.
        import subprocess,sys,unicodedata
        from musiclib import files as fl,summary
        from musiclib.review import review as run_review
        studio=str(SCRIPTS.joinpath('studio.py'))
        bidi=[chr(c) for c in (0x61c,0x200e,0x200f,*range(0x202a,0x202f),*range(0x2066,0x206a))]
        assert len(bidi)==12 and set(bidi)==fl.BIDI_CONTROL
        unsafe=['\x1b','\x07','\r','\n','\t','\x85','\x7f','\u2028','\u2029',*bidi]
        esc=lambda c:c.encode('unicode_escape').decode('ascii')
        kept='\U0001f469\u200d\U0001f3b9 喆乐 "q" \'s\' \\ x'   # a ZWJ emoji, Chinese, quotes, a backslash
        for c in unsafe:
            assert fl.one_line('a'+c+'b')==('a\tb' if c=='\t' else 'a'+esc(c)+'b'),esc(c)
        assert fl.one_line(kept)==kept
        def piece(section=None,note=None,**text):
            p=example()
            if section is not None:p['sections'][0]['id']=section
            if note is not None:
                t=p['tracks'][0];old=t['notes'][0]['id'];t['notes'][0]['id']=note;t['performance']['notes'][note]=t['performance']['notes'].pop(old)
            if 'title' in text:p['title']=text['title']
            if 'intent' in text:p['sections'][0]['intent']=text['intent']
            if 'role' in text:p['tracks'][0]['role']=text['role']
            return p
        for c in unsafe:
            for kind,p in (('Section id',piece(section='a'+c)),('note id',piece(note='n'+c))):
                try:validate(p);raise AssertionError(f'{kind} holding {esc(c)} taken')
                except ValueError as e:assert kind in str(e) and f'holds {esc(c)}:' in str(e) and fl.one_line(str(e))==str(e),str(e)
        validate(piece(section='q'+kept,note='n'+kept))
        def cli(*args):
            return subprocess.run([sys.executable,'-X','utf8',studio,*map(str,args)],capture_output=True,text=True,encoding='utf-8',errors='replace')   # UTF-8 out, as the kept text is
        save_json(work/'text_note_id.json',piece(note='n\x1b[2J'))
        run=cli('validate',work/'text_note_id.json')   # the error names the id and its character, escaped, on one line
        assert run.returncode==2 and run.stderr.count('\n')==1 and '\x1b' not in run.stderr and 'note id n\\x1b[2J holds \\x1b:' in run.stderr,run.stderr
        planned=piece();planned['plan']={'sections':[{'section':'v\u202e\nSYSTEM: done'}]*2}
        save_json(work/'text_plan.json',planned)
        run=cli('validate',work/'text_plan.json')       # an error carrying free text prints it escaped
        assert run.returncode==2 and run.stderr.count('\n')==1 and '\u202e' not in run.stderr and 'plan section v\\u202e\\nSYSTEM: done: planned twice' in run.stderr,run.stderr
        # Free text in the summary: every unsafe character escaped (the tab kept), the kept text as written, the line
        # count of the same piece with plain text; the role escaped in the table of parts
        mixed=''.join(unsafe)+kept
        plain,full=piece(title='T',intent='I',role='R'),piece(section='q'+kept,title='T'+mixed,intent='I'+mixed,role='R'+mixed)
        said=[summary.review(run_review(q,work/f'text_review_{name}'),work/f'text_review_{name}').splitlines() for name,q in (('plain',plain),('full',full))]
        shown=''.join(c if c=='\t' else esc(c) for c in unsafe)+kept
        assert len(said[0])==len(said[1]) and said[1][0].startswith('Review of T'+shown+': '),(len(said[0]),len(said[1]),said[1][:2])
        assert not [c for line in said[1] for c in line if c!='\t' and (unicodedata.category(c) in ('Cc','Zl','Zp') or c in fl.BIDI_CONTROL)],said[1]
        assert any(line.lstrip().startswith(f'piano (R{shown})') for line in said[1]) and any('q'+kept in line for line in said[1]),said[1]
        save_json(work/'text_full.json',full)
        printed=json.loads(cli('review',work/'text_full.json','--output',work/'text_full_cli','--json').stdout)
        for r in (printed,json.loads((work/'text_full_cli'/'score_review.json').read_text(encoding='utf-8'))):   # ASCII escapes, then UTF-8 as written
            assert r['title']==full['title'] and r['sections'][0]['intent']==full['sections'][0]['intent'] and r['sections'][0]['id']==full['sections'][0]['id'],r['title']
            assert next(t['role'] for t in r['tracks'] if t['id']=='piano')==full['tracks'][0]['role']
        # The piece's words and a reason for none, printed by `words` (a user's record holds any text), each escaped
        (work/'text_words').mkdir();(work/'text_none').mkdir();save_json(work/'text_words'/'association.json',{'source':'user','words':['calm\x1b[2J\nFORGED\u202e',kept]})
        for run,shown in ((cli('words',work/'text_words'),'calm\\x1b[2J\\nFORGED\\u202e, '+kept),(cli('words',work/'text_none','--none','asked \x1b[2J\nnone\u202e'),'(asked \\x1b[2J\\nnone\\u202e)')):
            assert run.returncode==0 and shown in run.stdout and not set(run.stdout)&{'\x1b','\u202e'},(run.stdout,run.stderr[-300:])
        # a record found in the folder is told as its record has it, and what is printed is bounded as --own bounds new
        # words, 24 of 60 characters (the security check of 0.10.0)
        (work/'text_many').mkdir();save_json(work/'text_many'/'association.json',{'source':'user','words':[f'word {k} '+'x'*80 for k in range(30)]})
        run=cli('words',work/'text_many');lines=run.stdout.splitlines()
        assert run.returncode==0 and 'its record says' in lines[0] and lines[1].endswith(', and 6 more') and lines[1].count('...')==24,run.stdout[:400]
        # Every exception text a script prints (beside its final error) goes through one_line: an installer's FAILED
        # line carried a download's or an archive's text as it came
        import ast
        def raw(node,name):
            if isinstance(node,ast.Call) and (getattr(node.func,'attr',None)=='one_line' or getattr(node.func,'id',None)=='type'):return False
            return isinstance(node,ast.Name) and node.id==name or any(raw(x,name) for x in ast.iter_child_nodes(node))
        printed_raw=[f'{f.name}:{c.lineno}' for f in sorted(SCRIPTS.glob('*.py'))+sorted((SCRIPTS/'musiclib').glob('*.py')) if f.name!='selfcheck.py'
                     for h in ast.walk(ast.parse(f.read_text(encoding='utf-8'))) if isinstance(h,ast.ExceptHandler) and h.name
                     for c in ast.walk(h) if isinstance(c,ast.Call) and getattr(c.func,'id',None)=='print' and any(raw(a,h.name) for a in c.args)]
        assert not printed_raw,printed_raw
        # Text printed beside an exception (the Astra review of step 2): a save's warnings (a plan's section name), a
        # failed download's address, the folder a piece's words are kept in, a configured bank's version and licence
        import bootstrap,contextlib,io
        from musiclib.builder import Song
        song=Song('T',bars=1);song.section('a',1);song.part('p','melody',keys=(48,72)).note(1,1,60,1)
        song.project['plan']={'sections':[{'section':'ghost\x1b\nFORGED\u202e','unknown':1}]};said=io.StringIO()
        with contextlib.redirect_stdout(said):song.save(work/'text_save.json')
        real_once=bootstrap._download_once;bootstrap._download_once=lambda item,archive:(_ for _ in ()).throw(OSError('reset\x1b\nFORGED'))
        try:
            with contextlib.redirect_stdout(said):
                try:bootstrap.download({'url':'https://github.com/a\x1b[2J\nFORGED\u202e'},work/'text_dl.bin',False,tries=1);raise AssertionError('a failed download passed')
                except OSError:pass
        finally:bootstrap._download_once=real_once
        assert said.getvalue().count('\n')==2 and 'ghost\\x1b\\nFORGED\\u202e' in said.getvalue() and not set(said.getvalue())&{'\x1b','\u202e'},said.getvalue()
        (work/'text_kept\u202e').mkdir();run=cli('words',work/'text_kept\u202e','--own','a, b')
        assert run.returncode==0 and 'text_kept\\u202e' in run.stdout and '\u202e' not in run.stdout,(run.stdout,run.stderr[-300:])
        if config:
            from musiclib import audio
            c=audio.load_config(config);mine={k:c[k] for k in ('fluidsynth','ffmpeg','soundfont')}
            mine['soundfonts']={'tag':{**c['soundfont'],'license':'CC0\x1b[2J\nFORGED','version':'v\u202e1'}}
            from musiclib.surge import installed as surge_installed
            surge=bool(c.get('surge') and c.get('pedalboard') and surge_installed(c))   # doctor prints Surge's line only then (the fourth review)
            if surge:   # Surge XT's and its host's text too (the third review found them raw)
                mine.update(surge={**c['surge'],'version':'1\x1b[2J','license':'GPL\nFORGED'},pedalboard={**c['pedalboard'],'version':'0.9\u202e'})
            save_json(work/'text_doctor.json',mine);run=cli('doctor','--config',work/'text_doctor.json')
            assert run.returncode==0 and 'SoundFont tag | v\\u202e1 | CC0\\x1b[2J\\nFORGED' in run.stdout and not set(run.stdout)&{'\x1b','\u202e'},run.stdout[-400:]
            assert not surge or ('Surge XT 1\\x1b[2J | GPL\\nFORGED' in run.stdout and 'pedalboard 0.9\\u202e' in run.stdout),run.stdout[-400:]
        return {'refused_in_ids':len(unsafe),'kept':'ZWJ emoji, Chinese, quotes, backslash, tab in free text',
                'escaped_beside':['words','a reason for none','printed exceptions','warnings','a download address','the kept folder']+(['a bank\'s version and licence'] if config else [])}
    def json_read_with_a_byte_order_mark():
        # 0.8 step 2.2 (design-0.8.md; RFC 8259, 8.1): a project and a record are read as bytes, so UTF-8 with a byte
        # order mark and UTF-16 with one, as Windows PowerShell 5.1 writes them, are read (0.7 refused both); the tools
        # still write UTF-8 without one.
        import subprocess,sys
        from musiclib import files as fl
        # a character beyond the BMP (a surrogate pair in UTF-16), and a U+FEFF inside the text, which is text, not a mark
        p=example();p['title']='Mark 喆\ufeff \U0001f3b9';text=json.dumps(p,ensure_ascii=False)
        forms={'utf8_bom':b'\xef\xbb\xbf'+text.encode('utf-8'),'utf16_le':text.encode('utf-16'),'utf16_be':b'\xfe\xff'+text.encode('utf-16-be'),
               'utf32_le':b'\xff\xfe\x00\x00'+text.encode('utf-32-le'),'utf32_be':b'\x00\x00\xfe\xff'+text.encode('utf-32-be')}
        for name,data in forms.items():
            (work/f'bom_{name}.json').write_bytes(data)
            r=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'validate',str(work/f'bom_{name}.json')],capture_output=True,text=True,encoding='utf-8',errors='replace')
            assert r.returncode==0 and json.loads(r.stdout)['tracks']==5,(name,r.stderr[-300:])
            assert fl.read_json(work/f'bom_{name}.json')==p,name   # the whole project as written
        save_json(work/'bom_written.json',p);assert (work/'bom_written.json').read_bytes()[:1]==b'{'
        # the render records the clean-up and the rounds read are read so too: a failed render's report and its
        # render_input.json saved with a mark or in UTF-16 were taken for none, the failure unseen (the review of 0.8.0)
        from musiclib import clean,render as rd
        failed=json.dumps({'failed':{'error':'stopped by a test'}});inputs=json.dumps({'project_sha256':'a'*64,'renderer_sha256':'b'*64})
        for name,encode in (('utf8_bom',lambda s:b'\xef\xbb\xbf'+s.encode('utf-8')),('utf16',lambda s:s.encode('utf-16'))):
            folder=work/f'bom_render_{name}';folder.mkdir();(folder/'report.json').write_bytes(encode(failed));(folder/'render_input.json').write_bytes(encode(inputs))
            assert rd.stopped(folder)=='stopped by a test' and clean.render_record(folder) is not None,name
            (folder/fl.RECORD).write_bytes(encode(json.dumps({'kind':fl.KIND,'files':{}})));assert fl.is_record(folder/fl.RECORD),name   # the folder's own record
        return {'read':list(forms),'written':'UTF-8 without a mark'}
    def every_command_has_help_and_an_example():
        # 0.8 step 2.4 (design-0.8.md; the Command Line Interface Guidelines: lead with examples, describe every flag):
        # each of studio.py's 21 commands has a one-line description and an example, every option and argument a help
        # text, the usual order's examples come before the list of commands, and every example parses as written.
        import argparse,shlex,subprocess,sys
        import studio
        parser=studio.build_parser();sub=next(a for a in parser._actions if isinstance(a,argparse._SubParsersAction))
        assert len(sub.choices)==21,sorted(sub.choices)   # 17, instruments (2.6), start (2.5), still and video (4)
        helped={c.dest:c.help for c in sub._choices_actions}
        for name,cmd in sub.choices.items():
            assert helped.get(name) and 'Example:\n  python studio.py '+name in cmd.description,(name,cmd.description)
            assert all(a.help for a in cmd._actions),(name,[a.dest for a in cmd._actions if not a.help])
            example=cmd.description.split('Example:\n  ',1)[1].strip()
            parsed=parser.parse_args(shlex.split(example)[2:]);assert parsed.command==name,example
        for line in studio.EXAMPLES.splitlines()[1:-1]:
            assert parser.parse_args(shlex.split(line)[2:]).command,line
        options={a.dest:a.help for a in sub.choices['sounds']._actions}   # each measured range in its own unit (2.3: --attack showed the centroid's Hz)
        assert 'second' in options['attack'] and 'Hz' not in options['attack'] and 'Hz' in options['centroid'],(options['attack'],options['centroid'])
        top=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),'--help'],capture_output=True,text=True,encoding='utf-8')
        assert top.returncode==0 and top.stdout.index('python studio.py validate song.json')<top.stdout.index('positional arguments'),top.stdout[:400]
        # A command line the parser cannot read is reported as every other error: the usage, then one line `ERROR: ...`,
        # exit 2 (the walkthrough of 0.8.0 met argparse's own `error:` line, which SKILL.md's rule does not name).
        for bad in (['compare','a','b','--differences'],['nosuch'],['validate']):
            r=subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),*bad],capture_output=True,text=True,encoding='utf-8')
            assert (r.returncode==2 and r.stderr.startswith('usage:') and r.stderr.strip().splitlines()[-1].startswith('ERROR: studio.py')
                    and 'Traceback' not in r.stderr),(bad,r.returncode,r.stderr[-300:])
        return {'commands':len(sub.choices),'examples_parsed':len(sub.choices)+len(studio.EXAMPLES.splitlines())-2}
    def messages_say_where_what_and_the_rule():
        # 0.8 step 2.1 (design-0.8.md; NN/g and Google's error-message guidance; the 0.7 agents' failures): each message
        # step 2.1 located now gives the place, the value, the rule or the values allowed, and the fix; notes missing a
        # performance are reported together with their count; a missing project file, a folder given as one, a range
        # past the piece, a file that is no MIDI and a folder that is no render say what was expected.
        import subprocess,sys
        from musiclib import review as rv,midi as md
        from excerpt import extract
        def says(change,*words):
            p=example();change(p)
            try:validate(p);raise AssertionError(f'taken: {words}')
            except ValueError as e:assert all(w in str(e) for w in words),(words,str(e))
        says(lambda p:p.update(schema='v0'),"'v0'",'"schema": "music-production/v1"')
        says(lambda p:p['clock'].update(meter=[3,3]),'meter [3, 3]','2, 4, 8 or 16')
        def shift(p,k,start):p['sections'][k]['start_bar']=start
        says(lambda p:(shift(p,0,1)),'starts at bar 1','counted from 0')
        says(lambda p:(shift(p,1,3)),'answer starts at bar 3','bars 2 to 2 belong to no section')
        says(lambda p:(shift(p,1,1)),'answer starts at bar 1','overlaps')
        says(lambda p:p['sections'][1].update(id='question'),'question is used twice')
        says(lambda p:p['sections'][1].update(bars=1),'cover 3 bars and clock.bars is 4','bars 3 to 3 belong to no section')
        says(lambda p:p.update(tracks=[]),'1 to 64 tracks','has 0')
        says(lambda p:p['tracks'][0].update(engine='piano'),"piano: engine 'piano' is none of",'surge')
        says(lambda p:p['tracks'][0]['performance'].pop('notes'),'piano: performance.notes is missing','"velocity": 80')
        says(lambda p:p['tracks'][0].update(program=200),'piano program','0..127','200')
        says(lambda p:p['tracks'][0]['mix'].update(pan=2),'piano mix.pan','-1..1')
        says(lambda p:p['tracks'][0].update(drums='yes'),"piano: drums is true or false, got 'yes'")
        says(lambda p:p['tracks'][0]['notes'][-1].update(duration=8),'ends at beat','past the end of the score at beat 16','(4 bars)','shorten it')
        def unplayed(p):
            perf=p['tracks'][0]['performance']['notes']
            for n in p['tracks'][0]['notes'][:3]:perf.pop(n['id'])
        says(unplayed,'piano: 3 notes without an entry in performance.notes','"velocity": 80')
        def six(p):
            perf=p['tracks'][0]['performance']['notes'];gone=[n['id'] for n in p['tracks'][0]['notes'][:6]]
            for k in gone:perf.pop(k)
            six.listed=f'({", ".join(gone[:5])}, ...)'
        q=example();six(q)   # six missing: the count, the first five and the ellipsis
        try:validate(q);raise AssertionError('six notes without entries taken')
        except ValueError as e:assert 'piano: 6 notes without an entry in performance.notes' in str(e) and six.listed in str(e),str(e)
        says(lambda p:p['tracks'][0]['performance']['notes'].update(zzz={'velocity':80}),'piano: performance.notes has 1 entry','(zzz)')
        try:extract(example(),4,3);raise AssertionError('excerpt past the piece taken')
        except ValueError as e:assert 'Bars 4 to 6 are outside the piece, which has bars 1 to 4' in str(e),str(e)
        (work/'msg_not_midi.mid').write_bytes(b'RIFF'+bytes(20))
        try:md.read(work/'msg_not_midi.mid');raise AssertionError('not a MIDI file read')
        except ValueError as e:assert 'msg_not_midi.mid is not a MIDI file' in str(e) and 'MThd' in str(e),str(e)
        cli=lambda *a:subprocess.run([sys.executable,str(SCRIPTS.joinpath('studio.py')),*map(str,a)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        (work/'msg_folder').mkdir();(work/'msg_round').mkdir();(work/'msg_round'/'round.json').write_text('{}',encoding='utf-8')
        for args,words in ((('validate',work/'msg_none.json'),'No project file at'),(('validate',work/'msg_folder'),'is a folder: give the project JSON file'),
                           (('analyze',work/'msg_folder'),'is not a finished render (project.json is missing)'),(('analyze',work/'msg_round'),'render is not a folder'),
                           (('analyze',work/'msg_not_midi.mid'),'is not a folder')):
            r=cli(*args);assert r.returncode==2 and words in r.stderr and 'Traceback' not in r.stderr,(args,r.stderr[-300:])
        # notes outside their preset's keys: named, with the keys the preset has (a preset over keys 60-72 alone)
        bank={'presets':[{'bank':0,'program':1,'zones':[{'gens':{43:(60,72)},'mods':[],'target':0}]}],'instruments':[{'zones':[{'gens':{43:(60,72),58:60},'mods':[],'target':0}]}],'samples':[{'root':60}]}
        from musiclib.model import Clock
        q=example();t=q['tracks'][0];t['notes']=[{'id':f'x{k}','on':k,'duration':1,'pitch':x} for k,x in enumerate((60,48,50,84,86))]
        asked=rv.outside_keys(rv.stretched(q,Clock(q),{t['id']:rv.transposition(bank,0,1)}))
        assert asked.startswith("4 notes fall on keys their preset has no sample for and will not sound: piano at bar 1 beat 2, C3 (its preset has samples for C4 to C5); ") and '; ...' in asked and 'Move them onto those keys' in asked,asked
        # a preset with a hole (keys 60 and 72 alone): E4 inside its range is named with the keys it has (the Astra review
        # of step 2: the message gave C4 to C5, as if E4 were outside them)
        holed={'presets':[{'bank':0,'program':1,'zones':[{'gens':{},'mods':[],'target':0}]}],'samples':[{'root':60},{'root':72}],
               'instruments':[{'zones':[{'gens':{43:(60,60),58:60},'mods':[],'target':0},{'gens':{43:(72,72),58:72},'mods':[],'target':1}]}]}
        t['notes']=[{'id':'e','on':0,'duration':1,'pitch':64}]
        asked=rv.outside_keys(rv.stretched(q,Clock(q),{t['id']:rv.transposition(holed,0,1)}))
        assert asked.startswith('1 notes fall on keys their preset has no sample for and will not sound: piano at bar 1 beat 1, E4 (its preset has samples for C4, C5)'),asked
        return {'messages':19,'cli':5,'outside_keys':'named with the keys the preset has, holes too'}
    def json_output_survives_an_ascii_console():
        # --json output escapes what the console's code page lacks as JSON does (\u00e9, a surrogate pair beyond the
        # BMP), so it stays JSON; the console's own escape (\xe9) is not JSON.  (Found by the second review of 0.4.0.)
        import subprocess,sys
        here=SCRIPTS
        p=example();p['title']='Café 𝄞 喆';save_json(work/'console_json.json',p)
        run=subprocess.run([sys.executable,str(here/'studio.py'),'review',str(work/'console_json.json'),'--output',str(work/'console_json_review'),'--json'],
                           capture_output=True,timeout=300,env={**os.environ,'PYTHONIOENCODING':'ascii'},creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        assert run.returncode==0,(run.returncode,run.stderr[-500:])
        assert json.loads(run.stdout.decode('ascii'))['title']=='Café 𝄞 喆'
        return {'parsed':True}
    def notes_csv_escapes_formulas():
        # A cell a spreadsheet would run as a formula (=, +, -, @, tab, CR first) starts with an apostrophe (OWASP, CSV
        # Injection), so a project from someone else cannot put a formula into notes.csv.
        import csv
        from musiclib.review import review
        p=example();n=p['tracks'][0]['notes'][0];n['phrase']='=HYPERLINK("http://example.org")';n['articulation']='@SUM(1)'
        review(p,work/'csv_review')
        rows=list(csv.DictReader((work/'csv_review'/'notes.csv').open(encoding='utf-8',newline='')))
        row=next(r for r in rows if r['note_id']==n['id'])
        cells=[v for v in row.values() if 'HYPERLINK' in v or 'SUM(1)' in v]
        assert len(cells)==2 and all(v.startswith("'") for v in cells),row
        return {'escaped_cells':len(cells)}
    def scripts_escape_what_their_output_cannot_show():
        # On Windows a script's output read through a pipe, as an agent reads it, is written in the ANSI code page
        # (Python documentation, sys.stdout), which lacks characters some folder names hold (喆 is not in code page 950):
        # every script that prints escapes them instead of stopping.  PYTHONIOENCODING=ascii makes any system's pipe
        # such a page.  (Found by setting the skill up in a folder named with 喆.)
        import subprocess,sys
        here=SCRIPTS
        printing=[s.name for s in sorted(here.glob('*.py')) for t in [s.read_text(encoding='utf-8')] if "__name__=='__main__'" in t.replace(' ','') and 'print(' in t]
        missing=[n for n in printing if 'escape_unprintable()' not in (here/n).read_text(encoding='utf-8')]
        assert len(printing)>=7 and not missing,(printing,missing)
        out=work/'console_喆'/'song.json';out.parent.mkdir()
        run=subprocess.run([sys.executable,str(here/'make_example.py'),'--output',str(out)],capture_output=True,timeout=120,
                           env={**os.environ,'PYTHONIOENCODING':'ascii'},creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        assert run.returncode==0 and b'console_\\u5586' in run.stdout and out.is_file(),(run.returncode,run.stdout[-300:],run.stderr[-500:])
        return {'printing_scripts':len(printing),'escaped':True}
    found = {'shared_tempo_clock_and_compound_meter': clock_roundtrip, 'malformed_projects_rejected': invalid, 'expressive_fields_validate': expressive_fields, 'validation_holds_its_limits_at_their_edges': validation_edges, 'effects_are_capped_per_part_and_counted_as_listed': effects_capped_per_part, 'integer_fields_and_unknown_fields_are_reported': strict_projects, 'project_text_stays_text': project_text_stays_text, 'json_read_with_a_byte_order_mark': json_read_with_a_byte_order_mark, 'every_command_has_help_and_an_example': every_command_has_help_and_an_example, 'messages_say_where_what_and_the_rule': messages_say_where_what_and_the_rule, 'json_output_survives_an_ascii_console': json_output_survives_an_ascii_console, 'notes_csv_escapes_formulas': notes_csv_escapes_formulas, 'scripts_escape_what_their_output_cannot_show': scripts_escape_what_their_output_cannot_show}
    return found
