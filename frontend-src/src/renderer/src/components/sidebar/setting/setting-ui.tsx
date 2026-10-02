// 設定抽屜的殼：Ark Dialog（透過 ui/tw/drawer）+ Ark Tabs + Tailwind。
//
// 七個分頁（規格 docs/superpowers/specs/2026-10-01-settings-redesign-design.md
// 「分頁」一節）：角色、對話、舞台、直播、模型、效能、系統。跟角色走的設定只在
// 角色頁；其他分頁只放跟角色無關的，每一頁由幾個各管一件事的元件疊成，用
// SettingSection 分區。順序與標籤在 settings-tabs.ts（可測），內容在這裡。
//
// lazyMount：分頁內容第一次被切到才掛載。一開啟抽屜就把所有分頁全部掛載的話，
// 任何一個分頁在渲染時丟例外，整個抽屜就是一片黑——這正是 __APP_VERSION__
// 那次事故的放大機制（見 build-defines.ts）。掛載過就留著（沒有
// unmountOnExit），切回去時狀態還在。

import { useState, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Tabs as ArkTabs } from '@ark-ui/react';
import { Stack } from '@chakra-ui/react';
import type { TFunction } from 'i18next';
import { Drawer, DRAWER_PX } from '@/components/ui/tw/drawer';
import { Button, cx } from '@/components/ui/tw/primitives';

import Characters from './characters';
import LLM from './llm';
import ASR from './asr';
import TTS from './tts';
import Agent from './agent';
import You from './you';
import Perf from './perf';
import RemoteAccess from './remote-access';
import About from './about';
import Performances from './performances';
import Scenes from './scenes';
import Stream from './stream';
import StageDisplay from './stage-display';
import SystemBasics from './system-basics';
import ModelExtras from './model-extras';
import EngineNumbers from './engine-numbers';
import CanvasInteraction from './canvas-interaction';
import StageEffects from './stage-effects';
import { SettingSection } from './setting-section';
import { PendingBanner } from './pending-banner';
import { SETTINGS_TABS, DEFAULT_SETTINGS_TAB, type SettingsTabId } from './settings-tabs';

interface SettingUIProps {
  open: boolean;
  onClose: () => void;
  onToggle: () => void;
}

/** 每個分頁的 render 拿得到的東西。
 *
 * onCancel 只剩系統頁的連線位址在用——其餘所有控制項都是改了就生效，沒有草稿
 * 可還原。active 給要在「被看見時」重抓現值的元件。 */
interface TabRenderArgs {
  onCancel: (handler: () => void) => () => void;
  active: boolean;
  t: TFunction;
}

// 自己有標題的元件（場景、演出、語音合成、遠端連線、關於……）不再給區塊標題，
// 免得同一個字出現兩次。
const RENDERS: Record<SettingsTabId, (a: TabRenderArgs) => JSX.Element> = {
  character: () => <Characters />,
  conversation: ({ active, t }) => (
    <Stack gap={6}>
      <SettingSection title={t('settings.tabs.agent')}><Agent /></SettingSection>
      <SettingSection><You active={active} /></SettingSection>
    </Stack>
  ),
  stage: ({ t }) => (
    <Stack gap={6}>
      <SettingSection title={t('settings.stage.display')}><StageDisplay /></SettingSection>
      <SettingSection><Scenes /></SettingSection>
      <SettingSection><Performances /></SettingSection>
      <SettingSection><StageEffects /></SettingSection>
      <SettingSection title={t('settings.stage.canvas')}><CanvasInteraction /></SettingSection>
    </Stack>
  ),
  stream: ({ active }) => <Stream active={active} />,
  models: ({ active, t }) => (
    <Stack gap={6}>
      <SettingSection title={t('settings.tabs.llm')}><LLM /></SettingSection>
      <SettingSection title={t('settings.models.extras')}><ModelExtras /></SettingSection>
      <SettingSection title={t('settings.tabs.asr')}><ASR active={active} /></SettingSection>
      <SettingSection><TTS active={active} /></SettingSection>
    </Stack>
  ),
  perf: ({ t }) => (
    <Stack gap={6}>
      <SettingSection><Perf /></SettingSection>
      <SettingSection title={t('settings.perf.engineNumbers')}><EngineNumbers /></SettingSection>
    </Stack>
  ),
  system: ({ onCancel, active }) => (
    <Stack gap={6}>
      <SettingSection><SystemBasics onCancel={onCancel} /></SettingSection>
      <SettingSection><RemoteAccess active={active} /></SettingSection>
      <SettingSection><About /></SettingSection>
    </Stack>
  ),
};

function SettingUI({ open, onClose }: SettingUIProps): JSX.Element {
  const { t } = useTranslation();
  const [cancelHandlers, setCancelHandlers] = useState<(() => void)[]>([]);
  const [activeTab, setActiveTab] = useState<SettingsTabId>(DEFAULT_SETTINGS_TAB);

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
    () => SETTINGS_TABS.map((tab) => (
      <ArkTabs.Content
        key={tab.id}
        value={tab.id}
        className={cx('py-4 outline-none', DRAWER_PX)}
      >
        {RENDERS[tab.id]({ onCancel: handleCancelCallback, active: activeTab === tab.id, t })}
      </ArkTabs.Content>
    )),
    [handleCancelCallback, activeTab, t],
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
      {/* 要重新載入才生效的變更集中在這裡，不再每頁各寫一句「重啟後生效」。 */}
      <PendingBanner active={open} />
      <ArkTabs.Root
        value={activeTab}
        onValueChange={(details) => setActiveTab(details.value as SettingsTabId)}
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
          {SETTINGS_TABS.map((tab) => (
            <ArkTabs.Trigger
              key={tab.id}
              value={tab.id}
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
        </ArkTabs.List>
        {/* 捲動發生在這一層，不是整個抽屜——分頁列要固定在上方。 */}
        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">{contents}</div>
      </ArkTabs.Root>
    </Drawer>
  );
}

export default SettingUI;
