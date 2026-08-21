import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  keepAliveToMode, modeToKeepAlive, clampKeepAliveSeconds,
  KEEP_ALIVE_MAX,
} from './perf.ts'

test('keep_alive 的 -1 是「永久常駐」，不是負數秒', () => {
  assert.equal(keepAliveToMode(-1), 'forever')
})

test('keep_alive 的 0 是「立即卸載」，不是零秒', () => {
  assert.equal(keepAliveToMode(0), 'immediate')
})

test('其他正數才是秒數', () => {
  assert.equal(keepAliveToMode(300), 'seconds')
})

test('模式轉回數值時，forever 與 immediate 忽略秒數欄位', () => {
  assert.equal(modeToKeepAlive('forever', 300), -1)
  assert.equal(modeToKeepAlive('immediate', 300), 0)
  assert.equal(modeToKeepAlive('seconds', 300), 300)
})

test('秒數夾在 [1, 86400]——0 與負數有特殊語意，不能從秒數欄位產生', () => {
  assert.equal(clampKeepAliveSeconds(0), 1, '0 會被誤讀為「立即卸載」')
  assert.equal(clampKeepAliveSeconds(-5), 1, '負數會被誤讀為「永久常駐」')
  assert.equal(clampKeepAliveSeconds(300), 300)
  assert.equal(clampKeepAliveSeconds(999999), KEEP_ALIVE_MAX)
})

test('秒數收到非數字時回傳下界而非 NaN', () => {
  assert.equal(clampKeepAliveSeconds(Number.NaN), 1)
})

test('KEEP_ALIVE_MAX 必須等於後端的 86400，改動要讓測試失敗', () => {
  assert.equal(KEEP_ALIVE_MAX, 86400)
})

// 這個測試釘住 code review 的修正：modeToKeepAlive 的 'seconds' 分支自己要
// 呼叫 clampKeepAliveSeconds 再夾一次，不能假設呼叫端已經夾過。舊版本會
// 原封不動回傳 seconds，所以 modeToKeepAlive('seconds', 0) 會回傳 0——而 0
// 對 keep_alive 而言是「立即卸載」的旗標，不是「0 秒的保留時間」。如果 UI
// 的自訂秒數輸入框被清空成 0 卻忘記先夾，這個分支就是防止那個 0 真的送到
// setKeepAlive 的最後一道關卡。
test('modeToKeepAlive 的 seconds 分支自己夾一次，即使呼叫端忘記先夾', () => {
  assert.equal(modeToKeepAlive('seconds', 0), 1, '0 不能原封不動流出去，會被誤讀成立即卸載')
  assert.equal(modeToKeepAlive('seconds', -5), 1, '負數同理，會被誤讀成永久常駐')
  assert.equal(modeToKeepAlive('seconds', 999999), KEEP_ALIVE_MAX)
  // forever／immediate 仍然精確回傳 -1／0，不會被 seconds 分支的夾範圍波及。
  assert.equal(modeToKeepAlive('forever', 0), -1)
  assert.equal(modeToKeepAlive('immediate', 0), 0)
})
