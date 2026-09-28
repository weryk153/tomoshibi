"""引擎是選用的：它要 Python 3.11 以上，而這個專案支援 3.10。

這一份在沒裝引擎的環境也要跑，所以不能匯入引擎。
"""

import sys

import pytest

from src.open_llm_vtuber.agent.agent_factory import AgentFactory
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from tests.engine_factory_arguments import factory_arguments


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
