"""假聊天室：從 JSON Lines 檔照間隔吐出留言，讀完就當直播結束。"""

import asyncio
import json

import pytest

from src.open_llm_vtuber.stream.chat_source import (
    ChatMessage,
    ChatSourceError,
    FileChatSource,
)


def _collect(source):
    async def run():
        return [m async for m in source.messages()]

    return asyncio.run(run())


def test_messages_come_out_in_order_after_their_delay(tmp_path):
    path = tmp_path / "chat.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=False)
            for item in [
                {"author": "小明", "text": "今天好冷", "delay": 2},
                {"author": "阿華", "text": "妳好", "delay": 3, "kind": "member"},
            ]
        )
        + "\n\n",
        "utf-8",
    )
    now = [100.0]
    waited = []

    async def sleep(seconds):
        waited.append(seconds)
        now[0] += seconds

    source = FileChatSource(str(path), clock=lambda: now[0], sleep=sleep)
    messages = _collect(source)

    assert waited == [2.0, 3.0]
    assert messages == [
        ChatMessage(id="file-0", author="小明", text="今天好冷", timestamp=102.0),
        ChatMessage(
            id="file-1", author="阿華", text="妳好", timestamp=105.0, kind="member"
        ),
    ]
    assert source.connected is True


def test_a_missing_file_is_a_chat_error(tmp_path):
    with pytest.raises(ChatSourceError):
        _collect(FileChatSource(str(tmp_path / "nope.jsonl")))


def test_a_broken_line_is_a_chat_error(tmp_path):
    path = tmp_path / "chat.jsonl"
    path.write_text('{"author": "小明"}\n', "utf-8")
    with pytest.raises(ChatSourceError):
        _collect(FileChatSource(str(path), sleep=lambda s: asyncio.sleep(0)))
