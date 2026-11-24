# Commands in full

Read this for a command SKILL.md does not show, an option it leaves out, or what a command writes and keeps. `scripts/studio.py` is the entry point: resolve its absolute path from the skill's folder and do not assume the working directory. Every command also answers `--help` with an example.

Contents: [Every command](#every-command) · [What each is for](#what-each-is-for) · [Errors, new paths, long runs](#errors-new-paths-long-runs) · [A composition script that fails](#a-composition-script-that-fails) · [A second final render](#a-second-final-render) · [What a render writes](#what-a-render-writes) · [The cache](#the-cache) · [What compare reports](#what-compare-reports) · [Writing with the builder](#writing-with-the-builder) · [Choosing sounds](#choosing-sounds) · [Showing the piece: video and still](#showing-the-piece-video-and-still) · [clean](#clean)

## Every command

```text
python <skill>/scripts/studio.py doctor   --config <config.json>
python <skill>/scripts/studio.py start    <project> --title "<title>" --tempo 96 --section verse:8 --section chorus:8 --part "piano harmony vcsl 0:0" --part "lead melody iowa_winds 0:73" --config <config.json>   # compose.py and the song.json it writes; --part "<id> <role> <words that find its preset>", as instruments takes them; --meter 6/8
python <skill>/scripts/studio.py words    <project>   # the piece's twelve words, drawn once; --own "a, b, c" for the user's own, --none "<why>" for none
python <skill>/scripts/studio.py round    <project>/song.json --config <config.json> --output <project>/r1
python <skill>/scripts/studio.py round    <project>/song.json --config <config.json> --output <project>/r2 --previous <project>/r1 --clip <project>/r1_r2.mp3
python <skill>/scripts/studio.py render   <project>/song.json --config <config.json> --output <project>/final
python <skill>/scripts/studio.py clean    <project> --keep <project>/final --keep <project>/r2   # the final and the last round stay: lists what would go
python <skill>/scripts/studio.py clean    <project> --keep <project>/final --keep <project>/r2 --remove   # once that list is right
python <skill>/scripts/studio.py validate <project>/song.json
python <skill>/scripts/studio.py review   <project>/song.json --output <project>/review_a --config <config.json>
python <skill>/scripts/studio.py analyze  <project>/r2 --span chorus:17-24 --reference synthwave --output <project>/r2/synthwave.json
python <skill>/scripts/studio.py compare  <project>/r2 <project>/final --clip <project>/r2_final.mp3 --config <config.json>
python <skill>/scripts/studio.py profile  <project>/song.json --output <project>/profile_r2.json
python <skill>/scripts/studio.py sounds   --role pad --character warm,slow --seed <piece seed>   # one line a patch; --centroid 600-900 --attack 0.1-0.3: by measured range; --id <id>: one patch's controls; --json: every figure
python <skill>/scripts/studio.py instruments viola --config <config.json>   # a preset's bank and program, the keys its samples cover, its layers
python <skill>/scripts/studio.py audition <project>/song.json --track lead --sounds surge:smooth_lead,synth:supersaw_lead --bars 21-24 --output <project>/audition_lead --config <config.json>
python <skill>/scripts/studio.py revise   <project>/song.json --track piano --note piano_b004_n003 --pitch 74 --output <project>/song_r2.json
python <skill>/scripts/studio.py export-midi <project>/song.json --output <project>/song.mid
python <skill>/scripts/studio.py add-soundfont --config <config.json> --path <bank>.sf2 --name <name> --license "<its licence>" --source "<where from>" --version <v> --output <new config.json>
python <skill>/scripts/studio.py configure --fluidsynth <exe> --ffmpeg <exe> --soundfont <bank>.sf2 --output <new config.json>
python <skill>/scripts/studio.py still <project>/final --at 42 --output <project>/roll_42.png   # the piano roll at one moment (Pillow)
python <skill>/scripts/studio.py video <project>/final --output <project>/roll.webm --config <config.json>   # the roll scrolling under the master; --mp4 for H.264
python <skill>/scripts/studio.py inspect-midi <file>.mid   # a MIDI file's division, tracks, notes, and notes left open or closed twice
python <skill>/scripts/excerpt.py <project>/song.json --first-bar 17 --bars 8 --output <project>/passage.json
python <skill>/scripts/selfcheck.py --work <new empty folder> --config <config.json>
```

## What each is for

`round` is the way to revise: one call per round, with one report. It validates the project, reviews the score with the configuration (so notes far from their samples are found), renders a draft (the same audio as a full render; `mix.chain` is `"bus"` for a finished mix), analyzes it (`--reference` where a genre reference fits, `--span` for a passage) and compares it with the previous round, printing each step's summary.

The other commands do what a round does not: `validate` and `review` check a project before anything is rendered; `render` makes the full render to deliver (`--draft` for a draft outside a round); `analyze` measures a render again, against another reference or passage; `compare` takes any two renders or rounds, with `--clip` for the user and `--differences <new folder>` for the change alone; `clean` frees the disk at the end, listing first and removing only with `--remove`. `review`, `render`, `analyze`, `compare` and `audition` print a short summary that ends with the file and the keys holding the full figures; `round` prints its steps' summaries and ends with the next round's `--previous` (its figures are in the round's round.json), and `clean` prints what it would remove; `--json` prints the full JSON instead (for `round`, its round.json), and [outputs.md](outputs.md) lists the keys.

`audition` plays one part's passage on several sounds in turn, in the mix and at one loudness. A `soundfont:` alternative keeps the part's `mix.amp`: a guitar compared with a bank that is already an amplified sound is heard through the amp as well, so compare those with the amp off.

## Errors, new paths, long runs

Errors go to stderr as `ERROR: ...` with exit code 2. Outputs never overwrite: use a new folder for every round, render and review, and a new file for every revision and report. The one exception is your composition script, which writes `song.json` again each time it runs.

Installing banks and rendering can take several minutes, and the selfcheck with a configuration about half an hour ([setup.md](setup.md#check-the-setup)); run them with a long timeout or in the background. `--resume` takes up the same project in an existing render folder that stopped, with an error or killed: its record and its journal prove every file the render had written or begun, the half-written go, and a file it cannot prove stops it, named (killed in the instant between making a new file and noting it, a render leaves that one file unproven). Parts render in parallel, one per processor up to 8 (`--jobs` sets the most), as many at once as the free memory holds by each part's measured needs; the result is the same for any number. A part that would need more memory than the machine has (a built-in synth note held for minutes) is refused before rendering, with the reason.

## A composition script that fails

A run of `compose.py` that fails leaves the old `song.json`, and every command then reads that one. So run the next command only if the script succeeded, and do not let a pipe hide its exit status:

```text
python compose.py && python <skill>/scripts/studio.py round song.json ...           # Bash; set -o pipefail where the script's output is piped
python compose.py; if ($LASTEXITCODE -eq 0) { python <skill>/scripts/studio.py round song.json ... }     # PowerShell
```

Where `compose.py` beside a `song.json` was saved after it, `validate`, `review`, `round`, `render`, `audition`, `profile`, `revise` and `export-midi` end with a note saying so (on stdout after a summary, on stderr where stdout is JSON). It compares file times, so a script that was only touched raises it too, and it never runs the script.

## A second final render

A render never writes over a folder. For a new final after a change, render to a new one (`--output <project>/final_2`) and keep the earlier until the new one has passed and the user has heard it; then `clean` with `--keep` on the one you deliver. `--resume` is only for the same project in a render that stopped.

## What a render writes

A render writes `master.wav` (24-bit), `master.flac` (not in a draft), `preview.mp3`, `composition.mid` (performed), `score.mid` (notation timing), one MIDI per part in `midi/`, processed stems in `stems/` (each part before its bus and without the shared reverbs) and `report.json`. With `mix.chain` `"bus"`, `returns/` holds the buses that have parts and the reverb and delay returns in use, which add up to `premix.wav`, the mix before mastering. A project with `loop` also gets `loop.wav`, `loop.ogg` (where the FFmpeg has the libvorbis encoder) and `loop.json`: the loop with the tail folded back from its start, the loop points and a cue point per section written into the files. With `loop.layers`, every layer also comes as its own loop in `layers/`; a draft leaves out the Ogg copies and the layers, and the check that the MP3 decodes to the master's loudness.

Stems, returns and the premix are 32-bit float WAV, which Python's `wave` module refuses: a script of yours reads them with `samples, info = musiclib.audio.read_wav(path)` (the rate is `info['sample_rate']`).

## The cache

The raw synthesis cache is keyed by notes, performance, instrument, the clock (bars, meter, the tempo as played and `tail_seconds`) and dependency hashes, so a mix edit reuses every part and a one-note edit synthesizes one part again (another `clock.tail_seconds` synthesizes every part again). Each cache entry also keeps the part's processed stem, which the next render copies while nothing it depends on has changed (its mix but its sends and bus, the song's length, the part a duck follows), as a DAW plays a frozen track. Every render mixes all the parts again, so the shared reverbs, their tails and the master follow the change. Renders of one piece may run at once: a part holds its cache entry while it is made, and the other render waits for it.

## What compare reports

`compare` reports what changed between two renders: the project's edits, the parts synthesized again, and per stem, bus, return, premix and master whether it is identical, its overall level change (none where more of the file changed than one gain matches, as in a part rewritten) and the passages (bar:beat) where it differs. In a file that mixes parts, a passage that only follows a part's overall level change (a part's level is set from its loudness, so one new note moves it a little) is marked `follows_part_levels`. A part's own stem with no overall level (much of it rewritten) shows its untouched bars as changed as well, since its level moved with the rewrite: the part's `gain_db` in the two renders' `stem_receipts.json` gives the move ([outputs.md](outputs.md)). It does not judge the sound.

So "only the intended parts and bars changed" allows for two things that follow from an edit: an overall level move of the changed part (and of what mixes it), and a release or reverb ringing on past the edited bar.

## Writing with the builder

`studio.py start` writes `compose.py` with the sections and parts, each part's preset found in the configured banks as `instruments` finds it. `musiclib.builder` keeps its books: notes placed by bar and beat (from 1; a beat is a quarter note), each with a stable id and its performance entry, checked against its part's keys as it is written, and a save that validates. `song.harmony(bar, beat, symbol)` writes the chords once, where `review` reads the pitched parts' notes against them; `song.changes()` gives them back in order as `(bar, beat, symbol, beats)` and `song.chord_at(bar, beat)` the chord at a place, so that every part is written from the one list (the symbols alone are what `voice_lead` takes). The builder starts the project's `mix` as the bus chain with `rules` 2 at -14 LUFS; the project's other fields (`plan`, `style`, `association`, `decisions`, `loop`, a changed `mix`) are written into `song.project` before `song.save()`, and the builder's methods are described in the docstrings of `scripts/musiclib/builder.py`. A note's id comes from the part, bar, beat and pitch; `part.note(..., id=...)` keeps the id of a note you move.

A script of yours that reads a command's output (`score_review.json`, `analysis.json`, `report.json`, a round's record) takes the keys from [outputs.md](outputs.md), which gives each file's shape. A script that writes a song with the builder prints any name safely; one that does not calls `musiclib.files.escape_unprintable()` first, so that a character the console cannot encode (the `ø` of a chord quality on a Traditional Chinese Windows console) is printed as an escape.

## Choosing sounds

Synth parts default to Surge XT where it is installed: `engine: "surge"` with a patch chosen for the part's need from its catalog of 3,008 measured patches. `studio.py sounds` with the piece's `--seed` gives a shortlist spread over the range, of its own for each piece, and takes ranges of measured brightness and attack (`--centroid 600-900 --attack 0.1-0.3`) and `--character steady` for a patch whose brightness holds still: a sound is designed by choosing it, since a patch's own controls rarely reach a target ([sound-selection.md](sound-selection.md), [electronic-sounds.md](electronic-sounds.md)). Where Surge is missing, the part plays its patch's built-in fallback by itself. Write a built-in preset only for what no curated patch plays (the 808's glide, the 303's sweep, chip waves, noise transitions) or where a render must repeat exactly; with the full patch set installed, `review --config` names the catalog patches whose designers named them for those sounds, to hear against the built-in. `studio.py audition` plays one part's passage on several sounds in turn, in the mix and at one loudness, so the choice is made by ear on the music itself.

## Showing the piece: video and still

Where the user wants to show the piece: `studio.py video <final render> --output roll.webm --config <config>` makes the score a scrolling piano roll under the master (WebM, or `--mp4` for the widest playback; kept under 10 MB, the size GitHub takes, unless `--size-mb` says otherwise; where an encode comes out over, the command encodes again at a lower rate by itself), and `studio.py still` one frame of it. Both need Pillow 10.1 or newer (`python -m pip install pillow`; `doctor` says whether it is there); the roll shows the notes as played, coloured by what each part does, every part named in the legend (in a large ensemble, the names that do not fit are counted as "+N more"). The video takes minutes (two passes over every frame: on a desktop machine about as long as the piece plays) and prints only when it is done, so run it where a long command can finish, in the background if commands are timed.

## clean

`studio.py clean <project> --keep <final render> --keep <last round>` lists the piece's older renders, rounds, standalone `review` folders and audition caches and the cache entries those two do not use; check the list, then run it again with `--remove`. It removes only what the tools made for that piece, by the records they wrote, never follows a link, and leaves alone a folder a render, round or audition is still working in. Of the cache it takes only the piece's own, beside the kept render or round or inside one of the piece's folders that goes, and no entry a render that stays still plays (an entry never goes with the folder holding it); it stops, removing nothing, if a kept render's `stem_receipts.json` does not name every part. A review can be made again with one command, so it is not kept unless a note of yours is in its folder. A finished audition keeps its `audition.mp3` and `audition.json`; a `--clip` MP3 saved outside a round stays too. Past 20 entries the list says how many more; `--json` lists every one.
