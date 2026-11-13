# Film score: emotional underscore, scoring to picture, suspense and horror

Read this when the music serves a picture or a story moment:
- an emotional cue for piano and strings;
- underscore for a film, a video or a cutscene;
- music timed to events on screen;
- a tension, suspense or horror cue.

Cinematic orchestral writing and the approaches of horror and suspense, each on the seven axes with its sources, are in [style-map-orchestral.md](style-map-orchestral.md) and [style-map-horror.md](style-map-horror.md).

Contents: [Brief](#brief) · [Emotional underscore](#emotional-underscore) · [Scoring to picture](#scoring-to-picture) · [Suspense and horror](#suspense-and-horror) · [Symptoms and causes](#symptoms-and-causes) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

Related guides:
- [orchestration.md](orchestration.md): the orchestra on the banks, balance, and the wide master;
- [climax-and-melody.md](climax-and-melody.md): planning a high point;
- [scene-music.md](scene-music.md): loops under text in a visual novel or an RPG.

This guide covers what film and media writing adds.

## Brief

Settle these from the request, deciding what it leaves open and saying so:

- **Picture or not.** A cue timed to picture needs the times of its events (hit points) in seconds. A free-standing cue only needs a length.
- **Function.** Is it emotional underscore, tension, action, a horror cue or a stinger? Is the cue one-shot or looping?
- **Dialogue.** Whether lines, narration or voices play over it. They change the register and density rules below.
- **Ending.**
  - A **button**: a short final chord, on the cut.
  - A **ring-out**.
  - A **fade**, left to the editor.
  - A **segue** into the next cue.

## Emotional underscore

**One theme, transformed.** A cue carries one theme and changes its surface:
- mode, tempo, register, dynamics, articulation and timbre, which act on perceived emotion additively (Eerola, Friberg and Bresin 2013; [scene-music.md](scene-music.md));
- a solo statement first, then the theme passed to a section, then to the full ensemble.

**A plan of texture.**
- Add instruments in steps toward the high point. A gradual addition raises intensity steadily, and a sudden one makes it jump (Goodchild, Wild and McAdams 2019).
- Keep something back for the arrival ([climax-and-melody.md](climax-and-melody.md)): the melody's highest sustained note, the fullest texture and the loudest dynamic.
- Thin out once before the arrival, for one bar or one beat.

**Harmony.** Lehman (2018) traces how Hollywood scores use chromatic triadic progressions to evoke wonder and awe.
- **Chromatic mediants.** Major triads a third apart, such as I–♭VI, I–♭III or I–III. Under a held melody note the change sounds like a lift, not a modulation. For example, the melody holds D while the harmony moves from D major to B♭ major (I–♭VI): the common tone keeps the line steady while the chord surprises.
- **♭VI–♭VII–I.** A triumphant way home after a lift to ♭VI.
- **Lydian colour.** The raised fourth over IV (C♯ over G in D major) for openness or wonder. Write it as `maj7#11` in the harmony list so `review` reads it as intended.
- **Pedal points** under changing harmony for suspense or a long build.
- **Suspensions and appoggiaturas** on the melody's strong beats, resolving down by step. These are the device Sloboda (1991) found most often under tears.

**Strings and piano.**
- **The climax's melody in octaves.** First violins, second violins an octave lower and cellos two octaves lower, with the piano doubling the line in octaves. The violas, horns and double basses take the harmony.
- **Violins' top.** The violins' top sample is D6 (`vsco_strings` stretches it to F♯6), so peak at A5–D6 and let a flute or the solo violin take anything higher.
- **Inner parts stay out of the melody's way.** Voice sustained inner parts (violas, horns, pads) without:
  - a major seventh, an added ninth or a sharp eleventh next to the root;
  - a semitone against the melody's longer notes.

  Leave those colours to the melody and the piano. `review` lists the remaining minor seconds and ninths; check that each is intended.
- **The piano** as a soloist: a pedalled preset, with the pedal changed with the harmony, and the left hand in flowing eighths through the chord. In the tutti it plays octaves.
- **Arrivals.** Mark them with a timpani roll growing into the downbeat and a suspended cymbal swell timed to peak on it ([orchestration.md](orchestration.md)).

**Tempo.**
- Slow tempos, with soft dynamics and legato, convey sad and peaceful characters (Eerola, Friberg and Bresin 2013, in [game-music.md](game-music.md)).
- Lean slightly forward in the build, then broaden at the harmony before the climax and through it.
- Slow at phrase ends with `clock.rubato`, and use a long final ritardando.

**Level.** Use `mix.dynamics: "wide"` with `target_lufs` −18 and `range_lu` 12, as for orchestra. Check with `analyze`:
- the climax section should be the loudest and brightest;
- the lead should not sit far under the accompaniment in the build (`lead_presence`).

## Scoring to picture

Film composers work from a timing list of the events the music must meet. These are hit points such as a cut, a gesture or a line (Karlin and Wright 2004).

- **Hit points on the grid.** Convert each hit point to a beat with the tempo map. Choose the tempo, or nudge it by a few BPM between hits, so that the important hits fall on strong beats; do not move the hit. A hit can be a downbeat, an entry, an accent, a chord change or a stop.
- **Catch some cuts, not all.** Music that marks every cut becomes mechanical, like "Mickey-Mousing". Mark the cuts that change the scene's meaning.
- **Entering and leaving.**
  - Start under the scene softly (a pad, a held note) so the entry is felt, not heard.
  - End with a button on the cut, or ring out under the next scene's start.
- **Under dialogue.** Keep the melody out of the voice's register and out of 1–4 kHz, where speech intelligibility mostly lies ([scene-music.md](scene-music.md)).
  - Keep the texture thin and sustained.
  - Bring in no new instrument under a line.
  - Move the theme to the gaps between lines.
- **Stems.** The render writes stems, so an editor can lower one group under a line. Say which stems carry the melody.

## Suspense and horror

**Two jobs.**
- **Anxiety** is sustained unease: quiet, slow, steady.
- **Terror** is the shock.

Trevor, Arnal and Frühholz (2020) compared screams and other vocalizations with "scream-like" music from scary film scenes and with music from other scenes. The scream-like music shared the screams' roughness, which may signal danger in music as it does in the voice.

**Roughness** is fast fluctuation of loudness. In screams it lies roughly between 30 and 150 Hz of modulation (Arnal et al. 2015). Two tones a semitone apart beat at their difference in frequency, and the register decides which you get:
- a minor-second cluster in the violins' fifth octave (880 Hz and up) beats at 50 Hz or more and sounds rough, scream-like;
- the same cluster near A3 (220 Hz) beats at about 13 Hz and throbs.

So use **high clusters for terror** and **low clusters for dread**.

**Nonlinear sounds.**
- Blumstein, Davitian and Kaye (2010) scored the soundtracks of highly ranked action, drama, horror and war films. The horror soundtracks of their sample had more noisy screams and more of what they call "non-musical sidebands" than expected, and fewer abrupt frequency transitions; dramas had more of the transitions and less noise.
- Noise or abrupt frequency shifts added to neutral music changed listeners' ratings of both arousal and valence. Paired with a benign video, only valence still fell, with the added noise or downward shifts (Blumstein, Bryant and Kaye 2012).
- So with a picture, expect a harsh sound to darken a scene more than to excite it, and tie it to an event on screen.

**The toolkit on the banks.**

| Effect | Bank and preset |
|---|---|
| Low string tremolo, a throbbing floor | `vsco_strings` tremolo 0:44 (violins), 0:45 (violas), 0:46 (cellos); `vsco_extra` 4:43 (double bass) |
| A thin high tremolo | `vsco_colors` 0:44 (solo violin tremolo) |
| Bowed metal | `iowa_perc` 128:48 keys 27 (40-inch tam-tam bowed), 28 (28-inch), 29 (crash), 30 (Chinese cymbal) |
| Scrapes and rubs | `vsco_colors` 128:50 keys 52 (scraped gong), 53 (bowed cymbal), 54 (scraped cymbal), 35 (rubbed bass drum) |
| The hit | `iowa_perc` tam-tams 52, 50, 48 and wind gong 47 (leave 12–15 s of `tail_seconds`); `vcsl` timpani 0:47; a low piano cluster on the Steinway (`vcsl` 0:0) |
| Falling or rising shimmer | `vsco_colors` 128:9 glockenspiel glissandi |
| Drones, air, wind | synth pads, `noise` parts |

**Shape of a suspense cue.**
1. **A floor:** a drone or low tremolo, pp, harmonically static.
2. **A pulse:** a heartbeat-like low thump or an ostinato.
3. **Slowly growing:** density, register and dynamics, with clusters widening by semitones.
4. **Silence:** one to two seconds before the shock.
5. **The shock:** a loud, dense, rough cluster with a fast attack (brass, a tam-tam, a low piano cluster, timpani). Section strings speak too slowly for the hit itself; let them sustain it.
6. **The aftermath:** the ring of the metal, and the floor again.

Huron (2006) explains the jump: an unexpected event triggers a fast, defensive reaction before any appraisal.

**In a visual novel or a game.**
- The loop under text stays steady ([scene-music.md](scene-music.md)).
- Put shocks in separate one-shot stingers that the script triggers ([game-music.md](game-music.md)).
- A loop that shocks every 90 seconds shocks under whatever line is on screen.

**Level.** Use a wide master: `mix.dynamics: "wide"`, `target_lufs` around −20 and `range_lu` up to 15. The shock needs room above the floor, about 20 dB or more.

## Symptoms and causes

| Symptom | Likely causes | What to check or change |
|---|---|---|
| The climax does not arrive | the melody peaked earlier; the texture was already full; no harmonic surprise at the arrival | hold the highest note and fullest texture back; a chromatic mediant or ♭VI–♭VII–I at the arrival; a reduction just before |
| Syrupy or generic | the full ensemble all the time; one dynamic; every chord with added colour in every part | a solo-to-tutti plan; colours kept to the melody and piano; contrast between sections |
| The melody is lost in the build | inner parts or the bass as loud as the melody; doublings counted as accompaniment | `lead_presence` per section; the melody section up, the bass down; double the melody rather than adding harmony |
| The underscore fights the dialogue | melody in the voice's register; busy rhythm; entries under lines | a thin sustained bed; the theme between lines |
| Horror that is not scary | everything loud; no silence before the shock; consonant drones; clusters only in the bass | contrast of 20 dB or more; 1–2 s of silence; high rough clusters for the hit |
| A weak stinger | slow string attacks on the hit; small level jump; no low end | brass, metal and piano on the hit; strings sustain after it |

## Sources

- Lehman, F. (2018). *Hollywood Harmony: Musical Wonder and the Sound of Cinema*. Oxford University Press.
- Karlin, F. and Wright, R. (2004). *On the Track: A Guide to Contemporary Film Scoring*, 2nd ed. Routledge.
- Sloboda, J. A. (1991). Music structure and emotional response: Some empirical findings. *Psychology of Music* 19(2), 110–120.
- Goodchild, M., Wild, J. and McAdams, S. (2019). Exploring emotional responses to orchestral gestures. *Musicae Scientiae* 23(1), 25–49.
- Eerola, T., Friberg, A. and Bresin, R. (2013). [Emotional expression in music: contribution, linearity, and additivity of primary musical cues](https://pmc.ncbi.nlm.nih.gov/articles/PMC3726864/). *Frontiers in Psychology* 4:487.
- Trevor, C., Arnal, L. H. and Frühholz, S. (2020). Terrifying film music mimics alarming acoustic feature of human screams. *The Journal of the Acoustical Society of America* 147(6), EL540 (JASA Express Letters). doi:10.1121/10.0001459
- Arnal, L. H., Flinker, A., Kleinschmidt, A., Giraud, A.-L. and Poeppel, D. (2015). Human screams occupy a privileged niche in the communication soundscape. *Current Biology* 25(15), 2051–2056.
- Blumstein, D. T., Davitian, R. and Kaye, P. D. (2010). [Do film soundtracks contain nonlinear analogues to influence emotion?](https://pmc.ncbi.nlm.nih.gov/articles/PMC3001365) *Biology Letters* 6(6), 751–754. doi:10.1098/rsbl.2010.0333
- Blumstein, D. T., Bryant, G. A. and Kaye, P. (2012). The sound of arousal in music is context-dependent. *Biology Letters* 8(5), 744–747.
- Huron, D. (2006). *Sweet Anticipation: Music and the Psychology of Expectation*. MIT Press.
