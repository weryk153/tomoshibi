# Tomoshibi

跟喜歡的動漫角色聊天、互動的 app。免費、開源，macOS 和 Windows 都能用。

**語言：** [English](./README.md) | 繁體中文 | [日本語](./README.JP.md) | [한국어](./README.KR.md) | [简体中文](./README.CN.md)

![Tomoshibi](assets/tomoshibi-hero.png)

## 可以做什麼

- 角色會看對話內容自己做表情和動作，Live2D 和 VRM（3D）模型都可以。
- 角色講什麼語言可以自己設定。聲音的語言不一樣時，會先翻譯再唸。
- 會記得你聊過的事，你一陣子沒說話，它也會主動找你聊。
- 可以直接用講的，講到一半也能打斷它。
- 放進自己的模型、寫好人設，就是你的角色。

## 安裝

到 [Releases](https://github.com/weryk153/tomoshibi/releases/latest) 下載：

| 電腦 | 檔案 |
|---|---|
| Apple Silicon Mac（M1 以後） | `arm64.dmg` |
| Intel Mac | `x64.dmg` |
| Windows 10／11 | `setup.exe` |

打開之後照著設定精靈走：

1. 接上 AI。按「一鍵安裝」會裝好免費的 [Ollama](https://ollama.com) 和本機模型，不用帳號，對話也不會離開你的電腦。也可以貼 OpenAI、Claude 或 Gemini 的 API key。
2. 選 2D 或 3D 角色。
3. 要不要裝本機語音 GPT-SoVITS，也可以之後再決定。

第一次開啟會下載 Python 和語音辨識模型，大約 1.5GB，之後就不用等了。

app 沒有簽章，第一次開會被系統擋：

- macOS：先按「完成」，再到「系統設定 → 隱私權與安全性」按「強制打開」。
- Windows：在藍色視窗按「其他資訊 → 仍要執行」。

### 從原始碼執行

需要 Python 3.10～3.12 和 [uv](https://github.com/astral-sh/uv)。

```bash
git clone https://github.com/weryk153/tomoshibi.git && cd tomoshibi
uv run run_server.py
```

然後打開 http://localhost:12393。

不想用終端機，也可以下載 ZIP 解壓縮，雙擊 `start-companion.command`（macOS）或 `start-companion.bat`（Windows）。跳出來的那個視窗就是伺服器，聊天時不要關。

## 放自己的角色

把模型資料夾放進 `live2d-models/` 或 `vrm-models/`，到「設定 → 角色」編輯角色，就能選到它。人設、回覆語言、參考音也在同一頁。

詳細做法：[Live2D](docs/add-live2d-character.md)、[VRM](docs/add-vrm-character.md)。

內建的模型只放了授權允許散布的：Live2D 官方範例（mao_pro、haru、hiyori）和 CC0 的 VRM 角色「篠」。請不要把有版權的角色、圖或聲音放進這個 repo。

## AI 模型

「一鍵安裝」用的是 Ollama 的 `qwen2.5:3b`，一般 8～16GB 記憶體的電腦就跑得動。想要回覆更聰明，可以在「設定 → 語言模型」換更大的模型，或改用 API key。

免費的 API 也能用，選「自訂端點（進階）」填 base URL：

- Gemini：`https://generativelanguage.googleapis.com/v1beta/openai/`
- Groq：`https://api.groq.com/openai/v1`
- Cerebras：`https://api.cerebras.ai/v1`

請選一般的對話模型。思考型（reasoning）模型會把回答放在另一個欄位，app 讀不到，畫面會是空白，也沒有聲音。一定要用的話，在 `conf.yaml` 的 LLM 設定加上：

```yaml
extra_body:
  reasoning_effort: 'none'
```

## 語音

預設用免費的 edge-tts，需要連網。

想要更自然、在自己電腦上跑的聲音，可以在精靈或「設定 → 語音合成」一鍵安裝 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)。支援 Apple Silicon Mac（下載約 3.8GB）和 Windows（約 8.2GB）。預設聲音來自つくよみちゃんコーパス（CV.夢前黎）。

它裝在 `~/Library/Application Support/Tomoshibi/GPT-SoVITS`（macOS）或 `%LOCALAPPDATA%\Tomoshibi\GPT-SoVITS`（Windows），不要了就刪掉那個資料夾。已經自己架好 GPT-SoVITS 的話，看[這篇](docs/custom-voice-gpt-sovits.md)。

拿真人的聲音當參考音，法律責任要自己承擔。

## 常見問題

**有文字但沒有聲音**
用 GPT-SoVITS 的話，開啟後它要大約一分鐘載入。還是沒聲音，就到「設定 → 語音合成」換回 Edge TTS。

**角色都不回話**
還沒接上 AI，到「設定 → 語言模型」設定。用 Ollama 的話，確認 Ollama app 有在執行。

**打不開，或視窗一開就關**
先更新到最新版。還是不行，打開 `conf.yaml`，把 `asr_model: 'faster_whisper'` 改成 `asr_model: 'sherpa_onnx_asr'`。

## 其他文件

- [用手機或平板連線（Tailscale）](docs/remote-access-tailscale.md)
- [場景](docs/scene-management.md)、[舞台特效](docs/stage-effects.md)、[介面說明](docs/ui-features.md)

## 致謝與授權

Tomoshibi 建立在 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) 之上，也請去支持原專案。

- 這個專案自己的程式碼是 MIT。上游的伺服器程式碼也是 MIT，Copyright (c) 2025 Yi-Ting Chiu。
- `frontend/` 裡的網頁前端採 Open-LLM-VTuber License 1.0（Apache-2.0 加上額外條款），商業用途要另外取得授權。
- 內建的 Live2D 範例模型依 Live2D 無償提供材料授權使用，付費或商用版本必須換掉（見 [`LICENSE-Live2D.md`](./LICENSE-Live2D.md)）：
  > This content uses sample data owned and copyrighted by Live2D Inc.
- 其他元件的授權見 [`NOTICE`](./NOTICE)。

## 回饋

有問題或想法，歡迎開 issue 或 PR。
