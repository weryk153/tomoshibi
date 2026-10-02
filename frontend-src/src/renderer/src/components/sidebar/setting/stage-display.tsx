// 舞台頁的字幕與音量。背景在下面的「場景」：只有那裡決定背景。
//
// 每一項直接呼叫自己的 context／localStorage，不經過一份共用的快照（以前的
// useGeneralSettings 會把別頁剛改的值蓋回去）。
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Stack } from '@chakra-ui/react';
import { useSubtitle } from '@/context/subtitle-context';
import { loadVoiceVolume, saveVoiceVolume } from '@/utils/voice-volume';
import { SwitchField, SliderField } from './common';

function StageDisplay(): JSX.Element {
  const { t } = useTranslation();
  const { showSubtitle, setShowSubtitle } = useSubtitle();
  const [voiceVolume, setVoiceVolume] = useState(loadVoiceVolume);

  return (
    <Stack gap={4}>
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
    </Stack>
  );
}

export default StageDisplay;
