import { test } from 'node:test'
import assert from 'node:assert/strict'
import { clampIntervalHours, normalizeTopics, MAX_TOPICS } from './topics.ts'

test('clampIntervalHours 夾在 1 到 24 之間', () => {
  assert.equal(clampIntervalHours(0), 1)
  assert.equal(clampIntervalHours(-5), 1)
  assert.equal(clampIntervalHours(1), 1)
  assert.equal(clampIntervalHours(6), 6)
  assert.equal(clampIntervalHours(24), 24)
  assert.equal(clampIntervalHours(25), 24)
  assert.equal(clampIntervalHours(1000), 24)
})

test('clampIntervalHours 把小數四捨五入成整數', () => {
  assert.equal(clampIntervalHours(3.4), 3)
  assert.equal(clampIntervalHours(3.6), 4)
})

test('clampIntervalHours 對 NaN 回傳預設值 6', () => {
  assert.equal(clampIntervalHours(Number.NaN), 6)
})

test('normalizeTopics 去除前後空白', () => {
  assert.deepEqual(normalizeTopics(['  科技 ', 'AI']), ['科技', 'AI'])
})

test('normalizeTopics 丟掉純空白與空字串', () => {
  assert.deepEqual(normalizeTopics(['科技', '   ', '', 'AI']), ['科技', 'AI'])
})

test('normalizeTopics 去重且保留首次出現的順序', () => {
  assert.deepEqual(normalizeTopics(['AI', '科技', 'AI', ' 科技 ']), ['AI', '科技'])
})

test('normalizeTopics 保留大小寫差異，不視為重複', () => {
  assert.deepEqual(normalizeTopics(['ai', 'AI']), ['ai', 'AI'])
})

// 釘住「去掉前後空白」與「去重」是同一次 trim 之後再判斷——若實作先去重
// 再 trim（順序顛倒），' 科技 ' 與 '科技' 在去重階段還沒被視為同一個字串，
// 就會漏判成兩筆，這裡確保兩段邏輯合起來的最終結果是對的。
test('normalizeTopics 去重比對的是 trim 之後的值，不是原始字串', () => {
  assert.deepEqual(normalizeTopics([' 科技', '科技 ', '  科技  ']), ['科技'])
})

// MAX_TOPICS 直接斷言等於後端 topics_route.py 的 MAX_TOPICS=30——改動這個
// 常數要讓測試失敗，不能讓測試自己用這個常數建構樣本再打勾（跟 perf.test.ts
// 釘住 KEEP_ALIVE_MAX 是同一種做法）。
test('MAX_TOPICS 必須等於後端的 30', () => {
  assert.equal(MAX_TOPICS, 30)
})
