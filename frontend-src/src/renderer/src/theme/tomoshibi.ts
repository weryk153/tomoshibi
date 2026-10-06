// Tomoshibi 的 Chakra 主題：方向 02「直播間・霓虹」。
//
// 做法是「換色階，不換名字」：各檔寫死的 gray.800／green.500／blue.500 有上百處，
// 逐一改既費工又一定會漏。所以這裡直接把 gray／green／blue 三組色階的值換掉——
//   gray  → 帶一點藍的冷灰（950＝最底、900＝面板、800＝輸入框／卡片、700＝hover）
//   green → 主色粉（500＝#ff4f9a）。原本綠色的地方（送出、選中、開）都是「主要動作」。
//   blue  → 副色青（500＝#27e2d4）。原本藍色的地方是連結、資訊、第二強調。
// red／yellow／orange 不動：錯誤、警告的語意要留著。
//
// Tailwind 那邊（index.css 的 @theme）有同一組值，兩邊要一起改——
// 遷移中的 Tailwind 元件跟 Chakra 元件會並排出現在同一個抽屜裡。

import { createSystem, defaultConfig, defineConfig } from '@chakra-ui/react';

/** 主色（粉）上的字。白字在 #ff4f9a 上對比不到 3:1，深色墨水有 6:1 以上。 */
export const ACCENT_INK = '#1a0611';
/** 副色（青）上的字。青太亮，白字只有 1.4:1。 */
export const ACCENT2_INK = '#04201d';

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
    50: '#fff0f6',
    100: '#ffd6e8',
    200: '#ffb3d4',
    300: '#ff8bbd',
    400: '#ff6daa',
    500: '#ff4f9a', // accent
    600: '#e0307d',
    700: '#b81f63',
    800: '#8a174a',
    900: '#5c0f31',
    950: '#3a0820',
  },
  blue: {
    50: '#e8fdfb',
    100: '#c3f9f4',
    200: '#8ff3ea',
    300: '#5aebdf',
    400: '#3be6d9',
    500: '#27e2d4', // accent2
    600: '#1bb8ac',
    700: '#158e85',
    800: '#10665f',
    900: '#0a403c',
    950: '#062826',
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
        // 預設的 solid 是 600 階、上面放白字。粉與青都比原本的綠／藍亮，
        // 白字會糊掉；改成 500 階（就是設計稿的主色／副色）配深色墨水。
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
