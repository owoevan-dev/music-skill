# Battle Reel of the Stork-Rider

Battle music for a fantasy story, played by a folk band (fiddle, clarinet, strumstick, guitar, folk harp, double bass, cello and hand drums): 122 bars at 168 BPM, a reel in E Dorian against a stamping tune in E Freygish, a hush between, and a last reel a step higher. Made by Claude Opus 5.5 (xhigh effort, in Claude Code) with a pre-release copy of this skill's version 0.7.0, in one take from the prompt below.

Listen: [Battle Reel of the Stork-Rider](https://github.com/owoevan-dev/music-skill/releases/download/examples-5/battle-reel-of-the-stork-rider.mp3) (2:58).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> Battle music for a fantasy story, played by a folk band and not by an orchestra: a fiddle or another solo string, a wind instrument, plucked strings, a bass and hand drums, whatever the banks give for it. Fast and driving, about three minutes. The fight changes sides more than once: let the music switch between two or three sections of different harmony and character (a running, reel-like one, a heavier stamping one, a moment of held breath), with the tune passing from instrument to instrument, and end on a blow.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `build_song.py`, checked
the score with `review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody
edited the notes it wrote.

## From twelve words to a plan

Before deciding what the brief left open, the agent drew twelve words at random for the piece with `studio.py words`: *drip*, *prickly*, *papaya*, *chisel*, *stork*, *snail*, *licorice*, *bracelet*, *cot*, *waddle*, *hover*, *melt*. It linked
the brief and all twelve into one whole, as the second step of [SKILL.md](../../skills/music-production/SKILL.md) asks, and wrote it into
the project:

> At the edge of a papaya grove, where the marsh meets the village, a stork-rider guards a child asleep in a reed cot. Hedge-goblins with prickly backs waddle up out of the mud in stamping ranks, bracelets of snail shells rattling on their wrists. The stork hovers and strikes and the reel runs; the goblins stamp back in their crooked mode; the fight swings twice. In the hush between, rain drips from the thatch, the goblin shaman's licorice-black charm melts in the fire and a snail-slow spell coils round the cot, until the village carver steps out and ends it with one blow of a chisel.

What the whole gave the music, in the agent's words (`association.gives` in `song.json`):

| | What | Where |
|---|---|---|
| Form | the fight swings: the stork's reel against the goblins' stamp twice, the hush of the spell between, and one chisel blow as the ending | all sections; the blow in bar 122 |
| Harmony | the stork's bittersweet E Dorian (licorice) with the papaya's warm borrowed major chords G, C and D in the B-strain; the goblins' prickly E Freygish on the same tonic (F natural and the augmented second F-G#); the melting chords Cmaj7, Bm7, Bbmaj7, Am7 sliding down by semitones in the hush | reel_b bars 21-36 and 103-110; stamp_1, stamp_2; breath bars 69-76 |
| Melody | the stork's stride (the A-strain opens with leaps E4-B4-E5) and its hovering round B4; the snail's spiral, the clarinet's intervals shrinking 9, 7, 5, 3, 2, 1 toward A3 | fiddle intro and reel_a; clarinet in breath |
| Rhythm | the goblins' waddle as 3+3+2 stamps (beats 1, 2.5, 4), taken over by the reel at the end; the drips falling at uneven places; the chisel as the guitar's chopped chords and the final stroke | stamp_1, stamp_2, reel_f1-reel_f3, coda; harp in breath |
| Sounds | the clarinet, the 'licorice stick', as the band's wind; the folk harp as the cot's lullaby in the hush; shaker and finger cymbals as the snail-shell bracelets | clarinet throughout; harp in breath; hand percussion in the stamps |

Its plan (`plan` in `song.json`) says what identifies the piece and where its high point is, and `review` read the score against it:

> A reel that is fought over: the stork's running E Dorian tune and the goblins' 3+3+2 Freygish stamp trade the field, the tune handed from fiddle to clarinet to strumstick to cello, until the reel, a step higher, swallows the stamp and a single blow ends it.

The high point, in the section `reel_f2`: key lifted a whole step to F# Dorian the section before; every part sounds; the clarinet's B-strain peaks on C#6 under the fiddle's E6, the highest note of the piece; the cello's counter-line enters; claps and darbuka on top of the reel drum.

## Files

- `build_song.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts.
- `song.json`: the project as it was rendered.
- `association.json`: the record of the twelve words, as `studio.py words` wrote it beside the project; the script reads the words from it.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python build_song.py
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again, the same project. The render needs the sound banks `bass_sneaky`, `cello_bigcat`, `guitar_shiny`, `vcsl_world`, `vsco`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project files are code, under the repository's MIT licence.
