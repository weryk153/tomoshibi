import { test } from 'node:test'
import assert from 'node:assert/strict'
import { clampCap, isValidConsolidation } from './memory.ts'

test('cap 夾在後端接受的 [500, 8000] 範圍內', () => {
  assert.equal(clampCap(100), 500)
  assert.equal(clampCap(500), 500)
  assert.equal(clampCap(4000), 4000)
  assert.equal(clampCap(8000), 8000)
  assert.equal(clampCap(99999), 8000)
})

test('cap 收到非數字時回傳下界而不是 NaN——NaN 會讓後端回 400 且訊息難懂', () => {
  assert.equal(clampCap(Number.NaN), 500)
})

test('consolidation 只接受後端允許的 1 / 3 / 5', () => {
  assert.equal(isValidConsolidation(1), true)
  assert.equal(isValidConsolidation(3), true)
  assert.equal(isValidConsolidation(5), true)
  assert.equal(isValidConsolidation(2), false)
  assert.equal(isValidConsolidation(0), false)
})

import { mapMemoryResponse } from './memory.ts'

test('GET 回應裡的 self 欄位會被帶進 MemoryState', () => {
  const state = mapMemoryResponse({
    conf_uid: 'aoi',
    enabled: true,
    content: '對方叫小明。',
    exists: true,
    char_count: 6,
    cap: 1500,
    cap_min: 500,
    cap_max: 8000,
    consolidation_interval: 1,
    consolidation_interval_choices: [1, 3, 5],
    self_content: '她喜歡咖啡。',
    self_char_count: 6,
    self_cap: 800,
  })
  assert.equal(state.self_content, '她喜歡咖啡。')
  assert.equal(state.self_char_count, 6)
  assert.equal(state.self_cap, 800)
  assert.equal(state.content, '對方叫小明。')
})
