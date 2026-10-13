"""Minecraft 設定的讀寫：conf.yaml 的 minecraft_config。"""

from __future__ import annotations

from typing import Any

from ..config_manager.minecraft import MinecraftConfig
from ..settings_block import read_block, write_block

BLOCK = "minecraft_config"


def read_minecraft_settings() -> MinecraftConfig:
    return read_block(BLOCK, MinecraftConfig)


def write_minecraft_settings(changes: dict[str, Any]) -> MinecraftConfig:
    return write_block(BLOCK, MinecraftConfig, changes)
