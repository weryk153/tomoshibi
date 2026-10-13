"""minecraft_do：她用一句英文交代身體要做什麼，回話當工具結果。"""

import asyncio

from src.open_llm_vtuber.minecraft.goal_tool import GOAL_TOOL, make_goal_handler


class FakeClient:
    def __init__(self, reply="On it!", connected=True, in_game=True):
        self.reply, self.connected, self.in_game = reply, connected, in_game
        self.asked = []

    async def ask(self, from_name, message, timeout):
        self.asked.append((from_name, message, timeout))
        return self.reply


def test_definition_shape():
    assert GOAL_TOOL.name == "minecraft_do"
    assert GOAL_TOOL.parameters["type"] == "object"
    assert GOAL_TOOL.parameters["required"] == ["goal"]
    assert "English" in GOAL_TOOL.description


def test_sends_goal_and_returns_reply():
    client = FakeClient()
    handler = make_goal_handler(client, "芙莉蓮", lambda: 20.0)
    result = asyncio.run(handler(goal="collect 10 oak logs"))
    assert client.asked == [("芙莉蓮", "collect 10 oak logs", 20.0)]
    assert "On it!" in result


def test_empty_goal_not_connected_not_in_game_and_timeout():
    handler = make_goal_handler(FakeClient(), "她", lambda: 1.0)
    assert "goal" in asyncio.run(handler(goal="   ")).lower()
    off = make_goal_handler(FakeClient(connected=False), "她", lambda: 1.0)
    assert "not connected" in asyncio.run(off(goal="x")).lower()
    out = make_goal_handler(FakeClient(in_game=False), "她", lambda: 1.0)
    assert "not in the game" in asyncio.run(out(goal="x")).lower()
    silent = make_goal_handler(FakeClient(reply=None), "她", lambda: 1.0)
    assert "no reply" in asyncio.run(silent(goal="x")).lower()
