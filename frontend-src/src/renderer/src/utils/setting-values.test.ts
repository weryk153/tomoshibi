import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseBoundedNumber, splitKeywords } from './setting-values.ts'

test('a number inside the bounds is accepted', () => {
  assert.equal(parseBoundedNumber('120', { min: 30, integer: true }), 120)
  assert.equal(parseBoundedNumber(' 0.8 ', { min: 0.1, max: 1 }), 0.8)
})

test('half-typed or out-of-range text is not a value', () => {
  for (const text of ['', ' ', '12a', '.', '-', '0.', '1e']) {
    assert.equal(parseBoundedNumber(text, { min: 0 }), null, text)
  }
  assert.equal(parseBoundedNumber('29', { min: 30, integer: true }), null)
  assert.equal(parseBoundedNumber('1.5', { min: 0, integer: true }), null)
  assert.equal(parseBoundedNumber('1.2', { min: 0.1, max: 1 }), null)
})

test('keywords split on ASCII and full-width commas', () => {
  assert.deepEqual(splitKeywords('晚安, 早安，你好、 晚安 ,,'), ['晚安', '早安', '你好'])
  assert.deepEqual(splitKeywords(''), [])
})
