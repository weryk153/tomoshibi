import { useCallback, useEffect, useRef, useState } from 'react';
import { useWebSocket } from '@/context/websocket-context';
import { useAiState } from '@/context/ai-state-context';
import { useChatHistory } from '@/context/chat-history-context';
import { useVAD } from '@/context/vad-context';
import { useConfig } from '@/context/character-config-context';
import { useGroup } from '@/context/group-context';
import { useInterrupt } from '@/hooks/utils/use-interrupt';
import { useMediaCapture } from '@/hooks/utils/use-media-capture';
import {
  EMPTY_PENDING_INPUT,
  PendingInputState,
  enqueuePendingInput,
  removePendingInput,
  hasPendingInput,
  joinPendingInput,
  clearPendingInput,
  mergeQueuedWithImmediate,
  decideSend,
  shouldFlushOnStateChange,
} from '@/hooks/footer/pending-input';

export function useTextInput() {
  const [inputText, setInputText] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const wsContext = useWebSocket();
  const { aiState } = useAiState();
  const { appendHumanMessage } = useChatHistory();
  const { stopMic, autoStopMic } = useVAD();
  const { confUid } = useConfig();
  const { captureAllMedia } = useMediaCapture();
  const { groupMembers } = useGroup();
  const { interrupt } = useInterrupt();

  // Messages typed/sent while she's speaking. A ref, not state: it's only
  // ever read inside callbacks/effects, and putting it in state would cause
  // an extra render per queued message for no one to see.
  const pendingRef = useRef<PendingInputState>(EMPTY_PENDING_INPUT);
  // 畫面上「排隊中」那一區要看的；跟 pendingRef 一起改（setPending）。
  const [queued, setQueued] = useState<readonly string[]>([]);
  const setPending = useCallback((next: PendingInputState) => {
    pendingRef.current = next;
    setQueued(next.queue);
  }, []);
  const prevAiStateRef = useRef(aiState);
  const prevConfUidRef = useRef(confUid);

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

  // If the socket happens to be down when this fires, wsService.sendMessage
  // already warns to the console (and toasts) on its own — the message
  // stays visible in chat history regardless (it was appended when the user
  // sent it), so nothing is dropped silently and we don't need a retry loop
  // here. Exposed as `flushPending` so an explicit interrupt-button press
  // can trigger it directly (see shouldFlushOnStateChange's doc comment for
  // why that's not inferred from the aiState transition alone).
  const flushPendingInput = useCallback(() => {
    if (!hasPendingInput(pendingRef.current)) return;
    const waiting = pendingRef.current.queue;
    const text = joinPendingInput(pendingRef.current);
    setPending(clearPendingInput());
    // 真的送出這一刻才進對話（排隊時只在輸入框上方的「排隊中」）。
    waiting.forEach((line) => appendHumanMessage(line));
    sendTextInput(text).catch((error) => {
      console.warn('Failed to send queued text-input:', error);
    });
  }, [sendTextInput, setPending, appendHumanMessage]);

  const removeQueued = useCallback((index: number) => {
    setPending(removePendingInput(pendingRef.current, index));
  }, [setPending]);

  // A character switch starts a new history for a different character —
  // text queued while talking to whoever she was before must not be
  // silently delivered to the next one. Declared *before* the idle-flush
  // effect below: set-model-and-conf changes confUid and sets aiState to
  // 'idle' together, so when both land in the same commit this one clears
  // the queue first and the flush effect then finds nothing left to send.
  useEffect(() => {
    const prevConfUid = prevConfUidRef.current;
    prevConfUidRef.current = confUid;
    if (prevConfUid === confUid) return;
    if (!hasPendingInput(pendingRef.current)) return;

    console.warn(
      'Character switched while a message was queued — dropping it instead of sending it to the new character:',
      joinPendingInput(pendingRef.current),
    );
    setPending(clearPendingInput());
  }, [confUid, setPending]);

  // Flush the queue once she genuinely settles back to idle (normal
  // conversation-chain-end, or config-switched/config-reloaded afterwards —
  // the confUid-switch effect above already cleared the queue first if this
  // idle is actually from a character switch).
  useEffect(() => {
    const prevAiState = prevAiStateRef.current;
    prevAiStateRef.current = aiState;
    if (prevAiState === aiState) return;
    if (!shouldFlushOnStateChange(aiState)) return;
    flushPendingInput();
  }, [aiState, flushPendingInput]);

  // Mode switch (pet ↔ window) unmounts whichever component owns this hook
  // instance. No hand-off to the other mode's instance — just don't drop a
  // queued message silently.
  useEffect(() => () => {
    if (hasPendingInput(pendingRef.current)) {
      console.warn(
        'Text input unmounted with a message still queued — it was dropped:',
        joinPendingInput(pendingRef.current),
      );
    }
  }, []);

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || !wsContext) return;

    setInputText('');
    if (autoStopMic) stopMic();

    const decision = decideSend(aiState, groupMembers.length);
    if (decision === 'queue') {
      // Do NOT interrupt her. Hold the message; it's sent (joined with
      // anything else queued meanwhile) once she's done, or sooner if the
      // user explicitly hits interrupt. 排隊時不進對話，只顯示在「排隊中」；
      // 真的送出時（flushPendingInput）才進。
      setPending(enqueuePendingInput(pendingRef.current, text));
      return;
    }
    if (decision === 'interrupt-then-send') {
      // Group chat: a queue would flush between members while the group
      // task is still running, and the backend drops that text (see
      // decideSend). Cut the round off and send now, as before the queue.
      interrupt();
    }

    // Anything still queued (e.g. typed while she was speaking, then the
    // user hit interrupt and immediately sent another message before the
    // queue had a chance to flush) must go out ahead of this one, not
    // after — chat history already shows it in that order.
    const outgoing = mergeQueuedWithImmediate(pendingRef.current, text);
    pendingRef.current.queue.forEach((line) => appendHumanMessage(line));
    appendHumanMessage(text);
    setPending(clearPendingInput());
    await sendTextInput(outgoing);
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
    flushPending: flushPendingInput,
    queued,
    removeQueued,
  };
}
