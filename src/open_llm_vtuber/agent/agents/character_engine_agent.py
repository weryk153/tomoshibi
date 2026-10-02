"""character_engine_agent：整段對話由 AI Character Engine 驅動。

對話、記憶、角色狀態、背景認知、工具迴圈都在引擎的 CharacterCompanion 裡。這裡
只做主機才知道的事：

- 把主機的一輪輸入翻成引擎的一輪（使用者的原話、主機給這一輪的提示、主動發話）。
- 把引擎吐出來的字接回主機的輸出管線（斷句、動作標籤、字幕、TTS 過濾）。
- 把主機的 MCP 工具登記給引擎，工具的進度照舊回報給前端。
- 主機的習慣：一個 agent 所有連線共用、每次儲存設定就重建一個。

這個模組會匯入引擎，所以只能由 agent_factory 在選了這個 agent 時才匯入。
"""

import asyncio
import contextvars
import json
import weakref
from dataclasses import replace
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union
from uuid import uuid4

from ai_character_engine.host import HostBridgeError, image_from_host
from ai_character_engine.companion import CompanionClosed, TurnInterrupted
from ai_character_engine.llm.models import Message
from ai_character_engine.tools.models import ToolDefinition
from ai_character_engine.vision.models import VisionFrame
from loguru import logger

from ...chat_history_manager import get_history
from ...config_manager import TTSPreprocessorConfig
from ...conversation_quality import (
    STREAM_FACT,
    build_turn_guidance,
    deduplicate_response_text,
    normalize_output_language_variant,
)
from ...mcpp.types import ToolCallFunctionObject, ToolCallObject
from ...stage_director import strip_stage_performance_tag
from ..input_types import BatchInput, TextSource
from ..output_types import SentenceOutput
from ..transformers import (
    tidy_marks,
    actions_extractor,
    display_processor,
    sentence_divider,
    tts_filter,
)
from .agent_interface import AgentInterface

INTERRUPT_RULE = (
    "If a reply of yours ends with `[Interrupted by user]`, you were interrupted there."
)
# 她記得什麼由引擎寫進對話的備註；這句告訴她怎麼用。
MEMORY_RULE = "備註裡的記憶是之前對話累積下來的，自然運用、不要生硬複述。"

_DONE = object()
# 這一輪的輸出要送去哪裡。agent 是所有連線共用的，不能記在 agent 身上：第二個
# 連線排隊等引擎的時候，第一個連線的工具進度會跑到它那裡去。引擎那一輪是在
# chat() 裡建的 task，會帶著建立當下的值。
_OUTPUTS: "contextvars.ContextVar[Optional[asyncio.Queue]]" = contextvars.ContextVar(
    "character_engine_outputs", default=None
)
WEEKDAYS = "一二三四五六日"
MAX_PICTURES = 4
MAX_PICTURE_BYTES = 8 * 1024 * 1024
_PICTURE_SOURCES = {"camera": "camera", "screen": "screenshot"}
# 引擎那一側是同一個，agent 卻一直被重建：記下工具是哪個 agent 登記的，
# 換人的時候才知道要重新登記。
_TOOLS_REGISTERED_BY: "weakref.WeakKeyDictionary[Any, int]" = (
    weakref.WeakKeyDictionary()
)


class CharacterEngineAgent(AgentInterface):
    # 她說出口的話由引擎把關（不重複、不講客服腔、不留只剩標點的碎片、主動開口
    # 不只是應一聲）。主機自己那一層過濾對這個 agent 跳過，不然兩邊各擋一次。
    checks_what_she_says = True

    def __init__(
        self,
        *,
        companion: Union[Any, Callable[[], Any]],
        system: str,
        live2d_model,
        tts_preprocessor_config: Optional[TTSPreprocessorConfig] = None,
        faster_first_response: bool = True,
        segment_method: str = "pysbd",
        use_mcpp: bool = False,
        tool_manager=None,
        tool_executor=None,
        player_language: str = "",
        conf_uid: str = "",
        character_name: str = "",
        now: Callable[[], datetime] = datetime.now,
    ):
        """companion 可以是 CharacterCompanion 本身，或是一個每次回傳「目前那一個」
        的函式。正式執行時給的是函式：設定變了引擎那一側會換一個，而舊的 agent
        還被別的連線拿著。
        """
        self._companion_source = companion
        self._player_language = player_language
        self._conf_uid = conf_uid
        self._character_name = character_name
        self._now = now
        self._tools = self._tool_definitions(tool_manager) if use_mcpp else []
        self._tool_executor = tool_executor
        self._conversation: Optional[str] = None
        # 還沒結束的每一輪：(等著它的 task, 它屬於哪段對話, 它的名字)。
        self._turns: list = []
        # 已經講完、但主機那一輪還活著（語音還在播）的：打斷時被取消的是它們的 task。
        self._playing: list = []
        # 最後結束的那一輪：主機等它停了才回報聽到哪裡時，指的是它。
        self._last_ended: Optional[tuple] = None
        # 已經送過打斷的回合名字。它的 task 等引擎停下來的期間，別的連線也可能打斷。
        self._told: set = set()
        self._group_note = ""
        self.set_system(system)

        @tts_filter(tts_preprocessor_config)
        @display_processor()
        @actions_extractor(live2d_model)
        @sentence_divider(
            faster_first_response=faster_first_response,
            segment_method=segment_method,
            valid_tags=["think"],
        )
        async def pipeline(input_data: BatchInput):
            async for output in self._reply(input_data):
                yield output

        self._pipeline = pipeline

    def _companion(self):
        source = self._companion_source
        return source if hasattr(source, "reply") else source()

    # --- 主機交代的事 ---------------------------------------------------------

    def set_system(self, system: str) -> None:
        """主機組好的系統提示（人設與通用規則）。她記得對方什麼、她自己說過什麼，
        都由引擎記、寫進對話的備註。舊 agent 留下的記憶檔不搬：那是當下的話被記成
        事實，搬進來她每一輪都會照著講。"""
        self._system = f"{system}\n\n{MEMORY_RULE}\n\n{INTERRUPT_RULE}"

    # --- 她記得對方什麼 -------------------------------------------------------
    # 記憶頁讀寫的是這一份。

    def conversation_memory(self, history_uid: str) -> str:
        return "\n".join(self._companion().memories(history_uid))

    def rewrite_conversation_memory(
        self, history_uid: str, text: str, *, edited_from: Optional[str] = None
    ) -> None:
        """edited_from 是使用者看到的那一版：只有看到、又被拿掉的行才算刪掉，
        頁面開著的時候引擎新記下的不受影響。"""
        self._companion().rewrite_memories(
            history_uid,
            text.splitlines(),
            edited_from=None if edited_from is None else edited_from.splitlines(),
        )

    # --- 她記得自己什麼 -------------------------------------------------------
    # 記憶頁讀寫的是這一份。

    def self_memory(self) -> str:
        return "\n".join(self._companion().self_memories())

    def rewrite_self_memory(
        self, text: str, *, edited_from: Optional[str] = None
    ) -> None:
        self._companion().rewrite_self_memories(
            text.splitlines(),
            edited_from=None if edited_from is None else edited_from.splitlines(),
        )

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        """之後的每一輪都屬於這段對話。引擎沒看過它的話，從主機的紀錄接著講。"""
        self._conf_uid = conf_uid
        self._conversation = history_uid
        self._hand_over(self._companion(), history_uid)

    def _hand_over(self, companion, history_uid: Optional[str]) -> None:
        if not history_uid or not self._conf_uid:
            return
        if companion.has_conversation(history_uid):
            return
        messages = []
        for entry in get_history(self._conf_uid, history_uid):
            role = {"human": "user", "ai": "assistant"}.get(entry.get("role"))
            content = entry.get("content")
            if role and isinstance(content, str) and content.strip():
                messages.append(Message(role, content))
        # 主機在每一輪開頭就把使用者的話寫進紀錄了；沒人回過的話不算講過，
        # 不然這一輪開頭會是連續兩句使用者的話。
        while messages and messages[-1].role == "user":
            messages.pop()
        companion.load_conversation(history_uid, messages)

    def start_group_conversation(
        self, human_name: str, ai_participants: List[str]
    ) -> None:
        self._group_note = (
            f"這是一場多人對話。使用者是 {human_name}，"
            f"在場的其他角色：{'、'.join(ai_participants)}。"
        )

    def get_recent_context_for_proactive(self) -> Optional[str]:
        lines = []
        for message in self._companion().runtime.history[-4:]:
            if message.role in ("user", "assistant") and message.content.strip():
                label = "使用者" if message.role == "user" else "角色"
                lines.append(f"{label}：{message.content.strip()[:500]}")
        return "\n".join(lines) or None

    def handle_interrupt(self, heard_response: str) -> None:
        """主機打斷的方式是取消等著回覆的那個 task，接著馬上呼叫這裡，不等它停。

        agent 是共用的，這裡又沒有參數說是哪個連線：

        - 有哪一輪「等它的 task 剛被取消」，被打斷的就是它。
        - 沒有的話，她的回覆已經生成完、正在播（主機不會去取消一個結束的 task），
          或是主機等它停了才來回報。兩種都是最後結束的那一輪。

        每一輪都帶著名字交給引擎，所以這裡指的永遠是某一輪，不會是別的連線
        正在生成的那一則。
        """
        self._playing = [entry for entry in self._playing if not entry[0].done()]
        # 送過一次就不再是打斷的對象；它的 task 收尾期間別的連線也可能打斷。
        cancelled = [
            entry
            for entry in (*self._turns, *self._playing)
            if entry[0].cancelling() and entry[2] not in self._told
        ]
        meant = cancelled[-1][1:] if cancelled else self._last_ended
        if cancelled:
            self._told.add(cancelled[-1][2])
        try:
            if meant is None:
                self._companion().interrupt(heard_response)
            else:
                self._companion().interrupt(
                    heard_response, conversation_id=meant[0], turn_id=meant[1]
                )
        except HostBridgeError as exc:
            logger.warning(f"[engine] interrupt not recorded ({exc})")

    async def remember_remark(self, conversation, remark: str) -> None:
        """她主動開口的那一輪帶著一大段指示，以 skip_memory 進行；說出口的那句另外
        記進對話，像她自己說的話一樣。主機在那一輪播完之後呼叫。"""
        await self._companion().remember_remark(conversation, self._remembered(remark))

    def _remembered(self, reply: str) -> str:
        """她記得自己說了什麼：表情與動作
        標籤留著（她得讀到自己會做表情），演出標籤拿掉，字形跟畫面一致。"""
        return normalize_output_language_variant(
            deduplicate_response_text(strip_stage_performance_tag(tidy_marks(reply))),
            self._player_language,
        )

    async def close(self) -> None:
        """一個連線結束時由 ServiceContext.close() 呼叫。

        agent 是所有連線共用的，所以這裡不能把引擎關掉——那樣重新整理一次頁面
        之後她就不會回話了。只存檔。
        """
        self._companion().flush()

    # --- 一輪 -----------------------------------------------------------------

    async def chat(
        self, input_data: BatchInput
    ) -> AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]:
        async for output in self._pipeline(input_data):
            yield output

    def _turn(self, input_data: BatchInput, frames: tuple) -> tuple:
        """(使用者的原話, 主機給這一輪的提示)"""
        metadata = input_data.metadata or {}
        proactive = bool(metadata.get("proactive_speak"))
        said = str(metadata.get("spoken_text") or "")
        parts, notes = [], []
        for text in input_data.texts:
            if text.source == TextSource.CLIPBOARD:
                parts.append(f"[User shared content from clipboard: {text.content}]")
            elif said and text.content.startswith(said):
                # 主機接在原話後面的，是給這一輪的模型看的。
                parts.append(said)
                notes.append(text.content[len(said) :])
            else:
                parts.append(text.content)
        if input_data.images and not frames:
            parts.append("[User has also provided images]")
        text = "\n".join(parts).strip()

        notes.append(build_turn_guidance(text, is_proactive=proactive))
        # 直播：她知道對面是一群觀眾。"- " 開頭的是她知道的事，引擎只在這場直播的
        # 對話裡寫一次，不是每一輪都提醒（每輪照送，主機不送了引擎才會收回）。
        if metadata.get("stream"):
            notes.append(STREAM_FACT)
        # 她主動說的話已經留在對話裡（remember_remark），不再以一次性的備註帶過去：
        # 那樣她會把引號裡的話照唸一遍。
        notes.append(self._group_note)
        # 問她幾點，小模型有一半的機會不呼叫時間工具而是編一個。這是這一輪的事，
        # 不是「她知道的事」：每輪都不一樣，當成後者會每輪去改上一則備註。
        now = self._now()
        notes.append(
            f"現在時間：{now:%Y-%m-%d}（週{WEEKDAYS[now.weekday()]}）{now:%H:%M}"
        )
        return text, [note.strip() for note in notes if note.strip()]

    async def _reply(
        self, input_data: BatchInput
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        companion = self._companion()
        frames = self._frames(input_data) if companion.sees else ()
        text, notes = self._turn(input_data, frames)
        if not text and not frames:
            logger.warning("No content generated for user message.")
            return
        metadata = input_data.metadata or {}
        # agent 是共用的，「目前這段對話」是最後一個載入歷史的連線設的；
        # 主機有指明這一輪屬於哪一段的話以它為準。
        conversation = metadata.get("history_uid") or self._conversation
        # 主機把上一則回覆整個丟掉、帶著提示再問一次：那一輪沒有人聽到。
        redo = bool(metadata.get("redo"))
        self._hand_over(companion, conversation)

        outputs: asyncio.Queue = asyncio.Queue()
        _OUTPUTS.set(outputs)
        name = uuid4().hex

        proactive = bool(metadata.get("proactive_speak"))
        material = [
            str(item).strip()
            for item in metadata.get("proactive_material") or ()
            if str(item).strip()
        ]

        def ask(companion):
            # 在引擎那一輪裡面做：agent 是共用的，這一輪排隊的時候別的連線可能
            # 正在講話，那時候不能換人設、換工具。
            def before_turn():
                self._bring_up_to_date(
                    companion, take_back=conversation if redo else None
                )

            if proactive:
                # 主動開口講什麼由引擎決定（她的目標、想法、還沒聊完的事），主機
                # 那一大段指示不送，只送素材。說出口的那句主機過濾後才記
                # （remember_remark），所以引擎不先記。
                call = companion.speak_up(
                    conversation,
                    frames=frames,
                    on_text_delta=outputs.put_nowait,
                    # 一整則，不以 "- " 開頭：引擎把 "- " 開頭的備註當成「她知道的事」
                    # 留在對話裡，素材只屬於這一句。
                    notes=[
                        *(
                            ["可以聊的素材：\n" + "\n\n".join(material)]
                            if material
                            else []
                        ),
                        *notes,
                    ],
                    before_turn=before_turn,
                    remember_as=self._remembered,
                    turn_id=name,
                    keep=False,
                    # 上一次主動開口已經問過問題：這次的問句由引擎拿掉，不只是叮嚀。
                    statement_only=bool(metadata.get("proactive_forbid_question")),
                    # 主機自己的規矩（中文，實測出來的）；沒有就用引擎的。
                    instruction=str(metadata.get("proactive_instruction") or "")
                    or None,
                )
            else:
                call = companion.reply(
                    text,
                    conversation_id=conversation,
                    frames=frames,
                    on_text_delta=outputs.put_nowait,
                    skip_memory=bool(metadata.get("skip_memory")),
                    notes=notes,
                    before_turn=before_turn,
                    remember_as=self._remembered,
                    turn_id=name,
                )
            turn = asyncio.ensure_future(call)
            turn.add_done_callback(lambda _: outputs.put_nowait(_DONE))
            return turn

        turn = ask(companion)
        waiting = (asyncio.current_task(), conversation, name)
        self._turns.append(waiting)
        try:
            while True:
                while (output := await outputs.get()) is not _DONE:
                    yield output
                try:
                    await turn
                    return
                except CompanionClosed:
                    # 設定一存，引擎那一側換了一個，而這一輪還在排隊、沒開始。
                    successor = self._companion()
                    if successor is companion:
                        raise
                    companion = successor
                    self._hand_over(companion, conversation)
                    turn = ask(companion)
        except TurnInterrupted:
            return
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            # 被取消的是引擎那一輪（引擎正在關閉），不是主機這一輪。主機沒有取消
            # 自己的話，這裡丟出取消會讓它那一輪收不了尾。
            logger.warning("[engine] the reply was cut short; the engine is closing")
            return
        finally:
            self._turns.remove(waiting)
            self._last_ended = (conversation, name)
            # 主機那一輪還沒結束：她的字已經全出來了，語音還在播。已經結束的
            # 在這裡順手清掉，不然只有打斷時才清。
            self._playing = [
                entry
                for entry in self._playing
                if not entry[0].done() and entry[0] is not waiting[0]
            ] + ([] if name in self._told else [waiting])
            self._told &= {entry[2] for entry in (*self._turns, *self._playing)}
            # 主機打斷的方式是取消等著這個 generator 的 task。引擎那一輪得真的
            # 停下來，之後 handle_interrupt 才記得進去。
            if not turn.done():
                turn.cancel()
                await asyncio.gather(turn, return_exceptions=True)

    @staticmethod
    def _frames(input_data: BatchInput) -> tuple:
        frames = []
        for picture in (input_data.images or [])[:MAX_PICTURES]:
            try:
                image = image_from_host(
                    picture.data, picture.mime_type, max_bytes=MAX_PICTURE_BYTES
                )
            except HostBridgeError as exc:
                # 一張讀不了的圖不值得賠上整輪對話。
                logger.warning(f"[engine] picture skipped ({exc})")
                continue
            source = _PICTURE_SOURCES.get(picture.source.value, "upload")
            frames.append(VisionFrame(image=image, source_type=source))
        return tuple(frames)

    def _bring_up_to_date(self, companion, *, take_back=None) -> None:
        if take_back is not None:
            # 在引擎那一輪裡面做：這時沒有別的連線在講話，最新的那一則才拿得掉。
            companion.take_back(take_back)
        if companion.character.description != self._system:
            companion.character = replace(companion.character, description=self._system)
        if _TOOLS_REGISTERED_BY.get(companion) == id(self):
            return
        for registered in list(companion.tools):
            companion.tools.unregister(registered.definition.name)
        for definition in self._tools:
            companion.tools.register(definition, self._tool_handler(definition.name))
        _TOOLS_REGISTERED_BY[companion] = id(self)

    # --- 工具 -----------------------------------------------------------------

    @staticmethod
    def _tool_definitions(tool_manager) -> List[ToolDefinition]:
        if tool_manager is None:
            return []
        definitions = []
        for tool in tool_manager.get_formatted_tools("OpenAI"):
            function = tool.get("function") or {}
            try:
                definitions.append(
                    ToolDefinition(
                        name=function.get("name") or "",
                        description=function.get("description")
                        or "No description available.",
                        parameters=function.get("parameters")
                        or {"type": "object", "properties": {}},
                    )
                )
            except ValueError as exc:
                logger.warning(f"[engine] tool skipped ({exc}): {function}")
        return definitions

    def _tool_handler(self, name: str):
        async def call(**arguments) -> str:
            if self._tool_executor is None:
                return "Error: no tool executor is configured."
            request = ToolCallObject(
                id=f"call_{uuid4().hex[:24]}",
                function=ToolCallFunctionObject(
                    name=name, arguments=json.dumps(arguments, ensure_ascii=False)
                ),
            )
            results: list = []
            async for update in self._tool_executor.execute_tools([request], "OpenAI"):
                if update.get("type") == "final_tool_results":
                    results = update.get("results") or []
                elif (outputs := _OUTPUTS.get()) is not None:
                    outputs.put_nowait(update)
            return str(results[0].get("content", "")) if results else ""

        return call
