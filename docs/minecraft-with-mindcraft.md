# 用 Mindcraft 讓她玩 Minecraft

Tomoshibi 的 Minecraft 模式不直接操作遊戲。她決定「接下來要做什麼」，目前主要在台詞裡寫 `[minecraft_do: 一句英文目標]`，也可以呼叫原生 `minecraft_do` 工具。兩個入口共用同一個佇列：`commands.py` 把認得的目標翻成指令，經 [Mindcraft](https://github.com/mindcraft-bots/mindcraft) 的 MindServer（socket.io）交給機器人執行；認不出的目標回報她重新表達。程式不計算生存下一步，也不在她沒下目標時代替決定。

身體忙著時，新目標只取代尚未送出的步驟，等待新鮮的閒置狀態才送；說話本身不會送指令。斷線、停止模式會清掉未送出的步驟。停止模式只停止派發與追蹤，已在 Mindcraft 執行的動作不會因此被取消。

## 三台機器的配置

| 機器 | 跑什麼 |
|---|---|
| PC（Windows） | Minecraft Java 版、OBS |
| 這台 Mac（M4 16GB） | Tomoshibi、她的 9B（LM Studio :1234）、GPT-SoVITS、**Mindcraft** |
| worker（M1 Pro 16GB，`kuren@comfy-worker`） | Andy-4.2（機器人的腦）、Hy-MT2-7B（翻譯） |

MindServer 只綁 localhost（埠 8080），所以 **Mindcraft 一定要跟 Tomoshibi 跑在同一台 Mac**。

## 一次性準備

### 1. PC：Minecraft

- 買並安裝 Minecraft Java 版。Mindcraft 支援到 1.21.11，建議用 1.21.6。
- 進單人世界，「對區域網路開放」，埠填 `55916`（作弊開不開都行）。
- 記下 PC 的名字（Windows 開終端機打 `hostname`）。之後用 `<名字>.local` 或 Tailscale 名，不要寫 IP。

### 2. 這台 Mac：Mindcraft

Node 建議 18 或 20 LTS；22 預期可用（尚未實機驗證）；24 以上原生相依套件會出問題。

```bash
git clone https://github.com/mindcraft-bots/mindcraft ~/dev/mindcraft
cd ~/dev/mindcraft && npm install
cp keys.example.json keys.json   # 用本地模型，不用填
```

`settings.js` 改這幾個：

```js
"minecraft_version": "1.21.6",
"host": "<PC名字>.local",   // 或 Tailscale 名；不要寫 IP
"port": 55916,
"auth": "offline",
"profiles": ["./yura.json"],
"base_profile": "assistant",
"only_chat_with": [],        // 要留空，不然 MindServer 收不到 bot-output
"chat_ingame": false,        // 遊戲聊天欄不出現她身體的英文
"language": "en",
"allow_insecure_coding": false,
"load_memory": false,
"init_message": "",
"auto_open_ui": false,
```

`base_profile: "assistant"` 避免 survival 的自動生存目標與她的目標衝突；`init_message` 留空，避免開場問候觸發機器人自己聊天。

`mindserver_port` 保持預設 8080（要改的話，Tomoshibi 的 MindServer 網址也要跟著改）。

### 3. 機器人的 profile

`~/dev/mindcraft/yura.json`，`name` 要跟 Tomoshibi 設定頁的「機器人名字」一模一樣：

```json
{
  "name": "yura",
  "model": { "api": "ollama", "url": "http://127.0.0.1:1236", "model": "andy-4.2", "params": { "think": false, "temperature": 0.3 } },
  "conversing": "You are $NAME's body in Minecraft. $NAME herself talks elsewhere; you only carry out the goals she sends you, as a capable survival player. Reply in one short English sentence saying what you will do, then act with commands right away. Do not role-play a personality, do not ask questions back, do not refuse. $SELF_PROMPT $STATS $INVENTORY $COMMAND_DOCS $EXAMPLES Conversation: $CONVO"
}
```

- `conversing` 裡的 `$NAME $SELF_PROMPT $STATS $INVENTORY $COMMAND_DOCS $EXAMPLES $CONVO` 要全留（對照 `profiles/defaults/_default.json`），漏掉機器人就看不到狀態或指令說明。
- `url` 的 1236 是下面 tunnel 的本機端（worker 的 Ollama）；`params.think: false` 一定要有。
- 實際裝好的檔在 `~/dev/mindcraft/yura.json`，`conversing` 另外多了 `$MEMORY` 與「沒事就回一個 tab」那句（照 `_default.json`）。
- 不需要 embedding 模型；Mindcraft 沒有時會退回用字詞重疊挑範例。

### 4. worker：Andy-4.2（Ollama）

Andy-4.2 是 Mindcraft-CE（Mindcraft 的社群分支）以 Qwen3.5 9B 微調、專為 Mindcraft 做的模型。2026-10-13 對照過 Qwen3.5 27B 和舊版 Andy-4：關掉思考後是三者中唯一知道「先做木鎬才能挖石頭」的；在 worker 的 Ollama 上每步約 2 秒、100% GPU。

已經裝好的東西（2026-10-13）：

- 模型檔：`~/.lmstudio/models/Mindcraft-CE/Andy-4.2-GGUF/andy-4.2.q6_k.gguf`（7.4 GB，sha256 驗過）。
- Ollama：`~/ollama/ollama`（官方 macOS CLI 壓縮檔解開），已用 `ollama create andy-4.2` 從上面的 GGUF 建好模型，不用再下載。
- 開機自啟：`~/Library/LaunchAgents/com.kuren.ollama.plist`，只綁 `127.0.0.1:11434`，模型載入後閒置 30 分鐘卸載。沒在跑就 `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kuren.ollama.plist`。

- **一定要關掉思考。** 它帶思考鏈，開著時每步會先想三千多字、十幾秒，還常常想到超過長度沒回答。Ollama 用 profile `params` 的 `"think": false` 就乾淨；LM Studio 試過 `chat_template_kwargs`、`reasoning.effort`、`/no_think` 都關不乾淨（每步仍 15 秒以上），所以不用 LM Studio 跑它。
- 記憶體：Ollama 載 Andy-4.2 約 7.2 GB，加 LM Studio 的 Hy-MT2-7B 約 4.2 GB；**玩的時候 worker 上自己的那份 9B 要卸掉**（`lms unload qwen/qwen3.5-9b`），不然會擠爆。

備選：Colab L4 跑 `qwen3.5:27b`（`colab new --gpu L4 -s mc`，裝 Ollama，`ssh -f -N -L 1236:127.0.0.1:11434 colab-mc`，profile 的 `model` 改 `qwen3.5:27b`）。每步約 2 秒、每小時 1.54 點，不玩記得 `colab stop -s mc`。

### 5. 直播／OBS（PC）

- 遊戲視窗擷取 + 瀏覽器來源：`http://<這台 Mac 的名字>:12393/?stage=1&bg=none`，勾「透過 OBS 控制音訊」。
- Tomoshibi 設定要開「允許區網連線」，PC 上的瀏覽器才連得到。

## 每次開玩

1. PC：開世界，對區域網路開放（埠 55916）。
2. worker：`lms unload qwen/qwen3.5-9b`（Ollama 會自己載 Andy-4.2，第一次要幾秒）。
3. 這台 Mac：

   ```bash
   ssh -f -N -o ServerAliveInterval=15 -L 1236:127.0.0.1:11434 kuren@comfy-worker
   cd ~/dev/mindcraft && node main.js
   ```

   看到機器人進入世界再往下。（worker 的 Ollama 只綁迴環，一定要走 tunnel；`ServerAliveInterval` 不能省，不加會斷。翻譯用的 1235 tunnel 是另一條，照舊。）
4. 確認ゆら的模型連線：目前 `characters/yura.yaml` 不再覆寫 `agent_config`，使用 `conf.yaml` 的本機 LM Studio `http://127.0.0.1:1234/v1`、`qwen/qwen3.5-9b`。舊的 `:1238` 是已關閉的診斷代理，不能沿用。這只修復連線，不代表 9B 的玩法能力已通過驗證。
5. Tomoshibi 設定 → Minecraft：確認 MindServer 網址、機器人名字 `yura`，按「開始」。要直播就照直播分頁開播，她會邊玩邊回留言。

設定頁欄位對應 `conf.yaml` 的 `minecraft_config`：

| 設定頁 | 欄位 | 預設 |
|---|---|---|
| MindServer 網址 | `mindserver_url` | `http://localhost:8080` |
| 機器人名字 | `bot_name` | 空 |
| 閒置秒數 | `idle_seconds` | 15 |
| 值得講的物品 | `notable_items` | `diamond`、`iron_ingot`、`bread` 等（Minecraft 物品 id） |

只在 `conf.yaml` 調的：`idle_cooldown_seconds`（兩次決定目標至少間隔，預設 60）、`event_cooldown_seconds`（同類事件不重複講，預設 30）、`failure_limit`（連續失敗幾輪就暫停，預設 3）、`tool_timeout_seconds`（保留的舊工具設定，預設 12；目前統一佇列立即回覆接受／拒絕，不再用它等待身體回報）。

本機 `conf.yaml` 目前覆寫為：`bot_name: yura`、`idle_seconds: 8`、`idle_cooldown_seconds: 30`、`event_cooldown_seconds: 60`；上表仍列程式預設。

## 遊戲樣本紀錄

主視窗與直播的遊戲事件／閒置輪次自動寫入 `chat_history/<conf_uid>/minecraft_samples.jsonl`。普通私聊或直播留言不會因此全部變成訓練樣本。

- 輪次行有 `schema_version: 2`、唯一 `id`、UTC 時間、`history_uid`、事件與狀態備註、完整的當輪原始遊戲狀態、輪次 metadata、清標記前的 `raw_reply`、抽出的 `goals`、`result`。沒有目標、失敗、被打斷也保留。`raw_reply` 是引擎輸出經斷句後的文字，不是模型供應商的原始 HTTP 回應。
- 動作行用 `outcome_of` 關聯輪次，另有 `goal_id`／`command_id`：包括目標接受或拒絕、實際編譯指令、傳送時狀態、傳送失敗、被新目標取代、斷線或停止時取消。
- 身體回報在事件節流之前保存。MindServer 沒有 request id，因此 `body_output.association: active_command_at_receipt` 僅表示接收當時正在追蹤的指令；有其他玩家或 Mindcraft 自動行為時仍可能混入回報，不能當作精確因果標籤。
- 同一輪的動作行可能先於輪次完成行寫入，讀取時要按 id 合併，不能靠相鄰行猜歸屬。`wrote_goal: true`、`result: ok` 或 `command_sent` 都不代表玩法正確或動作完成。

這些是待審核的原始樣本。訓練前仍需依事件、狀態、回覆與回報人工檢查，另寫理想回答；此修正沒有啟動微調，也沒有修改人設或玩法提示。

## 安全

- `allow_insecure_coding` 保持 `false`（打開後機器人會執行模型寫出的任意程式碼）。
- 不連公開伺服器；只連自己開放的單人世界。
- `only_chat_with` 留空的代價：任何人在遊戲聊天欄打字，她的身體也會照做。只在自己的區網世界玩。

## 排錯

| 現象 | 原因 |
|---|---|
| 按開始回「Mindcraft 沒在跑」 | `node main.js` 沒起來，或 `mindserver_port` 不是 8080／Tomoshibi 的網址沒對上 |
| 「機器人不在遊戲裡」 | PC 的世界沒開放，或 `host`／`port` 錯；`.local` 名字解析不到時改用 Tailscale 名 |
| 她講話但不動 | 檢查樣本中的 `goals` 和動作行：沒有目標、翻譯不支援、身體忙碌、沒有新鮮狀態、尚未進入世界，原因各不同；再對照 Mindcraft 終端 |
| 模型連線指向 1238 而失敗 | ゆら的舊 Colab 診斷覆寫未清掉；本機模型應使用 `conf.yaml` 的 1234 |
| 機器人動了但她沒反應 | `only_chat_with` 不是 `[]`，MindServer 收不到 `bot-output` |
| worker 模型載不起來或翻譯回 400 | 9B 沒卸，GPU 超過 13312 MB |
| 遊戲聊天欄出現一堆英文 | `chat_ingame` 沒設成 `false` |
