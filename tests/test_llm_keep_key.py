"""只換模型時不用重貼金鑰：網址沒變、金鑰欄留空，就沿用已經存的那把。

網址變了就不沿用——舊金鑰不能送到使用者剛填的別的主機去。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ruamel.yaml import YAML

from src.open_llm_vtuber import conf_editor as ce
from src.open_llm_vtuber import llm_config_route as lc

CONF = """\
character_config:
  agent_config:
    agent_settings:
      conversation:
        llm_provider: 'openai_compatible_llm'
    llm_configs:
      openai_compatible_llm:
        base_url: 'https://openrouter.ai/api/v1'
        llm_api_key: 'sk-or-v1-saved'
        model: 'qwen/qwen3.8-27b:free'
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(lc, "CONF_PATH", str(path))
    monkeypatch.setattr(lc, "_is_local_request", lambda r: True)
    tried = []

    async def validate(base_url, model, api_key):
        tried.append((base_url, model, api_key))
        return True, ""

    monkeypatch.setattr(lc, "_validate_combo", validate)
    app = FastAPI()
    app.include_router(lc.init_llm_config_route())
    test_client = TestClient(app)
    test_client.tried = tried
    test_client.path = path
    return test_client


def _saved(path):
    return YAML(typ="safe").load(path.read_text("utf-8"))["character_config"][
        "agent_config"
    ]["llm_configs"]["openai_compatible_llm"]


def test_changing_only_the_model_keeps_the_saved_key(client):
    r = client.post(
        "/api/llm-config",
        json={
            "provider": "openai",
            "api_key": "",
            "model": "google/gemma-4-31b-it:free",
            "base_url": "https://openrouter.ai/api/v1/",
        },
    )
    assert r.status_code == 200
    assert client.tried == [
        (
            "https://openrouter.ai/api/v1/",
            "google/gemma-4-31b-it:free",
            "sk-or-v1-saved",
        )
    ]
    saved = _saved(client.path)
    assert saved["llm_api_key"] == "sk-or-v1-saved"
    assert saved["model"] == "google/gemma-4-31b-it:free"


def test_a_new_address_needs_the_key_again(client):
    r = client.post(
        "/api/llm-config",
        json={
            "provider": "openai",
            "api_key": "",
            "model": "gpt-x",
            "base_url": "https://evil.example.com/v1",
        },
    )
    assert r.status_code == 400
    assert client.tried == []
    assert _saved(client.path)["llm_api_key"] == "sk-or-v1-saved"
