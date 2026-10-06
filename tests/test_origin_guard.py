"""跨站請求：別的網站不能趁你開著 app 改設定、或連上 WebSocket 跟她講話。

CORS 開著（*），而本機來的請求一律可信，所以任何網頁都能對 127.0.0.1:12393 送
POST（瀏覽器會照送，只是讀不到回應），例如把「允許區網連線」打開。瀏覽器送跨站
請求一定帶 Origin，所以看 Origin：是這個 app 自己的頁面才放行。
"""

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import pytest

from src.open_llm_vtuber.api_guard import origin_allowed
from src.open_llm_vtuber.origin_guard import install_origin_guard, websocket_origin_ok


@pytest.mark.parametrize(
    "origin, host, tailscale, expected",
    [
        (None, "127.0.0.1:12393", False, True),  # 不是瀏覽器（腳本、curl）
        ("http://127.0.0.1:12393", "127.0.0.1:12393", False, True),  # 同一個頁面
        ("http://192.168.1.114:12393", "192.168.1.114:12393", False, True),  # 區網手機
        ("http://localhost:5173", "127.0.0.1:12393", False, True),  # 前端開發伺服器
        ("http://[::1]:12393", "127.0.0.1:12393", False, True),
        ("https://evil.example", "127.0.0.1:12393", False, False),
        ("null", "127.0.0.1:12393", False, False),  # 沙箱 iframe
        ("http://127.0.0.1.evil.example", "127.0.0.1:12393", False, False),
        ("https://me.tail1234.ts.net", "127.0.0.1:12393", True, True),  # Tailscale Serve
        ("https://me.tail1234.ts.net", "127.0.0.1:12393", False, False),
    ],
)
def test_origin_allowed(origin, host, tailscale, expected):
    assert origin_allowed(origin, host, tailscale) is expected


def _app():
    app = FastAPI()
    install_origin_guard(app)

    @app.post("/api/network/host")
    async def set_host():
        return {"ok": True}

    @app.get("/api/network-info")
    async def info():
        return {"ok": True}

    @app.websocket("/client-ws")
    async def ws(websocket: WebSocket):
        if not await websocket_origin_ok(websocket):
            return
        await websocket.accept()
        await websocket.send_text("hi")
        await websocket.close()

    return TestClient(app)


def test_a_cross_site_post_is_refused():
    response = _app().post(
        "/api/network/host", json={}, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403


def test_the_apps_own_page_and_scripts_can_still_write():
    client = _app()
    assert client.post("/api/network/host", json={}).status_code == 200
    assert (
        client.post(
            "/api/network/host", json={}, headers={"Origin": "http://testserver"}
        ).status_code
        == 200
    )


def test_reads_are_not_blocked():
    response = _app().get("/api/network-info", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200


def test_a_cross_site_websocket_is_refused():
    client = _app()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/client-ws", headers={"Origin": "https://evil.example"}
        ) as ws:
            ws.receive_text()
    with client.websocket_connect("/client-ws", headers={"Origin": "http://testserver"}) as ws:
        assert ws.receive_text() == "hi"
