# Scene music: visual novels and RPG scenes

Read this when the music sits under scenes the player reads or watches: a visual novel, the dialogue and events of an RPG, a cutscene. Three things set this music apart. It shares the player's attention with text and voices. It comes back every time its kind of scene comes back. And the script, not the music, decides when a scene ends. Loops, layers, seams and file delivery are in [game-music.md](game-music.md); this guide covers what the scene adds.

Contents: [Brief](#brief) · [Under text and voices](#under-text-and-voices) · [A set of cues and their themes](#a-set-of-cues-and-their-themes) · [Scene starting points](#scene-starting-points) · [Instruments and a scene's character](#instruments-and-a-scenes-character) · [Form for a scene cue](#form-for-a-scene-cue) · [Delivery in a visual novel engine](#delivery-in-a-visual-novel-engine) · [Instruments for scene music](#instruments-for-scene-music) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

## Brief

Settle these from the request, deciding what it leaves open and saying so:

- **The set.** A soundtrack of this kind is a set of cues, each tied to a kind of scene (daily life, comedy, tension, sadness, romance, mystery, a climax, a memory) or to a character or place. Name the cue being written and where it sits in the set.
- **Text or voice.** Lines read silently need a quiet, steady bed. Voiced lines need more room (below).
- **Time in the scene.** The reader sets the pace, so one scene of text can last from one minute to ten. The cue loops for as long as the scene lasts.
- **Themes.** Whether the cue quotes the main theme or a character's motif, and in what guise.
- **Engine.** Ren'Py, RPG Maker, Godot or Unity decides the files and the loop syntax (Delivery).

## Under text and voices

On average, background music slightly impairs reading and memory, although its overall effect across all outcomes is close to null (Kämpfe, Sedlmeier and Renkewitz 2011, a meta-analysis). The tempo and the level matter. Thompson, Schellenberg and Letnic (2012) found that reading comprehension suffered when background instrumental music was both fast and loud, and not when it was slow, soft, or only one of the two. For a cue under reading, then:

- **Tempo and level.** Keep the tempo moderate and the dynamics soft. Express the scene through harmony, register and timbre rather than through busy rhythm.
- **Texture.** Keep it steady. A new entry, an accent or a sudden stop pulls the ear away from the sentence being read.
- **Peaks.** Keep big moments out of the loop. A loop that peaks every 90 seconds peaks under whatever line happens to be on screen.

Voiced lines need the music further down:

- **Level.** Torcoli et al. (2019) studied the ducking of music under commentary on television. They recommend that commentary sit at least 10 LU above music and 15 LU above ambience, and non-experts preferred about 4 LU more than experts. WCAG 2.2 success criterion 1.4.7 (level AAA) is written for recorded audio that is mainly speech: it asks for no background sound, or a way to turn it off, or background sound at least 20 dB under the speech. It is not a rule for games; it gives a figure for a voiced scene.
- **Ren'Py's ducking.** Ren'Py's "emphasize audio" preference is off by default (`default preferences.emphasize_audio = True` turns it on). It lowers the channels other than `voice` while a voice line plays, to 0.8 of their volume over 0.5 s. Ren'Py volumes are amplitudes, so 0.8 is only about −2 dB. For voiced scenes, set `config.emphasize_audio_volume` near 0.3 (about −10 dB), or mix the cue itself to sit low.
- **Spectrum.** Speech intelligibility rests mostly on the 1–4 kHz octaves: in the band-importance weights of ANSI S3.5-1997 they carry about 70% of the total. Under dialogue, keep a bright lead out of that region or keep it soft. A low piano, a cello, a dark pad or harp arpeggios leave more room for a voice than a violin or a flute melody in the same octave as the speech's presence.

Whether a level works is decided in the game, with the engine's own volume settings and with voices playing. Say which level the cue was mastered to and what the engine should do.

## A set of cues and their themes

A leitmotif is a short theme tied to a character, a place or an idea, which comes back and changes with the story. Summers (2014) traces how games use music in Wagnerian ways, the leitmotif among them, and RPG soundtracks commonly give characters and places their own themes. Recurrence builds the association; transformation shows what has changed, as when a hero's theme returns in minor after a loss.

To transform a theme, keep what makes it recognizable, its contour and rhythm, and change the cues that carry character. Eerola, Friberg and Bresin (2013) found these cues (mode, tempo, register, dynamics, articulation, timbre) to act additively on perceived emotion ([game-music.md](game-music.md)). One motif can therefore serve:

- the daily-life cue, in major, with light staccato;
- the sad cue, slowed, in minor, legato and soft;
- the tension cue, as a fragment in a low register;
- the climax, in full orchestration.

Write the main theme first, then derive the set from it. Keeping the set in related keys and shared tempos makes the switches between cues smoother (the switch rule in [game-music.md](game-music.md)).

## Scene starting points

Each row maps a scene to the character it conveys and that character's cue levels (Eerola, Friberg and Bresin 2013, in [game-music.md](game-music.md)); the brief overrides any of them. Under text, keep the cue soft and steady (the cue levels above). Tension, horror and emotional climaxes are written in more depth in [film-score.md](film-score.md); choose the instruments for each part's job ([sound-selection.md](sound-selection.md)) and for the character (below).

| Scene | Character | Cue levels, or where it is written |
|---|---|---|
| Daily life, school, home | happy or peaceful | major and a high register; soft and steady under text |
| Comedy | happy | major, fast, high register, staccato |
| Tender, romance | peaceful | slow, soft, legato, high register, a darker timbre |
| Sad, loss | sad | minor, slow, legato, soft, a darker timbre |
| Tension, suspense, horror | scary | minor, low register, loud at its peaks, a brighter timbre; [film-score.md](film-score.md) |
| Memory, flashback | the main theme recalled | the theme with its cue levels changed (A set of cues, above) |
| Climax, confession | the high point | [climax-and-melody.md](climax-and-melody.md) |
| Ending, credits | the main theme | ending on an authentic cadence ([climax-and-melody.md](climax-and-melody.md)) |

## Instruments and a scene's character

The instrument alone changes the emotion heard. Hailstone et al. (2009) recorded melodies written to sound happy, sad, fearful or angry on a synthesizer, a piano, a violin and a trumpet, at the same tempo and loudness, and the instrument changed which emotion listeners chose. What is known about which sounds suit which character:

- **Darker or brighter.** In Eerola, Friberg and Bresin (2013), a darker melody instrument made a passage more peaceful, nearly as strongly as a slower tempo or softer dynamics, and a little sadder; a brighter one made it a little scarier, and happiness did not depend on it ([game-music.md](game-music.md)). Brightness there was the energy below 1.5 kHz, which also followed how positive listeners rated 110 isolated instrument sounds (Eerola, Ferrer and Alluri 2012, as reported in the 2013 paper).
- **Sad.** Musicians judged the relative sadness of 44 familiar Western instruments, and another group rated the instruments' acoustic properties. The properties that make speech sound sad predicted the judgements, best of all the ability to make small pitch movements; the others studied were a dark timbre, low notes, playing quietly and the capacity to "mumble" (Huron, Anderson and Shanahan 2014). For a sad cue, choose an instrument that can glide, bend and play low and softly: a bowed string, the erhu, a lead with legato and bends (`performance.legato`, `performance.bend`).
- **Happy and comic.** An instrument limited to short, bright, high notes cannot imitate those cues. In recital repertoire, 6% of the xylophone pieces surveyed were in minor against 60% of the marimba pieces that are tonal, and the minor-key xylophone pieces were usually played on the marimba (Schutz et al. 2008). Keep the xylophone for the happy and comic cues (major, fast, high, staccato) and give a sad cue to an instrument that can sustain.
- **Hear the candidates.** Since the instrument changes the emotion, play the cue's melody on two or three sounds before choosing (`studio.py audition`, [sound-selection.md](sound-selection.md)).

## Form for a scene cue

- **Loop.** A scene cue loops, because the reader sets the pace. For a scene of a few minutes, make the loop 60–120 s, with an A section and a contrasting B inside it (the repetition advice in [game-music.md](game-music.md)).
- **Shape.** Keep the dynamic curve gentle across the loop, and save climaxes for cues written to a timed event.
- **Start.** An intro that plays once and then a loop from a later bar (`loop.start_bar`) suits a cue that starts a scene. A loop from bar 1 suits a cue the script may restart, and layered cues.
- **Timed events.** Cues timed to picture fit auto-advancing cutscenes. In a visual novel, an event usually gets a stinger over the loop or a switch to another cue.

## Delivery in a visual novel engine

- **Ren'Py** plays Ogg Vorbis and Opus. For a cue with an intro, play `loop.ogg` with its loop start in seconds from `loop.json`:
  `play music "<loop 12.0>audio/scene.ogg" fadein 1.0`.
  Ren'Py plays the whole file once, then loops from that point. A fade between cues is `play music "audio/next.ogg" fadeout 1.5 fadein 1.5`. A switch at a bar line needs code of your own, because the play statement fades at once.
- **Ren'Py, layered cues.** Register a second channel with `renpy.music.register_channel`, then start each layer synced to the first:
  `play music_2 [ "<sync music>audio/layers/lead.ogg", "audio/layers/lead.ogg" ]`.
  Later repeats play the layer file from its start, so loop layered cues from bar 1.
- **RPG Maker** reads the `LOOPSTART` and `LOOPLENGTH` tags in `loop.ogg`; **Godot** and **Unity** are covered in [game-music.md](game-music.md).

## Instruments for scene music

- **Piano.** The Steinway (`vcsl` 0:0) for every piano part ([piano-and-chamber.md](piano-and-chamber.md)). For legato, ringing writing, hold the pedal and change it at each harmony with CC64 in `performance.cc` (`[beat, 64, 0]`, then `[beat + 0.05, 64, 127]`); leave it up for dry, detached figures. `piano_osiris` has a preset recorded with the pedal held (1:0), where the whole instrument rings with every note: only for slow, sparse music built on that haze.
- **Solo cello.** `cello_bigcat` sustains loop for as long as a note is held. A gentle vibrato starts after 0.35 s, and CC1 deepens it.
- **Organ.** `organ_vcsl` does not respond to velocity, like a pipe organ. Shape its dynamics with CC11, as with a swell pedal, or by changing registration; [organ.md](organ.md) covers writing for it and the church it sounds in.
- **Orchestra.** Strings, woodwinds, brass, harp and timpani come from `vsco`, `vsco_extra` and `vcsl`; [orchestration.md](orchestration.md) covers balance and the wide master.

## Sources

- Kämpfe, J., Sedlmeier, P. and Renkewitz, F. (2011). [The impact of background music on adult listeners: A meta-analysis](https://journals.sagepub.com/doi/10.1177/0305735610376261). *Psychology of Music* 39(4), 424–448. doi:10.1177/0305735610376261
- Thompson, W. F., Schellenberg, E. G. and Letnic, A. K. (2012). Fast and loud background music disrupts reading comprehension. *Psychology of Music* 40(6), 700–708. doi:10.1177/0305735611400173
- Torcoli, M., Freke-Morin, A., Paulus, J., Simon, C. and Shirley, B. (2019). [Preferred Levels for Background Ducking to Produce Esthetically Pleasing Audio for TV with Clear Speech](https://cris.fau.de/publications/234640600). *Journal of the Audio Engineering Society* 67(12), 1003–1011. doi:10.17743/jaes.2019.0052
- W3C (2023). [Understanding Success Criterion 1.4.7: Low or No Background Audio](https://www.w3.org/WAI/WCAG22/Understanding/low-or-no-background-audio). WCAG 2.2.
- ANSI S3.5-1997. Methods for Calculation of the Speech Intelligibility Index. Octave-band importance as tabulated in the [R `SII` package](https://rdrr.io/cran/SII/man/sii.html).
- Summers, T. (2014). [From Parsifal to the PlayStation: Wagner and Video Game Music](https://pure.royalholloway.ac.uk/en/publications/from-parsifal-to-the-playstation-wagner-and-video-game-music). In K. J. Donnelly, W. Gibbons and N. Lerner (eds.), *Music in Video Games: Studying Play*, 199–216. Routledge.
- Eerola, T., Friberg, A. and Bresin, R. (2013). [Emotional expression in music: contribution, linearity, and additivity of primary musical cues](https://pmc.ncbi.nlm.nih.gov/articles/PMC3726864/). *Frontiers in Psychology* 4:487.
- Eerola, T., Ferrer, R. and Alluri, V. (2012). Timbre and affect dimensions: evidence from affect and similarity ratings and acoustic correlates of isolated instrument sounds. *Music Perception* 30(1), 49–70. doi:10.1525/mp.2012.30.1.49
- Hailstone, J. C., Omar, R., Henley, S. M. D., Frost, C., Kenward, M. G. and Warren, J. D. (2009). It's not what you play, it's how you play it: timbre affects perception of emotion in music. *Quarterly Journal of Experimental Psychology* 62(11), 2141–2155. doi:10.1080/17470210902765957
- Huron, D., Anderson, N. and Shanahan, D. (2014). "You can't play a sad song on the banjo": acoustic factors in the judgment of instrument capacity to convey sadness. *Empirical Musicology Review* 9(1), 29–41. doi:10.18061/emr.v9i1.4085
- Schutz, M., Huron, D., Keeton, K. and Loewer, G. (2008). [The happy xylophone: acoustics affordances restrict an emotional palate](https://doi.org/10.18061/1811/34103). *Empirical Musicology Review* 3(3), 126–135.
- Ren'Py. [Audio](https://www.renpy.org/doc/html/audio.html): partial playback and sync; [Configuration variables](https://www.renpy.org/doc/html/config.html): `config.emphasize_audio_channels`, `config.emphasize_audio_volume`, `config.emphasize_audio_time`.
