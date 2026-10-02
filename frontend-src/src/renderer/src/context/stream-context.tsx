// 直播的前端狀態：主視窗看「現在是不是在直播」（停用輸入列），舞台頁看「正在回哪
// 則留言」與「是不是被別的舞台頁取代了」。都由 websocket-handler 收到訊息時設定。
import {
  createContext, useContext, useMemo, useState, type ReactNode,
} from 'react';

export interface StreamComment {
  author: string;
  text: string;
}

interface StreamState {
  live: boolean;
  setLive: (live: boolean) => void;
  comment: StreamComment | null;
  setComment: (comment: StreamComment | null) => void;
  stageReplaced: boolean;
  setStageReplaced: (replaced: boolean) => void;
}

const StreamContext = createContext<StreamState | null>(null);

export function StreamProvider({ children }: { children: ReactNode }): JSX.Element {
  const [live, setLive] = useState(false);
  const [comment, setComment] = useState<StreamComment | null>(null);
  const [stageReplaced, setStageReplaced] = useState(false);
  const value = useMemo(() => ({
    live, setLive, comment, setComment, stageReplaced, setStageReplaced,
  }), [live, comment, stageReplaced]);
  return <StreamContext.Provider value={value}>{children}</StreamContext.Provider>;
}

export function useStream(): StreamState {
  const context = useContext(StreamContext);
  if (!context) throw new Error('useStream must be used within StreamProvider');
  return context;
}
