import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isStagePage, stageBackgroundHidden, withStageParam } from './stage-mode.ts'

test('只有 stage=1 才是舞台頁', () => {
  assert.equal(isStagePage('?stage=1'), true)
  assert.equal(isStagePage('?bg=none&stage=1'), true)
  assert.equal(isStagePage(''), false)
  assert.equal(isStagePage('?stage=0'), false)
  assert.equal(isStagePage('?stage'), false)
})

test('bg=none 時背景透明', () => {
  assert.equal(stageBackgroundHidden('?stage=1&bg=none'), true)
  assert.equal(stageBackgroundHidden('?stage=1'), false)
})

test('舞台頁連 WebSocket 時帶 stage=1，保留原本的位址', () => {
  assert.equal(withStageParam('ws://127.0.0.1:12393/client-ws'), 'ws://127.0.0.1:12393/client-ws?stage=1')
  assert.equal(
    withStageParam('wss://host.example.ts.net/client-ws?x=1'),
    'wss://host.example.ts.net/client-ws?x=1&stage=1',
  )
})

test('設定裡存了壞掉的位址也不能讓頁面炸掉', () => {
  // wsUrl 來自 localStorage，使用者在一般分頁可以打任何字。
  assert.equal(withStageParam('not a url'), 'not a url')
})
