/* eslint-disable react/require-default-props */
// remote-access：「這台伺服器現在能被哪些其他裝置連到」，以及「允許區網連線」
// 開關。開關寫 conf.yaml 的 system_config.host（POST /api/network/host），綁定位址
// 啟動時就決定了，要重啟後端才生效——抽屜頂端的提示會換成「重新啟動後端」。
// 下面列出的網址看的是這次啟動實際綁的位址（localhost_only），不是開關：重啟前
// 列出 LAN 網址會是「看起來能用、其實連不上」。
//
// 跟 asr.tsx／tts.tsx／memory.tsx 同一種 active-refetch 慣例：網路狀態在
// App 執行期間真的會變（換 Wi-Fi、開關 Tailscale），所以使用者切回這個分頁時
// 重新打一次 GET 是對的，不是多餘的动作。這裡沒有任何草稿或半編輯狀態要保護
// （整個分頁沒有輸入框），所以不需要 asr.tsx／memory.tsx 那種「分成兩個
// effect、第二個只挑幾個欄位刷新」的複雜度——一個 effect 依 active 決定要不要
// 打，active 從掛載時的預設 true 到之後任何一次 false→true 轉換都會重新抓。
import { useState, useEffect } from 'react';
import {
  Stack, Text, Heading, HStack, Box,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { QRCodeSVG } from 'qrcode.react';
import { settingStyles } from './setting-styles';
import { Clipboard as ArkClipboard } from '@ark-ui/react';
import { Button } from '@/components/ui/tw/primitives';
import { useWebSocket } from '@/context/websocket-context';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { SwitchField } from './common';
import {
  fetchNetworkInfo, pickPrimaryUrl, setAllowOtherDevices, shouldWarnMicNeedsHttps,
  type NetworkInfo, type NetworkUrl,
} from '@/api/network.ts';

interface RemoteAccessProps {
  // 這個分頁目前是不是使用者看得到的那個 tab（setting-ui.tsx 依 activeTab
  // 算出）。預設 true：萬一哪天有別的呼叫端沒傳這個 prop（目前只有
  // setting-ui.tsx 一處註冊），行為退回「一律當作可見」，不會因為漏傳就悄悄
  // 不刷新。
  active?: boolean
}

// urls 陣列裡只會出現 'lan'／'tailscale' 兩種 type（見 api/network.ts 的
// NetworkUrl），各自對應一個專屬的翻譯鍵；https_url 是獨立欄位，不在 urls
// 裡，它的標籤（labelHttps）在下面渲染那一列時直接引用，不經過這個函式。
function labelKeyForUrl(item: NetworkUrl): string {
  return item.type === 'lan'
    ? 'settings.remoteAccess.labelLan'
    : 'settings.remoteAccess.labelTailscale';
}

// ClipboardButton（components/ui/clipboard.tsx）的「Copy」／「Copied」文字是
// 寫死的英文，沒有走 i18n，這裡需要 settings.remoteAccess.copy／copied 這兩個
// 已經五語言翻好的鍵，所以不能直接用那個現成元件，改成直接組
// ChakraClipboard.Trigger + Indicator（跟 clipboard.tsx 內部組裝
// ClipboardButton 用的是同一組 Chakra 原生元件），只是把文字換成 t(...)。
// Ark 的 Clipboard——Chakra 的 ui/clipboard 包的就是它，換過來之後「已複製」的
// 狀態切換仍由同一顆狀態機處理（含自動切回原文字的計時）。
function CopyButton({ value }: { value: string }): JSX.Element {
  const { t } = useTranslation();
  return (
    <ArkClipboard.Root value={value}>
      <ArkClipboard.Trigger asChild>
        <Button size="xs" variant="solid">
          <ArkClipboard.Indicator copied={t('settings.remoteAccess.copied')}>
            {t('settings.remoteAccess.copy')}
          </ArkClipboard.Indicator>
        </Button>
      </ArkClipboard.Trigger>
    </ArkClipboard.Root>
  );
}

function RemoteAccess({ active = true }: RemoteAccessProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();

  const [info, setInfo] = useState<NetworkInfo | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  // 允許區網連線：切了就存；存失敗就退回原值。成功後重抓，下面的提示跟著變。
  const lanSaver = useAutosave(async (allow: boolean) => {
    const result = await setAllowOtherDevices(baseUrl, allow);
    if (!result.ok) {
      setInfo((current) => (current ? { ...current, allow_other_devices: !allow } : current));
      return { ok: false, error: result.error } as const;
    }
    setRefreshTick((n) => n + 1);
    return { ok: true } as const;
  }, { delayMs: 0 });

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    (async () => {
      const result = await fetchNetworkInfo(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setInfo(result.data);
        setLoadError(null);
      } else {
        setLoadError(result.error || t('settings.remoteAccess.error'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, baseUrl, refreshTick]);

  if (loadError) {
    return (
      <Stack {...settingStyles.common.container}>
        <Text fontSize="sm" color="red.300">{loadError}</Text>
      </Stack>
    );
  }

  if (!info) {
    return (
      <Stack {...settingStyles.common.container}>
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.remoteAccess.loading')}</Text>
      </Stack>
    );
  }

  const primaryUrl = pickPrimaryUrl(info);

  return (
    <Stack {...settingStyles.common.container} gap={4}>
      <Heading size="md" mb={1}>{t('settings.remoteAccess.tab')}</Heading>
      <Text fontSize="sm" color="whiteAlpha.800">{t('settings.remoteAccess.intro')}</Text>

      <Stack gap={1}>
        <SwitchField
          label={t('settings.remoteAccess.allowLan')}
          help={t('settings.remoteAccess.allowLanHelp')}
          checked={info.allow_other_devices}
          onChange={(checked) => {
            setInfo((current) => (current ? { ...current, allow_other_devices: checked } : current));
            lanSaver.change(checked);
          }}
          disabled={lanSaver.state.phase === 'saving'}
        />
        <SaveStatus state={lanSaver.state} />
        {info.allow_other_devices && info.localhost_only && (
          <Text fontSize="xs" color="orange.300">{t('settings.remoteAccess.allowLanPendingRestart')}</Text>
        )}
      </Stack>

      {/* 有 https_url 就代表 Tailscale Serve 已經把服務代理出去了，遠端存取其實
          是通的——這時再顯示橘色的「遠端存取目前關閉」會跟下面那句
          alreadyReachable 自相矛盾。所以這個提示只在「連 HTTPS 網址都沒有」時出現。 */}
      {info.localhost_only && !info.https_url && (
        <Box p={2} borderWidth="1px" borderColor="orange.700" borderRadius="sm">
          <Text fontWeight="bold" fontSize="sm" mb={1}>
            {t('settings.remoteAccess.offTitle')}
          </Text>
          <Text fontSize="xs" color="whiteAlpha.800" mb={2}>
            {t('settings.remoteAccess.recommendTailscale')}
          </Text>
          <Text fontSize="xs" color="whiteAlpha.700">
            {t('settings.remoteAccess.lanOptIn')}
          </Text>
        </Box>
      )}

      {/* alreadyReachable 的五語言文案講的是「上面那個 HTTPS 網址已經可以掃／
          用了」，所以條件要跟著 https_url 是否存在走，不能沿用
          !localhost_only && urls.length > 0——host: 0.0.0.0 卻沒設 Tailscale
          Serve 時，localhost_only 會是 false、urls 有 LAN 那筆，但根本沒有
          HTTPS 網址，舊條件會讓這段文案在畫面上撒謊。 */}
      {info.https_url && (
        <Text fontSize="sm" color="whiteAlpha.800">
          {t('settings.remoteAccess.alreadyReachable')}
        </Text>
      )}

      {!info.localhost_only && info.urls.length === 0 && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.remoteAccess.empty')}</Text>
      )}

      {/* LAN／Tailscale 這兩列只在 localhost_only 為 false 時渲染。
          localhost_only 為 true 時 urls 通常仍非空——作業系統找得到網卡、
          伺服器 socket 卻只收 loopback，這是使用者還沒動過設定時的正常狀態
          ——這時把這些網址印出來會是「看起來能用、其實連不上」的假象，跟上面
          橘色的 offTitle 提示自相矛盾。 */}
      {!info.localhost_only && info.urls.map((item) => (
        <HStack key={`${item.type}-${item.ip}`} justify="space-between" align="center">
          <Box>
            <Text fontSize="xs" color="whiteAlpha.600">{t(labelKeyForUrl(item))}</Text>
            <Text fontSize="sm" wordBreak="break-all">{item.url}</Text>
          </Box>
          <CopyButton value={item.url} />
        </HStack>
      ))}

      {info.https_url && (
        <Box>
          <HStack justify="space-between" align="center">
            <Box>
              <Text fontSize="xs" color="whiteAlpha.600">
                {t('settings.remoteAccess.labelHttps')}
              </Text>
              <Text fontSize="sm" wordBreak="break-all">{info.https_url}</Text>
            </Box>
            <CopyButton value={info.https_url} />
          </HStack>
          <Text fontSize="xs" color="whiteAlpha.600" mt={1}>
            {t('settings.remoteAccess.httpsNote')}
          </Text>
        </Box>
      )}

      {/* QR 只在 pickPrimaryUrl 回傳非 null 時渲染——它已經把「https_url
          優先、否則退回 localhost_only===false 時的 urls[0]、否則 null」這套
          邏輯收在 api/network.ts 裡（network.test.ts 有測），這裡不重複判斷
          條件，只問「有沒有網址可秀」。QR 本身固定白底黑碼（不用 whiteAlpha
          之類的主題色），因為這個抽屜是暗色主題，QR 掃描器需要模組跟底色對比
          夠高，暗色背景配暗色模組會直接掃不出來。 */}
      {primaryUrl && (
        <Stack align="center" gap={2}>
          <Box bg="white" p={3} borderRadius="sm">
            <QRCodeSVG value={primaryUrl} size={180} bgColor="#FFFFFF" fgColor="#000000" />
          </Box>
          <Text fontSize="xs" color="whiteAlpha.700">{t('settings.remoteAccess.qrCaption')}</Text>
        </Stack>
      )}

      {shouldWarnMicNeedsHttps(info) && (
        <Text fontSize="xs" color="orange.300">{t('settings.remoteAccess.micHttpsNote')}</Text>
      )}
    </Stack>
  );
}

export default RemoteAccess;
