import { createRoot } from 'react-dom/client';
// 字型打包進來，不走 Google Fonts：離線也要長得一樣。
// Space Grotesk／IBM Plex Mono 只拿 latin 子集（角色名、標籤是中日文時會
// 落到下一個字型）。Noto Sans TC 用可變字型版：一組 woff2 涵蓋所有字重，
// 比靜態版 400/500/700 三組（各自還附 woff 備援）小五倍左右。
import '@fontsource/space-grotesk/latin-500.css';
import '@fontsource/space-grotesk/latin-700.css';
import '@fontsource/ibm-plex-mono/latin-400.css';
import '@fontsource/ibm-plex-mono/latin-500.css';
import '@fontsource-variable/noto-sans-tc/wght.css';
import './index.css';
import App from './App';
import { LAppAdapter } from '../WebSDK/src/lappadapter';
import './i18n';

const originalConsoleWarn = console.warn;
console.warn = (...args) => {
  if (typeof args[0] === 'string' && args[0].includes('onnxruntime')) {
    return;
  }
  originalConsoleWarn.apply(console, args);
};

// Suppress specific console.error messages from @chatscope/chat-ui-kit-react
const originalConsoleError = console.error;
const errorMessagesToIgnore = ["Warning: Failed"];
console.error = (...args: any[]) => {
  if (typeof args[0] === 'string') {
    const shouldIgnore = errorMessagesToIgnore.some(msg => args[0].startsWith(msg));
    if (shouldIgnore) {
      return; // Suppress the warning
    }
  }
  // Call the original console.error for other messages
  originalConsoleError.apply(console, args);
};

if (typeof window !== 'undefined') {
  (window as any).getLAppAdapter = () => LAppAdapter.getInstance();

  // Dynamically load the Live2D Core script
  const loadLive2DCore = () => {
    return new Promise<void>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = './libs/live2dcubismcore.js'; // Path to the copied script
      script.onload = () => {
        console.log('Live2D Cubism Core loaded successfully.');
        resolve();
      };
      script.onerror = (error) => {
        console.error('Failed to load Live2D Cubism Core:', error);
        reject(error);
      };
      document.head.appendChild(script);
    });
  };

  // Load the script and then render the app
  loadLive2DCore()
    .then(() => {
      createRoot(document.getElementById('root')!).render(
        <App />,
      );
    })
    .catch((error) => {
      console.error('Application failed to start due to script loading error:', error);
      // Optionally render an error message to the user
      const rootElement = document.getElementById('root');
      if (rootElement) {
        rootElement.innerHTML = 'Error loading required components. Please check the console for details.';
      }
    });
}
