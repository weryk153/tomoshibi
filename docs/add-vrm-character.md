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

---

## 繁體中文

**情境：** 你有（或想做一個）VRM 3D 模型，想拿它當 Tomoshibi 角色的外觀，作為 Live2D
之外的另一種選擇。

### 你需要什麼

一個 **VRM 檔**——`.vrm` 其實是包了 VRM 擴充的二進位 glTF（`.glb`）容器，所以任何
VRoid Studio 或 Blender VRM 匯出的檔案都能用。另外可以選配一個或多個 **`.vrma` 動作檔**
（VRM 的動畫格式）搭配它。

強烈建議用 VRM 1.0：Tomoshibi 會讀 VRM 1.0 檔案的 `VRMC_vrm.expressions` 區塊來知道它
有哪些表情，而且只有當檔案裡真的有對應的標準 preset 時，才會自動把某個關鍵字對應到它
（見下面的[對應設定](#對應設定)）。VRM 0.x 檔案還是能載入、能顯示，但 Tomoshibi 沒辦法
列舉它的表情，所以只會拿到最陽春的 `{"neutral": "neutral"}` 對應，加上伺服器 log 裡的一則
警告——其餘的都要自己手動補上。

### Tomoshibi 怎麼找到你的模型（已讀程式碼查證）

跟 Live2D 一樣的自動掃描模式，實作在 `src/open_llm_vtuber/vrm_models.py`
（`scan_and_register_vrm`）：

- 每當**角色管理器**載入皮膚清單（打 `GET /api/live2d-skins`）時，Tomoshibi 也會掃描
  `vrm-models/` 資料夾。
- `vrm-models/` 底下每個**最上層子資料夾**，只要它的頂層（不是巢狀更深處）直接放了一個
  `*.vrm` 檔，就會被當成可用模型——**資料夾名稱就是模型名稱**，跟 Live2D 一樣。
- 如果一個資料夾頂層有一個以上的 `.vrm` 檔，Tomoshibi 會挑**依字母排序後排第一個**的那個。
- 任何掃到但**還沒註冊**的資料夾，會被**自動寫進** `model_dict.json`：讀 `.vrm` 檔算出
  預設的表情對應，掃 `motions/*.vrma` 算出預設的動作對應（見下方）。這個寫入是自動的，
  只有發現新模型時才會發生。

所以：把資料夾丟進去，打開角色管理器，它就會出現在皮膚下拉選單裡——一開始不用手改任何
東西。`vrm-models/` 本身有被 gitignore，你放進去的東西不會被提交進版控。

### 操作步驟

**1. 把模型放進 `vrm-models/`**

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

- `.vrm` 檔本身叫什麼名字不重要——只有**資料夾名稱**會變成模型名稱，掃描器只是抓資料夾
  頂層第一個找到的 `.vrm`。
- `motions/` 是選用的。裡面的 `idle.vrma` 是一個**保留檔名**：如果存在，它會取代內建的
  簡易搖擺，成為迴圈播放的待機動畫。`motions/` 裡**其他**每一個 `.vrma` 檔都會變成一個
  LLM 可觸發的一次性動作片段，預設關鍵字就是它的檔名（去掉 `.vrma`）。
- `thumbnail.png` / `.jpg` / `.jpeg` / `.webp` 是選用的，跟 Live2D 一樣——見下方
  [給你的角色一張選皮縮圖（選用）](#給你的角色一張選皮縮圖選用)。

**2. 讓 Tomoshibi 掃描它（自動）**

打開 Tomoshibi →**設定 → 角色管理器**，在新增或編輯角色時打開**外觀**下拉選單——打開
管理器就會觸發掃描，自動註冊你的新資料夾。你的模型會以資料夾名稱，出現在跟 Live2D 皮膚
同一個下拉選單裡。

自動註冊出來的 `model_dict.json` 條目長這樣（這是一個真實範例，不是模板——這個形狀是
固定的）：

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

（`kScale` / `initialXshift` / `initialYshift` / `tapMotions` 是為了跟 Live2D 條目
形狀相容而沿用的欄位，VRM 模型不會用到它們。）

**3. 建立或編輯一個用它的角色**

跟 Live2D 一樣：在角色管理器裡，把**外觀**設成你的 VRM 模型（它的資料夾名）——這個欄位
在角色 YAML 裡的名字還是 `live2d_model_name`，只是現在它也接受 VRM 模型名稱了。設定
人設與聲音、儲存，再切換到那個角色套用即可。

### 對應設定

**`emotionMap`——臉部表情**

`emotionMap` 把一個 Tomoshibi 情緒關鍵字對應到一個 **VRM 表情名稱**（是字串，不是像
Live2D 那樣的索引）。掃描器只有在檔案裡真的有對應的標準 preset 時，才會自動填入某個
關鍵字：

| Tomoshibi 關鍵字 | VRM 1.0 preset |
|---|---|
| `neutral` | `neutral` |
| `joy` | `happy` |
| `anger` | `angry` |
| `sadness` | `sad` |
| `surprise` | `surprised` |

`relaxed` 沒有常見的對應 preset，永遠不會被自動填入。如果你的 `.vrm` 檔案定義了自訂表情
（超出這五個標準 preset），可以在 `model_dict.json` 裡手動編輯 `emotionMap` 來對應——
表情名稱要跟檔案裡實際寫的一模一樣。

**`motionMap`——一次性動作片段**

`motionMap` 把一個關鍵字對應到 `{ "clip": "<檔名主體>", "label": "<描述>" }`。自動註冊
的條目會把 `clip` 設成每個 `motions/*.vrma` 檔案的檔名主體（扣掉 `idle`），`label` 則
留白（`null`）。

**記得補上 label。** label 是 LLM 決定要觸發哪個動作時**唯一看得到**的東西——光是關鍵字
本身不會顯示給它看。`label: null` 的條目，LLM 沒辦法有意識地挑選它。先看過那段動畫，
再去改 `model_dict.json`：

```json
"motionMap": { "wave": { "clip": "wave", "label": "揮手打招呼" } }
```

關鍵字本身就是 LLM 在回覆裡寫 `[關鍵字]` 用來觸發這個片段的東西——機制跟 Live2D 的
`[關鍵字]` 動作一樣。要換某個片段的關鍵字，重新命名那個 `.vrma` 檔即可（掃描器是用檔名
來產生新條目的 key）；要改既有對應的 label，直接編輯 JSON 就好。

`PUT /api/live2d/model-config/{name}`（從設定頁儲存時會呼叫）會拿這兩份對應表去比對
`.vrm` 檔與 `motions/` 資料夾裡實際存在的內容——指到不存在的片段或表情名稱會被拒絕。

### 相機

`camera.distance` 跟 `camera.height`，單位都是公尺，決定 VRM 相機的位置；相機會看向
`(0, height, 0)` 這個點。預設是 `distance: 1.6`、`height: 1.35`。如果模型框得太近／太遠
或太高／太低，就到 `model_dict.json` 調這兩個值。

### 執行期行為（模型載入後你會看到什麼）

- **口型同步**直接吃 TTS 產生的 WAV 音檔驅動（不經過 Web Audio API）。
- **表情**淡入淡出各 0.2 秒。
- **眨眼**是自動的（內建一套眨眼狀態機），跟你設的 `emotionMap` 無關。
- **視線**：如果 Live2D 的「視線跟隨滑鼠」設定是開的，角色的眼睛會跟著滑鼠指標；關閉的話
  就看向鏡頭。
- **待機**：如果有 `motions/idle.vrma` 就迴圈播放；沒有的話就用內建的簡易搖擺代替。
- **LLM 觸發的動作**：`motionMap` 裡的 `[關鍵字]` 會讓角色淡入該片段，播完再淡回待機。
- **載入失敗**：如果 `.vrm` 檔載入失敗，Tomoshibi 會跳一個提示，對話照常繼續，只是沒有
  角色畫面——不會卡住聊天。

### 設定頁

對 VRM 模型來說，角色管理器模型設定裡的**外觀**分頁顯示的是模型的片段、表情、目前關鍵字
對應的**唯讀摘要**（沒有 Live2D 那種動作／點擊區編輯器的 VRM 版本）。要改東西的話：

- **重新命名 `.vrma` 檔**來改變觸發它的關鍵字。
- **手動編輯 `model_dict.json`**來改動作的 label 或表情的關鍵字對應。

### 給你的角色一張選皮縮圖（選用）

機制跟 Live2D 完全一樣：把 `thumbnail.png` / `.jpg` / `.jpeg` / `.webp` 放進模型資料夾
（跟 `.vrm` 檔同一層），重開角色管理器讓它重掃，選皮的地方就會顯示。不放也沒關係，選單
會顯示一個佔位圖——其他功能都不受影響。

### 模型來源

目前有兩條候選管線可以做出一個 VRM 模型；**Tomoshibi 該推薦哪一條還沒定案**——有一個
spike 計畫要來釐清這件事。兩條路都能產出合法的 `.vrm` 檔，差別在匯出之後要花多少人工
去補臉部綁定。

1. **VRoid Studio → 匯出 VRM 1.0。** 最直接的路：VRoid Studio 直接匯出 VRM 1.0，標準
   表情 preset（`neutral`、`happy`、`angry`、`sad`、`surprised`）、眨眼，以及口型同步用的
   `aa`/`ih`/`ou`/`ee`/`oh` 嘴型都是現成的——不用額外綁定。你也可以選擇性地在 Blender 裡
   用 [VRM Add-on for Blender](https://github.com/saturday06/VRM-Add-on-for-Blender)
   （saturday06 出品，MIT 授權）進一步微調匯出的模型。
2. **圖生 3D → Blender → VRM 匯出。** 用一個帶自動綁骨功能的工具（例如 Meshy 或
   Tripo），或用 Hunyuan3D／Hyper3D，從參考圖生成一個網格模型，再拉進 Blender 用同一個
   VRM Add-on 匯出。身體的骨架綁定通常堪用，但**這類生成工具做不出 VRM 的臉部
   blendshape**——口型同步用的 `aa` 嘴型、眨眼、以及各種情緒表情，都得在 Blender 裡匯出
   前手動做出來。這比管線 1 要多花不少人工，這也是為什麼會有這個 spike。

**`.vrma` 動作片段的來源**

- VRoid Hub 上發布的免費範例 `.vrma` 動作（原始來源是 pixiv）。
- [Mixamo](https://www.mixamo.com/) 的動作捕捉片段，重新綁定後透過 Blender 的 VRM
  Add-on 匯出成 `.vrma`。

### v1 限制

- **只支援視窗模式**——VRM 角色目前不支援 Tomoshibi 的桌面寵物（pet）模式。
- **沒有點擊區**——點角色本身沒有反應（Live2D 的點擊觸發反應，VRM 目前還沒有對應功能）。
- **設定唯讀**——見上方[設定頁](#設定頁)；沒有應用內編輯器可以改片段或表情對應，只能
  改 `model_dict.json`。
- **沒有陰影或環境光照（IBL）**——VRM 畫布渲染時沒有陰影通道，也沒有環境光照。

### 授權提醒（務必看）

- **不要在公開／商用情境使用有版權的角色模型**，除非你有使用權。
- **遵守每個模型自己的授權**，包括你用的 `.vrma` 動作片段各自附帶的授權（VRoid Hub 跟
  Mixamo 都有各自的條款）。
- 用你自己委託製作或自製的模型是最安全的做法。
