"""讀寫 conf.yaml 的某個頂層區塊（stream_config、minecraft_config 這類「整個程式
的設定」）。

讀用 read_yaml（跟開機載設定同一條路），寫用 conf_editor 就地改——conf.yaml 是人手寫
的檔案，不可以整份重新序列化把註解洗掉，只動該區塊裡改到的葉子。區塊不存在時接在檔尾。
model 要有 lenient(data) 類別方法（手改寫錯的欄位退回預設）。
"""

from __future__ import annotations

import json
from typing import Any, Type, TypeVar

from pydantic import ValidationError

from . import conf_editor
from .config_manager.utils import read_yaml

M = TypeVar("M")


def read_block(block: str, model: Type[M]) -> M:
    data = read_yaml(conf_editor.CONF_PATH) or {}
    return model.lenient(data.get(block) or {})  # type: ignore[attr-defined]


def _render(value: Any) -> str:
    """寫成 YAML 純量：整數裸寫、清單用 JSON（合法的 YAML flow）、字串加單引號。"""
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def write_block(block: str, model: Type[M], changes: dict[str, Any]) -> M:
    """只寫這次送來的鍵。驗證不過或有未知欄位就丟 ValueError，檔案不動。"""
    unknown = set(changes) - set(model.model_fields)  # type: ignore[attr-defined]
    if unknown:
        raise ValueError(f"unknown {block} settings: {sorted(unknown)}")
    current = read_block(block, model)
    try:
        merged = model.model_validate(  # type: ignore[attr-defined]
            {**current.model_dump(), **changes}  # type: ignore[attr-defined]
        )
    except ValidationError as error:
        raise ValueError(str(error)) from error

    lines = conf_editor.read_conf_lines()
    try:
        start, end = conf_editor.block_extent(lines, block)
    except KeyError:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines += ["\n", f"{block}:\n"]
        start = end = len(lines)
    for key in changes:
        end = conf_editor.upsert_leaf(
            lines, start, end, key, _render(getattr(merged, key))
        )
    conf_editor.write_conf(lines)
    return merged
