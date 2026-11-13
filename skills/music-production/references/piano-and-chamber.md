# Piano and chamber music

Read this when the request is solo piano (a ballad, a nocturne-like piece, an emotional film or game piano cue), piano with one instrument (violin, cello, flute), a piano trio or a string quartet. Small ensembles leave every part exposed: the writing has to sit well under the hands and bows, and the performance carries most of the expression, through timing, dynamics and the pedal. For orchestra see [orchestration.md](orchestration.md); for jazz piano, [jazz-and-funk.md](jazz-and-funk.md).

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

The periods and styles this writing belongs to, each on the seven axes with its sources: [style-map-orchestral.md](style-map-orchestral.md); a mood's cues across styles in [moods.md](moods.md).

## Brief

- **Instruments.** Piano: two, the Steinway first ([soundbank-presets.md](soundbank-presets.md)). A piece for solo piano is played on the Steinway unless it asks for what the Osiris has, whatever its tempo and loudness, a fast or brilliant one too: where it wants a brighter piano, brighten the Steinway in the mix (a few dB at 2 to 5 kHz) and keep the piano.
  - **The `vcsl` Steinway grand (0:0)**, the piano for solo playing: quiet or loud, slow or fast, and wherever a clear, even tone is wanted. Fast, dense writing stays clear on it. Its soft and middle dynamics are made from its loud one, key by key, so a soft passage carries next to no hiss, and the hammer's blow sounds less in its tone than in a piano recorded close. It has no recording with the pedal held: CC64 lengthens its notes without the other strings' resonance.
  - **`piano_osiris` (0:0, recorded with the dampers down)**, the second choice, for slow and sparse music that wants a close, touched sound. Dense or fast writing turns thick on it, and no equalization made it as clear as the Steinway (tried on a showpiece of 2,500 notes with up to 8 dB added from 2.5 to 13 kHz). Every white key at two recorded dynamics, the hammer's blow plain in each note, and soft playing dark (11 to 17 dB less than the Steinway between 1 and 4 kHz in a soft passage). Its pedal preset (1:0), recorded with the pedal held, lets the whole instrument ring, and each note brings the pedal's and the dampers' own sounds with it, once a note where a pianist's pedal sounds once a harmony: for sparse music that wants that haze, by choice and not for pedalled playing in general.

  The other pianos stay in the banks for one colour each, with what it costs, and are not for general use:
  - **Uprights**, where the piece asks for an upright's sound (lo-fi, a bar room, something older): the Yamaha (`vcsl_keys` 0:3), recorded on thirteen keys (each C and G), its soft treble takes one to four seconds long, and fifteen of its takes with a breath or a knock late in the ring, heard under long exposed notes; the Knight (1:3), 45 keys at two dynamics; the VSCO upright (`vsco_colors` 0:0), fourteen keys.
  - **The Kawai grand** (`vcsl_keys` 0:1), four recorded dynamics and the brightest of the grands, for a piano part inside a full mix that wants that brightness. Not for solo piano: its softest layer carries rumble, and hiss for as long as a note's partials sound, which a pedal adds up ([noise.md](noise.md)).

  A hammer's blow and a pedal's resonance are the instrument, and they are chosen with the piano; hiss is the recording, and the builds take it out where they can. Strings: the Iowa solo violin, viola, cello and double bass (`iowa_strings`, three dynamics, looped), `cello_bigcat` (looped, four dynamics), the `vsco` solo violin. A flute, clarinet or oboe from `vsco` or `iowa_winds`.
- **Character and tempo.** Decide the character first, then the cues that convey it: slow tempos, soft dynamics and legato convey sad and peaceful characters (Eerola, Friberg and Bresin 2013, in [game-music.md](game-music.md)). Leave room for rubato (Timing and dynamics, below).
- **Room.** A small hall or room, a wide master: `mix.chain: "bus"`, `dynamics: "wide"`, `space` `hall` or `room`, `depth_m` to seat the players ([orchestration.md](orchestration.md)).

## Writing for the piano

- **Hands.** Hand spans vary by up to five inches between adult pianists. A tenth needs a span of about 8.5 inches, which about a quarter of men and most women lack, and fast octaves and large chords can strain smaller hands (PASK, after Boyle, Boyle and Booker 2015). So break a tenth (root, fifth, tenth) into an arpeggio rather than striking it, and keep struck chords within the reach of most hands. Write the two hands as separate parts, or as one part whose chords respect both spans.
- **Register.** Close intervals in a low register sound muddy (Open Music Theory, Jazz Voicings; the low interval limits in [development-and-groove.md](development-and-groove.md)): in the bass use open fifths, octaves and tenths, and put the thirds higher.
- **Voicing.** The melody on top and louder than the accompaniment (8–15 velocity steps, this skill's starting values); inner voices quieter still. `musiclib.expression` sounds the top note of a chord slightly early, as pianists' melody notes do, mostly because they are struck harder (Goebl 2001).
- **Textures.** Broken-chord accompaniments, repeated chords, a melody in octaves, a bass line in the left hand under chords in the right. Strong contrasts of texture mark section boundaries (McAdams, Goodchild and Soden 2022), so change the texture between sections.
- **Pedal.** CC64 holds the notes of any piano preset for as long as the pedal is down. Held down, the pedal works until the harmony changes or new notes clash with the sustaining ones; then a quick lift and press clears it (Yamaha, How to Use Keyboard Pedals). Write it with CC64 in `performance.cc` (`[beat, 64, 0]`, then `[beat + 0.05, 64, 127]`). Without CC64 a preset plays dry and detached. The Osiris's pedal preset adds the strings' sympathetic resonance, and the pedal's own sounds, to every note (Instruments, above).
- **How near it is heard.** A solo piano mixed with `mix.rules: 2` sets `mix.c80_db` ([orchestration.md](orchestration.md#how-near-the-orchestra-is-heard)): about +2 to +3 dB for a recital room heard from a good seat, 0 to +1 for a slow piece that wants a hall around it, +4 to +6 for fast or contrapuntal writing whose lines must stay apart, +8 and more for a close, dry piano in a song or a beat. Left at the sends alone, a piano part measures about +16 to +18 dB, which is heard as dry. Experts preferred reverberation times of 1.2 to 2.0 s for solo piano where they preferred 1.8 to 2.4 s for solo violin (Hidaka, Omoto and Nishihara 2024); in a diffuse field those times give a clarity of about −1 to +2 dB, and a recording stands nearer the instrument than a seat does. The starting values here are this skill's own, drawn from that range.

## Timing and dynamics

Performers shape time by the music's grouping. Repp (1992) measured 28 recordings of Schumann's *Träumerei* and found two constraints behind their great variety:
- the phrase structure prescribes where the large tempo changes fall: pronounced ritardandi at the ends of major sections, and lengthening of accented notes within gestures;
- within a melodic gesture the slowing follows a smooth, parabolic curve.

Inside those constraints each pianist's timing was individual. Here:
- the shared tempo map carries the large changes: `clock.rubato` slows each section's last beats and the close (after Friberg and Sundberg 1999, [schema.md](schema.md)); add a broader ritardando by tempo points where a major section ends or a climax broadens;
- `musiclib.expression` adds the small, player-like timing of each part; keep the parts together where they play together;
- phrase dynamics as arches with `musiclib.phrasing` (`sing`, `ramp`, `dynamics`).

Todd (1992) modelled phrases in which tempo and loudness rise and fall together, faster as louder and slower as softer, a coupling he suggests may characterise some classical and romantic styles. It is a useful default for an arching phrase, not a law: tested against real performances it explains only part of them (Windsor and Clarke 1997), and a held-back climax, loud and broad, reverses it.

## Chamber ensembles

- **Ranges.** Write within each bank's recorded range ([soundbank-presets.md](soundbank-presets.md), [orchestration.md](orchestration.md)); `review --config` lists notes played far from their samples.
- **Roles.** Layers of different prominence form a foreground and a background (McAdams, Goodchild and Soden 2022): give the lead one part at a time and the others sustained lines, counter-lines or accompaniment figures. A melody handed from one instrument to another is a timbral shift in their taxonomy; a phrase answered by another instrument or group is an antiphonal contrast, and one repeated in another colour a timbral echo.
- **Keep lines apart.** A melody stands out when its register or timbre differs from what accompanies it (McAdams, Goodchild and Soden 2022; [climax-and-melody.md](climax-and-melody.md)): keep the piano's right hand out of the cello's register while the cello sings, or move the cello above it.
- **Strings as players.** Single lines on sustained samples need connection: crossfade legato with `portamento_ms` on expressive leaps, `bow_change_s` on long notes, a dynamics curve per phrase (`dynamics_mode: "take"` for exposed solos) and `facing` and `depth_m` for placement ([orchestration.md](orchestration.md), [schema.md](schema.md)).
- **Balance.** If the piano masks a string line, find it by muting parts one at a time (Senior 2018, in [anime-opening.md](anime-opening.md)); thin the piano in that register or let the string line rise. Read `lead_minus_accompaniment` in `analyze`.

## Symptoms and causes

Sources for the table: Repp (1992) and Friberg and Sundberg (1999) for timing, Goebl (2001) for voicing, Yamaha for the pedal, Open Music Theory for low voicings.

| Symptom | Likely causes | What to check or change |
|---|---|---|
| Mechanical | strict tempo, constant velocities, chords struck together | `clock.rubato` and tempo points at section ends, `musiclib.expression`, phrase arches |
| Blurred | pedal held across harmony changes, low close voicings | CC64 lifts at each change, open voicings in the bass |
| Dry and disconnected | no pedal, short notes in a lyrical piece, or a mix left very near | CC64 through each harmony, longer note values, a lower `mix.c80_db` (How near it is heard) |
| The melody gets lost | accompaniment as loud as the tune, in its register | velocity steps, register separation |
| Rubato sounds random | timing that ignores the phrases | large changes only at phrase and section ends, smooth ritardandi |

## Sources

- Hidaka, T., Omoto, A. and Nishihara, N. (2024). Listener's quality in subjective evaluation of concert hall acoustics: comparison between musical experts' and students' judgment of reverberance for solo music. *Acoustical Science and Technology*, advance publication, [doi:10.1250/ast.e24.91](https://doi.org/10.1250/ast.e24.91) (the abstract read: preferred mid-frequency reverberation times for solo piano and solo violin).

- Boyle, R., Boyle, R. and Booker, E. (2015). Pianist hand spans: gender and ethnic differences and implications for piano playing. *Proceedings of the 12th Australasian Piano Pedagogy Conference*, 8–29. Summarised by [PASK, Pianists' hand spans vary greatly](https://paskpiano.org/pianists-hand-spans-vary-greatly/), read 7 November 2026.
- Yamaha. [How to Use Keyboard Pedals](https://hub.yamaha.com/keyboards/k-how-to/how-to-use-keyboard-pedals/). Yamaha Hub.
- Repp, B. H. (1992). Diversity and commonality in music performance: an analysis of timing microstructure in Schumann's "Träumerei". *Journal of the Acoustical Society of America* 92(5), 2546–2568.
- Todd, N. P. McA. (1992). The dynamics of dynamics: a model of musical expression. *Journal of the Acoustical Society of America* 91(6), 3540–3550.
- Windsor, W. L. and Clarke, E. F. (1997). Expressive timing and dynamics in real and artificial musical performances: using an algorithm as an analytical tool. *Music Perception* 15(2), 127–152.
- Eerola, T., Friberg, A. and Bresin, R. (2013). [Emotional expression in music: contribution, linearity, and additivity of primary musical cues](https://pmc.ncbi.nlm.nih.gov/articles/PMC3726864/). *Frontiers in Psychology* 4:487.
- Friberg, A. and Sundberg, J. (1999). Does music performance allude to locomotion? A model of final ritardandi derived from measurements of stopping runners. *Journal of the Acoustical Society of America* 105(3), 1469–1484.
- Goebl, W. (2001). Melody lead in piano performance: expressive device or artifact? *Journal of the Acoustical Society of America* 110(1), 563–572.
- Lavengood, M. [Jazz Voicings](https://pressbooks.nebraska.edu/openmusictheory/chapter/jazz-voicings/). In Gotham, M. et al., *Open Music Theory*: spacing after the harmonic series, close low intervals muddy.
- McAdams, S., Goodchild, M. and Soden, K. (2022). [A Taxonomy of Orchestral Grouping Effects Derived from Principles of Auditory Perception](https://doi.org/10.30535/mto.28.3.6). *Music Theory Online* 28(3).
