"""直播設定住在 conf.yaml 的 stream_config：沒有就用預設，寫入時就地改、不洗掉註解。"""

from pathlib import Path

import pytest
import yaml

from src.open_llm_vtuber.config_manager.stream import StreamConfig
from src.open_llm_vtuber.stream.settings import (
    read_stream_settings,
    write_stream_settings,
)

CONF = "system_config:\n  port: 12393  # 別動\ncharacter_config:\n  conf_uid: 'x'\n"


@pytest.fixture(autouse=True)
def _conf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(CONF, "utf-8")


def test_no_block_means_defaults():
    settings = read_stream_settings()
    assert settings == StreamConfig()
    assert settings.quiet_seconds == 30
    assert settings.blocklist == []


def test_first_write_adds_the_block_and_keeps_the_rest():
    write_stream_settings({"quiet_seconds": 45})
    text = Path("conf.yaml").read_text("utf-8")
    assert text.startswith(CONF)
    assert "port: 12393  # 別動" in text
    assert yaml.safe_load(text)["stream_config"] == {"quiet_seconds": 45}
    assert read_stream_settings().quiet_seconds == 45


def test_second_write_updates_in_place():
    write_stream_settings({"quiet_seconds": 45})
    write_stream_settings(
        {"quiet_seconds": 60, "youtube_url": "https://youtu.be/abcdefghijk"}
    )
    text = Path("conf.yaml").read_text("utf-8")
    assert text.count("quiet_seconds:") == 1
    block = yaml.safe_load(text)["stream_config"]
    assert block == {
        "quiet_seconds": 60,
        "youtube_url": "https://youtu.be/abcdefghijk",
    }


def test_blocklist_round_trips_with_quotes_and_chinese():
    write_stream_settings({"blocklist": ["笨蛋", "it's", ' "引號" ', "笨蛋", ""]})
    assert read_stream_settings().blocklist == ["笨蛋", "it's", '"引號"']


def test_bad_value_is_refused_and_the_file_is_untouched():
    before = Path("conf.yaml").read_text("utf-8")
    with pytest.raises(ValueError):
        write_stream_settings({"quiet_seconds": 1})
    with pytest.raises(ValueError):
        write_stream_settings({"no_such_field": 1})
    assert Path("conf.yaml").read_text("utf-8") == before


@pytest.mark.parametrize(
    "template",
    ["config_templates/conf.default.yaml", "config_templates/conf.ZH.default.yaml"],
)
def test_templates_carry_the_defaults(template):
    root = Path(__file__).resolve().parent.parent
    data = yaml.safe_load((root / template).read_text("utf-8"))
    assert StreamConfig.model_validate(data["stream_config"]) == StreamConfig()


def test_a_bad_hand_edit_falls_back_field_by_field():
    """手改 conf.yaml 寫錯一個值，不能害整個程式開不起來。"""
    Path("conf.yaml").write_text(
        CONF + "stream_config:\n  quiet_seconds: 2\n  blocklist: ['笨蛋']\n", "utf-8"
    )
    settings = read_stream_settings()
    assert settings.quiet_seconds == 30
    assert settings.blocklist == ["笨蛋"]


def test_the_app_config_tolerates_a_bad_stream_block():
    from src.open_llm_vtuber.config_manager.main import Config

    root = Path(__file__).resolve().parent.parent
    data = yaml.safe_load(
        (root / "config_templates/conf.default.yaml").read_text("utf-8")
    )
    data["stream_config"] = {"quiet_seconds": 2, "failure_limit": 5}
    config = Config.model_validate(data)
    assert config.stream_config.quiet_seconds == 30
    assert config.stream_config.failure_limit == 5
