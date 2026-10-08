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
    flushPending,
    queued,
    removeQueued,
  } = useTextInput();

  const { interrupt } = useInterrupt();
  const { startMic, autoStartMicOn } = useVAD();
  const { handleMicToggle, micOn } = useMicToggle();
  const { setAiState, aiState } = useAiState();
  const { sendTriggerSignal } = useTriggerSpeak();
  const { settings } = useProactiveSpeak();

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    handleChange({ target: { value: e.target.value } } as ChangeEvent<HTMLInputElement>);
    // Unconditional on purpose (reverted from a tighter idle-only guard):
    // the ai-state-context reducer already refuses to let WAITING override
    // THINKING_SPEAKING, so this never touches a speaking state. But it also
    // doubles as the recovery path out of 'interrupted' — after the
    // interrupt button, typing here moves interrupted -> waiting -> (2s
    // later, idle), which is what lets a queued pending-input message
    // (pending-input.ts) flush automatically if the user doesn't explicitly
    // trigger it. Gating this to idle-only broke that recovery.
    setAiState(AiStateEnum.WAITING);
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    handleKey(e as any);
  };

  const handleInterrupt = () => {
    if (aiState === AiStateEnum.THINKING_SPEAKING) {
      interrupt();
      // The user explicitly cut her off — send anything queued from while
      // she was talking right away, rather than waiting on the idle-only
      // auto-flush (which 'interrupted' deliberately doesn't trigger; see
      // shouldFlushOnStateChange's doc comment) or on the typing-driven
      // interrupted -> waiting -> idle recovery above.
      flushPending();
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
    queued,
    removeQueued,
  };
};
