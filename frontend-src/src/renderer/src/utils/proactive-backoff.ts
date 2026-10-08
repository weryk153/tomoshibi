// 主動開口沒人回時，下一次等多久。真人對著沒反應的人不會每分鐘講一次：每次沒人
// 回就把間隔加倍，連續 MAX_UNANSWERED 次都沒回就停下，等對方開口再從頭算。
// 不停的話，她會把自己上一句的提議當成對方問的來回答（自問自答）。

export const MAX_UNANSWERED = 3;
const MIN_SECONDS = 30;

/** 下一次主動開口前要等幾秒；null＝不再主動開口。 */
export function nextProactiveDelay(baseSeconds: number, unanswered: number): number | null {
  if (unanswered >= MAX_UNANSWERED) return null;
  const base = Math.max(MIN_SECONDS, Number(baseSeconds) || MIN_SECONDS);
  return base * 2 ** Math.max(0, unanswered);
}
