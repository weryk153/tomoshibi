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
    async def prepare_stage(self, stage_uid: str) -> None: ...

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
        self._end_announced = True

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

        # 舞台頁可能比你在主視窗換角色更早連上：開播前讓它換成現在選的角色。
        await self._host.prepare_stage(self.stage_uid)
        # 連續失敗而暫停的，按開始接著同一段對話；其他情況開新的一段。
        if not (self.stopped_reason == "failures" and self._history_uid):
            history_uid = self._host.new_stream_history(self.stage_uid)
            if not history_uid:
                # 沒有自己那段對話，引擎會退回「目前的對話」——那是你的私人對話。
                raise StreamError("no_history")
            self._history_uid = history_uid
        session = StreamSession(
            source,
            CommentPicker(self._rules(settings)),
            self._host.turn_runner(self._history_uid),
            quiet_seconds=settings.quiet_seconds,
            failure_limit=settings.failure_limit,
            **self._session_options,
        )
        session.stage_ready.set()
        self._session = session
        self.stopped_reason = None
        self._end_announced = False
        self._task = asyncio.create_task(self._run(session))
        await self._host.live_changed(True)
        return self.status()

    def _rules(self, settings: StreamConfig) -> PickerRules:
        return PickerRules(
            blocklist=tuple(settings.blocklist),
            max_chars=settings.max_comment_chars,
            max_age=settings.comment_max_age_seconds,
            viewer_cooldown=settings.same_viewer_cooldown_seconds,
            names=self._host.character_names(self.stage_uid) if self.stage_uid else (),
        )

    def apply_settings(self, settings: StreamConfig) -> None:
        """直播中改的設定立刻生效（黑名單、字數、冷卻、冷場秒數）。"""
        session = self._session
        if session is None or not self.live:
            return
        names = session.picker.rules.names
        rules = self._rules(settings)
        session.picker.rules = PickerRules(
            blocklist=rules.blocklist,
            max_chars=rules.max_chars,
            max_age=rules.max_age,
            viewer_cooldown=rules.viewer_cooldown,
            names=names,
        )
        session.quiet_seconds = settings.quiet_seconds

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
            try:
                await self._host.live_changed(False)
                self._end_announced = True
            except asyncio.CancelledError:
                pass  # 廣播到一半被 stop() 取消：stop() 會補一次

    async def stop(self) -> dict:
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if self.stage_uid:
                await self._host.stop_stage_audio(self.stage_uid)
        # 直播剛好自己結束、廣播到一半被這裡取消的話，主視窗會卡在直播中。
        if not self._end_announced:
            await self._host.live_changed(False)
            self._end_announced = True
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
            "last_error": session.visible_error() if session else "",
            "history_uid": self._history_uid,
        }
