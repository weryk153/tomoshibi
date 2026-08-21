/* eslint-disable no-use-before-define */
/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable no-underscore-dangle */
import { useEffect, useCallback, RefObject, useRef } from 'react';
import { ModelInfo } from '@/context/live2d-config-context';
import { LAppDelegate } from '../../../WebSDK/src/lappdelegate';
import { LAppLive2DManager } from '../../../WebSDK/src/lapplive2dmanager';
import { useMode } from '@/context/mode-context';
import { pinchScale, pointerDistance, type PointerPos } from '@/services/pinch-zoom';

// Constants for model scaling behavior
const MIN_SCALE = 0.1;
const MAX_SCALE = 5.0;
const EASING_FACTOR = 0.3; // Controls animation smoothness
const WHEEL_SCALE_STEP = 0.03; // Scale change per wheel tick
const DEFAULT_SCALE = 1.0; // Default scale if not specified

interface UseLive2DResizeProps {
  containerRef: RefObject<HTMLDivElement>;
  modelInfo?: ModelInfo;
  showSidebar?: boolean; // Sidebar collapse state
}

/**
 * Applies scale to both model and view matrices
 * @param scale - The scale value to apply
 */
export const applyScale = (scale: number) => {
  try {
    const manager = LAppLive2DManager.getInstance();
    if (!manager) return;

    const model = manager.getModel(0);
    if (!model) return;

    // @ts-ignore
    model._modelMatrix.scale(scale, scale);
  } catch (error) {
    console.debug('Model not ready for scaling yet');
  }
};

/**
 * Hook to handle Live2D model resizing and scaling
 * Provides smooth scaling animation and window resize handling
 */
export const useLive2DResize = ({
  containerRef,
  modelInfo,
  showSidebar,
}: UseLive2DResizeProps) => {
  const { mode } = useMode();
  const isPet = mode === 'pet';
  const animationFrameIdRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const isResizingRef = useRef<boolean>(false);

  // Initialize scale references
  const initialScale = modelInfo?.kScale || DEFAULT_SCALE;
  const lastScaleRef = useRef<number>(initialScale);
  const targetScaleRef = useRef<number>(initialScale);
  const animationFrameRef = useRef<number>();
  const isAnimatingRef = useRef<boolean>(false);
  const hasAppliedInitialScale = useRef<boolean>(false);

  // Previous container dimensions for change detection
  const lastContainerDimensionsRef = useRef<{width: number, height: number}>({ width: 0, height: 0 });

  // Previous sidebar state
  const prevSidebarStateRef = useRef<boolean | undefined>(showSidebar);

  /**
   * Reset scale state when model changes
   */
  useEffect(() => {
    const newInitialScale = modelInfo?.kScale || DEFAULT_SCALE;
    lastScaleRef.current = newInitialScale;
    targetScaleRef.current = newInitialScale;
    hasAppliedInitialScale.current = false;

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      isAnimatingRef.current = false;
    }

    const resizeHandle = requestAnimationFrame(() => {
      handleResize();
    });

    return () => cancelAnimationFrame(resizeHandle);
  }, [modelInfo?.url, modelInfo?.kScale]);

  /**
   * Smooth animation loop for scaling
   * Uses linear interpolation for smooth transitions
   */
  const animateEase = useCallback(() => {
    const clampedTargetScale = Math.max(
      MIN_SCALE,
      Math.min(MAX_SCALE, targetScaleRef.current),
    );

    const currentScale = lastScaleRef.current;
    const diff = clampedTargetScale - currentScale;

    const newScale = currentScale + diff * EASING_FACTOR;
    applyScale(newScale);
    lastScaleRef.current = newScale;

    animationFrameRef.current = requestAnimationFrame(animateEase);
  }, []);

  /**
   * Handles mouse wheel events for scaling
   * Initiates smooth scaling animation
   */
  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    if (!modelInfo?.scrollToResize) return;

    const direction = e.deltaY > 0 ? -1 : 1;
    const increment = WHEEL_SCALE_STEP * direction;

    const currentActualScale = lastScaleRef.current;
    const newTargetScale = Math.max(
      MIN_SCALE,
      Math.min(MAX_SCALE, currentActualScale + increment),
    );

    targetScaleRef.current = newTargetScale;

    if (!isAnimatingRef.current) {
      isAnimatingRef.current = true;
      animationFrameRef.current = requestAnimationFrame(animateEase);
    }
  }, [modelInfo?.scrollToResize, animateEase]);

  // ---- 雙指縮放 ----------------------------------------------------------
  // 手機沒有滾輪，所以在這之前完全沒辦法調整角色大小。用 pointer 事件而不是
  // touch 事件，跟拖曳那半一致，也順便支援觸控筆與觸控螢幕筆電。
  //
  // 縮放走「起始距離 → 現在距離」的比例（見 services/pinch-zoom.ts），不是每次
  // 移動累加增量——累加會讓誤差隨手指抖動漂移，手指回到原位大小卻回不去。
  const activePointers = useRef<Map<number, PointerPos>>(new Map());

  const pinchStart = useRef<{ distance: number; scale: number } | null>(null);

  const handlePointerDownZoom = useCallback((e: PointerEvent) => {
    if (e.pointerType === 'mouse') return;
    activePointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointers.current.size === 2) {
      const [a, b] = [...activePointers.current.values()];
      pinchStart.current = {
        distance: pointerDistance(a, b),
        scale: lastScaleRef.current,
      };
    }
  }, []);

  const handlePointerMoveZoom = useCallback((e: PointerEvent) => {
    if (!activePointers.current.has(e.pointerId)) return;
    activePointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointers.current.size !== 2 || !pinchStart.current) return;
    if (!modelInfo?.scrollToResize) return;

    e.preventDefault();
    const [a, b] = [...activePointers.current.values()];
    targetScaleRef.current = pinchScale(
      pinchStart.current.distance,
      pointerDistance(a, b),
      pinchStart.current.scale,
      MIN_SCALE,
      MAX_SCALE,
    );
    if (!isAnimatingRef.current) {
      isAnimatingRef.current = true;
      animationFrameRef.current = requestAnimationFrame(animateEase);
    }
  }, [modelInfo?.scrollToResize, animateEase]);

  const handlePointerEndZoom = useCallback((e: PointerEvent) => {
    activePointers.current.delete(e.pointerId);
    // 只剩一根手指就結束這次縮放；下次湊滿兩指時會用當下的大小重新起算，
    // 不然放開一指再按回去會從舊的基準跳一下。
    if (activePointers.current.size < 2) pinchStart.current = null;
  }, []);

  /**
   * Pre-process container resize
   * Preserve aspect ratio temporarily before actual change
   */
  const beforeResize = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    isResizingRef.current = true;

    if (animationFrameIdRef.current !== null) {
      cancelAnimationFrame(animationFrameIdRef.current);
      animationFrameIdRef.current = null;
    }
  }, []);

  /**
   * Handles window/container resize events
   * Updates canvas dimensions and model scaling
   */
  const handleResize = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    if (!isResizingRef.current) {
      beforeResize();
    }

    try {
      const containerBounds = containerRef.current?.getBoundingClientRect();
      const { width, height } = isPet
        ? { width: window.innerWidth, height: window.innerHeight }
        : containerBounds || { width: 0, height: 0 };

      const lastDimensions = lastContainerDimensionsRef.current;
      const sidebarChanged = prevSidebarStateRef.current !== showSidebar;
      const dimensionsChanged = Math.abs(lastDimensions.width - width) > 1 || Math.abs(lastDimensions.height - height) > 1;
      const hasChanged = dimensionsChanged || sidebarChanged;

      if (!hasChanged && hasAppliedInitialScale.current) {
        isResizingRef.current = false;
        return;
      }

      lastContainerDimensionsRef.current = { width, height };
      prevSidebarStateRef.current = showSidebar;

      if (!containerBounds && !isPet) {
        console.warn('[Resize] Container bounds not available in window mode.');
      }
      if (width === 0 || height === 0) {
        console.warn('[Resize] Width or Height is zero, skipping canvas/delegate update.');
        isResizingRef.current = false;
        return;
      }

      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      const delegate = LAppDelegate.getInstance();
      if (delegate) {
        delegate.onResize();
      } else {
        console.warn('[Resize] LAppDelegate instance not found.');
      }

      isResizingRef.current = false;
    } catch (error) {
      isResizingRef.current = false;
    }
  }, [isPet, containerRef, modelInfo?.kScale, modelInfo?.initialXshift, modelInfo?.initialYshift, showSidebar, beforeResize, canvasRef]);

  // Immediately respond to sidebar state changes
  useEffect(() => {
    if (prevSidebarStateRef.current !== showSidebar) {
      if (animationFrameIdRef.current !== null) {
        cancelAnimationFrame(animationFrameIdRef.current);
      }
      animationFrameIdRef.current = requestAnimationFrame(() => {
        handleResize();
        animationFrameIdRef.current = null;
      });
    }
  }, [showSidebar, handleResize]);

  // Set up event listeners and cleanup for wheel + pinch scaling
  useEffect(() => {
    const canvasElement = canvasRef.current;
    if (canvasElement) {
      canvasElement.addEventListener('wheel', handleWheel, { passive: false });
      // pinch 綁在 container 而不是 canvas。拖曳的處理器在 container 上，而且
      // pointerdown 會 setPointerCapture——第一根手指被捕捉之後，它的事件只送到
      // container，canvas 再也看不到它。綁在 canvas 上就只看得到第二根手指，
      // 湊不滿兩指，pinch 永遠不會啟動（實機驗證出來的：桌面滾輪正常、手機
      // 完全不能縮放）。container 兩根都收得到：第一根經由捕捉、第二根經由冒泡。
      //
      // passive: false —— pinch 途中要 preventDefault，否則瀏覽器會同時縮放整頁。
      // 標成 HTMLElement：聯集型別（div | canvas）會讓 TS 解不出
      // addEventListener 的多載，退回 (e: Event) => void 的基底簽章。
      const zoomTarget: HTMLElement = containerRef.current ?? canvasElement;
      zoomTarget.addEventListener('pointerdown', handlePointerDownZoom);
      zoomTarget.addEventListener('pointermove', handlePointerMoveZoom, { passive: false });
      zoomTarget.addEventListener('pointerup', handlePointerEndZoom);
      zoomTarget.addEventListener('pointercancel', handlePointerEndZoom);
      return () => {
        canvasElement.removeEventListener('wheel', handleWheel);
        zoomTarget.removeEventListener('pointerdown', handlePointerDownZoom);
        zoomTarget.removeEventListener('pointermove', handlePointerMoveZoom);
        zoomTarget.removeEventListener('pointerup', handlePointerEndZoom);
        zoomTarget.removeEventListener('pointercancel', handlePointerEndZoom);
      };
    }
    return undefined;
    // 三個 pinch 處理器都要進 deps：handlePointerMoveZoom 依賴
    // modelInfo.scrollToResize，漏掉的話那個設定改變後監聽器不會重綁，
    // 留著的是讀到舊值的閉包——關掉縮放之後手勢照樣有效。
  }, [handleWheel, canvasRef, containerRef,
    handlePointerDownZoom, handlePointerMoveZoom, handlePointerEndZoom]);

  // Clean up animations on unmount
  useEffect(() => () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = undefined;
    }
    if (animationFrameIdRef.current !== null) {
      cancelAnimationFrame(animationFrameIdRef.current);
      animationFrameIdRef.current = null;
    }
  }, []);


  // Monitor container size changes using ResizeObserver
  useEffect(() => {
    const containerElement = containerRef.current;
    if (!containerElement) {
      return undefined;
    }

    if (animationFrameIdRef.current !== null) cancelAnimationFrame(animationFrameIdRef.current);
    animationFrameIdRef.current = requestAnimationFrame(() => {
      handleResize();
      animationFrameIdRef.current = null;
    });

    const observer = new ResizeObserver(() => {
      if (!isResizingRef.current) {
        if (animationFrameIdRef.current !== null) cancelAnimationFrame(animationFrameIdRef.current);
        animationFrameIdRef.current = requestAnimationFrame(() => {
          handleResize();
          animationFrameIdRef.current = null;
        });
      }
    });

    observer.observe(containerElement);

    return () => {
      if (animationFrameIdRef.current !== null) {
        cancelAnimationFrame(animationFrameIdRef.current);
        animationFrameIdRef.current = null;
      }
      observer.disconnect();
    };
  }, [containerRef, handleResize]);

  // Monitor window size changes (mainly for 'pet' mode or fallback)
  useEffect(() => {
    const handleWindowResize = () => {
      if (!isResizingRef.current) {
        if (animationFrameIdRef.current !== null) cancelAnimationFrame(animationFrameIdRef.current);
        animationFrameIdRef.current = requestAnimationFrame(() => {
          handleResize();
          animationFrameIdRef.current = null;
        });
      }
    };

    window.addEventListener('resize', handleWindowResize);

    return () => {
      window.removeEventListener('resize', handleWindowResize);
      if (animationFrameIdRef.current !== null) {
        cancelAnimationFrame(animationFrameIdRef.current);
        animationFrameIdRef.current = null;
      }
    };
  }, [handleResize]);

  return { canvasRef, handleResize };
};

/**
 * Helper function to set model scale with device pixel ratio consideration
 * @deprecated This logic might be better handled within the view matrix scaling
 */
export const setModelScale = (
  model: any,
  kScale: string | number | undefined,
) => {
  if (!model || kScale === undefined) return;
  console.warn("setModelScale is potentially deprecated; scaling is primarily handled by view matrix now.");
};

/**
 * Helper function to center model in container with optional offset
 * This is now primarily handled within handleResize
 */
export const resetModelPosition = (
  model: any,
  width: number, // Logical width (CSS pixels)
  height: number, // Logical height (CSS pixels)
  initialXshift: number | undefined, // Shift in logical pixels
  initialYshift: number | undefined, // Shift in logical pixels
) => {
  if (!model || typeof model.setPosition !== 'function') return;

  const dpr = window.devicePixelRatio || 1;
  const canvasWidth = width * dpr; // Calculate canvas pixel dimensions
  const canvasHeight = height * dpr;

  const initXshiftPixels = Number(initialXshift || 0) * dpr; // Convert shift to canvas pixels
  const initYshiftPixels = Number(initialYshift || 0) * dpr;

  const centerX = canvasWidth / 2 + initXshiftPixels;
  const centerY = canvasHeight / 2 + initYshiftPixels;

  // @ts-ignore
  model.setPosition(centerX, centerY);
};
