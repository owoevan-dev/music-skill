# Performance and sound decisions

Performance (touch, timing, player-like deviation) and the mix (levels by role, the bus chain). How to read what `analyze` and `compare` measure is in [measuring.md](measuring.md).

Contents: [Tested baseline and its boundaries](#tested-baseline-and-its-boundaries) · [Touch and timing](#touch-and-timing) · [Player-like deviation: musiclib.expression](#player-like-deviation-musiclibexpression) · [Mix from musical roles](#mix-from-musical-roles) · [A bright pop piano](#a-bright-pop-piano) · [Brightness and air](#brightness-and-air) · [The bus chain (mix.chain: "bus")](#the-bus-chain-mixchain-bus) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

## Tested baseline and its boundaries

The pinned baseline is FluidSynth 2.6.1, FFmpeg 9.0.2 and the MuseScore MS Basic SF3 on Windows x64. Linux and macOS use the system FluidSynth and FFmpeg (6.0 or newer); the selfcheck there runs in CI, and results from other binary versions can differ slightly in samples. The engine imports NumPy only; it needs no DAW, account, plugin GUI or audio library.

Controlled probes of the default bank: velocity changes the MS Basic piano's sound and level; CC64 at 64 or above is a sustain switch, with no continuous half-pedalling; string CC11 mainly changes gain, with no multisampled dynamic crossfade or sampled legato. Do not present a volume swell as bowing realism. A preset that renders notes is not certified for every register or articulation: for an essential instrument, render a short range, velocity and CC probe before writing the piece around it.

FluidSynth runs in MMA bank-select mode, so a project `bank` below 128 selects that bank. The MS Basic "Expr." presets (banks 17/18) follow CC2 and are near-silent without it. Dedicated recordings for key parts are in [soundbanks.md](soundbanks.md), their measured attacks and quirks in [soundbank-measurements.md](soundbank-measurements.md).

## Touch and timing

- Shape performance by phrase, accompaniment role and metric accent. The KTH rules arch a phrase, growing toward it and relaxing at its end (Friberg et al. 2006), and pianists sound a chord's melody note louder and slightly ahead of the others (Goebl 2001, in [piano-and-chamber.md](piano-and-chamber.md)).
- Use shared tempo changes for rubato; let individual parts have small deliberate placements around that common clock. Preserve the groove's large pulses. Do not read every deviation from a sixteenth grid as expressive jitter: swing, tuplets and offsets from the click are mixed together.
- Use short gates for deliberate detached notes, suitable connection for singing lines, and a breath between phrases, as a singer takes one (Perricone 2000). Same-key overlapping MIDI retriggers are trimmed by the compiler and reported. This is note hygiene, not phrasing.
- Change the piano pedal with the harmony: held down, it works until the harmony changes or new notes clash with the sustaining ones, and then a quick lift and press clears it (Yamaha, How to Use Keyboard Pedals). Export the pedal release at the ending. String and wind long notes need envelopes but cannot gain absent sample articulations through arbitrary CC messages.
- Controller ramps: SoundFont tracks step between `cc` points unless `performance.cc_mode` is `linear`. Write a crescendo as two or three breakpoints with `linear`, not as a single jump.
- Sampled attacks: start slow-speaking parts early with `performance.offset_ms` (measured, e.g. −90 ms for sustained section strings) instead of shifting every note's `timing_ms`.
- Lead guitar with `performance.bend` (set `bend_range` to 12 so slides fit). Bending a string always raises its pitch, and rock and pop vibrato bends the string up and down, so it never falls below the note; players' vibrato differs widely in width and rate (Grimes 2014). The starting values in the guides are this skill's choices, not measurements: a bend up into a long target note from a whole step below, reaching pitch in 80–150 ms; a short slide into detached notes, 1–2 semitones below over 30–60 ms; vibrato only on held notes, after about a quarter of a second, from 0 to +30–50 cents at 5–7 Hz; an occasional release down at a phrase end.
- Strummed guitar chords: pass `{"strum": 6}` (ms between strings) for the guitar track in `musiclib.expression.apply`'s overrides. The hand alternates on the `strum_grid` steps (0.5 beats by default): chords on the beat are struck low to high and chords on the "and" high to low, a little faster and lighter, as the hand moves down and up; a chord off the grid is a downstroke, and `strum_grid` 0.25 alternates on sixteenths. The guides use 4–8 ms for driving rhythm parts and about 15 for slow, open strums: choices of this skill, not data, as no measurement of string-to-string timing was read.
- A melody on a sustaining sample (lead guitar, winds, solo strings) re-attacks every note, because each note-on restarts the recording's attack: set `performance.legato` so connected steps are slurred (hammer-ons and pull-offs on a guitar, tongue-less slurs on winds) and only phrase starts, repeated notes and wide leaps are re-attacked. A piano melody is struck by nature; there the line comes from overlap (connected notes held into the next by this skill's rule, the lesser of 45 ms and 15% of the interval, after the overlaps Repp 1995 and Bresin & Battel 2000 measured in legato playing; repeated notes about 60% of their interval, Bresin & Battel 2000), the melody voiced above its octave and inner notes and a little early, and the pedal changing with the harmony.
- Sustained orchestral parts on a bank with dynamic layers (`vsco`, `vsco_extra`, `cello_bigcat`) have two better tools ([orchestration.md](orchestration.md), [schema.md](schema.md)):
  - `performance.dynamics` moves a part through its recorded dynamics along a curve (one take per note by default, or crossfaded renders), so a crescendo brightens as it grows. In a selfcheck instrument with a soft sine take and a bright take, a crescendo from 40 to 127 took the spectral centroid from about 490 to 1550 Hz.
  - crossfade legato enters each slurred note past its recording's attack. On takes that swell in over 300 ms, the level at a slurred note change dipped at most 3–4 dB, against 11–16 dB when every note was attacked.
- A strum sounds the strings one after another, low to high on a downstroke; `strum` writes that order instead of every note on one sample.
- The built-in additive voice is intentionally synthetic. Its spectrum, glide, delayed vibrato and envelopes are editable in `instrument`. It is not an acoustic emulator, and its MIDI export carries the notes, not the timbre.

## Player-like deviation: `musiclib.expression`

A player is never exactly on the beat, and the distance is not a fresh random number at every note. `expression.apply(project, overrides, seed, drift='time')` writes deviation of the kind players produce on top of the authored performance:

- **A timing line per player**, a few milliseconds in size (2.5 ms drums to 6 ms melody).
  - It follows the model the research on keeping time with a beat uses most, linear phase correction: by the next beat the player takes back a share of the distance from the beat, and a new error comes on top (Repp 2005). So a part that is a little late stays a little late for a beat or two and then is not.
  - That share is measured between 0.2 and 0.8, and timing varies least when it is between 0.3 and 0.5 (van der Steen and Keller 2013). The skill uses 0.4; a part's profile can set another with `correction`.
  - On top of it each note has its own small motor delay, independent of the others (Wing and Kristofferson 1973).
  - Each part keeps to the score's beat by itself. No part's timing is taken from another's.
- **A slowly wandering loudness line per player.** In the recorded drum part analysed for it, the hi-hat's loudness wandered with long-range correlations (Räsänen et al. 2015); the velocities follow a line of that kind.
- **Pass `drift='time'` for a new piece.**
  - The lines run in time, on the sixteenth-note grid, so a note added or removed leaves what every other note draws as it was (its distance from the beat, its own small delay, its gate and its place on the loudness line), and `compare` shows the revision where it is. What is shaped from the notes around a note still follows them: a note added to a chord changes which note leads the chord and how it is strummed or spread, so the chord's other notes move; and with louder-for-higher on, a new high note moves the part's mean pitch and with it a neighbour's velocity by a step.
  - The default, `drift='notes'`, steps note by note; with it, a part's every note moves when it gains one.
  - Either way, a piece made longer draws its lines again.
  - Measured here on a steady sixteenth-note hi-hat, both give the same statistics: timing deviation 2.9 ms; correlation +0.64 between neighbouring notes, +0.45 a beat apart and +0.27 two beats apart.
- **Scripts written for 0.5 or before** write another performance under 0.6, of the same size: the timing line and the note lengths are drawn another way, and the loudness line takes other values with them. On a sampled instrument a note whose velocity lies near the border of two recorded dynamics can come out on the other side of it, so an exposed line can sound different. A project file already written keeps the performance it holds.
- a fixed feel per part, e.g. a bass a few milliseconds behind, two rhythm guitars apart;
- phrase arches and slightly louder high notes on melodic parts (KTH rules, Friberg et al. 2006);
- chord notes that are neither struck nor released together: the top note leads on keyboards, section players spread;
- a two-bar accent cycle on hi-hat and ride, and CC11 swells inside held chords of sustained parts.

Profiles come from the track role; `overrides` maps track ids to changed profile values (for example `{"bass": {"feel": 4}, "lead": {"lead": 18, "spread": 4}}`) or `None` to leave a part as written. Results are deterministic for a seed. Keep deviations small on tight drum grooves: listeners rated exaggerated microtiming worse than an expert's or a quantized version (Senn et al. 2016, in [development-and-groove.md](development-and-groove.md)). Keep chord spread: pianists do not sound a chord's notes together (Goebl 2001).

## Mix from musical roles

Each part has a chosen reference level (`level_dbfs`). `active_rms` measures the 70th percentile of non-silent half-second blocks; `peak` suits drum accents. This makes setup reproducible but is not a balance oracle: a rare accent should not become as loud as the melody just because both were normalized.

Build the balance from the most important part down. Senior (2009) starts a mix with its most important track and adds less important ones in turn, cutting a newly added part where it masks a more important one; rock and dance mixes often start from the rhythm section, pop mixes from the lead. Check sustained background notes as well as attacks: to find what masks the lead, mute the other parts one at a time (Senior 2018). Keep the bass clear by controlling overlapping low material, such as a pad's energy below about 200 Hz (Senior 2010), before raising the lead.

Check the low end against the bass recording, not only the mix: when a bass sample carries little fundamental (MS Basic picked bass at D2: about 2%), EQ cannot restore it. In one test piece a near-sine additive sub (three harmonics, low-pass 120 Hz, following the bass line, folded into E1–D♯2) raised the chorus share below 60 Hz from about 1% to 12–15% of the power, where a mix-only revision had moved it by less than one point.

A part's `highpass` falls 12 dB per octave: an octave under the part's lowest note keeps that note's fundamental within 0.3 dB, while a cutoff a major third under it takes 1.5 dB, and `review` names such a part. A high-pass that reaches into a line's fundamentals makes the balance between each note's fundamental and its harmonics vary from note to note, the more so the steeper it is: an 80 Hz fundamental can end up 24 dB or more down against the note an octave above (Senior 2020). The 1.5 dB at which `review` names a part is this skill's. When noise or hiss is heard, find the part and what the noise is before treating it ([noise.md](noise.md)): most of it belongs to the instruments, and the banks' recordings carry little.

Use pan to separate parts while keeping a stable centre: the most prominent parts and the bass are conventionally centred so the core of the song survives on most systems, and other parts spread for width (Flint 2005). Wide important parts lose balance and tone in mono (Senior 2010), so check the mix in mono. Spaced-microphone samples can measure near-zero left/right correlation, so a lead built on them sits diffuse: `mix.width` around 0.3–0.5 puts it in front.

## A bright pop piano

Measured here: the same figure (a C5–E5–G5 chord and eighths up to C6) on every piano in the banks, with its spectral
centroid and the share of its energy above 2 kHz. The recording chosen and the touch changed the brightness more than EQ
did.

| Piano | Centroid at velocity 110 | Above 2 kHz | Velocity 50 → 110 |
|---|---|---|---|
| FM piano (`vcsl_keys` 0:4, an electric piano) | 2253 Hz | 36% | 993 → 2253 Hz |
| Upright (`vsco_colors` 0:0) | 959 Hz | 7.6% | 709 → 959 Hz |
| Upright Yamaha (`vcsl_keys` 0:3) | 936 Hz | 6.7% | 713 → 936 Hz |
| Grand Kawai (`vcsl_keys` 0:1) | 820 Hz | 2.7% | 676 → 820 Hz |
| GM Bright Acoustic, Acoustic Grand (default 0:1, 0:0) | 762, 721 Hz | 0.8%, 0.3% | small |
| Grand Steinway B (`vcsl` 0:0) | 747 Hz | 1.1% | 707 → 747 Hz |
| Osiris, dampers down or pedal (`piano_osiris`) | 627–643 Hz | 0% | small |

- **The recording.** The Kawai is the brightest grand and grows brighter with velocity across its four dynamics; the
  uprights are brighter still; Osiris is the darkest.
- **The touch.** The banks' brighter layers sound at higher velocities: from velocity 80 to 110 the Kawai's centroid
  rose 51 Hz.
- **EQ.** On the Kawai at velocity 110, −2 dB at 300 Hz (the boxy, muddy region) with +1.5 dB at 1.6 kHz and +2.5 dB
  at 4 kHz (`mix.eq` [[300, -2], [1600, 1.5], [4000, 2.5]]) raised the centroid 77 Hz, about 9%. A further +3 dB at
  12 kHz added 5 Hz: a piano has little energy that high (0.1% above 5 kHz), and Mike Senior found such a boost
  brought out the hammers' hardness. His pop-piano treatment in Sound On Sound used two broad 1 dB moves, a cut at
  255 Hz and a lift at 1.6 kHz, and a cut of a couple of dB in the 200–400 Hz "danger zone".
- **Compression** evens the part (4:1 gave his melodic hook a "more chiming" quality) but lowered the centroid a
  little here: set it for evenness, not brightness.
- The master chain adds its own presence and air (3.2 kHz, 10 kHz shelf) to the whole mix.

## Brightness and air

What brightens a mix, by its sources; numbers measured here say so.

- **The genre's top.** US and UK number-one singles of 1950–2010 fall about 5 dB per octave from 100 Hz to 4 kHz and
  faster above; on the slope of their log-log spectrum over 100 Hz–10 kHz, electronic averaged −0.75, disco −0.80,
  hip-hop −0.81, pop −0.94, rock −0.98, soul and R&B −1.03, folk −1.18 and jazz −1.29, and the top ends of the genres
  differed by more than 10 dB (Pestana et al. 2013). The steeper the slope, the less top. `analyze` sets the master's
  slope beside the mean of the genre that governs the piece's mix axis (`published_genre`, from style-maps.json) and
  asks about a master more than 0.3 steeper, a margin this skill chose. Those songs carry vocals; these pieces do not.
- **Percussion.** Tracks with more percussion have relatively more bass and treble, and percussive prominence accounts
  for much of the difference between genres (Elowsson and Friberg 2017). Hi-hats, shakers, tambourine and cymbals
  carry most of a mix's top, so their level and density come first; a piece without them sits steeper, as expected.
- **Register and dynamics.** Parts written higher put more energy at the top. A louder recorded dynamic is brighter,
  not only louder ([orchestration.md](orchestration.md), Dynamics that change the tone), and a sampled part played
  soft stays dark whatever its EQ ([A bright pop piano](#a-bright-pop-piano)).
- **The sound.** `studio.py sounds --character bright` lists catalog patches measured bright; parts in front stay
  brighter and drier than those behind them (White 2009, in [sound-selection.md](sound-selection.md)).
- **Low-passes.** Widespread low-pass filtering seldom helps a mix, because the harmonics and noise of most
  instruments reach up the spectrum, and it easily dulls one; a low-pass suits a part case by case, such as an
  amplified guitar's noise in the top two octaves, for the balance (Senior 2012). A two-pole low-pass at 12 kHz takes 3 dB at 12 kHz,
  8 dB at 15 kHz and 15 dB at 18 kHz. Measured here: the sixteen 0.4.0 agent pieces low-passed 45 of their 163 parts
  at or under 12 kHz, and eight of them every part. `review` asks when most parts other than the bass sit at or under
  12 kHz, except in lo-fi, whose mix is unpolished on purpose.
- **The names of the bands.** In the mixing books Moffat, De Man and Reiss (2022) list, air is 10–20 or 12–20 kHz in
  five of the nine ranges given (11–22.5, 12–16 and 12–15 kHz in three others, 5–8 kHz in one); clarity 2.5–4 or
  2.5–5 kHz in two of four (3–12 and 4–16 kHz in the others); presence lies within 1.5–8 kHz in four of six. In their
  equalization data, "thin", "clean", "cut", "click" and "tin" went with
  boosts from 5 kHz up and less low end; "warm", "bass", "boom", "box" and "vocal" with a boost near 500 Hz and the
  top rolled off.
- **No single right value.** When eight songs were each mixed by eight engineers (two classes of eight, four songs a class), the mixes' spectral centroids differed
  strongly between engineers, and processing left every track but the bass guitar and the kick brighter than it was
  recorded (De Man et al. 2014).
- **Reverb.** More reverb puts a part further back (White 2009). The reverb returns here are low-passed at 13 kHz, so
  a wetter mix has less top.
- **The chain.** A part passes a low-pass at 18 kHz unless it sets its own (−0.6 dB at 15 kHz, −3 dB at 18 kHz), and
  the master adds 2.5 dB above 10 kHz and 0.8 dB at 3.2 kHz (this skill's master EQ: the shelf lies in the air band the
  mixing books name, its amounts were set in the skill's first versions and come from no source): computed from these
  filters, a part at the defaults leaves the master 1.3–1.7 dB brighter from 10 to 15 kHz than it went in.

## The bus chain (`mix.chain: "bus"`)

| Bus | Default members | Processing | Reverb send goes to |
|---|---|---|---|
| drums | drum parts | a hard-compressed copy mixed 20 dB under the dry kit, light tanh saturation | room |
| bass | role `bass` | light tanh saturation | room |
| rhythm | role `rhythm` | 2:1 compression, light saturation | room |
| ensemble | every other role | gentle 1.5:1 compression | hall |
| lead | role `melody` | 3:1 compression with makeup | plate |
| fx | role `effect`, noise parts | none | hall |

Override with `mix.bus` and `mix.space` per track: a clean guitar comping with the band belongs in rhythm, a string ostinato in ensemble. The spaces are generated noise impulse responses that decay faster at high frequencies (room 0.45 s, plate 1.7 s, hall 2.2 s and church 4.2 s at 1 kHz), with early reflections in the room, hall and church. No bus sends to the church by default; organ parts choose it ([organ.md](organ.md)). The delay send is shared and filtered as in the room chain.

`mix.depth_m` stands a part on a modelled stage (a shoebox hall 24 × 40 × 16 m heard from a main pair 4 m in front of the stage, 3.5 m up). Its pan stays on the direct sound and on time; image sources up to the second order add its early reflections from that position, each darkened a little per wall and all high-passed at 250 Hz (below that, specular images add up in phase into a boom and a comb on the direct sound); the result keeps the part's energy, and its reverb send rises by half the distance loss. For broadband noise at the centre, from the first desks to 8 m back the reflections grow from about 13 to about 6 dB under the direct sound and the send rises about 4 dB; the two capsules receive different reflections (correlation about 0.1), which widens the part. `stage` in the stem receipt reports these numbers.

The premix is brought to −18 LUFS for glue compression (about 2 dB on the loudest passages), a 2.5 dB air shelf at 10 kHz and a little presence at 3.2 kHz, then one gain toward `target_lufs` feeds a limiter half a dB under the true-peak ceiling. The ceiling is −1 dBTP, and −2 dBTP for a master louder than −14 LUFS, as Spotify asks of the masters it encodes: louder tracks gain more distortion in lossy encoding ([Spotify for Artists: Loudness normalization](https://support.spotify.com/us/artists/article/loudness-normalization/)). Measured here, a −9 LUFS master at −1.13 dBTP decoded from its MP3 at +0.06 dBTP. The limiter holds sample peaks, so bright transients (cymbals, mallets, distorted guitars) can still overshoot between samples. When the true peak passes the ceiling, the limiter's ceiling comes down by the overshoot plus a margin, and the gain restores the loudness. Up to four passes run, each listed in `report.json` under `mastering.passes`. The render fails if the true peak still exceeds the ceiling (`mastering.true_peak_ceiling_dbtp`) or the MP3 decodes to a different loudness, and its summary names an MP3 that decodes above full scale.

With `mix.dynamics: "wide"`, for orchestral and organ music ([orchestration.md](orchestration.md)), the buses pass their parts unchanged and the master keeps only its gain and EQ. One gain brings the mix to `target_lufs`; if the true peak would then pass 0.2 dB under the ceiling (−1.2 dBTP, or −2.2 above −14 LUFS), the gain is held down (`mastering.peak_held_db`). Under version 1 of the mix's rules a limiter at the ceiling stays as a guard; under version 2 a wide master has no limiter at all, since the gain already holds the peak the meter read and the render checks the master's true peak. `mastering.lra_lu` and `mastering.mixed.lra_lu` give the loudness range (EBU Tech 3342) of the master and of the mix.

### The rules of version 2 (`mix.rules: 2`)

Version 2 keeps the chain and changes four things. None of the four is set from a measurement of the piece's audio: each takes what it needs from what the project writes and from the tool's own reverbs. What version 1 measures, version 2 still does: every part is brought to its written level, the mix to its loudness target, and a wide master's `range_lu` works from the measured loudness. A project without `rules` stays on version 1 and is mixed as it was.

| What | Version 1 | Version 2 | From |
|---|---|---|---|
| Lead bus's compressor threshold | one figure for every piece (−22 dBFS), with 4 dB of make-up | 6 dB over the written level (`level_dbfs`) of the loudest lead part, with 0.4 dB of make-up | the usual way of setting a compressor: the threshold is moved to match the signal's level, and make-up gain then puts the level right (White, Inglis et al. 2003). Here the level is the one the project writes; the distance and the make-up are this skill's, from its own measurement below |
| Saturation on the drum, bass and rhythm buses | the tanh curve at the sample rate | the same curve at four times the rate, between two resamplers, so that far less of its harmonics folds back into the band | this skill's measurement: the folded part under three drum buses went from 53–80 dB down to 100 dB down or lower. It is lowered, not removed: a 19 kHz tone at 0.9 of full scale still leaves a fold at 17 kHz about 100 dB under it |
| Limiter | FFmpeg's on sample peaks, set half a decibel low and lowered pass by pass | one limiter on true peaks, aimed 0.1 dB under the ceiling | Hämäläinen (2002); true peak as ITU-R BS.1770-4 measures it |
| How near the piece is heard | not set | `mix.c80_db` asks a clarity, and one gain on the spaces' returns gives it, worked out from the project file and the spaces' impulse responses | the clarity index C80 as Barron (2013) reports it ([orchestration.md](orchestration.md#how-near-the-orchestra-is-heard)) |

The other compressors' thresholds, ratios, times and make-ups, the knee, the saturation amounts and the master's EQ are unchanged and remain this skill's own starting values. No source read gives others for them: judge them by ear.

**The lead stays near where you write it.** Under version 1 the lead bus's compressor had one threshold for every piece, so a lead written loud was compressed hard and a quiet one hardly. On this skill's test projects it took between 1.2 and 8.9 dB from the lead bus's loudness, and with its one make-up the lead bus came out between 4.8 dB quieter and 2.8 dB louder than the sum of its stems as they enter it (`buses.level_change_db`). Under version 2 the threshold follows the written level, so the compressor works as deep on a quiet lead as on a loud one.
- Measured on the 27 test projects rendered under version 2: of the 21 whose lead bus compresses, the lead bus ended within 0.4 dB of the sum of its parts on 20 (`buses.level_change_db` compares the bus with its stems' sum), and 1.1 dB under on one, a bell line. Those are this skill's test projects, not a bound: another piece can fall outside. A part of short, hard notes has peaks far over its level, so more of it stands over the threshold: check `buses.level_change_db` on such a lead and answer it with the part's `level_dbfs`.
- The lead is compressed less than version 1 compressed it on most pieces. Its loudest peaks come down by a few decibels (2 to 6 dB on the four pieces where that was read) and the body of the line is left alone. That is a difference in sound, to be judged by ear: a lead that should be denser takes a compressor of its own (`mix.compressor`, [schema.md](schema.md#tracks)).
- The compressor leaves a lead alone while what enters the bus peaks under the threshold. One lead part whose level is written as a peak (`level_mode: "peak"`) does so as long as nothing after its level raises it: the level is set first, and the part's EQ, effects and automation come after it, so a boost there (automation of +12 dB, say) lifts the part over the threshold and it is compressed. Several lead parts sounding together can add up over it too.
- The other buses are as under version 1. Their compressors took little there (the rhythm and the ensemble bus at most 1.4 dB on the test projects); the drum bus rises by what its parallel copy adds, up to 2.9 dB. `buses.level_change_db` gives each bus against its parts for every render: where a bus has moved more than the piece should have, write its parts' `level_dbfs` to answer it.

**How much reverb.** The sends stay as the project writes them. For a mix of a song, De Man, McNally and Reiss (2017) had 80 mixes of ten songs rated by skilled listeners and compared the loudness of everything the reverbs returned with the loudness of the dry signal: every mix whose reverb stood 9 LU under the dry signal or nearer was called too reverberant, and about 14 LU under lay between the mixes called too reverberant and those called too dry. Their songs were pop and rock with vocals. This skill does not measure that quantity; set the sends by ear, a style that is dry on purpose lower.

**How near, instead of how much.** An orchestral piece is judged another way, by how near the players are heard, and a hall has far more reverberant sound than a song's mix. Such a piece sets `mix.c80_db`, and the returns move to give the mix that clarity ([orchestration.md](orchestration.md#how-near-the-orchestra-is-heard)). The clarity is worked out from the project file (each part's written level, the time its notes sound and its send) and from the spaces' impulse responses, so it is the same before a note is rendered and whatever the parts' sounds do; it changes when the written levels, sends or note lengths do.

**The limiter** holds true peaks, so the master reaches its ceiling in one pass where version 1 needed up to four, and it adds no delay (version 1's master trails its mix by about 10 ms, which a loop's layers are shifted to match). It keeps one steady gain over a low note instead of following the waveform: pushed 6 dB into limiting, a 50 Hz tone came out with its harmonics 115 dB down against 37 dB down from version 1's limiter, and the SMPTE intermodulation test (60 Hz with 7 kHz) read −93 dB against −39 dB. Its release is 60 ms, as version 1's limiter has. `mastering.limiter` reports the release, the share of the piece in which it worked and its deepest reduction.

`mix.range_lu` narrows a wide master's loudness range for listening on small speakers. From the 3 s short-term loudness (every 100 ms, gated as Tech 3342 gates it), each passage under the 95th percentile rises by one share of its distance from there; a passage under the 10th percentile rises as one at it. The lift is smoothed over 1.5 s, so it follows phrases, and the share is set until the range meets the target. In a selfcheck signal with sections 14 and 8 dB under the loudest, a 14 LU range came down to 8 LU: the softest section rose 6 dB, the middle one 3.5 dB, and the loudest stayed within 0.2 dB. `mastering.range` reports the range before and after and the largest lift.

`bus_level_change_db.json` compares each bus with the sum of its stems. In a finished piece the drums gained 2.0 dB from the parallel compression, a piano lead lost 3.3 dB to its compressor, and the other buses moved by less than 0.2 dB. A bus far outside such values is worth a look at its members' levels.

The room chain applies constant gain into an oversampled limiter with a bounded peak allowance and may finish below the requested loudness rather than crush the dynamics.

## Sources

- Bresin, R. and Battel, G. U. (2000). Articulation strategies in expressive piano performance: analysis of legato, staccato, and repeated notes in performances of the Andante movement of Mozart's Sonata in G major (K 545). *Journal of New Music Research* 29(3), 211–224.
- De Man, B., Leonard, B., King, R. and Reiss, J. D. (2014). [An analysis and evaluation of audio features for multitrack music mixtures](https://archives.ismir.net/ismir2014/paper/000293.pdf). *Proceedings of the 15th ISMIR Conference*, Taipei, 137–142.
- De Man, B., McNally, K. and Reiss, J. D. (2017). [Perceptual evaluation and analysis of reverberation in multitrack music production](https://doi.org/10.17743/jaes.2016.0062). *Journal of the Audio Engineering Society* 65(1/2), 108–116. Open access (CC BY). Relative reverb loudness, the mixes called too reverberant and too dry, and the 5–6 dB it cites as the just-noticeable difference of the direct-to-reverberant ratio.
- Elowsson, A. and Friberg, A. (2017). [Long-term average spectrum in popular music and its relation to the level of the percussion](https://www.aes.org/e-lib/browse.cfm?elib=18638). AES 142nd Convention, Berlin, paper 9762. Read in its abstract.
- Fabiani, M. and Friberg, A. (2011). Influence of pitch, loudness, and timbre on the perception of instrument dynamics. *Journal of the Acoustical Society of America* 130(4), EL193–EL199.
- Flint, T. (2005). [Q. Should I always pan my vocals to the centre of the mix?](https://www.soundonsound.com/sound-advice/q-should-always-pan-my-vocals-centre-mix) *Sound On Sound*, February 2005.
- Friberg, A., Bresin, R. and Sundberg, J. (2006). Overview of the KTH rule system for musical performance. *Advances in Cognitive Psychology* 2(2–3), 145–161.
- Frühauf, J., Kopiez, R. and Platz, F. (2013). Music on the timing grid: the influence of microtiming on the perceived groove quality of a simple drum pattern performance. *Musicae Scientiae* 17(2), 246–260.
- Goebl, W. (2001). Melody lead in piano performance: expressive device or artifact? *Journal of the Acoustical Society of America* 110(1), 563–572.
- Grimes, D. R. (2014). [String Theory: The Physics of String-Bending and Other Electric Guitar Techniques](https://doi.org/10.1371/journal.pone.0102088). *PLoS ONE* 9(7), e102088.
- Hämäläinen, P. (2002). Smoothing of the control signal without clipped output in digital peak limiters. *Proceedings of the 5th International Conference on Digital Audio Effects (DAFx-02)*, Hamburg, 195–198. A running maximum over the look-ahead, then an average over no more than it, keeps a smoothed limiter from ever passing a peak.
- ITU-R BS.1770-4 (2015). [Algorithms to measure audio programme loudness and true-peak audio level](https://www.itu.int/rec/R-REC-BS.1770). Gated loudness, and true peak from the signal at four times the sample rate (annex 2).
- Moffat, D., De Man, B. and Reiss, J. D. (2022). [Semantic music production: a meta-study](https://doi.org/10.17743/jaes.2022.0023). *Journal of the Audio Engineering Society* 70(7/8), 548–564. Its Table 2 cites Owsinski (2006), Coryat (2008), Izhaki (2008), White (1999), Katz (2002), Cousins and Hepworth-Sawyer (2013), Waddell (2013) and Huber and Runstein (2014) for the bands.
- Perricone, J. (2000). *Melody in Songwriting*. Berklee Press. The [Chapter 1 excerpt](https://online.berklee.edu/takenote/conjunct-disjunct-melody-basic-definitions/).
- Pestana, P. D., Ma, Z., Reiss, J. D., Barbosa, A. and Black, D. A. A. (2013). [Spectral characteristics of popular commercial recordings 1950–2010](https://www.aes.org/e-lib/browse.cfm?elib=17010). AES 135th Convention, New York, paper 8960.
- Räsänen, E., Pulkkinen, O., Virtanen, T., Zollner, M. and Hennig, H. (2015). [Fluctuations of hi-hat timing and dynamics in a virtuoso drum track of a popular music recording](https://doi.org/10.1371/journal.pone.0127902). *PLoS ONE* 10(6), e0127902.
- Repp, B. H. (2005). [Sensorimotor synchronization: a review of the tapping literature](https://doi.org/10.3758/BF03206433). *Psychonomic Bulletin & Review* 12(6), 969–992. Section 5, models of error correction: linear phase correction, after Vorberg and Wing (1996) and Vorberg and Schulze (2002).
- Repp, B. H. (1995). Acoustics, perception, and production of legato articulation on a digital piano. *Journal of the Acoustical Society of America* 97(6), 3862–3874.
- Senior, M. (2009). [Q. What's the best order for mixing?](https://www.soundonsound.com/sound-advice/q-whats-best-order-mixing) *Sound On Sound*, June 2009.
- Senior, M. (2010). [Creating & Using Synth Pad Sounds](https://www.soundonsound.com/techniques/creating-using-synth-pad-sounds). *Sound On Sound*, May 2010.
- Senior, M. (2012). [Q. Do mixes benefit from low-pass filtering at mixdown?](https://www.soundonsound.com/sound-advice/q-do-mixes-benefit-low-pass-filtering-mixdown) *Sound On Sound*, January 2012.
- Senior, M. (2018). [Q. How can I locate the masking problems in my mix?](https://www.soundonsound.com/sound-advice/q-how-can-locate-masking-problems-my-mix) *Sound On Sound*, March 2018.
- Senior, M. (2020). [Q. How steep should I make a high-pass filter?](https://www.soundonsound.com/sound-advice/q-how-steep-should-make-high-pass-filter) *Sound On Sound*, June 2020: a steep high-pass varies the balance of fundamental and harmonics from note to note.
- Senior, M. [Mix Rescue: The Mountaineering Club](https://www.soundonsound.com/techniques/mix-rescue-mountaineering-club). *Sound On Sound*. A pop production's piano: the broad cut at 255 Hz and lift at 1.6 kHz, the 200–400 Hz "danger zone", the 12 kHz boost and its hammer hardness, 4:1 compression on the hook.
- van der Steen, M. C. and Keller, P. E. (2013). [The ADaptation and Anticipation Model (ADAM) of sensorimotor synchronization](https://doi.org/10.3389/fnhum.2013.00253). *Frontiers in Human Neuroscience* 7, 253. The range of measured phase correction (0.2 to 0.8) and the share at which timing varies least (0.3 to 0.5, after Repp and Keller 2008).
- White, P., Inglis, S. et al. (2003). [Using Your DAW's Compressors & Limiters](https://www.soundonsound.com/techniques/using-your-daws-compressors-limiters). *Sound On Sound*.
- White, P. (2009). [Creating A Sense Of Depth In Your Mix](https://www.soundonsound.com/techniques/creating-sense-depth-your-mix). *Sound On Sound*, February 2009.
- Wing, A. M. and Kristofferson, A. B. (1973). [Response delays and the timing of discrete motor responses](https://doi.org/10.3758/BF03198607). *Perception & Psychophysics* 14(1), 5–12. A timekeeper and a motor delay after it, each independent from one response to the next.
- Yamaha. [How to Use Keyboard Pedals](https://hub.yamaha.com/keyboards/k-how-to/how-to-use-keyboard-pedals/). Yamaha Hub.
