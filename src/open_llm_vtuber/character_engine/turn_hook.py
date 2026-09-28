"""一輪對話講完後通知 agent。

抽成一個函式是為了讓條件只寫一次、測得到。single_conversation 本身太大，整條
對話鏈跑一次才測得到一個 if，不值得。
"""

from typing import Any, Optional

from loguru import logger


def notify_turn_finished(
    agent: Any,
    *,
    conf_uid: str,
    history_uid: Optional[str],
    user_text: Any,
    reply: Any,
    is_proactive: bool,
) -> None:
    """有 observe_turn 的 agent 才通知；任何失敗只寫 log。

    條件跟記憶整理相同：主動發話不是使用者在講話，空輸入沒有東西可以觀察。
    """
    observe = getattr(agent, "observe_turn", None)
    if observe is None or is_proactive or not history_uid:
        return
    if not isinstance(user_text, str) or not user_text.strip():
        return
    if not isinstance(reply, str) or not reply.strip():
        return
    try:
        observe(conf_uid, history_uid, user_text, reply)
    except Exception as exc:
        logger.warning(f"[engine] turn hook failed ({type(exc).__name__}: {exc})")
