/**
 * WebSocket 自動重連的兩個決定：要不要重連、隔多久重連。
 *
 * 在這之前 websocket-service 的 onclose 只是把狀態標成 CLOSED，沒有任何重連。
 * 桌面上看不太出來（分頁通常不會被凍結），但手機一切到別的 App，瀏覽器就會
 * 凍結背景分頁、連線被斷掉，切回來時它永遠是斷的——畫面看起來正常，只是再也
 * 收不到任何訊息，使用者只能重整。
 *
 * 抽成純函式是為了測得到：這兩個決定錯了不會有任何錯誤訊息，只會表現成「有時
 * 候連不回來」或「按了斷線又自己連上」，都是很難重現的抱怨。
 */

/** 第一次重連的間隔。切回前景時斷線通常已經發生一陣子了，這次要快。 */
export const BASE_RECONNECT_DELAY_MS = 1000

/**
 * 退避上限。後端可能只是在重啟，無上限的話第十次就要等十七分鐘，
 * 實際上等於再也不會連上。
 */
export const MAX_RECONNECT_DELAY_MS = 30000

export function reconnectDelayMs(attempt: number): number {
  // 壞的次數（NaN／負數）當成第一次處理，絕不能回傳 NaN——setTimeout 收到 NaN
  // 會立刻執行，變成沒有間隔的重連風暴。
  const safeAttempt = Number.isFinite(attempt) && attempt > 0 ? Math.floor(attempt) : 0
  const delay = BASE_RECONNECT_DELAY_MS * 2 ** safeAttempt
  return Math.min(delay, MAX_RECONNECT_DELAY_MS)
}

export interface ReconnectContext {
  /** 這次關閉是不是使用者／程式主動要求的。 */
  intentional: boolean
  /** 上次連過的位址；從沒連過就沒有東西可以重連。 */
  url: string | null
}

export function shouldAutoReconnect(ctx: ReconnectContext): boolean {
  if (ctx.intentional) return false
  return Boolean(ctx.url)
}

/**
 * 連線是不是「卡住但沒關閉」。
 *
 * onclose 只在對方或網路層真的關閉時才來。連線半死（中間的代理靜靜丟包、
 * 網路換了但 socket 還沒被通知）時它永遠不會來，畫面看起來是連著的，只是
 * 再也收不到任何訊息——沒有這個判斷就永遠不會觸發重連。
 *
 * `missedAllowed` 是容許連續漏掉幾次心跳。設 1 會讓一次網路抖動就砍掉連線
 * 重連，反而更不穩。
 */
export function isHeartbeatStale(
  lastAckAt: number | null,
  now: number,
  intervalMs: number,
  missedAllowed: number,
): boolean {
  // 剛連上、第一個 ack 還沒回來的空窗期不能誤判成斷線。
  if (lastAckAt === null) return false
  return now - lastAckAt > intervalMs * missedAllowed
}

/**
 * 心跳間隔。太短會在行動網路下白白耗電，太長則讓「卡住但沒關閉」的連線拖很久
 * 才被發現。25 秒落在常見反向代理的閒置逾時（多半 60 秒起跳）之內。
 */
export const HEARTBEAT_INTERVAL_MS = 25000

/** 容許連續漏掉幾次。設 1 會讓一次網路抖動就砍掉連線重連，反而更不穩。 */
export const HEARTBEAT_MISSED_ALLOWED = 2
