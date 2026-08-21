// 聊天記錄抽屜。Ark Dialog + Tailwind（見 components/ui/tw/drawer.tsx）。
//
// 這是遷移過程中第一個真正用到 Dialog 的元件——先前四個設定分頁只碰了表單控制
// 項。Ark 的 Dialog 就是 Chakra v3 Drawer 底下跑的同一顆狀態機（zag-js），所以
// 焦點陷阱、Escape 關閉、點遮罩關閉、開啟時鎖捲動這些行為都不需要重寫。

import { FiTrash2 } from 'react-icons/fi';
import { formatDistanceToNow } from 'date-fns';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { Drawer, DrawerCloseAction } from '@/components/ui/tw/drawer';
import { Button, cx } from '@/components/ui/tw/primitives';
import { useHistoryDrawer } from '@/hooks/sidebar/use-history-drawer';
import { HistoryInfo } from '@/context/websocket-context';

interface HistoryDrawerProps {
  children: React.ReactNode;
}

interface HistoryItemProps {
  isSelected: boolean;
  latestMessage: { content: string; timestamp: string | null };
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
  isDeleteDisabled: boolean;
}

const HistoryItem = memo(({
  isSelected,
  latestMessage,
  onSelect,
  onDelete,
  isDeleteDisabled,
}: HistoryItemProps): JSX.Element => {
  const { t } = useTranslation();
  return (
    <div
      className={cx(
        'mb-4 cursor-pointer rounded-md p-3 transition-colors',
        isSelected
          ? 'border-l-[3px] border-blue-500 bg-walpha-200'
          : 'bg-white/5 hover:bg-walpha-100',
      )}
      onClick={onSelect}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-sm text-white/70">
          {latestMessage.timestamp
            ? formatDistanceToNow(new Date(latestMessage.timestamp), { addSuffix: true })
            : t('history.noMessages')}
        </span>
        <Button
          size="xs"
          variant="ghost"
          tone="red"
          onClick={onDelete}
          disabled={isDeleteDisabled}
          aria-label={t('history.deleteHistory')}
        >
          <FiTrash2 />
        </Button>
      </div>
      {latestMessage.content && (
        // line-clamp-2 取代 Chakra 的 noOfLines={2}。兩者產出的 CSS 是同一組
        // -webkit-line-clamp 宣告。
        <p className="line-clamp-2 text-sm text-white/90">{latestMessage.content}</p>
      )}
    </div>
  );
});

HistoryItem.displayName = 'HistoryItem';

function HistoryDrawer({ children }: HistoryDrawerProps): JSX.Element {
  const { t } = useTranslation();
  const {
    open,
    setOpen,
    historyList,
    currentHistoryUid,
    fetchAndSetHistory,
    deleteHistory,
    getLatestMessageContent,
  } = useHistoryDrawer();

  return (
    <Drawer
      open={open}
      onOpenChange={setOpen}
      placement="start"
      title={t('history.chatHistoryList')}
      trigger={children}
      footer={(
        <DrawerCloseAction>
          <Button variant="outline" tone="gray">{t('common.close')}</Button>
        </DrawerCloseAction>
      )}
    >
      <div className="flex-1 overflow-y-auto px-4 py-2">
        {historyList.map((history: HistoryInfo) => (
          <HistoryItem
            key={history.uid}
            isSelected={currentHistoryUid === history.uid}
            latestMessage={getLatestMessageContent(history)}
            onSelect={() => fetchAndSetHistory(history.uid)}
            onDelete={(e) => {
              e.stopPropagation();
              deleteHistory(history.uid);
            }}
            isDeleteDisabled={currentHistoryUid === history.uid}
          />
        ))}
      </div>
    </Drawer>
  );
}

export default HistoryDrawer;
