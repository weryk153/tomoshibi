// 還沒生效的設定變更（後端 pending_changes）。不含 React，可 node 測。
import { apiGet, type ApiResult } from './http.ts'

export const PENDING_KEYS = [
  'playerLanguage', 'playerPrompt', 'tools', 'translator', 'engine',
  'asr', 'tts', 'perfPreset', 'memory', 'character',
] as const

export const fetchPending = (baseUrl: string): Promise<ApiResult<{ pending: string[] }>> =>
  apiGet<{ pending: string[] }>(baseUrl, '/api/pending-changes')

export function pendingLabelKeys(keys: string[]): string[] {
  return keys.map((key) => (
    (PENDING_KEYS as readonly string[]).includes(key)
      ? `settings.pending.items.${key}`
      : 'settings.pending.items.other'
  ))
}
