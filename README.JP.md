# Tomoshibi

好きなアニメキャラクターとおしゃべりしたり触れ合ったりできるアプリです。無料・オープンソースで、macOS と Windows で使えます。

**言語：** [English](./README.md) | [繁體中文](./README.TW.md) | 日本語 | [한국어](./README.KR.md) | [简体中文](./README.CN.md)

![Tomoshibi](assets/tomoshibi-hero.png)

## できること

- キャラクターが会話に合わせて自分で表情と動きをつけます。Live2D と VRM（3D）のモデルに対応しています。
- キャラクターが話す言語を自分で決められます。声の言語が違うときは、翻訳してから読み上げます。
- 話したことを覚えていて、しばらく黙っていると向こうから話しかけてきます。
- 声で話しかけられて、話している途中に割り込むこともできます。
- 自分のモデルを入れて人設を書けば、あなたのキャラクターになります。

## インストール

[Releases](https://github.com/weryk153/tomoshibi/releases/latest) からダウンロードします。

| パソコン | ファイル |
|---|---|
| Apple シリコンの Mac（M1 以降） | `arm64.dmg` |
| Intel の Mac | `x64.dmg` |
| Windows 10／11 | `setup.exe` |

開いたら、セットアップウィザードに沿って進めます。

1. AI をつなぎます。「ワンクリックでインストール」を押すと、無料の [Ollama](https://ollama.com) とローカルモデルが入ります。アカウントは不要で、会話がパソコンの外に出ることもありません。OpenAI、Claude、Gemini の API キーを貼ることもできます。
2. 2D か 3D のキャラクターを選びます。
3. ローカル音声 GPT-SoVITS を入れるかどうかを決めます。あとからでも入れられます。

初回起動時に Python と音声認識モデル（約 1.5GB）をダウンロードします。2 回目からは待ちません。

アプリには署名がないので、初回はシステムにブロックされます。

- macOS：「完了」を押してから、「システム設定 → プライバシーとセキュリティ」で「このまま開く」を押します。
- Windows：青い画面で「詳細情報 → 実行」を押します。

### ソースから動かす

Python 3.10～3.12 と [uv](https://github.com/astral-sh/uv) が必要です。

```bash
git clone https://github.com/weryk153/tomoshibi.git && cd tomoshibi
uv run run_server.py
```

そのあと http://localhost:12393 を開きます。

ターミナルを使いたくない場合は、ZIP をダウンロードして展開し、`start-companion.command`（macOS）か `start-companion.bat`（Windows）をダブルクリックします。開いたウィンドウがサーバーなので、会話中は閉じないでください。

## 自分のキャラクターを入れる

モデルのフォルダを `live2d-models/` か `vrm-models/` に入れて、「設定 → キャラクター」でキャラクターを編集すると選べるようになります。人設、返答の言語、参照音声も同じページで設定します。

詳しい手順：[Live2D](docs/add-live2d-character.md)、[VRM](docs/add-vrm-character.md)

同梱しているのは、配布が許可されたモデルだけです（Live2D 公式サンプルの mao_pro、haru、hiyori と、CC0 の VRM キャラクター「篠」）。著作権のあるキャラクター、イラスト、声はこのリポジトリに入れないでください。

## AI モデル

「ワンクリックでインストール」で入るのは Ollama の `qwen2.5:3b` で、メモリ 8～16GB の普通のパソコンで動きます。もっと賢い返答がほしいときは、「設定 → LLM」で大きいモデルに変えるか、API キーを使ってください。

無料の API も使えます。「カスタムエンドポイント（上級者向け）」を選んで base URL を入れます。

- Gemini：`https://generativelanguage.googleapis.com/v1beta/openai/`
- Groq：`https://api.groq.com/openai/v1`
- Cerebras：`https://api.cerebras.ai/v1`

普通の会話モデルを選んでください。推論（reasoning）モデルは答えを別の欄に入れるのでアプリが読めず、返事が空で声も出ません。どうしても使う場合は、`conf.yaml` の LLM 設定に次を追加します。

```yaml
extra_body:
  reasoning_effort: 'none'
```

## 音声

標準は無料の edge-tts です。インターネット接続が必要です。

パソコン上で動く、もっと自然な声にしたいときは、ウィザードか「設定 → TTS」から [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) をワンクリックでインストールできます。Apple シリコンの Mac（ダウンロード約 3.8GB）と Windows（約 8.2GB）に対応しています。標準の声はつくよみちゃんコーパス（CV.夢前黎）です。

インストール先は `~/Library/Application Support/Tomoshibi/GPT-SoVITS`（macOS）か `%LOCALAPPDATA%\Tomoshibi\GPT-SoVITS`（Windows）です。いらなくなったらフォルダごと削除してください。GPT-SoVITS をすでに自分で動かしている場合は[こちら](docs/custom-voice-gpt-sovits.md)を見てください。

実在の人の声を参照音声に使う場合、その権利の責任はご自身にあります。

## よくある質問

**文字は出るのに声が出ない**
GPT-SoVITS は起動後の読み込みに 1 分ほどかかります。それでも出ないときは「設定 → TTS」で Edge TTS に戻してください。

**キャラクターが返事をしない**
AI がまだつながっていません。「設定 → LLM」で設定してください。Ollama を使う場合は、Ollama アプリが起動しているか確認してください。

**開かない、またはウィンドウがすぐ閉じる**
まず最新版に更新してください。それでも直らない場合は、`conf.yaml` の `asr_model: 'faster_whisper'` を `asr_model: 'sherpa_onnx_asr'` に変えます。

## その他のドキュメント

- [スマホやタブレットから使う（Tailscale）](docs/remote-access-tailscale.md)
- [シーン](docs/scene-management.md)、[ステージ演出](docs/stage-effects.md)、[画面の説明](docs/ui-features.md)

## クレジットとライセンス

Tomoshibi は [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) をもとにしています。元のプロジェクトもぜひ応援してください。

- このプロジェクト独自のコードは MIT です。上流のサーバーコードも MIT です（Copyright (c) 2025 Yi-Ting Chiu）。
- `frontend/` の Web フロントエンドは Open-LLM-VTuber License 1.0（Apache-2.0 と追加条件）です。商用利用には別途ライセンスが必要です。
- 同梱の Live2D サンプルモデルは Live2D の無償提供マテリアルの使用許諾に基づいて使っています。有料版や商用版では差し替えが必要です（[`LICENSE-Live2D.md`](./LICENSE-Live2D.md)）。
  > This content uses sample data owned and copyrighted by Live2D Inc.
- その他のコンポーネントのライセンスは [`NOTICE`](./NOTICE) にあります。

## 応援

役に立ったら [Ko-fi](https://ko-fi.com/leonhsueh) で応援してもらえるとうれしいです。質問やアイデアは issue か PR でどうぞ。
