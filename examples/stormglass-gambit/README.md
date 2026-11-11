# Stormglass Gambit

A looping battle theme for a game, led by synthesizers: 112 bars in G minor at 148 BPM, on Surge XT patches and the skill's drum machine. Made by Claude Fable 5.2 (xhigh effort, in Claude Code) with this skill's version 0.6.0, in one take from the prompt below.

Listen: [Stormglass Gambit](https://github.com/owoevan-dev/music-skill/releases/download/examples-4/stormglass-gambit.mp3) (3:07).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A battle theme for a game, led by synthesizers on Surge XT: high energy, about three minutes, and it must loop without a seam (deliver the loop as well as the preview). The lead is a synthesizer, not a sampled distorted guitar and not a saxophone. It will be heard on repeat, so give it a hook that holds up, a section that contrasts, and a build back into the top.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked the score with
`review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody edited the result.

## Files

- `compose.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts.
- `song.json`: the project as it was rendered.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again, the same project. The render needs no sound bank: every part plays on Surge XT or the skill's own drum machine and noise. 10 of its parts play on Surge XT and its patches, which `bootstrap.py` installs; without Surge XT they play their fallback presets on the built-in synthesizer, and the render's report says so. The render also writes the piece as a seamless loop (`loop.wav` and `loop.ogg`, with the loop points in them). Rendered again from scratch on the computer that made it, with the skill as published, every part not played by Surge XT came out identical, sample for sample, to the render the recording comes from. Surge XT starts its oscillators at random phases, so each time it synthesizes a part it plays a new take of the same sound; the render cache, not the renderer, keeps a take.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
