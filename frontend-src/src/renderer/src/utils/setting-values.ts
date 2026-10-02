// 設定欄位的文字 → 值。打到一半的文字（空、「0.」、「12a」）不是值：回 null，
// 呼叫端不存、也不把畫面彈回舊值，旁邊寫為什麼不存（boundsMessage）。
//
// 不含 React，所以能用 node:test 驗證。

const NUMBER = /^-?(\d+\.?\d*|\.\d+)$/

export interface Bounds { min?: number; max?: number; integer?: boolean }

export function parseBoundedNumber(text: string, bounds: Bounds): number | null {
  const trimmed = text.trim()
  if (!NUMBER.test(trimmed) || trimmed.endsWith('.')) return null
  const value = Number(trimmed)
  if (!Number.isFinite(value)) return null
  if (bounds.integer && !Number.isInteger(value)) return null
  if (bounds.min !== undefined && value < bounds.min) return null
  if (bounds.max !== undefined && value > bounds.max) return null
  return value
}

// 給 t() 的鍵與參數：t(key, params)。沒有上限時顯示 ∞。
export function boundsMessage(bounds: Bounds): { key: string; params: { min: number | string; max: number | string } } {
  return {
    key: bounds.integer ? 'settings.values.integerBetween' : 'settings.values.numberBetween',
    params: { min: bounds.min ?? '−∞', max: bounds.max ?? '∞' },
  }
}

export function splitKeywords(text: string): string[] {
  const words: string[] = []
  for (const part of text.split(/[,，、]/)) {
    const word = part.trim()
    if (word && !words.includes(word)) words.push(word)
  }
  return words
}
