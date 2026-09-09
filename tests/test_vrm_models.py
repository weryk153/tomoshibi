"""vrm-models/ 的掃描與 .vrm 的 GLB 讀取。

GLB = 12 bytes 標頭（magic 'glTF'、版本、總長）+ chunk（長度、型別 'JSON'、內容）。
表情名在 VRM 1.0 的 extensions.VRMC_vrm.expressions.{preset,custom}。
測試用 struct 現組最小 GLB，不依賴真的模型檔。
"""

import json
import struct

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
    d = tmp_path / "vrm-models" / "kurisu_vrm"
    (d / "motions").mkdir(parents=True)
    (d / "kurisu_vrm.vrm").write_bytes(_vrm1())
    (d / "motions" / "wave.vrma").write_bytes(b"")
    (d / "motions" / "idle.vrma").write_bytes(b"")
    (d / "thumbnail.png").write_bytes(b"")

    first = scan_and_register_vrm()
    assert first["newly_registered"] == ["kurisu_vrm"]
    assert first["skins"] == [
        {
            "name": "kurisu_vrm",
            "registered": True,
            "thumbnail": "/vrm-models/kurisu_vrm/thumbnail.png",
            "type": "vrm",
        }
    ]
    entries = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert entries == [
        {
            "name": "kurisu_vrm",
            "type": "vrm",
            "description": "自動偵測並註冊的 VRM 模型",
            "url": "/vrm-models/kurisu_vrm/kurisu_vrm.vrm",
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
