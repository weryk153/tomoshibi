"""判斷一句話是不是只有笑聲。

斷句器會把「哈↗哈↘哈↗！」這種笑聲切成獨立一句，畫面上就閃一行「哈哈哈！」。
這種句子聲音照播、對話紀錄照記，只是字幕留著上一句（見 TTSTaskManager 的
keep_subtitle）。規則是通用的，不靠角色設定。
"""

import re
import unicodedata

# 拉長音、促音：「あはははっ」「ふふっ」「ははー」裡只是把笑聲拉長或收尾。
# （～、♪、↗ 這類是符號，_letters_only 本來就會拿掉。）
_STRETCHERS = str.maketrans("", "", "ーっッ")

# 每一種笑聲至少兩個音節；一句話可以由好幾段笑聲接起來（「哈哈哈、嘿嘿」）。
_LAUGH_RUN = (
    r"(?:"
    r"[哈呵嘿嘻]{2,}"  # 中文
    r"|[あア]?[はハ]{2,}"  # はは、あはは、ハハ
    r"|[ふフ]{2,}"  # ふふ
    r"|[えエ]?[へヘ]{2,}"  # へへ、えへへ
    r"|w{2,}"  # www（全形ｗ在正規化後也是 w）
    r"|lol+"
    r"|a?(?:ha){2,}h?"  # haha、ahaha、hahah
    r"|(?:he){2,}"  # hehe
    r")"
)
_LAUGHTER_ONLY = re.compile(rf"{_LAUGH_RUN}+")


def _letters_only(text: str) -> str:
    """去掉標點、空白、箭頭與其他符號，只留字。全形／半形先統一。"""
    normalized = unicodedata.normalize("NFKC", text).lower().translate(_STRETCHERS)
    return "".join(ch for ch in normalized if unicodedata.category(ch)[0] not in "PSZC")


def is_laughter_only(text: str) -> bool:
    """整句拿掉標點符號後只剩笑聲（哈哈、ふふ、www、lol、haha…）。"""
    letters = _letters_only(text or "")
    return bool(letters) and _LAUGHTER_ONLY.fullmatch(letters) is not None
