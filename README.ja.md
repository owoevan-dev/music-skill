<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/logo-dark-1200.png">
    <img src="assets/brand/logo-1200.png" alt="music-skill" width="440">
  </picture>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-TW.md">繁體中文</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <strong>日本語</strong> ·
  <a href="README.ko.md">한국어</a>
</p>

<p align="center">
  <a href="https://github.com/owoevan-dev/music-skill/actions/workflows/tests.yml"><img src="https://github.com/owoevan-dev/music-skill/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-MIT-1f1c1a" alt="Licence: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-1f1c1a" alt="Python 3.10 or newer">
</p>

<p align="center"><strong>生成せず、作曲する。</strong></p>

music-skill は、作曲家と小さなスタジオのやり方でオリジナルの器楽曲を作るための [Agent Skill](https://agentskills.io) です。音はすべてエージェントが一つずつ書きます。スキルはその譜面をチェックし、サンプリング音源で演奏し、ミックスとマスタリングまで仕上げます。

音声生成モデルは一切使いません。MP3 と WAV に加えて、MIDI、パートごとのステム、そしてどの音でも書き換えて作り直せるプロジェクトファイルが手に入ります。

<p align="center">
  <img src="docs/images/fughetta-on-a-lantern-theme.png" alt="『Fughetta on a Lantern Theme』のすべての音をパートごとに並べた図。上にセクション名。赤が主題で、第 1 ヴァイオリン、第 2 ヴァイオリン、ヴィオラ、チェロの順に入り、ヘ長調、ト短調、曲の終わりの低音でもう一度現れる">
</p>

## 試聴

ここにある曲はどれも、Claude（Opus 5.5、xhigh effort）がこのスキルのバージョン 0.3.0 で、一行の題材と[全エージェント共通のルール](examples/agent-rules.md)から、一回の実行で作りました。曲名、形式、楽器、音色を自分で決め、すべての音を書き、レビュー、レンダリング、手直しまで自分で行っています。完成品に人の手は入っていません。各サンプルフォルダには、プロンプト、エージェントのスクリプト、レンダリングしたときのプロジェクトがあります。

**[『Fughetta on a Lantern Theme』](https://github.com/owoevan-dev/music-skill/releases/download/examples-2/fughetta-on-a-lantern-theme.mp3)**（1:55）。題材は「チェンバロと弦楽のためのバロック風の小品、声部どうしで模倣対位法を」。グラーヴェの序奏のあと、ニ短調のフゲッタで主題が弦楽の 4 声部に順に現れます（[サンプル](examples/fughetta-on-a-lantern-theme)）。

- [『Platform in the Snowmelt』](https://github.com/owoevan-dev/music-skill/releases/download/examples-2/platform-in-the-snowmelt.mp3)（4:37）。題材は「アニメのエンディング曲のような日本のバラード、ピアノと弦楽が中心、静かに始まり、最後のサビで最も気持ちが高まる」（[サンプル](examples/platform-in-the-snowmelt)）
- [『Sodium Lights』](https://github.com/owoevan-dev/music-skill/releases/download/examples-2/sodium-lights.mp3)（4:28）。題材は「日本のシティポップ、夜のドライブの都会的な雰囲気」（[サンプル](examples/sodium-lights)）
- [『Sprinkle Satellite』](https://github.com/owoevan-dev/music-skill/releases/download/examples-2/sprinkle-satellite.mp3)（2:30）。題材は「かわいい系のフューチャーベース、明るいコードと軽快なドロップ」（[サンプル](examples/sprinkle-satellite)）

[Before and after](examples/before-after) は短い曲の音を一つ変え、レンダリングの中で一緒に変わったものを `compare` ですべて示します。そのパート、そのバス、リバーブの残響、マスターです。

録音は MP3 ファイルで、リリース [examples-2](https://github.com/owoevan-dev/music-skill/releases/tag/examples-2) からダウンロードできます。

## クイックスタート

1. スキルを入れます。Claude Code では：

   ```
   /plugin marketplace add owoevan-dev/music-skill
   /plugin install music-skill@music-skill
   ```

   Codex などほかのエージェントでは `npx skills add owoevan-dev/music-skill`。
2. レンダリング用のツールと音源のセットアップをエージェントに頼みます。[インストール](#インストール)のコマンドを実行し、ダウンロードは約 3.7 GB、私たちのテスト環境ではそのあと約 5 分かかりました。
3. ふだんの言葉で曲を頼みます。

   > RPG の町のテーマを 1 分のループで書いて。リコーダーとハープに、やわらかい弦を添えて。

MP3 と WAV、MIDI、パートごとのステム、足し合わせるとミックスになるバスとリバーブのリターン、プロジェクトファイルが手に入ります。24 スレッドのノート PC では、上のサンプル曲を一からレンダリングして、1 曲あたり 30 秒（フゲッタ）から 2 分半（シティポップ）でした。

## 生成すればいいのでは？

テキストから音楽を作るモデルが返すのは、完成した音声ファイルです。一部分だけ作り直せるものもありますが、開いて音を一つ動かすことはできませんし、その音がどこから来たのかも説明できません。

ここではエージェントが譜面を書くので、音楽は読んで変えられる判断の積み重ねになります。33 小節目のメロディー、和音のボイシング、ドラマーがクラッシュを叩く強さ。音を一つ変えれば、合成し直すのはそのパートだけで、ミックスはまるごと作り直されます。音色は実在の楽器をマルチサンプリングした録音（ライセンスはすべて確認できます）か、スキル内蔵のシンセサイザーです。他人の録音で学習したモデルも使っていません。

Claude などのエージェントがすでに動画を編集したりゲームを作ったりしているなら、音楽が何に合わせるべきかはもう分かっています。各シーンの長さ、カットの位置、ナレーションの入り、ステージのループの仕方です。その数字に合わせて書けます。見せ場の瞬間に盛り上がりの頂点を置き、ナレーションの下では音量を控え、ループをステージと同じ長さにする。編集が変われば、動いた小節だけを書き直します。

## しくみ

1. **書く**：エージェントが曲の構成とテーマを決め、プロジェクトファイルを書きます。各音の音高と長さは譜面に、弾き方（ベロシティ、タイミング、離すタイミング）は別に記録します。長めの曲は、エージェントが書く短い Python スクリプトで生成するのが普通です。ボイシングやベースライン、ドラムのパターンが読みやすく、直しやすくなります。
2. **譜面をチェックする**：`review` は、パート同士で鳴り続ける短二度・短九度を一覧にし、書かれたコードから外れた音には経過音や掛留音などの非和声音の名前を付けて、順次進行で解決しないものを尋ねます。独立した声部間の連続五度・八度と、低すぎる音域の狭い音程も挙げます。どれも偶然ではなく、意図した選択になります。
3. **演奏する**：演奏モデルが、人が弾くときに生まれるずれを加えます。奏者ごとのタイミングと音量のゆるやかな揺れ、少し後ろに置いたベース、フレーズの山なりの抑揚、そして同時には押されず同時には離されない和音。サンプリングのメロディーはレガートでつなぐことも、ベンドさせることもできます。
4. **レンダリングする**：FluidSynth が、ライセンスの明確な SoundFont 音源で、サンプル音源のパートをそれぞれの楽器で鳴らします。エレクトロニックのパートは、内蔵のシンセサイザーとドラムマシン、または Surge XT シンセサイザーのプリセットで鳴らします。
5. **ミックスとマスタリング**：各パートはドラム、ベース、リズム、アンサンブル、メロディーのバスと、自動生成した四種類のリバーブを通り、マスター処理で プロジェクトの目標ラウドネス（標準は −16 LUFS、配信向けなら −14 LUFS）、トゥルーピーク −1 dBTP 以下に仕上がります。オーケストラやオルガンの曲は、コンプレッサーを通さずに強弱の幅をそのまま残せます。エレクトロニックな曲には、サイドチェインのダッキング、テンポに合わせたディレイ、フィルタースイープ、クラブ向けの大音量マスターを加えられます。
6. **計測する**：`analyze` は、セクションごとの音量、スペクトル、ステレオ感、メロディーが伴奏よりどれだけ前に出ているかを測り、マスターの音のバランスを、市販の録音について公表された測定値や同じジャンルのリファレンスと比べます。数字は問題の場所を示すだけで、聴くことの代わりにはなりません。

音を一つ変えれば、合成し直すのはそのパートだけです。音符もミックスも変わっていないパートは、DAW のフリーズしたトラックのように、キャッシュの処理済みステムをそのまま使います。レンダリングのたびに全パートからミックスし直すので、共有のリバーブとその残響、マスターも変更に追従します。修正は一回ごとに `round` を一つ実行します。譜面をチェックし、ドラフト（同じ音で、納品にだけ要るファイルを省いたもの）をレンダリングし、測定し、前の回と比べて、それぞれの短い要約を出します。`compare` は二つのレンダリングの違いを示します。どのパートを合成し直したか、どのステム、バス、リバーブのリターンが、どこでどれだけ変わったかです。

ゲーム用のプロジェクトはループにできます。レンダリング時に残響の尾をループの頭へ折り返し、Godot や RPG Maker が読む形式でループ位置を WAV と Ogg に書き込み、各セクションの頭にはキューポイントを付けます。ループをいくつかのレイヤーに分けることもでき、すべてを重ねると元のミックスになるので、ゲームの盛り上がりに合わせて音を重ねていけます。

## インストール

**Claude Code**

```
/plugin marketplace add owoevan-dev/music-skill
/plugin install music-skill@music-skill
```

**Codex やその他のエージェント**

```
npx skills add owoevan-dev/music-skill
```

`skills/music-production` をエージェントのスキルフォルダーにコピーしても使えます。

**レンダリング用ツール**（マシンごとに一度だけ。エージェントに任せられます）

Python 3.10 以降と NumPy が必要です。Linux と macOS では仮想環境を使うと NumPy をシステムの Python から分けられ、下のコマンドも `python` で動きます（Debian と Ubuntu では先に `sudo apt install python3-venv`）。

```
python3 -m venv .venv && . .venv/bin/activate        # Windows: py -m venv .venv, then .venv\Scripts\activate
python -m pip install -r skills/music-production/requirements.txt
```

Windows x64 では、固定バージョンの FluidSynth と FFmpeg のポータブル版に加え、Surge XT シンセサイザーとそれを動かすプラグインホスト（約 55 MB）、その 3,008 個のパッチ（約 217 MB）をダウンロードします。パッチは `--no-surge-catalog`、Surge 全体は `--no-surge` で省けます。

```
python skills/music-production/scripts/bootstrap.py --runtime <folder>/.runtime --config <folder>/local-config.json
```

Linux（Ubuntu 24.04、Debian 13 以降）と macOS では、システムのパッケージを使います。Surge XT とそのパッチは Windows と同じく自動でダウンロードします（Linux は x86-64 のみ）。

```
sudo apt install fluidsynth ffmpeg libarchive-tools        # macOS: brew install fluid-synth ffmpeg
python skills/music-production/scripts/bootstrap.py --system --runtime <folder>/.runtime --config <folder>/local-config.json
```

macOS の Homebrew 版 `ffmpeg` は、ゲーム用ループの Ogg 版（`loop.ogg`）を書き出せません。必要なら `brew install ffmpeg-full` を実行し、bootstrap に `--ffmpeg "$(brew --prefix ffmpeg-full)/bin/ffmpeg"` を加えてください。

続いて音源を入れます（このプロジェクトで構築したもの）。30 種すべてでダウンロードは約 3.5 GB、インストール後は約 8 GB です。`--delete-sources` を付けない限りダウンロードしたファイルは runtime フォルダーに残るので、約 12 GB の空きを用意してください。`--only orchestra`、`band`、`world`、`examples`（サンプル曲で使う音源）でグループごとに、または音源名（`--only vcsl,rusty`）で個別に入れられます。入っていない音源を使うプロジェクトは、それを入れるコマンドを示して止まります。`--from-source` を付けると、配布元のサンプルから自分で構築します。

```
python skills/music-production/scripts/fetch_soundbanks.py --config <folder>/local-config.json --runtime <folder>/.runtime --output <folder>/local-config.studio.json
```

GPU もアカウントも音声モデルも要りません。ダウンロードはすべて配布元か、このプロジェクト自身のリリースから行い、固定した SHA-256 で照合します。

**実行するもの・取得するもの・送信するもの**：スキルが実行するのは Python スクリプト、FluidSynth、FFmpeg、インストールされていれば Surge XT で、すべてお使いのコンピューター上で動き、レンダリングはオフラインです。スキル自身のダウンローダーがツールと音源を取得するのは github.com と GitHub のダウンロード用ホスト（api.github.com、raw.githubusercontent.com、objects.githubusercontent.com、release-assets.githubusercontent.com）、そして音源を元の録音からビルドするときだけアイオワ大学の theremin.music.uiowa.edu からだけで、ほかのホストへのリダイレクトは拒否します。Python パッケージ（NumPy と、Surge XT 用の pedalboard）は pip を通して取得し、pip に別のパッケージインデックスを設定していなければ PyPI から入ります。その場合も pedalboard の wheel は固定した SHA-256 で照合します。何も送信しません。テレメトリーもアカウントもアップロードもありません（[PRIVACY.md](PRIVACY.md)）。

## 使い方

エージェントに普段の言葉で頼んでください。

> パズルゲームのタイトル画面用に、90 秒のインストを書いて。あたたかくて少し切ない感じで、ピアノとストリングス。

> TV サイズのアニメ OP 風の曲を作って。ギターバンドにピアノのメロディーで。

> ビジュアルノベルの悲しい場面に流すループ曲を書いて。柔らかいピアノとチェロで、文章を読む邪魔にならない静かさで。

> フルオーケストラで 2 分の曲を書いて。日の出の情景で、静かなホルンのソロからオーケストラ全体まで。

> レースゲームの夜のドライブに合うシンセウェイヴの曲を作って。100 BPM、ゲートリバーブのスネア、グライドするリード。

> 雨のカフェの場面にボサノヴァを書いて。ナイロン弦ギター、フルート、やわらかいドラムで。

> 33 小節目のサビのメロディーが忙しすぎる。シンプルにして作り直して。

> 前のバージョンから何が変わった？違いを聴かせて。

> MIDI とステムもちょうだい。

## 音源

| 楽器 | 音源 | ライセンス |
|---|---|---|
| ピアノと鍵盤 | VCSL（Versilian Studios）の Steinway B、Kawai のグランドピアノ、アップライトピアノ、チェンバロ、Yamaha TX81Z の FM 音色、パイプオルガン。Karoryfer Samples の Osiris Piano（サステインペダルを踏んだ録音と踏まない録音） | CC0 |
| オーケストラ | VSCO 2 Community Edition（Versilian Studios）のストリングス（パート別、トレモロ、ピチカートを含む）、ブラス、トロンボーン、テューバ、コントラバス、木管、ピッコロ、グロッケンシュピール。VCSL のハープ、鍵盤打楽器、チューブラーベル、ティンパニ、オーケストラ打楽器。アイオワ大学電子音楽スタジオのホルン、バストロンボーン、クラリネット、フルート、ソロ弦楽器、打楽器 | CC0。アイオワ：用途を問わず制限なく使用可 |
| バンド | FreePats FSBS のエレキギター（ディストーション 2 種、クリーン 1 種）。Bass YR のピック弾きと指弾き（サンプル収録：Andrea Biasior）。Karoryfer Samples の Big Rusty Drums、5 弦ベース、ピチカートのコントラバス、アーチトップギター、バリトンサックス、テューバ。Karoryfer Lecolds と bigcat instruments のソロ・チェロ。アイオワ大学電子音楽スタジオのナイロン弦クラシックギター | CC0。アイオワ：用途を問わず制限なく使用可 |
| ソロと民族楽器 | VCSL のテナーサックス、サクセロ、リコーダー、オカリナ、ハーモニカ、フォークハープ、ダン・チャン、プサルテリウム、カリンバ、バラフォン、民族打楽器。二胡。テナー・スチールパン。歌声の「アー」 | CC0。スチールパン：Unlicense |
| シンセサイザー | 内蔵のシンセサイザーとドラムマシン。Surge XT とそのファクトリー・サードパーティのパッチ 3,008 個（うち 50 は厳選。任意、標準でインストール） | 内蔵：MIT。Surge XT：GPL-3.0、独立した GPL プログラムで実行 |
| その他の楽器 | MuseScore MS Basic | MIT |

収録音源はすべて CC0、用途を問わず制限なく使えるもの（アイオワ大学の録音）、またはパブリックドメインに供されたもの（スチールパン）なので、それで作った音楽にクレジットは要りません。Surge XT は GPL-3.0 で、このプロジェクトの独立した GPL プログラム（`surge_host.py`）の中だけで動きます。GPL が及ぶのはプログラム自体で、それが鳴らした音楽ではありません。MS Basic はほかのパートが代わりに使う General MIDI 音源で、ライセンスは MIT です。その表示は、派生物には謝辞を含めるよう求めています。私たちはこれを音源そのものの複製や改変のことで、それで演奏した音楽のことではないと読んでいますが、あくまで私たちの解釈です。公開する曲に MS Basic のパートがあるなら、念のためクレジットしてください（サンプル曲には使っていません）。出典は [THIRD_PARTY.md](THIRD_PARTY.md) にあります。

## どこまでできるか

`selfcheck.py` には 123 項目のチェック（レンダリング用の設定がなければ 98 項目）があり、MIDI の往復変換やアーカイブの安全性から、実際のレンダリングまで含みます。たとえば、音を一つ直したときに合成し直すのはそのパートだけで、`compare` がその音から先の、影響の届いたファイルにだけ違いを見つけること、旧来の単一リバーブのミックスが以前のリリースをビット単位で再現すること、ラウドネス計測が BS.1770 の基準音を −3.01 LUFS と読むこと。CI では、Ubuntu（FluidSynth 2.3、FFmpeg 6.1）と macOS（FluidSynth 2.6、FFmpeg 9.0）で、レンダリングも含めた全チェックを実行しています。

音楽として良いかどうかは別の話で、聴いてみるしかありません。上の曲が、このリポジトリで示せるいちばんの証拠です。

## よくある質問

**作った音楽を動画やゲーム、商用作品に使えますか？** ツールの側に妨げはありません。追加の音源は CC0 か用途を問わず使えるもので、クレジットも要りません（MS Basic は上記を参照）。GPL のプログラム（FFmpeg、Surge XT）が及ぶのはプログラム自体で、通った音楽ではありません。エージェントが書いた音楽にあなたの著作権が生じるかどうかは、お住まいの国の法律と、あなたがどこまで手を加えたかによります。

**どのエージェントで使えますか？** Agent Skills を読み込めて Python を実行できるエージェントなら使えます。Claude Code（プラグインとして）、Codex、そのほか `npx skills` で入れたもの。

**インターネットや GPU は必要ですか？** インターネットはセットアップのときだけで、レンダリングは CPU でオフラインに動きます。プロジェクトファイルが外に出るのは、エージェントが読んだ内容を自分のモデルに送るときだけです。

**自分の音源は使えますか？** SF2 の音源なら使えます。`studio.py add-soundfont` で設定に加え、パートで指定します（[soundbanks.md](skills/music-production/references/soundbanks.md)）。加えた音源はそれぞれのライセンスに従うので、作品を公開する前に確認してください。

## できないこと

- 歌うことや作詞はできません。プラグインは Surge XT だけに対応し、お手持ちの VST プラグインはまだ使えません。
- 音の質は無料の音源で決まります。YR ベースのベロシティレイヤーは一層だけ、ストリングスは立ち上がりが遅めで、マリンバ、シロフォン、ピッコロはサンプルがまばらです。サンプリングしたギターのベンドはサンプル全体の音程を変えるだけなので、本物の弦のような音色の変化はありません。
- スチール弦のアコースティックギター、合唱、そして二胡とダン・チャン以外の東アジアの楽器の音源はまだありません。こうしたパートは、サンプルの少ない MS Basic の General MIDI 音色になります。
- Surge XT はオシレーターをランダムな位相で鳴らし始めるため、Surge のパートは合成するたびにわずかに違うテイクになります。レンダーキャッシュは、パートを変えるまで一つのテイクを保持します。テンポ同期のディレイと LFO はパートごとに一つのテンポ、つまりそのパートの大半の音が始まる楽譜上のテンポに合わせます。弱起やリタルダンドでは決まらず、途中のテンポ変化にも追従しません。それ以外は毎回同じ結果になります。
- エージェントには音が聞こえません。`review` と `analyze` は問題の場所を見つけるだけで、結果は人が聴く必要があります。スキルは、聴いたとは決して言わないようエージェントに求めています。
- シンセやエフェクトのパートが多い長い曲はメモリを使います。同時にレンダリングするパートごとに最大約 2 GB で、空きメモリが少ないときは同時に処理するパートを自動で減らします（`--jobs` で指定もできます）。
- Linux と macOS ではシステムの FluidSynth と FFmpeg を使うため、固定バージョンの Windows 版とはサンプル単位でわずかに違う場合があります。

## ドキュメント

| | |
|---|---|
| [SKILL.md](skills/music-production/SKILL.md) | エージェントがたどる手順と、すべてのコマンド |
| [schema.md](skills/music-production/references/schema.md) | プロジェクトファイル：譜面、演奏、ミックス |
| [arrangement.md](skills/music-production/references/arrangement.md) | 構成、メロディー、ボイシング、各パートの役割 |
| [performance-and-mix.md](skills/music-production/references/performance-and-mix.md) | 演奏、バスによるミックス |
| [measuring.md](skills/music-production/references/measuring.md) | `analyze` と `compare` の読み方 |
| [soundbanks.md](skills/music-production/references/soundbanks.md) | 各音源と自分の音源の追加方法。プリセット、測定したくせ、音源の作り方はリンク先のファイルに |
| [outputs.md](skills/music-production/references/outputs.md) | 各コマンドが書き出すもの（キーごと） |
| [ジャンル別ガイド](skills/music-production/references) | エレクトロニックとテクノ、ヒップホップのビートとトラップ、ジャズ、ブルース、ボサノヴァとファンク、ロックとメタル、ポップとバラード、映画音楽とホラー、アニメのオープニング、ゲームと場面の音楽、オーケストラ、バロック、オルガン、ピアノと室内楽 |
| [setup.md](skills/music-production/references/setup.md) | Windows、Linux、macOS でのレンダリング用ツールの導入 |
| [sources-and-rights.md](skills/music-production/references/sources-and-rights.md) | 外部の譜面、MIDI、サンプルを使うときの注意 |

ドキュメント本体は英語で書かれています。

## コントリビュート

不具合の報告、試聴しての感想、音源の提案は [Issues](https://github.com/owoevan-dev/music-skill/issues) で歓迎しています。使い方の質問やアイデアは [Discussions](https://github.com/owoevan-dev/music-skill/discussions) へどうぞ。このスキルで作った曲もそこで共有できます。外部からのプルリクエストは現在受け付けていません。理由と代わりの方法は [CONTRIBUTING.md](CONTRIBUTING.md) にあります。

## ライセンス

コードとドキュメントは [MIT](LICENSE) です。サンプル曲の録音と楽曲は [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) でパブリックドメインに提供しています。サードパーティのツールと音源はそれぞれのライセンスのままで、このリポジトリには含めていません。ツールは配布元から、30 の音源はすべてこのプロジェクトのリリースからダウンロードします（25 は配布元のサンプルから構築したもの、5 は FreePats のファイルをそのまま詰め直したもの）。`skills/music-production/scripts/surge_host.py` は、動かす Surge XT と pedalboard と同じ GPL-3.0-or-later です。序曲の図はそのプロジェクトファイルからコードで描いたもので、ロゴの文字は Noto Serif TC（SIL Open Font License）をアウトライン化したものです。
