/* eslint-disable import/order */
/* eslint-disable no-use-before-define */
import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { settingsDirty } from '@/utils/settings-dirty';
import { BgUrlContextState } from '@/context/bgurl-context';
import { defaultBaseUrl, defaultWsUrl } from '@/context/websocket-context';
import { useSubtitle } from '@/context/subtitle-context';
import { useCamera } from '@/context/camera-context';
import { loadVoiceVolume, saveVoiceVolume } from '@/utils/voice-volume';
import i18n from 'i18next';

export const IMAGE_COMPRESSION_QUALITY_KEY = 'appImageCompressionQuality';
export const DEFAULT_IMAGE_COMPRESSION_QUALITY = 0.8;
export const IMAGE_MAX_WIDTH_KEY = 'appImageMaxWidth';
export const DEFAULT_IMAGE_MAX_WIDTH = 0;

interface GeneralSettings {
  language: string[]
  customBgUrl: string
  selectedBgUrl: string[]
  backgroundUrl: string
  useCameraBackground: boolean
  wsUrl: string
  baseUrl: string
  showSubtitle: boolean
  imageCompressionQuality: number;
  imageMaxWidth: number;
  // 角色語音的播放音量（0.0–1.0）。存取邏輯在 utils/voice-volume.ts，因為讀取端
  // 不是這裡而是播放端（use-audio-task），見該檔案檔頭。
  voiceVolume: number;
}

interface UseGeneralSettingsProps {
  bgUrlContext: BgUrlContextState | null
  baseUrl: string
  wsUrl: string
  onWsUrlChange: (url: string) => void
  onBaseUrlChange: (url: string) => void
  onCancel?: (callback: () => void) => () => void
}

const loadInitialCompressionQuality = (): number => {
  const storedQuality = localStorage.getItem(IMAGE_COMPRESSION_QUALITY_KEY);
  if (storedQuality) {
    const quality = parseFloat(storedQuality);
    if (!Number.isNaN(quality) && quality >= 0.1 && quality <= 1.0) {
      return quality;
    }
  }
  return DEFAULT_IMAGE_COMPRESSION_QUALITY;
};

const loadInitialImageMaxWidth = (): number => {
  const storedMaxWidth = localStorage.getItem(IMAGE_MAX_WIDTH_KEY);
  if (storedMaxWidth) {
    const maxWidth = parseInt(storedMaxWidth, 10);
    if (!Number.isNaN(maxWidth) && maxWidth >= 0) {
      return maxWidth;
    }
  }
  return DEFAULT_IMAGE_MAX_WIDTH;
};

export const useGeneralSettings = ({
  bgUrlContext,
  baseUrl,
  wsUrl,
  onWsUrlChange,
  onBaseUrlChange,
  onCancel,
}: UseGeneralSettingsProps) => {
  const { showSubtitle, setShowSubtitle } = useSubtitle();
  const { startBackgroundCamera, stopBackgroundCamera } = useCamera();

  const getCurrentBgKey = (): string[] => {
    if (!bgUrlContext?.backgroundUrl) return [];
    const currentBgUrl = bgUrlContext.backgroundUrl;
    const path = currentBgUrl.replace(baseUrl, '');
    return path.startsWith('/bg/') ? [path] : [];
  };

  const initialSettings: GeneralSettings = {
    language: [i18n.language || 'en'],
    customBgUrl: !bgUrlContext?.backgroundUrl?.includes('/bg/')
      ? bgUrlContext?.backgroundUrl || ''
      : '',
    selectedBgUrl: getCurrentBgKey(),
    backgroundUrl: bgUrlContext?.backgroundUrl || '',
    useCameraBackground: bgUrlContext?.useCameraBackground || false,
    wsUrl: wsUrl || defaultWsUrl,
    baseUrl: baseUrl || defaultBaseUrl,
    showSubtitle,
    imageCompressionQuality: loadInitialCompressionQuality(),
    imageMaxWidth: loadInitialImageMaxWidth(),
    voiceVolume: loadVoiceVolume(),
  };

  const [settings, setSettings] = useState<GeneralSettings>(initialSettings);

  // 一條規則：改了就生效。
  //
  // 抽屜裡多數區塊（記憶、場景、演出、人設、角色、動作設定、MCP、頭像…）本來
  // 就是即時存檔的，只有這幾個分頁的上半部曾經是草稿制。結果是同一個捲動面板
  // 裡兩個長得一樣的 switch 行為不同——上面那個要按套用、下面那個不用，而畫面
  // 上沒有任何東西能讓人分辨。統一成即時之後只剩一句話要記：改了就生效。
  //
  // 唯一的例外是 WebSocket／伺服器位址，見下面 connection 那一段：那兩個欄位
  // 即時生效不只是體驗問題，是 bug。onWsUrlChange 寫進 useLocalStorage（無
  // debounce），而 websocket-handler 有
  // `useEffect(() => wsService.connect(wsUrl), [wsUrl])`——改一次位址會對每一段
  // 半截的字串各發起一次連線，每次都把現有連線踢掉。所以它們有自己的按鈕。
  const applySettings = useCallback((next: GeneralSettings): void => {
    setShowSubtitle(next.showSubtitle);

    if (bgUrlContext) {
      bgUrlContext.setUseCameraBackground(next.useCameraBackground);
      const newBgUrl = next.customBgUrl || next.selectedBgUrl[0];
      if (newBgUrl) {
        const fullUrl = newBgUrl.startsWith('http') ? newBgUrl : `${baseUrl}${newBgUrl}`;
        bgUrlContext.setBackgroundUrl(fullUrl);
      }
    }

    // 攝像頭在這裡才真的開關。草稿階段就啟動的話，光是把開關撥過去看看就會
    // 跳出系統權限詢問、鏡頭燈亮起——而使用者可能根本還沒決定要不要用。
    if (next.useCameraBackground) {
      startBackgroundCamera().catch((error) => {
        // 提示由 camera-context.startBackgroundCamera 負責（錯誤發生在那裡，
        // 而且它有 DOMException 的 name 可以分辨原因）。這裡再彈一次就會變成
        // 同一個失敗跳兩個 toast。
        console.error('Failed to start camera:', error);
      });
    } else {
      stopBackgroundCamera();
    }

    if (next.language?.[0] && next.language[0] !== i18n.language) {
      i18n.changeLanguage(next.language[0]);
    }

    localStorage.setItem(IMAGE_COMPRESSION_QUALITY_KEY, next.imageCompressionQuality.toString());
    localStorage.setItem(IMAGE_MAX_WIDTH_KEY, next.imageMaxWidth.toString());
    // 不需要另外通知播放端：use-audio-task 每段音訊播放前都自己重讀一次
    // localStorage，所以這裡寫完，下一句就是新音量。
    saveVoiceVolume(next.voiceVolume);
  }, [
    bgUrlContext, baseUrl,
    setShowSubtitle, startBackgroundCamera, stopBackgroundCamera,
  ]);

  // 即時施加。跳過第一次（掛載時的值就是現值，重跑一次只會多開一次攝像頭）。
  const mounted = useRef(false);
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    applySettings(settings);
  }, [settings, applySettings]);

  // 這裡以前有一個 effect，在 confName 變動時把 selectedCharacterPreset 同步進
  // settings。那個欄位拿掉之後它就只剩「把 settings 原封不動複製一份、順便把
  // originalSettings 設成當下的值」——等於在切角色的瞬間悄悄丟掉還原基準，
  // 使用者尚未套用的修改就再也還原不回去。沒有需要同步的東西了，整段移除。

  // handleCancel 每次 render 都是新的函式實體，閉包裡綁著當下那份 originalSettings。
  // 這個 effect 只在掛載時跑一次（onCancel 是穩定的 useCallback），所以直接註冊
  // handleCancel 會讓抽屜永遠拿到掛載當下的快照——使用者改了背景、按「套用」、
  // 再關掉抽屜，還原邏輯會用開啟抽屜時的舊值把剛套用的設定蓋回去。
  // 用 ref 轉一手，讓註冊進去的閉包永遠呼叫到最新的 handleCancel。
  const handleCancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!onCancel) return;

    const cleanupCancel = onCancel(() => {
      handleCancelRef.current?.();
    });

    return () => {
      cleanupCancel?.();
    };
  }, [onCancel]);

  const handleSettingChange = (
    key: keyof GeneralSettings,
    value: GeneralSettings[keyof GeneralSettings],
  ): void => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  // ---- 連線位址：整個抽屜裡唯一還需要按按鈕的地方 ----
  //
  // 這兩個欄位不能邊打邊生效（見上方說明：每個字元一次重連）。所以它們獨立成
  // 一個小草稿，按「連線」才送出。這是規則的例外，不是規則的一部分——所以它有
  // 自己的按鈕、就放在那兩個欄位旁邊，而不是分頁底部一顆管很多東西的按鈕。
  const [connDraft, setConnDraft] = useState({
    wsUrl: initialSettings.wsUrl,
    baseUrl: initialSettings.baseUrl,
  });
  const [connApplied, setConnApplied] = useState(connDraft);

  const connectionDirty = useMemo(
    () => settingsDirty(connDraft, connApplied),
    [connDraft, connApplied],
  );

  const setConnectionField = (key: 'wsUrl' | 'baseUrl', value: string): void => {
    setConnDraft((prev) => ({ ...prev, [key]: value }));
  };

  const applyConnection = (): void => {
    onWsUrlChange(connDraft.wsUrl);
    onBaseUrlChange(connDraft.baseUrl);
    setConnApplied(connDraft);
    setSettings((prev) => ({ ...prev, wsUrl: connDraft.wsUrl, baseUrl: connDraft.baseUrl }));
  };

  const revertConnection = (): void => setConnDraft(connApplied);

  // 抽屜關閉時把還沒送出的連線草稿丟掉，免得下次打開看到一個沒生效的位址。
  handleCancelRef.current = revertConnection;

  // 攝像頭在切換的當下就開／關。這是使用者按下這個開關時期待發生的事——
  // 「使用攝像頭背景」撥開就是要用攝像頭。
  const handleCameraToggle = (checked: boolean): void => {
    handleSettingChange('useCameraBackground', checked);
  };

  return {
    settings,
    handleSettingChange,
    handleCameraToggle,
    connection: connDraft,
    connectionDirty,
    setConnectionField,
    applyConnection,
    revertConnection,
    // 開關要顯示草稿值、寫回草稿，不能直接接字幕 context——否則這一個開關會
    // 是整個分頁裡唯一一個「不按套用就生效」的東西。
    showSubtitle: settings.showSubtitle,
    setShowSubtitle: (value: boolean) => handleSettingChange('showSubtitle', value),
  };
};
