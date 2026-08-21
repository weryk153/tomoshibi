import { test } from 'node:test'
import assert from 'node:assert/strict'
import { settingsEqual, settingsDirty } from './settings-dirty.ts'

test('相同的扁平設定物件視為未變更', () => {
  const a = { language: ['zh'], showSubtitle: true, imageMaxWidth: 0 }
  const b = { language: ['zh'], showSubtitle: true, imageMaxWidth: 0 }
  assert.equal(settingsDirty(a, b), false)
})

test('任何一個欄位不同就是有變更', () => {
  const a = { language: ['zh'], showSubtitle: true }
  const b = { language: ['zh'], showSubtitle: false }
  assert.equal(settingsDirty(a, b), true)
})

test('鍵的順序不同不算變更——setState 展開本來就會改變順序', () => {
  // 這正是不能用 JSON.stringify 比對的原因：字串會不同，但值完全一樣。
  const a = { wsUrl: 'ws://a', baseUrl: 'http://b' }
  const b = { baseUrl: 'http://b', wsUrl: 'ws://a' }
  assert.equal(JSON.stringify(a) === JSON.stringify(b), false, '前提：字串確實不同')
  assert.equal(settingsDirty(a, b), false)
})

test('陣列逐項比對，順序有意義', () => {
  assert.equal(settingsDirty({ l: ['zh', 'en'] }, { l: ['zh', 'en'] }), false)
  assert.equal(settingsDirty({ l: ['zh', 'en'] }, { l: ['en', 'zh'] }), true)
  assert.equal(settingsDirty({ l: ['zh'] }, { l: ['zh', 'en'] }), true)
})

test('缺鍵與 undefined 視為同一件事', () => {
  // 設定物件常常在某個欄位還沒被碰過時整個鍵都不存在，那跟明確的 undefined
  // 對使用者是同一個狀態，不該讓按鈕亮起來。
  assert.equal(settingsDirty({ a: 1 }, { a: 1, b: undefined }), false)
})

test('null 與 undefined 視為相等，但都不等於空字串', () => {
  assert.equal(settingsEqual(null, undefined), true)
  assert.equal(settingsEqual(null, ''), false)
})

test('型別不同就是有變更——數字 0 不等於字串 "0"', () => {
  // 數字欄位從輸入框讀回來時很容易變成字串，混為一談的話按鈕會該亮不亮。
  assert.equal(settingsDirty({ n: 0 }, { n: '0' }), true)
  assert.equal(settingsDirty({ b: false }, { b: 0 }), true)
})

test('兩個 NaN 視為未變更——數字輸入到一半真的會是 NaN', () => {
  // 不特別處理的話 NaN !== NaN，按鈕會一直亮著，看起來像有改其實沒有。
  assert.equal(settingsDirty({ n: NaN }, { n: NaN }), false)
  assert.equal(settingsDirty({ n: NaN }, { n: 1 }), true)
})

test('巢狀物件會比到底', () => {
  assert.equal(settingsDirty({ a: { b: { c: 1 } } }, { a: { b: { c: 1 } } }), false)
  assert.equal(settingsDirty({ a: { b: { c: 1 } } }, { a: { b: { c: 2 } } }), true)
})

test('陣列與物件不會互相誤判成相等', () => {
  // [] 與 {} 的 Object.keys 都是空的，只比鍵的話會誤判成相等。
  assert.equal(settingsEqual([], {}), false)
  assert.equal(settingsEqual({ 0: 'a' }, ['a']), false)
})
