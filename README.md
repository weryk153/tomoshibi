# Tomoshibi

> A free, open-source, beginner-friendly **desktop AI companion** with a Live2D or VRM (3D) avatar — long-term memory, proactive chat, natural voice, and a sleep mode. Bring your own LLM; everything else works out of the box.

**Language:** **English** | [繁體中文](./README.TW.md) | [日本語](./README.JP.md) | [한국어](./README.KR.md) | [简体中文](./README.CN.md)

![License](https://img.shields.io/badge/license-MIT%20core%20%2B%20bundled%20terms-blue)
![Built on Open-LLM-VTuber](https://img.shields.io/badge/built%20on-Open--LLM--VTuber-orange)
![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey)

---

> ### Status
>
> **Tomoshibi** builds on **[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)**.
> The desktop and web UI are rebuilt on upstream Open-LLM-VTuber-Web.
>
> Everything is configured in-app — first-run LLM wizard, character manager,
> voices, memory, proactive topics, translation, remote access. You should never
> need to hand-edit `conf.yaml`.
>
> **There is no packaged release yet.** Run from source (see
> [Prefer the terminal?](#prefer-the-terminal-advanced)) or package it yourself.

## What is this?

**Tomoshibi** turns an on-screen character — hand-drawn Live2D or fully 3D VRM — into an AI companion you actually talk to — it remembers you, starts conversations on its own, listens while you speak, and goes quiet when you say goodnight.

It is a **friendly re-packaging** of the excellent [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) project. We stand on its shoulders: upstream provides the rock-solid Live2D + ASR/TTS + LLM plumbing; this fork adds VRM (3D) alongside it, and this fork wraps it into a **download → double-click → chat** experience for non-technical users, and adds a memory system, proactive conversation, natural barge-in voice, character management, an in-app setup wizard, and a fully bilingual (English / 繁體中文) UI.

**Our principles — and what we deliberately do NOT do:**

- **Free and open source, with optional donations.** No paid tier, no paywall.
- **No mobile version.** Desktop only (macOS / Windows).
- **No model marketplace / bundled copyrighted characters.** This avoids the Live2D commercial-licensing trap — we ship only defaults whose licences allow redistribution (three free Live2D Originals and one CC0 VRM character); you bring your own character, voice, and LLM.

> Built on Open-LLM-VTuber. See [`NOTICE`](./NOTICE) for full attribution and component licenses, and [`README.upstream.md`](./README.upstream.md) for the original project's docs.

---

## Features

- **Long-term memory** — it remembers who you are and what you're working on, and gets to know you over time. A curated per-character "core memory" is injected into the persona; after each turn the LLM decides what's worth saving. Updates take effect immediately (no restart). Tunable memory cap.
- **Proactive topics** — after a stretch of silence it opens a topic on its own. Optionally pull the latest AI / tech / anime / gaming news to chat about (pure stdlib helper, **no API key needed**).
- **Natural barge-in voice chat** — talk any time; you don't have to wait for the mic, and you can cut it off mid-sentence like a real conversation.
- **Sleep / do-not-disturb mode** — say "晚安" (goodnight) and it stops initiating; it resumes the next time you talk to it. The keyword is configurable.
- **Character management** — create / edit / switch / delete characters: name + persona + Live2D or VRM model + voice + its own separate memory.
- **2D and 3D avatars** — Live2D and VRM (glTF-based 3D) both work. VRM characters get lip sync, expressions, auto-blink, gaze tracking, `.vrma` motion clips, and drag / scroll-wheel framing. Drop a folder into `vrm-models/` and it registers itself.
- **First-run setup wizard** — paste an API key (OpenAI / Claude / Gemini) or pick a local Ollama model. The wizard runs a quick test call before saving.
- **LLM settings tab** — paste an API key, or pick/type an Ollama model (a local model, or a cloud model served through Ollama).
- **Performance presets** — Light / Standard / High-performance, bundling ASR/TTS engine choice + memory-consolidation frequency + model keep-alive.
- **Cross-language translation** — optional subtitle / voice translation (off by default).
- **Works out of the box** — bundled sample Live2D models + a CC0 VRM character + free cloud TTS (edge-tts) + an auto-downloaded speech-to-text model (~1GB; a one-time, several-minute download on the very first launch). You only have to plug in an LLM.
- **Fully bilingual UI** — Traditional Chinese (zh) and English (en).

---

## Screenshots

![Tomoshibi — your AI companion in action](assets/tomoshibi-hero.png)

*Tomoshibi running on the desktop, with the bundled `Sendagaya_Shino` VRM character. Live2D avatars work the same way — pick either in character settings.*

---

## Quick start (download → double-click → chat)

The easy path — **no terminal needed.**

> **Before you start: you'll need an AI "brain" (LLM).**
> Tomoshibi is the **body and face** — the avatar, the voice, the memory. The **brain** that actually thinks and talks is a separate AI that *you* provide. You set it up in the first-run wizard. Options, easiest first:
> - **(Recommended — free, private, runs on your own machine) A local model via Ollama.** Install the free **[Ollama](https://ollama.com)** app, then run `ollama pull qwen2.5:3b` in a terminal (a small ~1.9 GB model). Tomoshibi's default already points to it, so it just works — **no account, no API key, no cost, works offline, and your chats never leave your computer.** Fine on a normal 8–16 GB laptop. (Want sharper replies and have the RAM? Pull a bigger model like `qwen2.5:7b` and pick it in Settings.)
> - **(Optional — better quality if your PC is weak) Ollama Cloud free tier.** Ollama can run a bigger model on *its* servers for free (with limits). Needs a free account — see **Option B** below; you must `ollama pull` the cloud model first.
> - **(Optional — best free quality) A free hosted API key.** Google AI Studio (Gemini), Cerebras, or Groq give a free key (no credit card). Best quality of the free options, but needs an account + key and your chats go to that provider. See **Option C**.
> - **(If you already pay for one) A cloud API key** from OpenAI / Claude / Gemini — top quality, a few pennies per chat. See **Option D**.

1. **Get the code.** On the repo page click the green **`<> Code`** button → **Download ZIP**, then unzip it (e.g. to your Desktop). _(Or `git clone` it if you prefer.)_
2. **Double-click the launcher** inside the unzipped folder:
   - **macOS:** `start-companion.command`
   - **Windows:** `start-companion.bat`
   - The first launch installs everything (`uv`, then dependencies) and can take a few minutes. **Leave that window open — it's the server.**
3. Your browser opens to **http://localhost:12393**. On first run a **setup wizard** appears: either **paste an API key** (OpenAI / Claude / Gemini) **or** **pick a local Ollama model**. The wizard tests your choice before saving.

   ![Tomoshibi first-run setup wizard](assets/tomoshibi-setup.png)

   *The first-run setup wizard, where you plug in your AI "brain".*

4. **Restart so your new brain kicks in.** Quit by **closing that same launcher/terminal window from step 2** (that stops the server), then **double-click the launcher again** to start it back up with your new LLM. (The app also notes that an LLM change "takes effect after a restart — or after switching the character once.") Then start chatting; click once on the page to enable audio.

> **macOS Gatekeeper (first launch only):** double-clicking may show *"can't be opened because it is from an unidentified developer."* This is normal for an unsigned open-source app. **Right-click** `start-companion.command` → **Open** → **Open** in the dialog. After you allow it once, double-clicking works from then on. (We don't ship a signed/notarized build — this is the free tier.)

> **Windows SmartScreen (first launch only):** double-clicking may show a blue **"Windows protected your PC"** box. This is normal for an unsigned open-source app. Click **More info** → **Run anyway**. After you allow it once, it won't ask again.

Out of the box it uses the bundled **mao** sample Live2D model (the first-run wizard also offers the bundled 3D character instead) and **edge-tts** (free cloud voice, no GPU needed). The first run also downloads a speech-to-text model automatically — it's roughly **~1GB**, so the **very first launch does a one-time download + extract that can take several minutes**. The launcher window may look frozen during this — it isn't, so **leave it open and let it finish**; this only happens once.

### Prefer the terminal? (advanced)

Most people should use the **Download ZIP** path above. If you're comfortable with a terminal, you can clone the repo instead. Requires **Python ≥ 3.10, < 3.13** and [`uv`](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/weryk153/tomoshibi.git && cd tomoshibi
uv sync                  # installs dependencies
uv run run_server.py     # start the server
# open http://localhost:12393  → setup wizard → chat
```

The wizard writes your LLM choice into `conf.yaml` for you. You can still edit it by hand (see below).

---

## Starting, stopping, and auto-start

**To start it (open the "host"):**

- **Windows:** double-click **`start-companion.bat`**
- **macOS:** double-click **`start-companion.command`** — the very first time macOS may block it, so right-click the file → **Open** → **Open**; after that a normal double-click works.

A black command window opens — **that window *is* the server; keep it open while you chat.** Once it's ready it opens the app in your browser by itself (`http://localhost:12393`). Think of it as two parts: the **command window is the engine**, the **browser tab is just the screen**.

> First launch only: it downloads a ~1GB speech model and can take a few minutes — the window may look frozen but isn't. Leave it open and let it finish.

**To stop it:**

- **Close the black command window** (or press **Ctrl + C** inside it). That fully shuts the companion down.
- Closing the **browser tab** only hides the screen — the server keeps running. Close the command window to actually stop it.
- If you installed **Ollama** for a local brain, it keeps running quietly in the background. You can leave it (it's light when idle) or quit it from the system-tray (Windows) / menu-bar (macOS) icon.

**To open it again later:** just run the same launcher again — it's also your daily launcher.

**Start it automatically when your computer turns on (optional):**

- **Windows**
  1. Right-click **`start-companion.bat`** → **Create shortcut**.
  2. Press **Win + R**, type **`shell:startup`**, press **Enter** — this opens your Startup folder.
  3. Drag the shortcut into that folder. Tomoshibi now starts at every login. *(To undo: delete the shortcut from that folder.)*

- **macOS**
  1. Open **System Settings → General → Login Items & Extensions**.
  2. Under **Open at Login**, click **+** and choose **`start-companion.command`** (or drag the file into the list).
  *(To undo: select it and click **−**.)*

Either way the command window (and then the browser) pops up on its own at login. Heads-up: a terminal window appearing every boot is normal — that's the engine starting. If you use a local Ollama brain, the Ollama app already auto-starts after you install it, so the whole companion comes up by itself.

---

## LLM setup (required)

You need **either** an API key for a cloud LLM **or** a running local LLM. A cheap model is plenty for companion chat — you do not need a flagship.

#### Option A — Local Ollama (recommended: free, private, no account)
Install [Ollama](https://ollama.com/download), then run `ollama pull qwen2.5:3b` in a terminal (~1.9 GB). Tomoshibi's default already uses `qwen2.5:3b`, so once the download finishes it works after the next restart — no API key, no account, no cloud cost, fully offline, and your chats stay on your computer. Runs comfortably on a typical 8–16 GB laptop. For sharper replies, pull a bigger model (e.g. `qwen2.5:7b`) and set it in the LLM settings tab.

#### Option B — Cloud models through Ollama (free account; good if your PC is weak)
Ollama can run a *bigger* model on its own servers, so a slow computer still gets good replies. Free tier, but it needs an account and you must pull the model first:
1. Install Ollama from [ollama.com/download](https://ollama.com/download) (v0.12+).
2. Create a free account at [ollama.com](https://ollama.com), then run `ollama signin` in a terminal.
3. **Run `ollama pull gpt-oss:20b-cloud` — you must pull it before it works.** (Just typing the name in Settings is not enough.)
4. In the LLM settings tab, choose Ollama and set the model to `gpt-oss:20b-cloud`.

`gpt-oss:20b-cloud` is the lightest free-tier-friendly model; `qwen3.5:cloud` or `minimax-m3:cloud` are stronger but use up the free limits faster.

> **Honest about "free":** $0 with no credit card, just a free account — but a *light-usage* tier: one cloud model at a time, session limits that reset ~every 5 hours plus weekly limits, and Ollama doesn't publish exact numbers, so heavy chatting can hit a limit until it resets. Inference runs on **Ollama's servers**, so don't send anything you want kept fully private. Cloud models are in preview — **confirm it answers once before relying on it.**

#### Option C — Free hosted API key (Gemini / Cerebras / Groq)
The best chat quality of the free options. Make a free account (no credit card), create an API key, and paste it in the LLM settings tab with the matching base URL:
- **Google AI Studio (Gemini):** `https://generativelanguage.googleapis.com/v1beta/openai/` — generous free tier; note Google may use free-tier chats to improve its products.
- **Cerebras:** `https://api.cerebras.ai/v1` — very fast, ~1M tokens/day free (short context window on the free tier).
- **Groq:** `https://api.groq.com/openai/v1` — very fast, with daily token caps.

Use a current model name from each provider's docs. Your chats go to that provider, and free tiers have rate limits.

#### Option D — Paid cloud API key (OpenAI / Claude / Gemini)
If you already pay for one, paste the key in the wizard. Highest quality; a small model is typically just pennies per chat.

### ⚠️ Reasoning ("thinking") models need their reasoning turned off

Reasoning models such as **`glm-4.7:cloud`** put their answer in a separate `reasoning` field and leave the normal `content` field **empty**. This app reads only `content`, so a reasoning model will show up as a **blank reply** — and since there's nothing to read aloud, **no voice either**.

**Recommendation:** pick a normal (non-reasoning) chat model. A small, fast model gives a more natural, lower-latency companion anyway.

**If you want to use one anyway:** most endpoints let you switch the reasoning off, and then the model behaves like a normal chat model. Add `extra_body` to your LLM block in `conf.yaml`:

```yaml
extra_body:
  reasoning_effort: 'none'
```

The parameter name differs per provider — check your endpoint's docs. Tested against LM Studio with `qwen3.5`, only `reasoning_effort` worked; `chat_template_kwargs.enable_thinking`, a `/no_think` prefix, and `reasoning.enabled` were all silently ignored. Turning reasoning off also removes a large latency hit: left on, that model spent thousands of characters reasoning before saying a single sentence.

> Manual edit: the LLM config lives under `character_config → agent_config → llm_configs → openai_compatible_llm` in `conf.yaml`. Comments in the file show how to point at OpenAI / Claude / Gemini with your own key. Restart the launcher after editing.

---

## Other settings

### Memory (core + deep recall)
On by default. Each character keeps its own memory at `chat_history/<conf_uid>/core_memory.md` — persona-injected core memory plus per-turn LLM consolidation (the model decides what to keep). Tune the memory cap in settings.

### Characters
Create / edit / switch / delete characters in the app — each has its own name, persona, avatar model (Live2D **or** VRM), voice, and **separate memory**. To add your own model, drop the folder under `live2d-models/` or `vrm-models/` and open the character settings — the app finds it and registers it for you. Only the three bundled Live2D samples are tracked in git; anything else you drop in there stays on your machine, and so does your `model_dict.json`.

#### More characters (optional)
For licensing safety, Tomoshibi bundles only assets whose licences allow redistribution: **3 free Live2D Original Characters** (`mao_pro`, `haru`, `hiyori`) and **one CC0 VRM character** (`Sendagaya_Shino`, with motion clips under MIT — see `vrm-models/Sendagaya_Shino/NOTICE.md`). Want more — including the male butler character **Natori**? You can download free official Live2D sample models yourself from the official page and drop them in. Get them from **[Live2D's sample models page](https://www.live2d.com/en/learn/sample/)** under Live2D's own license — we don't redistribute them. See [`docs/add-live2d-character.md`](docs/add-live2d-character.md) for the how-to.

### Performance presets
**Light / Standard / High-performance** presets bundle the ASR/TTS engine choice, memory-consolidation frequency, and model keep-alive. Pick Light on a modest machine, High-performance if you have the hardware.

### Proactive topics & news
The companion opens topics after idle time. Optionally refresh those topics with current headlines via the bundled news helper (`scripts/news_topics.py`) — pure stdlib, no API key — and schedule it (cron / launchd / Task Scheduler), e.g. every few hours.

### Sleep / quiet mode
Say "晚安" to stop it initiating; it resumes on your next message. The keyword is configurable.

### Translation
Optional cross-language subtitle/voice translation, **off by default** (`tts_preprocessor_config → translator_config` in `conf.yaml`).

### Voice
Default is **edge-tts** (free, no hardware). For a high-quality local/custom voice, run [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) as a service and point the config at it (needs a GPU or Apple Silicon). Voice-cloning a real person's voice is your legal responsibility.

---

## Troubleshooting

**The app won't open / the black window closes right away.**
Usually a settings or engine choice an older build couldn't recover from. Download the **latest release** — it opens even with an old setting. If you'd rather not update: open `conf.yaml` in the app folder, find `asr_model: 'faster_whisper'`, change it to `asr_model: 'sherpa_onnx_asr'`, save, and relaunch. (Don't restore `conf.yaml.backup` — it has the same setting.)

**It replies in text but there's no voice.**
Update to the latest release (it bundles the audio tools Windows needs) and run the launcher again so dependencies refresh. If you switched the voice (TTS) engine to GPT-SoVITS, that needs a separate service running — switch back to **Edge TTS** in Settings → Performance for the free built-in voice.

**On the first launch the browser says "this site can't be reached / connection refused."**
The server is still starting — the first run downloads a ~1GB speech model, which takes a few minutes. Leave the black window open; once it prints that it's running, refresh `http://localhost:12393`. The latest release opens the browser only when it's ready.

**Windows: "Windows protected your PC" (SmartScreen), or nothing seems to happen.**
Click **More info → Run anyway** — this is the launcher, not a virus (it's just unsigned). If your antivirus blocked the one-time `uv` install, allow the app and run the launcher again, or install `uv` manually from <https://docs.astral.sh/uv/getting-started/installation/> and retry.

**macOS: "cannot be opened because it is from an unidentified developer."**
Right-click `start-companion.command` → **Open** → **Open**. You only need to do this the first time.

**It opens but never replies / says the AI brain isn't set up.**
You still need an LLM. Open the setup wizard (or Settings → Model): paste an API key (OpenAI / Claude / Gemini), or pick a local Ollama model. For the local route, make sure the **Ollama app is installed and running** and the model is downloaded.

**Web search / tools don't work with Claude.**
The setup wizard connects Claude through a compatibility endpoint that doesn't pass tools through, so the experimental web-search/tools toggle may do nothing on Claude. For tools, use a tool-calling model like GPT-4o or Gemini, or a capable local model. (Plain chat with Claude works fine.)

---

## Guides

- [Use it from your phone / tablet (Tailscale)](docs/remote-access-tailscale.md) — reach your companion from another device, even off your home network.
- [Custom voice with GPT-SoVITS](docs/custom-voice-gpt-sovits.md) — give your character a cloned or custom voice.
- [Add your own Live2D character](docs/add-live2d-character.md) — drop a model in and switch to it.
- [Add your own VRM (3D) character](docs/add-vrm-character.md) — folder layout, expression and motion mapping, camera framing.
- [Scene management](docs/scene-management.md) · [Stage effects](docs/stage-effects.md) · [UI features](docs/ui-features.md) — backgrounds, entrance effects, and what each panel does.

## Credits & license

This project would not exist without the upstream work it builds on. Please **star and support [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)** too.

- **Upstream:** [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) — its server-side code is MIT, Copyright (c) 2025 Yi-Ting Chiu.
- **Tomoshibi's own additions** (long-term memory, proactive conversation, sleep mode, group conversation, stage performances, in-app settings for all of it, and the five-language UI) — MIT.
- **Bundled web frontend** — the compiled web bundle in `frontend/` is the Open-LLM-VTuber-Web frontend, under the **Open-LLM-VTuber License 1.0** (Apache-2.0 + additional conditions). Free, non-commercial use and redistribution is permitted; commercial rebranding, paid hosting/SaaS, or embedding in a paid product needs a separate commercial license from the Open-LLM-VTuber org. This fork is free and non-commercial, which the license permits. See [`NOTICE`](./NOTICE).
- **Live2D Cubism & bundled sample models** — the bundled **mao_pro** / **haru** / **hiyori** models are Live2D Inc. sample data, used under the **Live2D Free Material License** (see [`LICENSE-Live2D.md`](./LICENSE-Live2D.md)). Required attribution:
  > This content uses sample data owned and copyrighted by Live2D Inc.

  They are bundled **unmodified** as a free default. **For any paid/commercial build, replace them** with your own CC0 / licensed / commissioned model.
- **Other components** (see [`NOTICE`](./NOTICE) for each license): GPT-SoVITS (MIT, optional TTS), sherpa-onnx (Apache-2.0, ASR engine — the SenseVoice model has its own license; or use Whisper), Silero VAD (MIT), edge-tts (uses Microsoft's online TTS service), DeepLX (unofficial DeepL endpoint — use the official DeepL API for production).

**Do not ship copyrighted characters, artwork, voices, or trained voice models.** This repo ships only neutral defaults; bring your own.

### License

This fork's own source code is released under the **MIT License**, on top of Open-LLM-VTuber's MIT-licensed server code (Copyright (c) 2025 Yi-Ting Chiu). However, **the whole project is not simply MIT**: the bundled compiled web frontend in `frontend/` is under the **Open-LLM-VTuber License 1.0** (Apache-2.0 + additional conditions), and the bundled Live2D sample models carry their own Live2D terms. See [`LICENSE`](./LICENSE), [`NOTICE`](./NOTICE), and [`LICENSE-Live2D.md`](./LICENSE-Live2D.md) for the full, accurate picture.

---

## Support this project

This is a free, open-source project — no paywall. If it's useful to you, a tip is appreciated but never required:

- **Ko-fi:** [ko-fi.com/leonhsueh](https://ko-fi.com/leonhsueh)
- **GitHub Sponsors:** coming soon

And please support the upstream project this is built on — [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber).

---

## Contributing

Issues and pull requests are welcome.

- File bugs and feature ideas in **Issues**.
- For code changes, open a **Pull Request** with a clear description.
- Please **do not** add copyrighted characters, artwork, voices, or trained voice models — keep the repo shippable as neutral defaults only.
