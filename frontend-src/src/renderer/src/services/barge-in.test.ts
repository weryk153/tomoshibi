import { test } from 'node:test'
import assert from 'node:assert/strict'
import { BARGE_IN_AFTER_MS, speechEndAction } from './barge-in.ts'

test('她講話時你出聲不到一秒就停：當成附和，丟掉，不打斷她', () => {
  assert.equal(speechEndAction({ duringHerTurn: true, bargedIn: false }), 'drop')
})

test('講超過一秒（已經插話）：照常送出', () => {
  assert.equal(speechEndAction({ duringHerTurn: true, bargedIn: true }), 'send')
})

test('她沒在講話時，多短都照常送出', () => {
  assert.equal(speechEndAction({ duringHerTurn: false, bargedIn: false }), 'send')
})

test('插話門檻是一秒', () => {
  assert.equal(BARGE_IN_AFTER_MS, 1000)
})
