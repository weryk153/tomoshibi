// 效能／硬體端點的 typed 包裝。
//
// 不含 React，所以能用 node:test 驗證。與 api/memory.ts 同樣的分層：純資料邏輯
// 在這裡，UI 是另一個檔案的事。

import { apiGet, apiPost, type ApiResult } from './http.ts'

// 數字對不上任何預設時，後端的 current_preset 是 'custom'。選單把它顯示成
// 「自訂」，不是空白——空白看起來像沒載入完。
export const PRESET_CUSTOM = 'custom'

export function presetSelection(current: string | undefined, presets: readonly string[]): string {
  return current && presets.includes(current) ? current : PRESET_CUSTOM
}

// GET /api/perf：語音辨識引擎與遮罩過的雲端金鑰（asr 分頁）、GPT-SoVITS 服務
// 位址（tts 分頁）、角色頁挑聲音用的清單（tts_models、gpt_sovits_langs、
// reference_voices），以及效能模式。遮罩金鑰絕不可以流進輸入框的初始值，見
// asr.tsx 檔頭。gpt_sovits_langs 是後端 GPT_SOVITS_LANGS 允許清單，語言下拉
// 選單只能選這裡面的值。
export interface PerfState {
  asr_models: string[]
  tts_models: string[]
  // gpt_sovits_tts 的 text_lang／prompt_lang 下拉選單的允許清單——見上方檔頭
  // 說明，跟後端 perf_route.py 的 GPT_SOVITS_LANGS 同一份 single source of truth。
  gpt_sovits_langs: string[]
  // GPT-SoVITS 可直接選用的參考音（後端掃 conf.yaml 那個 ref_audio_path 的
  // 所在資料夾）。prompt_text 來自同名的 .txt sidecar，沒有就是空字串。
  reference_voices?: { path: string; label: string; prompt_text: string }[]
  presets: string[]
  // 目前的背景工作數字正好是哪一個預設；都對不上是 'custom'（見 presetSelection）。
  current_preset: string
  asr_model: string
  // 一律是遮罩字串（例如 "sk-x****"）或空字串，絕不是明文——
  // perf_route.py 的 _asr_from_conf 用 _mask_key 讀出來就是這個形狀。UI 端
  // 只能拿它判斷「是否已有金鑰」並顯示 placeholder，不能把它塞回輸入框
  // 的初始值，否則使用者沒動輸入框直接按存檔，遮罩字串就會被當成真金鑰
  // 送出去——這正是 asr.tsx 要擋的陷阱，見該檔案檔頭的說明。
  groq_api_key_masked: string
  azure_api_key_masked: string
  // region 不是密鑰，後端原樣回傳明碼，可以放心塞回輸入框當初始值。
  azure_region: string
  // GPT-SoVITS 服務位址。聲音（引擎、參考音、語言）是角色自己的，不在這裡。
  gpt_sovits_api_url: string
}

export const fetchPerf = (baseUrl: string): Promise<ApiResult<PerfState>> =>
  apiGet<PerfState>(baseUrl, '/api/perf')

// POST /api/perf/asr 的回應形狀（set_asr handler 最後一行：
// {"ok": True, **_asr_from_conf(), "restart_required": True}）——不管這次送
// 的是 asr_model 還是雲端憑證，回應都是同一包「現在的完整 asr 狀態」，讀回來
// 的金鑰欄位一樣是遮罩過的。setAsrModel／setAsrCredentials 共用這個型別。
export interface AsrSaveResult {
  asr_model: string
  groq_api_key_masked: string
  azure_api_key_masked: string
  azure_region: string
  restart_required: boolean
}

// POST /api/perf/asr：只送 asr_model。引擎選擇是離散的下拉選單值，切換當下
// 就送出（跟 perf.tsx 的 keep_alive 模式切換同一種即時存檔），不需要額外的
// 存檔按鈕。
export const setAsrModel = (baseUrl: string, model: string): Promise<ApiResult<AsrSaveResult>> =>
  apiPost<AsrSaveResult>(baseUrl, '/api/perf/asr', { asr_model: model })

// POST /api/perf/asr：送雲端憑證欄位，可選帶上 asr_model。
//
// asr_model 是選填的——asr.tsx 只有在使用者切到一個需要憑證的引擎
// （groq_whisper_asr／azure_asr）時才會帶上它，把「切換引擎」跟「這次順便
// 存的憑證」包成同一次 POST 一起送。這是刻意的：如果切換引擎那一刻就單獨
// 送一次 asr_model（不等憑證），conf.yaml 會先被改成指向一個當下可能還沒有
// 任何憑證的引擎——service_context.init_asr 找不到可用憑證會初始化失敗，
// 下次重啟靜默 fallback 回 sherpa_onnx，變成「conf.yaml 寫著 groq/azure，
// 但從來沒真的用過」，跟 faster_whisper 缺相依套件時的靜默 fallback是同一種
// 問題。把 asr_model 跟憑證綁在同一次寫入，確保這個函式送出去的當下，
// 引擎要嘛沒變、要嘛一定伴隨著憑證（新打的，或呼叫端自己確認過已經存在
// conf.yaml 裡的舊憑證）。sherpa_onnx_asr／faster_whisper 不需要憑證，兩者
// 之間的切換不會走這支函式，見 setAsrModel。
//
// 呼叫端必須保證 groq_api_key／azure_api_key 這兩個欄位裡的字串都是使用者
// 親手輸入的新值，絕不是 GET /api/perf 回傳的遮罩字串（"sk-x****" 這種）
// 原樣送回——那會把遮罩字串寫死進 conf.yaml，變成真的金鑰再也讀不回來。
// asr.tsx 的作法是：金鑰欄位的 React state 從掛載到現在只被使用者的
// onChange 賦值過，從來不會被 fetchPerf() 的回應
// （groq_api_key_masked／azure_api_key_masked）指派，這樣遮罩字串在型別
// 系統的層次就不可能流進這裡的參數。
//
// 就算呼叫端不慎送出空字串，後端 set_asr 也只在收到非空值時才寫入（見
// perf_route.py「Credentials: only persisted when a fresh (non-empty) value is
// supplied, so a masked round-trip never overwrites the stored key」的註解）
// ——那是後端自己的第二道防線，這裡的型別／state 設計是前端的第一道。
export const setAsrCredentials = (
  baseUrl: string,
  creds: {
    asr_model?: string
    groq_api_key?: string
    azure_api_key?: string
    azure_region?: string
  },
): Promise<ApiResult<AsrSaveResult>> =>
  apiPost<AsrSaveResult>(baseUrl, '/api/perf/asr', creds)

// POST /api/perf/tts 的回應形狀：{"ok": True, **_tts_from_conf(), "restart_required": True}。
export interface TtsSaveResult {
  gpt_sovits_api_url: string
  restart_required: boolean
}

// POST /api/perf/tts：只設 GPT-SoVITS 服務位址。誰用 GPT-SoVITS、什麼參考音，
// 是角色自己的設定（api/characters.ts 的 updateCharacter）；後端收到那些欄位
// 會回 400。
export const setTtsServiceUrl = (
  baseUrl: string,
  apiUrl: string,
): Promise<ApiResult<TtsSaveResult>> =>
  apiPost<TtsSaveResult>(baseUrl, '/api/perf/tts', { gpt_sovits_api_url: apiUrl })

// POST /api/perf/preset：一次寫入引擎背景工作的那組數字（見 perf_route.py 的
// apply_preset／_apply_preset_bundle）。name 必須是後端 PRESETS 的其中一個
// key（light／standard／high）；由 UI 的 SelectField 保證只送得出合法選項，
// 這裡不重複驗證——跟 api/characters.ts 的 updateCharacter 一樣，交給後端的
// 400 訊息。
export const applyPreset = (baseUrl: string, name: string): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(baseUrl, '/api/perf/preset', { name })
