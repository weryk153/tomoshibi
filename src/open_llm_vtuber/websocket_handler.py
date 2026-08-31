from typing import Dict, List, Optional, Callable, TypedDict
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json
import time
from enum import Enum
import numpy as np
from loguru import logger

from .service_context import ServiceContext
from .chat_group import (
    ChatGroupManager,
    handle_group_operation,
    handle_client_disconnect,
    broadcast_to_group,
)
from .message_handler import message_handler
from .utils.stream_audio import prepare_audio_payload
from .chat_history_manager import (
    create_new_history,
    get_history,
    delete_history,
    get_history_list,
    history_exists,
)
from .config_manager.utils import scan_config_alts_directory, scan_bg_directory
from .conversations.conversation_handler import (
    handle_conversation_trigger,
    handle_group_interrupt,
    handle_individual_interrupt,
)
from .proactive_context import clear_proactive_context, proactive_context_uid
from .active_character_store import (
    get_active_character_filename,
    set_active_character_filename,
)
from .active_history_store import (
    clear_active_history_uid,
    get_active_history_uid,
    set_active_history_uid,
)


class MessageType(Enum):
    """Enum for WebSocket message types"""

    GROUP = ["add-client-to-group", "remove-client-from-group"]
    HISTORY = [
        "fetch-history-list",
        "fetch-and-set-history",
        "create-new-history",
        "delete-history",
    ]
    CONVERSATION = ["mic-audio-end", "text-input", "ai-speak-signal"]
    CONFIG = ["fetch-configs", "switch-config", "switch-persona"]
    CONTROL = ["interrupt-signal", "audio-play-start"]
    DATA = ["mic-audio-data"]


class WSMessage(TypedDict, total=False):
    """Type definition for WebSocket messages"""

    type: str
    action: Optional[str]
    text: Optional[str]
    audio: Optional[List[float]]
    images: Optional[List[str]]
    history_uid: Optional[str]
    file: Optional[str]
    persona_id: Optional[str]
    display_text: Optional[dict]
    candidates: Optional[List[dict]]


def select_history_peers(client_contexts: dict, origin_client_uid: str) -> list:
    """一輪對話結束後，該把更新後的紀錄推給哪些其他連線。

    兩台裝置連同一個角色時看的是同一段對話（連線時還原的 active history uid 是
    依角色存的，不分裝置），但單人對話的回覆只送給發話的那個連線，所以另一台
    要重整才看得到。

    只挑「同一個角色、而且正在看同一段對話」的其他連線。推錯人的後果是把 A 的
    對話內容送到正在翻舊對話或看別的角色的 B 畫面上，等於當著使用者的面把他的
    畫面換掉。
    """
    origin = client_contexts.get(origin_client_uid)
    if origin is None:
        return []
    history_uid = getattr(origin, "history_uid", None)
    if not history_uid:
        return []
    conf_uid = origin.character_config.conf_uid

    peers = []
    for uid, ctx in client_contexts.items():
        if uid == origin_client_uid:
            continue
        if getattr(ctx, "history_uid", None) != history_uid:
            continue
        if ctx.character_config.conf_uid != conf_uid:
            continue
        peers.append(uid)
    return peers


def is_proactive_owner(
    client_contexts: dict, last_active: dict, client_uid: str
) -> bool:
    """這個連線是不是這段對話裡負責主動發言的那一台。

    主動發言的閒置計時器在前端，每個連線各有一個。兩台同時開著時兩邊都會送
    ai-speak-signal，角色就各講各的——兩台畫面上的內容不一樣，而且兩句都被寫進
    同一段對話。

    規則是「最近使用過的那台」。你剛在手機上打完字，主動發言就該從手機發生，而
    不是從你早就沒在看的桌機。發話端講的話會透過 history 推送同步過去，所以限制
    成一台不會讓另一台漏掉內容，反而是唯一能讓兩邊一致的做法。

    平手時用 client_uid 決勝。兩台剛連上、都還沒講過話時時間戳會一樣，沒有決勝
    規則的話兩台都會認為自己負責，等於沒修。

    群組對話刻意不走這條：群組成員是不同角色、不同 history，本來就不會被算成同
    一組，兩邊各自觸發是預期行為。
    """
    origin = client_contexts.get(client_uid)
    if origin is None:
        return False

    history_uid = getattr(origin, "history_uid", None)
    if not history_uid:
        return False
    conf_uid = origin.character_config.conf_uid
    candidates = [
        uid
        for uid, ctx in client_contexts.items()
        if getattr(ctx, "history_uid", None) == history_uid
        and ctx.character_config.conf_uid == conf_uid
    ]

    best_uid = None
    best_key = None
    for uid in candidates:
        # 沒有紀錄代表這個連線從來沒有動作過。
        key = (last_active.get(uid, 0.0), uid)
        if best_key is None or key > best_key:
            best_key = key
            best_uid = uid
    return best_uid == client_uid


class WebSocketHandler:
    """Handles WebSocket connections and message routing"""

    def __init__(self, default_context_cache: ServiceContext):
        """Initialize the WebSocket handler with default context"""
        self.client_connections: Dict[str, WebSocket] = {}
        # client_uid -> 最後一次使用者動作的 monotonic 時間。多台連線時用來決定
        # 由誰負責主動發言：你剛用過的那台。
        self.client_last_active: Dict[str, float] = {}
        self.client_contexts: Dict[str, ServiceContext] = {}
        self.chat_group_manager = ChatGroupManager()
        self.current_conversation_tasks: Dict[str, Optional[asyncio.Task]] = {}
        self.default_context_cache = default_context_cache
        self.received_data_buffers: Dict[str, np.ndarray] = {}

        # Message handlers mapping
        self._message_handlers = self._init_message_handlers()

    def _init_message_handlers(self) -> Dict[str, Callable]:
        """Initialize message type to handler mapping"""
        return {
            "add-client-to-group": self._handle_group_operation,
            "remove-client-from-group": self._handle_group_operation,
            "request-group-info": self._handle_group_info,
            "fetch-history-list": self._handle_history_list_request,
            "fetch-and-set-history": self._handle_fetch_history,
            "create-new-history": self._handle_create_history,
            "delete-history": self._handle_delete_history,
            "interrupt-signal": self._handle_interrupt,
            "mic-audio-data": self._handle_audio_data,
            "mic-audio-end": self._handle_conversation_trigger,
            "raw-audio-data": self._handle_raw_audio_data,
            "text-input": self._handle_conversation_trigger,
            "ai-speak-signal": self._handle_conversation_trigger,
            "fetch-configs": self._handle_fetch_configs,
            "switch-config": self._handle_config_switch,
            "switch-persona": self._handle_persona_switch,
            "configure-stage-director": self._handle_stage_director_config,
            "fetch-backgrounds": self._handle_fetch_backgrounds,
            "audio-play-start": self._handle_audio_play_start,
            "request-init-config": self._handle_init_config_request,
            "heartbeat": self._handle_heartbeat,
        }

    async def handle_new_connection(
        self, websocket: WebSocket, client_uid: str
    ) -> None:
        """
        Handle new WebSocket connection setup

        Args:
            websocket: The WebSocket connection
            client_uid: Unique identifier for the client

        Raises:
            Exception: If initialization fails
        """
        try:
            session_service_context = await self._init_service_context(
                websocket.send_text, client_uid
            )

            await self._store_client_data(
                websocket, client_uid, session_service_context
            )

            await self._send_initial_messages(
                websocket, client_uid, session_service_context
            )

            logger.info(f"Connection established for client {client_uid}")

        except Exception as e:
            logger.error(
                f"Failed to initialize connection for client {client_uid}: {e}"
            )
            await self._cleanup_failed_connection(client_uid)
            raise

    async def _store_client_data(
        self,
        websocket: WebSocket,
        client_uid: str,
        session_service_context: ServiceContext,
    ):
        """Store client data and initialize group status"""
        self.client_connections[client_uid] = websocket
        self.client_contexts[client_uid] = session_service_context
        self.received_data_buffers[client_uid] = np.array([])

        self.chat_group_manager.client_group_map[client_uid] = ""
        await self.send_group_update(websocket, client_uid)

    async def _send_initial_messages(
        self,
        websocket: WebSocket,
        client_uid: str,
        session_service_context: ServiceContext,
    ):
        """Send initial connection messages to the client"""
        await websocket.send_text(
            json.dumps(
                {
                    "type": "full-text",
                    "text": "Connection established",
                    "text_key": "connectionEstablished",
                }
            )
        )

        await websocket.send_text(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": session_service_context.live2d_model.model_info,
                    "conf_name": session_service_context.character_config.conf_name,
                    "conf_uid": session_service_context.character_config.conf_uid,
                    "client_uid": client_uid,
                }
            )
        )

        # Send initial group status
        await self.send_group_update(websocket, client_uid)

        # Put the session back in the conversation the user was last having.
        # This must precede start-mic: without a history_uid nothing said next
        # would be recorded (see single_conversation.py's `if context.history_uid`).
        await self._restore_or_create_history(
            websocket, client_uid, session_service_context
        )

        # Start microphone
        await websocket.send_text(json.dumps({"type": "control", "text": "start-mic"}))

    async def _init_service_context(
        self, send_text: Callable, client_uid: str
    ) -> ServiceContext:
        """Initialize service context for a new session by cloning the default context"""
        session_service_context = ServiceContext()
        await session_service_context.load_cache(
            config=self.default_context_cache.config.model_copy(deep=True),
            system_config=self.default_context_cache.system_config.model_copy(
                deep=True
            ),
            character_config=self.default_context_cache.character_config.model_copy(
                deep=True
            ),
            live2d_model=self.default_context_cache.live2d_model,
            asr_engine=self.default_context_cache.asr_engine,
            tts_engine=self.default_context_cache.tts_engine,
            vad_engine=self.default_context_cache.vad_engine,
            agent_engine=self.default_context_cache.agent_engine,
            translate_engine=self.default_context_cache.translate_engine,
            mcp_server_registery=self.default_context_cache.mcp_server_registery,
            tool_adapter=self.default_context_cache.tool_adapter,
            send_text=send_text,
            client_uid=client_uid,
            subtitle_translate_engine=self.default_context_cache.subtitle_translate_engine,
            character_persona_prompt=self.default_context_cache.character_persona_prompt,
            active_persona_id=self.default_context_cache.active_persona_id,
            active_config_file=self.default_context_cache.active_config_file,
        )

        # The backend may stay alive while the browser is closed. A character
        # selected by the previous connection must therefore also be restored on
        # reconnect, not only on a full server restart.
        active_file = get_active_character_filename()
        if active_file and active_file != session_service_context.active_config_file:
            try:
                await session_service_context.load_character_config(active_file)
            except Exception as e:
                logger.warning(
                    f"Could not restore active character '{active_file}' for new "
                    f"connection ({type(e).__name__}: {e}); using conf.yaml"
                )
                await session_service_context.load_character_config("conf.yaml")
                try:
                    set_active_character_filename("conf.yaml")
                except OSError as state_error:
                    logger.warning(
                        "Could not reset active-character state "
                        f"({type(state_error).__name__}: {state_error})"
                    )
        return session_service_context

    async def handle_websocket_communication(
        self, websocket: WebSocket, client_uid: str
    ) -> None:
        """
        Handle ongoing WebSocket communication

        Args:
            websocket: The WebSocket connection
            client_uid: Unique identifier for the client
        """
        try:
            while True:
                try:
                    data = await websocket.receive_json()
                    message_handler.handle_message(client_uid, data)
                    await self._route_message(websocket, client_uid, data)
                except WebSocketDisconnect:
                    raise
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": str(e)})
                    )
                    continue

        except WebSocketDisconnect:
            logger.info(f"Client {client_uid} disconnected")
            raise
        except Exception as e:
            logger.error(f"Fatal error in WebSocket communication: {e}")
            raise

    async def _route_message(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """
        Route incoming message to appropriate handler

        Args:
            websocket: The WebSocket connection
            client_uid: Client identifier
            data: Message data
        """
        msg_type = data.get("type")
        if not msg_type:
            logger.warning("Message received without type")
            return

        # 記下這台裝置最後一次「使用者真的有動作」的時間，用來決定多台連線時由誰
        # 負責主動發言（見 is_proactive_owner）。心跳是背景維持連線、
        # ai-speak-signal 是計時器自己送的，兩者都不是使用者動作——把它們算進去
        # 的話每台裝置都會不斷刷新自己的時間戳，等於沒有依據。
        if msg_type not in ("heartbeat", "ai-speak-signal"):
            self.client_last_active[client_uid] = time.monotonic()

        handler = self._message_handlers.get(msg_type)
        if handler:
            await handler(websocket, client_uid, data)
        else:
            if msg_type != "frontend-playback-complete":
                logger.warning(f"Unknown message type: {msg_type}")

    async def _handle_stage_director_config(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        context = self.client_contexts.get(client_uid)
        if context is None:
            return
        candidates = await context.configure_stage_director(data.get("candidates", []))
        await websocket.send_text(
            json.dumps(
                {
                    "type": "stage-director-configured",
                    "candidate_count": len(candidates),
                }
            )
        )

    async def _handle_group_operation(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle group-related operations"""
        operation = data.get("type")
        target_uid = data.get(
            "invitee_uid" if operation == "add-client-to-group" else "target_uid"
        )

        await handle_group_operation(
            operation=operation,
            client_uid=client_uid,
            target_uid=target_uid,
            chat_group_manager=self.chat_group_manager,
            client_connections=self.client_connections,
            send_group_update=self.send_group_update,
        )

    async def handle_disconnect(self, client_uid: str) -> None:
        """Handle client disconnection"""
        context = self.client_contexts.get(client_uid)
        group = self.chat_group_manager.get_client_group(client_uid)
        if group:
            await handle_group_interrupt(
                group_id=group.group_id,
                heard_response="",
                current_conversation_tasks=self.current_conversation_tasks,
                chat_group_manager=self.chat_group_manager,
                client_contexts=self.client_contexts,
                broadcast_to_group=self.broadcast_to_group,
            )

        await handle_client_disconnect(
            client_uid=client_uid,
            chat_group_manager=self.chat_group_manager,
            client_connections=self.client_connections,
            send_group_update=self.send_group_update,
        )

        # Clean up other client data
        self.client_connections.pop(client_uid, None)
        self.client_last_active.pop(client_uid, None)
        self.client_contexts.pop(client_uid, None)
        self.received_data_buffers.pop(client_uid, None)
        if client_uid in self.current_conversation_tasks:
            task = self.current_conversation_tasks[client_uid]
            if task and not task.done():
                task.cancel()
            self.current_conversation_tasks.pop(client_uid, None)

        if context:
            # Recording and lookup are keyed by history_uid when there is one
            # (see proactive_context_uid); passing the raw client_uid here meant
            # the clear never matched the key actually in use.
            clear_proactive_context(
                context.character_config.conf_uid,
                proactive_context_uid(context.history_uid, client_uid),
            )

        # Call context close to clean up resources (e.g., MCPClient)
        if context:
            await context.close()

        logger.info(f"Client {client_uid} disconnected")
        message_handler.cleanup_client(client_uid)

    async def _cleanup_failed_connection(self, client_uid: str) -> None:
        """Clean up failed connection data"""
        self.client_connections.pop(client_uid, None)
        self.client_last_active.pop(client_uid, None)
        self.client_contexts.pop(client_uid, None)
        self.received_data_buffers.pop(client_uid, None)
        self.chat_group_manager.client_group_map.pop(client_uid, None)

        if client_uid in self.current_conversation_tasks:
            task = self.current_conversation_tasks[client_uid]
            if task and not task.done():
                task.cancel()
            self.current_conversation_tasks.pop(client_uid, None)

        message_handler.cleanup_client(client_uid)

    async def broadcast_to_group(
        self, group_members: list[str], message: dict, exclude_uid: str = None
    ) -> None:
        """Broadcasts a message to group members"""
        await broadcast_to_group(
            group_members=group_members,
            message=message,
            client_connections=self.client_connections,
            exclude_uid=exclude_uid,
        )

    async def send_group_update(self, websocket: WebSocket, client_uid: str):
        """Sends group information to a client"""
        group = self.chat_group_manager.get_client_group(client_uid)
        if group:
            current_members = self.chat_group_manager.get_group_members(client_uid)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "group-update",
                        "members": current_members,
                        "is_owner": group.owner_uid == client_uid,
                    }
                )
            )
        else:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "group-update",
                        "members": [],
                        "is_owner": False,
                    }
                )
            )

    async def _handle_interrupt(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle conversation interruption"""
        heard_response = data.get("text", "")
        context = self.client_contexts[client_uid]
        group = self.chat_group_manager.get_client_group(client_uid)

        if group and len(group.members) > 1:
            await handle_group_interrupt(
                group_id=group.group_id,
                heard_response=heard_response,
                current_conversation_tasks=self.current_conversation_tasks,
                chat_group_manager=self.chat_group_manager,
                client_contexts=self.client_contexts,
                broadcast_to_group=self.broadcast_to_group,
            )
        else:
            await handle_individual_interrupt(
                client_uid=client_uid,
                current_conversation_tasks=self.current_conversation_tasks,
                context=context,
                heard_response=heard_response,
            )

    async def _handle_history_list_request(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle request for chat history list"""
        context = self.client_contexts[client_uid]
        histories = get_history_list(context.character_config.conf_uid)
        await websocket.send_text(
            json.dumps({"type": "history-list", "histories": histories})
        )

    @staticmethod
    def _remember_active_history(conf_uid: str, history_uid: str) -> None:
        """Record which conversation to resume, without ever failing the switch.

        Losing the pointer only costs the next reload its resume; refusing to
        switch conversations because a state file could not be written would be
        the worse trade.
        """
        try:
            set_active_history_uid(conf_uid, history_uid)
        except (OSError, ValueError) as e:
            logger.warning(
                f"Could not save active history '{history_uid}' "
                f"({type(e).__name__}: {e})"
            )

    def _activate_history(
        self, context: ServiceContext, client_uid: str, history_uid: str
    ) -> List[dict]:
        """Point a session at a conversation and return it for display."""
        clear_proactive_context(
            context.character_config.conf_uid,
            proactive_context_uid(context.history_uid, client_uid),
        )
        # Update history_uid in service context
        context.history_uid = history_uid
        # agent_engine can be None if the AI brain failed to initialize (bad config);
        # the app still opens so the user can fix it in Settings. Skip memory load.
        if context.agent_engine is not None:
            context.agent_engine.set_memory_from_history(
                conf_uid=context.character_config.conf_uid,
                history_uid=history_uid,
            )
        self._remember_active_history(context.character_config.conf_uid, history_uid)

        messages = []
        for stored_message in get_history(
            context.character_config.conf_uid,
            history_uid,
        ):
            if stored_message["role"] == "system":
                continue
            message = dict(stored_message)
            # The canonical content remains on disk for the LLM; history-data is
            # a presentation payload, so expose the same translated copy used by
            # the live chat bubble when one was stored for this turn.
            if message.get("display_content"):
                message["content"] = message["display_content"]
            message.pop("display_content", None)
            messages.append(message)
        return messages

    async def _restore_or_create_history(
        self, websocket: WebSocket, client_uid: str, context: ServiceContext
    ) -> None:
        """Resume the conversation this character was last in, or start one.

        A reload opens a brand-new WebSocket, so without this the session would
        begin with no ``history_uid`` and the client would ask for a fresh empty
        conversation — wiping both the on-screen log and the agent's memory of a
        conversation the user never ended.
        """
        conf_uid = context.character_config.conf_uid
        saved_uid = get_active_history_uid(conf_uid)
        if saved_uid and history_exists(conf_uid, saved_uid):
            # This runs on the connect path, so a conversation the app can no
            # longer load (corrupt file, memory rebuild blowing up) must not be
            # allowed to make the app unopenable. Losing the resume is annoying;
            # a client that cannot connect at all is worse.
            try:
                messages = self._activate_history(context, client_uid, saved_uid)
            except Exception as e:
                logger.warning(
                    f"Could not resume conversation {saved_uid} "
                    f"({type(e).__name__}: {e}); starting a new one"
                )
            else:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "history-data",
                            "history_uid": saved_uid,
                            "messages": messages,
                            "restored": True,
                        }
                    )
                )
                logger.info(
                    f"Restored active conversation {saved_uid} "
                    f"({len(messages)} messages) for client {client_uid}"
                )
                return

        # Nothing to resume: a first-ever connection, the saved conversation was
        # deleted while the browser was closed, or it failed to load.
        await self._handle_create_history(websocket, client_uid, {})

    async def _handle_fetch_history(
        self, websocket: WebSocket, client_uid: str, data: dict
    ):
        """Handle fetching and setting specific chat history"""
        history_uid = data.get("history_uid")
        if not history_uid:
            return

        context = self.client_contexts[client_uid]
        messages = self._activate_history(context, client_uid, history_uid)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "history-data",
                    "history_uid": history_uid,
                    "messages": messages,
                }
            )
        )

    async def _handle_create_history(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle creation of new chat history"""
        context = self.client_contexts[client_uid]
        clear_proactive_context(
            context.character_config.conf_uid,
            proactive_context_uid(context.history_uid, client_uid),
        )
        history_uid = create_new_history(context.character_config.conf_uid)
        if history_uid:
            context.history_uid = history_uid
            if context.agent_engine is not None:
                context.agent_engine.set_memory_from_history(
                    conf_uid=context.character_config.conf_uid,
                    history_uid=history_uid,
                )
            self._remember_active_history(
                context.character_config.conf_uid, history_uid
            )
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "new-history-created",
                        "history_uid": history_uid,
                    }
                )
            )

    async def _handle_delete_history(
        self, websocket: WebSocket, client_uid: str, data: dict
    ):
        """Handle deletion of chat history"""
        history_uid = data.get("history_uid")
        if not history_uid:
            return

        context = self.client_contexts[client_uid]
        success = delete_history(
            context.character_config.conf_uid,
            history_uid,
        )
        await websocket.send_text(
            json.dumps(
                {
                    "type": "history-deleted",
                    "success": success,
                    "history_uid": history_uid,
                }
            )
        )
        if history_uid == context.history_uid:
            context.history_uid = None
        if success and history_uid == get_active_history_uid(
            context.character_config.conf_uid
        ):
            clear_active_history_uid(context.character_config.conf_uid)

    async def _handle_audio_data(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle incoming audio data"""
        audio_data = data.get("audio", [])
        if audio_data:
            self.received_data_buffers[client_uid] = np.append(
                self.received_data_buffers[client_uid],
                np.array(audio_data, dtype=np.float32),
            )

    async def _handle_raw_audio_data(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle incoming raw audio data for VAD processing"""
        context = self.client_contexts[client_uid]
        # vad_engine can be None if VAD failed to load (graceful init_vad). Raw audio
        # streams continuously, so silently ignore it rather than erroring per chunk.
        if context.vad_engine is None:
            return
        chunk = data.get("audio", [])
        if chunk:
            for audio_bytes in context.vad_engine.detect_speech(chunk):
                if audio_bytes == b"<|PAUSE|>":
                    await websocket.send_text(
                        json.dumps({"type": "control", "text": "interrupt"})
                    )
                elif audio_bytes == b"<|RESUME|>":
                    pass
                elif len(audio_bytes) > 1024:
                    # Detected audio activity (voice)
                    self.received_data_buffers[client_uid] = np.append(
                        self.received_data_buffers[client_uid],
                        np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32),
                    )
                    await websocket.send_text(
                        json.dumps({"type": "control", "text": "mic-audio-end"})
                    )

    async def _handle_conversation_trigger(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle triggers that start a conversation"""
        # 主動發言的計時器在前端，每個連線各有一個。兩台同時開著時兩邊都會送
        # ai-speak-signal，角色就各講各的——兩台看到的內容不一樣，而且兩句都被寫
        # 進同一段對話。只讓最近使用過的那台發動；它講的話會透過 history 推送
        # 同步到另一台，所以另一台不會漏掉內容。
        # 群組模式刻意不套這條限制：群組成員是不同角色、不同對話，判定天生就不會
        # 把他們算成同一組，兩邊各自觸發是可以的——一次觸發本來就會讓每個成員輪流
        # 講一輪，兩次觸發只是兩輪重疊，使用者要的是後者。
        if data.get("type") == "ai-speak-signal" and not is_proactive_owner(
            self.client_contexts, self.client_last_active, client_uid
        ):
            logger.debug(
                f"Ignoring ai-speak-signal from {client_uid}: another client on this "
                "conversation was used more recently"
            )
            return

        await handle_conversation_trigger(
            msg_type=data.get("type", ""),
            data=data,
            client_uid=client_uid,
            context=self.client_contexts[client_uid],
            websocket=websocket,
            client_contexts=self.client_contexts,
            client_connections=self.client_connections,
            chat_group_manager=self.chat_group_manager,
            received_data_buffers=self.received_data_buffers,
            current_conversation_tasks=self.current_conversation_tasks,
            broadcast_to_group=self.broadcast_to_group,
        )

        # 這一輪跑完之後，把更新後的紀錄推給同一段對話的其他裝置。掛在 task 的
        # done callback 上而不是把 callback 一路穿過對話流程：這裡本來就拿得到
        # 連線與 context，對話那邊不需要知道有幾台裝置在看。
        #
        # 對話是 create_task 起的，handle_conversation_trigger 立刻返回，所以要
        # 從 current_conversation_tasks 取回那個 task。被打斷（cancel）時一樣要
        # 推——人類那則訊息在回合開頭就已經存進去了。
        task = self.current_conversation_tasks.get(client_uid)
        if task is not None and not task.done():
            task.add_done_callback(
                lambda _t, uid=client_uid: asyncio.create_task(
                    self._push_history_to_peers(uid)
                )
            )

    async def _push_history_to_peers(self, origin_client_uid: str) -> None:
        """把這段對話的最新內容推給正在看同一段的其他連線。

        重用 history-data + restored=True：前端收到就直接換掉訊息列表，而且
        restored 會讓它不要跳「已載入歷史」的通知（那是給使用者主動切換用的）。
        不另外定義訊息型別，就不會有第二份需要跟著維護的訊息形狀。
        """
        peers = select_history_peers(self.client_contexts, origin_client_uid)
        if not peers:
            return

        origin = self.client_contexts[origin_client_uid]
        history_uid = origin.history_uid
        conf_uid = origin.character_config.conf_uid
        try:
            messages = get_history(conf_uid, history_uid)
        except Exception as e:
            logger.warning(
                f"Could not read history for peer push ({type(e).__name__}: {e})"
            )
            return

        payload = json.dumps(
            {
                "type": "history-data",
                "history_uid": history_uid,
                "messages": messages,
                "restored": True,
            }
        )
        for uid in peers:
            ws = self.client_connections.get(uid)
            if ws is None:
                continue
            try:
                await ws.send_text(payload)
            except Exception as e:
                # 一個已經斷掉的連線不該讓其他裝置也收不到。
                logger.debug(
                    f"Peer history push to {uid} failed ({type(e).__name__}: {e})"
                )

    async def _handle_fetch_configs(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle fetching available configurations"""
        context = self.client_contexts[client_uid]
        config_files = scan_config_alts_directory(context.system_config.config_alts_dir)
        await websocket.send_text(
            json.dumps({"type": "config-files", "configs": config_files})
        )

    async def _handle_config_switch(
        self, websocket: WebSocket, client_uid: str, data: dict
    ):
        """Handle switching to a different configuration"""
        config_file_name = data.get("file")
        if config_file_name:
            context = self.client_contexts[client_uid]
            await context.handle_config_switch(websocket, config_file_name)

    async def _handle_persona_switch(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Apply a prompt preset without changing character, model, voice or memory."""
        context = self.client_contexts[client_uid]
        await context.apply_persona(websocket, data.get("persona_id"))

    async def _handle_fetch_backgrounds(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle fetching available background images"""
        bg_files = scan_bg_directory()
        await websocket.send_text(
            json.dumps({"type": "background-files", "files": bg_files})
        )

    async def _handle_audio_play_start(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """
        Handle audio playback start notification
        """
        group_members = self.chat_group_manager.get_group_members(client_uid)
        if len(group_members) > 1:
            display_text = data.get("display_text")
            if display_text:
                silent_payload = prepare_audio_payload(
                    audio_path=None,
                    display_text=display_text,
                    actions=None,
                    forwarded=True,
                )
                await self.broadcast_to_group(
                    group_members, silent_payload, exclude_uid=client_uid
                )

    async def _handle_group_info(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle group info request"""
        await self.send_group_update(websocket, client_uid)

    async def _handle_init_config_request(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle request for initialization configuration"""
        context = self.client_contexts.get(client_uid)
        if not context:
            context = self.default_context_cache

        await websocket.send_text(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": context.live2d_model.model_info,
                    "conf_name": context.character_config.conf_name,
                    "conf_uid": context.character_config.conf_uid,
                    "client_uid": client_uid,
                }
            )
        )

    async def _handle_heartbeat(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle heartbeat messages from clients"""
        try:
            await websocket.send_json({"type": "heartbeat-ack"})
        except Exception as e:
            logger.error(f"Error sending heartbeat acknowledgment: {e}")
