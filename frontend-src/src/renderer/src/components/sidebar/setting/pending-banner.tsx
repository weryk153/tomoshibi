// 抽屜頂端：「有 N 項變更還沒生效」＋重新載入。後端記清單（重新整理頁面也還在），
// 重新載入成功後後端清空，下一次拉就消失。直播中不能重新載入（後端會拒絕，
// 而且重新載入會先關麥克風、打斷她）：按鈕停用並說明原因，清單保留到直播結束。
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { useWebSocket } from '@/context/websocket-context';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import { fetchPending, pendingLabelKeys } from '@/api/pending.ts';
import { useStream } from '@/context/stream-context';
import { useAiState } from '@/context/ai-state-context';

const POLL_MS = 3000;

export function PendingBanner({ active }: { active: boolean }): JSX.Element | null {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { reloadCharacter } = useSwitchCharacter();
  const [keys, setKeys] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const { live } = useStream();
  const { aiState } = useAiState();

  const refresh = useCallback(async () => {
    const result = await fetchPending(baseUrl);
    if (result.ok) setKeys(result.data.pending);
  }, [baseUrl]);

  useEffect(() => {
    if (!active) return undefined;
    void refresh();
    const timer = setInterval(() => { void refresh(); }, POLL_MS);
    return () => clearInterval(timer);
  }, [active, refresh]);

  if (keys.length === 0) return null;
  return (
    <div className="mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          className="text-left text-amber-200"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {t('settings.pending.count', { count: keys.length })}
        </button>
        <Button
          size="xs"
          tone="orange"
          onClick={reloadCharacter}
          disabled={live || aiState === 'loading'}
          loading={aiState === 'loading'}
        >
          {t('settings.pending.reload')}
        </Button>
      </div>
      {live && <p className="mt-1 text-xs text-amber-100/80">{t('settings.pending.liveBlocked')}</p>}
      {open && (
        <ul className="mt-2 list-disc pl-5 text-xs text-amber-100/80">
          {pendingLabelKeys(keys).map((key, index) => (
            <li key={`${key}-${index}`}>{t(key)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
