# Paper Lantern Hours

A lo-fi hip-hop beat in F major at 76 BPM that loops without a seam: a worn electric piano, an upright piano's motif, an upright bass and a swung kit. Made by Claude Sonnet 5.5 (medium effort, in Claude Code) with this skill's version 0.6.0, in one take from the prompt below.

Listen: [Paper Lantern Hours](https://github.com/owoevan-dev/music-skill/releases/download/examples-4/paper-lantern-hours.mp3) (2:10).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A lo-fi hip-hop beat of the kind people study to, about two minutes, looping without a seam: a mellow worn-tape piano or electric piano over jazzy seventh chords, a round bass, a laid-back swung drum pattern and a little tape or vinyl character. Keep it small, four or five parts, and let one simple melodic idea come back.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked the score with
`review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody edited the result.

## Files

- `compose.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts, and the default of `--out`, which named the piece's folder there and is now `song.json`.
- `song.json`: the project as it was rendered.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py --round 3
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again, the same project. The render needs the sound banks `bass_sneaky`, `rusty`, `vcsl_keys`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. One of its parts plays on Surge XT and its patches, which `bootstrap.py` installs; without Surge XT it plays its fallback preset on the built-in synthesizer, and the render's report says so. The render also writes the piece as a seamless loop (`loop.wav` and `loop.ogg`, with the loop points in them). Rendered again from scratch on the computer that made it, with the skill as published, every part not played by Surge XT came out identical, sample for sample, to the render the recording comes from. Surge XT starts its oscillators at random phases, so each time it synthesizes a part it plays a new take of the same sound; the render cache, not the renderer, keeps a take.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
