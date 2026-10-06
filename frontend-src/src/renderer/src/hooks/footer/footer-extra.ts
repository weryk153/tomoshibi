// 底部列面板比它那一格（layout 的 FOOTER_HEIGHT）高出多少。
//
// 輸入框長到第二、三行時，面板貼著底部往上長、蓋到畫布上（footer-styles.tsx）。
// 字幕是照 FOOTER_HEIGHT 擺的，不知道面板長高了，就會被蓋住——所以 footer 把
// 這個差值寫進 CSS 變數 --footer-extra，字幕的 bottom 加上它。
//
// 純函式，沒有 import：node --test 直接載入。

export interface FooterExtraInput {
  /** 面板實際高度（offsetHeight，不受 transform 影響）。 */
  panelHeight: number;
  /** 面板所在那一格的高度：展開時是 FOOTER_HEIGHT，收合時是 28px。 */
  slotHeight: number;
  collapsed: boolean;
}

/** 往上多長出來的像素，取整數；收合時一律 0（多出來的那段是往下藏在畫面外）。 */
export function footerExtra({ panelHeight, slotHeight, collapsed }: FooterExtraInput): number {
  if (collapsed) return 0;
  return Math.max(0, Math.round(panelHeight - slotHeight));
}
