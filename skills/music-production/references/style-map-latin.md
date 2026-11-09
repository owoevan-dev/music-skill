# Style map: Latin American, Caribbean and Iberian music

Dance and song traditions built on clave, tresillo and their relatives: bossa nova and samba, salsa and Latin jazz,
reggae and ska, reggaeton, tango, cumbia and flamenco. Read [style-maps.md](style-maps.md) first for the axes and for
combining entries; the craft for bossa nova is in [jazz-and-funk.md](jazz-and-funk.md), Bossa nova, and the drum
blocks' Latin feels in [building-blocks.md](building-blocks.md).

Contents: [Shared by the family](#shared-by-the-family) · [Bossa nova](#bossa-nova) · [Samba](#samba) ·
[Salsa](#salsa) · [Reggae](#reggae) · [Calypso and soca](#calypso-and-soca) · [Reggaeton](#reggaeton) ·
[Tango](#tango) · [Cumbia](#cumbia) · [Flamenco](#flamenco) · [Sources](#sources)

Source tags: WP is Wikipedia, by article, read on 9 November 2026 (and on 6 November for the articles in
[jazz-and-funk.md](jazz-and-funk.md)), with the sources it cites.

## Shared by the family

- **Tresillo and clave.** The habanera rhythm, also called tango-congo or tango, can be heard as tresillo with a
  backbeat; tresillo is half a clave (WP Latin jazz). Afro-Cuban music sets its rhythm section on ostinatos or a clave
  (WP Latin jazz).
- **The percussion.** The drummers' statistics hold `afrocuban` and `latin` feels and their shuffles
  ([building-blocks.md](building-blocks.md)); `vcsl_world` holds congas, bongos, cajon, agogo, claves, guiro, shakers
  and cowbells ([soundbanks.md](soundbanks.md)).

For the family, `review` keeps every default: its sources describe syncopated rhythm (WP Bossa nova; WP Samba), and
none describes a looped or static texture as the style.

## Bossa nova

A relaxed samba from Rio: the nylon-string guitar's syncopated beat stylising a samba band, with ambiguous chords and
a soft voice. `latin/bossa-nova`

| Axis | Traits | From |
|---|---|---|
| `tempo` | relaxed | WP Bossa nova |
| `harmony` | unconventional chords, complex progressions, "ambiguous" harmony, which samba guitarists used before jazz | WP Bossa nova |
| `melody` | long notes against the guitar's syncopation, mostly stepwise, at a speaking volume | jazz-and-funk.md (this skill's practice) |
| `rhythm` | a calm, syncopated rhythm: the guitar's chords and fingerstyle mimicking a samba groove, the thumb's bass regular | WP Bossa nova |
| `timbre` | the nylon-string guitar played with the fingers | WP Bossa nova |
| `form` | no source read | |
| `mix` | no source read; intimate and dry here ([jazz-and-funk.md](jazz-and-funk.md)) | |

- **In this skill**: [jazz-and-funk.md](jazz-and-funk.md), Bossa nova: the guitar on `iowa_guitar`, the harmony, the
  kit's surdo and clave, the bass (TalkingBass 2019), the melody, the mix.
- **Neighbours**: Samba; `jazz/modern-combo` (cool jazz); `jpop/city-pop`.

## Samba

Afro-Brazilian rhythms from Bahia and Rio: the urban samba of the samba schools, drummed and syncopated, with longer
notes over a faster beat than the samba-maxixe before it. `latin/samba`

| Axis | Traits | From |
|---|---|---|
| `tempo` | faster than the earlier samba-maxixe | WP Samba |
| `harmony` | no source read | |
| `melody` | longer notes | WP Samba |
| `rhythm` | a more drummed, syncopated style from a new percussive pattern; the samba schools defined its rhythm | WP Samba |
| `timbre` | percussion ensembles of the samba schools | WP Samba |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: the `vcsl_world` percussion and the kit's surdo pattern ([jazz-and-funk.md](jazz-and-funk.md),
  Percussion on a kit); `blocks.drums` in the `latin` feel; the nylon guitar.
- **Neighbours**: Bossa nova (its relaxed stylisation); Salsa.

## Salsa

Son montuno and son cubano with mambo, cha-cha-chá, jazz and more: a son ensemble with horns, congas, bongos and
timbales over clave. `latin/salsa`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | voices, the coro in the montuno | WP Salsa music |
| `rhythm` | the bell pattern on the timbales, a supporting part on the congas, and on the bongos improvised variations inside a repeated pattern, the martillo; for the montuno the bongo player switches to the bongo bell | WP Salsa music |
| `timbre` | the son montuno ensemble: bongos, bass, tres, trumpet, hand percussion (claves, güiro, maracas), sometimes piano, with a horn section and congas added; the timbales | WP Salsa music |
| `form` | verses, then the montuno section; piano solos | WP Salsa music |
| `mix` | no source read | |

- **In this skill**: the `vcsl_world` congas, bongos, claves, guiro, cowbells and shakers; `blocks.drums` in the
  `afrocuban` feel; the pianos; `vsco` trumpets and trombones; `bass_darkblack` or `bass_sneaky`. No tres and no
  timbales: a guitar in octaves, and a cowbell with the kit's snare and toms, stand in.
- **Variants**: *Latin jazz*: jazz over Latin American rhythms, Afro-Cuban jazz on ostinatos or a clave, and
  Afro-Brazilian jazz with samba and bossa nova (WP Latin jazz).
- **Neighbours**: Samba; `jazz/modern-combo`; Cumbia.

## Reggae

Slower than ska and rocksteady: drums and bass leaning on the downbeat, clipped guitar or piano chords on the
off-beats, a thick, heavy bass in front. `latin/reggae`

| Axis | Traits | From |
|---|---|---|
| `tempo` | slower than ska or rocksteady; dub typically 60–90 BPM | WP Reggae; Ableton Learning Music |
| `harmony` | clipped guitar or piano chords on the off-beats | WP Reggae |
| `melody` | call and response | WP Reggae |
| `rhythm` | the drums and bass leaning hard on the downbeat; the bass played as a percussion instrument | WP Reggae |
| `timbre` | the bass guitar central, thick and heavy | WP Reggae |
| `form` | no source read | |
| `mix` | the bass's high frequencies reduced to bring out the low end | WP Reggae |

- **In this skill**: `bass_darkblack` with a low `lowpass`; chords on `fsbs_clean` or a piano, short (`gate` about
  0.3) on the off-beats (`blocks.accompaniment` `figure='offbeat'`, the double skank with complexity: WP Reggae);
  `rusty`; dub's delays and reverb (`mix.delay`, as in `electronic/techno`'s dub variant).
- **Variants**: *Ska*: a walking bass with off-beat accents, the guitar and piano's "ska" strum; its later waves
  faster and harder, with punk (WP Ska).
- **Neighbours**: `electronic/dubstep` and `electronic/drum-and-bass` (dub's bass); Reggaeton.

## Calypso and soca

Trinidad's calypso, from West African kaiso and French Creole song, and soca, its offshoot with Afro- and
Indo-Trinidadian rhythms; the steelpan of the Carnival steelbands. `latin/calypso-soca`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | highly rhythmic and harmonic vocals | WP Calypso music |
| `melody` | extempo: melodies sung impromptu, commenting on island life | WP Calypso music |
| `rhythm` | rhythms traced to West African kaiso; soca's from Afro- and Indo-Trinidadian rhythms, fused with calypso, chutney, reggae, zouk and Latin music | WP Calypso music; WP Soca music |
| `timbre` | the steelpan, a chromatically pitched idiophone made from 200-litre drums, grown from Carnival percussion such as tamboo bamboo | WP Steelpan |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: `steel_drum`, a Trinidad tenor pan, C4–B5, up to five strengths with round robins
  ([soundbanks.md](soundbanks.md)); the `vcsl_world` percussion; `bass_darkblack`; a brass section from `vsco`.
- **Neighbours**: Reggae; Salsa.

## Reggaeton

Puerto Rican music on the dembow beat, from Jamaican dancehall's Dem Bow riddim and hip-hop. `latin/reggaeton`

| Axis | Traits | From |
|---|---|---|
| `tempo` | measured here on 15 Harmonix Set songs: a median 105 BPM, the middle 80% between 97 and 126 | Nieto et al. 2019 |
| `harmony` | no source read | |
| `melody` | no source read | |
| `rhythm` | the dembow beat, from the Dem Bow riddim | WP Reggaeton |
| `timbre` | hip-hop and dancehall production; bachata's guitar in a later fusion | WP Reggaeton |
| `form` | on the same songs: choruses 8 bars long in 83%, verses 8 in 53%; a median 2.6 minutes | Nieto et al. 2019 |
| `mix` | no source read | |

- **In this skill**: `blocks.drums` with `backbeat="dembow"` and `kick="four_floor"`
  ([building-blocks.md](building-blocks.md)); `drum_synth`; `bass_808` or a Surge bass.
- **Neighbours**: Reggae; `beats/trap`.

## Tango

The tango of the River Plate: an orquesta típica of violins, flute, piano, double bass and bandoneóns, on African and
European roots. `latin/tango`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | no source read | |
| `rhythm` | the habanera, tresillo with a backbeat, one of its names "tango" | WP Latin jazz |
| `timbre` | solo guitar, a guitar duo, or the orquesta típica: at least two violins, flute, piano, double bass and at least two bandoneóns; the sextet of piano, double bass, two violins and two bandoneóns | WP Tango music |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: `vsco_strings` or `iowa_strings` violins, the `vsco` flute, the pianos, `bass_sneaky`, the
  nylon guitar. No bandoneón or accordion is in the banks: a Surge reed or organ patch, or the harmonicas of
  `vcsl_winds`, comes nearest.
- **Neighbours**: `orchestral/romantic` (its salon side); Flamenco.

## Cumbia

Colombian rhythm and dance of Indigenous, European and African roots: three drums, the gaita flutes, and the
guacharaca's "chu-chucu-chu". `latin/cumbia`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | the gaitas and the flauta de millo | WP Cumbia |
| `rhythm` | in 2/2 or 2/4; a simple "chu-chucu-chu" from the guacharaca | WP Cumbia |
| `timbre` | three drums (tambora, tambor alegre, llamador) and three flutes; local instruments taken up where it travels, its percussion kept | WP Cumbia |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: the `vcsl_world` guiro for the guacharaca, frame drums and congas for the drums; the recorders
  and ocarina of `vcsl_winds` or the `vsco` flute for the gaitas, none of them a gaita.
- **Neighbours**: Salsa; Reggaeton.

## Flamenco

Andalusian song, guitar and dance in palos defined by their compás, mode and progression: the Phrygian flamenco mode,
the Andalusian cadence, twelve-beat cycles, handclaps. `latin/flamenco`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | the flamenco mode, a Phrygian or a harmonic Phrygian with a major third, beside major and minor; the Andalusian cadence, in E Am–G–F–E; bimodal palos, the guitar in Phrygian and the song in major | WP Flamenco (Manuel 2006; Rossy 1998) |
| `melody` | melodic ornamentation and improvisatory variation; falsetas on the guitar | WP Flamenco |
| `rhythm` | the compás, cycles of twelve beats in palos such as alegrías and soleá; handclaps and footwork | WP Flamenco |
| `timbre` | song, guitar, handclaps, footwork | WP Flamenco |
| `form` | the palo: a rhythmic cycle, a mode, a progression and a stanza form together | WP Flamenco |
| `mix` | no source read | |

- **In this skill**: the nylon guitar (`iowa_guitar`) with strummed chords (`musiclib.expression` `strum`) and
  falsetas; claps from `vcsl_world` or `drum_synth` (39); a 12/8 or 3/4 clock with the accents written in. No
  footwork recordings.
- **Neighbours**: Tango; `rock/heavy-metal` (the Phrygian ♭II).

## Sources

- Ableton. *Learning Music*, [Tempo and genre](https://learningmusic.ableton.com/make-beats/tempo-and-genre.html),
  read 9 November 2026: "typical" tempo ranges for dub, hip-hop, house, techno and trance, dubstep, and drum and
  bass.
- Nieto, O., McCallum, M., Davies, M. E. P., Robertson, A., Stark, A. and Egozy, E. (2019). [The Harmonix Set: Beats,
  Downbeats, and Functional Segment Annotations of Western Popular Music](https://archives.ismir.net/ismir2019/paper/000068.pdf).
  *Proceedings of ISMIR 2019*, 565–572: 912 full tracks annotated by professional musicians, chosen for rhythm
  games with a lean toward EDM and danceable pop; the annotations under the MIT licence. The tempos and section
  lengths by the set's genre labels are measured here: the metadata's BPM, and the downbeats from each section's
  start to the next.
- TalkingBass (2019): in [jazz-and-funk.md](jazz-and-funk.md).
- Wikipedia, read 9 November 2026: [Bossa nova](https://en.wikipedia.org/wiki/Bossa_nova),
  [Samba](https://en.wikipedia.org/wiki/Samba), [Salsa music](https://en.wikipedia.org/wiki/Salsa_music),
  [Latin jazz](https://en.wikipedia.org/wiki/Latin_jazz), [Reggae](https://en.wikipedia.org/wiki/Reggae),
  [Ska](https://en.wikipedia.org/wiki/Ska), [Calypso music](https://en.wikipedia.org/wiki/Calypso_music),
  [Soca music](https://en.wikipedia.org/wiki/Soca_music), [Steelpan](https://en.wikipedia.org/wiki/Steelpan),
  [Reggaeton](https://en.wikipedia.org/wiki/Reggaeton),
  [Tango music](https://en.wikipedia.org/wiki/Tango_music), [Cumbia](https://en.wikipedia.org/wiki/Cumbia),
  [Flamenco](https://en.wikipedia.org/wiki/Flamenco), with the sources they cite (Manuel 2006, Rossy 1998).
