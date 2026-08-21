import { test } from 'node:test'
import assert from 'node:assert/strict'
import { pinchScale, pointerDistance } from './pinch-zoom.ts'

const MIN = 0.1
const MAX = 5.0

test('兩點距離', () => {
  assert.equal(pointerDistance({ x: 0, y: 0 }, { x: 3, y: 4 }), 5)
  assert.equal(pointerDistance({ x: 10, y: 10 }, { x: 10, y: 10 }), 0)
})

test('手指張開一倍，大小就變一倍', () => {
  assert.equal(pinchScale(100, 200, 1, MIN, MAX), 2)
})

test('手指收合一半，大小就減半', () => {
  assert.equal(pinchScale(200, 100, 1, MIN, MAX), 0.5)
})

test('手指回到起始距離時，大小要回到手勢開始時的值', () => {
  // 用比例而不是累加增量的理由：累加會讓誤差隨手指抖動一路漂移，
  // 手指回到原位大小卻回不去。
  assert.equal(pinchScale(150, 150, 0.8, MIN, MAX), 0.8)
})

test('放大有上限', () => {
  assert.equal(pinchScale(10, 10000, 1, MIN, MAX), MAX)
})

test('縮小有下限，不能縮到看不見就再也拉不回來', () => {
  assert.equal(pinchScale(10000, 1, 1, MIN, MAX), MIN)
})

test('兩指重疊（距離 0）時停在原地，不可以回 Infinity 或 NaN', () => {
  assert.equal(pinchScale(0, 100, 1.5, MIN, MAX), 1.5)
  assert.equal(pinchScale(100, 0, 1.5, MIN, MAX), 1.5)
})

test('壞的輸入停在原地', () => {
  assert.equal(pinchScale(Number.NaN, 100, 1.5, MIN, MAX), 1.5)
  assert.equal(pinchScale(100, Number.NaN, 1.5, MIN, MAX), 1.5)
})
