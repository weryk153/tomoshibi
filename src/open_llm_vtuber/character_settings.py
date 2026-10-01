"""角色擁有的設定：寫在那個角色自己的檔案裡。

底稿角色的檔案是 conf.yaml 的 character_config；其他角色是 characters/<檔名>。
一律用 round-trip 改那幾個鍵，註解與其他欄位原樣留著。
"""

from __future__ import annotations

import os
from typing import Any, Optional

from .api_guard import make_yaml
from .conf_editor import CONF_PATH, write_conf_document

OWNED: dict[str, tuple[str, ...]] = {
    "tts_model": ("tts_config", "tts_model"),
    "voice": ("tts_config", "edge_tts", "voice"),
    "voice_lang": ("tts_config", "gpt_sovits_tts", "text_lang"),
    "ref_audio_path": ("tts_config", "gpt_sovits_tts", "ref_audio_path"),
    "prompt_text": ("tts_config", "gpt_sovits_tts", "prompt_text"),
    "prompt_lang": ("tts_config", "gpt_sovits_tts", "prompt_lang"),
    "reply_language": ("reply_language",),
    "translate_subtitle": (
        "tts_preprocessor_config",
        "translator_config",
        "translate_subtitle",
    ),
    "long_term_memory_enabled": ("long_term_memory_enabled",),
}
TOGGLES = ("translate_subtitle", "long_term_memory_enabled")
DEFAULTS: dict[str, Any] = {
    "translate_subtitle": False,
    "long_term_memory_enabled": True,
}


def file_for(filename: str) -> Optional[str]:
    from .character_route import _safe_character_path

    if filename == "conf.yaml":
        return CONF_PATH
    path = _safe_character_path(filename)
    return path if path and os.path.isfile(path) else None


def filename_for_uid(conf_uid: str) -> Optional[str]:
    from .character_route import _conf_uid_of, _list_character_files

    if _conf_uid_of(CONF_PATH) == conf_uid:
        return "conf.yaml"
    for path in _list_character_files():
        if _conf_uid_of(path) == conf_uid:
            return os.path.basename(path)
    return None


def _load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return make_yaml().load(f) or {}


def _dig(node: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def effective(filename: str) -> dict[str, Any]:
    base = (_load(CONF_PATH).get("character_config")) or {}
    own: dict = {}
    if filename != "conf.yaml":
        path = file_for(filename)
        own = ((_load(path).get("character_config")) or {}) if path else {}
    values = {}
    for name, path in OWNED.items():
        value = _dig(own, path)
        if value is None:
            value = _dig(base, path)
        values[name] = DEFAULTS.get(name, "") if value is None else value
    return values


def _set(node: dict, path: tuple[str, ...], value: Any) -> None:
    for key in path[:-1]:
        if not isinstance(node.get(key), dict):
            node[key] = {}
        node = node[key]
    node[path[-1]] = value


def write(filename: str, changes: dict[str, Any]) -> None:
    path = file_for(filename)
    if path is None:
        raise FileNotFoundError(filename)
    yaml = make_yaml()
    yaml.allow_unicode = True
    data = _load(path)
    cc = data.setdefault("character_config", {})
    for name, value in changes.items():
        _set(cc, OWNED[name], value)
    if filename == "conf.yaml":
        write_conf_document(lambda f: yaml.dump(data, f))
        return
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    os.replace(tmp, path)
