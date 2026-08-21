import assert from "node:assert/strict";
import test from "node:test";
import { inferSceneAssetType, validateSceneAsset } from "./scene-asset.ts";

const MB = 1024 * 1024;

test("圖片、影片與 GLB 可依 MIME 或副檔名辨識", () => {
  assert.equal(
    inferSceneAssetType({ name: "room.png", size: 1, type: "" }),
    "image",
  );
  assert.equal(
    inferSceneAssetType({ name: "rain.bin", size: 1, type: "video/webm" }),
    "video",
  );
  assert.equal(
    inferSceneAssetType({ name: "lab.GLB", size: 1, type: "" }),
    "model3d",
  );
});

test("本機 3D 場景只接受單檔 GLB，避免 GLTF 遺失外部貼圖", () => {
  assert.equal(
    validateSceneAsset(
      { name: "lab.gltf", size: 10, type: "model/gltf+json" },
      "model3d",
    ),
    "unsupported",
  );
  assert.equal(
    validateSceneAsset(
      { name: "lab.glb", size: 10, type: "model/gltf-binary" },
      "model3d",
    ),
    null,
  );
  assert.equal(
    validateSceneAsset({
      name: "unknown.bin",
      size: 10,
      type: "application/octet-stream",
    }),
    "unsupported",
  );
});

test("不同種類有各自容量上限，空檔一律拒絕", () => {
  assert.equal(
    validateSceneAsset({ name: "x.png", size: 0, type: "image/png" }),
    "empty",
  );
  assert.equal(
    validateSceneAsset({ name: "x.png", size: 25 * MB, type: "image/png" }),
    "tooLarge",
  );
  assert.equal(
    validateSceneAsset({ name: "x.mp4", size: 200 * MB, type: "video/mp4" }),
    null,
  );
});
