"""一句話裡「真正的字」——拿掉標點、空白、箭頭、表情符號這些之後剩下的東西。

laughter.is_laughter_only 用它判斷整句是不是只有笑聲；TTSTaskManager.speak
用它判斷這句有沒有東西可念（沒有就直接走靜音，不送去合成）。
"""

import re
import unicodedata

# *動作* 與 (*動作*) 是演出描述，不念出來（GPT-SoVITS 也會把它們濾掉，濾完是
# 空字串就回 400）。
_ACTION_TEXT = re.compile(r"\(\*[^)]*\)|\*[^*]+\*")


def letters_only(text: str) -> str:
    """NFKC 統一全形／半形後，去掉 Unicode 類別 P／S／Z／C（標點、符號含箭頭
    與表情符號、空白、控制字元），只留字母、文字與數字。"""
    normalized = unicodedata.normalize("NFKC", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch)[0] not in "PSZC")


def has_speakable_text(text: str) -> bool:
    """拿掉 *動作* 之後還有字母／文字／數字可念。"""
    return bool(letters_only(_ACTION_TEXT.sub("", text or "")))
