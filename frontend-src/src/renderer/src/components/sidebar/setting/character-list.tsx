// 角色頁左邊：每個角色一列，點了右邊就換成她。正在用的那個標出來；新增在最上面。
// 切換、刪除在右邊（她的設定頂端），清單只負責「選誰」。
import { useTranslation } from 'react-i18next';
import { Button, cx } from '@/components/ui/tw/primitives';
import type { CharacterRecord } from '@/api/characters.ts';
import { isActiveCharacter } from '@/utils/character-page';

export interface CharacterListProps {
  characters: CharacterRecord[]
  selectedFilename: string | null
  activeConfUid: string
  creating: boolean
  onSelect: (record: CharacterRecord) => void
  onCreate: () => void
  onRefresh: () => void
}

export function CharacterList({
  characters, selectedFilename, activeConfUid, creating, onSelect, onCreate, onRefresh,
}: CharacterListProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <nav className="flex shrink-0 flex-col gap-1 md:w-44" aria-label={t('settings.tabs.characters')}>
      <div className="mb-2 flex gap-2">
        <Button size="xs" tone="blue" variant={creating ? 'solid' : 'outline'} onClick={onCreate}>
          {t('settings.characters.add')}
        </Button>
        <Button size="xs" variant="ghost" onClick={onRefresh}>
          {t('settings.characters.refresh')}
        </Button>
      </div>
      {characters.map((record) => {
        const selected = !creating && record.filename === selectedFilename;
        return (
          <button
            key={record.filename}
            type="button"
            onClick={() => onSelect(record)}
            aria-current={selected ? 'true' : undefined}
            className={cx(
              'flex items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
              selected
                ? 'bg-blue-500/15 font-semibold text-blue-200'
                : 'text-walpha-700 hover:bg-walpha-100 hover:text-white',
            )}
          >
            <span className="truncate">{record.conf_name || record.filename}</span>
            {isActiveCharacter(record, activeConfUid) && (
              <span className="shrink-0 text-[11px] text-green-300">{t('settings.characters.activeBadge')}</span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
