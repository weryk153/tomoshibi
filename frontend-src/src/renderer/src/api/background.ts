// 背景圖片上傳。後端見 src/open_llm_vtuber/character_route.py 的 POST /api/background。
// 前端這一層的限制刻意與後端一致（不是更寬鬆），這樣使用者選錯檔案時可以立刻
// 知道，而不是等一趟往返之後才收到 400。
//
// BACKGROUND_MAX_BYTES／BACKGROUND_ALLOWED_TYPES 已跟後端的 BG_MAX_BYTES／
// BG_ALLOWED_EXTS 核對過：後端目前是 12 * 1024 * 1024 與
// {".jpg", ".jpeg", ".png", ".gif"}，跟這裡一致。
//
// 後端用副檔名判斷型別（character_route.py:1090-1091 的
// `up_ext = os.path.splitext(up_name)[1].lower(); if up_ext not in BG_ALLOWED_EXTS`），
// 這裡優先用 file.type（瀏覽器給的 MIME）判斷，因為它比副檔名更難偽造。但
// file.type 在某些環境（尤其 Electron／OS 無法辨識 MIME 時）會是空字串——這時
// 若只看 MIME 就一律回報 notImage，會把後端本來會接受的合法檔案（例如一張
// 檔名正確但 MIME 解析不出來的 photo.jpg）擋在網路請求之前，使用者完全沒有
// 辦法繼續。所以 MIME 沒命中允許清單時，退回用副檔名判斷，跟後端的判斷依據
// 一致（大小寫不敏感，比對方式跟 up_ext.lower() 一樣；.jpg／.jpeg 是兩個不同
// 字串，都要各自列在允許清單裡）。
//
// 刻意不處理的另一個方向：一個檔名是 .jfif、但 file.type 回報
// image/jpeg 的檔案，MIME 檢查會直接放行（不會走副檔名回退），送到後端後
// 因為副檔名不在 BG_ALLOWED_EXTS 裡被 400 拒絕。這是一個「送出後才發現」的
// 可見錯誤，使用者看得到、可以重新選檔，不是這裡要修的「靜默擋在請求之前」
// 問題，也不該為了讓它在前端也過而放寬後端沒有的副檔名清單。

import { buildUrl, normalizeError, type ApiResult } from './http.ts'

export const BACKGROUND_MAX_BYTES = 12 * 1024 * 1024
export const BACKGROUND_ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif'] as const

// 跟後端 character_route.py 的 BG_ALLOWED_EXTS 逐字核對過的副檔名清單，供
// file.type 判斷不出來時回退使用。
export const BACKGROUND_ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif'] as const

export type BackgroundFileError = 'notImage' | 'tooLarge'

// 副檔名比對：大小寫不敏感（跟後端 up_ext.lower() 一致），只看檔名結尾。
function hasAllowedBackgroundExtension(filename: string): boolean {
  const lower = filename.toLowerCase()
  return (BACKGROUND_ALLOWED_EXTENSIONS as readonly string[]).some((ext) => lower.endsWith(ext))
}

// 回傳穩定識別字串（不是寫死的中文句子），交給 UI 層自己用 t() 翻譯——本專案
// 把「寫死的使用者可見字串」視為 Critical 缺陷（見 api/memory.ts 的
// CONSOLIDATION_INVALID_INTERVAL_ERROR 檔頭說明，同一個理由）。先驗型別再驗
// 大小：型別錯比大小錯更根本，沒必要對一個型別就不對的檔案再報「太大」。
export function validateBackgroundFile(file: File): BackgroundFileError | null {
  const mimeOk = (BACKGROUND_ALLOWED_TYPES as readonly string[]).includes(file.type)
  if (!mimeOk && !hasAllowedBackgroundExtension(file.name)) {
    return 'notImage'
  }
  if (file.size > BACKGROUND_MAX_BYTES) {
    return 'tooLarge'
  }
  return null
}

// POST /api/background，multipart/form-data。跟 api/characters.ts 的
// uploadAvatar 同一種寫法：http.ts 的 request() 只走 JSON 路徑（固定
// Content-Type: application/json、JSON.stringify(body)），刻意不擴充成支援
// multipart，改用原生 fetch + FormData，並沿用 http.ts 匯出的
// buildUrl／normalizeError，讓錯誤形狀跟其他呼叫一致。
//
// 跟 uploadAvatar 不同的一點：這裡先跑 validateBackgroundFile，不通過就直接
// 回傳失敗的 ApiResult，不發請求。背景圖片檔案通常比頭像大（上限是頭像的
// 24 倍），讓使用者在按下上傳的當下就知道錯在哪，而不是等一趟往返之後才收到
// 後端的 400。
export async function uploadBackground(
  baseUrl: string,
  file: File,
): Promise<ApiResult<{ filename: string }>> {
  const invalid = validateBackgroundFile(file)
  if (invalid) return { ok: false, error: invalid }

  const form = new FormData()
  form.append('file', file)
  try {
    const res = await fetch(buildUrl(baseUrl, '/api/background'), {
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
