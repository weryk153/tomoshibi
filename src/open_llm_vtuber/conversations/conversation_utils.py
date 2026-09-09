import asyncio
import re
from typing import Optional, Union, Any, List, Dict
import numpy as np
import json
from loguru import logger

from ..message_handler import message_handler
from .types import WebSocketSend, BroadcastContext
from .tts_manager import TTSTaskManager
from ..agent.output_types import SentenceOutput, AudioOutput
from ..agent.input_types import BatchInput, TextData, ImageData, TextSource, ImageSource
from ..asr.asr_interface import ASRInterface
from ..avatar_model import AvatarModel
from ..tts.tts_interface import TTSInterface
from ..utils.stream_audio import prepare_audio_payload


# 等前端回報播放完成的上限。這是防卡死的最後一道防線，不是正常節奏的一部分：
# 正常情況下前端播完就回報，長度由這輪語音多長決定。取值要遠大於任何一輪語音的
# 實際長度，否則會在她還在講話時就送出 conversation-chain-end（前端會轉回 idle，
# 可能在句子中間觸發主動發言）。五分鐘足以涵蓋現實中的長回覆，同時保證卡住的
# 連線最多五分鐘就會自己恢復，而不是整個 session 報廢。
PLAYBACK_COMPLETE_TIMEOUT = 300.0

# 認得的語言。不在這個集合裡的一律當「不知道」——不知道就不翻譯、原文唸出去，
# 那是保守的預設。
_KNOWN_LANGS = {"ja", "zh", "en", "ko"}

# 判斷一句話是什麼語言。純正規表示式——不連網、不載模型，所以放在每一句都會
# 經過的熱路徑上也沒問題。
#
# **順序有意義**：先看假名（有假名就是日文），再看韓文字母，然後才是漢字，
# 最後才是拉丁字母。日文句子裡有漢字，反過來檢查會把日文判成中文。
_RE_KANA = re.compile(r"[぀-ゟ゠-ヿ]")  # Hiragana + Katakana
_RE_HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")  # Hangul
_RE_HAN = re.compile(r"[一-鿿㐀-䶿]")  # CJK Han (treat as Chinese)
_RE_LATIN = re.compile(r"[A-Za-z]")


def _detect_lang(text: str) -> Optional[str]:
    """粗略判斷一句話是什麼語言。

    認不出來（純標點、純數字）就回 None，呼叫端把 None 當成「不要做語言判斷」。

    **已知的限制**：一句全是漢字、一個假名都沒有的日文，會被判成中文。用正規
    表示式做不到更好，而代價只是那句話不會被翻譯——可以接受。
    """
    if not text:
        return None
    if _RE_KANA.search(text):
        return "ja"
    if _RE_HANGUL.search(text):
        return "ko"
    if _RE_HAN.search(text):
        return "zh"
    if _RE_LATIN.search(text):
        return "en"
    return None


def _normalize_lang(raw: Optional[str]) -> Optional[str]:
    """Normalize a raw engine language string to a known bucket {'ja','zh','en','ko'}.

    Handles GPT-SoVITS style tags ('all_ja' / 'all_zh' / 'all_ko' / 'yue' / 'auto' /
    'auto_yue') as well as plain codes ('ja' / 'zh' / 'en' / 'ko'). 'yue' (Cantonese)
    maps to 'zh'; 'auto'/'auto_yue' map to None (engine auto-detects -> don't gate).
    Returns None when nothing recognizable is found.
    """
    if not raw:
        return None
    s = str(raw).strip().lower()
    if any(name in s for name in ("日文", "日本語", "japanese")):
        return "ja"
    if any(
        name in s
        for name in ("中文", "繁體", "繁体", "簡體", "简体", "chinese", "mandarin")
    ):
        return "zh"
    if any(name in s for name in ("韓文", "韩文", "한국어", "korean")):
        return "ko"
    if any(name in s for name in ("英文", "英語", "英语", "english")):
        return "en"
    if s in ("auto", "auto_yue"):
        return None
    if "ja" in s:
        return "ja"
    if "zh" in s or "yue" in s:
        return "zh"
    if "ko" in s:
        return "ko"
    if "en" in s:
        return "en"
    return None


def derive_voice_lang(character_config: Any) -> Optional[str]:
    """Derive the active character's voice language V (one of {'ja','zh','en','ko'}).

    V now comes FROM THE VOICE PACK (the active TTS config), NOT from a per-character
    field — the voice pack already declares the language of the voice it speaks, so that
    is the authoritative source. When a character swaps its voice pack it automatically
    gets the new pack's language (no separate field to keep in sync).

    Resolution: read the active engine from ``character_config.tts_config.tts_model``,
    then read that engine's own language declaration:
    - ``edge_tts``    -> the locale language subtag (part before the FIRST hyphen) of
                         ``tts_config.edge_tts.voice`` (e.g. 'ja-JP-NanamiNeural' -> 'ja',
                         'zh-TW-HsiaoChenNeural' -> 'zh').
    - ``gpt_sovits_tts`` -> ``tts_config.gpt_sovits_tts.text_lang`` (e.g. 'all_ja' -> 'ja',
                         'all_zh' -> 'zh', 'all_ko' -> 'ko'); 'auto'/'auto_yue' -> None.
    - ``x_tts`` -> its ``.language`` field, normalized.

    Everything is clamped to {'ja','zh','en','ko'}. Returns None when V cannot be derived
    (no tts_config / engine has no readable language / unrecognized value). A None V means
    "skip gating" -> speak the reply verbatim, since cross-language voice is the opt-in
    case (an unknown voice should not silently trigger translation).
    """
    try:
        tts_config = getattr(character_config, "tts_config", None)
        if tts_config is None:
            return None

        engine = getattr(tts_config, "tts_model", None)

        # edge_tts: parse the locale subtag off the voice name (KEEP existing logic).
        if engine == "edge_tts":
            edge_tts = getattr(tts_config, "edge_tts", None)
            if edge_tts is None:
                return None
            voice = getattr(edge_tts, "voice", None)
            if not voice:
                return None
            subtag = str(voice).split("-", 1)[0].strip().lower()
            return subtag if subtag in _KNOWN_LANGS else None

        # GPT-SoVITS: read+normalize the declared text language ('all_ja' -> 'ja', etc.).
        if engine == "gpt_sovits_tts":
            gpt_sovits = getattr(tts_config, "gpt_sovits_tts", None)
            if gpt_sovits is None:
                return None
            return _normalize_lang(getattr(gpt_sovits, "text_lang", None))

        # Other engines that expose a plain language field.
        if engine == "x_tts":
            x_tts = getattr(tts_config, "x_tts", None)
            if x_tts is None:
                return None
            return _normalize_lang(getattr(x_tts, "language", None))

        # Unknown / unsupported engine -> can't read a voice language -> skip gating.
        return None
    except Exception as e:
        logger.debug(f"Could not derive voice language: {type(e).__name__}: {e}")
        return None


# Convert class methods to standalone functions
def create_batch_input(
    input_text: str,
    images: Optional[List[Dict[str, Any]]],
    from_name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> BatchInput:
    """Create batch input for agent processing"""
    return BatchInput(
        texts=[
            TextData(source=TextSource.INPUT, content=input_text, from_name=from_name)
        ],
        images=[
            ImageData(
                source=ImageSource(img["source"]),
                data=img["data"],
                mime_type=img["mime_type"],
            )
            for img in (images or [])
        ]
        if images
        else None,
        metadata=metadata,
    )


async def process_agent_output(
    output: Union[AudioOutput, SentenceOutput],
    character_config: Any,
    live2d_model: AvatarModel,
    tts_engine: TTSInterface,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    translate_engine: Optional[Any] = None,
    subtitle_translate_engine: Optional[Any] = None,
    subtitle_collector: Optional[List[str]] = None,
) -> str:
    """把回覆補上角色資訊，必要時翻譯，然後送出去。"""
    # 對話框上顯示的名字。絕不能是空的——前端拿到空值會退回寫死的「AI」，
    # 使用者會看到自己的角色突然叫做 AI。
    output.display_text.name = (
        character_config.character_name or character_config.conf_name
    )
    output.display_text.avatar = character_config.avatar

    # 聲音的語言每則算一次就好，不必逐句算——它只跟角色設定有關。
    # 算不出來就不做語言判斷，原文唸出去。
    voice_lang = derive_voice_lang(character_config)

    full_response = ""
    try:
        if isinstance(output, SentenceOutput):
            full_response = await handle_sentence_output(
                output,
                live2d_model,
                tts_engine,
                websocket_send,
                tts_manager,
                translate_engine,
                subtitle_translate_engine,
                voice_lang,
                subtitle_collector,
            )
        elif isinstance(output, AudioOutput):
            full_response = await handle_audio_output(output, websocket_send)
        else:
            logger.warning(f"Unknown output type: {type(output)}")
    except Exception as e:
        logger.error(f"Error processing agent output: {e}")
        await websocket_send(
            json.dumps(
                {"type": "error", "message": f"Error processing response: {str(e)}"}
            )
        )

    return full_response


async def handle_sentence_output(
    output: SentenceOutput,
    live2d_model: AvatarModel,
    tts_engine: TTSInterface,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    translate_engine: Optional[Any] = None,
    subtitle_translate_engine: Optional[Any] = None,
    voice_lang: Optional[str] = None,
    subtitle_collector: Optional[List[str]] = None,
) -> str:
    """處理一句輸出：需要時翻譯，然後交給語音合成。

    Two INDEPENDENT translations may happen per sentence:
    - AUDIO: ``translate_engine`` rewrites ``tts_text`` for the spoken voice. This is
      now AUTOMATIC (no user toggle): the engine runs ONLY when the character's voice
      language ``voice_lang`` (V) differs from the detected reply language R of the
      sentence. Same-language (e.g. Japanese reply + Japanese voice) -> skip + speak R
      verbatim. When V cannot be derived (None) the gate is skipped (speak verbatim).
      The engine's TARGET is V itself (the character's voice language): it is built in
      service_context.init_translate with target = V (mapped per provider), so when the
      gate fires the reply is translated INTO V. So a character with a Japanese voice
      always speaks Japanese; one with a Chinese voice always speaks Chinese — regardless
      of the reply language. (Falls back to the conf's global target_lang only when V
      can't be derived.) V here only drives the skip/translate DECISION.
    - SUBTITLE (display-only): ``subtitle_translate_engine`` rewrites a SEPARATE
      ``subtitle_text`` for the on-screen subtitle. UNCHANGED: gated only by the user's
      explicit subtitle language pick (built in init_translate). The canonical reply
      text (``display_text.text`` == R) is NEVER mutated, so ``full_response`` — the sole
      source for memory + history — stays on the original reply.
    """
    full_response = ""
    async for display_text, tts_text, actions in output:
        logger.debug(f"🏃 Processing output: '''{tts_text}'''...")

        if translate_engine:
            # 逐句判斷：有實際內容、而且聲音的語言跟這句話的語言不同，才翻譯。
            # 兩者相同時直接唸，省下一次往返。
            if len(re.sub(r'[\s.,!?，。！？\'"』」）】\s]+', "", tts_text)):
                reply_lang = _detect_lang(tts_text)
                if voice_lang and reply_lang and reply_lang != voice_lang:
                    # 翻譯是同步阻塞的（每一個實作都是），直接在事件迴圈上跑
                    # 會把 WebSocket 的送出、語音合成的完成回呼、LLM 串流的讀取
                    # 全部卡住一到四秒。丟到執行緒。
                    #
                    # 但還是在這裡 await：句子必須照順序交給 tts_manager，
                    # 它的排隊機制靠的就是這個順序。
                    tts_text = await asyncio.to_thread(
                        translate_engine.translate, tts_text
                    )
                    logger.info(
                        f"🏃 Audio translated (R={reply_lang} != V={voice_lang}): "
                        f"'''{tts_text}'''..."
                    )
                else:
                    logger.debug(
                        f"🚫 Audio translation skipped (R={reply_lang}, V={voice_lang}); "
                        "speaking reply verbatim."
                    )
        else:
            logger.debug("🚫 No translation engine available. Skipping translation.")

        # 這是正典的回覆文字，記憶與對話紀錄用的就是它。**絕對不能改動。**
        full_response += display_text.text

        # 字幕翻譯只影響畫面：算進另一個欄位，不碰正典文字。沒有字幕引擎時
        # 字幕就等於原文。
        subtitle_text = display_text.text
        if subtitle_translate_engine:
            if len(re.sub(r'[\s.,!?，。！？\'"』」）】\s]+', "", display_text.text)):
                reply_lang = _detect_lang(display_text.text)
                subtitle_lang = _normalize_lang(
                    getattr(subtitle_translate_engine, "target_lang", None)
                )
                if subtitle_lang and reply_lang == subtitle_lang:
                    logger.debug(
                        f"🚫 Subtitle translation skipped "
                        f"(R={reply_lang}, target={subtitle_lang})."
                    )
                else:
                    # Same reasoning as the audio-translate call above: keep the
                    # blocking call off the event loop, but still await it in order.
                    subtitle_text = await asyncio.to_thread(
                        subtitle_translate_engine.translate, display_text.text
                    )
            logger.info(f"🏃 Subtitle after translation: '''{subtitle_text}'''...")

        if subtitle_collector is not None:
            subtitle_collector.append(subtitle_text)

        await tts_manager.speak(
            tts_text=tts_text,
            display_text=display_text,
            actions=actions,
            live2d_model=live2d_model,
            tts_engine=tts_engine,
            websocket_send=websocket_send,
            subtitle_text=subtitle_text,
        )
    return full_response


async def handle_audio_output(
    output: AudioOutput,
    websocket_send: WebSocketSend,
) -> str:
    """Process and send AudioOutput directly to the client"""
    full_response = ""
    async for audio_path, display_text, transcript, actions in output:
        full_response += transcript
        audio_payload = prepare_audio_payload(
            audio_path=audio_path,
            display_text=display_text,
            actions=actions.to_dict() if actions else None,
        )
        await websocket_send(json.dumps(audio_payload))
    return full_response


async def send_conversation_start_signals(websocket_send: WebSocketSend) -> None:
    """Send initial conversation signals"""
    await websocket_send(
        json.dumps(
            {
                "type": "control",
                "text": "conversation-chain-start",
            }
        )
    )
    await websocket_send(
        json.dumps({"type": "full-text", "text": "Thinking...", "text_key": "thinking"})
    )


async def process_user_input(
    user_input: Union[str, np.ndarray],
    asr_engine: ASRInterface,
    websocket_send: WebSocketSend,
) -> str:
    """Process user input, converting audio to text if needed"""
    if isinstance(user_input, np.ndarray):
        if asr_engine is None:
            # Voice input is disabled (no speech engine could be loaded). Don't
            # dereference None — tell the user and let them type instead. Text chat
            # and voice output keep working.
            logger.warning(
                "Received audio input but no ASR engine is loaded; ignoring."
            )
            await websocket_send(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Voice input is unavailable (no speech-recognition engine loaded). Please type your message instead.",
                    }
                )
            )
            return ""
        logger.info("Transcribing audio input...")
        input_text = await asr_engine.async_transcribe_np(user_input)
        await websocket_send(
            json.dumps({"type": "user-input-transcription", "text": input_text})
        )
        return input_text
    return user_input


async def finalize_conversation_turn(
    tts_manager: TTSTaskManager,
    websocket_send: WebSocketSend,
    client_uid: str,
    broadcast_ctx: Optional[BroadcastContext] = None,
) -> None:
    """Finalize a conversation turn"""
    if tts_manager.task_list:
        await asyncio.gather(*tts_manager.task_list)

        # 先掛等待者，再送 backend-synth-complete。反過來的話，前端在播放佇列剛好
        # 是空的情況下會立刻回報播放完成，那則回報落在等待者掛上之前，被直接丟掉，
        # 這一輪就只能耗到逾時。
        message_handler.arm_response(client_uid, "frontend-playback-complete")
        await websocket_send(json.dumps({"type": "backend-synth-complete"}))

        response = await message_handler.wait_for_response(
            client_uid,
            "frontend-playback-complete",
            timeout=PLAYBACK_COMPLETE_TIMEOUT,
        )

        if not response:
            # 逾時不能就這樣 return：那樣 conversation-chain-end 不會送，前端的
            # aiState 永遠停在 thinking-speaking，之後所有依賴 idle 的功能（主動
            # 發言、自動開麥）全部失效，而且畫面上沒有任何線索。回報這一輪沒收到
            # 播放完成，然後照樣把這輪收掉。
            logger.warning(
                f"No playback completion response from {client_uid} within "
                f"{PLAYBACK_COMPLETE_TIMEOUT}s; ending the turn anyway"
            )

    await websocket_send(json.dumps({"type": "force-new-message"}))

    if broadcast_ctx and broadcast_ctx.broadcast_func:
        await broadcast_ctx.broadcast_func(
            broadcast_ctx.group_members,
            {"type": "force-new-message"},
            broadcast_ctx.current_client_uid,
        )

    await send_conversation_end_signal(websocket_send, broadcast_ctx)


async def send_conversation_end_signal(
    websocket_send: WebSocketSend,
    broadcast_ctx: Optional[BroadcastContext],
    session_emoji: str = "😊",
) -> None:
    """Send conversation chain end signal"""
    chain_end_msg = {
        "type": "control",
        "text": "conversation-chain-end",
    }

    await websocket_send(json.dumps(chain_end_msg))

    if broadcast_ctx and broadcast_ctx.broadcast_func and broadcast_ctx.group_members:
        await broadcast_ctx.broadcast_func(
            broadcast_ctx.group_members,
            chain_end_msg,
        )

    logger.info(f"😎👍✅ Conversation Chain {session_emoji} completed!")


def cleanup_conversation(tts_manager: TTSTaskManager, session_emoji: str) -> None:
    """Clean up conversation resources"""
    tts_manager.clear()
    logger.debug(f"🧹 Clearing up conversation {session_emoji}.")


EMOJI_LIST = [
    "🐶",
    "🐱",
    "🐭",
    "🐹",
    "🐰",
    "🦊",
    "🐻",
    "🐼",
    "🐨",
    "🐯",
    "🦁",
    "🐮",
    "🐷",
    "🐸",
    "🐵",
    "🐔",
    "🐧",
    "🐦",
    "🐤",
    "🐣",
    "🐥",
    "🦆",
    "🦅",
    "🦉",
    "🦇",
    "🐺",
    "🐗",
    "🐴",
    "🦄",
    "🐝",
    "🌵",
    "🎄",
    "🌲",
    "🌳",
    "🌴",
    "🌱",
    "🌿",
    "☘️",
    "🍀",
    "🍂",
    "🍁",
    "🍄",
    "🌾",
    "💐",
    "🌹",
    "🌸",
    "🌛",
    "🌍",
    "⭐️",
    "🔥",
    "🌈",
    "🌩",
    "⛄️",
    "🎃",
    "🎄",
    "🎉",
    "🎏",
    "🎗",
    "🀄️",
    "🎭",
    "🎨",
    "🧵",
    "🪡",
    "🧶",
    "🥽",
    "🥼",
    "🦺",
    "👔",
    "👕",
    "👜",
    "👑",
]


def should_skip_history(metadata: Optional[Dict[str, Any]]) -> bool:
    """這一輪要不要略過寫入歷史（主動發言用）。

    單人與群組兩邊本來各寫一份 `metadata and metadata.get("skip_history", False)`。
    抽出來的直接原因是群組那份寫壞了——存檔那段是 for-else，`else` 掛在 for 上，
    迴圈正常跑完就執行，於是一邊存、一邊印「跳過存檔」，而真正的 skip_history
    判斷整個不見了。

    回傳一定是 bool：原本的表達式在 metadata 是 None 時回傳 None，用在 if 沒差，
    拿去比對或序列化就會出事。
    """
    if not metadata:
        return False
    return bool(metadata.get("skip_history", False))
