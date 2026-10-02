"""主機這一側：agent 自己記得對方的時候，記憶頁與記憶整理怎麼配合。

不需要引擎。character_engine_agent 那一側在 test_engine_replaces_core_memory.py。
"""

from types import SimpleNamespace

from src.open_llm_vtuber import memory_route


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
        "no-memory": _context("charA", "conv2", SimpleNamespace()),
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


def test_the_endpoints_pass_the_starting_point():
    import inspect

    src = inspect.getsource(memory_route.init_memory_route)
    assert (
        src.count(
            '_save_through(keeper, history_uid, content, body.get("edited_from"))'
        )
        == 1
    )


def test_the_page_sends_the_starting_point():
    from pathlib import Path

    page = Path(
        "frontend-src/src/renderer/src/components/sidebar/setting/memory.tsx"
    ).read_text(encoding="utf-8")
    api = Path("frontend-src/src/renderer/src/api/memory.ts").read_text(
        encoding="utf-8"
    )
    # 頁面改成改了就存（離開欄位才送）：起點在送出的那一刻取「現在存著的那一版」。
    assert "saveMemoryContent(baseUrl, edit.uid, edit.draft, from)" in page
    assert "startingPoint(edit.uid, (m) => m.content)" in page
    assert "edited_from: editedFrom" in api
    # 她自己的記憶也是：引擎記的那一份同樣只刪頁面上有、存回來不見的行。
    assert "saveSelfMemoryContent(baseUrl, edit.uid, edit.draft, from)" in page
    assert "startingPoint(edit.uid, (m) => m.self_content)" in page
    assert api.count("edited_from: editedFrom") == 2


def _page(monkeypatch, tmp_path, contexts):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(memory_route, "_is_local_request", lambda request: True)
    monkeypatch.setattr(memory_route, "_resolve_conf_uid", lambda value: (value, None))
    app = FastAPI()
    app.include_router(memory_route.init_memory_route(contexts))
    return TestClient(app)


class _Keeper:
    def __init__(self):
        self.her_own = "紅莉栖喜歡胡椒博士。"
        self.edits = []

    def conversation_memory(self, history_uid):
        return ""

    def rewrite_conversation_memory(self, history_uid, text, **_):
        pass

    def self_memory(self):
        return self.her_own

    def rewrite_self_memory(self, text, *, edited_from=None):
        self.edits.append((text, edited_from))
        self.her_own = text


def test_the_memory_page_shows_and_edits_her_own_memory_in_the_engine(
    tmp_path, monkeypatch
):
    keeper = _Keeper()
    client = _page(monkeypatch, tmp_path, {"engine": _context("kurisu", "h1", keeper)})
    old_file = tmp_path / "chat_history" / "kurisu" / "self_memory.md"
    old_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.write_text("紅莉栖：舊檔案裡的。", encoding="utf-8")

    shown = client.get("/api/memory", params={"conf_uid": "kurisu"}).json()
    saved = client.post(
        "/api/memory/self",
        json={
            "conf_uid": "kurisu",
            "content": "紅莉栖怕蟑螂。",
            "edited_from": "紅莉栖喜歡胡椒博士。",
        },
    ).json()
    cleared = client.post("/api/memory/self/clear", json={"conf_uid": "kurisu"}).json()

    assert shown["self_content"] == "紅莉栖喜歡胡椒博士。"
    assert saved["ok"] is True and cleared["ok"] is True
    assert keeper.edits == [("紅莉栖怕蟑螂。", "紅莉栖喜歡胡椒博士。"), ("", None)]
    # 舊檔案沒被碰，也沒被搬進引擎。
    assert old_file.read_text(encoding="utf-8") == "紅莉栖：舊檔案裡的。"


def test_turning_memory_off_also_stops_her_remembering_herself():
    from src.open_llm_vtuber.agent.agent_factory import _engine_settings

    assert _engine_settings({"goal_every": 4}, long_term_memory=False) == {
        "goal_every": 4,
        "memory_every": 0,
        "memories_recalled": 0,
        "self_memory_every": 0,
        "self_memories_shown": 0,
    }


class _Companion:
    """引擎那一側：上限 2 條，多的丟掉最舊的。"""

    def __init__(self):
        self.lines = ["紅莉栖喜歡胡椒博士。"]

    def self_memories(self):
        return list(self.lines)

    def rewrite_self_memories(self, summaries, *, edited_from=None):
        self.lines = list(summaries)[-2:]


def test_without_a_connection_the_page_reaches_her_running_engine(
    tmp_path, monkeypatch
):
    from src.open_llm_vtuber.character_engine import factory

    engine = _Companion()
    monkeypatch.setattr(factory, "current_companion", lambda key: engine)
    client = _page(monkeypatch, tmp_path, {})

    saved = client.post(
        "/api/memory/self",
        json={"conf_uid": "kurisu", "content": "一。\n二。\n三。"},
    ).json()

    assert memory_route._self_keeper({}, "kurisu").self_memory() == "二。\n三。"
    # 引擎留下多少，頁面就顯示多少：不然下次存檔，被擠掉的又會被當成新的加回去。
    assert saved["content"] == "二。\n三。"
