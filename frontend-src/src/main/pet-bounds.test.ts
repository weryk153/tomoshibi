import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  spanAllDisplays, wasClamped, displayForRect, placementWithin, type Rect, type DisplayLike,
} from './pet-bounds.ts'

// 實機量到的配置（[PETDBG] 印出來的）：內建 Retina 是主要顯示器，外接 1080p 在上面
// 偏左 206px。
const BUILT_IN: DisplayLike = {
  bounds: { x: 0, y: 0, width: 1512, height: 982 },
  workArea: { x: 0, y: 37, width: 1512, height: 945 },
}
const EXTERNAL: DisplayLike = {
  bounds: { x: -206, y: -1080, width: 1920, height: 1080 },
  workArea: { x: -206, y: -1055, width: 1920, height: 1055 },
}
const DISPLAYS = [BUILT_IN, EXTERNAL]

// 切換前視窗在內建螢幕上，中心 (756, 435)。
const SOURCE: Rect = { x: 306, y: 100, width: 900, height: 670 }

test('鋪滿所有螢幕是兩台的聯集', () => {
  assert.deepEqual(spanAllDisplays(DISPLAYS), {
    x: -206, y: -1080, width: 1920, height: 2062,
  })
})

test('macOS 把視窗夾成單一螢幕時認得出來', () => {
  // 實機拿到的：要 2062 高，只給 1055（外接螢幕扣掉選單列）。
  // 「顯示器各自使用單獨的 Space」預設開著，視窗不能跨螢幕。
  const requested: Rect = { x: -206, y: -1080, width: 1920, height: 2062 }
  const actual: Rect = { x: -206, y: -1055, width: 1920, height: 1055 }

  assert.equal(wasClamped(requested, actual), true)
})

test('拿到要求的尺寸就不算被夾', () => {
  const requested: Rect = { x: -206, y: -1080, width: 1920, height: 2062 }

  assert.equal(wasClamped(requested, { ...requested }), false)
  // 差一兩個像素是取整，不是被夾。
  assert.equal(wasClamped(requested, { ...requested, height: 2061 }), false)
})

test('退回時選的是角色原本那台螢幕，不是主要顯示器', () => {
  // 這是整個修正的重點：視窗被夾到外接螢幕，但使用者是在內建螢幕上切的。
  assert.equal(displayForRect(DISPLAYS, SOURCE), BUILT_IN)
})

test('視窗中心不在任何螢幕上時退回最近的一台', () => {
  // 螢幕拔掉之後視窗座標可能留在已經不存在的區域。
  const orphan: Rect = { x: 5000, y: 5000, width: 400, height: 300 }

  assert.equal(displayForRect(DISPLAYS, orphan), BUILT_IN)
})

test('角色位置是視窗中心相對於桌寵視窗左上角的偏移', () => {
  assert.deepEqual(placementWithin(BUILT_IN.workArea, SOURCE), { x: 756, y: 398 })
})

test('角色位置夾在桌寵視窗之內', () => {
  // 切換前的視窗有可能一半在螢幕外；算出來的位置不能跑到畫布外面，
  // 不然角色會被放到看不見的地方。
  const offscreen: Rect = { x: -900, y: -900, width: 400, height: 300 }
  const placement = placementWithin(BUILT_IN.workArea, offscreen)

  assert.ok(placement.x >= 0 && placement.x <= BUILT_IN.workArea.width)
  assert.ok(placement.y >= 0 && placement.y <= BUILT_IN.workArea.height)
})
