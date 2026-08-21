/* eslint-disable import/no-extraneous-dependencies */
import {
  Box,
  Button,
  Heading,
  HStack,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";
import { createListCollection } from "@ark-ui/react/collection";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Field, TextInput } from '@/components/ui/tw/primitives';
import { toaster } from "@/components/ui/tw/toaster";
import { useScene } from "@/context/scene-context";
import { useWebSocket } from "@/context/websocket-context";
import {
  CURRENT_BACKGROUND_SCENE_ID,
  SCENE_FITS,
  SCENE_TYPES,
  ScenePreset,
  SceneType,
} from "@/scenes/scene";
import type { SceneAssetError } from "@/scenes/scene-asset";
import { NumberField, SelectField, SwitchField } from "./common";
import { settingStyles } from "./setting-styles";

function sceneAccept(type: SceneType): string {
  if (type === "image") return "image/*,.jpg,.jpeg,.png,.gif,.webp,.avif";
  if (type === "video") return "video/*,.mp4,.webm,.mov,.m4v,.ogv";
  return ".glb,model/gltf-binary";
}

function Scenes(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const {
    scenes,
    activeScene,
    activateScene,
    createScene,
    updateScene,
    deleteScene,
    importSceneAsset,
  } = useScene();
  const [selectedId, setSelectedId] = useState(activeScene.id);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [installedLive2DModels, setInstalledLive2DModels] = useState<
    { name: string; url: string }[]
  >([]);
  const selected = scenes.find((scene) => scene.id === selectedId) || scenes[0];
  const sceneLabel = (scene: ScenePreset) =>
    scene.id === CURRENT_BACKGROUND_SCENE_ID
      ? t("settings.scenes.currentBackground")
      : scene.name;

  useEffect(() => {
    if (!scenes.some((scene) => scene.id === selectedId)) {
      setSelectedId(CURRENT_BACKGROUND_SCENE_ID);
    }
  }, [scenes, selectedId]);

  useEffect(() => setPendingDelete(false), [selectedId]);

  useEffect(() => {
    let alive = true;
    fetch(`${baseUrl}/live2d-models/info`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!alive || !Array.isArray(data?.characters)) return;
        setInstalledLive2DModels(
          data.characters
            .filter(
              (item: unknown) =>
                item &&
                typeof item === "object" &&
                typeof (item as { model_path?: unknown }).model_path ===
                  "string",
            )
            .map((item: { name?: string; model_path: string }) => ({
              name: String(item.name || item.model_path),
              url: `${baseUrl}/${item.model_path.replace(/^\/+/, "")}`,
            })),
        );
      })
      .catch(() => {
        if (alive) setInstalledLive2DModels([]);
      });
    return () => {
      alive = false;
    };
  }, [baseUrl]);

  const typeCollection = useMemo(
    () =>
      createListCollection({
        items: SCENE_TYPES.map((value) => ({
          value: String(value),
          label: t(`settings.scenes.types.${value}`),
        })),
      }),
    [t],
  );
  const fitCollection = useMemo(
    () =>
      createListCollection({
        items: SCENE_FITS.map((value) => ({
          value: String(value),
          label: t(`settings.scenes.fits.${value}`),
        })),
      }),
    [t],
  );
  const installedLive2DCollection = useMemo(
    () =>
      createListCollection({
        items: installedLive2DModels.map((model) => ({
          value: model.url,
          label: model.name,
        })),
      }),
    [installedLive2DModels],
  );

  const updateSelected = (update: Partial<ScenePreset>) => {
    if (!selected.builtin) updateScene(selected.id, update);
  };

  const addScene = (type: SceneType) => {
    const id = createScene(type);
    setSelectedId(id);
  };

  const showAssetError = (error: SceneAssetError | "saveFailed") => {
    toaster.create({
      title: t(`settings.scenes.assetErrors.${error}`),
      type: "error",
      duration: 2400,
    });
  };

  const importAsset = async (file: File | undefined) => {
    if (!file || selected.builtin) return;
    setIsImporting(true);
    try {
      const error = await importSceneAsset(selected.id, file);
      if (error) showAssetError(error);
      else {
        toaster.create({
          title: t("settings.scenes.assetSaved"),
          type: "success",
          duration: 1800,
        });
      }
    } catch {
      showAssetError("saveFailed");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Stack {...settingStyles.common.container} maxW="none">
      <Heading size="sm">{t("settings.scenes.title")}</Heading>
      <Text fontSize="sm" color="fg.muted">
        {t("settings.scenes.description")}
      </Text>

      <HStack flexWrap="wrap">
        <Button size="sm" onClick={() => addScene("image")}>
          {t("settings.scenes.addImage")}
        </Button>
        <Button size="sm" onClick={() => addScene("video")}>
          {t("settings.scenes.addVideo")}
        </Button>
        <Button size="sm" onClick={() => addScene("live2d")}>
          {t("settings.scenes.addLive2d")}
        </Button>
        <Button size="sm" onClick={() => addScene("model3d")}>
          {t("settings.scenes.add3d")}
        </Button>
      </HStack>

      <Stack gap="2">
        {scenes.map((scene) => (
          <Box
            key={scene.id}
            p="3"
            borderWidth="1px"
            borderColor={
              selected.id === scene.id ? "blue.400" : "whiteAlpha.200"
            }
            borderRadius="md"
          >
            <HStack justify="space-between" flexWrap="wrap" gap="2">
              <Button
                size="sm"
                variant="ghost"
                flex="1"
                justifyContent="flex-start"
                onClick={() => setSelectedId(scene.id)}
              >
                {sceneLabel(scene)}
                <Text as="span" fontSize="xs" color="fg.muted">
                  {t(`settings.scenes.types.${scene.type}`)}
                </Text>
              </Button>
              {activeScene.id === scene.id && (
                <Text fontSize="xs" color="green.300">
                  {t("settings.scenes.active")}
                </Text>
              )}
              <Button
                size="xs"
                colorPalette="blue"
                variant={activeScene.id === scene.id ? "solid" : "outline"}
                onClick={() => activateScene(scene.id)}
              >
                {t("settings.scenes.use")}
              </Button>
            </HStack>
          </Box>
        ))}
      </Stack>

      <Box
        p="4"
        borderWidth="1px"
        borderColor="whiteAlpha.200"
        borderRadius="lg"
      >
        <Stack gap="3">
          <Heading size="xs">{sceneLabel(selected)}</Heading>
          {selected.builtin ? (
            <Text fontSize="sm" color="fg.muted">
              {t("settings.scenes.currentBackgroundHelp")}
            </Text>
          ) : (
            <>
              <Field label={t("settings.scenes.name")}>
                <TextInput
                  value={selected.name}
                  onChange={(event) =>
                    updateSelected({ name: event.target.value })
                  }
                />
              </Field>
              <SelectField
                label={t("settings.scenes.type")}
                value={[selected.type]}
                onChange={(value) =>
                  updateSelected({
                    type: (value[0] || "image") as SceneType,
                    assetKey: undefined,
                    assetFileName: undefined,
                    assetVersion: undefined,
                  })
                }
                collection={typeCollection}
                placeholder={t("settings.scenes.type")}
              />
              {selected.type !== "live2d" && (
                <Field
                  label={t("settings.scenes.asset")}
                  help={
                    selected.type === "model3d"
                      ? t("settings.scenes.glbHelp")
                      : t("settings.scenes.assetHelp")
                  }
                >
                  <Input
                    type="file"
                    size="sm"
                    accept={sceneAccept(selected.type)}
                    disabled={isImporting}
                    onChange={(event) => {
                      importAsset(event.currentTarget.files?.[0]);
                      event.currentTarget.value = "";
                    }}
                  />
                  {selected.assetFileName && (
                    <Text mt="1" fontSize="xs" color="cyan.300">
                      {selected.assetFileName}
                    </Text>
                  )}
                </Field>
              )}
              {selected.type === "live2d" &&
                installedLive2DCollection.items.length > 0 && (
                  <SelectField
                    label={t("settings.scenes.installedLive2d")}
                    value={
                      installedLive2DCollection.items.some(
                        (item) => item.value === selected.sourceUrl,
                      )
                        ? [selected.sourceUrl]
                        : []
                    }
                    onChange={(value) =>
                      updateSelected({
                        sourceUrl: value[0] || "",
                        assetKey: undefined,
                        assetFileName: undefined,
                        assetVersion: undefined,
                      })
                    }
                    collection={installedLive2DCollection}
                    placeholder={t("settings.scenes.selectLive2d")}
                  />
                )}
              <Field
                label={t("settings.scenes.sourceUrl")}
                help={
                  selected.type === "model3d"
                    ? t("settings.scenes.url3dHelp")
                    : selected.type === "live2d"
                      ? t("settings.scenes.urlLive2dHelp")
                      : undefined
                }
              >
                <TextInput
                  placeholder={t("settings.scenes.sourceUrlPlaceholder")}
                  value={selected.sourceUrl}
                  onChange={(event) =>
                    updateSelected({
                      sourceUrl: event.target.value,
                      assetKey: undefined,
                      assetFileName: undefined,
                      assetVersion: undefined,
                    })
                  }
                />
              </Field>
              {selected.type !== "model3d" && selected.type !== "live2d" && (
                <SelectField
                  label={t("settings.scenes.fit")}
                  value={[selected.fit]}
                  onChange={(value) =>
                    updateSelected({
                      fit: (value[0] || "cover") as ScenePreset["fit"],
                    })
                  }
                  collection={fitCollection}
                  placeholder={t("settings.scenes.fit")}
                />
              )}
              <NumberField
                label={t("settings.scenes.opacity")}
                value={Math.round(selected.opacity * 100)}
                min={10}
                max={100}
                step={5}
                onChange={(value) =>
                  updateSelected({ opacity: Number(value) / 100 })
                }
              />
              <NumberField
                label={t("settings.scenes.transition")}
                value={selected.transitionMs}
                min={0}
                max={5000}
                step={100}
                onChange={(value) =>
                  updateSelected({ transitionMs: Number(value) })
                }
              />
              {selected.type === "video" && (
                <>
                  <SwitchField
                    label={t("settings.scenes.loop")}
                    checked={selected.loop}
                    onChange={(loop) => updateSelected({ loop })}
                  />
                  <SwitchField
                    label={t("settings.scenes.muted")}
                    checked={selected.muted}
                    onChange={(muted) => updateSelected({ muted })}
                  />
                </>
              )}
              {selected.type === "live2d" && (
                <>
                  <NumberField
                    label={t("settings.scenes.live2dScale")}
                    value={selected.live2d.scale}
                    min={0.05}
                    max={10}
                    step={0.05}
                    onChange={(value) =>
                      updateSelected({
                        live2d: {
                          ...selected.live2d,
                          scale: Number(value),
                        },
                      })
                    }
                  />
                  <NumberField
                    label={t("settings.scenes.live2dX")}
                    value={selected.live2d.x}
                    min={-5}
                    max={5}
                    step={0.05}
                    onChange={(value) =>
                      updateSelected({
                        live2d: { ...selected.live2d, x: Number(value) },
                      })
                    }
                  />
                  <NumberField
                    label={t("settings.scenes.live2dY")}
                    value={selected.live2d.y}
                    min={-5}
                    max={5}
                    step={0.05}
                    onChange={(value) =>
                      updateSelected({
                        live2d: { ...selected.live2d, y: Number(value) },
                      })
                    }
                  />
                  <NumberField
                    label={t("settings.scenes.live2dParallax")}
                    value={Math.round(selected.live2d.parallax * 100)}
                    min={0}
                    max={100}
                    step={5}
                    onChange={(value) =>
                      updateSelected({
                        live2d: {
                          ...selected.live2d,
                          parallax: Number(value) / 100,
                        },
                      })
                    }
                  />
                </>
              )}
              {selected.type === "model3d" && (
                <>
                  <Field label={t("settings.scenes.backgroundColor")}>
                    <Input
                      type="color"
                      value={selected.model.backgroundColor}
                      onChange={(event) =>
                        updateSelected({
                          model: {
                            ...selected.model,
                            backgroundColor: event.target.value,
                          },
                        })
                      }
                    />
                  </Field>
                  <NumberField
                    label={t("settings.scenes.cameraFov")}
                    value={selected.model.cameraFov}
                    min={10}
                    max={100}
                    step={1}
                    onChange={(value) =>
                      updateSelected({
                        model: { ...selected.model, cameraFov: Number(value) },
                      })
                    }
                  />
                  {(["x", "y", "z"] as const).map((axis, index) => (
                    <NumberField
                      key={`camera-${axis}`}
                      label={t("settings.scenes.cameraPosition", {
                        axis: axis.toUpperCase(),
                      })}
                      value={selected.model.cameraPosition[index]}
                      min={-1000}
                      max={1000}
                      step={0.1}
                      onChange={(value) => {
                        const cameraPosition = [
                          ...selected.model.cameraPosition,
                        ] as [number, number, number];
                        cameraPosition[index] = Number(value);
                        updateSelected({
                          model: { ...selected.model, cameraPosition },
                        });
                      }}
                    />
                  ))}
                  {(["x", "y", "z"] as const).map((axis, index) => (
                    <NumberField
                      key={`target-${axis}`}
                      label={t("settings.scenes.cameraTarget", {
                        axis: axis.toUpperCase(),
                      })}
                      value={selected.model.cameraTarget[index]}
                      min={-1000}
                      max={1000}
                      step={0.1}
                      onChange={(value) => {
                        const cameraTarget = [
                          ...selected.model.cameraTarget,
                        ] as [number, number, number];
                        cameraTarget[index] = Number(value);
                        updateSelected({
                          model: { ...selected.model, cameraTarget },
                        });
                      }}
                    />
                  ))}
                  <NumberField
                    label={t("settings.scenes.ambientLight")}
                    value={selected.model.ambientIntensity}
                    min={0}
                    max={10}
                    step={0.1}
                    onChange={(value) =>
                      updateSelected({
                        model: {
                          ...selected.model,
                          ambientIntensity: Number(value),
                        },
                      })
                    }
                  />
                  <NumberField
                    label={t("settings.scenes.directionalLight")}
                    value={selected.model.directionalIntensity}
                    min={0}
                    max={20}
                    step={0.1}
                    onChange={(value) =>
                      updateSelected({
                        model: {
                          ...selected.model,
                          directionalIntensity: Number(value),
                        },
                      })
                    }
                  />
                  <SwitchField
                    label={t("settings.scenes.autoRotate")}
                    checked={selected.model.autoRotate}
                    onChange={(autoRotate) =>
                      updateSelected({
                        model: { ...selected.model, autoRotate },
                      })
                    }
                  />
                  <NumberField
                    label={t("settings.scenes.rotationSpeed")}
                    value={selected.model.rotationSpeed}
                    min={-3}
                    max={3}
                    step={0.05}
                    onChange={(value) =>
                      updateSelected({
                        model: {
                          ...selected.model,
                          rotationSpeed: Number(value),
                        },
                      })
                    }
                  />
                </>
              )}
              {pendingDelete ? (
                <HStack>
                  <Text fontSize="xs" color="red.300">
                    {t("settings.scenes.confirmDelete")}
                  </Text>
                  <Button
                    size="xs"
                    colorPalette="red"
                    onClick={() => {
                      deleteScene(selected.id);
                      setSelectedId(CURRENT_BACKGROUND_SCENE_ID);
                    }}
                  >
                    {t("settings.scenes.delete")}
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => setPendingDelete(false)}
                  >
                    {t("common.cancel")}
                  </Button>
                </HStack>
              ) : (
                <Button
                  size="sm"
                  colorPalette="red"
                  variant="outline"
                  onClick={() => setPendingDelete(true)}
                >
                  {t("settings.scenes.delete")}
                </Button>
              )}
            </>
          )}
        </Stack>
      </Box>
    </Stack>
  );
}

export default Scenes;
