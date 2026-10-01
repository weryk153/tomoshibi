"""只剩引擎 agent：工廠不再建 BasicMemoryAgent，也不再白建一個 Tomoshibi 自己的 LLM 客戶端。"""

import importlib.util

import pytest


def test_the_old_agent_is_gone():
    assert (
        importlib.util.find_spec("src.open_llm_vtuber.agent.agents.basic_memory_agent")
        is None
    )
    assert (
        importlib.util.find_spec("src.open_llm_vtuber.agent.stateless_llm_factory")
        is None
    )


def test_an_unknown_choice_is_refused():
    from src.open_llm_vtuber.agent.agent_factory import AgentFactory

    with pytest.raises(ValueError, match="Unsupported agent type"):
        AgentFactory.create_agent(
            conversation_agent_choice="basic_memory_agent",
            agent_settings={},
            llm_configs={},
            system_prompt="",
        )
