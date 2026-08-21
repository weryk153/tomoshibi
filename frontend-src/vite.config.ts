import { defineConfig, normalizePath } from 'vite';
import path from 'path';
import react from '@vitejs/plugin-react-swc';
import { buildDefines } from './build-defines';

const createConfig = async (outDir: string) => ({
  plugins: [
    // Tailwind v4 的 vite 外掛。兩份設定都要有——只加一邊的話，另一條建置
    // 路徑會安靜地產出沒有任何 utility class 的 CSS（見 build-defines.ts 的事故）。
    //
    // 動態 import 是必要的，不是風格選擇：這個套件是 ESM-only，而本專案沒有
    // "type": "module"，所以 vite 會用 require 載入這份設定，靜態 import 會直接
    // 讓 dev server 起不來（"ESM file cannot be loaded by require"）。下面的
    // vite-plugin-static-copy 也是為了同一個原因寫成這樣。
    (await import('@tailwindcss/vite')).default(),
    (await import('vite-plugin-static-copy')).viteStaticCopy({
      targets: [
        {
          src: normalizePath(path.resolve(__dirname, 'node_modules/@ricky0123/vad-web/dist/vad.worklet.bundle.min.js')),
          dest: './libs/',
        },
        {
          src: normalizePath(path.resolve(__dirname, 'node_modules/@ricky0123/vad-web/dist/silero_vad_v5.onnx')),
          dest: './libs/',
        },
        {
          src: normalizePath(path.resolve(__dirname, 'node_modules/@ricky0123/vad-web/dist/silero_vad_legacy.onnx')),
          dest: './libs/',
        },
        {
          src: normalizePath(path.resolve(__dirname, 'node_modules/onnxruntime-web/dist/*.wasm')),
          dest: './libs/',
        },
        {
          src: normalizePath(path.resolve(__dirname, 'src/renderer/WebSDK/Core/live2dcubismcore.js')),
          dest: './libs/',
        },
      ],
    }),
    react(),
  ],
  // 跟 electron.vite.config.ts 共用同一份，見 build-defines.ts 的說明。
  define: buildDefines,
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src/renderer/src"),
      "@framework": path.resolve(__dirname, "./src/renderer/WebSDK/Framework/src"),
      "@cubismsdksamples": path.resolve(__dirname, "./src/renderer/WebSDK/src"),
      "@motionsyncframework": path.resolve(
        __dirname,
        "./src/renderer/MotionSync/Framework/src",
      ),
      "@motionsync": path.resolve(__dirname, "./src/renderer/MotionSync/src"),
      "/src": path.resolve(__dirname, "./src/renderer/src"),
    },
  },
  root: path.join(__dirname, "src/renderer"),
  publicDir: path.join(__dirname, "src/renderer/public"),
  base: "./",
  server: {
    port: 3000,
  },
  build: {
    outDir: path.join(__dirname, outDir),
    emptyOutDir: true,
    assetsDir: "assets",
    rollupOptions: {
      input: {
        main: path.join(__dirname, "src/renderer/index.html"),
      },
    },
  },
  ssr: {
    noExternal: ['vite-plugin-static-copy'],
  },
});

export default defineConfig(async ({ mode }) => {
  if (mode === 'web') {
    // 直接輸出到 repo 的 frontend/——後端提供的就是這個目錄。
    // emptyOutDir 會先清空它，所以額外的靜態檔必須放在
    // src/renderer/public/ 由建置一併輸出，不能留在 frontend/ 內。
    return createConfig('../frontend');
  }
  return createConfig('dist/renderer');
});
