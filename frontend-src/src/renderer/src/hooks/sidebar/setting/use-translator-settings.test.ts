import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  SUBTITLE_LANG_OPTIONS,
  SUBTITLE_LANG_ORIGINAL,
  mapSubtitleSelection,
  subtitleStateToSelection,
} from './use-translator-settings.ts'

// 這份清單必須跟 src/open_llm_vtuber/translate/deeplx.py 的
// LANG_NAME_TO_DEEPL_CODE 逐字同步（該檔案的表頭註解明確指名這個檔案）。
// 這裡手動抄一份「應該有的 30 個值」，用逐一比對而不是只比長度——長度相同
// 但漏一個、多一個不相關的值，或哪個字打錯，都要讓測試失敗。
const EXPECTED_VALUES = [
  '繁體中文', '日文', '英文', '韓文', '保加利亞文', '捷克文', '丹麥文', '德文',
  '希臘文', '西班牙文', '愛沙尼亞文', '芬蘭文', '法文', '匈牙利文', '印尼文',
  '義大利文', '立陶宛文', '拉脫維亞文', '挪威文', '荷蘭文', '波蘭文', '葡萄牙文',
  '羅馬尼亞文', '俄文', '斯洛伐克文', '斯洛維尼亞文', '瑞典文', '土耳其文',
  '烏克蘭文', '簡體中文',
]

test('SUBTITLE_LANG_OPTIONS 恰好 30 個，跟 deeplx.py 的 LANG_NAME_TO_DEEPL_CODE 逐字同步', () => {
  assert.deepEqual(SUBTITLE_LANG_OPTIONS.map((o) => o.value), EXPECTED_VALUES)
})

test('SUBTITLE_LANG_OPTIONS 每一項的 value 都是非空字串，且不等於「原文」哨兵值', () => {
  for (const opt of SUBTITLE_LANG_OPTIONS) {
    assert.ok(opt.value.trim().length > 0, `空字串不該出現在語言清單裡：${JSON.stringify(opt)}`)
    assert.notEqual(opt.value, SUBTITLE_LANG_ORIGINAL)
  }
})

test('SUBTITLE_LANG_OPTIONS 的 labelKey 都指向 settings.translator.subtitleLangXx 命名空間', () => {
  for (const opt of SUBTITLE_LANG_OPTIONS) {
    assert.match(opt.labelKey, /^settings\.translator\.subtitleLang[A-Za-z]+$/)
  }
})

test('SUBTITLE_LANG_OPTIONS 沒有重複值（下拉選單不能有兩個一樣的選項）', () => {
  const values = SUBTITLE_LANG_OPTIONS.map((o) => o.value)
  assert.equal(new Set(values).size, values.length)
})

test('mapSubtitleSelection：選「原文」關閉字幕翻譯並清空 target', () => {
  assert.deepEqual(mapSubtitleSelection(SUBTITLE_LANG_ORIGINAL), {
    translate_subtitle: false,
    subtitle_target_lang: '',
  })
})

test('mapSubtitleSelection：選一個語言開啟字幕翻譯，target 就是選到的值', () => {
  assert.deepEqual(mapSubtitleSelection('日文'), {
    translate_subtitle: true,
    subtitle_target_lang: '日文',
  })
})

test('subtitleStateToSelection：translate_subtitle=false 一律顯示「原文」，不管殘留的 target 值', () => {
  assert.equal(
    subtitleStateToSelection({ translate_subtitle: false, subtitle_target_lang: '日文' }),
    SUBTITLE_LANG_ORIGINAL,
  )
})

test('subtitleStateToSelection：translate_subtitle=true 顯示目前的 target 值', () => {
  assert.equal(
    subtitleStateToSelection({ translate_subtitle: true, subtitle_target_lang: '韓文' }),
    '韓文',
  )
})

test('mapSubtitleSelection 與 subtitleStateToSelection 互為反函式（round-trip）', () => {
  for (const opt of SUBTITLE_LANG_OPTIONS) {
    const mapped = mapSubtitleSelection(opt.value)
    assert.equal(subtitleStateToSelection(mapped), opt.value)
  }
  const original = mapSubtitleSelection(SUBTITLE_LANG_ORIGINAL)
  assert.equal(subtitleStateToSelection(original), SUBTITLE_LANG_ORIGINAL)
})
