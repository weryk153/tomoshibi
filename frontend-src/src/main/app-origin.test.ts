import { test } from 'node:test'
import assert from 'node:assert/strict'
import { appOriginFor } from './app-origin.ts'

test('the packaged app page (file://) talks to its backend as that backend\'s own origin', () => {
  assert.equal(appOriginFor('null', 'http://127.0.0.1:12393/api/network/host'), 'http://127.0.0.1:12393')
  assert.equal(appOriginFor('file://', 'ws://127.0.0.1:12393/client-ws'), 'http://127.0.0.1:12393')
  assert.equal(appOriginFor('file://', 'wss://me.tail1.ts.net/client-ws'), 'https://me.tail1.ts.net')
})

test('any other origin is left alone', () => {
  assert.equal(appOriginFor('https://evil.example', 'http://127.0.0.1:12393/api/x'), null)
  assert.equal(appOriginFor(undefined, 'http://127.0.0.1:12393/api/x'), null)
  assert.equal(appOriginFor('http://localhost:5173', 'http://127.0.0.1:12393/api/x'), null)
})
