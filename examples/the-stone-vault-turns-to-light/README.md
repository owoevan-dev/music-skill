# The Stone Vault Turns to Light

A toccata for pipe organ in D minor: running figuration in the hands over a striding theme in the pedals, a quiet middle on the stopped flute, and a return to the full organ. Made by GPT-6 Astra (xhigh effort, in Codex) with this skill's version 0.6.0, in one take from the prompt below.

Listen: [The Stone Vault Turns to Light](https://github.com/owoevan-dev/music-skill/releases/download/examples-4/the-stone-vault-turns-to-light.mp3) (3:56).

## The prompt

The message began with [the opening every piece was given](../prompt.md) and ended with this brief:

> A toccata for pipe organ in a large church, about four minutes, in the grand manner of the romantic organ rather than a fugue: brilliant running figuration in the hands over a slow, striding theme in the pedals, a quieter middle section on the soft stop, and a return that builds to the full organ and a long last chord. Use the registrations the skill's organ bank has, and say in NOTES.md which you used where.

That was all the agent was given. It chose the title, the form, the instruments and the sounds, wrote every note in `compose.py`, checked the score with
`review`, rendered, measured, and revised its own work before delivering. Nobody replied to it while it worked, and nobody edited the result.

## Files

- `compose.py`: the agent's script; it writes every note. Edited for this repository only where it named folders of the machine it ran on: the lines that find the skill's scripts, and a line that set a temporary folder, which is left out.
- `song.json`: the project as it was rendered.

## Run it

In this folder, with the configuration `fetch_soundbanks.py` writes (`local-config.studio.json` in the repository's [install steps](../../README.md#install)):

```
python compose.py
python ../../skills/music-production/scripts/studio.py render song.json --config <folder>/local-config.studio.json --output render
```

The first command writes `song.json` again, the same project, and beside it `song_r4.json` (the same once more) and `form_r4.json` (a summary of the form). The render needs the sound bank `organ_vcsl`; `fetch_soundbanks.py --only examples` installs it with the other examples' banks. Rendered again from scratch on the computer that made it, with the skill as published, every part and the master came out identical, sample for sample, to the render the recording comes from.

## Credits and licence

The composition and its recording are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Its sounds and their licences are listed in the repository's [THIRD_PARTY.md](../../THIRD_PARTY.md). The script and the project file are code, under the repository's MIT licence.
