# Noise: where it comes from and how to treat it

Most of what sounds like noise in a render belongs to an instrument, and the recording noise in the banks built here is
low (measured below). Find the part and the moment first, decide what the noise is, then treat it in the order given
here, which runs from no processing at all to processing that can harm the sound. A person's ear decides whether a
treatment helped; a measurement only says where to listen.

Contents: [Where noise comes from](#where-noise-comes-from) · [When it is heard: masking](#when-it-is-heard-masking) · [Finding it](#finding-it) · [Treatments, safest first](#treatments-safest-first) · [The banks, measured](#the-banks-measured) · [Listening tests](#listening-tests) · [Sources](#sources)

## Where noise comes from

- **The instrument.** Bow and rosin, breath and reed, keys and pedals, hammers, fingers on strings, a guitar
  amplifier's hiss. It starts and stops with the notes and follows their dynamics. A player makes it too, and taking it
  away changes the instrument.
- **The recording.** Microphone and preamplifier hiss, room rumble, mains hum. It stays level while a note fades, so it
  shows in decays, after notes and in pauses.
- **Gain.** Every decibel a part is raised raises its noise with it: a soft recorded dynamic brought up to its layer's
  level by the bank (`match_limit_db`, layer offsets), a part set high with `level_dbfs`, a quiet cue normalised to a
  loud `target_lufs`, and `range_lu`, which lifts quiet passages together with their floor.
- **Voices adding up.** Every sounding note carries its own floor, and floors that are not correlated add in power:
  N notes lie 10·log10 N dB over one (Kinsler et al. 2000). A soft pad of twelve notes across three string sections
  carries about 11 dB more floor than one of its notes, enough to bring it within hearing where one note's would not be.
- **Sends.** Reverb and delay carry a part's noise into their tails.
- **Noise by design.** Vinyl crackle, noise oscillators, risers and tape wobble belong to their styles.
- **The playback level.** Turned up, hearing gains sensitivity to low frequencies faster than to the middle (the
  equal-loudness contours of ISO 226:2023), so rumble that is inaudible at a normal level appears when the music is
  loud. Hearing is most sensitive to hiss between about 1 and 6 kHz, which A-weighting (IEC 61672-1:2013) and, more
  steeply, ITU-R BS.468-4 (+12.2 dB at 6.3 kHz) weight up.

## When it is heard: masking

A note masks noise near it in frequency and, more widely, above it, but little below it: the upward spread of masking
(Wegel and Lane 1924; Zwicker and Fastl 2007, chapter 4). So rumble under a bass note and hiss above a dark pad are heard
while the notes play, and any noise is heard where the notes stop: in decays, rests, the end of a cue and fades. Listen
first to long decays (a pedalled piano, mallets, harp, plucked strings), soft exposed solos and parts raised well above
their recorded level.

## Finding it

1. Ask when it is heard and at what playback level.
2. Solo each stem (`stems/<part>.wav`) at the same gain over that passage. The noise belongs to the stem where it stays.
   A guess from an instrument's name is not a finding.
3. Decide what it is. Noise that starts and stops with the notes and follows their dynamics is the instrument's; noise
   that stays level while a note fades, or remains after it, is the recording's; noise that grows after the notes is a
   reverb or delay tail.
4. Measure with long frames. Under a low note, use frames of at least 0.3 s (16384 samples at 48 kHz): a short frame
   spreads the note's own fundamental into the band below it, where it reads as rumble. Estimators that follow the
   minimum of each band over time read the floor under speech or music (Martin 2001), and a percentile of each band over
   a stem does the same, but neither can tell an instrument's steady noise from a recording's, and both read sustained
   harmony (a pedalled piano, a string pad) as floor. They rank parts for listening; they do not prove noise.

## Treatments, safest first

### 1. Arrangement and gain

- Write the dynamic you want to hear. A soft recorded dynamic pushed up with `level_dbfs` brings its floor with it; a
  louder one set lower does not, though it also sounds brighter.
- Thin a soft pad: fewer notes or sections on a quiet chord (N notes, 10·log10 N dB of floor).
- Give a quiet cue a quieter master: a `target_lufs` under −14 (Spotify's playback level) keeps its floor lower, and
  for a game Sony's audio standards group recommended an average of −23 LUFS for the whole output
  ([game-music.md](game-music.md)). `range_lu` lifts quiet passages with their floor.

### 2. A high-pass under the part's lowest note

Rumble, handling noise and air conditioning lie below most instruments' range. A high-pass on every part with nothing
of its own down there is ordinary mixing practice; a low-pass to hide hiss is not, because most instruments' partials and
their own noise run up the whole spectrum (Senior, Sound On Sound Q&A).

- `mix.highpass` is FFmpeg's two-pole Butterworth, 12 dB per octave: at r times the cutoff it passes r⁴/(1 + r⁴) of the
  power. An octave under a part's lowest note keeps that note's fundamental within 0.3 dB; a major third above the
  cutoff it loses 1.5 dB, at the cutoff 3 dB. `review` names a part whose high-pass takes more than 1.5 dB from the
  fundamental of its lowest note (the limit is this project's own choice: style-maps.json).
- So, an octave under the lowest note: a bass reaching E1 (41 Hz) takes 20 Hz, cellos down to C2 (65 Hz) 33 Hz, violas
  to C3 (131 Hz) 65 Hz, violins to G3 (196 Hz) 98 Hz. Under B0 it stops at 15 Hz, the lowest a part's `highpass` may
  be, which still keeps a piano's A0 (27.5 Hz) within 0.4 dB. A piano's left hand reaching D1 (37 Hz) loses 5 dB of that
  note's fundamental to a 45 Hz high-pass.

### 3. EQ on an instrument's own noise

When bow scratch, breath or key noise reads as too much, a gentle bell cut where it sits (measured here, the section
strings' bow noise is strongest at 1–5 kHz), judged against the whole mix rather than solo, softens it. It also changes the instrument's character: a
balance decision, not a repair.

### 4. Reverb

A reverb send blends a part and fills the gaps where its noise would show, and also carries that noise into its tail.
Judge both.

### 5. Denoising the samples

`soundbank.py`'s `denoise` reduces the steady noise of a bank's recordings when the bank is built
([soundbank-building.md](soundbank-building.md)). It descends from spectral subtraction (Boll 1979): a short-time Wiener gain per bin
from a decision-directed estimate of the a-priori signal-to-noise ratio (Ephraim and Malah 1984; Scalart and Vieira
Filho 1996), smoothed (α = 0.98) so the noise left over stays steady instead of turning into "musical noise" (Cappé
1994), and never lower than a set reduction, so that, like the spectral floor of Berouti et al. (1979), it leaves natural
noise rather than none. The gain is shared by both channels; with `keep_partials_below` each take's partials under that
frequency stay as recorded.

- It is only as good as its noise measurement, which must come from where no note sounds: the pauses of a recording cut
  into notes (`split`), as in the Iowa banks. A bank recorded one note per file has no pause, and the builder then takes
  each dynamic's quietest frames; in takes cut before the note died away those frames are the note's own last ring. In a
  probe on a soft VSCO violin take, a gain measured that way took 2.9 dB under 300 Hz and 4.2 dB over 4 kHz from its
  first 80 ms. Before using `denoise` on such takes, find stretches of plain noise in them: flat for 0.3 s, at least
  35 dB under the note, with no partial lines.
- The decision-directed estimate trails one frame behind a rising note (Cappé 1994; Plapous, Marro and Scalart 2006), so
  the softest attacks lose a little of their top. Keep the reduction to 10–12 dB (this skill's limit, from its own bank builds).
- Not for sounds that are noise themselves (cymbals, tam-tams, breath, bow and reed noise) or noisy by design (a guitar
  amplifier's hiss, vinyl).
- Check every take against this skill's own limits: its level while it sounds (median change 0.1 dB or less), its first five partials (1 dB or less), its
  first 80 ms band by band, the reduction in its pauses, then a level-matched A/B by ear. A rebuilt bank changes every
  render that uses it, so approved pieces on it need their A/B again.
- Restoration tools refine the same principle (Godsill and Rayner 1998; Wolfe and Godsill 2003): smoothing the gain in
  time and frequency against musical noise (Lukin and Todd 2007), or suppressing only the noise that would be heard
  (Tsoukalas, Mourjopoulos and Kokkinakis 1997). Reduce noise; do not try to remove it.

### 6. Clicks inside the samples

A click is not steady noise but a short knock from the instrument recorded inside a take that rings on, such as a key
let go while the sustain pedal holds the string. Every note played on that take knocks at the same moment after its
strike, most clearly under soft pedalled playing. `soundbank.py`'s `declick` finds such clicks when a bank is built and
repairs them ([soundbank-building.md](soundbank-building.md)): a click is broadband (2–12 kHz) and stands alone, where a low string's
own pulse, once a period, and a soft take's hammer noise rise again and again; in the click's frames each bin is held
to its level just before and just after, so a ringing partial passes and the knock does not. Detecting a click and
interpolating over it is the classic restoration approach (Godsill and Rayner 1998). Check a repaired take as for
denoising: the click's band back to its surroundings, the partials' level unchanged, the rest of the take bit for bit,
then an A/B by ear. It suits takes recorded one note per file: a second strike's hammer noise looks like a click too.
The Osiris pedal takes had such knocks 0.2–3.8 s after the strike, where soft pedalled playing reaches them; its build
repairs them. The VCSL Steinway, Kawai and uprights and the VSCO upright have them too, mostly 3–20 s in, where only a
long or pedalled note reaches them, and keep them as recorded ([soundbank-measurements.md](soundbank-measurements.md)).

### 7. Gates and expanders

Sampled parts are already silent between their notes. A gate or downward expander on one cuts its decays and room along
with the noise; keep them for drums and for noise between notes that a part really carries.

## The banks, measured

On 4 November 2026 every take of the 29 banks (10,616) was measured for its loud level (the loudest tenth of its 50 ms
frames) and for plain noise exposed after its note: a stretch flat within 1.5 dB for 0.3 s or more, holding no digital
silence, at least 35 dB under the loud level.

- 148 takes have one: about half of the FreePats electric guitar takes (`fsbs_clean` 70 of 120, `fsbs_dist2` 61 of 120;
  the amplifier's hiss, A-weighted 39–45 dB under the note, part of an amplified guitar's sound) and a handful in
  `vcsl_world` (8), `vcsl` (4), `iowa_strings` (2), `vcsl_keys`, `vsco` and `vsco_strings` (one each).
- The other takes, VSCO, the VCSL winds, the Karoryfer banks, the Iowa banks after their noise reduction, the tuba,
  saxophone, erhu and voice included, end in their own release, a fade or a cut, and expose no steady noise of their own.
- At 25 dB under the loud level the count rises to 511, and every stretch inspected (piano, upright bass, FM piano,
  vibraphone, archtop guitar) is the note's fundamental or a low partial still ringing; in the bands away from it the
  recordings lie 50–80 dB under the note.
- Under their notes the section strings carry bow noise and room, strongest at 1–5 kHz, and a pad of several sections
  adds it up (above).

The measure above finds noise left bare after a note; it misses noise under a ringing note. A pedalled passage on the
sampled pianos found it there: the VCSL Steinway's soft layer carries rumble about 32 dB and hiss about 60 dB under the
note's early level, the Kawai's softest 30 and 47 dB (10 and 31 on its noisiest takes), where the Osiris pedal takes
keep 58 and 73, and a pedal adds the takes up. Reducing it take by take with a gain that follows the signal, each take
its own print, was tried and set aside: what was left of the noise rose and fell with the playing. The builds now take
it out in ways that move nothing with the playing. The Steinway's soft and middle dynamics are made from its loud one
(`vcsl` b7), and the Osiris's bands are closed once each has come down to the hiss, its takes stored at full scale
(`piano_osiris` b5): in a soft pedalled passage the floor at 12 to 20 kHz lay 75 dB under the music on both, where it
had lain 50 and 60 dB under it (measured on the builds before the closing was kept out of a note's first 0.06 s). For
quiet, exposed piano choose the Steinway, or the Osiris for a closer and darker sound
([piano-and-chamber.md](piano-and-chamber.md), Instruments).

A count of every decaying, unlooped take of the banks (the 6 to 16 kHz level over the later part of the take, against
the 0.35 of a 16-bit step that dither alone leaves) then found hiss under the ringing notes of thirty-one more
instruments, a few takes to all of them. Each was played softly, alone and dry, and heard; the bands of these are
closed the same way: the nylon guitar (`iowa_guitar` b3), the folk harp (`vcsl_world` b2), the concert harp, the
vibraphone, the tubular bells and the timpani (`vcsl` b7), the Kawai grand, the Yamaha and Knight uprights, the three
TX81Z presets and the French and Flemish harpsichords (`vcsl_keys` b3), the VSCO upright (`vsco_colors` b4) and the
glockenspiel (`vsco` b6). In the opening of a piece for
guitar, harp and plucked basses, the quietest moments measured 18 dB less at 6 to 12 kHz and 27 dB less at 12 to
20 kHz, the level and everything under 3 kHz as they were.

What the closing leaves, so that it is not looked for in vain: the hiss of a band while its partials still sound
(1 to 3 kHz rings long on a guitar or a harp); everything under 1 kHz, a mains hum included (49 Hz under one cello
pizzicato take, 60 and 120 Hz under the French harpsichord); sounds of the room that are no hiss (other players
under a section's pizzicato, birdsong under the French harpsichord's long A sharp 4); a note's first 0.06 s; and takes
under 2 s, which is most pizzicato. Every pizzicato preset was tried, heard to gain next to nothing, and is as
recorded: the takes are short, and a section's takes hold the other players' strings from the pluck on, with other
sounds of the room from about 1.3 s, which no closing of bands and no earlier end of the take removes (both were
tried on the violins' G3). A pizzicato note written under a second, as they are played, ends before the later
sounds are reached. Also as recorded: the upright and electric basses, the archtop guitar, the kalimbas, and the
mbira, whose rattle is the instrument's own.
Otherwise, noise heard in a render is first a matter of an instrument's own sound, gain, voices adding up and the
playback level.

## Listening tests

Compare versions level-matched, on the same passage, with a short clip of each. For small differences ITU-R BS.1116-3
sets out blind comparison against a hidden reference. Listen at the intended playback level and once louder,
where low frequencies gain the most loudness (ISO 226:2023).

## Sources

- Berouti, M., Schwartz, R. and Makhoul, J. (1979). Enhancement of speech corrupted by acoustic noise. *Proceedings of
  IEEE ICASSP 1979*, 208–211.
- Boll, S. F. (1979). Suppression of acoustic noise in speech using spectral subtraction. *IEEE Transactions on
  Acoustics, Speech, and Signal Processing* 27(2), 113–120.
- Cappé, O. (1994). Elimination of the musical noise phenomenon with the Ephraim and Malah noise suppressor. *IEEE
  Transactions on Speech and Audio Processing* 2(2), 345–349.
- Ephraim, Y. and Malah, D. (1984). Speech enhancement using a minimum mean-square error short-time spectral amplitude
  estimator. *IEEE Transactions on Acoustics, Speech, and Signal Processing* 32(6), 1109–1121.
- Godsill, S. J. and Rayner, P. J. W. (1998). *Digital Audio Restoration: A Statistical Model Based Approach.* Springer.
- IEC 61672-1:2013. Electroacoustics: Sound level meters, part 1: Specifications (A-weighting).
- ISO 226:2023. Acoustics: Normal equal-loudness-level contours.
- ITU-R BS.468-4 (1986). Measurement of audio-frequency noise voltage level in sound broadcasting.
- ITU-R BS.1116-3 (2015). Methods for the subjective assessment of small impairments in audio systems.
- Kinsler, L. E., Frey, A. R., Coppens, A. B. and Sanders, J. V. (2000). *Fundamentals of Acoustics* (4th ed.). Wiley.
- Lukin, A. and Todd, J. (2007). Suppression of musical noise artifacts in audio noise reduction by adaptive 2D
  filtering. *123rd AES Convention*, paper 7168.
- Martin, R. (2001). Noise power spectral density estimation based on optimal smoothing and minimum statistics. *IEEE
  Transactions on Speech and Audio Processing* 9(5), 504–512.
- Plapous, C., Marro, C. and Scalart, P. (2006). Improved signal-to-noise ratio estimation for speech enhancement. *IEEE
  Transactions on Audio, Speech, and Language Processing* 14(6), 2098–2108.
- Scalart, P. and Vieira Filho, J. (1996). Speech enhancement based on a priori signal to noise estimation. *Proceedings
  of IEEE ICASSP 1996*, vol. 2, 629–632.
- Senior, M. Q. Do mixes benefit from low-pass filtering at mixdown? *Sound On Sound*, Q&A.
  https://www.soundonsound.com/sound-advice/q-do-mixes-benefit-low-pass-filtering-mixdown
- Tsoukalas, D. E., Mourjopoulos, J. N. and Kokkinakis, G. (1997). Speech enhancement based on audible noise
  suppression. *IEEE Transactions on Speech and Audio Processing* 5(6), 497–514.
- Wegel, R. L. and Lane, C. E. (1924). The auditory masking of one pure tone by another and its probable relation to the
  dynamics of the inner ear. *Physical Review* 23(2), 266–285.
- Wolfe, P. J. and Godsill, S. J. (2003). Efficient alternatives to the Ephraim and Malah suppression rule for audio
  signal enhancement. *EURASIP Journal on Applied Signal Processing* 2003(10), 1043–1051.
- Zwicker, E. and Fastl, H. (2007). *Psychoacoustics: Facts and Models* (3rd ed.). Springer.
