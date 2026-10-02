// 攝影機場景：背景是你的攝影機畫面（鏡像）。掛上去才開攝影機、換走就關。
import { useEffect, useRef } from "react";
import { useCamera } from "@/context/camera-context";

export default function CameraScene({ opacity }: { opacity: number }): JSX.Element {
  const videoRef = useRef<HTMLVideoElement>(null);
  const {
    backgroundStream, isBackgroundStreaming, startBackgroundCamera, stopBackgroundCamera,
  } = useCamera();

  useEffect(() => {
    startBackgroundCamera().catch((error: unknown) => {
      console.error("Failed to start camera:", error);
    });
    return () => stopBackgroundCamera();
  }, [startBackgroundCamera, stopBackgroundCamera]);

  useEffect(() => {
    if (videoRef.current && backgroundStream) videoRef.current.srcObject = backgroundStream;
  }, [backgroundStream]);

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
        opacity,
        transform: "scaleX(-1)",
        display: isBackgroundStreaming ? "block" : "none",
      }}
    />
  );
}
