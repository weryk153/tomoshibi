// 畫布互動三個開關的預設值。實際行為（use-live2d-model、vrm-avatar）把「沒設」
// 當成開著；設定頁以前把沒設的滑鼠互動顯示成關著，看起來關了其實開著。兩邊都從
// 這裡拿預設值。
export const INTERACTION_DEFAULTS = {
  pointerInteractive: true,
  scrollToResize: true,
  lookAtPointer: true,
} as const

export const interactionSettingsOf = (
  info?: { pointerInteractive?: boolean; scrollToResize?: boolean; lookAtPointer?: boolean } | null,
): { pointerInteractive: boolean; scrollToResize: boolean; lookAtPointer: boolean } => ({
  pointerInteractive: info?.pointerInteractive ?? INTERACTION_DEFAULTS.pointerInteractive,
  scrollToResize: info?.scrollToResize ?? INTERACTION_DEFAULTS.scrollToResize,
  lookAtPointer: info?.lookAtPointer ?? INTERACTION_DEFAULTS.lookAtPointer,
})
