// 把桌面版要帶的 Python 後端複製到 bundled/backend/，給 electron-builder 的
// extraResources 打包。
//
// 用 git 決定帶哪些檔案，而且只取執行期用得到的目錄。直接複製整個 repo 的話，
// 本機的 .venv、下載的模型（動輒 GB 級）、conf.yaml、聊天紀錄、自己放的角色模型
// 全都會被打包出去——後面幾樣是個人資料，不是體積問題而已。
//
// 範圍是「追蹤中的」加上「還沒 commit、但沒被 .gitignore 排除的新檔」。只取追蹤
// 中的會漏掉剛寫好的新模組：打包出來的後端一 import 就 ModuleNotFoundError，
// 而開發環境裡一切正常（踩過一次）。個人資料都在 .gitignore 裡，不受影響。
//
// 另外寫一個 .bundle-id（所有檔案內容的雜湊）。app 啟動時拿它和使用者那份比對，
// 不同才重新同步程式檔。用內容雜湊而不是版本號：沒升版號的本機建置也會正確更新。

import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import {
  copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync,
} from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// 對照 run_server.py 與 server.py 在工作目錄底下讀的東西。
// frontend/ 桌面版本身用不到（畫面是 app 內建的），但 server.py 會把它掛成 /，
// 目錄不存在就啟動失敗；手機或瀏覽器連進來也要用它。
const ENTRIES = [
  'run_server.py',
  'pyproject.toml',
  'uv.lock',
  '.python-version',
  'model_profiles.yaml',
  'LICENSE',
  'LICENSE-Live2D.md',
  'NOTICE',
  'src',
  'upgrade_codes',
  'prompts',
  'config_templates',
  'characters',
  'personas',
  'live2d-models',
  'vrm-models',
  'backgrounds',
  'web_tool',
  'frontend',
];

const frontendSrc = join(dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = join(frontendSrc, '..');
const out = join(frontendSrc, 'bundled', 'backend');

const listed = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', ...ENTRIES], {
  cwd: repoRoot,
  maxBuffer: 64 * 1024 * 1024,
}).toString('utf8').split('\0').filter(Boolean);

// 追蹤中但工作目錄裡已經刪掉的檔案（還沒 commit 的刪除）不帶。
// 同一個檔案可能同時以 cached 與 others 出現（例如 index 有衝突時），去重後排序，
// bundle-id 才會穩定。
const files = [...new Set(listed)].filter((f) => existsSync(join(repoRoot, f))).sort();

for (const required of ['run_server.py', 'uv.lock', 'frontend/index.html']) {
  if (!files.includes(required)) {
    throw new Error(`缺少 ${required}——後端沒辦法在沒有它的情況下啟動`);
  }
}

rmSync(out, { recursive: true, force: true });
const hash = createHash('sha256');
let bytes = 0;
for (const file of files) {
  const src = join(repoRoot, file);
  const dst = join(out, file);
  mkdirSync(dirname(dst), { recursive: true });
  copyFileSync(src, dst);
  const content = readFileSync(src);
  bytes += content.length;
  hash.update(file).update('\0').update(content).update('\0');
}
const bundleId = hash.digest('hex');
writeFileSync(join(out, '.bundle-id'), `${bundleId}\n`);

console.log(`後端：${files.length} 個檔案，${(bytes / 1048576).toFixed(1)}MB → ${out}`);
console.log(`bundle-id ${bundleId.slice(0, 16)}`);
