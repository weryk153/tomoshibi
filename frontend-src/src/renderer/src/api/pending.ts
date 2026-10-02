// 還沒生效的設定變更（後端 pending_changes）。不含 React，可 node 測。
import { apiGet, type ApiResult } from './http.ts'

export const PENDING_KEYS = [
  'playerLanguage', 'playerPrompt', 'tools', 'translator', 'engine',
  'asr', 'tts', 'perfPreset', 'memory', 'character', 'host',
] as const

export const fetchPending = (
  baseUrl: string,
): Promise<ApiResult<{ pending: string[]; needs_restart: boolean }>> =>
  apiGet<{ pending: string[]; needs_restart: boolean }>(baseUrl, '/api/pending-changes')

export type PendingAction = 'reload' | 'restart-desktop' | 'restart-command'

// 頂端那顆按鈕做什麼：有要重啟的就重啟（重新載入不會生效）；桌面版自己重啟後端，
// 網頁版的後端是使用者在終端機開的，只能告訴他指令。
export const pendingAction = (needsRestart: boolean, canRestartHere: boolean): PendingAction => {
  if (!needsRestart) return 'reload'
  return canRestartHere ? 'restart-desktop' : 'restart-command'
}

export function pendingLabelKeys(keys: string[]): string[] {
  return keys.map((key) => (
    (PENDING_KEYS as readonly string[]).includes(key)
      ? `settings.pending.items.${key}`
      : 'settings.pending.items.other'
  ))
}
