# Minecraft 模式交接（2026-10-14）

給接手的人（Codex）。前一段工作由 Claude Code 做，2026-10-13 一整天，約 30 筆 commit，使用者對結果不滿意，要換人接。這份文件講：使用者要什麼、現在做到哪、昨天試過什麼又為什麼翻掉、環境怎麼開。

設計文件：`docs/superpowers/specs/2026-10-13-minecraft-mindcraft-design.md`
實作計畫：`docs/superpowers/plans/2026-10-13-minecraft-mindcraft.md`（照這份做出第一版，之後的改動都沒回寫）
架設與每次開玩：`docs/minecraft-with-mindcraft.md`（部分已過時，見「文件跟實際不符」）

## 使用者要的東西

一句話：Tomoshibi 的角色（月白ゆら，原創 VTuber）**自己玩 Minecraft 生存**，邊玩邊用自己的口吻講給觀眾聽，之後拿來開 YouTube 直播（遊戲畫面疊她的 Live2D）。

使用者在過程中講過、而且還沒被滿足的話（原話）：

- 「我以為是用他第一人稱視角」—— 想看到的是她的視角，不是旁觀者的。
- 「我是說他會使用我開的遊戲，而不是加入」—— 想像的是她接手玩，不是以另一個玩家 `yura` 進世界。Claude 回「接手要靠 Fabric／Baritone 那類模組，另起一個專案」，使用者說「先把現在這條調到能用」，所以這個方向只是暫緩，不是放棄。
- 「他每次都會說做什麼，但都不動」「還是不動」（講了五次）。
- 「他感覺很不會玩」。
- 「說話的同時動作不要停下來」。
- 「不要硬寫規則」—— 明確否決「程式算好下一步要她照抄」「聽不懂就代替她決定」「天黑自動挖洞」。程式只能翻譯她的意圖，不能替她決定。
- 「我們可以自己調教？」「好，但是要存有意義的樣本」—— 願意微調她的腦（Colab 有 L4／A100，使用者做過圖的 LoRA），前提是樣本有意義。

## 現在的架構（main，最後一筆 `dbbdda8`）

```
PC（Windows）Minecraft Java 1.21.6，單人世界對區網開放，埠 55916
        ▲ Mineflayer
Mindcraft（這台 Mac，~/dev/mindcraft，node main.js）
   機器人 profile ~/dev/mindcraft/yura.json，腦 = Andy-4.2（worker 的 Ollama，tunnel 1236）
        │ MindServer socket.io，只綁 localhost:8080
Tomoshibi 後端 src/open_llm_vtuber/minecraft/
   她的腦 = characters/yura.yaml 裡 agent_config 覆寫的 LLM（昨天是 Colab 27B）
```

兩顆模型分工：**她**（Tomoshibi 這邊的 LLM）決定目標並講話；**身體**（Mindcraft 的 Andy-4.2）執行目標。

`src/open_llm_vtuber/minecraft/` 各檔：

| 檔 | 做什麼 |
|---|---|
| `controller.py` | 開始／停止／狀態；目標排隊（身體在忙先排著）；把她的目標交給 `commands.compile_goal`，編得出來就逐步送 `!指令`，編不出來回報她「身體聽不懂」 |
| `host.py` | 接 WebSocketHandler：每一輪遊戲對話 = 對最近有動靜的主視窗跑一次主動開口（`handle_conversation_trigger`），備註從 `extra_metadata` 帶進去；掛工具 `minecraft_do` |
| `session.py` | 主迴圈：每秒狀態差分成事件丟 feed，半秒看一次有沒有該講的；直播中讓位給直播流程 |
| `feed.py` | 事件節流、合併成一輪的備註；閒置多久要她決定目標；`IDLE_NOTE`、`GAME_TURN_INSTRUCTION` 兩段提示文字在這 |
| `events.py` | 純函式：狀態差 → 事件（血量低、死亡、挖到好東西、做完／做不到…） |
| `mindserver.py` | socket.io client：`listen-to-agents`、`send-message`、收 `state-update`／`bot-output`／`agents-status` |
| `goal_tool.py` | 原生工具 `minecraft_do`（註冊著，但模型幾乎不走這條） |
| `goal_text.py` | 從她台詞裡抓 `[minecraft_do: ...]` 標記當目標，字幕與語音裡拿掉（實際在用的路） |
| `commands.py` | 英文目標 → Mindcraft `!指令` 的 regex 翻譯表（木頭、工作台、鎬、石頭、煤、火把、獵動物、逃、打、睡、放方塊、跟著我、過來、停、吃） |
| `samples.py` | 每輪樣本存 `chat_history/<conf_uid>/minecraft_samples.jsonl` 供微調。**寫好、有測試，沒接進流程**，昨天沒存到任何樣本 |
| `settings.py` | 讀寫 `conf.yaml` 的 `minecraft_config` |

設定：`src/open_llm_vtuber/config_manager/minecraft.py`（`mindserver_url`、`bot_name`、`idle_seconds`、`idle_cooldown_seconds`、`event_cooldown_seconds`、`tool_timeout_seconds`、`failure_limit`、`notable_items`）。設定頁有 Minecraft 分頁。`conf.yaml` 現值：`bot_name: yura`、`idle_seconds: 8`、`idle_cooldown_seconds: 30`、`event_cooldown_seconds: 60`。

測試：`tests/test_minecraft_*.py` 共 12 個檔，`uv run pytest` 全綠（1470 passed）。lint：`ruff check .`。

角色檔 `characters/yura.yaml`：**不在 Tomoshibi 版控，是自己的本機 git**（`git -C characters log`）。人設第一條規則就是「要讓身體動就寫 `[minecraft_do: 一句英文]`」。

## 昨天的時間線：試過什麼、為什麼翻掉

照順序，每一步都是「她不動」逼出來的。接手前先知道這些，不要重走。

1. **原生 function calling**（設計的做法）。本機 Qwen3.5 9B 在完整人設下不叫工具；拆掉人設、只留短系統提示才會叫。改工具說明「不呼叫身體不會動」沒用。
2. **換腦到 Colab L4 的 Qwen3.5 27B**（Ollama，ssh tunnel，`colab new --gpu L4 -s mc`，每小時 1.54 點）。直接打 API 會叫工具，但經過引擎（AI Character Engine）的請求就不叫。抓了引擎的原始請求重放：引擎的框架是「輸出只有你說出口的台詞」，模型寧可把工具寫成文字。
3. **改成台詞標記** `[minecraft_do: ...]`（commit `62e2f7f`），照 Mindcraft 自己的做法。模型會寫了，但：
   - Mindcraft 的開場問候讓機器人跟「yura」自己聊，狀態永遠不是閒置 → `init_message` 清空。
   - 閒置輪被事件輪餓死（事件一直有，閒置那輪排不到）→ 身體閒著時事件輪也問她要做什麼。
   - 字幕清 `[標籤]` 的步驟在抓目標之前跑，標記被吃掉 → 調順序。
   - 她寫標記了但目標太虛：「look around」「punch tree」「chop a tree」，身體的 Andy-4.2 把「chop a tree」翻成 `!attack("oak_log")`。
4. **程式照背包算生存下一步寫進提示要她照抄**（`618920f`），再**把目標直接編成 `!指令` 繞過 Andy-4.2 的腦**（`c4304b8`，`commands.py`）。身體終於照做。又加了「聽不懂就做算好的下一步」「天黑或血量低自動挖洞」。
5. **使用者：「不要硬寫規則」** → `b79b3fa` 把 4 的決策部分全拆：算下一步、代替決定、自動挖洞都移除。留下 `commands.py` 的翻譯表（這也是規則，使用者沒點名，但精神上是灰色地帶）。
6. 最後狀態：她自己決定目標（工作台→木鎬→圓石的順序是她想的），翻譯表編得出來就送；血量一直 1、沒食物、沒想到去獵牛。用量上限到，中斷。

其他做過的：人設從原本的改寫成「開 Minecraft 實況的 VTuber」；遊戲輪只講一句、不問觀眾；模式開著時前端的閒置主動開口關掉；每輪備註與送出的目標記進 log（`[minecraft] ...`）；Mindcraft `base_profile` 從 `survival` 改成 `assistant`（survival 的自動模式會自己打獵、跟她的目標打架）。

## 為什麼不滿意（我的判讀，給你參考不是結論）

- 她玩的品質：能動了，但「會不會玩」沒解決。27B 都常給空目標，9B 不行。使用者不接受用規則補，剩下的路是微調（他同意），或換更強的腦（成本）。
- 方向翻了四次，每次重開 server、等三分鐘。使用者看到的體驗是十個小時「還是不動」。
- 兩個原始期待（第一人稱視角、玩他開的遊戲而不是加入）被延後。
- 樣本沒存到，等於昨天跑的輪次對微調零貢獻。

## 現在機器上的狀態（2026-10-14 02:30 查）

- Tomoshibi 後端：**沒在跑**。Mindcraft：沒在跑。Colab session `mc`：已停（`colab ls` 無 session）。
- LM Studio（Bionic）:1234 在跑，本機 9B。
- **`characters/yura.yaml` 的 `agent_config.llm_configs.lmstudio_llm.base_url` 指到 `http://127.0.0.1:1238/v1`**（昨天診斷用的請求轉錄 proxy，早就不在）。現在跟她聊會連不上。要本機就把整段 `agent_config` 拿掉（回到 `conf.yaml` 的 :1234），要 Colab 就重開 Colab 並開 tunnel。
- `conf.yaml` 的 `minecraft_config` 仍是 `bot_name: yura`、`http://localhost:8080`。
- git：main 乾淨，未追蹤的 `.superdesign/`、`design-previews/` 跟這題無關。

## 文件跟實際不符（`docs/minecraft-with-mindcraft.md`）

| 文件 | 實際 |
|---|---|
| profile `frieren.json`，名字 `frieren` | `~/dev/mindcraft/yura.json`，名字 `yura` |
| `base_profile: "survival"` | `"assistant"`（survival 的自動打獵會跟她的目標衝突） |
| `init_message: "Say hello..."` | `""`（有問候機器人會跟自己聊，永遠不閒置） |
| 下目標走 `minecraft_do` 工具 | 走台詞標記 `[minecraft_do: ...]`，工具只是備援 |
| `idle_seconds` 預設 15 | `conf.yaml` 已調 8，cooldown 30 |
| 沒提 `commands.py` | 目標會先被編成 `!指令` 直送，編不出來才回報她 |

## 使用者的工作規則（全部適用）

- **不要硬寫規則**替她做決定。程式可以翻譯、可以回報、不能決定。
- **改提示要人讀對照把關**：n≥3 輪、全文並排給使用者判，自動化指標已經失準過四次。
- **系統提示只增不改**（LM Studio 快取每 256 token 一個檢查點，中段一變整段重讀）。
- `characters/` 在自己的 git 裡 commit，不建 `.bak`。
- Tomoshibi 的 commit 中英皆可；push 前先問。
- 回覆用正體中文。
- 改 `frontend-src/` 要重 build `frontend/` 一起 commit。
- 跟他講話：直接講結果，不要「讓我」「我來」這種開場。

## 環境備忘

- Mindcraft：`~/dev/mindcraft`，`node main.js`；settings 的 `host` 是 `DESKTOP-91248OU.local`，埠 55916。
- 身體的腦 Andy-4.2 在 worker（`ssh kuren@comfy-worker`）的 Ollama :11434，開 tunnel：`ssh -f -N -o ServerAliveInterval=15 -L 1236:127.0.0.1:11434 kuren@comfy-worker`。玩的時候 worker 要 `lms unload qwen/qwen3.5-9b`，否則記憶體爆。
- Colab CLI 有裝：`colab new --gpu L4 -s mc`、`colab stop -s mc`、`colab ls`。
- 她的語音 GPT-SoVITS :9880、翻譯 worker 的 Hy-MT2-7B（tunnel 1235）。
- 使用者的 PC 在遊戲裡開作弊後可 `/tp @s yura`、`/gamemode spectator` 對她點一下變她的視角。Mindcraft 也有 `render_bot_view` 可以開她視角的網頁（沒試）。
- 昨天的 Claude session id `3df4110b`，`cc-session inherit 3df4110b` 可以逐頁讀原始對話（17 頁）。

## 還沒做的（照使用者講過的順序，不是我排的優先）

1. 第一人稱視角（`render_bot_view` 或 spectator 擷取）。
2. 「她玩我開的遊戲」而不是加入：另一條技術路線（Fabric／Baritone 之類），尚未評估。
3. 她會玩：微調她的腦。`samples.py` 要先接進 `host.py`／`controller.py`（每輪存：事件、狀態摘要、原始狀態、她的原始回覆含標記、抓到的目標、身體回報），累積後用強模型替每輪寫理想回答，Colab QLoRA。
4. 說話時動作不停：確認身體的動作不會被她的下一輪打斷（目前 `send-message` 送新目標會中斷 Mindcraft 手上的動作，所以才排隊）。
5. 飢餓／回血：她血量 1 時沒想到找食物。不能寫規則，要靠狀態備註讓她自己看出來，或微調。
6. 把 `docs/minecraft-with-mindcraft.md` 更新到實際狀態。
