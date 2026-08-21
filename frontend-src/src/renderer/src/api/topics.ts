// 主動話題端點的 typed wrapper。後端見 src/open_llm_vtuber/topics_route.py。
//
// POST /api/proactive-topics 的語意是「只更新出現的欄位」——省略 topics 就不動
// topics，省略 news 就不動 news。所以 saveTopics 的參數刻意是 Partial，呼叫端
// 只送真正改過的部分，避免「載入 → 使用者只改了新聞開關 → 把整份 topics 一起
// 送回去」這種會在多分頁情境下覆寫他人變更的寫法。
//
// 跟其他 api/*.ts（characters.ts／memory.ts／perf.ts）同一套慣例：三個網路函式
// 一律回傳 ApiResult<T>，把「成功／失敗」交給呼叫端用 if (!res.ok) 判斷，不
// throw。內部直接把 apiGet／apiPost 的回傳值原樣交出去（跟 perf.ts 的
// fetchPerf／setAsrModel 等函式同一種寫法），共用 http.ts 那一套 base URL
// 串接、逾時、與「網路失敗 vs. 非 2xx 回應」錯誤正規化邏輯——這裡不重做一次。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export const INTERVAL_HOURS_MIN = 1
export const INTERVAL_HOURS_MAX = 24
export const INTERVAL_HOURS_DEFAULT = 6

// 見 src/open_llm_vtuber/topics_route.py:66 的 MAX_TOPICS——後端把 topics 陣列
// 靜默截到這個上限（超過的直接丟棄，不報錯）。這裡匯出給 Task 2 的 UI 用：
// UI 要能在使用者新增第 31 個話題時就攔下來、給出提示，而不是讓多出來的話題
// 被後端悄悄丟掉、使用者卻毫無感知。同一個檔案（topics_route.py:67）還有
// MAX_TOPIC_LEN=200（單一話題字數上限），本任務的函式清單沒要求匯出它，
// 留給需要它的呼叫端再補。
export const MAX_TOPICS = 30

export interface NewsSettings {
  enabled: boolean
  interval_hours: number
}

export interface TopicsState {
  topics: string[]
  news: NewsSettings
  last_news_refresh: string | null
  suggestions: string[]
}

export interface RefreshResult {
  ok: boolean
  news_enabled: boolean
  news_ok: boolean
  news_count: number
  last_news_refresh: string | null
}

export function clampIntervalHours(value: number): number {
  if (!Number.isFinite(value)) return INTERVAL_HOURS_DEFAULT
  const rounded = Math.round(value)
  if (rounded < INTERVAL_HOURS_MIN) return INTERVAL_HOURS_MIN
  if (rounded > INTERVAL_HOURS_MAX) return INTERVAL_HOURS_MAX
  return rounded
}

export function normalizeTopics(values: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  values.forEach((raw) => {
    const trimmed = raw.trim()
    if (trimmed === '') return
    if (seen.has(trimmed)) return
    seen.add(trimmed)
    out.push(trimmed)
  })
  return out
}

// GET /api/proactive-topics -> 目前的話題清單 + 新聞設定 + 快速新增建議清單。
export const fetchTopics = (baseUrl: string): Promise<ApiResult<TopicsState>> =>
  apiGet<TopicsState>(baseUrl, '/api/proactive-topics')

// POST /api/proactive-topics：部分更新。patch.topics 存在才送、送之前先過
// normalizeTopics（去空白／去重複，跟後端 _sanitize_topics 的行為對齊，讓
// UI 顯示的清單在送出前後一致，不會存檔後才發現後端幫忙去重、畫面卻沒更新）；
// patch.news?.interval_hours 存在才夾範圍，enabled 原樣送出（它本來就只有
// true／false 兩種合法值，不需要夾）。
//
// 回傳值只湊得出後端這次回應實際帶的欄位（topics／news／last_news_refresh），
// suggestions 是 GET 專屬、POST 回應不含它——呼叫端要嘛沿用上次 fetchTopics
// 拿到的 suggestions（它是靜態清單，不會因為存檔而改變），要嘛乾脆不需要它。
// 所以回傳型別是 Omit<TopicsState, 'suggestions'>，不假裝湊出一個完整
// TopicsState。
export function saveTopics(
  baseUrl: string,
  patch: { topics?: string[]; news?: Partial<NewsSettings> },
): Promise<ApiResult<Omit<TopicsState, 'suggestions'>>> {
  const body: { topics?: string[]; news?: Partial<NewsSettings> } = {}
  if (patch.topics !== undefined) {
    body.topics = normalizeTopics(patch.topics)
  }
  if (patch.news !== undefined) {
    const news: Partial<NewsSettings> = { ...patch.news }
    if (news.interval_hours !== undefined) {
      news.interval_hours = clampIntervalHours(news.interval_hours)
    }
    body.news = news
  }
  return apiPost<Omit<TopicsState, 'suggestions'>>(baseUrl, '/api/proactive-topics', body)
}

// POST /api/proactive-topics/refresh：立即重新抓新聞（若 news.enabled）並
// 重組 prompt。不帶請求體——這個端點不接受任何參數，行為完全由伺服器端已存
// 的狀態決定。
export const refreshNews = (baseUrl: string): Promise<ApiResult<RefreshResult>> =>
  apiPost<RefreshResult>(baseUrl, '/api/proactive-topics/refresh', {})
