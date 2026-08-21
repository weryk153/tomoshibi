import type {
  StageEffectId,
  StageEffectScale,
} from './stage-effect.ts';
import type { StageEffectPalette } from './stage-effect-bindings.ts';

export const STAGE_EFFECT_WEBGL_MAX_DPR = 2;
export const STAGE_EFFECT_WEBGL_MAX_DIMENSION = 4096;
export const STAGE_EFFECT_WEBGL_MAX_PIXELS = 4 * 1024 * 1024;

export interface StageEffectWebGLSize {
  width: number;
  height: number;
  dpr: number;
}

export interface StageEffectWebGLScene {
  effectId: StageEffectId;
  scale: StageEffectScale;
  intensity: number;
  durationMs: number;
  palette: StageEffectPalette;
}

interface StageEffectUniforms {
  resolution: WebGLUniformLocation;
  time: WebGLUniformLocation;
  progress: WebGLUniformLocation;
  intensity: WebGLUniformLocation;
  mode: WebGLUniformLocation;
  scale: WebGLUniformLocation;
  primary: WebGLUniformLocation;
  accent: WebGLUniformLocation;
  glow: WebGLUniformLocation;
}

const VERTEX_SHADER = `#version 300 es
in vec2 aPosition;
out vec2 vUv;

void main() {
  vUv = aPosition * 0.5 + 0.5;
  gl_Position = vec4(aPosition, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 outColor;

uniform vec2 uResolution;
uniform float uTime;
uniform float uProgress;
uniform float uIntensity;
uniform float uMode;
uniform float uScale;
uniform vec3 uPrimary;
uniform vec3 uAccent;
uniform vec3 uGlow;

float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float noise21(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash21(i), hash21(i + vec2(1.0, 0.0)), f.x),
    mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0)), f.x),
    f.y
  );
}

float band(float value, float start, float end, float softness) {
  return smoothstep(start - softness, start + softness, value)
    * (1.0 - smoothstep(end - softness, end + softness, value));
}

float ring(vec2 point, float radius, float width) {
  return 1.0 - smoothstep(width, width * 2.2, abs(length(point) - radius));
}

float sparkField(vec2 point, float speed, float density) {
  vec2 grid = point * vec2(density, density * 0.58);
  grid.y -= uTime * speed;
  vec2 cell = floor(grid);
  vec2 local = fract(grid) - 0.5;
  float seed = hash21(cell);
  vec2 offset = vec2(hash21(cell + 11.7), hash21(cell + 37.1)) - 0.5;
  offset *= 0.62;
  float pointLight = 1.0 - smoothstep(0.018, 0.12, length(local - offset));
  float flicker = 0.35 + 0.65 * sin(uTime * (2.0 + seed * 5.0) + seed * 18.0);
  return pointLight * max(0.0, flicker) * step(0.48, seed);
}

void main() {
  vec2 point = vUv * 2.0 - 1.0;
  point.x *= uResolution.x / max(1.0, uResolution.y);

  float entrance = 1.0 - step(0.5, uMode);
  float cinematic = step(0.5, uMode);
  float scaleEnergy = mix(0.48, 1.0, uScale * 0.5);
  float opening = band(uProgress, 0.02, 0.90, 0.06);
  float centerDistance = length(point - vec2(0.0, -0.10));
  float grain = noise21(point * 5.5 + vec2(uTime * 0.12, -uTime * 0.18));

  vec3 color = vec3(0.0);
  float alpha = 0.0;

  float halo = exp(-centerDistance * mix(4.8, 2.4, cinematic));
  halo *= opening * (0.25 + grain * 0.28);
  color += mix(uGlow, uPrimary, cinematic * 0.7) * halo;
  alpha += halo * 0.42;

  float ringGrowth = mix(0.10, 1.12, smoothstep(0.18, 0.74, uProgress));
  float energyRing = ring(point - vec2(0.0, -0.10), ringGrowth, 0.012);
  energyRing += ring(point - vec2(0.0, -0.10), ringGrowth * 0.72, 0.006) * 0.65;
  energyRing *= band(uProgress, 0.16, 0.82, 0.08);
  color += mix(uGlow, uAccent, cinematic) * energyRing;
  alpha += energyRing * 0.72;

  float scanPosition = mix(1.2, -1.2, smoothstep(0.18, 0.76, uProgress));
  float scanBeam = exp(-abs(point.y - scanPosition) * 54.0);
  scanBeam *= entrance * band(uProgress, 0.14, 0.82, 0.06);
  float scanColumns = 0.45 + 0.55 * step(0.55, fract((point.x + 2.0) * 18.0));
  color += uGlow * scanBeam * scanColumns * 1.25;
  alpha += scanBeam * 0.74;

  float angle = atan(point.y + 0.10, point.x);
  float rays = pow(max(0.0, cos(angle * 11.0 + grain * 2.5 + uTime * 0.24)), 22.0);
  rays *= cinematic * band(uProgress, 0.28, 0.84, 0.08);
  rays *= 1.0 - smoothstep(0.10, 1.4, centerDistance);
  color += mix(uPrimary, uAccent, grain) * rays * 0.9;
  alpha += rays * 0.42;

  float impactProgress = clamp((uProgress - 0.66) / 0.18, 0.0, 1.0);
  float shockwave = ring(point - vec2(0.0, -0.08), impactProgress * 1.55, 0.022);
  shockwave *= cinematic * band(uProgress, 0.65, 0.88, 0.025);
  color += uAccent * shockwave * 1.8;
  alpha += shockwave;

  float sparks = sparkField(
    point,
    mix(0.10, 0.42, cinematic),
    mix(10.0, 16.0, uScale * 0.5)
  );
  sparks *= band(uProgress, 0.22, 0.90, 0.10);
  sparks *= mix(0.45, 1.0, cinematic);
  color += mix(uGlow, uAccent, hash21(floor(point * 12.0))) * sparks;
  alpha += sparks * 0.7;

  float edgeFade = 1.0 - smoothstep(0.32, 1.45, length(point * vec2(0.70, 1.0)));
  alpha *= edgeFade * uIntensity * scaleEnergy;
  color *= uIntensity * scaleEnergy;
  alpha = clamp(alpha, 0.0, 0.88);
  color = min(color, vec3(2.4));

  outColor = vec4(color * alpha, alpha);
}
`;

export function resolveStageEffectWebGLSize(
  width: number,
  height: number,
  devicePixelRatio: number,
): StageEffectWebGLSize {
  const safeWidth = Math.max(1, Number.isFinite(width) ? width : 1);
  const safeHeight = Math.max(1, Number.isFinite(height) ? height : 1);
  let dpr = Math.min(
    STAGE_EFFECT_WEBGL_MAX_DPR,
    Math.max(1, Number.isFinite(devicePixelRatio) ? devicePixelRatio : 1),
  );

  const largestDimension = Math.max(safeWidth, safeHeight) * dpr;
  if (largestDimension > STAGE_EFFECT_WEBGL_MAX_DIMENSION) {
    dpr *= STAGE_EFFECT_WEBGL_MAX_DIMENSION / largestDimension;
  }
  const pixelCount = safeWidth * safeHeight * dpr * dpr;
  if (pixelCount > STAGE_EFFECT_WEBGL_MAX_PIXELS) {
    dpr *= Math.sqrt(STAGE_EFFECT_WEBGL_MAX_PIXELS / pixelCount);
  }

  return {
    width: Math.max(1, Math.round(safeWidth * dpr)),
    height: Math.max(1, Math.round(safeHeight * dpr)),
    dpr,
  };
}

export function stageEffectHexToRgb(hex: string): [number, number, number] {
  const normalized = /^#[\da-f]{6}$/i.test(hex) ? hex.slice(1) : 'ffffff';
  return [
    Number.parseInt(normalized.slice(0, 2), 16) / 255,
    Number.parseInt(normalized.slice(2, 4), 16) / 255,
    Number.parseInt(normalized.slice(4, 6), 16) / 255,
  ];
}

function compileShader(
  gl: WebGL2RenderingContext,
  type: number,
  source: string,
): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error('Could not create WebGL shader');
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message = gl.getShaderInfoLog(shader) || 'Unknown shader error';
    gl.deleteShader(shader);
    throw new Error(message);
  }
  return shader;
}

function createProgram(gl: WebGL2RenderingContext): WebGLProgram {
  const vertexShader = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const program = gl.createProgram();
  if (!program) {
    gl.deleteShader(vertexShader);
    gl.deleteShader(fragmentShader);
    throw new Error('Could not create WebGL program');
  }
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);
  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const message = gl.getProgramInfoLog(program) || 'Unknown program link error';
    gl.deleteProgram(program);
    throw new Error(message);
  }
  return program;
}

function requiredUniform(
  gl: WebGL2RenderingContext,
  program: WebGLProgram,
  name: string,
): WebGLUniformLocation {
  const location = gl.getUniformLocation(program, name);
  if (!location) throw new Error(`Missing WebGL uniform: ${name}`);
  return location;
}

export class StageEffectWebGLRenderer {
  private readonly canvas: HTMLCanvasElement;

  private readonly gl: WebGL2RenderingContext;

  private readonly program: WebGLProgram;

  private readonly buffer: WebGLBuffer;

  private readonly vertexArray: WebGLVertexArrayObject;

  private readonly uniforms: StageEffectUniforms;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const gl = canvas.getContext('webgl2', {
      alpha: true,
      antialias: false,
      depth: false,
      powerPreference: 'high-performance',
      premultipliedAlpha: true,
      preserveDrawingBuffer: false,
      stencil: false,
    });
    if (!gl) throw new Error('WebGL2 is unavailable');
    this.gl = gl;
    this.program = createProgram(gl);

    const vertexArray = gl.createVertexArray();
    const buffer = gl.createBuffer();
    if (!vertexArray || !buffer) {
      gl.deleteProgram(this.program);
      throw new Error('Could not allocate WebGL geometry');
    }
    this.vertexArray = vertexArray;
    this.buffer = buffer;

    gl.bindVertexArray(vertexArray);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const position = gl.getAttribLocation(this.program, 'aPosition');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    this.uniforms = {
      resolution: requiredUniform(gl, this.program, 'uResolution'),
      time: requiredUniform(gl, this.program, 'uTime'),
      progress: requiredUniform(gl, this.program, 'uProgress'),
      intensity: requiredUniform(gl, this.program, 'uIntensity'),
      mode: requiredUniform(gl, this.program, 'uMode'),
      scale: requiredUniform(gl, this.program, 'uScale'),
      primary: requiredUniform(gl, this.program, 'uPrimary'),
      accent: requiredUniform(gl, this.program, 'uAccent'),
      glow: requiredUniform(gl, this.program, 'uGlow'),
    };
  }

  resize(width: number, height: number, devicePixelRatio: number): void {
    const size = resolveStageEffectWebGLSize(width, height, devicePixelRatio);
    if (this.canvas.width !== size.width) this.canvas.width = size.width;
    if (this.canvas.height !== size.height) this.canvas.height = size.height;
    this.gl.viewport(0, 0, size.width, size.height);
  }

  render(elapsedMs: number, scene: StageEffectWebGLScene): void {
    const gl = this.gl;
    const progress = Math.min(1, Math.max(0, elapsedMs / scene.durationMs));
    const scale = scene.scale === 'accent' ? 0 : scene.scale === 'scene' ? 1 : 2;
    const primary = stageEffectHexToRgb(scene.palette.primary);
    const accent = stageEffectHexToRgb(scene.palette.accent);
    const glow = stageEffectHexToRgb(scene.palette.glow);

    gl.useProgram(this.program);
    gl.bindVertexArray(this.vertexArray);
    gl.uniform2f(this.uniforms.resolution, this.canvas.width, this.canvas.height);
    gl.uniform1f(this.uniforms.time, elapsedMs / 1000);
    gl.uniform1f(this.uniforms.progress, progress);
    gl.uniform1f(this.uniforms.intensity, scene.intensity);
    gl.uniform1f(this.uniforms.mode, scene.effectId === 'characterEntrance' ? 0 : 1);
    gl.uniform1f(this.uniforms.scale, scale);
    gl.uniform3fv(this.uniforms.primary, primary);
    gl.uniform3fv(this.uniforms.accent, accent);
    gl.uniform3fv(this.uniforms.glow, glow);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  dispose(): void {
    const gl = this.gl;
    gl.bindVertexArray(null);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    gl.deleteBuffer(this.buffer);
    gl.deleteVertexArray(this.vertexArray);
    gl.deleteProgram(this.program);
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
}
