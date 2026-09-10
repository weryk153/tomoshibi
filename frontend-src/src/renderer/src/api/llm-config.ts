// LLM 設定的 typed 包裝與表單邏輯。
//
// 刻意不含 React：這些是純資料轉換，所以能用 node:test 驗證。表單元件只負責
// 呈現與狀態，送出前的欄位組裝與驗證都在這裡。

import { apiGet, apiPost, postNdjsonStream, type ApiResult } from './http.ts'

export type LlmMode = 'apikey' | 'ollama' | 'custom'
export type ApiKeyProvider = 'openai' | 'claude' | 'gemini'

export interface LlmConfigRead {
  provider: string
  // llm_provider 實際選中的 provider。這支路由永遠讀寫 openai_compatible_llm，
  // 所以當 llm_provider 指向別的（lmstudio_llm、ollama_llm、claude_llm…）時，
  // 這個分頁顯示的 base_url／model 根本沒有人在用，改了也不會影響對話——跟角色
  // 自己釘住 TTS 引擎是同一個陷阱。有這個欄位，UI 才說得出來。
  active_provider?: string
  base_url: string
  model: string
  api_key_masked: string
  has_real_key: boolean
  is_configured: boolean
}

export interface LlmSaveResult {
  ok: true
  model: string
  base_url: string
  api_key_masked: string
  restart_required: boolean
}

export interface LlmFormState {
  mode: LlmMode
  provider: ApiKeyProvider
  apiKey: string
  model: string
  baseUrl: string
}

// 後端只接受 openai / claude / gemini / ollama 四個 provider 值
// （llm_config_route.py 的 PROVIDER_DEFAULT_BASE_URL）。「自訂端點」不是其中之一，
// 必須映射到 openai——後端只用 provider 決定 base_url 的預設值，而 custom 模式
// 一定會自帶 base_url，所以映射到哪個都不影響結果，選 openai 是因為它的語意
// 就是「OpenAI 相容」。
export function buildSavePayload(
  state: LlmFormState,
): { provider: string; api_key: string; model: string; base_url?: string } {
  const model = state.model.trim()
  const apiKey = state.apiKey.trim()

  if (state.mode === 'ollama') {
    return { provider: 'ollama', api_key: apiKey, model }
  }
  if (state.mode === 'custom') {
    return { provider: 'openai', api_key: apiKey, model, base_url: state.baseUrl.trim() }
  }
  // apikey 模式刻意不送 base_url，讓後端填該供應商的預設值——
  // 前端自己維護一份供應商→URL 對照表只會跟後端漂移。
  return { provider: state.provider, api_key: apiKey, model }
}

// 刻意沒有前端驗證函式。後端的必填欄位檢查跑在 ping 實測之前，所以缺欄位會
// 立刻回 400 並附人類可讀的訊息，不會讓使用者等 12-90 秒。前端再驗一次只是
// 多一份會跟後端漂移的規則。而且 setup 命名空間裡沒有逐欄位的錯誤字串
// ——更早的精靈本來也沒有前端驗證，只有一個通用的 setup.testFailed。

export const fetchLlmConfig = (baseUrl: string): Promise<ApiResult<LlmConfigRead>> =>
  apiGet<LlmConfigRead>(baseUrl, '/api/llm-config')

// 逾時 100 秒：後端存檔前會做一次真實的 ping 呼叫，本地模型的冷啟動預算是
// 90 秒（llm_config_route.py），所以前端必須比它寬鬆，否則會在後端還在等的時候
// 就顯示逾時。
export const saveLlmConfig = (
  baseUrl: string,
  state: LlmFormState,
): Promise<ApiResult<LlmSaveResult>> =>
  apiPost<LlmSaveResult>(baseUrl, '/api/llm-config', buildSavePayload(state), 100000)

// 後端對 localhost:11434 的逾時是 4 秒，前端給 6 秒緩衝。
export const fetchOllamaModels = (baseUrl: string): Promise<ApiResult<unknown>> =>
  apiGet<unknown>(baseUrl, '/api/llm-config/ollama-models', 6000)

// --- 偵測本機模型（LM Studio／Ollama） --------------------------------------- //
//
// 這兩個端點是 Task 8 後端的產物，這裡只是薄薄的 typed 包裝，形狀比照上面
// fetchOllamaModels／saveLlmConfig 的既有慣例：apiGet／apiPost 回傳
// ApiResult<T>，逾時另外算，不做重試。

export interface DetectedModel {
  id: string
  backend: 'lmstudio' | 'ollama'
  base_url: string
  arch: string | null
  is_vlm: boolean
  supports_tools: boolean
  max_context: number | null
  quantization: string | null
}

export interface DetectResponse {
  models: DetectedModel[]
  lmstudio_available: boolean
  ollama_available: boolean
  /** 連不上時用來分「沒裝」和「裝了沒開」。舊版後端沒有這欄，當作沒裝。 */
  ollama_installed?: boolean
  /** 這個平台能不能一鍵安裝 Ollama（macOS、Windows x64）。舊版後端沒有這欄。 */
  ollama_install_supported?: boolean
  recommended_pull: string
}

// 後端兩個探測各自 3 秒逾時、平行跑（asyncio.gather），最壞情況約 3 秒——
// 8 秒給足緩衝，不用比照本機推論那種要等模型冷啟動的逾時。
export const detectModels = (baseUrl: string): Promise<ApiResult<DetectResponse>> =>
  apiGet<DetectResponse>(baseUrl, '/api/llm-config/detect', 8000)

export interface ApplyDetectedResult {
  ok: boolean
  applied?: {
    provider: string
    model: string
    is_vlm: boolean
    supports_tools: boolean
    max_context: number | null
  }
  note?: string | null
  error?: string
}

// 逾時比照 saveLlmConfig：套用前會做一次真實 ping，本機模型冷啟動預算 90 秒
// （llm_config_route.py 的 LOCAL_TEST_CALL_TIMEOUT），前端要比它寬鬆。
export const applyDetectedModel = (
  baseUrl: string,
  backend: string,
  model: string,
): Promise<ApiResult<ApplyDetectedResult>> =>
  apiPost<ApplyDetectedResult>(
    baseUrl,
    '/api/llm-config/apply-detected',
    { backend, model },
    100000,
  )

// --- Ollama 一鍵下載推薦模型 -------------------------------------------------- //
//
// POST /api/llm-config/ollama-pull 把 Ollama 的下載進度逐行轉成 NDJSON 串流
// 給前端（見 llm_config_route.py 的 stream()），解析在 http.ts 的 postNdjsonStream。

export interface OllamaPullEvent {
  status?: string
  error?: string
  completed?: number
  total?: number
}

export const pullOllamaModel = (
  baseUrl: string,
  model: string,
  onEvent: (event: OllamaPullEvent) => void,
) => postNdjsonStream(baseUrl, '/api/llm-config/ollama-pull', { model }, onEvent, {
  failed: '下載失敗。',
  incomplete: '下載未完成就中斷了，請再試一次。',
})

// 一鍵安裝 Ollama 本體（下載官方安裝檔→驗校驗碼→安裝→啟動）。事件的 status 依序是
// resolving、downloading、verifying、installing、starting、success。
export const installOllama = (
  baseUrl: string,
  onEvent: (event: OllamaPullEvent) => void,
) => postNdjsonStream(baseUrl, '/api/llm-config/ollama-install', {}, onEvent, {
  failed: '安裝失敗。',
  incomplete: '安裝未完成就中斷了，請再試一次。',
})
