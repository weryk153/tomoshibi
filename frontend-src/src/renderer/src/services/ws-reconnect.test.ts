import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  reconnectDelayMs, shouldAutoReconnect, isHeartbeatStale, MAX_RECONNECT_DELAY_MS,
} from './ws-reconnect.ts'

test('第一次重連很快，之後逐次加倍', () => {
  // 手機切回前景時斷線通常已經發生了一陣子，第一次要快，不然使用者會以為壞了。
  assert.equal(reconnectDelayMs(0), 1000)
  assert.equal(reconnectDelayMs(1), 2000)
  assert.equal(reconnectDelayMs(2), 4000)
  assert.equal(reconnectDelayMs(3), 8000)
})

test('延遲有上限，不會退避到天荒地老', () => {
  // 後端可能只是重啟中。無上限的話第十次就要等十七分鐘，實際上等於不會再連上。
  assert.equal(reconnectDelayMs(10), MAX_RECONNECT_DELAY_MS)
  assert.equal(reconnectDelayMs(100), MAX_RECONNECT_DELAY_MS)
})

test('負數或壞的次數視為第一次，不可以回 NaN 或負值', () => {
  assert.equal(reconnectDelayMs(-1), 1000)
  assert.equal(reconnectDelayMs(Number.NaN), 1000)
})

test('使用者自己按斷線時不要自動重連', () => {
  // 不然設定頁的「斷線」按鈕會變成按了也沒用。
  assert.equal(shouldAutoReconnect({ intentional: true, url: 'ws://x/client-ws' }), false)
})

test('非預期斷線且有連過的位址時要重連', () => {
  assert.equal(shouldAutoReconnect({ intentional: false, url: 'ws://x/client-ws' }), true)
})

test('從來沒連過就沒有位址可重連', () => {
  assert.equal(shouldAutoReconnect({ intentional: false, url: null }), false)
})

test('剛收到 ack 就不算卡住', () => {
  assert.equal(isHeartbeatStale(1_000_000, 1_000_000, 25_000, 2), false)
})

test('還沒超過容許漏掉的次數就不算卡住', () => {
  // 容許漏 2 次＝50 秒。49 秒還在範圍內，不要因為一次網路抖動就砍掉連線重連。
  assert.equal(isHeartbeatStale(1_000_000, 1_000_000 + 49_000, 25_000, 2), false)
})

test('超過容許次數就當成卡住', () => {
  // 連線「卡住但沒關閉」時 onclose 永遠不會來，沒有這個判斷就會安靜地再也
  // 收不到任何訊息——畫面看起來是連著的。
  assert.equal(isHeartbeatStale(1_000_000, 1_000_000 + 51_000, 25_000, 2), true)
})

test('從來沒收過 ack 時不算卡住', () => {
  // 剛連上、第一個 ack 還沒回來的空窗期不能誤判成斷線。
  assert.equal(isHeartbeatStale(null, 1_000_000, 25_000, 2), false)
})
