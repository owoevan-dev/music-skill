# Piano and chamber music

Read this when the request is solo piano (a ballad, a nocturne-like piece, an emotional film or game piano cue), piano with one instrument (violin, cello, flute), a piano trio or a string quartet. Small ensembles leave every part exposed: the writing has to sit well under the hands and bows, and the performance carries most of the expression, through timing, dynamics and the pedal. For orchestra see [orchestration.md](orchestration.md); for jazz piano, [jazz-and-funk.md](jazz-and-funk.md).

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

The periods and styles this writing belongs to, each on the seven axes with its sources: [style-map-orchestral.md](style-map-orchestral.md); a mood's cues across styles in [moods.md](moods.md).

## Brief

- **Instruments.** Piano: `piano_osiris` (a grand recorded with and without the pedal, [soundbank-presets.md](soundbank-presets.md)), the `vcsl_keys` Kawai grand (four dynamics), the `vcsl` Steinway (three, no pedal recording), an upright (`vcsl_keys` 0:3) for an intimate, older sound. For quiet, exposed solo piano use `piano_osiris`, or that upright: their soft takes carry the least noise under a ringing note, where the Steinway's and the Kawai's soft layers carry rumble and hiss that a pedal adds up, covered in a fuller mix ([noise.md](noise.md)). Strings: the Iowa solo violin, viola, cello and double bass (`iowa_strings`, three dynamics, looped), `cello_bigcat` (looped, four dynamics), the `vsco` solo violin. A flute, clarinet or oboe from `vsco` or `iowa_winds`.
- **Character and tempo.** Decide the character first, then the cues that convey it: slow tempos, soft dynamics and legato convey sad and peaceful characters (Eerola, Friberg and Bresin 2013, in [game-music.md](game-music.md)). Leave room for rubato (Timing and dynamics, below).
- **Room.** A small hall or room, a wide master: `mix.chain: "bus"`, `dynamics: "wide"`, `space` `hall` or `room`, `depth_m` to seat the players ([orchestration.md](orchestration.md)).

## Writing for the piano

- **Hands.** Hand spans vary by up to five inches between adult pianists. A tenth needs a span of about 8.5 inches, which about a quarter of men and most women lack, and fast octaves and large chords can strain smaller hands (PASK, after Boyle, Boyle and Booker 2015). So break a tenth (root, fifth, tenth) into an arpeggio rather than striking it, and keep struck chords within the reach of most hands. Write the two hands as separate parts, or as one part whose chords respect both spans.
- **Register.** Close intervals in a low register sound muddy (Open Music Theory, Jazz Voicings; the low interval limits in [development-and-groove.md](development-and-groove.md)): in the bass use open fifths, octaves and tenths, and put the thirds higher.
- **Voicing.** The melody on top and louder than the accompaniment (8–15 velocity steps, this skill's starting values); inner voices quieter still. `musiclib.expression` sounds the top note of a chord slightly early, as pianists' melody notes do, mostly because they are struck harder (Goebl 2001).
- **Textures.** Broken-chord accompaniments, repeated chords, a melody in octaves, a bass line in the left hand under chords in the right. Strong contrasts of texture mark section boundaries (McAdams, Goodchild and Soden 2022), so change the texture between sections.
- **Pedal.** On the pedal preset of `piano_osiris` the notes ring as long as the pedal holds. Held down, the pedal works until the harmony changes or new notes clash with the sustaining ones; then a quick lift and press clears it (Yamaha, How to Use Keyboard Pedals). Write it with CC64 in `performance.cc` (`[beat, 64, 0]`, then `[beat + 0.05, 64, 127]`). Use the pedal-up preset, or no CC64, for dry, detached playing.

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
- **Roles.** Layers of different prominence form a foreground and a background (McAdams, Goodchild and Soden 2022): give the lead one part at a time and the others sustained lines, counter-lines or accompaniment figures. A melody handed from one instrument to another is a timbral shift in their taxonomy; a phrase answered in another voice is imitation.
- **Keep lines apart.** A melody stands out when its register or timbre differs from what accompanies it (McAdams, Goodchild and Soden 2022; [climax-and-melody.md](climax-and-melody.md)): keep the piano's right hand out of the cello's register while the cello sings, or move the cello above it.
- **Strings as players.** Single lines on sustained samples need connection: crossfade legato with `portamento_ms` on expressive leaps, `bow_change_s` on long notes, a dynamics curve per phrase (`dynamics_mode: "take"` for exposed solos) and `facing` and `depth_m` for placement ([orchestration.md](orchestration.md), [schema.md](schema.md)).
- **Balance.** If the piano masks a string line, find it by muting parts one at a time (Senior 2018, in [anime-opening.md](anime-opening.md)); thin the piano in that register or let the string line rise. Read `lead_minus_accompaniment` in `analyze`.

## Symptoms and causes

Sources for the table: Repp (1992) and Friberg and Sundberg (1999) for timing, Goebl (2001) for voicing, Yamaha for the pedal, Open Music Theory for low voicings.

| Symptom | Likely causes | What to check or change |
|---|---|---|
| Mechanical | strict tempo, constant velocities, chords struck together | `clock.rubato` and tempo points at section ends, `musiclib.expression`, phrase arches |
| Blurred | pedal held across harmony changes, low close voicings | CC64 lifts at each change, open voicings in the bass |
| Dry and disconnected | pedal-up preset with short notes in a lyrical piece | the pedal preset with CC64, longer note values |
| The melody gets lost | accompaniment as loud as the tune, in its register | velocity steps, register separation |
| Rubato sounds random | timing that ignores the phrases | large changes only at phrase and section ends, smooth ritardandi |

## Sources

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
