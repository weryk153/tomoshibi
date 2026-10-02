"""YouTube 直播聊天室，只讀。

chat-downloader 0.2.8 在 2026-10-02 已經讀不到（ParsingError: Unable to parse initial
video data），所以走 YouTube 自己網頁用的路，只用既有的 httpx：

1. GET /live_chat?v=<id>&is_popout=1：頁面的 ytInitialData 有第一個 continuation，
   ytcfg 有 clientVersion。
2. POST /youtubei/v1/live_chat/get_live_chat {context, continuation}：回新留言、下一個
   continuation 與建議的等待時間。沒有下一個 continuation 就是直播結束。

YouTube 改版時會壞的是 parse_chat_page／parse_chat_response 這兩個純函式，測試在
tests/test_stream_youtube_chat.py。預設讀的是「熱門聊天」（YouTube 先濾掉一批洗版）。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from .chat_source import ChatEnded, ChatMessage, ChatSourceError

CHAT_PAGE = "https://www.youtube.com/live_chat"
CHAT_API = "https://www.youtube.com/youtubei/v1/live_chat/get_live_chat"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CLIENT_VERSION = re.compile(r'"INNERTUBE_CONTEXT_CLIENT_VERSION":"([^"]+)"')
# YouTube 建議的等待時間夾在這個範圍：太短會被擋，太長留言會堆太久。
_MIN_WAIT_MS, _MAX_WAIT_MS = 1000, 10000


def video_id_from_url(url: str) -> Optional[str]:
    """直播影片網址 → 影片 id。頻道網址（/@name/live）抓不到直播，回 None。"""
    url = url.strip()
    if _VIDEO_ID.match(url):
        return url
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    for prefix in ("www.", "m."):
        host = host.removeprefix(prefix)
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif host == "youtube.com" and parsed.path == "/watch":
        candidate = (parse_qs(parsed.query).get("v") or [""])[0]
    elif host == "youtube.com" and parsed.path.startswith("/live/"):
        candidate = parsed.path.split("/")[2]
    else:
        return None
    return candidate if _VIDEO_ID.match(candidate) else None


@dataclass(frozen=True)
class ChatBatch:
    messages: list[ChatMessage] = field(default_factory=list)
    continuation: Optional[str] = None  # None = 直播結束
    timeout_ms: int = 0


def _json_after(html: str, marker: str) -> Any:
    at = html.find(marker)
    start = html.find("{", at) if at >= 0 else -1
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(html[start:])
    except json.JSONDecodeError:
        return None
    return value


def _first_continuation(continuations: Any) -> tuple[Optional[str], int]:
    for entry in continuations or ():
        if not isinstance(entry, dict):
            continue
        for data in entry.values():
            if isinstance(data, dict) and data.get("continuation"):
                return str(data["continuation"]), int(data.get("timeoutMs") or 0)
    return None, 0


def parse_chat_page(html: str) -> tuple[str, str]:
    version = _CLIENT_VERSION.search(html)
    data = _json_after(html, "ytInitialData")
    renderer = ((data or {}).get("contents") or {}).get("liveChatRenderer")
    if not version or not renderer:
        raise ChatSourceError("這支影片沒有進行中的聊天室")
    continuation, _ = _first_continuation(renderer.get("continuations"))
    if not continuation:
        raise ChatEnded("聊天室已經結束")
    return version.group(1), continuation


def _text(runs: Any) -> str:
    parts = []
    for run in runs or ():
        if "text" in run:
            parts.append(str(run["text"]))
        elif (emoji := run.get("emoji")) and not emoji.get("isCustomEmoji"):
            # 一般表情的 emojiId 就是那個字元；頻道自訂表情只有圖，唸不出來。
            parts.append(str(emoji.get("emojiId", "")))
    return "".join(parts).strip()


def _is_member(renderer: dict) -> bool:
    # 會員徽章是頻道自訂的圖（customThumbnail）；管理員、驗證徽章是內建圖示（icon）。
    for badge in renderer.get("authorBadges") or ():
        if (badge.get("liveChatAuthorBadgeRenderer") or {}).get("customThumbnail"):
            return True
    return False


def _message(item: dict) -> Optional[ChatMessage]:
    if renderer := item.get("liveChatTextMessageRenderer"):
        kind = "member" if _is_member(renderer) else "text"
    elif renderer := item.get("liveChatPaidMessageRenderer"):
        kind = "paid"
    else:
        return None
    text = _text((renderer.get("message") or {}).get("runs"))
    author = str((renderer.get("authorName") or {}).get("simpleText") or "")
    author = author.strip().lstrip("@")
    if not text or not author or not renderer.get("id"):
        return None
    try:
        timestamp = int(renderer.get("timestampUsec")) / 1_000_000
    except (TypeError, ValueError):
        timestamp = time.time()
    return ChatMessage(
        id=str(renderer["id"]),
        author=author,
        text=text,
        timestamp=timestamp,
        kind=kind,
    )


def parse_chat_response(data: Any) -> ChatBatch:
    chat = ((data or {}).get("continuationContents") or {}).get("liveChatContinuation")
    if not isinstance(chat, dict):
        return ChatBatch()
    messages = []
    for action in chat.get("actions") or ():
        item = ((action or {}).get("addChatItemAction") or {}).get("item") or {}
        if message := _message(item):
            messages.append(message)
    continuation, timeout_ms = _first_continuation(chat.get("continuations"))
    return ChatBatch(messages, continuation, timeout_ms)


class YouTubeChatSource:
    def __init__(
        self,
        video_id: str,
        *,
        client: Optional[httpx.AsyncClient] = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.video_id = video_id
        self.connected = False
        self._client = client
        self._owns_client = client is None
        self._sleep = sleep

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "en"},
                cookies={"CONSENT": "YES+1"},
                follow_redirects=True,
                timeout=15,
            )
        return self._client

    async def messages(self) -> AsyncIterator[ChatMessage]:
        client = self._http()
        self.connected = False
        try:
            page = await client.get(
                CHAT_PAGE, params={"v": self.video_id, "is_popout": "1", "hl": "en"}
            )
            page.raise_for_status()
            version, continuation = parse_chat_page(page.text)
            self.connected = True
            while continuation:
                response = await client.post(
                    CHAT_API,
                    params={"prettyPrint": "false"},
                    json={
                        "context": {
                            "client": {
                                "clientName": "WEB",
                                "clientVersion": version,
                                "hl": "en",
                            }
                        },
                        "continuation": continuation,
                    },
                )
                response.raise_for_status()
                batch = parse_chat_response(response.json())
                for message in batch.messages:
                    yield message
                continuation = batch.continuation
                if continuation:
                    wait = min(max(batch.timeout_ms, _MIN_WAIT_MS), _MAX_WAIT_MS)
                    await self._sleep(wait / 1000)
        except (httpx.HTTPError, ValueError) as error:
            self.connected = False
            raise ChatSourceError(f"{type(error).__name__}: {error}") from error

    async def close(self) -> None:
        self.connected = False
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
