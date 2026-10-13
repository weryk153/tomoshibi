"""遊戲事件的隊伍：節流、攢著、合併成一輪的備註；閒下來多久要她決定下一步。

不讀時鐘，時間由呼叫端傳入（跟 CommentPicker 一樣）。直播流程和私聊迴圈都從這裡
pick，同一時間只有一邊在 pick（直播中私聊迴圈不動）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .events import GameEvent, GameState, state_summary

IDLE_NOTE = (
    "你的身體在遊戲裡閒著沒事做。想做什麼就用 minecraft_do 工具、用一句英文交代；"
    "也可以只聊聊再說。"
)
EVENTS_HEADING = "遊戲裡剛發生："
STATE_HEADING = "你在遊戲裡目前的狀態："


@dataclass(frozen=True)
class FeedRules:
    idle_seconds: float = 15.0
    idle_cooldown: float = 60.0
    event_cooldown: float = 30.0


@dataclass(frozen=True)
class GameTurn:
    kind: str
    notes: tuple[str, ...]
    urgent: bool
    timestamp: float


class GameFeed:
    def __init__(self, rules: FeedRules):
        self.rules = rules
        self.latest: Optional[GameState] = None
        self._events: list[tuple[GameEvent, float]] = []
        self._last_kind_at: dict[str, float] = {}
        self._idle_since: Optional[float] = None
        self._last_idle_turn = float("-inf")

    def pending(self) -> int:
        return len(self._events)

    def offer(self, event: GameEvent, now: float) -> bool:
        if not event.urgent:
            last = self._last_kind_at.get(event.kind)
            if last is not None and now - last < self.rules.event_cooldown:
                return False
        self._last_kind_at[event.kind] = now
        self._events.append((event, now))
        return True

    def observe(self, state: GameState, now: float) -> None:
        self.latest = state
        if not state.is_idle:
            self._idle_since = None
            return
        if self._idle_since is None:
            self._idle_since = now

    def reset_idle(self) -> None:
        """斷線或機器人不在遊戲裡時清掉閒置起點；latest 留著，只給狀態顯示用。

        MindServer 對不在遊戲裡的機器人不再送狀態，不清的話最後一筆「閒著」會一直
        算下去，每個冷卻期就問她一次要做什麼。
        """
        self._idle_since = None

    def _idle_due(self, now: float) -> bool:
        """閒夠久、而且距離上次問她夠久。同一段閒置裡冷卻過了會再問一次。"""
        if self._idle_since is None:
            return False
        if now - self._idle_since < self.rules.idle_seconds:
            return False
        return now - self._last_idle_turn >= self.rules.idle_cooldown

    def pick(
        self, now: float, *, urgent_only: bool = False, idle_allowed: bool = True
    ) -> Optional[GameTurn]:
        urgent = any(event.urgent for event, _ in self._events)
        if urgent_only and not urgent:
            return None
        if self._events:
            lines = "\n".join(f"- {event.text}" for event, _ in self._events)
            self._events.clear()
            return GameTurn(
                "event", self._with_state((EVENTS_HEADING + "\n" + lines,)), urgent, now
            )
        if idle_allowed and self._idle_due(now):
            self._last_idle_turn = now
            return GameTurn("idle", self._with_state(()) + (IDLE_NOTE,), False, now)
        return None

    def _with_state(self, notes: tuple[str, ...]) -> tuple[str, ...]:
        if self.latest is None:
            return notes
        return notes + (STATE_HEADING + state_summary(self.latest),)
