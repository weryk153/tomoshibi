// 側邊抽屜，Ark Dialog + Tailwind。取代 components/ui/drawer.tsx（Chakra 版）。
//
// Ark 的 anatomy 不能省略任何一層：
//
//   Dialog.Root
//     ├── Dialog.Trigger        （可選，也可以純受控）
//     ├── Dialog.Backdrop       ← 遮罩，點擊關閉靠它
//     └── Dialog.Positioner     ← 定位錨點，少了它 Content 會跑到左上角
//           └── Dialog.Content
//
// Positioner 這一層特別容易被當成多餘的包裝刪掉。先前設定抽屜出過一次事故就是
// 這附近，所以這裡把結構寫死在元件內，呼叫端拿不到拆開它的機會。
//
// Backdrop 與 Content 都吃 data-state（open／closed），動畫直接掛在那上面，
// 不需要另外接動畫函式庫——Chakra 版是靠 framer-motion 做的。

import type { ReactNode } from 'react';
import { Dialog as ArkDialog, Portal } from '@ark-ui/react';
import { cx } from './primitives';

// 抽屜的水平內距。標題、頁尾、以及內容區都必須用這一個值——先前標題是 px-6、
// 分頁列與內容是 px-4，於是標題比下面所有東西往右縮排 8px，右緣也對不齊。
// 匯出讓內容區（例如 setting-ui 的分頁列）引用，而不是各自寫一個數字。
export const DRAWER_PX = 'px-6';

// Electron 有一條 30px 的自訂標題列，抽屜不能蓋住它。網頁版沒有這回事。
const isElectron = typeof window !== 'undefined' && window.api !== undefined;
const TOP_OFFSET = isElectron ? '30px' : '0px';
const PANEL_HEIGHT = isElectron ? 'calc(100vh - 30px)' : '100vh';

interface DrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** start = 從左邊滑出，end = 從右邊。 */
  placement?: 'start' | 'end';
  title: ReactNode;
  /** 觸發元素。純受控（由外部 state 開關）時可以不給。 */
  trigger?: ReactNode;
  footer?: ReactNode;
  /**
   * 遮罩外觀。'dim' 會把後面的畫面調暗並模糊；'clear' 是完全透明，只負責接
   * 「點外面關閉」。
   *
   * 設定抽屜必須用 'clear'：Live2D 與背景那幾個分頁調的就是右邊畫布上的東西，
   * 把畫布調暗等於一邊調一邊看不見結果。Chakra 版的遮罩本來就是透明的，改成
   * 調暗會是功能上的退步。
   */
  backdrop?: 'dim' | 'clear';
  /**
   * wide 給需要同時容納導覽與表單的設定中心；一般歷史／群組抽屜維持緊湊寬度。
   * 小螢幕兩者都會退回 100vw，不製造水平捲軸。
   */
  size?: 'default' | 'wide';
  children: ReactNode;
}

export function Drawer({
  open, onOpenChange, placement = 'start', title, trigger, footer,
  backdrop = 'dim', size = 'default', children,
}: DrawerProps): JSX.Element {
  const fromLeft = placement === 'start';

  return (
    <ArkDialog.Root open={open} onOpenChange={(e) => onOpenChange(e.open)}>
      {trigger && <ArkDialog.Trigger asChild>{trigger}</ArkDialog.Trigger>}
      <Portal>
        <ArkDialog.Backdrop
          className={cx(
            'fixed inset-0 z-[1400]',
            backdrop === 'dim' && 'bg-black/50 backdrop-blur-[2px]',
            'data-[state=open]:animate-[fadeIn_150ms_ease-out]',
            'data-[state=closed]:animate-[fadeOut_120ms_ease-in]',
          )}
        />
        <ArkDialog.Positioner
          className={cx('fixed z-[1400] flex', fromLeft ? 'left-0' : 'right-0')}
          style={{ top: TOP_OFFSET, height: PANEL_HEIGHT }}
        >
          <ArkDialog.Content
            className={cx(
              'flex h-full max-w-[100vw] flex-col bg-zinc-900 shadow-2xl outline-none',
              size === 'wide'
                ? 'w-[100vw] sm:w-[clamp(600px,44vw,680px)]'
                : 'w-[440px]',
              fromLeft ? 'border-r border-walpha-200' : 'border-l border-walpha-200',
              fromLeft
                ? 'data-[state=open]:animate-[slideInLeft_180ms_ease-out] data-[state=closed]:animate-[slideOutLeft_150ms_ease-in]'
                : 'data-[state=open]:animate-[slideInRight_180ms_ease-out] data-[state=closed]:animate-[slideOutRight_150ms_ease-in]',
            )}
          >
            <div className={cx('flex items-center justify-between py-4', DRAWER_PX)}>
              <ArkDialog.Title className="text-lg font-semibold text-white">
                {title}
              </ArkDialog.Title>
              <ArkDialog.CloseTrigger
                className={cx(
                  'rounded p-1 text-white/70 outline-none transition-colors',
                  'hover:bg-walpha-200 hover:text-white',
                  'focus-visible:ring-2 focus-visible:ring-blue-500/40',
                )}
              >
                {/* 用 SVG 而不是 ×：字元的視覺重心會隨字型跑掉，各平台對不齊。 */}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M6 6l12 12M18 6L6 18"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </ArkDialog.CloseTrigger>
            </div>

            {/* min-h-0 是必要的：flex 子項的預設 min-height 是 auto，內容一長
                就會把面板撐破而不是自己捲動。 */}
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>

            {footer && (
              <div className={cx('flex justify-end gap-2 border-t border-walpha-200 py-4', DRAWER_PX)}>
                {footer}
              </div>
            )}
          </ArkDialog.Content>
        </ArkDialog.Positioner>
      </Portal>
    </ArkDialog.Root>
  );
}

/** 關閉抽屜的按鈕包裝，讓 footer 裡的按鈕不必自己接 onOpenChange。 */
export function DrawerCloseAction({ children }: { children: ReactNode }): JSX.Element {
  return <ArkDialog.CloseTrigger asChild>{children}</ArkDialog.CloseTrigger>;
}
