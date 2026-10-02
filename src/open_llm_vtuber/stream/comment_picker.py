"""聊天室的留言：哪些直接丟、哪些排隊、下一則回哪一則。

時間由呼叫端傳進來（now），這裡不自己讀時鐘，測試才能固定。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from .chat_source import ChatMessage

_LINK = re.compile(
    r"https?://|www\.|\b[\w-]+\.(?:com|net|org|tv|io|gg|me|ly|co|jp|tw)\b",
    re.IGNORECASE,
)
_TRAILING = "。．.！!～~ 　…"
_PRIORITY_KINDS = ("paid", "member")
_SEEN_LIMIT = 2000


@dataclass(frozen=True)
class PickerRules:
    blocklist: tuple[str, ...] = ()
    max_chars: int = 100
    max_age: float = 60.0
    viewer_cooldown: float = 120.0
    duplicate_window: float = 30.0
    queue_limit: int = 50
    names: tuple[str, ...] = ()  # 她的名字：留言叫到她就優先


def drop_reason(message: ChatMessage, rules: PickerRules) -> Optional[str]:
    text = message.text.strip()
    if len(text) > rules.max_chars:
        return "too_long"
    if _LINK.search(text):
        return "link"
    if text.startswith(("!", "！")):
        return "command"
    if not any(unicodedata.category(ch)[0] in "LN" for ch in text):
        return "no_words"
    lowered = text.casefold()
    if any(word.casefold() in lowered for word in rules.blocklist if word.strip()):
        return "blocked"
    return None


def _normalized(text: str) -> str:
    return "".join(text.casefold().split())


def _asks_or_calls(message: ChatMessage, names: tuple[str, ...]) -> bool:
    text = message.text
    if "?" in text or "？" in text:
        return True
    if text.rstrip(_TRAILING).endswith(("嗎", "吗")):
        return True
    lowered = text.casefold()
    return any(name and name.casefold() in lowered for name in names)


class CommentPicker:
    def __init__(self, rules: PickerRules):
        self.rules = rules
        self._queue: list[ChatMessage] = []
        self._seen: dict[str, float] = {}
        self._answered_at: dict[str, float] = {}
        self.read = 0
        self.dropped = 0

    def __len__(self) -> int:
        return len(self._queue)

    def offer(self, message: ChatMessage, now: float) -> Optional[str]:
        """收一則留言。丟掉就回理由，排進隊伍回 None。"""
        self.read += 1
        reason = drop_reason(message, self.rules)
        key = _normalized(message.text)
        if reason is None:
            last = self._seen.get(key)
            if last is not None and now - last < self.rules.duplicate_window:
                reason = "duplicate"
        self._seen[key] = now
        if len(self._seen) > _SEEN_LIMIT:
            self._seen = {
                k: t
                for k, t in self._seen.items()
                if now - t < self.rules.duplicate_window
            }
        if reason:
            self.dropped += 1
            return reason
        self._queue.append(message)
        if len(self._queue) > self.rules.queue_limit:
            self._queue.pop(0)
            self.dropped += 1
        return None

    def pick(self, now: float) -> Optional[ChatMessage]:
        """挑下一則並從隊伍拿掉；沒有能回的回 None。"""
        fresh = [m for m in self._queue if now - m.timestamp <= self.rules.max_age]
        self.dropped += len(self._queue) - len(fresh)
        self._queue = fresh
        ready = [
            m
            for m in self._queue
            if m.author not in self._answered_at
            or now - self._answered_at[m.author] >= self.rules.viewer_cooldown
        ]
        if not ready:
            return None
        best = max(
            ready,
            key=lambda m: (
                m.kind in _PRIORITY_KINDS,
                _asks_or_calls(m, self.rules.names),
                m.author not in self._answered_at,
                m.timestamp,
            ),
        )
        self._queue.remove(best)
        self._answered_at[best.author] = now
        return best
