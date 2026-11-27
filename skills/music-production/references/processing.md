# Processing a part: its gate, EQ, dynamics and effects

Read this when setting a part's processing in its `mix`: a noise gate, the EQ, compression, the modulation and lo-fi effects,
a chain of Surge XT's effects (`mix.surge_fx`), or when a render's receipt or summary says something of them. The fields
themselves, with their limits: [schema.md](schema.md). Levels, sends and the bus chain: [performance-and-mix.md](performance-and-mix.md);
an electric guitar's amplifier (`mix.amp`): [rock-and-metal.md](rock-and-metal.md); the production tools of electronic styles
(ducking, tempo-synced delay, sweeps, saturation, gates by pattern): [electronic.md](electronic.md).

Contents: [The order a part goes through](#the-order-a-part-goes-through) · [Correcting first](#correcting-first) · [Character](#character) · [Surge XT's effects](#surge-xts-effects-mixsurge_fx) · [What the render says](#what-the-render-says) · [Sources](#sources)

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own tools, measured here or
read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources
named give the practice; a starting value is no norm of the style.

Each step costs a render; a part's processing is set once, with the piece's other mix decisions, and changed only where a
measurement (`analyze`, a receipt) or the user's listening asks for it.

## The order a part goes through

A part's raw take passes through these, in this order (musiclib/render.py), each only where the part asks for it:

1. its amplifier (`amp`), then its level (`level_dbfs`) and its high- and low-pass;
2. the noise gate (`noise_gate`);
3. the EQ (`eq`), the bands in the order listed;
4. the effects (`effects`), in the order listed: chorus, phaser, bitcrush, tremolo, flanger;
5. the compressor (`compressor`);
6. Surge XT's effects (`surge_fx`), in the order listed, then a 5 Hz DC filter and the part brought back to the level it
   entered the chain at;
7. its width and its static pan (a part on the stage or one that moves takes its place instead, after the automation), its
   automation, its stage position or movement, then the production tools (wow and flutter, filter sweep, saturation, gate by
   pattern, delay, ducking);
8. the bus, and the sends to the reverbs (`reverb_db`, `delay_db`).

The amplifier distorts first, as distortion goes at the front of a chain so that what follows works on its harmonics; a gate
goes before compressors, delay and reverb; delay and reverb come last (White 1997, 2002). Inside one `surge_fx` chain the order
is the part's own: drive or shaping first, then modulation, then delay, then reverb, as the same articles give it. A flanger
before a reverb gives a shimmer, after it the whole tail sweeps; a chorus usually comes before the reverb (White 1997, 2002).

## Correcting first

Correction makes a part sit in the mix; it is the same in every style.

- **Cut before boosting where the move is narrow.** Broad moves are interchangeable, brighter by raising the highs or by cutting
  the low mids, but a narrow boost sounds unnatural, while a narrow cut can take out a resonance the source already has (Mynett
  2018). Distortion's harmonics make such resonances in a guitar, more with fast subdivisions and low tunings; the regions he
  names: droning 125–220 Hz, muddy 200–300 Hz, woolly near 400 Hz, nasal 500–800 Hz, abrasive 2.5–4 kHz. A narrow cut is an
  `eq` peak with a negative `db` and a high `q` (8 is narrow); a `notch` takes its band out altogether.
- **Watch the 4 kHz octave.** Mixes with relatively more energy there were rated lower (De Man et al. 2015), and the 2–4 kHz
  "bite" of distorted guitars is shared with the cymbals (Senior 2019). `analyze` gives each section's band shares.
- **Compress where the level jumps note to note.** Engineers compress mainly to steady an erratic level, in vocals and drums
  above all; percussive sources take shorter time constants (attack usually 5–250 ms, release 5–3000 ms); a soft knee is more
  transparent; make-up gain brings the output back to the input's loudness (Ma et al. 2015). Start by lowering the threshold to
  6 dB of reduction on peaks, then raise it to the least that works; about 1.5:1 nudges, up to 3:1 is routine, 12:1 catches
  isolated peaks; a dynamic electric guitar near 2:1 (Senior 2009). For drums: a snare at 5:1 with a fast attack set so the hit
  is not squashed, a kick's slow attack and fast release pushing its front; several stages of 3–4 dB rather than one large one;
  too fast an attack makes the drums smaller (Rogers 2022). In the skill: `{"threshold_db", "ratio", "attack_ms", "release_ms"}`
  with `knee_db`, `makeup_db`, `mix` (below 1, the dry signal mixed back) and `detection`.
- **Leave alone what already balances.** Overdriven guitars rarely need compressing, the overdrive having already narrowed their
  dynamics; balance them with level automation (Senior 2019). Don't compress a part that balances; a bass with too much low end
  and a lead that needs to be understood want EQ and automation first (Senior 2009).
- **Keep the short-term dynamics.** At equal loudness, listeners preferred the mixes that varied more over short times and were
  less squashed (De Man et al. 2015).
- **Gate a part with noise between its notes**, such as an amplified part's hiss between strokes: `noise_gate` with its threshold
  above the noise and under the quietest note meant to sound (FFmpeg's agate at a ratio of 10: measured on held tones, 2 dB
  under the threshold about 5 dB off, 8 dB or more under it down to the floor). `range_db` is how far it falls when closed: this skill starts
  at −40 (its default) and goes towards 0 for a gate that only thins the gaps. Attack 2 ms and release 120 ms are its defaults;
  a part whose notes ring longer wants a longer release, so the gate does not cut their tails.

## Character

Character is the part's sound as the style shapes it, and styles differ in how far they shape it. Classical, jazz, folk and
country records have long aimed at fidelity to a performance, while in rock the record's own sound is part of the work (Gracyk
1996, as Brown 1998 reads him); from the 1960s rock and pop records left the illusion of a concert hall behind and built their
sound with editing, overdubbing and compression (Moorefield 2005). Classical recording still mostly recreates an idealised hall
(Capulet and Zagorski-Thomas 2017), and an engineer of acoustic ensembles takes the sound from the microphones' placement, the
room and where the players sit, EQ a last resort and compression light (King, in Senior 2015). Natural is not untouched: a jazz
band recorded live to stereo still had its bass compressed hard and its piano equalised (Robjohns 2003). So in the acoustic
styles the corrective moves above are most of the work; in pop, rock, electronic music and beats, character effects are part of
the arrangement. How a style shapes its sounds, and with what, is in its guide and on its map ([style-maps.md](style-maps.md)):
the anime opening's and rock's guitars by voicing and section, electronic music's production tools, lo-fi's worn media
([beats.md](beats.md)). Across them:

- **The tone goes with the voicing.** With more distortion, listeners rate power chords and major triads as more pleasant than
  richer chords, and a distorted triad sounds much like a power chord (Herbst 2019; Lilja 2015): chords with added tones ask for a
  clean or slightly broken-up tone (`clean`, `edge`), power chords may take more gain ([rock-and-metal.md](rock-and-metal.md)).
  Doubled guitars each take less gain than one alone seems to need (Senior 2019).
- **A clean guitar whose pick is heard and which breaks up a little.** Guitarists call it the edge of breakup: the amplifier set
  where a clean sound just starts to distort (Godfrey et al. 2026), so that a light touch stays clean and digging in adds grit
  (Barnard 2024); for country guitar, clean "with just a hint of edge when played hard" (White 1996). A compressor's longer
  attack lets the pick through, too fast an attack flattens it (White 2002b). In the skill: `mix.amp` with the voice `edge` (or
  `clean` driven harder), velocities that vary by stroke, since the amplifier's input follows them, and a compressor, if any,
  with an attack of 20 ms or more ([rock-and-metal.md](rock-and-metal.md)).
- **A sound is chosen and treated by the piece's idea.** Where a guide offers a part several sounds or treatments, the piece's
  whole chooses among those its style allows (SKILL.md, step 2), a level it gave in `association.gives`, the reason in
  `decisions` ([sound-selection.md](sound-selection.md)).

Which tool for which effect:

| For | Use | Why this one |
|---|---|---|
| a shared room, plate, hall or church | the part's `reverb_db` send (bus chain) | every part in one space; the mix's clarity (`c80_db`) moves them together |
| a part's own reverb as part of its sound (a spring on a clean guitar, a long wash on one pad) | `surge_fx` `spring_reverb`, `reverb_1` or `reverb_2`, its `output_mix` low on a part that should stay in front | an insert on one part |
| echoes on the beat | the production `delay` (`{"beats", ...}`) | it lands each echo on the tempo map, to the sample; Surge's delay times are absolute |
| an echo with modulated, filtered repeats | `surge_fx` `delay`, its times in ms (60000 ÷ BPM × beats: a dotted eighth at 120 BPM is 375 ms) | its feedback filters and modulation |
| chorus, phaser, flanger, tremolo | `effects` (the chorus the skill's own, run between FFmpeg's passes; the phaser, tremolo and flanger FFmpeg's) or `surge_fx` (`chorus`, `ensemble`, `phaser`, `flanger`, `rotary_speaker`) | the `effects` are simple and light; Surge's have more voices, stages and filters |
| drive or colour after the amplifier, on any part | `surge_fx` `distortion`, `waveshaper`, `bonsai`, `exciter`; `saturate` (production) | Surge's types for a chosen model, curve or band, hard clipping and folding among them; `saturate` without Surge XT, at four times the rate, its level kept: a number is tanh, `{"drive", "curve"}` one of four rounded curves, from the softest knee (`atan`: at full drive the third harmonic 13.0 dB under a 1 kHz fundamental) through `alg` and `tanh` to the firmest (`erf`, 10.3 dB) |
| lo-fi: fewer bits, a lower rate | `effects` `bitcrush`; production `wow_flutter` | [beats.md](beats.md) |

## Surge XT's effects (`mix.surge_fx`)

A chain of one to four effects from Surge XT Effects, applied in the order listed:
`"surge_fx": [{"type": "chorus", "params": {"modulation_rate": 0.6, "output_mix": 30}}, {"type": "reverb_2", "params": {"output_mix": 20}}]`.
Every type, parameter, unit and limit is in [surge-fx.json](surge-fx.json); a value outside its limits or a name it lacks is
refused before the render. Each parameter left out takes the table's default, which is the value Surge XT sets when the type is
chosen, read back here, except four of the distortion's (below). Times are absolute (no parameter follows the tempo).

What to watch, by type (the defaults and behaviour measured here, on Surge XT Effects 1.3.4):

| Type | For | Watch |
|---|---|---|
| `reverb_1`, `reverb_2` | a reverb of the part's own | defaults: `output_mix` 50 and 33 %, decay 2 s and 1.7 s: far wetter than an insert on a part in front usually is |
| `spring_reverb` | a spring tank's twang and drip (a clean guitar, a surf part) | its chaos and knock are left out: they did not render the same twice |
| `chorus` | doubling and width | default `output_mix` 100 % (only the delayed voices) and its high cut at 3.5 kHz: set `output_mix` (30–50 % for a chorus beside the dry sound) and `eq_high_cut` |
| `ensemble` | a string machine's thick bucket-brigade ensemble | `delay_type` picks the stages; width −100 to 100 % |
| `phaser` | a sweeping notch | default `modulation_depth` 0 %: it does not sweep until set |
| `flanger` | combs that sweep | its `output_mix` is the combs' level and polarity, −100 to 100 %, not a dry/wet blend: in "Dry + Combs" the dry signal stays at 0.40 of its level, in "Combs Only" a mix of 0 % is silent |
| `rotary_speaker` | an organ's rotating horn and drum | `speaker_horn_rate` and `speaker_rotor_rate` set slow or fast |
| `distortion` | a drive with pre- and post-EQ | Surge XT's own defaults leave drive, feedback and both high cuts to the type before; the table sets drive 0 dB, feedback 0 % and the high cuts at their maximum. A post-EQ high cut tames the fizz |
| `waveshaper` | a chosen transfer curve (soft, folds, harmonics, fuzz) | default `shaper_shape` "Off": it shapes nothing until a shape is set |
| `exciter` | added upper harmonics | default `output_mix` 50 % |
| `bonsai` | saturation and bass boost, with a noise section | at the defaults its noise added nothing measurable (in silence and under a tone); with `noise_gain` and `noise_sensitivity` at their tops, noise at −35 dB in silence |
| `delay` | stereo echoes with filtered, modulated feedback | default times 250 ms, feedback 50 %, mix 50 % |

Measured here on each type: every setting at the ends of every parameter, and three random settings each, render the same
twice; at a mix of 0 % every type with a mix but the flanger, whose mix is its combs' level, gives back the dry signal (all
but the 5 Hz high-pass's difference); none reports latency, and at its defaults each lines up
with its input but the distortion, 2 samples late (the waveshaper set to a shape 4, the exciter 5: about 0.1 ms). A host delays
the other tracks by the latency a plug-in reports (Steinberg's VST 3 SDK, `getLatencySamples`; Houghton 2010), so a DAW would
leave these as they are too; on one part they are inaudible.

## What the render says

- **The receipt** (`stem_receipts.json`, the part's `surge_fx`): `state` (`applied` or `bypassed` with its `reason`), each
  effect with every parameter as the plugin showed it (`shown`), and `level_change_db`, by how much the chain had moved the
  part's level before the render brought it back. A chain is followed by a 5 Hz first-order high-pass (−0.12 dB at 30 Hz): an
  asymmetric curve leaves a nonzero mean, which a DC blocker after it removes (Smith, DC Blocker; the Faust library's
  `cubicnl`), and a high-pass at a few hertz, typically 3 or 5, removes a DC offset (Sound On Sound's glossary). Then one gain
  returns the part to the level it entered the chain at, as an engineer aims for about the same level out of each plug-in as
  goes in, louder being heard as better (Houghton 2013), measured as the part's level is (`level_mode`: its active RMS by
  default, which follows loudness rather than sample peaks as Houghton 2026 advises, or its peak where the part asks for
  that), so that `level_dbfs` stays the part's level.
- **The summary** prints the parts that played without their chains and why, and any chain that moved its part's level 12 dB or
  more: such a chain usually has a gain, a drive or a mix at an extreme (with the distortion's leftover settings, noise bursts
  came out 38 dB lower). A chain that leaves a part silent stops the render with the part named.
- **Without Surge XT Effects** (not installed, or a file changed), the part plays without its chain; its receipt, `report.json`
  (`surge_fx`) and the summary say so, also when the stem comes from the cache. `studio.py doctor` says whether it is installed.
  A run that fails with the plugin in place is not kept: the next render tries the chain again.
- **The FFmpeg tools** are in the receipt's `filter_chain`, written as FFmpeg runs them.

## Sources

- Barnard, S. (2024). [What is a double stop on guitar?](https://www.guitarworld.com/lessons/improve-your-double-stops) *Guitar World*, 28 May 2024.
- Brown, L. B. (1998). [Documentation and Fabrication in Phonography](https://www.bu.edu/wcp/Papers/Aest/AestBrow.htm). Twentieth World Congress of Philosophy, Boston (reading Gracyk 1996).
- Capulet, E. and Zagorski-Thomas, S. (2017). [Creating a Rubato Layer Cake: performing and producing overdubs with expressive timing on a classical recording for 'solo' piano](https://www.arpjournal.com/asarpwp/creating-a-rubato-layer-cake-performing-and-producing-overdubs-with-expressive-timing-on-a-classical-recording-for-solo-piano/). *Journal on the Art of Record Production*, March 2017.
- De Man, B., Boerum, M., Leonard, B., King, R., Massenburg, G. and Reiss, J. D. (2015). [Perceptual Evaluation of Music Mixing Practices](https://www.aes.org/e-lib/browse.cfm?elib=17659). 138th AES Convention, Warsaw, paper 9235.
- Faust libraries (GRAME). [misceffects.lib](https://faustlibraries.grame.fr/libs/misceffects/), `cubicnl` and `cubicnl_nodc` (by J. O. Smith III), and [filters.lib](https://faustlibraries.grame.fr/libs/filters/), `dcblocker`.
- Godfrey, C. et al. (2026). [Best overdrive pedals](https://www.guitarplayer.com/gear/best-overdrive-pedals), its key terms (edge of breakup, dynamic response). *Guitar Player*, updated 22 July 2026.
- Gracyk, T. (1996). [*Rhythm and Noise: An Aesthetics of Rock*](https://www.dukeupress.edu/rhythm-and-noise). Duke University Press (as read by Brown 1998).
- Herbst, J.-P. (2019). [Distortion and rock guitar harmony: the influence of distortion level and structural complexity on acoustic features and perceived pleasantness of guitar chords](https://pure.hud.ac.uk/en/publications/distortion-and-rock-guitar-harmony-the-influence-of-distortion-le/). *Music Perception* 36(4), 335–352.
- Houghton, M. (2010). [Hardware In The Software Studio](https://www.soundonsound.com/techniques/hardware-software-studio). *Sound On Sound*, May 2010.
- Houghton, M. (2013). [Gain Staging In Your DAW Software](https://www.soundonsound.com/techniques/gain-staging-your-daw-software). *Sound On Sound*, September 2013.
- Houghton, M. (2026). [Q. Should I gain-stage to -6dBFS or -18dBFS?](https://www.soundonsound.com/sound-advice/q-should-gain-stage-6dbfs-or-18dbfs) *Sound On Sound*, April 2026.
- Lilja, E. (2015). Dealing with the 3rd: anatomy of distorted chords and subsequent compositional features of classic heavy metal. In T.-M. Karjalainen and K. Kärki (eds.), *Modern Heavy Metal: Markets, Practices and Cultures*, pp. 393–403. [Archived PDF](https://web.archive.org/web/20250124071258/https://iipc.utu.fi/MHM/Lilja2.pdf).
- Ma, Z., De Man, B., Pestana, P. D. L., Black, D. A. A. and Reiss, J. D. (2015). Intelligent Multitrack Dynamic Range Compression. *Journal of the Audio Engineering Society* 63(6), 412–426. [doi:10.17743/jaes.2015.0053](https://doi.org/10.17743/jaes.2015.0053).
- Moorefield, V. (2005). [*The Producer as Composer: Shaping the Sounds of Popular Music*](https://mitpress.mit.edu/9780262514057/the-producer-as-composer/). MIT Press (its publisher's description).
- Mynett, M. (2018). [Q. Are EQ cuts more effective on electric guitar than EQ boosts?](https://www.soundonsound.com/sound-advice/q-are-eq-cuts-more-effective-electric-guitar-eq-boosts) *Sound On Sound*, June 2018.
- Robjohns, H. (2003). [Recording A Jazz Band On Location: Part 1](https://www.soundonsound.com/techniques/recording-jazz-band-location-part-1). *Sound On Sound*, July 2003.
- Rogers, N. (2022). [Drum Compression](https://www.soundonsound.com/techniques/drum-compression). *Sound On Sound*, August 2022.
- Senior, M. (2009). [Compression Made Easy](https://www.soundonsound.com/techniques/compression-made-easy). *Sound On Sound*, September 2009.
- Senior, M. (2015). [Richard King: How To Record Acoustic Ensembles](https://www.soundonsound.com/people/richard-king-how-record-acoustic-ensembles). *Sound On Sound*, September 2015.
- Senior, M. (2019). [Q. How do I make guitars sound more 'epic'?](https://www.soundonsound.com/sound-advice/q-how-do-make-guitars-sound-more-epic) *Sound On Sound*, May 2019.
- Smith, J. O. III. [DC Blocker](https://ccrma.stanford.edu/~jos/filters/DC_Blocker.html). *Introduction to Digital Filters with Audio Applications*, CCRMA, Stanford University.
- Sound On Sound. [DC-Offset](https://www.soundonsound.com/glossary/dc-offset), in its glossary.
- Steinberg. [VST 3 SDK: IAudioProcessor, getLatencySamples](https://steinbergmedia.github.io/vst3_doc/vstinterfaces/classSteinberg_1_1Vst_1_1IAudioProcessor.html).
- White, P. (1996). [Producing & Recording Electric Guitar Styles](https://www.soundonsound.com/techniques/producing-recording-electric-guitar-styles). *Sound On Sound*, November 1996.
- White, P. (1997). [Multi-effects Explained: Part 3 (Effects Order: Which Is Best?)](https://www.soundonsound.com/techniques/multi-effects-explained-part-3). *Sound On Sound*, September 1997.
- White, P. (2002). [Using Plug-ins (Routing and Ordering of Plug-ins for Recording and Mixing Tasks)](https://www.soundonsound.com/techniques/using-plug-ins). *Sound On Sound*, February 2002.
- White, P. (2002b). [Recording Electric Guitar: From Miked-up Valve Amps To Physical Modelling Preamps](https://www.soundonsound.com/techniques/recording-electric-guitar). *Sound On Sound*, December 2002.
