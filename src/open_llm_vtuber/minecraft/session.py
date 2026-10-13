"""Minecraft 模式怎麼跑。

MindServerClient 的回呼都接到這裡：每秒的狀態差分成事件丟進 feed、機器人自己的回報
當 report 事件、斷線一次講一次。迴圈每半秒看 feed 有沒有該講的；直播中不動（直播
流程自己從同一個 feed 拿），停播後接回來。連續失敗 failure_limit 次就停。
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Literal, Optional

from loguru import logger

from .events import EventRules, GameEvent, GameState, diff_events, parse_state
from .feed import GameFeed, GameTurn

TurnResult = Literal["ok", "failed", "interrupted"]
GameTurnRunner = Callable[[GameTurn], Awaitable[TurnResult]]
POLL_SECONDS = 0.5


class MinecraftSession:
    def __init__(
        self,
        feed: GameFeed,
        run_turn: GameTurnRunner,
        *,
        rules: EventRules,
        stream_live: Callable[[], bool],
        failure_limit: int,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.feed = feed
        self.rules = rules
        self.latest: Optional[GameState] = None
        self.current: Optional[GameTurn] = None
        self._run_turn = run_turn
        self._stream_live = stream_live
        self._failure_limit = failure_limit
        self._clock = clock
        self._sleep = sleep
        self._failures = 0
        self._disconnected_told = False

    def handle_state(self, raw: object) -> None:
        now = self._clock()
        state = parse_state(raw)
        for event in diff_events(self.latest, state, self.rules):
            self.feed.offer(event, now)
        self.feed.observe(state, now)
        self.latest = state
        self._disconnected_told = False

    def handle_output(self, text: str) -> None:
        text = text.strip()
        if text:
            self.feed.offer(GameEvent("report", f"你的身體回報：{text}"), self._clock())

    def handle_disconnect(self) -> None:
        if self._disconnected_told:
            return
        self._disconnected_told = True
        self.feed.offer(
            GameEvent("disconnected", "跟 Minecraft 的連線斷了，正在重連。"),
            self._clock(),
        )

    async def run(self) -> str:
        while True:
            if self._stream_live():
                await self._sleep(POLL_SECONDS)
                continue
            turn = self.feed.pick(self._clock())
            if turn is None:
                await self._sleep(POLL_SECONDS)
                continue
            self.current = turn
            try:
                result = await self._run_turn(turn)
            finally:
                self.current = None
            if result == "ok":
                self._failures = 0
            elif result == "failed":
                self._failures += 1
                logger.warning(
                    f"[minecraft] turn failed ({self._failures}/{self._failure_limit})"
                )
                if self._failures >= self._failure_limit:
                    return "failures"
