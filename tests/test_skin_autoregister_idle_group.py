"""scan_and_register_skins() — 自動註冊時挑出來的 idleMotionGroupName。

一個動作群組的名字可以是空字串。這是合法的 Cubism，不是「沒有群組」——
mao_pro 就把六個動作全放在無名群組裡，而從 VTube Studio 匯出的模型（例如
Frieren）常常**只有**無名群組。

把空字串當成 falsy 濾掉，會讓自動註冊回退到預設值 "Idle"，指向一個模型裡
不存在的群組，待機動作就永遠不會播。live2d_config_route 的模組註解已經寫過
這條規則（"Never filter it out"），這裡把它釘成測試。

慣例同 tests/test_live2d_config_route.py：每個測試在 tmp_path 底下自己蓋一份
假的 live2d-models/ 與 model_dict.json，不碰真的那份。
"""

import json

from src.open_llm_vtuber.live2d_config_route import scan_and_register_skins


def _write_model3(tmp_path, folder, filename, *, motions):
    model_dir = tmp_path / "live2d-models" / folder
    model_dir.mkdir(parents=True, exist_ok=True)
    data = {"FileReferences": {"Motions": motions}, "HitAreas": []}
    (model_dir / filename).write_text(json.dumps(data), encoding="utf-8")


def _registered(tmp_path, name):
    entries = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    return next(e for e in entries if e.get("name") == name)


def test_model_with_only_unnamed_group_registers_that_group_as_idle(
    tmp_path, monkeypatch
):
    # Frieren 的實際形狀：兩個動作全在無名群組，沒有 Idle 也沒有 Talk。
    _write_model3(
        tmp_path,
        "Frieren",
        "Frieren.model3.json",
        motions={"": [{"File": "daiji.motion3.json"}, {"File": "zs1.motion3.json"}]},
    )
    (tmp_path / "model_dict.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    scan_and_register_skins()

    # "Idle" 在這個模型裡不存在，拿它當待機群組等於沒有待機動作。
    assert _registered(tmp_path, "Frieren")["idleMotionGroupName"] == ""


def test_named_idle_group_still_wins_over_unnamed(tmp_path, monkeypatch):
    # mao_pro 兩種都有，"Idle" 仍然要優先——修法不可以把這條吃掉。
    _write_model3(
        tmp_path,
        "mao_pro",
        "mao_pro.model3.json",
        motions={
            "": [{"File": "a.motion3.json"}],
            "Idle": [{"File": "idle.motion3.json"}],
        },
    )
    (tmp_path / "model_dict.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    scan_and_register_skins()

    assert _registered(tmp_path, "mao_pro")["idleMotionGroupName"] == "Idle"


def test_first_named_group_wins_when_there_is_no_idle(tmp_path, monkeypatch):
    # 這個模型沒有無名群組；有具名群組時就用第一個，行為不變。
    _write_model3(
        tmp_path,
        "compact_rig",
        "compact_rig.model3.json",
        motions={"Talk": [{"File": "talk.motion3.json"}]},
    )
    (tmp_path / "model_dict.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    scan_and_register_skins()

    assert _registered(tmp_path, "compact_rig")["idleMotionGroupName"] == "Talk"


def test_model_with_no_motions_at_all_falls_back_to_idle(tmp_path, monkeypatch):
    # 完全沒有動作時沒有更好的答案，維持既有的 "Idle" 預設值。
    _write_model3(tmp_path, "empty_model", "empty_model.model3.json", motions={})
    (tmp_path / "model_dict.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    scan_and_register_skins()

    assert _registered(tmp_path, "empty_model")["idleMotionGroupName"] == "Idle"
