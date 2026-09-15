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
  orphan_keywords: { keyword: string; clip: string | null }[]
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
export function buildVrmPayload(
  clips: VrmClipEntry[],
  rows: Record<string, VrmMotionRowEdit>,
  extraMappings: Record<string, VrmClipMapping[]>,
  expressions: VrmExpressionEntry[],
  expressionRows: Record<string, string>,
  extraEmotionKeywords: Record<string, string[]>,
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

  return { motionMap, emotionMap }
}
