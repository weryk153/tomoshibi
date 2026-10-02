"""直播的開始、停止與狀態。

控制器不認得 WebSocket，也不認得引擎：跟外面的接點全在 StreamHost（實作在
host.py）。舞台頁同時只認一個，新的連上就取代舊的；舞台斷線只讓直播停在原地等。
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional, Protocol

from loguru import logger

from ..config_manager.stream import StreamConfig
from .chat_source import ChatSource, open_chat_source
from .comment_picker import CommentPicker, PickerRules
from .session import StreamSession, TurnRunner
from .settings import read_stream_settings, write_stream_settings


class StreamError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class StreamHost(Protocol):
    def new_stream_history(self, stage_uid: str) -> str: ...

    def character_names(self, stage_uid: str) -> tuple[str, ...]: ...

    def turn_runner(self, history_uid: str) -> TurnRunner: ...

    async def live_changed(self, live: bool) -> None: ...

    async def stop_stage_audio(self, stage_uid: str) -> None: ...


class StreamController:
    def __init__(
        self,
        host: StreamHost,
        *,
        open_source: Callable[[str], ChatSource] = open_chat_source,
        read_settings: Callable[[], StreamConfig] = read_stream_settings,
        write_settings: Callable[[dict], StreamConfig] = write_stream_settings,
        session_options: Optional[dict[str, Any]] = None,
    ):
        self._host = host
        self._open_source = open_source
        self._read_settings = read_settings
        self._write_settings = write_settings
        self._session_options = session_options or {}
        self.stage_uid: Optional[str] = None
        self.stopped_reason: Optional[str] = None
        self._session: Optional[StreamSession] = None
        self._task: Optional[asyncio.Task] = None
        self._history_uid: Optional[str] = None

    @property
    def live(self) -> bool:
        return self._task is not None and not self._task.done()

    def attach_stage(self, uid: str) -> Optional[str]:
        replaced = self.stage_uid if self.stage_uid not in (None, uid) else None
        self.stage_uid = uid
        if self._session is not None:
            self._session.stage_ready.set()
        return replaced

    def detach_stage(self, uid: str) -> None:
        if uid != self.stage_uid:
            return
        self.stage_uid = None
        if self._session is not None:
            self._session.stage_ready.clear()

    async def start(self, url: Optional[str] = None) -> dict:
        if self.live:
            raise StreamError("already_live")
        if not self.stage_uid:
            raise StreamError("no_stage")
        settings = self._read_settings()
        url = (settings.youtube_url if url is None else url).strip()
        if not url:
            raise StreamError("no_url")
        try:
            source = self._open_source(url)
        except ValueError as error:
            raise StreamError("bad_url") from error
        if url != settings.youtube_url:
            settings = self._write_settings({"youtube_url": url})

        # 連續失敗而暫停的，按開始接著同一段對話；其他情況開新的一段。
        if not (self.stopped_reason == "failures" and self._history_uid):
            self._history_uid = self._host.new_stream_history(self.stage_uid)
        rules = PickerRules(
            blocklist=tuple(settings.blocklist),
            max_chars=settings.max_comment_chars,
            max_age=settings.comment_max_age_seconds,
            viewer_cooldown=settings.same_viewer_cooldown_seconds,
            names=self._host.character_names(self.stage_uid),
        )
        session = StreamSession(
            source,
            CommentPicker(rules),
            self._host.turn_runner(self._history_uid),
            quiet_seconds=settings.quiet_seconds,
            failure_limit=settings.failure_limit,
            **self._session_options,
        )
        session.stage_ready.set()
        self._session = session
        self.stopped_reason = None
        self._task = asyncio.create_task(self._run(session))
        await self._host.live_changed(True)
        return self.status()

    async def _run(self, session: StreamSession) -> None:
        reason = "error"
        try:
            reason = await session.run()
        except asyncio.CancelledError:
            reason = "stopped"
            raise
        except Exception:
            logger.exception("[stream] session crashed")
        finally:
            self.stopped_reason = reason
            await self._host.live_changed(False)

    async def stop(self) -> dict:
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if self.stage_uid:
                await self._host.stop_stage_audio(self.stage_uid)
        return self.status()

    def status(self) -> dict:
        session = self._session
        live = self.live
        current = session.current if (session is not None and live) else None
        return {
            "live": live,
            "stage_connected": self.stage_uid is not None,
            "chat": session.chat_status() if (session is not None and live) else "idle",
            "read": session.picker.read if session else 0,
            "dropped": session.picker.dropped if session else 0,
            "queued": len(session.picker) if session else 0,
            "current": (
                {"author": current.author, "text": current.text} if current else None
            ),
            "stopped_reason": self.stopped_reason,
            "last_error": session.last_error if session else "",
            "history_uid": self._history_uid,
        }
