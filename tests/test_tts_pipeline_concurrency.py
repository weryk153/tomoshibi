"""Concurrency properties of the TTS pipeline fix.

Root cause (verified, not re-derived here): conversation_utils.py used to call
translate_engine.translate() synchronously on the event loop thread, and every
translator implementation is a blocking httpx/requests call. That serialized
the whole pipeline. The fix moves translation off-thread (asyncio.to_thread),
caps TTS synthesis concurrency with a semaphore (GPT-SoVITS is a single local
service that queues internally -- flooding it makes things worse, not
better), and moves the pydub/ffmpeg + base64 work in prepare_audio_payload
off-thread too.

These tests exist to prove properties, not just "code runs":
  1. Sentences whose synthesis completes OUT of dispatch order must still be
     emitted to the websocket IN dispatch (sequence) order.
  2. The synthesis semaphore must genuinely cap in-flight synthesis calls --
     not just "usually" stay low.
  3. A translator that raises must not hang the pipeline or corrupt ordering
     of sentences already dispatched.
  4. The blocking translate() call must actually be off the event loop: other
     coroutines must keep making progress while a "slow" translate runs.

Fakes only -- never call the real GPT-SoVITS service or LM Studio.
"""

import asyncio
import time

import pytest

from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.conversations.conversation_utils import (
    handle_sentence_output,
)
from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager
from src.open_llm_vtuber.tts.tts_interface import TTSInterface


class _FakeTTSEngine(TTSInterface):
    """Fake synth engine whose async_generate_audio is directly controllable.

    The semaphore added to TTSTaskManager wraps the call to
    ``tts_engine.async_generate_audio`` (via ``_generate_audio``), so
    overriding this method -- rather than going through real threads/sleep --
    exercises exactly the seam that changed, deterministically.
    """

    def __init__(self, delays: dict[str, float]) -> None:
        self.delays = delays
        self.active = 0
        self.max_active = 0
        self.started_order: list[str] = []
        self.finished_order: list[str] = []

    def generate_audio(self, text, file_name_no_ext=None):  # pragma: no cover
        raise NotImplementedError("overridden via async_generate_audio in tests")

    async def async_generate_audio(self, text: str, file_name_no_ext=None) -> str:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.started_order.append(text)
        try:
            await asyncio.sleep(self.delays.get(text, 0.0))
        finally:
            self.active -= 1
        self.finished_order.append(text)
        return None  # no real audio file -> prepare_audio_payload takes the silent path


class _RecordingWebsocketSend:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, data: str) -> None:
        import json

        self.messages.append(json.loads(data))


class _FakeSentences:
    """Mimics SentenceOutput's async iteration protocol."""

    def __init__(self, items):
        self._items = items

    async def __aiter__(self):
        for item in self._items:
            yield item


class _EchoTranslateEngine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def translate(self, text: str) -> str:
        self.calls.append(text)
        return f"[T]{text}"


class _TargetedTranslateEngine(_EchoTranslateEngine):
    def __init__(self, target_lang: str) -> None:
        super().__init__()
        self.target_lang = target_lang


class _RaisingTranslateEngine:
    """Translates fine until it hits the configured trigger text, then raises."""

    def __init__(self, trigger: str) -> None:
        self.trigger = trigger
        self.calls: list[str] = []

    def translate(self, text: str) -> str:
        self.calls.append(text)
        if text == self.trigger:
            raise RuntimeError("translate service unavailable")
        return f"[T]{text}"


class _SlowTranslateEngine:
    """A translator whose translate() is a real blocking sleep, like the
    production httpx.post()-based implementations."""

    def __init__(self, delay: float) -> None:
        self.delay = delay

    def translate(self, text: str) -> str:
        time.sleep(self.delay)
        return f"[T]{text}"


async def _drain(tts_manager: TTSTaskManager) -> None:
    """Wait for all dispatched synthesis tasks AND the ordered sender to
    finish flushing them to the websocket."""
    if tts_manager.task_list:
        await asyncio.gather(*tts_manager.task_list)
    await tts_manager._payload_queue.join()


def test_out_of_order_completion_still_emits_in_sequence_order():
    """Sentence 'one' finishes LAST, 'two' finishes FIRST, 'three' in between --
    but the websocket must still see them in dispatch order: one, two, three."""

    async def _run():
        tts_manager = TTSTaskManager()
        tts_engine = _FakeTTSEngine(delays={"one": 0.06, "two": 0.01, "three": 0.03})
        ws_send = _RecordingWebsocketSend()

        for text in ("one", "two", "three"):
            await tts_manager.speak(
                tts_text=text,
                display_text=DisplayText(text=text),
                actions=None,
                live2d_model=None,
                tts_engine=tts_engine,
                websocket_send=ws_send,
            )

        await _drain(tts_manager)

        # Sanity: completion really was out of order (proves the test is
        # actually exercising the race, not vacuously passing).
        assert tts_engine.finished_order == ["two", "three", "one"]

        emitted = [m["display_text"]["text"] for m in ws_send.messages]
        assert emitted == ["one", "two", "three"]

    asyncio.run(_run())


def test_semaphore_caps_in_flight_synthesis():
    """5 sentences dispatched together must never exceed SYNTHESIS_CONCURRENCY
    simultaneous synthesis calls, and the cap must actually be reached (not
    just "happen to stay low")."""

    async def _run():
        tts_manager = TTSTaskManager()
        texts = [f"s{i}" for i in range(5)]
        tts_engine = _FakeTTSEngine(delays={t: 0.05 for t in texts})
        ws_send = _RecordingWebsocketSend()

        for text in texts:
            await tts_manager.speak(
                tts_text=text,
                display_text=DisplayText(text=text),
                actions=None,
                live2d_model=None,
                tts_engine=tts_engine,
                websocket_send=ws_send,
            )

        await _drain(tts_manager)

        assert tts_engine.max_active == TTSTaskManager.SYNTHESIS_CONCURRENCY
        assert tts_engine.max_active <= TTSTaskManager.SYNTHESIS_CONCURRENCY

    asyncio.run(_run())


def test_raising_translator_does_not_hang_and_keeps_prior_ordering():
    """Sentence 0 translates fine and must reach speak() before sentence 1's
    translate() raises. The call must fail promptly (not hang) and must not
    dispatch anything for the failing sentence or beyond."""

    async def _run():
        tts_manager = TTSTaskManager()
        tts_engine = _FakeTTSEngine(delays={})
        ws_send = _RecordingWebsocketSend()
        translate_engine = _RaisingTranslateEngine(trigger="boom trigger")

        sentences = _FakeSentences(
            [
                (DisplayText(text="Hello world"), "Hello world", Actions()),
                (DisplayText(text="boom trigger"), "boom trigger", Actions()),
            ]
        )

        with pytest.raises(RuntimeError, match="translate service unavailable"):
            await asyncio.wait_for(
                handle_sentence_output(
                    sentences,
                    live2d_model=None,
                    tts_engine=tts_engine,
                    websocket_send=ws_send,
                    tts_manager=tts_manager,
                    translate_engine=translate_engine,
                    subtitle_translate_engine=None,
                    voice_lang="ja",  # differs from detected 'en' -> gate fires
                ),
                timeout=2.0,
            )

        # Only the first sentence made it to speak(); ordering of what DID
        # get dispatched is intact.
        assert len(tts_manager.task_list) == 1
        await _drain(tts_manager)
        assert [m["display_text"]["text"] for m in ws_send.messages] == ["Hello world"]

    asyncio.run(_run())


def test_translate_call_does_not_block_the_event_loop():
    """A slow (blocking-sleep) translator must not stall other coroutines.
    This is the direct proof that translate() runs in a worker thread."""

    async def _run():
        tts_manager = TTSTaskManager()
        tts_engine = _FakeTTSEngine(delays={})
        ws_send = _RecordingWebsocketSend()
        translate_engine = _SlowTranslateEngine(delay=0.3)

        heartbeat_count = 0
        stop = False

        async def heartbeat():
            nonlocal heartbeat_count
            while not stop:
                heartbeat_count += 1
                await asyncio.sleep(0.01)

        hb_task = asyncio.create_task(heartbeat())

        sentences = _FakeSentences([(DisplayText(text="Hello"), "Hello", Actions())])
        await handle_sentence_output(
            sentences,
            live2d_model=None,
            tts_engine=tts_engine,
            websocket_send=ws_send,
            tts_manager=tts_manager,
            translate_engine=translate_engine,
            subtitle_translate_engine=None,
            voice_lang="ja",
        )

        stop = True
        await hb_task

        # If translate() were blocking the loop for its full 0.3s, the
        # heartbeat (tick every 0.01s) would barely have run at all.
        assert heartbeat_count >= 15

    asyncio.run(_run())


def test_translate_engine_is_awaited_in_sentence_order():
    """Even off-thread, translate() calls must still happen (and thus
    speak() must still be invoked) in strict sentence order -- to_thread must
    be awaited per sentence, not fired-and-forgotten."""

    async def _run():
        tts_manager = TTSTaskManager()
        tts_engine = _FakeTTSEngine(delays={})
        ws_send = _RecordingWebsocketSend()
        translate_engine = _EchoTranslateEngine()

        sentences = _FakeSentences(
            [
                (DisplayText(text="alpha"), "alpha", Actions()),
                (DisplayText(text="beta"), "beta", Actions()),
                (DisplayText(text="gamma"), "gamma", Actions()),
            ]
        )
        await handle_sentence_output(
            sentences,
            live2d_model=None,
            tts_engine=tts_engine,
            websocket_send=ws_send,
            tts_manager=tts_manager,
            translate_engine=translate_engine,
            subtitle_translate_engine=None,
            voice_lang="ja",
        )

        assert translate_engine.calls == ["alpha", "beta", "gamma"]

        await _drain(tts_manager)
        assert [m["display_text"]["text"] for m in ws_send.messages] == [
            "alpha",
            "beta",
            "gamma",
        ]

    asyncio.run(_run())


def test_subtitle_translation_skips_text_already_in_the_target_language():
    async def _run():
        tts_manager = TTSTaskManager()
        tts_engine = _FakeTTSEngine(delays={})
        ws_send = _RecordingWebsocketSend()
        translator = _TargetedTranslateEngine("中文")
        subtitle_parts = []
        sentences = _FakeSentences(
            [(DisplayText(text="已經是中文"), "已經是中文", Actions())]
        )

        await handle_sentence_output(
            sentences,
            live2d_model=None,
            tts_engine=tts_engine,
            websocket_send=ws_send,
            tts_manager=tts_manager,
            subtitle_translate_engine=translator,
            voice_lang="zh",
            subtitle_collector=subtitle_parts,
        )
        await _drain(tts_manager)

        assert translator.calls == []
        assert ws_send.messages[0]["subtitle_text"] == "已經是中文"
        assert subtitle_parts == ["已經是中文"]

    asyncio.run(_run())


def test_subtitle_translation_runs_when_reply_language_differs():
    async def _run():
        tts_manager = TTSTaskManager()
        tts_engine = _FakeTTSEngine(delays={})
        ws_send = _RecordingWebsocketSend()
        translator = _TargetedTranslateEngine("中文")
        subtitle_parts = []
        sentences = _FakeSentences(
            [(DisplayText(text="これは日本語です"), "これは日本語です", Actions())]
        )

        await handle_sentence_output(
            sentences,
            live2d_model=None,
            tts_engine=tts_engine,
            websocket_send=ws_send,
            tts_manager=tts_manager,
            subtitle_translate_engine=translator,
            voice_lang="ja",
            subtitle_collector=subtitle_parts,
        )
        await _drain(tts_manager)

        assert translator.calls == ["これは日本語です"]
        assert ws_send.messages[0]["subtitle_text"] == "[T]これは日本語です"
        assert subtitle_parts == ["[T]これは日本語です"]

    asyncio.run(_run())
