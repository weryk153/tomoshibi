import { useMemo, useCallback, useEffect, useState } from 'react';
import { useWebSocket } from '@/context/websocket-context';

interface WSStatusInfo {
  color: string
  textKey: string
  isDisconnected: boolean
  handleClick: () => void
}

/**
 * 連線正常時，這顆狀態徽章顯示多久之後自動消失。
 *
 * 「已連線」在連上的那一刻是有用的回饋，一直掛在畫面左上角就只是佔位置——它
 * 每一秒都在講同一件已經沒有懸念的事。連線中／斷線時則不會消失：那時候它是
 * 可以點的重連按鈕，藏起來等於把唯一的復原入口藏起來。
 */
const CONNECTED_VISIBLE_MS = 3000;

export const useWSStatus = () => {
  const { wsState, reconnect } = useWebSocket();
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (wsState !== 'OPEN') {
      // 連線中或斷線：一直顯示。斷線時它是重連按鈕。
      setVisible(true);
      return undefined;
    }
    // 剛連上時先讓它出現一下當作回饋，再淡出。每次重新連上都會再跑一次，
    // 所以自動重連成功也看得到。
    setVisible(true);
    const id = setTimeout(() => setVisible(false), CONNECTED_VISIBLE_MS);
    return () => clearTimeout(id);
  }, [wsState]);

  const handleClick = useCallback(() => {
    if (wsState !== 'OPEN' && wsState !== 'CONNECTING') {
      reconnect();
    }
  }, [wsState, reconnect]);

  const statusInfo = useMemo((): WSStatusInfo => {
    switch (wsState) {
      case 'OPEN':
        return {
          color: 'green.500',
          textKey: 'wsStatus.connected',
          isDisconnected: false,
          handleClick,
        };
      case 'CONNECTING':
        return {
          color: 'yellow.500',
          textKey: 'wsStatus.connecting',
          isDisconnected: false,
          handleClick,
        };
      default:
        return {
          color: 'red.500',
          textKey: 'wsStatus.clickToReconnect',
          isDisconnected: true,
          handleClick,
        };
    }
  }, [wsState, handleClick]);

  return { ...statusInfo, visible };
};
