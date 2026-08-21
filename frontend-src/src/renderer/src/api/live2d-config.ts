// 動作／點擊區域設定的 typed wrapper。後端見
// src/open_llm_vtuber/live2d_config_route.py 的
// GET/PUT /api/live2d/model-config/{name}。
//
// 型別欄位刻意保留後端 JSON 的原始命名（snake_case：hit_areas／tap_motions／
// orphan_keywords），不轉成 camelCase——跟 api/perf.ts 的 PerfState、
// api/network.ts 的 NetworkInfo 同一個決定：這個模組的回應是直接把 Python
// dict 序列化出來的，欄位名就是後端程式碼裡的鍵，轉成 camelCase 只會製造
// 「這裡的欄位到底對應後端哪一個」的翻譯負擔，且沒有任何 UI 慣例要求
// camelCase（Vue／React 兩邊都吃 snake_case 沒問題）。PUT 請求體則沿用
// model_dict.json 原本就是 camelCase 的 motionMap／tapMotions 兩個鍵
// （live2d_config_route.py 的 put_model_config 用 body.get("motionMap")／
// body.get("tapMotions") 原樣讀取）——後端這兩邊本來就命名不一致
// （回應是 snake_case，請求體鍵沿用 model_dict.json 既有的 camelCase），這裡
// 照樣鏡射，不強行統一成看起來一致但跟後端對不上的假象。
//
// 跟其他 api/*.ts（perf.ts／topics.ts／player.ts／agent-config.ts）同一套
// 慣例：一律回傳 ApiResult<T>，不 throw；GET 直接把後端回應原樣當作 T
// （這個端點的回應沒有 ok 欄位，跟 agent-config.ts 的 fetchUseMcpp 面對的
// GET 端點同一種形狀）；PUT 的原始回應含 ok:true，公開型別收斂掉 ok、只留
// restart_required，跟 PlayerLanguageSaveResult／TtsSaveResult／
// UseMcppSaveResult 同一種分法。

import { apiGet, apiPut, type ApiResult } from './http.ts'

// 一個 keyword 觸發某個 (group, index) 動作時，掛在這個 keyword 上的顯示用
// label。見 live2d_config_route.py build_model_config 的註解：label 是掛在
// keyword 上，不是掛在動作上——两個不同的 keyword 可以合法指向同一個
// (group, index)，各自帶不同的 label。用單一的 keyword/label 欄位會在這種
// 情況下悄悄丟掉其中一個 keyword，所以這裡跟後端一樣，每個動作底下是一個
// mappings 陣列，不是單一 keyword/label。
export interface MotionMapping {
  keyword: string
  label: string | null
}

// FileReferences.Motions 底下一個 (group, index) 位置的真實動作，合併了目前
// 指向它的所有 keyword（mappings，可能是空陣列）。group 可以合法是空字串
// （mao_pro 把六個可用動作全放在無名群組），不代表沒有群組，UI 不可把它當
// 「缺群組」過濾掉。
export interface MotionEntry {
  group: string
  index: number
  file: string
  // 自動 idle／talk 流程已經在用的群組（Idle、模型自己的
  // idleMotionGroupName、或 Talk）——UI 該標示出來，但這個動作仍然要列出，
  // 是否要因此排除是 UI 的決定，不是這個型別的責任。
  reserved: boolean
  mappings: MotionMapping[]
}

// model3.json 根層級 HitAreas[] 的一筆。
export interface HitArea {
  id: string
  name: string
}

// tapMotions 正規化後（_normalize_tap_motions）的單一項目。index 為 null
// 代表「群組內隨機挑一個」（legacy 的 {groupName: weight} 形狀轉換過來的，
// 從未記錄過具體 index）。
export interface TapMotionEntry {
  group: string
  index: number | null
  weight: number
}

// motionMap 裡指向的 (group, index) 已經不存在於目前的 model3.json
// （手動改過 model_dict.json，或模型檔案被替換過）。這些必須被顯示出來，
// 不能悄悄丟掉——UI 需要靠它們告訴使用者「這筆設定已經失效」。index 沿用
// _target_key 的行為：正常情況下是 number，若原始值不可雜湊（例如手改成
// list／dict），後端會把它轉成 repr 字串，所以這裡容許 string。
export interface OrphanKeyword {
  keyword: string
  group: string
  index: number | string | null
}

// FileReferences.Expressions 裡的一個表情，合併了目前 emotionMap 指向它的所有
// 情緒關鍵字（keywords，可能是空陣列＝這個表情還沒命名）。
//
// 定位方式跟動作不同：動作是 (group, index)，表情只有一個陣列索引。這個索引
// 很脆弱——model3.json 增刪表情之後，後面的索引整批位移，emotionMap 還指著
// 舊索引就會叫出完全不相干的臉，而且沒有任何錯誤訊息（實際發生過：刪掉兩個
// 失效表情之後 smirk 從「賊笑」變成「拿掉魔杖」）。所以 UI 一定要把索引跟
// 表情名字一起顯示，讓人看得出來對不對。
//
// keywords 跟動作的 mappings 一樣是陣列而不是單一值：兩個關鍵字指向同一個
// 表情是合法的（一張臉可以同時是 joy 和 smug）。
export interface ExpressionEntry {
  name: string
  index: number
  keywords: string[]
}

// GET /api/live2d/model-config/{name} 的完整回應形狀，逐欄位對照
// live2d_config_route.py 的 build_model_config。
export interface ModelConfig {
  name: string
  motions: MotionEntry[]
  hit_areas: HitArea[]
  tap_motions: Record<string, TapMotionEntry[]>
  expressions: ExpressionEntry[]
  orphan_keywords: OrphanKeyword[]
}

// PUT 請求體裡 motionMap 一個 keyword 指向的目標。label 允許 null——沿用
// GET 回應裡 mappings[].label 的形狀，UI 若沒有另外輸入顯示名稱，原樣
// 存回 null 即可，不必假造成空字串。
export interface MotionMapTarget {
  group: string
  index: number | null
  label: string | null
}

// GET /api/live2d/model-config/{name} -> 這個模型真實擁有的動作／點擊區域，
// 合併目前 model_dict.json 裡已存的 motionMap／tapMotions。
export const fetchModelConfig = (
  baseUrl: string,
  name: string,
): Promise<ApiResult<ModelConfig>> =>
  apiGet<ModelConfig>(baseUrl, `/api/live2d/model-config/${encodeURIComponent(name)}`)

// PUT /api/live2d/model-config/{name} 成功時的原始回應（write_model_config
// 的成功分支：{"ok": True, "restart_required": False}）。
interface SaveModelConfigResponse {
  ok: true
  restart_required: boolean
}

// 公開回傳型別不重複 ok（ApiResult 已經有了），只留 restart_required——跟
// api/player.ts 的 PlayerLanguageSaveResult、api/perf.ts 的 AsrSaveResult
// 同一種分法。這個端點目前恆為 false（_refresh_live2d_caches 就地刷新現有
// Live2dModel，不需要重啟），但仍然原樣透傳而不是寫死常數，避免後端未來
// 改變語意時這裡悄悄過期。
export interface SaveModelConfigResult {
  restart_required: boolean
}

// PUT /api/live2d/model-config/{name}：整份取代該模型的 motionMap／
// tapMotions。後端會先驗證（每個 keyword 大小寫不敏感不得重複、每個目標的
// (group, index) 或 hit area 必須真的存在）才寫入，驗證失敗回 400、經
// http.ts 的 normalizeError 收斂成 ApiResult 的 error 字串，呼叫端不需要
// 另外解析。
// emotionMap 省略（undefined）代表「這次不動表情設定」，不是「清空」——後端
// put_model_config 用 body.get("emotionMap") 讀，拿到 None 就整個跳過那段寫入。
// 傳空物件才是真的清空。任何不呼叫這裡的舊路徑因此不會意外洗掉表情對應。
export async function saveModelConfig(
  baseUrl: string,
  name: string,
  motionMap: Record<string, MotionMapTarget>,
  tapMotions: Record<string, TapMotionEntry[]>,
  emotionMap?: Record<string, number>,
): Promise<ApiResult<SaveModelConfigResult>> {
  const res = await apiPut<SaveModelConfigResponse>(
    baseUrl,
    `/api/live2d/model-config/${encodeURIComponent(name)}`,
    emotionMap === undefined
      ? { motionMap, tapMotions }
      : { motionMap, tapMotions, emotionMap },
  )
  if (!res.ok) return res
  return { ok: true, data: { restart_required: res.data.restart_required } }
}

// 新增一個 keyword 前的純驗證，回傳穩定識別字串讓 UI 翻譯——跟這個專案裡
// 其他驗證函式（characters.ts 的 validateAvatarFile、background.ts 的
// validateBackgroundFile）同一種「回傳識別字串而非拋例外／回傳中文」的做法。
//
// 檢查順序：empty -> invalidChars -> duplicate。empty 最基本，優先於一切；
// invalidChars 是結構性問題（這個字串連被掃描器正確辨識都做不到），排在
// duplicate（資料層面的衝突）之前——如果兩者都成立，「這個字元不合法」比
// 「這個字重複了」更接近使用者要先修的問題。
//
// 空白：只有空白的字串（例如 "   "）視為 empty，不是合法但空洞的 keyword——
// trim 之後才判斷是否為空字串。
//
// 方括號：live2d_model.py 的掃描器是逐字元找 '[' 再讀到對應的 ']'、把中間
// 的原文跟 motion_map 的 key 逐字比對（見 build_model_config 模組頭的
// live2d_model.py 掃描器說明，以及 task brief）。若 keyword 本身含有 '[' 或
// ']'，掃描器在文字裡找到的 "[key]" 永遠不會等於這個含方括號的 key 本身——
// 比對邏輯錯亂，這個 keyword 存進去也永遠打不中。所以任何含 '[' 或 ']' 的
// keyword 一律回絕，不管方括號出現在哪個位置。
//
// 重複：後端 live2d_model.py 建構 motion_map 時對每個 key 做 k.lower()，
// "Wave" 與 "wave" 在後端是同一個字典鍵，寫兩筆等於後面蓋掉前面、消失的
// 那筆變成使用者以為存在但永遠打不中的死設定，且沒有任何錯誤提示。所以
// duplicate 檢查必須不分大小寫比對 existing。
export function validateKeyword(
  keyword: string,
  existing: string[],
): 'empty' | 'duplicate' | 'invalidChars' | null {
  const trimmed = keyword.trim()
  if (trimmed === '') return 'empty'
  if (trimmed.includes('[') || trimmed.includes(']')) return 'invalidChars'
  const lowered = trimmed.toLowerCase()
  if (existing.some((k) => k.toLowerCase() === lowered)) return 'duplicate'
  return null
}
