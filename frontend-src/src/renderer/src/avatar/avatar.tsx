// frontend-src/src/renderer/src/avatar/avatar.tsx
// 角色層的掛載點。這裡跑的是「不管掛哪個 renderer 都要在」的東西：IPC、打斷、
// 音訊佇列、IDLE 時清表情。renderer 元件本身只負責畫與註冊自己。
import { useEffect } from "react";
import { useLive2DConfig } from "@/context/live2d-config-context";
import { useAiState, AiStateEnum } from "@/context/ai-state-context";
import { useIpcHandlers } from "@/hooks/utils/use-ipc-handlers";
import { useInterrupt } from "@/hooks/utils/use-interrupt";
import { useAudioTask } from "@/hooks/utils/use-audio-task";
import { Live2D } from "@/components/canvas/live2d";
import { getActiveRenderer } from "./character-renderer";
import { VRMAvatar } from "./vrm/vrm-avatar";

export function Avatar(): JSX.Element {
  const { modelInfo } = useLive2DConfig();
  const { aiState } = useAiState();

  useIpcHandlers();
  useInterrupt();
  useAudioTask();

  // Reset expression to default when AI state becomes idle
  useEffect(() => {
    if (aiState === AiStateEnum.IDLE) {
      getActiveRenderer()?.resetExpression();
    }
  }, [aiState, modelInfo]);

  if (modelInfo?.type === "vrm") return <VRMAvatar />;
  return <Live2D />;
}
