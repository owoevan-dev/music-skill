# Style map: jazz, blues, funk and soul

The African-American traditions of the swing band and the jazz combo, the blues, funk and soul. Read
[style-maps.md](style-maps.md) first for the axes and for combining entries; the craft is in
[jazz-and-funk.md](jazz-and-funk.md) (swing and time, the rhythm section, heads and solos, funk, the blues, bossa
nova). Latin and Caribbean styles are in [style-map-latin.md](style-map-latin.md).

Contents: [Shared by the family](#shared-by-the-family) · [Swing and big band](#swing-and-big-band) ·
[Modern jazz combo](#modern-jazz-combo) · [Modal jazz](#modal-jazz) · [Jazz fusion](#jazz-fusion) ·
[Smooth jazz](#smooth-jazz) · [Gypsy jazz](#gypsy-jazz) · [Blues](#blues) · [Funk](#funk) · [Soul](#soul) ·
[Sources](#sources)

Source tags: WP is Wikipedia, by article, read on 9 November 2026 (and on 6 November for the articles in
[jazz-and-funk.md](jazz-and-funk.md)); WJD is the Weimar Jazz Database as measured in *Inside the Jazzomat*
(Pfleiderer et al. 2017): 456 transcribed solos, 1416 choruses, 121 features each.

## Shared by the family

- **Swing and time.** The ride's swing ratio falls as the tempo rises, from about 3.5:1 at slow tempi to nearly even
  near 300 BPM, the short note staying near 100 ms; soloists land their downbeats after the ride and meet it on the
  off-beats (Friberg and Sundström 2002). [jazz-and-funk.md](jazz-and-funk.md) turns this into `performance.swing`
  settings.
- **What the solos show** (WJD, Pfleiderer and Abeßer 2017): the improvisations of bebop, cool and hard bop cannot
  be told apart statistically, the core of jazz improvisation; the styles beyond it differ most in rhythm and
  duration, not in pitch and harmony. The tempos of the database run from 50 to over 300 BPM, median 170.5; about 80%
  of its solos swing, the rest are Latin, funk and others.
- **Solos are written.** Nothing improvises here: a solo is written to sound improvised
  ([jazz-and-funk.md](jazz-and-funk.md), Writing the head and the solos).
- **The spectrum.** Number ones tagged jazz have the steepest slope of the genres Pestana et al. (2013) measured, −1.29
  over 100 Hz–10 kHz, and soul −1.03 (the `soul` entry's reference): acoustic music shows "a natural top-end decay",
  in their words. `analyze` sets the master beside it ([performance-and-mix.md](performance-and-mix.md), Brightness
  and air).

For the family, `review` keeps the defaults: its questions on outside notes ask for colour tones in the chord symbol,
as jazz harmony writes them, and bebop's complex syncopation (WP Bebop) keeps the question on pushes. Funk does not
ask about a part's loop (below).

## Swing and big band

Dance music of written arrangements for sections of saxophones, trumpets and trombones over a four-piece rhythm
section, with soloists. `jazz/swing`

| Axis | Traits | From |
|---|---|---|
| `tempo` | dance tempos; swung eighths, the ratio falling as the tempo rises | WP Swing music; Friberg and Sundström 2002 |
| `harmony` | written arrangements; call and response between the brass and the reeds; interludes arranged behind soloists | WP Swing music |
| `melody` | soloists who vary the tune by improvising above the arranged parts; swing solos play "slower" lines than the rest of the database, more eighths and fewer sixteenths, as traditional jazz does | WP Swing music; WJD |
| `rhythm` | rhythm that runs smoother than in the ragtime-influenced dance music before it | WP Swing music |
| `timbre` | ten or more players: a rhythm section (piano, guitar, double bass, drums) under three sections of winds (saxophones, trumpets, trombones) | WP Big band |
| `form` | written compositions and arrangements rather than improvisation; the bandleader, the arranger and the sections over the soloists | WP Big band |
| `mix` | no source read | |

- **In this skill**: the horns of [jazz-and-funk.md](jazz-and-funk.md) (`vcsl_winds` tenor sax, `sax_bear`, `vsco`
  trumpet and trombone, `vsco_extra`), the shout chorus voicings, the swing settings, `bass_sneaky`, `rusty` at low
  velocities, `guitar_shiny` for the rhythm guitar.
- **Neighbours**: Modern jazz combo; Gypsy jazz; Blues (jump blues).

## Modern jazz combo

Bebop, cool and hard bop: a small combo plays the head, solos over its changes, and the head again.
`jazz/modern-combo`

| Axis | Traits | From |
|---|---|---|
| `tempo` | bebop fast, not meant for dancing; cool jazz relaxed and moderate | WP Bebop; WP Cool jazz |
| `harmony` | bebop: complex, fast-moving progressions, quick changes of chord and of key, substitutions, altered and extended chords | WP Bebop |
| `melody` | angular melodies; virtuosic improvisation on harmony, scales and the melody; asymmetrical phrasing | WP Bebop |
| `rhythm` | complex syncopation; the rhythm section's role expanded | WP Bebop |
| `timbre` | trumpet and an alto or tenor saxophone, with a rhythm section of double bass, drums, piano and guitar | WP Bebop |
| `form` | the head with the rhythm section, a solo by each player, the head again | WP Bebop |
| `mix` | no source read | |

- **In this skill**: [jazz-and-funk.md](jazz-and-funk.md): the walking bass, rootless piano voicings, guitar comping,
  the ride pattern, heads and written solos.
- **Variants**:
  - *Cool jazz*: unhurried tempos, a lighter tone, formal arrangements, elements of classical music, a subdued,
    reflective approach (WP Cool jazz).
  - *Hard bop*: rhythm and blues, gospel and blues in the saxophone and the piano; "funky", a rollicking rhythmic
    feel (WP Hard bop).
- **Neighbours**: Swing and big band; Modal jazz; the J-pop map's city pop for its chords (`jpop/city-pop`).

## Modal jazz

Few chords held long, the soloist moving among modes over them instead of following a tonal center through fast
changes. `jazz/modal`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | modes, with frequent moves from one mode to another, in place of one tonal center; a theme's chords repeated through the piece under new improvised themes | WP Modal jazz |
| `melody` | in 102 modal choruses: a wider interval range (29.5 semitones against 21.1) and larger intervals; the blue minor third over major chords (0.8% against 3.6%) and the major third over minor ones avoided; more very short durations | WJD (Pfleiderer and Abeßer 2017, Table 2) |
| `rhythm` | more very short durations than short ones, as in post-bop at large | WJD |
| `timbre` | no source read | |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: chords held for several bars in the comping, a Dorian or other mode written into the chord
  symbol's colour tones; quartal or rootless voicings ([jazz-and-funk.md](jazz-and-funk.md)).
- **Neighbours**: Modern jazz combo; Jazz fusion (vamps on one chord).

## Jazz fusion

The harmony and improvisation of jazz joined to rock, funk and R&B on electric instruments: vamps on one chord, or
elaborate progressions in unusual meters. `jazz/fusion`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | jazz harmony; groove vamps on one key or chord, or elaborate progressions | WP Jazz fusion |
| `melody` | a simple repeated melody over a vamp, or a melody set against counter-melodies | WP Jazz fusion |
| `rhythm` | rock and funk grooves; unconventional time signatures in some | WP Jazz fusion |
| `timbre` | electric guitars and basses, electric pianos, organs, synthesizers; the acoustic piano and the double bass less often | WP Jazz fusion |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: `fsbs_clean` and the distorted banks, `bass_darkblack`, Surge electric pianos, organs and leads,
  `rusty`; `blocks.drums` in the `funk` or `rock` feel; meters other than 4/4 in the clock.
- **Neighbours**: Funk; Modal jazz; `rock/progressive`.

## Smooth jazz

Downtempo, radio-friendly jazz: a saxophone or a gentle electric guitar over programmed rhythms and pads.
`jazz/smooth`

| Axis | Traits | From |
|---|---|---|
| `tempo` | downtempo; 90–105 BPM in the tracks played most | WP Smooth jazz |
| `harmony` | influences of pop, rock, funk and R&B | WP Smooth jazz |
| `melody` | a lead, the saxophone (soprano and tenor most of all) or a guitar | WP Smooth jazz |
| `rhythm` | programmed rhythms | WP Smooth jazz |
| `timbre` | the saxophone; an electric guitar played gently and legato; pads and samples behind | WP Smooth jazz |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: `vcsl_winds` tenor sax with vibrato and `performance.legato`, `guitar_shiny`, Surge pads or an
  electric piano for the chords ([sound-selection.md](sound-selection.md), Electric pianos), `drum_synth` or
  `blocks.drums` with `programmed=True`.
- **Neighbours**: Soul; `jpop/city-pop`; `beats/lo-fi`.

## Gypsy jazz

Swing on acoustic strings: lead guitar and violin over a rhythm guitar's percussive "la pompe", which takes the
drums' place, and the double bass. `jazz/gypsy`

| Axis | Traits | From |
|---|---|---|
| `tempo` | swing | WP Gypsy jazz |
| `harmony` | no source read | |
| `melody` | lead guitar and violin | WP Gypsy jazz |
| `rhythm` | the rhythm guitar's "la pompe", a percussive strum that replaces the drums | WP Gypsy jazz |
| `timbre` | acoustic guitars, violin, double bass | WP Gypsy jazz |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: the solo violin (`vsco` 0:40, `iowa_strings`), `guitar_shiny` (microphone preset 0:25) for both
  guitars, `bass_sneaky`; no drums. The pompe: `blocks.accompaniment` with `figure='pompe'`, a short chord on every
  beat, 2 and 4 slightly stressed, a quick upstroke before 1 and 3 ([building-blocks.md](building-blocks.md), after
  Persinger 2014).
- **Neighbours**: Swing and big band.

## Blues

The twelve-bar sequence, AAB lines answered by an instrument, blue notes against the chords' major thirds, a shuffle
or a walking bass. `jazz/blues`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read; a slow blues is written in 12/8 here ([jazz-and-funk.md](jazz-and-funk.md)) | |
| `harmony` | the twelve-bar sequence of dominant sevenths, I–IV–I–V–IV–I, with a turnaround; eight- and sixteen-bar forms; the minor blues | WP Twelve-bar blues; WP Blues |
| `melody` | the blues scale over major chords; blue notes, lower than expected, the third, then the seventh, the fifth and the sixth; AAB lines; in the WJD, blues tonality uses smaller intervals | WP Blues; van der Merwe 1989 (in WP Blue note); Weisethaunet 2001; WJD |
| `rhythm` | shuffles, swung eighths; the backbeat on 2 and 4 | WP Blues |
| `timbre` | guitar and harmonica in the Delta; electric guitar, amplified harmonica, drums, bass and piano in Chicago | WP Delta blues; WP Chicago blues |
| `form` | call and response between the voice and the instruments | WP Blues |
| `mix` | no source read | |

- **In this skill**: [jazz-and-funk.md](jazz-and-funk.md), Blues: the forms, the bends and curls, the shuffle, the
  boogie-woogie left hand, the instruments.
- **Variants**:
  - *Delta blues*: guitar and harmonica dominant, slide guitar its hallmark (WP Delta blues).
  - *Chicago blues*: a solid-body electric guitar and a harmonica played through amplifiers, loud enough to
    distort, over weighty drums and bass, with piano in some songs (WP Chicago blues).
- **Neighbours**: `rock/classic-hard` (blues rock); Swing and big band (jump blues); Soul.

## Funk

A groove of interlocking parts on the One: the bass and drums in front, swung sixteenths and syncopation in the bass,
drums and guitar, melody and chord progressions in the background. `jazz/funk`

| Axis | Traits | From |
|---|---|---|
| `tempo` | often slower than other popular music | WP Funk |
| `harmony` | chord progressions de-emphasised | WP Funk |
| `melody` | melody de-emphasised | WP Funk |
| `rhythm` | the downbeat emphasised, "the One"; swung sixteenths and syncopation in every bassline, drum pattern and guitar riff; interlocking grooves, "hypnotic" and danceable | WP Funk |
| `timbre` | electric bass and drums in front; rhythm guitar; horns | WP Funk |
| `form` | one repeats "an internal difference": each part answers the others, every time the same | Danielsen 2006, quoted by Christodoulou 2020 |
| `mix` | no source read | |

- **In this skill**: [jazz-and-funk.md](jazz-and-funk.md), Funk; `blocks.drums` in the `funk` feel and the bass and
  comping blocks ([building-blocks.md](building-blocks.md)). `review` does not ask about a part's loop here: each part
  repeating its figure is the groove (Danielsen 2006, quoted by Christodoulou 2020).
- **Variants**: *Afrobeat*: Yoruba music and Ghanaian highlife joined to funk, jazz and soul from America; vocals
  that are chanted, rhythms that cross one another in complex ways, and percussion (WP Afrobeat): the `vcsl_world`
  agogo, shakers and congas over the funk groove. City pop is in the J-pop map (`jpop/city-pop`).
- **Neighbours**: Soul; Jazz fusion; `beats/g-funk`; `pop/disco`.

## Soul

Gospel and rhythm and blues brought together: rhythms that catch the ear, underlined by handclaps, and a lead voice answered
by the backing voices. `jazz/soul`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | drawn from jazz, gospel and R&B | WP Soul music |
| `melody` | the lead singer and the backing singers in call and response; a tense vocal sound; improvised additions | WP Soul music |
| `rhythm` | rhythms that catch the ear, underlined by handclaps | WP Soul music |
| `timbre` | no source read | |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: a lead instrument for the singer and a second for the answers; the clap (39) of `drum_synth` or
  the `vcsl_world` claps; `blocks.drums` in the `soul` feel; a Surge organ, the pianos or an electric piano
  ([sound-selection.md](sound-selection.md), Electric pianos), `vsco` horns.
- **Variants**: *Neo soul*: less conventional than contemporary R&B, drawing on hip-hop, rock, funk and jazz fusion, with
  live instruments rather than samples (WP Neo soul).
- **Neighbours**: Funk; Blues; `pop/ballad`.

## Sources

- Christodoulou, C. (2020), quoting Danielsen, A. (2006, *Presence and Pleasure*, p. 164): in
  [style-map-electronic.md](style-map-electronic.md).
- Friberg, A. and Sundström, A. (2002); Weisethaunet, H. (2001); van der Merwe, P. (1989): in
  [jazz-and-funk.md](jazz-and-funk.md).
- Pfleiderer, M., Frieler, K., Abeßer, J., Zaddach, W.-G. and Burkhart, B. (eds.) (2017). [*Inside the Jazzomat: New
  Perspectives for Jazz Research*](https://schott-campus.com/jazzomat/). Schott Campus, CC BY-NC-ND 4.0. In it:
  Pfleiderer, M., The Weimar Jazz Database; Pfleiderer, M. and Abeßer, J., Statistical feature selection: searching
  for musical style.
- Wikipedia, read 9 November 2026: [Swing music](https://en.wikipedia.org/wiki/Swing_music),
  [Big band](https://en.wikipedia.org/wiki/Big_band), [Bebop](https://en.wikipedia.org/wiki/Bebop),
  [Cool jazz](https://en.wikipedia.org/wiki/Cool_jazz), [Hard bop](https://en.wikipedia.org/wiki/Hard_bop),
  [Modal jazz](https://en.wikipedia.org/wiki/Modal_jazz), [Jazz fusion](https://en.wikipedia.org/wiki/Jazz_fusion),
  [Smooth jazz](https://en.wikipedia.org/wiki/Smooth_jazz), [Gypsy jazz](https://en.wikipedia.org/wiki/Gypsy_jazz),
  [Delta blues](https://en.wikipedia.org/wiki/Delta_blues), [Chicago blues](https://en.wikipedia.org/wiki/Chicago_blues),
  [Funk](https://en.wikipedia.org/wiki/Funk), [Soul music](https://en.wikipedia.org/wiki/Soul_music),
  [Neo soul](https://en.wikipedia.org/wiki/Neo_soul), [Afrobeat](https://en.wikipedia.org/wiki/Afrobeat); read 6 November: [Blues](https://en.wikipedia.org/wiki/Blues),
  [Twelve-bar blues](https://en.wikipedia.org/wiki/Twelve-bar_blues).
