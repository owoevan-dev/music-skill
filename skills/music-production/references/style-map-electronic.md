# Style map: electronic music

Dance music made with drum machines, synthesizers and samplers, from house to drum and bass, and the electronic
styles made for listening: synthwave, chiptune, ambient, IDM. Read [style-maps.md](style-maps.md) first for the axes
and for combining entries. The craft is in [electronic.md](electronic.md) (form, drums, production, techno, future
bass, synthwave, chiptune) and [electronic-sounds.md](electronic-sounds.md) (the sounds for each role); hip-hop and
lo-fi beats are in [beats.md](beats.md).

Contents: [Shared by the dance styles](#shared-by-the-dance-styles) · [House](#house) · [Techno](#techno) ·
[Trance](#trance) · [Festival EDM](#festival-edm) · [Hard dance](#hard-dance) · [Drum and bass](#drum-and-bass) ·
[UK garage](#uk-garage) · [Dubstep](#dubstep) · [Future bass](#future-bass) · [EDM trap](#edm-trap) ·
[Electro](#electro) · [Eurobeat](#eurobeat) · [Synthwave](#synthwave) · [Chiptune](#chiptune) ·
[Ambient](#ambient) · [IDM](#idm) · [Sources](#sources)

Source tags: WP is Wikipedia, read on 9 November 2026, by article; the articles' traits are described there with the
sources they cite. The other sources are by author and year.

## Shared by the dance styles

Electronic dance music (EDM) is built differently from songs, and the entries from House to Electro share this:
- **The loop is the unit.** Garcia (2005), after Butler (2006), takes the loop as the fundamental unit of EDM's
  structure: a riff of set length that the listener expects to come round again. Looping means layering loops,
  adding them and taking them away, an "ever-changing same". A groove is often built up from its parts, Spicer's accumulative
  form (Garcia 2005). Structural changes are expected on multiples of four: four beats, four bars, eight bars or more.
- **Change by process.** Melody and harmony in EDM are kept simple, where there are any, while the rhythms cycle in
  short loops; continuous processes bring the variety: pitch slides, crescendos, fades, filter sweeps, timbre
  changes (Smith 2021). Uplifters and downlifters sit right before and after the hypermetric downbeats where new
  sounds come in. Producers of house and techno say automation gives "the desired balance between repetition and
  constant change" (Wright 2017, quoted in Smith 2021). Garcia (2005) hears a techno loop whose clicks rise and fall in
  frequency over every four bars.
- **The build-up and the drop** (Smith 2021, on 2010s trance, big room, progressive house and electro house):
  - the build raises energy for about seven bars by crescendos, rising pitch slides, filter sweeps and the snare roll
    in rhythmic diminution;
  - often a break follows, nearly everything cut but a cue of one to four beats;
  - then the drop: everything, the drums and the bass included, returns at the start of the core section;
  - breakdowns, usually without drums, use continuous processes to disorient.

  How to write each part is in [electronic.md](electronic.md), Form.
- **Measured.** In the Harmonix Set, 129 songs labelled dance/electronic, most of them songs with verses and choruses:
  a median 128 BPM, the middle 80% between 119 and 134, the peak Nieto et al. (2019) find for the whole set and
  ascribe to dance music (Moelants 2008, as they cite him); choruses 8 bars long in 56% and 16 in 20%, verses 8 or
  16 bars in 35% each. Measured here.
- **Two kinds of beat.** House and techno emphasise the main beats with a regular kick (Christodoulou 2020).
  Breakbeats, sampled from soul and funk records, "de-emphasize strong beats" and stress weak positions (Butler 2006,
  quoted by Christodoulou 2020).
- **The spectrum.** Number ones tagged electronic have the flattest slope of the genres Pestana et al. (2013) measured,
  −0.75 over 100 Hz–10 kHz (pop −0.94, jazz −1.29): with hip-hop and disco the most top, as electronic recordings
  "allow and benefit from bigger frequency extensions" (there). `analyze` sets the master beside it, except for
  ambient, often without beat, where the top that percussion brings is missing by design (Elowsson and Friberg 2017;
  [performance-and-mix.md](performance-and-mix.md), Brightness and air).

For the whole family, `review` does not ask about pushes: that question rests on rock melodies (Tan, Lustig and
Temperley 2019), and the family's sources describe syncopation in the drums, not anticipations in melody. UK garage
and dubstep, whose sources describe syncopated basslines and rhythms, keep the question.

For the dance entries (House to EDM trap and Electro), `review`:
- does not ask about a part looping a short pattern: the loop is the unit (Garcia 2005; Smith 2021);
- asks about every part repeating one block note for note only where nothing moves the sound in that span: no filter
  sweep, no gain automation, no controller curve on any part (Smith 2021; Garcia 2005).

## House

A repetitive four-on-the-floor beat on drum machines, off-beat hi-hats, deep basslines and synthesizer riffs, built
from loops and samples in a sparse texture. `electronic/house`

| Axis | Traits | From |
|---|---|---|
| `tempo` | typically 115–130 BPM, mostly 120–130; 4/4 | Ableton Learning Music, which WP House music cites |
| `harmony` | bass-heavy loops or synthesizer basslines; loops built on samples of disco, soul, jazz-funk or funk | WP House music |
| `melody` | synthesizer riffs; where there are vocals, often simple words or phrases repeated | WP House music |
| `rhythm` | the kick on every beat, snare, claps or higher percussion on 2 and 4, off-beat hi-hats; claps, shakers, snare and hats add syncopation; the "poumtchak", kick and off-beat hat alternating | WP House music; Zeiner-Henriksen 2010 |
| `timbre` | drum machines, the TR-808, TR-909 or TR-707; synthesizer basslines; sampled instruments rather than session players | WP House music |
| `form` | layered loops; some tracks have no verse and repeat one cycle | WP House music; Garcia 2005 |
| `mix` | the overall texture relatively sparse | WP House music |

- **In this skill**: `drum_synth` with `kit.style` `"909"` or `"808"`, or `blocks.drums` in the `dance` feel with
  `kick="four_floor"`, `pulse="offbeat"`, `backbeat_sound="clap"`, `programmed=True`
  ([building-blocks.md](building-blocks.md)); basses from `studio.py sounds --role bass` or `sub_bass`; the pianos for
  the garage-house piano; pumping by `mix.duck` ([electronic.md](electronic.md), Production).
- **Variants**:
  - *Deep house*: 110–125 BPM; muted basslines; spacious percussion, typically a TR-909; soft keyboard pads; advanced
    chord structures from the lush chords of 1980s jazz-funk; ambient mixes; steady, hypnotic repetition that avoids
    other dance styles' build-up and release (WP Deep house).
  - *Acid house*: the TB-303's squelch over the four-on-the-floor beat: filter resonance raised and cutoff lowered,
    its accent, slide and octave settings varying a simple bass pattern (WP Acid house); `acid_bass`
    ([electronic.md](electronic.md), Techno).
  - *Garage house*: piano riffs drawn more from gospel, and female voices (WP House music).
- **Neighbours**: Techno (sequences in place of harmony, synthesis to the fore); UK garage (shuffled, often without
  four-on-the-floor kicks); Festival EDM (long builds and drops).

## Techno

Repetitive sequences on drum machines and synthesizers for a continuous DJ set: the loop's sound changes more than
its notes. `electronic/techno`

| Axis | Traits | From |
|---|---|---|
| `tempo` | typically 120–140 BPM; common time. Wikipedia's 120–150 cites no source | Ableton Learning Music; WP Techno |
| `harmony` | the harmonic practice of other music often ignored for repetitive sequences of notes | WP Techno |
| `melody` | repeated sequences rather than melody | WP Techno |
| `rhythm` | a repetitive four-on-the-floor beat; the kick and an open hat on every off-beat | WP Techno; Zeiner-Henriksen 2010 |
| `timbre` | drum machines, the TR-808 and TR-909 above all, sequencers and synthesizers; distinctive timbres from synthesis | WP Techno |
| `form` | loops layered, added and removed; the high point forecast by a filter on the drum loop and layers taken out before it | Garcia 2005 |
| `mix` | built for a continuous DJ set | WP Techno |

- **In this skill**: [electronic.md](electronic.md), Techno: the pulse, the rumble, the acid line, polymeter, dub
  chords and repetition by process (`mix.filter_sweep`, `automation`, a delay that grows).
- **Variants**:
  - *Minimal techno*: a stripped-down style that exploits repetition and understated development (WP Minimal
    techno); Garcia (2005) draws on it and on tech house, a hybrid of house and techno, as the styles that use
    repetition most.
  - *Dub techno*: 110–125 BPM; deep, repetitive basslines; atmospheric soundscapes; chorded layers; slowly developing
    phrases in heavy delay and reverb, on percussion and melody alike (WP Dub techno).
- **Neighbours**: House (more riffs, vocals and samples); Ambient (the ambient-techno variant).

## Trance

Repeating melodic phrases over a four-on-the-floor beat, in a form that builds tension to one or two peaks, with a
breakdown that leaves the melody alone. `electronic/trance`

| Axis | Traits | From |
|---|---|---|
| `tempo` | 120–150 BPM, mostly 125–150; 4/4; techno and trance typically 120–140 in Ableton's lesson | WP Trance music, after Snoman 2009 and Hewitt 2008; Ableton Learning Music |
| `harmony` | minor keys almost universal; in the British approach, progressive chord structures | WP Trance music |
| `melody` | repeating melodic phrases; a lead motif first heard sliced and simplified before the breakdown | WP Trance music |
| `rhythm` | a kick on every downbeat, often a regular open hi-hat on the upbeat, the kick less emphasised than in house and techno to leave room for the bassline; rapid arpeggios; snare rolls that build in velocity, frequency and volume before transitions | WP Trance music |
| `timbre` | synthesizers; vocals, where there are any, mostly female soloists over the synths | WP Trance music |
| `form` | 16- or 32-beat phrases; tension built across the track to one or two peaks or drops; a mid-track climax, then a soft breakdown without beats or percussion, melody or atmospherics alone, then a new build | WP Trance music; Smith 2021 |
| `mix` | layers mixed with distinctly foreshadowed build-up and release | WP Trance music |

- **In this skill**: `supersaw_lead` or `sounds --role lead --character bright`, `trance_pad`, arpeggios on
  `pluck` or `sounds --role pluck` ([electronic-sounds.md](electronic-sounds.md)); a bassline the kick leaves room
  for; snare rolls and risers ([electronic.md](electronic.md), Form); `mix.gate` for the gated pads of hard trance.
- **Variants**:
  - *Uplifting trance*: fast, with its own kind of build-up, long breakdowns and large drops (WP Trance music).
  - *Hard trance*: faster, with gated pads; it set the breakdown-build-anthem template (WP Trance music).
  - *Psychedelic trance*: 125–150 BPM (full-on 140–148, dark psytrance from about 150); a bass that pounds through
    the whole track under varying rhythms; leads, rhythms and beats changing every eight bars, new layers every four
    to eight until a climax, then a breakdown and a new pattern over the same bass; a developed, atmospheric intro
    and a breakdown of thirty seconds to over a minute (WP Psychedelic trance).
- **Neighbours**: Festival EDM (simpler melodies, the electro-style drop); Techno (sequences, not melodic phrases).

## Festival EDM

Big room house: long build-ups to an electro-style drop over four-on-the-floor kicks, simple melodies, often a
supersaw, and large-hall reverb. `electronic/festival-edm`

| Axis | Traits | From |
|---|---|---|
| `tempo` | 126–132 BPM | WP Big room house |
| `harmony` | a single bassline, with a high or low line or two beside it, sets the mood of the whole track | WP Big room house |
| `melody` | simple and minimal, often on a supersaw | WP Big room house |
| `rhythm` | four-on-the-floor kicks; minimal drums, at times just a kick or a tom with two hi-hats | WP Big room house |
| `timbre` | the supersaw; the kick | WP Big room house |
| `form` | two build-ups with breaks, two drops, one or two breakdowns; one build-up much longer than the other | WP Big room house; Smith 2021 |
| `mix` | relative minimalism enlarged by large-hall reverb | WP Big room house |

- **In this skill**: [electronic.md](electronic.md), Form (the example layout of a big room track) and Production
  (pumping, loudness); `supersaw_lead` or a bright Surge lead; `reverb_db` with `space` `"hall"` on the lead.
- **Variants**:
  - *Electro house*: 125–135 BPM; heavy, buzzing basslines of distorted sawtooths; large four-on-the-floor kicks;
    prominent melodic riffs (WP Electro house).
- **Neighbours**: Trance (repeating melodic phrases, minor keys, long breakdowns); Hard dance (big room took up its
  structures and pitched kicks: WP Hardstyle).

## Hard dance

Hardstyle and hardcore: overdriven, distorted kicks at fast tempos, the kick itself pitched into a bassline.
`electronic/hard-dance`

| Axis | Traits | From |
|---|---|---|
| `tempo` | hardstyle about 140–150 BPM early, 150–160 modern; hardcore 160–200 or more, gabber 140–190 | WP Hardstyle; WP Hardcore (electronic dance music genre); WP Gabber |
| `harmony` | basslines played on the kick itself: a pitched kick | WP Hardstyle |
| `melody` | synthesizer melodies; dissonant synth "screeches" in early hardstyle | WP Hardstyle |
| `rhythm` | overdriven, hard kicks, often with an offbeat bass, the "reverse bass", within the same beat | WP Hardstyle |
| `timbre` | overdriven kicks made a bass tone by distortion, equalisation and layering; vocal samples; hardcore's distorted sawtooth kick | WP Hardstyle; WP Hardcore (electronic dance music genre) |
| `form` | no source read | |
| `mix` | saturation in hardcore | WP Hardcore (electronic dance music genre) |

- **In this skill**: the kick from `drum_synth` with `mix.saturate` 0.5 or more; a pitched kick as a synth part,
  `bass_808` (a sine with a pitch punch) under heavy `drive` and `saturate`, playing the bassline on the beats; the
  reverse bass as a synth bass on the off-beats whose `amp` `attack` swells into the next kick. These are this
  skill's approximations, not the producers' methods. Supersaw or bright Surge leads for the melodies.
- **Variants**: *rawstyle*, darker, with less melody or none and heavy use of screeches, against euphoric
  hardstyle (WP Hardstyle); *gabber*, superfast tempos, distorted kicks, house-style breakbeats and hi-hat fills,
  samples from films (WP Gabber).
- **Neighbours**: Festival EDM; Trance (hard trance led to hardstyle: WP Trance music).

## Drum and bass

Fast, syncopated breakbeats, chopped and rearranged, over deep sub-bass, with pads and samples above.
`electronic/drum-and-bass`

| Axis | Traits | From |
|---|---|---|
| `tempo` | usually 160–180 BPM, mostly 170–180 since about 1996; jungle about 160 by 1993; at about 140 the same elements make a breakbeat track instead | Ableton Learning Music; WP Drum and bass; Christodoulou 2020 |
| `harmony` | atmospheric pads: light ones, ambient pads and samples of jazz, or dark ones, dissonant pads and sci-fi samples | WP Drum and bass |
| `melody` | MCs in older styles; melodic instruments soloing in jazz-influenced styles | WP Drum and bass |
| `rhythm` | syncopated breaks from 1960s and 1970s soul and funk records, one crashing snare-and-cymbal break above all, sped up, cut into their smallest parts and reassembled into intricate, asymmetrical patterns ("choppage"); breakbeats stress weak positions; in early jungle the bass runs at half the tempo of the breaks, about 80 BPM | WP Drum and bass; Christodoulou 2020, after Chapman 2003 and Butler 2006 |
| `timbre` | a deep sub-bass pattern felt through the sound system; the reese bassline; bass instruments played by hand less common | WP Drum and bass |
| `form` | a build and a breakdown before the drop, where the rhythm or the bassline switches; the drums often fade to an ambient intro and come back more complex with a heavier bass | WP Drum and bass |
| `mix` | sparse arrangements that leave room for basslines deeper than in most dance music; the full frequency range, sub-bass felt more than heard | WP Drum and bass |

- **In this skill**: no sampled breaks: write the break as notes, in the `funk` feel of the drummers' statistics
  ([building-blocks.md](building-blocks.md)) at 170–175 BPM, on the sampled `rusty` kit or `drum_synth`, and rearrange
  its sixteenth-note cells bar by bar as the producers chop theirs. `reese_bass` or `sub_bass`
  ([electronic-sounds.md](electronic-sounds.md)); Surge pads, light or dark; a high-pass `filter_sweep` on the break for
  an intro that teases it without its low end, then opens, as an ambient-jungle track does (Christodoulou 2020).
- **Variants**:
  - *Jungle*: about 160 BPM; rapid breakbeats; heavily syncopated percussion loops; the deep basslines, melodies and
    vocal samples of dub, reggae and dancehall (WP Jungle music; Christodoulou 2020).
  - *Liquid*: the same basslines and bar layouts with more instrumental layers, harmonies, melodies and ambience,
    from jazz, soul and sometimes blues (WP Liquid drum and bass).
  - *Neurofunk*: cleaner production, intricate basslines, subtle changes of timbre, more regular two-step rhythms
    than jungle's dense ones (WP Neurofunk).
  - *Two-step*: the mainstream form: a dominant kick on beats 1 and 3, sparse, repetitive hits that leave room for a
    pop melody (Christodoulou 2020).
- **Neighbours**: Dubstep (140 BPM, the snare on beat three, sparser); UK garage (130 BPM, shuffled); breakbeat at
  130–140 (WP Drum and bass).

## UK garage

Shuffled, syncopated hats and snares, four-on-the-floor or broken "2-step" kicks, and chopped, pitched vocal
samples at about 130 BPM. `electronic/uk-garage`

| Axis | Traits | From |
|---|---|---|
| `tempo` | about 130 BPM | WP UK garage |
| `harmony` | sub-bass lines; influences of garage house, gospel and R&B | WP UK garage |
| `melody` | vocal samples chopped, time-stretched or pitch-shifted; vocal phrases played like an instrument, syllables reversed or pitch-shifted | WP UK garage |
| `rhythm` | percussive, shuffled rhythms; syncopated hats, cymbals and snares; 4/4 house kicks or 2-step: the second and fourth kicks removed and the third shifted; off-beat snares, scattered rimshots and woodblocks; syncopated basslines | WP UK garage; WP 2-step garage |
| `timbre` | synth basslines; pads or strings played percussively | WP 2-step garage |
| `form` | no source read | |
| `mix` | no source read | |

- **In this skill**: drums with `performance.swing` `{"ratio": 0.6–0.67, "unit": 0.25}` on the hats and snares for
  the shuffle (the ratio is this skill's starting point); `blocks.drums` with `kick="syncopated"` for 2-step, or
  `"four_floor"`; short `vocal_ah` notes, with `bend`, where a chopped vocal would go; `sub_bass` or a Surge bass.
  `review` asks about pushes here: the bassline is syncopated (WP 2-step garage).
- **Variants**:
  - *2-step*: two kicks a bar that skip a beat, shuffles or triplets on the other percussion (WP 2-step garage).
  - *Speed garage*: a sped-up house beat at 130 with rolling snares and warped, sweeping, half-tempo basslines from
    jungle and reggae (WP Speed garage).
- **Neighbours**: House (four-on-the-floor, garage house's piano and vocals); Dubstep (grew out of 2-step's bass).

## Dubstep

Half-time syncopation at 140 BPM, a clap or snare on beat three, prominent sub-bass or wobble bass, dark and
minimal. `electronic/dubstep`

| Axis | Traits | From |
|---|---|---|
| `tempo` | typically 135–145 BPM, mostly 140; Wikipedia's 132–142 cites no source | Ableton Learning Music; WP Dubstep, after McKinnon 2007 (CBC) |
| `harmony` | dark: often a minor key or the Phrygian mode; dissonance such as a tritone within a riff | WP Dubstep |
| `melody` | mostly instrumental; riffs | WP Dubstep |
| `rhythm` | a clap or snare usually on the third beat of the bar; syncopated, often shuffled or in tuplets; early dubstep closer to 2-step drum patterns | WP Dubstep |
| `timbre` | prominent sub-bass; the wobble bass, a long bass note shaped rhythmically by an LFO on volume, distortion or filter cutoff | WP Dubstep |
| `form` | intro; a main section with a bass drop; a middle section; another main section much like the first; outro; the drop often after bar 16 or 32, the percussion pausing, often to silence, then resuming with more intensity and a dominant sub-bass | WP Dubstep |
| `mix` | more minimal than other garage styles, focused on the sub-bass | WP Dubstep |

- **In this skill**: `blocks.drums` with `backbeat="half"`; `wobble_bass` (its `lfo` with `rate_beats` 0.5 or 0.25)
  or `sub_bass`, a Surge bass with a wobble on its filter ([electronic-sounds.md](electronic-sounds.md));
  `mix.mono_below_hz` for the sub. `review` asks about pushes here: the rhythms are syncopated (WP Dubstep).
- **Variants**:
  - *Brostep*: harder and aggressive; distorted bass riffs in the middle register in place of sub-bass, in the
    register of a heavy-metal guitar (WP Dubstep).
  - *Chillstep*: softer and more melodic, with elements of ambient and chill-out music (WP Dubstep).
- **Neighbours**: UK garage; Drum and bass (breakbeats at 160–180); Future bass (which mixes dubstep with EDM trap).

## Future bass

Warm, wobbling chords on the beat's swells, risers and arpeggiated chords, between dubstep and EDM trap but less
abrasive. `electronic/future-bass`

| Axis | Traits | From |
|---|---|---|
| `tempo` | 130–175 BPM; 4/4 | WP Future bass |
| `harmony` | arpeggiated chords | WP Future bass |
| `melody` | vocal chops, vocoders | WP Future bass |
| `rhythm` | warmer, less abrasive rhythms than dubstep and EDM trap | WP Future bass |
| `timbre` | sound waves modulated by automation or an LFO on a filter's cutoff or on the amplitude, a wobbly effect; a twinkly, gradual rise in pitch in the risers before the drop | WP Future bass |
| `form` | risers into drops | WP Future bass |
| `mix` | no source read beyond pumping ([electronic.md](electronic.md)) | |

- **In this skill**: [electronic.md](electronic.md), Future bass: `future_bass_chord` or `sounds --role chords
  --character wide`, ducked by the kick; an `lfo` on pitch or cutoff; `vocal_ah` chops with a dotted-eighth delay.
- **Variants**:
  - *Kawaii future bass*: a happy, cute timbre with strong Japanese pop-culture influence; chiptune sounds, soft
    square waves, percussion instruments, door and bed squeaks, samples from anime or games (WP Future bass). Here:
    `chip_square` and the other chip presets, glockenspiel and toy-like patches (`sounds --name music_box`, `--name
    bell`). No squeak samples, and never a sample of a work.
- **Neighbours**: Dubstep; EDM trap; fast electro J-pop (`jpop/fast-electro`).

## EDM trap

Hip-hop trap's 808s and hi-hats with EDM's build-ups, drops, breakdowns and rave synthesizers. `electronic/edm-trap`

| Axis | Traits | From |
|---|---|---|
| `tempo` | typically 140 BPM | WP EDM trap music |
| `harmony` | no source read | |
| `melody` | dark melodies; vocal samples typical of hip-hop trap | WP EDM trap music |
| `rhythm` | the TR-808's drums as in hip-hop trap ([beats.md](beats.md)) | WP EDM trap music |
| `timbre` | dense production with rave synthesizers; techno, dub and electro sounds with TR-808 drum samples | WP EDM trap music |
| `form` | build-ups, strong bass drops, breakdowns | WP EDM trap music |
| `mix` | dynamic and boisterous, against hip-hop trap | WP EDM trap music |

- **In this skill**: the trap drums and `bass_808` of [beats.md](beats.md) (`blocks.drums` `rolls` for the hats),
  with the build and drop of [electronic.md](electronic.md); `brass_stab` or bright Surge leads for the rave synths.
- **Neighbours**: hip-hop trap in [beats.md](beats.md) (no build-ups or drops); Future bass; Dubstep.

## Electro

Mechanical, syncopated TR-808 beats from funk and early hip-hop, programmed basslines, arpeggiated riffs and
science-fiction effects. `electronic/electro`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | programmed basslines; eerie synthetic strings or pads | WP Electro (music) |
| `melody` | sequenced or arpeggiated synthetic riffs; mostly instrumental, vocals through a vocoder or speech synthesis | WP Electro (music) |
| `rhythm` | electronic emulations of breakbeats: a syncopated kick, a snare or clap on the backbeat, more mechanical than sampled breaks; staccato drum patterns | WP Electro (music) |
| `timbre` | the TR-808: its deep bass drum, handclaps, open and closed hats, clave and cowbell; analogue synthesis; atonal sound effects | WP Electro (music) |
| `form` | no source read | |
| `mix` | heavy reverb, delay, chorus or phaser | WP Electro (music) |

- **In this skill**: `drum_synth` with `kit.style` `"808"` (cowbell 56; no clave), `blocks.drums` with
  `kick="syncopated"` and `programmed=True`; `pluck` or Surge plucks with `arpeggio`; `pwm_strings` or a Surge string
  machine for the pads; `effects` `phaser` and `chorus`. No vocoder: the riff or a lead takes the vocal line.
- **Neighbours**: breakbeat, whose breaks have a human feel (WP Electro (music)); Techno; Synthwave.

## Eurobeat

The hi-NRG-driven Italo disco made from the early 1990s and popular in Japan: a sequenced octave bass, a thunderous
synth riff after the intro and after each chorus, and each repeat of a section arranged anew. `electronic/eurobeat`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | a sequenced octave bass; IV–V–vi, which Japanese pop calls the "Eurobeat progression" | WP Eurobeat; Uehara, Itoh and Takatsuka 2016 (Table 1) |
| `melody` | very complex melodies; the "sabi", a highly technical synth riff, which can resemble the chorus | WP Eurobeat |
| `rhythm` | tight, rhythmic percussion in the background | WP Eurobeat |
| `timbre` | energetic, heavy synths; brass and harp sounds; electric guitars from the mid-1990s; the riff layered on up to twenty tracks | WP Eurobeat |
| `form` | an introduction like the verse, bridge or chorus played instrumentally; verse, bridge and chorus repeated, each time with a different arrangement; the riff after the introduction and after the chorus | WP Eurobeat |
| `mix` | no source read | |

- **In this skill**: `synthwave_bass` or a Surge bass in octaves; `brass_stab` and Surge brass; the concert harp
  (`vcsl`); the electric guitars (`fsbs_dist1`, `fsbs_clean`); the riff doubled on several synth parts. A lead takes
  the vocal line. `review`'s question on literal returns fits the style: each return is arranged anew.
- **Neighbours**: Trance; Festival EDM; fast electro J-pop (`jpop/fast-electro`).

## Synthwave

The sound of 1980s action, science-fiction and horror film scores and synth-pop, revived with nostalgia.
`electronic/synthwave`

| Axis | Traits | From |
|---|---|---|
| `tempo` | 80–118 BPM; upbeat tracks 128–140 | WP Synthwave |
| `harmony` | no source read; this skill's four-chord loops are in [electronic.md](electronic.md) | |
| `melody` | no source read | |
| `rhythm` | the drum machines of the 1980s, the LM-1 and TR-808, with gated-reverb snares | Merlini 2023 |
| `timbre` | the arpeggiated, fat bass of early-1980s polysynths; synthesizers; elements of 1980s rock and metal in some | Merlini 2023; WP Synthwave |
| `form` | no source read | |
| `mix` | the thicker sound of present-day EDM | Merlini 2023 |

- **In this skill**: [electronic.md](electronic.md), Synthwave; `fsbs_dist1` for the rock and metal elements.
- **Variants**: *Darksynth*: influenced by horror cinema, darker, with post-punk, industrial and EBM sounds (WP
  Synthwave).
- **Neighbours**: Electro; the Horror map's ostinato pulse (`horror/ostinato-pulse`) for darksynth's dread.

## Chiptune

Music made with, or in the manner of, the sound chips of old consoles and computers: few voices, simple waves, quick
arpeggios for chords. `electronic/chiptune`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | chords as quick arpeggios, the chip's few voices emulating polyphony | WP Chiptune |
| `melody` | melody and harmony on the pulse channels, the bass on the triangle | electronic.md (Collins 2007; Cook 2023; NESdev) |
| `rhythm` | drums on the noise channel | electronic.md (NESdev) |
| `timbre` | defined by its instruments: pulse waves whose duty cycle sets the timbre, square, triangle and sawtooth waves, a noise generator | WP Chiptune; NESdev |
| `form` | short loops, a composer's choice as much as a technical limit | Collins 2007 |
| `mix` | dry; this skill's practice ([electronic.md](electronic.md), Chiptune) | |

- **In this skill**: [electronic.md](electronic.md), Chiptune: the NES's channels on `chip_pulse12`,
  `chip_pulse25`, `chip_square`, `chip_triangle`, `chip_noise` and `chip_arp`.
- **Variants**:
  - *Game Boy*: two pulse channels at 12.5, 25, 50 or 75% duty, one 4-bit wave channel and noise (WP
    Chiptune). No preset plays the waveform channel; the triangle is nearest.
  - *Commodore 64*: the SID's three voices, each pulse, sawtooth, triangle or noise, with full control of the pulse
    width, ring modulation and resonant filters (WP Chiptune). The synth plays pulse with `pwm`, sawtooth, triangle,
    noise and a resonant `filter`, not ring modulation.
- **Neighbours**: Future bass's kawaii variant; game music ([game-music.md](game-music.md)).

## Ambient

Tone and atmosphere over structure and rhythm: textural layers, often without beat or structured melody, calm, "as
ignorable as it is interesting". `electronic/ambient`

| Axis | Traits | From |
|---|---|---|
| `tempo` | often no beat | WP Ambient music |
| `harmony` | held or repeated notes, drone-like; with minimalism, steady drones and consonant harmony | WP Ambient music |
| `melody` | often without structured melody | WP Ambient music |
| `rhythm` | often without a beat; repetitive patterns or pulses, shared with minimalism | WP Ambient music |
| `timbre` | textural layers; piano, strings and flute, often on a synthesizer; nature soundscapes | WP Ambient music |
| `form` | atmosphere over traditional structure | WP Ambient music |
| `mix` | music to accommodate many levels of listening attention, "as ignorable as it is interesting" (Eno, quoted there) | WP Ambient music |

- **In this skill**: slow pads (`sounds --role pad --character slow`, `warm_pad`); the pianos, strings and flutes of
  the sampled banks; `noise` parts for air; the ocean drum of `vcsl_world` for waves; long reverb (`space` `"hall"`
  or `"church"`) and a `tail_seconds` that lets it ring. `review` does not ask about loops, static textures, sections
  alike or melodic restatement here: drones, repetition and the absence of structure are the style (WP Ambient
  music).
- **Variants**:
  - *Dark ambient*: ominous, dark drones, discordant overtones, a gloomy, monumental atmosphere (WP Ambient music).
  - *Ambient techno*: ambient atmospheres with the rhythms and melodies of techno; *ambient house*: house's
    four-on-the-floor beats with synth pads in an atmospheric style (WP Ambient music).
- **Neighbours**: the Horror map's drone dread (`horror/drone-dread`) for dark ambient; the Orchestral map's
  minimalist entry (`orchestral/minimalist`).

## IDM

Electronic music for listening that keeps dance music's binary rhythms, repetition and forms and makes their rhythm
and timbre complex. `electronic/idm`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | melody, atmosphere and emotion in its early phase | WP Intelligent dance music (Reynolds) |
| `rhythm` | binary rhythms made complex; microrhythmic sets, groups of very rapid events, some contrasting with the surrounding rhythm, some suggesting its continuation | WP Intelligent dance music (Papavassiliou) |
| `timbre` | recorded sound manipulated as material: granular synthesis, slicing, time-stretching, sound "freezing"; recognisable machine timbres | WP Intelligent dance music (Papavassiliou; Ramsay) |
| `form` | conventional forms with repetition | WP Intelligent dance music (Papavassiliou) |
| `mix` | reverberation and echo shaping the space | WP Intelligent dance music (Ramsay) |

- **In this skill**: `drum_synth` with rapid groups written as notes (thirty-seconds and finer, rolls); `effects`
  `bitcrush`, `mix.gate`, filter sweeps and delays. No granular synthesis, time-stretching or freezing.
- **Neighbours**: Techno and Ambient (the ambient-techno variant); Drum and bass.

## Sources

- Ableton. *Learning Music*, [Tempo and genre](https://learningmusic.ableton.com/make-beats/tempo-and-genre.html),
  read 9 November 2026: "typical" tempo ranges for dub, hip-hop, house, techno and trance, dubstep, and drum and
  bass.
- Butler, M. J. (2006). *Unlocking the Groove: Rhythm, Meter, and Musical Design in Electronic Dance Music*. Indiana
  University Press. Not read here; cited through Garcia (2005, the loop as EDM's unit) and Christodoulou (2020, the
  breakbeat's stress on weak positions).
- Christodoulou, C. (2020). [Bring the Break-Beat Back! Authenticity and the Politics of Rhythm in Drum 'n' Bass](https://dj.dancecult.net/index.php/dancecult/article/view/1153).
  *Dancecult* 12(1), 3–21, [doi:10.12801/1947-5403.2020.12.01.08](https://doi.org/10.12801/1947-5403.2020.12.01.08).
  With Chapman (2003) on chopping breaks.
- Collins, K. (2007); Cook, K. M. (2023); NESdev wiki: in [electronic.md](electronic.md).
- Garcia, L.-M. (2005). [On and On: Repetition as Process and Pleasure in Electronic Dance Music](https://mtosmt.org/issues/mto.05.11.4/mto.05.11.4.garcia.php).
  *Music Theory Online* 11(4): loops and looping, accumulative form, changes on multiples of four.
- Merlini, M. (2023): in [electronic.md](electronic.md).
- Moelants, D. (2008). Hype vs. natural tempo: a long-term study of dance music tempi. *Proceedings of ICMPC 10*,
  Sapporo. Not read here; cited by Nieto et al. (2019) for 128 BPM as dance music's most common tempo.
- Nieto, O., McCallum, M., Davies, M. E. P., Robertson, A., Stark, A. and Egozy, E. (2019). [The Harmonix Set: Beats,
  Downbeats, and Functional Segment Annotations of Western Popular Music](https://archives.ismir.net/ismir2019/paper/000068.pdf).
  *Proceedings of ISMIR 2019*, 565–572: 912 full tracks annotated by professional musicians, chosen for rhythm
  games with a lean toward EDM and danceable pop; the annotations under the MIT licence. The tempos and section
  lengths by the set's genre labels are measured here: the metadata's BPM, and the downbeats from each section's
  start to the next.
- Smith, J. W. (2021). [The Functions of Continuous Processes in Contemporary Electronic Dance Music](https://mtosmt.org/issues/mto.21.27.2/mto.21.27.2.smith.html).
  *Music Theory Online* 27(2): continuous processes as ornament, orientation and disorientation; the build-up and
  the drop. With Wright (2017) and Snoman (2019), cited there.
- Snoman, R. (2009). *The Dance Music Manual*, 2nd ed. Focal Press, pp. 251–253, 266; and Hewitt, M. (2008). *Music
  Theory for Computer Musicians*. Course Technology. Not read here; cited by WP Trance music for its tempo ranges.
- Tan, I., Lustig, E. and Temperley, D. (2019), in [development-and-groove.md](development-and-groove.md).
- Uehara, M., Itoh, T. and Takatsuka, M. (2016). [Japanese pop music visualization focused on chord progression
  patterns](https://www.art-science.org/journal/v15n4/v15n4pp177/artsci-v15n4pp177.pdf) (in Japanese). *Transactions
  of the Society for Art and Science* 15(4), 177–184. Table 1 lists the chord progressions frequent in J-pop by
  the names Japanese pop gives them.
- Wikipedia, read 9 November 2026: [House music](https://en.wikipedia.org/wiki/House_music),
  [Deep house](https://en.wikipedia.org/wiki/Deep_house), [Acid house](https://en.wikipedia.org/wiki/Acid_house),
  [Techno](https://en.wikipedia.org/wiki/Techno), [Minimal techno](https://en.wikipedia.org/wiki/Minimal_techno),
  [Dub techno](https://en.wikipedia.org/wiki/Dub_techno), [Trance music](https://en.wikipedia.org/wiki/Trance_music),
  [Psychedelic trance](https://en.wikipedia.org/wiki/Psychedelic_trance),
  [Big room house](https://en.wikipedia.org/wiki/Big_room_house),
  [Electro house](https://en.wikipedia.org/wiki/Electro_house), [Hardstyle](https://en.wikipedia.org/wiki/Hardstyle),
  [Hardcore (electronic dance music genre)](https://en.wikipedia.org/wiki/Hardcore_(electronic_dance_music_genre)),
  [Gabber](https://en.wikipedia.org/wiki/Gabber), [Drum and bass](https://en.wikipedia.org/wiki/Drum_and_bass),
  [Jungle music](https://en.wikipedia.org/wiki/Jungle_music),
  [Liquid drum and bass](https://en.wikipedia.org/wiki/Liquid_drum_and_bass),
  [Neurofunk](https://en.wikipedia.org/wiki/Neurofunk), [UK garage](https://en.wikipedia.org/wiki/UK_garage),
  [2-step garage](https://en.wikipedia.org/wiki/2-step_garage), [Speed garage](https://en.wikipedia.org/wiki/Speed_garage),
  [Dubstep](https://en.wikipedia.org/wiki/Dubstep), [Future bass](https://en.wikipedia.org/wiki/Future_bass),
  [EDM trap music](https://en.wikipedia.org/wiki/Trap_music_(EDM)),
  [Electro (music)](https://en.wikipedia.org/wiki/Electro_(music)), [Eurobeat](https://en.wikipedia.org/wiki/Eurobeat),
  [Synthwave](https://en.wikipedia.org/wiki/Synthwave), [Chiptune](https://en.wikipedia.org/wiki/Chiptune),
  [Ambient music](https://en.wikipedia.org/wiki/Ambient_music),
  [Intelligent dance music](https://en.wikipedia.org/wiki/Intelligent_dance_music).
- Zeiner-Henriksen, H. T. (2010): in [electronic.md](electronic.md).
