/* eslint-disable react/require-default-props */
import { Box, Button, Menu, Text } from '@chakra-ui/react';
import {
  FiSettings, FiClock, FiPlus, FiChevronLeft, FiChevronRight, FiUsers, FiLayers
} from 'react-icons/fi';
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

// Type definitions
interface SidebarProps {
  isCollapsed?: boolean
  onToggle: () => void
}

interface HeaderButtonsProps {
  onSettingsOpen: () => void
  onNewHistory: () => void
  setMode: (mode: ModeType) => void
  currentMode: 'window' | 'pet'
  isElectron: boolean
}

// 收合：展開時是按鈕列最右邊的一顆（›），收起後是左緣的一整條把手（‹）。
// 窄螢幕聊天在舞台下方，不收合。
const CollapseButton = memo(({ onCollapse }: { onCollapse: () => void }) => {
  const { t } = useTranslation();
  const label = t('sidebar.collapsePanel');
  return (
    <Button
      type="button"
      {...sidebarStyles.sidebar.headerButton}
      display={{ base: 'none', md: 'inline-flex' }}
      aria-label={label}
      aria-expanded
      title={label}
      onClick={onCollapse}
    >
      <FiChevronRight aria-hidden="true" />
    </Button>
  );
});

CollapseButton.displayName = 'CollapseButton';

const ExpandRail = memo(({ onExpand }: { onExpand: () => void }) => {
  const { t } = useTranslation();
  const label = t('sidebar.expandPanel');
  return (
    <Button
      type="button"
      variant="ghost"
      {...sidebarStyles.sidebar.collapsedRail}
      aria-label={label}
      aria-expanded={false}
      title={label}
      onClick={onExpand}
    >
      <FiChevronLeft aria-hidden="true" />
    </Button>
  );
});

ExpandRail.displayName = 'ExpandRail';

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

const HeaderButtons = memo(({
  onSettingsOpen, onNewHistory, setMode, currentMode, isElectron,
}: HeaderButtonsProps) => {
  const { t } = useTranslation();
  return (
    <Box display="flex" gap={1}>
      <Button
        onClick={onSettingsOpen}
        aria-label={t('common.settings')}
        title={t('common.settings')}
        {...sidebarStyles.sidebar.headerButton}
      >
        <FiSettings />
      </Button>

      <GroupDrawer>
        <Button
          aria-label={t('sidebar.group')}
          title={t('sidebar.group')}
          {...sidebarStyles.sidebar.headerButton}
        >
          <FiUsers />
        </Button>
      </GroupDrawer>

      <HistoryDrawer>
        <Button
          aria-label={t('sidebar.history')}
          title={t('sidebar.history')}
          {...sidebarStyles.sidebar.headerButton}
        >
          <FiClock />
        </Button>
      </HistoryDrawer>

      <Button
        onClick={onNewHistory}
        aria-label={t('sidebar.newChat')}
        title={t('sidebar.newChat')}
        {...sidebarStyles.sidebar.headerButton}
      >
        <FiPlus />
      </Button>

      <ModeMenu setMode={setMode} currentMode={currentMode} isElectron={isElectron} />
    </Box>
  );
});

HeaderButtons.displayName = 'HeaderButtons';

const SidebarContent = memo(({
  onCollapse,
  onSettingsOpen,
  onNewHistory,
  setMode,
  currentMode,
  isElectron
}: HeaderButtonsProps & { onCollapse: () => void }) => (
  <Box {...sidebarStyles.sidebar.content}>
    <Box {...sidebarStyles.sidebar.header}>
      <HeaderButtons
        onSettingsOpen={onSettingsOpen}
        onNewHistory={onNewHistory}
        setMode={setMode}
        currentMode={currentMode}
        isElectron={isElectron}
      />
      {/* 品牌記號，只是裝飾。 */}
      <Text
        aria-hidden="true"
        ml="auto"
        mr="1"
        fontFamily="mono"
        fontSize="11px"
        fontWeight="500"
        letterSpacing="0.14em"
        color="blue.500"
        userSelect="none"
      >
        TMSB
      </Text>
      <CollapseButton onCollapse={onCollapse} />
    </Box>
    {/* 像直播的聊天室：上面攝影機／螢幕（平常收起），中間聊天紀錄，最下面輸入框。 */}
    <BottomTab />
    <Box flex="1" minH="0" display="flex" flexDirection="column">
      <ChatHistoryPanel />
    </Box>
    <Footer />
  </Box>
));

SidebarContent.displayName = 'SidebarContent';

// Main component
function Sidebar({ isCollapsed = false, onToggle }: SidebarProps): JSX.Element {
  const {
    settingsOpen,
    onSettingsOpen,
    onSettingsClose,
    createNewHistory,
    setMode,
    currentMode,
    isElectron,
  } = useSidebar();

  return (
    <Box {...sidebarStyles.sidebar.container(isCollapsed)}>
      {isCollapsed && <ExpandRail onExpand={onToggle} />}


      {/* 收起時只藏起來、不卸載：輸入框裡排隊中的訊息、聊天紀錄的捲動位置都在
          元件裡，卸載就沒了。窄螢幕不收合（收合鈕也不顯示）。 */}
      <Box
        flex="1"
        minH="0"
        flexDirection="column"
        display={isCollapsed ? { base: 'flex', md: 'none' } : 'flex'}
      >
        <SidebarContent
          onCollapse={onToggle}
          onSettingsOpen={onSettingsOpen}
          onNewHistory={createNewHistory}
          setMode={setMode}
          currentMode={currentMode}
          isElectron={isElectron}
        />
      </Box>

      {settingsOpen && (
        <SettingUI
          open={settingsOpen}
          onClose={onSettingsClose}
          onToggle={onToggle}
        />
      )}
    </Box>
  );
}

export default Sidebar;
