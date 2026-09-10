// GPT-SoVITS 一鍵安裝的 typed 包裝與進度判讀（後端見 gpt_sovits_route.py）。
//
// 不含 React，所以能用 node:test 驗證。

import { apiGet, postNdjsonStream, type ApiResult } from './http.ts'

export interface GptSovitsStatus {
  supported: boolean
  installed: boolean
  installing: boolean
  running: boolean
  download_bytes: number
  required_free_bytes: number
  install_dir: string
}

export interface GptSovitsEvent {
  status?: string
  error?: string
  step?: string
  completed?: number
  total?: number
  percent?: number
}

// 後端會探測 9880 有沒有回應（最多 0.5 秒），給足緩衝。
export const fetchGptSovitsStatus = (baseUrl: string): Promise<ApiResult<GptSovitsStatus>> =>
  apiGet<GptSovitsStatus>(baseUrl, '/api/gpt-sovits', 5000)

export const installGptSovits = (
  baseUrl: string,
  onEvent: (event: GptSovitsEvent) => void,
) => postNdjsonStream<GptSovitsEvent>(baseUrl, '/api/gpt-sovits/install', {}, onEvent, {
  failed: '安裝失敗。',
  incomplete: '安裝未完成就中斷了，請再試一次。',
})

export type InstallStage =
  | 'preparing' | 'downloading' | 'packages' | 'models' | 'voice'
  | 'extracting' | 'starting' | 'testing'

const STAGES: readonly InstallStage[] = [
  'preparing', 'downloading', 'packages', 'models', 'voice', 'extracting', 'starting', 'testing',
]

// 後端事件轉成畫面上的一個階段與百分比。installing 用 step 分成三段；
// 認不得的事件回 null，畫面維持上一個狀態。
export function describeEvent(
  event: GptSovitsEvent,
): { stage: InstallStage; percent: number | null } | null {
  const name = event.status === 'installing' ? event.step : event.status
  const stage = STAGES.find((s) => s === name)
  if (!stage) return null
  if (stage === 'downloading' && event.total) {
    return { stage, percent: Math.floor(((event.completed ?? 0) / event.total) * 100) }
  }
  if (stage === 'extracting' && typeof event.percent === 'number') {
    return { stage, percent: event.percent }
  }
  return { stage, percent: null }
}

// 「約 X GB」，取到小數一位。
export function formatGb(bytes: number): string {
  return (Math.max(bytes, 1e8) / 1e9).toFixed(1)
}
