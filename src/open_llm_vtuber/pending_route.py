"""GET /api/pending-changes：還沒生效的設定變更（見 pending_changes）。"""

from fastapi import APIRouter

from . import pending_changes


def init_pending_route() -> APIRouter:
    router = APIRouter()

    @router.get("/api/pending-changes")
    async def get_pending():
        return {
            "pending": pending_changes.pending(),
            "needs_restart": pending_changes.needs_restart(),
        }

    return router
