// LLM 設定的 typed 包裝與表單邏輯。
//
// 刻意不含 React：這些是純資料轉換，所以能用 node:test 驗證。表單元件只負責
// 呈現與狀態，送出前的欄位組裝與驗證都在這裡。

import { apiGet, apiPost, type ApiResult } from './http.ts'

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
