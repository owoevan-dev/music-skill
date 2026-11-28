# Style map: orchestral and classical

The family of Western art music for orchestra and its ensembles, by the periods the literature describes, and the
orchestral music of film. Read [style-maps.md](style-maps.md) first for the axes and for combining entries; the craft
of each trait is in [orchestration.md](orchestration.md), [baroque.md](baroque.md),
[piano-and-chamber.md](piano-and-chamber.md), [organ.md](organ.md) and [film-score.md](film-score.md).

Contents: [Baroque](#baroque) · [Classical era](#classical-era) · [Romantic](#romantic) ·
[Impressionist](#impressionist) · [Post-tonal](#post-tonal) · [Neoclassical](#neoclassical) ·
[Minimalist](#minimalist) · [Cinematic orchestral](#cinematic-orchestral) · [Treatments by role](#treatments-by-role) · [Sources](#sources)

The periods as Open Music Theory gives them: Baroque about 1600-1750, Classical 1750-1820, Romantic 1800-1910,
post-tonal from 1900 (OMT, Other Aspects of Notation). Source tags: UM is *Understanding Music: Past and Present*
(Clark et al. 2016), by chapter section; OMT is *Open Music Theory*, by chapter; MT21C is Hutchinson's *Music
Theory for the 21st-Century Classroom*, by section.

For the whole family, `review` does not ask about pushes: that question rests on rock and pop melodies (Tan, Lustig
and Temperley 2019), and none of the family's sources describes anticipatory pushes.

## Baroque

Motor rhythm under imitative counterpoint, or a melody over a continuo; concertos set a soloist or a small group
against the orchestra. `orchestral/baroque`

| Axis | Traits | From |
|---|---|---|
| `tempo` | definite, regular rhythm in a meter, the bar line prominent | UM 4.4.2 |
| `harmony` | the major and minor keys, with chord progressions over a basso continuo; galant schemas; the rule of the octave | UM 4.4.2; OMT, Galant Schemas, Rule of the Octave |
| `melody` | a fugue subject answered at the fifth, with a countersubject and episodes; sequences | OMT, High Baroque Fugal Exposition; Diatonic Sequences |
| `rhythm` | "motor rhythm", the beat subdivided without a break | UM 4.4.2 |
| `timbre` | the violin family; a continuo section of harpsichord or organ with cello, viola da gamba or lute; the trio sonata (two melody instruments and continuo); strings at the core, woodwinds and brass doubling the strings or filling the harmony, timpani the only percussion | UM 4.4.2, 4.4.3, 5.4.2 (the orchestra chart) |
| `form` | longer works in several movements of defined forms: ritornello form, binary form; the concerto and the concerto grosso; fugue; ground bass | UM 4.4.2, 4.4.3; OMT, Binary Form, Ground Bass |
| `mix` | terraced dynamics, abrupt changes between loud and soft | UM 4.4.2 |

- **In this skill**: [baroque.md](baroque.md) (counterpoint, schemas, the continuo), harpsichords (`vcsl_keys`) and
  the pipe organ (`organ_vcsl`, [organ.md](organ.md)), VSCO 2 CE strings and winds. The bus chain with
  `"dynamics": "wide"`.
- **Variants**: the chorale and the cantata (block chords on a hymn tune: OMT, Chords in SATB Style); the trio
  sonata; the solo concerto.
- **Neighbours**: Classical era: homophony instead of motor counterpoint, crescendos instead of terraced dynamics.

## Classical era

Tuneful, balanced phrases over a homophonic accompaniment, in forms that set key and theme against each other.
`orchestral/classical-era`

| Axis | Traits | From |
|---|---|---|
| `tempo` | contrasting tempos, between movements and within them | UM 5.4.1 |
| `harmony` | slower harmonic rhythm than the Baroque; the phrase model, cadences, tonicization, and modulation to keys closely related | UM 5.4.2; OMT, Intro to Harmony, Performing Harmonic Analysis Using the Phrase Model, Extended Tonicization |
| `melody` | tuneful melodies in question-and-answer (antecedent and consequent) phrases, shorter than earlier phrases; the sentence and the period | UM 5.4.1, 5.4.2; OMT, The Phrase, Archetypes, and Unique Forms |
| `rhythm` | flexible use of rhythm and rests | UM 5.4.2 |
| `timbre` | the string quartet; the piano; an orchestra of thirty to sixty in strings, woodwinds, brass and percussion: first violins carry the melody, the lower strings accompany, woodwinds give colour and solos (clarinets added by the early nineteenth century), horns and trumpets add volume and fill the harmony but rarely carry the melody, timpani mark loud moments and the pulse | UM 5.4.2 |
| `form` | sonata form, rondo, minuet and trio, theme and variations, the first-movement concerto form | UM 5.4.1; OMT, Sonata Form, Rondo |
| `mix` | crescendos and decrescendos; contrasting dynamics and articulations | UM 5.4.1 |

- **In this skill**: [orchestration.md](orchestration.md), VSCO 2 CE and Iowa strings and winds, the Steinway and the
  other pianos. `review` asks about parallel fifths and octaves, the rule of independent voices this style keeps
  (OMT, First-Species Counterpoint).
- **Variants**: the string quartet; the solo sonata with piano.
- **Neighbours**: Baroque (above); Romantic: longer, more chromatic lines and larger forces.

## Romantic

Songlike melodies over chromatic harmony that delays its resolutions and modulates far; large orchestras and wide
dynamics; music that tells or depicts. `orchestral/romantic`

| Axis | Traits | From |
|---|---|---|
| `tempo` | more rubato and tempo fluctuation within a piece | UM 6.4.1, 6.4.2 |
| `harmony` | more chromatic and dissonant harmony, seventh chords and more, dissonances held before they resolve; modulation between keys of very different pitch content; modal mixture, the Neapolitan, augmented sixths, common-tone diminished sevenths, chromatic mediants, the octave divided equally, triads moving by common tones (neo-Riemannian) | UM 6.4.2; OMT, Modal Mixture, Neapolitan Sixth Chords, Augmented Sixth Chords, Common-Tone Chords, Mediants, Equal Divisions of the Octave, Neo-Riemannian Triadic Progressions |
| `melody` | lyrical, songlike melodies, often with wider leaps; sequences, often as part of a modulation; chromatic notes from outside the key | UM 6.4.1, 6.4.2 |
| `rhythm` | no source read on rhythm itself | |
| `timbre` | larger forces using more registers, dynamics and timbres; orchestras of over fifty, sometimes over a hundred; the piccolo, English horn, tuba and contrabassoon; the modern piano | UM 6.4.1, 6.4.2 |
| `form` | the symphony, concerto and sonata-form movement continued and transformed; the miniature (song, short piano piece); program music, as symphonic poem and as program symphony | UM 6.4.1, 6.4.2 |
| `mix` | wide dynamic ranges, more crescendos and decrescendos | UM 6.4.1, 6.4.2 |

- **In this skill**: [orchestration.md](orchestration.md) (the orchestra's sections, the hall, dynamic layers and
  legato), all orchestral banks; the bus chain with `"dynamics": "wide"`. The banks' winds are listed in
  [soundbanks.md](soundbanks.md); none holds an English horn or a contrabassoon.
- **Variants**: the character piece for piano; the program symphony and symphonic poem.
- **Neighbours**: Classical era (above); Impressionist: modes and parallel chords instead of functional chromaticism;
  Cinematic orchestral: the same language put to picture.

## Impressionist

Tonal music with ambiguous key centres and lush chords, modes and parallel motion, colours over murmuring
figures. `orchestral/impressionist`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | chords with ninths, elevenths and thirteenths, sometimes altered; the church modes (Phrygian, Lydian, Dorian) as an alternative to heavy chromaticism; whole voicings moved in parallel ("planing"), against the old prohibition of parallel fifths and octaves; tonal with ambiguous key centres; the whole-tone collection, whose single step size leaves the centre ambiguous and can sound unsettled, and the pentatonic | MT21C 32.1; UM 7.3.7; OMT, Collections |
| `melody` | melody over murmuring accompaniment figures; songlike and dancelike melodies handed between instruments | UM 7.3.7 (the listening guide) |
| `rhythm` | no source read | |
| `timbre` | new colours; solos for flute and clarinet over strings | UM 7.3.6, 7.3.7 |
| `form` | through-composed | UM 7.3.7 (the listening guide) |
| `mix` | no source read | |

- **In this skill**: harp, flutes, clarinets and strings in the orchestral banks; `musiclib.voicing` voices the
  extended chords; no celesta among the banks. `review` does not ask about parallel fifths and octaves here: planing
  moves them on purpose (MT21C 32.1).
- **Neighbours**: Romantic; Post-tonal, which leaves the tonal centre altogether.

## Post-tonal

Music without a tonal centre or with several at once: angular lines, high dissonance, new rhythms and colours.
`orchestral/post-tonal`

| Axis | Traits | From |
|---|---|---|
| `tempo` | strict meter abandoned for rapidly changing time signatures, bars of five or seven beats; ametric music, polymeter, metric modulation | UM 7.3.3; OMT, Twentieth-Century Rhythmic Techniques |
| `harmony` | dissonance far beyond the nineteenth century; polytonality, two tonal centres at once; atonality, no tonal centre; pitch-class sets; twelve-tone rows and their operations | UM 7.3.2, 7.4; OMT, Pitch-Class Sets, Basics of Twelve-Tone Theory |
| `melody` | angular shapes, wide leaps, unusual phrase structures; melody may yield to texture or rhythm as the main feature | UM 7.3.1 |
| `rhythm` | irregular rhythms, short hard notes; ostinato | UM 7.5 (the listening guide); OMT, Twentieth-Century Rhythmic Techniques |
| `timbre` | new colours from new instruments (synthesizers) or traditional instruments played in new ways | UM 7.3.4 |
| `form` | twelve-tone music avoided repetition | UM 7.7 |
| `mix` | no source read | |

- **In this skill**: the orchestral banks, the orchestral effects of `vsco_colors`; Surge XT for synthesizers. No
  prepared piano and no extended string techniques beyond tremolo, pizzicato and the effects listed in
  [soundbanks.md](soundbanks.md). `review` does not ask about parallel fifths and octaves (the rule belongs to tonal
  voice leading these composers set aside: UM 7.3.2) or about melodies that restate nothing (UM 7.7).
- **Variants**: serial (twelve-tone); rhythmic and percussive, with irregular accents (UM 7.5).
- **Neighbours**: Neoclassical: classical forms and restraint with modern harmony and rhythm.

## Neoclassical

Classical balance, economy and clarity, and forms such as the fugue, concerto grosso and symphony, with modern
harmonies and rhythms. `orchestral/neoclassical`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | modern harmonies, tonal and chromatic elements together | UM 7.6 |
| `melody` | economy of material | UM 7.6 |
| `rhythm` | strongly rhythmic | UM 7.6 |
| `timbre` | no source read | |
| `form` | balance of form and phrase, clarity of design; the fugue, the concerto grosso, the symphony | UM 7.6 |
| `mix` | emotional restraint | UM 7.6 |

- **In this skill**: as for Classical era and Baroque.
- **Neighbours**: Classical era and Baroque (their forms); Post-tonal (its harmony).

## Minimalist

Consonant patterns repeated over a steady meter, changing slowly: by adding to a pattern, or by setting two copies of
it out of phase. `orchestral/minimalist`

| Axis | Traits | From |
|---|---|---|
| `tempo` | a steady meter | UM 7.7 |
| `harmony` | highly consonant, triads; a simple chord pattern repeated throughout | UM 7.7 |
| `melody` | repeated melodic motifs entering over the pattern | UM 7.7 |
| `rhythm` | a steady pattern established at the start; additive process (a pattern repeated with a note added or taken away each time, or each chord lengthened by more subdivisions); phase shifting, one part keeping the pattern while another rotates it a note at a time | UM 7.7; MT21C 35.1, 35.2 |
| `timbre` | ensembles such as mallets, voices, woodwinds and percussion | UM 7.7 |
| `form` | repetition the focus; change only as rhythmic density, texture and range vary very slowly | UM 7.7 |
| `mix` | no source read | |

- **In this skill**: marimba, vibraphone and xylophone (`vcsl`), the pianos, winds; a voice on "ah" (`vocal_ah`). `review` does not ask about loops or nearly alike sections: repetition and slow change
  are the style (UM 7.7; MT21C 35.2).
- **Neighbours**: Post-tonal (the opposite approach to repetition: UM 7.7); electronic styles built on loops.

## Cinematic orchestral

The symphonic language of the nineteenth century set to picture: themes for characters and ideas, fanfares, sweeping
love themes, cadences that carry sentiment or wonder. `orchestral/cinematic`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | the mixed plagal cadence (the minor subdominant to the tonic), carrying Romantic associations of sentiment and the sublime; the chromatically modulating cadential resolution, a cadence begun in one key whose dominant resolves to the tonic of a chromatically related key, associated with wonder; the subtonic half cadence, linked to the Western; a strong tonal centre for heroism, moving toward dissonance for danger | Lehman 2013; UM 7.9.4 |
| `melody` | leitmotifs; heroic themes; sweeping love themes; fanfares built on perfect fourths | UM 7.9.4 |
| `rhythm` | cadences synchronised with the action ("mickey mousing" at the level of the phrase) | Lehman 2013 |
| `timbre` | the full orchestra, trumpets and brass for the fanfare; dense clusters and synthesized sounds for strangeness | UM 7.9.4 |
| `form` | the overture, leitmotifs and incidental music inherited from nineteenth-century opera; the cue shaped to the scene | UM 7.9.4; film-score.md |
| `mix` | under dialogue: [film-score.md](film-score.md) and [scene-music.md](scene-music.md) | |

- **In this skill**: [film-score.md](film-score.md) (scoring to picture, hit points, suspense), the orchestral banks,
  Surge XT for the synthesized colours.
- **Variants**: heroic adventure (fanfare, strong tonic); love theme (sweeping melody, mixed plagal cadences); wonder
  (chromatically modulating cadences); the Western (subtonic half cadences).
- **Neighbours**: Romantic (its language); horror and suspense (its dissonance and clusters).

<!-- treatments, written from style-maps.json -->
## Treatments by role

What published sources document of this family's processing, by a part's role (`treatments` in style-maps.json; `studio.py effects --role <role> --style <entry>` lists the tools, these first). *Usual*: a convention two sources or more corroborate, one saying it is the rule or nearly; *often*: a source speaks of its frequency; *documented*: one session, one engineer's practice or a tutorial. Each says what it was applied to: an entry about one instrument says nothing of the role's others. An entry that holds for some entries of the family names them. Every one was checked against its page ([processing.md](processing.md#choosing-a-parts-treatment)).

- **Melody.** Space (*documented*): sample mock-ups: every part sent to one shared reverb, the samplers' own reverb off, as a first approach (Inglis 2001; Senior 2012).
- **Harmony.** Space (*documented*): sample mock-ups: every part sent to one shared reverb, the samplers' own reverb off, as a first approach (Inglis 2001; Senior 2012); little or no dynamics (*often*): other processing typically minimal: gentle control of loud peaks at most (1.5:1 on the bus on one record) (Senior 2015; Robjohns 1999); correction (*documented*): EQ a last resort, in small moves; a cut near 900 Hz on boxy violins (recorded players) (Senior 2015; Rowcroft 2000); little or no modulation (*documented*): chorus made strings sound artificial and did little for woodwind (a subtle chorus worked on brass) (Rowcroft 2000); space (*documented*): strings in a live room, reverb about 1.5-2.5 s (up to 4 s for a swimmy sound) (Robjohns 1999; Senior 2015).
- **Rhythm.** Space (*documented*): more reverb on the rear sections (percussion, brass), less on the front (Meehan 1999; Rowcroft 2000).
- **Texture.** Colour (*documented*, cinematic): saturation and overdrive on single parts (an electric cello) (D'Silva 2025); sound design (*documented*, cinematic): synths through resonators (Dune); granular plug-ins (another score) (Inglis 2024; D'Silva 2025).

<!-- /treatments -->

## Sources

- Clark, N. A., Heflin, T., Kluball, J. and Kramer, E. (2016). [*Understanding Music: Past and Present*](https://ung.edu/UNIVERSITY-PRESS/_uploads/files/Understanding_Music-Past_and_Present.pdf).
  University of North Georgia Press, CC BY-SA 4.0: the comparison overviews and general trends of the Baroque (4.4),
  the Classical period (5.4), the nineteenth century (6.4) and the twentieth century (7.3-7.9), with their listening
  guides.
- Gotham, M. et al. *Open Music Theory*, version 2 (viva.pressbooks.pub/openmusictheory), CC BY-SA 4.0: the chapters
  named above, among them Hughes on equal divisions of the octave and neo-Riemannian progressions, and Gotham,
  Lavengood, Moseley and Shaffer on collections.
- Hutchinson, R. *Music Theory for the 21st-Century Classroom* (musictheory.pugetsound.edu/mt21c): 32.1 Impressionism,
  35.1 Additive Minimalism, 35.2 Phase Shifting.
- Lehman, F. (2013). [Hollywood Cadences: Music and the Structure of Cinematic Expectation](https://mtosmt.org/issues/mto.13.19.4/mto.13.19.4.lehman.html).
  *Music Theory Online* 19(4).
- Tan, I., Lustig, E. and Temperley, D. (2019), in [development-and-groove.md](development-and-groove.md): pushes in rock
  melodies.
- Inglis, S. (2001). [Mixing Programmed & Real Instruments Successfully](https://www.soundonsound.com/techniques/mixing-programmed-real-instruments-successfully). *Sound On Sound*, September 2001.
- Senior, M. (2012). [Q. How should I treat my sample library orchestral parts?](https://www.soundonsound.com/sound-advice/q-how-should-treat-my-sample-library-orchestral-parts). *Sound On Sound*.
- Senior, M. (2015). [Richard King: How To Record Acoustic Ensembles](https://www.soundonsound.com/people/richard-king-how-record-acoustic-ensembles). *Sound On Sound*, September 2015.
- Robjohns, H. (1999). [Recording Strings](https://www.soundonsound.com/techniques/recording-strings). *Sound On Sound*, April 1999.
- Rowcroft, J. (2000). [Creating Orchestral Arrangements On A Budget](https://www.soundonsound.com/techniques/creating-orchestral-arrangements-budget). *Sound On Sound*, April 2000.
- Meehan, P. (1999). [Creating Orchestral Music With Sampled Instruments](https://www.soundonsound.com/techniques/creating-orchestral-music-sampled-instruments). *Sound On Sound*, March 1999.
- D'Silva, S. (2025). [Evgueni Sacha Galperine](https://www.soundonsound.com/techniques/evgueni-sacha-galperine). *Sound On Sound*, May 2025.
- Inglis, S. (2024). [Dune: Hans Zimmer & Friends](https://www.soundonsound.com/techniques/dune-hans-zimmer-friends). *Sound On Sound*, April 2024.
