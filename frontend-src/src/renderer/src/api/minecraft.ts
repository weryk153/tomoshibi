// Minecraft 分頁的 REST 包裝與純函式。不含 React，所以能用 node:test 驗證。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export interface MinecraftSettings {
  mindserver_url: string
  bot_name: string
  idle_seconds: number
  idle_cooldown_seconds: number
  event_cooldown_seconds: number
  tool_timeout_seconds: number
  failure_limit: number
  notable_items: string[]
}

export interface MinecraftStatus {
  live: boolean
  connected: boolean
  in_game: boolean
  pending: number
  health: number | null
  action: string
  current: string | null
  // null：還沒停過；failures：連續失敗暫停；stopped：按了停止；error：程式出錯
  stopped_reason: string | null
  last_error: string
}

export interface MinecraftInfo {
  settings: MinecraftSettings
  status: MinecraftStatus
}

export const fetchMinecraft = (baseUrl: string): Promise<ApiResult<MinecraftInfo>> =>
  apiGet<MinecraftInfo>(baseUrl, '/api/minecraft')

export const saveMinecraftSettings = (
  baseUrl: string,
  changes: Partial<MinecraftSettings>,
): Promise<ApiResult<{ settings: MinecraftSettings }>> =>
  apiPost<{ settings: MinecraftSettings }>(baseUrl, '/api/minecraft/settings', changes)

// 失敗時 error 是後端的原因代號（already_live／no_bot_name／not_running）。
export const startMinecraft = (baseUrl: string): Promise<ApiResult<MinecraftStatus>> =>
  apiPost<MinecraftStatus>(baseUrl, '/api/minecraft/start', {})

export const stopMinecraft = (baseUrl: string): Promise<ApiResult<MinecraftStatus>> =>
  apiPost<MinecraftStatus>(baseUrl, '/api/minecraft/stop', {})

export function linesToItems(text: string): string[] {
  const items: string[] = []
  for (const line of text.split('\n')) {
    const item = line.trim()
    if (item && !items.includes(item)) items.push(item)
  }
  return items
}

export function itemsToLines(items: readonly string[]): string {
  return items.join('\n')
}

export function parseSeconds(text: string, min: number, max: number): number | null {
  const trimmed = text.trim()
  if (!/^\d+$/.test(trimmed)) return null
  const value = Number(trimmed)
  return value >= min && value <= max ? value : null
}

// 開始按鈕不能按的原因（i18n 鍵）；開著時按鈕是「停止」，永遠能按。
export function startBlockedKey(status: MinecraftStatus | null, botName: string): string | null {
  if (!status) return 'settings.minecraft.loading'
  if (status.live) return null
  if (!botName.trim()) return 'settings.minecraft.needBotName'
  return null
}
