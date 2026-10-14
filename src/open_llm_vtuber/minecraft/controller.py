"""Minecraft 模式的開始、停止與狀態。

控制器不認得 WebSocket：跟主視窗的接點全在 host（host.py）；跟直播的接點是
StreamController.attach_extra——開播時直播流程從同一個 feed 拿事件，私聊迴圈讓位。
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from uuid import uuid4
from typing import Any, Callable, Optional

from loguru import logger

from ..config_manager.minecraft import MinecraftConfig
from .events import EventRules
from .feed import FeedRules, GameFeed
from . import goal_text, samples
from .commands import compile_goal
from .mindserver import MindServerClient
from .session import MinecraftSession
from .settings import read_minecraft_settings, write_minecraft_settings


@dataclass(frozen=True)
class QueuedStep:
    command: str
    goal_id: str
    command_id: str
    sample: samples.SampleRef | None


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
        self._queue: deque[QueuedStep] = deque()
        self._active: QueuedStep | None = None
        self._pump_tasks: set[asyncio.Task] = set()
        self._pump_lock = asyncio.Lock()
        self._state_at = float("-inf")
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
            client.on_output = self._on_output
            client.on_disconnect = self._on_disconnect
            self._sent_at = self._state_at = float("-inf")
            self._active = None
            self._host.install_tool(self._tool_goal)
            if self.stream is not None:
                self.stream.attach_extra(self._feed)
            goal_text._recent.clear()
            goal_text.sink = self._submit_goal
            self.stopped_reason = None
            self.last_error = ""
        except BaseException:
            await self._teardown()
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
        self._clear_queue("mode_stopped")
        if self._active is not None:
            self._step_event(self._active, "tracking_stopped", reason="mode_stopped")
        self._active = None
        for task in self._pump_tasks:
            task.cancel()
        if self._pump_tasks:
            await asyncio.gather(*self._pump_tasks, return_exceptions=True)
        self._pump_tasks.clear()
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

    async def _tool_goal(self, goal: str = "", **_: Any) -> str:
        text = str(goal or "").strip()
        if not text:
            return "Say what to do: the goal was empty."
        samples.goals([text])
        return await self._submit_goal(text)

    async def _submit_goal(self, goal: str) -> str:
        ref = samples.current_ref()
        goal_id = uuid4().hex
        client = self._client
        if client is None or not client.connected or not client.in_game:
            samples.event(
                ref, "goal_rejected", goal=goal, goal_id=goal_id, reason="not_in_game"
            )
            return "Your body is not connected to the game right now."
        steps = compile_goal(goal)
        if not steps:
            reply = f"I don't understand '{goal}'. Tell me one concrete thing, like 'collect 10 oak logs' or 'craft a stone pickaxe'."
            samples.event(
                ref,
                "goal_rejected",
                goal=goal,
                goal_id=goal_id,
                reason="not_understood",
                body_reply=reply,
            )
            if self._session is not None:
                self._session.handle_output(reply)
            return reply
        logger.info(f"[minecraft] goal {goal!r} -> {steps}")
        self._clear_queue("superseded")
        self._queue.extend(
            QueuedStep(step, goal_id, uuid4().hex, ref) for step in steps
        )
        samples.event(
            ref,
            "goal_queued",
            goal=goal,
            goal_id=goal_id,
            commands=[
                {"command": step.command, "command_id": step.command_id}
                for step in self._queue
            ],
        )
        await self._schedule_pump()
        return "Goal accepted; queued steps run when your body is idle. This is not a completion report."

    def _clear_queue(self, reason: str) -> None:
        while self._queue:
            step = self._queue.popleft()
            self._step_event(step, "command_cancelled", reason=reason)

    @staticmethod
    def _step_event(step: QueuedStep, kind: str, **details: Any) -> None:
        samples.event(
            step.sample,
            kind,
            goal_id=step.goal_id,
            command_id=step.command_id,
            command=step.command,
            **details,
        )

    def _on_output(self, text: str) -> None:
        # MindServer 沒有 request id；保留接收當時的 active command，但不宣稱因果確定。
        if self._active is not None:
            self._step_event(
                self._active,
                "body_output",
                body_reply=text,
                association="active_command_at_receipt",
            )
        if self._session is not None:
            self._session.handle_output(text)

    def _on_disconnect(self) -> None:
        self._clear_queue("disconnected")
        if self._active is not None:
            self._step_event(self._active, "command_interrupted", reason="disconnected")
        self._active = None
        self._state_at = float("-inf")
        if self._session is not None:
            self._session.handle_disconnect()

    def _on_state(self, raw: object) -> None:
        session = self._session
        if session is None:
            return
        if (
            not isinstance(raw, dict)
            or "error" in raw
            or not isinstance(raw.get("gameplay"), dict)
        ):
            return
        self._state_at = time.monotonic()
        session.handle_state(raw)
        if self._queue:
            self._schedule_pump()

    def _schedule_pump(self) -> asyncio.Task:
        task = asyncio.create_task(self._pump())
        self._pump_tasks.add(task)
        task.add_done_callback(self._pump_tasks.discard)
        return task

    async def _pump(self) -> None:
        """只在有新鮮閒置狀態時送下一步；兩個入口共用，不搶掉正在做的動作。"""
        async with self._pump_lock:
            session, client = self._session, self._client
            if session is None or client is None or not self._queue:
                return
            if not client.connected or not client.in_game:
                return
            latest = session.latest
            now = time.monotonic()
            if latest is None or not latest.is_idle or now - self._state_at > 5.0:
                return
            if now - self._sent_at < 4.0 or self._state_at < self._sent_at:
                return
            step = self._queue.popleft()
            self._sent_at = now
            self._active = step
            self._step_event(step, "command_sending", state=session.feed.state_raw)
            try:
                await client.send(self._host.speaker_name(), step.command)
            except Exception as error:
                self.last_error = f"{type(error).__name__}: {error}"
                self._step_event(step, "command_send_failed", error=self.last_error)
                self._clear_queue("send_failed")
                self._active = None
                session.handle_output(f"Failed to send command: {error}")
                return
            self._step_event(step, "command_sent")
            logger.info(
                f"[minecraft] -> body: {step.command} ({len(self._queue)} more queued)"
            )

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
