# Style map: the places of a role-playing game

The music of the places a role-playing game moves between: the town, the overworld, the dungeon and the battle. In
early Japanese role-playing games the form of each sets it apart (Elkins 2020); for other games these entries are the
nearest description read. Read [style-maps.md](style-maps.md) first for the axes and for combining entries; the craft
of loops, seams, layers and delivery is in [game-music.md](game-music.md), music under text and voices in
[scene-music.md](scene-music.md).

Contents: [Shared by the family](#shared-by-the-family) · [Town](#town) · [Overworld](#overworld) ·
[Dungeon](#dungeon) · [Battle](#battle) · [Sources](#sources)

Source tags: WP is Wikipedia, read on 9 November 2026, by article. The other sources are by author and year.

## Shared by the family

- **Four places.** The bulk of the music in early role-playing games falls into town music, overworld exploration
  music, dungeon music and battle music, and musical form helps tell these spaces apart (Elkins 2020, read in its
  abstract). Older games often made combat a mode of its own, apart from exploring the world, some of them, especially
  the earlier, starting battles from random encounters, and most role-playing games set bosses at key places (WP
  Role-playing video game): the battle is a piece of its own, switched to and back from
  ([game-music.md](game-music.md), Stingers, transitions and endings).
- **The game's sound.** A place takes its sound from the game; the sound chips of early consoles gave theirs the style
  now called chiptune (WP Video game music; `electronic/chiptune`). These entries describe the places' form and
  harmony, so a piece takes the game's style as its primary entry and borrows those two axes from the place, the
  reason in `decisions`:

  ```json
  "style": {"primary": "electronic/chiptune", "borrow": {"form": "game/dungeon", "harmony": "game/dungeon"}}
  ```

  Where the brief names only the place, its entry is the primary, and the axes it leaves without a source follow
  [style-maps.md](style-maps.md), Using a map, step 5.
- **Pieces that do not end.** Many early console games share a style sometimes called the video game genre: music with
  no lyrics that plays over the game's sounds and is written to go round again, with no ending and no fade; no form of
  game music is more common than the loop (WP Video game music). The loop point, and how much a loop can repeat before
  players tire of it, are in [game-music.md](game-music.md) (The loop point; Repetition: Dutta 2020, Worrall 2025).
- **Character.** No source read says which character each place conveys: take it from the brief, and set its cues as
  [game-music.md](game-music.md) (Mood and scene) and [moods.md](moods.md) give them (Eerola, Friberg and Bresin
  2013).

For the family, `review` keeps every default but one, in the dungeon (below): no other source read describes a limit
to change.

## Town

Music for a town or a village. `game/town`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | authentic cadential closure, more likely here than in the other places | Elkins 2020 |
| `melody` | no source read | |
| `rhythm` | no source read | |
| `timbre` | no source read | |
| `form` | phrases in pairs, the second closing more firmly than the first (the period, as Open Music Theory describes it), likeliest in town music of the four kinds of theme; the pairing and its cadences give a town a balance and rest the other kinds largely lack | Elkins 2020 |
| `mix` | no source read | |

- **In this skill**: the period's antecedent and consequent, the first closing on a weaker cadence and the second on
  an authentic one ([climax-and-melody.md](climax-and-melody.md); [harmony.md](harmony.md), cadences); the loop's
  length from the time a player spends there ([game-music.md](game-music.md), Brief).
- **Neighbours**: Overworld, whose sentences drive forward where the town's periods come to rest.

## Overworld

Music for exploring the world between the towns and the dungeons. `game/overworld`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | no source read | |
| `rhythm` | no source read | |
| `timbre` | no source read | |
| `form` | more often the sentence than a town's period: a form that presses on toward its close (Vande Moortele 2011 on the sentence, as Elkins cites him). That this suits music for travelling is this skill's reading | Elkins 2020 |
| `mix` | no source read | |

- **In this skill**: the sentence, a basic idea stated and repeated, then a continuation that fragments it and drives
  to the cadence ([climax-and-melody.md](climax-and-melody.md); [harmony.md](harmony.md), In a phrase); `review`
  asks about a section whose melody restates no earlier bar (Caplin 1998), as for any piece.
- **Neighbours**: Town, whose periods close and rest; Battle.

## Dungeon

Music for a dungeon, a cave or a tower. `game/dungeon`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | chords that stay where they are or leave the key unclear, without the pull of functional progressions | Elkins 2020 |
| `melody` | no source read | |
| `rhythm` | no source read | |
| `timbre` | no source read | |
| `form` | much repeating inside the cue | Elkins 2020 |
| `mix` | no source read | |

- **In this skill**: harmony that does not progress toward a cadence, a drone or pedal under it
  ([film-score.md](film-score.md), pedal points); for an ambiguous centre, modes or the whole-tone collection, as the
  modal and impressionist entries describe them (`jazz/modal`, `orchestral/impressionist`). `review` does not ask
  about a part repeating a short cycle unchanged: much internal repetition is the place's form (Elkins 2020).
- **Neighbours**: Battle, which keeps some of these traits; `horror/drone-dread` (static drones and ambiguity, for
  a dungeon meant to frighten); `jazz/modal`.

## Battle

Music for a fight, from a random encounter to a boss. `game/battle`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | some but not all of the dungeon's traits: the abstract read does not say which | Elkins 2020 |
| `melody` | no source read | |
| `rhythm` | no source read | |
| `timbre` | no source read | |
| `form` | some but not all of the dungeon's traits: the abstract read does not say which | Elkins 2020 |
| `mix` | no source read | |

- **In this skill**: the switch into the battle and the victory piece after it are seams between modules
  ([game-music.md](game-music.md), Stingers, transitions and endings); the battle's drive, which no source read
  gives, comes from the game's own style.
- **Neighbours**: Dungeon; Overworld.

## Sources

- Elkins, A. (2020). Musical Form and Gameplay Context in the Japanese Role-Playing Game. Paper at the North American
  Conference on Video Game Music, 2020. Read in its abstract, as kept by
  [The Unofficial Convention Archive](https://www.theunofficialconventionarchive.com/nacvgm-2020-musical-form-and-gameplay-context-in-the-japanese-role-playing-game/):
  the four kinds of music and the form and harmony of each, after the Formenlehre of Richards (2011) and Vande
  Moortele (2011) and its application to game music by Schartmann (2018).
- Wikipedia, read 9 November 2026: [Video game music](https://en.wikipedia.org/wiki/Video_game_music) (chiptune
  as the sound of early games; the video game genre's pieces, which repeat indefinitely, without lyrics, over the
  game's sounds; looping as game music's most common form),
  [Role-playing video game](https://en.wikipedia.org/wiki/Role-playing_video_game) (combat as a mode of its own in
  older games; random encounters; bosses).
- In [game-music.md](game-music.md): Dutta (2020), Worrall (2025), Eerola, Friberg and Bresin (2013).
