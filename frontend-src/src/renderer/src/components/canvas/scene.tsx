import { Box } from "@chakra-ui/react";
import { lazy, memo, Suspense, useCallback, useEffect, useState } from "react";
import { useScene } from "@/context/scene-context";
import { CURRENT_BACKGROUND_SCENE_ID } from "@/scenes/scene";
import Background from "./background";
import "./scene.css";

const Scene3D = lazy(() => import("./scene-3d"));

const Scene = memo(() => {
  const { activeScene, resolvedSourceUrl } = useScene();
  const [failed, setFailed] = useState(false);
  const handleError = useCallback(() => setFailed(true), []);

  useEffect(() => setFailed(false), [activeScene.id, resolvedSourceUrl]);

  useEffect(() => {
    const syncLive2DScene = () => {
      const manager = (window as any).getLive2DManager?.();
      if (!manager) return;
      if (activeScene.type !== "live2d" || !resolvedSourceUrl) {
        manager.clearBackgroundScene?.();
        return;
      }
      manager.setBackgroundScene?.(resolvedSourceUrl, {
        ...activeScene.live2d,
        opacity: activeScene.opacity,
        transitionMs: activeScene.transitionMs,
      });
    };
    syncLive2DScene();
    window.addEventListener("tomoshibi:live2d-ready", syncLive2DScene);
    return () => {
      window.removeEventListener("tomoshibi:live2d-ready", syncLive2DScene);
    };
  }, [
    activeScene.live2d,
    activeScene.opacity,
    activeScene.transitionMs,
    activeScene.type,
    resolvedSourceUrl,
  ]);

  useEffect(
    () => () => {
      (window as any).getLive2DManager?.()?.clearBackgroundScene?.();
    },
    [],
  );

  if (
    activeScene.id === CURRENT_BACKGROUND_SCENE_ID ||
    !resolvedSourceUrl ||
    failed
  ) {
    return <Background />;
  }

  if (activeScene.type === "live2d") {
    return <Background />;
  }

  const sharedStyle = {
    width: "100%",
    height: "100%",
    opacity: activeScene.opacity,
    objectFit: activeScene.fit,
  } as const;

  return (
    <Box
      key={`${activeScene.id}:${resolvedSourceUrl}`}
      className="tomoshibi-scene"
      data-scene-id={activeScene.id}
      data-scene-type={activeScene.type}
      style={
        {
          "--scene-transition": `${activeScene.transitionMs}ms`,
        } as React.CSSProperties
      }
    >
      {activeScene.type === "image" && (
        <img
          src={resolvedSourceUrl}
          alt={activeScene.name}
          style={sharedStyle}
          onError={handleError}
        />
      )}
      {activeScene.type === "video" && (
        <video
          src={resolvedSourceUrl}
          autoPlay
          playsInline
          loop={activeScene.loop}
          muted={activeScene.muted}
          style={sharedStyle}
          onError={handleError}
        />
      )}
      {activeScene.type === "model3d" && (
        <Suspense fallback={null}>
          <Scene3D
            sourceUrl={resolvedSourceUrl}
            config={activeScene.model}
            opacity={activeScene.opacity}
            onError={handleError}
          />
        </Suspense>
      )}
    </Box>
  );
});

Scene.displayName = "Scene";

export default Scene;
