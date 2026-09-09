// @ts-nocheck
/* eslint-disable no-underscore-dangle */
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */

import { LAppDelegate } from "./lappdelegate";
import * as LAppDefine from "./lappdefine";
import { LAppGlManager } from "./lappglmanager";
import { LAppLive2DManager } from "./lapplive2dmanager";

/**
 * Initialize the Live2D application
 */
export function initializeLive2D(): void {
  console.log(
    "Initializing Live2D with resourcePath:",
    LAppDefine.ResourcesPath
  );
  console.log("Model directories:", LAppDefine.ModelDir);

  // Clean up any existing instances first
  if (LAppDelegate.getInstance()) {
    // Release existing model resources
    LAppLive2DManager.releaseInstance();
  }

  // 先釋放再取得，不是多此一舉。LAppGlManager 的 constructor 只在「建構的那一刻」
  // 抓一次 document.getElementById('canvas')，之後永遠用手上那個 element；
  // 這個 branch 以前不會出事，是因為 <Live2D/> 一旦掛上去就不會卸載，canvas 永遠是同一個。
  // 雙 renderer 之後 Live2D → VRM → Live2D 會把舊的 <canvas id="canvas"> 整個從 DOM 移掉、
  // 再掛一個新的；不重建這個 singleton 的話，SDK 會繼續畫進那張已經離開 DOM 的舊畫布，
  // 畫面就永遠空白。同一張 canvas 重複呼叫 getContext('webgl2') 會拿回同一個 context，
  // 所以 Live2D → Live2D 換角色走同一條路徑時，gl 不變、行為也不變。
  LAppGlManager.releaseInstance();

  if (
    !LAppGlManager.getInstance() ||
    !LAppDelegate.getInstance().initialize()
  ) {
    console.error("Failed to initialize Live2D");
    return;
  }

  LAppDelegate.getInstance().run();

  (window as any).getLive2DManager = () => LAppLive2DManager.getInstance();
  window.dispatchEvent(new CustomEvent("tomoshibi:live2d-ready"));

  // Make sure LAppAdapter is available globally
  if (!(window as any).getLAppAdapter) {
    console.log('Setting up getLAppAdapter function');
    const { LAppAdapter } = require('./lappadapter');
    (window as any).getLAppAdapter = () => LAppAdapter.getInstance();
  }

  if ((window as any).api?.setIgnoreMouseEvent) {
    const parent = document.getElementById("live2d");

    parent?.addEventListener("pointermove", (e) => {
      const model = LAppLive2DManager.getInstance().getModel(0);
      const view = LAppDelegate.getInstance().getView();

      // Transform screen coordinates to Live2D canvas coordinates
      const x = view?._deviceToScreen.transformX(e.x);
      const y = view?._deviceToScreen.transformY(e.y);

      // Check if mouse is over the Live2D model
      (window as any).api.setIgnoreMouseEvent(!model?.anyhitTest(x, y) && !model?.isHitOnModel(x, y));
    });

    // Add pointerdown event listener
    parent?.addEventListener("pointerdown", (e) => {
      const model = LAppLive2DManager.getInstance().getModel(0);
      const view = LAppDelegate.getInstance().getView();

      // Transform screen coordinates to Live2D canvas coordinates
      const x = view?._deviceToScreen.transformX(e.x);
      const y = view?._deviceToScreen.transformY(e.y);

      // Test hit and log result
      const hitAreaName = model?.anyhitTest(x, y);
      const isHit = hitAreaName !== null || model?.isHitOnModel(x, y);
      console.log("Model clicked:", isHit, hitAreaName ? `in area: ${hitAreaName}` : '');
    });
  }
}

/**
 * Keep the original window.load handler for backwards compatibility
 * (for the standalone HTML file)
 */
/* // Comment out the window.load listener
window.addEventListener(
  "load",
  (): void => {
    initializeLive2D();
  },
  { passive: true }
);
*/

/**
 * 終了時の処理
 * 结束时的处理
 */
window.addEventListener(
  "beforeunload",
  (): void => LAppDelegate.releaseInstance(),
  { passive: true }
);

/**
 * Process when changing screen size.
 */
window.addEventListener(
  "resize",
  () => {
    if (LAppDefine.CanvasSize === "auto") {
      LAppDelegate.getInstance().onResize();
    }
  },
  { passive: true }
);

// Make the initialization function available globally
(window as any).initializeLive2D = initializeLive2D;
