// 兩條建置路徑共用的 define。
//
// 網頁版走 vite.config.ts（輸出到 repo 的 frontend/，由後端 serve），桌面版走
// electron.vite.config.ts。兩份設定各自獨立，先前 define 是各寫一份——
// __APP_VERSION__ 只加進網頁版那份，桌面版裡它就是一個未定義的識別字，
// about.tsx 一渲染就 ReferenceError；而 Chakra 的 Tabs 會把所有分頁一次掛載，
// 所以「一打開設定就整片黑」。瀏覽器完全正常，因此拖到使用者開桌面版才發現。
//
// 放在這裡之後，兩邊引用同一個物件，分岔在結構上就不可能發生。
// scripts/check-build-defines.mjs 退居第二道防線：確認兩份設定都還在用這個
// 共用來源、而且沒有人偷偷加了只在單邊生效的 inline define。

import pkg from './package.json'

export const buildDefines = {
  // about.tsx 顯示的版本號。寫死的話改了 package.json 這裡不會跟著動——
  // 一個安靜地慢慢變錯的數字。
  __APP_VERSION__: JSON.stringify(pkg.version),
}
