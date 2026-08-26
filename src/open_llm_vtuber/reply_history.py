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

狀態的歸屬（history_uid）
--------------------------
最初只用 (conf_uid, client_uid) 當 key，而 client_uid 認的是 WebSocket 連線、
不是對話：使用者在同一條連線裡切換對話（不重新連線）時，這裡的狀態原封不動
跟過去，於是新對話的提示詞裡混進了上一段對話說過的話——這是一次真實的隱私
外洩，不是假設。修法是把 history_uid 併進 key，讓狀態跟著對話走。

history_uid 為空時：不讀、不寫、不回退到只用 conf_uid+client_uid 的舊範圍。
這跟 memory_core 對長期記憶定的規則一樣——「沒有對話就沒有記憶」。這裡刻意
沿用同一條規則，而不是給重複護欄開特例，是因為：兩邊的 key 命名空間本來就
共用同一份「history_uid 是什麼」的心智模型，一旦其中一邊在空值時悄悄回退到
更寬的範圍，維護的人得記住「這裡跟那裡不一樣」，那正是這次外洩的成因（呼叫
端以為狀態是跟著對話走的，實際上不是）。付出的代價很小：history_uid 為空
只發生在連線剛建立、對話還沒建立的短暫窗口，那個當下本來就沒有東西可比對，
護欄晚一輪才生效不痛不癢；換來的是「空值語意全模組一致」，不用逐一稽核每個
呼叫端有沒有踩到那個特例。
"""

from collections import OrderedDict, deque
from typing import Deque

from .conversation_quality import SENTENCE_SPLIT_RE

# 每個 session 記多少則。夠涵蓋「連續鬼打牆」的範圍，又不會把很久以前講過
# 的話也當成重複——同一句話隔了二十輪再出現，通常是合理的。
MAX_RECENT_REPLIES = 6

# 同時記住多少個 session。超過就淘汰最久沒用到的，避免長時間執行累積。
MAX_SESSIONS = 32

# 當輪上下文裡最多列幾則。列太多會把提示詞灌爆，也會把「不要重複」稀釋成
# 一片背景噪音；模型對結尾最敏感，少而近的幾則比較有效。
MAX_GUIDANCE_LINES = 3


_recent_by_session: "OrderedDict[tuple[str, str, str], Deque[str]]" = OrderedDict()


def _session_key(
    conf_uid: str, history_uid: str, client_uid: str
) -> tuple[str, str, str]:
    return (str(conf_uid or ""), str(history_uid or ""), str(client_uid or ""))


def _normalize(text: str) -> str:
    """壓掉空白差異。串流拼出來的文字，空白與換行位置會漂移。"""
    return " ".join(str(text or "").split())


def _touch(key: tuple[str, str, str]) -> None:
    if key in _recent_by_session:
        _recent_by_session.move_to_end(key)
    while len(_recent_by_session) > MAX_SESSIONS:
        _recent_by_session.popitem(last=False)


def record_reply(
    conf_uid: str, history_uid: str, client_uid: str, response: str
) -> None:
    """記下一則已經說出口的回覆。

    history_uid 為空就不記：這則狀態現在跟著對話走，沒有對話可歸屬的東西
    不留底，免得下一段對話（不管是換了 history_uid 還是連線初始化中途）
    意外收到不屬於它的種子。跟 memory_core 的規則一致——見模組開頭。
    """
    if not history_uid:
        return
    normalized = _normalize(response)
    if not normalized:
        return
    key = _session_key(conf_uid, history_uid, client_uid)
    recent = _recent_by_session.setdefault(key, deque(maxlen=MAX_RECENT_REPLIES))
    recent.append(normalized)
    _touch(key)


def recent_sentences(conf_uid: str, history_uid: str, client_uid: str) -> list:
    """最近幾則回覆拆成句子，給跨輪的逐句護欄當種子。

    拆句用的是 conversation_quality 那份切分規則，跟護欄自己在同一則回覆裡
    的切法一致——兩邊用不同的規則會讓「同一句」在兩個地方長得不一樣。

    history_uid 為空就回空清單：見模組開頭「history_uid 為空」的說明。
    """
    if not history_uid:
        return []
    recent = list(
        _recent_by_session.get(_session_key(conf_uid, history_uid, client_uid), ())
    )
    out: list = []
    for reply in recent[-MAX_GUIDANCE_LINES:]:
        out.extend(part for part in SENTENCE_SPLIT_RE.split(reply) if part.strip())
    return out


def build_recent_reply_guidance(
    conf_uid: str, history_uid: str, client_uid: str
) -> str:
    """組出「你最近說過這些，不要重複」，附在當輪的輸入後面。

    這是預防，不是事後補救。實測顯示：等整則生成完才發現重複、再叫模型重寫，
    在真實的系統提示裡沒有用——那段提示被人設、記憶、表情規則埋掉了。反過來
    在生成之前就把「剛講過什麼」擺在輸入的最後面，是主動發言那條路已經驗證
    有效的做法。

    沒有東西可列就回空字串：第一輪不該憑空多出一段沒有指涉對象的「不要重複」。
    history_uid 為空同樣回空字串——見模組開頭的說明。
    """
    if not history_uid:
        return ""
    recent = list(
        _recent_by_session.get(_session_key(conf_uid, history_uid, client_uid), ())
    )
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


def reset_for_tests() -> None:
    """清空模組層的狀態。測試之間不該互相污染。"""
    _recent_by_session.clear()
