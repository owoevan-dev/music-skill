# Organ music: the pipe organ bank

Read this when a part is for pipe organ: a chorale or hymn, a prelude, a solemn scene, organ with orchestra. It covers what the bank's organ can do, how organ parts are written for hands and feet, how an organ phrases without dynamics, and the church it is heard in. For baroque counterpoint, continuo and forms, see [baroque.md](baroque.md).

**Numbers here.** A number given with no source beside it is one of two things: a fact of the skill's own banks and tools, measured here or read from their files, or a setting that is this skill's starting value, to be judged by ear and with `analyze`. The sources named give the sound and the practice; a starting value is no norm of the style.

## The instrument in the bank

`organ_vcsl` ([soundbank-presets.md](soundbank-presets.md)) holds three registrations of one pipe organ, each a preset of its own:

| Preset (bank:program) | What it is | Sounding range |
|---|---|---|
| Pipe Organ (0:19) | The full manual registration: an 8′ foundation with 4′ and higher ranks, and a quieter 16′ sub-octave from about middle C up | C2–C7 |
| Pipe Organ Soft (1:19) | A soft stopped flute at 8′ pitch | G2–C7 |
| Organ Pedal (2:19) | The pedal division, its fundamental at 16′ pitch | C1–G3 |

**Footage.** It names the pitch of a stop by the approximate length of its longest open pipe: an 8′ stop sounds at the pitch of the keys, a 4′ an octave higher, a 16′ an octave lower (Wikipedia, Organ stop). A full registration stacks such ranks into a bright, dense chorus, and a soft flute stop is close to a pure tone.

**Fixed registrations.** The bank has no single stops to draw, no reeds and no couplers, only these three. A registration change is a move to another track: change at a phrase or section boundary, or layer the soft stop under the full one to thicken a passage.

**Keys are on or off.** As on a real organ, velocity changes nothing. CC11 lowers or raises a part's level like a swell box, but without the swell box's change of brightness.

**Held notes.** Each note holds as long as the key (the recordings are looped). On release the pipe stops within 0.35 s, and the long decay belongs to the room. The full registration beats slowly between its ranks, at middle C about once every 1.2 s, as in the recording.

## Hands and feet

- **Manuals.** Each hand holds up to about five notes within the span of a hand. Write the manual parts as voices: a melody, inner voices, and a tenor that the left hand can reach.
- **Pedal.** The feet play the bass line, at most two notes at once. Write it at the pitch it sounds (C1–G3): with its 16′ fundamental it sounds an octave below the manuals' bass. It can also sustain a pedal point under changing harmony.
- **Range.** Keep the full registration's bass above C2. Below that the pedal takes over.

## Phrasing without dynamics

Like the harpsichord, the organ offers almost no dynamic or timbral nuance from the keys, apart from registration changes. What players shape instead is mostly timing: articulation, onset asynchrony and tempo (Gingras, Asselin and McAdams 2013). Sixteen professional organists playing Bach's "Dorian" fugue on an organ with a MIDI console made their largest tempo changes at the boundaries they named as the work's main sections (Gingras, McAdams and Schubert 2010). In practice:

- **Articulation.** Separate repeated notes, or a held key cannot sound again and they merge into one (`gate` 0.7–0.85, this skill's starting values). Mark stresses by articulation rather than velocity, which changes nothing; `gate` 1.0 with slight overlaps joins a legato line.
- **Timing at boundaries.** Slow into the main section boundaries with the tempo map, as the organists Gingras, McAdams and Schubert (2010) measured did.
- **Registration as dynamics.** Soft stop, then full manual, then full manual with the pedal: that is the organ's crescendo. Changes of texture (more voices, the pedal entering) add to it.

## The church

Organs speak into large, reverberant rooms. Mapp (2019) measured mid-frequency reverberation times of 1.2–3.5 s in ten English churches, and 5.1 s in a cathedral of about 23,000 m³. In seven Spanish cathedrals it ran from 4.3 to 9 s, and listeners could not tell apart rooms between 4 and 7 s (Girón, Galindo and Gómez-Gómez 2020).

The mix's `church` space decays in about 4.2 s at 1 kHz, longer in the bass and shorter in the treble. That is a large church, between those churches and the cathedrals.

- Send every organ track to it: `mix.space: "church"`, with a strong send (`reverb_db` around −6 to −3, this skill's starting values).
- In a room that decays over about 4 s, a chord still sounds when a fast change brings the next one: let the harmony change slowly enough for the room.
- Leave a rest after a final chord, and set `tail_seconds` to at least 6 for the reverb to die away.
- For organ with orchestra, send the orchestra to the same church, or keep the organ in the hall with the orchestra.
- Organ chords sustain at a constant level, so the loudness hardly varies. Use `mix.dynamics: "wide"` ([orchestration.md](orchestration.md)) so nothing compresses the registration changes.

## Sources

- Gingras, B., Asselin, P.-Y. and McAdams, S. (2013). [Individuality in harpsichord performance: disentangling performer- and piece-specific influences on interpretive choices](https://pmc.ncbi.nlm.nih.gov/articles/PMC3842509/). *Frontiers in Psychology* 4:895. doi:10.3389/fpsyg.2013.00895
- Gingras, B., McAdams, S. and Schubert, P. (2010). [The Performer as Analyst: A Case Study of J. S. Bach's "Dorian" Fugue BWV 538](https://gmth.de/proceedings/artikel/78.aspx). In *Musiktheorie als interdisziplinäres Fach* (GMTH Proceedings 2008), 305–318. doi:10.31751/p.78
- Mapp, P. (2019). [An acoustic and audio survey of some English churches](https://www.ioa.org.uk/system/files/proceedings/p_mapp_an_acoustic_and_audio_survey_of_some_english_churches.pdf). *Proceedings of the Institute of Acoustics* 41(3), Reproduced Sound 2019. doi:10.25144/15316
- Girón, S., Galindo, M. and Gómez-Gómez, T. (2020). Assessment of the subjective perception of reverberation in Spanish cathedrals. *Building and Environment* 171, 106656. doi:10.1016/j.buildenv.2020.106656
- [Organ stop](https://en.wikipedia.org/wiki/Organ_stop). Wikipedia, read 7 November 2026: footage and pitch.
- Girón, S., Álvarez-Morales, L. and Zamarreño, T. (2017). Church acoustics: A state-of-the-art review after several decades of research. *Journal of Sound and Vibration* 411, 378–408. doi:10.1016/j.jsv.2017.09.015
