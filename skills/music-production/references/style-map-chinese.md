# Style map: Chinese traditional and Chinese-style music

Chinese instrumental traditions and the modern styles built on them, for a skill whose only Chinese instrument is the
erhu. Read [style-maps.md](style-maps.md) first for the axes and for combining entries; the erhu bank and the zithers
of `vcsl_world` are described in [soundbanks.md](soundbanks.md).

Contents: [Shared by the family](#shared-by-the-family) · [Silk and bamboo](#silk-and-bamboo) ·
[Ancient-style music](#ancient-style-music) · [Shanghai popular song](#shanghai-popular-song) · [Sources](#sources)

Source tags: WP is Wikipedia, read on 9 November 2026, by article.

## Shared by the family

- **The instruments.** Sizhu, "silk and bamboo", names strings and winds: silk for the strings, bamboo for flutes
  such as the dizi and the xiao (WP Jiangnan sizhu). The erhu, a two-stringed spike fiddle, the most popular of the
  huqin, sounds through its python-skin resonator under the bow, and is used in traditional and in pop, rock and jazz
  arrangements alike (WP Erhu).
- **What the banks lack.** No dizi, xiao, pipa, yangqin, sheng, sanxian or guzheng. The stand-ins, this skill's
  choice: the `vcsl_world` dan tranh, a Vietnamese zither, for the guzheng; its psaltery and folk harp for plucked
  strings; the `vsco` and `iowa_winds` flutes for the dizi. Say so in `decisions` when one stands in.

For the family, `review` keeps every default: no source read describes a limit to change.

## Silk and bamboo

Jiangnan sizhu: a small ensemble of strings and winds, one of each, playing pieces elaborated from older tunes, mostly
indoors. `chinese/sizhu`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | new pieces made by elaborating and ornamenting older tunes | WP Jiangnan sizhu |
| `rhythm` | no source read | |
| `timbre` | plucked, bowed, strummed and struck strings, flutes, sometimes a mouth organ, small percussion; the erhu (D4–A4 strings), dizi or xiao, pipa and yangqin at the core, usually one of each, two to ten or more players | WP Jiangnan sizhu |
| `form` | no source read | |
| `mix` | music played indoors, by amateur clubs for social functions and their own entertainment | WP Jiangnan sizhu |

- **In this skill**: the `erhu` bank as the lead, with `performance.legato` and `bend`; the dan tranh or psaltery of
  `vcsl_world` for the plucked parts, a flute for the dizi; one instrument per part. The ornamented versions of one
  tune can be written as the same melody varied part by part (this skill's reading of the elaboration).
- **Variants**: *The modern Chinese orchestra* (guoyue): grown from the Shanghai sizhu in the 20th century, built on
  the Western symphony orchestra's structure with Chinese instruments in four sections, winds, plucked strings, bowed
  strings and percussion (WP Chinese orchestra; WP Guoyue). The banks can play only its erhu.
- **Neighbours**: Ancient-style music; `orchestral/cinematic`.

## Ancient-style music

Gufeng: modern Chinese compositions steeped in traditional music, narrative singing and folk song, often on Chinese
instruments, the sound of xianxia, wuxia and historical-fantasy dramas, games and animation. `chinese/gufeng`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | heavy influences of traditional Chinese music (guoyue), narrative singing (tanci) and folk songs (min'ge) | WP Gufeng music |
| `rhythm` | no source read | |
| `timbre` | often Chinese instruments | WP Gufeng music |
| `form` | theme songs and soundtracks of television drama, video games and animation | WP Gufeng music |
| `mix` | no source read | |

- **In this skill**: the `erhu` lead over strings, piano or pads; the dan tranh for plucked colour; [game-music.md](game-music.md)
  for a game's loop and [film-score.md](film-score.md) for drama.
- **Variants**: *Guofeng*: modern Mandarin pop with Chinese cultural elements (WP Gufeng music).
- **Neighbours**: Silk and bamboo; `orchestral/cinematic`; `jpop/anime-opening` (another region's theme song).

## Shanghai popular song

Shidaiqu, the Mandarin popular song of 1920s–1940s Shanghai films: tunes in the style of pentatonic folk melody over
an orchestra like an American jazz band. `chinese/shidaiqu`

| Axis | Traits | From |
|---|---|---|
| `tempo` | no source read | |
| `harmony` | no source read | |
| `melody` | tunes shaped like pentatonic folk melodies | WP Mandopop |
| `rhythm` | no source read | |
| `timbre` | instrumentation like that of an American jazz orchestra | WP Mandopop |
| `form` | songs from sound films, first made in Mandarin in the early 1930s | WP Mandopop |
| `mix` | no source read | |

- **In this skill**: a pentatonic melody (on C: C, D, E, G, A) on a lead, the erhu, a muted trumpet or the clarinet,
  over the swing band of [jazz-and-funk.md](jazz-and-funk.md).
- **Neighbours**: `jazz/swing`; Ancient-style music.

## Sources

- Wikipedia, read 9 November 2026: [Jiangnan sizhu](https://en.wikipedia.org/wiki/Jiangnan_sizhu),
  [Chinese orchestra](https://en.wikipedia.org/wiki/Chinese_orchestra), [Guoyue](https://en.wikipedia.org/wiki/Guoyue),
  [Erhu](https://en.wikipedia.org/wiki/Erhu), [Gufeng music](https://en.wikipedia.org/wiki/Gufeng_music),
  [Mandopop](https://en.wikipedia.org/wiki/Mandopop).
