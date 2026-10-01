"""引擎是 Tomoshibi 的依賴；萬一沒裝起來，錯誤要說怎麼補。"""

import sys

import pytest

from src.open_llm_vtuber.agent.agent_factory import AgentFactory
from tests.engine_factory_arguments import factory_arguments


def test_choosing_the_engine_without_it_installed_says_how_to_install_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "ai_character_engine", None)

    with pytest.raises(RuntimeError) as caught:
        AgentFactory.create_agent(**factory_arguments())

    message = str(caught.value)
    assert "ai-character-engine" in message
    assert "3.11" in message
    assert "uv sync" in message
