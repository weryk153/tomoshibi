import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import { useInterrupt } from '@/hooks/utils/use-interrupt';
import { useVAD } from '@/context/vad-context';
import { useSubtitle } from '@/context/subtitle-context';
import { useAiState } from '@/context/ai-state-context';
import { useLive2DConfig } from '@/context/live2d-config-context';

export function useSwitchCharacter() {
  const { t } = useTranslation();
  const { sendMessage } = useWebSocket();
  const { confName, getFilenameByName } = useConfig();
  const { interrupt } = useInterrupt();
  const { stopMic } = useVAD();
  const { setSubtitleText } = useSubtitle();
  const { setAiState } = useAiState();
  const { setModelInfo } = useLive2DConfig();
  const switchCharacter = useCallback((fileName: string, force = false) => {
    const currentFilename = getFilenameByName(confName);

    if (currentFilename === fileName && !force) {
      console.log('Skipping character switch - same configuration file');
      return;
    }

    setSubtitleText(t('subtitle.characterLoading'));
    interrupt();
    stopMic();
    setAiState('loading');
    setModelInfo(undefined);
    sendMessage({
      type: 'switch-config',
      file: fileName,
    });
    console.log('Switch Character fileName: ', fileName);
  }, [confName, getFilenameByName, sendMessage, interrupt, stopMic, setSubtitleText, setAiState, t]);

  // 不換角色，只讓後端重讀一次 conf.yaml 與目前的角色檔——存好 LLM 或外觀之後
  // 用這個讓設定立刻生效，不必重啟。後端回的是 config-reloaded，不會像
  // config-switched 那樣跳「角色已切換」或開新對話。
  const reloadCharacter = useCallback(() => {
    interrupt();
    stopMic();
    setAiState('loading');
    sendMessage({ type: 'reload-config' });
  }, [sendMessage, interrupt, stopMic, setAiState]);

  return { switchCharacter, reloadCharacter };
}
