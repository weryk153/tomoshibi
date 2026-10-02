// 數字欄位：欄位保留使用者打的字，停手 0.8 秒或離開欄位才交出去；打到一半的值
// （空、「0.」、超出範圍）不交出去、不彈回舊值，旁邊寫範圍。
//
// 介面跟 NumberField 一樣（onChange 拿到的是已經合法的字串），所以原本的
// onChange 處理不用改。外面的值換了（例如切換到另一個場景）才同步回欄位。
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';
import { NumberField } from './primitives';
import { SaveStatus } from './save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { boundsMessage, parseBoundedNumber, type Bounds } from '@/utils/setting-values';

interface DraftNumberFieldProps {
  label: ReactNode;
  value: number;
  onChange: (value: string) => void;
  min?: number;
  max?: number;
  step?: number;
  integer?: boolean;
  help?: ReactNode;
}

export function DraftNumberField({
  label, value, onChange, min, max, step, integer, help,
}: DraftNumberFieldProps): JSX.Element {
  const { t } = useTranslation();
  const bounds: Bounds = { min, max, integer };
  const [text, setText] = useState(String(value));

  useEffect(() => {
    setText((current) => (parseBoundedNumber(current, bounds) === value ? current : String(value)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const saver = useAutosave(async (next: string) => {
    onChange(next);
    return { ok: true } as const;
  }, {
    validate: (next) => {
      if (parseBoundedNumber(next, bounds) !== null) return null;
      const message = boundsMessage(bounds);
      return t(message.key, message.params);
    },
  });

  return (
    <div className="flex flex-col gap-1">
      <NumberField
        label={label}
        value={text}
        min={min}
        max={max}
        step={step}
        help={help}
        onChange={(next) => { setText(next); saver.change(next); }}
        onBlur={saver.flush}
      />
      {saver.state.phase === 'invalid' && <SaveStatus state={saver.state} />}
    </div>
  );
}
