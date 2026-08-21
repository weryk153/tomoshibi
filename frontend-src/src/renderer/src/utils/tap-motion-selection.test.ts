import { test } from 'node:test'
import assert from 'node:assert/strict'
import { selectTapMotion, type TapMotionsConfig } from './tap-motion-selection.ts'

// random() 固定回傳 0：加權迴圈的第一次比較 `r < w` 必然成立（只要第一個
// 候選的權重 > 0），所以永遠選中候選清單裡的第一項。用來讓「選中誰」這件
// 事在測試裡是確定的，不必真的驗證亂數分佈。
const pickFirst = () => 0

test('direct area hit: 只從命中的區域挑，不落回全域清單', () => {
  const config: TapMotionsConfig = {
    head: [{ group: 'TapHead', index: 0, weight: 1 }],
    body: [{ group: 'TapBody', index: 0, weight: 1 }],
  }
  const decision = selectTapMotion(config, 'head', pickFirst)
  assert.deepEqual(decision, { group: 'TapHead', index: 0 })
})

test('miss falls back to the union of all areas', () => {
  const config: TapMotionsConfig = {
    head: [{ group: 'TapHead', index: 0, weight: 1 }],
    body: [{ group: 'TapBody', index: 0, weight: 1 }],
  }
  // hitAreaName 為 null（沒命中任何具名區域）-> 落回全域清單，第一項來自
  // Object.values 的疊代順序，也就是 head 的那一筆。
  const decision = selectTapMotion(config, null, pickFirst)
  assert.deepEqual(decision, { group: 'TapHead', index: 0 })
})

test('miss falls back to union even when the missed name is not a configured key', () => {
  const config: TapMotionsConfig = {
    head: [{ group: 'TapHead', index: 0, weight: 1 }],
  }
  const decision = selectTapMotion(config, 'unconfiguredArea', pickFirst)
  assert.deepEqual(decision, { group: 'TapHead', index: 0 })
})

test('index: null entry means "random within the group"', () => {
  const config: TapMotionsConfig = {
    head: [{ group: 'TapHead', index: null, weight: 1 }],
  }
  const decision = selectTapMotion(config, 'head', pickFirst)
  assert.deepEqual(decision, { group: 'TapHead', index: null })
})

test('index: 0 must not be confused with index: null', () => {
  // 兩個候選：第一個 index 是 null，第二個 index 是 0，權重都給極小值以外的
  // 0，讓 random() 回傳的值精確落在「跳過第一項、選中第二項」的區間，藉此
  // 驗證 0 走的是 startMotion(group, 0, ...) 那條路，不是被 `!index` 或
  // `index ?? random` 之類的 falsy 判斷誤判成「跟 null 一樣要隨機」。
  const config: TapMotionsConfig = {
    head: [
      { group: 'TapHead', index: null, weight: 1 },
      { group: 'TapHead', index: 0, weight: 1 },
    ],
  }
  // totalWeight = 2；random() 回傳 0.6 -> r = 1.2，第一項 r(1.2) < w(1) 為
  // false，扣掉後 r = 0.2，第二項 r(0.2) < w(1) 為 true -> 選中第二項。
  const decision = selectTapMotion(config, 'head', () => 0.6)
  assert.deepEqual(decision, { group: 'TapHead', index: 0 })
  assert.notEqual(decision?.index, null)
})

test('empty-string group is a legal candidate, not "no group"', () => {
  // mao_pro 把六個可用動作全放在無名群組（group === ''）。這裡驗證選中的
  // group 原樣是空字串，沒有被當成缺值濾掉或替換成別的東西。
  const config: TapMotionsConfig = {
    head: [{ group: '', index: 2, weight: 1 }],
  }
  const decision = selectTapMotion(config, 'head', pickFirst)
  assert.deepEqual(decision, { group: '', index: 2 })
})

test('empty config: 沒有任何區域設定時回傳 null，不丟例外', () => {
  const decision = selectTapMotion({}, 'head', pickFirst)
  assert.equal(decision, null)
})

test('hit area configured but with an empty candidate list: 不落回全域清單', () => {
  // 這個區域「刻意」設定成不播任何東西，跟「沒設定這個區域」語意不同——
  // 不該悄悄退回全域清單去播別的動作。
  const config: TapMotionsConfig = {
    head: [],
    body: [{ group: 'TapBody', index: 0, weight: 1 }],
  }
  const decision = selectTapMotion(config, 'head', pickFirst)
  assert.equal(decision, null)
})

// 這個函式跑在 canvas 的 mouseup handler 裡。丟出例外會逃出 handler、
// 連它自己的清理都跳過，所以任何非預期的輸入都必須回 null 而不是 throw。
// 後端已在 Live2dModel.set_model 就地正規化，但使用者手改過的檔案什麼形狀都可能。
test('舊的物件形狀不會 throw，回傳 null', () => {
  const legacy = { HitArea: { TapBody: 2 } } as unknown as TapMotionsConfig
  assert.equal(selectTapMotion(legacy, 'HitArea', () => 0.5), null)
})

test('未命中時把舊形狀混進聯集也不會 throw', () => {
  const legacy = { HitArea: { TapBody: 2 } } as unknown as TapMotionsConfig
  assert.equal(selectTapMotion(legacy, null, () => 0.5), null)
})

test('陣列裡混入 null 項目不會 throw', () => {
  const dirty = {
    Body: [null, { group: '', index: 0, weight: 1 }],
  } as unknown as TapMotionsConfig
  assert.deepEqual(selectTapMotion(dirty, 'Body', () => 0.5), { group: '', index: 0 })
})
