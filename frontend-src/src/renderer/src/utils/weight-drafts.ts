// 點擊權重的文字草稿，鍵是 `${點擊區域}#${第幾個候選}`。候選被刪掉時草稿要跟著刪、
// 後面的往前挪，不然新加的候選會顯示別人的字，或一個已經不存在的空白欄位永遠擋住存檔。
//
// 不含 React，可 node 測。
import { parseBoundedNumber } from './setting-values.ts'

export type WeightDrafts = Record<string, string>

export function removeWeightDraft(texts: WeightDrafts, areaId: string, index: number): WeightDrafts {
  const next: WeightDrafts = {}
  for (const [key, text] of Object.entries(texts)) {
    const at = key.lastIndexOf('#')
    const area = key.slice(0, at)
    const i = Number(key.slice(at + 1))
    if (area !== areaId || i < index) next[key] = text
    else if (i > index) next[`${area}#${i - 1}`] = text
  }
  return next
}

export function anyInvalidWeightDraft(
  texts: WeightDrafts,
  entries: Record<string, readonly unknown[]>,
): boolean {
  return Object.entries(texts).some(([key, text]) => {
    const at = key.lastIndexOf('#')
    const area = key.slice(0, at)
    const i = Number(key.slice(at + 1))
    const exists = i < (entries[area]?.length ?? 0)
    return exists && parseBoundedNumber(text, { min: 0 }) === null
  })
}
