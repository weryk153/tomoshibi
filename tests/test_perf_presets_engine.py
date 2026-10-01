"""效能模式只調引擎背景工作的頻率與放在心上的數量。

接引擎時真正影響速度的是情緒、記憶、目標、反思各幾輪跑一次。語音辨識、聲音
不歸效能模式管：以前選一次「高效能」就把聲音打回 edge-tts。
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


def test_a_preset_no_longer_writes_the_old_memory_leaves(conf):
    """核心記憶上限與整理頻率只屬於拿掉的舊 agent；效能模式不再寫它們。"""
    for preset in perf_route.PRESETS.values():
        perf_route._apply_preset_bundle(preset)

    text = conf.read_text(encoding="utf-8")
    assert "core_memory_max_chars" not in text
    assert "memory_consolidation_interval" not in text


def test_a_preset_writes_only_performance_numbers(conf):
    before = conf.read_text(encoding="utf-8")
    perf_route._apply_preset_bundle(perf_route.PRESETS["light"])
    after = conf.read_text(encoding="utf-8")

    def leaf(text, key):
        return [
            line for line in text.splitlines() if line.strip().startswith(f"{key}:")
        ]

    for key in ("asr_model", "tts_model", "keep_alive"):
        assert leaf(before, key) == leaf(after, key)


def test_every_preset_sets_all_seven_numbers():
    for preset in perf_route.PRESETS.values():
        assert set(preset) == set(engine_config_route.EVERY_KEYS)


def test_the_current_preset_is_recognised_and_anything_else_is_custom(conf):
    perf_route._apply_preset_bundle(perf_route.PRESETS["high"])
    assert perf_route._current_preset() == "high"
    engine_config_route.write_engine_settings({"goal_every": 7})
    assert perf_route._current_preset() == "custom"


def test_keep_alive_is_gone():
    assert not hasattr(perf_route, "_write_keep_alive")
    assert not hasattr(perf_route, "_keep_alive_from_conf")


def test_the_presets_are_listed_from_light_to_high(conf, monkeypatch):
    """選單照字母排是「高效能、輕量、標準」，看起來沒有順序。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(perf_route, "_is_local_request", lambda r: True)
    app = FastAPI()
    app.include_router(perf_route.init_perf_route())
    assert TestClient(app).get("/api/perf").json()["presets"] == [
        "light",
        "standard",
        "high",
    ]
