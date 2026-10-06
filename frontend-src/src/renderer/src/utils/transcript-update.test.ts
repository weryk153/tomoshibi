import { test } from 'node:test'
import assert from 'node:assert/strict'
import { applyTranscriptUpdate } from './transcript-update.ts'

type Msg = { id: string; content: string; role: 'ai' | 'human'; timestamp: string }

const human = (content: string): Msg => ({ id: content, content, role: 'human', timestamp: 't' })
const ai = (content: string): Msg => ({ id: content, content, role: 'ai', timestamp: 't' })

test('最後一則是使用者剛講的原始字：換成修好的字', () => {
  const messages = [ai('早安'), human('空尼七哇')]
  const updated = applyTranscriptUpdate(messages, '空尼七哇', 'こんにちは')
  assert.deepEqual(updated, [ai('早安'), { ...human('空尼七哇'), content: 'こんにちは' }])
  assert.equal(messages[1].content, '空尼七哇', '原陣列不能被改')
})

test('最後一則的字跟原始字不同：不動', () => {
  const messages = [human('別的話')]
  assert.equal(applyTranscriptUpdate(messages, '空尼七哇', 'こんにちは'), messages)
})

test('最後一則是她的回覆：不動，就算前面有同樣的字', () => {
  const messages = [human('空尼七哇'), ai('嗯？')]
  assert.equal(applyTranscriptUpdate(messages, '空尼七哇', 'こんにちは'), messages)
})

test('空陣列：不動', () => {
  const messages: Msg[] = []
  assert.equal(applyTranscriptUpdate(messages, '空尼七哇', 'こんにちは'), messages)
})
