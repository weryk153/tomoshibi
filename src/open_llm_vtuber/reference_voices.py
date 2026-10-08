"""GPT-SoVITS 的參考音：每個角色一個資料夾，共用的放 shared/，可以從角色頁上傳。

    references/
      <conf_uid>/xxx.wav (+ xxx.txt 逐字稿)   這個角色自己的聲音，只在她的選單裡
      shared/xxx.wav                           每個角色都看得到（例如つくよみちゃん）
      xxx.wav                                  舊的放法：每個角色都看得到

參考音要 3～10 秒（GPT-SoVITS 不收範圍外的）。上傳太長的，在句子之間的停頓處切
成 10 秒內最長的一段；逐字稿由語音辨識聽切好的那段產生，所以兩者一定對得上。沒有
語音辨識時逐字稿留空，讓使用者自己填。
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from typing import Any, Callable, Optional

from fastapi import APIRouter, Request
from loguru import logger
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from starlette.responses import JSONResponse

from .api_guard import is_trusted_request as _is_local_request

SHARED = "shared"
MIN_SECONDS = 3.0
MAX_SECONDS = 10.0
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
SAMPLE_RATE = 44100
_PAD_MS = 120
_OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")


class NotUsable(ValueError):
    """這段聲音當不了參考音（訊息給使用者看）。"""


def owner_folder(name: str) -> Optional[str]:
    """角色的資料夾名（conf_uid 或 shared）；不是單純的名字就是 None。"""
    name = str(name or "")
    return name if _OWNER.match(name) else None


def fit(clip: AudioSegment) -> AudioSegment:
    """可以當參考音的一段：單聲道、去掉頭尾的靜音，太長就在停頓處切到 10 秒內。"""
    clip = clip.set_channels(1).set_frame_rate(SAMPLE_RATE).set_sample_width(2)
    threshold = max(-50.0, clip.dBFS - 16) if clip.dBFS != float("-inf") else -50.0
    spans = detect_nonsilent(
        clip, min_silence_len=250, silence_thresh=threshold, seek_step=10
    )
    if not spans:
        raise NotUsable("聽不到聲音。參考音要 3 到 10 秒的說話聲。")
    best: Optional[tuple[int, int]] = None
    for i in range(len(spans)):
        for j in range(i, len(spans)):
            start, end = spans[i][0], spans[j][1]
            length = end - start
            if length > MAX_SECONDS * 1000:
                break
            if length >= MIN_SECONDS * 1000 and (
                best is None or length > best[1] - best[0]
            ):
                best = (start, end)
    if best is None:
        talking = sum(end - start for start, end in spans) / 1000
        if talking < MIN_SECONDS:
            raise NotUsable(
                f"太短了（說話只有 {talking:.1f} 秒）。參考音要 3 到 10 秒。"
            )
        raise NotUsable(
            "找不到 3 到 10 秒、前後有停頓的一段（一句話就超過 10 秒）。請剪一段 3 到 10 秒的再上傳。"
        )
    start = max(0, best[0] - _PAD_MS)
    end = min(len(clip), best[1] + _PAD_MS)
    return clip[start:end]


def voices_in_root(root: str) -> list[dict[str, Any]]:
    """root 底下的參考音：直接放在 root 的（owner ""）和每個子資料夾的。"""
    from .perf_route import _voices_in

    seen: set = set()
    voices = _voices_in(root, seen, owner="")
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if os.path.isdir(folder) and owner_folder(name):
            voices.extend(_voices_in(folder, seen, owner=name))
    return voices


def references_root() -> str:
    """參考音的根目錄：底稿角色的參考音所在的資料夾（在角色資料夾或 shared/ 裡
    的話往上一層）；沒有就是一鍵安裝的 references/。"""
    from . import gpt_sovits_installer
    from .conf_editor import CONF_PATH
    from .config_manager.utils import read_yaml

    node: Any = None
    try:
        node = read_yaml(CONF_PATH) or {}
        for key in (
            "character_config",
            "tts_config",
            "gpt_sovits_tts",
            "ref_audio_path",
        ):
            node = node.get(key) if isinstance(node, dict) else None
    except Exception:
        node = None
    folder = os.path.dirname(str(node or "").strip())
    if folder and os.path.isdir(folder):
        parent = os.path.dirname(folder)
        if os.path.basename(folder) == SHARED or os.path.isdir(
            os.path.join(parent, SHARED)
        ):
            return parent
        return folder
    return str(gpt_sovits_installer.install_root() / "references")


def _label(name: str) -> str:
    stem = os.path.splitext(os.path.basename(str(name or "")))[0]
    return re.sub(r"[^\w\-]+", "_", stem).strip("_") or "voice"


def _free_name(folder: str, label: str) -> str:
    candidate, n = label, 1
    while os.path.exists(os.path.join(folder, candidate + ".wav")):
        n += 1
        candidate = f"{label}_{n}"
    return candidate


async def _transcribe(ears: Any, clip: AudioSegment) -> str:
    if ears is None:
        return ""
    import numpy as np

    mono = clip.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    audio = np.array(mono.get_array_of_samples(), dtype=np.float32) / 32768.0
    try:
        return str(await ears.async_transcribe_np(audio) or "").strip()
    except Exception as e:  # noqa: BLE001 — 沒有逐字稿就讓使用者自己填
        logger.warning(f"[reference] 語音辨識失敗：{type(e).__name__}")
        return ""


def _decode(raw: bytes, name: str) -> Optional[AudioSegment]:
    """音檔的內容；讀不了是 None。先寫成暫存檔再交給 ffmpeg：從記憶體用管線餵
    不是音檔的資料時，ffmpeg 會卡住不回來。"""
    suffix = os.path.splitext(str(name or ""))[1].lower()
    if suffix not in (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".webm"):
        suffix = ".bin"
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "upload" + suffix)
        with open(path, "wb") as f:
            f.write(raw)
        try:
            return AudioSegment.from_file(path)
        except Exception:
            return None


def _bad(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"ok": False, "error": message})


def init_reference_voice_route(ears: Callable[[], Any]) -> APIRouter:
    """POST /api/reference-voices?owner=<conf_uid 或 shared>&name=<原檔名>，本文是
    音檔本身（mp3、wav…）。存成 <owner>/<名字>.wav，回傳選單用的那一筆。"""
    router = APIRouter()

    @router.post("/api/reference-voices")
    async def upload(request: Request):
        if not _is_local_request(request):
            return JSONResponse(
                status_code=403, content={"ok": False, "error": "Forbidden."}
            )
        owner = owner_folder(request.query_params.get("owner", ""))
        if owner is None:
            return _bad("不知道要放進哪個角色的資料夾。")
        name = request.query_params.get("name", "") or "voice.wav"
        raw = await request.body()
        if not raw or len(raw) > MAX_UPLOAD_BYTES:
            return _bad("檔案是空的，或超過 30 MB。")
        clip = await asyncio.to_thread(_decode, raw, name)
        if clip is None:
            return _bad("讀不了這個檔案，請上傳 mp3 或 wav。")
        try:
            clip = fit(clip)
        except NotUsable as e:
            return _bad(str(e))
        folder = os.path.join(references_root(), owner)
        os.makedirs(folder, exist_ok=True)
        label = _free_name(folder, _label(name))
        path = os.path.join(folder, label + ".wav")
        clip.export(path, format="wav")
        transcript = await _transcribe(ears(), clip)
        if transcript:
            with open(os.path.join(folder, label + ".txt"), "w", encoding="utf-8") as f:
                f.write(transcript)
        logger.info(
            f"[reference] 上傳 {owner}/{label}.wav（{len(clip) / 1000:.1f} 秒）"
        )
        return {
            "ok": True,
            "voice": {
                "path": path,
                "label": label,
                "prompt_text": transcript,
                "owner": owner,
                "seconds": round(len(clip) / 1000, 2),
            },
        }

    return router
