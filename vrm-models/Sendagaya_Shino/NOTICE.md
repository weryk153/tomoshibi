# Sendagaya Shino

VRoid Studio 的官方範例模型（VRoid Project「歴代サンプルモデル」系列），隨本專案附帶
作為開箱即用的 3D 角色。**VRM 1.0**（VRoid Studio 1.20.2 匯出，meta `version: v2.0`）。

## 授權

以下是從 `.vrm` 檔案內嵌的 `VRMC_vrm.meta` 讀出來的欄位——不是從網頁抄的，是檔案
本身宣告的。VRM 1.0 的 meta 沒有 `licenseName` 這種單一欄位，授權拆成幾個旗標：

| 欄位 | 值 |
|---|---|
| `name` | Sendagaya_Shino |
| `authors` | coati |
| `licenseUrl` | https://vrm.dev/licenses/1.0/ |
| `avatarPermission` | everyone |
| `allowRedistribution` | true |
| `modification` | allowModificationRedistribution |
| `commercialUsage` | corporation |
| `creditNotation` | unnecessary |
| `allowExcessivelyViolentUsage` / `allowExcessivelySexualUsage` | true |
| `allowPoliticalOrReligiousUsage` / `allowAntisocialOrHateUsage` | true |

VRoid Hub 那頁的說明寫的是全系列 CC0；檔案內嵌的旗標與此一致（可再散布、可改作後
再散布、不需署名、商用允許）。

取得來源：<https://hub.vroid.com/en/characters/4593660874193246717/models/7956589129305596116>
（VRoid Hub，需登入下載）

想自己確認的話：

```bash
uv run python -c "
from src.open_llm_vtuber.vrm_models import read_glb_json
d = read_glb_json('vrm-models/Sendagaya_Shino/Sendagaya_Shino.vrm')
print(d['extensions']['VRMC_vrm']['meta'])
"
```

## 表情

VRM 1.0 的 `VRMC_vrm.expressions` 掃描器讀得到，14 個 preset：
`happy`、`angry`、`sad`、`relaxed`、`surprised`、`aa`／`ih`／`ou`／`ee`／`oh`（嘴型）、
`blink`／`blinkLeft`／`blinkRight`、`neutral`。

`model_dict` 裡的 `emotionMap` 對應：`joy→happy`、`anger→angry`、`sadness→sad`、
`surprise→surprised`、`relaxed→relaxed`、`neutral→neutral`。

## motions/

### idle.vrma

**不是**第三方素材。由 `scripts/make_idle_vrma.py` 從零生成：自己搭一副標準
VRM T-pose 骨架、自己算曲線，所以沒有授權問題，跟本專案同授權。

現成的情緒動作起訖姿勢不同，拿來當 idle 會每隔幾秒硬接一次很明顯；這支生成的
所有擺動頻率都取週期的整數倍，首末幀完全相同。

### 其餘 11 個動作片段

來自 **[tk256ailab/vrm-viewer](https://github.com/tk256ailab/vrm-viewer)**，
MIT 授權。授權全文附在同目錄的 `LICENSE.tk256`：

> MIT License
> Copyright (c) 2025 TK256

**本專案做過的修改**：原始檔案的 `VRMC_vrm_animation` 缺 `specVersion`，
載入時 three-vrm 每個檔案都會警告一次（它會自行假設 1.0）。已補上該欄位，
動畫資料未變動。檔名也改成小寫底線（`Goodbye.vrma` → `goodbye.vrma`），
因為檔名就是 LLM 觸發用的關鍵字。

沒有 `idle.vrma` 的話角色會維持 T-pose——VRM 的靜止姿勢就是張開雙臂，
`motion-player.ts` 找不到 idle action 時會淡出到那個姿勢。所以它形同必要。

要再加動作，把 `.vrma` 放進 `motions/` 就會自動登記；檔名（去掉副檔名）就是
LLM 用來觸發它的關鍵字。詳見 `docs/add-vrm-character.md`。

## 歷史

2026-09-10 起附帶的是同一角色的 VRM 0.x 版（VRoidStudio-0.8.1 匯出，
`VRM.meta.licenseName: CC0`）。0.x 掃不出表情，`emotionMap` 得手填，preset 名也會被
three-vrm 改名（`joy→happy` 等）。2026-09-15 換成 VRoid Hub 上的官方 VRM 1.0 版。
