"""背景模型挑表情的人讀對照：三段真的對話裡她的句子，逐句跑 ExpressionPicker。

對話從 chat_history/<conf_uid>/<history_uid>.json 讀她（role=ai）的回覆，照標點切
成句子（每段取前 LIMIT 句）；表情與動作清單是那個角色當時的模型（model_dict.json
的 emotionMap／motionMap，含 label）。前一句是同一段對話裡她的上一句。對話紀錄
沒記心情，心情一律給 unknown（正式流程讀引擎當下的心情）。

正式流程 2.5 秒沒答就當沒挑到；這裡等到 15 秒，記下真的延遲，超過 2.5 秒的那句
當成 null 計（頁面上標「逾時」）。

輸出 docs/superpowers/eval/2026-10-06-expression-pick.html（gitignored）：
句子｜心情｜挑到的表情／動作｜延遲；最上面是 null 比例、延遲中位數、逾時句數。
明顯挑錯幾句由人看頁面判。

    uv run python scripts/eval_expression_pick.py [--root ../tomoshibi]
        [--base-url http://127.0.0.1:1235/v1] [--model qwen/qwen3.5-9b]
        [--out docs/superpowers/eval/2026-10-06-expression-pick.html]
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.open_llm_vtuber.background_llm import ChatClient  # noqa: E402
from src.open_llm_vtuber.expression_pick import (  # noqa: E402
    TIMEOUT_SECONDS,
    ExpressionPicker,
    pick_actions,
)

OUT = ROOT / "docs/superpowers/eval/2026-10-06-expression-pick.html"
# (標題, conf_uid, 對話檔, 模型名)
CONVERSATIONS = [
    (
        "佩克拉（VRM，6 表情＋11 動作）",
        "pekora",
        "2026-10-06_00-21-09_842ed0722fb243dd8843bcc52b661898.json",
        "pekora",
    ),
    (
        "芙莉蓮（Live2D，11 表情、無動作）",
        "char_16560406",
        "2026-08-19_21-20-04_dc62c610bd23440bbd02d734283d100a.json",
        "Frieren",
    ),
    (
        "Mao（Live2D，8 表情＋6 動作）",
        "mao_pro_001",
        "2026-07-31_20-22-47_f3e64d090d194a749ceec1f58e218aa9.json",
        "mao_pro",
    ),
]
LIMIT = 30
WAIT_SECONDS = 15.0
_TAG = re.compile(r"\[[^\[\]]{1,64}\]")
_SENTENCE = re.compile(r"[^。！？!?…\n]+(?:[。！？!?…]+|$)")


def sentences(text: str) -> list[str]:
    text = _TAG.sub("", text)
    return [s.strip() for s in _SENTENCE.findall(text) if s.strip(" 　*（）()")]


def load_lines(root: Path, conf_uid: str, name: str) -> list[str]:
    messages = json.loads((root / "chat_history" / conf_uid / name).read_text("utf-8"))
    lines: list[str] = []
    for message in messages:
        if message.get("role") == "ai" and message.get("content"):
            lines.extend(sentences(message["content"]))
    return lines[:LIMIT]


def load_model(root: Path, model: str) -> tuple[list[str], dict[str, str]]:
    entries = json.loads((root / "model_dict.json").read_text("utf-8"))
    entry = next(e for e in entries if e["name"] == model)
    expressions = [k.lower() for k in entry.get("emotionMap", {})]
    motions = {
        k.lower(): str((v or {}).get("label") or "")
        for k, v in entry.get("motionMap", {}).items()
    }
    return expressions, motions


async def run(args) -> list[dict]:
    client = ChatClient(
        base_url=args.base_url,
        model=args.model,
        request_options={
            "temperature": 0,
            "max_tokens": 80,
            "reasoning_effort": "none",
        },
        timeout_seconds=WAIT_SECONDS,
    )
    groups = []
    for title, conf_uid, name, model in CONVERSATIONS:
        expressions, motions = load_model(args.root, model)
        picker = ExpressionPicker(
            client=client, expressions=expressions, motions=motions
        )
        rows = []
        previous = ""
        for line in load_lines(args.root, conf_uid, name):
            started = time.monotonic()
            raw, error = "", ""
            try:
                raw = await asyncio.wait_for(
                    client.complete(picker.messages(line, previous)), WAIT_SECONDS
                )
            except Exception as e:  # noqa: BLE001 — 記下來給人看
                error = f"{type(e).__name__}: {e}"
            seconds = time.monotonic() - started
            picked = (
                pick_actions(line, expressions, list(motions), raw) if raw else None
            )
            rows.append(
                {
                    "line": line,
                    "previous": previous,
                    "raw": raw,
                    "error": error,
                    "seconds": seconds,
                    "picked": picked,
                    "late": seconds > TIMEOUT_SECONDS,
                }
            )
            print(f"{seconds:5.2f}s {picked} {line[:40]}", flush=True)
            previous = line
        groups.append(
            {
                "title": title,
                "model": model,
                "expressions": expressions,
                "motions": motions,
                "rows": rows,
            }
        )
    return groups


def effective(row: dict) -> tuple:
    """正式流程看到的：逾時或讀不懂就是 (None, None)。"""
    picked = row["picked"]
    if row["late"] or not picked:
        return None, None
    return picked["expression"], picked["motion"]


def stats(rows: list[dict]) -> dict:
    total = len(rows)
    expression_null = sum(1 for r in rows if effective(r)[0] is None)
    motion_null = sum(1 for r in rows if effective(r)[1] is None)
    both_null = sum(1 for r in rows if effective(r) == (None, None))
    late = sum(1 for r in rows if r["late"])
    unreadable = sum(1 for r in rows if not r["picked"])
    seconds = [r["seconds"] for r in rows] or [0.0]
    return {
        "total": total,
        "expression_null": expression_null,
        "motion_null": motion_null,
        "both_null": both_null,
        "late": late,
        "unreadable": unreadable,
        "median": statistics.median(seconds),
        "p90": sorted(seconds)[max(0, int(len(seconds) * 0.9) - 1)],
        "max": max(seconds),
    }


def pct(part: int, total: int) -> str:
    return f"{part}/{total}（{part / total:.0%}）" if total else "0/0"


def render(groups: list[dict], args) -> str:
    every = [r for g in groups for r in g["rows"]]
    overall = stats(every)

    def summary(s: dict) -> str:
        return (
            f"<ul><li>句數 {s['total']}</li>"
            f"<li>表情 null {pct(s['expression_null'], s['total'])}；動作 null "
            f"{pct(s['motion_null'], s['total'])}；兩者皆 null "
            f"{pct(s['both_null'], s['total'])}</li>"
            f"<li>延遲中位數 {s['median']:.2f}s、p90 {s['p90']:.2f}s、最慢 "
            f"{s['max']:.2f}s；超過 {TIMEOUT_SECONDS}s（正式流程當 null）"
            f"{pct(s['late'], s['total'])}</li>"
            f"<li>讀不懂／呼叫失敗 {s['unreadable']}</li></ul>"
        )

    parts = [
        "<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>表情挑選對照</title><style>",
        ":root{--bg:#fff;--fg:#1c1c1e;--mute:#6b6b70;--line:#e3e3e6;--late:#fff1e6;"
        "--null:#f4f4f6;--chip:#eef3ff}",
        "@media (prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececef;"
        "--mute:#9a9aa2;--line:#2c2c30;--late:#3a2a1c;--null:#202024;--chip:#1f2a44}}",
        "body{background:var(--bg);color:var(--fg);font:14px/1.6 system-ui,"
        "'PingFang TC',sans-serif;margin:0 auto;max-width:1100px;padding:16px}",
        "h1{font-size:20px}h2{font-size:16px;margin-top:32px}",
        ".mute{color:var(--mute);font-size:12px}",
        ".wrap{overflow-x:auto}table{border-collapse:collapse;width:100%}",
        "th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;"
        "vertical-align:top}",
        "th{font-size:12px;color:var(--mute);font-weight:600}",
        "tr.late td{background:var(--late)}td.null{color:var(--mute)}",
        ".chip{background:var(--chip);border-radius:4px;padding:1px 6px}",
        "td.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}",
        "details{font-size:12px;color:var(--mute)}",
        "</style></head><body>",
        "<h1>表情與動作交給背景模型挑：三段真實對話逐句對照</h1>",
        f"<p class='mute'>模型 {html.escape(args.model)} @ "
        f"{html.escape(args.base_url)}；temperature 0、reasoning_effort none、"
        f"max_tokens 80。每段取前 {LIMIT} 句；前一句是她的上一句。"
        "對話紀錄沒有心情，心情一律 unknown。延遲是單獨跑、背景模型閒著時量的；"
        "正式流程會跟 TTS 合成、引擎背景工作搶同一顆模型。</p>",
        "<h2>總計</h2>",
        summary(overall),
        "<p class='mute'>「明顯挑錯」請看下表逐句判斷（例如難過的句子挑 joy、"
        "沒在道別卻揮手道別）。</p>",
    ]
    for group in groups:
        motions = ", ".join(
            f"{k}（{v}）" if v else k for k, v in group["motions"].items()
        )
        parts += [
            f"<h2>{html.escape(group['title'])}</h2>",
            f"<p class='mute'>表情：{html.escape(', '.join(group['expressions']))}"
            f"<br>動作：{html.escape(motions or '（無）')}</p>",
            summary(stats(group["rows"])),
            "<div class='wrap'><table><thead><tr><th>#</th><th>句子</th>"
            "<th>心情</th><th>表情</th><th>強度</th><th>動作</th><th>延遲</th>"
            "</tr></thead><tbody>",
        ]
        for i, row in enumerate(group["rows"], 1):
            expression, motion = effective(row)
            picked = row["picked"] or {}
            note = ""
            if row["late"] and picked:
                note = (
                    f"<br><span class='mute'>逾時；本來會是 {picked.get('expression')}"
                    f"／{picked.get('motion')}</span>"
                )
            if row["error"]:
                note = f"<br><span class='mute'>{html.escape(row['error'])}</span>"
            elif not picked:
                note = (
                    "<details><summary>讀不懂</summary>"
                    f"{html.escape(row['raw'][:300])}</details>"
                )

            def cell(value):
                if value is None:
                    return "<td class='null'>—</td>"
                return f"<td><span class='chip'>{html.escape(value)}</span></td>"

            intensity = f"{picked['intensity']:.2f}" if expression and picked else "—"
            parts.append(
                f"<tr class='{'late' if row['late'] else ''}'><td class='num'>{i}</td>"
                f"<td>{html.escape(row['line'])}{note}</td><td class='null'>unknown</td>"
                f"{cell(expression)}<td class='num'>{intensity}</td>{cell(motion)}"
                f"<td class='num'>{row['seconds']:.2f}s</td></tr>"
            )
        parts.append("</tbody></table></div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base-url", default="http://127.0.0.1:1235/v1")
    parser.add_argument("--model", default="qwen/qwen3.5-9b")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    groups = asyncio.run(run(args))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(groups, args), encoding="utf-8")
    every = [r for g in groups for r in g["rows"]]
    print(json.dumps(stats(every), ensure_ascii=False))
    print(args.out)


if __name__ == "__main__":
    main()
