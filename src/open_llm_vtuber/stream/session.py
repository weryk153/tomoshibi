"""一場直播怎麼跑。

兩條線同時跑：
- 讀聊天室：留言交給 picker 排隊；讀不到就照 backoff 等一下再連，期間不中斷直播。
- 講話：一次只跑一輪，上一輪（含語音播完）結束才挑下一則；沒有能回的留言超過
  quiet_seconds 就主動開口。舞台頁不在（stage_ready 沒設）時停在原地等。

直播結束（聊天室正常結束）時把隊伍回完就收工。被取消（按停止）時，正在跑的那輪
跟著取消。
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import Awaitable, Callable, Literal, Optional

from loguru import logger

from .chat_source import ChatEnded, ChatMessage, ChatSource, ChatSourceError
from .comment_picker import CommentPicker

TurnResult = Literal["ok", "failed", "interrupted"]
TurnRunner = Callable[[Optional[ChatMessage]], Awaitable[TurnResult]]

BACKOFF = (5.0, 10.0, 30.0, 60.0)
IDLE_POLL_SECONDS = 0.5


class StreamSession:
    def __init__(
        self,
        source: ChatSource,
        picker: CommentPicker,
        run_turn: TurnRunner,
        *,
        quiet_seconds: float,
        failure_limit: int,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        backoff: tuple[float, ...] = BACKOFF,
    ):
        self.picker = picker
        self.stage_ready = asyncio.Event()
        self.current: Optional[ChatMessage] = None
        self.last_error = ""
        # 直播中改設定（StreamController.apply_settings）會直接換掉這兩個。
        self.quiet_seconds = quiet_seconds
        self._source = source
        self._run_turn = run_turn
        self._failure_limit = failure_limit
        self._clock = clock
        self._sleep = sleep
        self._backoff = backoff
        self._retrying = False
        self._ended = False
        self._ended_event = asyncio.Event()
        self._failures = 0

    def chat_status(self) -> str:
        if self._ended:
            return "ended"
        if self._retrying:
            return "retrying"
        if getattr(self._source, "connected", False):
            return "connected"
        return "connecting"

    def visible_error(self) -> str:
        """給畫面看的錯誤：重新連上之後就不再掛著舊的錯誤。"""
        return "" if self.chat_status() in ("connected", "ended") else self.last_error

    def _end(self) -> None:
        self._ended = True
        self._ended_event.set()

    async def run(self) -> str:
        reader = asyncio.create_task(self._read())
        try:
            return await self._talk()
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
            await self._source.close()

    async def _read(self) -> None:
        attempt = 0
        while True:
            try:
                async for message in self._source.messages():
                    self._retrying = False
                    attempt = 0
                    # 留言的年紀從收到的那一刻算：YouTube 的時間戳記是伺服器的，
                    # 本機時鐘差個一分鐘就會全部被當成過期。
                    now = self._clock()
                    self.picker.offer(dataclasses.replace(message, timestamp=now), now)
                self._end()
                return
            except ChatEnded as error:
                self.last_error = str(error)
                self._end()
                return
            except Exception as error:
                # 非預期的例外（例如 YouTube 改了回應形狀）也當成暫時讀不到：記下來、
                # 等一下重連。只接 ChatSourceError 的話讀聊天室這條線會默默死掉，
                # 畫面還顯示「已連上」，整場再也收不到留言。
                if isinstance(error, ChatSourceError):
                    self.last_error = str(error)
                    logger.warning(f"[stream] chat unreadable: {error}")
                else:
                    self.last_error = f"{type(error).__name__}: {error}"
                    logger.exception("[stream] chat reader failed unexpectedly")
                self._retrying = True
                wait = self._backoff[min(attempt, len(self._backoff) - 1)]
                attempt += 1
                await self._sleep(wait)
                self._retrying = False

    async def _talk(self) -> str:
        last_spoke = self._clock()
        while True:
            if not self.stage_ready.is_set():
                # 舞台不在時也要聽「直播結束了」，不然收播後一直掛著直播中。
                waiters = [
                    asyncio.ensure_future(self.stage_ready.wait()),
                    asyncio.ensure_future(self._ended_event.wait()),
                ]
                try:
                    await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for waiter in waiters:
                        waiter.cancel()
                if not self.stage_ready.is_set():
                    return "ended"
            now = self._clock()
            comment = self.picker.pick(now)
            if comment is None:
                if self._ended:
                    return "ended"
                if now - last_spoke < self.quiet_seconds:
                    await self._sleep(IDLE_POLL_SECONDS)
                    continue
            self.current = comment
            try:
                result = await self._run_turn(comment)
            finally:
                self.current = None
            last_spoke = self._clock()
            if result == "ok":
                self._failures = 0
            elif result == "failed":
                self._failures += 1
                if self._failures >= self._failure_limit:
                    return "failures"
