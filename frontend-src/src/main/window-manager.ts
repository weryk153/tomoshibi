import {
  BrowserWindow, screen, shell, ipcMain,
} from 'electron';
import { join } from 'path';
import { is } from '@electron-toolkit/utils';
import {
  spanAllDisplays, wasClamped, displayForRect, placementWithin,
} from './pet-bounds';

const isMac = process.platform === 'darwin';

export class WindowManager {
  private window: BrowserWindow | null = null;

  private windowedBounds: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null = null;

  private hoveringComponents: Set<string> = new Set();

  private currentMode: 'window' | 'pet' = 'window';

  private petInitialPlacement: {
    x: number;
    y: number;
    canvasWidth: number;
    canvasHeight: number;
  } | null = null;

  // 顯示視窗的保險絲。桌寵模式下我們等 renderer 回報定位完成才把視窗顯示出來，
  // 但定位有可能等不到畫布（螢幕拔掉、畫布掛掉），那時候不能讓視窗永遠隱形。
  private petRevealTimer: ReturnType<typeof setTimeout> | null = null;

  // Track if mouse events are forcibly ignored
  private forceIgnoreMouse = false;

  constructor() {
    ipcMain.on('renderer-ready-for-mode-change', (_event, newMode) => {
      if (newMode === 'pet') {
        setTimeout(() => {
          this.continueSetWindowModePet();
        }, 500);
      } else {
        setTimeout(() => {
          this.continueSetWindowModeWindow();
        }, 500);
      }
    });

    ipcMain.on('mode-change-rendered', () => {
      if (this.currentMode !== 'pet' || !this.petInitialPlacement) {
        this.revealWindow();
        return;
      }

      // 桌寵模式先不顯示。視窗這時已經鋪滿整個合併桌面，而角色還停在畫布正中央
      // ——兩台螢幕上下排的話那個中央根本不在任何一台的中間。先顯示再定位，使用者
      // 就會看到角色在錯的螢幕上閃一下才跳回來。
      this.window?.webContents.send('pet-initial-placement', {
        ...this.petInitialPlacement,
      });

      // 保險絲：renderer 等不到畫布也會回報 pet-placement-done，但萬一連那個都沒
      // 來（例如 renderer 當掉），視窗不能就這樣隱形下去。
      this.clearPetRevealTimer();
      this.petRevealTimer = setTimeout(() => {
        console.log('[pet] reveal by fallback timer (renderer never reported)');
        this.revealWindow();
      }, 1000);
    });

    // [DRAGDBG] 暫時的診斷，查完拿掉
    ipcMain.on('drag-debug', (_event, payload) => {
      console.log('[DRAGDBG]', JSON.stringify(payload));
    });

    ipcMain.on('pet-placement-done', (_event, report) => {
      console.log('[pet] renderer reported', JSON.stringify(report ?? {}));
      this.revealWindow();
    });

    ipcMain.on('window-unfullscreen', () => {
      const window = this.getWindow();
      if (window && window.isFullScreen()) {
        window.setFullScreen(false);
      }
    });

    // Handle toggle force ignore mouse events from renderer
    ipcMain.on('toggle-force-ignore-mouse', () => {
      this.toggleForceIgnoreMouse();
    });
  }

  createWindow(options: Electron.BrowserWindowConstructorOptions): BrowserWindow {
    this.window = new BrowserWindow({
      width: 900,
      height: 670,
      show: false,
      transparent: true,
      backgroundColor: '#ffffff',
      autoHideMenuBar: true,
      frame: false,
      icon: process.platform === 'win32'
        ? join(__dirname, '../../resources/icon.ico')
        : join(__dirname, '../../resources/icon.png'),
      ...(isMac ? { titleBarStyle: 'hiddenInset' } : {}),
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        sandbox: false,
        contextIsolation: true,
        nodeIntegration: true,
      },
      hasShadow: false,
      paintWhenInitiallyHidden: true,
      ...options,
    });

    this.setupWindowEvents();
    this.loadContent();

    this.window.on('enter-full-screen', () => {
      this.window?.webContents.send('window-fullscreen-change', true);
    });

    this.window.on('leave-full-screen', () => {
      this.window?.webContents.send('window-fullscreen-change', false);
    });

    return this.window;
  }

  private setupWindowEvents(): void {
    if (!this.window) return;

    this.window.on('ready-to-show', () => {
      this.window?.show();
      this.window?.webContents.send(
        'window-maximized-change',
        this.window.isMaximized(),
      );
    });

    this.window.on('maximize', () => {
      this.window?.webContents.send('window-maximized-change', true);
    });

    this.window.on('unmaximize', () => {
      this.window?.webContents.send('window-maximized-change', false);
    });

    this.window.on('resize', () => {
      const window = this.getWindow();
      if (window) {
        const bounds = window.getBounds();
        const { width, height } = screen.getPrimaryDisplay().workArea;
        const isMaximized = bounds.width >= width && bounds.height >= height;
        window.webContents.send('window-maximized-change', isMaximized);
      }
    });

    this.window.webContents.setWindowOpenHandler((details) => {
      shell.openExternal(details.url);
      return { action: 'deny' };
    });
  }

  private loadContent(): void {
    if (!this.window) return;

    if (is.dev && process.env.ELECTRON_RENDERER_URL) {
      this.window.loadURL(process.env.ELECTRON_RENDERER_URL);
    } else {
      this.window.loadFile(join(__dirname, '../renderer/index.html'));
    }
  }

  /**
   * 設定滑鼠事件穿透。永遠帶 { forward: true }。
   *
   * 原本 macOS 走的是不帶 forward 的分支，結果是個死結：桌寵模式一開始就設成穿透，
   * renderer 因此收不到任何滑鼠事件，hover 偵測不會跑，update-component-hover 不會
   * 送，穿透就永遠關不掉——唯一能解除穿透的訊號正好被穿透本身擋住。托盤的
   * Toggle Mouse Passthrough 也救不了：關掉 force 之後它重算 shouldIgnore，
   * hoveringComponents 是空的，結果還是穿透。症狀就是桌寵模式下角色完全拖不動。
   *
   * forward 在舊版 Electron 只支援 Windows，那個分支是那時候留下來的；現在的版本
   * macOS 也支援，行為就是「照樣穿透，但把 mousemove 轉給 renderer」——正是 hover
   * 偵測需要的東西。
   */
  private applyIgnoreMouse(ignore: boolean): void {
    this.window?.setIgnoreMouseEvents(ignore, { forward: true });
  }

  private clearPetRevealTimer(): void {
    if (this.petRevealTimer) {
      clearTimeout(this.petRevealTimer);
      this.petRevealTimer = null;
    }
  }

  private revealWindow(): void {
    this.clearPetRevealTimer();
    this.window?.setOpacity(1);
  }

  setWindowMode(mode: 'window' | 'pet'): void {
    if (!this.window) return;

    this.currentMode = mode;
    this.window.setOpacity(0);

    if (mode === 'window') {
      this.setWindowModeWindow();
    } else {
      this.setWindowModePet();
    }
  }

  private setWindowModeWindow(): void {
    if (!this.window) return;

    this.window.setAlwaysOnTop(false);
    this.window.setIgnoreMouseEvents(false);
    this.window.setSkipTaskbar(false);
    this.window.setResizable(true);
    this.window.setFocusable(true);
    this.window.setAlwaysOnTop(false);

    this.window.setBackgroundColor('#ffffff');
    this.window.webContents.send('pre-mode-changed', 'window');
  }

  private continueSetWindowModeWindow(): void {
    if (!this.window) return;
    if (this.windowedBounds) {
      this.window.setBounds(this.windowedBounds);
    } else {
      this.window.setSize(900, 670);
      this.window.center();
    }

    if (isMac) {
      this.window.setWindowButtonVisibility(true);
      this.window.setVisibleOnAllWorkspaces(false, {
        visibleOnFullScreen: false,
      });
    }

    this.window?.setIgnoreMouseEvents(false, { forward: true });

    this.window.webContents.send('mode-changed', 'window');
  }

  private setWindowModePet(): void {
    if (!this.window) return;

    this.windowedBounds = this.window.getBounds();

    if (this.window.isFullScreen()) {
      this.window.setFullScreen(false);
    }

    this.window.setBackgroundColor('#00000000');

    this.window.setAlwaysOnTop(true, 'screen-saver');
    this.window.setPosition(0, 0);

    this.window.webContents.send('pre-mode-changed', 'pet');
  }

  private continueSetWindowModePet(): void {
    if (!this.window) return;

    const displays = screen.getAllDisplays();
    const sourceBounds = this.windowedBounds ?? this.window.getBounds();

    // 先照上游的做法試著鋪滿所有螢幕，這樣角色可以被拖到任何一台。
    const span = spanAllDisplays(displays);
    this.window.setBounds(span);

    // 讀回來看系統給了什麼。macOS 在「顯示器各自使用單獨的 Space」（預設開著）下
    // 不讓視窗跨螢幕，會把它夾到其中一台——夾到哪一台是系統看重疊面積決定的，不是
    // 我們能選的。實機量到：要 2062 高、只給 1055，整個視窗跑到上方的外接螢幕，
    // 下方連畫布都沒有，角色拖過去就消失。
    let bounds = this.window.getContentBounds();
    const clamped = wasClamped(span, bounds);
    if (clamped) {
      // 不接受系統的選擇：明確放到角色切換前所在的那一台。
      const target = displayForRect(displays, sourceBounds);
      this.window.setBounds(target.workArea);
      bounds = this.window.getContentBounds();
    }

    // 常駐的診斷。這條路上任何一步錯掉，症狀都是「角色看不到」，而看不到的畫面
    // 本身完全不帶資訊——沒有這幾行就只能重寫一次診斷再請使用者重現一次。
    console.log('[pet] span', JSON.stringify(span), 'clamped', clamped);
    console.log('[pet] bounds', JSON.stringify(bounds), 'source', JSON.stringify(sourceBounds));

    this.petInitialPlacement = {
      ...placementWithin(bounds, sourceBounds),
      // 座標是用畫布像素換算成模型座標的，換算只有在畫布已經是這個尺寸時才成立。
      // 送實際拿到的尺寸，不是我們要求的——這兩個可能不一樣。
      canvasWidth: bounds.width,
      canvasHeight: bounds.height,
    };
    console.log('[pet] placement', JSON.stringify(this.petInitialPlacement));

    if (isMac) this.window.setWindowButtonVisibility(false);
    this.window.setResizable(false);
    this.window.setSkipTaskbar(true);
    this.window.setFocusable(false);

    this.applyIgnoreMouse(true);
    if (isMac) {
      this.window.setVisibleOnAllWorkspaces(true, {
        visibleOnFullScreen: true,
      });
    }

    this.window.webContents.send('mode-changed', 'pet');
  }
  
  getWindow(): BrowserWindow | null {
    return this.window;
  }

  setIgnoreMouseEvents(ignore: boolean): void {
    this.applyIgnoreMouse(ignore);
  }

  maximizeWindow(): void {
    if (!this.window) return;

    if (this.isWindowMaximized()) {
      if (this.windowedBounds) {
        this.window.setBounds(this.windowedBounds);
        this.windowedBounds = null;
        this.window.webContents.send('window-maximized-change', false);
      }
    } else {
      this.windowedBounds = this.window.getBounds();
      const { width, height } = screen.getPrimaryDisplay().workArea;
      this.window.setBounds({
        x: 0, y: 0, width, height,
      });
      this.window.webContents.send('window-maximized-change', true);
    }
  }

  isWindowMaximized(): boolean {
    if (!this.window) return false;
    const bounds = this.window.getBounds();
    const { width, height } = screen.getPrimaryDisplay().workArea;
    return bounds.width >= width && bounds.height >= height;
  }

  updateComponentHover(componentId: string, isHovering: boolean): void {
    if (this.currentMode === 'window') {
      console.log('[pet] hover ignored, still in window mode:', componentId, isHovering);
      return;
    }

    // If force ignore is enabled, don't change the mouse ignore state
    if (this.forceIgnoreMouse) {
      console.log('[pet] hover ignored, force passthrough is on:', componentId, isHovering);
      return;
    }

    if (isHovering) {
      this.hoveringComponents.add(componentId);
    } else {
      this.hoveringComponents.delete(componentId);
    }

    if (this.window) {
      const shouldIgnore = this.hoveringComponents.size === 0;
      // 拖拉的前提就是這一行：滑鼠移到角色上時穿透必須關掉。它沒印出來，代表
      // renderer 根本沒收到滑鼠事件（forward 沒生效），不是 hit test 判錯。
      console.log('[pet] hover', componentId, isHovering, '→ passthrough', shouldIgnore);
      this.applyIgnoreMouse(shouldIgnore);
      if (!shouldIgnore) {
        this.window.setFocusable(true);
      }
    }
  }

  // Toggle force ignore mouse events
  toggleForceIgnoreMouse(): void {
    this.forceIgnoreMouse = !this.forceIgnoreMouse;

    // Apply the new setting immediately
    if (this.forceIgnoreMouse) {
      this.applyIgnoreMouse(true);
    } else {
      // Reapply normal behavior based on hovering components
      const shouldIgnore = this.hoveringComponents.size === 0;
      this.applyIgnoreMouse(shouldIgnore);
    }

    // Notify renderer about the change
    this.window?.webContents.send('force-ignore-mouse-changed', this.forceIgnoreMouse);
  }

  // Get current force ignore state
  isForceIgnoreMouse(): boolean {
    return this.forceIgnoreMouse;
  }

  // Get current mode
  getCurrentMode(): 'window' | 'pet' {
    return this.currentMode;
  }
}
