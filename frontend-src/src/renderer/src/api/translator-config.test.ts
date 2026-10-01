import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildTranslatorSavePayload,
  isTranslatorEngine,
  VALID_ENGINES,
  type TranslatorConfigState,
} from './translator-config.ts'

// 一份「已經從後端 GET 回來」的完整設定，代表使用者手動編輯過 conf.yaml、
// 幫 llm 區塊加上非預設值的情境——跟任務簡報描述的 extra_body／timeout 陷阱
// 同一種精神：這些欄位在 UI 上沒有輸入框，任何一次存檔都不該把它們改掉。
const CURRENT: TranslatorConfigState = {
  enabled: true,
  engine: 'llm',
  raw_provider: 'llm',
  llm_target_lang: '英文', // 使用者手動改過，不是預設的「日文」
  llm_endpoint: 'http://localhost:9999/v1/chat/completions',
  llm_model: 'custom/model-name',
  deeplx_target_lang: 'DE', // 使用者手動改過，不是預設的 'JA'
  deeplx_endpoint: 'http://localhost:1188/v2/translate',
  speak_voice: 'zh-CN-XiaoyiNeural',
  default_jp_voice: 'ja-JP-NanamiNeural',
}

test('buildTranslatorSavePayload：只切換引擎時，沒有 UI 控制項的隱藏欄位原樣保留', () => {
  const payload = buildTranslatorSavePayload(CURRENT, {
    engine: 'deeplx',
    deeplx_endpoint: 'http://localhost:1188/v2/translate',
  })
  assert.equal(payload.engine, 'deeplx')
  assert.equal(payload.llm_target_lang, '英文')
  assert.equal(payload.llm_endpoint, 'http://localhost:9999/v1/chat/completions')
  assert.equal(payload.llm_model, 'custom/model-name')
  assert.equal(payload.deeplx_target_lang, 'DE')
})

test('buildTranslatorSavePayload：字幕設定不再經過這裡', () => {
  const payload = buildTranslatorSavePayload(CURRENT, {})
  assert.equal(payload.engine, CURRENT.engine)
  assert.equal(payload.deeplx_endpoint, CURRENT.deeplx_endpoint)
  assert.equal('translate_subtitle' in payload, false)
  assert.equal('subtitle_target_lang' in payload, false)
})

test('isTranslatorEngine：只接受 llm／deeplx', () => {
  assert.equal(isTranslatorEngine('llm'), true)
  assert.equal(isTranslatorEngine('deeplx'), true)
  assert.equal(isTranslatorEngine('tencent'), false)
  assert.equal(isTranslatorEngine(''), false)
})

test('VALID_ENGINES 跟後端 translator_route.py 的 VALID_ENGINES 一致', () => {
  assert.deepEqual([...VALID_ENGINES], ['llm', 'deeplx'])
})
