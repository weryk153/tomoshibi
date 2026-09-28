# AI Character Engine：Tomoshibi 本機試接

> 這份文件記錄的是最初的試接腳本。正式的接法是 `character_engine_agent`，
> 見 [character-engine-agent.md](character-engine-agent.md)。

本分支驗證把 AI Character Engine 1.0.0 接進 Tomoshibi 的文字對話管線。
現有主程式仍使用原本的 agent；試接入口是 `scripts/try_character_engine.py`。

## 已跑通的情境

使用本機 LM Studio 的 Qwen3.5 9B，經過真實 Tomoshibi `BatchInput`、
引擎串流回合、Tomoshibi 斷句／表情擷取／TTS 文字前處理：

1. 告訴角色「我叫晨星，今天喝烏龍茶」。
2. 下一輪問名字與飲料，確認上下文接續。
3. 將對話轉成 JSON，建立新引擎並還原，再問一次確認可接續。

另檢查表情標籤有轉成 actions、朗讀文字不含表情標籤，且未修改使用者設定。
這輪沒有驗證語音合成／播放、ASR、鏡頭、MCP、背景認知或完整 UI agent 替換。

## 執行試接

Tomoshibi 支援 Python 3.10–3.12，引擎需要 3.11 以上；本次採獨立 Python 3.12
環境，不覆寫原本 `.venv`。在新環境安裝 Tomoshibi 鎖定依賴與已驗證的
`ai_character_engine-1.0.0`、`ai_character_engine_tomoshibi-1.0.0` wheels。
這兩個 wheel 由引擎私人 repo 的交付包提供，不假設公開 PyPI 已上架。

啟動本機 LM Studio，在 `127.0.0.1:1234` 提供相容 API，將已安裝模型載入為
`tomoshibi-engine-trial`，再使用該 Python 3.12 環境執行：

```sh
python scripts/try_character_engine.py --tomoshibi . --output /tmp/tomoshibi-engine-trial.json --interactive
```

程式先跑上述三輪，全部通過後可繼續輸入文字；`/quit` 結束。可用 `--model`
指定另一個本機已載入的模型識別字。結果 JSON 保存檢查狀態及對話，不寫入
Tomoshibi 使用者歷史。模型未啟動、連線失敗或任一檢查失敗，都會回傳失敗。

試接只連本機推論，不啟用搜尋、雲端模型或語音服務。完整 App 的設定與服務
仍由原本的 Tomoshibi 管理。
