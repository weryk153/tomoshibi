import { test } from 'node:test'
import assert from 'node:assert/strict'
import { AudioManager } from './audio-manager.ts'

type FakeAudio = HTMLAudioElement & {
  pauseCalls: number
  loadCalls: number
}

function makeAudio(): FakeAudio {
  return {
    src: 'data:audio/wav;base64,test',
    pauseCalls: 0,
    loadCalls: 0,
    pause() {
      this.pauseCalls += 1
    },
    load() {
      this.loadCalls += 1
    },
  } as FakeAudio
}

function makeModel() {
  return {
    idleCalls: 0,
    _wavFileHandler: {
      releaseCalls: 0,
      _lastRms: 0.9,
      _sampleOffset: 42,
      _userTimeSeconds: 1.5,
      releasePcmData() {
        this.releaseCalls += 1
      },
    },
    returnToIdleMotion() {
      this.idleCalls += 1
    },
  }
}

// 播放任務的 promise 只靠 audio 的 canplaythrough／ended／error 事件收尾。
// 被外部停掉的音訊（stopCurrentAudioAndLipSync 會 pause + 清空 src + load）
// 這三個事件一個都不會來，promise 就永遠懸著，音訊佇列跟著卡死。所以「停止」
// 必須是一條確定會收尾的路徑，而不是指望瀏覽器補一個事件給我們。
test('外部停止播放時，仍在等待的播放任務會被收尾', () => {
  const manager = new AudioManager()
  const model = makeModel()
  const audio = makeAudio()
  let settled = 0

  manager.beginSpeaking(model)
  manager.setCurrentAudio(audio, model, () => { settled += 1 })
  manager.stopCurrentAudioAndLipSync()

  assert.equal(settled, 1, '停止播放必須讓等待中的任務結束，否則佇列會卡住')

  manager.stopCurrentAudioAndLipSync()
  assert.equal(settled, 1, '重複停止不可重複收尾')
})

test('音訊自然結束後，再停止播放不會重複收尾', () => {
  const manager = new AudioManager()
  const model = makeModel()
  const audio = makeAudio()
  let settled = 0

  manager.beginSpeaking(model)
  manager.setCurrentAudio(audio, model, () => { settled += 1 })
  // ended 事件已經自己 resolve 過，並解除註冊。
  manager.clearCurrentAudio(audio)
  manager.stopCurrentAudioAndLipSync()

  assert.equal(settled, 0, '自然結束的任務不該再被停止路徑收尾一次')
})

test('連續語音分段只在第一段啟動 Talk', () => {
  const manager = new AudioManager()
  const model = makeModel()

  assert.equal(manager.beginSpeaking(model), true)
  assert.equal(manager.beginSpeaking(model), false)
})

test('一段音訊自然結束後仍保留整次回覆的 speaking 狀態', () => {
  const manager = new AudioManager()
  const model = makeModel()
  const firstAudio = makeAudio()

  assert.equal(manager.beginSpeaking(model), true)
  manager.setCurrentAudio(firstAudio, model)
  manager.clearCurrentAudio(firstAudio)

  assert.equal(manager.hasCurrentAudio(), false)
  assert.equal(manager.beginSpeaking(model), false)
})

test('整次回覆完成時重設嘴型並以 Idle 淡出 Talk', () => {
  const manager = new AudioManager()
  const model = makeModel()
  const audio = makeAudio()

  manager.beginSpeaking(model)
  manager.setCurrentAudio(audio, model)
  manager.stopCurrentAudioAndLipSync()

  assert.equal(audio.pauseCalls, 1)
  assert.equal(audio.loadCalls, 1)
  assert.equal(audio.src, '')
  assert.equal(model._wavFileHandler.releaseCalls, 1)
  assert.equal(model._wavFileHandler._lastRms, 0)
  assert.equal(model._wavFileHandler._sampleOffset, 0)
  assert.equal(model._wavFileHandler._userTimeSeconds, 0)
  assert.equal(model.idleCalls, 1)
  assert.equal(manager.hasCurrentAudio(), false)

  assert.equal(manager.beginSpeaking(model), true)
})
