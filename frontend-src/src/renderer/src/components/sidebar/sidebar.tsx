/* eslint-disable react/require-default-props */
import { Box, Button, Menu } from '@chakra-ui/react';
import { FiSettings, FiClock, FiPlus, FiChevronLeft, FiChevronRight, FiUsers, FiLayers, FiMessageCircle } from 'react-icons/fi';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { sidebarStyles } from './sidebar-styles';
import SettingUI from './setting/setting-ui';
import ChatHistoryPanel from './chat-history-panel';
import BottomTab from './bottom-tab';
import HistoryDrawer from './history-drawer';
import { useSidebar } from '@/hooks/sidebar/use-sidebar';
import GroupDrawer from './group-drawer';
import Footer from '../footer/footer';
import { ModeType } from '@/context/mode-context';
import { useConfig } from '@/context/character-config-context';

const ModeMenu = memo(({ setMode, currentMode, isElectron }: {
  setMode: (mode: ModeType) => void
  currentMode: ModeType
  isElectron: boolean
}) => {
  const { t } = useTranslation();
  return (
  <Menu.Root>
    <Menu.Trigger
      as={Button}
      aria-label={t('sidebar.modeMenu')}
      title={t('sidebar.modeMenu')}
      {...sidebarStyles.sidebar.headerButton}
    >
      <FiLayers />
    </Menu.Trigger>
    <Menu.Positioner>
      <Menu.Content>
        <Menu.RadioItemGroup value={currentMode}>
          <Menu.RadioItem value="window" onClick={() => setMode('window')}>
            <Menu.ItemIndicator />
            {t('sidebar.windowMode')}
          </Menu.RadioItem>
          <Menu.RadioItem
            value="pet"
            onClick={() => {
              if (isElectron) {
                setMode('pet');
              }
            }}
            disabled={!isElectron}
            // 用瀏覽器開前台時這一項是停用的。沒有這行說明，使用者只會看到一個
            // 點不動的選項，不知道是壞了還是不適用。
            title={!isElectron ? t('sidebar.petModeDesktopOnly') : undefined}
          >
            <Menu.ItemIndicator />
            {t('sidebar.petMode')}
          </Menu.RadioItem>
        </Menu.RadioItemGroup>
      </Menu.Content>
    </Menu.Positioner>
  </Menu.Root>
  );
});

ModeMenu.displayName = 'ModeMenu';

export function AppHeader({ isCollapsed, onToggle }: {
  isCollapsed: boolean; onToggle: () => void;
}): JSX.Element {
  const { t } = useTranslation();
  const { settingsOpen, onSettingsOpen, onSettingsClose, setMode, currentMode, isElectron } = useSidebar();
  const toggleLabel = t(isCollapsed ? 'sidebar.expandPanel' : 'sidebar.collapsePanel');
  return (
    <header className="moonlight-header">
      <div className="moonlight-brand">tomoshibi</div>
      <Box display="flex" gap="1" alignItems="center">
        <Button onClick={onSettingsOpen} aria-label={t('common.settings')} title={t('common.settings')} {...sidebarStyles.sidebar.headerButton}><FiSettings /></Button>
        <GroupDrawer><Button aria-label={t('sidebar.group')} title={t('sidebar.group')} {...sidebarStyles.sidebar.headerButton}><FiUsers /></Button></GroupDrawer>
        <ModeMenu setMode={setMode} currentMode={currentMode} isElectron={isElectron} />
        <Button onClick={onToggle} aria-label={toggleLabel} title={toggleLabel} aria-expanded={!isCollapsed} {...sidebarStyles.sidebar.headerButton}>
          {isCollapsed ? <FiChevronLeft /> : <FiChevronRight />}
        </Button>
      </Box>
      {settingsOpen && <SettingUI open={settingsOpen} onClose={onSettingsClose} onToggle={onToggle} />}
    </header>
  );
}

function Sidebar({ isCollapsed = false }: { isCollapsed?: boolean }): JSX.Element {
  const { t } = useTranslation();
  const { createNewHistory } = useSidebar();
  const { confName } = useConfig();
  // Keep the same component tree across collapse and screen sizes: drafts,
  // queued messages and active media streams remain available when reopened.
  return (
    <Box height="100%" minH="0" display={isCollapsed ? 'none' : 'flex'} flexDirection="column">
      <div className="moonlight-chat-header">
        <FiMessageCircle aria-hidden="true" />
        <span>{confName || 'tomoshibi'}</span>
        <Box display="flex" ml="auto" gap="1">
          <HistoryDrawer><Button aria-label={t('sidebar.history')} title={t('sidebar.history')} {...sidebarStyles.sidebar.headerButton}><FiClock /></Button></HistoryDrawer>
          <Button onClick={createNewHistory} aria-label={t('sidebar.newChat')} title={t('sidebar.newChat')} {...sidebarStyles.sidebar.headerButton}><FiPlus /></Button>
        </Box>
      </div>
      <BottomTab />
      <Box flex="1" minH="0" display="flex" flexDirection="column"><ChatHistoryPanel /></Box>
      <Footer />
    </Box>
  );
}
export default Sidebar;
