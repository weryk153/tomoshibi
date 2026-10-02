// 欄位旁的存檔狀態：儲存中、已儲存（兩秒後淡掉）、存不進去（留著直到下一次改）、
// 不合法的值為什麼不存。
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { SaveState } from '@/utils/autosave';
import { cx } from './primitives';

export function SaveStatus({ state }: { state: SaveState }): JSX.Element | null {
  const { t } = useTranslation();
  const [showSaved, setShowSaved] = useState(false);
  useEffect(() => {
    if (state.phase !== 'saved') return undefined;
    setShowSaved(true);
    const timer = setTimeout(() => setShowSaved(false), 2000);
    return () => clearTimeout(timer);
  }, [state]);

  let text: string | null = null;
  let tone = 'text-zinc-400';
  if (state.phase === 'saving') {
    text = t('common.saving');
  } else if (state.phase === 'saved' && showSaved) {
    text = t('common.savedShort');
    tone = 'text-emerald-400';
  } else if (state.phase === 'error') {
    text = t('common.saveFailed', { error: state.message ?? '' });
    tone = 'text-red-400';
  } else if (state.phase === 'invalid') {
    text = state.message ?? '';
    tone = 'text-amber-400';
  }
  if (!text) return null;
  return <span role="status" className={cx('text-xs', tone)}>{text}</span>;
}
