import { useEffect, useState } from 'react';

// 窄螢幕（手機、平板直向）＝ Chakra 的 md 斷點以下（48em）。
// 直式版面跟寬螢幕不是同一棵元件樹（聊天與輸入列只能掛一份，不然排隊中的訊息
// 會分成兩份），所以用 JS 判斷、只渲染其中一種，不靠 CSS 藏起來。
const NARROW = '(max-width: 47.99em)';

export function useIsNarrow(): boolean {
  const [narrow, setNarrow] = useState(() => window.matchMedia(NARROW).matches);
  useEffect(() => {
    const query = window.matchMedia(NARROW);
    const update = () => setNarrow(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return narrow;
}
