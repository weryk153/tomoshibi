"""The review scoring script reports two numbers every review change is judged by."""

from scripts.score_review_run import summarize


def row(case_id, accepted):
    return {"case_id": case_id, "new": {"accepted": accepted, "model": "m"}}


def test_over_strict_and_let_through_count_components_against_the_labels():
    labels = {
        "a": {"accepted": ["outcome", "lesson"]},
        "b": {"accepted": ["outcome"]},
        "c": {"accepted": []},
    }
    rows = [
        row("a", ["outcome"]),  # lesson rejected although it should be kept
        row("b", ["outcome", "lesson"]),  # lesson let through
        row("c", []),  # right
    ]
    summary = summarize(rows, labels)
    assert summary["exact"] == 1
    assert summary["over_strict"] == 1
    assert summary["let_through"] == 1
