from typing import Dict, Optional, Tuple
import asyncio
from loguru import logger
from collections import defaultdict


class MessageHandler:
    def __init__(self):
        self._response_events: Dict[
            str, Dict[Tuple[str, Optional[str]], asyncio.Event]
        ] = defaultdict(dict)
        self._response_data: Dict[str, Dict[Tuple[str, Optional[str]], dict]] = (
            defaultdict(dict)
        )

    def arm_response(
        self,
        client_uid: str,
        response_type: str,
        request_id: str | None = None,
    ) -> None:
        """在送出請求「之前」先掛好等待者。

        handle_message() 只會叫醒已經登記在案的等待者，早到的回應沒有任何緩衝，
        會被直接丟掉。所以「先送訊息、再開始等」這個順序本身就是競態：對方回得
        夠快就永遠等不到。要等某個回應的呼叫端應該先 arm_response()、送出訊息、
        再 wait_for_response()——後者看到已經掛好的等待者就直接沿用。
        """
        response_key = (response_type, request_id)
        if response_key not in self._response_events[client_uid]:
            self._response_events[client_uid][response_key] = asyncio.Event()

    async def wait_for_response(
        self,
        client_uid: str,
        response_type: str,
        request_id: str | None = None,
        timeout: float | None = None,
    ) -> Optional[dict]:
        """
        Wait for a response of specific type and optional request_id from a client.

        Args:
            client_uid: Client identifier
            response_type: Type of response to wait for
            request_id: Optional identifier for the specific request
            timeout: Optional timeout in seconds. If None, wait indefinitely

        Returns:
            Optional[dict]: Response data if received, None if timeout
        """
        response_key = (response_type, request_id)
        # 沿用 arm_response() 先掛好的等待者，否則在這裡才建立（維持舊行為）。
        # 若回應在 arm 之後、走到這裡之前就到了，事件已經是 set 的狀態，下面的
        # wait 立刻返回——這正是先 arm 的目的。
        event = self._response_events[client_uid].get(response_key)
        if event is None:
            event = asyncio.Event()
            self._response_events[client_uid][response_key] = event

        try:
            if timeout is not None:
                # Wait with timeout
                await asyncio.wait_for(event.wait(), timeout)
            else:
                # Wait indefinitely
                await event.wait()

            return self._response_data[client_uid].pop(response_key, None)
        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout waiting for {response_type} (ID: {request_id}) from {client_uid}"
            )
            return None
        finally:
            self._response_events[client_uid].pop(response_key, None)

    def handle_message(self, client_uid: str, message: dict) -> None:
        """
        Process an incoming message, potentially matching a response event waiting.

        Args:
            client_uid: Client identifier
            message: Message data dictionary, expected to contain 'type' and optionally 'request_id'
        """
        msg_type = message.get("type")
        request_id = message.get("request_id")
        if not msg_type:
            return

        response_key = (msg_type, request_id)

        if (
            client_uid in self._response_events
            and response_key in self._response_events[client_uid]
        ):
            self._response_data[client_uid][response_key] = message
            self._response_events[client_uid][response_key].set()

    def cleanup_client(self, client_uid: str) -> None:
        """
        Cleanup all events and cached data for a given client.

        Args:
            client_uid: Client identifier
        """
        if client_uid in self._response_events:
            for event in self._response_events[client_uid].values():
                event.set()
            self._response_events.pop(client_uid)
            self._response_data.pop(client_uid, None)


message_handler = MessageHandler()
