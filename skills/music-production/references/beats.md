# Beats: lo-fi, boom bap, trap and instrumental hip-hop

Read this when the request is any of these:
- a lo-fi or chillhop beat, a "beats to study to" loop, or jazz-hop;
- a boom-bap or trap instrumental;
- a background beat for a stream or a video.

Its sub-styles (lo-fi, boom bap, trap, drill, phonk, trip hop, G-funk), each on the seven axes with its sources and what `review` asks there, are in [style-map-beats.md](style-map-beats.md).

Contents: [Brief](#brief) · [Groove](#groove) · [Lo-fi and chillhop](#lo-fi-and-chillhop) · [Boom bap](#boom-bap) · [Trap](#trap) · [The worn sound](#the-worn-sound) · [Symptoms and causes](#symptoms-and-causes) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

These are loops first: a two-, four- or eight-bar figure of drums, bass and chords that has to feel good on its hundredth repeat, with a few changes over the top. Much of each style's character is in the groove (where each hit falls) and in the sound of the machines and media it grew up on. For dance music and synth styles see [electronic.md](electronic.md); for jazz harmony and voicings, [jazz-and-funk.md](jazz-and-funk.md).

## Brief

Settle these from the request, deciding what it leaves open and saying so:

- **Style and tempo.** From the sources named; take the tempo from the brief and a reference of the style:

  | Style | Tempo | Feel | Sound |
  |---|---|---|---|
  | Lo-fi, chillhop | downtempo, "poky" (Wikipedia, Lofi hip hop) | soft drums | piano or guitar melodies, vinyl hiss (Wikipedia); jazz roots; the worn sound below |
  | Boom bap | midtempo (Wikipedia, Boom bap) | swung sixteenths (Frane 2017); a hard kick and snare | gritty sampler drums (the SP-1200, the MPC), a looped or chopped sample |
  | Trap | about 140–160 BPM with the kick and snare at half that (Computer Music 2016); 100–176 occur (Wikipedia) | double- and triple-time hi-hats (Wikipedia) | an 808 bass, synthesized strings, brass, woodwinds and keys (Wikipedia) |

- **Loop or arc.**
  - A study or stream beat loops. Give it a `loop` ([game-music.md](game-music.md)) and keep its energy level.
  - A track for listening can have an intro, variations of the loop and an ending.
- **Room for a voice.** Say whether a rapper or singer will go over it. A beat for vocals keeps its melody short and out of the voice's register, as a comping piano stays below the lead's (Israels, in [anime-opening.md](anime-opening.md)).
- **Nothing sampled.** In sample-based hip-hop, producers build beats from short loops and drum breaks cut from older records (Schloss 2004). Here every note is written: compose the loop on instruments, then give it the sound described below. Do not imitate a recognisable record's sample.

## Groove

- **Swing on sixteenths.** Frane (2017) measured 30 classic drum breaks of hip-hop's breakbeat canon.
  - Most swung their sixteenths, but mildly: the median swing ratio was 1.2:1, the first sixteenth of each pair taking about 55% of the eighth.
  - Swing did not grow with tempo in that sample.
  - The snare was often late on beat 2, but generally not on beat 4.
- **Swing settings.** `performance.swing` `{"ratio": 0.54–0.62, "unit": 0.25}` on the drums and the parts that play sixteenths. Drum machines and DAWs give the same setting as a percentage (Attack Magazine; Linn 2013):
  - 50% is straight;
  - 54% loosens straight sixteenths without sounding like swing;
  - 58% and 62% are progressively looser;
  - 66% is a full triplet swing, and 71% leans toward dotted notes.
- **Swing needs notes on the off-sixteenths.** Frane also proposed swing density, the share of the even sixteenth positions that hold notes. A swing setting moves only the notes that are there, so a beat with few off-sixteenths sounds straighter at the same setting.
- **Parts against each other.** Swinging the hats while the keys stay straight, or the reverse, gives a push and pull between layers. Producers and musicians in hip-hop, electronic dance music and three other groove-based genres describe shaping timing and sound together: a hit's attack and weight change where it seems to fall (Danielsen et al. 2023). Judge the result with all the parts playing.
- **Behind the beat.** `performance.offset_ms` +10 to +30 on the snare or the keys lays them back against the kick and hats.
  - At slow tempos, jazz soloists played their downbeats after the drummer's ride cymbal while meeting it on the off-beats (Friberg and Sundström 2002).
  - The same delay in a beat reads as relaxed rather than late when it is consistent.
- **Velocity.** Accent the hats on the beat or the off-beat, and keep a few ghost snares well below the backbeat. `musiclib.expression` adds the small drift of a player.

## Lo-fi and chillhop

- **Drums.** An example plan: a soft kick, a snare or side-stick (37) on 2 and 4, and swung hats. Use the sampled `rusty` kit through the worn sound below, or `drum_synth` `"808"` with `decay` 0.6–0.8 for a softer machine.
- **Bass.** `bass_sneaky` (upright bass, finger and pluck layers, round robins, ghost notes) on roots and fifths with approach notes ([jazz-and-funk.md](jazz-and-funk.md)), or a Surge sub bass (`studio.py sounds --role bass --name sub --seed <piece seed>`; or the built-in `sub_bass`) for a synth bottom.
- **Harmony.** Lo-fi has jazz roots (Wikipedia, Lofi hip hop): seventh and extended chords, ii–V–I ([jazz-and-funk.md](jazz-and-funk.md)) and I–vi–ii–V, the doo-wop schema with ii for IV (Open Music Theory, Four-Chord Schemas).

  Voice them as a pianist would ([jazz-and-funk.md](jazz-and-funk.md)): rootless, in the middle register, with the bass taking the root.
- **Keys.**
  - The upright pianos of `vcsl_keys` (0:3, 1:3) for a worn piano.
  - For an electric piano: a Surge one (`studio.py sounds --role keys --name ep`, or `rhodes`, `wurli`, `suitcase`; with the piece's `--seed`), `fm_epiano`, or the TX81Z FM pianos (`vcsl_keys` 0:4, 1:4). Audition two to four on the part.
  - `lofi_keys` for a soft synth.
- **Guitar.** `guitar_shiny`, an archtop with four dynamics: pickup 0:26 for a warm jazz tone, microphone 0:25 for an acoustic one.
- **Lead.** `sax_bear`, a flute (`iowa_winds`), `vocal_ah` for a wordless voice, or the keys alone. Lo-fi beats are made to relax or study to (Winston and Saywood 2019): short phrases with long rests stay out of the way.

## Boom bap

The name imitates the kick ("boom") and the snare ("bap"). The style's drum loop puts a hard-hitting kick on the downbeats and a snappy snare on the backbeats, mixed up front, with the kick's low end emphasised; the rest is a looped or chopped sample (Wikipedia's boom-bap article and its sources).

- **Drums.**
  - The kick on 1 and 3, the snare hard on 2 and 4: the basic boom-bap loop (Wikipedia, Boom bap). Vary the kick from bar to bar, for example on the "and" of 2 or 3 or just before the downbeat, and keep the snare where it is.
  - Try the snare a little late on beat 2 (`timing_ms` +10 to +20), as in the breaks Frane measured, and judge by ear.
  - Hats in swung eighths or sixteenths, an open hat on the last off-beat of the bar, and ghost snares around the backbeat.
- **The sampler's sound.** The 12-bit, 26.04 kHz E-mu SP-1200 gave the style its gritty drums.
  - The `rusty` kit with `effects` `{"type": "bitcrush", "bits": 12, "downsample": 2}`.
  - `mix.saturate` 0.2–0.3 and a compressor on the drums.
  - The kick and snare loud against everything else.
- **The loop.** In sample-based production, a loop is cut from a record and repeated (Schloss 2004). Write the loop as if it were one:
  - one, two or four bars, its harmony from the brief (jazz voicings: [jazz-and-funk.md](jazz-and-funk.md));
  - on electric piano, a worn upright (`vcsl_keys` 0:3), strings (`vsco_strings`) or a horn section (`vsco` 0:61, stabs 0:62);
  - thin and dark like a sample under a bass line: `highpass` 150–250 Hz, `lowpass` 3–5 kHz, a little `wow_flutter`, and the vinyl below.
- **Chops.** A chopped loop plays pieces of the sample out of order as short stabs: a chord on 1, the "and" of 2 and 4, each cut off by a short `gate`, with the bass and kick holding the bar together.
- **Bass.** A short figure doubling the kick's rhythm, or the loop's own bass line.
  - `bass_darkblack` 0:33 with `lowpass` 1.5–2.5 kHz for an electric bass, or `bass_sneaky` for an upright.
  - A Surge sub bass (`studio.py sounds --role bass --name sub`) or a filtered `sub_bass` for a modern bottom.
- **Changes.** Change something at phrase edges ([development-and-groove.md](development-and-groove.md), Loops), for example every 4 or 8 bars:
  - drop the drums or the bass for a bar;
  - filter the loop down and open it again;
  - add a horn or string line for the hook.
- **No scratching.** The banks have no turntable recordings.

## Trap

- **The grid.** Most trap is produced at about 140–160 BPM, with the kick and snare programmed at half that tempo (Computer Music 2016); tempos from about 100 to 176 occur, 140 being typical (Wikipedia). The half-time snare falls on beat 3 of each bar, so written at 140 the track moves at 70, while hats and claps keep the full tempo.
- **Hi-hats.** Trap's hats run in double- and triple-time divisions (Wikipedia, Trap music):
  - eighths or sixteenths as the base;
  - rolls of sixteenth triplets or thirty-seconds before phrase ends, their velocities rising as a drummer's do toward a bar's end (Dow 2010).

  A closed hat that changes speed is the style's trademark: keep the base at quarters or eighths and shift to triplets or dotted notes near the end of a bar (Computer Music 2016). Vary the rolls every bar or two; the same roll in every bar sounds programmed.
- **The 808.** The TR-808's bass drum is a sine through a low-pass filter and an amplifier, with a decay control that lengthens it and low frequencies that sag a little in pitch as it rings (Wikipedia, Roland TR-808); trap tunes it with a long decay as the bass line (Wikipedia, Trap music) and UK drill slides it (Wikipedia, UK drill).
  - Where Surge XT is installed with its full patch set, play it on a Surge 808 patch measured to slide as written ([surge-roles.json](surge-roles.json): `a_liv/basses/bonsai_808`, `vospi/basses/808_builder_a`, with `surge.glide_ms` 80, the slide measured at 82 ms and the notes within 8 cents), and hear both on the part. The built-in `bass_808` (a long sine with a pitch punch on each attack, `mono`, `glide_ms` 60) is the fallback and the choice where a render must repeat exactly.
  - Write it mono and let notes overlap where it should slide: an overlapping note glides from the previous pitch instead of attacking again, on Surge with `glide_ms` and on the built-in synth alike; notes that do not overlap start at their own pitch. `blocks.slides(notes, share, seed)` holds a share of a line's notes into the next ([building-blocks.md](building-blocks.md)).
  - Follow the kick's rhythm, and keep the 808 and the kick from hitting different notes at once.
- **The 808's register.** Deruty (2024) analysed 808 bass-drum samples. Their median fundamental was 49.5 Hz, about G1.
  - Tuning one down a fourth, to D1 (37 Hz), cost about 6 dB through typical loudspeakers, and about as much again in the ear's sensitivity at moderate levels.
  - The sample's harmonics made up much of that loss.
  - So some producers move the song's key to suit the 808 rather than tune the 808 down.

  Keep the 808's tonic between about F1 and C2 (44–65 Hz, MIDI 29–36; G1 is MIDI 31, and 43 is already G2 at 98 Hz). In a key whose tonic falls lower, play the 808 an octave up or choose another key. `mix.saturate` 0.2–0.4 adds the harmonics that carry it on phone speakers. `analyze` shows a misplaced octave at once: an 808 an octave too high puts its energy at 100–160 Hz and leaves the 31 and 63 Hz octaves nearly empty.
- **Kick, snare, claps.**
  - The `drum_synth` `"808"` kick (36), short, or no separate kick where the 808 carries the downbeat.
  - The snare (38 or 40) and a bright clap (39) layered on beat 3, with extra hits as fills. A second, thicker clap on 2 and 4 can mark the full tempo against the half-time snare (Computer Music 2016).
  - Trap producers also pitch repeated snares up or down into a roll; `drum_synth` tunes only the whole kit, so do that with the snare's velocity and density instead.
  - A rim (37) or percussion as a counter-rhythm.
- **Melody and colour.** Trap uses synthesized strings, brass, woodwinds and keyboards for a cinematic sound (Wikipedia, Trap music):
  - bells (`studio.py sounds --name bell`; the built-in `fm_bell` is brighter than most), plucks, dark pads (`sounds --role pad --character dark`, or `warm_pad`), a flute (`vsco` 0:73) or `vocal_ah`, and orchestral brass, strings and woodwinds.
- **Arrangement**, an example plan:
  - an intro of 4–8 bars: the melody alone, filtered;
  - the drums and the 808 entering together;
  - before a new section, drop the 808 or the drums for half a bar, with a `reverse_cymbal` or a riser into it.

## The worn sound

Lo-fi hip-hop is distributed almost entirely online and plays with nostalgia for older media (Winston and Saywood 2019). Its sound of worn tape and vinyl is added on purpose, part by part; boom bap takes the grit and the vinyl from it.

- **Muffled highs.** `mix.lowpass` at 2.5–5 kHz on keys and drums (12 dB per octave). For a steeper cut with a little resonance, `mix.filter_sweep` with a single point is a fixed filter: `{"type": "lowpass", "points": [[0, 3500]], "resonance": 0.2}`.
- **Tape wobble.** `mix.wow_flutter` `{"wow_cents": 6–15, "wow_hz": 0.4–1}` on the keys or guitar, or 3–6 cents on the whole mix (project `mix.wow_flutter`).
- **Vinyl.** A `noise` part with one `vinyl` note across the track, `level_mode: "peak"`, `level_dbfs` about −26.
- **Grit.** `effects` bitcrush (12 bits, `downsample` 2) and `mix.saturate` 0.2–0.3 on the drums.
- **Ducking.** A light `mix.duck` (3–5 dB) of the keys by the kick makes the loop breathe.
- **Loudness.** Lo-fi stays soft and warm: `target_lufs` −14, `dynamics: "glue"`, a modest `reverb_db` on keys and snare. Boom bap and trap use the same chain, with less reverb and the drums and bass further forward.

## Symptoms and causes

| Symptom | Likely causes | What to check or change |
|---|---|---|
| Stiff | straight sixteenths; constant velocities | `performance.swing`, accents and ghost notes, `musiclib.expression` |
| Swing that is not heard | no notes on the off-sixteenths | hats or ghost notes on them, or a higher setting |
| Sloppy rather than relaxed | swing or offsets that differ bar to bar; too much random drift | one swing per part, a consistent `offset_ms` |
| Muddy | keys and bass overlap below 200 Hz; too much reverb | `mix.highpass` on the keys, the bass alone below |
| Too clean for lo-fi or boom bap | no wobble, no noise, full highs; drums without grit | `wow_flutter`, `vinyl`, a fixed low-pass; bitcrush and saturation on the drums |
| Boom bap without punch | the loop as loud as the drums; a soft kick and snare | the loop thinner and lower; the kick and snare up and compressed |
| Programmed-sounding hats | the same roll every bar; flat velocities | rolls that vary; ramps through each roll |
| The 808 vanishes on small speakers, or booms | a pure sine below about F1; no saturation; the kick on top of it | the 808 higher, or another key; `mix.saturate`; the kick shorter |
| Boring on repeat | the loop never changes | drop a part for a bar or two, a fill every 4 or 8 bars, a variation of the top line |

## Sources

- Schloss, J. G. (2004). *Making Beats: The Art of Sample-Based Hip-Hop*. Wesleyan University Press.
- Frane, A. V. (2017). [Swing rhythm in classic drum breaks from hip-hop's breakbeat canon](https://doi.org/10.1525/mp.2017.34.3.291). *Music Perception* 34(3), 291–302.
- Computer Music (2016). [10 tricks every trap producer should know](https://www.musicradar.com/tuition/tech/10-tricks-every-trap-producer-should-know-638684). *MusicRadar*: tempo and the half-time snare, hi-hat rate changes, layered claps, 808 harmonics.
- Wikipedia, read 6 November 2026: [Boom bap](https://en.wikipedia.org/wiki/Boom_bap) (the kick-snare loop, swing, samplers) and [Trap music](https://en.wikipedia.org/wiki/Trap_music) (tempo range, the 808, orchestration), with the sources they cite.
- Linn, R. (2013). [Roger Linn on swing, groove and the magic of the MPC's timing](https://www.attackmagazine.com/features/interview/roger-linn-swing-groove-magic-mpc-timing/). Interview, *Attack Magazine*.
- Attack Magazine. [Swing in DAWs and drum machines](https://www.attackmagazine.com/technique/passing-notes/daw-drum-machine-swing/), on the MPC-style swing percentages.
- Deruty, E. (2024). [Harmonic and transposition constraints arising from the use of the Roland TR-808 bass drum](https://arxiv.org/abs/2502.07524). *Proceedings of the 25th International Society for Music Information Retrieval Conference*, San Francisco.
- Winston, E. and Saywood, L. (2019). [Beats to Relax/Study To: Contradiction and Paradox in Lofi Hip Hop](https://iaspmjournal.net/index.php/IASPM_Journal/article/view/949). *IASPM Journal* 9(2), 40–54.
- Dow, R. (2010). [Programming Realistic Drum Parts](https://www.soundonsound.com/techniques/programming-realistic-drum-parts). *Sound On Sound*, September 2010.
- Hughes, B. and Lavengood, M. [Four-Chord Schemas](https://viva.pressbooks.pub/openmusictheory/chapter/4-chord-schemas/). In Gotham, M. et al., *Open Music Theory*, version 2.
- [Lofi hip hop](https://en.wikipedia.org/wiki/Lo-fi_hip_hop). Wikipedia, read 7 November 2026: downtempo, piano or guitar melodies, vinyl hiss, jazz roots.
- Danielsen, A., Johansson, M., Brøvig, R., Sandvik, B. and Bøhler, K. K. (2023). [Shaping rhythm: timing and sound in five groove-based genres](https://doi.org/10.1017/S0261143023000041). *Popular Music* 42(1).
- Friberg, A. and Sundström, A. (2002). Swing ratios and ensemble timing in jazz performance: evidence for a common rhythmic pattern. *Music Perception* 19(3), 333–349.
- [E-mu SP-1200](https://en.wikipedia.org/wiki/E-mu_SP-1200). Wikipedia, on its 12-bit, 26.04 kHz sampling.
- Wikipedia, read 9 November 2026: [Roland TR-808](https://en.wikipedia.org/wiki/Roland_TR-808) (the bass drum's circuit and decay) and [UK drill](https://en.wikipedia.org/wiki/UK_drill) (the sliding 808).
