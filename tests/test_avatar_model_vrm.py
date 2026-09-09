"""AvatarModel 吃 VRM 型的 model_dict 項目。

VRM 的 emotionMap 值是 expression preset 名（字串），motionMap 值是 {clip}。
AvatarModel 對值本來就不透明——只有 extract_motions 硬讀了 group/index，
那是唯一要分支的地方。Live2D 項目的行為一個位元都不能變。
"""

import json

import pytest

from src.open_llm_vtuber.avatar_model import AvatarModel


def _model(tmp_path, entry):
    path = tmp_path / "model_dict.json"
    path.write_text(json.dumps([entry]), encoding="utf-8")
    return AvatarModel(entry["name"], model_dict_path=str(path))


@pytest.fixture()
def vrm(tmp_path):
    return _model(
        tmp_path,
        {
            "name": "kurisu_vrm",
            "type": "vrm",
            "url": "/vrm-models/kurisu_vrm/kurisu_vrm.vrm",
            "emotionMap": {"neutral": "neutral", "joy": "happy", "anger": "angry"},
            "motionMap": {
                "wave": {"clip": "wave", "label": "揮手"},
                "nod": {"clip": "nod"},
            },
        },
    )


@pytest.fixture()
def live2d(tmp_path):
    return _model(
        tmp_path,
        {
            "name": "mao_pro",
            "emotionMap": {"neutral": 0, "joy": 3},
            "motionMap": {"special_01": {"group": "", "index": 3}},
        },
    )


def test_type_defaults_to_live2d(live2d, vrm):
    assert live2d.type == "live2d"
    assert vrm.type == "vrm"


def test_vrm_extract_emotion_returns_preset_names(vrm):
    assert vrm.extract_emotion("[joy] 你好 [anger]") == ["happy", "angry"]


def test_vrm_extract_motions_returns_clip(vrm):
    assert vrm.extract_motions("[wave] 嗨 [nod]") == [{"clip": "wave"}, {"clip": "nod"}]


def test_vrm_motion_str_uses_label(vrm):
    assert vrm.motion_str == "[wave]（揮手）, [nod],"


def test_live2d_extract_motions_unchanged(live2d):
    assert live2d.extract_motions("[special_01]") == [{"group": "", "index": 3}]


def test_model_info_carries_type(vrm):
    assert vrm.model_info["type"] == "vrm"
