# Fughetta of the Paper Paddock

A baroque-style fughetta for harpsichord, violin, viola and cello: 53 bars in D minor at 90 BPM, the subject taken up by each voice in turn, three episodes, and a stretto over a dominant pedal. Made by Claude Sonnet 5.5 (xhigh effort, in Claude Code) with a pre-release copy of this skill's version 0.7.0, in one take from the prompt below.

Listen: [Fughetta of the Paper Paddock](https://github.com/owoevan-dev/music-skill/releases/download/examples-5/fughetta-of-the-paper-paddock.mp3) (2:28).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A baroque-style fughetta for harpsichord and strings, about two and a half minutes: a subject with a clear head and tail, answered in turn by each voice, a countersubject that keeps its shape, episodes in sequence that travel to related keys, a stretto or a pedal point near the end, and a firm cadence to close. The voices stay independent, each one singable on its own.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked
the score with `review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody
edited the notes it wrote.

## From twelve words to a plan

Before deciding what the brief left open, the agent drew twelve words at random for the piece with `studio.py words`: *savanna*, *origami*, *rice*, *heel*, *paddock*, *huddle*, *spider*, *lattice*, *shutter*, *magpie*, *rowboat*, *fry*. It linked
the brief and all twelve into one whole, as the second step of [SKILL.md](../../skills/music-production/SKILL.md) asks, and wrote it into
the project:

> On a wet afternoon someone folds a savanna out of rice paper on a table by a window with a wooden lattice and a shutter: a paddock of paper animals, a paper rowboat on a bowl of water with a shoal of paper fry under it. A spider lets one thread down across the lattice, then a second and a third along the same path, and a fourth, so that four threads hang there answering one another. A magpie hops along the sill, takes a bright scrap of the web at a time and carries it from pane to pane, from room to room of the paddock. Grains of rice scatter and settle. At the end every animal huddles into one corner of the paddock, the heel of a foot is planted on one note, the shutter is pulled to, and the last light through the lattice goes out in one firm chord.

What the whole gave the music, in the agent's words (`association.gives` in `song.json`):

| | What | Where |
|---|---|---|
| Form | the fugue follows the scene: the exposition lays the four threads one by one; three episodes are the magpie carrying scraps; the stretto is the huddle; the cadence is the shutter | all sections |
| Melody | subject = the thread: a head that leaps D-A-D across the lattice and a tail that folds the paper back (a falling scale, then the neighbour-note cell 3-2-1-2 twice, a step lower each time); countersubject = the rice: even eighth notes in thirds and sixths that keep their shape | bars 1-44 |
| Harmony | the paddock is a fence of related keys: F major (the relative) and G minor (the subdominant) as its two rooms; the huddle is a dominant pedal the voices crowd over; the last chord lets the light in with a raised third | bars 14-19, 24-29, 36-43, 52-53 |
| Rhythm | the rowboat is the cello's paired oar strokes (root-third-root, then A low-high-low-high) under the episodes and the pedal; the fry are the sixteenth-note flicks in the tail | bars 11-13, 30-33, 36-43 |
| Sounds | rice paper and plucked wire: the harpsichord on its single Flemish 8-foot stop, with a solo violin, viola and cello, each a single player, as in a room for four | whole piece |
| Mix | the shutter: the room is a near one (clarity C80 +8 dB), the lines easy to follow, little hall around them | whole piece |

Its plan (`plan` in `song.json`) says what identifies the piece and where its high point is, and `review` read the score against it:

> A fughetta in D minor made from two bars of subject (a rising D-A-D head folded back by a neighbour-note tail) and two bars of countersubject (rice-grain eighths), passed between harpsichord, violin, viola and cello, sequenced in the episodes and crowded together in a stretto over a dominant pedal.

The high point, in the section `stretto`: entries one bar and a half apart over a held dominant, the violin's subject an octave higher (D5-D6) in bar 40, the cello's pedal in octave strokes, ending in the dominant that the return resolves.

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

The first command writes `song.json` again, the same project. The render needs the sound banks `cello_bigcat`, `iowa_strings`, `vcsl_keys`, `vsco`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project files are code, under the repository's MIT licence.
