// 伺服器上的背景圖清單（backgrounds/ 底下的檔名）。websocket-handler 收到後端的
// background-files 寫進來，場景頁的「內建背景」選單從這裡列。
//
// 背景本身由場景決定（scene-context）。以前這裡還存著「目前背景」網址與攝影機
// 開關，跟場景互相蓋來蓋去；那些都搬進場景了。
import {
  createContext, useMemo, useContext, useState,
} from 'react';

export interface BgUrlContextState {
  // 後端 scan_bg_directory() 送的是檔名字串陣列。
  backgroundFiles: string[];
  setBackgroundFiles: (files: string[]) => void;
}

const BgUrlContext = createContext<BgUrlContextState | null>(null);

export function BgUrlProvider({ children }: { children: React.ReactNode }) {
  const [backgroundFiles, setBackgroundFiles] = useState<string[]>([]);
  const contextValue = useMemo(
    () => ({ backgroundFiles, setBackgroundFiles }),
    [backgroundFiles],
  );
  return (
    <BgUrlContext.Provider value={contextValue}>
      {children}
    </BgUrlContext.Provider>
  );
}

export function useBgUrl() {
  const context = useContext(BgUrlContext);
  if (!context) {
    throw new Error('useBgUrl must be used within a BgUrlProvider');
  }
  return context;
}
