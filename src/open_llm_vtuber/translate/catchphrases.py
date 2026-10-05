"""角色口頭禪的確定性處理：不經翻譯模型。

一句話如果只有口頭禪（例如「konpeko！」），答案是確定的：語音照角色設定的
寫法唸、字幕原樣顯示。送去翻譯模型反而會被音譯成「孔佩可」或「コンペコ」。

這個模組不認得任何具體角色；名單由角色設定（CharacterConfig.catchphrases）
提供，鍵是來源寫法、值是語音語言要用的寫法。
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping

_ASCII_ALNUM = re.compile(r"[A-Za-z0-9]")


def _pattern(keys: Iterable[str]) -> re.Pattern | None:
    """所有鍵合成一個不分大小寫的正規表示式，長的先比。

    拉丁字母開頭／結尾的鍵要整個字才算（「pekora」裡的 peko 不算），但旁邊是
    漢字、假名時照樣算——中文句子裡的「要叫konpeko才對」沒有空白。
    """
    alternatives = []
    for key in sorted({k for k in keys if k}, key=len, reverse=True):
        part = re.escape(key)
        if _ASCII_ALNUM.match(key[0]):
            part = r"(?<![A-Za-z0-9])" + part
        if _ASCII_ALNUM.match(key[-1]):
            part = part + r"(?![A-Za-z0-9])"
        alternatives.append(part)
    if not alternatives:
        return None
    return re.compile("|".join(alternatives), re.IGNORECASE)


def _is_filler(char: str) -> bool:
    """標點、符號、空白：拿掉口頭禪之後只剩這些，就算「只有口頭禪」。"""
    return char.isspace() or unicodedata.category(char)[0] in "PSZ"


def only_catchphrases(text: str, keys: Iterable[str]) -> bool:
    """這句話除了口頭禪、標點和空白之外什麼都沒有（而且至少有一個口頭禪）。"""
    pattern = _pattern(keys)
    if pattern is None or not text or not pattern.search(text):
        return False
    rest = pattern.sub("", text)
    return all(_is_filler(char) for char in rest)


def replace_catchphrases(text: str, mapping: Mapping[str, str]) -> str:
    """把句子裡每個口頭禪換成它的目標寫法，其餘（標點、空白）不動。"""
    pattern = _pattern(mapping)
    if pattern is None:
        return text
    by_lower = {key.lower(): value for key, value in mapping.items()}
    return pattern.sub(lambda m: by_lower.get(m.group(0).lower(), m.group(0)), text)
