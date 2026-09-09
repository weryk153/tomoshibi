"""Live2D model motion/hit-area configuration — read side.

==========================================
Localhost-only REST endpoints that let the in-app "motion config" UI show the
user every motion and hit area a model *actually has*, merged with whatever
the user already assigned in ``model_dict.json``'s ``motionMap``/
``tapMotions`` (GET), and let them persist a new ``motionMap``/``tapMotions``
for one model (PUT).

Design notes:
- Standard Cubism 4 convention: a motion is addressed by (group name, index
  within that group's array in ``FileReferences.Motions``); a hit area by its
  ``HitAreas[].Id``. This module speaks that vocabulary, not our own.
- A motion group name CAN be the empty string (``mao_pro`` keeps all six of
  its usable motions in the unnamed group) — that is legal Cubism, not a
  missing group. Never filter it out.
- The path from a ``model_dict.json`` entry to its ``.model3.json`` is not
  uniform across model folders (nesting, filename case, unrelated filename).
  REUSE ``character_route._find_model3`` (already proven against all four
  bundled models) instead of assuming ``<folder>/<folder>.model3.json``.
- ``live2d-models/`` and ``model_dict.json`` are READ-ONLY from here.
- ``reserved`` marks a group the automatic idle/talk pipeline already uses
  (``Idle``, the model's own ``idleMotionGroupName``, or ``Talk``) — the UI
  should flag it, but it is still listed; excluding it is a UI decision, not
  this endpoint's.
- ``orphan_keywords`` surfaces ``motionMap`` entries that point at a
  (group, index) which no longer exists (hand-edited model_dict.json, or the
  model file was swapped) — these must never be silently dropped, since the
  UI needs them to show the user something is broken.
- ``tapMotions`` has a legacy per-hit-area shape (``{groupName: weight}``)
  alongside the newer list shape (``[{group, index, weight}]``); both are
  normalized to the list shape here so downstream code only has to handle one
  shape.
"""

import os
import json
import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from loguru import logger

# REUSE the localhost+proxy guard — do not diverge (see character_route.py).
from .api_guard import is_trusted_request as _is_local_request, forbidden as _forbidden
from .avatar_model import normalize_tap_motions as _normalize_tap_motions
from .live2d_discovery import is_discoverable_live2d_dir

# REUSE the generic model3.json resolver + model_dict reader/writer — already
# proven against all four bundled models (nested runtime/, filename-case
# mismatch, and an unrelated filename). Do NOT reimplement "filename == folder
# name" like routes.py's GET /live2d-models/info does — it fails on two of
# the four.
from .character_route import (
    _find_model3,
    _load_model_dict,
    _write_model_dict_atomic,
    LIVE2D_DIR,
)


# --------------------------------------------------------------------------- #
# Pure helpers (unit-testable without FastAPI/TestClient)
# --------------------------------------------------------------------------- #


def _find_model_entry(model_dict: list, name: str) -> Optional[dict]:
    """First model_dict.json entry whose ``name`` matches, or None."""
    for entry in model_dict:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    return None


def _target_key(target: dict) -> tuple:
    """(group, index) key for a motionMap entry, safe for hand-edited files.

    `index` is used as part of a dict/set key, so an unhashable value from a
    hand-edited model_dict.json (`"index": [0]` or `{}`) would raise TypeError
    before any parsing guard could catch it -- surfacing as an uncaught 500 that
    makes the settings page unopenable, which is exactly the failure this
    endpoint exists to help the user recover from. Coerce anything unhashable to
    its repr so it lands in orphan_keywords like every other malformed index.
    """
    group = target.get("group", "")
    index = target.get("index")
    if not isinstance(group, str):
        group = repr(group)
    try:
        hash(index)
    except TypeError:
        index = repr(index)
    return (group, index)


def build_model_config(name: str) -> Optional[dict]:
    """Enumerate ``name``'s real motions/hit-areas and merge model_dict.json.

    Returns None when ``name`` isn't a registered model_dict entry, or its
    ``.model3.json`` can't be found/parsed (broken/missing model folder) — the
    caller maps that to a 404, since either case means "nothing to show".
    """
    model_dict = _load_model_dict()
    entry = _find_model_entry(model_dict, name)
    if entry is None:
        return None

    if entry.get("type") == "vrm":
        from .vrm_models import build_vrm_model_config

        return build_vrm_model_config(entry)

    model_dir = os.path.join(LIVE2D_DIR, name)
    model3_path = _find_model3(model_dir)
    if model3_path is None:
        logger.warning(f"live2d model-config: no .model3.json found for '{name}'")
        return None

    try:
        with open(model3_path, "r", encoding="utf-8") as f:
            model3 = json.load(f)
    except Exception as e:
        logger.error(
            f"live2d model-config: unreadable model3.json for '{name}': {type(e).__name__}"
        )
        return None

    file_refs = model3.get("FileReferences", {}) or {}
    motions_by_group = file_refs.get("Motions", {})
    # HitAreas is a ROOT-level key, not under FileReferences — confirmed against
    # the official Cubism Framework parser (cubismmodelsettingjson.ts does
    # getRoot().getValueByString("HitAreas")) and against all four bundled
    # models. Reading it from FileReferences returns [] for every real model.
    hit_areas_raw = model3.get("HitAreas", []) or []

    # The group the automatic idle loop plays. Falls back to the literal
    # "Idle" the same way character_route._detect_idle_group does, so a model
    # without an explicit idleMotionGroupName still flags its "Idle" group.
    idle_group = entry.get("idleMotionGroupName") or "Idle"

    # Index the model's existing motionMap by the (group, index) it points at.
    # `label` lives on the KEYWORD, not on the motion — two different keywords
    # can legitimately point at the same (group, index) with two different
    # labels, so each target key collects a LIST of {keyword, label} in the
    # order they appear in motionMap (dict insertion order is preserved by
    # json.load). A singular "primary" field here would silently drop every
    # keyword but the last one that shares a target.
    motion_map = entry.get("motionMap", {}) or {}
    mappings_by_target: dict = {}
    if isinstance(motion_map, dict):
        for keyword, target in motion_map.items():
            if not isinstance(target, dict):
                continue
            key = _target_key(target)
            mappings_by_target.setdefault(key, []).append(
                {"keyword": keyword, "label": target.get("label")}
            )

    motions = []
    real_motion_keys = set()
    if isinstance(motions_by_group, dict):
        for group, defs in motions_by_group.items():
            if not isinstance(defs, list):
                continue
            for index, motion_def in enumerate(defs):
                key = (group, index)
                real_motion_keys.add(key)
                motions.append(
                    {
                        "group": group,
                        "index": index,
                        "file": (motion_def or {}).get("File", "")
                        if isinstance(motion_def, dict)
                        else "",
                        "reserved": group == "Idle"
                        or group == idle_group
                        or group == "Talk",
                        "mappings": mappings_by_target.get(key, []),
                    }
                )

    # motionMap entries whose (group, index) doesn't correspond to any real
    # motion — a hand-edited model_dict.json or a swapped model file. Must be
    # surfaced, never silently dropped.
    orphan_keywords = []
    if isinstance(motion_map, dict):
        for keyword, target in motion_map.items():
            if not isinstance(target, dict):
                continue
            key = _target_key(target)
            if key not in real_motion_keys:
                orphan_keywords.append(
                    {"keyword": keyword, "group": key[0], "index": key[1]}
                )

    hit_areas = [
        {"id": ha.get("Id", ""), "name": ha.get("Name", "")}
        for ha in hit_areas_raw
        if isinstance(ha, dict)
    ]

    tap_motions = _normalize_tap_motions(entry.get("tapMotions", {}))

    # 表情跟動作反過來：動作用 (group, index) 定位，表情只有一個陣列索引。
    # emotionMap 是 {關鍵字: 索引}，這裡反轉成「每個表情被哪些關鍵字指到」，
    # 跟動作那邊每個 (group,index) 收一串 mappings 是同一個形狀——兩個關鍵字
    # 指向同一個表情是合法的，所以收的是 list 不是單一值。
    keywords_by_index: dict = {}
    emotion_map = entry.get("emotionMap", {})
    if isinstance(emotion_map, dict):
        for keyword, index in emotion_map.items():
            keywords_by_index.setdefault(index, []).append(keyword)

    expressions = [
        {
            "name": str(exp.get("Name", "")).strip(),
            "index": i,
            "keywords": keywords_by_index.get(i, []),
        }
        for i, exp in enumerate(file_refs.get("Expressions", []) or [])
        if isinstance(exp, dict)
    ]

    return {
        "name": name,
        "motions": motions,
        "hit_areas": hit_areas,
        "tap_motions": tap_motions,
        "expressions": expressions,
        "orphan_keywords": orphan_keywords,
    }


# --------------------------------------------------------------------------- #
# Write side (pure helpers, unit-testable without FastAPI/TestClient)
# --------------------------------------------------------------------------- #


def _real_motion_keys(model3: dict) -> set:
    """Every ``(group, index)`` this model's ``.model3.json`` actually has.

    Mirrors the enumeration in ``build_model_config`` — kept separate (rather
    than refactored to share code) so this module's read side stays untouched.
    A group name CAN be the empty string; that key still belongs in the set.
    """
    file_refs = model3.get("FileReferences", {}) or {}
    motions_by_group = file_refs.get("Motions", {})
    keys: set = set()
    if isinstance(motions_by_group, dict):
        for group, defs in motions_by_group.items():
            if not isinstance(defs, list):
                continue
            for index in range(len(defs)):
                keys.add((group, index))
    return keys


def _real_hit_area_ids(model3: dict) -> set:
    """Every ``HitAreas[].Id`` this model's ``.model3.json`` actually has."""
    # Root-level, not under FileReferences — see build_model_config.
    hit_areas = model3.get("HitAreas", []) or []
    return {ha.get("Id", "") for ha in hit_areas if isinstance(ha, dict)}


def _validate_motion_map(motion_map, real_motion_keys: set) -> Optional[str]:
    """None if valid, else a human-readable reason.

    Two different keywords pointing at the same ``(group, index)`` is legal
    (two labels for one motion). The same keyword appearing twice is not:
    ``live2d_model.py`` lowercases every key when building ``motion_map``, so
    e.g. "Wave" and "wave" collide into one dict key and the scanner only
    ever matches whichever survives — the other is dead config. An
    empty-string ``group`` is legal Cubism (the unnamed group), so membership
    in ``real_motion_keys`` is checked directly rather than via truthiness.
    """
    if not isinstance(motion_map, dict):
        return "motionMap must be an object"

    seen: dict = {}
    for keyword, target in motion_map.items():
        lowered = keyword.lower() if isinstance(keyword, str) else keyword
        if lowered in seen:
            return (
                f"duplicate keyword (case-insensitive): '{seen[lowered]}' and "
                f"'{keyword}' both resolve to '{lowered}' — the scanner only "
                "ever matches the first one, the other is dead config"
            )
        seen[lowered] = keyword

        if not isinstance(target, dict):
            return f"motionMap['{keyword}'] must be an object with group/index"
        group = target.get("group", "")
        index = target.get("index")
        if (group, index) not in real_motion_keys:
            return (
                f"motionMap['{keyword}'] points at group={group!r} index={index!r}, "
                "which this model does not have"
            )
    return None


def _real_expression_count(model3: dict) -> int:
    """幾個表情。emotionMap 的值是這個陣列的索引，合法範圍就是 0..count-1。"""
    expressions = (model3.get("FileReferences", {}) or {}).get("Expressions", []) or []
    return len(expressions)


def _validate_emotion_map(emotion_map, expression_count: int) -> Optional[str]:
    """None if valid, else a human-readable reason.

    兩個關鍵字指向同一個表情是合法的（一張臉可以同時是 joy 和 smug）。同一個
    關鍵字出現兩次不是：``live2d_model.py`` 建 ``emo_map`` 時把每個 key 轉小寫，
    "Joy" 和 "joy" 會併成一個 dict key，另一個變成永遠比不到的死設定——跟
    ``_validate_motion_map`` 擋重複關鍵字是同一個理由。

    索引必須真的落在這個模型的表情陣列裡。這條是這個驗證存在的主因：手改
    ``model_dict.json`` 時，只要 ``model3.json`` 的表情增刪過，後面的索引就
    整批位移，指到的會是另一張完全不相干的臉，而且不會有任何錯誤訊息。
    """
    if not isinstance(emotion_map, dict):
        return "emotionMap must be an object"

    seen: dict = {}
    for keyword, index in emotion_map.items():
        lowered = keyword.lower() if isinstance(keyword, str) else keyword
        if lowered in seen:
            return (
                f"duplicate keyword (case-insensitive): '{seen[lowered]}' and "
                f"'{keyword}' both resolve to '{lowered}' — live2d_model lowercases "
                "every key, so only one of them can ever match"
            )
        seen[lowered] = keyword

        # bool 是 int 的子類別，True 會被當成索引 1 溜過去。
        if not isinstance(index, int) or isinstance(index, bool):
            return f"emotionMap['{keyword}'] must be an integer expression index, got {index!r}"
        if not 0 <= index < expression_count:
            return (
                f"emotionMap['{keyword}'] points at expression index {index}, "
                f"but this model has {expression_count} expression(s)"
            )
    return None


def _validate_tap_motions(
    tap_motions, real_hit_area_ids: set, real_motion_keys: set
) -> Optional[str]:
    """None if valid, else a human-readable reason.

    Shape: ``{hitAreaId: [{group, index, weight}, ...]}``. ``index`` of
    ``None`` means "random within group", so only the group itself needs to
    exist in that case. As in ``_validate_motion_map``, an empty-string
    ``group`` is legal and never treated as missing.
    """
    if not isinstance(tap_motions, dict):
        return "tapMotions must be an object"

    real_groups = {group for group, _index in real_motion_keys}
    for area_id, entries in tap_motions.items():
        if area_id not in real_hit_area_ids:
            return f"tapMotions references hit area '{area_id}', which this model does not have"
        if not isinstance(entries, list):
            return f"tapMotions['{area_id}'] must be a list"
        for item in entries:
            if not isinstance(item, dict):
                return f"tapMotions['{area_id}'] entries must be objects"
            group = item.get("group", "")
            index = item.get("index")
            if index is None:
                if group not in real_groups:
                    return (
                        f"tapMotions['{area_id}'] references group={group!r}, "
                        "which this model does not have"
                    )
            elif (group, index) not in real_motion_keys:
                return (
                    f"tapMotions['{area_id}'] points at group={group!r} index={index!r}, "
                    "which this model does not have"
                )
    return None


def _refresh_live2d_caches(name: str, default_context_cache, client_contexts) -> None:
    """Reload ``motion_map``/``motion_str``（以及 ``emo_map``/``emo_str``）in
    place for every live ``AvatarModel`` currently showing ``name``.

    ``set_model()`` 重建的是整份 ``model_info``，動作與表情兩套對應都是在同一
    個地方建起來的，所以這裡不必分開處理。

    ``default_context_cache.live2d_model`` is the SAME object reference every
    fresh session gets handed by ``websocket_handler.py``'s
    ``WebSocketHandler._init_service_context`` (``live2d_model=self.
    default_context_cache.live2d_model``) — calling ``set_model()`` on it in
    place refreshes every session still sharing that reference immediately,
    no restart needed. A session that has done a character switch
    (``handle_config_switch`` -> ``load_from_config`` -> ``init_live2d``)
    builds its OWN ``AvatarModel`` instance instead, so ``client_contexts``
    (``WebSocketHandler.client_contexts: Dict[str, ServiceContext]``) is
    walked separately and each session's own instance refreshed too — but
    only when it is currently showing the model that was just edited; a
    session on a different model is left alone.
    """
    refreshed_ids: set = set()

    shared_model = (
        getattr(default_context_cache, "live2d_model", None)
        if default_context_cache is not None
        else None
    )
    if (
        shared_model is not None
        and getattr(shared_model, "live2d_model_name", None) == name
    ):
        shared_model.set_model(name)
        refreshed_ids.add(id(shared_model))

    if client_contexts:
        for ctx in client_contexts.values():
            model = getattr(ctx, "live2d_model", None)
            if model is None or id(model) in refreshed_ids:
                continue
            if getattr(model, "live2d_model_name", None) == name:
                model.set_model(name)
                refreshed_ids.add(id(model))


def write_model_config(
    name: str,
    motion_map: dict,
    tap_motions: dict,
    default_context_cache=None,
    client_contexts=None,
    emotion_map: Optional[dict] = None,
) -> dict:
    """Validate, then persist ``motionMap``/``tapMotions``（以及可選的
    ``emotionMap``）for one model.

    ``emotion_map`` 是 None 代表「這次不動表情設定」，不是「清空」——動作那半
    的存檔不會帶它，不能因此把表情對應洗掉。要清空就傳空 dict。

    Re-reads ``model_dict.json`` fresh right before writing and replaces only
    the target entry's ``motionMap``/``tapMotions`` — every other entry, and
    every other key on the target entry (``emotionMap``, ``kScale``,
    ``description``, ``url``, ...), is carried through untouched.
    ``scan_and_register_skins()`` holds no lock and may append a new model
    between an earlier read and this write, so the list read for validation
    above is never the one written back — a fresh read is fetched immediately
    before mutating and writing.

    On success, refreshes every live ``AvatarModel`` currently showing
    ``name`` in place (see ``_refresh_live2d_caches``) so sessions pick up
    the edit with no restart and no character switch required.

    Returns a dict with ``ok``; on failure also ``status`` (int) and
    ``error`` (str) for the route wrapper to turn into an HTTP response.
    """
    model_dict = _load_model_dict()
    entry = _find_model_entry(model_dict, name)
    if entry is None:
        return {"ok": False, "status": 404, "error": f"Unknown Live2D model: {name}"}

    if entry.get("type") == "vrm":
        from .vrm_models import (
            VRM_DIR,
            find_vrm_file,
            list_vrm_clips,
            read_vrm_expressions,
            validate_vrm_emotion_map,
            validate_vrm_motion_map,
        )

        model_dir = os.path.join(VRM_DIR, name)
        vrm_path = find_vrm_file(model_dir)
        if not vrm_path:
            return {"ok": False, "status": 404, "error": f"Unknown VRM model: {name}"}
        error = validate_vrm_motion_map(motion_map, set(list_vrm_clips(model_dir)))
        if error is None and tap_motions:
            error = "tapMotions must be empty for a VRM model (no hit areas)"
        if error is None and emotion_map is not None:
            error = validate_vrm_emotion_map(
                emotion_map, set(read_vrm_expressions(vrm_path) or [])
            )
        if error is not None:
            return {"ok": False, "status": 400, "error": error}
        write_dict = _load_model_dict()
        write_entry = _find_model_entry(write_dict, name)
        if write_entry is None:
            return {"ok": False, "status": 404, "error": f"Unknown VRM model: {name}"}
        write_entry["motionMap"] = motion_map
        write_entry["tapMotions"] = {}
        if emotion_map is not None:
            write_entry["emotionMap"] = emotion_map
        _write_model_dict_atomic(write_dict)
        _refresh_live2d_caches(name, default_context_cache, client_contexts)
        return {"ok": True, "restart_required": False}

    model_dir = os.path.join(LIVE2D_DIR, name)
    model3_path = _find_model3(model_dir)
    if model3_path is None:
        logger.warning(f"live2d model-config write: no .model3.json found for '{name}'")
        return {"ok": False, "status": 404, "error": f"Unknown Live2D model: {name}"}

    try:
        with open(model3_path, "r", encoding="utf-8") as f:
            model3 = json.load(f)
    except Exception as e:
        logger.error(
            f"live2d model-config write: unreadable model3.json for '{name}': {type(e).__name__}"
        )
        return {"ok": False, "status": 404, "error": f"Unknown Live2D model: {name}"}

    real_motion_keys = _real_motion_keys(model3)
    real_hit_area_ids = _real_hit_area_ids(model3)

    error = _validate_motion_map(motion_map, real_motion_keys)
    if error is None:
        error = _validate_tap_motions(tap_motions, real_hit_area_ids, real_motion_keys)
    if error is None and emotion_map is not None:
        error = _validate_emotion_map(emotion_map, _real_expression_count(model3))
    if error is not None:
        return {"ok": False, "status": 400, "error": error}

    # Re-read fresh right before writing — see docstring above.
    write_dict = _load_model_dict()
    write_entry = _find_model_entry(write_dict, name)
    if write_entry is None:
        return {"ok": False, "status": 404, "error": f"Unknown Live2D model: {name}"}
    write_entry["motionMap"] = motion_map
    write_entry["tapMotions"] = tap_motions
    if emotion_map is not None:
        write_entry["emotionMap"] = emotion_map
    _write_model_dict_atomic(write_dict)

    _refresh_live2d_caches(name, default_context_cache, client_contexts)

    return {"ok": True, "restart_required": False}


# --------------------------------------------------------------------------- #
# Route factory
# --------------------------------------------------------------------------- #

_THUMB_NAMES = (
    "thumbnail.png",
    "thumbnail.jpg",
    "thumbnail.jpeg",
    "thumbnail.webp",
    "preview.png",
    "preview.jpg",
    "icon.png",
)


def _detect_idle_group(model3_path: str) -> str:
    """Read FileReferences.Motions and pick the idle group ('Idle' preferred)."""
    try:
        with open(model3_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        motions = data.get("FileReferences", {}).get("Motions", {})
        if isinstance(motions, dict):
            if "Idle" in motions:
                return "Idle"
            for key in motions.keys():
                if key:  # first non-empty key
                    return key
            # 空字串是合法的群組名，不是「沒有群組」——mao_pro 把六個動作放在
            # 無名群組，VTube Studio 匯出的模型（Frieren）更是只有無名群組。
            # 濾掉它就會回退到下面那個 "Idle"，指向模型裡不存在的群組，待機動作
            # 永遠不會播。同一條規則見 live2d_config_route 的模組註解。
            if "" in motions:
                return ""
    except Exception as e:
        logger.debug(f"idle-group detect failed for {model3_path}: {type(e).__name__}")
    # Frontend tolerates a missing group; 'Idle' is the safe default.
    return "Idle"


def _find_skin_thumbnail(folder: str, name: str) -> Optional[str]:
    """Web URL for a player-supplied thumbnail inside the model folder, or None.
    Lets a user give their own Live2D model a picker preview by dropping a
    thumbnail.png next to the model3.json."""
    for fn in (*_THUMB_NAMES, f"{name}.png", f"{name}.jpg"):
        if os.path.isfile(os.path.join(folder, fn)):
            return f"/{LIVE2D_DIR}/{name}/{fn}"
    return None


def scan_and_register_skins() -> dict:
    """Scan live2d-models/, auto-register any unregistered valid model, return list.

    Returns ``{"skins": [{"name","registered","thumbnail"}...], "newly_registered": [...]}``.
    A model is VALID iff its top-level folder contains a *.model3.json (recursive,
    depth-capped). The folder name IS the value used in live2d_model_name AND the
    model_dict ``name``. Idempotent: only writes model_dict.json when something is
    missing.
    """
    model_dict = _load_model_dict()
    registered_names = {m.get("name") for m in model_dict if isinstance(m, dict)}

    newly_registered = []
    found_skins = []  # preserve discovery order, dedupe by name
    thumb_by_name: dict = {}  # name -> player-supplied thumbnail URL (or None)

    if os.path.isdir(LIVE2D_DIR):
        for entry in sorted(os.listdir(LIVE2D_DIR)):
            if not is_discoverable_live2d_dir(entry):
                continue
            folder = os.path.join(LIVE2D_DIR, entry)
            if not os.path.isdir(folder):
                continue
            model3 = _find_model3(folder)
            if not model3:
                continue  # not a valid Live2D model folder
            name = entry  # top-level folder name
            found_skins.append(name)
            thumb_by_name[name] = _find_skin_thumbnail(folder, name)

            if name not in registered_names:
                # Build the web-served URL relative to LIVE2D_DIR.
                rel = os.path.relpath(model3, LIVE2D_DIR).replace(os.sep, "/")
                idle_group = _detect_idle_group(model3)
                entry_obj = {
                    "name": name,
                    "description": "自動偵測並註冊的 Live2D 模型",
                    "url": f"/{LIVE2D_DIR}/{rel}",
                    "kScale": 0.5,
                    "initialXshift": 0,
                    "initialYshift": 0,
                    "idleMotionGroupName": idle_group,
                    "emotionMap": {
                        "neutral": 0
                    },  # MUST be non-empty (set_model KeyErrors otherwise)
                    "tapMotions": {},
                    "motionMap": {},
                }
                model_dict.append(entry_obj)
                registered_names.add(name)
                newly_registered.append(name)

    if newly_registered:
        _write_model_dict_atomic(model_dict)
        logger.info(f"Auto-registered Live2D skins: {newly_registered}")

    skins = [
        {"name": n, "registered": True, "thumbnail": thumb_by_name.get(n)}
        for n in dict.fromkeys(found_skins)
    ]
    return {"skins": skins, "newly_registered": newly_registered}


def list_all_skins() -> dict:
    """Live2D 與 VRM 兩邊的掃描結果合併；每筆帶 ``type``。

    ``type`` 是給之後與診斷用的：目前前端的皮膚選單（characters.tsx）只取 ``name``
    跟 ``thumbnail``，會把 ``type`` 丟掉，沒有任何 UI 行為靠它。
    """
    from .vrm_models import scan_and_register_vrm

    live2d = scan_and_register_skins()
    for skin in live2d["skins"]:
        skin["type"] = "live2d"
    vrm = scan_and_register_vrm()
    return {
        "skins": live2d["skins"] + vrm["skins"],
        "newly_registered": live2d["newly_registered"] + vrm["newly_registered"],
    }


def init_live2d_config_route(
    default_context_cache=None, client_contexts=None
) -> APIRouter:
    """REST endpoints for the in-app motion/hit-area config UI. Localhost-only.

    - GET /api/live2d/model-config/{name} -> enumerate motions/hit areas and
      merge in the model's existing motionMap/tapMotions.
    - PUT /api/live2d/model-config/{name} -> validate and persist a new
      motionMap/tapMotions for that model, then refresh any live AvatarModel
      currently showing it (see write_model_config/_refresh_live2d_caches).

    Args:
        default_context_cache: the process's ServiceContext (its
            ``live2d_model`` is the reference every fresh session shares).
            Passed through to write_model_config for the post-write refresh;
            the endpoint still works without it (refresh becomes a no-op),
            which keeps this router constructible with no arguments.
        client_contexts: ``WebSocketHandler.client_contexts`` (``Dict[str,
            ServiceContext]``) — sessions that hold their own AvatarModel
            instance after a character switch. Same optional/no-op fallback.
    """
    router = APIRouter()

    @router.get("/api/live2d-skins")
    async def list_skins(request: Request):
        """掃描 live2d-models/，把還沒登記的模型自動加進 model_dict.json。

        使用者把模型資料夾丟進去就該出現在清單上，不必手動編輯 JSON。
        """
        if not _is_local_request(request):
            return _forbidden()
        try:
            result = await asyncio.to_thread(list_all_skins)
        except Exception as e:
            logger.error(f"[live2d] skin scan failed: {type(e).__name__}")
            return JSONResponse(status_code=500, content={"error": "skin scan failed"})
        return JSONResponse(result)

    @router.get("/api/live2d/model-config/{name}")
    async def get_model_config(name: str, request: Request):
        if not _is_local_request(request):
            return _forbidden()
        result = await asyncio.to_thread(build_model_config, name)
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": f"Unknown Live2D model: {name}"},
            )
        return JSONResponse(result)

    @router.put("/api/live2d/model-config/{name}")
    async def put_model_config(name: str, request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "invalid JSON body"},
            )
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "request body must be an object"},
            )
        motion_map = body.get("motionMap", {})
        tap_motions = body.get("tapMotions", {})
        # 沒帶 emotionMap 就是 None 而不是 {}——None 代表「這次不動表情設定」。
        # 動作設定那半存檔時不會帶它，用 {} 當預設會把表情對應整個洗掉。
        emotion_map = body.get("emotionMap")
        result = await asyncio.to_thread(
            write_model_config,
            name,
            motion_map,
            tap_motions,
            default_context_cache,
            client_contexts,
            emotion_map,
        )
        status = result.get("status", 200 if result.get("ok") else 400)
        content = {k: v for k, v in result.items() if k != "status"}
        return JSONResponse(status_code=status, content=content)

    return router
