"""Short summaries of what review, render, analyze, compare and audition found, printed by default.

Each is meant to answer what an agent decides next without opening the JSON: every review question, the failed
checks, the key figures beside their reference, what changed.  Long lists are cut to their first few entries, and each
summary ends with the file and the keys that hold the full figures, so a detail is fetched directly rather than
explored (Anthropic, Writing effective tools for agents, 2025: concise responses with sensible defaults and
truncation; Yang et al. 2024, SWE-agent: summarized results).  `--json` prints the full JSON instead.  The keys are
documented in references/outputs.md."""
import os
from pathlib import Path

from .review import note_name

EXAMPLES = 5  # entries shown per list; the files hold all of them


def _rel(path):
    """A path relative to the working folder when that is shorter."""
    path = str(Path(path))
    try:
        rel = os.path.relpath(path)
    except ValueError:  # another drive on Windows
        return path
    return rel if len(rel) < len(path) else path


def _label(folder):
    """A render folder's name, or its round's name when it is the render inside a round's folder."""
    folder = Path(folder)
    return folder.parent.name if folder.name == 'render' and (folder.parent / 'round.json').is_file() else folder.name


def _signed(x, digits=1):
    return 'n/a' if x is None else f'{x:+.{digits}f}'


def _g(x):
    """A figure as written, or n/a where it was not measured (a render stopped before report.json has no master figures)."""
    return 'n/a' if x is None else f'{x:g}'


def _more(items, shown=EXAMPLES, count=None):
    """'; and N more' after the first `shown` of `items`; `count` is how many there are in all where the list keeps only
    the first of them (review keeps 40 examples of a finding)."""
    listed = min(shown, len(items))
    total = max(len(items), count or 0)
    return f'; and {total - listed} more' if total > listed else ''


def review(r, folder):
    """Every review question in full, then where each counted finding is (its first examples)."""
    count = lambda n, word: f'{n} {word}{"s" if n != 1 else ""}'
    lines = [f'Review of {r["title"]}: {count(len(r["tracks"]), "part")}, {count(len(r["sections"]), "section")}, '
             f'{count(len(r["prompts"]), "question")}.']
    lines += [f'{k}. {q}' for k, q in enumerate(r['prompts'], 1)] or ['No questions.']
    where = []

    def notes(x):
        return '/'.join(x.get('notes') or [note_name(p) for p in x.get('pitches', [])])

    v = r.get('vertical_minor_seconds_ninths') or {}
    if v.get('count'):
        ex = v['examples']
        where.append(f'vertical_minor_seconds_ninths ({v["count"]}, {v["foreground_count"]} touching the foreground): ' + '; '.join(
            f'{x["at"]} {"+".join(x["parts"])} {notes(x)}{" (foreground)" if x.get("involves_foreground") else ""}'
            for x in ex[:EXAMPLES]) + _more(ex, count=v['count']))
    oc = r.get('outside_chord') or {}
    if oc.get('count'):
        ex = oc['examples']
        where.append(f'outside_chord ({oc["count"]}): ' + '; '.join(
            f'{x["at"]} {x["track"]} {x["note"]} on {x["chord"]} ({x.get("approach")}, {x.get("departure")})' for x in ex[:EXAMPLES]) + _more(ex, count=oc['count']))
    par = r.get('parallel_fifths_octaves') or {}
    if par.get('count'):
        ex = par['examples']
        where.append(f'parallel_fifths_octaves ({par["count"]}): ' + '; '.join(
            f'{x["at"]} {"+".join(x["parts"])} {x["interval"]}' for x in ex[:EXAMPLES]) + _more(ex, count=par['count']))
    low = r.get('low_intervals') or {}
    if low.get('count'):
        ex = low['examples']
        where.append(f'low_intervals ({low["count"]}): ' + '; '.join(
            f'{x["at"]} {"+".join(x["parts"])} {x["interval"]} {notes(x)} (limit {x["limit"]})' for x in ex[:EXAMPLES]) + _more(ex, count=low['count']))
    st = r.get('transposed_samples') or {}
    if st.get('count'):
        ex = st['examples']
        where.append(f'transposed_samples ({st["count"]}): ' + '; '.join(
            f'{x["at"]} {x["track"]} {note_name(x["pitch"])} {x["semitones"]:+d} semitones' for x in ex[:EXAMPLES]) + _more(ex, count=st['count']))
    if where:
        lines += ['Where (first examples):'] + [f'- {w}' for w in where]
    lines.append(f'Full figures: {_rel(Path(folder) / "score_review.json")}: examples under the keys above, and '
                 'tracks, sections, repetition, stiffness, melody_sections, loop_seam; notes.csv lists every note.')
    return '\n'.join(lines)


def render(report, folder):
    """The status and failed checks, the master against its target, limiting per section, what was made again."""
    m, mastering = report['master'], report.get('mastering') or {}
    stages = report.get('stage_seconds') or {}
    lines = [f'Render{" (draft)" if report.get("draft") else ""} of {report["title"]}: {report["status"]} in '
             f'{report["runtime_seconds"]:.1f} s (' + ', '.join(f'{k} {v:.1f}' for k, v in stages.items() if v >= 1) + ').']
    target = mastering.get('target_lufs')
    lines.append(f'Master: {m["integrated_lufs"]:g} LUFS' + (f' (target {target:g})' if target is not None else '') +
                 f', true peak {m["true_peak_dbtp"]:g} dBTP, loudness range {m["lra_lu"]:g} LU.')
    limiting = mastering.get('limiting_db') or {}
    if limiting:
        lines.append('Delivery limiting by section (dB): ' + ', '.join(f'{k} {max(v, 0.0) + 0.0:.1f}' for k, v in limiting.items()) + '.')
    if mastering.get('peak_held_db'):
        lines.append(f'The gain was held {mastering["peak_held_db"]:g} dB under the target by the true peak (dynamics "wide").')
    buses = report.get('buses') or {}
    if buses.get('level_change_db'):
        lines.append('Each bus against the sum of its stems (dB): ' + ', '.join(f'{k} {v:+g}' for k, v in buses['level_change_db'].items()) + '.')
    failed = [k for k, ok in report['checks'].items() if not ok]
    lines.append('Failed checks: ' + (', '.join(failed) if failed else 'none') + '.')
    if report.get('left_out'):
        lines.append('Left out of this draft: ' + '; '.join(report['left_out']) + '. Deliver a full render.')
    lines.append(f'Parts: {report["stem_count"]}; raw synthesis from the cache {report["cache_hits"]}, processed stems from the '
                 f'cache {report.get("stems_reused", 0)} (stem_receipts.json names which).')
    loop = report.get('loop')
    if loop:
        lines.append(f'Loop: bars {loop["start_bar"] + 1}-{loop["end_bar"]}, {loop["length_samples"]} samples, loop.wav'
                     + (', loop.ogg' if 'ogg' in loop['files'] else '') + (f', {len(loop["layers"]["parts"])} layers' if loop.get('layers') else '') + '.')
    lines.append(f'Full figures: {_rel(Path(folder) / "report.json")}: checks, master, mastering (passes, limiting_db), '
                 'sections, buses (level_change_db), loop, stage_seconds, process_seconds; stem_receipts.json per part.')
    return '\n'.join(lines)


def analysis(r, path, render=None):
    """Per section: level, stereo and mono fold, the lead against the rest, the melody group; the tonal balance against
    published measurements and a reference; the balance suggestions and warnings."""
    m = r.get('master') or {}
    lines = [f'Analysis of {_label(render) if render else r["render"]}: master {_g(m.get("integrated_lufs"))} LUFS, true peak '
             f'{_g(m.get("true_peak_dbtp"))} dBTP, loudness range {_g(m.get("lra_lu"))} LU, peak to loudness {_g(m.get("plr_db"))} dB.']
    lead = {x['section']: x for x in r.get('lead_presence') or []}
    group = {x['region']: x for x in r.get('melody_groups') or []}
    lines.append('Per section: level LUFS (ungated) | L/R correlation | mono fold dB | lead minus accompaniment dB: level, '
                 f'median, 10th percentile, masked % (lead: {", ".join(r.get("lead_tracks") or []) or "none"}, from the '
                 f'{r.get("lead_source", "stems")}) | melody group minus the rest dB')
    regions = [s['section'] for s in r['sections']] + [k for k in group if k not in {s['section'] for s in r['sections']}]
    rows = {s['section']: s for s in r['sections']}
    for k in regions:
        s, x, g = rows.get(k, {}), lead.get(k), group.get(k, {})
        own = (f'{_g(s.get("level_lufs_ungated"))} | {_g(s.get("lr_correlation"))} | {_signed(s.get("mono_sum_change_db"))}' if s else 'n/a | n/a | n/a')
        ld = (f'{_signed(x.get("lead_minus_accompaniment_level_db"))}, {_signed(x.get("lead_minus_accompaniment_db_median"))}, '
              f'{_signed(x.get("lead_minus_accompaniment_db_p10"))}, {x.get("masked_share_pct", "n/a")}%' if x else 'no lead')
        lines.append(f'  {k}: {own} | {ld} | {_signed(g.get("melody_group_minus_rest_db"))}')
    if r['sections'] and r['sections'][0].get('band_share_pct'):
        names = list(r['sections'][0]['band_share_pct'])
        lines.append(f'Power by band % ({" / ".join(names)} Hz): ' + '; '.join(
            f'{s["section"]} ' + '/'.join(f'{s["band_share_pct"][n]:g}' for n in names) for s in r['sections']))
    t = r['tonal_balance']
    lines.append(f'Tonal balance: {_g(t.get("slope_db_per_octave_100hz_4khz"))} dB per octave over 100 Hz-4 kHz; {t.get("reference", "")}; '
                 f'low end {_signed(t["low_end_vs_line_db"])} dB and top end {_signed(t["top_end_vs_line_db"])} dB off that line.')
    c = r.get('reference_comparison')
    if c:
        lines.append(f'Against {c["reference"]}: slope {_signed(c["slope_difference_db_per_octave"], 2)} dB per octave, octaves minus '
                     'the reference (dB) ' + ', '.join(f'{k} {v:+g}' for k, v in c['octaves_minus_reference_db'].items())
                     + f'; loudness {_signed(c.get("integrated_lufs_difference"))} LU, peak to loudness {_signed(c.get("plr_db_difference"))} dB, '
                     f'loudness range {_signed(c.get("lra_lu_difference"))} LU.')
    cuts = [(x['region'], b) for x in r.get('melody_groups') or [] for b in x.get('balance', [])[:3]]
    if cuts:
        lines.append('Parts close to the melody group (level minus the melody, the cut that puts each under it, dB): ' + '; '.join(
            f'{k} {b["track"]} {b["level_minus_melody_db"]:+g} (cut {b["suggested_cut_db"]:g})' for k, b in cuts[:12]) + _more(cuts, 12))
    lines += [f'Warning: {w}' for w in r.get('warnings') or []]
    lines.append(f'Full figures: {_rel(path)}: sections (band_share_pct, peak, crest), lead_presence, melody_groups (balance), '
                 'stem_levels_lufs_ungated (each part per section), tonal_balance (third_octaves_db), reference_comparison, '
                 'side_minus_mid_db. Measurements only; they do not establish how the music sounds.')
    return '\n'.join(lines)


def compare(r, path):
    """The project's edits, what was synthesized again, and every file that changed, with where."""
    s = r['summary']
    lines = [f'Compare {_label(r["before"])} -> {_label(r["after"])}: master '
             + ' -> '.join('n/a' if x is None else f'{x:g}' for x in r.get('master_lufs', [])) + ' LUFS.']
    lines.append('Project changes: ' + ('; '.join(s.get('project') or []) or 'none') + '.')
    for key, label in (('synthesized_again', 'Synthesized again'), ('same_inputs_new_take', 'Same inputs, a new take (Surge XT)')):
        if s.get(key):
            lines.append(f'{label}: {", ".join(s[key])}.')
    changed = s.get('changed') or {}
    for group, entries in changed.items():
        for name, text in entries.items():
            lines.append(f'- {group} {name}: {text}')
    if not any(changed.values()):
        lines.append('No file changed.')
    same = s.get('identical') or {}
    lines.append('Identical: ' + (', '.join(f'{n} {g}' for g, n in same.items() if n) or 'none') + '.')
    if s.get('note'):
        lines.append(s['note'])
    if 'clip' in r:
        c = r['clip']
        lines.append('Clip: ' + ('not made, the masters do not differ' if c is None else
                                 f'not made: {c["error"]}' if c.get('error') else f'{_rel(c["file"])}, old then new'))
    lines += [f'Warning: {w}' for w in r.get('warnings') or []]
    lines.append(f'Full figures: {_rel(path)}: files.<stems|buses|returns|premix|master>.<name> (passages with seconds and '
                 'bar:beat, level_db, difference_db), project_changes, synthesis.')
    return '\n'.join(lines)


def audition(r, folder):
    """The order the versions play in, with each sound's measured level and brightness."""
    lines = [f'Audition of {r["track"]}, bars {r["bars"][0]}-{r["bars"][1]}{" alone" if r.get("solo") else ""}: '
             f'{_rel(Path(folder) / "audition.mp3")}, each {r["each_seconds"]:g} s, {r["gap_seconds"]:g} s apart, '
             f'all at {r["loudness_lufs"]:g} LUFS.']
    for v in r['versions']:
        b = v['part_brightness']
        extra = [x for x in (v.get('surge_character'), v.get('rendered_with') if v.get('fallback') else None) if x]
        controls = v.get('surge_controls') or {}
        if controls.get('wheel'):
            extra.append('mod wheel: ' + ', '.join(controls['wheel']))
        if controls.get('macros'):
            extra.append('macros: ' + '; '.join(f'{k} {(m.get("label") or "")} {", ".join(m.get("targets", [])[:2])}'.replace('  ', ' ')
                                                 for k, m in controls['macros'].items()))
        if v.get('performance_left_out'):
            extra.append('left out: ' + ', '.join(v['performance_left_out']))
        lines.append(f'{v["order"]}. {v["sound"]} ({v["engine"]}): part {v["part_rms_dbfs"]:g} dBFS RMS, centroid '
                     f'{b["centroid_hz"]:g} Hz, {b["above_2k_pct"]:g}% above 2 kHz, {b["above_5k_pct"]:g}% above 5 kHz'
                     + (f'; {"; ".join(extra)}' if extra else '') + (f' [fell back: {v.get("reason")}]' if v.get('fallback') else ''))
    lines.append(r['note'])
    lines.append(f'Full figures: {_rel(Path(folder) / "audition.json")}: versions (surge_controls, surge_character, '
                 'part_brightness); each version\'s render in its numbered folder.')
    return '\n'.join(lines)
