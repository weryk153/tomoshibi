"""self 記憶端點只以 conf_uid 為鍵；記憶由引擎拿著，沒有引擎就不收。

用 FastAPI TestClient 打真的 router，conf_uid 驗證接縫（_resolve_conf_uid 用的
_existing_conf_uids）換成固定集合，檔案系統在 tmp_path。
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import memory_route as mr
from src.open_llm_vtuber.character_engine import factory

CONF = "aoi"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mr, "_existing_conf_uids", lambda: {CONF})
    monkeypatch.setattr(mr, "_base_conf_uid", lambda: CONF)
    monkeypatch.setattr(mr, "_is_local_request", lambda _r: True)
    # 這台機器上沒有她在跑的引擎。
    monkeypatch.setattr(factory, "current_companion", lambda _storage: None)
    contexts = {}
    app = FastAPI()
    app.include_router(mr.init_memory_route(contexts))
    return TestClient(app), contexts


def test_self_save_without_her_engine_is_refused(client, tmp_path):
    """以前沒有引擎時寫進 self_memory.md；現在沒有人會讀那個檔，寫了等於丟掉。"""
    c, _ = client
    r = c.post("/api/memory/self", json={"conf_uid": CONF, "content": "她喜歡咖啡。"})
    assert r.status_code == 409
    assert r.json()["error"] == mr.ENGINE_NOT_RUNNING
    assert not (tmp_path / "chat_history" / CONF / "self_memory.md").exists()


def test_self_clear_without_her_engine_is_refused(client):
    c, _ = client
    r = c.post("/api/memory/self/clear", json={"conf_uid": CONF})
    assert r.status_code == 409
    assert r.json()["error"] == mr.ENGINE_NOT_RUNNING


def test_self_save_requires_a_string(client):
    c, _ = client
    r = c.post("/api/memory/self", json={"conf_uid": CONF, "content": 123})
    assert r.status_code == 400


def test_self_endpoints_reject_unknown_conf_uid(client):
    c, _ = client
    assert (
        c.post(
            "/api/memory/self", json={"conf_uid": "nope", "content": "x"}
        ).status_code
        == 400
    )
    assert (
        c.post("/api/memory/self/clear", json={"conf_uid": "nope"}).status_code == 400
    )


def test_get_still_409s_without_a_connection(client):
    c, _ = client
    assert c.get(f"/api/memory?conf_uid={CONF}").status_code == 409


def test_get_reads_both_memories_from_the_agent(client, monkeypatch):
    c, contexts = client
    monkeypatch.setattr(
        mr, "read_yaml", lambda _p: {"character_config": {"conf_uid": CONF}}
    )
    contexts["client-1"] = SimpleNamespace(
        character_config=SimpleNamespace(conf_uid=CONF),
        history_uid="conv-1",
        agent_engine=SimpleNamespace(
            conversation_memory=lambda uid: "對方叫小明。",
            self_memory=lambda: "她喜歡咖啡。",
        ),
    )
    r = c.get(f"/api/memory?conf_uid={CONF}")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "conf_uid": CONF,
        "enabled": True,
        "content": "對方叫小明。",
        "self_content": "她喜歡咖啡。",
    }
