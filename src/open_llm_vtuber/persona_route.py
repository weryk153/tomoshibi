"""Local REST CRUD API for character-independent persona presets."""

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from .api_guard import forbidden as _forbidden, is_trusted_request as _is_local_request
from .persona_store import (
    create_persona,
    delete_persona,
    get_active_persona_id,
    is_persona_active,
    list_personas,
    update_persona,
)


def _bad_request(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "error": message},
    )


def init_persona_route() -> APIRouter:
    router = APIRouter()

    @router.get("/api/personas")
    async def get_personas(request: Request, conf_uid: str = ""):
        if not _is_local_request(request):
            return _forbidden()
        return JSONResponse(
            {
                "personas": list_personas(),
                "active_persona_id": get_active_persona_id(conf_uid),
            }
        )

    @router.post("/api/personas")
    async def add_persona(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            body = await request.json()
            item = create_persona(
                body.get("name"),
                body.get("prompt"),
                body.get("id"),
            )
        except ValueError as exc:
            return _bad_request(str(exc))
        except Exception:
            return _bad_request("Could not create persona.", 500)
        return JSONResponse({"ok": True, "persona": item}, status_code=201)

    @router.put("/api/personas/{persona_id}")
    async def edit_persona(persona_id: str, request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            body = await request.json()
            item = update_persona(persona_id, body.get("name"), body.get("prompt"))
        except KeyError:
            return _bad_request("Persona not found.", 404)
        except ValueError as exc:
            return _bad_request(str(exc))
        except Exception:
            return _bad_request("Could not update persona.", 500)
        return JSONResponse({"ok": True, "persona": item})

    @router.delete("/api/personas/{persona_id}")
    async def remove_persona(persona_id: str, request: Request):
        if not _is_local_request(request):
            return _forbidden()
        if is_persona_active(persona_id):
            return _bad_request(
                "Switch every character using this persona back to its default before deleting it.",
                409,
            )
        if not delete_persona(persona_id):
            return _bad_request("Persona not found.", 404)
        return JSONResponse({"ok": True})

    return router
