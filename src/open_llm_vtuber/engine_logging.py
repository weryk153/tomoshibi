"""引擎（ai_character_engine）用標準 logging，主機用 loguru。

沒接起來的話，引擎的 warning 到不了 logs/：2026-10-17 往 worker 的 tunnel 斷了兩個
小時，背景工作全部失敗，她什麼都沒記住，log 裡一行都沒有。
"""

from __future__ import annotations

import logging

from loguru import logger

ENGINE_LOGGER = "ai_character_engine"


class _ToLoguru(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def route_engine_logs(level: int = logging.INFO) -> None:
    """引擎 ``level`` 以上的 log 交給 loguru；呼叫多次只接一次。"""
    engine = logging.getLogger(ENGINE_LOGGER)
    engine.setLevel(level)
    if not any(isinstance(h, _ToLoguru) for h in engine.handlers):
        engine.addHandler(_ToLoguru())
    engine.propagate = False
