"""對話用的模型與工具設定，從 basic_memory_agent 區塊改名成 conversation。

舊 agent 拿掉之後，那個區塊裝的其實是對話用的 llm_provider／use_mcpp／斷句設定，
引擎 agent 也靠它。名字改中性；舊名字（舊 conf.yaml、角色檔的深度合併）照樣讀得到。
"""

from src.open_llm_vtuber.config_manager.agent import (
    AgentConfig,
    AgentSettings,
    conversation_block,
)

LLM_CONFIGS = {"lmstudio_llm": {"base_url": "http://127.0.0.1:1234/v1", "model": "m"}}


def test_the_new_block_name_is_read():
    settings = AgentSettings(
        conversation={"llm_provider": "lmstudio_llm", "use_mcpp": True}
    )
    assert settings.conversation.llm_provider == "lmstudio_llm"
    assert settings.conversation.use_mcpp is True


def test_the_old_block_name_is_still_read():
    settings = AgentSettings(basic_memory_agent={"llm_provider": "lmstudio_llm"})
    assert settings.conversation.llm_provider == "lmstudio_llm"
    assert "basic_memory_agent" not in settings.model_dump()


def test_the_new_name_wins_when_both_are_there():
    settings = AgentSettings(
        conversation={"llm_provider": "lmstudio_llm"},
        basic_memory_agent={"llm_provider": "ollama_llm"},
    )
    assert settings.conversation.llm_provider == "lmstudio_llm"


def test_the_old_agent_choice_becomes_the_engine():
    for old in ("basic_memory_agent", "mem0_agent"):
        config = AgentConfig(
            conversation_agent_choice=old,
            agent_settings={"conversation": {"llm_provider": "lmstudio_llm"}},
            llm_configs=LLM_CONFIGS,
        )
        assert config.conversation_agent_choice == "character_engine_agent"


def test_raw_yaml_readers_get_either_name():
    assert conversation_block({"conversation": {"use_mcpp": True}}) == {
        "use_mcpp": True
    }
    assert conversation_block({"basic_memory_agent": {"use_mcpp": False}}) == {
        "use_mcpp": False
    }
    assert conversation_block({}) == {}
    assert conversation_block(None) == {}


def test_a_character_file_with_the_old_name_still_overrides_the_upgraded_base():
    """conf.yaml 開機升級成 conversation 之後，手寫角色檔若還寫 basic_memory_agent，
    深度合併會兩個名字並存；不先改名的話，角色檔指定的模型被底稿蓋掉、沒有任何提示。"""
    from src.open_llm_vtuber.config_manager import AgentSettings
    from src.open_llm_vtuber.config_manager.agent import with_conversation_block
    from src.open_llm_vtuber.service_context import deep_merge

    base = {
        "agent_config": {
            "agent_settings": {
                "conversation": {"llm_provider": "lmstudio_llm", "use_mcpp": True}
            }
        }
    }
    character = {
        "agent_config": {
            "agent_settings": {"basic_memory_agent": {"llm_provider": "ollama_llm"}}
        }
    }

    merged = deep_merge(base, with_conversation_block(character))
    settings = AgentSettings.model_validate(merged["agent_config"]["agent_settings"])

    assert settings.conversation.llm_provider == "ollama_llm"
    assert settings.conversation.use_mcpp is True


def test_renaming_the_old_block_leaves_other_character_settings_alone():
    from src.open_llm_vtuber.config_manager.agent import with_conversation_block

    character = {
        "conf_uid": "kurisu",
        "agent_config": {"conversation_agent_choice": "x"},
    }
    assert with_conversation_block(character) == character
    assert with_conversation_block({"conf_uid": "kurisu"}) == {"conf_uid": "kurisu"}


def test_switching_characters_renames_before_merging():
    import inspect

    from src.open_llm_vtuber.service_context import ServiceContext

    source = inspect.getsource(ServiceContext)
    assert (
        "deep_merge(\n                base_character_data, with_conversation_block(alt_config_data)\n            )"
        in source
    )
