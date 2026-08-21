import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  pickPrimaryUrl, shouldWarnMicNeedsHttps, type NetworkInfo,
} from './network.ts'

// 共用的最小骨架，每個測試只覆寫要測的欄位，其餘保持「無網址、無 https、
// 伺服器只收 loopback」這個最安全的預設值，避免遺漏欄位造成假陽性。
const base: NetworkInfo = {
  urls: [],
  port: 12393,
  scheme: 'http',
  https_url: null,
  localhost_only: true,
  mic_needs_https: true,
}

test('有 https_url 時一律選它——麥克風需要安全內容，LAN 的 http 給不了', () => {
  const info: NetworkInfo = {
    ...base,
    https_url: 'https://example.ts.net',
    localhost_only: false,
    urls: [{ type: 'lan', ip: '192.168.1.5', url: 'http://192.168.1.5:12393' }],
  }
  assert.equal(pickPrimaryUrl(info), 'https://example.ts.net')
})

test('沒有 https_url、但伺服器真的對外開放時，退回可連得上的 LAN 網址', () => {
  const info: NetworkInfo = {
    ...base,
    localhost_only: false,
    urls: [{ type: 'lan', ip: '192.168.1.5', url: 'http://192.168.1.5:12393' }],
  }
  assert.equal(pickPrimaryUrl(info), 'http://192.168.1.5:12393')
})

test('localhost_only 為 true 時，即使 urls 非空也不能選——那是 OS 找得到網卡但 socket 只收 loopback 的正常狀態，那些網址連不上', () => {
  const info: NetworkInfo = {
    ...base,
    localhost_only: true,
    urls: [{ type: 'lan', ip: '192.168.1.5', url: 'http://192.168.1.5:12393' }],
  }
  assert.equal(pickPrimaryUrl(info), null)
})

test('urls 為空、也沒有 https_url 時回傳 null——沒有任何網址可秀', () => {
  const info: NetworkInfo = {
    ...base,
    localhost_only: false,
    urls: [],
  }
  assert.equal(pickPrimaryUrl(info), null)
})

test('已經有 https_url 時不要再叫使用者去設定 Tailscale Serve', () => {
  // mic_needs_https 講的是「你現在看的這個網址」需要 HTTPS——從
  // http://127.0.0.1 打開設定頁時它永遠是 true。單看這個旗標就顯示
  // 「請依教學設定 Tailscale Serve」，會出現在同一畫面上方已經秀著
  // 「麥克風可用・HTTPS」和一個可用網址的情況下，自相矛盾。
  assert.equal(shouldWarnMicNeedsHttps({
    ...base, mic_needs_https: true, https_url: 'https://host.ts.net',
  }), false)
})

test('沒有 https_url 且目前是 http 時才要提醒', () => {
  assert.equal(shouldWarnMicNeedsHttps({
    ...base, mic_needs_https: true, https_url: null,
  }), true)
})

test('目前已經是 https 就不用提醒', () => {
  assert.equal(shouldWarnMicNeedsHttps({
    ...base, mic_needs_https: false, https_url: null,
  }), false)
})
