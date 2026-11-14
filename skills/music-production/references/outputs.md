# What the commands write

Read this when a command's summary points to a figure you need in full. Every command prints a short summary that
ends with the file and the keys below; `--json` prints the whole file instead (`round` prints its round.json, `clean`
its report). Levels are dB, loudness LUFS (ITU-R BS.1770), true peak dBTP, positions bar:beat counted from 1 unless a
key says seconds or samples.

Contents: [round.json](#roundjson) · [report.json](#reportjson-render) · [stem_receipts.json](#stem_receiptsjson-render) ·
[score_review.json](#score_reviewjson-review) · [analysis.json](#analysisjson-analyze) · [compare](#compare_namejson-compare) ·
[audition.json](#auditionjson-audition) · [clean](#clean-its-report) · [files.json](#filesjson-every-folder) ·
[what stays local](#what-stays-local)

## round.json

`studio.py round` writes `review/` and `render/` (a draft, with `analysis.json` and `compare_<previous>.json`) and
`round.json`, from the moment the round's folder is made: `kind` and `title` (what made the folder and of which piece),
`status` (the render's; `FAIL` if it did not finish), `failed` (null, or the `step` that stopped the round and its
`error`), `questions` (how many review questions), `new_questions` and `gone_questions` (with `--previous` a round
made by this version: the identifiers of the questions this round asks that the round before did not, and of those
it asked that are gone; a fix that raises another question shows in the first), `project` and `previous` (relative
to the round's folder), the
relative paths `review`, `render`, `analysis`, `compare`, `seconds` per step and `runtime_seconds`. With `--clip`, the comparison's `clip` names the old-then-new MP3
(or why it was not made). A round's folder can stand for its render wherever a command takes a render folder;
`compare` of two rounds names its report after the first, and `analyze` of a round needs `--output` (the round wrote
its `analysis.json`).
With a `plan` in the project, the round also records `plan` (the plan as it stands in this round), `plan_first` (the
plan as first written, carried from round to round so that it outlives the earlier rounds' folders) and, where the
two differ, `plan_changed` (`identity`, `high_point`, `section <id>`). A round whose project has no plan any more
still carries `plan_first` on, and its `plan_changed` says the whole plan is gone.

## report.json (render)

| Key | What it holds |
|---|---|
| `status` | `TECHNICAL_PASS_AUDITION_PENDING` (a full render), `DRAFT_PASS` (a draft: deliver a full render), `FAIL` |
| `failed` | only in a render that stopped before its report: `after_stage` (the last stage it finished, as in `stage_seconds`), `part` (the first part that stopped, or null) and `error`; such a report holds `status`, `title`, `draft`, `stage_seconds` and `runtime_seconds` besides. `--previous`, `compare` and `analyze --reference` refuse it |
| `draft`, `left_out` | whether it is a draft, and what a draft leaves out (master.flac, the MP3 check, a loop's Ogg copies and layers) |
| `checks` | every delivery check, true or false: finite audio, no clipping, the true-peak ceiling, the exact length, 48 kHz 24-bit stereo, a quiet tail, the MIDI note count, the MP3's loudness, the buses and returns adding up to the premix, the loop's points and cues |
| `master`, `premaster` | the delivered master and the mix before mastering: `integrated_lufs`, `true_peak_dbtp`, `lra_lu` (loudness range, EBU Tech 3342), `sample_peak_dbfs`, `clipped_samples`, `frames`, `seconds`, `sha256` |
| `mastering` | the bus chain's record: `target_lufs`, `mixed` (after the master chain), `passes` (each delivery pass: gain, limiter ceiling, loudness, true peak), `limiting_db` (level the clipper and limiter took per section), `true_peak_ceiling_dbtp` (−1, or −2 above −14 LUFS), `limiter_dbfs`; with `dynamics: "wide"` also `peak_held_db`, `lra_lu` and `range`. With `mix.rules: 2` also `rules`. A wide master under version 2 has no limiter at all: its `limiter_dbfs` and its pass's `limit_dbfs` are `null`, and it has none of the fields that follow. A glue or loud master under version 2 has `limiter_dbtp` (the true peak the limiter aimed at) in place of `limiter_dbfs`, and `limiter`: `release_ms`, `lookahead_ms`, `share_of_time_pct` (how much of the piece it worked in) and `deepest_db`; each pass then holds `limit_dbtp` and `taken_db` (the level the clipper and limiter took, which the gain put back) |
| `buses` | `assignment` (part to bus), `spaces` (part to reverb), `returns` (the files in `returns/`), `level_change_db` (each bus against the sum of its stems, also in bus_level_change_db.json), `sum_minus_premix_peak_dbfs`. With `mix.rules: 2` also `rules`, what the mix set from the project, kept in `returns/mix_rules.json` too: `lead_threshold_dbfs` (the lead bus's compressor threshold, 6 dB over the loudest lead part's written level; `null` without a lead part and in a wide mix, where no bus compresses) and `reverb` (`null`, or with `mix.c80_db` the returns' `gain_db` and `c80_asked_db`, `c80_written_db`, `c80_db` and `c80_reached`) |
| `sections` | per section: `start_seconds`, `end_seconds`, `rms_dbfs`, `side_mid_db`, `active_tracks` |
| `mp3` | `mp3_lufs`, `mp3_true_peak_dbtp`, `matches` (within 0.2 LU of the master), `over_full_scale` (the decoded MP3's true peak above 0 dBTP, named in the summary); none in a draft |
| `loop` | a game loop: `start_sample`, `end_sample`, `length_samples`, `bpm`, `bar_beats` and `beat_count` (null where the tempo changes), `sections` (cue points), `files`, `gain_db`, `seam` (meter, timbre, pitch, abruptness and volume across the loop point), `layers` |
| `cache_hits`, `stems_reused`, `stem_count` | parts whose raw synthesis, and whose processed stem, came from the cache |
| `stage_seconds`, `process_seconds`, `runtime_seconds` | seconds per stage (they add up to the runtime) and in FFmpeg by kind |
| `validation`, `dependencies`, `project_sha256`, `renderer_sha256` | the project's validation, the tools and banks with their hashes |

## stem_receipts.json (render)

One entry per part: `track`, `cache_key` (its cache entry), `cache_hit` (raw synthesis from the cache), `stem_reused`
(processed stem from the cache), `gain_db` and `reference_level_dbfs` (the gain that set its level), `filter_chain`
(the FFmpeg processing), `raw_sha256`, `stem_sha256`, `same_pitch_retrigger_trims`, and where they apply `soundfont`,
`expressive` (crossfaded dynamics), `surge` (`rendered_with`, the fallback and why), `automation_points` (the
automation, applied after the chain), `nearly_silent` (an audition's context part kept at its own level), `stage`
(depth and early reflections), `production` (what each production tool did), `unlocked_cache` (the cache's drive could
not lock the entry, or the entry's folder could not be made there for want of permission, so the part was made in the
render's own `unlocked_cache/` folder: none of the cache's files was read or written, and trying for the lock made at
most the entry's folder and its `entry.lock`; the folder is the render's own, which `clean` takes with the render by
its record, never as a cache) and `seconds`: `waiting` (for another render's hold on the same cache entry, or for
memory while other parts held it), `synthesis` and `processing`.

## score_review.json (review)

| Key | What it holds |
|---|---|
| `prompts` | every review question, as the summary prints them |
| `association` questions | `association.missing` (the project records none), `association.whole` (words without the whole made of them), `association.gives` (the whole gave the music fewer than three levels); a project with `"association": {"none": "..."}` is asked none of them |
| `answered` | the questions a decision answers and that are therefore not asked: `id`, the question's `text` with what it counts now, and the `reason` (the decision after the identifier and its colon). An identifier holds no colon followed by a space, and the names in it are joined by plus signs: in a name a per cent sign is written `%25` and a plus sign `%2B`, and a space after a colon `%20` (a section named `answer: reprise` gives `plan:answer:%20reprise`; the sections `a+b` and `c` give `sections_alike:a%2Bb+c`), so no two questions about different names share an identifier. The identifier a decision answers is the text before its first colon and space, that one and no other, in every round; the summary prints each question's identifier in brackets |
| `plan` | null for a project without a plan, else the plan read against the score: `identity`; `high_point` (`section`, `means`, `in_piece`); `commitments`, `kept` and `differences` (counts of the statements that can be read off a score); and per planned section `kept` (the commitments the score holds), `differs` (each with `what`, `planned`, `found` and the sentence the question prints), `unread` (what cannot be read and why: a first section has none before it, a project without `harmony` has no pace) and `what_differs` (the plan's own sentence, compared with nothing) |
| `questions` | the same questions, each with its `text` and an `id` that does not depend on the wording: the kind of question and, after a colon, the part, the parts or the section it is about (`vertical`, `outside_chord.melody`, `sections_alike:verse+chorus`, `stiffness:keys`, `restatement:chorus`). Rounds and versions are compared by these |
| `views` | the score at a glance, which the summary prints before the questions. `parts_by_section`: per section the parts that sound in it, attacked there or held into it, each with `attacks`, `held_in`, `notes_per_bar`, `low` and `high`, `velocity`; `part_sets`: how many different sets of parts the sections have. `harmony_pace`: `entries` of `harmony`, `changes` (a chord that differs from the one before it, however it is spelled; the same chord written again is none), `changes_per_bar`, `kinds` (triad, added, seventh, extended, altered) and the same by section. `melody_rhythm`: for each part with the role `melody`, `syncopated_pct` and `pushes_pct` by the rule of `stiffness`, `longest_run` (the longest stretch it sounds without a rest of half a beat: `beats`, `seconds`, `from_bar`, `to_bar`), `bar_rhythms`, and by section its attacks, syncopations, pushes, rests and phrases. They describe the score; none is a question or a mark |
| `tracks` | per part: notes, pitch range, duration values, velocity range, key gaps, step share, phrase labels |
| `sections` | per section: seconds, active parts, onsets by role |
| `vertical_minor_seconds_ninths` | `count`, `foreground_count`, `by_parts`, `examples` (each `at`, `parts`, `pitches`, `ids` (the two notes, the lower pitch first), `overlap_beats`) |
| `outside_chord` | `count` and `examples` of the notes not resolved by step (each `at`, `track`, `note`, `id` and `struck` (the note and where it begins: a note held into a chord is named `at` the chord's beat, which is not where the note is written), `chord`, `approach`, `departure`), `not_resolved_by_step` (by melody, bass and accompaniment), `tracks` (each part's notes outside the chord counted by kind: passing, neighbour, suspension and the rest), `unparsed_symbols` |
| `parallel_fifths_octaves` | `count`, `by_pair`, `examples` (each `at`, `parts`, `interval`, `pitches`), `octaves_in_doublings` |
| `low_intervals` | `count`, `by_parts`, `furthest_below`, `examples` (each `at`, `parts`, `interval`, `notes`, `limit`) |
| `repetition` | `static_spans`, `part_loops`, `literal_returns`, `arrivals_thinner_than_before`, `sections_alike`, `energy` per section |
| `stiffness` | `block_chord_parts`, `parts`, `no_pushes_anywhere` |
| `melody_sections` | per section: phrases (a phrase ends at a rest of half a beat or at a note held a beat and a half), the longest of them (`longest_without_breath_*`: a guess at phrasing, not a measure of rest, which `views.melody_rhythm.longest_run` is), leaps, bars restated, the peak and where it falls |
| `transposed_samples`, `cannot_render` | with `--config`: notes played from samples far from their pitch, notes outside a preset, parts the banks cannot play |
| (question `piano:<part>`) | with `--config` and the `vcsl` bank installed: a piano part played on another piano than the Steinway grand ([piano-and-chamber.md](piano-and-chamber.md)); it has no field of its own, and a decision that begins with its identifier answers it. It is asked of the project's own banks only: a bank that someone configured themselves, the default bank included, may hold anything at any program |
| `loop_seam` | a game loop's seam from the score |

`notes.csv` lists every note with its bar, beat, pitch, velocity, timing and performed seconds; `arrangement.md` is
the sections, the authored decisions and the questions as a page.

## analysis.json (analyze)

| Key | What it holds |
|---|---|
| `sections` | per section of the master: `level_lufs_ungated`, `peak_dbfs`, `crest_db`, `band_share_pct` (six bands), `lr_correlation`, `mono_sum_change_db` |
| `lead_presence` | per section and span: `lead_minus_accompaniment_level_db`, its band-wise `_db_median` and `_db_p10`, `masked_share_pct`; `lead_tracks`, `lead_source` (buses or stems) |
| `melody_groups` | per section and span: `melody_group` (the melody and the parts doubling it), `melody_group_minus_rest_db`, `balance` (parts close to it: `level_minus_melody_db`, `suggested_cut_db`) |
| `stem_levels_lufs_ungated` | each part's level per section and span |
| `tonal_balance` | `slope_db_per_octave_100hz_4khz`, `low_end_vs_line_db`, `top_end_vs_line_db`, `third_octaves_db`, the published range it is read against |
| `reference_comparison` | with `--reference`: the slope, low and top end, each octave, width, loudness, peak to loudness and loudness range minus the reference's |
| `reverb` | a bus-chain render with reverb, from the project and the spaces' impulse responses: `early_decay_time_s` (of the spaces in use, weighted by what the parts send into each), `clarity_c80_db` (the mix taken as one room; `analyze` needs the render's `project.json`) with `hall_c80_db` (the range Barron recommends for concert halls) and, where the project asks one, `c80_asked_db`, and `spaces` |
| `master`, `side_minus_mid_db`, `warnings` | `integrated_lufs`, `true_peak_dbtp`, `lra_lu`, `plr_db`; width per band; what the analysis flags |

How to read these is in [measuring.md](measuring.md). At its peak `analyze` holds about ten float64 copies of the
song (9.7 measured on songs of one to four minutes with 14 parts): about 0.46 GB a minute of music. `analyze` and
`compare` read a render folder's own files only and refuse one holding links, or one that is itself a link (the
render inside a round too); a report's bus names are the mix's six or it is refused; no WAV longer than 31 minutes, the
longest a render can be, is read, a reference included.

## `compare_<name>.json` (compare)

`summary` holds what the printed summary shows: `project` (the edits), `synthesized_again`, `same_inputs_new_take`
(Surge XT parts with unchanged inputs, a new take), `changed` (one line per changed file) and `identical` (counts).
`files.<stems|buses|returns|premix|master>.<name>` holds per file `identical`, or `level_db` (the one gain that
matches the two files; null where matching by it leaves more than half the file's power, as in a part rewritten), `passages` (each
`start_s`, `end_s`, `from`, `to` and `follows_part_levels`), `difference_db` and `difference_peak_dbfs`;
`project_changes` the edits field by field, `synthesis` per part, `master_lufs` both masters' loudness, and `clip`
the A/B clip. `before`, `after` and the clip's `file` are relative to the report's folder.

## audition.json (audition)

`versions` in playing order: `sound`, `engine`, `master_lufs` (the version's render, its ring-out included),
`cut_lufs` (the cut the MP3 plays, before the versions are matched), `part_rms_dbfs`, `part_brightness` (`centroid_hz`,
`above_2k_pct`, `above_5k_pct`), and where they apply `surge_character`, `surge_controls` (what the mod wheel and
macros move), `rendered_with`, `fallback` and `reason`, `performance_left_out` (what the sound cannot take, and with
`--solo` a duck on a part left out). Also `kind`, `title`, `project` (relative to the audition's folder), `track`,
`bars`, `solo`, `status` (`RUNNING` from the start, then `PASS`, or `FAIL` with `failed`: the `version` that stopped it
and its `error`), `each_seconds`, `gap_seconds`, `loudness_lufs` (the level every cut plays at: the quietest cut's,
lower where the peak guard turned them all down) and `fallbacks`. Each version's render and its `cut.wav` are in its
numbered folder.

## clean (its report)

`studio.py clean` writes nothing of its own; `--json` prints its report: `dry_run` (true unless `--remove` was given),
`listed` (each folder it takes files from, or would: `kind` render, round, audition or cache entry, `path`, `bytes`,
`whole` whether the folder goes, and `kept_inside`, the first 20 of what stays in it: files no tool recorded or changed
since, and the folders inside it that stay, ending in `/`),
`bytes`, `kept` and `cache_entries_kept`, `left_alone` (folders of another piece, whose piece cannot be read, with no
files.json (made before 0.4.0), a render, round or audition at work, or inside one, cache entries holding files renders
did not write there or that changed since: `kind`, `path`, `title`, `why`) and `not_removed` (what was held open or in use by a render, with the
`error`).  A render, round or audition holds its folder's lock file `work.lock` while it runs and removes it when it
ends, `analyze` and `compare` hold the renders they read, and clean takes the same lock before it looks inside a
folder, keeping it, and those of the tool folders holding it, until it is done there; its dry run looks at each lock
without creating any.

## files.json (every folder)

Every folder a command writes holds `files.json`: `kind` (`music-production files`) and `files`, each file the tools
wrote there by its path relative to the folder, with its size, modification time and file number (`st_ino`). `clean`
removes a file only while that record lists it unchanged, as Ninja's clean tool removes only the outputs its build log
names (Ninja manual); a file put in such a folder, or changed since, stays, and so does a copy put in a file's place,
even one that keeps its size and time. A folder copied elsewhere, rather than moved, is so not the tools' any more:
`clean` leaves it and `--resume` refuses it. Installed banks and tools keep one in the runtime folder: an installer
replaces only what it recorded there and sets anything else aside as `<name>.replaced-<time>`.

While a render works, its folder and each cache entry it writes also hold `files.journal`, appended line by line: each
new file's name before the file is made and again, with its file number, once it is made (the render writes every file
under a new name of its own and gives it its name when it is whole), and each file's size, time and number before it
takes its name, as a database logs a change before it makes it (PostgreSQL documentation, Write-Ahead Logging). A
killed render so leaves only files its record or its journal proves: `--resume` removes those half written and takes
up the rest, and `clean` removes them with the recorded files. A name alone proves nothing: the journal proves the
file it noted, by its number, so a file put later under a name it holds, a copy even, is not the render's, and a
render killed in the instant between making a new file and noting it made leaves that file unproven. `--resume` names
such a file and stops, and `clean` leaves it. A file the render made stays the render's whatever is written into it
afterwards, as the programs it runs write their output into the file made for them: the temporary files of a render
(`.<name>.<random part>`) are its working space, so copy elsewhere what a stopped render left under such a name and is
worth keeping, before the next `--resume` or `clean`. A program the killed render had started (FluidSynth, FFmpeg, the
Surge host) can run on to its end and hold its new file meanwhile, which Windows will not let go: that file stays, the
journal naming it, until the next render or `clean` removes it. One case more leaves a file nothing proves: a
`--resume` or `clean` run before such a program has opened its output removes the file the render made for it, and the
program then makes another under that name (FluidSynth opens its output once its SoundFont is loaded: 0.1 to 6 seconds
after it starts on the three banks we measured, on one machine). That file stays too, named, until it is removed by
hand; the master is the same. The journal goes when the render ends and its record lists everything. A cache entry
keeps a `files.json` of its own, of what renders wrote in it, and `clean` removes an entry by it; an entry of 0.4.0,
which has none, goes by the names renders gave their files, its key and its receipt, as before. A render killed before
its first file, `render_input.json` (which names the piece too), leaves a folder `clean` cannot tell for a render's:
it stays, and `--resume` takes it up.

## What stays local

The records meant to be shared name files relative to their folders: round.json, the comparisons, audition.json and
the receipts. The logs (`logs/`, and each process's `*.process.json` with its command line) and the configuration
hold the full local paths, which can include your user name: share a render folder without them. Delivered audio
carries no tags from the files it was made from (every FFmpeg output is written with `-map_metadata -1`), only
FFmpeg's encoder tag and, in a loop's OGG, its `LOOPSTART` and `LOOPLENGTH`.
