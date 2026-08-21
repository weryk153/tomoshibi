"""
Open-LLM-VTuber Server
========================
This module contains the WebSocket server for Open-LLM-VTuber, which handles
the WebSocket connections, serves static files, and manages the web tool.
It uses FastAPI for the server and Starlette for static file serving.
"""

import os
import shutil

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles as StarletteStaticFiles

from .routes import init_client_ws_route, init_webtool_routes, init_proxy_route
from .llm_config_route import init_llm_config_route
from .character_route import init_character_route
from .live2d_config_route import init_live2d_config_route
from .persona_route import init_persona_route
from .translator_route import init_translator_route
from .player_route import init_player_route
from .network_route import init_network_route
from .voice_route import init_voice_route
from .memory_route import init_memory_route
from .perf_route import init_perf_route
from .topics_route import (
    init_topics_route,
    start_news_refresh_task,
    stop_news_refresh_task,
)
from .service_context import ServiceContext
from .config_manager.utils import Config
from .active_character_store import (
    get_active_character_filename,
    set_active_character_filename,
)
from loguru import logger


# Create a custom StaticFiles class that adds CORS headers
class CORSStaticFiles(StarletteStaticFiles):
    """
    Static files handler that adds CORS headers to all responses.
    Needed because Starlette StaticFiles might bypass standard middleware.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)

        # Add CORS headers to all responses
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

        if path.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript"

        # HTML 不快取：不然改了東西之後，瀏覽器會拿舊的頁面配新的資源檔（尤其
        # for remote devices). Decided by content-type because a request for "/" has an empty
        # path (StaticFiles serves index.html internally). Hash-named .js/.css can still cache long.
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"

        return response


class AvatarStaticFiles(CORSStaticFiles):
    """
    Avatar files handler with security restrictions and CORS headers
    """

    async def get_response(self, path: str, scope):
        allowed_extensions = (".jpg", ".jpeg", ".png", ".gif", ".svg")
        if not any(path.lower().endswith(ext) for ext in allowed_extensions):
            return Response("Forbidden file type", status_code=403)
        response = await super().get_response(path, scope)
        return response


class WebSocketServer:
    """
    API server for Open-LLM-VTuber. This contains the websocket endpoint for the client, hosts the web tool, and serves static files.

    Creates and configures a FastAPI app, registers all routes
    (WebSocket, web tools, proxy) and mounts static assets with CORS.

    Args:
        config (Config): Application configuration containing system settings.
        default_context_cache (ServiceContext, optional):
            Pre‑initialized service context for sessions' service context to reference to.
            **If omitted, `initialize()` method needs to be called to load service context.**

    Notes:
        - If default_context_cache is omitted, call `await initialize()` to load service context cache.
        - Use `clean_cache()` to clear and recreate the local cache directory.
    """

    def __init__(self, config: Config, default_context_cache: ServiceContext = None):
        self.app = FastAPI(title="Open-LLM-VTuber Server")  # Added title for clarity
        self.config = config
        self.default_context_cache = (
            default_context_cache or ServiceContext()
        )  # Use provided context or initialize a new empty one waiting to be loaded
        # It will be populated during the initialize method call

        # Add global CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Include routes, passing the context instance
        # The context will be populated during the initialize step
        client_ws_router, ws_handler = init_client_ws_route(
            default_context_cache=self.default_context_cache
        )
        self.app.include_router(client_ws_router)
        self.app.include_router(
            init_webtool_routes(default_context_cache=self.default_context_cache),
        )

        # 設定類的 API。全部在靜態檔掛載之前註冊，/api/* 才會排在 "/" 那個
        # 萬用路由前面；順序反了的話每一個 API 都會回傳首頁的 HTML。
        #
        # 存取控制統一在 api_guard，各 route 不各自實作。
        self.app.include_router(init_llm_config_route())      # 首次設定精靈
        self.app.include_router(init_character_route())       # 角色管理
        self.app.include_router(init_persona_route())         # 人設預設
        self.app.include_router(init_translator_route())      # 翻譯
        self.app.include_router(init_player_route())          # 玩家層級設定
        self.app.include_router(init_network_route())         # 遠端存取
        self.app.include_router(init_voice_route())           # 語音清單與試聽
        self.app.include_router(init_memory_route())          # 長期記憶
        self.app.include_router(init_perf_route())            # 引擎與硬體
        self.app.include_router(init_topics_route())          # 主動話題

        # Live2D 的動作與點擊區設定。多帶兩個參數是為了「存檔後立刻生效」：
        # PUT 成功時可以就地更新每一個正在顯示這個模型的連線，不必重啟或切角色。
        self.app.include_router(
            init_live2d_config_route(self.default_context_cache, ws_handler.client_contexts)
        )

        # 開機時啟動新聞的定時更新，關機時取消。這取代了系統的 cron——使用者
        # 不必去設排程，開了新聞話題就會自己更新。
        @self.app.on_event("startup")
        async def _start_topics_refresh():  # noqa: D401
            try:
                start_news_refresh_task()
            except Exception as e:
                # 背景任務起不來也不可以害整個 server 開不起來。
                from loguru import logger as _logger

                _logger.warning(
                    f"could not start news-refresh task: {type(e).__name__}: {e}"
                )

        @self.app.on_event("shutdown")
        async def _stop_topics_refresh():  # noqa: D401
            try:
                await stop_news_refresh_task()
            except Exception:
                pass

        # Initialize and include proxy routes if proxy is enabled
        system_config = config.system_config
        if hasattr(system_config, "enable_proxy") and system_config.enable_proxy:
            # Construct the server URL for the proxy
            host = system_config.host
            port = system_config.port
            server_url = f"ws://{host}:{port}/client-ws"
            self.app.include_router(
                init_proxy_route(server_url=server_url),
            )

        # Mount cache directory first (to ensure audio file access)
        if not os.path.exists("cache"):
            os.makedirs("cache")
        self.app.mount(
            "/cache",
            CORSStaticFiles(directory="cache"),
            name="cache",
        )

        # Generated pictures must NOT live in cache/: run_server.py registers
        # clean_cache() with atexit, which rmtree's it on every shutdown, and
        # chat history keeps pointing at these files forever.
        if not os.path.exists("generated_images"):
            os.makedirs("generated_images")
        self.app.mount(
            "/generated-images",
            CORSStaticFiles(directory="generated_images"),
            name="generated_images",
        )

        # Ensure static dirs exist before mounting. Empty dirs (notably avatars/)
        # are not shipped in a fresh download/clone, and mounting a missing
        # directory raises at startup — which would crash every first launch.
        for _static_dir in ("live2d-models", "backgrounds", "avatars"):
            os.makedirs(_static_dir, exist_ok=True)

        # Mount static files with CORS-enabled handlers
        self.app.mount(
            "/live2d-models",
            CORSStaticFiles(directory="live2d-models"),
            name="live2d-models",
        )
        self.app.mount(
            "/bg",
            CORSStaticFiles(directory="backgrounds"),
            name="backgrounds",
        )
        self.app.mount(
            "/avatars",
            AvatarStaticFiles(directory="avatars"),
            name="avatars",
        )

        # Mount web tool directory separately from frontend
        self.app.mount(
            "/web-tool",
            CORSStaticFiles(directory="web_tool", html=True),
            name="web_tool",
        )

        # Mount main frontend last (as catch-all)
        self.app.mount(
            "/",
            CORSStaticFiles(directory="frontend", html=True),
            name="frontend",
        )

    async def initialize(self):
        """Asynchronously load the service context from config.
        Calling this function is needed if default_context_cache was not provided to the constructor."""
        await self.default_context_cache.load_from_config(self.config)
        active_file = get_active_character_filename()
        if active_file and active_file != "conf.yaml":
            try:
                await self.default_context_cache.load_character_config(active_file)
                logger.info(f"Restored active character: {active_file}")
            except Exception as e:
                logger.warning(
                    f"Could not restore active character '{active_file}' "
                    f"({type(e).__name__}: {e}); using conf.yaml"
                )
                await self.default_context_cache.load_character_config("conf.yaml")
                try:
                    set_active_character_filename("conf.yaml")
                except OSError as state_error:
                    logger.warning(
                        "Could not reset active-character state "
                        f"({type(state_error).__name__}: {state_error})"
                    )

    @staticmethod
    def clean_cache():
        """Clean the cache directory by removing and recreating it."""
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)
