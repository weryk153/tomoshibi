import { test } from 'node:test'
import assert from 'node:assert/strict'
import { describeEvent, formatGb } from './gpt-sovits.ts'

test('download progress becomes a percentage', () => {
  assert.deepEqual(
    describeEvent({ status: 'downloading', completed: 250, total: 1000 }),
    { stage: 'downloading', percent: 25 },
  )
})

test('installing is split by step', () => {
  assert.deepEqual(describeEvent({ status: 'installing', step: 'models' }), { stage: 'models', percent: null })
  assert.deepEqual(describeEvent({ status: 'installing', step: 'voice' }), { stage: 'voice', percent: null })
})

test('windows extraction carries its own percentage', () => {
  assert.deepEqual(describeEvent({ status: 'extracting', percent: 42 }), { stage: 'extracting', percent: 42 })
})

test('unknown and terminal events keep the previous state', () => {
  assert.equal(describeEvent({ status: 'success' }), null)
  assert.equal(describeEvent({ status: 'installing', step: 'something-new' }), null)
  assert.equal(describeEvent({}), null)
})

test('sizes read as gigabytes with one decimal', () => {
  assert.equal(formatGb(8_185_689_226), '8.2')
  assert.equal(formatGb(3_771_000_000), '3.8')
  assert.equal(formatGb(0), '0.1')
})
