# Tomoshibi

> 免費、開源、新手也能上手的 **AI 角色聊天 app**。角色可以是 Live2D 或 VRM（3D），會依對話自己做表情和動作，說話的語言也能設定，還會記得你、主動找你聊。自備 LLM，其餘開箱即用。

**語言：** [English](./README.md) | **繁體中文** | [日本語](./README.JP.md) | [한국어](./README.KR.md) | [简体中文](./README.CN.md)

![License](https://img.shields.io/badge/license-MIT%20core%20%2B%20bundled%20terms-blue)
![Built on Open-LLM-VTuber](https://img.shields.io/badge/built%20on-Open--LLM--VTuber-orange)
![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey)

---

> ### 現況
>
> **Tomoshibi** 建立在 **[Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)** 之上，
> 桌面與網頁介面以上游的 Open-LLM-VTuber-Web 為基底重建。
>
> 所有設定都在應用程式裡完成——首次啟動的 LLM 精靈、角色管理、語音、記憶、
> 主動話題、翻譯、遠端存取。你不需要手動編輯 `conf.yaml`。
>
> **下載 app：** 到 [Releases](https://github.com/weryk153/tomoshibi/releases/latest)（macOS／Windows）。也可以從原始碼執行。

## 最短路徑

**下載 app**（最簡單）

1. 到 [Releases](https://github.com/weryk153/tomoshibi/releases/latest) 下載：Apple Silicon Mac 選 `arm64.dmg`、Intel Mac 選 `x64.dmg`、Windows 選 `setup.exe`
2. 打開 app。第一次會自動下載需要的東西，只需一次，約幾分鐘。被系統擋住的話，看下方的安全性警告說明。
3. 精靈按 **一鍵安裝** → 挑 2D 或 3D 角色 → 開始聊天。

**不裝 app** — 大約 10 分鐘，其中 8 分鐘在等下載。

1. 這個頁面點綠色 **`<> Code`** → **Download ZIP** → 解壓縮
2. 雙擊 `start-companion.command`（macOS）或 `start-companion.bat`（Windows）。
   **那個視窗別關，它就是伺服器。**
3. 瀏覽器會自己開 → 精靈按 **一鍵安裝**（自動裝好 Ollama 和免費的本機模型）→ 挑 2D 或 3D 角色 → 開始聊天。

不想裝 Ollama？精靈也吃 OpenAI／Claude／Gemini 的 API key，貼上就能用。

**已經有 `uv`**

```bash
git clone https://github.com/weryk153/tomoshibi.git && cd tomoshibi
uv run run_server.py          # 首次會自己 uv sync
# 開 http://localhost:12393 → 精靈 → 開聊
```

卡住了，或想知道每個選項差在哪？完整步驟在下面，包含第一次啟動一定會遇到的
macOS／Windows 安全性警告。

---

## 這是什麼？

**Tomoshibi** 讓一個角色 —— 手繪的 Live2D 或全 3D 的 VRM —— 真的能跟你聊天：它記得你、會自己開話題、你說話時會聽，說話時還會自己做表情和動作。

它是把優秀的開源專案 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) 重新打包成**對小白友善**的版本。我們站在它的肩膀上：上游提供穩定的 Live2D + 語音辨識/合成 + LLM 底層，這個 fork 在旁邊補上 VRM（3D），並把它包成「**下載 → 雙擊 → 開聊**」的體驗，並加上長期記憶、主動話題、自然插話語音、角色管理、首次啟動設定精靈，以及五種語言的介面。

> 本專案建構於 Open-LLM-VTuber 之上。完整致謝與各元件授權見 [`NOTICE`](./NOTICE)，原專案文件保留於 [`README.upstream.md`](./README.upstream.md)。

## 功能亮點

- **AI 驅動表情與動作**：每句話由 LLM 挑表情和動作，還會決定強弱（淺笑或大笑），Live2D 與 VRM 都支援。
- **可設定表達語言**：每個角色可設定回覆語言（日文、英文⋯）。語音用的語言不同時，會先翻譯再唸。
- **長期記憶**：它會記得你是誰、你在忙什麼，並隨時間越來越了解你。每個角色有一份「核心記憶」注入人設；每輪結束後由 LLM 決定哪些值得存下來。更新即時生效，不用重啟。記憶上限可調。
- **主動話題**：沉默一段時間後它會自己開話題。可選擇抓最新的 AI／科技／動漫／遊戲新聞來聊（純標準函式庫，**不需要 API key**）。
- **自然插話語音對話**：隨時都能開口，不必等麥克風，也能像真人對話一樣中途打斷它。
- **角色管理**：建立／編輯／切換／刪除角色 — 名稱＋人設＋Live2D 或 VRM 模型＋語音＋各自獨立的記憶。
- **2D 與 3D 角色都支援**：Live2D 與 VRM（以 glTF 為基礎的 3D）並存。VRM 角色有口型、表情、自動眨眼、視線跟隨、`.vrma` 動作片段，以及拖曳與滾輪調整構圖。把資料夾放進 `vrm-models/` 就會自動登記。
- **首次啟動設定精靈**：貼上 API key（OpenAI／Claude／Gemini）或選本地 Ollama 模型，存檔前會先做一次測試呼叫。
- **LLM 設定分頁**：貼上 API key，或選擇／手動填入一個 Ollama 模型（本地模型，或透過 Ollama 提供的雲端模型）。
- **效能預設**：輕量／標準／高效能三檔，一鍵搭配好 ASR/TTS 引擎＋記憶整理頻率＋模型常駐。
- **跨語言翻譯**：可選的字幕／語音翻譯（預設關閉）。
- **開箱即用**：內建範例 Live2D 模型＋一個 CC0 授權的 VRM 角色＋免費雲端語音（edge-tts）＋自動下載的語音辨識模型（約 1GB，僅在第一次啟動時下載一次、需數分鐘），你只要插上一個 LLM。
- **五種語言介面**：English、繁體中文、简体中文、日本語、한국어。

## 截圖

![Tomoshibi 實際運作畫面](assets/tomoshibi-hero.png)

*Tomoshibi 在桌面上運作，畫面是隨附的 `Sendagaya_Shino` VRM 角色。Live2D 角色的用法完全相同 — 在角色設定裡挑就好。*

## 快速開始（下載 → 雙擊 → 開聊）

最簡單的路徑，**完全不用終端機。**

> **開始前先準備好：你需要一顆 AI「大腦」（LLM）。**
> Tomoshibi 是**身體和臉** — 角色外型、聲音、記憶都有了。但真正會思考、會講話的**大腦**，是一個另外的 AI，要由**你**來提供。你會在首次啟動精靈裡設定它。選項由簡到繁：
> - **（推薦 — 免費、私密、跑在你自己的電腦上）透過 Ollama 用本地模型。** 設定精靈按一下就會裝好免費的 **[Ollama](https://ollama.com)** app 和一個小模型（`qwen2.5:3b`，約 1.9 GB），不用打指令。Tomoshibi 的預設本來就指向它，所以直接就能用 — **不用帳號、不用 API key、零費用、可離線、而且你的對話永遠不會離開你的電腦。** 一般 8–16 GB 的筆電就跑得動。（想要更聰明的回覆、記憶體也夠？拉一個更大的模型，例如 `qwen2.5:7b`，再到設定裡選它。）
> - **（選用 — 電腦較弱時品質更好）Ollama Cloud 免費方案。** Ollama 可以在*它的*伺服器上免費跑一個更大的模型（有額度限制）。需要一個免費帳號 — 見下方**方案 B**；你必須先 `ollama pull` 那個雲端模型。
> - **（選用 — 免費中品質最好）免費的雲端 API key。** Google AI Studio（Gemini）、Cerebras 或 Groq 提供免費 key（免綁信用卡）。免費選項中品質最好，但需要帳號 + key，而且你的對話會送到該供應商。見**方案 C**。
> - **（如果你本來就有付費的）雲端 API key**：來自 OpenAI／Claude／Gemini — 頂級品質，一次聊天幾分錢。見**方案 D**。

1. **取得程式。** 在 repo 主頁點綠色 **`<> Code`** 按鈕 → **Download ZIP**，然後解壓縮（例如解到桌面）。_（習慣用 git 的話 `git clone` 也可以。）_
2. **雙擊資料夾裡的啟動器**：
   - **macOS：** `start-companion.command`
   - **Windows：** `start-companion.bat`
   - 第一次啟動會自動安裝所有東西（先 `uv`，再相依套件），可能要幾分鐘。**那個視窗別關，它就是伺服器本體。**
3. 瀏覽器會自動開到 **http://localhost:12393**。第一次會出現**設定精靈**：**貼上 API key**（OpenAI／Claude／Gemini），**或**選一個本地 **Ollama 模型**。精靈會先測試再存檔。

   ![Tomoshibi 首次啟動設定精靈](assets/tomoshibi-setup.png)

   *首次啟動的設定精靈，在這裡接上你的 AI「大腦」。*

4. **重啟一次，新的大腦才會接上。** 請**把步驟 2 那個啟動器／終端機視窗關掉**結束它（這會停掉伺服器），再**重新雙擊一次啟動器**，讓新的 LLM 接上。（app 裡也會提示，LLM 的變更「會在重啟之後生效 — 或切換一次角色之後生效」。）接著就能開始聊天；點一下頁面以解鎖音訊。

> **macOS Gatekeeper（僅第一次）：** 可能會說「無法驗證」這個 app。這對未簽章的開源 app 是正常的。先按 **完成**，再到 **系統設定 → 隱私權與安全性** 按 **強制打開**。app 和 `start-companion.command` 都一樣。舊版 macOS 也可以按右鍵 → **打開**。（我們不提供簽章／公證版本 — 這是免費版。）

> **Windows SmartScreen（僅第一次）：** 雙擊時可能跳出藍色的「**Windows 已保護您的電腦**」視窗。這對未簽章的開源 app 是正常的。請點 **其他資訊** → **仍要執行**。允許一次之後就不會再問了。

開箱使用內建的 **mao** 範例 Live2D 模型（首次啟動精靈也會讓你改用內建的 3D 角色）與 **edge-tts**（免費雲端語音，不需顯卡）。第一次啟動也會自動下載一個語音辨識模型 —— 它大約 **1GB**，所以**第一次啟動會做一次性的下載＋解壓，可能要好幾分鐘**。這段期間啟動器視窗看起來像卡住了，其實沒有，**請別關掉、讓它跑完**；這只會發生一次。

### 習慣用終端機？（進階）

大多數人用上面的 **Download ZIP** 路徑就好。如果你熟悉終端機，也可以改用 clone 取得專案。需要 **Python ≥ 3.10、< 3.13** 與 [`uv`](https://github.com/astral-sh/uv)。

```bash
git clone https://github.com/weryk153/tomoshibi.git && cd tomoshibi
uv sync                  # 安裝相依套件
uv run run_server.py     # 啟動伺服器
# 開 http://localhost:12393  → 設定精靈 → 開聊
```

### 桌面版（自行建置）

需要 Node 22 與 pnpm。安裝檔已內建後端，不用另外裝 Python 或 `uv`。

```bash
pnpm --dir frontend-src install
pnpm --dir frontend-src run build:mac   # Windows 上用 build:win，產物在 frontend-src/release/
```

第一次開啟會下載 Python、相依套件（約 500MB）與語音模型（約 1GB），只需一次。12393 已有伺服器在跑時，app 會直接沿用。

## 跑起來之後

| 想做什麼 | 去哪 |
|---|---|
| 換成 3D 角色 | 設定 → 角色 → 編輯 → 外觀 |
| 加自己的模型 | 丟進 `live2d-models/` 或 `vrm-models/`，見下方教學 |
| 換一個聲音 | 設定 → 角色 → 編輯 → 參考音（需要 GPT-SoVITS） |
| 從手機用 | 見下方 Tailscale 教學 |
| 讓它主動找你聊 | 設定 → 主動發言 |
| 換它說話的語言 | 設定 → 角色 → 編輯 → 回覆語言 |

---

## 開啟、關閉、開機自動啟動

**怎麼開（啟動「主機」）：**

- **Windows：** 雙擊 **`start-companion.bat`**
- **macOS：** 雙擊 **`start-companion.command`** —— 第一次系統可能會擋：按 **完成**，再到 **系統設定 → 隱私權與安全性 → 強制打開**；之後正常雙擊就行。

會跳出一個黑色命令視窗 —— **那個視窗就是伺服器，聊天期間要一直開著。** 等它準備好，會自己用瀏覽器打開 app（`http://localhost:12393`）。可以這樣想：**命令視窗是引擎，瀏覽器分頁只是畫面。**

> 僅限第一次啟動：會下載約 1GB 的語音模型、要等幾分鐘，視窗看起來像卡住其實沒有 —— 讓它開著跑完即可。

**怎麼關：**

- **關掉那個黑色命令視窗**（或在裡面按 **Ctrl + C**），角色就完全停止。
- 只關**瀏覽器分頁**只是隱藏畫面，伺服器還在跑；要真的停掉請關命令視窗。
- 若你裝了 **Ollama** 跑本地大腦，它會在背景持續執行。閒置時很省，可以不管；想關就從工作列（Windows）／選單列（macOS）的圖示 Quit。

**之後要再開：** 再執行同一個啟動器即可（它也是你的日常啟動器）。

**讓它在電腦開機時自動啟動（選配）：**

- **Windows**
  1. 對 **`start-companion.bat`** 按右鍵 → **建立捷徑**。
  2. 按 **Win + R**，輸入 **`shell:startup`**，按 **Enter** —— 會打開「啟動」資料夾。
  3. 把捷徑拖進那個資料夾。以後每次登入都會自動開啟。*（要取消：把該捷徑從資料夾刪掉。）*

- **macOS**
  1. 打開 **系統設定 → 一般 → 登入項目與擴充功能**。
  2. 在 **登入時開啟** 下按 **+**，選 **`start-companion.command`**（或把檔案拖進清單）。
  *（要取消：選取它後按 **−**。）*

兩種方式都會在登入時自動跳出命令視窗（接著是瀏覽器）。提醒：每次開機會跳出一個終端機視窗是正常的，那就是引擎在啟動。若你用本地 Ollama 大腦，Ollama 裝好後本來就會開機自啟，所以整套會自己起來。

## LLM 設定（必做）

你需要**擇一**：雲端 LLM 的 API key，**或**一個本地 LLM。聊天用便宜的模型就很夠，不需要旗艦級。

#### 方案 A — 本地 Ollama（推薦：免費、私密、不用帳號）
在設定精靈按 **一鍵安裝**，會自動裝好 [Ollama](https://ollama.com/download)、下載 `qwen2.5:3b`（約 1.9 GB）並切換過去 —— 不用打指令、不用重啟、不用 API key、不用帳號、零雲端費用、完全離線，而且你的對話都留在你的電腦上。一般 8–16 GB 的筆電就跑得很順。想要更聰明的回覆，可以拉一個更大的模型（例如 `qwen2.5:7b`），再到 LLM 設定分頁裡選它。

#### 方案 B — 透過 Ollama 用雲端模型（免費帳號；電腦較弱時很適合）
Ollama 可以在它自己的伺服器上跑一個*更大的*模型，所以慢的電腦也能得到不錯的回覆。免費方案，但需要一個帳號、而且你必須先把模型拉下來：
1. 從 [ollama.com/download](https://ollama.com/download) 安裝 Ollama（v0.12+）。
2. 到 [ollama.com](https://ollama.com) 開一個免費帳號，然後在終端機執行 `ollama signin`。
3. **執行 `ollama pull gpt-oss:20b-cloud` —— 必須先拉下來才能用。**（只在設定裡填名字是不夠的。）
4. 在 LLM 設定分頁選 Ollama，把模型設成 `gpt-oss:20b-cloud`。

`gpt-oss:20b-cloud` 是最適合免費額度的輕量模型；`qwen3.5:cloud` 或 `minimax-m3:cloud` 更強，但會更快用掉免費額度。

> **誠實說明「免費」：** 完全 $0、免綁信用卡，只要一個免費帳號 —— 但屬於「輕量使用」等級：一次只能跑一個雲端模型，session 額度每約 5 小時重置一次、外加每週額度，而且 Ollama 沒有公布確切數字，所以聊太多可能會碰到額度上限、要等重置。運算跑在 **Ollama 的伺服器上**，所以不要傳你想完全保密的內容。雲端模型還在 preview 階段 —— **依賴它之前，先確認它真的能回一次。**

#### 方案 C — 免費的雲端 API key（Gemini／Cerebras／Groq）
免費選項中聊天品質最好。開一個免費帳號（免綁信用卡），建立一把 API key，到 LLM 設定分頁貼上 key 並填對應的 base URL：
- **Google AI Studio（Gemini）：** `https://generativelanguage.googleapis.com/v1beta/openai/` —— 免費額度大方；注意 Google 可能會用免費方案的對話來改進它的產品。
- **Cerebras：** `https://api.cerebras.ai/v1` —— 很快，每天約 1M token 免費（免費方案的 context window 較短）。
- **Groq：** `https://api.groq.com/openai/v1` —— 很快，有每日 token 上限。

請用各供應商文件裡目前可用的模型名。你的對話會送到該供應商，而且免費方案有速率限制。

#### 方案 D — 付費的雲端 API key（OpenAI／Claude／Gemini）
如果你本來就有付費的，把 key 貼進精靈即可。品質最高；用小模型通常一次聊天只要幾分錢。

### ⚠️ 思考型（reasoning）模型要把推理關掉才能用

像 **`glm-4.7:cloud`** 這類思考型模型，會把答案放在另一個 `reasoning` 欄位，而一般的 `content` 欄位是**空的**。這個 app 只讀 `content`，所以思考型模型會顯示成**空白回覆** — 沒有文字可念，**語音也不會出聲**。

**建議：** 選一個一般（非思考型）的對話模型。小而快的模型反而讓對話更自然、延遲更低。

**如果你還是想用：** 多數端點可以把推理關掉，關掉之後它就跟一般對話模型一樣。在 `conf.yaml` 的 LLM 區塊加上 `extra_body`：

```yaml
extra_body:
  reasoning_effort: 'none'
```

參數名各家不同，查你的端點文件。以 LM Studio 搭 `qwen3.5` 實測，只有 `reasoning_effort` 有效；`chat_template_kwargs.enable_thinking`、prompt 前加 `/no_think`、`reasoning.enabled` 三種寫法都被靜默忽略。關掉推理同時解掉一個很大的延遲問題：不關的話那個模型會花數千字推理才講出一句話。

## 其他設定

- **記憶**：預設開啟，每個角色記憶獨立存在 `chat_history/<conf_uid>/core_memory.md`，每輪由 LLM 決定要存什麼。記憶上限可在設定調整。
- **角色**：在 app 內建立／編輯／切換／刪除，每個角色有獨立的名稱、人設、角色模型（Live2D **或** VRM）、語音與記憶。要加自己的模型，把資料夾放進 `live2d-models/` 或 `vrm-models/` 再打開角色設定，app 會自己找到並登記。版控裡只有隨附的三個 Live2D 官方範例，你放進去的其他模型留在本機，`model_dict.json` 也是。
  - **想要更多角色（選用）**：為了授權安全，Tomoshibi 只內建授權允許再散布的資源：**3 個免費的 Live2D 原創角色**（`mao_pro`、`haru`、`hiyori`），以及**一個 CC0 的 VRM 角色**（`Sendagaya_Shino`，動作片段為 MIT，見 `vrm-models/Sendagaya_Shino/NOTICE.md`）。想要更多 — 包含男管家角色 **Natori（名取）**？你可以自己到官方頁面下載免費的官方 Live2D 範例模型再放進來。請從 **[Live2D 範例模型頁面](https://www.live2d.com/en/learn/sample/)** 依 Live2D 自己的授權下載 — 我們不代為散布。作法見 [`docs/add-live2d-character.md`](docs/add-live2d-character.md)。
- **效能預設**：輕量／標準／高效能，一鍵搭好引擎、整理頻率與模型常駐。
- **主動話題與新聞**：可用 `scripts/news_topics.py`（純標準函式庫、不需 key）定時更新話題。
- **翻譯**：可選的跨語言字幕／語音翻譯，預設關閉。
- **語音**：預設 edge-tts（免費、不需硬體）；要高品質本地／自訂語音可接 GPT-SoVITS（需顯卡或 Apple Silicon）。克隆真人聲音的法律責任由你自負。選 `fun_asr`、`coqui_tts` 或 `silero_vad` 要另外裝 PyTorch：`uv sync --extra torch`。

## 疑難排解

**App 打不開／黑色視窗一開就關。**
多半是改了某個設定／引擎、舊版救不回來。抓**最新版**即可（新版就算帶著舊設定也開得起來）。不想更新的話：打開 app 資料夾的 `conf.yaml`，找到 `asr_model: 'faster_whisper'` 改成 `asr_model: 'sherpa_onnx_asr'`，存檔重開。（別還原 `conf.yaml.backup`，裡面是同一個壞設定。）

**能回文字但沒聲音。**
更新到最新版（內含 Windows 需要的音訊工具），並再跑一次啟動器讓相依更新。如果你把語音（TTS）引擎切成 GPT-SoVITS，那需要另外跑一個服務 —— 到 設定 → 效能 切回 **Edge TTS** 用免費內建語音。

**第一次開，瀏覽器顯示「無法連上這個網站／拒絕連線」。**
伺服器還在啟動 —— 第一次會下載約 1GB 語音模型、要等幾分鐘。讓黑色視窗開著，等它印出在執行了，再重新整理 `http://localhost:12393`。最新版會等伺服器準備好才自動開瀏覽器。

**Windows：「Windows 已保護您的電腦」（SmartScreen），或按了沒反應。**
按 **其他資訊 → 仍要執行** —— 這是啟動器、不是病毒（只是沒簽章）。若防毒擋掉了一次性的 `uv` 安裝，把這個 app 加進允許清單再跑一次，或到 <https://docs.astral.sh/uv/getting-started/installation/> 手動裝 `uv` 後重試。

**macOS：「無法打開」或「Apple 無法驗證」。**
按 **完成**，再到 **系統設定 → 隱私權與安全性 → 強制打開**。只有第一次需要。（舊版 macOS 也可以按右鍵 → **打開**。）

**開得起來但都不回覆／顯示 AI 大腦尚未設定。**
你還沒設定 LLM。打開設定精靈（或 設定 → 模型）：貼一個 API 金鑰（OpenAI / Claude / Gemini），或選一個本地 Ollama 模型。走本地路線要確認 **Ollama app 已安裝並在執行**、而且模型已下載。

**用 Claude 時網路搜尋／工具沒作用。**
設定精靈把 Claude 接到一個相容端點、不會把工具傳過去，所以對 Claude 來說網路搜尋／工具（那個實驗性開關）可能沒效果。要用工具請改用支援工具呼叫的模型，例如 GPT-4o 或 Gemini，或夠強的本地模型。（用 Claude 純聊天是正常的。）

---

## 教學

- [從手機／平板遠端使用（Tailscale）](docs/remote-access-tailscale.md) — 即使不在家，也能從別的裝置開啟你的虛擬角色。
- [用 GPT-SoVITS 自訂聲音](docs/custom-voice-gpt-sovits.md) — 讓角色用克隆或自訂的聲音說話。
- [自己加 Live2D 角色](docs/add-live2d-character.md) — 把模型放進來並切換使用。
- [自己加 VRM（3D）角色](docs/add-vrm-character.md) — 目錄結構、表情與動作對應、相機構圖。
- [場景管理](docs/scene-management.md)・[舞台特效](docs/stage-effects.md)・[介面功能](docs/ui-features.md) — 背景、登場演出，以及各個面板在做什麼。
- [自己加 VRM（3D）角色](docs/add-vrm-character.md) — 目錄結構、表情與動作對應、相機構圖。
- [場景管理](docs/scene-management.md)・[舞台特效](docs/stage-effects.md)・[介面功能](docs/ui-features.md) — 背景、登場演出，以及各個面板在做什麼。

## 致謝與授權

沒有上游就沒有這個專案，也請去 **star 並支持 [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)**。

- **上游：** [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) — 其伺服器端程式碼為 MIT，Copyright (c) 2025 Yi-Ting Chiu。
- **Tomoshibi 自己新增的部分**（長期記憶、主動開口、群組對話、舞台演出、以及上述全部的應用程式內設定介面、五語言 UI）— MIT。
- **Tomoshibi 自己的變更**（桌面／網頁前端改以上游 Open-LLM-VTuber-Web 重建、換品牌、五語言介面）— MIT。
- **內建前端：** `frontend/` 裡的編譯後網頁是 Open-LLM-VTuber-Web 前端，採 **Open-LLM-VTuber License 1.0**（Apache-2.0 + 額外條款）。免費、非商業的使用與再散布是被允許的；商業改名、付費託管／SaaS、或內嵌進付費產品，則需向 Open-LLM-VTuber 團隊另取商業授權。本 fork 免費且非商業，符合該授權允許的範圍。見 [`NOTICE`](./NOTICE)。
- **Live2D Cubism 與內建範例模型：** 內建的 **mao_pro** / **haru** / **hiyori** 為 Live2D Inc. 範例資料，依 **Live2D 無償提供材料授權**使用（見 [`LICENSE-Live2D.md`](./LICENSE-Live2D.md)），必須保留致謝句：
  > This content uses sample data owned and copyrighted by Live2D Inc.

  它們以**未修改**形式作為免費預設附帶。**任何付費／商用版本都必須替換**成你自己的 CC0／已授權／委託製作的模型。
- **其他元件**（各授權見 [`NOTICE`](./NOTICE)）：GPT-SoVITS（MIT，選用 TTS）、sherpa-onnx（Apache-2.0，ASR 引擎；SenseVoice 模型另有授權，或改用 Whisper）、Silero VAD（MIT）、edge-tts（使用微軟線上語音服務）、DeepLX（非官方 DeepL 端點，正式環境請改用官方 DeepL API）。

**請勿散布有版權的角色、美術、語音或訓練過的語音模型。** 本 repo 只附中性預設，其餘自己帶。

### License

本 fork 自己寫的程式碼以 **MIT 授權**釋出，建構於 Open-LLM-VTuber 同為 MIT 授權的伺服器端程式碼之上（Copyright (c) 2025 Yi-Ting Chiu）。但**整個專案並非單純的 MIT**：`frontend/` 裡內建的編譯後網頁前端採 **Open-LLM-VTuber License 1.0**（Apache-2.0 + 額外條款），而內建的 Live2D 範例模型另有其 Live2D 授權條款。完整且準確的內容見 [`LICENSE`](./LICENSE)、[`NOTICE`](./NOTICE) 與 [`LICENSE-Live2D.md`](./LICENSE-Live2D.md)。

## 支持本專案

這是免費開源專案，沒有付費牆。如果它對你有幫助，歡迎（但絕非必須）小額贊助：

- **Ko-fi:** [ko-fi.com/leonhsueh](https://ko-fi.com/leonhsueh)
- **GitHub Sponsors:** 即將開放

也請支持本專案所建構於的上游 — [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)。

## 貢獻指南

歡迎開 issue 與 pull request。

- bug 與功能想法請開 **Issue**。
- 程式碼變更請開 **Pull Request** 並清楚說明。
- 請**不要**加入有版權的角色、美術、語音或訓練過的語音模型，讓 repo 維持可發布的中性預設狀態。
