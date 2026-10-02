import { test } from 'node:test'
import assert from 'node:assert/strict'
import { interactionSettingsOf } from './canvas-interaction.ts'

test('never-set switches show what the canvas actually does: all on', () => {
  assert.deepEqual(interactionSettingsOf(undefined), {
    pointerInteractive: true, scrollToResize: true, lookAtPointer: true,
  })
  assert.deepEqual(interactionSettingsOf({}), {
    pointerInteractive: true, scrollToResize: true, lookAtPointer: true,
  })
})

test('a switch the user turned off stays off', () => {
  assert.deepEqual(interactionSettingsOf({ pointerInteractive: false }), {
    pointerInteractive: false, scrollToResize: true, lookAtPointer: true,
  })
})
