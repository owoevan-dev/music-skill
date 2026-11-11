# Fughetta in D minor

A baroque-style fughetta for harpsichord and strings: 36 bars in D minor, the subject taken up by each voice in turn. Made by Claude Opus 5.5 (medium effort, in Claude Code) with this skill's version 0.6.0, in one take from the prompt below.

Listen: [Fughetta in D minor](https://github.com/owoevan-dev/music-skill/releases/download/examples-4/fughetta-in-d-minor.mp3) (2:00).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A baroque-style miniature for harpsichord and strings, about two minutes, with imitative counterpoint between the voices: a subject that each voice takes up in turn, an episode that travels to another key, and a firm cadence to close.

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

The first command writes `song.json` again, the same project. The render needs the sound banks `cello_bigcat`, `iowa_strings`, `vcsl_keys`, `vsco`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
