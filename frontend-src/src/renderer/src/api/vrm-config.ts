// VRM 模型設定的 typed wrapper。跟同目錄的 live2d-config.ts 打同一個端點
// （GET /api/live2d/model-config/{name}），後端依 model_dict 項目的 type 回不同
// 形狀；這裡只描述 VRM 那一種。欄位保留後端的 snake_case，理由同 live2d-config.ts。
import { apiGet, type ApiResult } from './http.ts'

export interface VrmClipEntry {
  clip: string
  file: string
  mappings: { keyword: string; label: string | null }[]
}

export interface VrmExpressionEntry {
  name: string
  keywords: string[]
}

export interface VrmModelConfig {
  name: string
  type: 'vrm'
  clips: VrmClipEntry[]
  expressions: VrmExpressionEntry[]
  has_idle: boolean
  orphan_keywords: { keyword: string; clip: string | null }[]
}

export const fetchVrmModelConfig = (
  baseUrl: string,
  name: string,
): Promise<ApiResult<VrmModelConfig>> =>
  apiGet<VrmModelConfig>(baseUrl, `/api/live2d/model-config/${encodeURIComponent(name)}`)
