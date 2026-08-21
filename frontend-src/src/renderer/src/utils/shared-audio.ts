/**
 * 全 app 共用的那一個 <audio> 元素。
 *
 * 為什麼不是每段語音各建一個 new Audio()：iOS／iPadOS 的自動播放授權是**掛在
 * 元素上**的。使用者點過畫面之後，只有「在那個手勢裡播過的那個元素」拿到授權；
 * 之後 new Audio() 出來的都是全新未授權的元素，程式主動 play() 一樣被
 * NotAllowedError 擋掉。實測：在首次手勢時播一段無聲音訊解鎖，桌面沒問題，
 * iPad 上語音照樣被擋——因為被解鎖的是那個無聲元素，不是後面每一個新元素。
 *
 * 所以改成整個 app 只用一個元素，換 src 播下一段。它在首次手勢時被解鎖一次，
 * 之後每段語音都沿用同一份授權。
 *
 * 代價是這個元素變成共用資源：播放中的事件監聽器、以及 Web Audio 的
 * createMediaElementSource（每個元素一輩子只能建一次）都要跟著改成「一次建立、
 * 反覆使用」，見 voice-gain.ts。
 */

// 0.15 秒的真無聲 WAV（8 kHz、8-bit、單聲道；8-bit PCM 的靜音值是 128）。
//
// 長度很重要：一開始用的是只有檔頭、零個取樣的 44 位元組檔案，桌面上 play()
// 會成功（duration 是 0），但 iOS 不把「播了一個零長度的東西」算成一次真正的
// 播放，解鎖等於沒發生。
//
// 用 data URI 而不是檔案：解鎖必須發生在手勢的同一個 tick 裡，等網路回來就
// 來不及了。
export const SILENT_WAV =
  'data:audio/wav;base64,UklGRtQEAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YbAEAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIA='

let element: HTMLAudioElement | null = null

/**
 * 取得共用的音訊元素。第一次呼叫時建立。
 *
 * 不掛進 DOM——不需要顯示，而且掛進去反而會被某些瀏覽器當成內容播放器處理。
 */
export function getSharedAudio(): HTMLAudioElement {
  if (!element) {
    element = new Audio()
    // iOS 需要這個才會允許在非全螢幕狀態下播放。
    element.setAttribute('playsinline', '')
    element.preload = 'auto'
  }
  return element
}

/**
 * 趁使用者手勢在共用元素上播一次無聲音訊，換取這個元素的播放授權。
 *
 * 必須同步呼叫（在手勢的 handler 裡直接叫），不能 await 之後再播——那時手勢的
 * 有效期已經過了。
 */
export function unlockSharedAudio(): void {
  const audio = getSharedAudio()
  try {
    audio.src = SILENT_WAV
    audio.volume = 0
    const played = audio.play()
    // play() 回傳 Promise 的瀏覽器上，失敗不需要處理——重要的是「play() 曾經在
    // 手勢裡被呼叫過」這件事本身。
    if (played && typeof played.catch === 'function') played.catch(() => {})
  } catch {
    // 連設 src 都失敗的環境（測試、無 DOM）跳過。
  }
}
