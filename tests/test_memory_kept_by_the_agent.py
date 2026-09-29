"""主機這一側：agent 自己記得對方的時候，記憶頁與記憶整理怎麼配合。

不需要引擎。character_engine_agent 那一側在 test_engine_replaces_core_memory.py。
"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber import memory_core, memory_route


def _context(conf_uid, history_uid, agent_engine):
    return SimpleNamespace(
        character_config=SimpleNamespace(conf_uid=conf_uid),
        history_uid=history_uid,
        agent_engine=agent_engine,
    )


def test_the_route_asks_the_agent_that_keeps_the_memory_itself():
    keeper = SimpleNamespace(
        conversation_memory=lambda history_uid: "",
        rewrite_conversation_memory=lambda history_uid, text: None,
    )
    contexts = {
        "other": _context("charB", "conv1", keeper),
        "basic": _context("charA", "conv2", SimpleNamespace()),
    }
    assert memory_route._memory_keeper(contexts, "charA") is None

    contexts["engine"] = _context("charA", "conv3", keeper)
    assert memory_route._memory_keeper(contexts, "charA") is keeper


def test_consolidation_keeps_her_own_half_and_leaves_the_users_to_the_engine(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    async def rewrite(*_args, **_kwargs):
        return "對方：名字是晨星。\nMao：喜歡烏龍茶。"

    monkeypatch.setattr(memory_core, "_request_rewrite", rewrite)

    async def run(**more):
        await memory_core.consolidate_core_memory(
            "mao",
            "h1",
            "我叫晨星",
            "我喜歡烏龍茶",
            "http://x",
            "m",
            character_name="Mao",
            **more,
        )
        return (
            memory_core.load_core_memory("mao", "h1"),
            memory_core.load_self_memory("mao"),
        )

    conversation, her_own = asyncio.run(run(conversation_half=False))

    assert conversation == ""
    assert "喜歡烏龍茶" in her_own


def test_the_conversation_asks_the_agent_whether_it_keeps_the_memory():
    import inspect

    from src.open_llm_vtuber.conversations import single_conversation

    src = inspect.getsource(single_conversation.process_single_conversation)

    assert "conversation_half=not hasattr(" in src
    assert '"conversation_memory"' in src
