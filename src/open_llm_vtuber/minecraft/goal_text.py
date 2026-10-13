"""她用文字下的目標：`[minecraft_do: collect 10 oak logs]`。

實測（2026-10-14，Qwen3.5 27B）：在引擎「輸出只有你說出口的台詞」的框架下，模型寧可把
工具呼叫寫成文字也不走原生的 function calling。所以照 Mindcraft 自己的做法：認文字裡的
標記，抓出目標送給身體，講話和字幕裡把它拿掉。原生的工具照樣註冊，兩條路都收。

``sink`` 由 Minecraft 控制器在開始時設、停止時清；沒開模式時標記只會被拿掉，不會送。
"""

from __future__ import annotations

import asyncio
import re
from typing import Awaitable, Callable, Optional

from loguru import logger

# 允許的寫法：[minecraft_do: goal]、minecraft_do: goal、[minecraft_do("goal")]；目標到右括號或行尾為止。
GOAL_RE = re.compile(
    r"\[?\s*minecraft_do\s*(?:[:：]|\(\s*)\s*[\"“]?\s*([^\]\n\"”)]+)\s*[\"”]?\s*\)?\s*\]?",
    re.IGNORECASE,
)

sink: Optional[Callable[[str], Awaitable[None]]] = None
_recent: dict[str, float] = {}
REPEAT_WINDOW = 15.0  # 同一個目標幾秒內不重送（她常在一輪裡寫兩三次）


def extract_goals(text: str) -> tuple[str, list[str]]:
    """把目標從一句話裡抓出來。回 (拿掉標記後的句子, 目標們)。"""
    goals = [m.group(1).strip() for m in GOAL_RE.finditer(text)]
    goals = [g for g in goals if g]
    clean = GOAL_RE.sub("", text)
    clean = re.sub(r"[ \t]{2,}", " ", clean).strip()
    return clean, goals


def dispatch(goals: list[str]) -> None:
    """送給身體（背景跑）；沒開 Minecraft 模式就只記一筆。"""
    import time

    now = time.monotonic()
    for goal in goals:
        key = goal.lower()
        if now - _recent.get(key, float("-inf")) < REPEAT_WINDOW:
            continue
        _recent[key] = now
        if sink is None:
            logger.debug(f"[minecraft] goal in text but mode is off: {goal}")
            continue

        async def _send(goal: str = goal) -> None:
            try:
                await sink(goal)  # type: ignore[misc]
                logger.info(f"[minecraft] goal sent: {goal}")
            except Exception as error:
                logger.warning(f"[minecraft] could not send goal {goal!r}: {error}")

        asyncio.create_task(_send())
