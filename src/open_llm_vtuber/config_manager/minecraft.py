"""Minecraft 模式的設定（conf.yaml 的 minecraft_config，設定頁的 Minecraft 分頁改這一塊）。

這是整個程式的設定，不是某個角色的：換角色不會換掉 MindServer 網址。
"""

from typing import ClassVar, Dict, List

from pydantic import Field, ValidationError, field_validator

from .i18n import Description, I18nMixin

DEFAULT_NOTABLE_ITEMS = [
    "diamond",
    "iron_ingot",
    "raw_iron",
    "gold_ingot",
    "raw_gold",
    "emerald",
    "ender_pearl",
    "blaze_rod",
    "bread",
    "cooked_beef",
    "cooked_porkchop",
]


class MinecraftConfig(I18nMixin):
    """Minecraft 模式：連哪個 MindServer、閒多久換目標、哪些東西值得講。"""

    mindserver_url: str = Field("http://127.0.0.1:8080", alias="mindserver_url")
    bot_name: str = Field("", alias="bot_name")
    idle_seconds: int = Field(15, alias="idle_seconds", ge=3, le=600)
    idle_cooldown_seconds: int = Field(60, alias="idle_cooldown_seconds", ge=0, le=3600)
    event_cooldown_seconds: int = Field(
        30, alias="event_cooldown_seconds", ge=0, le=600
    )
    tool_timeout_seconds: int = Field(20, alias="tool_timeout_seconds", ge=1, le=120)
    failure_limit: int = Field(3, alias="failure_limit", ge=1, le=100)
    notable_items: List[str] = Field(
        default_factory=lambda: list(DEFAULT_NOTABLE_ITEMS), alias="notable_items"
    )

    @field_validator("mindserver_url", "bot_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("notable_items")
    @classmethod
    def _clean_items(cls, items: List[str]) -> List[str]:
        cleaned: List[str] = []
        for item in items:
            word = str(item).strip()
            if word and word not in cleaned:
                cleaned.append(word)
        return cleaned

    @classmethod
    def lenient(cls, data: object) -> "MinecraftConfig":
        """手改 conf.yaml 寫錯的欄位退回預設，其他照用；不讓一個錯值害程式開不起來。"""
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            return cls()
        try:
            return cls.model_validate(data)
        except ValidationError:
            kept = {}
            for key, value in data.items():
                try:
                    cls.model_validate({key: value})
                except ValidationError:
                    continue
                kept[key] = value
            return cls.model_validate(kept)

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "mindserver_url": Description(
            en="Mindcraft MindServer URL", zh="Mindcraft 的 MindServer 網址"
        ),
        "bot_name": Description(
            en="Name of her Mindcraft bot profile", zh="她的 Mindcraft 機器人名字"
        ),
        "idle_seconds": Description(
            en="Seconds idle before she decides the next goal", zh="閒多久算閒下來"
        ),
        "idle_cooldown_seconds": Description(
            en="Minimum seconds between two goal decisions",
            zh="兩次決定目標至少隔多久",
        ),
        "event_cooldown_seconds": Description(
            en="Same kind of event is not repeated within this many seconds",
            zh="同類事件多久內不重複",
        ),
        "tool_timeout_seconds": Description(
            en="Seconds to wait for the bot's reply to a goal",
            zh="等 Mindcraft 回話多久",
        ),
        "failure_limit": Description(
            en="Pause after this many failed turns in a row",
            zh="連續失敗幾輪就暫停",
        ),
        "notable_items": Description(
            en="Items worth mentioning when they appear in her inventory",
            zh="背包多了什麼值得講",
        ),
    }
