// 下載要隨桌面版一起打包的 uv 執行檔，放到 bundled/uv/<os>-<arch>/。
//
// electron-builder.yml 的 extraResources 用 ${os}-${arch} 取對應的那一份，所以
// 目錄名稱必須跟 electron-builder 的巨集一致：os 是 mac／win，arch 是 x64／arm64。
//
// 版本與 SHA-256 釘死在這裡。下載的是會被使用者執行的程式，校驗碼不符就中止，
// 而不是「大概沒問題」地打包進去。升級 uv 時從 release 頁的 .sha256 檔抄過來。
//
// 用法：
//   node scripts/fetch-uv.mjs mac   # x64 + arm64（build:mac 同時建兩種架構）
//   node scripts/fetch-uv.mjs win   # x64
//   node scripts/fetch-uv.mjs       # 只抓目前這台機器的

import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import {
  chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync,
  readFileSync, rmSync, statSync, writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const UV_VERSION = '0.12.12';

const TARGETS = {
  'mac-arm64': {
    asset: 'uv-aarch64-apple-darwin.tar.gz',
    sha256: '46740540b63fdee9a6cb2e19baf3f1f475b850c440a33e63455087a6871263f1',
    exe: 'uv',
  },
  'mac-x64': {
    asset: 'uv-x86_64-apple-darwin.tar.gz',
    sha256: '0dc8cd6c961582b0d140b5398f96b23502885277fb3464241456a2435e460dfa',
    exe: 'uv',
  },
  'win-x64': {
    asset: 'uv-x86_64-pc-windows-msvc.zip',
    sha256: '3d54912924c36e862c14f427d04f2ed70a99e8001d1c30caa101f6d5711626d5',
    exe: 'uv.exe',
  },
};

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const outRoot = join(root, 'bundled', 'uv');

function currentKey() {
  const os = { darwin: 'mac', win32: 'win' }[process.platform];
  return `${os}-${process.arch}`;
}

function keysFor(arg) {
  if (!arg) return [currentKey()];
  if (arg === 'mac') return ['mac-arm64', 'mac-x64'];
  if (arg === 'win') return ['win-x64'];
  return [arg];
}

function findFile(dir, name) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      const found = findFile(full, name);
      if (found) return found;
    } else if (entry === name) {
      return full;
    }
  }
  return null;
}

async function fetchOne(key) {
  const target = TARGETS[key];
  if (!target) throw new Error(`沒有 ${key} 的 uv（支援：${Object.keys(TARGETS).join('、')}）`);

  const outDir = join(outRoot, key);
  const exePath = join(outDir, target.exe);
  const stamp = join(outDir, '.source');
  const expected = `${UV_VERSION} ${target.sha256}`;
  if (existsSync(exePath) && existsSync(stamp) && readFileSync(stamp, 'utf8') === expected) {
    console.log(`uv ${UV_VERSION} ${key}：已存在，略過`);
    return;
  }

  const url = `https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${target.asset}`;
  console.log(`uv ${UV_VERSION} ${key}：下載 ${url}`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`下載失敗：HTTP ${res.status} ${url}`);
  const archive = Buffer.from(await res.arrayBuffer());

  const actual = createHash('sha256').update(archive).digest('hex');
  if (actual !== target.sha256) {
    throw new Error(`${target.asset} 校驗碼不符\n  預期 ${target.sha256}\n  實際 ${actual}`);
  }

  const work = mkdtempSync(join(tmpdir(), 'tomoshibi-uv-'));
  try {
    const archivePath = join(work, target.asset);
    writeFileSync(archivePath, archive);
    // macOS 與 Windows 10+ 內建的 tar 都是 bsdtar，zip 也解得開。
    execFileSync('tar', ['-xf', archivePath, '-C', work]);
    const extracted = findFile(work, target.exe);
    if (!extracted) throw new Error(`${target.asset} 裡找不到 ${target.exe}`);

    rmSync(outDir, { recursive: true, force: true });
    mkdirSync(outDir, { recursive: true });
    copyFileSync(extracted, exePath);
    chmodSync(exePath, 0o755);
    writeFileSync(stamp, expected);
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
  console.log(`uv ${UV_VERSION} ${key}：完成 → ${exePath}`);
}

for (const key of keysFor(process.argv[2])) {
  // eslint-disable-next-line no-await-in-loop
  await fetchOne(key);
}
