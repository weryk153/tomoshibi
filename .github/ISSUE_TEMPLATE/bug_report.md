---
name: Bug report / 回報問題
about: Something is broken or not behaving as documented. 有東西壞了，或跟文件寫的不一樣。
title: "[BUG] "
labels: bug
assignees: ''

---

### 1. Checklist / 檢查項

- [ ] I removed API keys and other sensitive values from the config and logs I am pasting.

      我已從要貼上的設定與日誌中移除 API key 等敏感資訊。

- [ ] I searched [existing issues](https://github.com/weryk153/tomoshibi/issues).

      我已搜尋過[既有的 issue](https://github.com/weryk153/tomoshibi/issues)。

- [ ] I am on the latest version.

      我用的是最新版本。

---

### 2. Environment / 環境

- OS and version / 作業系統與版本:
- How you installed / 安裝方式:
    - [ ] Download ZIP （下載 ZIP）
    - [ ] `git clone` + `uv sync` （從原始碼）
- Are the server and the UI on the same machine? / 後端與前端是否在同一台機器？
- LLM you configured / 你設定的 LLM（Ollama、OpenAI、LM Studio…）:
- GPU model and driver, if you use one / 若有使用 GPU，型號與驅動版本:

---

### 3. What happened / 發生了什麼

What did you do, what did you expect, and what happened instead? Steps to reproduce help most.

你做了什麼、預期看到什麼、實際發生什麼？能重現的步驟最有幫助。

---

### 4. Logs and screenshots / 日誌與截圖

- Server log / 後端日誌（跑 `run_server.py` 的那個視窗）
- Browser console / 瀏覽器主控台（F12）
- Screenshot / 截圖

---

### 5. Configuration / 設定

> Paste the relevant part of `conf.yaml` **with API keys removed**.
>
> 貼上 `conf.yaml` 的相關片段，**務必先移除 API key**。
