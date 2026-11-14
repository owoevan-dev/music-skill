# Jazz, blues, bossa nova and funk: swing, comping, walking bass and the groove

Read this when the request is a jazz combo or big-band-flavoured cue (swing, ballad, bossa nova, jazz waltz), blues (a 12-bar, a shuffle, a slow blues), a cafe or bar scene, funk, pop-funk or city pop, or any piece whose harmony is built from sevenths and extensions. Both styles live in the rhythm section's time: jazz in the swing of the ride cymbal and the walking bass, funk in sixteenth-note parts locked to the downbeat. For lo-fi and hip-hop beats built on the same harmony see [beats.md](beats.md).

The sub-styles of jazz, blues, funk and soul are mapped in [style-map-jazz.md](style-map-jazz.md), and bossa nova with the other Latin American and Caribbean styles in [style-map-latin.md](style-map-latin.md), each on the seven axes with its sources.

Contents: [Brief](#brief) · [Swing and time](#swing-and-time) · [The rhythm section](#the-rhythm-section) · [Writing the head and the solos](#writing-the-head-and-the-solos) · [Funk](#funk) · [Blues](#blues) · [Bossa nova](#bossa-nova) · [Symptoms and causes](#symptoms-and-causes) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

## Brief

Settle these from the request, deciding what it leaves open and saying so:

- **Ensemble.** A piano trio (piano, upright bass, drums) is the core; a quartet adds a horn or guitar. Funk adds electric bass, a rhythm guitar, keys and horns.
- **Feel**, from the sources below (take the tempo from the brief):

  | Style | Feel |
  |---|---|
  | Swing | swung eighths whose ratio falls toward even eighths as the tempo rises (Friberg and Sundström 2002), walking bass |
  | Bossa nova | straight eighths, a syncopated guitar, the bass in a two-feel on 1 and 3 (Wikipedia, Bossa nova; TalkingBass 2019) |
  | Blues | a shuffle over a steady bass line, the backbeat on 2 and 4 (Wikipedia, Blues); a slow blues in 12/8 |
  | Funk | sixteenths, everything on the One (Vincent 1996; Danielsen 2006) |

- **Form.** A jazz performance usually plays the tune (the head), then solos over its chord changes, then the head again, with an intro and an ending or tag. Common tune forms are the 32-bar AABA and the 12-bar blues. A funk track is a groove of two or four bars with a contrasting bridge and breaks.
- **Solos are written.** Nothing improvises here: write each solo as a line that sounds improvised (below).

## Swing and time

Friberg and Sundström (2002) measured jazz recordings and found:
- the drummer's swing ratio on the ride cymbal falls as the tempo rises, from about 3.5:1 at slow tempi to nearly 1:1 around 300 BPM, and the "triplet" 2:1 occurs at only one tempo;
- from medium to fast tempi the short note of each pair stays near 100 ms;
- soloists swing less than the drummer: in medium tempi they land their downbeats after the ride but meet it on the off-beats, which is how a soloist sounds behind the beat without dragging (the KTH group's ensemble-swing rule reproduces this).

Put those into `performance.swing` (unit 0.5 for eighths):
- **Drums and bass**: `ratio` = 1 − 0.1 × BPM / 60, kept between 0.5 and 0.78. That keeps the short note at 100 ms: 0.78 at 120 BPM and below, 0.67 at 200, 0.6 at 240, 0.5 at 300. The formula is this skill's, fitted to Friberg and Sundström's short note of about 100 ms.
- **A soloist** delayed by `d` seconds (`performance.offset_ms`, a few tens of milliseconds, your choice) meets the ride's off-beats with `ratio` = drummer's ratio − `d` / (60 / BPM). At 160 BPM with a 30 ms delay: 0.733 − 0.08 ≈ 0.65.
- **Comping piano or guitar** between the two, or with the drummer.
- Ballads and bossa nova keep straight eighths; give them `musiclib.expression` timing instead.

## The rhythm section

**Bass.** A walking bass plays quarter notes through the changes. The usual construction, as jazz bass teaching gives it: a chord tone on beat 1 (most often the root), chord and scale tones on 2 and 3, and on beat 4 a note a half step above or below the next chord's root, or its fifth, leading into it. Keep the line mostly stepwise, change direction now and then, and let the register drift over a chorus rather than resetting each bar. On ballads, play half notes or roots and fifths; for bossa nova, root on 1 and fifth on the "and" of 2 (dotted quarter and eighth).
- Instruments: `bass_sneaky` (upright bass, finger and stronger plucked layers with round robins; `bank 1` muted, `bank 2` ghost notes). Give it `performance.round_robin` and velocities 60–100.

**Guitar comping.** `guitar_shiny` is an archtop, the jazz guitar: its pickup preset (0:26) for the warm electric sound of jazz comping and chord melodies, the microphone preset (0:25) for an acoustic tone. Comp in four-note chords on the middle strings (sevenths and ninths without the root, the bass has it), short and on the off-beats, or in quarter notes on every beat for a swing rhythm guitar.

**Piano comping.** Pianists voice the left hand without the root, which the bass plays (Levine 1989): the third and seventh at the bottom with the fifth or ninth and thirteenth above, in two shapes that alternate through a progression. The A form stacks 3–5–7–9 and the B form 7–9–3–5, so a ii–V–I in C moves Dm9 F–A–C–E, G13 F–A–B–E, Cmaj9 E–G–B–D with almost no motion; keep these between about C3 and C5. The thirds and sevenths (the guide tones) move by step from chord to chord: let them, and let the top voice make a line. Comp in short, syncopated hits, on the "and" of 2 or 4 and anticipating the next bar, not on every beat; leave space when the soloist plays.
- Instruments: the Steinway grand (`vcsl` 0:0) for the piano ([piano-and-chamber.md](piano-and-chamber.md)); an upright (`vcsl_keys` 0:3) only for a bar room; the TX81Z FM pianos (`vcsl_keys` 0:4, 1:4), a Surge electric piano (`studio.py sounds --role keys --name ep`, or `rhodes`, `wurli`, `suitcase`; with the piece's `--seed`), or `fm_epiano` for an electric piano; `vcsl` vibraphone (0:11) for a vibes comp or melody.

**Drums.** The ride cymbal plays the swing pattern, quarter notes with a swung eighth after 2 and 4, the skip note that leads into 3 and 1 ("ding, ding-a ding, ding-a"); the hi-hat pedal closes on 2 and 4; the bass drum stays soft, with occasional accents; the snare adds light comping figures and ghost notes. Accents and fills mark the ends of choruses and phrases. Use the `rusty` kit at low velocities (ride 51, ride bell 53, pedal hat 44); no sampled jazz kit with brushes is in the banks yet.

## Writing the head and the solos

- **Head.** A melody that can be sung, with syncopation at phrase ends and anticipations of the next chord's tones by an eighth; give the horn `performance.legato` and vibrato on long notes (`vcsl_winds` Tenor Sax Vibrato 1:66).
- **Solos that sound played.** Eighth-note lines with chord tones on the strong beats, chromatic passing and approach notes between them, enclosures (the notes above and below a target, then the target), and phrases of irregular length starting on different beats, separated by rests. Build over choruses: start sparse and low, climb, peak in the last chorus, and quote the head's motif in passing. Repeat a motif in sequence through the changes rather than running scales.
- **Horns.** `vcsl_winds` Tenor Sax (0:66, vibrato 1:66, staccato 2:66; give it `mix.width` near 0.2, its channels are partly out of phase), `sax_bear` (baritone); `vsco` Trumpet (0:56) and harmon or straight mute (`vsco_colors` 0:59, 1:59); trombone (`vsco_extra` 0:57; vibrato, falls and growls in `vsco_colors`); `vsco` Clarinet (0:71). A two-horn head in thirds or sixths; shout chorus voicings in four or five parts below the lead.

## Funk

Funk grooves are built from short figures, each part repeating its own pattern with small variations, interlocking with the others (Danielsen 2006). Its players speak of "the One", the first beat of the bar that the whole groove leans on and returns to (Vincent 1996 takes it as his book's title).

- **Drums**: straight or lightly swung sixteenths (`performance.swing` 0.52–0.56 on unit 0.25), a strong kick on 1, snare on 2 and 4 with ghost notes between, sixteenth hats with accents.
- **Bass**: `bass_darkblack` or `bass_pick` (electric): the root on the One, then syncopated sixteenths, octaves, ghost notes (low velocities) and rests; leave the space just before the next One.
- **Guitar**: a clean electric (`fsbs_clean`) playing short sixteenth-note chord stabs and single-note riffs, high on the neck, many muted or very short notes (`gate` 0.3–0.5 in `performance.notes`).
- **Keys**: the TX81Z Clavisynth (`vcsl_keys` 0:7) for clavinet-like figures, an electric piano, a Surge organ (`studio.py sounds --role keys --name organ`) or organ-like pads (`pwm_strings`).
- **Horns**: short unison or octave stabs on off-beats, a brass section hit (`vsco` 0:62 Brass Stab) on the One of a new section, falls (`vsco_colors` 1:57).
- **Pop-funk and city pop** add major-seventh and ninth harmony, a melodic electric bass, strings or synth brass, and a clear vocal-like lead (a sax, a synth lead or the guitar).

Keep every part's notes short unless they need to sustain: funk's energy comes from the silences between the hits as much as from the hits.

## Blues

The blues is built on a repeating chord progression, the twelve-bar sequence most of all, on call and response between the voice and the instruments, on the blues scale and its blue notes, and on a groove of shuffles or walking bass (Wikipedia, Blues).

- **The twelve-bar form** (Wikipedia, Twelve-bar blues):

  | Bars | 1–4 | 5–8 | 9–12 |
  |---|---|---|---|
  | Basic | I · I · I · I | IV · IV · I · I | V · IV · I · I (or V in bar 12) |
  | Quick change | I · IV · I · I | IV · IV · I · I | V · IV · I · V |

  - Dominant sevenths on every chord.
  - A turnaround in bars 11–12 leads back to the top: I–IV–I–V7, or a chromatic line falling toward the V7.
  - The minor blues runs i7–iv7–♭VI7–V7–i7.
  - Eight- and sixteen-bar blues stretch or shorten the same plan.
- **AAB phrasing.** The three lines of four bars align with an AAB pattern:
  - a phrase over I;
  - the phrase repeated over IV;
  - an answer over V that closes into the turnaround.

  Each line leaves its last bar or two open, and an instrument answers there (call and response). An instrumental lead takes the voice's lines; a guitar, harmonica or piano fills the gaps.
- **Blue notes.** The blues scale sits over the major chords: its minor third, flattened fifth and flattened seventh against a major third and a dominant seventh in the chords make a deliberate conflict.
  - Blue notes are lower than expected: a quarter-tone to a semitone, often reached by a glide. Van der Merwe (1989) ranks the degrees treated that way: the third, then the seventh, the fifth and the sixth.
  - Weisethaunet (2001) separates the blue note as a pitch from the broader "blue" feeling of a performance.
  - On the engine, write the scale note and bend it with `performance.bend` on a monophonic lead:
    - the minor third pushed a quarter- to a half-tone toward the major third and released (a "curl");
    - a full bend from the fourth into the fifth;
    - vibrato on held notes ([performance-and-mix.md](performance-and-mix.md)).
- **The groove.**
  - A **shuffle** swings the eighths (Wikipedia, Blues): `performance.swing` `{"ratio": 0.66, "unit": 0.5}`, a triplet ratio, on drums, bass, comping and lead. At fast tempos, flatten it as for jazz (above).
  - A **slow blues** is written in 12/8 (`meter` [12, 8]; one beat is a dotted quarter, three eighths).
  - **Drums.** A backbeat on 2 and 4 under the shuffle on the hi-hat or ride, the kick on 1 and 3, ghost notes on the snare's triplets.
  - **Bass.** A shuffle bass climbs root–fifth–sixth–flat seventh on each chord, or walks.
  - **Piano.** A boogie-woogie left hand: eighths through 1–3–5–6–♭7–6–5–3.
- **Instruments.**
  - Lead guitar: `fsbs_clean`, or `guitar_shiny` pickup 0:26 for a clean jazz-blues tone, with bends.
  - Harmonica: `vcsl_winds` Harmonica in C (0:22; vibrato 1:22). A diatonic harmonica is played in "second position", a fifth above its key, for the blues: a C harmonica plays a blues in G. Both VCSL harmonicas are sampled only on C, E and G of each octave, so every other note is one of those stretched up to two semitones, and the draw notes are blow notes moved. Keep the harmonica to short fills; lead on the guitar or a tenor sax (`vcsl_winds` 1:66, sampled every whole tone).
  - Piano: the uprights `vcsl_keys` 0:3, 1:3 for a barrelhouse.
  - Organ: a Surge organ (`studio.py sounds --role keys --name organ`, with the piece's `--seed`; audition two to four).
  - Bass: `bass_sneaky` (upright) or `bass_darkblack`.
  - Drums: `rusty`.
  - Horns for jump blues: tenor sax `vcsl_winds` 0:66, `vsco` trumpet 0:56.

## Bossa nova

A relaxed kind of samba born in late-1950s Rio de Janeiro, bossa nova is played with the fingers on a classical guitar with nylon strings. Its core is the guitar beat, the batida, which takes one layer of the samba ensemble, the tamborim, into the picking hand (Wikipedia, Bossa nova).

- **The guitar** (`iowa_guitar` 0:24, the nylon-string guitar in [soundbanks.md](soundbanks.md)).
  - The thumb keeps the bass regular: the root on beats 1 and 3, or the root and then the fifth. `blocks.accompaniment` with `figure='batida'` writes the chords' beat ([building-blocks.md](building-blocks.md)).
  - The fingers pluck the chord, three or four notes, syncopated against it. Wikipedia gives the basic one-bar pattern in 2/4: the thumb on 1 and 2, the chord on both eighths of beat 1 and the second sixteenth of beat 2. Written in 4/4 at 120–140, that is chords on beats 1 and 2 and the "and" of 3, the bass on 1 and 3.
  - Vary it in two-bar patterns that push a chord ahead of the bar line by an eighth; let the pushed chord ring over the bar line rather than striking it again on 1.
  - Keep the notes short (`gate` 0.5–0.7) and the velocities soft, 50–75.
- **Harmony.** Major sevenths, minor sevenths and ninths, 6/9 chords, dominants with flat nines, sharp elevenths and thirteenths, half-diminished ii–V into minor, and chromatic lines through the inner voices or the bass. Bossa nova's "ambiguous" chords are often credited to jazz, but samba guitarists used similar structures before it (Wikipedia, Bossa nova).
  - Check each voicing against the tune: a semitone or minor ninth between them (a flat thirteenth in the tune over a voiced fifth, a natural ninth over a voiced flat nine, a natural note over its flattened form) sounds wrong, not rich. Leave the clashing note out of the chord or change the melody note.
  - On the guitar, keep the thumb's bass on or above E2: a D or E-flat root goes up an octave (D3 on the A string).
- **Percussion on a kit.**
  - The surdo's pattern on the kick: 1, the "and" of 2, 3 and the "and" of 4 (in 4/4).
  - A side stick (37) on the bossa clave, a son clave with the side of two notes pushed an eighth: in eighths over two bars, positions 0, 3, 6, 10 and 13.
  - Eighths on the hi-hat or the ride.
  - A shaker or cabasa (`vcsl_world` 128:25, keys 69–71) in sixteenths, well under the side stick: the shaker samples are quiet, so its stem's level reads high for what it is.
- **Bass.** `bass_sneaky`, the surdo's rhythm on root and fifth. TalkingBass gives the most common figure as the root on 1 (a dotted quarter), the fifth on the "and" of 2 and again on 3 (a dotted quarter), the root on the "and" of 4: each eighth anticipates the next note. The simpler two-feel, the root on 1 and the fifth on 3, also suits it. Where the guitar pushes the next chord early, push its root with it.
- **Melody.** Long notes against the guitar's syncopation, mostly stepwise, at a speaking volume: a flute (`vsco` 0:73, or the `iowa_winds` alto flute), a tenor sax with vibrato (`vcsl_winds` 1:66), a muted trumpet (`vsco_colors` 0:59), or the piano. The `vsco` flute was recorded with spaced microphones: give it `width` 0.3 or so, or the tune spreads across the room instead of sitting in front.
- **The mix.** Intimate and dry: a short room, the guitar and the bass close; `target_lufs` −16 suits it.

## Symptoms and causes

| Symptom | Likely causes | What to check or change |
|---|---|---|
| Swing sounds mechanical | every part on one ratio, the soloist exactly with the ride | the ratios above, a soloist's delay and lower ratio |
| Swing sounds like a shuffle | a 0.67–0.78 ratio at a fast tempo | the tempo formula: ratios fall toward 0.5 as the tempo rises |
| The harmony is muddy | roots in the piano's left hand with the bass, voicings below C3 | rootless voicings, register |
| Walking bass wanders | no chord tone on beat 1, approaches that resolve nowhere | the beat-1 chord tone and the beat-4 approach |
| Solo sounds like scales | constant eighths, no rests, no target notes | phrase lengths, rests, chord tones on strong beats, a motif in sequence |
| Funk feels busy | every part plays every sixteenth | rests, shorter notes, one part at a time on each sixteenth |
| The blues sounds like a scale exercise | blue notes as plain semitones; no answers between phrases | bends and curls on the third and seventh; a fill in each line's last bar |
| Bossa nova sounds stiff | the chord on every beat; loud, long guitar notes | the syncopated pattern above, short notes, soft velocities |

## Sources

- Friberg, A. and Sundström, A. (2002). Swing ratios and ensemble timing in jazz performance: evidence for a common rhythmic pattern. *Music Perception* 19(3), 333–349. [KTH summary with the ensemble-swing rule](https://www.speech.kth.se/music/performance/Texts/ensemble_swing.htm).
- Levine, M. (1989). *The Jazz Piano Book*. Sher Music.
- Berliner, P. F. (1994). *Thinking in Jazz: The Infinite Art of Improvisation*. University of Chicago Press. How jazz musicians learn and build solos, comping and walking lines.
- Danielsen, A. (2006). *Presence and Pleasure: The Funk Grooves of James Brown and Parliament*. Wesleyan University Press.
- Vincent, R. (1996). *Funk: The Music, the People, and the Rhythm of the One*. St. Martin's Griffin.
- van der Merwe, P. (1989). *Origins of the Popular Style: The Antecedents of Twentieth-Century Popular Music*. Clarendon Press. Quoted in Wikipedia, [Blue note](https://en.wikipedia.org/wiki/Blue_note), on the order of the blue degrees.
- Weisethaunet, H. (2001). [Is there such a thing as the 'blue note'?](https://www.cambridge.org/core/journals/popular-music/article/is-there-such-a-thing-as-the-blue-note/EE4A6BCF75165945F6024E01D7F56C31) *Popular Music* 20(1), 99–116.
- Wikipedia, read 6 November 2026: [Blues](https://en.wikipedia.org/wiki/Blues), [Twelve-bar blues](https://en.wikipedia.org/wiki/Twelve-bar_blues) and [Bossa nova](https://en.wikipedia.org/wiki/Bossa_nova), with the sources they cite.
- TalkingBass (2019). [Bossa nova bass lines: a beginner's guide](https://www.talkingbass.net/bossa-nova-bass-lines-beginners/). The two-feel and the dotted-quarter–eighth figure on root and fifth, read 6 November 2026.
- Danielsen, A., Johansson, M., Brøvig, R., Sandvik, B. and Bøhler, K. K. (2023). [Shaping rhythm: timing and sound in five groove-based genres](https://doi.org/10.1017/S0261143023000041). *Popular Music* 42(1).
