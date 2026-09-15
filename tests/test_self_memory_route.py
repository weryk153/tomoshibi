"""self 記憶端點只以 conf_uid 為鍵，沒有連線也能讀寫；GET /api/memory 仍要連線。

用 FastAPI TestClient 打真的 router，conf_uid 驗證接縫（_resolve_conf_uid 用的
_existing_conf_uids）換成固定集合，檔案系統在 tmp_path。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace

from src.open_llm_vtuber import memory_core
from src.open_llm_vtuber import memory_route as mr

CONF = "aoi"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mr, "_existing_conf_uids", lambda: {CONF})
    monkeypatch.setattr(mr, "_base_conf_uid", lambda: CONF)
    monkeypatch.setattr(mr, "_is_local_request", lambda _r: True)
    contexts = {}
    app = FastAPI()
    app.include_router(mr.init_memory_route(contexts))
    return TestClient(app), contexts


def test_self_save_and_read_without_any_connection(client):
    c, _ = client
    r = c.post("/api/memory/self", json={"conf_uid": CONF, "content": "她喜歡咖啡。"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["char_count"] == len("她喜歡咖啡。")
    assert body["cap"] == memory_core.SELF_CAP_CHARS
    assert body["restart_required"] is True
    assert memory_core.load_self_memory(CONF) == "她喜歡咖啡。"


def test_self_clear_without_any_connection(client):
    c, _ = client
    memory_core.save_self_memory(CONF, "x")
    r = c.post("/api/memory/self/clear", json={"conf_uid": CONF})
    assert r.status_code == 200
    assert r.json()["cleared"] is True
    assert memory_core.load_self_memory(CONF) == ""


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


def test_get_carries_self_fields_when_connected(client, monkeypatch):
    c, contexts = client
    # GET 會經 _character_setting → read_yaml(CONF_PATH) 讀開關與上限；換掉解析結果這個接縫
    monkeypatch.setattr(
        mr, "read_yaml", lambda _p: {"character_config": {"conf_uid": CONF}}
    )
    contexts["client-1"] = SimpleNamespace(
        character_config=SimpleNamespace(conf_uid=CONF), history_uid="conv-1"
    )
    memory_core.save_self_memory(CONF, "她喜歡咖啡。")
    memory_core.save_core_memory(CONF, "conv-1", "對方叫小明。")
    r = c.get(f"/api/memory?conf_uid={CONF}")
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "對方叫小明。"
    assert body["self_content"] == "她喜歡咖啡。"
    assert body["self_char_count"] == len("她喜歡咖啡。")
    assert body["self_cap"] == memory_core.SELF_CAP_CHARS
