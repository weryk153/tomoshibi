// 抽屜頂端：「有 N 項變更還沒生效」＋重新載入。後端記清單（重新整理頁面也還在），
// 重新載入成功後後端清空，下一次拉就消失。直播中不能重新載入（後端會拒絕，
// 而且重新載入會先關麥克風、打斷她）：按鈕停用並說明原因，清單保留到直播結束。
//
// 兩種生效方式：大多數變更重新載入就好；少數（綁定位址）要重啟後端，重新載入
// 不會清掉它們。有要重啟的項目時按鈕換成「重新啟動後端」：桌面版由 app 自己
// 重啟它起的後端；網頁版（或後端不是 app 起的）顯示終端機指令。
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { useWebSocket } from '@/context/websocket-context';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import {
  fetchPending, hasReloadItems, pendingAction, pendingLabelKeys, type DesktopRestart,
} from '@/api/pending.ts';
import { useStream } from '@/context/stream-context';
import { useAiState } from '@/context/ai-state-context';
import { wsService } from '@/services/websocket-service';

const POLL_MS = 3000;

export function PendingBanner({ active }: { active: boolean }): JSX.Element | null {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { reloadCharacter } = useSwitchCharacter();
  const [keys, setKeys] = useState<string[]>([]);
  const [needsRestart, setNeedsRestart] = useState(false);
  const [restarting, setRestarting] = useState(false);
  // 後端不是這個 app 起的（開發模式、沿用別人開著的）：改顯示終端機指令。
  const [notManaged, setNotManaged] = useState(false);
  // 桌面版重啟失敗：後端可能已經停了。說失敗、給記錄檔位置與重試，不叫人去開終端機。
  const [restartFailure, setRestartFailure] = useState<{ logPath?: string } | null>(null);
  const [open, setOpen] = useState(false);
  const { live } = useStream();
  const { aiState } = useAiState();

  const refresh = useCallback(async () => {
    const result = await fetchPending(baseUrl);
    if (result.ok) {
      setKeys(result.data.pending);
      setNeedsRestart(Boolean(result.data.needs_restart));
      if (!result.data.needs_restart) setRestartFailure(null);
    }
  }, [baseUrl]);

  useEffect(() => {
    if (!active) return undefined;
    void refresh();
    const timer = setInterval(() => { void refresh(); }, POLL_MS);
    return () => clearInterval(timer);
  }, [active, refresh]);

  const desktop: DesktopRestart = !window.api?.restartBackend || notManaged
    ? 'unavailable'
    : restartFailure ? 'failed' : 'available';
  const action = pendingAction(needsRestart, desktop);

  const restart = async (): Promise<void> => {
    if (!window.api?.restartBackend) return;
    setRestarting(true);
    setRestartFailure(null);
    const result = await window.api.restartBackend();
    setRestarting(false);
    if (result.ok) {
      // 後端剛重開：連線不等退避那一輪，馬上重連。
      wsService.reconnectNow();
      void refresh();
    } else if (result.reason === 'not-managed') {
      setNotManaged(true);
    } else {
      setRestartFailure({ logPath: result.logPath });
    }
  };

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
        {(action === 'reload' || (action !== 'restart-desktop' && hasReloadItems(keys))) && (
          <Button
            size="xs"
            tone="orange"
            onClick={reloadCharacter}
            disabled={live || aiState === 'loading'}
            loading={aiState === 'loading'}
          >
            {t('settings.pending.reload')}
          </Button>
        )}
        {(action === 'restart-desktop' || action === 'restart-failed') && (
          <Button
            size="xs"
            tone="orange"
            onClick={() => { void restart(); }}
            disabled={live || restarting}
            loading={restarting}
          >
            {action === 'restart-failed' ? t('settings.pending.retry') : t('settings.pending.restart')}
          </Button>
        )}
      </div>
      {action === 'restart-failed' && (
        <p className="mt-1 text-xs text-red-200">
          {t('settings.pending.restartFailed', { path: restartFailure?.logPath ?? '' })}
        </p>
      )}
      {action === 'restart-command' && (
        <p className="mt-1 text-xs text-amber-100/80">{t('settings.pending.restartCommand')}</p>
      )}
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
