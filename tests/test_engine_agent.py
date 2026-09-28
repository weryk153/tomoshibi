"""character_engine_agent：整段對話由 AI Character Engine 驅動，這裡只是轉接。

測的是轉接層自己的責任：把主機的輸入翻成引擎的一輪、把引擎吐出來的字接回主機
的輸出管線、以及主機那些「一個 agent 大家共用、隨時被重建」的習慣。引擎本身的
行為（記憶、狀態、背景認知）在引擎那邊測。
"""

import asyncio
import json

import pytest

pytest.importorskip("ai_character_engine")

from ai_character_engine import CharacterProfile  # noqa: E402
from ai_character_engine.companion import (  # noqa: E402
    CharacterCompanion,
    CompanionSettings,
)
from ai_character_engine.llm.models import LLMResponse, LLMStreamChunk  # noqa: E402
from ai_character_engine.tools.models import ToolCall  # noqa: E402

import src.open_llm_vtuber.agent.agents.character_engine_agent as agent_module  # noqa: E402
from src.open_llm_vtuber.agent.agents.character_engine_agent import (  # noqa: E402
    CharacterEngineAgent,
)
from src.open_llm_vtuber.agent.input_types import (  # noqa: E402
    BatchInput,
    ImageData,
    ImageSource,
    TextData,
    TextSource,
)
from src.open_llm_vtuber.agent.output_types import SentenceOutput  # noqa: E402
from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig  # noqa: E402

CONTEXT_MARK = "Character context for this turn."


class EngineLLM:
    """引擎那一側的模型。一次回一句；gate 沒開的時候停在第一段之後。"""

    def __init__(self, reply="嗯，我知道了。", *, gate=None):
        self.reply = reply
        self.gate = gate
        self.calls = []
        self.started = asyncio.Event()

    async def generate(self, messages, *, tools=None):
        self.calls.append(list(messages))
        return LLMResponse(text=self.reply, model="fake")

    async def stream_generate(self, messages, *, tools=None):
        self.calls.append(list(messages))
        yield LLMStreamChunk(text=self.reply[:1])
        self.started.set()
        if self.gate is not None:
            await self.gate.wait()
        yield LLMStreamChunk(text=self.reply[1:])
        yield LLMStreamChunk(
            final=True, response=LLMResponse(text=self.reply, model="fake")
        )

    def sent(self, turn=-1):
        return [message.content for message in self.calls[turn]]

    def said_by_both(self, turn=-1):
        return [
            content for content in self.sent(turn)[1:] if CONTEXT_MARK not in content
        ]

    def context(self, turn=-1):
        return "\n".join(c for c in self.sent(turn) if CONTEXT_MARK in c)


class FakeLive2D:
    @staticmethod
    def extract_emotion(_text):
        return None

    @staticmethod
    def extract_emotion_keys(_text):
        return []

    @staticmethod
    def extract_motions(_text):
        return None


def tts_config():
    return TTSPreprocessorConfig(
        remove_special_char=True,
        translator_config={"translate_audio": False, "translate_provider": "deeplx"},
    )


def companion(tmp_path, llm):
    return CharacterCompanion(
        character=CharacterProfile(
            id="kurisu", name="紅莉栖", description="你是紅莉栖。"
        ),
        llm=llm,
        background_llm={},
        storage_dir=tmp_path / "engine",
        settings=CompanionSettings(),
    )


def agent(source, **more):
    return CharacterEngineAgent(
        companion=source,
        system="你是紅莉栖。",
        live2d_model=FakeLive2D(),
        tts_preprocessor_config=tts_config(),
        **more,
    )


def batch(text, **metadata):
    return BatchInput(
        texts=[TextData(source=TextSource.INPUT, content=text)],
        metadata=metadata or None,
    )


async def say(current, text, **metadata):
    return [output async for output in current.chat(batch(text, **metadata))]


def spoken(outputs):
    return "".join(
        output.display_text.text
        for output in outputs
        if isinstance(output, SentenceOutput)
    )


# --- 一輪對話 ---------------------------------------------------------------------


def test_her_reply_comes_out_through_the_hosts_sentence_pipeline(tmp_path):
    async def scenario():
        current = agent(companion(tmp_path, EngineLLM("嗯，我知道了。你呢？")))
        return await say(current, "你好")

    outputs = asyncio.run(scenario())

    assert all(isinstance(output, SentenceOutput) for output in outputs)
    assert spoken(outputs) == "嗯，我知道了。你呢？"


def test_the_engine_keeps_the_conversation(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        await say(current, "我叫晨星")
        await say(current, "我叫什麼")
        return llm.said_by_both()

    assert asyncio.run(scenario()) == ["我叫晨星", "嗯，我知道了。", "我叫什麼"]


def test_what_the_host_added_for_the_model_is_not_kept_as_the_users_words(tmp_path):
    """主機會在使用者的話後面接「你最近說過這些」之類的提示。那是給這一輪的模型
    看的，留在對話裡的話，下一輪她會讀到使用者「說」了一段提示。"""

    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        await say(current, "你好\n\n［你最近說過：早安］", spoken_text="你好")
        first = llm.context(), llm.said_by_both()
        await say(current, "再見")
        return first, llm.sent()

    (context, said), afterwards = asyncio.run(scenario())

    assert said == ["你好"]
    assert "［你最近說過：早安］" in context
    # 它留在當時那則備註裡（下一輪的提示才會是這一輪的延伸，推論端的快取才用得上），
    # 但不會變成使用者說過的話，也不會再講一次。
    assert [CONTEXT_MARK in c for c in afterwards if "你最近說過" in c] == [True]


def test_a_refreshed_persona_reaches_the_next_reply(tmp_path):
    """主機每輪對話前會重組系統提示（記憶刷新、切換人設）。"""

    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        await say(current, "你好")
        current.set_system("你是鋼琴家。")
        await say(current, "你是做什麼的")
        return llm.sent(0)[0], llm.sent(1)[0]

    before, after = asyncio.run(scenario())

    assert "你是紅莉栖。" in before
    assert "你是鋼琴家。" in after
    assert "你是紅莉栖。" not in after


def test_proactive_speech_leaves_no_trace_in_the_conversation(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        await say(current, "你好")
        await say(current, "（主動開口的指示）", proactive_speak=True, skip_memory=True)
        await say(current, "還在嗎")
        return llm.said_by_both()

    assert asyncio.run(scenario()) == ["你好", "嗯，我知道了。", "還在嗎"]


def test_the_remark_she_made_on_her_own_is_supplied_once(tmp_path):
    """主動發話不進對話；使用者回應它的那一輪，主機把那句話帶過來。"""

    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        await say(current, "真的嗎", previous_proactive_response="外面下雨了。")
        first = llm.context()
        await say(current, "好吧")
        return first, llm.sent()

    context, afterwards = asyncio.run(scenario())

    assert "外面下雨了。" in context
    assert [CONTEXT_MARK in c for c in afterwards if "外面下雨了。" in c] == [True]


# --- 影像 -------------------------------------------------------------------------

PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB"
    "9Y9Z0iUAAAAASUVORK5CYII="
)


def seeing(tmp_path, llm):
    from ai_character_engine.vision import VisionPipeline
    from ai_character_engine.vision.models import VisionAnalysis
    from ai_character_engine.vision.providers import CallableVisionProvider
    from ai_character_engine.vision.sampling import FrameGate

    async def look(image, prompt):
        return VisionAnalysis(text="桌上有一杯烏龍茶。", provider="fake")

    return CharacterCompanion(
        character=CharacterProfile(
            id="kurisu", name="紅莉栖", description="你是紅莉栖。"
        ),
        llm=llm,
        background_llm={},
        storage_dir=tmp_path / "engine",
        vision=VisionPipeline(
            provider=CallableVisionProvider(look),
            frame_gate=FrameGate(min_interval_seconds=0, deduplicate=False),
        ),
    )


def with_picture(text, source=ImageSource.CAMERA):
    return BatchInput(
        texts=[TextData(source=TextSource.INPUT, content=text)],
        images=[ImageData(source=source, data=PNG, mime_type="image/png")],
    )


def test_a_picture_from_the_host_is_shown_to_her(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(seeing(tmp_path, llm))
        first = [o async for o in current.chat(with_picture("你看這個"))]
        # 鏡頭每一輪都會送畫面來，常常是同一張。
        second = [o async for o in current.chat(with_picture("還是這個"))]
        return spoken(first), spoken(second), llm.sent(0)[-1], llm.said_by_both()

    first, second, newest, conversation = asyncio.run(scenario())

    assert (first, second) == ("嗯，我知道了。", "嗯，我知道了。")
    assert "你看這個" in newest
    assert "桌上有一杯烏龍茶。" in newest
    assert "(camera)" in newest
    assert conversation[0] == "你看這個"


def test_without_eyes_she_is_told_a_picture_came_with_it(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        outputs = [o async for o in current.chat(with_picture("你看這個"))]
        return spoken(outputs), llm.sent()[-1]

    said, newest = asyncio.run(scenario())

    assert said == "嗯，我知道了。"
    assert newest == "你看這個\n[User has also provided images]"


def test_a_picture_that_cannot_be_read_does_not_cost_the_turn(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(seeing(tmp_path, llm))
        broken = BatchInput(
            texts=[TextData(source=TextSource.INPUT, content="你看這個")],
            images=[
                ImageData(
                    source=ImageSource.UPLOAD,
                    data="https://example.com/a.png",
                    mime_type="image/png",
                )
            ],
        )
        return spoken([o async for o in current.chat(broken)])

    assert asyncio.run(scenario()) == "嗯，我知道了。"


# --- 對話的載入與切換 -------------------------------------------------------------


def test_a_loaded_conversation_is_continued_and_owns_its_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "get_history",
        lambda conf_uid, history_uid: [
            {"role": "system", "content": "不是對話"},
            {"role": "human", "content": "我們講到哪"},
            {"role": "ai", "content": "講到時光機。"},
            {"role": "ai", "content": "（她自己又補了一句）"},
        ],
    )

    async def scenario():
        llm = EngineLLM()
        engine = companion(tmp_path, llm)
        current = agent(engine)
        current.set_memory_from_history("kurisu", "h1")
        await say(current, "繼續")
        return llm.said_by_both(), engine.runtime.memory_scope_id

    said, scope = asyncio.run(scenario())

    assert said == ["我們講到哪", "講到時光機。", "繼續"]
    assert scope == "kurisu:h1"


def test_a_conversation_the_engine_has_not_seen_is_taken_from_the_hosts_record(
    tmp_path, monkeypatch
):
    """設定一存，引擎那一側可能換了一個，而 agent 不會再被告知一次目前是哪段對話。
    主機在每一輪開頭就把使用者的話寫進紀錄了，所以最後那句不能再算一次。"""
    asked = []

    def history(conf_uid, history_uid):
        asked.append((conf_uid, history_uid))
        return [
            {"role": "human", "content": "我們講到哪"},
            {"role": "ai", "content": "講到時光機。"},
            {"role": "human", "content": "繼續"},
        ]

    monkeypatch.setattr(agent_module, "get_history", history)

    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm), conf_uid="kurisu")
        await say(current, "繼續", history_uid="h1")
        first = llm.said_by_both()
        await say(current, "然後呢", history_uid="h1")
        return first, llm.said_by_both()

    first, second = asyncio.run(scenario())

    assert first == ["我們講到哪", "講到時光機。", "繼續"]
    assert second == [*first, "嗯，我知道了。", "然後呢"]
    assert asked == [("kurisu", "h1")]


# --- 打斷 -------------------------------------------------------------------------


def test_interrupted_she_remembers_only_what_was_heard(tmp_path):
    """主機打斷的方式是取消正在等回覆的那個 task，之後才從前端得知聽到哪裡。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。", gate=asyncio.Event())
        engine = companion(tmp_path, llm)
        current = agent(engine)
        turn = asyncio.ensure_future(say(current, "你好"))
        await llm.started.wait()
        turn.cancel()
        with pytest.raises(asyncio.CancelledError):
            await turn
        current.handle_interrupt("嗯")
        history = [message.content for message in engine.runtime.history]
        llm.gate.set()
        outputs = await say(current, "抱歉，你繼續")
        return history, engine.busy, spoken(outputs)

    history, busy, after = asyncio.run(scenario())

    assert history == ["你好", "嗯 [Interrupted by user]"]
    assert busy is False
    assert after == "嗯，我知道了。"


def test_what_was_displayed_replaces_what_was_generated(tmp_path):
    """主機會丟掉重複的句子、做繁簡正規化。她記得的要是使用者看到的那一版。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。有什麼可以幫你的嗎？")
        engine = companion(tmp_path, llm)
        current = agent(engine)
        await say(current, "你好", history_uid="h1")
        current.observe_turn("kurisu", "h1", "你好", "嗯，我知道了。")
        return [message.content for message in engine.runtime.history]

    assert asyncio.run(scenario()) == ["你好", "嗯，我知道了。"]


def test_each_turn_belongs_to_the_conversation_the_host_names(tmp_path):
    """agent 是共用的：兩個連線可以在不同的對話裡輪流講。"""

    async def scenario():
        llm = EngineLLM()
        engine = companion(tmp_path, llm)
        current = agent(engine)
        await say(current, "我在第一段", history_uid="h1")
        await say(current, "我在第二段", history_uid="h2")
        current.observe_turn("kurisu", "h1", "我在第一段", "不是剛講完的那段")
        await say(current, "回到第一段", history_uid="h1")
        return llm.said_by_both()

    assert asyncio.run(scenario()) == ["我在第一段", "嗯，我知道了。", "回到第一段"]


# --- 工具 -------------------------------------------------------------------------


class ToolUsingLLM(EngineLLM):
    async def stream_generate(self, messages, *, tools=None):
        self.calls.append(list(messages))
        self.tools = [tool.name for tool in tools or ()]
        if messages[-1].role == "tool":
            yield LLMStreamChunk(text="現在十二點半。")
            yield LLMStreamChunk(
                final=True, response=LLMResponse(text="現在十二點半。", model="fake")
            )
            return
        yield LLMStreamChunk(
            final=True,
            response=LLMResponse(
                text="",
                tool_calls=(ToolCall("call-1", "clock", {"zone": "Asia/Taipei"}),),
                model="fake",
            ),
        )


class FakeToolManager:
    def get_formatted_tools(self, mode):
        assert mode == "OpenAI"
        return [
            {
                "type": "function",
                "function": {
                    "name": "clock",
                    "description": "Read the clock",
                    "parameters": {
                        "type": "object",
                        "properties": {"zone": {"type": "string"}},
                    },
                },
            }
        ]


class FakeToolExecutor:
    def __init__(self):
        self.calls = []

    async def execute_tools(self, tool_calls, caller_mode):
        for call in tool_calls:
            arguments = json.loads(call.function.arguments)
            self.calls.append((call.function.name, arguments, caller_mode))
            yield {
                "type": "tool_call_status",
                "tool_id": call.id,
                "tool_name": call.function.name,
                "status": "running",
            }
            yield {
                "type": "tool_call_status",
                "tool_id": call.id,
                "tool_name": call.function.name,
                "status": "completed",
                "content": "12:30",
            }
        yield {
            "type": "final_tool_results",
            "results": [
                {"role": "tool", "tool_call_id": tool_calls[0].id, "content": "12:30"}
            ],
        }


def test_the_hosts_tools_run_and_report_their_progress(tmp_path):
    async def scenario():
        llm = ToolUsingLLM()
        executor = FakeToolExecutor()
        current = agent(
            companion(tmp_path, llm),
            use_mcpp=True,
            tool_manager=FakeToolManager(),
            tool_executor=executor,
        )
        outputs = await say(current, "現在幾點")
        return outputs, executor.calls, llm.tools, llm.sent()[-1]

    outputs, calls, offered, tool_result = asyncio.run(scenario())

    assert offered == ["clock"]
    assert calls == [("clock", {"zone": "Asia/Taipei"}, "OpenAI")]
    assert [o["status"] for o in outputs if isinstance(o, dict)] == [
        "running",
        "completed",
    ]
    assert tool_result == "12:30"
    assert spoken(outputs) == "現在十二點半。"


def test_a_rebuilt_agent_brings_its_own_tools(tmp_path):
    """每次儲存設定都會重建 agent 與它的工具執行器，而引擎那一側是同一個。"""

    async def scenario():
        llm = ToolUsingLLM()
        engine = companion(tmp_path, llm)
        old, new = FakeToolExecutor(), FakeToolExecutor()
        first = agent(
            engine, use_mcpp=True, tool_manager=FakeToolManager(), tool_executor=old
        )
        await say(first, "現在幾點")
        second = agent(
            engine, use_mcpp=True, tool_manager=FakeToolManager(), tool_executor=new
        )
        await say(second, "現在幾點")
        without = agent(engine)
        await say(without, "現在幾點")
        return len(old.calls), len(new.calls), llm.tools

    assert asyncio.run(scenario()) == (1, 1, [])


# --- 一個 agent 大家共用 ----------------------------------------------------------


def test_one_connection_closing_does_not_end_her_for_the_next(tmp_path):
    """agent 是所有連線共用的，而每個連線結束時都會呼叫 close()。"""

    async def scenario():
        engine = companion(tmp_path, EngineLLM())
        current = agent(engine)
        await say(current, "你好")
        await current.close()
        outputs = await say(current, "還在嗎")
        return spoken(outputs), (tmp_path / "engine" / "state.json").is_file()

    assert asyncio.run(scenario()) == ("嗯，我知道了。", True)


def test_the_companion_is_looked_up_each_turn_so_a_replacement_takes_over(tmp_path):
    async def scenario():
        first, second = EngineLLM("第一個。"), EngineLLM("第二個。")
        live = {"now": companion(tmp_path / "a", first)}
        current = agent(lambda: live["now"])
        one = await say(current, "你好")
        live["now"] = companion(tmp_path / "b", second)
        two = await say(current, "你好")
        return spoken(one), spoken(two)

    assert asyncio.run(scenario()) == ("第一個。", "第二個。")


def test_recent_lines_are_available_to_anchor_proactive_speech(tmp_path):
    async def scenario():
        current = agent(companion(tmp_path, EngineLLM()))
        await say(current, "你好")
        return current.get_recent_context_for_proactive()

    assert asyncio.run(scenario()) == "使用者：你好\n角色：嗯，我知道了。"
