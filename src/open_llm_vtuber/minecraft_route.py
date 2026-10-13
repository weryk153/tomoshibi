"""Minecraft 模式的 REST：狀態、開始、停止、設定。寫入只收信任的來源（api_guard）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .api_guard import forbidden, is_trusted_request
from .minecraft.controller import MinecraftError
from .minecraft.settings import read_minecraft_settings, write_minecraft_settings
from .stream_route import _json_object


def _is_trusted(request) -> bool:
    return is_trusted_request(request)


def init_minecraft_route(controller: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/minecraft")
    async def get_minecraft():
        return {
            "settings": read_minecraft_settings().model_dump(),
            "status": controller.status(),
        }

    @router.post("/api/minecraft/settings")
    async def save_settings(request: Request):
        if not _is_trusted(request):
            return forbidden()
        body = await _json_object(request)
        if body is None:
            return JSONResponse({"error": "expected an object"}, status_code=400)
        try:
            settings = write_minecraft_settings(body)
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=400)
        controller.apply_settings(settings)
        return {"settings": settings.model_dump()}

    @router.post("/api/minecraft/start")
    async def start(request: Request):
        if not _is_trusted(request):
            return forbidden()
        try:
            return await controller.start()
        except MinecraftError as error:
            return JSONResponse(
                {"error": error.reason, "status": controller.status()}, status_code=409
            )

    @router.post("/api/minecraft/stop")
    async def stop(request: Request):
        if not _is_trusted(request):
            return forbidden()
        return await controller.stop()

    return router
