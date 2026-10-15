"""Replay saved interaction candidates through the per-component review.

The older review (proof version 2) judged the whole candidate with one set of
booleans, checked the supporting quote as one contiguous string and had no
separate look at the user's stated conditions. This script runs the same
sources and candidates through the current reviewer (proof version 3) and
writes an HTML page that puts every old verdict beside the new one, with the
full feedback, candidate and reasons, for human reading.

Cases come from three places: the 14 fixed review inputs shared by all three
model runs, the candidates each L4 model actually extracted in its own
conversations, and clearly labelled synthetic counterexamples written after
those runs. Synthetic rows carry an expected result but are not conversation
samples. Nothing here changes the engine; results go to an ignored eval directory.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from ai_character_engine.cognition.background import _parse_json_object
from ai_character_engine.llm.local import OpenAICompatibleChatClient
from ai_character_engine.memory.experience import (
    _legacy_accepted_components,
    condition_check_required,
    experience_condition_messages,
    experience_review_conditions,
    experience_review_messages,
    experience_review_proof,
)

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "docs/superpowers/eval"
OLD_RUNS = {
    "Qwen3.5-9B (v4)": EVAL / "2026-10-14-interaction-v4",
    "Qwen3.8-27B (L4)": EVAL / "2026-10-14-qwen38-l4",
    "Gemma 4 31B (L4)": EVAL / "2026-10-14-gemma4-l4",
}
FIXTURE = EVAL / "2026-10-14-gemma4-l4/fixture.json"


def source_of(user: dict) -> dict:
    return {
        "previous_reply": user["character_previous_reply"],
        "feedback": user["user_feedback"],
        "topics": user["prior_interpretations"],
    }


def old_verdict(review: dict, feedback: str) -> dict:
    return {
        "review": review,
        "accepted": _legacy_accepted_components(review, feedback),
    }


def parsed(text: str) -> dict:
    try:
        return _parse_json_object(text)
    except ValueError as error:
        return {"parse_error": str(error)}


def fixed_cases() -> list[dict]:
    fixture = json.loads(FIXTURE.read_text())
    cases = []
    for case in fixture["review_cases"]:
        user = json.loads(case["messages"][1]["content"])
        cases.append(
            {
                "case_id": case["case_id"],
                "group": "fixed",
                "origin": "14 組固定審核（9B v4 候選）",
                "source": source_of(user),
                "candidate": user["candidate"],
                "old": {},
            }
        )
    by_id = {case["case_id"]: case for case in cases}
    for name, directory in OLD_RUNS.items():
        rows_path = directory / "results/fixed-review-comparison.json"
        if rows_path.exists():
            for row in json.loads(rows_path.read_text()):
                case = by_id[row["case_id"]]
                case["old"][name] = old_verdict(
                    row["review"], case["source"]["feedback"]
                )
            continue
        # The 9B baseline reviewed these candidates inside its own conversations.
        for run in (1, 2, 3):
            data = json.loads((directory / f"run-{run}-True.json").read_text())
            for call in data["background"]:
                user = json.loads(call["messages"][1]["content"])
                if "candidate" not in user:
                    continue
                for case in cases:
                    if case["candidate"] == user["candidate"] and name not in case["old"]:
                        case["old"][name] = old_verdict(
                            parsed(call["response"]["text"]),
                            case["source"]["feedback"],
                        )
    return cases


def live_cases() -> list[dict]:
    cases = []
    for name, directory in OLD_RUNS.items():
        results = directory / "results"
        if not results.exists():
            continue
        for run in (1, 2, 3):
            for index, line in enumerate(
                (results / f"background-{run}.jsonl").read_text().splitlines()
            ):
                call = json.loads(line)
                user = json.loads(call["messages"][1]["content"])
                if "candidate" not in user:
                    continue
                cases.append(
                    {
                        "case_id": f"{name}-run-{run}-call-{index}",
                        "group": "live",
                        "origin": f"{name} 自己對話中的候選，第 {run} 組",
                        "source": source_of(user),
                        "candidate": user["candidate"],
                        "old": {
                            name: old_verdict(
                                parsed(call["response"]["text"]), user["user_feedback"]
                            )
                        },
                    }
                )
    return cases


def synthetic_cases() -> list[dict]:
    """Unseen counterexamples; each names the expected accepted components."""

    def case(case_id, reply, feedback, outcome, lesson, expect, why, **extra):
        return {
            "case_id": f"synthetic-{case_id}",
            "group": "synthetic",
            "origin": "合成反例（非對話樣本）",
            "expected": expect,
            "why": why,
            "source": {"previous_reply": reply, "feedback": feedback, "topics": []},
            "candidate": {
                "topic": extra.get("topic", "相處方式"),
                "lesson": lesson,
                "outcome": outcome,
                "character_quote": reply,
                "user_quote": feedback,
                "basis": extra.get("basis", "boundary"),
                "topic_id": None,
                "revises": False,
            },
            "old": {},
        }

    return [
        case(
            "condition-dropped",
            "那我以後都叫你小白好不好？",
            "你可以叫我小白，但只有在家裡，出門就不要。",
            "對方同意我叫他小白。",
            "對方喜歡我叫他小白，以後可以這樣叫。",
            [],
            "「只有在家裡」在 outcome 與 lesson 都被省略；兩者都把許可擴大。",
        ),
        case(
            "condition-kept",
            "那我以後都叫你小白好不好？",
            "你可以叫我小白，但只有在家裡，出門就不要。",
            "對方同意在家裡被叫小白，出門不要。",
            "在家可以叫對方小白，出門就不行。",
            ["outcome", "lesson"],
            "兩者都保留了地點條件，只是換了說法。",
        ),
        case(
            "condition-absent",
            "可以用手指彈瓶蓋，看誰最快彈出桌邊。你想試試看嗎？",
            "我喜歡你也自己下場玩，不要只當出題的人。規則偏心一點也行，但被我抓到要認輸喔。",
            "對方希望我一起下場玩，不只出題。",
            "對方喜歡我一起玩，而不是只負責出題。",
            ["outcome", "lesson"],
            "候選完全沒提規則偏心，條件應判 absent，不該因此拒絕。",
            basis="preference",
            topic="一起玩",
        ),
        case(
            "condition-weakened",
            "可以用手指彈瓶蓋，看誰最快彈出桌邊。你想試試看嗎？",
            "我喜歡你也自己下場玩，不要只當出題的人。規則偏心一點也行，但被我抓到要認輸喔。",
            "對方希望我一起下場玩，不只出題。",
            "對方喜歡我一起玩，也不介意我規則偏心，只要我輸了認帳就好。",
            ["outcome"],
            "lesson 把「被抓到要認輸」改成「輸了認帳」；outcome 沒提偏心，應保留。",
            basis="preference",
            topic="一起玩",
        ),
        case(
            "lesson-speaker-swap",
            "你今天過得怎麼樣？有沒有什麼好玩的事？那你晚餐吃了什麼？",
            "我不喜歡你每句話都問我問題。",
            "對方表示不喜歡我每句話都問問題。",
            "我不喜歡每句話都被問問題。",
            ["outcome"],
            "lesson 把對方的偏好寫成角色自己的；outcome 說話者正確。",
            basis="preference",
            topic="提問頻率",
        ),
        case(
            "invented-cause",
            "好喔，那今天就先到這裡吧。明天再來挑戰看誰能一次丟準三個？",
            "對，我說先收工就真的想停。下次精神好再玩，不用激我繼續。",
            "對方明確表示想停，並要求我不要激他繼續。",
            "我發現激將會讓人想停，下次得先確認對方意願再決定要不要繼續。",
            ["outcome"],
            "「激將會讓人想停」是候選自己加的因果；對方只說不用激。三個模型以前都放過。",
            topic="停下來",
        ),
        case(
            "story-continuation",
            "那你先彈，看能不能彈到桌邊。",
            "我用手指彈，第一個直接飛到桌子下面，零分。",
            "對方對規則不滿，覺得被針對。",
            "我的規則讓對方覺得被針對，下次要公平一點。",
            [],
            "只是遊戲進行，沒有回饋；整筆應拒絕。",
            topic="遊戲規則",
        ),
        case(
            "condition-narrowed",
            "可以用手指彈瓶蓋，看誰最快彈出桌邊。你想試試看嗎？",
            "我喜歡你也自己下場玩，不要只當出題的人。規則偏心一點也行，但被我抓到要認輸喔。",
            "對方希望我親自參與遊戲，並接受偏心的規則，但需遵守認輸的約定。",
            "我應該親自下場一起玩。規則可以稍微偏心，但被抓到時要誠實認輸。",
            ["outcome", "lesson"],
            "outcome 只寫「需遵守認輸的約定」沒寫「被抓到」，是比原話窄，不是改寫；"
            "條件會逐字附在記憶旁。27B 之前把這筆整筆拒絕。",
            basis="preference",
            topic="一起玩",
        ),
        case(
            "separate-plan-not-a-condition",
            "好喔，那今天就先到這裡吧。明天再來挑戰看誰能一次丟準三個？",
            "對，我說先收工就真的想停。下次精神好再玩，不用激我繼續。",
            "對方明確表示想停止，並指出不需要被激將繼續。",
            "對方說要收工就是真的想停，我不該用激將法讓他繼續。",
            ["outcome", "lesson"],
            "「下次精神好再玩」是另一個打算，不是限制「不用激我」的條件；"
            "之前被列為條件後整筆拒絕。",
            topic="停下來",
        ),
        case(
            "scope-widened",
            "那這局我規定我的瓶蓋可以彈兩次，沒問題吧？",
            "今天這局你偏心一點沒關係。",
            "對方同意今天這局規則可以偏心。",
            "對方不介意我規則偏心。",
            ["outcome"],
            "「今天這局」是限制；lesson 把它擴成一般許可，outcome 有保留。",
            basis="preference",
            topic="遊戲規則",
        ),
    ]


class RecordedClient:
    def __init__(self, client, path: Path):
        self.client = client
        self.path = path

    async def generate(self, messages):
        started = time.time()
        call = {"messages": [asdict(m) for m in messages], "started_at": started}
        try:
            response = await self.client.generate(messages)
            call["response"] = asdict(response)
        except BaseException as error:
            call["error"] = {"type": type(error).__name__, "message": str(error)}
            raise
        finally:
            call["elapsed_seconds"] = time.time() - started
            with self.path.open("a") as handle:
                handle.write(json.dumps(call, ensure_ascii=False, default=str) + "\n")
        return response


async def review_case(client: RecordedClient, case: dict, prior: dict | None = None) -> dict:
    """Review one case; with `prior`, reuse its first-stage review and redo only the condition comparison."""
    source, candidate = case["source"], case["candidate"]
    feedback = source["feedback"]
    if prior is None:
        response = await client.generate(experience_review_messages(source, candidate))
        review = parsed(response.text)
    else:
        response = None
        review = prior["review"]
    conditions_check = None
    conditions_response = None
    if condition_check_required(review, feedback):
        conditions_response = await client.generate(
            experience_condition_messages(
                experience_review_conditions(review), candidate
            )
        )
        conditions_check = parsed(conditions_response.text)
    proof = experience_review_proof(candidate, review, feedback, conditions_check)
    return {
        "review": review,
        "conditions": conditions_check,
        "accepted": proof["accepted_components"] if proof else [],
        "review_reused_from": prior.get("reused_from") if prior else None,
        "review_response": asdict(response) if response else None,
        "conditions_response": asdict(conditions_response)
        if conditions_response
        else None,
    }


async def run(args) -> list[dict]:
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / "review-comparison.json"
    rows = json.loads(target.read_text()) if target.exists() else []
    cases = fixed_cases() + live_cases() + synthetic_cases()
    done = {row["case_id"] for row in rows}
    reused: dict[str, dict] = {}
    if args.reuse_reviews:
        for row in json.loads((args.reuse_reviews / "review-comparison.json").read_text()):
            reused[row["case_id"]] = {**row["new"], "reused_from": str(args.reuse_reviews)}
    client = RecordedClient(
        OpenAICompatibleChatClient(
            model=args.model,
            base_url=args.base_url,
            backend="lmstudio_llm",
            timeout_seconds=args.timeout,
            max_retries=0,
            request_options={
                "temperature": 0.1,
                "max_tokens": 600,
                "extra_body": json.loads(args.extra_body),
            },
        ),
        args.out / "review-calls.jsonl",
    )
    try:
        for case in cases:
            if case["case_id"] in done:
                continue
            case["new"] = {
                "model": args.model,
                **await review_case(client, case, reused.get(case["case_id"])),
            }
            rows.append(case)
            target.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
            print(
                case["case_id"],
                "old=",
                {k: v["accepted"] for k, v in case["old"].items()},
                "new=",
                case["new"]["accepted"],
                flush=True,
            )
    finally:
        await client.client.client.close()
    return rows


def esc(value) -> str:
    return html.escape(str(value))


def pre(value) -> str:
    return f"<pre>{esc(json.dumps(value, ensure_ascii=False, indent=1))}</pre>"


def verdict(accepted) -> str:
    label = {
        (): "全部拒絕",
        ("outcome",): "只存摘要",
        ("outcome", "lesson"): "摘要＋教訓",
    }[tuple(accepted)]
    return f'<span class="v v-{len(accepted)}">{label}</span>'


def report(rows: list[dict], out: Path) -> None:
    sections = []
    for group, title in (
        ("fixed", "一、14 組固定審核：三個舊審核 vs 新審核"),
        ("live", "二、L4 模型自己對話中的候選：該模型的舊審核 vs 新審核"),
        ("synthetic", "三、合成反例（事後寫的，不是對話樣本）"),
    ):
        cards = []
        for row in [r for r in rows if r["group"] == group]:
            old_cols = "".join(
                f"<div class='col'><h4>{esc(name)}（舊）{verdict(v['accepted'])}</h4>"
                f"{pre(v['review'])}</div>"
                for name, v in row["old"].items()
            )
            new = row["new"]
            new_col = (
                f"<div class='col new'><h4>{esc(new['model'])}（新）{verdict(new['accepted'])}</h4>"
                f"{pre(new['review'])}"
                + (
                    f"<h5>條件逐條比對</h5>{pre(new['conditions'])}"
                    if new["conditions"] is not None
                    else "<p class='muted'>沒有列出條件，未做第二次比對。</p>"
                )
                + "</div>"
            )
            expected = (
                f"<p><b>預期：</b>{verdict(row['expected'])} <b>理由：</b>{esc(row['why'])}</p>"
                if "expected" in row
                else ""
            )
            cards.append(
                f"<section class='card'><h3>{esc(row['case_id'])}</h3>"
                f"<p class='muted'>{esc(row['origin'])}</p>{expected}"
                f"<div class='exchange'><p><b>角色上一句：</b>{esc(row['source']['previous_reply'])}</p>"
                f"<p><b>使用者回饋：</b>{esc(row['source']['feedback'])}</p>"
                f"<p><b>候選 outcome：</b>{esc(row['candidate']['outcome'])}</p>"
                f"<p><b>候選 lesson：</b>{esc(row['candidate']['lesson'])}</p>"
                + (
                    f"<p><b>既有主題：</b>{esc(json.dumps(row['source']['topics'], ensure_ascii=False))}</p>"
                    if row["source"]["topics"]
                    else ""
                )
                + f"</div><div class='cols'>{old_cols}{new_col}</div></section>"
            )
        sections.append(f"<h2>{title}</h2>" + "".join(cards))
    page = (
        "<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
        "<title>審核流程 v2 vs v3 逐案並排</title><style>"
        "body{font-family:system-ui,sans-serif;margin:24px;line-height:1.5;color:#222}"
        ".card{border:1px solid #ccc;border-radius:8px;padding:12px 16px;margin:16px 0}"
        ".exchange{background:#f6f6f6;padding:8px 12px;border-radius:6px}"
        ".cols{display:flex;gap:12px;flex-wrap:wrap;margin-top:8px}"
        ".col{flex:1 1 280px;min-width:260px;border-top:3px solid #bbb;padding-top:4px}"
        ".col.new{border-top-color:#2a6}"
        "pre{white-space:pre-wrap;word-break:break-word;font-size:12px;background:#fafafa;padding:6px}"
        ".v{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:10px;font-size:13px;font-weight:normal}"
        ".v-0{background:#fdd}.v-1{background:#ffe9b3}.v-2{background:#d7f5d7}"
        ".muted{color:#666}h4,h5{margin:6px 0}</style></head><body>"
        "<h1>審核流程 v2 vs v3 逐案並排</h1>"
        f"<p>產生於 {datetime.now():%Y-%m-%d %H:%M}。新審核由 {esc(rows[0]['new']['model'])} 執行，"
        "舊審核沿用各目錄保存的原始回應。這是給人讀的全文，不是準確率。</p>"
        + "".join(sections)
        + "</body></html>"
    )
    (out / "comparison.html").write_text(page)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=EVAL / datetime.now().strftime("%Y-%m-%d-review-v3-replay"),
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1235/v1")
    parser.add_argument("--model", default="qwen/qwen3.5-9b")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--extra-body",
        default='{"reasoning_effort": "none"}',
        help="JSON merged into each request; LM Studio needs reasoning_effort, "
        'llama.cpp takes {"chat_template_kwargs": {"enable_thinking": false}}',
    )
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument(
        "--reuse-reviews",
        type=Path,
        help="a previous output directory whose first-stage reviews are reused; "
        "only the condition comparison is called again (for tuning that prompt alone)",
    )
    args = parser.parse_args()
    if args.report_only:
        rows = json.loads((args.out / "review-comparison.json").read_text())
    else:
        rows = asyncio.run(run(args))
    report(rows, args.out)
    print("report:", args.out / "comparison.html")
