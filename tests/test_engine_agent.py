"""character_engine_agent：前景照舊（繼承 BasicMemoryAgent），引擎負責對話之後的認知。

這裡用假的認知工作階段，所以不需要裝引擎——agent 本身不匯入引擎，這一點也是
要釘住的行為：選了別的 agent 的人不該因為沒裝引擎而受影響。
"""

import asyncio
import sys

import pytest

import src.open_llm_vtuber.agent.agents.basic_memory_agent as basic_memory_module
from src.open_llm_vtuber.agent.agent_factory import AgentFactory
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from src.open_llm_vtuber.agent.agents.character_engine_agent import CharacterEngineAgent
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from src.open_llm_vtuber.character_engine.prompt_block import CharacterSnapshot
from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig


class RecordingLLM:
    def __init__(self):
        self.systems = []
        self.conversations = []

    async def chat_completion(self, messages, system=None, tools=None):
        self.systems.append(system)
        self.conversations.append(
            [
                (
                    message["role"],
                    message["content"]
                    if isinstance(message["content"], str)
                    else "".join(
                        part.get("text", "")
                        for part in message["content"]
                        if part.get("type") == "text"
                    ),
                )
                for message in messages
            ]
        )
        yield "嗯，我知道了。"

    def last_user_line(self, turn=-1):
        return self.conversations[turn][-1][1]


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


class FakeSession:
    def __init__(self, snapshot=None, *, fail=False):
        self.current = snapshot or neutral()
        self.fail = fail
        self.bound = []
        self.turns = []
        self.closed = False
        self.flushed = 0
        self.talking = []
        self.conversations = []

    def snapshot(self):
        if self.fail:
            raise RuntimeError("engine state unreadable")
        return self.current

    def bind_conversation(self, history_uid, recent):
        self.bound.append((history_uid, list(recent)))

    async def observe_turn(self, user_text, reply, *, history_uid=None):
        if self.fail:
            raise RuntimeError("engine is down")
        self.turns.append((user_text, reply))
        self.conversations.append(history_uid)

    def flush(self):
        self.flushed += 1

    def foreground_started(self):
        self.talking.append("started")

    def foreground_finished(self):
        self.talking.append("finished")

    async def close(self):
        self.closed = True


def neutral(**overrides):
    base = {
        "emotion": "neutral",
        "trust": 50.0,
        "favorability": 50.0,
        "relationship_stage": "stranger",
    }
    base.update(overrides)
    return CharacterSnapshot(**base)


def tts_config():
    return TTSPreprocessorConfig(
        remove_special_char=True,
        translator_config={"translate_audio": False, "translate_provider": "deeplx"},
    )


def agent(session, llm=None, system="你是紅莉栖。"):
    return CharacterEngineAgent(
        session=session,
        character_name="紅莉栖",
        llm=llm or RecordingLLM(),
        system=system,
        live2d_model=FakeLive2D(),
        tts_preprocessor_config=tts_config(),
    )


def batch(text):
    return BatchInput(texts=[TextData(source=TextSource.INPUT, content=text)])


async def say(current, text):
    async for _ in current.chat(batch(text)):
        pass


@pytest.fixture(autouse=True)
def _no_real_probe(monkeypatch):
    monkeypatch.setattr(
        basic_memory_module, "detect_context_window", lambda *a, **k: None
    )


def basic_agent(llm):
    return BasicMemoryAgent(
        llm=llm,
        system="你是紅莉栖。",
        live2d_model=FakeLive2D(),
        tts_preprocessor_config=tts_config(),
    )


def test_her_current_state_rides_on_the_newest_user_line():
    """量過的：放在系統提示尾端的話，心情一變模型就得把整段對話歷史重讀一遍，
    7 輪對話時第一個字從 1.1 秒變成 4.5 秒，而且對話越長越慢。接在最新一句後面
    是 1.0 秒。"""
    llm = RecordingLLM()
    current = agent(
        FakeSession(neutral(emotion="happy", relationship_stage="friend")), llm
    )

    asyncio.run(say(current, "你好"))

    assert llm.last_user_line().startswith("你好")
    assert "心情：開心" in llm.last_user_line()


def test_the_system_prompt_is_exactly_the_basic_agents_whatever_her_state():
    llm, basic_llm = RecordingLLM(), RecordingLLM()
    current = agent(FakeSession(neutral(emotion="happy")), llm)

    asyncio.run(say(current, "你好"))
    asyncio.run(say(basic_agent(basic_llm), "你好"))

    assert llm.systems == basic_llm.systems


def test_with_nothing_to_say_the_whole_request_is_exactly_the_basic_agents():
    llm, basic_llm = RecordingLLM(), RecordingLLM()

    asyncio.run(say(agent(FakeSession(), llm), "你好"))
    asyncio.run(say(basic_agent(basic_llm), "你好"))

    assert llm.systems == basic_llm.systems
    assert llm.conversations == basic_llm.conversations


def test_her_state_is_never_kept_as_something_the_user_said():
    llm = RecordingLLM()
    current = agent(FakeSession(neutral(emotion="happy")), llm)

    async def two_turns():
        await say(current, "你好")
        await say(current, "在嗎")

    asyncio.run(two_turns())

    assert current._memory[0] == {"role": "user", "content": "你好"}
    earlier_lines = llm.conversations[1][:-1]
    assert all("心情" not in text for _, text in earlier_lines)
    assert "心情：開心" in llm.last_user_line()


def test_she_is_told_the_note_is_not_the_users_words():
    llm = RecordingLLM()

    asyncio.run(say(agent(FakeSession(neutral(emotion="happy")), llm), "你好"))

    assert "不是對方說的話" in llm.last_user_line()


def test_each_turn_sees_the_state_as_it_is_now():
    llm = RecordingLLM()
    session = FakeSession()
    current = agent(session, llm)

    async def two_turns():
        await say(current, "你好")
        session.current = neutral(emotion="hurt")
        await say(current, "抱歉")

    asyncio.run(two_turns())

    assert "心情" not in llm.last_user_line(0)
    assert "心情：受傷" in llm.last_user_line(1)


def test_a_refreshed_persona_is_passed_straight_through():
    llm = RecordingLLM()
    current = agent(FakeSession(neutral(emotion="happy")), llm)

    async def scenario():
        await say(current, "你好")
        current.set_system("你是紅莉栖。\n\n## 你對對方的長期記憶\n對方養了一隻貓")
        await say(current, "記得嗎")

    asyncio.run(scenario())

    assert "對方養了一隻貓" in llm.systems[1]
    assert "心情" not in llm.systems[1]


def test_state_that_cannot_be_read_never_stops_the_conversation():
    llm = RecordingLLM()

    asyncio.run(say(agent(FakeSession(fail=True), llm), "你好"))

    assert llm.last_user_line() == "你好"


def test_a_finished_turn_is_handed_to_the_engine():
    session = FakeSession()
    current = agent(session)

    async def scenario():
        current.observe_turn("kurisu", "h1", "謝謝你", "不用謝啦。")
        await current.close()

    asyncio.run(scenario())

    assert session.turns == [("謝謝你", "不用謝啦。")]
    assert session.flushed == 1


def test_one_connection_closing_does_not_end_her_cognition_for_the_next():
    """agent 是所有連線共用的，而每個連線斷開時 ServiceContext.close() 都會呼叫
    agent.close()。重新整理一次頁面就把引擎關掉的話，之後的對話全都不會被觀察。"""
    session = FakeSession()
    current = agent(session)

    async def scenario():
        current.observe_turn("kurisu", "h1", "第一個連線", "嗯。")
        await current.close()
        current.observe_turn("kurisu", "h1", "第二個連線", "嗯。")
        await current.close()

    asyncio.run(scenario())

    assert [user for user, _ in session.turns] == ["第一個連線", "第二個連線"]
    assert session.closed is False


def test_each_turn_tells_the_engine_which_conversation_it_belongs_to():
    """agent 是所有連線共用的，兩個連線可以在不同的對話裡。"""
    session = FakeSession()
    current = agent(session)

    async def scenario():
        current.observe_turn("kurisu", "h1", "甲", "嗯。")
        current.observe_turn("kurisu", "h2", "乙", "嗯。")
        await current.close()

    asyncio.run(scenario())

    assert session.conversations == ["h1", "h2"]
    assert session.bound == []


def test_the_session_is_looked_up_each_time_so_a_replacement_takes_over():
    first, second = FakeSession(), FakeSession()
    current_session = [first]
    current = agent(lambda: current_session[0])

    async def scenario():
        current.observe_turn("kurisu", "h1", "甲", "嗯。")
        await current.close()
        current_session[0] = second
        current.observe_turn("kurisu", "h1", "乙", "嗯。")
        await current.close()

    asyncio.run(scenario())

    assert [user for user, _ in first.turns] == ["甲"]
    assert [user for user, _ in second.turns] == ["乙"]


def test_an_engine_that_is_down_never_reaches_the_conversation():
    current = agent(FakeSession(fail=True))

    async def scenario():
        current.observe_turn("kurisu", "h1", "謝謝你", "不用謝啦。")
        await current.close()

    asyncio.run(scenario())


def test_without_an_engine_session_she_is_just_the_basic_agent():
    llm = RecordingLLM()
    current = agent(None, llm)

    async def scenario():
        await say(current, "你好")
        current.observe_turn("kurisu", "h1", "你好", "嗯。")
        await current.close()

    asyncio.run(scenario())

    assert llm.last_user_line() == "你好"


def test_loading_a_conversation_gives_the_engine_its_recent_lines(monkeypatch):
    monkeypatch.setattr(
        basic_memory_module,
        "get_history",
        lambda conf_uid, history_uid: [
            {"role": "human", "content": "昨天說到哪"},
            {"role": "ai", "content": "說到時間機器"},
            {"role": "system", "content": "[Interrupted by user]"},
        ],
    )
    session = FakeSession()

    agent(session).set_memory_from_history("kurisu", "h1")

    assert session.bound == [
        ("h1", [("user", "昨天說到哪"), ("assistant", "說到時間機器")])
    ]


def factory_arguments(choice="character_engine_agent"):
    return {
        "conversation_agent_choice": choice,
        "agent_settings": {
            "basic_memory_agent": {"llm_provider": "lmstudio_llm", "use_mcpp": False},
            "character_engine_agent": {},
        },
        "llm_configs": {
            "lmstudio_llm": {
                "base_url": "http://127.0.0.1:1/v1",
                "model": "stub",
                "llm_api_key": "not-needed",
                "temperature": 0.7,
            }
        },
        "system_prompt": "你是紅莉栖。",
        "live2d_model": FakeLive2D(),
        "tts_preprocessor_config": tts_config(),
        "conf_uid": "kurisu",
        "character_name": "紅莉栖",
    }


def test_choosing_the_engine_without_it_installed_says_how_to_install_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "ai_character_engine", None)

    with pytest.raises(RuntimeError) as caught:
        AgentFactory.create_agent(**factory_arguments())

    message = str(caught.value)
    assert "ai-character-engine" in message
    assert "3.11" in message
    assert "basic_memory_agent" in message


def test_the_basic_agent_never_needs_the_engine(monkeypatch):
    monkeypatch.setitem(sys.modules, "ai_character_engine", None)

    created = AgentFactory.create_agent(**factory_arguments("basic_memory_agent"))

    assert type(created) is BasicMemoryAgent


def test_the_engine_is_told_when_she_starts_and_stops_talking():
    session = FakeSession()

    asyncio.run(say(agent(session), "你好"))

    assert session.talking == ["started", "finished"]


def test_the_engine_is_told_she_stopped_even_when_the_reply_is_cut_off():
    session = FakeSession()
    current = agent(session)

    async def interrupted():
        stream = current.chat(batch("你好"))
        async for _ in stream:
            break
        await stream.aclose()

    asyncio.run(interrupted())

    assert session.talking == ["started", "finished"]
