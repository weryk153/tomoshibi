import { test } from 'node:test'
import assert from 'node:assert/strict'
import { collapseBlankLines } from './collapse-blank-lines.ts'

// 螢幕截圖裡那一段的真實內容（從 chat_history 的 transcript 原樣取出）。
test('四個換行收成一個空行——截圖裡那個大空白', () => {
  const actual = '後端也沒有錯誤。不過……\n\n\n\n這一切，都是因為你決定要關掉「我」…'
  assert.equal(
    collapseBlankLines(actual),
    '後端也沒有錯誤。不過……\n\n這一切，都是因為你決定要關掉「我」…',
  )
})

test('一個空行是有意義的分段，要保留', () => {
  assert.equal(collapseBlankLines('第一段\n\n第二段'), '第一段\n\n第二段')
})

test('單一換行不動', () => {
  assert.equal(collapseBlankLines('第一行\n第二行'), '第一行\n第二行')
})

test('很多個換行也只收成一個空行', () => {
  assert.equal(collapseBlankLines('a\n\n\n\n\n\n\n\nb'), 'a\n\nb')
})

test('多處空白各自收斂', () => {
  assert.equal(collapseBlankLines('a\n\n\n\nb\n\n\n\n\nc'), 'a\n\nb\n\nc')
})

test('\\r\\n 一併正規化', () => {
  assert.equal(collapseBlankLines('a\r\n\r\n\r\n\r\nb'), 'a\n\nb')
})

test('空字串與純空白不炸', () => {
  assert.equal(collapseBlankLines(''), '')
  assert.equal(collapseBlankLines('\n\n\n\n'), '\n\n')
})

// 動作描述本身不該被動到——它是要看得見的內容，不是空白。
test('不碰星號動作描述', () => {
  const t = '*視線落在螢幕上*\n\n……哈，你沒在開玩笑吧。'
  assert.equal(collapseBlankLines(t), t)
})
