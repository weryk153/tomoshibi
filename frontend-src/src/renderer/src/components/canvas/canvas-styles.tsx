export const canvasStyles = {
  background: {
    container: {
      position: 'relative',
      width: '100%',
      height: '100%',
      overflow: 'hidden',
      pointerEvents: 'auto',
    },
    image: {
      position: 'absolute',
      top: '0',
      left: '0',
      width: '100%',
      height: '100%',
      objectFit: 'cover',
      zIndex: 1,
    },
    video: {
      position: 'absolute' as const,
      top: '0',
      left: '0',
      width: '100%',
      height: '100%',
      objectFit: 'cover' as const,
      zIndex: 1,
      transform: 'scaleX(-1)' as const,
    },
  },
  canvas: {
    container: {
      position: 'relative',
      width: '100%',
      height: '100%',
      zIndex: '1',
      pointerEvents: 'auto',
    },
  },
  subtitle: {
    container: {
      // 底色是 bg（#0a0a0e）的 78%，跟整個介面同一個冷黑，不是純黑。
      backgroundColor: 'rgba(10, 10, 14, 0.78)',
      padding: '15px 30px',
      borderRadius: '6px',
      minWidth: '60%',
      maxWidth: '95%',
    },
    text: {
      color: 'white',
      fontFamily: 'body',
      fontSize: '1.5rem',
      textAlign: 'center',
      lineHeight: '1.4',
      whiteSpace: 'pre-wrap',
    },
    // 雙語字幕的上行（她唸的原文）：等寬小字、淡一點，視線先落在下行的字幕。
    spoken: {
      color: 'whiteAlpha.700',
      fontFamily: 'mono',
      fontSize: '12px',
      textAlign: 'center',
      lineHeight: '1.4',
      whiteSpace: 'pre-wrap',
      marginBottom: '4px',
    },
  },
  wsStatus: {
    container: {
      position: 'relative',
      // top: '20px',
      // left: '20px',
      zIndex: 2,
      padding: '8px 16px',
      borderRadius: '20px',
      fontSize: '14px',
      fontWeight: 'medium',
      color: 'white',
      transition: 'all 0.2s',
      cursor: 'pointer',
      userSelect: 'none',
      _hover: {
        opacity: 0.8,
      },
    },
  },
};
