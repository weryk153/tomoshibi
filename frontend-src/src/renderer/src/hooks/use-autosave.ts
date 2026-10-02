// createAutosaver 的 React 包裝：元件卸載（關抽屜、切分頁）時把還沒送的那筆送出去。
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

  useEffect(() => () => { void saver.dispose(); }, [saver]);

  return {
    state,
    change: saver.change,
    flush: () => { void saver.flush(); },
  };
}
