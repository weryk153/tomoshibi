/* eslint-disable */
import { useEffect, useState } from 'react'
import { Box, Button, Tabs } from '@chakra-ui/react'
import { FiCamera, FiMonitor, FiGlobe, FiChevronDown } from 'react-icons/fi'
import { useTranslation } from 'react-i18next'
import { sidebarStyles } from './sidebar-styles'
import CameraPanel from './camera-panel'
import ScreenPanel from './screen-panel'
import BrowserPanel from './browser-panel'
import { useCamera } from '@/context/camera-context'
import { useScreenCaptureContext } from '@/context/screen-capture-context'
import { useBrowser } from '@/context/browser-context'

type MediaTab = 'camera' | 'screen' | 'browser'

// 右欄頂端的攝影機／螢幕／瀏覽器。平常收起來只剩一列分頁，聊天紀錄才有地方；
// 點分頁就展開，開了攝影機、螢幕或瀏覽器時自動展開到那一頁。
// 收起只是藏起來（display: none），面板不卸載：攝影機與螢幕的串流照樣在跑。
function BottomTab(): JSX.Element {
  const { t } = useTranslation();
  const [tab, setTab] = useState<MediaTab>('camera');
  const [expanded, setExpanded] = useState(false);
  const { isStreaming: cameraOn } = useCamera();
  const { isStreaming: screenOn } = useScreenCaptureContext();
  const { browserViewData } = useBrowser();
  const browserOn = Boolean(browserViewData);

  useEffect(() => {
    if (cameraOn) { setTab('camera'); setExpanded(true); }
  }, [cameraOn]);
  useEffect(() => {
    if (screenOn) { setTab('screen'); setExpanded(true); }
  }, [screenOn]);
  useEffect(() => {
    if (browserOn) { setTab('browser'); setExpanded(true); }
  }, [browserOn]);

  const toggleLabel = t(expanded ? 'sidebar.collapseMedia' : 'sidebar.expandMedia');

  return (
    <Tabs.Root
      value={tab}
      onValueChange={(details) => setTab(details.value as MediaTab)}
      variant="plain"
      {...sidebarStyles.bottomTab.container}
    >
      <Box display="flex" alignItems="center">
        <Tabs.List {...sidebarStyles.bottomTab.list} flex="1">
          <Tabs.Trigger value="camera" onClick={() => setExpanded(true)} {...sidebarStyles.bottomTab.trigger}>
            <FiCamera />
            {t('sidebar.camera')}
          </Tabs.Trigger>
          <Tabs.Trigger value="screen" onClick={() => setExpanded(true)} {...sidebarStyles.bottomTab.trigger}>
            <FiMonitor />
            {t('sidebar.screen')}
          </Tabs.Trigger>
          <Tabs.Trigger value="browser" onClick={() => setExpanded(true)} {...sidebarStyles.bottomTab.trigger}>
            <FiGlobe />
            {t('sidebar.browser')}
          </Tabs.Trigger>
        </Tabs.List>
        <Button
          {...sidebarStyles.sidebar.headerButton}
          aria-label={toggleLabel}
          aria-expanded={expanded}
          title={toggleLabel}
          onClick={() => setExpanded(!expanded)}
        >
          <FiChevronDown
            aria-hidden="true"
            style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
          />
        </Button>
      </Box>

      <Box display={expanded ? 'block' : 'none'}>
        <Tabs.Content value="camera">
          <CameraPanel />
        </Tabs.Content>

        <Tabs.Content value="screen">
          <ScreenPanel />
        </Tabs.Content>

        <Tabs.Content value="browser">
          <BrowserPanel />
        </Tabs.Content>
      </Box>
    </Tabs.Root>
  );
}

export default BottomTab
