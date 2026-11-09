# Orchestral music: the orchestra on the sampled banks

Read this when the music is for orchestra: a symphonic piece or cue, a film or game score, a chamber ensemble. The banks hold most of a classical or romantic orchestra; this guide maps what an orchestrator writes onto them, then covers balance, chords, dynamics and the mix. Pipe organ is in [organ.md](organ.md).

The periods and orchestral styles, Baroque to cinematic, each on the seven axes with its sources, are in [style-map-orchestral.md](style-map-orchestral.md).

Contents: [The orchestra in the banks](#the-orchestra-in-the-banks) · [Balance](#balance) · [Chords and doubling](#chords-and-doubling) · [Dynamics and the master](#dynamics-and-the-master) · [Expression on the sampled orchestra](#expression-on-the-sampled-orchestra) · [Writing for the sampled orchestra](#writing-for-the-sampled-orchestra) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

## The orchestra in the banks

Write one track per orchestral part (violins I, violins II, violas, cellos, basses, each wind and brass part, timpani, each percussion part), up to 64. Ranges are where each preset sounds, written at sounding pitch.

| Section | Instrument and presets (bank, patch) | Sounding range |
|---|---|---|
| Strings | Each section on its own: `vsco_strings` violins 0:40, violas 0:41, cellos 0:42 sustain; bank 1 spiccato, bank 2 pizzicato; tremolo 0:44, 0:45, 0:46 | G3–F♯6, C3–F♯6, C2–A5 |
| | All sections in one preset: `vsco` 0:48 sustain, 0:49 slow attack, 0:45 spiccato, 0:44 tremolo, 1:45 pizzicato | C2–G7 |
| | Double bass `vsco_extra` 0:43 sustain with vibrato, 1:43 straight, 2:43 spiccato, 3:43 pizzicato, 4:43 tremolo | E1–D4 |
| | Solo violin `vsco` 0:40, spiccato 1:40; solo cello `cello_bigcat` 0:42, staccato 1:42, pizzicato 2:42 | G3–E7; C2–C6 |
| | Solo violin, viola, cello and double bass at pp, mf and ff: `iowa_strings` 0:40–0:43 arco, 2:40–2:43 pizzicato | G3–B7, C3–B♭6, C2–B♭5, E1–G4 |
| Woodwinds | Piccolo `vsco_extra` 0:72, staccato 1:72 | D5–C8 |
| | Flute `vsco` 0:73, oboe 0:68, clarinet 0:71, bassoon 0:70; staccato on bank 1 of each | B3–D7, B♭3–A6, D3–E6, B♭1–E♭5 |
| | Alto flute `iowa_winds` 0:73, bass flute 0:74, E-flat clarinet 0:71, bass clarinet 0:70 (pp, mf, ff) | G3–G6, C3–C♯6, G3–C7, C♯2–B♭5 |
| Brass | Horn `vsco` 0:60; trumpet 0:56, staccato 1:56, vibrato 2:56 | A1–G5; F♯3–C6 |
| | Trombone `vsco_extra` 0:57, short 1:57; tuba 0:58, staccato 1:58 | E2–B♭4; F1–C4 |
| | Horn `iowa_brass` 0:60 and bass trombone 0:57, chromatic at pp, mf and ff | A♯1–F5; C1–B♭4 |
| Percussion | Timpani `vcsl` 0:47; orchestra kit `vcsl` 128:48 (bass drum, snare, cymbals, gong, triangle, tambourine); glockenspiel `vsco` 0:9; xylophone, tubular bells, marimba, vibraphone in `vcsl` | timpani D2–B3 |
| | Orchestra bells `iowa_perc` 0:9, crotales 0:10, Thai gongs 0:11; kit 128:48 with clash and suspended cymbals, tam-tams of 22–40 inches and a wind gong, struck, rolled and bowed | C5–E8, C6–C8, C4–C5 |
| Colours | Muted horn `vsco_colors` 0:60; harmon- and straight-muted trumpet 0:59, 1:59; trombone vibrato, falls and growls 0:57, 1:57, 2:57; flute, oboe and bassoon with vibrato 0:73, 0:68, 0:70; solo violin tremolo 0:44 and pizzicato 2:40; glockenspiel glissandi and orchestral effects (kits 128:9, 128:50) | |
| Early and folk ([baroque.md](baroque.md)) | Harpsichords `vcsl_keys` 0:6–3:6; recorders `vcsl_winds` program 74; Renaissance organ 0:20; folk harp, psaltery, dan tranh, kalimbas, balafon and world percussion in `vcsl_world` | |
| Harp, keyboards | Harp `vcsl` 0:46; pianos `piano_osiris` and `vcsl` 0:0; organ `organ_vcsl` | |

**Write each string section on its own preset.** `vsco_strings` plays every section over its whole sampled range: a cello melody in the tenor register sounds like cellos, a viola line in the treble like violas. The combined `vsco` presets switch sections by register (cellos to F♯3, violas G3–E4, violins above F4), so there a viola line below G3 takes on the cellos' tone and a cello line above F♯3 the violas', and they stretch the violins' top sample (D6) up to G7. The violins have no sample above D6: on `vsco_strings` they reach F♯6, and the octave above belongs to flutes, piccolo or the solo violin (sampled to C7). Run `review --config` to list notes played far from their samples. Violins I and II are two tracks on the same preset.

**The double bass is one player.** The library has a solo double bass, not a section. Doubling the cellos an octave below with it is the usual bass line (Rimsky-Korsakov finds cellos and basses together "rich" and full); the cellos then carry the body of the sound.

**Missing**: English horn, contrabassoon, celesta and choir. Cover a missing part with the nearest colour (an oboe for the English horn's upper range, the bass clarinet or a bassoon for a contrabassoon line an octave up) and say so.

**Two of some instruments.** The Iowa recordings sample the horn, the solo strings and the woodwinds they add on every semitone at three dynamics, dry and played by single players; VSCO samples its horn and solo violin every few semitones (`review --config` lists the notes it stretches) at two to four dynamics, in a room. Where both exist, render the passage on each and let the user choose by ear; keep the chosen one in place. The Iowa solo strings are single players: a soloist, not a section.

## Balance

Rimsky-Korsakov (1922) gives approximate equivalents of strength. In forte, one trumpet, one trombone or the tuba equals two horns, and one horn equals two woodwinds. In piano, all wind instruments, wood or brass, balance roughly equally. A whole string section, such as all first violins in an orchestra of medium size, equals one wind instrument in piano and two in forte. Because horns are the softer brass, he marks them one degree louder than the rest (*p* when trumpets and trombones play *pp*).

The mix levels each part from its louder passages (`mix.level_dbfs`, see [performance-and-mix.md](performance-and-mix.md)), so the orchestra's natural balance has to be set by hand. These starting levels follow the equivalents in forte: twice the strength is about 3 dB.

| Part | level_dbfs relative to a trumpet |
|---|---|
| Trumpet, trombone, tuba | 0 |
| Horn | −3 |
| Each string section | −3 (several desks), for melody up to 0 |
| Each woodwind | −6, for a solo up to −3 |
| Timpani (peak mode) | set by ear against the brass |

Then check with `analyze` (stem levels per section) and adjust where a line must lead. The velocity of each note still makes the dynamics, and the banks' velocity layers change the tone with it.

**Soft solos.** Because a part is levelled from its louder passages, a solo in a quiet section, written on a track that also plays ff, stays as far under the tutti as its velocity says. In one piece a clarinet's pp answer to a horn call came out 23 dB under the horn. Give such a solo a track of its own on the same patch and level it with the quiet section. Parts that only ever play softly, such as harp arpeggios or tremolo under a solo, are levelled from their soft playing, so set them well under their role's usual level.

- **Seating.** Orchestral layouts vary; a popular one places the first violins, second violins, violas and cellos from left to right (Wikipedia, Orchestra). This skill's starting pans follow it: first violins about −0.5, second violins left-centre, violas centre-right, cellos right, basses right; woodwinds in the centre, brass and percussion behind (the depths below).
- **Depth.** Set `mix.depth_m` on every part ([Expression on the sampled orchestra](#expression-on-the-sampled-orchestra)); without it, give the back rows (brass, percussion) more reverb send than the strings (this skill's starting point: 2–3 dB), since the ratio of direct to reverberant sound is one of the two primary cues to distance (Zahorik 2002).
- **One room.** Route every part to the hall: set `mix.space: "hall"` on every track, since melody parts otherwise send to the plate, and bass and rhythm parts to the room. The halls most praised for symphonic music, such as Vienna's Musikverein, Amsterdam's Concertgebouw and Boston's Symphony Hall, decay in about 1.9–2.0 s at mid frequencies when full (Beranek 2004); the generated hall decays in about 2.2 s at 1 kHz.

## Chords and doubling

Rimsky-Korsakov's rules for distributing a chord follow the harmonic series:

- **Spacing.** Keep wide intervals at the bottom and closer ones higher up. The bass should rarely lie more than an octave below the part above it.
- **Gaps.** Leave no wide empty space between the upper and lower parts, above all in forte; in piano it is possible.
- **Woodwind order.** The natural order of the woodwinds, top to bottom, is flutes, oboes, clarinets, bassoons. Crossing it (bassoons above clarinets, flutes below oboes) sounds contrived and suits only special effects.
- **Mixing groups.** Woodwinds thicken the strings and soften the brass. Strings and brass side by side do not blend, each heard too distinctly. All three groups in unison give a rich, mellow, coherent tone.
- **Doubling a melody.** Rimsky-Korsakov sets string melodies in octaves in many pairings: first and second violins, violins with violas, violas with cellos, violins with cellos, and cellos with basses. A bass line on cellos and basses an octave apart is the norm.
- **Divided sections.** He warns that violins divided in octaves lose resonance, because each part has half the players. Sampled sections do the opposite: each divided track still sounds like a full section, so divisi passages come out thicker than an orchestra plays them. Lower their level.

## Dynamics and the master

An orchestral piece lives on contrast between *pp* and *ff*. The default bus chain glues the mix with compression, which narrows that contrast. Set `mix.dynamics: "wide"` ([schema.md](schema.md)): no bus compresses or saturates, the master keeps only its EQ, and one gain brings the mix to `target_lufs`. If the true peak would then pass −1.2 dBTP (−2.2 for a master louder than −14 LUFS), the render holds the gain down instead of limiting, and reports how far as `mastering.peak_held_db`. The loudest passage then sets the level, so expect a quieter result than a pop master where the music has strong peaks: the skill's orchestral reference measured −17 LUFS ([measuring.md](measuring.md)), and EBU R 128 normalises broadcast programmes to −23 LUFS.

The report also gives the loudness range (LRA, EBU Tech 3342), the spread of loudness across the piece in LU; compare it with the premix's to see what the master kept.

Shape crescendos with `performance.dynamics` on parts whose preset has dynamic layers (bank 0 of a program in [soundbank-presets.md](soundbank-presets.md)'s table; below), otherwise with velocity steps and CC11 in `cc_mode: "linear"`. For arrivals, timpani rolls, cymbal swells (keys 27–30 of the orchestra kit) and brass crescendos are the bank's means; the research on what accompanies strong responses is in [climax-and-melody.md](climax-and-melody.md).

If the piece must also carry on small speakers, `mix.range_lu` brings the master's loudness range down to that many LU by lifting the quieter passages, slowly and in proportion, while the loudest keep their level ([performance-and-mix.md](performance-and-mix.md)). EBU R 128 sets no ceiling on loudness range and leaves it to the programme and where it will be heard.

## Expression on the sampled orchestra

A recording holds one note at one dynamic, so a sampled orchestra loses three things a real one has: a crescendo that changes the tone, notes joined without a new attack, and players who stand at different distances in one room. The renderer puts them back.

- **Dynamics that change the tone.** An instrument played louder is also brighter, in ways that vary with instrument and register (Fabiani 2009); a sampled crescendo should therefore move from one recorded dynamic to the next, not only turn the level up. Samplers crossfade between recorded dynamics along the mod wheel (SFZ's `xfin`/`xfout` on CC1). Eleven banks also hold each recorded dynamic of a sustained preset as its own preset (banks 16 and up) for the bank-0 presets [soundbank-presets.md](soundbank-presets.md) lists: the four VSCO banks, the Iowa brass, winds and strings, the VCSL winds, the Big Cat cello, the War Tuba and the Bear Sax. A part with `performance.dynamics`, a [beat, 0–127] curve, plays each note on the recorded dynamic nearest the curve and lets the curve move its level and tone (take mode, the default), or, with `dynamics_mode: "crossfade"`, is rendered once per dynamic and the renders are crossfaded along it. The values read like velocities: 64 sounds about 12 dB under 127, as on a plain preset. Neighbouring dynamics cross over in the middle half of the span between them, with equal-power curves corrected by the two renders' correlation over 0.4 s so the sum keeps its power (Fink, Holters and Zölzer 2016); near a recorded dynamic its take sounds alone. Two takes of one note carry their own vibrato and phase: held together they comb-filter and sound like two players, which a section hides and a solo does not. Write the curve as a player shapes a phrase: a swell on a long note, a crescendo across bars, a decrescendo into the cadence. In take mode each note plays one recorded dynamic and the curve moves its level and, through a filter learned from the bank's own layers, its tone, so a solo can swell freely without two takes sounding at once. In single held notes swelling from pp to ff, brightness (spectral centroid in harmonics) rose in 96–100% of steps on the horns in take mode against 81–94% with crossfades, and 72–88% against 55–74% on the Iowa violin; one crossfaded VSCO horn note nearly vanished where its two takes cancelled. Keep crossfades for sections, where two takes at once read as more players; in crossfade mode keep a solo's curve near one recorded dynamic (with four, near 0, 42, 85 or 127; with two, near either end; `musiclib.phrasing.near` holds a curve there) and let `level_dbfs` set its loudness: its track is levelled from its own playing.
- **Legato.** `performance.legato` with `"mode": "crossfade"` joins a single line: a note that follows its neighbour within `gap_ms` starts from the bank's legato preset (banks 32 and up), the same recording entered past its attack, and the two notes cross over in `crossfade_ms`. This follows SFZ legato regions, which skip a sustained sample's start with `offset` and fade it in (SFZ format, "Legato"). It fits section strings, woodwinds and the low brass; this skill's starting values are 100–150 ms for strings in a slow line and 60–100 ms for winds. Chords and repeated notes still attack. In an orchestral piece rendered both ways, the level dip at a slurred note change (median) fell from 14 to 6 dB on the first violins, from 10 to 3 dB on the cellos and from 24 to 3 dB on a solo flute. A solo horn moving in small steps dipped less with the slur mode (a glide on one sample) than with crossfades, so keep that mode for solo brass and for guitars and lines that bend; on a bank with dynamic layers it works there too.
- **Long notes, leaps and repeats.** A looped sample holds one bow for ever: `performance.bow_change_s` (3–5 s for strings, a starting value) re-enters a long note from its legato preset every few seconds, as a player changes bow. `legato.portamento_ms` slides a slurred leap of a third or more into its pitch, an expressive shift rather than a glissando (this skill's starting values: 60–120 for strings, 0 for brass and woodwinds). `performance.round_robin` varies a repeated note on a bank without round robins (the Iowa banks, most VSCO sustains): an ostinato or repeated chord no longer replays one recording.
- **Phrasing.** `musiclib.phrasing` gives composition scripts arched velocities (`sing`), hairpin plans (`ramp`) and a dynamics curve with swells on held notes (`dynamics`). `clock.rubato` slows phrase ends and the close as players do (Friberg and Sundberg 1999); this skill's starting values are 0.94 over the last beat of a section and 0.6 over the last four beats of a piece.
- **Horns on the stage.** Give horn parts `mix.facing: "back"` with their `depth_m`: their bells point away from the hall, so the direct sound is darker and more of it comes off the stage shell (Meyer 2009).
- **Stage depth.** `mix.depth_m` stands a part that many metres behind the first desks. The renderer adds early reflections from that position in a modelled hall (image sources; Allen and Berkley 1979) and gives the part more of the hall, half the distance loss; the direct sound keeps its timing and pan, and the part its loudness. Listeners judge distance in a room from two primary cues, the level and the ratio of direct to reverberant sound, weighted differently for different sources and directions (Zahorik 2002); Bronkhorst and Houtgast (1999) modelled perceived distance in rooms from that ratio. A loudspeaker orchestra laid out in the American seating spans about 13 m by 7 m (Pätynen, Tervo and Lokki 2008). Starting depths:

| Part | depth_m |
|---|---|
| First and second violins, violas, cellos | 1–3 |
| Double basses, harp | 3–4 |
| Flutes, oboes, piccolo | 5–5.5 |
| Clarinets, bassoons | 6–6.5 |
| Horns | 7–7.5 |
| Trumpets, trombones, tuba | 8–9 |
| Timpani and percussion | 9–10 |

  With `depth_m` on every part, give all of them one reverb send (−14 dB, a starting value) and let the depth set the rest.

## Writing for the sampled orchestra

- **Attack.** Start slow-speaking parts early with `performance.offset_ms`:
  - section strings sustain −90 (slow attack −120), spiccato −35 to −40;
  - clarinet and tremolo about −60, flute about −35.
  The numbers come from [soundbank-measurements.md](soundbank-measurements.md). A note that enters with crossfade legato speaks at once and leaves this offset out.
- **Long and short notes.** Long notes go to the sustained presets and short ones to staccato, spiccato or pizzicato tracks. A fast passage on a sustain sample re-attacks every note slowly.
- **Holding notes.** Trombone, tuba, double bass and piccolo sustains are looped, so they hold as long as written. The loud brass takes were recorded for 2–4 s, so a held *ff* loops a short stretch: vary such notes with the parts around them. The double bass's vibrato takes repeat the player's bow changes about every 2.3 s; hold long quiet notes on the straight preset.
- **Connecting notes.** Crossfade legato (above) joins a line on the sustained presets of the dynamic-layer banks; the slur mode joins steps on other single-line parts. `performance.bow_change_s` re-enters long notes as a bow change does (above).
- **Divisi.** Split a section into two tracks on the same preset.

## Sources

- Rimsky-Korsakov, N. (1922). [Principles of Orchestration](https://www.gutenberg.org/ebooks/33900), ed. M. Steinberg, trans. E. Agate. Project Gutenberg #33900, public domain in the USA. Chapters II and III: the relative strength of the groups, the distribution of chords, the natural order of the woodwinds, strings doubling in octaves, combinations of timbres.
- Beranek, L. L. (2004). *Concert Halls and Opera Houses: Music, Acoustics, and Architecture*, 2nd ed. Springer. See also Beranek, L. L. (2008). Concert Hall Acoustics—2008. *Journal of the Audio Engineering Society* 56(7/8), 532–544.
- EBU (2023). [Tech 3342: Loudness range: A measure to supplement EBU R 128 loudness normalisation](https://tech.ebu.ch/publications/tech3342). First published 2010. See also EBU (2023), R 128: Loudness normalisation and permitted maximum level of audio signals.
- Fabiani, M. (2009). [A method for the modification of acoustic instrument tone dynamics](https://www.dafx.de/paper-archive/2009/papers/paper_75.pdf). *Proceedings of the 12th International Conference on Digital Audio Effects (DAFx-09)*, Como.
- Fink, M., Holters, M. and Zölzer, U. (2016). [Signal-matched power-complementary cross-fading and dry-wet mixing](https://dafx.de/paper-archive/details/gUO-U6xEDk0Z_m4S-PivJQ). *Proceedings of the 19th International Conference on Digital Audio Effects (DAFx-16)*, Brno, 109–112.
- SFZ format. [Legato](https://sfzformat.com/tutorials/legato/) (tutorial): legato regions with `offset` and an attack, crossfades between dynamics on CC1.
- Allen, J. B. and Berkley, D. A. (1979). Image method for efficiently simulating small-room acoustics. *Journal of the Acoustical Society of America* 65(4), 943–950. doi:10.1121/1.382599
- Zahorik, P. (2002). Assessing auditory distance perception using virtual acoustics. *Journal of the Acoustical Society of America* 111(4), 1832–1846. doi:10.1121/1.1458027
- Bronkhorst, A. W. and Houtgast, T. (1999). Auditory distance perception in rooms. *Nature* 397, 517–520. doi:10.1038/17374
- Pätynen, J., Tervo, S. and Lokki, T. (2008). [A loudspeaker orchestra for concert hall studies](https://mediatech.aalto.fi/~ktlokki/Publs/08_J_Patyen.pdf). *Proceedings of the Institute of Acoustics* 30(3), 45–52.
- Meyer, J. (2009). *Acoustics and the Performance of Music: Manual for Acousticians, Audio Engineers, Musicians, Architects and Musical Instrument Makers*, 5th ed. Springer. The directivity of the horns and the other instruments.
- [Orchestra](https://en.wikipedia.org/wiki/Orchestra). Wikipedia, read 7 November 2026: layouts vary; one popular arrangement places firsts, seconds, violas and cellos from left to right.
- Friberg, A. and Sundberg, J. (1999). Does music performance allude to locomotion? A model of final ritardandi derived from measurements of stopping runners. *Journal of the Acoustical Society of America* 105(3), 1469–1484.
