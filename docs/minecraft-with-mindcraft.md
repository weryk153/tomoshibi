# 用 Mindcraft 讓她玩 Minecraft

Tomoshibi 的 Minecraft 模式不直接操作遊戲。她只決定「接下來要做什麼」，用 `minecraft_do` 工具把目標送給 [Mindcraft](https://github.com/mindcraft-bots/mindcraft) 的 MindServer（socket.io），由 Mindcraft 的機器人去執行；機器人的回報與遊戲事件再回到她這邊，由她開口講。

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
"profiles": ["./frieren.json"],
"base_profile": "survival",
"only_chat_with": [],        // 要留空，不然 MindServer 收不到 bot-output
"chat_ingame": false,        // 遊戲聊天欄不出現她身體的英文
"language": "en",
"allow_insecure_coding": false,
"load_memory": false,
"init_message": "Say hello in one short sentence.",
"auto_open_ui": false,
```

`mindserver_port` 保持預設 8080（要改的話，Tomoshibi 的 MindServer 網址也要跟著改）。

### 3. 機器人的 profile

`~/dev/mindcraft/frieren.json`，`name` 要跟 Tomoshibi 設定頁的「機器人名字」一模一樣：

```json
{
  "name": "frieren",
  "model": { "api": "lmstudio", "url": "http://127.0.0.1:1235/v1", "model": "andy-4" },
  "conversing": "You are $NAME's body in Minecraft. $NAME herself talks elsewhere; you only carry out the goals she sends you, as a capable survival player. Reply in one short English sentence saying what you will do, then act with commands right away. Do not role-play a personality, do not ask questions back, do not refuse. $SELF_PROMPT $STATS $INVENTORY $COMMAND_DOCS $EXAMPLES Conversation: $CONVO"
}
```

- `conversing` 裡的 `$NAME $SELF_PROMPT $STATS $INVENTORY $COMMAND_DOCS $EXAMPLES $CONVO` 要全留（對照 `profiles/defaults/_default.json`），漏掉機器人就看不到狀態或指令說明。
- `url` 的 1235 是下面 tunnel 的本機端。
- 不需要 embedding 模型；Mindcraft 沒有時會退回用字詞重疊挑範例。

### 4. worker：Andy-4.2

Andy-4.2 是 Mindcraft-CE（Mindcraft 的社群分支）以 Qwen3.5 9B 微調、專為 Mindcraft 做的模型。2026-10-13 在 Colab L4 上跟 Qwen3.5 27B 和舊版 Andy-4 對照：關掉思考後每步約 1 秒，做石鎬那條材料鏈是三者中唯一知道「先做木鎬才能挖石頭」的。

- Hugging Face：`Mindcraft-CE/Andy-4.2-GGUF`，檔名 `andy-4.2.q6_k.gguf` 約 7.4 GB（Q4_K_M 5.6 GB、Q8_0 9.5 GB；Q8 加翻譯模型會超過 worker 上限）。LM Studio 內建下載很慢，改用並行 curl range，並驗 sha256。
- 在 LM Studio 載入時取名 `andy-4`（要跟 profile 的 `model` 一致）。
- **一定要關掉思考。** 它帶思考鏈，開著時每步會先想三千多字、十幾秒，還常常想到超過長度沒回答。Ollama 是 `think: false`；LM Studio 在模型的載入設定裡把 reasoning／thinking 關掉，或在 profile 的 `params` 加 `"chat_template_kwargs": {"enable_thinking": false}`。第一次跑先看 Mindcraft 終端：回話一句加一條指令、一兩秒內出來，就是對的。
- worker 的 GPU 上限是 13312 MB。Hy-MT2-7B（約 5 GB）要留著，所以**玩的時候要卸掉 worker 上自己的那份 9B**，否則會 OOM。

備選：Colab L4 跑 `qwen3.5:27b`（`colab new --gpu L4 -s mc`，Ollama，`ssh -f -N -L 1236:127.0.0.1:11434 colab-mc`，profile 改 `{"api": "ollama", "url": "http://127.0.0.1:1236", "model": "qwen3.5:27b"}`）。每步約 2 秒、每小時 1.54 點，不玩記得 `colab stop -s mc`。

### 5. 直播／OBS（PC）

- 遊戲視窗擷取 + 瀏覽器來源：`http://<這台 Mac 的名字>:12393/?stage=1&bg=none`，勾「透過 OBS 控制音訊」。
- Tomoshibi 設定要開「允許區網連線」，PC 上的瀏覽器才連得到。

## 每次開玩

1. PC：開世界，對區域網路開放（埠 55916）。
2. worker：卸掉 9B，載入 `andy-4`（Andy-4.2，思考要關）。
3. 這台 Mac：

   ```bash
   ssh -f -N -o ServerAliveInterval=15 -L 1235:127.0.0.1:1234 kuren@comfy-worker
   cd ~/dev/mindcraft && node main.js
   ```

   看到機器人進入世界再往下。（LM Studio 只綁迴環，一定要走 tunnel；`ServerAliveInterval` 不能省，不加會斷。）
4. Tomoshibi 設定 → Minecraft：確認 MindServer 網址、機器人名字，按「開始」。要直播就照直播分頁開播，她會邊玩邊回留言。

設定頁欄位對應 `conf.yaml` 的 `minecraft_config`：

| 設定頁 | 欄位 | 預設 |
|---|---|---|
| MindServer 網址 | `mindserver_url` | `http://127.0.0.1:8080` |
| 機器人名字 | `bot_name` | 空 |
| 閒置秒數 | `idle_seconds` | 15 |
| 值得講的物品 | `notable_items` | `diamond`、`iron_ingot`、`bread` 等（Minecraft 物品 id） |

只在 `conf.yaml` 調的：`idle_cooldown_seconds`（兩次決定目標至少間隔，預設 60）、`event_cooldown_seconds`（同類事件不重複講，預設 30）、`failure_limit`（連續失敗幾輪就暫停，預設 3）、`tool_timeout_seconds`（她的目標工具等 Mindcraft 回覆的秒數，預設 12；要小於引擎的 15 秒工具上限，別調超過）。

## 安全

- `allow_insecure_coding` 保持 `false`（打開後機器人會執行模型寫出的任意程式碼）。
- 不連公開伺服器；只連自己開放的單人世界。
- `only_chat_with` 留空的代價：任何人在遊戲聊天欄打字，她的身體也會照做。只在自己的區網世界玩。

## 排錯

| 現象 | 原因 |
|---|---|
| 按開始回「Mindcraft 沒在跑」 | `node main.js` 沒起來，或 `mindserver_port` 不是 8080／Tomoshibi 的網址沒對上 |
| 「機器人不在遊戲裡」 | PC 的世界沒開放，或 `host`／`port` 錯；`.local` 名字解析不到時改用 Tailscale 名 |
| 她講話，但工具回 "No reply" | Andy-4.2 太慢（多半是思考沒關）（超過 `tool_timeout_seconds`）或 tunnel 斷了；看 Mindcraft 終端。連線 refused 是 tunnel 沒開，timeout 是網路不通 |
| 機器人動了但她沒反應 | `only_chat_with` 不是 `[]`，MindServer 收不到 `bot-output` |
| worker 模型載不起來或翻譯回 400 | 9B 沒卸，GPU 超過 13312 MB |
| 遊戲聊天欄出現一堆英文 | `chat_ingame` 沒設成 `false` |
