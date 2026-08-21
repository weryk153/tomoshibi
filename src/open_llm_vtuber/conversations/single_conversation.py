from typing import Union, List, Dict, Any, Optional, Callable, Awaitable
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
from ..service_context import ServiceContext
from ..conversation_quality import (
    ResponseRepetitionGuard,
    is_generic_assistant_boilerplate,
    normalize_output_language_variant,
)
from ..reply_history import (
    build_recent_reply_guidance,
    build_reply_retry_prompt,
    recent_sentences,
    record_reply,
)
from ..proactive_context import (
    build_proactive_retry_prompt,
    record_proactive_response,
    record_suppressed_proactive,
    should_suppress_proactive_text,
)

# Import necessary types from agent outputs
from ..agent.output_types import SentenceOutput, AudioOutput

# 保存背景核心記憶整理 task 的 reference，避免被 GC
_BG_MEMORY_TASKS: set = set()

# 每個連線各自數輪數，用來決定何時整理記憶。
# (conf_uid, client_uid) so each character + client tracks its own cadence.
# 只存在記憶體：重啟就歸零，整理週期重新開始，可以接受。
_TURN_COUNTS: "dict[tuple[str, str], int]" = {}


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


async def _speak(
    output_item,
    *,
    context: ServiceContext,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    subtitle_response_parts: List[str],
) -> str:
    """把一句送去 TTS 與前端，回傳它貢獻給 full_response 的文字。

    抽出來是因為現在有三個地方要送：串流當下放行的、串流結束時補送的、以及
    重生之後的。三份一樣的十行參數列表很容易改了一份忘了另外兩份。

    簡繁正規化也放這裡。原本只寫在主串流迴圈裡，重生那條路繞過它，於是重生
    出來的句子沒被轉成正體——差一個「来」/「來」就讓逐字比對失效，重複因此
    照樣漏出去。共用的出口只能有一個。
    """
    if isinstance(output_item, SentenceOutput):
        output_language = _effective_output_language(context)
        output_item.display_text.text = normalize_output_language_variant(
            output_item.display_text.text, output_language
        )
        output_item.tts_text = normalize_output_language_variant(
            output_item.tts_text, output_language
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
    # 護欄帶著最近幾則回覆的句子當種子。單看一則的話攔不到實測最常見的重複
    # ——模型換掉開頭四個字、正文整段照抄，整則比對認為那是不同的回覆。
    # 主動發言有自己的跨輪機制（proactive_context），不種，免得兩層打架。
    repetition_guard = ResponseRepetitionGuard(
        seen=(
            []
            if is_proactive
            else recent_sentences(context.character_config.conf_uid, client_uid)
        )
    )

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

        # 預防重複：把最近說過的幾則接在這一輪的輸入後面，讓模型在「生成之前」
        # 就知道自己剛講過什麼。事後偵測到重複再叫它重寫是沒用的——實測顯示那段
        # 指示會被人設、記憶、表情規則的系統提示埋掉。
        #
        # 只餵給模型，不進 input_text 本身：下面的 store_message 用的是 input_text，
        # 混進去的話這段提示會永久留在對話歷史與長期記憶裡。
        model_input_text = input_text
        if not is_proactive and isinstance(input_text, str):
            model_input_text = input_text + build_recent_reply_guidance(
                context.character_config.conf_uid, client_uid
            )

        # Create batch input
        batch_input = create_batch_input(
            input_text=model_input_text,
            images=images,
            from_name=context.character_config.human_name,
            metadata=metadata,
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

        # 睡眠勿擾：晚安→她不再主動開口，下一句真的話就喚醒。規則整條在
        # sleep_mode 模組裡；只餵真人發話——主動觸發的提示不是使用者在講話。
        if not is_proactive and isinstance(input_text, str):
            from ..sleep_mode import note_user_message

            note_user_message(context.character_config.conf_uid, input_text)

        # 對話前刷新核心記憶到 system prompt（phase 1.5）：
        # agent_engine 在 server 開機時烤死 system prompt、新連線只 pass by reference 不重讀，
        # 導致背景 consolidation 寫入的新記憶要等重啟才生效。這裡在每輪對話前重讀 core_memory.md，
        # 只有記憶真的變了（或這個 session context 第一次跑）才重建 prompt 並 set_system，
        # 讓「越聊越認識你」免重啟即時生效，又不動到 agent 的對話歷史。見 MEMORY_SYSTEM_DESIGN.md
        # 長期記憶關閉時跳過 phase-1.5 重注入（construct_system_prompt 本身也已 gate，
        # 這裡短路避免無謂重建 prompt）。
        try:
            from ..memory_core import load_core_memory

            _mem_on = getattr(
                context.character_config, "long_term_memory_enabled", True
            )
            agent = context.agent_engine
            if _mem_on and hasattr(agent, "set_system"):
                fresh_mem = load_core_memory(context.character_config.conf_uid)
                if fresh_mem != getattr(context, "_core_mem_injected", None):
                    refreshed_prompt = await context.construct_system_prompt(
                        context.character_config.persona_prompt
                    )
                    agent.set_system(refreshed_prompt)
                    context._core_mem_injected = fresh_mem
                    logger.info(
                        "[core_memory] system prompt refreshed with latest core memory"
                    )
        except Exception as _refresh_e:
            logger.warning(f"[core_memory] refresh failed: {_refresh_e}")

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
                            )
                        )
                        output_item.tts_text = normalize_output_language_variant(
                            output_item.tts_text,
                            output_language,
                        )

                    if isinstance(
                        output_item, SentenceOutput
                    ) and is_generic_assistant_boilerplate(
                        output_item.display_text.text
                    ):
                        logger.info("Suppressed generic assistant boilerplate")
                        continue

                    if (
                        is_proactive
                        and isinstance(output_item, SentenceOutput)
                        and should_suppress_proactive_text(
                            output_item.display_text.text,
                            forbid_question=bool(
                                metadata and metadata.get("proactive_forbid_question")
                            ),
                            image_sources=(
                                metadata.get("proactive_image_sources")
                                if metadata
                                else None
                            ),
                            recent_outputs=(
                                metadata.get("proactive_recent_outputs")
                                if metadata
                                else None
                            ),
                        )
                    ):
                        # 印出被擋的內容。只寫「Suppressed」的話，事後完全無法判斷
                        # 是過濾器太嚴還是模型真的在生廢話——實測 9 次觸發有 7 次
                        # 整批被擋，而 log 對「擋掉了什麼」一個字都沒有。
                        logger.info(
                            "Suppressed repetitive or generic proactive sentence: "
                            f"{output_item.display_text.text!r}"
                        )
                        # 記下來，否則下一輪的提示詞不知道這句講過，模型會原封不動
                        # 再生一次、再被擋——實測同一句被重生了三十幾次。
                        record_suppressed_proactive(
                            context.character_config.conf_uid,
                            str(
                                (metadata or {}).get("proactive_context_uid")
                                or client_uid
                            ),
                            output_item.display_text.text,
                        )
                        continue

                    if isinstance(
                        output_item, SentenceOutput
                    ) and not repetition_guard.accept(output_item.display_text.text):
                        logger.info("Suppressed repeated or near-duplicate sentence")
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

        # 整則都被護欄丟掉了——代表這一輪講的每一句最近都講過。與其讓她沈默，
        # 帶著「你剛說過這些」重生一次。這條路以前只有主動發言走，現在一般回覆
        # 也需要，因為逐句護欄會整輪丟光。
        if not is_proactive and not full_response:
            logger.info("整則回覆都被跨輪護欄丟掉，重生一次")
            retry_input = create_batch_input(
                # 用 model_input_text：它已經帶著「你最近說過這些」。少了那段，
                # 模型只被告知「換個說法」卻不知道要避開什麼。
                input_text=build_reply_retry_prompt(
                    model_input_text if isinstance(model_input_text, str) else "",
                    "\n".join(
                        recent_sentences(
                            context.character_config.conf_uid, client_uid
                        )[-3:]
                    ),
                ),
                images=images,
                from_name=context.character_config.human_name,
                metadata=metadata,
            )
            # 重生的輸出也要過同一道護欄，否則它可能再講一次剛被丟掉的內容——
            # 實測遇過。這裡先整批收完再決定：重生本來就是罕見路徑，多等這一下
            # 不影響一般情況的延遲，而且收完才有辦法在「全部又是重複」時改口。
            retry_items = []
            try:
                async for retry_item in context.agent_engine.chat(retry_input):
                    if isinstance(retry_item, (SentenceOutput, AudioOutput)):
                        retry_items.append(retry_item)
            except Exception as e:
                logger.warning(f"重生失敗（{type(e).__name__}: {e}）")

            fresh = [
                item
                for item in retry_items
                if not isinstance(item, SentenceOutput)
                or repetition_guard.accept(item.display_text.text)
            ]
            if not fresh and retry_items:
                # 重生出來的還是同一批內容。放行原樣——寧可重複，也不要她突然
                # 沈默；沈默看起來像當掉，而使用者無從得知發生了什麼事。
                logger.info("重生仍是重複的內容，放行以免整輪沈默")
                fresh = retry_items
            for item in fresh:
                full_response += await _speak(
                    item,
                    context=context,
                    websocket_send=websocket_send,
                    tts_manager=tts_manager,
                    subtitle_response_parts=subtitle_response_parts,
                )

        if is_proactive and not full_response:
            logger.info(
                "All proactive sentences were suppressed; retrying once as a statement"
            )
            retry_batch_input = create_batch_input(
                input_text=build_proactive_retry_prompt(input_text),
                images=images,
                from_name=context.character_config.human_name,
                metadata=metadata,
            )
            try:
                retry_stream = context.agent_engine.chat(retry_batch_input)
                async for output_item in retry_stream:
                    if not isinstance(output_item, (SentenceOutput, AudioOutput)):
                        continue
                    if isinstance(output_item, SentenceOutput):
                        output_language = _effective_output_language(context)
                        output_item.display_text.text = (
                            normalize_output_language_variant(
                                output_item.display_text.text,
                                output_language,
                            )
                        )
                        output_item.tts_text = normalize_output_language_variant(
                            output_item.tts_text,
                            output_language,
                        )
                        if is_generic_assistant_boilerplate(
                            output_item.display_text.text
                        ) or should_suppress_proactive_text(
                            output_item.display_text.text,
                            forbid_question=True,
                            image_sources=(
                                metadata.get("proactive_image_sources")
                                if metadata
                                else None
                            ),
                            recent_outputs=(
                                metadata.get("proactive_recent_outputs")
                                if metadata
                                else None
                            ),
                        ):
                            logger.info(
                                "Suppressed retry sentence: "
                                f"{output_item.display_text.text!r}"
                            )
                            record_suppressed_proactive(
                                context.character_config.conf_uid,
                                str(
                                    (metadata or {}).get("proactive_context_uid")
                                    or client_uid
                                ),
                                output_item.display_text.text,
                            )
                            continue
                        if not repetition_guard.accept(output_item.display_text.text):
                            logger.info(
                                "Suppressed repeated or near-duplicate retry sentence"
                            )
                            continue

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
                    if response_part is not None:
                        full_response += str(response_part)
            except Exception as retry_error:
                logger.warning(f"Proactive statement retry failed: {retry_error}")

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
            if not is_proactive:
                # 記下來，下一輪才有東西可以比對。主動發言走 proactive_context
                # 自己那套，不重複記。
                record_reply(
                    context.character_config.conf_uid, client_uid, full_response
                )

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

        # 對話一輪後背景整理核心記憶（fire-and-forget，不阻塞使用者）。見 MEMORY_SYSTEM_DESIGN.md
        # 長期記憶關閉時（long_term_memory_enabled=False）跳過整理，連背景 task 都不建。
        # 節流：memory_consolidation_interval 控制每幾輪才整理一次（1=每輪、預設、行為不變；
        # 3/5 給弱機/本地模型省一半以上「整理用」的 LLM 呼叫）。用 per-session 計數器，
        # 只有 turn % interval == 0 那一輪才排整理 task。整段 fail-soft：計數器出錯絕不弄壞這輪對話。
        try:
            from ..memory_core import (
                consolidate_core_memory,
                resolve_consolidation_llm,
                _clamp_interval,
            )

            _mem_on = getattr(
                context.character_config, "long_term_memory_enabled", True
            )
            if (
                _mem_on
                and not is_proactive
                and isinstance(input_text, str)
                and input_text.strip()
            ):
                _conf_uid = context.character_config.conf_uid
                _interval = _clamp_interval(
                    getattr(
                        context.character_config, "memory_consolidation_interval", 1
                    )
                )
                _key = (str(_conf_uid), str(client_uid))
                _n = _TURN_COUNTS.get(_key, 0) + 1
                _TURN_COUNTS[_key] = _n
                if _n % _interval == 0:
                    _base_url, _model, _api_key, _extra_body = (
                        resolve_consolidation_llm(context.character_config)
                    )
                    _cap = getattr(
                        context.character_config, "core_memory_max_chars", 1500
                    )
                    _t = asyncio.create_task(
                        consolidate_core_memory(
                            _conf_uid,
                            input_text,
                            full_response,
                            _base_url,
                            _model,
                            cap=_cap,
                            api_key=_api_key,
                            extra_body=_extra_body,
                            # 記憶的每一條都要寫明主詞是使用者還是角色，所以
                            # 抽取器需要知道角色叫什麼（見 build_consolidation_prompt）。
                            character_name=getattr(
                                context.character_config, "character_name", ""
                            ),
                        )
                    )
                    # 保存 reference 避免 fire-and-forget task 被 GC（Python asyncio 已知坑）
                    _BG_MEMORY_TASKS.add(_t)
                    _t.add_done_callback(_BG_MEMORY_TASKS.discard)
                else:
                    logger.debug(
                        f"[core_memory] consolidation skipped "
                        f"(turn {_n}, every {_interval})"
                    )
        except Exception as _mem_e:
            logger.warning(f"[core_memory] schedule failed: {_mem_e}")

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
