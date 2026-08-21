// 「點一下模型的某個區域時該播哪個動作」的純選擇邏輯。從
// WebSDK/src/lappmodel.ts 的 startTapMotion 抽出來，原因很直接：
// lappmodel.ts 是 vendored 檔案，會 import 一堆需要真的 WebGL/Cubism
// framework 環境才能載入的模組（@framework/*），`pnpm test` 用的
// `node --test --experimental-strip-types` 只做型別剝除、不處理路徑別名，
// 沒辦法直接 import 那個檔案來測。這裡沒有任何 framework 依賴，是純函式，
// 可以直接測。
//
// tapMotions 的正規化形狀：`{hitAreaId: [{group, index, weight}]}`。
// index 為 null 代表「群組內隨機挑一個」——是 legacy 的 {groupName: weight}
// 形狀轉換過來的資料，從未記錄過具體 index，這裡刻意保留這個語意而不是
// 假裝成 index 0。

/** tapMotions 正規化清單裡的一筆候選。group 允許合法的空字串（例如
 * mao_pro 把六個可用動作全放在無名群組），呼叫端不可對它做 truthy 測試。 */
export interface TapMotionCandidate {
  group: string
  index: number | null
  weight: number
}

/** hitAreaId -> 該區域的候選清單。 */
export type TapMotionsConfig = Record<string, TapMotionCandidate[]>

/** 選中的結果：要播哪個 (group, index)。index 為 null 代表群組內隨機。 */
export interface TapMotionDecision {
  group: string
  index: number | null
}

/**
 * 給定目前設定的 tapMotions 與命中的 hitArea（anyhitTest 的回傳值，沒命中
 * 任何具名區域時是 null），決定要播哪一個候選。
 *
 * 命中規則跟改版前的 {group: weight} 邏輯保持一致：
 * - hitAreaName 命中某個有設定的區域 -> 只從那個區域的候選清單裡選，不落回
 *   全域清單，即使那個區域的清單是空的（維持「這個區域刻意設定成不播任何
 *   東西」的行為，不悄悄變成全域隨機）。
 * - 否則（沒命中任何具名區域，或命中的區域沒有設定）-> 把所有區域的候選
 *   清單串接起來，當作一個共用池。舊實作在這裡是把同名群組的權重相加；新
 *   形狀下，同一個 {group, index} 出現兩次就是兩個候選項，串接陣列在權重
 *   加總的意義上是等價的，不需要另外做加總。
 *
 * random 參數只用來讓測試能戳穿「加權隨機」這件事本身（預設用真正的
 * Math.random）。
 */
export function selectTapMotion(
  config: TapMotionsConfig,
  hitAreaName: string | null,
  random: () => number = Math.random,
): TapMotionDecision | null {
  if (!config || Object.keys(config).length === 0) return null

  let candidates: TapMotionCandidate[]
  if (hitAreaName && hitAreaName in config) {
    candidates = config[hitAreaName]
  } else {
    candidates = Object.values(config).flat()
  }

  // Defensive, not a legacy-shape branch. The backend normalises tapMotions at
  // the source (Live2dModel.set_model), so the list shape is all this should
  // ever see. But this runs inside the canvas mouseup handler: a TypeError here
  // escapes and skips the handler's own cleanup, so anything unexpected must
  // return null rather than throw. A stored file edited by hand can still be
  // any shape at all.
  if (!Array.isArray(candidates) || candidates.length === 0) return null
  candidates = candidates.filter((c) => c && typeof c === 'object')
  if (candidates.length === 0) return null

  const weights = candidates.map((c) => Number(c.weight))
  const totalWeight = weights.reduce((sum, w) => sum + (Number.isNaN(w) ? 0 : w), 0)
  if (totalWeight <= 0) return null

  let r = random() * totalWeight
  for (let i = 0; i < candidates.length; i += 1) {
    const w = Number.isNaN(weights[i]) ? 0 : weights[i]
    if (r < w) {
      const { group, index } = candidates[i]
      return { group, index }
    }
    r -= w
  }

  // 理論上不該走到這裡（totalWeight > 0 時，浮點誤差以外一定會在迴圈內
  // 命中一個候選）；維持舊實作的保守選擇：不硬選最後一個，回傳 null。
  return null
}
