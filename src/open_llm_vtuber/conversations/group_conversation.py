from typing import Any, Dict, List, Optional, Union
import asyncio
import json
from loguru import logger
from fastapi import WebSocket
import numpy as np

from ..agent.output_types import AudioOutput, SentenceOutput

from .conversation_utils import (
    create_batch_input,
    process_agent_output,
    process_user_input,
    finalize_conversation_turn,
    cleanup_conversation,
    should_skip_history,
    EMOJI_LIST,
)
from .types import (
    BroadcastFunc,
    GroupConversationState,
    BroadcastContext,
    WebSocketSend,
)
from ..service_context import ServiceContext
from ..chat_history_manager import store_message
from .tts_manager import TTSTaskManager


async def process_group_conversation(
    client_contexts: Dict[str, ServiceContext],
    client_connections: Dict[str, WebSocket],
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    initiator_client_uid: str,
    user_input: Union[str, np.ndarray],
    images: Optional[List[Dict[str, Any]]] = None,
    session_emoji: str = np.random.choice(EMOJI_LIST),
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Process group conversation

    Args:
        client_contexts: Dictionary of client contexts
        client_connections: Dictionary of client WebSocket connections
        broadcast_func: Function to broadcast messages to group
        group_members: List of group member UIDs
        initiator_client_uid: UID of conversation initiator
        user_input: Text or audio input from user
        images: Optional list of image data
        session_emoji: Emoji identifier for the conversation
        metadata: Optional metadata for special processing flags
    """
    # Create TTSTaskManager for each member
    tts_managers = {uid: TTSTaskManager() for uid in group_members}

    try:
        logger.info(f"Group Conversation Chain {session_emoji} started!")

        # Initialize state with group_id
        state = GroupConversationState(
            group_id=f"group_{initiator_client_uid}",  # Use same format as chat_group
            session_emoji=session_emoji,
            group_queue=list(group_members),
            memory_index={
                uid: 0 for uid in group_members
            },  # Initialize memory index for each member
        )

        # Initialize group conversation context for each AI
        init_group_conversation_contexts(client_contexts)

        # Get human name from initiator context
        initiator_context = client_contexts.get(initiator_client_uid)
        human_name = (
            initiator_context.character_config.human_name
            if initiator_context
            else "Human"
        )

        # Process initial input
        # 主動發言那一輪的「輸入」是提示詞本身，不是使用者講的話——同一個旗標
        # 既決定要不要寫進歷史，也決定要不要當成使用者發言廣播出去。
        skip_history = should_skip_history(metadata)

        input_text = await process_group_input(
            user_input=user_input,
            initiator_context=initiator_context,
            initiator_ws_send=client_connections[initiator_client_uid].send_text,
            broadcast_func=broadcast_func,
            group_members=group_members,
            initiator_client_uid=initiator_client_uid,
            is_user_speech=not skip_history,
        )

        if not skip_history:
            for member_uid in group_members:
                member_context = client_contexts[member_uid]
                store_message(
                    conf_uid=member_context.character_config.conf_uid,
                    history_uid=member_context.history_uid,
                    role="human",
                    content=input_text,
                    name=human_name,
                )
        else:
            logger.debug("Skipping storing proactive speak input to group history")

        state.conversation_history = [f"{human_name}: {input_text}"]

        is_first_responder = False
        # Main conversation loop
        while state.group_queue:
            try:
                current_member_uid = state.group_queue.pop(0)

                # Only pass metadata to the first responder
                current_metadata = None
                if is_first_responder:
                    current_metadata = metadata
                    is_first_responder = False

                await handle_group_member_turn(
                    current_member_uid=current_member_uid,
                    state=state,
                    client_contexts=client_contexts,
                    client_connections=client_connections,
                    broadcast_func=broadcast_func,
                    group_members=group_members,
                    images=images,
                    tts_manager=tts_managers[current_member_uid],
                    metadata=current_metadata,
                )
            except Exception as e:
                logger.error(f"Error in group member turn: {e}")
                await handle_member_error(
                    broadcast_func, group_members, f"Error in conversation: {str(e)}"
                )

    except asyncio.CancelledError:
        logger.info(
            f"🤡👍 Group Conversation {session_emoji} cancelled because interrupted."
        )
        raise
    except Exception as e:
        logger.error(f"Error in group conversation chain: {e}")
        await handle_member_error(
            broadcast_func, group_members, f"Fatal error in conversation: {str(e)}"
        )
        raise
    finally:
        # Cleanup all TTS managers
        for tts_manager in tts_managers.values():
            cleanup_conversation(tts_manager, session_emoji)
        # Clean up
        GroupConversationState.remove_state(state.group_id)


def init_group_conversation_state(
    group_members: List[str], session_emoji: str
) -> GroupConversationState:
    """Initialize group conversation state"""
    return GroupConversationState(
        conversation_history=[],
        memory_index={uid: 0 for uid in group_members},
        group_queue=list(group_members),
        session_emoji=session_emoji,
    )


def init_group_conversation_contexts(
    client_contexts: Dict[str, ServiceContext],
) -> None:
    """Initialize group conversation context for each AI participant"""
    ai_names = [ctx.character_config.character_name for ctx in client_contexts.values()]

    for context in client_contexts.values():
        agent = context.agent_engine
        if hasattr(agent, "start_group_conversation"):
            agent.start_group_conversation(
                human_name="Human",
                ai_participants=[
                    name
                    for name in ai_names
                    if name != context.character_config.character_name
                ],
            )
            logger.debug(
                f"Initialized group conversation context for "
                f"{context.character_config.character_name}"
            )


async def process_group_input(
    user_input: Union[str, np.ndarray],
    initiator_context: ServiceContext,
    initiator_ws_send: WebSocketSend,
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    initiator_client_uid: str,
    is_user_speech: bool = True,
) -> str:
    """Process and broadcast user input to group.

    ``is_user_speech`` 為 False 代表這一輪的「輸入」是主動發言的提示詞，不是
    使用者講的話。那段文字是給模型看的系統指令，廣播出去會變成其他成員畫面上的
    一則使用者訊息——整段提示詞原文貼在對話裡。發起端本來就被 exclude_uid 排除，
    所以這個 bug 只有從另一台看得到。
    """
    input_text = await process_user_input(
        user_input, initiator_context.asr_engine, initiator_ws_send
    )
    if is_user_speech:
        await broadcast_transcription(
            broadcast_func, group_members, input_text, initiator_client_uid
        )
    return input_text


async def broadcast_transcription(
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    text: str,
    exclude_uid: str,
) -> None:
    """Broadcast transcription to group members"""
    await broadcast_func(
        group_members,
        {
            "type": "user-input-transcription",
            "text": text,
        },
        exclude_uid,
    )


async def handle_group_member_turn(
    current_member_uid: str,
    state: GroupConversationState,
    client_contexts: Dict[str, ServiceContext],
    client_connections: Dict[str, WebSocket],
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    images: Optional[List[Dict[str, Any]]],
    tts_manager: TTSTaskManager,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Handle a single group member's conversation turn"""
    # Update current speaker before processing
    state.current_speaker_uid = current_member_uid

    await broadcast_thinking_state(broadcast_func, group_members)

    context = client_contexts[current_member_uid]
    current_ws_send = client_connections[current_member_uid].send_text

    new_messages = state.conversation_history[state.memory_index[current_member_uid] :]
    new_context = "\n".join(new_messages) if new_messages else ""

    batch_input = create_batch_input(
        input_text=new_context,
        images=images,
        from_name="Human",
        metadata=metadata,
    )

    logger.info(
        f"AI {context.character_config.character_name} "
        f"(client {current_member_uid}) receiving context:\n{new_context}"
    )

    full_response = await process_member_response(
        context=context,
        batch_input=batch_input,
        current_ws_send=current_ws_send,
        tts_manager=tts_manager,
        broadcast_func=broadcast_func,
        group_members=group_members,
    )

    if tts_manager.task_list:
        # 收尾與 backend-synth-complete 由 finalize_conversation_turn 負責，這裡
        # 不要重複送（原因見 single_conversation.py 同一處的說明）。
        broadcast_ctx = BroadcastContext(
            broadcast_func=broadcast_func,
            group_members=group_members,
            current_client_uid=current_member_uid,
        )

        await finalize_conversation_turn(
            tts_manager=tts_manager,
            websocket_send=current_ws_send,
            client_uid=current_member_uid,
            broadcast_ctx=broadcast_ctx,
        )

    if full_response:
        ai_message = f"{context.character_config.character_name}: {full_response}"
        state.conversation_history.append(ai_message)
        logger.info(f"Appended complete response: {ai_message}")

        # 這裡原本是 for-else：`else` 掛在 for 上（Python 的 for-else），迴圈正常
        # 跑完就會執行，於是一邊存、一邊印「跳過存檔」，而真正的 skip_history
        # 判斷整個不見了——單人對話的主動發言不會寫進歷史，群組模式卻會。
        if should_skip_history(metadata):
            logger.debug("Skipping storing AI response to history (proactive speak)")
        else:
            for member_uid in group_members:
                member_context = client_contexts[member_uid]
                store_message(
                    conf_uid=member_context.character_config.conf_uid,
                    history_uid=member_context.history_uid,
                    role="ai",
                    content=full_response,
                    # 發話成員的名字與頭像，不是接收端的——群組裡每個人的畫面
                    # 都要標出這句是誰講的。
                    name=context.character_config.character_name
                    or context.character_config.conf_name,
                    avatar=context.character_config.avatar,
                )

    state.memory_index[current_member_uid] = len(state.conversation_history)
    state.group_queue.append(current_member_uid)

    # Clear speaker after turn completes
    state.current_speaker_uid = None


async def broadcast_thinking_state(
    broadcast_func: BroadcastFunc, group_members: List[str]
) -> None:
    """Broadcast thinking state to group"""
    await broadcast_func(
        group_members,
        {"type": "control", "text": "conversation-chain-start"},
    )
    await broadcast_func(
        group_members,
        {"type": "full-text", "text": "Thinking...", "text_key": "thinking"},
    )


async def handle_member_error(
    broadcast_func: BroadcastFunc,
    group_members: List[str],
    error_message: str,
) -> None:
    """Handle and broadcast member error"""
    await broadcast_func(
        group_members,
        {
            "type": "error",
            "message": error_message,
        },
    )


async def process_member_response(
    context: ServiceContext,
    batch_input: Any,
    current_ws_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    broadcast_func: Optional[BroadcastFunc] = None,
    group_members: Optional[List[str]] = None,
) -> str:
    """Process group member's response, handling text/audio and tool status events."""
    full_response = ""

    # The AI brain can be unset if it failed to initialize (graceful init_agent).
    if context.agent_engine is None:
        await current_ws_send(
            json.dumps(
                {
                    "type": "error",
                    "message": "AI brain not set up yet — open Settings to configure your LLM.",
                }
            )
        )
        return ""

    try:
        # agent.chat now yields Union[SentenceOutput, Dict[str, Any]]
        agent_output_stream = context.agent_engine.chat(batch_input)

        async for output_item in agent_output_stream:
            if (
                isinstance(output_item, dict)
                and output_item.get("type") == "tool_call_status"
            ):
                if broadcast_func and group_members:
                    logger.debug(f"Broadcasting tool status update: {output_item}")
                    output_item["name"] = context.character_config.character_name
                    await broadcast_func(group_members, output_item)
                else:
                    logger.warning(
                        "Cannot broadcast tool status: broadcast_func or group_members missing."
                    )
            elif isinstance(output_item, (SentenceOutput, AudioOutput)):
                # Handle SentenceOutput or AudioOutput: Send to current user, broadcast audio later if needed
                response_part = await process_agent_output(
                    output=output_item,
                    character_config=context.character_config,
                    live2d_model=context.live2d_model,
                    tts_engine=context.tts_engine,
                    websocket_send=current_ws_send,  # Send TTS/display text directly to speaker's client
                    tts_manager=tts_manager,
                    translate_engine=context.translate_engine,
                    subtitle_translate_engine=context.subtitle_translate_engine,
                )
                full_response += response_part  # Accumulate text response
            else:
                logger.warning(
                    f"Received unexpected item type from agent chat stream: {type(output_item)}"
                )

    except Exception as e:
        logger.exception(f"Error processing group member response stream: {e}")
        await current_ws_send(
            json.dumps(
                {"type": "error", "message": f"Error processing response: {str(e)}"}
            )
        )

    return full_response
