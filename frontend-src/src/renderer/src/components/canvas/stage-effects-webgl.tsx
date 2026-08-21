import {
  memo,
  useEffect,
  useRef,
} from 'react';
import { useStageEffect } from '@/context/stage-effect-context';
import { getStageEffectDuration } from '@/effects/stage-effect';
import { StageEffectWebGLRenderer } from '@/effects/stage-effect-webgl';

function StageEffectsWebGLComponent(): JSX.Element | null {
  const { activeEffect } = useStageEffect();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !activeEffect) return undefined;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (reducedMotion.matches) return undefined;

    let renderer: StageEffectWebGLRenderer;
    try {
      renderer = new StageEffectWebGLRenderer(canvas);
    } catch (error) {
      console.warn('[StageEffect] WebGL layer unavailable; using CSS fallback:', error);
      return undefined;
    }

    const scene = {
      effectId: activeEffect.id,
      scale: activeEffect.options.scale,
      intensity: activeEffect.options.intensity,
      durationMs: getStageEffectDuration(activeEffect.id),
      palette: activeEffect.binding.palette,
    };
    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      renderer.resize(bounds.width, bounds.height, window.devicePixelRatio);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const startedAt = performance.now();
    let animationFrame = 0;
    const render = (now: number) => {
      const elapsedMs = now - startedAt;
      renderer.render(elapsedMs, scene);
      if (elapsedMs < scene.durationMs) {
        animationFrame = window.requestAnimationFrame(render);
      }
    };
    animationFrame = window.requestAnimationFrame(render);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      renderer.dispose();
    };
  }, [activeEffect]);

  if (!activeEffect) return null;

  return (
    <canvas
      ref={canvasRef}
      className="stage-fx__webgl"
      data-stage-fx-webgl={activeEffect.id}
      aria-hidden="true"
    />
  );
}

export const StageEffectsWebGL = memo(StageEffectsWebGLComponent);
