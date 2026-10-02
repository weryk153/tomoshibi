"""留言從哪裡來。

直播流程只認 ChatSource 這個介面：messages() 一則一則吐出留言，正常跑完代表直播
結束，丟 ChatSourceError 代表暫時讀不到（流程會等一下再呼叫一次 messages()）。
YouTube 的實作在 youtube_chat.py；以後換官方 API 也只換那一塊。
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Protocol


@dataclass(frozen=True)
class ChatMessage:
    id: str
    author: str
    text: str
    timestamp: float  # unix 秒
    kind: str = "text"  # "text" | "paid"（Super Chat）| "member"（會員）


class ChatSourceError(Exception):
    """讀不到聊天室：網路、YouTube 改版、這支影片沒有聊天室。"""


class ChatSource(Protocol):
    connected: bool

    def messages(self) -> AsyncIterator[ChatMessage]: ...

    async def close(self) -> None: ...


class FileChatSource:
    """假聊天室：JSON Lines，每行 {"author", "text", "delay", "kind"?}。

    delay 是距離上一則的秒數。讀完就當直播結束。給對照實驗與測試用：不用真的開播，
    同一批留言可以讓不同模型各跑幾次。
    """

    def __init__(
        self,
        path: str,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._path = path
        self._clock = clock
        self._sleep = sleep
        self.connected = False

    async def messages(self) -> AsyncIterator[ChatMessage]:
        try:
            lines = Path(self._path).read_text("utf-8").splitlines()
        except OSError as error:
            raise ChatSourceError(f"cannot read {self._path}: {error}") from error
        self.connected = True
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                author, text = str(item["author"]), str(item["text"])
                delay = float(item.get("delay", 0))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                raise ChatSourceError(f"line {index + 1}: {error}") from error
            await self._sleep(delay)
            yield ChatMessage(
                id=f"file-{index}",
                author=author,
                text=text,
                timestamp=self._clock(),
                kind=str(item.get("kind", "text")),
            )

    async def close(self) -> None:
        self.connected = False
