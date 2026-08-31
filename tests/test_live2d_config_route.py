"""GET/PUT /api/live2d/model-config/{name} — enumerate + persist motions/hit areas.

Tests call ``build_model_config``/``write_model_config`` directly (the router
endpoints are thin JSONResponse/404 wrappers around them) — same convention as
tests/test_character_fields.py and tests/test_llm_provider_write.py, which
call route-module helper functions rather than going through TestClient.

Every test builds a fake model folder + model_dict.json under tmp_path;
none of them touch the real live2d-models/ or model_dict.json.
"""

import json
from types import SimpleNamespace

from src.open_llm_vtuber.live2d_config_route import (
    build_model_config,
    write_model_config,
)
from src.open_llm_vtuber.live2d_model import Live2dModel


def _write_model3(tmp_path, folder, filename, *, motions=None, hit_areas=None):
    """Write a minimal .model3.json at <tmp_path>/live2d-models/<folder>/<filename>."""
    model_dir = tmp_path / "live2d-models" / folder
    model_dir.mkdir(parents=True, exist_ok=True)
    # HitAreas is a ROOT-level key in a real .model3.json, NOT under
    # FileReferences — verified against all four bundled models and against the
    # official Cubism Framework parser. Putting it under FileReferences here
    # would make these tests pass against an implementation that reads the wrong
    # place and returns [] for every real model.
    data = {
        "FileReferences": {"Motions": motions if motions is not None else {}},
        "HitAreas": hit_areas if hit_areas is not None else [],
    }
    (model_dir / filename).write_text(json.dumps(data), encoding="utf-8")


def _write_model_dict(tmp_path, entries):
    (tmp_path / "model_dict.json").write_text(json.dumps(entries), encoding="utf-8")


def test_lists_every_motion_group_and_index(tmp_path, monkeypatch):
    # mao_pro keeps all six of its usable motions in the unnamed ("") group —
    # that is legal Cubism, not a missing group. Anything that treats "" as
    # falsy/"no group" silently drops them.
    _write_model3(
        tmp_path,
        "mao_pro",
        "mao_pro.model3.json",
        motions={
            "Idle": [{"File": "motions/mtn_01.motion3.json"}],
            "": [
                {"File": "motions/mtn_02.motion3.json"},
                {"File": "motions/mtn_03.motion3.json"},
                {"File": "motions/special_01.motion3.json"},
            ],
        },
    )
    _write_model_dict(tmp_path, [{"name": "mao_pro", "idleMotionGroupName": "Idle"}])
    monkeypatch.chdir(tmp_path)

    result = build_model_config("mao_pro")

    assert result is not None
    keys = {(m["group"], m["index"]) for m in result["motions"]}
    assert keys == {("Idle", 0), ("", 0), ("", 1), ("", 2)}, (
        "the empty-string group must be listed like any other group"
    )
    special_01 = next(
        m for m in result["motions"] if m["group"] == "" and m["index"] == 2
    )
    assert special_01["file"] == "motions/special_01.motion3.json"


def test_lists_hit_areas_with_id_and_name(tmp_path, monkeypatch):
    _write_model3(
        tmp_path,
        "haru",
        "Haru.model3.json",
        hit_areas=[
            {"Id": "HitAreaHead", "Name": "Head"},
            {"Id": "HitAreaBody", "Name": "Body"},
        ],
    )
    _write_model_dict(tmp_path, [{"name": "haru"}])
    monkeypatch.chdir(tmp_path)

    result = build_model_config("haru")

    assert result["hit_areas"] == [
        {"id": "HitAreaHead", "name": "Head"},
        {"id": "HitAreaBody", "name": "Body"},
    ]


def test_merges_existing_motion_map(tmp_path, monkeypatch):
    _write_model3(
        tmp_path,
        "kurisu_fan",
        "kurisu.model3.json",
        motions={
            "Acknowledge": [{"File": "motions/nod.motion3.json"}],
        },
    )
    _write_model_dict(
        tmp_path,
        [
            {
                "name": "kurisu_fan",
                "motionMap": {
                    "acknowledge": {
                        "group": "Acknowledge",
                        "index": 0,
                        "label": "點頭認同",
                    }
                },
            }
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = build_model_config("kurisu_fan")

    motion = next(
        m for m in result["motions"] if m["group"] == "Acknowledge" and m["index"] == 0
    )
    assert motion["mappings"] == [{"keyword": "acknowledge", "label": "點頭認同"}]
    assert result["orphan_keywords"] == []


def test_motion_map_entry_pointing_at_missing_motion_is_flagged(tmp_path, monkeypatch):
    # The user hand-edited model_dict.json (or swapped the model file) so the
    # keyword now points at a (group, index) that doesn't exist anymore. This
    # must not be silently dropped — the UI needs it to show it's broken.
    _write_model3(
        tmp_path,
        "haru",
        "Haru.model3.json",
        motions={"TapBody": [{"File": "motions/tap_00.motion3.json"}]},
    )
    _write_model_dict(
        tmp_path,
        [
            {
                "name": "haru",
                "motionMap": {
                    "greet": {"group": "TapBody", "index": 5, "label": "打招呼"},
                    "ghost": {"group": "GoneNow", "index": 0, "label": "不存在的群組"},
                },
            }
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = build_model_config("haru")

    orphans = {
        (o["keyword"], o["group"], o["index"]) for o in result["orphan_keywords"]
    }
    assert orphans == {("greet", "TapBody", 5), ("ghost", "GoneNow", 0)}
    # And the real motion that DOES exist must not have picked up either
    # orphaned keyword.
    real_motion = next(
        m for m in result["motions"] if m["group"] == "TapBody" and m["index"] == 0
    )
    assert real_motion["mappings"] == []


def test_two_keywords_pointing_at_same_motion_both_survive(tmp_path, monkeypatch):
    # `label` lives on the KEYWORD in motionMap, not on the motion — two
    # different keywords can legitimately point at the same (group, index)
    # with two different labels. Both must round-trip, in motionMap order;
    # a singular "primary keyword" field would silently drop one.
    _write_model3(
        tmp_path,
        "kurisu_fan",
        "kurisu.model3.json",
        motions={"Acknowledge": [{"File": "motions/nod.motion3.json"}]},
    )
    _write_model_dict(
        tmp_path,
        [
            {
                "name": "kurisu_fan",
                "motionMap": {
                    "acknowledge": {
                        "group": "Acknowledge",
                        "index": 0,
                        "label": "點頭認同",
                    },
                    "nod_yes": {
                        "group": "Acknowledge",
                        "index": 0,
                        "label": "點頭表示同意",
                    },
                },
            }
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = build_model_config("kurisu_fan")

    motion = next(
        m for m in result["motions"] if m["group"] == "Acknowledge" and m["index"] == 0
    )
    assert motion["mappings"] == [
        {"keyword": "acknowledge", "label": "點頭認同"},
        {"keyword": "nod_yes", "label": "點頭表示同意"},
    ]


def test_legacy_tap_motions_object_shape_is_converted_to_list(tmp_path, monkeypatch):
    _write_model3(
        tmp_path, "haru", "Haru.model3.json", motions={"TapBody": [{"File": "a"}]}
    )
    _write_model_dict(
        tmp_path,
        [{"name": "haru", "tapMotions": {"HitArea": {"TapBody": 2}}}],
    )
    monkeypatch.chdir(tmp_path)

    result = build_model_config("haru")

    assert result["tap_motions"] == {
        "HitArea": [{"group": "TapBody", "index": None, "weight": 2}]
    }


def test_excludes_nothing_from_the_listing(tmp_path, monkeypatch):
    # Idle and Talk are used by the automatic pipeline, but exclusion is a UI
    # decision — the enumeration endpoint must still list them (flagged via
    # `reserved`).
    _write_model3(
        tmp_path,
        "kurisu_fan",
        "kurisu.model3.json",
        motions={
            "Idle": [{"File": "motions/idle_00.motion3.json"}],
            "Talk": [{"File": "motions/talk_00.motion3.json"}],
            "Signature": [{"File": "motions/sig_00.motion3.json"}],
        },
    )
    _write_model_dict(tmp_path, [{"name": "kurisu_fan", "idleMotionGroupName": "Idle"}])
    monkeypatch.chdir(tmp_path)

    result = build_model_config("kurisu_fan")

    groups_present = {m["group"] for m in result["motions"]}
    assert groups_present == {"Idle", "Talk", "Signature"}
    reserved_by_group = {m["group"]: m["reserved"] for m in result["motions"]}
    assert reserved_by_group["Idle"] is True
    assert reserved_by_group["Talk"] is True
    assert reserved_by_group["Signature"] is False


def test_unknown_model_name_returns_404(tmp_path, monkeypatch):
    _write_model_dict(tmp_path, [{"name": "haru"}])
    monkeypatch.chdir(tmp_path)

    assert build_model_config("does_not_exist") is None


# --------------------------------------------------------------------------- #
# PUT /api/live2d/model-config/{name} — write side
# --------------------------------------------------------------------------- #


def test_writes_only_the_named_model_entry(tmp_path, monkeypatch):
    _write_model3(
        tmp_path, "haru", "Haru.model3.json", motions={"Wave": [{"File": "a"}]}
    )
    _write_model_dict(
        tmp_path,
        [
            {
                "name": "haru",
                "emotionMap": {"neutral": 0},
                "kScale": 0.5,
                "description": "Haru desc",
                "url": "/live2d-models/haru/Haru.model3.json",
                "motionMap": {"old": {"group": "Wave", "index": 0, "label": "old"}},
            },
            {
                "name": "hiyori",
                "emotionMap": {"joy": 1},
                "kScale": 0.7,
                "description": "Hiyori desc",
                "url": "/live2d-models/hiyori/Hiyori.model3.json",
                "motionMap": {"greet": {"group": "TapBody", "index": 0, "label": "hi"}},
                "tapMotions": {"HitArea": {"TapBody": 3}},
            },
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = write_model_config(
        "haru",
        {"wave": {"group": "Wave", "index": 0, "label": "揮手"}},
        {},
    )

    assert result["ok"] is True

    on_disk = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    hiyori = next(e for e in on_disk if e["name"] == "hiyori")
    assert hiyori == {
        "name": "hiyori",
        "emotionMap": {"joy": 1},
        "kScale": 0.7,
        "description": "Hiyori desc",
        "url": "/live2d-models/hiyori/Hiyori.model3.json",
        "motionMap": {"greet": {"group": "TapBody", "index": 0, "label": "hi"}},
        "tapMotions": {"HitArea": {"TapBody": 3}},
    }, (
        "an untouched model's entry must be byte-identical, including its motionMap/tapMotions"
    )

    haru = next(e for e in on_disk if e["name"] == "haru")
    assert haru["motionMap"] == {"wave": {"group": "Wave", "index": 0, "label": "揮手"}}
    assert haru["emotionMap"] == {"neutral": 0}
    assert haru["kScale"] == 0.5
    assert haru["description"] == "Haru desc"
    assert haru["url"] == "/live2d-models/haru/Haru.model3.json"


def test_rejects_duplicate_keywords_within_a_model(tmp_path, monkeypatch):
    # Two DIFFERENT keywords pointing at the same (group, index) is fine.
    # The same keyword spelled with different case is not: live2d_model.py
    # lowercases every key when building motion_map, so "Wave" and "wave"
    # collide into one dict key and the scanner only ever sees whichever one
    # survives the collision — the other is dead config.
    _write_model3(
        tmp_path,
        "haru",
        "Haru.model3.json",
        motions={"Wave": [{"File": "a"}], "Nod": [{"File": "b"}]},
    )
    _write_model_dict(tmp_path, [{"name": "haru", "emotionMap": {"neutral": 0}}])
    monkeypatch.chdir(tmp_path)

    # Allowed: two distinct keywords, same target.
    ok = write_model_config(
        "haru",
        {
            "wave": {"group": "Wave", "index": 0, "label": "揮手"},
            "greet": {"group": "Wave", "index": 0, "label": "打招呼"},
        },
        {},
    )
    assert ok["ok"] is True

    # Rejected: same keyword, different case.
    bad = write_model_config(
        "haru",
        {
            "Wave": {"group": "Wave", "index": 0, "label": "揮手"},
            "wave": {"group": "Nod", "index": 0, "label": "點頭"},
        },
        {},
    )
    assert bad["ok"] is False
    assert bad["status"] == 400

    # The rejected write must not have overwritten the previously-good state.
    on_disk = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert on_disk[0]["motionMap"] == {
        "wave": {"group": "Wave", "index": 0, "label": "揮手"},
        "greet": {"group": "Wave", "index": 0, "label": "打招呼"},
    }


def test_rejects_motion_pointing_at_nonexistent_group_or_index(tmp_path, monkeypatch):
    _write_model3(
        tmp_path, "haru", "Haru.model3.json", motions={"Wave": [{"File": "a"}]}
    )
    _write_model_dict(tmp_path, [{"name": "haru", "emotionMap": {"neutral": 0}}])
    monkeypatch.chdir(tmp_path)

    bad_group = write_model_config(
        "haru", {"wave": {"group": "GoneNow", "index": 0, "label": "x"}}, {}
    )
    assert bad_group["ok"] is False
    assert bad_group["status"] == 400

    bad_index = write_model_config(
        "haru", {"wave": {"group": "Wave", "index": 5, "label": "x"}}, {}
    )
    assert bad_index["ok"] is False
    assert bad_index["status"] == 400

    # Nothing was written for either rejected attempt.
    on_disk = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert "motionMap" not in on_disk[0] or on_disk[0]["motionMap"] == {}


def test_empty_string_group_name_is_accepted_by_validation(tmp_path, monkeypatch):
    # mao_pro-style: the unnamed group is legal Cubism, not "missing". A
    # validator that does `if not group: reject` would break this.
    _write_model3(
        tmp_path,
        "mao_pro",
        "mao_pro.model3.json",
        motions={"": [{"File": "a"}, {"File": "b"}]},
    )
    _write_model_dict(tmp_path, [{"name": "mao_pro", "emotionMap": {"neutral": 0}}])
    monkeypatch.chdir(tmp_path)

    result = write_model_config(
        "mao_pro", {"wave": {"group": "", "index": 1, "label": "x"}}, {}
    )
    assert result["ok"] is True

    on_disk = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert on_disk[0]["motionMap"] == {"wave": {"group": "", "index": 1, "label": "x"}}


def test_rejects_tap_area_id_not_in_the_model(tmp_path, monkeypatch):
    _write_model3(
        tmp_path,
        "haru",
        "Haru.model3.json",
        motions={"Wave": [{"File": "a"}]},
        hit_areas=[{"Id": "HitAreaBody", "Name": "Body"}],
    )
    _write_model_dict(tmp_path, [{"name": "haru", "emotionMap": {"neutral": 0}}])
    monkeypatch.chdir(tmp_path)

    result = write_model_config(
        "haru",
        {},
        {"HitAreaHead": [{"group": "Wave", "index": 0, "weight": 1}]},
    )
    assert result["ok"] is False
    assert result["status"] == 400

    on_disk = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert "tapMotions" not in on_disk[0] or on_disk[0]["tapMotions"] == {}


def test_accepts_empty_maps(tmp_path, monkeypatch):
    # Clearing everything out is a legitimate operation.
    _write_model3(
        tmp_path, "haru", "Haru.model3.json", motions={"Wave": [{"File": "a"}]}
    )
    _write_model_dict(
        tmp_path,
        [
            {
                "name": "haru",
                "emotionMap": {"neutral": 0},
                "motionMap": {"wave": {"group": "Wave", "index": 0, "label": "x"}},
                "tapMotions": {"HitArea": {"Wave": 1}},
            }
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = write_model_config("haru", {}, {})
    assert result["ok"] is True

    on_disk = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert on_disk[0]["motionMap"] == {}
    assert on_disk[0]["tapMotions"] == {}


def test_write_refreshes_the_shared_live2d_model_in_place(tmp_path, monkeypatch):
    # websocket_handler.py hands every fresh session the SAME Live2dModel
    # object reference as default_context_cache.live2d_model. Calling
    # set_model() on it in place must make motion_map/motion_str reflect the
    # just-written config, with no restart and no character switch.
    _write_model3(
        tmp_path, "haru", "Haru.model3.json", motions={"Wave": [{"File": "a"}]}
    )
    _write_model_dict(
        tmp_path, [{"name": "haru", "emotionMap": {"neutral": 0}, "motionMap": {}}]
    )
    monkeypatch.chdir(tmp_path)

    shared_model = Live2dModel("haru")  # reads tmp_path/model_dict.json (cwd-relative)
    assert shared_model.motion_map == {}
    fake_cache = SimpleNamespace(live2d_model=shared_model)

    result = write_model_config(
        "haru",
        {"wave": {"group": "Wave", "index": 0, "label": "揮手"}},
        {},
        default_context_cache=fake_cache,
        client_contexts={},
    )

    assert result["ok"] is True
    assert result["restart_required"] is False
    assert shared_model.motion_map == {
        "wave": {"group": "Wave", "index": 0, "label": "揮手"}
    }
    assert "wave" in shared_model.motion_str


def test_write_does_not_touch_sessions_using_a_different_model(tmp_path, monkeypatch):
    _write_model3(
        tmp_path, "haru", "Haru.model3.json", motions={"Wave": [{"File": "a"}]}
    )
    _write_model3(
        tmp_path, "hiyori", "Hiyori.model3.json", motions={"Nod": [{"File": "b"}]}
    )
    _write_model_dict(
        tmp_path,
        [
            {"name": "haru", "emotionMap": {"neutral": 0}, "motionMap": {}},
            {"name": "hiyori", "emotionMap": {"neutral": 0}, "motionMap": {}},
        ],
    )
    monkeypatch.chdir(tmp_path)

    haru_model = Live2dModel("haru")
    other_session_model = Live2dModel("hiyori")
    fake_cache = SimpleNamespace(live2d_model=haru_model)
    fake_client_contexts = {
        "session-1": SimpleNamespace(live2d_model=other_session_model),
    }

    result = write_model_config(
        "haru",
        {"wave": {"group": "Wave", "index": 0, "label": "揮手"}},
        {},
        default_context_cache=fake_cache,
        client_contexts=fake_client_contexts,
    )

    assert result["ok"] is True
    assert haru_model.motion_map == {
        "wave": {"group": "Wave", "index": 0, "label": "揮手"}
    }
    # The session on a different model must be left completely alone.
    assert other_session_model.motion_map == {}


def test_write_refreshes_a_sessions_own_live2d_model_instance(tmp_path, monkeypatch):
    # A session that did a character switch holds its OWN Live2dModel
    # instance (not shared with default_context_cache) — it must still be
    # refreshed when it's showing the model that was just edited.
    _write_model3(
        tmp_path, "haru", "Haru.model3.json", motions={"Wave": [{"File": "a"}]}
    )
    _write_model_dict(
        tmp_path, [{"name": "haru", "emotionMap": {"neutral": 0}, "motionMap": {}}]
    )
    monkeypatch.chdir(tmp_path)

    default_model = Live2dModel("haru")
    own_model = Live2dModel("haru")  # a distinct instance, same model name
    assert default_model is not own_model

    result = write_model_config(
        "haru",
        {"wave": {"group": "Wave", "index": 0, "label": "揮手"}},
        {},
        default_context_cache=SimpleNamespace(live2d_model=default_model),
        client_contexts={"session-1": SimpleNamespace(live2d_model=own_model)},
    )

    assert result["ok"] is True
    assert default_model.motion_map == {
        "wave": {"group": "Wave", "index": 0, "label": "揮手"}
    }
    assert own_model.motion_map == {
        "wave": {"group": "Wave", "index": 0, "label": "揮手"}
    }


def test_write_is_atomic_and_preserves_unrelated_keys(tmp_path, monkeypatch):
    _write_model3(
        tmp_path, "haru", "Haru.model3.json", motions={"Wave": [{"File": "a"}]}
    )
    _write_model_dict(
        tmp_path,
        [
            {
                "name": "haru",
                "emotionMap": {"neutral": 0, "joy": 1},
                "kScale": 0.42,
                "description": "d",
                "url": "/live2d-models/haru/Haru.model3.json",
                "someFutureField": {"nested": True},
            }
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = write_model_config(
        "haru", {"wave": {"group": "Wave", "index": 0, "label": "x"}}, {}
    )
    assert result["ok"] is True

    on_disk = json.loads((tmp_path / "model_dict.json").read_text(encoding="utf-8"))
    assert len(on_disk) == 1
    entry = on_disk[0]
    assert entry["emotionMap"] == {"neutral": 0, "joy": 1}
    assert entry["kScale"] == 0.42
    assert entry["description"] == "d"
    assert entry["url"] == "/live2d-models/haru/Haru.model3.json"
    assert entry["someFutureField"] == {"nested": True}
    assert entry["motionMap"] == {"wave": {"group": "Wave", "index": 0, "label": "x"}}


def test_unknown_model_name_returns_404_on_write(tmp_path, monkeypatch):
    _write_model_dict(tmp_path, [{"name": "haru", "emotionMap": {"neutral": 0}}])
    monkeypatch.chdir(tmp_path)

    result = write_model_config("does_not_exist", {}, {})
    assert result["ok"] is False
    assert result["status"] == 404


def test_unhashable_index_does_not_crash(tmp_path, monkeypatch):
    """A hand-edited `"index": [0]` must land in orphan_keywords, not 500.

    `index` is part of a dict/set key. An unhashable value raises TypeError
    before any parsing guard can catch it, which would make the settings page
    -- the very tool for repairing a broken model_dict.json -- refuse to open.
    """
    _write_model3(
        tmp_path, "toy", "toy.model3.json", motions={"": [{"File": "a.motion3.json"}]}
    )
    _write_model_dict(
        tmp_path,
        [
            {
                "name": "toy",
                "url": "/live2d-models/toy/toy.model3.json",
                "motionMap": {
                    "broken_list": {"group": "", "index": [0], "label": "壞掉的"},
                    "broken_dict": {"group": "", "index": {}, "label": "也壞掉"},
                    "broken_group": {
                        "group": ["x"],
                        "index": 0,
                        "label": "群組型別壞掉",
                    },
                    "ok": {"group": "", "index": 0, "label": "好的"},
                },
            }
        ],
    )
    monkeypatch.chdir(tmp_path)

    result = build_model_config("toy")

    assert {o["keyword"] for o in result["orphan_keywords"]} == {
        "broken_list",
        "broken_dict",
        "broken_group",
    }
    assert result["motions"][0]["mappings"] == [{"keyword": "ok", "label": "好的"}]


def test_hit_areas_are_read_from_the_root_not_file_references(tmp_path, monkeypatch):
    """HitAreas is a ROOT-level key in .model3.json.

    The official Cubism Framework reads it with
    getRoot().getValueByString("HitAreas") (cubismmodelsettingjson.ts), and all
    four bundled models put it there. An implementation reading
    FileReferences.HitAreas returns [] for every real model -- the tap-area UI
    would show nothing and tap-area validation would reject every valid Id.
    """
    model_dir = tmp_path / "live2d-models" / "toy"
    model_dir.mkdir(parents=True)
    (model_dir / "toy.model3.json").write_text(
        json.dumps(
            {
                "FileReferences": {
                    "Motions": {"": [{"File": "a.motion3.json"}]},
                    # A decoy in the wrong place: must be ignored entirely.
                    "HitAreas": [{"Id": "WrongPlace", "Name": "nope"}],
                },
                "HitAreas": [{"Id": "Body", "Name": "Body"}],
            }
        ),
        encoding="utf-8",
    )
    _write_model_dict(
        tmp_path, [{"name": "toy", "url": "/live2d-models/toy/toy.model3.json"}]
    )
    monkeypatch.chdir(tmp_path)

    result = build_model_config("toy")

    assert result["hit_areas"] == [{"id": "Body", "name": "Body"}]
