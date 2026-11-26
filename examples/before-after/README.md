# Before and after

What does the skill render again when one note changes, and does the shared reverb follow? This example answers with a fixed project, one revision of it and the `compare` command. It is also a fixed pair to test a change to the renderer against.

`porch_light.py` writes Porch Light, an original eight-bar miniature for flute, piano, bass and a light kit at 92 BPM in D major. Every part plays on the default MuseScore MS Basic bank, so the quick start's setup renders it in seconds. The revision raises the flute's held note in bar 5 from C♯5 to E5. The flute is the lead, so it sends to the plate reverb, and the note rings into bar 6.

## Run it

From the repository root, with the configuration written by `bootstrap.py`:

```
python examples/before-after/porch_light.py out/porch_light
python skills/music-production/scripts/studio.py revise out/porch_light/song.json --track flute --note flute_b005_n000 --pitch 76 --output out/porch_light/song_r2.json
python skills/music-production/scripts/studio.py render out/porch_light/song.json --config <folder>/local-config.json --output out/porch_light/before --cache out/porch_light/cache
python skills/music-production/scripts/studio.py render out/porch_light/song_r2.json --config <folder>/local-config.json --output out/porch_light/after --cache out/porch_light/cache
python skills/music-production/scripts/studio.py compare out/porch_light/before out/porch_light/after --clip out/porch_light/before_after.mp3 --config <folder>/local-config.json --differences out/porch_light/difference
```

The first command writes the same project as `porch_light.json` here. The second render synthesizes only the flute again; the other three parts come from the cache. Every render then mixes all four parts again through the buses, the reverbs and the master.

## What compare reports

On Windows with the pinned FluidSynth 2.6.3 and FFmpeg 9.0.2, positions in bar:beat:

| | Result |
|---|---|
| Project | the flute's note `flute_b005_n000` at 5:1, pitch 73 → 76 |
| Synthesized again | the flute; piano, bass and drums are reused |
| Stems | flute changed from 5:1 to 5:4.6, its overall level within a hundredth of a dB of before: a part's level is set from its loudness, which the new note can move. Piano, bass and drums identical. |
| Buses | lead changed from 5:1 to 5:4.65; the other three identical |
| Returns | plate changed from 5:1.05 to 6:1.85, almost a bar past the note; hall and room identical |
| Premix | changed from 5:1 to 5:4.95 |
| Master | 0.02 dB louder overall, because the master's gain follows the loudness target; besides that, changed from 5:1 to 6:1 |

In the premix and the master the plate's tail stops counting around 6:1. From there on the difference is more than 40 dB under the music around it, and `compare` does not count it. A file whose whole level moved is first matched in level by one gain, so a level change and a local change are reported apart.

A part's level is set from its loudness, so the new note can also move the whole flute a little (under 0.01 dB here, 0.03 dB with FluidSynth 2.6.1). On another system the same edit can move it more: one note once moved a piano 0.01 dB on Windows and 0.11 dB with Ubuntu's FluidSynth. Such a move reaches every mix the part plays in. `compare` keeps those passages too and marks them `follows_part_levels`, so the changes still start where the note changed.

On Linux and macOS the system FluidSynth and FFmpeg can make the levels differ slightly. The same files should change in the same places.

`before_after.mp3` holds 8 seconds of the master, old then new at the same loudness, from 1.5 seconds before the change. In `difference/` each changed file is written as after minus before, matched in level: the new note alone in the flute's stem, its new tail alone in the plate's return.

## Test a change to the renderer

Render `song.json` before your change and again with it, into two folders, and compare them. The files your change did not reach come out identical, sample for sample. The others show where the change starts and how loud it is next to the music. Compare renders made on one machine.

## Credits and licence

The composition is dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds come from MuseScore's MS Basic (MIT; see the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md)). The script and the project file are code, under the repository's MIT licence.
