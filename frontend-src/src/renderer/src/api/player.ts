// 玩家語言與全域指示的 typed wrapper。後端見
// src/open_llm_vtuber/translator_route.py 的 GET/POST /api/player-language 與
// GET/POST /api/player-prompt。兩者都寫進 conf.yaml 的 system_config
// （player_language／player_prompt），conf.yaml 只在啟動時讀取一次，所以兩個
// POST 端點回應裡的 restart_required 永遠是 true——UI 必須講明「存檔後要
// 重啟才生效」這件事。跟 api/perf.ts 的 AsrSaveResult／TtsSaveResult、
// api/agent-config.ts 的 UseMcppSaveResult 同一種做法：restart_required 留在
// setPlayerLanguage／setPlayerPrompt 的公開回傳型別裡，呼叫端從回應資料讀，
// 不另外匯出常數。
//
// 這是跟 UI 顯示語言（general 分頁既有的、決定介面文字用哪種語言）完全不同
// 的設定：player_language 是告訴每一個角色「玩家平常用什麼語言」，讓角色
// 不管輸入語言是什麼，一律用這個語言回覆（service_context.py:815-820）；
// player_prompt 則是注入到每個角色系統提示詞的全域「關於玩家」說明
// （service_context.py:826-831）。兩者都是 system-level，不寫進任何角色
// 人設檔。
//
// 跟其他 api/*.ts（perf.ts／topics.ts／agent-config.ts）同一套慣例：一律回傳
// ApiResult<T>，不 throw。GET 端點的成功回應沒有 ok 欄位（跟 agent-config.ts
// 的 fetchUseMcpp 同一種形狀），這裡收斂成呼叫端只需要的裸字串。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export interface PlayerLanguageOption {
  value: string
  labelKey: string
}

// 五個代碼已對照 src/open_llm_vtuber/asr/sherpa_onnx_asr.py 的
// _clamp_sense_voice_language 驗證過：該函式把 player_language 這個自由字串
// 映射成 SenseVoice 支援的解碼提示（auto/zh/en/ja/ko/yue）。zh-TW／zh-CN 都
// 以 startswith('zh') 落到 'zh'（zh-* 刻意不走 'auto'，SenseVoice 的
// 自動偵測在短句中文片段上會誤判——見該函式的註解），en／ja／ko 則各自
// 以字首比對命中。後端本身（config_manager/system.py 的 player_language
// 欄位）是不限制列舉值的自由字串，這五個代碼是這裡（前端）選定要開放的
// 選項，不是後端強制的枚舉——但選這五個的理由是它們都能被上述 clamp
// 函式正確辨識，不會意外落到 'auto' 這個「放棄辨識、盡力而為」的分支。
export const PLAYER_LANGUAGES: readonly PlayerLanguageOption[] = [
  { value: 'zh-TW', labelKey: 'settings.playerLanguage.optZhTw' },
  { value: 'en', labelKey: 'settings.playerLanguage.optEn' },
  { value: 'ja', labelKey: 'settings.playerLanguage.optJa' },
  { value: 'ko', labelKey: 'settings.playerLanguage.optKo' },
  { value: 'zh-CN', labelKey: 'settings.playerLanguage.optZhCn' },
]

// 後端把換行摺成空白（強制單行）——見 translator_route.py 的
// save_player_prompt：`re.sub(r"\s*\n\s*", " ", prompt).strip()`。前端在送出
// 前先做同樣的正規化，使用者才不會看到「我打了三行，存檔後從後端讀回來
// 變一行」這種像是資料被吃掉的行為；也讓 UI 在使用者按下存檔的當下就能
// 預覽最終會被存成什麼樣子，不必等一次 round trip 才發現。
// 這個正則刻意跟後端逐字元類別對齊，不是 /\s+/g。後端只摺「含有換行的空白
// 串」，同一行內的連續空格與 tab 它原樣保留。若前端用 /\s+/g，使用者刻意打的
// 「我　　很喜歡」或貼上的 tab 分隔文字會在送出前被靜默改寫，而後端本來根本
// 不會動它——那是無故竄改使用者的內容。
export function normalizePlayerPrompt(raw: string): string {
  return raw.replace(/\s*\n\s*/g, ' ').trim()
}

interface PlayerLanguageGetResponse {
  language: string
}

interface PlayerLanguageSaveResponse {
  ok: true
  language: string
  restart_required: boolean
}

// POST /api/player-language 的回應形狀，跟 api/perf.ts 的
// AsrSaveResult／TtsSaveResult、api/agent-config.ts 的 UseMcppSaveResult 同一種
// 分法：不重複 ok，但保留 restart_required。
export interface PlayerLanguageSaveResult {
  language: string
  restart_required: boolean
}

interface PlayerPromptGetResponse {
  prompt: string
}

interface PlayerPromptSaveResponse {
  ok: true
  prompt: string
  restart_required: boolean
}

// POST /api/player-prompt 的回應形狀，理由同 PlayerLanguageSaveResult。
export interface PlayerPromptSaveResult {
  prompt: string
  restart_required: boolean
}

// GET /api/player-language -> 目前的玩家語言代碼，空字串代表未設定（沿用
// 各角色自身語言）。
export async function fetchPlayerLanguage(baseUrl: string): Promise<ApiResult<string>> {
  const res = await apiGet<PlayerLanguageGetResponse>(baseUrl, '/api/player-language')
  if (!res.ok) return res
  return { ok: true, data: res.data.language }
}

// POST /api/player-language：原樣送出 language，不在這裡限制只能是
// PLAYER_LANGUAGES 裡的值——後端本身就是自由字串欄位，夾選項是 UI（下拉選單）
// 的責任，跟 api/perf.ts 的 applyPreset 交給後端驗證合法性是同一種分工。
export async function setPlayerLanguage(
  baseUrl: string,
  language: string,
): Promise<ApiResult<PlayerLanguageSaveResult>> {
  const res = await apiPost<PlayerLanguageSaveResponse>(baseUrl, '/api/player-language', {
    language,
  })
  if (!res.ok) return res
  return {
    ok: true,
    data: { language: res.data.language, restart_required: res.data.restart_required },
  }
}

// GET /api/player-prompt -> 目前的全域「關於玩家」指示，空字串代表未設定
// （不注入任何內容）。
export async function fetchPlayerPrompt(baseUrl: string): Promise<ApiResult<string>> {
  const res = await apiGet<PlayerPromptGetResponse>(baseUrl, '/api/player-prompt')
  if (!res.ok) return res
  return { ok: true, data: res.data.prompt }
}

// POST /api/player-prompt：送出前一律先過 normalizePlayerPrompt，讓「這次
// 存檔會變成什麼樣子」在前端與後端完全一致——不依賴後端的正規化當唯一
// 防線，也不讓使用者在存檔前後看到不同的字串。
export async function setPlayerPrompt(
  baseUrl: string,
  prompt: string,
): Promise<ApiResult<PlayerPromptSaveResult>> {
  const res = await apiPost<PlayerPromptSaveResponse>(baseUrl, '/api/player-prompt', {
    prompt: normalizePlayerPrompt(prompt),
  })
  if (!res.ok) return res
  return {
    ok: true,
    data: { prompt: res.data.prompt, restart_required: res.data.restart_required },
  }
}
