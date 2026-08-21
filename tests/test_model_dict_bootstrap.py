"""model_dict.json 是使用者狀態，不是隨附檔案。

live2d_config_route 會在使用者調動作對應或點擊區時改寫 model_dict.json。
它同時又被 git 追蹤，於是每次在 UI 裡設定都會冒出一筆 git 修改——順手
commit 就把本機的模型（可能是有版權的角色）寫進 repo。

改成跟 conf.yaml 同一個模式：隨附的是 config_templates/model_dict.default.json，
使用者的 model_dict.json 首次讀取時才產生，且不進版控。
"""

import json

from src.open_llm_vtuber import character_route


def _write_default(tmp_path, entries):
    d = tmp_path / "config_templates"
    d.mkdir(exist_ok=True)
    (d / "model_dict.default.json").write_text(
        json.dumps(entries, ensure_ascii=False), encoding="utf-8"
    )


def test_seeds_user_file_from_default_on_first_read(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_default(tmp_path, [{"name": "mao_pro", "url": "/live2d-models/mao_pro"}])

    entries = character_route._load_model_dict()

    assert [e["name"] for e in entries] == ["mao_pro"]
    assert (tmp_path / "model_dict.json").exists(), "首次讀取要把預設複製成使用者的那份"


def test_does_not_overwrite_an_existing_user_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_default(tmp_path, [{"name": "mao_pro"}])
    (tmp_path / "model_dict.json").write_text(
        json.dumps([{"name": "my_own_model"}], ensure_ascii=False), encoding="utf-8"
    )

    entries = character_route._load_model_dict()

    assert [e["name"] for e in entries] == ["my_own_model"], (
        "使用者自己的設定不能被預設蓋掉"
    )


def test_returns_empty_when_neither_file_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert character_route._load_model_dict() == []
    assert not (tmp_path / "model_dict.json").exists(), "沒有預設可抄時不該憑空造檔"
