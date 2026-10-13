"""Minecraft 的一輪怎麼交給主視窗；工具怎麼跟著連線走。"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.minecraft.feed import GameTurn
from src.open_llm_vtuber.minecraft.goal_tool import GOAL_TOOL
from src.open_llm_vtuber.minecraft.host import WebSocketMinecraftHost


class Agent:
    def __init__(self):
        self.tools = {}

    def add_tool(self, definition, handler):
        self.tools[definition.name] = handler

    def remove_tool(self, name):
        self.tools.pop(name, None)


def context(history="h1", name="芙莉蓮"):
    return SimpleNamespace(
        history_uid=history,
        agent_engine=Agent(),
        character_config=SimpleNamespace(
            conf_uid="c", character_name=name, conf_name="frieren"
        ),
    )


class Socket:
    async def send_text(self, payload):
        pass


def ws(**contexts):
    return SimpleNamespace(
        client_contexts=dict(contexts),
        client_connections={uid: Socket() for uid in contexts},
        client_last_active={uid: i for i, uid in enumerate(contexts)},
        current_conversation_tasks={},
        chat_group_manager=SimpleNamespace(get_client_group=lambda uid: None),
        received_data_buffers={},
        broadcast_to_group=None,
        stage_clients=set(),
        _is_stage=lambda uid: uid == "stage",
        _push_history_to_peers=_push,
    )


pushed = []


async def _push(uid):
    pushed.append(uid)


async def handler(**_):
    return "ok"


def turn():
    return GameTurn("event", ("遊戲裡剛發生：\n- 天黑了",), False, 0.0)


def test_install_puts_tool_on_every_agent_and_ensure_adds_to_new_ones():
    a, b = context(), context()
    host = WebSocketMinecraftHost(ws(a=a, b=b))
    host.install_tool(handler)
    assert (
        GOAL_TOOL.name in a.agent_engine.tools
        and GOAL_TOOL.name in b.agent_engine.tools
    )
    c = context()
    host.ensure_tool(c)
    assert GOAL_TOOL.name in c.agent_engine.tools
    host.uninstall_tool()
    assert not a.agent_engine.tools and not b.agent_engine.tools
    d = context()
    host.ensure_tool(d)
    assert not d.agent_engine.tools


def test_private_turn_goes_to_most_recent_non_stage_window_with_notes():
    calls = []

    async def trigger(**kwargs):
        calls.append(kwargs)
        kwargs["current_conversation_tasks"][kwargs["client_uid"]] = (
            asyncio.create_task(asyncio.sleep(0))
        )

    old, new, stage = context(), context(), context()
    w = ws(old=old, new=new, stage=stage)
    w.client_last_active = {"old": 1, "new": 5, "stage": 9}
    host = WebSocketMinecraftHost(w, trigger=trigger)
    host.install_tool(handler)
    pushed.clear()
    result = asyncio.run(host.run_private_turn(turn()))
    assert result == "ok"
    assert calls[0]["client_uid"] == "new"
    assert calls[0]["msg_type"] == "ai-speak-signal"
    meta = calls[0]["extra_metadata"]
    assert meta["notes"] == ["遊戲裡剛發生：\n- 天黑了"]
    # 遊戲那一輪不帶主動開口的題材（新聞、話題），指令也換成講遊戲的，不然她會聊別的。
    assert meta["proactive_material"] == []
    assert "Minecraft" in meta["proactive_instruction"]
    assert pushed == ["new"]


def test_private_turn_waits_for_running_turn_and_ensures_tool_first():
    seen = []

    async def trigger(**kwargs):
        seen.append(GOAL_TOOL.name in kwargs["context"].agent_engine.tools)
        kwargs["current_conversation_tasks"]["u"] = asyncio.create_task(
            asyncio.sleep(0)
        )

    u = context()
    w = ws(u=u)
    host = WebSocketMinecraftHost(w, trigger=trigger)
    host.install_tool(handler)
    u.agent_engine = Agent()  # 換角色換了 agent，工具掉了

    async def go():
        w.current_conversation_tasks["u"] = asyncio.create_task(asyncio.sleep(0.01))
        return await host.run_private_turn(turn())

    assert asyncio.run(go()) == "ok"
    assert seen == [True]


def test_no_window_or_no_history_is_interrupted():
    host = WebSocketMinecraftHost(ws())
    assert asyncio.run(host.run_private_turn(turn())) == "interrupted"
    host = WebSocketMinecraftHost(ws(u=context(history="")))
    assert asyncio.run(host.run_private_turn(turn())) == "interrupted"


def test_speaker_name():
    assert (
        WebSocketMinecraftHost(ws(u=context(name="芙莉蓮"))).speaker_name() == "芙莉蓮"
    )
    assert WebSocketMinecraftHost(ws(u=context(name=""))).speaker_name() == "frieren"
    assert WebSocketMinecraftHost(ws()).speaker_name() == "Tomoshibi"


def test_still_running_turn_after_timeout_skips_without_triggering(monkeypatch):
    from src.open_llm_vtuber.minecraft import host as host_module

    monkeypatch.setattr(host_module, "PRIVATE_TURN_WAIT_SECONDS", 0.01)
    calls = []

    async def trigger(**kwargs):
        calls.append(kwargs)

    u = context()
    w = ws(u=u)
    host = WebSocketMinecraftHost(w, trigger=trigger)

    async def go():
        stuck = asyncio.create_task(asyncio.sleep(30))
        w.current_conversation_tasks["u"] = stuck
        try:
            return await host.run_private_turn(turn())
        finally:
            stuck.cancel()

    assert asyncio.run(go()) == "interrupted"
    assert calls == []


def test_cancelling_host_does_not_cancel_the_conversation_task():
    inner = {}

    async def trigger(**kwargs):
        async def speak():
            await asyncio.sleep(0.05)
            return "spoken"

        inner["task"] = asyncio.create_task(speak())
        kwargs["current_conversation_tasks"][kwargs["client_uid"]] = inner["task"]

    w = ws(u=context())
    host = WebSocketMinecraftHost(w, trigger=trigger)

    async def go():
        runner = asyncio.create_task(host.run_private_turn(turn()))
        await asyncio.sleep(0.01)
        runner.cancel()
        try:
            await runner
        except asyncio.CancelledError:
            cancelled = True
        else:
            cancelled = False
        assert not inner["task"].cancelled()
        return cancelled, await inner["task"]

    assert asyncio.run(go()) == (True, "spoken")
