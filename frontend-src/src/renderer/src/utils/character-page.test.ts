import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  isActiveCharacter, skinTypeOf, isLoadedModel, voiceFieldGroups, nextSelection, personaApplyMode,
} from './character-page.ts'

const records = [
  { filename: 'conf.yaml', conf_uid: 'frieren' },
  { filename: 'himmel.yaml', conf_uid: 'himmel' },
]

test('the active character is the one whose conf_uid is loaded', () => {
  assert.equal(isActiveCharacter({ conf_uid: 'himmel' }, 'himmel'), true)
  assert.equal(isActiveCharacter({ conf_uid: 'frieren' }, 'himmel'), false)
  // 連線還沒回報是哪個角色時（confUid 是空字串），誰都不是正在用的。
  assert.equal(isActiveCharacter({ conf_uid: null }, ''), false)
})

test('a model\'s type comes from the skin list; unknown models have none', () => {
  const skins = [{ name: 'kurisu', type: 'live2d' as const }, { name: 'alicia', type: 'vrm' as const }]
  assert.equal(skinTypeOf(skins, 'alicia'), 'vrm')
  assert.equal(skinTypeOf(skins, 'kurisu'), 'live2d')
  assert.equal(skinTypeOf(skins, 'gone'), null)
})

test('only the model on screen can be previewed or have its live tap motions replaced', () => {
  assert.equal(isLoadedModel('kurisu', 'kurisu'), true)
  assert.equal(isLoadedModel('alicia', 'kurisu'), false)
  assert.equal(isLoadedModel(undefined, undefined), false)
  assert.equal(isLoadedModel('kurisu', undefined), false)
})

test('the voice section shows only the chosen engine\'s fields', () => {
  assert.deepEqual(voiceFieldGroups('edge_tts'), { edge: true, gptSovits: false })
  assert.deepEqual(voiceFieldGroups('gpt_sovits_tts'), { edge: false, gptSovits: true })
  // 沿用全域：不知道全域是哪個引擎，兩組都給。
  assert.deepEqual(voiceFieldGroups('__inherit__'), { edge: true, gptSovits: true })
  assert.deepEqual(voiceFieldGroups(''), { edge: true, gptSovits: true })
  // 其他引擎的參數不在角色檔，畫面上兩組都不給。
  assert.deepEqual(voiceFieldGroups('azure_tts'), { edge: false, gptSovits: false })
})

test('the selection survives a refresh, and falls back to the active character when its record is gone', () => {
  assert.equal(nextSelection(records, 'himmel.yaml', 'frieren'), 'himmel.yaml')
  assert.equal(nextSelection(records, 'deleted.yaml', 'frieren'), 'conf.yaml')
  assert.equal(nextSelection(records, null, 'himmel'), 'himmel.yaml')
  // 不知道哪個在用：退回第一筆。
  assert.equal(nextSelection(records, null, ''), 'conf.yaml')
  assert.equal(nextSelection([], null, 'frieren'), null)
})

test('a persona is applied live only to the character in use', () => {
  assert.equal(personaApplyMode(true), 'live')
  assert.equal(personaApplyMode(false), 'stored')
})
