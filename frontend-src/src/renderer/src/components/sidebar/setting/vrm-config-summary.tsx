// VRM 模型的動作／表情摘要。v1 唯讀：motion-config.tsx 整頁建立在 Live2D 的
// (group, index) 與表情索引上，VRM 的編輯器另做。要改對應：換關鍵字改
// motions/ 裡的檔名，加 label 或改表情對應編輯 model_dict.json。
import { useEffect, useState } from 'react';
import { Box, Heading, Stack, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useWebSocket } from '@/context/websocket-context';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { fetchVrmModelConfig, type VrmModelConfig } from '@/api/vrm-config';

export default function VrmConfigSummary(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { modelInfo } = useLive2DConfig();
  const [config, setConfig] = useState<VrmModelConfig | null>(null);
  // 沒有這個狀態的話，抓失敗會讓畫面永遠停在「…」，看起來像還在載入。
  const [error, setError] = useState(false);
  const name = modelInfo?.name;

  useEffect(() => {
    if (!name) return;
    let cancelled = false;
    setError(false);
    fetchVrmModelConfig(baseUrl, name).then((r) => {
      if (cancelled) return;
      if (r.ok) setConfig(r.data);
      else setError(true);
    });
    return () => { cancelled = true; };
  }, [baseUrl, name]);

  if (error) {
    return <Text fontSize="sm" color="orange.300">{t('settings.live2d.motionConfigLoadError')}</Text>;
  }
  if (!config) return <Text fontSize="sm">…</Text>;

  return (
    <Stack gap={3}>
      <Text fontSize="xs" color="blue.300">{t('settings.live2d.vrmReadOnlyNote')}</Text>
      <Box>
        <Heading size="sm">{t('settings.live2d.vrmClips')}</Heading>
        {!config.has_idle && <Text fontSize="sm" color="orange.300">{t('settings.live2d.vrmNoIdle')}</Text>}
        {config.clips.length === 0 && <Text fontSize="sm">—</Text>}
        {config.clips.map((c) => (
          <Text key={c.clip} fontSize="sm">
            {c.file} → {c.mappings.map((m) => `[${m.keyword}]${m.label ? `（${m.label}）` : ''}`).join(' ') || '—'}
          </Text>
        ))}
      </Box>
      <Box>
        <Heading size="sm">{t('settings.live2d.vrmExpressions')}</Heading>
        {config.expressions.map((e) => (
          <Text key={e.name} fontSize="sm">
            {e.name} → {e.keywords.map((k) => `[${k}]`).join(' ') || '—'}
          </Text>
        ))}
      </Box>
      {config.orphan_keywords.length > 0 && (
        <Text fontSize="sm" color="orange.300">
          {t('settings.live2d.vrmOrphans')}: {config.orphan_keywords.map((o) => `[${o.keyword}]`).join(' ')}
        </Text>
      )}
    </Stack>
  );
}
