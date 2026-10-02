// 截圖送給她看之前的壓縮設定。存在 localStorage，系統分頁寫、截圖時讀。
export const IMAGE_COMPRESSION_QUALITY_KEY = 'appImageCompressionQuality'
export const DEFAULT_IMAGE_COMPRESSION_QUALITY = 0.8
export const IMAGE_MAX_WIDTH_KEY = 'appImageMaxWidth'
export const DEFAULT_IMAGE_MAX_WIDTH = 0

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
