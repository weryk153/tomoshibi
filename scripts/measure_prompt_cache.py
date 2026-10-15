"""How much of each prompt LM Studio had to read again.

    .venv/bin/python scripts/measure_prompt_cache.py <server log> [<server log> ...] [--since HH:MM]

LM Studio logs every request as
`Prompt cache restore: cached_tokens=2816 uncached_tokens=223 ...`
(`~/.lmstudio/apps/bionic/server-logs/YYYY-MM/YYYY-MM-DD.N.log`). A
conversation request is usually 2000 tokens and more, a background job a few
hundred; the total tells them apart. Printed per file: how many of each, and
the median, p90 and maximum of `uncached_tokens`, the part read again
(about 370 tokens a second on an M4).
"""

from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

CACHE_LINE = re.compile(r"cached_tokens=(\d+) uncached_tokens=(\d+)")
TIME = re.compile(r"\b(\d{2}:\d{2}):\d{2}")
CONVERSATION_FROM = 2000


def summarize(lines, since: str | None = None) -> dict:
    groups = {"conversation": [], "background": []}
    for line in lines:
        if since:
            stamp = TIME.search(line)
            if stamp and stamp.group(1) < since:
                continue
        found = CACHE_LINE.search(line)
        if not found:
            continue
        cached, uncached = int(found.group(1)), int(found.group(2))
        key = "conversation" if cached + uncached >= CONVERSATION_FROM else "background"
        groups[key].append(uncached)
    summary = {}
    for key, values in groups.items():
        if not values:
            summary[key] = {"n": 0, "median": 0, "p90": 0, "max": 0}
            continue
        ordered = sorted(values)
        summary[key] = {
            "n": len(values),
            "median": statistics.median(values),
            "p90": ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))],
            "max": ordered[-1],
        }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--since", help="HH:MM; only lines from this time of day on")
    args = parser.parse_args()
    for log in args.logs:
        summary = summarize(log.read_text(errors="replace").splitlines(), args.since)
        print(f"{log.name}:")
        for key, stats in summary.items():
            print(
                f"  {key:13s} n={stats['n']:4d}  uncached median={stats['median']:7.1f}"
                f"  p90={stats['p90']:5d}  max={stats['max']:5d}"
            )
