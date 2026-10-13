"""Mindcraft 每秒送來的狀態，跟上一秒比，變成她聽得懂的事件。

純函式，不讀時鐘、不碰網路。事件的文字是給她看的備註（中文），她用自己的語言講。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

HOSTILE = frozenset(
    {
        "zombie",
        "skeleton",
        "creeper",
        "spider",
        "cave_spider",
        "enderman",
        "witch",
        "drowned",
        "husk",
        "stray",
        "phantom",
        "pillager",
        "vindicator",
        "slime",
        "blaze",
        "ghast",
        "piglin",
        "hoglin",
        "zombified_piglin",
        "wither_skeleton",
        "warden",
        "silverfish",
        "endermite",
        "ravager",
        "evoker",
        "vex",
        "guardian",
    }
)
LOW_HEALTH = 6  # 20 的三分之一往下取整
RESPAWN_JUMP = 30.0  # 一秒內移動超過這麼多格又滿血，是死了重生


@dataclass(frozen=True)
class GameState:
    health: int = 20
    hunger: int = 20
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    dimension: str = ""
    biome: str = ""
    time_label: str = ""
    action: str = "Idle"
    is_idle: bool = True
    inventory: dict[str, int] = field(default_factory=dict)
    entities: tuple[str, ...] = ()


@dataclass(frozen=True)
class GameEvent:
    kind: str
    text: str
    urgent: bool = False


@dataclass(frozen=True)
class EventRules:
    notable_items: tuple[str, ...] = ()


def _int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _counts(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(k): _int(v, 0) for k, v in value.items()}
    counts: dict[str, int] = {}
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("name"):
                name = str(item["name"])
                counts[name] = counts.get(name, 0) + _int(item.get("count", 1), 1)
    return counts


def parse_state(raw: object) -> GameState:
    data = _dict(raw)
    play = _dict(data.get("gameplay"))
    pos = _dict(play.get("position"))
    action = data.get("action")
    if isinstance(action, dict):
        current = str(action.get("current") or "Idle")
        idle = bool(action.get("isIdle", current == "Idle"))
    else:
        current = str(action or "Idle")
        idle = current == "Idle"
    nearby = _dict(data.get("nearby"))
    entities = nearby.get("entityTypes")
    return GameState(
        health=_int(play.get("health"), 20),
        hunger=_int(play.get("hunger"), 20),
        position=(_float(pos.get("x")), _float(pos.get("y")), _float(pos.get("z"))),
        dimension=str(play.get("dimension") or ""),
        biome=str(play.get("biome") or ""),
        time_label=str(play.get("timeLabel") or ""),
        action=current,
        is_idle=idle,
        inventory=_counts(_dict(data.get("inventory")).get("counts")),
        entities=tuple(str(e) for e in entities) if isinstance(entities, list) else (),
    )


def state_summary(state: GameState) -> str:
    x, y, z = state.position
    parts = [
        f"血量 {state.health}/20",
        f"飢餓 {state.hunger}/20",
        f"正在做：{state.action}",
        f"位置 ({x:.0f}, {y:.0f}, {z:.0f})",
    ]
    if state.biome:
        parts.append(f"地點 {state.biome}")
    if state.time_label:
        parts.append(f"時段 {state.time_label}")
    if state.entities:
        parts.append("附近有 " + "、".join(state.entities[:6]))
    return "、".join(parts)


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5


def diff_events(
    prev: Optional[GameState], cur: GameState, rules: EventRules
) -> list[GameEvent]:
    if prev is None:
        return []
    events: list[GameEvent] = []
    died = (prev.health > 0 and cur.health <= 0) or (
        0 < prev.health <= LOW_HEALTH
        and cur.health >= 20
        and _distance(prev.position, cur.position) > RESPAWN_JUMP
    )
    if died:
        events.append(
            GameEvent("death", "你在遊戲裡死掉了，東西可能掉在原地。", urgent=True)
        )
    elif prev.health > LOW_HEALTH >= cur.health > 0:
        events.append(
            GameEvent("low_health", f"你的血量只剩 {cur.health}/20，很危險。")
        )
    for name in rules.notable_items:
        gained = cur.inventory.get(name, 0) - prev.inventory.get(name, 0)
        if gained > 0:
            events.append(GameEvent("found_item", f"你拿到了 {gained} 個 {name}。"))
    if not prev.is_idle and cur.is_idle:
        events.append(GameEvent("finished", f"你剛做完「{prev.action}」，現在閒著。"))
    new_hostile = sorted((set(cur.entities) - set(prev.entities)) & HOSTILE)
    if new_hostile:
        events.append(
            GameEvent("hostile", "附近出現了 " + "、".join(new_hostile) + "。")
        )
    if cur.time_label == "Night" and prev.time_label != "Night":
        events.append(GameEvent("night", "遊戲裡天黑了。"))
    return events
