"""把 Minecraft 模式接到 WebSocketHandler。

私聊時每一輪是「替最近有動靜的那個主視窗跑一次主動開口」：重用
handle_conversation_trigger（ai-speak-signal），備註從 extra_metadata 帶進去，語音、
字幕照原本的路送到那個視窗，跑完把紀錄推給同一段對話的其他裝置。

工具 minecraft_do 掛在 agent 上，而 agent 是每個連線一個、換角色會重建，所以模式開著時
每一輪開跑前都 ensure_tool 一次（WebSocketHandler 在使用者觸發的那一輪也會叫）。
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from ..conversations.conversation_handler import handle_conversation_trigger
from .feed import GameTurn, game_turn_metadata
from .goal_tool import GOAL_TOOL
from .session import TurnResult

PRIVATE_TURN_WAIT_SECONDS = 60.0


class WebSocketMinecraftHost:
    def __init__(
        self,
        ws_handler: Any,
        *,
        trigger: Callable[..., Awaitable[None]] = handle_conversation_trigger,
    ):
        self._ws = ws_handler
        self._trigger = trigger
        self._handler: Optional[Callable[..., Awaitable[str]]] = None

    # --- 工具 -----------------------------------------------------------------

    def install_tool(self, handler: Callable[..., Awaitable[str]]) -> None:
        self._handler = handler
        for context in list(self._ws.client_contexts.values()):
            self.ensure_tool(context)

    def uninstall_tool(self) -> None:
        self._handler = None
        for context in list(self._ws.client_contexts.values()):
            agent = getattr(context, "agent_engine", None)
            if hasattr(agent, "remove_tool"):
                agent.remove_tool(GOAL_TOOL.name)

    def ensure_tool(self, context: Any) -> None:
        if self._handler is None:
            return
        agent = getattr(context, "agent_engine", None)
        if hasattr(agent, "add_tool"):
            agent.add_tool(GOAL_TOOL, self._handler)

    # --- 誰在聽 ---------------------------------------------------------------

    def _owner(self) -> Optional[str]:
        """最近有動靜的非舞台連線；舞台頁由直播流程負責，不算。"""
        last_active = getattr(self._ws, "client_last_active", {})
        candidates = [
            uid for uid in self._ws.client_contexts if not self._ws._is_stage(uid)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda uid: (last_active.get(uid, 0.0), uid))

    def speaker_name(self) -> str:
        uid = self._owner()
        if uid is None:
            return "Tomoshibi"
        config = self._ws.client_contexts[uid].character_config
        return str(config.character_name or config.conf_name or "Tomoshibi")

    # --- 一輪 -----------------------------------------------------------------

    async def run_private_turn(self, turn: GameTurn) -> TurnResult:
        uid = self._owner()
        if uid is None:
            return "interrupted"
        context = self._ws.client_contexts[uid]
        socket = self._ws.client_connections.get(uid)
        if socket is None or not getattr(context, "history_uid", ""):
            return "interrupted"
        # 正在講的那句先讓它講完：角色大腦是共用的，不然聲音疊在一起。
        pending = [
            task
            for task in list(self._ws.current_conversation_tasks.values())
            if task is not None and not task.done()
        ]
        if pending:
            _, still = await asyncio.wait(pending, timeout=PRIVATE_TURN_WAIT_SECONDS)
            if still:
                # 等了還沒講完就硬開下一輪，聲音會疊；若是她自己那個視窗的任務，
                # 新任務還會蓋掉登記，使用者就再也打斷不了舊的那一輪。
                logger.warning(
                    "[minecraft] previous turn still running, skipping this one"
                )
                return "interrupted"
        self.ensure_tool(context)
        logger.info(
            "[minecraft] {} turn -> {}: {}",
            turn.kind,
            uid,
            " | ".join(note[:70].replace("\n", " ") for note in turn.notes),
        )
        try:
            await self._trigger(
                msg_type="ai-speak-signal",
                data={},
                client_uid=uid,
                context=context,
                websocket=socket,
                client_contexts=self._ws.client_contexts,
                client_connections=self._ws.client_connections,
                chat_group_manager=self._ws.chat_group_manager,
                received_data_buffers=self._ws.received_data_buffers,
                current_conversation_tasks=self._ws.current_conversation_tasks,
                broadcast_to_group=self._ws.broadcast_to_group,
                extra_metadata=game_turn_metadata(turn.notes),
            )
        except Exception as error:
            logger.warning(f"[minecraft] could not start the turn: {error}")
            return "failed"
        task = self._ws.current_conversation_tasks.get(uid)
        if task is None:
            return "interrupted"
        try:
            # shield：關閉模式取消的是這個協程，不該連帶把她正在講的話切掉；
            # 使用者打斷是直接取消 task 本身，仍會走到下面的 interrupted。
            await asyncio.shield(task)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
            return "interrupted"
        except Exception as error:
            logger.warning(f"[minecraft] turn failed: {type(error).__name__}: {error}")
            return "failed"
        push = getattr(self._ws, "_push_history_to_peers", None)
        if push is not None:
            await push(uid)
        return "ok"
