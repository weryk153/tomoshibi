// 截圖送給她看之前的壓縮設定。存在 localStorage，系統分頁寫、截圖時讀。
export const IMAGE_COMPRESSION_QUALITY_KEY = 'appImageCompressionQuality'
export const DEFAULT_IMAGE_COMPRESSION_QUALITY = 0.8
export const IMAGE_MAX_WIDTH_KEY = 'appImageMaxWidth'
// 0 是不縮小。本機 9B 讀一張 1280 寬的圖約 7–9 秒，原尺寸的 Retina 截圖要 30 秒上下。
export const DEFAULT_IMAGE_MAX_WIDTH = 1280

export const loadImageQuality = (stored: string | null): number => {
  if (stored) {
    const quality = parseFloat(stored)
    if (!Number.isNaN(quality) && quality >= 0.1 && quality <= 1.0) return quality
  }
  return DEFAULT_IMAGE_COMPRESSION_QUALITY
}

export const loadImageMaxWidth = (stored: string | null): number => {
  if (stored) {
    const maxWidth = parseInt(stored, 10)
    if (!Number.isNaN(maxWidth) && maxWidth >= 0) return maxWidth
  }
  return DEFAULT_IMAGE_MAX_WIDTH
}
