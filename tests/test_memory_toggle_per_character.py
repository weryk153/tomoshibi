"""記憶開關跟角色走：切到哪個角色就改哪個角色，畫面顯示的是她實際的值。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import (
    character_route,
    character_settings,
    conf_editor,
    memory_route,
)

BASE = "character_config:\n  conf_uid: 'base_uid'\n"
OTHER = "character_config:\n  conf_uid: 'kurisu'\n  long_term_memory_enabled: false\n"


def http(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(BASE, "utf-8")
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "kurisu.yaml").write_text(OTHER, "utf-8")
    for module in (conf_editor, character_route, character_settings, memory_route):
        monkeypatch.setattr(module, "CONF_PATH", "conf.yaml", raising=False)
    monkeypatch.setattr(memory_route, "_is_local_request", lambda r: True)
    monkeypatch.setattr(memory_route, "_resolve_conf_uid", lambda v: (v, None))
    app = FastAPI()
    app.include_router(memory_route.init_memory_route({}))
    return TestClient(app)


def test_the_switch_writes_the_character_it_was_sent_for(tmp_path, monkeypatch):
    client = http(tmp_path, monkeypatch)
    r = client.post("/api/memory/toggle", json={"conf_uid": "kurisu", "enabled": True})
    assert r.status_code == 200
    assert (
        character_settings.effective("kurisu.yaml")["long_term_memory_enabled"] is True
    )
    assert "long_term_memory_enabled" not in (tmp_path / "conf.yaml").read_text("utf-8")


def test_the_page_shows_her_own_value(tmp_path, monkeypatch):
    client = http(tmp_path, monkeypatch)
    monkeypatch.setattr(
        memory_route, "_resolved_history_uid", lambda contexts, uid: ("h1", None)
    )
    shown = client.get("/api/memory", params={"conf_uid": "kurisu"}).json()
    assert shown["enabled"] is False


def test_an_unknown_character_is_404(tmp_path, monkeypatch):
    client = http(tmp_path, monkeypatch)
    r = client.post("/api/memory/toggle", json={"conf_uid": "nobody", "enabled": False})
    assert r.status_code == 404


def test_the_switch_refuses_anything_but_true_or_false(tmp_path, monkeypatch):
    """送字串 "false" 以前會被 bool() 當成 True，寫進去的是相反的值。"""
    client = http(tmp_path, monkeypatch)
    before = (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8")
    r = client.post(
        "/api/memory/toggle", json={"conf_uid": "kurisu", "enabled": "false"}
    )
    assert r.status_code == 400
    assert (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8") == before
