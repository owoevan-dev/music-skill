# Game music: loops, layers and scenes

Read this when the music is for a game: a loop for a place or a state, a battle, a menu, a jingle. Game music is heard while the player does something else, it is heard many times, and it meets other music at seams. Those three facts change the brief, the form and the delivery.

What a cue sounds like, by style, is in the style maps ([style-maps.md](style-maps.md)), chiptune in [style-map-electronic.md](style-map-electronic.md), the form and harmony of a town, an overworld, a dungeon and a battle in [style-map-game.md](style-map-game.md); a mood's cues across styles in [moods.md](moods.md).

Contents: [Brief](#brief) · [The loop point](#the-loop-point) · [Repetition](#repetition) · [Mood and scene](#mood-and-scene) · [Layers](#layers) · [Stingers, transitions and endings](#stingers-transitions-and-endings) · [Delivery](#delivery) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

## Brief

Settle these from the request, deciding what it leaves open and saying so:

- **Use**: a background loop, a one-shot (a victory or level-up jingle, a stinger, game over), or layers the game mixes. A one-shot has no `loop`: it ends with a cadence and a natural decay, and `tail_quiet` applies.
- **Time spent**: how long a player stays in the place. A 30-second shop visit and an hour in a dungeon need different loop lengths and different amounts of variation.
- **Loop start**: from bar 1, or an intro that plays once and then a loop from a later bar (`loop.start_bar`).
- **Engine and format**, if known (see Delivery).
- **Loudness**: `target_lufs` −14 suits a soundtrack file. In a game the developer sets each asset's level, and platform guidance measures the whole game's output: Sony's audio standards group recommended an average of −23 LUFS for PS3 and −18 for PS Vita, ±2 LU. Use a target the person names (down to −30); otherwise deliver at −14 and say that the in-game level is set in the engine.

## The loop point

`loop` in the project ([schema.md](schema.md)) makes the render deliver a loop. The jump from the end of the last bar back to the loop start is a seam between two pieces of music, and Medina-Gray (2019) describes how smooth such a seam is in five aspects, comparing the second after it with the five seconds before it. Write each one on purpose:

- **Meter**: the same tempo on both sides of the seam: no ritardando, fermata or final cadence in the last bar. The schema puts the loop point on a bar line.
- **Pitch**: the pitch classes of the first second after the seam should already sound in the five seconds before it. That is smoothest when all of them do, still fairly smooth when at least half do, and disjunct when none do. End on a harmony that leads into the first bar: the dominant into the tonic, or the opening chord itself.
- **Timbre**: the same instruments carry on across the seam unless a change is meant. A drum fill that restarts the groove is meant; a pad that stops dead at the seam usually is not.
- **Volume**: keep the level across the seam. Do not fade or thin the end to nothing unless the start builds back from it.
- **Abruptness**: a note still sounding at the end is released at the seam, and its decay plus the reverb are folded into the loop start of `loop.wav`, so the jump continues the sound instead of cutting it. Write the first bar as the continuation of the last.

`review` asks about tempo changes, pitch classes that are new after the seam, and parts entering or leaving at it. The render reports all five aspects in `report.json` under `loop.seam`. Read them one at a time, as Medina-Gray does; she deliberately does not add them into a single score.

**The first play** differs from the repeats.
- With a loop from bar 1, the first play also hears the folded tail at the very start. `loop.seam.abruptness.tail_below_own_db` says how far below the opening's own music it sits.
- With an intro, the intro's own reverb is in the file at the loop start, so every repeat hears it there too. On the first play, the folded tail of the loop end is also there. If either matters, end the intro dry and short.

A fade-in on the first play is the engine's job. The file cannot have one, because its first frames replay on every loop.

## Repetition

Players hear a loop many times. In interviews, players tolerated repetition but could grow overfamiliar with music that repeats, which affected their enjoyment, while familiarity also helped them read the game (Dutta 2020). Worrall (2025) treats excessive repetition as a documented cause of fatigue, lower enjoyment and weaker immersion. In his study inside a role-playing game, players noticed expressive performance variation less than in plain listening, yet it still changed how they rated the repetition, the performance and the composition.

- Build contrast into the loop (A, B, then A with new orchestration or a countermelody) rather than repeating one phrase.
- Make the loop longer for places where players stay long. When file size allows, write the material twice inside one loop, with a different voicing or accompaniment the second time.
- Keep `musiclib.expression` on, and give a repeated passage its own timing and dynamics rather than copying the first one's performance.
- A background loop sits under play, dialogue and sound effects. Keep its lead clear but not insistent, and its texture lighter than a soundtrack cue's.

## Mood and scene

Eerola, Friberg and Bresin (2013) varied six cues in a factorial design and asked listeners which character they heard. The cues ranked mode, then tempo, register, dynamics, articulation and timbre, and they combined additively, with no meaningful interactions. Mode mattered most for happy against sad and little for peaceful or scary. Dynamics mattered for peaceful and scary and little for happy or sad. The melody was played on a flute, a horn or a trumpet, from darkest to brightest: the darker sound raised the peaceful ratings almost as much as tempo or dynamics did, and the sad ratings a little, the brighter one raised the scary ratings a little, and happiness did not depend on it. Their tempo was the number of distinct onsets per second in all voices together, from 1.2 to 6, about the medians that musicians chose for these emotions in a production study (Bresin and Friberg 2011, as reported there); faster raised the happy ratings and lowered the sad and peaceful ones. Their passages were a melody over a piano accompaniment. `profile` reports the same count per section (`onsets_per_second`, the pitched parts together).

| Character | Cue levels that conveyed it |
|---|---|
| Happy | major, fast, high register, staccato |
| Sad | roughly the reverse of happy (minor, slow, legato), plus softer dynamics and a darker timbre |
| Peaceful | slow, soft, legato, high register, a darker timbre |
| Scary | minor, low register, loud, a brighter timbre |

A scene's music starts from the character it should convey, which the brief decides; the cue levels follow from the table above. In the table below, the character beside each scene is this skill's starting point, which no source read gives; the cue levels are Eerola et al.'s for that character. Choose the instruments for each part's job ([sound-selection.md](sound-selection.md)) and for the character ([scene-music.md](scene-music.md), Instruments and a scene's character).

| Scene | Character | Cue levels |
|---|---|---|
| Town, village, shop | happy or peaceful | major and a high register; faster with staccato for happy, slow, soft and legato for peaceful |
| Field, overworld | happy | major, fast, high register, staccato |
| Dungeon, cave | scary | minor, low register; loud for a threat |
| Battle, boss | scary | minor, low register, loud |
| Sad scene | sad | minor, slow, legato, soft, a darker timbre |
| Victory, level-up | happy | major, fast, high register; a one-shot ending on an authentic cadence |

The orchestral instruments are in the `vsco`, `vsco_extra` and `vcsl` banks ([soundbanks.md](soundbanks.md)); [orchestration.md](orchestration.md) covers writing for them. Music under the text and voices of a visual novel or an RPG scene has its own needs: see [scene-music.md](scene-music.md).

A pixel-art game does not have to sound like an old console; ask or decide. For chip-like voices, the `additive` engine with `odd_only: true` makes odd harmonics only: `spectral_tilt` 1 approaches a square wave and 2 a triangle.

## Layers

The game can fade layers of one piece in and out (vertical layering), for example to raise intensity as a fight heats up. Each layer is then heard alone and together with every other.
- Share tempo, length, key and loop points across the layers.
- Keep each layer consonant with the others. In a simultaneous seam, Medina-Gray hears consonance as agreement and dissonance as disjunction.
- Keep the layers' dynamics close, and each instrument in a stable range (Crowley 2015).
- Give the base layer the harmony and the pulse, so it stands alone. Then add layers that each bring something new: percussion, a countermelody, the lead, brass.
- Check the thinnest combination the game will play, usually the base alone, as well as the full mix.

`loop.layers` in the project ([schema.md](schema.md)) assigns every part to one layer. The render then writes `layers/<id>.wav` and `.ogg` next to the loop files:
- each layer is mixed alone through the same buses and reverbs;
- it gets the master's gain and EQ but not its compressor and limiters;
- it is delayed by the limiters' look-ahead (about 10 ms, measured on each render), so it lines up with `loop.wav`;
- it is folded at the loop point like the full loop.

All layers share one gain, so their balance stays as mixed. Played together they add up to the mix before the master's dynamics, a little louder than `loop.wav` (`loop.layers.sum_minus_loop_db` in the report): give the game's music bus a limiter. They get the mix's `mono_below_hz` and `wow_flutter` as the mix does. A bus compresses or saturates the sum of its parts, which no split into layers can add back up to (every bus but `fx`), so `validate` refuses parts of one such bus in different layers: keep them in one layer, give some another bus (`mix.bus`), or set `mix.dynamics` to `"wide"`, which leaves the buses linear.

`stems/` still holds every part processed before the buses, without its reverb, for a developer who builds the mix in the engine.

## Stingers, transitions and endings

- **A stinger** is a short one-shot played over the loop: an item found, a warning, a door. Write it in the loop's key and tempo, on a chord that fits wherever it may land (the tonic chord, or a figure without a third), and out of the melody's register. Let it end on a natural decay. Deliver it as its own project without `loop`. The engine starts it on the loop's next beat or bar.
- **An ending** follows the loop at a bar line: two to four bars in the same tempo and key, starting on a downbeat that works after any bar of the loop (or after the last bar, if the engine waits for the loop end), and closing on a cadence. Deliver it as its own project, and have the engine start it at the next bar line.
- **A switch between pieces** (exploration to battle) is a seam between modules, judged like a loop point: meter, timbre, pitch, volume and abruptness. A shared tempo, a shared key or the dominant of the next piece, and a bar-line switch make it smooth.
- **Sections as segments.** The loop files carry a cue point at every section start, labelled with the section id. An engine can jump between them on a bar line (horizontal resequencing).

## Delivery

A render with `loop` writes these files next to the master:

| File | What it is |
|---|---|
| `loop.wav` | 24-bit, with one forward loop in a `smpl` chunk. Its end frame is played, as the RIFF definition requires. Godot's importer reads WAV loop points in its default "Detect From WAV" mode. A cue point with a `labl` entry marks every section start; Wwise reads WAV markers. |
| `loop.ogg` | Vorbis, with `LOOPSTART` and `LOOPLENGTH` comments in samples, the convention RPG Maker reads. RPG Maker VX Ace jumps back when the length is reached; MV plays the whole file once and then follows the tags. Both behave the same here, because the file ends at the loop end. It needs FFmpeg's `libvorbis` encoder, which Homebrew's `ffmpeg` lacks, so on macOS install `ffmpeg-full` ([setup.md](setup.md)). Without it the render writes the WAV and notes the Ogg copy as skipped. |
| `loop.json` | Loop start and end in samples at 48 kHz, in seconds and in bars; the section starts; and, when the tempo is constant, `bpm`, `bar_beats` and `beat_count`, the three values Godot's `AudioStreamInteractive` needs on each clip to switch on a beat or a bar. |
| `layers/<id>.wav`, `.ogg` | With `loop.layers`: every layer as a loop, as above. In Godot, put them in an `AudioStreamSynchronized`, which starts its streams at exactly the same time and sets each one's volume. In Unity, start one `AudioSource` per layer with `PlayScheduled` at the same DSP time; Unity loops whole clips, so loop from bar 1 there or play the intro as its own clip. |
| `preview.mp3` | For listening only. MP3 stores 1152-sample frames and adds encoder delay and padding (576 samples for LAME), so it gaps at a loop unless the player trims those from the LAME tag. |

`report.json` adds these checks:
- `loop_length_exact`;
- `loop_points_in_wav`;
- `loop_true_peak_ceiling`: the tail can add to a peak near the start, and the whole loop comes down if it would pass the master's ceiling (−1 dBTP, or −2 above −14 LUFS: [performance-and-mix.md](performance-and-mix.md));
- `loop_ogg_length_exact`: the decoded Ogg has as many frames as the WAV;
- `loop_ogg_tags`;
- `loop_cues_in_wav`: the section cue points read back as written;
- with layers, the same checks for every layer (`layer_lengths_exact`, `layer_points_in_wav`, `layer_true_peak_ceiling`, `layer_cues_in_wav`, `layer_ogg_lengths_exact`, `layer_ogg_tags`).

In the reply, give:
- the loop points in seconds and samples;
- which file suits which engine;
- whether anyone has listened across the seam. If nobody has, say so plainly.

## Sources

- Medina-Gray, E. (2019). [Analyzing Modular Smoothness in Video Game Music](https://www.mtosmt.org/issues/mto.19.25.3/mto.19.25.3.medina.gray.html). *Music Theory Online* 25(3). doi:10.30535/mto.25.3.2
- Eerola, T., Friberg, A. and Bresin, R. (2013). [Emotional expression in music: contribution, linearity, and additivity of primary musical cues](https://pmc.ncbi.nlm.nih.gov/articles/PMC3726864/). *Frontiers in Psychology* 4:487. doi:10.3389/fpsyg.2013.00487
- Worrall, K. (2025). [Expressive Performance Rendering for Reduced Music Repetition in Video Games](https://etheses.whiterose.ac.uk/id/eprint/38684/). PhD thesis, University of York.
- Dutta, V. (2020). [The Repetition of Video Game Music, its Impact on Video Game Enjoyment, and How Best to Manage it](https://eprints.hud.ac.uk/id/eprint/35234/). PhD thesis, University of Huddersfield.
- Crowley, D. (2015). [Composing Adaptive Music for Games: Advanced Concepts in Elias](https://www.gamedeveloper.com/audio/composing-adaptive-music-for-games-advanced-concepts-in-elias). Game Developer.
- Taylor, G. (2012). [Video Games and Loudness Standards](https://designingsound.org/2012/07/30/video-games-and-loudness-standards-interview-with-sonys-garry-taylor/), interview. Designing Sound.
- Godot Engine. [ResourceImporterWAV](https://docs.godotengine.org/en/stable/classes/class_resourceimporterwav.html), `edit/loop_mode`; [AudioStreamSynchronized](https://docs.godotengine.org/en/stable/classes/class_audiostreamsynchronized.html); [AudioStreamInteractive](https://docs.godotengine.org/en/stable/classes/class_audiostreaminteractive.html).
- Unity. [AudioSource.PlayScheduled](https://docs.unity3d.com/ScriptReference/AudioSource.PlayScheduled.html).
- Audiokinetic community Q&A. [Detecting the end of a stinger with a WAV marker](https://www.audiokinetic.com/qa/9331/how-do-i-detect-the-end-of-a-stinger-started-by-a-stinger).
- EasyRPG Player. [Pull request 2618](https://github.com/EasyRPG/Player/pull/2618): LOOPSTART and LOOPLENGTH in Ogg, RPG Maker VX Ace and MV behaviour.
- un4seen. [TAG_SMPL_LOOP](https://www.un4seen.com/doc/#bass/TAG_SMPL_LOOP.html): the RIFF `smpl` loop structure.
- CompuPhase. [Gapless looping MP3 tracks](https://compuphase.com/mp3/mp3loops.htm).
