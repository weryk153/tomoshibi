import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
// 遷移中：這個分頁的表單控制項已改用 Ark UI + Tailwind（common-tw），版面容器
// 與下半部尚未遷移的區塊（You／MCP／背景上傳）仍是 Chakra。createListCollection
// 要從 Ark 拿——Chakra 匯出的那個雖然是同一個實作，型別上卻是 Chakra 的包裝，
// 傳進 Ark 的 Select 會對不起來。
import { Box, HStack, Stack, Text } from "@chakra-ui/react";
import { createListCollection } from "@ark-ui/react/collection";
import { useBgUrl } from "@/context/bgurl-context";
import { settingStyles } from "./setting-styles";
import { useGeneralSettings } from "@/hooks/sidebar/setting/use-general-settings";
import { useWebSocket } from "@/context/websocket-context";
import { SelectField, SwitchField, InputField, SliderField, NumberField, TabActions } from "./common";
import { Button } from "@/components/ui/tw/primitives";
import { Field } from '@/components/ui/tw/primitives';
import { toaster } from "@/components/ui/tw/toaster";
import { SaveStatus } from "@/components/ui/tw/save-status";
import { useAutosave } from "@/hooks/use-autosave";
import { boundsMessage, parseBoundedNumber, type Bounds } from "@/utils/setting-values";
import {
  fetchUseMcpp, setUseMcpp, fetchEngineSettings, saveEngineSettings,
  type EngineSettings, type EngineEvery,
} from "@/api/agent-config.ts";
import { uploadBackground, validateBackgroundFile } from "@/api/background.ts";
import You from "./you";

interface GeneralProps {
  onCancel?: (callback: () => void) => () => void;
}

// Data collection definition
const useCollections = () => {
  const { backgroundFiles } = useBgUrl() || {};

  const languages = createListCollection({
    items: [
      { label: "English", value: "en" },
      { label: "繁體中文", value: "zh" },
      { label: "简体中文", value: "zh-CN" },
      { label: "日本語", value: "ja" },
      { label: "한국어", value: "ko" },
    ],
  });

  const backgrounds = createListCollection({
    items:
      backgroundFiles?.map((filename) => ({
        label: String(filename),
        value: `/bg/${filename}`,
      })) || [],
  });

  return {
    languages,
    backgrounds,
  };
};

function General({ onCancel }: GeneralProps): JSX.Element {
  const { t, i18n } = useTranslation();
  const bgUrlContext = useBgUrl();
  const {
    wsUrl, setWsUrl, baseUrl, setBaseUrl, sendMessage,
  } = useWebSocket();
  const collections = useCollections();

  const {
    settings,
    handleSettingChange,
    handleCameraToggle,
    connection,
    connectionDirty,
    setConnectionField,
    applyConnection,
    revertConnection,
    showSubtitle,
    setShowSubtitle,
  } = useGeneralSettings({
    bgUrlContext,
    baseUrl,
    wsUrl,
    onWsUrlChange: setWsUrl,
    onBaseUrlChange: setBaseUrl,
    onCancel,
  });

  useEffect(() => {
    if (settings.language[0] !== i18n.language) {
      handleSettingChange("language", [i18n.language]);
    }
  }, [i18n.language, settings.language]);

  const [customBgDraft, setCustomBgDraft] = useState(settings.customBgUrl);
  // 背景選取的世代計數器（說明見下面 handleBackgroundFile 上方）。
  const bgSelectionSessionRef = useRef(0);

  // MCP 開關（工具／網路搜尋）：改了就存到 conf.yaml；要重新載入才生效，由抽屜
  // 頂端的提示處理。存失敗就退回原值。
  const [mcpEnabled, setMcpEnabled] = useState(false);
  const [mcpLoading, setMcpLoading] = useState(true);
  const [mcpLoadError, setMcpLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchUseMcpp(baseUrl);
      if (cancelled) return;
      setMcpLoading(false);
      if (result.ok) {
        setMcpEnabled(result.data);
      } else {
        setMcpLoadError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  const mcpSaver = useAutosave(async (checked: boolean) => {
    const result = await setUseMcpp(baseUrl, checked);
    if (result.ok) {
      setMcpEnabled(result.data.use_mcpp);
      return { ok: true } as const;
    }
    // 失敗就退回原值，不留一個「畫面上開著、conf.yaml 其實沒存到」的假象。
    setMcpEnabled(!checked);
    return { ok: false, error: result.error } as const;
  }, { delayMs: 0 });

  // 引擎驅動對話：開關與「每幾輪跑一次」的幾個數字，同樣直接寫 conf.yaml、
  // 存了要重啟。引擎裝不起來時開關是灰的，reason 說明為什麼。數字改了不是
  // 每敲一個字就寫一次檔——停手半秒再送。
  const [engine, setEngine] = useState<EngineSettings | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [everyDrafts, setEveryDrafts] = useState<Record<EngineEvery, string> | null>(null);
  // 背景工作另外用的模型：兩欄一起套用，填一半的話後端不會用。
  const [backgroundDraft, setBackgroundDraft] = useState<{ url: string; model: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchEngineSettings(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setEngine(result.data);
        setEveryDrafts({
          emotion_every: String(result.data.emotion_every),
          memory_every: String(result.data.memory_every),
          self_memory_every: String(result.data.self_memory_every),
          goal_every: String(result.data.goal_every),
          reflection_every: String(result.data.reflection_every),
          goals_shown: String(result.data.goals_shown),
          thoughts_shown: String(result.data.thoughts_shown),
        });
        setBackgroundDraft({
          url: result.data.background_base_url,
          model: result.data.background_model,
        });
      } else {
        setEngineError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  const EVERY_BOUNDS: Bounds = { min: 0, max: 99, integer: true };
  const boundsText = (bounds: Bounds): string => {
    const message = boundsMessage(bounds);
    return t(message.key, message.params);
  };

  // 「每幾輪跑一次」與「放在心上幾個」：停手才存，打到一半的值不存也不彈回。
  // 跟「後端最後一次確認存下的值」比，不跟畫面上一輪的 engine 比：上一筆剛存好、
  // 接著排的那筆在畫面重畫前就會跑，用 state 比會把「改回原值」誤判成沒變。
  const savedEngineRef = useRef<EngineSettings | null>(null);
  savedEngineRef.current = savedEngineRef.current ?? engine;
  const everySaver = useAutosave(async (drafts: Record<EngineEvery, string>) => {
    const saved = savedEngineRef.current;
    if (!saved) return { ok: true } as const;
    const changes: Partial<Record<EngineEvery, number>> = {};
    (Object.keys(drafts) as EngineEvery[]).forEach((key) => {
      const value = parseBoundedNumber(drafts[key], EVERY_BOUNDS);
      if (value !== null && value !== saved[key]) changes[key] = value;
    });
    if (Object.keys(changes).length === 0) return { ok: true } as const;
    const result = await saveEngineSettings(baseUrl, changes);
    if (!result.ok) return { ok: false, error: result.error } as const;
    savedEngineRef.current = { ...saved, ...result.data };
    setEngine((current) => (current ? { ...current, ...result.data } : current));
    return { ok: true } as const;
  }, {
    validate: (drafts) => (
      (Object.values(drafts) as string[]).some((v) => parseBoundedNumber(v, EVERY_BOUNDS) === null)
        ? boundsText(EVERY_BOUNDS)
        : null
    ),
  });

  const changeEvery = (key: EngineEvery, value: string): void => {
    if (!everyDrafts) return;
    const next = { ...everyDrafts, [key]: value };
    setEveryDrafts(next);
    everySaver.change(next);
  };

  // 背景工作另外用的模型：兩欄一起存，填一半的話後端不會用。
  const backgroundSaver = useAutosave(async (draft: { url: string; model: string }) => {
    const url = draft.url.trim();
    const model = draft.model.trim();
    const result = await saveEngineSettings(baseUrl, {
      background_base_url: url,
      background_model: model,
    });
    if (!result.ok) return { ok: false, error: result.error } as const;
    setEngine((current) => (current ? { ...current, ...result.data } : current));
    // 後端不寫它認為會弄壞設定檔的值（不是 http 網址、含引號或換行）。
    if (result.data.background_base_url !== url || result.data.background_model !== model) {
      return { ok: false, error: t("settings.general.engineBackgroundInvalid") } as const;
    }
    return { ok: true } as const;
  });

  const changeBackground = (field: 'url' | 'model', value: string): void => {
    if (!backgroundDraft) return;
    const next = { ...backgroundDraft, [field]: value };
    setBackgroundDraft(next);
    backgroundSaver.change(next);
  };

  // 自訂背景網址：停手就套用，空白不存。
  const customBgSaver = useAutosave(async (url: string) => {
    if (url.trim() === settings.customBgUrl) return { ok: true } as const;
    bgSelectionSessionRef.current += 1;
    handleSettingChange("selectedBgUrl", []);
    handleSettingChange("customBgUrl", url.trim());
    return { ok: true } as const;
  }, { validate: (url) => (url.trim() ? null : t("settings.general.customBgUrlEmpty")) });

  // 圖片壓縮品質、最大寬度：欄位保留使用者打的字，合法才存。
  const QUALITY_BOUNDS: Bounds = { min: 0.1, max: 1 };
  const WIDTH_BOUNDS: Bounds = { min: 0, integer: true };
  const [qualityText, setQualityText] = useState(String(settings.imageCompressionQuality));
  const [widthText, setWidthText] = useState(String(settings.imageMaxWidth));
  const qualitySaver = useAutosave(async (text: string) => {
    handleSettingChange("imageCompressionQuality", parseBoundedNumber(text, QUALITY_BOUNDS) as number);
    return { ok: true } as const;
  }, { validate: (text) => (parseBoundedNumber(text, QUALITY_BOUNDS) === null ? boundsText(QUALITY_BOUNDS) : null) });
  const widthSaver = useAutosave(async (text: string) => {
    handleSettingChange("imageMaxWidth", parseBoundedNumber(text, WIDTH_BOUNDS) as number);
    return { ok: true } as const;
  }, { validate: (text) => (parseBoundedNumber(text, WIDTH_BOUNDS) === null ? boundsText(WIDTH_BOUNDS) : null) });

  // 背景圖片上傳：POST /api/background 把檔案寫進磁碟，同樣是立刻生效、
  // 不可還原。
  const [bgUploading, setBgUploading] = useState(false);
  const [bgUploadError, setBgUploadError] = useState<string | null>(null);
  const bgFileInputRef = useRef<HTMLInputElement | null>(null);

  // 世代計數器：跟 characters.tsx 的 formSessionRef 同一種手法（見該檔案檔頭
  // 說明），防的是同一種事故——上傳這段 await 期間使用者可能已經手動改選了
  // 別的背景（下拉選單／自訂 URL／切去攝像頭背景），上傳完成時不能無條件把
  // 新檔案蓋回目前選取。這裡只有一個「目前選取」而不是多個表單，用遞增計數
  // 比對「上傳開始時」跟「上傳完成時」是否還是同一次選取意圖；不一致就只更新
  // 背景清單，不動使用者已經換過的選取。

  const handleBackgroundFile = useCallback(async (file: File) => {
    setBgUploadError(null);
    const invalid = validateBackgroundFile(file);
    if (invalid) {
      setBgUploadError(
        t(invalid === "notImage" ? "settings.general.bgNotImage" : "settings.general.bgTooLarge"),
      );
      return;
    }

    const session = bgSelectionSessionRef.current;
    setBgUploading(true);
    const result = await uploadBackground(baseUrl, file);
    setBgUploading(false);

    if (!result.ok) {
      setBgUploadError(result.error || t("settings.general.bgUploadFailed"));
      return;
    }

    // 重新抓一次背景清單：這裡的 backgroundFiles 是靠 WebSocket 的
    // fetch-backgrounds/background-files 往返維持的（見 bgurl-context.tsx／
    // websocket-handler.tsx），不是 REST GET，所以「刷新」是重送這則訊息。
    sendMessage({ type: "fetch-backgrounds" });

    toaster.create({
      title: t("settings.general.bgUploaded"),
      type: "success",
      duration: 3000,
    });

    if (bgSelectionSessionRef.current !== session) {
      // 使用者在上傳期間已經換了選取意圖，新檔案仍然上傳成功、也已經加進
      // 清單，但不強行把它設為目前選取。
      return;
    }
    bgSelectionSessionRef.current += 1;
    handleSettingChange("selectedBgUrl", [`/bg/${result.data.filename}`]);
    handleSettingChange("customBgUrl", "");
    setCustomBgDraft("");
  }, [baseUrl, sendMessage, t, handleSettingChange]);

  return (
    <Stack {...settingStyles.common.container}>
      <SelectField
        label={t("settings.general.language")}
        value={settings.language}
        onChange={(value) => handleSettingChange("language", value)}
        collection={collections.languages}
        placeholder={t("settings.general.language")}
      />

      <SwitchField
        label={t("settings.general.useCameraBackground")}
        checked={settings.useCameraBackground}
        onChange={(checked) => {
          // 切去攝像頭背景等於放棄目前的背景圖片選取，跟改選下拉選單／自訂
          // URL 是同一種「使用者換了選取意圖」，背景上傳的世代守衛也要算上。
          bgSelectionSessionRef.current += 1;
          handleCameraToggle(checked);
        }}
      />

      <SwitchField
        label={t("settings.general.showSubtitle")}
        checked={showSubtitle}
        onChange={setShowSubtitle}
      />

      {/* 語音音量。以百分比呈現、內部存 0–5，跟演出分頁的配樂音量同一個做法
          （performances.tsx 的 musicVolume），免得同樣是音量的兩個控制項一個
          用 0–1 一個用 0–100。step 用 5 也是照抄那裡。
          上限是 500% 而不是 100%：GPT-SoVITS 的輸出實測 RMS 只有 -35 dBFS，
          100%（即 .volume = 1.0）就是原始音量、已經太小聲。超過 100% 的部分
          走 Web Audio 的 GainNode，見 utils/voice-gain.ts。
          這是即時生效的：寫進 localStorage 之後，下一段音訊播放前會自己重讀。 */}
      <SliderField
        label={t("settings.general.voiceVolume")}
        value={Math.round(settings.voiceVolume * 100)}
        min={0}
        max={500}
        step={5}
        unit="%"
        onChange={(pct) => handleSettingChange("voiceVolume", pct / 100)}
        help={t("settings.general.voiceVolumeHelp")}
      />

      {!settings.useCameraBackground && (
        <>
          {/* 上傳中停用下拉選單：避免使用者在上傳這段 await 期間切選，跟下面
              handleBackgroundFile 的世代守衛互相配合，而不是唯一防線。 */}
          <Box
            opacity={bgUploading ? 0.5 : 1}
            pointerEvents={bgUploading ? "none" : "auto"}
          >
            <SelectField
              label={t("settings.general.backgroundImage")}
              value={settings.selectedBgUrl}
              onChange={(value) => {
                bgSelectionSessionRef.current += 1;
                handleSettingChange("selectedBgUrl", value);
                handleSettingChange("customBgUrl", "");
                setCustomBgDraft("");
              }}
              collection={collections.backgrounds}
              placeholder={t("settings.general.backgroundImage")}
            />
          </Box>

          <Stack gap={1}>
            <InputField
              label={t("settings.general.customBgUrl")}
              value={customBgDraft}
              onChange={(value) => {
                setCustomBgDraft(value);
                // 每次都排：打了又改回原值時，存檔器才會送最後那個（而不是中間打的字）。
                customBgSaver.change(value);
              }}
              onBlur={customBgSaver.flush}
              placeholder={t("settings.general.customBgUrlPlaceholder")}
            />
            <SaveStatus state={customBgSaver.state} />
          </Stack>
        </>
      )}

      {/* 角色切換以前在這裡有第二個入口，名字還不一樣（「角色預設」）。除了讓
          人找不到之外，它的「還原」是壞的：handleCancel 只把 confName 這個標籤
          設回去、不會送 switch-config，所以按下還原後畫面顯示舊角色、實際載入
          的仍是新角色。切換現在只留在「角色」分頁，那裡會標示哪一個使用中。 */}
      {/* 連線設定是整個抽屜裡唯一要按按鈕的地方，所以獨立成一塊、用邊框隔開，
          按鈕就在欄位旁邊。理由不是偏好：這兩個欄位每改一個字元就會重連一次
          （見 use-general-settings 的說明），必須等使用者打完才送。 */}
      <Stack
        gap={2}
        pt={3}
        borderTopWidth="1px"
        borderColor="whiteAlpha.200"
      >
        <Text fontSize="sm" color="whiteAlpha.800" fontWeight="semibold">
          {t("settings.general.connectionSection")}
        </Text>
        <InputField
          label={t("settings.general.wsUrl")}
          value={connection.wsUrl}
          onChange={(value) => setConnectionField("wsUrl", value)}
          placeholder={t("settings.general.wsUrlPlaceholder")}
        />
        <InputField
          label={t("settings.general.baseUrl")}
          value={connection.baseUrl}
          onChange={(value) => setConnectionField("baseUrl", value)}
          placeholder={t("settings.general.baseUrlPlaceholder")}
          help={t("settings.general.connectionHelp")}
        />
        <TabActions
          dirty={connectionDirty}
          applyLabel={t("settings.general.connect")}
          onApply={applyConnection}
          onRevert={revertConnection}
        />
      </Stack>

      <InputField
        label={t("settings.general.imageCompressionQuality")}
        value={qualityText}
        onChange={(value) => { setQualityText(value); qualitySaver.change(value); }}
        onBlur={qualitySaver.flush}
        help={t("settings.general.imageCompressionQualityHelp")}
      />
      <SaveStatus state={qualitySaver.state} />

      <InputField
        label={t("settings.general.imageMaxWidth")}
        value={widthText}
        onChange={(value) => { setWidthText(value); widthSaver.change(value); }}
        onBlur={widthSaver.flush}
        help={t("settings.general.imageMaxWidthHelp")}
      />
      <SaveStatus state={widthSaver.state} />



      {/* 「關於你」：每一項都改了就存，見 you.tsx 檔頭。 */}
      <You active />

      {/* 工具開關、背景工作、背景上傳：改了就存；寫進 conf.yaml 的要重新載入才生效，由抽屜頂端的提示處理。 */}
      <Stack gap={2} pt={3} borderTopWidth="1px" borderColor="whiteAlpha.200">
        <SwitchField
          label={t("settings.general.enableMcpp")}
          checked={mcpEnabled}
          onChange={(checked) => { setMcpEnabled(checked); mcpSaver.change(checked); }}
          disabled={mcpLoading || mcpSaver.state.phase === 'saving'}
        />
        <SaveStatus state={mcpSaver.state} />
        <Text fontSize="xs" color="whiteAlpha.600">
          {t("settings.general.enableMcppHelp")}
        </Text>
        {mcpLoadError && (
          <Text fontSize="xs" color="red.300">{mcpLoadError}</Text>
        )}

        {engine && !engine.available && (
          <Text fontSize="xs" color="orange.300">{engine.reason}</Text>
        )}
        {engine && everyDrafts && (
          <Stack gap={1} pl={2}>
            <Text fontSize="xs" color="whiteAlpha.600">
              {t("settings.general.engineEveryHelp")}
            </Text>
            {(["emotion_every", "memory_every", "self_memory_every", "goal_every", "reflection_every"] as EngineEvery[]).map((key) => (
              <NumberField
                key={key}
                label={t(`settings.general.engine_${key}`)}
                value={everyDrafts[key]}
                min={0}
                max={99}
                step={1}
                onChange={(value) => changeEvery(key, value)}
                onBlur={everySaver.flush}
              />
            ))}
            <Text fontSize="xs" color="whiteAlpha.600">
              {t("settings.general.engineShownHelp")}
            </Text>
            {(["goals_shown", "thoughts_shown"] as EngineEvery[]).map((key) => (
              <NumberField
                key={key}
                label={t(`settings.general.engine_${key}`)}
                value={everyDrafts[key]}
                min={0}
                max={99}
                step={1}
                onChange={(value) => changeEvery(key, value)}
                onBlur={everySaver.flush}
              />
            ))}
            <SaveStatus state={everySaver.state} />
            {backgroundDraft && (
              <Stack gap={1}>
                <Text fontSize="xs" color="whiteAlpha.600">
                  {t("settings.general.engineBackgroundHelp")}
                </Text>
                <InputField
                  label={t("settings.general.engineBackgroundUrl")}
                  value={backgroundDraft.url}
                  onChange={(value) => changeBackground('url', value)}
                  onBlur={backgroundSaver.flush}
                  placeholder="http://127.0.0.1:1235/v1"
                />
                <InputField
                  label={t("settings.general.engineBackgroundModel")}
                  value={backgroundDraft.model}
                  onChange={(value) => changeBackground('model', value)}
                  onBlur={backgroundSaver.flush}
                  placeholder="qwen/qwen3.5-9b"
                />
                <SaveStatus state={backgroundSaver.state} />
              </Stack>
            )}
          </Stack>
        )}
        {engineError && (
          <Text fontSize="xs" color="red.300">{engineError}</Text>
        )}

        <Field
          label={t("settings.general.bgUploadLabel")}
          help={t("settings.general.bgUploadHelp")}
        >
          <HStack>
            <input
              ref={bgFileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/gif"
              style={{ display: "none" }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
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
              {t("settings.general.bgUpload")}
            </Button>
          </HStack>
          {bgUploadError && (
            <Text fontSize="xs" color="red.300">{bgUploadError}</Text>
          )}
        </Field>
      </Stack>
    </Stack>
  );
}

export default General;
