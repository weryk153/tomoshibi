import { test } from 'node:test'
import assert from 'node:assert/strict'
import { decidePlacement, type CanvasSize } from './pet-placement.ts'

// 桌寵模式的視窗會鋪滿「所有螢幕合起來」的範圍，然後把角色移到他原本那台螢幕上。
// 舊版用一個 50ms 計時器賭畫布已經 resize 完就直接套用座標，而重試迴圈只在
// canvas/view/model 不存在時重試——畫布還是視窗模式的舊尺寸時不會重試，於是拿舊
// 尺寸換算座標，角色被扔到畫面外（看起來像一瞬間消失），最後停在合併桌面的幾何
// 中心。
//
// 使用者的螢幕：內建 Retina 3024×1964 @2x（主要）＋外接 1920×1080 @1x 在上方。
// 合起來高 2062，中心在 1031，而內建螢幕上緣在 1080——中心點差 49 就落在外接
// 螢幕上。「跑到上方螢幕」就是這麼來的。
//
// 所以不賭：主程序把「畫布應該多大」一起送過來，這裡等到畫布真的是那個尺寸才套用。

const EXPECTED: CanvasSize = { width: 1920, height: 2062 }

test('尺寸對上就套用', () => {
  assert.equal(decidePlacement(EXPECTED, EXPECTED, 10), 'apply')
})

test('畫布還是舊尺寸時要繼續等，不能拿舊尺寸換算', () => {
  const stale: CanvasSize = { width: 1200, height: 800 }

  assert.equal(decidePlacement(stale, EXPECTED, 10), 'retry')
})

test('次像素誤差不算不一致', () => {
  // clientWidth 是整數化過的，跟主程序算出來的 DIP 尺寸可能差一兩個像素。
  assert.equal(decidePlacement({ width: 1921, height: 2061 }, EXPECTED, 10), 'apply')
})

test('畫布還沒有尺寸就等', () => {
  assert.equal(decidePlacement({ width: 0, height: 0 }, EXPECTED, 10), 'retry')
  assert.equal(decidePlacement(null, EXPECTED, 10), 'retry')
})

test('等到次數用完就放棄，不是無限重試', () => {
  // 放棄很重要：主程序要等這邊回報才把視窗顯示出來。永遠不回報＝視窗永遠不出現。
  const stale: CanvasSize = { width: 1200, height: 800 }

  assert.equal(decidePlacement(stale, EXPECTED, 0), 'give-up')
  assert.equal(decidePlacement(null, EXPECTED, 0), 'give-up')
})

test('主程序沒送尺寸就只要求畫布不是空的', () => {
  // 舊版主程序不會送 expected。這時候沒有東西可以比對，退回舊行為總比不套用好。
  assert.equal(decidePlacement({ width: 1200, height: 800 }, null, 10), 'apply')
  assert.equal(decidePlacement({ width: 0, height: 0 }, null, 10), 'retry')
})

test('尺寸為零的期望值當成沒送', () => {
  // 主程序算錯或螢幕資訊還沒好時可能送 0。拿 0 當目標會永遠等不到。
  assert.equal(decidePlacement({ width: 1200, height: 800 }, { width: 0, height: 0 }, 10), 'apply')
})
