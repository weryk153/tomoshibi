// Toast，Ark + Tailwind。取代 components/ui/toaster.tsx（Chakra 版）。
//
// 匯出的 `toaster` 物件保持同一個介面（create / dismiss），所以 24 個呼叫端
// 一行都不用改——它們呼叫的本來就是 Ark 的 createToaster，Chakra 只是把它
// re-export 出來而已。真正換掉的只有畫面那一層。

import { Toast as ArkToast, Toaster as ArkToaster, createToaster } from '@ark-ui/react';
import { cx } from './primitives';

export const toaster = createToaster({
  placement: 'top-end',
  pauseOnPageIdle: true,
  max: 5,
});

// 依 toast 類型決定左側色條。用色條而不是整塊染色：訊息本身是白字深底，整塊
// 染成紅色會讓錯誤訊息比內容還搶眼，而多數 toast 只是確認「存好了」。
const TONE = {
  success: 'border-l-green-500',
  error: 'border-l-red-500',
  warning: 'border-l-yellow-500',
  info: 'border-l-blue-500',
  loading: 'border-l-blue-500',
} as const;

export function Toaster(): JSX.Element {
  return (
    <ArkToaster toaster={toaster}>
      {(toast) => (
        <ArkToast.Root
          className={cx(
            'pointer-events-auto flex w-[min(24rem,90vw)] items-start gap-3 rounded-md',
            'border border-walpha-200 border-l-4 bg-zinc-800 px-4 py-3 shadow-xl',
            'data-[state=open]:animate-[fadeIn_150ms_ease-out]',
            'data-[state=closed]:animate-[fadeOut_120ms_ease-in]',
            TONE[toast.type as keyof typeof TONE] ?? TONE.info,
          )}
        >
          {toast.type === 'loading' && (
            <span
              className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-blue-400 border-t-transparent"
              aria-hidden="true"
            />
          )}
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            {toast.title && (
              <ArkToast.Title className="text-sm font-medium text-white">
                {toast.title}
              </ArkToast.Title>
            )}
            {toast.description && (
              <ArkToast.Description className="text-xs leading-snug text-white/70">
                {toast.description}
              </ArkToast.Description>
            )}
          </div>
          {toast.action && (
            <ArkToast.ActionTrigger className="shrink-0 text-xs font-medium text-blue-300 hover:text-blue-200">
              {toast.action.label}
            </ArkToast.ActionTrigger>
          )}
          <ArkToast.CloseTrigger
            className="shrink-0 rounded p-0.5 text-white/50 transition-colors hover:bg-walpha-200 hover:text-white"
            aria-label="close"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </ArkToast.CloseTrigger>
        </ArkToast.Root>
      )}
    </ArkToaster>
  );
}
