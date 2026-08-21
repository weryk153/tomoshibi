# Add your own Live2D character

**Scenario:** You have a Live2D model and you want to use it as your character's
appearance in Tomoshibi, instead of the built-in sample models.

## What you need

A complete **Live2D model folder**. A valid model folder contains at least:

- a **`.model3.json`** file (the model's main descriptor),
- a **`.moc3`** file (the model data),
- **textures** (the image files, usually a `.../*.2048/texture_00.png` set),
- **motions** (the `.motion3.json` animation files, including an idle motion).

The built-in `mao_pro` sample uses the nested layout
`live2d-models/<name>/runtime/<name>.model3.json`; the others (`haru`, `hiyori`)
keep the `.model3.json` directly in the folder. Either shape works —
the scanner finds the `.model3.json` up to 3 levels deep.

## How Tomoshibi finds your model (verified from the code)

You **do not** normally need to hand-edit any JSON. Tomoshibi has an **auto-scanner**:

- Whenever the **Character Manager** loads the skin list (it calls the
  `/api/live2d-skins` endpoint), Tomoshibi scans the `live2d-models/` folder.
- For every **top-level sub-folder** that contains a `*.model3.json` (found within up to
  3 levels deep — so `live2d-models/<name>/...` or `<name>/runtime/...` both work), it
  treats that folder as a usable model.
- Any model it finds that **isn't registered yet** is **auto-registered** into
  `model_dict.json` for you, using the **folder name** as the skin name, a neutral
  emotion map, and the model's real idle motion group. This write is automatic and only
  happens when something new is found.

So: **the folder name is the skin name**, and dropping a valid folder in is enough — it
shows up in the skin dropdown by itself. Editing `model_dict.json` by hand is optional and
only needed for fine-tuning (see FAQ).

## Step-by-step

### 1. Drop your model into `live2d-models/`

Put your whole model folder under the Tomoshibi folder:

```
live2d-models/
  my_character/
    runtime/
      my_character.model3.json
      my_character.moc3
      my_character.2048/ (textures)
      motions/ (*.motion3.json)
```

Use a simple folder name (letters, numbers, `_`, `-`). That name becomes the skin name.

### 2. Let Tomoshibi scan it (automatic)

Open Tomoshibi → **Settings → Character Manager**, and open the **Appearance (Live2D skin)**
dropdown when creating or editing a character. Opening the manager triggers the skin scan,
which auto-registers your new folder. Your model should now appear in the dropdown by its
folder name. (If you just added the folder while Tomoshibi was open, reopen the Character
Manager so it rescans.)

### 3. Create or edit a character that uses it

In the Character Manager:

1. **Create** a new character (or **edit** an existing one).
2. Set the **Appearance / Live2D skin** to your model (its folder name).
3. Set the **persona** (personality / system prompt) and **voice**.
4. **Save**, then **select / switch to** that character to apply it.

(Note: the Character Manager validates the skin — if you typed a name that isn't a scanned,
registered model, it will refuse with a "drop it into live2d-models/ then rescan" message.
That's expected; just make sure the folder is really there and contains a `.model3.json`.)

## Give your character a skin-picker thumbnail (optional)

The skin picker shows a thumbnail for each character. The built-in characters already ship
with thumbnails; for a model you add yourself, just drop a preview image into its folder and
the picker shows it automatically — no screenshotting, no configuration needed.

How: name an image `thumbnail.png` and put it in your model folder (the same level as the
`.model3.json`):

```
live2d-models/<your_character>/thumbnail.png
```

- Accepted filenames (detected in order): `thumbnail.png` / `.jpg` / `.jpeg` / `.webp`,
  `preview.png`, `preview.jpg`, `icon.png`, or a `<foldername>.png` that matches the folder.
- Many Live2D models already come with a preview image — just rename it and drop it in.
- A portrait aspect ratio (e.g. 260×400) looks best; the image is auto-cropped and centered.
- It's fine to skip this — the picker shows a "?" placeholder and everything still works.
- After adding it, reopen the Character Manager (it rescans) to make it appear.

## FAQ / troubleshooting

- **My folder doesn't appear in the dropdown.** It's almost always because the folder has
  **no `*.model3.json`** within 3 levels, so the scanner skips it. Confirm the model3.json
  is at `live2d-models/<name>/...` or `<name>/runtime/...`. Then reopen the Character
  Manager to rescan.
- **The model loads but is too big/small or off-center.** The auto-registered entry uses
  safe defaults (`kScale: 0.5`, no offset). To fine-tune, open `model_dict.json` and edit
  your model's entry — `kScale` (size), `initialXshift` / `initialYshift` (position). This
  hand-editing is **optional**; the model already works without it.
- **No expressions / it only stays neutral.** Auto-registered models get a minimal
  `emotionMap` of just `{"neutral": 0}`. To map more expressions, edit your model's
  `emotionMap` in `model_dict.json` (compare with the built-in `mao_pro` entry, which maps
  joy/anger/sadness/etc. to motion indices). Optional.
- **My character never plays a body motion.** That's `motionMap`, a separate field from
  `emotionMap`: an expression is a facial parameter overlay, a motion is a full-body
  timeline animation (`.motion3.json`), and the LLM triggers it the same way — a
  `[keyword]` in its reply. Auto-registered models get an empty `motionMap` (`{}`), so nothing
  plays until you add one by hand in `model_dict.json`. Each entry has the shape
  `"keyword": {"group": "<group name>", "index": <index>}`, and **you need both** — a
  group name alone isn't enough to pick a motion. Look at your `.model3.json`'s
  `FileReferences.Motions` block: it's a dict of group name → list of motion files, and
  the built-in `mao_pro` has *six* usable motions that all live in the **same unnamed
  group** (its key is the empty string `""`), distinguished only by their position in
  that list (index `0`, `1`, `2`, ...). A table keyed by group name only would collapse
  all six into one random pick. Exclude the `Idle` and `Talk` groups from `motionMap` —
  they're already driven automatically and aren't yours to trigger. Each entry also takes
  an optional `"label"` — a short human-written description of what the animation actually
  shows (`"雙手抱胸的招牌姿勢"`). The whole list goes into the LLM's system prompt, and the
  keyword alone tells it nothing, so a label is what lets it choose between six motions
  instead of guessing. Write the label only after you have watched the animation: a wrong
  description is worse than none, because the model will then use it confidently at the
  wrong moment. Leave it out (or empty) and the keyword is listed bare, which reads as
  "unspecified". To preview a motion, open devtools and call
  `window.Live2DDebug.playMotion("<group>", <index>)`. Optional.
- **Idle animation looks wrong.** The scanner auto-detects the idle motion group (it
  prefers a group literally named `Idle`, otherwise the first motion group). If your model
  names its idle group differently, adjust `idleMotionGroupName` in `model_dict.json`.

## Licensing reminder (please read)

- **Don't use copyrighted character models in public or commercial settings** without the
  rights to do so.
- **Follow each model's own license.** The bundled samples (`mao_pro`, `haru`, `hiyori`)
  are Live2D Original Characters, used under the Live2D Free Material License. See
  `LICENSE-Live2D.md` and `NOTICE` in the project for details. When you add your own
  model, follow that model's own license.
- Using your own commissioned or self-made model is the safe path.

---

## 繁體中文

**情境：** 你有一個 Live2D 模型，想拿它當 Tomoshibi 角色的外觀，取代內建的範例模型。

### 你需要什麼

一個完整的 **Live2D 模型資料夾**，至少要包含：

- 一個 **`.model3.json`**（模型主描述檔）、
- 一個 **`.moc3`**（模型資料）、
- **貼圖**（圖檔，通常是 `.../*.2048/texture_00.png` 那一組）、
- **動作 motions**（`.motion3.json` 動畫檔，含一個 idle 待機動作）。

內建的 `mao_pro` 範例採巢狀結構
`live2d-models/<名稱>/runtime/<名稱>.model3.json`；其餘（`haru`、`hiyori`）則把
`.model3.json` 直接放在資料夾裡。兩種擺法都可以——掃描器會在 3 層深度內找到
`.model3.json`。

### Tomoshibi 怎麼找到你的模型（已讀程式碼查證）

正常情況下你**不用**手動改任何 JSON。Tomoshibi 有**自動掃描**：

- 每當**角色管理器**載入皮膚清單（它會打 `/api/live2d-skins` 這個端點），Tomoshibi 就會掃描
  `live2d-models/` 資料夾。
- 只要某個**最上層子資料夾**裡含有 `*.model3.json`（在 3 層深度內找——所以
  `live2d-models/<名稱>/...` 或 `<名稱>/runtime/...` 都行），就會被當成可用模型。
- 任何掃到但**還沒註冊**的模型，會被**自動寫進** `model_dict.json`，用**資料夾名稱**當皮膚名、
  套一個中性的表情對應、以及該模型真正的 idle 動作群組。這個寫入是自動的，只有發現新模型時才會發生。

所以：**資料夾名稱就是皮膚名稱**，把有效的資料夾丟進去就夠了，它會自己出現在皮膚下拉選單。
手動改 `model_dict.json` 是選用的，只有微調時才需要（見常見問題）。

### 操作步驟

1. **把模型放進 `live2d-models/`。** 把整個模型資料夾放到 Tomoshibi 資料夾底下：

   ```
   live2d-models/
     my_character/
       runtime/
         my_character.model3.json
         my_character.moc3
         my_character.2048/ (貼圖)
         motions/ (*.motion3.json)
   ```

   用簡單的資料夾名稱（英數字、`_`、`-`），這個名稱就會變成皮膚名稱。

2. **讓 Tomoshibi 掃描它（自動）。** 打開 Tomoshibi →**設定 → 角色管理器**，在新增或編輯角色時
   打開**外觀（Live2D 皮膚）**下拉選單。打開角色管理器就會觸發皮膚掃描、自動註冊你的新資料夾，
   你的模型就會以資料夾名稱出現在下拉選單裡。（如果你是在 Tomoshibi 開著時才加資料夾，重新打開
   角色管理器讓它重掃一次。）

3. **建立或編輯一個用它的角色。** 在角色管理器裡：**新增**一個角色（或**編輯**現有的）→
   把**外觀／Live2D 皮膚**選成你的模型（它的資料夾名）→ 設定**人設**（個性／系統提示詞）與
   **聲音**→**儲存**，再**選取／切換**到那個角色就會套用。

   （注意：角色管理器會驗證皮膚——如果你填的名稱不是掃描並註冊過的模型，它會擋下來並提示
   「丟進 live2d-models/ 再重掃」。這是正常的，確認資料夾真的在、而且裡面有 `.model3.json` 即可。）

### 給你的角色一張選皮縮圖（選用）

選皮的地方會顯示每個角色的縮圖。內建角色都已附縮圖；你自己加的模型，只要在它的資料夾裡放
一張預覽圖，選單就會自動顯示——不用自己截圖、不用任何設定。

做法：把一張圖命名為 `thumbnail.png`，放進你的模型資料夾（跟 `.model3.json` 同一層）：

```
live2d-models/<你的角色>/thumbnail.png
```

- 支援的檔名（依序偵測）：`thumbnail.png` / `.jpg` / `.jpeg` / `.webp`、`preview.png`、
  `preview.jpg`、`icon.png`，或跟資料夾同名的 `<角色名>.png`。
- 很多 Live2D 模型下載時本來就附一張預覽圖，直接改名丟進去即可。
- 直式比例（例如 260×400 上下）最好看；圖會自動裁切置中。
- 沒放也沒關係，選單會顯示一個「?」佔位，功能不受影響。
- 放好後重開角色管理器（會重新掃描）就會出現。

### 常見問題

- **資料夾沒出現在下拉選單。** 幾乎都是因為 3 層內**沒有 `*.model3.json`**，掃描器就跳過了。
  確認 model3.json 在 `live2d-models/<名稱>/...` 或 `<名稱>/runtime/...`，再重開角色管理器重掃。
- **模型載入了但太大／太小／沒對中。** 自動註冊的條目用的是安全預設（`kScale: 0.5`、無位移）。
  要微調就打開 `model_dict.json` 改你模型那筆的 `kScale`（大小）、`initialXshift` /
  `initialYshift`（位置）。這個手改是**選用的**，不改也能用。
- **沒有表情／一直是中性臉。** 自動註冊的模型只有最小的 `emotionMap`（只有 `{"neutral": 0}`）。
  要對應更多表情，就在 `model_dict.json` 改你模型的 `emotionMap`（可參考內建 `mao_pro` 那筆，
  它把喜怒哀等對應到動作索引）。選用。
- **角色都不會做出動作。** 那是 `motionMap`，跟 `emotionMap` 是不同欄位：表情是臉部參數疊加，
  動作則是全身的時間軸動畫（`.motion3.json`），LLM 觸發它的方式跟表情一樣——回覆裡放一個
  `[關鍵字]`。自動註冊的模型拿到的是空的 `motionMap`（`{}`），所以在你手動填進 `model_dict.json` 之前
  什麼都不會播。每個條目的形狀是 `"關鍵字": {"group": "<群組名>", "index": <索引>}`，**兩個都
  要有**——只給群組名不夠選出一個動作。看你的 `.model3.json` 裡的 `FileReferences.Motions`
  區塊：它是「群組名 → 動作檔案清單」的字典，內建的 `mao_pro` 有**六個**可用動作，全部都在
  **同一個無名群組**裡（它的 key 是空字串 `""`），只靠它們在清單裡的位置（索引 `0`、`1`、`2`、
  ……）互相區分。如果表格只用群組名當 key，這六個就會全部塌縮成同一個、隨機挑一個播放。
  `Idle` 與 `Talk` 群組不要放進 `motionMap`，它們已經被自動流程使用，不是給你觸發的。每個條目
  還可以有一個選用的 `"label"`——一句人寫的中文描述，講這個動畫實際長什麼樣（例如
  `"雙手抱胸的招牌姿勢"`）。整份清單會被塞進 LLM 的系統提示詞，而光看關鍵字它什麼都不知道，
  所以 label 才是讓它能在六個動作之間做選擇、而不是亂猜的東西。**label 要等你實際看過動畫再
  寫**：描述錯的比沒有更糟，因為模型會很有自信地在錯的時機用它。不填（或留空字串）就只列出
  關鍵字，對模型而言讀起來是「未指定」。要預覽某個動作，開 devtools 呼叫
  `window.Live2DDebug.playMotion("<群組名>", <索引>)`。選用。
- **待機動畫怪怪的。** 掃描器會自動偵測 idle 動作群組（優先找名字就叫 `Idle` 的，沒有就用第一個
  動作群組）。如果你的模型 idle 群組名字不同，去 `model_dict.json` 調 `idleMotionGroupName`。

### 授權提醒（務必看）

- **不要在公開／商用情境使用有版權的角色模型**，除非你有使用權。
- **遵守每個模型自己的授權。** 內建範例（`mao_pro`、`haru`、`hiyori`）都是 Live2D 原創角色，
  依 Live2D 無償提供材料授權使用。詳見專案裡的 `LICENSE-Live2D.md` 與 `NOTICE`。當你加入自己的
  模型時，請遵守那個模型自己的授權。
- 用你自己委託製作或自製的模型是最安全的做法。
