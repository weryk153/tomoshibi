import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  activeWhere, buildSavePayload, initialSource, needsKeyAgain, setupErrorKey, type ActiveLlm, type LlmFormState,
} from './llm-config.ts'

const base: LlmFormState = {
  mode: 'apikey', provider: 'openai', apiKey: '', model: '', baseUrl: '',
}

test('apikey 模式送出 provider 為選定的供應商，且不送 base_url（讓後端填預設）', () => {
  const p = buildSavePayload({ ...base, provider: 'claude', apiKey: 'sk-x', model: 'claude-3' })
  assert.equal(p.provider, 'claude')
  assert.equal(p.model, 'claude-3')
  assert.equal(p.api_key, 'sk-x')
  assert.ok(!('base_url' in p), 'apikey 模式不應送 base_url')
})

test('ollama 模式送出 provider=ollama，且不需要 api_key（後端會自動填 "ollama"）', () => {
  const p = buildSavePayload({ ...base, mode: 'ollama', model: 'qwen2.5:3b' })
  assert.equal(p.provider, 'ollama')
  assert.equal(p.model, 'qwen2.5:3b')
})

test('custom 模式必須送出使用者填的 base_url，provider 用後端接受的 openai', () => {
  const p = buildSavePayload({
    ...base, mode: 'custom', model: 'x', apiKey: 'k', baseUrl: 'http://localhost:1234/v1',
  })
  assert.equal(p.base_url, 'http://localhost:1234/v1')
  assert.equal(p.provider, 'openai', 'custom 不是後端認得的 provider，必須映射')
})

test('欄位前後空白必須去除——貼上金鑰時最常帶到空白', () => {
  const p = buildSavePayload({ ...base, apiKey: '  sk-x  ', model: '  gpt-4o  ' })
  assert.equal(p.api_key, 'sk-x')
  assert.equal(p.model, 'gpt-4o')
})

test('ollama 模式即使沒有金鑰也要能組出 payload——後端會自動填 "ollama"', () => {
  const p = buildSavePayload({ ...base, mode: 'ollama', model: 'qwen2.5:3b', apiKey: '' })
  assert.equal(p.api_key, '')
  assert.equal(p.provider, 'ollama')
})

test('warn only when the switch is on and the model has no tools', async () => {
  const { shouldWarnNoTools } = await import('./llm-config.ts')
  assert.equal(shouldWarnNoTools(false, true), true)
  assert.equal(shouldWarnNoTools(false, false), false)
  assert.equal(shouldWarnNoTools(true, true), false)
  assert.equal(shouldWarnNoTools(null, true), false)
})

test('金鑰欄留空、網址換了被後端拒絕時，才請使用者重貼金鑰', () => {
  // 只換模型時後端會沿用存著的金鑰，前端不再先擋。
  assert.equal(needsKeyAgain('Missing API key.', '', true), true)
  assert.equal(needsKeyAgain('Missing API key.', 'sk-new', true), false)
  assert.equal(needsKeyAgain('Missing API key.', '', false), false)
  assert.equal(needsKeyAgain('401 unauthorized', '', true), false)
})

const active = (source: ActiveLlm['source'], extra: Partial<ActiveLlm> = {}): ActiveLlm => ({
  provider: 'openai_compatible_llm', source, api_provider: null, model: 'm', base_url: '', ...extra,
})

test('打開語言模型頁時，停在正在用的那個來源', () => {
  assert.equal(initialSource(active('local'), true), 'local')
  assert.equal(initialSource(active('ollama'), true), 'ollama')
  assert.equal(initialSource(active('apikey', { api_provider: 'claude' }), true), 'apikey')
  assert.equal(initialSource(active('custom'), true), 'custom')
  // 手改設定檔選了別的供應商：沒有對應的表單，停在 API 金鑰。
  assert.equal(initialSource(active('other'), true), 'apikey')
  // 還沒設定（首次精靈）：先偵測這台電腦上的模型。
  assert.equal(initialSource(active('custom'), false), 'local')
  assert.equal(initialSource(undefined, true), 'local')
})

test('「目前使用」寫得出它在哪裡', () => {
  assert.deepEqual(activeWhere(active('local')), { key: 'setup.whereLmStudio' })
  assert.deepEqual(activeWhere(active('ollama')), { key: 'setup.whereOllama' })
  assert.deepEqual(activeWhere(active('apikey', { api_provider: 'gemini' })), { key: 'setup.whereNamed', name: 'Gemini' })
  assert.deepEqual(
    activeWhere(active('custom', { base_url: 'https://openrouter.ai/api/v1' })),
    { key: 'setup.whereNamed', name: 'openrouter.ai' },
  )
  assert.deepEqual(activeWhere(active('custom', { base_url: 'not a url' })), { key: 'setup.whereNamed', name: 'not a url' })
  assert.deepEqual(activeWhere(active('other', { provider: 'claude_llm' })), { key: 'setup.whereNamed', name: 'claude_llm' })
})

test('後端的英文錯誤換成翻譯鍵；認不出來的照原文', () => {
  assert.deepEqual(
    setupErrorKey('Could not reach the endpoint. Check the URL (and that the server is running).'),
    { key: 'setup.errors.unreachable' },
  )
  assert.deepEqual(
    setupErrorKey('Authentication failed — the API key was rejected. Check the key.'),
    { key: 'setup.errors.auth' },
  )
  assert.deepEqual(setupErrorKey('Missing model name.'), { key: 'setup.errors.missingModel' })
  assert.deepEqual(
    setupErrorKey('Test call failed (APIError). Check the URL, model, and key.'),
    { key: 'setup.errors.testCallFailed', type: 'APIError' },
  )
  assert.equal(setupErrorKey('請求逾時（6000 毫秒）'), null)
})
