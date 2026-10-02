"""直播分頁的 REST：讀設定與狀態、存設定、開始、停止。

存取控制跟其他設定一樣走 api_guard：讀可以，改要是信任的來源。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from .api_guard import forbidden, is_trusted_request
from .stream.controller import StreamError
from .stream.settings import read_stream_settings, write_stream_settings


def _is_trusted(request: Request) -> bool:
    return is_trusted_request(request)


async def _json_object(request: Request) -> dict[str, Any] | None:
    """沒有 body 當成空物件；body 不是物件回 None。"""
    try:
        body = await request.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else None


def init_stream_route(controller: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/stream")
    async def get_stream():
        return {
            "settings": read_stream_settings().model_dump(),
            "status": controller.status(),
        }

    @router.post("/api/stream/settings")
    async def save_settings(request: Request):
        if not _is_trusted(request):
            return forbidden()
        body = await _json_object(request)
        if body is None:
            return JSONResponse(
                status_code=400, content={"error": "expected an object"}
            )
        try:
            settings = write_stream_settings(body)
        except ValueError as error:
            return JSONResponse(status_code=400, content={"error": str(error)})
        return {"settings": settings.model_dump()}

    @router.post("/api/stream/start")
    async def start(request: Request):
        if not _is_trusted(request):
            return forbidden()
        body = await _json_object(request) or {}
        url = body.get("url")
        try:
            return await controller.start(url if isinstance(url, str) else None)
        except StreamError as error:
            return JSONResponse(
                status_code=409,
                content={"error": error.reason, "status": controller.status()},
            )

    @router.post("/api/stream/stop")
    async def stop(request: Request):
        if not _is_trusted(request):
            return forbidden()
        return await controller.stop()

    return router
