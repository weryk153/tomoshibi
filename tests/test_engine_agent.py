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


def test_what_she_said_on_her_own_stays_in_the_conversation(tmp_path):
    """主動開口的那一輪帶著一大段指示，不進對話；但她說出口的那句要留下，而且是她
    自己說的話。之前只在使用者回應時以一次性的備註帶過去：她不記得自己主動說過
    什麼（一直講同一件事），使用者回應時還把那句照唸一遍。"""

    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        await say(current, "我在做時光機", history_uid="h1")
        await say(
            current,
            "（主動開口的指示）",
            history_uid="h1",
            proactive_speak=True,
            skip_memory=True,
        )
        await current.remember_remark("h1", "別讓 Amadeus 過熱了。")
        await say(
            current,
            "好 確認下",
            history_uid="h1",
            previous_proactive_response="別讓 Amadeus 過熱了。",
        )
        return llm.calls[-1], llm.context()

    sent, context = asyncio.run(scenario())
    lines = [(message.role, message.content) for message in sent]
    assert ("assistant", "別讓 Amadeus 過熱了。") in lines
    assert "別讓 Amadeus 過熱了。" not in context
    assert not any("主動開口的指示" in content for _, content in lines)


def test_after_asking_on_her_own_her_next_remark_asks_nothing(tmp_path):
    """主機算出上一次主動開口已經問過問題時，這次的問句由引擎拿掉。以前只是在
    素材裡叮嚀一句，小模型照樣問。"""

    async def remark(**metadata):
        llm = EngineLLM("你在做什麼？")
        current = agent(companion(tmp_path / str(len(metadata)), llm))
        outputs = await say(
            current,
            "（主動開口的指示）",
            history_uid="h1",
            proactive_speak=True,
            skip_memory=True,
            **metadata,
        )
        return spoken(outputs)

    assert asyncio.run(remark()) == "你在做什麼？"
    assert asyncio.run(remark(proactive_forbid_question=True)) == ""


def test_the_conversation_keeps_what_she_said_on_her_own():
    import inspect

    from src.open_llm_vtuber.conversations import single_conversation

    src = inspect.getsource(single_conversation.process_single_conversation)

    assert 'getattr(context.agent_engine, "remember_remark", None)' in src


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


def test_interrupted_the_way_the_host_really_does_it(tmp_path):
    """conversation_handler 取消 task 之後馬上呼叫 handle_interrupt，不等它停下來。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。", gate=asyncio.Event())
        engine = companion(tmp_path, llm)
        current = agent(engine)
        turn = asyncio.ensure_future(say(current, "你好"))
        await llm.started.wait()
        turn.cancel()
        current.handle_interrupt("嗯")
        with pytest.raises(asyncio.CancelledError):
            await turn
        llm.gate.set()
        outputs = await say(current, "抱歉，你繼續")
        return llm.said_by_both()[:2], spoken(outputs)

    history, after = asyncio.run(scenario())

    assert history == ["你好", "嗯 [Interrupted by user]"]
    assert after == "嗯，我知道了。"


def test_interrupting_the_one_who_waits_does_not_cut_off_the_one_who_talks(tmp_path):
    """agent 是共用的：A 的回覆還在生成，B 排在後面等。B 被打斷不能切掉 A。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。", gate=asyncio.Event())
        engine = companion(tmp_path, llm)
        current = agent(engine)
        first = asyncio.ensure_future(say(current, "我是第一個", history_uid="h1"))
        await llm.started.wait()
        second = asyncio.ensure_future(say(current, "我是第二個", history_uid="h2"))
        for _ in range(20):
            await asyncio.sleep(0)
        second.cancel()
        current.handle_interrupt("")
        llm.gate.set()
        outputs = await first
        with pytest.raises(asyncio.CancelledError):
            await second
        await say(current, "繼續", history_uid="h1")
        return spoken(outputs), llm.said_by_both()

    said, conversation = asyncio.run(scenario())

    assert said == "嗯，我知道了。"
    assert conversation == ["我是第一個", "嗯，我知道了。", "繼續"]


def test_interrupting_what_is_being_played_does_not_cut_off_another_connection(
    tmp_path,
):
    """A 的回覆已經生成完、正在播；B 的回覆還在生成。A 那邊打斷的時候主機不會
    取消任何 task（A 的已經結束了），只呼叫 handle_interrupt。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。", gate=asyncio.Event())
        llm.gate.set()
        engine = companion(tmp_path, llm)
        current = agent(engine)
        await say(current, "我是A", history_uid="h1")
        llm.gate.clear()
        llm.started.clear()
        talking = asyncio.ensure_future(say(current, "我是B", history_uid="h2"))
        await llm.started.wait()
        current.handle_interrupt("嗯")
        llm.gate.set()
        outputs = await talking
        return spoken(outputs), [m.content for m in engine.runtime.history]

    said, conversation = asyncio.run(scenario())

    assert said == "嗯，我知道了。"
    assert conversation == ["我是B", "嗯，我知道了。"]


def test_a_finished_turn_is_let_go_once_its_host_task_ends(tmp_path):
    """播放中的回合要記著，好讓打斷找得到；主機那一輪結束後就不用了。"""

    async def scenario():
        current = agent(companion(tmp_path, EngineLLM()))
        for number in range(5):
            await say(current, f"第 {number} 句", history_uid="h1")
        for _ in range(5):
            await asyncio.sleep(0)
        return len(current._playing)

    assert asyncio.run(scenario()) <= 1


def test_an_interruption_is_delivered_once(tmp_path):
    """A 被打斷後，它那一輪的 task 還在收尾。這時 B 打斷不能再落到 A 頭上。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。", gate=asyncio.Event())
        llm.gate.set()
        engine = companion(tmp_path, llm)
        current = agent(engine)
        playing = asyncio.Event()

        async def a_turn():
            await say(current, "我是A", history_uid="h1")
            await playing.wait()

        a = asyncio.ensure_future(a_turn())
        for _ in range(50):
            await asyncio.sleep(0)
        a.cancel()
        current.handle_interrupt("嗯")
        llm.gate.clear()
        llm.started.clear()
        b = asyncio.ensure_future(say(current, "我是B", history_uid="h2"))
        await llm.started.wait()
        b.cancel()
        current.handle_interrupt("我")
        with pytest.raises(asyncio.CancelledError):
            await a
        with pytest.raises(asyncio.CancelledError):
            await b
        llm.gate.set()
        await say(current, "繼續", history_uid="h2")
        return llm.said_by_both()

    assert asyncio.run(scenario()) == ["我是B", "我 [Interrupted by user]", "繼續"]


def test_a_turn_told_of_its_interruption_is_not_told_again_while_it_stops(tmp_path):
    """真的 HTTP 串流關掉要一點時間。A 被打斷、送過一次之後，它的 task 還在等
    引擎停下來；這期間 B 打斷，不能又落到 A 頭上——A 聽到的會被 B 的覆寫。"""

    class SlowToStop(EngineLLM):
        async def stream_generate(self, messages, *, tools=None):
            self.calls.append(list(messages))
            yield LLMStreamChunk(text=self.reply[:1])
            self.started.set()
            try:
                await self.gate.wait()
            except asyncio.CancelledError:
                for _ in range(20):
                    await asyncio.sleep(0)
                raise
            yield LLMStreamChunk(text=self.reply[1:])
            yield LLMStreamChunk(
                final=True, response=LLMResponse(text=self.reply, model="fake")
            )

    async def scenario():
        llm = SlowToStop("嗯，我知道了。", gate=asyncio.Event())
        engine = companion(tmp_path, llm)
        current = agent(engine)
        a = asyncio.ensure_future(say(current, "我是A", history_uid="h1"))
        await llm.started.wait()
        b = asyncio.ensure_future(say(current, "我是B", history_uid="h2"))
        for _ in range(5):
            await asyncio.sleep(0)
        a.cancel()
        current.handle_interrupt("嗯")
        for _ in range(5):
            await asyncio.sleep(0)
        assert not a.done()
        b.cancel()
        current.handle_interrupt("")
        with pytest.raises(asyncio.CancelledError):
            await a
        with pytest.raises(asyncio.CancelledError):
            await b
        llm.gate.set()
        await say(current, "繼續", history_uid="h1")
        return llm.said_by_both()

    assert asyncio.run(scenario()) == ["我是A", "嗯 [Interrupted by user]", "繼續"]


def test_the_same_conversation_in_two_windows(tmp_path):
    """A 在生成、B 排在後面，兩個都在同一段對話。主機取消 A 並回報聽到哪裡：
    被打斷的是 A，B 照常回答。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。", gate=asyncio.Event())
        engine = companion(tmp_path, llm)
        current = agent(engine)
        first = asyncio.ensure_future(say(current, "我是A", history_uid="h1"))
        await llm.started.wait()
        second = asyncio.ensure_future(say(current, "我是B", history_uid="h1"))
        for _ in range(20):
            await asyncio.sleep(0)
        first.cancel()
        current.handle_interrupt("嗯")
        llm.gate.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        outputs = await second
        return spoken(outputs), [m.content for m in engine.runtime.history]

    said, conversation = asyncio.run(scenario())

    assert said == "嗯，我知道了。"
    assert conversation == [
        "我是A",
        "嗯 [Interrupted by user]",
        "我是B",
        "嗯，我知道了。",
    ]


def test_a_turn_that_waited_while_she_was_replaced_is_given_to_the_new_one(tmp_path):
    """設定一存，引擎那一側換了一個。排隊等舊的那一輪還沒開始，交給新的。"""

    async def scenario():
        slow = EngineLLM("舊的。", gate=asyncio.Event())
        old = companion(tmp_path / "old", slow)
        live = {"now": old}
        current = agent(lambda: live["now"])
        talking = asyncio.ensure_future(say(current, "我是A", history_uid="h1"))
        await slow.started.wait()
        waiting = asyncio.ensure_future(say(current, "我是B", history_uid="h2"))
        for _ in range(20):
            await asyncio.sleep(0)
        live["now"] = companion(tmp_path / "new", EngineLLM("新的。"))
        old.retire()
        slow.gate.set()
        return spoken(await talking), spoken(await waiting)

    assert asyncio.run(scenario()) == ("舊的。", "新的。")


def test_each_turn_belongs_to_the_conversation_the_host_names(tmp_path):
    """agent 是共用的：兩個連線可以在不同的對話裡輪流講。"""

    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        await say(current, "我在第一段", history_uid="h1")
        await say(current, "我在第二段", history_uid="h2")
        await say(current, "回到第一段", history_uid="h1")
        return llm.said_by_both()

    assert asyncio.run(scenario()) == ["我在第一段", "嗯，我知道了。", "回到第一段"]


def test_two_connections_with_different_personas_do_not_trip_over_each_other(tmp_path):
    """設定一存就有新的 agent，舊連線還拿著舊的；兩邊的人設可以不一樣。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。", gate=asyncio.Event())
        engine = companion(tmp_path, llm)
        old, new = agent(engine), agent(engine)
        new.set_system("你是鋼琴家。")
        first = asyncio.ensure_future(say(old, "我是第一個", history_uid="h1"))
        await llm.started.wait()
        second = asyncio.ensure_future(say(new, "我是第二個", history_uid="h2"))
        for _ in range(20):
            await asyncio.sleep(0)
        llm.gate.set()
        results = await asyncio.gather(first, second)
        return [spoken(r) for r in results], llm.sent(0)[0], llm.sent(1)[0]

    said, first_system, second_system = asyncio.run(scenario())

    assert said == ["嗯，我知道了。", "嗯，我知道了。"]
    assert "你是紅莉栖。" in first_system
    assert "你是鋼琴家。" in second_system


def test_she_remembers_her_own_expressions(tmp_path):
    """畫面上的字會把 [joy] 這類標籤拿掉；她記得的那一份要留著，不然幾輪之後
    她讀到的自己從來不做表情，就真的不做了。"""

    async def scenario():
        llm = EngineLLM("[joy]太好了！你呢？")
        engine = companion(tmp_path, llm)
        current = agent(engine)
        outputs = await say(current, "我考上了")
        return spoken(outputs), engine.runtime.history[-1].content

    shown, remembered = asyncio.run(scenario())

    assert shown == "太好了！你呢？"
    assert remembered == "[joy]太好了！你呢？"


def test_she_remembers_what_she_said_in_the_players_script(tmp_path):
    """模型某一輪漂到簡體時，畫面與紀錄會被轉成繁體；她記得的那一份沒轉的話，
    下一輪她讀到自己講簡體，就更容易繼續漂。"""

    async def scenario():
        llm = EngineLLM("这样啊，我知道了。")
        engine = companion(tmp_path, llm)
        current = agent(engine, player_language="繁體中文")
        await say(current, "我考上了")
        return engine.runtime.history[-1].content

    assert asyncio.run(scenario()) == "這樣啊，我知道了。"


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


def test_two_connections_talking_at_once_each_get_their_own_tool_progress(tmp_path):
    """agent 是所有連線共用的。引擎一次只跑一輪，但第二個連線在排隊的時候，
    第一個連線的工具進度不能跑到它那裡去。"""

    async def scenario():
        current = agent(
            companion(tmp_path, ToolUsingLLM()),
            use_mcpp=True,
            tool_manager=FakeToolManager(),
            tool_executor=FakeToolExecutor(),
        )
        return await asyncio.gather(
            say(current, "現在幾點", history_uid="h1"),
            say(current, "現在幾點", history_uid="h2"),
        )

    for outputs in asyncio.run(scenario()):
        assert [o["status"] for o in outputs if isinstance(o, dict)] == [
            "running",
            "completed",
        ]
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


def test_a_reply_the_host_threw_away_is_not_kept_when_it_asks_again(tmp_path):
    """整則回覆被跨輪護欄丟掉時，主機帶著提示再問一次。那一輪沒有人聽到：
    留著的話，同一句話會在對話裡出現兩次，第一次配著沒人聽過的回覆。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。")
        engine = companion(tmp_path, llm)
        current = agent(engine)
        await say(current, "你好", history_uid="h1")
        await say(current, "再說一次", history_uid="h1", spoken_text="再說一次")
        await say(
            current,
            "再說一次\n\n（你最近說過這些，換個說法）",
            history_uid="h1",
            spoken_text="再說一次",
            redo=True,
        )
        await say(current, "繼續", history_uid="h1")
        return llm.said_by_both()

    assert asyncio.run(scenario()) == [
        "你好",
        "嗯，我知道了。",
        "再說一次",
        "嗯，我知道了。",
        "繼續",
    ]


def test_the_retry_after_the_guard_tells_the_agent_to_redo():
    import inspect

    from src.open_llm_vtuber.conversations import single_conversation

    src = inspect.getsource(single_conversation.process_single_conversation)

    assert 'metadata={**agent_metadata, "redo": True},' in src


def test_she_speaks_up_through_the_engine_with_the_hosts_material(tmp_path):
    """主動開口改由引擎決定講什麼：主機那一大段指示不送，只送素材（話題、新聞、
    查到的資料）。說出口的那句由主機過濾後再記（remember_remark），引擎不先記。"""

    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        await say(current, "我在做時光機", history_uid="h1")
        await say(
            current,
            "（主機的一大段主動開口指示）",
            history_uid="h1",
            proactive_speak=True,
            skip_memory=True,
            proactive_material=["- 天文"],
            proactive_instruction="對方已經有一段時間沒講話了。請你自然地開口。",
        )
        prompt = llm.calls[-1]
        await say(current, "嗯", history_uid="h1")
        return prompt, llm.calls[-1]

    prompt, afterwards = asyncio.run(scenario())
    everything = "\n".join(message.content for message in prompt)
    assert "主機的一大段主動開口指示" not in everything
    assert "請你自然地開口" in prompt[-1].content
    assert "For the next reply only: 可以聊的素材：\n- 天文" in everything
    later = "\n".join(message.content for message in afterwards)
    assert "請你自然地開口" not in later
    assert "- 天文" not in later
