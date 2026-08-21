import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  VOICE_VOLUME_KEY,
  DEFAULT_VOICE_VOLUME,
  MAX_VOICE_VOLUME,
  clampVoiceVolume,
  loadVoiceVolume,
  saveVoiceVolume,
} from './voice-volume.ts'

// node:test 沒有 DOM，localStorage 要自己補一個。故意做成可以「壞掉」的版本，
// 因為 loadVoiceVolume 對外承諾的正是「localStorage 不能用時也不會拋」。
function installStorage(options: { throwing?: boolean } = {}) {
  const map = new Map<string, string>()
  const storage = {
    getItem(key: string) {
      if (options.throwing) throw new Error('storage disabled')
      return map.has(key) ? map.get(key)! : null
    },
    setItem(key: string, value: string) {
      if (options.throwing) throw new Error('storage disabled')
      map.set(key, value)
    },
  }
  ;(globalThis as any).localStorage = storage
  return map
}

beforeEach(() => {
  installStorage()
})

test('clamp 夾到 [0, MAX]', () => {
  assert.equal(clampVoiceVolume(0.5), 0.5)
  assert.equal(clampVoiceVolume(-1), 0)
  assert.equal(clampVoiceVolume(0), 0)
  assert.equal(clampVoiceVolume(1), 1)
  // 上限是 5.0 而不是 1.0——超過 1 的部分由 voice-gain.ts 的 GainNode 實現，
  // 因為 HTMLAudioElement.volume 本身只吃 [0, 1]。
  assert.equal(clampVoiceVolume(3), 3)
  assert.equal(clampVoiceVolume(MAX_VOICE_VOLUME), MAX_VOICE_VOLUME)
  assert.equal(clampVoiceVolume(99), MAX_VOICE_VOLUME)
})

test('clamp 對非有限數退回預設值', () => {
  assert.equal(clampVoiceVolume(NaN), DEFAULT_VOICE_VOLUME)
  assert.equal(clampVoiceVolume(Infinity), DEFAULT_VOICE_VOLUME)
  assert.equal(clampVoiceVolume(-Infinity), DEFAULT_VOICE_VOLUME)
})

test('沒存過時回預設值', () => {
  assert.equal(loadVoiceVolume(), DEFAULT_VOICE_VOLUME)
})

test('存過就讀得回來', () => {
  saveVoiceVolume(0.35)
  assert.equal(loadVoiceVolume(), 0.35)
})

// 這是最容易寫錯的一個：靜音是合法設定，不能被 falsy 檢查吃掉變成「沒設定過」
// 而回到 1.0——那會讓使用者把音量拉到 0、重開之後聲音又全開。
test('音量 0 是合法值，不會被當成未設定', () => {
  saveVoiceVolume(0)
  assert.equal(globalThis.localStorage.getItem(VOICE_VOLUME_KEY), '0')
  assert.equal(loadVoiceVolume(), 0)
})

test('存進去之前先夾值，壞值不會落地', () => {
  saveVoiceVolume(99)
  assert.equal(loadVoiceVolume(), MAX_VOICE_VOLUME)
  saveVoiceVolume(-3)
  assert.equal(loadVoiceVolume(), 0)
})

test('讀到壞字串時回預設值', () => {
  const map = installStorage()
  map.set(VOICE_VOLUME_KEY, 'not-a-number')
  assert.equal(loadVoiceVolume(), DEFAULT_VOICE_VOLUME)
  map.set(VOICE_VOLUME_KEY, '')
  assert.equal(loadVoiceVolume(), DEFAULT_VOICE_VOLUME)
})

test('讀到超出範圍的舊值時夾回範圍內', () => {
  const map = installStorage()
  map.set(VOICE_VOLUME_KEY, '9')
  assert.equal(loadVoiceVolume(), MAX_VOICE_VOLUME)
})

// localStorage 整個不能用（Safari 無痕、SSR）時不能往外拋：這條路徑在每段
// 音訊播放前都會跑，拋出去會直接打斷整輪語音。
test('localStorage 拋錯時不往外拋', () => {
  installStorage({ throwing: true })
  assert.equal(loadVoiceVolume(), DEFAULT_VOICE_VOLUME)
  assert.doesNotThrow(() => saveVoiceVolume(0.5))
})

test('localStorage 不存在時不往外拋', () => {
  delete (globalThis as any).localStorage
  assert.equal(loadVoiceVolume(), DEFAULT_VOICE_VOLUME)
  assert.doesNotThrow(() => saveVoiceVolume(0.5))
})
