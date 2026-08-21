// 「畫面上的值」跟「上次套用時的值」是否已經不同。
//
// 設定分頁的套用／還原按鈕原本永遠是啟用的：沒有任何改動時按下「套用」，
// handleSave 只是把目前的值設成新的還原基準，畫面上什麼都不會動，也沒有任何
// 訊息——按了像沒反應，實際上也真的沒反應。這個判斷讓按鈕只在真的有未套用的
// 變更時才可按，「按了沒事」因此變成「不能按」，是個看得見的狀態。
//
// 這些設定物件都是扁平的 JSON 形狀（字串、數字、布林、字串陣列），所以不需要
// 通用的深層比較。刻意不用 JSON.stringify 比對：那個做法會因為鍵的順序不同而
// 誤判成有變更，而 React 的 setState 展開（{ ...prev, x }）本來就可能改變順序。

type Comparable = unknown;

/** 兩個設定值是否相等。undefined 與 null 視為同一件事（都代表「沒設定」）。 */
export function settingsEqual(a: Comparable, b: Comparable): boolean {
  if (a === b) return true;
  if (a == null || b == null) return a == null && b == null;

  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b)) return false;
    return a.length === b.length && a.every((item, i) => settingsEqual(item, b[i]));
  }

  if (typeof a === 'object' && typeof b === 'object') {
    const ka = Object.keys(a as object);
    const kb = Object.keys(b as object);
    // 只比對兩邊鍵的聯集，不要求順序一致。
    const keys = new Set([...ka, ...kb]);
    for (const key of keys) {
      if (!settingsEqual(
        (a as Record<string, unknown>)[key],
        (b as Record<string, unknown>)[key],
      )) {
        return false;
      }
    }
    return true;
  }

  // NaN === NaN 是 false，但兩個 NaN 對使用者來說沒有差別。數字欄位在輸入到
  // 一半（例如只打了一個負號）時真的會是 NaN，不擋掉的話按鈕會一直亮著。
  if (typeof a === 'number' && typeof b === 'number') {
    return Number.isNaN(a) && Number.isNaN(b);
  }

  return false;
}

/** settingsEqual 的反面，命名成呼叫端讀起來順的樣子。 */
export function settingsDirty(current: Comparable, original: Comparable): boolean {
  return !settingsEqual(current, original);
}
