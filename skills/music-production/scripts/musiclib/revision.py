"""One revision round in one command: validate the project, review the score, render a draft, analyze it and compare it
with the previous round, each step's short summary shown as soon as it is done.

The steps are those an agent chains on every revision, done in one call with one report, as Anthropic advises for
frequently chained multi-step tasks (Writing effective tools for agents, 2025).  Each step writes what its own command
writes, in the round's folder:

    <round>/review/      score_review.json, notes.csv, arrangement.md (studio.py review)
    <round>/render/      a draft render (studio.py render --draft), with analysis.json and compare_<previous>.json
    <round>/round.json   where each result is, the render's status and the seconds per step

The draft is the same audio as a full render; deliver a full render (studio.py render).  The cache is shared with the
other rounds and renders of the project: by default the folder `cache` next to the round."""
import os
import time
from pathlib import Path

from . import files, summary
from .model import load_project, save_json, validate

KIND = 'music-production round'  # in round.json: what made the folder (clean removes only what the tools made)


def render_folder(path):
    """A render folder, or the render inside a round's folder.  Neither may be a link: the commands that take one
    hold its work lock and write their report into it, and through a link both went wherever it led, as a round from
    elsewhere whose render/ is a link to another folder (GPT's security audit of 0.5, S03)."""
    path = Path(path)
    inner = path / 'render' if (path / 'round.json').is_file() else path
    for p in dict.fromkeys((path, inner)):
        if files.linked(p):
            raise ValueError(f'{p} is a link; give the folder itself (a render folder is never read or written through a link)')
    return inner


def revision_round(project_file, output, config_file, previous=None, cache=None, spans=(), reference=None, jobs=None,
                   show=print, clip=None):
    """Run a round into the new folder `output`, passing each step's summary to `show` as soon as the step is done (a
    failed render still leaves the review shown); returns the round's record, also saved as round.json.  With `clip`
    (an MP3 path) and a previous round, the comparison also writes the change old then new at one loudness."""
    from .analysis import analyze, load_reference, region_names
    from .audio import load_config
    from .compare import clip as make_clip, compare
    from .render import render, stopped
    from .review import review
    output = Path(output)
    files.fresh(output, 'outputs never overwrite, so choose a new folder')
    before = render_folder(previous) if previous else None
    if before is not None and not (before / 'report.json').is_file():
        raise ValueError(f'--previous {previous}: no render there (a round folder or a render folder)')
    if before is not None and stopped(before):
        raise ValueError(f'--previous {previous}: that render stopped before it finished ({stopped(before)}); name one that finished')
    if clip is not None and (before is None or files.occupied(clip)):
        raise ValueError('--clip needs --previous: the clip plays the previous round, then this one' if before is None
                         else f'{clip} exists; outputs never overwrite, so choose a new path')
    started, seconds = time.monotonic(), {}
    mark = [started]

    def lap(name):
        now = time.monotonic()
        seconds[name] = round(now - mark[0], 2)
        mark[0] = now

    p = load_project(project_file)
    validation = validate(p)  # raises with the notes, bar and beat of what to change
    for name, first, last in spans:  # analyze would refuse them after the render
        if last > p['clock']['bars']:
            raise ValueError(f'--span {name}:{first}-{last}: the piece has {p["clock"]["bars"]} bars')
    region_names([s['id'] for s in p['sections']], spans)  # so would it two regions of one name
    cfg = load_config(config_file)
    ref = load_reference(reference, cfg) if reference else None  # a bad reference fails before the render
    lap('validate')
    output.mkdir(parents=True)
    with files.working(output):  # held for the whole round: clean leaves a round at work alone (files.working)
        # Paths relative to the round's folder: the record can be shared without the local folders and user name in them
        # (across two Windows drives no relative path exists, and the full one is kept).
        def here(path):
            try:
                return os.path.relpath(Path(path).resolve(), output.resolve()).replace(os.sep, '/')
            except ValueError:
                return str(Path(path).resolve())
        record = {'kind': KIND, 'title': p['title'], 'project': here(project_file), 'validation': validation,
                  'status': 'FAIL', 'failed': None, 'previous': here(before) if before is not None else None,
                  'review': 'review/score_review.json', 'render': 'render/report.json', 'analysis': None,
                  'compare': None, 'seconds': seconds}
        # The round's folder holds its record from the start, and whatever step stops the round, the record says which.
        save_json(output / 'round.json', record)
        files.register(output, [output / 'round.json'])
        step = 'review'
        try:
            reviewed = review(p, output / 'review', cfg)
            record['questions'] = len(reviewed['prompts'])
            lap('review')
            show(summary.review(reviewed, output / 'review'))
            step = 'render'
            rendered = render(project_file, output / 'render', config_file,
                              Path(cache) if cache else output.parent / 'cache', jobs=jobs, draft=True)
            record['status'] = rendered['status']
            lap('render')
            show(summary.render(rendered, output / 'render'))
            step = 'analyze'
            measured = analyze(output / 'render', spans, ref)
            save_json(output / 'render' / 'analysis.json', measured)
            files.register(output / 'render', [output / 'render' / 'analysis.json'])
            record['analysis'] = 'render/analysis.json'
            lap('analyze')
            show(summary.analysis(measured, output / 'render' / 'analysis.json', output / 'render'))
            if before is not None:
                step = 'compare'
                # The previous round's render, held while it is read, the clip's reading of its master included
                # (clean leaves it alone; it was let go before the clip, and a clean could take that master; found by
                # GPT Pro's fourth review of 0.4.0).
                with files.working(before):
                    compared = compare(before, output / 'render')
                    if clip is not None:
                        # As compare --clip: if the clip cannot be made, the comparison is still written and says why.
                        try:
                            compared['clip'] = make_clip(cfg, compared, clip)
                        except (ValueError, OSError, RuntimeError) as e:
                            compared['clip'] = {'error': str(e)}
                in_round = before.name == 'render' and (before.parent / 'round.json').is_file()
                name = before.parent.name if in_round else before.name
                compare_file = output / 'render' / f'compare_{name}.json'
                from .compare import portable
                save_json(compare_file, portable(compared, compare_file.parent))
                files.register(output / 'render', [compare_file])
                if isinstance(compared.get('clip'), dict) and compared['clip'].get('file'):
                    files.register_output(compared['clip']['file'])
                record['compare'] = f'render/{compare_file.name}'
                lap('compare')
                show(summary.compare(compared, compare_file))
            else:
                show('No previous round to compare with (--previous names one).')
        except BaseException as e:
            if step not in seconds:
                lap(step)  # the seconds up to the failure, under the step that failed
            record['failed'] = {'step': step, 'error': str(e) or type(e).__name__}
            raise
        finally:
            record['runtime_seconds'] = round(time.monotonic() - started, 2)
            save_json(output / 'round.json', record)
            files.register(output, [output / 'round.json'])
        show(f'Round {output.name}: {record["status"]} in {record["runtime_seconds"]:.1f} s ('
             + ', '.join(f'{k} {v:.1f}' for k, v in seconds.items()) + f'). Next round: --previous {output}')
        return record
