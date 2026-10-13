"""Minecraft 模式的 REST。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import minecraft_route
from src.open_llm_vtuber.minecraft.controller import MinecraftError
from src.open_llm_vtuber.minecraft_route import init_minecraft_route


class FakeController:
    def __init__(self):
        self.live = False
        self.applied = []

    def status(self):
        return {
            "live": self.live,
            "connected": self.live,
            "in_game": False,
            "pending": 0,
            "health": None,
            "action": "",
            "current": None,
            "stopped_reason": None,
            "last_error": "",
        }

    def apply_settings(self, settings):
        self.applied.append(settings)

    async def start(self):
        if self.live:
            raise MinecraftError("already_live")
        self.live = True
        return self.status()

    async def stop(self):
        self.live = False
        return self.status()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(
        "system_config: {}\ncharacter_config: {}\n", encoding="utf-8"
    )
    monkeypatch.setattr(minecraft_route, "_is_trusted", lambda request: True)
    controller = FakeController()
    app = FastAPI()
    app.include_router(init_minecraft_route(controller))
    return TestClient(app), controller


def test_get_returns_settings_and_status(client):
    http, _ = client
    body = http.get("/api/minecraft").json()
    assert body["settings"]["bot_name"] == ""
    assert body["status"]["live"] is False


def test_settings_validation_and_apply(client):
    http, controller = client
    assert (
        http.post("/api/minecraft/settings", json={"bot_name": "frieren"}).status_code
        == 200
    )
    assert controller.applied[-1].bot_name == "frieren"
    assert (
        http.post("/api/minecraft/settings", json={"idle_seconds": 0}).status_code
        == 400
    )
    assert http.post("/api/minecraft/settings", json=[1]).status_code == 400


def test_start_and_stop(client):
    http, _ = client
    assert http.post("/api/minecraft/start").json()["live"] is True
    again = http.post("/api/minecraft/start")
    assert again.status_code == 409 and again.json()["error"] == "already_live"
    assert http.post("/api/minecraft/stop").json()["live"] is False


def test_untrusted_cannot_write(client, monkeypatch):
    http, _ = client
    monkeypatch.setattr(minecraft_route, "_is_trusted", lambda request: False)
    assert http.post("/api/minecraft/start").status_code == 403
    assert http.post("/api/minecraft/settings", json={}).status_code == 403
