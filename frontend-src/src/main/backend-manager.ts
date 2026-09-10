// 桌面版自己把 Python 後端拉起來。
//
// 安裝檔只帶 uv 和後端原始碼（resources/backend、resources/uv），依賴在第一次啟動
// 時才裝：依賴有好幾百 MB 而且分平台，塞進安裝檔等於每個安裝檔各背一份，更新時
// 也得整份重下載。uv 本身會處理 Python 直譯器的下載，所以使用者不需要先裝 Python。
//
// 為什麼不直接在 resources/backend 裡跑：app 目錄對一般使用者是唯讀的（Windows 裝
// 在 Program Files；macOS 從下載資料夾開的 .app 甚至會被搬到隨機的唯讀路徑），
// 但後端會在自己的目錄底下寫 conf.yaml、聊天紀錄、快取和下載的模型——那些路徑
// 全部是相對於工作目錄寫死的。所以把程式檔同步到 userData，使用者的東西留在原地。
//
// 開發模式（沒打包）什麼都不做：開發者自己跑 `uv run run_server.py`。

import { app } from 'electron';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import {
  createWriteStream, existsSync, mkdirSync, readFileSync, writeFileSync,
  type WriteStream,
} from 'node:fs';
import { cp, rm } from 'node:fs/promises';
import { join } from 'node:path';

// 與 renderer 的 services/backend-url.ts 的 FALLBACK_HOST 一致。使用者若在 conf.yaml
// 改了 port，自己架的後端照樣能連（renderer 有自己的連線設定），只是這裡偵測不到。
const PROBE_URL = 'http://127.0.0.1:12393/api/characters';

// 更新時整個刪掉再複製的程式目錄。不先刪的話，舊版移除掉的 .py 會留在原地，
// 而且照樣 import 得到。使用者狀態（conf.yaml、characters/*.yaml、chat_history/、
// models/、cache/、.venv/……）不在這份清單裡、也不在安裝檔裡，所以不會被碰到。
const CODE_DIRS = ['src', 'upgrade_codes', 'prompts', 'config_templates', 'web_tool', 'frontend'];

// 後端啟動時會先下載語音辨識模型才開始 listen，網路慢的話要很久。所以不設總時限，
// 只在「沒有任何輸出也還沒就緒」持續這麼久時判定卡住。
const SERVER_SILENCE_LIMIT_MS = 10 * 60 * 1000;

const TAIL_LINES = 40;

// loguru 用 colorize=True，就算輸出不是終端機也會帶色碼。
// eslint-disable-next-line no-control-regex
const ANSI_RE = /\x1b\[[0-9;]*[A-Za-z]/g;

export type BackendStage = 'copying' | 'installing' | 'starting';

export interface BackendProgress {
  stage: BackendStage
  /** 子行程最新的一行輸出，給啟動畫面顯示「還活著」。 */
  line?: string
}

export type FailureCause = 'port-in-use' | 'unknown';

export type BackendResult =
  | { kind: 'disabled' } // 開發模式
  | { kind: 'reused' } // 已經有一個後端在跑（自己開的、或上一次沒關乾淨的）
  | { kind: 'started' }
  | { kind: 'failed', cause: FailureCause, message: string, logPath: string };

// macOS／Linux 是 Errno 48／98，Windows 是 WinError 10048。
const PORT_IN_USE_RE = /address already in use|only one usage of each socket address|Errno 48|Errno 98|WinError 10048/i;

// 看起來是「原因」的行。直接拿輸出的最後十幾行當錯誤訊息行不通：port 被佔用時，
// 真正的原因只有一行，卻被預設設定連不上 Ollama 的那串 traceback 擠出畫面（踩過）。
const ERROR_LINE_RE = /\b(ERROR|CRITICAL)\b|Error:|Exception:|Errno|WinError|exited with/;

function summarize(lines: string[]): string {
  const errors = lines.filter((l) => ERROR_LINE_RE.test(l) && !/^\s*File "/.test(l));
  const picked = errors.length > 0 ? errors : lines;
  return [...new Set(picked)].slice(-8).join('\n');
}

async function probe(): Promise<boolean> {
  try {
    const res = await fetch(PROBE_URL, { signal: AbortSignal.timeout(1500) });
    if (!res.ok) return false;
    // 只看 port 有沒有開不夠：別的程式佔著 12393 時會誤判成「後端已在跑」，
    // 然後畫面永遠連不上。這個路由是 Tomoshibi 才有的。
    const body = (await res.json()) as { characters?: unknown };
    return Array.isArray(body?.characters);
  } catch {
    return false;
  }
}

function childEnv(uv: string): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    // Windows 的主控台編碼是 cp950／cp936，log 裡的中文和 emoji 寫進 pipe 會直接
    // UnicodeEncodeError 讓後端啟動失敗。
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
    PYTHONUNBUFFERED: '1',
    // 一律用 uv 自己下載的 Python。否則系統上剛好有個 3.10（Homebrew、conda、
    // Microsoft Store 版）就會被拿去用，每台機器裝出來的環境都不一樣。
    UV_PYTHON_PREFERENCE: 'only-managed',
    // 設定精靈的「一鍵安裝 GPT-SoVITS」要用 uv 建它自己的 Python 環境
    // （gpt_sovits_installer.py）。使用者電腦上不一定有 uv，給它內附的這一個。
    TOMOSHIBI_UV: uv,
  };
  // 從啟用了 venv 的終端機開 app 時，這些會把 uv 和 Python 指到別的環境去。
  for (const key of ['VIRTUAL_ENV', 'UV_PROJECT_ENVIRONMENT', 'PYTHONPATH', 'PYTHONHOME', 'CONDA_PREFIX']) {
    delete env[key];
  }
  return env;
}

function forceKill(proc: ChildProcess): void {
  if (proc.pid === undefined) return;
  if (process.platform === 'win32') {
    // TerminateProcess 只殺這一個行程，/T 連它開出來的子行程一起收掉。
    spawnSync('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { windowsHide: true });
  } else {
    proc.kill('SIGKILL');
  }
}

export class BackendManager {
  private child: ChildProcess | null = null;

  private log: WriteStream | null = null;

  private readonly tail: string[] = [];

  private get workspace(): string {
    return join(app.getPath('userData'), 'backend');
  }

  private get payload(): string {
    return join(process.resourcesPath, 'backend');
  }

  get logPath(): string {
    return join(this.workspace, 'logs', 'desktop-backend.log');
  }

  isRunning(): boolean {
    const proc = this.child;
    return proc !== null && proc.exitCode === null && proc.signalCode === null;
  }

  async start(onProgress: (progress: BackendProgress) => void): Promise<BackendResult> {
    if (!app.isPackaged) return { kind: 'disabled' };
    if (await probe()) return { kind: 'reused' };

    try {
      mkdirSync(join(this.workspace, 'logs'), { recursive: true });
      this.log = createWriteStream(this.logPath, { flags: 'a' });
      this.write(`\n===== ${new Date().toISOString()} Tomoshibi ${app.getVersion()} =====`);

      if (!existsSync(join(this.payload, '.bundle-id'))) {
        throw new Error(`bundled backend not found at ${this.payload}`);
      }
      if (this.needsSync()) {
        onProgress({ stage: 'copying' });
        await this.syncPayload();
      }

      // 每次啟動都跑：環境已經對的話一秒內結束，壞掉或裝到一半被中斷的話會補齊。
      onProgress({ stage: 'installing' });
      await this.runToEnd(this.uvPath(), ['sync', '--frozen', '--no-dev', '--no-progress'], (line) => {
        onProgress({ stage: 'installing', line });
      });

      onProgress({ stage: 'starting' });
      await this.serve((line) => onProgress({ stage: 'starting', line }));
      return { kind: 'started' };
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      const recent = summarize(this.tail);
      this.write(`[desktop] ${reason}`);
      return {
        kind: 'failed',
        cause: this.tail.some((l) => PORT_IN_USE_RE.test(l)) ? 'port-in-use' : 'unknown',
        message: recent ? `${reason}\n\n${recent}` : reason,
        logPath: this.logPath,
      };
    }
  }

  /** 關 app 時呼叫。先好好請它結束（uvicorn 會清快取），等不到才硬殺。 */
  stop(): Promise<void> {
    const proc = this.child;
    if (!proc || !this.isRunning()) return Promise.resolve();
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        forceKill(proc);
        resolve();
      }, 3000);
      proc.once('exit', () => {
        clearTimeout(timer);
        resolve();
      });
      // Windows 沒有 SIGTERM，kill() 本來就是硬殺，而且殺不到子行程。
      if (process.platform === 'win32') forceKill(proc);
      else proc.kill('SIGTERM');
    });
  }

  private uvPath(): string {
    return join(process.resourcesPath, 'uv', process.platform === 'win32' ? 'uv.exe' : 'uv');
  }

  private pythonPath(): string {
    return process.platform === 'win32'
      ? join(this.workspace, '.venv', 'Scripts', 'python.exe')
      : join(this.workspace, '.venv', 'bin', 'python');
  }

  private needsSync(): boolean {
    const read = (dir: string): string | null => {
      try {
        return readFileSync(join(dir, '.bundle-id'), 'utf8').trim();
      } catch {
        return null;
      }
    };
    return read(this.workspace) !== read(this.payload);
  }

  private async syncPayload(): Promise<void> {
    await Promise.all(
      CODE_DIRS.map((dir) => rm(join(this.workspace, dir), { recursive: true, force: true })),
    );
    await cp(this.payload, this.workspace, { recursive: true, force: true });
    // 複製完才寫。複製到一半被關掉的話，下次啟動會重來一次。
    // （.bundle-id 本身也在 payload 裡被複製過來了，這裡是保險再寫一次確定內容一致。）
    writeFileSync(join(this.workspace, '.bundle-id'), readFileSync(join(this.payload, '.bundle-id')));
  }

  private spawnChild(command: string, args: string[], onLine: (line: string) => void): ChildProcess {
    this.write(`[desktop] $ ${command} ${args.join(' ')}`);
    const proc = spawn(command, args, {
      cwd: this.workspace,
      env: childEnv(this.uvPath()),
      windowsHide: true, // 否則 Windows 會為 uv 和 python 各彈一個黑色主控台視窗
    });
    this.child = proc;

    const pipe = (stream: NodeJS.ReadableStream | null): void => {
      if (!stream) return;
      let pending = '';
      stream.setEncoding('utf8');
      stream.on('data', (chunk: string) => {
        pending += chunk;
        // tqdm 用 \r 原地更新進度，也要當成換行，否則整段下載都看不到任何一行。
        const parts = pending.split(/\r\n|\r|\n/);
        pending = parts.pop() ?? '';
        for (const raw of parts) {
          const line = raw.replace(ANSI_RE, '').trimEnd();
          if (!line) continue;
          this.write(line);
          onLine(line);
        }
      });
    };
    pipe(proc.stdout);
    pipe(proc.stderr);
    return proc;
  }

  private runToEnd(command: string, args: string[], onLine: (line: string) => void): Promise<void> {
    return new Promise((resolve, reject) => {
      const proc = this.spawnChild(command, args, onLine);
      proc.once('error', reject); // 例如 uv 執行檔不見了
      proc.once('exit', (code, signal) => {
        if (code === 0) resolve();
        else reject(new Error(`${args[0] ?? command} exited with ${code ?? signal}`));
      });
    });
  }

  private serve(onLine: (line: string) => void): Promise<void> {
    return new Promise((resolve, reject) => {
      let lastOutput = Date.now();
      let settled = false;
      let checking = false;

      const proc = this.spawnChild(this.pythonPath(), ['run_server.py'], (line) => {
        lastOutput = Date.now();
        onLine(line);
      });

      const finish = (error?: Error): void => {
        if (settled) return;
        settled = true;
        clearInterval(timer);
        if (error) reject(error);
        else resolve();
      };

      proc.once('error', (error) => finish(error));
      proc.once('exit', (code, signal) => {
        const message = `server exited with ${code ?? signal}`;
        // 就緒之後才結束的話 finish 不會再做事，要自己記一筆；
        // 就緒之前結束的由 start() 的 catch 記，這裡再記就重複了。
        if (settled) this.write(`[desktop] ${message}`);
        finish(new Error(message));
      });

      const timer = setInterval(async () => {
        if (settled || checking) return;
        checking = true;
        const ready = await probe();
        checking = false;
        if (ready) {
          this.write('[desktop] server is ready');
          finish();
        } else if (Date.now() - lastOutput > SERVER_SILENCE_LIMIT_MS) {
          forceKill(proc);
          finish(new Error('server produced no output and never became ready'));
        }
      }, 1000);
    });
  }

  private write(line: string): void {
    this.tail.push(line);
    if (this.tail.length > TAIL_LINES) this.tail.shift();
    this.log?.write(`${line}\n`);
  }
}
