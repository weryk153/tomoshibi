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

// 拖曳平移與滾輪縮放的邊界。距離就是 model_dict 的 camera.distance——變大＝鏡頭
// 拉遠＝角色變小。夾在這個範圍內，免得滾過頭把角色縮成一點或穿進臉裡再也找不回來。
const MIN_DISTANCE = 0.4;
const MAX_DISTANCE = 8;
// 每一格滾輪改變距離的比例。用乘法而不是加法：拉遠時一格跨得多、湊近時跨得少，
// 手感才會從頭到尾一致。
const WHEEL_STEP = 0.0015;

export function VRMAvatar(): JSX.Element {
  const { t } = useTranslation();
  const { modelInfo } = useLive2DConfig();
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const lookAtPointer = modelInfo?.lookAtPointer !== false;
  const lookAtPointerRef = useRef(lookAtPointer);
  lookAtPointerRef.current = lookAtPointer;
  // 拖曳平移與滾輪縮放各自受設定頁的開關控制（跟 Live2D 同兩個欄位）。
  // 跟 lookAtPointer 同樣用 ref 帶進 effect：放進依賴陣列的話，使用者每切一次
  // 開關就會重建整個 WebGL context、模型重載一次。
  const pointerInteractiveRef = useRef(true);
  pointerInteractiveRef.current = modelInfo?.pointerInteractive !== false;
  const scrollToResizeRef = useRef(true);
  scrollToResizeRef.current = modelInfo?.scrollToResize !== false;

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
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.0));
    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(1, 2, 3);
    scene.add(key);

    const lookTarget = new THREE.Object3D();
    scene.add(lookTarget);

    // 使用者拖出來的平移與縮放。Live2D 的縮放也只活在當次工作階段（見
    // use-live2d-resize.ts 的 lastScaleRef），這裡刻意比照：不寫回 model_dict。
    //
    // 用 effect 內的區域變數而不是 React state——state 一變整個 effect 會重跑，
    // WebGL context 跟著重建，畫面會閃一下而且模型要重載。換角色時 effect 本來
    // 就會重跑，等於自動復位。
    let panX = 0;
    let panY = 0;
    let distance = camDistance;

    // 視線的休息位置要跟著鏡頭走，否則一拖曳角色就會盯著原本鏡頭在的地方看。
    const restGaze = () => lookTarget.position.set(panX, camHeight + panY, distance);

    const applyView = () => {
      camera.position.set(panX, camHeight + panY, distance);
      camera.lookAt(panX, camHeight + panY, 0);
      if (!lookAtPointerRef.current) restGaze();
    };
    applyView();
    restGaze();

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
        restGaze();
        return;
      }
      const r = container.getBoundingClientRect();
      const nx = ((e.clientX - r.left) / r.width) * 2 - 1;
      const ny = -(((e.clientY - r.top) / r.height) * 2 - 1);
      lookTarget.position.set(
        panX + nx * 0.6,
        camHeight + panY + ny * 0.4,
        distance * 0.6,
      );
    };
    window.addEventListener("pointermove", onPointer);

    // --- 拖曳平移 / 滾輪縮放 ---------------------------------------------
    //
    // 移動的是鏡頭，不是模型：角色永遠站在原點，拖曳讓鏡頭往反方向平移，看起來
    // 就是角色跟著游標走。Live2D 那套是改 Cubism 的 _modelMatrix，3D 這邊沒有
    // 對應的東西，所以完全是另一套實作。
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    const onDragStart = (e: PointerEvent) => {
      if (e.button !== 0 || !pointerInteractiveRef.current) return;
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      container.setPointerCapture?.(e.pointerId);
    };

    const onDragMove = (e: PointerEvent) => {
      if (!dragging) return;
      // 拖到一半被關掉開關：當場收手，不要繼續跟著游標跑。
      if (!pointerInteractiveRef.current) {
        dragging = false;
        return;
      }
      // 螢幕像素換算成世界單位：可視高度 = 2 · distance · tan(fov/2)，除以容器
      // 高度就是「一像素等於幾公尺」。不這樣換算的話，拉遠時角色會追不上游標、
      // 湊近時又會飛出去。
      const h = Math.max(1, container.clientHeight);
      const worldPerPx = (2 * distance * Math.tan((camera.fov * Math.PI) / 360)) / h;
      panX -= (e.clientX - lastX) * worldPerPx;
      panY += (e.clientY - lastY) * worldPerPx;
      lastX = e.clientX;
      lastY = e.clientY;
      applyView();
    };

    const onDragEnd = (e: PointerEvent) => {
      if (!dragging) return;
      dragging = false;
      container.releasePointerCapture?.(e.pointerId);
    };

    const onWheel = (e: WheelEvent) => {
      // 關掉滾輪縮放時就不要攔截，讓事件照常冒泡去捲動頁面。
      if (!scrollToResizeRef.current) return;
      // 不 preventDefault 的話，在角色上滾滾輪會連帶捲動整個頁面。
      e.preventDefault();
      distance = Math.min(
        MAX_DISTANCE,
        Math.max(MIN_DISTANCE, distance * (1 + e.deltaY * WHEEL_STEP)),
      );
      applyView();
    };

    // 沒有持久化，所以一定要留一條回頭路：拖到畫面外就再也拉不回來了。
    const onResetView = () => {
      panX = 0;
      panY = 0;
      distance = camDistance;
      applyView();
    };

    container.addEventListener("pointerdown", onDragStart);
    container.addEventListener("pointermove", onDragMove);
    container.addEventListener("pointerup", onDragEnd);
    container.addEventListener("pointercancel", onDragEnd);
    container.addEventListener("wheel", onWheel, { passive: false });
    container.addEventListener("dblclick", onResetView);

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
      container.removeEventListener("pointerdown", onDragStart);
      container.removeEventListener("pointermove", onDragMove);
      container.removeEventListener("pointerup", onDragEnd);
      container.removeEventListener("pointercancel", onDragEnd);
      container.removeEventListener("wheel", onWheel);
      container.removeEventListener("dblclick", onResetView);
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
