"""角色狀態怎麼隨互動改變（character_engine/state_policy.py 的純函式規則）。

輸入是引擎提交的「使用者情緒觀察」，輸出是這一輪要套用的變化。規則不看情緒的
文字標籤——那是自由文字、什麼語言都可能——只看 valence（對方心情好不好）與
stance（對方怎麼對待角色）這兩個 -1 到 1 的數字。
"""

import pytest

from src.open_llm_vtuber.character_engine.state_policy import next_state_change


def observation(**overrides):
    base = {
        "emotion": "快樂",
        "intensity": 1.0,
        "confidence": 1.0,
        "valence": 0.0,
        "stance": 0.0,
        "proposal_id": "p1",
    }
    base.update(overrides)
    return base


def change(
    observed=None, *, trust=50.0, favorability=50.0, stage="stranger", applied=None
):
    return next_state_change(
        trust=trust,
        favorability=favorability,
        relationship_stage=stage,
        observation=observed,
        applied_observation_id=applied,
    )


def test_every_turn_builds_a_little_trust_even_without_an_observation():
    result = change(None)

    assert result.trust_delta == pytest.approx(0.3)
    assert result.favorability_delta == 0
    assert result.emotion is None
    assert result.applied_observation_id is None


def test_warmth_toward_her_raises_favorability_and_trust():
    result = change(observation(stance=1.0, valence=0.9))

    assert result.favorability_delta == pytest.approx(4.0)
    assert result.trust_delta == pytest.approx(0.3 + 2.0)
    assert result.emotion == "happy"
    assert result.applied_observation_id == "p1"


def test_hostility_toward_her_costs_more_trust_than_warmth_earns():
    result = change(observation(stance=-1.0, valence=-0.8))

    assert result.favorability_delta == pytest.approx(-4.0)
    assert result.trust_delta == pytest.approx(0.3 - 3.0)
    assert result.emotion == "hurt"


def test_a_bad_day_that_is_not_about_her_earns_trust_not_dislike():
    result = change(observation(stance=0.0, valence=-0.6, intensity=0.8))

    assert result.favorability_delta == 0
    assert result.trust_delta == pytest.approx(0.3 + 0.8)
    assert result.emotion == "concerned"


def test_strength_scales_with_intensity_and_confidence():
    result = change(observation(stance=1.0, intensity=0.5, confidence=0.5))

    assert result.favorability_delta == pytest.approx(1.0)


def test_an_unremarkable_turn_leaves_her_calm():
    assert change(observation(stance=0.1, valence=0.1)).emotion == "calm"


def test_the_same_observation_is_applied_only_once():
    result = change(observation(stance=1.0), applied="p1")

    assert result.favorability_delta == 0
    assert result.trust_delta == pytest.approx(0.3)
    assert result.emotion is None
    assert result.applied_observation_id is None


def test_an_observation_without_scores_changes_nothing_but_is_consumed():
    old_worker = {
        "emotion": "frustrated",
        "intensity": 0.8,
        "confidence": 0.9,
        "proposal_id": "p2",
    }

    result = change(old_worker)

    assert result.favorability_delta == 0
    assert result.trust_delta == pytest.approx(0.3)
    assert result.emotion is None
    assert result.applied_observation_id == "p2"


@pytest.mark.parametrize("garbage", ["high", None, float("nan"), True, [1]])
def test_unreadable_scores_are_treated_as_missing(garbage):
    result = change(observation(stance=garbage, valence=garbage))

    assert result.favorability_delta == 0
    assert result.emotion is None


@pytest.mark.parametrize(
    ("trust", "favorability", "expected"),
    [
        (50.0, 50.0, None),
        (60.0, 56.0, "acquaintance"),
        (70.0, 70.0, "friend"),
        (90.0, 80.0, "close"),
    ],
)
def test_relationship_stage_follows_the_average_of_trust_and_favorability(
    trust, favorability, expected
):
    assert (
        change(None, trust=trust, favorability=favorability).relationship_stage
        == expected
    )


def test_stage_does_not_drop_on_a_small_dip_below_its_threshold():
    just_below_friend = change(None, trust=66.0, favorability=66.0, stage="friend")

    assert just_below_friend.relationship_stage is None


def test_stage_drops_once_the_dip_is_clear():
    result = change(None, trust=60.0, favorability=62.0, stage="friend")

    assert result.relationship_stage == "acquaintance"


def test_stage_uses_the_values_after_this_turns_change():
    result = change(observation(stance=1.0), trust=57.0, favorability=56.0)

    assert result.relationship_stage == "acquaintance"


def test_an_unknown_stage_label_is_treated_as_the_lowest():
    assert (
        change(None, trust=70.0, favorability=70.0, stage="???").relationship_stage
        == "friend"
    )


def test_reacting_between_turns_does_not_count_as_another_turn():
    result = next_state_change(
        trust=50.0,
        favorability=50.0,
        relationship_stage="stranger",
        observation=observation(stance=1.0),
        applied_observation_id=None,
        count_turn=False,
    )

    assert result.trust_delta == pytest.approx(2.0)
    assert result.favorability_delta == pytest.approx(4.0)


def test_when_they_are_hurting_she_is_concerned_even_if_they_are_warm_to_her():
    """實測：「今天被老闆罵了一整天，好累，只想跟你說說話」是 stance 1、valence -0.4。
    對方是帶著信任來訴苦的——好感照漲，但她該擔心，不是開心。"""
    result = change(
        observation(stance=1.0, valence=-0.4, intensity=0.8, confidence=0.9)
    )

    assert result.emotion == "concerned"
    assert result.favorability_delta > 0
    assert result.trust_delta > 0.3
