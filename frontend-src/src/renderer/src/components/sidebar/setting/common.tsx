// 設定分頁用的複合元件，Ark UI + Tailwind 版。
//
// 遷移期間這個檔案叫 common-tw.tsx，與 Chakra 版的 common.tsx 並存。設定分頁
// 全部改完之後 Chakra 版已刪除，這裡收編回原名。

import { useState, useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { toaster } from '@/components/ui/tw/toaster';
import { Button, cx } from '@/components/ui/tw/primitives';

export {
  Field, InputField, SwitchField, SelectField, NumberField, SliderField, TextareaField,
  HelpIcon, Button, cx,
} from '@/components/ui/tw/primitives';

// 「套用／還原」按鈕組。
//
// 現在整個設定抽屜只剩一個地方在用它：一般分頁的連線設定（WebSocket／伺服器
// 位址）。其餘所有控制項都是改了就生效——抽屜裡多數區塊本來就是那樣，把少數
// 幾個做成草稿制只會讓同一個面板裡兩個長得一樣的 switch 行為不同。
//
// 連線位址是唯一的例外，而且理由是功能性的而非偏好：那兩個欄位每改一個字元
// 就會觸發一次 WebSocket 重連（見 use-general-settings 的說明），必須等使用者
// 打完才送。
//
// 回饋：這組按鈕原本永遠是啟用的，而當時這幾個分頁的設定是打字當下就生效的
// ——handleSave 只是把目前的值設成新的還原基準，畫面上不會有任何變化。沒改
// 東西就按下去，等於什麼都沒發生，看起來就像按鈕壞了。四個分頁後來改成真正
// 的草稿制（見各自的 use-*-settings），套用才施加變更；這組按鈕的狀態機制
// 一併留著，因為「有沒有未套用的變更」在草稿制下更有意義。現在：
//
//   - dirty=false 時兩顆都停用，「按了沒事」變成看得見的「不能按」
//   - dirty=true 時上方顯示一行「有未套用的變更」，說明按鈕為什麼亮著
//   - 按下之後跳一則 toast，並且按鈕會立刻變灰（因為 dirty 翻回 false）
//
// onApply 可以回傳 Promise：有網路寫入的分頁在等待期間按鈕顯示載入中並停用，
// 失敗時 toast 換成錯誤訊息，不會謊報成功。
interface TabActionsProps {
  onApply: () => void | Promise<unknown>;
  onRevert: () => void;
  disabled?: boolean;
  /** 是否有未套用的變更。省略時維持舊行為（永遠可按）。 */
  dirty?: boolean;
  /** 主要按鈕的文字。連線設定用「連線」而不是「套用」——那顆按鈕做的是連線。 */
  applyLabel?: string;
}

export function TabActions({
  onApply, onRevert, disabled = false, dirty, applyLabel,
}: TabActionsProps): JSX.Element {
  const { t } = useTranslation();
  const [applying, setApplying] = useState(false);
  // 卸載後不要再 setState：套用可能是非同步的，而使用者隨時會關掉抽屜。
  const alive = useRef(true);
  useEffect(() => () => {
    alive.current = false;
  }, []);

  const hasChanges = dirty === undefined ? true : dirty;
  const blocked = disabled || applying || !hasChanges;

  const handleApply = useCallback(async () => {
    setApplying(true);
    try {
      await onApply();
      if (!alive.current) return;
      toaster.create({ title: t('common.applied'), type: 'success', duration: 2000 });
    } catch (e) {
      if (!alive.current) return;
      // 不吞掉失敗——謊報成功比沒有回饋更糟。
      toaster.create({
        title: t('common.applyFailed'),
        description: e instanceof Error ? e.message : undefined,
        type: 'error',
        duration: 4000,
      });
    } finally {
      if (alive.current) setApplying(false);
    }
  }, [onApply, t]);

  return (
    <div className="flex flex-col gap-1 pt-2">
      {/* 佔位用的空白：沒有它的話，提示出現／消失會讓下面的內容跳動一次。 */}
      <span className={cx('text-right text-xs', hasChanges ? 'text-yellow-300' : 'invisible')}>
        {hasChanges ? t('common.unsavedChanges') : ' '}
      </span>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onRevert} disabled={blocked}>
          {t('common.revert')}
        </Button>
        <Button onClick={handleApply} loading={applying} disabled={blocked}>
          {applyLabel ?? t('common.apply')}
        </Button>
      </div>
    </div>
  );
}
