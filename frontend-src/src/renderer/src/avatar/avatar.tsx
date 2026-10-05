// frontend-src/src/renderer/src/avatar/avatar.tsx
// 角色層的掛載點。這裡跑的是「不管掛哪個 renderer 都要在」的東西：IPC、打斷、
// 音訊佇列、IDLE 時回到她心情的臉。renderer 元件本身只負責畫與註冊自己。
import { lazy, Suspense, useEffect } from "react";
import { useLive2DConfig } from "@/context/live2d-config-context";
import { useAiState, AiStateEnum } from "@/context/ai-state-context";
import { useIpcHandlers } from "@/hooks/utils/use-ipc-handlers";
import { useInterrupt } from "@/hooks/utils/use-interrupt";
import { useAudioTask } from "@/hooks/utils/use-audio-task";
import { Live2D } from "@/components/canvas/live2d";
import { getActiveRenderer } from "./character-renderer";
import {
  getCharacterMood,
  onCharacterMoodChange,
  RESTING_REFRESH_MS,
  restingFor,
} from "./mood";

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

  // 回到 IDLE（講完、等你打字）時，臉帶著她現在的心情；心情隨時間淡掉，所以
  // 空檔時每 RESTING_REFRESH_MS 重算一次，新的心情到了也馬上重算。講話中不動：
  // 句子的表情標籤優先。
  useEffect(() => {
    if (aiState !== AiStateEnum.IDLE) return undefined;
    const apply = () => {
      const renderer = getActiveRenderer();
      if (!renderer) return;
      const resting = restingFor(getCharacterMood(), modelInfo?.emotionMap, Date.now() / 1000);
      renderer.setRestingExpression(resting.expression, resting.intensity);
      renderer.resetExpression();
    };
    apply();
    const timer = window.setInterval(apply, RESTING_REFRESH_MS);
    const stop = onCharacterMoodChange(apply);
    return () => {
      window.clearInterval(timer);
      stop();
    };
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
