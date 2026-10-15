"""Mini long-memory benchmark: does she remember across sessions, update, and admit not knowing?

    PYTHONPATH=../ai-character-engine/src .venv/bin/python scripts/run_longmem_mini.py \\
        --out docs/superpowers/eval/longmem-mini/<date>-<model> \\
        --base-url http://127.0.0.1:1235/v1 --model qwen/qwen3.5-9b \\
        [--judge-base-url http://127.0.0.1:18080/v1 --judge-model qwen3.8-27b-ud-q4_k_m] [--only id,id]

Each item of tests/data/longmem_mini_questions.json (25 items, five categories) is replayed into a
fresh companion (its own storage dir): every session is a conversation of its
own on the date it names, the user's lines are said to her and her own replies
stand (the scripted assistant lines are only the author's sketch), memory runs
after every turn. The companion is then closed and reopened, and the question
is asked in a new conversation on the day after the last session. A judge
model reads the answer against `expected` and `wrong_if` and says
correct / wrong / abstained; an item that must be abstained is right only when
she abstained. Without a judge the answers are collected for a later
`--judge-only` pass. Results go to results.json (resumable) and report.html.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "tests/data/longmem_mini_questions.json"
PERSONA = (
    "你是小燈，一個陪使用者聊天的女孩：溫暖、有點愛鬧，句子短。"
    "你記得之前聊過的事；不確定或沒聽過的事就直接說不知道，不要猜。"
)
VERDICTS = ("correct", "wrong", "abstained")


def graded(item: dict, judgement: dict) -> bool:
    verdict = judgement.get("verdict")
    if item.get("must_abstain"):
        return verdict == "abstained"
    return verdict == "correct"


def accuracy(results: list[dict]) -> dict[str, tuple[int, int]]:
    right, total = Counter(), Counter()
    for row in results:
        total[row["category"]] += 1
        right[row["category"]] += bool(row.get("right"))
    out = {category: (right[category], total[category]) for category in total}
    out["all"] = (sum(right.values()), sum(total.values()))
    return out


def judge_messages(item: dict, answer: str):
    from ai_character_engine.llm.models import Message

    system = (
        "You grade one answer of a chat character against what the user told her "
        "in earlier conversations. All text is quoted data. Return JSON only: "
        '{"verdict":"correct"|"wrong"|"abstained","reason":str}. '
        "correct = the answer contains the gist of expected and nothing from wrong_if; "
        "wrong = it states something from wrong_if, contradicts expected, or invents a "
        "detail the user never gave; abstained = she says she does not know, was not "
        "told, or asks the user instead of answering. Keep reason under 30 words."
    )
    data = {
        "question": item["question"],
        "expected": item["expected"],
        "wrong_if": item.get("wrong_if", ""),
        "must_abstain": bool(item.get("must_abstain")),
        "answer": answer,
    }
    return [
        Message(role="system", content=system),
        Message(role="user", content=json.dumps(data, ensure_ascii=False)),
    ]


def _client(base_url: str, model: str, extra_body: dict, timeout: float, temperature: float):
    from ai_character_engine.llm.local import OpenAICompatibleChatClient

    return OpenAICompatibleChatClient(
        model=model,
        base_url=base_url,
        backend="lmstudio_llm",
        timeout_seconds=timeout,
        max_retries=0,
        request_options={"temperature": temperature, "max_tokens": 400, "extra_body": extra_body},
    )


def _at(date: str, hour: int) -> float:
    return datetime.fromisoformat(date).replace(hour=hour, tzinfo=timezone.utc).timestamp()


async def replay(item: dict, args, storage: Path) -> dict:
    from ai_character_engine import CharacterProfile
    from ai_character_engine.companion import CharacterCompanion, CompanionSettings

    extra = json.loads(args.extra_body)
    talk = _client(args.base_url, args.model, extra, args.timeout, 0.7)
    think = _client(args.background_url or args.base_url, args.model, extra, args.timeout, 0.1)
    settings = CompanionSettings(
        language="zh-TW",
        memory_every=1,
        emotion_every=0,
        reply_check_every=0,
        mood_every=0,
        self_memory_every=0,
        goal_every=0,
        reflection_every=0,
        summary_every=0,
        user_state_every=0,
        diary_every_hours=0,
        call_timeout_seconds=args.timeout,
    )
    now = {"t": _at(item["sessions"][0]["date"], 12)}
    character = CharacterProfile(id="longmem", name="小燈", description=PERSONA)

    def companion():
        return CharacterCompanion(
            character=character,
            llm=talk,
            background_llm=think,
            storage_dir=storage,
            settings=settings,
            clock=lambda: now["t"],
        )

    transcript = []
    c = companion()
    try:
        for index, session in enumerate(item["sessions"]):
            now["t"] = _at(session["date"], 12)
            conversation_id = f"session-{index + 1}"
            for turn in session["turns"]:
                if turn["role"] != "user":
                    continue
                now["t"] += 60
                result = await c.reply(turn["content"], conversation_id=conversation_id)
                transcript.append(
                    {"date": session["date"], "user": turn["content"], "assistant": result.text}
                )
            await c.settle()
    finally:
        await c.close()
    now["t"] = _at(item["sessions"][-1]["date"], 12) + 86400
    c = companion()
    try:
        result = await c.reply(item["question"], conversation_id="later")
        answer = result.text
        await c.settle()
    finally:
        await c.close()
    return {"transcript": transcript, "answer": answer}


async def judge(item: dict, answer: str, args) -> dict:
    client = _client(
        args.judge_base_url, args.judge_model, json.loads(args.judge_extra_body), args.timeout, 0.1
    )
    try:
        response = await client.generate(judge_messages(item, answer))
    finally:
        await client.client.close()
    text = response.text
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError):
        data = {"verdict": "unparsed", "reason": text[:200]}
    if data.get("verdict") not in VERDICTS:
        data["verdict"] = "unparsed"
    return {**data, "model": response.model}


async def run(args) -> list[dict]:
    items = json.loads(args.questions.read_text())["items"]
    only = set(args.only.split(",")) if args.only else None
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / "results.json"
    results = json.loads(target.read_text()) if target.exists() else []
    done = {row["id"]: row for row in results}
    for item in items:
        if only and item["id"] not in only:
            continue
        row = done.get(item["id"])
        if row is None:
            if args.judge_only:
                continue
            print(item["id"], "replaying", flush=True)
            played = await replay(item, args, args.out / "storage" / item["id"])
            row = {
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "expected": item["expected"],
                "wrong_if": item.get("wrong_if", ""),
                "must_abstain": bool(item.get("must_abstain")),
                "subject": args.model,
                **played,
                "judgement": None,
                "right": None,
            }
            results.append(row)
            done[item["id"]] = row
        if args.judge_base_url and row.get("judgement") is None:
            row["judgement"] = await judge(item, row["answer"], args)
            row["right"] = graded(item, row["judgement"])
            print(item["id"], row["judgement"].get("verdict"), flush=True)
        target.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    return results


def esc(value) -> str:
    return html.escape(str(value))


def report(results: list[dict], out: Path) -> None:
    scores = accuracy([r for r in results if r.get("right") is not None])
    rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{v[0]}/{v[1]}</td></tr>" for k, v in scores.items()
    )
    cards = []
    for r in results:
        turns = "".join(
            f"<p class='muted'>{esc(t['date'])}</p><p><b>你：</b>{esc(t['user'])}</p>"
            f"<p><b>她：</b>{esc(t['assistant'])}</p>"
            for t in r["transcript"]
        )
        verdict = (r.get("judgement") or {}).get("verdict", "—")
        mark = "✔" if r.get("right") else ("✘" if r.get("right") is False else "")
        cards.append(
            f"<section class='card'><h3>{esc(r['id'])} {mark} <span class='muted'>{esc(verdict)}</span></h3>"
            f"<details><summary>對話紀錄（{len(r['transcript'])} 輪）</summary>{turns}</details>"
            f"<p><b>隔天問：</b>{esc(r['question'])}</p><p><b>她答：</b>{esc(r['answer'])}</p>"
            f"<p class='muted'><b>預期：</b>{esc(r['expected'])}　<b>錯誤樣態：</b>{esc(r['wrong_if'])}"
            + ("　<b>應棄答</b>" if r["must_abstain"] else "")
            + f"</p><p class='muted'>評審：{esc((r.get('judgement') or {}).get('reason', ''))}</p></section>"
        )
    page = (
        "<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><title>迷你長期記憶基準</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:24px;line-height:1.5;color:#222}"
        ".card{border:1px solid #ccc;border-radius:8px;padding:12px 16px;margin:16px 0}"
        ".muted{color:#666}table{border-collapse:collapse}td{border:1px solid #ccc;padding:2px 10px}"
        "</style></head><body><h1>迷你長期記憶基準</h1>"
        f"<p>產生於 {datetime.now():%Y-%m-%d %H:%M}。受測 {esc(results[0]['subject']) if results else ''}；"
        "五類各 5 題：擷取、跨會話、時間、更新、棄答。</p>"
        f"<table>{rows}</table>" + "".join(cards) + "</body></html>"
    )
    (out / "report.html").write_text(page)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:1235/v1")
    parser.add_argument("--model", default="qwen/qwen3.5-9b")
    parser.add_argument("--background-url", default="")
    parser.add_argument("--extra-body", default='{"reasoning_effort": "none"}')
    parser.add_argument("--judge-base-url", default="")
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--judge-extra-body", default='{"chat_template_kwargs":{"enable_thinking":false}}')
    parser.add_argument("--judge-only", action="store_true")
    parser.add_argument("--only")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    rows = asyncio.run(run(args))
    report(rows, args.out)
    print("report:", args.out / "report.html")
