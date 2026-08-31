"""GET/PUT /api/live2d/model-config/{name} 的表情那一半 —— 列出表情、命名情緒關鍵字。

在這之前 emotionMap 沒有任何 UI 也沒有 API：write_model_config 的 docstring
明講會原樣保留它，唯一的改法是手改 model_dict.json。手改的代價實際發生過——
model3.json 刪掉兩個表情之後索引整個往前位移，emotionMap 還指著舊索引，
`smirk` 就從「賊笑」變成「拿掉魔杖」，而且不會有任何錯誤訊息。

所以這裡的驗證重點跟動作那半一樣是「指向的東西真的存在嗎」，只是座標從
(group, index) 換成表情陣列的索引。

慣例同 tests/test_live2d_config_route.py：每個測試在 tmp_path 底下自己蓋一份
假的 live2d-models/ 與 model_dict.json，不碰真的那份。
"""

import json

from src.open_llm_vtuber.live2d_config_route import (
    build_model_config,
    write_model_config,
)


def _write_model3(tmp_path, folder, *, expressions=(), motions=None):
    model_dir = tmp_path / "live2d-models" / folder
    model_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "FileReferences": {
            "Motions": motions if motions is not None else {},
            "Expressions": [{"Name": n, "File": f"{n}.exp3.json"} for n in expressions],
        },
        "HitAreas": [],
    }
    (model_dir / f"{folder}.model3.json").write_text(json.dumps(data), encoding="utf-8")


def _write_model_dict(tmp_path, entries):
    (tmp_path / "model_dict.json").write_text(json.dumps(entries), encoding="utf-8")


def _entry(tmp_path, name):
    entries = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    return next(e for e in entries if e.get("name") == name)


def test_lists_every_expression_with_its_index(tmp_path, monkeypatch):
    _write_model3(tmp_path, "Frieren", expressions=["ku", "mmy", "anya"])
    _write_model_dict(tmp_path, [{"name": "Frieren", "emotionMap": {}}])
    monkeypatch.chdir(tmp_path)

    config = build_model_config("Frieren")

    assert [(e["name"], e["index"]) for e in config["expressions"]] == [
        ("ku", 0),
        ("mmy", 1),
        ("anya", 2),
    ]


def test_expression_carries_its_emotion_keyword(tmp_path, monkeypatch):
    _write_model3(tmp_path, "Frieren", expressions=["ku", "mmy", "anya"])
    _write_model_dict(tmp_path, [{"name": "Frieren", "emotionMap": {"sadness": 0}}])
    monkeypatch.chdir(tmp_path)

    by_index = {
        e["index"]: e["keywords"] for e in build_model_config("Frieren")["expressions"]
    }

    assert by_index[0] == ["sadness"]
    # 沒有人指向它的表情不是錯誤，只是還沒命名。
    assert by_index[1] == []


def test_two_keywords_on_one_expression_both_survive(tmp_path, monkeypatch):
    # 跟 motionMap 同一條規則：兩個關鍵字指向同一個目標是合法的。
    _write_model3(tmp_path, "Frieren", expressions=["ku", "mmy"])
    _write_model_dict(
        tmp_path, [{"name": "Frieren", "emotionMap": {"joy": 1, "smug": 1}}]
    )
    monkeypatch.chdir(tmp_path)

    by_index = {
        e["index"]: e["keywords"] for e in build_model_config("Frieren")["expressions"]
    }

    assert sorted(by_index[1]) == ["joy", "smug"]


def test_writes_emotion_map(tmp_path, monkeypatch):
    _write_model3(tmp_path, "Frieren", expressions=["ku", "mmy"])
    _write_model_dict(tmp_path, [{"name": "Frieren", "emotionMap": {"neutral": 0}}])
    monkeypatch.chdir(tmp_path)

    result = write_model_config(
        "Frieren", {}, {}, emotion_map={"sadness": 0, "smug": 1}
    )

    assert result["ok"] is True
    assert _entry(tmp_path, "Frieren")["emotionMap"] == {"sadness": 0, "smug": 1}


def test_omitting_emotion_map_leaves_it_untouched(tmp_path, monkeypatch):
    # 動作設定那半存檔時不會帶 emotionMap，不能因此把表情設定清掉。
    _write_model3(
        tmp_path,
        "Frieren",
        expressions=["ku"],
        motions={"": [{"File": "a.motion3.json"}]},
    )
    _write_model_dict(tmp_path, [{"name": "Frieren", "emotionMap": {"sadness": 0}}])
    monkeypatch.chdir(tmp_path)

    assert write_model_config("Frieren", {}, {})["ok"] is True

    assert _entry(tmp_path, "Frieren")["emotionMap"] == {"sadness": 0}


def test_rejects_keyword_pointing_at_missing_expression(tmp_path, monkeypatch):
    # 這正是手改 model_dict 出過的錯：索引位移之後指向不存在的表情。
    _write_model3(tmp_path, "Frieren", expressions=["ku", "mmy"])
    _write_model_dict(tmp_path, [{"name": "Frieren", "emotionMap": {}}])
    monkeypatch.chdir(tmp_path)

    result = write_model_config("Frieren", {}, {}, emotion_map={"joy": 9})

    assert result["ok"] is False
    assert result["status"] == 400
    assert "9" in result["error"]
    # 失敗就整個不寫，不可以留下半套。
    assert _entry(tmp_path, "Frieren")["emotionMap"] == {}


def test_rejects_case_insensitive_duplicate_keyword(tmp_path, monkeypatch):
    # live2d_model.py 建 emo_map 時把每個 key 轉小寫，Joy 和 joy 會併成一個，
    # 另一個變成永遠比不到的死設定。
    _write_model3(tmp_path, "Frieren", expressions=["ku", "mmy"])
    _write_model_dict(tmp_path, [{"name": "Frieren", "emotionMap": {}}])
    monkeypatch.chdir(tmp_path)

    result = write_model_config("Frieren", {}, {}, emotion_map={"Joy": 0, "joy": 1})

    assert result["ok"] is False
    assert result["status"] == 400


def test_rejects_non_integer_index(tmp_path, monkeypatch):
    _write_model3(tmp_path, "Frieren", expressions=["ku"])
    _write_model_dict(tmp_path, [{"name": "Frieren", "emotionMap": {}}])
    monkeypatch.chdir(tmp_path)

    result = write_model_config("Frieren", {}, {}, emotion_map={"joy": "0"})

    assert result["ok"] is False
    assert result["status"] == 400
