/* eslint-disable no-shadow */
// import { StrictMode } from 'react';
import { Box, Flex, ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { useState, useEffect, useRef } from "react";
import { installAudioUnlock } from "@/utils/audio-unlock";
import { resumeSharedAudioContext } from "@/utils/voice-gain";
// import Canvas from './components/canvas/canvas'; // Likely unused now
import Sidebar from "./components/sidebar/sidebar";
import Footer from "./components/footer/footer";
import { AiStateProvider } from "./context/ai-state-context";
import { Live2DConfigProvider } from "./context/live2d-config-context";
import { SubtitleProvider } from "./context/subtitle-context";
import { BgUrlProvider } from "./context/bgurl-context";
import {
  FOOTER_COLLAPSED_HEIGHT,
  FOOTER_HEIGHT,
  SIDEBAR_COLLAPSED_WIDTH,
  SIDEBAR_WIDTH,
  layoutStyles,
} from "./layout";
import WebSocketHandler from "./services/websocket-handler";
import { CameraProvider } from "./context/camera-context";
import { ChatHistoryProvider } from "./context/chat-history-context";
import { CharacterConfigProvider } from "./context/character-config-context";
import { Toaster } from "./components/ui/tw/toaster";
import { VADProvider } from "./context/vad-context";
import { Live2D } from "./components/canvas/live2d";
import TitleBar from "./components/electron/title-bar";
import { InputSubtitle } from "./components/electron/input-subtitle";
import { ProactiveSpeakProvider } from "./context/proactive-speak-context";
import { ScreenCaptureProvider } from "./context/screen-capture-context";
import { GroupProvider } from "./context/group-context";
import { BrowserProvider } from "./context/browser-context";
import FirstRunWizard from "./components/llm/first-run-wizard";
// eslint-disable-next-line import/no-extraneous-dependencies, import/newline-after-import
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import Scene from "./components/canvas/scene";
import WebSocketStatus from "./components/canvas/ws-status";
import Subtitle from "./components/canvas/subtitle";
import { ModeProvider, useMode } from "./context/mode-context";
import { StageEffectProvider, useStageEffect } from "./context/stage-effect-context";
import { StageEffects } from "./components/canvas/stage-effects";
import { StagePerformanceProvider } from "./context/stage-performance-context";
import { SceneProvider } from "./context/scene-context";

function AppContent(): JSX.Element {
  // iOS／iPadOS 擋掉所有非使用者手勢觸發的播放，而角色的語音是收到訊息後自己播
  // 的——在 iPad 上因此完全沒有聲音，要先點一下螢幕。這裡在第一次手勢時播一段
  // 無聲音訊並喚醒 AudioContext，把頁面標記成「使用者已允許播放」。
  // 只做一次，成功後監聽器自己拆掉。詳見 utils/audio-unlock.ts。
  useEffect(() => installAudioUnlock(resumeSharedAudioContext), []);

  const [showSidebar, setShowSidebar] = useState(true);
  const [isFooterCollapsed, setIsFooterCollapsed] = useState(false);
  const { mode } = useMode();
  const { activeEffect } = useStageEffect();
  const isElectron = window.api !== undefined;
  const live2dContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleResize = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty("--vh", `${vh}px`);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

    
  document.documentElement.style.overflow = 'hidden';
  document.body.style.overflow = 'hidden';
  document.documentElement.style.height = '100%';
  document.body.style.height = '100%';
  document.documentElement.style.position = 'fixed';
  document.body.style.position = 'fixed';
  document.documentElement.style.width = '100%';
  document.body.style.width = '100%';

  // Define base style properties shared across modes/breakpoints
  const live2dBaseStyle = {
    position: "absolute" as const,
    overflow: "hidden",
    transition: "all 0.3s ease-in-out", // Optional transition
    pointerEvents: "auto" as const,
  };

  // Define styles specifically for the "window" mode, using responsive syntax
  const getResponsiveLive2DWindowStyle = (sidebarVisible: boolean) => ({
    ...live2dBaseStyle,
    top: isElectron ? "30px" : "0px",
    height: `calc(100% - ${isElectron ? "30px" : "0px"})`,
    zIndex: 5, // Ensure it's layered correctly below UI but above background
    left: {
      base: "0px", // Column layout (base): Start from left edge
      md: sidebarVisible ? SIDEBAR_WIDTH : SIDEBAR_COLLAPSED_WIDTH,
    },
    width: {
      base: "100%", // Column layout (base): Full width
      md: `calc(100% - ${sidebarVisible ? SIDEBAR_WIDTH : SIDEBAR_COLLAPSED_WIDTH})`,
    },
  });

  // Define styles specifically for the "pet" mode
  const live2dPetStyle = {
    ...live2dBaseStyle,
    top: 0, // Override position for pet mode
    left: 0,
    width: "100vw", // Full viewport
    height: "100vh",
    zIndex: 15, // Higher zIndex for pet mode overlay
  };

  return (
    <>
      <Box
        ref={live2dContainerRef}
        data-stage-effect={activeEffect?.id}
        data-stage-effect-character={activeEffect?.characterId}
        data-stage-effect-scale={activeEffect?.options.scale}
        // Apply styles conditionally based on mode
        // Use the function to get dynamic responsive styles for window mode
        {...(mode === "window"
          ? getResponsiveLive2DWindowStyle(showSidebar)
          : live2dPetStyle)}
      >
        <Live2D />
        <StageEffects />
      </Box>

      {/* Conditional Rendering of Window UI */}
      {mode === "window" && (
        <>
          {isElectron && <TitleBar />}
          {/* Apply styles by spreading */}
          <Flex {...layoutStyles.appContainer}>
            <Box
              {...layoutStyles.sidebar}
              {...(!showSidebar && { width: SIDEBAR_COLLAPSED_WIDTH })}
            >
              <Sidebar
                isCollapsed={!showSidebar}
                onToggle={() => setShowSidebar(!showSidebar)}
              />
            </Box>
            <Box {...layoutStyles.mainContent}>
              <Box {...layoutStyles.canvas}>
                <Scene />
              </Box>
              <Box position="absolute" top="20px" left="20px" zIndex={10}>
                <WebSocketStatus />
              </Box>
              <Box
                position="absolute"
                bottom={`calc(${isFooterCollapsed ? FOOTER_COLLAPSED_HEIGHT : FOOTER_HEIGHT} + 15px)`}
                left="50%"
                transform="translateX(-50%)"
                zIndex={10}
                width="60%"
              >
                <Subtitle />
              </Box>
              <Box
                {...layoutStyles.footer}
                zIndex={10}
                {...(isFooterCollapsed && layoutStyles.collapsedFooter)}
              >
                <Footer
                  isCollapsed={isFooterCollapsed}
                  onToggle={() => setIsFooterCollapsed(!isFooterCollapsed)}
                />
              </Box>
            </Box>
          </Flex>
        </>
      )}

      {/* Conditional Rendering of Pet Mode UI */}
      {mode === "pet" && <InputSubtitle />}
    </>
  );
}

function App(): JSX.Element {
  return (
    <ChakraProvider value={defaultSystem}>
      {/* ModeProvider needs to wrap AppContent to provide mode to getGlobalStyles */}
      <ModeProvider>
        <AppWithGlobalStyles />
      </ModeProvider>
    </ChakraProvider>
  );
}

// New component to access mode for global styles
function AppWithGlobalStyles(): JSX.Element {
  return (
    <>
      <CameraProvider>
        <ScreenCaptureProvider>
          <CharacterConfigProvider>
            <ChatHistoryProvider>
              <AiStateProvider>
                <ProactiveSpeakProvider>
                  <Live2DConfigProvider>
                    <StageEffectProvider>
                      <BgUrlProvider>
                        <SceneProvider>
                          <StagePerformanceProvider>
                            <SubtitleProvider>
                              <VADProvider>
                                <GroupProvider>
                                  <BrowserProvider>
                                    <WebSocketHandler>
                                      <Toaster />
                                      <FirstRunWizard />
                                      <AppContent />
                                    </WebSocketHandler>
                                  </BrowserProvider>
                                </GroupProvider>
                              </VADProvider>
                            </SubtitleProvider>
                          </StagePerformanceProvider>
                        </SceneProvider>
                      </BgUrlProvider>
                    </StageEffectProvider>
                  </Live2DConfigProvider>
                </ProactiveSpeakProvider>
              </AiStateProvider>
            </ChatHistoryProvider>
          </CharacterConfigProvider>
        </ScreenCaptureProvider>
      </CameraProvider>
    </>
  );
}

export default App;
