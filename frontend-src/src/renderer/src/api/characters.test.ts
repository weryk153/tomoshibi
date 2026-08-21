import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildCharacterUpdate, validateAvatarFile, AVATAR_MAX_CLIENT_BYTES,
  type CharacterRecord,
} from './characters.ts'

const current: CharacterRecord = {
  filename: 'mao.yaml',
  slug: 'mao',
  is_base: false,
  conf_name: '小貓',
  character_name: '貓',
  avatar: 'avatars/mao.png',
  conf_uid: 'mao_001',
  persona_prompt: '你是一隻貓。',
  live2d_model_name: 'mao_pro',
  voice: 'zh-TW-HsiaoChenNeural',
  reply_language: '',
  voice_lang: '',
  tts_model: '',
}

test('只改一個欄位時，其他欄位必須沿用現值——這是資料遺失的主要來源', () => {
  const body = buildCharacterUpdate(current, { persona_prompt: '你是一隻很懶的貓。' })
  assert.equal(body.persona_prompt, '你是一隻很懶的貓。')
  assert.equal(body.conf_name, '小貓', 'conf_name 不得遺失')
  assert.equal(body.live2d_model_name, 'mao_pro', 'live2d_model_name 不得遺失')
  assert.equal(body.voice, 'zh-TW-HsiaoChenNeural', 'voice 不得遺失')
})

test('完全沒有編輯時，送出的內容等於現值', () => {
  const body = buildCharacterUpdate(current, {})
  assert.deepEqual(body, {
    conf_name: '小貓',
    persona_prompt: '你是一隻貓。',
    live2d_model_name: 'mao_pro',
    voice: 'zh-TW-HsiaoChenNeural',
  })
})

test('現值為 null 的欄位轉成空字串，不得送出 null——後端的驗證只認 falsy 與否', () => {
  const blank: CharacterRecord = { ...current, voice: null, persona_prompt: null }
  const body = buildCharacterUpdate(blank, {})
  assert.equal(body.voice, '')
  assert.equal(body.persona_prompt, '')
})

test('編輯值為空字串時要保留空字串，不能被現值蓋回去——那會讓使用者無法清空欄位', () => {
  const body = buildCharacterUpdate(current, { voice: '' })
  assert.equal(body.voice, '', '明確清空必須生效')
})

const rec: CharacterRecord = {
  filename: 'mao.yaml', slug: 'mao', is_base: false,
  conf_name: '小貓', character_name: '貓', avatar: 'avatars/mao.png',
  conf_uid: 'mao_001', persona_prompt: '你是一隻貓。',
  live2d_model_name: 'mao_pro', voice: 'zh-TW-HsiaoChenNeural',
  reply_language: '', voice_lang: '', tts_model: '',
}

test('不傳 optional 時，酬載不含 character_name 與 avatar——後端會因此保留現值', () => {
  const body = buildCharacterUpdate(rec, { persona_prompt: '懶貓。' })
  assert.ok(!('character_name' in body), '未編輯就不該送 character_name')
  assert.ok(!('avatar' in body), '未編輯就不該送 avatar')
})

test('傳了 optional 才會出現在酬載裡', () => {
  const body = buildCharacterUpdate(rec, {}, { character_name: '喵喵' })
  assert.equal(body.character_name, '喵喵')
  assert.ok(!('avatar' in body), '只編輯了名稱就不該送頭像')
})

test('optional 的空字串要送出去——那是「清除」，不是「未編輯」', () => {
  const body = buildCharacterUpdate(rec, {}, { avatar: '' })
  assert.equal(body.avatar, '', '清除頭像必須送出空字串')
  assert.ok('avatar' in body)
})

test('optional 的 undefined 視為未編輯，不得送出', () => {
  const body = buildCharacterUpdate(rec, {}, { character_name: undefined })
  assert.ok(!('character_name' in body), 'undefined 必須當成未編輯')
})

// 這四個選填鍵在 buildCharacterUpdate 裡是走同一個迴圈的，但漏掉其中一個不會有
// 任何錯誤訊息——那個欄位只是永遠存不進去。所以每個鍵都要各自被釘住一次。
for (const key of ['character_name', 'avatar', 'reply_language', 'voice_lang'] as const) {
  test(`選填欄位 ${key}：有傳就要出現在酬載裡`, () => {
    const body = buildCharacterUpdate(rec, {}, { [key]: 'X' })
    assert.equal(body[key], 'X')
  })

  test(`選填欄位 ${key}：沒傳就完全不出現`, () => {
    const body = buildCharacterUpdate(rec, {}, {})
    assert.ok(!(key in body), `未編輯的 ${key} 不該送出`)
  })

  test(`選填欄位 ${key}：空字串是「清除」，必須送出`, () => {
    const body = buildCharacterUpdate(rec, {}, { [key]: '' })
    assert.ok(key in body, `清除 ${key} 必須送出空字串而不是省略`)
    assert.equal(body[key], '')
  })
}

test('reply_language 與 voice_lang 是兩個獨立的欄位，不得互相汙染', () => {
  // 兩者語意完全不同（她用什麼語言寫 vs 用什麼語言唸），若實作不小心共用了
  // 同一個鍵，只改其中一個時另一個會跟著變，而畫面上看起來一切正常。
  const body = buildCharacterUpdate(rec, {}, { reply_language: 'Japanese' })
  assert.equal(body.reply_language, 'Japanese')
  assert.ok(!('voice_lang' in body), '只改回覆語言不該動到發聲語言')
})

test('前端頭像上限必須是 512KB，刻意比後端 4MB 更嚴格——不得被「修」成跟後端一致', () => {
  // 直接鎖常數本身的值，而不是只用它去建構測試 fixture：後者在常數被改動時
  // 會跟著一起變大，測試永遠通過，等於沒測到「上限確實是 512KB」這件事
  // （final review 抓到的：把常數從 512KB 改成 4MB 後，原本 11 個測試全數通過）。
  assert.equal(AVATAR_MAX_CLIENT_BYTES, 512 * 1024)
})

test('頭像大小超過前端上限時回傳 i18n 鍵', () => {
  const big = { name: 'a.png', size: AVATAR_MAX_CLIENT_BYTES + 1, type: 'image/png' } as File
  assert.equal(validateAvatarFile(big), 'settings.characters.aiAvatarTooLarge')
})

test('非圖片檔回傳 i18n 鍵', () => {
  const txt = { name: 'a.txt', size: 10, type: 'text/plain' } as File
  assert.equal(validateAvatarFile(txt), 'settings.characters.aiAvatarNotImage')
})

test('型別錯又過大時，回報「不是圖片」而不是「太大」——型別檢查必須先於大小檢查', () => {
  // 這個 fixture 同時踩中兩種錯誤：驗證順序若被調換（先驗大小），會回傳
  // aiAvatarTooLarge，這個斷言就會失敗，藉此釘住「型別優先」的順序
  // （final review 抓到的：把順序調換後，原本 11 個測試全數通過）。
  const bigTxt = {
    name: 'a.txt', size: AVATAR_MAX_CLIENT_BYTES + 1, type: 'text/plain',
  } as File
  assert.equal(validateAvatarFile(bigTxt), 'settings.characters.aiAvatarNotImage')
})

test('合法圖片回傳 null', () => {
  const ok = { name: 'a.png', size: 1000, type: 'image/png' } as File
  assert.equal(validateAvatarFile(ok), null)
})
