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

- Python 3.11 或 3.12（`.python-version` 是 3.12，uv 會自己下載）。
- OpenAI 相容的 LLM 端點（LM Studio、Ollama 的 `/v1`、OpenAI 相容 API）。對話由引擎
  直接呼叫模型，所以 `claude_llm` 這類不相容的 provider 不能用；選了會在啟動時
  說明原因。

## 安裝

引擎是 Tomoshibi 的一般依賴，`uv sync` 就會裝好（從 GitHub 裝，`pyproject.toml` 釘在
一個 commit）。啟動照常：

```sh
uv run run_server.py
```

改引擎本身時，可以暫時換成本機的原始碼：

```sh
uv pip install -e ../ai-character-engine
```

下一次 `uv sync` 會換回 `pyproject.toml` 釘的那一版。

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
    goals_shown: 3  # 她同時放在心上的目標最多幾條（最急的優先）
    thoughts_shown: 2  # 她同時放在心上的想法最多幾條（最新的優先）
    max_history_messages: 80  # 對話最多留幾則給模型
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

她記得對方什麼，由引擎負責，`core_memory.md` 不再使用：

- 記憶頁「對這段對話的記憶」顯示的、編輯的，是引擎的記憶。刪掉或改掉的那一行會從
  她讀到的內容裡拿掉。
- 換成這個 agent 之前累積的 `core_memory.md`，每段對話第一次用到時搬一次，只搬
  主詞是「對方」的那幾行。
- 她會拿到這段對話的全部記憶（預設最多 40 筆），跟最新一句有關的排前面。

她自己說過什麼（喜好、習慣、在做的事）也由引擎記，`self_memory.md` 不再使用：

- 引擎從她的話裡抽出來，整個角色共用、所有對話都看得到，每輪放進備註
  （`you said about yourself`）。頻率是 `self_memory_every`，長期記憶關掉時跟著關。
- 記憶頁「她自己的記憶」顯示的、編輯的，是引擎的這一份。
- 換成這個 agent 之前的 `self_memory.md` 搬一次；舊 `core_memory.md` 裡主詞是她的那
  幾行也搬到這裡。
- 主機那一套記憶整理（每幾輪一次模型呼叫）整個不跑。

她說出口的話也由引擎把關：不重複、不講客服腔、不留只剩標點的碎片、主動開口不只是
應一聲、上一次主動開口問過問題這次就不問。主機原本那幾層過濾對這個 agent 跳過，
不然兩邊各擋一次，主機擋掉的句子引擎不知道。

## 送給模型的長相

引擎把她此刻的狀態、想起來的事、目標、體會寫成備註，放進對話裡、接在那一輪使用者
的話前面，而且只寫「之前的備註還沒講過的」。備註會留在原處，所以每一輪送出去的
提示都是上一輪的延伸，推論端的快取才用得上。系統提示只有人設與一段「備註怎麼讀」
的說明，狀態怎麼變都不會動到它。

`basic_memory_agent` 把長期記憶放在系統提示的中段，而它每一輪都會被整理一次：它一
變，推論端就得把後半段系統提示連同整段對話重讀一遍。寫進備註就只多讀新增的那幾行。

備註的標籤（`emotion`、`memory`、`goal`、`the user seems`、`For the next reply only`）
是引擎的，英文；那是給模型讀的，使用者看不到。記憶、目標、體會的內容用她回話的
語言寫（`player_language`／角色的 `reply_language`）。

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
- 整則回覆被重複護欄丟掉而重生時，引擎那邊會算成兩輪（`basic_memory_agent` 也是）。
- 被護欄丟掉的句子她自己還記得說過（`basic_memory_agent` 也是）。
- 兩個連線同時講話時，引擎一次只跑一輪，後到的要等前一個講完。
- 字幕翻譯和 `core_memory` 的整理也用同一顆模型，它們不在「她回話時讓路」的機制裡。
