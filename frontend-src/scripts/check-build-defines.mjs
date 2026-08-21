// 兩份 vite 設定的 define 必須來自同一個來源。
//
// 這個專案有兩條建置路徑：網頁版走 vite.config.ts（輸出到 repo 的 frontend/，
// 由後端 serve），桌面版走 electron.vite.config.ts。它們是各自獨立的檔案。
//
// 實際發生過的事故：__APP_VERSION__ 只加進 vite.config.ts。網頁版一切正常，
// 桌面版裡它是一個未定義的識別字，about.tsx 一渲染就 ReferenceError；而
// Chakra 的 Tabs 會把所有分頁一次掛載，所以「一打開設定就整片黑」。因為驗證
// 全在瀏覽器做，這個缺口撐到使用者打開桌面版才被發現。
//
// 主要的防線是 build-defines.ts：兩邊引用同一個物件，分岔在結構上不可能發生。
// 這支腳本是第二道，擋的是「有人把共用來源改回 inline」或「只在單邊多加一個
// inline define」——那會讓主要防線失效，而且失效時毫無徵兆。
//
// 刻意用文字比對而不是 import 兩份設定：electron.vite.config.ts 匯出的是物件、
// vite.config.ts 匯出的是需要 mode 參數的 async 函式，真的載入還會把 vite /
// electron-vite / 外掛全都拉進來。要防的是「有人只改了一邊」，看 define 怎麼
// 寫的就夠，而且不會因為載入失敗而變成假警報。

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const SHARED = 'build-defines'
const CONFIGS = [
  { label: '網頁版', file: 'vite.config.ts' },
  { label: '桌面版', file: 'electron.vite.config.ts' },
]

let failed = false

/** 找出所有 `define:` 的寫法：共用來源的引用，或 inline 物件。 */
const inspect = (source) => {
  const shared = []
  const inline = []
  for (const match of source.matchAll(/^\s*define:\s*(.+)$/gm)) {
    const value = match[1].trim().replace(/,$/, '')
    if (value === 'buildDefines') shared.push(value)
    else inline.push(value)
  }
  const importsShared = new RegExp(
    `import\\s*\\{[^}]*\\bbuildDefines\\b[^}]*\\}\\s*from\\s*['"][./]*${SHARED}['"]`,
  ).test(source)
  return { shared, inline, importsShared }
}

for (const { label, file } of CONFIGS) {
  let source
  try {
    source = readFileSync(join(here, '..', file), 'utf8')
  } catch (e) {
    console.error(`✗ 讀不到 ${file} — ${e.message}`)
    failed = true
    continue
  }

  const { shared, inline, importsShared } = inspect(source)

  if (!shared.length) {
    console.error(
      `✗ ${label}（${file}）沒有引用共用的 buildDefines —— `
        + `兩邊各寫一份就會分岔，用到的常數在單邊變成未定義的識別字。`,
    )
    failed = true
  } else if (!importsShared) {
    console.error(`✗ ${label}（${file}）用了 buildDefines 但沒有從 ${SHARED} 匯入`)
    failed = true
  }

  if (inline.length) {
    console.error(
      `✗ ${label}（${file}）有 ${inline.length} 個 inline define：${inline.join(' / ')}`,
    )
    console.error('    inline 的只在這一側生效。請把它放進 build-defines.ts。')
    failed = true
  }

  if (!failed) console.log(`  ${label}：使用共用的 buildDefines ✓`)
}

// 兩份設定都要掛 Tailwind 外掛。這是跟 define 完全同一類的漂移，而且同樣
// 沒有徵兆：少掛的那一側 CSS 照樣產得出來（theme 變數都在），只是一條 utility
// class 都沒有，畫面整片裸奔而主控台毫無錯誤。
//
// 只比對「有沒有提到這個套件」而不比對寫法：兩份設定載入方式不同——
// vite.config.ts 被 vite 用 require 載入，ESM-only 的外掛必須寫成
// `(await import(...)).default()`；electron.vite.config.ts 由 electron-vite 以
// ESM 載入，靜態 import 可行。要求兩邊寫法一致反而會逼出一個壞掉的設定。
const TAILWIND = '@tailwindcss/vite'
for (const { label, file } of CONFIGS) {
  let source
  try {
    source = readFileSync(join(here, '..', file), 'utf8')
  } catch {
    continue // 上面那圈已經回報過讀不到了
  }
  if (source.includes(TAILWIND)) {
    console.log(`  ${label}：已掛上 ${TAILWIND} ✓`)
  } else {
    console.error(
      `✗ ${label}（${file}）沒有掛 ${TAILWIND} —— `
        + `這一側會產出沒有任何 utility class 的 CSS，而且不會報錯。`,
    )
    failed = true
  }
}

// 共用來源本身要真的定義了東西，否則「兩邊一致」只是兩邊都空的。
try {
  const sharedSource = readFileSync(join(here, '..', `${SHARED}.ts`), 'utf8')
  const keys = [...sharedSource.matchAll(/^\s*(__[A-Z0-9_]+__)\s*:/gm)].map((m) => m[1])
  if (!keys.length) {
    console.error(`✗ ${SHARED}.ts 裡沒有任何 define`)
    failed = true
  } else {
    console.log(`  共用來源 ${SHARED}.ts：${keys.length} 個 — ${keys.join(', ')}`)
  }
} catch (e) {
  console.error(`✗ 讀不到 ${SHARED}.ts — ${e.message}`)
  failed = true
}

if (failed) {
  console.error('\n建置設定檢查未通過')
  process.exit(1)
}
console.log('\n建置設定檢查通過：兩份 vite 設定的 define 與 Tailwind 外掛都一致')
