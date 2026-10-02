"""擋掉別的網站趁你開著 app 送來的請求（跨站請求偽造、跨站 WebSocket）。

CORS 開著，而本機來源一律可信（api_guard），所以任何網頁都能對
127.0.0.1:12393 送 POST——瀏覽器會照送，只是讀不到回應——例如把「允許區網連線」
打開；也能直接連 /client-ws 跟她講話、換角色。瀏覽器送這類請求一定帶 Origin，
這裡看 Origin 決定放不放行（規則見 api_guard.origin_allowed）。

讀取（GET）不擋：讀取靠 CORS，這裡管的是會改東西的請求與 WebSocket。
"""

from fastapi import FastAPI, Request, WebSocket
from starlette.responses import JSONResponse

from .api_guard import is_tailscale_request, origin_allowed

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _allowed(conn) -> bool:
    return origin_allowed(
        conn.headers.get("origin"),
        conn.headers.get("host"),
        is_tailscale_request(conn),
    )


def install_origin_guard(app: FastAPI) -> None:
    @app.middleware("http")
    async def refuse_cross_site_writes(request: Request, call_next):
        if request.method not in _SAFE_METHODS and not _allowed(request):
            return JSONResponse(status_code=403, content={"error": "forbidden origin"})
        return await call_next(request)


async def websocket_origin_ok(websocket: WebSocket) -> bool:
    """WebSocket 握手時檢查來源；不放行就關掉（1008 = policy violation）。"""
    if _allowed(websocket):
        return True
    await websocket.close(code=1008)
    return False
