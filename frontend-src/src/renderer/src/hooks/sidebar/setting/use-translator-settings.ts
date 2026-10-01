// you.tsx「用其他語言發聲」區塊（Step 5）的狀態與存檔邏輯。後端見
// src/open_llm_vtuber/translator_route.py 的 GET/POST /api/translator-config，
// 機制說明見 service_context.py:616 附近的 init_translate 註解。
//
// 字幕翻譯不在這裡：開不開是每個角色自己的設定，翻成什麼跟「你看的語言」走。
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
  type TranslatorConfigState,
  type TranslatorConfigEdits,
  type TranslatorEngine,
  type TranslatorConfigSaveResult,
} from '../../../api/translator-config.ts'
import type { ApiResult } from '../../../api/http.ts'

export interface UseTranslatorSettingsResult {
  config: TranslatorConfigState | null
  loadError: string | null
  engineSaving: boolean
  saveEngine: (
    engine: TranslatorEngine,
    deeplxEndpoint?: string,
  ) => Promise<ApiResult<TranslatorConfigSaveResult>>
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

  // 共用的送出邏輯：呼叫 API、成功時把 state
  // 更新成「這次實際送出的值」（不是重新 GET 一次）——跟 asr.tsx 的
  // applySaveResult 同一種道理，避免多打一次 API 只為了刷新畫面。
  const save = useCallback(
    async (edits: TranslatorConfigEdits): Promise<ApiResult<TranslatorConfigSaveResult>> => {
      if (!config) {
        return { ok: false, error: 'translator config not loaded yet' }
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

  return {
    config, loadError, engineSaving, saveEngine,
  }
}
