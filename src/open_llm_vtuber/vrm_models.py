"""vrm-models/ 的掃描登記，與 .vrm 檔的最小讀取。

.vrm 就是 GLB（binary glTF）。只讀第一個 chunk（JSON），從
``extensions.VRMC_vrm.expressions`` 拿表情名——這是產生預設 emotionMap 與驗證
使用者手改對應時唯一需要的資訊，不需要任何 glTF 函式庫。

跟 live2d_config_route.scan_and_register_skins 同一套規則：資料夾名 = 模型名 =
model_dict ``name``；冪等，只在有新模型時寫檔。
"""

import glob
import json
import os
import struct
from typing import Optional

from loguru import logger

from .character_route import _load_model_dict, _write_model_dict_atomic

VRM_DIR = "vrm-models"
MOTIONS_SUBDIR = "motions"
IDLE_CLIP = "idle"

_GLB_MAGIC = b"glTF"
_JSON_CHUNK = 0x4E4F534A

# Tomoshibi 情緒關鍵字 → VRM 1.0 標準 preset。只有檔案裡真的有的 preset 才會進
# 預設對應；relaxed 沒有對應的常用關鍵字，留給使用者自己加。
_KEYWORD_TO_PRESET = {
    "neutral": "neutral",
    "joy": "happy",
    "anger": "angry",
    "sadness": "sad",
    "surprise": "surprised",
}

_THUMB_NAMES = ("thumbnail.png", "thumbnail.jpg", "thumbnail.jpeg", "thumbnail.webp")


def read_glb_json(path: str) -> Optional[dict]:
    """GLB 的 JSON chunk。不是 GLB、截斷、或 JSON 壞掉都回 None。"""
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                return None
            magic, _version, _length = struct.unpack("<4sII", header)
            if magic != _GLB_MAGIC:
                return None
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                return None
            chunk_len, chunk_type = struct.unpack("<II", chunk_header)
            if chunk_type != _JSON_CHUNK:
                return None
            data = json.loads(f.read(chunk_len).decode("utf-8"))
            return data if isinstance(data, dict) else None
    except Exception as e:
        logger.debug(f"[vrm] glb read failed for {path}: {type(e).__name__}")
        return None


def read_vrm_expressions(path: str) -> Optional[list[str]]:
    """VRM 1.0 的表情名（preset 在前、custom 在後）。VRM 0.x 或讀不了回 None。"""
    data = read_glb_json(path)
    if data is None:
        return None
    ext = data.get("extensions", {}) or {}
    if not isinstance(ext, dict):
        return None
    vrmc = ext.get("VRMC_vrm")
    if not isinstance(vrmc, dict):
        if "VRM" in ext:
            logger.warning(
                f"[vrm] {path} is VRM 0.x — expressions not enumerated; "
                "emotionMap defaults to neutral only"
            )
        return None
    expressions = vrmc.get("expressions", {}) or {}
    if not isinstance(expressions, dict):
        return []
    names: list[str] = []
    for bucket in ("preset", "custom"):
        group = expressions.get(bucket, {}) or {}
        if isinstance(group, dict):
            names.extend(group.keys())
    return names


def default_emotion_map(expressions: Optional[list[str]]) -> dict:
    """關鍵字 → preset，只放檔案裡真的有的。不知道有什麼就只給 neutral。"""
    if not expressions:
        return {"neutral": "neutral"}
    have = set(expressions)
    result = {k: p for k, p in _KEYWORD_TO_PRESET.items() if p in have}
    if "neutral" not in result:
        result = {"neutral": "neutral", **result}
    return result


def find_vrm_file(model_dir: str) -> Optional[str]:
    matches = sorted(glob.glob(os.path.join(model_dir, "*.vrm")))
    return matches[0] if matches else None


def list_vrm_clips(model_dir: str) -> list[str]:
    """motions/*.vrma 的檔名（不含副檔名），排序，排除 idle（那是待機迴圈，不給 LLM 觸發）。"""
    pattern = os.path.join(model_dir, MOTIONS_SUBDIR, "*.vrma")
    stems = [os.path.splitext(os.path.basename(p))[0] for p in glob.glob(pattern)]
    return sorted(s for s in stems if s != IDLE_CLIP)


def _find_thumbnail(model_dir: str, name: str) -> Optional[str]:
    for fn in _THUMB_NAMES:
        if os.path.isfile(os.path.join(model_dir, fn)):
            return f"/{VRM_DIR}/{name}/{fn}"
    return None


def scan_and_register_vrm() -> dict:
    """掃 vrm-models/，把還沒登記的自動加進 model_dict.json。

    一個資料夾是有效模型 iff 頂層有 *.vrm。回傳形狀與
    scan_and_register_skins 相同，多一個 ``type: "vrm"``。
    """
    model_dict = _load_model_dict()
    registered = {m.get("name") for m in model_dict if isinstance(m, dict)}
    newly: list[str] = []
    skins: list[dict] = []

    if os.path.isdir(VRM_DIR):
        for entry in sorted(os.listdir(VRM_DIR)):
            if entry.startswith("."):
                continue
            model_dir = os.path.join(VRM_DIR, entry)
            if not os.path.isdir(model_dir):
                continue
            vrm_path = find_vrm_file(model_dir)
            if not vrm_path:
                continue
            name = entry
            skins.append(
                {
                    "name": name,
                    "registered": True,
                    "thumbnail": _find_thumbnail(model_dir, name),
                    "type": "vrm",
                }
            )
            if name in registered:
                continue
            expressions = read_vrm_expressions(vrm_path)
            model_dict.append(
                {
                    "name": name,
                    "type": "vrm",
                    "description": "自動偵測並註冊的 VRM 模型",
                    "url": f"/{VRM_DIR}/{name}/{os.path.basename(vrm_path)}",
                    # 前端 ModelInfo 型別要求這三欄；VRM 不使用。
                    "kScale": 1,
                    "initialXshift": 0,
                    "initialYshift": 0,
                    "emotionMap": default_emotion_map(expressions),
                    "tapMotions": {},
                    "motionMap": {
                        clip: {"clip": clip, "label": None}
                        for clip in list_vrm_clips(model_dir)
                    },
                    "camera": {"distance": 1.6, "height": 1.35},
                }
            )
            registered.add(name)
            newly.append(name)

    if newly:
        _write_model_dict_atomic(model_dict)
        logger.info(f"Auto-registered VRM models: {newly}")

    return {"skins": skins, "newly_registered": newly}


def _entry_dir(entry: dict) -> str:
    return os.path.join(VRM_DIR, entry["name"])


def build_vrm_model_config(entry: dict) -> Optional[dict]:
    """列舉一個 VRM 模型真的有的 clip 與表情，合併 model_dict 的對應。

    形狀跟 Live2D 的 build_model_config 不同（沒有 group/index、沒有 hit area），
    前端用 ``type`` 分辨。找不到 .vrm 回 None → 404。
    """
    model_dir = _entry_dir(entry)
    vrm_path = find_vrm_file(model_dir)
    if not vrm_path:
        return None

    motion_map = entry.get("motionMap", {}) or {}
    clips = list_vrm_clips(model_dir)
    by_clip: dict = {c: [] for c in clips}
    orphans = []
    for keyword, target in motion_map.items():
        clip = (target or {}).get("clip") if isinstance(target, dict) else None
        if clip in by_clip:
            by_clip[clip].append({"keyword": keyword, "label": target.get("label")})
        else:
            orphans.append({"keyword": keyword, "clip": clip})

    expressions = read_vrm_expressions(vrm_path) or []
    emotion_map = entry.get("emotionMap", {}) or {}
    by_expr: dict = {e: [] for e in expressions}
    for keyword, name in emotion_map.items():
        if name in by_expr:
            by_expr[name].append(keyword)

    return {
        "name": entry["name"],
        "type": "vrm",
        "clips": [
            {"clip": c, "file": f"{MOTIONS_SUBDIR}/{c}.vrma", "mappings": by_clip[c]}
            for c in clips
        ],
        "expressions": [{"name": e, "keywords": by_expr[e]} for e in expressions],
        "has_idle": os.path.isfile(
            os.path.join(model_dir, MOTIONS_SUBDIR, f"{IDLE_CLIP}.vrma")
        ),
        "orphan_keywords": orphans,
    }


def _duplicate_keyword(mapping: dict) -> Optional[str]:
    seen: dict = {}
    for keyword in mapping:
        lowered = keyword.lower() if isinstance(keyword, str) else keyword
        if lowered in seen:
            return (
                f"duplicate keyword (case-insensitive): '{seen[lowered]}' and "
                f"'{keyword}' both resolve to '{lowered}'"
            )
        seen[lowered] = keyword
    return None


def validate_vrm_motion_map(motion_map, clips: set) -> Optional[str]:
    """None 代表合法。值必須是 {clip} 且 clip 存在於 motions/。"""
    if not isinstance(motion_map, dict):
        return "motionMap must be an object"
    dup = _duplicate_keyword(motion_map)
    if dup:
        return dup
    for keyword, target in motion_map.items():
        if not isinstance(target, dict) or "clip" not in target:
            return f"motionMap['{keyword}'] must be an object with a clip (VRM has no group/index)"
        if target["clip"] not in clips:
            return f"motionMap['{keyword}'] points at clip {target['clip']!r}, which this model does not have"
    return None


def validate_vrm_emotion_map(emotion_map, expressions: set) -> Optional[str]:
    """None 代表合法。值必須是模型裡存在的表情名（字串）。"""
    if not isinstance(emotion_map, dict):
        return "emotionMap must be an object"
    dup = _duplicate_keyword(emotion_map)
    if dup:
        return dup
    for keyword, name in emotion_map.items():
        if not isinstance(name, str):
            return f"emotionMap['{keyword}'] must be an expression name string, got {name!r}"
        if name not in expressions:
            return f"emotionMap['{keyword}'] points at expression {name!r}, which this model does not have"
    return None
