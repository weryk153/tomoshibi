// 翻譯審核建議：嵌在角色頁「語言」區，翻譯審核開著時才顯示。後端在背景審她每句
// 語音翻譯，累積成建議；這裡列出出現夠多次、角色設定裡還沒有的，按「加入」才寫進
// 角色檔（後端從不自動改）。正在用的角色要重新載入才生效，由抽屜頂端的提示處理。
import { useState, useEffect, useCallback } from 'react';
import { Stack, Text, HStack } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import {
  fetchTranslationAudit,
  acceptTranslationAuditSuggestion,
  type TranslationAudit,
  type SuggestionKind,
  type AuditSuggestion,
} from '@/api/translation-audit.ts';

const KINDS: { kind: SuggestionKind; labelKey: string }[] = [
  { kind: 'protected_names', labelKey: 'settings.characters.translationAuditNames' },
  { kind: 'catchphrases', labelKey: 'settings.characters.translationAuditCatchphrases' },
];

function TranslationAuditSuggestions({ filename }: { filename: string }): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const [audit, setAudit] = useState<TranslationAudit | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [adding, setAdding] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setAudit(null);
    setLoadError(null);
    (async () => {
      const result = await fetchTranslationAudit(baseUrl, filename);
      if (cancelled) return;
      if (result.ok) setAudit(result.data);
      else setLoadError(result.error || t('settings.characters.translationAuditLoadFailed'));
    })();
    return () => { cancelled = true; };
  }, [baseUrl, filename, t]);

  const handleAdd = useCallback(async (kind: SuggestionKind, row: AuditSuggestion) => {
    const key = `${kind}:${row.source}:${row.target}`;
    setAdding(key);
    const result = await acceptTranslationAuditSuggestion(baseUrl, filename, kind, row);
    setAdding(null);
    if (result.ok) {
      setAudit(result.data);
      toaster.create({ title: t('settings.characters.translationAuditAdded'), type: 'success', duration: 2500 });
    } else {
      toaster.create({ title: result.error, type: 'error', duration: 3000 });
    }
  }, [baseUrl, filename, t]);

  if (loadError) {
    return <Text fontSize="xs" color="red.300">{loadError}</Text>;
  }
  if (!audit) {
    return <Text fontSize="xs" color="whiteAlpha.600">{t('settings.characters.translationAuditLoading')}</Text>;
  }

  const empty = KINDS.every(({ kind }) => audit.suggestions[kind].length === 0);
  return (
    <Stack gap={2}>
      <Text fontSize="sm" fontWeight="semibold">{t('settings.characters.translationAuditSuggestions')}</Text>
      <Text fontSize="xs" color="whiteAlpha.600">
        {t('settings.characters.translationAuditSummary', { audited: audit.audited, flagged: audit.flagged })}
      </Text>
      {empty && (
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.characters.translationAuditNone')}</Text>
      )}
      {KINDS.map(({ kind, labelKey }) => audit.suggestions[kind].length > 0 && (
        <Stack key={kind} gap={1}>
          <Text fontSize="xs" color="whiteAlpha.700">{t(labelKey)}</Text>
          {audit.suggestions[kind].map((row) => {
            const key = `${kind}:${row.source}:${row.target}`;
            return (
              <HStack key={key} justify="space-between" gap={2}>
                <Text fontSize="sm" minW={0} wordBreak="break-all">
                  {row.source} → {row.target}
                  <Text as="span" fontSize="xs" color="whiteAlpha.600"> ×{row.count}</Text>
                </Text>
                <Button
                  size="xs"
                  variant="outline"
                  loading={adding === key}
                  disabled={adding !== null}
                  onClick={() => handleAdd(kind, row)}
                >
                  {t('settings.characters.translationAuditAdd')}
                </Button>
              </HStack>
            );
          })}
        </Stack>
      ))}
    </Stack>
  );
}

export default TranslationAuditSuggestions;
