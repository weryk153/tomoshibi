import { test } from 'node:test'
import assert from 'node:assert/strict'
import { anyInvalidWeightDraft, removeWeightDraft } from './weight-drafts.ts'

test('removing an entry drops its draft and shifts the later ones down', () => {
  const texts = { 'head#0': '2', 'head#1': '5', 'head#2': '', 'body#1': '3' }
  assert.deepEqual(removeWeightDraft(texts, 'head', 1), { 'head#0': '2', 'head#1': '', 'body#1': '3' })
})

test('a draft for an entry that no longer exists never blocks saving', () => {
  const entries = { head: [{ weight: 1 }] }
  assert.equal(anyInvalidWeightDraft({ 'head#1': '' }, entries), false)
  assert.equal(anyInvalidWeightDraft({ 'head#0': '' }, entries), true)
  assert.equal(anyInvalidWeightDraft({ 'head#0': '3' }, entries), false)
})
