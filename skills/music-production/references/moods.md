# Moods across styles: which cues carry happy, sad, calm and frightening music

Read this when a brief names a mood (joyful, melancholy, calm, uneasy, nostalgic) as well as, or instead of, a style.
A mood is not a style map entry: it moves the cues inside whatever style the piece takes ([style-maps.md](style-maps.md)).
Words for a quality of sound or motion (bright, warm, thick, bouncy) and the wider vocabulary of musical emotion are in
[character-words.md](character-words.md).
Write the style's traits from its map, then push the cues below in the mood's direction as far as the style allows.

Contents: [The measured cues](#the-measured-cues) · [Four moods](#four-moods) ·
[Unease and the uncanny](#unease-and-the-uncanny) · [Elation at a peak](#elation-at-a-peak) ·
[Nostalgia](#nostalgia) · [On the engine](#on-the-engine) · [Sources](#sources)

## The measured cues

Eerola, Friberg and Bresin (2013) varied six cues independently over four pieces and had listeners rate 200
versions as happy, sad, peaceful and scary. The levels they used:

| Cue | Levels |
|---|---|
| Mode | the piece in major (Ionian), or translated to natural minor (Aeolian), the V–I becoming v–i |
| Tempo | 1.2, 2, 2.8, 4.4 and 6 notes per second: the average number of non-simultaneous onsets per second over all voices, the medians of emotions players chose in an earlier production study |
| Dynamics | −10, −5, 0, +5 and +10 dB, roughly pp to ff, the timbre changing with the level as on the instrument |
| Articulation | note length over the time to the next note: 1 (legato), 0.75, 0.5, 0.25 (staccatissimo) |
| Timbre | the melody on flute, horn or trumpet, from least to most bright (brightness read from the share of spectral energy below 1500 Hz) |
| Register | the melody's average pitch at F3, B3, F4, B4, F5 or B5 |

What they found:
- The cues together, coded linearly, explained 77–89% of the ratings; the cues added up rather than interacting.
- Mode mattered most overall, then tempo, register, dynamics, articulation and timbre, but the order differed by
  emotion: mode decided happy and sad and mattered little for peaceful and scary; dynamics mattered for scary and
  peaceful and little for happy and sad.

## Four moods

The direction of each cue in Eerola, Friberg and Bresin's (2013) regressions:

| Mood | Mode | Tempo | Register | Dynamics | Articulation | Timbre |
|---|---|---|---|---|---|---|
| Happy | major, the strongest cue | fast | high | no effect | staccato | no effect |
| Sad | minor, the strongest cue | slow | slightly low | softer | legato | darker |
| Peaceful | major | slow | high | soft, a strong cue | legato | darker, a strong cue |
| Scary | minor | slightly faster | low, a strong cue | loud | no effect | brighter |

For scary music, the structure of the piece itself carried most of the rating: the cues alone do not make a passage
frightening ([style-map-horror.md](style-map-horror.md) has the devices that do).

## Unease and the uncanny

The horror and suspense map gathers the devices of fear: instability that does not settle, an expectation kept
waiting, the signals of alarm (scream-like roughness, voices, heartbeats) and the startle
([style-map-horror.md](style-map-horror.md), with the studies each rests on). Unease in another style borrows from it: a
borrowed `harmony` from `horror/drone-dread` for an unresolved drone under a pop or orchestral piece, with the
reason in `decisions`. The cue table adds: low register, minor mode and loud dynamics for the frightening end, soft
dynamics and slow tempo held under it for dread.

## Elation at a peak

- The drop of a dance track's break routine drew listeners' strongest physiological response of the routine, and
  they described the experience as energising and bodily (Solberg and Dibben 2019, in [electronic.md](electronic.md)).
  The build that leads to it raises energy by crescendos, rising pitch slides, filter sweeps and the snare roll
  ([style-map-electronic.md](style-map-electronic.md), Shared by the dance styles).
- A chorus more intense than its verse, denser or higher (Summach 2012, in
  [pop-and-ballad.md](pop-and-ballad.md)), and the cue table's happy direction: major, fast, high, short notes.

## Nostalgia

- Lo-fi hip-hop plays with nostalgia for older media, its worn tape and vinyl added on purpose (Winston and Saywood
  2019; [beats.md](beats.md), The worn sound).
- Synthwave revives the sound of 1980s film scores and pop with nostalgia for the decade (Merlini 2023; WP Synthwave,
  read 9 November 2026; [style-map-electronic.md](style-map-electronic.md), Synthwave).
- No source read measures which musical cues make music sound nostalgic; the worn sound and the retro timbres above
  are the styles' own means, not a measured cue.

## On the engine

- Tempo as notes per second: the study counts the moments at which any voice starts a note, onsets struck together
  counting once (non-simultaneous onsets over all voices), so a slow tempo with many notes in turn reads as fast, a
  chord as one onset. Count those moments over a passage against the cue's levels (1.2 to 6 a second).
- Dynamics: velocities and `level_dbfs`; a 20 dB range from pp to ff is an acoustic instrument's (Eerola, Friberg and
  Bresin 2013, after Fletcher and Rossing).
- Articulation: note lengths, or `gate` in `performance.notes` (1 legato, 0.5 staccato).
- Timbre: a darker or brighter instrument or patch; `studio.py sounds --character dark` or `bright` searches the Surge
  catalog by its measured brightness ([sound-selection.md](sound-selection.md)).
- Register: the melody's average pitch; the study's range runs from F3 to B5.

## Sources

- Eerola, T., Friberg, A. and Bresin, R. (2013). [Emotional expression in music: contribution, linearity, and
  additivity of primary musical cues](https://doi.org/10.3389/fpsyg.2013.00487). *Frontiers in Psychology* 4:487.
- Ireland, D. (2023): in [style-map-horror.md](style-map-horror.md).
- Merlini, M. (2023); Solberg, R. T. and Dibben, N. (2019): in [electronic.md](electronic.md).
- Summach, J. (2012), in Open Music Theory: in [pop-and-ballad.md](pop-and-ballad.md).
- Winston, E. and Saywood, L. (2019): in [beats.md](beats.md).
