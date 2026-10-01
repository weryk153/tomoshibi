"""改模型、改工具開關，寫進 agent_settings.conversation，不寫到檔案別處。"""

from src.open_llm_vtuber import conf_editor, llm_config_route, player_route

CONF = """\
character_config:
  agent_config:
    conversation_agent_choice: 'character_engine_agent'
    agent_settings:
      letta_agent:
        llm_provider: 'not_this_one'
      conversation:
        llm_provider: 'lmstudio_llm'
        use_mcpp: False
    llm_configs:
      lmstudio_llm:
        model: 'a'
      ollama_llm:
        model: 'b'
"""


def setup(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(conf_editor, "CONF_PATH", str(path))
    return path


def test_provider_is_written_inside_the_conversation_block(tmp_path, monkeypatch):
    path = setup(tmp_path, monkeypatch)
    lines = conf_editor.read_conf_lines()
    llm_config_route._point_llm_provider_at(lines, "ollama_llm")
    conf_editor.write_conf(lines)
    text = path.read_text(encoding="utf-8")

    assert "      conversation:\n        llm_provider: 'ollama_llm'\n" in text
    assert "llm_provider: 'not_this_one'" in text


def test_the_tools_switch_is_written_inside_the_conversation_block(
    tmp_path, monkeypatch
):
    path = setup(tmp_path, monkeypatch)
    player_route._write_use_mcpp(True)

    assert (
        "      conversation:\n        llm_provider: 'lmstudio_llm'\n        use_mcpp: True\n"
        in path.read_text(encoding="utf-8")
    )


def test_the_active_provider_is_read_from_the_conversation_block():
    data = {
        "character_config": {
            "agent_config": {"agent_settings": {"conversation": {"llm_provider": "x"}}}
        }
    }
    assert llm_config_route._get_llm_provider(data) == "x"
