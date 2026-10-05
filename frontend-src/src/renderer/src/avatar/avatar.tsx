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
import { getActiveRenderer, onRendererRegistered } from "./character-renderer";
import {
  getCharacterMood,
  onCharacterMoodChange,
  RESTING_REFRESH_MS,
  restingFor,
  shouldApplyResting,
  type Resting,
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
  //
  // 重算不等於重套：設定頁試播、Live2D 點頭的隨機表情都是使用者剛叫出來的臉，
  // 每 10 秒一律 resetExpression() 會把它們蓋掉。所以記住上次真的套上去的值，
  // 只有表情換了才重套（shouldApplyResting）；同一個表情只是淡了，交給
  // setRestingExpression（VRM 只在臉還是她的心情時更新濃淡，Live2D 沒有濃淡）。
  // 進 IDLE、心情真的來了、換了新 renderer 時一律套一次（applied 歸 null）。
  useEffect(() => {
    if (aiState !== AiStateEnum.IDLE) return undefined;
    let applied: Resting | null = null;
    const refresh = () => {
      const renderer = getActiveRenderer();
      // 還沒註冊（VRM 是 lazy import）或模型還沒載完：不套也不記，等註冊通知或下一次 tick。
      if (!renderer || renderer.isReady?.() === false) return;
      const next = restingFor(getCharacterMood(), modelInfo?.emotionMap, Date.now() / 1000);
      renderer.setRestingExpression(next.expression, next.intensity);
      if (shouldApplyResting(applied, next)) renderer.resetExpression();
      applied = next;
    };
    const applyAgain = () => {
      applied = null;
      refresh();
    };
    refresh();
    const timer = window.setInterval(refresh, RESTING_REFRESH_MS);
    const stopMood = onCharacterMoodChange(applyAgain);
    const stopRegistered = onRendererRegistered(applyAgain);
    return () => {
      window.clearInterval(timer);
      stopMood();
      stopRegistered();
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
