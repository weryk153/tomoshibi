const isElectron = window.api !== undefined;

// Keep the conversation tools useful without letting them dominate the stage.
// A fixed 440px sidebar consumed almost a third of the usable browser viewport at
// common zoom levels, while the 24px collapsed rail was too small to target.
export const SIDEBAR_WIDTH = 'clamp(320px, 26vw, 400px)';
export const SIDEBAR_COLLAPSED_WIDTH = '32px';
export const FOOTER_HEIGHT = '128px';
export const FOOTER_COLLAPSED_HEIGHT = '28px';

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
    bg: 'gray.900',
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
    bg: 'gray.800',
    borderRight: '1px solid',
    borderColor: 'whiteAlpha.200',
    overflow: 'hidden',
    flexShrink: 0,
    transition: 'all 0.2s',
  },
  mainContent: {
    flex: 1,
    height: { base: `calc(100% - ${FOOTER_HEIGHT})`, md: '100%' },
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
  footer: {
    width: '100%',
    height: FOOTER_HEIGHT,
    flexShrink: 0,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    willChange: 'transform',
    position: 'relative',
    zIndex: 1,
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
  canvasHeight: (isFooterCollapsed: boolean) => ({
    height: isFooterCollapsed
      ? `calc(100% - ${FOOTER_COLLAPSED_HEIGHT})`
      : `calc(100% - ${FOOTER_HEIGHT})`,
  }),
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
  collapsedFooter: {
    height: FOOTER_COLLAPSED_HEIGHT,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
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
