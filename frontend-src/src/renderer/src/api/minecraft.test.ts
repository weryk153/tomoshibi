import { test } from 'node:test'
import assert from 'node:assert/strict'
import { linesToItems, itemsToLines, parseSeconds, startBlockedKey } from './minecraft.ts'

test('items list round-trips through lines, trimmed and deduped', () => {
  assert.deepEqual(linesToItems(' diamond \n\nbread\ndiamond'), ['diamond', 'bread'])
  assert.equal(itemsToLines(['diamond', 'bread']), 'diamond\nbread')
})

test('parseSeconds enforces bounds', () => {
  assert.equal(parseSeconds('15', 3, 600), 15)
  assert.equal(parseSeconds('2', 3, 600), null)
  assert.equal(parseSeconds('abc', 3, 600), null)
})

test('start is blocked without status or bot name', () => {
  assert.equal(startBlockedKey(null, 'frieren'), 'settings.minecraft.loading')
  const status = { live: false, connected: false, in_game: false, pending: 0, health: null, action: '', current: null, stopped_reason: null, last_error: '' }
  assert.equal(startBlockedKey(status, ''), 'settings.minecraft.needBotName')
  assert.equal(startBlockedKey(status, 'frieren'), null)
  assert.equal(startBlockedKey({ ...status, live: true }, ''), null)
})
