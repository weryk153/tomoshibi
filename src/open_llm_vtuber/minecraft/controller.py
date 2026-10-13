"""Minecraft 模式的開始、停止與狀態。

控制器不認得 WebSocket：跟主視窗的接點全在 host（host.py）；跟直播的接點是
StreamController.attach_extra——開播時直播流程從同一個 feed 拿事件，私聊迴圈讓位。
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any, Callable, Optional

from loguru import logger

from ..config_manager.minecraft import MinecraftConfig
from .events import EventRules
from .feed import FeedRules, GameFeed
from . import goal_text
from .commands import compile_goal
from .goal_tool import make_goal_handler
from .mindserver import MindServerClient
from .session import MinecraftSession
from .settings import read_minecraft_settings, write_minecraft_settings


class MinecraftError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class MinecraftController:
    def __init__(
        self,
        host: Any,
        *,
        stream: Any = None,
        make_client: Callable[[str, str], Any] = MindServerClient,
        read_settings: Callable[[], MinecraftConfig] = read_minecraft_settings,
        write_settings: Callable[[dict], MinecraftConfig] = write_minecraft_settings,
        session_options: Optional[dict[str, Any]] = None,
    ):
        self._host = host
        self.stream = stream
        self._make_client = make_client
        self._read_settings = read_settings
        self._write_settings = write_settings
        self._session_options = session_options or {}
        self._client: Any = None
        self._feed: Optional[GameFeed] = None
        self._session: Optional[MinecraftSession] = None
        # 身體在忙時她下的目標先排著，閒下來才送：送了 Mindcraft 會中斷手上的動作。
        self._queue: deque[str] = deque()
        self._sent_at = float("-inf")
        self._task: Optional[asyncio.Task] = None
        self._settings: MinecraftConfig = MinecraftConfig()
        self.stopped_reason: Optional[str] = None
        self.last_error = ""
        # 兩個 start() 同時進來時，第二個要等第一個做完才看得到 live。
        self._lock = asyncio.Lock()

    @property
    def live(self) -> bool:
        return self._task is not None and not self._task.done()

    @staticmethod
    def _feed_rules(settings: MinecraftConfig) -> FeedRules:
        return FeedRules(
            idle_seconds=float(settings.idle_seconds),
            idle_cooldown=float(settings.idle_cooldown_seconds),
            event_cooldown=float(settings.event_cooldown_seconds),
        )

    async def start(self) -> dict:
        async with self._lock:
            return await self._start()

    async def _start(self) -> dict:
        if self.live:
            raise MinecraftError("already_live")
        settings = self._read_settings()
        if not settings.bot_name:
            raise MinecraftError("no_bot_name")
        client = self._make_client(settings.mindserver_url, settings.bot_name)
        try:
            await client.connect()
        except ConnectionError as error:
            self.last_error = str(error)
            raise MinecraftError("not_running") from error
        # connect 之後任何一步丟錯，都不能留下連著卻沒人管的 client。
        try:
            self._settings = settings
            self._client = client
            self._feed = GameFeed(self._feed_rules(settings))
            self._feed.ready = lambda: bool(client.connected and client.in_game)
            self._session = MinecraftSession(
                self._feed,
                self._host.run_private_turn,
                rules=EventRules(notable_items=tuple(settings.notable_items)),
                stream_live=lambda: bool(self.stream is not None and self.stream.live),
                failure_limit=settings.failure_limit,
                **self._session_options,
            )
            client.on_state = self._on_state
            client.on_output = self._session.handle_output
            client.on_disconnect = self._session.handle_disconnect
            self._host.install_tool(
                make_goal_handler(
                    client,
                    self._host.speaker_name(),
                    lambda: float(self._settings.tool_timeout_seconds),
                )
            )
            if self.stream is not None:
                self.stream.attach_extra(self._feed)

            # 她在台詞裡寫的 [minecraft_do: ...] 也送給身體（goal_text）；回話會從
            # bot-output 變成回報事件。
            async def _send_text_goal(goal: str) -> None:
                # 編成 Mindcraft 指令（可能好幾步）；她的新目標蓋掉舊目標剩下的步驟。
                # 身體在忙就排著，閒下來才一步一步送（送了 Mindcraft 會中斷手上的動作）。
                steps = compile_goal(goal)
                if not steps:
                    # 不替她決定：聽不懂就告訴她，讓她換個具體的說法。
                    logger.info(f"[minecraft] goal {goal!r} not understood")
                    if self._session is not None:
                        self._session.handle_output(
                            f"I don't understand '{goal}'. Tell me one concrete thing, like 'collect 10 oak logs' or 'craft a stone pickaxe'."
                        )
                    return
                logger.info(f"[minecraft] goal {goal!r} -> {steps}")
                self._queue.clear()
                self._queue.extend(steps)
                await self._pump()

            goal_text.sink = _send_text_goal
            self.stopped_reason = None
            self.last_error = ""
        except BaseException:
            self._client = None
            await client.close()
            raise
        self._task = asyncio.create_task(self._run(self._session))
        return self.status()

    async def _run(self, session: MinecraftSession) -> None:
        reason = "error"
        try:
            reason = await session.run()
        except asyncio.CancelledError:
            reason = "stopped"
            raise
        except Exception as error:
            self.last_error = f"{type(error).__name__}: {error}"
            logger.exception("[minecraft] session crashed")
        finally:
            self.stopped_reason = reason
            await self._teardown()

    async def _teardown(self) -> None:
        goal_text.sink = None
        self._queue.clear()
        self._host.uninstall_tool()
        if self.stream is not None:
            self.stream.detach_extra()
        client, self._client = self._client, None
        if client is not None:
            await client.close()

    async def stop(self) -> dict:
        async with self._lock:
            return await self._stop()

    async def _stop(self) -> dict:
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        # 任務還沒跑到第一個 await 就被取消時，_run 的 finally 根本不會執行；
        # 這裡補收尾（_run 收過的話 _client 已是 None，不會重複）。
        if self._client is not None:
            await self._teardown()
        if self.stopped_reason is None:
            self.stopped_reason = "stopped"
        return self.status()

    def apply_settings(self, settings: MinecraftConfig) -> None:
        self._settings = settings
        if self._feed is not None:
            self._feed.rules = self._feed_rules(settings)
        if self._session is not None:
            self._session.rules = EventRules(
                notable_items=tuple(settings.notable_items)
            )

    def _on_state(self, raw: object) -> None:
        session = self._session
        if session is None:
            return
        session.handle_state(raw)
        if self._queue:
            asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        """身體閒著就送佇列的下一步；剛送的那步給它幾秒開始動，別一口氣全倒進去。"""
        session, client = self._session, self._client
        if session is None or client is None or not self._queue:
            return
        latest = session.latest
        if latest is not None and not latest.is_idle:
            return
        if time.monotonic() - self._sent_at < 4.0:
            return
        step = self._queue.popleft()
        self._sent_at = time.monotonic()
        logger.info(f"[minecraft] -> body: {step} ({len(self._queue)} more queued)")
        # 名字每次現取：開始時主視窗可能還沒連上，那時會拿到預設名。
        await client.send(self._host.speaker_name(), step)

    def status(self) -> dict:
        latest = self._session.latest if self._session is not None else None
        current = self._session.current if self._session is not None else None
        return {
            "live": self.live,
            "connected": bool(self._client is not None and self._client.connected),
            "in_game": bool(self._client is not None and self._client.in_game),
            "pending": self._feed.pending() if self._feed is not None else 0,
            "health": latest.health if latest is not None else None,
            "action": latest.action if latest is not None else "",
            "current": current.kind if current is not None else None,
            "stopped_reason": self.stopped_reason,
            "last_error": self.last_error,
        }
