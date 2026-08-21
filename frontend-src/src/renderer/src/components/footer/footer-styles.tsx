import { SystemStyleObject } from '@chakra-ui/react';

interface FooterStyles {
  container: (isCollapsed: boolean) => SystemStyleObject
  toggleButton: SystemStyleObject
  actionButton: SystemStyleObject
  sendButton: SystemStyleObject
  input: SystemStyleObject
}

interface AIIndicatorStyles {
  stateColors: Record<string, string>
  container: SystemStyleObject
  text: SystemStyleObject
}

export const footerStyles: {
  footer: FooterStyles
  aiIndicator: AIIndicatorStyles
} = {
  footer: {
    container: (isCollapsed) => ({
      bg: isCollapsed ? 'transparent' : 'gray.800',
      borderTopRadius: isCollapsed ? 'none' : 'lg',
      transform: isCollapsed ? 'translateY(calc(100% - 28px))' : 'translateY(0)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      height: '100%',
      position: 'relative',
      overflow: isCollapsed ? 'visible' : 'hidden',
      // 28px toggle + 86px controls already fill most of the 128px footer.
      // Extra bottom padding made the 50px action buttons visibly clip.
      pb: '0',
    }),
    toggleButton: {
      height: '28px',
      minHeight: '28px',
      minWidth: '100%',
      padding: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
      color: 'whiteAlpha.700',
      _hover: { color: 'white' },
      bg: 'transparent',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    },
    actionButton: {
      borderRadius: '12px',
      width: '50px',
      height: '50px',
      minW: '50px',
    },
    sendButton: {
      position: 'absolute',
      right: '12px',
      top: '50%',
      transform: 'translateY(-50%)',
      width: '44px',
      height: '44px',
      minWidth: '44px',
      borderRadius: '10px',
      bg: 'green.500',
      color: 'black',
      _hover: { bg: 'green.400' },
      _disabled: {
        bg: 'whiteAlpha.100',
        color: 'whiteAlpha.400',
        cursor: 'not-allowed',
        opacity: 1,
      },
    },
    input: {
      bg: 'gray.700',
      border: 'none',
      height: '80px',
      borderRadius: '12px',
      fontSize: '18px',
      pl: '4',
      pr: '68px',
      color: 'whiteAlpha.900',
      _placeholder: {
        color: 'whiteAlpha.500',
      },
      _focus: {
        border: 'none',
        bg: 'gray.700',
      },
      resize: 'none',
      minHeight: '80px',
      maxHeight: '80px',
      py: '0',
      display: 'flex',
      alignItems: 'center',
      paddingTop: '28px',
      lineHeight: '1.4',
    },
  },
  aiIndicator: {
    // 這顆徽章顯示的是會變的狀態（空閒／思考／聆聽／已打斷），顏色卻是固定的
    // 紫色——一個不帶資訊的飽和色塊，只是在跟旁邊的麥克風、舉手按鈕搶注意力。
    // 讓顏色跟著狀態走，它才真的在說話；順帶讓「空閒」退成中性灰，畫面靜下來。
    stateColors: {
      idle: '#4A5568',
      loading: '#4A5568',
      waiting: '#4A5568',
      'thinking-speaking': '#7C5CFF',
      listening: '#2F855A',
      interrupted: '#C05621',
    } as Record<string, string>,
    container: {
      bg: '#7C5CFF',
      color: 'white',
      width: '110px',
      height: '30px',
      borderRadius: '12px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 2px 6px rgba(0,0,0,0.1)',
      overflow: 'hidden',
    },
    text: {
      fontSize: '12px',
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
    },
  },
};
