// 設定抽屜的自動存檔器：改了就存，但不在打字途中存。
//
// change() 重新計時 delayMs，停手才送；flush() 立刻送（失焦、關抽屜）；送的途中
// 又改，等這一筆回來再送最後那個值——不會讓較早的回應蓋掉較新的值。validate
// 不過的值不送，狀態是 invalid 並帶原因，欄位保持使用者打的字。
//
// 不含 React，所以能用 node:test 驗證；React 包裝在 hooks/use-autosave.ts。

export type SaveResult = { ok: true } | { ok: false; error: string }

export interface SaveState {
  phase: 'idle' | 'saving' | 'saved' | 'error' | 'invalid'
  message?: string
}

export interface AutosaverOptions<T> {
  save: (value: T) => Promise<SaveResult>
  delayMs: number
  validate?: (value: T) => string | null
  onState: (state: SaveState) => void
  schedule?: (fn: () => void, ms: number) => unknown
  cancel?: (handle: unknown) => void
}

export interface Autosaver<T> {
  change(value: T): void
  flush(): Promise<void>
  dispose(): Promise<void>
}

export const AUTOSAVE_DELAY_MS = 800

export function createAutosaver<T>(options: AutosaverOptions<T>): Autosaver<T> {
  const schedule = options.schedule ?? ((fn: () => void, ms: number) => setTimeout(fn, ms))
  const cancel = options.cancel
    ?? ((handle: unknown) => clearTimeout(handle as ReturnType<typeof setTimeout>))
  let pending: { value: T } | null = null
  let timer: unknown = null
  let inFlight: Promise<void> | null = null

  const run = async (): Promise<void> => {
    if (timer !== null) { cancel(timer); timer = null }
    if (inFlight) {
      await inFlight
      if (!pending) return
    }
    if (!pending) return
    const { value } = pending
    pending = null
    const problem = options.validate?.(value) ?? null
    if (problem) {
      options.onState({ phase: 'invalid', message: problem })
      return
    }
    options.onState({ phase: 'saving' })
    inFlight = (async () => {
      try {
        const result = await options.save(value)
        options.onState(result.ok ? { phase: 'saved' } : { phase: 'error', message: result.error })
      } catch (error) {
        options.onState({ phase: 'error', message: error instanceof Error ? error.message : String(error) })
      }
    })()
    try {
      await inFlight
    } finally {
      inFlight = null
    }
    if (pending) await run()
  }

  return {
    change(value: T) {
      pending = { value }
      if (timer !== null) cancel(timer)
      timer = schedule(() => { timer = null; void run() }, options.delayMs)
    },
    flush: run,
    dispose: run,
  }
}
