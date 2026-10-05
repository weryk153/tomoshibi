"""她的心情送到前端：character-mood。

心情怎麼來、怎麼淡在引擎測；這裡測主機的責任：訊息長什麼樣、什麼時候送、引擎
沒準備好就不送、背景結果改了心情要送到每個連著這個角色的頁面。
"""

import asyncio
import inspect
import json
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber.character_mood import (
    follow_mood,
    mood_message,
    send_character_mood,
)
from src.open_llm_vtuber.service_context import ServiceContext

SNAPSHOT = SimpleNamespace(
    emotion="sad",
    mood_intensity=0.8,
    mood_updated_at=1000.0,
    mood_half_life_seconds=300.0,
)
MESSAGE = {
    "type": "character-mood",
    "mood": "sad",
    "intensity": 0.8,
    "updated_at": 1000.0,
    "half_life": 300.0,
}


class Sent:
    def __init__(self):
        self.texts = []

    async def __call__(self, text):
        self.texts.append(json.loads(text))


class FakeSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, payload):
        self.sent.append(json.loads(payload))


class Listening:
    def __init__(self):
        self.listeners = []

    def listen_to_mood(self, listener):
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)


def test_the_message_carries_her_mood_as_set_not_faded():
    assert mood_message(SNAPSHOT) == MESSAGE


def test_an_engine_without_moods_has_no_message():
    assert mood_message(SimpleNamespace(emotion="happy", trust=50.0)) is None


def test_her_mood_is_sent_when_the_agent_can_tell_it():
    sent = Sent()
    assert asyncio.run(
        send_character_mood(SimpleNamespace(mood_message=lambda: MESSAGE), sent)
    )
    assert sent.texts == [MESSAGE]


@pytest.mark.parametrize(
    "agent",
    [None, SimpleNamespace(), SimpleNamespace(mood_message=lambda: None)],
    ids=["no agent", "an agent without moods", "engine not ready"],
)
def test_nothing_is_sent_when_there_is_no_mood_to_tell(agent):
    sent = Sent()
    assert asyncio.run(send_character_mood(agent, sent)) is False
    assert sent.texts == []


def test_a_failing_read_sends_nothing_and_does_not_raise():
    def broken():
        raise RuntimeError("engine closed")

    sent = Sent()
    assert (
        asyncio.run(send_character_mood(SimpleNamespace(mood_message=broken), sent))
        is False
    )
    assert sent.texts == []


def test_a_change_of_her_mood_reaches_the_page():
    agent, sent = Listening(), Sent()

    async def scenario():
        follow_mood(agent, sent)
        agent.listeners[0](MESSAGE)
        await asyncio.sleep(0)

    asyncio.run(scenario())
    assert sent.texts == [MESSAGE]


def test_a_page_that_is_gone_does_not_break_the_engine():
    """一個頁面的 socket 關了：引擎呼叫 listener 的當下不能炸，另一個還連著的
    頁面要照樣收到，而送失敗的 task 用完要從送出中的集合裡消失，不是卡著。"""
    import src.open_llm_vtuber.character_mood as character_mood

    agent, still_here = Listening(), Sent()

    async def closed(_text):
        raise RuntimeError("socket closed")

    async def scenario():
        follow_mood(agent, closed)
        follow_mood(agent, still_here)
        agent.listeners[0](MESSAGE)
        agent.listeners[1](MESSAGE)
        await asyncio.sleep(0)  # 讓兩個 task 真的跑
        await asyncio.sleep(0)  # 讓送失敗那個的 done callback 也跑完

    asyncio.run(scenario())

    assert still_here.texts == [MESSAGE]
    assert character_mood._SENDING == set()


def test_following_stops_when_told():
    agent = Listening()
    stop = follow_mood(agent, Sent())
    stop()
    assert agent.listeners == []


def test_there_is_nothing_to_follow_without_an_engine_agent():
    assert follow_mood(SimpleNamespace(), Sent())() is None

    listening = Listening()
    assert follow_mood(listening, None)() is None
    assert listening.listeners == []


def _context(agent):
    context = ServiceContext.__new__(ServiceContext)
    context.agent_engine = agent
    context.live2d_model = SimpleNamespace(model_info={"name": "m"})
    context.character_config = SimpleNamespace(conf_name="紅莉栖", conf_uid="kurisu")
    return context


def test_a_switched_or_reloaded_character_shows_her_mood_right_away():
    socket = FakeSocket()
    context = _context(SimpleNamespace(mood_message=lambda: MESSAGE))
    asyncio.run(context._send_model_and_conf(socket))
    assert [m["type"] for m in socket.sent] == ["set-model-and-conf", "character-mood"]


def test_each_page_follows_the_agent_it_has_now():
    first, second = Listening(), Listening()
    context = _context(first)
    context.send_text = Sent()
    context._follow_mood()
    context.agent_engine = second
    context._follow_mood()
    assert first.listeners == []
    assert len(second.listeners) == 1


def test_a_closed_page_stops_following():
    agent = Listening()
    context = _context(agent)
    context.send_text = Sent()
    context.mcp_client = None
    context._follow_mood()
    asyncio.run(context.close())
    assert agent.listeners == []


def test_every_place_that_hands_a_page_its_agent_follows_her_mood():
    assert "self._follow_mood()" in inspect.getsource(ServiceContext.load_cache)
    assert "self._follow_mood()" in inspect.getsource(ServiceContext.init_agent)


def test_her_mood_is_sent_once_a_turn_has_ended():
    from src.open_llm_vtuber.conversations import single_conversation

    src = inspect.getsource(single_conversation.process_single_conversation)
    assert "send_character_mood(context.agent_engine, websocket_send)" in src
    assert src.index("send_character_mood(") > src.index(
        "await finalize_conversation_turn("
    )


def test_a_new_page_hears_her_mood_right_after_her_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.open_llm_vtuber.chat_group import ChatGroupManager
    from src.open_llm_vtuber.websocket_handler import WebSocketHandler

    handler = WebSocketHandler.__new__(WebSocketHandler)
    handler.client_contexts = {}
    handler.client_connections = {}
    handler.client_last_active = {}
    handler.current_conversation_tasks = {}
    handler.received_data_buffers = {}
    handler.chat_group_manager = ChatGroupManager()
    handler.stream = None
    socket = FakeSocket()
    context = SimpleNamespace(
        history_uid="",
        character_config=SimpleNamespace(conf_uid="frieren", conf_name="frieren"),
        live2d_model=SimpleNamespace(model_info={}),
        agent_engine=SimpleNamespace(
            set_memory_from_history=lambda **kw: None, mood_message=lambda: MESSAGE
        ),
    )
    handler.client_connections["me"] = socket
    handler.client_contexts["me"] = context
    handler.chat_group_manager.client_group_map["me"] = ""

    asyncio.run(handler._send_initial_messages(socket, "me", context, stage=False))

    kinds = [m["type"] for m in socket.sent]
    assert kinds[kinds.index("set-model-and-conf") + 1] == "character-mood"
