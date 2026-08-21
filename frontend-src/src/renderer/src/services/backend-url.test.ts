import { test } from 'node:test'
import assert from 'node:assert/strict'
import { deriveBaseUrl, deriveWsUrl } from './backend-url.ts'

test('由後端 serve 的頁面，位址就跟著頁面來源走', () => {
  const loc = { protocol: 'http:', host: '127.0.0.1:12393' }
  assert.equal(deriveBaseUrl(loc), 'http://127.0.0.1:12393')
  assert.equal(deriveWsUrl(loc), 'ws://127.0.0.1:12393/client-ws')
})

test('HTTPS 頁面要用 wss，不能用 ws', () => {
  // 這是手機連 Tailscale Serve 時真正壞掉的地方：https 頁面開 ws:// 會被
  // 瀏覽器當成 mixed content 直接擋掉，連錯誤都不太明顯——畫面載得出來，
  // 但永遠停在未連線。
  const loc = { protocol: 'https:', host: 'kurenmacbook-pro.tailf70fde.ts.net' }
  assert.equal(deriveWsUrl(loc), 'wss://kurenmacbook-pro.tailf70fde.ts.net/client-ws')
  assert.equal(deriveBaseUrl(loc), 'https://kurenmacbook-pro.tailf70fde.ts.net')
})

test('遠端主機名要原樣沿用，不能退回 127.0.0.1', () => {
  // 手機上的 127.0.0.1 是手機自己。寫死的預設值在本機沒問題，換一台裝置就
  // 指向那台裝置自己，這是「手機連得到頁面但後端沒通」的成因。
  const loc = { protocol: 'https:', host: 'host.example.ts.net' }
  assert.ok(!deriveWsUrl(loc).includes('127.0.0.1'))
})

test('Vite 開發伺服器要退回寫死的後端位址', () => {
  // dev:web 的頁面在 3000，後端在 12393，而且 vite.config.ts 沒有設 proxy，
  // 跟著頁面走會連到開發伺服器自己。
  const loc = { protocol: 'http:', host: 'localhost:3000' }
  assert.equal(deriveWsUrl(loc), 'ws://127.0.0.1:12393/client-ws')
  assert.equal(deriveBaseUrl(loc), 'http://127.0.0.1:12393')
})

test('非 http(s) 的來源要退回寫死的位址', () => {
  // 桌面版（electron）從 file:// 載入，location.host 是空的。
  assert.equal(deriveWsUrl({ protocol: 'file:', host: '' }), 'ws://127.0.0.1:12393/client-ws')
})

test('拿不到 location 時要退回寫死的位址，不可以炸掉', () => {
  assert.equal(deriveWsUrl(undefined), 'ws://127.0.0.1:12393/client-ws')
  assert.equal(deriveBaseUrl(undefined), 'http://127.0.0.1:12393')
})

test('host 是空字串時也退回，不能生出 ws:///client-ws', () => {
  assert.equal(deriveWsUrl({ protocol: 'http:', host: '' }), 'ws://127.0.0.1:12393/client-ws')
})
