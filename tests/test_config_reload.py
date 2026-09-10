"""存好設定後不用重啟就生效。

設定精靈與 LLM 設定頁存檔後，前端送 reload-config。原本只能叫使用者「關掉終端機、
重新執行 start-companion」——桌面版使用者沒有終端機可關，一鍵安裝完還得重啟也
不算一鍵。
"""

import asyncio
import json
from types import SimpleNamespace

from src.open_llm_vtuber.service_context import ServiceContext
from src.open_llm_vtuber.websocket_handler import MessageType, WebSocketHandler


class _Socket:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def _context(active_file: str, loaded: list[str], fail: bool = False) -> ServiceContext:
    ctx = ServiceContext.__new__(ServiceContext)
    ctx.active_config_file = active_file

    async def load(file_name):
        if fail:
            raise ValueError("broken conf")
        loaded.append(file_name)

    ctx.load_character_config = load
    ctx.live2d_model = SimpleNamespace(model_info={"name": "mao_pro"})
    ctx.character_config = SimpleNamespace(conf_name="Mao", conf_uid="mao")
    return ctx


def test_reload_uses_the_active_character_and_does_not_announce_a_switch():
    loaded: list[str] = []
    ctx = _context("alice.yaml", loaded)
    ws = _Socket()

    asyncio.run(ctx.handle_config_reload(ws))

    assert loaded == ["alice.yaml"], "重載的是目前的角色，不是換回 conf.yaml"
    assert [m["type"] for m in ws.sent] == ["set-model-and-conf", "config-reloaded"]
    assert "config-switched" not in [m["type"] for m in ws.sent], (
        "config-switched 會讓前端跳「角色已切換」並開新對話"
    )


def test_reload_failure_reports_an_error_without_raising():
    ctx = _context("conf.yaml", [], fail=True)
    ws = _Socket()

    asyncio.run(ctx.handle_config_reload(ws))  # 不能丟例外，連線要留著

    assert ws.sent[-1]["type"] == "error"
    assert "broken conf" in ws.sent[-1]["message"]


def test_handler_also_reloads_the_shared_context_for_new_connections():
    shared_loaded: list[str] = []
    session_loaded: list[str] = []
    handler = WebSocketHandler.__new__(WebSocketHandler)
    handler.default_context_cache = _context("conf.yaml", shared_loaded)
    handler.client_contexts = {"c1": _context("alice.yaml", session_loaded)}

    asyncio.run(
        handler._handle_config_reload(_Socket(), "c1", {"type": "reload-config"})
    )

    assert shared_loaded == ["conf.yaml"], (
        "新連線從共用 context 複製，不重載它的話重新整理就退回舊設定"
    )
    assert session_loaded == ["alice.yaml"]


def test_reload_config_is_a_registered_message():
    assert "reload-config" in MessageType.CONFIG.value
