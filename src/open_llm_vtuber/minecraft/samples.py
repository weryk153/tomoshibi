"""遊戲輪次與動作紀錄。ContextVar 隔離並行對話；回報以明確的 sample/command id 關聯。

raw_reply 是引擎輸出經斷句後、清標記前的文字，不是供應商原始 HTTP 回應。
紀錄只供後續人工審核，不能把 wrote_goal 或傳送成功當成正確玩法標籤。
"""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Any
from uuid import uuid4

from loguru import logger


@dataclass(frozen=True)
class SampleRef:
    path: str
    id: str


_current: ContextVar[dict | None] = ContextVar("minecraft_sample", default=None)


def path_for(conf_uid: str) -> str:
    return os.path.join(
        "chat_history", conf_uid or "unknown", "minecraft_samples.jsonl"
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start(
    conf_uid: str,
    kind: str,
    notes: list[str],
    state_raw: Any,
    suggested: str = "",
    *,
    history_uid: str = "",
    metadata: Any = None,
):
    # suggested 只保留舊格式相容性；目前流程不計算或推薦目標。
    sample = {
        "schema_version": 2,
        "id": uuid4().hex,
        "time": now(),
        "kind": kind,
        "history_uid": history_uid,
        "notes": list(notes),
        "state": deepcopy(state_raw) if isinstance(state_raw, dict) else None,
        "metadata": deepcopy(metadata),
        "suggested_goal": suggested,
        "raw_reply": "",
        "raw_reply_source": "engine_sentences_before_tag_removal",
        "goals": [],
        "_path": path_for(conf_uid),
    }
    return _current.set(sample)


def current_ref() -> SampleRef | None:
    sample = _current.get()
    return SampleRef(sample["_path"], sample["id"]) if sample else None


def raw_sentence(text: str) -> None:
    sample = _current.get()
    if sample is not None and text:
        sample["raw_reply"] += text


def goals(found: list[str]) -> None:
    sample = _current.get()
    if sample is not None:
        sample["goals"].extend(found)


def finish(result: str, token=None) -> None:
    sample = _current.get()
    if token is not None:
        _current.reset(token)
    else:
        _current.set(None)
    if sample is None:
        return
    record = {k: v for k, v in sample.items() if k != "_path"}
    record.update(result=result, wrote_goal=bool(sample["goals"]))
    _write(sample["_path"], record)


def event(ref: SampleRef | None, kind: str, **details: Any) -> None:
    if ref is not None:
        _write(
            ref.path, {"outcome_of": ref.id, "time": now(), "event": kind, **details}
        )


def outcome(text: str, ref: SampleRef | None = None, **details: Any) -> None:
    # 不再猜「最近一輪」；控制器必須傳入正在執行的指令所屬樣本。
    if text:
        event(ref, "body_output", body_reply=text, **details)


def _write(path: str, record: dict[str, Any]) -> None:
    try:
        line = json.dumps(record, ensure_ascii=False) + "\n"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except (OSError, TypeError, ValueError) as error:
        logger.warning(f"[minecraft] sample not saved: {error}")
