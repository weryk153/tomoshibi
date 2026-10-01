"""記憶只剩引擎那一份：記憶頁不再有字數上限與整理頻率，沒有引擎時拒絕寫入。"""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import memory_route


def client(tmp_path, monkeypatch, contexts):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(memory_route, "_is_local_request", lambda request: True)
    monkeypatch.setattr(memory_route, "_resolve_conf_uid", lambda value: (value, None))
    app = FastAPI()
    app.include_router(memory_route.init_memory_route(contexts))
    return TestClient(app)


def test_the_page_shows_only_what_the_engine_remembers(tmp_path, monkeypatch):
    agent = SimpleNamespace(
        conversation_memory=lambda uid: "對方：名字是晨星。",
        rewrite_conversation_memory=lambda uid, text, **_: None,
        self_memory=lambda: "紅莉栖喜歡咖啡。",
        rewrite_self_memory=lambda text, **_: None,
    )
    ctx = SimpleNamespace(
        character_config=SimpleNamespace(conf_uid="kurisu"),
        history_uid="h1",
        agent_engine=agent,
    )
    shown = (
        client(tmp_path, monkeypatch, {"c": ctx})
        .get("/api/memory", params={"conf_uid": "kurisu"})
        .json()
    )

    assert shown["content"] == "對方：名字是晨星。"
    assert shown["self_content"] == "紅莉栖喜歡咖啡。"
    for gone in ("cap", "consolidation_interval", "self_cap", "engine_managed"):
        assert gone not in shown


def test_the_old_settings_endpoints_are_gone(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch, {})
    assert (
        http.post(
            "/api/memory/cap", json={"conf_uid": "kurisu", "cap": 2000}
        ).status_code
        == 404
    )
    assert (
        http.post(
            "/api/memory/consolidation", json={"conf_uid": "kurisu", "interval": 3}
        ).status_code
        == 404
    )


def test_without_her_engine_an_edit_is_refused(tmp_path, monkeypatch):
    from src.open_llm_vtuber.character_engine import factory

    monkeypatch.setattr(factory, "current_companion", lambda key: None)
    response = client(tmp_path, monkeypatch, {}).post(
        "/api/memory/self", json={"conf_uid": "kurisu", "content": "x"}
    )
    assert response.status_code == 409
