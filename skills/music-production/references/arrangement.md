# Musical decisions that change the result

Each piece of guidance below names its source. Findings marked "measured here" come from this skill's own test pieces and corpus analyses; they are observations, not general rules.

Contents: [Diagnose the "one finger" complaint](#diagnose-the-one-finger-complaint) · [Form before surface detail](#form-before-surface-detail) · [Melody and harmony](#melody-and-harmony) · [Roles and playability](#roles-and-playability) · [Vertical hygiene across parts](#vertical-hygiene-across-parts) · [Describe the score: studio.py profile](#describe-the-score-studiopy-profile) · [Articulation and sampled instruments](#articulation-and-sampled-instruments) · [Applied evidence from the first corpus](#applied-evidence-from-the-first-corpus) · [Sources](#sources)

## Diagnose the "one finger" complaint

Separate three possibilities. A melody may lack an arc despite flawless timing. A good line may be rendered as disconnected taps by short gates, inappropriate attacks or excessive gaps. A reasonable melody and performance may still sit over an accompaniment that does not support it. Fix the responsible layer and keep the others unchanged while you compare.

- **Phrase.** A phrase moves toward a goal (Open Music Theory) and usually ends by resting, holding or resolving, in vocal music where a singer breathes (Perricone 2000). Find each phrase's arrival and its breath. If every phrase begins alike and ends on the same scale degree, compare the period: its first phrase ends on a weaker cadence and its second on a stronger one ([climax-and-melody.md](climax-and-melody.md)).
- **Connection.** Compare the score's end of a note, the key release, the next attack and the audible tail separately. A piano can sound connected through the pedal after the key is released. A sampled sustained instrument may need overlapping notes, but overlap alone does not create recorded legato transitions.
- **Accompaniment.** Give the texture a job of its own. Israels has a comping piano play commentary on the melody rather than double its rhythms. Owsinski's fills answer the lead, and his rhythm element plays against the foundation ([sound-selection.md](sound-selection.md)). Parts in different registers or timbres are heard as separate streams (McAdams, Goodchild and Soden 2022).

## Form before surface detail

For each section, record a short function, the foreground part, the harmonic destination and the one or two things that change. A full form may be song-based, through-composed, ternary, rondo-like or something else: use the brief, not a universal verse and chorus template. [development-and-groove.md](development-and-groove.md) turns this into an energy plan and lists, with their sources, the moves that vary a return or a loop.

Sources describe several ways a form develops:

- **Fewer repeats.** Senior (2024) shortened a song by removing repeats that had gone stale, and held layers back for later sections.
- **A theme handed to another instrument, and strong contrasts at section boundaries.** McAdams, Goodchild and Soden (2022) describe both: the first as timbral shifts, the second as contrasts of register, texture and instrumentation.
- **A build into the chorus.** A prechorus builds toward its chorus through register, phrasing, the length of units and harmonic rhythm (Summach 2011).
- **A motive varied.** Its rhythm changed, its intervals widened or narrowed, sequenced or fragmented (Schoenberg 1967).

A game loop has no ending: its last bar leads back into its first, and the seam is written like any other join ([game-music.md](game-music.md)).

## Melody and harmony

Write a motif in actual pitches and rhythm, not only a chord progression, and check its contour at phrase scale: where it rises, holds, falls and rests ([climax-and-melody.md](climax-and-melody.md)):

- the arch of folksong phrases (Huron 1996);
- the turn after a leap (von Hippel and Huron 2000);
- the sequences Sloboda found under tears.

Arrivals and held notes (cadences, predominants and colour chords are in [harmony.md](harmony.md)):

- **Arrivals.** Anchor important arrivals in the harmony.
- **Notes outside the chord** embellish chord tones (Open Music Theory):
  - passing and neighbour tones move by step;
  - an appoggiatura usually takes the strong part of a beat;
  - a suspension is held over the change and resolves down by step.
- **A held note crossing a chord change** becomes one of four things:
  - a common tone;
  - a suspension that resolves;
  - an extension of the new chord, voiced above its seventh (Open Music Theory, Jazz Voicings);
  - a new chord tone reached by step.

**Voicing chords by their actual parts** (Open Music Theory, Jazz Voicings):

- **Spacing.** Wide intervals low and close ones high, after the harmonic series; close intervals placed low sound muddy. Low interval limits give the lowest pitch for each close interval (Hoffmann, in [development-and-groove.md](development-and-groove.md)); `review` lists close intervals under them.
- **Doubling.** Double the bass note or the root.
- **Omitting tones.** Leave out the fifth first, and the root where a bass plays it.
- **Motion.** Give each voice the shortest way to its next note: common tones held, then steps. Use leaps sparingly, for contrast.
- **Slash chords.** A slash chord names the bass note. It does not make that note the root of a new guitar chord.
- **Staggered changes.** When every sustained part changes on the downbeat, the change draws the ear less than when some parts move on other beats (Senior 2020).
- **The tool.** `musiclib.voicing.voice_lead` finds such voicings for a whole progression ([development-and-groove.md](development-and-groove.md)).

A close upper chord tone can distract from the tune even when the chord symbol is correct. Kovarsky (Yamaha) discusses how accompaniment register interacts with the tune, and Israels keeps piano comping mostly below the lead's register ([anime-opening.md](anime-opening.md)). Inspect the clash's actual register and duration. Moving a colour tone inward, or thinning the support, can clarify the foreground without removing the harmony.

## Roles and playability

- **How many parts at once.** Plan which parts play when, not a number of tracks. Owsinski advises that usually no more than four arrangement elements play at once ([sound-selection.md](sound-selection.md)).
- **Ranges.** Give the lead and the parts that answer it ranges of their own (Israels; McAdams, Goodchild and Soden 2022).
- **Melody on top, rhythm in the bass.** The ear follows the pitch of the highest voice and the timing of the lowest best (Hove, Marie, Bruce and Trainor 2014, in [sound-selection.md](sound-selection.md)). Keep the accompaniment under the lead (`ceilings` in `musiclib.voicing`) and let the bass and kick carry the rhythm.
- **Playability.** Keyboard parts have two hands. Guitar voicings and strum order follow the strings. A General MIDI patch makes a sound, but it does not show the part could be played. If an idiomatic guitar part cannot be rendered convincingly, simplify its articulation, change the lead instrument, or say what the mockup cannot do.

**Drums** (Dow 2010):

- A drummer has four limbs. Two toms do not sound together with a ride, a crash and the hi-hat, and hi-hats usually stop during a tom fill.
- Patterns change from section to section, for example from hi-hat in the verse to ride in the chorus.
- A small fill at the end of an eight-bar section leads into the next.
- Velocities vary with intent rather than at random: a little harder toward the end of a bar or of a verse, the last snare before a chorus harder, every other hi-hat hit softer for the weaker hand.
- Ghost notes are quiet hits between the main ones.

Timing: listeners rated an expert drummer's microtiming and a quantized version as alike in groove, and exaggerated deviations worse (Senn et al. 2016, in [development-and-groove.md](development-and-groove.md)).

For a featured solo or a pickup into a chorus, try removing competing attacks before raising the foreground: thin the clav and guitar behind a Rhodes solo, clear the last rhythmic attacks under a chorus pickup. [Ableton's subtractive-arranging discussion](https://makingmusic.ableton.com/arranging-as-a-subtractive-process) presents this as an alternative working method, not a requirement to fill every track first.

## Vertical hygiene across parts

Each part can be voiced correctly on its own while the ensemble still rubs. Measured here, in the first draft of one test piece:

- strings put F♯3 under the piano's G3 on G△7;
- a held F♯ sat under the melody's G;
- 153 cross-part minor seconds and ninths in all, none visible part by part.

The practice behind the fixes: a tone a semitone above a chord tone (a minor ninth above it, an octave higher) is the jazz "avoid note", heard as a dissonance. An F over a C major chord sits a semitone above its third (Wikipedia, Avoid note, citing Nettles 1987 and Terefenko 2017). A voicing leaves out a tone that would clash too strongly with a more important member of the chord (Open Music Theory, Jazz Voicings). What fixed that piece:

- **Voice parts in dependency order:** foreground, bass, rhythm guitars, held strings, pads, piano, accents. Each later voicing avoids a minor second or minor ninth against anything already sounding.
  - Prefer dropping a colour tone, or moving the seventh above the root, to keeping a complete chord that clashes.
  - A major seventh above the root is fine. The seventh a semitone under the root is not.
- **Anticipations.** A lead anticipation (the next bar's note arriving on the last eighth) is heard as belonging to the next beat (Tan, Lustig and Temperley 2019). It clashed with the old chord where it lay a semitone from one of its tones (D over A7's C♯). Moving the bass, guitars, comping and held strings to the new chord on that eighth removed the clash.
- **Bass approach notes.** In that piece a chromatic approach (A♯ into B) rubbed against the chord held above it and against anticipated melody notes. A whole step from a tone of the current chord (B down to A, G down to F♯) kept the motion without the rub.
- **A sub layer.** A sub layer under the sampled bass followed the bass line's own notes, approaches included, rather than holding the root under them. Senior (2020) likewise replaced a bass synth's fundamental with a dedicated sub patch.

After these changes `review` reported zero part-to-part collisions in that piece. The four that remained were deliberate passing tones of the melody over a held chord. Measure, then decide each case musically.

## Describe the score: `studio.py profile`

`profile` reads the written notes (not the audio). The descriptors follow Yang and Lerch (2020, *Neural Computing and Applications* 32). They describe; they do not judge.

- **Per part:**
  - note density, register, and pitch-class use and entropy;
  - the top line's intervals: steps, leaps, direction changes, recurring cells;
  - inter-onset intervals and note lengths;
  - off-beat and downbeat onsets;
  - how often a bar repeats an earlier bar's rhythm;
  - velocity spread and polyphony.
- **Per section:** every part's density, and the melody's median and highest note.

Use them to check the plan against the score:

- Does the melody climb where the form says it should?
- Does density grow into the high point and thin out where the music should breathe?
- Does the melody state and restate its ideas ([climax-and-melody.md](climax-and-melody.md))?

Compare the profiles of two versions to see what a revision changed. A figure out of line with the plan is a question to answer by listening, not a fault to fix by number.

## Articulation and sampled instruments

- **Sampled strings.** Measured here, sampled section strings start slowly ([soundbank-measurements.md](soundbank-measurements.md) lists each patch's measured attack), and their sustain recordings blur eighth-note lines. Give short notes to a spiccato or staccato patch and long notes to sustain, as separate parts. Start each part early by its measured attack (`offset_ms`).
- **Open hats.** Kits without a hi-hat choke group cannot cut an open hat short. In those kits, write closed hats on the offbeats and let an open hat lead into a crash.

## Applied evidence from the first corpus

Measured here, on CC0 OpenScore editions and the Groove MIDI Dataset:

- Schubert, *An die Musik*, OpenScore `lc6180725`: the written voice has 63 noteheads in 23 measures while the upper piano staff has 499. This is a concrete example of differing layer activity, not a rule to use this ratio.
- Schubert, *Gretchen am Spinnrade*, `lc7111114`: the piano's repeating figure occupies far more events than the voice, and the voice reuses short interval shapes at multiple locations. An active accompaniment can carry continuity beneath a slower foreground.
- Clara Schumann, *Liebst du um Schönheit*, `lc5000397`: the voice's four-interval candidate `[0, 0, 5, -5]` appears at linear measure positions 3, 11, 19 and 27. Recurrent cells can anchor several phrases while their surroundings change. This is an interval-match observation, not proof that every candidate is the same theme.
- The 80-file GMD focus subset contains separate low and high velocity populations and style- and player-dependent timing distributions. Apply accent roles and intentional placement, not the dataset's raw velocity scale or residual variance unchanged to a different soundfont.

These observations informed original decisions in the project's own pieces. No reference melody or groove sequence was copied. Score MIDI is not evidence of a human performance. Measure positions in corpus analyses are written sequence positions, without unfolding repeats.

Close reading matters more than aggregate counts:

- **Clara Schumann, `lc5000397`.** The recurring five-pitch cell at positions 3–4 and 11–12 keeps its pitches. Its opening changes from a two-beat note to a one-beat rest plus three shorter notes. When developing a return, compare pitch identity, entry, duration and closure separately.
- **Haydn, `sq12772795`.** The opening four long notes return an octave higher at positions 5–6, while the response that follows them changes. A restrained, recognisable theme can support a more active response.

These are observations of the CC0 OpenScore editions, not universal prescriptions or copied material.

## Sources

- Dow, R. (2010). [Programming Realistic Drum Parts](https://www.soundonsound.com/techniques/programming-realistic-drum-parts). *Sound On Sound*, September 2010. Four limbs, patterns per section, a fill at the end of an eight-bar section, velocities with intent, ghost notes.
- Friberg, A. [A Quantitative Rule System for Musical Performance](https://www.speech.kth.se/music/publications/thesisaf/sammfa2nd.htm). KTH. Phrase-level and ensemble expression; only the web summary is the cited reading.
- Gillick, J. et al. (2019). [Learning to Groove with Inverse Sequence Transformations](https://proceedings.mlr.press/v97/gillick19a.html). *ICML 2019*. The Groove MIDI Dataset; we used the dataset and a descriptive analysis, not their model or training code.
- Gotham, M. et al. *Open Music Theory*, version 2: [The Phrase, Archetypes, and Unique Forms](https://viva.pressbooks.pub/openmusictheory/chapter/phrase-archetypes-unique-forms/), [Embellishing Tones](https://viva.pressbooks.pub/openmusictheory/chapter/embellishing-tones/), and Lavengood, M., [Jazz Voicings](https://pressbooks.nebraska.edu/openmusictheory/chapter/jazz-voicings/) (spacing, doubling, omitted tones, smooth voice leading).
- Israels, C. [The Piano and the Art of Jazz Accompaniment](https://chuckisraelsjazz.com/blogs/news/the-piano-and-the-art-of-jazz-accompaniment). Chuck Israels Jazz Orchestra.
- Kovarsky, J. [Playing Well With Others](https://hub.yamaha.com/keyboards/k-how-to/playing-well-with-others/). Yamaha. Accompaniment and register; no audio or notation from the article is bundled.
- McAdams, S., Goodchild, M. and Soden, K. (2022). [A Taxonomy of Orchestral Grouping Effects Derived from Principles of Auditory Perception](https://doi.org/10.30535/mto.28.3.6). *Music Theory Online* 28(3).
- Owsinski, B. [A look at the 5 song arrangement elements](https://bobbyowsinskiblog.com/song-arrangement-elements/). An excerpt from *The Music Producer's Handbook*, 2nd edition.
- Perricone, J. (2000). *Melody in Songwriting*. Berklee Press. The [Chapter 1 excerpt](https://online.berklee.edu/takenote/conjunct-disjunct-melody-basic-definitions/).
- Schoenberg, A. (1967). *Fundamentals of Musical Composition*. Faber and Faber. Varying a motive.
- Senior, M. (2020). [Mix Rescue: Rearranging](https://www.soundonsound.com/techniques/mix-rescue-rearranging). *Sound On Sound*, March 2020.
- Senior, M. (2024). [Mix Rescue: Strong Arrangements](https://www.soundonsound.com/techniques/mix-rescue-strong-arrangements). *Sound On Sound*, May 2024.
- Summach, J. (2011). [The Structure, Function, and Genesis of the Prechorus](https://mtosmt.org/issues/mto.11.17.3/mto.11.17.3.summach.html). *Music Theory Online* 17(3).
- [Avoid note](https://en.wikipedia.org/wiki/Avoid_note). Wikipedia, read 7 November 2026, citing Nettles, B. (1987), *Harmony 3*, Berklee College of Music, and Terefenko, D. (2017), *Jazz Theory: From Basic to Advanced Study*, 2nd ed., Routledge.
- Yang, L.-C. and Lerch, A. (2020). [On the evaluation of generative models in music](https://doi.org/10.1007/s00521-018-3849-7). *Neural Computing and Applications* 32, 4773–4784. The score descriptors `profile` reports.
- [University of Puget Sound, The Period](https://musictheory.pugetsound.edu/mt21c/PeriodForm.html), and Ableton / Dennis DeSantis, [Mutation Over Generations](https://makingmusic.ableton.com/creating-variation-2-mutation-over-generations) (change a meaningful dimension while keeping an identifiable relationship). No exercises or examples are bundled.

These are observations about particular pieces and datasets, not a universal style model. Pop, rock, chamber music and anime-style scoring still need different groove, harmonic, instrumental and sound-design choices.
