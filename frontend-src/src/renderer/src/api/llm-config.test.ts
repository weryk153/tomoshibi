import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildSavePayload, type LlmFormState } from './llm-config.ts'

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
