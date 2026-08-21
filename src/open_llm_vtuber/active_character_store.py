"""Persist the character selected most recently by the user.

The active character is runtime state, not configuration: rewriting ``conf.yaml``
would mix a UI selection into the user's base character settings.  Keep the tiny
state file beside the ignored character overrides instead.
"""

from __future__ import annotations

import json
import os
import threading


STORE_PATH = os.path.join("characters", ".active-character.json")

_LOCK = threading.RLock()


def _validate_filename(value: object) -> str:
    filename = str(value or "").strip()
    if (
        not filename
        or os.path.basename(filename) != filename
        or not filename.endswith(".yaml")
    ):
        raise ValueError("Invalid active character filename.")
    return filename


def get_active_character_filename() -> str | None:
    """Return the saved filename, or ``None`` for absent/corrupt state."""
    with _LOCK:
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                return None
            return _validate_filename(data.get("filename"))
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError, TypeError):
            return None


def set_active_character_filename(filename: str) -> None:
    """Atomically save a validated character config filename."""
    clean_filename = _validate_filename(filename)
    with _LOCK:
        directory = os.path.dirname(STORE_PATH)
        os.makedirs(directory, exist_ok=True)
        temp_path = STORE_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(
                {"version": 1, "filename": clean_filename},
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        os.replace(temp_path, STORE_PATH)
