import {
  createContext, useCallback, useContext, useState, useMemo,
} from 'react';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';

/**
 * Model emotion mapping interface
 * @interface EmotionMap
 */
interface EmotionMap {
  [key: string]: number | string;
}

/**
 * A single candidate in a hit area's tap-motion list: which (group, index)
 * to consider, and its weight. `index: null` means "pick randomly within
 * the group" — this is the shape produced by the backend's normalisation of
 * legacy `{groupName: weight}` data (see live2d_config_route.py), and it is
 * also the shape `LAppModel.startTapMotion` (WebSDK/src/lappmodel.ts)
 * consumes directly.
 * @interface TapMotionEntry
 */
export interface TapMotionEntry {
  group: string;
  index: number | null;
  weight: number;
}

/**
 * Tap motion mapping interface: hitAreaId -> ordered list of candidates.
 * @interface TapMotionMap
 */
export interface TapMotionMap {
  [key: string]: TapMotionEntry[];
}

/**
 * Live2D model information interface
 * @interface ModelInfo
 */
export interface ModelInfo {
  /** 角色 renderer。缺省為 live2d（舊的 model_dict.json 項目沒有這欄）。 */
  type?: 'live2d' | 'vrm';

  /** VRM 相機：距離與高度（公尺）。Live2D 不用。 */
  camera?: { distance: number; height: number };

  /** Model name */
  name?: string;

  /** Model description */
  description?: string;

  /** Model URL */
  url: string;

  /** Scale factor */
  kScale: number;

  /** Initial X position shift */
  initialXshift: number;

  /** Initial Y position shift */
  initialYshift: number;

  /** Idle motion group name */
  idleMotionGroupName?: string;

  /** Default emotion */
  defaultEmotion?: number | string;

  /** Emotion mapping configuration */
  emotionMap: EmotionMap;

  /** Enable pointer interactivity */
  pointerInteractive?: boolean;

  /** 指標移動時，角色的頭與視線要不要跟著轉（SDK 預設會跟）。 */
  lookAtPointer?: boolean;

  /** Tap motion mapping configuration */
  tapMotions?: TapMotionMap;

  /**
   * LLM-triggerable motion keyword -> resolved group/index mapping.
   * Optional: older `model_dict.json` entries and user-defined models may not
   * have it.
   */
  motionMap?: Record<string, { group: string; index: number } | { clip: string }>;

  /** Enable scroll to resize */
  scrollToResize?: boolean;

  /** Initial scale */
  initialScale?: number;
}

/**
 * Live2D configuration context state interface
 * @interface Live2DConfigState
 */
interface Live2DConfigState {
  modelInfo?: ModelInfo;
  setModelInfo: (info: ModelInfo | undefined) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

/**
 * Default values and constants
 */
const DEFAULT_CONFIG = {
  modelInfo: {
    scrollToResize: true,
  } as ModelInfo | undefined,
  isLoading: false,
};

/**
 * Create the Live2D configuration context
 */
export const Live2DConfigContext = createContext<Live2DConfigState | null>(null);

/**
 * Live2D Configuration Provider Component
 * @param {Object} props - Provider props
 * @param {React.ReactNode} props.children - Child components
 */
export function Live2DConfigProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(DEFAULT_CONFIG.isLoading);

  const [interactionSettings, setInteractionSettings] = useLocalStorage(
    'live2dInteractionSettings',
    { pointerInteractive: true, scrollToResize: true, lookAtPointer: true },
  );

  const [modelInfo, setModelInfoState] = useLocalStorage<ModelInfo | undefined>(
    "modelInfo",
    DEFAULT_CONFIG.modelInfo,
    {
      filter: (value) => (value ? { ...value, url: "" } : value),
    },
  );

  // const [modelInfo, setModelInfoState] = useState<ModelInfo | undefined>(DEFAULT_CONFIG.modelInfo);

  const setModelInfo = useCallback((info: ModelInfo | undefined) => {
    if (!info?.url) {
      setModelInfoState(undefined);
      return;
    }

    const pointerInteractive = info.pointerInteractive
      ?? interactionSettings.pointerInteractive;
    const lookAtPointer = info.lookAtPointer
      ?? interactionSettings.lookAtPointer;
    const scrollToResize = info.scrollToResize
      ?? interactionSettings.scrollToResize;
    if (
      pointerInteractive !== interactionSettings.pointerInteractive
      || lookAtPointer !== interactionSettings.lookAtPointer
      || scrollToResize !== interactionSettings.scrollToResize
    ) {
      setInteractionSettings({ pointerInteractive, scrollToResize, lookAtPointer });
    }

    setModelInfoState({
      ...info,
      kScale: Number(info.kScale || 0.5),
      pointerInteractive,
      lookAtPointer,
      scrollToResize,
    });
  }, [interactionSettings, setInteractionSettings, setModelInfoState]);

  const contextValue = useMemo(
    () => ({
      modelInfo,
      setModelInfo,
      isLoading,
      setIsLoading,
    }),
    [modelInfo, setModelInfo, isLoading, setIsLoading],
  );

  return (
    <Live2DConfigContext.Provider value={contextValue}>
      {children}
    </Live2DConfigContext.Provider>
  );
}

/**
 * Custom hook to use the Live2D configuration context
 * @throws {Error} If used outside of Live2DConfigProvider
 */
export function useLive2DConfig() {
  const context = useContext(Live2DConfigContext);

  if (!context) {
    throw new Error('useLive2DConfig must be used within a Live2DConfigProvider');
  }

  return context;
}

// Export the provider as default
export default Live2DConfigProvider;
