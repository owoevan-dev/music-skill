# Sources, permissions and provenance

The skill's original code and guidance are MIT. That does not relicense external executables, instrument samples, reference scores, MIDI performances or recordings. Keep each dependency/material's original notice and source link. The skill itself publishes nothing: it creates no remote repository and uploads no audio.

## First corpus

The guidance in [arrangement.md](arrangement.md) draws on this study corpus. The corpus itself is not distributed with the skill.

| Material | Official evidence | Selection |
|---|---|---|
| OpenScore Lieder and String Quartets | [OpenScore owner](https://fourscoreandmore.org/openscore/), [Lieder](https://github.com/OpenScore/Lieder), [StringQuartets](https://github.com/OpenScore/StringQuartets) | CC0 digital scores, selected historical compositions. Exact commits and file hashes are retained. |
| Original Google Groove MIDI Dataset v1.0.0 | [Google dataset page](https://magenta.withgoogle.com/datasets/groove) | CC BY 4.0; MIDI-only archive verified against the publisher's SHA-256. Credit Google LLC, the dataset and Gillick et al. (ICML 2019); retain source/license links and indicate derived analysis. |
| Mutopia K.488 and Magic Flute Overture | [Item 2229](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=2229), [item 248](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=248), [license explanation](https://www.mutopiaproject.org/legal.html) | These two item pages and source headers state Public Domain. The site as a whole has mixed licenses. The concerto MIDI set is incomplete: its third movement contains no notes. |

Source bytes remain in a separate research corpus, outside the installable MIT skill. Analyses retain attribution even when describing statistical facts. Do not state that the first corpus includes aligned real performances of all works: OpenScore/Mutopia supply scores or score-generated MIDI; GMD's published paired audio is electronic-drum synthesis, and only MIDI was downloaded here.

For additional materials, record title, composer/arranger/performer/typesetter, official source, revision, retrieval date, exact license/evidence, hash and modifications. Check composition/arrangement, digital edition, performance and recording separately. A score's CC0 dedication does not cover an unrelated commercial recording. Do not treat a software repository's MIT file as a blanket license for music scraped into its dataset.

What is taken into the skill and what is only cited are kept apart:

- **Taken in.** Anything copied or adapted into the skill (text, tables, figures, scores, MIDI, recordings, data files) comes only from sources that allow it with no condition on the result: public domain, CC0, CC BY, MIT and the like, each credited where its licence asks. Material under non-commercial, no-derivatives or share-alike terms, or of unknown rights, is not copied or adapted, and no dataset under non-commercial terms produces a number here.
- **Cited.** A fact, a measurement or a method that a paper, a book or an article states is given in this skill's own words with its source, whatever licence the publication carries, as in any scholarly writing. No table or figure is reproduced, and a quotation is short and marked.

This is a project choice, made to keep the release permissive and reusable, not a claim that every such license is inherently incompatible with MIT. Public-domain status can depend on jurisdiction and publication history; use clear historical works and explicit digital-edition evidence rather than a blanket statement of global clearance.

## Source security

Use official HTTPS download endpoints; pin revisions and verify publisher checksums when provided. Download data separately from executable dependencies. Bound archive size/member count; reject traversal and symlinks; extract only expected data extensions. Do not execute LilyPond source or arbitrary code embedded in a reference package.

The study parser rejects XML DTD/entities and parses only bounded score data; the MIDI reader bounds bytes/events and never executes text or SysEx. Anomaly records are retained. These are format/security precautions, not antivirus certification. No successful antivirus scan of this first corpus/runtime is claimed.

## Sound banks

Optional recordings are listed with their evidence in [soundbanks.md](soundbanks.md). All are CC0 (FreePats FSBS guitars and Bass YR, and banks built here from VSCO 2 CE, VCSL, Karoryfer, Big Rusty Drums and sfzinstruments samples) except the University of Iowa Musical Instrument Samples, whose publisher states that they "may be downloaded and used for any projects, without restrictions", and John Learman's steel drum, dedicated to the public domain under the Unlicense; music made with any of them needs no credit. CC BY banks such as Salamander Grand Piano or MuldjordKit are not offered: they would need a credit wherever the music is published. A bank built here from CC0 samples keeps the samples' CC0 status; the build spec and receipt record every source file hash and change. Banks are runtime data, never bundled in the skill package, and never executed. The banks built here are also offered prebuilt, as assets of the repository's release, byte for byte what a build from the sources gives: CC0, the Unlicense and the Iowa grant ("for any projects, without restrictions") all allow that, and the release notes keep the VSCO readme's requests (not sold as such, improvements kept open, a credit with a link) and the credits the publishers ask for.

## Runtime licenses

- FluidSynth: LGPL-2.1-or-later, invoked as a separate executable (the pinned Windows build, or the system package on Linux and macOS).
- FFmpeg: the pinned Windows build from Gyan is a GPL-3.0 build; system packages carry their own build licence. Invoked as a separate executable on local WAV files with numeric filter settings.
- MS Basic SoundFont: MIT with named sample-author notices; preserve the complete upstream notice.
- NumPy: BSD-3-Clause.
- Surge XT and its factory patches: GPL-3.0-or-later, the plugin-only Windows release pinned by hash (or the user's own install elsewhere) and the curated patches from the pinned repository commit, each checked by hash. pedalboard: GPL-3.0, the pinned wheel checked against the hashes PyPI publishes. Both run only inside `scripts/surge_host.py`, a GPL-3.0-or-later program of this skill that the renderer starts as its own process and exchanges files with (a job in, a WAV out); the skill's MIT code never runs in that process except one helper the host imports (MIT code may be used in a GPL program). The only GPL file the skill itself carries is that host script; Surge XT and pedalboard are downloaded to the user's machine. Audio rendered with them is not covered by their licence.

The installable package does not bundle these binaries or samples. Installing dependencies separately keeps their original licensing clear; redistributing them later would require satisfying their own notices/source obligations. The original room impulse and synthetic instruments in the skill have no external sample assets.
