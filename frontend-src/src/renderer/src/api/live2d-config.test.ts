import { test } from 'node:test'
import assert from 'node:assert/strict'
import { validateKeyword } from './live2d-config.ts'

test('空字串回傳 empty', () => {
  assert.equal(validateKeyword('', []), 'empty')
})

test('只有空白的字串回傳 empty', () => {
  assert.equal(validateKeyword('   ', []), 'empty')
  assert.equal(validateKeyword('\t\n', []), 'empty')
})

test('與既有關鍵字重複回傳 duplicate（不分大小寫）', () => {
  assert.equal(validateKeyword('wave', ['Wave']), 'duplicate')
  assert.equal(validateKeyword('WAVE', ['wave']), 'duplicate')
})

// 後端掃描器是逐字元找 '[' 再比對 `[key]`，所以關鍵字本身含有 '[' 或 ']'
// 會讓比對錯亂。
test('含有方括號回傳 invalidChars', () => {
  assert.equal(validateKeyword('[wave]', []), 'invalidChars')
  assert.equal(validateKeyword('wa[ve', []), 'invalidChars')
  assert.equal(validateKeyword('wave]', []), 'invalidChars')
})

test('合法關鍵字回傳 null', () => {
  assert.equal(validateKeyword('wave', []), null)
  assert.equal(validateKeyword('wave', ['nod', 'shake']), null)
})

// 大小寫不敏感這點很重要：後端建構 motion_map 時做 k.lower()，"Wave" 與
// "wave" 是同一個鍵，前端若不擋，使用者會存進兩筆而其中一筆永遠打不中。
test('關鍵字比對大小寫不敏感——後端會把 key 轉小寫', () => {
  assert.equal(validateKeyword('Wave', ['wave']), 'duplicate')
  assert.equal(validateKeyword('wAvE', ['WaVe']), 'duplicate')
})

test('關鍵字前後有空白時，trim 之後再比對是否重複', () => {
  assert.equal(validateKeyword('  wave  ', ['wave']), 'duplicate')
})

// 若兩種問題同時成立，「這個字元不合法」比「這個字重複了」更接近使用者
// 要先修的問題——釘住檢查順序是 invalidChars 先於 duplicate。
test('同時含方括號又重複時，優先回報 invalidChars', () => {
  assert.equal(validateKeyword('[wave]', ['[wave]']), 'invalidChars')
})

test('空字串優先於其他所有檢查', () => {
  assert.equal(validateKeyword('', ['']), 'empty')
})
