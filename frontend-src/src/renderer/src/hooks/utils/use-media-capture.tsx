/* eslint-disable operator-assignment */
/* eslint-disable object-shorthand */
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useCamera } from '@/context/camera-context';
import { useScreenCaptureContext } from '@/context/screen-capture-context';
import { toaster } from "@/components/ui/tw/toaster";
import {
  IMAGE_COMPRESSION_QUALITY_KEY, IMAGE_MAX_WIDTH_KEY, loadImageQuality, loadImageMaxWidth,
} from '@/utils/image-settings';
import { FINGERPRINT_SIZE, fingerprintFromRgba, isSamePicture } from '@/utils/picture-fingerprint';

// 每個來源最後一張「有變、真的送去看」的畫面指紋。跟它比而不是跟上一張比：
// 畫面慢慢變（天色、移動）時，一張一張比永遠算「沒變」，描述就一直停在很久以前。
const lastLookedAt = new Map<'camera' | 'screen', number[]>();

function fingerprintOf(bitmap: ImageBitmap): number[] | null {
  const canvas = document.createElement('canvas');
  canvas.width = FINGERPRINT_SIZE.width;
  canvas.height = FINGERPRINT_SIZE.height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return fingerprintFromRgba(ctx.getImageData(0, 0, canvas.width, canvas.height).data);
}

// Add type definition for ImageCapture
declare class ImageCapture {
  constructor(track: MediaStreamTrack);

  grabFrame(): Promise<ImageBitmap>;
}

interface ImageData {
  source: 'camera' | 'screen';
  data: string;
  mime_type: string;
  unchanged: boolean;
}

export function useMediaCapture() {
  const { t } = useTranslation();
  const { stream: cameraStream } = useCamera();
  const { stream: screenStream } = useScreenCaptureContext();

  const getCompressionQuality = useCallback(
    () => loadImageQuality(localStorage.getItem(IMAGE_COMPRESSION_QUALITY_KEY)),
    [],
  );

  const getImageMaxWidth = useCallback(
    () => loadImageMaxWidth(localStorage.getItem(IMAGE_MAX_WIDTH_KEY)),
    [],
  );

  const captureFrame = useCallback(async (stream: MediaStream | null, source: 'camera' | 'screen') => {
    if (!stream) {
      console.warn(`No ${source} stream available`);
      return null;
    }

    const videoTrack = stream.getVideoTracks()[0];
    if (!videoTrack) {
      console.warn(`No video track in ${source} stream`);
      return null;
    }

    const imageCapture = new ImageCapture(videoTrack);
    try {
      const bitmap = await imageCapture.grabFrame();
      const canvas = document.createElement('canvas');
      let { width, height } = bitmap;

      const maxWidth = getImageMaxWidth();
      if (maxWidth > 0 && width > maxWidth) {
        height = (maxWidth / width) * height;
        width = maxWidth;
      }

      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        console.error('Failed to get canvas context');
        return null;
      }

      ctx.drawImage(bitmap, 0, 0, width, height);
      const quality = getCompressionQuality();
      const fingerprint = fingerprintOf(bitmap);
      const unchanged = fingerprint !== null
        && isSamePicture(lastLookedAt.get(source) ?? null, fingerprint);
      if (fingerprint && !unchanged) lastLookedAt.set(source, fingerprint);
      return { data: canvas.toDataURL('image/jpeg', quality), unchanged };
    } catch (error) {
      console.error(`Error capturing ${source} frame:`, error);
      toaster.create({
        title: `${t('error.failedCapture', { source: source })}: ${error}`,
        type: 'error',
        duration: 2000,
      });
      return null;
    }
  }, [t, getCompressionQuality, getImageMaxWidth]);

  const captureAllMedia = useCallback(async () => {
    const images: ImageData[] = [];

    // Capture camera frame
    if (cameraStream) {
      const cameraFrame = await captureFrame(cameraStream, 'camera');
      if (cameraFrame) {
        images.push({
          source: 'camera',
          data: cameraFrame.data,
          mime_type: 'image/jpeg',
          // 跟上一張看過的幾乎一樣：後端沿用上一次的描述，不再叫模型看圖。
          unchanged: cameraFrame.unchanged,
        });
      }
    }

    // Capture screen frame
    if (screenStream) {
      const screenFrame = await captureFrame(screenStream, 'screen');
      if (screenFrame) {
        images.push({
          source: 'screen',
          data: screenFrame.data,
          mime_type: 'image/jpeg',
          // 跟上一張看過的幾乎一樣：後端沿用上一次的描述，不再叫模型看圖。
          unchanged: screenFrame.unchanged,
        });
      }
    }

    console.log("images: ", images);

    return images;
  }, [cameraStream, screenStream, captureFrame]);

  return {
    captureAllMedia,
  };
}
