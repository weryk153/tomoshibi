// 選裝套件（例如 faster-whisper）的狀態與一鍵安裝（後端見 optional_extras.py）。
//
// 不含 React，所以能用 node:test 驗證。

import { apiGet, postNdjsonStream, type ApiResult } from './http.ts'

export interface ExtraStatus {
  name: string
  available: boolean
  installing: boolean
  download_mb: number
}

export interface ExtraEvent {
  status?: string
  line?: string
  error?: string
  // status 'model'：語音模型已下載／總共多少 byte（總大小問不到時是 0）。
  completed?: number
  total?: number
}

export const fetchExtraStatus = (baseUrl: string, name: string): Promise<ApiResult<ExtraStatus>> =>
  apiGet<ExtraStatus>(baseUrl, `/api/extras/${encodeURIComponent(name)}`, 5000)

export const installExtra = (
  baseUrl: string,
  name: string,
  onEvent: (event: ExtraEvent) => void,
) => postNdjsonStream<ExtraEvent>(baseUrl, `/api/extras/${encodeURIComponent(name)}/install`, {}, onEvent, {
  failed: '安裝失敗。',
  incomplete: '安裝未完成就中斷了，請再試一次。',
})

/** 畫面上顯示的進度：uv 最新的那一行；空行或其他事件維持原樣。 */
export function lastLine(event: ExtraEvent, previous: string): string {
  return event.status === 'installing' && event.line ? event.line : previous
}

/** 語音模型的下載進度；不是下載事件是 null。總大小不知道時 percent／totalMb 是 null。 */
export function modelProgress(
  event: ExtraEvent,
): { percent: number | null; doneMb: number; totalMb: number | null } | null {
  if (event.status !== 'model') return null
  const done = event.completed ?? 0
  const total = event.total ?? 0
  return {
    percent: total > 0 ? Math.min(100, Math.floor((done / total) * 100)) : null,
    doneMb: Math.round(done / 1e6),
    totalMb: total > 0 ? Math.round(total / 1e6) : null,
  }
}
