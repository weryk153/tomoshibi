from src.open_llm_vtuber.stage_director import (
    build_stage_director_prompt,
    extract_stage_performance,
    normalize_stage_candidates,
    strip_stage_performance_tag,
)


def test_candidates_are_allowlisted_deduplicated_and_bounded():
    candidates = normalize_stage_candidates(
        [
            {"id": "hero-entry", "name": "Hero", "description": "Grand entrance"},
            {"id": "hero-entry", "name": "Duplicate"},
            {"id": "../../bad", "name": "Bad"},
            "not-an-object",
        ]
    )
    assert candidates == [
        {
            "id": "hero-entry",
            "name": "Hero",
            "description": "Grand entrance",
        }
    ]


def test_prompt_requires_optional_allowlisted_tag_at_reply_start():
    prompt = build_stage_director_prompt(
        [{"id": "hero-entry", "name": "Hero", "description": "Grand entrance"}]
    )
    assert "[stage:<preset_id>]" in prompt
    assert "hero-entry" in prompt
    assert "very beginning" in prompt
    assert "Omit the tag" in prompt


def test_extractor_accepts_only_frontend_allowlist():
    allowed = {"hero-entry"}
    assert (
        extract_stage_performance("[stage:hero-entry] Hello", allowed) == "hero-entry"
    )
    assert extract_stage_performance("[stage:invented] Hello", allowed) is None
    assert extract_stage_performance("No direction", allowed) is None
    assert extract_stage_performance("Hello [stage:hero-entry]", allowed) is None


def test_stage_tag_is_removed_before_assistant_memory():
    assert (
        strip_stage_performance_tag("[stage:hero-entry] Hello there.") == "Hello there."
    )
    assert strip_stage_performance_tag("Hello [stage:hero-entry]") == (
        "Hello [stage:hero-entry]"
    )
