# Contributing

Thanks for wanting to help. music-skill is maintained by one person and has a fairly fixed direction, so here is how help works best.

## Questions and ideas: Discussions

Questions about using or setting up the skill go to [Q&A](https://github.com/owoevan-dev/music-skill/discussions/categories/q-a), where an answer can be marked, and ideas to [Ideas](https://github.com/owoevan-dev/music-skill/discussions/categories/ideas). Music you made with the skill is welcome in [Show and tell](https://github.com/owoevan-dev/music-skill/discussions/categories/show-and-tell).

## Issues are welcome

- **A render that went wrong.** Paste the command, the error or the `report.json` checks, and say what you expected. Attach the project file if you can share it.
- **Music that sounds wrong.** Say where (bar numbers or seconds) and what you hear: a clash, a part too loud, a stiff phrase. Listening notes like these are the most useful feedback the project gets.
- **A sound bank you would like.** Link the publisher's page and its licence. Only banks with a clear licence that allows redistribution of music made with them can be added.

Write in any language you like.

## Pull requests

Small pull requests to the text are welcome, in stages, and so are new translations. For anything else bigger than a small fix to the text, and for every fix in the code, open an issue first, so that no time goes into something that cannot be taken. If you would rather not open a pull request, describe the fix in an issue or paste the patch there.

**Open for now:**

- The README and its translations. A new translation is a `README.<language>.md`: a two- or three-letter language, with a script and a region if it needs them, such as `README.pt-BR.md`, `README.es-419.md` or `README.zh-Hant-TW.md`. Add its link to the line of languages at the top of every README, as the others are linked.
- Corrections to `SKILL.md` below its frontmatter and to the guides in `references/`, other than the four named below, and style data in those guides, with its sources.

**A fix in the code**, however small, on Linux, macOS or anywhere: open an issue first, with the error and your patch if you have one. If it can be taken, you will be told which branch to open a pull request against: the one the next version is built on. It is read and merged there, then tested with every sound bank. If it holds it ships with that version, and the pull request says which version it was, or why it was held.

**Staying with the maintainer for now**, so a pull request here is closed with thanks and an issue is the better place:

- The sound: the synthesis and mixing code, the renderer, the banks and their recipes. A project has to go on rendering to the same audio.
- What installs, downloads or starts other programs, what removes files (`clean`), and what checks a bank before it is played.
- The tests and selfchecks.
- `SKILL.md`'s frontmatter, the data files in `references/`, and the setup, rights, bank-building and bank-preset guides (`setup.md`, `sources-and-rights.md`, `soundbank-building.md`, `soundbank-presets.md`).
- The CI, the plugin manifests, the licences, policies and changelog, images and examples.
- New files other than a translation, deletions and renames.

**How a pull request goes:**

- Keep it to one topic. Say what it changes, why, and how you checked it.
- `SKILL.md` and the guides are instructions an AI agent carries out on someone's computer, so they are read as carefully as code. Every new link, command and instruction needs a reason.
- A change that alters what an agent or a reader runs, downloads, reads or writes (a command, a link, a path, an instruction an agent follows) is merged into the branch the next version is built on, tried there, and ships with that version; you may be asked to point the pull request at that branch. Wording, spelling, and a translation that keeps every command and link of the original go straight to `main`.
- Give the source of every figure, rule or style fact, with its licence where it has one.
- The maintainer reads each pull request before its CI runs, so the checks may take a while to start.
- You are credited: as the author of a change merged into `main`, as a co-author of the release for a change that ships with the next version, and by name in the changelog. By opening a pull request or posting a patch you agree that it may be used under the project's MIT licence.

## What the project will not take

- An audio-generation model inside the skill. The notes are written, not generated.
- Sound banks under NC, ND or unclear licences, or samples taken from commercial libraries.
- Reference melodies, grooves or recordings copied from existing music.

## Paths under `research/`

Comments in the scripts and a few lines of the guides name files under `research/` (a design note, a measurement script, a trial). Those are the project's development records. They are kept outside this repository, so such a path names where a figure came from and is not a file here; what the skill relies on is stated where it is cited, and the checks that guard it are in `scripts/selfcheck.py`, which runs them, and `scripts/selfchecks/`, which holds them by area.

## Running the tests

```bash
python3 -m venv .venv && . .venv/bin/activate        # Windows: py -m venv .venv, then .venv\Scripts\activate
python -m pip install -r skills/music-production/requirements.txt
python -m pip install pyyaml pytest
python -m pytest -q tests
```

On your fork the same tests run from the Actions tab: enable workflows there once, then start `tests` on your branch. Without a renderer configuration the render checks are skipped. To include them, run the bootstrap from the README and set `MUSIC_SKILL_CONFIG` to the configuration file.
