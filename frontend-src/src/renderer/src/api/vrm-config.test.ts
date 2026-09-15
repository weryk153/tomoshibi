import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  EMOTION_EXCLUDED_PRESETS,
  emotionPresets,
  buildVrmPayload,
  type VrmModelConfig,
  type VrmClipEntry,
  type VrmExpressionEntry,
  type VrmMotionRowEdit,
  type VrmClipMapping,
} from './vrm-config.ts'

function config(overrides: Partial<VrmModelConfig> = {}): VrmModelConfig {
  return {
    name: 'shino',
    type: 'vrm',
    clips: [],
    expressions: [],
    has_idle: true,
    orphan_keywords: [],
    ...overrides,
  }
}

test('emotionPresets 濾掉嘴型／眨眼／視線／neutral，只留情緒 preset', () => {
  const expressions: VrmExpressionEntry[] = [
    { name: 'aa', keywords: [] },
    { name: 'blink', keywords: [] },
    { name: 'blinkLeft', keywords: [] },
    { name: 'blinkRight', keywords: [] },
    { name: 'lookUp', keywords: [] },
    { name: 'lookDown', keywords: [] },
    { name: 'lookLeft', keywords: [] },
    { name: 'lookRight', keywords: [] },
    { name: 'neutral', keywords: [] },
    { name: 'happy', keywords: ['joy'] },
    { name: 'sad', keywords: [] },
  ]
  const result = emotionPresets(config({ expressions }))
  assert.deepEqual(result.map((e) => e.name), ['happy', 'sad'])
})

test('EMOTION_EXCLUDED_PRESETS 涵蓋全部嘴型／眨眼／視線 preset 加 neutral', () => {
  const expected = [
    'aa', 'ih', 'ou', 'ee', 'oh',
    'blink', 'blinkLeft', 'blinkRight',
    'lookUp', 'lookDown', 'lookLeft', 'lookRight',
    'neutral',
  ]
  assert.deepEqual([...EMOTION_EXCLUDED_PRESETS].sort(), expected.sort())
})

test('emotionPresets 沒有任何 preset 時回傳空陣列', () => {
  assert.deepEqual(emotionPresets(config()), [])
})

test('buildVrmPayload：idle 永遠不進 motionMap，即使 rows 裡有值', () => {
  const clips: VrmClipEntry[] = [
    { clip: 'idle', file: 'idle.vrma', mappings: [] },
    { clip: 'wave', file: 'wave.vrma', mappings: [] },
  ]
  const rows: Record<string, VrmMotionRowEdit> = {
    idle: { keyword: 'sleep', label: '' },
    wave: { keyword: 'hello', label: '打招呼' },
  }
  const { motionMap } = buildVrmPayload(clips, rows, {}, [], {}, {})
  assert.deepEqual(motionMap, { hello: { clip: 'wave', label: '打招呼' } })
})

test('buildVrmPayload：空白關鍵字（trim 後為空）跳過不寫入', () => {
  const clips: VrmClipEntry[] = [{ clip: 'wave', file: 'wave.vrma', mappings: [] }]
  const rows: Record<string, VrmMotionRowEdit> = { wave: { keyword: '   ', label: '' } }
  const { motionMap } = buildVrmPayload(clips, rows, {}, [], {}, {})
  assert.deepEqual(motionMap, {})
})

test('buildVrmPayload：label 留白存 null，不存空字串', () => {
  const clips: VrmClipEntry[] = [{ clip: 'wave', file: 'wave.vrma', mappings: [] }]
  const rows: Record<string, VrmMotionRowEdit> = { wave: { keyword: 'hello', label: '   ' } }
  const { motionMap } = buildVrmPayload(clips, rows, {}, [], {}, {})
  assert.deepEqual(motionMap, { hello: { clip: 'wave', label: null } })
})

test('buildVrmPayload：同一個 clip 的 extras 原樣保留，不受畫面只顯示第一筆影響', () => {
  const clips: VrmClipEntry[] = [{ clip: 'wave', file: 'wave.vrma', mappings: [] }]
  const rows: Record<string, VrmMotionRowEdit> = { wave: { keyword: 'hello', label: '' } }
  const extraMappings: Record<string, VrmClipMapping[]> = {
    wave: [{ keyword: 'hi', label: null }, { keyword: 'yo', label: 'YO' }],
  }
  const { motionMap } = buildVrmPayload(clips, rows, extraMappings, [], {}, {})
  assert.deepEqual(motionMap, {
    hello: { clip: 'wave', label: null },
    hi: { clip: 'wave', label: null },
    yo: { clip: 'wave', label: 'YO' },
  })
})

test('buildVrmPayload：clip 沒有對應的 rows 項目時安全跳過（不 throw）', () => {
  const clips: VrmClipEntry[] = [{ clip: 'wave', file: 'wave.vrma', mappings: [] }]
  const { motionMap } = buildVrmPayload(clips, {}, {}, [], {}, {})
  assert.deepEqual(motionMap, {})
})

test('buildVrmPayload：空白情緒關鍵字跳過，emotionMap 存 preset 名字不是索引', () => {
  const expressions: VrmExpressionEntry[] = [
    { name: 'happy', keywords: [] },
    { name: 'sad', keywords: [] },
  ]
  const expressionRows: Record<string, string> = { happy: 'joy', sad: '   ' }
  const { emotionMap } = buildVrmPayload([], {}, {}, expressions, expressionRows, {})
  assert.deepEqual(emotionMap, { joy: 'happy' })
})

test('buildVrmPayload：情緒關鍵字的 extras 會 trim 並跳過空白後原樣保留', () => {
  const expressions: VrmExpressionEntry[] = [{ name: 'happy', keywords: [] }]
  const expressionRows: Record<string, string> = { happy: 'joy' }
  const extraEmotionKeywords: Record<string, string[]> = { happy: ['  glad  ', '   '] }
  const { emotionMap } = buildVrmPayload([], {}, {}, expressions, expressionRows, extraEmotionKeywords)
  assert.deepEqual(emotionMap, { joy: 'happy', glad: 'happy' })
})

test('buildVrmPayload：motionMap 與 emotionMap 互不干擾，各自從各自的輸入組裝', () => {
  const clips: VrmClipEntry[] = [{ clip: 'nod', file: 'nod.vrma', mappings: [] }]
  const rows: Record<string, VrmMotionRowEdit> = { nod: { keyword: 'yes', label: '' } }
  const expressions: VrmExpressionEntry[] = [{ name: 'happy', keywords: [] }]
  const expressionRows: Record<string, string> = { happy: 'joy' }
  const { motionMap, emotionMap } = buildVrmPayload(clips, rows, {}, expressions, expressionRows, {})
  assert.deepEqual(motionMap, { yes: { clip: 'nod', label: null } })
  assert.deepEqual(emotionMap, { joy: 'happy' })
})

// review a0c0ce7 fix 1（critical）：emotionPresets 濾掉的 preset（嘴型／眨眼／視線／
// neutral）從來不會出現在 `expressions` 這個參數裡——UI 沒有畫面可以編輯它們。
// 存檔前必須把它們的既有關鍵字原樣帶回 hiddenEmotionKeywords，否則每次存檔都會
// 把 neutral→neutral 這種每個 VRM 模型出廠就有的對應洗掉（kurisu_3d* 系列甚至
// 整份 emotionMap 都是被排除的 preset，可見列表是空的，不帶回等於整份清空）。
test('buildVrmPayload：指向被排除 preset 的關鍵字存檔後原樣保留', () => {
  const expressions: VrmExpressionEntry[] = [{ name: 'happy', keywords: [] }]
  const expressionRows: Record<string, string> = { happy: 'joy' }
  const hiddenEmotionKeywords: Record<string, string[]> = { neutral: ['neutral'] }
  const { emotionMap } = buildVrmPayload(
    [], {}, {}, expressions, expressionRows, {}, hiddenEmotionKeywords,
  )
  assert.deepEqual(emotionMap, { joy: 'happy', neutral: 'neutral' })
})

test('buildVrmPayload：可見清單全空時（kurisu_3d 形狀），存檔後的 map 等於載入時的 map', () => {
  // kurisu_3d 系列：expressionManager 裡只有 neutral 這個 preset，emotionPresets
  // 過濾完是空陣列——畫面上完全沒有表情列可編輯，但 hiddenEmotionKeywords 仍要把
  // 載入時讀到的 neutral→neutral 原樣帶回去。
  const hiddenEmotionKeywords: Record<string, string[]> = { neutral: ['neutral'] }
  const { motionMap, emotionMap } = buildVrmPayload([], {}, {}, [], {}, {}, hiddenEmotionKeywords)
  assert.deepEqual(motionMap, {})
  assert.deepEqual(emotionMap, { neutral: 'neutral' })
})

test('buildVrmPayload：hiddenEmotionKeywords 省略時不影響既有行為（向下相容）', () => {
  const expressions: VrmExpressionEntry[] = [{ name: 'happy', keywords: [] }]
  const expressionRows: Record<string, string> = { happy: 'joy' }
  const { emotionMap } = buildVrmPayload([], {}, {}, expressions, expressionRows, {})
  assert.deepEqual(emotionMap, { joy: 'happy' })
})
