"""Persist which conversation each character was last talking in.

A browser reload opens a fresh WebSocket, and a fresh WebSocket used to mean a
fresh empty conversation: the on-screen log was cleared and the agent's memory
was reset along with it.  The conversation itself was never lost — it stays in
``chat_history/<conf_uid>/`` — the connection simply had no way to know which
one to resume.

This is runtime state, not configuration, so it lives in a tiny state file next
to the histories it points at, mirroring ``active_character_store``.  It is
keyed by ``conf_uid`` because each character keeps its own conversations, and
switching character must not drag the previous one's transcript along.
"""

from __future__ import annotations

import json
import os
import threading


STORE_PATH = os.path.join("chat_history", ".active-history.json")

_LOCK = threading.RLock()


def _validate_component(value: object, label: str) -> str:
    """Reject anything that could escape the chat_history directory.

    The state file is read back as untrusted input — it is plain JSON a user or
    a stray process can edit — so uids are validated on the way out as well as
    on the way in.
    """
    component = str(value or "").strip()
    if (
        not component
        or component in {".", ".."}
        or os.path.basename(component) != component
        or "\\" in component
        or os.sep in component
    ):
        raise ValueError(f"Invalid {label}.")
    return component


def _read_state() -> dict:
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    histories = data.get("histories")
    return histories if isinstance(histories, dict) else {}


def _write_state(histories: dict) -> None:
    directory = os.path.dirname(STORE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temp_path = STORE_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(
            {"version": 1, "histories": histories},
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
    os.replace(temp_path, STORE_PATH)


def get_active_history_uid(conf_uid: str) -> str | None:
    """Return the saved conversation for a character, or ``None``.

    Absent, corrupt and unsafe state all resolve to ``None``: the caller then
    starts a new conversation, which is the old behaviour and always safe.
    """
    with _LOCK:
        try:
            clean_conf_uid = _validate_component(conf_uid, "conf_uid")
        except ValueError:
            return None
        stored = _read_state().get(clean_conf_uid)
        try:
            return _validate_component(stored, "history_uid")
        except ValueError:
            return None


def set_active_history_uid(conf_uid: str, history_uid: str) -> None:
    """Atomically record the conversation a character is now talking in."""
    clean_conf_uid = _validate_component(conf_uid, "conf_uid")
    clean_history_uid = _validate_component(history_uid, "history_uid")
    with _LOCK:
        histories = _read_state()
        histories[clean_conf_uid] = clean_history_uid
        _write_state(histories)


def clear_active_history_uid(conf_uid: str) -> None:
    """Forget a character's conversation, e.g. after the user deleted it."""
    with _LOCK:
        try:
            clean_conf_uid = _validate_component(conf_uid, "conf_uid")
        except ValueError:
            return
        histories = _read_state()
        if clean_conf_uid not in histories:
            return
        del histories[clean_conf_uid]
        _write_state(histories)
