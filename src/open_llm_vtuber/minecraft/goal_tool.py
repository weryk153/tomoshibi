"""她下目標的工具。只在 Minecraft 模式開著時註冊到她的 agent 上。

工具結果用英文：那是她的身體（Mindcraft）回的話，她讀得懂，會用自己的語言講。
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ai_character_engine.tools.models import ToolDefinition

GOAL_TOOL = ToolDefinition(
    name="minecraft_do",
    description=(
        "Tell your body in Minecraft what to do next. Write the goal as one short "
        "English sentence, e.g. 'collect 10 oak logs', 'build a small shelter before "
        "night', 'go mine iron underground'. Your body replies with what it will do."
    ),
    parameters={
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "One short English sentence saying what to do.",
            }
        },
        "required": ["goal"],
        "additionalProperties": False,
    },
)


def make_goal_handler(
    client: Any, from_name: str, timeout: Callable[[], float]
) -> Callable[..., Awaitable[str]]:
    async def minecraft_do(goal: str = "", **_: Any) -> str:
        text = str(goal or "").strip()
        if not text:
            return "Say what to do: the goal was empty."
        if not client.connected:
            return "Not connected to Minecraft right now."
        if not client.in_game:
            return "Your body is not in the game right now."
        reply = await client.ask(from_name, text, timeout())
        if reply is None:
            return "No reply from your body yet; it may still be working on it."
        return f"Your body says: {reply}"

    return minecraft_do
