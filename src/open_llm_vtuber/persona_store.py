"""Persistent, character-independent persona preset storage.

Personas deliberately live outside ``characters/``.  A persona changes only the
prompt used by the conversation agent; Live2D, voice, character identity, chat
history and long-term memory continue to belong to the active character.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from typing import Any


PERSONAS_DIR = "personas"
STORE_PATH = os.path.join(PERSONAS_DIR, "personas.json")

PERSONA_ID_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
MAX_NAME_LENGTH = 80
MAX_PROMPT_LENGTH = 20_000

_LOCK = threading.RLock()


def _empty_store() -> dict[str, Any]:
    return {"version": 1, "personas": [], "active_by_character": {}}


def _slugify(value: str) -> str:
    value = str(value or "").strip().lower().replace(" ", "_")
    value = re.sub(r"[^a-z0-9_-]", "", value).strip("_-")
    return value[:40]


def _read_store() -> dict[str, Any]:
    with _LOCK:
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
            return _empty_store()

        if not isinstance(raw, dict):
            return _empty_store()
        personas = raw.get("personas")
        active = raw.get("active_by_character")
        return {
            "version": 1,
            "personas": personas if isinstance(personas, list) else [],
            "active_by_character": active if isinstance(active, dict) else {},
        }


def _write_store(store: dict[str, Any]) -> None:
    with _LOCK:
        os.makedirs(PERSONAS_DIR, exist_ok=True)
        temp_path = STORE_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(store, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, STORE_PATH)


def _validate_fields(name: Any, prompt: Any) -> tuple[str, str]:
    clean_name = str(name or "").strip()
    clean_prompt = str(prompt or "").strip()
    if not clean_name:
        raise ValueError("Persona name is required.")
    if not clean_prompt:
        raise ValueError("Persona prompt is required.")
    if len(clean_name) > MAX_NAME_LENGTH:
        raise ValueError(f"Persona name must be at most {MAX_NAME_LENGTH} characters.")
    if len(clean_prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(
            f"Persona prompt must be at most {MAX_PROMPT_LENGTH} characters."
        )
    return clean_name, clean_prompt


def _unique_id(requested: Any, name: str, existing: set[str]) -> str:
    raw = str(requested or "").strip()
    if raw and not PERSONA_ID_RE.fullmatch(raw):
        raise ValueError("Persona ID must contain only lowercase letters, numbers, _ or -.")
    base = raw or _slugify(name) or f"persona_{uuid.uuid4().hex[:8]}"
    if base not in existing:
        return base
    for index in range(2, 1000):
        suffix = f"_{index}"
        candidate = f"{base[: 40 - len(suffix)]}{suffix}"
        if candidate not in existing:
            return candidate
    return f"persona_{uuid.uuid4().hex[:8]}"


def list_personas() -> list[dict[str, str]]:
    store = _read_store()
    result: list[dict[str, str]] = []
    for item in store["personas"]:
        if not isinstance(item, dict):
            continue
        persona_id = item.get("id")
        name = item.get("name")
        prompt = item.get("prompt")
        if (
            isinstance(persona_id, str)
            and PERSONA_ID_RE.fullmatch(persona_id)
            and isinstance(name, str)
            and isinstance(prompt, str)
        ):
            result.append({"id": persona_id, "name": name, "prompt": prompt})
    return result


def get_persona(persona_id: str) -> dict[str, str] | None:
    for item in list_personas():
        if item["id"] == persona_id:
            return item
    return None


def create_persona(name: Any, prompt: Any, requested_id: Any = None) -> dict[str, str]:
    clean_name, clean_prompt = _validate_fields(name, prompt)
    with _LOCK:
        store = _read_store()
        existing = {
            str(item.get("id"))
            for item in store["personas"]
            if isinstance(item, dict) and item.get("id")
        }
        persona_id = _unique_id(requested_id, clean_name, existing)
        item = {"id": persona_id, "name": clean_name, "prompt": clean_prompt}
        store["personas"].append(item)
        _write_store(store)
        return item


def update_persona(persona_id: str, name: Any, prompt: Any) -> dict[str, str]:
    if not PERSONA_ID_RE.fullmatch(str(persona_id or "")):
        raise ValueError("Invalid persona ID.")
    clean_name, clean_prompt = _validate_fields(name, prompt)
    with _LOCK:
        store = _read_store()
        for index, item in enumerate(store["personas"]):
            if isinstance(item, dict) and item.get("id") == persona_id:
                updated = {
                    "id": persona_id,
                    "name": clean_name,
                    "prompt": clean_prompt,
                }
                store["personas"][index] = updated
                _write_store(store)
                return updated
    raise KeyError(persona_id)


def delete_persona(persona_id: str) -> bool:
    if not PERSONA_ID_RE.fullmatch(str(persona_id or "")):
        return False
    with _LOCK:
        store = _read_store()
        before = len(store["personas"])
        store["personas"] = [
            item
            for item in store["personas"]
            if not (isinstance(item, dict) and item.get("id") == persona_id)
        ]
        if len(store["personas"]) == before:
            return False
        store["active_by_character"] = {
            conf_uid: active_id
            for conf_uid, active_id in store["active_by_character"].items()
            if active_id != persona_id
        }
        _write_store(store)
        return True


def is_persona_active(persona_id: str) -> bool:
    store = _read_store()
    return persona_id in store["active_by_character"].values()


def get_active_persona_id(conf_uid: str) -> str | None:
    if not conf_uid:
        return None
    store = _read_store()
    persona_id = store["active_by_character"].get(str(conf_uid))
    if not isinstance(persona_id, str) or get_persona(persona_id) is None:
        return None
    return persona_id


def set_active_persona(conf_uid: str, persona_id: str | None) -> None:
    clean_uid = str(conf_uid or "").strip()
    if not clean_uid:
        raise ValueError("Character ID is required.")
    if persona_id is not None and get_persona(persona_id) is None:
        raise KeyError(persona_id)
    with _LOCK:
        store = _read_store()
        if persona_id is None:
            store["active_by_character"].pop(clean_uid, None)
        else:
            store["active_by_character"][clean_uid] = persona_id
        _write_store(store)


def resolve_active_persona(conf_uid: str) -> dict[str, str] | None:
    persona_id = get_active_persona_id(conf_uid)
    return get_persona(persona_id) if persona_id else None
