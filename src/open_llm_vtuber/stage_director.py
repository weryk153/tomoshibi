"""Validated AI stage-performance selection.

The frontend owns performance files and timelines. The backend only gives the LLM
a compact allowlist and extracts one semantic preset ID from its response.
"""

from __future__ import annotations

import re
from typing import Any


PRESET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
STAGE_TAG_RE = re.compile(r"^\s*\[stage:([A-Za-z0-9][A-Za-z0-9_-]{0,63})\]")
MAX_CANDIDATES = 24


def normalize_stage_candidates(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw[:MAX_CANDIDATES]:
        if not isinstance(item, dict):
            continue
        preset_id = str(item.get("id") or "").strip()
        if not PRESET_ID_RE.fullmatch(preset_id) or preset_id in seen:
            continue
        name = " ".join(str(item.get("name") or preset_id).split())[:80] or preset_id
        description = " ".join(str(item.get("description") or "").split())[:240]
        result.append(
            {
                "id": preset_id,
                "name": name,
                "description": description,
            }
        )
        seen.add(preset_id)
    return result


def build_stage_director_prompt(candidates: list[dict[str, str]]) -> str:
    if not candidates:
        return ""
    choices = "\n".join(
        f"- {item['id']}: {item['name']} — {item['description']}" for item in candidates
    )
    return f"""
## Optional stage direction
You may select at most one stage performance when it materially fits the current
reply and context. Do not add a performance to routine sentences. If you select
one, put exactly one tag at the very beginning of the reply:
[stage:<preset_id>]

You may only use one of these preset IDs:
{choices}

Omit the tag when no performance is appropriate. Never invent a preset ID, never
explain the tag, and do not repeat a performance merely to make the reply livelier.
The tag is control metadata and is removed before subtitles, speech, and memory.
""".strip()


def extract_stage_performance(text: str, allowed_ids: set[str]) -> str | None:
    if not text or not allowed_ids:
        return None
    for match in STAGE_TAG_RE.finditer(text):
        preset_id = match.group(1)
        if preset_id in allowed_ids:
            return preset_id
    return None


def strip_stage_performance_tag(text: str) -> str:
    """Remove stage control metadata before persisting assistant memory."""
    return STAGE_TAG_RE.sub("", text, count=1).lstrip()
