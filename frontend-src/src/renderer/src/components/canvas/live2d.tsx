/* eslint-disable no-shadow */
/* eslint-disable no-underscore-dangle */
/* eslint-disable @typescript-eslint/ban-ts-comment */
import { memo, useRef, useEffect } from "react";
import { useLive2DConfig } from "@/context/live2d-config-context";
import { useLive2DModel } from "@/hooks/canvas/use-live2d-model";
import { useLive2DResize } from "@/hooks/canvas/use-live2d-resize";
import { useForceIgnoreMouse } from "@/hooks/utils/use-force-ignore-mouse";
import { useMode } from "@/context/mode-context";
// 視線跟隨的開關是 LAppModel 上的 static 旗標，見下方 useEffect 的說明。
import { LAppModel } from "@cubismsdksamples/lappmodel";
import { LAppDelegate } from "@cubismsdksamples/lappdelegate";
import { registerRenderer } from "@/avatar/character-renderer";
import { createLive2DRenderer } from "@/avatar/live2d/live2d-renderer";

interface Live2DProps {
  showSidebar?: boolean;
}

export const Live2D = memo(
  ({ showSidebar }: Live2DProps): JSX.Element => {
    const { forceIgnoreMouse } = useForceIgnoreMouse();
    const { modelInfo } = useLive2DConfig();
    const { mode } = useMode();
    const internalContainerRef = useRef<HTMLDivElement>(null);

    // 把「視線跟隨」設定同步到 SDK。那段邏輯在 lappmodel 的 update() 裡，每一幀
    // 把游標位置加到頭部／身體／眼球的參數上，原本沒有任何開關可以關掉；
    // LAppModel 上加了一個 static 旗標，這裡負責讓它跟著設定走。用 static 是
    // 因為這是整個 app 的偏好，不是某個模型的屬性——換模型時設定要留著。
    useEffect(() => {
      LAppModel.lookAtPointer = modelInfo?.lookAtPointer !== false;
    }, [modelInfo?.lookAtPointer]);
    const isPet = mode === 'pet';

    // Get canvasRef from useLive2DResize
    const { canvasRef } = useLive2DResize({
      containerRef: internalContainerRef,
      modelInfo,
      showSidebar,
    });

    // Pass canvasRef to useLive2DModel
    const { isDragging, handlers } = useLive2DModel({
      modelInfo,
      canvasRef,
    });

    // 掛上去就是當前 renderer；卸載就註銷。註銷只在自己仍是當前時才清，
    // 所以 Live2D → VRM 切換時舊的晚一步卸載也不會清掉新的。
    useEffect(() => registerRenderer(createLive2DRenderer()), []);

    // 卸載時把整組 SDK 收掉。Cubism 的 singleton 在 constructor 就把
    // <canvas id="canvas"> 抓進去、之後再也不重讀，所以那張 canvas 一旦隨著這個
    // 元件被 React 移除，SDK 手上就只剩一個離開 DOM 的死畫布。這個分支以前不需要
    // 清理，是因為 <Live2D/> 掛上去就不會卸載；現在 Live2D → VRM 會把它整個換掉。
    // 不收的話 rAF 迴圈會繼續跑、WebGL context 也一直占著。
    // LAppDelegate.releaseInstance() 內部會連帶叫 LAppLive2DManager.releaseInstance()。
    useEffect(
      () => () => {
        try {
          LAppDelegate.releaseInstance();
        } catch (e) {
          // SDK 還沒初始化完就卸載（例如載入中途切走）時會走到這裡，忽略即可。
          console.warn("[Live2D] LAppDelegate.releaseInstance() failed:", e);
        }
      },
      [],
    );

    // Expose setExpression for console testing
    // useEffect(() => {
    //   const testSetExpression = (expressionValue: string | number) => {
    //     const lappAdapter = (window as any).getLAppAdapter?.();
    //     if (lappAdapter) {
    //       setExpression(expressionValue, lappAdapter, `[Console Test] Set expression to: ${expressionValue}`);
    //     } else {
    //       console.error('[Console Test] LAppAdapter not found.');
    //     }
    //   };

    //   // Expose the function to the window object
    //   (window as any).testSetExpression = testSetExpression;
    //   console.log('[Debug] testSetExpression function exposed to window.');

    //   // Cleanup function to remove the function from window when the component unmounts
    //   return () => {
    //     delete (window as any).testSetExpression;
    //     console.log('[Debug] testSetExpression function removed from window.');
    //   };
    // }, [setExpression]);


    const handleContextMenu = (e: React.MouseEvent) => {
      if (!isPet) {
        return;
      }

      e.preventDefault();
      console.log(
        "[ContextMenu] (Pet Mode) Right-click detected, requesting menu...",
      );
      window.api?.showContextMenu?.();
    };

    return (
      <div
        ref={internalContainerRef} // Ref for useLive2DResize if it observes this element
        id="live2d-internal-wrapper"
        style={{
          width: "100%",
          height: "100%",
          pointerEvents: isPet && forceIgnoreMouse ? "none" : "auto",
          // 沒有這行的話瀏覽器會先把拖曳解讀成捲動、雙指解讀成整頁縮放，
          // 手勢根本傳不到這裡——手機上的拖曳與雙指縮放都靠它。
          touchAction: "none",
          overflow: "hidden",
          position: "relative",
          cursor: isDragging ? "grabbing" : "default",
        }}
        onContextMenu={handleContextMenu}
        {...handlers}
      >
        <canvas
          id="canvas"
          ref={canvasRef}
          style={{
            width: "100%",
            height: "100%",
            pointerEvents: isPet && forceIgnoreMouse ? "none" : "auto",
            display: "block",
            cursor: isDragging ? "grabbing" : "default",
          }}
        />
      </div>
    );
  },
);

Live2D.displayName = "Live2D";
