# Style map: horror and suspense

Music for fear and tension in film, games and visual novels, by the approaches the literature describes. Read
[style-maps.md](style-maps.md) first; the craft is in [film-score.md](film-score.md) (Suspense and horror: the
toolkit on the banks, the shape of a cue, the level), with [game-music.md](game-music.md) and
[scene-music.md](scene-music.md) for loops and stingers under play or text.

Contents: [Shared by the family](#shared-by-the-family) · [Shrieking strings](#shrieking-strings) ·
[Drone dread](#drone-dread) · [Ostinato pulse](#ostinato-pulse) · [Corrupted innocence](#corrupted-innocence) ·
[Sources](#sources)

## Shared by the family

Four things run through the approaches below. Each is given with the research on why it works and with the practice
in film scores (Ireland 2023, a film-music scholar's overview).

- **Instability that does not settle.** Tension comes from conflict, dissonance or instability, which make a listener
  want a more stable state (Lehne and Koelsch 2015). These scores hold that state back: the harmony stays dissonant
  and there is little tune to follow (Ireland 2023).
- **An expectation kept waiting.** What triggers tension is an event that raises a strong expectation of what comes
  next (Lehne and Koelsch 2015). A short figure played again and again, a tremolo or a drone raises one and does not
  answer it. The wait is tightened by more instruments, more level, repeats that come more regularly, or each repeat
  a step higher (Ireland 2023).
- **Signals of alarm.** A scream is rough: its loudness flutters 30 to 150 times a second, and rougher voices are
  heard as more fearful (Arnal et al. 2015). Scream-like film music shares that roughness (Trevor, Arnal and
  Frühholz 2020), and horror soundtracks hold more noisy screams and harsh, non-musical tones than expected
  (Blumstein, Davitian and Kaye 2010). High strings, whispered or shouted voices and heartbeat-like sounds carry it
  (Ireland 2023).
- **The startle.** A stinger: a sudden loud sound, often after a sudden silence (Ireland 2023). An unexpected event
  sets off a fast defensive reaction before any appraisal (Huron 2006, in [film-score.md](film-score.md)).

Anxiety (sustained unease) and terror (the shock) are the two jobs in [film-score.md](film-score.md). Scream-like
roughness belongs to the shock and the shriek: high clusters for terror, low ones for dread, as that guide explains
from the beating of close intervals.

For the whole family, `review` does not ask about these:
- minor-second collisions, and notes outside the chord left unresolved: the family's dissonance is meant and stays
  (Ireland 2023; Lehne and Koelsch 2015 on dissonance as the source of the tension);
- close low intervals: low drones and rumbling are its floor (Ireland 2023; film-score.md);
- pushes: that question rests on rock melodies (Tan, Lustig and Temperley 2019), and the family's sources describe
  none.

## Shrieking strings

Repeated high-register string pitches, the shriek, building as more strings join to widen a dissonant chord; tremolo
under it; the stinger. `horror/shrieking-strings`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | a dissonant chord that widens as more strings join | Ireland 2023; dissonance as tension: Lehne and Koelsch 2015 |
| `melody` | melody avoided for repeated high pitches | Ireland 2023 |
| `rhythm` | repeated high notes; tremolo (one pitch struck again and again, or two in quick exchange) | Ireland 2023 |
| `timbre` | high violins, then more strings; roughness like a scream's | Ireland 2023; Trevor et al. 2020; Arnal et al. 2015 |
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
| `harmony` | a drone that does not move, and no clear key over it | Ireland 2023; instability as tension: Lehne and Koelsch 2015 |
| `melody` | high melodic fragments far above the drone | Ireland 2023 |
| `rhythm` | held notes or a figure that repeats; a heartbeat-like sound | Ireland 2023 |
| `timbre` | low drones and rumbling; electronic sound that shades into sound design, machine-like and not human; mechanical sounds such as ticking; whispers; harsh, noisy tones | Ireland 2023; noise in horror soundtracks: Blumstein et al. 2010 |
| `form` | repetition that does not give the development it leads one to expect | Ireland 2023; expectation as the trigger: Lehne and Koelsch 2015 |
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
| `form` | escalation: instruments enter, the level grows, the repeats come more regularly or climb in pitch | Ireland 2023; expectation as the trigger: Lehne and Koelsch 2015 |
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
| `form` | something familiar put where it does not belong; cheerful or wistful music against what the scene shows | Ireland 2023 |
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
- Lehne, M. and Koelsch, S. (2015). [Toward a general psychological model of tension and
  suspense](https://doi.org/10.3389/fpsyg.2015.00079). *Frontiers in Psychology* 6, 79. Tension from conflict,
  dissonance and instability, and from expectations of what comes next, in music as in film and stories.
- Arnal, L. H., Flinker, A., Kleinschmidt, A., Giraud, A.-L. and Poeppel, D. (2015). [Human screams occupy a
  privileged niche in the communication soundscape](https://doi.org/10.1016/j.cub.2015.06.043). *Current Biology*
  25(15), 2051–2056. Roughness, modulation at 30 to 150 Hz, in screams and alarms; rougher sounds rated more fearful.
- Trevor, C., Arnal, L. H. and Frühholz, S. (2020); Blumstein, D. T., Davitian, R. and Kaye, P. D. (2010); Huron, D.
  (2006): in [film-score.md](film-score.md). The first two were read in their abstracts.
- Tan, I., Lustig, E. and Temperley, D. (2019), in [development-and-groove.md](development-and-groove.md).
