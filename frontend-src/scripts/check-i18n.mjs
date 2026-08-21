// i18n 一致性檢查。不引入新依賴，用 node 內建模組。
//
// 守住三件事：
//
// 1. 五個語言的鍵集必須完全一致（少一個鍵 = 該語言缺翻譯，i18next 會靜默
//    fallback，肉眼看不出來）。
// 2. 不得殘留舊品牌名。
// 3. 程式碼用到的每個 t() 鍵都必須存在於語言檔內。
//
// 第 3 項是後來補的，因為前兩項合起來仍有一個類別性缺口：五個語言「一致地」
// 缺少同一個鍵時，第 1 項會通過。實際踩到過——settings.tabs.tts 在五個語言
// 全部缺少，而 setting-ui.tsx 正在渲染它，分頁標籤是壞的，檢查卻是綠的。
// 語言互相比對永遠抓不到這種情況，只有拿程式碼去比對語言檔才抓得到。
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const LOCALES = ['zh', 'en', 'ja', 'ko', 'zh-CN']
// 語系檔裡不准出現的舊品牌名。這只管翻譯字串——整個 repo 的把關在
// scripts/check_branding.py（發布前必跑）。
const FORBIDDEN = ['Warashi']
const SRC = join(here, '..', 'src/renderer/src')

const flatten = (obj, prefix = '') =>
  Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k
    return v !== null && typeof v === 'object' ? flatten(v, key) : [[key, v]]
  })

let failed = false
const keysets = {}
// 第 4 節要用巢狀結構判斷命名空間是否為空，扁平化的 key set 看不出來。
const trees = {}

for (const lng of LOCALES) {
  const path = join(here, '..', 'src/renderer/src/locales', lng, 'translation.json')
  let data
  try {
    data = JSON.parse(readFileSync(path, 'utf8'))
  } catch (e) {
    console.error(`✗ ${lng}: 讀取或解析失敗 — ${e.message}`)
    failed = true
    continue
  }
  const entries = flatten(data)
  keysets[lng] = new Set(entries.map(([k]) => k))
  trees[lng] = data

  for (const [key, value] of entries) {
    if (typeof value !== 'string') continue
    for (const bad of FORBIDDEN) {
      if (value.includes(bad)) {
        console.error(`✗ ${lng}: ${key} 含舊品牌名 "${bad}" — ${value}`)
        failed = true
      }
    }
  }
  console.log(`  ${lng}: ${entries.length} 條`)
}

const base = keysets.zh
if (base) {
  for (const lng of LOCALES) {
    if (lng === 'zh' || !keysets[lng]) continue
    const missing = [...base].filter((k) => !keysets[lng].has(k))
    const extra = [...keysets[lng]].filter((k) => !base.has(k))
    if (missing.length || extra.length) {
      console.error(`✗ ${lng}: 缺 ${missing.length} 個鍵、多 ${extra.length} 個鍵`)
      if (missing.length) console.error(`    缺：${missing.slice(0, 5).join(', ')}`)
      if (extra.length) console.error(`    多：${extra.slice(0, 5).join(', ')}`)
      failed = true
    }
  }
}

// --- 3. 程式碼用到的鍵是否都存在 -----------------------------------------
//
// 只認靜態字面值的 t('a.b.c')。樣板字串組出來的鍵（t(`x.${y}`)）無法靜態解析，
// 一律跳過並回報數量——把盲點講出來，而不是讓它靜默存在。

const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name)
    if (e.isDirectory()) return e.name === 'locales' ? [] : walk(p)
    return /\.tsx?$/.test(e.name) ? [p] : []
  })

const STATIC_T = /\bt\(\s*(['"])([A-Za-z0-9_][A-Za-z0-9_.]*)\1/g
const DYNAMIC_T = /\bt\(\s*`/g

if (base) {
  const used = new Map() // 鍵 -> 首次出現的位置
  let dynamicCount = 0

  // 剝掉區塊註解再比對。註解掉的 JSX（{/* <Text>{t('X')}</Text> */}）不是活的
  // 程式碼，對它報警只會訓練人忽略這個檢查。已確認本專案的字串字面值內不含
  // "/*"，所以這個剝除不會誤傷程式碼；若日後有人加了含 "/*" 的字串，這裡會
  // 開始漏掉它後面的內容，屆時要改成真正的詞法分析。
  const stripBlockComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '')

  for (const file of walk(SRC)) {
    const src = stripBlockComments(readFileSync(file, 'utf8'))
    const where = relative(SRC, file)
    for (const m of src.matchAll(STATIC_T)) {
      if (!used.has(m[2])) used.set(m[2], where)
    }
    dynamicCount += [...src.matchAll(DYNAMIC_T)].length
  }

  const unknown = [...used].filter(([key]) => !base.has(key))
  console.log(`  程式碼用到 ${used.size} 個靜態鍵`)

  if (unknown.length) {
    console.error(`✗ 有 ${unknown.length} 個鍵在程式碼裡被使用，但語言檔內不存在：`)
    for (const [key, where] of unknown) console.error(`    ${key}  （${where}）`)
    failed = true
  }

  if (dynamicCount) {
    console.log(
      `  註：另有 ${dynamicCount} 處動態組成的鍵，樣板字串無法靜態解析`,
    )
  }

  // --- 4. 動態鍵的命名空間完整性 -----------------------------------------
  //
  // 上面那個 dynamicCount 只是把盲點數出來，不會發現任何問題。實際踩過的坑：
  // settings.memory.errors 在五個語言裡都是空物件 {}，而程式碼用一個常數引用
  // settings.memory.errors.invalidInterval——靜態掃描看不到（不是字面值 t()），
  // 動態計數也不管，於是那把鍵從來沒被建立，錯誤訊息會顯示成鍵本身。
  //
  // t(`ns.${x}`) 的形狀無法逐鍵驗證，但可以驗證「ns 存在且非空」，以及對於
  // 值域已知的幾組，逐一比對。這比只數數字有用得多。
  const NAMESPACE_MUST_BE_NON_EMPTY = [
    'settings.scenes.types',
    'settings.scenes.fits',
    'settings.scenes.assetErrors',
    'settings.live2d.musicErrors',
    'settings.performances.triggers',
    'settings.performances.modes',
    'settings.performances.scales',
    'settings.performances.time',
    'aiState',
    'subtitle',
    'effects',
  ]

  // 值域寫死在程式碼裡、可以逐一核對的幾組。來源見各自的 as const 陣列／enum。
  const EXHAUSTIVE = {
    // effects/stage-effect.ts 的 STAGE_EFFECT_IDS
    effects: ['characterEntrance', 'cinematicBurst'],
    // context/ai-state-context.tsx 的 AiStateEnum
    aiState: [
      'idle', 'thinking-speaking', 'interrupted', 'loading', 'listening', 'waiting',
    ],
  }

  const lookup = (obj, path) =>
    path.split('.').reduce((n, part) => (n && typeof n === 'object' ? n[part] : undefined), obj)

  for (const [lang, tree] of Object.entries(trees)) {
    for (const ns of NAMESPACE_MUST_BE_NON_EMPTY) {
      const node = lookup(tree, ns)
      if (!node || typeof node !== 'object' || Object.keys(node).length === 0) {
        console.error(`✗ ${lang}：動態鍵的命名空間 ${ns} 不存在或是空的`)
        failed = true
      }
    }
    for (const [ns, values] of Object.entries(EXHAUSTIVE)) {
      const node = lookup(tree, ns)
      if (!node || typeof node !== 'object') continue
      for (const v of values) {
        if (!(v in node)) {
          console.error(`✗ ${lang}：${ns}.${v} 缺少（程式碼會產生這個值）`)
          failed = true
        }
      }
    }
  }
  console.log(
    `  動態鍵命名空間：${NAMESPACE_MUST_BE_NON_EMPTY.length} 個檢查非空，`
      + `${Object.keys(EXHAUSTIVE).length} 個逐值核對`,
  )

  // --- 5. 不在 t() 裡的鍵引用 --------------------------------------------
  //
  // 上面第 3 節只認 t('a.b.c')。但鍵也可能被存成常數再傳給呼叫端，例如
  // api/memory.ts 的
  //   export const CONSOLIDATION_INVALID_INTERVAL_ERROR = 'settings.memory.errors.invalidInterval'
  // 它的消費端寫的是 t(result.error)，靜態掃描兩邊都看不到這個鍵。實際後果：
  // 那把鍵從來沒有被建立，而五個語言「一致地」都沒有它，所以第 1 節的鍵集
  // 比對也不會報警——錯誤訊息會顯示成鍵本身。
  //
  // 這裡改成掃描「長得像鍵的字串字面值」：開頭是已知的頂層命名空間、且含點。
  // 誤判的代價只是要求補一把翻譯，比漏掉一個顯示成 raw key 的錯誤訊息便宜。
  const TOP_LEVEL = [...new Set([...base].map((k) => k.split('.')[0]))]
  const KEY_LIKE = new RegExp(
    `(['"\`])((?:${TOP_LEVEL.join('|')})\\.[A-Za-z0-9_]+(?:\\.[A-Za-z0-9_]+)*)\\1`,
    'g',
  )
  const referenced = new Map()
  for (const file of walk(SRC)) {
    const src = stripBlockComments(readFileSync(file, 'utf8'))
    for (const m of src.matchAll(KEY_LIKE)) {
      if (!referenced.has(m[2])) referenced.set(m[2], relative(SRC, file))
    }
  }
  const danglingRefs = [...referenced].filter(([key]) => !base.has(key))
  console.log(`  另有 ${referenced.size} 個非 t() 直接引用的鍵`)
  if (danglingRefs.length) {
    console.error(`✗ 有 ${danglingRefs.length} 個鍵以字串常數形式被引用，但語言檔內不存在：`)
    for (const [key, where] of danglingRefs) console.error(`    ${key}  （${where}）`)
    failed = true
  }
}

if (failed) {
  console.error('\ni18n 檢查未通過')
  process.exit(1)
}
console.log('\ni18n 檢查通過：五語言鍵集一致、無殘留品牌名、程式碼用到的鍵都存在')
