#!/usr/bin/env python3
"""她的心情：規則推出的（現行）與 mood worker 判斷的，逐輪並排給人讀。

用法（mood worker 還沒發版，用引擎 repo 的環境跑；不要用 Tomoshibi 的 uv run，
那會把引擎換回 pyproject 釘的版本）：

    uv run --project ../ai-character-engine python scripts/compare_mood.py \
        chat_history/<conf_uid>/<history_uid>.json [...至少三段] \
        --model qwen/qwen3.5-9b --out docs/superpowers/eval/<日期>-mood.html

每段對話照紀錄重播：使用者那句原樣送進引擎，她的回覆由一個只會照念紀錄的假模型
給，所以雙方的話跟當時一模一樣。每一輪都跑情緒分析（只讀使用者）與 mood worker
（讀雙方），用 --base-url 那顆模型。每輪記下：雙方的話、情緒分析看到的使用者與
規則會由它推出的心情（每輪都排 mood 判斷，引擎在這種輪不讓規則動心情，
所以這欄只是「沒排 mood 的輪規則會怎麼做」的參考）、mood worker 的原始回答與引擎收不收、
收了之後是採用還是保留前一個（心情有慣性：較弱的別種心情、neutral 都不蓋掉現在的）、
這輪結束後存著的心情。

只讀 chat_history/ 的對話檔，不寫任何東西回去；引擎狀態只在記憶體裡。
"""

import argparse
import asyncio
import html
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from ai_character_engine import CharacterProfile
from ai_character_engine.companion import (
    CHARACTER_MOODS,
    CharacterCompanion,
    CompanionSettings,
)
from ai_character_engine.llm.local import OpenAICompatibleChatClient
from ai_character_engine.llm.models import LLMResponse, LLMStreamChunk
from ai_character_engine.state.models import CharacterState
from ai_character_engine.state.mood import MOOD_SYNONYMS, effective_mood
from ai_character_engine.state.relationship import (
    APPLIED_OBSERVATION_KEY,
    OBSERVATION_KEY,
    relationship_patch,
)

# 規則改用新詞之前的叫法，讓人對得上舊的紀錄。
OLD_NAMES = {"sad": "hurt", "worried": "concerned"}


class Replay:
    """她那一側：照紀錄念出這一輪她說過的話。重問也念同一句。"""

    def __init__(self):
        self.line = ""

    async def generate(self, messages, *, tools=None):
        return LLMResponse(text=self.line, model="replay")

    async def stream_generate(self, messages, *, tools=None):
        yield LLMStreamChunk(text=self.line)
        yield LLMStreamChunk(
            final=True, response=LLMResponse(text=self.line, model="replay")
        )


class Recording:
    """背景模型的 client，記下最後一次的原始回答。"""

    def __init__(self, client):
        self.client = client
        self.last = None

    async def generate(self, messages, **kwargs):
        response = await self.client.generate(messages, **kwargs)
        self.last = response.text
        return response


def turns_of(path: Path, limit: int) -> tuple[str, list[tuple[str, str]]]:
    """(她的名字, [(使用者的話, 她的回覆)])，取前 limit 輪。"""
    name, pairs, pending = "", [], None
    for entry in json.loads(path.read_text(encoding="utf-8")):
        role = entry.get("role")
        content = str(entry.get("content") or "").strip()
        if role == "human" and content:
            pending = content
        elif role == "ai" and content and pending is not None:
            name = name or str(entry.get("name") or "")
            pairs.append((pending, content))
            pending = None
    return name or "角色", pairs[:limit]


def parsed(text):
    if text is None:
        return None
    cleaned = (
        text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    )
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": text}
    return data if isinstance(data, dict) else {"raw": text}


def canonical(answer) -> str | None:
    """引擎把這個回答當成哪個心情詞（近義詞照 MOOD_SYNONYMS 換），不是就 None。"""
    if not isinstance(answer, dict):
        return None
    word = str(answer.get("mood") or "").strip().lower()
    word = MOOD_SYNONYMS.get(word, word)
    return word if word in CHARACTER_MOODS else None


# 規則只在觀察夠明顯時才動她的心情，其他時候讓心情維持原樣。
UNCHANGED = "unchanged"


def rule_mood(observation):
    if not isinstance(observation, dict):
        return None
    patch = relationship_patch(
        CharacterState(custom={OBSERVATION_KEY: observation}).snapshot(),
        count_turn=False,
        now=time.time(),
    )
    if patch is None or patch.emotion is None:
        return UNCHANGED
    return patch.emotion, patch.mood_intensity


async def replay(path: Path, args) -> tuple[str, list[dict]]:
    name, pairs = turns_of(path, args.max_turns)

    def model():
        return OpenAICompatibleChatClient(
            model=args.model,
            base_url=args.base_url,
            api_key="not-needed",
            timeout_seconds=None,
            request_options={
                "temperature": 0.1,
                "max_tokens": 600,
                "extra_body": {"reasoning_effort": "none"},
            },
        )

    her, emotion, mood = Replay(), Recording(model()), Recording(model())
    companion = CharacterCompanion(
        character=CharacterProfile(
            id="mood-compare", name=name, description="(replay)"
        ),
        llm=her,
        background_llm={"emotion": emotion, "mood": mood},
        settings=CompanionSettings(
            emotion_every=1,
            mood_every=1,
            memory_every=0,
            self_memory_every=0,
            goal_every=0,
            reflection_every=0,
            summary_every=0,
            call_timeout_seconds=120.0,
        ),
    )

    # 看每個結果實際對她存著的心情做了什麼：包住 commit 與規則，比對前後。
    def stored():
        state = companion.runtime.state
        return state.emotion, state.mood_intensity, state.mood_updated_at

    worker_effects, rule_effects = [], []
    commit = companion._commits.commit

    async def watched_commit(proposal):
        before = stored()
        outcome = await commit(proposal)
        if proposal.target == "state.mood_candidate":
            worker_effects.append(
                (outcome.status.value, outcome.reason, stored() != before)
            )
        return outcome

    companion._commits.commit = watched_commit
    react = companion._react_to_observation

    async def watched_react():
        before = stored()
        await react()
        rule_effects.append(stored() != before)

    companion._react_to_observation = watched_react
    policy = companion.runtime.state_policy
    on_event = policy.on_event

    def watched_on_event(event, state):
        patch = on_event(event, state)
        if patch is not None and patch.custom_updates.get(APPLIED_OBSERVATION_KEY):
            rule_effects.append(patch.emotion is not None)
        return patch

    policy.on_event = watched_on_event

    rows, seen = [], None
    try:
        for number, (user, line) in enumerate(pairs, 1):
            her.line = line
            emotion.last = mood.last = None
            worker_effects.clear()
            rule_effects.clear()
            await companion.reply(user, conversation_id="replay")
            await companion.settle()
            observation = companion.runtime.state.custom.get(OBSERVATION_KEY)
            fresh = (
                isinstance(observation, dict) and observation.get("proposal_id") != seen
            )
            if fresh:
                seen = observation.get("proposal_id")
            answer = parsed(mood.last)
            word, strength, updated_at = stored()
            _, now_strength = effective_mood(
                word, strength, updated_at, now=time.time()
            )
            rows.append(
                {
                    "number": number,
                    "user": user,
                    "her": line,
                    "observation": observation if fresh else None,
                    "rule": rule_mood(observation) if fresh else None,
                    "rule_moved": any(rule_effects),
                    "answer": answer,
                    "worker": worker_effects[-1] if worker_effects else None,
                    "after": (word, strength, now_strength),
                }
            )
            print(f"{path.name} turn {number}/{len(pairs)}", file=sys.stderr)
    finally:
        await companion.close()
    return name, rows


def cell(text) -> str:
    return html.escape(str(text)).replace("\n", "<br>")


def render_row(row: dict, name: str) -> str:
    observation = row["observation"]
    seemed = (
        "（沒有新的觀察）"
        if observation is None
        else f"{observation.get('emotion')}　valence {observation.get('valence', '—')}　"
        f"stance {observation.get('stance', '—')}　強度 {observation.get('intensity')}"
    )
    rule = row["rule"]
    rule_text = (
        "—"
        if rule is None
        else "不變"
        if rule == UNCHANGED
        else f"{rule[0]}（舊稱 {OLD_NAMES[rule[0]]}）　{rule[1]:.2f}"
        if rule[0] in OLD_NAMES
        else f"{rule[0]}　{rule[1]:.2f}"
    )
    if rule is not None and rule != UNCHANGED:
        rule_text += (
            "\n→ 改了她的心情"
            if row["rule_moved"]
            else "\n（這輪有 mood 判斷，規則不動心情）"
        )

    answer = row["answer"]
    if answer is None:
        worker = "（這輪沒有呼叫）"
    elif "raw" in answer:
        worker = f"讀不懂：{answer['raw']}"
    else:
        said = str(answer.get("mood"))
        word = canonical(answer)
        if word is not None and word != said.strip().lower():
            said += f"（當 {word}）"
        effect = row["worker"]
        if effect is None:
            verdict = "不收（解析不過）"
        elif effect[0] != "committed":
            verdict = f"不收（{effect[0]}: {effect[1]}）"
        else:
            verdict = "收 → 採用" if effect[2] else "收 → 保留前一個"
        worker = (
            f"{said}　強度 {answer.get('intensity')}　信心 {answer.get('confidence')}"
            f"\n依據：{'；'.join(map(str, answer.get('evidence') or []))}"
            f"\n{verdict}"
        )
    word, strength, now_strength = row["after"]
    after = f"{word}　{strength:.2f}"
    if abs(now_strength - strength) >= 0.005:
        after += f"（淡到現在 {now_strength:.2f}）"
    cells = [row["number"], row["user"], row["her"], seemed, rule_text, worker, after]
    return "<tr>" + "".join(f"<td>{cell(c)}</td>" for c in cells) + "</tr>"


def render(sections: list[tuple[Path, str, list[dict]]], args) -> str:
    parts = []
    for path, name, rows in sections:
        head = "".join(
            f"<th>{cell(h)}</th>"
            for h in (
                "輪",
                "使用者",
                name,
                "使用者看起來（情緒分析）",
                "規則會推出的心情（只在沒排 mood 判斷的輪生效；本頁每輪都排）",
                "mood worker",
                "這輪之後她的心情",
            )
        )
        body = "".join(render_row(row, name) for row in rows)
        parts.append(
            f"<h2>{cell(path)}</h2><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        )
    style = (
        "body{font-family:-apple-system,'PingFang TC',sans-serif;margin:16px;background:#fff;color:#222}"
        "table{border-collapse:collapse;width:100%;margin-bottom:32px}"
        "th,td{border:1px solid #ccc;padding:6px;vertical-align:top;font-size:14px}"
        "th{background:#f3f3f3;position:sticky;top:0}"
        "@media (prefers-color-scheme:dark){body{background:#1b1b1b;color:#ddd}th{background:#333}td,th{border-color:#555}}"
    )
    meta = f"模型 {args.model} @ {args.base_url}　{datetime.now():%Y-%m-%d %H:%M}"
    return (
        "<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>心情判斷對照</title><style>{style}</style></head><body>"
        f"<h1>她的心情：規則（參考）與 mood worker 並排</h1><p>{cell(meta)}</p>"
        "<p>本頁每輪都排 mood 判斷（mood_every=1）。有 mood 判斷的輪，規則只動信任與好感，"
        "不動她的心情；規則欄是沒排 mood 判斷的輪（預設 mood_every=2 的奇數輪）規則會推出的心情。</p>"
        + "".join(parts)
        + "</body></html>"
    )


async def main(args) -> None:
    sections = []
    for raw in args.conversations:
        path = Path(raw)
        name, rows = await replay(path, args)
        sections.append((path, name, rows))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(sections, args), encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("conversations", nargs="+")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--out", default="docs/superpowers/eval/2026-10-05-mood.html")
    arguments = parser.parse_args()
    if len(arguments.conversations) < 3:
        parser.error("至少三段對話（人讀對照的慣例）")
    asyncio.run(main(arguments))
