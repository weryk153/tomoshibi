/**
 * 桌寵模式的初始定位：要等畫布真的變大之後才能算座標。
 *
 * 桌寵視窗會鋪滿「所有螢幕合起來」的範圍，然後把角色移到他切換前所在的那台螢幕。
 * 座標是用 view._deviceToScreen 從畫面像素換算成模型座標的，所以換算的前提是畫布
 * 已經是合併桌面的尺寸。
 *
 * 舊版用一個 50ms 計時器賭這件事已經發生，而重試迴圈只在 canvas/view/model 不存在
 * 時重試——畫布還是視窗模式的舊尺寸時它照樣算下去。算出來的座標遠在畫面之外，角色
 * 被扔出去（看起來像一瞬間消失），最後停在合併桌面的幾何中心。
 *
 * 兩台螢幕上下排的時候那個中心不在任何一台的中間：內建 Retina（1512×982 DIP，主要）
 * 加上方的外接 1920×1080，合起來高 2062、中心在 1031，而內建螢幕的上緣在 1080——
 * 中心點差 49 就落在外接螢幕上。使用者看到的「跑到上方螢幕」就是這個。
 *
 * 所以不賭：主程序把畫布應該多大一起送過來，這裡等到畫布真的是那個尺寸。
 */

export interface CanvasSize {
  width: number
  height: number
}

export type PlacementDecision = 'apply' | 'retry' | 'give-up'

/**
 * clientWidth／clientHeight 是整數化過的，跟主程序用螢幕邊界算出來的 DIP 尺寸差
 * 一兩個像素是正常的，不該因此一直等下去。
 */
const SIZE_TOLERANCE_PX = 2

function hasSize(size: CanvasSize | null): size is CanvasSize {
  return !!size && size.width > 0 && size.height > 0
}

/**
 * 現在能不能套用定位。
 *
 * @param actual 畫布目前的 CSS 尺寸（clientWidth／clientHeight），還沒掛上時傳 null
 * @param expected 主程序算出來的合併桌面尺寸；舊版主程序不會送，傳 null
 * @param retriesLeft 還剩幾次重試機會
 *
 * `give-up` 不是可有可無的分支：主程序要等這邊回報才把視窗顯示出來，永遠不回報
 * 就等於視窗永遠不出現。等不到也要說一聲。
 */
export function decidePlacement(
  actual: CanvasSize | null,
  expected: CanvasSize | null,
  retriesLeft: number,
): PlacementDecision {
  const wait = (): PlacementDecision => (retriesLeft > 0 ? 'retry' : 'give-up')

  if (!hasSize(actual)) return wait()

  // 沒有目標尺寸可比（舊版主程序，或主程序自己算出 0）——有畫布就先套用，
  // 那是舊行為，總比完全不定位好。
  if (!hasSize(expected)) return 'apply'

  const matches =
    Math.abs(actual.width - expected.width) <= SIZE_TOLERANCE_PX &&
    Math.abs(actual.height - expected.height) <= SIZE_TOLERANCE_PX

  return matches ? 'apply' : wait()
}
