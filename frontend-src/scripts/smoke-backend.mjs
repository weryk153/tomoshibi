// CI 用：用打包進去的那一份 uv 和後端，照桌面版的步驟實際跑一次，確認 server
// 真的起得來。
//
// 建出安裝檔只證明「檔案湊齊了」。依賴在某個平台上沒有 wheel、Windows 的編碼
// 問題、payload 漏帶了哪個目錄——這些都要到使用者第一次開 app 才會炸，而 CI 上
// 沒有人會去點那個安裝檔。這支把 backend-manager.ts 做的事在無頭環境重演一次：
// 複製到一個可寫的目錄、uv sync、跑 run_server.py、等 /api/characters 回應。
//
// 步驟與環境變數要跟 src/main/backend-manager.ts 保持一致，否則這裡過了不代表 app 會過。
//
// 用法（先跑過 fetch-uv.mjs 與 stage-backend.mjs）：
//   node scripts/smoke-backend.mjs

import { spawn, spawnSync } from 'node:child_process';
import { cpSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const PROBE_URL = 'http://127.0.0.1:12393/api/characters';
const READY_TIMEOUT_MS = 20 * 60 * 1000;

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const isWin = process.platform === 'win32';
const os = { darwin: 'mac', win32: 'win' }[process.platform];
const uv = join(root, 'bundled', 'uv', `${os}-${process.arch}`, isWin ? 'uv.exe' : 'uv');

const env = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONIOENCODING: 'utf-8',
  PYTHONUNBUFFERED: '1',
  UV_PYTHON_PREFERENCE: 'only-managed',
};
for (const key of ['VIRTUAL_ENV', 'UV_PROJECT_ENVIRONMENT', 'PYTHONPATH', 'PYTHONHOME', 'CONDA_PREFIX']) {
  delete env[key];
}

async function probe() {
  try {
    const res = await fetch(PROBE_URL, { signal: AbortSignal.timeout(1500) });
    return res.ok && Array.isArray((await res.json())?.characters);
  } catch {
    return false;
  }
}

if (await probe()) {
  console.error('12393 已經有一個後端在跑，這樣測不出任何東西');
  process.exit(1);
}

const workspace = mkdtempSync(join(tmpdir(), 'tomoshibi-smoke-'));
console.log(`工作目錄：${workspace}`);
cpSync(join(root, 'bundled', 'backend'), workspace, { recursive: true });

const sync = spawnSync(uv, ['sync', '--frozen', '--no-dev', '--no-progress'], {
  cwd: workspace, env, stdio: 'inherit',
});
if (sync.status !== 0) {
  console.error(`uv sync 失敗（${sync.status ?? sync.error}）`);
  process.exit(1);
}

const python = isWin
  ? join(workspace, '.venv', 'Scripts', 'python.exe')
  : join(workspace, '.venv', 'bin', 'python');
const server = spawn(python, ['run_server.py'], { cwd: workspace, env, stdio: 'inherit' });

let exited = null;
server.on('exit', (code, signal) => { exited = code ?? signal; });

const started = Date.now();
let ok = false;
while (Date.now() - started < READY_TIMEOUT_MS && exited === null) {
  // eslint-disable-next-line no-await-in-loop
  if (await probe()) { ok = true; break; }
  // eslint-disable-next-line no-await-in-loop
  await new Promise((r) => setTimeout(r, 1000));
}

if (isWin) spawnSync('taskkill', ['/pid', String(server.pid), '/T', '/F']);
else server.kill('SIGTERM');
await new Promise((r) => setTimeout(r, 2000));
try { rmSync(workspace, { recursive: true, force: true }); } catch { /* Windows 上檔案可能還被佔著 */ }

if (ok) {
  console.log(`\n後端在 ${Math.round((Date.now() - started) / 1000)} 秒內就緒 ✓`);
  process.exit(0);
}
console.error(exited !== null ? `\n後端提前結束（${exited}）` : '\n等待後端就緒逾時');
process.exit(1);
