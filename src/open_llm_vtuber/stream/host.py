"""把直播控制器接到 WebSocketHandler 與現有的對話流程。

每一輪都是「替舞台頁那個連線跑一次 process_single_conversation」：語音、字幕、
表情照原本的路送到舞台頁，也照原本的方式等前端播完（frontend-playback-complete）
才回來，所以一則接一則的節奏是現成的。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from loguru import logger

from ..active_character_store import get_active_character_filename
from ..chat_history_manager import create_new_history
from ..conversations.conversation_handler import (
    PROACTIVE_TEXT,
    proactive_turn_metadata,
)
from ..conversations.single_conversation import process_single_conversation
from .chat_source import ChatMessage
from .session import TurnResult


class WebSocketStreamHost:
    def __init__(self, ws_handler: Any, *, process=process_single_conversation):
        self._ws = ws_handler
        self._process = process
        self.controller: Any = None  # 建好 StreamController 之後由 server 設定

    def _stage(self) -> tuple[Optional[str], Any, Any]:
        uid = getattr(self.controller, "stage_uid", None)
        if not uid:
            return None, None, None
        return (
            uid,
            self._ws.client_contexts.get(uid),
            self._ws.client_connections.get(uid),
        )

    async def prepare_stage(self, stage_uid: str) -> None:
        """舞台頁的角色是連上那一刻載入的；之後在主視窗換角色只換主視窗那個連線。
        開播前把舞台換成現在選的角色，並讓舞台頁換模型。"""
        context = self._ws.client_contexts.get(stage_uid)
        socket = self._ws.client_connections.get(stage_uid)
        active = get_active_character_filename()
        if context is None or not active or active == context.active_config_file:
            return
        await context.load_character_config(active)
        if socket is not None:
            await context._send_model_and_conf(socket)

    def new_stream_history(self, stage_uid: str) -> str:
        # 只建檔，不記成「上次聊到哪」：私人聊天的進度不動。
        context = self._ws.client_contexts[stage_uid]
        return create_new_history(context.character_config.conf_uid)

    def character_names(self, stage_uid: str) -> tuple[str, ...]:
        config = self._ws.client_contexts[stage_uid].character_config
        names: list[str] = []
        for name in (config.character_name, config.conf_name):
            if name and name not in names:
                names.append(name)
        return tuple(names)

    def turn_runner(self, history_uid: str):
        async def run_turn(comment: Optional[ChatMessage]) -> TurnResult:
            uid, context, socket = self._stage()
            if context is None or socket is None:
                return "interrupted"
            context.history_uid = history_uid
            if comment is None:
                metadata = {**proactive_turn_metadata(context, uid), "stream": True}
                user_input = PROACTIVE_TEXT
                shown = {"type": "stream-comment", "author": "", "text": ""}
            else:
                metadata = {
                    "stream": True,
                    "stream_comment": {"author": comment.author, "text": comment.text},
                }
                user_input = f"{comment.author}：{comment.text}"
                shown = {
                    "type": "stream-comment",
                    "author": comment.author,
                    "text": comment.text,
                }
            try:
                await socket.send_text(json.dumps(shown, ensure_ascii=False))
            except Exception:
                return "interrupted"

            task = asyncio.create_task(
                self._process(
                    context=context,
                    websocket_send=socket.send_text,
                    client_uid=uid,
                    user_input=user_input,
                    metadata=metadata,
                )
            )
            self._ws.current_conversation_tasks[uid] = task
            try:
                reply = await task
            except asyncio.CancelledError:
                # 自己被取消（按停止）就往外丟；只有那一輪被取消（舞台斷線）才算中斷。
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise
                return "interrupted"
            except Exception as error:
                logger.warning(f"[stream] turn failed: {type(error).__name__}: {error}")
                return "failed"
            return "ok" if reply else "failed"

        return run_turn

    async def live_changed(self, live: bool) -> None:
        await self._ws.broadcast_stream_state(live)

    async def stop_stage_audio(self, stage_uid: str) -> None:
        socket = self._ws.client_connections.get(stage_uid)
        if socket is None:
            return
        for message in (
            {"type": "interrupt-signal"},
            {"type": "stream-comment", "author": "", "text": ""},
        ):
            try:
                await socket.send_text(json.dumps(message))
            except Exception:
                return
