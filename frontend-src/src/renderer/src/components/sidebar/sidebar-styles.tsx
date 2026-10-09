import { css } from '@emotion/react';
import { SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH } from '@/layout';

const isElectron = window.api !== undefined;

const commonStyles = {
  scrollbar: {
    '&::-webkit-scrollbar': {
      width: '4px',
    },
    '&::-webkit-scrollbar-track': {
      bg: 'whiteAlpha.100',
      borderRadius: 'full',
    },
    '&::-webkit-scrollbar-thumb': {
      bg: 'whiteAlpha.300',
      borderRadius: 'full',
    },
  },
  panel: {
    border: '1px solid',
    borderColor: 'whiteAlpha.200',
    borderRadius: 'lg',
    bg: 'blackAlpha.400',
  },
  title: {
    fontSize: 'lg',
    fontWeight: 'semibold',
    color: 'white',
    mb: 4,
  },
};

export const sidebarStyles = {
  sidebar: {
    // 右欄。收起時整欄往右推出去，只留左緣一條把手（SIDEBAR_COLLAPSED_WIDTH）。
    container: (isCollapsed: boolean) => ({
      position: 'absolute' as const,
      right: 0,
      top: 0,
      height: '100%',
      width: SIDEBAR_WIDTH,
      bg: 'gray.900',
      transform: isCollapsed
        ? `translateX(calc(100% - ${SIDEBAR_COLLAPSED_WIDTH}))`
        : 'translateX(0)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      display: 'flex',
      flexDirection: 'column' as const,
      overflow: isCollapsed ? 'visible' : 'hidden',
    }),
    // Icon-only actions on the dark sidebar. These carried no styling at all
    // and rendered as Chakra's default `solid` chip, which only looked right
    // because it resolved to a dark grey in light mode — flipping the app to
    // dark mode turned them into white chips. State the treatment instead of
    // inheriting it.
    headerButton: {
      variant: 'ghost' as const,
      size: 'sm' as const,
      color: '#7761ae',
      bg: 'transparent',
      borderRadius: '12px',
      _hover: { bg: '#e6ddf3', color: '#5c468c' },
      _active: { bg: '#d0c5e1' },
    },
    // 收起後左緣那一整條把手；展開時改用按鈕列最右邊的那顆。
    collapsedRail: {
      position: 'absolute',
      left: 0,
      top: 0,
      width: SIDEBAR_COLLAPSED_WIDTH,
      minWidth: SIDEBAR_COLLAPSED_WIDTH,
      padding: 0,
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
      color: 'whiteAlpha.700',
      _hover: { color: 'white', bg: 'whiteAlpha.50' },
      bg: 'transparent',
      borderRadius: 0,
      zIndex: 1,
    },
    content: {
      flex: 1,
      minHeight: 0,
      width: '100%',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: 3,
      overflow: 'hidden',
    },
    header: {
      width: '100%',
      display: 'flex',
      alignItems: 'center',
      gap: 1,
      p: 2,
      borderBottom: '1px solid',
      borderColor: 'whiteAlpha.100',
    },
  },

  chatHistoryPanel: {
    container: {
      flex: 1,
      minHeight: 0,
      overflow: 'hidden',
      px: 3,
      display: 'flex',
      flexDirection: 'column',
    },
    title: commonStyles.title,
    messageList: {
      ...commonStyles.panel,
      p: 4,
      width: '100%',
      flex: 1,
      overflowY: 'auto',
      css: {
        ...commonStyles.scrollbar,
        scrollPaddingBottom: '1rem',
      },
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    },
  },

  systemLogPanel: {
    container: {
      width: '100%',
      overflow: 'hidden',
      px: 4,
      minH: '200px',
      marginTop: 'auto',
    },
    title: commonStyles.title,
    logList: {
      ...commonStyles.panel,
      p: 4,
      height: '200px',
      overflowY: 'auto',
      fontFamily: 'mono',
      css: commonStyles.scrollbar,
    },
    entry: {
      p: 2,
      borderRadius: 'md',
      _hover: {
        bg: 'whiteAlpha.50',
      },
    },
  },

  chatBubble: {
    container: {
      display: 'flex',
      position: 'relative',
      _hover: {
        bg: 'whiteAlpha.50',
      },
      py: 1,
      px: 2,
      borderRadius: 'md',
    },
    message: {
      maxW: '90%',
      bg: 'transparent',
      p: 2,
    },
    text: {
      fontSize: 'xs',
      color: 'whiteAlpha.900',
    },
    dot: {
      position: 'absolute',
      w: '2',
      h: '2',
      borderRadius: 'full',
      bg: 'white',
      top: '2',
    },
  },

  historyDrawer: {
    listContainer: {
      flex: 1,
      overflowY: 'auto',
      px: 4,
      py: 2,
      css: commonStyles.scrollbar,
    },
    historyItem: {
      mb: 4,
      p: 3,
      borderRadius: 'md',
      bg: 'whiteAlpha.50',
      cursor: 'pointer',
      transition: 'all 0.2s',
      _hover: {
        bg: 'whiteAlpha.100',
      },
    },
    historyItemSelected: {
      bg: 'whiteAlpha.200',
      borderLeft: '3px solid',
      borderColor: 'blue.500',
    },
    historyHeader: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      mb: 2,
    },
    timestamp: {
      fontSize: 'sm',
      color: 'whiteAlpha.700',
      fontFamily: 'mono',
    },
    deleteButton: {
      variant: 'ghost' as const,
      colorScheme: 'red' as const,
      size: 'sm' as const,
      color: 'red.300',
      opacity: 0.8,
      _hover: {
        opacity: 1,
        bg: 'whiteAlpha.200',
      },
    },
    messagePreview: {
      fontSize: 'sm',
      color: 'whiteAlpha.900',
      noOfLines: 2,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
    },
    drawer: {
      content: {
        background: 'var(--chakra-colors-gray-900)',
        maxWidth: '440px',
        marginTop: isElectron ? '30px' : '0',
        height: isElectron ? 'calc(100vh - 30px)' : '100vh',
      },
      title: {
        color: 'white',
      },
      closeButton: {
        color: 'white',
      },
      actionButton: {
        color: 'white',
        borderColor: 'white',
        variant: 'outline' as const,
      },
    },
  },

  cameraPanel: {
    container: {
      width: '100%',
      overflow: 'hidden',
      px: 0,
      minH: '0',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      mb: 1,
    },
    title: commonStyles.title,
    videoContainer: {
      border: '1px solid #d0c5e1', borderRadius: '12px', bg: '#f2edf8', color: '#80768d',
      width: '100%',
      height: 'clamp(100px, 18vh, 160px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      transition: 'all 0.2s',
    },
    video: {
      width: '100%',
      height: '100%',
      objectFit: 'cover' as const,
      transform: 'scaleX(-1)',
      borderRadius: '8px',
      display: 'block',
    } as const,
  },

  screenPanel: {
    container: {
      width: '100%',
      overflow: 'hidden',
      px: 0,
      minH: '0',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      mb: 1,
    },
    title: commonStyles.title,
    screenContainer: {
      border: '1px solid #d0c5e1', borderRadius: '12px', bg: '#f2edf8', color: '#80768d',
      width: '100%',
      height: 'clamp(100px, 18vh, 160px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      transition: 'all 0.2s',
    },
    video: {
      width: '100%',
      height: '100%',
      objectFit: 'cover' as const,
      borderRadius: '8px',
      display: 'block',
    } as const,
  },

  // Add Browser Panel Styles
  browserPanel: {
    container: {
      width: '100%',
      overflow: 'hidden',
      px: 0,
      minH: '0',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      mb: 1,
    },
    title: commonStyles.title,
    browserContainer: {
      border: '1px solid #d0c5e1', borderRadius: '12px', bg: '#f2edf8', color: '#80768d',
      width: '100%',
      height: 'clamp(100px, 18vh, 160px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      transition: 'all 0.2s',
      cursor: 'pointer',
      _hover: {
        bg: 'whiteAlpha.100',
      },
    },
    iframe: {
      width: '100%',
      height: '100%',
      border: 'none',
      borderRadius: '8px',
    } as const,
  },

  bottomTab: {
    container: {
      width: '100%',
      px: 3,
      flexShrink: 0,
      position: 'relative' as const,
      zIndex: 0,
    },
    tabs: {
      width: '100%',
      bg: '#f2edf8',
      borderRadius: 'lg',
      p: '1',
    },
    list: {
      borderBottom: 'none',
      gap: '1',
    },
    trigger: {
      color: '#80768d',
      display: 'flex',
      alignItems: 'center',
      gap: 1.5,
      px: 2,
      py: 2,
      fontSize: '12px',
      flex: 1,
      borderRadius: 'md',
      _hover: {
        color: '#5c468c',
        bg: '#f2edf8',
      },
      _selected: {
        color: '#5c468c',
        bg: '#e6ddf3',
      },
    },
  },

  groupDrawer: {
    section: {
      mb: 6,
    },
    sectionTitle: {
      fontSize: 'lg',
      fontWeight: 'semibold',
      color: 'white',
      mb: 3,
    },
    inviteBox: {
      display: 'flex',
      gap: 2,
    },
    input: {
      bg: 'whiteAlpha.100',
      border: 'none',
      color: 'white',
      _placeholder: {
        color: 'whiteAlpha.400',
      },
    },
    memberList: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    },
    memberItem: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      p: 2,
      borderRadius: 'md',
      bg: 'whiteAlpha.100',
    },
    memberText: {
      color: 'white',
      fontSize: 'sm',
    },
    removeButton: {
      size: 'sm',
      color: 'red.300',
      bg: 'transparent',
      _hover: {
        bg: 'whiteAlpha.200',
      },
    },
    button: {
      color: 'white',
      bg: 'whiteAlpha.100',
      _hover: {
        bg: 'whiteAlpha.200',
      },
    },
    clipboardButton: {
      color: 'white',
      bg: 'transparent',
      _hover: {
        bg: 'whiteAlpha.200',
      },
      size: 'sm',
    },
  },

  // Add styles for the Tool Call Indicator
  toolCallIndicator: {
    container: {
      pl: '44px', // Indent to align with message content (avatar width + gap)
      my: '1', // Reduced vertical margin (e.g., 4px if theme space 1 = 4px)
      gap: 2,
      width: '100%',
      minHeight: '24px', // Ensure minimum height
      display: 'flex', // Ensure display is flex
      alignItems: 'center', // Keep vertical alignment
      justifyContent: 'center', // Center items horizontally
    },
    icon: {
      color: '#7761ae',
      boxSize: '14px',
    },
    text: {
      fontSize: 'xs',
      color: '#80768d',
      fontStyle: 'italic',
    },
    spinner: {
      size: 'xs',
      color: '#7761ae',
      ml: 0,
    },
    completedIcon: {
      color: '#658774',
      boxSize: '14px',
      ml: 0,
    },
    errorIcon: {
      color: 'red.300',
      boxSize: '14px',
      ml: 0,
    },
  },
};

export const chatPanelStyles = css`
  .cs-message-list { background: #fffcf7 !important; padding: 12px 16px !important; }
  .cs-message { margin: 16px 0 !important; }
  .cs-message__content {
    background-color: #f0eaf7 !important; border: 1px solid #e0d6ed;
    border-radius: 16px !important; padding: 12px 14px !important;
    color: #342d49 !important; font-size: 14px !important; line-height: 1.7 !important;
    margin-top: 5px !important;
  }
  .cs-message--outgoing .cs-message__content { background-color: #f8dfd2 !important; border-color: #edcdbd; }
  .cs-message--outgoing .cs-message__html-content { color: #342d49 !important; }
  .cs-chat-container { background: transparent !important; border: none !important; padding: 0 !important; }
  .cs-main-container { border: none !important; background: transparent !important; width: 100% !important; margin-left: 0 !important; }
  .cs-message__sender { font-size: 12px !important; font-weight: 600 !important; color: #80768d !important; }
  .cs-message__content-wrapper { max-width: 84%; margin: 0 8px; }
  .cs-avatar {
    background-color: #e6ddf3 !important; color: #5c468c !important;
    width: 28px !important; height: 28px !important; font-size: 14px !important;
    display: flex !important; align-items: center !important; justify-content: center !important; border-radius: 50% !important;
  }
  .cs-message--outgoing .cs-avatar { background-color: #f5c9b5 !important; color: #694938 !important; }
  .cs-message__header { display: block !important; visibility: visible !important; opacity: 1 !important; }
  .cs-message-list .ps__thumb-y { background: #c5b7d8 !important; }
`;
