"""vrm-models/ 的掃描與 .vrm 的 GLB 讀取。

GLB = 12 bytes 標頭（magic 'glTF'、版本、總長）+ chunk（長度、型別 'JSON'、內容）。
表情名在 VRM 1.0 的 extensions.VRMC_vrm.expressions.{preset,custom}。
測試用 struct 現組最小 GLB，不依賴真的模型檔。
"""

import json
import struct

from loguru import logger

from src.open_llm_vtuber.vrm_models import (
    default_emotion_map,
    list_vrm_clips,
    read_vrm_expressions,
    scan_and_register_vrm,
)

JSON_CHUNK = 0x4E4F534A


def _glb(obj: dict) -> bytes:
    body = json.dumps(obj).encode("utf-8")
    body += b" " * ((4 - len(body) % 4) % 4)
    chunk = struct.pack("<II", len(body), JSON_CHUNK) + body
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunk)) + chunk


def _vrm1(preset=("neutral", "happy", "aa"), custom=("smug",)):
    return _glb(
        {
            "asset": {"version": "2.0"},
            "extensions": {
                "VRMC_vrm": {
                    "expressions": {
                        "preset": {p: {} for p in preset},
                        "custom": {c: {} for c in custom},
                    }
                }
            },
        }
    )


def _vrm0():
    return _glb({"asset": {"version": "2.0"}, "extensions": {"VRM": {}}})


def test_read_expressions_vrm1(tmp_path):
    p = tmp_path / "a.vrm"
    p.write_bytes(_vrm1())
    assert read_vrm_expressions(str(p)) == ["neutral", "happy", "aa", "smug"]


def test_read_expressions_vrm0_is_none(tmp_path):
    p = tmp_path / "a.vrm"
    p.write_bytes(_vrm0())
    assert read_vrm_expressions(str(p)) is None


def test_read_expressions_garbage_is_none(tmp_path):
    p = tmp_path / "a.vrm"
    p.write_bytes(b"not a glb")
    assert read_vrm_expressions(str(p)) is None


def test_read_expressions_non_dict_extensions_is_none(tmp_path):
    p = tmp_path / "a.vrm"
    p.write_bytes(_glb({"asset": {"version": "2.0"}, "extensions": "foo"}))
    assert read_vrm_expressions(str(p)) is None


def test_read_expressions_non_dict_expressions_is_empty(tmp_path):
    p = tmp_path / "a.vrm"
    p.write_bytes(
        _glb(
            {
                "asset": {"version": "2.0"},
                "extensions": {"VRMC_vrm": {"expressions": [1, 2]}},
            }
        )
    )
    assert read_vrm_expressions(str(p)) == []


def test_default_emotion_map_only_presets_present():
    assert default_emotion_map(["neutral", "happy", "aa", "smug"]) == {
        "neutral": "neutral",
        "joy": "happy",
    }


def test_default_emotion_map_unknown_is_neutral_only():
    assert default_emotion_map(None) == {"neutral": "neutral"}


def test_list_clips_sorted_excluding_idle(tmp_path):
    (tmp_path / "motions").mkdir()
    for n in ("wave.vrma", "idle.vrma", "Nod.vrma", "readme.txt"):
        (tmp_path / "motions" / n).write_bytes(b"")
    assert list_vrm_clips(str(tmp_path)) == ["Nod", "wave"]


def test_scan_registers_new_model_idempotently(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "model_dict.json").write_text("[]", encoding="utf-8")
    d = tmp_path / "vrm-models" / "my_vrm"
    (d / "motions").mkdir(parents=True)
    (d / "my_vrm.vrm").write_bytes(_vrm1())
    (d / "motions" / "wave.vrma").write_bytes(b"")
    (d / "motions" / "idle.vrma").write_bytes(b"")
    (d / "thumbnail.png").write_bytes(b"")

    first = scan_and_register_vrm()
    assert first["newly_registered"] == ["my_vrm"]
    assert first["skins"] == [
        {
            "name": "my_vrm",
            "registered": True,
            "thumbnail": "/vrm-models/my_vrm/thumbnail.png",
            "type": "vrm",
        }
    ]
    entries = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert entries == [
        {
            "name": "my_vrm",
            "type": "vrm",
            "description": "自動偵測並註冊的 VRM 模型",
            "url": "/vrm-models/my_vrm/my_vrm.vrm",
            "kScale": 1,
            "initialXshift": 0,
            "initialYshift": 0,
            "emotionMap": {"neutral": "neutral", "joy": "happy"},
            "tapMotions": {},
            "motionMap": {"wave": {"clip": "wave", "label": None}},
            "camera": {"distance": 1.6, "height": 1.35},
        }
    ]

    second = scan_and_register_vrm()
    assert second["newly_registered"] == []
    assert (
        json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
        == entries
    )


def test_scan_skips_folder_without_vrm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "model_dict.json").write_text("[]", encoding="utf-8")
    (tmp_path / "vrm-models" / "empty").mkdir(parents=True)
    assert scan_and_register_vrm() == {"skins": [], "newly_registered": []}


def test_scan_without_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "model_dict.json").write_text("[]", encoding="utf-8")
    assert scan_and_register_vrm() == {"skins": [], "newly_registered": []}


def test_list_all_skins_merges_live2d_and_vrm(tmp_path, monkeypatch):
    from src.open_llm_vtuber.live2d_config_route import list_all_skins

    monkeypatch.chdir(tmp_path)
    (tmp_path / "model_dict.json").write_text("[]", encoding="utf-8")
    l2d = tmp_path / "live2d-models" / "haru"
    l2d.mkdir(parents=True)
    (l2d / "Haru.model3.json").write_text(
        json.dumps({"FileReferences": {"Motions": {"Idle": [{}]}}}), encoding="utf-8"
    )
    v = tmp_path / "vrm-models" / "kv"
    v.mkdir(parents=True)
    (v / "kv.vrm").write_bytes(_vrm1())

    result = list_all_skins()
    assert [(s["name"], s["type"]) for s in result["skins"]] == [
        ("haru", "live2d"),
        ("kv", "vrm"),
    ]
    assert sorted(result["newly_registered"]) == ["haru", "kv"]


def _vrm_folder(
    tmp_path, name="kv", clips=("wave", "idle"), expressions=("neutral", "happy", "aa")
):
    d = tmp_path / "vrm-models" / name
    (d / "motions").mkdir(parents=True)
    (d / f"{name}.vrm").write_bytes(_vrm1(preset=expressions, custom=()))
    for c in clips:
        (d / "motions" / f"{c}.vrma").write_bytes(b"")
    return d


def test_build_vrm_model_config(tmp_path, monkeypatch):
    from src.open_llm_vtuber.vrm_models import build_vrm_model_config

    monkeypatch.chdir(tmp_path)
    _vrm_folder(tmp_path)
    entry = {
        "name": "kv",
        "type": "vrm",
        "url": "/vrm-models/kv/kv.vrm",
        "emotionMap": {"neutral": "neutral", "joy": "happy", "smug": "happy"},
        "motionMap": {
            "wave": {"clip": "wave", "label": "揮手"},
            "gone": {"clip": "nope"},
        },
    }
    assert build_vrm_model_config(entry) == {
        "name": "kv",
        "type": "vrm",
        "clips": [
            {
                "clip": "wave",
                "file": "motions/wave.vrma",
                "mappings": [{"keyword": "wave", "label": "揮手"}],
            }
        ],
        "expressions": [
            {"name": "neutral", "keywords": ["neutral"]},
            {"name": "happy", "keywords": ["joy", "smug"]},
            {"name": "aa", "keywords": []},
        ],
        "has_idle": True,
        "orphan_keywords": [{"keyword": "gone", "clip": "nope"}],
    }


def test_validate_vrm_motion_map():
    from src.open_llm_vtuber.vrm_models import validate_vrm_motion_map

    assert validate_vrm_motion_map({"wave": {"clip": "wave"}}, {"wave"}) is None
    assert "nope" in validate_vrm_motion_map({"x": {"clip": "nope"}}, {"wave"})
    assert "group" in validate_vrm_motion_map(
        {"x": {"group": "", "index": 0}}, {"wave"}
    )
    assert "duplicate" in validate_vrm_motion_map(
        {"Wave": {"clip": "wave"}, "wave": {"clip": "wave"}}, {"wave"}
    )


def test_validate_vrm_emotion_map():
    from src.open_llm_vtuber.vrm_models import validate_vrm_emotion_map

    assert validate_vrm_emotion_map({"joy": "happy"}, {"happy"}) is None
    assert "sad" in validate_vrm_emotion_map({"x": "sad"}, {"happy"})
    assert "string" in validate_vrm_emotion_map({"x": 3}, {"happy"})


def test_route_dispatches_on_type(tmp_path, monkeypatch):
    from src.open_llm_vtuber.live2d_config_route import (
        build_model_config,
        write_model_config,
    )

    monkeypatch.chdir(tmp_path)
    _vrm_folder(tmp_path)
    (tmp_path / "model_dict.json").write_text(
        json.dumps(
            [
                {
                    "name": "kv",
                    "type": "vrm",
                    "url": "/vrm-models/kv/kv.vrm",
                    "emotionMap": {"neutral": "neutral"},
                    "motionMap": {},
                    "tapMotions": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    assert build_model_config("kv")["type"] == "vrm"

    ok = write_model_config(
        "kv",
        {"wave": {"clip": "wave", "label": "揮手"}},
        {},
        emotion_map={"joy": "happy"},
    )
    assert ok == {"ok": True, "restart_required": False}
    saved = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))[0]
    assert saved["motionMap"] == {"wave": {"clip": "wave", "label": "揮手"}}
    assert saved["emotionMap"] == {"joy": "happy"}

    bad = write_model_config("kv", {"x": {"clip": "nope"}}, {})
    assert bad["ok"] is False and bad["status"] == 400

    tap = write_model_config("kv", {}, {"Head": []})
    assert tap["ok"] is False and "tapMotions" in tap["error"]


def test_read_expressions_lying_chunk_length_is_none(tmp_path):
    """chunk 標頭宣稱 0xFFFFFFFF、實際內容很短。

    沒有夾住的話 f.read(chunk_len) 會直接向 CPython 要 4 GiB 的 buffer；夾住之後
    只會讀到檔案真正剩下的那幾個 byte，JSON 解不開就照常回 None。
    """
    p = tmp_path / "a.vrm"
    body = b'{"asset": {"vers'  # 截斷的 JSON
    p.write_bytes(
        struct.pack("<4sII", b"glTF", 2, 20 + len(body))
        + struct.pack("<II", 0xFFFFFFFF, JSON_CHUNK)
        + body
    )
    assert read_vrm_expressions(str(p)) is None


def test_scan_warns_when_name_collides_with_live2d(tmp_path, monkeypatch, caplog):
    """live2d-models/x 與 vrm-models/x 同名時，VRM 那筆會被跳過——要留下痕跡。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "model_dict.json").write_text(
        json.dumps([{"name": "x"}], ensure_ascii=False), encoding="utf-8"
    )
    d = tmp_path / "vrm-models" / "x"
    d.mkdir(parents=True)
    (d / "x.vrm").write_bytes(_vrm1())

    sink = logger.add(caplog.handler, format="{message}", level="WARNING")
    try:
        result = scan_and_register_vrm()
    finally:
        logger.remove(sink)

    assert result["newly_registered"] == []
    assert [s["name"] for s in result["skins"]] == ["x"]
    entries = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert entries == [{"name": "x"}]
    assert "x" in caplog.text and "shadow" in caplog.text.lower()
