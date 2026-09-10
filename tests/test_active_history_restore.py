"""A browser reload must land back in the conversation it left.

These exercise the real store and the real history files under ``tmp_path``;
only the agent engine and the socket are stand-ins.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber import active_history_store
from src.open_llm_vtuber.chat_history_manager import (
    create_new_history,
    get_history_list,
    store_message,
)
from src.open_llm_vtuber.websocket_handler import WebSocketHandler


CONF_UID = "aoi"


class _FakeAgent:
    def __init__(self):
        self.memory_loaded_from = []

    def set_memory_from_history(self, conf_uid, history_uid):
        self.memory_loaded_from.append((conf_uid, history_uid))


class _FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, payload):
        self.sent.append(json.loads(payload))


def _handler(context) -> WebSocketHandler:
    handler = WebSocketHandler.__new__(WebSocketHandler)
    handler.client_contexts = {"client-1": context}
    return handler


def _context(agent=None):
    return SimpleNamespace(
        character_config=SimpleNamespace(conf_uid=CONF_UID),
        history_uid="",
        agent_engine=agent if agent is not None else _FakeAgent(),
    )


def _messages_of(type_name, websocket):
    return [m for m in websocket.sent if m["type"] == type_name]


def _seed_conversation(text="我自己選了") -> str:
    history_uid = create_new_history(CONF_UID)
    store_message(CONF_UID, history_uid, "human", text)
    store_message(CONF_UID, history_uid, "ai", "哈，說起來也是")
    return history_uid


def _restore(handler, websocket, context):
    asyncio.run(handler._restore_or_create_history(websocket, "client-1", context))


@pytest.fixture(autouse=True)
def _in_tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_reconnect_resumes_the_saved_conversation():
    history_uid = _seed_conversation()
    active_history_store.set_active_history_uid(CONF_UID, history_uid)
    agent = _FakeAgent()
    context = _context(agent)
    websocket = _FakeWebSocket()

    _restore(_handler(context), websocket, context)

    assert context.history_uid == history_uid
    assert agent.memory_loaded_from == [(CONF_UID, history_uid)]
    assert not _messages_of("new-history-created", websocket)
    (payload,) = _messages_of("history-data", websocket)
    assert payload["history_uid"] == history_uid
    assert [m["content"] for m in payload["messages"]] == [
        "我自己選了",
        "哈，說起來也是",
    ]


def test_a_first_ever_connection_starts_a_new_conversation():
    context = _context()
    websocket = _FakeWebSocket()

    _restore(_handler(context), websocket, context)

    (payload,) = _messages_of("new-history-created", websocket)
    assert payload["history_uid"] == context.history_uid
    assert context.history_uid
    assert not _messages_of("history-data", websocket)


def test_a_saved_conversation_that_no_longer_exists_starts_a_new_one():
    active_history_store.set_active_history_uid(CONF_UID, "2026-01-01_00-00-00_gone")
    context = _context()
    websocket = _FakeWebSocket()

    _restore(_handler(context), websocket, context)

    (payload,) = _messages_of("new-history-created", websocket)
    assert context.history_uid == payload["history_uid"]
    assert context.history_uid != "2026-01-01_00-00-00_gone"
    assert not _messages_of("history-data", websocket)


def test_restoring_survives_a_broken_agent_engine():
    """A bad LLM config still opens the app; history must not crash the connect."""
    history_uid = _seed_conversation()
    active_history_store.set_active_history_uid(CONF_UID, history_uid)
    context = _context(agent=None)
    context.agent_engine = None
    websocket = _FakeWebSocket()

    _restore(_handler(context), websocket, context)

    assert context.history_uid == history_uid
    assert _messages_of("history-data", websocket)


def test_a_conversation_that_fails_to_load_still_lets_the_app_connect():
    """Resume runs on the connect path; it must never block the handshake."""

    corrupt_uid = _seed_conversation()

    class _AgentThatChokesOnOneHistory(_FakeAgent):
        def set_memory_from_history(self, conf_uid, history_uid):
            if history_uid == corrupt_uid:
                raise RuntimeError("corrupt memory")
            super().set_memory_from_history(conf_uid, history_uid)

    history_uid = corrupt_uid
    active_history_store.set_active_history_uid(CONF_UID, history_uid)
    context = _context(agent=_AgentThatChokesOnOneHistory())
    websocket = _FakeWebSocket()

    _restore(_handler(context), websocket, context)

    (payload,) = _messages_of("new-history-created", websocket)
    assert context.history_uid == payload["history_uid"]
    assert context.history_uid != history_uid
    assert not _messages_of("history-data", websocket)


def test_starting_a_new_conversation_is_what_gets_resumed_next_time():
    _seed_conversation()
    context = _context()
    websocket = _FakeWebSocket()
    handler = _handler(context)

    asyncio.run(handler._handle_create_history(websocket, "client-1", {}))

    assert active_history_store.get_active_history_uid(CONF_UID) == context.history_uid


def test_switching_to_an_older_conversation_is_what_gets_resumed_next_time():
    older = _seed_conversation("舊的那段")
    newer = _seed_conversation("新的那段")
    active_history_store.set_active_history_uid(CONF_UID, newer)
    context = _context()
    websocket = _FakeWebSocket()
    handler = _handler(context)

    asyncio.run(
        handler._handle_fetch_history(websocket, "client-1", {"history_uid": older})
    )

    assert active_history_store.get_active_history_uid(CONF_UID) == older

    # And a reload after that switch comes back to the older one, not the newest.
    reconnect_context = _context()
    reconnect_socket = _FakeWebSocket()
    _restore(_handler(reconnect_context), reconnect_socket, reconnect_context)
    assert reconnect_context.history_uid == older


def test_deleting_the_active_conversation_forgets_it():
    history_uid = _seed_conversation()
    active_history_store.set_active_history_uid(CONF_UID, history_uid)
    context = _context()
    context.history_uid = history_uid
    handler = _handler(context)

    asyncio.run(
        handler._handle_delete_history(
            _FakeWebSocket(), "client-1", {"history_uid": history_uid}
        )
    )

    assert active_history_store.get_active_history_uid(CONF_UID) is None


def test_deleting_some_other_conversation_keeps_the_active_one():
    active = _seed_conversation("還在用的")
    stale = _seed_conversation("要刪掉的")
    active_history_store.set_active_history_uid(CONF_UID, active)
    context = _context()
    context.history_uid = active
    handler = _handler(context)

    asyncio.run(
        handler._handle_delete_history(
            _FakeWebSocket(), "client-1", {"history_uid": stale}
        )
    )

    assert active_history_store.get_active_history_uid(CONF_UID) == active


def test_reload_no_longer_litters_empty_conversations():
    """The old flow minted a throwaway history per reload; this one must not."""
    history_uid = _seed_conversation()
    active_history_store.set_active_history_uid(CONF_UID, history_uid)

    for _ in range(3):
        context = _context()
        _restore(_handler(context), _FakeWebSocket(), context)

    assert [h["uid"] for h in get_history_list(CONF_UID)] == [history_uid]
