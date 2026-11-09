# Style map: J-pop and anime songs

Japanese popular music as its literature describes it: the anime opening, fast electronic J-pop, idol group songs,
city pop and enka. The skill is instrumental, so in every entry an instrument carries the singer's line. Read
[style-maps.md](style-maps.md) first for the axes and for combining entries; the craft is in
[anime-opening.md](anime-opening.md) (form, harmony, the instrumental lead, the band), with
[pop-and-ballad.md](pop-and-ballad.md), [electronic.md](electronic.md) and [jazz-and-funk.md](jazz-and-funk.md).

Contents: [Shared by the family](#shared-by-the-family) · [Anime opening](#anime-opening) ·
[Fast electro J-pop](#fast-electro-j-pop) · [Idol pop](#idol-pop) · [City pop](#city-pop) ·
[Enka](#enka) · [Not entries](#not-entries) · [Sources](#sources)

Source tags: WP is Wikipedia, read on 9 November 2026, by article. The other sources are by author and year.

## Shared by the family

- **Sections.** Japanese songwriting names the verse A-melo, the prechorus B-melo and the chorus sabi. A song turns
  through intro, verse, prechorus and chorus; the full-length song is a compound AABA′ form, of which a TV opening is
  one A rotation (Li 2026, after Covach 2005).
- **Chords.** In the archetypal anime song Li (2026) describes, I, IV, V and vi, with ii and iii, carry the structure,
  and chromatic chords such as ♭VII and V/ii come sparingly. The progressions frequent in J-pop, by the names
  Japanese pop gives them (Uehara, Itoh and Takatsuka 2016, Table 1):

  | Name | Progression |
  |---|---|
  | three chords | I–IV–V |
  | the J-pop progression, the royal road | IV–V7–iii–vi |
  | a producer's progression, and its minor form | vi–IV–V–I; vi–ii–V–vi |
  | a 1980s hit's progression | I–vi–IV–V7 |
  | the Eurobeat progression | IV–V–vi–vi |
  | one-six-two-five | I–vi–ii–V7 |
  | the progression of rising expectation | vi–iii–IV–V7 |
  | the canon progression | I–V–vi–iii–IV–I–IV–V |

  The royal road is usually all sevenths, IVM7–V7–iii7–vi(7), and resolves by IVM7–V7–I or ii7–V7–I; after vi,
  ii7–V7–I completes a circle of fifths. In minor its forms are VIM7–VII7–v7–i and iv7–v7–IIIM7–VI (WP Royal road
  progression). Two of the table's names are a producer's and a song's; they are given here by description.
- **Colour.** J-pop progressions often carry tensions and slash chords (Uehara, Itoh and Takatsuka 2016). Across
  2,419 songs from 1927 to 2019, the chords J-pop uses grew more varied, most between the 1970s and the mid-1990s; the
  authors leave open how much the make-up of the data adds (Moss and Nakamura 2024). Relative major and minor keys
  are often interchanged, which Ramage (2023) reads as a binary tonal system (Li 2026).
- **Modulation by a minor third.** 41% of the anime openings Li (2026) surveyed modulated; 38 of the 72 modulations
  moved a minor third, 33 of the 72 at the prechorus–chorus boundary, prepared by ♭VII, V or III
  ([anime-opening.md](anime-opening.md), Harmony).
- **Scales.** Japanese pop moved from melodies on the Japanese pentatonic scale toward Western ones (WP J-pop); enka
  keeps the yonanuki scales (below).
- **The spectrum.** No spectrum of J-pop was read. `analyze` borrows the nearest published measurement, US and
  UK number ones tagged pop, −0.94 on Pestana et al. (2013)'s log-log slope over 100 Hz–10 kHz, and says it is borrowed
  ([performance-and-mix.md](performance-and-mix.md), Brightness and air).

For the family, `review` keeps every default, the question on pushes included: the instrumental lead takes the place
of a pop vocal, and rock and pop melodies anticipate strong beats (Tan, Lustig and Temperley 2019).

## Anime opening

A band cue of about ninety seconds: one rotation of intro, verse, prechorus and chorus, a hook that lifts, often a
modulation into the chorus. `jpop/anime-opening`

| Axis | Traits | From |
|---|---|---|
| `tempo` | from the anime: the style, the instrumentation and the tempo of an opening tend to reflect the anime's genre; openings with a postchorus have a median tempo over 20 BPM faster than those without | Li 2026 |
| `harmony` | the family's chords and progressions; the royal road, widely described as the typical chorus progression; a modulation by a minor third at the prechorus–chorus boundary | Li 2026; Ramage 2023; WP Royal road progression |
| `melody` | singable, mostly by step with leaps for character; a chorus higher or denser than the verse | Perricone 2000; Summach 2012 (in anime-opening.md) |
| `rhythm` | a backbeat, half time and double time the common alternatives; moderate syncopation | OMT, Drumbeats; Witek et al. 2014 (in anime-opening.md) |
| `timbre` | as the anime's genre asks; in a band, distorted guitars on power chords, whose distortion gives the chords a major quality | Li 2026; Lilja 2015 |
| `form` | 92.6% of 108 openings surveyed: one intro–verse–prechorus–chorus rotation of about 90 s; verse and chorus closing on authentic cadences, the prechorus on a half cadence; the chorus slightly longer than the verse, the prechorus shortest; 61% without a postchorus | Li 2026 |
| `mix` | no source read; this skill delivers at −14 LUFS ([anime-opening.md](anime-opening.md), The mix) | |

- **In this skill**: [anime-opening.md](anime-opening.md): the TV-size layout, the build, the royal road and the
  minor-third modulations, the melody for an instrumental lead, the band, the arrangement and the mix.
- **Variants**:
  - *Full size*: the compound AABA′ of two rotations with a bridge, the postchorus doubling as the second rotation's
    intro (Li 2026).
  - *Orchestral or electronic openings*: the instrumentation follows the anime (Li 2026): borrow `timbre` from
    `orchestral/cinematic` or an electronic entry.
- **Neighbours**: Fast electro J-pop; rock and metal ([rock-and-metal.md](rock-and-metal.md)).

## Fast electro J-pop

Fast, dense electronic J-pop: many notes and chord changes a bar, rhythm to the fore, the vocal line on a lead.
`jpop/fast-electro`

| Axis | Traits | From |
|---|---|---|
| `tempo` | fast, but denser more than faster: in the 100 most popular songs of each year from 2007 to 2025 made with one singing synthesizer, tempo rose 2.3% and onset density 6.4% | Lau 2026 |
| `harmony` | a faster rate of harmonic change (+8.0% there); the family's progressions and modulations | Lau 2026; Li 2026 |
| `melody` | dense; songs that stick in the mind have common overall contours with less common intervals inside them, and faster tempi | Lau 2026; Jakubowski et al. 2017 |
| `rhythm` | more complex rhythm (+9.1%) | Lau 2026 |
| `timbre` | no source read; the electronic entries' sounds | |
| `form` | shorter songs (−6.8%, most after 2020); an opening's about 90 s | Lau 2026; Li 2026 |
| `mix` | no source read; the electronic entries' production | |

- **In this skill**: the drums, the pumping and the risers of [electronic.md](electronic.md) and their sounds in
  [electronic-sounds.md](electronic-sounds.md); a piano or a synth lead in the singer's place
  ([anime-opening.md](anime-opening.md), Melody for an instrumental lead). Its rhythm and mix are best borrowed from an
  electronic entry, the reason in `decisions`: `{"primary": "jpop/fast-electro", "borrow": {"rhythm":
  "electronic/drum-and-bass", "mix": "electronic/future-bass"}}`. Lau's figures were read in the abstract only, so
  only their direction is used.
- **Variants**: *cute*: the kawaii variant of future bass, chiptune sounds and soft square waves
  (`electronic/future-bass`).
- **Neighbours**: Anime opening; `electronic/future-bass`; `electronic/eurobeat`.

## Idol pop

Songs for idol groups: lines divided among the members, solo against unison, with countermelodies, harmonies and
choral parts over arrangements of many instruments, mastered loud, in any of many styles. `jpop/idol-pop`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read on real idol songs; the corpus's fifteen commissioned songs run 78–190 BPM | Suda et al. 2025 |
| `harmony` | various chord progressions; harmonies and choral sections ("oohs" and "ahhs"), characteristic of J-pop | Suda et al. 2025 |
| `melody` | song division (utawari): the members take turns line by line, some sections solo, others sung together; countermelodies | Suda et al. 2025 |
| `rhythm` | no source read | |
| `timbre` | numerous instruments; a wide range of styles, pop, UK garage, ballads, rock and dance among them: the accompaniments of 4,483 songs by 234 groups formed no distinct clusters | Suda et al. 2025 |
| `form` | no source read beyond the song division | |
| `mix` | complex mastering and high loudness: commercial idol songs near −7 LUFS, some creators releasing quieter versions for streaming (the corpus's at −9) | Suda et al. 2025 |

- **In this skill**: the song division as the line handed between two or three lead timbres phrase by phrase, each
  with `performance.legato`, and the group lines doubled in unison or octaves; choral "ah" on `vocal_ah` (a low
  voice). No calls or chants: there are no such voices. `mix.loudness: "loud"` keeps the true peak under −2 dBTP and
  so stops short of −7 LUFS ([performance-and-mix.md](performance-and-mix.md)). The style itself is borrowed from the
  entry it takes: an idol song in UK garage is `{"primary": "jpop/idol-pop", "borrow": {"rhythm":
  "electronic/uk-garage"}}`.
- **Neighbours**: Anime opening; Fast electro J-pop.

## City pop

Japanese pop of the late 1970s and 1980s with an urban, sophisticated sound: the chords of jazz and soft rock over
funk, disco and boogie grooves, sometimes tropical. `jpop/city-pop`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | jazz techniques of writing and arranging, major-seventh and diminished chords, taken from 1970s American soft rock | WP City pop |
| `melody` | no source read | |
| `rhythm` | funk, disco, R&B and boogie; of its two styles, one "a thumping rug-cutter" | WP City pop |
| `timbre` | soft rock and AOR; tropical touches and borrowings from jazz fusion and from Okinawan, Latin and Caribbean music; the other style "a lush, tropical romp" | WP City pop |
| `form` | no source read | |
| `mix` | an urban, sophisticated atmosphere | WP City pop |

- **In this skill**: [jazz-and-funk.md](jazz-and-funk.md), Funk and pop-funk: sevenths and ninths, a melodic
  electric bass, strings or synth brass, a vocal-like lead (this skill's practice); `bass_darkblack`; electric pianos
  (`studio.py sounds --name ep`, `--name rhodes`); `vsco` brass; for the tropical side the `steel_drum` and the
  `vcsl_world` percussion; `blocks.drums` in the `soul` or `funk` feel.
- **Neighbours**: `electronic/synthwave` (the 1980s by way of film); the jazz and funk map.

## Enka

The sentimental ballad of postwar Japan: melodies on the yonanuki scales, sung with kobushi, over Western harmony.
`jpop/enka`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | Western harmony under the melody | WP Enka |
| `melody` | the yonanuki minor scale, the minor scale without its fourth and seventh, derived from the yonanuki major, the major without its fourth and seventh, after the older ryo scale; kobushi, a melisma in which the pitch fluctuates irregularly within one scale degree, unlike the regular cycle of vibrato | WP Enka |
| `rhythm` | no source read | |
| `timbre` | synthesizers and a distorted electric lead guitar; the shakuhachi and the shamisen | WP Enka |
| `form` | the sentimental ballad | WP Enka |
| `mix` | no source read | |

- **In this skill**: the yonanuki minor written by hand (on A: A, B, C, E, F) and the major (on C: C, D, E, G, A);
  kobushi as an irregular `bend` around one held pitch (this skill's approximation; its depth and rate are not
  measured) on the erhu, a violin, the saxophone or the distorted guitar. No shakuhachi or shamisen in the banks.
- **Neighbours**: the pop ballad ([pop-and-ballad.md](pop-and-ballad.md)).

## Not entries

Two requests have no entry, as no source read describes their traits ([style-maps.md](style-maps.md), When a
sub-style is an entry of its own).

- **A J-pop ballad.** Take the pop ballad as the primary and borrow the harmony from the anime opening, the reason
  in `decisions`: the family's progressions, the royal road among them, under the ballad's slow tempo, lush
  arrangement and voice-like lead. The ballad's verse, prechorus and chorus are already the family's A-melo, B-melo
  and sabi.

  ```json
  "style": {"primary": "pop/ballad", "borrow": {"harmony": "jpop/anime-opening"}}
  ```

  The borrowed axis brings the openings' modulation too, a trait of openings to take or leave: 41% of those Li (2026)
  surveyed modulated, 38 of their 72 modulations by a minor third.
- **The anime underscore**, the background music under an anime's scenes. The sources read describe anime songs, the
  theme, insert and image songs (WP Anime song), not the underscore. Write it as music for a scene
  ([film-score.md](film-score.md), [scene-music.md](scene-music.md)) in the style of the entry nearest the brief.

## Sources

- Covach, J. (2005), cited by Li (2026), for compound AABA′ form.
- Jakubowski, K., Finkel, S., Stewart, L. and Müllensiefen, D. (2017). Dissecting an earworm: melodic features and
  song popularity predict involuntary musical imagery. *Psychology of Aesthetics, Creativity, and the Arts* 11(2),
  122–135. Read in the abstract and the university's summary.
- Lau, K. (2026). Are Vocaloid songs getting denser? IPSJ SIG Technical Report 2026-MUS-146. Read in the abstract
  and a summary; the full text is paid until 2028.
- Li, J. (2026). [Modulation and Chromatic Mediants in Japanese Anime Songs](https://mtosmt.org/issues/mto.26.32.1/mto.26.32.1.li.php).
  *Music Theory Online* 32(1). doi:10.30535/mto.32.1.6
- Moss, F. C. and Nakamura, E. (2024). [Modeling the Evolution of Harmony in Popular Music from Different Cultural
  Contexts](https://ceur-ws.org/Vol-3834/paper133.pdf). *Proceedings of the Computational Humanities Research
  Conference* (CEUR Workshop Proceedings 3834).
- Ramage, M. (2023). The Royal Road Progression in Japanese Popular Music. *Music Theory Spectrum* 45(2), 238–256.
  Read in summary and as cited by Li (2026).
- Suda, H. et al. (2025). [IdolSongsJp Corpus: A Multi-Singer Song Corpus in the Style of Japanese Idol Groups](https://arxiv.org/abs/2507.01349).
  ISMIR 2025.
- Uehara, M., Itoh, T. and Takatsuka, M. (2016). [Japanese pop music visualization focused on chord progression
  patterns](https://www.art-science.org/journal/v15n4/v15n4pp177/artsci-v15n4pp177.pdf) (in Japanese). *Transactions
  of the Society for Art and Science* 15(4), 177–184.
- The sources of [anime-opening.md](anime-opening.md): Perricone (2000), Summach (2011, 2012), Tan, Lustig and
  Temperley (2019), Witek et al. (2014), Lilja (2015), Open Music Theory.
- Wikipedia, read 9 November 2026: [J-pop](https://en.wikipedia.org/wiki/J-pop),
  [Royal road progression](https://en.wikipedia.org/wiki/Royal_road_progression),
  [City pop](https://en.wikipedia.org/wiki/City_pop), [Enka](https://en.wikipedia.org/wiki/Enka),
  [Anime song](https://en.wikipedia.org/wiki/Anime_song).
