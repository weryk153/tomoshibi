from typing import Union, List, Dict, Any, Optional
import asyncio
import json
from loguru import logger
import numpy as np

from .conversation_utils import (
    create_batch_input,
    process_agent_output,
    send_conversation_start_signals,
    process_user_input,
    finalize_conversation_turn,
    cleanup_conversation,
    EMOJI_LIST,
)
from .types import WebSocketSend
from .tts_manager import TTSTaskManager
from ..chat_history_manager import store_message
from ..character_mood import send_character_mood
from ..service_context import ServiceContext
from ..conversation_quality import normalize_output_language_variant
from ..proactive_context import (
    breaks_what_the_host_knows,
    record_proactive_response,
)

# Import necessary types from agent outputs
from ..agent.output_types import SentenceOutput, AudioOutput


def _effective_output_language(context: ServiceContext) -> str:
    """這一輪要用哪個語言輸出：角色自己的設定優先，沒設就用玩家層級的。

    跟 service_context 建立 agent 時算的是同一件事（reply_language 退回
    player_language），只是那裡的結果進了 agent，這裡的結果要拿去 normalize
    每一則句子的字形變體，所以句子串流當下得再算一次。

    YAML 的空欄位讀出來是 ''，不是 None，所以要當成「沒設」而不是「設成空的」。
    """
    character = getattr(context, "character_config", None)
    system = getattr(context, "system_config", None)
    return str(
        getattr(character, "reply_language", "")
        or getattr(system, "player_language", "")
        or ""
    )


def _protected(context: ServiceContext):
    """這個角色的專有名詞表；沒設就是 None，normalize 會當成沒有表。"""
    return getattr(context.character_config, "protected_names", None)


async def _speak(
    output_item,
    *,
    context: ServiceContext,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    subtitle_response_parts: List[str],
) -> str:
    """把一句送去 TTS 與前端，回傳它貢獻給 full_response 的文字。

    簡繁正規化在這裡做：送出去的每一句都經過同一個出口。
    """
    if isinstance(output_item, SentenceOutput):
        output_language = _effective_output_language(context)
        output_item.display_text.text = normalize_output_language_variant(
            output_item.display_text.text, output_language, _protected(context)
        )
        output_item.tts_text = normalize_output_language_variant(
            output_item.tts_text, output_language, _protected(context)
        )
    response_part = await process_agent_output(
        output=output_item,
        character_config=context.character_config,
        live2d_model=context.live2d_model,
        tts_engine=context.tts_engine,
        websocket_send=websocket_send,
        tts_manager=tts_manager,
        translate_engine=context.translate_engine,
        subtitle_translate_engine=context.subtitle_translate_engine,
        subtitle_collector=subtitle_response_parts,
    )
    return str(response_part) if response_part is not None else ""


async def process_single_conversation(
    context: ServiceContext,
    websocket_send: WebSocketSend,
    client_uid: str,
    user_input: Union[str, np.ndarray],
    images: Optional[List[Dict[str, Any]]] = None,
    session_emoji: str = np.random.choice(EMOJI_LIST),
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Process a single-user conversation turn

    Args:
        context: Service context containing all configurations and engines
        websocket_send: WebSocket send function
        client_uid: Client unique identifier
        user_input: Text or audio input from user
        images: Optional list of image data
        session_emoji: Emoji identifier for the conversation
        metadata: Optional metadata for special processing flags

    Returns:
        str: Complete response text
    """
    # Create TTSTaskManager for this conversation
    tts_manager = TTSTaskManager()
    full_response = ""  # Initialize full_response here
    subtitle_response_parts: List[str] = []
    is_proactive = bool(metadata and metadata.get("proactive_speak"))
    try:
        # Send initial signals
        await send_conversation_start_signals(websocket_send)
        logger.info(f"New Conversation Chain {session_emoji} started!")

        # The AI brain can be unset if it failed to initialize (graceful init_agent).
        # The app still opens so the user can fix it — give a clear notice here rather
        # than letting a raw NoneType error surface.
        if context.agent_engine is None:
            await websocket_send(
                json.dumps(
                    {
                        "type": "error",
                        "message": "AI brain not set up yet — open Settings to configure your LLM.",
                    }
                )
            )
            return ""

        # Process user input
        input_text = await process_user_input(
            user_input, context.asr_engine, websocket_send
        )

        # 給 agent 的兩件它自己分不出來的事：這一輪屬於哪段對話（agent 是所有連線
        # 共用的），以及使用者實際講的是哪一段——引擎記得的要是原話。
        agent_metadata = {**(metadata or {}), "history_uid": context.history_uid}
        if not is_proactive and isinstance(input_text, str):
            agent_metadata["spoken_text"] = input_text

        # Create batch input
        batch_input = create_batch_input(
            input_text=input_text,
            images=images,
            from_name=context.character_config.human_name,
            metadata=agent_metadata,
        )

        # Store user message (check if we should skip storing to history)
        skip_history = metadata and metadata.get("skip_history", False)
        if context.history_uid and not skip_history:
            store_message(
                conf_uid=context.character_config.conf_uid,
                history_uid=context.history_uid,
                role="human",
                content=input_text,
                name=context.character_config.human_name,
            )

        if skip_history:
            logger.debug("Skipping storing user input to history (proactive speak)")

        logger.info(f"User input: {input_text}")
        if images:
            logger.info(f"With {len(images)} images")

        try:
            # agent.chat yields Union[SentenceOutput, Dict[str, Any]]
            agent_output_stream = context.agent_engine.chat(batch_input)

            async for output_item in agent_output_stream:
                if (
                    isinstance(output_item, dict)
                    and output_item.get("type") == "tool_call_status"
                ):
                    # Handle tool status event: send WebSocket message
                    output_item["name"] = context.character_config.character_name
                    logger.debug(f"Sending tool status update: {output_item}")

                    await websocket_send(json.dumps(output_item))

                elif isinstance(output_item, (SentenceOutput, AudioOutput)):
                    if isinstance(output_item, SentenceOutput):
                        output_language = _effective_output_language(context)
                        output_item.display_text.text = (
                            normalize_output_language_variant(
                                output_item.display_text.text,
                                output_language,
                                _protected(context),
                            )
                        )
                        output_item.tts_text = normalize_output_language_variant(
                            output_item.tts_text,
                            output_language,
                            _protected(context),
                        )

                    if (
                        is_proactive
                        and isinstance(output_item, SentenceOutput)
                        # 引擎管不到的只剩主機才知道的事（截圖是哪裡來的、人設不准
                        # 她自稱程式）；重複、客服腔、只應一聲由引擎擋。
                        and breaks_what_the_host_knows(
                            output_item.display_text.text,
                            (metadata or {}).get("proactive_image_sources"),
                        )
                    ):
                        # 印出被擋的內容，事後才判斷得出是過濾器太嚴還是模型真的講錯。
                        logger.info(
                            "Suppressed proactive sentence the host knows is wrong: "
                            f"{output_item.display_text.text!r}"
                        )
                        continue

                    full_response += await _speak(
                        output_item,
                        context=context,
                        websocket_send=websocket_send,
                        tts_manager=tts_manager,
                        subtitle_response_parts=subtitle_response_parts,
                    )
                else:
                    logger.warning(
                        f"Received unexpected item type from agent chat stream: {type(output_item)}"
                    )
                    logger.debug(f"Unexpected item content: {output_item}")

        except Exception as e:
            logger.exception(
                f"Error processing agent response stream: {e}"
            )  # Log with stack trace
            await websocket_send(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Error processing agent response: {str(e)}",
                    }
                )
            )
            # full_response will contain partial response before error
        # --- End processing agent response ---

        # 先存再收尾。full_response 在上面的串流迴圈結束時就已經完整，寫入歷史
        # 不需要等聲音——而 finalize_conversation_turn 會等 TTS 合成收尾、還要等
        # 前端回報 frontend-playback-complete（語音播完）。排在它後面的後果是：
        # 她的字早就顯示在畫面上、聲音也在放了，紀錄卻還沒寫。使用者在她講話中途
        # 重整，那一整輪就永遠不會被存下來，而人類訊息在回合開頭已經存了——症狀
        # 就是「我的話在，她的回覆不見」。重整還會讓 frontend-playback-complete
        # 永遠不回來，後端卡在那個等待上，store 根本執行不到。
        if context.history_uid and full_response and not skip_history:
            store_message(
                conf_uid=context.character_config.conf_uid,
                history_uid=context.history_uid,
                role="ai",
                content=full_response,
                name=context.character_config.character_name
                or context.character_config.conf_name,
                avatar=context.character_config.avatar,
                display_content=("".join(subtitle_response_parts) or None),
            )
            logger.info(f"AI response: {full_response}")

        # 等待 TTS 收尾與送出 backend-synth-complete 都在 finalize_conversation_turn
        # 裡做了，這裡不要再做一次。先前這段會讓 backend-synth-complete 連送兩則，
        # 而前端收到第一則就開始倒數回報播放完成——那時後端還沒掛上等待者，回報
        # 直接被丟掉，接著前端的旗標已被清掉不會再送第二次，於是後端在下面那個
        # wait 上無限等待，conversation-chain-end 永遠不送。
        await finalize_conversation_turn(
            tts_manager=tts_manager,
            websocket_send=websocket_send,
            client_uid=client_uid,
        )

        # 講完了（也包括主動開口）：空檔的臉帶著她這一輪之後的心情。背景的判斷
        # 晚一點才到，到了引擎會再通知（_follow_mood）。
        await send_character_mood(context.agent_engine, websocket_send)

        if is_proactive and full_response:
            proactive_uid = str(
                (metadata or {}).get("proactive_context_uid") or client_uid
            )
            record_proactive_response(
                context.character_config.conf_uid,
                proactive_uid,
                full_response,
            )
            logger.info("Proactive response recorded in rolling anti-repeat context")
            # 她說出口的那句留在引擎的對話裡，指示不留。不然她不記得自己主動說過什麼。
            remember_remark = getattr(context.agent_engine, "remember_remark", None)
            if remember_remark is not None:
                try:
                    await remember_remark(context.history_uid, full_response)
                except Exception as error:
                    logger.warning(f"Proactive remark not kept: {error}")
            # 她提過的新聞之後不再給她，不然同一則標題每次開口都在素材裡。
            try:
                from ..news_topics import note_mentioned

                note_mentioned(full_response, (metadata or {}).get("proactive_source"))
            except Exception as error:
                logger.warning(f"Mentioned news not noted: {error}")

        return full_response  # Return accumulated full_response

    except asyncio.CancelledError:
        logger.info(f"🤡👍 Conversation {session_emoji} cancelled because interrupted.")
        raise
    except Exception as e:
        logger.error(f"Error in conversation chain: {e}")
        await websocket_send(
            json.dumps({"type": "error", "message": f"Conversation error: {str(e)}"})
        )
        raise
    finally:
        cleanup_conversation(tts_manager, session_emoji)
