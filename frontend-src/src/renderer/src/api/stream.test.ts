import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  blocklistFromText, blocklistToText, parseQuietSeconds, startBlockedKey, type StreamStatus,
} from './stream.ts'

const idle: StreamStatus = {
  live: false,
  stage_connected: true,
  chat: 'idle',
  read: 0,
  dropped: 0,
  queued: 0,
  current: null,
  stopped_reason: null,
  last_error: '',
  history_uid: null,
}

test('黑名單一行一個，去頭尾空白、去空行、去重複', () => {
  assert.deepEqual(blocklistFromText(' 笨蛋 \n\nbaka\n笨蛋\n'), ['笨蛋', 'baka'])
  assert.equal(blocklistToText(['笨蛋', 'baka']), '笨蛋\nbaka')
})

test('冷場秒數只收 5～3600 的整數', () => {
  assert.equal(parseQuietSeconds('30'), 30)
  assert.equal(parseQuietSeconds(' 45 '), 45)
  assert.equal(parseQuietSeconds('4'), null)
  assert.equal(parseQuietSeconds('3601'), null)
  assert.equal(parseQuietSeconds('1.5'), null)
  assert.equal(parseQuietSeconds(''), null)
})

test('開始按鈕不能按的原因', () => {
  assert.equal(startBlockedKey(null, 'x'), 'settings.stream.loading')
  assert.equal(startBlockedKey({ ...idle, stage_connected: false }, 'x'), 'settings.stream.needStage')
  assert.equal(startBlockedKey(idle, '  '), 'settings.stream.needUrl')
  assert.equal(startBlockedKey(idle, 'https://youtu.be/abcdefghijk'), null)
  assert.equal(startBlockedKey({ ...idle, live: true, stage_connected: false }, ''), null)
})
