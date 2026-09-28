# 用 AI Character Engine 的 agent

`character_engine_agent` 是 `basic_memory_agent` 加上
[AI Character Engine](https://github.com/weryk153/ai-character-engine) 的背景認知。
對話本身完全沿用原本的 agent；多出來的是每一輪之後，引擎在背景整理：

- 她對你的感覺：心情、信任、好感、關係階段，會隨互動累積。
- 她接下來想做的事：例如你說「畫好了給我看」，她會記著要畫。
- 她注意到的事：對你或你們之間的體會。

這些會接在下一輪你說的話後面送給模型（不會存進對話紀錄）。設計與實測數據見
`docs/superpowers/specs/2026-09-28-character-engine-agent-design.md`。

## 需求

- Python 3.11 或 3.12。引擎不支援 3.10。
- `ai-character-engine` 套件。它目前不在 PyPI 上，要從原始碼或 wheel 安裝。
- OpenAI 相容的 LLM 端點（LM Studio、Ollama、OpenAI 相容 API）。

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

對話的設定沿用 `agent_settings.basic_memory_agent`，不用另外填。要改回來就把這一行
改回 `basic_memory_agent`。

引擎沒裝好時 App 照常開啟，log 會寫明原因與做法，聊天畫面會提示去設定頁。

## 調整節奏

每一種背景工作都是一次額外的 LLM 呼叫。預設值是在 M4 16GB、`qwen/qwen3.5-9b` 上
量出來的；機器比較慢、或覺得回覆變慢時把數字調大，`0` 是停用。

```yaml
agent_settings:
  character_engine_agent:
    emotion_every: 1      # 每輪分析對方的情緒；決定她下一句的心情
    memory_every: 2       # 每 2 輪擷取一次引擎記憶
    summary_every: 0      # 摘要，預設停用
    reflection_every: 6   # 每 6 輪反思一次
    goal_every: 4         # 每 4 輪產生一次目標
    timeout_seconds: 60
    max_rebase_turns: 3   # 背景結果落後幾輪以內仍然採用
    goal_max_age_days: 7  # 超過幾天沒更新的目標不再寫進提示
```

## 資料放在哪裡

```
chat_history/<conf_uid>/engine/state.json       心情、信任、好感、關係階段
chat_history/<conf_uid>/engine/goals.jsonl      目標
chat_history/<conf_uid>/engine/cognition.jsonl  體會
chat_history/<conf_uid>/engine/memory.jsonl     引擎的記憶（這一版不注入提示）
```

狀態、目標、體會屬於角色，所有對話共用。要讓她重新開始，刪掉 `engine/` 資料夾。

`core_memory.md` 與 `self_memory.md` 照舊運作，這個 agent 不碰它們。

## 目前的限制

- 群組對話沒有背景認知，行為與 `basic_memory_agent` 相同。
- 設定頁還沒有對應的 UI，要直接改 yaml。
- 引擎的記憶只累積、不注入。要不要用它取代現有的記憶，得先並排比較準確度。
- 背景工作與對話共用同一顆模型。她在生成回覆時背景工作會讓路，但字幕翻譯和
  `core_memory` 的整理不在這個機制裡。實測數字見規格文件。
- 被打斷的那一輪不會交給引擎。
