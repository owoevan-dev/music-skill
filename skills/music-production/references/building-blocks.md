# Building blocks: a drum groove, a bass line and an accompaniment to start from

Read this when a part needs a groove, a bass line or a comping figure that the piece's own decisions can describe.
`musiclib.blocks` writes the notes as a starting point, and the composition script puts them in the part and edits
them. Nothing a block writes has been heard. Whether it suits the piece is a listening question, as for every note.

Contents: [Settings, not defaults](#settings-not-defaults) · [Drums](#drums) · [The drummers' feels](#the-drummers-feels) ·
[Candidates](#candidates) · [Bass](#bass) · [Accompaniment](#accompaniment) · [Into a part](#into-a-part) ·
[Where the numbers come from](#where-the-numbers-come-from) · [Sources](#sources)

## Settings, not defaults

Professional tools work this way:
- Logic Pro's Drummer sets complexity and loudness on an XY pad, with fills, swing, feel, ghost notes and hi-hat
  openness, each region on its own (Apple).
- Its Session Players follow the chord track. Every player takes a pattern, a bar of sixteenths whose brighter dots are
  the main accents and whose dimmer ones are played as complexity rises, with complexity, intensity and fills; the Bass
  Player adds octave jumps, slides, dead notes and the longest a note may last (Apple).
- Ableton Live 12's generators place a chosen density of notes among the steps and rotate Euclidean rhythms (Ableton).

Tools also make work alike:
- Writers given a GPT-4 idea wrote better-rated stories that were more alike, anchored on the idea. With five ideas to
  choose from, their stories were still more alike than those of writers alone (Doshi and Hauser 2024).
- A tool answers different users' similar requests with similar output (Anderson, Shah and Kreminski 2024).

So the blocks ask for the piece's decisions:
- **No defaults.** Every musical setting, and the seed, must be given; a call without them stops and names what to
  decide. Derive each from the brief and the energy plan (development-and-groove.md), never from a habit.
- **The piece's seed.** `blocks.seed(title)` turns the title into a seed. The same call gives the same notes when the
  script runs again, and other notes in another piece. Never reuse one piece's seed in another.
- **The piece's own material.** Give the comping the melody and the bass line: it answers them (below). Give the bass
  a rhythm of the piece's own with `figure='pattern'`, or the kick's with `figure='kick'`.
- **Candidates.** `blocks.candidates` returns several parts for one setting, spread over density and syncopation.
  Choose one for the brief and say why in the project's decisions. Choosing among several does not remove the anchor
  (Doshi and Hauser's writers with five ideas still wrote alike), so change the one chosen where the piece asks.
- **What is typical.** The record's `typical` names a choice that is its style's most common form, such as the basic
  rock beat. That is fine when the brief asks for it. Otherwise move something: the kick, the pulse, a section's
  backbeat.
- **Edit.** The notes are a draft: vary the bars a hook or a lyric line needs, and give the transitions their own
  moves (development-and-groove.md).

## Drums

```python
from musiclib import blocks
s = blocks.seed(project['title'])
groove = blocks.drums(bars=32, meter=[4, 4], seed=s, sections=project['sections'],
                      feel={'verse': 'soul', 'chorus': 'rock', 'bridge': 'soul'},
                      backbeat={'verse': 'normal', 'chorus': 'normal', 'bridge': 'half'},
                      kick={'verse': 'syncopated', 'chorus': 'four_floor', 'bridge': 'syncopated'},
                      pulse={'verse': 'eighth', 'chorus': 'sixteenth', 'bridge': 'quarter'},
                      cymbal='closed_hat', complexity={'verse': .4, 'chorus': .6, 'bridge': .3},
                      intensity={'verse': .5, 'chorus': .85, 'bridge': .4}, fills=.5)
blocks.add(drum_track, groove, 'd')
```

A pop drumbeat is three layers (Open Music Theory, Drumbeats). The layers say where the backbeat, the kick's anchor and
the cymbals go; the feel says how professional drummers filled them in. Each setting may be one value or one per
section id:

| Setting | Values | From |
|---|---|---|
| `feel` | one of `blocks.FEELS` ([below](#the-drummers-feels)) | the drummers' statistics |
| `backbeat` | `normal` (2 and 4; beat 3 in triple meter), `half` (beat 3), `double` (every off-beat eighth), `dembow` (the last two parts of a tresillo, each half-bar, with `kick` `four_floor`), `blast` (every second sixteenth, the kick between), `eighths` (every eighth), `none` | the most stable layer: Open Music Theory; the blasts: Wikipedia, Blast beat |
| `kick` | `one_three`, `four_floor`, `syncopated` (the downbeat, the rest where the feel puts its kicks), `tresillo` (3+3+2 eighths), `euclidean` (an even spread, rotated: Toussaint 2005), `eighths` (every eighth), `double` (every sixteenth, the double kick), `none` | the most flexible layer, often syncopated, still on the downbeat: Open Music Theory; the double kick: [rock-and-metal.md](rock-and-metal.md) |
| `pulse` | `quarter`, `eighth`, `sixteenth`, `offbeat`, `feel` (the cymbal where the feel's drummers played it, step by step in proportion), `none` | the cymbals' regular pulse: Open Music Theory |
| `cymbal` | `closed_hat`, `open_hat`, `ride`, `shaker` (the shaker takes the closed hat's accents) | |
| `complexity` | 0 to 1: how many kicks, other snares and open hats a bar holds, at this quantile of the drummers' bars in the feel (0.5 is their median bar) | Drummer's XY pad; the drummers |
| `intensity` | 0 to 1: velocities from the drummers' 10th percentile to their 90th, drum by drum and step by step | Drummer's loudness; the drummers |
| `fills` | 0 none. Otherwise a fill ends each section, and inside a section one comes every so many bars: this quantile of the drummers' spacing (0.5 their median, 1 their closest) | Dow 2010; Drummer's Fills knob; the drummers |

Also:
- `variation` (0 to 1; complexity when not given): how often a bar departs from the groove, and by how many kicks, at
  this quantile of the drummers' performances (0 the most repetitive, 1 the most varied). The drummers improvised, so
  even 0 varies more than a programmed loop; give a loop `phrase_bars=1` or edit it.
- `backbeat_sound`: `snare`, `clap` or `rim`. Off-backbeat snares, ghost notes among them, come with `snare`.
- `rolls` (0 to 1): trap's hi-hat rate changes on a sixteenth pulse, thirty-seconds or triplets on a bar's last beat
  (beats.md).
- `phrase_bars` (1, 2, 4 or 8): the cycle over which the bars vary.
- `programmed=True`: one velocity per drum, as a step sequencer plays.
- `pattern`: the groove written on a step sequencer's grid instead of the layers, one bar per voice: `{"kick": "x...x...x...x...", "snare": "....x.......x...", "closed_hat": "xoxoxoxoxoxoxoxo"}`, sixteen steps in 4/4 (twelve in 6/8), `x` a hit, `o` a probable hit taken with complexity's probability (drawn per bar of the phrase), `.` a rest. The voices: `kick`, `snare`, `clap`, `rim`, `closed_hat`, `pedal_hat`, `open_hat`, `ride`, `crash`, `tom_high`, `tom_mid`, `tom_low`. Leave `backbeat`, `kick`, `pulse` and `cymbal` out; fills, intensity, the drummers' velocities and `programmed` apply as before. A style's documented pattern that no layer names goes here: reggae's one drop (kick and snare together on beat 3), a gallop doubled on the kick.

Metal's patterns from the layers (Wikipedia, Blast beat; [rock-and-metal.md](rock-and-metal.md)), with `complexity` 0 to keep them exact:
- the traditional blast beat, kick and snare alternating on sixteenths with the cymbal on the kick: `backbeat='blast'`, `kick='eighths'`, `pulse='eighth'`, `cymbal='ride'`, usually from about 180 BPM;
- the hammer blast, kick and snare together on eighths: `backbeat='eighths'`, `kick='eighths'`;
- the bomb blast, snare eighths over the double kick's sixteenths: `backbeat='eighths'`, `kick='double'`;
- the thrash or skank beat, kick and snare alternating on eighths with the ride on every eighth: `backbeat='double'`, `kick='four_floor'`, `pulse='eighth'`, `cymbal='ride'`;
- power metal's constant double kick under the backbeat: `kick='double'`, `backbeat='normal'`.
The record's `typical` names each when it is built.

A fill takes its length and its drums from the drummers' fills in the feel: the cymbals stop (Open Music Theory), at
most two hand drums play at a time (Dow 2010: four limbs), and a crash follows on the next downbeat as often as it did
after theirs. Straight feels need a meter that beats in quarter notes (2/4, 3/4, 4/4, 5/4); the shuffle feels need
6/8, 9/8 or 12/8, so write a 4/4 shuffle in 12/8. In a meter other than 4/4 or 12/8 each beat borrows from a 4/4 beat:
the first from the first, a backbeat (Open Music Theory: beat 3 in triple meter) from beats 2 and 4, any other beat
from beat 3.

The styles' patterns are in their guides: [beats.md](beats.md), [electronic.md](electronic.md),
[rock-and-metal.md](rock-and-metal.md) and [jazz-and-funk.md](jazz-and-funk.md). The block's settings express them;
the guides say which.

## The drummers' feels

Measured here from the Groove MIDI Dataset: professional drummers on an electronic kit, playing to a click in the
styles they named (Gillick et al. 2019). Each feel holds at least 200 bars from at least two drummers, none playing
more than 80% of them. Medians, with the 10th and 90th percentiles:

| feel | read on | bars | drummers | kicks a bar | other snares a bar | open hats a bar | snare on 2 and 4 | fill bars | a fill every (bars) | crash after a fill |
|---|---|---|---|---|---|---|---|---|---|---|
| afrocuban | sixteenths | 499 | 2 | 4 (2-6) | 4 (0-7) | 0 (0-1) | 8% | 9% | 4 | 40% |
| dance | sixteenths | 479 | 2 | 4 (2-6) | 0 (0-6) | 0 (0-5) | 77% | 12% | 4 | 28% |
| funk | sixteenths | 2099 | 4 | 4 (2-6) | 4 (0-8) | 1 (0-2) | 61% | 10% | 4 | 38% |
| hiphop | sixteenths | 716 | 5 | 5 (3-7) | 1 (0-6) | 0 (0-5) | 64% | 8% | 4 | 13% |
| jazz | sixteenths | 1561 | 5 | 2 (0-5) | 3 (0-9) | 0 (0-1) | 34% | 9% | 3 | 26% |
| jazz_shuffle | triplet eighths | 469 | 3 | 1 (0-4) | 1 (0-4) | 0 (0-1) | 9% | 8% | 6 | 28% |
| latin | sixteenths | 3008 | 4 | 5 (3-8) | 6 (1-12) | 0 (0-1) | 23% | 9% | 3 | 13% |
| latin_shuffle | triplet eighths | 235 | 2 | 1 (1-4) | 0 (0-2) | 0 (0-0) | 31% | 7% | 2 | 0% |
| neworleans | sixteenths | 657 | 4 | 5 (2-8) | 10 (3-14) | 0 (0-2) | 62% | 9% | 3 | 38% |
| rock | sixteenths | 4814 | 9 | 4 (1-6) | 1 (0-6) | 0 (0-3) | 62% | 12% | 4 | 38% |
| rock_shuffle | triplet eighths | 791 | 6 | 4 (1-6) | 1 (0-4) | 0 (0-3) | 63% | 11% | 4 | 42% |
| soul | sixteenths | 548 | 4 | 3 (2-6) | 2 (0-5) | 0 (0-2) | 83% | 9% | 4 | 59% |

Pop, punk, reggae, country, blues, afrobeat and the other labels had too few bars or came mostly from one drummer.
For a style outside the table, choose the feel nearest in its placements and say why; for electronic styles, a feel's
placements with `programmed=True`. The data's limits: ten drummers, two of whom played over half the files; an
electronic kit; improvised takes. Its jazz is mostly straight-eighth jazz, its swing the shuffle feel.

## Candidates

```python
options = blocks.candidates(n=4, bars=8, meter=[4, 4], seed=s, feel='funk', backbeat='normal', kick='syncopated',
                            pulse='sixteenth', cymbal='closed_hat', complexity=.5, intensity=.7, fills=.3)
for o in options:
    print(o['seed'], o['density'], o['syncopation'], o['kick_steps'])
line_options = blocks.candidates(block='bass', n=3, chords=chords, meter=[4, 4], seed=s, figure='walking',
                                 complexity=.6, intensity=.6, low=28, high=52, push='none', fills=.5)
```

Several parts for one setting, made from seeds derived from the piece's seed. They are picked to lie as far apart as
possible in onset density and syncopation (Longuet-Higgins and Lee's measure, as `review` computes it): the spread of
quality-diversity search (Mouret and Clune 2015), without its measure of which is best, which is the agent's
judgement for the brief. The seed of the one chosen gives it again: call the block with it. A drum candidate's
`kick_steps` are sixteenths from the downbeat; its density follows complexity, so its candidates differ in placement.

## Bass

```python
line = blocks.bass(chords, [4, 4], seed=s, figure='root_fifth', complexity=.4, intensity=.7, low=28, high=52,
                   push='phrase', fills=.5)
```

`chords` holds one symbol per bar, or per bar a list of (beat in the bar, symbol). Each `figure` comes from the
guides or the Session Players:

| `figure` | The line | From |
|---|---|---|
| `root` | the root on each chord | development-and-groove.md |
| `root_fifth` | the root on the downbeat, the fifth on the half-bar (the two-feel) | jazz-and-funk.md |
| `eighths`, `octaves` | the root in driving eighths, or root and octave | rock-and-metal.md (punk's eighths) |
| `kick` | the kick's rhythm: pass the drums result as `kick=` | development-and-groove.md: a rhythmic cell shared with the kick |
| `funk` | the root on the One; each sixteenth off the beat taken with complexity's probability, an octave, the root or a ghost note (the seed choosing uniformly); the space before the next One left | jazz-and-funk.md |
| `bossa` | the root on 1, the fifth on the "and" of 2 and on 3, the root on the "and" of 4 | jazz-and-funk.md (TalkingBass 2019) |
| `walking` | quarter notes: the root on beat 1, chord and scale tones by step on 2 and 3, and before a change a half step above or below the next root, or its fifth | jazz-and-funk.md; the scales from Open Music Theory's chord-scale table |
| `pattern` | the piece's own rhythm, `pattern=` a bar of sixteenths: `x` a hit, `o` a probable hit (complexity is its probability, drawn again in each bar of the phrase), `.` a rest; the chord's root on each hit | Logic Pro's Session Player patterns |

The settings:
- `push` (`none`, `phrase`, `changes`): the note of a chord change struck an eighth early and held over it, at every
  change or at the first of each phrase (development-and-groove.md: pushes; jazz-and-funk.md: push the root where the
  guitar pushes the chord).
- `fills` (0 to 1): the probability that a phrase end runs to a half step from the next root through the chord's
  tones and scale: the last beat in eighths, or above complexity 0.5 the last two beats in sixteenths, on slots the
  seed keeps (development-and-groove.md: the bass's last bar answering; the Session Players' fills).
- `complexity`: also the probability that any other change is approached by a whole step from a tone of the chord,
  which kept the motion without the rub a chromatic approach gave (arrangement.md).
- `octaves` (optional, 0 to 1): the probability that a later note of a chord leaps an octave (the Bass Player's
  octave jumps).
- `phrasing` (optional, beats): the longest a note lasts, as the Bass Player's Phrasing sets it; otherwise each note
  lasts until the next.
- `low` and `high` are MIDI numbers; the range needs an octave or more.

Velocities sit at intensity's place between pp (32) and ff (112) on MuseScore's table of dynamics (mp 64, mf 80); a
probable hit one marking softer; a ghost note at ppp (16). The block writes no slides or dead notes: a slide is the
track's `performance.legato` (`portamento_ms`) or `performance.bend` ([schema.md](schema.md)).

The figures of steady notes (`eighths`, `octaves`, `walking`) keep their rhythm from piece to piece; their pitches,
fills and pushes differ. For a rhythm of the piece's own, use `pattern` or `kick`.

## Accompaniment

```python
comp = blocks.accompaniment(chords, [4, 4], seed=s, figure='syncopated', complexity=.5, intensity=.6,
                            low=52, high=74, voices=4, push='phrase', melody=lead_notes, bass=line['notes'])
```

The pitches come from `voice_lead` ([development-and-groove.md](development-and-groove.md)). Given the melody's notes,
the voicing stays a minor third under its lowest pitch in each chord and keeps clear of its pitches. The figures are
those development-and-groove.md gives for accompaniment that moves (after Owsinski and Israels):

| `figure` | The part |
|---|---|
| `held` | each voicing held; a chord that can take it has its third delayed by the fourth for a beat, a 4-3 suspension resolving, with complexity's probability |
| `broken` | the chord broken into eighths (sixteenths above complexity 0.5), up, down or both, the seed choosing per chord |
| `alternating` | the lowest tone on the beat, the rest of the chord on the "and" with complexity's probability |
| `syncopated` | short chords with rests: the change struck, each other free eighth taken with complexity's probability |
| `strum` | the chord down on the beats and up on the "and"s, each upstroke taken with complexity's probability, for a guitar: set `strum` in musiclib.expression's overrides |
| `offbeat` | the skank: a short damped chord on each off-beat, and with complexity's probability the double skank, a second stroke a sixteenth later (Wikipedia, Reggae; Ska). Reggae's chord on 2 and 4 alone is a `pattern` |
| `pompe` | gypsy jazz's la pompe: four staccato downstrokes a bar with a slight emphasis on beats 2 and 4, and a quick upstroke before 1 and 3 (Persinger 2014; the emphasis on 2 and 4 also Wikipedia, Gypsy jazz). The upstroke plays the chord of the beat it leads into, across a change too, and none comes before the first beat; 1 and 3 a dynamic step softer and the upstroke an eighth of a beat long are this skill's choices. There are many regional variants of la pompe (Persinger) |
| `batida` | the bossa nova guitar's beat: in 4/4 the chord on 1, 2 and the "and" of 3, an eighth long (in 2/4, both eighths of beat 1 and the second sixteenth of beat 2: Wikipedia, Bossa nova, in [jazz-and-funk.md](jazz-and-funk.md)); a pushed chord (`push`) rings over the bar line. The thumb's bass on 1 and 3 is the bass block's `bossa` figure, or `keep_root` |
| `pattern` | the piece's own rhythm, as for `bass`, the whole voicing on each hit |

Where a length has no source, a short chord (`syncopated`, `alternating`'s chord) lasts a sixteenth or an eighth, the
seed choosing uniformly; the other figures last until the next attack, or `phrasing` beats at most.

**Answering.** Given `melody` or `bass` (the notes of those parts), the comping's optional hits leave the eighths where
they strike: commentary on the melody rather than its rhythm, chords in answer to the bass (Israels; Owsinski's
fills answer the lead). The change itself is always struck. `answer=False` turns it off. `push` is as for `bass`; a
pushed chord rings over the downbeat.

Without a bass part, pass `keep_root=True` (voice_lead).

The figures of short notes (`broken`, `alternating`, `syncopated`, `strum`) need a sound that speaks at once: a piano,
keys, a pluck, a guitar or an organ. A slow pad never reaches its level on a stab: `warm_pad`'s attack is 1.2 s
(references/synth-presets.json). Each note also costs its whole release to synthesize. Measured here, 280 stabs on
`warm_pad` took 370 s against 3 s for the drums. Give a pad the `held` figure.

## Slides and articulation

- `blocks.slides(notes, share, seed)`: with `share`'s probability, a note followed by one of another pitch is held an eighth of a beat into it, so that on a patch that glides between overlapping notes (Surge with `surge.glide_ms`, a `mono` built-in patch) the second slides from the first: UK drill's sliding 808 (Wikipedia, UK drill), acid house's slide per step (Wikipedia, Acid house). The seed chooses which; notes struck together are left alone.
- `blocks.articulate(notes, ratio)`: each note's length set to `ratio` times the time to the next onset, chords sharing it. Eerola, Friberg and Bresin (2013) varied articulation at 1 (legato), 0.75, 0.5 and 0.25 (staccatissimo); shorter notes moved listeners' ratings toward happy, legato toward sad and peaceful ([moods.md](moods.md), [character-words.md](character-words.md)). The last onset keeps `ratio` of its own length.

## Into a part

`blocks.add(track, result, prefix)` appends the notes to a track with ids `prefix`0, 1 and so on, and each velocity
(and `gate`, if given) under `performance.notes`. The block's `record` says what it chose: the seed, the feel, the kick
and backbeat steps, `typical`. Keep it in the project's decisions. `musiclib.expression` (with `drift='time'`) adds
the player's drift afterwards, and `review` reads the result as it reads every part.

## Where the numbers come from

Every number a block uses is one of these:
- **The drummers'**: [drum-statistics.json](drum-statistics.json), made by `research/gmd-drums/gmd_drum_stats.py` from
  the Groove MIDI Dataset's MIDI: where each drum falls in the bar, its velocities by step (10th to 90th percentile),
  the notes a bar holds, how often and by how much the bars depart from the groove, and the fills' lengths, drums,
  velocities, spacing and crashes. Aggregate numbers only; no performance is copied.
- **A tool's or a source's**: MuseScore's velocities for the dynamic markings; the chord-scale table; the layers and
  figures of the guides.
- **A definition of a setting**: a quantile, a probability or a share the agent chooses, such as complexity 0.6.
- **Uniform**: where no source gives a frequency, the seed picks evenly among the options (a sixteenth or an eighth;
  the octave, the root or a ghost note).

## Sources

- Anderson, B. R., Shah, J. H. and Kreminski, M. (2024). Homogenization effects of large language models on human
  creative ideation. *Creativity and Cognition '24*; [arXiv 2402.01536](https://arxiv.org/abs/2402.01536): group-level
  sameness from one tool's similar output; randomness from a large pool, quality-diversity and intent elicitation
  proposed as remedies, and the inference that users told what a tool tends to suggest might resist it, none of them
  tested in the study.
- Apple. *Logic Pro User Guide*, [Edit a drummer's performance](https://help.apple.com/logicpro/mac/10.4/en.lproj/lgcp898c7532.html):
  the XY pad, fills, swing, feel, ghost notes, hi-hat, phrase variation, settings per region.
- Apple. *Logic Pro User Guide* (Logic Pro 13), [Edit a Session Player performance](https://support.apple.com/guide/logicpro/lgcp74b34026/mac)
  and [Edit a Bass Player performance](https://support.apple.com/guide/logicpro/lgcp719a5d95/mac): patterns of main
  and probable accents on sixteenths, complexity, intensity, fill amount, swing, feel, dynamics; the Bass Player's
  melody notes, octave jumps, phrasing, lowest note, dead notes, slides.
- Ableton. *Live 12 Reference Manual*, [MIDI Tools](https://www.ableton.com/en/manual/midi-tools/): the Rhythm,
  Seed and Euclidean generators.
- Doshi, A. R. and Hauser, O. P. (2024). Generative AI enhances individual creativity but reduces the collective
  diversity of novel content. *Science Advances* 10, eadn5290: stories more alike, anchored on the idea shown, with one
  idea or five to choose from (by 10.7% and 8.9% of the human-only stories' range).
- Dow, R. (2010). [Programming Realistic Drum Parts](https://www.soundonsound.com/techniques/programming-realistic-drum-parts).
  *Sound On Sound*, September 2010: four limbs, a fill at the end of an eight-bar section.
- Gillick, J., Roberts, A., Engel, J., Eck, D. and Bamman, D. (2019). Learning to groove with inverse sequence
  transformations. *ICML 2019*. The [Groove MIDI Dataset](https://magenta.tensorflow.org/datasets/groove), Google
  LLC, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): 13.6 hours by ten drummers, over 80% of it by hired
  professionals, on a Roland TD-11 to a click; the statistics in drum-statistics.json are computed from its MIDI.
- Hanenberg, S. Drumbeats. *Open Music Theory*, [chapter](https://viva.pressbooks.pub/openmusictheory/chapter/drumbeats/):
  the backbeat, the kick and the cymbals as layers; half and double time; four on the floor; dembow; the kick on the
  downbeat despite syncopation; the cymbal pulse stopping for a fill.
- MuseScore. [Soundfont, MIDI velocity and instruments.xml](https://musescore.org/en/handbook/developers-handbook/references/instrumentsxml-documentation):
  the MIDI velocities of MuseScore 3's dynamic markings (ppp 16, pp 32, p 48, mp 64, mf 80, f 96, ff 112, fff 126).
- Mouret, J.-B. and Clune, J. (2015). Illuminating search spaces by mapping elites. [arXiv 1504.04909](https://arxiv.org/abs/1504.04909):
  many high-performing yet different solutions rather than one.
- *Open Music Theory*, [Chord-Scale Theory](https://viva.pressbooks.pub/openmusictheory/chapter/chord-scale-theory/):
  dorian for minor sevenths, mixolydian for dominant sevenths, ionian or lydian for major sevenths, locrian for
  half-diminished sevenths.
- Resnick, M. and Myers, B. (2005). Design principles for tools to support creative thinking: low threshold, high
  ceiling, wide walls.
- Toussaint, G. (2005). The Euclidean algorithm generates traditional musical rhythms. *Bridges 2005*, 47–56:
  onsets as evenly spread as possible give many traditional timelines.
- Persinger, S. (2014). [Rhythm Rules: Gypsy Jazz Primer](https://www.premierguitar.com/rhythm-rules-gypsy-jazz-primer). *Premier Guitar*, 26 April 2014: la pompe as four staccato downstrokes with a slight emphasis on beats two and four, and with a quick upstroke before beats one and three.
- Israels, C., and Owsinski, B., in [development-and-groove.md](development-and-groove.md): comping as commentary on
  the melody, chords in answer to the bass; fills answering the lead.
- Eerola, T., Friberg, A. and Bresin, R. (2013). [Emotional expression in music: contribution, linearity, and
  additivity of primary musical cues](https://doi.org/10.3389/fpsyg.2013.00487). *Frontiers in Psychology* 4:487:
  articulation as note length over the time to the next note, at 1, 0.75, 0.5 and 0.25.
- Wikipedia, read 9 November 2026: [Blast beat](https://en.wikipedia.org/wiki/Blast_beat) (the traditional, hammer
  and bomb blasts, counted in sixteenths, from about 180 BPM), [Double bass drum](https://en.wikipedia.org/wiki/Double_bass_drum),
  [Reggae](https://en.wikipedia.org/wiki/Reggae) (the skank and the double skank, read 9 November in the Latin
  map's sources), [Ska](https://en.wikipedia.org/wiki/Ska), [Gypsy jazz](https://en.wikipedia.org/wiki/Gypsy_jazz)
  (la pompe), [Bossa nova](https://en.wikipedia.org/wiki/Bossa_nova) (the batida), [UK drill](https://en.wikipedia.org/wiki/UK_drill)
  and [Acid house](https://en.wikipedia.org/wiki/Acid_house) (slides).
