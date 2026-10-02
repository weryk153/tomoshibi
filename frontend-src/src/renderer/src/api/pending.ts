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

export type PendingAction = 'reload' | 'restart-desktop' | 'restart-failed' | 'restart-command'

// 這裡能不能重啟後端：桌面版 app 自己起的才能（available）；網頁版或後端不是 app
// 起的就不能（unavailable）；桌面版剛試過、失敗了（failed）。
export type DesktopRestart = 'available' | 'unavailable' | 'failed'

// 頂端那顆按鈕做什麼：有要重啟的就重啟（重新載入不會生效）。桌面版自己重啟後端；
// 失敗時說失敗、給重試與記錄檔位置——用 app 的人沒有終端機可以照著打指令。網頁版
// 的後端是使用者在終端機開的，只能告訴他指令。
export const pendingAction = (needsRestart: boolean, desktop: DesktopRestart): PendingAction => {
  if (!needsRestart) return 'reload'
  if (desktop === 'available') return 'restart-desktop'
  if (desktop === 'failed') return 'restart-failed'
  return 'restart-command'
}

export function pendingLabelKeys(keys: string[]): string[] {
  return keys.map((key) => (
    (PENDING_KEYS as readonly string[]).includes(key)
      ? `settings.pending.items.${key}`
      : 'settings.pending.items.other'
  ))
}

// 要重啟後端才生效的項目（跟後端 pending_changes.RESTART_KEYS 一致）。
export const RESTART_KEYS: readonly string[] = ['host']

// 清單裡還有重新載入就會生效的項目嗎：有的話就算同時在等重啟，也要留著重新載入鈕
// （網頁版只能給重啟指令，不能讓其他項目跟著卡住）。
export const hasReloadItems = (keys: string[]): boolean =>
  keys.some((key) => !RESTART_KEYS.includes(key))
