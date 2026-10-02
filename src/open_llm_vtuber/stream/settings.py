"""直播設定的讀寫：conf.yaml 的 stream_config。

讀用 read_yaml（跟開機載設定同一條路），寫用 conf_editor 就地改——conf.yaml 是人手寫
的檔案，不可以整份重新序列化把註解洗掉。區塊不存在時接在檔尾。
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .. import conf_editor
from ..config_manager.stream import StreamConfig
from ..config_manager.utils import read_yaml

BLOCK = "stream_config"


def read_stream_settings() -> StreamConfig:
    data = read_yaml(conf_editor.CONF_PATH) or {}
    return StreamConfig.lenient(data.get(BLOCK) or {})


def _render(value: Any) -> str:
    """寫成 YAML 純量：整數裸寫、清單用 JSON（合法的 YAML flow）、字串加單引號。"""
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def write_stream_settings(changes: dict[str, Any]) -> StreamConfig:
    """只寫這次送來的鍵。驗證不過或有未知欄位就丟 ValueError，檔案不動。"""
    unknown = set(changes) - set(StreamConfig.model_fields)
    if unknown:
        raise ValueError(f"unknown stream settings: {sorted(unknown)}")
    current = read_stream_settings()
    try:
        merged = StreamConfig.model_validate({**current.model_dump(), **changes})
    except ValidationError as error:
        raise ValueError(str(error)) from error

    lines = conf_editor.read_conf_lines()
    try:
        start, end = conf_editor.block_extent(lines, BLOCK)
    except KeyError:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines += ["\n", f"{BLOCK}:\n"]
        start = end = len(lines)
    for key in changes:
        end = conf_editor.upsert_leaf(
            lines, start, end, key, _render(getattr(merged, key))
        )
    conf_editor.write_conf(lines)
    return merged
