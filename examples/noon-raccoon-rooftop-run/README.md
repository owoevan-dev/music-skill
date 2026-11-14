# Noon Raccoon Rooftop Run

An 8-bit chiptune for the first level of a platform game, a 90-second loop: 48 bars at 128 BPM, G major with a detour to E minor, on two pulse waves, a triangle bass and noise drums. Made by GPT-6 Luna (xhigh effort, in Codex) with a pre-release copy of this skill's version 0.7.0, in one take from the prompt below.

Listen: [Noon Raccoon Rooftop Run](https://github.com/owoevan-dev/music-skill/releases/download/examples-5/noon-raccoon-rooftop-run.mp3) (1:31).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> An 8-bit chiptune for the first level of a retro platform game, about ninety seconds, looping without a seam (deliver the loop as well as the preview): two pulse-wave voices, a triangle bass and noise drums, and nothing else. A bright tune that catches at once, fast arpeggios standing in for chords, a second section in another key or mood, and back to the top.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked
the score with `review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody
edited the notes it wrote.

## From twelve words to a plan

Before deciding what the brief left open, the agent drew twelve words at random for the piece with `studio.py words`: *noon*, *scrub*, *wink*, *leak*, *lemon*, *gnarled*, *tumble*, *porch*, *raccoon*, *waffle*, *barge*, *kiln*. It linked
the brief and all twelve into one whole, as the second step of [SKILL.md](../../skills/music-production/SKILL.md) asks, and wrote it into
the project:

> At noon, a raccoon gives a wink from a porch and launches on a waffle barge across scrub. A leak swells into a shortcut past gnarled roots, a lemon bounces, and one tumble sends the raft by a sun-warm kiln before the runner returns to the porch.

What the whole gave the music, in the agent's words (`association.gives` in `song.json`):

| | What | Where |
|---|---|---|
| Form | The porch departure, drain detour, and porch return set a 16+16+16 bar A–B–A loop. | all sections |
| Harmony | The sunny launch and return sit in G major; the leaking shortcut shifts to E minor and uses B7 to turn home. | bars 1-48 |
| Melody | A compact leaping hook carries the wink; the lower, stepwise drain phrase is the tumble; the return restores the opening hook after the detour. | bars 1-48 |
| Rhythm | Sixteenth-note pulse arpeggios suggest the waffle barge's bounce; a single noise channel alternates thuds, snares and hats, with short phrase-end tumbles. | all sections |
| Timbre | Four console-like voices only: narrow pulse melody, arpeggiated pulse chords, 16-step triangle bass and clocked noise drums. | all sections |

Its plan (`plan` in `song.json`) says what identifies the piece and where its high point is, and `review` read the score against it:

> A short rooftop hook stated over a written 16th-note pulse arpeggio, with a low E-minor detour and a G-major return.

The high point, in the section `porch_return`: The opening hook returns after the lower detour; its lead and noise backbeat use the strongest section velocities, without adding tracks.

## Files

- `compose.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts.
- `song.json`: the project as it was rendered.
- `association.json`: the record of the twelve words, as `studio.py words` wrote it beside the project; the script reads the words from it.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again, the same project. The render needs no sound bank: every part plays on the skill's own synthesizer. The render also writes the piece as a seamless loop (`loop.wav` and `loop.ogg`, with the loop points in them). Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project files are code, under the repository's MIT licence.
