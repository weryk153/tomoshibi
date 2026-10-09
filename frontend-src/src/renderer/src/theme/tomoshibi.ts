// Shared lavender accents for both Chakra and Tailwind.
// Portal surfaces use moonlight-surfaces.css for their light neutral palette.

import { createSystem, defaultConfig, defineConfig } from '@chakra-ui/react';

/** Text on the lavender primary action. */
export const ACCENT_INK = '#ffffff';
/** Text on the secondary action. */
export const ACCENT2_INK = '#ffffff';

const scale = (values: Record<string, string>) => Object.fromEntries(
  Object.entries(values).map(([step, value]) => [step, { value }]),
);

export const tomoshibiColors = {
  gray: {
    50: '#f2f2f6', // fg 主文字
    100: '#e2e2ea',
    200: '#c8c8d4',
    300: '#a9a9b8',
    400: '#8b8b9c', // fg2 次文字（Chakra 的 fg.muted 在深色模式就是 gray.400）
    500: '#6a6a7c',
    600: '#464658', // 邊線（實線）
    700: '#242433', // panel3：hover／選中
    800: '#1a1a24', // panel2：輸入框、泡泡、卡片
    900: '#111118', // panel：側欄、底部列、Drawer
    950: '#0a0a0e', // bg：最底
  },
  green: {
    50: '#f6f1fc',
    100: '#e6ddf3',
    200: '#d0c0e5',
    300: '#b6a1d0',
    400: '#695198',
    500: '#7761ae',
    600: '#695198',
    700: '#574181',
    800: '#49366d',
    900: '#382952',
    950: '#2a203f',
  },
  blue: {
    50: '#f6f1fc',
    100: '#e6ddf3',
    200: '#d0c0e5',
    300: '#b6a1d0',
    400: '#695198',
    500: '#7761ae',
    600: '#695198',
    700: '#574181',
    800: '#49366d',
    900: '#382952',
    950: '#2a203f',
  },
} as const;

const FONT_CJK_FALLBACK = "'PingFang TC', 'Hiragino Sans', 'Apple SD Gothic Neo', 'Microsoft JhengHei', 'Yu Gothic', 'Malgun Gothic', 'Noto Sans CJK TC'";

export const tomoshibiFonts = {
  heading: `'Space Grotesk', 'Noto Sans TC Variable', ${FONT_CJK_FALLBACK}, system-ui, sans-serif`,
  body: `'Noto Sans TC Variable', ${FONT_CJK_FALLBACK}, system-ui, sans-serif`,
  mono: `'IBM Plex Mono', 'Noto Sans TC Variable', ${FONT_CJK_FALLBACK}, ui-monospace, monospace`,
} as const;

const config = defineConfig({
  theme: {
    tokens: {
      colors: {
        gray: scale(tomoshibiColors.gray),
        green: scale(tomoshibiColors.green),
        blue: scale(tomoshibiColors.blue),
      },
      fonts: {
        heading: { value: tomoshibiFonts.heading },
        body: { value: tomoshibiFonts.body },
        mono: { value: tomoshibiFonts.mono },
      },
      radii: {
        sm: { value: '4px' },
        md: { value: '6px' },
        lg: { value: '10px' },
        xl: { value: '14px' },
      },
    },
    semanticTokens: {
      colors: {
        // All primary actions use lavender with a white foreground.
        green: {
          solid: { value: '{colors.green.500}' },
          contrast: { value: ACCENT_INK },
          focusRing: { value: '{colors.green.500}' },
        },
        blue: {
          solid: { value: '{colors.blue.500}' },
          contrast: { value: ACCENT2_INK },
          focusRing: { value: '{colors.blue.500}' },
        },
      },
    },
  },
});

export const tomoshibiSystem = createSystem(defaultConfig, config);
