# Harmony and development: function, colour, key and motive

Read this when choosing chords for a phrase, giving a return new harmony, changing key, or developing a motive. Each piece of guidance names its source, most of it Open Music Theory, the peer-reviewed open textbook (Gotham et al.). Style-specific harmony is in the genre guides:
- pop's four-chord schemas: [pop-and-ballad.md](pop-and-ballad.md);
- rock's IV and ♭VII: [rock-and-metal.md](rock-and-metal.md);
- J-pop's royal road and minor-third modulations: [anime-opening.md](anime-opening.md);
- jazz voicings and substitutions in practice: [jazz-and-funk.md](jazz-and-funk.md);
- the baroque rule of the octave and schemata: [baroque.md](baroque.md).

Contents: [Function and the phrase](#function-and-the-phrase) · [Colour: tonicization and mixture](#colour-tonicization-and-mixture) · [Sequences](#sequences) · [Changing key](#changing-key) · [Reharmonizing a return](#reharmonizing-a-return) · [Developing a motive](#developing-a-motive) · [How much harmony chart songs use](#how-much-harmony-chart-songs-use) · [Sources](#sources)

## Function and the phrase

- **A phrase moves toward a cadence.** Open Music Theory analyses a phrase from its ending back:
  - find the phrase end and its cadence;
  - find the strong predominant before it;
  - then work forward from the beginning.

  Composing can follow the same order: decide each phrase's cadence first.
- **Cadences** (Introduction to Harmony, Cadences, and Phrase Endings):
  - a half cadence ends the phrase on V and sounds open;
  - an authentic cadence moves V(7)–I and sounds closed. It is perfect when both chords are in root position and 1 is in the melody over the tonic; otherwise it is imperfect.
- **Strong predominants** (Strengthening Endings with Strong Predominants):
  - a predominant before V strengthens most phrase endings;
  - in the bass this is fa–sol (4–5) at a half cadence, fa–sol–do (4–5–1) at an authentic one;
  - the fa is harmonised with ii6, the more common choice, or IV. Either predicts a dominant.
  - Parallel fifths and octaves are the common part-writing error here.
- **The cadential 6/4** embellishes V: over sol in the bass, a sixth and a fourth resolve to a fifth and a third (6–5, 4–3). Any chord that approaches V can approach it, most often a strong predominant (Strengthening Endings with Cadential 6/4).
- **Smooth connection.** Hold common tones and move the other voices as little as possible (Jazz Voicings). `musiclib.voicing.voice_lead` does this for a progression ([development-and-groove.md](development-and-groove.md)).

## Colour: tonicization and mixture

- **Tonicization** lets a chord other than the tonic be heard, for a moment, as a tonic (Tonicization):
  - it uses applied chords: a secondary dominant V(7)/x or a secondary leading-tone chord viio(7)/x;
  - an applied chord nearly always carries an accidental, usually raising a pitch;
  - it can be read as an altered diatonic chord on the same root: ii with its third raised (II♯) is V/V.
- **Modal mixture** borrows notes from the parallel key (Modal Mixture):
  - major keys borrow from their parallel minor more often than the reverse (me, le, te: ♭3, ♭6, ♭7);
  - it changes a chord's quality, not its function;
  - it can colour a melody, single chords, an extended tonicization or a modulation;
  - borrowed chords on lowered roots are written with a flat (♭VI, ♭VII).
- **In jazz** mixture most often gives ii∅7 for ii7 and a ♭9 added to V7, both with le (♭6) in place of la (Substitutions).
- **In rock**, ♭VII is the most common root outside the major scale (de Clercq and Temperley 2011, in [rock-and-metal.md](rock-and-metal.md)).

## Sequences

- A sequence is a pattern repeated and transposed: a model, usually two chords with their melody, then copies (Diatonic Sequences in Middles).
- **Descending:** falling fifths (the circle of fifths) and falling thirds (the Pachelbel pattern).
- **Ascending:** the ascending 5–6, rising by step.
- **Writing one:** write the whole model, then the first chord of the copy, then follow the model's intervals.
- **Where they go.** The chapter's title places them in the middles of phrases and forms. Sloboda (1991) found sequences among the devices most often under tears ([climax-and-melody.md](climax-and-melody.md)).

## Changing key

- **Modulation** changes the tonic for a longer stretch, in one of two basic ways (Extended Tonicization and Modulation to Closely Related Keys):
  - **direct:** abrupt, straight into the new key;
  - **pivot chord:** subtler, through a chord the two keys share.

  Between them lies the extended tonicization. Cadences establish keys, and a recurring accidental points to a new one.
- **Distant keys** (Chromatic Modulation):
  - mixture supplies extra pivot chords;
  - a single pivot pitch can stand in for a pivot chord;
  - a dominant seventh and a German or Italian augmented sixth are enharmonically equal, so either leads to a key a semitone above or below;
  - a diminished seventh can resolve into four keys.
- **In popular music:**
  - the lift by a half or whole step near the end ([pop-and-ballad.md](pop-and-ballad.md));
  - the minor-third modulation into an anime chorus ([anime-opening.md](anime-opening.md)).

## Reharmonizing a return

A theme that comes back with new chords keeps its identity and changes its colour ([development-and-groove.md](development-and-groove.md)). Substitutions alter a progression without changing where it goes (Substitutions):

- **Applied chords.** A chord that moves by fifth to the next can become the dominant on its root, an applied chord to the next chord: vi–ii becomes VI7–ii, that is V7/ii–ii.
- **Mixture.** Borrow from the parallel key: iv for IV, ♭VI, ii∅7.
- **Tritone substitution.** Replace a dominant with the dominant a tritone away. The two share their tritone, so the substitute resolves the same way: D♭7 for G7 into C.

Keep the melody's notes as chord tones or treated embellishing tones (passing, neighbour, appoggiatura, suspension: [climax-and-melody.md](climax-and-melody.md)). `review` names the notes outside the written chord in every part by these types and asks about those not resolved by step.

## Developing a motive

- **The motive.** A motif is the smallest structural unit with thematic identity. Development alters, repeats or sequences it through a piece, which gives the piece its unity (Wikipedia, Motif).
- **Ways to develop one** (Wikipedia, Development):
  - change its intervals while keeping its rhythm;
  - displace it rhythmically, so its stress falls elsewhere in the bar;
  - sequence it, diatonically or through a succession of keys;
  - work with its fragments, or combine two ideas.
- **Contour.** A varied repetition that keeps the contour is heard as the same idea; a new contour is heard as a contrasting idea (Open Music Theory, The Phrase).
- **In a phrase.** The sentence presents a basic idea twice, then fragments it, with faster harmonic rhythm and often a sequence, toward the cadence ([climax-and-melody.md](climax-and-melody.md), Writing a melody that sounds composed).

## How much harmony chart songs use

Two collections of chord annotations give a measure of how much harmony rock and chart songs use. They are counts of what those songs do, not targets: they say nothing of orchestral music, jazz, game music or electronic styles, and a piece may lie outside them for a reason of its own. Read `review`'s harmonic pace (chord changes a bar, by section) beside them when a piece in these families seems to have too little harmony or too much.

| | Rock songs (200, two analysts averaged) | Chart songs (739) |
|---|---|---|
| What counts as a change | a change of root | a change of chord: root, degrees or bass |
| Changes a bar: median (quartiles) | 0.85 (0.50 to 1.18) | 0.97 (0.69 to 1.33) |
| The same, 10th to 90th percentile | 0.33 to 1.59 | 0.47 to 1.71 |
| Different chords in a song, the bass left out | 5 (3.5 to 6.1), by root and major or minor | 9 (6 to 12), by root and degrees |
| Different roots in a song | 4.5 (3 to 6) | 6 (4 to 7) |
| Root motion, share of a song's changes of root | up a fourth 30, up a fifth 26, up a second 14, down a second 11 | up a fourth 31, up a fifth 23, up a second 15, down a second 11 |
| Kinds of chord, share of a song's chords | not counted | triads 70, sevenths 23, extended 3, added-note 3, altered 1 |

The two columns count different things and are not to be set against each other. What they have in common:
- **About one change a bar, and often fewer.** A quarter of these songs change chord in fewer than every other bar (rock) or two bars in three (charts).
- **A handful of chords.** Half the rock songs use five or fewer, by root and quality; in them I, IV, V, ♭VII and VI are 88 per cent of the chords. A small vocabulary is what this music has, not a fault to correct.
- **Roots move by fourth and fifth** in over half the changes, by step in a quarter.
- **Mostly triads.** In the chart songs seven chords in ten are triads and two are sevenths; extended, added-note and altered chords together are one in fourteen.

How they were taken: each song counts once, by its median or its share, and the table gives the median of the songs (for the shares, their mean). The rock corpus's timed chord lists hold one row for each change of root, so it counts changes of root; the chart annotations write every chord, so they count changes of chord. The rules were written down before the figures were computed. The scripts that computed them are among the project's development records (`research/corpus-0.7`), which the published repository does not hold.

## Sources

- de Clercq, T. and Temperley, D. (2011). [A corpus analysis of rock harmony](https://rockcorpus.midside.com/2011_paper/declercq_temperley_2011.pdf). *Popular Music* 30(1), 47–70. The annotations: [A Corpus Study of Rock Music](https://rockcorpus.midside.com/), version 2.1 (the RS 200), CC BY 4.0; the counts above are this skill's, from the harmonic analyses alone.
- Burgoyne, J. A., Wild, J. and Fujinaga, I. (2011). An Expert Ground Truth Set for Audio Chord Recognition and Music Analysis. *ISMIR 2011*. The annotations: [The McGill Billboard Project](https://ddmal.ca/research/The_McGill_Billboard_Project_(Chord_Analysis_Dataset)/), DDMAL, CC0; the counts above are this skill's.

- Gotham, M., Gullings, K., Hamm, C., Hughes, B., Jarvis, B., Lavengood, M. and Peterson, J. *Open Music Theory*, version 2. VIVA Pressbooks, read 7 November 2026:
  - [Introduction to Harmony, Cadences, and Phrase Endings](https://viva.pressbooks.pub/openmusictheory/chapter/intro-to-harmony/)
  - [Performing Harmonic Analysis Using the Phrase Model](https://viva.pressbooks.pub/openmusictheory/chapter/performing-harmonic-analysis-using-the-phrase-model/)
  - [Strengthening Endings with Strong Predominants](https://viva.pressbooks.pub/openmusictheory/chapter/strong-predominants/)
  - [Strengthening Endings with Cadential 6/4](https://viva.pressbooks.pub/openmusictheory/chapter/cadential-64/)
  - [Tonicization](https://viva.pressbooks.pub/openmusictheory/chapter/tonicization/)
  - [Extended Tonicization and Modulation to Closely Related Keys](https://viva.pressbooks.pub/openmusictheory/chapter/extended-tonicization-and-modulation-to-closely-related-keys/)
  - [Modal Mixture](https://viva.pressbooks.pub/openmusictheory/chapter/modal-mixture/)
  - [Chromatic Modulation](https://viva.pressbooks.pub/openmusictheory/chapter/reinterpreting-augmented-sixth-chords/)
  - [Diatonic Sequences in Middles](https://viva.pressbooks.pub/openmusictheory/chapter/diatonic-sequences/)
  - [Substitutions](https://viva.pressbooks.pub/openmusictheory/chapter/substitutions/)
  - Lavengood, M., [Jazz Voicings](https://viva.pressbooks.pub/openmusictheory/chapter/jazz-voicings/)
  - [The Phrase, Archetypes, and Unique Forms](https://viva.pressbooks.pub/openmusictheory/chapter/phrase-archetypes-unique-forms/)
- de Clercq, T. and Temperley, D. (2011). [A corpus analysis of rock harmony](https://doi.org/10.1017/S026114301000067X). *Popular Music* 30(1), 47–70.
- Sloboda, J. A. (1991). Music structure and emotional response: some empirical findings. *Psychology of Music* 19(2), 110–120.
- Wikipedia, read 7 November 2026: [Motif (music)](https://en.wikipedia.org/wiki/Motif_(music)) and [Development (music)](https://en.wikipedia.org/wiki/Development_(music)), with the sources they cite.
