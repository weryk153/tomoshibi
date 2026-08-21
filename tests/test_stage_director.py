from src.open_llm_vtuber.stage_director import (
    build_stage_director_prompt,
    extract_stage_performance,
    normalize_stage_candidates,
    strip_stage_performance_tag,
)


def test_candidates_are_allowlisted_deduplicated_and_bounded():
    candidates = normalize_stage_candidates(
        [
            {"id": "kurisu-entry", "name": "Kurisu", "description": "Lab entrance"},
            {"id": "kurisu-entry", "name": "Duplicate"},
            {"id": "../../bad", "name": "Bad"},
            "not-an-object",
        ]
    )
    assert candidates == [
        {
            "id": "kurisu-entry",
            "name": "Kurisu",
            "description": "Lab entrance",
        }
    ]


def test_prompt_requires_optional_allowlisted_tag_at_reply_start():
    prompt = build_stage_director_prompt(
        [{"id": "kurisu-entry", "name": "Kurisu", "description": "Lab entrance"}]
    )
    assert "[stage:<preset_id>]" in prompt
    assert "kurisu-entry" in prompt
    assert "very beginning" in prompt
    assert "Omit the tag" in prompt


def test_extractor_accepts_only_frontend_allowlist():
    allowed = {"kurisu-entry"}
    assert (
        extract_stage_performance("[stage:kurisu-entry] Hello", allowed)
        == "kurisu-entry"
    )
    assert extract_stage_performance("[stage:invented] Hello", allowed) is None
    assert extract_stage_performance("No direction", allowed) is None
    assert extract_stage_performance("Hello [stage:kurisu-entry]", allowed) is None


def test_stage_tag_is_removed_before_assistant_memory():
    assert (
        strip_stage_performance_tag("[stage:kurisu-entry] Hello there.")
        == "Hello there."
    )
    assert strip_stage_performance_tag("Hello [stage:kurisu-entry]") == (
        "Hello [stage:kurisu-entry]"
    )
