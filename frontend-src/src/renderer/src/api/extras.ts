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
