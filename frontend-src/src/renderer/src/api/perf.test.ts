import { test } from 'node:test'
import assert from 'node:assert/strict'
import { presetSelection, PRESET_CUSTOM } from './perf.ts'

test('目前的數字對得上某個預設就選它', () => {
  assert.equal(presetSelection('high', ['high', 'light', 'standard']), 'high')
})

test('對不上任何預設時是「自訂」', () => {
  assert.equal(presetSelection('custom', ['high', 'light', 'standard']), PRESET_CUSTOM)
})

test('後端回了不認得的名字也當成自訂，不讓選單顯示空白', () => {
  assert.equal(presetSelection('turbo', ['high', 'light', 'standard']), PRESET_CUSTOM)
  assert.equal(presetSelection(undefined, ['high', 'light', 'standard']), PRESET_CUSTOM)
})
