# Fjord Stopwatch

A lo-fi hip-hop beat for reading late at night that loops without a seam: 48 bars in F major at 78 BPM, on a worn upright piano, a double bass, a flute and a side-stick kit, with vinyl hiss under it. Made by Claude Haiku 5.5 (xhigh effort, in Claude Code) with a pre-release copy of this skill's version 0.7.0, in one take from the prompt below.

Listen: [Fjord Stopwatch](https://github.com/owoevan-dev/music-skill/releases/download/examples-5/fjord-stopwatch.mp3) (2:32).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A lo-fi hip-hop beat for reading late at night, about two and a half minutes, looping without a seam (deliver the loop as well as the preview): a warm, slightly worn piano or electric piano over jazzy seventh chords, a round bass, a laid-back swung drum pattern and a little tape or vinyl character. Keep it small, four or five parts, with one simple melodic idea that keeps coming back and small changes that keep it alive.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked
the score with `review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody
edited the notes it wrote.

## From twelve words to a plan

Before deciding what the brief left open, the agent drew twelve words at random for the piece with `studio.py words`: *fjord*, *pulley*, *stopwatch*, *plywood*, *balloon*, *simmer*, *wagon*, *cheek*, *canvas*, *ooze*, *nettle*, *patio*. It linked
the brief and all twelve into one whole, as the second step of [SKILL.md](../../skills/music-production/SKILL.md) asks, and wrote it into
the project:

> A late reader on a plywood floor over a fjord-side harbour. A pulley outside lifts a wagon of nets; the stopwatch on the sill times a kettle that simmers. A red balloon, lost from the harbour fair, drifts past the patio door and its string brushes the canvas awning; nettles grow through the paving and ooze from an old paint tin in the gutter. The reader rests a cheek on one hand while the balloon rises and comes down again and the night goes on.

What the whole gave the music, in the agent's words (`association.gives` in `song.json`):

| | What | Where |
|---|---|---|
| Form | six scenes of eight bars in the order of the night: kettle, pulley, stopwatch, wagon, balloon, patio | all sections |
| Rhythm | the pulley creaks in 3+3+2 eighths (kick on steps 0, 6, 12) in the pulley and wagon scenes; the stopwatch ticks evenly on the hats | bars 8-15, 24-31; bars 16-23 and 40-43 |
| Melody | the balloon: a fourth up from C5 to F5, then down by step to A4, the hook; the wagon plays the same shape over the cold chords | bars 16-19, 24-29, 32-43, 47 |
| Harmony | the cold fjord turn: D-flat major seventh and the B-flat minor and E-flat seventh colour in the pulley and wagon scenes; the balloon climbs down a circle of fifths | bars 8-15, 24-31, 32-39 |
| Sounds | wood and canvas: a side stick, a worn upright piano, an upright bass and a flute for the balloon | all sections |
| Mix | the canvas muffles the top: piano low-passed at 5.2 kHz, tape wobble on the piano and flute, vinyl hiss under the whole piece | all sections |

Its plan (`plan` in `song.json`) says what identifies the piece and where its high point is, and `review` read the score against it:

> a two-bar hook for the flute that floats up a fourth and falls back by step, over a piano that answers with rootless sevenths; the B scenes turn cold by a half step.

The high point, in the section `balloon`: the hook an octave up on the flute, after two bars with the drums out.

## Files

- `compose.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts.
- `song.json`: the project as it was rendered.
- `association.json`: the record of the twelve words, as `studio.py words` wrote it beside the project; the script carries the same twelve words in its own text.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again, the same project. The render needs the sound banks `bass_sneaky`, `rusty`, `vcsl_keys`, `vsco`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. The render also writes the piece as a seamless loop (`loop.wav` and `loop.ogg`, with the loop points in them). Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project files are code, under the repository's MIT licence.
