// 首次啟動精靈的第二步：挑 2D 還是 3D。
//
// 兩種模型都隨附了（live2d-models/ 三個、vrm-models/Sendagaya_Shino），但預設
// 角色寫死指向 mao_pro，所以不主動去角色設定翻的人根本不知道有 3D 可以用。
// 這一步只是把「已經在硬碟上的東西」擺到看得見的地方。
//
// 選項不寫死模型名稱：掃 /api/live2d-skins 的結果按 type 分組，各取第一個。
// 使用者刪掉隨附模型、或自己放了別的，這一步照樣正確——寫死的話會指向不存在
// 的模型，存下去就是一個壞掉的角色。
//
// 只有一種類型時整步跳過：沒得選就不要多問一次。

import { useEffect, useState } from 'react';
import { Stack, Text, HStack } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import {
  buildCharacterUpdate,
  fetchCharacters,
  fetchLive2dSkins,
  updateCharacter,
  type CharacterRecord,
} from '@/api/characters.ts';

interface Skin {
  name: string
  type?: string
}

interface Props {
  baseUrl: string
  /** 選完（或跳過、或沒得選）之後往下走。 */
  onDone: () => void
}

type Kind = 'live2d' | 'vrm';

function AvatarKindStep({ baseUrl, onDone }: Props): JSX.Element | null {
  const { t } = useTranslation();
  const [choices, setChoices] = useState<Record<Kind, string> | null>(null);
  const [base, setBase] = useState<CharacterRecord | null>(null);
  const [saving, setSaving] = useState<Kind | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [skinsResult, charsResult] = await Promise.all([
        fetchLive2dSkins(baseUrl),
        fetchCharacters(baseUrl),
      ]);
      if (cancelled) return;

      // 任何一邊失敗就整步跳過。這一步是錦上添花，不該擋住首次啟動——
      // 使用者之後在角色設定一樣換得了模型。
      if (!skinsResult.ok || !charsResult.ok) {
        onDone();
        return;
      }
      const skins = ((skinsResult.data as { skins?: Skin[] })?.skins ?? []);
      const first = (kind: Kind): string | undefined =>
        skins.find((s) => (s.type ?? 'live2d') === kind)?.name;
      const live2d = first('live2d');
      const vrm = first('vrm');
      if (!live2d || !vrm) {
        onDone();
        return;
      }
      const records = (charsResult.data as { characters?: CharacterRecord[] })
        .characters ?? [];
      const baseRecord = records.find((r) => r.is_base);
      if (!baseRecord) {
        onDone();
        return;
      }
      setChoices({ live2d, vrm });
      setBase(baseRecord);
    })();
    return () => {
      cancelled = true;
    };
  }, [baseUrl, onDone]);

  if (!choices || !base) return null;

  const pick = async (kind: Kind): Promise<void> => {
    setSaving(kind);
    setFailed(false);
    // 只改外觀，其餘欄位由 buildCharacterUpdate 從現值帶回去——底稿是整份
    // 重寫的，漏帶就等於把人設之類的清掉。
    const body = buildCharacterUpdate(base, { live2d_model_name: choices[kind] });
    const result = await updateCharacter(baseUrl, base.filename, body);
    setSaving(null);
    if (result.ok) onDone();
    else setFailed(true);
  };

  return (
    <Stack gap={4}>
      <Stack gap={1}>
        <Text fontWeight="bold">{t('setup.avatarKindTitle')}</Text>
        <Text fontSize="sm" color="whiteAlpha.700">
          {t('setup.avatarKindIntro')}
        </Text>
      </Stack>

      <HStack gap={3} flexWrap="wrap">
        <Button
          tone="blue"
          disabled={saving !== null}
          onClick={() => pick('live2d')}
        >
          {saving === 'live2d' ? t('setup.avatarKindApplying') : t('setup.avatarKind2d')}
        </Button>
        <Button
          tone="blue"
          disabled={saving !== null}
          onClick={() => pick('vrm')}
        >
          {saving === 'vrm' ? t('setup.avatarKindApplying') : t('setup.avatarKind3d')}
        </Button>
      </HStack>

      <Text fontSize="xs" color="whiteAlpha.600">
        {t('setup.avatarKindHelp')}
      </Text>

      {failed && (
        <Text fontSize="sm" color="red.300">
          {t('setup.avatarKindFailed')}
        </Text>
      )}
    </Stack>
  );
}

export default AvatarKindStep;
