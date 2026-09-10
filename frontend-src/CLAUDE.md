# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Install dependencies
```bash
pnpm install
```

This project uses **pnpm**, pinned via `packageManager` in `package.json`. Do not use `npm` or `yarn` — they would produce a second lockfile and a differently-shaped `node_modules`.

### Electron is pinned to an exact version — do not widen it

`devDependencies.electron` is `31.7.6` with **no caret**, deliberately.

macOS XProtect flags **Electron 31.7.7** as malware: on launch, the system shows
「已阻擋惡意軟體並丟到垃圾桶」 and moves `Electron.app` to the Trash. `spctl -a -vv`
on that build reports `notarization indicates this code has been revoked`. The zip
is genuine — its SHA256 matches the checksum recorded in the `electron` npm package,
and no mirror is configured — so this is Apple blocking that specific build, not a
corrupted download.

The failure is easy to misdiagnose because the app **vanishes** rather than erroring:
the binary sits on disk untouched until something tries to execute it, so `pnpm run dev`
just reports `spawn ... ENOENT` on the *next* run. 31.7.6, 31.6.0 and 43.2.0 all run
and survive; only 31.7.7 is flagged.

A caret would let pnpm resolve back to 31.7.7 and silently reintroduce this. If you
need to move off 31.7.6, verify the candidate first:

```bash
node_modules/.pnpm/electron@<version>/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron --version
# then check the file still exists — a flagged build is deleted by the OS at this point
```

### Dependency install scripts must stay allow-listed

`package.json` carries `pnpm.onlyBuiltDependencies`. pnpm blocks dependencies'
`install`/`postinstall` scripts by default, and Electron downloads its binary in
`postinstall` — without the allow-list you get `Error: Electron uninstall`. Note that
`typecheck`, the unit tests, `check:i18n` and `build:web` all pass without the Electron
binary, so none of them catch this; only actually launching the desktop app does.

### Run development server
```bash
pnpm run dev        # Run Electron app in dev mode
pnpm run dev:web    # Run web-only version
```

### Build commands
```bash
pnpm run build:win     # Build for Windows
pnpm run build:mac     # Build for macOS
pnpm run build:linux   # Build for Linux
pnpm run build:web     # Build web version
```

### The desktop build bundles the Python backend

`build:mac` / `build:win` / `build:unpack` run two extra steps before electron-builder:

- `scripts/fetch-uv.mjs` downloads a pinned `uv` (version + SHA-256 in the script) into `bundled/uv/<os>-<arch>/`
- `scripts/stage-backend.mjs` copies the backend into `bundled/backend/` — git-tracked files **plus untracked-but-not-ignored ones** (a brand-new module that isn't committed yet must still ship), limited to the runtime directories listed in the script

Both land in `extraResources`, outside the asar. At launch, `src/main/backend-manager.ts` copies the backend into `userData/backend` (the app directory is read-only; the backend writes conf.yaml, history and models relative to its cwd), runs `uv sync --frozen --no-dev`, starts `run_server.py` and waits for `/api/characters` before creating the main window; `src/main/startup-window.ts` shows progress meanwhile. If a Tomoshibi backend already answers on 12393 it is reused. Dev mode (`pnpm run dev`) never spawns anything.

macOS builds are ad-hoc signed by `scripts/adhoc-sign.cjs` (electron-builder `afterPack`). Without it, packaging invalidates Electron's own ad-hoc signature and Apple Silicon reports a downloaded app as **"damaged"** with no way to allow it; with it, users get the ordinary "Apple could not verify" prompt they can override in System Settings → Privacy & Security. Check a build with `codesign --verify --deep --strict <app>`.

CI runs `scripts/smoke-backend.mjs` after packaging, which repeats those steps headlessly on both OSes. Keep its env and commands in sync with `backend-manager.ts`.

### Code quality
```bash
pnpm run lint          # Run ESLint
pnpm run lint:fix      # Run ESLint with auto-fix
pnpm run typecheck     # Run TypeScript type checking (both node and web)
pnpm run format        # Format code with Prettier
```

### Translation extraction
```bash
pnpm run extract-translations  # Extract i18n strings
```

## Architecture Overview

This is an Electron + React application for an AI VTuber system with Live2D integration. The architecture consists of:

### Main Process (`src/main/`)
- **index.ts**: Entry point, sets up IPC handlers for window management, mouse events, and screen capture
- **window-manager.ts**: Manages window state, modes (window/pet), and window properties
- **menu-manager.ts**: Handles system tray and context menus

### Renderer Process (`src/renderer/src/`)
- **App.tsx**: Root component that sets up providers and renders the main layout
- **Two display modes**:
  - **Window mode**: Full UI with sidebar, footer, and Live2D canvas
  - **Pet mode**: Minimal overlay with just Live2D and input subtitle

### Core Services
- **WebSocket Handler** (`services/websocket-handler.tsx`): Central communication hub that:
  - Manages WebSocket connection to backend server
  - Handles incoming messages (audio, control, model updates, chat history)
  - Coordinates state updates across multiple contexts
  - Manages audio playback queue

### Context Providers (State Management)
The app uses React Context for state management with multiple specialized contexts:
- **AiStateContext**: AI conversation state (idle, thinking, speaking, listening)
- **Live2DConfigContext**: Live2D model configuration and loading
- **ChatHistoryContext**: Conversation history and messages
- **VADContext**: Voice Activity Detection for microphone control
- **WebSocketContext**: WebSocket connection state and messaging
- **SubtitleContext**: Subtitle display management
- **GroupContext**: Multi-user group session management

### Live2D Integration
- Uses Cubism SDK (WebSDK folder) for Live2D model rendering
- **live2d.tsx**: Main Live2D component handling model loading, animation, and lip sync
- Supports model switching, expressions, and motion playback
- Audio-driven lip sync with volume-based animation

### Key Features
- Real-time voice interaction with VAD (Voice Activity Detection)
- WebSocket-based communication with backend AI server
- Live2D character animation with expressions and lip sync
- Multi-language support (i18n)
- Group/collaborative sessions
- Screen capture support
- Customizable backgrounds and UI themes

## Important Notes
- The app requires a backend server connection (WebSocket) for AI functionality
- Live2D models are loaded from URLs provided by the backend
- Audio is streamed as base64-encoded data with volume arrays for lip sync
- The app uses Chakra UI v3 for the component library
- ESLint is configured with relaxed rules (many checks disabled in .eslintrc.js)