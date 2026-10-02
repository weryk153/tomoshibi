import { test } from 'node:test'
import assert from 'node:assert/strict'
import { pendingAction, pendingLabelKeys } from './pending.ts'

test('each pending key has a label; unknown ones get a generic label', () => {
  assert.deepEqual(pendingLabelKeys(['engine', 'nope']), [
    'settings.pending.items.engine',
    'settings.pending.items.other',
  ])
})

test('only a restart item changes the button; the desktop app restarts by itself', () => {
  assert.equal(pendingAction(false, true), 'reload')
  assert.equal(pendingAction(false, false), 'reload')
  assert.equal(pendingAction(true, true), 'restart-desktop')
  assert.equal(pendingAction(true, false), 'restart-command')
})

test('the LAN switch has its own label', () => {
  assert.deepEqual(pendingLabelKeys(['host']), ['settings.pending.items.host'])
})
