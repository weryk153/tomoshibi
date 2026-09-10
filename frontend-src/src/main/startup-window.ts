// 後端還沒好之前顯示的小視窗。
//
// 第一次啟動要裝執行環境、下載語音辨識模型，動輒幾分鐘。主視窗在後端就緒前
// 打開只會是一個一直「連線中」的畫面，使用者分不出是在忙還是壞了——所以先顯示
// 這個，並且把子行程最新一行輸出擺出來，證明它還在動。
//
// 頁面用 data: URL 內嵌，不走 renderer 的建置：它必須在任何東西載入前就能顯示，
// 也不需要 React 或 i18n 那一整套。

import { BrowserWindow, dialog, shell } from 'electron';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { BackendProgress, BackendResult } from './backend-manager';

type Lang = 'en' | 'zh-TW' | 'zh-CN' | 'ja' | 'ko';

interface Strings {
  copying: string
  installing: string
  installingHint: string
  starting: string
  startingHint: string
  failedTitle: string
  failedBody: string
  portInUse: string
  continueAnyway: string
  openLog: string
  quit: string
}

const TEXT: Record<Lang, Strings> = {
  en: {
    copying: 'Updating program files…',
    installing: 'Installing the runtime',
    installingHint: 'Only needed on first launch or after an update. This can take a few minutes.',
    starting: 'Starting up',
    startingHint: 'The first launch also downloads the speech recognition model.',
    failedTitle: 'The backend did not start',
    failedBody: 'Open the log to see why. "Open anyway" shows the app; it connects on its own once a backend is available.',
    portInUse: 'Port 12393 is already used by another program. Close that program, then open Tomoshibi again.',
    continueAnyway: 'Open anyway',
    openLog: 'Open log',
    quit: 'Quit',
  },
  'zh-TW': {
    copying: '正在更新程式檔案…',
    installing: '正在安裝執行環境',
    installingHint: '只有第一次啟動或更新後需要，視網路速度約需數分鐘。',
    starting: '正在啟動',
    startingHint: '第一次啟動還會下載語音辨識模型。',
    failedTitle: '後端沒有順利啟動',
    failedBody: '可以打開記錄檔查看原因。選「仍然開啟」會照常顯示畫面，等後端可用時自動連上。',
    portInUse: '連接埠 12393 已經被其他程式佔用。關掉那個程式後，再重新開啟 Tomoshibi。',
    continueAnyway: '仍然開啟',
    openLog: '開啟記錄檔',
    quit: '結束',
  },
  'zh-CN': {
    copying: '正在更新程序文件…',
    installing: '正在安装运行环境',
    installingHint: '只有首次启动或更新后需要，视网速约需几分钟。',
    starting: '正在启动',
    startingHint: '首次启动还会下载语音识别模型。',
    failedTitle: '后端没有正常启动',
    failedBody: '可以打开日志查看原因。选择“仍然打开”会照常显示界面，后端可用时自动连接。',
    portInUse: '端口 12393 已被其他程序占用。关闭该程序后，再重新打开 Tomoshibi。',
    continueAnyway: '仍然打开',
    openLog: '打开日志',
    quit: '退出',
  },
  ja: {
    copying: 'プログラムファイルを更新しています…',
    installing: '実行環境をインストールしています',
    installingHint: '初回起動時とアップデート後のみ必要です。数分かかることがあります。',
    starting: '起動しています',
    startingHint: '初回起動時は音声認識モデルもダウンロードします。',
    failedTitle: 'バックエンドを起動できませんでした',
    failedBody: 'ログで原因を確認できます。「このまま開く」を選ぶと画面を表示し、バックエンドが使えるようになると自動で接続します。',
    portInUse: 'ポート 12393 が別のプログラムに使われています。そのプログラムを終了してから、Tomoshibi を開き直してください。',
    continueAnyway: 'このまま開く',
    openLog: 'ログを開く',
    quit: '終了',
  },
  ko: {
    copying: '프로그램 파일을 업데이트하는 중…',
    installing: '실행 환경을 설치하는 중',
    installingHint: '처음 실행하거나 업데이트한 뒤에만 필요합니다. 몇 분 걸릴 수 있습니다.',
    starting: '시작하는 중',
    startingHint: '처음 실행할 때는 음성 인식 모델도 다운로드합니다.',
    failedTitle: '백엔드를 시작하지 못했습니다',
    failedBody: '로그에서 원인을 확인할 수 있습니다. "그래도 열기"를 선택하면 화면을 표시하고, 백엔드를 사용할 수 있게 되면 자동으로 연결합니다.',
    portInUse: '포트 12393을 다른 프로그램이 사용 중입니다. 해당 프로그램을 종료한 뒤 Tomoshibi를 다시 열어 주세요.',
    continueAnyway: '그래도 열기',
    openLog: '로그 열기',
    quit: '종료',
  },
};

export function pickLang(locale: string): Lang {
  const l = locale.toLowerCase();
  if (l.startsWith('zh')) {
    return /^zh-(tw|hk|mo)|hant/.test(l) ? 'zh-TW' : 'zh-CN';
  }
  if (l.startsWith('ja')) return 'ja';
  if (l.startsWith('ko')) return 'ko';
  return 'en';
}

function iconDataUrl(): string {
  try {
    const png = readFileSync(join(__dirname, '../../resources/icon.png'));
    return `data:image/png;base64,${png.toString('base64')}`;
  } catch {
    return '';
  }
}

// 「燈火」：暗底上一點暖色的光，跟圖示的燈光一致。
function pageHtml(icon: string): string {
  return `<!doctype html><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<style>
:root{color-scheme:dark}
html,body{margin:0;height:100%;overflow:hidden;background:#16131d;color:#ece6f5;
  font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang TC","Microsoft JhengHei","Hiragino Sans","Malgun Gothic",sans-serif;
  user-select:none;-webkit-app-region:drag;cursor:default}
.head{display:flex;gap:18px;align-items:center;padding:30px 30px 0}
img{width:64px;height:64px;flex:none;filter:drop-shadow(0 0 16px rgba(242,183,102,.35))}
h1{margin:0;font-size:17px;font-weight:600;letter-spacing:.03em}
p{margin:2px 0 0}
#title{color:#f2b766}
#hint{color:#9d93ad;font-size:12px}
.bar{position:relative;height:2px;margin:24px 30px 0;background:#2a2433;border-radius:2px;overflow:hidden}
.bar::after{content:"";position:absolute;top:0;bottom:0;left:0;width:35%;
  background:linear-gradient(90deg,transparent,#f2b766,transparent);animation:glide 1.8s ease-in-out infinite}
@keyframes glide{from{transform:translateX(-100%)}to{transform:translateX(290%)}}
@media (prefers-reduced-motion:reduce){.bar::after{animation:none;width:100%;opacity:.45}}
#line{margin:10px 30px 0;font:11px/1.4 ui-monospace,Menlo,Consolas,monospace;color:#6f6680;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style>
<div class="head">${icon ? `<img src="${icon}" alt="">` : ''}
<div><h1>Tomoshibi</h1><p id="title"></p><p id="hint"></p></div></div>
<div class="bar"></div>
<div id="line"></div>
<script>
window.__set = function (title, hint, line) {
  document.getElementById('title').textContent = title;
  document.getElementById('hint').textContent = hint;
  document.getElementById('line').textContent = line;
};
</script>`;
}

export class StartupWindow {
  private readonly window: BrowserWindow;

  private readonly t: Strings;

  private loaded = false;

  private state = { title: '', hint: '', line: '' };

  private flushTimer: ReturnType<typeof setTimeout> | null = null;

  private readonly showTimer: ReturnType<typeof setTimeout>;

  constructor(lang: Lang) {
    this.t = TEXT[lang];
    this.window = new BrowserWindow({
      width: 460,
      height: 200,
      show: false,
      frame: false,
      resizable: false,
      maximizable: false,
      fullscreenable: false,
      center: true,
      backgroundColor: '#16131d',
      title: 'Tomoshibi',
      webPreferences: { sandbox: true, contextIsolation: true },
    });
    this.window.webContents.once('did-finish-load', () => {
      this.loaded = true;
      this.flush();
    });
    this.window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(pageHtml(iconDataUrl()))}`);

    // 後端早就在跑的話，整個流程不到一秒，這時閃一下啟動畫面反而像出錯。
    this.showTimer = setTimeout(() => {
      if (!this.window.isDestroyed()) this.window.show();
    }, 600);
  }

  update(progress: BackendProgress): void {
    const { t } = this;
    const [title, hint] = {
      copying: [t.copying, ''],
      installing: [t.installing, t.installingHint],
      starting: [t.starting, t.startingHint],
    }[progress.stage];
    // 換階段時清掉上一階段的輸出，免得「正在啟動」底下還掛著 uv 的最後一行。
    const line = progress.line ?? (title === this.state.title ? this.state.line : '');
    this.state = { title, hint, line };
    // 下載進度一秒可以刷幾十行，沒必要每行都進 renderer。
    if (!this.flushTimer) {
      this.flushTimer = setTimeout(() => {
        this.flushTimer = null;
        this.flush();
      }, 120);
    }
  }

  close(): void {
    clearTimeout(this.showTimer);
    if (this.flushTimer) clearTimeout(this.flushTimer);
    if (!this.window.isDestroyed()) this.window.destroy();
  }

  /** 後端失敗時問使用者要不要照樣開畫面。回傳 true 表示繼續。 */
  async askAfterFailure(result: Extract<BackendResult, { kind: 'failed' }>): Promise<boolean> {
    const { t } = this;
    for (;;) {
      // eslint-disable-next-line no-await-in-loop
      const { response } = await dialog.showMessageBox({
        type: 'error',
        title: 'Tomoshibi',
        message: t.failedTitle,
        // 原因認得出來就先講人話，技術細節擺後面給需要的人看。
        detail: result.cause === 'port-in-use'
          ? `${t.portInUse}\n\n${t.failedBody}\n\n${result.message}`
          : `${t.failedBody}\n\n${result.message}`,
        buttons: [t.continueAnyway, t.openLog, t.quit],
        defaultId: 0,
        cancelId: 2,
        noLink: true,
      });
      if (response !== 1) return response === 0;
      // 開完記錄檔再問一次，而不是直接替使用者決定結束或繼續。
      // eslint-disable-next-line no-await-in-loop
      await shell.openPath(result.logPath);
    }
  }

  private flush(): void {
    if (!this.loaded || this.window.isDestroyed()) return;
    const { title, hint, line } = this.state;
    this.window.webContents
      .executeJavaScript(`window.__set(${JSON.stringify(title)}, ${JSON.stringify(hint)}, ${JSON.stringify(line)})`)
      .catch(() => {});
  }
}
