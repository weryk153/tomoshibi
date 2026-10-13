import { test } from 'node:test'
import assert from 'node:assert/strict'
import { SETTINGS_TABS, DEFAULT_SETTINGS_TAB } from './settings-tabs.ts'

test('eight tabs, character first, stream and minecraft on their own pages', () => {
  assert.deepEqual(
    SETTINGS_TABS.map((tab) => tab.id),
    ['character', 'conversation', 'stage', 'stream', 'minecraft', 'models', 'perf', 'system'],
  )
  assert.equal(DEFAULT_SETTINGS_TAB, 'character')
})

test('every tab has its own label key', () => {
  const keys = SETTINGS_TABS.map((tab) => tab.labelKey)
  assert.equal(new Set(keys).size, keys.length)
  keys.forEach((key) => assert.match(key, /^settings\.tabs\./))
})
