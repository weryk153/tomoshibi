"""ASR 還原：語音那一輪，用最近的對話把語音辨識的同音錯字還原，再交給她。

9B 模型讀到「空尼七哇」「歐嗨唷狗紮伊媽斯」會當成使用者真的那樣唸、去評發音，
提示怎麼寫都壓不住（2026-10-06）。所以在她回話之前先還原：她、她的記憶、對話
紀錄看到的都是還原後的字。

用引擎的背景模型（character_engine_agent 的 background_base_url／background_model）
另外問一次。沒把握、太慢（TIMEOUT_SECONDS）、回的東西不對、任何例外——一律用原文。
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional, Sequence

import httpx
from loguru import logger

from .chat_history_manager import get_history
from .conversations.conversation_utils import derive_voice_lang
from .translate.catchphrases import only_catchphrases

# 她要等這一步才開始回話，所以有上限；超過就用原文。
TIMEOUT_SECONDS = 4.0
MAX_TOKENS = 200
# 採用守門（accept）
MIN_CONFIDENCE = 0.7
MIN_RATIO = 0.5
MAX_RATIO = 2.0
MIN_RAW_LENGTH = 2
# 給模型看的上下文：最近幾輪（她一句＋使用者一句算一輪）、每一句最多幾個字。
ROUNDS = 6
LINE_CHARS = 160
# 只帶思考開關（同 character_engine/factory.py 的背景工作），取樣參數不帶。
_REASONING_KEYS = (
    "reasoning_effort",
    "reasoning",
    "chat_template_kwargs",
    "enable_thinking",
)
_LANG_NAMES = {"ja": "Japanese", "zh": "Chinese", "en": "English", "ko": "Korean"}

SYSTEM_PROMPT = """\
You fix speech-recognition (ASR) errors in one line the user just SAID out loud.
The recogniser often writes a word that sounds the same but is wrong:
- Chinese homophones or near-homophones (wrong characters, same sound)
- a foreign phrase written as Chinese sound-alike characters (e.g. 阿里嘎多 -> ありがとう)
- misspelled kana or romaji
Use the recent conversation to tell what the user most likely said.
Rules:
- Only replace words that sound like what was recognised. Do not change the meaning.
- Do not add or remove words, do not fix grammar or punctuation, do not rephrase, do not translate, do not reply to the user.
- Keep names, catchphrases and every word that already makes sense exactly as written.
- If the line already makes sense, or you are not sure, return it unchanged with low confidence.
Reply with JSON only: {"text": "<the line, repaired>", "confidence": <0 to 1, how sure the repaired line is what was said>, "note": "<one short reason>"}"""


@dataclass(frozen=True)
class RepairResult:
    text: str
    changed: bool
    confidence: float
    reason: str


def accept(
    raw: str, fixed: str, confidence: float, *, catchphrases: Iterable[str] = ()
) -> bool:
    """模型的還原要不要採用。不過就用原文。"""
    raw = (raw or "").strip()
    fixed = (fixed or "").strip()
    if len(raw) < MIN_RAW_LENGTH or not fixed:
        return False
    if confidence < MIN_CONFIDENCE:
        return False
    if not MIN_RATIO <= len(fixed) / len(raw) <= MAX_RATIO:
        return False
    if only_catchphrases(raw, list(catchphrases)):
        return False
    return True


def _messages(
    text: str, transcript: Sequence[tuple[str, str]], languages: Sequence[str]
) -> list[dict]:
    langs = [lang for lang in languages if lang]
    lines = []
    if langs:
        speaks = f"The user speaks {langs[0]}."
        if len(langs) > 1 and langs[1] != langs[0]:
            speaks += (
                f" The character speaks {langs[1]}; the user may also say"
                f" {langs[1]} words or phrases (e.g. when learning or repeating"
                " after her)."
            )
        lines.append(speaks)
    if transcript:
        lines.append("Recent conversation:")
        lines.extend(f"{who}: {said}" for who, said in transcript)
    lines.append("")
    lines.append(f"Line recognised by ASR: {text}")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines)},
    ]


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _parse(reply: str) -> Optional[tuple[str, float, str]]:
    body = _FENCE.sub("", (reply or "").strip())
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        return None
    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        return None
    confidence = min(max(confidence, 0.0), 1.0)
    return data["text"].strip(), confidence, str(data.get("note") or "")


async def repair(
    text: str,
    transcript: Sequence[tuple[str, str]],
    *,
    client: Any,
    languages: Sequence[str],
    catchphrases: Iterable[str] = (),
    timeout: float = TIMEOUT_SECONDS,
) -> RepairResult:
    """把一句語音辨識的字還原。client 要有 async complete(messages) -> str。"""
    raw = text or ""
    catchphrases = list(catchphrases)
    if len(raw.strip()) < MIN_RAW_LENGTH or only_catchphrases(raw, catchphrases):
        return RepairResult(raw, False, 0.0, "skipped")
    try:
        reply = await asyncio.wait_for(
            client.complete(_messages(raw, transcript, languages)), timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"ASR repair timed out after {timeout}s; keeping '{raw}'")
        return RepairResult(raw, False, 0.0, "timeout")
    except Exception as e:
        logger.warning(f"ASR repair failed ({type(e).__name__}: {e}); keeping '{raw}'")
        return RepairResult(raw, False, 0.0, "error")
    parsed = _parse(reply)
    if parsed is None:
        logger.warning(f"ASR repair: unreadable reply {reply!r}; keeping '{raw}'")
        return RepairResult(raw, False, 0.0, "bad reply")
    fixed, confidence, note = parsed
    taken = accept(raw, fixed, confidence, catchphrases=catchphrases)
    logger.info(
        f"ASR repair: '{raw}' -> '{fixed}' ({confidence})"
        + ("" if taken else " — kept original")
    )
    if not taken or fixed == raw.strip():
        return RepairResult(raw, False, confidence, note)
    return RepairResult(fixed, True, confidence, note)


@dataclass
class ChatClient:
    """OpenAI 相容的 /chat/completions，一次一句、不串流。"""

    base_url: str
    model: str
    api_key: str = ""
    request_options: Optional[dict] = None

    async def complete(self, messages: list[dict]) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS + 1) as http:
            response = await http.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    **(self.request_options or {}),
                },
                headers=headers,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"] or ""


def recent_transcript(context: Any) -> list[tuple[str, str]]:
    """這段對話最近 ROUNDS 輪（使用者與她的話；系統訊息、空回覆不算）。"""
    character = context.character_config
    lines = []
    for message in get_history(character.conf_uid, context.history_uid or ""):
        content = str(message.get("content") or "").strip()
        if message.get("role") not in ("human", "ai") or not content:
            continue
        if len(content) > LINE_CHARS:
            content = "…" + content[-LINE_CHARS:]
        who = message.get("name") or (
            character.human_name
            if message.get("role") == "human"
            else character.character_name
        )
        lines.append((str(who), content))
    return lines[-2 * ROUNDS :]


def _languages(context: Any) -> tuple[str, ...]:
    reply = str(
        getattr(context.character_config, "reply_language", "")
        or getattr(getattr(context, "system_config", None), "player_language", "")
        or ""
    )
    voice = _LANG_NAMES.get(derive_voice_lang(context.character_config) or "", "")
    return tuple(lang for lang in (reply, voice) if lang)


def _client(character: Any) -> Optional[ChatClient]:
    """引擎的背景模型；網址和模型都有才用。"""
    agent = getattr(character, "agent_config", None)
    settings = getattr(agent, "agent_settings", None)
    engine = getattr(settings, "character_engine_agent", None)
    base_url = str(getattr(engine, "background_base_url", "") or "").strip()
    model = str(getattr(engine, "background_model", "") or "").strip()
    if not base_url or not model:
        return None
    provider = getattr(getattr(settings, "conversation", None), "llm_provider", "")
    llm = getattr(getattr(agent, "llm_configs", None), str(provider or ""), None)
    extra_body = dict(getattr(llm, "extra_body", None) or {})
    return ChatClient(
        base_url=base_url,
        model=model,
        api_key=str(getattr(engine, "background_api_key", "") or "")
        or str(getattr(llm, "llm_api_key", "") or ""),
        request_options={
            "temperature": 0,
            "max_tokens": MAX_TOKENS,
            **{k: v for k, v in extra_body.items() if k in _REASONING_KEYS},
        },
    )


def repairer(context: Any) -> Optional[Callable[[str], Awaitable[str]]]:
    """這個連線的還原函式；開關關著或沒有背景模型就是 None（照舊不還原）。"""
    character = getattr(context, "character_config", None)
    asr_config = getattr(character, "asr_config", None)
    if not getattr(asr_config, "repair_with_context", False):
        return None
    client = _client(character)
    if client is None:
        return None

    async def fix(text: str) -> str:
        try:
            transcript = recent_transcript(context)
            result = await repair(
                text,
                transcript,
                client=client,
                languages=_languages(context),
                catchphrases=(getattr(character, "catchphrases", None) or {}).keys(),
            )
            return result.text
        except Exception as e:
            logger.warning(f"ASR repair skipped ({type(e).__name__}: {e})")
            return text

    return fix
