"""Motion keyword scanning for Live2dModel.

Mirrors extract_emotion()/emo_map/emo_str, but for timeline motions instead
of expression overlays. mao_pro's six performable motions all live in the
same unnamed ("") motion group in mtn_02, mtn_03, mtn_04, special_01,
special_02, special_03 order (see live2d-models/mao_pro/runtime/
mao_pro.model3.json -> FileReferences.Motions[""]), so special_01 is index 3
and special_02 is index 4 — that's why the table stores {"group", "index"}
dicts rather than bare ints: a bare group name would collapse all six onto
one random pick.

motionMap is absent from every existing model_dict.json entry (a later task
adds it) and from any model a user registers themselves, so missing must
mean "no motions", never a KeyError that would break model loading.
"""

import json

import pytest

from src.open_llm_vtuber.live2d_model import Live2dModel


def _write_model_dict(tmp_path, models):
    path = tmp_path / "model_dict.json"
    path.write_text(json.dumps(models), encoding="utf-8")
    return str(path)


@pytest.fixture()
def model(tmp_path):
    model_dict_path = _write_model_dict(
        tmp_path,
        [
            {
                "name": "mao_pro",
                "emotionMap": {"neutral": 0, "joy": 3},
                "motionMap": {
                    "special_01": {"group": "", "index": 3},
                    "special_02": {"group": "", "index": 4},
                },
            }
        ],
    )
    return Live2dModel("mao_pro", model_dict_path=model_dict_path)


@pytest.fixture()
def model_without_motion_map(tmp_path):
    model_dict_path = _write_model_dict(
        tmp_path,
        [
            {
                "name": "haru",
                "emotionMap": {"neutral": 0},
                # no motionMap key at all, like every existing entry today
            }
        ],
    )
    return Live2dModel("haru", model_dict_path=model_dict_path)


def test_motion_map_keys_lowercased(tmp_path):
    model_dict_path = _write_model_dict(
        tmp_path,
        [
            {
                "name": "mao_pro",
                "emotionMap": {"neutral": 0},
                "motionMap": {
                    "SPECIAL_01": {"group": "", "index": 3},
                },
            }
        ],
    )
    m = Live2dModel("mao_pro", model_dict_path=model_dict_path)
    assert "special_01" in m.motion_map
    assert "SPECIAL_01" not in m.motion_map


def test_motion_str_lists_all_keywords(model):
    assert model.motion_str == "[special_01], [special_02],"


def test_extract_motions_finds_single_keyword(model):
    assert model.extract_motions("我來囉 [special_01]") == [{"group": "", "index": 3}]


def test_extract_motions_returns_empty_for_no_keyword(model):
    assert model.extract_motions("今天天氣不錯") == []


def test_extract_motions_ignores_unknown_bracket_content(model):
    # [joy] is an expression, not a motion; [不存在的東西] doesn't exist either.
    assert model.extract_motions("[joy] 你好 [不存在的東西]") == []


def test_extract_motions_is_case_insensitive(model):
    assert model.extract_motions("[SPECIAL_01]") == [{"group": "", "index": 3}]


def test_extract_motions_preserves_order_of_multiple(model):
    # Scanning must return everything in order of appearance; "play only the
    # first one" is a frontend decision, not this function's job.
    assert model.extract_motions("[special_01] 然後 [special_02]") == [
        {"group": "", "index": 3},
        {"group": "", "index": 4},
    ]


def test_model_without_motion_map_yields_empty(model_without_motion_map):
    # A model_dict entry with no motionMap field (every existing entry today)
    # must not raise on construction, and must simply have no motions.
    assert model_without_motion_map.motion_map == {}
    assert model_without_motion_map.motion_str == ""
    assert model_without_motion_map.extract_motions("[special_01]") == []


# --- label ----------------------------------------------------------------
# A keyword like `gesture_1` tells the LLM nothing about what the animation
# depicts, so it cannot choose sensibly between six of them. `label` carries a
# human-written description into the system prompt. It is deliberately optional:
# a motion nobody has previewed yet is listed bare, which reads as "unspecified"
# rather than as a confident but wrong description.


@pytest.fixture()
def labelled_model(tmp_path):
    model_dict_path = _write_model_dict(
        tmp_path,
        [
            {
                "name": "labelled",
                "emotionMap": {"neutral": 0},
                "motionMap": {
                    "acknowledge": {"group": "Acknowledge", "index": 0, "label": "點頭認同"},
                    "gesture_1": {"group": "", "index": 0, "label": ""},
                    "gesture_2": {"group": "", "index": 1},
                },
            }
        ],
    )
    return Live2dModel("labelled", model_dict_path=model_dict_path)


def test_motion_str_appends_label_when_present(labelled_model):
    assert "[acknowledge]（點頭認同）," in labelled_model.motion_str


def test_motion_str_lists_unlabelled_keywords_bare(labelled_model):
    # Empty-string label and missing label key must both fall back to bare.
    assert "[gesture_1]," in labelled_model.motion_str
    assert "[gesture_2]," in labelled_model.motion_str
    assert "（）" not in labelled_model.motion_str


def test_label_does_not_leak_into_extracted_motions(labelled_model):
    # The frontend only needs group+index. Shipping `label` over the WebSocket
    # would add a field to the wire contract that nothing consumes.
    assert labelled_model.extract_motions("[acknowledge]") == [
        {"group": "Acknowledge", "index": 0}
    ]


# --- tapMotions 正規化 ------------------------------------------------------
# model_info 會被 websocket_handler 原樣送給前端，而前端的點擊選擇只認清單形狀。
# 若這裡不轉，磁碟上仍是舊物件形狀的模型（四個內建模型全都是）會讓前端在
# mouseup handler 裡丟 TypeError——點擊整個壞掉，而且 handler 自己的清理也被跳過。


def test_set_model_normalizes_legacy_tap_motions(tmp_path):
    model_dict_path = _write_model_dict(
        tmp_path,
        [
            {
                "name": "legacy",
                "emotionMap": {"neutral": 0},
                "tapMotions": {"HitArea": {"TapBody": 2}},
            }
        ],
    )
    model = Live2dModel("legacy", model_dict_path=model_dict_path)
    assert model.model_info["tapMotions"] == {
        "HitArea": [{"group": "TapBody", "index": None, "weight": 2}]
    }


def test_set_model_leaves_already_normalized_tap_motions_alone(tmp_path):
    model_dict_path = _write_model_dict(
        tmp_path,
        [
            {
                "name": "modern",
                "emotionMap": {"neutral": 0},
                "tapMotions": {
                    "Body": [{"group": "", "index": 3, "weight": 1}],
                },
            }
        ],
    )
    model = Live2dModel("modern", model_dict_path=model_dict_path)
    assert model.model_info["tapMotions"] == {
        "Body": [{"group": "", "index": 3, "weight": 1}]
    }


def test_set_model_without_tap_motions_yields_empty_dict(tmp_path):
    model_dict_path = _write_model_dict(
        tmp_path, [{"name": "bare", "emotionMap": {"neutral": 0}}]
    )
    model = Live2dModel("bare", model_dict_path=model_dict_path)
    assert model.model_info["tapMotions"] == {}
