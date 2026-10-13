"""Minecraft 模式的設定：讀 conf.yaml 的 minecraft_config、寫回時只動該區塊。"""

import pytest

from src.open_llm_vtuber import conf_editor
from src.open_llm_vtuber.config_manager.minecraft import MinecraftConfig
from src.open_llm_vtuber.minecraft.settings import (
    read_minecraft_settings,
    write_minecraft_settings,
)

CONF = "system_config:\n  port: 12393  # 別動\ncharacter_config:\n  conf_uid: 'x'\n"


@pytest.fixture(autouse=True)
def _conf(tmp_path, monkeypatch):
    # read_yaml 只吃 cwd 底下的路徑，所以跟 test_stream_settings 一樣 chdir 到暫存目錄，
    # 讓 conf_editor.CONF_PATH 指到裡面的 conf.yaml。
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(CONF, "utf-8")
    monkeypatch.setattr(conf_editor, "CONF_PATH", "conf.yaml")


def test_defaults_when_block_missing():
    settings = read_minecraft_settings()
    assert settings.mindserver_url == "http://127.0.0.1:8080"
    assert settings.bot_name == ""
    assert settings.idle_seconds == 15
    assert settings.idle_cooldown_seconds == 60
    assert settings.event_cooldown_seconds == 30
    assert settings.tool_timeout_seconds == 12
    assert settings.failure_limit == 3
    assert "diamond" in settings.notable_items


def test_lenient_keeps_good_keys_and_drops_bad_ones():
    settings = MinecraftConfig.lenient({"idle_seconds": 0, "bot_name": "frieren"})
    assert settings.bot_name == "frieren"
    assert settings.idle_seconds == 15


def test_write_appends_block_and_only_touches_changed_keys():
    before = open(conf_editor.CONF_PATH, encoding="utf-8").read()
    written = write_minecraft_settings({"bot_name": "frieren", "idle_seconds": 20})
    assert written.bot_name == "frieren"
    after = open(conf_editor.CONF_PATH, encoding="utf-8").read()
    assert after.startswith(before)
    assert "minecraft_config:" in after
    assert "bot_name: 'frieren'" in after
    assert "idle_seconds: 20" in after
    assert read_minecraft_settings().idle_seconds == 20


def test_write_rejects_unknown_and_invalid():
    with pytest.raises(ValueError):
        write_minecraft_settings({"nope": 1})
    with pytest.raises(ValueError):
        write_minecraft_settings({"idle_seconds": 1})


def test_notable_items_are_cleaned():
    settings = MinecraftConfig.lenient(
        {"notable_items": [" diamond ", "", "diamond", "bread"]}
    )
    assert settings.notable_items == ["diamond", "bread"]
