import { useCallback, useEffect, useRef, useState } from 'react';
import { useWebSocket } from '@/context/websocket-context';
import { useAiState } from '@/context/ai-state-context';
import { useChatHistory } from '@/context/chat-history-context';
import { useVAD } from '@/context/vad-context';
import { useMediaCapture } from '@/hooks/utils/use-media-capture';
import {
  EMPTY_PENDING_INPUT,
  PendingInputState,
  enqueuePendingInput,
  hasPendingInput,
  joinPendingInput,
  clearPendingInput,
  shouldQueueInsteadOfSending,
  shouldFlushOnStateChange,
} from '@/hooks/footer/pending-input';

export function useTextInput() {
  const [inputText, setInputText] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const wsContext = useWebSocket();
  const { aiState } = useAiState();
  const { appendHumanMessage } = useChatHistory();
  const { stopMic, autoStopMic } = useVAD();
  const { captureAllMedia } = useMediaCapture();

  // Messages typed/sent while she's speaking. A ref, not state: it's only
  // ever read inside callbacks/effects, and putting it in state would cause
  // an extra render per queued message for no one to see.
  const pendingRef = useRef<PendingInputState>(EMPTY_PENDING_INPUT);
  const prevAiStateRef = useRef(aiState);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputText(e.target.value);
  };

  // Images are captured at the moment of actually sending (not when the
  // user pressed send) so a queued message reflects the screen/camera when
  // it finally goes out, same as it always has for an immediate send.
  const sendTextInput = useCallback(async (text: string) => {
    if (!wsContext) return;
    const images = await captureAllMedia();
    wsContext.sendMessage({
      type: 'text-input',
      text,
      images,
    });
  }, [wsContext, captureAllMedia]);

  // Flush the queue once she genuinely settles back to idle. If the socket
  // happens to be down at that moment, wsService.sendMessage already warns
  // to the console (and toasts) on its own — the message stays visible in
  // chat history regardless (it was appended when the user sent it), so
  // nothing is dropped silently and we don't need a retry loop here.
  useEffect(() => {
    const prevAiState = prevAiStateRef.current;
    prevAiStateRef.current = aiState;
    if (prevAiState === aiState) return;
    if (!shouldFlushOnStateChange(aiState)) return;
    if (!hasPendingInput(pendingRef.current)) return;

    const text = joinPendingInput(pendingRef.current);
    pendingRef.current = clearPendingInput();
    sendTextInput(text).catch((error) => {
      console.warn('Failed to send queued text-input:', error);
    });
  }, [aiState, sendTextInput]);

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || !wsContext) return;

    // Shown immediately either way — queueing only delays the backend turn,
    // not her seeing it echoed in the transcript.
    appendHumanMessage(text);
    setInputText('');
    if (autoStopMic) stopMic();

    if (shouldQueueInsteadOfSending(aiState)) {
      // Do NOT interrupt her. Hold the message; the effect above sends it
      // (joined with anything else queued meanwhile) once she's done.
      pendingRef.current = enqueuePendingInput(pendingRef.current, text);
      return;
    }

    await sendTextInput(text);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (isComposing) return;

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCompositionStart = () => setIsComposing(true);
  const handleCompositionEnd = () => setIsComposing(false);

  return {
    inputText,
    setInputText: handleInputChange,
    handleSend,
    handleKeyPress,
    handleCompositionStart,
    handleCompositionEnd,
  };
}
