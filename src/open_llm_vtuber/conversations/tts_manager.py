import asyncio
import json
import uuid
from datetime import datetime
from typing import Awaitable, Callable, List, Optional, Dict, Tuple
from loguru import logger

from ..agent.output_types import DisplayText, Actions
from ..avatar_model import AvatarModel
from ..expression_pick import (
    GRACE_SECONDS,
    LEAD_SECONDS,
    SILENT_GRACE_SECONDS,
    apply_pick,
)
from ..tts.tts_interface import TTSInterface
from ..utils.stream_audio import prepare_audio_payload
from .laughter import is_laughter_only
from .text_content import has_speakable_text
from .types import WebSocketSend

# 引擎挑這句的表情與動作（expression_pick.EnginePicker.ask 綁好這句）。
Pick = Callable[[], Awaitable[Optional[dict]]]


def _seconds_of(message: Dict) -> float:
    """這個 payload 念完要多久（volumes × slice_length）；不是聲音的是 0。"""
    volumes = message.get("volumes") if isinstance(message, dict) else None
    if not volumes:
        return 0.0
    return len(volumes) * float(message.get("slice_length") or 0) / 1000


def _is_timeout(error: Optional[BaseException]) -> bool:
    """各引擎用的 HTTP 套件不同（requests、httpx、aiohttp…），逾時例外沒有共同
    父類別可以 isinstance，所以看內建 TimeoutError 或類別名稱裡的 Timeout。"""
    if error is None:
        return False
    if isinstance(error, TimeoutError):
        return True
    return any("Timeout" in cls.__name__ for cls in type(error).__mro__)


def _mark_subtitle_hold(
    payload: Dict, display_text: DisplayText, subtitle_text: Optional[str]
) -> None:
    """只有笑聲的句子（「哈↗哈↘哈↗！」）標 keep_subtitle：聲音照播、對話紀錄
    照記，前端只是不把畫面字幕換成這一句，留著上一句。看的是畫面上會顯示的
    那行（有字幕翻譯就看翻譯）。"""
    visible = subtitle_text or getattr(display_text, "text", "") or ""
    payload["keep_subtitle"] = is_laughter_only(visible)


class TTSTaskManager:
    """Manages TTS tasks and ensures ordered delivery to frontend while allowing parallel TTS generation"""

    # GPT-SoVITS (the local synth service) is a single CPU/GPU-bound process that
    # queues requests internally rather than truly parallelizing them. Once
    # translation stops blocking the event loop, a dozen-plus sentences can reach
    # `_process_tts` almost simultaneously; firing all of their synthesis calls at
    # once floods that one service's internal queue and makes per-sentence latency
    # WORSE (head-of-line contention) instead of better. 2 in-flight requests lets
    # the client have the next request already sitting at the server the instant
    # the current one finishes (no idle round-trip gap between sentences) without
    # meaningfully oversubscribing a service that can't actually run them in
    # parallel. This is deliberately small, not a generic thread-pool-sized value.
    SYNTHESIS_CONCURRENCY = 2

    # 合成失敗（丟例外或回 None）時總共試幾次。GPT-SoVITS 在記憶體吃緊時偶爾
    # 一句超過 120 秒，第二次通常就過了；再失敗才放棄，送靜音 payload 並跳通知。
    # 放在這裡而不是各引擎裡，所以每個 TTS 後端都有同樣的保護。
    SYNTHESIS_ATTEMPTS = 2

    def __init__(self) -> None:
        self.task_list: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        # Queue of (messages, sequence_number). Each sequence number carries the
        # list of websocket messages for that sentence (its audio payload, plus a
        # failure notice when synthesis gave up), so they stay in sentence order.
        self._payload_queue: asyncio.Queue = asyncio.Queue()
        # Task to handle sending payloads in order
        self._sender_task: Optional[asyncio.Task] = None
        # Counter for maintaining order
        self._sequence_counter = 0
        self._next_sequence_to_send = 0
        # Caps how many synthesis calls to the (single, local) TTS service are
        # in flight at once. See SYNTHESIS_CONCURRENCY above.
        self._synthesis_semaphore = asyncio.Semaphore(self.SYNTHESIS_CONCURRENCY)
        # 已送出的聲音大約何時念完（loop.time()）；每送出一句就通知等著的挑選。
        self._play_until = 0.0
        self._sent = asyncio.Condition()

    async def speak(
        self,
        tts_text: str,
        display_text: DisplayText,
        actions: Optional[Actions],
        live2d_model: AvatarModel,
        tts_engine: TTSInterface,
        websocket_send: WebSocketSend,
        subtitle_text: Optional[str] = None,
        spoken_text: Optional[str] = None,
        silenced: bool = False,
        pick: Optional[Pick] = None,
    ) -> None:
        """
        Queue a TTS task while maintaining order of delivery.

        Args:
            tts_text: Text to synthesize
            display_text: Text to display in UI
            actions: Live2D model actions
            live2d_model: Live2D model instance
            tts_engine: TTS engine instance
            websocket_send: WebSocket send function
            subtitle_text: Optional display-only translated subtitle. When None the
                frontend falls back to display_text.text (the canonical reply R).
                This NEVER replaces display_text.text, which memory/history rely on.
            spoken_text: 雙語字幕開著時她念的那句（見 conversations/bilingual.py）。
                None＝不帶，payload 跟沒有這個功能時一樣。沒東西可念、走靜音
                payload 的句子本來就不換字幕，不帶。
            silenced: 這句本來有話要念，是語音翻譯兩次都不是她的語言才被清空的
                （conversation_utils）。靜音 payload 的畫面字幕本來不動（「……」
                「（笑）」沒必要上字幕），這種句子例外：標 show_subtitle 讓前端
                把字幕換到這句，不然畫面停在上一句。
            pick: 背景模型挑這句的表情與動作（expression_source: background）。
                跟合成並行，結果放進 actions；它自己有上限、失敗回 None，不擋聲音。
                None＝tags 模式，流程與 payload 跟沒有這個功能時一樣。
        """
        # 沒有字母／文字／數字可念（「……」「♪」、表情符號、*動作*）就不送去合成：
        # 引擎對這種輸入多半回錯（GPT-SoVITS 回 400），會被當成失敗重試再跳通知。
        if not has_speakable_text(tts_text):
            logger.debug(
                "Nothing speakable in TTS text, sending silent display payload"
            )
            # Get current sequence number for silent payload
            current_sequence = self._sequence_counter
            self._sequence_counter += 1

            # Start sender task if not running
            if not self._sender_task or self._sender_task.done():
                self._sender_task = asyncio.create_task(
                    self._process_payload_queue(websocket_send)
                )

            if pick is None:
                await self._send_silent_payload(
                    display_text, actions, current_sequence, subtitle_text, silenced
                )
                return
            # 沒聲音的句子（*歪頭*）一樣配表情；等挑選的時候不能擋住下一句。
            self.task_list.append(
                asyncio.create_task(
                    self._send_picked_silent_payload(
                        pick,
                        live2d_model,
                        display_text,
                        actions,
                        current_sequence,
                        subtitle_text,
                        silenced,
                    )
                )
            )
            return

        logger.debug(
            f"🏃Queuing TTS task for: '''{tts_text}''' (by {display_text.name})"
        )

        # Get current sequence number
        current_sequence = self._sequence_counter
        self._sequence_counter += 1

        # Start sender task if not running
        if not self._sender_task or self._sender_task.done():
            self._sender_task = asyncio.create_task(
                self._process_payload_queue(websocket_send)
            )

        # Create and queue the TTS task
        task = asyncio.create_task(
            self._process_tts(
                tts_text=tts_text,
                display_text=display_text,
                actions=actions,
                live2d_model=live2d_model,
                tts_engine=tts_engine,
                sequence_number=current_sequence,
                subtitle_text=subtitle_text,
                spoken_text=spoken_text,
                **({"pick": pick} if pick is not None else {}),
            )
        )
        self.task_list.append(task)

    async def _process_payload_queue(self, websocket_send: WebSocketSend) -> None:
        """
        Process and send payloads in correct order.
        Runs continuously until all payloads are processed.
        """
        buffered_payloads: Dict[int, List[Dict]] = {}

        while True:
            try:
                # Get this sentence's messages from queue
                messages, sequence_number = await self._payload_queue.get()
                buffered_payloads[sequence_number] = messages

                # Send payloads in order
                while self._next_sequence_to_send in buffered_payloads:
                    for message in buffered_payloads.pop(self._next_sequence_to_send):
                        await websocket_send(json.dumps(message))
                        seconds = _seconds_of(message)
                        if seconds:
                            now = asyncio.get_running_loop().time()
                            self._play_until = max(now, self._play_until) + seconds
                    self._next_sequence_to_send += 1
                    async with self._sent:
                        self._sent.notify_all()

                self._payload_queue.task_done()

            except asyncio.CancelledError:
                break

    async def _send_silent_payload(
        self,
        display_text: DisplayText,
        actions: Optional[Actions],
        sequence_number: int,
        subtitle_text: Optional[str] = None,
        silenced: bool = False,
    ) -> None:
        """Queue a silent audio payload"""
        audio_payload = prepare_audio_payload(
            audio_path=None,
            display_text=display_text,
            actions=actions,
            subtitle_text=subtitle_text,
        )
        _mark_subtitle_hold(audio_payload, display_text, subtitle_text)
        if silenced:
            # 只有這種句子才標；其他靜音 payload 跟以前逐 byte 相同。
            audio_payload["show_subtitle"] = True
        await self._payload_queue.put(([audio_payload], sequence_number))

    async def _send_picked_silent_payload(
        self,
        pick: Pick,
        live2d_model: AvatarModel,
        display_text: DisplayText,
        actions: Optional[Actions],
        sequence_number: int,
        subtitle_text: Optional[str],
        silenced: bool,
    ) -> None:
        picking = asyncio.create_task(pick())
        actions = apply_pick(
            actions,
            await self._wait_for_pick(picking, sequence_number, SILENT_GRACE_SECONDS),
            live2d_model,
        )
        await self._send_silent_payload(
            display_text, actions, sequence_number, subtitle_text, silenced
        )

    async def _wait_for_pick(
        self, picking: asyncio.Task, sequence_number: int, grace: float
    ) -> Optional[dict]:
        """這句的挑選結果；等不到就取消（排在後面的句子才挑得到）、回 None。

        至少等 ``grace`` 秒。前面的句子都送出了、還在念的話，等到它們念完前
        LEAD_SECONDS：這句反正要等前面念完才輪到。前面還沒送出時，這句也送不
        出去，就一直等到輪到它（前面的句子各自有期限，不會卡住）。
        """
        loop = asyncio.get_running_loop()
        ready = loop.time()
        try:
            while not picking.done():
                if self._next_sequence_to_send >= sequence_number:
                    deadline = max(ready + grace, self._play_until - LEAD_SECONDS)
                    remaining = deadline - loop.time()
                    if remaining > 0:
                        await asyncio.wait({picking}, timeout=remaining)
                    break
                turn = asyncio.ensure_future(
                    self._until_sent_past(self._next_sequence_to_send)
                )
                try:
                    await asyncio.wait(
                        {picking, turn}, return_when=asyncio.FIRST_COMPLETED
                    )
                finally:
                    turn.cancel()
        except BaseException:
            picking.cancel()
            raise
        if not picking.done():
            picking.cancel()
            return None
        if picking.cancelled() or picking.exception() is not None:
            return None
        return picking.result()

    async def _until_sent_past(self, seen: int) -> None:
        async with self._sent:
            await self._sent.wait_for(lambda: self._next_sequence_to_send != seen)

    async def _synthesize(
        self, tts_engine: TTSInterface, tts_text: str, emotion: Optional[str]
    ) -> Tuple[Optional[str], Optional[Exception]]:
        async with self._synthesis_semaphore:
            return await self._synthesize_with_retry(
                tts_engine, tts_text, emotion=emotion
            )

    async def _process_tts(
        self,
        tts_text: str,
        display_text: DisplayText,
        actions: Optional[Actions],
        live2d_model: AvatarModel,
        tts_engine: TTSInterface,
        sequence_number: int,
        subtitle_text: Optional[str] = None,
        spoken_text: Optional[str] = None,
        pick: Optional[Pick] = None,
    ) -> None:
        """Process TTS generation and queue the result for ordered delivery"""
        audio_file_path = None
        failure_notice: Optional[Dict] = None
        try:
            emotion = getattr(actions, "emotion", None)
            if pick is None:
                audio_file_path, error = await self._synthesize(
                    tts_engine, tts_text, emotion
                )
            else:
                # 挑表情跟合成同時跑；合成好了，挑選再等一下（見 _wait_for_pick）。
                picking = asyncio.create_task(pick())
                try:
                    audio_file_path, error = await self._synthesize(
                        tts_engine, tts_text, emotion
                    )
                except BaseException:
                    picking.cancel()
                    raise
                actions = apply_pick(
                    actions,
                    await self._wait_for_pick(picking, sequence_number, GRACE_SECONDS),
                    live2d_model,
                )
            if not audio_file_path:
                logger.error(
                    f"TTS synthesis failed after {self.SYNTHESIS_ATTEMPTS} attempts,"
                    f" sending silent payload: {error!r} text='{tts_text[:30]}'"
                )
                failure_notice = self._synthesis_failed_notice(error)
            # prepare_audio_payload does pydub/ffmpeg decode+re-encode and base64
            # encoding synchronously (utils/stream_audio.py) — non-trivial CPU work
            # per sentence. Keep it off the event loop, same as synthesis itself.
            payload = await asyncio.to_thread(
                prepare_audio_payload,
                audio_path=audio_file_path,
                display_text=display_text,
                actions=actions,
                subtitle_text=subtitle_text,
                spoken_text=spoken_text,
            )
            has_audio = payload.get("audio") is not None
            logger.info(
                f"Audio payload ready: has_audio={has_audio}, text='{tts_text[:30]}'"
            )

        except Exception as e:
            logger.error(f"Error preparing audio payload: {e}")
            # Queue silent payload for error case
            payload = prepare_audio_payload(
                audio_path=None,
                display_text=display_text,
                actions=actions,
                subtitle_text=subtitle_text,
                spoken_text=spoken_text,
            )
            failure_notice = failure_notice or self._synthesis_failed_notice(e)

        finally:
            if audio_file_path:
                tts_engine.remove_file(audio_file_path)
                logger.debug("Audio cache file cleaned.")

        # 靜音 payload 不會換畫面字幕，這句只會出現在聊天泡泡裡；通知跟在同一句
        # 後面，順序不亂。
        # 被 clear() 取消時 CancelledError 會直接穿出去，不會走到這裡。
        _mark_subtitle_hold(payload, display_text, subtitle_text)
        messages = [payload]
        if failure_notice:
            messages.append(failure_notice)
        await self._payload_queue.put((messages, sequence_number))

    async def _synthesize_with_retry(
        self, tts_engine: TTSInterface, text: str, emotion: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Exception]]:
        """合成一句；丟例外或回 None 都算失敗，最多試 SYNTHESIS_ATTEMPTS 次。

        回傳 (檔案路徑, None) 或 (None, 最後一次的例外——回 None 時是 None)。
        CancelledError 不是 Exception，不會被當成失敗重試。
        """
        error: Optional[Exception] = None
        for attempt in range(1, self.SYNTHESIS_ATTEMPTS + 1):
            try:
                audio_file_path = await self._generate_audio(
                    tts_engine, text, emotion=emotion
                )
            except Exception as e:
                audio_file_path, error = None, e
            else:
                if audio_file_path:
                    return audio_file_path, None
                error = None
            if attempt < self.SYNTHESIS_ATTEMPTS:
                reason = repr(error) if error else "engine returned no audio"
                logger.warning(
                    f"TTS synthesis failed ({reason}), retrying"
                    f" ({attempt}/{self.SYNTHESIS_ATTEMPTS}): '{text[:30]}'"
                )
        return None, error

    @staticmethod
    def _synthesis_failed_notice(error: Optional[BaseException]) -> Dict:
        """前端會把 type=error 顯示成 toast；text_key 有翻譯就用翻譯，沒有就顯示 message。"""
        if _is_timeout(error):
            return {
                "type": "error",
                "message": "語音合成失敗（逾時），這句沒有聲音",
                "text_key": "notification.ttsTimedOut",
            }
        return {
            "type": "error",
            "message": "語音合成失敗，這句沒有聲音",
            "text_key": "notification.ttsFailed",
        }

    async def _generate_audio(
        self, tts_engine: TTSInterface, text: str, emotion: Optional[str] = None
    ) -> str:
        """Generate audio file from text.

        emotion 是這則回覆的情緒關鍵字（見 Actions.emotion）。支援的引擎拿它挑
        參考音，其他引擎完全看不到這個參數（見 TTSInterface.supports_emotion）。
        """
        logger.debug(f"🏃Generating audio for '''{text}'''...")
        # 只有宣告支援的引擎才會看到 emotion 這個關鍵字。介面明說子類可以覆寫
        # async_generate_audio（見 TTSInterface），而覆寫版的簽名是舊的兩個參數
        # ——無條件傳下去會打破每一個這樣做的引擎，包括第三方的。
        extra = {}
        if emotion and getattr(tts_engine, "supports_emotion", False):
            extra["emotion"] = emotion
        return await tts_engine.async_generate_audio(
            text=text,
            file_name_no_ext=f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}",
            **extra,
        )

    def clear(self) -> None:
        """Clear all pending tasks and reset state"""
        # Cancel in-flight synthesis tasks instead of just dropping references to
        # them. Previously `task_list.clear()` left them running: they'd still
        # hit GPT-SoVITS and burn a synthesis call whose output was discarded, and
        # since `self._payload_queue` is replaced below, a task that was still
        # awaiting synthesis when clear() was called could go on to `put()` its
        # stale payload into the *new* queue with a sequence number that lines up
        # with the reset `_next_sequence_to_send`, bleeding a previous turn's
        # audio into the new one. Cancelling releases the synthesis semaphore
        # slot promptly (via `async with` unwinding) and, in the common case,
        # interrupts the task before it reaches that `put()`. This does not stop
        # the underlying blocking HTTP call already running in its worker thread
        # (that thread has no cancellation hook), so the wasted GPT-SoVITS request
        # itself isn't prevented — only its consequences are.
        for task in self.task_list:
            if not task.done():
                task.cancel()
        self.task_list.clear()
        if self._sender_task:
            self._sender_task.cancel()
        self._sequence_counter = 0
        self._next_sequence_to_send = 0
        self._play_until = 0.0
        # Create a new queue to clear any pending items
        self._payload_queue = asyncio.Queue()
