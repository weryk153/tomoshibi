"""模型家族 → 偵測不到的必要設定。

界線：只放 API 不會告訴你、但不設就會壞的東西。偵測得到的（is_vlm /
supports_tools / max_context）由 model_probe 直接回，不進這裡。

note 必填是防腐設計。範圍是「不設就像壞掉」，所以每條都必須說得出它防的是哪
種壞掉；寫不出來的就不該進這個檔。載入時檢查，缺的丟掉並記 warning。它同時
會顯示在首次啟動精靈上，讓使用者知道為什麼有東西被設了。
"""

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from .model_probe import DetectedModel

DEFAULT_PATH = "model_profiles.yaml"
_FALLBACK_MODEL = "qwen2.5:3b"


def normalize(raw: Any) -> dict:
    """把讀進來的東西整理成可信的結構。壞掉的項目丟掉，不讓它們害整個檔失效。"""
    if not isinstance(raw, dict):
        return {"profiles": [], "recommended_models": [], "fallback": _FALLBACK_MODEL}

    profiles = []
    for entry in raw.get("profiles") or []:
        if not isinstance(entry, dict):
            continue
        arches = entry.get("match_arch")
        arches = [str(a).strip().lower() for a in arches] if isinstance(arches, list) else []
        extra_body = entry.get("extra_body")
        note = str(entry.get("note") or "").strip()
        if not arches or not isinstance(extra_body, dict) or not extra_body:
            logger.warning(f"[profiles] 略過缺 match_arch 或 extra_body 的項目：{entry!r}")
            continue
        if not note:
            logger.warning(
                f"[profiles] 略過缺 note 的項目（說不出防的是哪種壞掉的不收）：{arches}"
            )
            continue
        backend = entry.get("match_backend")
        profiles.append(
            {
                "match_arch": arches,
                "match_backend": str(backend).strip().lower() if backend else None,
                "extra_body": {str(k): str(v) for k, v in extra_body.items()},
                "note": note,
            }
        )

    tiers = []
    for tier in raw.get("recommended_models") or []:
        if isinstance(tier, dict) and tier.get("model"):
            tiers.append(
                {"max_ram_gb": tier.get("max_ram_gb"), "model": str(tier["model"])}
            )

    return {
        "profiles": profiles,
        "recommended_models": tiers,
        "fallback": str(raw.get("fallback") or _FALLBACK_MODEL),
    }


def load_data(path: str | None = None) -> dict:
    """讀整份資料檔。讀不到就回一份空的——沒有 profile 只代表不套任何怪癖設定，
    不該讓首次啟動精靈壞掉。"""
    target = Path(path or DEFAULT_PATH)
    try:
        with open(target, "r", encoding="utf-8") as f:
            return normalize(yaml.safe_load(f))
    except Exception as e:
        logger.debug(f"[profiles] 讀不到 {target}: {type(e).__name__}")
        return normalize(None)


def load_profiles(path: str | None = None) -> list[dict]:
    return load_data(path)["profiles"]


def profile_for(
    model: DetectedModel, profiles: list[dict] | None = None
) -> dict | None:
    """這顆模型要不要套什麼必要設定。查不到回 None——不猜、不套通用建議值。

    對未經 normalize() 的 profiles 也成立：match_arch / match_backend 兩邊都
    在這裡自行 strip().lower()，不假設呼叫端已經正規化過。這是刻意的保證，
    不是巧合——`profiles` 是公開可直接傳入的參數，靜默比不中正是這個檔案要
    防止的那類失敗。
    """
    if not model.arch:
        return None
    candidates = load_profiles() if profiles is None else profiles
    arch = model.arch.strip().lower()
    backend = (model.backend or "").strip().lower()

    hits = [
        p
        for p in candidates
        if arch in [a.strip().lower() for a in p.get("match_arch", [])]
        and (
            not p.get("match_backend")
            or str(p["match_backend"]).strip().lower() == backend
        )
    ]
    if not hits:
        return None
    if len(hits) > 1:
        logger.warning(
            f"[profiles] {arch}/{backend} 命中 {len(hits)} 條 profile，取第一條。"
            "重疊代表資料檔該整理。"
        )
    return hits[0]


def recommended_model(total_ram_bytes: int | None, data: dict | None = None) -> str:
    """依 RAM 建議下載哪顆模型。測不到、或分層表為空，都回 fallback。"""
    source = load_data() if data is None else data
    fallback = str(source.get("fallback") or _FALLBACK_MODEL)
    tiers = source.get("recommended_models") or []
    if total_ram_bytes is None or not tiers:
        return fallback

    gb = total_ram_bytes / (1024**3)
    for tier in tiers:
        cap = tier.get("max_ram_gb")
        if cap is None or gb <= float(cap):
            return str(tier["model"])
    return fallback
