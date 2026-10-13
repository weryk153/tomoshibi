"""遊戲事件的隊伍：節流、攢著、合併成一輪的備註；閒下來多久要她決定下一步。

不讀時鐘，時間由呼叫端傳入（跟 CommentPicker 一樣）。直播流程和私聊迴圈都從這裡
pick，同一時間只有一邊在 pick（直播中私聊迴圈不動）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .events import GameEvent, GameState, state_summary

IDLE_NOTE = (
    "你的身體在遊戲裡閒著沒事做。這一輪一定要替它決定下一件事：回覆的第一行就寫 "
    "[minecraft_do: 一句英文]，然後講一句話就好；沒有這一行，身體會一直站著不動。"
    "一次只寫一個目標，要具體、帶數量，照生存順序挑（木頭→工作台→木鎬→圓石→石鎬→煤→火把"
    "→食物→天黑前的小屋）。好的例子：[minecraft_do: collect 10 oak logs]、"
    "[minecraft_do: craft a crafting table]、[minecraft_do: craft a wooden pickaxe]、"
    "[minecraft_do: collect 8 cobblestone]、[minecraft_do: craft a stone pickaxe]、"
    "[minecraft_do: collect 5 coal]、[minecraft_do: craft 8 torches]、"
    "[minecraft_do: kill a cow and collect the beef]、"
    "[minecraft_do: dig into the hillside and make a small shelter]。"
    "不要寫 look around、walk forward 這種沒有結果的事；背包有什麼就看狀態列，沒材料的東西先別合成。"
)
EVENTS_HEADING = "遊戲裡剛發生："
STATE_HEADING = "你在遊戲裡目前的狀態："
# 遊戲那一輪給引擎的指令，取代主動開口原本的（找話題、聊新聞）：不然她會丟下遊戲聊別的。
GAME_TURN_INSTRUCTION = (
    "你正在開 Minecraft 生存實況。備註是遊戲裡剛發生的事和你目前的狀態。像實況主一樣對著"
    "看台講一句、最多兩句，動作比話重要，只講備註裡真的有的事；備註沒提到的（礦、動物、村莊、物品）就當沒看到，"
    "不要編，也不要換到別的話題。要讓身體做事，就在台詞裡"
    "自己一行寫 [minecraft_do: 一句英文]，例如 [minecraft_do: craft a stone pickaxe]；"
    "一輪最多一個目標，身體正在做事就不要再下。"
)


def game_turn_metadata(notes) -> dict:
    """遊戲那一輪要合進主動開口 metadata 的東西：備註、清掉題材、換掉指令。"""
    return {
        "notes": list(notes),
        "proactive_material": [],
        "proactive_instruction": GAME_TURN_INSTRUCTION,
    }


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
        # 不在遊戲裡就不問她閒置目標。閘放在 feed 上，私聊迴圈和直播流程
        # 都從這裡 pick，才不會有一邊漏掉；由控制器接上連線狀態。
        self.ready: Callable[[], bool] = lambda: True
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

    def pick(self, now: float, *, urgent_only: bool = False) -> Optional[GameTurn]:
        urgent = any(event.urgent for event, _ in self._events)
        if urgent_only and not urgent:
            return None
        # 身體閒著時，事件那一輪也一併問她要做什麼：事件每隔幾十秒就來一個，
        # 不這樣做「閒下來、決定目標」永遠排不到，她會一直評論卻不動。
        ask_idle = self.ready() and self._idle_due(now)
        if self._events:
            lines = "\n".join(f"- {event.text}" for event, _ in self._events)
            self._events.clear()
            notes = self._with_state((EVENTS_HEADING + "\n" + lines,))
            if ask_idle:
                self._last_idle_turn = now
                notes = notes + (IDLE_NOTE,)
            return GameTurn("event", notes, urgent, now)
        if ask_idle:
            self._last_idle_turn = now
            return GameTurn("idle", self._with_state(()) + (IDLE_NOTE,), False, now)
        return None

    def _with_state(self, notes: tuple[str, ...]) -> tuple[str, ...]:
        if self.latest is None:
            return notes
        return notes + (STATE_HEADING + state_summary(self.latest),)
