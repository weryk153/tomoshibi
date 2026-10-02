// 背景攝影機的串流槽。開攝影機是非同步的（要等使用者允許、等鏡頭暖機），這段時間
// 裡場景可能已經換走、或又開了一次。只靠「停的時候關掉手上那一條」會漏：晚到的
// 串流沒人關，鏡頭燈一直亮，而且再開一次時舊的那條會被蓋掉、再也關不到。
//
// 每次開始領一個號碼；串流回來時號碼不是最新的就直接關掉。停止也會讓手上的號碼
// 作廢。
export interface StoppableStream {
  getTracks(): { stop(): void }[]
}

export function createStreamSlot<S extends StoppableStream>(): {
  begin(): number
  accept(token: number, stream: S): boolean
  stop(): void
  current(): S | null
} {
  let generation = 0
  let current: S | null = null
  const stopStream = (stream: S): void => { stream.getTracks().forEach((track) => track.stop()) }

  return {
    begin() {
      generation += 1
      return generation
    },
    accept(token, stream) {
      if (token !== generation) {
        stopStream(stream)
        return false
      }
      if (current && current !== stream) stopStream(current)
      current = stream
      return true
    },
    stop() {
      generation += 1
      if (current) stopStream(current)
      current = null
    },
    current: () => current,
  }
}
