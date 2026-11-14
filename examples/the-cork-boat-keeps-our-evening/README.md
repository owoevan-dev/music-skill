# The Cork Boat Keeps Our Evening

A slow ballad without a singer, in the manner of a film's ending theme: 64 bars in E-flat major at 74 BPM, the tune on the piano alone, then on a solo cello over strings, a guitar and a soft band, and the piano alone again at the end. Made by GPT-6 Astra (xhigh effort, in Codex) with a pre-release copy of this skill's version 0.7.0, in one take from the prompt below.

Listen: [The Cork Boat Keeps Our Evening](https://github.com/owoevan-dev/music-skill/releases/download/examples-5/the-cork-boat-keeps-our-evening.mp3) (3:33).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A slow ballad without a singer, in the manner of the ending theme of a Japanese film or anime, about three and a half minutes. A piano opens alone with the tune; strings and a soft band come in section by section; one instrument carries the line a singer would sing, in long phrases; the last chorus is the fullest, and the piano has the last word alone. Keep the pulse and the feel steady from the first bar to the last: few sections and long ones, no sudden stops, no short stabs, nothing that jumps.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked
the score with `review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody
edited the notes it wrote. One thing was changed after it finished: its two piano parts, which it had put on the Kawai grand, play the Steinway, as the skill's piano guide now asks of every piano part.

## From twelve words to a plan

Before deciding what the brief left open, the agent drew twelve words at random for the piece with `studio.py words`: *pyramid*, *birthday*, *cork*, *steamroller*, *blanket*, *minnow*, *sofa*, *clove*, *gecko*, *frizzy*, *cement*, *walrus*. It linked
the brief and all twelve into one whole, as the second step of [SKILL.md](../../skills/music-production/SKILL.md) asks, and wrote it into
the project:

> After a seaside birthday, a child with frizzy hair folds a blanket on a sofa beside a toy walrus and a gecko ornament; a pyramid of gifts still smells of clove cake. Outside, a parked steamroller stands on new cement while a cork boat drifts above a minnow. The boat travels away and returns below the lit window.

What the whole gave the music, in the agent's words (`association.gives` in `song.json`):

| | What | Where |
|---|---|---|
| Form | Departure, broad return, then the window alone; five long sections | entire piece |
| Melody | Rising third and a long stepwise return, like the drifting boat | piano opening and cello themes |
| Rhythm | Even rocking quarters without a tempo change | piano left hand throughout |
| Harmony | Common-tone inversions join the journey to the home tonic | two-bar harmonic spans |

Its plan (`plan` in `song.json`) says what identifies the piece and where its high point is, and `review` read the score against it:

> A rising third answered by stepwise retreat, long vocal-length phrases, and an unbroken rocking piano pulse.

The high point, in the section `last_chorus`: All eight parts, two-voice strings, higher sustained cello and long open guitar chords; no faster pulse.

## Files

- `compose.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts, and a line that set a temporary folder, which is left out; and its two piano parts, which it put on the Kawai grand (`vcsl_keys` 0:1), play the Steinway (`vcsl` 0:0), as the recording does.
- `song.json`: the project as it was rendered.
- `association.json`: the record of the twelve words, as `studio.py words` wrote it beside the project; the script reads the words from it.
- `review_decisions.json`: decisions the agent wrote after its first round, which the script adds to the project in its second revision (`--revision 2`).

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py --revision 2
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again, the same project, and beside it `song_r2.json` (the same once more) and `plan.json` (its title, clock, sections and plan, for reading). The render needs the sound banks `bass_darkblack`, `cello_bigcat`, `guitar_shiny`, `vcsl`, `vsco_strings`; `fetch_soundbanks.py --only examples` installs them with the other examples' banks. Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project files are code, under the repository's MIT licence.
