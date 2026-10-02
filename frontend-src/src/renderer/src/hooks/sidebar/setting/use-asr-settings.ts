import React, {
  useRef, useState, useEffect,
} from 'react';
import { useVAD, VADSettings } from '@/context/vad-context';

export const useASRSettings = () => {
  const {
    settings,
    updateSettings,
    autoStopMic,
    setAutoStopMic,
    autoStartMicOn,
    setAutoStartMicOn,
    autoStartMicOnConvEnd,
    setAutoStartMicOnConvEnd,
  } = useVAD();

  const localSettingsRef = useRef<VADSettings>(settings);
  const [localVoiceInterruption, setLocalVoiceInterruption] = useState(autoStopMic);
  const [localAutoStartMic, setLocalAutoStartMic] = useState(autoStartMicOn);
  const [localAutoStartMicOnConvEnd, setLocalAutoStartMicOnConvEnd] = useState(autoStartMicOnConvEnd);
  const [, forceUpdate] = React.useReducer((x) => x + 1, 0);

  useEffect(() => {
    setLocalVoiceInterruption(autoStopMic);
    setLocalAutoStartMic(autoStartMicOn);
    setLocalAutoStartMicOnConvEnd(autoStartMicOnConvEnd);
  }, [autoStopMic, autoStartMicOn, autoStartMicOnConvEnd]);

  // 欄位（DraftNumberField）停手才交出合法的值：套用會重開麥克風，不能每打一個字
  // 就重開，也不能存進空字串。
  const handleInputChange = (key: keyof VADSettings, value: number | string): void => {
    const parsed = Number(value);
    if (value === '' || !Number.isFinite(parsed)) return;
    localSettingsRef.current = { ...localSettingsRef.current, [key]: parsed };
    updateSettings(localSettingsRef.current);
    forceUpdate();
  };

  // 改了就生效，跟這個分頁下半部的辨識引擎區塊、以及抽屜裡其他區塊一致。
  const handleVoiceInterruptionChange = (value: boolean) => {
    setLocalVoiceInterruption(value);
    setAutoStopMic(value);
  };

  const handleAutoStartMicChange = (value: boolean) => {
    setLocalAutoStartMic(value);
    setAutoStartMicOn(value);
  };

  const handleAutoStartMicOnConvEndChange = (value: boolean) => {
    setLocalAutoStartMicOnConvEnd(value);
    setAutoStartMicOnConvEnd(value);
  };

  return {
    localSettings: localSettingsRef.current,
    autoStopMic: localVoiceInterruption,
    autoStartMicOn: localAutoStartMic,
    autoStartMicOnConvEnd: localAutoStartMicOnConvEnd,
    setAutoStopMic: handleVoiceInterruptionChange,
    setAutoStartMicOn: handleAutoStartMicChange,
    setAutoStartMicOnConvEnd: handleAutoStartMicOnConvEndChange,
    handleInputChange,
  };
};
