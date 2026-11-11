# Fughetta on a Lantern Theme

A baroque-style miniature for harpsichord and strings, with imitative counterpoint between the voices. Made by Claude (Opus 5.5, xhigh effort) with this skill's version 0.3.0, in one run from the prompt below.

Listen: [Fughetta on a Lantern Theme](https://github.com/owoevan-dev/music-skill/releases/download/examples-3/fughetta-on-a-lantern-theme.mp3) (1:55).

## The prompt

> 題材：巴洛克風格的大鍵琴與弦樂小品，聲部之間要有模仿對位。長度與細節自由發揮。

"Subject: A baroque-style miniature for harpsichord and strings, with imitative counterpoint between the voices. Length and details are up to you." The prompt also told the agent to read [the rules every agent
followed](../agent-rules.md) first. That was all it was given: it chose the title, the form, the instruments and the
sounds, wrote every note in `compose_baroque.py`, checked the score with `review`, rendered, measured, and revised its own work
before delivering. Nobody edited the result, and nobody listened until it was finished.

## Files

- `compose_baroque.py`: the agent's script; it writes every note. One edit for this repository: the line that finds the skill's scripts.
- `song.json`: the project as it was rendered.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose_baroque.py new.json
python ../../skills/music-production/scripts/studio.py render new.json --config <folder>/local-config.studio.json --output render
```

The first command writes the same project as `song.json`. The render needs the sound banks `cello_bigcat`, `iowa_strings`, `vcsl_keys`, `vsco` and `vsco_extra`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
