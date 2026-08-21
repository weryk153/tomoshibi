// Ark UI + Tailwind 版的基礎元件。Chakra 遷移的第一批。
//
// 為什麼是 Ark 而不是 Radix：Chakra v3 底層跑的就是 Ark（zag-js）——目前
// package.json 裡 @ark-ui/react 被 Chakra 釘在 5.5.0，我們刻意裝同一版，這樣
// node_modules 與 bundle 裡只有一份 Ark/zag。也就是說這次換掉的只有樣式層，
// 鍵盤操作、焦點管理、ARIA、狀態機全部原封不動——先前踩過的 zag 行為（例如
// Select 不能用空字串當 value，見 characters.tsx 的 INHERIT_VOICE）在這裡
// 依然成立，不需要重新摸索一遍。
//
// 樣式對照的來源是 setting-styles.tsx 與執行中 app 讀出來的 CSS 變數，不是
// 憑印象配色：遷移中的分頁和還沒遷移的分頁會並排在同一個抽屜裡，差一點就
// 會被看見。Chakra v3 的灰階本來就是 Tailwind 的 zinc、blue/yellow/red 也
// 完全對得上，只有 whiteAlpha 要自訂（index.css 的 --color-walpha-*）。

import { forwardRef, type ReactNode } from 'react';
import {
  Select as ArkSelect,
  Switch as ArkSwitch,
  Field as ArkField,
  NumberInput as ArkNumberInput,
  Slider as ArkSlider,
  Tooltip as ArkTooltip,
  Checkbox as ArkCheckbox,
} from '@ark-ui/react';
import { HiQuestionMarkCircle } from 'react-icons/hi';
import type { ListCollection } from '@ark-ui/react/collection';

// 把 class 串起來，順手濾掉 falsy——條件式 class 到處都要用。
export const cx = (...parts: (string | false | null | undefined)[]): string =>
  parts.filter(Boolean).join(' ');

// --------------------------------------------------------------------------
// 共用的視覺常數
// --------------------------------------------------------------------------

// setting-styles.tsx 的 common.input：bg whiteAlpha.100、border whiteAlpha.200、
// hover 時 bg 轉 whiteAlpha.200。focus 環是新加的——Chakra 版本靠瀏覽器預設的
// outline，在深色底上幾乎看不見。
const CONTROL = 'w-full rounded-md border border-walpha-200 bg-walpha-100 px-3 py-2 '
  + 'text-sm text-white placeholder:text-walpha-400 outline-none transition-colors '
  + 'hover:bg-walpha-200 focus-visible:border-blue-500 focus-visible:ring-2 '
  + 'focus-visible:ring-blue-500/40 disabled:cursor-not-allowed disabled:opacity-50';

const LABEL = 'text-sm leading-snug text-walpha-800';
const HELPER = 'text-xs text-walpha-600';

// --------------------------------------------------------------------------
// Field：標籤 + 控制項 + 說明文字
// --------------------------------------------------------------------------

interface FieldProps {
  label: ReactNode;
  /** 橫向排版時標籤的固定寬度，對齊 Chakra 版的 --field-label-width: 120px。 */
  horizontal?: boolean;
  help?: ReactNode;
  children: ReactNode;
}

export function Field({
  label, horizontal = false, help, children,
}: FieldProps): JSX.Element {
  return (
    <ArkField.Root className={cx(
      'flex gap-2',
      horizontal ? 'flex-col sm:flex-row sm:items-center' : 'flex-col',
    )}>
      <ArkField.Label className={cx(LABEL, horizontal && 'sm:w-[120px] sm:shrink-0')}>
        {label}
      </ArkField.Label>
      <div className={cx('flex flex-col gap-1', horizontal ? 'flex-1' : 'w-full')}>
        {children}
        {help && <ArkField.HelperText className={HELPER}>{help}</ArkField.HelperText>}
      </div>
    </ArkField.Root>
  );
}

// --------------------------------------------------------------------------
// Input
// --------------------------------------------------------------------------

interface InputFieldProps {
  label: ReactNode;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  help?: ReactNode;
  type?: string;
  disabled?: boolean;
}

// 沒有標籤的裸輸入框，給「標籤由外層 Field 提供」的呼叫端用。
export const TextInput = forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...rest }, ref) => (
  <input ref={ref} className={cx(CONTROL, className)} {...rest} />
));
TextInput.displayName = 'TextInput';

export const InputField = forwardRef<HTMLInputElement, InputFieldProps>(
  ({
    label, value, onChange, placeholder, help, type = 'text', disabled,
  }, ref) => (
    <Field label={label} help={help}>
      <input
        ref={ref}
        className={CONTROL}
        type={type}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  ),
);
InputField.displayName = 'InputField';

// --------------------------------------------------------------------------
// Switch
// --------------------------------------------------------------------------

interface SwitchFieldProps {
  label: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  help?: ReactNode;
  disabled?: boolean;
}

export function SwitchField({
  label, checked, onChange, help, disabled,
}: SwitchFieldProps): JSX.Element {
  return (
    <div className="flex flex-col gap-1">
      <ArkSwitch.Root
        checked={checked}
        disabled={disabled}
        onCheckedChange={(e) => onChange(e.checked)}
        className="flex items-center justify-between gap-4 data-[disabled]:opacity-50"
      >
        <ArkSwitch.Label className={LABEL}>{label}</ArkSwitch.Label>
        <ArkSwitch.Control
          className={cx(
            'relative h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors',
            'bg-walpha-300 data-[state=checked]:bg-blue-600',
            'focus-visible:ring-2 focus-visible:ring-blue-500/40',
            'data-[disabled]:cursor-not-allowed',
          )}
        >
          <ArkSwitch.Thumb
            className={cx(
              'block h-5 w-5 translate-x-0.5 rounded-full bg-white shadow transition-transform',
              'data-[state=checked]:translate-x-[22px]',
            )}
          />
        </ArkSwitch.Control>
        <ArkSwitch.HiddenInput />
      </ArkSwitch.Root>
      {help && <span className={HELPER}>{help}</span>}
    </div>
  );
}

// --------------------------------------------------------------------------
// Select
// --------------------------------------------------------------------------

interface SelectItemShape {
  label: string;
  value: string;
}

interface SelectFieldProps {
  label: ReactNode;
  value: string[];
  onChange: (value: string[]) => void;
  collection: ListCollection<SelectItemShape>;
  placeholder?: string;
  help?: ReactNode;
  disabled?: boolean;
}

export function SelectField({
  label, value, onChange, collection, placeholder, help, disabled,
}: SelectFieldProps): JSX.Element {
  return (
    <ArkSelect.Root
      collection={collection}
      value={value}
      disabled={disabled}
      onValueChange={(e) => onChange(e.value)}
      positioning={{ sameWidth: true }}
      className="flex flex-col gap-2"
    >
      <ArkSelect.Label className={LABEL}>{label}</ArkSelect.Label>
      <ArkSelect.Control>
        <ArkSelect.Trigger
          className={cx(CONTROL, 'flex cursor-pointer items-center justify-between text-left')}
        >
          <ArkSelect.ValueText placeholder={placeholder} className="truncate" />
          {/* 用 SVG 而不是文字箭頭：文字箭頭會被字型與行高影響，各平台對不齊。 */}
          <ArkSelect.Indicator className="ml-2 shrink-0 text-walpha-600 transition-transform data-[state=open]:rotate-180">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M6 9l6 6 6-6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </ArkSelect.Indicator>
        </ArkSelect.Trigger>
      </ArkSelect.Control>
      {/* Positioner 不能省：它是 Ark 放置浮層的錨點，少了它選單會定位到左上角。 */}
      <ArkSelect.Positioner>
        <ArkSelect.Content
          className={cx(
            'z-[1500] max-h-64 overflow-y-auto rounded-md border border-walpha-200',
            'bg-zinc-800 p-1 shadow-xl outline-none',
          )}
        >
          {collection.items.map((item) => (
            <ArkSelect.Item
              key={item.value}
              item={item}
              className={cx(
                'flex cursor-pointer items-center justify-between gap-2 rounded px-2 py-1.5',
                'text-sm text-white',
                'data-[highlighted]:bg-walpha-200 data-[state=checked]:text-blue-400',
              )}
            >
              <ArkSelect.ItemText className="truncate">{item.label}</ArkSelect.ItemText>
              <ArkSelect.ItemIndicator className="shrink-0 text-blue-400">✓</ArkSelect.ItemIndicator>
            </ArkSelect.Item>
          ))}
        </ArkSelect.Content>
      </ArkSelect.Positioner>
      <ArkSelect.HiddenSelect />
      {help && <span className={HELPER}>{help}</span>}
    </ArkSelect.Root>
  );
}

// --------------------------------------------------------------------------
// Button
// --------------------------------------------------------------------------

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'solid' | 'outline' | 'ghost';
  /** 語意色。Chakra 版叫 colorPalette，這裡用 tone，免得看起來還在用 Chakra。 */
  tone?: 'blue' | 'red' | 'orange' | 'gray';
  size?: 'xs' | 'sm' | 'md';
  loading?: boolean;
  /** 載入中改顯示的文字（例如「儲存中…」）。省略就沿用原本的內容。 */
  loadingText?: string;
}

const BUTTON_SIZE = {
  xs: 'px-2 py-1 text-xs gap-1.5',
  sm: 'px-3 py-1.5 text-sm gap-2',
  md: 'px-4 py-2 text-sm gap-2',
} as const;

// 每個語意色三種變體。展開寫而不是用字串拼 `bg-${tone}-600`——Tailwind 是靠
// 掃描原始碼找 class 字面量的，拼出來的 class 不會出現在產出的 CSS 裡，而且
// 不會有任何錯誤，只是顏色安靜地消失。
const BUTTON_TONE = {
  blue: {
    solid: 'bg-blue-600 text-white hover:bg-blue-500',
    outline: 'border border-blue-500/60 text-blue-300 hover:bg-blue-500/10',
    ghost: 'text-blue-300 hover:bg-blue-500/10',
  },
  red: {
    solid: 'bg-red-600 text-white hover:bg-red-500',
    outline: 'border border-red-500/60 text-red-300 hover:bg-red-500/10',
    ghost: 'text-red-300 hover:bg-red-500/10',
  },
  orange: {
    solid: 'bg-orange-600 text-white hover:bg-orange-500',
    outline: 'border border-orange-500/60 text-orange-300 hover:bg-orange-500/10',
    ghost: 'text-orange-300 hover:bg-orange-500/10',
  },
  gray: {
    solid: 'bg-walpha-300 text-white hover:bg-walpha-400',
    outline: 'border border-walpha-400 text-white hover:border-walpha-600 hover:bg-walpha-200',
    ghost: 'text-walpha-800 hover:bg-walpha-200',
  },
} as const;

export function Button({
  variant = 'solid', tone = 'blue', size = 'sm', loading = false, loadingText,
  disabled, children, className, ...rest
}: ButtonProps): JSX.Element {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center rounded-md font-medium',
        'transition-colors outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40',
        'disabled:cursor-not-allowed disabled:opacity-40',
        BUTTON_SIZE[size],
        BUTTON_TONE[tone][variant],
        className,
      )}
      {...rest}
    >
      {loading && (
        <span
          className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      )}
      {loading && loadingText ? loadingText : children}
    </button>
  );
}

// --------------------------------------------------------------------------
// Textarea
// --------------------------------------------------------------------------

interface TextareaFieldProps {
  label?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  help?: ReactNode;
  rows?: number;
  disabled?: boolean;
}

export function TextareaField({
  label, value, onChange, placeholder, help, rows = 6, disabled,
}: TextareaFieldProps): JSX.Element {
  const field = (
    <textarea
      className={cx(CONTROL, 'resize-y leading-relaxed')}
      rows={rows}
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    />
  );
  if (label === undefined) return field;
  return <Field label={label} help={help}>{field}</Field>;
}

// --------------------------------------------------------------------------
// HelpIcon：標籤旁的問號，hover 顯示說明
// --------------------------------------------------------------------------

export function HelpIcon({ content }: { content: ReactNode }): JSX.Element {
  return (
    <ArkTooltip.Root
      openDelay={200}
      closeDelay={100}
      // overflowPadding 讓浮層被抽屜邊緣擠到時自己retreat，不會半截跑到畫面外。
      positioning={{ gutter: 6, overflowPadding: 8 }}
    >
      <ArkTooltip.Trigger asChild>
        {/* type=button：預設是 submit，包在表單裡時按下去會送出表單。 */}
        <button type="button" className="ml-1 cursor-help text-zinc-400 hover:text-white">
          <HiQuestionMarkCircle size={14} />
        </button>
      </ArkTooltip.Trigger>
      <ArkTooltip.Positioner>
        <ArkTooltip.Content
          className={cx(
            'z-[1600] max-w-[300px] rounded-md border border-walpha-200 bg-zinc-800',
            'px-3 py-2 text-sm leading-snug text-white shadow-xl',
            // 觸發器住在 NumberInput.Label 裡面，而標籤是 whitespace-nowrap
            // （標籤本來就不該折行）。浮層是它的子孫，會繼承到那個 nowrap，
            // 於是 max-w 明明生效、文字卻不折行，整條溢出到抽屜外面。
            'whitespace-normal',
          )}
        >
          {content}
        </ArkTooltip.Content>
      </ArkTooltip.Positioner>
    </ArkTooltip.Root>
  );
}

// --------------------------------------------------------------------------
// NumberField
// --------------------------------------------------------------------------

interface NumberFieldProps {
  label: ReactNode;
  value: string | number;
  onChange: (value: string) => void;
  min?: number;
  max?: number;
  step?: number;
  allowMouseWheel?: boolean;
  help?: ReactNode;
}

export function NumberField({
  label, value, onChange, min, max, step, allowMouseWheel, help,
}: NumberFieldProps): JSX.Element {
  return (
    <ArkNumberInput.Root
      // Chakra 版帶著 pattern/inputMode，讓行動裝置跳出數字鍵盤、也擋掉非數字。
      // 這兩個屬性是 zag 直接轉發到 input 上的，不是 Chakra 的東西，照搬即可。
      pattern="[0-9]*\.?[0-9]*"
      inputMode="decimal"
      value={value.toString()}
      onValueChange={(details) => onChange(details.value)}
      min={min}
      max={max}
      step={step}
      allowMouseWheel={allowMouseWheel}
      className="flex flex-col items-stretch gap-1 sm:flex-row sm:items-center sm:gap-2"
    >
      <ArkNumberInput.Label className={cx(LABEL, 'flex sm:w-[120px] sm:shrink-0 sm:items-center')}>
        {label}
        {help && <HelpIcon content={help} />}
      </ArkNumberInput.Label>
      <div className="relative flex-1">
        <ArkNumberInput.Input className={cx(CONTROL, 'pr-7')} />
        {/* 增減鈕疊在輸入框右側。Chakra 版靠 recipe 排版，這裡直接絕對定位——
            兩顆各佔一半高度，維持跟輸入框同高。 */}
        <ArkNumberInput.Control className="absolute right-0 top-0 flex h-full w-6 flex-col">
          <ArkNumberInput.IncrementTrigger
            className="flex flex-1 cursor-pointer items-center justify-center text-walpha-600 hover:text-white"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M6 15l6-6 6 6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </ArkNumberInput.IncrementTrigger>
          <ArkNumberInput.DecrementTrigger
            className="flex flex-1 cursor-pointer items-center justify-center text-walpha-600 hover:text-white"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </ArkNumberInput.DecrementTrigger>
        </ArkNumberInput.Control>
      </div>
    </ArkNumberInput.Root>
  );
}

// --------------------------------------------------------------------------
// SliderField：拉桿 + 右側數值
// --------------------------------------------------------------------------
//
// 給「連續調整、想邊拉邊聽結果」的設定用（目前是語音音量）。NumberField 的
// 上下鈕一次只動一步，要從 100% 拉到 400% 得按 60 次；音量這種東西也不會有人
// 想精確輸入某個數字，拉桿才是對的形狀。
//
// 用 Ark 的 Slider 而不是原生 <input type="range">：鍵盤操作、ARIA、拖曳狀態
// 全部跟抽屜裡其他 Ark 元件一致，樣式層才是我們要寫的部分。
//
// Ark 的 value 是陣列（支援多把手），這裡固定單一把手，對外只收／回 number。

interface SliderFieldProps {
  label: ReactNode;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  /** 數值右側的單位字串，例如 '%'。 */
  unit?: string;
  help?: ReactNode;
  disabled?: boolean;
}

export function SliderField({
  label, value, onChange, min = 0, max = 100, step = 1, unit = '', help, disabled,
}: SliderFieldProps): JSX.Element {
  return (
    <ArkSlider.Root
      value={[value]}
      // onValueChange 是拖曳過程中每一步都會觸發（不是放開才觸發）——這正是
      // 這個控制項要的：邊拉邊生效，放開之前就聽得到差別。
      onValueChange={(details) => onChange(details.value[0])}
      min={min}
      max={max}
      step={step}
      disabled={disabled}
      className="flex flex-col items-stretch gap-1 sm:flex-row sm:items-center sm:gap-2"
    >
      <ArkSlider.Label className={cx(LABEL, 'flex sm:w-[120px] sm:shrink-0 sm:items-center')}>
        {label}
        {help && <HelpIcon content={help} />}
      </ArkSlider.Label>
      <ArkSlider.Control className="relative flex flex-1 items-center py-2">
        <ArkSlider.Track className="h-1 w-full rounded-full bg-walpha-200">
          <ArkSlider.Range className="h-full rounded-full bg-blue-500" />
        </ArkSlider.Track>
        <ArkSlider.Thumb
          index={0}
          className={cx(
            'block h-3.5 w-3.5 rounded-full bg-white shadow ring-offset-0 outline-none',
            'focus-visible:ring-2 focus-visible:ring-blue-500/60',
            'data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50',
          )}
        >
          {/* 表單語意與鍵盤輸入靠這個隱藏 input，Ark 要求它掛在 Thumb 底下。 */}
          <ArkSlider.HiddenInput />
        </ArkSlider.Thumb>
      </ArkSlider.Control>
      {/* 數值靠右固定寬度，拖動時不會因為位數變化把拉桿推來推去。 */}
      <span className="w-12 shrink-0 self-end text-right text-xs tabular-nums text-walpha-600 sm:self-auto">
        {value}
        {unit}
      </span>
    </ArkSlider.Root>
  );
}

// --------------------------------------------------------------------------
// Tooltip：受控版，給「hover 才顯示、由呼叫端決定開關」的面板用
// --------------------------------------------------------------------------

interface TooltipProps {
  content: ReactNode;
  /** 省略就走 Ark 自己的 hover／focus 開關；給值就是完全受控。 */
  open?: boolean;
  children: ReactNode;
}

export function Tooltip({ content, open, children }: TooltipProps): JSX.Element {
  return (
    <ArkTooltip.Root
      open={open}
      openDelay={200}
      closeDelay={100}
      positioning={{ gutter: 6, overflowPadding: 8 }}
    >
      <ArkTooltip.Trigger asChild>{children}</ArkTooltip.Trigger>
      <ArkTooltip.Positioner>
        <ArkTooltip.Content
          className={cx(
            'z-[1600] max-w-[300px] whitespace-normal rounded-md border border-walpha-200',
            'bg-zinc-800 px-3 py-2 text-sm leading-snug text-white shadow-xl',
          )}
        >
          {content}
        </ArkTooltip.Content>
      </ArkTooltip.Positioner>
    </ArkTooltip.Root>
  );
}

// --------------------------------------------------------------------------
// Checkbox
// --------------------------------------------------------------------------

interface CheckboxProps {
  checked: boolean;
  onCheckedChange: (details: { checked: boolean | 'indeterminate' }) => void;
  children?: ReactNode;
  disabled?: boolean;
}

export function Checkbox({
  checked, onCheckedChange, children, disabled,
}: CheckboxProps): JSX.Element {
  return (
    <ArkCheckbox.Root
      checked={checked}
      disabled={disabled}
      onCheckedChange={(e) => onCheckedChange({ checked: e.checked })}
      className="flex cursor-pointer items-center gap-2 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
    >
      <ArkCheckbox.Control
        className={cx(
          'flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors',
          'border-walpha-400 bg-walpha-100',
          'data-[state=checked]:border-blue-600 data-[state=checked]:bg-blue-600',
          'focus-visible:ring-2 focus-visible:ring-blue-500/40',
        )}
      >
        <ArkCheckbox.Indicator>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 13l4 4L19 7" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </ArkCheckbox.Indicator>
      </ArkCheckbox.Control>
      {children && <ArkCheckbox.Label className={LABEL}>{children}</ArkCheckbox.Label>}
      <ArkCheckbox.HiddenInput />
    </ArkCheckbox.Root>
  );
}
