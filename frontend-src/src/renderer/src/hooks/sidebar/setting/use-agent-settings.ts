import { useCallback, useEffect, useState, useRef } from 'react';
import { useProactiveSpeak } from '@/context/proactive-speak-context';

// onCancel 曾經用來在抽屜關閉時還原草稿。改成即時生效之後沒有草稿可還原，
// 參數整個移除——留著一個沒人用的參數只會讓下一個人以為這裡還有還原機制。
export function useAgentSettings() {
  const { settings: persistedSettings, updateSettings } = useProactiveSpeak();

  const [tempSettings, setTempSettings] = useState({
    allowProactiveSpeak: persistedSettings.allowProactiveSpeak,
    idleSecondsToSpeak: persistedSettings.idleSecondsToSpeak,
    allowButtonTrigger: persistedSettings.allowButtonTrigger,
  });

  useEffect(() => {
    if (persistedSettings) {
      setTempSettings(persistedSettings);
    }
  }, [persistedSettings]);

  const handleAllowProactiveSpeakChange = useCallback((checked: boolean) => {
    setTempSettings((prev) => ({
      ...prev,
      allowProactiveSpeak: checked,
    }));
  }, []);

  const handleIdleSecondsChange = useCallback((value: number) => {
    setTempSettings((prev) => ({
      ...prev,
      idleSecondsToSpeak: Math.max(30, Number(value) || 30),
    }));
  }, []);

  const handleAllowButtonTriggerChange = useCallback((checked: boolean) => {
    setTempSettings((prev) => ({
      ...prev,
      allowButtonTrigger: checked,
    }));
  }, []);

  // 改了就生效，跟這個分頁下半部的主動話題區塊一致。
  const mounted = useRef(false);
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    updateSettings(tempSettings);
  }, [tempSettings, updateSettings]);

  return {
    settings: tempSettings,
    handleAllowProactiveSpeakChange,
    handleIdleSecondsChange,
    handleAllowButtonTriggerChange,
  };
}
