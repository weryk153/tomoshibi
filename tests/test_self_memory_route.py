"""self 記憶端點只以 conf_uid 為鍵，沒有連線也能讀寫；GET /api/memory 仍要連線。

用 FastAPI TestClient 打真的 router，conf_uid 驗證接縫（_resolve_conf_uid 用的
_existing_conf_uids）換成固定集合，檔案系統在 tmp_path。
"""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace

from src.open_llm_vtuber import memory_core
from src.open_llm_vtuber import memory_route as mr

CONF = "aoi"
HISTORY = "conv-1"


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


def _endpoint(router, path, method="POST"):
    """GET /api/memory 跟 POST /api/memory 的 path 一樣，只用 path 找會抓到
    先註冊的那個——一律也比對 method，才不會在 POST 端點上跑到 GET 的 handler。
    """
    for route in router.routes:
        if getattr(route, "path", None) != path:
            continue
        if method not in getattr(route, "methods", {method}):
            continue
        return route.endpoint
    raise AssertionError(f"找不到 {method} {path}")


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


@pytest.fixture()
def router_with_history(tmp_path, monkeypatch):
    """跟 router 一樣，但帶一個已連線的 context——對話記憶端點（/api/memory、
    /api/memory/clear）需要 history_uid 才能通過 _resolved_history_uid 的 409。
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mr, "_existing_conf_uids", lambda: {CONF})
    monkeypatch.setattr(mr, "_is_local_request", lambda _r: True)
    memory_core._consolidation_locks.clear()
    contexts = {
        "client-1": SimpleNamespace(
            character_config=SimpleNamespace(conf_uid=CONF), history_uid=HISTORY
        )
    }
    return mr.init_memory_route(contexts)


async def _while_consolidating(endpoint, body, read=None):
    """整理持鎖期間呼叫 endpoint，回傳 (鎖還握著時的檔案內容, 鎖放掉之後的內容)。"""
    read = read or (lambda: memory_core.load_self_memory(CONF))
    lock = memory_core._consolidation_lock(CONF)
    await lock.acquire()
    task = asyncio.create_task(endpoint(_FakeRequest(body)))
    for _ in range(5):
        await asyncio.sleep(0.01)  # 給 endpoint 足夠的機會跑到寫入
    during = read()
    lock.release()
    await task
    return during, read()


async def _while_lock_is_busy(endpoint, body, wait_timeout=2.0):
    """整理持著鎖、不放，一路撐過端點自己的等待上限；回傳端點的回應。

    endpoint 跟持鎖是同一個 coroutine 依序跑（不是分開的 task）：先拿鎖、
    再呼叫 endpoint，所以鎖永遠不會被放掉——這正是要測的情境（等到上限、
    誰都沒有要把鎖交出來）。外層另包一個 wait_for(wait_timeout) 是保險，
    不是被測的行為：端點自己若沒有等待上限會真的卡死，這裡讓測試在
    wait_timeout 秒後用 TimeoutError 失敗，而不是掛住整個測試行程。
    """
    lock = memory_core._consolidation_lock(CONF)
    await lock.acquire()
    try:
        return await asyncio.wait_for(
            endpoint(_FakeRequest(body)), timeout=wait_timeout
        )
    finally:
        lock.release()


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


# --- final fix wave 2 G1: 鎖等待要有上限，等不到回 503 -------------------------- #
#
# 整理持鎖跨整個 LLM 呼叫（最長 60 秒），前端 apiPost 逾時只有 15～20 秒。四個
# 寫入端點（save/clear、self/self-clear）原本要嘛完全沒進鎖（對話那兩個），要嘛
# 進鎖後沒有等待上限（self 那兩個）——後者會讓 HTTP 請求撐到前端自己斷線，畫面
# 報「請求逾時」，其實寫入已經在背後完成。四個都要在等到上限時明確回 503、
# 檔案完全不動；在上限內等到鎖就正常寫入。


def _body_json(resp):
    return json.loads(resp.body)


def test_self_save_returns_503_when_the_lock_wait_is_exceeded(router, monkeypatch):
    monkeypatch.setattr(mr, "_LOCK_WAIT_SECONDS", 0.05)
    memory_core.save_self_memory(CONF, "舊的。")
    resp = asyncio.run(
        _while_lock_is_busy(
            _endpoint(router, "/api/memory/self"),
            {"conf_uid": CONF, "content": "新的。"},
        )
    )
    assert resp.status_code == 503
    body = _body_json(resp)
    assert body["ok"] is False
    assert "幾秒後再試" in body["error"]
    assert memory_core.load_self_memory(CONF) == "舊的。"


def test_self_clear_returns_503_when_the_lock_wait_is_exceeded(router, monkeypatch):
    monkeypatch.setattr(mr, "_LOCK_WAIT_SECONDS", 0.05)
    memory_core.save_self_memory(CONF, "舊的。")
    resp = asyncio.run(
        _while_lock_is_busy(
            _endpoint(router, "/api/memory/self/clear"), {"conf_uid": CONF}
        )
    )
    assert resp.status_code == 503
    body = _body_json(resp)
    assert body["ok"] is False
    assert "幾秒後再試" in body["error"]
    assert memory_core.load_self_memory(CONF) == "舊的。"


def test_save_memory_waits_for_the_consolidation_lock(router_with_history):
    memory_core.save_core_memory(CONF, HISTORY, "舊的。")
    during, after = asyncio.run(
        _while_consolidating(
            _endpoint(router_with_history, "/api/memory"),
            {"conf_uid": CONF, "content": "新的。"},
            read=lambda: memory_core.load_core_memory(CONF, HISTORY),
        )
    )
    assert during == "舊的。", "整理還持著鎖，手動儲存不可以先寫進去"
    assert after == "新的。"


def test_save_memory_returns_503_when_the_lock_wait_is_exceeded(
    router_with_history, monkeypatch
):
    monkeypatch.setattr(mr, "_LOCK_WAIT_SECONDS", 0.05)
    memory_core.save_core_memory(CONF, HISTORY, "舊的。")
    resp = asyncio.run(
        _while_lock_is_busy(
            _endpoint(router_with_history, "/api/memory"),
            {"conf_uid": CONF, "content": "新的。"},
        )
    )
    assert resp.status_code == 503
    body = _body_json(resp)
    assert body["ok"] is False
    assert "幾秒後再試" in body["error"]
    assert memory_core.load_core_memory(CONF, HISTORY) == "舊的。"


def test_clear_memory_waits_for_the_consolidation_lock(router_with_history):
    memory_core.save_core_memory(CONF, HISTORY, "舊的。")
    during, after = asyncio.run(
        _while_consolidating(
            _endpoint(router_with_history, "/api/memory/clear"),
            {"conf_uid": CONF},
            read=lambda: memory_core.load_core_memory(CONF, HISTORY),
        )
    )
    assert during == "舊的。", "整理還持著鎖，手動清除不可以先寫進去"
    assert after == ""


def test_clear_memory_returns_503_when_the_lock_wait_is_exceeded(
    router_with_history, monkeypatch
):
    monkeypatch.setattr(mr, "_LOCK_WAIT_SECONDS", 0.05)
    memory_core.save_core_memory(CONF, HISTORY, "舊的。")
    resp = asyncio.run(
        _while_lock_is_busy(
            _endpoint(router_with_history, "/api/memory/clear"), {"conf_uid": CONF}
        )
    )
    assert resp.status_code == 503
    body = _body_json(resp)
    assert body["ok"] is False
    assert "幾秒後再試" in body["error"]
    assert memory_core.load_core_memory(CONF, HISTORY) == "舊的。"
