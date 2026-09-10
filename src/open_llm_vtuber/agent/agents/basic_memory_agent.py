from typing import (
    AsyncIterator,
    List,
    Dict,
    Any,
    Callable,
    Literal,
    Union,
    Optional,
)
from loguru import logger
from .agent_interface import AgentInterface
from ..output_types import SentenceOutput, DisplayText
from ..stateless_llm.stateless_llm_interface import StatelessLLMInterface
from ..stateless_llm.claude_llm import AsyncLLM as ClaudeAsyncLLM
from ..stateless_llm.openai_compatible_llm import AsyncLLM as OpenAICompatibleAsyncLLM
from ...chat_history_manager import get_history
from ..transformers import (
    sentence_divider,
    actions_extractor,
    tts_filter,
    display_processor,
)
from ...config_manager import TTSPreprocessorConfig
from ..input_types import BatchInput, TextSource
from prompts import prompt_loader
from ...mcpp.tool_manager import ToolManager
from ...mcpp.json_detector import StreamJSONDetector
from ...mcpp.types import ToolCallObject
from ...mcpp.tool_executor import ToolExecutor
from ...conversation_quality import (
    build_turn_guidance,
    deduplicate_response_text,
    normalize_output_language_variant,
)
from ...stage_director import strip_stage_performance_tag
from ...context_window import detect_context_window


# --- 短期記憶的上限 ----------------------------------------------------------
#
# self._memory 原本沒有任何上限：set_memory_from_history 把整段對話全載進來，
# _add_message 一路往後加。長對話遲早撐爆模型的 context window，而症狀不是一個
# 清楚的錯誤——後端根本不知道 window 多大，超過時是推論端（LM Studio / Ollama）
# 自己靜默砍掉最舊的訊息，畫面上只會看到她突然變糊、忘記剛講過的話。
#
# window 設在哪裡：不在這個 repo 裡。專案從不送 num_ctx / max_tokens，payload
# 只有 model / messages / temperature / stream / extra_body。實際值由 LM Studio
# 載入模型時的 Context Length（或 Ollama 的 num_ctx）決定，後端看不到也管不到。
# 至少讓截斷的邏輯掌握在自己手上、砍完會寫 log。
#
# 這裡只做截斷，不做摘要。「別弄丟舊事實」那件事已經有人在做了：core_memory.md
# 每輪整理，第 N 輪的事實在第 N 輪就寫進記憶檔，之後每輪注入進 persona——這正是
# 兩層式設計裡「上層記事實、下層記逐字」的分工。再加一個摘要器等於在同一份資料
# 上放第二個有損壓縮器，兩個提示詞會互相打架。
#
# 但這條分工有前提：長期記憶被關掉（long_term_memory_enabled=False）時沒有
# backstop，被截掉就是真的沒了。那仍然好過撐爆 context，只是值得知道。
#
# 預算怎麼來的（2026-08，開發機實測，qwen/qwen3.5-9b on LM Studio）：
#
#     loaded_context_length            20,992 token（該模型 max 262,144）
#   - 長人設角色的 system prompt           5,479 token
#       persona 2,007 / CORE_CONVERSATION_PROMPT 854 / think_tag 602
#       / live2d_expression 505 / mcp 388 / core_memory 滿載 1,123
#   - 留給生成                          1,500 token
#   = 對話可用                        ~14,000 token
#
# 實測真實對話是 1.57 字元/token（中文比直覺便宜；英文提示詞更省，約 4.4–4.9），
# 所以 14,000 token ≈ 22,000 字元。取 20,000 留一點餘裕。
#
# 這個數字綁在「window 20,992」這個前提上，而那是使用者在 LM Studio 裡按的，
# 隨時可能不一樣（同一台機器上的模型 max 從 2,048 到 262,144 都有）。真正的解法
# 是開機去問 /api/v0/models 的 loaded_context_length 回推——在那之前，這是個
# 有依據但會過期的常數。
MEMORY_MAX_CHARS = 20000  # 問不到 window 時的保守預設，也是「要不要去問」的門檻
MEMORY_MIN_MESSAGES = 24  # 底線：無論多長都留最近這麼多則（約 12 輪一問一答）

# 實測（開發機，qwen/qwen3.5-9b）：真實中文對話 1.57 字元/token，英文提示詞
# 4.4–4.9。system prompt 是中英混雜，用中文的比率去估會高估它的 token 數——
# 那個方向是安全的（預算算得比實際小）。
CHARS_PER_TOKEN = 1.57
GENERATION_RESERVE_TOKENS = 1500  # 留給她把話講完
MIN_BUDGET_CHARS = 2000  # window 小到離譜時的地板，配合 MEMORY_MIN_MESSAGES  # 底線：無論多長都留最近這麼多則（約 12 輪一問一答）


class BasicMemoryAgent(AgentInterface):
    """Agent with basic chat memory and tool calling support."""

    _system: str = "You are a helpful assistant."

    def __init__(
        self,
        llm: StatelessLLMInterface,
        system: str,
        live2d_model,
        tts_preprocessor_config: TTSPreprocessorConfig = None,
        faster_first_response: bool = True,
        segment_method: str = "pysbd",
        use_mcpp: bool = False,
        interrupt_method: Literal["system", "user"] = "user",
        tool_prompts: Dict[str, str] = None,
        tool_manager: Optional[ToolManager] = None,
        tool_executor: Optional[ToolExecutor] = None,
        mcp_prompt_string: str = "",
        player_language: str = "",
        llm_base_url: str = "",
        llm_model: str = "",
    ):
        """Initialize agent with LLM and configuration."""
        super().__init__()
        self._memory = []
        # 記憶要跟顯示／歷史走同一套字形正規化，否則模型讀到的自己是簡體、
        # 使用者看到的是繁體——見 _add_message 裡的說明。
        self._player_language = player_language
        self._live2d_model = live2d_model
        self._tts_preprocessor_config = tts_preprocessor_config
        self._faster_first_response = faster_first_response
        self._segment_method = segment_method
        self._use_mcpp = use_mcpp
        # 只為了問推論端 window 多大而留的；問不到就退回 MEMORY_MAX_CHARS。
        self._llm_base_url = llm_base_url
        self._llm_model = llm_model
        self.interrupt_method = interrupt_method
        self._tool_prompts = tool_prompts or {}
        self._interrupt_handled = False
        self.prompt_mode_flag = False

        self._tool_manager = tool_manager
        self._tool_executor = tool_executor
        self._mcp_prompt_string = mcp_prompt_string
        self._json_detector = StreamJSONDetector()

        self._formatted_tools_openai = []
        self._formatted_tools_claude = []
        if self._tool_manager:
            self._formatted_tools_openai = self._tool_manager.get_formatted_tools(
                "OpenAI"
            )
            self._formatted_tools_claude = self._tool_manager.get_formatted_tools(
                "Claude"
            )
            logger.debug(
                f"Agent received pre-formatted tools - OpenAI: {len(self._formatted_tools_openai)}, Claude: {len(self._formatted_tools_claude)}"
            )
        else:
            logger.debug(
                "ToolManager not provided, agent will not have pre-formatted tools."
            )

        self._set_llm(llm)
        self.set_system(system if system else self._system)

        if self._use_mcpp and not all(
            [
                self._tool_manager,
                self._tool_executor,
                self._json_detector,
            ]
        ):
            logger.warning(
                "use_mcpp is True, but some MCP components are missing in the agent. Tool calling might not work as expected."
            )
        elif not self._use_mcpp and any(
            [
                self._tool_manager,
                self._tool_executor,
                self._json_detector,
            ]
        ):
            logger.warning(
                "use_mcpp is False, but some MCP components were passed to the agent."
            )

        logger.info("BasicMemoryAgent initialized.")

    def _set_llm(self, llm: StatelessLLMInterface):
        """Set the LLM for chat completion."""
        self._llm = llm
        self.chat = self._chat_function_factory()

    def set_system(self, system: str):
        """Set the system prompt."""
        logger.debug(f"Memory Agent: Setting system prompt: '''{system}'''")

        if self.interrupt_method == "user":
            system = f"{system}\n\nIf you received `[interrupted by user]` signal, you were interrupted."

        self._system = system

    def get_recent_context_for_proactive(self) -> str | None:
        """Expose recent real turns so a synthetic proactive prompt stays on topic."""
        lines = []
        for message in self._memory[-4:]:
            role = message.get("role")
            content = str(message.get("content") or "").strip()
            if not content or role not in {"user", "assistant"}:
                continue
            label = "使用者" if role == "user" else "角色"
            lines.append(f"{label}：{content[:500]}")
        return "\n".join(lines) or None

    def _add_message(
        self,
        message: Union[str, List[Dict[str, Any]]],
        role: str,
        display_text: DisplayText | None = None,
        skip_memory: bool = False,
    ):
        """Add message to memory."""
        if skip_memory:
            return

        text_content = ""
        if isinstance(message, list):
            for item in message:
                if item.get("type") == "text":
                    text_content += item["text"] + " "
            text_content = text_content.strip()
        elif isinstance(message, str):
            text_content = message
        else:
            logger.warning(
                f"_add_message received unexpected message type: {type(message)}"
            )
            text_content = str(message)

        if role == "assistant":
            text_content = strip_stage_performance_tag(text_content)
            text_content = deduplicate_response_text(text_content)
            # 顯示與寫入歷史那兩條路都會做這個正規化（single_conversation 對
            # display_text／tts_text 各做一次），只有記憶這條漏了。後果是一個會
            # 自我強化的迴圈：模型某輪漂到簡體 → 畫面與歷史被轉成繁體 → 記憶裡
            # 留的是簡體 → 下一輪它讀到自己的過去發言是簡體 → 更容易繼續漂。
            # debug log 的主動發言錨點裡抓到過繁簡混在同一段的實例。
            # 只影響中文字形，日文／英文回覆原樣通過，不會跟「跟著使用者的語言
            # 回答」互相衝突。
            text_content = normalize_output_language_variant(
                text_content, self._player_language
            )

        if not text_content and role == "assistant":
            return

        message_data = {
            "role": role,
            "content": text_content,
        }

        if display_text:
            if display_text.name:
                message_data["name"] = display_text.name
            if display_text.avatar:
                message_data["avatar"] = display_text.avatar

        if (
            self._memory
            and self._memory[-1]["role"] == role
            and self._memory[-1]["content"] == text_content
        ):
            return

        self._memory.append(message_data)
        self._trim_memory()

    def _memory_budget_chars(self) -> int:
        """這一輪能留多少字的對話。

        問得到 window 就照實算，問不到退回 MEMORY_MAX_CHARS。用 self._system
        當場量 system prompt，而不是寫死一個保留值——每個角色的人設長度差很多
        （實測長人設的 persona 2,007 token、Mao 只有 55），寫死等於對其中一個
        算錯。system prompt 每輪會被重新組（記憶刷新），所以每次都重算。

        偵測到的值可以比保守預設更小：window 真的只有 4k 時就該勒緊，那正是
        去問的理由。MEMORY_MIN_MESSAGES 和 MIN_BUDGET_CHARS 一起兜住地板。
        """
        window = detect_context_window(self._llm_base_url, self._llm_model)
        if not window:
            return MEMORY_MAX_CHARS

        system_tokens = len(self._system) / CHARS_PER_TOKEN
        usable = window - system_tokens - GENERATION_RESERVE_TOKENS
        return max(int(usable * CHARS_PER_TOKEN), MIN_BUDGET_CHARS)

    def _trim_memory(self) -> None:
        """把最舊的對話丟掉，直到記憶回到預算內。

        兩道界線，先撞到哪道就停在哪道：字元預算（MEMORY_MAX_CHARS）與則數底線
        （MEMORY_MIN_MESSAGES）。底線優先——寧可稍微超出預算，也不要把對話砍到
        接不上話。實測 20 輪語音對話大約 4–8k token，正常聊天根本碰不到截斷。

        丟到最後會讓開頭停在 assistant 那則。留著不會壞，但接下來的訊息串就是
        「她先開口、使用者才回」，跟真實對話的形狀對不上；模型讀到的第一件事變成
        自己的話，容易照著它的語氣續寫。多丟一則讓開頭回到 user。
        """
        if len(self._memory) <= MEMORY_MIN_MESSAGES:
            return

        total = sum(len(str(m.get("content", ""))) for m in self._memory)
        if total <= MEMORY_MAX_CHARS:
            # 還在保守預算內，怎麼算都不用截——這條 early return 同時是「不去
            # 探測 window」的守門員，正常對話因此一次網路請求都不會發。
            return

        budget = self._memory_budget_chars()
        dropped = 0
        while total > budget and len(self._memory) > MEMORY_MIN_MESSAGES:
            total -= len(str(self._memory[0].get("content", "")))
            self._memory.pop(0)
            dropped += 1

        # 對齊到 user 開頭。這一步不受底線保護——底線是「留幾則」，這裡是
        # 「留下來的第一則是誰說的」，讓底線擋住它會留下錯的形狀。最多只會多丟一則。
        if self._memory and self._memory[0]["role"] != "user":
            self._memory.pop(0)
            dropped += 1

        if dropped:
            logger.info(
                "Trimmed {} oldest message(s) from working memory; {} left "
                "(~{} chars, budget {}). Older facts survive in core_memory.md.",
                dropped,
                len(self._memory),
                sum(len(str(m.get("content", ""))) for m in self._memory),
                budget,
            )

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        """Load a clean alternating conversation from chat history.

        Older versions stored proactive AI speech without a matching user turn.
        Keeping those consecutive assistant messages in model memory makes the
        next proactive completion repeat or imitate them.  Preserve the history
        file for the UI, but omit invalid roles and later same-role entries from
        the model-facing memory.
        """
        messages = get_history(conf_uid, history_uid)

        self._memory = []
        skipped = 0
        for msg in messages:
            history_role = msg.get("role")
            if history_role not in {"human", "ai"}:
                skipped += 1
                continue

            role = "user" if history_role == "human" else "assistant"
            content = msg.get("content")
            if not isinstance(content, str) or not content.strip():
                logger.warning(f"Skipping invalid message from history: {msg}")
                skipped += 1
                continue

            if self._memory and self._memory[-1]["role"] == role:
                skipped += 1
                continue

            self._memory.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        logger.info(
            "Loaded {} messages from history; omitted {} invalid or "
            "consecutive same-role entries.",
            len(self._memory),
            skipped,
        )
        # 載入是第二個會撐爆 context 的入口：一段長對話重連時會一次全部灌進來，
        # 光靠 _add_message 那邊的截斷擋不住（那是一則一則長出來的路徑）。
        self._trim_memory()

    def handle_interrupt(self, heard_response: str) -> None:
        """Handle user interruption."""
        if self._interrupt_handled:
            return

        self._interrupt_handled = True

        # 只在真的聽到內容時才補 "..."（表示話被打斷）；heard_response 為空/全空白時
        # 不附 "..."，避免把無意義的 "..." 寫進記憶，僅留下 [Interrupted by user] 標記。
        partial = (heard_response + "...") if heard_response.strip() else heard_response

        if self._memory and self._memory[-1]["role"] == "assistant":
            self._memory[-1]["content"] = partial
        elif heard_response:
            self._memory.append(
                {
                    "role": "assistant",
                    "content": partial,
                }
            )

        interrupt_role = "system" if self.interrupt_method == "system" else "user"
        self._memory.append(
            {
                "role": interrupt_role,
                "content": "[Interrupted by user]",
            }
        )
        logger.info(f"Handled interrupt with role '{interrupt_role}'.")

    def _to_text_prompt(self, input_data: BatchInput) -> str:
        """Format input data to text prompt."""
        message_parts = []

        for text_data in input_data.texts:
            if text_data.source == TextSource.INPUT:
                message_parts.append(text_data.content)
            elif text_data.source == TextSource.CLIPBOARD:
                message_parts.append(
                    f"[User shared content from clipboard: {text_data.content}]"
                )

        if input_data.images:
            message_parts.append("\n[User has also provided images]")

        return "\n".join(message_parts).strip()

    def _to_messages(self, input_data: BatchInput) -> List[Dict[str, Any]]:
        """Prepare messages for LLM API call."""
        messages = self._memory.copy()
        user_content = []
        text_prompt = self._to_text_prompt(input_data)
        previous_proactive = (
            input_data.metadata.get("previous_proactive_response")
            if input_data.metadata
            else None
        )
        if isinstance(previous_proactive, str) and previous_proactive.strip():
            proactive_message = previous_proactive.strip()
            if messages and messages[-1].get("role") == "assistant":
                # Preserve valid role alternation for strict ChatML templates while
                # making the proactive remark the assistant's most recent utterance.
                existing = str(messages[-1].get("content") or "").strip()
                messages[-1] = {
                    **messages[-1],
                    "content": (
                        f"{existing}\n\n{proactive_message}"
                        if existing
                        else proactive_message
                    ),
                }
            else:
                messages.append(
                    {
                        "role": "assistant",
                        "content": proactive_message,
                    }
                )

        if text_prompt:
            api_text_prompt = text_prompt + build_turn_guidance(
                text_prompt,
                is_proactive=bool(
                    input_data.metadata and input_data.metadata.get("proactive_speak")
                ),
            )
            user_content.append({"type": "text", "text": api_text_prompt})

        if input_data.images:
            image_added = False
            for img_data in input_data.images:
                if isinstance(img_data.data, str) and img_data.data.startswith(
                    "data:image"
                ):
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": img_data.data, "detail": "auto"},
                        }
                    )
                    image_added = True
                else:
                    logger.error(
                        f"Invalid image data format: {type(img_data.data)}. Skipping image."
                    )

            if not image_added and not text_prompt:
                logger.warning(
                    "User input contains images but none could be processed."
                )

        if user_content:
            user_message = {"role": "user", "content": user_content}
            messages.append(user_message)

            skip_memory = False
            if input_data.metadata and input_data.metadata.get("skip_memory", False):
                skip_memory = True

            if not skip_memory:
                self._add_message(
                    text_prompt if text_prompt else "[User provided image(s)]", "user"
                )
        else:
            logger.warning("No content generated for user message.")

        return messages

    async def _claude_tool_interaction_loop(
        self,
        initial_messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        skip_memory: bool = False,
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Handle Claude interaction loop with tool support."""
        messages = initial_messages.copy()
        current_turn_text = ""
        pending_tool_calls = []
        current_assistant_message_content = []

        while True:
            stream = self._llm.chat_completion(messages, self._system, tools=tools)
            pending_tool_calls.clear()
            current_assistant_message_content.clear()

            async for event in stream:
                if event["type"] == "text_delta":
                    text = event["text"]
                    current_turn_text += text
                    yield text
                    if (
                        not current_assistant_message_content
                        or current_assistant_message_content[-1]["type"] != "text"
                    ):
                        current_assistant_message_content.append(
                            {"type": "text", "text": text}
                        )
                    else:
                        current_assistant_message_content[-1]["text"] += text
                elif event["type"] == "tool_use_complete":
                    tool_call_data = event["data"]
                    logger.info(
                        f"Tool request: {tool_call_data['name']} (ID: {tool_call_data['id']})"
                    )
                    pending_tool_calls.append(tool_call_data)
                    current_assistant_message_content.append(
                        {
                            "type": "tool_use",
                            "id": tool_call_data["id"],
                            "name": tool_call_data["name"],
                            "input": tool_call_data["input"],
                        }
                    )
                # elif event["type"] == "message_delta":
                #     if event["data"]["delta"].get("stop_reason"):
                #         stop_reason = event["data"]["delta"].get("stop_reason")
                elif event["type"] == "message_stop":
                    break
                elif event["type"] == "error":
                    logger.error(f"LLM API Error: {event['message']}")
                    yield f"[Error from LLM: {event['message']}]"
                    return

            if pending_tool_calls:
                filtered_assistant_content = [
                    block
                    for block in current_assistant_message_content
                    if not (
                        block.get("type") == "text"
                        and not block.get("text", "").strip()
                    )
                ]

                if filtered_assistant_content:
                    messages.append(
                        {"role": "assistant", "content": filtered_assistant_content}
                    )
                    assistant_text_for_memory = "".join(
                        [
                            c["text"]
                            for c in filtered_assistant_content
                            if c["type"] == "text"
                        ]
                    ).strip()
                    if assistant_text_for_memory and not skip_memory:
                        self._add_message(assistant_text_for_memory, "assistant")

                tool_results_for_llm = []
                if not self._tool_executor:
                    logger.error(
                        "Claude Tool interaction requested but ToolExecutor is not available."
                    )
                    yield "[Error: ToolExecutor not configured]"
                    return

                tool_executor_iterator = self._tool_executor.execute_tools(
                    tool_calls=pending_tool_calls,
                    caller_mode="Claude",
                )
                try:
                    while True:
                        update = await anext(tool_executor_iterator)
                        if update.get("type") == "final_tool_results":
                            tool_results_for_llm = update.get("results", [])
                            break
                        else:
                            yield update
                except StopAsyncIteration:
                    logger.warning(
                        "Tool executor finished without final results marker."
                    )

                if tool_results_for_llm:
                    messages.append({"role": "user", "content": tool_results_for_llm})

                # stop_reason = None
                continue
            else:
                if current_turn_text and not skip_memory:
                    self._add_message(current_turn_text, "assistant")
                return

    async def _openai_tool_interaction_loop(
        self,
        initial_messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        skip_memory: bool = False,
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Handle OpenAI interaction with tool support."""
        messages = initial_messages.copy()
        current_turn_text = ""
        pending_tool_calls: Union[List[ToolCallObject], List[Dict[str, Any]]] = []
        current_system_prompt = self._system

        while True:
            if self.prompt_mode_flag:
                if self._mcp_prompt_string:
                    current_system_prompt = (
                        f"{self._system}\n\n{self._mcp_prompt_string}"
                    )
                else:
                    logger.warning("Prompt mode active but mcp_prompt_string is empty!")
                    current_system_prompt = self._system
                tools_for_api = None
            else:
                current_system_prompt = self._system
                tools_for_api = tools

            stream = self._llm.chat_completion(
                messages, current_system_prompt, tools=tools_for_api
            )
            pending_tool_calls.clear()
            current_turn_text = ""
            assistant_message_for_api = None
            detected_prompt_json = None
            goto_next_while_iteration = False

            async for event in stream:
                if self.prompt_mode_flag:
                    if isinstance(event, str):
                        current_turn_text += event
                        if self._json_detector:
                            potential_json = self._json_detector.process_chunk(event)
                            if potential_json:
                                try:
                                    if isinstance(potential_json, list):
                                        detected_prompt_json = potential_json
                                    elif isinstance(potential_json, dict):
                                        detected_prompt_json = [potential_json]

                                    if detected_prompt_json:
                                        break
                                except Exception as e:
                                    logger.error(f"Error parsing detected JSON: {e}")
                                    if self._json_detector:
                                        self._json_detector.reset()
                                    yield f"[Error parsing tool JSON: {e}]"
                                    goto_next_while_iteration = True
                                    break
                        yield event
                else:
                    if isinstance(event, str):
                        current_turn_text += event
                        yield event
                    elif isinstance(event, list) and all(
                        isinstance(tc, ToolCallObject) for tc in event
                    ):
                        pending_tool_calls = event
                        assistant_message_for_api = {
                            "role": "assistant",
                            "content": current_turn_text if current_turn_text else None,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": tc.type,
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in pending_tool_calls
                            ],
                        }
                        break
                    elif event == "__API_NOT_SUPPORT_TOOLS__":
                        logger.warning(
                            f"LLM {getattr(self._llm, 'model', '')} has no native tool support. Switching to prompt mode."
                        )
                        self.prompt_mode_flag = True
                        if self._tool_manager:
                            self._tool_manager.disable()
                        if self._json_detector:
                            self._json_detector.reset()
                        goto_next_while_iteration = True
                        break
            if goto_next_while_iteration:
                continue

            if detected_prompt_json:
                logger.info("Processing tools detected via prompt mode JSON.")
                if not skip_memory:
                    self._add_message(current_turn_text, "assistant")

                parsed_tools = self._tool_executor.process_tool_from_prompt_json(
                    detected_prompt_json
                )
                if parsed_tools:
                    tool_results_for_llm = []
                    if not self._tool_executor:
                        logger.error(
                            "Prompt Tool interaction requested but ToolExecutor/MCPClient is not available."
                        )
                        yield "[Error: ToolExecutor/MCPClient not configured for prompt mode]"
                        continue

                    tool_executor_iterator = self._tool_executor.execute_tools(
                        tool_calls=parsed_tools,
                        caller_mode="Prompt",
                    )
                    try:
                        while True:
                            update = await anext(tool_executor_iterator)
                            if update.get("type") == "final_tool_results":
                                tool_results_for_llm = update.get("results", [])
                                break
                            else:
                                yield update
                    except StopAsyncIteration:
                        logger.warning(
                            "Prompt mode tool executor finished without final results marker."
                        )

                    if tool_results_for_llm:
                        result_strings = [
                            res.get("content", "Error: Malformed result")
                            for res in tool_results_for_llm
                        ]
                        combined_results_str = "\n".join(result_strings)
                        messages.append(
                            {"role": "user", "content": combined_results_str}
                        )
                continue

            elif pending_tool_calls and assistant_message_for_api:
                messages.append(assistant_message_for_api)
                if current_turn_text and not skip_memory:
                    self._add_message(current_turn_text, "assistant")

                tool_results_for_llm = []
                if not self._tool_executor:
                    logger.error(
                        "OpenAI Tool interaction requested but ToolExecutor/MCPClient is not available."
                    )
                    yield "[Error: ToolExecutor/MCPClient not configured for OpenAI mode]"
                    continue

                tool_executor_iterator = self._tool_executor.execute_tools(
                    tool_calls=pending_tool_calls,
                    caller_mode="OpenAI",
                )
                try:
                    while True:
                        update = await anext(tool_executor_iterator)
                        if update.get("type") == "final_tool_results":
                            tool_results_for_llm = update.get("results", [])
                            break
                        else:
                            yield update
                except StopAsyncIteration:
                    logger.warning(
                        "OpenAI tool executor finished without final results marker."
                    )

                if tool_results_for_llm:
                    messages.extend(tool_results_for_llm)
                continue

            else:
                if current_turn_text and not skip_memory:
                    self._add_message(current_turn_text, "assistant")
                return

    def _chat_function_factory(
        self,
    ) -> Callable[[BatchInput], AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]]:
        """Create the chat pipeline function."""

        @tts_filter(self._tts_preprocessor_config)
        @display_processor()
        @actions_extractor(self._live2d_model)
        @sentence_divider(
            faster_first_response=self._faster_first_response,
            segment_method=self._segment_method,
            valid_tags=["think"],
        )
        async def chat_with_memory(
            input_data: BatchInput,
        ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
            """Process chat with memory and tools."""
            self.reset_interrupt()
            self.prompt_mode_flag = False

            messages = self._to_messages(input_data)
            skip_memory = bool(
                input_data.metadata and input_data.metadata.get("skip_memory", False)
            )
            tools = None
            tool_mode = None
            llm_supports_native_tools = False

            if self._use_mcpp and self._tool_manager:
                tools = None
                if isinstance(self._llm, ClaudeAsyncLLM):
                    tool_mode = "Claude"
                    tools = self._formatted_tools_claude
                    llm_supports_native_tools = True
                elif isinstance(self._llm, OpenAICompatibleAsyncLLM):
                    tool_mode = "OpenAI"
                    tools = self._formatted_tools_openai
                    llm_supports_native_tools = True
                else:
                    logger.warning(
                        f"LLM type {type(self._llm)} not explicitly handled for tool mode determination."
                    )

                if llm_supports_native_tools and not tools:
                    logger.warning(
                        f"No tools available/formatted for '{tool_mode}' mode, despite MCP being enabled."
                    )

            if self._use_mcpp and tool_mode == "Claude":
                logger.debug(
                    f"Starting Claude tool interaction loop with {len(tools)} tools."
                )
                async for output in self._claude_tool_interaction_loop(
                    messages, tools if tools else [], skip_memory=skip_memory
                ):
                    yield output
                return
            elif self._use_mcpp and tool_mode == "OpenAI":
                logger.debug(
                    f"Starting OpenAI tool interaction loop with {len(tools)} tools."
                )
                async for output in self._openai_tool_interaction_loop(
                    messages, tools if tools else [], skip_memory=skip_memory
                ):
                    yield output
                return
            else:
                logger.info("Starting simple chat completion.")
                token_stream = self._llm.chat_completion(messages, self._system)
                complete_response = ""
                async for event in token_stream:
                    text_chunk = ""
                    if isinstance(event, dict) and event.get("type") == "text_delta":
                        text_chunk = event.get("text", "")
                    elif isinstance(event, str):
                        text_chunk = event
                    else:
                        continue
                    if text_chunk:
                        yield text_chunk
                        complete_response += text_chunk
                if complete_response and not skip_memory:
                    self._add_message(complete_response, "assistant")

        return chat_with_memory

    async def chat(
        self,
        input_data: BatchInput,
    ) -> AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]:
        """Run chat pipeline."""
        chat_func_decorated = self._chat_function_factory()
        async for output in chat_func_decorated(input_data):
            yield output

    def reset_interrupt(self) -> None:
        """Reset interrupt flag."""
        self._interrupt_handled = False

    def start_group_conversation(
        self, human_name: str, ai_participants: List[str]
    ) -> None:
        """Start a group conversation."""
        if not self._tool_prompts:
            logger.warning("Tool prompts dictionary is not set.")
            return

        other_ais = ", ".join(name for name in ai_participants)
        prompt_name = self._tool_prompts.get("group_conversation_prompt", "")

        if not prompt_name:
            logger.warning("No group conversation prompt name found.")
            return

        try:
            group_context = prompt_loader.load_util(prompt_name).format(
                human_name=human_name, other_ais=other_ais
            )
            self._memory.append({"role": "user", "content": group_context})
        except FileNotFoundError:
            logger.error(f"Group conversation prompt file not found: {prompt_name}")
        except KeyError as e:
            logger.error(f"Missing formatting key in group conversation prompt: {e}")
        except Exception as e:
            logger.error(f"Failed to load group conversation prompt: {e}")
