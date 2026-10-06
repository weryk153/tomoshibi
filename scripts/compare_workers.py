#!/usr/bin/env python3
"""引擎 1.2.0 的背景工作：舊（1.1）與新（1.2）逐輪並排給人讀。

用法（1.2.0 還沒發版，用引擎 repo 的環境跑；不要用 Tomoshibi 的 uv run，那會把
引擎換回 pyproject 釘的版本）：

    uv run --project ../ai-character-engine python scripts/compare_workers.py \\
        chat_history/<conf_uid>/<history_uid>.json[@起-迄] [...] \\
        [--live 人設.md 台詞.txt ...] \\
        --model qwen/qwen3.5-9b --out-prefix docs/superpowers/eval/2026-10-06-engine-1.2.0

每段對話跑兩次，先新後舊，各用一個只在記憶體裡的 companion：
- 新：引擎現在的提示與程式（1.2）。
- 舊：同一個引擎，四個提示截回 1.1.1 的長度（1.2 只在末尾追加，截掉就是原文；
  引擎的測試用雜湊守著這件事），情緒分析的輸入版面換回 1.1 的，
  plans_stay_in_conversation=False（1.1 的跨對話行為）。
每輪都跑 emotion、memory、self_memory、reflection（goal 每 --goal-every 輪）。
記下模型的原始回答與引擎實際收了什麼；舊欄另外標「1.1 的程式會不會收」。
每段對話最後在一段新對話裡說一句話，列出她心裡的目標、她自己的事、想法。
第五頁是回話自檢（reply_check，1.2.0 新增）：只有新欄，舊欄留空（1.1 沒有這個
工作）；列出每輪找到的問題、引擎收了哪些，與這一輪她收到的上一句提醒。
--pages 只跑指定的頁（例如只看 reply-check 時，舊的那一次與其他工作都不跑）。
重播的紀錄若在 characters/<conf_uid>.yaml 找得到人設（persona_prompt），就跟
Tomoshibi 一樣當 background 給引擎（回話自檢拿它對照人設）。

對話檔後面可加 @起-迄（第幾輪到第幾輪，從 1 起算），起之前的輪只當歷史載入，
不跑背景。--live 的人設與台詞跟 compare_mood.py 一樣；她的回覆在新的那一次
現場生成，舊的那一次照念同樣的話。

輸出五頁：<out-prefix>-memory.html、-self-memory.html、-reflection.html、
-emotion.html、-reply-check.html。只讀對話檔，不寫回任何東西。
"""

import argparse
import asyncio
import html
import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

from ai_character_engine import CharacterProfile
from ai_character_engine.cognition import background
from ai_character_engine.cognition.background import (
    REPLY_CHECK_KINDS,
    REPLY_FIX_CHARS,
    REPLY_NOTE_TARGET,
    BackgroundCognitionKind,
    _echoes,
    _her_lines,
    _line_quoted,
    _lines_the_user_said,
    _replies_around,
    _user_lines,
)
from ai_character_engine.companion import CharacterCompanion, CompanionSettings
from ai_character_engine.companion.companion import REPLY_NOTE_LINE
from ai_character_engine.context.builder import SELF_MEMORY_LINE, is_turn_context
from ai_character_engine.llm.local import OpenAICompatibleChatClient
from ai_character_engine.llm.models import LLMResponse, LLMStreamChunk, Message
from ai_character_engine.memory.evidence import classify_user_text
from ai_character_engine.memory.self_kinds import (
    self_memory_kind,
    stays_in_conversation,
)

KINDS = {
    "memory": BackgroundCognitionKind.MEMORY_EXTRACTION,
    "self-memory": BackgroundCognitionKind.SELF_MEMORY_EXTRACTION,
    "reflection": BackgroundCognitionKind.REFLECTION,
    "emotion": BackgroundCognitionKind.EMOTION_ANALYSIS,
    "reply-check": BackgroundCognitionKind.REPLY_CHECK,
}
# 每頁要開的工作（CompanionSettings 的 *_every）。
SETTING_OF = {
    "memory": "memory_every",
    "self-memory": "self_memory_every",
    "reflection": "reflection_every",
    "emotion": "emotion_every",
    "reply-check": "reply_check_every",
}
# 1.1 也有的工作；只要這些頁才需要跑舊的那一次。
OLD_PAGES = ("memory", "self-memory", "reflection", "emotion")
TITLES = {
    "memory": "她記得的使用者（memory）",
    "self-memory": "她自己說的事（self_memory）",
    "reflection": "她的想法（reflection）",
    "emotion": "使用者的情緒（emotion）",
    "reply-check": "回話自檢（reply_check）",
}
# 1.1.1 的提示長度；跟引擎 tests/test_background_cognition.py 的 PROMPTS_OF_1_1 同一組。
LENGTH_IN_1_1 = {
    BackgroundCognitionKind.MEMORY_EXTRACTION: 906,
    BackgroundCognitionKind.SELF_MEMORY_EXTRACTION: 1244,
    BackgroundCognitionKind.REFLECTION: 634,
    BackgroundCognitionKind.EMOTION_ANALYSIS: 551,
}
NEW_PROMPTS = background._SYSTEM_PROMPTS
NEW_EARLIER_LINES = background._earlier_user_lines
NEW_EARLIER_TITLE = background._EARLIER_USER_LINES
FRESH = "（新的一段對話）"


def old_earlier_lines(history):
    """1.1 的情緒分析：最新一句也在前文裡，事件也在。"""
    return [message for message in history if message.role != "assistant"]


@contextmanager
def prompts(variant: str):
    """old：四個提示截回 1.1.1、情緒分析的輸入換回 1.1 的版面。離開時換回來。"""
    if variant == "old":
        background._SYSTEM_PROMPTS = MappingProxyType(
            {
                kind: text[: LENGTH_IN_1_1[kind]] if kind in LENGTH_IN_1_1 else text
                for kind, text in NEW_PROMPTS.items()
            }
        )
        background._earlier_user_lines = old_earlier_lines
        background._EARLIER_USER_LINES = "Recent transcript"
    try:
        yield
    finally:
        background._SYSTEM_PROMPTS = NEW_PROMPTS
        background._earlier_user_lines = NEW_EARLIER_LINES
        background._EARLIER_USER_LINES = NEW_EARLIER_TITLE


class Replay:
    """她那一側：照紀錄念出這一輪她說過的話，記下每次收到的訊息。"""

    def __init__(self):
        self.line = ""
        self.calls = []

    async def generate(self, messages, *, tools=None):
        self.calls.append(list(messages))
        return LLMResponse(text=self.line, model="replay")

    async def stream_generate(self, messages, *, tools=None):
        self.calls.append(list(messages))
        yield LLMStreamChunk(text=self.line)
        yield LLMStreamChunk(
            final=True, response=LLMResponse(text=self.line, model="replay")
        )


class Live:
    """她那一側：現場生成，記下每次收到的訊息。"""

    def __init__(self, client):
        self.client = client
        self.calls = []

    async def generate(self, messages, *, tools=None):
        self.calls.append(list(messages))
        return await self.client.generate(messages, tools=tools)

    async def stream_generate(self, messages, *, tools=None):
        self.calls.append(list(messages))
        async for chunk in self.client.stream_generate(messages, tools=tools):
            yield chunk


def model(args, temperature=0.1, max_tokens=800):
    return OpenAICompatibleChatClient(
        model=args.model,
        base_url=args.base_url,
        api_key="not-needed",
        timeout_seconds=None,
        request_options={
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": {"reasoning_effort": "none"},
        },
    )


def pairs_of(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """(她的名字, [(使用者的話, 她的回覆)])。"""
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
    return name or "角色", pairs


def persona_of(path: Path) -> str:
    """紀錄所屬角色的人設（characters/<conf_uid>.yaml 的 persona_prompt），跟
    Tomoshibi 給引擎的 background 一樣；找不到就空字串。不裝 yaml，只讀那一段。"""
    source = Path("characters") / f"{path.parent.name}.yaml"
    if not source.is_file():
        return ""
    lines, inside, indent = [], False, 0
    for line in source.read_text(encoding="utf-8").splitlines():
        if not inside:
            if line.strip().startswith("persona_prompt:"):
                inside, indent = True, len(line) - len(line.lstrip())
            continue
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        lines.append(line.strip())
    return "\n".join(lines).strip()


def conversation_arg(raw: str) -> tuple[Path, int, int | None]:
    """「檔案@起-迄」→（檔案, 起, 迄）；沒寫範圍就是全部。"""
    path, _, span = raw.partition("@")
    if not span:
        return Path(path), 1, None
    start, _, end = span.partition("-")
    return Path(path), int(start), int(end) if end else None


def live_of(persona: Path, script: Path) -> tuple[str, str, list[str]]:
    description = persona.read_text(encoding="utf-8").strip()
    first = description.splitlines()[0].strip() if description else ""
    name = first.removeprefix("#").strip() if first.startswith("#") else persona.stem
    lines = [
        line.strip()
        for line in script.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return name or persona.stem, description, lines


def reason(exc: BaseException) -> str:
    if isinstance(exc, (asyncio.CancelledError, TimeoutError)):
        return f"{type(exc).__name__}（逾時或被取消）"
    text = str(exc).strip()
    return f"{type(exc).__name__}：{text}" if text else type(exc).__name__


async def converse(
    variant, name, description, earlier, turns, her, args, persona=None
) -> dict:
    """跑一個 variant。turns 是 [(使用者, 她或 None)]；None 由 her 現場生成。"""
    seen: list[tuple] = []
    original = background.StructuredBackgroundWorker._normalize
    original_call = background.StructuredBackgroundWorker.__call__
    recorded: set[int] = set()

    def recording(worker, context, data):
        try:
            out = original(worker, context, data)
        except Exception as exc:
            recorded.add(id(exc))
            seen.append(
                (worker.spec.kind, context, dict(data), None, worker, reason(exc))
            )
            raise
        seen.append((worker.spec.kind, context, dict(data), out, worker, None))
        return out

    async def calling(worker, context):
        """呼叫本身失敗（逾時、取消、回的不是 JSON）也記下來，不然看起來像沒跑。"""
        try:
            return await original_call(worker, context)
        except BaseException as exc:
            if id(exc) not in recorded:
                seen.append((worker.spec.kind, context, {}, None, worker, reason(exc)))
            raise

    worker = model(args)
    clients = {
        "emotion": worker,
        "memory": worker,
        "self_memory": worker,
        "reflection": worker,
        "goal": worker,
        "reply_check": worker,
    }
    wanted = set(args.pages)
    every = {
        setting: int(page in wanted and (variant == "new" or page in OLD_PAGES))
        for page, setting in SETTING_OF.items()
    }
    companion = CharacterCompanion(
        character=CharacterProfile(
            id="workers-compare",
            name=name,
            description=description,
            background=persona or (description if args.live else None),
        ),
        llm=her,
        background_llm=clients,
        settings=CompanionSettings(
            **every,
            mood_every=0,
            goal_every=args.goal_every if wanted & set(OLD_PAGES) else 0,
            summary_every=0,
            call_timeout_seconds=180.0,
            plans_stay_in_conversation=variant == "new",
            language=args.language,
        ),
    )
    commits = []
    commit = companion._commits.commit

    async def watched(proposal):
        outcome = await commit(proposal)
        commits.append((proposal, outcome))
        return outcome

    companion._commits.commit = watched
    if earlier:
        companion.load_conversation(
            "replay",
            [
                message
                for user, line in earlier
                for message in (Message("user", user), Message("assistant", line))
            ],
        )
    rows = []
    background.StructuredBackgroundWorker._normalize = recording
    background.StructuredBackgroundWorker.__call__ = calling
    try:
        with prompts(variant):
            for number, (user, line) in turns:
                seen.clear()
                commits.clear()
                if line is not None:
                    her.line = line
                asked = len(her.calls)
                result = await companion.reply(user, conversation_id="replay")
                await companion.settle()
                rows.append(
                    {
                        "number": number,
                        "user": user,
                        "her": result.text if line is None else line,
                        "readings": list(seen),
                        "commits": list(commits),
                        "told": told(her.calls, asked),
                    }
                )
                print(f"{variant} {name} turn {number}", file=sys.stderr)
            if isinstance(her, Replay):
                her.line = "嗨。"
            await companion.reply(FRESH, conversation_id="fresh", skip_memory=True)
            fresh = in_mind(her.calls[-1], companion)
    finally:
        background.StructuredBackgroundWorker._normalize = original
        background.StructuredBackgroundWorker.__call__ = original_call
        await companion.close()
    return {"rows": rows, "fresh": fresh}


def told(calls, asked) -> list[str]:
    """這一輪她的提示裡「上一句的提醒」：只看這一輪的備註（緊接在使用者這句
    之前的那則）；之前輪的備註留在對話裡，不算。"""
    if len(calls) <= asked or len(calls[asked]) < 2:
        return []
    note = calls[asked][-2]
    if not is_turn_context(note):
        return []
    return [
        line for line in note.content.splitlines() if line.startswith(REPLY_NOTE_LINE)
    ]


def in_mind(messages, companion) -> dict:
    """新對話那一句時，她的提示裡有什麼，與 snapshot。"""
    context = "\n".join(
        message.content
        for message in messages
        if message.role == "system" or is_turn_context(message)
    )
    lines = context.splitlines()
    snapshot = companion.snapshot()
    return {
        "goals": [line for line in lines if line.startswith("- goal: ")],
        "self": [line for line in lines if line.startswith(SELF_MEMORY_LINE)],
        "thoughts": [line for line in lines if line.startswith("- thought: ")],
        "snapshot_goals": list(snapshot.goals),
        "snapshot_thoughts": list(snapshot.thoughts),
    }


# --- 判讀：一筆模型回答在新舊程式下收不收 ----------------------------------------


def committed(commits, target, key, value) -> str:
    for proposal, outcome in commits:
        if proposal.target == target and str(proposal.payload.get(key, "")) == value:
            return outcome.status.value
    return ""


def memory_items(reading, commits, variant) -> list[str]:
    _, context, data, _, worker, error = reading
    if error:
        return [f"這輪呼叫失敗：{error}"]
    users = _user_lines(context, turns=worker.spec.every_n_revisions)
    hers = _her_lines(context, worker.history_messages)
    out = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        summary = str(raw.get("summary", "")).strip()
        quote = str(raw.get("evidence") or "")
        source = _line_quoted(quote, users)
        if "evidence" not in raw:
            new, old = "丟：沒有引文", "收"
        elif not quote.strip():
            new = old = "丟：沒有引文"
        elif source is None:
            new = old = "丟：不是使用者說的"
        elif classify_user_text(source) != "asserted_fact":
            new = old = f"丟：{classify_user_text(source)}"
        elif _echoes(quote, hers):
            new, old = "丟：跟著她念的", "收"
        else:
            new = old = "收"
        status = committed(commits, "memory.append_candidate", "summary", summary)
        verdict = new if variant == "new" else f"1.1 程式：{old}"
        out.append(
            f"{summary}\n　「{quote}」　信心 {raw.get('confidence')}\n　{verdict}"
            + (f"（commit：{status}）" if status else "")
        )
    return out or ["（沒有項目）"]


def self_memory_items(reading, commits, variant) -> list[str]:
    _, context, data, _, worker, error = reading
    if error:
        return [f"這輪呼叫失敗：{error}"]
    out = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        summary = str(raw.get("summary", "")).strip()
        named = str(raw.get("kind", ""))
        kind = self_memory_kind(named)
        if variant == "new":
            where = "綁這段對話" if stays_in_conversation(kind) else "跨對話"
            kind_text = kind if kind == named.strip() else f"{named} → {kind}"
        else:
            where, kind_text = "跨對話（1.1）", named
        status = committed(commits, "memory.self_candidate", "summary", summary)
        out.append(
            f"{summary}\n　kind {kind_text}　{where}\n　「{raw.get('evidence')}」"
            + (
                f"\n　commit：{status}"
                if status
                else "\n　（沒提交：引文不在她的話裡或是問句）"
            )
        )
    return out or ["（沒有項目）"]


def reflection_items(reading, commits, variant) -> list[str]:
    _, context, data, _, worker, error = reading
    if error:
        return [f"這輪呼叫失敗：{error}"]
    users = _lines_the_user_said(context, worker.history_messages)
    hers = _her_lines(context, worker.history_messages)
    latest_type = context.request.payload.get("memory_evidence_type")
    quotes = []
    for quote in data.get("evidence") or []:
        quote = str(quote).strip()
        source = _line_quoted(quote, users)
        if source is not None:
            label = f"使用者原話（{classify_user_text(source)}）"
        elif _line_quoted(quote, hers) is not None:
            label = "她的話"
        else:
            label = "改寫或沒出現"
        if variant == "old":
            label += f"；1.1 照收（{latest_type}）"
        quotes.append(f"　「{quote}」　{label}")
    insight = str(data.get("insight", ""))
    status = committed(commits, "cognition.reflection_candidate", "insight", insight)
    proposed = any(p.target == "cognition.reflection_candidate" for p, _ in commits)
    if status:
        done = f"commit：{status}"
    elif not proposed:
        done = "沒提案（沒有使用者原話）"
    else:
        done = "提案了但沒提交"
    # 舊欄的處置是 1.2 的程式對這份（1.1 提示的）回答做的事；1.1 的程式不查引文，
    # 照樣提案。
    verdict = (
        done
        if variant == "new"
        else f"1.2 的程式會：{done}／1.1 的程式會：照樣提案（不查引文）"
    )
    return [
        f"{insight}\n　belief：{json.dumps(data.get('belief_candidate'), ensure_ascii=False)}"
        f"　信心 {data.get('confidence')}\n" + "\n".join(quotes) + f"\n　{verdict}"
    ]


def emotion_items(reading, commits, variant) -> list[str]:
    _, _, data, _, _, error = reading
    if error:
        return [f"這輪呼叫失敗：{error}"]
    return [
        f"{data.get('emotion')}　強度 {data.get('intensity')}　valence {data.get('valence')}"
        f"　stance {data.get('stance')}　信心 {data.get('confidence')}\n"
        f"　依據：{'；'.join(map(str, data.get('evidence') or []))}"
    ]


def reply_check_items(reading, commits, variant) -> list[str]:
    _, context, data, normalized, worker, error = reading
    if error:
        return [f"這輪呼叫失敗：{error}"]
    reply = _replies_around(context, worker.history_messages)[1]
    issues = data.get("issues")
    if not isinstance(issues, list):
        return [f"回答裡沒有 issues 陣列：{json.dumps(data, ensure_ascii=False)}"]
    # 先過字面的檢查（normalize），off_persona／broke_character 再問一次；
    # 最後收的是送去 commit 的那份。
    passed = {
        (item["kind"], item["evidence"])
        for item in (normalized[0] if normalized else ())
    }
    kept = {
        (item["kind"], item["evidence"])
        for proposal, _ in commits
        if proposal.target == REPLY_NOTE_TARGET
        for item in proposal.payload["issues"]
    }
    out = []
    for raw in issues:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "").strip().casefold()
        quote = str(raw.get("evidence") or "").strip()
        fix = str(raw.get("fix") or "").strip()
        against = str(raw.get("against") or "").strip()
        if (kind, quote) in kept:
            verdict = "收" + ("（fix 截短）" if len(fix) > REPLY_FIX_CHARS else "")
        elif (kind, quote) in passed:
            verdict = "丟：再問一次，模型答不是"
        elif kind not in REPLY_CHECK_KINDS:
            verdict = "丟：kind 不在清單"
        elif not fix:
            verdict = "丟：沒有 fix"
        elif _line_quoted(quote, [reply]) is None:
            verdict = "丟：引文不是她這輪說的"
        else:
            verdict = "丟：字面對不上這個 kind（或超過兩項）"
        out.append(
            f"{raw.get('kind')}\n　「{quote}」"
            + (f"\n　對照：「{against}」" if against else "")
            + f"\n　→ {fix}\n　{verdict}"
        )
    status = next(
        (o.status.value for p, o in commits if p.target == REPLY_NOTE_TARGET), ""
    )
    if status:
        out.append(f"commit：{status}")
    return out or ["（沒有問題）"]


ITEMS = {
    "memory": memory_items,
    "self-memory": self_memory_items,
    "reflection": reflection_items,
    "emotion": emotion_items,
    "reply-check": reply_check_items,
}


def negative(reading) -> bool:
    if reading is None or reading[5]:
        return False
    data = reading[2]
    try:
        return (
            float(data.get("valence") or 0) <= -0.3
            or float(data.get("stance") or 0) <= -0.3
        )
    except (TypeError, ValueError):
        return False


def reading_of(row, kind):
    return next((r for r in row["readings"] if r[0] is kind), None)


# --- 頁面 ------------------------------------------------------------------------


def cell(text) -> str:
    return html.escape(str(text)).replace("\n", "<br>")


def column(row, page, variant) -> str:
    if page == "reply-check" and variant == "old":
        return "（1.1 沒有這個工作）"
    reading = reading_of(row, KINDS[page])
    if reading is None:
        text = "（這輪沒有跑）"
    else:
        text = "\n".join(ITEMS[page](reading, row["commits"], variant))
    if page == "reply-check":
        received = "\n".join(row.get("told") or []) or "（無）"
        text = f"這一輪她收到的提醒：{received}\n——\n{text}"
    return text


def section(page, label, name, runs) -> str:
    new_rows, old_rows = runs["new"]["rows"], runs["old"]["rows"]
    body = []
    for index, (new, old) in enumerate(zip(new_rows, old_rows)):
        mark = ""
        if page == "emotion" and index > 0:
            before = [
                reading_of(rows[index - 1], KINDS["emotion"])
                for rows in (new_rows, old_rows)
            ]
            if any(negative(r) for r in before):
                mark = "\n⚠ 負面輪之後"
        cells = [
            f"{new['number']}{mark}",
            new["user"],
            new["her"],
            column(old, page, "old"),
            column(new, page, "new"),
        ]
        body.append("<tr>" + "".join(f"<td>{cell(c)}</td>" for c in cells) + "</tr>")
    head = "".join(
        f"<th>{cell(h)}</th>"
        for h in ("輪", "使用者", name, "舊（1.1 提示）", "新（1.2 提示與程式）")
    )
    parts = [
        f"<h2>{cell(label)}</h2><table><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    ]
    if page == "self-memory":
        parts.append(fresh_box(runs))
    return "".join(parts)


def fresh_box(runs) -> str:
    rows = []
    for title, key in (
        ("目標（她的提示裡）", "goals"),
        ("她自己的事（她的提示裡）", "self"),
        ("想法（她的提示裡）", "thoughts"),
        ("snapshot().goals", "snapshot_goals"),
        ("snapshot().thoughts", "snapshot_thoughts"),
    ):
        old = "\n".join(runs["old"]["fresh"][key]) or "（無）"
        new = "\n".join(runs["new"]["fresh"][key]) or "（無）"
        rows.append(
            f"<tr><td>{cell(title)}</td><td>{cell(old)}</td><td>{cell(new)}</td></tr>"
        )
    return (
        f"<h3>開一段新對話說「{cell(FRESH)}」時她心裡有什麼</h3>"
        "<table><thead><tr><th></th><th>舊（1.1）</th><th>新（1.2）</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render(page, sections, args) -> str:
    style = (
        "body{font-family:-apple-system,'PingFang TC',sans-serif;margin:16px;background:#fff;color:#222}"
        "table{border-collapse:collapse;width:100%;margin-bottom:32px}"
        "th,td{border:1px solid #ccc;padding:6px;vertical-align:top;font-size:14px}"
        "th{background:#f3f3f3;position:sticky;top:0}"
        "@media (prefers-color-scheme:dark){body{background:#1b1b1b;color:#ddd}th{background:#333}td,th{border-color:#555}}"
    )
    meta = (
        f"模型 {args.model} @ {args.base_url}　goal_every={args.goal_every}"
        f"　language={args.language or '（空）'}"
        f"　{datetime.now():%Y-%m-%d %H:%M}"
    )
    note = (
        "舊欄：1.1.1 的提示（截掉 1.2 追加的句子）在 1.2 的引擎上跑，跨對話行為照 1.1；"
        "每個項目另標 1.1 的程式會不會收。新欄：1.2 的提示與程式，標的是引擎實際的處置。"
    )
    if page == "reply-check":
        note = (
            "回話自檢是 1.2.0 新增的工作，舊欄留空。新欄：模型回報的每個問題（kind／她的原句／"
            "給她的提醒）與引擎的處置；「這一輪她收到的提醒」是上一輪的問題被帶進這一輪提示的那幾行。"
            "重播的對話她照念紀錄，提醒不會改變她說的話；現場生成的才看得出她有沒有照做。"
        )
    body = "".join(section(page, *item) for item in sections)
    return (
        "<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{cell(TITLES[page])}</title><style>{style}</style></head><body>"
        f"<h1>引擎 1.2.0：{cell(TITLES[page])}　舊與新並排</h1>"
        f"<p>{cell(meta)}</p><p>{cell(note)}</p>{body}</body></html>"
    )


def skipped(new) -> dict:
    """沒跑的舊的那一次：每輪空白。"""
    return {
        "rows": [
            {**row, "readings": [], "commits": [], "told": []} for row in new["rows"]
        ],
        "fresh": {key: [] for key in new["fresh"]},
    }


async def main(args) -> None:
    sections = []
    for raw in args.conversations:
        path, start, end = conversation_arg(raw)
        name, pairs = pairs_of(path)
        end = min(end or len(pairs), len(pairs), start - 1 + args.max_turns)
        earlier = pairs[: start - 1]
        turns = [(n, pairs[n - 1]) for n in range(start, end + 1)]
        runs = {}
        for variant in ("new", "old"):
            if variant == "old" and not set(args.pages) & set(OLD_PAGES):
                runs["old"] = skipped(runs["new"])
                continue
            runs[variant] = await converse(
                variant,
                name,
                "(replay)",
                earlier,
                [(n, (u, line)) for n, (u, line) in turns],
                Replay(),
                args,
                persona=persona_of(path),
            )
        sections.append((f"{path}　第 {start}–{end} 輪", name, runs))
    for persona, script in args.live or ():
        name, description, lines = live_of(Path(persona), Path(script))
        turns = [(n, (user, None)) for n, user in enumerate(lines, 1)]
        new = await converse(
            "new", name, description, [], turns, Live(model(args, 0.7, 400)), args
        )
        said = [(row["number"], (row["user"], row["her"])) for row in new["rows"]]
        if set(args.pages) & set(OLD_PAGES):
            old = await converse("old", name, description, [], said, Replay(), args)
        else:
            old = skipped(new)
        sections.append(
            (f"{persona}（現場生成，舊的一次照念）", name, {"new": new, "old": old})
        )
    for page in args.pages:
        out = Path(f"{args.out_prefix}-{page}.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(page, sections, args), encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("conversations", nargs="*", help="對話檔，可加 @起-迄")
    parser.add_argument(
        "--live", nargs=2, action="append", metavar=("PERSONA_MD", "SCRIPT_TXT")
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-turns", type=int, default=16)
    parser.add_argument(
        "--goal-every", type=int, default=2, help="幾輪跑一次 goal（0 不跑）"
    )
    parser.add_argument(
        "--out-prefix", default="docs/superpowers/eval/2026-10-06-engine-1.2.0"
    )
    parser.add_argument(
        "--language",
        default="",
        help="CompanionSettings.language，跟 Tomoshibi 一樣用角色的回話語言"
        "（例如 Traditional Chinese (Taiwan)）；預設空",
    )
    parser.add_argument(
        "--pages",
        nargs="+",
        choices=list(KINDS),
        default=list(KINDS),
        help="只跑這幾頁（預設全部）",
    )
    arguments = parser.parse_args()
    if len(arguments.conversations) + len(arguments.live or ()) < 3:
        parser.error("至少三段對話（人讀對照的慣例）")
    asyncio.run(main(arguments))
