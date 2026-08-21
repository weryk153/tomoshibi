import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { attachVoiceGain, resetVoiceGainForTest } from './voice-gain.ts'

// 最小的 Web Audio 替身。只做到足以驗證「有沒有接上 graph」與「接上時參數對不對」。
function installAudioContext(options: {
  state?: string
  throwOnSource?: boolean
  missing?: boolean
} = {}) {
  const created = { sources: 0, connects: [] as string[], gain: 0, resumeCalls: 0 }
  if (options.missing) {
    delete (globalThis as any).AudioContext
    delete (globalThis as any).webkitAudioContext
    return created
  }
  class FakeCtx {
    state = options.state ?? 'running'
    destination = { name: 'destination' }
    resume() { created.resumeCalls += 1; return Promise.resolve() }
    createMediaElementSource() {
      if (options.throwOnSource) throw new Error('already connected')
      created.sources += 1
      return { connect: (n: any) => created.connects.push(n.name ?? 'gain'), disconnect() {} }
    }
    createGain() {
      const node: any = {
        name: 'gain',
        gain: { set value(v: number) { created.gain = v }, get value() { return created.gain } },
        connect: (n: any) => created.connects.push(n.name ?? 'limiter'),
        disconnect() {},
      }
      return node
    }
    createDynamicsCompressor() {
      return {
        name: 'limiter',
        threshold: { value: 0 }, knee: { value: 0 }, ratio: { value: 0 },
        attack: { value: 0 }, release: { value: 0 },
        connect: (n: any) => created.connects.push(n.name ?? 'destination'),
        disconnect() {},
      }
    }
  }
  ;(globalThis as any).AudioContext = FakeCtx
  return created
}

const fakeAudio = () => ({}) as HTMLAudioElement

beforeEach(() => {
  resetVoiceGainForTest()
})

test('gain <= 1 不建立任何節點（走 .volume 就好）', () => {
  const c = installAudioContext()
  assert.equal(attachVoiceGain(fakeAudio(), 1), null)
  assert.equal(attachVoiceGain(fakeAudio(), 0.5), null)
  assert.equal(c.sources, 0)
})

test('gain > 1 時接上 source → gain → limiter → destination', () => {
  const c = installAudioContext()
  const handle = attachVoiceGain(fakeAudio(), 3)
  assert.ok(handle)
  assert.equal(c.sources, 1)
  assert.equal(c.gain, 3)
  assert.deepEqual(c.connects, ['gain', 'limiter', 'destination'])
})

// 這是這個模組最重要的性質：接上去之後元素就不再直接出聲，
// 所以 context 還沒 running 時絕不能接——否則使用者聽到的是全靜音。
test('context 為 suspended 時不接上去，並嘗試喚醒', () => {
  const c = installAudioContext({ state: 'suspended' })
  assert.equal(attachVoiceGain(fakeAudio(), 3), null)
  assert.equal(c.sources, 0, '不可以在 suspended 狀態下接上 graph')
  assert.equal(c.resumeCalls, 1)
})

test('context 為 closed 時不接上去', () => {
  const c = installAudioContext({ state: 'closed' })
  assert.equal(attachVoiceGain(fakeAudio(), 3), null)
  assert.equal(c.sources, 0)
})

test('瀏覽器沒有 Web Audio 時回 null 而不是拋錯', () => {
  installAudioContext({ missing: true })
  assert.doesNotThrow(() => {
    assert.equal(attachVoiceGain(fakeAudio(), 3), null)
  })
})

test('建立節點失敗時回 null 而不是拋錯', () => {
  installAudioContext({ throwOnSource: true })
  assert.doesNotThrow(() => {
    assert.equal(attachVoiceGain(fakeAudio(), 3), null)
  })
})

test('非有限數的 gain 不接上去', () => {
  const c = installAudioContext()
  assert.equal(attachVoiceGain(fakeAudio(), NaN), null)
  assert.equal(attachVoiceGain(fakeAudio(), Infinity), null)
  assert.equal(c.sources, 0)
})

test('disconnect 可重複呼叫且不拋錯', () => {
  installAudioContext()
  const handle = attachVoiceGain(fakeAudio(), 2)
  assert.ok(handle)
  assert.doesNotThrow(() => { handle.disconnect(); handle.disconnect() })
})
