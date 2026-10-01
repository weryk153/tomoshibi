"""主機這一側：agent 自己記得對方的時候，記憶頁與記憶整理怎麼配合。

不需要引擎。character_engine_agent 那一側在 test_engine_replaces_core_memory.py。
"""

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
    ).read_text(encoding="utf-8")
    api = Path("frontend-src/src/renderer/src/api/memory.ts").read_text(
        encoding="utf-8"
    )
    assert (
        "saveMemoryContent(\n      baseUrl, confUid, contentDraft, memory?.content,\n    )"
        in page
    )
    assert "edited_from: editedFrom" in api
    # 她自己的記憶也是：引擎記的那一份同樣只刪頁面上有、存回來不見的行。
    assert (
        "saveSelfMemoryContent(\n      baseUrl, confUid, selfDraft, memory?.self_content,\n    )"
        in page
    )
    assert api.count("edited_from: editedFrom") == 2


def test_an_agent_that_keeps_her_own_memory_gets_no_consolidation():
    """引擎記得對方、也記得她自己說過什麼：主機那一套整理（一次模型呼叫，跟她的
    回覆搶同一顆本機模型）整個不用做。"""
    import inspect

    from src.open_llm_vtuber.conversations import single_conversation

    src = inspect.getsource(single_conversation.process_single_conversation)

    assert 'not hasattr(context.agent_engine, "self_memory")' in src


def test_the_agents_memory_is_not_held_up_by_the_hosts_consolidation():
    """實機：整理「她自己的記憶」跑到一半（最長 60 秒）時按下清除，記憶頁回 503
    「記憶正在整理中」。整理碰的是 self_memory.md，跟引擎的記憶無關，不用等它。"""
    assert memory_route._needs_consolidation_lock(keeper=object()) is False
    assert memory_route._needs_consolidation_lock(keeper=None) is True


def test_the_memory_page_is_told_when_the_engine_keeps_the_memory(
    tmp_path, monkeypatch
):
    """引擎的記憶不按字數限制。頁面要知道，不然會顯示一個不起作用的上限。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(memory_route, "_is_local_request", lambda request: True)
    monkeypatch.setattr(memory_route, "_resolve_conf_uid", lambda value: (value, None))
    keeper = SimpleNamespace(
        conversation_memory=lambda history_uid: "對方：名字是晨星。",
        rewrite_conversation_memory=lambda history_uid, text, **_: None,
    )
    contexts = {"engine": _context("kurisu", "h1", keeper)}
    app = FastAPI()
    app.include_router(memory_route.init_memory_route(contexts))
    client = TestClient(app)

    engine = client.get("/api/memory", params={"conf_uid": "kurisu"}).json()
    contexts["engine"] = _context("kurisu", "h1", SimpleNamespace())
    basic = client.get("/api/memory", params={"conf_uid": "kurisu"}).json()

    assert engine["engine_managed"] is True
    assert basic["engine_managed"] is False


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
    memory_core.save_self_memory("kurisu", "紅莉栖：舊檔案裡的。")

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
    assert shown["self_engine_managed"] is True
    assert saved["ok"] is True and cleared["ok"] is True
    assert keeper.edits == [("紅莉栖怕蟑螂。", "紅莉栖喜歡胡椒博士。"), ("", None)]
    # 主機那一份沒被碰：它只在第一次搬進引擎。
    assert memory_core.load_self_memory("kurisu") == "紅莉栖：舊檔案裡的。"


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
    monkeypatch.setattr(memory_route, "_configured_for_the_engine", lambda uid: True)
    client = _page(monkeypatch, tmp_path, {})

    saved = client.post(
        "/api/memory/self",
        json={"conf_uid": "kurisu", "content": "一。\n二。\n三。"},
    ).json()

    assert memory_route._self_keeper({}, "kurisu").self_memory() == "二。\n三。"
    # 引擎留下多少，頁面就顯示多少：不然下次存檔，被擠掉的又會被當成新的加回去。
    assert saved["content"] == "二。\n三。"


def test_an_edit_that_no_one_would_read_is_refused(tmp_path, monkeypatch):
    """引擎接手過她自己的記憶、現在卻沒在跑：寫進 self_memory.md 的東西不會再
    被讀，不能讓頁面說「已儲存」。"""
    from src.open_llm_vtuber.character_engine import factory

    monkeypatch.setattr(factory, "current_companion", lambda key: None)
    monkeypatch.setattr(memory_route, "_configured_for_the_engine", lambda uid: True)
    client = _page(monkeypatch, tmp_path, {})
    marker = tmp_path / "chat_history" / "kurisu" / "engine" / "brought-self-memory.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text("brought\n", encoding="utf-8")
    memory_core.save_self_memory("kurisu", "紅莉栖：舊的。")

    saved = client.post(
        "/api/memory/self", json={"conf_uid": "kurisu", "content": "新的。"}
    )
    cleared = client.post("/api/memory/self/clear", json={"conf_uid": "kurisu"})

    assert saved.status_code == 409 and cleared.status_code == 409
    assert memory_core.load_self_memory("kurisu") == "紅莉栖：舊的。"


def test_back_on_the_basic_agent_the_page_edits_the_file_she_reads(
    tmp_path, monkeypatch
):
    """試過引擎、又換回 basic_memory_agent：上次啟動的引擎還在記憶體裡、搬過的
    記號也還在，但她說話讀的是 self_memory.md。頁面要改的是那一份，不能 409。"""
    from src.open_llm_vtuber.character_engine import factory

    monkeypatch.setattr(factory, "current_companion", lambda key: _Companion())
    marker = tmp_path / "chat_history" / "kurisu" / "engine" / "brought-self-memory.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text("brought\n", encoding="utf-8")
    with_connection = _page(
        monkeypatch, tmp_path, {"basic": _context("kurisu", "h1", SimpleNamespace())}
    )
    saved = with_connection.post(
        "/api/memory/self",
        json={"conf_uid": "kurisu", "content": "紅莉栖：連線中改的。"},
    )
    assert saved.status_code == 200
    assert memory_core.load_self_memory("kurisu") == "紅莉栖：連線中改的。"

    monkeypatch.setattr(memory_route, "_configured_for_the_engine", lambda uid: False)
    no_connection = _page(monkeypatch, tmp_path, {})
    saved = no_connection.post(
        "/api/memory/self",
        json={"conf_uid": "kurisu", "content": "紅莉栖：重開之後改的。"},
    )
    assert saved.status_code == 200
    assert memory_core.load_self_memory("kurisu") == "紅莉栖：重開之後改的。"


def test_which_agent_a_character_is_set_to_comes_from_its_file_or_the_base(
    tmp_path, monkeypatch
):
    from src.open_llm_vtuber import character_route

    def conf(uid, choice=None):
        agent = (
            f"  agent_config:\n    conversation_agent_choice: '{choice}'\n"
            if choice
            else ""
        )
        return f"character_config:\n  conf_uid: '{uid}'\n{agent}"

    base = tmp_path / "conf.yaml"
    base.write_text(conf("mao", "character_engine_agent"), encoding="utf-8")
    characters = tmp_path / "characters"
    characters.mkdir()
    (characters / "kurisu.yaml").write_text(
        conf("kurisu", "basic_memory_agent"), encoding="utf-8"
    )
    (characters / "frieren.yaml").write_text(conf("frieren"), encoding="utf-8")
    # read_yaml 只讀工作目錄底下的檔案，跟正式執行一樣用相對路徑。
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(memory_route, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_route, "CHARACTERS_DIR", "characters")

    assert memory_route._configured_for_the_engine("mao") is True
    assert memory_route._configured_for_the_engine("kurisu") is False
    assert memory_route._configured_for_the_engine("frieren") is True
