"""效能模式也要調引擎背景工作的頻率。

接引擎時真正影響速度的是情緒、記憶、目標、反思各幾輪跑一次；效能模式原本只
調舊 agent 的核心記憶上限與整理頻率，在慢機器上選「輕量」引擎照跑不誤。
"""

import shutil

import pytest

from src.open_llm_vtuber import conf_editor, engine_config_route, perf_route


@pytest.fixture
def conf(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    shutil.copy("config_templates/conf.default.yaml", path)
    monkeypatch.setattr(conf_editor, "CONF_PATH", str(path))
    monkeypatch.setattr(perf_route, "CONF_PATH", str(path), raising=False)
    monkeypatch.setattr(engine_config_route, "CONF_PATH", str(path), raising=False)
    return path


def test_the_light_preset_makes_the_engine_think_less_often(conf):
    perf_route._apply_preset_bundle(perf_route.PRESETS["light"])

    settings = engine_config_route.read_engine_settings()
    assert settings["memory_every"] > 2
    assert settings["goal_every"] > 4
    assert settings["reflection_every"] > 6


def test_the_standard_preset_restores_the_engine_defaults(conf):
    perf_route._apply_preset_bundle(perf_route.PRESETS["light"])
    perf_route._apply_preset_bundle(perf_route.PRESETS["standard"])

    settings = engine_config_route.read_engine_settings()
    assert {k: settings[k] for k in engine_config_route.EVERY_DEFAULTS} == (
        engine_config_route.EVERY_DEFAULTS
    )


def test_a_preset_does_not_switch_the_engine_on_or_off(conf):
    before = engine_config_route.read_engine_settings()["enabled"]
    perf_route._apply_preset_bundle(perf_route.PRESETS["high"])

    assert engine_config_route.read_engine_settings()["enabled"] is before


def test_a_preset_no_longer_writes_the_old_memory_leaves(conf):
    """核心記憶上限與整理頻率只屬於拿掉的舊 agent；效能模式不再寫它們。"""
    for preset in perf_route.PRESETS.values():
        perf_route._apply_preset_bundle(preset)

    text = conf.read_text(encoding="utf-8")
    assert "core_memory_max_chars" not in text
    assert "memory_consolidation_interval" not in text
