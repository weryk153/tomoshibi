// 畫面「有沒有變」：鏡頭大多時候拍的都是同一個畫面，沒變就不用再叫模型看圖
// （本機 9B 約 2 秒；引擎會沿用這個來源上一次的描述）。
//
// 指紋是縮成 16×12 的灰階；平均每格差不到 SAME_PICTURE_DIFF 就算同一張。鏡頭
// 雜訊大約差 2–4，換了人、移了鏡頭、開關燈都在 20 以上。

export const FINGERPRINT_SIZE = { width: 16, height: 12 }
const SAME_PICTURE_DIFF = 8

export function fingerprintFromRgba(rgba: Uint8ClampedArray): number[] {
  const out: number[] = []
  for (let i = 0; i < rgba.length; i += 4) {
    out.push(0.299 * rgba[i] + 0.587 * rgba[i + 1] + 0.114 * rgba[i + 2])
  }
  return out
}

export function isSamePicture(previous: number[] | null, next: number[]): boolean {
  if (!previous || previous.length !== next.length || next.length === 0) return false
  let total = 0
  for (let i = 0; i < next.length; i += 1) total += Math.abs(previous[i] - next[i])
  return total / next.length < SAME_PICTURE_DIFF
}
