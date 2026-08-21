import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { SceneModelConfig } from "@/scenes/scene";

interface Scene3DProps {
  sourceUrl: string;
  config: SceneModelConfig;
  opacity: number;
  onError: () => void;
}

interface Scene3DRuntime {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  hemisphere: THREE.HemisphereLight;
  directional: THREE.DirectionalLight;
}

function disposeMaterial(material: THREE.Material): void {
  Object.values(material).forEach((value) => {
    if (value instanceof THREE.Texture) value.dispose();
  });
  material.dispose();
}

function disposeObject(root: THREE.Object3D): void {
  root.traverse((object) => {
    const mesh = object as THREE.Mesh;
    mesh.geometry?.dispose();
    if (Array.isArray(mesh.material)) mesh.material.forEach(disposeMaterial);
    else if (mesh.material) disposeMaterial(mesh.material);
  });
}

export function Scene3D({
  sourceUrl,
  config,
  opacity,
  onError,
}: Scene3DProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<Scene3DRuntime | null>(null);
  const configRef = useRef(config);
  const [error, setError] = useState(false);
  configRef.current = config;

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;
    runtime.scene.background = new THREE.Color(config.backgroundColor);
    runtime.camera.fov = config.cameraFov;
    runtime.camera.position.set(...config.cameraPosition);
    runtime.camera.lookAt(...config.cameraTarget);
    runtime.camera.updateProjectionMatrix();
    runtime.hemisphere.intensity = config.ambientIntensity;
    runtime.directional.intensity = config.directionalIntensity;
    runtime.renderer.domElement.style.opacity = String(opacity);
  }, [config, opacity]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !sourceUrl) return undefined;
    setError(false);
    let disposed = false;
    let frameId = 0;
    let modelRoot: THREE.Object3D | null = null;
    let mixer: THREE.AnimationMixer | null = null;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        powerPreference: "high-performance",
      });
    } catch (rendererError) {
      console.warn("[Scene] WebGL is unavailable:", rendererError);
      setError(true);
      onError();
      return undefined;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1;
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    renderer.domElement.style.opacity = String(opacity);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(config.backgroundColor);
    const camera = new THREE.PerspectiveCamera(
      config.cameraFov,
      Math.max(1, container.clientWidth) / Math.max(1, container.clientHeight),
      0.01,
      4000,
    );
    camera.position.set(...config.cameraPosition);
    camera.lookAt(...config.cameraTarget);

    const hemisphere = new THREE.HemisphereLight(
      0xdbe9ff,
      0x302719,
      config.ambientIntensity,
    );
    const directional = new THREE.DirectionalLight(
      0xffffff,
      config.directionalIntensity,
    );
    directional.position.set(4, 8, 5);
    scene.add(hemisphere, directional);
    runtimeRef.current = {
      renderer,
      scene,
      camera,
      hemisphere,
      directional,
    };

    const resize = () => {
      const width = Math.max(1, container.clientWidth);
      const height = Math.max(1, container.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    new GLTFLoader().load(
      sourceUrl,
      (gltf) => {
        if (disposed) {
          disposeObject(gltf.scene);
          return;
        }
        modelRoot = gltf.scene;
        if (gltf.animations.length > 0) {
          mixer = new THREE.AnimationMixer(gltf.scene);
          gltf.animations.forEach((clip) => mixer?.clipAction(clip).play());
        }
        scene.add(gltf.scene);
      },
      undefined,
      (loadError) => {
        if (!disposed) {
          console.warn("[Scene] Could not load 3D scene:", loadError);
          setError(true);
          onError();
        }
      },
    );

    const clock = new THREE.Clock();
    const animate = () => {
      frameId = window.requestAnimationFrame(animate);
      const delta = Math.min(clock.getDelta(), 0.1);
      mixer?.update(delta);
      if (modelRoot && configRef.current.autoRotate) {
        modelRoot.rotation.y += delta * configRef.current.rotationSpeed;
      }
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      disposed = true;
      observer.disconnect();
      window.cancelAnimationFrame(frameId);
      if (modelRoot) disposeObject(modelRoot);
      mixer?.stopAllAction();
      runtimeRef.current = null;
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, [onError, sourceUrl]);

  return (
    <div
      ref={containerRef}
      data-scene-renderer="three"
      data-scene-error={error || undefined}
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        background: config.backgroundColor,
        display: error ? "none" : "block",
      }}
    />
  );
}

export default Scene3D;
