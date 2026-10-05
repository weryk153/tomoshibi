"""她的心情送到前端（character-mood）。

心情由引擎記、引擎淡（ai_character_engine 1.1.0）。這裡只把它包成前端要的訊息：
強度與時間是設下那一刻的原始值，前端用半衰期自己算淡到哪裡，不必一直來問。
不匯入引擎：沒選 character_engine_agent 的人也會走到這些呼叫點，那時 agent 沒有
mood_message，什麼都不送，前端維持原本的行為。
"""

import asyncio
import json
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

MESSAGE_TYPE = "character-mood"
# 送出中的訊息；留著參照，不然 task 可能在送完前被回收。
_SENDING: set = set()


def mood_message(snapshot: Any) -> Optional[dict]:
    """引擎的 CompanionSnapshot → 前端的訊息。舊引擎沒有這些欄位就是 None。"""
    updated_at = getattr(snapshot, "mood_updated_at", None)
    half_life = getattr(snapshot, "mood_half_life_seconds", None)
    if updated_at is None or half_life is None:
        return None
    try:
        return {
            "type": MESSAGE_TYPE,
            "mood": str(snapshot.emotion),
            "intensity": float(getattr(snapshot, "mood_intensity", 0.0)),
            "updated_at": float(updated_at),
            "half_life": float(half_life),
        }
    except (TypeError, ValueError):
        return None


async def send_character_mood(
    agent: Any, send: Callable[[str], Awaitable[Any]]
) -> bool:
    """有心情可說就送一則，回傳有沒有送。讀不到、送不出去都不往外丟：
    少一則心情頂多是臉沒變，不能因此打斷一輪對話或一次連線。"""
    read = getattr(agent, "mood_message", None)
    if read is None:
        return False
    try:
        message = read()
    except Exception as error:
        logger.debug(f"[mood] not read ({type(error).__name__}: {error})")
        return False
    if not message:
        return False
    try:
        await send(json.dumps(message))
    except Exception as error:
        logger.debug(f"[mood] not delivered ({type(error).__name__}: {error})")
        return False
    return True


def _nothing() -> None:
    return None


def _sent(task: asyncio.Task) -> None:
    _SENDING.discard(task)
    if not task.cancelled() and task.exception() is not None:
        logger.debug(f"[mood] not delivered ({task.exception()})")


def follow_mood(
    agent: Any, send: Optional[Callable[[str], Awaitable[Any]]]
) -> Callable[[], None]:
    """背景結果改了她的心情時送給這個頁面。回傳停止跟隨的函式。"""
    listen = getattr(agent, "listen_to_mood", None)
    if listen is None or send is None:
        return _nothing

    def deliver(message: dict) -> None:
        # 引擎在自己的 event loop 裡、提交背景結果的當下呼叫這裡，不能等送完。
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(send(json.dumps(message)))
        _SENDING.add(task)
        task.add_done_callback(_sent)

    return listen(deliver)
