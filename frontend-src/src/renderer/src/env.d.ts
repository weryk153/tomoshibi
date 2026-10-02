interface Window {
  api?: {
    setIgnoreMouseEvents: (ignore: boolean) => void
    showContextMenu?: () => void
    onModeChanged: (callback: (mode: string) => void) => void
    getBackgroundPreferences?: () => Promise<{ backgroundUrl: string } | null>
    setBackgroundPreferences?: (backgroundUrl: string) => Promise<void>
    restartBackend?: () => Promise<{ ok: boolean; reason?: 'not-managed' | 'failed'; logPath?: string }>
  }
  TomoshibiEffects?: {
    play: (
      id: import('./effects/stage-effect').StageEffectId,
      options?: import('./effects/stage-effect').StageEffectOptions,
    ) => void
    stop: () => void
    list: () => import('./effects/stage-effect').StageEffectId[]
  }
}
