# Style maps: what a style sounds like, on seven axes, and pieces that combine styles

Read this at the brief (step 1), when choosing what the piece should sound like, and whenever a request names a style
or describes one. A family's map lists its sub-styles, each on the same axes, each trait with what it rests on. A
piece takes one entry, or one primary entry with others borrowed for some axes, and says so in its `style`.

Contents: [Why traits, not names](#why-traits-not-names) · [An entry](#an-entry) ·
[When a sub-style is an entry of its own](#when-a-sub-style-is-an-entry-of-its-own) ·
[Combining entries](#combining-entries) · [Using a map](#using-a-map) · [The families](#the-families) ·
[Sources](#sources)

## Why traits, not names

- Style names do not agree. Three catalogues compared by Pachet and Cazaly (2000):
  - AllMusicGuide had 531 genres, Amazon 719, MP3.com 430;
  - 70 words were common to all three, 198 to two, and 802 belonged to one alone;
  - even "Rock" and "Pop" had no common definition.

  A name tells the agent little. The traits on the axes say what to write.
- A genre, in Fabbri's (1981) definition, is a set of musical facts, real and possible, whose course is governed by
  a defined set of socially accepted norms. His norms are of five kinds: technical and formal, semiotic, behavioural,
  social and ideological, economic and juridical. The maps describe the first kind, the norms a composer writes.
- In Fabbri's set terms, a sub-genre is a subset of a genre. A musical fact can lie in the intersection of two or
  more genres and belong to all of them at once. Hence the family, the sub-style, its variants, and pieces that
  combine entries.
- Entries are named for their sound, never for an artist or a work.

## An entry

Each entry is a sub-style of its family, with:

| Axis | What it says |
|---|---|
| `tempo` | tempo and feel: the beat, its subdivision, straight or swung |
| `harmony` | chords, progressions, voicing and texture, voice leading |
| `melody` | range, contour, motif and phrase, how the line moves |
| `rhythm` | the rhythmic layers, syncopation, the groove |
| `timbre` | instruments and sounds, and the ensemble |
| `form` | sections, their lengths and order, repetition and development |
| `mix` | production and mix: space, balance, loudness |

The entry adds:
- **In this skill**: the engines, banks, building-block feels and sound queries that play it, and what the skill
  cannot play.
- **Variants**: forms of the sub-style that differ on one or two axes.
- **Neighbours**: the nearest entries and how this one differs from each.

Every trait says what it rests on: a source read, or a measurement stated as ours. A cell that no source read
describes says so and gives no rule of the style; the axis is still written, as [Using a map](#using-a-map) says
(step 5).

## When a sub-style is an entry of its own

A sub-style gets an entry when all three hold:
1. the literature describes it as a style of its own, not only names it;
2. it differs from the family's other entries on the axes enough to change what a composer writes;
3. the skill can play it, or the entry says what it cannot.

A sub-style that differs on an axis or two is a variant inside an entry. The maps have as many entries as the
literature distinguishes this way, no fixed number.

## Combining entries

`style` names one entry, or a primary entry and entries borrowed for some axes ([schema.md](schema.md)):

```json
"style": {"primary": "jpop/anime-opening", "borrow": {"rhythm": "electronic/drum-and-bass"}}
```

- **One entry per axis.** Each axis is governed by one entry: the one borrowed for it, otherwise the primary. A trait
  is then written as one entry describes it; two descriptions of one axis mixed would follow neither.
- **A reason for each borrowing.** Boden (2004) counts unfamiliar combinations of familiar ideas as one of the three
  ways of creativity. She adds that such a combination is not "shaking marbles in a bag": it is valued when there is
  an intelligible link between the ideas, which the maker recognises and judges. So record in the project's
  `decisions` why the borrowed axis belongs with the primary. Borrow what the brief asks for, or an axis the primary
  leaves without a source ([Using a map](#using-a-map), step 5), not more.
- **Review follows the axes.** Each of `review`'s checks belongs to an axis. The entry governing that axis supplies
  its limits; otherwise the check keeps its default, and `review`'s record names the origin of every limit
  ([style-maps.json](style-maps.json)). A limit comes only from a source or from professional work measured, never
  from agent pieces.
- **Review checks a sourced tempo.** Where an entry's tempo cell gives a range from its source (`tempo_bpm`: house,
  techno, trance, festival EDM, hard dance, drum and bass, dubstep, future bass, synthwave, trap, G-funk and smooth
  jazz), `review` asks about a piece whose main tempo lies outside it, the written tempo most notes start under. In
  a closed range a half- or double-time reading inside it counts as inside; an open range is read as written.
- **Analyze sets the spectrum beside the genre's.** Where the family or entry governing the mix axis has a published
  measurement of its genre's long-term spectrum (`published_mix`: number-one singles by genre, Pestana et al. 2013),
  `analyze` reports the master's slope beside it and asks about a master well below its top. Pop, rock, electronic,
  beats, jazz and folk have one, disco and soul their own; J-pop borrows pop's and says so; lo-fi, ambient and a
  game's places have none, with the reason ([performance-and-mix.md](performance-and-mix.md), Brightness and air).
- **Requests with no entry of their own** are combined the same way: a J-pop ballad
  ([style-map-jpop.md](style-map-jpop.md), Not entries), a game's town or dungeon in the game's style
  ([style-map-game.md](style-map-game.md), Shared by the family).

## Using a map

1. At the brief, find the family, then the entry nearest the request.
2. Where the request mixes styles, take the entry that should govern most axes as the primary, and borrow only the
   axes the request takes from elsewhere.
3. Where no entry fits, describe the target on the axes from the request, and take the nearest entries.
4. Write the entries' traits into the plan and `style` into the project. The craft guides each entry links to say how
   to write each trait.
5. Where a cell of the entry governing an axis says no source read, the maps hold no rule of that style for the
   axis, but the piece still needs one. Take it from the first of these that answers:
   1. the brief: a tempo, a length, a loudness it gives;
   2. the guide whose practice holds across styles: [harmony.md](harmony.md) for harmony,
      [climax-and-melody.md](climax-and-melody.md) for melody, [development-and-groove.md](development-and-groove.md)
      and [building-blocks.md](building-blocks.md) for rhythm, [sound-selection.md](sound-selection.md) for timbre,
      [arrangement.md](arrangement.md) and [development-and-groove.md](development-and-groove.md) for form,
      [performance-and-mix.md](performance-and-mix.md) for the mix, [moods.md](moods.md) for tempo where the brief
      names a mood;
   3. a neighbouring entry whose cell for that axis rests on a source, borrowed for it in `style` with the reason in
      `decisions` (Combining entries, above). The synth-pop entry leaves tempo open; synthwave, which revives 1980s
      synth-pop, gives 80–118 BPM ([style-map-electronic.md](style-map-electronic.md)), so a synth-pop piece may
      borrow it and say why;
   4. the piece's own choice.

   Record what was chosen in `decisions` as the piece's choice, not as the style's norm. A borrowed axis brings the
   lending entry's `review` limits with it; otherwise `review` checks the axis as for any piece.
6. Where the brief names a mood as well, move the cues inside the style's range in the mood's direction
   ([moods.md](moods.md)): a mood is not an entry. A quality of sound or motion (bright, warm, thick, bouncy) works
   the same way ([character-words.md](character-words.md)).

## The families

Each family's map lists its entries, the traits of each with their sources, the cells no source read describes, and
what `review` asks differently there.

| Family | Map | Entries |
|---|---|---|
| Orchestral and classical | [style-map-orchestral.md](style-map-orchestral.md) | `orchestral/baroque`, `orchestral/classical-era`, `orchestral/romantic`, `orchestral/impressionist`, `orchestral/post-tonal`, `orchestral/neoclassical`, `orchestral/minimalist`, `orchestral/cinematic` |
| Horror and suspense | [style-map-horror.md](style-map-horror.md) | `horror/shrieking-strings`, `horror/drone-dread`, `horror/ostinato-pulse`, `horror/corrupted-innocence` |
| J-pop and anime songs | [style-map-jpop.md](style-map-jpop.md) | `jpop/anime-opening`, `jpop/fast-electro`, `jpop/idol-pop`, `jpop/city-pop`, `jpop/enka` |
| Pop and ballads | [style-map-pop.md](style-map-pop.md) | `pop/uptempo`, `pop/ballad`, `pop/disco`, `pop/synth-pop`, `pop/hyperpop` |
| Rock and metal | [style-map-rock.md](style-map-rock.md) | `rock/classic-hard`, `rock/punk`, `rock/alternative`, `rock/shoegaze`, `rock/post-rock`, `rock/progressive`, `rock/surf`, `rock/heavy-metal`, `rock/thrash`, `rock/power-metal`, `rock/extreme-metal`, `rock/doom`, `rock/metalcore`, `rock/nu-metal` |
| Beats and instrumental hip-hop | [style-map-beats.md](style-map-beats.md) | `beats/lo-fi`, `beats/boom-bap`, `beats/trap`, `beats/drill`, `beats/phonk`, `beats/trip-hop`, `beats/g-funk` |
| Jazz, blues, funk and soul | [style-map-jazz.md](style-map-jazz.md) | `jazz/swing`, `jazz/modern-combo`, `jazz/modal`, `jazz/fusion`, `jazz/smooth`, `jazz/gypsy`, `jazz/blues`, `jazz/funk`, `jazz/soul` |
| Latin American, Caribbean and Iberian | [style-map-latin.md](style-map-latin.md) | `latin/bossa-nova`, `latin/samba`, `latin/salsa`, `latin/reggae`, `latin/calypso-soca`, `latin/reggaeton`, `latin/tango`, `latin/cumbia`, `latin/flamenco` |
| Chinese traditional and Chinese-style | [style-map-chinese.md](style-map-chinese.md) | `chinese/sizhu`, `chinese/gufeng`, `chinese/shidaiqu` |
| Folk and roots | [style-map-folk.md](style-map-folk.md) | `folk/celtic`, `folk/klezmer`, `folk/bluegrass`, `folk/country` |
| Electronic | [style-map-electronic.md](style-map-electronic.md) | `electronic/house`, `electronic/techno`, `electronic/trance`, `electronic/festival-edm`, `electronic/hard-dance`, `electronic/drum-and-bass`, `electronic/uk-garage`, `electronic/dubstep`, `electronic/future-bass`, `electronic/edm-trap`, `electronic/electro`, `electronic/eurobeat`, `electronic/synthwave`, `electronic/chiptune`, `electronic/ambient`, `electronic/idm` |
| The places of a role-playing game | [style-map-game.md](style-map-game.md) | `game/town`, `game/overworld`, `game/dungeon`, `game/battle` |

## Sources

- Boden, M. A. (2004). *The Creative Mind: Myths and Mechanisms*, 2nd ed. Routledge. Read in the extract the author
  published in *Computational Creativity: An Interdisciplinary Approach*, Dagstuhl Seminar Proceedings 09291 (2009),
  [doi:10.4230/DagSemProc.09291.21](https://doi.org/10.4230/DagSemProc.09291.21), CC BY 4.0: combinational,
  exploratory and transformational creativity; a combination valued for an intelligible link.
- Fabbri, F. (1981). Una teoria dei generi musicali: due applicazioni. Paper at the first conference of IASPM,
  Amsterdam; in English as "A theory of musical genres: two applications", in Horn and Tagg (eds.), *Popular Music
  Perspectives*, 1982. Read in the Italian original on [the author's site](https://www.francofabbri.net/files/Testi_per_Studenti/Teoria_dei_generi.pdf):
  the definition, the five kinds of norm, sub-genres as subsets, a musical fact in the intersection of genres.
- Pachet, F. and Cazaly, D. (2000). [A taxonomy of musical genres](https://www.francoispachet.fr/wp-content/uploads/2021/01/pachet-00-RIAO.pdf).
  *Content-Based Multimedia Information Access (RIAO)*, Paris: three catalogues' genres compared.
