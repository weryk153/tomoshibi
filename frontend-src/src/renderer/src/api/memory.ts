// 記憶端點的 typed 包裝。不含 React，所以能用 node:test 驗證。
//
// 記憶全在引擎手上：這段對話的記憶、她自己的記憶，都沒有字數上限，也沒有整理
// 頻率可調。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export interface MemoryState {
  enabled: boolean
  content: string
  // 她自己的記憶：角色層、所有對話共用、直播時也帶著。
  self_content: string
}

// 寫入要等引擎改完記憶檔才回應；apiPost 的預設逾時（DEFAULT_TIMEOUT_MS，15 秒）
// 在背景工作正忙時可能不夠，後端其實已經存好、畫面卻報「請求逾時」。拉到
// 20 秒留出餘裕。
const MEMORY_WRITE_TIMEOUT_MS = 20000

// GET /api/memory 的原始回應形狀（就是 memory_route.py 實際回傳的鍵）。
interface MemoryGetResponse {
  conf_uid: string
  enabled: boolean
  content: string
  self_content: string
}

// 從 GET 的原始形狀映射成 MemoryState。抽成純函式是為了測得到——欄位漏抄
// 在 UI 上只會顯示成空白，不會報錯。
export function mapMemoryResponse(d: MemoryGetResponse): MemoryState {
  return {
    enabled: d.enabled,
    content: d.content,
    self_content: d.self_content,
  }
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
  return {
    ok: true,
    data: mapMemoryResponse(res.data),
  }
}

// POST /api/memory：整份取代這段對話的記憶（不是部分更新）。
// editedFrom 是這份編輯的起點（載入時放進 textarea 的那一版）。引擎用它判斷
// 哪幾行是使用者刪掉的：頁面開著的時候引擎新記下的行不在起點裡，不算被刪。
// 不送的話伺服器當成整份取代。
export const saveMemoryContent = (
  baseUrl: string,
  confUid: string,
  content: string,
  editedFrom?: string,
): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(
    baseUrl,
    '/api/memory',
    { conf_uid: confUid, content, edited_from: editedFrom },
    MEMORY_WRITE_TIMEOUT_MS,
  )

export const setMemoryEnabled = (
  baseUrl: string,
  confUid: string,
  enabled: boolean,
): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(baseUrl, '/api/memory/toggle', { conf_uid: confUid, enabled })

// 破壞性：把這段對話的記憶清空（不動對話紀錄）。
export const clearMemory = (baseUrl: string, confUid: string): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(
    baseUrl,
    '/api/memory/clear',
    { conf_uid: confUid },
    MEMORY_WRITE_TIMEOUT_MS,
  )

// POST /api/memory/self：整份取代她自己的記憶（角色層；她的引擎要在跑）。
// editedFrom 跟 saveMemoryContent 的同義：只有起點裡有、存回來不見的行才算刪掉。
export const saveSelfMemoryContent = (
  baseUrl: string,
  confUid: string,
  content: string,
  editedFrom?: string,
): Promise<ApiResult<{ content?: string }>> =>
  apiPost<{ content?: string }>(
    baseUrl,
    '/api/memory/self',
    { conf_uid: confUid, content, edited_from: editedFrom },
    MEMORY_WRITE_TIMEOUT_MS,
  )

// 破壞性：清空她自己的記憶。
export const clearSelfMemory = (baseUrl: string, confUid: string): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(
    baseUrl,
    '/api/memory/self/clear',
    { conf_uid: confUid },
    MEMORY_WRITE_TIMEOUT_MS,
  )

