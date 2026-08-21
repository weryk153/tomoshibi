"""語音清單與試聽：讓使用者用耳朵挑聲音，而不是從一串代號裡猜。

edge-tts 有幾百個語音代號（ja-JP-NanamiNeural 這種），直接列出來沒有人選得下去。
所以預設只給一份精選清單，附中文說明；想看全部的人可以帶 ?full=1 去線上抓。

試聽是這個模組真正的價值：合成一小段音訊直接播給使用者聽。挑聲音本來就該用聽的。

原本住在 character_route 裡——選聲音確實是設定角色的一部分，但「有哪些聲音可用」
與「這個聲音聽起來怎樣」是語音合成的知識，不是角色管理的。
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse, Response

from .api_guard import forbidden as _forbidden, is_trusted_request as _is_local_request

# 語音代號的合法字元。這個值會被拿去呼叫外部工具，必須先擋掉任意輸入。
VOICE_SHORTNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
# 試聽文字的長度上限——這是即時合成，不能讓人丟一整篇進來。
VOICE_SAMPLE_MAX_TEXT = 120
# 線上抓完整語音清單的逾時。這只是「想看全部」時的加值功能，抓不到就退回精選
# 清單，所以寧可等短一點也不要讓設定面板卡住。
LIST_VOICES_TIMEOUT = 6.0

VOICE_SAMPLE_TEXTS = {
    "zh-TW": "你好，很高興認識你。",
    "zh-CN": "你好，很高兴认识你。",
    "ja": "こんにちは、はじめまして。",
    "en": "Hi, nice to meet you.",
}
VOICE_SAMPLE_DEFAULT_TEXT = "Hi, nice to meet you."
VOICE_SAMPLE_TIMEOUT = 12.0  # seconds

CURATED_VOICES = [
    # zh-TW（台灣國語）
    {"value": "zh-TW-HsiaoChenNeural", "label": "曉臻（台灣國語・女）", "locale": "zh-TW", "gender": "Female"},
    {"value": "zh-TW-HsiaoYuNeural", "label": "曉雨（台灣國語・女）", "locale": "zh-TW", "gender": "Female"},
    {"value": "zh-TW-YunJheNeural", "label": "雲哲（台灣國語・男）", "locale": "zh-TW", "gender": "Male"},
    # en（English）
    {"value": "en-US-AvaNeural", "label": "Ava（English US・F）", "locale": "en-US", "gender": "Female"},
    {"value": "en-US-AndrewNeural", "label": "Andrew（English US・M）", "locale": "en-US", "gender": "Male"},
    {"value": "en-GB-SoniaNeural", "label": "Sonia（English UK・F）", "locale": "en-GB", "gender": "Female"},
    {"value": "en-US-AshleyNeural", "label": "Ashley（English US・F）", "locale": "en-US", "gender": "Female"},
    # ja（日本語）
    {"value": "ja-JP-NanamiNeural", "label": "Nanami（日本語・女）", "locale": "ja-JP", "gender": "Female"},
    {"value": "ja-JP-KeitaNeural", "label": "Keita（日本語・男）", "locale": "ja-JP", "gender": "Male"},
]

def _sample_text_for_voice(voice: str) -> str:
    """Pick a short locale-appropriate preview line from the voice ShortName."""
    v = voice.lower()
    if v.startswith("zh-tw"):
        return VOICE_SAMPLE_TEXTS["zh-TW"]
    if v.startswith("zh-cn") or v.startswith("zh-hk") or v.startswith("zh"):
        return VOICE_SAMPLE_TEXTS["zh-CN"]
    if v.startswith("ja"):
        return VOICE_SAMPLE_TEXTS["ja"]
    return VOICE_SAMPLE_TEXTS["en"]


async def _synth_voice_sample(voice: str, text: str) -> Optional[bytes]:
    """Stream one short edge-tts utterance into memory; None on any failure.

    Mirrors the live engine (edge_tts.Communicate) but collects the mp3 bytes in
    memory instead of writing a file, so the endpoint can return them directly.
    """
    try:
        import edge_tts

        async def _collect() -> bytes:
            communicate = edge_tts.Communicate(text, voice)
            buf = bytearray()
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    buf += chunk["data"]
            return bytes(buf)

        data = await asyncio.wait_for(_collect(), timeout=VOICE_SAMPLE_TIMEOUT)
        return data or None
    except Exception as e:
        # edge-tts can be region-blocked or slow; never raise to the caller.
        logger.warning(
            f"voice-sample synth failed (voice={voice}): {type(e).__name__}. "
            "edge-tts may be blocked in your region."
        )
        return None


def _build_live_voice_label(v: dict) -> str:
    friendly = v.get("FriendlyName") or v.get("ShortName", "")
    locale = v.get("Locale", "")
    gender = v.get("Gender", "")
    return f"{friendly}（{locale}・{gender}）" if locale else friendly


async def _live_edge_voices() -> Optional[list]:
    """Attempt edge_tts.list_voices() with a short timeout; None on any failure."""
    try:
        import edge_tts

        raw = await asyncio.wait_for(
            edge_tts.list_voices(), timeout=LIST_VOICES_TIMEOUT
        )
        voices = []
        for v in raw:
            short = v.get("ShortName")
            if not short:
                continue
            voices.append(
                {
                    "value": short,
                    "label": _build_live_voice_label(v),
                    "locale": v.get("Locale", ""),
                    "gender": v.get("Gender", ""),
                }
            )
        # zh-TW first to match the curated ordering / UI default.
        voices.sort(key=lambda x: (not x["locale"].startswith("zh-TW"), x["locale"]))
        return voices or None
    except Exception as e:
        logger.debug(f"live edge_tts.list_voices failed: {type(e).__name__}")
        return None


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"ok": False, "error": message})


def init_voice_route() -> APIRouter:
    """語音清單與試聽的端點。"""
    router = APIRouter()

    @router.get("/api/voices")
    async def list_voices(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        full = request.query_params.get("full")
        if full in ("1", "true", "yes"):
            voices = await _live_edge_voices()
            if voices is not None:
                return JSONResponse({"voices": voices, "source": "edge_tts"})
            # fall through to curated on any failure/timeout
        return JSONResponse({"voices": CURATED_VOICES, "source": "curated"})

    # ------------------------------------------------------------------ #
    @router.get("/api/voice-sample")
    async def voice_sample(request: Request):
        """Synthesize a short preview of a voice (試聽). Returns audio/mpeg bytes.

        Localhost-only (reused guard). Validates the voice ShortName charset to
        avoid arbitrary input; returns 502 on edge-tts failure/region-block so a
        blocked network surfaces a clean error instead of hanging.
        """
        if not _is_local_request(request):
            return _forbidden()
        voice = (request.query_params.get("voice") or "").strip()
        if not voice or not VOICE_SHORTNAME_RE.match(voice):
            return _bad_request("Invalid or missing voice.")
        text = (request.query_params.get("text") or "").strip()
        if not text:
            text = _sample_text_for_voice(voice)
        else:
            text = text[:VOICE_SAMPLE_MAX_TEXT]
        audio = await _synth_voice_sample(voice, text)
        if not audio:
            return JSONResponse(
                status_code=502,
                content={
                    "ok": False,
                    "error": "Could not synthesize the voice sample "
                    "(edge-tts may be blocked or slow).",
                },
            )
        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )

    # ------------------------------------------------------------------ #
    return router
