// 角色端點的 typed 包裝與合併邏輯。
//
// 不含 React，所以能用 node:test 驗證。PUT /api/characters/{filename} 是整欄位
// 取代而非部分更新，所以送出前必須把使用者的編輯疊在現值上——漏掉任何欄位
// 就等於把它清空。

import { apiGet, apiPost, apiPut, buildUrl, normalizeError, type ApiResult } from './http.ts'

export interface CharacterRecord {
  filename: string
  slug: string
  is_base: boolean
  conf_name: string | null
  character_name: string | null
  avatar: string | null
  conf_uid: string | null
  persona_prompt: string | null
  live2d_model_name: string | null
  voice: string | null
  // 兩種語言，不要混淆：reply_language 是她「用什麼語言寫回覆」，
  // voice_lang 是「用什麼語言發聲」（tts_config.gpt_sovits_tts.text_lang）。
  // 兩者不同時後端會在合成前翻譯一次，那是延遲的主要來源之一。
  // 空字串＝沒設，沿用 conf.yaml 的全域值。
  reply_language: string
  voice_lang: string
  // 這個角色釘住的 TTS 引擎（tts_config.tts_model）。空字串＝沒釘，沿用
  // conf.yaml 的 tts_model。以前後端根本不回這個欄位，而寫入端又無條件把它
  // 塞成 edge_tts，所以角色面板存一次檔就會把訓練好的音色換掉。
  tts_model: string
  // 「用誰的聲音」。GPT-SoVITS 是 zero-shot 克隆，聲線由 ref_audio_path 這段
  // 參考音決定；prompt_text 是那段音檔的逐字稿，prompt_lang 是它的語言——三者
  // 是一組，逐字稿給錯音色就會歪。空字串＝沒設，沿用 conf.yaml 的全域參考音。
  ref_audio_path: string
  prompt_text: string
  prompt_lang: string
}

export interface CharacterEdits {
  conf_name: string
  persona_prompt: string
  live2d_model_name: string
  voice: string
}

// POST /api/characters（建立新角色）。四個必填欄位與 CharacterEdits 相同；
// slug/character_name/avatar 都是選填——後端會在缺 slug 時從 conf_name 衍生、
// 缺 character_name 時退回 conf_name。
export interface CharacterCreate {
  conf_name: string
  persona_prompt: string
  live2d_model_name: string
  voice: string
  slug?: string
  character_name?: string
  avatar?: string
  reply_language?: string
  voice_lang?: string
  tts_model?: string
  ref_audio_path?: string
  prompt_text?: string
  prompt_lang?: string
}

// 只用在 buildCharacterUpdate 的第三參數。這兩個欄位在後端是「省略就保留現值」
// （見 character_route.py 的 update_character：fields["avatar"] if ... is not None
// else existing_cc.get("avatar")），所以語意跟四個必填欄位不同：必填欄位永遠送出
// 完整字串，這兩個要嘛完全不送（未編輯），要嘛送出使用者給的值（含空字串＝清除）。
export type OptionalCharacterFields = {
  character_name?: string
  avatar?: string
  reply_language?: string
  voice_lang?: string
  tts_model?: string
  ref_audio_path?: string
  prompt_text?: string
  prompt_lang?: string
}

// 這幾個鍵共用「省略＝保留現值、空字串＝清除」的語意。列成陣列而不是寫四段
// 相同的 if，是因為漏掉一個不會有任何錯誤訊息——那個欄位只是永遠存不進去。
const OPTIONAL_KEYS = [
  'character_name',
  'avatar',
  'reply_language',
  'voice_lang',
  'tts_model',
  'ref_audio_path',
  'prompt_text',
  'prompt_lang',
] as const satisfies readonly (keyof OptionalCharacterFields)[]

const str = (v: string | null | undefined): string => (v == null ? '' : v)

// 用「鍵是否存在」而非「值是否 falsy」判斷有沒有編輯過。
// 若寫成 edits.voice || current.voice，使用者把語音清空就會被現值蓋回去，
// 欄位永遠清不掉。
const pick = (
  edits: Partial<CharacterEdits>,
  key: keyof CharacterEdits,
  fallback: string | null,
): string => (key in edits ? str(edits[key]) : str(fallback))

export function buildCharacterUpdate(
  current: CharacterRecord,
  edits: Partial<CharacterEdits>,
  optional?: OptionalCharacterFields,
): CharacterEdits & OptionalCharacterFields {
  const body: CharacterEdits & OptionalCharacterFields = {
    conf_name: pick(edits, 'conf_name', current.conf_name),
    persona_prompt: pick(edits, 'persona_prompt', current.persona_prompt),
    live2d_model_name: pick(edits, 'live2d_model_name', current.live2d_model_name),
    voice: pick(edits, 'voice', current.voice),
  }
  // 選填欄位只在「該鍵存在且值不是 undefined」時才放進酬載。
  // 用 in 而非解構＋預設值，是因為要保留「完全沒傳這個鍵」與「傳了 undefined」
  // 兩種都當成未編輯，同時讓「傳了空字串」正常送出（那是使用者要清空）。
  for (const key of OPTIONAL_KEYS) {
    if (optional && key in optional && optional[key] !== undefined) {
      body[key] = optional[key]
    }
  }
  return body
}

export const fetchCharacters = (
  baseUrl: string,
): Promise<ApiResult<{ characters: CharacterRecord[] }>> =>
  apiGet<{ characters: CharacterRecord[] }>(baseUrl, '/api/characters')

export const fetchLive2dSkins = (baseUrl: string): Promise<ApiResult<unknown>> =>
  apiGet<unknown>(baseUrl, '/api/live2d-skins')

// full=1 會讓後端做一次即時的 edge_tts.list_voices()，後端逾時 6 秒，
// 前端給 9 秒緩衝。不帶 full 時回的是精選的 9 個語音，很快。
export const fetchVoices = (baseUrl: string, full = false): Promise<ApiResult<unknown>> =>
  apiGet<unknown>(baseUrl, `/api/voices${full ? '?full=1' : ''}`, full ? 9000 : 15000)

// 後端這個端點是 PUT（整欄位取代），不是部分更新的 PATCH/POST。
// 見 src/open_llm_vtuber/character_route.py：
//   @router.put("/api/characters/{filename}")
// 沒有對應的 POST 別名——POST /api/characters 是「新建角色」，路徑與必填欄位都不同
// （create 要求 conf_name/persona/skin 全部存在才能建立新檔案，update 則是替換既有檔案）。
// 所以在 http.ts 加了 apiPut，而不是借用 apiPost 打這個端點。
export const updateCharacter = (
  baseUrl: string,
  filename: string,
  body: CharacterEdits,
): Promise<ApiResult<unknown>> =>
  apiPut<unknown>(baseUrl, `/api/characters/${encodeURIComponent(filename)}`, body)

// POST /api/characters：建立新角色檔案。跟 updateCharacter 共用 apiPost 這條 JSON
// 路徑（body 是純 JSON，不含檔案），所以直接透過 http.ts 打。
export const createCharacter = (
  baseUrl: string,
  body: CharacterCreate,
): Promise<ApiResult<unknown>> => apiPost<unknown>(baseUrl, '/api/characters', body)

// 前端頭像大小上限。刻意比後端的 AVATAR_MAX_BYTES（character_route.py，4 MB）更
// 嚴格——頭像顯示很小，512KB 已經綽綽有餘。這是刻意的兩層限制，不是 bug，
// 不要「修」成跟後端一致。
export const AVATAR_MAX_CLIENT_BYTES = 512 * 1024

// 跟後端 AVATAR_ALLOWED_EXTS（character_route.py）保持一致，讓前端能在送出前
// 就擋掉一定會被後端拒絕的副檔名。
export const AVATAR_ALLOWED_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']

const extOf = (name: string): string => {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

// 回傳 i18n 鍵字串或 null（合法）。先驗類型再驗大小——類型錯比大小錯更根本，
// 沒必要對一個型別就不對的檔案再報「太大」。
export function validateAvatarFile(file: File): string | null {
  if (!AVATAR_ALLOWED_EXTS.includes(extOf(file.name))) {
    return 'settings.characters.aiAvatarNotImage'
  }
  if (file.size > AVATAR_MAX_CLIENT_BYTES) {
    return 'settings.characters.aiAvatarTooLarge'
  }
  return null
}

// POST /api/character/avatar，multipart/form-data。http.ts 的 request() 只走
// JSON 路徑（固定 Content-Type: application/json、JSON.stringify(body)），刻意
// 不擴充成支援 multipart——那會在每個呼叫都會經過的 JSON 路徑裡插入一個只有這裡
// 用得到的分支。改用原生 fetch + FormData，並沿用 http.ts 匯出的 buildUrl／
// normalizeError，讓錯誤形狀跟其他呼叫一致。
export async function uploadAvatar(
  baseUrl: string,
  file: File,
  confUid?: string,
): Promise<ApiResult<{ filename: string }>> {
  const form = new FormData()
  form.append('file', file)
  if (confUid) form.append('conf_uid', confUid)
  try {
    const res = await fetch(buildUrl(baseUrl, '/api/character/avatar'), {
      method: 'POST',
      body: form,
    })
    let parsed: unknown = null
    try {
      parsed = await res.json()
    } catch {
      // 非 JSON 回應（例如代理伺服器的 HTML 錯誤頁）
      if (!res.ok) return { ok: false, error: `請求失敗（HTTP ${res.status}）` }
    }
    if (!res.ok) return { ok: false, error: normalizeError(parsed, res.status) }
    return { ok: true, data: parsed as { filename: string } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : '網路錯誤' }
  }
}
