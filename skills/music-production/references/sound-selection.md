# Choosing sounds

Read this when choosing the patch or instrument for a part, above all a synth part from the Surge XT catalog (3,008 factory and third-party patches). Each piece of guidance below names its source, and the steps under [With the tools](#with-the-tools) say what the commands do. Figures marked "measured here" are this skill's own measurements of its sounds, not general rules.

Contents: [The part's job](#the-parts-job) · [What puts a sound in front or behind](#what-puts-a-sound-in-front-or-behind) · [By element](#by-element) · [Across a piece](#across-a-piece) · [With the tools](#with-the-tools) · [Sampled instruments and drums](#sampled-instruments-and-drums) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

A sound that impresses on its own is not thereby right for the piece. Flint (2007) explains that a synth patch which impresses without accompaniment was probably programmed to stand out that way, and that this does not make it suit a composition. White (2009) warns that shaping parts while they play solo tends to leave many big, bright sounds competing for the front of the mix. Senior (2024) sees little point in detailed mixing before sounds can be judged in their final context. So a sound is chosen for its job in this piece, and judged on the part's own notes with the other parts playing.

**A guide's table gives options.** Where a guide names several instruments, banks, amplifier voices or effects for a part, each with the conditions it suits, none of them is the style's norm: the piece's whole (SKILL.md, step 2) chooses among those the style allows, recorded as a level it gave (`association.gives`), the reason in `decisions`. A sound is then treated as well as chosen, by its EQ, dynamics and effects, as far as the style treats its sounds ([processing.md](processing.md)).

## The part's job

Owsinski names five kinds of arrangement element:

- **Foundation**: the rhythm section, usually bass and drums, plus any part playing their rhythm.
- **Pad**: a long sustained note or chord. Synthesizers provide most pads today. An organ, an electric piano, strings or a guitar power chord can also be one.
- **Rhythm**: any part playing against the foundation. It adds motion and excitement.
- **Lead**: the lead vocal, a lead instrument or a solo.
- **Fills**: lines in the gaps between lead phrases, or a signature line, heard as an answer to the lead.

Parts playing exactly the same rhythm count as one element. He advises that usually no more than four play at once, and that three can work very well.

Parts also sit at different depths. McAdams, Goodchild and Soden (2022) call this stratification: groups of parts form layers of different prominence (foreground, middleground, background), and timbral differences keep the layers apart. White (2009) gives the usual order in pop:

- the vocal in front;
- guitars, the main keyboard parts and the drums slightly behind;
- pads and backing vocals further back;
- incidental percussion further back still, and panned wider.

Before searching, write down for the part:

- its element;
- its layer;
- its register;
- how many notes it plays in a bar.

## What puts a sound in front or behind

- **What the catalog measures.** McAdams et al. (1995) had listeners compare synthesized timbres and found three shared dimensions:
  - log rise time: how fast a sound starts;
  - spectral centroid: its brightness;
  - spectral variation: how much its spectrum changes.

  Each timbre also had qualities of its own outside these dimensions, and different groups of listeners weighted the dimensions differently. So the numbers can narrow a search, but listening has to make the choice. The catalog measures attack and centroid on one note, with the tail and the stereo width ([With the tools](#with-the-tools)).
- **Front and back.** Perspective comes from contrast (White 2009):
  - parts at the back are quieter, duller and more reverberant;
  - brighter, drier parts in front balance them;
  - chorus-type modulation makes a sound less focused and pushes it back.

  Choose sounds with this plan in mind. A very bright pad is harder to push back than a dull one, and a backing part brighter than the lead will not sit behind it (White 2009).
- **Blend or stand apart.** Sounds fuse into one event when they share three things: they start together, they are harmonic, and their spectra overlap. Moving in parallel strengthens the fusion. Dissimilar timbres stay separately heard (McAdams, Goodchild and Soden 2022). A part meant to reinforce another starts with it and moves with it. A part meant to be followed on its own needs a timbre unlike its neighbours.
- **Top and bottom.** The ear follows the pitch of the highest of simultaneous voices best, already at three months of age (Marie and Trainor 2014), and the timing of the lowest best (Hove, Marie, Bruce and Trainor 2014). Hove et al. trace both to the inner ear and see in them why melodies usually lie in the highest voice and rhythm in the bass. In mixtures of pure-tone melodies in six bands, listeners recognised the highest and lowest bands more accurately than the middle ones (Bürgel, Mares and Siedenburg 2024). Give the lead the top of the texture and the rhythm to the bass and kick.
- **A voice draws attention; an instrument needs help.** In mixes of popular music, listeners found the lead vocal more reliably than any instrument, and neither filtering nor level changes removed that advantage (Bürgel, Picinali and Siedenburg 2021). An instrumental lead does not have it: give it the top of the texture, a timbre unlike its neighbours (above) and room in level.
- **Masking.** When the lead still sits back, listen to it while muting the other parts one at a time. The part whose muting brings it forward is masking it (Senior 2018).
- **The ear's most sensitive region.** Senior (2010) often finds one of a pad's overly prominent regions around 3–4 kHz, where hearing is most sensitive, and dips it there by 4–6 dB. White (2009) cautions against the tendency to make every part as bright as possible. The catalog gives each patch's share of power above 2 kHz and above 5 kHz. Measured here: an eighth-note melody from G4 to G5, played alone at velocity 90, put 65% of its power above 2 kHz on the built-in `fm_bell` (a centroid of 3.3 kHz) and 2% on Surge's `fantasy_bell` (0.9 kHz).

## By element

### Bass, in the foundation

- Patches are programmed for one region of the keyboard, so first work out the range of the bass line (Flint 2007).
- A brighter bass can compete with the vocal and the guitars. A more muted one can be louder without crowding the parts above it (Flint 2007).
- Detuned oscillators can make a bass feel out of tune. Two identical waves with different envelopes can cancel some notes and double others (Flint 2007).
- Keep it mono and centred:
  - the position of frequencies below about 100 Hz cannot be heard, and a centred mono bass is more focused (Flint 2007);
  - a centred bass and kick share their energy evenly between the speakers (Flint 2005).
- The kick and the bass share the lowest frequencies, below about 60 Hz in Senior's (2020) example:
  - a kick that dominates them can suit beat-driven arrangements;
  - for a solid harmonic foundation, he replaced a bass synth's fundamental with a dedicated sub-bass patch and trimmed the kick's lowest end.

### Pad

- **Decide what the pad is for** (Senior 2010):
  - filling spectral gaps;
  - smoothing harshness;
  - lengthening the sustain of chordal parts;
  - widening the stereo image.
- **Saw and pulse pads** give a dense, fizzy fill. **Sine and triangle pads** add warmth and sustain to other parts almost unheard (Senior 2010).
- **For an unobtrusive pad, avoid** (Senior 2010):
  - detuned oscillators, which blur the chord's pitch;
  - strong filter sweeps, pulse-width modulation and vibrato, whose changing harmonics are hard to keep down in the mix.
- **Mixing a pad** (Senior 2010):
  - energy below about 200 Hz rarely helps, so he high-passes pads;
  - warm pads usually blend without reverb or delay, whose tails make chord changes sound sluggish;
  - width costs little on a pad, which carries no essential line and can lose definition in mono;
  - current practice keeps pads barely audible, with automation, for example a fade up into a chorus.
- **A static pad can leave a mix without detail or momentum.** Senior (2020) added rhythmic filter movement and short, quiet snippets of presets that move by themselves.

### Rhythm

- Repeated synth chords can reinforce the groove in upbeat music (Senior 2010).
- A rhythm part that needs width or harmony but no more sustain can be doubled with short, naturally decaying notes (Senior 2010).
- In dance music the chords are ducked by the kick ([electronic.md](electronic.md)).

### Lead

- The lead is the part the listener should be most aware of. Keep it brighter and drier than the parts behind it (White 2009).
- Chorus pushes a sound back. If a front part needs it, keeping the part bright and free of excess reverb keeps it in front (White 2009).
- The most prominent parts, such as a lead vocal, are conventionally centred, so the core of the song survives on most playback systems (Flint 2005).
- Wide or width-enhanced important parts lose balance and tone in mono (Senior 2010).
- Its melody and register: [climax-and-melody.md](climax-and-melody.md).

### Fills and ear candy

- Senior (2020) browses presets for movement: sequences, swells, arpeggios, modulation.
- He drops each one into only one or two places. A swell goes towards an important beat or bar line; an arpeggio goes into a gap between lead phrases.
- Kept very quiet, such parts are noticed mainly when they are muted.

## Across a piece

- **Timbre marks the form** (McAdams, Goodchild and Soden 2022):
  - timbral contrasts mark segments, from a motif to a whole section;
  - strong contrasts of register, texture and instrumentation mark section boundaries;
  - gradual or sudden additions and reductions of instruments give a large section its shape.
- **Keep something for later** (Senior 2024):
  - reserve some layers for later sections;
  - restrict the brightness of drums or guitars early on, so the song has dynamics left to build.
- **Vary a repeating part** (Senior 2024):
  - layer a similar-sounding instrument with different upper voicings in each section;
  - add a sub-bass layer for the later choruses;
  - keep such additions subtle, even subliminal.

## With the tools

1. **Shortlist.** `studio.py sounds --role pad --character warm,slow --seed <the piece's seed>` lists catalog patches of a role and character, dark to bright.
   - **A spread, not the first few.** When more patches match than `--limit` shows (25), the list takes one from each stretch of the range and prefers designers not yet shown. The piece's seed (`musiclib.blocks.seed(title)`) picks within each stretch, so two pieces asking the same question see different patches. In 0.4.0 the list showed the darkest 25, the same for every agent: the agent pieces took 71% of their Surge parts from the fifty curated patches, and five patches recurred across pieces. A tool's shared starting point makes work alike (Doshi and Hauser 2024, in [building-blocks.md](building-blocks.md)).
   - **Roles:** the patch's category in the Surge library: lead, pad, chords, keys, pluck, bass, brass, sequence, fx, percussion, other.
   - **Left out:** patches that were silent on a plain note, built for MPE controllers, microtonal, or off their written pitch.
   - **Character words:** the catalog's own bins of its measurements, not a standard vocabulary:

     | Measure | Words and bins |
     |---|---|
     | Centroid | dark, warm, mid, bright: under 400, 800 and 1,500 Hz, then above |
     | Attack | fast under 30 ms, soft under 250 ms, then slow |
     | Tail | dry under 0.1 s, short under 1.2 s, then long |
     | Width (side over mid power) | mono under −40 dB, narrow under −12 dB, then wide |
     | Centroid between three playings | steady within 10%, then moving (between playings: a steady patch may still swing within one) |

   - **By number.** `--centroid 600-900` and `--attack 0.1-0.3` take the probe note's spectral centroid in Hz and its attack in seconds (the time to half its peak level), either end open (`1500-`, `-0.03`). These are the two measures found most often with the dimensions on which listeners tell timbres apart: the centroid, heard as brightness, and the logarithm of the attack time, which separates blown and bowed sounds from struck and plucked ones (McAdams and Giordano 2015, who report the confirmation of both with synthetic tones by Caclin and colleagues in 2005). A sound of a wanted brightness and attack is therefore chosen, from 3,008: a patch's own controls do not reliably reach one. Measured on 120 patches, a low-pass filter moved a whole octave moved the centroid 0.19 octave at the median, and an amplitude attack set to 200 ms came out between 100 and 300 ms in 42 of 92 fast patches.
   - **Steady or moving.** Each figure is the median of three playings of the probe. Surge starts its oscillators at random phases and many patches move on their own, so the same patch measures differently each time: by 5% at the median, by over 10% in 1,068 of the 2,997 measured, which the catalog calls moving (`--character steady` leaves them out, `--character moving` asks for them; `centroid_spread_pct` is the figure). A moving patch's brightness is not one number: choose it for its movement, and a steady one where a part must sit at a fixed place under or over another.
   - **What a held note does.** Three more playings of the probe say what the sound does over the 1.2 s it is held, each figure the median of the playings that read it (the inharmonic share only where they fall on the same side of its line; our measurement, `musiclib/motion.py`); a word marks the patches whose figure passes this skill's line for it, and `studio.py sounds --id <id>` gives a patch's figures:

     | Word | When | Patches it marks, of those the figure could be read for |
     |---|---|---|
     | decays | its loudest moments at the end of the hold (the last 300 ms, or a regular gate's whole cycle) lie 12 dB or more under those of its first 150 ms: a plucked or struck sound | 593 of 2,997 |
     | darkens, brightens | its centroid ends an octave or more under, or over, where it began: a filter closing or opening over the note | 155 and 92 of 2,763 |
     | pitch blip | its pitch starts a semitone or more from where it settles (the farthest it lies over the first 80 ms; a slow glide in counts too) | 253 of 1,997 |
     | pitch steps | its pitch lies a semitone or more from its middle in a fifth or more of the held part: an arpeggio or a sequence in the patch, or a vibrato wider than a semitone; a figure whose other notes lie a fifth or an octave from the pitch it holds most can read none | 40 of 2,063 |
     | level swings | its level swings 6 dB or more, at a rate it repeats (a tremolo, a gate, an LFO) | 429 of 2,763 |
     | pitch swings | its pitch swings 20 cents or more, at a rate it repeats (a vibrato) | 214 of 2,022 |
     | brightness swings | its centroid swings an octave or more, at a rate it repeats (a filter LFO) | 239 of 2,763 |
     | inharmonic | 30% or more of the power of its partials (the peaks that stand out between 45 Hz and 8 kHz, up to 40 cents over the 16th harmonic of the lower of its two pitches, each with its whole peak) lies away from the harmonics of the pitch it holds, by its measured pitch and by the pitch the probe heard alike (each moved with the pitch heard moment by moment where it has a vibrato and the two agree within 50 cents), in each of the two or three playings that read it: a struck metal, a clangorous FM tone; most synth bells, built on whole-number ratios, are harmonic and not marked (a Chords patch is not judged) | 30 of 1,868 |

     A swing that only wanders, as the beating of many detuned voices does, gives figures but no word, and a one-way change of brightness is `darkens` or `brightens`, not a swing. What one held note cannot tell: a swing slower than about one and a half times a second reads as a lasting change (`decays`, `darkens`, `brightens`) or as none, by where the note caught it; a gate of about two times a second or slower whose silence holds the end of the hold can read as `decays` (one gap and a silence at the end are also a shot, an echo and the end); a level swing faster than about 15 Hz reads shallower than it is; a pitch a gate silences for more than 40 ms at a time has no rate, as whether its swing repeats is not known; a figure's notes a fifth from the pitch it holds most give no steps, and are left out of its inharmonic share with their frames; a steady tone whose upper partials outweigh its fundamental can lead the pitch track to another harmonic at the onset than through the hold, which reads as a `pitch blip` of a fifth, a fourth or a third (of the 253 patches marked `pitch blip`, 88 have a blip within 25 cents of one of these; played again, 25 of them kept the hold's partials at the onset, a misreading, and the rest could not be told; our measurement); a note an octave over the pitch it holds lies on its harmonics; where no vibrato moves the references (none is heard, or the measured pitch and the pitch track disagree), one the track reads within 150 cents of an octave or two away, where its own errors land, counts against the share (one an octave under, or a major seventh away), and as the track can read a note an octave from where it is, a note a little over an octave away counts or is left out by how it is read; where a vibrato moves them, such a note is left out with its frames. Patches without a clear pitch get no pitch figures, `inharmonic` among them, though the most clangorous sounds are often such patches (a pitched role's shortlist shows them only with `--all`). The inharmonic share alone is also not read for a patch either of whose pitches lies under 50 Hz, as its harmonics lie too close for the frames read, nor where its two pitches, or its playings, put it either side of the line, or a vibrato moves its pitch more than about 80 cents within a frame of 85 ms (a fast one, which the pitch track narrows, sooner; one that dwells near its middle and darts to its ends can be judged though it moves further); where no vibrato is heard, frames whose pitch lies more than 40 cents from where it holds most (a glide after the attack, a vibrato with no rate, another note; fewer cents where the pitch swings fast, as the track narrows a fast swing) are left out of it, as are, under a vibrato, frames holding another note (a semitone or more off); a partial within 40 cents of a harmonic counts as harmonic. The pitch is read on the louder channel, so another note the other channel alone carries is not heard: it counts against the share, as a partial on one side does. One note also speaks for its own register and a firm touch (velocity 100): in a sample of 500 patches, an octave from the probe a third changed at least one word, and a fifth when played softly (velocity 60) or hard (127), against one in seven between two runs of the probe itself; `decays` held best (5 to 12% of the patches it marked lost it an octave away, 3% between runs), the brightness and pitch words least (`darkens`, `brightens`, `pitch blip`, `pitch swings` and `brightness swings` were lost by 31 to 80% an octave away, by 6 to 27% between runs), partly because the measure reads a bass an octave down or a lead an octave up less well (our measurement). Each patch's `per_note` in the catalog lists what a note's velocity, its key and the other sources that differ from note to note (random and alternating values, the scene LFOs) move in its envelopes, read from its file (657 patches): such a patch may rise or fall otherwise on another note, and `review` does not read its attack and decay. The shortlist is a start: hear the candidates on the part's own notes (step 2). A patch near a line falls either side of it from one set of playings to the next: between two runs of the catalog, of the patches a word marked in either run, 21 to 30% it marked in one only (`decays` 3%), while of the patches `--without` kept for a word, 0.0 to 1.4% were marked with it in the other run (our measurement). Centroid fluctuation and inharmonicity are among the acoustic correlates of the dimensions listeners use for timbre ([character-words.md](character-words.md)). `--without` leaves out patches with any word given, matched as a whole phrase or one of its words, and those not known to lack it: its figure could not be read, or a swing reaches the line with no rate read: `--without "decays,level swings"` for a pad meant to hold still, quoted because a word holds a space; ask for words with `--character` to find a sound that does the thing (`--character "decays,pitch blip"`).
   - **The probe note,** measured here: C2 for basses; C5 for leads, plucks and brass; C4 for the rest. A patch built an octave away from its key gets a `transpose`: renders play its notes moved by it, so that the written pitch sounds, and it is measured played the same way, where a part plays it (until 0.10 such patches were measured at the written note, an octave from where a part plays them).
2. **Hear two to four on the part.** `studio.py audition <project>/song.json --track pad --sounds surge:a,surge:b,surge:c --bars 9-16 --output <project>/aud_pad --config <config.json>` plays the passage as written, then once per patch. Every version plays at one loudness, with the other parts sounding.
3. **Shape the one you keep.** `studio.py sounds --id <id>` prints what a patch's mod wheel and macros move, from [surge-catalog.json](surge-catalog.json) (about 3 MB: search it with the command rather than reading it):
   - a CC1 value or curve on the part moves what the wheel moves;
   - labelled macros are set with `surge.macros`;
   - `per_note` says what each note's velocity and key move in its envelopes (a harder note may rise faster).
4. **Check it in the mix.** `analyze` reports three things: the lead's level over its accompaniment, how much of it is masked, and the master's share in each band. Compare them with a reference of the style ([measuring.md](measuring.md)).

## Sampled instruments and drums

[soundbanks.md](soundbanks.md) lists the sampled pianos, guitars, basses, orchestra, kits and other recordings, [soundbank-presets.md](soundbank-presets.md) their presets and [soundbank-measurements.md](soundbank-measurements.md) what each was measured to do. Electric pianos also include the sampled TX81Z FM pianos ([beats.md](beats.md)). `studio.py audition` takes `soundfont:<bank>:<bank number>:<program>` to compare them on the part.

**The piano.** A piano part in any kind of music is played on the Steinway grand (`"soundfont": "vcsl"`, bank 0, program 0), solo or in a mix, and made brighter or closer in the mix where it wants to be. Another piano is used where the user names it or the piece is built on its sound; [piano-and-chamber.md](piano-and-chamber.md) says which and what each costs. With `--config`, `review` asks about a piano part on any other piano (`piano:<part>`).

**Notes far from a sample's pitch.** A sampled note played away from the pitch it was recorded at changes its tone, and a vibrato or other movement in it speeds up as it goes higher; a multisample gives each source sample a range of three or four semitones (Howell 2006), and one sample played across an octave sounds "very obviously less natural a few semitones in either direction from the root note" (Walden 2023). With `--config`, `review` names notes played more than 4 semitones from their sample, a limit this skill set ([outputs.md](outputs.md), `transposed_samples`).

**Electric pianos** are there whenever a part wants one; none is a sampled Rhodes or Wurlitzer:
- Surge XT's electric pianos, found by name: `studio.py sounds --role keys --name ep` (or `rhodes`, `wurli`, `suitcase`, `e-piano`, `electric`) with the piece's `--seed` ([electronic-sounds.md](electronic-sounds.md));
- the sampled TX81Z FM pianos (`vcsl_keys` 0:4, 1:4) and its clavinet-like Clavisynth (`vcsl_keys` 0:7);
- the built-in `fm_epiano`, two-operator FM.

The style maps name them where a style's sources do: the Rhodes, Wurlitzer and Clavinet in disco (`pop/disco`), electric pianos in jazz fusion (`jazz/fusion`). Lo-fi, boom bap, funk, city pop, soul and smooth jazz use them as this skill's options ([beats.md](beats.md), [jazz-and-funk.md](jazz-and-funk.md)). The catalog measures each patch on one note at one velocity; the electric pianos were also measured on one C4 at velocities 30, 60, 90 and 120 ([surge-roles.json](surge-roles.json), `ep_velocity`): `factory/keys/dx_ep`, `factory/keys/ep_1`, `factory/keys/ep_2`, `bluelight/keys/treated_rhodes`, `vospi/keys/ep_forest` and `vospi/keys/ep_middle` grow brighter and louder with velocity; `cybersoda/keys/wurli`, `cybersoda/keys/vintage_ep` and `kinsey_dulcet/keys/japanese_suitcase` brighter at about the same level; `emu/keys/light_ep`, `emu/keys/trashion_ep` and `factory/keys/soft_suitcase` louder with the tone about the same; two irregular. Give the part a range of velocities and read `audition`'s level and brightness for each candidate.

## Sources

- Bürgel, M., Mares, D. and Siedenburg, K. (2024). Enhanced salience of edge frequencies in auditory pattern recognition. *Attention, Perception, & Psychophysics* 86(8), 2811–2820. doi:10.3758/s13414-024-02971-x
- Bürgel, M., Picinali, L. and Siedenburg, K. (2021). [Listening in the mix: lead vocals robustly attract auditory attention in popular music](https://doi.org/10.3389/fpsyg.2021.769663). *Frontiers in Psychology* 12:769663.
- Flint, T. (2005). [Q. Should I always pan my vocals to the centre of the mix?](https://www.soundonsound.com/sound-advice/q-should-always-pan-my-vocals-centre-mix) *Sound On Sound*, February 2005. Lead vocal and bass centred as standard practice; why.
- Flint, T. (2007). [Q. How can I get more effective synth bass in my mixes?](https://www.soundonsound.com/sound-advice/q-how-can-get-more-effective-synth-bass-my-mixes) *Sound On Sound*, January 2007. Choosing and adapting a synth bass patch: range, brightness, detuning, mono.
- Hove, M. J., Marie, C., Bruce, I. C. and Trainor, L. J. (2014). [Superior time perception for lower musical pitch explains why bass-ranged instruments lay down musical rhythms](https://doi.org/10.1073/pnas.1402039111). *Proceedings of the National Academy of Sciences* 111(28), 10383–10388.
- Howell, S. (2006). [The Lost Art of Sampling: Part 6](https://www.soundonsound.com/techniques/lost-art-sampling-part-6). *Sound On Sound*, January 2006: keygroups, one sample over three or four semitones, a sample's movement speeding up as it is transposed.
- Marie, C. and Trainor, L. J. (2014). Early development of polyphonic sound encoding and the high voice superiority effect. *Neuropsychologia* 57, 50–58. doi:10.1016/j.neuropsychologia.2014.02.023
- McAdams, S. and Giordano, B. L. (2015). The perception of musical timbre. In *The Oxford Handbook of Music Psychology*, 2nd ed. (online). [doi:10.1093/oxfordhb/9780198722946.013.12](https://doi.org/10.1093/oxfordhb/9780198722946.013.12); read in the copy on the first author's [laboratory site](https://www.mcgill.ca/mpcl/files/mpcl/mcadams_2015_oxfordhdbkmuspsychol.pdf). The acoustic measures found with the dimensions of timbre.
- McAdams, S., Goodchild, M. and Soden, K. (2022). [A Taxonomy of Orchestral Grouping Effects Derived from Principles of Auditory Perception](https://doi.org/10.30535/mto.28.3.6). *Music Theory Online* 28(3). Summarized in the [Timbre and Orchestration Resource](https://timbreandorchestration.org/tor/modules/taxonomy/orchestral-grouping-effects/introduction): blend, stratification, timbral contrasts, orchestral gestures.
- McAdams, S., Winsberg, S., Donnadieu, S., De Soete, G. and Krimphoff, J. (1995). [Perceptual scaling of synthesized musical timbres: common dimensions, specificities, and latent subject classes](https://doi.org/10.1007/BF00419633). *Psychological Research* 58, 177–192.
- Owsinski, B. [A look at the 5 song arrangement elements](https://bobbyowsinskiblog.com/song-arrangement-elements/). An excerpt from *The Music Producer's Handbook*, 2nd edition.
- Senior, M. (2010). [Creating & Using Synth Pad Sounds](https://www.soundonsound.com/techniques/creating-using-synth-pad-sounds). *Sound On Sound*, May 2010.
- Senior, M. (2018). [Q. How can I locate the masking problems in my mix?](https://www.soundonsound.com/sound-advice/q-how-can-locate-masking-problems-my-mix) *Sound On Sound*, March 2018.
- Senior, M. (2020). [Mix Rescue: Rearranging](https://www.soundonsound.com/techniques/mix-rescue-rearranging). *Sound On Sound*, March 2020. A sub-bass patch under the bass synth; static pads; preset snippets with movement.
- Senior, M. (2024). [Mix Rescue: Strong Arrangements](https://www.soundonsound.com/techniques/mix-rescue-strong-arrangements). *Sound On Sound*, May 2024.
- Walden, J. (2023). [Cubase 12: Sampler Track, audio examples](https://www.soundonsound.com/techniques/cubase-12-sampler-track-audio-examples). *Sound On Sound*, January 2023: one sample over an octave, obviously less natural a few semitones from its root.
- White, P. (2009). [Creating A Sense Of Depth In Your Mix](https://www.soundonsound.com/techniques/creating-sense-depth-your-mix). *Sound On Sound*, February 2009. Front and back by brightness, reverb and chorus; choosing sounds for the mix plan.
