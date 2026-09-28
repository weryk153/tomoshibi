"""裝了引擎時，工廠真的建得出 character_engine_agent，而且狀態存在角色自己的資料夾。"""

import asyncio

import pytest

pytest.importorskip("ai_character_engine")

from src.open_llm_vtuber.agent.agent_factory import AgentFactory  # noqa: E402
from src.open_llm_vtuber.agent.agents.character_engine_agent import (  # noqa: E402
    CharacterEngineAgent,
)
from src.open_llm_vtuber.character_engine.factory import _worker_client  # noqa: E402
from tests.test_engine_agent import factory_arguments  # noqa: E402


def test_the_factory_builds_the_engine_agent_with_per_character_storage(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    async def scenario():
        created = AgentFactory.create_agent(**factory_arguments())
        created.observe_turn("kurisu", "h1", "你好", "嗯，你好。")
        await created.close()
        return created

    created = asyncio.run(scenario())

    assert isinstance(created, CharacterEngineAgent)
    assert (tmp_path / "chat_history" / "kurisu" / "engine" / "state.json").is_file()


def test_engine_state_lives_next_to_that_characters_chat_history(tmp_path, monkeypatch):
    """conf_uid 的清理方式要跟 chat_history_manager 一樣，不然同一個角色的歷史
    在一個資料夾、引擎狀態在另一個。"""
    monkeypatch.chdir(tmp_path)
    arguments = factory_arguments()
    arguments["conf_uid"] = "../../outside"

    async def scenario():
        created = AgentFactory.create_agent(**arguments)
        created.observe_turn("../../outside", "h1", "你好", "嗯。")
        await created.close()

    asyncio.run(scenario())

    assert (tmp_path / "chat_history" / "outside" / "engine" / "state.json").is_file()
    assert not (tmp_path.parent / "outside").exists()


def test_a_conf_uid_that_is_not_a_name_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arguments = factory_arguments()
    arguments["conf_uid"] = ".."

    with pytest.raises(ValueError):
        AgentFactory.create_agent(**arguments)

    assert not (tmp_path / "chat_history").exists()


def test_rebuilding_the_agent_with_the_same_settings_keeps_the_same_session(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    async def scenario():
        first = AgentFactory.create_agent(**factory_arguments())
        second = AgentFactory.create_agent(**factory_arguments())
        first.observe_turn("kurisu", "h1", "一", "嗯。")
        await first.close()
        second.observe_turn("kurisu", "h1", "二", "嗯。")
        await second.close()
        return first, second

    first, second = asyncio.run(scenario())

    assert first._current_session() is second._current_session()
    assert second._current_session().snapshot().trust == pytest.approx(50.6)


def test_changing_the_model_moves_every_agent_to_the_new_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def scenario():
        before = AgentFactory.create_agent(**factory_arguments())
        before.observe_turn("kurisu", "h1", "一", "嗯。")
        await before.close()
        old_session = before._current_session()
        changed = factory_arguments()
        changed["llm_configs"]["lmstudio_llm"]["model"] = "another-model"
        after = AgentFactory.create_agent(**changed)
        before.observe_turn("kurisu", "h1", "舊連線繼續聊", "嗯。")
        await before.close()
        return before, after, old_session

    before, after, old_session = asyncio.run(scenario())

    assert before._current_session() is after._current_session()
    assert before._current_session() is not old_session
    assert after._current_session().snapshot().trust == pytest.approx(50.6)


def test_background_workers_keep_only_the_reasoning_switches():
    client = _worker_client(
        "lmstudio_llm",
        {
            "base_url": "http://127.0.0.1:1/v1",
            "model": "stub",
            "extra_body": {
                "reasoning_effort": "none",
                "presence_penalty": 0.6,
                "top_k": 20,
            },
        },
    )

    assert client.request_options["extra_body"] == {"reasoning_effort": "none"}


def test_a_provider_that_is_not_openai_compatible_turns_cognition_off():
    assert _worker_client("claude_llm", {"model": "claude", "base_url": "x"}) is None
    assert _worker_client("lmstudio_llm", {"model": "stub"}) is None
