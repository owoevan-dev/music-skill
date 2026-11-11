# High points, emotion and melody

Read this when planning a piece's high point or a theme's return, writing a melody, orchestrating so that a line stands out or parts blend, or when a piece is correct but does not move anyone. The research below links particular musical events to strong responses in listeners. None of it guarantees a response: listeners differ, and every finding is a tendency, not a recipe. Use it to choose what to try, then listen.

## What goes with strong responses

- **Tears and shivers.** Sloboda (1991) asked listeners to recall a physical response to music and to find its place in the score. Tears went most reliably with melodic appoggiaturas and with sequences; shivers with new or unexpected harmonies.
- **Chills.** Grewe, Nagel, Kopiez and Altenmüller (2007) found that chills followed no simple stimulus and response; the entry of a voice and changes in volume were the patterns listeners reacted to most. Guhn, Hamm and Zentner (2007) linked chill passages to the interplay of solo and accompanying instruments and, sometimes, to an expansion of the overall frequency range (both as summarised by Bannister and Eerola 2018).
- **The passage causes them.** Bannister and Eerola (2018) removed the passages that listeners had named as giving chills from three pieces (in one, a gradual increase in loudness). Chills became significantly rarer in all three. The continuously rated intensity was higher in the chill passages, and in two of the pieces it followed loudness, brightness and roughness. Their review of earlier studies links chills most often to dynamic changes and crescendos.
- **Adding and taking away.** Goodchild, Wild and McAdams (2019) played listeners orchestral gestures. As instruments were added gradually, rated intensity rose steadily with the texture and loudness; a sudden addition made it jump; and after a reduction, gradual or sudden, intensity stayed high for a while instead of falling with the music.
- **Expectation.** Huron (2006) explains much of this through expectation: when an expectation is violated, a quick worst-case reaction produces the chill, and a slower appraisal in the safety of listening turns it into pleasure (as summarised by Bannister and Eerola 2018). For gradual increases in loudness, Bannister and Eerola suggest auditory looming may play a part: a sound that keeps growing louder seems to approach.

## Planning a high point

1. **Place it.** Decide which bar it lands on and build toward it: a gradual addition of instruments raises intensity steadily, and a sudden addition at the arrival makes it jump (Goodchild, Wild and McAdams 2019, above).
2. **Hold things back.** Keep the melody's highest sustained note, the fullest texture, the widest range and the loudest dynamic for the high point. If the music has already been there, it cannot arrive.
3. **Combine three or four devices** from the findings above:
   - a crescendo carried by instruments entering one after another;
   - a new voice or instrument entering on the arrival (horns, a choir-like pad, a solo line taking over);
   - the range opening up: the melody rising to its peak, the bass dropping to a low register, or both;
   - an unexpected harmony at the arrival or just before it: a deceptive cadence that delays the tonic, ♭VI or ♭VII in major, a chromatic mediant, a modulation;
   - an appoggiatura on the melody's peak note, falling by step into the chord;
   - solo and full ensemble answering each other;
   - more brightness: cymbals, upper octaves, open filters.
4. **Prepare it.** A moment of reduction just before (a thinner bar, a held chord, a breath of silence) makes the arrival a contrast; anime choruses and dance drops use the same move ([anime-opening.md](anime-opening.md), [electronic.md](electronic.md)).
5. **After it, let it settle.** Listeners stay moved after the music gets quieter, so a calm, slowly thinning passage after the peak works, and a busy new section straight away throws that away.

Check it: `analyze` should show the high point as the loudest and brightest section, and `profile` the melody's highest note and the greatest density there. For orchestra, write the crescendo as `performance.dynamics` curves ([orchestration.md](orchestration.md)) and broaden the tempo into the arrival with `clock.rubato` or the tempo map.

## Melody

- **Steps, leaps and turning back.** Melodies move mostly by small intervals. A leap is usually followed by a turn in the opposite direction, and von Hippel and Huron (2000) showed why: leaps tend to land near the edge of a melody's range, from where most notes lie back toward the middle. So after a leap toward the top or bottom of the range, turn back, often by step; a leap toward the middle can go on in the same direction.
- **Implication and realisation.** In Narmour's (1990) model a small interval implies another small one in the same direction, and a large interval implies a turn and a smaller interval. Meeting these implications most of the time makes a line easy to follow; denying one at a point of emphasis gives that point weight.
- **Arches.** Phrases in Western folksongs most often rise and then fall (Huron 1996). Let a phrase climb to its peak and come down to rest, and let the phrases of a section build to the section's peak in the same way.
- **Appoggiaturas and sequences.** The two devices Sloboda found most often under tears: a dissonance on a strong beat resolving by step (4–3, 9–8, 7–8 in the melody), and a motif repeated at a step or a third higher or lower, two or three times, before it breaks off.
- **A motif first.** Write the motif in real pitches and rhythm and test it against the bass ([arrangement.md](arrangement.md)). A varied repetition that keeps the contour is heard as the same idea; a new contour is heard as a contrasting one (Open Music Theory).

### Writing a melody that sounds composed

The sources below describe what such a melody has: an idea that returns, phrases that breathe, and a common overall shape with a detail of its own. A line of chord tones in running eighths, new in every bar, has none of them.

1. **The hook.** Write the chorus's opening idea, or the riff, first: it is the motif (A motif first, above).
   - Perricone (2000) names what gives a melody character: its rhythm, its contour, its tonal makeup and its intervals.
   - Jakubowski, Finkel, Stewart and Müllensiefen (2017) compared 100 songs often named as earworms with 100 matched for chart success and style. The earworms had more common overall contours, less common interval patterns (unexpected leaps, or more repeated notes than usual), and faster tempi.
   - One of the most common contours rises in its first phrase and falls in its second (the publisher's summary of that study), as folksong phrases most often do (Huron 1996, Arches above).

   Test it against the bass before writing the rest (A motif first, above).
2. **Phrase like a singer** (Perricone 2000):
   - a phrase usually ends by resting, holding or resolving, and in vocal music where a singer breathes;
   - short phrases group into longer ones;
   - most vocal melodies move by step, and it is usually their leaps that give them character and make them memorable.

   He asks of a line written for the voice whether the singer has time to breathe between phrases, and whether a phrase is too long for one breath.
3. **Build each section from restatement.** State an idea, restate it, depart, conclude: the srdc pattern (statement, restatement, departure, conclusion) that Summach (2011) traces through pop forms after Everett (1999). In classical terms this is the sentence (Caplin 1998). Its presentation is a basic idea, often two bars long, and its repetition. A continuation follows and drives to a cadence.
   - **Restate with a change.** The idea usually comes back changed. One that keeps the contour is heard as a varied repetition; one with a new contour is heard as a contrasting idea (Open Music Theory). A sequence repeats the idea a step or a third higher or lower (Sloboda, above).
   - **Depart by fragmenting.** Fragmentation means units shorter than the basic idea. A continuation often adds sequences and chords that change faster than before (Open Music Theory).
4. **Contrast the sections.** A chorus intensifies over its verse with a fuller or busier texture, a higher melody, or both (Summach 2012, in Open Music Theory, Verse-Chorus Form). Summach lists register, phrasing, the length of units and harmonic rhythm among the devices that build a prechorus toward its chorus.
5. **Tension and rest.**
   - **Notes outside the chord** embellish chord tones (Open Music Theory):
     - an appoggiatura is leapt to and left by a step the other way, and usually takes the strong part of a beat;
     - a suspension, a held note resolving down by step, always does;
     - an escape tone and an anticipation usually fall on weaker parts.

     Sloboda found appoggiaturas most often under tears (above).
   - **Pair phrases as question and answer**, the antecedent and consequent of a period (Caplin 1998; Open Music Theory):
     - the first closes on the weaker cadence, as a rule a half cadence, on V;
     - the second closes on a stronger one, as a rule the perfect authentic cadence, with 1 in the melody over the tonic;
     - when the melody ends on 3 or 5 over the tonic, the authentic cadence is imperfect.
   - **Anticipations.** A melody note that anticipates a downbeat is heard as belonging to that beat (Tan, Lustig and Temperley 2019, in [development-and-groove.md](development-and-groove.md)). It is the next chord's tone heard early, over the old chord (Open Music Theory, Embellishing Tones); the band can stay on the beat, or push with it where the arrangement wants a joint push or the early note rubs against the old chord (`review` lists such rubs).
6. **Save the peak.** Keep the melody's highest note for the high point (Planning a high point, above).
7. **Check the figures.** `profile` reports, per section, the melody's phrases and its longest run without a breath, its leaps, how many bars restate an earlier bar's rhythm and contour, and where its peak falls. `review` asks about a section of eight bars or more in which no bar restates another. The figures show what the line does, not whether it is good: listen.

## Orchestration: what blends and what stands out

McAdams, Goodchild and Soden (2022) classify orchestral effects by the auditory grouping that produces them:

- **Blend (concurrent grouping).** Instruments fuse into one event when their notes start together, their partials line up and their spectra overlap, and parallel motion in pitch and dynamics strengthens the fusion. In timbral augmentation one instrument stays recognisable and the others colour it (a flute doubling violins an octave up); timbral emergence is the case where the mixture is heard as a new sound, none of its parts. Instruments that start apart or differ widely stay separately audible (heterogeneity). To make a line richer without making it two lines, double it in unison or octaves with notes that start together.
- **Streams and layers (sequential grouping).** Successive notes of similar timbre and register join into one line; differences in timbre and register split them into separate streams; and layers of different prominence form a foreground and a background. For counterpoint to be heard as counterpoint, give each line its own timbre or register; for a melody to sit in front, keep its timbre apart from the accompaniment's.
- **Contrast and progression (segmental grouping).** A change of instrumentation divides the music into units: phrases answered by another section (antiphony), a figure echoed in another colour. Over a longer span a planned progression of timbres, adding or changing instruments section by section, gives a form its dramatic shape.

## Sources

- Sloboda, J. A. (1991). Music structure and emotional response: some empirical findings. *Psychology of Music* 19(2), 110–120.
- Grewe, O., Nagel, F., Kopiez, R. and Altenmüller, E. (2007). Listening to music as a re-creative process: physiological, psychological, and psychoacoustical correlates of chills and strong emotions. *Music Perception* 24(3), 297–314.
- Guhn, M., Hamm, A. and Zentner, M. (2007). Physiological and musico-acoustic correlates of the chill response. *Music Perception* 24(5), 473–484.
- Bannister, S. and Eerola, T. (2018). [Suppressing the Chills: Effects of Musical Manipulation on the Chills Response](https://doi.org/10.3389/fpsyg.2018.02046). *Frontiers in Psychology* 9, 2046.
- Goodchild, M., Wild, J. and McAdams, S. (2019). Exploring emotional responses to orchestral gestures. *Musicae Scientiae* 23(1), 25–49.
- Huron, D. (2006). *Sweet Anticipation: Music and the Psychology of Expectation*. MIT Press.
- von Hippel, P. and Huron, D. (2000). Why do skips precede reversals? The effect of tessitura on melodic structure. *Music Perception* 18(1), 59–85.
- Narmour, E. (1990). *The Analysis and Cognition of Basic Melodic Structures: The Implication-Realization Model*. University of Chicago Press.
- Huron, D. (1996). The melodic arch in Western folksongs. *Computing in Musicology* 10, 3–23.
- Jakubowski, K., Finkel, S., Stewart, L. and Müllensiefen, D. (2017). [Dissecting an earworm: Melodic features and song popularity predict involuntary musical imagery](https://research.gold.ac.uk/id/eprint/19405/). *Psychology of Aesthetics, Creativity, and the Arts* 11(2), 122–135. The leaps and repeated notes, and the contour that rises then falls, are from the publisher's [summary](https://www.apa.org/news/press/releases/2016/11/earworms).
- Perricone, J. (2000). *Melody in Songwriting: Tools and Techniques for Writing Hit Songs*. Berklee Press. What gives a melody character, phrases and breathing, steps and leaps, and the questions for a line written for the voice: the [Chapter 1 excerpt](https://online.berklee.edu/takenote/conjunct-disjunct-melody-basic-definitions/).
- Gotham, M. et al. *Open Music Theory*, version 2. VIVA Pressbooks. [Verse-Chorus Form](https://viva.pressbooks.pub/openmusictheory/chapter/verse-chorus-form/) (the chorus's intensity, quoting Summach 2012); [The Phrase, Archetypes, and Unique Forms](https://viva.pressbooks.pub/openmusictheory/chapter/phrase-archetypes-unique-forms/) (the sentence, its varied repetition and continuation; the period); [Embellishing Tones](https://viva.pressbooks.pub/openmusictheory/chapter/embellishing-tones/) (where each falls in the beat); [Introduction to Harmony, Cadences, and Phrase Endings](https://viva.pressbooks.pub/openmusictheory/chapter/intro-to-harmony/) (perfect and imperfect authentic cadences, half cadences).
- Summach, J. (2011). [The Structure, Function, and Genesis of the Prechorus](https://mtosmt.org/issues/mto.11.17.3/mto.11.17.3.summach.html). *Music Theory Online* 17(3). The srdc pattern after Everett (1999); the prechorus's devices.
- Caplin, W. E. (1998). *Classical Form: A Theory of Formal Functions for the Instrumental Music of Haydn, Mozart, and Beethoven*. Oxford University Press. The sentence: presentation, continuation (fragmentation, faster harmonic change), cadence; the period: an antecedent ending with a weak cadence, a consequent with a stronger one.
- McAdams, S., Goodchild, M. and Soden, K. (2022). [A Taxonomy of Orchestral Grouping Effects Derived from Principles of Auditory Perception](https://doi.org/10.30535/mto.28.3.6). *Music Theory Online* 28(3); examples in the [Timbre and Orchestration Resource](https://timbreandorchestration.org/tor/modules/taxonomy/orchestral-grouping-effects/introduction).
