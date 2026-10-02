import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  loadImageQuality, loadImageMaxWidth, DEFAULT_IMAGE_COMPRESSION_QUALITY, DEFAULT_IMAGE_MAX_WIDTH,
} from './image-settings.ts'

test('a stored quality inside 0.1–1 is used', () => {
  assert.equal(loadImageQuality('0.5'), 0.5)
})

test('missing or broken quality falls back to the default', () => {
  for (const stored of [null, '', 'abc', '0', '1.5']) {
    assert.equal(loadImageQuality(stored), DEFAULT_IMAGE_COMPRESSION_QUALITY, String(stored))
  }
})

test('a stored width of zero or more is used; anything else falls back', () => {
  assert.equal(loadImageMaxWidth('1280'), 1280)
  assert.equal(loadImageMaxWidth('0'), 0)
  for (const stored of [null, 'abc', '-5']) {
    assert.equal(loadImageMaxWidth(stored), DEFAULT_IMAGE_MAX_WIDTH, String(stored))
  }
})
