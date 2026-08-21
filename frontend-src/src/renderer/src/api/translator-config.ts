// 跨語言發聲／字幕翻譯設定的 typed wrapper。後端見
// src/open_llm_vtuber/translator_route.py 的 GET/POST /api/translator-config
// （handler 本體＋檔頭的機制說明都在那份檔案，這裡不重複抄一份）。
//
// 跟 api/perf.ts／api/player.ts 同一套慣例：一律回傳 ApiResult<T>，不 throw。
//
// 這個模組刻意分兩層：
// 1. fetchTranslatorConfig／saveTranslatorConfig：薄薄的 GET/POST 包裝。
// 2. buildTranslatorSavePayload：純函式，決定「這次到底送什麼」——見它上面的
//    大段說明，這是整個模組裡最容易踩雷的一塊，值得獨立測試。
//
// 不在這裡放語言選單的資料（SUBTITLE_LANG_OPTIONS）：那是 UI 選項，跟後端
// deeplx.py 的 LANG_NAME_TO_DEEPL_CODE 表同步，放在
// hooks/sidebar/setting/use-translator-settings.ts——見該檔案檔頭說明。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export const VALID_ENGINES = ['llm', 'deeplx'] as const
export type TranslatorEngine = (typeof VALID_ENGINES)[number]

export function isTranslatorEngine(value: string): value is TranslatorEngine {
  return (VALID_ENGINES as readonly string[]).includes(value)
}

// GET /api/translator-config 的完整回應形狀（translator_route.py 367-424）。
export interface TranslatorConfigState {
  enabled: boolean
  engine: TranslatorEngine
  // 後端唯一會回傳 llm／deeplx 以外值的欄位——conf.yaml 手動設成 tencent 時，
  // engine 會退回顯示 'llm'，但 raw_provider 誠實回報真正生效的值。UI 不把它
  // 綁到任何控制項，只在需要對使用者揭露「conf.yaml 現在其實是 tencent」時
  // 才讀它（目前 you.tsx 沒有這個顯示需求，先原樣透傳，見後端 handler
  // 367 行附近註解）。
  raw_provider: string
  llm_target_lang: string
  llm_endpoint: string
  llm_model: string
  deeplx_target_lang: string
  deeplx_endpoint: string
  speak_voice: string
  default_jp_voice: string
  translate_subtitle: boolean
  subtitle_target_lang: string
}

export const fetchTranslatorConfig = (
  baseUrl: string,
): Promise<ApiResult<TranslatorConfigState>> =>
  apiGet<TranslatorConfigState>(baseUrl, '/api/translator-config')

// POST /api/translator-config 的回應形狀（translator_route.py 552-575 附近）。
export interface TranslatorConfigSaveResult {
  enabled: boolean
  engine: string
  translate_subtitle: boolean
  subtitle_target_lang: string
  restart_required: boolean
}

// UI 實際提供控制項的欄位子集。engine：兩個選項的下拉選單。deeplx_endpoint：
// 只有 engine=deeplx 時才顯示的輸入框。translate_subtitle／subtitle_target_lang：
// 字幕語言下拉選單（見 use-translator-settings.ts 的 mapSubtitleSelection）。
//
// 刻意不包含 llm_target_lang／llm_endpoint／llm_model／deeplx_target_lang——
// 這四個沒有對應的 UI 控制項（i18n 的 50 個鍵裡沒有讓使用者填它們的欄位；
// llm_endpoint／llm_model 的設計是直接沿用「你現在的 AI」，deeplx_target_lang
// 跟 llm_target_lang 一樣，audio 路徑的真正目標語言現在是角色的發聲語言 V，
// 這兩個欄位只是後端在 V 推導不出來時的 fallback，不是使用者要調的東西）。
// 也不包含 speak_voice——後端已經不再用它（POST handler 永遠傳 None，
// 見 translator_route.py 487-492 附近），送了也沒作用。
export interface TranslatorConfigEdits {
  engine?: TranslatorEngine
  deeplx_endpoint?: string
  translate_subtitle?: boolean
  subtitle_target_lang?: string
}

// 把「目前從 GET 拿到的完整設定」＋「這次使用者實際改的欄位」合併成 POST
// body。這是整個模組最重要的一段邏輯：POST handler 對「呼叫端沒送的欄位」
// 的處理方式因欄位而異——
//   - llm_target_lang／deeplx_target_lang：沒送就退回寫死的預設值（'日文'／
//     'JA'，見 translator_route.py 500-501／496-499），不是「保留原值」。
//   - llm_endpoint／llm_model：沒送才會觸發從目前的 AI 設定重新推導
//     （510-525 行），不是單純的預設值，但一樣不是「保留 conf.yaml 現有值」。
// 如果這裡漏送任何一個，效果是「使用者只是想切换翻譯引擎或字幕語言，結果
// conf.yaml 裡跟這次操作完全無關的欄位被靜默改掉」——跟任務要防的
// extra_body／timeout 陷阱是同一種事故，只是換了欄位。所以這個函式無條件把
// 這四個隱藏欄位原樣帶上（來自 current，不是來自 edits——UI 沒有暴露它們的
// 編輯管道），確保沒有 UI 控制項的欄位在任何一次存檔動作後都維持原值。
export function buildTranslatorSavePayload(
  current: TranslatorConfigState,
  edits: TranslatorConfigEdits,
): Record<string, unknown> {
  return {
    enabled: current.enabled,
    engine: edits.engine ?? current.engine,
    llm_target_lang: current.llm_target_lang,
    llm_endpoint: current.llm_endpoint,
    llm_model: current.llm_model,
    deeplx_target_lang: current.deeplx_target_lang,
    deeplx_endpoint: edits.deeplx_endpoint ?? current.deeplx_endpoint,
    translate_subtitle: edits.translate_subtitle ?? current.translate_subtitle,
    subtitle_target_lang: edits.subtitle_target_lang ?? current.subtitle_target_lang,
  }
}

// 送出前的存檔前檢查，對應後端 466-485 行的驗證：translate_subtitle=true 卻
// target lang 是空字串會被 400 擋下。UI 目前的字幕下拉選單設計上不可能送出
// 這個組合（「原文」選項本身就把 translate_subtitle 設回 false，見
// use-translator-settings.ts 的 mapSubtitleSelection），但存檔前仍在這裡擋
// 一次——純函式，不必等一次網路來回才發現送不出去，也防将来 UI 改法時
// 不小心又踩回這個組合。刻意回傳 boolean 而不是專屬錯誤訊息鍵：50 個既有
// i18n 鍵裡沒有對應這個情境的文案，呼叫端擋下時直接沿用既有的
// settings.translator.saveFailed，不新造一個理論上不會被使用者看到的鍵。
export function isTranslatorPayloadValid(payload: Record<string, unknown>): boolean {
  if (payload.translate_subtitle && !String(payload.subtitle_target_lang ?? '').trim()) {
    return false
  }
  return true
}

export const saveTranslatorConfig = (
  baseUrl: string,
  current: TranslatorConfigState,
  edits: TranslatorConfigEdits,
): Promise<ApiResult<TranslatorConfigSaveResult>> =>
  apiPost<TranslatorConfigSaveResult>(
    baseUrl,
    '/api/translator-config',
    buildTranslatorSavePayload(current, edits),
  )

// 這個功能的每一種失敗都是無聲的：推理模型把答案放進 reasoning_content、
// content 留空；模型太慢撞到逾時；端點或模型名打錯。LLMTranslate 一律 fallback
// 回原文，所以角色只是講出沒翻譯的句子，畫面上沒有任何錯誤——跟「翻譯根本沒開」
// 長得一模一樣。這支端點跑一次真的翻譯並回報結果，把沉默的失敗變成看得見的。
export interface TranslatorTestResult {
  ok: boolean
  reason: 'ok' | 'unchanged' | 'disabled' | 'config' | 'error'
  sample?: string
  result?: string
  seconds?: number
  provider?: string
  error?: string
}

export const testTranslator = (
  baseUrl: string,
): Promise<ApiResult<TranslatorTestResult>> =>
  apiPost<TranslatorTestResult>(baseUrl, '/api/translator-config/test', {})
