/**
 * 首次使用者手勢時解鎖音訊播放。
 *
 * iOS／iPadOS 的自動播放政策：程式主動呼叫 play() 必須源自使用者手勢，否則以
 * NotAllowedError 被拒。角色的語音是收到 WebSocket 訊息後自己播的，不算手勢，
 * 所以在 iPad 上每次都被擋——畫面有字幕、嘴型也在動，就是沒有聲音，要先點一下
 * 螢幕才會有。
 *
 * 做法是等第一次真正的使用者手勢，趁那個時機做兩件事：
 *   1. 播一段極短的無聲音訊——瀏覽器因此把這個頁面標記成「使用者已經允許播放」。
 *   2. 喚醒共用的 AudioContext（voice-gain 的音量放大走它，suspended 時會整段
 *      放棄放大）。
 *
 * 只做一次就夠，成功後把監聽器拆掉。
 *
 * 用 pointerdown/touchend/keydown 三種：iOS 對「什麼算手勢」比較嚴格，
 * pointerdown 在部分版本上不被接受，touchend 比較穩；桌面則靠 pointerdown
 * 與鍵盤輸入。三個都掛著，誰先來就用誰。
 */

import { unlockSharedAudio } from './shared-audio'

const GESTURES = ['touchend', 'pointerdown', 'keydown'] as const

let unlocked = false

/** 已經解鎖過了嗎（給測試與除錯用）。 */
export function isAudioUnlocked(): boolean {
  return unlocked
}

/**
 * 掛上一次性的解鎖監聽器。回傳解除函式，重複呼叫是安全的。
 */
export function installAudioUnlock(
  resumeContext?: () => void,
): () => void {
  if (typeof document === 'undefined' || unlocked) return () => {}

  const cleanups: Array<() => void> = []

  const unlock = (): void => {
    if (unlocked) return
    unlocked = true

    // 一定要解鎖「之後真的會用來播語音的那個元素」——授權掛在元素上，解鎖一個
    // 臨時的 new Audio() 對後面每一段語音毫無幫助（實測過，iPad 照樣被擋）。
    unlockSharedAudio()

    try {
      resumeContext?.()
    } catch {
      // AudioContext 還沒建立或已關閉，不影響解鎖本身。
    }

    cleanups.forEach((fn) => fn())
  }

  GESTURES.forEach((type) => {
    // once + passive：只需要搭一次順風車，不要干擾原本的手勢處理
    //（尤其 touchend，非 passive 會影響捲動判定）。
    document.addEventListener(type, unlock, { once: true, passive: true })
    cleanups.push(() => document.removeEventListener(type, unlock))
  })

  return () => cleanups.forEach((fn) => fn())
}
