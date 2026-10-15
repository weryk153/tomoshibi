# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tomoshibi is an app for chatting and interacting with your favorite anime characters (Live2D or VRM avatars), built on [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) (MIT). It runs completely offline when paired with a local LLM. It's a cross-platform Python application supporting real-time voice conversations, visual perception, and Live2D character animations. The project features modular architecture for LLM, ASR (Automatic Speech Recognition), TTS (Text-to-Speech), and other components.

## Gotchas and Conventions

- **Frontend source**: `frontend-src/` — a vendored fork of upstream `Open-LLM-VTuber-Web` (tracked directly in this repo, not a submodule; see `frontend-src/UPSTREAM.md` for the pinned upstream commit)
- **Frontend build output**: `frontend/` — a **generated** artifact produced by `pnpm --dir frontend-src run build:web`. That command runs with `emptyOutDir: true`, so it wipes `frontend/` before writing. Never hand-edit files in `frontend/` — edit `frontend-src/` and rebuild. Static files that must ship in `frontend/` belong in `frontend-src/src/renderer/public/`, since anything else in `frontend/` gets deleted on the next build.
  - **Any commit that changes `frontend-src/` must rebuild and commit `frontend/` too.** `frontend/` is what the backend actually serves, so a change left unbuilt simply does not take effect — and nothing warns you. This has already happened once: a fix adding a missing i18n key was committed without a rebuild, so the broken UI label stayed broken in the served bundle. Locale JSON in particular is bundled into the JS, so translation edits always change the output. To check whether `frontend/` is stale: run `pnpm --dir frontend-src run build:web` and see whether `git status --short -- frontend/` comes back non-empty.
- **Minecraft 模式**: `src/open_llm_vtuber/minecraft/`（接 Mindcraft 的 MindServer，設定在 `conf.yaml` 的 `minecraft_config`；怎麼架見 `docs/minecraft-with-mindcraft.md`）
- **VRM models**: `vrm-models/` — `<name>/<name>.vrm` + `<name>/motions/*.vrma`；掃描登記與對應驗證在 `src/open_llm_vtuber/vrm_models.py`，角色 renderer 的共用介面在 `frontend-src/src/renderer/src/avatar/character-renderer.ts`（見 `docs/add-vrm-character.md`）
- **Character definitions**: `characters/` — each file owns that character's voice, reply language, subtitle translation and long-term memory switch (`OWNED` in `src/open_llm_vtuber/character_settings.py`); startup fills in missing ones (`conf_upgrade.upgrade_character_files`)
- **Chat history**: `chat_history/` — `<conf_uid>/<history_uid>.json` 逐字稿；記憶全在引擎的 `<conf_uid>/engine/`（這段對話的記憶、她自己的記憶）。舊版留下的 `<conf_uid>/<history_uid>/core_memory.md`、`<conf_uid>/self_memory.md` 不會搬進引擎（當下的話被記成事實，搬進去她會每輪照著講）

### Configuration Changes
- Always update both default config templates (`config_templates/conf.default.yaml` and `conf.ZH.default.yaml`)
- Maintain backward compatibility when possible
- Use the upgrade system (`conf_upgrade`) for breaking changes
- Validate configurations in respective config manager classes

## Package Management

- **torch is an optional extra, not a default dependency**: only `fun_asr`, `coqui_tts` and `silero_vad` import it, and only when selected. Use `uv sync --extra torch` for those; the factories raise a message saying so when it is missing. Keeping it out of the default install saves ~350MB for everyone, including the desktop app's first launch.
- **AI Character Engine is a regular dependency**, installed by `uv sync` from PyPI and pinned to an exact version in `pyproject.toml` (`ai-character-engine==1.4.0`). It needs Python ≥3.11, so the project is on 3.12 (`.python-version`). To try local engine changes, `uv pip install -e ../ai-character-engine`; the next `uv sync` puts the pinned version back. Moving the pin means releasing the engine first (tag `v*`, then its manual `Publish` workflow — see the engine's `docs/release.md`).
