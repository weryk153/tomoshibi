// frontend-src/src/renderer/src/avatar/vrm/vrm-avatar.tsx
// VRM 的 three.js canvas。結構仿 components/canvas/scene-3d.tsx：一個 effect 建
// renderer、載模型、跑 rAF、卸載時全部 dispose + forceContextLoss（不做的話
// 切幾次角色 WebGL context 就用完）。
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";
import { useTranslation } from "react-i18next";
import { useLive2DConfig } from "@/context/live2d-config-context";
import { toaster } from "@/components/ui/tw/toaster";
import { registerRenderer, isClipMotion } from "../character-renderer";
import { ExpressionController } from "./expression-controller";
import { MotionPlayer, IDLE_CLIP } from "./motion-player";
import { VRMRenderer } from "./vrm-renderer";

const DEFAULT_CAMERA = { distance: 1.6, height: 1.35 };

export function VRMAvatar(): JSX.Element {
  const { t } = useTranslation();
  const { modelInfo } = useLive2DConfig();
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const lookAtPointer = modelInfo?.lookAtPointer !== false;
  const lookAtPointerRef = useRef(lookAtPointer);
  lookAtPointerRef.current = lookAtPointer;

  const url = modelInfo?.url ?? "";
  const camDistance = modelInfo?.camera?.distance ?? DEFAULT_CAMERA.distance;
  const camHeight = modelInfo?.camera?.height ?? DEFAULT_CAMERA.height;
  // motionMap 的 clip 名單；用 JSON 當依賴，避免每次 render 都重載。
  const clipsKey = JSON.stringify(
    Object.values(modelInfo?.motionMap ?? {})
      .filter(isClipMotion)
      .map((m) => m.clip)
      .sort(),
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !url) return undefined;
    setError(false);
    let disposed = false;
    let frameId = 0;
    let vrm: VRM | null = null;
    let motions: MotionPlayer | null = null;
    let avatarRenderer: VRMRenderer | null = null;
    let unregister: (() => void) | null = null;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch (e) {
      console.warn("[VRM] WebGL is unavailable:", e);
      setError(true);
      return undefined;
    }
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);
    // setSize(w, h, false) 的 false 是 updateStyle=false：只改 drawing buffer，不寫 CSS 尺寸。
    // 那 canvas 的 CSS 寬高就只剩瀏覽器預設的 attribute 值（= drawing buffer 的像素數），
    // 在 Retina（pixelRatio 2）上等於容器的兩倍大。CSS 尺寸交給這三行固定住。
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
    camera.position.set(0, camHeight, camDistance);
    camera.lookAt(0, camHeight, 0);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.0));
    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(1, 2, 3);
    scene.add(key);

    const lookTarget = new THREE.Object3D();
    lookTarget.position.set(0, camHeight, camDistance);
    scene.add(lookTarget);

    const resize = () => {
      const w = Math.max(1, container.clientWidth);
      const h = Math.max(1, container.clientHeight);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    const onPointer = (e: PointerEvent) => {
      if (!lookAtPointerRef.current) {
        // 關掉跟隨時要把視線收回鏡頭，否則會凍在游標最後停的地方。復位放在這裡
        // 而不是另開 effect，是為了不讓 lookAtPointer 進依賴陣列——那會重建整個
        // WebGL context。下一次滑鼠動就會歸位。
        lookTarget.position.set(0, camHeight, camDistance);
        return;
      }
      const r = container.getBoundingClientRect();
      const nx = ((e.clientX - r.left) / r.width) * 2 - 1;
      const ny = -(((e.clientY - r.top) / r.height) * 2 - 1);
      lookTarget.position.set(nx * 0.6, camHeight + ny * 0.4, camDistance * 0.6);
    };
    window.addEventListener("pointermove", onPointer);

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    loader.load(
      url,
      async (gltf) => {
        if (disposed) return;
        const loaded = gltf.userData.vrm as VRM | undefined;
        if (!loaded) {
          console.warn("[VRM] file has no VRM extension:", url);
          setError(true);
          toaster.create({ id: "vrm-load-failed", title: t("error.vrmLoad"), type: "error", duration: 6000 });
          return;
        }
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.combineSkeletons(gltf.scene);
        VRMUtils.rotateVRM0(loaded);
        vrm = loaded;
        if (vrm.lookAt) vrm.lookAt.target = lookTarget;
        scene.add(vrm.scene);

        motions = new MotionPlayer(vrm);
        const base = url.slice(0, url.lastIndexOf("/"));
        const names = [IDLE_CLIP, ...(JSON.parse(clipsKey) as string[])];
        await Promise.all(names.map((n) => motions!.load(n, `${base}/motions/${n}.vrma`)));
        if (disposed) return;
        motions.playIdle();

        const expressions = new ExpressionController({
          has: (name) => !!vrm?.expressionManager?.getExpression(name),
          setValue: (name, w) => vrm?.expressionManager?.setValue(name, w),
        });
        avatarRenderer = new VRMRenderer(vrm, motions, expressions);
        unregister = registerRenderer(avatarRenderer);
      },
      undefined,
      (e) => {
        if (disposed) return;
        console.warn("[VRM] load failed:", e);
        setError(true);
        toaster.create({ id: "vrm-load-failed", title: t("error.vrmLoad"), type: "error", duration: 6000 });
      },
    );

    const clock = new THREE.Clock();
    let running = true;
    const animate = () => {
      if (!running) return;
      frameId = window.requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.1);
      avatarRenderer?.update(dt);
      renderer.render(scene, camera);
    };
    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        window.cancelAnimationFrame(frameId);
      } else if (!running) {
        running = true;
        clock.getDelta();
        animate();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    animate();

    return () => {
      disposed = true;
      running = false;
      window.cancelAnimationFrame(frameId);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pointermove", onPointer);
      observer.disconnect();
      unregister?.();
      motions?.dispose();
      if (vrm) {
        scene.remove(vrm.scene);
        VRMUtils.deepDispose(vrm.scene);
      }
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, [url, camDistance, camHeight, clipsKey, t]);

  return (
    <div
      ref={containerRef}
      data-avatar-renderer="vrm"
      data-avatar-error={error || undefined}
      style={{ position: "absolute", inset: 0, overflow: "hidden" }}
    />
  );
}
