import { ChangeEvent, KeyboardEvent } from 'react';
import { useVAD } from '@/context/vad-context';
import { useTextInput } from '@/hooks/footer/use-text-input';
import { useInterrupt } from '@/hooks/utils/use-interrupt';
import { useMicToggle } from '@/hooks/utils/use-mic-toggle';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';
import { useTriggerSpeak } from '@/hooks/utils/use-trigger-speak';
import { useProactiveSpeak } from '@/context/proactive-speak-context';

export const useFooter = () => {
  const {
    inputText: inputValue,
    setInputText: handleChange,
    handleKeyPress: handleKey,
    handleCompositionStart,
    handleCompositionEnd,
    handleSend,
  } = useTextInput();

  const { interrupt } = useInterrupt();
  const { startMic, autoStartMicOn } = useVAD();
  const { handleMicToggle, micOn } = useMicToggle();
  const { setAiState, aiState } = useAiState();
  const { sendTriggerSignal } = useTriggerSpeak();
  const { settings } = useProactiveSpeak();

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    handleChange({ target: { value: e.target.value } } as ChangeEvent<HTMLInputElement>);
    // WAITING's only effect is pausing the proactive-speak idle timer, which
    // only ever runs while aiState === IDLE (see proactive-speak-context.tsx).
    // So the per-keystroke call is only meaningful from idle; calling it
    // unconditionally used to also fire while she's speaking/listening/etc.,
    // which did nothing harmful today (the context already refuses to let
    // WAITING override THINKING_SPEAKING) but needlessly yanked the aiState
    // away from other states too. Scoping it to idle keeps the "don't
    // proactively speak while the user is mid-typing" behaviour and removes
    // every other no-op/unwanted transition.
    if (aiState === AiStateEnum.IDLE) {
      setAiState(AiStateEnum.WAITING);
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    handleKey(e as any);
  };

  const handleInterrupt = () => {
    if (aiState === AiStateEnum.THINKING_SPEAKING) {
      interrupt();
      if (autoStartMicOn) {
        startMic();
      }
    } else if (settings.allowButtonTrigger) {
      sendTriggerSignal(-1);
    }
  };

  return {
    inputValue,
    handleInputChange,
    handleKeyPress,
    handleCompositionStart,
    handleCompositionEnd,
    handleSend,
    handleInterrupt,
    handleMicToggle,
    micOn,
  };
};
