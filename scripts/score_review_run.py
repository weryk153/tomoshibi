"""Score one or more review replay runs against the reference labels.

    .venv/bin/python scripts/score_review_run.py <run dir> [<run dir> ...] [--labels <json>]

A run dir is an output of scripts/compare_review_policies.py. The labels file
(default docs/superpowers/eval/review-labels-2026-10-15.json) names, per case,
the components that should be accepted. For each run this prints: exact match
rate over the 47 cases; outcome and lesson decisions as accept/reject
confusion counts; and, for a checklist run, how often each question answered
yes, how many of those yeses could cite the text, and how each question's
verified yeses line up with the label.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = ROOT / "docs/superpowers/eval/review-labels-2026-10-15.json"


def decisions(accepted: list[str]) -> dict[str, bool]:
    return {"outcome": "outcome" in accepted, "lesson": "lesson" in accepted}


def summarize(rows: list[dict], labels: dict) -> dict:
    """Exact matches, components rejected that the label keeps (over_strict) and
    components accepted that the label rejects (let_through), plus the
    accept/reject confusion per component and the missed cases."""
    exact = 0
    confusion = {c: Counter() for c in ("outcome", "lesson")}
    misses = []
    parse_errors = 0
    for row in rows:
        label = labels.get(row["case_id"])
        if label is None:
            continue
        got, want = decisions(row["new"]["accepted"] or []), decisions(label["accepted"])
        if got == want:
            exact += 1
        else:
            misses.append((row["case_id"], label["accepted"], row["new"]["accepted"]))
        for component in confusion:
            confusion[component][(want[component], got[component])] += 1
        if "parse_error" in (row["new"].get("review") or {}):
            parse_errors += 1
        for entry in (row["new"].get("checklist") or {}).values():
            if "parse_error" in entry:
                parse_errors += 1
    return {
        "exact": exact,
        "over_strict": sum(c[(True, False)] for c in confusion.values()),
        "let_through": sum(c[(False, True)] for c in confusion.values()),
        "confusion": confusion,
        "misses": misses,
        "parse_errors": parse_errors,
    }


def score(run: Path, labels: dict) -> None:
    rows = json.loads((run / "review-comparison.json").read_text())
    print(f"\n=== {run.name}: {len(rows)} cases, model {rows[0]['new']['model']}")
    summary = summarize(rows, labels)
    exact, confusion, misses = summary["exact"], summary["confusion"], summary["misses"]
    print(
        f"exact match {exact}/{len(rows)}   over_strict {summary['over_strict']}"
        f"   let_through {summary['let_through']}   parse errors {summary['parse_errors']}"
    )
    for component, counts in confusion.items():
        tp, fn = counts[(True, True)], counts[(True, False)]
        fp, tn = counts[(False, True)], counts[(False, False)]
        print(
            f"{component:8s} should-accept {tp + fn:2d}: accepted {tp:2d}, rejected {fn:2d} (over-strict)"
            f" | should-reject {fp + tn:2d}: rejected {tn:2d}, accepted {fp:2d} (let through)"
        )
    if misses:
        print("misses (case, label, got):")
        for case_id, want, got in misses:
            print(f"  {case_id:40s} {'+'.join(want) or '–':15s} {'+'.join(got) or '–'}")
    if rows[0]["new"].get("checklist") is None:
        return
    print("checklist questions (yes = answered yes; cited = yes with verifiable excerpt):")
    per_question = {}
    for row in rows:
        label = labels.get(row["case_id"])
        want = decisions(label["accepted"]) if label else None
        flags = row["new"].get("checklist_flags") or {}
        for key, entry in (row["new"].get("checklist") or {}).items():
            component, question = key.split(":")
            stats = per_question.setdefault(key, Counter())
            if entry.get("answer") == "yes":
                stats["yes"] += 1
                if question in flags.get(component, []):
                    stats["cited"] += 1
                    if want is not None:
                        stats["cited & label rejects"] += not want[component]
                        stats["cited & label accepts"] += want[component]
    for key in sorted(per_question):
        stats = per_question[key]
        print(
            f"  {key:18s} yes {stats['yes']:2d}  cited {stats['cited']:2d}"
            f"  of which label rejects {stats['cited & label rejects']:2d},"
            f" label accepts {stats['cited & label accepts']:2d} (false alarms)"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    args = parser.parse_args()
    labels = json.loads(args.labels.read_text())["labels"]
    for run in args.runs:
        score(run, labels)
