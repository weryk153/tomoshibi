import { test } from 'node:test'
import assert from 'node:assert/strict'
import { chatLines, type ChatLineSource } from './mobile-chat.ts'

const ai = (id: string, content: string): ChatLineSource => ({ id, role: 'ai', content, type: 'text' })
const me = (id: string, content: string): ChatLineSource => ({ id, role: 'human', content })

test('她正在說話時，最後一則她的話是「正在說的那句」', () => {
  const lines = chatLines([me('1', '嗨'), ai('2', '嘿嘿，')], { speaking: true, limit: 30 })
  assert.deepEqual(lines.map((l) => [l.id, l.live]), [['1', false], ['2', true]])
})

test('她沒在說話，或最後一則是我說的，就沒有正在說的那句', () => {
  assert.equal(chatLines([ai('1', '好')], { speaking: false, limit: 30 }).some((l) => l.live), false)
  assert.equal(chatLines([ai('1', '好'), me('2', '嗯')], { speaking: true, limit: 30 }).some((l) => l.live), false)
})

test('只留最近幾則，空的與工具狀態不顯示', () => {
  const many = Array.from({ length: 40 }, (_, i) => me(String(i), `第${i}句`))
  const lines = chatLines([...many, { id: 'x', role: 'ai', content: '', type: 'tool_call_status' }], { speaking: false, limit: 30 })
  assert.equal(lines.length, 30)
  assert.equal(lines[lines.length - 1].id, '39')
})
