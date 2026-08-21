import { createContext, useContext, useState, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { toaster } from "@/components/ui/tw/toaster";
import { isScreenPickerDismissed } from "@/utils/media-error";

interface ScreenCaptureContextType {
  stream: MediaStream | null;
  isStreaming: boolean;
  error: string;
  startCapture: () => Promise<void>;
  stopCapture: () => void;
}

const ScreenCaptureContext = createContext<ScreenCaptureContextType | undefined>(undefined);

export function ScreenCaptureProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState('');

  const startCapture = async () => {
    try {
      let mediaStream: MediaStream;

      if (window.electron) {
        const sourceId = await window.electron.ipcRenderer.invoke('get-screen-capture');

        const displayMediaOptions: DisplayMediaStreamOptions = {
          video: {
            // eslint-disable-next-line @typescript-eslint/ban-ts-comment
            // @ts-expect-error
            mandatory: {
              chromeMediaSource: "desktop",
              chromeMediaSourceId: sourceId,
              minWidth: 1280,
              maxWidth: 1280,
              minHeight: 720,
              maxHeight: 720,
            },
          },
          audio: false,
        };

        mediaStream = await navigator.mediaDevices.getUserMedia(displayMediaOptions);
      } else {
        const displayMediaOptions: DisplayMediaStreamOptions = {
          video: true,
          audio: false,
        };
        mediaStream = await navigator.mediaDevices.getDisplayMedia(displayMediaOptions);
      }

      setStream(mediaStream);
      setIsStreaming(true);
      setError('');
    } catch (err) {
      console.error(err);
      // getDisplayMedia 在「使用者按了取消」和「拒絕權限」時都丟
      // NotAllowedError。取消分享是正常操作，不是失敗——為它跳一個紅色錯誤，
      // 等於告訴使用者他弄壞了什麼，其實他只是改變主意。
      if (isScreenPickerDismissed(err)) {
        setError('');
        return;
      }
      setError(t('error.failedStartScreenCapture'));
      toaster.create({
        title: t('error.failedStartScreenCapture'),
        type: 'error',
        duration: 6000,
      });
    }
  };

  const stopCapture = () => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
      setIsStreaming(false);
    }
  };

  return (
    <ScreenCaptureContext.Provider
      // eslint-disable-next-line react/jsx-no-constructed-context-values
      value={{
        stream,
        isStreaming,
        error,
        startCapture,
        stopCapture,
      }}
    >
      {children}
    </ScreenCaptureContext.Provider>
  );
}

export const useScreenCaptureContext = () => {
  const context = useContext(ScreenCaptureContext);
  if (context === undefined) {
    throw new Error('useScreenCaptureContext must be used within a ScreenCaptureProvider');
  }
  return context;
};
