# Sound banks: the presets of the built banks

Read this when choosing a preset in one of the optional banks: each preset's program, range and recorded dynamics, the presets with dynamic layers and legato, and the percussion kits' keys. The banks, their licences and how to install them are in [soundbanks.md](soundbanks.md); what each one measured in probes, in [soundbank-measurements.md](soundbank-measurements.md).

Contents: [Presets in the built banks](#presets-in-the-built-banks) · [Dynamic layers and legato presets](#dynamic-layers-and-legato-presets) · [Percussion kits](#percussion-kits)

## Presets in the built banks

A track selects one with `soundfont` and `patch` ([schema.md](schema.md)); `studio.py instruments <words> --config <config.json>` finds a configured bank's presets by name, General MIDI family or bank and reads each one's keys and velocity ranges from the bank itself. Long and short articulations are separate presets: write short notes on a staccato or pizzicato track and long notes on the sustained one.

| Bank | Patch (bank:program) | Preset | Keys | Velocity layers |
|---|---|---|---|---|
| `vsco` | 0:48 | Strings Sustain | C2–G7 | 2 |
| `vsco` | 0:49 | Strings Slow | C2–G7 | 2 |
| `vsco` | 0:45 | Strings Spiccato | C2–E7 | 2 + round robins |
| `vsco` | 0:44 | Strings Tremolo | C2–D7 | 2 |
| `vsco` | 1:45 | Strings Pizzicato | C2–D7 | 2 + round robins |
| `vsco` | 0:61 | Brass Section | A1–E6 | 4 + round robins |
| `vsco` | 0:62 | Brass Stab | A1–E6 | 4 + round robins |
| `vsco` | 0:60 | French Horn | A1–G5 | 4 |
| `vsco` | 0:73 | Flute | B3–D7 | 3 |
| `vsco` | 1:73 | Flute Staccato | F4–D7 | 3 + round robins |
| `vsco` | 0:68 | Oboe | B♭3–A6 | 2 |
| `vsco` | 1:68 | Oboe Staccato | B♭3–A6 | 3 + round robins |
| `vsco` | 0:71 | Clarinet | D3–E6 | 3 |
| `vsco` | 1:71 | Clarinet Staccato | D3–F6 | 3 + round robins |
| `vsco` | 0:70 | Bassoon | B♭1–E♭5 | 2 |
| `vsco` | 1:70 | Bassoon Staccato | B♭1–D5 | 2 + round robins |
| `vsco` | 0:9 | Glockenspiel | G4–C8 | 1 |
| `vsco` | 0:40 | Solo Violin (vibrato) | G3–E7 | 2 |
| `vsco` | 1:40 | Solo Violin Spiccato | G3–C7 | 2 + round robins |
| `vsco` | 0:56 | Trumpet | F#3–C6 | 2 |
| `vsco` | 2:56 | Trumpet Vibrato | F#3–C6 | 2 |
| `vsco` | 1:56 | Trumpet Staccato | F#3–C6 | 3 + round robins |
| `vsco_extra` | 0:57 | Trombone | E2–B♭4 | 5 + round robins |
| `vsco_extra` | 1:57 | Trombone Short | E2–B♭4 | 3 + round robins |
| `vsco_extra` | 0:58 | Tuba | F1–C4 | 3 |
| `vsco_extra` | 1:58 | Tuba Staccato | E1–F4 | 2 + round robins |
| `vsco_extra` | 0:43 | Contrabass (vibrato) | E1–D4 | 2 |
| `vsco_extra` | 1:43 | Contrabass Straight | E1–D4 | 2 |
| `vsco_extra` | 2:43 | Contrabass Spiccato | E1–D4 | 2 + round robins |
| `vsco_extra` | 3:43 | Contrabass Pizz | E1–D4 | 2 + round robins |
| `vsco_extra` | 4:43 | Contrabass Tremolo | E1–D4 | 2 |
| `vsco_extra` | 0:72 | Piccolo | D5–C8 | 1 |
| `vsco_extra` | 1:72 | Piccolo Staccato | D5–C8 | 1 |
| `vsco_strings` | 0:40, 0:41, 0:42 | Violins, Violas, Cellos Sustain | G3–F♯6, C3–F♯6, C2–A5 | 2 |
| `vsco_strings` | 1:40, 1:41, 1:42 | Violins, Violas, Cellos Spiccato | as above | 2 + round robins |
| `vsco_strings` | 2:40, 2:41, 2:42 | Violins, Violas, Cellos Pizzicato | as above | 2 + round robins |
| `vsco_strings` | 0:44, 0:45, 0:46 | Violins, Violas, Cellos Tremolo | as above | 2 |
| `vcsl` | 0:0 | Grand Steinway B | A0–C8 | 3 |
| `vcsl` | 0:46 | Concert Harp | C1–G7 | 2 |
| `vcsl` | 0:12 | Marimba | C2–C7 | 3 |
| `vcsl` | 0:11 | Vibraphone | F3–F6 | 2 + round robins |
| `vcsl` | 0:13 | Xylophone | F4–C8 | 2 |
| `vcsl` | 0:14 | Tubular Bells | C4–F5 | 2 |
| `vcsl` | 0:47 | Timpani | D2–B3 | 3 + round robins |
| `vcsl` | 128:48 | Orchestra Kit (a drum part: keys below) | 27–86 | 1–5 per piece |
| `bass_darkblack` | 0:33 | Bass darkblack (ghost notes at velocities 1–24) | B0–E4 | 2 ghost + 4, round robins |
| `bass_darkblack` | 1:33 | Bass darkblack Staccato | B0–E4 | 1 + round robins |
| `piano_osiris` | 0:0 | Osiris Piano (dampers down) | A0–C8 | 2 |
| `piano_osiris` | 1:0 | Osiris Piano Pedal (recorded with the pedal held) | A0–C8 | 2 |
| `cello_bigcat` | 0:42 | Cello (looped sustain, delayed vibrato) | C2–C6 | 4 + bow directions |
| `cello_bigcat` | 1:42 | Cello Staccato | C2–C6 | 4 + round robins |
| `cello_bigcat` | 2:42 | Cello Pizzicato | C2–D5 | 1 + round robins |
| `organ_vcsl` | 0:19 | Pipe Organ (full registration) | C2–C7 | 1; velocity has no effect |
| `organ_vcsl` | 1:19 | Pipe Organ Soft (stopped flute) | G2–C7 | 1; velocity has no effect |
| `organ_vcsl` | 2:19 | Organ Pedal | C1–G3 | 1; velocity has no effect |
| `vsco_colors` | 0:60 | Horn Muted | G♯2–G5 | 2 |
| `vsco_colors` | 0:59, 1:59 | Trumpet Harmon Mute, Straight Mute | G♯3–B5 | 2 |
| `vsco_colors` | 0:57, 1:57, 2:57 | Trombone Vibrato, Fall, Growl | G♯2–G4, F2–C♯4, D♯2–E4 | 1 + round robins, 1, 2 |
| `vsco_colors` | 0:44, 2:40 | Solo Violin Tremolo, Pizzicato | F3–D7, F3–B6 | 2, 2 + round robins |
| `vsco_colors` | 0:73, 1:73, 0:68, 0:70 | Flute Vibrato, Flute Expressive Vibrato, Oboe Vibrato, Bassoon Vibrato | A♯3–D7, A♯3–D7, G♯3–G6, F2–D5 | 1, 1, 2, 2 |
| `vsco_colors` | 0:0 | Upright Piano | A♯0–A7 | 3 + round robins |
| `vsco_colors` | 128:9, 128:50 | Glockenspiel Glissandi, Orchestral FX (keys below) | 84–90; 35, 52–54 | 1 + round robins |
| `vcsl_keys` | 0:6, 1:6, 2:6, 3:6 | Harpsichord French, Flemish 8′, Flemish 8′+4′, English Lute (velocity sets no level) | C1–D6, E1–D6, E1–D7, G♯1–F♯6 | 1 + round robins |
| `vcsl_keys` | 0:1 | Grand Kawai | G♯0–D8 | 4 |
| `vcsl_keys` | 0:3, 1:3 | Upright Yamaha, Upright Knight | A♯0–D7, G0–D8 | 3 + round robins, 2 |
| `vcsl_keys` | 0:4, 1:4, 0:7 | FM Piano, FM Piano 1, Clavisynth (Yamaha TX81Z) | A♯0–D7, A♯0–D8, A♯1–D8 | 3 |
| `vcsl_winds` | 0:74, 2:74 | Soprano Recorder, Staccato | A♯4–D7 | 1 + round robins |
| `vcsl_winds` | 3:74, 4:74, 5:74 | Alto Recorder, Vibrato, Staccato | D♯4–F♯6 | 1 |
| `vcsl_winds` | 6:74, 7:74, 8:74 | Tenor Recorder, Vibrato, Staccato | A♯3–D6 | 1 |
| `vcsl_winds` | 9:74, 10:74, 11:74 | Bass Recorder, Vibrato, Staccato | D♯3–G5 | 1 |
| `vcsl_winds` | 0:79, 1:79 | Ocarina, Vibrato | G4–D♯6 | 1 |
| `vcsl_winds` | 0:22, 1:22, 2:22, 0:23 | Harmonica in C (soft and normal), Vibrato, Hand Vibrato; Chromatic Harmonica (normal and accented) | A♯3–D7, A♯3–D7, D♯4–G7, A♯2–D7 | 2, 1, 1, 2 |
| `vcsl_winds` | 0:66, 1:66, 2:66 | Tenor Sax, Vibrato, Staccato | F♯2–F♯6 | 2, 1, 2 + round robins |
| `vcsl_winds` | 0:64, 1:64, 2:64 | Saxello, Vibrato, Staccato | G♯3–F♯6 | 2, 1, 2 + round robins |
| `vcsl_winds` | 0:20, 1:20, 2:20 | Renaissance Organ Full, 8′, 4′ (velocity sets no level) | A♯1–F♯6 (4′ an octave up) | 1 |
| `vcsl_world` | 0:46, 0:25 | Folk Harp, Strumstick | A♯1–A♯6, C3–B5 | 2, 3 + round robins |
| `vcsl_world` | 0:107, 1:107, 2:107 | Dan Tranh, Vibrato, Tremolo | A2–C♯6 | 3, 2, 1 |
| `vcsl_world` | 0:15, 1:15 | Psaltery Plucked, Bowed | G♯4–G♯6 | 1 + round robins |
| `vcsl_world` | 0:108, 1:108, 2:108 | Kalimba (Tanzania), Kalimba (Kenya), Mbira Nyamaropa | F2–D♯7, A3–C♯6, G♯2–D♯6 | 1 + round robins |
| `vcsl_world` | 0:12, 1:12 | Balafon, Balafon Soft | B3–G6 | 3 |
| `vcsl_world` | 0:14, 0:92 | Hand Chimes, Glass Harp (wine glasses) | A♯3–D7, C♯5–E6 | 1 |
| `vcsl_world` | 128:25 | World Percussion (a drum part: keys below) | 35–84 | 1–4 per piece |
| `iowa_brass` | 0:60 | Horn | A♯1–F5 | 3 |
| `iowa_brass` | 0:57 | Bass Trombone | C1–B♭4 | 3 |
| `iowa_winds` | 0:70 | Bass Clarinet | C♯2–B♭5 | 3 |
| `iowa_winds` | 0:71 | E-flat Clarinet | G3–C7 | 3 |
| `iowa_winds` | 0:73 | Alto Flute | G3–G6 | 3 |
| `iowa_winds` | 0:74 | Bass Flute | C3–C♯6 | 3 |
| `iowa_strings` | 0:40, 0:41, 0:42, 0:43 | Violin, Viola, Cello, Double Bass (arco, looped) | G3–B7, C3–B♭6, C2–B♭5, E1–G4 | 3 |
| `iowa_strings` | 2:40, 2:41, 2:42, 2:43 | Violin, Viola, Cello, Double Bass Pizzicato | G3–A7, C3–B♭6, C2–B♭5, E1–G4 | 3 |
| `iowa_perc` | 0:9 | Orchestra Bells (plastic mallets) | C5–E8 | 3 |
| `iowa_perc` | 0:10 | Crotales | C6–C8 | 2 |
| `iowa_perc` | 0:11 | Thai Gongs | C4–C5 | 3 |
| `iowa_perc` | 128:48 | Orchestra Kit (a drum part: keys below) | 27–60 | 1–3 per piece |
| `iowa_guitar` | 0:24 | Nylon Guitar | E2–B5 | 3 |
| `bass_sneaky` | 0:32 | Upright Bass (finger 1–84, a stronger pluck 85–127) | B♭0–D4 | 2 + round robins |
| `bass_sneaky` | 1:32, 2:32 | Upright Bass Muted, Upright Bass Ghost | B♭0–D4, B0–D4 | 1 + round robins |
| `guitar_shiny` | 0:25, 0:26 | Archtop Guitar (microphone), Archtop Electric (pickup) | B1–D6 | 4 + round robins |
| `erhu` | 0:110, 1:110, 2:110 | Erhu (sustained, looped), Erhu Short, Erhu Sul Tasto (looped) | C4–B5, C4–B5, C4–E6 | 1 + round robins |
| `steel_drum` | 0:114 | Steel Drum | F♯3–F6 | 5 below C5, 4 above, + round robins |
| `tuba_war` | 0:58, 1:58 | War Tuba (sustained, looped), War Tuba Short | E♭1–A3 | 4 + round robins |
| `sax_bear` | 0:67, 1:67 | Bear Sax (baritone, sustained, looped), Bear Sax Short | B1–B♭4 | 2; 4 + round robins |
| `vocal_ah` | 0:52 | Vocal Ah (sustained, looped) | B♭1–C4 | 1 |

## Dynamic layers and legato presets

The sustained presets below also come in two more forms on the same program, for `performance.dynamics` and crossfade legato ([schema.md](schema.md), [orchestration.md](orchestration.md)):

- **Dynamic layers**, bank 16 + k: the k-th recorded dynamic alone, from the softest (k = 0), deaf to velocity. A layer with fewer recorded dynamics than its preset's richest maps onto the same scale, so one key range may repeat a dynamic.
- **Legato**, bank 32 + k: the same takes entered past their attack, at the first 10 ms frame within 2 dB of the take's steady level plus 20 ms (at most 0.6 s), faded in over 10 ms.

Only the preset at bank 0 of each program listed has them: another preset on the same program (Contrabass Straight at 1:43, a spiccato, a pizzicato) plays its velocity layers alone. `review --config` names a part that asks for dynamics or crossfade legato on such a preset, with the programs that have them, and a render stops on it before anything is synthesized.

| Bank | Programs with dynamic layers (count) | Legato |
|---|---|---|
| `vsco` | Strings Sustain 48 (2), French Horn 60 (4), Flute 73 (3), Oboe 68 (2), Clarinet 71 (3), Bassoon 70 (2), Solo Violin 40 (2), Trumpet 56 (2), Strings Tremolo 44 (2), Brass Section 61 (4) | all but Tremolo and Brass Section |
| `vsco_extra` | Trombone 57 (5), Tuba 58 (3), Contrabass 43 (2), Piccolo 72 (1) | all |
| `vsco_strings` | Violins 40, Violas 41, Cellos 42 (2 each); their tremolos 44, 45, 46 (2 each) | the sustains |
| `cello_bigcat` | Cello 42 (4) | yes |
| `vsco_colors` | Horn Muted 60, Trumpet Harmon Mute 59, Solo Violin Tremolo 44, Oboe Vibrato 68, Bassoon Vibrato 70 (2 each) | all |
| `vcsl_winds` | Harmonica 22, Chromatic Harmonica 23, Tenor Sax 66, Saxello 64 (2 each) | all |
| `iowa_brass` | Horn 60, Bass Trombone 57 (3 each) | all |
| `iowa_winds` | Bass Clarinet 70, E-flat Clarinet 71, Alto Flute 73, Bass Flute 74 (3 each) | all |
| `iowa_strings` | Violin 40, Viola 41, Cello 42, Double Bass 43 (3 each) | all |
| `tuba_war` | War Tuba 58 (4) | yes |
| `sax_bear` | Bear Sax 67 (2) | yes |

Median legato entry: section strings 535 ms (their bowed swell), the Iowa solo strings about 480 ms (violin, viola, cello; double bass 380 ms), the Iowa woodwinds 130–250 ms, the Iowa horn 90 ms and bass trombone 140 ms, double bass 230 ms, cello 240 ms, clarinet 200 ms, solo violin 155 ms, horn and trombone 140 ms, tuba 120 ms, flute 115 ms, bassoon 110 ms, oboe 100 ms, piccolo 90 ms, trumpet 75 ms. A few takes whose level keeps moving reach the 0.6 s cap.

## Percussion kits

The orchestra kit's keys: 35 and 36 concert bass drum; 38 snare, 40 snare roll; 49 clash cymbals, 57 clash cymbals choked; 55 suspended cymbal with soft mallets, 51 with a stick, 53 its bell, 59 a suspended cymbal roll; 27, 28, 29 and 30 suspended cymbal swells (their timing in [soundbank-measurements.md](soundbank-measurements.md), VCSL orchestra kit); 52 gong; 54 tambourine; 81 triangle, 80 muted; 83 sleigh bells; 84, 85 and 86 mark tree glissandi (fast up, up, down). On a drum track, set `"patch": {"bank": 128, "program": 48}` and `"soundfont": "vcsl"`.

The world percussion kit (`vcsl_world`, `"patch": {"bank": 128, "program": 25}`): 35 frame drum, large, and 36 muted; 37 frame drum, small, and 38 muted; 39 hand claps; 41, 42 and 43 cajon bass, slap and tone; 44–48 darbuka strokes 1–5; 56 cowbell, 57 muted; 60 and 61 bongos high and low; 62 quinto muted, 63 quinto open, 64 conga open, 65 tumba open, 66 tumba muted; 67 and 68 agogo high and low; 69 cabasa; 70 large shaker, 71 small shaker, 72 shaker roll; 73 guiro short, 74 long; 75 claves; 76 and 77 slit drum high and low; 78 brake drum; 79 anvil; 80 finger cymbals; 81 bell tree; 82 ratchet; 84 ocean drum. Velocity picks between two to four recorded strengths where they exist. In `vsco_colors`, 128:9 holds glockenspiel glissandi (84 down chromatic fast, 85 down chromatic slow, 86 down pentatonic, 87 up chromatic fast, 88 up chromatic medium, 89 up chromatic slow, 90 up pentatonic) and 128:50 orchestral effects (35 rubbed bass drum, 52 scraped gong, 53 bowed cymbal, 54 scraped cymbal): start a glissando that long before the note it should land on.

The Iowa kit (`iowa_perc`, the same patch) has orchestral colours the VCSL kit lacks: 49 clash cymbals, an 18-inch Viennese pair, and 57 an 18-inch German pair (pp, mf and ff by velocity); 55 a suspended 18-inch crash and 51 a 20-inch one, soft mallet (pp, mf, ff); 59 and 60 their mallet rolls; 56 the 18-inch crash choked; 52 a 40-inch tam-tam, 50 a 28-inch and 48 a 22-inch one, 47 a 20-inch wind gong (pp, mf, ff each); 27 the 40-inch tam-tam bowed, 28 the 28-inch bowed, 29 the 18-inch crash bowed and 30 a 20-inch Chinese cymbal bowed. Every piece rings out whatever the note length, so leave `tail_seconds` of 12–15 after a tam-tam.
