# Add your own VRM character

**Scenario:** You have (or want to build) a VRM 3D model and you want to use it as your
character's appearance in Tomoshibi, as an alternative to a Live2D model.

## What you need

A **VRM file** — `.vrm` is a binary glTF (`.glb`) container with a VRM extension, so any
VRoid Studio / Blender VRM export works. Optionally, one or more **`.vrma` motion clips**
(the VRM animation format) to go alongside it.

VRM 1.0 files are strongly recommended: Tomoshibi reads a VRM 1.0 file's
`VRMC_vrm.expressions` block to know what facial expressions it has, and only maps a
keyword to an expression when the standard preset actually exists in the file (see
[Expression and motion mapping](#expression-and-motion-mapping) below). A VRM 0.x file
still loads and renders, but Tomoshibi cannot enumerate its expressions, so it only gets
a bare `{"neutral": "neutral"}` mapping and a warning in the server log — everything else
must be added by hand.

## How Tomoshibi finds your model (verified from the code)

Same auto-scanner pattern as Live2D, implemented in
`src/open_llm_vtuber/vrm_models.py` (`scan_and_register_vrm`):

- Whenever the **Character Manager** loads the skin list (`GET /api/live2d-skins`),
  Tomoshibi also scans the `vrm-models/` folder.
- For every **top-level sub-folder** of `vrm-models/` that has a `*.vrm` file directly
  inside it (not nested), that folder is a usable model — **the folder name is the model
  name**, exactly like Live2D.
- If a folder has more than one `.vrm` file at its top level, Tomoshibi picks the
  alphabetically first one.
- Any folder found that **isn't registered yet** is **auto-registered** into
  `model_dict.json`, reading the `.vrm` file to build a default expression map and
  scanning `motions/*.vrma` to build a default motion map (see below). This write is
  automatic and only happens when something new is found.

So: drop a folder in, open the Character Manager, and it appears in the skin dropdown —
no hand-editing required to get started. `vrm-models/` itself is gitignored, so nothing
you put there gets committed to the repo.

## Step-by-step

### 1. Drop your model into `vrm-models/`

```
vrm-models/
  my_character/
    my_character.vrm
    motions/
      idle.vrma
      wave.vrma
      nod.vrma
    thumbnail.png
```

- The `.vrm` file's own name doesn't matter — only the **folder name** becomes the model
  name, and the scanner just takes the first `.vrm` it finds at the folder's top level.
- `motions/` is optional. Inside it, `idle.vrma` is a **reserved name**: if present, it
  plays as the looping idle animation instead of the built-in procedural sway. Every
  *other* `.vrma` file in `motions/` becomes an LLM-triggerable one-shot clip, keyed by
  its filename (without `.vrma`) as the default keyword.
- `thumbnail.png` / `.jpg` / `.jpeg` / `.webp` is optional, same as Live2D — see
  [Give your character a skin-picker thumbnail](#give-your-character-a-skin-picker-thumbnail-optional)
  below.

### 2. Let Tomoshibi scan it (automatic)

Open Tomoshibi → **Settings → Character Manager**, and open the **Appearance** dropdown
when creating or editing a character — opening the manager triggers the scan, which
auto-registers your new folder. Your model appears in the same dropdown as Live2D
skins, listed by its folder name.

The auto-registered `model_dict.json` entry looks like this (this is a real example, not
a template — the shape is fixed):

```json
{
  "name": "kurisu_vrm",
  "type": "vrm",
  "description": "自動偵測並註冊的 VRM 模型",
  "url": "/vrm-models/kurisu_vrm/kurisu_vrm.vrm",
  "kScale": 1,
  "initialXshift": 0,
  "initialYshift": 0,
  "emotionMap": { "neutral": "neutral", "joy": "happy" },
  "tapMotions": {},
  "motionMap": { "wave": { "clip": "wave", "label": null } },
  "camera": { "distance": 1.6, "height": 1.35 }
}
```

(`kScale` / `initialXshift` / `initialYshift` / `tapMotions` are carried over from the
Live2D entry shape for type-compatibility but are not used for VRM models.)

### 3. Create or edit a character that uses it

Same as Live2D: in the Character Manager, set **Appearance** to your VRM model (its
folder name) — the field is still called `live2d_model_name` in the character YAML, it
just now also accepts VRM model names. Set persona and voice, save, and switch to that
character to apply it.

## Expression and motion mapping

### `emotionMap` — facial expressions

`emotionMap` maps a Tomoshibi emotion keyword to a **VRM expression name** (a string, not
an index like Live2D). The scanner only auto-fills a keyword when the file actually has
the matching standard preset:

| Tomoshibi keyword | VRM 1.0 preset |
|---|---|
| `neutral` | `neutral` |
| `joy` | `happy` |
| `anger` | `angry` |
| `sadness` | `sad` |
| `surprise` | `surprised` |

`relaxed` has no common preset counterpart and is never auto-filled. Any custom
expression your `.vrm` file defines (beyond the five standard presets) can be mapped by
hand by editing `emotionMap` in `model_dict.json` — use the expression name exactly as
authored in the file.

### `motionMap` — one-shot motion clips

`motionMap` maps a keyword to `{ "clip": "<file stem>", "label": "<description>" }`. The
auto-registered entry sets `clip` to each `motions/*.vrma` file's stem (minus `idle`) and
leaves `label` as `null`.

**Add a label.** The label is the only thing the LLM sees when deciding which motion to
trigger — the keyword alone isn't shown to it. An entry with `label: null` is unusable for
the LLM to pick deliberately. Watch the clip, then edit `model_dict.json`:

```json
"motionMap": { "wave": { "clip": "wave", "label": "揮手打招呼" } }
```

The keyword itself is what the LLM writes as `[keyword]` in its reply to trigger the
clip — same mechanism as Live2D's `[keyword]` motions. To change a clip's keyword,
rename the `.vrma` file (the scanner keys new entries off the filename); to relabel an
existing mapping, edit the JSON directly.

`PUT /api/live2d/model-config/{name}` (used when saving from the settings page)
validates both maps against what the `.vrm` file and `motions/` folder actually contain
— an unknown clip or expression name is rejected.

## Camera

`camera.distance` and `camera.height`, both in meters, position the VRM camera; it looks
at the point `(0, height, 0)`. Defaults are `distance: 1.6`, `height: 1.35`. Adjust these
in `model_dict.json` if the model is framed too close/far or too high/low.

## Runtime behavior (what you can expect once it's loaded)

- **Lip sync** drives off the TTS-generated WAV directly (no Web Audio API involved).
- **Expressions** cross-fade in/out over 0.2 s.
- **Blinking** is automatic (a built-in blink state machine), independent of your
  `emotionMap`.
- **Gaze**: if the Live2D "look at pointer" setting is on, the character's eyes follow
  the mouse pointer; if it's off, the character looks at the camera.
- **Idle**: `motions/idle.vrma` plays looped if present; otherwise a subtle procedural
  sway is used instead.
- **LLM-triggered motions**: a `[keyword]` from `motionMap` crossfades into that clip and
  back to idle when it finishes.
- **Load failure**: if the `.vrm` file fails to load, Tomoshibi shows a toast and the
  conversation continues without an avatar — it doesn't block the chat.

## Settings page

For a VRM model, the **Appearance** tab in the Character Manager's model settings shows a
**read-only summary** of the model's clips, expressions, and current keyword mappings
(there is no VRM equivalent of Live2D's motion/hit-area editor UI). To change something:

- **Rename a `.vrma` file** to change which keyword triggers it.
- **Edit `model_dict.json` by hand** to change a motion's label or an expression's
  keyword mapping.

## Give your character a skin-picker thumbnail (optional)

Identical mechanism to Live2D: drop `thumbnail.png` / `.jpg` / `.jpeg` / `.webp` into the
model's folder (alongside the `.vrm` file), reopen the Character Manager to rescan, and
the picker shows it. Skip it and the picker shows a placeholder instead — everything
else still works.

## Where to get a model

There are two candidate pipelines for producing a VRM model; **which one Tomoshibi
recommends is still undecided** — a spike is planned to settle it. Both produce a valid
`.vrm` file; the tradeoff is how much manual facial-rig work is required afterward.

1. **VRoid Studio → export VRM 1.0.** The straightforward path: VRoid Studio exports VRM
   1.0 directly, and the standard expression presets (`neutral`, `happy`, `angry`,
   `sad`, `surprised`, blink, and the `aa`/`ih`/`ou`/`ee`/`oh` mouth shapes used for lip
   sync) come pre-authored — no extra rigging work needed. You can optionally refine the
   exported model further in Blender using the
   [VRM Add-on for Blender](https://github.com/saturday06/VRM-Add-on-for-Blender)
   (saturday06, MIT license).
2. **Image-to-3D generation → Blender → VRM export.** Generate a mesh from a reference
   image with a tool that includes auto-rigging (e.g. Meshy or Tripo), or with
   Hunyuan3D / Hyper3D, then bring it into Blender and export with the same VRM Add-on.
   The body rig comes out usable, but **these generators do not produce VRM facial
   blendshapes** — the `aa` mouth shape used for lip sync, blink, and the emotion
   expressions all have to be authored by hand in Blender before export. This is
   meaningfully more manual work than pipeline 1, which is why the spike exists.

### Motion sources for `.vrma` clips

- Free sample `.vrma` motions distributed on VRoid Hub (originally sourced from pixiv).
- [Mixamo](https://www.mixamo.com/) motion capture clips, retargeted and exported as
  `.vrma` via the Blender VRM Add-on.

## v1 limitations

- **Window mode only** — VRM characters don't currently support Tomoshibi's pet
  (desktop overlay) mode.
- **No tap/hit areas** — clicking on the character does nothing (Live2D's tap-triggered
  reactions have no VRM equivalent yet).
- **Settings are read-only** — see [Settings page](#settings-page) above; there is no
  in-app editor for clips or expression mappings, only `model_dict.json`.
- **No shadows or image-based lighting** — the VRM canvas renders without a shadow pass
  or environment lighting.

## Licensing reminder (please read)

- **Don't use copyrighted character models in public or commercial settings** without
  the rights to do so.
- **Follow each model's own license**, including any license attached to a `.vrma`
  motion clip you use (VRoid Hub and Mixamo both have their own terms).
- Using your own commissioned or self-made model is the safe path.
