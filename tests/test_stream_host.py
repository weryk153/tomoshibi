"""直播的一輪怎麼交給現有的對話流程。"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber import active_history_store
from src.open_llm_vtuber.conversations.conversation_handler import PROACTIVE_TEXT
from src.open_llm_vtuber.stream.chat_source import ChatMessage
from src.open_llm_vtuber.stream.host import WebSocketStreamHost


class FakeSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, payload):
        self.sent.append(json.loads(payload))


def context():
    return SimpleNamespace(
        history_uid="",
        character_config=SimpleNamespace(
            conf_uid="frieren", character_name="芙莉蓮", conf_name="frieren"
        ),
        system_config=SimpleNamespace(tool_prompts={}),
    )


def setup(process):
    ws = SimpleNamespace(
        client_contexts={"stage": context()},
        client_connections={"stage": FakeSocket()},
        current_conversation_tasks={},
    )
    host = WebSocketStreamHost(ws, process=process)
    host.controller = SimpleNamespace(stage_uid="stage")
    return ws, host


@pytest.fixture(autouse=True)
def _tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def comment(text="今天好冷"):
    return ChatMessage(id="1", author="小明", text=text, timestamp=0.0)


def test_a_comment_turn():
    calls = []

    async def process(**kwargs):
        calls.append(kwargs)
        return "好冷喔"

    ws, host = setup(process)
    result = asyncio.run(host.turn_runner("stream-1")(comment()))

    assert result == "ok"
    (call,) = calls
    assert call["user_input"] == "小明：今天好冷"
    assert call["client_uid"] == "stage"
    assert call["metadata"] == {
        "stream": True,
        "stream_comment": {"author": "小明", "text": "今天好冷"},
    }
    assert ws.client_contexts["stage"].history_uid == "stream-1"
    assert ws.client_connections["stage"].sent == [
        {"type": "stream-comment", "author": "小明", "text": "今天好冷"}
    ]


def test_a_quiet_turn():
    calls = []

    async def process(**kwargs):
        calls.append(kwargs)
        return "大家好"

    ws, host = setup(process)
    assert asyncio.run(host.turn_runner("stream-1")(None)) == "ok"
    assert calls[0]["user_input"] == PROACTIVE_TEXT
    assert calls[0]["metadata"]["stream"] is True
    assert calls[0]["metadata"]["proactive_speak"] is True
    assert ws.client_connections["stage"].sent[0] == {
        "type": "stream-comment",
        "author": "",
        "text": "",
    }


def test_empty_reply_or_exception_is_a_failure():
    async def empty(**kwargs):
        return ""

    async def boom(**kwargs):
        raise RuntimeError("llm down")

    assert asyncio.run(setup(empty)[1].turn_runner("s")(comment())) == "failed"
    assert asyncio.run(setup(boom)[1].turn_runner("s")(comment())) == "failed"


def test_stage_gone_or_turn_cancelled_by_disconnect_is_interrupted():
    async def slow(**kwargs):
        await asyncio.Event().wait()

    ws, host = setup(slow)

    async def disconnect_midway():
        run = asyncio.create_task(host.turn_runner("s")(comment()))
        while "stage" not in ws.current_conversation_tasks:
            await asyncio.sleep(0)
        ws.current_conversation_tasks["stage"].cancel()
        return await run

    assert asyncio.run(disconnect_midway()) == "interrupted"
    host.controller = SimpleNamespace(stage_uid=None)
    assert asyncio.run(host.turn_runner("s")(comment())) == "interrupted"


def test_stopping_cancels_the_turn_too():
    async def slow(**kwargs):
        await asyncio.Event().wait()

    ws, host = setup(slow)

    async def stop_midway():
        run = asyncio.create_task(host.turn_runner("s")(comment()))
        while "stage" not in ws.current_conversation_tasks:
            await asyncio.sleep(0)
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        await asyncio.sleep(0)
        return ws.current_conversation_tasks["stage"].cancelled()

    assert asyncio.run(stop_midway()) is True


def test_a_stream_history_does_not_move_the_private_resume_point():
    ws, host = setup(None)
    active_history_store.set_active_history_uid("frieren", "private-1")
    history_uid = host.new_stream_history("stage")
    assert history_uid
    assert active_history_store.get_active_history_uid("frieren") == "private-1"
    assert host.character_names("stage") == ("芙莉蓮", "frieren")
