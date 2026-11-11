# Glass Towers, Low Gear

A city pop instrumental at 110 BPM: a night drive through a lit city. Made by Claude Opus 5.5 (xhigh effort, in Claude Code) with this skill's version 0.6.0, in one take from the prompt below.

Listen: [Glass Towers, Low Gear](https://github.com/owoevan-dev/music-skill/releases/download/examples-4/glass-towers-low-gear.mp3) (3:03).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A city pop instrumental, about three minutes: a night drive through a lit city. A groove that sits back, an electric bass that moves, electric piano chords rich in sevenths and ninths, bright synth brass stabs, and a tune one remembers after one hearing. The lead is a synthesizer or an electric piano, not a sampled saxophone or guitar. Give it a verse, a chorus and a short solo.

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

The first command writes `song.json` again, the same project. The render needs the sound banks `bass_darkblack`, `fsbs_clean`, `rusty`, `vcsl_world`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. 7 of its parts play on Surge XT and its patches, which `bootstrap.py` installs; without Surge XT they play their fallback presets on the built-in synthesizer, and the render's report says so. Rendered again from scratch on the computer that made it, with the skill as published, every part not played by Surge XT came out identical, sample for sample, to the render the recording comes from. Surge XT starts its oscillators at random phases, so each time it synthesizes a part it plays a new take of the same sound; the render cache, not the renderer, keeps a take.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
