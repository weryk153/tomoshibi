import { test } from 'node:test'
import assert from 'node:assert/strict'
import { hasReloadItems, pendingAction, pendingLabelKeys } from './pending.ts'

test('each pending key has a label; unknown ones get a generic label', () => {
  assert.deepEqual(pendingLabelKeys(['engine', 'nope']), [
    'settings.pending.items.engine',
    'settings.pending.items.other',
  ])
})

test('only a restart item changes the button; the desktop app restarts by itself', () => {
  assert.equal(pendingAction(false, 'available'), 'reload')
  assert.equal(pendingAction(false, 'unavailable'), 'reload')
  assert.equal(pendingAction(true, 'available'), 'restart-desktop')
  assert.equal(pendingAction(true, 'unavailable'), 'restart-command')
})

test('a desktop restart that failed says so and offers a retry — no terminal command for app users', () => {
  assert.equal(pendingAction(true, 'failed'), 'restart-failed')
  // 失敗後就算清單變了（例如沒有要重啟的了），也不會卡在失敗畫面。
  assert.equal(pendingAction(false, 'failed'), 'reload')
})

test('the LAN switch has its own label', () => {
  assert.deepEqual(pendingLabelKeys(['host']), ['settings.pending.items.host'])
})

test('the reload button stays when some items only need a reload, even while a restart is pending', () => {
  assert.equal(hasReloadItems(['host']), false)
  assert.equal(hasReloadItems(['host', 'tools']), true)
  assert.equal(hasReloadItems([]), false)
})
