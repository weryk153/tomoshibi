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
from functools import lru_cache
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
# 中文諧音換成假名時，每拿掉一個漢字最多多幾個假名（長音、拗音會多一點）。
KANA_PER_HAN = 1.5
# 給模型看的上下文：最近幾輪（她一句＋使用者一句算一輪）、每一句最多幾個字。
# 模型讀提示的速度約每秒三四百 token，而且快取用不上：上下文越長越慢。最後兩句
# （通常是她要對方念的那句）留長一點，更早的只留結尾。
ROUNDS = 6
LINE_CHARS = 80
OLDER_LINE_CHARS = 30
# 只帶思考開關（同 character_engine/factory.py 的背景工作），取樣參數不帶。
_REASONING_KEYS = (
    "reasoning_effort",
    "reasoning",
    "chat_template_kwargs",
    "enable_thinking",
)
_LANG_NAMES = {"ja": "Japanese", "zh": "Chinese", "en": "English", "ko": "Korean"}

SYSTEM_PROMPT = """\
Speech recognition (ASR) wrote down a line the user just said out loud. It may contain sound-alike errors:
- wrong Chinese characters with the same or a similar sound
- a foreign phrase written as Chinese sound-alike characters: write the phrase itself in its own script, never its meaning (e.g. 阿里嘎多 -> ありがとう, not 謝謝)
- kana or romaji that is not a real word
If the character just asked the user to say a phrase and the line sounds like that phrase, the line is that phrase.
Most lines are fine: if the line makes sense here, return it unchanged.
Otherwise replace only the mis-heard words with what they sound like. Keep everything else exactly: other words, names, numbers, punctuation, character forms. Casual or short forms are real words. Never rephrase, add or drop words, translate, answer the user, or copy an earlier line.
Reply with JSON only: {"text": "<the line>", "confidence": <0 to 1, how sure this is what was said>, "note": "<at most 6 words>"}"""


@dataclass(frozen=True)
class RepairResult:
    text: str
    changed: bool
    confidence: float
    reason: str


_FILLER = re.compile(r"[\s\W_]+", re.UNICODE)
_HAN = re.compile(r"[一-鿿㐀-䶿]")
_KANA = re.compile(r"[぀-ゟ゠-ヿ]")
_KANA_RUN = re.compile(r"[぀-ゟ゠-ヿ]+")
_DIGITS = re.compile(r"[0-9０-９]+")
_KANA_OR_LATIN = re.compile(r"[぀-ゟ゠-ヿA-Za-z]")


@lru_cache(maxsize=1)
def _simplified() -> Callable[[str], str]:
    """把字形統一（日文新字體→繁體→簡體），只拿來比較。"""
    from opencc import OpenCC

    japanese, simplified = OpenCC("jp2t"), OpenCC("t2s")
    return lambda text: simplified.convert(japanese.convert(text))


def _bare(text: str) -> str:
    """拿掉空白與標點，只比字。"""
    return _FILLER.sub("", text or "")


def accept(
    raw: str,
    fixed: str,
    confidence: float,
    *,
    catchphrases: Iterable[str] = (),
    earlier: Iterable[str] = (),
    context: Optional[str] = None,
) -> bool:
    """模型的還原要不要採用。不過就用原文。

    earlier 是使用者前面講過的話：模型有時把上一句整句抄過來當「還原」。
    context 是模型看到的對話；給了的話，中文諧音換成的假名要是她剛講過的
    （沒上下文時模型會把「哈囉」翻成「ハロー」）。
    """
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
    bare_raw, bare_fixed = _bare(raw), _bare(fixed)
    # 只差標點、空白：不算還原。
    if bare_raw == bare_fixed:
        return False
    # 中文換中文：同音字是一個字換一個字，字數變了就是潤飾或改寫。
    if not _KANA_OR_LATIN.search(raw + fixed) and len(bare_raw) != len(bare_fixed):
        return False
    # 只換了字形（繁簡、日文新字體）：不是還原，是改了使用者的寫法。
    simplified = _simplified()
    if simplified(bare_raw) == simplified(bare_fixed):
        return False
    # 中文諧音換成假名：一個字大約一個音節。假名多出一大截就是翻譯，不是還原。
    han_removed = len(_HAN.findall(raw)) - len(_HAN.findall(fixed))
    kana_added = len(_KANA.findall(fixed)) - len(_KANA.findall(raw))
    if kana_added > 0 and kana_added > KANA_PER_HAN * max(han_removed, 0):
        return False
    if context is not None and kana_added > 0 and han_removed > 0:
        new_kana = set(_KANA_RUN.findall(fixed)) - set(_KANA_RUN.findall(raw))
        if any(run not in context for run in new_kana):
            return False
    # 數字照原樣（50音 不是 五十音）。
    if _DIGITS.findall(raw) != _DIGITS.findall(fixed):
        return False
    if any(_bare(line) == bare_fixed for line in earlier):
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
        lines.append("")
        lines.append("Conversation so far (context only):")
        lines.extend(f"{who}: {said}" for who, said in transcript)
    lines.append("")
    lines.append("New line from ASR:")
    lines.append(text)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines)},
    ]


_QUOTES = ("「」", "『』", '""', "“”")


def _unquote(fixed: str, raw: str) -> str:
    """模型有時把整句包在引號裡回來；原句沒有引號就拿掉。"""
    for pair in _QUOTES:
        if (
            len(fixed) > 2
            and fixed[0] == pair[0]
            and fixed[-1] == pair[1]
            and not raw.strip().startswith(pair[0])
        ):
            return fixed[1:-1].strip()
    return fixed


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _parse(reply: str) -> Optional[tuple[str, float, str]]:
    """(還原後的字, 信心, 理由)。"""
    body = _FENCE.sub("", (reply or "").strip())
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("text"), str):
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
    user: str = "",
    timeout: float = TIMEOUT_SECONDS,
) -> RepairResult:
    """把一句語音辨識的字還原。client 要有 async complete(messages) -> str。

    user 是逐字稿裡使用者的名字；他前面講過的話不能被當成這一句的還原。
    """
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
    fixed = _unquote(fixed, raw)
    earlier = [said for who, said in transcript if user and who == user]
    taken = accept(
        raw,
        fixed,
        confidence,
        catchphrases=catchphrases,
        earlier=earlier,
        context="\n".join(said for _, said in transcript),
    )
    logger.info(
        f"ASR repair: '{raw}' -> '{fixed}' ({confidence})"
        + ("" if taken else " — kept original")
    )
    if not taken:
        return RepairResult(raw, False, confidence, note)
    return RepairResult(fixed, True, confidence, note)


@dataclass
class ChatClient:
    """OpenAI 相容的 /chat/completions，一次一句、不串流。"""

    base_url: str
    model: str
    api_key: str = ""
    request_options: Optional[dict] = None
    # 正式流程由 repair() 的 wait_for 管上限；這只是連線層的保險。
    timeout_seconds: float = TIMEOUT_SECONDS + 1

    async def complete(self, messages: list[dict]) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http:
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


def transcript_from(
    messages: Iterable[dict], human_name: str, character_name: str
) -> list[tuple[str, str]]:
    """對話紀錄的最後 ROUNDS 輪（使用者與她的話；系統訊息、空回覆不算）。"""
    lines = []
    for message in messages:
        content = str(message.get("content") or "").strip()
        if message.get("role") not in ("human", "ai") or not content:
            continue
        who = message.get("name") or (
            human_name if message.get("role") == "human" else character_name
        )
        lines.append((str(who), content))
    lines = lines[-2 * ROUNDS :]
    for index, (who, content) in enumerate(lines):
        limit = LINE_CHARS if index >= len(lines) - 2 else OLDER_LINE_CHARS
        if len(content) > limit:
            lines[index] = (who, "…" + content[-limit:])
    return lines


def recent_transcript(context: Any) -> list[tuple[str, str]]:
    """這段對話（chat_history 裡的逐字稿）最近 ROUNDS 輪。"""
    character = context.character_config
    return transcript_from(
        get_history(character.conf_uid, context.history_uid or ""),
        character.human_name,
        character.character_name,
    )


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
                user=str(getattr(character, "human_name", "") or ""),
            )
            return result.text
        except Exception as e:
            logger.warning(f"ASR repair skipped ({type(e).__name__}: {e})")
            return text

    return fix
