"""舊 conf.yaml 開機時升級一次：逐行改，註解與排版原樣。"""

from src.open_llm_vtuber.conf_upgrade import upgrade_conf_lines

OLD = """\
character_config:
  conf_uid: 'mao'
  long_term_memory_enabled: true # 長期記憶
  core_memory_max_chars: 1500 # 舊 agent 的上限
  memory_consolidation_interval: 1
  agent_config:
    conversation_agent_choice: 'basic_memory_agent' # 對話代理
    agent_settings:
      basic_memory_agent:
        llm_provider: 'lmstudio_llm' # 用哪一組
        use_mcpp: true
      character_engine_agent:
        memory_every: 2
    llm_configs:
      lmstudio_llm:
        model: 'qwen/qwen3.5-9b'
"""


def lines(text):
    return text.splitlines(keepends=True)


def test_the_three_old_things_are_upgraded():
    upgraded = lines(OLD)
    changes = upgrade_conf_lines(upgraded)
    text = "".join(upgraded)

    assert "conversation_agent_choice: 'character_engine_agent' # 對話代理" in text
    assert (
        "      conversation:\n        llm_provider: 'lmstudio_llm' # 用哪一組\n" in text
    )
    assert "basic_memory_agent" not in text
    assert "core_memory_max_chars" not in text
    assert "memory_consolidation_interval" not in text
    assert len(changes) == 4


def test_comments_and_other_keys_survive():
    upgraded = lines(OLD)
    upgrade_conf_lines(upgraded)
    text = "".join(upgraded)

    assert "  long_term_memory_enabled: true # 長期記憶\n" in text
    assert "      character_engine_agent:\n        memory_every: 2\n" in text
    assert "        model: 'qwen/qwen3.5-9b'\n" in text


def test_upgrade_is_idempotent():
    upgraded = lines(OLD)
    upgrade_conf_lines(upgraded)
    again = list(upgraded)

    assert upgrade_conf_lines(again) == []
    assert again == upgraded


def test_a_file_without_an_agent_config_is_left_alone():
    text = lines("system_config:\n  port: 12393\n")
    assert upgrade_conf_lines(text) == []
    assert "".join(text) == "system_config:\n  port: 12393\n"
