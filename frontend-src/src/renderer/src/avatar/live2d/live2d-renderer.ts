// frontend-src/src/renderer/src/avatar/live2d/live2d-renderer.ts
// CharacterRenderer 的 Live2D 實作。這裡的每一行都是從 use-audio-task.ts 和
// audio-manager.ts 原樣搬過來的，只是換了個家；行為不變。
/* eslint-disable no-underscore-dangle */
import * as LAppDefine from "@cubismsdksamples/lappdefine";
import type { CharacterRenderer, SpeakCues } from "../character-renderer.ts";
import { isClipMotion } from "../character-renderer.ts";
import {
  setLive2DExpression,
  clearLive2DExpression,
} from "@/hooks/canvas/use-live2d-expression";
import { playLive2DMotion } from "@/hooks/canvas/use-live2d-motion";

function getModel(): any | null {
  const manager = (window as any).getLive2DManager?.();
  return manager?.getModel(0) ?? null;
}

function getAdapter(): any | null {
  return (window as any).getLAppAdapter?.() ?? null;
}

export function createLive2DRenderer(): CharacterRenderer {
  return {
    beginSegment(audio, cues: SpeakCues, firstOfResponse) {
      // Get Live2D manager and model
      const live2dManager = (window as any).getLive2DManager?.();
      if (!live2dManager) {
        console.error("Live2D manager not found");
        return;
      }

      const model = live2dManager.getModel(0);
      if (!model) {
        console.error("Live2D model not found at index 0");
        return;
      }
      console.log("Found model for audio playback");

      if (!model._wavFileHandler) {
        console.warn("Model does not have _wavFileHandler for lip sync");
      } else {
        console.log("Model has _wavFileHandler available");
      }

      const lappAdapter = getAdapter();

      if (lappAdapter && cues.expression !== undefined) {
        setLive2DExpression(
          cues.expression,
          lappAdapter,
          `Set expression to: ${cues.expression}`,
        );
      }

      // Live2D's motion queue is single-slot, so only the first motion of the
      // segment is used (mirrors expressions[0]).
      const motion = cues.motion && !isClipMotion(cues.motion) ? cues.motion : undefined;
      if (lappAdapter && motion) {
        playLive2DMotion(
          motion,
          lappAdapter,
          `Playing motion: ${motion.group}[${motion.index}]`,
        );
      }

      // Start Talk once for the whole queued response. Replaying it for every
      // TTS chunk causes visible resets at sentence boundaries.
      if (firstOfResponse && LAppDefine && LAppDefine.PriorityNormal) {
        if (motion) {
          // This segment carries an LLM-triggered motion, started above at
          // PriorityForce (3) so it can play *while the character speaks*.
          //
          // Skipping Talk here is belt-and-braces rather than load-bearing:
          // `beginSpeaking()` returns true at most once per response, so no
          // later segment restarts Talk anyway, and a Talk request at
          // PriorityNormal (2) would in any case be rejected by
          // `reserveMotion` while the force-priority motion is reserved.
          // It is kept because both of those are properties of code
          // elsewhere — if either changes, requesting Talk here would start
          // cutting the motion short, and that failure would be silent.
          console.log("Skipping 'Talk' motion: this segment triggers an LLM motion");
        } else {
          console.log("Starting random 'Talk' motion");
          model.startRandomMotion("Talk", LAppDefine.PriorityNormal);
        }
      } else if (!LAppDefine || !LAppDefine.PriorityNormal) {
        console.warn("LAppDefine.PriorityNormal not found - cannot start talk motion");
      }

      // Full rigs benefit from the historical sensitivity boost. Kurisu's
      // compact two-state mouth needs the raw envelope so it does not slam
      // into its maximum open sprite on every syllable.
      const lipSyncScale = /\/(?:kurisu_fan)\/$/.test(model._modelHomeDir ?? "")
        ? 1.0
        : 2.0;

      if (model._wavFileHandler) {
        if (!model._wavFileHandler._initialized) {
          console.log("Applying enhanced lip sync");
          model._wavFileHandler._initialized = true;
          const originalUpdate = model._wavFileHandler.update.bind(model._wavFileHandler);
          model._wavFileHandler.update = function (deltaTimeSeconds: number) {
            const result = originalUpdate(deltaTimeSeconds);
            // @ts-ignore
            this._lastRms = Math.min(2.0, this._lastRms * lipSyncScale);
            return result;
          };
        }
        model._wavFileHandler.start(audio.src);
      }
    },

    stop() {
      const model = getModel();
      if (!model) return;
      if (model._wavFileHandler) {
        try {
          model._wavFileHandler.releasePcmData();
          console.log("[Live2DRenderer] Called _wavFileHandler.releasePcmData()");
          model._wavFileHandler._lastRms = 0.0;
          model._wavFileHandler._sampleOffset = 0;
          model._wavFileHandler._userTimeSeconds = 0.0;
          if (typeof model._smoothedLipSyncValue === "number") {
            model._smoothedLipSyncValue = 0.0;
          }
        } catch (e) {
          console.error("[Live2DRenderer] Error resetting wavFileHandler:", e);
        }
      }
      // Starting Idle through Cubism's motion manager crossfades the looping
      // Talk motion instead of leaving it active or stopping it abruptly.
      try {
        if (typeof model.returnToIdleMotion === "function") {
          model.returnToIdleMotion();
        } else if (typeof model.startRandomMotion === "function") {
          model.startRandomMotion("Idle", 3);
        }
      } catch (e) {
        console.error("[Live2DRenderer] Error returning model to idle:", e);
      }
    },

    resetExpression() {
      clearLive2DExpression(getAdapter());
    },
  };
}
