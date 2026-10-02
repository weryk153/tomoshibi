"""自己讀 YouTube 聊天室（chat-downloader 2026-10-02 已壞）。

回應形狀照 2026-10-02 實際抓到的縮減。YouTube 改版時壞的會是這裡的 parse 函式。
"""

import asyncio
import json

import httpx
import pytest

from src.open_llm_vtuber.stream.chat_source import (
    ChatSourceError,
    FileChatSource,
    open_chat_source,
)
from src.open_llm_vtuber.stream.youtube_chat import (
    YouTubeChatSource,
    parse_chat_page,
    parse_chat_response,
    video_id_from_url,
)

VID = "1-LpQekNa9g"

PAGE = (
    '<script>ytcfg.set({"INNERTUBE_CONTEXT_CLIENT_VERSION":"2.20261001.01.00"});'
    '</script><script>window["ytInitialData"] = {"contents":{"liveChatRenderer":'
    '{"continuations":[{"invalidationContinuationData":{"continuation":"C1",'
    '"timeoutMs":10000}}]}}};</script>'
)


def _text_item(id_, author, runs, usec="1790923121088765", badges=None):
    renderer = {
        "id": id_,
        "authorName": {"simpleText": author},
        "message": {"runs": runs},
        "timestampUsec": usec,
    }
    if badges:
        renderer["authorBadges"] = badges
    return {"addChatItemAction": {"item": {"liveChatTextMessageRenderer": renderer}}}


def _response(actions, continuation="C2", timeout=5000):
    chat = {"actions": actions}
    if continuation:
        chat["continuations"] = [
            {
                "invalidationContinuationData": {
                    "continuation": continuation,
                    "timeoutMs": timeout,
                }
            }
        ]
    return {"continuationContents": {"liveChatContinuation": chat}}


@pytest.mark.parametrize(
    "url,expected",
    [
        (f"https://www.youtube.com/watch?v={VID}", VID),
        (f"https://youtube.com/watch?v={VID}&t=10", VID),
        (f"https://m.youtube.com/watch?v={VID}", VID),
        (f"https://youtu.be/{VID}?si=x", VID),
        (f"https://www.youtube.com/live/{VID}?feature=share", VID),
        (f"youtube.com/watch?v={VID}", VID),
        (VID, VID),
        ("https://www.youtube.com/@LofiGirl/live", None),
        ("https://www.youtube.com/channel/UCSJ4gkVC6NrvII8umztf0Ow", None),
        ("https://example.com/watch?v=" + VID, None),
        ("", None),
    ],
)
def test_only_live_video_urls_are_accepted(url, expected):
    assert video_id_from_url(url) == expected


def test_the_page_gives_the_version_and_first_continuation():
    assert parse_chat_page(PAGE) == ("2.20261001.01.00", "C1")


def test_a_page_without_live_chat_is_an_error():
    with pytest.raises(ChatSourceError):
        parse_chat_page("<html>沒有聊天室</html>")


def test_text_member_and_super_chat_are_read():
    member_badge = [
        {"liveChatAuthorBadgeRenderer": {"customThumbnail": {"thumbnails": []}}}
    ]
    mod_badge = [{"liveChatAuthorBadgeRenderer": {"icon": {"iconType": "MODERATOR"}}}]
    paid = {
        "addChatItemAction": {
            "item": {
                "liveChatPaidMessageRenderer": {
                    "id": "p1",
                    "authorName": {"simpleText": "@大方"},
                    "message": {"runs": [{"text": "生日快樂"}]},
                    "timestampUsec": "1790923130000000",
                }
            }
        }
    }
    batch = parse_chat_response(
        _response(
            [
                _text_item("t1", "@小明", [{"text": "今天好冷"}], badges=mod_badge),
                _text_item("t2", "@阿華", [{"text": "嗨"}], badges=member_badge),
                paid,
            ]
        )
    )
    assert [(m.id, m.author, m.text, m.kind) for m in batch.messages] == [
        ("t1", "小明", "今天好冷", "text"),
        ("t2", "阿華", "嗨", "member"),
        ("p1", "大方", "生日快樂", "paid"),
    ]
    assert batch.messages[0].timestamp == pytest.approx(1790923121.088765)
    assert (batch.continuation, batch.timeout_ms) == ("C2", 5000)


def test_custom_emoji_are_dropped_and_unicode_emoji_kept():
    custom = {
        "emoji": {"emojiId": "UCx/abc", "isCustomEmoji": True, "shortcuts": [":yt:"]}
    }
    batch = parse_chat_response(
        _response(
            [
                _text_item("e1", "@a", [custom]),
                _text_item(
                    "e2", "@b", [{"text": "好耶"}, {"emoji": {"emojiId": "🎉"}}]
                ),
            ]
        )
    )
    assert [m.text for m in batch.messages] == ["好耶🎉"]


def test_odd_shapes_do_not_raise():
    assert parse_chat_response({}).continuation is None
    assert parse_chat_response({"continuationContents": {}}).messages == []
    ended = parse_chat_response(_response([], continuation=None))
    assert ended.continuation is None
    nameless = parse_chat_response(
        _response(
            [_text_item("n1", "", [{"text": "誰"}]), {"addChatItemAction": {}}, {}]
        )
    )
    assert nameless.messages == []


def test_the_source_polls_until_the_chat_ends():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.params["v"] == VID
            return httpx.Response(200, text=PAGE)
        body = json.loads(request.content)
        calls.append(body["continuation"])
        assert body["context"]["client"]["clientVersion"] == "2.20261001.01.00"
        if body["continuation"] == "C1":
            return httpx.Response(
                200,
                json=_response([_text_item("t1", "@小明", [{"text": "安安"}])], "C2"),
            )
        return httpx.Response(200, json=_response([], continuation=None))

    slept = []

    async def sleep(seconds):
        slept.append(seconds)

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        source = YouTubeChatSource(VID, client=client, sleep=sleep)
        got = [m.text async for m in source.messages()]
        connected = source.connected
        await client.aclose()
        return got, connected

    got, connected = asyncio.run(run())
    assert got == ["安安"]
    assert connected is True
    assert calls == ["C1", "C2"]
    assert slept == [5.0]


def test_http_failure_is_a_chat_error():
    def handler(request):
        return httpx.Response(503)

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        source = YouTubeChatSource(VID, client=client)
        try:
            return [m async for m in source.messages()]
        finally:
            await client.aclose()

    with pytest.raises(ChatSourceError):
        asyncio.run(run())


def test_open_chat_source_picks_by_url(tmp_path):
    assert isinstance(open_chat_source(f"file:{tmp_path}/c.jsonl"), FileChatSource)
    youtube = open_chat_source(f"https://youtu.be/{VID}")
    assert isinstance(youtube, YouTubeChatSource) and youtube.video_id == VID
    with pytest.raises(ValueError):
        open_chat_source("https://www.youtube.com/@LofiGirl/live")
