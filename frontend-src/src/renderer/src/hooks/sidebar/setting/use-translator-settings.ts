// you.tsx「用其他語言發聲」區塊（Step 5）的狀態與存檔邏輯。後端見
// src/open_llm_vtuber/translator_route.py 的 GET/POST /api/translator-config，
// 機制說明見 service_context.py:616 附近的 init_translate 註解。
//
// SUBTITLE_LANG_OPTIONS 是這個檔案存在的主要理由之一：src/open_llm_vtuber/
// translate/deeplx.py 的 LANG_NAME_TO_DEEPL_CODE 表頭註解明確指名「跟
// use-translator-settings.ts 的 SUBTITLE_LANG_OPTIONS 表同步」，這裡就是
// 那份對應的前端表。**value 必須是跟該表 KEYS 逐字相同的繁體中文字串**，
// 不能用 i18n 顯示文字代替——subtitle_target_lang 存進 conf.yaml 的是這個
// 值本身（不是使用者看到的翻譯文案），因為同一個值要同時給兩種引擎用：
// llm 引擎把它原樣塞進翻譯 prompt（哪種介面語言都一樣是這串繁中字）；
// deeplx 引擎則靠 resolve_deepl_target_lang() 把它對照成 DeepL 代碼。
// 所以這裡的 value 欄位在五種介面語言下都不能變，只有 labelKey 對應的
// 翻譯文字會跟著介面語言換。
//
// 沒有收錄 LANG_NAME_TO_DEEPL_CODE 裡的三個別名（簡體「繁体中文／简体中文」
// 兩種簡寫、以及籠統的「中文」）——那些是後端為了容忍手動編輯 conf.yaml
// 而留的相容別名，不是 UI 要另外提供的獨立選項，只會讓下拉選單多出語意
// 重複的項目。
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
// 相對路徑，不用 '@/api/...' 別名——那個別名只有 electron-vite 的 bundler
// 認得，`node --test` 直接執行 .ts 檔案時完全不認識它，會整個檔案載入失敗
// （ERR_MODULE_NOT_FOUND: Cannot find package '@/api'）。這正是這個檔案的
// 專屬測試 use-translator-settings.test.ts 一度「靜默沒有真正跑到」的原因：
// node --test 對單一檔案的載入錯誤沒有讓整體 `pnpm test` 回報失敗，只是那個
// 檔案的測試從頭到尾沒被執行、也沒被算進總數，比顯式失敗更難發現。api/*.ts
// 互相 import 全部用相對路徑（見 api/player.ts 的 `from './http.ts'`）就是
// 同一個理由，這裡跨目錄 import api/ 時比照辦理。
import {
  fetchTranslatorConfig,
  saveTranslatorConfig,
  isTranslatorPayloadValid,
  buildTranslatorSavePayload,
  type TranslatorConfigState,
  type TranslatorConfigEdits,
  type TranslatorEngine,
  type TranslatorConfigSaveResult,
} from '../../../api/translator-config.ts'
import type { ApiResult } from '../../../api/http.ts'

export interface SubtitleLangOption {
  value: string
  labelKey: string
}

// 「原文（不翻譯）」的前端專用哨兵值：從不送進 subtitle_target_lang，選到它
// 代表 translate_subtitle=false（見下面的 mapSubtitleSelection）。用空字串
// 而不是另造一個常數字串，是因為 GET /api/translator-config 在字幕翻譯
// 關閉、從未設定過時，subtitle_target_lang 本來就是空字串（translator_route.py
// 420-422 行：`str(subtitle_target) if subtitle_target is not None else ""`），
// 兩者共用同一個值，選單初始化時不需要另外做值轉換。
export const SUBTITLE_LANG_ORIGINAL = ''

// 對應 src/open_llm_vtuber/translate/deeplx.py 的 LANG_NAME_TO_DEEPL_CODE，
// 「original 4」＋「rest of DeepL's supported target languages」共 30 個，
// 逐一對應 locales/*/translation.json 裡的 30 個 settings.translator.subtitleLangXx
// 鍵（不含 subtitleLangOriginal，那是上面的哨兵值，不在這份清單裡）。
export const SUBTITLE_LANG_OPTIONS: readonly SubtitleLangOption[] = [
  { value: '繁體中文', labelKey: 'settings.translator.subtitleLangZhTw' },
  { value: '日文', labelKey: 'settings.translator.subtitleLangJa' },
  { value: '英文', labelKey: 'settings.translator.subtitleLangEn' },
  { value: '韓文', labelKey: 'settings.translator.subtitleLangKo' },
  { value: '保加利亞文', labelKey: 'settings.translator.subtitleLangBg' },
  { value: '捷克文', labelKey: 'settings.translator.subtitleLangCs' },
  { value: '丹麥文', labelKey: 'settings.translator.subtitleLangDa' },
  { value: '德文', labelKey: 'settings.translator.subtitleLangDe' },
  { value: '希臘文', labelKey: 'settings.translator.subtitleLangEl' },
  { value: '西班牙文', labelKey: 'settings.translator.subtitleLangEs' },
  { value: '愛沙尼亞文', labelKey: 'settings.translator.subtitleLangEt' },
  { value: '芬蘭文', labelKey: 'settings.translator.subtitleLangFi' },
  { value: '法文', labelKey: 'settings.translator.subtitleLangFr' },
  { value: '匈牙利文', labelKey: 'settings.translator.subtitleLangHu' },
  { value: '印尼文', labelKey: 'settings.translator.subtitleLangId' },
  { value: '義大利文', labelKey: 'settings.translator.subtitleLangIt' },
  { value: '立陶宛文', labelKey: 'settings.translator.subtitleLangLt' },
  { value: '拉脫維亞文', labelKey: 'settings.translator.subtitleLangLv' },
  { value: '挪威文', labelKey: 'settings.translator.subtitleLangNb' },
  { value: '荷蘭文', labelKey: 'settings.translator.subtitleLangNl' },
  { value: '波蘭文', labelKey: 'settings.translator.subtitleLangPl' },
  { value: '葡萄牙文', labelKey: 'settings.translator.subtitleLangPt' },
  { value: '羅馬尼亞文', labelKey: 'settings.translator.subtitleLangRo' },
  { value: '俄文', labelKey: 'settings.translator.subtitleLangRu' },
  { value: '斯洛伐克文', labelKey: 'settings.translator.subtitleLangSk' },
  { value: '斯洛維尼亞文', labelKey: 'settings.translator.subtitleLangSl' },
  { value: '瑞典文', labelKey: 'settings.translator.subtitleLangSv' },
  { value: '土耳其文', labelKey: 'settings.translator.subtitleLangTr' },
  { value: '烏克蘭文', labelKey: 'settings.translator.subtitleLangUk' },
  { value: '簡體中文', labelKey: 'settings.translator.subtitleLangZhHans' },
]

// 字幕下拉選單的值 -> {translate_subtitle, subtitle_target_lang} 的唯一轉換
// 入口。純函式，不依賴 React——選到「原文」哨兵值就是關閉字幕翻譯（且不留
// 舊的 target lang，一併清空，不讓 conf.yaml 留著一個使用者已經不再選用的
// 語言值造成誤解）；選到任何一個 SUBTITLE_LANG_OPTIONS 的值就是開啟，target
// 就是選到的值本身。
export function mapSubtitleSelection(value: string): {
  translate_subtitle: boolean
  subtitle_target_lang: string
} {
  if (value === SUBTITLE_LANG_ORIGINAL) {
    return { translate_subtitle: false, subtitle_target_lang: '' }
  }
  return { translate_subtitle: true, subtitle_target_lang: value }
}

// 反向：目前存檔狀態 -> 下拉選單該顯示哪個值。translate_subtitle=false 時一律
// 顯示「原文」，不管 subtitle_target_lang 裡殘留著什麼舊值——那個值只有在
// translate_subtitle=true 時才會被後端實際拿去用（見 service_context.py 的
// init_translate：字幕引擎「Built only when translate_subtitle is True」）。
export function subtitleStateToSelection(config: {
  translate_subtitle: boolean
  subtitle_target_lang: string
}): string {
  return config.translate_subtitle ? config.subtitle_target_lang : SUBTITLE_LANG_ORIGINAL
}

export interface UseTranslatorSettingsResult {
  config: TranslatorConfigState | null
  loadError: string | null
  engineSaving: boolean
  subtitleSaving: boolean
  saveEngine: (
    engine: TranslatorEngine,
    deeplxEndpoint?: string,
  ) => Promise<ApiResult<TranslatorConfigSaveResult>>
  saveSubtitleSelection: (value: string) => Promise<ApiResult<TranslatorConfigSaveResult>>
}

// active：跟 asr.tsx／memory.tsx 同一種訊號，這個分頁被抽屜重新看見時要不要
// 重抓一次現值。you.tsx 目前固定傳 true（跟 general.tsx 傳給 <You active />
// 的方式一致），保留這個參數是為了跟其餘 use-*-settings hook 的介面對齊，
// 不是這次任務用得到的行為。
export function useTranslatorSettings(
  baseUrl: string,
  active = true,
): UseTranslatorSettingsResult {
  const { t } = useTranslation()
  const [config, setConfig] = useState<TranslatorConfigState | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [engineSaving, setEngineSaving] = useState(false)
  const [subtitleSaving, setSubtitleSaving] = useState(false)

  useEffect(() => {
    if (!active) return undefined
    let cancelled = false
    setLoadError(null)
    ;(async () => {
      const result = await fetchTranslatorConfig(baseUrl)
      if (cancelled) return
      if (result.ok) {
        setConfig(result.data)
      } else {
        // http.ts 的 normalizeError 保證 result.error 不是空字串，這裡的
        // fallback 只是防禦性寫法（跟 asr.tsx／you.tsx 既有 loadError 欄位
        // 同一種慣例），也讓 settings.translator.loadError 這把鍵確實被引用到。
        setLoadError(result.error || t('settings.translator.loadError'))
      }
    })()
    return (): void => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, active])

  // 共用的送出邏輯：組 payload、擋下不合法組合、呼叫 API、成功時把 state
  // 更新成「這次實際送出的值」（不是重新 GET 一次）——跟 asr.tsx 的
  // applySaveResult 同一種道理，避免多打一次 API 只為了刷新畫面。
  const save = useCallback(
    async (edits: TranslatorConfigEdits): Promise<ApiResult<TranslatorConfigSaveResult>> => {
      if (!config) {
        return { ok: false, error: 'translator config not loaded yet' }
      }
      const payload = buildTranslatorSavePayload(config, edits)
      if (!isTranslatorPayloadValid(payload)) {
        return { ok: false, error: 'invalid translator config payload' }
      }
      const result = await saveTranslatorConfig(baseUrl, config, edits)
      if (result.ok) {
        setConfig((prev) => (prev ? { ...prev, ...edits } : prev))
      }
      return result
    },
    [baseUrl, config],
  )

  const saveEngine = useCallback(
    async (engine: TranslatorEngine, deeplxEndpoint?: string) => {
      setEngineSaving(true)
      const result = await save(
        deeplxEndpoint === undefined ? { engine } : { engine, deeplx_endpoint: deeplxEndpoint },
      )
      setEngineSaving(false)
      return result
    },
    [save],
  )

  const saveSubtitleSelection = useCallback(
    async (value: string) => {
      setSubtitleSaving(true)
      const result = await save(mapSubtitleSelection(value))
      setSubtitleSaving(false)
      return result
    },
    [save],
  )

  return {
    config, loadError, engineSaving, subtitleSaving, saveEngine, saveSubtitleSelection,
  }
}
