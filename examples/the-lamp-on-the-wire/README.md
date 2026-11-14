# The Lamp on the Wire

Music for the climax of an animated film, for full orchestra with harp, piano, timpani and a large percussion section: 91 bars in 57 parts, from the theme alone on the piano through a chase and a still scene to the whole orchestra, and back to the piano. Made by Claude Fable 5.2 (xhigh effort, in Claude Code) with a pre-release copy of this skill's version 0.7.0, in one take from the prompt below.

Listen: [The Lamp on the Wire](https://github.com/owoevan-dev/music-skill/releases/download/examples-5/the-lamp-on-the-wire.mp3) (4:43).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> Music for the climax of an animated feature film, for the largest orchestra the banks give: strings, woodwinds, brass, harp, piano, timpani and a large percussion section. Four to five minutes. It opens small, the film's main theme on one instrument, and builds through two or three turns of the story (a chase or a struggle, a moment where everything stops, a return) to the largest statement of the theme by the whole orchestra, and then lets it go quietly. The theme must be one a listener sings on the way out. Write for the sections as well as for soloists, and let every section of the orchestra carry the theme at some point.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked
the score with `review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody
edited the notes it wrote.

## From twelve words to a plan

Before deciding what the brief left open, the agent drew twelve words at random for the piece with `studio.py words`: *wire*, *ladle*, *stroll*, *grip*, *reef*, *sorbet*, *hedge*, *lamp*, *chin*, *typewriter*, *decal*, *burlap*. It linked
the brief and all twelve into one whole, as the second step of [SKILL.md](../../skills/music-production/SKILL.md) asks, and wrote it into
the project:

> At dusk a girl takes a stroll along the top of the harbour hedge with a paper lamp that wears a star decal, humming the tune her grandmother used to tap out on a typewriter. A gust tears the lamp away and she rides after it down the telegraph wire in a burlap sack, keeping her grip while the line clatters like keys, bell and carriage return, until the wire snaps over the reef. Everything stops: under the water the lamp sinks in light the colour of sorbet. She lifts her chin, the town's lamps answer one by one, and the lamp is ladled up into the sky, the seventh star of the Dipper, the ladle that points at the pole star.

What the whole gave the music, in the agent's words (`association.gives` in `song.json`):

| | What | Where |
|---|---|---|
| Form | the eight scenes in the order of the story: stroll, hedge, gust, wire, reef, chin, ladle, star | the eight sections |
| Melody | the theme's head is a ladle of seven notes: a handle of three (two alike and a step up), a bowl that dips, and a leap of a sixth that points up, as the Dipper points at the pole star; the note it points at, the high D, is reached only in the last phrase of the tutti | bars 1-2 and every statement; the high D in bars 81-85 |
| Rhythm | the typewriter: sixteenth-note clatter in 3+3+2, a triangle bell at the end of every fourth bar and a ratchet and falling run for the carriage return; the theme sails over it in doubled note values, at the speed of the stroll | wire, bars 27-50 |
| Harmony | the reef and the sorbet are one chord in two lights, a major seventh with a Lydian fourth: struck hard on F (bar 51), floating on A-flat under the bells (bar 54); the return climbs by whole tones, A-flat, B-flat, C, to D | reef bars 51-56, chin bars 57-66, the peak bars 81-83 |
| Sounds | the wire is one held high note on a solo violin, always the fifth of the key; the lamp is a glockenspiel; the keys are claves and a slit drum; the grip is the brass hammering the handle; the first and last voice is the piano, the instrument with keys | bars 9-12, 52-56, 89-91 (wire); 53-56, 90-91 (lamp); 27-50 (keys) |

Its plan (`plan` in `song.json`) says what identifies the piece and where its high point is, and `review` read the score against it:

> One theme whose head is seven notes, a handle, a bowl and a leap that points up; the piece is the story of that leap: bent down by the gust, set in minor on the wire, hung in bells, raised three times by a whole tone, and answered at last by the high D it pointed at.

The high point, in the section `ladle`: the melody's highest held notes (D6, E6, D6) kept for bars 81-85, over B-flat and C major chords the piece has not used at that level (flat VI, flat VII, I), the bass at its lowest, the whole brass and timpani giving the head under the held notes, clash cymbals and bells; a bar of thinner woodwind writing and one beat of air before it.

## Files

- `compose.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts.
- `song.json`: the project as it was rendered.
- `association.json`: the record of the twelve words, as `studio.py words` wrote it beside the project; the script reads the words from it.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again, the same project. The render needs the sound banks `iowa_brass`, `iowa_perc`, `iowa_winds`, `vcsl`, `vcsl_world`, `vsco`, `vsco_colors`, `vsco_extra`, `vsco_strings`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project files are code, under the repository's MIT licence.
