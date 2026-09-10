// 效能／硬體端點的 typed 包裝與 keep_alive 語意。
//
// 不含 React，所以能用 node:test 驗證。與 api/memory.ts 同樣的分層：純資料邏輯
// 在這裡，UI 是另一個檔案的事。
//
// 這個模組存在的理由：見 src/open_llm_vtuber/perf_route.py:72-74，
// `ollama_llm.keep_alive` 不是「保留幾秒」，而是「-1 = 永久常駐記憶體、
// 0 = 立即卸載、其他正數才是秒數」——兩個特殊值是旗標，不是數量。如果 UI
// 讓「自訂秒數」的輸入框吐出 0 或負數，使用者以為自己設了很短的保留時間，
// 實際上卻拿到完全相反的行為（永久常駐或立即卸載），而且沒有任何提示。
// 所以這裡把「模式」（forever / immediate / seconds）與「秒數」拆成兩個型別，
// 讓呼叫端不可能只靠一個裸數字輸入框意外產生 0 或負數。

import { apiGet, apiPost, type ApiResult } from './http.ts'

// 見 perf_route.py 的 KEEP_ALIVE_MIN／KEEP_ALIVE_MAX：後端接受的完整範圍是
// [-1, 86400]，但 -1（永久常駐）與 0（立即卸載）是旗標，不屬於「秒數」欄位。
// KEEP_ALIVE_MAX 直接斷言等於後端的 86400——見 perf.test.ts 最後一個測試，
// 改動這個常數要讓測試失敗，不能讓測試自己用這個常數建構樣本再打勾。
export const KEEP_ALIVE_MAX = 86400
// 秒數欄位的下界是 1，不是 0——0 在 keep_alive 裡代表「立即卸載」，一旦讓秒數
// 欄位夾到 0，使用者送出的「很短的保留時間」就會被誤讀成完全相反的旗標。
export const KEEP_ALIVE_SECONDS_MIN = 1

export type KeepAliveMode = 'forever' | 'immediate' | 'seconds'

// 一個「已經安全」的 keep_alive 值：不是裸 number，而是掛了型別品牌
// （branding）的 number——結構上仍是數字，可以送進 JSON.stringify／算術，
// 但 TypeScript 不會讓一個普通 number（包含常數 0 或使用者輸入）在沒有
// 顯式斷言的情況下被當成 KeepAliveValue 用。這個模組裡唯一會產生這個型別
// 的函式是 modeToKeepAlive——所以「呼叫端手造一個裸數字送給後端」這條路
// 在編譯期就被擋掉，不必依賴 setKeepAlive 內部再做一次執行期檢查。
export type KeepAliveValue = number & { readonly __keepAliveValueBrand: unique symbol }

// 把後端的裸數字解讀成使用者看得懂的模式。-1／0 是旗標，其餘正數才是秒數。
export function keepAliveToMode(value: number): KeepAliveMode {
  if (value === -1) return 'forever'
  if (value === 0) return 'immediate'
  return 'seconds'
}

// 秒數輸入框的邊界防護。Number.isFinite 同時擋掉 NaN（輸入框清空時）與
// Infinity；夾在 [1, KEEP_ALIVE_MAX]——下界用 1 而非 0 的理由見檔頭註解。
//
// 只接受 number，不做字串轉型：若呼叫端直接把 <input> 的 event.target.value
// （字串）丟進來，Number.isFinite('300') 是 false，會被悄悄夾到下界 1，
// 而不是先幫忙 parseFloat／Number() 轉換——這裡刻意不做那個隱性轉換（跟
// api/memory.ts 的 clampCap 是同一個決定），呼叫端必須自己先轉成 number。
export function clampKeepAliveSeconds(value: number): number {
  if (!Number.isFinite(value)) return KEEP_ALIVE_SECONDS_MIN
  return Math.min(KEEP_ALIVE_MAX, Math.max(KEEP_ALIVE_SECONDS_MIN, value))
}

// 模式轉回後端要的裸數字，回傳型別是 KeepAliveValue——這是把「模式＋秒數」
// 轉成「保證安全的 keep_alive 值」的唯一入口。forever／immediate 忽略呼叫端
// 傳入的秒數（就算 UI 還留著上次輸入的秒數值，切到這兩個模式也不會不小心
// 把它送出去）；seconds 分支自己呼叫 clampKeepAliveSeconds 再夾一次——不假設
// 呼叫端已經夾過。理由：如果只靠呼叫端（UI）在送出前記得夾，秒數輸入框被
// 清空成 0 卻忘記夾的那一刻，0 就會被後端讀成「立即卸載」而不是「很短的
// 保留時間」——這正是這個模組要防的事故。夾在這裡而不是在 setKeepAlive 裡，
// 是因為只有這裡知道現在是不是「秒數」分支；在 setKeepAlive 裡夾就得重新
// 判斷一次是不是 -1／0 旗標，等於把同一個條件判斷複製到第二個地方。
export function modeToKeepAlive(mode: KeepAliveMode, seconds: number): KeepAliveValue {
  if (mode === 'forever') return -1 as KeepAliveValue
  if (mode === 'immediate') return 0 as KeepAliveValue
  return clampKeepAliveSeconds(seconds) as KeepAliveValue
}

// GET /api/perf 的形狀比這裡窄——後端還回傳目前的 asr_model／tts_model、
// 遮罩過的雲端金鑰、gpt_sovits 的 api_url／ref_audio_path（perf_route.py 381-402）。
// 這裡只型別化本任務的消費端（perf 分頁的一鍵模式／keep_alive／整理頻率、
// 以及 asr／tts 分頁要用的引擎清單）實際需要的欄位；current asr_model／
// tts_model 屬於後續任務（引擎選擇 UI）的範圍，留給那裡再擴充型別，不在
// 這裡預先加沒人用的欄位。
//
// Task 3（asr 分頁的引擎選擇 UI）在這裡把 asr_model／groq_api_key_masked／
// azure_api_key_masked／azure_region 四個欄位補上——這就是上一段註解說的
// 「那裡」。Task 4（tts 分頁）接著補上 tts_model／gpt_sovits_api_url／
// gpt_sovits_ref_audio_path 三個欄位：後兩者不是憑證（是 URL 與檔案路徑），
// perf_route.py 的 _tts_from_conf 原樣回傳明碼，不像 groq/azure 金鑰要遮罩，
// 所以可以直接塞回輸入框當初始值，不需要 asr.tsx 那套「遮罩字串絕不可以
// 流進 state」的防線。
//
// 後續任務再補上 gpt_sovits_prompt_text／gpt_sovits_text_lang／
// gpt_sovits_prompt_lang 三個欄位——這是 gpt_sovits_tts 九個設定裡真正卡住
// 「能不能從 App 裡把音色克隆設定完」的關鍵缺口：prompt_text 是參考音檔的
// 逐字稿，GPT-SoVITS 拿它去對齊「這段音檔說的是這些字」，沒填克隆效果差或
// 直接失敗；text_lang／prompt_lang 分別是角色回覆的語言、參考音檔本身的語言。
// 同樣不是密鑰，perf_route.py 原樣回傳明碼，可以直接塞回輸入框。
// gpt_sovits_langs 是後端 GPT_SOVITS_LANGS 允許清單（見 perf_route.py），
// UI 的語言下拉選單只能選這裡面的值，不接受自由輸入。
export interface PerfState {
  keep_alive: number
  keep_alive_min: number
  keep_alive_max: number
  consolidation_interval: number
  consolidation_interval_choices: number[]
  asr_models: string[]
  tts_models: string[]
  // gpt_sovits_tts 的 text_lang／prompt_lang 下拉選單的允許清單——見上方檔頭
  // 說明，跟後端 perf_route.py 的 GPT_SOVITS_LANGS 同一份 single source of truth。
  gpt_sovits_langs: string[]
  // GPT-SoVITS 可直接選用的參考音（後端掃 conf.yaml 那個 ref_audio_path 的
  // 所在資料夾）。prompt_text 來自同名的 .txt sidecar，沒有就是空字串。
  reference_voices?: { path: string; label: string; prompt_text: string }[]
  presets: string[]
  // 角色檔自己釘住的引擎，key 是 conf_name。角色的 asr_config／tts_config 會
  // 蓋掉 conf.yaml（service_context 的 init_tts／init_asr 拿的是角色那份），
  // 所以在這裡選的引擎可能一換角色就被換回去、畫面上卻沒有任何說明。有這份
  // 對照表，UI 才能在使用者浪費時間之前先講出「這個分頁對目前角色沒有作用」。
  engine_overrides_by_character: Record<string, {
    tts_model?: string
    asr_model?: string
  }>
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
  tts_model: string
  // 見上面的檔頭說明：URL 與檔案路徑，不是密鑰，明碼往返安全。
  gpt_sovits_api_url: string
  gpt_sovits_ref_audio_path: string
  // 參考音檔的逐字稿。跟 api_url／ref_audio_path 同樣是明碼往返、非密鑰，但
  // 語意上允許是空字串（使用者故意留空，只是克隆效果會變差）——tts.tsx 因此
  // 不把它放進「兩個必填欄位」那組存檔閘門，見 gptSovitsFieldsRequired 旁的
  // 說明只講 api_url／ref_audio_path 兩個。
  gpt_sovits_prompt_text: string
  // 角色回覆的語言／參考音檔本身的語言，值必須落在 gpt_sovits_langs 允許清單內。
  gpt_sovits_text_lang: string
  gpt_sovits_prompt_lang: string
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

// POST /api/perf/tts 的回應形狀（set_tts handler 最後一行：
// {"ok": True, **_tts_from_conf(), "restart_required": True}）——不管這次送
// 的是 tts_model 還是 gpt_sovits 欄位，回應都是同一包「現在的完整 tts 狀態」。
// setTtsModel／setTtsConfig 共用這個型別，跟 AsrSaveResult／setAsrModel／
// setAsrCredentials 是同一種分法。
export interface TtsSaveResult {
  tts_model: string
  gpt_sovits_api_url: string
  gpt_sovits_ref_audio_path: string
  gpt_sovits_prompt_text: string
  gpt_sovits_text_lang: string
  gpt_sovits_prompt_lang: string
  restart_required: boolean
}

// POST /api/perf/tts：只送 tts_model。edge_tts 不需要任何額外欄位就能動作，
// 切換到它當下就送出（跟 asr.tsx 的 sherpa_onnx／faster_whisper 同一種
// 即時存檔模式），不需要额外的存檔按鈕。
export const setTtsModel = (baseUrl: string, model: string): Promise<ApiResult<TtsSaveResult>> =>
  apiPost<TtsSaveResult>(baseUrl, '/api/perf/tts', { tts_model: model })

// POST /api/perf/tts：送 gpt_sovits 的 api_url／ref_audio_path，可選帶上
// tts_model。tts_model 是選填的——tts.tsx 只有在使用者切到 gpt_sovits_tts
// 時才會帶上它，把「切換引擎」跟「這次順便存的欄位」包成同一次 POST 一起送，
// 理由跟 setAsrCredentials 完全一樣：如果切換引擎那一刻就單獨送一次
// tts_model（不等這兩個欄位），conf.yaml 會先被改成指向一個當下可能還沒有
// 可用設定的引擎——service_context.py:411-414 找不到可達的 GPT-SoVITS 服務
// 會靜默 fallback 回 edge_tts，變成「conf.yaml 寫著 gpt_sovits_tts，但其實在
// 用 edge_tts、畫面卻還顯示 gpt_sovits_tts」，跟 asr.tsx 要擋的雲端引擎陷阱
// 是同一種問題。edge_tts 不需要這兩個欄位，不會走這支函式，見 setTtsModel。
export const setTtsConfig = (
  baseUrl: string,
  config: {
    tts_model?: string
    gpt_sovits_api_url?: string
    gpt_sovits_ref_audio_path?: string
    gpt_sovits_prompt_text?: string
    gpt_sovits_text_lang?: string
    gpt_sovits_prompt_lang?: string
  },
): Promise<ApiResult<TtsSaveResult>> =>
  apiPost<TtsSaveResult>(baseUrl, '/api/perf/tts', config)

// 這個函式本身不做任何夾範圍——它只是把值轉送給後端。安全性不是在這裡
// 用執行期檢查頂住的，是型別：參數是 KeepAliveValue 而不是裸 number，而
// modeToKeepAlive 是這個模組裡唯一產生 KeepAliveValue 的函式（-1／0 兩個
// 旗標直接回傳，'seconds' 分支已經呼叫過 clampKeepAliveSeconds）。所以呼叫
// 這個函式的唯一合法路徑是先呼叫 modeToKeepAlive，TypeScript 會拒絕任何
// 手造的裸數字（包含 0 或負數）在沒有型別斷言的情況下混進來。
// 這裡刻意不在執行期重新判斷「現在是不是秒數」再夾一次——那個判斷只有
// modeToKeepAlive 知道（它才知道呼叫端選的是哪個 mode），在這裡重做一次
// 等於把同一個條件複製到第二個地方，兩處分開演化就會其中一處忘記更新。
export const setKeepAlive = (
  baseUrl: string,
  value: KeepAliveValue,
): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(baseUrl, '/api/perf/keep-alive', { keep_alive: value })

// POST /api/perf/preset：一次原子寫入六個設定葉（見 perf_route.py 的
// apply_preset／_apply_preset_bundle）。name 必須是後端 PRESETS 的其中一個
// key（light／standard／high）；由 UI 的 SelectField 保證只送得出合法選項，
// 這裡不重複驗證——跟 api/characters.ts 的 updateCharacter 一樣，交給後端的
// 400 訊息。
export const applyPreset = (baseUrl: string, name: string): Promise<ApiResult<unknown>> =>
  apiPost<unknown>(baseUrl, '/api/perf/preset', { name })

// 刻意不包裝 POST /api/perf/consolidation。它與 POST /api/memory/consolidation
// 寫的是同一個設定葉（character_config.memory_consolidation_interval）——
// perf_route.py 的 _write_consolidation_interval 與 memory_route.py 的寫入
// 呼叫同一支 _rewrite_int_leaf，作用在同一個 conf.yaml 位置；memory_route 的
// handler 註解自己說是這個值的權威寫法，且 api/memory.ts 已經有
// setMemoryConsolidation／isValidConsolidation 兩個包裝、驗證邏輯齊全，只是
// 還沒有 UI 呼叫它們。整理頻率這裡不重複一份，perf 分頁直接呼叫
// api/memory.ts 的既有函式。
