# Setup and reproduction

The renderer needs Python 3.10 or newer with NumPy, FluidSynth 2.x, FFmpeg 6.0 or newer with the MP3 encoder (libmp3lame), and at least one SoundFont. `scripts/bootstrap.py` sets these up in a folder you choose and writes the configuration file every render takes. Keep that folder, the sound banks and your projects outside the skill folder.

Use a virtual environment for NumPy:

```text
python -m venv <work>/.venv
<work>/.venv/Scripts/python -m pip install -r <skill>/requirements.txt      # Windows
<work>/.venv/bin/python -m pip install -r <skill>/requirements.txt          # Linux, macOS
```

requirements.txt names every file PyPI publishes for the NumPy it pins, by SHA-256, so pip installs NumPy only as published (pip's hash-checking mode); install any other package with a pip command of its own. On a platform with no NumPy wheel, install NumPy as your platform provides it. The bootstrap itself needs only the standard library.

## Windows x64

```text
python <skill>/scripts/bootstrap.py --runtime <work>/.runtime --config <work>/local-config.json
```

This downloads the pinned FluidSynth 2.6.1 (2.7 MB) and FFmpeg 9.0.2 essentials (115 MB) builds from their official GitHub releases and the MuseScore MS Basic SF3 (51 MB) from a pinned MuseScore commit. Every size and SHA-256 must match `runtime-lock.json`, or installation stops. Nothing runs an installer or changes the registry or PATH. With the archives already downloaded, add `--archive-cache <folder> --offline`.

Folder names may hold any characters and spaces: the setup, a render with Surge XT parts and the selfcheck were run in folders whose names held Chinese characters, spaces and 喆, which code page 950 lacks (Python on Traditional Chinese Windows writes piped output in that page), and the scripts print a character their output cannot hold as an escape (`喆`). Keep the runtime folder's path, and each piece's, under 120 characters: Windows limits a path to 260 characters unless long paths are turned on and the program opts in (Microsoft, [Maximum Path Length Limitation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)), FluidSynth 2.6.1 does not opt in, and the setup writes files up to 133 characters below the runtime folder (our measurement).

## Linux and macOS

Install the tools from your package manager, then bootstrap with `--system`:

```text
sudo apt install fluidsynth ffmpeg libarchive-tools        # Debian 13, Ubuntu 24.04 or newer
brew install fluid-synth ffmpeg                             # macOS
python3 <skill>/scripts/bootstrap.py --system --runtime <work>/.runtime --config <work>/local-config.json
```

`--system` records the `fluidsynth` and `ffmpeg` found on PATH (or given with `--fluidsynth` and `--ffmpeg`) with their hash and version, and downloads only MS Basic and its licence notice, checked against the lock. It refuses FFmpeg older than 6.0. `libarchive-tools` provides `bsdtar` for the optional .7z banks. The repository's CI renders with FluidSynth 2.3.4 and FFmpeg 6.1 on Ubuntu 24.04 and with FluidSynth 2.6.1 and Homebrew's FFmpeg 9.0 on macOS; other binary versions may produce slightly different samples.

Homebrew's `ffmpeg` is built without `libvorbis`, the Vorbis encoder the skill uses, so a game loop rendered with it gets `loop.wav` but no `loop.ogg`, and the render notes the Ogg copy as skipped. For the Ogg copy, install `ffmpeg-full`, which Homebrew keeps off PATH, and give it to the bootstrap: `brew install ffmpeg-full`, then `--ffmpeg "$(brew --prefix ffmpeg-full)/bin/ffmpeg"`. The bootstrap says when an FFmpeg cannot write Ogg, and so does `studio.py doctor`.

## Surge XT

Unless you pass `--no-surge`, the bootstrap also sets up Surge XT for `surge` parts (its 3,008 patches, fifty of them curated: [sound-selection.md](sound-selection.md), [electronic-sounds.md](electronic-sounds.md)):

- Windows and Linux on x86-64, and macOS: the pinned plugin-only Surge XT 1.3.4 release for that system (Windows 49 MB, Linux 97 MB, macOS 187 MB and universal for Intel and Apple silicon; the archive and the plugin's binary checked by hash; only its VST3 is kept), the pinned pedalboard 0.9.26 wheel for your Python (about 4 MB, fetched from its locked address no larger than its locked size and checked against the hash PyPI publishes as it arrives, installed into the runtime folder only, never into your Python), the fifty curated patches (1.8 MB) from Surge's pinned repository commit, each checked by hash, and every patch of the catalog (3,008, about 217 MB, eight downloads at a time) from the same commit, each checked by size and hash. `--no-surge-catalog` leaves the full set out: parts that name a catalog patch then play their fallback presets.
- A Surge XT you installed yourself: pass `--surge-vst3 <bundle>`. On Linux on ARM, where no build is pinned, install Surge XT 1.3.4 from https://surge-synthesizer.github.io/ first, and the bootstrap finds `Surge XT.vst3` in the usual VST3 folders. Either way it records the plugin's hash, then installs pedalboard and the patches as above.

Without Surge XT the bootstrap says so and carries on, and Surge parts play their fallback presets on the built-in synth. Surge XT and pedalboard are GPL-3.0 programs; they run only inside `scripts/surge_host.py`, a GPL-3.0-or-later program the renderer starts as its own process and exchanges files with, so the rest of the skill stays MIT, and what you render with them is yours. An optional piece that fails to install (no wheel for this Python, a changed file) is skipped with its reason and the configuration is still written. Loading the plugin and a patch takes under a second per part; afterwards the render cache keeps the part's take.

## Check the setup

```text
python <skill>/scripts/studio.py doctor --config <work>/local-config.json
python <skill>/scripts/selfcheck.py --work <new empty folder> --config <work>/local-config.json
```

`doctor` re-hashes every configured file. The selfcheck runs 73 checks on its own and 91 with a configuration (`--config`), real renders included, in a few minutes.

## Optional sound banks

```text
python <skill>/scripts/fetch_soundbanks.py --config <work>/local-config.json --runtime <work>/.runtime --output <work>/local-config.studio.json
```

This adds the banks in [soundbanks.md](soundbanks.md) to a new configuration: three FSBS electric guitars (352, 131 and 149 MB to download), two basses (2–3 MB each), all five repacked unchanged from FreePats, and twenty-five banks built here from the samples of pinned commits or of the University of Iowa site:
- the orchestra: VSCO 2 CE strings, brass, woodwinds and colours, the section strings, trombone, tuba, double bass and piccolo; the Iowa horn, bass trombone, clarinets, flutes, solo strings and orchestral percussion; the VCSL harp, mallets, bells, timpani and orchestra kit;
- keyboards: a Steinway grand (VCSL), a pedalled grand (Osiris), a Kawai grand, upright pianos, harpsichords and FM keys (VCSL), a pipe organ (VCSL);
- band and solo: a rock kit (Big Rusty Drums), a five-string bass, a pizzicato double bass, an archtop guitar, a solo cello, a tuba, a baritone and a tenor saxophone, recorders and harmonicas;
- world: an erhu, a steel pan, a folk harp, a dan tranh, kalimbas, a balafon and world percussion; and a sung "ah".

The twenty-five come as this project built them: one xz-compressed SF2 each from the repository's release `soundbanks-1`, 2.9 GB in all, checked by size and SHA-256, then unpacked and checked against the build's locked hash, so each is byte for byte what a build from the sources gives. Where the release cannot be reached or a file does not match, that bank is built from its sources instead; `--from-source` builds them all that way (larger downloads, and the builds take a while), and `--prebuilt-from <folder>` takes the assets from a local copy. The five FreePats banks come from the same release, their files repacked unchanged as tar.xz (0.6 GB) and checked against the hashes of FreePats' own files; only where the release cannot be reached do they come from FreePats as .7z archives, which need a tar with LZMA or 7-Zip (Windows 10's own tar cannot read them). All thirty are about 3.5 GB to download and 8.2 GB installed; each bank's sizes are in [soundbanks.md](soundbanks.md). `--only` takes bank names (`--only vcsl,rusty`) and groups: `orchestra` (1.5 GB to download), `band` (1.3 GB), `world` (0.5 GB) and `examples`, the banks the published examples use (2.5 GB). `--delete-sources` deletes the downloads once every requested bank is verified (the banks stay; installing one again downloads it again). Every archive, asset and sample is checked against `soundbank-lock.json`, a dropped download is tried again, and each build must reproduce its locked hash. Large banks are loaded only by the tracks that select them. A project that names a bank not yet configured stops with the command that installs it.

The downloads stay in the runtime folder unless you add `--delete-sources`, which deletes a download or a sample only while it is still the installer's own (its locked size and hash) and names anything else it finds there: all thirty take about 3.5 GB to download and 8.2 GB installed, so keep about 12 GB free. An install replaces only what an earlier install put there; a file of yours at the same place is renamed aside (`<name>.replaced-<time>`), never deleted. A bank that fails (a lost connection after its retries, a missing tool) is listed at the end; the others are still configured. A build from the sources (`--from-source`, or where the release cannot be reached) fetches only the samples the lock pins for it, each path with its git blob hash and size (a source listing that names others is refused before anything is fetched), and reproduces the locked hashes with NumPy 2.1.2, the version `requirements.txt` pins for Python 3.10–3.13; with another NumPy a few samples can round differently and the build stops with that reason. The prebuilt banks do not depend on it.

## Your own tools or banks

```text
python <skill>/scripts/studio.py configure --fluidsynth <path> --ffmpeg <path> --soundfont <bank.sf2> --output <work>/local-config.json
python <skill>/scripts/studio.py add-soundfont --config <work>/local-config.json --name piano --path <bank.sf2> --license "<licence and credit>" --source <official url> --version "<version and hash>" --output <work>/local-config.studio.json
```

A configuration records paths (absolute, or relative to the configuration file) and SHA-256 hashes. A hash proves the file is unchanged, not who published it or that it is safe: read the source and licence yourself. A bank whose preset and instrument tables do not hold together is refused, as FluidSynth refuses it. Both commands write a new file, with every path made absolute, and never overwrite one. After a system package update replaces FluidSynth or FFmpeg, the hash no longer matches: run the bootstrap again for a new configuration.

## Small functional example

```text
python <skill>/scripts/make_example.py --output <work>/example.json
python <skill>/scripts/studio.py render <work>/example.json --config <work>/local-config.json --output <work>/example_render
```

A four-bar fixture that checks the setup, not a musical demonstration. To revise a passage on its own, `excerpt.py` cuts bars into a new project that plays the passage as the piece does: the notes still sounding at its start, as written and as played, are re-attacked (a note that only its gate or timing carries past the cut is not, as that would add an attack the piece does not have); dynamics, bends, filter sweeps, CC and automation are cut at the values they have there, linear CC ramps included; and the piece's ritardandi that reach into the passage are kept (`clock.rubato.spans`). A loop is left out. For an exact audio excerpt cut the finished WAV instead.

## Installing the skill

Copy the whole `music-production` folder into your agent's skills folder (for Codex, `~/.codex/skills/music-production`), or install the music-skill plugin as its README describes. A newly added skill may need a new session to be discovered. Versions are pinned for reproducibility, not certified secure forever: an update needs new provenance and regression checks.
