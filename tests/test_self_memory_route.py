"""self 記憶端點只以 conf_uid 為鍵，沒有連線也能讀寫；GET /api/memory 仍要連線。

用 FastAPI TestClient 打真的 router，conf_uid 驗證接縫（_resolve_conf_uid 用的
_existing_conf_uids）換成固定集合，檔案系統在 tmp_path。
"""

import asyncio

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


# --- final fix wave F6: 手動儲存／清除要跟整理排同一把鎖 ----------------------
#
# 整理是「讀出兩份記憶 → 丟給 LLM（最久 60 秒）→ merge 寫回」。設定頁在鎖外寫檔
# 的話，整理若已經讀到舊的 self、使用者這時刪掉一行、60 秒後 merge 把舊內容寫
# 回去——被刪的行就復活了。而設定頁刪除正是規格對「分類誤判」這個已知漏洞唯一
# 的緩解手段，復活等於把那個手段拿掉。
#
# 這裡直接拿 router 上的 endpoint 函式來跑（不經 TestClient）：TestClient 自己
# 起一個事件迴圈跑請求，測試這一端拿不到那個迴圈，沒辦法在「整理持鎖中」這個
# 時間點上斷言。endpoint 只用到 request.json()，假物件就夠。


def _endpoint(router, path):
    for route in router.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"找不到 {path}")


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


@pytest.fixture()
def router(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mr, "_existing_conf_uids", lambda: {CONF})
    monkeypatch.setattr(mr, "_is_local_request", lambda _r: True)
    memory_core._consolidation_locks.clear()
    return mr.init_memory_route({})


async def _while_consolidating(endpoint, body):
    """整理持鎖期間呼叫 endpoint，回傳 (鎖還握著時的檔案內容, 鎖放掉之後的內容)。"""
    lock = memory_core._consolidation_lock(CONF)
    await lock.acquire()
    task = asyncio.create_task(endpoint(_FakeRequest(body)))
    for _ in range(5):
        await asyncio.sleep(0.01)  # 給 endpoint 足夠的機會跑到寫入
    during = memory_core.load_self_memory(CONF)
    lock.release()
    await task
    return during, memory_core.load_self_memory(CONF)


def test_self_save_waits_for_the_consolidation_lock(router):
    memory_core.save_self_memory(CONF, "舊的。")
    during, after = asyncio.run(
        _while_consolidating(
            _endpoint(router, "/api/memory/self"),
            {"conf_uid": CONF, "content": "新的。"},
        )
    )
    assert during == "舊的。", "整理還持著鎖，手動儲存不可以先寫進去"
    assert after == "新的。"


def test_self_clear_waits_for_the_consolidation_lock(router):
    memory_core.save_self_memory(CONF, "舊的。")
    during, after = asyncio.run(
        _while_consolidating(
            _endpoint(router, "/api/memory/self/clear"), {"conf_uid": CONF}
        )
    )
    assert during == "舊的。", "整理還持著鎖，手動清除不可以先寫進去"
    assert after == ""
