# Skybutton Speedway

An 8-bit chiptune for a title screen: a 90-second loop in D major on two pulse waves, a triangle bass and noise drums. Made by GPT-6 Luna (max effort, in Codex) with this skill's version 0.6.0, in one take from the prompt below.

Listen: [Skybutton Speedway](https://github.com/owoevan-dev/music-skill/releases/download/examples-4/skybutton-speedway.mp3) (1:31).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> An 8-bit chiptune for the title screen of a retro platform game, about ninety seconds, looping without a seam: two pulse-wave voices, a triangle bass and noise drums, and nothing else. A bright tune that catches at once, a fast arpeggio or two, a second section, and back to the top.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked the score with
`review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody edited the result.

## Files

- `compose.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts.
- `song.json`: the project as it was rendered.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py --revision 3
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again with the same notes. This script gives a note the id it had in the project of the round before, which it reads from `song.json` beside it, so it writes the published notes only beside the published project; each run also adds an entry to the project's `revision_history`, the one difference from the published file. The render needs no sound bank: every part plays on the skill's own synthesizer. The render also writes the piece as a seamless loop (`loop.wav` and `loop.ogg`, with the loop points in them). Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
