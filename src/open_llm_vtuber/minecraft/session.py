"""Minecraft 模式怎麼跑。

MindServerClient 的回呼都接到這裡：每秒的狀態差分成事件丟進 feed、機器人自己的回報
當 report 事件、斷線一次講一次。迴圈每半秒看 feed 有沒有該講的；直播中不動（直播
流程自己從同一個 feed 拿），停播後接回來。連續失敗 failure_limit 次就停。
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Awaitable, Callable, Literal, Optional

from loguru import logger

from .events import EventRules, GameEvent, GameState, diff_events, parse_state
from .feed import GameFeed, GameTurn

TurnResult = Literal["ok", "failed", "interrupted"]
GameTurnRunner = Callable[[GameTurn], Awaitable[TurnResult]]
POLL_SECONDS = 0.5
_REPORT_WORTH = re.compile(
    r"can'?t|cannot|couldn'?t|unable|fail|no .* (found|nearby)|not found|do(?:n'?t| not) have|missing|requires?|need|invalid|understand|"
    r"done|finished|collected|crafted|placed|died|killed",
    re.IGNORECASE,
)


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
        # Mindcraft 會回 {error: ...} 之類的東西；當成預設狀態去比會憑空生出
        # 死亡、拿到物品的事件，所以不是正常狀態就整包忽略。
        if (
            not isinstance(raw, dict)
            or "error" in raw
            or not isinstance(raw.get("gameplay"), dict)
        ):
            return
        now = self._clock()
        state = parse_state(raw)
        for event in diff_events(self.latest, state, self.rules):
            self.feed.offer(event, now)
        self.feed.observe(state, now)
        self.latest = state
        self._disconnected_told = False

    def handle_output(self, text: str) -> None:
        text = text.strip()
        # 身體的回話大多是「Searching for another oak_log」這種流水帳，每句都讓她講一輪
        # 太吵；只有做不到、失敗、找不到、做完了才值得講。
        if text and not _REPORT_WORTH.search(text):
            return
        if text:
            self.feed.offer(GameEvent("report", f"你的身體回報：{text}"), self._clock())

    def handle_disconnect(self) -> None:
        if self._disconnected_told:
            return
        self._disconnected_told = True
        self.feed.reset_idle()
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
            # 沒講成的那輪（沒視窗、被跳過）可能一個 await 都沒有；cooldown 設 0 時
            # 不睡一下迴圈就不讓出事件迴圈，整個 server 會卡住。
            await self._sleep(POLL_SECONDS if result != "ok" else 0)
