// 舞台頁（?stage=1）：給 OBS 瀏覽器來源擷取的畫面，只有角色、特效、字幕與正在回的
// 留言。它連的是同一個 /client-ws，只是帶 stage=1，後端就不會讓它接手私人對話。
//
// 不含 React，所以能用 node:test 驗證。

export function isStagePage(search: string): boolean {
  return new URLSearchParams(search).get('stage') === '1'
}

// &bg=none：背景透明，可以疊在 OBS 裡別的畫面上。
export function stageBackgroundHidden(search: string): boolean {
  return new URLSearchParams(search).get('bg') === 'none'
}

export function withStageParam(wsUrl: string): string {
  let url: URL
  try {
    url = new URL(wsUrl)
  } catch {
    // 壞掉的位址照原樣交給連線，讓它以「連不上」的方式失敗，而不是整頁炸掉。
    return wsUrl
  }
  url.searchParams.set('stage', '1')
  return url.toString()
}

export const IS_STAGE: boolean =
  typeof window !== 'undefined' && isStagePage(window.location.search)
