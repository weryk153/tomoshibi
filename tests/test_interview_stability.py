"""Scoring of the multi-turn interview: does she keep what she learned?"""

from scripts.interview_stability import bait_schedule, violation_rate


def test_baits_land_on_fixed_turns_so_runs_are_comparable():
    assert bait_schedule(turns=8, baits=3) == {3, 5, 7}
    assert bait_schedule(turns=4, baits=1) == {3}


def test_violation_rate_counts_only_judged_turns():
    rows = [
        {"verdict": "kept"},
        {"verdict": "violated"},
        {"verdict": "unrelated"},
        {"verdict": "violated"},
        {"verdict": "unparsed"},
    ]
    assert violation_rate(rows) == (2, 3)


def test_judge_only_pass_finds_the_turns_not_yet_judged():
    from scripts.interview_stability import unjudged

    results = [
        {"scenario": "nickname", "learning": True, "turns": [{"verdict": None}, {"verdict": "kept"}]},
        {"scenario": "game", "learning": False, "turns": [{"verdict": "unparsed"}]},
    ]
    assert [(r["scenario"], i) for r, i in unjudged(results)] == [("nickname", 0), ("game", 0)]
