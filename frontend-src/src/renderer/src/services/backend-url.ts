/**
 * 後端位址的預設值：跟著頁面來源走，而不是寫死 127.0.0.1。
 *
 * 網頁版是由後端自己 serve 出去的，所以頁面來源就是後端。寫死
 * `ws://127.0.0.1:12393` 在本機看起來完全正常——直到換一台裝置：手機上的
 * 127.0.0.1 是手機自己，於是「頁面載得出來，但永遠停在未連線」。
 *
 * HTTPS 的情況更隱蔽：https 頁面開 `ws://` 會被瀏覽器當成 mixed content 直接
 * 擋掉，所以 Tailscale Serve 掛好、憑證也對，手機還是連不上後端。協定必須跟著
 * 頁面一起升成 wss。
 *
 * 兩種情況不能跟著頁面走，要退回寫死的位址：
 *   - Vite 開發伺服器（dev:web）：頁面在 3000、後端在 12393，而 vite.config.ts
 *     沒有設 proxy，跟著頁面走會連到開發伺服器自己。
 *   - 桌面版（electron）：從 file:// 載入，host 是空的。
 *
 * 這些只是「沒有存過設定時的預設值」。設定頁的連線設定一旦寫進 localStorage
 * 就以那份為準，這裡不會覆蓋它。
 */

const FALLBACK_HOST = '127.0.0.1:12393'
const WS_PATH = '/client-ws'

// vite.config.ts 的 server.port。改那邊要記得改這裡——改錯的話開發模式一開就
// 連不上後端，是立刻看得見的失敗，不會安靜地錯下去。
const VITE_DEV_PORT = '3000'

export interface PageLocation {
  protocol: string
  host: string
}

function usablePageOrigin(loc: PageLocation | undefined): PageLocation | null {
  if (!loc) return null
  if (loc.protocol !== 'http:' && loc.protocol !== 'https:') return null
  if (!loc.host) return null
  if (loc.host.endsWith(`:${VITE_DEV_PORT}`)) return null
  return loc
}

export function deriveBaseUrl(loc: PageLocation | undefined): string {
  const origin = usablePageOrigin(loc)
  if (!origin) return `http://${FALLBACK_HOST}`
  return `${origin.protocol}//${origin.host}`
}

export function deriveWsUrl(loc: PageLocation | undefined): string {
  const origin = usablePageOrigin(loc)
  if (!origin) return `ws://${FALLBACK_HOST}${WS_PATH}`
  const scheme = origin.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${scheme}//${origin.host}${WS_PATH}`
}
