import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { createListCollection } from '@ark-ui/react/collection';
import { SelectField } from './common';
import { useWebSocket } from '@/context/websocket-context';
import {
  REPLY_LENGTHS, fetchReplyLength, saveReplyLength, type ReplyLength,
} from '@/api/reply-length.ts';
import { toaster } from '@/components/ui/tw/toaster';

// 她每次回幾句（全部角色共用）。存了下一句就生效，不用重啟。
function ReplyLengthSetting(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const [length, setLength] = useState<ReplyLength | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReplyLength(baseUrl).then((result) => {
      if (!cancelled && result.ok) setLength(result.data);
    });
    return () => { cancelled = true; };
  }, [baseUrl]);

  const collection = useMemo(() => createListCollection({
    items: REPLY_LENGTHS.map((value): { value: string, label: string } => (
      { value, label: t(`settings.replyLength.${value}`) }
    )),
  }), [t]);

  const change = async (value: string[]) => {
    const next = value[0] as ReplyLength | undefined;
    if (!next || next === length) return;
    const before = length;
    setLength(next);
    const result = await saveReplyLength(baseUrl, next);
    if (!result.ok || !result.data.ok) {
      setLength(before);
      toaster.create({ title: t('settings.replyLength.saveFailed'), type: 'error' });
    }
  };

  return (
    <SelectField
      label={t('settings.replyLength.label')}
      value={length ? [length] : []}
      onChange={change}
      collection={collection}
      help={t('settings.replyLength.help')}
      disabled={length === null}
    />
  );
}

export default ReplyLengthSetting;
