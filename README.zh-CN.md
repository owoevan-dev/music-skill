<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/logo-dark-1200.png">
    <img src="assets/brand/logo-1200.png" alt="music-skill" width="440">
  </picture>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <strong>简体中文</strong> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
  <a href="https://github.com/owoevan-dev/music-skill/actions/workflows/tests.yml"><img src="https://github.com/owoevan-dev/music-skill/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-MIT-111111" alt="Licence: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-111111" alt="Python 3.10 or newer">
</p>

<p align="center"><strong>不是生成，是作曲。</strong></p>

music-skill 是一个 [Agent Skill](https://agentskills.io)，让 AI agent 像作曲家加上一间小录音棚那样，写出原创的器乐曲。每一个音都由 agent 写下，skill 负责检查乐谱、用采样乐器演奏、混音和母带处理。

整个过程没有用到任何音频生成模型。除了 MP3 和 WAV，你还会得到 MIDI、每个声部各自的音轨，以及一份项目文件：其中任何一个音都能修改，改完再重新渲染。

https://github.com/user-attachments/assets/ec1994cd-6e44-4262-9354-a1186ff3304b

<p align="center"><sub>六首示例各 8 秒，取各自最密集的片段；画面直接从项目文件画出，声音就是录音本身。</sub></p>

## 试听

六首曲子，六个模型各一首，都用 xhigh effort。每首都是一次完成，只给了一条消息：[六首共用的开头](examples/prompt.md)，加上几句需求。曲名、曲式和音色都由 agent 自己决定，每个音都是它写的，审查和修改也由它自己完成。制作期间没有人回复它，它写的音符也没有人修改过。

<table>
<tr>
<td width="33%" valign="top"><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/the-lamp-on-the-wire.mp3"><img src="docs/images/the-lamp-on-the-wire.jpg" alt="《The Lamp on the Wire》的钢琴卷帘的一个瞬间"></a><br><b><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/the-lamp-on-the-wire.mp3">《The Lamp on the Wire》</a></b><br>动画电影的高潮配乐，完整管弦乐团，4:43<br><sub>Claude Fable 5.2 · <a href="examples/the-lamp-on-the-wire">制作过程</a></sub></td>
<td width="33%" valign="top"><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/battle-reel-of-the-stork-rider.mp3"><img src="docs/images/battle-reel-of-the-stork-rider.jpg" alt="《Battle Reel of the Stork-Rider》的钢琴卷帘的一个瞬间"></a><br><b><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/battle-reel-of-the-stork-rider.mp3">《Battle Reel of the Stork-Rider》</a></b><br>奇幻故事的战斗曲，民谣乐队演奏，2:58<br><sub>Claude Opus 5.5 · <a href="examples/battle-reel-of-the-stork-rider">制作过程</a></sub></td>
<td width="33%" valign="top"><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/fughetta-of-the-paper-paddock.mp3"><img src="docs/images/fughetta-of-the-paper-paddock.jpg" alt="《Fughetta of the Paper Paddock》的钢琴卷帘的一个瞬间"></a><br><b><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/fughetta-of-the-paper-paddock.mp3">《Fughetta of the Paper Paddock》</a></b><br>巴洛克小赋格，大键琴与弦乐，2:28<br><sub>Claude Sonnet 5.5 · <a href="examples/fughetta-of-the-paper-paddock">制作过程</a></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/fjord-stopwatch.mp3"><img src="docs/images/fjord-stopwatch.jpg" alt="《Fjord Stopwatch》的钢琴卷帘的一个瞬间"></a><br><b><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/fjord-stopwatch.mp3">《Fjord Stopwatch》</a></b><br>深夜阅读的 lo-fi，可循环，2:32<br><sub>Claude Haiku 5.5 · <a href="examples/fjord-stopwatch">制作过程</a></sub></td>
<td width="33%" valign="top"><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/the-cork-boat-keeps-our-evening.mp3"><img src="docs/images/the-cork-boat-keeps-our-evening.jpg" alt="《The Cork Boat Keeps Our Evening》的钢琴卷帘的一个瞬间"></a><br><b><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/the-cork-boat-keeps-our-evening.mp3">《The Cork Boat Keeps Our Evening》</a></b><br>没有歌手的抒情慢歌，3:33<br><sub>GPT-6 Astra · <a href="examples/the-cork-boat-keeps-our-evening">制作过程</a></sub></td>
<td width="33%" valign="top"><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/noon-raccoon-rooftop-run.mp3"><img src="docs/images/noon-raccoon-rooftop-run.jpg" alt="《Noon Raccoon Rooftop Run》的钢琴卷帘的一个瞬间"></a><br><b><a href="https://github.com/owoevan-dev/music-skill/releases/download/examples-5/noon-raccoon-rooftop-run.mp3">《Noon Raccoon Rooftop Run》</a></b><br>平台游戏第一关的 8-bit，可循环，1:31<br><sub>GPT-6 Luna · <a href="examples/noon-raccoon-rooftop-run">制作过程</a></sub></td>
</tr>
</table>

乐曲和录音都是 CC0；录音是 MP3 文件，放在 release [examples-5](https://github.com/owoevan-dev/music-skill/releases/tag/examples-5)。[原版与修改版对照](examples/before-after) 把一首小曲改掉一个音，再用 `compare` 列出渲染里随之改变的所有地方：那个声部、它的总线、混响尾巴和母带。

## 快速开始

1. 安装这个 skill。在 Claude Code 里：

   ```
   /plugin marketplace add owoevan-dev/music-skill
   /plugin install music-skill@music-skill
   ```

   Codex 和其他 agent：`npx skills add owoevan-dev/music-skill`。
2. 让 agent 安装渲染工具和音色库。它会执行[安装](#install)一节的命令：下载约 3.7 GB，在我们的测试电脑上接着约五分钟就完成其余步骤。
3. 用平常的话点一首曲子：

   > 给我的 RPG 写一首一分钟、可以循环的城镇主题：竖笛、竖琴和轻柔的弦乐。

你会得到 MP3 和 WAV、MIDI、每个声部的分轨、加起来就是完整混音的总线与混响返回，以及项目文件。在一台 24 线程的笔记本电脑上，上面的示例从零开始渲染，每首用了 25 秒（小赋格和 8-bit 曲）到 156 秒（57 个声部的电影配乐）。

## 为什么不直接生成？

| | 文本生成音乐的模型 | music-skill |
|---|---|---|
| 改一个音 | 重新生成整首或其中一段 | 直接改那个音，只重新演奏那个声部 |
| 你得到什么 | 一个音频文件 | 音频、MIDI、每个声部的分轨和项目文件 |
| 声音从哪里来 | 模型内部 | 录下的真实乐器和合成器，每一个都标明许可 |
| 配合场景或关卡 | 大致吻合 | 精确到小节：循环点、命中点、准确的时长 |
| 同一首再做一次 | 新的一次生成 | 同一个项目渲染出相同的声音（Surge XT 声部除外） |

如果 Claude 或其他 agent 已经在帮你剪视频或做游戏，它本来就知道音乐要配合什么：每个场景多长、转场落在哪里、旁白何时开始、关卡怎么循环。它可以照着这些数字写：在揭晓的那一刻推到最高点、旁白底下的配乐收小、循环和关卡一样长；剪辑改了，就只重写挪动到的那几小节。

## 工作原理

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/pipeline.zh-CN-dark.svg">
    <img src="docs/images/pipeline.zh-CN.svg" alt="写谱、检查、演奏、渲染、混音、测量" width="900">
  </picture>
</p>

<details>
<summary><b>六个步骤的细节</b></summary>

1. **写谱**：agent 先确定需求要的是什么，再为这首曲子随机抽出十二个词，把需求和这十二个词连成一个整体（一个场景或一段故事），由它决定需求没说到的部分：曲名、曲式、音色。接着写下计划（这首曲子靠什么辨认、高潮在哪里、用什么手段、每个段落要做到什么），再写出项目文件。每个音的音高和时值记在乐谱里；怎么演奏（力度、时间点、松开的时机）另外记录。较长的曲子通常由 agent 写一个简短的 Python 脚本来生成，让和声配置、贝斯线和鼓的乐句都清晰、好改。
2. **检查乐谱**：`review` 一开头先列出三张从乐谱算出的表（每个段落有哪些声部发声、和弦多久换一次、旋律的节奏），再拿乐谱对照计划，问出两者不符的地方。它会列出声部之间持续的小二度和小九度；为和弦外的每个音标出经过音、挂留音等非和弦音的类型，并询问没有级进解决的音；还会列出独立声部之间的平行五度、八度，以及音区过低的密集音程。每个问题都有标识符，以它开头的书面决定就是对那个问题的回答，让每一处都是有意的选择，而不是意外。
3. **演奏**：演奏模型加入真人演奏会有的偏差：每位乐手在时间和音量上缓慢的起伏、略微靠后的贝斯、乐句的起伏弧线，以及和弦中各音不会同时按下、也不会同时松开。采样的主旋律可以连奏，也可以推弦。
4. **渲染**：FluidSynth 用有许可的 SoundFont 音色库，让每个采样声部用各自的乐器演奏；电子声部则由内置的合成器和鼓机，或 Surge XT 合成器的音色演奏。
5. **混音与母带**：各声部经过鼓、贝斯、节奏、合奏和主旋律总线，以及四种自动生成的混响，最后由母带处理做到 项目的目标响度（默认 −16 LUFS，流媒体常用 −14 LUFS），真峰值不超过 −1 dBTP。采用新版混音规则时，主旋律会保持在你写的音量附近，母带以真峰值限制器收尾；管弦乐曲还能指定听起来离乐手多近，从乐手身边到音乐厅的座位。管弦乐和管风琴可以跳过压缩器，保留完整的强弱对比；电子音乐可以加上侧链闪避、跟随速度的延迟、滤波扫频，以及俱乐部级别的响亮母带。
6. **测量**：`analyze` 会测出每个段落的响度、频谱和立体声、主旋律比伴奏响多少，并把母带的音色平衡与已发表的商业录音测量，或同曲风的参考进行比较。这些数字能指出问题所在，但不能代替实际聆听。

只改一个音，就只会重新合成那一个声部；音符和混音都没变的声部，会像 DAW 里冻结的音轨一样，直接使用缓存中处理好的分轨。每次渲染都会用所有声部重新混音，所以共用混响、混响尾巴和母带都会随之改变。每一轮修改用一次 `round`：检查乐谱、渲染草稿（声音相同，只省去交付才需要的文件）、测量，再与上一轮比较，每一步都给出简短摘要。`compare` 会列出两次渲染之间的差异：哪些声部重新合成，以及哪些分轨、总线和混响返回有变化、变在哪里、差多少。

游戏用的项目可以设置循环：渲染时会把混响尾巴折回循环开头，并按 Godot 和 RPG Maker 读取的格式，把循环点写进 WAV 和 Ogg 文件，每个段落也标上提示点。循环还能拆成几层，各层相加就是完整混音，让音乐随着游戏紧张程度逐层加厚。

</details>

## 更多内容

<a id="install"></a>

<details>
<summary><b>安装</b></summary>

**在哪里运行。** 在你自己的电脑上，通过能在那里执行命令的 agent 使用；已在 Claude Code 和 Codex 中测试过。安装时需要联网一次，并会保留它的文件夹供之后的会话使用，大小从约 1 GB 到装满全部音色库的约 12 GB。claude.ai 的对话和 Cowork 尚未测试；离线或每次对话都会重置的沙盒无法保留安装。

**Claude Code**

```
/plugin marketplace add owoevan-dev/music-skill
/plugin install music-skill@music-skill
```

**Codex 与其他 agent**

```
npx skills add owoevan-dev/music-skill
```

也可以直接把 `skills/music-production` 复制到 agent 的 skills 文件夹。

**渲染工具**：每台电脑设置一次，可以交给 agent 代劳。命令里的 `<folder>` 是你自选的文件夹，放在 skill 自己的文件夹之外，安装的内容会留在那里。

需要 Python 3.10 及以上版本和 NumPy。在 Linux 和 macOS 上，用虚拟环境把 NumPy 和系统的 Python 分开，下面的命令也就能用 `python`（Debian 和 Ubuntu 要先 `sudo apt install python3-venv`）：

```
python3 -m venv .venv && . .venv/bin/activate        # Windows: py -m venv .venv, then .venv\Scripts\activate
python -m pip install -r skills/music-production/requirements.txt
```

Windows x64 会下载锁定版本的 FluidSynth 和 FFmpeg 便携版，以及 Surge XT 合成器和运行它的插件宿主（约 55 MB）与它的 3,008 个音色（约 217 MB）；加上 `--no-surge-catalog` 就不装这些音色，加上 `--no-surge` 就完全不装 Surge：

```
python skills/music-production/scripts/bootstrap.py --runtime <folder>/.runtime --config <folder>/local-config.json
```

Linux（Ubuntu 24.04、Debian 13 或更新版本）和 macOS 使用系统软件包；Surge XT 和它的音色会像 Windows 一样自动下载（Linux 限 x86-64）：

```
sudo apt install fluidsynth ffmpeg libarchive-tools        # macOS：brew install fluid-synth ffmpeg
python skills/music-production/scripts/bootstrap.py --system --runtime <folder>/.runtime --config <folder>/local-config.json
```

macOS 上 Homebrew 的 `ffmpeg` 无法输出游戏循环的 Ogg 版本（`loop.ogg`）。需要时请运行 `brew install ffmpeg-full`，并在 bootstrap 命令中加上 `--ffmpeg "$(brew --prefix ffmpeg-full)/bin/ffmpeg"`。

然后下载音色库（本项目构建好的版本）：全部三十个下载约 3.5 GB、安装后约 8 GB；除非加上 `--delete-sources`，下载的文件会留在 runtime 文件夹，所以请预留约 12 GB。`--only orchestra`、`band`、`world` 或 `examples`（示例曲用到的音色库）可以只装一组，也可以直接写音色库名称（`--only vcsl,rusty`）；项目用到尚未安装的音色库时，会停下来并给出安装命令。加上 `--from-source` 则改从各发布者的原始采样自行构建。

```
python skills/music-production/scripts/fetch_soundbanks.py --config <folder>/local-config.json --runtime <folder>/.runtime --output <folder>/local-config.studio.json
```

不需要 GPU、账号或音频模型。所有文件都从发布者或本项目自己的 release 下载，并用锁定的 SHA-256 校验。

**它运行什么、下载什么、发送什么**：skill 运行的是它的 Python 脚本、FluidSynth、FFmpeg，以及已安装时的 Surge XT，全部在你的电脑上运行，渲染不需要联网。skill 自己的下载程序只从 github.com 和 GitHub 的下载主机（api.github.com、raw.githubusercontent.com、objects.githubusercontent.com、release-assets.githubusercontent.com）下载工具和音色库；只有从原始录音构建音色库时，才会连到爱荷华大学的 theremin.music.uiowa.edu。它会拒绝重定向到其他主机。Python 包（NumPy，以及 Surge XT 用的 pedalboard）通过 pip 下载，除非你给 pip 设置了其他包索引，否则来自 PyPI；pedalboard 的 wheel 仍会用锁定的 SHA-256 校验。它不发送任何东西：没有遥测、没有账号、不上传（[PRIVACY.md](PRIVACY.md)）。

</details>

<details>
<summary><b>使用方法</b></summary>

直接用平常的话告诉 agent：

> 给我的益智游戏标题画面写一首 90 秒的器乐曲，温暖、带点忧伤，用钢琴和弦乐。

> 做一首 TV 尺寸的动漫片头风格曲子，吉他乐队配钢琴主旋律。

> 给我的视觉小说写一段悲伤场景的循环配乐：柔和的钢琴和大提琴，安静到可以边听边读。

> 写两分钟的管弦乐：日出，从安静的圆号独奏到整个乐团。

> 给我的赛车游戏写一段夜间驾驶的 synthwave 配乐：100 BPM，门限混响军鼓，滑音主旋律。

> 给雨天咖啡馆的场景写一首波萨诺瓦：尼龙弦吉他、长笛和轻柔的鼓。

> 第 33 小节的副歌旋律太满了，简化一下再重新渲染。

> 跟上一版比，改了哪里？让我听听区别。

> 也把 MIDI 和分轨发给我。

</details>

<details>
<summary><b>音色库</b></summary>

| 乐器 | 音色库 | 许可 |
|---|---|---|
| 钢琴与键盘 | VCSL（Versilian Studios）的 Steinway B、Kawai 三角钢琴、立式钢琴、羽管键琴、Yamaha TX81Z FM 音色和管风琴；Karoryfer Samples 的 Osiris Piano，分别录了踩与不踩延音踏板的版本 | CC0 |
| 管弦乐 | VSCO 2 Community Edition（Versilian Studios）的弦乐（含分部、震音和拨奏）、铜管、长号、大号、低音提琴、木管、短笛和钟琴；VCSL 的竖琴、木槌类打击乐、管钟、定音鼓和管弦打击乐；爱荷华大学电子音乐工作室的圆号、低音长号、单簧管、长笛、独奏弦乐和打击乐 | CC0；爱荷华：可自由用于任何用途，没有限制 |
| 乐队 | FreePats FSBS 电吉他（两种失真、一种干净音色）；Bass YR 拨片与指弹贝斯，采样由 Andrea Biasior 录制；Karoryfer Samples 的 Big Rusty Drums、五弦贝斯、拨奏低音提琴、弧顶爵士吉他、上低音萨克斯和大号；Karoryfer Lecolds 与 bigcat instruments 的独奏大提琴；爱荷华大学电子音乐工作室的尼龙弦古典吉他 | CC0；爱荷华：可自由用于任何用途，没有限制 |
| 独奏与世界乐器 | VCSL 的次中音萨克斯、saxello、竖笛、陶笛、口琴、民谣竖琴、越南筝（đàn tranh）、psaltery（拨弦齐特琴）、卡林巴、巴拉风和世界打击乐；二胡；次中音钢鼓；人声“啊” | CC0；钢鼓：Unlicense |
| 合成器 | 内置的合成器与鼓机；Surge XT 和它的 3,008 个出厂与第三方音色（其中五十个精选），可选，默认安装 | 内置：MIT；Surge XT：GPL-3.0，由独立的 GPL 程序运行 |
| 其他乐器 | MuseScore MS Basic | MIT |

录音音色库都是 CC0、可自由用于任何用途而没有限制（爱荷华大学的录音），或已贡献给公有领域（钢鼓），用它们制作的音乐不需要署名。Surge XT 采用 GPL-3.0，只在本项目一个独立的 GPL 程序（`surge_host.py`）里运行；GPL 约束的是程序本身，不是它们演奏出来的音乐。MS Basic 是其他声部退而使用的 General MIDI 音色库，采用 MIT：它的声明随音色库本身的复制和改编保留，用它演奏的音乐同样不需要署名。来源和我们对各项许可的理解列在 [THIRD_PARTY.md](THIRD_PARTY.md)。

</details>

<details>
<summary><b>效果如何</b></summary>

`selfcheck.py` 共有 160 项检查（没有渲染配置时为 130 项），从 MIDI 往返转换、压缩包安全到实际渲染都包含在内。例如：只改一个音时只会重新合成一个声部，而 `compare` 只在受影响的文件里、从那个音开始找到差异；旧的单一混响混音能逐位重现之前的版本；响度测量对 BS.1770 的标准测试音读出 −3.01 LUFS。CI 会跑完所有检查（包括渲染），环境是 Ubuntu（FluidSynth 2.3、FFmpeg 6.1）、macOS（FluidSynth 2.6、FFmpeg 9.0）和 Windows（固定版本的 FluidSynth 2.6.1、FFmpeg 9.0.2，加上 Surge XT）。

音乐好不好听是另一回事，只有实际聆听才知道。上面这些曲子是这个仓库最好的证据。

</details>

<details>
<summary><b>常见问题</b></summary>

**做出来的音乐可以用在视频、游戏或商业作品里吗？** 工具本身没有任何限制。音色库都不需要署名：可选音色库是 CC0 或可自由使用，MS Basic 的 MIT 许可对用它演奏的音乐没有任何要求。GPL 许可的程序（FFmpeg、Surge XT）约束的是程序本身，不是经过它们处理的音乐。至于你对 agent 帮你写的音乐是否享有著作权，取决于你所在地的法律，以及你参与塑造了多少。

**哪些 agent 可以用？** 任何能加载 Agent Skills 并运行 Python 的 agent：Claude Code（以插件安装）、Codex，以及通过 `npx skills` 安装的其他 agent。

**需要网络或 GPU 吗？** 只有安装时需要网络；渲染在 CPU 上离线进行。你的项目文件不会发给任何人，只有你的 agent 会把它读到的内容发给它自己的模型。

**可以用自己的乐器吗？** 任何 SF2 音色库都可以：用 `studio.py add-soundfont` 加进配置文件，再在声部里指定它（见 [soundbanks.md](skills/music-production/references/soundbanks.md)）。自己加的音色库保留它原本的许可，发布作品前请先确认。

</details>

<details>
<summary><b>局限</b></summary>

- 不会唱歌、不写歌词。插件只支持 Surge XT，还不能加载你自己的 VST 插件。
- 音色的上限取决于免费音色库：YR 贝斯只有一层力度，弦乐起音偏慢，马林巴、木琴和短笛的采样稀疏，采样吉他的推弦是把整段采样变调，不会有真实琴弦的音色变化。
- 目前还没有钢弦木吉他、合唱，以及二胡和越南筝以外的东亚乐器音色库；这些声部只能用 MS Basic 采样稀疏的 General MIDI 音色。
- Surge XT 的振荡器每次都从随机相位开始，所以同一个 Surge 声部每次合成都会有细微差异；渲染缓存会保留一次的结果，直到这个声部改动为止。它的节拍同步延迟和 LFO 每个声部只用一个速度：该声部大多数音符起始时的乐谱速度，所以弱起拍或渐慢不会决定它，曲中变速也不会跟着改。其他部分每次渲染都完全相同。
- agent 听不到声音。`review` 和 `analyze` 只能找出问题，结果必须由人来听；skill 也要求 agent 不得声称自己听过。
- 长曲里如果有很多合成器或效果处理的声部，会占用不少内存，同时渲染的每个声部最多约 2 GB；可用内存不足时，渲染程序会自动减少同时处理的声部数，也可以用 `--jobs` 指定。
- Linux 和 macOS 使用系统的 FluidSynth 和 FFmpeg，渲染出的采样可能与 Windows 的锁定版本略有差异。

</details>

## 文档

| | |
|---|---|
| [SKILL.md](skills/music-production/SKILL.md) | agent 遵循的工作流程，以及所有命令 |
| [schema.md](skills/music-production/references/schema.md) | 项目文件：乐谱、演奏与混音 |
| [arrangement.md](skills/music-production/references/arrangement.md) | 曲式、旋律、和声配置与各声部的职责 |
| [performance-and-mix.md](skills/music-production/references/performance-and-mix.md) | 演奏与总线混音 |
| [measuring.md](skills/music-production/references/measuring.md) | 如何解读 `analyze` 与 `compare` |
| [soundbanks.md](skills/music-production/references/soundbanks.md) | 各音色库，以及如何加入自己的音色库；预设、测得的特性与如何制作音色库见其链接的文件 |
| [outputs.md](skills/music-production/references/outputs.md) | 各命令写出的文件，逐个键说明 |
| [曲风指南](skills/music-production/references) | 电子音乐与 techno、嘻哈节拍与 trap、爵士、布鲁斯、波萨诺瓦与放克、摇滚与金属、流行与抒情曲、电影配乐与恐怖、动漫片头、游戏与场景配乐、管弦乐、巴洛克、管风琴、钢琴与室内乐 |
| [setup.md](skills/music-production/references/setup.md) | 在 Windows、Linux 和 macOS 上安装渲染工具 |
| [sources-and-rights.md](skills/music-production/references/sources-and-rights.md) | 使用外部乐谱、MIDI 与采样的注意事项 |

文档本身以英文撰写。

## 参与贡献

欢迎在 [Issues](https://github.com/owoevan-dev/music-skill/issues) 报告错误、提供试听反馈或推荐音色库。使用上的问题和想法请到 [Discussions](https://github.com/owoevan-dev/music-skill/discussions)，也欢迎在那里分享用这个 skill 做的音乐。目前不接受项目外部的 Pull Request，原因和替代做法写在 [CONTRIBUTING.md](CONTRIBUTING.md) 里。

## 许可

本项目自己的代码与文档采用 [MIT](LICENSE) 许可；第三方数据、对它们的测量结果和引用的片段保留各自的条款，列在 [THIRD_PARTY.md](THIRD_PARTY.md)。示例的录音与乐曲以 [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) 贡献到公有领域。第三方工具和音色库保留各自的许可，不包含在这个仓库中：工具从发布者下载，三十个音色库都从本项目的 release 下载，其中二十五个用发布者的采样构建，五个是 FreePats 的原文件重新打包。`skills/music-production/scripts/surge_host.py` 采用 GPL-3.0-or-later，与它运行的 Surge XT 和 pedalboard 相同。示例的图是程序直接从各自的项目文件画出来的，图中文字用 Noto Sans TC（SIL Open Font License）；logo 的文字是将 Noto Serif TC（SIL Open Font License）转为轮廓。
