// 設定抽屜的殼：Ark Dialog（透過 ui/tw/drawer）+ Ark Tabs + Tailwind。
//
// 分頁清單改成資料驅動。原本 14 個 Trigger 與 14 個 Content 各自手寫，兩份清單
// 要靠人工維持同步——加一個分頁要改兩個地方、順序也得自己對齊，而漏掉時不會有
// 任何錯誤，只是那個分頁點不到或點了空白。現在兩者都從 TABS 生出來。
//
// lazyMount：分頁內容第一次被切到才掛載。Chakra 的 Tabs 是一開啟抽屜就把 14 個
// 分頁全部掛載，所以任何一個分頁在渲染時丟例外，整個抽屜就是一片黑——這正是
// __APP_VERSION__ 那次事故的放大機制（見 build-defines.ts）。掛載過就留著
// （沒有 unmountOnExit），切回去時狀態還在。

import { useState, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs as ArkTabs } from '@ark-ui/react';
import { Drawer, DRAWER_PX } from '@/components/ui/tw/drawer';
import { Button, cx } from '@/components/ui/tw/primitives';

import General from './general';
import Characters from './characters';
import Personas from './personas';
import LLM from './llm';
import Live2D from './live2d';
import ASR from './asr';
import TTS from './tts';
import Agent from './agent';
import Memory from './memory';
import Perf from './perf';
import RemoteAccess from './remote-access';
import About from './about';
import Performances from './performances';
import Scenes from './scenes';

interface SettingUIProps {
  open: boolean;
  onClose: () => void;
  onToggle: () => void;
}

/** 每個分頁的 render 拿得到的東西。
 *
 * onCancel 現在只剩「一般」分頁在用，而且只管連線位址那一小塊草稿——其餘所有
 * 控制項都是改了就生效，沒有草稿可還原。 */
interface TabRenderArgs {
  onCancel: (handler: () => void) => () => void;
  active: boolean;
}

type TabGroup = 'companion' | 'stage' | 'intelligence' | 'system';

interface SettingsTab {
  value: string;
  labelKey: string;
  group: TabGroup;
  render: (a: TabRenderArgs) => JSX.Element;
}

// 14 個入口不再排成一堵三列文字牆。順序按使用者心智模型分組：先是陪伴角色，
// 再是舞台外觀、AI／語音，最後才是系統工具。桌面版由這個 group 生出左側導覽，
// 手機版則隱藏群組標題、退回單列橫向分頁。
const TABS: SettingsTab[] = [
  { value: 'general', labelKey: 'settings.tabs.general', group: 'companion', render: ({ onCancel }) => <General onCancel={onCancel} /> },
  { value: 'characters', labelKey: 'settings.tabs.characters', group: 'companion', render: () => <Characters /> },
  { value: 'personas', labelKey: 'settings.tabs.personas', group: 'companion', render: () => <Personas /> },
  { value: 'live2d', labelKey: 'settings.tabs.avatar', group: 'stage', render: () => <Live2D /> },
  { value: 'performances', labelKey: 'settings.tabs.performances', group: 'stage', render: () => <Performances /> },
  { value: 'scenes', labelKey: 'settings.tabs.scenes', group: 'stage', render: () => <Scenes /> },
  { value: 'llm', labelKey: 'settings.tabs.llm', group: 'intelligence', render: () => <LLM /> },
  { value: 'asr', labelKey: 'settings.tabs.asr', group: 'intelligence', render: ({ active }) => <ASR active={active} /> },
  { value: 'tts', labelKey: 'settings.tabs.tts', group: 'intelligence', render: ({ active }) => <TTS active={active} /> },
  { value: 'agent', labelKey: 'settings.tabs.agent', group: 'intelligence', render: () => <Agent /> },
  { value: 'memory', labelKey: 'settings.tabs.memory', group: 'intelligence', render: ({ active }) => <Memory active={active} /> },
  { value: 'perf', labelKey: 'settings.tabs.perf', group: 'system', render: () => <Perf /> },
  { value: 'remoteAccess', labelKey: 'settings.remoteAccess.tab', group: 'system', render: ({ active }) => <RemoteAccess active={active} /> },
  { value: 'about', labelKey: 'settings.tabs.about', group: 'system', render: () => <About /> },
];

const GROUPS: TabGroup[] = ['companion', 'stage', 'intelligence', 'system'];

function SettingUI({ open, onClose }: SettingUIProps): JSX.Element {
  const { t } = useTranslation();
  const [cancelHandlers, setCancelHandlers] = useState<(() => void)[]>([]);
  const [activeTab, setActiveTab] = useState('general');

  const handleCancelCallback = useCallback((handler: () => void) => {
    setCancelHandlers((prev) => [...prev, handler]);
    return (): void => {
      setCancelHandlers((prev) => prev.filter((h) => h !== handler));
    };
  }, []);

  const handleCancel = useCallback((): void => {
    cancelHandlers.forEach((handler) => handler());
    onClose();
  }, [cancelHandlers, onClose]);

  const contents = useMemo(
    () => TABS.map((tab) => (
      <ArkTabs.Content
        key={tab.value}
        value={tab.value}
        className={cx('py-4 outline-none', DRAWER_PX)}
      >
        {tab.render({ onCancel: handleCancelCallback, active: activeTab === tab.value })}
      </ArkTabs.Content>
    )),
    [handleCancelCallback, activeTab],
  );

  return (
    <Drawer
      open={open}
      // 關閉一律走 handleCancel：各分頁註冊的還原邏輯要跑，草稿才會被丟掉。
      onOpenChange={(next) => { if (!next) handleCancel(); }}
      placement="start"
      size="wide"
      // 透明遮罩：Live2D 與背景分頁調的就是右邊畫布，不能把它調暗。
      backdrop="clear"
      title={t('common.settings')}
      footer={(
        <Button variant="outline" tone="gray" onClick={handleCancel}>
          {t('common.close')}
        </Button>
      )}
    >
      <ArkTabs.Root
        value={activeTab}
        onValueChange={(details) => setActiveTab(details.value)}
        lazyMount
        className="flex min-h-0 flex-1 flex-col sm:flex-row"
      >
        <ArkTabs.List
          className={cx(
            'flex shrink-0 gap-1 overflow-x-auto border-b border-walpha-200 px-4 pb-3',
            'sm:w-[156px] sm:flex-col sm:overflow-y-auto sm:border-b-0 sm:border-r sm:px-3 sm:py-3',
          )}
          aria-label={t('common.settings')}
        >
          {GROUPS.map((group) => (
            <div key={group} className="contents sm:block">
              <span className="mb-1 mt-3 hidden px-2 text-[11px] font-semibold uppercase tracking-wider text-walpha-400 sm:block">
                {t(`settings.groups.${group}`)}
              </span>
              {TABS.filter((tab) => tab.group === group).map((tab) => (
                <ArkTabs.Trigger
                  key={tab.value}
                  value={tab.value}
                  className={cx(
                    'shrink-0 cursor-pointer rounded-md px-3 py-2 text-left text-sm outline-none transition-colors',
                    'text-walpha-600 hover:bg-walpha-100 hover:text-white',
                    'data-[selected]:bg-blue-500/15 data-[selected]:font-semibold data-[selected]:text-blue-200',
                    'focus-visible:ring-2 focus-visible:ring-blue-500/40',
                    'sm:w-full',
                  )}
                >
                  {t(tab.labelKey)}
                </ArkTabs.Trigger>
              ))}
            </div>
          ))}
        </ArkTabs.List>
        {/* 捲動發生在這一層，不是整個抽屜——分頁列要固定在上方。 */}
        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">{contents}</div>
      </ArkTabs.Root>
    </Drawer>
  );
}

export default SettingUI;
