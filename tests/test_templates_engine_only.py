"""三份範本都是引擎 agent，而且能通過設定驗證。"""

import pytest

from src.open_llm_vtuber.config_manager.utils import read_yaml, validate_config

TEMPLATES = (
    "config_templates/conf.default.yaml",
    "config_templates/conf.ZH.default.yaml",
    "config_templates/conf.tomoshibi.default.yaml",
)


@pytest.mark.parametrize("path", TEMPLATES)
def test_a_template_is_engine_only_and_valid(path):
    text = open(path, encoding="utf-8").read()
    assert "basic_memory_agent" not in text
    assert "core_memory_max_chars" not in text
    config = validate_config(read_yaml(path))
    agent = config.character_config.agent_config
    assert agent.conversation_agent_choice == "character_engine_agent"
    assert agent.agent_settings.conversation is not None
    assert agent.agent_settings.character_engine_agent is not None
