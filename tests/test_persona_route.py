from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import persona_route, persona_store


def _client(tmp_path, monkeypatch):
    persona_dir = tmp_path / "personas"
    monkeypatch.setattr(persona_store, "PERSONAS_DIR", str(persona_dir))
    monkeypatch.setattr(persona_store, "STORE_PATH", str(persona_dir / "personas.json"))
    monkeypatch.setattr(persona_route, "_is_local_request", lambda request: True)
    app = FastAPI()
    app.include_router(persona_route.init_persona_route())
    return TestClient(app)


def test_choosing_a_persona_for_one_character_leaves_the_others_alone(
    tmp_path, monkeypatch
):
    client = _client(tmp_path, monkeypatch)
    persona = persona_store.create_persona("溫柔", "她說話很溫柔。")
    persona_store.set_active_persona("frieren", None)

    response = client.put(
        "/api/personas/active",
        json={"conf_uid": "himmel", "persona_id": persona["id"]},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "active_persona_id": persona["id"]}
    assert persona_store.get_active_persona_id("himmel") == persona["id"]
    assert persona_store.get_active_persona_id("frieren") is None


def test_null_goes_back_to_the_characters_own_persona(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    persona = persona_store.create_persona("溫柔", "她說話很溫柔。")
    persona_store.set_active_persona("himmel", persona["id"])

    response = client.put(
        "/api/personas/active", json={"conf_uid": "himmel", "persona_id": None}
    )

    assert response.status_code == 200
    assert persona_store.get_active_persona_id("himmel") is None


def test_unknown_persona_and_missing_character_are_refused(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    unknown = client.put(
        "/api/personas/active", json={"conf_uid": "himmel", "persona_id": "nope"}
    )
    blank = client.put(
        "/api/personas/active", json={"conf_uid": "  ", "persona_id": None}
    )

    assert unknown.status_code == 404
    assert blank.status_code == 400
    assert persona_store.get_active_persona_id("himmel") is None


def test_a_persona_never_gets_the_id_the_choose_route_uses(tmp_path, monkeypatch):
    # PUT /api/personas/active 是「替角色選人設」；人設的 id 若是 active，就再也
    # 編輯不到它（PUT /api/personas/active 會被選人設的路由接走）。
    client = _client(tmp_path, monkeypatch)
    by_name = persona_store.create_persona("Active", "名字剛好是 active。")
    by_id = persona_store.create_persona("另一個", "直接要 active 當 id。", "active")

    assert by_name["id"] != "active"
    assert by_id["id"] != "active"
    response = client.put(
        f"/api/personas/{by_name['id']}", json={"name": "改名", "prompt": "改了。"}
    )
    assert response.status_code == 200
