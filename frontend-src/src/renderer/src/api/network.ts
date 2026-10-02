// 遠端連線的端點包裝。GET /api/network-info 讀現況；POST /api/network/host 改
// 綁定位址（要重啟後端才生效，由設定抽屜頂端的提示處理）。後端見
// src/open_llm_vtuber/network_route.py。
//
// 跟其他 api/*.ts 同一套慣例：一律回傳 ApiResult<T>，不 throw。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export interface NetworkUrl {
  type: 'lan' | 'tailscale'
  ip: string
  url: string
}

export interface NetworkInfo {
  urls: NetworkUrl[]
  port: number | null
  scheme: 'http' | 'https'
  https_url: string | null
  // 這次啟動實際綁的位址只聽本機：網址連不上。
  localhost_only: boolean
  // conf.yaml 的設定（設定頁的「允許區網連線」）。重啟前可以跟 localhost_only 對不上。
  allow_other_devices: boolean
  mic_needs_https: boolean
}

// GET /api/network-info -> 目前可從其他裝置連到這台伺服器的網址清單
// （同 Wi-Fi／Tailscale／HTTPS）、伺服器目前是否只綁 localhost、麥克風是否
// 需要 HTTPS 才能用。後端這支路由刻意「不」限定只有 localhost 呼叫端才能拿到
// 完整清單（見 character_route.py 該路由上方的註解：已經連進來的裝置可能想
// 把其他可連的網址轉交給第三台裝置），前端這裡原樣轉發，不額外過濾。
export const fetchNetworkInfo = (baseUrl: string): Promise<ApiResult<NetworkInfo>> =>
  apiGet<NetworkInfo>(baseUrl, '/api/network-info')

// remote-access.tsx 的 QR code 要編碼「目前唯一值得掃的那個網址」——不是
// urls[0]，也不是任何寫死的欄位優先順序，而是「手機瀏覽器掃了之後真的連得
// 上、且麥克風權限給得下去」的那個。
//
// 判斷順序跟 character_route.py 的 mic_needs_https 註解對齊：
// 1. https_url 優先——Tailscale Serve 代理出來的網址，麥克風要用的安全內容
//    （secure context）只有 HTTPS 或 localhost 給得了，LAN 的 http:// 給不了。
//    https_url 不受 localhost_only 影響：後端註解說得很明白，Serve 是從
//    loopback 代理出去的，即使伺服器本身只綁 127.0.0.1，這個網址還是通。
// 2. 沒有 https_url 時退回 urls 裡第一筆——但前提是 localhost_only 為
//    false。localhost_only 為 true 時 urls 仍可能非空（OS 找得到 LAN
//    介面卡，但伺服器 socket 只收 loopback），這時那些網址一律連不上，
//    回傳 null 讓呼叫端知道「沒有可秀的網址」，不要生一個掃了也沒用的 QR。
// 3. urls 為空、https_url 也是 null，同樣回傳 null。
export const pickPrimaryUrl = (info: NetworkInfo): string | null => {
  if (info.https_url) return info.https_url
  if (info.localhost_only) return null
  return info.urls[0]?.url ?? null
}

// remote-access.tsx 底下那句「用 http 網址可以打字聊天，但麥克風需要 HTTPS，
// 請依教學設定 Tailscale Serve」該不該出現。
//
// 不能只看 mic_needs_https。那個旗標講的是「你現在正在看的這個網址」需不需要
// HTTPS，而使用者幾乎總是從 http://127.0.0.1 打開設定頁，所以它幾乎永遠是
// true——包括 Tailscale Serve 已經設好、上方正秀著「麥克風可用・HTTPS」和一個
// 可用網址的時候。那句話這時候會直接跟它上面的內容打架，讀起來像是設定失敗。
//
// 判斷跟 pickPrimaryUrl 對齊：有 https_url 就代表這台已經有一個麥克風用得了的
// 網址，教學就沒必要再出現。
export const shouldWarnMicNeedsHttps = (info: NetworkInfo): boolean =>
  info.mic_needs_https && !info.https_url

export const hostBody = (allow: boolean): { allow_other_devices: boolean } => ({ allow_other_devices: allow })

export const setAllowOtherDevices = (
  baseUrl: string,
  allow: boolean,
): Promise<ApiResult<{ ok: boolean; restart_required: boolean }>> =>
  apiPost<{ ok: boolean; restart_required: boolean }>(baseUrl, '/api/network/host', hostBody(allow))
