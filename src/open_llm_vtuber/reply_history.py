"""一般回覆的跨輪記錄，用來擋掉逐字重複的回答。

為什麼需要這個
--------------
single_conversation 每一輪都新建一個 ResponseRepetitionGuard，那個護欄的
docstring 寫得很清楚：「for one response stream」。它比對的是同一則回覆裡的
句子，跨輪看不到任何東西。於是三則不同的使用者訊息可以各自得到逐字相同的
回覆，而系統從頭到尾覺得一切正常。

主動發言那條路（proactive_context）早就有跨輪記錄。這個模組是一般回覆的
對應物，刻意分開放：proactive_context 還帶著 _pending / _since_user 兩份只有
主動發言才有意義的狀態，混在一起會讓兩邊的生命週期糾纏。

比對方式
--------
正規化後「逐字相同」才算重複，不做相似度比對。相似度門檻會誤殺「同一件事換
個說法」——那是正常的回覆，不是故障。先擋住確定錯的那一類。
"""

from collections import OrderedDict, deque
from typing import Deque

from .conversation_quality import is_repetitive_response_segment

# 每個 session 記多少則。夠涵蓋「連續鬼打牆」的範圍，又不會把很久以前講過
# 的話也當成重複——同一句話隔了二十輪再出現，通常是合理的。
MAX_RECENT_REPLIES = 6

# 同時記住多少個 session。超過就淘汰最久沒用到的，避免長時間執行累積。
MAX_SESSIONS = 32

# 當輪上下文裡最多列幾則。列太多會把提示詞灌爆，也會把「不要重複」稀釋成
# 一片背景噪音；模型對結尾最敏感，少而近的幾則比較有效。
MAX_GUIDANCE_LINES = 3

# 累積到幾個字才開始用相似度判斷「還可能是重複嗎」。角色常有固定的起手式
# （「……是嗎？」），太短就比對的話每一輪的第一句都會被緩衝，零延遲的前提
# 就沒了。這個門檻以下改用嚴格的逐字開頭比對。
MIN_CHARS_FOR_SIMILARITY = 20

_recent_by_session: "OrderedDict[tuple[str, str], Deque[str]]" = OrderedDict()


def _session_key(conf_uid: str, client_uid: str) -> tuple[str, str]:
    return (str(conf_uid or ""), str(client_uid or ""))


def _normalize(text: str) -> str:
    """壓掉空白差異。串流拼出來的文字，空白與換行位置會漂移。"""
    return " ".join(str(text or "").split())


def _touch(key: tuple[str, str]) -> None:
    if key in _recent_by_session:
        _recent_by_session.move_to_end(key)
    while len(_recent_by_session) > MAX_SESSIONS:
        _recent_by_session.popitem(last=False)


def record_reply(conf_uid: str, client_uid: str, response: str) -> None:
    """記下一則已經說出口的回覆。"""
    normalized = _normalize(response)
    if not normalized:
        return
    key = _session_key(conf_uid, client_uid)
    recent = _recent_by_session.setdefault(key, deque(maxlen=MAX_RECENT_REPLIES))
    recent.append(normalized)
    _touch(key)


def is_repeat_of_recent(conf_uid: str, client_uid: str, response: str) -> bool:
    """這則回覆是不是在重複最近說過的其中一則。

    用的是 conversation_quality 既有的相似度判斷，不是逐字相同。原本寫成逐字，
    理由是「相似度會誤殺同一件事換個說法」——實測打臉了：真實的重複長這樣，
    整句只差「眼神」/「視線」兩個字，逐字比對全部放過，而人一眼就看得出是
    同一句。
    """
    normalized = _normalize(response)
    if not normalized:
        return False
    recent = list(_recent_by_session.get(_session_key(conf_uid, client_uid), ()))
    if not recent:
        return False
    return is_repetitive_response_segment(normalized, recent)


def prefix_matches_recent(conf_uid: str, client_uid: str, partial: str) -> bool:
    """目前累積到的文字，還有沒有可能長成某則最近說過的回覆。

    串流當下用這個決定「先緩衝還是直接放行」。一旦分岔就回 False，那一刻把
    緩衝的內容整批放行——所以沒有重複時延遲是零，只有真的在鬼打牆時才會等。

    空字串回 False：空字串是任何字串的開頭，當成「可能重複」的話每一輪的第一
    句都會被無故緩衝，零延遲的前提就沒了。
    """
    normalized = _normalize(partial)
    if not normalized:
        return False
    recent = list(_recent_by_session.get(_session_key(conf_uid, client_uid), ()))
    if not recent:
        return False

    if len(normalized) < MIN_CHARS_FOR_SIMILARITY:
        # 太短，只認逐字相同的開頭——這時候還沒有足夠的字可以談「相似」。
        #
        # 這裡曾經改成直接不扣住，理由是「角色每輪都用同一句起手，每輪都延遲
        # 不划算」。實測證明那等於把整個機制關掉：句子切分器會在「？」斷句，
        # 第一段常常就是「……是嗎？」五個字，低於門檻就放行，於是之後永遠不再
        # 緩衝，一次都沒攔到。
        #
        # 真正的代價只是延後「一句」的時間，不是整則——下一句馬上就會讓它分岔
        # 或確認重複。
        return any(seen.startswith(normalized) for seen in recent)

    # 夠長了，跟每一則「同樣長度的開頭」比相似度——這樣才擋得住只差兩三個字
    # 的重複，那正是逐字比對放過去的那一種。
    heads = [seen[: len(normalized)] for seen in recent]
    return is_repetitive_response_segment(normalized, heads)


def build_recent_reply_guidance(conf_uid: str, client_uid: str) -> str:
    """組出「你最近說過這些，不要重複」，附在當輪的輸入後面。

    這是預防，不是事後補救。實測顯示：等整則生成完才發現重複、再叫模型重寫，
    在真實的系統提示裡沒有用——那段提示被人設、記憶、表情規則埋掉了。反過來
    在生成之前就把「剛講過什麼」擺在輸入的最後面，是主動發言那條路已經驗證
    有效的做法。

    沒有東西可列就回空字串：第一輪不該憑空多出一段沒有指涉對象的「不要重複」。
    """
    recent = list(_recent_by_session.get(_session_key(conf_uid, client_uid), ()))
    if not recent:
        return ""
    # 只留最近的幾則，且維持由舊到新——最近說過的那句排在最後，離模型最近。
    lines = "\n".join(f"- {item}" for item in recent[-MAX_GUIDANCE_LINES:])
    return f"""

## 你最近說過的話
{lines}
不要重複上面的句子、句型或動作描述。就算立場與情緒不變，也要換一種說法；
如果這個話題已經講不出新東西——尤其連續兩輪都在繞同一件事——那就往前推進
或換一件事說。
"""


def build_reply_retry_prompt(original_prompt: str, repeated: str) -> str:
    """整則回覆跟最近說過的一模一樣時，用這個提示重生一次。

    把重複的那句原文寫進去，而不是只說「不要重複」——模型看不到自己上一輪的
    輸出時，「不要重複」沒有指涉對象。這是主動發言那邊學到的：被擋掉的內容
    正是最需要讓模型知道的內容。
    """
    return f"""{str(original_prompt or "").rstrip()}

## 重新生成
你剛才已經說過這句，一字不差：
「{_normalize(repeated)}」
換一個說法回應對方這一輪的話。可以是同一個立場、同一個情緒，但用不同的句子
與不同的動作描述。只輸出角色說的內容。
"""


class ReplyBuffer:
    """串流當下決定每一句先扣住還是直接放行。

    為什麼要扣住
    ------------
    process_agent_output 在串流迴圈裡就把句子送去 TTS 並推給前端。等整則講完
    才發現是重複已經來不及——那句話早就播出去了，事後再補一則不同的，比原本
    的重複更糟。

    代價是零，只要沒有真的在重複
    ----------------------------
    只有「目前累積到的文字仍然是某則最近回覆的開頭」時才扣住。第一句通常就
    分岔了，那一刻整批放行，聽起來跟沒有這層一樣。真的鬼打牆時才會延遲，而
    那正是我們想攔的情況。
    """

    def __init__(self, conf_uid: str, client_uid: str, enabled: bool = True) -> None:
        self._conf_uid = conf_uid
        self._client_uid = client_uid
        self._buffering = bool(enabled)
        self._held: list = []
        self._held_text_parts: list[str] = []

    @property
    def held_text(self) -> str:
        # 直接相接，不加分隔字元：串流的累積方式就是 full_response += part，
        # 中間插一個空格的話，逐字比對永遠對不上。
        return _normalize("".join(self._held_text_parts))

    @property
    def is_full_repeat(self) -> bool:
        """扣住的內容剛好等於某則最近說過的回覆。"""
        if not self._buffering:
            return False
        return is_repeat_of_recent(self._conf_uid, self._client_uid, self.held_text)

    def offer(self, item, text: str) -> list:
        """交出一句。回傳「現在該送出去」的項目，順序就是原本的順序。"""
        if not self._buffering:
            return [item]

        self._held.append(item)
        self._held_text_parts.append(str(text or ""))

        if prefix_matches_recent(self._conf_uid, self._client_uid, self.held_text):
            return []

        # 分岔了：這一則不可能是重複，把扣住的整批放行，之後不再緩衝。
        self._buffering = False
        released, self._held = self._held, []
        self._held_text_parts = []
        return released

    def flush(self) -> list:
        """串流結束時，還扣在手上、而且該說出口的部分。

        走到這裡代表從頭到尾沒有分岔。如果不是逐字重複（例如這則比較短，剛好
        是舊回覆的開頭），還是要說出來——把它吞掉她就沈默了。
        """
        released, self._held = self._held, []
        self._held_text_parts = []
        return released


def reset_for_tests() -> None:
    """清空模組層的狀態。測試之間不該互相污染。"""
    _recent_by_session.clear()
