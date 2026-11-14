# Development and groove: music that keeps changing and moves

Read this when planning the form (step 3), when writing the accompaniment (step 4) and when `review` asks about loops,
returns, arrivals, block chords or pushes (step 6). It builds on [arrangement.md](arrangement.md) (form, roles, vertical
hygiene) and [climax-and-melody.md](climax-and-melody.md) (the high point, melodic shape).

Contents: [Diagnose "dull" and "stiff"](#diagnose-dull-and-stiff) · [Plan the energy (step 3)](#plan-the-energy-step-3) · [Groove (steps 4 and 5)](#groove-steps-4-and-5) · [Voicings that move: musiclib.voicing](#voicings-that-move-musiclibvoicing) · [Sources](#sources)

## Diagnose "dull" and "stiff"

Seven pieces that agents made with this skill (ballad, boom bap, film cue, horror cue, rock, techno, trap) were heard as
not wrong, but at times dull or stiff. Measured on their scores:

- **Dull:** loops held unchanged for 24 to 48 bars (a techno kit and its bass, a boom-bap keyboard loop), rock choruses
  thinner than their pre-choruses, verses and hooks at nearly the same density and dynamics.
- **Stiff:** chord parts that strike and release every chord as one block (100% of the chords in the boom-bap keys, the
  rock organ, the techno stab and pad, the trap pad and brass), sustained harmony that changes in every part at once on
  the downbeat, melodies mostly on the beat.
- **Not the cause:** micro-timing. Every part already had the small player-like deviation of `musiclib.expression`
  (a standard deviation of 2 to 9 ms). Listeners rate quantized and performed micro-timing alike as groovy, and
  exaggerated deviation worse (Senn et al. 2016). Fix the written rhythm and voicing, not the jitter.

The ballad, the film cue and the horror cue had a clear arc and moving parts; `review` asks nothing about them.

## Plan the energy (step 3)

For each section write down its notes per bar, the parts that play, the register and the dynamics, and draw the curve:
where it builds, where it breathes, where the high point is ([climax-and-melody.md](climax-and-melody.md)). `profile`
shows the plan against the score; `review` reports the same figures per section under `repetition.energy`.

Decide how much the music should change before any of it is written: what the request and its use say of that is settled in step 1, and what they leave open in step 2. Moderate novelty is liked
best: across 57 studies of music preference, most fit an inverted U between novelty or complexity and liking (Chmiel
and Schubert 2017). Keep what gives identity (the motif, the groove, the harmony) and change one or two dimensions at
a time. In a song, the prechorus builds toward the chorus through register, phrasing, the length of units and harmonic
rhythm (Summach 2011), and layers held back for later sections give the song room to build (Senior 2024). Dance music
builds and breaks by its own routine ([electronic.md](electronic.md); Solberg 2014).

| Dimension | Moves |
|---|---|
| Texture | add or remove a layer; take the kick and bass out for a bar or a phrase and bring them back; a contrasting breakdown (Solberg 2014) |
| Register | the accompaniment up an octave; a wider, more open voicing in the chorus; the bass down an octave at the arrival |
| Rhythm | hats from eighths to sixteenths; half-time or double-time feel; a push into the chorus |
| Harmony | the returning theme reharmonized; a pedal under changing chords; a borrowed chord at the turn ([harmony.md](harmony.md)) |
| Melody | the motif varied, not repeated: its rhythm changed, its intervals widened or narrowed, sequenced, fragmented (Schoenberg 1967); fragments shortening toward the cadence (Caplin 1998) |
| Transitions | a fill at the end of a phrase; a riser before a phrase downbeat and a falling sweep after it (Smith 2021; the risers in [electronic-sounds.md](electronic-sounds.md)); a stop before the chorus |

Strong contrasts of register, texture and instrumentation mark section boundaries, and instruments added or taken away
gradually or suddenly shape a longer span (McAdams, Goodchild and Soden 2022).

A return that changes nothing is a question: `review` asks when a section repeats an earlier one note for note in every
part, and when a chorus, hook, drop or climax arrives thinner than the section before it.

### Loops

Repetition can be the pleasure itself (Garcia 2005): keep the loop, and let something move. Dance music is phrased in
groups of two bars at several levels, and new sounds enter at the downbeats of those phrases (Smith 2021);
[electronic.md](electronic.md) gives the break routine and its five tension techniques (Solberg 2014) and the engine's
tools for repetition with process. The same holds for a boom-bap loop, a trap beat or a game loop. At each 8- or 16-bar
edge change something:

- a fill, or a bar with the kit thinned out;
- a dropout and return: kick and bass out for a bar or a break, back on the downbeat;
- a process over the loop: a filter opening (`mix.filter_sweep`), a swell (the part's `mix.automation`, in dB);
- the pattern varied: one hat accent moved, a percussion layer entering, the bass's last bar answering.

`review` asks when a pitched part repeats a 1-, 2- or 4-bar pattern unchanged for 24 bars or more, a percussion part for
33 or more, or the whole texture for 16. A heartbeat in a horror cue or a techno kick under moving layers is fine; the
question is whether anything else moves. The three counts are this project's own, set on its early pieces, not taken
from a source; a style's map entry may give its own ([style-maps.md](style-maps.md)), and review's record lists every
limit with its origin.

## Groove (steps 4 and 5)

- **Syncopation, in moderation.** Medium syncopation made listeners most want to move and gave the most pleasure;
  heavy syncopation keeps them from finding the beat (Witek et al. 2014, on funk drum breaks). Rhythm drives groove, and
  very complex harmony weakens its effect (Matthews et al. 2019). A few well-placed off-beat attacks, not all of them.
- **Pushes.** Rock and pop melodies put accented notes just before strong beats, and listeners hear them as belonging
  to that beat (Tan, Lustig and Temperley 2019). Such a note is the next chord's tone heard early, over the old chord
  (Open Music Theory, Embellishing Tones: the anticipation). The accompaniment can stay on the beat, or push with the
  melody where the arrangement wants a joint push or the early note rubs against the old chord (`review` lists minor
  seconds and ninths; [arrangement.md](arrangement.md)). `review` counts as a push an attack at most an eighth
  before a downbeat or half-bar that its part holds over or rests through, with no attack of its own on that beat: the
  syncopation Longuet-Higgins and Lee (1984) define, a note from a weaker position sounding over the stronger one
  after it; a new note on the downbeat makes the earlier one a pickup instead. It asks when no melody or accompaniment
  attack pushes a downbeat or half-bar at all; in a chorale or a baroque piece that is right.
- **Accompaniment that moves.** Give each support part a job and a rhythm of its own. Owsinski's rhythm element plays
  against the foundation to add motion. Israels has the comping piano play commentary on the melody rather than its
  rhythms, with chords in answer to the bass's rhythm or ahead of it. Common figures:
  - piano and keys: broken chords or arpeggios, an alternating bass and chord, syncopated comping with rests in it;
  - guitar: chords strummed down and up (`strum` in `musiclib.expression`'s overrides), muted sixteenths between
    chord hits;
  - pads and held strings: keep the common tone over the change, move one inner voice, a suspension (4-3) resolving,
    a swell (CC11) within the held chord;
  - bass: the root on the downbeat, a passing or approach note into the next chord (a whole step, see
    [arrangement.md](arrangement.md)), octave leaps, a rhythmic cell shared with the kick;
  - drums: ghost notes under the backbeat, accents in the hats, fills where the phrases end ([arrangement.md](arrangement.md)).
- **Lengths.** When every note of every sustained part starts or moves on the downbeat, the changes draw the ear less
  than when some enter on other beats (Senior 2020). `review`
  asks about chord parts (three or more pitch classes; power chords are left out) whose chords are at least 90% struck
  and released as one block when they are held (half notes or longer) or all one length; syncopated stabs and comping
  of varied lengths are a rhythm and are not asked about. The 90% and the eight chords are this project's own numbers,
  not a source's.

## Voicings that move: `musiclib.voicing`

`voice_lead(symbols, voices=4, low=48, high=79, start=None, ceilings=None, avoid_parallels=False, against=None)`
voices a chord progression for a keyboard, pad, string or brass part. It chooses pitches, not rhythm: give each
voicing the part's own rhythm (blocks, broken chords, a strum, held tones).

- The voicings are chosen across the whole progression so the voices move as little as possible: common tones held,
  the others to the nearest chord tone (efficient voice leading, Tymoczko 2011), which also keeps each voice heard as
  one line (Huron 2001). The top voice counts more, a leap past a fifth costs extra, and the voicing does not drift
  out of its range over a long progression.
- Adjacent voices stay within an octave, no doubled pitch, no voice crossing, no close interval below its low
  interval limit (Hoffmann's chart; a minor third not below C3, a major third not below B♭2, a fifth not below B♭1),
  and no minor second or minor ninth between two voices: a major seventh is fine, the seventh a semitone under the
  root is not ([arrangement.md](arrangement.md), vertical hygiene).
- With fewer voices than tones it leaves out the fifth, then the root (the bass plays it), an eleventh, a ninth; under
  a major seventh the root goes first. Where no bass part plays (a piano or a pad alone), pass `keep_root=True`, or one
  value per chord: a rootless A♭△7 in three voices, C E♭ G, is heard as C minor. It keeps the third or the suspended tone, the seventh or sixth, a thirteenth
  and altered tones. When the range has no room for a chord as it stands, it doubles another tone, then leaves out one
  more (a major seventh without its root under a melody, rather than a cluster).
- `against` gives, per chord, the pitches other parts sound with it: the melody, the bass, the left hand, a part
  voiced before. The voicing keeps minor seconds and ninths away from them and, where it can, leaves their pitches to
  them; the two hands of one piano cannot strike one key at once. A tone that would rub against them wherever the
  range puts it is left out: under a melody on the root of a major-seventh chord, the accompaniment plays the triad
  (the third stays). Voice the parts in dependency order, each against what was written before it.
- Where the melody anticipates a downbeat and the accompaniment pushes with it, voice the next chord at that eighth;
  where the accompaniment stays on the beat, check the early note against the old chord (`review` lists the rubs).
- `ceilings` keeps the voicing under the melody chord by chord, leaving the lead its register: the ear follows the
  highest voice's pitch best (Hove et al. 2014, in [sound-selection.md](sound-selection.md)), chords above the
  comping range crowd the lead (Israels, in [anime-opening.md](anime-opening.md)), and chords in the lead's octave are
  a cause of a lead lost in a drop ([electronic.md](electronic.md)). The example below uses the melody's lowest note in
  the bar less a minor third. `start` begins near a given voicing; `avoid_parallels` avoids consecutive fifths and octaves
  wherever the range allows another voicing, for common-practice and choral writing (pop and rock move in parallel on
  purpose, so it is off by default). Where the range allows none, the fewest remain; `review` lists parallels between
  parts that each play one line (voices written a part each), not inside one chord part.

```python
from musiclib.voicing import voice_lead
chords = ['Dm7', 'G7', 'Cmaj7', 'Am7']
melody = [[74, 72, 69], [71, 74], [76, 72], [72, 69]]  # the melody's pitches in each bar
bass = [[38], [43], [36], [45]]
pad = voice_lead(chords, voices=4, low=52, high=76, against=[m + b for m, b in zip(melody, bass)],
                 ceilings=[min(m) - 3 for m in melody])
for bar, voicing in enumerate(pad):
    for pitch in voicing:  # a whole-note pad; a piano part would break the chord into its own rhythm
        note('pad', pitch, on=bar * 4, duration=4)  # your composition script's own note helper
```

Here the pad stays under the tune (A3 C4 D4 F4 under a line from A4 to E5), and under the tune's C5 it plays C△7 as
a C major triad, G3 C4 E4 G4: its B would rub a minor ninth under that C. Measured without a melody: a ii-V-I moves three semitones per change
(A to G and C to B, then F to E and D to C), and an I-V-vi-IV loop five to seven, against seven to 28 for the same
chords as root-position blocks.

## Sources

- Caplin, W. E. (1998). *Classical Form: A Theory of Formal Functions for the Instrumental Music of Haydn, Mozart, and
  Beethoven*. Oxford University Press. Fragmentation and liquidation toward a cadence.
- Chmiel, A. and Schubert, E. (2017). Back to the inverted-U for music preference: a review of the literature.
  *Psychology of Music* 45(6), 886-909. https://doi.org/10.1177/0305735617697507
- Garcia, L.-M. (2005). [On and On: Repetition as Process and Pleasure in Electronic Dance Music](https://www.mtosmt.org/issues/mto.05.11.4/mto.05.11.4.garcia.html).
  *Music Theory Online* 11(4).
- Hoffmann, R. [Low Interval Limits](https://www.robin-hoffmann.com/dfsb/low-interval-limits/). An arranger's chart;
  Sweetwater's [glossary](https://www.sweetwater.com/insync/low-interval-limit/) gives a close table. Guides, not laws.
- Huron, D. (2001). Tone and voice: a derivation of the rules of voice-leading from perceptual principles. *Music
  Perception* 19(1), 1-64. https://doi.org/10.1525/mp.2001.19.1.1
- Israels, C. [The Piano and the Art of Jazz Accompaniment](https://chuckisraelsjazz.com/blogs/news/the-piano-and-the-art-of-jazz-accompaniment).
  Chuck Israels Jazz Orchestra. The comping register; commentary on the melody, chords placed against the bass.
- Longuet-Higgins, H. C. and Lee, C. S. (1984). The rhythmic interpretation of monophonic music. *Music Perception*
  1(4), 424-441. https://doi.org/10.2307/40285271
- Matthews, T. E., Witek, M. A. G., Heggli, O. A., Penhune, V. B. and Vuust, P. (2019). [The sensation of groove is
  affected by the interaction of rhythmic and harmonic complexity](https://doi.org/10.1371/journal.pone.0204539).
  *PLoS ONE* 14(1), e0204539.
- McAdams, S., Goodchild, M. and Soden, K. (2022). [A Taxonomy of Orchestral Grouping Effects Derived from Principles
  of Auditory Perception](https://doi.org/10.30535/mto.28.3.6). *Music Theory Online* 28(3).
- Owsinski, B. [A look at the 5 song arrangement elements](https://bobbyowsinskiblog.com/song-arrangement-elements/).
  An excerpt from *The Music Producer's Handbook*, 2nd edition.
- Schoenberg, A. (1967). *Fundamentals of Musical Composition*, ed. G. Strang and L. Stein. Faber and Faber. Varying a
  motive by its rhythm, its intervals, sequence and fragmentation.
- Senior, M. (2020). [Mix Rescue: Rearranging](https://www.soundonsound.com/techniques/mix-rescue-rearranging).
  *Sound On Sound*, March 2020. Staggering the entries of sustained parts.
- Senior, M. (2024). [Mix Rescue: Strong Arrangements](https://www.soundonsound.com/techniques/mix-rescue-strong-arrangements).
  *Sound On Sound*, May 2024. Layers reserved for later sections.
- Senn, O., Kilchenmann, L., von Georgi, R. and Bullerjahn, C. (2016). [The effect of expert performance microtiming on
  listeners' experience of groove in swing or funk music](https://doi.org/10.3389/fpsyg.2016.01487). *Frontiers in
  Psychology* 7, 1487.
- Smith, J. W. (2021). [The Functions of Continuous Processes in Contemporary Electronic Dance Music](https://mtosmt.org/issues/mto.21.27.2/mto.21.27.2.smith.html).
  *Music Theory Online* 27(2). Cites Snoman, R. (2019), *The Dance Music Manual*, 4th ed., pp. 327-28, for new sounds at
  phrase downbeats.
- Solberg, R. T. (2014). ["Waiting for the Bass to Drop": Correlations between Intense Emotional Experiences and
  Production Techniques in Build-up and Drop Sections of Electronic Dance Music](https://dj.dancecult.net/index.php/dancecult/article/view/451).
  *Dancecult* 6(1).
- Summach, J. (2011). [The Structure, Function, and Genesis of the Prechorus](https://mtosmt.org/issues/mto.11.17.3/mto.11.17.3.summach.html).
  *Music Theory Online* 17(3).
- Tan, I., Lustig, E. and Temperley, D. (2019). Anticipatory syncopation in rock: a corpus study. *Music Perception*
  36(4), 353-370. https://doi.org/10.1525/mp.2019.36.4.353
- Tymoczko, D. (2011). *A Geometry of Music: Harmony and Counterpoint in the Extended Common Practice*. Oxford
  University Press.
- Witek, M. A. G., Clarke, E. F., Wallentin, M., Kringelbach, M. L. and Vuust, P. (2014). [Syncopation, body-movement
  and pleasure in groove music](https://doi.org/10.1371/journal.pone.0094446). *PLoS ONE* 9(4), e94446.

These say what listeners and analysts found in particular repertoires and experiments. They support the questions and
the moves above; they are not a recipe that makes a piece good. Listening decides.
