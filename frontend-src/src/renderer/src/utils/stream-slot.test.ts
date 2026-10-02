import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createStreamSlot } from './stream-slot.ts'

function fakeStream() {
  const tracks = [{ stopped: false, stop() { this.stopped = true } }]
  return { tracks, getTracks: () => tracks, get stopped() { return tracks.every((t) => t.stopped) } }
}

test('a camera stream that arrives after the scene was left is stopped, not kept', () => {
  const slot = createStreamSlot<ReturnType<typeof fakeStream>>()
  const token = slot.begin()
  slot.stop() // 換走了，getUserMedia 還沒回來
  const late = fakeStream()
  assert.equal(slot.accept(token, late), false)
  assert.equal(late.stopped, true)
  assert.equal(slot.current(), null)
})

test('starting again stops the stream that was already running', () => {
  const slot = createStreamSlot<ReturnType<typeof fakeStream>>()
  const first = fakeStream()
  assert.equal(slot.accept(slot.begin(), first), true)
  const second = fakeStream()
  assert.equal(slot.accept(slot.begin(), second), true)
  assert.equal(first.stopped, true)
  assert.equal(slot.current(), second)
})

test('of two overlapping starts only the last one is kept', () => {
  const slot = createStreamSlot<ReturnType<typeof fakeStream>>()
  const older = slot.begin()
  const newer = slot.begin()
  const a = fakeStream()
  const b = fakeStream()
  assert.equal(slot.accept(newer, b), true)
  assert.equal(slot.accept(older, a), false)
  assert.equal(a.stopped, true)
  assert.equal(b.stopped, false)
})

test('stop turns the running camera off', () => {
  const slot = createStreamSlot<ReturnType<typeof fakeStream>>()
  const stream = fakeStream()
  slot.accept(slot.begin(), stream)
  slot.stop()
  assert.equal(stream.stopped, true)
  assert.equal(slot.current(), null)
})
