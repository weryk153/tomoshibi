import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mapMemoryResponse } from './memory.ts'

test('mapMemoryResponse keeps only what the engine memory page needs', () => {
  const state = mapMemoryResponse({
    conf_uid: 'kurisu',
    enabled: true,
    content: '對方：名字是晨星。',
    self_content: '紅莉栖喜歡咖啡。',
  })
  assert.deepEqual(state, {
    enabled: true,
    content: '對方：名字是晨星。',
    self_content: '紅莉栖喜歡咖啡。',
  })
})
