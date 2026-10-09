"""回覆長度（全部角色共用）：每一輪的備註帶一句「這次回覆最多幾句」。

她常一次講 5–11 句，每句都要翻譯、合成，一輪要 40–100 秒才合成完，下一輪就跟著
排隊變慢。對照過：加「最多三句」三句裡兩句明顯變短。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import player_route, reply_length


def write_conf(path, extra=""):
    path.write_text("system_config:\n  host: '127.0.0.1'\n" + extra, encoding="utf-8")


def test_short_is_the_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_conf(tmp_path / "conf.yaml")
    assert reply_length.current() == "short"
    assert "最多三句" in reply_length.note()


def test_each_choice_has_its_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_conf(tmp_path / "conf.yaml", "  reply_length: 'medium'\n")
    assert "最多五句" in reply_length.note()
    write_conf(tmp_path / "conf.yaml", "  reply_length: 'free'\n")
    assert reply_length.note() == ""


def test_an_unknown_value_is_the_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_conf(tmp_path / "conf.yaml", "  reply_length: 'huge'\n")
    assert reply_length.current() == "short"


def test_saving_takes_effect_without_a_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_conf(tmp_path / "conf.yaml")
    monkeypatch.setattr(player_route, "_is_local_request", lambda request: True)
    app = FastAPI()
    app.include_router(player_route.init_player_route())
    http = TestClient(app)
    assert http.get("/api/reply-length").json() == {"length": "short"}
    saved = http.post("/api/reply-length", json={"length": "medium"}).json()
    assert saved == {"ok": True, "length": "medium", "restart_required": False}
    assert reply_length.current() == "medium"
    assert http.post("/api/reply-length", json={"length": "huge"}).status_code == 400
