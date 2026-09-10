import os
import sys
import time
import atexit
import shutil
import socket
import asyncio
import argparse
import threading
import subprocess
import webbrowser
from pathlib import Path
import tomli
import uvicorn
from loguru import logger
from upgrade_codes.upgrade_manager import UpgradeManager

from src.open_llm_vtuber.server import WebSocketServer
from src.open_llm_vtuber.config_manager import Config, read_yaml, validate_config

os.environ["HF_HOME"] = str(Path(__file__).parent / "models")
os.environ["MODELSCOPE_CACHE"] = str(Path(__file__).parent / "models")

upgrade_manager = UpgradeManager()


def get_version() -> str:
    with open("pyproject.toml", "rb") as f:
        pyproject = tomli.load(f)
    return pyproject["project"]["version"]


def init_logger(console_log_level: str = "INFO") -> None:
    logger.remove()
    # Console output
    logger.add(
        sys.stderr,
        level=console_log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | {message}",
        colorize=True,
    )

    # File output
    logger.add(
        "logs/debug_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {extra}",
        backtrace=True,
        diagnose=True,
    )


def check_frontend_submodule(lang=None):
    """
    Check if the frontend submodule is initialized. If not, attempt to initialize it.
    If initialization fails, log an error message.
    """
    if lang is None:
        lang = upgrade_manager.lang

    frontend_path = Path(__file__).parent / "frontend" / "index.html"
    if not frontend_path.exists():
        if lang == "zh":
            logger.warning("未找到前端子模块，正在尝试初始化子模块...")
        else:
            logger.warning(
                "Frontend submodule not found, attempting to initialize submodules..."
            )

        try:
            subprocess.run(
                ["git", "submodule", "update", "--init", "--recursive"], check=True
            )
            if frontend_path.exists():
                if lang == "zh":
                    logger.info("👍 前端子模块（和其他子模块）初始化成功。")
                else:
                    logger.info(
                        "👍 Frontend submodule (and other submodules) initialized successfully."
                    )
            else:
                if lang == "zh":
                    logger.critical(
                        '子模块初始化失败。\n你之后可能会在浏览器中看到 {{"detail":"Not Found"}} 的错误提示。请检查我们的快速入门指南和常见问题页面以获取更多信息。'
                    )
                    logger.error(
                        "初始化子模块后，前端文件仍然缺失。\n"
                        + "你是否手动更改或删除了 `frontend` 文件夹？\n"
                        + "它是一个 Git 子模块 - 你不应该直接修改它。\n"
                        + "如果你这样做了，请使用 `git restore frontend` 丢弃你的更改，然后再试一次。\n"
                    )
                else:
                    logger.critical(
                        'Failed to initialize submodules. \nYou might see {{"detail":"Not Found"}} in your browser. Please check our quick start guide and common issues page from our documentation.'
                    )
                    logger.error(
                        "Frontend files are still missing after submodule initialization.\n"
                        + "Did you manually change or delete the `frontend` folder?  \n"
                        + "It's a Git submodule — you shouldn't modify it directly.  \n"
                        + "If you did, discard your changes with `git restore frontend`, then try again.\n"
                    )
        except Exception as e:
            if lang == "zh":
                logger.critical(
                    f'初始化子模块失败: {e}。\n怀疑你跟 GitHub 之间有网络问题。你之后可能会在浏览器中看到 {{"detail":"Not Found"}} 的错误提示。请检查我们的快速入门指南和常见问题页面以获取更多信息。\n'
                )
            else:
                logger.critical(
                    f'Failed to initialize submodules: {e}. \nYou might see {{"detail":"Not Found"}} in your browser. Please check our quick start guide and common issues page from our documentation.\n'
                )


def parse_args():
    parser = argparse.ArgumentParser(description="Open-LLM-VTuber Server")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--hf_mirror", action="store_true", help="Use Hugging Face mirror"
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the app in the default browser once the server is actually ready",
    )
    return parser.parse_args()


def _open_browser_when_ready(host: str, port: int, timeout: float = 600.0) -> None:
    """Open the default browser ONLY after the server is accepting connections.

    The launcher used to open the browser on a fixed short delay, but first-run
    startup (downloading the speech model + loading the avatar) can take much
    longer, so the browser hit the port before uvicorn was listening and the user
    saw 'connection refused'. Poll the port and open exactly when it is ready."""
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "", "::", "::1") else host
    url = f"http://localhost:{port}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((connect_host, port), timeout=1.0):
                pass
        except OSError:
            time.sleep(0.5)
            continue
        # The port is accepting connections — the app is up. Open the browser once.
        try:
            webbrowser.open(url)
            logger.info(f"Opened {url} in your browser.")
        except Exception as e:
            logger.warning(
                f"Could not auto-open the browser ({type(e).__name__}: {e}). "
                f"Open {url} manually."
            )
        return
    logger.warning(
        "Server did not become ready in time; the browser was not auto-opened."
    )


@logger.catch
def run(console_log_level: str, open_browser: bool = False):
    init_logger(console_log_level)
    logger.info(f"Open-LLM-VTuber, version v{get_version()}")

    # Get selected language
    lang = upgrade_manager.lang

    # Check if the frontend submodule is initialized
    check_frontend_submodule(lang)

    # First run: if conf.yaml is missing (e.g. a fresh download where conf.yaml is
    # not shipped), create it from the bundled default template so every entry
    # point works — the double-click launcher AND a plain `uv run run_server.py`.
    #
    # 必須在 sync_user_config() 之前。它發現 conf.yaml 不存在時，會依系統語言複製
    # 上游的 conf.default.yaml／conf.ZH.default.yaml，這裡的 Tomoshibi 預設就永遠
    # 輪不到——英文系統因此拿到 use_mcpp: True，又沒有 mcp_servers.json，開機直接
    # 失敗（CI 在 macOS 與 Windows 上都重現了）。雙擊啟動器沒事，是因為啟動器自己
    # 先複製了範本。
    if not os.path.exists("conf.yaml"):
        _template = "config_templates/conf.tomoshibi.default.yaml"
        if os.path.exists(_template):
            shutil.copy(_template, "conf.yaml")
            logger.info(
                "conf.yaml not found — created it from "
                "config_templates/conf.tomoshibi.default.yaml (first run)."
            )
        else:
            logger.warning("conf.yaml not found and no default template available.")

    # Sync user config with default config
    try:
        upgrade_manager.sync_user_config()
    except Exception as e:
        logger.error(f"Error syncing user config: {e}")

    atexit.register(WebSocketServer.clean_cache)

    # model_dict.json 也是同一個模式（不進版控，首次執行從 config_templates 複製）。
    # 原本只有角色相關的 API 在讀取時才會補，但開機時 AvatarModel 就直接讀它了——
    # 全新的 clone 或桌面版的全新工作目錄因此在啟動時就找不到檔案。
    from src.open_llm_vtuber.character_route import _ensure_model_dict

    _ensure_model_dict()

    # mcp_servers.json 也不進版控（使用者會加自己的伺服器，可能帶金鑰）。開啟 MCP 時
    # ServerRegistry 找不到它會讓整個後端初始化失敗，所以一樣從範本補。
    _mcp_template = "config_templates/mcp_servers.default.json"
    if not os.path.exists("mcp_servers.json") and os.path.exists(_mcp_template):
        shutil.copy(_mcp_template, "mcp_servers.json")
        logger.info(f"mcp_servers.json not found — created it from {_mcp_template}.")

    # Load configurations from yaml file
    config: Config = validate_config(read_yaml("conf.yaml"))
    server_config = config.system_config

    # 記憶改成每段對話一份之後,舊的角色層 core_memory.md 不會再被讀到。
    # 只跑一次,搬完原檔改名保留。失敗不擋開機。
    try:
        from src.open_llm_vtuber.memory_migration import migrate_character_memories

        _moved = migrate_character_memories()
        if _moved:
            logger.info(f"Migrated core memory for: {', '.join(_moved)}")
    except Exception as e:
        logger.warning(f"Memory migration skipped ({type(e).__name__}: {e})")

    if server_config.enable_proxy:
        logger.info("Proxy mode enabled - /proxy-ws endpoint will be available")

    # Initialize the WebSocket server (synchronous part)
    server = WebSocketServer(config=config)

    # Perform asynchronous initialization (loading context, etc.)
    logger.info("Initializing server context...")
    try:
        asyncio.run(server.initialize())
        logger.info("Server context initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize server context: {e}")
        sys.exit(1)  # Exit if initialization fails

    # Open the browser only once the server is actually listening (opt-in; the
    # double-click launcher passes --open-browser). The thread polls the port and
    # opens exactly when ready, so a slow first-run startup never shows a
    # 'connection refused' page.
    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(server_config.host, server_config.port),
            daemon=True,
        ).start()

    # Run the Uvicorn server
    logger.info(f"Starting server on {server_config.host}:{server_config.port}")
    uvicorn.run(
        app=server.app,
        host=server_config.host,
        port=server_config.port,
        log_level=console_log_level.lower(),
    )


if __name__ == "__main__":
    args = parse_args()
    console_log_level = "DEBUG" if args.verbose else "INFO"
    if args.verbose:
        logger.info("Running in verbose mode")
    else:
        logger.info(
            "Running in standard mode. For detailed debug logs, use: uv run run_server.py --verbose"
        )
    if args.hf_mirror:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    run(console_log_level=console_log_level, open_browser=args.open_browser)
