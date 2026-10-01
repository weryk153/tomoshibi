"""設定頁的「由 AI Character Engine 驅動對話」開關與它的幾個數字。

跟 use_mcpp 一樣直接讀寫 conf.yaml：conf.yaml 只在啟動時讀一次，存了要重啟。
"""

import pytest

from src.open_llm_vtuber import conf_editor
from src.open_llm_vtuber import engine_config_route as route

CONF = """character_config:
  agent_config:
    conversation_agent_choice: 'basic_memory_agent' # 对话代理选择
    agent_settings:
      conversation:
        llm_provider: 'openai_compatible_llm'
        use_mcpp: False
      character_engine_agent:
        # Run each background job every N turns; 0 turns it off.
        emotion_every: 1
        memory_every: 2
        summary_every: 0
        reflection_every: 6
        goal_every: 4
        timeout_seconds: 60 # per background job
      letta_agent:
        host: 'localhost'
"""


@pytest.fixture(autouse=True)
def conf_file(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(conf_editor, "CONF_PATH", str(path))
    monkeypatch.setattr(route, "CONF_PATH", str(path), raising=False)
    return path


def test_reading_gives_the_numbers_and_the_engine_is_always_on():
    assert route.read_engine_settings() == {
        "enabled": True,
        "emotion_every": 1,
        "memory_every": 2,
        "self_memory_every": 2,
        "goal_every": 4,
        "reflection_every": 6,
        "goals_shown": 3,
        "thoughts_shown": 2,
        "background_base_url": "",
        "background_model": "",
    }


def test_the_old_switch_no_longer_writes_the_choice(conf_file):
    """引擎是唯一的對話方式；舊畫面送來的 enabled 不再改 conversation_agent_choice。"""
    before = conf_file.read_text(encoding="utf-8")
    route.write_engine_settings({"enabled": False})

    assert conf_file.read_text(encoding="utf-8") == before


def test_the_numbers_are_written_where_they_live_and_the_rest_is_kept(conf_file):
    route.write_engine_settings({"memory_every": 3, "goal_every": 0})

    text = conf_file.read_text(encoding="utf-8")
    assert "        memory_every: 3\n" in text
    assert "        goal_every: 0\n" in text
    assert "        emotion_every: 1\n" in text
    assert "timeout_seconds: 60 # per background job" in text
    assert "# Run each background job every N turns; 0 turns it off." in text
    assert "use_mcpp: False" in text


def test_a_conf_without_the_engine_block_gets_one(conf_file):
    conf_file.write_text(
        "character_config:\n"
        "  agent_config:\n"
        "    conversation_agent_choice: 'basic_memory_agent'\n"
        "    agent_settings:\n"
        "      conversation:\n"
        "        llm_provider: 'openai_compatible_llm'\n",
        encoding="utf-8",
    )

    route.write_engine_settings({"enabled": True, "memory_every": 3})

    assert route.read_engine_settings() == {
        "enabled": True,
        "emotion_every": 1,
        "memory_every": 3,
        "self_memory_every": 2,
        "goal_every": 4,
        "reflection_every": 6,
        "goals_shown": 3,
        "thoughts_shown": 2,
        "background_base_url": "",
        "background_model": "",
    }


def test_numbers_are_clamped_and_non_numbers_ignored(conf_file):
    route.write_engine_settings(
        {"memory_every": -5, "goal_every": 10_000, "reflection_every": "abc"}
    )

    settings = route.read_engine_settings()
    assert settings["memory_every"] == 0
    assert settings["goal_every"] == route.EVERY_MAX
    assert settings["reflection_every"] == 6


def test_availability_says_why_the_engine_cannot_be_used(monkeypatch):
    monkeypatch.setattr(route.sys, "version_info", (3, 10, 0))
    available, reason = route.engine_availability()
    assert available is False
    assert "3.11" in reason

    monkeypatch.setattr(route.sys, "version_info", (3, 12, 0))
    monkeypatch.setattr(route, "_engine_importable", lambda: False)
    available, reason = route.engine_availability()
    assert available is False
    assert "ai-character-engine" in reason

    monkeypatch.setattr(route, "_engine_importable", lambda: True)
    assert route.engine_availability() == (True, "")


def test_the_endpoints_read_and_write_and_say_a_restart_is_needed(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(route, "_is_local_request", lambda request: True)
    monkeypatch.setattr(route, "engine_availability", lambda: (True, ""))
    app = FastAPI()
    app.include_router(route.init_engine_config_route())
    client = TestClient(app)

    before = client.get("/api/agent-config/character-engine").json()
    assert before["enabled"] is True
    assert before["available"] is True

    saved = client.post(
        "/api/agent-config/character-engine", json={"memory_every": 3}
    ).json()
    assert saved["ok"] is True
    assert saved["restart_required"] is True
    assert saved["enabled"] is True
    assert saved["memory_every"] == 3

    after = client.get("/api/agent-config/character-engine").json()
    assert after["enabled"] is True
    assert after["memory_every"] == 3


def test_the_background_model_is_written_and_read_back(conf_file):
    route.write_engine_settings(
        {
            "background_base_url": " http://127.0.0.1:1235/v1 ",
            "background_model": "qwen/qwen3.5-9b",
        }
    )

    settings = route.read_engine_settings()
    text = conf_file.read_text(encoding="utf-8")

    assert settings["background_base_url"] == "http://127.0.0.1:1235/v1"
    assert settings["background_model"] == "qwen/qwen3.5-9b"
    assert "        background_base_url: 'http://127.0.0.1:1235/v1'\n" in text
    # 清空就是回到跟她講話同一顆。
    route.write_engine_settings({"background_base_url": "", "background_model": ""})
    assert route.read_engine_settings()["background_model"] == ""


def test_a_background_address_that_would_break_the_file_is_ignored(conf_file):
    before = conf_file.read_text(encoding="utf-8")

    route.write_engine_settings(
        {
            "background_base_url": "127.0.0.1:1235",  # 不是網址
            "background_model": "x'\nmalicious: 1",  # 會弄壞 YAML
        }
    )

    assert conf_file.read_text(encoding="utf-8") == before


def test_what_the_settings_page_writes_reaches_the_engine():
    """設定檔要先過 config_manager 的模型，它不認得的欄位會被靜靜丟掉：self_memory_every
    加進設定頁之後，實際上從來沒傳到引擎。"""
    from src.open_llm_vtuber.config_manager.agent import CharacterEngineAgentConfig

    dumped = CharacterEngineAgentConfig(
        self_memory_every=3,
        background_base_url="http://127.0.0.1:1235/v1",
        background_model="qwen/qwen3.5-9b",
    ).model_dump()

    for key in (*route.EVERY_KEYS, *route.TEXT_KEYS):
        assert key in dumped, key
    assert dumped["self_memory_every"] == 3
    assert dumped["background_model"] == "qwen/qwen3.5-9b"
