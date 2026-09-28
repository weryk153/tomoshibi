# 用 AI Character Engine 的 agent

選了 `character_engine_agent`，整段對話就由
[AI Character Engine](https://github.com/weryk153/ai-character-engine) 驅動：

- 對話、對話歷史、工具呼叫、看圖，都在引擎裡。
- 她對你的感覺（心情、信任、好感、關係階段）會隨互動累積。
- 她記得你講過的事，每段對話各自一份。
- 她有接下來想做的事，也有自己對你們之間的體會。

Tomoshibi 這一側只做轉接：把一輪輸入交給引擎、把引擎吐出來的字接回斷句／動作／
字幕／語音那條管線、把 MCP 工具登記給引擎。程式在
`src/open_llm_vtuber/agent/agents/character_engine_agent.py` 與
`src/open_llm_vtuber/character_engine/factory.py`。

## 需求

- Python 3.11 或 3.12。引擎不支援 3.10。
- `ai-character-engine` 套件。它目前不在 PyPI 上，要從原始碼或 wheel 安裝。
- OpenAI 相容的 LLM 端點（LM Studio、Ollama 的 `/v1`、OpenAI 相容 API）。對話由引擎
  直接呼叫模型，所以 `claude_llm` 這類不相容的 provider 不能用；選了會在啟動時
  說明原因。

## 安裝

建一個 3.12 的環境，把引擎裝進去。用另一個資料夾名稱可以不動原本的 `.venv`：

```sh
UV_PROJECT_ENVIRONMENT=.venv-engine uv sync --python 3.12
uv pip install --python .venv-engine/bin/python -e ../ai-character-engine
```

啟動時用這個環境：

```sh
.venv-engine/bin/python run_server.py
```

`uv run` 預設用的是 `.venv`，不是這個環境；而 `uv sync` 會移除 lock 檔裡沒有的套件，
引擎不在 lock 檔裡。所以用上面這種直接指定直譯器的方式啟動，更新依賴後要重裝引擎。

## 啟用

在 `conf.yaml`（或角色的 yaml）裡改一行：

```yaml
agent_config:
  conversation_agent_choice: 'character_engine_agent'
```

模型、MCP、斷句這些設定沿用 `agent_settings.basic_memory_agent`，不用另外填。要改回來
就把這一行改回 `basic_memory_agent`。

引擎沒裝好時 App 照常開啟，log 會寫明原因與做法，聊天畫面會提示去設定頁。

## 調整節奏

每一種背景工作都是一次額外的 LLM 呼叫，跟對話用同一顆模型。她在回話時背景工作
會讓路；一輪講完後先讀這一輪的情緒，其餘的一次一個。預設值是在 M4 16GB、
`qwen/qwen3.5-9b` 上量出來的；機器比較慢、或覺得回覆變慢時把數字調大，`0` 是停用。

```yaml
agent_settings:
  character_engine_agent:
    emotion_every: 1      # 每輪分析對方的情緒；決定她下一句的心情
    memory_every: 2       # 每 2 輪擷取一次記憶
    summary_every: 0      # 摘要，預設停用
    reflection_every: 6   # 每 6 輪反思一次
    goal_every: 4         # 每 4 輪產生一次目標
    timeout_seconds: 60
    max_rebase_turns: 3   # 背景結果落後幾輪以內仍然採用（記憶不受此限）
    goal_max_age_days: 7  # 超過幾天沒更新的目標不再寫進提示
```

## 資料放在哪裡

```
chat_history/<conf_uid>/engine/state.json       心情、信任、好感、關係階段
chat_history/<conf_uid>/engine/memory.jsonl     她記得的事（每段對話各自一份）
chat_history/<conf_uid>/engine/goals.jsonl      目標
chat_history/<conf_uid>/engine/cognition.jsonl  體會
```

狀態、目標、體會屬於角色，所有對話共用；記憶跟著對話走。要讓她重新開始，刪掉
`engine/` 資料夾。

對話紀錄仍然由 Tomoshibi 存在 `chat_history/<conf_uid>/<history_uid>.json`。引擎只在
記憶體裡留最近幾段對話；沒看過的對話會從這份紀錄接著講。

`core_memory.md` 與 `self_memory.md` 照舊整理、照舊可以在記憶頁編輯，跟引擎的記憶
並存。差別在送給模型的位置：`basic_memory_agent` 把它們放在系統提示裡，這個 agent
把它們拿出來、一行一行寫進對話的備註。在記憶頁刪掉的那一行不會再被提起，但已經
寫進這段對話備註裡的要等那一輪離開對話才會消失。

## 送給模型的長相

引擎把她此刻的狀態、想起來的事、目標、體會寫成備註，放進對話裡、接在那一輪使用者
的話前面，而且只寫「之前的備註還沒講過的」。備註會留在原處，所以每一輪送出去的
提示都是上一輪的延伸，推論端的快取才用得上。系統提示只有人設與一段「備註怎麼讀」
的說明，狀態怎麼變都不會動到它。

主機的長期記憶每一輪都會被整理一次。放在系統提示裡的話，它一變，推論端就得把
後半段系統提示連同整段對話重讀一遍；寫進備註就只多讀新增的那幾行。

量過的數字（M4 16GB、`qwen/qwen3.5-9b`、LM Studio、GPT-SoVITS，實際伺服器走
WebSocket，第 2–5 輪）：

| | `basic_memory_agent` | `character_engine_agent` |
|---|---|---|
| 第一句語音出來 | 16.5–24.7 秒 | 6.6–10.6 秒 |
| 推論端每輪沿用的 token | 2048 | 4352–5120 |
| 推論端每輪重讀的 token | 2339–2998 | 445–879 |

她也會從備註知道現在的日期與時間。問她幾點時，9B 的模型有一半的機會不呼叫時間
工具而是編一個（實測 6 次裡 3 次）。

## 看圖

引擎的訊息只有文字。鏡頭、螢幕、上傳的圖會先用同一顆模型描述成兩三句話（約 3 秒），
她讀到的是描述；對話裡留的是你說的話，不留圖也不留描述。

## 目前的限制

- 設定頁還沒有對應的 UI，要直接改 yaml。
- 看圖多一次模型呼叫，有圖的那一輪第一句話會晚約 3 秒。
- 模型不支援原生工具呼叫時，`basic_memory_agent` 會改用提示詞模式；這個 agent 沒有
  那條退路。
- 整則回覆被重複護欄丟掉而重生時，引擎那邊會算成兩輪。
- 字幕翻譯和 `core_memory` 的整理也用同一顆模型，它們不在「她回話時讓路」的機制裡。
