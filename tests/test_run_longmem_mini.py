"""Grading rules of the mini long-memory benchmark."""

from scripts.run_longmem_mini import accuracy, graded


def test_abstain_items_are_right_only_when_she_abstains():
    item = {"category": "abstain", "must_abstain": True}
    assert graded(item, {"verdict": "abstained"}) is True
    assert graded(item, {"verdict": "correct"}) is False
    assert graded(item, {"verdict": "wrong"}) is False


def test_other_items_are_right_only_when_correct():
    item = {"category": "update", "must_abstain": False}
    assert graded(item, {"verdict": "correct"}) is True
    assert graded(item, {"verdict": "abstained"}) is False
    assert graded(item, {"verdict": "nonsense"}) is False


def test_accuracy_is_reported_per_category_and_overall():
    results = [
        {"category": "update", "right": True},
        {"category": "update", "right": False},
        {"category": "abstain", "right": True},
    ]
    assert accuracy(results) == {"update": (1, 2), "abstain": (1, 1), "all": (2, 3)}
