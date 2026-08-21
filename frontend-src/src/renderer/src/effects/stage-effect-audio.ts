import type { StageEffectId } from './stage-effect.ts';

type WebkitAudioWindow = Window & {
  webkitAudioContext?: typeof AudioContext;
};

function createNoiseBuffer(context: AudioContext, seconds: number): AudioBuffer {
  const length = Math.ceil(context.sampleRate * seconds);
  const buffer = context.createBuffer(1, length, context.sampleRate);
  const channel = buffer.getChannelData(0);

  for (let index = 0; index < length; index += 1) {
    const envelope = 1 - index / length;
    channel[index] = (Math.random() * 2 - 1) * envelope;
  }

  return buffer;
}

function scheduleTone(
  context: AudioContext,
  destination: AudioNode,
  startAt: number,
  duration: number,
  fromFrequency: number,
  toFrequency: number,
  gainValue: number,
  type: OscillatorType,
): void {
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(fromFrequency, startAt);
  oscillator.frequency.exponentialRampToValueAtTime(
    Math.max(1, toFrequency),
    startAt + duration,
  );
  gain.gain.setValueAtTime(0.0001, startAt);
  gain.gain.exponentialRampToValueAtTime(gainValue, startAt + 0.03);
  gain.gain.exponentialRampToValueAtTime(0.0001, startAt + duration);
  oscillator.connect(gain);
  gain.connect(destination);
  oscillator.start(startAt);
  oscillator.stop(startAt + duration);
}

async function playCinematicBurstSound(intensity: number): Promise<void> {
  const AudioContextClass = window.AudioContext
    || (window as WebkitAudioWindow).webkitAudioContext;
  if (!AudioContextClass) return;

  const context = new AudioContextClass();
  const master = context.createGain();
  const compressor = context.createDynamicsCompressor();
  master.gain.value = Math.min(0.42, 0.24 * intensity);
  master.connect(compressor);
  compressor.connect(context.destination);

  if (context.state === 'suspended') {
    await context.resume();
  }

  const start = context.currentTime + 0.02;

  // Opening pulse, charging shimmer, then the main impact.
  scheduleTone(context, master, start, 0.7, 76, 34, 0.75, 'sine');
  scheduleTone(context, master, start + 1.25, 2.5, 220, 920, 0.14, 'triangle');
  scheduleTone(context, master, start + 3.8, 1.05, 92, 28, 1, 'sine');
  scheduleTone(context, master, start + 3.82, 0.48, 980, 170, 0.18, 'sawtooth');

  const noise = context.createBufferSource();
  const noiseFilter = context.createBiquadFilter();
  const noiseGain = context.createGain();
  noise.buffer = createNoiseBuffer(context, 1.1);
  noiseFilter.type = 'lowpass';
  noiseFilter.frequency.setValueAtTime(1800, start + 3.78);
  noiseFilter.frequency.exponentialRampToValueAtTime(180, start + 4.85);
  noiseGain.gain.setValueAtTime(0.0001, start + 3.78);
  noiseGain.gain.exponentialRampToValueAtTime(0.44, start + 3.82);
  noiseGain.gain.exponentialRampToValueAtTime(0.0001, start + 4.88);
  noise.connect(noiseFilter);
  noiseFilter.connect(noiseGain);
  noiseGain.connect(master);
  noise.start(start + 3.78);

  window.setTimeout(() => {
    context.close().catch(() => undefined);
  }, 6500);
}

async function playCharacterEntranceSound(intensity: number): Promise<void> {
  const AudioContextClass = window.AudioContext
    || (window as WebkitAudioWindow).webkitAudioContext;
  if (!AudioContextClass) return;

  const context = new AudioContextClass();
  const master = context.createGain();
  master.gain.value = Math.min(0.26, 0.15 * intensity);
  master.connect(context.destination);
  if (context.state === 'suspended') {
    await context.resume();
  }

  const start = context.currentTime + 0.02;
  scheduleTone(context, master, start, 0.45, 110, 52, 0.42, 'sine');
  scheduleTone(context, master, start + 0.72, 0.18, 520, 780, 0.18, 'triangle');
  scheduleTone(context, master, start + 0.94, 0.22, 660, 990, 0.16, 'triangle');
  scheduleTone(context, master, start + 1.62, 0.34, 880, 440, 0.2, 'sine');

  window.setTimeout(() => {
    context.close().catch(() => undefined);
  }, 4900);
}

export function playStageEffectSound(
  id: StageEffectId,
  intensity: number,
): void {
  const playback = id === 'characterEntrance'
    ? playCharacterEntranceSound(intensity)
    : playCinematicBurstSound(intensity);

  playback.catch((error) => {
    // Browsers can reject autoplay before the first user interaction.
    console.warn('[StageEffect] Sound playback was blocked:', error);
  });
}
