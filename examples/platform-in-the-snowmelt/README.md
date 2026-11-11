# Platform in the Snowmelt

A Japanese ballad like an anime ending theme, mostly piano and strings: it starts quietly, and the last chorus carries the most feeling. Made by Claude (Opus 5.5, xhigh effort) with this skill's version 0.3.0, in one run from the prompt below.

Listen: [Platform in the Snowmelt](https://github.com/owoevan-dev/music-skill/releases/download/examples-3/platform-in-the-snowmelt.mp3) (4:37).

## The prompt

> 題材：像動畫片尾曲的日系抒情曲，鋼琴和弦樂為主，安靜開始，最後一次副歌情緒最滿。長度與細節自由發揮。

"Subject: A Japanese ballad like an anime ending theme, mostly piano and strings: it starts quietly, and the last chorus carries the most feeling. Length and details are up to you." The prompt also told the agent to read [the rules every agent
followed](../agent-rules.md) first. That was all it was given: it chose the title, the form, the instruments and the
sounds, wrote every note in `compose.py`, checked the score with `review`, rendered, measured, and revised its own work
before delivering. Nobody edited the result, and nobody listened until it was finished.

## Files

- `compose.py`: the agent's script; it writes every note. One edit for this repository: the line that finds the skill's scripts.
- `song.json`: the project as it was rendered.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py new.json r6
python ../../skills/music-production/scripts/studio.py render new.json --config <folder>/local-config.studio.json --output render
```

The first command writes the same project as `song.json`. The render needs the sound banks `bass_darkblack`, `cello_bigcat`, `iowa_brass`, `iowa_strings`, `piano_osiris`, `rusty`, `vcsl` and `vsco_strings`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. Its synth parts play on Surge XT and its patches, which `bootstrap.py` installs; without Surge XT they play their fallback presets on the built-in synthesizer, and the render's report says so. Rendered again from scratch on the computer that made it, with the skill as published, every part not played by Surge XT came out identical, sample for sample, to the render the recording comes from. Surge XT starts its oscillators at random phases, so each time it synthesizes a part it plays a new take of the same sound; the render cache, not the renderer, keeps a take.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
