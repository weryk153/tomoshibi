// 記憶端點的 typed 包裝與邊界驗證。
//
// 不含 React，所以能用 node:test 驗證。與 api/characters.ts 的做法不同：那裡
// 刻意不做前端欄位驗證，因為後端對缺欄位會立即回帶可讀訊息的 400。這裡的
// cap／consolidation 是滑桿與下拉選單，前端本來就該讓 UI 無法產生非法值——
// 那不是重複後端規則，是拒絕組出一個註定會被拒絕的請求。

import { apiGet, apiPost, type ApiResult } from './http.ts'

// 見 src/open_llm_vtuber/memory_route.py 的 set_cap／CAP_MIN／CAP_MAX。
// 這兩個常數只當 clampCap 的最後防線——它是純函式，會在狀態載入完成前就被
// 呼叫，拿不到伺服器送來的界限。畫面上顯示與強制的範圍請用 MemoryState 帶
// 回來的 cap_min／cap_max，那才是權威。
const CAP_MIN = 500
const CAP_MAX = 8000

// 見 memory_core.CONSOLIDATE_INTERVAL_CHOICES；後端用 `in` 集合比對，這裡跟著做。
const CONSOLIDATION_CHOICES = new Set([1, 3, 5])

export interface MemoryState {
  enabled: boolean
  content: string
  char_count: number
  cap: number
  consolidation_interval: number
  // 後端已經在 GET 裡公布 cap 的界限（memory_route.py 的 cap_min／cap_max，
  // 值來自 memory_core）。先前這裡把它們丟掉，
  // UI 改用自己寫死的副本——今天數字剛好一樣，但只要後端調整界限，畫面就會
  // 顯示並強制一個伺服器早就不用的範圍，而且不會有任何錯誤訊息。伺服器是
  // 權威，帶著走。
  cap_min: number
  cap_max: number
}

// GET /api/memory 的原始回應形狀（欄位比 MemoryState 多，且後端命名是
// 因為這就是 memory_route.py 實際回傳的鍵）。
interface MemoryGetResponse {
  conf_uid: string
  enabled: boolean
  content: string
  exists: boolean
  char_count: number
  cap: number
  cap_min: number
  cap_max: number
  consolidation_interval: number
  consolidation_interval_choices: number[]
}

// cap 是數字輸入框；使用者清空輸入框時 value 會是 NaN，直接送給後端會被
// int() 解析失敗、回一個「'cap' must be an integer」以外更難懂的 400
// （其實是 500，因為 JSON.stringify(NaN) 會變成 null）。用 Number.isFinite
// 把 NaN／Infinity 都攔在前端，永遠不讓非法值離開這個函式。
export function clampCap(value: number): number {
  if (!Number.isFinite(value)) return CAP_MIN
  return Math.min(CAP_MAX, Math.max(CAP_MIN, value))
}

export function isValidConsolidation(value: number): boolean {
  return CONSOLIDATION_CHOICES.has(value)
}

export const fetchMemory = async (
  baseUrl: string,
  confUid: string,
): Promise<ApiResult<MemoryState>> => {
  const res = await apiGet<MemoryGetResponse>(
    baseUrl,
    `/api/memory?conf_uid=${encodeURIComponent(confUid)}`,
  )
  if (!res.ok) return res
  const d = res.data
  return {
    ok: true,
    data: {
      enabled: d.enabled,
      content: d.content,
      char_count: d.char_count,
      cap: d.cap,
      consolidation_interval: d.consolidation_interval,
      cap_min: d.cap_min,
      cap_max: d.cap_max,
    },
  }
}

// POST /api/memory：整份取代 core memory 文字（不是部分更新）。
export const saveMemoryContent = (
  baseUrl: string,
  confUid: string,
  content: string,
): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(baseUrl, '/api/memory', { conf_uid: confUid, content })

export const setMemoryEnabled = (
  baseUrl: string,
  confUid: string,
  enabled: boolean,
): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(baseUrl, '/api/memory/toggle', { conf_uid: confUid, enabled })

// 用 clampCap 頂住，讓這個函式本身就不可能送出範圍外的 cap，不依賴呼叫端
// （UI 的滑桿）先做對——雙重保險比事後才發現漏夾好。
export const setMemoryCap = (
  baseUrl: string,
  confUid: string,
  cap: number,
): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(baseUrl, '/api/memory/cap', { conf_uid: confUid, cap: clampCap(cap) })

// 任務簡報的函式清單沒列出這個，但「已確立的事實」明確列了
// POST /api/memory/consolidation 這個端點，UI 需要它才能存 consolidation
// 設定，所以補上，命名與行為都比照 setMemoryCap。非法值（不在 {1,3,5}）直接
// 丟錯，不悄悄夾到最近的合法值——consolidation 是下拉選單，呼叫端本來就該
// 只送選單上的三個值之一。
// memory.ts 是純模組（見檔頭註解），不能呼叫 t() 做在地化，但 error 欄位是
// 使用者看得到的文字（ApiResult 的慣例——UI 直接把 error 丟進 toaster）。這裡
// 還沒有消費端：目前沒有 consolidation 的 UI，這個分支永遠不會被觸發。等之後
// 的子專案接上 UI，那個呼叫端要能把這個值丟進 t() 顯示成五種語言之一，所以回
// 傳穩定、非語言的識別碼（i18n 鍵的形狀），不是寫死的中文句子——本專案把「寫死
// 的使用者可見字串」視為 Critical 缺陷，因為要出五個語系，在這裡先寫中文句子
// 只是把同一個缺陷往後推延到接線的那一天。
export const CONSOLIDATION_INVALID_INTERVAL_ERROR = 'settings.memory.errors.invalidInterval'

export const setMemoryConsolidation = (
  baseUrl: string,
  confUid: string,
  interval: number,
): Promise<ApiResult<unknown>> => {
  if (!isValidConsolidation(interval)) {
    return Promise.resolve({ ok: false, error: CONSOLIDATION_INVALID_INTERVAL_ERROR })
  }
  return apiPost<unknown>(baseUrl, '/api/memory/consolidation', {
    conf_uid: confUid,
    interval,
  })
}

// 破壞性：把 core memory 清空（不刪檔、不動對話紀錄）。
export const clearMemory = (baseUrl: string, confUid: string): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(baseUrl, '/api/memory/clear', { conf_uid: confUid })

