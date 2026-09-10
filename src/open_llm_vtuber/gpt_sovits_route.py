"""GPT-SoVITS 一鍵安裝的端點，給設定精靈與語音設定分頁用。

- GET  /api/gpt-sovits          -> 支不支援、裝好了沒、要下載多少、要多少空間
- POST /api/gpt-sovits/install  -> 安裝，進度用 NDJSON 串流回傳（事件格式同 ollama-install）

裝好之後順便把語音引擎切到 GPT-SoVITS，使用者不必再去設定頁填位址和參考音。
"""

import asyncio
import json

import httpx
from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse, StreamingResponse

from . import gpt_sovits_installer as installer
from . import gpt_sovits_service as service
from .api_guard import forbidden as _forbidden, is_trusted_request as _is_local_request
from .conf_editor import CONF_PATH
from .config_manager.utils import read_yaml
from .perf_route import GPT_SOVITS_LANGS, _write_tts


def voice_text_lang(conf: dict) -> str:
    """換成 GPT-SoVITS 之後唸哪種語言：沿用換之前的聲音講的語言。

    講哪種語言是使用者在聲音設定裡選的。原本用 Edge TTS 中文聲音的角色，換了引擎
    還是講中文，不會突然改講日文。認不出來時才用參考音的語言。
    """
    tts = (conf.get("character_config") or {}).get("tts_config") or {}
    engine = tts.get("tts_model")
    raw = ""
    if engine == "edge_tts":
        raw = str((tts.get("edge_tts") or {}).get("voice") or "").split("-", 1)[0]
    elif engine == "gpt_sovits_tts":
        raw = str((tts.get("gpt_sovits_tts") or {}).get("text_lang") or "")
    lang = raw.strip().lower().removeprefix("all_")
    return lang if lang in GPT_SOVITS_LANGS else installer.REFERENCE_LANG


def _use_installed_voice(reference: dict) -> None:
    try:
        conf = read_yaml(CONF_PATH) or {}
        _write_tts(
            "gpt_sovits_tts",
            installer.API_URL,
            reference["path"],
            reference["prompt_text"],
            voice_text_lang(conf),
            reference["prompt_lang"],
        )
    except Exception as e:
        logger.warning(
            f"[gpt-sovits] couldn't switch the voice: {type(e).__name__}: {e}"
        )
        raise installer.InstallError(
            "GPT-SoVITS is installed, but switching the voice failed. Choose it in the voice settings."
        ) from e


def init_gpt_sovits_route() -> APIRouter:
    router = APIRouter()
    # 同時只允許一個安裝在跑。連按兩下、或開了兩個分頁，不該跑出兩份下載。
    install_lock = asyncio.Lock()

    @router.get("/api/gpt-sovits")
    async def status(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        return JSONResponse(
            {
                "supported": installer.supported(),
                "installed": installer.read_marker() is not None,
                "installing": install_lock.locked(),
                "running": await asyncio.to_thread(service.api_ready, 0.5),
                "download_bytes": installer.download_bytes(),
                "required_free_bytes": installer.required_free_bytes(),
                "install_dir": str(installer.install_root()),
            }
        )

    @router.post("/api/gpt-sovits/install")
    async def install(request: Request):
        """會下載並執行程式，所以跟其他寫入端點一樣只接受本機請求。"""
        if not _is_local_request(request):
            return _forbidden()

        def line(event: dict) -> str:
            return json.dumps(event, ensure_ascii=False) + "\n"

        async def stream():
            if install_lock.locked():
                yield line(
                    {
                        "status": "error",
                        "error": "GPT-SoVITS is already being installed.",
                    }
                )
                return
            async with install_lock:
                try:
                    async for event in installer.install():
                        if event["status"] == "success":
                            await asyncio.to_thread(
                                _use_installed_voice, event["reference"]
                            )
                        yield line(event)
                except installer.InstallError as e:
                    yield line({"status": "error", "error": str(e)})
                except httpx.HTTPError as e:
                    logger.warning(
                        f"[gpt-sovits] download failed: {type(e).__name__}: {e}"
                    )
                    yield line(
                        {
                            "status": "error",
                            "error": "The download failed. Check your connection and try again — it picks up where it left off.",
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"[gpt-sovits] install failed: {type(e).__name__}: {e}"
                    )
                    yield line(
                        {
                            "status": "error",
                            "error": "Installing GPT-SoVITS failed. Try again.",
                        }
                    )

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    return router
