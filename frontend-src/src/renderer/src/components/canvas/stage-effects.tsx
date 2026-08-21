import { CSSProperties, memo } from 'react';
import { useTranslation } from 'react-i18next';
import { useStageEffect } from '@/context/stage-effect-context';
import { getStageEffectDuration } from '@/effects/stage-effect';
import { StageEffectsWebGL } from './stage-effects-webgl';
import './stage-effects.css';

const PARTICLES = Array.from({ length: 34 }, (_, index) => ({
  angle: (index * 137.5) % 360,
  distance: 22 + ((index * 31) % 72),
  delay: (index % 9) * 0.055,
  size: 2 + (index % 4),
}));

const SHARDS = Array.from({ length: 14 }, (_, index) => ({
  angle: -38 + index * 6.1,
  delay: (index % 5) * 0.035,
  offset: -44 + ((index * 19) % 88),
}));

function StageEffectsComponent(): JSX.Element | null {
  const { t } = useTranslation();
  const { activeEffect } = useStageEffect();

  if (!activeEffect) return null;

  const { options } = activeEffect;
  const { binding } = activeEffect;
  const title = options.title
    || binding.title
    || t(`effects.${activeEffect.id}.title`);
  const subtitle = options.subtitle
    || binding.subtitle
    || t(`effects.${activeEffect.id}.subtitle`);
  const rootStyle = {
    '--fx-duration': `${getStageEffectDuration(activeEffect.id)}ms`,
    '--fx-intensity': options.intensity,
    '--fx-opacity-high': Math.min(1, options.intensity),
    '--fx-opacity-medium': Math.min(0.72, options.intensity * 0.72),
    '--fx-opacity-low': Math.min(0.36, options.intensity * 0.36),
    '--fx-shake-small': `${0.5 * options.intensity}%`,
    '--fx-shake-small-neg': `${-0.5 * options.intensity}%`,
    '--fx-shake-medium': `${0.7 * options.intensity}%`,
    '--fx-shake-large': `${0.8 * options.intensity}%`,
    '--fx-shake-large-neg': `${-0.8 * options.intensity}%`,
    '--fx-gold': binding.palette.accent,
    '--fx-amber': binding.palette.glow,
    '--fx-glow': binding.palette.glow,
    '--fx-crimson': binding.palette.primary,
    '--fx-void': binding.palette.void,
  } as CSSProperties;

  return (
    <div
      key={activeEffect.sequence}
      className={`stage-fx stage-fx--${activeEffect.id === 'characterEntrance' ? 'character-entrance' : 'cinematic-burst'} stage-fx--scale-${options.scale}`}
      style={rootStyle}
      aria-hidden="true"
    >
      <div className="stage-fx__void" />
      <div className="stage-fx__vignette" />
      <div className="stage-fx__speed-lines" />
      <StageEffectsWebGL />

      <div className="stage-fx__cutin">
        <div className="stage-fx__cutin-rule" />
        <div className="stage-fx__cutin-copy">
          <span className="stage-fx__eyebrow">{title}</span>
          <strong>{subtitle}</strong>
        </div>
      </div>

      <div className="stage-fx__sigil" aria-hidden="true">
        <div className="stage-fx__ring stage-fx__ring--outer" />
        <div className="stage-fx__ring stage-fx__ring--middle" />
        <div className="stage-fx__ring stage-fx__ring--inner" />
        <div className="stage-fx__sigil-core">✦</div>
      </div>

      <div className="stage-fx__particles">
        {PARTICLES.map((particle, index) => (
          <i
            // Static deterministic particles; index is stable for the preset.
            // eslint-disable-next-line react/no-array-index-key
            key={index}
            style={{
              '--particle-angle': `${particle.angle}deg`,
              '--particle-distance': `${particle.distance}vmin`,
              '--particle-distance-accent': `${particle.distance * 0.35}vmin`,
              '--particle-delay': `${particle.delay}s`,
              '--particle-size': `${particle.size}px`,
            } as CSSProperties}
          />
        ))}
      </div>

      <div className="stage-fx__shards">
        {SHARDS.map((shard, index) => (
          <i
            // Static deterministic shards; index is stable for the preset.
            // eslint-disable-next-line react/no-array-index-key
            key={index}
            style={{
              '--shard-angle': `${shard.angle}deg`,
              '--shard-delay': `${shard.delay}s`,
              '--shard-offset': `${shard.offset}vmin`,
            } as CSSProperties}
          />
        ))}
      </div>

      <div className="stage-fx__slash stage-fx__slash--one" />
      <div className="stage-fx__slash stage-fx__slash--two" />
      <div className="stage-fx__impact" />
      <div className="stage-fx__flash stage-fx__flash--opening" />
      <div className="stage-fx__flash stage-fx__flash--impact" />
    </div>
  );
}

export const StageEffects = memo(StageEffectsComponent);
