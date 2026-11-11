# Cairnfire

A concert overture for full orchestra in E minor: 133 bars in 36 parts, with a singing theme in the middle and a fugato in the development. Made by Claude Fable 5.2 (xhigh effort, in Claude Code) with this skill's version 0.6.0, in one take from the prompt below.

Listen: [Cairnfire](https://github.com/owoevan-dev/music-skill/releases/download/examples-4/cairnfire.mp3) (4:29).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A dramatic concert overture for full orchestra, four to five minutes. It must seize the listener within the first ten seconds: a stark opening gesture, then a driving figure in the low strings with timpani and brass over it. In the middle comes a broad, singing theme that should sound as it does from a good seat in the hall; the development has a fugato; and at the end the opening returns at full force and lands. Write for the sections rather than for soloists: no long exposed line for a solo string instrument.

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

The first command writes `song.json` again, the same project. The render needs the sound banks `iowa_brass`, `vcsl`, `vsco`, `vsco_extra`, `vsco_strings`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
