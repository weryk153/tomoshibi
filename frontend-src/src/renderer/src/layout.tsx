const isElectron = window.api !== undefined;

// 右欄（像直播的聊天室）：按鈕列、攝影機／螢幕、聊天紀錄、輸入框都在這一欄。
// 固定 440px 在常見縮放下吃掉快三分之一的瀏覽器寬度，所以跟著視窗縮放。
export const SIDEBAR_WIDTH = 'clamp(320px, 26vw, 400px)';
export const SIDEBAR_COLLAPSED_WIDTH = '32px';
// 窄螢幕（手機、平板直向）舞台在上、聊天在下：舞台佔的高度。
export const STAGE_MOBILE_HEIGHT = '42%';

const getAppHeight = () => {
  // App.tsx keeps --vh in sync with the *visible* viewport. Unlike a module-load
  // snapshot of window.innerHeight, this also follows browser chrome, the mobile
  // keyboard and window resizes, so the footer does not end up below the fold.
  return isElectron
    ? 'calc(var(--vh, 1vh) * 100 - 30px)'
    : 'calc(var(--vh, 1vh) * 100)';
};



export const layoutStyles = {
  appContainer: {
    width: '100vw',
    height: getAppHeight(),
    bg: 'gray.950',
    color: 'white',
    overflow: 'hidden',
    position: 'relative',
    display: 'flex',
    flexDirection: { base: 'column', md: 'row' },
    mt: isElectron ? '30px' : '0',
  },
  sidebar: {
    position: 'relative' as const,
    width: { base: '100%', md: SIDEBAR_WIDTH },
    height: { base: 'auto', md: '100%' },
    flex: { base: 1, md: 'none' },
    minHeight: 0,
    bg: 'gray.900',
    borderLeft: { base: 'none', md: '1px solid' },
    borderTop: { base: '1px solid', md: 'none' },
    borderColor: 'whiteAlpha.100',
    overflow: 'hidden',
    flexShrink: 0,
    transition: 'all 0.2s',
  },
  mainContent: {
    flex: { base: 'none', md: 1 },
    height: { base: STAGE_MOBILE_HEIGHT, md: '100%' },
    minHeight: 0,
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    width: '100%',
    overflow: 'hidden',
  },
  canvas: {
    position: 'relative',
    width: '100%',
    flex: 1,
    minHeight: 0,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    overflow: 'hidden',
    willChange: 'transform',
  },
  toggleButton: {
    position: 'absolute',
    left: 0,
    top: '50%',
    transform: 'translateY(-50%)',
    height: '60px',
    bg: 'whiteAlpha.100',
    _hover: { bg: 'whiteAlpha.200' },
    borderLeftRadius: 0,
    borderRightRadius: 'md',
    zIndex: 10,
  },
  sidebarToggleButton: {
    position: 'absolute',
    left: 0,
    top: '50%',
    transform: 'translateY(-50%)',
    height: '60px',
    bg: 'gray.800',
    borderLeftRadius: 0,
    borderRightRadius: 'md',
    zIndex: 10,
  },
  windowsTitleBar: {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100vw',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: '30px',
    backgroundColor: 'gray.800',
    paddingX: '10px',
    zIndex: 1000,
    css: { '-webkit-app-region': 'drag' },
  },
  macTitleBar: {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100vw',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '30px',
    backgroundColor: 'gray.800',
    zIndex: 1000,
    css: {
      '-webkit-app-region': 'drag',
      '-webkit-user-select': 'none',
    },
  },
  titleBarTitle: {
    fontSize: 'sm',
    color: 'whiteAlpha.800',
    textAlign: 'center',
  },
  titleBarButtons: {
    display: 'flex',
    gap: '1',
  },
  titleBarButton: {
    size: 'sm',
    variant: 'ghost',
    color: 'whiteAlpha.800',
    css: { '-webkit-app-region': 'no-drag' },
    _hover: { backgroundColor: 'whiteAlpha.200' },
  },
  closeButton: {
    size: 'sm',
    variant: 'ghost',
    color: 'whiteAlpha.800',
    css: { '-webkit-app-region': 'no-drag' },
    _hover: { backgroundColor: 'red.500' },
  },
} as const;
