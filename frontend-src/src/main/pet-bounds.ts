/**
 * 桌寵視窗要放在哪一台螢幕。
 *
 * 上游的設計是把視窗鋪滿「所有螢幕的聯集」，這樣角色可以被拖到任何一台。實機量到
 * 的結果是 macOS 根本不給：
 *
 *     要求 {x:-206, y:-1080, width:1920, height:2062}
 *     拿到 {x:-206, y:-1055, width:1920, height:1055}
 *
 * 「顯示器各自使用單獨的 Space」預設是開著的，視窗不能跨螢幕，系統會把它夾到其中
 * 一台。夾到哪一台不是我們能選的——看要求的範圍跟哪一台重疊得多。使用者的配置是
 * 外接 1920×1080 在上方、內建 1512×982 DIP 在下方，外接的面積比較大，所以視窗整個
 * 跑到上面那台，下方連畫布都沒有（角色拖過去就消失）。
 *
 * 這也解釋了為什麼「以前可以正常拖到下面」：程式沒變，變的是螢幕怎麼排。夾到哪一台
 * 一直都是系統在決定，只是以前剛好夾對。
 *
 * 所以不賭系統的選擇：鋪滿之後把實際拿到的範圍讀回來，發現被夾就明確指定「角色切換
 * 前所在的那一台」。Windows／Linux 上鋪滿會成功，那條路不受影響。
 */

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

export interface DisplayLike {
  bounds: Rect
  workArea: Rect
}

/** 視窗尺寸是整數化過的，差一兩個像素是取整不是被夾。 */
const CLAMP_TOLERANCE_PX = 2

/** 所有螢幕的聯集。鋪得到的平台走這條。 */
export function spanAllDisplays(displays: DisplayLike[]): Rect {
  const minX = Math.min(...displays.map((d) => d.bounds.x))
  const minY = Math.min(...displays.map((d) => d.bounds.y))
  const maxX = Math.max(...displays.map((d) => d.bounds.x + d.bounds.width))
  const maxY = Math.max(...displays.map((d) => d.bounds.y + d.bounds.height))
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}

/** 系統有沒有把視窗夾小。只看尺寸——位置被移動而尺寸沒少，畫布還是完整的。 */
export function wasClamped(requested: Rect, actual: Rect): boolean {
  return (
    requested.width - actual.width > CLAMP_TOLERANCE_PX
    || requested.height - actual.height > CLAMP_TOLERANCE_PX
  )
}

function centreOf(rect: Rect): { x: number; y: number } {
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
}

function contains(bounds: Rect, point: { x: number; y: number }): boolean {
  return (
    point.x >= bounds.x
    && point.x < bounds.x + bounds.width
    && point.y >= bounds.y
    && point.y < bounds.y + bounds.height
  )
}

function distanceToCentre(bounds: Rect, point: { x: number; y: number }): number {
  const c = centreOf(bounds)
  return Math.hypot(c.x - point.x, c.y - point.y)
}

/**
 * 這個視窗屬於哪一台螢幕。
 *
 * 用視窗中心而不是左上角：靠邊放的視窗左上角可能落在隔壁那台上。中心不在任何一台
 * 上時（螢幕拔掉之後留下的座標）退回最近的一台，不要回 undefined 讓呼叫端去猜。
 */
export function displayForRect(displays: DisplayLike[], rect: Rect): DisplayLike {
  const centre = centreOf(rect)
  const hit = displays.find((d) => contains(d.bounds, centre))
  if (hit) return hit

  return displays.reduce((nearest, d) => (
    distanceToCentre(d.bounds, centre) < distanceToCentre(nearest.bounds, centre) ? d : nearest
  ), displays[0])
}

/**
 * 角色要放在桌寵視窗裡的哪個位置（相對於視窗左上角的 DIP 座標）。
 *
 * 夾在視窗範圍內：切換前的視窗有可能一半在螢幕外，算出來的位置跑到畫布外面的話
 * 角色會被放到看不見的地方。
 */
export function placementWithin(
  windowBounds: Rect,
  sourceBounds: Rect,
): { x: number; y: number } {
  const centre = centreOf(sourceBounds)
  return {
    x: Math.min(Math.max(centre.x - windowBounds.x, 0), windowBounds.width),
    y: Math.min(Math.max(centre.y - windowBounds.y, 0), windowBounds.height),
  }
}
