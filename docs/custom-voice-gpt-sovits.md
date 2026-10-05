# Custom / cloned voice (GPT-SoVITS)

**Scenario:** You want your character to speak in a **custom or cloned voice** (for
example a specific character's voice) instead of the default free **edge-tts** voice.
Tomoshibi can do this through **GPT-SoVITS**, a separate voice-synthesis service that you
run yourself.

> **Easiest way:** on macOS (Apple Silicon) or 64-bit Windows, Tomoshibi installs GPT-SoVITS
> for you — it's offered at first launch, and in **Settings → Models** under
> **Text-to-speech engine (TTS)** while it isn't installed yet. That sets up everything
> below with a default voice, running on the CPU. Read on to run GPT-SoVITS yourself, use a
> GPU, or load your own voice pack.

## Prerequisites

- **A machine with a GPU or Apple Silicon.** GPT-SoVITS is a neural TTS engine; it needs
  roughly **6 GB of VRAM** on an NVIDIA GPU, or an Apple Silicon Mac. It can be the same
  computer as Tomoshibi, or another computer on your network.
- **GPT-SoVITS installed by you.** It is **not bundled** with Tomoshibi — you install and
  run it separately. Get it here: <https://github.com/RVC-Boss/GPT-SoVITS>
- GPT-SoVITS exposes an HTTP API, by default on **port `9880`**.

## The most important concept: who holds what

This is the part people get wrong, so read it first. The voice setup is split across
**two** programs:

| Thing | Lives in | Why |
|------|----------|-----|
| **Voice model weights** — the GPT model (`.ckpt`) and the SoVITS model (`.pth`) | **GPT-SoVITS** | They are the actual neural model; GPT-SoVITS is the program that loads and runs them. |
| **Reference audio file + its transcript** | **Tomoshibi** — each character's own file (`characters/<name>.yaml`; the base character's is `conf.yaml`) | Every time it needs speech, Tomoshibi calls GPT-SoVITS and has to tell it *which short reference clip to imitate* and *what that clip says*. So those go in Tomoshibi's config, per character. |

In short: **load the voice-pack weights into GPT-SoVITS; tell Tomoshibi the reference clip
and its transcript.** Tomoshibi is the *client* that asks GPT-SoVITS for audio on each
reply.

## Step-by-step

### 1. Install, start, and load your voice into GPT-SoVITS

1. Install and start the GPT-SoVITS API server (it listens on `:9880` by default).
2. For a **custom voice**, load that voice pack's **weights** into GPT-SoVITS. You do this
   **on the GPT-SoVITS side**, by either:
   - calling its `/set_gpt_weights` (the `.ckpt` GPT model) and `/set_sovits_weights`
     (the `.pth` SoVITS model) endpoints, **or**
   - editing GPT-SoVITS's own `tts_infer.yaml` so it loads those weights at startup.

   (Refer to the GPT-SoVITS docs for the exact endpoint/config details — those belong to
   that project, not to Tomoshibi.)

### 2. In Tomoshibi: tell it where GPT-SoVITS is

Open **Settings → Models** → **Text-to-speech engine (TTS)** and fill
**GPT-SoVITS service URL** (`api_url`). It saves as you type. This one address is shared
by every character. Default is:

```
http://localhost:9880/tts
```

If GPT-SoVITS runs on another computer on your network, use that machine's address
instead of `localhost`, e.g. `http://192.168.1.50:9880/tts`.

### 3. In Tomoshibi: give a character the voice

Which engine and which reference clip are set **per character**. Open
**Settings → Characters**, pick the character from the list, and go to her **Voice**
section:

1. Set **TTS engine** to **GPT-SoVITS** (`gpt_sovits_tts`). The other choice is the
   default **Edge TTS** (`edge_tts`). **Same as the base character** copies the base
   character's current choice.
2. Pick **Reference audio** (`ref_audio_path`) — the short clip whose voice you want
   copied. The list shows the audio files in every folder that `conf.yaml` or a
   character file already points `ref_audio_path` at, plus the clip that the one-click
   install ships. To add a voice, drop its `.wav` into one of those folders. A `.txt`
   with the same name is read as its transcript.
3. Check **Reference transcript** (`prompt_text`) — **word for word**, exactly what is
   said in the clip. Picking a clip with a `.txt` next to it fills this in for you.
4. Set **Reference language** (`prompt_lang`) — the language spoken in the clip.

Then, in her **Language** section, set **Voice language** (`text_lang`) — the language
she actually *speaks*. If it differs from her reply language, Tomoshibi translates each
reply before sending it to TTS, which adds a few seconds per sentence.

Each field saves as you change it, into that character's file, under
`character_config` → `tts_config` (`conf.yaml` for the base character,
`characters/<name>.yaml` for the others). `api_url` is only written to `conf.yaml`;
the other characters use that one. The block looks like this:

```yaml
gpt_sovits_tts:
  api_url: 'http://localhost:9880/tts'   # Settings → Models (shared)
  text_lang: 'ja'                        # Voice language
  ref_audio_path: ''                     # Reference audio
  prompt_lang: 'ja'                      # Reference language
  prompt_text: ''                        # Reference transcript
  text_split_method: 'cut5'              # not in the UI; leave as-is unless you know otherwise
  batch_size: '1'
  media_type: 'wav'
  streaming_mode: 'false'
```

### 4. Apply it

If you changed the character you are talking to, the top of the settings drawer says
some changes haven't taken effect yet — press **Reload**. The service URL works the same
way. For any other character, the new voice is used the next time you switch to her.
No restart needed.

## FAQ / troubleshooting

- **No sound / TTS errors after switching?** Check, in order: (1) GPT-SoVITS is actually
  running and reachable at your `api_url`; (2) the voice weights are loaded in GPT-SoVITS;
  (3) `ref_audio_path` points to a file GPT-SoVITS can read; (4) `prompt_text` is filled
  in and matches the reference clip.
- **Key limitation — `prompt_text` is mandatory.** Leaving it blank is the most common
  cause of failure. GPT-SoVITS needs the reference clip's transcript to clone the voice.
- **Wrong-sounding language?** Make sure `prompt_lang` matches your reference clip and
  `text_lang` matches what you want spoken.
- **GPT-SoVITS on another PC?** Put that PC's IP in `api_url`, and remember
  `ref_audio_path` is resolved **on that PC**, not on the Tomoshibi machine. The
  **Reference audio** list only shows files on the Tomoshibi machine, so for a path that
  only exists on the other PC, edit `ref_audio_path` in the character's file by hand.
- **Want to go back to free voices?** Set that character's TTS engine back to
  **Edge TTS** and press **Reload**.
- **Legal note:** cloning a real person's voice is **your** legal responsibility — only
  use voices you have the right to use.

---

## 繁體中文

**情境：** 你想讓角色用**自訂或克隆的聲音**（例如某個角色的聲音）說話，取代預設免費的
**edge-tts**。Tomoshibi 可以透過 **GPT-SoVITS** 做到——那是一個**你自己另外安裝、自己跑**的
語音合成服務。

> **最簡單的做法：** 在 macOS（Apple Silicon）或 64 位元 Windows 上，Tomoshibi 可以幫你裝
> GPT-SoVITS——首次啟動時會問，也可以在**設定 →「模型」→「語音合成引擎（TTS）」**按「安裝」
> （還沒裝時才會出現）。裝好就有預設聲音，用 CPU 跑。要自己跑 GPT-SoVITS、用 GPU、或換成
> 自己的聲音包，再往下看。

### 前提

- **一台有 GPU 或 Apple Silicon 的機器。** GPT-SoVITS 是神經網路語音引擎，NVIDIA 顯卡大約需要
  **6 GB 顯示記憶體**，或用 Apple Silicon 的 Mac。它可以跟 Tomoshibi 同一台，也可以是同網路的
  另一台電腦。
- **GPT-SoVITS 要你自己裝。** 它**沒有內建**在 Tomoshibi 裡，要另外安裝、另外啟動。
  專案在這：<https://github.com/RVC-Boss/GPT-SoVITS>
- GPT-SoVITS 會開一個 HTTP API，預設在 **連接埠 `9880`**。

### 最重要的觀念：什麼東西放哪邊（最容易搞錯）

這段是最多人弄錯的，先看。聲音設定拆在**兩個**程式裡：

| 東西 | 放在 | 為什麼 |
|------|------|--------|
| **聲線「模型權重」**——GPT 模型（`.ckpt`）與 SoVITS 模型（`.pth`） | **GPT-SoVITS 那邊** | 它們就是真正的神經網路模型，GPT-SoVITS 才是負責載入與運算的程式。 |
| **參考音檔 + 逐字稿** | **Tomoshibi 這邊**——每個角色自己的檔案（`characters/<名稱>.yaml`；底稿角色是 `conf.yaml`） | Tomoshibi 每次要語音時都會去呼叫 GPT-SoVITS，必須告訴它「**模仿哪一段短參考音色**」以及「**那段在講什麼**」，所以這些填在 Tomoshibi 的設定裡，每個角色各自一份。 |

一句話：**聲音包的權重載進 GPT-SoVITS；參考音檔和逐字稿填在 Tomoshibi。** Tomoshibi 是每次回覆時
去跟 GPT-SoVITS 要語音的「客戶端」。

### 操作步驟

1. **安裝、啟動 GPT-SoVITS，並把你的聲音載進去。**
   - 啟動 GPT-SoVITS 的 API 服務（預設監聽 `:9880`）。
   - 要用**自訂聲音**，就把那個聲音包的**權重**載進 GPT-SoVITS——這一步**在 GPT-SoVITS 那邊
     做**：呼叫它的 `/set_gpt_weights`（`.ckpt` GPT 模型）和 `/set_sovits_weights`
     （`.pth` SoVITS 模型），或改它自己的 `tts_infer.yaml` 讓它開機就載入。
     （確切的端點/設定細節請查 GPT-SoVITS 的文件，那是它的範疇，不是 Tomoshibi。）

2. **在 Tomoshibi：告訴它 GPT-SoVITS 在哪。** 打開**設定 →「模型」→「語音合成引擎（TTS）」**，
   填 **「GPT-SoVITS 服務位址」**（`api_url`），改了就存。這個位址所有角色共用。預設是
   `http://localhost:9880/tts`；若 GPT-SoVITS 跑在同網路的另一台機器，把 `localhost` 換成
   那台的位址，例如 `http://192.168.1.50:9880/tts`。

3. **在 Tomoshibi：讓角色用這副嗓子。** 用哪個引擎、哪段參考音是**每個角色各自**設定。
   打開**設定 →「角色」**，左邊選角色，到她的「聲音」區：
   - **「語音合成引擎」**設成 **GPT-SoVITS**（`gpt_sovits_tts`），另一個選項是預設的
     **Edge TTS**（`edge_tts`）。選「跟底稿角色一樣」會把底稿角色現在的選擇存成她自己的。
   - **「參考音檔」**（`ref_audio_path`）選你想被模仿的那段短參考音。清單列的是
     `conf.yaml` 與各角色檔的 `ref_audio_path` 用到的資料夾裡的音檔，加上一鍵安裝附的參考音。
     要加新聲線，把 `.wav` 放進其中一個資料夾；同名的 `.txt` 會當成它的逐字稿。
   - **「參考音逐字稿」**（`prompt_text`）——參考音檔裡**一字不差**講的那句話。選的音檔旁邊有
     同名 `.txt` 的話會自動填好。
   - **「參考音語言」**（`prompt_lang`）——參考音檔講的語言。

   再到她的「語言」區設 **「發聲語言」**（`text_lang`）——她實際要**說出來**的語言。跟回覆語言
   不同時，Tomoshibi 會先把回覆翻譯過再送進 TTS，每句多花數秒。

   每一欄改了就存，寫進那個角色檔案的 `character_config` → `tts_config` 底下（底稿角色是
   `conf.yaml`，其他角色是 `characters/<名稱>.yaml`）。`api_url` 只寫在 `conf.yaml`，其他角色
   共用那一份。區塊長這樣：

   ```yaml
   gpt_sovits_tts:
     api_url: 'http://localhost:9880/tts'   # 設定 →「模型」（共用）
     text_lang: 'ja'                        # 發聲語言
     ref_audio_path: ''                     # 參考音檔
     prompt_lang: 'ja'                      # 參考音語言
     prompt_text: ''                        # 參考音逐字稿
     text_split_method: 'cut5'              # 介面上沒有；不清楚就別動
     batch_size: '1'
     media_type: 'wav'
     streaming_mode: 'false'
   ```

4. **套用。** 改的是正在聊天的角色時，設定抽屜頂端會寫有變更還沒生效，按 **「重新載入」**。
   服務位址也一樣。其他角色下次切換到她時就會用新聲音。不用重啟。

### 常見問題

- **切換後沒聲音／TTS 報錯？** 依序檢查：(1) GPT-SoVITS 真的有在跑、`api_url` 連得到；
  (2) 聲音權重有載進 GPT-SoVITS；(3) `ref_audio_path` 指向 GPT-SoVITS 讀得到的檔；
  (4) `prompt_text` 有填且跟參考音檔一致。
- **關鍵限制——`prompt_text` 必填。** 留空是最常見的失敗原因。
- **語言聽起來不對？** 確認 `prompt_lang` 跟參考音檔一致、`text_lang` 跟你想說的語言一致。
- **GPT-SoVITS 在另一台電腦？** `api_url` 填那台的 IP，並記得 `ref_audio_path` 是在**那台**上
  解析，不是 Tomoshibi 這台。「參考音檔」清單只列 Tomoshibi 這台上的檔案，只存在那台的路徑
  要手改角色檔的 `ref_audio_path`。
- **想換回免費聲音？** 把那個角色的「語音合成引擎」切回 **Edge TTS**，再按「重新載入」。
- **法律提醒：** 克隆真人聲音的法律責任由**你自己**承擔，只用你有權使用的聲音。
