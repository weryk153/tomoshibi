"""引擎的 log 進得了主機的 loguru。"""

import logging

from loguru import logger

from src.open_llm_vtuber.engine_logging import route_engine_logs


def test_an_engine_warning_reaches_loguru_once():
    seen = []
    sink = logger.add(lambda message: seen.append(message.record["message"]), level="INFO")
    try:
        route_engine_logs()
        route_engine_logs()
        logging.getLogger("ai_character_engine.companion.companion").warning(
            "background %s failed (%d in a row)", "self_memory", 1
        )
        logging.getLogger("ai_character_engine.companion.companion").debug("too quiet")
    finally:
        logger.remove(sink)
    assert seen == ["background self_memory failed (1 in a row)"]


def test_an_unreachable_background_endpoint_is_said_at_start():
    import socket

    from src.open_llm_vtuber.character_engine.factory import reachable

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # closed again before it is tried
    seen = []
    sink = logger.add(lambda message: seen.append(message.record["message"]), level="WARNING")
    try:
        assert reachable(f"http://127.0.0.1:{port}/v1") is False
    finally:
        logger.remove(sink)
    assert len(seen) == 1 and f"127.0.0.1:{port}" in seen[0]


def test_a_listening_background_endpoint_is_reachable():
    import socket

    from src.open_llm_vtuber.character_engine.factory import reachable

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        assert reachable(f"http://127.0.0.1:{s.getsockname()[1]}/v1") is True
