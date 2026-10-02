from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import persona_route, persona_store


def _client(tmp_path, monkeypatch):
    persona_dir = tmp_path / "personas"
    monkeypatch.setattr(persona_store, "PERSONAS_DIR", str(persona_dir))
    monkeypatch.setattr(
        persona_store, "STORE_PATH", str(persona_dir / "personas.json")
    )
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
