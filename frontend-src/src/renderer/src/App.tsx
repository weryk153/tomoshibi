/* eslint-disable no-shadow */
// import { StrictMode } from 'react';
import { Box, ChakraProvider } from "@chakra-ui/react";
import { tomoshibiSystem } from "./theme/tomoshibi";
import { useState, useEffect } from "react";
import { installAudioUnlock } from "@/utils/audio-unlock";
import { resumeSharedAudioContext } from "@/utils/voice-gain";
// import Canvas from './components/canvas/canvas'; // Likely unused now
import Sidebar, { AppHeader } from "./components/sidebar/sidebar";
import MobileOverlay from "./components/mobile/mobile-overlay";
import { useIsNarrow } from "./hooks/utils/use-is-narrow";
import "./theme/theme-palette.css";
import "./theme/moonlight.css";
import { ThemeProvider } from "./context/theme-context";
import "./theme/moonlight-surfaces.css";
import { AiStateProvider } from "./context/ai-state-context";
import { Live2DConfigProvider } from "./context/live2d-config-context";
import { SubtitleProvider } from "./context/subtitle-context";
import { BgUrlProvider } from "./context/bgurl-context";
import WebSocketHandler from "./services/websocket-handler";
import { CameraProvider } from "./context/camera-context";
import { ChatHistoryProvider } from "./context/chat-history-context";
import { CharacterConfigProvider } from "./context/character-config-context";
import { Toaster } from "./components/ui/tw/toaster";
import { VADProvider } from "./context/vad-context";
import { Avatar } from "./avatar/avatar";
import TitleBar from "./components/electron/title-bar";
import { InputSubtitle } from "./components/electron/input-subtitle";
import { ProactiveSpeakProvider } from "./context/proactive-speak-context";
import { ScreenCaptureProvider } from "./context/screen-capture-context";
import { GroupProvider } from "./context/group-context";
import { BrowserProvider } from "./context/browser-context";
import FirstRunWizard from "./components/llm/first-run-wizard";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import Scene from "./components/canvas/scene";
import StageView from "./components/canvas/stage-view";
import { StreamProvider } from "./context/stream-context";
import { IS_STAGE } from "./services/stage-mode";
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
  const isNarrow = useIsNarrow();
  const { mode } = useMode();
  const { activeEffect } = useStageEffect();
  const isElectron = window.api !== undefined;

  useEffect(() => {
    const handleResize = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty("--vh", `${vh}px`);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // 舞台頁只要角色與字幕；所有 hook 都在上面呼叫過了，這裡提早回傳不違反 hooks 規則。
  if (IS_STAGE) return <StageView />;

    
  document.documentElement.style.overflow = 'hidden';
  document.body.style.overflow = 'hidden';
  document.documentElement.style.height = '100%';
  document.body.style.height = '100%';
  document.documentElement.style.position = 'fixed';
  document.body.style.position = 'fixed';
  document.documentElement.style.width = '100%';
  document.body.style.width = '100%';

  const avatar = (
    <Box
      position="absolute" inset="0" zIndex={5} overflow="hidden"
      data-stage-effect={activeEffect?.id}
      data-stage-effect-character={activeEffect?.characterId}
      data-stage-effect-scale={activeEffect?.options.scale}
    >
      <Avatar />
      <StageEffects />
    </Box>
  );

  if (mode === "pet") return <>{avatar}<InputSubtitle /></>;

  // 手機直式：像 YouTube 直式直播——角色滿版，聊天疊在下方（MobileOverlay）。
  // 不用寬螢幕的上下排版：舞台只剩一小條、角色被切到，使用者看過說比例太怪。
  if (isNarrow) {
    return (
      <>
        {isElectron && <TitleBar />}
        <div className="moonlight-mobile">
          <Scene />
          {avatar}
          <Box position="absolute" top="12px" left="50%" transform="translateX(-50%)" zIndex={12}>
            <WebSocketStatus />
          </Box>
          <MobileOverlay />
        </div>
      </>
    );
  }

  return (
    <>
      {isElectron && <TitleBar />}
      <div className={`moonlight-app${isElectron ? " is-electron" : ""}${showSidebar ? "" : " chat-collapsed"}`}>
        <AppHeader isCollapsed={!showSidebar} onToggle={() => setShowSidebar(!showSidebar)} />
        <main className="moonlight-layout">
          <section className="moonlight-stage-frame">
            <div className="moonlight-stage">
              <Scene />
              {avatar}
              <Box position="absolute" top="16px" left="16px" zIndex={10}>
                <WebSocketStatus />
              </Box>
              <div className="moonlight-subtitle"><Subtitle /></div>
            </div>
          </section>
          <aside className="moonlight-sidebar">
            <Sidebar isCollapsed={!showSidebar} />
          </aside>
        </main>
      </div>
    </>
  );
}

function App(): JSX.Element {
  return (
    <ChakraProvider value={tomoshibiSystem}>
      {/* ModeProvider needs to wrap AppContent to provide mode to getGlobalStyles */}
      <ThemeProvider>
        <ModeProvider>
          <AppWithGlobalStyles />
        </ModeProvider>
      </ThemeProvider>
    </ChakraProvider>
  );
}

// New component to access mode for global styles
function AppWithGlobalStyles(): JSX.Element {
  return (
    <>
      <StreamProvider>
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
                                        {/* 舞台頁不顯示提示框：直播畫面上不能冒出錯誤訊息。 */}
                                        {!IS_STAGE && <Toaster />}
                                        {!IS_STAGE && <FirstRunWizard />}
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
      </StreamProvider>
    </>
  );
}

export default App;
