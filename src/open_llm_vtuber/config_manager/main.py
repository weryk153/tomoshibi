# config_manager/main.py
from pydantic import BaseModel, Field, field_validator
from typing import Dict, ClassVar

from .system import SystemConfig
from .character import CharacterConfig
from .live import LiveConfig
from .stream import StreamConfig
from .minecraft import MinecraftConfig
from .i18n import I18nMixin, Description


class Config(I18nMixin, BaseModel):
    """
    Main configuration for the application.
    """

    system_config: SystemConfig = Field(default=None, alias="system_config")
    character_config: CharacterConfig = Field(..., alias="character_config")
    live_config: LiveConfig = Field(default=LiveConfig(), alias="live_config")
    stream_config: StreamConfig = Field(
        default_factory=StreamConfig, alias="stream_config"
    )

    @field_validator("stream_config", mode="before")
    @classmethod
    def _lenient_stream_config(cls, value):
        # 直播設定寫錯不該讓整個程式開不起來。
        return StreamConfig.lenient(value)

    minecraft_config: MinecraftConfig = Field(
        default_factory=MinecraftConfig, alias="minecraft_config"
    )

    @field_validator("minecraft_config", mode="before")
    @classmethod
    def _lenient_minecraft_config(cls, value):
        # Minecraft 設定寫錯同樣不該讓程式開不起來。
        return MinecraftConfig.lenient(value)

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "system_config": Description(
            en="System configuration settings", zh="系统配置设置"
        ),
        "character_config": Description(
            en="Character configuration settings", zh="角色配置设置"
        ),
        "live_config": Description(
            en="Live streaming platform integration settings", zh="直播平台集成设置"
        ),
        "stream_config": Description(
            en="YouTube stream mode settings", zh="YouTube 直播模式設定"
        ),
        "minecraft_config": Description(
            en="Minecraft mode settings", zh="Minecraft 模式設定"
        ),
    }
