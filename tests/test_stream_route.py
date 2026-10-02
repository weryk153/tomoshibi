"""直播分頁用的 REST。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import stream_route
from src.open_llm_vtuber.stream.controller import StreamError


class FakeController:
    def __init__(self):
        self.live = False
        self.started_with = []

    def status(self):
        return {"live": self.live}

    async def start(self, url=None):
        if url == "bad":
            raise StreamError("bad_url")
        self.started_with.append(url)
        self.live = True
        return self.status()

    async def stop(self):
        self.live = False
        return self.status()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text("system_config:\n  port: 1\n", "utf-8")
    monkeypatch.setattr(stream_route, "_is_trusted", lambda request: True)
    controller = FakeController()
    app = FastAPI()
    app.include_router(stream_route.init_stream_route(controller))
    test_client = TestClient(app)
    test_client.controller = controller
    return test_client


def test_get_returns_settings_and_status(client):
    body = client.get("/api/stream").json()
    assert body["settings"]["quiet_seconds"] == 30
    assert body["status"] == {"live": False}


def test_settings_are_saved_and_bad_ones_refused(client):
    r = client.post(
        "/api/stream/settings", json={"blocklist": ["笨蛋"], "quiet_seconds": 40}
    )
    assert r.status_code == 200
    assert r.json()["settings"]["blocklist"] == ["笨蛋"]
    assert client.get("/api/stream").json()["settings"]["quiet_seconds"] == 40
    bad = client.post("/api/stream/settings", json={"quiet_seconds": 0})
    assert bad.status_code == 400
    assert client.post("/api/stream/settings", json=["x"]).status_code == 400


def test_start_and_stop(client):
    started = client.post(
        "/api/stream/start", json={"url": "https://youtu.be/abcdefghijk"}
    )
    assert started.json() == {"live": True}
    assert client.controller.started_with == ["https://youtu.be/abcdefghijk"]
    assert client.post("/api/stream/stop").json() == {"live": False}
    r = client.post("/api/stream/start", json={"url": "bad"})
    assert r.status_code == 409
    assert r.json()["error"] == "bad_url"
    assert client.post("/api/stream/start").status_code == 200
    assert client.controller.started_with[-1] is None


def test_untrusted_requests_cannot_change_anything(client, monkeypatch):
    monkeypatch.setattr(stream_route, "_is_trusted", lambda request: False)
    assert client.post("/api/stream/start", json={}).status_code == 403
    assert client.post("/api/stream/stop").status_code == 403
    assert client.post("/api/stream/settings", json={}).status_code == 403
