import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createAutosaver, type SaveState } from './autosave.ts'

function harness(results: Array<{ ok: true } | { ok: false; error: string }> = []) {
  const saved: string[] = []
  const states: SaveState[] = []
  let timer: (() => void) | null = null
  const resolvers: Array<() => void> = []
  const saver = createAutosaver<string>({
    delayMs: 800,
    save: (value) => {
      saved.push(value)
      const result = results.shift() ?? { ok: true as const }
      return new Promise((resolve) => resolvers.push(() => resolve(result)))
    },
    validate: (value) => (value === 'bad' ? '不合法' : null),
    onState: (state) => states.push(state),
    schedule: (fn) => { timer = fn; return 1 },
    cancel: () => { timer = null },
  })
  return {
    saver, saved, states,
    tick: () => { const fn = timer; timer = null; fn?.() },
    // 每輪放行所有在等的存檔，再讓出一個 macrotask，讓「回來之後再送最後那個值」排進來。
    finish: async () => {
      for (let i = 0; i < 20; i += 1) {
        while (resolvers.length) resolvers.shift()!()
        await new Promise((resolve) => setTimeout(resolve, 0))
      }
    },
    hasTimer: () => timer !== null,
  }
}

test('only the last value within the delay is saved', async () => {
  const h = harness()
  h.saver.change('a'); h.saver.change('ab'); h.saver.change('abc')
  assert.deepEqual(h.saved, [])
  h.tick()
  await h.finish()
  assert.deepEqual(h.saved, ['abc'])
  assert.deepEqual(h.states.map((s) => s.phase), ['saving', 'saved'])
})

test('flush saves right away (blur, closing the drawer)', async () => {
  const h = harness()
  h.saver.change('x')
  const done = h.saver.flush()
  await h.finish()
  await done
  assert.deepEqual(h.saved, ['x'])
  assert.equal(h.hasTimer(), false)
})

test('coalesces while saving: the last value wins', async () => {
  const h = harness()
  h.saver.change('one'); h.tick()
  h.saver.change('two'); h.tick()
  h.saver.change('three'); h.tick()
  await h.finish()
  assert.deepEqual(h.saved, ['one', 'three'])
})

test('an invalid value is not saved and says why', async () => {
  const h = harness()
  h.saver.change('bad'); h.tick()
  await h.finish()
  assert.deepEqual(h.saved, [])
  assert.deepEqual(h.states.at(-1), { phase: 'invalid', message: '不合法' })
})

test('a failed save shows the error and the next change retries', async () => {
  const h = harness([{ ok: false, error: 'HTTP 500' }])
  h.saver.change('v'); h.tick()
  await h.finish()
  assert.deepEqual(h.states.at(-1), { phase: 'error', message: 'HTTP 500' })
  h.saver.change('v2'); h.tick()
  await h.finish()
  assert.deepEqual(h.saved, ['v', 'v2'])
  assert.equal(h.states.at(-1)?.phase, 'saved')
})

test('dispose flushes a pending change', async () => {
  const h = harness()
  h.saver.change('last words')
  const done = h.saver.dispose()
  await h.finish()
  await done
  assert.deepEqual(h.saved, ['last words'])
})

test('a zero delay saves on the next tick without waiting', async () => {
  const saved: boolean[] = []
  const saver = createAutosaver<boolean>({
    delayMs: 0,
    save: async (value) => { saved.push(value); return { ok: true } },
    onState: () => {},
  })
  saver.change(true)
  await new Promise((resolve) => setTimeout(resolve, 5))
  assert.deepEqual(saved, [true])
})

test('a save that throws is reported, not left as an unhandled rejection', async () => {
  const states: SaveState[] = []
  const saver = createAutosaver<string>({
    delayMs: 0,
    save: async () => { throw new Error('network down') },
    onState: (state) => states.push(state),
  })
  saver.change('x')
  await saver.flush()
  assert.deepEqual(states.at(-1), { phase: 'error', message: 'network down' })
})

test('awaiting flush during an in-flight save ends only after the queued value is sent', async () => {
  // 角色頁換選角色前 await 這個：存檔器只有一格，沒等完就換的話，新角色的第一個
  // 字會把舊角色排著的那筆擠掉。
  const h = harness()
  h.saver.change('A1'); h.tick()          // A1 送出中
  h.saver.change('A2')                    // A2 排隊
  let done = false
  const flushed = h.saver.flush().then(() => { done = true })
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(done, false)
  await h.finish()
  await flushed
  assert.deepEqual(h.saved, ['A1', 'A2'])
})
