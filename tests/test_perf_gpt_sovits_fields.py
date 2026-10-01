"""語音合成頁只管 GPT-SoVITS 服務在哪；誰用什麼聲音是角色的事。"""

import shutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import conf_editor, perf_route


@pytest.fixture
def conf(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    shutil.copy("config_templates/conf.tomoshibi.default.yaml", path)
    monkeypatch.setattr(conf_editor, "CONF_PATH", str(path))
    monkeypatch.setattr(perf_route, "CONF_PATH", str(path), raising=False)
    return path


def test_only_the_service_address_is_written(conf):
    before = conf.read_text("utf-8")
    perf_route._write_tts_service("http://127.0.0.1:9881")
    after = conf.read_text("utf-8")
    changed = [b for b, a in zip(before.splitlines(), after.splitlines()) if a != b]
    assert len(changed) == 1 and "api_url" in changed[0]


def test_character_voice_fields_are_refused(conf, monkeypatch):
    monkeypatch.setattr(perf_route, "_is_local_request", lambda r: True)
    app = FastAPI()
    app.include_router(perf_route.init_perf_route())
    r = TestClient(app).post("/api/perf/tts", json={"tts_model": "edge_tts"})
    assert r.status_code == 400


def test_reference_voices_come_from_every_character_and_the_installer(
    tmp_path, monkeypatch
):
    """參考音清單給角色頁挑聲音用：底稿、每個角色檔用到的資料夾，以及一鍵安裝
    附的參考音都要列出來。安裝不再改底稿的 ref_audio_path，只看底稿會漏掉它。"""
    from src.open_llm_vtuber import gpt_sovits_installer

    monkeypatch.chdir(tmp_path)
    mine = tmp_path / "my_refs"
    mine.mkdir()
    (mine / "kurisu.wav").write_bytes(b"")
    (mine / "kurisu.txt").write_text("こんにちは。", encoding="utf-8")
    installed = tmp_path / "gpt-sovits"
    (installed / "references").mkdir(parents=True)
    (installed / "references" / "tsukuyomi_ja.wav").write_bytes(b"")
    monkeypatch.setenv(gpt_sovits_installer.DIR_ENV, str(installed))
    (tmp_path / "conf.yaml").write_text(
        "character_config:\n  conf_uid: base\n", "utf-8"
    )
    monkeypatch.setattr(perf_route, "CONF_PATH", "conf.yaml", raising=False)
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "kurisu.yaml").write_text(
        "character_config:\n  tts_config:\n    gpt_sovits_tts:\n"
        f"      ref_audio_path: '{mine / 'kurisu.wav'}'\n",
        "utf-8",
    )

    labels = {voice["label"]: voice for voice in perf_route._reference_voices()}

    assert labels["kurisu"]["prompt_text"] == "こんにちは。"
    assert "tsukuyomi_ja" in labels
