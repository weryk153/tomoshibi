# Tomoshibi

Chat and hang out with your favorite anime characters. Free and open source, for macOS and Windows.

**Language:** English | [繁體中文](./README.TW.md) | [日本語](./README.JP.md) | [한국어](./README.KR.md) | [简体中文](./README.CN.md)

![Tomoshibi](assets/tomoshibi-hero.png)

## What it does

- The character picks its own expressions and gestures as it talks. Live2D and VRM (3D) models both work.
- You choose what language the character speaks. If its voice uses a different language, lines are translated before they're read out.
- It remembers what you've talked about, and starts a conversation if you've been quiet for a while.
- You can talk to it out loud, and cut in while it's speaking.
- Add your own model and write a persona, and it's your character.

## Install

Download from [Releases](https://github.com/weryk153/tomoshibi/releases/latest):

| Computer | File |
|---|---|
| Mac with Apple Silicon (M1 or later) | `arm64.dmg` |
| Mac with Intel | `x64.dmg` |
| Windows 10 / 11 | `setup.exe` |

Open it and follow the setup wizard:

1. Connect an AI. **Install with one click** sets up the free [Ollama](https://ollama.com) app and a local model. No account, and your chats stay on your computer. You can also paste an OpenAI, Claude or Gemini API key.
2. Pick a 2D or 3D character.
3. Decide whether to install the local GPT-SoVITS voice. You can also do this later.

The first launch downloads Python and a speech recognition model, about 1.5 GB. Later launches skip this.

The app isn't signed, so the system blocks it the first time:

- macOS: click **Done**, then go to **System Settings → Privacy & Security** and click **Open Anyway**.
- Windows: in the blue box, click **More info → Run anyway**.

### Run from source

Needs Python 3.10–3.12 and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/weryk153/tomoshibi.git && cd tomoshibi
uv run run_server.py
```

Then open http://localhost:12393.

If you'd rather not use a terminal, download the ZIP, unzip it, and double-click `start-companion.command` (macOS) or `start-companion.bat` (Windows). The window that opens is the server, so keep it open while you chat.

## Add your own character

Put the model folder in `live2d-models/` or `vrm-models/`, then edit a character under **Settings → Characters** and pick it. The persona, reply language and reference audio are on the same page.

Step-by-step: [Live2D](docs/add-live2d-character.md), [VRM](docs/add-vrm-character.md).

The only bundled models are ones whose licenses allow sharing: the official Live2D samples (mao_pro, haru, hiyori) and the CC0 VRM character Shino. Please don't add copyrighted characters, art or voices to this repo.

## AI model

**Install with one click** uses Ollama's `qwen2.5:3b`, which runs on a normal laptop with 8–16 GB of RAM. For smarter replies, pick a bigger model or use an API key under **Settings → LLM**.

Free APIs work too. Choose **Custom endpoint (advanced)** and enter the base URL:

- Gemini: `https://generativelanguage.googleapis.com/v1beta/openai/`
- Groq: `https://api.groq.com/openai/v1`
- Cerebras: `https://api.cerebras.ai/v1`

Use a regular chat model. Reasoning ("thinking") models put their answer in a separate field the app doesn't read, so you get a blank reply and no voice. If you want one anyway, add this to the LLM section of `conf.yaml`:

```yaml
extra_body:
  reasoning_effort: 'none'
```

## Voice

The default is the free edge-tts voice, which needs an internet connection.

For a more natural voice that runs on your computer, install [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) with one click from the wizard or **Settings → TTS**. It works on Macs with Apple Silicon (about 3.8 GB to download) and on Windows (about 8.2 GB). The default voice comes from the Tsukuyomi-chan Corpus (CV: Rei Yumesaki).

It's installed in `~/Library/Application Support/Tomoshibi/GPT-SoVITS` (macOS) or `%LOCALAPPDATA%\Tomoshibi\GPT-SoVITS` (Windows). Delete that folder to remove it. Already running GPT-SoVITS yourself? See [this guide](docs/custom-voice-gpt-sovits.md).

If you use a real person's voice as the reference, you're responsible for having the right to.

## FAQ

**There's text but no voice**
GPT-SoVITS takes about a minute to load after launch. If there's still no sound, switch back to Edge TTS under **Settings → TTS**.

**The character never replies**
No AI is connected yet. Set one up under **Settings → LLM**. If you use Ollama, make sure the Ollama app is running.

**It won't open, or the window closes right away**
Update to the latest release first. If that doesn't fix it, open `conf.yaml` and change `asr_model: 'faster_whisper'` to `asr_model: 'sherpa_onnx_asr'`.

## More docs

- [Use it from your phone or tablet (Tailscale)](docs/remote-access-tailscale.md)
- [Scenes](docs/scene-management.md), [stage effects](docs/stage-effects.md), [UI guide](docs/ui-features.md)

## Credits and license

Tomoshibi is built on [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber). Please support the original project too.

- This project's own code is MIT. The upstream server code is also MIT, Copyright (c) 2025 Yi-Ting Chiu.
- The web frontend in `frontend/` is under the Open-LLM-VTuber License 1.0 (Apache-2.0 plus additional conditions). Commercial use needs a separate license.
- The bundled Live2D sample models are used under the Live2D Free Material License and must be replaced in any paid or commercial build (see [`LICENSE-Live2D.md`](./LICENSE-Live2D.md)):
  > This content uses sample data owned and copyrighted by Live2D Inc.
- Licenses for the other components are in [`NOTICE`](./NOTICE).

## Feedback

Questions and ideas are welcome as issues or pull requests.
