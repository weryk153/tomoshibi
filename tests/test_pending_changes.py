"""要重新載入才生效的設定，寫入後登記一筆；重新載入或換角色成功後清空。"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import pending_changes, pending_route


@pytest.fixture(autouse=True)
def _fresh():
    pending_changes.clear()
    yield
    pending_changes.clear()


def test_marks_are_kept_in_order_without_duplicates():
    pending_changes.mark("engine")
    pending_changes.mark("asr")
    pending_changes.mark("engine")
    assert pending_changes.pending() == ["engine", "asr"]
    pending_changes.clear()
    assert pending_changes.pending() == []


def test_the_route_lists_them():
    app = FastAPI()
    app.include_router(pending_route.init_pending_route())
    pending_changes.mark("tools")
    assert TestClient(app).get("/api/pending-changes").json() == {"pending": ["tools"]}


def test_saving_the_active_character_is_pending_but_another_is_not(
    tmp_path, monkeypatch
):
    from src.open_llm_vtuber import character_route, character_settings, conf_editor

    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(
        "character_config:\n  conf_uid: 'base'\n", "utf-8"
    )
    (tmp_path / "characters").mkdir()
    for name in ("a.yaml", "b.yaml"):
        (tmp_path / "characters" / name).write_text(
            f"character_config:\n  conf_uid: '{name[0]}'\n", "utf-8"
        )
    for module in (conf_editor, character_route, character_settings):
        monkeypatch.setattr(module, "CONF_PATH", "conf.yaml", raising=False)
    monkeypatch.setattr(character_route, "_is_local_request", lambda r: True)
    monkeypatch.setattr(
        character_route, "get_active_character_filename", lambda: "a.yaml"
    )
    app = FastAPI()
    app.include_router(character_route.init_character_route())
    client = TestClient(app)

    client.post("/api/characters/b.yaml/settings", json={"actions_enabled": True})
    assert pending_changes.pending() == []
    client.post("/api/characters/a.yaml/settings", json={"actions_enabled": True})
    assert pending_changes.pending() == ["character"]


class _Socket:
    def __init__(self):
        self.sent = []

    async def send_text(self, payload):
        self.sent.append(json.loads(payload))


def test_a_successful_reload_clears_the_list():
    from src.open_llm_vtuber.websocket_handler import WebSocketHandler

    async def ok_reload(socket):
        return True

    async def failed_reload(socket):
        return False

    async def load(_):
        return None

    h = WebSocketHandler.__new__(WebSocketHandler)
    h.default_context_cache = SimpleNamespace(
        active_config_file="conf.yaml", load_character_config=load
    )
    h.client_contexts = {"me": SimpleNamespace(handle_config_reload=failed_reload)}
    pending_changes.mark("engine")
    asyncio.run(h._handle_config_reload(_Socket(), "me", {}))
    assert pending_changes.pending() == ["engine"]
    h.client_contexts["me"].handle_config_reload = ok_reload
    asyncio.run(h._handle_config_reload(_Socket(), "me", {}))
    assert pending_changes.pending() == []


def test_a_successful_character_switch_clears_the_list():
    from src.open_llm_vtuber.websocket_handler import WebSocketHandler

    async def ok_switch(socket, name):
        return True

    h = WebSocketHandler.__new__(WebSocketHandler)
    h.client_contexts = {"me": SimpleNamespace(handle_config_switch=ok_switch)}
    pending_changes.mark("character")
    asyncio.run(h._handle_config_switch(_Socket(), "me", {"file": "a.yaml"}))
    assert pending_changes.pending() == []


def _put_client(tmp_path, monkeypatch, active):
    import yaml

    from src.open_llm_vtuber import character_route, conf_editor

    monkeypatch.chdir(tmp_path)
    base = {
        "conf_uid": "base",
        "conf_name": "底稿",
        "persona_prompt": "你是底稿。\n",
        "live2d_model_name": "mao_pro",
    }
    (tmp_path / "conf.yaml").write_text(
        yaml.safe_dump({"character_config": base}, allow_unicode=True), "utf-8"
    )
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "kurisu.yaml").write_text(
        yaml.safe_dump(
            {"character_config": {**base, "conf_uid": "kurisu", "conf_name": "紅莉栖"}},
            allow_unicode=True,
        ),
        "utf-8",
    )
    for module in (conf_editor, character_route):
        monkeypatch.setattr(module, "CONF_PATH", "conf.yaml", raising=False)
    monkeypatch.setattr(character_route, "_rescan_skins", lambda: None)
    monkeypatch.setattr(
        character_route, "_load_model_dict", lambda: [{"name": "mao_pro"}]
    )
    monkeypatch.setattr(character_route, "_is_local_request", lambda r: True)
    monkeypatch.setattr(
        character_route, "get_active_character_filename", lambda: active
    )
    app = FastAPI()
    app.include_router(character_route.init_character_route())
    return TestClient(app)


_EDIT = {
    "conf_name": "新名字",
    "persona_prompt": "改過了",
    "live2d_model_name": "mao_pro",
}


@pytest.mark.parametrize(
    "active,edited,expected",
    [
        ("kurisu.yaml", "kurisu.yaml", ["character"]),
        ("other.yaml", "kurisu.yaml", []),
        (None, "conf.yaml", ["character"]),  # 沒存過正在用的角色＝底稿角色
        ("kurisu.yaml", "conf.yaml", []),
    ],
)
def test_editing_a_whole_character_is_pending_only_when_she_is_active(
    tmp_path, monkeypatch, active, edited, expected
):
    client = _put_client(tmp_path, monkeypatch, active)
    response = client.put(f"/api/characters/{edited}", json=_EDIT)
    assert response.status_code == 200, response.text
    assert pending_changes.pending() == expected
