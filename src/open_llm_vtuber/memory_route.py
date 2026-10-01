"""長期記憶的設定頁後端：看、改、清空她記得的事。

她記得什麼全在 AI Character Engine 裡：每段對話各一份（她對你的記憶），加上整個
角色一份（她自己說過的事）。這裡只是把引擎那一份拿給頁面讀寫，經過這個角色的
character_engine_agent，或沒有連線時她還在跑的引擎；兩者都沒有就拒絕寫入，不寫到
任何不會被讀的地方。

conf_uid 前端知道（從 WebSocket 的 set-model-and-conf 來），沒帶就退回 conf.yaml
裡的基礎角色；history_uid 前端不知道——它活在每個連線各自的 ServiceContext 裡，
要從 client_contexts 找當前那段對話。找不到就回 409，不猜一個：猜錯會編輯到
別段對話的記憶。

安全上有兩道，兩道都不能省：

- 只接受本機請求（連同代理標頭的檢查）。
- conf_uid 在被拿去找任何東西之前，先擋掉路徑符號、再比對已知角色的集合。

長期記憶開關存在 conf.yaml 的 character_config 底下，寫入走 conf_editor 的就地改寫。
"""

import os
import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from loguru import logger

from . import character_settings

from .api_guard import (
    is_trusted_request as _is_local_request,
    forbidden as _forbidden,
)

from .conf_editor import (
    CONF_PATH,
)

from .character_route import _existing_conf_uids
from .config_manager.utils import read_yaml


# --------------------------------------------------------------------------- #
# Read helpers
# --------------------------------------------------------------------------- #


def _character_setting(key: str, default: Any, coerce=None) -> Any:
    """讀 character_config 底下的一個設定，讀不到就回程式端的預設值。

    四個設定原本各自寫一遍同樣的 try／read／dig／default，四份都要記得 fail-soft。
    收成一個之後，「conf.yaml 有問題不可以讓設定頁打不開」這條保證只需要對一次。

    ``coerce`` 用來把讀到的值夾進合法範圍——UI 顯示的數字永遠要在範圍內，就算
    有人手動把 conf.yaml 改成離譜的值。
    """
    try:
        data = read_yaml(CONF_PATH) or {}
        value = data.get("character_config", {}).get(key)
    except Exception:
        return default
    if value is None:
        return default
    return coerce(value) if coerce else value


def _base_conf_uid() -> Optional[str]:
    """conf.yaml 裡基礎角色的 conf_uid（沒指定角色時的退路）。"""
    uid = _character_setting("conf_uid", None)
    return str(uid) if uid else None


def _memory_enabled_for(conf_uid: str) -> bool:
    """這個角色的長期記憶開著沒有：她自己的檔案為準，沒寫就照底稿，再沒有就開著。"""
    filename = character_settings.filename_for_uid(conf_uid)
    if filename is None:
        return True
    return bool(character_settings.effective(filename)["long_term_memory_enabled"])


def _resolve_conf_uid(supplied: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """驗證前端送來的 conf_uid，沒帶就退回基礎角色。.

    Returns ``(conf_uid, error)``. ``error`` is non-None when the supplied uid is
    unknown (rejected to prevent arbitrary-path access). A falsy ``supplied`` falls
    back to the base conf_uid without error.
    """
    if supplied is not None and str(supplied).strip():
        uid = str(supplied).strip()
        # 路徑符號在比對已知集合「之前」就擋掉——這是安全防線的第一道。
        if os.sep in uid or "/" in uid or "\\" in uid or ".." in uid:
            return None, "Invalid conf_uid."
        known = _existing_conf_uids()
        if uid not in known:
            return None, "Unknown conf_uid."
        return uid, None
    # 沒指定就用底稿的角色。
    base = _base_conf_uid()
    if not base:
        return None, "No conf_uid available."
    return base, None


def _resolve_history_uid(client_contexts: dict, conf_uid: str):
    """當前連線正在用的那段對話。取不到回 None。

    記憶現在屬於一段對話，而設定頁本身不知道是哪一段——它只知道角色。這個值
    活在每個連線各自的 ServiceContext 裡，所以要從連線取。

    dict 保有插入順序，最後一個就是最近連上的那一個；那正是使用者面前的視窗。
    """
    found = None
    for ctx in client_contexts.values():
        cfg = getattr(ctx, "character_config", None)
        if getattr(cfg, "conf_uid", None) != conf_uid:
            continue
        history_uid = getattr(ctx, "history_uid", "")
        if history_uid:
            found = history_uid
    return found


# --- 寫設定 ----------------------------------------------------------------- #
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# 端點共用的前置作業
# --------------------------------------------------------------------------- #


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "error": message})


async def _parse_body(
    request: Request,
) -> tuple[Optional[dict], Optional[JSONResponse]]:
    """讀出 JSON body，順便驗證它是個物件。

    回傳 (body, 錯誤回應)——其中一個一定是 None。六個端點原本各自寫一遍
    try/except 加 isinstance 檢查，錯誤訊息還得手動保持一致。
    """
    try:
        body = await request.json()
    except Exception:
        return None, _error(400, "Invalid JSON body.")
    if not isinstance(body, dict):
        return None, _error(400, "Invalid JSON body.")
    return body, None


def _resolved_uid(body: dict):
    """從 body 取出並驗證 conf_uid。回傳 (conf_uid, 錯誤回應)。"""
    conf_uid, err = _resolve_conf_uid(body.get("conf_uid"))
    if err:
        return None, _error(400, err)
    return conf_uid, None


def _memory_keeper(client_contexts: dict, conf_uid: str):
    """這段對話的記憶在哪個 agent 手上；沒有就回 None。

    看的是 _resolve_history_uid 選中的那個連線：正在初始化的連線（還沒有
    history_uid、agent 也還沒好）不算。
    """
    found = None
    for ctx in client_contexts.values():
        cfg = getattr(ctx, "character_config", None)
        if getattr(cfg, "conf_uid", None) != conf_uid:
            continue
        if not getattr(ctx, "history_uid", ""):
            continue
        agent = getattr(ctx, "agent_engine", None)
        found = agent if hasattr(agent, "conversation_memory") else None
    return found


class _EngineSelfMemory:
    """沒有連線開著時，直接找這個角色還在跑的引擎；介面跟 agent 那兩個方法一樣。"""

    def __init__(self, companion):
        self._companion = companion

    def self_memory(self) -> str:
        return "\n".join(self._companion.self_memories())

    def rewrite_self_memory(self, text: str, *, edited_from=None) -> None:
        self._companion.rewrite_self_memories(
            text.splitlines(),
            edited_from=None if edited_from is None else edited_from.splitlines(),
        )


def _engine_storage(conf_uid: str):
    from .character_engine.factory import storage_dir

    return storage_dir(conf_uid)


def _self_keeper(client_contexts: dict, conf_uid: str):
    """她自己說過的事由誰拿著：這個角色的 agent，或沒有連線時她還在跑的引擎。

    她自己的記憶在角色層，不屬於任何一段對話，所以不看 history_uid：這個角色
    任何一個連線的 agent 都是同一份。都沒有就回 None。
    """
    for ctx in client_contexts.values():
        cfg = getattr(ctx, "character_config", None)
        agent = getattr(ctx, "agent_engine", None)
        if getattr(cfg, "conf_uid", None) == conf_uid and hasattr(agent, "self_memory"):
            return agent
    try:
        from .character_engine.factory import current_companion

        companion = current_companion(str(_engine_storage(conf_uid).resolve()))
    except Exception:
        return None
    if companion is None or not hasattr(companion, "self_memories"):
        return None
    return _EngineSelfMemory(companion)


ENGINE_NOT_RUNNING = "她的引擎還沒啟動；先跟她開始一段對話再改她的記憶。"


def _save_through(keeper, history_uid: str, content: str, edited_from) -> None:
    """edited_from 是前端這次編輯的起點（載入時放進 textarea 的那一版）。只有起點
    裡有、存回來時不見的行才算使用者刪掉的；頁面開著的時候引擎新記下的行不受
    影響。伺服器自己記不住這件事——同一段對話可以開兩個頁面、切分頁回來也不會
    重載文字框——所以由前端送。沒送就當整份取代。"""
    keeper.rewrite_conversation_memory(
        history_uid,
        content,
        edited_from=edited_from if isinstance(edited_from, str) else None,
    )


def _resolved_history_uid(client_contexts: dict, conf_uid: str):
    """取出目前連線正在用的 history_uid。回傳 (history_uid, 錯誤回應)。

    三個端點（GET /api/memory、POST /api/memory、POST /api/memory/clear）原本
    各自重複同一段八行的 409 guard——找不到就回 409，不猜一個（猜錯會編輯到
    別段對話的記憶）。跟 _resolved_uid 擺在一起收成一個，未來要加第四個需要
    這段對話身分的端點時，才不會複製貼上時漏掉這個檢查。
    """
    history_uid = _resolve_history_uid(client_contexts, conf_uid)
    if not history_uid:
        return None, JSONResponse(
            status_code=409,
            content={
                "error": "記憶現在屬於一段對話。請先在 app 裡連上這個角色，"
                "才知道要讀寫哪一段對話的記憶。"
            },
        )
    return history_uid, None


async def _write_or_error(fn, *args, what: str):
    """在執行緒裡跑一個寫入動作；失敗時記 log 並回統一的 500。

    寫設定檔失敗的處理六個端點都一樣：記下真正的例外（給我們看）、回一句
    使用者看得懂的話（不外洩內部細節）。
    """
    try:
        await asyncio.to_thread(fn, *args)
        return None
    except Exception as e:
        logger.error(f"[memory] {what} failed: {type(e).__name__}: {e}")
        return _error(500, "Could not write config file.")


# --------------------------------------------------------------------------- #
# Route factory
# --------------------------------------------------------------------------- #


def init_memory_route(client_contexts: dict) -> APIRouter:
    """長期記憶設定頁的 REST 端點。只接受本機請求。

    - GET  /api/memory?conf_uid=<uid>   記憶開關、這段對話的記憶、她自己的記憶
    - POST /api/memory                  改這段對話的記憶（使用者手動修正）
    - POST /api/memory/toggle           開關長期記憶
    - POST /api/memory/clear            清空這段對話的記憶
    - POST /api/memory/self             改她自己的記憶（角色層；不需要連線）
    - POST /api/memory/self/clear       清空她自己的記憶

    改記憶是即時的，引擎下一輪就照新的內容。開關要重新載入才生效。
    """
    router = APIRouter()

    @router.get("/api/memory")
    async def get_memory(request: Request):
        if not _is_local_request(request):
            return _forbidden()

        conf_uid, err = _resolve_conf_uid(request.query_params.get("conf_uid"))
        if err:
            return JSONResponse(status_code=400, content={"error": err})

        history_uid, bad = _resolved_history_uid(client_contexts, conf_uid)
        if bad:
            return bad

        keeper = _memory_keeper(client_contexts, conf_uid)
        self_keeper = _self_keeper(client_contexts, conf_uid)
        return JSONResponse(
            {
                "conf_uid": conf_uid,
                "enabled": _memory_enabled_for(conf_uid),
                "content": keeper.conversation_memory(history_uid) if keeper else "",
                "self_content": self_keeper.self_memory() if self_keeper else "",
            }
        )

    @router.post("/api/memory")
    async def save_memory(request: Request):
        """把這段對話的記憶換成使用者編輯過的版本：修掉她記錯或不想被記住的事。"""
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad

        history_uid, bad = _resolved_history_uid(client_contexts, conf_uid)
        if bad:
            return bad

        content = body.get("content")
        if not isinstance(content, str):
            return _error(400, "'content' must be a string.")

        keeper = _memory_keeper(client_contexts, conf_uid)
        if keeper is None:
            return _error(409, ENGINE_NOT_RUNNING)
        _save_through(keeper, history_uid, content, body.get("edited_from"))
        stored = keeper.conversation_memory(history_uid)
        logger.info(f"[memory] edited in the engine (conf_uid={conf_uid})")
        return JSONResponse({"ok": True, "conf_uid": conf_uid, "content": stored})

    @router.post("/api/memory/toggle")
    async def toggle_memory(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad
        if not isinstance(body.get("enabled"), bool):
            return _error(400, "Missing 'enabled' boolean.")

        # 開關是這個角色自己的：寫進她的角色檔（底稿角色寫 conf.yaml）。
        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad
        filename = await asyncio.to_thread(
            character_settings.filename_for_uid, conf_uid
        )
        if filename is None:
            return _error(404, "Character not found.")

        enabled = bool(body["enabled"])
        bad = await _write_or_error(
            character_settings.write,
            filename,
            {"long_term_memory_enabled": enabled},
            what="toggle write",
        )
        if bad:
            return bad

        logger.info(f"[memory] toggle saved (conf_uid={conf_uid}, enabled={enabled})")
        return JSONResponse(
            {
                "ok": True,
                "conf_uid": conf_uid,
                "enabled": enabled,
                "restart_required": True,
            }
        )

    @router.post("/api/memory/clear")
    async def clear_memory(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad

        history_uid, bad = _resolved_history_uid(client_contexts, conf_uid)
        if bad:
            return bad

        keeper = _memory_keeper(client_contexts, conf_uid)
        if keeper is None:
            return _error(409, ENGINE_NOT_RUNNING)
        keeper.rewrite_conversation_memory(history_uid, "")

        logger.info(f"[memory] cleared (conf_uid={conf_uid})")
        return JSONResponse({"ok": True, "conf_uid": conf_uid, "cleared": True})

    @router.post("/api/memory/self")
    async def save_self_memory(request: Request):
        """改她自己的記憶。只以 conf_uid 為鍵：它在角色層，不屬於任何一段對話。"""
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad
        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad
        content = body.get("content")
        if not isinstance(content, str):
            return _error(400, "'content' must be a string.")
        self_keeper = _self_keeper(client_contexts, conf_uid)
        if self_keeper is None:
            return _error(409, ENGINE_NOT_RUNNING)
        # edited_from 的意思跟對話記憶一樣：只有頁面上有、存回來不見的行才算刪掉，
        # 頁面開著時引擎新記下的不受影響。
        edited_from = body.get("edited_from")
        self_keeper.rewrite_self_memory(
            content,
            edited_from=edited_from if isinstance(edited_from, str) else None,
        )
        stored = self_keeper.self_memory()
        logger.info(f"[memory] self memory edited in the engine (conf_uid={conf_uid})")
        # 引擎有上限，存進去的不一定全部留下：頁面要顯示它實際記得的。
        return JSONResponse({"ok": True, "conf_uid": conf_uid, "content": stored})

    @router.post("/api/memory/self/clear")
    async def clear_self_memory(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad
        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad
        self_keeper = _self_keeper(client_contexts, conf_uid)
        if self_keeper is None:
            return _error(409, ENGINE_NOT_RUNNING)
        self_keeper.rewrite_self_memory("")
        logger.info(f"[memory] self memory cleared (conf_uid={conf_uid})")
        return JSONResponse({"ok": True, "conf_uid": conf_uid, "cleared": True})

    return router
