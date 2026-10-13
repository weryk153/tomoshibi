"""接 Mindcraft 的 MindServer（socket.io，只綁 localhost，沒有 REST）。

用到的事件：送 listen-to-agents（之後才會每秒收到 state-update）、send-message；
收 state-update、agents-status、bot-output。bot-output 一次只能有一個人等：工具
下目標時等下一句當結果，沒人等的才當事件交給 on_output。
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from loguru import logger


def _default_client():
    import socketio

    return socketio.AsyncClient(
        reconnection=True, reconnection_delay=5, reconnection_delay_max=60
    )


class MindServerClient:
    def __init__(
        self,
        url: str,
        bot_name: str,
        *,
        make_client: Callable[[], Any] = _default_client,
    ):
        self.url = url
        self.bot_name = bot_name
        self.on_state: Optional[Callable[[object], None]] = None
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        self._sio = make_client()
        self._in_game = False
        self._waiter: Optional[asyncio.Future] = None
        self._sio.on("connect", self._connected)
        self._sio.on("disconnect", self._disconnected)
        self._sio.on("state-update", self._state_update)
        self._sio.on("agents-status", self._agents_status)
        self._sio.on("bot-output", self._bot_output)

    @property
    def connected(self) -> bool:
        return bool(getattr(self._sio, "connected", False))

    @property
    def in_game(self) -> bool:
        return self._in_game

    async def connect(self) -> None:
        try:
            await self._sio.connect(self.url, transports=["websocket"], wait_timeout=5)
        except Exception as error:
            raise ConnectionError(f"{type(error).__name__}: {error}") from error

    async def close(self) -> None:
        try:
            await self._sio.disconnect()
        except Exception as error:
            logger.debug(f"[minecraft] disconnect: {error}")

    async def send(self, from_name: str, message: str) -> None:
        # data 給 tuple，python-socketio 會展開成多個參數
        await self._sio.emit(
            "send-message", (self.bot_name, {"from": from_name, "message": message})
        )

    async def ask(self, from_name: str, message: str, timeout: float) -> Optional[str]:
        loop = asyncio.get_running_loop()
        self._waiter = loop.create_future()
        try:
            await self.send(from_name, message)
            return await asyncio.wait_for(asyncio.shield(self._waiter), timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self._waiter = None

    async def _connected(self) -> None:
        # 重連後也要重新訂閱，否則不會再收到 state-update
        await self._sio.emit("listen-to-agents")

    async def _disconnected(self, *_: Any) -> None:
        self._in_game = False
        if self.on_disconnect is not None:
            self.on_disconnect()

    async def _state_update(self, states: Any) -> None:
        if (
            isinstance(states, dict)
            and self.bot_name in states
            and self.on_state is not None
        ):
            self.on_state(states[self.bot_name])

    async def _agents_status(self, agents: Any) -> None:
        for agent in agents if isinstance(agents, list) else []:
            if isinstance(agent, dict) and agent.get("name") == self.bot_name:
                self._in_game = bool(agent.get("in_game"))

    async def _bot_output(self, agent_name: Any, message: Any = "") -> None:
        if agent_name != self.bot_name:
            return
        text = str(message)
        waiter = self._waiter
        if waiter is not None and not waiter.done():
            waiter.set_result(text)
            return
        if self.on_output is not None:
            self.on_output(text)
