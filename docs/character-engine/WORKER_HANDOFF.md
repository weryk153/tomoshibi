# AI Character Engine／Tomoshibi：Worker 執行交接

更新日期：2026-09-22  
狀態：規格與交接文件；未完成 v0.24 實作或驗收。

完整後續順序見 [ROADMAP.md](ROADMAP.md)。目前首要工作是第 28 冊與 Engine v0.24 的原生整合。28–36 的程式、教材及驗收由後續執行 worker 依依賴順序承接；本文件不代表有排程或背景工作正在自動執行。

## 1. 先取得可重現的輸入

| 輸入 | 已知狀態 | 開始實作前的動作 |
|---|---|---|
| Tomoshibi 公開原始碼 | 已核對 commit `de8c2ce02303ba403e3de35cf4eebf48ca68dd6c` | 讀最新版本與專案指引，保留未合併工作 |
| Engine v0.23.1 | 整合基線，但本交接尚未提供可公開取得的原始碼位置 | 取得真實來源、LICENSE、版本和 checksum；建立公開讀者能重現的取得方式 |
| Engine v0.24 | 目標版本 | 不可預先寫成已發行套件 |
| 教材第 27 冊修訂原稿 | 第 28 冊的先備教材 | 核對實際 API、例子與限制，與 Engine 原始碼逐一對照 |
| 執行與驗收設施 | 須由執行者核對 | 確認 Python／依賴／測試執行、文件產生與真設備的可用範圍 |

不能僅從教材或這份交接推測整個 Engine API，不能編造 import 名稱、PyPI 安裝指令或不存在的下載 URL。若缺少來源，先完成可核對的宿主分析與規格，保留阻擋原因，功能仍標記未完成。

Engine 版本與 Tomoshibi 版本分開管理；目前已讀的 Tomoshibi `pyproject.toml` 是 0.1.10，Python 範圍是 >=3.10,<3.13。必須比對 Engine 實際需求後才決定相容組合。

## 2. 本次已做與未做

**已做：**

- 核對公開 main、完整檔案樹與 `CLAUDE.md`；本次檔案樹未找到 `AGENTS.md`。
- 讀取 Agent factory／interface、輸入輸出型別、Agent 設定、ServiceContext、對話與 TTS 流程。
- 核對既有測試工作流程、LICENSE 及 NOTICE。
- 建立 28–36 路線、28 的整合契約、必要測試矩陣與教材章節安排。

**未做：**

- Engine v0.24 程式、Tomoshibi adapter、依賴更新或功能開關。
- Python 測試、應用啟動、模型呼叫、音訊播放或 GPU 訓練。
- 完整第 28 冊、閱讀版文件、原始碼發行包與實機驗收。

不要把前一版測試數據移作這次變更的驗收，也不要把本文件當成完成的第 28 冊教材。

## 3. 實際宿主入口與整合風險

以下觀察只適用於上述 commit；引用的是現有程式，後續須重讀變動部分。

| 入口 | 已核對行為 | 第 28 冊必處理 |
|---|---|---|
| [AgentFactory](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/agent/agent_factory.py) | 目前只有 basic_memory、mem0、hume、letta 分支；部分可選依賴採 lazy import | 新 agent 為可選分支；未選用時不載入 Engine；保留原預設 |
| [AgentInterface](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/agent/agents/agent_interface.py) | 非同步 `chat`；同步 `handle_interrupt`、`set_memory_from_history`；可選近期主動對話 context | 不能在同步 callback 裡假裝 await；非同步取消／恢復需由宿主提供明確生命週期 |
| [Agent 設定](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/config_manager/agent.py) | agent choice 與 settings 有固定 Pydantic 型別 | 加入型別、驗證、描述及預設範本；未知或缺失設定有可理解的錯誤 |
| [ServiceContext](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/service_context.py) | `load_cache` 直接保存傳入 agent 參照，並讀 basic_memory_agent 的 MCP 設定 | 不可假設「每個 context 物件」等於「每個 session 都有獨立 Runtime」；移除新分支對 basic_memory_agent 設定的隱含依賴 |
| [ServiceContext](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/service_context.py) | `close` 先關 MCP，再呼叫可能存在的 agent.close | 先排乾／取消會使用工具的工作，再關閉由該 owner 持有的資源；防止關閉共享 provider |
| [輸入型別](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/agent/input_types.py) | BatchInput 有 texts、images、files、metadata；主動輸入帶 skip_memory／skip_history 等旗標 | 逐項決定映射、來源、支援性與歷史紀錄政策；旗標不可用來繞過必要的 Engine 執行記錄 |
| [輸出型別](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/agent/output_types.py) | SentenceOutput 分開 DisplayText、tts_text 與 Actions | 不把例外訊息當角色對話；維持字幕／口語／表情的責任邊界 |
| [單人對話](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/conversations/single_conversation.py) | 一般與主動回覆為空時都有再次呼叫 `agent.chat` 的路徑 | Engine 的 BLOCKED／EMPTY／FAILED 不得被誤判為需要重跑整輪；工具副作用可能因此重複 |
| [對話控制](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/conversations/conversation_handler.py) | 個別中斷 cancel task 後立即呼叫同步 interrupt；該函式內未 await 被取消 task | 新回合進 Bridge 前，確定上一工作已離開租約及輸出路徑 |
| [TTS 管理](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/src/open_llm_vtuber/conversations/tts_manager.py) | 有合成 concurrency=2、排序佇列及 clear 取消；註解指出阻塞合成未必真的終止 | 將 TTS 重試與 Engine 重試分開；驗證取消後不會送出舊回合的字幕、音訊與動作 |

額外稽核：搜尋所有直接讀取 `basic_memory_agent` 設定、私有 `_llm`、agent 記憶方法或關閉方法的呼叫點。只接 factory 不足以構成原生整合。

## 4. 第 28 冊的不可破壞契約

### Session 與資源所有權

- 定義可持久對應的角色／對話識別，與暫時的 WebSocket client ID 分開。
- 同一角色 session 的一般輸入與主動輸入使用同一個 Runtime／Bridge；不得為繞過 busy 另建 Runtime。
- 不同使用者／角色的可變 state、history、claim、held 記錄不可共用。
- 網路 client、模型 provider 可否共用要由其能力決定；建立者負責關閉。
- 換角色、切歷史、重連及斷線，都需有明確的 Runtime 建立／保留／清理規則。

### 輸入、取消與關閉

- 使用者輸入優先時，取消並 await 正在執行的主動 task，再提交新的回合。
- 同步 `handle_interrupt` 不應偽造已完成非同步清理；由可 await 的宿主流程收斂。
- 保留已聽見內容與實際已交付內容的區別，避免寫入完整但未播放的回覆。
- 關閉時先拒絕新 tick，再取消並 await 工作，最後依所有權釋放 provider。
- 副作用不確定的 held 工作不能當成可丟棄的 idle 事件，亦不能自動重跑。

### 輸出與重試

- 只有成功交付（DELIVERED）的回覆可以進入新字幕、TTS 與角色動作輸出。
- EMPTY／BLOCKED 沒有新角色輸出；FAILED 走系統錯誤呈現，不朗讀 exception。
- 状態名稱與欄位的實際拼法，取得 Engine 原始碼後確認；本文件只定義語意。
- 宿主的「空輸出重生」須有明確能力或結果契約，不能對所有 agent 一律重跑。
- TTS／輸出交付重試不能重新執行 Runtime、工具或記憶更新。
- 回合取消、角色切換及斷線後，尚未送出的舊輸出必須失效。
- 宿主現有的防重複、主動閒聊及睡眠機制，與 Engine 排程只能有清楚分工，不能各自再發起一輪。

### 歷史與記憶

- 決定 Engine 的執行歷史、Tomoshibi 可見對話紀錄及長期記憶的寫入責任。
- 一個使用者輸入不能因 adapter、宿主與重試各寫一次而變成多筆事實。
- 主動提示等內部控制內容不能被當作使用者真的說過的話。
- 取消、空回覆、輸出被過濾及 held 等情境須有可追蹤狀態，不能默默改成成功。

## 5. 實作工作包與順序

| 工作包 | 必交付 | 依賴 |
|---|---|---|
| W28-01 基線 | Engine 原始碼與授權、真實 API 清單、相容範圍、基線測試證據 | 可取得的 Engine 來源與執行工具 |
| W28-02 Adapter | 可選 Agent 分支、輸入／輸出轉換、型別化設定、lazy import | W28-01 |
| W28-03 Session 宿主 | Runtime 所有權、history 切換、取消等待、關閉、主動 tick 路由 | W28-02 |
| W28-04 交付與故障 | 狀態到輸出的映射、抑制宿主盲重試、held 呈現、TTS 重試分離 | W28-03 |
| W28-05 範例與測試 | 離線 fake provider、本機模型設定、整合及故障測試 | W28-02–04 |
| W28-06 教材 | 完整繁中原稿、可執行示例、練習／解答、詞彙及驗收表 | 與 W28-02–05 同步，內容須符合最終程式 |
| W28-07 驗收與交付 | 三層驗收證據、原始碼包、相容性與限制、遷移／回滾說明 | W28-05–06 |

可由 worker 分工，但同時修改同一宿主檔案前先協調；整合 owner 負責最後的 API 一致性與回歸。每個工作包完成要留下來源 commit、變更與驗證證據。

第 29 冊再深化端到端插話、播放背壓與效能；第 28 冊仍必須確保最基本的取消及舊回合失效安全。第 30 冊再增加持久化自主佇列；第 28 冊不可假稱已有 crash recovery。

## 6. 必要驗收矩陣

| 編號 | 情境 | 預期觀察 |
|---|---|---|
| T01 | 未安裝 Engine、仍用 basic_memory_agent | 原設定可啟動與對話，無 Engine import 錯誤 |
| T02 | 選 Engine 但依賴缺失／版本不相容 | 明確設定錯誤；不偷偷改用不同 agent |
| T03 | 兩個不同 session 同時對話 | state／history／held 互不污染 |
| T04 | 同 session 一般輸入和主動 tick 重疊 | 同一租約約束，沒有第二個 Runtime 旁路 |
| T05 | 主動 task 運行時使用者輸入 | 先取消並 await，再進新回合；舊輸出失效 |
| T06 | EMPTY／BLOCKED／FAILED | 不朗讀例外，不觸發宿主整輪盲重試 |
| T07 | 工具已成功、TTS 失敗 | 僅重試輸出，工具執行次數不增加 |
| T08 | 工具或儲存副作用不確定 | 進 held；需明確處理，不自動重跑或丟棄 |
| T09 | 雙 tick／重複事件 | claim／ack 行為正確，沒有重複角色回覆 |
| T10 | 中斷時 TTS 正合成／排隊 | 新回合不收到舊字幕、音訊或 avatar 動作 |
| T11 | 關閉或換角色時仍有工作 | 拒絕新工作，排乾／取消；不提前關共享 provider |
| T12 | 重連及切換 history | 依指定識別恢復或新建，不串用其他歷史 |
| T13 | 輸入圖片／檔案不受目前模型支援 | 明確拒絕或可追蹤降級；不能假稱已看懂 |
| T14 | 現有防重複／睡眠／主動機制啟用 | 沒有雙排程、雙重記憶寫入或重複回合 |
| T15 | 預設設定與新設定往返載入 | 型別和範本一致，舊設定向後相容 |
| T16 | 無 API 金鑰執行離線範例 | 可確定重現狀態與輸出，無偷偷連外依賴 |

所有列目前皆為待執行；新增測試應針對上述真實風險，不鏡像實作充數。

驗收分三層記錄：

1. **離線：** deterministic fake LLM／TTS／工具、整合測試與故障注入。
2. **真服務：** 實際本機或遠端 LLM、實際 TTS，記錄模型與 provider 設定。
3. **真人設備：** 麥克風、相機／螢幕、字幕、播放、VRM／Live2D 和插話。

缺少任何設備就標記該列未驗收。第 28 冊可提供離線可驗證的程式候選版，但完整實戰驗收仍須補足所宣稱支援的真實路徑。

## 7. 第 28 冊教材章節草案

這是編寫骨架，尚不是完成教材。

1. 從函式庫走到完整角色應用：本冊問題與完成目標。
2. Tomoshibi 宿主架構與現有對話資料流。
3. Engine／Adapter／Provider 的責任和依賴。
4. Session 身分、共享資源與 Runtime 生命週期。
5. AgentInterface、factory 與型別化設定。
6. 文字、ASR、圖片及 metadata 的輸入映射。
7. 回合結果、字幕、TTS 與 Avatar 的輸出映射。
8. 主動輸入與使用者輸入的協調。
9. 中斷、取消、關閉與過期輸出。
10. 記憶、歷史、重複寫入與宿主重試。
11. 外部副作用、held 和輸出階段重試。
12. 從零執行離線整合範例。
13. 本機模型、語音與視覺的實戰設定。
14. 故障注入、測試、除錯與驗收證據。
15. 開源安裝、授權、貢獻、版本相容與後續練習。

每章包含原理、設計理由、真實程式導讀、輸入輸出例子及檢核點。最終附術語表、完整範例索引、練習與參考解答。不能只交簡短實作筆記。

## 8. 開源與專案規則

- 讀 [CLAUDE.md](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/CLAUDE.md) 和 [CONTRIBUTING.md](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/CONTRIBUTING.md)，開始新工作前再次檢查新增指引。
- 新增設定要同步所有適用預設範本，包含 `config_templates/conf.default.yaml`、`conf.ZH.default.yaml`、`conf.tomoshibi.default.yaml`。
- 可選依賴維持 lazy import，不把本機大模型／torch 強制加入預設安裝。
- 若改 `frontend-src/`，依專案規則執行 `pnpm --dir frontend-src run build:web` 並交付 `frontend/`；不手改生成檔。
- 現有 CI 在 Ubuntu／Windows 上以 Python 3.10 執行 `uv sync` 和 `uv run pytest tests/ -q`。依賴變更需更新 lock 並驗證乾淨安裝，不能手造 lock 結果。
- 程式、文件、模型、聲音、圖片、VRM／Live2D 分項記錄來源與授權；保留 [LICENSE](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/LICENSE) 和 [NOTICE](https://github.com/weryk153/tomoshibi/blob/de8c2ce02303ba403e3de35cf4eebf48ca68dd6c/NOTICE)。
- 範例不提交金鑰、使用者對話、私人記憶或未獲再散布授權的資產。
- 對外說明「開源引擎與整合原始碼」時，同時連到既有第三方授權說明；不宣稱整套資產一律 MIT。
- 教材與程式來源都要可編輯、可版本控制；發行的閱讀版和 ZIP 必須對應同一份版本內容。

## 9. 後續每次交接的格式

請直接更新此段或追加日期明確的進度，不要覆蓋尚未解決的阻擋。

- **基準與工作分支：** 實際 commit／PR。
- **完成的工作包：** 附變更檔案與行為。
- **已執行驗證：** 命令、版本、結果與日誌位置。
- **未驗收：** 服務、設備或案例，附原因。
- **阻擋：** 缺少的真實輸入或能力；不得用假 API／測試結果填補。
- **下一步：** 可執行的一個工作包及完成判準。
- **後續路線：** 保留 29–36 的依賴與未完成狀態。

目前下一步為 **W28-01：取得並核對 Engine v0.23.1 真實來源及授權，建立公開可重現取得方式，執行基線測試後再接 adapter**。
