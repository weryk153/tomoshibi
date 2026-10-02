// createAutosaver 的 React 包裝。還沒送的那筆在三種時候立刻送：欄位失焦（呼叫端接
// onBlur={flush}）、元件卸載、頁面要關掉或重新整理（pagehide）。
//
// 注意：設定抽屜關起來、切分頁時分頁內容不會卸載（Ark 的 Tabs 只有 lazyMount），
// 計時器照常跑完、照常存；真正會丟資料的是關掉頁面，所以要聽 pagehide。
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AUTOSAVE_DELAY_MS, createAutosaver, type SaveResult, type SaveState,
} from '@/utils/autosave';

export function useAutosave<T>(
  save: (value: T) => Promise<SaveResult>,
  options: { delayMs?: number; validate?: (value: T) => string | null } = {},
): { state: SaveState; change: (value: T) => void; flush: () => void } {
  const [state, setState] = useState<SaveState>({ phase: 'idle' });
  // 最新的 save／validate，不必因為它們換了身分就重建存檔器（會丟掉排隊的那筆）。
  const saveRef = useRef(save);
  saveRef.current = save;
  const validateRef = useRef(options.validate);
  validateRef.current = options.validate;
  const delayMs = options.delayMs ?? AUTOSAVE_DELAY_MS;

  const saver = useMemo(() => createAutosaver<T>({
    delayMs,
    save: (value) => saveRef.current(value),
    validate: (value) => validateRef.current?.(value) ?? null,
    onState: setState,
  }), [delayMs]);

  useEffect(() => {
    const onPageHide = (): void => { void saver.flush(); };
    window.addEventListener('pagehide', onPageHide);
    return () => {
      window.removeEventListener('pagehide', onPageHide);
      void saver.dispose();
    };
  }, [saver]);

  return {
    state,
    change: saver.change,
    flush: () => { void saver.flush(); },
  };
}
