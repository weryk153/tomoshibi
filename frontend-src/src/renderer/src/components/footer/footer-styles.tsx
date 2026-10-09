import { SystemStyleObject } from '@chakra-ui/react';
import { ACCENT_INK } from '@/theme/tomoshibi';

// 右欄最底下的輸入列（方向 02「直播間・霓虹」）：圓形麥克風＋輸入框，像直播聊天室。顏色全用 token：gray.900＝panel、gray.800＝panel2、
// green.*＝主色粉、gray.400＝次文字（fg2），見 theme/tomoshibi.ts。

/** 一行的輸入框高度；麥克風對齊這條中線。 */
const INPUT_HEIGHT = '44px';
/** 長到三行為止，再多就在框內捲動。15px 字 × 1.45 行高 ≈ 22px 一行。 */
const INPUT_MAX_HEIGHT = '88px';
/** 主色 18% 透明：麥克風開著時的外圈光暈。 */
const ACCENT_GLOW = 'rgba(255, 79, 154, 0.18)';
const LINE = 'rgba(255, 255, 255, 0.07)';

interface FooterStyles {
  container: SystemStyleObject
  overlayContainer: SystemStyleObject
  row: SystemStyleObject
  lineSlot: SystemStyleObject
  mic: (micOn: boolean) => SystemStyleObject
  inputSlot: SystemStyleObject
  input: (hasInterrupt: boolean) => SystemStyleObject
  inlineButtons: SystemStyleObject
  interruptButton: SystemStyleObject
  sendButton: (hasText: boolean) => SystemStyleObject
}

export const footerStyles: { footer: FooterStyles } = {
  footer: {
    // 在右欄的 flex 欄裡排在最後：輸入框長到多行時整列跟著長高，把聊天紀錄往上擠。
    container: {
      bg: 'gray.900',
      boxShadow: `inset 0 1px 0 ${LINE}`,
      flexShrink: 0,
    },
    // 手機直式：疊在角色上，只留一層薄薄的底色，角色的腳還看得到。
    overlayContainer: {
      bg: 'rgba(10, 10, 14, 0.55)',
      backdropFilter: 'blur(6px)',
      flexShrink: 0,
    },
    // 一行時 10＋44＋10＝64px。多行時這一列跟著輸入框長高，麥克風貼齊底部那一行
    // （lineSlot 佔一行高、在裡面置中）。
    row: {
      minHeight: '64px',
      px: '3',
      py: '10px',
      gap: '2',
      display: 'flex',
      alignItems: 'flex-end',
    },
    lineSlot: {
      height: INPUT_HEIGHT,
      display: 'flex',
      alignItems: 'center',
      flexShrink: 0,
      minW: 0,
    },
    mic: (micOn) => ({
      width: '40px',
      height: '40px',
      minW: '40px',
      borderRadius: 'full',
      bg: 'transparent',
      border: '1.5px solid',
      borderColor: micOn ? 'green.500' : 'gray.400',
      color: micOn ? 'green.500' : 'gray.400',
      boxShadow: micOn ? `0 0 0 4px ${ACCENT_GLOW}` : 'none',
      transition: 'border-color 0.2s, color 0.2s, box-shadow 0.2s',
      _hover: {
        bg: 'gray.800',
        color: micOn ? 'green.400' : 'gray.50',
      },
    }),
    inputSlot: {
      flex: 1,
      minW: 0,
      position: 'relative',
    },
    input: (hasInterrupt) => ({
      display: 'block',
      width: '100%',
      bg: 'gray.800',
      border: `1px solid ${LINE}`,
      borderRadius: 'lg',
      fontSize: '15px',
      lineHeight: '1.45',
      color: 'gray.50',
      pl: '3.5',
      // 送出鍵 32px＋右邊距；打斷鍵出現時再讓出一顆的位置。
      pr: hasInterrupt ? '84px' : '48px',
      py: '10px',
      minHeight: INPUT_HEIGHT,
      maxHeight: INPUT_MAX_HEIGHT,
      overflowY: 'auto',
      resize: 'none',
      // 內容多高框就多高（Chromium 123+，Electron 31 是 126）；不支援的瀏覽器
      // 停在一行、超過就捲動，功能不受影響。
      css: { fieldSizing: 'content' },
      _placeholder: { color: 'gray.400' },
      _focus: { outline: 'none' },
      _focusVisible: {
        outline: 'none',
        borderColor: 'green.500',
        boxShadow: 'none',
      },
      _disabled: { opacity: 0.6, cursor: 'not-allowed' },
    }),
    inlineButtons: {
      position: 'absolute',
      right: '6px',
      bottom: '6px',
      display: 'flex',
      gap: '1',
      alignItems: 'center',
    },
    interruptButton: {
      width: '32px',
      height: '32px',
      minW: '32px',
      borderRadius: 'md',
      bg: 'transparent',
      border: '1px solid',
      borderColor: 'green.500',
      color: 'green.400',
      _hover: { bg: 'green.950' },
    },
    sendButton: (hasText) => ({
      width: '32px',
      height: '32px',
      minW: '32px',
      borderRadius: 'md',
      transition: 'background-color 0.2s, color 0.2s, opacity 0.2s',
      ...(hasText
        ? {
          bg: 'green.500',
          color: ACCENT_INK,
          border: '1px solid transparent',
          _hover: { bg: 'green.400' },
        }
        : {
          bg: 'transparent',
          color: 'gray.400',
          border: '1px solid',
          borderColor: 'gray.600',
          opacity: 0.7,
        }),
      _disabled: {
        cursor: 'not-allowed',
        // 沒字時本來就是淡的那一套；Chakra 預設的 disabled 透明度會再疊一層。
        opacity: hasText ? 0.5 : 0.7,
      },
    }),
  },
};
