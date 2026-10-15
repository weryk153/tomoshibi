"""Replay saved interpretations and labelled positive controls through the reviewer."""

# ruff: noqa: E402
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.compare_character_development import (
    ROOT,
    RecordedClient,
    _clients,
    yaml,
    logger,
)
from ai_character_engine.cognition.background import _parse_json_object
from ai_character_engine.memory.experience import (
    experience_review_messages,
    experience_review_passed,
    experience_review_proof,
)

OUT = (
    ROOT
    / "docs/superpowers/eval"
    / datetime.now().strftime("%Y-%m-%d-%H%M%S-review-replay")
)
SOURCE = ROOT / "docs/superpowers/eval/2026-10-14-interaction-v2"


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "review-replay.json"
    logger.remove()
    raw = yaml.safe_load((ROOT / "conf.yaml").read_text())
    config = raw["character_config"]["agent_config"]["llm_configs"]["lmstudio_llm"]
    config = {
        **config,
        "base_url": "http://127.0.0.1:1234/v1",
        "model": "qwen/qwen3.5-9b",
    }
    _, client, _, _, _ = _clients(
        "lmstudio_llm",
        config,
        {
            "background_base_url": "http://127.0.0.1:1235/v1",
            "background_model": "qwen/qwen3.5-9b",
        },
    )
    recorded = RecordedClient(client)
    cases = []
    for run in (1, 3):
        data = json.loads((SOURCE / f"run-{run}-True.json").read_text())
        for call in data["background"]:
            candidate = _parse_json_object(call["response"]["text"]).get("experience")
            if candidate:
                source = json.loads(call["messages"][1]["content"])
                cases.append(
                    dict(
                        origin=f"{SOURCE.name}-run-{run}",
                        source=source,
                        candidate=candidate,
                    )
                )
    # Positive controls use real exchanges but hand-written, narrowly supported
    # interpretations. They are labelled synthetic, not extra full conversations.
    controls = [
        (
            "我改主意了",
            "nicknames",
            "I can privately call this person 菜攤老闆; other nicknames are still unwelcome.",
            "The user explicitly permits this one private nickname while excluding other nicknames.",
            "boundary",
        ),
        (
            "我喜歡你也自己下場玩",
            "playing together",
            "I can join this person in the game; if they catch a biased rule, I should admit defeat.",
            "The user wants me to participate and sets a condition on biased rules.",
            "preference",
        ),
        (
            "對，我說先收工",
            "stopping a game",
            "When this person says to stop for the day, I should stop rather than goad them to continue.",
            "The user explicitly asks me to respect their decision to stop playing.",
            "boundary",
        ),
    ]
    for prefix, topic, interpretation, outcome, basis in controls:
        original = next(
            case for case in cases if case["source"]["feedback"].startswith(prefix)
        )
        source = {**original["source"], "topics": []}
        revises = prefix == "我改主意了"
        if revises:
            source["topics"] = [
                {
                    "topic_id": "known-nickname-boundary",
                    "topic": topic,
                    "interpretation": "This person does not want me to give them nicknames.",
                }
            ]
        candidate = dict(
            topic=topic,
            topic_id="known-nickname-boundary" if revises else None,
            lesson=interpretation,
            outcome=outcome,
            basis=basis,
            revises=revises,
            character_quote=source["previous_reply"],
            user_quote=source["feedback"],
        )
        cases.append(
            dict(
                origin="synthetic-positive-interpretation",
                source=source,
                candidate=candidate,
            )
        )
    results = json.loads(target.read_text()) if target.exists() else []
    for previous, case in zip(results, cases):
        messages = experience_review_messages(case["source"], case["candidate"])
        if (
            previous.get("candidate") != case["candidate"]
            or previous.get("messages") != [asdict(m) for m in messages]
            or previous.get("admission_version") != 2
        ):
            raise SystemExit(
                "Saved replay uses different inputs or policy; choose a fresh --out."
            )
    for case in cases[len(results) :]:
        messages = experience_review_messages(case["source"], case["candidate"])
        response = await recorded.generate(messages)
        try:
            review = _parse_json_object(response.text)
        except ValueError as exc:
            review = {"parse_error": str(exc)}
        accepted = experience_review_passed(
            case["candidate"], review, case["source"]["feedback"]
        )
        proof = experience_review_proof(
            case["candidate"], review, case["source"]["feedback"]
        )
        results.append(
            {
                **case,
                "accepted": accepted,
                "admission_version": 2,
                "accepted_components": proof["accepted_components"] if proof else [],
                "review": review,
                "messages": [asdict(m) for m in messages],
                "response": asdict(response),
            }
        )
        target.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(
            case["origin"],
            case["source"]["feedback"],
            "\naccepted=",
            accepted,
            review,
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--source", type=Path, default=SOURCE)
    args = parser.parse_args()
    OUT, SOURCE = args.out, args.source
    asyncio.run(main())
