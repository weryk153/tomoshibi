// VRM 模型設定的 typed wrapper。跟同目錄的 live2d-config.ts 打同一個端點
// （GET /api/live2d/model-config/{name}），後端依 model_dict 項目的 type 回不同
// 形狀；這裡只描述 VRM 那一種。欄位保留後端的 snake_case，理由同 live2d-config.ts。
import { apiGet, apiPut, type ApiResult } from './http.ts'

export interface VrmClipMapping {
  keyword: string
  label: string | null
}

export interface VrmClipEntry {
  clip: string
  file: string
  mappings: VrmClipMapping[]
}

export interface VrmExpressionEntry {
  name: string
  keywords: string[]
}

export interface VrmModelConfig {
  name: string
  type: 'vrm'
  clips: VrmClipEntry[]
  expressions: VrmExpressionEntry[]
  has_idle: boolean
  // kind 區分這個失效關鍵字原本指的是動作還是表情——兩者訊息不同（見
  // vrm-motion-config.tsx 的 orphan 清單）。後端一律會送，型別上留成可選是為了
  // 相容還沒更新的後端，讀的地方預設當 'motion'。
  orphan_keywords: { keyword: string; clip: string | null; kind?: 'motion' | 'expression' }[]
}

export const fetchVrmModelConfig = (
  baseUrl: string,
  name: string,
): Promise<ApiResult<VrmModelConfig>> =>
  apiGet<VrmModelConfig>(baseUrl, `/api/live2d/model-config/${encodeURIComponent(name)}`)

// preset 名單裡不是「情緒」的那些：嘴型（口型同步逐幀寫入，跟 LLM 觸發的情緒
// 完全是两回事）、眨眼（AutoBlink 自動跑）、視線（沒有對應的視線控制器，留著
// 也沒地方接）。neutral 不是被 emotionMap 指到的——「回到原樣」呼叫的是
// ExpressionController.clear()，把所有情緒淡到 0，VRM 的中性本來就是全零，不用
// 另外挑一個 preset 蓋上去（跟 vrm-renderer.ts 檔頭的说明同一件事）。
// 這些 preset 名稱固定，來自 VRM 1.0 規格與 three-vrm 的 VRMExpressionPresetName。
export const EMOTION_EXCLUDED_PRESETS = new Set([
  'aa',
  'ih',
  'ou',
  'ee',
  'oh',
  'blink',
  'blinkLeft',
  'blinkRight',
  'lookUp',
  'lookDown',
  'lookLeft',
  'lookRight',
  'neutral',
])

// 情緒對應編輯器只列會被 emotionMap 用到的 preset——濾掉上面那份清單。
export function emotionPresets(config: VrmModelConfig): VrmExpressionEntry[] {
  return config.expressions.filter((expression) => !EMOTION_EXCLUDED_PRESETS.has(expression.name))
}

// re-review of cfa0138 殘留 1：畫面上情緒關鍵字的重複檢查（validateKeyword 的
// existing 清單）原本只看得到可見列 expressionRows／extraEmotionKeywords，沒有
// hiddenEmotionKeywords（被 emotionPresets 濾掉的 preset，例如 neutral，的既有
// 關鍵字）。漏了它的後果：使用者在可見的表情列打「neutral」不會被標成重複，
// 存檔時 buildVrmPayload 用 hiddenEmotionKeywords 覆寫同一個 key（兩邊都想要
// "neutral" 這個字，後寫的那個贏），或者後端 _validate_emotion_map 的大小寫
// 不敏感重複檢查直接拒絕整次存檔、UI 只看到一個看不懂的 400。
//
// 抽成純函式（跟 vrm-motion-config.tsx 元件內同名的 useCallback 邏輯完全一致，
// 只是多吃一個 hiddenEmotionKeywords 參數）方便脫離 React 單獨測試——元件裡的
// allEmotionKeywordsExcept 就是呼叫這個函式，state 從外面傳進來。
//
// excludeName 只排除「自己正在編輯的那一列」，只對 expressionRows／
// extraEmotionKeywords 有意義；hiddenEmotionKeywords 沒有對應的可見列（它的
// key 是被排除的 preset 名稱，不可能等於使用者正在打字的那個可見 expression
// 名稱），所以整份都算進去，不做排除。
export function emotionKeywordsExcept(
  excludeName: string,
  expressionRows: Record<string, string>,
  extraEmotionKeywords: Record<string, string[]>,
  hiddenEmotionKeywords: Record<string, string[]>,
): string[] {
  const list: string[] = []
  Object.entries(expressionRows).forEach(([name, keyword]) => {
    if (name === excludeName) return
    const trimmed = keyword.trim()
    if (trimmed) list.push(trimmed)
  })
  Object.entries(extraEmotionKeywords).forEach(([name, keywords]) => {
    if (name === excludeName) return
    keywords.forEach((k) => list.push(k))
  })
  Object.values(hiddenEmotionKeywords).forEach((keywords) => {
    keywords.forEach((k) => list.push(k))
  })
  return list
}

// motionMap 裡一個 keyword 指向的目標。VRM 的動作只有 clip 檔名可以定位，沒有
// Live2D 的 (group, index)——見 api/live2d-config.ts 的 MotionMapTarget。
export interface VrmMotionMapTarget {
  clip: string
  label: string | null
}

// 畫面上一個 clip 目前正在編輯的第一筆 mapping。
export interface VrmMotionRowEdit {
  keyword: string
  label: string
}

// PUT /api/live2d/model-config/{name} 成功時的原始回應。
interface SaveVrmModelConfigResponse {
  ok: true
  restart_required: boolean
}

export interface SaveVrmModelConfigResult {
  restart_required: boolean
}

// PUT /api/live2d/model-config/{name}：整份取代 motionMap／emotionMap。VRM 沒有
// 點擊區域（vrm_models.py 的 validate_vrm_motion_map 要求 tapMotions 必須是
// 空物件），所以固定送 {}，不像 Live2D 版本（api/live2d-config.ts 的
// saveModelConfig）需要一份 tapMotions 參數。
export async function saveVrmModelConfig(
  baseUrl: string,
  name: string,
  motionMap: Record<string, VrmMotionMapTarget>,
  emotionMap: Record<string, string>,
): Promise<ApiResult<SaveVrmModelConfigResult>> {
  const res = await apiPut<SaveVrmModelConfigResponse>(
    baseUrl,
    `/api/live2d/model-config/${encodeURIComponent(name)}`,
    { motionMap, tapMotions: {}, emotionMap },
  )
  if (!res.ok) return res
  return { ok: true, data: { restart_required: res.data.restart_required } }
}

// 從畫面狀態組出整份 motionMap／emotionMap（PUT 是整份取代，見
// saveVrmModelConfig 的說明）。純函式，方便單元測試，不碰 fetch。
//
// - rows／expressionRows：每個 clip／expression 目前畫面上那一列的編輯狀態，
//   key 是 clip 名稱／expression 名稱（VRM 沒有 Live2D 的 (group, index)，這兩個
//   名稱本身就是穩定唯一的鍵，不需要 motion-config.tsx 的 motionKey() 那種
//   JSON.stringify 組合鍵）。
// - extraMappings／extraEmotionKeywords：同一個 clip／expression 被不只一個
//   關鍵字指到時，畫面沒有欄位可編輯的其餘那些——存檔要原樣帶回去，理由跟
//   motion-config.tsx 檔頭說明的一樣：PUT 整份取代，少送等於悄悄清空。
// - idle 永遠不進 motionMap：它被待機流程佔用，UI 也不給輸入框，就算 rows 裡
//   意外帶了值也要在這裡再擋一次。
// - 空白關鍵字（trim 後是空字串）代表「還沒命名」，跳過不寫入。extras 沿用
//   motion-config.tsx 兩種不同的既有慣例：動作的 extras 原樣帶回（來源是後端
//   已驗證過的資料，不需要再 trim／檢查空字串）；情緒關鍵字的 extras 有 trim
//   與空字串檢查（跟 motion-config.tsx 的 buildEmotionMap 同一種寫法）。
// - hiddenEmotionKeywords：review a0c0ce7 fix 1（critical）。emotionPresets 濾掉
//   的 preset（嘴型／眨眼／視線／neutral）從來不會出現在 `expressions` 參數裡，
//   UI 根本沒有畫面可以編輯它們——但每個 VRM 模型出廠時的 emotionMap 幾乎都有
//   neutral→neutral，kurisu_3d 系列甚至整份 emotionMap 都指向被排除的 preset。
//   不把這些原樣帶回去的話，第一次存檔就會把它們全部洗掉。key 是 preset 名稱，
//   value 是載入當下讀到的完整關鍵字清單（不像 extraEmotionKeywords 只存「第一筆
//   以外」的——這裡整份都是「畫面沒有欄位」，所以整份都要原樣帶回，沒有
//   trim／空字串檢查，因為來源是後端已經驗證過的既有資料）。省略＝視為空物件，
//   向下相容舊呼叫端。
export function buildVrmPayload(
  clips: VrmClipEntry[],
  rows: Record<string, VrmMotionRowEdit>,
  extraMappings: Record<string, VrmClipMapping[]>,
  expressions: VrmExpressionEntry[],
  expressionRows: Record<string, string>,
  extraEmotionKeywords: Record<string, string[]>,
  hiddenEmotionKeywords: Record<string, string[]> = {},
): { motionMap: Record<string, VrmMotionMapTarget>; emotionMap: Record<string, string> } {
  const motionMap: Record<string, VrmMotionMapTarget> = {}
  clips.forEach((clip) => {
    if (clip.clip === 'idle') return
    const row = rows[clip.clip]
    const trimmedKeyword = row?.keyword.trim()
    if (trimmedKeyword) {
      motionMap[trimmedKeyword] = { clip: clip.clip, label: row.label.trim() || null }
    }
    ;(extraMappings[clip.clip] ?? []).forEach((extra) => {
      motionMap[extra.keyword] = { clip: clip.clip, label: extra.label }
    })
  })

  const emotionMap: Record<string, string> = {}
  expressions.forEach((expression) => {
    const trimmedKeyword = expressionRows[expression.name]?.trim()
    if (trimmedKeyword) emotionMap[trimmedKeyword] = expression.name
    ;(extraEmotionKeywords[expression.name] ?? []).forEach((keyword) => {
      const trimmed = keyword.trim()
      if (trimmed) emotionMap[trimmed] = expression.name
    })
  })
  Object.entries(hiddenEmotionKeywords).forEach(([presetName, keywords]) => {
    keywords.forEach((keyword) => {
      emotionMap[keyword] = presetName
    })
  })

  return { motionMap, emotionMap }
}
