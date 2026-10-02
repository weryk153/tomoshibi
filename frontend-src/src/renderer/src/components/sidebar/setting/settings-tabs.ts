// 設定抽屜的分頁。順序照規格：先是角色，再是全域的對話、舞台、直播、模型、
// 效能、系統。每個分頁長什麼樣在 setting-ui.tsx；這裡只放順序與標籤，好測。
export type SettingsTabId =
  | 'character' | 'conversation' | 'stage' | 'stream' | 'models' | 'perf' | 'system'

export const SETTINGS_TABS: readonly { id: SettingsTabId; labelKey: string }[] = [
  { id: 'character', labelKey: 'settings.tabs.characters' },
  { id: 'conversation', labelKey: 'settings.tabs.conversation' },
  { id: 'stage', labelKey: 'settings.tabs.stage' },
  { id: 'stream', labelKey: 'settings.tabs.stream' },
  { id: 'models', labelKey: 'settings.tabs.models' },
  { id: 'perf', labelKey: 'settings.tabs.perf' },
  { id: 'system', labelKey: 'settings.tabs.system' },
]

export const DEFAULT_SETTINGS_TAB: SettingsTabId = 'character'
