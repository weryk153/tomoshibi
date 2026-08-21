/**
 * 雙指縮放的數學。
 *
 * 原本模型只能用滑鼠滾輪縮放（use-live2d-resize 只綁了 wheel），手機沒有滾輪
 * 也沒有接 pinch，所以在手機上完全沒辦法調整角色大小。
 *
 * 抽成純函式是為了測得到：這段算錯不會拋錯，只會表現成「縮放怪怪的」——縮太
 * 快、反向、或縮到看不見就再也拉不回來。手勢很難用手動測試重現同樣的輸入。
 */

export interface PointerPos {
  x: number
  y: number
}

export function pointerDistance(a: PointerPos, b: PointerPos): number {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

/**
 * 由手指張開的比例算出新的縮放值。
 *
 * 用「起始距離 → 現在距離」的比例乘上「手勢開始時的縮放」，而不是每次移動都
 * 累加增量：累加會讓誤差隨手指抖動一路漂移，手指回到原位時大小卻回不去。
 */
export function pinchScale(
  startDistance: number,
  currentDistance: number,
  startScale: number,
  minScale: number,
  maxScale: number,
): number {
  // 兩指重疊時距離是 0，相除會得到 Infinity／NaN，直接讓縮放停在原地。
  if (!Number.isFinite(startDistance) || startDistance <= 0) return startScale
  if (!Number.isFinite(currentDistance) || currentDistance <= 0) return startScale

  const raw = startScale * (currentDistance / startDistance)
  if (!Number.isFinite(raw)) return startScale
  return Math.min(maxScale, Math.max(minScale, raw))
}
