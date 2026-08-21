// 前端呼叫後端 REST 的薄層。
//
// 上游前端只用 WebSocket，renderer 內原本沒有任何 fetch()，所以這裡沒有既有
// 模式可循。刻意做得薄：只處理 URL 串接、逾時、以及把後端兩種不同形狀的錯誤
// 回應正規化成一種。不做快取、不做重試——那些會讓「設定存檔失敗」變得難以理解。

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string }

const DEFAULT_TIMEOUT_MS = 15000

export function buildUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`
}

// 後端有兩種錯誤形狀：POST 端點回 {ok:false,error}，GET 端點回 {error}。
// 兩者都取 error 欄位；都沒有時退回含狀態碼的字串，絕不回傳 undefined
// ——UI 顯示 "undefined" 比顯示狀態碼更糟。
export function normalizeError(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'error' in body) {
    const e = (body as { error: unknown }).error
    if (typeof e === 'string' && e.length > 0) return e
  }
  return `請求失敗（HTTP ${status}）`
}

async function request<T>(
  method: 'GET' | 'POST' | 'PUT',
  baseUrl: string,
  path: string,
  body: unknown,
  timeoutMs: number,
): Promise<ApiResult<T>> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(buildUrl(baseUrl, path), {
      method,
      signal: controller.signal,
      ...(method === 'POST' || method === 'PUT'
        ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
        : {}),
    })
    let parsed: unknown = null
    try {
      parsed = await res.json()
    } catch {
      // 非 JSON 回應（例如代理伺服器的 HTML 錯誤頁）
      if (!res.ok) return { ok: false, error: `請求失敗（HTTP ${res.status}）` }
    }
    if (!res.ok) return { ok: false, error: normalizeError(parsed, res.status) }
    return { ok: true, data: parsed as T }
  } catch (e) {
    // AbortError（逾時）與網路錯誤都走這裡。不讓例外逸出——呼叫端一律看 ok 欄位。
    const name = e instanceof Error ? e.name : ''
    if (name === 'AbortError') return { ok: false, error: `請求逾時（${timeoutMs} 毫秒）` }
    return { ok: false, error: e instanceof Error ? e.message : '網路錯誤' }
  } finally {
    clearTimeout(timer)
  }
}

export const apiGet = <T>(baseUrl: string, path: string, timeoutMs = DEFAULT_TIMEOUT_MS) =>
  request<T>('GET', baseUrl, path, undefined, timeoutMs)

export const apiPost = <T>(
  baseUrl: string,
  path: string,
  body: unknown,
  timeoutMs = DEFAULT_TIMEOUT_MS,
) => request<T>('POST', baseUrl, path, body, timeoutMs)

export const apiPut = <T>(
  baseUrl: string,
  path: string,
  body: unknown,
  timeoutMs = DEFAULT_TIMEOUT_MS,
) => request<T>('PUT', baseUrl, path, body, timeoutMs)
