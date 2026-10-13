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
    "你正在開 Minecraft 生存實況。備註是遊戲裡剛發生的事和你目前的狀態。只講一句，說你"
    "現在在做什麼或剛發生了什麼；備註沒提到的（礦、動物、村莊、物品）就當沒看到，不要編，"
    "不要問觀眾問題，不要重複上一輪講過的話，沒有新鮮事就只講半句帶過。要讓身體做事，就在"
    "台詞裡自己一行寫 [minecraft_do: 一句英文]，例如 [minecraft_do: craft a stone pickaxe]；"
    "一輪最多一個目標，身體正在做事就不要再下。"
)


def game_turn_metadata(notes) -> dict:
    """遊戲那一輪要合進主動開口 metadata 的東西：備註、清掉題材、換掉指令。"""
    return {
        "notes": list(notes),
        "proactive_material": [],
        # 事件和狀態直接接在指令後面（模型最看重最後那段），不然 27B 會丟著不講。
        "proactive_instruction": GAME_TURN_INSTRUCTION
        + "\n\n第一句一定要回應下面這些：\n"
        + "\n".join(notes),
        # 不要一直問觀眾「你們覺得呢」：引擎會把問句濾掉。
        "proactive_forbid_question": True,
    }


def suggest_goal(state) -> str:
    """照背包和時段算生存的下一步。27B 自己想的目標太虛（look around、punch tree），
    給它一句能照抄的。"""
    inv = state.inventory if state is not None else {}

    def have(*names):
        return sum(v for k, v in inv.items() if any(n in k for n in names))

    logs = have("_log")
    planks = have("_planks")
    if state is not None and state.time_label == "Night" and have("torch") < 1:
        return "dig into the hillside and make a small shelter"
    if have("crafting_table") < 1 and logs + planks // 4 < 4:
        return "collect 10 oak logs"
    if have("crafting_table") < 1:
        return "craft a crafting table"
    if have("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe") < 1:
        if logs + planks // 4 < 2:
            return "collect 6 oak logs"
        return "craft a wooden pickaxe"
    if have("stone_pickaxe", "iron_pickaxe") < 1:
        if have("cobblestone") < 3:
            return "collect 8 cobblestone"
        return "craft a stone pickaxe"
    if have("torch") < 4:
        if have("coal") < 1:
            return "collect 5 coal"
        return "craft 8 torches"
    if (
        state is not None
        and state.hunger < 12
        and have("beef", "porkchop", "bread", "apple", "mutton", "chicken") < 1
    ):
        return "kill a cow and collect the beef"
    if have("iron_ingot", "raw_iron") < 3:
        return "mine 5 raw iron underground"
    return "collect 10 oak logs"


def idle_note(state) -> str:
    return IDLE_NOTE


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
    suggested: str = ""  # 身體閒著時程式算好的下一步；她沒給具體目標就照這個做


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
                notes = notes + (idle_note(self.latest),)
            return GameTurn("event", notes, urgent, now)
        if ask_idle:
            self._last_idle_turn = now
            return GameTurn(
                "idle", self._with_state(()) + (idle_note(self.latest),), False, now
            )
        return None

    def _with_state(self, notes: tuple[str, ...]) -> tuple[str, ...]:
        if self.latest is None:
            return notes
        return notes + (STATE_HEADING + state_summary(self.latest),)
