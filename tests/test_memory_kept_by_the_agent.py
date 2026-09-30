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


def test_the_route_asks_the_connection_whose_conversation_it_resolved():
    """一個連線還在初始化（沒有 history_uid、agent 也還沒好）時，記憶頁不能因此
    退回去讀 core_memory.md——它讀寫的對話是另一個連線的。"""
    keeper = SimpleNamespace(
        conversation_memory=lambda history_uid: "",
        rewrite_conversation_memory=lambda history_uid, text: None,
    )
    contexts = {
        "engine": _context("charA", "conv1", keeper),
        "starting": _context("charA", "", None),
    }
    assert memory_route._resolve_history_uid(contexts, "charA") == "conv1"
    assert memory_route._memory_keeper(contexts, "charA") is keeper


def test_saving_forgets_only_what_the_page_started_from():
    """起點由前端送：伺服器記不住某個頁面顯示的是哪一版（同一段對話可以開兩個
    頁面，切分頁回來也不重載文字框）。沒送就整份取代。"""
    edits = []

    def rewrite(history_uid, text, edited_from=None):
        edits.append((history_uid, text, edited_from))

    keeper = SimpleNamespace(rewrite_conversation_memory=rewrite)
    memory_route._save_through(
        keeper, "conv1", "對方：喜歡烏龍茶。", "對方：住在台北。"
    )
    memory_route._save_through(keeper, "conv1", "對方：喜歡烏龍茶。", None)
    memory_route._save_through(keeper, "conv1", "對方：喜歡烏龍茶。", 42)

    assert edits == [
        ("conv1", "對方：喜歡烏龍茶。", "對方：住在台北。"),
        ("conv1", "對方：喜歡烏龍茶。", None),
        ("conv1", "對方：喜歡烏龍茶。", None),
    ]


def test_the_endpoints_pass_the_starting_point_and_skip_the_lock_for_the_agent():
    import inspect

    src = inspect.getsource(memory_route.init_memory_route)
    assert (
        src.count(
            '_save_through(keeper, history_uid, content, body.get("edited_from"))'
        )
        == 1
    )
    assert src.count("needed=_needs_consolidation_lock(keeper=keeper)") == 2


def test_the_page_sends_the_starting_point():
    from pathlib import Path

    page = Path(
        "frontend-src/src/renderer/src/components/sidebar/setting/memory.tsx"
    ).read_text()
    api = Path("frontend-src/src/renderer/src/api/memory.ts").read_text()
    assert (
        "saveMemoryContent(\n      baseUrl, confUid, contentDraft, memory?.content,\n    )"
        in page
    )
    assert "edited_from: editedFrom" in api


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


def test_the_agents_memory_is_not_held_up_by_the_hosts_consolidation():
    """實機：整理「她自己的記憶」跑到一半（最長 60 秒）時按下清除，記憶頁回 503
    「記憶正在整理中」。整理碰的是 self_memory.md，跟引擎的記憶無關，不用等它。"""
    assert memory_route._needs_consolidation_lock(keeper=object()) is False
    assert memory_route._needs_consolidation_lock(keeper=None) is True
