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
第六頁是記憶衝突（memory-conflicts，memory_conflict 工作）：只有新欄；每輪記下的
使用者記憶、每次觸發的候選、模型的關係判定（含再問一次的回答）、採用與否，與這一輪
她收到的「問哪個才對」提醒。頁首統計採用的 supersedes／contradicts，逐筆列出給人判
誤判（supersedes 會讓真事實消失）。
--pages 只跑指定的頁（例如只看 reply-check 時，舊的那一次與其他工作都不跑）。
第六、七頁是她的日記（diary）與使用者狀態摘要（user-state），也只有新欄：
user-state 每 --user-state-every 輪一列（她讀到的使用者原句、情緒序列、模型的回答
與引擎收了什麼）；diary 是每段對話重播完後 write_diary() 一篇，列出她那天的材料
（摘要、使用者告訴她的、她自己說的、她對使用者的看法、心情、目標）、模型的回答、
引擎的處置，與下一段新對話時系統提示裡的那兩句。跑 diary 時其他工作照 Tomoshibi
的預設開（emotion 1、memory 2、self_memory 2、mood 2、goal 4），summary 每
--summary-every 輪（Tomoshibi 預設 0，日記才有摘要可讀）。
重播的紀錄若在 characters/<conf_uid>.yaml 找得到人設（persona_prompt），就跟
Tomoshibi 一樣當 background 給引擎（回話自檢拿它對照人設）。

對話檔後面可加 @起-迄（第幾輪到第幾輪，從 1 起算），起之前的輪只當歷史載入，
不跑背景。--live 的人設與台詞跟 compare_mood.py 一樣；她的回覆在新的那一次
現場生成，舊的那一次照念同樣的話。

輸出：<out-prefix>-memory.html、-self-memory.html、-reflection.html、
-emotion.html、-reply-check.html、-memory-conflicts.html（--pages 選的那幾頁）。
只讀對話檔，不寫回任何東西。
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
    _CHANGE_QUESTION,
    MEMORY_CONFLICT_TARGET,
    REPLY_CHECK_KINDS,
    REPLY_FIX_CHARS,
    REPLY_NOTE_TARGET,
    USER_STATE_TARGET,
    BackgroundCognitionKind,
    _diary_sections,
    _diary_text,
    _not_of_the_day,
    _echoes,
    _her_lines,
    _line_quoted,
    _lines_the_user_said,
    _replies_around,
    _user_lines,
)
from ai_character_engine.companion import CharacterCompanion, CompanionSettings
from ai_character_engine.companion.companion import CONFLICT_NOTES, REPLY_NOTE_LINE
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
    "user-state": BackgroundCognitionKind.USER_STATE,
    "diary": BackgroundCognitionKind.DIARY,
    "memory-conflicts": BackgroundCognitionKind.MEMORY_CONFLICT,
}
# 每頁要開的工作（CompanionSettings 的 *_every）。
SETTING_OF = {
    "memory": "memory_every",
    "self-memory": "self_memory_every",
    "reflection": "reflection_every",
    "emotion": "emotion_every",
    "reply-check": "reply_check_every",
}
# 只有新欄的頁（1.1 沒有這些工作）。
NEW_ONLY = ("reply-check", "user-state", "diary")
# 記憶衝突跟在 memory 後面：要 memory 每輪跑，再開 memory_conflicts。
CONFLICT_PAGE = "memory-conflicts"
# 1.1 也有的工作；只要這些頁才需要跑舊的那一次。
OLD_PAGES = ("memory", "self-memory", "reflection", "emotion")
TITLES = {
    "memory": "她記得的使用者（memory）",
    "self-memory": "她自己說的事（self_memory）",
    "reflection": "她的想法（reflection）",
    "emotion": "使用者的情緒（emotion）",
    "reply-check": "回話自檢（reply_check）",
    "user-state": "使用者狀態摘要（user_state）",
    "diary": "她的日記（diary）",
    "memory-conflicts": "記憶衝突（memory_conflict）",
}
# 她收到的「問哪個才對」提醒：每種語言框架裡「之前」那段之前的字。
CONFLICT_NOTE_HEADS = tuple(
    frame.split("{earlier}")[0] for frame in CONFLICT_NOTES.values()
)
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


class Asked:
    """背景模型：照常呼叫，另外記下記憶衝突「再問一次」的問與答。"""

    def __init__(self, client):
        self.client = client
        self.again: list[tuple[str, str]] = []

    async def generate(self, messages, *, tools=None):
        response = await self.client.generate(messages, tools=tools)
        if messages and messages[0].content == _CHANGE_QUESTION:
            self.again.append((messages[-1].content, response.text))
        return response


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
    original_again = background.StructuredBackgroundWorker._diary_again
    recorded: set[int] = set()
    asked_again: list[tuple[dict, dict]] = []

    async def again(worker, context, messages, answered, data):
        """日記：第一次的回答，與再問一次之後的回答（沒再問就是同一份）。"""
        out = await original_again(worker, context, messages, answered, data)
        asked_again.append((dict(data), dict(out)))
        return out

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

    worker = Asked(model(args))
    clients = {
        "emotion": worker,
        "memory": worker,
        "self_memory": worker,
        "reflection": worker,
        "goal": worker,
        "reply_check": worker,
        "mood": worker,
        "summary": worker,
        "user_state": worker,
        "diary": worker,
        "memory_conflict": worker,
    }
    wanted = set(args.pages)
    every = {
        setting: int(page in wanted and (variant == "new" or page in OLD_PAGES))
        for page, setting in SETTING_OF.items()
    }
    diary = "diary" in wanted and variant == "new"
    extra = {
        "mood_every": 0,
        "summary_every": 0,
        "user_state_every": args.user_state_every
        if "user-state" in wanted and variant == "new"
        else 0,
        # 日記只在重播完後手動寫一篇。
        "diary_every_hours": 0,
    }
    if "user-state" in wanted and variant == "new":
        # 使用者狀態要讀情緒序列。
        every["emotion_every"] = 1
    if diary:
        # 日記的材料：照 Tomoshibi 的預設開，再加摘要。
        every.update(emotion_every=1, memory_every=2, self_memory_every=2)
        extra.update(mood_every=2, summary_every=args.summary_every)
    conflicts = CONFLICT_PAGE in wanted and variant == "new"
    if conflicts:
        every["memory_every"] = 1
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
            **extra,
            goal_every=args.goal_every if wanted & set(OLD_PAGES) or diary else 0,
            call_timeout_seconds=180.0,
            plans_stay_in_conversation=variant == "new",
            language=args.language,
            memory_conflicts=conflicts,
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
    background.StructuredBackgroundWorker._diary_again = again
    try:
        with prompts(variant):
            for number, (user, line) in turns:
                seen.clear()
                commits.clear()
                worker.again.clear()
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
                        "asked_again": list(worker.again),
                        "conflict_notes": told(her.calls, asked, CONFLICT_NOTE_HEADS),
                    }
                )
                print(f"{variant} {name} turn {number}", file=sys.stderr)
            written = None
            if diary:
                seen.clear()
                asked_again.clear()
                entry = await companion.write_diary()
                written = {
                    "entry": entry,
                    "reading": next(
                        (r for r in seen if r[0] is BackgroundCognitionKind.DIARY), None
                    ),
                    "first": asked_again[0][0] if asked_again else None,
                }
                print(f"{variant} {name} diary", file=sys.stderr)
            if isinstance(her, Replay):
                her.line = "嗨。"
            await companion.reply(FRESH, conversation_id="fresh", skip_memory=True)
            fresh = in_mind(her.calls[-1], companion)
            if written is not None:
                written["in_prompt"] = fresh.get("diary", [])
    finally:
        background.StructuredBackgroundWorker._normalize = original
        background.StructuredBackgroundWorker.__call__ = original_call
        background.StructuredBackgroundWorker._diary_again = original_again
        await companion.close()
    return {"rows": rows, "fresh": fresh, "diary": written}


def told(calls, asked, heads=(REPLY_NOTE_LINE,)) -> list[str]:
    """這一輪她的提示裡「上一句的提醒」（或 heads 開頭的其他提醒）：只看這一輪
    的備註（緊接在使用者這句之前的那則）；之前輪的備註留在對話裡，不算。"""
    if len(calls) <= asked or len(calls[asked]) < 2:
        return []
    note = calls[asked][-2]
    if not is_turn_context(note):
        return []
    return [
        line
        for line in note.content.splitlines()
        if any(
            line.removeprefix("For the next reply only: ").startswith(h) for h in heads
        )
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
        "diary": _diary_in(messages),
    }


def _diary_in(messages) -> list[str]:
    """系統提示裡她的日記那一段（標題與那兩句）。"""
    system = next((m.content for m in messages if m.role == "system"), "")
    for part in system.split("\n\n"):
        if part.startswith("From your diary"):
            return part.splitlines()
    return []


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


def user_state_items(reading, commits, variant) -> list[str]:
    _, context, data, normalized, worker, error = reading
    if error:
        return [f"這輪呼叫失敗：{error}"]
    payload = context.request.payload
    said = background._state_lines(context, turns=worker.spec.every_n_revisions)
    hers = _her_lines(context, worker.history_messages)
    emotions = [
        f"{e.get('emotion')}（valence {e.get('valence')}，stance {e.get('stance')}）"
        for e in payload.get("user_emotions") or ()
    ]
    out = [
        "讀到的使用者原句：\n" + "\n".join(f"　{line}" for line in said),
        "情緒序列：" + ("、".join(emotions) or "（無）"),
        f"模型：energy {data.get('energy')}　trend {data.get('mood_trend')}",
    ]
    kept = normalized[0] if normalized and normalized[0] else {}
    for raw in data.get("concerns") or []:
        if not isinstance(raw, dict):
            continue
        concern = str(raw.get("concern") or "")
        quote = str(raw.get("evidence") or "")
        if concern[:30].strip() in (kept.get("concerns") or []):
            verdict = "收"
        elif _line_quoted(quote, said) is None:
            verdict = "丟：引文不是使用者這段的原句"
        elif _echoes(quote, hers):
            verdict = "丟：跟著她念的"
        else:
            verdict = "丟：診斷字眼、語言不對或超過三項"
        out.append(f"concern：{concern}\n　「{quote}」\n　{verdict}")
    for quote in data.get("evidence") or []:
        mark = "原句" if _line_quoted(str(quote), said) is not None else "改寫或沒出現"
        out.append(f"evidence：「{quote}」（{mark}）")
    if kept:
        lately = f"energy {kept['energy']}, mood {kept['mood_trend']}" + (
            f"; concerns: {', '.join(kept['concerns'])}" if kept["concerns"] else ""
        )
        out.append(f"引擎收下：{lately}")
    else:
        out.append("引擎沒收（energy／trend 不在詞彙裡）")
    status = next(
        (o.status.value for p, o in commits if p.target == USER_STATE_TARGET), ""
    )
    if status:
        out.append(f"commit：{status}")
    return out


def conflict_judgements(row):
    """這一輪每次觸發：(新事實, 候選 [(label, 摘要)], 模型原答, 判定列 [(label, 關係,
    理由, 處置)], commit 狀態)。"""
    out = []
    readings = [
        r for r in row["readings"] if r[0] is BackgroundCognitionKind.MEMORY_CONFLICT
    ]
    for _, context, data, normalized, _, error in readings:
        payload = context.request.payload
        new = payload.get("new_memory") or {}
        candidates = [
            (f"m{n}", str(item.get("id")), str(item.get("summary") or ""))
            for n, item in enumerate(payload.get("candidates") or (), 1)
        ]
        by_label = {label: (old_id, summary) for label, old_id, summary in candidates}
        by_label.update(
            {old_id: (old_id, summary) for _, old_id, summary in candidates}
        )
        passed = {item["old_id"] for item in (normalized[0] if normalized else ())}
        final, status = {}, ""
        for proposal, outcome in row["commits"]:
            if proposal.target == MEMORY_CONFLICT_TARGET and proposal.payload.get(
                "new_id"
            ) == new.get("id"):
                status = outcome.status.value
                for item in (
                    outcome.metadata.get("applied") or proposal.payload["conflicts"]
                ):
                    final[item["old_id"]] = item["relation"]
        verdicts = []
        raw_conflicts = data.get("conflicts") if isinstance(data, dict) else None
        for raw in raw_conflicts if isinstance(raw_conflicts, list) else ():
            if not isinstance(raw, dict):
                continue
            label = str(raw.get("old_id") or "").strip()
            relation = str(raw.get("relation") or "").strip()
            known = by_label.get(label)
            if known is None:
                verdict = "丟：不是給它看的候選"
            elif relation.casefold() not in ("supersedes", "contradicts", "refines"):
                verdict = "丟：關係不在清單"
            elif known[0] in final and status == "committed":
                verdict = f"採用：{final[known[0]]}"
            elif known[0] in final:
                verdict = f"判定 {final[known[0]]}，commit：{status}"
            elif known[0] in passed:
                verdict = "丟：再問一次後不成立（計畫／一天對習慣／可同時為真／答不清）"
            else:
                verdict = "丟"
            verdicts.append(
                (
                    label,
                    known[1] if known else "?",
                    relation,
                    str(raw.get("reason") or ""),
                    verdict,
                )
            )
        out.append(
            {
                "new": str(new.get("summary") or ""),
                "said": str(new.get("said") or ""),
                "candidates": candidates,
                "raw": data,
                "verdicts": verdicts,
                "status": status,
                "error": error,
            }
        )
    return out


def conflict_items(row) -> list[str]:
    out = []
    remembered = [
        (proposal.payload.get("summary"), outcome)
        for proposal, outcome in row["commits"]
        if proposal.target == "memory.append_candidate"
    ]
    for summary, outcome in remembered:
        candidates = len(outcome.metadata.get("conflict_candidates") or ())
        out.append(
            f"記下：{summary}（commit：{outcome.status.value}"
            + (f"，候選 {candidates} 筆" if outcome.committed else "")
            + "）"
        )
    if not remembered:
        out.append("（這輪沒有記下使用者的事）")
    for job in conflict_judgements(row):
        lines = [f"▶ 觸發：「{job['new']}」　使用者原話「{job['said']}」"]
        lines += [f"　{label}: {summary}" for label, _, summary in job["candidates"]]
        if job["error"]:
            lines.append(f"　呼叫失敗：{job['error']}")
        else:
            lines.append(f"　模型答：{json.dumps(job['raw'], ensure_ascii=False)}")
        for label, summary, relation, why, verdict in job["verdicts"]:
            lines.append(f"　{label}「{summary}」→ {relation}（{why}）　{verdict}")
        if not job["verdicts"] and not job["error"]:
            lines.append("　（模型判定無關）")
        out.append("\n".join(lines))
    for question, answer in row.get("asked_again") or []:
        out.append(
            f"再問一次：{' / '.join(question.splitlines()[1::3])}\n　答：{' '.join(answer.split())}"
        )
    return out


ITEMS = {
    "memory": memory_items,
    "self-memory": self_memory_items,
    "reflection": reflection_items,
    "emotion": emotion_items,
    "reply-check": reply_check_items,
    "user-state": user_state_items,
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
    if (page in NEW_ONLY or page == CONFLICT_PAGE) and variant == "old":
        return "（1.1 沒有這個工作）"
    if page == CONFLICT_PAGE:
        received = "\n".join(row.get("conflict_notes") or []) or "（無）"
        return "\n".join(
            [f"這一輪她收到的確認提醒：{received}", "——", *conflict_items(row)]
        )
    reading = reading_of(row, KINDS[page])
    if reading is None:
        text = "（這輪沒有跑）"
    else:
        text = "\n".join(ITEMS[page](reading, row["commits"], variant))
    if page == "reply-check":
        received = "\n".join(row.get("told") or []) or "（無）"
        text = f"這一輪她收到的提醒：{received}\n——\n{text}"
    return text


def diary_section(label, name, runs) -> str:
    written = runs["new"].get("diary") or {}
    reading = written.get("reading")
    entry = written.get("entry")
    if reading is None:
        happened, answer, verdict = "（沒有材料：這段沒有對話？）", "（沒跑）", ""
    else:
        _, context, data, normalized, _, error = reading
        day = context.request.payload.get("diary") or {}
        happened = "\n\n".join(
            f"{title}：\n" + "\n".join(f"・{line}" for line in lines)
            for title, lines in _diary_sections(day)
        )
        lines = [line for _, ls in _diary_sections(day) for line in ls]

        def shown(answer_data) -> str:
            text = _diary_text(str(answer_data.get("text") or ""))
            off = _not_of_the_day(text, lines)
            return (
                f"{answer_data.get('text')}\n\nevidence：\n"
                + "\n".join(
                    f"「{quote}」"
                    + (
                        ""
                        if _line_quoted(str(quote), lines) is not None
                        else "（不在材料裡）"
                    )
                    for quote in answer_data.get("evidence") or []
                )
                + (
                    "\n\n跟材料對不上的句子：\n" + "\n".join(f"・{x}" for x in off)
                    if off
                    else ""
                )
            )

        first = written.get("first")
        if error:
            answer, verdict = f"這次呼叫失敗：{error}", ""
        else:
            answer = shown(data)
            if first is not None and first != data:
                answer = (
                    f"第一次：\n{shown(first)}\n\n（再問一次）\n\n第二次：\n{answer}"
                )
            verdict = (
                f"收下（{entry.date}）：\n{entry.text}\n\n依據：\n"
                + "\n".join(f"「{quote}」" for quote in entry.evidence)
                if entry is not None
                else "沒收：依據不在材料裡、對得上材料的句子不到兩句、寫成清單或語言不對"
            )
    prompt = "\n".join(written.get("in_prompt") or []) or "（無）"
    cells = [happened, "（1.1 沒有這個工作）", f"{answer}\n——\n{verdict}", prompt]
    head = "".join(
        f"<th>{cell(h)}</th>"
        for h in (
            "她那天的材料",
            "舊（1.1）",
            f"新：{name} 的日記（模型的回答——引擎的處置）",
            "下一段新對話時她的系統提示裡",
        )
    )
    body = "<tr>" + "".join(f"<td>{cell(c)}</td>" for c in cells) + "</tr>"
    return (
        f"<h2>{cell(label)}</h2><table><thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def section(page, label, name, runs) -> str:
    if page == "diary":
        return diary_section(label, name, runs)
    new_rows, old_rows = runs["new"]["rows"], runs["old"]["rows"]
    body = []
    for index, (new, old) in enumerate(zip(new_rows, old_rows)):
        if page == "user-state" and reading_of(new, KINDS[page]) is None:
            continue  # 每 --user-state-every 輪才跑一次
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
    if page == "user-state":
        note = (
            "使用者狀態摘要是新工作，舊欄留空；只列有跑的那幾輪。每列：這一段她讀到的"
            "使用者原句、情緒工作給的序列、模型的回答，每個 concern 有沒有使用者原句"
            "與引擎的處置，最後是她提示裡那一行（user lately）。"
        )
    if page == "diary":
        note = (
            "她的日記是新工作，舊欄留空。每段對話重播完，write_diary() 寫一篇："
            "左邊是引擎給模型的材料（只有這些可以寫），中間是模型的回答與引擎的處置，"
            "右邊是之後新對話時她系統提示裡的那兩句。判讀：每句對得到左邊的材料嗎？語氣像她嗎？"
        )
    if page == "reply-check":
        note = (
            "回話自檢是 1.2.0 新增的工作，舊欄留空。新欄：模型回報的每個問題（kind／她的原句／"
            "給她的提醒）與引擎的處置；「這一輪她收到的提醒」是上一輪的問題被帶進這一輪提示的那幾行。"
            "重播的對話她照念紀錄，提醒不會改變她說的話；現場生成的才看得出她有沒有照做。"
        )
    if page == CONFLICT_PAGE:
        note = (
            "記憶衝突是新工作，舊欄留空。新欄：這輪記下的使用者記憶與候選數；每次觸發列候選"
            "（m1…）、模型原答、每筆關係的處置（supersedes／contradicts 會再問一次，答案列在"
            "「再問一次」）；「這一輪她收到的確認提醒」是 contradicts 帶進下一輪的那行。"
            "頁首是採用的關係，逐筆給人判：supersedes 誤判會讓真事實消失（硬指標 0）。"
        )
    body = "".join(section(page, *item) for item in sections)
    if page == CONFLICT_PAGE:
        body = conflict_summary(sections) + body
    return (
        "<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{cell(TITLES[page])}</title><style>{style}</style></head><body>"
        f"<h1>引擎 1.2.0：{cell(TITLES[page])}　舊與新並排</h1>"
        f"<p>{cell(meta)}</p><p>{cell(note)}</p>{body}</body></html>"
    )


def conflict_summary(sections) -> str:
    """頁首：每段對話觸發幾次、模型答了什麼、採用了什麼；採用的逐筆列出。"""
    rows, adopted = [], []
    for title, _, runs in sections:
        triggers = answered = 0
        kinds = {"supersedes": 0, "contradicts": 0, "refines": 0}
        for row in runs["new"]["rows"]:
            for job in conflict_judgements(row):
                triggers += 1
                answered += len(job["verdicts"])
                for label, summary, relation, _, verdict in job["verdicts"]:
                    if verdict.startswith("採用："):
                        kind = verdict.removeprefix("採用：")
                        kinds[kind] = kinds.get(kind, 0) + 1
                        adopted.append(
                            (
                                title,
                                row["number"],
                                kind,
                                summary,
                                job["new"],
                                job["said"],
                            )
                        )
        rows.append(
            f"<tr><td>{cell(title)}</td><td>{triggers}</td><td>{answered}</td>"
            + "".join(
                f"<td>{kinds[k]}</td>" for k in ("supersedes", "contradicts", "refines")
            )
            + "</tr>"
        )
    listed = (
        "".join(
            f"<tr><td>{cell(title)}</td><td>{number}</td><td>{cell(kind)}</td>"
            f"<td>{cell(old)}</td><td>{cell(new)}</td><td>{cell(said)}</td><td></td></tr>"
            for title, number, kind, old, new, said in adopted
        )
        or "<tr><td colspan='7'>（沒有採用任何關係）</td></tr>"
    )
    return (
        "<h2>統計</h2><table><thead><tr><th>對話</th><th>觸發</th><th>模型給的關係</th>"
        "<th>採用 supersedes</th><th>採用 contradicts</th><th>採用 refines</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "<h3>採用的關係（逐筆判：對／誤判）</h3><table><thead><tr><th>對話</th><th>輪</th>"
        "<th>關係</th><th>舊事實</th><th>新事實</th><th>使用者原話</th><th>人判</th></tr></thead>"
        f"<tbody>{listed}</tbody></table>"
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
    old_needed = set(args.pages) & set(OLD_PAGES)
    for raw in args.conversations:
        path, start, end = conversation_arg(raw)
        name, pairs = pairs_of(path)
        end = min(end or len(pairs), len(pairs), start - 1 + args.max_turns)
        earlier = pairs[: start - 1]
        turns = [(n, pairs[n - 1]) for n in range(start, end + 1)]
        runs = {}
        for variant in ("new", "old"):
            if variant == "old" and not old_needed:
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
        "--user-state-every", type=int, default=6, help="使用者狀態幾輪讀一次"
    )
    parser.add_argument(
        "--summary-every",
        type=int,
        default=6,
        help="跑 diary 時摘要幾輪一次（Tomoshibi 預設 0；0 就沒有摘要可讀）",
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
