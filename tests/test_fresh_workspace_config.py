"""全新工作目錄第一次開機，要拿到 Tomoshibi 自己的預設設定。

run_server 原本先呼叫上游的 sync_user_config()，才檢查 conf.yaml 要不要從
conf.tomoshibi.default.yaml 建。前者發現沒有 conf.yaml 時會依系統語言複製上游的
conf.default.yaml 或 conf.ZH.default.yaml，於是 Tomoshibi 的預設永遠輪不到。
英文系統拿到的上游範本 use_mcpp: True，而 mcp_servers.json 不進版控、也沒人補，
ServerRegistry 初始化失敗，整個後端結束——CI 的打包實測在 macOS 與 Windows
上都撞到。中文系統拿到的範本 use_mcpp: False，所以開發機上看不出來。
"""

import inspect
import json
from pathlib import Path

import yaml

import run_server

ROOT = Path(__file__).resolve().parent.parent


def test_tomoshibi_template_is_seeded_before_upstream_sync():
    src = inspect.getsource(run_server.run)
    seed = src.find('"config_templates/conf.tomoshibi.default.yaml"')
    sync = src.find("upgrade_manager.sync_user_config()")
    assert seed != -1 and sync != -1
    assert seed < sync, (
        "要先放 Tomoshibi 的預設；sync_user_config 先跑的話會依系統語言複製上游範本"
    )


def test_mcp_servers_is_seeded_before_the_server_is_built():
    src = inspect.getsource(run_server.run)
    seed = src.find('"config_templates/mcp_servers.default.json"')
    build = src.find("WebSocketServer(config=config)")
    assert seed != -1, "run_server 開機時沒有補 mcp_servers.json"
    assert seed < build


def test_default_mcp_servers_cover_what_the_templates_enable():
    """範本預設啟用的 MCP 伺服器，預設的 mcp_servers.json 裡都要有。"""
    servers = json.loads(
        (ROOT / "config_templates/mcp_servers.default.json").read_text(encoding="utf-8")
    )["mcp_servers"]
    for name in (
        "conf.tomoshibi.default.yaml",
        "conf.default.yaml",
        "conf.ZH.default.yaml",
    ):
        conf = yaml.safe_load(
            (ROOT / "config_templates" / name).read_text(encoding="utf-8")
        )
        agent = conf["character_config"]["agent_config"]["agent_settings"]
        enabled = agent["basic_memory_agent"]["mcp_enabled_servers"]
        missing = set(enabled) - set(servers)
        assert not missing, f"{name} 啟用了 {missing}，但預設的 mcp_servers.json 沒有"
