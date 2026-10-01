// MCP 開關的 typed wrapper。後端見 src/open_llm_vtuber/translator_route.py 的
// GET/POST /api/agent-config/use-mcpp。設定葉是
// character_config.agent_config.agent_settings.basic_memory_agent.use_mcpp
// （use_mcpp = MCP Plus，即工具／網路搜尋），缺省為 false。
//
// 跟其他 api/*.ts（characters.ts／memory.ts／perf.ts／topics.ts）同一套慣例：
// 一律回傳 ApiResult<T>，不 throw。GET 成功時後端回 {use_mcpp: boolean}（沒有
// ok 欄位，見 http.ts 的 normalizeError 註解——GET 端點的錯誤形狀跟 POST 不同，
// 但成功形狀本來就沒有 ok），這裡收斂成呼叫端只需要的 boolean。POST 成功時回
// {ok: true, use_mcpp: boolean, restart_required: true}——conf.yaml 只在啟動時
// 讀取一次，所以 restart_required 必須留在公開回傳型別裡讓 UI 講明「存檔後要
// 重啟才生效」，跟 api/perf.ts 的 AsrSaveResult／TtsSaveResult 是同一個理由、
// 同一種形狀（見該檔案 115-121、171-176 行）。

import { apiGet, apiPost, type ApiResult } from './http.ts'

interface UseMcppGetResponse {
  use_mcpp: boolean
}

interface UseMcppSaveResponse {
  ok: true
  use_mcpp: boolean
  restart_required: boolean
}

// POST /api/agent-config/use-mcpp 的回應形狀，跟 api/perf.ts 的
// AsrSaveResult／TtsSaveResult 同一種分法：不重複 ok（ApiResult 已經有了），
// 但保留 restart_required 讓呼叫端知道要提示使用者重啟。
export interface UseMcppSaveResult {
  use_mcpp: boolean
  restart_required: boolean
}

export async function fetchUseMcpp(baseUrl: string): Promise<ApiResult<boolean>> {
  const res = await apiGet<UseMcppGetResponse>(baseUrl, '/api/agent-config/use-mcpp')
  if (!res.ok) return res
  return { ok: true, data: res.data.use_mcpp }
}

export async function setUseMcpp(
  baseUrl: string,
  enabled: boolean,
): Promise<ApiResult<UseMcppSaveResult>> {
  const res = await apiPost<UseMcppSaveResponse>(baseUrl, '/api/agent-config/use-mcpp', {
    use_mcpp: enabled,
  })
  if (!res.ok) return res
  return {
    ok: true,
    data: { use_mcpp: res.data.use_mcpp, restart_required: res.data.restart_required },
  }
}

// 「由 AI Character Engine 驅動對話」：後端見 src/open_llm_vtuber/engine_config_route.py
// 的 GET/POST /api/agent-config/character-engine。跟 use_mcpp 同一種存法（直接寫
// conf.yaml、要重啟），多了 available／reason：引擎裝不起來時開關是灰的，旁邊
// 說明為什麼。

export type EngineEvery =
  | 'emotion_every' | 'memory_every' | 'self_memory_every' | 'goal_every' | 'reflection_every'
  | 'goals_shown' | 'thoughts_shown'

export interface EngineSettings {
  enabled: boolean
  available: boolean
  reason: string
  emotion_every: number
  memory_every: number
  self_memory_every: number
  goal_every: number
  reflection_every: number
  goals_shown: number
  thoughts_shown: number
}

export type EngineSettingsChange = Partial<Pick<EngineSettings, 'enabled' | EngineEvery>>

interface EngineSaveResponse extends Omit<EngineSettings, 'available' | 'reason'> {
  ok: true
  restart_required: boolean
}

export async function fetchEngineSettings(baseUrl: string): Promise<ApiResult<EngineSettings>> {
  return apiGet<EngineSettings>(baseUrl, '/api/agent-config/character-engine')
}

export async function saveEngineSettings(
  baseUrl: string,
  changes: EngineSettingsChange,
): Promise<ApiResult<Omit<EngineSaveResponse, 'ok'>>> {
  const res = await apiPost<EngineSaveResponse>(baseUrl, '/api/agent-config/character-engine', changes)
  if (!res.ok) return res
  const { ok: _ok, ...rest } = res.data
  return { ok: true, data: rest }
}
