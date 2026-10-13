"""直播設定的讀寫：conf.yaml 的 stream_config。

實際讀寫在 settings_block（跟 Minecraft 設定共用），這裡只指定區塊與型別。
"""

from __future__ import annotations

from typing import Any

from ..config_manager.stream import StreamConfig
from ..settings_block import read_block, write_block

BLOCK = "stream_config"


def read_stream_settings() -> StreamConfig:
    return read_block(BLOCK, StreamConfig)


def write_stream_settings(changes: dict[str, Any]) -> StreamConfig:
    return write_block(BLOCK, StreamConfig, changes)
