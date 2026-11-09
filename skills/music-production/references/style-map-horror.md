# Style map: horror and suspense

Music for fear and tension in film, games and visual novels, by the approaches the literature describes. Read
[style-maps.md](style-maps.md) first; the craft is in [film-score.md](film-score.md) (Suspense and horror: the
toolkit on the banks, the shape of a cue, the level), with [game-music.md](game-music.md) and
[scene-music.md](scene-music.md) for loops and stingers under play or text.

Contents: [Shared by the family](#shared-by-the-family) · [Shrieking strings](#shrieking-strings) ·
[Drone dread](#drone-dread) · [Ostinato pulse](#ostinato-pulse) · [Corrupted innocence](#corrupted-innocence) ·
[Sources](#sources)

## Shared by the family

The approaches below share these devices (Ireland 2023, a film-music scholar's overview of horror and thriller
scores):
- **Ambiguity**: little conventional melody, and dissonant harmonies that do not readily resolve.
- **Repetition that withholds**: repeated short figures, tremolo, drones. Unease grows when an expected development
  does not come. Tension rises by adding instruments, by more volume or a more regular repetition, or by repeating
  each figure a step higher, while the melody hardly develops.
- **The body**: high strings that imitate the roughness of screams; whispered or shouted voices; heartbeats.
  Scream-like music shares the screams' roughness (Trevor, Arnal and Frühholz 2020). Horror soundtracks hold more
  noisy screams and harsh, rough tones than expected (Blumstein, Davitian and Kaye 2010).
- **The shock**: a stinger, a sudden loud burst like a jump scare, often after a sudden silence.

Anxiety (sustained unease) and terror (the shock) are the two jobs in [film-score.md](film-score.md). Scream-like
roughness belongs to the shock and the shriek: high clusters for terror, low ones for dread, as that guide explains
from the beating of close intervals.

For the whole family, `review` does not ask about these:
- minor-second collisions, and notes outside the chord left unresolved: the family's dissonance is meant and does not
  resolve (Ireland 2023);
- close low intervals: low drones and rumbling are its floor (Ireland 2023; film-score.md);
- pushes: that question rests on rock melodies (Tan, Lustig and Temperley 2019), and the family's sources describe
  none.

## Shrieking strings

Repeated high-register string pitches, the shriek, building as more strings join to widen a dissonant chord; tremolo
under it; the stinger. `horror/shrieking-strings`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | a dissonant chord expanded note by note as strings are added | Ireland 2023 |
| `melody` | melody avoided for repeated high pitches | Ireland 2023 |
| `rhythm` | repeated high notes; tremolo, the rapid repetition of a pitch or alternation of two | Ireland 2023 |
| `timbre` | high violins, then more strings; roughness like a scream's | Ireland 2023; Trevor et al. 2020 |
| `form` | a build that ends in the shock, often after silence | Ireland 2023 |
| `mix` | wide dynamics, room above the floor for the shock | film-score.md (Level) |

- **In this skill**: section strings and tremolo (`vsco_strings`), the thin high solo-violin tremolo
  (`vsco_colors`), the hits of film-score.md's toolkit.
- **Neighbours**: Drone dread (low and still instead of high and rising).

## Drone dread

Sustained low notes or repeated low figures, with rumbling, leaving a void up to high fragments; electronic sound
blurred with sound design. `horror/drone-dread`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | static drones; ambiguity | Ireland 2023 |
| `melody` | high melodic fragments far above the drone | Ireland 2023 |
| `rhythm` | sustained notes or repeated figures; a heartbeat-like sound | Ireland 2023 |
| `timbre` | low drones and rumbling; electronic instruments and sounds blurred with sound design, which evoke technology and the inhuman; mechanical sounds such as ticking; whispers | Ireland 2023 |
| `form` | repetition that withholds the expected development | Ireland 2023 |
| `mix` | wide dynamics (film-score.md, Level) | |

- **In this skill**: low string tremolo and double bass (`vsco_strings`, `vsco_extra`), bowed metal and scrapes
  (`iowa_perc`, `vsco_colors`), Surge XT pads and drones (`studio.py sounds --role pad`), `noise` parts for rumble and
  air. No whispered voice: the only voice bank sings "ah" (`vocal_ah`). `review` does not ask about loops or static
  textures here: the drone's repetition is the device (Ireland 2023).
- **Neighbours**: Shrieking strings; Ostinato pulse (a figure that moves instead of a held floor); ambient
  electronic music (calm instead of threat).

## Ostinato pulse

A short figure repeated over an ominous bass, escalating by entries, volume and pitch; in thrillers, a recurring
motif with dissonant string stabs. `horror/ostinato-pulse`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | dissonant, unresolved; an ominous bass | Ireland 2023 |
| `melody` | repeated short melodies instead of development | Ireland 2023 |
| `rhythm` | a pulsing figure; dissonant string stabs building | Ireland 2023 |
| `timbre` | a pulsing piano over the bass; a recurring guitar motif; strings | Ireland 2023 |
| `form` | escalation: instruments enter, the volume grows, the repetitions grow more regular or rise in pitch | Ireland 2023 |
| `mix` | no source read | |

- **In this skill**: the pianos, Surge XT basses and pulses (`sounds --role bass`, `--role pluck`), section strings
  for the stabs (`vsco_strings` spiccato), the building blocks for a pulse. `review` does not ask about loops, static
  textures or stabs struck as blocks here: the repeated figure and the stabs are the device (Ireland 2023).
- **Neighbours**: Drone dread; cinematic orchestral (`orchestral/cinematic`) in thrillers and action.

## Corrupted innocence

The sounds of childhood and faith set against dark content: a music box, a lullaby, an organ, a hymn; cheerful or
nostalgic music against violence. `horror/corrupted-innocence`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | as the lullaby or hymn it alludes to | Ireland 2023 |
| `melody` | allusions to lullabies and hymns | Ireland 2023 |
| `rhythm` | no source read | |
| `timbre` | the music box; the organ | Ireland 2023 |
| `form` | the familiar placed in an unfamiliar setting; lively or nostalgic music set against the scene | Ireland 2023 |
| `mix` | no source read | |

- **In this skill**: the pipe organ (`organ_vcsl`, [organ.md](organ.md)); the catalog's patches named for a music
  box or a toy piano (`studio.py sounds --name music_box`, `--name toy`); the glockenspiel (`vsco`). A lullaby or
  hymn of the piece's own: never a quoted one.
- **Neighbours**: Drone dread under it; the Romantic or Baroque entry (`orchestral/romantic`, `orchestral/baroque`)
  for the hymn's harmony.

## Sources

- Ireland, D. (2023). [What makes a film score frightening? Expert explains the techniques that build tension and make us jump](https://theconversation.com/what-makes-a-film-score-frightening-expert-explains-the-techniques-that-build-tension-and-make-us-jump-216121).
  *The Conversation*, 26 October 2023. The author is Associate Professor in Film Music Studies and Music Psychology,
  University of Leeds. It cites K. J. Donnelly on the scream-like roughness of high strings.
- Trevor, C., Arnal, L. H. and Frühholz, S. (2020); Blumstein, D. T., Davitian, R. and Kaye, P. D. (2010): in
  [film-score.md](film-score.md), read in their abstracts.
- Tan, I., Lustig, E. and Temperley, D. (2019), in [development-and-groove.md](development-and-groove.md).
