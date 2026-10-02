import { test } from 'node:test'
import assert from 'node:assert/strict'
import { activePersonaBody } from './personas.ts'

test('choosing a persona names the character it is for', () => {
  assert.deepEqual(activePersonaBody('himmel', 'gentle'), { conf_uid: 'himmel', persona_id: 'gentle' })
})

test('going back to the character\'s own persona sends null, not an empty string', () => {
  assert.deepEqual(activePersonaBody('himmel', null), { conf_uid: 'himmel', persona_id: null })
})
