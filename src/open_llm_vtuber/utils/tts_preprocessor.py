import re
import unicodedata
from dataclasses import dataclass
from typing import Tuple
from loguru import logger
from ..translate.translate_interface import TranslateInterface


@dataclass
class TTSFilterState:
    """
    Tracks marker regions (asterisks, brackets, parentheses, angle brackets)
    that are still open at the end of a TTS text fragment.

    `sentence_divider` splits a reply into fragments on punctuation
    (including commas) before `tts_filter` ever sees the text, so a single
    stage direction like `*歪頭，眼神帶著一絲困惑*` can be cut in half, with each
    half carrying only one side of the marker pair. A stateless filter can
    never match those halves up. This object lets the filter remember, across
    consecutive fragments of the *same* streamed response, that it is still
    "inside" a marker region so it can keep dropping text until the closing
    marker arrives.

    IMPORTANT: a fresh instance must be created for every new response
    stream. Reusing one across responses would let an unterminated marker at
    the end of one reply swallow the start of the next.
    """

    in_asterisk: bool = False
    bracket_depth: int = 0
    paren_depth: int = 0
    angle_depth: int = 0


def tts_filter(
    text: str,
    remove_special_char: bool,
    ignore_brackets: bool,
    ignore_parentheses: bool,
    ignore_asterisks: bool,
    ignore_angle_brackets: bool,
    translator: TranslateInterface | None = None,
    state: TTSFilterState | None = None,
) -> str:
    """
    Filter or do anything to the text before TTS generates the audio.
    Changes here do not affect subtitles or LLM's memory. The generated audio is
    the only affected thing.

    Args:
        text (str): The text to filter.
        remove_special_char (bool): Whether to remove special characters.
        ignore_brackets (bool): Whether to ignore text within brackets.
        ignore_parentheses (bool): Whether to ignore text within parentheses.
        ignore_asterisks (bool): Whether to ignore text within asterisks.
        translator (TranslateInterface, optional):
            The translator to use. If None, we'll skip the translation. Defaults to None.
        state (TTSFilterState, optional):
            Carries open-marker state across fragments of the same streamed
            response (see `TTSFilterState`). If None, a fresh, throwaway
            state is used, matching the old stateless-per-call behavior.

    Returns:
        str: The filtered text.
    """
    if state is None:
        state = TTSFilterState()

    if ignore_asterisks:
        try:
            text = filter_asterisks(text, state)
        except Exception as e:
            logger.warning(f"Error ignoring asterisks: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")

    if ignore_brackets:
        try:
            text = filter_brackets(text, state)
        except Exception as e:
            logger.warning(f"Error ignoring brackets: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if ignore_parentheses:
        try:
            text = filter_parentheses(text, state)
        except Exception as e:
            logger.warning(f"Error ignoring parentheses: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if ignore_angle_brackets:
        try:
            text = filter_angle_brackets(text, state)
        except Exception as e:
            logger.warning(f"Error ignoring angle brackets: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if remove_special_char:
        try:
            text = remove_special_characters(text)
        except Exception as e:
            logger.warning(f"Error removing special characters: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if translator:
        try:
            logger.info("Translating...")
            text = translator.translate(text)
            logger.info(f"Translated: {text}")
        except Exception as e:
            logger.critical(f"Error translating: {e}")
            logger.critical(f"Text: {text}")
            logger.warning("Skipping...")

    logger.debug(f"Filtered text: {text}")
    return text


def remove_special_characters(text: str) -> str:
    """
    Filter text to remove all non-letter, non-number, and non-punctuation characters.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    normalized_text = unicodedata.normalize("NFKC", text)

    def is_valid_char(char: str) -> bool:
        category = unicodedata.category(char)
        return (
            category.startswith("L")
            or category.startswith("N")
            or category.startswith("P")
            or char.isspace()
        )

    filtered_text = "".join(char for char in normalized_text if is_valid_char(char))
    return filtered_text


def _filter_nested(text: str, left: str, right: str, depth: int) -> Tuple[str, int]:
    """
    Generic function to handle nested symbols, carrying nesting `depth` in
    from (and back out to) the caller so a pair split across two calls -
    e.g. two fragments produced by `sentence_divider` - is still matched up.

    Args:
        text (str): The text to filter.
        left (str): The left symbol (e.g. '[' or '(').
        right (str): The right symbol (e.g. ']' or ')').
        depth (int): Nesting depth carried over from the previous fragment
            (0 means "not currently inside a marker region").

    Returns:
        Tuple[str, int]: The filtered text, and the nesting depth left open
        at the end of this fragment.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    if not text:
        return text, depth
    if depth == 0 and left not in text and right not in text:
        # Nothing to filter and nothing left open from a previous fragment -
        # return the text untouched (no whitespace collapsing) so plain text
        # passes through byte-identical.
        return text, depth

    result = []
    for char in text:
        if char == left:
            depth += 1
        elif char == right:
            if depth > 0:
                depth -= 1
        else:
            if depth == 0:
                result.append(char)
    filtered_text = "".join(result)
    filtered_text = re.sub(r"\s+", " ", filtered_text).strip()
    return filtered_text, depth


def filter_brackets(text: str, state: "TTSFilterState") -> str:
    """
    Filter text to remove all text within brackets, handling nested cases
    and cases where a pair straddles two fragments of the same stream.

    Args:
        text (str): The text to filter.
        state (TTSFilterState): Cross-fragment state for the current stream.

    Returns:
        str: The filtered text.
    """
    filtered_text, state.bracket_depth = _filter_nested(
        text, "[", "]", state.bracket_depth
    )
    return filtered_text


def filter_parentheses(text: str, state: "TTSFilterState") -> str:
    """
    Filter text to remove all text within parentheses, handling nested cases
    and cases where a pair straddles two fragments of the same stream.

    Args:
        text (str): The text to filter.
        state (TTSFilterState): Cross-fragment state for the current stream.

    Returns:
        str: The filtered text.
    """
    # 全形括號要一起濾。中文本來就用全形，模型自己就會產出（實測：一輪回覆裡
    # 每個動作描述都是全形括號），而只認半形的話它們會被當成台詞送去翻譯＋
    # 合成——每個多付一次翻譯（實測 3～9 秒）加一次 TTS。
    #
    # 兩種寬度共用同一個深度計數：模型不會在同一段裡混用左右不同寬度，而共用
    # 之後「(前半…」跨片段接上「…後半）」這種情況也還是能收斂。
    filtered_text, state.paren_depth = _filter_nested(text, "(", ")", state.paren_depth)
    filtered_text, state.paren_depth = _filter_nested(
        filtered_text, "（", "）", state.paren_depth
    )
    return filtered_text


def filter_angle_brackets(text: str, state: "TTSFilterState") -> str:
    """
    Filter text to remove all text within angle brackets, handling nested
    cases and cases where a pair straddles two fragments of the same stream.

    Args:
        text (str): The text to filter.
        state (TTSFilterState): Cross-fragment state for the current stream.

    Returns:
        str: The filtered text.
    """
    filtered_text, state.angle_depth = _filter_nested(text, "<", ">", state.angle_depth)
    return filtered_text


def filter_asterisks(text: str, state: "TTSFilterState") -> str:
    """
    Removes text enclosed within asterisks of any length (*, **, ***, etc.)
    from a string, remembering across calls (via `state.in_asterisk`)
    whether an opening asterisk from a previous fragment is still
    unterminated. This matters because `sentence_divider` splits text on
    punctuation - including commas - before this filter runs, so a stage
    direction such as `*歪頭，眼神帶著一絲困惑*` can arrive as two fragments,
    each carrying only one asterisk of the pair.

    Args:
        text: The input string (one fragment of a streamed response).
        state (TTSFilterState): Cross-fragment state for the current stream.

    Returns:
        The string with asterisk-enclosed text removed.
    """
    if not text:
        return text
    if "*" not in text and not state.in_asterisk:
        # Nothing to filter and nothing left open from a previous fragment -
        # return the text untouched (no whitespace collapsing) so plain text
        # passes through byte-identical.
        return text

    # Split into alternating non-asterisk text and runs of one-or-more
    # asterisks. Each asterisk run flips whether we're "inside" a region.
    parts = re.split(r"(\*+)", text)
    output = []
    in_region = state.in_asterisk
    for part in parts:
        if not part:
            continue
        if part.count("*") == len(part):  # a run consisting solely of '*'
            in_region = not in_region
        elif not in_region:
            output.append(part)
    state.in_asterisk = in_region

    filtered_text = "".join(output)
    filtered_text = re.sub(r"\s+", " ", filtered_text).strip()

    return filtered_text
