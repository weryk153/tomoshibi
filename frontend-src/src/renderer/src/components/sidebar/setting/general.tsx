/* eslint-disable import/no-extraneous-dependencies */
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
import { SelectField, SwitchField, InputField, SliderField, TabActions } from "./common";
import { Button } from "@/components/ui/tw/primitives";
import { Field } from '@/components/ui/tw/primitives';
import { toaster } from "@/components/ui/tw/toaster";
import { fetchUseMcpp, setUseMcpp } from "@/api/agent-config.ts";
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

  // MCP 開關（工具／網路搜尋）：直接讀寫 conf.yaml，跟這個分頁其餘欄位的
  // 草稿制的 TabActions 套用／還原跟這個完全是兩回事——conf.yaml 只在後端啟動時
  // 讀取一次（見 api/agent-config.ts 檔頭），所以這裡切換就立刻送出，不受
  // 下面的套用／還原影響，也不能被它們還原掉。
  const [mcpEnabled, setMcpEnabled] = useState(false);
  const [mcpLoading, setMcpLoading] = useState(true);
  const [mcpSaving, setMcpSaving] = useState(false);
  const [mcpError, setMcpError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchUseMcpp(baseUrl);
      if (cancelled) return;
      setMcpLoading(false);
      if (result.ok) {
        setMcpEnabled(result.data);
      } else {
        setMcpError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  const handleMcpToggle = useCallback(async (checked: boolean) => {
    const previous = mcpEnabled;
    setMcpEnabled(checked);
    setMcpSaving(true);
    setMcpError(null);
    const result = await setUseMcpp(baseUrl, checked);
    setMcpSaving(false);
    if (result.ok) {
      setMcpEnabled(result.data.use_mcpp);
      toaster.create({
        title: t("settings.general.mcppSaved"),
        type: "success",
        duration: 3000,
      });
    } else {
      // 失敗就退回原值，不留一個「畫面上開著、conf.yaml 其實沒存到」的假象。
      setMcpEnabled(previous);
      setMcpError(result.error);
    }
  }, [baseUrl, mcpEnabled, t]);

  // 背景圖片上傳：POST /api/background 把檔案寫進磁碟，同樣是立刻生效、
  // 不可還原，不受下面的套用／還原影響。
  const [bgUploading, setBgUploading] = useState(false);
  const [bgUploadError, setBgUploadError] = useState<string | null>(null);
  const bgFileInputRef = useRef<HTMLInputElement | null>(null);

  // 世代計數器：跟 characters.tsx 的 formSessionRef 同一種手法（見該檔案檔頭
  // 說明），防的是同一種事故——上傳這段 await 期間使用者可能已經手動改選了
  // 別的背景（下拉選單／自訂 URL／切去攝像頭背景），上傳完成時不能無條件把
  // 新檔案蓋回目前選取。這裡只有一個「目前選取」而不是多個表單，用遞增計數
  // 比對「上傳開始時」跟「上傳完成時」是否還是同一次選取意圖；不一致就只更新
  // 背景清單，不動使用者已經換過的選取。
  const bgSelectionSessionRef = useRef(0);

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

          <Stack gap={2}>
            <InputField
              label={t("settings.general.customBgUrl")}
              value={customBgDraft}
              onChange={setCustomBgDraft}
              placeholder={t("settings.general.customBgUrlPlaceholder")}
            />
            <Button
              size="xs"
              tone="blue"
              className="self-start"
              disabled={
                !customBgDraft.trim()
                || customBgDraft.trim() === settings.customBgUrl
              }
              onClick={() => {
                bgSelectionSessionRef.current += 1;
                handleSettingChange("selectedBgUrl", []);
                handleSettingChange("customBgUrl", customBgDraft.trim());
              }}
            >
              {t("common.apply")}
            </Button>
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
        value={settings.imageCompressionQuality.toString()}
        onChange={(value) => {
          const quality = parseFloat(value as string);
          if (!Number.isNaN(quality) && quality >= 0.1 && quality <= 1.0) {
            handleSettingChange("imageCompressionQuality", quality);
          } else if (value === "") {
            handleSettingChange("imageCompressionQuality", settings.imageCompressionQuality);
          }
        }}
        help={t("settings.general.imageCompressionQualityHelp")}
      />

      <InputField
        label={t("settings.general.imageMaxWidth")}
        value={settings.imageMaxWidth.toString()}
        onChange={(value) => {
          const maxWidth = parseInt(value as string, 10);
          if (!Number.isNaN(maxWidth) && maxWidth >= 0) {
            handleSettingChange("imageMaxWidth", maxWidth);
          } else if (value === "") {
            handleSettingChange("imageMaxWidth", settings.imageMaxWidth);
          }
        }}
        help={t("settings.general.imageMaxWidthHelp")}
      />



      {/* Task 4「關於你」：暱稱／頭像／玩家語言／全域指示／角色發聲語言，一律
          即時存檔或寫 localStorage，不受上面的 TabActions 管——理由跟緊接在後
          的 MCP／背景上傳區塊一樣，詳見 you.tsx 檔頭註解。刻意排在 TabActions
          之後、緊鄰 MCP 區塊，讓「套用／還原管到這裡為止，下面都即時生效」
          從畫面順序上就讀得出來，不是只能靠說明文字。General 本身沒有從
          setting-ui.tsx 拿到 activeTab 訊號（不像 asr.tsx／memory.tsx 那樣接了
          active prop），這裡固定傳 true，效果等同 You 自己的預設值，只是寫明
          而非留給隱式預設生效。 */}
      <You active />

      {/* 立即生效區塊：MCP 開關寫 conf.yaml、背景上傳寫磁碟，兩者都不可還原，
          跟上面的草稿制套用／還原是兩種不同的存檔機制，故意用邊框跟上面
          隔開，不接進上面的 TabActions。 */}
      <Stack gap={2} pt={3} borderTopWidth="1px" borderColor="whiteAlpha.200">
        <SwitchField
          label={t("settings.general.enableMcpp")}
          checked={mcpEnabled}
          onChange={handleMcpToggle}
          disabled={mcpLoading || mcpSaving}
        />
        <Text fontSize="xs" color="whiteAlpha.600">
          {t("settings.general.enableMcppHelp")}
        </Text>
        {mcpError && (
          <Text fontSize="xs" color="red.300">{mcpError}</Text>
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
