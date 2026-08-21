from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.server import WebSocketServer


class _FakeContext:
    def __init__(self, fail_restore: bool = False):
        self.loaded = []
        self.fail_restore = fail_restore

    async def load_from_config(self, config):
        self.loaded.append(("base", config))

    async def load_character_config(self, filename):
        self.loaded.append(("character", filename))
        if self.fail_restore and filename != "conf.yaml":
            raise ValueError("missing character")


def _server(context: _FakeContext) -> WebSocketServer:
    server = WebSocketServer.__new__(WebSocketServer)
    server.config = SimpleNamespace()
    server.default_context_cache = context
    return server


def test_server_startup_restores_the_last_character(monkeypatch):
    context = _FakeContext()
    server = _server(context)
    monkeypatch.setattr(
        "src.open_llm_vtuber.server.get_active_character_filename",
        lambda: "kurisu.yaml",
    )

    asyncio.run(server.initialize())

    assert context.loaded == [
        ("base", server.config),
        ("character", "kurisu.yaml"),
    ]


def test_missing_saved_character_falls_back_to_base(monkeypatch):
    context = _FakeContext(fail_restore=True)
    saved = []
    monkeypatch.setattr(
        "src.open_llm_vtuber.server.get_active_character_filename",
        lambda: "deleted.yaml",
    )
    monkeypatch.setattr(
        "src.open_llm_vtuber.server.set_active_character_filename", saved.append
    )

    asyncio.run(_server(context).initialize())

    assert context.loaded[-2:] == [
        ("character", "deleted.yaml"),
        ("character", "conf.yaml"),
    ]
    assert saved == ["conf.yaml"]
