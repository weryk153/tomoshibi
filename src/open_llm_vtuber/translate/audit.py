"""翻譯審核（背景）：她每句語音翻譯事後由背景模型審一遍。

抓漏翻、多翻、整句跑成別的語言（例如英文）、名字翻錯、口頭禪沒保留；結果累積成
建議清單（protected_names／catchphrases 候選＋可疑句），讓使用者在角色頁決定要
不要加進角色設定。**不改當下的輸出、不加延遲、不自動改角色檔。**

角色設定 translation_audit 開著、而且引擎有背景模型才跑。逐句輸出那裡
（conversation_utils.handle_sentence_output）把有經過翻譯模型的句子排進佇列，
只排、不問模型——她還在講，主模型正忙。一輪結束（single／group_conversation
的串流迴圈跑完）才由 flush_for 在背景一次審完，每 BATCH_SIZE 句問一次。佇列
最多 MAX_QUEUE 句，滿了丟最舊的。逾時、壞 JSON、任何例外：那一批丟掉，不重試。

盡力而為：還沒審的句子只在記憶體裡，斷線、關掉程式、伺服器重啟就沒了。

存在 chat_history/<conf_uid>/translation_audit/：
- audit.jsonl：每審一句一行（時間、原句、譯句、目標語言、issues、suggest），
  只留最近 MAX_LOG_LINES 行
- summary.json：總數、每個建議出現幾次、最近 SUSPICIOUS_KEPT 句可疑句
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Iterable, Mapping, Optional

from loguru import logger

from ..background_llm import background_client

BATCH_SIZE = 4
MAX_QUEUE = 8
# 背景工作：不擋任何人，給寬一點。
TIMEOUT_SECONDS = 90.0
MAX_TOKENS = 1200
SUSPICIOUS_KEPT = 50
# audit.jsonl 的上限：超過行數或大小就只留最後 MAX_LOG_LINES 行。
MAX_LOG_LINES = 2000
MAX_LOG_BYTES = 1_000_000
# 角色頁只列出現過這麼多次的建議：一次的多半是模型一時興起。
MIN_SUGGESTION_COUNT = 2
# 建議的字串上限：名字、口頭禪都很短，長的是模型把整句塞進來。
MAX_TERM_CHARS = 24
MAX_DETAIL_CHARS = 200

KINDS = ("omitted", "added", "wrong_language", "name", "catchphrase", "meaning")
SUGGEST_KINDS = ("protected_names", "catchphrases")
_LANG_NAMES = {"ja": "Japanese", "zh": "Chinese", "en": "English", "ko": "Korean"}

SYSTEM_PROMPT = """\
You review machine translations of a character's spoken lines. She wrote each line in one language; a translator turned it into the language of her voice. Compare each translation with its source and report only real problems:
- omitted: part of the source meaning is missing
- added: the translation says something the source does not
- wrong_language: the translation, or a whole sentence of it, is not in the target language (e.g. English)
- name: a name is misspelled, replaced by a sound-alike, or written inconsistently
- catchphrase: her catchphrase or verbal tic was dropped or translated away
- meaning: the meaning is changed or inverted
Fine, not problems: natural rewording, a different politeness level, dropped filler words, punctuation, kanji in Japanese, a common noun translated normally, and words kept as they are in the source (quoted foreign words, names, numbers, typos). Most translations are fine: then ok is true and issues is empty.
Suggest only fixes for problems you reported:
- protected_names: {"<wrong spelling, exactly as in the translation>": "<correct spelling>"}
- catchphrases: {"<catchphrase exactly as in the source>": "<how to write it in the target language>"}
Reply with JSON only, one result per numbered pair, in order:
{"results": [{"i": 1, "ok": true, "issues": [{"kind": "<kind>", "detail": "<at most 12 words>"}], "suggest": {"protected_names": {}, "catchphrases": {}}}]}"""


@dataclass(frozen=True)
class AuditItem:
    original: str
    translated: str
    target_lang: str
    character: str = ""
    time: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


# --------------------------------------------------------------------- 解析

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _issues(raw: Any) -> list[dict]:
    issues = []
    for issue in raw if isinstance(raw, list) else []:
        if not isinstance(issue, dict) or issue.get("kind") not in KINDS:
            continue
        detail = issue.get("detail")
        issues.append(
            {
                "kind": issue["kind"],
                "detail": (detail if isinstance(detail, str) else "")[
                    :MAX_DETAIL_CHARS
                ],
            }
        )
    return issues


def _pairs(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        source.strip(): target.strip()
        for source, target in raw.items()
        if isinstance(source, str)
        and isinstance(target, str)
        and source.strip()
        and target.strip()
        and source.strip() != target.strip()
        and len(source.strip()) <= MAX_TERM_CHARS
        and len(target.strip()) <= MAX_TERM_CHARS
        and "\n" not in source + target
    }


def _result(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    issues = _issues(raw.get("issues"))
    suggest = raw.get("suggest") if isinstance(raw.get("suggest"), dict) else {}
    return {
        "ok": bool(raw.get("ok", True)) and not issues,
        "issues": issues,
        "suggest": {kind: _pairs(suggest.get(kind)) for kind in SUGGEST_KINDS},
    }


def _first_json(reply: str) -> Any:
    """回覆裡第一個 JSON 值；後面多出來的不管（9B 模型會把整段重複一次）。"""
    body = _FENCE.sub("", (reply or "").strip())
    starts = [i for i in (body.find("{"), body.find("[")) if i >= 0]
    if not starts:
        raise ValueError("no JSON")
    return json.JSONDecoder().raw_decode(body[min(starts) :])[0]


def parse_reply(reply: str, count: int) -> Optional[list[Optional[dict]]]:
    """模型的回覆 → 每句一個結果（對不上的那句是 None）；整個讀不懂回 None。"""
    try:
        data = _first_json(reply)
    except ValueError:
        return None
    if isinstance(data, dict):
        data = data.get("results")
    if not isinstance(data, list):
        return None
    results: list[Optional[dict]] = [None] * count
    numbered = all(
        isinstance(raw, dict) and isinstance(raw.get("i"), int) for raw in data
    )
    for position, raw in enumerate(data):
        index = raw["i"] - 1 if numbered else position
        if 0 <= index < count and results[index] is None:
            results[index] = _result(raw)
    return results


def _grounded(
    suggest: Mapping[str, Mapping[str, str]], item: AuditItem, issues: list[dict]
) -> dict:
    """建議要有同類的問題，而且指得到句子：名字的錯誤寫法在譯句裡、口頭禪在
    原句裡（不分大小寫）。模型說沒問題時順手給的建議，多半是把普通詞當口頭禪。
    """
    kinds = {issue["kind"] for issue in issues}
    return {
        "protected_names": {
            wrong: right
            for wrong, right in suggest.get("protected_names", {}).items()
            if "name" in kinds and wrong in item.translated
        },
        "catchphrases": {
            source: target
            for source, target in suggest.get("catchphrases", {}).items()
            if "catchphrase" in kinds and source.lower() in item.original.lower()
        },
    }


_KANA = re.compile(r"[぀-ゟ゠-ヿ]")
_HAN = re.compile(r"[一-鿿㐀-䶿]")
_LATIN = re.compile(r"[A-Za-z]")
_LETTER = re.compile(r"[^\W\d_]")
# 全漢字的日文短句（大丈夫？、了解。）是對的；長一點還一個假名都沒有、或帶著
# 中文才有的虛字（吗、呢、這……），才算還是中文。
MIN_HAN_WITHOUT_KANA = 5
_CHINESE_ONLY = re.compile(r"[的吗嗎呢們们这這吧啊喔耶麼么沒没]")


def _mostly_latin(text: str) -> bool:
    letters = len(_LETTER.findall(text))
    return letters > 0 and len(_LATIN.findall(text)) * 2 >= letters


def plain_issues(original: str, translated: str, target_lang: str) -> list[dict]:
    """不用問模型就看得出來的：沒翻、目標日文卻還是中文、整句跑成英文。

    9B 模型自己常漏掉這幾種（實測：還是中文的句子它說沒問題）。
    """
    original, translated = (original or "").strip(), (translated or "").strip()
    if not translated:
        return []
    if translated == original and _LETTER.search(original):
        return [{"kind": "wrong_language", "detail": "not translated"}]
    if _mostly_latin(translated) and not _mostly_latin(original):
        return [{"kind": "wrong_language", "detail": "mostly Latin letters"}]
    if (
        target_lang == "ja"
        and not _KANA.search(translated)
        and (
            len(_HAN.findall(translated)) >= MIN_HAN_WITHOUT_KANA
            or (len(_HAN.findall(translated)) >= 2 and _CHINESE_ONLY.search(translated))
        )
    ):
        return [{"kind": "wrong_language", "detail": "no kana: still Chinese"}]
    return []


_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _only_copied_foreign_words(original: str, translated: str) -> bool:
    """譯句是日文（有假名），裡面的拉丁字母詞都是原句照抄的（她要對方念的詞）。"""
    words = _LATIN_WORD.findall(translated)
    source = original.lower()
    return (
        bool(words)
        and bool(_KANA.search(translated))
        and all(word.lower() in source for word in words)
    )


def _merge(plain: list[dict], issues: list[dict], item: AuditItem) -> list[dict]:
    """模型的 issues 加上看得出來的；照抄原句外語詞的 wrong_language 是誤報。"""
    if _only_copied_foreign_words(item.original, item.translated):
        issues = [issue for issue in issues if issue["kind"] != "wrong_language"]
    kinds = {issue["kind"] for issue in issues}
    return issues + [issue for issue in plain if issue["kind"] not in kinds]


# --------------------------------------------------------------------- 存檔


def _empty_summary() -> dict:
    return {
        "audited": 0,
        "flagged": 0,
        "protected_names": {},
        "catchphrases": {},
        "suspicious": [],
    }


def load_summary(directory: os.PathLike | str) -> dict:
    path = Path(directory) / "summary.json"
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return _empty_summary()
    summary = _empty_summary()
    if isinstance(data, dict):
        # 型別不對的欄位（手改壞、舊格式）用空的，不讓加總時炸掉。
        summary.update(
            {
                k: data[k]
                for k, empty in summary.items()
                if k in data
                and type(data[k]) is type(empty)
                and not isinstance(data[k], bool)
            }
        )
    return summary


class AuditStore:
    """一個角色的審核紀錄。只有背景審核會寫，同一個角色同一時間只有一批。"""

    def __init__(self, directory: os.PathLike | str):
        self.directory = Path(directory)

    @staticmethod
    def _cap(log: Path) -> None:
        """超過 MAX_LOG_BYTES 或 MAX_LOG_LINES 行：只留最後 MAX_LOG_LINES 行。"""
        if log.stat().st_size <= MAX_LOG_BYTES:
            with open(log, "rb") as f:
                if sum(1 for _ in f) <= MAX_LOG_LINES:
                    return
        lines = log.read_text("utf-8").splitlines(keepends=True)
        tmp = log.with_name(".audit.jsonl.tmp")
        tmp.write_text("".join(lines[-MAX_LOG_LINES:]), "utf-8")
        os.replace(tmp, log)

    def record(self, entries: list[dict]) -> None:
        if not entries:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        log = self.directory / "audit.jsonl"
        with open(log, "a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._cap(log)
        summary = load_summary(self.directory)
        for entry in entries:
            summary["audited"] += 1
            for kind in SUGGEST_KINDS:
                counts = summary[kind]
                for source, target in (
                    (entry.get("suggest") or {}).get(kind, {}).items()
                ):
                    targets = counts.setdefault(source, {})
                    targets[target] = targets.get(target, 0) + 1
            if entry.get("issues"):
                summary["flagged"] += 1
                summary["suspicious"].append(
                    {
                        key: entry.get(key)
                        for key in ("time", "original", "translated", "issues")
                    }
                )
        summary["suspicious"] = summary["suspicious"][-SUSPICIOUS_KEPT:]
        path = self.directory / "summary.json"
        tmp = path.with_name(".summary.json.tmp")
        tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, path)


def audit_dir(conf_uid: str) -> Path:
    from ..chat_history_manager import _sanitize_path_component

    return (
        Path("chat_history")
        / _sanitize_path_component(conf_uid)
        / ("translation_audit")
    )


# --------------------------------------------------------------------- 審核


def _messages(
    items: list[AuditItem],
    character: str,
    names: Iterable[str],
    catchphrases: Mapping[str, str],
) -> list[dict]:
    lines = []
    if character:
        lines.append(f"Character: {character}")
    names = [name for name in names if name]
    if names:
        lines.append("Her names to keep exactly: " + "、".join(names))
    if catchphrases:
        lines.append(
            "Her catchphrases (source → target): "
            + ", ".join(f"{s} → {t}" for s, t in catchphrases.items())
        )
    for number, item in enumerate(items, 1):
        target = _LANG_NAMES.get(item.target_lang, item.target_lang or "?")
        lines.append("")
        lines.append(f"{number}. Source: {item.original}")
        lines.append(f"   Translation ({target}): {item.translated}")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines).strip()},
    ]


class TranslationAuditor:
    """一個角色的審核佇列。submit／flush 都在背景 task 裡跑。"""

    def __init__(
        self,
        client: Any,
        store: AuditStore,
        *,
        character: str = "",
        names: Iterable[str] = (),
        catchphrases: Optional[Mapping[str, str]] = None,
        batch_size: int = BATCH_SIZE,
        max_queue: int = MAX_QUEUE,
        timeout: float = TIMEOUT_SECONDS,
    ):
        self.client = client
        self.store = store
        self.character = character
        self.names = list(names)
        self.catchphrases = dict(catchphrases or {})
        self.batch_size = batch_size
        self.timeout = timeout
        self._queue: deque[AuditItem] = deque(maxlen=max_queue)
        self._lock: Optional[asyncio.Lock] = None

    def submit(
        self,
        original: str,
        translated: str,
        target_lang: str,
        character: Optional[str] = None,
    ) -> None:
        """排一句，不問模型。佇列滿了，最舊的那句被擠掉。"""
        self._queue.append(
            AuditItem(
                original, translated, target_lang or "", character or self.character
            )
        )

    async def flush(self) -> None:
        """一輪結束：排著的全部審掉，每 batch_size 句問一次模型。"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            while self._queue:
                size = min(self.batch_size, len(self._queue))
                batch = [self._queue.popleft() for _ in range(size)]
                await self._audit(batch)

    async def _audit(self, batch: list[AuditItem]) -> None:
        """問一次模型。模型沒回、回不懂：只記下不用模型也看得出錯的那幾句。"""
        results: Optional[list[Optional[dict]]] = None
        messages = _messages(batch, self.character, self.names, self.catchphrases)
        try:
            reply = await asyncio.wait_for(self.client.complete(messages), self.timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Translation audit timed out after {self.timeout}s")
        except Exception as e:
            logger.warning(f"Translation audit failed ({type(e).__name__}: {e})")
        else:
            results = parse_reply(reply, len(batch))
            if results is None:
                logger.warning(f"Translation audit: unreadable reply {reply[:200]!r}")
        entries = []
        for index, item in enumerate(batch):
            result = results[index] if results else None
            plain = plain_issues(item.original, item.translated, item.target_lang)
            if result is None and not plain:
                continue
            issues = _merge(plain, result["issues"] if result else [], item)
            entries.append(
                {
                    "time": item.time,
                    "character": item.character,
                    "original": item.original,
                    "translated": item.translated,
                    "target_lang": item.target_lang,
                    "issues": issues,
                    "suggest": _grounded(
                        result["suggest"] if result else {}, item, issues
                    ),
                }
            )
            if issues:
                kinds = ",".join(issue["kind"] for issue in issues)
                logger.info(
                    f"Translation audit [{kinds}]: '{item.original}' -> "
                    f"'{item.translated}'"
                )
        skipped = len(batch) - len(entries)
        if skipped:
            logger.debug(f"Translation audit: {skipped} line(s) not reviewed")
        try:
            await asyncio.to_thread(self.store.record, entries)
        except Exception as e:
            logger.warning(f"Translation audit not saved ({type(e).__name__}: {e})")


# --------------------------------------------------------------------- 接上對話

_AUDITORS: dict[str, TranslationAuditor] = {}
_BACKGROUND: set[asyncio.Task] = set()


def auditor_for(character: Any) -> Optional[TranslationAuditor]:
    """這個角色的審核器；開關關著、沒有背景模型、沒有 conf_uid 就是 None。"""
    if not getattr(character, "translation_audit", False):
        return None
    conf_uid = str(getattr(character, "conf_uid", "") or "")
    if not conf_uid:
        return None
    client = background_client(
        character, max_tokens=MAX_TOKENS, timeout_seconds=TIMEOUT_SECONDS + 5
    )
    if client is None:
        return None
    auditor = _AUDITORS.get(conf_uid)
    if auditor is None:
        auditor = TranslationAuditor(client, AuditStore(audit_dir(conf_uid)))
        _AUDITORS[conf_uid] = auditor
    # 設定可能換過（模型、名字、口頭禪）：每則回覆用現在的。
    auditor.client = client
    auditor.character = str(getattr(character, "character_name", "") or "")
    auditor.names = list((getattr(character, "protected_names", None) or {}).keys())
    auditor.catchphrases = dict(getattr(character, "catchphrases", None) or {})
    return auditor


def _done(task: asyncio.Task) -> None:
    _BACKGROUND.discard(task)
    if not task.cancelled() and task.exception() is not None:
        error = task.exception()
        logger.warning(
            f"Translation audit task failed ({type(error).__name__}: {error})"
        )


def spawn(coro: Awaitable) -> None:
    """丟到背景跑，不等；留著參照，task 才不會跑到一半被回收。"""
    task = asyncio.ensure_future(coro)
    _BACKGROUND.add(task)
    task.add_done_callback(_done)


def flush_for(character: Any) -> None:
    """一輪結束：這個角色排著的句子在背景審掉。不等、不丟例外。

    只找已經有的審核器（這一輪有句子排進來才會有）；開關關著什麼都不做。
    """
    try:
        if not getattr(character, "translation_audit", False):
            return
        auditor = _AUDITORS.get(str(getattr(character, "conf_uid", "") or ""))
        if auditor is not None and auditor._queue:
            spawn(auditor.flush())
    except Exception as e:
        logger.warning(f"Translation audit flush skipped ({type(e).__name__}: {e})")


async def wait_background() -> None:
    """等背景審核都跑完（測試與對照腳本用）。"""
    while _BACKGROUND:
        await asyncio.gather(*list(_BACKGROUND), return_exceptions=True)


def reset() -> None:
    _AUDITORS.clear()


# --------------------------------------------------------------------- 角色頁


def suggestions(
    summary: Mapping[str, Any],
    protected_names: Optional[Mapping[str, Iterable[str]]] = None,
    catchphrases: Optional[Mapping[str, str]] = None,
    min_count: int = MIN_SUGGESTION_COUNT,
) -> dict[str, list[dict]]:
    """出現夠多次、角色設定裡還沒有的建議，次數多的在前。

    protected_names 的建議是「錯誤寫法 → 正確寫法」，加進角色設定時變成
    正確寫法底下多一個錯誤寫法；已經在那裡的就不再列。
    """
    variants = {
        (wrong, right)
        for right, wrongs in (protected_names or {}).items()
        for wrong in (wrongs or [])
    }
    have = {
        "protected_names": lambda s, t: (s, t) in variants,
        "catchphrases": lambda s, t: (catchphrases or {}).get(s) == t,
    }
    out: dict[str, list[dict]] = {}
    for kind in SUGGEST_KINDS:
        rows = [
            {"source": source, "target": target, "count": count}
            for source, targets in (summary.get(kind) or {}).items()
            for target, count in (targets or {}).items()
            if isinstance(count, int)
            and count >= min_count
            and not have[kind](source, target)
        ]
        out[kind] = sorted(rows, key=lambda r: (-r["count"], r["source"]))
    return out
