// 系統頁的基本設定：介面語言、伺服器連線、截圖壓縮。從原本的「一般」分頁搬來。
//
// 連線是整個抽屜裡唯一要按按鈕的地方：這兩個欄位每改一個字元就會重連一次，
// 必須等使用者打完才送。關抽屜時丟掉沒按「連線」的草稿（onCancel）。
import { useState, useMemo, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Stack, Text } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useWebSocket, defaultBaseUrl, defaultWsUrl } from '@/context/websocket-context';
import { settingsDirty } from '@/utils/settings-dirty';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { boundsMessage, parseBoundedNumber, type Bounds } from '@/utils/setting-values';
import {
  IMAGE_COMPRESSION_QUALITY_KEY, IMAGE_MAX_WIDTH_KEY, loadImageQuality, loadImageMaxWidth,
} from '@/utils/image-settings';
import { SelectField, InputField, TabActions } from './common';

const LANGUAGES = [
  { label: 'English', value: 'en' },
  { label: '繁體中文', value: 'zh' },
  { label: '简体中文', value: 'zh-CN' },
  { label: '日本語', value: 'ja' },
  { label: '한국어', value: 'ko' },
];
const QUALITY_BOUNDS: Bounds = { min: 0.1, max: 1 };
const WIDTH_BOUNDS: Bounds = { min: 0, integer: true };

interface SystemBasicsProps {
  onCancel?: (callback: () => void) => () => void
}

function SystemBasics({ onCancel }: SystemBasicsProps): JSX.Element {
  const { t, i18n } = useTranslation();
  const {
    wsUrl, setWsUrl, baseUrl, setBaseUrl,
  } = useWebSocket();
  const languages = useMemo(() => createListCollection({ items: LANGUAGES }), []);
  const boundsText = (bounds: Bounds): string => {
    const message = boundsMessage(bounds);
    return t(message.key, message.params);
  };

  const [connApplied, setConnApplied] = useState(() => ({
    wsUrl: wsUrl || defaultWsUrl,
    baseUrl: baseUrl || defaultBaseUrl,
  }));
  const [connDraft, setConnDraft] = useState(connApplied);
  const connectionDirty = settingsDirty(connDraft, connApplied);
  const applyConnection = (): void => {
    setWsUrl(connDraft.wsUrl);
    setBaseUrl(connDraft.baseUrl);
    setConnApplied(connDraft);
  };
  const revertConnection = (): void => setConnDraft(connApplied);
  // 註冊只做一次，用 ref 拿最新的還原。
  const revertRef = useRef(revertConnection);
  revertRef.current = revertConnection;
  useEffect(() => {
    if (!onCancel) return undefined;
    return onCancel(() => revertRef.current());
  }, [onCancel]);

  // 圖片壓縮品質、最大寬度：欄位保留使用者打的字，合法才存。
  const [qualityText, setQualityText] = useState(
    () => String(loadImageQuality(localStorage.getItem(IMAGE_COMPRESSION_QUALITY_KEY))),
  );
  const [widthText, setWidthText] = useState(
    () => String(loadImageMaxWidth(localStorage.getItem(IMAGE_MAX_WIDTH_KEY))),
  );
  const qualitySaver = useAutosave(async (text: string) => {
    localStorage.setItem(IMAGE_COMPRESSION_QUALITY_KEY, String(parseBoundedNumber(text, QUALITY_BOUNDS)));
    return { ok: true } as const;
  }, { validate: (text) => (parseBoundedNumber(text, QUALITY_BOUNDS) === null ? boundsText(QUALITY_BOUNDS) : null) });
  const widthSaver = useAutosave(async (text: string) => {
    localStorage.setItem(IMAGE_MAX_WIDTH_KEY, String(parseBoundedNumber(text, WIDTH_BOUNDS)));
    return { ok: true } as const;
  }, { validate: (text) => (parseBoundedNumber(text, WIDTH_BOUNDS) === null ? boundsText(WIDTH_BOUNDS) : null) });

  return (
    <Stack gap={4}>
      <SelectField
        label={t('settings.general.language')}
        value={[i18n.language]}
        onChange={(value) => {
          if (value[0] && value[0] !== i18n.language) i18n.changeLanguage(value[0]);
        }}
        collection={languages}
        placeholder={t('settings.general.language')}
      />

      <Stack gap={2} pt={3} borderTopWidth="1px" borderColor="whiteAlpha.200">
        <Text fontSize="sm" color="whiteAlpha.800" fontWeight="semibold">
          {t('settings.general.connectionSection')}
        </Text>
        <InputField
          label={t('settings.general.wsUrl')}
          value={connDraft.wsUrl}
          onChange={(value) => setConnDraft((prev) => ({ ...prev, wsUrl: value }))}
          placeholder={t('settings.general.wsUrlPlaceholder')}
        />
        <InputField
          label={t('settings.general.baseUrl')}
          value={connDraft.baseUrl}
          onChange={(value) => setConnDraft((prev) => ({ ...prev, baseUrl: value }))}
          placeholder={t('settings.general.baseUrlPlaceholder')}
          help={t('settings.general.connectionHelp')}
        />
        <TabActions
          dirty={connectionDirty}
          applyLabel={t('settings.general.connect')}
          onApply={applyConnection}
          onRevert={revertConnection}
        />
      </Stack>

      <InputField
        label={t('settings.general.imageCompressionQuality')}
        value={qualityText}
        onChange={(value) => { setQualityText(value); qualitySaver.change(value); }}
        onBlur={qualitySaver.flush}
        help={t('settings.general.imageCompressionQualityHelp')}
      />
      <SaveStatus state={qualitySaver.state} />

      <InputField
        label={t('settings.general.imageMaxWidth')}
        value={widthText}
        onChange={(value) => { setWidthText(value); widthSaver.change(value); }}
        onBlur={widthSaver.flush}
        help={t('settings.general.imageMaxWidthHelp')}
      />
      <SaveStatus state={widthSaver.state} />
    </Stack>
  );
}

export default SystemBasics;
