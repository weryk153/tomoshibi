import { useState, useEffect, useRef } from 'react';
import { ModelInfo, useLive2DConfig } from '@/context/live2d-config-context';

export const useLive2dSettings = () => {
  const Live2DConfigContext = useLive2DConfig();

  const initialModelInfo: ModelInfo = {
    url: '',
    kScale: 0.5,
    initialXshift: 0,
    initialYshift: 0,
    emotionMap: {},
    scrollToResize: true,
  };

  const [modelInfo, setModelInfoState] = useState<ModelInfo>(
    Live2DConfigContext?.modelInfo || initialModelInfo,
  );
  const [originalModelInfo, setOriginalModelInfo] = useState<ModelInfo>(
    Live2DConfigContext?.modelInfo || initialModelInfo,
  );

  useEffect(() => {
    if (Live2DConfigContext?.modelInfo) {
      if (JSON.stringify(Live2DConfigContext.modelInfo) !== JSON.stringify(originalModelInfo)) {
        setOriginalModelInfo(Live2DConfigContext.modelInfo);
        setModelInfoState(Live2DConfigContext.modelInfo);
      }
    }
  }, [Live2DConfigContext?.modelInfo]);

  // 改了就生效，跟這個分頁下半部的動作設定、以及抽屜裡其他區塊一致。
  // 對這裡的東西即時尤其合理：kScale、位移、指標互動調的都是右邊那個模型，
  // 看得到結果才知道要不要再調。
  const mounted = useRef(false);
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    if (Live2DConfigContext && modelInfo) {
      Live2DConfigContext.setModelInfo(modelInfo);
    }
  }, [modelInfo, Live2DConfigContext]);

  const handleInputChange = (key: keyof ModelInfo, value: ModelInfo[keyof ModelInfo]): void => {
    setModelInfoState((prev) => ({ ...prev, [key]: value }));
  };

  return {
    modelInfo,
    handleInputChange,
  };
};
