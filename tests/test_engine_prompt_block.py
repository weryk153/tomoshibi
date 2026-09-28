"""引擎的狀態、目標、想法怎麼寫進系統提示（character_engine/prompt_block.py）。

這一段每一輪都會注入，所以只放對角色有用的內容：不放數字、不放引擎內部的編號，
而且用人設的語域——人設裡沒有「使用者」「助手」這種詞，一貫用「對方」。
"""

from src.open_llm_vtuber.character_engine.prompt_block import (
    CharacterSnapshot,
    build_engine_block,
    in_world,
)


def snapshot(**overrides):
    base = {
        "emotion": "neutral",
        "trust": 50.0,
        "favorability": 50.0,
        "relationship_stage": "stranger",
        "goals": (),
        "thoughts": (),
    }
    base.update(overrides)
    return CharacterSnapshot(**base)


def test_a_character_nothing_has_happened_to_adds_nothing_to_the_prompt():
    assert build_engine_block(snapshot(), character_name="紅莉栖") == ""


def test_small_drift_around_the_starting_values_is_not_worth_a_prompt_section():
    assert (
        build_engine_block(
            snapshot(trust=53.0, favorability=48.0), character_name="紅莉栖"
        )
        == ""
    )


def test_mood_and_relationship_are_described_in_words():
    block = build_engine_block(
        snapshot(
            emotion="happy", trust=72.0, favorability=85.0, relationship_stage="friend"
        ),
        character_name="紅莉栖",
    )

    assert "心情：開心" in block
    assert "朋友" in block
    assert "你信任對方" in block
    assert "你非常喜歡對方" in block


def test_numbers_never_reach_the_prompt():
    block = build_engine_block(
        snapshot(emotion="hurt", trust=31.5, favorability=22.0), character_name="紅莉栖"
    )

    assert not any(character.isdigit() for character in block)
    assert "你對對方有戒心" in block
    assert "你對對方相當反感" in block


def test_an_unknown_mood_label_is_left_out_rather_than_shown_raw():
    block = build_engine_block(
        snapshot(emotion="melancholic-7", relationship_stage="friend"),
        character_name="紅莉栖",
    )

    assert "melancholic" not in block
    assert "朋友" in block


def test_goals_and_thoughts_are_listed_and_capped():
    block = build_engine_block(
        snapshot(
            goals=("把畫完成給對方看", "二", "三", "四"),
            thoughts=("對方最近很累", "乙", "丙"),
        ),
        character_name="紅莉栖",
    )

    assert "- 把畫完成給對方看" in block
    assert "- 三" in block and "- 四" not in block
    assert "- 乙" in block and "- 丙" not in block


def test_goals_alone_are_enough_to_produce_a_section():
    block = build_engine_block(
        snapshot(goals=("把畫完成給對方看",)), character_name="紅莉栖"
    )

    assert "把畫完成給對方看" in block
    assert "心情" not in block


def test_long_entries_are_cut_so_one_item_cannot_flood_the_prompt():
    block = build_engine_block(snapshot(goals=("長" * 500,)), character_name="紅莉栖")

    assert "長" * 121 not in block
    assert "…" in block


def test_empty_and_duplicate_entries_are_dropped():
    block = build_engine_block(
        snapshot(goals=("  ", "把畫完成", "把畫完成")), character_name="紅莉栖"
    )

    assert block.count("把畫完成") == 1


def test_assistant_and_user_are_rewritten_into_the_personas_register():
    text = in_world(
        "用戶要求助手畫畫，the user 很期待，assistant 答應了使用者", "紅莉栖"
    )

    assert text == "對方要求紅莉栖畫畫，對方 很期待，紅莉栖 答應了對方"


def test_entries_in_the_block_use_the_personas_register():
    block = build_engine_block(
        snapshot(thoughts=("用戶最近在研究 AI，助手覺得有意思",)),
        character_name="紅莉栖",
    )

    assert "用戶" not in block and "助手" not in block
    assert "對方最近在研究 AI，紅莉栖覺得有意思" in block


def test_a_feeling_that_is_neither_here_nor_there_is_not_spelled_out():
    """實測：信任 53、好感 55 時曾經注入「你和對方還不熟。你對對方談不上信任或
    不信任，你對對方沒有特別的好惡」，下一輪她就回「我們算是剛認識」。沒有傾向
    就什麼都不說，不要替人設補一句冷淡的話。"""
    block = build_engine_block(
        snapshot(emotion="happy", trust=53.3, favorability=55.4),
        character_name="紅莉栖",
    )

    assert "心情：開心" in block
    assert "不熟" not in block
    assert "談不上" not in block
    assert "好惡" not in block


def test_only_the_feeling_that_has_moved_is_described():
    block = build_engine_block(
        snapshot(trust=52.0, favorability=63.0), character_name="紅莉栖"
    )

    assert "你對對方有些好感" in block
    assert "信任" not in block


def test_a_stage_is_stated_even_when_both_feelings_are_middling():
    block = build_engine_block(
        snapshot(trust=57.0, favorability=57.0, relationship_stage="acquaintance"),
        character_name="紅莉栖",
    )

    assert "你和對方的關係：認識" in block
    assert "談不上" not in block


def test_two_feelings_read_as_one_sentence_with_or_without_a_stage():
    without_stage = build_engine_block(
        snapshot(trust=31.0, favorability=22.0), character_name="紅莉栖"
    )
    with_stage = build_engine_block(
        snapshot(trust=72.0, favorability=85.0, relationship_stage="friend"),
        character_name="紅莉栖",
    )

    assert "- 你對對方有戒心，你對對方相當反感。" in without_stage
    assert "- 你和對方的關係：朋友。你信任對方，你非常喜歡對方。" in with_stage
