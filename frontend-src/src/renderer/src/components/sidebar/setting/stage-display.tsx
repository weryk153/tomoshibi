// 舞台頁的「字幕、音量與背景」。背景下一步會併進場景（規格：只有一個地方決定
// 背景），這裡先原樣從原本的「一般」分頁搬過來。每一項改了就生效。
//
// 這裡不再經過 useGeneralSettings：那個 hook 把十個欄位放在一份快照裡，任何一欄
// 改了就整份重套一次。分到不同分頁之後，這一頁的快照會把系統頁剛改的介面語言
// 蓋回去，所以每一項都直接呼叫自己的 context／localStorage。
import { useState, useRef, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Box, HStack, Stack, Text } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useBgUrl } from '@/context/bgurl-context';
import { useSubtitle } from '@/context/subtitle-context';
import { useCamera } from '@/context/camera-context';
import { useWebSocket } from '@/context/websocket-context';
import { loadVoiceVolume, saveVoiceVolume } from '@/utils/voice-volume';
import { uploadBackground, validateBackgroundFile } from '@/api/background.ts';
import { Button, Field } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { SelectField, SwitchField, InputField, SliderField } from './common';

function StageDisplay(): JSX.Element {
  const { t } = useTranslation();
  const bg = useBgUrl();
  const { showSubtitle, setShowSubtitle } = useSubtitle();
  const { startBackgroundCamera, stopBackgroundCamera } = useCamera();
  const { baseUrl, sendMessage } = useWebSocket();

  const [voiceVolume, setVoiceVolume] = useState(loadVoiceVolume);

  const currentUrl = bg?.backgroundUrl ?? '';
  const currentPath = currentUrl.replace(baseUrl, '');
  const selectedBg = currentPath.startsWith('/bg/') ? [currentPath] : [];
  const [customBgDraft, setCustomBgDraft] = useState(currentPath.startsWith('/bg/') ? '' : currentUrl);
  // 背景選取的世代計數器：上傳期間使用者換了選取（下拉選單／自訂網址／攝影機），
  // 上傳完成時就不把新檔案蓋回目前選取，只更新清單。
  const bgSelectionSessionRef = useRef(0);

  const backgrounds = useMemo(() => createListCollection({
    items: (bg?.backgroundFiles ?? []).map((filename) => ({
      label: String(filename),
      value: `/bg/${filename}`,
    })),
  }), [bg?.backgroundFiles]);

  const showBackground = useCallback((url: string): void => {
    if (!bg || !url) return;
    bg.setBackgroundUrl(url.startsWith('http') ? url : `${baseUrl}${url}`);
  }, [bg, baseUrl]);

  // 自訂背景網址：停手就套用，空白不存。
  const customBgSaver = useAutosave(async (url: string) => {
    bgSelectionSessionRef.current += 1;
    showBackground(url.trim());
    return { ok: true } as const;
  }, { validate: (url) => (url.trim() ? null : t('settings.general.customBgUrlEmpty')) });

  const toggleCamera = (checked: boolean): void => {
    // 切去攝影機背景等於放棄目前的背景圖片選取，背景上傳的世代守衛也要算上。
    bgSelectionSessionRef.current += 1;
    bg?.setUseCameraBackground(checked);
    if (checked) {
      startBackgroundCamera().catch((error) => {
        console.error('Failed to start camera:', error);
      });
    } else {
      stopBackgroundCamera();
    }
  };

  // 背景圖片上傳：POST /api/background 把檔案寫進磁碟，立刻生效、不可還原。
  const [bgUploading, setBgUploading] = useState(false);
  const [bgUploadError, setBgUploadError] = useState<string | null>(null);
  const bgFileInputRef = useRef<HTMLInputElement | null>(null);

  const handleBackgroundFile = useCallback(async (file: File) => {
    setBgUploadError(null);
    const invalid = validateBackgroundFile(file);
    if (invalid) {
      setBgUploadError(
        t(invalid === 'notImage' ? 'settings.general.bgNotImage' : 'settings.general.bgTooLarge'),
      );
      return;
    }

    const session = bgSelectionSessionRef.current;
    setBgUploading(true);
    const result = await uploadBackground(baseUrl, file);
    setBgUploading(false);

    if (!result.ok) {
      setBgUploadError(result.error || t('settings.general.bgUploadFailed'));
      return;
    }

    // 背景清單靠 WebSocket 的 fetch-backgrounds／background-files 往返維持，
    // 「刷新」是重送這則訊息。
    sendMessage({ type: 'fetch-backgrounds' });

    toaster.create({
      title: t('settings.general.bgUploaded'),
      type: 'success',
      duration: 3000,
    });

    if (bgSelectionSessionRef.current !== session) return;
    bgSelectionSessionRef.current += 1;
    showBackground(`/bg/${result.data.filename}`);
    setCustomBgDraft('');
  }, [baseUrl, sendMessage, t, showBackground]);

  const cameraOn = bg?.useCameraBackground ?? false;

  return (
    <Stack gap={4}>
      <SwitchField
        label={t('settings.general.useCameraBackground')}
        checked={cameraOn}
        onChange={toggleCamera}
      />

      <SwitchField
        label={t('settings.general.showSubtitle')}
        checked={showSubtitle}
        onChange={setShowSubtitle}
      />

      {/* 語音音量。以百分比呈現、內部存 0–5，跟演出的配樂音量同一個做法。
          上限是 500%：GPT-SoVITS 的輸出實測 RMS 只有 -35 dBFS，100% 已經太小聲；
          超過 100% 的部分走 Web Audio 的 GainNode，見 utils/voice-gain.ts。
          寫進 localStorage 之後，下一段音訊播放前會自己重讀，即時生效。 */}
      <SliderField
        label={t('settings.general.voiceVolume')}
        value={Math.round(voiceVolume * 100)}
        min={0}
        max={500}
        step={5}
        unit="%"
        onChange={(pct) => { setVoiceVolume(pct / 100); saveVoiceVolume(pct / 100); }}
        help={t('settings.general.voiceVolumeHelp')}
      />

      {!cameraOn && (
        <>
          {/* 上傳中停用下拉選單，跟 handleBackgroundFile 的世代守衛互相配合。 */}
          <Box
            opacity={bgUploading ? 0.5 : 1}
            pointerEvents={bgUploading ? 'none' : 'auto'}
          >
            <SelectField
              label={t('settings.general.backgroundImage')}
              value={selectedBg}
              onChange={(value) => {
                bgSelectionSessionRef.current += 1;
                showBackground(value[0] ?? '');
                setCustomBgDraft('');
              }}
              collection={backgrounds}
              placeholder={t('settings.general.backgroundImage')}
            />
          </Box>

          <Stack gap={1}>
            <InputField
              label={t('settings.general.customBgUrl')}
              value={customBgDraft}
              onChange={(value) => {
                setCustomBgDraft(value);
                customBgSaver.change(value);
              }}
              onBlur={customBgSaver.flush}
              placeholder={t('settings.general.customBgUrlPlaceholder')}
            />
            <SaveStatus state={customBgSaver.state} />
          </Stack>
        </>
      )}

      <Field
        label={t('settings.general.bgUploadLabel')}
        help={t('settings.general.bgUploadHelp')}
      >
        <HStack>
          <input
            ref={bgFileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/gif"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              if (file) handleBackgroundFile(file);
            }}
          />
          <Button
            size="xs"
            variant="outline"
            onClick={() => bgFileInputRef.current?.click()}
            loading={bgUploading}
            disabled={bgUploading}
          >
            {t('settings.general.bgUpload')}
          </Button>
        </HStack>
        {bgUploadError && (
          <Text fontSize="xs" color="red.300">{bgUploadError}</Text>
        )}
      </Field>
    </Stack>
  );
}

export default StageDisplay;
