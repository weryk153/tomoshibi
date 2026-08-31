# 首次啟動的模型偵測與自動設定 — 設計

## 問題

一個新使用者要讓 Tomoshibi 講出第一句話，現在得：裝推論端 → 下載模型 →
編輯 `conf.yaml` → **知道自己的模型是不是思考型** → 手動解開一段註解。

最後那步是隱形的門檻。樣板裡已經寫著答案：

```yaml
lmstudio_llm:
  # 若你載入的是推理／思考型模型（如 qwen3.5），加上這段關掉它的推理，
  # 否則會是空白回覆且沒有語音。
  # extra_body:
  #   reasoning_effort: 'none'
```

知識早就寫下來了，只是要求使用者自己讀、自己判斷、自己編輯 YAML。不照做的
症狀是「每句話等三分鐘然後沒反應」——看起來像壞掉，不是像設定沒調。

本設計把這三步變成零步。

## 範圍

**做**：偵測本機模型；套用「不設就像壞掉」的必要設定；沒有模型時幫忙下載。

**不做**：sampling 的品味設定（`temperature` / `top_p` / penalty）。那些是品質
判斷，而本專案的規矩是這類事只信 n≥3 全文人讀，不信自動化。

**不做**：碰已設定使用者的設定檔。只在未設定時跑一次。

### 範圍決策紀錄

| 決定 | 選擇 |
|---|---|
| 管到哪一層 | 只管「不設就像壞掉」的 |
| 偵測哪些後端 | LM Studio + Ollama |
| 何時寫入 | 只在未設定時跑一次，不覆蓋既有設定 |
| RAM 偵測用途 | 只決定推薦下載哪顆模型 |
| 平台 | 必須含 Windows |

## 架構

四個單元，各自能獨立理解與測試：

```
model_probe.py       問推論端有哪些模型 → 正規化清單。不決定設定、不寫檔案。
model_profiles.yaml  arch → 偵測不到的必要設定。純資料。
conf_editor（擴充）   巢狀區塊寫入 + 換行符修正
llm_config_route     接線：probe → 選擇 → 套 profile → 驗證 → 寫入
```

### 1. `model_probe.py`

```python
@dataclass(frozen=True)
class DetectedModel:
    id: str                    # 寫進 conf 的模型名
    backend: str               # 'lmstudio' | 'ollama' → 決定寫哪個 conf 區塊
    base_url: str
    arch: str | None           # profile 查表的 key
    is_vlm: bool               # → 視覺輸入開關
    supports_tools: bool       # → use_mcpp 開關
    max_context: int | None
    quantization: str | None   # 只給人看
```

兩個後端的資訊深度不同，正規化在這層做完：

| | LM Studio | Ollama |
|---|---|---|
| 端點 | `/api/v0/models` 一次全拿 | `/api/tags` 列表 + `/api/show` 逐顆 |
| arch | `arch` | `details.family` |
| VLM | `type == "vlm"` | `capabilities` 含 `vision` |
| 工具 | `capabilities` 含 `tool_use` | `capabilities` 含 `tools` |
| context | `max_context_length` | `model_info` 的 context 長度 |

**Ollama 分兩階段**：`/api/show` 要逐顆呼叫，20 顆模型就是 20 次請求。列表時
只列，選定後才問細節。介面統一為 `list_models()` + `describe(model_id)`。

**與 `context_window.py` 的關係**：兩者都打 `/api/v0/models`，但用途不同——
一個是執行期問「載入的 window 多大」（懶惰、快取、有冷卻），一個是設定期問
「有哪些模型」。抽出共用的 `fetch_lmstudio_models(base_url)`，`context_window`
的快取與冷卻語意原封不動。避免的是「兩個地方各自知道端點形狀」，不是硬合併。

### 2. `model_profiles.yaml`

**界線**：profile 只放**偵測不到**的怪癖。

| 來源 | 內容 |
|---|---|
| `DetectedModel` 直接用 | `is_vlm`、`supports_tools`、`max_context` |
| profile 查表 | API 不會告訴你、但不設就會壞的東西 |

因此 profile 目前只有一類內容：`extra_body` 的項目。

**注意這裡有個容易誤讀的地方**：`extra_body` 底下同時住著必要設定
（`reasoning_effort`）與 sampling 旋鈕（`top_p` / `top_k` / `presence_penalty`）。
Profile **只准放前者**。分界不靠欄位名，靠 `note` 寫不寫得出來：能說出「不設會
出現什麼故障」的才算必要設定；只能說「這樣比較好」的是品味，不收。


```yaml
profiles:
  - match_arch: ['qwen35', 'qwen3']   # 兩個後端的 arch 詞彙不同，故為清單
    match_backend: 'lmstudio'          # 可選
    extra_body:
      reasoning_effort: 'none'
    note: |
      不關思考模式會超過 60 秒 timeout，然後靜默 fallback 回原文／空白。
      症狀是「每句話等三分鐘然後沒反應」，看起來像壞掉而不是慢。

recommended_models:      # RAM → 下載建議
  # 型號待實測填入
fallback: 'qwen2.5:3b'   # RAM 測不到時；沿用現有的 RECOMMENDED_OLLAMA_MODEL
```

**`match_arch` 是清單**，因為 LM Studio 回 `qwen35`、Ollama 的 `details.family`
用另一套寫法。與其硬做一套會一直漏的正規化對照，不如讓每條 profile 自己宣告
它認得哪些字串。

**`note` 必填，載入時檢查**。這是防腐設計：範圍是「不設就像壞掉」，每條都必須
說得出它防的是哪種壞掉；寫不出來的就不該進這個檔。它同時在 wizard 上兌現，
讓使用者知道為什麼有東西被設了。

**比對規則**：`match_arch` 任一字串命中即算命中；`match_backend` 省略時代表
不限後端。多條同時命中時**取檔案中的第一條**並記一行 warning——重疊代表資料檔
該整理，不該靠隱性的優先序默默解決。

**查不到就什麼都不寫**，不猜、不套通用建議值。

**初始只有一條**（實測過的 Qwen3.5）。不預填 Llama / Mistral / Gemma——沒有
證據而憑印象填，正是本專案反覆踩過的坑。一條有據勝過十條臆測；其餘由開源後
的回報長大。

### 3. `conf_editor` 擴充

**`upsert_nested_block(lines, start, end, key, mapping)`**

`sub_block_extent` 已能定位既有的 `extra_body:`，只缺「不存在時建立」。
其 regex 為 `^(\s*)key:\s*(#.*)?$`，樣板那段 `# extra_body:` 的 `#` 卡在空白與
key 之間，不會誤中——安全。

插入時不動樣板註解，與 `conf_editor` 既有哲學一致（它連 `True`／`null` 的寫法
都原樣保留）。結果是檔案同時有註解範例與實際區塊，稍囉嗦但誠實。

**`newline=""`（Windows 前置）**

`read_conf_lines` 與 `write_conf` / `write_conf_document` 目前都用預設的
universal newlines：

| conf.yaml 原本 | Windows 存檔後 |
|---|---|
| CRLF | CRLF（剛好對上） |
| **LF**（git `autocrlf=input`、或從 mac 複製） | **整份變 CRLF** |

第二種情況下改一個欄位會產生整份 diff，違反 `conf_editor` 自己立的規矩。三處
加 `newline=""` 關掉翻譯，位元組原樣進出。

這是既有缺陷，但屬本功能前置：自動設定第一次寫入就會踩到。

### 4. `write_provider_config(provider, values)`

```
provider: 'lmstudio_llm' | 'ollama_llm' | 'openai_compatible_llm'
values:   base_url / model / llm_api_key / extra_body
副作用:   把 llm_provider 指向該 provider
```

取代 `_write_openai_block`。後者固定寫 `openai_compatible_llm` 並強制切換到
它——偵測到 LM Studio 卻寫進另一個區塊，會把使用者導向一個沒有 `extra_body`
的地方，**正好製造本功能想避免的問題**。一般化是前置，不是附帶。

### 5. RAM 偵測

用 `psutil.virtual_memory().total`，新增依賴。

不走 stdlib 三分支：Windows 那條要 `ctypes` 手刻 `GlobalMemoryStatusEx` 的
struct，而本機無法測、CI 也不會測。在無法驗證的前提下寫 ctypes 不負責任。

測不到 → 用 `fallback`。

## 流程

```
後端就緒 AND 未設定（既有顯示條件，不動）
  ↓
並行 probe LM Studio(1234) + Ollama(11434)
  ├ 有模型 ─────────→ 合併清單（標 backend / VLM / 工具支援）
  ├ Ollama 在跑但空 ─→ RAM 分層推薦 + 一鍵 ollama-pull（既有路由，已實作）
  ├ 只有 LM Studio 且空 → 引導去其內建模型瀏覽器（無法代下，誠實說明）
  └ 都沒在跑 ───────→ 說明要先裝哪一個
        ↓
   使用者選一顆 → (Ollama) /api/show 補細節 → 套 profile
        ↓
   顯示「將套用什麼、為什麼」← profile 的 note 在此兌現
        ↓
   _validate_combo() 打真的 API → write_provider_config()
```

**手動填表永遠保留**。偵測是加速不是取代，呼應 wizard 現有的哲學：「寧可漏
顯示，也不要在後端有問題時擋住整個畫面」。

## 錯誤處理

全部 fail-soft，一個例外：

| 失敗 | 行為 |
|---|---|
| probe 掛掉 | 當作該 backend 沒模型，不擋畫面 |
| profile 查不到 | 不寫 `extra_body`，設定照樣完成 |
| RAM 測不到 | 用 fallback 推薦值 |
| **`_validate_combo()` 失敗** | **擋住儲存**（既有行為） |

最後一條該保留：讓使用者以為設好了但其實不能用，比明確報錯更糟。

## 測試

1. `model_probe` — 餵兩種假 JSON，斷言正規化結果一致。不打網路。
2. `model_profiles` — 比對規則、`note` 必填檢查、查不到回空
3. `upsert_nested_block` — 已有 `extra_body`／完全沒有／只有註解版
4. 換行符往返 — LF 進 LF 出、CRLF 進 CRLF 出
5. `write_provider_config` — 三個 provider 各寫對區塊 + provider 切換
6. RAM 分層 — 餵假的 total bytes
7. Windows CI runner 跑全套

第 4 條有附帶好處：加了 `newline=""` 之後換行行為不再依賴平台，Linux CI 就
釘得住它。等於把一個「只能在 Windows 踩到」的 bug 變成到處都測得到。Windows
runner 是保險，不是唯一防線。

## 明確排除

- **`llm_translate.model` 耦合**：樣板的 `translate_provider` 預設是 `deeplx`，
  所以這條在 first-run 路徑上不會觸發。「換模型忘了改兩處」的風險對既有使用者
  是真的，但該用一致性測試擋，不屬本功能。
- **RAM → context 長度**：LM Studio 的 context 是載入時的 GUI 設定，無外部 API
  可寫（本專案只讀得到）。做成建議文字會與事後偵測到的實際值不一致。
- **代裝推論端**：要裝 app、要權限，超出一個 Python server 該碰的範圍。

## 未定

`recommended_models` 的 RAM 分層型號尚未填入——需要在不同 RAM 的機器上實測。

**這不擋實作**：分層表為空時，RAM 偵測的結果不影響任何事，一律推薦
`fallback: 'qwen2.5:3b'`（即現行的 `RECOMMENDED_OLLAMA_MODEL`，行為與今天相同）。
分層是之後往資料檔加幾行的事，不需要改程式。填入未經實測的型號才是要避免的。
