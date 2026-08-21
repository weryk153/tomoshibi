// 這些測試對應一個實際卡死過的情境：一段音訊被外部停掉之後，它的播放 task
// 永遠不會 resolve，整條音訊佇列就此停擺。後果不只是「後面幾句沒播出來」——
// waitForCompletion() 跟著永不 resolve，前端就再也不會送出
// frontend-playback-complete，後端在 finalize_conversation_turn 無限等待，
// conversation-chain-end 永遠不送，前端 aiState 卡在 thinking-speaking，
// 於是「主動發言」的閒置計時器永遠不會啟動。
//
// 佇列本身擋不住上游送進來的壞 task，但它不該把一個壞 task 放大成整個 session
// 停擺。以下三項就是這條防線。

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { TaskQueue } from './task-queue.ts'

const tick = (ms = 0): Promise<void> => new Promise((resolve) => { setTimeout(resolve, ms) })

// timeout：這些案例的失敗形態就是「永遠不結束」，沒有 timeout 的話測試會掛住
// 而不是紅燈，CI 上看起來像卡住而不是失敗。
test('永不結束的任務不會把整條佇列鎖死', { timeout: 5000 }, async () => {
  const queue = new TaskQueue(0, 50)
  let secondRan = false

  queue.addTask(() => new Promise<void>(() => {}))
  queue.addTask(async () => { secondRan = true })

  await tick(250)

  assert.equal(secondRan, true, '前一個任務卡住時，後續任務仍必須有機會執行')
  assert.equal(queue.hasTask(), false, '卡住的任務不可讓 hasTask() 永遠為真')
})

test('waitForCompletion 在任務卡住時仍會結束', { timeout: 5000 }, async () => {
  const queue = new TaskQueue(0, 50)

  queue.addTask(() => new Promise<void>(() => {}))
  await queue.waitForCompletion()

  assert.equal(queue.hasTask(), false)
})

test('清空佇列後，原本在飛的任務結束時不會再啟動第二條抽取迴圈', { timeout: 5000 }, async () => {
  const queue = new TaskQueue(0, 5000)
  let release: () => void = () => {}
  let running = 0
  let maxRunning = 0

  const tracked = (body: () => Promise<void>) => async (): Promise<void> => {
    running += 1
    maxRunning = Math.max(maxRunning, running)
    await body()
    running -= 1
  }

  queue.addTask(tracked(() => new Promise<void>((resolve) => { release = resolve })))
  await tick(10)

  // 使用者打斷：conversation-chain-start 會呼叫 clearQueue()，但上面那個
  // task 此刻仍在飛。
  queue.clearQueue()

  queue.addTask(tracked(() => tick(40)))
  queue.addTask(tracked(() => tick(40)))
  await tick(10)

  // 被清掉的舊 task 現在才結束——它的收尾不可以去推動新的佇列。
  release()
  await tick(300)

  assert.equal(maxRunning, 1, '任何時刻都只能有一個任務在播，否則會出現疊音')
})
