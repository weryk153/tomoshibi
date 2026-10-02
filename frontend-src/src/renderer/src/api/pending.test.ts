import { test } from 'node:test'
import assert from 'node:assert/strict'
import { pendingLabelKeys } from './pending.ts'

test('each pending key has a label; unknown ones get a generic label', () => {
  assert.deepEqual(pendingLabelKeys(['engine', 'nope']), [
    'settings.pending.items.engine',
    'settings.pending.items.other',
  ])
})
