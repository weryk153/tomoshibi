# Sendagaya Shino

VRoid Studio 的官方範例模型，隨本專案附帶作為開箱即用的 3D 角色。

## 授權

**CC0**（公眾領域）。以下是從 `.vrm` 檔案內嵌的 `VRM.meta` 讀出來的欄位——
不是從網頁抄的，是檔案本身宣告的：

| 欄位 | 值 |
|---|---|
| `title` | Sendagaya Shino |
| `licenseName` | CC0 |
| `allowedUserName` | Everyone |
| `commercialUssageName` | Allow |
| `violentUssageName` | Allow |
| `sexualUssageName` | Allow |

取得來源：<https://github.com/madjin/vrm-samples>（VRoid 官方 sample 的彙整）

想自己確認的話：

```bash
python -c "
from src.open_llm_vtuber.vrm_models import read_glb_json
d = read_glb_json('vrm-models/Sendagaya_Shino/Sendagaya_Shino.vrm')
print(d['extensions']['VRM']['meta'])
"
```

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

## 這個模型是 VRM 0.x

掃描器列舉不到它的表情（那是 VRM 1.0 的 `VRMC_vrm.expressions` 才有的），所以
`model_dict.json` 裡的 `emotionMap` 需要手動填。three-vrm 會照
`v0v1PresetNameMap` 把 0.x 的 preset 改名：`joy` → `happy`、`sorrow` → `sad`、
`fun` → `relaxed`。
