"""Run frozen interaction scenes against an OpenAI-compatible evaluation server.

The fixture contains already assembled host prompts and synthetic test exchanges.
No live host configuration, credentials, or user memory is required remotely.
Use the matching engine checkout recorded in fixture.engine_commit.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from ai_character_engine import CharacterProfile
from ai_character_engine.cognition.background import _parse_json_object
from ai_character_engine.companion import CharacterCompanion, CompanionSettings
from ai_character_engine.llm.local import OpenAICompatibleChatClient
from ai_character_engine.llm.models import Message
from ai_character_engine.memory.experience import experience_review_proof


def write_json(path: Path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    temporary.replace(path)


class RecordedClient:
    def __init__(self, client, path: Path):
        self.client = client
        self.path = path
        self.calls = []

    async def generate(self, messages, *, tools=None):
        started = time.time()
        call = {"messages": [asdict(m) for m in messages], "started_at": started}
        try:
            response = await self.client.generate(messages, tools=tools)
            call["response"] = asdict(response)
        except BaseException as error:
            call["error"] = {"type": type(error).__name__, "message": str(error)}
            raise
        finally:
            call["elapsed_seconds"] = time.time() - started
            self.calls.append(call)
            with self.path.open("a") as handle:
                handle.write(json.dumps(call, ensure_ascii=False, default=str) + "\n")
        return response


def client(args, options):
    return OpenAICompatibleChatClient(
        model=args.model,
        base_url=args.base_url,
        backend="colab_llama_cpp",
        timeout_seconds=args.timeout,
        max_retries=0,
        request_options=options,
    )


async def trial(args, fixture, scene):
    run = scene["run"]
    saved = args.out / f"run-{run}.json"
    if saved.exists():
        previous = json.loads(saved.read_text())
        if len(previous.get("rows", [])) == 9:
            print(f"Preserving completed scene {run}", flush=True)
            return
        raise RuntimeError(
            f"Incomplete scene preserved at {saved}; use a fresh output."
        )
    store = args.out / f"store-{run}"
    if store.exists():
        raise RuntimeError(f"Existing store without completed scene: {store}")
    foreground = RecordedClient(
        client(args, fixture["foreground_options"]),
        args.out / f"foreground-{run}.jsonl",
    )
    background = RecordedClient(
        client(args, fixture["background_options"]),
        args.out / f"background-{run}.jsonl",
    )
    selected = {
        **fixture["settings"],
        "call_timeout_seconds": args.timeout,
        "foreground_patience_seconds": args.timeout,
    }
    options = dict(
        character=CharacterProfile(
            id="yura-interaction-trial",
            name=fixture["character_name"],
            description=fixture["system"],
            background=fixture["persona"],
        ),
        llm=foreground,
        background_llm=background,
        storage_dir=store,
        settings=CompanionSettings(**selected),
    )
    companion = CharacterCompanion(**options)
    rows = []
    try:
        for turn, entry in enumerate(scene["turns"], 1):
            if turn == 7:
                await companion.close()
                companion = CharacterCompanion(**options)
            identity = "another-person" if turn == 9 else "eval-owner"
            conversation = (
                "other" if turn == 9 else ("fresh" if turn >= 7 else "forming")
            )
            result = await companion.reply(
                entry["user"],
                conversation_id=conversation,
                user_id=identity,
                notes=entry["notes"],
            )
            await companion.settle()
            rows.append(
                {
                    "turn": turn,
                    "user": entry["user"],
                    "reply": result.text,
                    "user_id": identity,
                    "conversation_id": conversation,
                    "experiences": [
                        asdict(r) for r in companion.interaction_experiences(identity)
                    ],
                }
            )
            data = {
                "run": run,
                "scenario": scene["scenario"],
                "model": args.model,
                "engine_commit": fixture["engine_commit"],
                "system": fixture["system"],
                "prompt_sha256": fixture["prompt_sha256"],
                "settings": selected,
                "rows": rows,
                "foreground": foreground.calls,
                "background": background.calls,
            }
            write_json(saved, data)
            print(f"run={run} turn={turn}: {result.text}", flush=True)
    finally:
        await companion.close()
        await foreground.client.client.close()
        await background.client.client.close()


async def reviews(args, fixture):
    target = args.out / "fixed-review-comparison.json"
    rows = json.loads(target.read_text()) if target.exists() else []
    reviewing = RecordedClient(
        client(args, fixture["background_options"]),
        args.out / "fixed-review-calls.jsonl",
    )
    try:
        for case in fixture["review_cases"][len(rows) :]:
            messages = [
                Message(role=m["role"], content=m["content"]) for m in case["messages"]
            ]
            response = await reviewing.generate(messages)
            source = json.loads(messages[1].content)
            try:
                verdict = _parse_json_object(response.text)
            except ValueError as error:
                verdict = {"parse_error": str(error)}
            proof = experience_review_proof(
                source["candidate"], verdict, source["user_feedback"]
            )
            rows.append(
                {
                    **case,
                    "response": asdict(response),
                    "review": verdict,
                    "accepted_components": proof["accepted_components"]
                    if proof
                    else [],
                }
            )
            write_json(target, rows)
            print(
                f"review={case['case_id']} accepted={rows[-1]['accepted_components']}",
                flush=True,
            )
    finally:
        await reviewing.client.client.close()


async def main(args):
    args.out.mkdir(parents=True, exist_ok=True)
    raw = args.fixture.read_bytes()
    fixture = json.loads(raw)
    assert (
        hashlib.sha256(fixture["system"].encode()).hexdigest()
        == fixture["prompt_sha256"]
    )
    manifest = {
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "model": args.model,
        "base_url": args.base_url,
        "timeout_seconds": args.timeout,
        "foreground_options": fixture["foreground_options"],
        "background_options": fixture["background_options"],
        "engine_commit": fixture["engine_commit"],
        "notes": fixture["notes"],
    }
    path = args.out / "comparison-manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise RuntimeError(
            "Output already contains a different comparison; use a fresh path."
        )
    write_json(path, manifest)
    for scene in fixture["scenes"]:
        await trial(args, fixture, scene)
    await reviews(args, fixture)
    print("COMPARISON_COMPLETE", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--timeout", type=float, default=180.0)
    asyncio.run(main(parser.parse_args()))
