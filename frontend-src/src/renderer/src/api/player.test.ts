import { test } from 'node:test'
import assert from 'node:assert/strict'
import { normalizePlayerPrompt, PLAYER_LANGUAGES } from './player.ts'

test('把換行摺成單一空白', () => {
  assert.equal(normalizePlayerPrompt('第一行\n第二行'), '第一行 第二行')
})

test('把 CRLF 也摺成單一空白', () => {
  assert.equal(normalizePlayerPrompt('第一行\r\n第二行'), '第一行 第二行')
})

test('連續換行與空白摺成單一空白', () => {
  assert.equal(normalizePlayerPrompt('第一行\n\n\n  第二行'), '第一行 第二行')
})

test('去除前後空白', () => {
  assert.equal(normalizePlayerPrompt('  你好  '), '你好')
})

test('純空白字串變成空字串', () => {
  assert.equal(normalizePlayerPrompt('  \n \n '), '')
})

test('不改動單行且已乾淨的字串', () => {
  assert.equal(normalizePlayerPrompt('我是台灣人，講中文。'), '我是台灣人，講中文。')
})

// 後端的 re.sub(r"\s*\n\s*", " ", ...) 只摺「含有換行的空白串」，同一行內的
// 連續空格與 tab 它原樣保留。前端若用 /\s+/g 就會比後端更激進，把使用者刻意
// 打的間距靜默改掉——而後端本來根本不會動它。
test('同一行內的連續空白原樣保留（不比後端更激進）', () => {
  assert.equal(normalizePlayerPrompt('我   很喜歡貓'), '我   很喜歡貓')
})

test('同一行內的 tab 原樣保留', () => {
  assert.equal(normalizePlayerPrompt('欄一\t\t欄二'), '欄一\t\t欄二')
})

test('跨行時連同前後空白一起摺成單一空白', () => {
  assert.equal(normalizePlayerPrompt('第一行   \n   第二行'), '第一行 第二行')
})

test('PLAYER_LANGUAGES 的五個代碼與 i18n 鍵一一對應', () => {
  assert.deepEqual(
    PLAYER_LANGUAGES.map((l) => l.value),
    ['zh-TW', 'en', 'ja', 'ko', 'zh-CN'],
  )
  assert.deepEqual(
    PLAYER_LANGUAGES.map((l) => l.labelKey),
    [
      'settings.playerLanguage.optZhTw',
      'settings.playerLanguage.optEn',
      'settings.playerLanguage.optJa',
      'settings.playerLanguage.optKo',
      'settings.playerLanguage.optZhCn',
    ],
  )
})
