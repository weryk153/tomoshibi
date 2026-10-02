// 打包版的頁面從 file:// 載入，送給後端的請求 Origin 是 "null" 或 "file://"。
// 後端只放行 app 自己的頁面（擋別的網站趁你開著 app 改設定），而 "null" 也是
// 別的網站用沙箱 iframe 送得出來的值，不能整個放行。所以由主程序把「我們自己的
// 頁面」送出的請求改成後端自己的位址——網頁裡的程式碰不到主程序這一層。
export function appOriginFor(origin: string | undefined, targetUrl: string): string | null {
  if (origin !== 'null' && origin !== 'file://') return null
  try {
    const url = new URL(targetUrl)
    const scheme = url.protocol === 'wss:' || url.protocol === 'https:' ? 'https:' : 'http:'
    return `${scheme}//${url.host}`
  } catch {
    return null
  }
}
