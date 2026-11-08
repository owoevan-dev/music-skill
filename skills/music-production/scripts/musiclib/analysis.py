"""Measurements of a finished render, for reviewing a mix without listening.  They locate problems; they are not a
verdict on how the music sounds.

- Each section of the master: ungated K-weighted level (LUFS-like), peak, crest factor, the share of power in six
  bands, left/right correlation, and the level change when folded to mono.
- Each processed stem: its K-weighted level per section.
- Lead presence: the melody against everything else, as the mix hears it.  In a bus-chain render that is the lead
  bus's output against the sum of the other buses (bus processing included: a lead compressor can take several dB);
  in a room-chain render, the melody stems (role "melody") against all other stems, which is what that chain sums.
  Reverb and delay returns count on neither side.  Two measures per section:
  - the K-weighted level of the melody minus that of the accompaniment, full band, over the whole section
    (`lead_minus_accompaniment_level_db`), the usual sense of "the lead sits 2 dB above the band";
  - frame by frame in 24 log bands from 200 Hz to 8 kHz, the median and 10th percentile of lead minus
    accompaniment, and the share of lead energy in bands where the accompaniment is at least 3 dB louder ("masked
    share").  Bass and cymbals are left out, so these read several dB higher than the full-band level difference.
  Both are proxies, not a model of masking.
- The melody group: in each section (and each requested bar span), the melody parts and every part whose onsets fall
  on theirs, at the same pitch class in any octave, at least 60% of the time. An orchestral tune is played by many
  parts at once, most of them on the ensemble bus, so the group's stems against all other stems
  (`melody_group_minus_rest_db`) reads the balance the bus measure misses.
- Balance suggestions: parts within a few dB of the group's loudest stem, with the cut that would put each 6 dB under
  it (3 dB for bass and countermelody parts). Near full velocity a softer velocity changes the level very little;
  make the cut with `level_dbfs` or let the part rest.
- The whole master: its long-term spectrum (slope over 100 Hz-4 kHz, low and top ends; `tonal_balance`), its width
  per band (`side_minus_mid_db`) and its peak-to-loudness ratio, against published measurements of commercial
  recordings and, with a reference, against that reference: a measured demo of the genre from tonal-references.json,
  another render or a WAV file.
- Warnings from the stem receipts: parts whose dynamics sat between two recorded takes that disagree in phase, and
  Surge XT parts that played their fallback preset.
"""
import json
import math
from pathlib import Path
import tempfile

import numpy as np

from . import audio, files
from .measure import k_filter, level, release
from .model import Clock, load_project

RATE = audio.RATE
BANDS = [(20, 60), (60, 250), (250, 800), (800, 2500), (2500, 6000), (6000, 16000)]
NPERSEG, HOP = 4096, 1024
REFERENCES = Path(__file__).resolve().parents[2] / 'references' / 'tonal-references.json'
OCTAVE_NAMES = {-5: '31', -4: '63', -3: '125', -2: '250', -1: '500', 0: '1k', 1: '2k', 2: '4k', 3: '8k', 4: '16k'}


def db(x):
    return 10 * np.log10(np.maximum(x, 1e-20))


def section_spans(p, clock):
    return [(s['id'], round(clock.seconds(s['start_bar'] * clock.beats_per_bar) * RATE),
             round(clock.seconds((s['start_bar'] + s['bars']) * clock.beats_per_bar) * RATE)) for s in p['sections']]


def band_powers(x, edges):
    """Power per frame in each band [edges[i], edges[i+1]) of a mono signal (Hann window of 4096, hop 1024, frames
    centred on multiples of the hop).  Returns (bands x frames, frame centres in samples)."""
    f = np.fft.rfftfreq(NPERSEG, 1 / RATE)
    lo, hi = np.searchsorted(f, edges[:-1]), np.searchsorted(f, edges[1:])
    pad = np.concatenate([np.zeros(NPERSEG // 2), np.asarray(x, dtype=np.float64), np.zeros(NPERSEG // 2)])
    frames = 1 + max(0, (len(pad) - NPERSEG) // HOP)
    window = np.hanning(NPERSEG + 1)[:-1]
    out = np.empty((len(lo), frames))
    for start in range(0, frames, 256):
        idx = np.arange(start, min(frames, start + 256))
        power = np.abs(np.fft.rfft(pad[idx[:, None] * HOP + np.arange(NPERSEG)] * window, axis=1)) ** 2
        c = np.concatenate([np.zeros((len(idx), 1)), np.cumsum(power, axis=1)], axis=1)
        out[:, idx] = (c[:, hi] - c[:, lo]).T
    return out, np.arange(frames) * HOP


def master_sections(master, spans):
    km = k_filter(master)
    rows = []
    for sid, a, b in spans:
        x = np.asarray(master[a:b], dtype=np.float64)
        if len(x) < 2:
            continue
        mono = x.mean(axis=1)
        spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) ** 2
        f = np.fft.rfftfreq(len(mono), 1 / RATE)
        total = max(float(spec[(f >= 20) & (f < 16000)].sum()), 1e-30)
        left, right = x[:, 0], x[:, 1]
        corr = float(np.corrcoef(left, right)[0, 1]) if left.std() > 0 and right.std() > 0 else 1.0
        mono_change = 10 * math.log10(max(float(np.mean(mono ** 2)), 1e-30) / max(float(np.mean(x ** 2)), 1e-30))
        peak = 20 * math.log10(max(float(np.abs(x).max()), 1e-15))
        rows.append({'section': sid, 'seconds': [round(a / RATE, 1), round(b / RATE, 1)],
                     'level_lufs_ungated': round(level(km[a:b]), 2), 'peak_dbfs': round(peak, 2),
                     'crest_db': round(peak - 10 * math.log10(max(float(np.mean(x ** 2)), 1e-30)), 1),
                     'band_share_pct': {f'{lo}-{hi}': round(float(spec[(f >= lo) & (f < hi)].sum()) / total * 100, 1)
                                        for lo, hi in BANDS},
                     'lr_correlation': round(corr, 3), 'mono_sum_change_db': round(mono_change, 2)})
    return rows


def tonal_balance(master):
    """The master's long-term average spectrum against published measurements of commercial recordings.

    Power per hertz in third-octave bands from 31.5 Hz to 16 kHz (mono, the whole render), the slope of a line fitted
    from 100 Hz to 4 kHz in dB per octave (pink noise reads -3, white noise 0), and how far the bands below 80 Hz and
    from 6.3 to 12.5 kHz sit from that line extended.  Popular recordings fall about 5 dB per octave over 100 Hz-4 kHz
    (Pestana et al. 2013, about 800 recordings 1950-2010; Elowsson and Friberg 2017 measured 4.5), hip-hop and
    electronic ones extend further into the low end and jazz and folk fall away at the top (Pestana et al. 2013), and
    more percussion raises the top (Elowsson and Friberg 2017)."""
    mono = np.asarray(master, dtype=np.float64).mean(axis=1)
    centres = 1000 * 2 ** (np.arange(-15, 15) / 3)
    centres = centres[(centres >= 31.5) & (centres <= 16000)]
    edges = np.concatenate([[centres[0] * 2 ** (-1 / 6)], centres * 2 ** (1 / 6)])
    power, _ = band_powers(mono, edges)
    f = np.fft.rfftfreq(NPERSEG, 1 / RATE)
    bins = np.array([max(1, int(np.sum((f >= lo) & (f < hi)))) for lo, hi in zip(edges[:-1], edges[1:])])
    spectrum = db(power.mean(axis=1) / bins)
    octaves = np.log2(centres / 1000)
    fit = (centres >= 100) & (centres <= 4000)
    slope, offset = np.polyfit(octaves[fit], spectrum[fit], 1)
    line = slope * octaves + offset
    low = centres < 80
    top = (centres >= 6300) & (centres <= 12500)
    return {'slope_db_per_octave_100hz_4khz': round(float(slope), 2),
            'low_end_vs_line_db': round(float(np.mean(spectrum[low] - line[low])), 1),
            'top_end_vs_line_db': round(float(np.mean(spectrum[top] - line[top])), 1),
            'third_octaves_db': {f'{c:.0f}': round(float(v - line[np.argmin(np.abs(centres - 1000))]), 1) for c, v in zip(centres, spectrum)},
            'reference': 'popular recordings fall about 4.5-5 dB per octave over 100 Hz-4 kHz (Pestana et al. 2013; Elowsson and Friberg 2017)'}


def stereo_width(master):
    """Side minus mid power in dB below 120 Hz, from 120 Hz to 2 kHz and from 2 to 16 kHz: -60 (the floor) is mono,
    0 as much side as mid (left and right unrelated)."""
    x = np.asarray(master, dtype=np.float64)
    edges = [20, 120, 2000, 16000]
    mid, _ = band_powers((x[:, 0] + x[:, 1]) / 2, edges)
    side, _ = band_powers((x[:, 0] - x[:, 1]) / 2, edges)
    return {f'{lo}-{hi}': round(max(-60.0, float(db(s.sum()) - db(m.sum()))), 1)
            for lo, hi, m, s in zip(edges[:-1], edges[1:], mid, side)}


def long_term(master, meter):
    """What a reference stores: tonal balance, width per band, and from the loudness meter (`meter`: the report's
    master entry) integrated loudness, true peak, loudness range and the peak-to-loudness ratio (PLR)."""
    loud = {k: meter.get(k) for k in ('integrated_lufs', 'true_peak_dbtp', 'lra_lu')}
    if loud['integrated_lufs'] is not None and loud['true_peak_dbtp'] is not None:
        loud['plr_db'] = round(loud['true_peak_dbtp'] - loud['integrated_lufs'], 1)
    return {'tonal_balance': tonal_balance(master), 'side_minus_mid_db': stereo_width(master), 'loudness': loud}


def no_links_in(folder):
    """Refuse a render folder holding links: it holds its own files only, so nothing is read through a link."""
    odd = files.links_in(folder)
    if odd:
        raise ValueError(f'{folder} holds links ({", ".join(str(Path(p).relative_to(folder)) for p in odd[:5])}); a render '
                         'folder holds its own files only, so analyze reads none through a link')


def load_reference(spec, config=None):
    """(name, long_term measures) of a reference: a name in tonal-references.json, a render folder (its master.wav
    and report.json), or a WAV file, which FFmpeg converts to 48 kHz and meters in a temporary folder (needs a
    config).  Nothing of a WAV reference is kept."""
    table = json.loads(REFERENCES.read_text(encoding='utf-8'))['references']
    if spec in table:
        return spec, table[spec]
    path = Path(spec)
    if path.is_dir():
        no_links_in(path)
        report = json.loads((path / 'report.json').read_text(encoding='utf-8'))
        if isinstance(report.get('failed'), dict):
            raise ValueError(f'--reference {spec}: that render stopped before it finished ({report["failed"].get("error")})')
        master, _ = audio.read_wav(path / 'master.wav')
        return f'{path.resolve().parent.name}/{path.name}', long_term(master, report.get('master', {}))
    if path.is_file():
        if path.suffix.lower() != '.wav':
            raise ValueError(f'--reference {spec}: convert it to WAV first (for example ffmpeg -i song.flac song.wav)')
        if config is None:
            raise ValueError('--reference with a WAV file needs --config: FFmpeg converts and meters it')
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / 'reference.wav'
            # At most a second past the longest WAV read (audio.MAX_WAV_SECONDS), so a longer reference is refused
            # when it is read rather than converted whole first.
            audio.ffmpeg(config, ['-i', str(path), '-t', str(audio.MAX_WAV_SECONDS + 1), '-ac', '2', '-ar', str(RATE), '-c:a',
                                  'pcm_f32le', str(wav)], tmp, 'reference')
            meter = audio.measure(config, wav, tmp, 'reference_loudness')
            master, _ = audio.read_wav(wav)
            measures = long_term(np.array(master), meter)
            del master
        return path.name, measures
    raise ValueError(f'--reference {spec}: not one of {", ".join(sorted(table))}, a render folder or a WAV file')


def octaves(third_octaves):
    """Third-octave levels (dB, keyed by centre in Hz) power-averaged into octaves."""
    groups = {}
    for key, v in third_octaves.items():
        groups.setdefault(round(math.log2(float(key) / 1000)), []).append(10 ** (v / 10))
    return {OCTAVE_NAMES[k]: 10 * math.log10(sum(g) / len(g)) for k, g in sorted(groups.items())}


def compare(here, ref, name):
    """The master's long-term measures minus a reference's, with warnings where they differ widely: a tilt over
    1.5 dB per octave (8 dB across 100 Hz-4 kHz), a low or top end 6 dB apart, a PLR 4 dB apart, a bass much wider
    than the reference's.  Both spectra are levelled at their own fitted line at 1 kHz."""
    a, b = here['tonal_balance'], ref['tonal_balance']
    oa, ob = octaves(a['third_octaves_db']), octaves(b['third_octaves_db'])
    la, lb = here['loudness'], ref['loudness']

    def diff(x, y):
        return None if x is None or y is None else round(x - y, 2)
    out = {'reference': name,
           'slope_difference_db_per_octave': diff(a['slope_db_per_octave_100hz_4khz'], b['slope_db_per_octave_100hz_4khz']),
           'low_end_difference_db': diff(a['low_end_vs_line_db'], b['low_end_vs_line_db']),
           'top_end_difference_db': diff(a['top_end_vs_line_db'], b['top_end_vs_line_db']),
           'octaves_minus_reference_db': {k: round(oa[k] - ob[k], 1) for k in oa if k in ob},
           'side_minus_mid_difference_db': {k: diff(v, ref['side_minus_mid_db'].get(k)) for k, v in here['side_minus_mid_db'].items()},
           **{f'{k}_difference': diff(la.get(k), lb.get(k)) for k in ('integrated_lufs', 'plr_db', 'lra_lu')}}
    warnings = []
    tilt = out['slope_difference_db_per_octave']
    if abs(tilt) > 1.5:
        warnings.append(f'the master tilts {abs(tilt):g} dB per octave {"brighter" if tilt > 0 else "darker"} than {name} over '
                        f'100 Hz-4 kHz ({a["slope_db_per_octave_100hz_4khz"]:g} against {b["slope_db_per_octave_100hz_4khz"]:g}): '
                        'octaves_minus_reference_db shows where.')
    for key, region in (('low_end_difference_db', 'low end (below 80 Hz)'), ('top_end_difference_db', 'top (6.3-12.5 kHz)')):
        if abs(out[key]) > 6:
            warnings.append(f'the {region} sits {abs(out[key]):g} dB {"above" if out[key] > 0 else "below"} that of {name}, '
                            'each measured against its own slope.')
    plr = out['plr_db_difference']
    if plr is not None and abs(plr) > 4:
        warnings.append(f'the master\'s peak-to-loudness ratio is {la["plr_db"]:g} dB against {lb["plr_db"]:g} for {name}: '
                        f'{"more compressed" if plr < 0 else "more dynamic"} than the reference.')
    low_here, low_ref = here['side_minus_mid_db']['20-120'], ref['side_minus_mid_db'].get('20-120')
    if low_ref is not None and low_here > -20 and low_here - low_ref > 10:
        warnings.append(f'below 120 Hz the side is {-low_here:g} dB under the mid, against {-low_ref:g} for {name}: a bass wider '
                        'than the reference loses level in mono; check the panning of the bass parts and their reverb, or '
                        'set mix.mono_below_hz.')
    return out, warnings


def lead_presence(lead, accompaniment, spans):
    """`lead` and `accompaniment` are stereo sums of their stems."""
    lead_k, acc_k = k_filter(lead), k_filter(accompaniment)
    level_diff = {sid: level(lead_k[a:b]) - level(acc_k[a:b]) for sid, a, b in spans}
    del lead_k, acc_k
    edges = np.geomspace(200, 8000, 25)
    bl, centres = band_powers(lead.mean(axis=1), edges)
    ba, _ = band_powers(accompaniment.mean(axis=1), edges)
    lead_total, acc_total = bl.sum(axis=0), ba.sum(axis=0)
    # A frame counts while the lead sounds: some energy (db() floors silence at -200 dB, so a silent lead would be
    # within 35 dB of its own "loudest" frame everywhere) and within 35 dB of its loudest.  A lead that rests
    # throughout a section has no active frames there, and no figures.
    active = (lead_total > 1e-20) & (db(lead_total) > db(lead_total).max() - 35)
    rows = []
    for sid, a, b in spans:
        sel = active & (centres >= a) & (centres < b)
        row = {'section': sid, 'lead_active_frames': int(sel.sum())}
        if sel.sum() >= 5:
            ratio = db(lead_total[sel]) - db(acc_total[sel])
            masked = (ba[:, sel] > 2 * bl[:, sel]) * bl[:, sel]
            row.update(lead_minus_accompaniment_level_db=round(level_diff[sid], 1),
                       lead_minus_accompaniment_db_median=round(float(np.median(ratio)), 1),
                       lead_minus_accompaniment_db_p10=round(float(np.percentile(ratio, 10)), 1),
                       masked_share_pct=round(float(masked.sum() / bl[:, sel].sum() * 100), 1))
        rows.append(row)
    return rows


def doublings(p, lo, hi, share=.6):
    """The melody parts sounding in beats [lo, hi) and the parts that double them: at least `share` of a part's onsets
    there fall on a melody onset of the same pitch class."""
    melody = [t for t in p['tracks'] if t.get('role') == 'melody' and any(lo <= n['on'] < hi for n in t['notes'])]
    keys = {(round(n['on'], 3), n['pitch'] % 12) for t in melody for n in t['notes'] if lo <= n['on'] < hi}
    group = {t['id'] for t in melody}
    for t in p['tracks']:
        if t['id'] in group or t.get('drums'):
            continue
        notes = [n for n in t['notes'] if lo <= n['on'] < hi]
        if len(notes) >= 4 and sum((round(n['on'], 3), n['pitch'] % 12) in keys for n in notes) >= share * len(notes):
            group.add(t['id'])
    return sorted(group)


MARGIN_DB = {'bass': 3, 'countermelody': 3}


def balance(p, levels, group):
    """Non-melody parts within MARGIN_DB (6 dB by default) of the loudest melody-group stem, loudest first."""
    roles = {t['id']: t.get('role') for t in p['tracks']}
    drums = {t['id'] for t in p['tracks'] if t.get('drums')}
    lead = max((levels[t] for t in group if t in levels and levels[t] > -90), default=None)
    out = []
    if lead is None:
        return out
    for tid, x in sorted(levels.items(), key=lambda kv: -kv[1]):
        if tid in group or tid in drums or x <= -90:
            continue
        want = lead - MARGIN_DB.get(roles.get(tid), 6)
        if x > want:
            out.append({'track': tid, 'role': roles.get(tid), 'level_minus_melody_db': round(x - lead, 1),
                        'suggested_cut_db': round(x - want, 1)})
    return out


def analyze(render_dir, bar_spans=(), reference=None):
    """`bar_spans`: (name, first bar, last bar), 1-based and inclusive, measured like the sections.  `reference`:
    (name, measures) from load_reference."""
    render_dir = Path(render_dir)
    # The project as the render wrote it, read as any project is (size bounded, validated): a render folder from
    # elsewhere cannot name stems outside it or ask for an unbounded length, nor reach one through a link.
    no_links_in(render_dir)
    p = load_project(render_dir / 'project.json')
    clock = Clock(p)
    spans = section_spans(p, clock)
    bpb = clock.beats_per_bar
    for name, first, last in bar_spans:
        if last > p['clock']['bars']:
            raise ValueError(f'--span {name}:{first}-{last}: the piece has {p["clock"]["bars"]} bars')
    extra = [(f'span:{name}', round(clock.seconds((first - 1) * bpb) * RATE), round(clock.seconds(last * bpb) * RATE))
             for name, first, last in bar_spans]
    regions = spans + extra
    beats = {sid: ((s['start_bar']) * bpb, (s['start_bar'] + s['bars']) * bpb) for sid, s in zip([x[0] for x in spans], p['sections'])}
    beats.update({f'span:{name}': ((first - 1) * bpb, last * bpb) for name, first, last in bar_spans})
    groups = {sid: doublings(p, *beats[sid]) for sid, _, _ in regions}
    sums = {sid: [np.zeros((b - a, 2)), np.zeros((b - a, 2))] for sid, a, b in regions}
    master, _ = audio.read_wav(render_dir / 'master.wav')
    rows = master_sections(master, spans)
    report_file = render_dir / 'report.json'
    report = json.loads(report_file.read_text(encoding='utf-8')) if report_file.is_file() else {}
    buses = (report.get('buses') or {}).get('assignment') if report.get('chain') == 'bus' else None
    stems, lead, accompaniment = {}, None, None
    for t in p['tracks']:
        y, _ = audio.read_wav(render_dir / 'stems' / f'{t["id"]}.wav')
        ky = k_filter(y)
        stems[t['id']] = {sid: round(level(ky[a:b]), 2) for sid, a, b in regions}
        del ky
        for sid, a, b in regions:
            seg = np.asarray(y[a:b], dtype=np.float64)
            sums[sid][0 if t['id'] in groups[sid] else 1][:len(seg)] += seg
        if buses is None:
            y = np.asarray(y, dtype=np.float64)
            if t.get('role') == 'melody':
                lead = y if lead is None else lead + y
            else:
                accompaniment = y if accompaniment is None else accompaniment + y
    if buses is not None:
        lead_tracks = [tid for tid, b in buses.items() if b == 'lead']
        for b in sorted(set(buses.values())):
            y = np.asarray(audio.read_wav(render_dir / 'returns' / f'bus_{b}.wav')[0], dtype=np.float64)
            if b == 'lead':
                lead = y
            else:
                accompaniment = y if accompaniment is None else accompaniment + y
    else:
        lead_tracks = [t['id'] for t in p['tracks'] if t.get('role') == 'melody']
    melody = []
    for sid, a, b in regions:
        g, r = sums[sid]
        row = {'region': sid, 'melody_group': groups[sid]}
        if groups[sid] and np.any(g) and np.any(r):
            row['melody_group_minus_rest_db'] = round(level(k_filter(g)) - level(k_filter(r)), 1)
        row['balance'] = balance(p, {tid: v[sid] for tid, v in stems.items()}, groups[sid])
        melody.append(row)
    warnings = []
    here = long_term(master, report.get('master', {}))
    slope = here['tonal_balance']['slope_db_per_octave_100hz_4khz']
    if not -8 <= slope <= -1.5:
        warnings.append(f'the master falls {-slope:g} dB per octave over 100 Hz-4 kHz, far {"darker" if slope < -8 else "brighter"} '
                        'than commercial recordings, which average about 4.5-5 (Pestana et al. 2013; Elowsson and Friberg '
                        '2017): check the bass and pads against the cymbals and leads, and compare with a reference of the '
                        'genre (--reference).')
    comparison = None
    if reference is not None:
        comparison, differ = compare(here, reference[1], reference[0])
        warnings += differ
    squeezed = {k: v for k, v in ((report.get('mastering') or {}).get('limiting_db') or {}).items() if v > 3}
    if squeezed:
        worst = max(squeezed, key=squeezed.get)
        warnings.append(f'the delivery limiter took {squeezed[worst]:g} dB of level from {worst} '
                        f'({", ".join(f"{k} {v:g}" for k, v in squeezed.items())}): Sound On Sound\'s guidance is 3-6 dB of '
                        'gain reduction on loud peaks and rarely more than 6 (White 2003), and heavier limiting can flatten '
                        'transients; have it heard, lower target_lufs, or lower that section\'s peaks '
                        '(mix.saturate on its loudest parts, ducking, less level on what it adds).')
    receipts_file = render_dir / 'stem_receipts.json'
    for r in json.loads(receipts_file.read_text(encoding='utf-8')) if receipts_file.is_file() else []:
        played = r.get('surge') or {}
        if played.get('rendered_with') == 'built-in synth':
            warnings.append(f'{r["track"]}: Surge XT preset {played.get("preset")} played on the built-in synth\'s '
                            f'{played.get("fallback")} instead ({played.get("reason")}).')
        share = (r.get('expressive') or {}).get('correction_out_of_range_pct')
        if share is not None and share > 2:
            warnings.append(f'{r["track"]}: for {share:g}% of its playing the dynamics sat between two recorded takes that '
                            'disagree in phase (the correction ran past 1.25 or under 0.8); play it in dynamics_mode "take" (the default), or keep a solo near one recorded dynamic.')
    measured = {'render': render_dir.name, 'sections': rows, 'tonal_balance': here['tonal_balance'],
                'side_minus_mid_db': here['side_minus_mid_db'], 'reference_comparison': comparison, 'stem_levels_lufs_ungated': stems,
                'lead_tracks': lead_tracks, 'lead_source': 'buses' if buses is not None else 'stems',
                'lead_presence': lead_presence(lead, accompaniment, regions) if lead is not None and accompaniment is not None else [],
                'melody_groups': melody, 'warnings': warnings,
                'master': here['loudness'],
                'note': 'Measurements only; they do not establish how the music sounds.'}
    release()
    return measured
