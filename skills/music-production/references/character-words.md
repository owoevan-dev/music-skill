# Character words: how listeners group words for sound, motion and feeling

Read this when a brief describes the music by a quality rather than, or as well as, a style: bright, airy, warm,
thick, harsh, spacious, bouncy, driving, rousing, tender, epic. Research has found how people group such words; the
groups below are those groups, each with the words its source puts in it, what was measured to go with it, and where
the skill makes it.

- Find the group or groups that hold the brief's word or its near neighbours, and move the cues of each inside the
  piece's style ([style-maps.md](style-maps.md)), as a mood does ([moods.md](moods.md)).
- No source read here ties words such as bouncy, epic or heroic to particular cues. For those, choose among the cues
  of the groups the word belongs to and record the choice in `decisions` as the piece's own, not as what the word
  means.

Contents: [Sound](#sound) · [Motion](#motion) · [Feeling](#feeling) · [Checking](#checking) · [Sources](#sources)

## Sound

**Three dimensions of timbre.** English and Greek listeners described 23 instrument tones with 30 adjectives, and both
groups' ratings reduced to three shared dimensions, which the authors named luminance, texture and mass; Lichte had
proposed brightness, roughness and fullness in 1941 (Zacharakis, Pastiadis and Reiss 2014). The adjectives loading
on each at 0.75 or more, and in brackets weaker ones with their loadings:

| Dimension | English listeners | Greek listeners | Measured with it (Zacharakis et al. 2014) |
|---|---|---|---|
| Luminance | brilliant, sharp (bright 0.69) | deep and thick against brilliant | the English listeners' luminance with the energy distribution of the partials; some evidence in both groups that more inharmonic sounds, and those whose centroid fluctuates more, sound less brilliant |
| Texture | rough, messy, harsh (against them soft −0.68, warm −0.57) | warm, rounded and soft against harsh (shrill −0.74, sharp −0.62) | in both groups, stronger high partials with rough and harsh, weaker ones with round and soft |
| Mass | thick and dense against light (deep 0.74, dark 0.70; thin −0.65) | rich, full | for English listeners, higher fundamentals lighter, more inharmonicity and centroid fluctuation thicker |

- Two of the dimensions overlap: English listeners called light sounds more brilliant and thick ones less, and a
  sound high in luminance and in roughness is heard as sharp (Štěpánek 2006, through Zacharakis et al.).
- Simple spectral centroid followed perceived brightness better than a centroid relative to the fundamental
  (Schubert and Wolfe 2006, as Zacharakis et al. read their results).
- For English listeners "dark" loaded with thick and deep (0.70), not on the dimension of brilliant.

**Models of single sounds.** The Audio Commons project trained models on listeners' ratings of sound effects and
validated them (Pearce, Brookes and Mason 2018): brightness from the share of high-frequency energy and the centroid
above a cut-off (r = 0.86 with the ratings), warmth (0.79), sharpness (0.78) and boominess, after Hatano and
Hashimoto's index (0.67, the weakest); hardness, depth and roughness were validated as well, and reverberation is
classified (75% correct). They were built on single sounds, not mixes. `timbral_models` (Apache 2.0) implements them;
the skill does not install it.

**Words for mixes and effects.** Moffat, De Man and Reiss (2022) compared three collections of the words people give
to the result of an effect:
- "Warm" and "bright" were the commonest. In equalization data, bass, boom, box, vocal and warm went with a boost
  near 500 Hz and the top rolled off; clean, click, cut, thin and tin with boosts from 5 kHz up and less low end.
- The mixing books they list name a band for such words, and the books do not agree. Three of the ten words in
  their table, as examples: air is 10–20 kHz in two books (Coryat 2008; Izhaki 2008) and 12–16 kHz in a third (Katz
  2002); presence runs from 1.5–6 kHz (Coryat) to 2–11 kHz (Izhaki); fat is 60–250 Hz in one place in Owsinski
  (2006) and 200–800 Hz in another. The whole list is their Table 2, an excerpt of De Man's thesis, and is read
  there. What it shows is the spread: the band given for one word differs from book to book, and within one
  book. The books are cited through Moffat et al.
- Among the commonest words for reverberation: echo, church, big, spacious, distant, hall, ring, far, room, echoing
  and large (the SocialFX collection, crowdsourced from non-experts).
- Bright, resonant and harsh drew strong agreement between listeners in another study, open, hard and heavy weak
  agreement (cited there).

**Where the skill makes them.**
- Luminance and air: [performance-and-mix.md](performance-and-mix.md#brightness-and-air): the genre's published
  top, percussion (Elowsson and Friberg 2017), the upper register, the louder recorded dynamics, bright patches
  (`studio.py sounds --character bright`), no low-pass without a reason (Senior 2012).
- Texture: a softer dynamic or a rounder patch; the region near 3–4 kHz on the part that sticks out (Senior 2010, in
  [sound-selection.md](sound-selection.md)); a guitar's fizz low-passed ([rock-and-metal.md](rock-and-metal.md)).
- Mass: doublings, sections rather than solos, the range opened downward ([orchestration.md](orchestration.md),
  Chords and doubling); fewer parts, higher and shorter, for light.
- Warmth and the named bands: `mix.eq` on the part at the band's frequencies; `sounds --character warm`.
- Space: `reverb_db`, `space` and `depth_m`; front parts brighter and drier than those behind (White 2009, in
  [sound-selection.md](sound-selection.md)).
- Muddiness: Hoffmann's low interval limits ([arrangement.md](arrangement.md), Vertical hygiene across parts).

## Motion

No source read groups words for motion (bouncy, driving, flowing, floating, heavy, swinging) as the timbre studies
group words for sound. What was measured is how the cues of motion move listeners' judgements:
- **Articulation.** Note length over the time to the next note at 1, 0.75, 0.5 and 0.25: shorter notes moved
  ratings toward happy, legato toward sad and peaceful (Eerola, Friberg and Bresin 2013; `gate` sets it here).
- **Tempo.** 1.2 to 6 onsets per second over all voices, notes struck together counting once: fast toward happy, slow toward sad and peaceful (Eerola et al.
  2013; [moods.md](moods.md)).
- **Syncopation.** Moderate syncopation made listeners most want to move and gave the most pleasure; heavy
  syncopation hid the beat (Witek et al. 2014, in [development-and-groove.md](development-and-groove.md), Groove).
- **Timing.** Small timing deviations did not improve a simple drum pattern's groove (Frühauf, Kopiez and Platz 2013,
  in [performance-and-mix.md](performance-and-mix.md)); classic hip-hop breaks swing their sixteenths mildly, a median
  of 1.2:1 (Frane 2017, in [beats.md](beats.md)).
- **Register and dynamics.** Low and loud toward scary; high toward happy and peaceful; soft toward peaceful (Eerola
  et al. 2013).

## Feeling

**What the music expresses and what the listener feels are different ratings.** Perceived emotion is what listeners
judge the music to express; felt emotion is what they feel themselves; in 75% of the studies reviewed the music was
rated for the first (Warrenburg 2021, through Strauss et al. 2024).

- **Expressed: four emotions with measured cues.** Happy, sad, peaceful and scary, from cues varied one at a time
  (Eerola et al. 2013): [moods.md](moods.md).
- **Labels of commercial music: five clusters.** AllMusic's editors' mood labels fell into five clusters with few
  synonyms crossing between them (Hu and Downie 2007): rowdy, rousing, confident, boisterous, passionate;
  good-natured, sweet, fun, rollicking, cheerful; literate, wistful, bittersweet, autumnal, brooding, poignant; witty,
  humorous, whimsical, wry, campy, quirky, silly; volatile, fiery, visceral, aggressive, tense, intense.
- **Felt: nine dimensions.** The Geneva Emotional Music Scale groups 45 terms for emotions music evokes into nine
  dimensions, wonder, transcendence, tenderness, nostalgia, peacefulness, power (called energy in later work),
  joyful activation, sadness and tension, and three higher-order factors, sublimity, vitality and unease (Zentner,
  Grandjean and Scherer 2008, through Strauss et al. 2024). Its 45 terms are given by its authors on request; they
  are not reproduced here. Listeners felt less sublimity in hip-hop than in classical and pop excerpts, and more
  unease in hip-hop and classical than in pop (Strauss et al. 2024).
- **Strong responses.** Tears went with appoggiaturas and sequences, shivers with new or unexpected harmony; chills
  with a voice entering and changes of loudness; intensity with instruments added step by step
  ([climax-and-melody.md](climax-and-melody.md)). Chromatic mediants evoke wonder and awe in Hollywood scores
  (Lehman 2018, in [film-score.md](film-score.md)).

## Checking

No measure here says a word has been reached; each says where a part or the mix stands, for a look and, at the end of
a version, for the user's listening.
- Luminance and air: `analyze` band shares per section, and the master's slope beside its genre's
  (`published_genre`); a patch's centroid in `sounds` and `audition`.
- Mass: the parts per section and their range in `profile`; stem levels in `analyze`.
- Motion: note lengths and onsets in `profile`; `review`'s questions on block chords and pushes.
- Strong responses: the high point as the loudest and brightest section in `analyze`, the melody's peak there in
  `profile` ([climax-and-melody.md](climax-and-melody.md)).

## Sources

- Eerola, T., Friberg, A. and Bresin, R. (2013). [Emotional expression in music: contribution, linearity, and additivity
  of primary musical cues](https://doi.org/10.3389/fpsyg.2013.00487). *Frontiers in Psychology* 4:487.
- Elowsson, A. and Friberg, A. (2017). Long-term average spectrum in popular music and its relation to the level of the
  percussion. AES 142nd Convention, paper 9762. Read in its abstract.
- Hu, X. and Downie, J. S. (2007). [Exploring mood metadata: relationships with genre, artist and usage
  metadata](https://archives.ismir.net/ismir2007/paper/000067.pdf). *Proceedings of the 8th ISMIR Conference*,
  Vienna, 67–72.
- Moffat, D., De Man, B. and Reiss, J. D. (2022). [Semantic music production: a
  meta-study](https://doi.org/10.17743/jaes.2022.0023). *Journal of the Audio Engineering Society* 70(7/8), 548–564.
  The books quoted here from its Table 2: Owsinski (2006), Coryat (2008), Izhaki (2008), Katz (2002).
- Pearce, A., Brookes, T. and Mason, R. (2018). Audio Commons deliverable D5.7: [Evaluation report on the second
  prototypes of the timbral characterisation
  tools](https://audiocommons.github.io/assets/files/AC-WP5-Surrey-D5.7%20Evaluation%20report%20on%20the%20second%20prototypes%20of%20the%20timbral%20characterisation%20tools.pdf).
  University of Surrey. The models: [timbral_models](https://github.com/AudioCommons/timbral_models), Apache 2.0.
- Strauss, H., Vigl, J., Jacobsen, P.-O., Bayer, M., Talamini, F., Vigl, W., Zangerle, E. and Zentner, M. (2024).
  [The Emotion-to-Music Mapping Atlas (EMMA): a systematically organized online database of emotionally evocative
  music excerpts](https://doi.org/10.3758/s13428-024-02336-0). *Behavior Research Methods* 56, 3560–3577. CC BY 4.0.
  Cited through it: Zentner, Grandjean and Scherer (2008); Warrenburg (2021).
- Zacharakis, A., Pastiadis, K. and Reiss, J. D. (2014). [An interlanguage study of musical timbre semantic dimensions
  and their acoustic correlates](https://doi.org/10.1525/mp.2014.31.4.339). *Music Perception* 31(4), 339–358. Cited
  through it: Lichte (1941), Schubert and Wolfe (2006), Štěpánek (2006).
- In the guides linked: Frane 2017; Frühauf, Kopiez and Platz 2013; Lehman 2018; Senior 2010 and 2012; White 2009;
  Witek et al. 2014.
