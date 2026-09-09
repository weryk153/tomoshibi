// frontend-src/src/renderer/src/avatar/avatar.tsx
// 角色層的掛載點。這裡跑的是「不管掛哪個 renderer 都要在」的東西：IPC、打斷、
// 音訊佇列、IDLE 時清表情。renderer 元件本身只負責畫與註冊自己。
import { lazy, Suspense, useEffect } from "react";
import { useLive2DConfig } from "@/context/live2d-config-context";
import { useAiState, AiStateEnum } from "@/context/ai-state-context";
import { useIpcHandlers } from "@/hooks/utils/use-ipc-handlers";
import { useInterrupt } from "@/hooks/utils/use-interrupt";
import { useAudioTask } from "@/hooks/utils/use-audio-task";
import { Live2D } from "@/components/canvas/live2d";
import { getActiveRenderer } from "./character-renderer";

// three + three-vrm 只在真的掛 VRM 角色時才下載；靜態 import 會把它們塞進主 bundle，
// 只用 Live2D 的人也要多載 800 多 KB。
const VRMAvatar = lazy(() =>
  import("./vrm/vrm-avatar").then((m) => ({ default: m.VRMAvatar })),
);

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

  if (modelInfo?.type === "vrm") {
    return (
      <Suspense fallback={null}>
        <VRMAvatar />
      </Suspense>
    );
  }
  return <Live2D />;
}
