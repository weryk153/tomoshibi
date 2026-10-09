// 組合頁裡的一區：標題＋（選填）一行說明＋內容，區與區之間一條分隔線。
import type { ReactNode } from 'react';

export function SettingSection({ title, note, children }: {
  title?: string
  note?: string
  children: ReactNode
}): JSX.Element {
  return (
    <section className="moonlight-setting-section flex flex-col gap-4">
      {title && <h3 className="text-sm font-semibold text-white">{title}</h3>}
      {note && <p className="text-xs text-walpha-600">{note}</p>}
      {children}
    </section>
  );
}
