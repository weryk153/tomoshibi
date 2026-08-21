/* eslint-disable no-underscore-dangle */
/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable no-use-before-define */
/* eslint-disable no-param-reassign */
/* eslint-disable @typescript-eslint/no-unused-vars */
// @ts-nocheck
import { useEffect, useRef, useCallback, useState, RefObject } from "react";
import { ModelInfo } from "@/context/live2d-config-context";
import { updateModelConfig } from '../../../WebSDK/src/lappdefine';
import { LAppDelegate } from '../../../WebSDK/src/lappdelegate';
import { initializeLive2D } from '@cubismsdksamples/main';
import { useMode } from '@/context/mode-context';
import { decidePlacement } from '@/services/pet-placement';

interface UseLive2DModelProps {
  modelInfo: ModelInfo | undefined;
  canvasRef: RefObject<HTMLCanvasElement>;
}

interface Position {
  x: number;
  y: number;
}

// Thresholds for tap vs drag detection
const TAP_DURATION_THRESHOLD_MS = 200; // Max duration for a tap
const DRAG_DISTANCE_THRESHOLD_PX = 5; // Min distance to be considered a drag

function parseModelUrl(url: string): { baseUrl: string; modelDir: string; modelFileName: string } {
  try {
    const urlObj = new URL(url);
    const { pathname } = urlObj;

    const lastSlashIndex = pathname.lastIndexOf('/');
    if (lastSlashIndex === -1) {
      throw new Error('Invalid model URL format');
    }

    const fullFileName = pathname.substring(lastSlashIndex + 1);
    const modelFileName = fullFileName.replace('.model3.json', '');

    const secondLastSlashIndex = pathname.lastIndexOf('/', lastSlashIndex - 1);
    if (secondLastSlashIndex === -1) {
      throw new Error('Invalid model URL format');
    }

    const modelDir = pathname.substring(secondLastSlashIndex + 1, lastSlashIndex);
    const baseUrl = `${urlObj.protocol}//${urlObj.host}${pathname.substring(0, secondLastSlashIndex + 1)}`;

    return { baseUrl, modelDir, modelFileName };
  } catch (error) {
    console.error('Error parsing model URL:', error);
    return { baseUrl: '', modelDir: '', modelFileName: '' };
  }
}

export const playAudioWithLipSync = (audioPath: string, modelIndex = 0): Promise<void> => new Promise((resolve, reject) => {
  const live2dManager = window.LAppLive2DManager?.getInstance();
  if (!live2dManager) {
    reject(new Error('Live2D manager not initialized'));
    return;
  }

  const fullPath = `/Resources/${audioPath}`;
  const audio = new Audio(fullPath);

  audio.addEventListener('canplaythrough', () => {
    const model = live2dManager.getModel(modelIndex);
    if (model) {
      if (model._wavFileHandler) {
        model._wavFileHandler.start(fullPath);
        audio.play();
      } else {
        reject(new Error('Wav file handler not available on model'));
      }
    } else {
      reject(new Error(`Model index ${modelIndex} not found`));
    }
  });

  audio.addEventListener('ended', () => {
    resolve();
  });

  audio.addEventListener('error', () => {
    reject(new Error(`Failed to load audio: ${fullPath}`));
  });

  audio.load();
});

/** 主程序算好的桌寵初始位置。canvas* 是畫布應該有的尺寸，見 services/pet-placement.ts。 */
interface PetPlacement {
  x: number
  y: number
  canvasWidth?: number
  canvasHeight?: number
}

export const useLive2DModel = ({
  modelInfo,
  canvasRef,
}: UseLive2DModelProps) => {
  const { mode } = useMode();
  const isPet = mode === 'pet';
  const [isDragging, setIsDragging] = useState(false);
  const [position, setPosition] = useState<Position>({ x: 0, y: 0 });
  const dragStartPos = useRef<Position>({ x: 0, y: 0 }); // Screen coordinates at drag start
  const modelStartPos = useRef<Position>({ x: 0, y: 0 }); // Model coordinates at drag start
  const modelPositionRef = useRef<Position>({ x: 0, y: 0 });
  // 進桌寵模式之前角色在哪。桌寵定位會把位移寫進模型矩陣，而那個位移是照桌寵畫布
  // （整台螢幕）算出來的；視窗模式的畫布小很多，同一個位移換算過去會把角色推出
  // 畫面外——症狀是切回視窗模式之後角色整個不見，而且畫面本身不帶任何線索。
  const prePetPositionRef = useRef<Position | null>(null);
  const prevModelUrlRef = useRef<string | null>(null);
  const isHoveringModelRef = useRef(false);
  const dragMovedRef = useRef(false); // [DRAGDBG]
  const electronApi = (window as any).electron;

  // --- State for Tap vs Drag ---
  const mouseDownTimeRef = useRef<number>(0);
  const mouseDownPosRef = useRef<Position>({ x: 0, y: 0 }); // Screen coords at mousedown
  const isPotentialTapRef = useRef<boolean>(false); // Flag for ongoing potential tap/drag action
  // ---

  const getPointerPosition = useCallback((e: React.MouseEvent) => {
    if (isPet && window.api !== undefined) {
      // A captured pointer crossing from a 1x display to a 2x Retina display
      // can report clientX/clientY in the new backing scale and jump by an
      // entire screen. screenX/screenY and window.screenX/screenY share the
      // same global coordinate space, so their difference remains stable.
      return {
        x: e.screenX - window.screenX,
        y: e.screenY - window.screenY,
      };
    }
    return { x: e.clientX, y: e.clientY };
  }, [isPet]);

  useEffect(() => {
    const currentUrl = modelInfo?.url;
    const sdkScale = (window as any).LAppDefine?.CurrentKScale;
    const modelScale = modelInfo?.kScale !== undefined ? Number(modelInfo.kScale) : undefined;

    const needsUpdate = currentUrl &&
                        (currentUrl !== prevModelUrlRef.current ||
                         (sdkScale !== undefined && modelScale !== undefined && sdkScale !== modelScale));

    if (needsUpdate) {
      prevModelUrlRef.current = currentUrl;

      try {
        const { baseUrl, modelDir, modelFileName } = parseModelUrl(currentUrl);

        if (baseUrl && modelDir) {
          updateModelConfig(baseUrl, modelDir, modelFileName, Number(modelInfo.kScale));

          setTimeout(() => {
            if ((window as any).LAppLive2DManager?.releaseInstance) {
              (window as any).LAppLive2DManager.releaseInstance();
            }
            initializeLive2D();
          }, 500);
        }
      } catch (error) {
        console.error('Error processing model URL:', error);
      }
    }
  }, [modelInfo?.url, modelInfo?.kScale]);

  const getModelPosition = useCallback(() => {
    const adapter = (window as any).getLAppAdapter?.();
    if (adapter) {
      const model = adapter.getModel();
      if (model && model._modelMatrix) {
        const matrix = model._modelMatrix.getArray();
        return {
          x: matrix[12],
          y: matrix[13],
        };
      }
    }
    return { x: 0, y: 0 };
  }, []);

  const setModelPosition = useCallback((x: number, y: number) => {
    const adapter = (window as any).getLAppAdapter?.();
    if (adapter) {
      const model = adapter.getModel();
      if (model && model._modelMatrix) {
        const matrix = model._modelMatrix.getArray();

        const newMatrix = [...matrix];
        newMatrix[12] = x;
        newMatrix[13] = y;

        model._modelMatrix.setMatrix(newMatrix);
        modelPositionRef.current = { x, y };
      }
    }
  }, []);

  useEffect(() => {
    if (!isPet || !window.electron?.ipcRenderer) return undefined;

    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    // 主程序在等這一聲才把視窗顯示出來。等不到畫布也要說，不然視窗永遠隱形。
    const reportDone = () => {
      window.electron?.ipcRenderer.send('pet-placement-done');
    };

    const applyPlacement = (
      placement: PetPlacement,
      retriesLeft = 20,
    ) => {
      if (cancelled) return;
      const canvas = canvasRef.current;
      const adapter = (window as any).getLAppAdapter?.();
      const view = LAppDelegate.getInstance().getView();
      const model = adapter?.getModel();

      // 畫布必須已經鋪滿整個合併桌面才能換算座標——拿視窗模式的舊尺寸算，角色會被
      // 扔到畫面外。decidePlacement 負責這個判斷，理由寫在 services/pet-placement.ts。
      const ready = view && model
        ? decidePlacement(
          canvas ? { width: canvas.clientWidth, height: canvas.clientHeight } : null,
          { width: placement.canvasWidth ?? 0, height: placement.canvasHeight ?? 0 },
          retriesLeft,
        )
        : (retriesLeft > 0 ? 'retry' : 'give-up');

      if (ready === 'retry') {
        retryTimer = setTimeout(() => applyPlacement(placement, retriesLeft - 1), 25);
        return;
      }
      if (ready === 'give-up' || !canvas || !view || !model) {
        reportDone();
        return;
      }

      const scale = canvas.width / canvas.clientWidth;
      const targetX = view._deviceToScreen.transformX(placement.x * scale);
      const targetY = view._deviceToScreen.transformY(placement.y * scale);
      const centerX = view._deviceToScreen.transformX(canvas.width / 2);
      const centerY = view._deviceToScreen.transformY(canvas.height / 2);
      const matrix = model._modelMatrix?.getArray?.();
      if (!matrix) {
        reportDone();
        return;
      }

      // The model matrix already contains its base alignment and scale. The
      // model appears at the virtual-desktop center immediately after resize;
      // move it by the center-to-target delta instead of replacing the matrix
      // translation with an absolute screen coordinate.
      const x = matrix[12] + targetX - centerX;
      const y = matrix[13] + targetY - centerY;
      if (!prePetPositionRef.current) {
        prePetPositionRef.current = getModelPosition();
      }
      setModelPosition(x, y);
      modelStartPos.current = { x, y };
      setPosition({ x, y });
      reportDone();
    };

    const handlePlacement = (
      _event: unknown,
      placement: PetPlacement,
    ) => applyPlacement(placement);

    window.electron.ipcRenderer.on('pet-initial-placement', handlePlacement);
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      window.electron?.ipcRenderer.removeListener('pet-initial-placement', handlePlacement);
    };
  }, [isPet, canvasRef, setModelPosition, getModelPosition]);

  // 離開桌寵模式：把角色放回進去之前的位置。
  useEffect(() => {
    if (isPet) return;
    const saved = prePetPositionRef.current;
    if (!saved) return;
    prePetPositionRef.current = null;
    setModelPosition(saved.x, saved.y);
    modelStartPos.current = saved;
    setPosition(saved);
  }, [isPet, setModelPosition]);

  useEffect(() => {
    const timer = setTimeout(() => {
      const currentPos = getModelPosition();
      modelPositionRef.current = currentPos;
      setPosition(currentPos);
    }, 500);

    return () => clearTimeout(timer);
  }, [modelInfo?.url, getModelPosition]);

  const getCanvasScale = useCallback(() => {
    const canvas = document.getElementById('canvas') as HTMLCanvasElement;
    if (!canvas) return { width: 1, height: 1, scale: 1 };

    const { width } = canvas;
    const { height } = canvas;
    const scale = width / canvas.clientWidth;

    return { width, height, scale };
  }, []);

  const screenToModelPosition = useCallback((screenX: number, screenY: number) => {
    const { width, height, scale } = getCanvasScale();

    const x = ((screenX * scale) / width) * 2 - 1;
    const y = -((screenY * scale) / height) * 2 + 1;

    return { x, y };
  }, [getCanvasScale]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const adapter = (window as any).getLAppAdapter?.();
    if (!adapter || !canvasRef.current) return;

    const model = adapter.getModel();
    const view = LAppDelegate.getInstance().getView();
    if (!view || !model) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const pointer = getPointerPosition(e);
    const x = pointer.x - rect.left; // Screen X relative to canvas
    const y = pointer.y - rect.top; // Screen Y relative to canvas

    // --- Check if click is on model ---
    const scale = canvas.width / canvas.clientWidth;
    const scaledX = x * scale;
    const scaledY = y * scale;
    const modelX = view._deviceToScreen.transformX(scaledX);
    const modelY = view._deviceToScreen.transformY(scaledY);

    const hitAreaName = model.anyhitTest(modelX, modelY);
    const isHitOnModel = model.isHitOnModel(modelX, modelY);
    // --- End Check ---

    // [DRAGDBG] 暫時的診斷，查完拿掉。一次點擊一行。
    window.electron?.ipcRenderer.send('drag-debug', {
      isPet,
      pointer,
      canvas: { w: canvas.width, cw: canvas.clientWidth },
      model: { x: Number(modelX.toFixed(3)), y: Number(modelY.toFixed(3)) },
      matrix: model._modelMatrix
        ? [model._modelMatrix.getArray()[12], model._modelMatrix.getArray()[13]]
        : null,
      opacity: (model as any)._opacity,
      drawables: model.getModel?.()?.getDrawableCount?.() ?? null,
      hitAreaName,
      isHitOnModel,
    });

    if (hitAreaName !== null || isHitOnModel) {
      // Record potential tap/drag start
      mouseDownTimeRef.current = Date.now();
      dragMovedRef.current = false; // [DRAGDBG]
      mouseDownPosRef.current = pointer;
      isPotentialTapRef.current = true;
      setIsDragging(false); // Ensure dragging is false initially

      // Store initial model position IF drag starts later
      if (model._modelMatrix) {
        const matrix = model._modelMatrix.getArray();
        modelStartPos.current = { x: matrix[12], y: matrix[13] };
      }
    }
  }, [canvasRef, modelInfo, getPointerPosition, isPet]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const adapter = (window as any).getLAppAdapter?.();
    const view = LAppDelegate.getInstance().getView();
    const model = adapter?.getModel();

    // --- Start Drag Logic ---
    if (isPotentialTapRef.current && adapter && view && model && canvasRef.current) {
      const pointer = getPointerPosition(e);
      const timeElapsed = Date.now() - mouseDownTimeRef.current;
      const deltaX = pointer.x - mouseDownPosRef.current.x;
      const deltaY = pointer.y - mouseDownPosRef.current.y;
      const distanceMoved = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

      // Check if it's a drag (moved enough distance OR held long enough while moving slightly)
      if (distanceMoved > DRAG_DISTANCE_THRESHOLD_PX || (timeElapsed > TAP_DURATION_THRESHOLD_MS && distanceMoved > 1)) {
        isPotentialTapRef.current = false; // It's a drag, not a tap
        // [DRAGDBG] 暫時的診斷，查完拿掉。一次拖曳一行。
        window.electron?.ipcRenderer.send('drag-debug', {
          what: 'drag-start', isPet, distanceMoved, timeElapsed,
        });
        setIsDragging(true);

        // Set initial drag screen position using the position from mousedown
        const canvas = canvasRef.current;
        const rect = canvas.getBoundingClientRect();
        dragStartPos.current = {
          x: mouseDownPosRef.current.x - rect.left,
          y: mouseDownPosRef.current.y - rect.top,
        };
        // modelStartPos is already set in handleMouseDown
      }
    }
    // --- End Start Drag Logic ---

    // --- Continue Drag Logic ---
    if (isDragging && adapter && view && model && canvasRef.current) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      const pointer = getPointerPosition(e);
      const currentX = pointer.x - rect.left; // Current screen X relative to canvas
      const currentY = pointer.y - rect.top; // Current screen Y relative to canvas

      // Convert screen delta to model delta
      const scale = canvas.width / canvas.clientWidth;
      const startScaledX = dragStartPos.current.x * scale;
      const startScaledY = dragStartPos.current.y * scale;
      const startModelX = view._deviceToScreen.transformX(startScaledX);
      const startModelY = view._deviceToScreen.transformY(startScaledY);

      const currentScaledX = currentX * scale;
      const currentScaledY = currentY * scale;
      const currentModelX = view._deviceToScreen.transformX(currentScaledX);
      const currentModelY = view._deviceToScreen.transformY(currentScaledY);

      const dx = currentModelX - startModelX;
      const dy = currentModelY - startModelY;

      const newX = modelStartPos.current.x + dx;
      const newY = modelStartPos.current.y + dy;

      // Use the adapter's setModelPosition method if available, otherwise update matrix directly
      if (adapter.setModelPosition) {
        adapter.setModelPosition(newX, newY);
      } else if (model._modelMatrix) {
        const matrix = model._modelMatrix.getArray();
        const newMatrix = [...matrix];
        newMatrix[12] = newX;
        newMatrix[13] = newY;
        model._modelMatrix.setMatrix(newMatrix);
      }

      modelPositionRef.current = { x: newX, y: newY };
      // [DRAGDBG] 只印第一格，避免每次 mousemove 都刷
      if (!dragMovedRef.current) {
        dragMovedRef.current = true;
        window.electron?.ipcRenderer.send('drag-debug', {
          what: 'drag-move', dx, dy, newX, newY,
        });
      }
      setPosition({ x: newX, y: newY }); // Update React state if needed for UI feedback
    }
    // --- End Continue Drag Logic ---

    // --- Pet Hover Logic (Unchanged) ---
    if (isPet && !isDragging && !isPotentialTapRef.current && electronApi && adapter && view && model && canvasRef.current) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const scale = canvas.width / canvas.clientWidth;
      const scaledX = x * scale;
      const scaledY = y * scale;
      const modelX = view._deviceToScreen.transformX(scaledX);
      const modelY = view._deviceToScreen.transformY(scaledY);

      const currentHitState = model.anyhitTest(modelX, modelY) !== null || model.isHitOnModel(modelX, modelY);

      if (currentHitState !== isHoveringModelRef.current) {
        isHoveringModelRef.current = currentHitState;
        electronApi.ipcRenderer.send('update-component-hover', 'live2d-model', currentHitState);
      }
    }
    // --- End Pet Hover Logic ---
  }, [isPet, isDragging, electronApi, canvasRef, getPointerPosition]);

  const handleMouseUp = useCallback((e: React.MouseEvent) => {
    const adapter = (window as any).getLAppAdapter?.();
    const model = adapter?.getModel();
    const view = LAppDelegate.getInstance().getView();

    if (isDragging) {
      // Finalize drag
      setIsDragging(false);
      if (adapter) {
        const currentModel = adapter.getModel(); // Re-get model in case adapter changed
        if (currentModel && currentModel._modelMatrix) {
          const matrix = currentModel._modelMatrix.getArray();
          const finalPos = { x: matrix[12], y: matrix[13] };
          modelPositionRef.current = finalPos;
          modelStartPos.current = finalPos; // Update base position for next potential drag
          setPosition(finalPos);
        }
      }
    } else if (isPotentialTapRef.current && adapter && model && view && canvasRef.current) {
      // --- Tap Motion Logic ---
      const pointer = getPointerPosition(e);
      const timeElapsed = Date.now() - mouseDownTimeRef.current;
      const deltaX = pointer.x - mouseDownPosRef.current.x;
      const deltaY = pointer.y - mouseDownPosRef.current.y;
      const distanceMoved = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

      // Check if it qualifies as a tap (short duration, minimal movement)
      if (timeElapsed < TAP_DURATION_THRESHOLD_MS && distanceMoved < DRAG_DISTANCE_THRESHOLD_PX) {
        const allowTapMotion = modelInfo?.pointerInteractive !== false;

        if (allowTapMotion && modelInfo?.tapMotions) {
          // Use mouse down position for hit testing
          const canvas = canvasRef.current;
          const rect = canvas.getBoundingClientRect();
          const scale = canvas.width / canvas.clientWidth;
          const downX = (mouseDownPosRef.current.x - rect.left) * scale;
          const downY = (mouseDownPosRef.current.y - rect.top) * scale;
          const modelX = view._deviceToScreen.transformX(downX);
          const modelY = view._deviceToScreen.transformY(downY);

          const hitAreaName = model.anyhitTest(modelX, modelY);
          // Trigger tap motion using the specific hit area name or null for general body tap
          model.startTapMotion(hitAreaName, modelInfo.tapMotions);
        }
      }
      // --- End Tap Motion Logic ---
    }

    // Reset potential tap flag regardless of outcome
    isPotentialTapRef.current = false;
  }, [isDragging, canvasRef, modelInfo, getPointerPosition]);

  const handleMouseLeave = useCallback(() => {
    if (isDragging) {
      // If dragging and mouse leaves, treat it like a mouse up to end drag
      handleMouseUp({} as React.MouseEvent); // Pass a dummy event or adjust handleMouseUp signature
    }
    // Reset potential tap if mouse leaves before mouse up
    if (isPotentialTapRef.current) {
      isPotentialTapRef.current = false;
    }
    // --- Pet Hover Logic (Unchanged) ---
    if (isPet && electronApi && isHoveringModelRef.current) {
      isHoveringModelRef.current = false;
      electronApi.ipcRenderer.send('update-component-hover', 'live2d-model', false);
    }
  }, [isPet, isDragging, electronApi, handleMouseUp]);

  useEffect(() => {
    if (!isPet && electronApi && isHoveringModelRef.current) {
      isHoveringModelRef.current = false;
    }
  }, [isPet, electronApi]);

  // Expose motion debugging functions to window for console testing
  useEffect(() => {
    const playMotion = (motionGroup: string, motionIndex: number = 0, priority: number = 3) => {
      const adapter = (window as any).getLAppAdapter?.();
      if (!adapter) {
        console.error('Live2D adapter not available');
        return false;
      }

      const model = adapter.getModel();
      if (!model) {
        console.error('Live2D model not available');
        return false;
      }

      try {
        console.log(`Playing motion: group="${motionGroup}", index=${motionIndex}, priority=${priority}`);
        const result = model.startMotion(motionGroup, motionIndex, priority);
        console.log('Motion start result:', result);
        return result;
      } catch (error) {
        console.error('Error playing motion:', error);
        return false;
      }
    };

    const playRandomMotion = (motionGroup: string, priority: number = 3) => {
      const adapter = (window as any).getLAppAdapter?.();
      if (!adapter) {
        console.error('Live2D adapter not available');
        return false;
      }

      const model = adapter.getModel();
      if (!model) {
        console.error('Live2D model not available');
        return false;
      }

      try {
        console.log(`Playing random motion from group: "${motionGroup}", priority=${priority}`);
        const result = model.startRandomMotion(motionGroup, priority);
        console.log('Random motion start result:', result);
        return result;
      } catch (error) {
        console.error('Error playing random motion:', error);
        return false;
      }
    };

    const getMotionInfo = () => {
      const adapter = (window as any).getLAppAdapter?.();
      if (!adapter) {
        console.error('Live2D adapter not available');
        return null;
      }

      const model = adapter.getModel();
      if (!model) {
        console.error('Live2D model not available');
        return null;
      }

      try {
        const motionGroups = [];
        const setting = model._modelSetting;
        if (setting) {
          // Get all motion groups
          const groups = setting._json?.FileReferences?.Motions;
          if (groups) {
            for (const groupName in groups) {
              const motions = groups[groupName];
              motionGroups.push({
                name: groupName,
                count: motions.length,
                motions: motions.map((motion: any, index: number) => ({
                  index,
                  file: motion.File
                }))
              });
            }
          }
        }
        
        console.log('Available motion groups:', motionGroups);
        return motionGroups;
      } catch (error) {
        console.error('Error getting motion info:', error);
        return null;
      }
    };

    // Expose to window for console access
    (window as any).Live2DDebug = {
      playMotion,
      playRandomMotion,
      getMotionInfo,
      // Helper functions
      help: () => {
        console.log(`
Live2D Motion Debug Functions:
- Live2DDebug.getMotionInfo() - Get all available motion groups and their motions
- Live2DDebug.playMotion(group, index, priority) - Play specific motion
- Live2DDebug.playRandomMotion(group, priority) - Play random motion from group  
- Live2DDebug.help() - Show this help

Example usage:
Live2DDebug.getMotionInfo()  // See available motions
Live2DDebug.playMotion("", 0)  // Play first motion from default group
Live2DDebug.playRandomMotion("")  // Play random motion from default group
        `);
      }
    };

    console.log('Live2D Debug functions exposed to window.Live2DDebug');
    console.log('Type Live2DDebug.help() for usage information');

    // Cleanup function
    return () => {
      delete (window as any).Live2DDebug;
    };
  }, []);

  // Pointer 事件而不是 Mouse 事件：pointer 同時涵蓋滑鼠、觸控與觸控筆，這是
  // 手機上能拖動角色的前提。桌面瀏覽器會把觸控「合成」成滑鼠事件，所以舊寫法
  // 在某些情況下看起來也能動，但多點觸控與觸控筆完全不會進來。
  //
  // React 的 PointerEvent 繼承 MouseEvent，clientX/clientY 都在，所以底下的
  // 處理函式不用改簽章。
  //
  // setPointerCapture：手指／游標拖出元件外時事件仍然送到這裡，不然快速拖曳
  // 會在半路斷掉、角色卡在中途。捕捉之後 onPointerLeave 就不會在拖曳中觸發，
  // 但 onPointerCancel（來電、系統手勢介入）還是要收，否則會卡在拖曳狀態。
  // 目前壓著的指標數。第二根手指落下代表使用者要縮放不是要移動，這時候要停掉
  // 拖曳——不然兩指張開的過程中角色會跟著跑掉。
  const activePointerCount = useRef(0);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    activePointerCount.current += 1;
    if (activePointerCount.current > 1) {
      // 進入縮放手勢：結束拖曳，並且不要捕捉這一根，否則 pinch 那邊收不到它。
      handleMouseUp(e);
      return;
    }
    try {
      (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    } catch {
      // 某些瀏覽器在多指情況下會拒絕捕捉，忽略即可，拖曳仍然可用。
    }
    handleMouseDown(e);
  }, [handleMouseDown, handleMouseUp]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    activePointerCount.current = Math.max(0, activePointerCount.current - 1);
    try {
      (e.currentTarget as Element).releasePointerCapture?.(e.pointerId);
    } catch {
      // 沒捕捉到就沒有東西要放開。
    }

    // SDK 自己在 canvas 上綁了 mousedown/mousemove/mouseup，用 _captured 決定要
    // 不要讓頭部與視線跟著游標（lappdelegate.ts 的 onMouseMoved 開頭就檢查它）。
    // 我們在外層 container 呼叫 setPointerCapture 之後，連帶的相容滑鼠事件也會
    // 改送到 container，canvas 因此收不到 mouseup——_captured 永遠停在 true，
    // 之後只要移動游標角色的頭就一直跟著轉，即使沒有按著任何鍵。
    //
    // 沒有公開 API 可以通知它，但那個欄位本來就是公開宣告的。指標已經放開了，
    // 把它歸位是事實陳述，不是繞過什麼。
    try {
      const delegate = LAppDelegate.getInstance() as unknown as { _captured?: boolean };
      if (delegate) delegate._captured = false;
    } catch {
      // SDK 還沒初始化就沒有東西要清。
    }

    handleMouseUp(e);
  }, [handleMouseUp]);

  const handlePointerMoveDrag = useCallback((e: React.PointerEvent) => {
    // 兩指以上一律交給縮放，不要同時移動角色。
    if (activePointerCount.current > 1) return;
    handleMouseMove(e);
  }, [handleMouseMove]);

  return {
    position,
    isDragging,
    handlers: {
      onPointerDown: handlePointerDown,
      onPointerMove: handlePointerMoveDrag,
      onPointerUp: handlePointerUp,
      onPointerCancel: handlePointerUp,
      onPointerLeave: handleMouseLeave,
    },
  };
};
