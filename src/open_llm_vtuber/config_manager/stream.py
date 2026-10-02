"""YouTube 直播模式的設定（conf.yaml 的 stream_config）。

這是整個程式的設定，不是某個角色的：換角色不會換掉直播網址或黑名單。
"""

from typing import ClassVar, Dict, List

from pydantic import Field, ValidationError, field_validator

from .i18n import Description, I18nMixin


class StreamConfig(I18nMixin):
    """直播模式：讀哪個聊天室、怎麼挑留言、冷場多久開口。"""

    youtube_url: str = Field("", alias="youtube_url")
    blocklist: List[str] = Field(default_factory=list, alias="blocklist")
    quiet_seconds: int = Field(30, alias="quiet_seconds", ge=5, le=3600)
    max_comment_chars: int = Field(100, alias="max_comment_chars", ge=1, le=1000)
    comment_max_age_seconds: int = Field(
        60, alias="comment_max_age_seconds", ge=5, le=3600
    )
    same_viewer_cooldown_seconds: int = Field(
        120, alias="same_viewer_cooldown_seconds", ge=0, le=3600
    )
    failure_limit: int = Field(3, alias="failure_limit", ge=1, le=100)

    @field_validator("youtube_url")
    @classmethod
    def _strip_url(cls, url: str) -> str:
        return url.strip()

    @field_validator("blocklist")
    @classmethod
    def _clean_blocklist(cls, words: List[str]) -> List[str]:
        cleaned: List[str] = []
        for word in words:
            word = str(word).strip()
            if word and word not in cleaned:
                cleaned.append(word)
        return cleaned

    @classmethod
    def lenient(cls, data: object) -> "StreamConfig":
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
        "youtube_url": Description(
            en="Last YouTube live video URL used", zh="上次用的 YouTube 直播網址"
        ),
        "blocklist": Description(
            en="Comments containing any of these words are skipped",
            zh="留言含有這些字就略過",
        ),
        "quiet_seconds": Description(
            en="Seconds without an answerable comment before she speaks up",
            zh="多久沒有能回的留言就主動開口（秒）",
        ),
        "max_comment_chars": Description(
            en="Longer comments are skipped", zh="超過這個字數的留言略過"
        ),
        "comment_max_age_seconds": Description(
            en="Queued comments older than this are dropped",
            zh="排隊超過這個秒數的留言丟掉",
        ),
        "same_viewer_cooldown_seconds": Description(
            en="Do not answer the same viewer again within this many seconds",
            zh="同一個觀眾多久內不連續回（秒）",
        ),
        "failure_limit": Description(
            en="Pause after this many failed turns in a row",
            zh="連續失敗幾輪就暫停",
        ),
    }
