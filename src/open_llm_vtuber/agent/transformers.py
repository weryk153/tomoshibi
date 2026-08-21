from typing import AsyncIterator, Tuple, Callable, List, Union, Dict, Any
from functools import wraps
from .output_types import Actions, SentenceOutput, DisplayText
from ..utils.tts_preprocessor import tts_filter as filter_text
from ..utils.tts_preprocessor import TTSFilterState
from ..live2d_model import Live2dModel
from ..config_manager import TTSPreprocessorConfig
from ..utils.sentence_divider import SentenceDivider
from ..utils.sentence_divider import SentenceWithTags, TagState
from ..stage_director import extract_stage_performance
from loguru import logger
import re


def sentence_divider(
    faster_first_response: bool = True,
    segment_method: str = "pysbd",
    valid_tags: List[str] = None,
):
    """
    Decorator that transforms token stream into sentences with tags

    Args:
        faster_first_response: bool - Whether to enable faster first response
        segment_method: str - Method for sentence segmentation
        valid_tags: List[str] - List of valid tags to process
    """

    def decorator(
        func: Callable[
            ..., AsyncIterator[Union[str, Dict[str, Any]]]
        ],  # Expects str or dict
    ) -> Callable[
        ..., AsyncIterator[Union[SentenceWithTags, Dict[str, Any]]]
    ]:  # Yields SentenceWithTags or dict
        @wraps(func)
        async def wrapper(
            *args, **kwargs
        ) -> AsyncIterator[Union[SentenceWithTags, Dict[str, Any]]]:
            divider = SentenceDivider(
                faster_first_response=faster_first_response,
                segment_method=segment_method,
                valid_tags=valid_tags or [],
            )
            stream_from_func = func(*args, **kwargs)

            # Process the mixed stream using the updated SentenceDivider
            async for item in divider.process_stream(stream_from_func):
                if isinstance(item, SentenceWithTags):
                    logger.debug(f"sentence_divider yielding sentence: {item}")
                elif isinstance(item, dict):
                    logger.debug(f"sentence_divider yielding dict: {item}")
                yield item  # Yield either SentenceWithTags or dict
            # Flushing is handled within divider.process_stream

        return wrapper

    return decorator


def actions_extractor(live2d_model: Live2dModel):
    """
    Decorator that extracts actions from sentences, passing through dicts.
    """

    def decorator(
        func: Callable[
            ..., AsyncIterator[Union[SentenceWithTags, Dict[str, Any]]]
        ],  # Input type hint
    ) -> Callable[
        ..., AsyncIterator[Union[Tuple[SentenceWithTags, Actions], Dict[str, Any]]]
    ]:  # Output type hint
        @wraps(func)
        async def wrapper(
            *args, **kwargs
        ) -> AsyncIterator[
            Union[Tuple[SentenceWithTags, Actions], Dict[str, Any]]
        ]:  # Yield type hint
            stream = func(*args, **kwargs)
            async for item in stream:
                if isinstance(item, SentenceWithTags):
                    sentence = item
                    actions = Actions()
                    stage_performance = extract_stage_performance(
                        sentence.text,
                        getattr(live2d_model, "stage_performance_ids", set()),
                    )
                    if stage_performance:
                        actions.stage_performance = stage_performance
                    # Only extract emotions for non-tag text
                    if not any(
                        tag.state in [TagState.START, TagState.END]
                        for tag in sentence.tags
                    ):
                        expressions = live2d_model.extract_emotion(sentence.text)
                        if expressions:
                            actions.expressions = expressions
                        motions = live2d_model.extract_motions(sentence.text)
                        if motions:
                            actions.motions = motions
                    yield sentence, actions  # Yield the tuple
                elif isinstance(item, dict):
                    # Pass through dictionaries
                    yield item
                else:
                    logger.warning(
                        f"actions_extractor received unexpected type: {type(item)}"
                    )

        return wrapper

    return decorator


def balance_asterisk_actions(text: str, inside: bool) -> tuple[str, bool]:
    """把被斷句器切斷的星號動作描述補成每句自己平衡，並跨句保持狀態。

    回傳 (補好的文字, 下一句開始時是否仍在星號區間內)。

    動作描述照原樣用星號顯示——TTS 那側的 ignore_asterisks 本來就會濾掉它們
    （filter_asterisks 也有自己的跨句狀態），所以不需要改寫成別的符號。這裡只
    處理「星號對被切斷」造成的顯示問題。

    為什麼會被切斷：斷句器在句末標點切開，而標點常常就落在星號對的中間。
    實際發生過的例子——模型寫了

        *視線落在螢幕上，盯著你臉上那雙鏡框，還有……那個位置好像有東西？*

    在 `？` 被切成兩段，第一段只有開頭的星號、第二段只剩收尾那一個。第二段那個
    孤零零的星號被黏到下一句前面，字幕上就是一個沒有來由的 `*`（日誌裡那次字幕
    翻譯的輸入原文就是 `'*\n\n……哈，你沒在開玩笑吧。'`）。

    補平衡之後第一段是完整的 `*...*`、第二段的孤星被消掉，兩段都能各自被
    filter_asterisks 正確處理，畫面上也不會再出現落單的星號。
    """
    out: list[str] = []
    if inside:
        # 上一句結束時還在星號區間內——這一句是同一段動作的延續，補一個開頭。
        out.append("*")
    for ch in text:
        out.append(ch)
        if ch == "*":
            inside = not inside
    if inside:
        # 這一句結束時仍在區間內。先分辨兩種完全不同的情況——差別在那個開頭
        # 星號後面「有沒有內容」：
        #
        #   有內容 → 動作被斷句器切斷，這是真的動作開頭。補收尾讓這句自己
        #            平衡，狀態留給下一句接續。
        #   沒內容 → 模型自己吐了一個落單的星號（當成分隔線或強調符號用）。
        #            它不是動作的開頭，狀態不能延續。
        #
        # 沒有這個分辨的話，落單星號會把 inside 帶到下一句，下一句整段真正的
        # 台詞就被補成 `*…台詞…*`——畫面上多兩個星號事小，TTS 的
        # ignore_asterisks 會把整句當動作濾掉，**那句話完全不會被唸出來**，
        # 而且畫面上沒有任何錯誤訊息。
        partial = "".join(out)
        opener = partial.rfind("*")
        if partial[opener + 1:].strip() == "":
            out = list(partial[:opener])
            inside = False
        else:
            out.append("*")
    result = "".join(out)
    # 收尾星號被切到下一句開頭時，上面會補出一對只包住空白的星號。
    result = re.sub(r"\*\s*\*", "", result)
    return result, inside


def display_processor():
    """
    Decorator that processes text for display, passing through dicts.
    """

    def decorator(
        func: Callable[
            ..., AsyncIterator[Union[Tuple[SentenceWithTags, Actions], Dict[str, Any]]]
        ],  # Input type hint
    ) -> Callable[
        ...,
        AsyncIterator[
            Union[Tuple[SentenceWithTags, DisplayText, Actions], Dict[str, Any]]
        ],
    ]:  # Output type hint
        @wraps(func)
        async def wrapper(
            *args, **kwargs
        ) -> AsyncIterator[
            Union[Tuple[SentenceWithTags, DisplayText, Actions], Dict[str, Any]]
        ]:  # Yield type hint
            stream = func(*args, **kwargs)
            # 每次呼叫（＝每則回覆）都是新的，理由同 tts_filter 的 filter_state：
            # 一則回覆結尾沒收掉的星號不能滲進下一則的開頭。
            inside_asterisk = False

            async for item in stream:
                if (
                    isinstance(item, tuple)
                    and len(item) == 2
                    and isinstance(item[0], SentenceWithTags)
                ):
                    sentence, actions = item
                    text = sentence.text
                    # Handle think tag states
                    for tag in sentence.tags:
                        if tag.name == "think":
                            if tag.state == TagState.START:
                                text = "("
                            elif tag.state == TagState.END:
                                text = ")"

                    # 去掉 [neutral]/[smirk] 等情緒標籤（表情已被 actions_extractor 提取，這裡只清字幕顯示）
                    text = re.sub(r"\[[^\]]*\]", "", text).strip()

                    # 動作描述維持星號原樣顯示——TTS 的 ignore_asterisks 本來
                    # 就會濾掉星號包住的內容，不會唸出來。這裡只補平衡，處理
                    # 星號對被斷句器切斷的情況（見 balance_asterisk_actions）。
                    text, inside_asterisk = balance_asterisk_actions(
                        text, inside_asterisk
                    )
                    text = text.strip()
                    display = DisplayText(text=text)  # Simplified DisplayText creation
                    yield sentence, display, actions  # Yield the tuple
                elif isinstance(item, dict):
                    # Pass through dictionaries
                    yield item
                else:
                    logger.warning(
                        f"display_processor received unexpected type: {type(item)}"
                    )

        return wrapper

    return decorator


def tts_filter(
    tts_preprocessor_config: TTSPreprocessorConfig = None,
):
    """
    Decorator that filters text for TTS, passing through dicts.
    Skips TTS for think tag content.
    """

    def decorator(
        func: Callable[
            ...,
            AsyncIterator[
                Union[Tuple[SentenceWithTags, DisplayText, Actions], Dict[str, Any]]
            ],
        ],  # Input type hint
    ) -> Callable[
        ..., AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]
    ]:  # Output type hint
        @wraps(func)
        async def wrapper(
            *args, **kwargs
        ) -> AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]:  # Yield type hint
            stream = func(*args, **kwargs)
            config = tts_preprocessor_config or TTSPreprocessorConfig()
            # Fresh per invocation of this generator (i.e. fresh per streamed
            # response - see basic_memory_agent.py / letta_agent.py, which
            # call the decorated `chat` function once per turn). This is
            # what guarantees an unterminated marker (e.g. an unclosed
            # asterisk) at the end of one response can never leak into and
            # swallow the start of the next one.
            filter_state = TTSFilterState()

            async for item in stream:
                if (
                    isinstance(item, tuple)
                    and len(item) == 3
                    and isinstance(item[1], DisplayText)
                ):
                    sentence, display, actions = item
                    if any(tag.name == "think" for tag in sentence.tags):
                        tts = ""
                    else:
                        tts = filter_text(
                            text=display.text,
                            remove_special_char=config.remove_special_char,
                            ignore_brackets=config.ignore_brackets,
                            ignore_parentheses=config.ignore_parentheses,
                            ignore_asterisks=config.ignore_asterisks,
                            ignore_angle_brackets=config.ignore_angle_brackets,
                            state=filter_state,
                        )

                    logger.debug(f"[{display.name}] display: {display.text}")
                    logger.debug(f"[{display.name}] tts: {tts}")

                    yield SentenceOutput(
                        display_text=display,
                        tts_text=tts,
                        actions=actions,
                    )
                elif isinstance(item, dict):
                    # Pass through dictionaries
                    yield item
                else:
                    logger.warning(f"tts_filter received unexpected type: {type(item)}")

        return wrapper

    return decorator
