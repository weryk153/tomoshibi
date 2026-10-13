"""每一輪遊戲對話的樣本，之後拿去微調她的腦。

一筆樣本要能單獨重現那一輪：她看到的東西（事件、狀態摘要、原始狀態、程式建議的下一步）、
她原本寫的回覆（含 [minecraft_do: ...] 標記，在被清掉之前）、抓到的目標，以及身體事後
回報了什麼。沒寫標記、或目標太虛的樣本也要留，那是之後要教它別這樣的負例。

一行一筆 JSON，放在 chat_history/<conf_uid>/minecraft_samples.jsonl；身體的回報另外一行
{"outcome_of": id, ...} 接在後面，讀的時候用 id 合併。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Optional

from loguru import logger

_current: Optional[dict[str, Any]] = None
_last_path: Optional[str] = None
_last_id: Optional[str] = None


def path_for(conf_uid: str) -> str:
    return os.path.join(
        "chat_history", conf_uid or "unknown", "minecraft_samples.jsonl"
    )


def start(
    conf_uid: str, kind: str, notes: list[str], state_raw: Any, suggested: str
) -> None:
    global _current
    _current = {
        "id": uuid.uuid4().hex[:12],
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "notes": list(notes),
        "state": _trim_state(state_raw),
        "suggested_goal": suggested,
        "raw_reply": "",
        "goals": [],
        "_path": path_for(conf_uid),
    }


def raw_sentence(text: str) -> None:
    """她回覆的每一句原文（標記還在）。"""
    if _current is not None and text:
        _current["raw_reply"] += text


def goals(found: list[str]) -> None:
    if _current is not None:
        _current["goals"].extend(found)


def finish(result: str) -> None:
    """這一輪結束：寫檔。沒寫標記的也要留（負例）。"""
    global _current, _last_path, _last_id
    sample, _current = _current, None
    if sample is None:
        return
    path = sample.pop("_path")
    sample["result"] = result
    sample["wrote_goal"] = bool(sample["goals"])
    _write(path, sample)
    _last_path, _last_id = path, sample["id"]


def outcome(text: str) -> None:
    """身體事後回報的話，掛到最近那一筆。"""
    if _last_path is None or not text:
        return
    _write(
        _last_path,
        {
            "outcome_of": _last_id,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "body_reply": text,
        },
    )


def _trim_state(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return None
    keep = {}
    for key in ("gameplay", "action", "inventory", "nearby"):
        if key in raw:
            keep[key] = raw[key]
    return keep


def _write(path: str, record: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as error:
        logger.warning(f"[minecraft] sample not saved: {error}")
