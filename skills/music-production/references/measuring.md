# Measuring a render: analyze and compare

Read this to interpret what `studio.py analyze` and `studio.py compare` report: each field, the values finished pieces measured here, the tonal balance against published measurements and references, and how to judge a change. Their summaries print the key figures; every key is in [outputs.md](outputs.md). The mix itself is in [performance-and-mix.md](performance-and-mix.md).

## Measure a render: `studio.py analyze`

Fields, per section unless noted:

- `level_lufs_ungated`: K-weighted mean level. Compare sections with each other; the master's integrated loudness is in `report.json`.
- `band_share_pct`: share of power in 20–60, 60–250, 250–800, 800–2500, 2500–6000 and 6000–16000 Hz.
- `lr_correlation` and `mono_sum_change_db`: how much of the stereo image survives in mono.
- `stem_levels_lufs_ungated`: each processed stem per section, to see which part makes a section loud.
- `melody_groups`: per section and per `--span NAME:FIRST-LAST` (bars, 1-based, repeatable; each NAME its own, and `span:NAME` no section's id), the melody parts and the parts that double them in any octave (at least 60% of their onsets on a melody onset of the same pitch class), the group's stems against all other stems (`melody_group_minus_rest_db`), and `balance`: parts within 6 dB of the group's loudest stem (3 dB for bass and countermelody parts) with the cut that would put them there. An orchestral tune sits in many parts, most on the ensemble bus, which the bus measure below counts as accompaniment. Near full velocity a softer velocity changes the level little (the level follows (v/127)², so 110 to 104 is about 1 dB): make a cut with `level_dbfs`, or rest the part.
- `tonal_balance` (whole master): power per hertz in third-octave bands from 40 Hz to 16 kHz, relative to a line fitted from 100 Hz to 4 kHz and read at 1 kHz; the line's slope (`slope_db_per_octave_100hz_4khz`: pink noise reads −3, white noise 0); and how far the bands below 80 Hz (`low_end_vs_line_db`) and from 6.3 to 12.5 kHz (`top_end_vs_line_db`) sit from the line extended.
- `side_minus_mid_db` (whole master): side power minus mid power below 120 Hz, from 120 Hz to 2 kHz and from 2 to 16 kHz. −60 (the floor) is mono, 0 is two unrelated channels.
- `master`: integrated loudness, true peak and loudness range from the render's meter, and the peak-to-loudness ratio (`plr_db`, true peak minus integrated loudness).
- `reference_comparison`, with `--reference`: the master minus a reference ([below](#tonal-balance-and-references)).
- `reverb` (a bus-chain render with reverb): what the project and the spaces' impulse responses say of the reverb; the returns' audio is not read. `early_decay_time_s` is six times the time the spaces' decay takes to fall its first 10 dB (ISO 3382's early decay time), the spaces in use weighted by what the parts send into each as the project writes it. `clarity_c80_db` takes the mix as one room: the dry signal is the direct sound, and each space answers at the level the parts send to it. It is the energy of that response within 80 ms of the direct sound over the energy after, in dB, in the octaves of 500, 1000 and 2000 Hz and averaged, as Barron (2013) reports the index. Each part counts by its written level and the time its notes sound, so the figure is the same before and after a render; without the render's project it is `null`. Barron recommends −2 to +2 dB for concert halls (`hall_c80_db`; occupied halls, from the stage to a seat), a mix of a song is far clearer, and which an orchestral piece should have is its own choice ([orchestration.md](orchestration.md#how-near-the-orchestra-is-heard)); a piece that asks one with `mix.c80_db` has `c80_asked_db` beside it. The delay's return is not counted.
- `warnings`: a section from which the delivery limiter took more than 3 dB (a threshold this skill set); a master far outside the tonal balance of commercial recordings and, with a reference, wide differences from it; parts whose dynamics sat between two recorded takes that disagree in phase for more than 2% of their playing (`correction_out_of_range_pct` in the stem receipt); Surge XT parts that played their fallback preset.
- `lead_presence`: the melody against everything else as the mix hears it: in a bus-chain render the lead bus's output against the other buses, so a lead compressor's gain reduction counts; in a room-chain render the melody stems against the other stems (`lead_source` says which). Reverb and delay returns count on neither side. `lead_minus_accompaniment_level_db` is the full-band K-weighted level difference over the section. The `..._db_median` and `..._db_p10` values compare the two frame by frame in 24 bands from 200 Hz to 8 kHz, which leaves out the bass and cymbals and so reads several dB higher. `masked_share_pct` is the share of lead energy in bands where the accompaniment is at least 3 dB louder.

Values from finished pieces, as data points rather than targets:

- In *Daybreak Signal* the lead bus measured +0.3 dB with the piano lead (the published version) and +0.8 dB with a guitar lead against the other buses over the chorus, and +3.7 and +3.8 dB over the sparser verse. The band median read +5.0 and +3.3 dB in the chorus, with 1.5% and 1.0% of the lead masked.
- Before the piano version's level fix its verse measured −0.4 dB, with a 10th percentile of −4.4 dB. Raising the piano's velocities and level brought these to +3.7 and +1.7 dB.
- The stems alone put the same piano chorus at +5.2 dB. The lead compressor takes about 3 dB back and the drum bus adds about 2, which is why a bus-chain render is measured after its buses.
- A spaced-pair piano lead measured a correlation of 0.03 before `width` 0.35 brought its part back to 0.83.
- An orchestral piece with wide dynamics measured −30.5 LUFS in its pp opening and −14.0 in its ff tutti (ungated, per section), and the master kept the mix's loudness range of 20.5 LU. Its melody's band median read +3.7 to +5.0 dB over the accompaniment in the soft sections and −4.0 dB in the tutti, where the woodwinds doubling the melody count as accompaniment.
- The same notes rendered with dynamic layers along their velocities, crossfade legato on the single lines, stage depths from 1 m (first violins) to 10 m (timpani) and `range_lu` 12: the loudness range went from 19.3 LU in the mix to 12.0 in the master (largest lift 7.8 dB), the soft sections rose about 6–7 dB against the ff, and the true peak stayed at −2.2 dBTP. The early reflections came out about 13 dB under the direct sound on the double basses, 6 dB on the violins and level with it on the horns, whose sound reaches the hall largely from the stage shell.
- A piano-led mix put 34–54% of its power at 250–800 Hz and 1–5% at 2.5–6 kHz, against 26–33% at 2.5–6 kHz with a distorted lead guitar. The lead instrument causes most of such a difference, so compare spectra between mixes that share a lead.

These numbers locate causes. They do not say whether the piece works.

## Tonal balance and references

Popular commercial recordings fall about 5 dB per octave from 100 Hz to 4 kHz in power per hertz (the average spectrum of Pestana et al. 2013, about 800 recordings from 1950 to 2010; the slopes that paper gives by genre are regressions over 100 Hz to 10 kHz on logarithmic axes, another measure; Elowsson and Friberg 2017 report about 4.5 over a similar range, measured another way). Hip-hop and electronic recordings reach further into the low end, and jazz and folk fall away at the top (Pestana et al.). Tracks with more percussion carry more bass and top, which accounts for much of the difference between genres (Elowsson and Friberg). Mainstream masters lost microdynamics as they got louder from the 1980s to the late 2000s (Deruty and Pachet 2015 measure it with crest factor and related descriptors; the peak-to-loudness ratio here is a related measure, not theirs). `analyze` fits the slope to the third-octave bands centred from 125 Hz to 4 kHz. Without a reference it warns only when the slope leaves −8 to −1.5 dB per octave, far from all of these. That range and the reference differences below are prompts to look closer, chosen for this skill, not quality classes any study validated.

`tonal_balance.slope_log_log_100hz_10khz` is Pestana et al.'s own measure, the slope of log magnitude on log frequency over 100 Hz–10 kHz of the mean magnitude spectrum (frames of about 10.8 Hz, unwindowed): pink noise reads −0.5, white noise 0. Their genre means run from −0.75 (electronic) to −1.29 (jazz), pop −0.94. With a `style`, `published_genre` gives the genre that governs the mix axis, its mean, the master's slope and the difference, and `analyze` warns when the master is more than 0.3 steeper, a margin chosen for this skill. The genre means come from songs with vocals; they place a mix, they do not say what it needs ([performance-and-mix.md](performance-and-mix.md#brightness-and-air)).

For a genre, compare with a reference: `studio.py analyze <render> --reference house`. The names in [tonal-references.json](tonal-references.json) are pieces of this skill's own, measured the same way on renders of the projects in the repository's examples folder:

| Reference | Music | Slope | Low end | Top end | Side − mid below 120 Hz | LUFS | PLR | LRA |
|---|---|---|---|---|---|---|---|---|
| `jazz` | jazz blues, tenor sax and piano trio | −2.8 | −0.4 | −3.9 | −16 | −15.0 | 13.9 | 1.5 |
| `synthwave` | gated snare, octave bass, string-machine pads | −3.4 | +3.2 | −7.6 | −57 | −10.5 | 9.0 | 6.1 |
| `house` | festival house, loud master | −4.1 | −0.3 | −1.2 | −40 | −9.1 | 7.9 | 5.3 |
| `lofi` | worn-tape piano, upright bass, bit-reduced kit | −4.8 | −1.1 | −7.5 | −37 | −14.1 | 13.0 | 5.2 |
| `future_bass` | pumped supersaws, an 808, a half-time beat | −2.9 | +6.2 | −2.3 | −57 | −9.5 | 8.3 | 5.9 |
| `chiptune` | two pulses, triangle bass, noise drums | −4.0 | −13.9 | −2.8 | −60 | −14.0 | 12.0 | 0.8 |
| `orchestral` | overture with wide dynamics, in a hall | −2.9 | −14.9 | −16.4 | −7 | −17.0 | 15.2 | 12.0 |

Slopes are in dB per octave, the ends and widths in dB. The electronic references keep the bass mono; the jazz trio and the orchestra, played in rooms, carry side energy down to the bass. Where the published trends overlap, the ends follow them: the 808 and the synthwave bass extend the low end, the jazz top falls away, and the orchestra has little below 80 Hz or above 6 kHz. Several demos are flatter than the commercial average (−2.8 to −2.9 against about −5): the measure places a mix; it does not say which slope is right.

A render folder or a WAV file works as a reference too: another mix, or a commercial track the user owns, converted to WAV first. A WAV needs `--config`, for FFmpeg to convert and meter it in a temporary folder, and nothing of it is kept. `reference_comparison` gives the master minus the reference: the slope, both ends, each octave (both spectra levelled at their own line at 1 kHz), the width per band, loudness, PLR and loudness range. It warns past 1.5 dB per octave of tilt (8 dB across 100 Hz–4 kHz), 6 dB at either end, 4 dB of PLR, or a bass more than 10 dB wider than the reference's. A reference is one piece: it shows where a mix differs, not what the piece needs. Look first at what plays in each register and how loud the cymbals, bass and pads are, then at EQ.

Sources for this section:

- Pestana, P. D., Ma, Z., Reiss, J. D., Barbosa, A. and Black, D. A. A. (2013). [Spectral Characteristics of Popular Commercial Recordings 1950–2010](https://www.aes.org/e-lib/browse.cfm?elib=17010). AES 135th Convention, New York.
- Elowsson, A. and Friberg, A. (2017). [Long-term Average Spectrum in Popular Music and its Relation to the Level of the Percussion](https://www.aes.org/e-lib/browse.cfm?elib=18638). AES 142nd Convention, Berlin, paper 9762.
- Deruty, E. and Pachet, F. (2015). The MIR Perspective on the Evolution of Dynamics in Mainstream Music. *Proceedings of the 16th ISMIR Conference*, Málaga.

## Compare and judge

For a revision, compare the same passage at matched loudness, so a louder version does not fool the ear (Robjohns 2014), and keep an unchanged full version. Review the full form after local edits: a better eight-bar phrase can still damage an arrival later. If no reliable audio audition happened, say exactly that and do not invent a listening impression.

Official references: [FluidSynth features](https://www.fluidsynth.org/wiki/FluidFeatures/), [FFmpeg audio filters](https://ffmpeg.org/ffmpeg-filters.html), [ITU-R BS.1770](https://www.itu.int/rec/R-REC-BS.1770), [Yamaha keyboard pedals](https://hub.yamaha.com/keyboards/k-how-to/how-to-use-keyboard-pedals/). Runtime claims are tied to the tested versions and receipts, not inferred from those pages.

## Sources

- De Man, B., Leonard, B., King, R. and Reiss, J. D. (2014). [An analysis and evaluation of audio features for multitrack music mixtures](https://archives.ismir.net/ismir2014/paper/000293.pdf). *Proceedings of the 15th ISMIR Conference*, 137–142. The lead vocal's loudness against the mix in eight engineers' mixes of eight songs.
- De Man, B., McNally, K. and Reiss, J. D. (2017). [Perceptual evaluation and analysis of reverberation in multitrack music production](https://doi.org/10.17743/jaes.2016.0062). *Journal of the Audio Engineering Society* 65(1/2), 108–116. Open access (CC BY). Relative reverb loudness, the mixes called too reverberant and too dry, and the 5–6 dB it cites as the just-noticeable difference of the direct-to-reverberant ratio.
- Robjohns, H. (2014). [MeterPlugs Perception](https://www.soundonsound.com/reviews/meterplugs-perception). *Sound On Sound*, July 2014. Loudness-matched comparison of processed and unprocessed audio.
