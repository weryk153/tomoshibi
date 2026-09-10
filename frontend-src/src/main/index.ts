/* eslint-disable no-shadow */
import { app, ipcMain, globalShortcut, desktopCapturer } from "electron";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { electronApp, optimizer } from "@electron-toolkit/utils";
import { WindowManager } from "./window-manager";
import { MenuManager } from "./menu-manager";
import { BackendManager } from "./backend-manager";
import { StartupWindow, pickLang } from "./startup-window";

let windowManager: WindowManager;
let menuManager: MenuManager;
const backendManager = new BackendManager();
let isQuitting = false;

interface BackgroundPreferences {
  backgroundUrl: string;
}

const backgroundPreferencesPath = (): string => join(
  app.getPath('userData'),
  'background-preferences.json',
);

async function readBackgroundPreferences(): Promise<BackgroundPreferences | null> {
  try {
    const parsed = JSON.parse(await readFile(backgroundPreferencesPath(), 'utf8'));
    if (typeof parsed?.backgroundUrl !== 'string' || !parsed.backgroundUrl.trim()) {
      return null;
    }
    return { backgroundUrl: parsed.backgroundUrl };
  } catch {
    return null;
  }
}

async function writeBackgroundPreferences(
  preferences: BackgroundPreferences,
): Promise<void> {
  if (typeof preferences?.backgroundUrl !== 'string' || !preferences.backgroundUrl.trim()) {
    return;
  }
  await writeFile(
    backgroundPreferencesPath(),
    `${JSON.stringify({ backgroundUrl: preferences.backgroundUrl }, null, 2)}\n`,
    'utf8',
  );
}

function setupIPC(): void {
  ipcMain.handle("get-platform", () => process.platform);

  ipcMain.on("set-ignore-mouse-events", (_event, ignore: boolean) => {
    const window = windowManager.getWindow();
    if (window) {
      windowManager.setIgnoreMouseEvents(ignore);
    }
  });

  ipcMain.on("get-current-mode", (event) => {
    event.returnValue = windowManager.getCurrentMode();
  });

  ipcMain.on("pre-mode-changed", (_event, newMode) => {
    if (newMode === 'window' || newMode === 'pet') {
      menuManager.setMode(newMode);
    }
  });

  ipcMain.on("window-minimize", () => {
    windowManager.getWindow()?.minimize();
  });

  ipcMain.on("window-maximize", () => {
    const window = windowManager.getWindow();
    if (window) {
      windowManager.maximizeWindow();
    }
  });

  ipcMain.on("window-close", () => {
    const window = windowManager.getWindow();
    if (window) {
      if (process.platform === "darwin") {
        window.hide();
      } else {
        window.close();
      }
    }
  });

  ipcMain.on(
    "update-component-hover",
    (_event, componentId: string, isHovering: boolean) => {
      windowManager.updateComponentHover(componentId, isHovering);
    },
  );

  ipcMain.handle("get-config-files", () => {
    const configFiles = JSON.parse(localStorage.getItem("configFiles") || "[]");
    menuManager.updateConfigFiles(configFiles);
    return configFiles;
  });

  ipcMain.on("update-config-files", (_event, files) => {
    menuManager.updateConfigFiles(files);
  });

  ipcMain.handle('get-screen-capture', async () => {
    const sources = await desktopCapturer.getSources({ types: ['screen'] });
    return sources[0].id;
  });

  ipcMain.handle('background-preferences:get', readBackgroundPreferences);
  ipcMain.handle(
    'background-preferences:set',
    (_event, preferences: BackgroundPreferences) => writeBackgroundPreferences(preferences),
  );
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId("com.tomoshibi.app");

  // 後端就緒前先顯示啟動畫面，主視窗等後端好了才建。啟動畫面要撐到主視窗出現
  // 才關：中間要是一個視窗都沒有，Windows 上 window-all-closed 會直接結束 app。
  const startup = new StartupWindow(pickLang(app.getLocale()));
  const backend = await backendManager.start((progress) => startup.update(progress));
  if (isQuitting) return; // 等待期間使用者按了結束
  if (backend.kind === 'failed' && !(await startup.askAfterFailure(backend))) {
    startup.close();
    app.quit();
    return;
  }

  windowManager = new WindowManager();
  menuManager = new MenuManager((mode) => windowManager.setWindowMode(mode));

  const window = windowManager.createWindow({
    titleBarOverlay: {
      color: "#111111",
      symbolColor: "#FFFFFF",
      height: 30,
    },
  });
  menuManager.createTray();

  // 主視窗是等 renderer 回報才顯示的（見 window-manager 的 revealWindow），
  // 保險起見也設個上限，免得啟動畫面蓋在那裡不走。
  window.once("show", () => startup.close());
  setTimeout(() => startup.close(), 15000);

  window.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      window.hide();
    }
    return false;
  });

  // if (process.env.NODE_ENV === "development") {
  //   globalShortcut.register("F12", () => {
  //     const window = windowManager.getWindow();
  //     if (!window) return;

  //     if (window.webContents.isDevToolsOpened()) {
  //       window.webContents.closeDevTools();
  //     } else {
  //       window.webContents.openDevTools();
  //     }
  //   });
  // }

  setupIPC();

  app.on("activate", () => {
    const window = windowManager?.getWindow();
    if (window) {
      window.show();
    }
  });

  app.on("browser-window-created", (_, window) => {
    optimizer.watchWindowShortcuts(window);
  });

  app.on('web-contents-created', (_, contents) => {
    contents.session.setPermissionRequestHandler((webContents, permission, callback) => {
      if (permission === 'media') {
        callback(true);
      } else {
        callback(false);
      }
    });
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", (event) => {
  isQuitting = true;
  // 先等後端結束再真的退出，不然 Python 會變成孤兒行程繼續佔著 port。
  // stop() 完成後再呼叫一次 quit，那時 isRunning() 已是 false，會走到下面。
  if (backendManager.isRunning()) {
    event.preventDefault();
    void backendManager.stop().then(() => app.quit());
    return;
  }
  menuManager?.destroy();
  globalShortcut.unregisterAll();
});
