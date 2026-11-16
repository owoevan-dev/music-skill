"""studio.py still and studio.py video (0.8 step 4): a render's score as a piano roll, drawn from the render's own
project.json (as_played: the notes as the part's renderer played them), with the render's master.wav as the sound.

What it shows (design-0.8.md, 4.6): the notes' own properties alone, pitch, onset, duration and part, with the bar
lines, the sections, a legend and a moving playhead; nothing is coloured or marked by interval, chord or harmony.
Time runs right to left past the playhead; pitch runs upward; unpitched parts (a kit, noise) have a lane beneath.

Colour: a part takes the colour of its class, from its mix bus (mixbus.bus_of): the lead bus; the ensemble and rhythm
buses together; the bass bus; and the kit and effects in a neutral grey, in a lane of their own.  Three hues, because
three is the most that stay apart for every pair under simulated colour-vision deficiency on a dark ground: checked
with a palette validator over all pairs on the roll's three grounds (worst colour-deficient Delta E 9.4, normal vision
20.9, OKLab x 100; each 3:1 or more), where no four or five hues of Okabe and Ito's palette (2008) or of the reference
palette it was checked against clear those floors together.  The legend names every part and lights it while it
sounds, so no part rests on colour alone (parts of one name in one class share an entry; in two classes, two).  Contrast (WCAG 2.2, 1.4.3 and 1.4.11): text 4.5:1 and note bars 3:1
against what they lie on; the selfcheck computes both from the colours.  A sounding note brightens in place, never
the frame (WCAG 2.3.1).

Pillow draws it, and is optional: without it the commands say how to install it.  The font is Pillow's own (a version
of Aileron, which its author releases with no rights reserved); a title in another script is drawn with a font the
system has (never one bundled), and without one it is drawn as far as the built-in font goes.

Memory: each frame is drawn from the notes inside it, one frame after another, and handed to FFmpeg as it is made: no
picture of the whole piece is held (the private tool's two strips took about 250 MB for five minutes).  A frame is a
function of its time alone, so a video drawn in pieces would join without a seam."""
import bisect
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from . import files
from .midi import remap
from .mixbus import bus_of
from .model import TPQ, Clock, performed

SURFACE, PANEL, GRID = (20, 20, 19), (30, 30, 28), (58, 58, 54)
BLACK_ROW = (25, 25, 23)
TEXT, TEXT2, TEXT3 = (240, 239, 236), (200, 199, 190), (160, 159, 150)
SECTION_ON, SECTION = (66, 66, 62), (40, 40, 38)   # the section playing (its name in TEXT) and the others (theirs in TEXT3)
INKS = {SURFACE: (TEXT, TEXT2, TEXT3), PANEL: (TEXT3,), BLACK_ROW: (TEXT3,), SECTION_ON: (TEXT,), SECTION: (TEXT3,)}   # what text lies on what
# A bus's class, and a class's colour and name (the three hues validated as the module's docstring says; the grey a
# neutral for the kit's lane, apart from them by lightness and by place)
CLASS = {'lead': 'lead', 'ensemble': 'harmony', 'rhythm': 'harmony', 'bass': 'bass', 'drums': 'kit', 'fx': 'kit'}
COLOUR = {'lead': (217, 89, 38), 'harmony': (57, 135, 229), 'bass': (25, 158, 112), 'kit': (176, 175, 166)}
LABEL = {'lead': 'Lead', 'harmony': 'Harmony and patterns', 'bass': 'Bass', 'kit': 'Drums and effects'}
ORDER = ('lead', 'harmony', 'bass', 'kit')
# Windows' own in its Fonts folder (%WINDIR%: Windows need not be on drive C, and the repository holds no drive's path)
SYSTEM_FONTS = (*(os.path.join(os.environ['WINDIR'], 'Fonts', f) for f in ('msjh.ttc', 'msyh.ttc', 'YuGothR.ttc', 'malgun.ttf') if os.environ.get('WINDIR')),
                '/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/Hiragino Sans GB.ttc',
                '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc')
LANE_HIT_S = .09   # a hit in the lane is drawn this long, as a short mark


def pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ValueError('still and video draw with Pillow, which is not installed: python -m pip install pillow') from None
    return Image, ImageDraw, ImageFont


def luminance(rgb):
    """WCAG 2.2's relative luminance of an sRGB colour."""
    c = [x / 255 for x in rgb]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def brighter(rgb, k=.42):
    return tuple(int(round(x + (255 - x) * k)) for x in rgb)


class Roll:
    """A render's piano roll at a size: frame(t) draws the picture at t seconds."""

    def __init__(self, render, width=1280, height=720, fps=30):
        render = unlinked(render)
        project = render / 'project.json'
        if not project.is_file():
            raise ValueError(f'{render} is not a render folder (project.json is missing): still and video take the --output of studio.py render')
        # its own files alone, as analyze and compare read a render folder: a link in it (its project, its master) led
        # the picture and the video's sound to files elsewhere (the whole review of 0.8); refused before Pillow is needed
        from .analysis import no_links_in
        no_links_in(render)
        Image, ImageDraw, ImageFont = pillow()
        self.Image, self.ImageDraw = Image, ImageDraw
        from .model import load_project
        p = load_project(project)
        clock = Clock(p)
        if not (320 <= width <= 3840 and 240 <= height <= 2160 and width % 2 == 0 and height % 2 == 0):
            raise ValueError(f'a picture of {width}x{height}: from 320x240 to 3840x2160, even numbers (video codecs halve the colour)')
        self.W, self.H, self.fps = width, height, fps
        # one line each: a valid name or title holding a line break stopped Pillow's measure (the review of 0.8.0)
        self.title = ' '.join(p['title'].split())
        self.parts = []
        for t in p['tracks']:
            # a kit's hits are short marks in the lane; noise there sounds as long as it is written (a riser of
            # seconds was drawn and lit for 90 ms: the third outside review), and so does a kit played backwards, each
            # note a swell over its written span (a reversed crash was drawn as a hit: the Astra review of the fixes)
            kit = bool(t.get('drums')) or t['engine'] == 'drum_synth'
            hits = kit and not (t['engine'] == 'soundfont' and t.get('reverse'))
            lane = kit or t['engine'] == 'noise'
            notes = sorted((n['start_seconds'], n['end_seconds'], n['pitch']) for n in as_played(t, clock))
            # by onset, with the longest note's length: a frame looks only at the notes that can reach into it
            self.parts.append({'name': ' '.join((t.get('name') or t['id']).split()), 'class': 'kit' if lane else CLASS[bus_of(t)], 'lane': lane, 'hits': hits,
                               'notes': notes, 'starts': [n[0] for n in notes],
                               'longest': max([LANE_HIT_S] + [e - s for s, e, _ in notes])})
        self.length = clock.seconds(clock.total_beats)   # the score's end
        self.total = clock.end + clock.tail              # the master's: the score and its tail, as render makes it
        self.bars = [clock.seconds(b * clock.beats_per_bar) for b in range(p['clock']['bars'] + 1)]
        self.sections = [(s['id'].replace('_', ' '), clock.seconds(s['start_bar'] * clock.beats_per_bar),
                          clock.seconds((s['start_bar'] + s['bars']) * clock.beats_per_bar)) for s in p['sections']]
        size = lambda k: max(10, int(round(height * k)))
        try:
            self.font = {k: ImageFont.load_default(size(v)) for k, v in (('title', .042), ('body', .024), ('small', .02))}
        except TypeError:   # Pillow before 10.1: its built-in font comes in one size only
            raise ValueError('still and video need Pillow 10.1 or later: python -m pip install -U pillow') from None
        if any(ord(c) > 0x24F for c in self.title):   # beyond Latin: a system font that has the script, where there is one
            for path in SYSTEM_FONTS:
                if os.path.isfile(path):
                    self.font['title'] = ImageFont.truetype(path, size(.042))
                    break
        self._layout()
        self._cache = {}

    def _layout(self):
        W, H = self.W, self.H
        measure = self.ImageDraw.Draw(self.Image.new('RGB', (8, 8))).textlength
        self.groups = []
        for cls in ORDER:
            names = []
            for q in self.parts:
                if q['class'] == cls and q['name'] not in names:
                    names.append(q['name'])
            if names:
                self.groups.append((cls, names))
        # the legend: a column a bus, its names wrapped inside it, at most 30 % of the picture's height; names past that
        # end the column as "+N more" (an orchestra of 57 parts at 720 lines)
        self.margin = int(W * .03)
        self.col = (W - 2 * self.margin) / max(1, len(self.groups))
        self.line = int(self.H * .034)
        most = max(1, int((H * .3) / self.line - 1.6))
        room = self.col - self.line * .5
        width = lambda text: measure(text, font=self.font['small']) + self.line * .5

        def fit(name):   # a name wider than its column alone: its longest beginning that fits with an ellipsis
            if width(name) <= room:
                return name
            lo, hi = 0, len(name)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                lo, hi = (mid, hi) if width(name[:mid].rstrip() + '…') <= room else (lo, mid - 1)
            return name[:lo].rstrip() + '…'
        # each row holds (the text drawn, the part's name): two names cut to one text stay two parts (the text alone
        # lit both from the later one: the third outside review); "+N more" names none
        self.legend_rows = []
        for bus, names in self.groups:
            shown = [(fit(name), name) for name in names]
            rows, x = [[]], 0
            for k, (text, name) in enumerate(shown):
                if x + width(text) > room and rows[-1]:
                    if len(rows) == most:   # the last row: room for what is left as "+N more"
                        while rows[-1] and x + width(f'+{len(shown) - k} more') > room:
                            x -= width(rows[-1].pop()[0])
                            k -= 1
                        rows[-1].append((f'+{len(shown) - k} more', None))
                        break
                    rows.append([])
                    x = 0
                rows[-1].append((text, name))
                x += width(text)
            self.legend_rows.append(rows)
        tallest = max((len(r) for r in self.legend_rows), default=1)
        self.legend_top = H - int(self.line * (1.6 + tallest))
        self.top = int(H * .15)
        self.bottom = self.legend_top - int(H * .02)
        pitched = [n for q in self.parts if not q['lane'] for n in q['notes']]
        self.lo, self.hi = (min(n[2] for n in pitched) - 2, max(n[2] for n in pitched) + 2) if pitched else (58, 72)
        self.lane_keys = sorted({n[2] for q in self.parts if q['lane'] for n in q['notes']})
        self.lane_row = {k: n for n, k in enumerate(self.lane_keys)}
        lane_h = min(int(H * .14), int(H * .016) * len(self.lane_keys) + 8) if self.lane_keys else 0
        self.pitch_bottom = self.bottom - (lane_h + 6 if lane_h else 0)
        self.semitone = (self.pitch_bottom - self.top) / (self.hi - self.lo + 1)
        self.lane_top, self.lane_h = self.pitch_bottom + 6, lane_h
        self.playhead = int(W * .3)
        self.pps = self.fps * max(1, round(W / 10 / self.fps))   # about ten seconds across, whole pixels a frame
        # the roll's still ground: its rows (a darker one a black key), a line and name at each C
        ground = self.Image.new('RGB', (W, self.bottom - self.top), PANEL)
        d = self.ImageDraw.Draw(ground)
        for pitch in range(self.lo, self.hi + 1):
            y = self.y_of(pitch) - self.top
            if pitch % 12 in (1, 3, 6, 8, 10):
                d.rectangle([0, y, W, y + self.semitone], fill=BLACK_ROW)
        for pitch in range(self.lo, self.hi + 1):
            if pitch % 12 == 0:
                y = self.y_of(pitch) - self.top + self.semitone
                d.line([0, y, W, y], fill=GRID, width=1)
        if lane_h:
            d.rectangle([0, self.lane_top - self.top - 3, W, self.lane_top - self.top - 3], fill=GRID)
        self.ground = np.asarray(ground).copy()

    def y_of(self, pitch):
        return self.pitch_bottom - (pitch - self.lo + 1) * self.semitone

    def x_of(self, seconds, now):
        return self.playhead + (seconds - now) * self.pps

    def frame(self, t):
        """The picture at t seconds, as an array of height x width x 3 (a function of t alone)."""
        W, H = self.W, self.H
        img = self.Image.new('RGB', (W, H), SURFACE)
        img.paste(self.Image.fromarray(self.ground), (0, self.top))
        d = self.ImageDraw.Draw(img)
        small = self.font['small']
        for k, s in enumerate(self.bars):
            x = round(self.x_of(s, t))
            if 0 <= x < W:
                d.line([x, self.top, x, self.bottom], fill=GRID, width=1)
                d.text((x + 4, self.top + 2), str(k + 1), font=small, fill=TEXT3)
        for pitch in range(self.lo, self.hi + 1):
            if pitch % 12 == 0:
                d.text((6, self.y_of(pitch) + self.semitone - 2), f'C{pitch // 12 - 1}', font=small, fill=TEXT3, anchor='ls')
        sounding = set()
        row_h = (self.lane_h - 8) / max(1, len(self.lane_keys))
        left, right = t - self.playhead / self.pps, t + (W - self.playhead) / self.pps   # the seconds the picture spans
        for q in self.parts:
            colour = COLOUR[q['class']]
            i, j = bisect.bisect_left(q['starts'], left - q['longest']), bisect.bisect_right(q['starts'], right)
            for s, e, pitch in q['notes'][i:j]:
                # a hit sounds and is drawn as a short mark; noise sounds as long as it is written and is drawn at least
                # that mark's width (its sounding not lengthened by it: a 20 ms noise lit at 50 ms, the fourth review)
                sounds = s + LANE_HIT_S if q['hits'] else e
                e = max(sounds, s + LANE_HIT_S) if q['lane'] else e
                x0, x1 = self.x_of(s, t), self.x_of(e, t)
                if x1 < 0 or x0 > W:
                    continue
                on = s <= t < sounds
                if on:
                    sounding.add((q['class'], q['name']))
                fill = brighter(colour) if on else colour
                # bounds kept in order where a row or a note is under two pixels (Pillow refuses a rectangle whose end
                # comes before its start: a full register at 320x240, the third outside review)
                if q['lane']:
                    y0 = self.lane_top + 2 + self.lane_row[pitch] * row_h
                    end = round(x0) + max(6, int(self.H * .012)) if q['hits'] else max(round(x0) + 2, round(x1) - 2)
                    box = [round(x0), round(y0), end, round(y0 + max(3, row_h - 2))]
                else:
                    y0 = self.y_of(pitch)
                    box = [round(x0), round(y0 + 1), max(round(x0) + 2, round(x1) - 2), max(round(y0 + 1), round(y0 + self.semitone - 1))]
                d.rectangle(box, fill=fill, outline=TEXT if on else None)
        d.rectangle([self.playhead - 1, self.top, self.playhead + 1, self.bottom], fill=TEXT)
        img.paste(self._header(t), (0, 0))
        img.paste(self._legend(frozenset(sounding)), (0, self.legend_top))
        return np.asarray(img)

    def _header(self, t):
        """The title, the time, and the sections as a strip with the playhead's place in the piece."""
        minutes = lambda v: f'{int(v // 60)}:{int(v % 60):02d}'
        section = next((k for k, (_, s0, s1) in enumerate(self.sections) if s0 <= t < s1), None)
        x_now = self.margin + (self.W - 2 * self.margin) * min(1, max(0, t) / max(self.total, 1e-9))
        key = ('header', minutes(t), section, round(x_now))
        if key not in self._cache:
            if len(self._cache) > 64:
                self._cache.clear()
            img = self.Image.new('RGB', (self.W, self.top), SURFACE)
            d = self.ImageDraw.Draw(img)
            d.text((self.margin, int(self.H * .02)), self.title, font=self.font['title'], fill=TEXT)
            d.text((self.W - self.margin, int(self.H * .03)), f'{minutes(t)} / {minutes(self.total)}', font=self.font['body'], fill=TEXT2, anchor='ra')
            y0, y1 = int(self.top * .62), int(self.top * .9)
            span = self.W - 2 * self.margin   # the master's length across, the tail after the last section
            for k, (label, s0, s1) in enumerate(self.sections):
                a = self.margin + span * s0 / max(self.total, 1e-9)
                b = self.margin + span * s1 / max(self.total, 1e-9)
                d.rectangle([a + 1, y0, max(a + 1, b - 1), y1], fill=SECTION_ON if k == section else SECTION)   # a section under 2 pixels wide too
                if d.textlength(label, font=self.font['small']) < b - a - 8:
                    d.text(((a + b) / 2, (y0 + y1) / 2), label, font=self.font['small'], fill=TEXT if k == section else TEXT3, anchor='mm')
            d.rectangle([round(x_now) - 1, y0 - 3, round(x_now) + 1, y1 + 3], fill=TEXT)
            self._cache[key] = img
        return self._cache[key]

    def _legend(self, lit):
        key = ('legend', lit)
        if key not in self._cache:
            if len(self._cache) > 64:
                self._cache.clear()
            img = self.Image.new('RGB', (self.W, self.H - self.legend_top), SURFACE)
            d = self.ImageDraw.Draw(img)
            sw = int(self.line * .55)
            for k, ((bus, _), rows) in enumerate(zip(self.groups, self.legend_rows)):
                x = self.margin + k * self.col
                d.rectangle([x, int(self.line * .25), x + sw, int(self.line * .25) + sw], fill=COLOUR[bus])
                d.text((x + sw + 8, int(self.line * .25) + sw / 2), LABEL[bus], font=self.font['body'], fill=TEXT, anchor='lm')
                for r, row in enumerate(rows):
                    cx = x
                    for text, name in row:
                        d.text((cx, int(self.line * (1.2 + r))), text, font=self.font['small'], fill=TEXT if (bus, name) in lit else TEXT3)
                        cx += d.textlength(text, font=self.font['small']) + self.line * .5
            self._cache[key] = img
        return self._cache[key]


def as_played(t, clock):
    """A part's notes as its renderer plays them, each with the pitch it is written at (the note heard), as
    mixbus.held_spans takes their times: a sampled part played backwards over each note's written span
    (render.reversed_notes); one on its recorded dynamics or with crossfade legato as layered.plan has them (a note
    entered legato later, the one before held into the crossfade); one with a key_map as midi.remap leaves them (notes
    the map puts on one key at once sound as one, a retrigger there cuts the note before: the whole review); else as
    performed.  The roll drew every part from the performed notes, which the first two do not play (the review of 0.8.0)."""
    from . import layered
    if t['engine'] == 'soundfont' and t.get('reverse'):
        return [{'start_seconds': clock.seconds(n['on']), 'end_seconds': clock.seconds(n['on'] + n['duration']), 'pitch': n['pitch']} for n in t['notes']]
    if t['engine'] == 'soundfont' and layered.wanted(t):
        return [{'start_seconds': clock.seconds(n['tick'] / TPQ), 'end_seconds': clock.seconds(n['end_tick'] / TPQ), 'pitch': n['pitch']}
                for n in layered.plan(t, clock)]
    played = performed(t, clock)
    if t.get('key_map'):
        played = [{**n, 'pitch': n['written'], 'end_seconds': clock.seconds(n['end_tick'] / TPQ)}
                  for n in remap([{**n, 'written': n['pitch']} for n in played], t['key_map'])]
    return played


def unlinked(render):
    """The render folder given, refused where it is itself a link (revision.render_folder's rule): it is read, and held,
    as the folder itself."""
    render = Path(render)
    if files.linked(render):
        raise ValueError(f'{render} is a link; give the folder itself (a render folder is never read through a link)')
    return render


def master_of(render):
    """The render's master: master.wav, which every render writes and checks, full or draft (as analyze and compare
    read it).  Its FLAC was taken first, and a draft resumed over a full render leaves the full render's FLAC beside
    the new WAV: the video carried the earlier master (the review of 0.8.0)."""
    if (Path(render) / 'master.wav').is_file():
        return Path(render) / 'master.wav'
    raise ValueError(f'{render} has no master.wav: still and video take the --output of studio.py render')


def still(render, at, output, width=1280, height=720):
    files.fresh(output)
    # held while it is read, as analyze and compare hold a render: one a render is still writing is refused, and a clean
    # leaves it alone meanwhile (the whole review of 0.8)
    with files.working(unlinked(render)):
        roll = Roll(render, width, height)
        if not 0 <= at <= roll.total:
            raise ValueError(f'--at {at:g}: the piece runs 0 to {roll.total:.1f} seconds')
        picture = roll.Image.fromarray(roll.frame(at))
    try:
        with files.staged(Path(output), new=True) as f:   # never in the place of a file that took the name meanwhile
            picture.save(f, format='PNG')
    except FileExistsError:
        raise ValueError(f'{output} was made by something else while the picture was drawn; it is left as it is') from None
    return files.joined([f'Wrote {output}: {roll.W}x{roll.H}, the roll at {at:.2f} s, {len(roll.parts)} parts in {len(roll.groups)} colours.'])


def encoders(ffmpeg):
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    try:
        out = subprocess.run([ffmpeg, '-hide_banner', '-encoders'], capture_output=True, text=True, errors='replace',
                             stdin=subprocess.DEVNULL, creationflags=flags, timeout=30)
    except subprocess.TimeoutExpired:   # not a TimeoutError: it went past the command's handler as a traceback
        raise ValueError(f'{ffmpeg} did not list its encoders within 30 seconds; check the FFmpeg the configuration names') from None
    return {line.split()[1] for line in out.stdout.splitlines() if len(line.split()) > 1 and line.startswith(' ')}


def video(render, output, config, mp4=False, size_mb=10.0, fps=30, width=1280, height=720):
    """The roll as a video with the render's master as its sound: WebM (VP9 and Opus) by default, MP4 (H.264 and AAC,
    the widest playback) with `mp4`, each only where the configured FFmpeg has the encoders; two passes at the bit rate
    that brings the file under `size_mb` (GitHub takes videos up to 10 MB on its free plans).  The render is held while
    it is read, as still holds it: its master is read until the last frame is encoded."""
    render = unlinked(Path(render).absolute())
    with files.working(render):
        return _video(render, output, config, mp4, size_mb, fps, width, height)


def _video(render, output, config, mp4, size_mb, fps, width, height):
    from . import audio
    # absolute: FFmpeg runs in the staging folder, where a relative render's master named nothing (the third review)
    render, output = Path(render).absolute(), Path(output).absolute()
    files.fresh(output)
    if output.suffix.lower() != ('.mp4' if mp4 else '.webm'):
        raise ValueError(f'{output}: name it .mp4 with --mp4, else .webm')
    cfg = audio.load_config(config)
    ffmpeg = cfg['ffmpeg']['path']
    vcodec, acodec, abr = ('libx264', 'aac', 128_000) if mp4 else ('libvpx-vp9', 'libopus', 96_000)
    have = encoders(ffmpeg)
    missing = [c for c in (vcodec, acodec) if c not in have]
    if missing:
        raise ValueError(f'this FFmpeg has no {" or ".join(missing)} encoder; ' + ('try the WebM default' if mp4 else 'try --mp4, or an FFmpeg build with libvpx and libopus'))
    if not 1 <= fps <= 60 or not 0.5 <= size_mb <= 4000:
        raise ValueError(f'--fps {fps} (1-60) and --size-mb {size_mb:g} (0.5-4000)')
    roll = Roll(render, width, height, fps)
    master = master_of(render)
    frames = int(math.ceil(roll.total * fps - 1e-9))   # as long as the master, its tail included
    seconds = frames / fps
    # the least this makes is 100 kbps of picture and the sound's rate, 4 % kept for the containers: a size under that
    # is refused before anything is drawn (a minute at 0.5 MB was made at three times the size and reported done)
    need = (100_000 + abr) * seconds / 8 / .96 / 1e6
    if size_mb < need:
        raise ValueError(f'--size-mb {size_mb:g}: {seconds:.0f} seconds of video take {math.ceil(need * 10) / 10:g} MB at least '
                         f'(100 kbps of picture and {abr // 1000} of sound); ask for that or more')
    vbr = int(size_mb * 8e6 * .96 / seconds) - abr
    staging = files.staging_folder(output)
    try:
        log = staging / 'passlog'
        base = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(fps), '-i', '-']
        codec = (['-c:v', 'libx264', '-preset', 'medium', '-pix_fmt', 'yuv420p'] if mp4 else
                 ['-c:v', 'libvpx-vp9', '-deadline', 'good', '-row-mt', '1', '-pix_fmt', 'yuv420p'])
        out = staging / output.name
        # Every input before the options of the output (FFmpeg gives an option to the file that follows it: the codec's
        # options ahead of the master's -i were refused as options of that input).
        for n, inputs, tail in ((1, [], ['-an', '-f', 'null', os.devnull]),
                                (2, ['-i', str(master)], ['-map', '0:v', '-map', '1:a', '-map_metadata', '-1', '-c:a', acodec, '-b:a', str(abr), '-shortest', str(out)])):
            argv = base + inputs + codec + ['-b:v', str(vbr), '-pass', str(n), '-passlogfile', str(log)] + (['-cpu-used', '4' if n == 1 else '2'] if not mp4 else []) + tail
            with open(staging / f'pass{n}.log', 'wb') as err:
                proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stderr=err, cwd=staging,
                                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                try:
                    for k in range(frames):
                        proc.stdin.write(roll.frame(k / fps).tobytes())
                    proc.stdin.close()
                except OSError:   # FFmpeg stopped reading the frames (an option refused; -shortest's end): its exit code and log tell
                    try:
                        proc.stdin.close()
                    except OSError:
                        pass
                except BaseException:
                    proc.kill()
                    proc.wait()
                    raise
                if proc.wait():
                    raise ValueError(f'FFmpeg stopped in pass {n}: ' + files.one_line((staging / f'pass{n}.log').read_text(errors='replace')[-600:]))
        size = out.stat().st_size
        if size > size_mb * 1e6:   # the size asked is a ceiling: a file over it is not put out as if it were met
            raise ValueError(f'the video came out at {size / 1e6:.2f} MB, over the {size_mb:g} MB asked, and is not written; ask for '
                             f'{math.floor(size_mb * size_mb * 1e6 / size * 95) / 100:g} MB, which aims that much lower')
        try:
            files.publish_new(out, output)   # never in the place of a file that took the name while the video was made
        except FileExistsError:
            raise ValueError(f'{output} was made by something else while the video was encoded; it is left as it is') from None
    finally:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
    return files.joined([f'Wrote {output}: {width}x{height} at {fps} frames a second, {seconds:.1f} s, {size / 1e6:.2f} MB '
                         f'(under the {size_mb:g} MB asked; {vcodec} at {vbr // 1000} kbps, {acodec} at {abr // 1000} kbps).',
                         'The sound is the master as rendered; the picture shows the notes as they were played.'])
