// 直播分頁的 REST 包裝與純函式。不含 React，所以能用 node:test 驗證。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export interface StreamSettings {
  youtube_url: string
  blocklist: string[]
  quiet_seconds: number
  max_comment_chars: number
  comment_max_age_seconds: number
  same_viewer_cooldown_seconds: number
  failure_limit: number
}

export type ChatState = 'idle' | 'connecting' | 'connected' | 'retrying' | 'ended'

export interface StreamStatus {
  live: boolean
  stage_connected: boolean
  chat: ChatState
  read: number
  dropped: number
  queued: number
  current: { author: string; text: string } | null
  // null：還沒停過；ended：直播結束；failures：連續失敗暫停；stopped：按了停止；error：程式出錯
  stopped_reason: string | null
  last_error: string
  history_uid: string | null
}

export interface StreamInfo {
  settings: StreamSettings
  status: StreamStatus
}

export const fetchStream = (baseUrl: string): Promise<ApiResult<StreamInfo>> =>
  apiGet<StreamInfo>(baseUrl, '/api/stream')

export const saveStreamSettings = (
  baseUrl: string,
  changes: Partial<StreamSettings>,
): Promise<ApiResult<{ settings: StreamSettings }>> =>
  apiPost<{ settings: StreamSettings }>(baseUrl, '/api/stream/settings', changes)

// 失敗時 error 是後端的原因代號（already_live／no_stage／no_url／bad_url）。
export const startStream = (baseUrl: string, url: string): Promise<ApiResult<StreamStatus>> =>
  apiPost<StreamStatus>(baseUrl, '/api/stream/start', { url })

export const stopStream = (baseUrl: string): Promise<ApiResult<StreamStatus>> =>
  apiPost<StreamStatus>(baseUrl, '/api/stream/stop', {})

export function blocklistFromText(text: string): string[] {
  const words: string[] = []
  for (const line of text.split('\n')) {
    const word = line.trim()
    if (word && !words.includes(word)) words.push(word)
  }
  return words
}

export function blocklistToText(words: readonly string[]): string {
  return words.join('\n')
}

export function parseQuietSeconds(text: string): number | null {
  const trimmed = text.trim()
  if (!/^\d+$/.test(trimmed)) return null
  const value = Number(trimmed)
  return value >= 5 && value <= 3600 ? value : null
}

// 開始按鈕不能按的原因（i18n 鍵）；直播中按鈕是「停止」，永遠能按。
export function startBlockedKey(status: StreamStatus | null, url: string): string | null {
  if (!status) return 'settings.stream.loading'
  if (status.live) return null
  if (!status.stage_connected) return 'settings.stream.needStage'
  if (!url.trim()) return 'settings.stream.needUrl'
  return null
}
