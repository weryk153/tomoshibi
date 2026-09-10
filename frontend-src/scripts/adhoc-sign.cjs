// electron-builder 的 afterPack hook：把 macOS 的 .app 整包做 ad-hoc 簽章。
//
// 沒有 Apple Developer ID 時 electron-builder 會整個略過簽章，但 Electron 的主程式
// 本來就帶著 ad-hoc 簽章——打包時改了 Info.plist、塞進 resources 之後，那個簽章就
// 對不上了（codesign：code has no resources but signature indicates they must be
// present）。Apple Silicon 上，從網路下載、帶隔離標記的這種 app 會被判成
// 「已損毀，應丟到垃圾桶」，而且沒有任何放行的方法。
//
// 整包重新 ad-hoc 簽過之後，同樣的情況變成一般的「Apple 無法驗證」，使用者可以到
// 「系統設定 → 隱私權與安全性 → 強制打開」放行。兩種對話框本機都加隔離標記實測過。
//
// 放在 afterPack 而不是 afterSign：簽章步驟被略過，而 dmg 是在這之後才做的。
// 日後若有正式憑證，electron-builder 的簽章會在這之後覆蓋掉 ad-hoc 簽章，不衝突。

const { execFileSync } = require('node:child_process');
const path = require('node:path');

exports.default = async function adhocSign(context) {
  if (context.electronPlatformName !== 'darwin') return;
  const app = path.join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`);
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', app], { stdio: 'inherit' });
  // 簽完當場驗證。簽壞了就讓建置失敗，而不是做出一個使用者打不開的 dmg。
  execFileSync('codesign', ['--verify', '--deep', '--strict', app], { stdio: 'inherit' });
  console.log(`  • ad-hoc signed  ${app}`);
};
