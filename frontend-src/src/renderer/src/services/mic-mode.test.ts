import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  resolveMicMode, micModeState, shouldHonourStartMic, type MicState,
} from './mic-mode.ts'

// autoStopMic 的真正語意是「**你**講完話時關麥克風」——vad-context 的
// handleSpeechEnd 裡呼叫 stopMic()。設定頁原本的標籤寫成「AI 開始說話時自動關閉
// 麥克風」，是錯的，模式說明也因此跟著錯過一輪。
const ALWAYS: MicState = {
  micOn: true, autoStopMic: false, autoStartMicOn: true, autoStartMicOnConvEnd: true,
}
const VAD: MicState = {
  micOn: true, autoStopMic: true, autoStartMicOn: true, autoStartMicOnConvEnd: true,
}
const PUSH: MicState = {
  micOn: false, autoStopMic: true, autoStartMicOn: false, autoStartMicOnConvEnd: false,
}

test('三個模式各自認得出自己', () => {
  assert.equal(resolveMicMode(ALWAYS), 'always')
  assert.equal(resolveMicMode(VAD), 'vad')
  assert.equal(resolveMicMode(PUSH), 'push')
})

test('主動按麥克風模式不看麥克風當下開著沒有', () => {
  // 這個模式下 micOn 一直在變：按下去講話時是開的，講完自動關。把 micOn 納入
  // 判定的話，模式會在講話中途跳成「自訂」。
  assert.equal(resolveMicMode({ ...PUSH, micOn: true }), 'push')
  assert.equal(resolveMicMode({ ...PUSH, micOn: false }), 'push')
})

test('持續開著與偵測到聲音才收只差在你講完會不會關', () => {
  assert.deepEqual(micModeState('always'), { ...VAD, autoStopMic: false })
})

test('切到主動按麥克風時要先把麥克風關起來', () => {
  // 這個模式的前提就是「平常關著，要講才按」。切過去卻還開著會繼續收音。
  const result = micModeState('push')
  assert.equal(result.micOn, false)
  assert.equal(result.autoStopMic, true)
  assert.equal(result.autoStartMicOn, false)
  assert.equal(result.autoStartMicOnConvEnd, false)
})

test('切換模式後再判定，會得到同一個模式', () => {
  for (const mode of ['always', 'vad', 'push'] as const) {
    assert.equal(resolveMicMode(micModeState(mode)), mode, mode)
  }
})

test('手動改開關改出不屬於任何模式的組合時回報 custom', () => {
  assert.equal(resolveMicMode({ ...VAD, autoStartMicOnConvEnd: false }), 'custom')
  assert.equal(resolveMicMode({ ...ALWAYS, autoStartMicOn: false }), 'custom')
  // 兩個自動開啟都關、但你講完也不關麥克風——沒有名字的組合。
  assert.equal(resolveMicMode({ ...PUSH, autoStopMic: false }), 'custom')
})

test('主動按麥克風模式要擋掉後端的 start-mic', () => {
  // 後端每次連上都無條件送 start-mic。照做的話「要講才按」就破功了：每次重整
  // 麥克風都自己打開，然後把環境噪音辨識成句子送出去。
  assert.equal(shouldHonourStartMic(PUSH), false)
})

test('另外兩個模式照常接受 start-mic', () => {
  assert.equal(shouldHonourStartMic(ALWAYS), true)
  assert.equal(shouldHonourStartMic(VAD), true)
})

test('自訂組合也接受 start-mic', () => {
  // 使用者留著任何一個自動開啟的設定，就代表他確實要它自己開。
  assert.equal(shouldHonourStartMic({ ...VAD, autoStartMicOnConvEnd: false }), true)
})
