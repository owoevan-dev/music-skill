# Style map: rock and metal

Guitar bands, from classic rock to post-rock and from traditional heavy metal to its extreme forms. Read
[style-maps.md](style-maps.md) first for the axes and for combining entries; the craft is in
[rock-and-metal.md](rock-and-metal.md) (riffs, power chords, drums, the guitars on the banks, the bass, the mix),
with [anime-opening.md](anime-opening.md) for a J-rock band cue and [pop-and-ballad.md](pop-and-ballad.md) for the
power ballad.

Contents: [Shared by the family](#shared-by-the-family) · [Classic and hard rock](#classic-and-hard-rock) ·
[Punk](#punk) · [Alternative and indie](#alternative-and-indie) · [Shoegaze](#shoegaze) · [Post-rock](#post-rock) ·
[Progressive rock](#progressive-rock) · [Surf](#surf) · [Heavy metal](#heavy-metal) · [Thrash](#thrash) ·
[Power metal](#power-metal) · [Extreme metal](#extreme-metal) · [Doom](#doom) · [Metalcore](#metalcore) ·
[Nu metal](#nu-metal) · [Sources](#sources)

Source tags: WP is Wikipedia, by article: read on 9 November 2026, and on 6 November for the articles in
[rock-and-metal.md](rock-and-metal.md). The other sources are by author and year.

## Shared by the family

- **Chords.** In 100 songs of a rock canon, IV was the most common chord after I, especially right before the tonic,
  and ♭VII the most common root outside the major scale (de Clercq and Temperley 2011). Classic rock's modal patterns:
  the double-plagal ♭VII–IV–I, the Aeolian ♭VI–♭VII–i, chords built on the pentatonic scale (Biamonte 2010).
- **Melody against the chords.** Rock melodies often leave non-chord tones unresolved, mostly in pentatonic verses;
  choruses bring melody and chords closer (Temperley 2007).
- **Distortion and the power chord.** Distortion lowers sensory consonance, most of all with complex harmony (Herbst
  2018); under it, power chords and major triads sound clearly more pleasant than minor triads and altered dominants,
  so the more distorted styles rely more on power chords (Herbst 2019); distortion gives most chords a major quality
  (Lilja 2015).
- **The band.** The backbeat (OMT, Drumbeats); tight drums, as small timing deviations did not improve a simple
  pattern's groove (Frühauf, Kopiez and Platz 2013); rhythm guitars recorded at least twice and panned apart (Mynett
  2017).
- **Measured.** In the Harmonix Set, 36 songs labelled rock: a median 126 BPM, the middle 80% between 82 and 151;
  verses 8 bars long in 41% and 16 in 28%, choruses 8 in 37%, solos a median 10 bars. 32 labelled metal: a median
  143 BPM, 80% between 91 and 190; a median 4.8 minutes; solos a median 18 bars, bridges 16 bars in 31%. The
  labels are the set's, not this map's sub-styles. Measured here.
- **The spectrum.** Number ones tagged rock slope −0.98 on Pestana et al. (2013)'s log-log measure over 100 Hz–10 kHz
  (pop −0.94), with no split by sub-genre. `analyze` sets the master beside it
  ([performance-and-mix.md](performance-and-mix.md), Brightness and air).

For the whole family, `review` does not ask about parallel fifths and octaves: power chords move in parallel fifths
by design (Herbst 2019; Lilja 2015), and guitars and bass play the same riff, the ordinary way of writing in heavy
metal (WP Doom metal). The question on pushes stays: Tan, Lustig and Temperley (2019) measured it on
rock melodies.

## Classic and hard rock

The backbeat band with power chords and open chords, pentatonic riffs and a lead guitar that bends.
`rock/classic-hard`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read; from the brief | |
| `harmony` | IV and ♭VII; the double-plagal and Aeolian patterns; power chords and open chords | de Clercq and Temperley 2011; Biamonte 2010; WP Hard rock |
| `melody` | minor-pentatonic riffs; a lead with bends; pentatonic verse melodies apart from the chords | WP Hard rock; Temperley 2007 |
| `rhythm` | the backbeat; eighths on the hi-hat or ride | OMT, Drumbeats; WP Hard rock |
| `timbre` | electric guitars, aggressive and distorted, as rhythm instruments on repetitive riffs and as the solo lead; the bass with the drums behind them | WP Hard rock |
| `form` | verse–chorus with a pre-chorus, a solo in the bridge's place | Summach 2011; rock-and-metal.md, Form |
| `mix` | no source read beyond this skill's delivery at −14 LUFS ([rock-and-metal.md](rock-and-metal.md), The mix) | |

- **In this skill**: [rock-and-metal.md](rock-and-metal.md): the guitars on the FSBS banks, `rusty`, the bass banks;
  `blocks.drums` in the `rock` feel ([building-blocks.md](building-blocks.md)).
- **Variants**: *Blues rock*: the chords, scales and improvisation of the blues, electric blues played faster and
  more aggressively, with electric guitar, bass, drums, sometimes keys and harmonica (WP Blues rock).
- **Neighbours**: Heavy metal (less syncopation and less blues, more brute force: WP Heavy metal music); Punk.

## Punk

Short, fast, stripped-down songs: driving eighths, power chords on downstrokes, little syncopation, no long solos.
`rock/punk`

| Axis | Traits | From |
|---|---|---|
| `tempo` | fast | WP Punk rock |
| `harmony` | few chords; eighth-note power chords | WP Punk rock; rock-and-metal.md |
| `melody` | rough, stripped-down vocals; basic guitar breaks rather than long solos | WP Punk rock |
| `rhythm` | driving eighths on the hats or ride, the snare on 2 and 4 or on every beat; much less syncopation than other rock | WP Punk rock |
| `timbre` | drums, bass and one guitar or two | WP Punk rock |
| `form` | short songs in verse–chorus form | WP Punk rock |
| `mix` | heavy, dry drums; against the overproduction of arena rock | WP Punk rock |

- **In this skill**: the punk row of [rock-and-metal.md](rock-and-metal.md); `blocks.drums` with `pulse="eighth"`,
  the snare on every beat for a lift written by hand.
- **Variants**: *Pop-punk*: fast, energetic tempos with classic pop songcraft, sweet harmonies against rowdy riffs, a
  catchy, faster power pop (WP Pop-punk).
- **Neighbours**: Classic and hard rock; Alternative and indie; Metalcore (from hardcore punk).

## Alternative and indie

Guitar music of power chords, chiming riffs, fuzz and feedback; a quiet, clean verse against a loud, distorted
chorus. `rock/alternative`

| Axis | Traits | From |
|---|---|---|
| `tempo` | measured here on 33 Harmonix Set songs labelled alternative: a median 96 BPM, the middle 80% between 78 and 135 | Nieto et al. 2019 |
| `harmony` | power chords | WP Alternative rock |
| `melody` | chiming riffs; melodic guitar interplay | WP Alternative rock; WP Indie rock |
| `rhythm` | the backbeat; toms in the verse | rock-and-metal.md (the Brief's table) |
| `timbre` | guitars that "blast out power chords, pick out chiming riffs, buzz with fuzztone and squeal in feedback" | Jon Pareles, "A New Kind of Rock", *The New York Times*, 5 March 1989, quoted in WP Alternative rock (the article itself not read) |
| `form` | on the same songs: choruses 8 bars long in 63%, verses 8 in 43% and 16 in 20%, a bridge in 82%; the clean, thin verse against a distorted chorus is this skill's ([rock-and-metal.md](rock-and-metal.md), Form) | Nieto et al. 2019 |
| `mix` | no source read | |

- **In this skill**: `fsbs_clean` with `chorus` for the verse, the distorted banks for the chorus
  ([rock-and-metal.md](rock-and-metal.md)).
- **Variants**:
  - *Grunge*: punk and heavy metal fused, the distorted guitar of both, at times slow and sludgy (WP Grunge).
  - *Jangle and indie pop*: the melodic interplay of clean guitars (WP Indie rock).
- **Neighbours**: Shoegaze; Punk; Post-rock.

## Shoegaze

A wash of sound: guitars in layers, distorted, flanged or pitch-bent, and obscured vocals; no instrument stands out.
`rock/shoegaze`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | ethereal, swirling, obscured vocals | WP Shoegaze |
| `rhythm` | no source read | |
| `timbre` | layered guitars, distorted, flanged or pitch-bent; pedals for distortion, chorus, tremolo, delay and reverb | WP Shoegaze |
| `form` | no source read | |
| `mix` | one blended wash in which no single instrument stands out | WP Shoegaze |

- **In this skill**: two or more distorted guitar parts with `bend` and `effects` `chorus` or `phaser`, long
  `reverb_db` and `mix.delay`; a lead set into the wash, not over it. `vocal_ah` for a wordless voice.
- **Variants**: *Dream pop*: atmosphere and texture as strong as the melody; breathy vocals, dense production, chorus,
  tremolo, echo and reverb everywhere; textures rather than propulsive riffs (WP Dream pop).
- **Neighbours**: Post-rock; Alternative and indie; `electronic/ambient`.

## Post-rock

Rock instruments for texture, timbre and atmosphere instead of songs: often instrumental, often one motive built to a
climax at the end. `rock/post-rock`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | a piece unified by one short progression, two chords in one example | Osborn 2011 |
| `melody` | a melodic theme, if any, on the lead guitar or keyboard; voices, when present, as one more layer | Osborn 2011; WP Post-rock |
| `rhythm` | patterns and minimal arrangements | WP Post-rock |
| `timbre` | rock instruments with electronics; the exploration of textures and timbres | WP Post-rock |
| `form` | through-composed: often a single motive developed by texture, timbre and dynamics, a structural crescendo or decrescendo; a volume climax at the end a recognisable trope | Osborn 2011 |
| `mix` | atmosphere and mood over conventional rock technique | WP Post-rock |

- **In this skill**: the clean and distorted guitars with delays and long reverbs, pads, the pianos; the crescendo
  written in layers entering and velocities rising, the climax saved for the end. `review` does not ask about a
  part's loop or a static texture here: one motive developed by texture, timbre and dynamics is the form (Osborn
  2011).
- **Neighbours**: Shoegaze; Progressive rock (math rock); `electronic/ambient`; the Orchestral map's minimalist entry
  (`orchestral/minimalist`).

## Progressive rock

Rock that takes up the techniques of jazz, folk and classical music: extended pieces in many sections, long solos,
technical virtuosity. `rock/progressive`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | some harmonic language taken from jazz and from the classical music of the 19th century; complex chord changes in the Canterbury scene | WP Progressive rock |
| `melody` | long solos | WP Progressive rock |
| `rhythm` | no source read for the style as a whole; math rock below | |
| `timbre` | the instrumentation of rock; wind instruments in the Canterbury scene; technology for new sounds | WP Progressive rock |
| `form` | extended pieces; non-recapitulating groups of sections | WP Progressive rock; Osborn 2011 |
| `mix` | the studio, not the stage, the focus: music for listening | WP Progressive rock |

- **In this skill**: the rock band with the keys row of [rock-and-metal.md](rock-and-metal.md) (organs, pianos), the
  winds of the orchestral banks; meters other than 4/4 in the clock.
- **Variants**: *Math rock*: complex, atypical rhythms with irregular stops and starts, odd meters,
  extended chords and counterpoint, through-composed rather than in song forms (WP Math rock); its metal kin builds
  pieces by stringing together thematically different riffs in changing meters such as 17/16 and 13/16 (Osborn 2011).
- **Neighbours**: Post-rock; Metalcore (the djent variant); Classic and hard rock.

## Surf

Instrumental rock and roll with reverb-drenched electric guitars meant to sound like waves, fast alternate picking,
straight 4/4. `rock/surf`

| Axis | Traits | From |
|---|---|---|
| `tempo` | medium to fast | WP Surf music |
| `harmony` | no source read | |
| `melody` | the guitar carries it; influences from Mexico and the Middle East in the founding style | WP Surf music |
| `rhythm` | almost always straight 4/4; rapid alternate picking | WP Surf music |
| `timbre` | electric guitars through a "wet" spring reverb | WP Surf music |
| `form` | instrumental | WP Surf music |
| `mix` | the reverb as the sound | WP Surf music |

- **In this skill**: `fsbs_clean` with a high `reverb_db` on the plate and fast repeated notes for the picking
  (`gate` short); `rusty` and `bass_pick`. The skill has no spring reverb model: the plate stands in.
- **Neighbours**: Classic and hard rock; Punk.

## Heavy metal

Traditional heavy metal: guitars loud and distorted, rhythm hammered home, bass and drums packed dense, the gallop, twin leads
and guitar solos. `rock/heavy-metal`

| Axis | Traits | From |
|---|---|---|
| `tempo` | slow in the early style, faster from the late 1970s | rock-and-metal.md (the Brief's table) |
| `harmony` | Aeolian and Phrygian riffs, modal progressions, the tritone and chromatic motion, pedal points; power chords | rock-and-metal.md (WP Heavy metal music, Walser 1993) |
| `melody` | one guitar solo or more, where the player shows virtuosity; twin leads in thirds | WP Heavy metal music; rock-and-metal.md |
| `rhythm` | emphatic rhythms with less syncopation than hard rock; the gallop in guitars and bass, often doubled by the kick; palm-muted crunch | WP Heavy metal music |
| `timbre` | distorted guitars at moderate gain played loud; a prominent bass in interplay with the guitar | WP Heavy metal music |
| `form` | no source read beyond the solo | |
| `mix` | loudness; bass and drums packed dense | WP Heavy metal music |

- **In this skill**: [rock-and-metal.md](rock-and-metal.md): the gallop, the palm-muted chugs on a part of their own,
  twin leads, the Aeolian and Phrygian riffs, the mix.
- **Neighbours**: Thrash; Power metal; Doom; Classic and hard rock.

## Thrash

Fast, aggressive metal: low-register palm-muted riffs, shredding solos, double kick and the thrash beat.
`rock/thrash`

| Axis | Traits | From |
|---|---|---|
| `tempo` | fast | WP Thrash metal |
| `harmony` | chromatic steps, tritones and diminished intervals rather than one scale | rock-and-metal.md (WP Thrash metal) |
| `melody` | high-register solos, shredding: sweep picking, legato, alternate and tremolo picking, tapping | WP Thrash metal |
| `rhythm` | fast percussive beats; the thrash beat, kick and snare alternating on eighths; double kick | WP Thrash metal; rock-and-metal.md |
| `timbre` | heavily distorted, often palm-muted power chords; scooped mids and a tightly compressed tone | WP Thrash metal; WP Heavy metal music |
| `form` | no source read | |
| `mix` | no source read beyond the tone above | |

- **In this skill**: the thrash row of [rock-and-metal.md](rock-and-metal.md); `eq` cuts in the mids of the rhythm
  guitars for the scooped tone (this skill's reading of it).
- **Neighbours**: Heavy metal; Extreme metal; Punk (hardcore and skate punk among its sources).

## Power metal

Mid-to-fast, epic and anthemic: a stream of double kick, melodic choruses, keyboards or an orchestra, neoclassical
solos. `rock/power-metal`

| Axis | Traits | From |
|---|---|---|
| `tempo` | mid to fast | WP Power metal |
| `harmony` | chords that change once a bar or slower under rapid streams of notes | rock-and-metal.md (WP Power metal) |
| `melody` | anthemic choruses; fast, neoclassical solos, natural and harmonic minor | WP Power metal; rock-and-metal.md |
| `rhythm` | a constant stream of sixteenths on the double kick, or thrash-style bursts | rock-and-metal.md (WP Power metal) |
| `timbre` | keyboards; in the symphonic branch, orchestral elements | WP Power metal |
| `form` | anthemic choruses | WP Power metal |
| `mix` | heavy and epic in the traditional branch; lighter and uplifting in the symphonic one | WP Power metal |

- **In this skill**: the power-metal row of [rock-and-metal.md](rock-and-metal.md); the orchestra row for the
  symphonic branch.
- **Variants**:
  - *Symphonic metal*: symphonic instruments, choirs, sometimes a full orchestra, or keyboards emulating one; songs
    shaped by orchestral structures; classically trained voices (WP Symphonic metal). `vsco_strings`, `vsco` brass,
    `vocal_ah`, timpani ([orchestration.md](orchestration.md)).
  - *Melodic death metal*: harmonised guitar riffs as the melody, fast double kick, occasional blast beats
    (rock-and-metal.md, WP Melodic death metal).
- **Neighbours**: Heavy metal; `orchestral/cinematic`.

## Extreme metal

Death and black metal: low-tuned or icy guitars in tremolo picking, blast beats and double kick, minor keys,
chromaticism or dissonance, growled or shrieked vocals. `rock/extreme-metal`

| Axis | Traits | From |
|---|---|---|
| `tempo` | fast, black metal's tempos sometimes near 300 BPM; abrupt changes of tempo, key and meter in death metal | WP Death metal; WP Black metal |
| `harmony` | minor keys or atonality; chromatic chord progressions; in black metal, dissonance, scales and intervals chosen for dread | WP Death metal; WP Black metal |
| `melody` | growled (death) or shrieked (black) vocals | WP Death metal; WP Black metal |
| `rhythm` | blast beats and double kick; tremolo picking and palm muting | WP Death metal; WP Black metal |
| `timbre` | heavily distorted, low-tuned guitars (death); heavily distorted guitars playing power chords and tremolo picking with the strings unmuted, the bass following the riff (black); keyboards in some | WP Death metal; WP Black metal |
| `form` | unconventional song structures (black) | WP Black metal |
| `mix` | raw, lo-fi recording in black metal; an emphasis on atmosphere | WP Black metal |

- **In this skill**: the blast beat and the double kick on `rusty` ([rock-and-metal.md](rock-and-metal.md), Metal
  figures); tremolo picking as fast repeated sixteenths or thirty-seconds on the distorted banks; the banks reach
  B1, so lower tunings cannot be played. No growled or shrieked voice: a lead or the riffs carry the line.
- **Variants**: *Technical death metal*: uncommon meters, atypical rhythms, unusual harmonies and melodies (WP Death
  metal).
- **Neighbours**: Thrash; Doom (death-doom); the Horror map (`horror/shrieking-strings`) for dread without guitars.

## Doom

Slow, low and thick: guitars tuned down and heavily distorted, the bass in unison with them, on repetitive riffs in
minor, with the tritone. `rock/doom`

| Axis | Traits | From |
|---|---|---|
| `tempo` | slow tempos throughout | WP Doom metal |
| `harmony` | minor tonality, much dissonance, the tritone above all; harmonic progression counts for little | WP Doom metal |
| `melody` | clean vocals sung with despair in the traditional style | WP Doom metal |
| `rhythm` | repetitive rhythms | WP Doom metal |
| `timbre` | guitars and bass tuned down, with much distortion: a thick, heavy tone; guitars and bass on the same riff | WP Doom metal |
| `form` | little regard to musical structure | WP Doom metal |
| `mix` | a wall of sound, loud and heavy in the bass | WP Doom metal |

- **In this skill**: the distorted banks at their lowest (B1) with `bass_darkblack`'s low B; slow tempos; long notes
  that ring under `reverb_db`. `review` does not ask about a part's loop here: rhythms that repeat, with little attention
  to harmonic progression or to structure, are the style (WP Doom metal).
- **Neighbours**: Heavy metal; Extreme metal; `horror/drone-dread`.

## Metalcore

Heavy metal with hardcore punk: aggressive verses, melodic choruses and half-time breakdowns of low-tuned,
percussive chugs. `rock/metalcore`

| Axis | Traits | From |
|---|---|---|
| `tempo` | breakdowns slow and intense | WP Metalcore |
| `harmony` | low-tuned power chords and open-string chugs | WP Metalcore; rock-and-metal.md |
| `melody` | melodic choruses; clean singing against harsh shouting and screaming | WP Metalcore |
| `rhythm` | double kick; in breakdowns a half-time snare with the kick in unison with the chugs | WP Metalcore; rock-and-metal.md |
| `timbre` | guitar riffs tuned low and played percussively | WP Metalcore |
| `form` | aggressive verse, melodic chorus, the breakdown as a section of its own | WP Metalcore; Gamble 2019 |
| `mix` | a highly produced sound | WP Metalcore |

- **In this skill**: the metalcore row and the breakdown of [rock-and-metal.md](rock-and-metal.md).
- **Variants**: *Djent*: a progressive-metal style named for the onomatopoeia of its guitar sound (WP Djent); riffs
  in groups of 5 or 7 sixteenths over a steady 4/4 kept by the hats and snare (Pieslak 2007, on the band that named
  it; rock-and-metal.md, Form).
- **Neighbours**: Punk; Nu metal; Heavy metal.

## Nu metal

Down-tuned, heavily syncopated riffs on seven-string guitars, hip-hop rhythms and voices, rarely a solo.
`rock/nu-metal`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | down-tuned seven-string guitars for a heavier sound | WP Nu metal |
| `melody` | rhythmic vocals from hip-hop: singing, rapping, screaming; rarely guitar solos | WP Nu metal |
| `rhythm` | the instrumentation heavily syncopated; rhythm over technique | WP Nu metal |
| `timbre` | seven-string guitars; at times a DJ's samples, scratching and electronic backgrounds | WP Nu metal |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: the distorted banks down to B1, the seven-string's low B; syncopated riffs with the kick;
  `drum_synth` or Surge textures for the electronic layer. No scratching: the banks hold no turntable.
- **Neighbours**: Metalcore; Alternative and indie; [beats.md](beats.md) for the hip-hop side.

## Sources

- Nieto, O., McCallum, M., Davies, M. E. P., Robertson, A., Stark, A. and Egozy, E. (2019). [The Harmonix Set: Beats,
  Downbeats, and Functional Segment Annotations of Western Popular Music](https://archives.ismir.net/ismir2019/paper/000068.pdf).
  *Proceedings of ISMIR 2019*, 565–572: 912 full tracks annotated by professional musicians, chosen for rhythm
  games with a lean toward EDM and danceable pop; the annotations under the MIT licence. The tempos and section
  lengths by the set's genre labels are measured here: the metadata's BPM, and the downbeats from each section's
  start to the next.
- Osborn, B. (2011). [Understanding Through-Composition in Post-Rock, Math-Metal, and other Post-Millennial Rock
  Genres](https://www.mtosmt.org/issues/mto.11.17.3/mto.11.17.3.osborn.php). *Music Theory Online* 17(3).
- The sources of [rock-and-metal.md](rock-and-metal.md): Biamonte (2010), de Clercq and Temperley (2011), Frühauf,
  Kopiez and Platz (2013), Gamble (2019), Herbst (2018, 2019), Lilja (2015), Mynett (2017), Pieslak (2007), Temperley
  (2007), Open Music Theory, and Wikipedia read 6 November 2026.
- Tan, I., Lustig, E. and Temperley, D. (2019); Summach, J. (2011): in [anime-opening.md](anime-opening.md).
- Wikipedia, read 9 November 2026: [Hard rock](https://en.wikipedia.org/wiki/Hard_rock),
  [Blues rock](https://en.wikipedia.org/wiki/Blues_rock), [Punk rock](https://en.wikipedia.org/wiki/Punk_rock),
  [Pop-punk](https://en.wikipedia.org/wiki/Pop-punk), [Alternative rock](https://en.wikipedia.org/wiki/Alternative_rock),
  [Indie rock](https://en.wikipedia.org/wiki/Indie_rock), [Grunge](https://en.wikipedia.org/wiki/Grunge),
  [Shoegaze](https://en.wikipedia.org/wiki/Shoegaze), [Dream pop](https://en.wikipedia.org/wiki/Dream_pop),
  [Post-rock](https://en.wikipedia.org/wiki/Post-rock), [Progressive rock](https://en.wikipedia.org/wiki/Progressive_rock),
  [Math rock](https://en.wikipedia.org/wiki/Math_rock), [Surf music](https://en.wikipedia.org/wiki/Surf_music),
  [Heavy metal music](https://en.wikipedia.org/wiki/Heavy_metal_music),
  [Thrash metal](https://en.wikipedia.org/wiki/Thrash_metal), [Power metal](https://en.wikipedia.org/wiki/Power_metal),
  [Symphonic metal](https://en.wikipedia.org/wiki/Symphonic_metal), [Death metal](https://en.wikipedia.org/wiki/Death_metal),
  [Black metal](https://en.wikipedia.org/wiki/Black_metal), [Doom metal](https://en.wikipedia.org/wiki/Doom_metal),
  [Metalcore](https://en.wikipedia.org/wiki/Metalcore), [Djent](https://en.wikipedia.org/wiki/Djent),
  [Nu metal](https://en.wikipedia.org/wiki/Nu_metal).
