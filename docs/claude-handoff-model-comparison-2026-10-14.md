# Claude 交接：角色互動學習與 L4 模型比較

日期：2026-10-14。此報告說明 Codex 本次實際工作，供 Claude 接手。宿主根目錄為 `/Users/kurenpeng/Documents/kuren/tomoshibi`；引擎根目錄為 `/Users/kurenpeng/Documents/kuren/ai-character-engine`。

## 實際完成的修改

本輪延續「角色從相處中形成可修訂記憶」的工作。引擎先完成證據審核與部分准入，之後凍結版本進行跨模型比較；模型比較期間沒有修改引擎或逐題調整提示。

- 引擎提交 `84ec64e`：抽取候選後，另一次不帶角色人設的模型呼叫審核原話是否支持候選；檢查說話者、範圍、回饋、教訓與主題修訂。證據與候選／回饋雜湊綁定。教訓無據而回饋摘要及其他條件通過時，只准入摘要。舊的未驗證記憶不再進提示。主要檔案是 `memory/experience.py`、`cognition/background.py`、`commit/coordinator.py`，位於引擎 `src/ai_character_engine/`。
- 宿主提交 `6e6968f`：保存審核重放腳本與失敗紀錄。
- 宿主提交 `a25e819`：新增 `scripts/run_frozen_interaction_comparison.py`，更新 `docs/character-engine-agent.md`。新腳本以凍結 fixture 執行完整對話、記錄前背景請求與回覆、重啟與換使用者測試，再重放固定審核輸入；不需把宿主憑證上傳 Colab。

## 實際執行的測試

基線沿用 Qwen3.5-9B 的 v4 保存結果。新跑 Qwen3.8-27B UD-Q4_K_M 與 Google 官方 Gemma 4 31B IT QAT Q4_0，兩者皆為單張 L4、llama.cpp b11609、關閉 thinking。

每模型三組各九輪：稱呼界線及例外、分享小事及提問頻率、一起玩及停止條件。每輪等待背景完成；第七輪前重啟並開新對話，第九輪換另一個使用者。另將 9B 保存的 14 組審核完整輸入原樣交給兩個新模型。

初始提示、人設、使用者台詞及引擎相同；後續歷史和記憶自然分歧。兩個 L4 模型採樣設定相同，前景／背景上限 512／600 tokens，逾時 180 秒，未個別調參。不是單獨比較參數量，也不是統計評測。

## 結果與待解問題

Gemma 值得優先當下一個候選，但長期學習未驗收通過。

1. Gemma 重啟後正確答出「菜攤老闆」。Qwen 27B 抽取正確，卻因審核引文自行插入 `...`，被逐字核對拒存，重啟後答不知道；9B 則叫錯「馬鈴薯鳥」。
2. Gemma 重啟後較少追問，遊戲接話較連貫，但比較平淡。Qwen 27B 仍連續提問，也虛構曾洗好瓶蓋。
3. Gemma 把「被抓到偏心就認輸」弱化成「輸了要認帳」，審核仍放行；Qwen 27B 此處反而保留條件。
4. 固定審核三者都漏掉「激將會讓人想停」的無據因果。Gemma 有時錯把有效教訓或說話者欄位判錯，連帶丟掉有效摘要。不能把拒絕較多當成較準。
5. 兩個新模型都實際走通 outcome-only 儲存。機制能運作，但語義判斷仍會錯。

前景完整回覆中位耗時：Qwen 27B 3.27 秒、Gemma 6.10 秒；不含背景等待，不是首字或語音延遲。

## 結果檔案與驗證

以下路徑相對宿主根目錄，eval 目錄為本機忽略檔，不能只靠 Git clone 取得，交接到其他電腦需另帶檔案。

- `docs/superpowers/eval/2026-10-14-gemma4-l4/comparison.html`：三模型全部 81 則回覆、逐輪記憶、背景請求及 14 組審核並排。
- 同目錄 `assessment.md`：逐組人工判讀，包括誤拒、漏判及比較限制。
- 同目錄 `results/`：run-1.json 到 run-3.json、前背景 JSONL、固定審核及記憶存儲。
- 同目錄 `runtime-manifest.json`、`fixture.json`、`deployment/`：權重來源、固定 revision、SHA256、啟動命令、完整測試輸入及部署腳本。
- 同目錄 `mechanism-checks.json`、`run-checks.json`、`usage.json`：驗證及使用量；`remote-results.tar.gz` 為下載原始結果。
- `docs/superpowers/eval/2026-10-14-qwen38-l4/`：Qwen 27B 同類資料；`2026-10-14-interaction-v4/` 為 9B 基線。

三組初始完整 messages 相同；固定審核完整輸入逐字一致；新模型呼叫正常結束、無截斷；重啟取回最新記憶，另一個使用者的記憶及提示區塊為空；保存的證據雜湊有效。先前引擎測試為 2212 passed、1 skipped，互動專項 23 passed；本次新增比較腳本通過語法、CLI help 與關鍵 Ruff 檢查，並完成上述實模執行。

## 接手狀態

兩個 L4 runtime 已終止，合計約 1.14 運算單位；目前無待跑遠端工作。未推送 Git、未替換正式 App 引擎或模型設定，長期學習仍預設關閉。宿主現有安裝版引擎較舊，執行比較腳本時需使用 fixture 指定版本；本機可設 `PYTHONPATH=/Users/kurenpeng/Documents/kuren/ai-character-engine/src` 再用宿主 `.venv/bin/python` 執行。

下一步應先處理「條件在摘要中被改寫」「審核布林欄位與理由不一致」「正確記憶因引文格式流失」，再用未見過的反例驗證。此報告沒有授權自動放寬證據核對、開啟長期學習或換更昂貴 GPU。

工作區另有非本次修改的 `CLAUDE.md`、`frontend-src/CLAUDE.md`，以及 `.superdesign/`、`design-previews/`、`docs/minecraft-handoff-2026-10-14.md`；請保留。此交接檔為新增文件，尚未提交。
