# Anime-opening style: a band cue in about ninety seconds

Read this when the request is an anime opening, a J-rock or J-pop-style band cue, an energetic theme for a game or video in that style, or an instrumental version of a song like that. A TV opening typically holds a single verse–prechorus–chorus rotation in about 90 seconds (Li 2026). Each piece of guidance below names its source; the layouts and tables are example plans built from them, not norms. Instrumental here means an instrument carries the vocal line, so the melody has to be singable and the lead part has to phrase like a singer. Rock and metal outside this form, with riffs, palm-muted guitars and breakdowns, are in [rock-and-metal.md](rock-and-metal.md).

This cue and the other J-pop styles (fast electro J-pop, idol pop, city pop, enka), each on the seven axes with its sources, are in [style-map-jpop.md](style-map-jpop.md).

Contents: [Brief](#brief) · [Form](#form) · [Harmony](#harmony) · [Melody for an instrumental lead](#melody-for-an-instrumental-lead) · [Rhythm and drums](#rhythm-and-drums) · [Arrangement](#arrangement) · [Performance](#performance) · [The mix](#the-mix) · [Instruments](#instruments) · [Symptoms and causes](#symptoms-and-causes) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

## Brief

Settle these from the request; what it leaves open is decided after the piece's words are drawn (SKILL.md, steps 1 and 2), and said so:

- **Length**: "TV size" is about 90 seconds. TV openings have ranged from 70 to 110 seconds and average about 90 (Anime Nation's "Ask John" column). A full-size version runs about four minutes and repeats verse, build and chorus with a bridge.
- **Tempo**: from the brief. In Li's (2026) survey the openings with a postchorus had a median tempo more than 20 BPM faster than those without: to keep about 90 seconds, a slow opening drops the postchorus.
- **Lead instrument**: the line a singer would sing. Any timbre can carry it; what it needs is phrasing. A sustained sampled instrument (electric guitar, violin, trumpet, flute) connects notes with legato, and a guitar adds bends. A piano phrases by overlap and voicing. The additive synth voice phrases with glide and vibrato. The lead can pass between instruments by section, for example piano in the verse and guitar in the chorus.
- **Ending**: a short tag with a final hit or chord, or a fade: decide from the brief.
- **Delivery**: as usual. For a game title screen or a battle, decide whether it loops ([game-music.md](game-music.md)).

## Form

Japanese songwriting names the sections A-melo (verse), B-melo (the pre-chorus) and sabi (chorus). Li (2026) surveyed the openings of the most popular TV series on MyAnimeList:
- 100 of 108 (92.6%) used a single intro–verse–prechorus–chorus rotation lasting about 90 seconds;
- in the opening Li presents as the archetype, the verse and the chorus close on authentic cadences and the prechorus on a half cadence (one example, not a count of the corpus);
- section lengths varied widely around the often-quoted 16 + 8 + 16 bars;
- 61% had no postchorus.

An example TV-size layout:

| Section | Bars (4/4) | Function |
|---|---|---|
| Intro | 4–8 | The chorus hook or a riff from it, full band |
| A-melo | 8–16 | The verse: the groove settles |
| B-melo | 4–8 | The build to the chorus (below) |
| Sabi | 8–16 | The chorus: the hook, the highest sustained notes, the full band |
| Tag | 2–4 | The hook's last phrase or a riff, then the final hit |

At 170 BPM a 4/4 bar lasts 1.41 s, so 64 bars take 90 s; at 150 BPM, 56 bars do. Count the bars against the target length before writing.

**The build.** Summach (2011) traces the pre-chorus in Anglo-American pop and finds one function behind its many devices: building momentum toward the chorus. The devices he lists:
- changes of groove;
- shorter phrase units (fragmentation);
- a faster harmonic rhythm;
- a rising register;
- added or thinned instruments;
- a harmonic progression that leaves the verse's tonic;
- sometimes a held pause just before the chorus.

In the opening Li presents as the archetype the prechorus closes on a half cadence, on V.

**The chorus** is more intense than the verse: a fuller or busier texture, a higher melody, or both (Summach 2012, in Open Music Theory). A two-part chorus states its idea twice, the halves beginning alike and ending differently (aa′; Open Music Theory, Melody and Phrasing).

## Harmony

- The **royal road progression**, IV–V–iii–vi (often IVmaj7–V7–iii7–vi), is widely described as the typical J-pop chorus progression since the 1990s, and Ramage (2023) studies it as a distinctive feature of modern Japanese popular music. Starting the chorus on IV keeps the tonic back for the cadence. His counts are not repeated here (the article was read only in summary), so treat it as one strong option, not a rule.
- Pop's four-chord schemas are in [pop-and-ballad.md](pop-and-ballad.md).
- **Modulation by a minor third** is the style's signature, more than the stepwise "pump-up" of Western pop. In Li's corpus:
  - 41% of the openings modulated at least once;
  - 38 of the 72 modulations moved a minor third up or down, and 14 by a step;
  - 33 of the 72 fell at the prechorus–chorus boundary.

  Two ways to write it:
  - **Up a minor third** (to ♭III): the prechorus expands the predominant, the bass moves into ♭VI and ♭VII, and ♭VII acts as V of the new key, landing on its tonic (or, deceptively, on its relative minor) at the chorus.
  - **Down a minor third** (to VI): the bass climbs from 2 to 5, then III, which normally leads to vi, resolves to a major VI instead.

  The two are reciprocal: up and then down returns to the first key. A stepwise lift is the other common move (14 of Li's 72).
- **The guitars' tone goes with their voicing.** Under distortion a rhythm guitar plays power chords (root and fifth, often with the octave): distortion's harmonics and intermodulation give most chords a major quality, a distorted major triad sounds much like a power chord, and a minor third clashes with that implied major third and turns rough, a major quality that coexists with the minor-mode melodies around it (Lilja 2015); with more distortion, listeners rated power chords and major triads clearly more pleasant than minor triads and richer chords (Herbst 2019). The family's progressions carry sevenths, tensions and slash chords ([style-map-jpop.md](style-map-jpop.md), Shared by the family): a guitar that plays them as written takes a clean or slightly broken-up tone (`mix.amp` `clean` or `edge`), and open strings left ringing against a moving shape add sevenths, ninths and elevenths from the hand's position (Koozin 2011, ¶11-12). Under `crunch` or `high_gain`, the minor thirds and colour tones come from the bass line, piano, strings, the lead or a second, cleaner guitar. `review` still checks the written chord list against the foreground.

## Melody for an instrumental lead

Write it as [climax-and-melody.md](climax-and-melody.md) describes (Writing a melody that sounds composed): the hook first, phrases that breathe, each section built by restating its idea.

- Keep the line singable (Perricone 2000):
  - most vocal melodies move by step, with leaps for character;
  - ask whether the range is too great, and whether it changes too quickly within a section;
  - leave room to breathe at phrase ends.
- A higher melody is one of the ways a chorus intensifies (Summach 2012, above).
- **An instrument in the singer's place.** In mixes of popular music, listeners found the lead vocal more reliably than any instrument, whatever the filtering or level (Bürgel, Picinali and Siedenburg 2021, in [sound-selection.md](sound-selection.md)). An instrumental lead has to be given that place: the top of the texture, a timbre unlike the band's, and room in level.
- A piano that carries the tune over a band:
  - **Keep the band's chords out of its register.** Chuck Israels puts piano comping mostly below middle C, from about D3 to F4 or G4, with the weight below C4. Higher than that, he writes, chords intrude on the range where the ear is most sensitive and crowd the lead, whose overtones need that space even when its notes lie lower. `ceilings` in `musiclib.voicing` holds a voicing under the melody chord by chord.
  - **Octaves where the band is full**, the melody voiced above its octave ([piano-and-chamber.md](piano-and-chamber.md), Voicing). A doubling whose notes start together makes the line richer without splitting it in two ([climax-and-melody.md](climax-and-melody.md), Orchestration).
  - **A brighter recording for the lead.** Parts in front of a mix are brighter and drier than the parts behind them (White 2009). The piano is the Steinway ([piano-and-chamber.md](piano-and-chamber.md)); its brightness in front of a mix is set by the touch and the equalizer ([performance-and-mix.md](performance-and-mix.md), A bright pop piano).
  - **If the lead still sits back, find what masks it.** Listen to the lead while muting the other parts one at a time; where the lead steps forward, cut some of that part's frequencies (Senior 2018). `analyze` reports the lead's level over its accompaniment and how much of it is masked.
- Syncopate the ends of phrases, not every note: rock and pop melodies anticipate strong beats, for example a note on the "and" of four tied over the bar line (Tan, Lustig and Temperley 2019).
- Every note-on restarts a sample's attack, which a singer, a bow or a breath does not do between connected notes. Give sustained sampled leads `performance.legato`, and the guitar bends ([performance-and-mix.md](performance-and-mix.md)).

## Rhythm and drums

- Most pop drumbeats keep a backbeat, the snare on 2 and 4; half-time and double-time are common alternatives (Open Music Theory, Drumbeats). Drum patterns usually change from section to section, for example from hi-hat in the verse to ride in the chorus (Dow 2010). An example plan: eighth-note hats in the verse, half-time or a new kick pattern for the build, sixteenth hats or ride for the chorus.
- Syncopate moderately. Witek et al. (2014) found that drum breaks with medium syncopation made listeners most want to move and gave the most pleasure, more than either little or a lot of syncopation.
- Keep the drums tight. Frühauf, Kopiez and Platz (2013) found that small timing deviations did not make a simple drum pattern groove better than the quantized version. `musiclib.expression` keeps drum deviation small for that reason.
- **Change the pattern with the form.** In the Billboard pop airplay top ten of each year from 2012 to 2021, a song had 5.4 drum patterns and about 10 pattern changes on average, the changes falling at phrase and section junctures; 96% of the songs varied the number of layers, 77% the rhythm, 78% the instruments. A build adds layers or quickens the rhythm (a prechorus adding sixteenths on the hi-hat), a fall takes them away (15% of the songs with a prechorus had one that falls), and a bridge may go to half time or move from the hi-hat to the ride (Geary 2024).
- A small fill at the end of a section leads into the next; no hi-hat during a tom fill, and no more limbs at once than a drummer has. Vary the ghost notes and the open hats between the halves of a phrase instead of repeating one every bar, and play alternate hi-hat strokes softer, as two hands do (Dow 2010).
- **The four-on-the-floor of Japanese rock.** Since the 2000s many Japanese rock bands have played the kick on every quarter note, the snare on 2 and 4 and the hi-hat on the off-beats between the kicks, on a sixteenth-note grid; in Japanese rock it became a style of its own, fast (about 133 to 175 BPM in the songs named) and built on catchy riffs, and one song keeps a funky, syncopated verse and brings the four-on-the-floor in only for the chorus (imdkm 2019, music journalism). One of the grooves a J-pop band cue may take, not its rule.
- **Place the stops.** Unison stops and hits (kime) change the texture sharply, and strong contrasts of texture mark section boundaries (McAdams, Goodchild and Soden 2022); Summach lists a held pause just before the chorus among the prechorus's devices. Inside a section, a stop also interrupts the groove the drums and bass are building, so place each where the form wants it.

## Arrangement

| Part | Verse (A-melo) | Build (B-melo) | Chorus (sabi) |
|---|---|---|---|
| Drums | a groove of the section's own: eighth or sixteenth hats, or the four-on-the-floor | a build (more layers, sixteenths on the hats, rising toms or snare) or a fall | the fullest pattern: ride or open hats, a crash on the downbeat |
| Bass | roots on the strong beats, with passing or approach notes into the chord changes | longer notes or a climbing line | octaves, passing tones into chord changes |
| Rhythm guitars | one guitar, clean or slightly broken up: the chord left to ring note by note with its open strings and added tones, muted sixteenth cutting, or a riff | add the second guitar, or move the first to sustained or strummed chords | two guitars panned apart: strummed full chords, or barre or power chords under more drive; an octave line or a riff answering the lead |
| Piano | the riff or the lead | chords in the upper middle | high-register sparkle, doubling the hook; a bright grand ([performance-and-mix.md](performance-and-mix.md), A bright pop piano) |
| Strings | sustained pads | rising lines or an eighth-note ostinato | the melody an octave up, or long counter-lines |
| Brass | — | swells | stabs on the accents |
| Bells, mark tree | — | a mark tree into the chorus | glockenspiel on the hook, a cymbal swell into the last chorus |

The table is an example plan. Build by addition from verse to chorus (McAdams, Goodchild and Soden 2022 describe such gradual addition), and hold layers back so the last chorus has somewhere to go (Senior 2024).

The guitar and bass rows are ways of playing, not a rule. Open-string chords in the verse and barre or power chords in the chorus is one order, the reverse another (Koozin 2011, ¶15-16). A bass can step off its roots: to the chord's fifth and third, or to a chromatic approach note a semitone from the next root, which the ear accepts because the line is heading for that root (MusicRadar 2022, a practitioner lesson). A guitar part in one way of playing from start to end, or a bass on repeated roots throughout, is a choice for `decisions`, not a default.

## Performance

- **Strummed guitar chords**: `musiclib.expression` with `{"strum": 6}` (ms between strings) for a rhythm-guitar track strikes chords low to high on downstrokes and high to low on upstrokes, alternating down on each eighth and up between them (`strum_grid`: 0.5 beats). The guides use 4–8 ms for driving parts and about 15 for slow, open strums, choices of this skill rather than measurements ([performance-and-mix.md](performance-and-mix.md)). Power chords of two or three notes barely spread at these values, as with a real pick.
- Shape velocities by phrase, rising toward the end of a bar or a section (Dow 2010). Constant velocities replay one sample.
- Bass: `bass_darkblack` plays ghost notes at velocities 1–24, about 28–32 dB under velocity 120. Write ordinary notes from about 40 up.

## The mix

- **Brightness comes from the band.** Elowsson and Friberg (2017) found that the more percussion a popular-music track has, the more energy it has in the bass and the treble, and that much of the spectral difference between genres follows from that. Commercial recordings also lean toward a consistent target spectrum (Pestana et al. 2013).
  - So a band cue should show far more energy above 2.5 kHz in `analyze` than a strings-and-harp loop.
  - If the 2.5–6 kHz and 6–16 kHz bands still hold only a fraction of a percent, look for the cause before reaching for EQ: hi-hat and cymbal levels, a low `lowpass` on the guitars or the reverb returns, or a lead with no presence.
- **Guitars.** High-pass the rhythm guitars so the bass owns the low end, and tame distortion's fizz with a low-pass ([rock-and-metal.md](rock-and-metal.md) gives the practitioners' starting points; a part through `mix.amp` needs no such low-pass, its loudspeaker filter falls away above 5 kHz).
- **The lead sits on top.** Read `lead_minus_accompaniment` in `analyze`; to find what masks the lead, see the piano bullets above.
- **Loudness.** Deliver at −14 LUFS, Spotify's playback level ([pop-and-ballad.md](pop-and-ballad.md)).

## Instruments

| Role | Bank and preset |
|---|---|
| Drums | `rusty` (rock kit on GM keys), the skill's one acoustic rock kit: what sets one piece's drums apart is the pattern by section, the ghosts and accents, and the processing |
| Bass | `bass_darkblack` 0:33 (five-string, fingers, four dynamics, ghost notes on low velocities), 1:33 staccato; `bass_pick` 0:0 for a picked attack and `bass_finger` 0:0, each with one velocity layer, so their dynamics come from the level and, through `mix.amp` `bass`, from the drive |
| Rhythm guitars | Chosen with the voicing and the section, and by the piece's own idea (SKILL.md, step 2: a level its whole gave, in `association.gives`), the reason in `decisions`. `fsbs_direct` through `mix.amp`, played by string: `clean`, or `edge`, which breaks up when struck hard, for chords left to ring and colour chords; `crunch` for strummed or riffed chords; `high_gain` for palm-muted riffs. `fsbs_clean`, a recorded clean amplifier, for arpeggios; `guitar_shiny` 0:26, an archtop's magnetic pickup, for a rounder clean voice; `fsbs_dist1` and `fsbs_dist2`, recorded distortion. Two guitars may differ in bank or voice as well as in pan ([rock-and-metal.md](rock-and-metal.md), Writing the guitar part) |
| Lead | `fsbs_direct` through `mix.amp` on `lead` with bends (joined with `performance.legato` and without `strings`, or played by string without legato), or `fsbs_dist2` with legato and bends; `vsco` Solo Violin 0:40; `vsco` Trumpet 0:56, Trumpet Vibrato 2:56 (samples about 4.7 s); `vcsl` Grand 0:0; `vsco` Flute 0:73 |
| Strings, brass | `vsco` section strings, spiccato, Brass Section 0:61, Brass Stab 0:62 |
| Synths | Surge XT patches for pads, plucks and leads, chosen for the part's job ([sound-selection.md](sound-selection.md)) |
| Colour | `vsco` Glockenspiel 0:9, `vcsl` Tubular Bells 0:14, `vcsl` Orchestra Kit 128:48 (clash cymbals, timed cymbal swells, mark tree), `vcsl` Timpani 0:47 for an orchestral intro |

Probe a preset before building a part on it ([soundbank-measurements.md](soundbank-measurements.md) has what each bank measured).

## Symptoms and causes

| Symptom | Likely causes | What to check or change |
|---|---|---|
| Mechanical | constant velocities, which replay one sample; every part exactly on the grid; a lead with no dynamics or vibrato | velocities shaped by phrase, `musiclib.expression`, legato or vibrato on the lead |
| Momentum stalls | stops, kime or held chords inside sections | where the form needs each stop |
| The lead sounds detached | a sampled lead re-attacking each note | `performance.legato`, longer notes, bends on guitar |
| Dull | quiet cymbals, low-passed guitars or reverb returns, a lead without presence | `analyze` band shares and stem levels first |
| The chorus does not lift | the verse is as dense and as high as the chorus | a chorus denser or higher than the verse (Summach 2012); the B-melo's devices (Summach 2011) |
| Every band cue sounds alike | power chords from start to end; one bar rhythm in every section; one drum pattern throughout; the same tone on every guitar | the band by section (Arrangement), the patterns by section (Rhythm and drums), the tone with the voicing (Harmony), the guitars chosen by the piece's own idea (Instruments); `review` counts each rhythm and harmony part's bar rhythms and chord kinds by section, and asks `unchanging:<part>` where a chorus is played as the verse was |
| The guitars sound thick or smeared | more drive than the voicing takes; doubled guitars each at full gain | `clean` or `edge` for colour chords; less gain on each doubled guitar than seems needed (Senior 2019) |

## Sources

- Dow, R. (2010). [Programming Realistic Drum Parts](https://www.soundonsound.com/techniques/programming-realistic-drum-parts). *Sound On Sound*, September 2010.
- Gotham, M. et al. *Open Music Theory*, version 2: Hughes, B. and Lavengood, M., [Verse-Chorus Form](https://viva.pressbooks.pub/openmusictheory/chapter/verse-chorus-form/) (quoting Summach 2012) and [Melody and Phrasing](https://viva.pressbooks.pub/openmusictheory/chapter/melody-and-phrasing/); Hanenberg, S., [Drumbeats](https://viva.pressbooks.pub/openmusictheory/chapter/drumbeats/).
- McAdams, S., Goodchild, M. and Soden, K. (2022). [A Taxonomy of Orchestral Grouping Effects Derived from Principles of Auditory Perception](https://doi.org/10.30535/mto.28.3.6). *Music Theory Online* 28(3).
- Perricone, J. (2000). *Melody in Songwriting*. Berklee Press. The [Chapter 1 excerpt](https://online.berklee.edu/takenote/conjunct-disjunct-melody-basic-definitions/).
- Senior, M. (2024). [Mix Rescue: Strong Arrangements](https://www.soundonsound.com/techniques/mix-rescue-strong-arrangements). *Sound On Sound*, May 2024.
- Tan, I., Lustig, E. and Temperley, D. (2019). Anticipatory syncopation in rock: a corpus study. *Music Perception* 36(4), 353–370.
- Li, J. (2026). [Modulation and Chromatic Mediants in Japanese Anime Songs](https://mtosmt.org/issues/mto.26.32.1/mto.26.32.1.li.php). *Music Theory Online* 32(1). doi:10.30535/mto.32.1.6
- Summach, J. (2011). [The Structure, Function, and Genesis of the Prechorus](https://mtosmt.org/issues/mto.11.17.3/mto.11.17.3.summach.html). *Music Theory Online* 17(3).
- Witek, M. A. G., Clarke, E. F., Wallentin, M., Kringelbach, M. L. and Vuust, P. (2014). [Syncopation, Body-Movement and Pleasure in Groove Music](https://doi.org/10.1371/journal.pone.0094446). *PLoS ONE* 9(4): e94446.
- Frühauf, J., Kopiez, R. and Platz, F. (2013). Music on the timing grid: the influence of microtiming on the perceived groove quality of a simple drum pattern performance. *Musicae Scientiae* 17(2), 246–260.
- Lilja, E. (2015). Dealing with the 3rd: anatomy of distorted chords and subsequent compositional features of classic heavy metal. In T.-M. Karjalainen and K. Kärki (eds.), *Modern Heavy Metal: Markets, Practices and Cultures*, pp. 393–403. Helsinki and Turku: Aalto University and the International Institute for Popular Culture. [Archived PDF](https://web.archive.org/web/20250124071258/https://iipc.utu.fi/MHM/Lilja2.pdf).
- Elowsson, A. and Friberg, A. (2017). [Long-term Average Spectrum in Popular Music and its Relation to the Level of the Percussion](https://www.aes.org/e-lib/browse.cfm?elib=18638). AES 142nd Convention.
- Pestana, P. D., Ma, Z., Reiss, J. D., Barbosa, A. and Black, D. A. A. (2013). [Spectral Characteristics of Popular Commercial Recordings 1950–2010](https://www.aes.org/e-lib/browse.cfm?elib=17010). AES 135th Convention, paper 8960.
- Anime Nation. [Ask John: What Anime Have the Longest & Shortest Openings?](https://www.animenation.net/blog/?p=23043)
- Israels, C. [The Piano and the Art of Jazz Accompaniment](https://chuckisraelsjazz.com/blogs/news/the-piano-and-the-art-of-jazz-accompaniment). Chuck Israels Jazz Orchestra. Registers for piano comping under a singer or a soloist.
- Senior, M. (2018). [Q. How can I locate the masking problems in my mix?](https://www.soundonsound.com/sound-advice/q-how-can-locate-masking-problems-my-mix) *Sound On Sound*, March 2018.
- White, P. (2009). [Creating A Sense Of Depth In Your Mix](https://www.soundonsound.com/techniques/creating-sense-depth-your-mix). *Sound On Sound*, February 2009. Parts in front brighter and drier than those behind.
- Ramage, M. (2023). The Royal Road Progression in Japanese Popular Music. *Music Theory Spectrum* 45(2), 238–256. https://doi.org/10.1093/mts/mtad008
- [Royal road progression](https://en.wikipedia.org/wiki/Royal_road_progression). Wikipedia.
- Geary, D. (2024). [Formal Functions of Drum Patterns in Post-Millennial Pop Songs, 2012–2021](https://mtosmt.org/issues/mto.24.30.2/mto.24.30.2.geary.html). *Music Theory Online* 30(2). doi:10.30535/mto.30.2.3
- Herbst, J.-P. (2019). [Distortion and rock guitar harmony: the influence of distortion level and structural complexity on acoustic features and perceived pleasantness of guitar chords](https://pure.hud.ac.uk/en/publications/distortion-and-rock-guitar-harmony-the-influence-of-distortion-le/). *Music Perception* 36(4), 335–352. doi:10.1525/mp.2019.36.4.335
- imdkm (2019). [リズムから考えるJ-POP史 第6回：Base Ball Bearから検証する、ロックにおける4つ打ちの原点](https://realsound.jp/2019/06/post-372154.html) (in Japanese). *Real Sound*, 9 June 2019. Music journalism, not peer-reviewed.
- Koozin, T. (2011). [Guitar Voicing in Pop-Rock Music: A Performance-Based Analytical Approach](https://mtosmt.org/issues/mto.11.17.3/mto.11.17.3.koozin.php). *Music Theory Online* 17(3).
- MusicRadar (2022). [How to write compelling basslines by working around root notes](https://musicradar.com/how-to/write-bassline-root-notes). 3 February 2022. A practitioner lesson.
- Senior, M. (2019). [Q. How do I make my guitars sound more 'epic'?](https://www.soundonsound.com/sound-advice/q-how-do-make-guitars-sound-more-epic) *Sound On Sound*, May 2019.
