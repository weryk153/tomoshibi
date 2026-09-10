#!/usr/bin/env python3
"""Measure whether replies actually obey the persona's length rule.

A persona that says 「平常講一到三句就好」 is only obeyed if real replies show it. Whether that is working can only be
answered from real conversations, so this reads chat_history/ and reports the
distribution.

Two things it deliberately gets right, because getting them wrong produces a
flattering but meaningless number:

- Proactive turns are counted separately. Their prompt says 「長度不限」, so
  averaging them with user-triggered replies measures nothing.
- LLM error placeholders are excluded. They are not speech (see
  llm_error_sentinel); before that guard existed, 75 of 231 stored assistant
  turns were error text.

Usage:
    uv run scripts/reply_length_report.py [conf_uid] [--since ISO8601]

    uv run scripts/reply_length_report.py default_001 --since 2026-08-01T03:43
"""

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.open_llm_vtuber.llm_error_sentinel import is_llm_error_placeholder  # noqa: E402

TARGET_MAX_SENTENCES = 3  # 人設寫的「平常講一到三句就好」
TARGET_MAX_QUESTIONS = 1  # 人設寫的「一次最多問一個問題」


def _sentences(text: str) -> int:
    return len([s for s in re.split(r"[。！？!?]", text) if s.strip()])


def _questions(text: str) -> int:
    """Stacked questions are the measurable form of "sounds like an interrogation".

    Before the cap was added to the persona, 12 of 29 replies carried three or
    more question marks and two carried seven — in a spoken conversation the
    user cannot answer those.
    """
    return text.count("？") + text.count("?")


def collect(conf_uid: str, since: str | None):
    """Return (kind, timestamp, text) for every stored assistant turn.

    A proactive turn is stored with no preceding human message: the synthetic
    user input carries skip_history, so it never reaches the file.
    """
    rows = []
    pattern = f"chat_history/{conf_uid}/*.json"
    for path in sorted(glob.glob(pattern), key=os.path.getmtime):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        previous = None
        for message in data:
            role = message.get("role")
            content = message.get("content") or ""
            if role == "ai" and content and not is_llm_error_placeholder(content):
                timestamp = message.get("timestamp", "")
                if not since or timestamp >= since:
                    kind = "proactive" if previous == "ai" else "reply"
                    rows.append((kind, timestamp, content))
            if role in ("ai", "human"):
                previous = role
    return sorted(rows, key=lambda r: r[1])


def report(rows, kind: str, label: str, rule: str) -> None:
    selected = [(t, c) for k, t, c in rows if k == kind]
    print(f"\n{label}  （{rule}）")
    if not selected:
        print("  沒有資料")
        return
    counts = sorted(_sentences(c) for _, c in selected)
    chars = [len(c) for _, c in selected]
    over = sum(1 for n in counts if n > TARGET_MAX_SENTENCES)
    print(f"  n={len(selected)}  平均 {sum(chars) // len(chars)} 字")
    print(f"  句數分布 {counts}")
    print(f"  中位數 {counts[len(counts) // 2]} 句")
    if kind == "reply":
        pct = 100 * over // len(counts)
        print(f"  超過 {TARGET_MAX_SENTENCES} 句：{over}/{len(counts)} ({pct}%)")
        questions = sorted(_questions(c) for _, c in selected)
        too_many = sum(1 for n in questions if n > TARGET_MAX_QUESTIONS)
        qpct = 100 * too_many // len(questions)
        print(f"  問號數分布 {questions}")
        print(
            f"  超過 {TARGET_MAX_QUESTIONS} 個問句："
            f"{too_many}/{len(questions)} ({qpct}%)"
        )
    print(f"  最早 {selected[0][0]}   最晚 {selected[-1][0]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("conf_uid", nargs="?", default="default_001")
    parser.add_argument("--since", default=None, help="只算這個時間之後的（ISO8601）")
    args = parser.parse_args()

    rows = collect(args.conf_uid, args.since)
    print(
        f"角色 {args.conf_uid}：{len(rows)} 則有效發言"
        + (f"（{args.since} 之後）" if args.since else "")
    )
    report(rows, "reply", "使用者觸發", "人設：平常講一到三句")
    report(rows, "proactive", "主動發言", "提示詞：長度不限")

    replies = [r for r in rows if r[0] == "reply"]
    if len(replies) < 8:
        print(
            f"\n注意：使用者觸發只有 {len(replies)} 則，樣本太小，不足以判斷人設有沒有生效。"
        )


if __name__ == "__main__":
    main()
